#!/usr/bin/env python3
"""calibrate.py <project_dir> <private_dir> [--secret FILE] [--split search] [--probes ...]

Operator only: reads hidden labels and the world's parameters. Fits reference
predictors of known strength on one world and scores each with eval/score.py, plus
a per-mechanism breakdown (which branch of the source emitted the scored symbol).
A world family is usable only if

  unigram  ~ 0      the baseline is what the evaluator calls 0
  ngram    << 1     an obvious first draft leaves most of the gap
  generic  <  ref   a good mechanism-blind model still leaves a mechanism unfound
  ref      ~ .95    a model that knows the mechanisms (true parameters, inferred
                    latents) gets near 1: the ceiling is reachable

Each probe also reports bits per branch of the source next to the source's own.
Stdlib only; a few minutes per world on one core.
"""
import argparse, hashlib, json, math, subprocess, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import world as W  # noqa: E402

K = W.K


def read_docs(path):
    return [[int(c, 16) for c in line.strip()] for line in open(path) if line.strip()]


def norm(p):
    s = sum(p)
    return [v / s for v in p]


# --- probes -----------------------------------------------------------------------

def p_unigram(train, inputs):
    u = W.unigram(train)
    return [u for _ in inputs]


class NGram:
    """Interpolated Witten-Bell n-gram, orders 0..N, pooled over all training docs."""

    def __init__(self, train, order=4):
        self.N = order
        self.cnt = [defaultdict(lambda: [0] * K) for _ in range(order + 1)]
        for d in train:
            for t, s in enumerate(d):
                for n in range(order + 1):
                    if t >= n:
                        self.cnt[n][tuple(d[t - n:t])][s] += 1

    def predict(self, x, t):
        p = [1.0 / K] * K
        for n in range(self.N + 1):
            if t < n:
                break
            c = self.cnt[n].get(tuple(x[t - n:t]))
            if not c:
                break
            tot, typ = sum(c), sum(1 for v in c if v)
            lam = tot / (tot + typ)
            p = [lam * v / tot + (1 - lam) * q for v, q in zip(c, p)]
        return p


def p_ngram(train, inputs, order=4):
    m = NGram(train, order)
    return [m.predict(x, len(x)) for x in inputs]


def match_pred(x, t, min_len=8, max_off=1500):
    """Mechanism-blind match model: the offsets whose preceding min_len symbols equal ours."""
    if t < min_len + 1:
        return None
    tail = x[t - min_len:t]
    votes = [0] * K
    hit = 0
    for d in range(1, min(t - min_len, max_off) + 1):
        if x[t - d - min_len:t - d] == tail:
            votes[x[t - d]] += 1
            hit += 1
    return (votes, hit) if hit else None


def p_generic(train, inputs):
    """n-gram + match model + a document-local order-2 cache, with fixed mixing weights."""
    m = NGram(train, 4)
    out = []
    for x in inputs:
        t = len(x)
        p = m.predict(x, t)
        loc = defaultdict(lambda: [0] * K)
        for i in range(2, t):
            loc[(x[i - 2], x[i - 1])][x[i]] += 1
        c = loc.get((x[t - 2], x[t - 1])) if t >= 2 else None
        if c and sum(c) >= 3:
            tot = sum(c)
            w = tot / (tot + 8)
            p = [(1 - w) * a + w * (v + 0.1) / (tot + 1.6) for a, v in zip(p, c)]
        mp = match_pred(x, t)
        if mp:
            votes, hit = mp
            p = [0.1 * a + 0.9 * v / hit for a, v in zip(p, votes)]
        out.append(p)
    return out


