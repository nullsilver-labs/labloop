"""headroom_replay.py: is a per-candidate "is this line exhausted?" judgment predictive?

The Choice replay (orchestrator_replay.py) showed a decision model asked "which parent"
ranks by apparent quality. This replay asks a different question, one per eligible
candidate at every recorded tick, with a hindsight label the recorded history provides:

    Noul   "is candidate c's line exhausted?"           -> p(exhausted) in [0, 1]
    Score  "how much headroom does c's line have?"      -> ordered levels, low = exhausted

    label(t, c) = 1 (exhausted) if c received at least one later descendant and none
                  of them beat c's search score; 0 (open) if a later descendant beat it;
                  unlabeled if c never received a later descendant (unfed lines cannot
                  show anything either way and are not counted against anyone).

Every judgment is scored against that label by the area under the ROC curve, pooled over
(tick, candidate) pairs and, to undo the correlation of one candidate across ticks, once
per candidate at the first tick it was eligible. Beside the model: a mechanical rule from
the same bookkeeping, and two trivial baselines (children so far, the score itself). One
request per tick carries every question over one shared state (chunked if large).

    scripts/headroom_replay.py PROJECT [PROJECT ...] --out DIR [--backend jev|none]
        [--card-chars 1200] [--task-chars 2000] [--chunk 24]

Read-only on the projects; never reads labels, a final score or REPORT.md. Needs
TYPESAFE_API_KEY in the environment or ./.env; the key is never written anywhere.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator_replay import (Jev, load_cards, load_rows, campaign_id, card_text, knob_index,  # noqa: E402
                                 ticks_of, eligible_at, bookkeeping, book_text, ts)

DEFINITION = (
    "A line is EXHAUSTED when the next job built directly on this candidate is unlikely to "
    "beat this candidate's own search score: its recent changes were knob values without gain, "
    "the knobs it varies are already covered in the knob index, its children scored below it, "
    "or its card reports a ceiling the change cannot move. A line is OPEN when its card names "
    "an untried idea or a mechanism with headroom, its own change gained over its parent, or "
    "no job has been built on it yet and its idea is unlike the rest of the population.")
LEVELS = ["exhausted: the next job on it will not beat its score",
          "little headroom: a small gain is possible, a repeat more likely",
          "some headroom: an untried change with a plausible gain exists",
          "much headroom: the card names a mechanism nobody has followed up"]


def questions_for(ids: list[str]) -> dict:
    q = {}
    for c in ids:
        q[f"noul:{c}"] = {"type": "noul",
                          "instructions": f"Is candidate {c}'s line exhausted, as state.definition defines it? "
                                          f"Judge {c} from state.cards['{c}'], its bookkeeping row in "
                                          f"state.population and state.knob_index.",
                          "criteria": {"true": "exhausted: the next job built on it is unlikely to beat its score",
                                       "false": "open: a next job built on it can plausibly beat its score"}}
        q[f"score:{c}"] = {"type": "score",
                           "instructions": f"How much headroom does candidate {c}'s line have (state.definition, "
                                           f"state.cards['{c}'], its bookkeeping row, state.knob_index)?",
                           "criteria": LEVELS}
    return q


class JevBatch(Jev):
    def ask(self, questions: dict, state: dict) -> dict:
        body = {"state": state, "model": self.MODEL, "questions": questions}
        data = json.dumps(body).encode()
        req = urllib.request.Request(self.BASE + self.PATH, data=data, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.key}"})
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": f"http {e.code}: {e.read().decode()[:300]}", "latency_s": time.monotonic() - t0,
                    "bytes": len(data), "answers": {}}
        except Exception as e:  # noqa: BLE001
            return {"error": f"{type(e).__name__}: {e}", "latency_s": time.monotonic() - t0,
                    "bytes": len(data), "answers": {}}
        return {"answers": raw.get("answers") or {}, "model": raw.get("model"), "usage": raw.get("usage"),
                "latency_s": time.monotonic() - t0, "bytes": len(data)}


class NoBatch:
    name = "none"

    def ask(self, questions, state):  # noqa: ANN001
        return {"answers": {}, "latency_s": 0.0, "bytes": len(json.dumps({"state": state, "questions": questions}))}


def descendants_after(rows: list[dict], c: str, t0: datetime) -> list[dict]:
    """Rows launched at or after t0 whose ancestry includes c."""
    by = {r["id"]: r for r in rows}
    out = []
    for r in rows:
        if not r.get("launched") or ts(r["launched"]) < t0 or r.get("exec") != "completed" or r.get("fitness") is None:
            continue
        seen, stack = set(), list(r["parents"] or [])
        hit = False
        while stack:
            x = stack.pop()
            if x == c:
                hit = True
                break
            if x in seen or x not in by:
                continue
            seen.add(x)
            stack.extend(by[x]["parents"] or [])
        if hit:
            out.append(r)
    return out


def rule_score(r: dict, elig_by: dict[str, dict], book: dict) -> float:
    """A mechanical p(exhausted) from the same bookkeeping the model sees."""
    kids = [x for x in elig_by.values() if r["id"] in (x["parents"] or [])]
    beat_by_child = any(x["fitness"] > r["fitness"] for x in kids)
    if beat_by_child:
        return 0.1
    parent = elig_by.get((r["parents"] or [None])[0])
    gained = parent is None or r["fitness"] > parent["fitness"]
    p = 0.0
    if kids:
        p += 0.5
    if len(kids) >= 2:
        p += 0.25
    if not gained:
        p += 0.25
    return p


def auc(pairs: list[tuple[float, int]]) -> float | None:
    pos = [s for s, y in pairs if y == 1]
    neg = [s for s, y in pairs if y == 0]
    if not pos or not neg:
        return None
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 3)


def replay_project(project: Path, backend, args) -> dict:
    rows = load_rows(project)
    cards = load_cards(project, rows)
    task = (project / "task.md").read_text()[: args.task_chars]
    records = []
    for tick in ticks_of(rows):
        elig = eligible_at(rows, tick)
        if len(elig) < 2:
            continue
        t0 = ts(tick["launched"])
        book = bookkeeping(elig, cards)
        elig_by = {r["id"]: r for r in elig}
        table = [{"id": r["id"], "operator": r["operator"], "parents": r["parents"],
                  "search_score": round(r["fitness"], 4), **book[r["id"]]} for r in elig]
        state = {"task": task, "definition": DEFINITION, "population": table,
                 "knob_index": knob_index(elig, cards),
                 "cards": {r["id"]: card_text(r, cards.get(r["id"]), args.card_chars) + " " + book_text(book[r["id"]])
                           for r in elig}}
        ids = [r["id"] for r in elig]
        answers, calls, err, lat, byt, usage = {}, 0, [], [], 0, 0
        for i in range(0, len(ids), args.chunk):
            res = backend.ask(questions_for(ids[i:i + args.chunk]), state)
            calls += 1
            answers.update(res.get("answers") or {})
            lat.append(res.get("latency_s", 0.0))
            byt = max(byt, res.get("bytes", 0))
            usage += ((res.get("usage") or {}).get("input_tokens") or 0)
            if res.get("error"):
                err.append(res["error"])
        cands = []
        for r in elig:
            desc = descendants_after(rows, r["id"], t0)
            label = None if not desc else (0 if any(d["fitness"] > r["fitness"] for d in desc) else 1)
            n = (answers.get(f"noul:{r['id']}") or {})
            s = (answers.get(f"score:{r['id']}") or {})
            cands.append({"id": r["id"], "fitness": r["fitness"], "label": label, "later_descendants": len(desc),
                          "noul": n.get("noul"), "score": s.get("score"), "score_confidence": s.get("confidence"),
                          "score_probabilities": s.get("probabilities"),
                          "rule": rule_score(r, elig_by, book), "children": book[r["id"]]["children"],
                          "jobs_in_line": book[r["id"]]["jobs_in_line"]})
        records.append({"campaign": campaign_id(project), "tick": tick["id"], "launched": tick["launched"],
                        "chance_parents": tick["parents"],
                        "calls": calls, "errors": err, "latency_s": lat, "state_bytes": byt,
                        "input_tokens": usage, "model": res.get("model"), "candidates": cands})
        labeled = [c for c in cands if c["label"] is not None]
        sys.stderr.write(f"  {tick['id']}: {len(elig)} candidates, {len(labeled)} labeled "
                         f"({sum(c['label'] for c in labeled)} exhausted), {calls} call(s) {sum(lat):.1f}s {byt} B"
                         + (f" ERROR {err[0]}" if err else "") + "\n")
    return {"campaign": campaign_id(project), "project": str(project), "backend": backend.name,
            "definition": DEFINITION, "levels": LEVELS, "ticks": records}


def summarise(res: dict) -> dict:
    T = res["ticks"]
    pooled, first = [], {}
    for t in T:
        for c in t["candidates"]:
            if c["label"] is None:
                continue
            pooled.append(c)
            first.setdefault((t.get("campaign"), c["id"]), c)
    signals = {"jev_noul": lambda c: c["noul"],
               "jev_score_inverted": lambda c: (-c["score"]) if c["score"] is not None else None,
               "rule": lambda c: c["rule"],
               "children": lambda c: c["children"],
               "jobs_in_line": lambda c: c["jobs_in_line"],
               "search_score": lambda c: c["fitness"]}
    out = {"campaign": res["campaign"], "ticks": len(T), "calls": sum(t["calls"] for t in T),
           "errors": sum(len(t["errors"]) for t in T),
           "latency_per_call_median_s": round(statistics.median([x for t in T for x in t["latency_s"]]), 3) if T else None,
           "state_bytes_max": max((t["state_bytes"] for t in T), default=0),
           "input_tokens_total": sum(t["input_tokens"] for t in T),
           "labeled_pairs": len(pooled), "exhausted_pairs": sum(c["label"] for c in pooled),
           "labeled_candidates": len(first), "exhausted_candidates": sum(c["label"] for c in first.values()),
           "auc_pooled": {}, "auc_first_tick": {}, "mean_noul_by_label": {}}
    for name, f in signals.items():
        pp = [(f(c), c["label"]) for c in pooled if f(c) is not None]
        ff = [(f(c), c["label"]) for c in first.values() if f(c) is not None]
        out["auc_pooled"][name] = auc(pp)
        out["auc_first_tick"][name] = auc(ff)
    for y in (0, 1):
        v = [c["noul"] for c in pooled if c["label"] == y and c["noul"] is not None]
        out["mean_noul_by_label"][str(y)] = round(statistics.mean(v), 3) if v else None
    out["model"] = next((t["model"] for t in T if t.get("model")), None)
    return out


def write_md(out: Path, sums: list[dict], allsum: dict) -> None:
    names = ["jev_noul", "jev_score_inverted", "rule", "children", "jobs_in_line", "search_score"]
    lines = [f"# Headroom replay (Noul / Score per candidate), {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}", "",
             "AUC of each signal against the hindsight label (1 = exhausted: no later descendant beat the "
             "candidate; 0 = open). Pooled over (tick, candidate) pairs, and once per candidate at its first "
             "eligible tick. 0.5 is chance; a signal that predicts *open* rather than exhausted reads below 0.5.", "",
             "| | " + " | ".join(s["campaign"] for s in sums) + " | all three |", "|---|" + "---|" * (len(sums) + 1)]
    for k in ("ticks", "calls", "errors", "latency_per_call_median_s", "state_bytes_max", "input_tokens_total",
              "labeled_pairs", "exhausted_pairs", "labeled_candidates", "exhausted_candidates", "model"):
        lines.append(f"| {k} | " + " | ".join(str(s.get(k)) for s in sums) + f" | {allsum.get(k)} |")
    for n in names:
        lines.append(f"| AUC pooled, {n} | " + " | ".join(str(s['auc_pooled'].get(n)) for s in sums)
                     + f" | {allsum['auc_pooled'].get(n)} |")
    for n in names:
        lines.append(f"| AUC first tick, {n} | " + " | ".join(str(s['auc_first_tick'].get(n)) for s in sums)
                     + f" | {allsum['auc_first_tick'].get(n)} |")
    lines.append("| mean noul, open / exhausted | " + " | ".join(
        f"{s['mean_noul_by_label'].get('0')} / {s['mean_noul_by_label'].get('1')}" for s in sums)
        + f" | {allsum['mean_noul_by_label'].get('0')} / {allsum['mean_noul_by_label'].get('1')} |")
    (out / "HEADROOM.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("projects", nargs="+", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--backend", choices=["jev", "none"], default="none")
    ap.add_argument("--card-chars", type=int, default=1200)
    ap.add_argument("--task-chars", type=int, default=2000)
    ap.add_argument("--chunk", type=int, default=24)
    ap.add_argument("--resummarise", action="store_true",
                    help="no calls: rebuild summary.json and HEADROOM.md from the headroom-*.json already in --out")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    backend = JevBatch() if args.backend == "jev" else NoBatch()
    sums, merged = [], {"campaign": "all", "ticks": []}
    for p in args.projects:
        if args.resummarise:
            res = json.loads((args.out / f"headroom-{campaign_id(p)}.json").read_text())
            for t in res["ticks"]:
                t.setdefault("campaign", res["campaign"])
        else:
            sys.stderr.write(f"{p}\n")
            res = replay_project(p, backend, args)
            (args.out / f"headroom-{res['campaign']}.json").write_text(json.dumps(res, indent=1) + "\n")
        sums.append(summarise(res))
        merged["ticks"].extend(res["ticks"])
    allsum = summarise(merged)
    (args.out / "summary.json").write_text(json.dumps({"per_campaign": sums, "all": allsum}, indent=1) + "\n")
    write_md(args.out, sums, allsum)
    print((args.out / "HEADROOM.md").read_text())


if __name__ == "__main__":
    main()
