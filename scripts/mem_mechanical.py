#!/usr/bin/env python3
"""mem_mechanical.py — the mechanical secondary measures of a legacy-vs-findings comparison.

Everything PREREG.md lists under "Secondary measures" that a script can compute:
settlement counts, GPU-hours and wall clock, candidates per GPU-hour, served models,
deferrals, finding-card coverage (findings arm), search progress after 8 and 20
settled candidates, the frozen candidate's final-split score as the lab recorded it
(read once by `lab run`; this script never reads labels), and prompt cost from
`scripts/pilot_prompt_size.py --json` outputs. The primary endpoint (statement
accuracy) is not here; it comes from the blinded rating (`scripts/mem_rating_pack.py`).

    scripts/mem_mechanical.py --findings DIR --legacy DIR \\
        [--pilot-findings JSON --pilot-legacy JSON] [--prompt-bound 2.0] [--md OUT.md]

Read-only on both arms.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
from datetime import datetime
from pathlib import Path


def iso(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def arm_facts(d: Path) -> dict:
    pop = json.loads((d / "population.json").read_text())
    cands = pop["candidates"]
    ordered = [cands[k] for k in sorted(cands)]
    execs = collections.Counter(c.get("exec") for c in ordered)
    served = collections.Counter(tuple((c.get("session") or {}).get("models") or []) for c in ordered
                                 if c.get("operator") != "baseline")
    turns = [(c.get("session") or {}).get("turns") for c in ordered if (c.get("session") or {}).get("turns")]
    gpu_h = (pop.get("gpu_seconds") or 0) / 3600
    started, finished = iso(pop.get("started")), iso(pop.get("finished"))
    wall_h = (finished - started).total_seconds() / 3600 if started and finished else None
    settled = [c for c in ordered if c.get("exec") in ("completed", "invalid", "failed", "killed")]
    nonbase_settled = [c for c in settled if c.get("operator") != "baseline"]
    def best_after(n: int) -> float | None:
        vals = [c.get("fitness") for c in ordered[:n] if isinstance(c.get("fitness"), (int, float))]
        return max(vals) if vals else None
    final = pop.get("final") or {}
    fin_score = final.get("score") if isinstance(final, dict) else None
    return {
        "campaign": pop.get("campaign"), "memory": (pop.get("memory") or {}).get("mode") if isinstance(pop.get("memory"), dict) else pop.get("memory"),
        "stop_reason": pop.get("stop_reason"), "claim": pop.get("claim"),
        "settled": len(settled), "settled_non_baseline": len(nonbase_settled),
        "exec": dict(execs), "defers": sum(c.get("defers") or 0 for c in ordered),
        "gpu_hours": round(gpu_h, 3), "wall_hours": round(wall_h, 3) if wall_h else None,
        "valid_per_gpu_hour": round(execs.get("completed", 0) / gpu_h, 2) if gpu_h else None,
        "served_models": {"|".join(k): v for k, v in served.items()},
        "turns_median": statistics.median(turns) if turns else None, "turns_max": max(turns) if turns else None,
        "best_search_after_8": best_after(8), "best_search_after_20": best_after(20),
        "frozen": pop.get("best"), "final_score": fin_score,
        "_pop": pop,
    }


def coverage(d: Path, pop: dict) -> dict:
    """PREREG: every job's context holds its direct parent(s); once >= 4 cards exist,
    >= 2 cards from outside its lineage. Reported twice: with the baseline card
    counted as outside the lineage, and without (the rule does not say)."""
    parents = {k: v.get("parents") or [] for k, v in pop["candidates"].items()}
    def closure(cid):
        seen, st = set(), list(parents.get(cid, []))
        while st:
            x = st.pop()
            if x not in seen:
                seen.add(x)
                st += parents.get(x, [])
        return seen
    rows, viol_incl, viol_excl, parent_viol = [], [], [], []
    for cid in sorted(pop["candidates"]):
        jp = d / "candidates" / cid / "job.json"
        if not jp.exists():
            continue
        j = json.loads(jp.read_text())
        if j.get("operator") == "baseline" or not j.get("findings"):
            continue
        ids = [c["id"] for c in j["findings"].get("cards", [])]
        lin = closure(cid)
        outside_incl = [i for i in ids if i not in lin]
        outside_excl = [i for i in outside_incl if pop["candidates"][i].get("operator") != "baseline"]
        n_exist = int(cid[1:])          # sequential campaign: cards that existed at dispatch
        ok_parents = all(p in ids for p in parents[cid])
        need = n_exist >= 4
        if not ok_parents:
            parent_viol.append(cid)
        if need and len(outside_incl) < 2:
            viol_incl.append(cid)
        if need and len(outside_excl) < 2:
            viol_excl.append(cid)
        rows.append({"job": cid, "parents": parents[cid], "cards": ids,
                     "outside_lineage": len(outside_excl), "outside_incl_baseline": len(outside_incl)})
    return {"jobs": len(rows), "parent_violations": parent_viol,
            "cross_branch_violations_baseline_excluded": viol_excl,
            "cross_branch_violations_baseline_counted": viol_incl, "rows": rows}


def prompt_cost(p: Path | None) -> dict | None:
    if not p:
        return None
    d = json.loads(p.read_text())
    toks = [r["as_dispatched"]["tokens"] for r in d["rows"]]
    return {"tokenizer": d.get("tokenizer"), "jobs": len(toks), "mean": round(statistics.mean(toks), 1),
            "median": statistics.median(toks), "max": max(toks), "total": sum(toks)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--findings", required=True, type=Path)
    ap.add_argument("--legacy", required=True, type=Path)
    ap.add_argument("--pilot-findings", type=Path)
    ap.add_argument("--pilot-legacy", type=Path)
    ap.add_argument("--prompt-bound", type=float, default=2.0)
    ap.add_argument("--md", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    arms = {"findings": arm_facts(args.findings), "legacy": arm_facts(args.legacy)}
    cov = coverage(args.findings, arms["findings"].pop("_pop"))
    arms["legacy"].pop("_pop")
    pc = {"findings": prompt_cost(args.pilot_findings), "legacy": prompt_cost(args.pilot_legacy)}
    ratio = (pc["findings"]["mean"] / pc["legacy"]["mean"]) if pc["findings"] and pc["legacy"] else None
    same_models = set(arms["findings"]["served_models"]) == set(arms["legacy"]["served_models"])
    pending = []
    for name, a in arms.items():
        if a["settled_non_baseline"] < 10:
            pending.append(f"{name}: fewer than 10 settled non-baseline candidates")
        if a["stop_reason"] and "max_candidates" not in str(a["stop_reason"]):
            pending.append(f"{name}: ended early ({a['stop_reason']})")
    if not same_models:
        pending.append("served models differ between the arms")
    out = {"arms": arms, "coverage": cov, "prompt_cost": pc,
           "prompt_ratio_findings_over_legacy": round(ratio, 3) if ratio else None,
           "prompt_bound": args.prompt_bound,
           "prompt_within_bound": (ratio <= args.prompt_bound) if ratio else None,
           "same_served_models": same_models, "mechanical_pending_reasons": pending}
    if args.json:
        args.json.write_text(json.dumps(out, indent=1) + "\n")

    f, l = arms["findings"], arms["legacy"]
    lines = ["| measure | findings arm | legacy arm |", "|---|---|---|"]
    def row(label, key, fmt=lambda v: v):
        lines.append(f"| {label} | {fmt(f.get(key))} | {fmt(l.get(key))} |")
    row("campaign", "campaign")
    row("stop reason", "stop_reason")
    row("settled (non-baseline)", "settled_non_baseline")
    row("exec counts", "exec", lambda v: ", ".join(f"{k} {n}" for k, n in (v or {}).items()))
    row("deferred jobs", "defers")
    row("GPU-hours", "gpu_hours")
    row("wall clock (h)", "wall_hours")
    row("valid candidates per GPU-hour", "valid_per_gpu_hour")
    row("served models (sessions)", "served_models", lambda v: "; ".join(f"{k}: {n}" for k, n in (v or {}).items()))
    row("turns median / max", "turns_median", lambda v: v)
    lines[-1] = f"| turns median / max | {f['turns_median']} / {f['turns_max']} | {l['turns_median']} / {l['turns_max']} |"
    row("best search fitness after 8 settled", "best_search_after_8")
    row("best search fitness after 20 settled", "best_search_after_20")
    row("frozen candidate", "frozen")
    row("final-split score (lab's one read)", "final_score")
    row("task claim vs fixed 0.50", "claim")
    if pc["findings"] and pc["legacy"]:
        lines.append(f"| job-card tokens, mean (median, max) | {pc['findings']['mean']} ({pc['findings']['median']}, {pc['findings']['max']}) "
                     f"| {pc['legacy']['mean']} ({pc['legacy']['median']}, {pc['legacy']['max']}) |")
        lines.append(f"| prompt ratio findings / legacy | {ratio:.2f} (bound ≤ {args.prompt_bound}: "
                     f"{'within' if ratio <= args.prompt_bound else 'EXCEEDED'}) | |")
    lines += ["", f"Coverage (findings arm, {cov['jobs']} jobs with cards): parent violations "
              f"{len(cov['parent_violations'])} {cov['parent_violations'] or ''}; jobs with fewer than two "
              f"out-of-lineage cards once ≥ 4 existed: {len(cov['cross_branch_violations_baseline_excluded'])} "
              f"{cov['cross_branch_violations_baseline_excluded']} (baseline card not counted), "
              f"{len(cov['cross_branch_violations_baseline_counted'])} {cov['cross_branch_violations_baseline_counted']} "
              f"(baseline counted).", "",
              "Mechanical pending reasons: " + ("; ".join(pending) if pending else "none") + "."]
    text = "\n".join(lines) + "\n"
    print(text)
    if args.md:
        args.md.write_text(text)


if __name__ == "__main__":
    main()
