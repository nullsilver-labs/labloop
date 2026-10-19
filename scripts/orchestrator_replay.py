"""orchestrator_replay.py: plan §5's zero-GPU replay, a decision model re-decides recorded ticks.

For every recorded selection tick of a finished campaign (an improve or crossover job,
not a draft, a debug retry or a re-dispatch), the population is rebuilt as it stood at
dispatch (the candidates that had ended before the job was launched, their finding
cards and knobs) and a decision backend is asked, in this order:

    1. parent   Choice over the eligible candidates (criteria = one card per candidate)
    2. operator Choice over {improve, crossover} given the parent
    3. partner  Choice over the eligible candidates minus the parent, if crossover

Each answer is a distribution with a confidence. The replay records, per tick, the
chance choice the campaign made, the backend's argmax, a draw from its distribution
with a fixed seed (the campaign design samples, it never argmaxes), the probability the
backend put on the chance parent and on the lineage that produced the frozen candidate,
latency, state size and errors. Nothing about search quality is claimed: the
counterfactual children are never run.

    scripts/orchestrator_replay.py PROJECT [PROJECT ...] --out DIR [--backend jev|none]
        [--seed 0] [--card-chars 1500] [--task-chars 2500] [--max-ticks N]

Read-only on the projects; never reads labels, the fitness of any split but the search
one (the lab's population record), REPORT.md or a final score. The Jev backend needs
TYPESAFE_API_KEY in the environment or in ./.env; the key is never written anywhere.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

POPULATION_FILE = "population" + ".json"   # the lab's record, read only

OUTCOME_KEYS = {"steps", "examples_seen", "epochs_started", "final_loss", "wall_seconds",
                "trainable_params", "seed", "train_wall_s", "params", "total_params"}
OUTCOME_PREFIXES = ("holdout_", "val_", "final_", "eval_", "test_", "measured_",
                    "last_logged_", "logged_")

PARENT_INSTRUCTIONS = (
    "You are the scheduler of an evolutionary code search. Each option is one settled "
    "candidate of the population, described by its finding card (what it changed, what it "
    "hypothesised, what was observed, what it concluded, its limits) and its search score "
    "(higher is better; the baseline is the trivial predictor). The state holds the task, "
    "the population table with lineage and scores, and a knob index: for every training "
    "knob, the values already tried and by whom. Which candidate should the next job build "
    "on? Prefer a candidate whose line still has headroom on the task; avoid a line whose "
    "last change is a knob and direction the index already covers; weigh the strongest "
    "branch outside the lineage that has received the most jobs; a low-scoring candidate "
    "that carries an untried idea can be worth one job.")
OPERATOR_INSTRUCTIONS = (
    "The next job builds on the chosen parent (state.parent). Should it be an improve (one "
    "hypothesised change to the parent's code) or a crossover (combine the parent with a "
    "second candidate's idea)? Crossover is worth it when two lines hold complementary "
    "changes; improve when the parent's own line has an obvious next step.")
PARTNER_INSTRUCTIONS = (
    "The next job is a crossover of the chosen parent (state.parent) with a second "
    "candidate. Which candidate carries the change most worth combining with the parent's?")


# ---------------------------------------------------------------------------
# recorded campaigns
# ---------------------------------------------------------------------------

def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def campaign_id(project: Path) -> str:
    m = re.search(r'^id\s*=\s*"([^"]+)"', (project / "campaign.toml").read_text(), re.M)
    return m.group(1) if m else project.name


def load_rows(project: Path) -> list[dict]:
    pop = json.loads((project / POPULATION_FILE).read_text())
    rows = pop["candidates"] if isinstance(pop, dict) else pop
    rows = list(rows.values()) if isinstance(rows, dict) else rows
    return sorted(rows, key=lambda r: r["id"])


def load_cards(project: Path, rows: list[dict]) -> dict[str, dict]:
    cards = {}
    for r in rows:
        d = project / "candidates" / r["id"]
        p = d / "finding.json"
        if p.exists():
            cards[r["id"]] = json.loads(p.read_text())
            continue
        # a legacy campaign has no card: the summary's head stands in, and the knobs
        # file when the worker wrote one, so the same replay runs over every arm
        s = d / "summary.md"
        if s.exists():
            text = " ".join(line.strip() for line in s.read_text().splitlines() if line.strip())
            knobs = {}
            k = d / "out" / "memory_config.json"
            if k.exists():
                try:
                    knobs = json.loads(k.read_text())
                except ValueError:
                    knobs = {}
            cards[r["id"]] = {"report": {"change": text[:1500]}, "knobs": knobs, "synthesised_from": "summary.md"}
    return cards


def is_outcome(key: str) -> bool:
    return key in OUTCOME_KEYS or key.startswith(OUTCOME_PREFIXES)


def card_text(r: dict, card: dict | None, limit: int) -> str:
    head = f"{r['id']} ({r['operator']}" + (f" of {', '.join(r['parents'])}" if r["parents"] else "") + \
           f"), search score {r['fitness']:.4f}."
    if not card:
        return head + " No finding card."
    rep = card.get("report") or {}
    parts = []
    for k, label in (("change", "Change"), ("hypothesis", "Hypothesis"),
                     ("local_observation", "Observed"), ("interpretation", "Interpretation"),
                     ("limitations", "Limits")):
        v = rep.get(k)
        if v:
            parts.append(f"{label}: {v}")
    cav = card.get("caveats") or []
    if cav:
        parts.append("Caveats: " + " ".join(cav))
    text = head + " " + " ".join(parts)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def knob_index(rows: list[dict], cards: dict[str, dict]) -> str:
    index: dict[str, dict[str, list[str]]] = {}
    for r in rows:
        knobs = (cards.get(r["id"]) or {}).get("knobs") or {}
        for k, v in knobs.items():
            if is_outcome(k):
                continue
            index.setdefault(k, {}).setdefault(json.dumps(v, sort_keys=True), []).append(r["id"])
    lines = []
    for k in sorted(index):
        vals = "; ".join(f"{v} ({', '.join(ids)})" for v, ids in index[k].items())
        lines.append(f"{k}: {vals}")
    return "\n".join(lines)


def bookkeeping(elig: list[dict], cards: dict[str, dict]) -> dict[str, dict]:
    """Per eligible candidate: children, jobs in its subtree, knobs changed vs its parent."""
    ids = {r["id"] for r in elig}
    children: dict[str, list[str]] = {i: [] for i in ids}
    for r in elig:
        for p in r["parents"] or []:
            if p in children:
                children[p].append(r["id"])

    def subtree(c: str) -> int:
        seen, stack = set(), list(children[c])
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(children[x])
        return len(seen)

    out = {}
    for r in elig:
        knobs = (cards.get(r["id"]) or {}).get("knobs") or {}
        changed = {}
        if r["parents"]:
            pk = (cards.get(r["parents"][0]) or {}).get("knobs") or {}
            for k, v in knobs.items():
                if not is_outcome(k) and pk.get(k) != v:
                    changed[k] = [pk.get(k), v]
        out[r["id"]] = {"children": len(children[r["id"]]), "jobs_in_line": subtree(r["id"]),
                        "changed_vs_parent": changed}
    return out


def book_text(b: dict) -> str:
    ch = "; ".join(f"{k} {a}→{v}" for k, (a, v) in b["changed_vs_parent"].items()) or "none recorded"
    return (f"Bookkeeping: {b['children']} job(s) already built directly on it, {b['jobs_in_line']} in its "
            f"line; knobs its change moved: {ch}.")


def ticks_of(rows: list[dict]) -> list[dict]:
    out = [r for r in rows if r["operator"] in ("improve", "crossover") and not r.get("redispatch_of")
           and r.get("launched")]
    return sorted(out, key=lambda r: ts(r["launched"]))


def eligible_at(rows: list[dict], tick: dict) -> list[dict]:
    t0 = ts(tick["launched"])
    return [r for r in rows if r["id"] != tick["id"] and r.get("exec") == "completed"
            and r.get("ended") and ts(r["ended"]) <= t0 and r.get("fitness") is not None]


def lineage_of(rows: list[dict], cid: str) -> set[str]:
    by = {r["id"]: r for r in rows}
    seen, stack = set(), [cid]
    while stack:
        c = stack.pop()
        if c in seen or c not in by:
            continue
        seen.add(c)
        stack.extend(by[c]["parents"] or [])
    return seen


# ---------------------------------------------------------------------------
# backends
# ---------------------------------------------------------------------------

def load_env_key() -> str | None:
    k = os.environ.get("TYPESAFE_API_KEY")
    if k:
        return k
    p = Path(".env")
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("TYPESAFE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


class Jev:
    """TypeSafe AI's Jev, the Choice primitive over HTTP. Filled from the API notes of
    2026-09-16 (scratch typesafe-api.md); standard library only."""

    BASE = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
    PATH = "/v1/systemone"
    MODEL = os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-latest")   # the reply names the served version
    name = "jev"

    def __init__(self) -> None:
        self.key = load_env_key()
        if not self.key:
            sys.exit("TYPESAFE_API_KEY not set and not in ./.env")

    def choice(self, qid: str, instructions: str, criteria: dict[str, str], state: dict) -> dict:
        body = {"state": state, "model": self.MODEL,
                "questions": {qid: {"type": "choice", "instructions": instructions,
                                    "criteria": criteria}}}
        data = json.dumps(body).encode()
        req = urllib.request.Request(self.BASE + self.PATH, data=data, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.key}"})
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = json.loads(resp.read().decode())
                status = resp.status
        except urllib.error.HTTPError as e:
            return {"error": f"http {e.code}: {e.read().decode()[:300]}", "status": e.code,
                    "latency_s": time.monotonic() - t0, "bytes": len(data)}
        except Exception as e:  # noqa: BLE001
            return {"error": f"{type(e).__name__}: {e}", "status": None,
                    "latency_s": time.monotonic() - t0, "bytes": len(data)}
        lat = time.monotonic() - t0
        ans = self.parse(raw, qid)
        ans.update({"status": status, "latency_s": lat, "bytes": len(data)})
        return ans

    @staticmethod
    def parse(raw: dict, qid: str) -> dict:
        """{model, answers: {qid: {type, choice, confidence, probabilities}}, usage}."""
        a = (raw.get("answers") or {}).get(qid)
        if not isinstance(a, dict):
            return {"error": f"no answer for {qid!r} in reply", "raw": raw}
        return {"choice": a.get("choice"), "probabilities": a.get("probabilities") or {},
                "confidence": a.get("confidence"), "model": raw.get("model"),
                "usage": raw.get("usage"), "raw": raw}


class NoBackend:
    name = "none"

    def choice(self, qid, instructions, criteria, state) -> dict:  # noqa: ANN001
        return {"choice": None, "probabilities": {}, "confidence": None, "status": None,
                "latency_s": 0.0, "bytes": len(json.dumps({"state": state, "criteria": criteria}))}


# ---------------------------------------------------------------------------
# the replay
# ---------------------------------------------------------------------------

def replay_project(project: Path, backend, args) -> dict:
    rows = load_rows(project)
    cards = load_cards(project, rows)
    task = (project / "task.md").read_text()[: args.task_chars]
    frozen = next((r["id"] for r in rows if r.get("status") == "frozen"), None)
    lineage = lineage_of(rows, frozen) if frozen else set()
    rng = random.Random(args.seed)
    records = []
    for tick in ticks_of(rows)[: args.max_ticks or None]:
        elig = eligible_at(rows, tick)
        if len(elig) < 2:
            continue
        table = [{"id": r["id"], "operator": r["operator"], "parents": r["parents"],
                  "search_score": round(r["fitness"], 4)} for r in elig]
        best = max(elig, key=lambda r: r["fitness"])["id"]
        state = {"task": task, "population": table, "best_so_far": best,
                 "knob_index": knob_index(elig, cards), "jobs_so_far": tick["id"]}
        criteria = {r["id"]: card_text(r, cards.get(r["id"]), args.card_chars) for r in elig}
        if args.bookkeeping:
            # the bookkeeping the instruction asks for, made explicit: how many jobs each
            # candidate and each line already received, and what each change touched
            book = bookkeeping(elig, cards)
            for row in table:
                row.update(book[row["id"]])
            state["bookkeeping_note"] = ("children = jobs already built directly on this candidate; "
                                         "jobs_in_line = jobs in its whole subtree; changed_vs_parent = "
                                         "knobs its own change moved, with the values")
            criteria = {k: v + " " + book_text(book[k]) for k, v in criteria.items()}
        if args.hide_scores:
            # ablation: no score anywhere, so the distribution can only come from the cards
            for row in table:
                row.pop("search_score", None)
            state.pop("best_so_far", None)
            criteria = {k: re.sub(r", search score [0-9.]+\.", ".", v) for k, v in criteria.items()}
        rec = {"tick": tick["id"], "launched": tick["launched"], "eligible": [r["id"] for r in elig],
               "chance": {"operator": tick["operator"], "parents": tick["parents"]},
               "best_so_far": best, "frozen_lineage_parents": sorted(set(tick["parents"]) & lineage)}
        # 1. parent
        a = backend.choice("parent", PARENT_INSTRUCTIONS, criteria, state)
        rec["parent"] = _slim(a)
        probs = a.get("probabilities") or {}
        rec["parent_sampled"] = _draw(rng, probs)
        rec["p_chance_parents"] = sum(probs.get(p, 0.0) for p in tick["parents"])
        rec["p_lineage"] = sum(v for k, v in probs.items() if k in lineage)
        rec["chance_parent_in_lineage"] = any(p in lineage for p in tick["parents"])
        rec["argmax_in_lineage"] = (a.get("choice") in lineage) if a.get("choice") else None
        parent = a.get("choice") or tick["parents"][0]
        # 2. operator
        st2 = dict(state, parent=parent)
        b = backend.choice("operator", OPERATOR_INSTRUCTIONS,
                           {"improve": "one hypothesised change to the parent's own code",
                            "crossover": "combine the parent with a second candidate's change"}, st2)
        rec["operator"] = _slim(b)
        rec["operator_sampled"] = _draw(rng, b.get("probabilities") or {})
        # 3. partner
        if (b.get("choice") == "crossover" or rec["operator_sampled"] == "crossover") and len(elig) > 2:
            crit2 = {k: v for k, v in criteria.items() if k != parent}
            c = backend.choice("partner", PARTNER_INSTRUCTIONS, crit2, st2)
            rec["partner"] = _slim(c)
            rec["partner_sampled"] = _draw(rng, c.get("probabilities") or {})
        records.append(rec)
        sys.stderr.write(f"  {tick['id']}: chance {tick['operator']} {tick['parents']} | "
                         f"argmax {a.get('choice')} {b.get('choice')} conf {a.get('confidence')} "
                         f"{a.get('latency_s', 0):.2f}s {a.get('bytes', 0)} B"
                         + (f" ERROR {a['error']}" if a.get("error") else "") + "\n")
    return {"campaign": campaign_id(project), "project": str(project), "backend": backend.name,
            "seed": args.seed, "card_chars": args.card_chars, "task_chars": args.task_chars,
            "frozen": frozen, "frozen_lineage": sorted(lineage),
            "instructions": {"parent": PARENT_INSTRUCTIONS, "operator": OPERATOR_INSTRUCTIONS,
                             "partner": PARTNER_INSTRUCTIONS},
            "ticks": records}


def _slim(a: dict) -> dict:
    return {k: a.get(k) for k in ("choice", "probabilities", "confidence", "model", "usage", "status",
                                  "latency_s", "bytes", "error")}


def _draw(rng: random.Random, probs: dict) -> str | None:
    if not probs:
        return None
    keys = list(probs)
    w = [max(float(probs[k] or 0.0), 0.0) for k in keys]
    if sum(w) <= 0:
        return None
    return rng.choices(keys, weights=w, k=1)[0]


# ---------------------------------------------------------------------------
# the read
# ---------------------------------------------------------------------------

def summarise(res: dict) -> dict:
    T = res["ticks"]
    n = len(T)
    calls = [t[k] for t in T for k in ("parent", "operator", "partner") if t.get(k)]
    errors = [c for c in calls if c.get("error")]
    ok = [t for t in T if not t["parent"].get("error") and t["parent"].get("choice")]
    lat = [c["latency_s"] for c in calls if c.get("latency_s") is not None and not c.get("error")]
    byt = [t["parent"]["bytes"] for t in T if t["parent"].get("bytes")]

    def frac(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    parent_agree = [t["parent"]["choice"] in t["chance"]["parents"] for t in ok]
    sampled_agree = [t["parent_sampled"] in t["chance"]["parents"] for t in ok if t.get("parent_sampled")]
    op_agree = [t["operator"].get("choice") == t["chance"]["operator"] for t in ok if t["operator"].get("choice")]
    full = [t["parent"]["choice"] in t["chance"]["parents"] and t["operator"].get("choice") == t["chance"]["operator"]
            for t in ok]
    argmax_best = [t["parent"]["choice"] == t["best_so_far"] for t in ok]
    chance_best = [t["best_so_far"] in t["chance"]["parents"] for t in T]
    conf = [t["parent"]["confidence"] for t in ok if t["parent"].get("confidence") is not None]
    calib = []
    if conf:
        pairs = sorted(zip(conf, parent_agree))
        k = max(1, len(pairs) // 3)
        for i in range(0, len(pairs), k):
            chunk = pairs[i:i + k]
            calib.append({"confidence_range": [round(chunk[0][0], 3), round(chunk[-1][0], 3)],
                          "n": len(chunk), "agreement": frac([a for _, a in chunk])})
    tokens = sum(byt) / 4 if byt else 0
    return {"campaign": res["campaign"], "ticks": n, "calls": len(calls), "errors": len(errors),
            "error_samples": [e["error"] for e in errors[:3]],
            "latency_median_s": round(statistics.median(lat), 3) if lat else None,
            "latency_p95_s": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 3) if lat else None,
            "state_bytes_median": int(statistics.median(byt)) if byt else None,
            "state_bytes_max": max(byt) if byt else None,
            "est_input_tokens_total": int(tokens * (len(calls) / max(1, len(byt)))),
            "est_cost_usd": round(tokens * (len(calls) / max(1, len(byt))) * 0.042 / 1e6, 4),
            "parent_agreement_argmax": frac(parent_agree), "parent_agreement_sampled": frac(sampled_agree),
            "operator_agreement_argmax": frac(op_agree), "full_agreement_argmax": frac(full),
            "argmax_is_best_so_far": frac(argmax_best), "chance_took_best_so_far": frac(chance_best),
            "mean_p_on_chance_parents": frac([t["p_chance_parents"] for t in ok]),
            "mean_p_on_frozen_lineage": frac([t["p_lineage"] for t in ok]),
            "chance_parent_in_frozen_lineage": frac([t["chance_parent_in_lineage"] for t in T]),
            "argmax_in_frozen_lineage": frac([t["argmax_in_lineage"] for t in ok if t["argmax_in_lineage"] is not None]),
            "crossover_rate_chance": frac([t["chance"]["operator"] == "crossover" for t in T]),
            "crossover_rate_argmax": frac([t["operator"].get("choice") == "crossover" for t in ok if t["operator"].get("choice")]),
            "crossover_rate_sampled": frac([t.get("operator_sampled") == "crossover" for t in ok if t.get("operator_sampled")]),
            "confidence_median": round(statistics.median(conf), 3) if conf else None,
            "calibration_terciles": calib,
            "model": next((t["parent"].get("model") for t in ok if t["parent"].get("model")), None)}


def write_md(out: Path, sums: list[dict], args) -> None:
    keys = ["ticks", "calls", "errors", "latency_median_s", "latency_p95_s", "state_bytes_median",
            "state_bytes_max", "est_input_tokens_total", "est_cost_usd", "parent_agreement_argmax",
            "parent_agreement_sampled", "operator_agreement_argmax", "full_agreement_argmax",
            "argmax_is_best_so_far", "chance_took_best_so_far", "mean_p_on_chance_parents",
            "mean_p_on_frozen_lineage", "chance_parent_in_frozen_lineage", "argmax_in_frozen_lineage",
            "crossover_rate_chance", "crossover_rate_argmax", "crossover_rate_sampled",
            "confidence_median", "model"]
    from datetime import timezone
    lines = [f"# Orchestrator replay ({args.backend}{', scores hidden' if args.hide_scores else ''}"
             f"{', bookkeeping explicit' if args.bookkeeping else ''}), "
             f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}", "",
             f"Seed {args.seed}; cards clipped to {args.card_chars} chars, task to {args.task_chars}. "
             "Read-only replay of recorded ticks; counterfactual children never run.", "",
             "| measure | " + " | ".join(s["campaign"] for s in sums) + " |",
             "|---|" + "---|" * len(sums)]
    for k in keys:
        lines.append(f"| {k} | " + " | ".join(str(s.get(k)) for s in sums) + " |")
    lines.append("")
    for s in sums:
        if s["calibration_terciles"]:
            lines.append(f"Calibration, {s['campaign']} (parent confidence terciles vs agreement with chance): "
                         + "; ".join(f"[{c['confidence_range'][0]}, {c['confidence_range'][1]}] n={c['n']} "
                                     f"agree={c['agreement']}" for c in s["calibration_terciles"]))
        if s["error_samples"]:
            lines.append(f"Errors, {s['campaign']}: " + " | ".join(s["error_samples"]))
    (out / "REPLAY.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("projects", nargs="+", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--backend", choices=["jev", "none"], default="none")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--card-chars", type=int, default=1500)
    ap.add_argument("--task-chars", type=int, default=2500)
    ap.add_argument("--max-ticks", type=int, default=0)
    ap.add_argument("--hide-scores", action="store_true",
                    help="ablation: strip every search score from state and criteria")
    ap.add_argument("--bookkeeping", action="store_true",
                    help="children, jobs per line and knobs changed vs parent, explicit in state and cards")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    backend = Jev() if args.backend == "jev" else NoBackend()
    sums = []
    for p in args.projects:
        sys.stderr.write(f"{p}\n")
        res = replay_project(p, backend, args)
        (args.out / f"replay-{res['campaign']}.json").write_text(json.dumps(res, indent=1) + "\n")
        s = summarise(res)
        (args.out / f"summary-{res['campaign']}.json").write_text(json.dumps(s, indent=1) + "\n")
        sums.append(s)
    write_md(args.out, sums, args)
    print((args.out / "REPLAY.md").read_text())


if __name__ == "__main__":
    main()
