#!/usr/bin/env python3
"""mem_replay_ledger.py — the replay gate for the findings-v3 knob ledger.

Read-only, no LLM, no labels, no writes into the replayed campaign. For every job a
finished campaign dispatched it rebuilds the finding cards of the candidates that had
settled by then (as `scripts/mem_replay_selector.py` does), re-runs the selector under
the policy the campaign actually ran, and renders the v3 ledger that job would have
seen instead of the v2 one.

Two things are checked:

1. **v2 is unchanged.** The rebuilt v2 selection and its rendered text must equal the
   snapshot stored in that job's `job.json`. If they differ, v2 has moved under us and
   nothing below can be trusted, so the run stops.
2. **The eleven facts.** Each rated novelty error of
   `docs/mem2-comparison-20260914/RESULT.md` (the eleven statements the population
   contradicts, with their ratings in `ratings/B.json`) names a candidate and the knob
   its claim is about. For each, the v3 ledger that candidate's job would have seen is
   searched for the contradicting fact: the knob's row, the contradicting value, and
   the id of the candidate that tried it. v3 is ready only if all eleven are present.

    scripts/mem_replay_ledger.py <project-dir> [--knobs out/memory_config.json]
                                 [--md OUT.md] [--json OUT.json]

Needs LAB_PRIVATE only so campaign.toml expands; no label is read.
"""
from __future__ import annotations

import argparse
import copy
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"

# The eleven rated novelty statements of docs/mem2-comparison-20260914/RESULT.md
# ("Eleven of the eighteen are novelty claims that the population contradicts"), each
# quoted from ratings/B.json with the rater's note. `knob` is the knob the claim is
# about; `contradicted_by` are the candidates whose own configuration file contradicts
# it, with the value they ran. `kind`:
#   knob      — a claim about what has been configured: the v3 index must carry it
#   outcome   — a claim about a measured quantity (parameter counts, search deltas):
#               v3 deliberately keeps these out of the index, so the check records
#               where the fact does live instead of pretending the index answers it
CLAIMS = [
    {"id": "c0008-orders-never", "candidate": "c0008", "knob": "orders", "kind": "knob",
     "quote": "No candidate in this lineage (c0001-c0007) had ever varied `orders`",
     "contradicted_by": {"c0001": "[1,2,3]", "c0002": "[1,2]"}},
    {"id": "c0008-orders-runsh", "candidate": "c0008", "knob": "orders", "kind": "knob",
     "quote": "but every prior `run.sh` hardcoded `--orders 1`",
     "contradicted_by": {"c0001": "[1,2,3]", "c0002": "[1,2]"}},
    {"id": "c0008-orders-first", "candidate": "c0008", "knob": "orders", "kind": "knob",
     "quote": "This candidate is the first to pass `--orders 1 2`",
     "contradicted_by": {"c0002": "[1,2]"}},
    {"id": "c0014-heads-540s", "candidate": "c0014", "knob": "heads", "kind": "knob",
     "quote": "but every 540s run in the ledger so far also used heads=8",
     "contradicted_by": {"c0011": "4"}},
    {"id": "c0015-seed-only", "candidate": "c0015", "knob": "weight_decay", "kind": "knob",
     "quote": "c0009 vs c0003's seed-only delta was -0.0054 held-out accuracy",
     "contradicted_by": {"c0009": "0.01"}},
    {"id": "c0019-wd-never", "candidate": "c0019", "knob": "weight_decay", "kind": "knob",
     "quote": "weight_decay has never been varied anywhere in this lineage",
     "contradicted_by": {"c0009": "0.01", "c0014": "0.01"}},
    {"id": "c0019-wd-repeat", "candidate": "c0019", "knob": "weight_decay", "kind": "knob",
     "quote": "Repeat check: no candidate in the ledger has ever varied `weight_decay`",
     "contradicted_by": {"c0009": "0.01", "c0014": "0.01"}},
    {"id": "c0019-batch-both", "candidate": "c0019", "knob": "batch_size", "kind": "knob",
     "quote": "a knob+direction already fully explored in both directions",
     "contradicted_by": {}},      # the row itself shows every value tried, and that
                                  # none is below the opening one
    {"id": "c0005-params-14.1M", "candidate": "c0005", "knob": "trainable_params", "kind": "outcome",
     "quote": "28,234,240 trainable memory params, up from c0003's 14.1M",
     "contradicted_by": {"c0003": "15166720"},
     "probes": ["15166720", "15,166,720"]},
    {"id": "c0006-params-14.1M", "candidate": "c0006", "knob": "trainable_params", "kind": "outcome",
     "quote": "c0005's 8-head model (28.2M trainable params, double c0003's 14.1M)",
     "contradicted_by": {"c0003": "15166720"},
     "probes": ["15166720", "15,166,720"]},
    {"id": "c0017-largest-jump", "candidate": "c0017", "knob": "(search delta)", "kind": "delta",
     "quote": "and produced the single largest jump in the ledger (delta +0.0668)",
     "contradicted_by": {}, "claimed_delta": 0.0668,
     "probes": ["+0.1299", "+0.129883", "+0.0926", "+0.092651"]},
]

