"""No-spend discovery demonstrator. Not a live-worker or authorization boundary.

Only a fixed scripted worker and pure local evaluator are available. Private
SQLite state is deliberately separate from the legacy public research format.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import time

BASE_COMMIT = "992c2f4b921fb82e9f6d2b6657fc98ce03a4f595"
MISSION = {
    "objective": "Reduce squared error against y=x*x on a synthetic integer grid",
    "evaluator": "square-grid-v1",
    "inputs": [-3, -2, -1, 0, 1, 2, 3],
    "baseline": "constant-zero",
    "seed": 0,
    "candidate_limit": 2,
    "slice_limit": 2,
    "mode": "exploration_only",
    "confirmation": "none; all results are synthetic and unconfirmed",
}
CANDIDATES = ("constant-zero", "square")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@contextmanager
def transaction(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.rollback()
        raise
    else:
        db.commit()


def event(db, key, kind, payload):
    # Keys identify logical transitions, not attempts to export them.
    db.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?)",
               (key, time.time(), kind, json.dumps(payload, sort_keys=True)))


def initialize(directory, wait_seconds=60, wall_seconds=3600):
    if not 0 <= wait_seconds <= 86400 or not 1 <= wall_seconds <= 604800:
        raise ValueError("wait must be 0..86400s and wall limit 1..604800s")
    directory = Path(directory)
    # Exclusive creation prevents accidental reset of evidence or spending.
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    db = sqlite3.connect(directory / "demo.sqlite3", isolation_level=None)
    try:
        db.executescript("""
            CREATE TABLE campaign (
                id INTEGER PRIMARY KEY CHECK(id=1), mission TEXT NOT NULL,
                mission_hash TEXT NOT NULL, status TEXT NOT NULL,
                outcome TEXT, created REAL NOT NULL, deadline REAL NOT NULL,
                wait_seconds INTEGER NOT NULL, wait_until REAL,
                wait_used INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE operations (
                id TEXT PRIMARY KEY, candidate TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('reserved','settled')),
                units INTEGER NOT NULL CHECK(units=1)
            );
            CREATE TABLE measurements (
                operation_id TEXT PRIMARY KEY REFERENCES operations(id),
                evidence TEXT NOT NULL
            );
            CREATE TABLE findings (
                candidate TEXT PRIMARY KEY, status TEXT NOT NULL,
                observation TEXT NOT NULL
            );
            CREATE TABLE events (
                id TEXT PRIMARY KEY, timestamp REAL NOT NULL,
                kind TEXT NOT NULL, payload TEXT NOT NULL
            );
        """)
        now = time.time()
        with transaction(db):
            db.execute("INSERT INTO campaign VALUES (1, ?, ?, 'ready', NULL, ?, ?, ?, NULL, 0)",
                       (json.dumps(MISSION, sort_keys=True), digest(MISSION), now,
                        now + wall_seconds, wait_seconds))
            event(db, "created", "campaign.created", {"base_commit": BASE_COMMIT})
    finally:
        db.close()


def connect(directory):
    path = Path(directory) / "demo.sqlite3"
    # mode=rw must not silently bootstrap a missing database.
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True,
                         isolation_level=None, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    row = db.execute("SELECT * FROM campaign").fetchone()
    if row is None or row["mission_hash"] != digest(MISSION) or json.loads(row["mission"]) != MISSION:
        db.close()
        raise ValueError("demo mission mismatch; refusing to reinterpret existing evidence")
    return db


def measure(candidate):
    # No model, subprocess, external data, stochastic sampling or credentials.
    if candidate not in CANDIDATES:
        raise ValueError("unregistered synthetic candidate")
    xs = MISSION["inputs"]
    outputs = [0 if candidate == "constant-zero" else x * x for x in xs]
    return {"validity": "completed", "candidate": candidate,
            "artifact_hash": digest({"candidate": candidate, "version": 1}),
            "evaluator": MISSION["evaluator"], "data_hash": digest(xs),
            "sample_count": len(xs), "seed": MISSION["seed"],
            "squared_error_sum": sum((y - x*x)**2 for x, y in zip(xs, outputs)),
            "aggregation": "sum_squared_error / sample_count"}


# Frozen square-grid-v1 gate: zero MSE AND strictly better than the measured
# trivial baseline. This makes the old zero-error criterion explicit, not looser.
TARGET_SQUARED_ERROR_SUM = 0


def evidence_score(evidence, candidate):
    """Return the validated raw sum; division can underflow or erase differences."""
    expected = measure_contract(candidate)
    if type(evidence) is not dict or set(evidence) != set(expected) | {"squared_error_sum"}:
        return None
    if any(type(evidence[k]) is not type(v) or evidence[k] != v for k, v in expected.items()):
        return None
    score = evidence["squared_error_sum"]
    if type(score) not in (int, float) or score < 0:
        return None
    try:
        return score if math.isfinite(score) else None
    except OverflowError:
        return None


def measure_contract(candidate):
    return {"validity": "completed", "candidate": candidate,
            "artifact_hash": digest({"candidate": candidate, "version": 1}),
            "evaluator": MISSION["evaluator"], "data_hash": digest(MISSION["inputs"]),
            "sample_count": len(MISSION["inputs"]), "seed": MISSION["seed"],
            "aggregation": "sum_squared_error / sample_count"}


def decode_evidence(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate evaluator evidence field")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("nonfinite evaluator evidence")
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, TypeError):
        return None  # Raw immutable evidence remains in SQLite for audit.


def finding(db, candidate, evidence):
    if candidate == MISSION["baseline"] or evidence_score(evidence, candidate) is None:
        return evidence_verdict(candidate, evidence, None)
    row = db.execute("SELECT evidence FROM measurements JOIN operations ON operation_id=id "
                     "WHERE candidate=?", (MISSION["baseline"],)).fetchone()
    return evidence_verdict(candidate, evidence, decode_evidence(row[0]) if row else None)


def evidence_verdict(candidate, evidence, baseline_evidence):
    """Shared frozen verdict for toy and canonical-ledger synthetic workflows."""
    score = evidence_score(evidence, candidate)
    if score is None:
        return "invalid", "Invalid evaluator evidence or provenance; no scientific verdict"
    if candidate == MISSION["baseline"]:
        return "abandoned", "Valid trivial baseline retained for comparison; not an improvement"
    baseline = evidence_score(baseline_evidence, MISSION["baseline"])
    if baseline is None:
        return "inconclusive", "No valid trivial baseline; comparison unavailable"
    # Both sample counts match the frozen contract; compare sums without rounding.
    if score == baseline:
        return "tied", "Tie against trivial baseline; no improvement"
    if score < baseline and score == TARGET_SQUARED_ERROR_SUM:
        return "promising", "Exploratory improvement meets frozen zero-MSE gate; not confirmation"
    return "abandoned", "No qualifying improvement against trivial baseline and frozen zero-MSE gate"


def snapshot(db):
    c = dict(db.execute("SELECT * FROM campaign").fetchone())
    usage = {r["status"]: r["n"] for r in db.execute(
        "SELECT status, SUM(units) AS n FROM operations GROUP BY status")}
    reserved, spent = usage.get("reserved", 0), usage.get("settled", 0)
    return {"schema_version": 1, "synthetic": True, "mission_hash": c["mission_hash"],
            "status": c["status"], "outcome": c["outcome"], "deadline": c["deadline"],
            "wait": ({"reason": "simulated_subscription_limit", "pool": "demo-slices",
                      "next_eligible_at": c["wait_until"]} if c["status"] == "waiting_resource" else None),
            "resources": {"unit": "synthetic_worker_slice", "authorized": 2,
                          "reserved": reserved, "spent": spent,
                          "available": 2 - reserved - spent},
            "claim": "untested", "confirmation": MISSION["confirmation"],
            "operations": [dict(r) for r in db.execute("SELECT * FROM operations ORDER BY id")],
            "measurements": [decode_evidence(r[0]) for r in db.execute(
                "SELECT evidence FROM measurements ORDER BY operation_id")],
            "findings": [dict(r) for r in db.execute("SELECT * FROM findings ORDER BY candidate")]}


def report(db, directory):
    return write_report(snapshot(db), directory)


def campaign_outcome(statuses):
    statuses = set(statuses)
    return ("inconclusive_invalid_evidence" if statuses & {"invalid", "inconclusive"}
            else "synthetic_improvement_unconfirmed" if "promising" in statuses
            else "no_improvement_tie" if "tied" in statuses else "no_qualifying_improvement")


def write_report(data, directory):
    """Regenerable view only; never rewrites source measurements or verdicts."""
    lines = ["# Synthetic discovery demo", "", "Not live research; no confirmed claim.",
             f"Status: {data['status']}; outcome: {data['outcome'] or 'pending'}",
             f"Mission hash: {data['mission_hash']}",
             "Baseline: constant-zero. Metric: mean squared error (lower is better).", ""]
    lines.append("Frozen square-grid-v1 gate: MSE <= 0 and strictly better than baseline.")
    for operation, m in zip(data["operations"], data["measurements"]):
        candidate = operation["candidate"]
        score = evidence_score(m, candidate)
        if score is None:
            lines.append(f"- {candidate}: invalid evaluator evidence/provenance; no valid metric.")
        else:
            metric = score / m["sample_count"]  # Presentation only, never a verdict input.
            lines.append(f"- {candidate}: MSE {metric:.6f} on {m['sample_count']} synthetic points; "
                         f"raw squared error sum {score!r}; completed.")
    lines += ["", "Resources: " + json.dumps(data["resources"], sort_keys=True),
              "Pending operations: " + str(sum(o["status"] in ("reserved", "active", "uncertain")
                                              for o in data.get("resource_operations", data["operations"]))),
              "", "The alternative was scripted, not discovered by a language model."]
    if "execution_route" in data:
        lines += ["", "Execution route: " + data["execution_route"],
                  "Authentication verified: false; eligible for live dispatch: false.",
                  "Recovery: retained fixture enforcer reaped fixed no-fork children; not arbitrary job supervision.",
                  "Confirmation is unperformed; its protected packet remains allocated, not borrowed."]
        for operation in data["resource_operations"]:
            lines.append("- Resource operation: " + json.dumps(operation, sort_keys=True))
    target = Path(directory) / "report.md"
    temporary = target.with_suffix(".tmp")
    with temporary.open("w") as f:
        f.write("\n".join(lines) + "\n")
        f.flush()
        os.fsync(f.fileno())
    temporary.replace(target)
    return data


def advance(db, crash=None):
    """One bounded transition. Completed measurements are reconciled before limits."""
    c = db.execute("SELECT * FROM campaign").fetchone()
    if c["status"] == "completed":
        return
    # Recover the side-effect/acknowledgment gap without another evaluation.
    pending = db.execute("SELECT * FROM operations WHERE status='reserved'").fetchone()
    if pending:
        result = db.execute("SELECT evidence FROM measurements WHERE operation_id=?",
                            (pending["id"],)).fetchone()
        if result:
            m = decode_evidence(result[0])
            status, observation = finding(db, pending["candidate"], m)
            with transaction(db):
                db.execute("UPDATE operations SET status='settled' WHERE id=?", (pending["id"],))
                db.execute("INSERT INTO findings VALUES (?, ?, ?)",
                           (pending["candidate"], status,
                            observation))
                event(db, pending["id"] + ":settled", "candidate." + status, m)
            return
    if time.time() >= c["deadline"]:
        with transaction(db):
            db.execute("UPDATE campaign SET status='completed', outcome='inconclusive_deadline' WHERE id=1")
            event(db, "completed", "campaign.completed", {"outcome": "inconclusive_deadline"})
        return
    if pending:
        m = measure(pending["candidate"])
        with transaction(db):
            db.execute("INSERT INTO measurements VALUES (?, ?)",
                       (pending["id"], json.dumps(m, sort_keys=True)))
            event(db, pending["id"] + ":measured", "trial.completed", m)
        if crash == "after_measurement":
            os._exit(75)  # test the real process-death recovery path
        return
    count = db.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
    if count == 2:
        statuses = {r[0] for r in db.execute("SELECT status FROM findings")}
        outcome = campaign_outcome(statuses)
        with transaction(db):
            db.execute("UPDATE campaign SET status='completed', outcome=? WHERE id=1", (outcome,))
            event(db, "completed", "campaign.completed", {"outcome": outcome})
        return
    if count == 1 and not c["wait_used"]:
        with transaction(db):
            until = time.time() + c["wait_seconds"]
            db.execute("UPDATE campaign SET status='waiting_resource', wait_until=?, wait_used=1 WHERE id=1", (until,))
            event(db, "quota-wait", "resource.wait", {"next_eligible_at": until, "pool": "demo-slices"})
        return
    if c["status"] == "waiting_resource" and time.time() < c["wait_until"]:
        return
    with transaction(db):
        used = db.execute("SELECT COALESCE(SUM(units),0) FROM operations").fetchone()[0]
        if used >= MISSION["slice_limit"]:
            raise ValueError("synthetic slice allocation exhausted")
        candidate = CANDIDATES[count]
        op_id = f"candidate-{count + 1}"
        db.execute("INSERT INTO operations VALUES (?, ?, 'reserved', 1)", (op_id, candidate))
        db.execute("UPDATE campaign SET status='running', wait_until=NULL WHERE id=1")
        event(db, op_id + ":intent", "operation.reserved", {"candidate": candidate})
    if crash == "after_reservation":
        os._exit(75)


def run(directory, watch=False, crash=None):
    # This lock protects the entire local demo executor, not merely SQL writes.
    # Kernel releases it on death; no remote jobs or descendant processes exist.
    with (Path(directory) / "executor.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another demo executor is active") from None
        db = connect(directory)
        try:
            while True:
                advance(db, crash)
                data = report(db, directory)
                if data["status"] == "completed":
                    return data
                if data["status"] == "waiting_resource":
                    if not watch:
                        return data
                    delay = min(data["wait"]["next_eligible_at"], data["deadline"]) - time.time()
                    time.sleep(max(0, min(1, delay)))
        finally:
            db.close()


def command(args):
    try:
        if args.demo_action == "init":
            initialize(args.directory, args.wait_seconds, args.wall_seconds)
        if args.demo_action == "run":
            data = run(args.directory, args.watch, args.simulate_crash)
        else:
            db = connect(args.directory)
            try:
                with transaction(db):
                    data = snapshot(db)
            finally:
                db.close()
        print(json.dumps(data, sort_keys=True, indent=2))
    except (ValueError, OSError, sqlite3.Error) as exc:
        raise SystemExit(f"demo: {exc}") from None


def add_parser(sub):
    campaign = sub.add_parser("campaign", help="experimental discovery interfaces (no live dispatch)")
    campaigns = campaign.add_subparsers(dest="campaign_action", required=True)
    from labloop_resources import add_parsers as add_resource_parsers
    add_resource_parsers(sub, campaigns)
    from labloop_integration import add_parser as add_integration_parser
    add_integration_parser(campaigns)
    demo = campaigns.add_parser("demo", help="fixed synthetic worker; no providers or public-state writes")
    actions = demo.add_subparsers(dest="demo_action", required=True)
    for name in ("init", "run", "status"):
        parser = actions.add_parser(name)
        parser.add_argument("--directory", required=True, type=Path,
                            help="private demo directory; init requires it not to exist")
        if name == "init":
            parser.add_argument("--wait-seconds", type=int, default=60)
            parser.add_argument("--wall-seconds", type=int, default=3600)
        if name == "run":
            parser.add_argument("--watch", action="store_true", help="foreground timer; bounded by campaign deadline")
            parser.add_argument("--simulate-crash", choices=("after_reservation", "after_measurement"),
                                help="test only: exit 75 at a durable boundary")
        parser.set_defaults(func=command)
