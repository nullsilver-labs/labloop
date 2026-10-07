#!/usr/bin/env python3
"""bits: a generated next-symbol prediction benchmark for comparing the lab's loop.

    world.py gen <name> <project_dir> <private_dir> [--python PATH] [--threads N]

builds one world: a hidden random source over 16 symbols, sampled into documents.
Workers see the train documents and, for search and final, every document but its
last symbol; they predict a distribution over that symbol. The evaluator scores the
mean code length in bits as the fraction of the gap closed between the unigram
baseline (0) and the source's own conditional distribution (1).

The source stacks mechanisms of similar size, so no single draft finds them all:
  regime  three sticky regimes, each a variable-order Markov model (depth 1-3)
  copy    long repeats of the same document from a random earlier offset
  rule    at positions t = phase (mod period), x_t = (x_{t-a} + c*x_{t-b} + k) mod 16

The world's random draw comes from sha256(secret, name), and the secret lives only in
$LAB_PRIVATE/bits.secret, shared by every campaign there, so the two arms of a pair
that name the same world get the same data. A worker that reads this file still cannot regenerate the
labels. It does learn the mechanisms, which spoils the benchmark, so keep this repo
out of the workers' reach and check transcripts for it (README.md).

Stdlib only. Deterministic given (secret, name).
"""
import argparse, hashlib, json, math, os, random, secrets, shutil, sys
from bisect import bisect_right
from pathlib import Path

K = 16
HEX = "0123456789abcdef"
HERE = Path(__file__).resolve().parent

# the knobs that define the family; every world draws its specifics inside these
FAMILY = {
    "regimes": 3, "switch_p": 1 / 300, "depth_weights": [0.3, 0.4, 0.3], "alpha": 0.25,
    "copy_start_p": 1 / 120, "copy_end_p": 1 / 40, "copy_fidelity": 0.95,
    "copy_min_t": 64, "copy_min_off": 32, "copy_max_off": 1024,
    "rule_period": [9, 15], "rule_max_lag": 24, "rule_fidelity": 0.98,
    "train_docs": 1200, "train_len": [600, 2400],
    "query_docs": 4000, "query_len": [64, 2048],
}


def dirichlet(rng, alpha, k=K):
    g = [rng.gammavariate(alpha, 1.0) for _ in range(k)]
    s = sum(g)
    if s <= 0:
        g, s = [1.0] * k, float(k)
    return [x / s for x in g]