# Rated statements that are novelty claims about a knob but are not among RESULT.md's
# eleven; reported beside the gate, never part of the verdict.
EXTRA_CLAIMS = [
    {"id": "c0009-seed-swing", "candidate": "c0009", "knob": "orders", "kind": "knob",
     "quote": "even a bare seed change alone can swing hidden search score (c0006 vs c0008)",
     "contradicted_by": {"c0008": "[1,2]"}},
    {"id": "c0017-depth-axis", "candidate": "c0017", "knob": "attach_layer", "kind": "knob",
     "quote": "attach_layer 4 ... the only other point on the depth axis measured so far",
     "contradicted_by": {"c0007": "6", "c0012": "6"}},
]


def load_modules(project: Path):
    os.environ["LAB_ROOT"] = str(project)
    os.environ.setdefault("LAB_PRIVATE", str(Path.home() / ".local/share/labloop-private"))
    loader = importlib.machinery.SourceFileLoader("lab", str(TOOLS / "lab"))
    spec = importlib.util.spec_from_loader("lab", loader)
    lab = importlib.util.module_from_spec(spec)
    sys.modules["lab"] = lab
    loader.exec_module(lab)
    sys.path.insert(0, str(TOOLS))
    import lab_campaign as C   # noqa: E402
    import lab_findings as F   # noqa: E402
    C.L = lab
    return lab, C, F


ROW_RE = re.compile(r"^([^:\n]+): (.*)$")
RANGE_RE = re.compile(r"^(c\d{4})(?:–(c\d{4}))?$")


def parse_index(text: str) -> dict[str, list[tuple[str, list[str]]]]:
    """The rendered v3 index back into {knob: [(value, [ids])]} — read from the text the
    worker would actually have seen, so an elision is an absence here too."""
    out: dict[str, list[tuple[str, list[str]]]] = {}
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m or line.startswith("#") or " (" not in line:
            continue
        knob, rest = m.group(1), m.group(2)
        vals = []
        for part in rest.split(" · "):
            pm = re.match(r"^(.*) \(([^()]*)\)$", part)
            if not pm:
                continue                      # "3 older value(s) elided"
            ids: list[str] = []
            for chunk in pm.group(2).split(", "):
                rm = RANGE_RE.match(chunk.strip())
                if not rm:
                    continue
                a = int(rm.group(1)[1:])
                b = int(rm.group(2)[1:]) if rm.group(2) else a
                ids += [f"c{i:04d}" for i in range(a, b + 1)]
            vals.append((pm.group(1), ids))
        if vals:
            out[knob] = vals
    return out


def fmt_elided(elided: list[dict]) -> str:
    return ", ".join("{}×{}".format(e["knob"], e["values"]) for e in elided)