def p_reference(world, inputs):
    """Knows the source's parameters, infers its latents: a forward filter over regimes
    (rule positions skipped, copies ignored as noise), a posterior over copy offsets
    from the run of agreement before t, and the rule. An achievable ceiling, not the oracle."""
    f = world.f
    R, sw = world.R, f["switch_p"]
    out = []
    for x in inputs:
        t = len(x)
        post = [1.0 / R] * R
        for i in range(t):
            prior = [(1 - sw) * post[r] + sw * (1 - post[r]) / (R - 1) for r in range(R)]
            if world.is_rule(i):
                post = prior
                continue
            c = world.ctx(x, i)
            lik = [0.9 * world.table[r][c][0][x[i]] + 0.1 / K for r in range(R)]
            z = sum(p * l for p, l in zip(prior, lik))
            post = [p * l / z for p, l in zip(prior, lik)]
        preg = [0.0] * K
        for r in range(R):
            for i, v in enumerate(world.regime_mix(x, t, r)):
                preg[i] += post[r] * v
        # copy: a posterior over offsets from the run of agreement ending at t (one
        # mismatch allowed, rule positions skipped), against "not copying"
        fid, end, st = f["copy_fidelity"], f["copy_end_p"], f["copy_start_p"]
        offs = range(f["copy_min_off"], min(t, f["copy_max_off"]) + 1) if t >= f["copy_min_t"] else range(0)
        in_copy = st / (st + end)                       # stationary share of copying steps
        weights = {}
        for d in offs:
            m, mis, j = 0, 0, 1
            while j <= min(24, t - d):
                if not world.is_rule(t - j):
                    if x[t - j] == x[t - j - d]:
                        m += 1
                    else:
                        mis += 1
                        if mis > 1:
                            break
                j += 1
            if m >= 3:
                weights[d] = in_copy / len(offs) * (1 - end) ** j * 5.0 ** m * 0.25 ** mis
        z = 1 - in_copy + sum(weights.values())
        p = [0.0] * K
        for d, wd in weights.items():
            a = wd / z * (1 - end)
            p[x[t - d]] += a * fid
            p = [q + (wd / z - a * fid) * v for q, v in zip(p, preg)]
        rest = (1 - in_copy) / z
        if offs:
            hist = [0.0] * K
            for d in offs:
                hist[x[t - d]] += 1.0
            p = [q + rest * ((1 - st * fid) * v + st * fid * h / len(offs))
                 for q, v, h in zip(p, preg, hist)]
        else:
            p = [q + rest * v for q, v in zip(p, preg)]
        if world.is_rule(t):
            rf = f["rule_fidelity"]
            p = [(1 - rf) * v for v in norm(p)]
            p[world.rule_sym(x, t)] += rf
        out.append(norm(p))
    return out


# --- scoring ----------------------------------------------------------------------

def score(preds, labels_dir, tmp):
    tmp.write_text(json.dumps(preds))
    cp = subprocess.run([sys.executable, str(HERE / "score.py"), str(tmp), str(labels_dir)],
                        capture_output=True, text=True, check=True)
    return json.loads(cp.stdout)


def breakdown(preds, lab):
    eps, by, orc = lab["eps"], defaultdict(list), defaultdict(list)
    for p, y, br, ob in zip(preds, lab["labels"], lab["branch"], lab["oracle_bits_each"]):
        by[br].append(W.bits_of(p, y, eps))
        orc[br].append(ob)
    return {br: {"share": round(len(v) / len(preds), 3), "bits": round(sum(v) / len(v), 3),
                 "oracle": round(sum(orc[br]) / len(v), 3)} for br, v in sorted(by.items())}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("private")
    ap.add_argument("--secret")
    ap.add_argument("--split", default="search")
    ap.add_argument("--probes", nargs="+", default=["unigram", "ngram", "generic", "reference"])
    ap.add_argument("--limit", type=int, default=0, help="score only the first N queries (fast look)")
    args = ap.parse_args()
    proj, priv = Path(args.project), Path(args.private)
    lab = json.load(open(priv / args.split / "labels.json"))
    train = read_docs(proj / "data/train/train.txt")
    inputs = read_docs(proj / "data" / args.split / "inputs.txt")
    if args.limit:
        inputs = inputs[:args.limit]
        for k in ("labels", "branch", "oracle_bits_each"):
            lab[k] = lab[k][:args.limit]
        n = len(inputs)
        lab["oracle_bits"] = sum(lab["oracle_bits_each"]) / n
        lab["baseline_bits"] = sum(W.bits_of(W.unigram(train), y, lab["eps"]) for y in lab["labels"]) / n
    sub = priv / ".calibrate"
    sub.mkdir(exist_ok=True)
    (sub / "labels.json").write_text(json.dumps(lab))
    sec = Path(args.secret) if args.secret else priv.parent / "bits.secret"
    name = json.load(open(priv / "world.json"))["name"]
    world = W.World(hashlib.sha256((sec.read_text().strip() + ":" + name).encode()).digest())

    report = {"world": name, "split": args.split, "n": len(inputs),
              "baseline_bits": round(lab["baseline_bits"], 4), "oracle_bits": round(lab["oracle_bits"], 4),
              "probes": {}}
    for probe in args.probes:
        preds = {"unigram": lambda: p_unigram(train, inputs),
                 "ngram": lambda: p_ngram(train, inputs),
                 "generic": lambda: p_generic(train, inputs),
                 "reference": lambda: p_reference(world, inputs)}[probe]()
        s = score(preds, sub, sub / f"pred-{probe}.json")
        each = [W.bits_of(p, y, lab["eps"]) for p, y in zip(preds, lab["labels"])]
        mu = sum(each) / len(each)
        sd = math.sqrt(sum((b - mu) ** 2 for b in each) / (len(each) - 1))
        gap = lab["baseline_bits"] - lab["oracle_bits"]
        report["probes"][probe] = {"score": round(s["score"], 4), "bits": round(s["bits"], 4),
                                   "score_se": round(sd / math.sqrt(len(each)) / gap, 4),
                                   "by_branch": breakdown(preds, lab)}
        print(f"{probe:10s} score {s['score']:.4f}  bits {s['bits']:.4f}", file=sys.stderr, flush=True)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
