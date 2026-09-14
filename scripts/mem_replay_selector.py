#!/usr/bin/env python3
"""mem_replay_selector.py — what findings-v2 would have shown, on a campaign already run.

Read-only, no LLM, no labels, no writes into the project. For every job a finished (or
paused) campaign dispatched it rebuilds the finding cards of the candidates that had
settled by then, runs `select_context` twice — once under `findings-v1`, once under
`findings-v2` with the knob ledger — and reports what each job would have seen.

Under v1 the rebuilt selection is checked against the snapshot stored in that job's
`job.json`: if the two disagree, v1 has changed and nothing below can be trusted. A
legacy campaign stores no snapshot, so its rows are counterfactual on both sides (the
same construction `scripts/pilot_prompt_size.py` uses).

    scripts/mem_replay_selector.py <project-dir> [--knobs out/memory_config.json]
                                   [--pair later:earlier ...] [--json OUT]

The three measures the selector was changed for (docs/memory-comparison-20260913/
opus-review.md §2): how many jobs saw at least two cards from outside their own
lineage, how many cards were shown to nobody at all, and whether the earlier half of a
known repeated idea was visible — as a card or as a ledger row — to the job that
repeated it.

Needs LAB_PRIVATE only so campaign.toml expands; no label is read.
"""
from __future__ import annotations

import argparse
import copy
import importlib.machinery
import importlib.util
import json
import os
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"

# the repeats opus-review.md §1 found in the findings arm; overridden with --pair
DEFAULT_PAIRS = [("c0016", "c0015"), ("c0017", "c0011"), ("c0019", "c0017")]


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


