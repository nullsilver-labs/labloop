#!/usr/bin/env python3
"""Zero-GPU evaluation of `lab index` (docs/experiment-index-plan.md §4).

  replay      for every rated-wrong statement of the mem2 and mem3 pairs that a lookup could
              have prevented: build the index of that arm *as of the stating worker's launch*
              and run the query the index instruction asks for (the knob it names, the
              candidate it names, `best`, or a search for the idea). Reachable = the
              contradicting candidate (and value) is in what comes back.
  paraphrase  free-text probes written from the cards by a session that never ran a search
              (probes JSON: query, difficulty, target, expected[]). recall@5 = any expected
              id in the top 5; MRR over the first expected id. Lexical, vector and hybrid
              when the fixture was built with --embed-url (scripts/index_fixture.sh passes it on).
  latency     p50 / p95 of search and knob over the fixture.

usage: index_probes.py replay | paraphrase FIXTURE.sqlite3 PROBES.json [--stem-fixture F] [--misses] | latency FIXTURE.sqlite3
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace as NS

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tools"))
import lab_index as I  # noqa: E402

UP = HERE.parent
ARMS = {"mem2L": UP / "labloop-mem2-legacy-20260914", "mem2F": UP / "labloop-mem2-findings-20260914",
        "mem3F": UP / "labloop-mem3-findings-20260915", "mem3L": UP / "labloop-mem3-legacy-20260915"}

# (arm, statement # in that pair's ratings file, stating candidate, what it got wrong,
#  [queries the instruction would have it run], ids that contradict it, value that must show)
REPLAY = [
    ("mem2L", 153, "c0012", "dropout past 0.4 never tested", [("knob", "dropout_p")], ["c0005"], "0.6"),
    ("mem2L", 184, "c0015", "small table only tested up to 0.4", [("knob", "dropout_p")], ["c0005"], "0.6"),
    ("mem2L", 187, "c0015", "this 520k-row table (it is 500,000)", [("open", "c0012")], ["c0012"], "500000"),
    ("mem2L", 120, "c0009", "higher than every held-out value in the lineage", [("lineage", "c0009"), ("open", "c0002")], ["c0002"], "0.5034"),
    ("mem2F", 33, "c0005", "c0003 has 14.1M trainable params", [("open", "c0003")], ["c0003"], "15166720"),
    ("mem2F", 45, "c0006", "double c0003's 14.1M", [("open", "c0003")], ["c0003"], "15166720"),
    ("mem2F", 54, "c0006", "previous best held-out was c0001's", [("open", "c0002")], ["c0002"], "0.87"),
    ("mem2F", 67, "c0008", "orders never varied from [1]", [("knob", "orders"), ("search", "n-gram orders")], ["c0001", "c0002"], None),
    ("mem2F", 69, "c0008", "first to pass --orders 1 2", [("knob", "orders"), ("search", "orders 1 2 bigram")], ["c0002"], None),
    ("mem2F", 133, "c0014", "every 540 s run used heads=8", [("knob", "train_seconds"), ("knob", "heads")], ["c0011"], None),
    ("mem2F", 148, "c0015", "c0009 vs c0003 is seed-only", [("open", "c0009")], ["c0009"], "weight_decay"),
    ("mem2F", 160, "c0017", "layer 4 the only other depth point", [("knob", "attach_layer")], ["c0007"], "6"),
    ("mem2F", 186, "c0019", "weight_decay never varied", [("knob", "weight_decay")], ["c0009", "c0014"], "0.01"),
    ("mem2F", 187, "c0019", "batch_size explored in both directions", [("knob", "batch_size")], ["c0016"], None),
    ("mem3F", 43, "c0005", "previous table sizes were not recorded", [("knob", "table_rows")], ["c0001"], None),
    ("mem3F", 76, "c0008", "same 262144-ish tables as c0001", [("open", "c0001"), ("knob", "table_rows")], ["c0001"], "50000"),
    ("mem3F", 99, "c0009", "c0001-c0006 all below 0.26 search", [("best",)], ["c0003", "c0005"], None),
    ("mem3F", 133, "c0011", "table_rows only recorded for c0005", [("knob", "table_rows")], ["c0001"], None),
    ("mem3F", 178, "c0016", "c0009 was on free-form decoding", [("open", "c0009"), ("knob", "decoding")], ["c0009"], "closed_vocab"),
    ("mem3F", 190, "c0017", "closed-vocab held-out runs 0.79-0.85", [("knob", "decoding", "holdout_wording_acc")], ["c0014"], "0.69"),
    ("mem3L", 53, "c0006", "c0002 is the best in the population", [("best",)], ["c0005"], None),
    ("mem3L", 94, "c0009", "parent c0005 best so far", [("best",)], ["c0008"], None),
    ("mem3L", 109, "c0010", "c0008 best in the population", [("best",)], ["c0009"], None),
    ("mem3L", 128, "c0011", "c0008 best in the population", [("best",)], ["c0009"], None),
    ("mem3L", 123, "c0010", "best held-out with the entity channel", [("search", "entity channel held-out accuracy")], ["c0009"], None),
    ("mem3L", 186, "c0014", "c0002 best among decay variants", [("knob", "weight_decay"), ("knob", "table_weight_decay")], ["c0008"], None),
    ("mem3L", 229, "c0017", "c0009's steps not available", [("open", "c0009")], ["c0009"], "4181"),
    ("mem3L", 73, "c0007", "c0005 ran 4252 steps (4255)", [("open", "c0005")], ["c0005"], "4255"),
    ("mem3L", 181, "c0014", "c0006 final loss 0.0012 (0.00094)", [("open", "c0006")], ["c0006"], "0.0009"),
]


def run(con, q: tuple) -> tuple[str, list[str]]:
    cmd, *rest = q
    a = {"search": lambda: NS(query=rest[0], limit=10, field=None), "knob": lambda: NS(key=rest[0], with_key=(rest[1] if len(rest) > 1 else None)),
         "open": lambda: NS(candidate=rest[0]), "lineage": lambda: NS(candidate=rest[0]),
         "best": lambda: NS(outside=None, limit=5), "knobs": lambda: NS()}[cmd]()
    lines, ids = getattr(I, f"q_{cmd}")(con, a)
    return "\n".join(lines), ids


def replay() -> None:
    tmp = Path(tempfile.mkdtemp())
    rows, ok = [], 0
    for arm, num, who, claim, queries, want_ids, want_val in REPLAY:
        pop = json.loads((ARMS[arm] / "population.json").read_text())
        launched = pop["candidates"][who]["launched"]
        db = tmp / f"{arm}-{who}.sqlite3"
        I.build(db, [("", ARMS[arm])], as_of=launched)
        con = I.connect(db)
        text, ids = "", []
        for q in queries:
            t, i = run(con, q)
            text += t + "\n"
            ids += i
        in_index = [w for w in want_ids if I._cand(con, w) is not None]
        found = bool(in_index) and all(w in text for w in in_index) and (want_val is None or want_val in text)
        verdict = "reachable" if found else ("not settled at launch" if not in_index else "NOT reachable")
        ok += found
        rows.append((arm, num, who, claim, " ; ".join(" ".join(q) for q in queries), verdict, len(text.encode())))
    print("| arm | # | by | the error | queries | verdict | bytes returned |\n|---|---|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    unsettled = sum(r[5] == "not settled at launch" for r in rows)
    print(f"\nreachable {ok} of {len(rows)}; {unsettled} could not have been known at launch; "
          f"{len(rows) - ok - unsettled} not reachable by the asked query")


def paraphrase(a) -> None:
    """Every system is `lab index`'s own search path: lexical, vector and auto (hybrid when the
    fixture was built with an embedder and it answers)."""
    probes = json.loads(Path(a.probes).read_text())
    ranked: dict[str, list[list[str]]] = {}
    con = I.connect(Path(a.fixture))
    has_vec = bool((con.execute("SELECT value FROM meta WHERE key='embedder'").fetchone() or [""])[0])
    for mode in ("lexical", "vector", "auto") if has_vec else ("lexical",):
        how, lists, t0 = "", [], time.time()
        for p in probes:
            hits, how = I.search(con, p["query"], 50, None, mode)
            lists.append([h["id"] for h in hits])
        ranked[how] = lists
        print(f"{how}: {(time.time() - t0) / len(probes) * 1000:.0f} ms per query")
    if a.stem_fixture:
        cs = I.connect(Path(a.stem_fixture))
        ranked["lexical + porter"] = [[h["id"] for h in I.lexical(cs, p["query"], 50)] for p in probes]
    print("| system | probes | recall@1 | recall@5 | recall@10 | MRR |\n|---|---|---|---|---|---|")
    for name, lists in ranked.items():
        for label, sel in (("all", None), ("easy", "easy"), ("hard", "hard")):
            idx = [i for i, p in enumerate(probes) if sel is None or p["difficulty"] == sel]
            def first(i):
                exp = set(probes[i]["expected"]) | {probes[i]["target"]}
                return next((r + 1 for r, c in enumerate(lists[i]) if c in exp), None)
            fr = [first(i) for i in idx]
            rec = lambda k: sum(1 for r in fr if r and r <= k) / len(idx)
            print(f"| {name} | {label} ({len(idx)}) | {rec(1):.2f} | {rec(5):.2f} | {rec(10):.2f} | "
                  f"{statistics.mean(1 / r if r else 0 for r in fr):.2f} |")
    if a.misses:
        base = list(ranked)[-1]
        for i, p in enumerate(probes):
            exp = set(p["expected"]) | {p["target"]}
            if not any(c in exp for c in ranked[base][i][:5]):
                print(f"miss [{base}] {p['difficulty']}: {p['query']!r} → wanted {sorted(exp)[:4]}, got {ranked[base][i][:5]}")


def latency(a) -> None:
    con = I.connect(Path(a.fixture))
    qs = ["closed vocabulary scoring over known answers", "weight decay on the embedding table only",
          "attach the memory at a later decoder block", "entity identity channel", "dropout schedule"]
    keys = [r[0] for r in con.execute("SELECT DISTINCT key FROM knobs")]
    for name, fn in (("search", lambda i: I.lexical(con, qs[i % len(qs)], 10)),
                     ("knob", lambda i: I.q_knob(con, NS(key=keys[i % len(keys)], with_key=None)))):
        ts = []
        for i in range(300):
            t0 = time.perf_counter()
            fn(i)
            ts.append((time.perf_counter() - t0) * 1000)
        ts.sort()
        print(f"{name}: p50 {ts[150]:.2f} ms, p95 {ts[285]:.2f} ms")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("replay")
    p = sub.add_parser("paraphrase")
    p.add_argument("fixture")
    p.add_argument("probes")
    p.add_argument("--stem-fixture")
    p.add_argument("--misses", action="store_true")
    l = sub.add_parser("latency")
    l.add_argument("fixture")
    a = ap.parse_args()
    {"replay": lambda: replay(), "paraphrase": lambda: paraphrase(a), "latency": lambda: latency(a)}[a.cmd]()
