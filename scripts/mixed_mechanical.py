#!/usr/bin/env python3
"""mixed_mechanical.py — the mechanical read of the mixed-model arm (Opus drafts,
Sonnet improves) against its all-Sonnet control D4.

Everything `../labloop-mixed-20260914/PREREG.md` and its "Amendment before launch"
ask a script to compute: the four preregistered reads (task claim, cost per
candidate, final-split score, where the Opus money went), the kill criterion as
fixed, the secondary measures (requested vs served per session and per operator,
governor, coverage under findings-v2, knob ledger counts, valid candidates per
GPU-hour, exec counts, the GPU covariate), the two-slot throughput read (settled per
lease-hour and per wall-hour, lease minus recorded training seconds) against D4 and
the two one-GPU mem2 arms, and the leakage checks.

    scripts/mixed_mechanical.py --arm DIR --control DIR [--ref DIR ...] \
        [--md OUT.md] [--json OUT.json]

Read-only on every directory it is given. Most of the work is done by the functions
in `scripts/drafts_mechanical.py`, which this script imports; what is added here is
the per-session model check, the cost split, the knob-ledger counts, the weight
hashes, the throughput-per-wall-hour figures, and this arm's kill criterion.

It never reads labels or a split: the final score it reports is the one `lab run`
already recorded.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import drafts_mechanical as dm  # noqa: E402
from drafts_mechanical import (  # noqa: E402
    THRESHOLD, SETTLED_EXEC, arm_facts, coverage, gpu_covariate, iso, jread,
    lineages, progress, secs, session_anomalies, weight_checks,
)

# The kill criterion's two halves, fixed in PREREG before launch.
COST_BAND = 0.10                 # "within 10 % of D4's cost per candidate"
HAIKU = "claude-haiku-4-5-20251001"   # served alongside the requested model in every
                                      # session of every arm read here; not a worker model.

# This arm's candidates record their training wall clock under three different keys
# (train_wall_s, train_wall_seconds, train_seconds); the reference arms use
# train_seconds. drafts_mechanical.py looks only for train_seconds, so the key list is
# extended here and dm.timing is called through the patched lookup below.
TRAIN_KEYS = ("train_seconds", "train_wall_seconds", "train_wall_s")
RUN_WALL_KEYS = ("wall_seconds", "last_run_wall_seconds", "run_wall_seconds")


def first_key(d: dict, keys) -> object:
    for k in keys:
        if isinstance(d.get(k), (int, float)):
            return d[k]
    return None


def timing(d: Path, pop: dict) -> dict:
    """dm.timing, with the training-seconds and run-wall-seconds key lists widened to
    the keys this arm's candidates actually wrote, and the derived distributions
    recomputed from the repaired rows."""
    out = dm.timing(d, pop)
    for r in out["rows"]:
        mc = jread(d / "candidates" / r["id"] / "out" / "memory_config.json") or {}
        ts = jread(d / "candidates" / r["id"] / "code" / "train_stats.json") or {}
        r["train_sec"] = first_key(ts, TRAIN_KEYS)
        if r["train_sec"] is None:
            r["train_sec"] = first_key(mc, TRAIN_KEYS)
        r["train_sec_key"] = next((k for k in TRAIN_KEYS
                                   if isinstance(ts.get(k), (int, float))
                                   or isinstance(mc.get(k), (int, float))), None)
        r["run_wall_sec"] = first_key(mc, RUN_WALL_KEYS)
        r["non_training_sec"] = (round(r["lease_sec"] - r["train_sec"], 1)
                                 if isinstance(r.get("lease_sec"), (int, float))
                                 and isinstance(r.get("train_sec"), (int, float)) else None)
    worker = [r for r in out["rows"] if r["operator"] != "baseline"]

    def dist(key, rs):
        vals = [r[key] for r in rs if isinstance(r.get(key), (int, float))]
        if not vals:
            return None
        return {"n": len(vals), "median": round(statistics.median(vals), 1),
                "mean": round(statistics.mean(vals), 1),
                "min": round(min(vals), 1), "max": round(max(vals), 1)}

    for key in ("train_sec", "non_training_sec", "run_wall_sec"):
        out[key] = dist(key, worker)
    out["train_sec_keys_used"] = dict(collections.Counter(
        r.get("train_sec_key") for r in worker))
    return out


# --------------------------------------------------- requested vs served models

def model_check(d: Path, pop: dict) -> dict:
    """PREREG read 1's pending clause: *any session served a model other than the one
    requested for its operator*, checked per session from config.json
    (`agent.requested`, `agent.requested_source`, `agent.served`). The baseline runs no
    session. Haiku is served alongside the requested model in every session of every
    arm read here; it is reported, and the check is against the requested model being
    present and no other worker-class model being served."""
    rows, mismatches = [], []
    by_op = collections.defaultdict(lambda: collections.Counter())
    for cid in sorted(pop["candidates"]):
        c = pop["candidates"][cid]
        cfg = jread(d / "candidates" / cid / "config.json") or {}
        a = cfg.get("agent") or {}
        served = list(a.get("served") or [])
        req = a.get("requested")
        op = c.get("operator")
        if op == "baseline":
            rows.append({"id": cid, "operator": op, "requested": req,
                         "requested_source": a.get("requested_source"),
                         "served": served, "ok": None,
                         "note": "baseline runs no agent session"})
            continue
        extra = [m for m in served if m != req and m != HAIKU]
        ok = bool(req) and req in served and not extra
        by_op[op][(req, " + ".join(served))] += 1
        rows.append({"id": cid, "operator": op, "requested": req,
                     "requested_source": a.get("requested_source"),
                     "served": served, "ok": ok,
                     "unexpected_models": extra,
                     "note": None if ok else "requested model not served, or another served"})
        if not ok:
            mismatches.append(cid)
    return {"rows": rows, "mismatches": mismatches,
            "sessions_checked": sum(1 for r in rows if r["ok"] is not None),
            "by_operator": {op: {"%s → %s" % k: n for k, n in ctr.items()}
                            for op, ctr in sorted(by_op.items())},
            "haiku_alongside": sum(1 for r in rows if HAIKU in (r["served"] or []))}


def endpoint_mixed(a: dict, mc: dict) -> dict:
    """PREREG read 1, with its three pending clauses exactly as written."""
    pending = []
    if a["status"] != "finished" or "max_candidates" not in str(a["stop_reason"]):
        pending.append("ended early (%s)" % a["stop_reason"])
    if a["settled"] < 20:
        pending.append("only %d settled candidates" % a["settled"])
    if mc["mismatches"]:
        pending.append("sessions served a model other than the one requested: %s"
                       % ", ".join(mc["mismatches"]))
    if pending:
        return {"claim": "pending", "reasons": pending,
                "final_score": a["final_score"], "threshold": THRESHOLD}
    f = a["final_score"]
    return {"claim": "supported" if f is not None and f >= THRESHOLD else "not_supported",
            "reasons": [], "final_score": f, "threshold": THRESHOLD}


# ------------------------------------------------------------------- 2. costs

def costs(d: Path, pop: dict) -> dict:
    """PREREG read 2: per-session total_cost_usd over settled candidates. config.json
    carries no cost field; `session.json`'s `total_cost_usd` is the per-session number
    and population.json copies it to `session.cost_usd` — both are read and compared."""
    per, by_op = [], collections.defaultdict(list)
    for cid in sorted(pop["candidates"]):
        c = pop["candidates"][cid]
        if c.get("exec") not in SETTLED_EXEC or c.get("operator") == "baseline":
            continue
        s = jread(d / "candidates" / cid / "session.json") or {}
        cost = s.get("total_cost_usd")
        pop_cost = (c.get("session") or {}).get("cost_usd")
        cfg = jread(d / "candidates" / cid / "config.json") or {}
        req = ((cfg.get("agent") or {}).get("requested"))
        per.append({"id": cid, "operator": c.get("operator"), "requested_model": req,
                    "total_cost_usd": cost, "population_cost_usd": pop_cost,
                    "agrees": (cost == pop_cost)})
        if isinstance(cost, (int, float)):
            by_op[c.get("operator")].append(cost)
    vals = [r["total_cost_usd"] for r in per if isinstance(r["total_cost_usd"], (int, float))]
    settled = len([c for c in pop["candidates"].values() if c.get("exec") in SETTLED_EXEC])

    def dist(v):
        return None if not v else {
            "n": len(v), "total": round(sum(v), 4), "mean": round(statistics.mean(v), 4),
            "median": round(statistics.median(v), 4), "min": round(min(v), 4),
            "max": round(max(v), 4)}

    by_model = collections.defaultdict(list)
    for r in per:
        if isinstance(r["total_cost_usd"], (int, float)):
            by_model[r["requested_model"]].append(r["total_cost_usd"])
    return {
        "rows": per,
        "sessions": len(vals),
        "settled_candidates": settled,
        "total_usd": round(sum(vals), 4),
        "per_settled_candidate_usd": round(sum(vals) / settled, 4) if settled else None,
        "per_session": dist(vals),
        "by_operator": {k: dist(v) for k, v in sorted(by_op.items())},
        "by_requested_model": {str(k): dist(v) for k, v in sorted(by_model.items(), key=str)},
        "population_copy_disagreements": [r["id"] for r in per if not r["agrees"]],
    }


# ------------------------------------------------------------- knob ledger

def ledger(d: Path, pop: dict) -> dict:
    """The knob ledger as the mem2 PREREG reports it: how many settled non-baseline
    candidates wrote the knobs file, and per job how many ledger rows were carried and
    how many were dropped by the 2 KiB bound (`findings.ledger.omitted`)."""
    wrote = [cid for cid in sorted(pop["candidates"])
             if pop["candidates"][cid].get("operator") != "baseline"
             and (d / "candidates" / cid / "out" / "memory_config.json").exists()]
    rows, bound = [], None
    for cid in sorted(pop["candidates"]):
        j = jread(d / "candidates" / cid / "job.json") or {}
        f = j.get("findings") or {}
        led = f.get("ledger")
        if led is None:
            continue
        bound = bound or ((f.get("limits") or {}).get("ledger_max_bytes"))
        rows.append({"job": cid, "file": led.get("file"),
                     "rows": len(led.get("rows") or []),
                     "row_ids": led.get("rows") or [],
                     "dropped_by_the_bound": len(led.get("omitted") or []),
                     "dropped_ids": led.get("omitted") or [],
                     "bytes": led.get("bytes")})
    carried = [r["rows"] for r in rows]
    dropped = [r["dropped_by_the_bound"] for r in rows]
    byts = [r["bytes"] for r in rows if isinstance(r["bytes"], int)]
    return {"knobs_file": (pop.get("memory") or {}).get("knobs"),
            "ledger_max_bytes": bound,
            "candidates_that_wrote_the_knobs_file": len(wrote),
            "settled_non_baseline": len([c for c in pop["candidates"].values()
                                         if c.get("operator") != "baseline"
                                         and c.get("exec") in SETTLED_EXEC]),
            "jobs_with_a_ledger": len(rows),
            "rows_carried_total": sum(carried),
            "rows_carried_median": statistics.median(carried) if carried else None,
            "rows_carried_max": max(carried) if carried else None,
            "rows_dropped_total": sum(dropped),
            "rows_dropped_median": statistics.median(dropped) if dropped else None,
            "rows_dropped_max": max(dropped) if dropped else None,
            "jobs_with_a_drop": sum(1 for x in dropped if x),
            "ledger_bytes_median": statistics.median(byts) if byts else None,
            "ledger_bytes_max": max(byts) if byts else None,
            "rows": rows}


# ------------------------------------------------------------ weight hashes

def weight_hashes(d: Path, pop: dict) -> dict:
    """Leakage check: every *.safetensors under candidates/*/code hashed, pairwise
    distinctness, and the `loaded_existing_weights` flag as each candidate wrote it."""
    seen, rows = collections.defaultdict(list), []
    for cid in sorted(pop["candidates"]):
        code = d / "candidates" / cid / "code"
        if not code.is_dir():
            continue
        for w in sorted(code.glob("*.safetensors")):
            h = hashlib.sha256(w.read_bytes()).hexdigest()
            seen[h].append("%s/%s" % (cid, w.name))
            mc = jread(d / "candidates" / cid / "out" / "memory_config.json") or {}
            rows.append({"id": cid, "file": w.name, "sha256": h,
                         "bytes": w.stat().st_size,
                         "loaded_existing_weights": mc.get("loaded_existing_weights")})
    dupes = {h: v for h, v in seen.items() if len(v) > 1}
    return {"files": len(rows), "distinct_hashes": len(seen),
            "pairwise_distinct": not dupes, "duplicate_groups": dupes,
            "loaded_existing_weights_true": [r["id"] for r in rows
                                             if r["loaded_existing_weights"] is True],
            "loaded_existing_weights_false": [r["id"] for r in rows
                                              if r["loaded_existing_weights"] is False],
            "loaded_existing_weights_absent": [r["id"] for r in rows
                                               if r["loaded_existing_weights"] is None],
            "rows": rows}


# ------------------------------------------------------------- 5. throughput

def throughput(name: str, a: dict, tim: dict, slots: int) -> dict:
    settled = a["settled"]
    lease_h = (tim["lease_seconds_sum"] or 0) / 3600
    wall_h = a["wall_hours"]
    nt = tim.get("non_training_sec") or {}
    return {"arm": name, "campaign": a["campaign"], "slots": slots, "settled": settled,
            "gpu_hours_recorded": a["gpu_hours"],
            "lease_hours": round(lease_h, 3),
            "settled_per_lease_hour": round(settled / lease_h, 2) if lease_h else None,
            "wall_hours": wall_h,
            "settled_per_wall_hour": round(settled / wall_h, 2) if wall_h else None,
            "lease_sec_median": (tim.get("lease_sec") or {}).get("median"),
            "lease_sec_mean": (tim.get("lease_sec") or {}).get("mean"),
            "train_sec_median": (tim.get("train_sec") or {}).get("median"),
            "train_sec_mean": (tim.get("train_sec") or {}).get("mean"),
            "non_training_sec_median": nt.get("median"),
            "non_training_sec_mean": nt.get("mean"),
            "non_training_n": nt.get("n")}


# ------------------------------------------------------------------ markdown

fmt = dm.fmt


def render(out: dict) -> str:
    A_ = []
    A = A_.append
    arm, ctl = out["arms"]["MIXED"], out["arms"]["D4"]
    A("# mixed-model arm — mechanical read (Opus drafts, Sonnet elsewhere)\n")
    A("Generated by `scripts/mixed_mechanical.py`, read-only over every directory it "
      "was given. Search fitness is the hidden search split and is optimistic by "
      "construction; the final score is the single read `lab run` already recorded. "
      "Generated at %s.\n" % out["generated_at"])

    A("## 1. Per-arm facts\n")
    A("| measure | MIXED (`engram-mixed-w0`) | D4 control (`engram-drafts4-w0`) |")
    A("|---|---|---|")

    def row(label, key, f=lambda v: fmt(v)):
        A("| %s | %s | %s |" % (label, f(arm.get(key)), f(ctl.get(key))))

    row("campaign", "campaign")
    row("seed", "seed")
    row("started", "started")
    row("finished", "finished")
    row("stop reason", "stop_reason")
    row("candidates in the population", "candidates_total")
    row("settled", "settled")
    row("settled, non-baseline", "settled_non_baseline")
    row("exec counts", "exec_counts",
        lambda v: ", ".join("%s %d" % (k, n) for k, n in (v or {}).items()))
    row("defers", "defers")
    row("re-dispatches", "redispatches", lambda v: ", ".join(v) if v else "none")
    row("GPU-hours recorded (sum of slot leases)", "gpu_hours")
    row("wall clock (h)", "wall_hours")
    row("settled per GPU-hour (as REPORT.md states it)", "settled_per_gpu_hour")
    row("valid (completed) candidates per GPU-hour", "valid_per_gpu_hour")
    row("list-price cost, all sessions", "cost_total_usd", lambda v: "$%s" % fmt(v, 2))
    row("served models (sessions)", "served_models",
        lambda v: "; ".join("%s: %d" % (k, n) for k, n in (v or {}).items()))
    row("sessions that never started (no model served)", "sessions_never_ran",
        lambda v: ", ".join(v) if v else "none")
    row("sessions with an error flag", "sessions_with_errors",
        lambda v: ", ".join("%s (%s)" % (e["id"], e["subtype"]) for e in v) if v else "none")
    A("| turns median / mean / max | %s / %s / %s | %s / %s / %s |"
      % (fmt(arm["turns_median"]), fmt(arm["turns_mean"]), fmt(arm["turns_max"]),
         fmt(ctl["turns_median"]), fmt(ctl["turns_mean"]), fmt(ctl["turns_max"])))
    row("frozen candidate", "frozen")
    row("frozen search fitness", "frozen_search_fitness", lambda v: fmt(v, 6))
    row("final-split score (read once)", "final_score", lambda v: fmt(v, 6))
    row("claim vs the fixed 0.50, as lab recorded it", "claim_recorded")
    row("usage: pauses / seconds waiting / peak fraction", "usage",
        lambda v: "%s / %s s / %s" % (v.get("pauses"), round(v.get("waiting_seconds") or 0),
                                      v.get("peak_fraction")))
    row("usage: rate limits / deferred / hard kills", "usage",
        lambda v: "%s / %s / %s" % (v.get("rate_limits"), v.get("deferred"),
                                    v.get("hard_kills")))

    A("\n## 2. Read 1 — task claim (frozen candidate's final vs the fixed 0.50)\n")
    e = out["read1_task_claim"]
    A("| arm | frozen | final score | threshold | endpoint | pending reasons |")
    A("|---|---|---|---|---|---|")
    A("| MIXED | %s | %s | %s | **%s** | %s |"
      % (arm["frozen"], fmt(e["final_score"], 6), fmt(THRESHOLD, 2), e["claim"],
         "; ".join(e["reasons"]) or "none"))
    A("\nPending clauses, each evaluated: ended early — %s (status `%s`, stop reason "
      "`%s`); fewer than 20 settled — %s (%d settled); any session served a model other "
      "than the one requested for its operator — %s (%d worker sessions checked, "
      "mismatches: %s).\n"
      % (fmt(out["pending_checks"]["ended_early"]), arm["status"], arm["stop_reason"],
         fmt(out["pending_checks"]["fewer_than_20_settled"]), arm["settled"],
         fmt(out["pending_checks"]["model_mismatch"]),
         out["models"]["MIXED"]["sessions_checked"],
         ", ".join(out["models"]["MIXED"]["mismatches"]) or "none"))

    A("## 3. Read 2 — cost per candidate\n")
    A("| measure | MIXED | D4 control |")
    A("|---|---|---|")
    cm, cc = out["read2_cost"]["MIXED"], out["read2_cost"]["D4"]
    for label, key, f in (("worker sessions with a cost", "sessions", lambda v: fmt(v)),
                          ("settled candidates", "settled_candidates", lambda v: fmt(v)),
                          ("total, all sessions", "total_usd", lambda v: "$%s" % fmt(v, 4)),
                          ("cost per settled candidate", "per_settled_candidate_usd",
                           lambda v: "**$%s**" % fmt(v, 4))):
        A("| %s | %s | %s |" % (label, f(cm.get(key)), f(cc.get(key))))
    for label, key in (("mean", "mean"), ("median", "median"), ("min", "min"), ("max", "max")):
        A("| per-session %s | $%s | $%s |"
          % (label, fmt((cm["per_session"] or {}).get(key), 4),
             fmt((cc["per_session"] or {}).get(key), 4)))
    r = out["read2_cost"]["ratio_mixed_over_d4"]
    A("\nRatio MIXED / D4 cost per settled candidate: **%s**. The all-Opus reference "
      "does not exist (that bundle is shelved), so this read is two numbers and one "
      "ratio, as the PREREG amendment restates it.\n" % fmt(r, 4))
    A("Cost split by requested model and by operator:\n")
    A("| arm | group | sessions | total | mean | median |")
    A("|---|---|---|---|---|---|")
    for k, c in (("MIXED", cm), ("D4", cc)):
        for g, dd in list(c["by_requested_model"].items()) + list(c["by_operator"].items()):
            if not dd:
                continue
            A("| %s | %s | %d | $%s | $%s | $%s |"
              % (k, g, dd["n"], fmt(dd["total"], 4), fmt(dd["mean"], 4), fmt(dd["median"], 4)))
    A("")
    sp = out["read2_cost"]["draft_split"]
    A("The four opening drafts against the sixteen jobs that follow:\n")
    A("| arm | four drafts (model) | drafts total | drafts mean | other sessions | others total | others mean |")
    A("|---|---|---|---|---|---|---|")
    for k in ("MIXED", "D4"):
        s = sp[k]
        A("| %s | %s (%s) | $%s | $%s | %d | $%s | $%s |"
          % (k, ", ".join(s["draft_ids"]), s["draft_model"], fmt(s["drafts_total"], 4),
             fmt(s["drafts_mean"], 4), s["others_n"], fmt(s["others_total"], 4),
             fmt(s["others_mean"], 4)))

    A("\n## 4. Read 3 — final-split score beside the common threshold\n")
    A("| arm | frozen | search fitness | final split (read once) | threshold | lab's recorded claim |")
    A("|---|---|---|---|---|---|")
    for k in ("MIXED", "D4"):
        a = out["arms"][k]
        A("| %s (%s) | %s | %s | **%s** | %s | %s |"
          % (k, a["campaign"], a["frozen"], fmt(a["frozen_search_fitness"], 6),
             fmt(a["final_score"], 6), fmt(THRESHOLD, 2), a["claim_recorded"]))
    A("\nDescriptive difference MIXED − D4 on the final split: **%s**. Two single runs; "
      "descriptive only, no test.\n" % fmt(out["read3_final_gap_mixed_minus_d4"], 6))

    A("## 5. Read 4 — where the Opus money went\n")
    A("### The four opening drafts, side by side\n")
    A("| # | MIXED draft | search fitness | approach | D4 draft | search fitness | approach |")
    A("|---|---|---|---|---|---|---|")
    for i, (m, c) in enumerate(zip(out["read4_drafts"]["MIXED"],
                                   out["read4_drafts"]["D4"]), 1):
        A("| %d | %s | %s | %s | %s | %s | %s |"
          % (i, m["id"], fmt(m["fitness"], 6), m["approach"],
             c["id"], fmt(c["fitness"], 6), c["approach"]))
    A("\nBest draft: MIXED %s at %s, D4 %s at %s; drafts that beat D4's best draft: %s.\n"
      % (out["read4_drafts"]["best"]["MIXED"]["id"],
         fmt(out["read4_drafts"]["best"]["MIXED"]["fitness"], 6),
         out["read4_drafts"]["best"]["D4"]["id"],
         fmt(out["read4_drafts"]["best"]["D4"]["fitness"], 6),
         ", ".join(out["read4_drafts"]["mixed_drafts_over_d4_best"]) or "none"))
    for k in ("MIXED", "D4"):
        lin = out["lineages"][k]
        A("### %s lineages — %s\n" % (k, lin["draft_count_as_reported"]))
        A("| root | kind | members | best search fitness | ever held the running best | approach |")
        A("|---|---|---|---|---|---|")
        for rr in lin["lineages"]:
            A("| %s | %s | %d (%s) | %s | %s | %s |"
              % (rr["root"], rr["kind"], len(rr["members"]), ", ".join(rr["members"]),
                 fmt(rr["best_search_fitness"], 6), fmt(rr["ever_held_running_best"]),
                 rr["approach"]))
        A("\nFrozen %s sits in lineage %s; %d of %d improve/crossover slots (%s) went to "
          "that lineage. Distinct opening approaches: %d planned + %d via the baseline "
          "(a disguised draft = an improve of `%s`, or a crossover with `%s` as a "
          "parent). Candidates in no lineage: %s.\n"
          % (lin["frozen"], lin["frozen_lineage_root"], lin["slots_on_frozen_lineage"],
             lin["improve_crossover_slots"], fmt(lin["slots_on_frozen_lineage_fraction"]),
             lin["n_planned_drafts"], lin["n_disguised_drafts"], lin["baseline"],
             lin["baseline"], ", ".join(lin["unassigned_candidates"]) or "none"))
    A("### Search progress\n")
    A("| measure | MIXED | D4 |")
    A("|---|---|---|")
    pm, pc = out["progress"]["MIXED"], out["progress"]["D4"]
    for label, key in (("best search fitness after 4 settled", "best_after_4"),
                       ("after 8 settled", "best_after_8"),
                       ("after 20 settled", "best_after_20"),
                       ("after every settled candidate", "best_after_all")):
        A("| %s | %s | %s |" % (label, fmt(pm[key], 6), fmt(pc[key], 6)))

    A("\n## 6. The kill criterion, as fixed before launch\n")
    k = out["kill_criterion"]
    A("*Fires only if the mixed arm's cost per candidate is within 10 % of D4's "
      "**and** none of its four drafts reached a higher search fitness than D4's best "
      "draft.*\n")
    A("- Half A — cost per candidate within %d %% of D4's: MIXED $%s vs D4 $%s, "
      "relative difference **%s %%** → **%s**."
      % (int(COST_BAND * 100), fmt(k["mixed_cost_per_candidate"], 4),
         fmt(k["d4_cost_per_candidate"], 4),
         fmt(k["relative_difference_pct"], 2), fmt(k["half_a_cost_within_band"])))
    A("- Half B — no MIXED draft beat D4's best draft (%s at %s): MIXED drafts %s → "
      "**%s**."
      % (k["d4_best_draft"], fmt(k["d4_best_draft_fitness"], 6),
         ", ".join("%s %s" % (i, fmt(v, 6)) for i, v in k["mixed_drafts"]),
         fmt(k["half_b_no_draft_beat_d4_best"])))
    A("- **The criterion fires: %s.**\n" % fmt(k["fires"]))

    A("## 7. Requested vs served model, per session and per operator\n")
    for key in ("MIXED", "D4"):
        m = out["models"][key]
        A("### %s\n" % key)
        A("| operator | requested → served | sessions |")
        A("|---|---|---|")
        for op, ctr in m["by_operator"].items():
            for combo, n in ctr.items():
                A("| %s | %s | %d |" % (op, combo, n))
        A("\nWorker sessions checked: %d; mismatches: %s; `%s` served alongside the "
          "requested model in %d sessions (it is the harness's quick model, not a worker "
          "model, and appears in every session of both arms).\n"
          % (m["sessions_checked"], ", ".join(m["mismatches"]) or "none", HAIKU,
             m["haiku_alongside"]))

    A("## 8. Coverage under findings-v2\n")
    for key in ("MIXED", "D4"):
        c = out["coverage"][key]
        A("- **%s**: %d jobs with cards; parent violations %d %s; jobs with fewer than "
          "two out-of-lineage cards once ≥ 4 cards had **ended** before dispatch: %d %s "
          "(baseline card not counted), %d %s (baseline counted)."
          % (key, c["jobs"], len(c["parent_violations"]), c["parent_violations"] or "",
             len(c["cross_branch_violations_baseline_excluded"]),
             c["cross_branch_violations_baseline_excluded"],
             len(c["cross_branch_violations_baseline_counted"]),
             c["cross_branch_violations_baseline_counted"]))
        for v in c["violation_detail"]:
            A("    - %s: cards %s; non-baseline out-of-lineage cards that existed at "
              "dispatch: %d (a second one existed: %s)"
              % (v["job"], v["cards"], v["out_of_lineage_cards_available_at_dispatch"],
                 fmt(v["second_out_of_lineage_card_existed"])))

    A("\n## 9. The knob ledger\n")
    A("| measure | MIXED | D4 |")
    A("|---|---|---|")
    lm, lc = out["ledger"]["MIXED"], out["ledger"]["D4"]
    for label, key in (("knobs file", "knobs_file"),
                       ("ledger byte bound", "ledger_max_bytes"),
                       ("settled non-baseline candidates", "settled_non_baseline"),
                       ("candidates that wrote the knobs file",
                        "candidates_that_wrote_the_knobs_file"),
                       ("jobs whose card pack carried a ledger", "jobs_with_a_ledger"),
                       ("ledger rows carried, total", "rows_carried_total"),
                       ("ledger rows carried, median / max", "rows_carried_median"),
                       ("ledger rows dropped by the bound, total", "rows_dropped_total"),
                       ("jobs with at least one dropped row", "jobs_with_a_drop"),
                       ("ledger bytes, median / max", "ledger_bytes_median")):
        if key == "rows_carried_median":
            A("| %s | %s / %s | %s / %s |" % (label, fmt(lm["rows_carried_median"]),
                                              fmt(lm["rows_carried_max"]),
                                              fmt(lc["rows_carried_median"]),
                                              fmt(lc["rows_carried_max"])))
        elif key == "ledger_bytes_median":
            A("| %s | %s / %s | %s / %s |" % (label, fmt(lm["ledger_bytes_median"]),
                                              fmt(lm["ledger_bytes_max"]),
                                              fmt(lc["ledger_bytes_median"]),
                                              fmt(lc["ledger_bytes_max"])))
        else:
            A("| %s | %s | %s |" % (label, fmt(lm.get(key)), fmt(lc.get(key))))
    A("\nPer-job ledger rows (MIXED): %s\n"
      % "; ".join("%s %d carried / %d dropped" % (r["job"], r["rows"],
                                                  r["dropped_by_the_bound"])
                  for r in lm["rows"]))

    A("## 10. GPU covariate\n")
    for key in ("MIXED", "D4"):
        g = out["gpu"][key]
        A("### %s\n" % key)
        A("| GPU | candidates | best search fitness | mean lease (min) | median lease (min) |")
        A("|---|---|---|---|---|")
        for gid, v in g["per_gpu"].items():
            A("| %s | %d (%s) | %s | %s | %s |"
              % (gid, v["n"], ", ".join(v["candidates"]),
                 fmt(v["best_search_fitness"], 6), fmt(v["mean_lease_min"]),
                 fmt(v["median_lease_min"])))
        A("\nLineage roots by GPU: %s. Frozen %s on GPU %s.\n"
          % (", ".join("%s→GPU %s" % (a, b)
                       for a, b in g["gpu_of_each_lineage_root"].items()),
             g["frozen"], g["frozen_gpu"]))

    A("## 11. The two-slot throughput read (reported only, no threshold)\n")
    A("| arm | slots | settled | lease-hours | settled / lease-hour | wall (h) | "
      "settled / wall-hour | lease s (median/mean) | training s (median/mean) | "
      "lease − training s (median/mean) |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for t in out["throughput"]:
        A("| %s (%s) | %d | %d | %s | **%s** | %s | **%s** | %s / %s | %s / %s | %s / %s |"
          % (t["campaign"], t["arm"], t["slots"], t["settled"], fmt(t["lease_hours"]),
             fmt(t["settled_per_lease_hour"]), fmt(t["wall_hours"]),
             fmt(t["settled_per_wall_hour"]), fmt(t["lease_sec_median"]),
             fmt(t["lease_sec_mean"]), fmt(t["train_sec_median"]),
             fmt(t["train_sec_mean"]), fmt(t["non_training_sec_median"]),
             fmt(t["non_training_sec_mean"])))
    A("\nTraining seconds are the values the candidates recorded themselves; the key "
      "differs by arm (%s). `gpu_seconds` minus the sum of leases, per arm: %s.\n"
      % ("; ".join("%s: %s" % (n, out["timing"][n].get("train_sec_keys_used"))
                   for n in out["timing"]),
         "; ".join("%s %s s" % (n, fmt(out["timing"][n]["gpu_seconds_minus_lease_sum"]))
                   for n in out["timing"])))
    A("Slot occupancy and concurrency:\n")
    A("| measure | " + " | ".join(out["timing_names"]) + " |")
    A("|---" * (1 + len(out["timing_names"])) + "|")
    for label, key in (("sum of leases (s)", "lease_seconds_sum"),
                       ("gpu_seconds recorded", "gpu_seconds_recorded"),
                       ("campaign wall clock (s)", "wall_seconds"),
                       ("seconds with a lease open (union)", "lease_union_seconds"),
                       ("seconds with two leases open", "two_leases_open_seconds"),
                       ("two-lease fraction of wall", "two_leases_open_fraction_of_wall"),
                       ("slot occupancy = leases / (2 × wall)",
                        "slot_occupancy_leases_over_2x_wall"),
                       ("seconds waiting on usage", "usage_waiting_seconds"),
                       ("usage pauses", "usage_pauses"),
                       ("turns per session, median", None)):
        if key is None:
            A("| %s | %s |" % (label, " | ".join(
                fmt((out["timing"][n].get("turns") or {}).get("median"))
                for n in out["timing_names"])))
        else:
            A("| %s | %s |" % (label, " | ".join(fmt(out["timing"][n].get(key))
                                                 for n in out["timing_names"])))

    A("\n## 12. Leakage checks\n")
    for name in out["timing_names"]:
        w = out["weights"].get(name)
        h = out["weight_hashes"].get(name)
        if not w or not h:
            continue
        A("- **%s**: %d weight files checked for freshness; files not postdating their "
          "candidate's dispatch or its oldest code file: %s. %d files hashed, %d "
          "distinct — pairwise distinct: **%s**%s. `loaded_existing_weights`: true in "
          "%s; false in %s; key absent in %d files."
          % (name, w["checked"], w["violations"] or "none", h["files"],
             h["distinct_hashes"], fmt(h["pairwise_distinct"]),
             "" if h["pairwise_distinct"] else " — duplicates: %s" % h["duplicate_groups"],
             ", ".join(h["loaded_existing_weights_true"]) or "none",
             ", ".join(h["loaded_existing_weights_false"]) or "none",
             len(h["loaded_existing_weights_absent"])))
    A("\nA candidate whose code never writes the key is counted under “absent”, which is "
      "not the same as writing `false`.\n")
    A("Largest single-step jumps in search fitness (parent → child), for the "
      "“explain any suspicious jump from the code” check:\n")
    A("| arm | child | operator | parents | parent best fitness | child fitness | jump |")
    A("|---|---|---|---|---|---|---|")
    for j in out["jumps"]:
        A("| %s | %s | %s | %s | %s | %s | **%s** |"
          % (j["arm"], j["id"], j["operator"], ", ".join(j["parents"]) or "—",
             fmt(j["parent_fitness"], 6), fmt(j["fitness"], 6), fmt(j["jump"], 6)))

    A("\n## 13. Session anomalies\n")
    for name in out["timing_names"]:
        s = out["session_anomalies"].get(name)
        if not s:
            continue
        A("- **%s** (worker_max_turns %s): %d denied tool calls in %d sessions (%s); "
          "sessions over the turn cap: %s; non-empty session.stderr: %s."
          % (name, fmt(s["worker_max_turns"]), s["permission_denials_total"],
             len(s["permission_denials_by_candidate"]),
             ", ".join(s["permission_denials_by_candidate"]) or "none",
             ", ".join("%s (%d turns)" % (o["id"], o["turns"])
                       for o in s["sessions_over_turn_cap"]) or "none",
             "; ".join("%d × “%s”" % (len(v), kk)
                       for kk, v in s["session_stderr_first_lines"].items()) or "none"))
    return "\n".join(A_) + "\n"


# ----------------------------------------------------------------------- main

def draft_rows(d: Path, pop: dict) -> list:
    c = pop["candidates"]
    return [{"id": i, "fitness": c[i].get("fitness"), "gpu": c[i].get("gpu"),
             "approach": dm.approach_line(d, i)}
            for i in sorted(c) if c[i].get("operator") == "draft"]


def split_costs(cost: dict, drafts: list) -> dict:
    ids = {r["id"] for r in drafts}
    dr = [r for r in cost["rows"] if r["id"] in ids
          and isinstance(r["total_cost_usd"], (int, float))]
    ot = [r for r in cost["rows"] if r["id"] not in ids
          and isinstance(r["total_cost_usd"], (int, float))]
    return {"draft_ids": [r["id"] for r in dr],
            "draft_model": dr[0]["requested_model"] if dr else None,
            "drafts_n": len(dr),
            "drafts_total": round(sum(r["total_cost_usd"] for r in dr), 4),
            "drafts_mean": round(statistics.mean([r["total_cost_usd"] for r in dr]), 4) if dr else None,
            "others_n": len(ot),
            "others_total": round(sum(r["total_cost_usd"] for r in ot), 4),
            "others_mean": round(statistics.mean([r["total_cost_usd"] for r in ot]), 4) if ot else None}


def jumps(name: str, pop: dict, top: int = 3) -> list:
    c = pop["candidates"]
    rows = []
    for cid in sorted(c):
        par = c[cid].get("parents") or []
        f = c[cid].get("fitness")
        pf = max([c[p].get("fitness") for p in par
                  if isinstance(c.get(p, {}).get("fitness"), (int, float))], default=None)
        if isinstance(f, (int, float)):
            rows.append({"arm": name, "id": cid, "operator": c[cid].get("operator"),
                         "parents": par, "fitness": f, "parent_fitness": pf,
                         "jump": (f - pf) if pf is not None else None})
    rows = [r for r in rows if r["jump"] is not None]
    rows.sort(key=lambda r: -r["jump"])
    return rows[:top]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True, type=Path, help="the mixed-model arm")
    ap.add_argument("--control", required=True, type=Path, help="the all-Sonnet D4 control")
    ap.add_argument("--ref", type=Path, action="append", default=[],
                    help="single-GPU reference arm for the throughput read (repeatable)")
    ap.add_argument("--md", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    arms = {"MIXED": arm_facts(args.arm), "D4": arm_facts(args.control)}
    refs = [arm_facts(p) for p in args.ref]
    pops = {k: arms[k].pop("_pop") for k in arms}
    dirs = {"MIXED": args.arm, "D4": args.control}
    for r, p in zip(refs, args.ref):
        pops[r["campaign"]] = r.pop("_pop")
        dirs[r["campaign"]] = p
    for k in list(arms) + [r["campaign"] for r in refs]:
        a = arms.get(k) or next(r for r in refs if r["campaign"] == k)
        gh = (a["gpu_seconds"] or 0) / 3600
        a["valid_per_gpu_hour"] = (round((a["exec_counts"].get("completed") or 0) / gh, 2)
                                   if gh else None)

    models = {k: model_check(dirs[k], pops[k]) for k in ("MIXED", "D4")}
    ep = endpoint_mixed(arms["MIXED"], models["MIXED"])
    lin = {k: lineages(dirs[k], pops[k]) for k in ("MIXED", "D4")}
    cost = {k: costs(dirs[k], pops[k]) for k in ("MIXED", "D4")}
    drafts = {k: draft_rows(dirs[k], pops[k]) for k in ("MIXED", "D4")}

    def best(rows):
        return max(rows, key=lambda r: r["fitness"] if r["fitness"] is not None else -1)

    d4_best = best(drafts["D4"])
    over = [r["id"] for r in drafts["MIXED"]
            if r["fitness"] is not None and d4_best["fitness"] is not None
            and r["fitness"] > d4_best["fitness"]]

    cm = cost["MIXED"]["per_settled_candidate_usd"]
    cc = cost["D4"]["per_settled_candidate_usd"]
    rel = abs(cm - cc) / cc if (cm is not None and cc) else None
    half_a = bool(rel is not None and rel <= COST_BAND)
    half_b = not over
    kill = {"mixed_cost_per_candidate": cm, "d4_cost_per_candidate": cc,
            "band": COST_BAND,
            "relative_difference": round(rel, 6) if rel is not None else None,
            "relative_difference_pct": round(rel * 100, 4) if rel is not None else None,
            "half_a_cost_within_band": half_a,
            "d4_best_draft": d4_best["id"], "d4_best_draft_fitness": d4_best["fitness"],
            "mixed_drafts": [(r["id"], r["fitness"]) for r in drafts["MIXED"]],
            "mixed_drafts_over_d4_best": over,
            "half_b_no_draft_beat_d4_best": half_b,
            "fires": bool(half_a and half_b)}

    tim = {k: timing(dirs[k], pops[k]) for k in pops}
    names = ["MIXED", "D4"] + [r["campaign"] for r in refs]
    all_arms = {"MIXED": arms["MIXED"], "D4": arms["D4"]}
    all_arms.update({r["campaign"]: r for r in refs})
    slots = {"MIXED": 2, "D4": 2}
    thr = [throughput(n, all_arms[n], tim[n], slots.get(n, 1)) for n in names]

    fm, fc = arms["MIXED"]["final_score"], arms["D4"]["final_score"]
    out = {
        "generated_by": "scripts/mixed_mechanical.py",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "threshold": THRESHOLD, "cost_band": COST_BAND,
        "dirs": {k: str(v) for k, v in dirs.items()},
        "arms": arms, "references": refs,
        "models": models,
        "read1_task_claim": ep,
        "pending_checks": {
            "ended_early": not (arms["MIXED"]["status"] == "finished"
                                and "max_candidates" in str(arms["MIXED"]["stop_reason"])),
            "fewer_than_20_settled": arms["MIXED"]["settled"] < 20,
            "model_mismatch": bool(models["MIXED"]["mismatches"])},
        "read2_cost": {"MIXED": cost["MIXED"], "D4": cost["D4"],
                       "ratio_mixed_over_d4": (round(cm / cc, 4) if cm and cc else None),
                       "draft_split": {k: split_costs(cost[k], drafts[k])
                                       for k in ("MIXED", "D4")}},
        "read3_final_gap_mixed_minus_d4": ((fm - fc) if (fm is not None and fc is not None)
                                           else None),
        "read4_drafts": {"MIXED": drafts["MIXED"], "D4": drafts["D4"],
                         "best": {"MIXED": best(drafts["MIXED"]), "D4": d4_best},
                         "mixed_drafts_over_d4_best": over},
        "kill_criterion": kill,
        "lineages": lin,
        "progress": {"MIXED": progress(pops["MIXED"], fc),
                     "D4": progress(pops["D4"], fm)},
        "coverage": {k: coverage(dirs[k], pops[k]) for k in ("MIXED", "D4")},
        "ledger": {k: ledger(dirs[k], pops[k]) for k in ("MIXED", "D4")},
        "gpu": {k: gpu_covariate(pops[k], lin[k]) for k in ("MIXED", "D4")},
        "timing": tim, "timing_names": names,
        "throughput": thr,
        "session_anomalies": {k: session_anomalies(dirs[k], pops[k]) for k in pops},
        "weights": {k: weight_checks(dirs[k], pops[k]) for k in pops},
        "weight_hashes": {k: weight_hashes(dirs[k], pops[k]) for k in pops},
        "jumps": jumps("MIXED", pops["MIXED"]) + jumps("D4", pops["D4"]),
    }

    text = render(out)
    print(text)
    if args.md:
        args.md.write_text(text)
    if args.json:
        args.json.write_text(json.dumps(out, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
