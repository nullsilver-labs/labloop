#!/usr/bin/env python3
"""Canonical-ledger integration; only real fixed synthetic processes, no providers."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import labloop_integration as integration
from labloop_resources import Ledger, ResourceError, audit, canonical, transaction


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "campaign"
        integration.initialize(self.directory, 0)

    def open(self, verifier=None):
        ledger = integration.open_fixture(self.directory, verifier)
        self.addCleanup(ledger.close)
        return ledger

    def start(self, enforcer, ledger, session):
        proc, identity = enforcer.launch(self.directory, session)
        token = ledger.acquire_lease(session + "-owner", identity)
        proc.stdin.write(canonical({"identity": identity, "token": token}) + "\n")
        proc.stdin.flush()
        integration.ready(proc)
        return proc, identity, token

    def test_full_cli_reports_canonical_ids_dimensions_and_protected_confirmation(self):
        command = [str(ROOT / "tools/lab"), "campaign", "integrated-demo", "run", "--directory", str(self.directory)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["outcome"], "synthetic_improvement_unconfirmed")
        self.assertFalse(data["authentication_verified"])
        self.assertFalse(data["eligible_for_live_dispatch"])
        self.assertEqual([f["status"] for f in data["findings"]], ["abandoned", "promising"])
        self.assertEqual([m["squared_error_sum"] for m in data["measurements"]], [196, 0])
        self.assertEqual([o["id"] for o in data["resource_operations"]], list(integration.STEPS))
        self.assertEqual([o["purpose"] for o in data["resource_operations"]], ["exploration", "exploration", "finalization"])
        self.assertEqual([o["generation"] for o in data["resource_operations"]], [1, 2, 3])
        self.assertEqual([o["exit_code"] for o in data["resource_operations"]], [0, -signal.SIGKILL, 0])
        for op in data["resource_operations"]:
            self.assertEqual(op["costs"], integration.COSTS)
            self.assertEqual(op["worker_slices"], 1)
        resources = data["resources"]
        self.assertEqual((resources["spent"], resources["reserved"], resources["uncertain"]), (3, 0, 0))
        self.assertEqual(resources["protected_remaining"], {"confirmation": 1, "finalization": 0})
        self.assertEqual(resources["local_packet_remaining"], {
            "confirmation": integration.COSTS, "finalization": dict.fromkeys(integration.COSTS, 0),
            "exploration": dict.fromkeys(integration.COSTS, 0)})
        status = subprocess.run([str(ROOT / "tools/lab"), "resources", "status", "--inventory",
                                 str(self.directory / "private/inventory.json"), "--policy",
                                 str(self.directory / "project/labloop.json")], capture_output=True, text=True, timeout=10)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout), resources)
        self.assertEqual(resources["operations"], data["resource_operations"])
        ledger = self.open()
        tables = {r[0] for r in ledger.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {"metadata", "grants", "sessions", "audit", "leases", "session_packets"})
        self.assertEqual(list(self.directory.rglob("*.sqlite3")), [self.directory / "private/resources.sqlite3"])
        before = list(ledger.db.iterdump())
        report = self.directory / "report.md"
        expected = report.read_bytes()
        text = report.read_text()
        self.assertIn("unconfirmed", text)
        self.assertIn("MSE 28.000000", text)
        self.assertIn("intent ONLY", text)
        for line in text.splitlines():
            if line.startswith("- Resource operation: "):
                self.assertIn(json.loads(line.removeprefix("- Resource operation: ")), data["resource_operations"])
        report.unlink()
        again = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout), data)
        self.assertEqual(report.read_bytes(), expected)
        self.assertEqual(list(ledger.db.iterdump()), before)
        # Reauthorization never renews any deadline or replenishes an allocation.
        grant = dict(ledger.grant())
        ledger.authorize(ledger.config["authorization_hash"], now=grant["deadline"] + 1)
        self.assertEqual(dict(ledger.grant()), grant)
        self.assertEqual(list(ledger.db.iterdump()), before)
        with self.assertRaises(FileExistsError):
            integration.initialize(self.directory)

    def test_external_sigkill_gap_reopens_generation_without_evaluator_replay(self):
        calls = Path(self.temp.name) / "evaluator-calls"
        real_popen = subprocess.Popen
        real_ready = integration.ready
        real_verify = integration.FixtureEnforcer.verify
        observations = []
        snapshots = []
        # Test-only instrumentation of the fixed child evaluator. No production
        # arbitrary-runner API; an fsynced external call audit detects replay.
        wrapper = '''import os,sys
sys.path.insert(0, sys.argv[1])
import labloop_integration as i
original = i.demo.measure
def measured(candidate):
    with open(sys.argv[2], 'a') as f:
        f.write(candidate+'\\n'); f.flush(); os.fsync(f.fileno())
    return original(candidate)
i.demo.measure=measured
i.child(sys.argv[3],sys.argv[4])
'''
        def instrumented(argv, **kwargs):
            if len(argv) == 4 and argv[1] == str(ROOT / "tools/labloop_integration.py"):
                argv = [sys.executable, "-c", wrapper, str(ROOT / "tools"), str(calls), argv[2], argv[3]]
            return real_popen(argv, **kwargs)
        def observed_verify(enforcer, kind, record):
            code = real_verify(enforcer, kind, record)
            observations.append((kind, record, code))
            return code
        def boundary(proc):
            real_ready(proc)
            ledger = integration.open_fixture(self.directory)
            try:
                saved = integration.records(ledger)
                if "demo-B:measurement" not in saved or "completed" in saved:
                    return
                before = list(ledger.db.iterdump())
                pending = integration.report(ledger, self.directory)
                self.assertEqual(pending["resources"]["spent"], 1)
                self.assertEqual(pending["resources"]["reserved"], 1)
                self.assertEqual(pending["outcome"], None)
                self.assertNotIn("demo-B:finding", saved)
                self.assertIsNone(proc.poll())
                # A second actual CLI supervisor is denied; it cannot reset state.
                second = subprocess.run([str(ROOT / "tools/lab"), "campaign", "integrated-demo", "run",
                                         "--directory", str(self.directory)], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(second.returncode, 0)
                self.assertIn("another synthetic coordinator", second.stderr)
                # No default verifier may infer exit from committed measurement.
                identity = {"host": "synthetic-fixture", "boot_id": "other", "pid": os.getpid(), "start_id": "other"}
                with self.assertRaisesRegex(ResourceError, "verifier required"):
                    ledger.acquire_lease("intruder", identity, now=ledger.grant()["deadline"] + 1)
                self.assertEqual(list(ledger.db.iterdump()), before)
                snapshots.append({k: v for k, v in saved.items()})
            finally:
                ledger.close()
        with patch.object(integration.subprocess, "Popen", side_effect=instrumented), \
             patch.object(integration, "ready", side_effect=boundary), \
             patch.object(integration.FixtureEnforcer, "verify", observed_verify):
            done = integration.run(self.directory)
        self.assertEqual(calls.read_text().splitlines(), ["constant-zero", "square"])
        self.assertEqual(len(snapshots), 1)
        ledger = self.open()
        saved = integration.records(ledger)
        for key, value in snapshots[0].items():
            self.assertEqual(saved[key], value)
        b_exits = [(kind, record, code) for kind, record, code in observations if record.get("session") == "demo-B"]
        self.assertEqual(len(b_exits), 1)
        self.assertEqual(b_exits[0][2], -signal.SIGKILL)
        reconciled = [json.loads(r[0]) for r in ledger.db.execute("SELECT payload FROM audit WHERE kind='session.reconciled'")]
        self.assertEqual(reconciled, [{"id": "demo-B", "status": "settled", "exit_code": -signal.SIGKILL}])
        self.assertEqual(done["resources"]["lease"]["generation"], 3)
        self.assertEqual(done["resources"]["spent"], 3)
        self.assertEqual(integration.run(self.directory), done)
        self.assertEqual(calls.read_text().splitlines(), ["constant-zero", "square"])

    def test_live_child_and_lost_enforcer_evidence_preserve_unknown_occupancy(self):
        enforcer = integration.FixtureEnforcer()
        self.addCleanup(enforcer.close)
        ledger = self.open(enforcer.verify)
        proc, identity = enforcer.launch(self.directory, "demo-B")
        token = ledger.acquire_lease("demo-B-owner", identity)
        # Real fixed child is waiting for its handshake: dispatched identity is
        # real, but this test intentionally produces NO evaluator outcome.
        ledger.reserve("demo-B", lease=token, costs=integration.COSTS)
        ledger.mark_dispatched("demo-B", lease=token, job="demo-B-job", process=identity)
        ledger.mark_uncertain("demo-B", lease=token)
        other = {**identity, "pid": os.getpid(), "start_id": "replacement"}
        before = list(ledger.db.iterdump())
        with self.assertRaisesRegex(ResourceError, "unknown"):
            ledger.acquire_lease("replacement", other, now=ledger.grant()["deadline"] + 100)
        self.assertEqual(list(ledger.db.iterdump()), before)
        with self.assertRaisesRegex(ResourceError, "unknown"):
            ledger.record_exit("demo-B", 0, lease=token)
        proc.kill()
        self.assertEqual(proc.wait(timeout=5), -signal.SIGKILL)
        # Fresh process has no retained Popen authority, even though parent knows
        # the exit. It cannot accept caller-provided exit booleans or PID absence.
        result = subprocess.run([str(ROOT / "tools/lab"), "campaign", "integrated-demo", "run",
                                 "--directory", str(self.directory)], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prior enforcer evidence unavailable", result.stderr)
        self.assertEqual(list(ledger.db.iterdump()), before)
        pending = integration.report(ledger, self.directory)
        self.assertEqual(pending["resources"]["uncertain"], 1)
        self.assertEqual(pending["resources"]["account_unresolved_sessions"], 1)
        self.assertIsNone(pending["outcome"])
        self.assertEqual(pending["measurements"], [])
        self.assertIn("Pending operations: 1", (self.directory / "report.md").read_text())
        with self.assertRaisesRegex(ResourceError, "unresolved"):
            ledger.reserve("cannot-borrow", lease=token, costs=integration.COSTS)

    def test_external_supervisor_kill_without_retained_enforcer_gates_fresh_process(self):
        # This direct fixed evaluator is also the lease-owning supervisor. Parent
        # reaps it, then deliberately discards that authority. No descendant claim.
        enforcer = integration.FixtureEnforcer()
        self.addCleanup(enforcer.close)
        ledger = self.open(enforcer.verify)
        real_popen = subprocess.Popen
        wrapper = '''import sys,time
sys.path.insert(0,sys.argv[1])
import labloop_integration as i
original=i.append
def committed(ledger,key,data):
    original(ledger,key,data)
    if key=='demo-A:measurement':
        ledger.db.commit()
        print('committed',flush=True)
        time.sleep(15)
i.append=committed
i.child(sys.argv[2],sys.argv[3])
'''
        def paused(argv, **kwargs):
            return real_popen([sys.executable, "-c", wrapper, str(ROOT / "tools"), argv[2], argv[3]], **kwargs)
        with patch.object(integration.subprocess, "Popen", side_effect=paused):
            proc, _, token = self.start(enforcer, ledger, "demo-A")
        ledger.mark_uncertain("demo-A", lease=token)
        before = list(ledger.db.iterdump())
        proc.kill()
        self.assertEqual(proc.wait(timeout=5), -signal.SIGKILL)
        result = subprocess.run([str(ROOT / "tools/lab"), "campaign", "integrated-demo", "run",
                                 "--directory", str(self.directory)], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prior enforcer evidence unavailable", result.stderr)
        self.assertEqual(list(ledger.db.iterdump()), before)
        pending = integration.report(ledger, self.directory)
        self.assertEqual(pending["resources"]["uncertain"], 1)
        self.assertEqual(pending["resources"]["lease"]["generation"], 1)
        self.assertEqual(len(pending["measurements"]), 1)
        self.assertEqual(pending["findings"], [])
        self.assertIsNone(pending["outcome"])

    def test_audit_atomicity_conflicts_and_malformed_records_fail_closed(self):
        ledger = self.open()
        initial = list(ledger.db.iterdump())
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with transaction(ledger.db):
                integration.append(ledger, "quota-wait", {"reason": "simulated_subscription_limit", "next_eligible_at": 1})
                raise RuntimeError("rollback")
        self.assertEqual(list(ledger.db.iterdump()), initial)
        created = integration.records(ledger)["created"]
        with transaction(ledger.db):
            integration.append(ledger, "created", created)
        self.assertEqual(list(ledger.db.iterdump()), initial)
        with self.assertRaisesRegex(ResourceError, "conflicting"):
            with transaction(ledger.db):
                integration.append(ledger, "created", {**created, "wait_seconds": 2})
        self.assertEqual(list(ledger.db.iterdump()), initial)
        malformed = [{"key": "created", "data": created}, {"key": "unknown", "data": {}},
                     {"key": "demo-B:measurement", "data": {"session": "demo-A", "candidate": "square", "evidence": "{}"}}]
        for value in malformed:
            with self.assertRaises(ResourceError):
                with transaction(ledger.db):
                    audit(ledger.db, integration.PREFIX, value, 0)
                    integration.records(ledger)
            self.assertEqual(list(ledger.db.iterdump()), initial)

    def test_corrupt_measurement_verdict_reuses_immutable_evaluator_validation(self):
        # Test-only evaluator fault, not a selectable production worker/evaluator.
        real_popen = subprocess.Popen
        wrapper = '''import sys
sys.path.insert(0,sys.argv[1])
import labloop_integration as i
i.demo.measure=lambda candidate: {"untrusted": "invalid"}
i.child(sys.argv[2],sys.argv[3])
'''
        def invalid(argv, **kwargs):
            return real_popen([sys.executable, "-c", wrapper, str(ROOT / "tools"), argv[2], argv[3]], **kwargs)
        with patch.object(integration.subprocess, "Popen", side_effect=invalid):
            data = integration.run(self.directory)
        self.assertEqual(data["outcome"], "inconclusive_invalid_evidence")
        self.assertEqual([f["status"] for f in data["findings"]], ["invalid", "invalid"])
        self.assertEqual(data["resources"]["spent"], 3)
        ledger = self.open()
        self.assertEqual(integration.records(ledger)["demo-B:measurement"]["evidence"], '{"untrusted":"invalid"}')

    def test_quota_wait_is_durable_and_protected_packets_are_not_exploration(self):
        self.directory = Path(self.temp.name) / "waiting"
        integration.initialize(self.directory, 1)
        original_sleep = time.sleep
        observed = []
        def during_wait(seconds):
            ledger = integration.open_fixture(self.directory)
            try:
                data = integration.snapshot(ledger)
                observed.append(data)
                before = list(ledger.db.iterdump())
                self.assertEqual(data["status"], "waiting_resource")
                self.assertEqual(data["wait"]["reason"], "simulated_subscription_limit")
                self.assertEqual(data["resources"]["spent"], 1)
                self.assertEqual(data["resources"]["protected_remaining"], {"confirmation": 1, "finalization": 1})
                self.assertEqual(data["resources"]["local_packet_remaining"]["confirmation"], integration.COSTS)
                self.assertEqual(data["resources"]["local_packet_remaining"]["finalization"], integration.COSTS)
                self.assertEqual(integration.snapshot(ledger), data)
                self.assertEqual(list(ledger.db.iterdump()), before)
            finally:
                ledger.close()
            original_sleep(seconds)
        with patch.object(integration, "time", wraps=time) as clock:
            clock.sleep.side_effect = during_wait
            done = integration.run(self.directory)
        self.assertEqual(len(observed), 1)
        self.assertEqual(done["deadline"], observed[0]["deadline"])
        self.assertEqual(done["wait"], observed[0]["wait"])
        self.assertEqual(done["resources"]["protected_remaining"]["confirmation"], 1)

    def test_packet_deadline_denial_never_resets_campaign_or_runs_evaluator(self):
        self.directory = Path(self.temp.name) / "late"
        # Fresh fixture authorized almost an hour ago, not a rewrite of a grant.
        now = time.time()
        with patch.object(integration.time, "time", return_value=now - 3590):
            integration.initialize(self.directory, 0)
        ledger = self.open()
        grant = dict(ledger.grant())
        with self.assertRaisesRegex(ResourceError, "before durable boundary"):
            integration.run(self.directory)
        self.assertEqual(dict(ledger.grant()), grant)
        data = integration.snapshot(ledger)
        self.assertEqual(data["resource_operations"], [])
        self.assertEqual(data["measurements"], [])
        self.assertEqual(data["resources"]["spent"], 0)
        with self.assertRaisesRegex(ResourceError, "prior enforcer evidence unavailable"):
            integration.run(self.directory)
        self.assertEqual(dict(ledger.grant()), grant)

    def test_fixture_configuration_is_explicit_and_cannot_activate_real_intent(self):
        path = self.directory / "private/inventory.json"
        cfg = json.loads(path.read_text())
        cfg["providers"]["synthetic_intent_only"]["models"]["research"] = "sonnet"
        path.write_text(canonical(cfg))
        with self.assertRaisesRegex(ResourceError, "exact fresh synthetic fixture"):
            integration.open_fixture(self.directory)
        with self.assertRaises(FileExistsError):
            integration.initialize(self.directory)


if __name__ == "__main__":
    unittest.main()
