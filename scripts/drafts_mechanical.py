#!/usr/bin/env python3
"""drafts_mechanical.py — the mechanical read of the initial_drafts 4-vs-1 pair.

Everything `../labloop-drafts-20260914/PREREG.md` (including its two-GPU amendment)
asks a script to compute: per-arm settlement and cost facts, the per-arm primary
endpoint against the fixed threshold 0.50, the descriptive final-score gap, the two
halves of the kill criterion, lineages (drafts plus the amendment's "disguised
drafts" via the baseline), search progress after 4 / 8 / 20 settled, findings-v2
coverage, the GPU covariate, the M4 throughput read against one-GPU reference arms,
and the throughput diagnosis (leases, session time, training seconds, slot idling,
usage pauses, turns).

    scripts/drafts_mechanical.py --d1 DIR --d4 DIR [--ref DIR ...] \
        [--md OUT.md] [--json OUT.json]

Read-only on every directory it is given. It never reads labels or a split: the
final score it reports is the one `lab run` already recorded.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

THRESHOLD = 0.50
KILL_MARGIN = 0.05
SETTLED_EXEC = ("completed", "invalid", "failed", "killed")


def iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def secs(a, b):
    x, y = iso(a), iso(b)
    return (y - x).total_seconds() if x and y else None


def jread(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def load_pop(d: Path) -> dict:
    return json.loads((d / "population.json").read_text())


# ---------------------------------------------------------------- 1. arm facts

def arm_facts(d: Path) -> dict:
    pop = load_pop(d)
    cands = pop["candidates"]
    ids = sorted(cands)
    ordered = [cands[k] for k in ids]
    execs = collections.Counter(c.get("exec") for c in ordered)
    settled = [c for c in ordered if c.get("exec") in SETTLED_EXEC]
    nonbase = [c for c in settled if c.get("operator") != "baseline"]
    # A job the usage window deferred before its session started leaves a record with
    # an empty model list; it served no model, so it is listed apart (mem_mechanical.py).
    ran = [c for c in ordered if c.get("operator") != "baseline"
           and (c.get("session") or {}).get("models")]
    never_ran = [c["id"] for c in ordered if c.get("operator") != "baseline"
                 and not (c.get("session") or {}).get("models")]
    served = collections.Counter(tuple(c["session"]["models"]) for c in ran)
    costs = [(c.get("session") or {}).get("cost_usd") for c in ran]
    costs = [x for x in costs if isinstance(x, (int, float))]
    turns = [t for t in ((c.get("session") or {}).get("turns") for c in ran) if t]
    errs = [{"id": c["id"], "subtype": (c.get("session") or {}).get("subtype"),
             "is_error": (c.get("session") or {}).get("is_error"),
             "api_error_status": (c.get("session") or {}).get("api_error_status"),
             "rate_limited": (c.get("session") or {}).get("rate_limited"),
             "message": (c.get("session") or {}).get("message")}
            for c in ran
            if (c.get("session") or {}).get("is_error")
            or (c.get("session") or {}).get("subtype") not in (None, "success")
            or (c.get("session") or {}).get("api_error_status")
            or (c.get("session") or {}).get("rate_limited")]
    gpu_h = (pop.get("gpu_seconds") or 0) / 3600
    wall_s = secs(pop.get("started"), pop.get("finished"))
    final = pop.get("final") or {}
    frozen = pop.get("best")
    usage = pop.get("usage") or {}
    return {
        "dir": str(d), "campaign": pop.get("campaign"), "seed": pop.get("seed"),
        "status": pop.get("status"), "stop_reason": pop.get("stop_reason"),
        "started": pop.get("started"), "finished": pop.get("finished"),
        "candidates_total": len(ids),
        "settled": len(settled), "settled_non_baseline": len(nonbase),
        "exec_counts": dict(execs),
        "defers": sum(c.get("defers") or 0 for c in ordered),
        "redispatches": [c["id"] for c in ordered if c.get("redispatch_of")],
        "gpu_seconds": pop.get("gpu_seconds"), "gpu_hours": round(gpu_h, 3),
        "wall_hours": round(wall_s / 3600, 3) if wall_s else None,
        "settled_per_gpu_hour": round(len(settled) / gpu_h, 2) if gpu_h else None,
        "cost_total_usd": round(sum(costs), 2),
        "cost_mean_per_candidate_usd": round(sum(costs) / len(costs), 3) if costs else None,
        "cost_median_usd": round(statistics.median(costs), 3) if costs else None,
        "served_models": {" + ".join(k): v for k, v in served.items()},
        "sessions_never_ran": never_ran,
        "sessions_with_errors": errs,
        "turns_median": statistics.median(turns) if turns else None,
        "turns_mean": round(statistics.mean(turns), 1) if turns else None,
        "turns_max": max(turns) if turns else None,
        "frozen": frozen,
        "frozen_search_fitness": (cands.get(frozen) or {}).get("fitness"),
        "final_score": final.get("score"),
        "claim_recorded": pop.get("claim"),
        "usage": {"pauses": usage.get("pauses"), "waiting_seconds": usage.get("waiting_seconds"),
                  "rate_limits": usage.get("rate_limits"), "deferred": usage.get("deferred"),
                  "hard_kills": usage.get("hard_kills"),
                  "peak_fraction": usage.get("peak_fraction"),
                  "waiting_reason": usage.get("waiting_reason")},
        "_pop": pop,
    }


def endpoint(a: dict, same_models: bool) -> dict:
    """PREREG primary endpoint: the frozen candidate's final-split score against the
    fixed 0.50 — supported / not_supported — or pending if the arm ended early,
    settled fewer than 20 candidates, or the arms were served different models."""
    pending = []
    if a["status"] != "finished" or "max_candidates" not in str(a["stop_reason"]):
        pending.append("ended early (%s)" % a["stop_reason"])
    if a["settled"] < 20:
        pending.append("only %d settled candidates" % a["settled"])
    if not same_models:
        pending.append("the two arms were served different models")
    if pending:
        return {"claim": "pending", "reasons": pending,
                "final_score": a["final_score"], "threshold": THRESHOLD}
    f = a["final_score"]
    return {"claim": "supported" if f is not None and f >= THRESHOLD else "not_supported",
            "reasons": [], "final_score": f, "threshold": THRESHOLD}


# ------------------------------------------------------------------ 2. lineages

CHANGE_RE = re.compile(r"^Change:\s*(.+)", re.M)


def first_sentence(text: str, limit: int = 260) -> str:
    text = " ".join(text.split())
    m = re.search(r"(.+?[.;])(\s|$)", text)
    s = m.group(1) if m else text
    return s if len(s) <= limit else s[: limit - 1] + "…"


def approach_line(d: Path, cid: str) -> str:
    p = d / "candidates" / cid / "summary.md"
    if not p.exists():
        return "(no summary.md)"
    txt = p.read_text()
    m = CHANGE_RE.search(txt)
    if m:
        return first_sentence(m.group(1))
    body = re.sub(r"^#.*$", "", txt, flags=re.M).strip()
    return first_sentence(body) if body else "(empty summary.md)"


def lineages(d: Path, pop: dict) -> dict:
    """Each opening approach is a lineage root: every `draft`, plus the amendment's
    "disguised draft" — an improve whose parent is the baseline, or a crossover with
    the baseline as a parent. Membership follows the first-parent chain."""
    cands = pop["candidates"]
    ids = sorted(cands)
    base = [k for k in ids if cands[k].get("operator") == "baseline"]
    baseline = base[0] if base else "c0000"

    kinds = {}
    for cid in ids:
        op, par = cands[cid].get("operator"), cands[cid].get("parents") or []
        if op == "draft":
            kinds[cid] = "planned draft"
        elif op == "improve" and par == [baseline]:
            kinds[cid] = "disguised draft (improve of the baseline)"
        elif op == "crossover" and baseline in par:
            kinds[cid] = "disguised draft (crossover with the baseline)"
    roots = [c for c in ids if c in kinds]

    def root_of(cid):
        seen, cur = set(), cid
        while cur and cur not in seen:
            seen.add(cur)
            if cur in kinds:
                return cur
            if cur == baseline:
                return None
            par = cands[cur].get("parents") or []
            if not par:
                return None
            cur = par[0]                      # crossovers follow the first parent
        return None

    member_of = {cid: root_of(cid) for cid in ids if cid != baseline}

    held_best, best_val = set(), None
    for cid in ids:                            # settlement order == id order
        f = cands[cid].get("fitness")
        if isinstance(f, (int, float)) and (best_val is None or f > best_val):
            best_val = f
            r = member_of.get(cid)
            if r:
                held_best.add(r)

    frozen = pop.get("best")
    frozen_root = member_of.get(frozen)
    slots = [c for c in ids if cands[c].get("operator") in ("improve", "crossover")
             and c not in kinds]
    on_frozen = [c for c in slots if member_of.get(c) == frozen_root]

    rows = []
    for r in roots:
        members = [c for c in ids if member_of.get(c) == r]
        fits = [cands[c].get("fitness") for c in members
                if isinstance(cands[c].get("fitness"), (int, float))]
        rows.append({
            "root": r, "kind": kinds[r], "operator": cands[r].get("operator"),
            "root_fitness": cands[r].get("fitness"),
            "members": members, "size": len(members),
            "best_search_fitness": max(fits) if fits else None,
            "best_member": (max(members, key=lambda c: cands[c].get("fitness") or -1)
                            if fits else None),
            "ever_held_running_best": r in held_best,
            "approach": approach_line(d, r),
        })
    rows.sort(key=lambda x: -(x["best_search_fitness"] if x["best_search_fitness"] is not None else -1))
    n_planned = sum(1 for r in roots if kinds[r] == "planned draft")
    n_disg = len(roots) - n_planned
    return {
        "baseline": baseline, "n_roots": len(roots),
        "n_planned_drafts": n_planned, "n_disguised_drafts": n_disg,
        "draft_count_as_reported": "%d planned + %d via the baseline" % (n_planned, n_disg),
        "roots_that_ever_held_best": sorted(held_best),
        "frozen": frozen, "frozen_lineage_root": frozen_root,
        "improve_crossover_slots": len(slots),
        "slots_on_frozen_lineage": len(on_frozen),
        "slots_on_frozen_lineage_fraction": (round(len(on_frozen) / len(slots), 3)
                                             if slots else None),
        "unassigned_candidates": [c for c, r in sorted(member_of.items()) if r is None],
        "lineages": rows,
    }


# --------------------------------------------------------- 3. search progress

def progress(pop: dict, other_final):
    cands = pop["candidates"]
    ids = sorted(cands)

    def best_after(n):
        vals = [cands[c].get("fitness") for c in ids[:n]
                if isinstance(cands[c].get("fitness"), (int, float))]
        return max(vals) if vals else None

    first_i = first_id = None
    if other_final is not None:
        for i, c in enumerate(ids):
            f = cands[c].get("fitness")
            if isinstance(f, (int, float)) and f > other_final:
                first_i, first_id = i, c
                break
    return {"best_after_4": best_after(4), "best_after_8": best_after(8),
            "best_after_20": best_after(20), "best_after_all": best_after(len(ids)),
            "other_arm_final": other_final,
            "first_index_over_other_final": first_i,
            "first_candidate_over_other_final": first_id}


# --------------------------------------------------------------- 4. coverage

def coverage(d: Path, pop: dict) -> dict:
    """PREREG (as in the mem2 preregistration): every job's context holds its direct
    parent(s), and once >= 4 cards exist, >= 2 cards from outside its lineage. With
    two slots a sibling still in flight has no card yet, so "cards that existed at
    dispatch" are the candidates that had *ended* before this job was launched."""
    cands = pop["candidates"]
    parents = {k: v.get("parents") or [] for k, v in cands.items()}

    def closure(cid):
        seen, st = set(), list(parents.get(cid, []))
        while st:
            x = st.pop()
            if x not in seen:
                seen.add(x)
                st += parents.get(x, [])
        return seen

    rows, viol_excl, viol_incl, parent_viol = [], [], [], []
    for cid in sorted(cands):
        j = jread(d / "candidates" / cid / "job.json")
        if not j or j.get("operator") == "baseline" or not j.get("findings"):
            continue
        card_ids = [c["id"] for c in j["findings"].get("cards", [])]
        lin = closure(cid) | {cid}
        launched = cands[cid].get("launched")
        available = [k for k, v in cands.items()
                     if v.get("ended") and launched and iso(v["ended"]) <= iso(launched)]
        avail_out = [k for k in available
                     if k not in lin and cands[k].get("operator") != "baseline"]
        out_incl = [i for i in card_ids if i not in lin]
        out_excl = [i for i in out_incl if cands[i].get("operator") != "baseline"]
        need = len(available) >= 4
        if not all(p in card_ids for p in parents[cid]):
            parent_viol.append(cid)
        if need and len(out_incl) < 2:
            viol_incl.append(cid)
        if need and len(out_excl) < 2:
            viol_excl.append(cid)
        rows.append({"job": cid, "parents": parents[cid], "cards": card_ids,
                     "cards_available_at_dispatch": len(available),
                     "outside_lineage_cards": len(out_excl),
                     "outside_incl_baseline": len(out_incl),
                     "out_of_lineage_cards_available_at_dispatch": len(avail_out),
                     "second_out_of_lineage_card_existed": len(avail_out) >= 2,
                     "omitted": [o.get("id") for o in j["findings"].get("omitted", [])]})
    by_id = {r["job"]: r for r in rows}
    return {"jobs": len(rows), "parent_violations": parent_viol,
            "cross_branch_violations_baseline_excluded": viol_excl,
            "cross_branch_violations_baseline_counted": viol_incl,
            "violation_detail": [
                {"job": v, "cards": by_id[v]["cards"],
                 "out_of_lineage_cards_available_at_dispatch":
                     by_id[v]["out_of_lineage_cards_available_at_dispatch"],
                 "second_out_of_lineage_card_existed":
                     by_id[v]["second_out_of_lineage_card_existed"]}
                for v in viol_excl],
            "rows": rows}


