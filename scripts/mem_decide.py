#!/usr/bin/env python3
"""mem_decide.py — unseal a rating pack and apply the preregistered decision.

Reads OUT/SEAL.json, OUT/ratings/A.json and B.json (written by the blinded rater) and
the mechanical measures JSON (scripts/mem_mechanical.py --json), recomputes every
total from the statement lists (the rater's totals block is checked, not trusted),
and applies PREREG.md's decision rule:

  supported      fraction_bad(findings) <= 0.5 * fraction_bad(legacy), >= 40 rated M+R
                 statements in each arm, and no mechanical pending reason
  pending        fewer than 40 rated M+R in either arm, fewer than 10 settled
                 non-baseline candidates, an arm that ended early, or served models
                 that differ
  not_supported  otherwise

    scripts/mem_decide.py --pack OUT --mechanical mechanical.json [--min-rated 40] [--json RESULT.json]

Prints a markdown result. Read-only; the ratings and the seal are not modified.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

TYPES = ("M", "R", "C")
RATINGS = ("correct", "incorrect", "unsupported")


def totals(rating: dict) -> dict:
    t = {ty: {r: 0 for r in RATINGS} for ty in TYPES}
    bad_types = collections.Counter()
    for s in rating.get("statements", []):
        ty, r = s.get("type"), s.get("rating")
        if ty not in TYPES or r not in RATINGS:
            bad_types[(ty, r)] += 1
            continue
        t[ty][r] += 1
    rated_mr = sum(t[ty][r] for ty in ("M", "R") for r in RATINGS)
    bad_mr = sum(t[ty][r] for ty in ("M", "R") for r in ("incorrect", "unsupported"))
    ack = rating.get("acknowledgment", [])
    reps = rating.get("repeats", [])
    return {"by_type": t, "rated_MR": rated_mr, "bad_MR": bad_mr,
            "fraction_bad": (bad_mr / rated_mr) if rated_mr else None,
            "C_rated": sum(t["C"].values()),
            "C_bad": t["C"]["incorrect"] + t["C"]["unsupported"],
            "unrated": len(rating.get("unrated", [])),
            "candidates_with_cross_branch_ack": sum(1 for a in ack if a.get("cross_branch")),
            "repeats_unacknowledged": sum(1 for r in reps if not r.get("acknowledged")),
            "repeats_acknowledged": sum(1 for r in reps if r.get("acknowledged")),
            "malformed_statements": dict(bad_types) if bad_types else {},
            "rater_totals_agree": _agree(rating.get("totals"), t, rated_mr, bad_mr)}


def _agree(rt: dict | None, t: dict, rated_mr: int, bad_mr: int) -> bool | None:
    if not rt:
        return None
    try:
        return all(rt[ty][r] == t[ty][r] for ty in TYPES for r in RATINGS) \
            and rt.get("rated_MR") == rated_mr and rt.get("bad_MR") == bad_mr
    except (KeyError, TypeError):
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True, type=Path)
    ap.add_argument("--mechanical", required=True, type=Path)
    ap.add_argument("--min-rated", type=int, default=40)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    seal = json.loads((args.pack / "SEAL.json").read_text())
    letters = seal["assignment"]                      # {"A": "findings"|"legacy", "B": ...}
    ratings = {}
    for letter in ("A", "B"):
        p = args.pack / "ratings" / f"{letter}.json"
        if not p.exists():
            sys.exit(f"{p} missing: the rating is not finished; the comparison stays pending")
        ratings[letter] = json.loads(p.read_text())
    mech = json.loads(args.mechanical.read_text())
    per_arm = {letters[letter]: {"letter": letter, **totals(r)} for letter, r in ratings.items()}
    f, l = per_arm["findings"], per_arm["legacy"]
    pending = list(mech.get("mechanical_pending_reasons") or [])
    for name, a in per_arm.items():
        if a["rated_MR"] < args.min_rated:
            pending.append(f"{name}: {a['rated_MR']} rated M+R statements < {args.min_rated}")
    if pending:
        decision = "pending"
    elif l["fraction_bad"] is not None and f["fraction_bad"] is not None \
            and f["fraction_bad"] <= 0.5 * l["fraction_bad"]:
        decision = "supported"
    else:
        decision = "not_supported"
    ratio = (f["fraction_bad"] / l["fraction_bad"]) if f["fraction_bad"] is not None and l["fraction_bad"] else None
    out = {"decision": decision, "pending_reasons": pending, "assignment": letters,
           "fraction_bad_ratio_findings_over_legacy": ratio, "arms": per_arm,
           "rule": "supported iff fraction_bad(findings) <= 0.5 * fraction_bad(legacy) with >= "
                   f"{args.min_rated} rated M+R per arm and no pending reason"}
    if args.json:
        args.json.write_text(json.dumps(out, indent=1) + "\n")

    def fb(a):
        return "—" if a["fraction_bad"] is None else f"{a['fraction_bad']:.3f} ({a['bad_MR']}/{a['rated_MR']})"
    lines = [f"**Decision: {decision}**" + (f" — {'; '.join(pending)}" if pending else ""), "",
             "| | findings arm | legacy arm |", "|---|---|---|",
             f"| pack letter | {f['letter']} | {l['letter']} |",
             f"| fraction_bad over M+R (bad/rated) | {fb(f)} | {fb(l)} |"]
    for ty in TYPES:
        lines.append(f"| {ty}: correct / incorrect / unsupported | "
                     + " / ".join(str(f['by_type'][ty][r]) for r in RATINGS) + " | "
                     + " / ".join(str(l['by_type'][ty][r]) for r in RATINGS) + " |")
    lines += [f"| C statements bad / rated | {f['C_bad']} / {f['C_rated']} | {l['C_bad']} / {l['C_rated']} |",
              f"| unrated statements | {f['unrated']} | {l['unrated']} |",
              f"| candidates with cross-branch acknowledgment | {f['candidates_with_cross_branch_ack']} | {l['candidates_with_cross_branch_ack']} |",
              f"| repeats unacknowledged / acknowledged | {f['repeats_unacknowledged']} / {f['repeats_acknowledged']} | {l['repeats_unacknowledged']} / {l['repeats_acknowledged']} |",
              f"| rater's totals block agrees with its statement list | {f['rater_totals_agree']} | {l['rater_totals_agree']} |"]
    if ratio is not None:
        lines += ["", f"fraction_bad findings / legacy = {ratio:.2f} (supported needs ≤ 0.50)."]
    for name, a in per_arm.items():
        if a["malformed_statements"]:
            lines.append(f"{name}: statements with an unknown type or rating, ignored: {a['malformed_statements']}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