class World:
    def __init__(self, seed_bytes: bytes):
        f = FAMILY
        rng = random.Random(int.from_bytes(seed_bytes, "big"))
        self.f = f
        self.R = f["regimes"]
        # per regime: depth by last symbol, then one distribution per context
        self.depth, self.table = [], []
        for _ in range(self.R):
            depth = [rng.choices([1, 2, 3], f["depth_weights"])[0] for _ in range(K)]
            dists, table = {}, []
            for c in range(K ** 3):                     # c = x[t-1] + 16 x[t-2] + 256 x[t-3]
                d = depth[c % K]
                key = (d, c % (K ** d))
                if key not in dists:
                    p = dirichlet(rng, f["alpha"])
                    cum, acc = [], 0.0
                    for v in p:
                        acc += v
                        cum.append(acc)
                    dists[key] = (p, cum)
                table.append(dists[key])
            self.depth.append(depth)
            self.table.append(table)
        lo, hi = f["rule_period"]
        self.period = rng.randint(lo, hi)
        self.phase = rng.randrange(self.period)
        self.lag_a, self.lag_b = sorted(rng.sample(range(1, f["rule_max_lag"] + 1), 2))
        self.rule_c = rng.choice([1, 3, 5, 7, 9, 11, 13, 15])
        self.rule_k = rng.randrange(K)
        self.rng = random.Random(rng.getrandbits(64))   # sampling stream

    def params(self) -> dict:
        return {"family": self.f, "period": self.period, "phase": self.phase,
                "lag_a": self.lag_a, "lag_b": self.lag_b, "rule_c": self.rule_c,
                "rule_k": self.rule_k, "depth": self.depth}

    # --- the source -----------------------------------------------------------------

    def ctx(self, x, t):
        a = x[t - 1] if t >= 1 else 0
        b = x[t - 2] if t >= 2 else 0
        c = x[t - 3] if t >= 3 else 0
        return a + K * b + K * K * c

    def is_rule(self, t):
        return t >= self.f["rule_max_lag"] and t % self.period == self.phase

    def rule_sym(self, x, t):
        return (x[t - self.lag_a] + self.rule_c * x[t - self.lag_b] + self.rule_k) % K

    def sample_doc(self, n):
        """Return (symbols, latent state before the last step, branch used at the last step)."""
        f, rng = self.f, self.rng
        x = []
        r = rng.randrange(self.R)
        copy_d = 0                                      # 0 = not copying
        state = branch = None
        for t in range(n):
            if t == n - 1:
                state = (r, copy_d)
            if rng.random() < f["switch_p"]:
                r = rng.choice([q for q in range(self.R) if q != r])
            if copy_d:
                if rng.random() < f["copy_end_p"]:
                    copy_d = 0
            elif t >= f["copy_min_t"] and rng.random() < f["copy_start_p"]:
                copy_d = rng.randint(f["copy_min_off"], min(t, f["copy_max_off"]))
            if self.is_rule(t) and rng.random() < f["rule_fidelity"]:
                s, br = self.rule_sym(x, t), "rule"
            elif copy_d and rng.random() < f["copy_fidelity"]:
                s, br = x[t - copy_d], "copy"
            else:
                cum = self.table[r][self.ctx(x, t)][1]
                s, br = min(bisect_right(cum, rng.random()), K - 1), "regime"
            x.append(s)
            if t == n - 1:
                branch = br
        return x, state, branch

    def regime_mix(self, x, t, r):
        """P(x_t | regime at t-1 = r), marginal over the regime transition."""
        sw = self.f["switch_p"]
        c = self.ctx(x, t)
        out = [(1 - sw) * v for v in self.table[r][c][0]]
        for q in range(self.R):
            if q != r:
                p = self.table[q][c][0]
                w = sw / (self.R - 1)
                for i in range(K):
                    out[i] += w * p[i]
        return out

    def oracle(self, x, t, state):
        """The source's distribution of x_t given the past and the latent state at t-1."""
        f = self.f
        r, copy_d = state
        preg = self.regime_mix(x, t, r)
        if copy_d:
            fid, end = f["copy_fidelity"], f["copy_end_p"]
            pc = [end * v + (1 - end) * (1 - fid) * v for v in preg]
            pc[x[t - copy_d]] += (1 - end) * fid
        elif t >= f["copy_min_t"]:
            hist = [0.0] * K
            offs = range(f["copy_min_off"], min(t, f["copy_max_off"]) + 1)
            for d in offs:
                hist[x[t - d]] += 1.0
            n = len(offs)
            st, fid = f["copy_start_p"], f["copy_fidelity"]
            pc = [(1 - st) * v + st * (1 - fid) * v + st * fid * h / n for v, h in zip(preg, hist)]
        else:
            pc = preg
        if self.is_rule(t):
            rf = f["rule_fidelity"]
            out = [(1 - rf) * v for v in pc]
            out[self.rule_sym(x, t)] += rf
            return out
        return pc


def unigram(train_docs):
    cnt = [1.0] * K
    for d in train_docs:
        for s in d:
            cnt[s] += 1
    tot = sum(cnt)
    return [c / tot for c in cnt]


def bits_of(p, y, eps=1e-3):
    """Code length of y under p mixed with eps of uniform, exactly as score.py computes it."""
    return -math.log2((1 - eps) * p[y] / sum(p) + eps / K)


