#!/usr/bin/env python3
"""Resource-matched comparison of two campaign arms, as preregistered.

Read-only. Implements the "Primary resource-matched comparison" section of the
matched-pair PROTOCOL.md (labloop-m2-matched-20260912): candidate leases are
reconstructed from finished watcher records (start/end timestamps, integer
seconds), accumulated in chronological lease order (candidate id breaks ties),
B = min(cap, A, G), and each arm's best is the best completed, scored candidate
whose cumulative lease is <= B. No proration, no estimates for missing intervals.

    scripts/matched_compare.py SEARCH_ROOT GREEDY_ROOT [--cap-seconds 43200]
                               [--band 0.004] [--json]

An arm whose population.json is not `finished` is reported as PROVISIONAL: its
total is what it has spent so far, so B and D can still move.
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_arm(root):
    pop = json.load(open(os.path.join(root, "population.json")))
    cands = pop["candidates"]
    if isinstance(cands, dict):
        cands = list(cands.values())
    records = {}
    for path in glob.glob(os.path.join(root, ".lab", "watch", "done", "*.json")):
        r = json.load(open(path))
        records[r["id"]] = r
    for path in glob.glob(os.path.join(root, ".lab", "watch", "*.json")):
        r = json.load(open(path))
        records.setdefault(r["id"], r)
    rows, missing, running = [], [], []
    for c in cands:
        w = records.get(c.get("watch") or "")
        if w and w.get("status") == "running":
            running.append(c["id"])
            continue
        if not w or not w.get("started") or not w.get("ended"):
            missing.append(c["id"])
            continue
        lease = int((ts(w["ended"]) - ts(w["started"])).total_seconds())
        rows.append(
            dict(
                id=c["id"],
                operator=c["operator"],
                exec=c.get("exec"),
                fitness=c.get("fitness"),
                started=w["started"],
                ended=w["ended"],
                lease=lease,
                defers=c.get("defers", 0),
                watch_status=w.get("status"),
                kill_reason=w.get("kill_reason"),
                models=(c.get("session") or {}).get("models") or [],
            )
        )
    rows.sort(key=lambda r: (r["started"], r["id"]))
    cum = 0
    for r in rows:
        cum += r["lease"]
        r["cum"] = cum
    # Circuit counters, per PROTOCOL.md, over terminal learned settlements in order.
    failures = deferrals = 0
    max_fail = max_defer = 0
    for r in rows:
        if r["operator"] == "baseline":
            continue
        if r["exec"] == "completed":
            failures = deferrals = 0
        elif r["exec"] == "deferred":
            deferrals += 1
        else:
            failures += 1
        max_fail, max_defer = max(max_fail, failures), max(max_defer, deferrals)
    final = pop.get("final") or {}
    final_lease = None
    if final.get("started") and final.get("ended"):
        final_lease = int((ts(final["ended"]) - ts(final["started"])).total_seconds())
    return dict(
        root=root,
        campaign=pop.get("campaign"),
        status=pop.get("status"),
        rows=rows,
        missing=missing,
        running=running,
        total=cum,
        pop_gpu_seconds=pop.get("gpu_seconds"),
        stop_reason=pop.get("stop_reason"),
        final=final,
        final_lease=final_lease,
        claim=pop.get("claim"),
        wall_h=(
            (ts(pop["finished"]) - ts(pop["started"])).total_seconds() / 3600
            if pop.get("finished")
            else None
        ),
        circuit=dict(max_failures=max_fail, max_deferrals=max_defer),
        models=sorted({m for r in rows for m in r["models"]}),
        main_model_missing=[r["id"] for r in rows if r["models"] and "claude-sonnet-5" not in r["models"]],
    )


def cut(arm, B):
    best = last = last_attempt = None
    crossing, beyond = None, []
    for r in arm["rows"]:
        if r["cum"] <= B:
            last_attempt = r
            if r["exec"] == "completed" and r["fitness"] is not None:
                last = r
                if best is None or r["fitness"] > best["fitness"]:
                    best = r
        elif crossing is None and r["cum"] - r["lease"] < B:
            crossing = r
        else:
            beyond.append(r)
    return dict(best=best, last_scored=last, last_attempt=last_attempt, crossing=crossing, beyond=beyond)


def fmt(r):
    if not r:
        return "—"
    return f"{r['id']} ({r['operator']}) {r['fitness']} at cum {r['cum']} s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("search_root")
    ap.add_argument("greedy_root")
    ap.add_argument("--cap-seconds", type=int, default=43200)
    ap.add_argument("--band", type=float, default=0.004)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    S, G = load_arm(a.search_root), load_arm(a.greedy_root)
    provisional = S["status"] != "finished" or G["status"] != "finished"
    inconclusive = []
    for arm, name in ((S, "search"), (G, "greedy")):
        if arm["missing"]:
            inconclusive.append(f"{name}: no complete watcher interval for {', '.join(arm['missing'])}")
        if arm["circuit"]["max_failures"] >= 3 or arm["circuit"]["max_deferrals"] >= 3:
            inconclusive.append(f"{name}: circuit counter reached 3")
    B = min(a.cap_seconds, S["total"], G["total"])
    cs, cg = cut(S, B), cut(G, B)
    D = None
    if cs["best"] and cg["best"]:
        D = round(cs["best"]["fitness"] - cg["best"]["fitness"], 6)
        verdict = (
            "search advantage" if D > a.band else "greedy advantage" if D < -a.band else "within practical tie band"
        )
    else:
        verdict = "inconclusive: an arm has no eligible scored candidate"
        inconclusive.append(verdict)
    out = dict(
        provisional=provisional,
        inconclusive=inconclusive,
        cap_seconds=a.cap_seconds,
        band=a.band,
        A=S["total"],
        G=G["total"],
        B=B,
        D=D,
        verdict=verdict,
        search=dict(campaign=S["campaign"], status=S["status"], **{k: v for k, v in cs.items()}),
        greedy=dict(campaign=G["campaign"], status=G["status"], **{k: v for k, v in cg.items()}),
        arms={n: {k: v for k, v in arm.items() if k != "rows"} for n, arm in (("search", S), ("greedy", G))},
    )
    if a.json:
        json.dump(out, sys.stdout, indent=1, default=str)
        return

    print("# Resource-matched comparison" + ("  — PROVISIONAL (an arm is not finished)" if provisional else ""))
    print()
    print(f"cap {a.cap_seconds} s; A (search) {S['total']} s; G (greedy) {G['total']} s; **B = {B} s** ({B/3600:.3f} h)")
    print(f"tie band ±{a.band}")
    print()
    for name, arm, c in (("search", S, cs), ("greedy", G, cg)):
        print(f"## {name}: {arm['campaign']} [{arm['status']}]")
        print(f"- best eligible: {fmt(c['best'])}")
        print(f"- last eligible scored completion: {fmt(c['last_scored'])}" + (f"; unused gap B − cum = {B - c['last_scored']['cum']} s" if c["last_scored"] else ""))
        if c["last_attempt"] and (not c["last_scored"] or c["last_attempt"]["id"] != c["last_scored"]["id"]):
            print(f"- last whole attempt at B: {c['last_attempt']['id']} cum {c['last_attempt']['cum']} s; gap {B - c['last_attempt']['cum']} s")
        if c["crossing"]:
            r = c["crossing"]
            print(f"- excluded crossing candidate: {r['id']} {r['started']}→{r['ended']} ({r['lease']} s, cum {r['cum']} s) fitness {r['fitness']}")
        if c["beyond"]:
            print(f"- beyond B: {', '.join(f'{r['id']}={r['fitness']}' for r in c['beyond'])}")
        print(f"- candidate lease total {arm['total']} s (population gpu_seconds {arm['pop_gpu_seconds']}); rows {len(arm['rows'])}; missing intervals {arm['missing'] or 'none'}; still running {arm['running'] or 'none'}")
        print(f"- circuit: max learned failures in a row {arm['circuit']['max_failures']}, max deferrals {arm['circuit']['max_deferrals']}")
        print(f"- served models seen: {', '.join(arm['models'])}; sessions without sonnet-5: {arm['main_model_missing'] or 'none'}")
        if arm["final"]:
            f = arm["final"]
            print(f"- final (separate, not part of B): {f.get('candidate')} score {f.get('score')} n {f.get('n')}, lease {arm['final_lease']} s; claim {arm['claim']}")
        if arm["wall_h"] is not None:
            print(f"- wall {arm['wall_h']:.2f} h; stop reason: {arm['stop_reason']}")
        print()
    print(f"## D = search_best(B) − greedy_best(B) = {D}  →  **{verdict}**")
    if inconclusive:
        print()
        print("INCONCLUSIVE per protocol: " + "; ".join(inconclusive))
    if provisional:
        print()
        print("Provisional: B is the running arm's spend so far; rerun when both REPORT.md files exist.")


if __name__ == "__main__":
    main()