# ---------------------------------------------------------- 5. GPU covariate

def gpu_covariate(pop: dict, lin: dict) -> dict:
    cands = pop["candidates"]
    per = collections.defaultdict(list)
    for cid in sorted(cands):
        per[cands[cid].get("gpu")].append(cid)
    out = {}
    for g, members in sorted(per.items(), key=lambda kv: (kv[0] is None, kv[0])):
        fits = [cands[c].get("fitness") for c in members
                if isinstance(cands[c].get("fitness"), (int, float))]
        leases = [x for x in (secs(cands[c].get("launched"), cands[c].get("ended"))
                              for c in members) if x]
        out[str(g)] = {"candidates": members, "n": len(members),
                       "best_search_fitness": max(fits) if fits else None,
                       "mean_lease_min": round(statistics.mean(leases) / 60, 2) if leases else None,
                       "median_lease_min": round(statistics.median(leases) / 60, 2) if leases else None}
    frozen = pop.get("best")
    return {"per_gpu": out,
            "gpu_of_each_lineage_root": {r["root"]: cands[r["root"]].get("gpu")
                                         for r in lin["lineages"]},
            "frozen": frozen, "frozen_gpu": (cands.get(frozen) or {}).get("gpu")}


# --------------------------------------------------- 6. timing / diagnosis