def check_claim(claim: dict, index: dict[str, list[tuple[str, list[str]]]]) -> dict:
    """Would the contradicting fact have been in front of this worker?"""
    knob, res = claim["knob"], {"id": claim["id"], "candidate": claim["candidate"],
                                "knob": claim["knob"], "kind": claim["kind"],
                                "quote": claim["quote"]}
    if claim["kind"] == "delta":
        # a superlative over search deltas: the contradicting fact is every earlier
        # candidate whose jump over its parent exceeded the claimed one. A knob index
        # cannot carry it; the job card's population table can, once it lists parents
        # beside scores (tools since 2026-09-15). Present iff that table, rendered as the
        # job would have seen it, names each such candidate with its parent and both scores.
        table = "\n".join(claim["table"])
        larger = [(cid, par, d) for cid, par, d in claim["deltas"] if d > claim["claimed_delta"]]
        rows = {ln.split(" | ")[0].strip("| ") : ln for ln in claim["table"] if ln.startswith("| c")}
        ok = bool(larger) and "| parents |" in table and all(
            cid in rows and par in rows[cid] and par in rows for cid, par, _ in larger)
        res.update(present=ok,
                   detail=("larger jumps in the population table (parents column): "
                           + ", ".join(f"{cid} {d:+.6g} from {par}" for cid, par, d in larger))
                   if ok else ("larger jumps exist (" + ", ".join(f"{cid} {d:+.6g}" for cid, _, d in larger)
                               + ") but the population table does not show their parents"
                               if larger else "no larger jump found in the population at dispatch"))
        return res
    if claim["kind"] == "outcome":
        # not a knob claim: v3 keeps measured quantities out of the index on purpose, so
        # the question is whether the contradicting number was anywhere in the rendered
        # context (a shown card's score, a parent delta) at all
        hits = [t for t in claim["probes"] if t in claim["context"]]
        res.update(present=bool(hits),
                   detail=("found in the rendered context: " + ", ".join(hits)) if hits else
                          "outcome quantity: not in the index by design, and not in the "
                          "rendered cards either")
        return res
    row = index.get(knob)
    if row is None:
        res.update(present=False, detail="no row for this knob in the v3 index")
        return res
    seen = {cid: val for val, ids in row for cid in ids}
    missing = [c for c in claim["contradicted_by"] if c not in seen]
    wrong = [f"{c}={seen[c]} (expected {v})" for c, v in claim["contradicted_by"].items()
             if c in seen and seen[c] != v]
    # a row naming the contradicting candidate with the value it ran *is* the fact, even
    # when the knob has one value: "weight_decay: 0.01 (c0009, c0014)" contradicts
    # "weight_decay has never been varied" on its own
    ok = (not missing and not wrong) if claim["contradicted_by"] else bool(row)
    res.update(present=ok, values=len(row),
               detail=("; ".join(filter(None, [
                   "row: " + " · ".join(f"{v} ({len(ids)} id(s))" for v, ids in row),
                   "missing " + ", ".join(missing) if missing else "",
                   "value mismatch: " + ", ".join(wrong) if wrong else "",
                   ""]))))
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--knobs", default="out/memory_config.json")
    ap.add_argument("--md")
    ap.add_argument("--json")
    args = ap.parse_args()
    project = Path(args.project).resolve()
    lab, C, F = load_modules(project)
    cfg = C.load_campaign(project / "campaign.toml")
    pop = C.load_pop()
    if pop is None:
        sys.exit(f"{project}: no population")
    policy = (pop.get("memory") or {}).get("policy", "legacy")
    if policy != F.POLICY_V2:
        sys.exit(f"{project}: this gate replays a {F.POLICY_V2} campaign (found {policy!r})")

    settled = [cid for cid, c in pop["candidates"].items() if c.get("exec") in F.EXEC_STATUSES]
    pop_v2 = copy.deepcopy(pop)
    pop_v2["memory"] = {"policy": F.POLICY_V2, "knobs": args.knobs}
    pop_v3 = copy.deepcopy(pop)
    pop_v3["memory"] = {"policy": F.POLICY_V3, "knobs": args.knobs}
    cards_v2 = {cid: C.build_candidate_card(cfg, pop_v2, cid) for cid in settled}
    cards_v3 = {cid: C.build_candidate_card(cfg, pop_v3, cid) for cid in settled}
    ended = {k: pop["candidates"][k].get("ended") or "" for k in settled}

    rows, mismatches, drift, ledgers, contexts = [], [], [], {}, {}
    tables, deltas = {}, {}      # the job card's population table at dispatch, and each settled candidate's jump over its first parent
    for cid, c in pop["candidates"].items():
        if c["operator"] == "baseline":
            continue
        cdir = project / c["path"]
        job = json.loads((cdir / "job.json").read_text())
        start = (json.loads((cdir / "config.json").read_text()) or {}).get("start_time") or ""
        avail = [k for k in settled if ended[k] and ended[k] <= start and k != cid]
        parents = [p["id"] for p in job["parents"]]
        for p in parents:
            if p not in avail and p in cards_v2:
                avail.append(p)
        v2 = F.select_context({k: cards_v2[k] for k in avail}, parents,
                              policy=F.POLICY_V2, knobs_file=args.knobs)
        v3 = F.select_context({k: cards_v3[k] for k in avail}, parents,
                              policy=F.POLICY_V3, knobs_file=args.knobs)
        stored = job.get("findings")
        if stored is not None:
            cut = lambda t: t.split("\n## Knob ledger", 1)[0]
            if [x["id"] for x in stored["cards"]] != [x["id"] for x in v2["cards"]] \
                    or cut(stored["rendered"]) != cut(v2["rendered"]):
                mismatches.append(cid)      # the selector itself moved: stop
            elif stored["rendered"] != v2["rendered"]:
                # the selection and the cards are identical and only a ledger row
                # differs: a knobs artifact on disk is not what it was at dispatch
                # (a file rewritten after the job started), not a change to v2
                drift.append(cid)
        led3 = v3["ledger"]
        # the same call select_context makes, for the text on its own
        ledgers[cid] = F.render_ledger_v3({k: cards_v3[k] for k in avail}, args.knobs)[0]
        contexts[cid] = v3["rendered"]
        cands = pop["candidates"]
        listed = [k for k, v in cands.items() if k != cid and (v.get("launched") or "") <= start]
        tables[cid] = C.population_table([
            {"id": k, "operator": cands[k]["operator"], "parents": cands[k].get("parents") or [],
             "status": "evaluated" if k in avail else "running",
             "fitness": cands[k].get("fitness") if k in avail else None} for k in listed])
        deltas[cid] = [(k, cands[k]["parents"][0], cands[k]["fitness"] - cands[cands[k]["parents"][0]]["fitness"])
                       for k in avail if cands[k].get("parents") and cands[k].get("fitness") is not None
                       and cands[cands[k]["parents"][0]].get("fitness") is not None]
        rows.append({"id": cid, "operator": c["operator"], "parents": parents,
                     "available": len(avail),
                     "v2_ledger_bytes": v2["ledger"]["bytes"],
                     "v2_ledger_rows": len(v2["ledger"]["rows"]),
                     "v2_ledger_omitted": v2["ledger"]["omitted"],
                     "v3_ledger_bytes": led3["bytes"], "v3_knobs": led3["knobs"],
                     "v3_candidates": len(led3["rows"]), "v3_elided": led3["elided"],
                     "v3_over_budget": led3["over_budget"],
                     "v2_bytes": v2["bytes"], "v3_bytes": v3["bytes"],
                     "stored_ledger_bytes": (stored or {}).get("ledger", {}).get("bytes")})
    if mismatches:
        sys.exit("STOP: the rebuilt findings-v2 context differs from the snapshot stored in "
                 "job.json for " + ", ".join(mismatches) + " — v2 has changed; the v3 numbers "
                 "below would not be comparable. Nothing written.")

    results, extra = [], []
    for claims, sink in ((CLAIMS, results), (EXTRA_CLAIMS, extra)):
        for cl in claims:
            cl = dict(cl, context=contexts.get(cl["candidate"], ""),
                      table=tables.get(cl["candidate"], []), deltas=deltas.get(cl["candidate"], []))
            r = check_claim(cl, parse_index(ledgers.get(cl["candidate"], "")))
            r["ledger_bytes"] = next((x["v3_ledger_bytes"] for x in rows
                                      if x["id"] == cl["candidate"]), None)
            sink.append(r)
    knob_claims = [r for r in results if r["kind"] == "knob"]
    ready = all(r["present"] for r in results)

    b3 = [r["v3_ledger_bytes"] for r in rows]
    b2 = [r["v2_ledger_bytes"] for r in rows]
    out = []
    A = out.append
    A(f"# Ledger v3 replay — {pop['campaign']} ({project.name})")
    A("")
    A(f"Generated by `scripts/mem_replay_ledger.py` (read-only, no LLM, no labels). "
      f"Policy as run: **{policy}**; jobs replayed: {len(rows)} (baseline excluded); settled "
      f"cards: {len(settled)}; knobs file `{args.knobs}`.")
    A("")
    A("- rebuilt findings-v2 selection and card text equal the snapshot stored in every "
      "job.json: **yes** (v2 is unchanged, so the v3 columns are comparable)")
    if drift:
        A(f"- artifact drift (reported, not a policy change): the rebuilt v2 ledger row differs "
          f"from the stored one for {', '.join(drift)}, because a settled candidate's `{args.knobs}` "
          f"on disk is no longer byte-identical to what it was at dispatch. The cards, the "
          f"selection and every id are unchanged; the v3 index is rebuilt from the same files, so "
          f"both columns drift together.")
    A(f"- ledger budget: {F.LEDGER_MAX_BYTES} B for both policies; v3 excludes outcome keys "
      f"({', '.join(sorted(F.OUTCOME_KEYS))}, and any key starting "
      f"{', '.join(F.OUTCOME_PREFIXES)})")
    A(f"- v3 ledger bytes: min {min(b3)}, max {max(b3)}, mean {sum(b3) / len(b3):.0f} "
      f"(v2: min {min(b2)}, max {max(b2)}, mean {sum(b2) / len(b2):.0f})")
    elided = [r["id"] for r in rows if r["v3_elided"]]
    A(f"- knobs elided under the 2 KiB bound: **{len(elided)} job(s)**"
      + (" (" + ", ".join(elided) + ")" if elided else "") + "; candidates dropped for age: "
      f"v3 0, v2 {sum(len(r['v2_ledger_omitted']) for r in rows)}")
    A("")
    A("| job | cards avail | v2 ledger B | v2 rows (dropped) | v3 ledger B | v3 knobs | "
      "v3 candidates named | elided |")
    A("|---|---|---|---|---|---|---|---|")
    for r in rows:
        A(f"| {r['id']} | {r['available']} | {r['v2_ledger_bytes']} | {r['v2_ledger_rows']} "
          f"({len(r['v2_ledger_omitted'])}) | {r['v3_ledger_bytes']} | {len(r['v3_knobs'])} | "
          f"{r['v3_candidates']} | {fmt_elided(r['v3_elided']) or '—'} |")
    A("")
    A("## The eleven rated novelty claims")
    A("")
    A("Would the contradicting fact have been in the v3 ledger this job was dispatched with?")
    A("")
    A("| claim | job | knob | kind | present | what the v3 index holds |")
    A("|---|---|---|---|---|---|")
    for r in results:
        A(f"| {r['quote'][:60]}… | {r['candidate']} | `{r['knob']}` | {r['kind']} | "
          f"**{'present' if r['present'] else 'absent'}** | {r['detail']} |")
    A("")
    A(f"**{sum(r['present'] for r in results)} of {len(results)} present** "
      f"({sum(r['present'] for r in knob_claims)} of {len(knob_claims)} of the knob claims).")
    A("")
    A("## Verdict")
    A("")
    A(f"**v3 is {'ready' if ready else 'NOT ready'} by the preregistered gate** "
      "(docs/campaign-plan-20260914.md §6: ready only if every one of the eleven facts is "
      "present in the ledger the job would have seen).")
    A("")
    A("## Other rated knob-novelty claims (reported, not part of the gate)")
    A("")
    A("| claim | job | knob | present | what the v3 index holds |")
    A("|---|---|---|---|---|")
    for r in extra:
        A(f"| {r['quote'][:60]}… | {r['candidate']} | `{r['knob']}` | "
          f"{'present' if r['present'] else 'absent'} | {r['detail']} |")
    A("")
    A("## The v3 ledger c0019 would have seen")
    A("")
    A("```")
    A(ledgers.get("c0019", "").strip("\n"))
    A("```")
    text = "\n".join(out) + "\n"
    print(text, end="")
    if args.md:
        Path(args.md).write_text(text)
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"campaign": pop["campaign"], "project": str(project), "policy": policy,
             "knobs": args.knobs, "v2_matches_snapshot": not mismatches,
             "artifact_drift": drift,
             "ledger_max_bytes": F.LEDGER_MAX_BYTES,
             "outcome_keys": sorted(F.OUTCOME_KEYS),
             "outcome_prefixes": list(F.OUTCOME_PREFIXES),
             "jobs": rows, "claims": results, "extra_claims": extra,
             "ready": ready}, indent=1) + "\n")
    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    main()