def gen(args):
    proj, priv = Path(args.project).resolve(), Path(args.private).resolve()
    priv.mkdir(parents=True, exist_ok=True)
    os.chmod(priv, 0o700)
    sec_path = Path(args.secret).resolve() if args.secret else priv.parent / "bits.secret"
    if not sec_path.exists():
        sec_path.write_text(secrets.token_hex(16) + "\n")
        os.chmod(sec_path, 0o600)
    seed = hashlib.sha256((sec_path.read_text().strip() + ":" + args.name).encode()).digest()
    w = World(seed)
    f = FAMILY

    train = [w.sample_doc(w.rng.randint(*f["train_len"]))[0] for _ in range(f["train_docs"])]
    uni = unigram(train)
    (proj / "data/train").mkdir(parents=True, exist_ok=True)
    with open(proj / "data/train/train.txt", "w") as fh:
        for d in train:
            fh.write("".join(HEX[s] for s in d) + "\n")

    summary = {"world": args.name, "train_docs": len(train),
               "train_symbols": sum(map(len, train))}
    for split in ("search", "final"):
        labels, oracle_bits, base_bits, branches = [], [], [], []
        (proj / "data" / split).mkdir(parents=True, exist_ok=True)
        with open(proj / "data" / split / "inputs.txt", "w") as fh:
            for _ in range(f["query_docs"]):
                x, state, br = w.sample_doc(w.rng.randint(*f["query_len"]))
                t, y = len(x) - 1, x[-1]
                fh.write("".join(HEX[s] for s in x[:-1]) + "\n")
                labels.append(y)
                oracle_bits.append(bits_of(w.oracle(x, t, state), y))
                base_bits.append(bits_of(uni, y))
                branches.append(br)
        (priv / split).mkdir(exist_ok=True)
        rec = {"world": args.name, "labels": labels, "branch": branches,
               "oracle_bits": sum(oracle_bits) / len(labels),
               "baseline_bits": sum(base_bits) / len(labels),
               "oracle_bits_each": [round(b, 5) for b in oracle_bits],
               "eps": 1e-3}
        with open(priv / split / "labels.json", "w") as fh:
            json.dump(rec, fh)
        summary[split] = {"n": len(labels), "baseline_bits": round(rec["baseline_bits"], 4),
                          "oracle_bits": round(rec["oracle_bits"], 4),
                          "branch_share": {b: round(branches.count(b) / len(branches), 3)
                                           for b in ("regime", "copy", "rule")}}
    with open(priv / "world.json", "w") as fh:
        json.dump({"name": args.name, "params": w.params(), "summary": summary}, fh)

    if args.scaffold:
        scaffold(proj, args)
    print(json.dumps(summary, indent=1))


def scaffold(proj, args):
    """Copy the evaluator and baseline and fill the task and campaign templates."""
    (proj / "eval").mkdir(exist_ok=True)
    for src, dst in (("score.py", "eval/score.py"), ("baseline.sh", "eval/baseline.sh")):
        shutil.copy(HERE / src, proj / dst)
        os.chmod(proj / dst, 0o755)
    subs = {"@PYTHON@": args.python, "@THREADS@": str(args.threads),
            "@CAMPAIGN@": args.campaign or f"bits-{args.name}",
            "@MINUTES@": str(args.minutes)}
    for src, dst in (("task.md.in", "task.md"), ("campaign.toml.in", "campaign.toml")):
        p = proj / dst
        if p.exists() and not args.force:
            print(f"kept existing {dst} (use --force to overwrite)", file=sys.stderr)
            continue
        body = (HERE / src).read_text()
        for k, v in subs.items():
            body = body.replace(k, v)
        p.write_text(body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="generate one world into a project and its private dir")
    g.add_argument("name", help="public world name, e.g. w1 (the secret makes it unguessable)")
    g.add_argument("project", help="project dir: data/{train,search,final} are written here")
    g.add_argument("private", help="private dir: $LAB_PRIVATE/<campaign>; labels.json per split and world.json")
    g.add_argument("--secret", help="secret file (default <private>/../bits.secret, shared by every "
                   "campaign under $LAB_PRIVATE, so two arms with the same name get the same world)")
    g.add_argument("--scaffold", action="store_true", help="also write eval/, task.md, campaign.toml")
    g.add_argument("--campaign", help="campaign id for the scaffold (default bits-<name>)")
    g.add_argument("--python", default="/usr/bin/python3", help="interpreter for code/run.sh (needs numpy)")
    g.add_argument("--threads", type=int, default=4, help="threads per job, told to workers")
    g.add_argument("--minutes", type=int, default=5, help="run.sh wall-clock limit told to workers")
    g.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.cmd == "gen":
        gen(args)


if __name__ == "__main__":
    main()