def off_lineage(F, cards: dict, parents: list[str], chosen: list[str]) -> list[str]:
    """The chosen ids outside the parents' whole ancestor closure — the cards a job
    could not have read from its own lineage."""
    closure = set(parents) | {c for c, _ in F.ancestors_bfs(cards, parents)}
    return [c for c in chosen if c not in closure]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--knobs", default="out/memory_config.json",
                    help="the candidate's configuration file, relative to its dir")
    ap.add_argument("--pair", action="append", default=[], metavar="LATER:EARLIER",
                    help="a known repeated idea to check visibility for (repeatable)")
    ap.add_argument("--json", help="write the per-job figures here")
    args = ap.parse_args()
    project = Path(args.project).resolve()
    lab, C, F = load_modules(project)
    cfg = C.load_campaign(project / "campaign.toml")
    pop = C.load_pop()
    if pop is None:
        sys.exit(f"{project}: no population")
    policy = (pop.get("memory") or {}).get("policy", "legacy")
    pairs = [tuple(p.split(":", 1)) for p in args.pair] or DEFAULT_PAIRS

    settled = [cid for cid, c in pop["candidates"].items() if c.get("exec") in F.EXEC_STATUSES]
    # v1 cards: what this campaign published (or would have, when it ran legacy).
    # v2 cards: the same sources plus the candidate's own configuration file.
    pop_v1 = copy.deepcopy(pop)
    pop_v1["memory"] = {"policy": F.POLICY}
    pop_v2 = copy.deepcopy(pop)
    pop_v2["memory"] = {"policy": F.POLICY_V2, "knobs": args.knobs}
    cards_v1 = {cid: C.build_candidate_card(cfg, pop_v1, cid) for cid in settled}
    cards_v2 = {cid: C.build_candidate_card(cfg, pop_v2, cid) for cid in settled}
    with_knobs = sum(1 for c in cards_v2.values() if c["knobs"] is not None)
    ended = {k: pop["candidates"][k].get("ended") or "" for k in settled}

    rows, mismatches = [], []
    for cid, c in pop["candidates"].items():
        if c["operator"] == "baseline":
            continue
        cdir = project / c["path"]
        job = json.loads((cdir / "job.json").read_text())
        start = (json.loads((cdir / "config.json").read_text()) or {}).get("start_time") or ""
        avail = [k for k in settled if ended[k] and ended[k] <= start and k != cid]
        parents = [p["id"] for p in job["parents"]]
        for p in parents:
            if p not in avail and p in cards_v1:
                avail.append(p)        # settled in the very tick it was dispatched from
        a1 = {k: cards_v1[k] for k in avail}
        a2 = {k: cards_v2[k] for k in avail}
        row = {"id": cid, "operator": c["operator"], "parents": parents, "available": len(avail)}
        try:
            v1 = F.select_context(a1, parents)
            v2 = F.select_context(a2, parents, policy=F.POLICY_V2, knobs_file=args.knobs)
        except F.ToolingError as e:
            row["error"] = str(e)
            rows.append(row)
            continue
        ids1 = [x["id"] for x in v1["cards"]]
        ids2 = [x["id"] for x in v2["cards"]]
        stored = job.get("findings")
        if stored is not None:
            if [x["id"] for x in stored["cards"]] != ids1 or stored["rendered"] != v1["rendered"]:
                mismatches.append(cid)
        row.update({
            "v1": ids1, "v2": ids2,
            "v1_off": off_lineage(F, a1, parents, ids1),
            "v2_off": off_lineage(F, a2, parents, ids2),
            "v1_bytes": v1["bytes"], "v2_bytes": v2["bytes"],
            "ledger_bytes": v2["ledger"]["bytes"], "ledger_rows": v2["ledger"]["rows"],
            "v2_omitted": [o["id"] for o in v2["omitted"]],
            "as_dispatched": [x["id"] for x in stored["cards"]] if stored else None,
        })
        rows.append(row)

    ok = [r for r in rows if "error" not in r]
    eligible = [r for r in ok if r["available"] >= 4]
    cov1 = sum(1 for r in eligible if len(r["v1_off"]) >= 2)
    cov2 = sum(1 for r in eligible if len(r["v2_off"]) >= 2)
    seen1 = {x for r in ok for x in r["v1"]}
    seen2 = {x for r in ok for x in r["v2"]}
    led = {x for r in ok for x in r["ledger_rows"]}
    nobody1 = sorted(set(settled) - seen1)
    nobody2 = sorted(set(settled) - seen2)
    nobody2_led = sorted(set(settled) - seen2 - led)
    lbytes = [r["ledger_bytes"] for r in ok]

    print(f"# Selector replay — findings-v1 vs findings-v2 · campaign {pop['campaign']} ({project.name})")
    print()
    print(f"- memory policy as run: **{policy}**; jobs replayed: {len(rows)} (baseline excluded); "
          f"settled cards: {len(settled)}")
    print(f"- knobs file: `{args.knobs}` — present for {with_knobs} of {len(settled)} settled candidates")
    print(f"- limits: max_cards {F.MAX_CARDS}, max_bytes {F.MAX_BYTES}, "
          f"ledger_max_bytes {F.LEDGER_MAX_BYTES} (the ledger is additional to the card budget)")
    if policy == F.POLICY:
        print(f"- rebuilt v1 selection equals the snapshot stored in each job.json: "
              + ("**yes, for every job** (v1 is unchanged)" if not mismatches
                 else "**NO — differs for " + ", ".join(mismatches) + "**"))
    else:
        print("- this campaign stored no findings snapshot (legacy): both columns are counterfactual")
    print()
    print("| job | parents | cards avail | v1 cards | v2 cards | off-lineage v1 | off-lineage v2 | "
          "v1 bytes | v2 bytes (cards+ledger) | ledger bytes |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if "error" in r:
            print(f"| {r['id']} | {', '.join(r['parents']) or '—'} | {r['available']} | "
                  f"error: {r['error']} | | | | | | |")
            continue
        print(f"| {r['id']} | {', '.join(r['parents']) or '—'} | {r['available']} | "
              f"{' '.join(r['v1'])} | {' '.join(r['v2'])} | "
              f"{len(r['v1_off'])} | {len(r['v2_off'])} | {r['v1_bytes']} | {r['v2_bytes']} | "
              f"{r['ledger_bytes']} |")
    print()
    print("## Totals")
    print()
    print(f"- jobs with ≥ 4 cards available: {len(eligible)}")
    print(f"- of those, jobs seeing ≥ 2 cards from outside their lineage: "
          f"**v1 {cov1} ({cov1 / len(eligible):.0%}) → v2 {cov2} ({cov2 / len(eligible):.0%})**"
          if eligible else "- no job had ≥ 4 cards available")
    print(f"- cards shown to nobody: **v1 {len(nobody1)} → v2 {len(nobody2)}** "
          f"(v1: {', '.join(nobody1) or '—'}; v2: {', '.join(nobody2) or '—'})")
    print(f"- cards neither shown nor named in any job's knob ledger, under v2: "
          f"{len(nobody2_led)} ({', '.join(nobody2_led) or '—'})")
    if lbytes:
        print(f"- ledger size: mean {statistics.mean(lbytes):.0f} B, median {statistics.median(lbytes):.0f} B, "
              f"max {max(lbytes)} B of {F.LEDGER_MAX_BYTES}")
        print(f"- rendered memory per job: v1 mean {statistics.mean([r['v1_bytes'] for r in ok]):.0f} B, "
              f"v2 mean {statistics.mean([r['v2_bytes'] for r in ok]):.0f} B "
              f"({statistics.mean([r['v2_bytes'] for r in ok]) / statistics.mean([r['v1_bytes'] for r in ok]):.2f}×)")
    print()
    print("## Known repeated ideas — was the earlier candidate visible to the later job?")
    print()
    print("| later | earlier | card under v1 | card under v2 | ledger row under v2 |")
    print("|---|---|---|---|---|")
    pair_out = []
    for later, earlier in pairs:
        r = next((x for x in ok if x["id"] == later), None)
        if r is None:
            print(f"| {later} | {earlier} | (no such job here) | | |")
            continue
        rec = {"later": later, "earlier": earlier,
               "v1_card": earlier in r["v1"], "v2_card": earlier in r["v2"],
               "v2_ledger": earlier in r["ledger_rows"]}
        pair_out.append(rec)
        print(f"| {later} | {earlier} | {'yes' if rec['v1_card'] else 'no'} | "
              f"{'yes' if rec['v2_card'] else 'no'} | {'yes' if rec['v2_ledger'] else 'no'} |")
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"campaign": pop["campaign"], "project": str(project), "policy": policy,
             "knobs": args.knobs, "mismatches": mismatches, "coverage": {"eligible": len(eligible),
             "v1": cov1, "v2": cov2}, "shown_to_nobody": {"v1": nobody1, "v2": nobody2},
             "pairs": pair_out, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
