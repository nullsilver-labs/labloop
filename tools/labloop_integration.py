"""Fixed offline discovery on the canonical v2 Ledger; no live adapter.

The foreground enforcer retains/reaps ONLY children launched by this module. Its
in-memory Popen evidence cannot survive its own death. Never use this fixture
verifier for real jobs, arbitrary runners, descendants, or worker exit assertions.
Namespaced versioned audit records extend no SQL schema and create no allowance DB.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

import labloop_discovery as demo
from labloop_resources import (Ledger, ResourceError, audit, canonical, integer,
                               object_keys, private_path, require, resolve, transaction)

PREFIX = "synthetic.discovery.v1"
COSTS = {"evaluator_runs": 1, "cpu_seconds": 2, "inference_units": 3, "wall_seconds": 10}
STEPS = {"demo-A": ("exploration", "constant-zero"),
         "demo-B": ("exploration", "square"), "demo-finalize": ("finalization", None)}
MISSION_TEXT = canonical({"fixture": PREFIX, "execution_route": "fixed-synthetic-no-provider",
                          "mission": demo.MISSION}) + "\n"


def fixture_files(directory):
    directory = Path(directory).absolute()
    packet = {"inference_unit": "local_token", "campaign": {d: 4*v for d, v in COSTS.items()},
              "confirmation": COSTS, "finalization": COSTS}
    inventory = {"schema_version": 2, "ledger_path": str(directory / "private/resources.sqlite3"),
                 "new_cash_spending": {"enabled": False, "currency": "EUR", "monthly_limit": "0.00"},
                 "providers": {"synthetic_intent_only": {
                     "enabled": True, "adapter": "claude_code_cli", "authentication": "native_subscription",
                     "pool": "synthetic_pool", "models": {"research": "synthetic-not-a-model"},
                     "allow_subagents": False, "allow_paid_features": False}},
                 "pools": {"synthetic_pool": {"kind": "subscription", "max_parallel_sessions": 1,
                     "max_worker_slices_per_day": 4, "max_turns_per_slice": 1,
                     "max_slice_wall_seconds": 60, "allow_paid_overage": False}}}
    policy = {"schema_version": 2, "project_id": "synthetic-discovery", "mode": "discovery",
              "mission_file": "MISSION.md", "routing": {"research": ["synthetic_intent_only:research"]},
              "allocations": {"synthetic_pool": {"campaign_slices": 4, "daily_slices": 4,
                  "confirmation_slices": 1, "finalization_slices": 1, "local_packet": packet}},
              "max_campaign_wall_hours": 1}
    return inventory, policy


def configuration(directory):
    directory = Path(directory).absolute()
    private_path(directory, directory=True)
    cfg = resolve(directory / "private/inventory.json", directory / "project/labloop.json")
    inventory, policy = fixture_files(directory)
    require(cfg["inventory"] == inventory and cfg["policy"] == policy and cfg["mission_text"] == MISSION_TEXT,
            "only the exact fresh synthetic fixture is supported; real configuration refused")
    return cfg


def initialize(directory, wait_seconds=1):
    integer(wait_seconds, 0, 5, "synthetic wait seconds")
    directory = Path(directory).absolute()
    require(not directory.resolve().is_relative_to(Path(__file__).resolve().parent.parent),
            "synthetic fixture must be outside repository")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    (directory / "private").mkdir(mode=0o700)
    (directory / "project").mkdir(mode=0o700)
    inventory, policy = fixture_files(directory)
    for path, value in ((directory / "private/inventory.json", canonical(inventory)),
                        (directory / "project/labloop.json", canonical(policy)),
                        (directory / "project/MISSION.md", MISSION_TEXT)):
        with path.open("x") as f:
            os.chmod(path, 0o600)
            f.write(value)
    ledger = Ledger(configuration(directory), create=True)
    try:
        ledger.authorize(ledger.config["authorization_hash"])
        with transaction(ledger.db):
            append(ledger, "created", {"wait_seconds": wait_seconds, "mission_hash": demo.digest(demo.MISSION)})
    finally:
        ledger.close()


def records(ledger):
    """Strict, immutable key association; corruption is not treated as no evidence."""
    result = {}
    for row in ledger.db.execute("SELECT kind,payload FROM audit WHERE kind LIKE ? ORDER BY sequence", (PREFIX + "%",)):
        require(row["kind"] == PREFIX, "unsupported synthetic audit version")
        value = demo.decode_evidence(row["payload"])
        object_keys(value, ("key", "data"), "synthetic audit record")
        key, data = value["key"], value["data"]
        require(type(key) is str and key not in result, "duplicate or invalid synthetic audit key")
        if key == "created":
            object_keys(data, ("wait_seconds", "mission_hash"), key)
            integer(data["wait_seconds"], 0, 5, "synthetic wait seconds")
            require(data["mission_hash"] == demo.digest(demo.MISSION), "synthetic mission mismatch")
        elif key == "quota-wait":
            object_keys(data, ("next_eligible_at", "reason"), key)
            ledger.clock(data["next_eligible_at"])
            require(data["reason"] == "simulated_subscription_limit", "invalid wait reason")
        elif key == "completed":
            object_keys(data, ("outcome",), key)
            require(data["outcome"] in ("inconclusive_invalid_evidence", "synthetic_improvement_unconfirmed",
                    "no_improvement_tie", "no_qualifying_improvement"), "invalid outcome")
        else:
            parts = key.split(":")
            require(len(parts) == 2 and parts[0] in ("demo-A", "demo-B")
                    and parts[1] in ("measurement", "finding"), "unknown synthetic audit key")
            session, kind = parts
            fields = ("session", "candidate", "evidence") if kind == "measurement" else ("session", "candidate", "status", "observation")
            object_keys(data, fields, key)
            require(data["session"] == session and data["candidate"] == STEPS[session][1], "evidence association mismatch")
            op = ledger.session(session)
            packet = ledger.db.execute("SELECT * FROM session_packets WHERE session=?", (session,)).fetchone()
            require(op["purpose"] == "exploration" and op["status"] in ("active", "uncertain", "settled")
                    and packet is not None and packet["costs"] == canonical(COSTS)
                    and packet["job"] == session + "-job", "evidence lacks matching canonical dispatched intent")
            if kind == "measurement":
                require(type(data["evidence"]) is str, "raw evidence must be immutable text")
            else:
                require(session + ":measurement" in result and op["status"] == "settled", "finding lacks settled evidence")
                raw = result[session + ":measurement"]["evidence"]
                baseline = result.get("demo-A:measurement", {}).get("evidence")
                expected = demo.evidence_verdict(data["candidate"], demo.decode_evidence(raw), demo.decode_evidence(baseline))
                require((data["status"], data["observation"]) == expected, "finding differs from frozen verdict")
        result[key] = data
    if "completed" in result:
        require(all(s + ":finding" in result for s in ("demo-A", "demo-B")), "completion lacks findings")
        require(result["completed"]["outcome"] == demo.campaign_outcome(result[s + ":finding"]["status"] for s in ("demo-A", "demo-B")),
                "completion differs from evaluator verdicts")
        require(ledger.session("demo-finalize")["status"] in ("active", "uncertain", "settled"), "completion lacks finalization opportunity")
    return result


def append(ledger, key, data):
    require(ledger.db.in_transaction, "synthetic evidence requires canonical write transaction")
    old = records(ledger)
    if key in old:
        require(canonical(old[key]) == canonical(data), "conflicting immutable synthetic audit key")
        return
    audit(ledger.db, PREFIX, {"key": key, "data": data}, time.time())
    records(ledger)  # Validate before commit; malformed evidence envelopes roll back.


def open_fixture(directory, verifier=None):
    ledger = Ledger(configuration(directory), exit_verifier=verifier)
    try:
        ledger.grant()
        require("created" in records(ledger), "not an initialized synthetic campaign")
        return ledger
    except BaseException:
        ledger.close()
        raise


def acknowledge(ledger, token, session):
    with transaction(ledger.db):
        ledger.check_lease(token)
        require(ledger.session(session)["status"] == "settled", "exit not reconciled; occupancy retained")
        saved = records(ledger)
        raw = saved.get(session + ":measurement")
        require(raw is not None, "unknown evaluator outcome; no reevaluation or invented finding")
        status, observation = demo.evidence_verdict(raw["candidate"], demo.decode_evidence(raw["evidence"]),
                                                   demo.decode_evidence(saved.get("demo-A:measurement", {}).get("evidence")))
        append(ledger, session + ":finding", {"session": session, "candidate": raw["candidate"],
                                              "status": status, "observation": observation})


def snapshot(ledger):
    with transaction(ledger.db):
        resources = ledger._status(ledger.clock(None))
        saved = records(ledger)
        operations = resources["operations"]
        outcome = saved.get("completed", {}).get("outcome")
        finalized = any(o["id"] == "demo-finalize" and o["status"] == "settled" for o in operations)
        wait = saved.get("quota-wait")
        waiting = wait and time.time() < wait["next_eligible_at"]
        measured = [s for s in ("demo-A", "demo-B") if s + ":measurement" in saved]
        return {"schema_version": 1, "synthetic": True, "status": "completed" if finalized and outcome else "waiting_resource" if waiting else "pending",
                "outcome": outcome if finalized else None, "mission_hash": demo.digest(demo.MISSION),
                "deadline": resources["deadline"], "resources": resources, "resource_operations": operations,
                "execution_route": "fixed-synthetic-no-provider (configured Claude adapter is intent ONLY)",
                "authentication_verified": False, "eligible_for_live_dispatch": False, "claim": "untested",
                "confirmation": demo.MISSION["confirmation"], "wait": wait,
                "operations": [{"id": s, "candidate": STEPS[s][1], "status": ledger.session(s)["status"]} for s in measured],
                "measurements": [demo.decode_evidence(saved[s + ":measurement"]["evidence"]) for s in measured],
                "findings": [saved[s + ":finding"] for s in ("demo-A", "demo-B") if s + ":finding" in saved]}


def report(ledger, directory):
    return demo.write_report(snapshot(ledger), directory)


class FixtureEnforcer:
    """Ephemeral trusted Popen registry, exclusively for our fixed no-fork child.

    Identity start_id is an enforcer-assigned lifecycle nonce, NOT an OS start-time
    certificate. Exact handle binding plus wait/poll is the only exit authority.
    Losing this object loses that authority; neither files nor PID absence replace it.
    """
    def __init__(self):
        self.children = {}
        self.boot = uuid.uuid4().hex

    def launch(self, directory, session):
        require(session in STEPS, "unregistered fixed step")
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(Path(directory).absolute()), session],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        identity = {"host": "synthetic-fixture", "boot_id": self.boot, "pid": proc.pid, "start_id": uuid.uuid4().hex}
        self.children[canonical(identity)] = (proc, session)
        return proc, identity

    def verify(self, kind, record):
        identity = record["identity"] if kind == "supervisor" else record["process"]
        entry = self.children.get(identity)
        if entry is None:
            return None
        proc, session = entry
        if kind == "supervisor":
            if record["owner"] != session + "-owner":
                return None
        elif kind != "job" or record["session"] != session or record["job"] != session + "-job":
            return None
        return proc.poll()  # None while alive; real waitpid outcome otherwise.

    def close(self):
        for proc, _ in self.children.values():
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                stream.close()


def ready(proc):
    require(bool(select.select([proc.stdout], [], [], 10)[0]), "fixed child readiness timeout")
    require(proc.stdout.readline() == "committed\n", "fixed child failed before durable boundary")


def child(directory, session):
    """Private fixed child protocol; no commands, exit claims or verifier accepted."""
    require(session in STEPS, "unregistered fixed step")
    require(bool(select.select([sys.stdin], [], [], 15)[0]), "enforcer handshake timeout")
    launch = json.loads(sys.stdin.readline())
    object_keys(launch, ("identity", "token"), "enforcer handshake")
    identity, token = launch["identity"], launch["token"]
    require(identity["pid"] == os.getpid(), "wrong fixture child PID")
    ledger = open_fixture(directory)
    try:
        # Same identity retries may not create a replacement generation themselves.
        ledger.check_lease(token)
        lease = ledger.db.execute("SELECT * FROM leases").fetchone()
        require(lease["identity"] == canonical(identity) and lease["owner"] == session + "-owner", "unowned fixture step")
        purpose, candidate = STEPS[session]
        if session == "demo-B":
            saved = records(ledger)
            require("demo-A:finding" in saved and "quota-wait" in saved
                    and time.time() >= saved["quota-wait"]["next_eligible_at"], "synthetic quota wait not completed")
        op = ledger.reserve(session, purpose, lease=token, costs=COSTS)
        require(op["status"] == "reserved", "stable operation cannot be executed again")
        ledger.mark_dispatched(session, lease=token, job=session + "-job", process=identity)
        if session == "demo-finalize":
            acknowledge(ledger, token, "demo-B")
        if candidate:
            evidence = canonical(demo.measure(candidate))
            with transaction(ledger.db):
                ledger.check_lease(token)
                ledger.session_packet(session, token)
                require(ledger.session(session)["status"] == "active", "evaluation lost active intent")
                append(ledger, session + ":measurement", {"session": session, "candidate": candidate, "evidence": evidence})
        else:
            with transaction(ledger.db):
                ledger.check_lease(token)
                saved = records(ledger)
                outcome = demo.campaign_outcome(saved[s + ":finding"]["status"] for s in ("demo-A", "demo-B"))
                append(ledger, "completed", {"outcome": outcome})
        print("committed", flush=True)  # Side-effect readiness, NOT completion/final reply.
        if session == "demo-B":
            time.sleep(15)  # Parent externally SIGKILLs this fixed no-fork process.
            raise RuntimeError("enforcer failed to kill paused fixture")
    finally:
        ledger.close()


def run(directory):
    """Bounded foreground demo. New enforcer cannot resume unknown prior owners."""
    directory = Path(directory)
    private_path(directory, directory=True)
    with (directory / "coordinator.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ResourceError("another synthetic coordinator is active") from None
        enforcer = FixtureEnforcer()
        ledger = open_fixture(directory, enforcer.verify)
        try:
            initial = snapshot(ledger)
            if initial["status"] == "completed":
                return report(ledger, directory)
            # No filesystem exit claims or reset path when enforcer evidence is lost.
            require(initial["resources"]["lease"] is None,
                    "prior enforcer evidence unavailable; recovery gated, occupancy/allocations retained")
            for session in STEPS:
                proc, identity = enforcer.launch(directory, session)
                token = ledger.acquire_lease(session + "-owner", identity)
                proc.stdin.write(canonical({"identity": identity, "token": token}) + "\n")
                proc.stdin.flush()
                ready(proc)
                if session == "demo-B":
                    # Unknown remains occupied even with a committed measurement.
                    ledger.mark_uncertain(session, lease=token)
                    report(ledger, directory)
                    proc.kill()  # External SIGKILL, before finding/ack/final worker response.
                    require(proc.wait(timeout=5) == -signal.SIGKILL, "expected external synthetic SIGKILL")
                    ledger.close()
                    ledger = open_fixture(directory, enforcer.verify)
                    # Next iteration acquires a NEW generation, atomically reconciling
                    # B from trusted retained handle evidence, never from measurement.
                    continue
                require(proc.wait(timeout=5) == 0, "fixed child failed")
                ledger.record_exit(session, 0, lease=token)
                if session == "demo-A":
                    acknowledge(ledger, token, session)
                    with transaction(ledger.db):
                        ledger.check_lease(token)
                        append(ledger, "quota-wait", {"next_eligible_at": time.time() + records(ledger)["created"]["wait_seconds"],
                                                       "reason": "simulated_subscription_limit"})
                    data = report(ledger, directory)
                    until = data["wait"]["next_eligible_at"]
                    require(until + 30 <= data["deadline"], "wait cannot fit remaining packet; no deadline renewal")
                    time.sleep(max(0, until - time.time()))
            return report(ledger, directory)
        finally:
            ledger.close()
            enforcer.close()


def command(args):
    try:
        if args.integration_action == "init":
            initialize(args.directory, args.wait_seconds)
        if args.integration_action == "run":
            data = run(args.directory)
        else:
            ledger = open_fixture(args.directory)
            try:
                data = snapshot(ledger)
            finally:
                ledger.close()
        print(json.dumps(data, sort_keys=True, indent=2))
    except (ValueError, OSError, sqlite3.Error) as exc:
        raise SystemExit(f"synthetic integration: {exc}") from None


def add_parser(campaigns):
    parser = campaigns.add_parser("integrated-demo", help="fresh synthetic fixture on canonical v2 ledger; no providers")
    actions = parser.add_subparsers(dest="integration_action", required=True)
    for name in ("init", "run", "status"):
        action = actions.add_parser(name)
        action.add_argument("--directory", required=True, type=Path)
        if name == "init":
            action.add_argument("--wait-seconds", type=int, default=1)
        action.set_defaults(func=command)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Private fixed synthetic child, not an arbitrary runner")
    parser.add_argument("directory", type=Path)
    parser.add_argument("session", choices=STEPS)
    args = parser.parse_args()
    child(args.directory, args.session)