def timing(d: Path, pop: dict) -> dict:
    cands = pop["candidates"]
    rows = []
    for cid in sorted(cands):
        c = cands[cid]
        lease = secs(c.get("launched"), c.get("ended"))
        sess_ms = (c.get("session") or {}).get("duration_ms")
        ts = jread(d / "candidates" / cid / "code" / "train_stats.json") or {}
        mc = jread(d / "candidates" / cid / "out" / "memory_config.json") or {}
        train = ts.get("train_seconds", mc.get("train_seconds"))
        rows.append({
            "id": cid, "operator": c.get("operator"), "gpu": c.get("gpu"),
            "lease_sec": round(lease, 1) if lease else None,
            "session_sec": round(sess_ms / 1000, 1) if sess_ms else None,
            "session_over_lease": (round(sess_ms / 1000 / lease, 3)
                                   if sess_ms and lease else None),
            "train_sec": train,
            "run_wall_sec": mc.get("wall_seconds"),
            "loaded_existing_weights": mc.get("loaded_existing_weights"),
            "turns": (c.get("session") or {}).get("turns"),
            "launched": c.get("launched"), "ended": c.get("ended"),
        })
    worker = [r for r in rows if r["operator"] != "baseline"]
    for r in rows:
        r["non_training_sec"] = (round(r["lease_sec"] - r["train_sec"], 1)
                                 if isinstance(r.get("lease_sec"), (int, float))
                                 and isinstance(r.get("train_sec"), (int, float)) else None)

    def dist(key, rs):
        vals = [r[key] for r in rs if isinstance(r.get(key), (int, float))]
        if not vals:
            return None
        return {"n": len(vals), "median": round(statistics.median(vals), 1),
                "mean": round(statistics.mean(vals), 1),
                "min": round(min(vals), 1), "max": round(max(vals), 1)}

    iv = sorted((iso(r["launched"]), iso(r["ended"])) for r in rows
                if r["launched"] and r["ended"])
    edges = sorted({t for a, b in iv for t in (a, b)})
    union = conc2 = 0.0
    for a, b in zip(edges, edges[1:]):
        n = sum(1 for s, e in iv if s <= a and e >= b)
        w = (b - a).total_seconds()
        if n >= 1:
            union += w
        if n >= 2:
            conc2 += w
    # how much of each candidate's own lease was shared with another live lease
    for r in rows:
        a, b = iso(r["launched"]), iso(r["ended"])
        if not (a and b) or b <= a:
            r["overlap_fraction"] = None
            continue
        ov = 0.0
        for s, e in iv:
            if (s, e) == (a, b):
                continue
            lo, hi = max(a, s), min(b, e)
            if hi > lo:
                ov += (hi - lo).total_seconds()
        r["overlap_fraction"] = round(min(ov / (b - a).total_seconds(), 1.0), 3)
    shared = [r for r in worker if (r.get("overlap_fraction") or 0) >= 0.9]
    mostly_solo = [r for r in worker if (r.get("overlap_fraction") or 0) < 0.5]

    lease_sum = sum(r["lease_sec"] or 0 for r in rows)
    wall = secs(pop.get("started"), pop.get("finished")) or 0
    gpu_s = pop.get("gpu_seconds") or 0
    return {
        "rows": rows,
        "lease_sec": dist("lease_sec", worker), "session_sec": dist("session_sec", worker),
        "non_training_sec": dist("non_training_sec", worker),
        "lease_sec_overlap_ge_90pct": dist("lease_sec", shared),
        "lease_sec_overlap_lt_50pct": dist("lease_sec", mostly_solo),
        "train_sec": dist("train_sec", worker), "run_wall_sec": dist("run_wall_sec", worker),
        "turns": dist("turns", worker),
        "session_over_lease": dist("session_over_lease", worker),
        "lease_seconds_sum": round(lease_sum, 1),
        "gpu_seconds_recorded": gpu_s,
        "gpu_seconds_minus_lease_sum": round(gpu_s - lease_sum, 1),
        "wall_seconds": round(wall, 1),
        "lease_union_seconds": round(union, 1),
        "two_leases_open_seconds": round(conc2, 1),
        "two_leases_open_fraction_of_wall": round(conc2 / wall, 3) if wall else None,
        "slot_occupancy_leases_over_2x_wall": round(lease_sum / (2 * wall), 3) if wall else None,
        "usage_waiting_seconds": (pop.get("usage") or {}).get("waiting_seconds"),
        "usage_pauses": (pop.get("usage") or {}).get("pauses"),
        "loaded_existing_weights_true": [r["id"] for r in rows
                                         if r["loaded_existing_weights"] is True],
    }


# --------------------------------------------------- 6b. session anomalies

def session_anomalies(d: Path, pop: dict) -> dict:
    """Things worth a human's eye: denied tool calls, sessions whose reported turn
    count exceeds the campaign's worker_max_turns, and non-empty session.stderr."""
    cap = None
    toml = d / "campaign.toml"
    if toml.exists():
        m = re.search(r"^worker_max_turns\s*=\s*(\d+)", toml.read_text(), re.M)
        if m:
            cap = int(m.group(1))
    denials, over_cap, stderr_lines = {}, [], {}
    for cid in sorted(pop["candidates"]):
        s = jread(d / "candidates" / cid / "session.json") or {}
        pd = s.get("permission_denials") or []
        if pd:
            denials[cid] = [p.get("tool_name") for p in pd]
        n = s.get("num_turns")
        if cap and isinstance(n, int) and n > cap:
            over_cap.append({"id": cid, "turns": n, "cap": cap})
        err = d / "candidates" / cid / "session.stderr"
        if err.exists() and err.stat().st_size:
            first = err.read_text().strip().splitlines()[0][:160]
            stderr_lines.setdefault(first, []).append(cid)
    return {"worker_max_turns": cap,
            "permission_denials_by_candidate": denials,
            "permission_denials_total": sum(len(v) for v in denials.values()),
            "sessions_over_turn_cap": over_cap,
            "session_stderr_first_lines": stderr_lines}


# ------------------------------------------------------- 7. weight freshness

def weight_checks(d: Path, pop: dict) -> dict:
    rows, late = [], []
    for cid in sorted(pop["candidates"]):
        cdir = d / "candidates" / cid
        cands = [p for p in (cdir / "code").glob("*.safetensors")] if (cdir / "code").is_dir() else []
        if not cands:
            continue
        cfg = jread(cdir / "config.json") or {}
        start = iso(cfg.get("start_time"))
        code_files = [p for p in (cdir / "code").glob("*") if p.suffix in (".py", ".sh")]
        oldest_code = min((p.stat().st_mtime for p in code_files), default=None)
        for w in cands:
            wm = w.stat().st_mtime
            ok_start = (start is None) or (wm >= start.timestamp())
            ok_code = (oldest_code is None) or (wm >= oldest_code)
            rows.append({"id": cid, "file": w.name,
                         "weights_mtime": datetime.fromtimestamp(wm, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "dispatch": cfg.get("start_time"),
                         "weights_postdate_dispatch": ok_start,
                         "weights_postdate_oldest_code_file": ok_code})
            if not (ok_start and ok_code):
                late.append(cid)
    return {"checked": len(rows), "violations": sorted(set(late)), "rows": rows}


# --------------------------------------------------------------------- M4

def m4(d1: dict, d4: dict, refs: list) -> dict:
    ref_rows = [{"arm": r["campaign"], "dir": r["dir"], "settled": r["settled"],
                 "gpu_hours": r["gpu_hours"],
                 "settled_per_gpu_hour": r["settled_per_gpu_hour"],
                 "wall_hours": r["wall_hours"]} for r in refs]
    vals = [r["settled_per_gpu_hour"] for r in ref_rows if r["settled_per_gpu_hour"]]
    lo, hi = (min(vals), max(vals)) if vals else (None, None)
    two = [d1["settled_per_gpu_hour"], d4["settled_per_gpu_hour"]]
    return {"two_slot": {d1["campaign"]: d1["settled_per_gpu_hour"],
                         d4["campaign"]: d4["settled_per_gpu_hour"]},
            "one_slot_references": ref_rows,
            "reference_min": lo, "reference_max": hi,
            "criterion": "two slots settle fewer candidates per GPU-hour than one",
            "fires_against_every_reference": bool(vals) and all(t < lo for t in two),
            "fires_against_any_reference": bool(vals) and any(t < hi for t in two)}


# ------------------------------------------------------------------ markdown

def fmt(v, nd=3):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return ("%.*f" % (nd, v)).rstrip("0").rstrip(".") if abs(v) < 1000 else "%.1f" % v
    return str(v)


def render(out: dict) -> str:
    d1, d4 = out["arms"]["D1"], out["arms"]["D4"]
    L = []
    A = L.append
    A("# drafts pair — mechanical read (initial_drafts 1 vs 4)\n")
    A("Generated by `scripts/drafts_mechanical.py`, read-only over both arm directories. "
      "Search fitness is the hidden search split and is optimistic by construction; the "
      "final score is the single read `lab run` already recorded.\n")

    A("## 1. Per-arm facts\n")
    A("| measure | D1 (one draft) | D4 (four drafts) |")
    A("|---|---|---|")

    def row(label, key, f=lambda v: fmt(v)):
        A("| %s | %s | %s |" % (label, f(d1.get(key)), f(d4.get(key))))

    row("campaign", "campaign")
    row("seed", "seed")
    row("stop reason", "stop_reason")
    row("candidates in the population", "candidates_total")
    row("settled", "settled")
    row("settled, non-baseline", "settled_non_baseline")
    row("exec counts", "exec_counts",
        lambda v: ", ".join("%s %d" % (k, n) for k, n in (v or {}).items()))
    row("defers", "defers")
    row("re-dispatches", "redispatches", lambda v: ", ".join(v) if v else "none")
    row("GPU-hours", "gpu_hours")
    row("wall clock (h)", "wall_hours")
    row("settled per GPU-hour", "settled_per_gpu_hour")
    row("list-price cost, all sessions", "cost_total_usd", lambda v: "$%s" % fmt(v, 2))
    row("cost per candidate, mean", "cost_mean_per_candidate_usd", lambda v: "$%s" % fmt(v))
    row("cost per candidate, median", "cost_median_usd", lambda v: "$%s" % fmt(v))
    row("served models (sessions)", "served_models",
        lambda v: "; ".join("%s: %d" % (k, n) for k, n in (v or {}).items()))
    row("sessions that never started (no model served)", "sessions_never_ran",
        lambda v: ", ".join(v) if v else "none")
    row("sessions with an error flag", "sessions_with_errors",
        lambda v: ", ".join("%s (%s)" % (e["id"], e["subtype"]) for e in v) if v else "none")
    A("| turns median / mean / max | %s / %s / %s | %s / %s / %s |"
      % (fmt(d1["turns_median"]), fmt(d1["turns_mean"]), fmt(d1["turns_max"]),
         fmt(d4["turns_median"]), fmt(d4["turns_mean"]), fmt(d4["turns_max"])))
    row("frozen candidate", "frozen")
    row("frozen search fitness", "frozen_search_fitness", lambda v: fmt(v, 6))
    row("final-split score (read once)", "final_score", lambda v: fmt(v, 6))
    row("claim vs the fixed 0.50, as lab recorded it", "claim_recorded")
    row("usage pauses / seconds waiting", "usage",
        lambda v: "%s / %s s" % (v.get("pauses"), round(v.get("waiting_seconds") or 0)))

    A("\n## 2. Primary endpoint (per arm, against the fixed 0.50)\n")
    A("| arm | frozen | final score | endpoint | pending reasons |")
    A("|---|---|---|---|---|")
    for k in ("D1", "D4"):
        e = out["endpoint"][k]
        A("| %s | %s | %s | **%s** | %s |"
          % (k, out["arms"][k]["frozen"], fmt(e["final_score"], 6), e["claim"],
             "; ".join(e["reasons"]) or "none"))
    A("\nDescriptive gap D4 − D1 in final score: **%s** (one seed, two runs, no test; "
      "not evidence that either setting is better).\n"
      % fmt(out["final_gap_d4_minus_d1"], 4))

    A("## 3. Kill criterion\n")
    k = out["kill_criterion"]
    A("- Half A — D4's frozen final (%s) below D1's (%s) by more than %s: **%s** "
      "(gap %s)." % (fmt(k["d4_final"], 6), fmt(k["d1_final"], 6), KILL_MARGIN,
                     fmt(k["half_a_final_gap"]), fmt(k["gap"], 4)))
    A("- Half B — no D4 draft after the first beat the first on the search split: **%s** "
      "(first draft %s %s; later drafts %s)."
      % (fmt(k["half_b_no_later_draft_beat_first"]), k["first_draft"],
         fmt(k["first_draft_fitness"], 6),
         ", ".join("%s %s" % (i, fmt(v, 6)) for i, v in k["later_drafts"]) or "none"))
    A("- **The criterion fires: %s.**\n" % fmt(k["fires"]))

    A("## 4. Lineages\n")
    for arm in ("D1", "D4"):
        lin = out["lineages"][arm]
        A("### %s — %s\n" % (arm, lin["draft_count_as_reported"]))
        A("| root | kind | members | best search fitness | ever held the running best | approach |")
        A("|---|---|---|---|---|---|")
        for r in lin["lineages"]:
            A("| %s | %s | %d (%s) | %s | %s | %s |"
              % (r["root"], r["kind"], len(r["members"]), ", ".join(r["members"]),
                 fmt(r["best_search_fitness"], 6), fmt(r["ever_held_running_best"]),
                 r["approach"]))
        A("\nFrozen candidate %s sits in lineage %s; %d of %d improve/crossover slots (%s) "
          "went to that lineage. Candidates in no lineage: %s.\n"
          % (lin["frozen"], lin["frozen_lineage_root"], lin["slots_on_frozen_lineage"],
             lin["improve_crossover_slots"], fmt(lin["slots_on_frozen_lineage_fraction"]),
             ", ".join(lin["unassigned_candidates"]) or "none"))

    A("## 5. Search progress\n")
    p1, p4 = out["progress"]["D1"], out["progress"]["D4"]
    A("| measure | D1 | D4 |")
    A("|---|---|---|")
    for label, key in (("best search fitness after 4 settled", "best_after_4"),
                       ("after 8 settled", "best_after_8"),
                       ("after 20 settled", "best_after_20"),
                       ("after every settled candidate", "best_after_all")):
        A("| %s | %s | %s |" % (label, fmt(p1[key], 6), fmt(p4[key], 6)))
    A("| the other arm's final score | %s | %s |"
      % (fmt(p1["other_arm_final"], 6), fmt(p4["other_arm_final"], 6)))
    A("| first candidate exceeding it on the search split | %s (index %s) | %s (index %s) |"
      % (p1["first_candidate_over_other_final"] or "never",
         fmt(p1["first_index_over_other_final"]),
         p4["first_candidate_over_other_final"] or "never",
         fmt(p4["first_index_over_other_final"])))

    A("\n## 6. Coverage under findings-v2\n")
    for arm in ("D1", "D4"):
        c = out["coverage"][arm]
        A("- **%s**: %d jobs with cards; parent violations %d %s; jobs with fewer than two "
          "out-of-lineage cards once ≥ 4 cards existed at dispatch: %d %s (baseline card "
          "not counted), %d %s (baseline counted)."
          % (arm, c["jobs"], len(c["parent_violations"]), c["parent_violations"] or "",
             len(c["cross_branch_violations_baseline_excluded"]),
             c["cross_branch_violations_baseline_excluded"],
             len(c["cross_branch_violations_baseline_counted"]),
             c["cross_branch_violations_baseline_counted"]))
        for v in c["violation_detail"]:
            A("    - %s: cards %s; non-baseline out-of-lineage cards that existed at dispatch: "
              "%d (a second one existed: %s)"
              % (v["job"], v["cards"], v["out_of_lineage_cards_available_at_dispatch"],
                 fmt(v["second_out_of_lineage_card_existed"])))

    A("\n## 7. GPU covariate\n")
    for arm in ("D1", "D4"):
        g = out["gpu"][arm]
        A("### %s\n" % arm)
        A("| GPU | candidates | best search fitness | mean lease (min) | median lease (min) |")
        A("|---|---|---|---|---|")
        for gid, v in g["per_gpu"].items():
            A("| %s | %d (%s) | %s | %s | %s |"
              % (gid, v["n"], ", ".join(v["candidates"]), fmt(v["best_search_fitness"], 6),
                 fmt(v["mean_lease_min"]), fmt(v["median_lease_min"])))
        A("\nLineage roots by GPU: %s. Frozen %s on GPU %s.\n"
          % (", ".join("%s→GPU %s" % (k, v)
                       for k, v in g["gpu_of_each_lineage_root"].items()),
             g["frozen"], g["frozen_gpu"]))
    A("The two arms' frozen candidates trained on %s (D1 GPU %s, D4 GPU %s).\n"
      % ("**different GPUs**" if out["frozen_gpus_differ"] else "the same GPU",
         out["gpu"]["D1"]["frozen_gpu"], out["gpu"]["D4"]["frozen_gpu"]))

    A("## 8. M4 throughput read\n")
    m = out["m4"]
    A("| arm | slots | settled | GPU-hours | settled per GPU-hour | wall (h) |")
    A("|---|---|---|---|---|---|")
    for arm in ("D1", "D4"):
        a = out["arms"][arm]
        A("| %s (%s) | 2 | %d | %s | **%s** | %s |"
          % (a["campaign"], arm, a["settled"], fmt(a["gpu_hours"]),
             fmt(a["settled_per_gpu_hour"]), fmt(a["wall_hours"])))
    for r in m["one_slot_references"]:
        A("| %s (reference) | 1 | %d | %s | %s | %s |"
          % (r["arm"], r["settled"], fmt(r["gpu_hours"]),
             fmt(r["settled_per_gpu_hour"]), fmt(r["wall_hours"])))
    A("\nM4 kill criterion — *%s*: fires against every reference: **%s**; against at "
      "least one reference: %s.\n"
      % (m["criterion"], fmt(m["fires_against_every_reference"]),
         fmt(m["fires_against_any_reference"])))

    A("## 9. Throughput diagnosis (numbers)\n")
    names = ["D1", "D4"] + [r["arm"] for r in out["m4"]["one_slot_references"]]
    tim = out["timing"]
    A("| measure | " + " | ".join(names) + " |")
    A("|---" * (1 + len(names)) + "|")
    for label, key in (("lease seconds (ended − launched)", "lease_sec"),
                       ("session duration (s)", "session_sec"),
                       ("training seconds recorded by the candidate", "train_sec"),
                       ("run.sh wall seconds recorded", "run_wall_sec"),
                       ("turns per session", "turns"),
                       ("session seconds / lease seconds", "session_over_lease"),
                       ("non-training lease seconds (lease − training)", "non_training_sec"),
                       ("lease of candidates ≥ 90 % overlapped by a sibling", "lease_sec_overlap_ge_90pct"),
                       ("lease of candidates < 50 % overlapped", "lease_sec_overlap_lt_50pct")):
        cells = []
        for n in names:
            dd = tim[n].get(key)
            cells.append("%s / %s (n=%d)" % (fmt(dd["median"]), fmt(dd["mean"]), dd["n"])
                         if dd else "—")
        A("| %s, median / mean | %s |" % (label, " | ".join(cells)))
    for label, key in (("sum of leases (s)", "lease_seconds_sum"),
                       ("gpu_seconds recorded", "gpu_seconds_recorded"),
                       ("gpu_seconds − sum of leases", "gpu_seconds_minus_lease_sum"),
                       ("campaign wall clock (s)", "wall_seconds"),
                       ("seconds with a lease open (union)", "lease_union_seconds"),
                       ("seconds with two leases open", "two_leases_open_seconds"),
                       ("two-lease fraction of wall", "two_leases_open_fraction_of_wall"),
                       ("slot occupancy = leases / (2 × wall)",
                        "slot_occupancy_leases_over_2x_wall"),
                       ("seconds waiting on usage", "usage_waiting_seconds"),
                       ("usage pauses", "usage_pauses")):
        A("| %s | %s |" % (label, " | ".join(fmt(tim[n].get(key)) for n in names)))

    A("\n## 10. Weight-freshness and reload checks\n")
    for arm in names:
        w = out["weights"].get(arm)
        if not w:
            continue
        A("- **%s**: %d weight files checked; files not postdating their candidate's "
          "dispatch or its code copy: %s. `loaded_existing_weights: true` in: %s."
          % (arm, w["checked"], w["violations"] or "none",
             ", ".join(out["timing"][arm]["loaded_existing_weights_true"]) or "none"))
    A("\nA candidate that records no `loaded_existing_weights` key at all is listed as "
      "“none” here; the key is written only by code that has a load path.\n")

    A("## 11. Session anomalies\n")
    for arm in names:
        s = out["session_anomalies"].get(arm)
        if not s:
            continue
        A("- **%s** (worker_max_turns %s): %d denied tool calls in %d sessions (%s); "
          "sessions over the turn cap: %s; non-empty session.stderr: %s."
          % (arm, fmt(s["worker_max_turns"]), s["permission_denials_total"],
             len(s["permission_denials_by_candidate"]),
             ", ".join(s["permission_denials_by_candidate"]) or "none",
             ", ".join("%s (%d turns)" % (o["id"], o["turns"])
                       for o in s["sessions_over_turn_cap"]) or "none",
             "; ".join("%d × “%s”" % (len(v), k)
                       for k, v in s["session_stderr_first_lines"].items()) or "none"))
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--d1", required=True, type=Path, help="one-draft arm directory")
    ap.add_argument("--d4", required=True, type=Path, help="four-draft arm directory")
    ap.add_argument("--ref", type=Path, action="append", default=[],
                    help="single-GPU reference arm for the M4 read (repeatable)")
    ap.add_argument("--md", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    arms = {"D1": arm_facts(args.d1), "D4": arm_facts(args.d4)}
    refs = [arm_facts(p) for p in args.ref]
    pops = {"D1": arms["D1"].pop("_pop"), "D4": arms["D4"].pop("_pop")}
    dirs = {"D1": args.d1, "D4": args.d4}
    for r, p in zip(refs, args.ref):
        pops[r["campaign"]] = r.pop("_pop")
        dirs[r["campaign"]] = p

    same_models = set(arms["D1"]["served_models"]) == set(arms["D4"]["served_models"])
    ep = {k: endpoint(arms[k], same_models) for k in arms}
    lin = {k: lineages(dirs[k], pops[k]) for k in ("D1", "D4")}

    f1, f4 = arms["D1"]["final_score"], arms["D4"]["final_score"]
    d4c = pops["D4"]["candidates"]
    drafts4 = [c for c in sorted(d4c) if d4c[c].get("operator") == "draft"]
    first = drafts4[0] if drafts4 else None
    ff = d4c[first].get("fitness") if first else None
    later = [(c, d4c[c].get("fitness")) for c in drafts4[1:]]
    half_a = bool(f1 is not None and f4 is not None and f4 < f1 - KILL_MARGIN)
    half_b = all((v is None or ff is None or v <= ff) for _, v in later)
    kill = {"d1_final": f1, "d4_final": f4,
            "gap": (f4 - f1) if (f1 is not None and f4 is not None) else None,
            "margin": KILL_MARGIN, "half_a_final_gap": half_a,
            "first_draft": first, "first_draft_fitness": ff, "later_drafts": later,
            "half_b_no_later_draft_beat_first": half_b,
            "fires": bool(half_a and half_b)}

    out = {
        "generated_by": "scripts/drafts_mechanical.py",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "threshold": THRESHOLD, "kill_margin": KILL_MARGIN,
        "arms": arms, "references": refs, "same_served_models": same_models,
        "endpoint": ep,
        "final_gap_d4_minus_d1": (f4 - f1) if (f1 is not None and f4 is not None) else None,
        "kill_criterion": kill,
        "lineages": lin,
        "progress": {"D1": progress(pops["D1"], f4), "D4": progress(pops["D4"], f1)},
        "coverage": {k: coverage(dirs[k], pops[k]) for k in ("D1", "D4")},
        "gpu": {k: gpu_covariate(pops[k], lin[k]) for k in ("D1", "D4")},
        "timing": {k: timing(dirs[k], pops[k]) for k in pops},
        "session_anomalies": {k: session_anomalies(dirs[k], pops[k]) for k in pops},
        "weights": {k: weight_checks(dirs[k], pops[k]) for k in pops},
    }
    out["frozen_gpus_differ"] = out["gpu"]["D1"]["frozen_gpu"] != out["gpu"]["D4"]["frozen_gpu"]
    out["m4"] = m4(arms["D1"], arms["D4"], refs)

    text = render(out)
    print(text)
    if args.md:
        args.md.write_text(text)
    if args.json:
        args.json.write_text(json.dumps(out, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
