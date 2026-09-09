#!/usr/bin/env python3
"""Offline acceptance tests for the explicitly synthetic discovery slice."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import labloop_discovery as demo


def recorded_worker(directory, audit_path, ready_fd=None):
    """Test-only child: record real evaluator calls and pause after durable measurement."""
    original_measure = demo.measure
    original_advance = demo.advance

    def counted_measure(candidate):
        with Path(audit_path).open("a") as audit:
            audit.write(candidate + "\n")
            audit.flush()
            os.fsync(audit.fileno())
        return original_measure(candidate)

    def pause_after_measurement(db, crash=None):
        original_advance(db, crash)
        if db.execute("SELECT 1 FROM measurements JOIN operations "
                      "ON operation_id=id WHERE status='reserved'").fetchone():
            # advance has committed evidence but has not acknowledged it by
            # settlement. The parent must explicitly SIGKILL us at this boundary.
            os.write(ready_fd, b"after_measurement\n")
            os.close(ready_fd)
            time.sleep(30)  # Bounded even if the parent fails to send its signal.
            raise TimeoutError("external SIGKILL never arrived")

    with patch.object(demo, "measure", side_effect=counted_measure):
        if ready_fd is None:
            result = demo.run(Path(directory), watch=True)
        else:
            with patch.object(demo, "advance", side_effect=pause_after_measurement):
                result = demo.run(Path(directory), watch=True)
    print(json.dumps(result))  # The killed child must never reach this final reply.


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "campaign"

    def cli(self, action, *extra):
        return subprocess.run([sys.executable, str(ROOT / "tools/lab"), "campaign", "demo",
                               action, "--directory", str(self.directory), *extra],
                              capture_output=True, text=True, timeout=10)

    def records(self, table):
        with sqlite3.connect(self.directory / "demo.sqlite3") as db:
            return db.execute(f"SELECT * FROM {table}").fetchall()

    def test_reject_pivot_wait_resume_without_mission_change(self):
        demo.initialize(self.directory, wait_seconds=30)
        before = self.records("campaign")[0][1:3]
        waiting = demo.run(self.directory)
        self.assertEqual(waiting["status"], "waiting_resource")
        self.assertEqual(waiting["findings"][0]["status"], "abandoned")
        self.assertEqual(waiting["resources"]["spent"], 1)
        # Repeated invocations while unavailable do no work and add no events.
        events = self.records("events")
        self.assertEqual(demo.run(self.directory), waiting)
        self.assertEqual(events, self.records("events"))
        with patch.object(demo.time, "time", return_value=waiting["wait"]["next_eligible_at"] + 1):
            done = demo.run(self.directory)
        self.assertEqual(done["outcome"], "synthetic_improvement_unconfirmed")
        self.assertEqual(before, self.records("campaign")[0][1:3])
        self.assertEqual(done["resources"], {"unit": "synthetic_worker_slice", "authorized": 2,
                                            "reserved": 0, "spent": 2, "available": 0})
        self.assertEqual([m["squared_error_sum"] for m in done["measurements"]], [196, 0])
        self.assertEqual(done["claim"], "untested")
        self.assertEqual(len(self.records("events")), 9)
        self.assertFalse((self.directory / "state.json").exists())
        self.assertFalse((self.directory / "events.jsonl").exists())

    def test_real_process_crashes_retain_reservation_and_reconcile(self):
        for boundary in ("after_reservation", "after_measurement"):
            with self.subTest(boundary=boundary):
                self.directory = Path(self.temp.name) / boundary
                demo.initialize(self.directory, wait_seconds=0)
                crashed = self.cli("run", "--simulate-crash", boundary)
                self.assertEqual(crashed.returncode, 75, crashed.stderr)
                db = demo.connect(self.directory)
                data = demo.snapshot(db)
                db.close()
                self.assertEqual(data["resources"]["reserved"], 1)
                self.assertEqual(data["resources"]["spent"], 0)
                if boundary == "after_measurement":
                    original_measure = demo.measure
                    def forbid_duplicate(candidate):
                        self.assertNotEqual(candidate, "constant-zero")
                        return original_measure(candidate)
                    with patch.object(demo, "measure", side_effect=forbid_duplicate):
                        done = demo.run(self.directory, watch=True)
                else:
                    done = demo.run(self.directory, watch=True)
                self.assertEqual(done["status"], "completed")
                self.assertEqual(len(done["measurements"]), 2)
                self.assertEqual(done["resources"]["spent"], 2)

    def test_external_sigkill_after_durable_measurement_before_acknowledgment(self):
        demo.initialize(self.directory, wait_seconds=0)
        audit = Path(self.temp.name) / "evaluator-calls.txt"
        child_source = ("import sys; sys.path.insert(0, sys.argv[1]); "
                        "from test_discovery import recorded_worker; "
                        "recorded_worker(sys.argv[2], sys.argv[3], "
                        "int(sys.argv[4]) if len(sys.argv) > 4 else None)")
        command = [sys.executable, "-c", child_source, str(ROOT / "scripts"),
                   str(self.directory), str(audit)]
        ready_read, ready_write = os.pipe()
        child = None
        try:
            child = subprocess.Popen(command + [str(ready_write)], pass_fds=(ready_write,),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            os.close(ready_write)
            ready_write = None
            self.assertTrue(select.select([ready_read], [], [], 10)[0],
                            "child did not reach durable measurement within 10s")
            self.assertEqual(os.read(ready_read, 128), b"after_measurement\n")
            self.assertIsNone(child.poll(), "child exited instead of waiting for external kill")
            child.kill()  # Parent-delivered SIGKILL, not an injected os._exit.
            stdout, stderr = child.communicate(timeout=5)  # Reap before reopening.
            self.assertEqual(child.returncode, -signal.SIGKILL, stderr)
            self.assertEqual(stdout, "", "killed worker fabricated a final reply")
            self.assertEqual(stderr, "")
        finally:
            if child is not None:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=5)
            os.close(ready_read)
            if ready_write is not None:
                os.close(ready_write)

        # Fresh connection observes committed evidence, but no completion ack.
        status = self.cli("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        pending = json.loads(status.stdout)
        self.assertEqual(pending["status"], "running")
        self.assertIsNone(pending["outcome"])
        self.assertEqual(pending["claim"], "untested")
        self.assertEqual(pending["operations"], [{"id": "candidate-1",
                         "candidate": "constant-zero", "status": "reserved", "units": 1}])
        self.assertEqual(pending["resources"], {"unit": "synthetic_worker_slice",
                         "authorized": 2, "reserved": 1, "spent": 0, "available": 1})
        self.assertEqual(pending["measurements"], [demo.measure("constant-zero")])
        self.assertEqual(pending["findings"], [])
        measurements = self.records("measurements")
        events = self.records("events")
        self.assertEqual([e[0] for e in events],
                         ["created", "candidate-1:intent", "candidate-1:measured"])
        self.assertEqual(audit.read_text().splitlines(), ["constant-zero"])

        # Regenerate an honest pending report from SQLite alone, with no worker reply.
        report = self.directory / "report.md"
        report.unlink()
        db = demo.connect(self.directory)
        try:
            self.assertEqual(demo.report(db, self.directory), pending)
        finally:
            db.close()
        self.assertIn("Status: running; outcome: pending", report.read_text())
        self.assertIn("constant-zero: MSE 28.000000", report.read_text())
        self.assertIn("Pending operations: 1", report.read_text())
        self.assertEqual(self.records("events"), events)

        # A fresh interpreter recovers the recorded baseline; only square is evaluated.
        restarted = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        done = json.loads(restarted.stdout)
        self.assertEqual(audit.read_text().splitlines(), ["constant-zero", "square"])
        self.assertEqual(done["operations"], [
            {"id": "candidate-1", "candidate": "constant-zero", "status": "settled", "units": 1},
            {"id": "candidate-2", "candidate": "square", "status": "settled", "units": 1}])
        self.assertEqual(done["resources"], {"unit": "synthetic_worker_slice",
                         "authorized": 2, "reserved": 0, "spent": 2, "available": 0})
        self.assertEqual(done["measurements"], [demo.measure(c) for c in demo.CANDIDATES])
        self.assertEqual(self.records("measurements")[:1], measurements)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["outcome"], "synthetic_improvement_unconfirmed")
        self.assertEqual(done["claim"], "untested")
        self.assertEqual([(f["candidate"], f["status"]) for f in done["findings"]],
                         [("constant-zero", "abandoned"), ("square", "promising")])
        final_events = self.records("events")
        self.assertEqual(final_events[:3], events)
        self.assertEqual([e[0] for e in final_events], [
            "created", "candidate-1:intent", "candidate-1:measured", "candidate-1:settled",
            "quota-wait", "candidate-2:intent", "candidate-2:measured", "candidate-2:settled",
            "completed"])
        self.assertIn("Not live research; no confirmed claim.", report.read_text())
        expected_report = report.read_bytes()
        tables = {t: self.records(t) for t in
                  ("campaign", "operations", "measurements", "findings", "events")}
        report.unlink()
        repeated = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout), done)
        self.assertEqual(report.read_bytes(), expected_report)
        self.assertEqual(audit.read_text().splitlines(), ["constant-zero", "square"])
        self.assertEqual({t: self.records(t) for t in tables}, tables)

    def test_restart_after_report_loss_is_idempotent(self):
        demo.initialize(self.directory, wait_seconds=0)
        done = demo.run(self.directory, watch=True)
        events = self.records("events")
        report = self.directory / "report.md"
        expected = report.read_bytes()
        report.unlink()  # Reports are regenerable views, never source evidence.
        self.assertEqual(demo.run(self.directory), done)
        self.assertEqual(report.read_bytes(), expected)
        self.assertEqual(events, self.records("events"))

    def test_deadline_includes_wait_and_requires_no_model_finalization(self):
        demo.initialize(self.directory, wait_seconds=60, wall_seconds=1)
        waiting = demo.run(self.directory)
        with patch.object(demo.time, "time", return_value=waiting["deadline"] + 1):
            done = demo.run(self.directory)
        self.assertEqual(done["outcome"], "inconclusive_deadline")
        self.assertEqual(len(done["operations"]), 1)
        self.assertIn("Not live research", (self.directory / "report.md").read_text())

    def test_pending_intent_at_deadline_is_not_free_or_replayed(self):
        demo.initialize(self.directory)
        self.assertEqual(self.cli("run", "--simulate-crash", "after_reservation").returncode, 75)
        with patch.object(demo.time, "time", return_value=10**12), patch.object(
                demo, "measure", side_effect=AssertionError("must not dispatch")):
            done = demo.run(self.directory)
        self.assertEqual(done["resources"]["reserved"], 1)
        self.assertEqual(done["measurements"], [])

    def test_completed_measurement_reconciled_even_after_deadline(self):
        demo.initialize(self.directory)
        self.assertEqual(self.cli("run", "--simulate-crash", "after_measurement").returncode, 75)
        with patch.object(demo.time, "time", return_value=10**12):
            done = demo.run(self.directory)
        self.assertEqual(done["resources"]["spent"], 1)
        self.assertEqual(done["resources"]["reserved"], 0)
        self.assertEqual(done["outcome"], "inconclusive_deadline")

    def test_second_executor_rejected(self):
        demo.initialize(self.directory)
        with (self.directory / "executor.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.cli("run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another demo executor", result.stderr)
        self.assertEqual(self.records("operations"), [])

    def test_init_cannot_reset_database_or_invalid_limits(self):
        with self.assertRaises(ValueError):
            demo.initialize(self.directory, wall_seconds=0)
        self.assertFalse(self.directory.exists())
        demo.initialize(self.directory)
        before = hashlib.sha256((self.directory / "demo.sqlite3").read_bytes()).hexdigest()
        result = self.cli("init")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, hashlib.sha256((self.directory / "demo.sqlite3").read_bytes()).hexdigest())

    def test_status_does_not_create_missing_database(self):
        self.assertNotEqual(self.cli("status").returncode, 0)
        self.assertFalse(self.directory.exists())

    def test_altered_mission_rejected_not_silently_migrated(self):
        demo.initialize(self.directory)
        with sqlite3.connect(self.directory / "demo.sqlite3") as db:
            db.execute("UPDATE campaign SET mission='{}'")
        self.assertNotEqual(self.cli("run").returncode, 0)
        self.assertEqual(self.records("operations"), [])

    def test_invalid_evidence_never_promising_and_recovery_preserves_bytes(self):
        valid = demo.measure("square")
        fixtures = [None, [], "malformed", {}, {**valid, "validity": "invalid"},
                    {**valid, "squared_error_sum": float("nan")},
                    {**valid, "squared_error_sum": float("inf")},
                    {**valid, "squared_error_sum": -1},
                    {**valid, "squared_error_sum": True},
                    {**valid, "sample_count": 0}, {**valid, "sample_count": True},
                    {**valid, "data_hash": "leaked-training-data"},
                    {**valid, "artifact_hash": "different-candidate"},
                    {**valid, "evaluator": "unregistered"},
                    {**valid, "seed": 1}, {**valid, "leakage": True}]
        original = demo.measure
        for index, evidence in enumerate(fixtures):
            with self.subTest(index=index):
                self.directory = Path(self.temp.name) / str(index)
                demo.initialize(self.directory, wait_seconds=0)
                with patch.object(demo, "measure", side_effect=lambda c: original(c) if c == "constant-zero" else evidence):
                    done = demo.run(self.directory, watch=True)
                self.assertEqual(done["outcome"], "inconclusive_invalid_evidence")
                self.assertNotIn("promising", [f["status"] for f in done["findings"]])
                before = self.records("measurements")
                with patch.object(demo, "measure", side_effect=AssertionError("no reevaluation")):
                    demo.run(self.directory)
                self.assertEqual(before, self.records("measurements"))
                self.assertIn("invalid evaluator evidence", (self.directory / "report.md").read_text())

    def test_poor_tie_and_nonzero_improvement_use_original_baseline_and_gate(self):
        original = demo.measure
        for score, outcome, status in [(343, "no_qualifying_improvement", "abandoned"),
                                        (196, "no_improvement_tie", "tied"),
                                        (7, "no_qualifying_improvement", "abandoned")]:
            with self.subTest(score=score):
                self.directory = Path(self.temp.name) / str(score)
                demo.initialize(self.directory, wait_seconds=0)
                def fixture(candidate):
                    evidence = original(candidate)
                    if candidate == "square":
                        evidence["squared_error_sum"] = score
                    return evidence
                with patch.object(demo, "measure", side_effect=fixture):
                    done = demo.run(self.directory, watch=True)
                self.assertEqual(done["outcome"], outcome)
                self.assertEqual(done["findings"][1]["status"], status)
                self.assertEqual(done["measurements"][0], original("constant-zero"))
                self.assertIn("constant-zero: MSE 28.000000", (self.directory / "report.md").read_text())

    def test_subnormal_positive_error_cannot_pass_frozen_zero_gate(self):
        original = demo.measure
        evidence = {**original("square"), "squared_error_sum": 5e-324}
        self.assertEqual(evidence["squared_error_sum"] / evidence["sample_count"], 0.0)
        demo.initialize(self.directory, wait_seconds=0)
        with patch.object(demo, "measure", side_effect=lambda c: original(c) if c == "constant-zero" else evidence):
            done = demo.run(self.directory, watch=True)
        self.assertEqual(done["outcome"], "no_qualifying_improvement")
        self.assertEqual(done["findings"][1]["status"], "abandoned")
        self.assertEqual(done["measurements"], [original("constant-zero"), evidence])
        self.assertIn("raw squared error sum 5e-324", (self.directory / "report.md").read_text())
        before = self.records("measurements")
        with patch.object(demo, "measure", side_effect=AssertionError("no reevaluation")):
            self.assertEqual(demo.run(self.directory), done)
        self.assertEqual(self.records("measurements"), before)

    def test_raw_error_comparisons_do_not_round_nonzero_baselines_into_ties(self):
        original = demo.measure
        tiny = 5e-324
        cases = [(tiny * 2, tiny, "abandoned"), (tiny, tiny * 2, "abandoned"),
                 (tiny, tiny, "tied"), (tiny, 0, "promising"),
                 (0, tiny, "abandoned"), (0, 0, "tied"),
                 (2**56, 2**56 + 1, "abandoned"), (2**56 + 1, 2**56, "abandoned"),
                 (2**56, 2**56, "tied")]
        for index, (baseline, score, status) in enumerate(cases):
            with self.subTest(baseline=baseline, score=score):
                self.assertEqual(baseline / 7, score / 7, "fixture must collide after division")
                self.directory = Path(self.temp.name) / str(index)
                demo.initialize(self.directory, wait_seconds=0)
                def fixture(candidate):
                    return {**original(candidate), "squared_error_sum": baseline if candidate == "constant-zero" else score}
                with patch.object(demo, "measure", side_effect=fixture):
                    done = demo.run(self.directory, watch=True)
                self.assertEqual(done["findings"][1]["status"], status)
                outcome = {"abandoned": "no_qualifying_improvement", "tied": "no_improvement_tie",
                           "promising": "synthetic_improvement_unconfirmed"}[status]
                self.assertEqual(done["outcome"], outcome)
                self.assertEqual([m["squared_error_sum"] for m in done["measurements"]], [baseline, score])

    def test_malformed_persisted_json_is_invalid_not_replaced_on_recovery(self):
        demo.initialize(self.directory, wait_seconds=0)
        db = demo.connect(self.directory)
        try:
            demo.advance(db)  # Durable baseline intent, no evaluator response yet.
            db.execute("INSERT INTO measurements VALUES (?, ?)", ("candidate-1", "{malformed"))
        finally:
            db.close()
        before = self.records("measurements")
        original = demo.measure
        with patch.object(demo, "measure", side_effect=lambda c: original(c) if c == "square" else self.fail("replayed evidence")):
            done = demo.run(self.directory, watch=True)
        self.assertEqual(done["outcome"], "inconclusive_invalid_evidence")
        self.assertEqual(self.records("measurements")[:1], before)
        self.assertEqual([f["status"] for f in done["findings"]], ["invalid", "inconclusive"])

    def test_duplicate_evaluator_json_fields_are_invalid(self):
        evidence = json.dumps(demo.measure("square"))
        raw = evidence[:-1] + ', "squared_error_sum": 0}'
        self.assertIsNone(demo.decode_evidence(raw))
        self.assertEqual(demo.finding(None, "square", demo.decode_evidence(raw))[0], "invalid")

    def test_invalid_baseline_prevents_zero_error_claim(self):
        original = demo.measure
        demo.initialize(self.directory, wait_seconds=0)
        with patch.object(demo, "measure", side_effect=lambda c: {} if c == "constant-zero" else original(c)):
            done = demo.run(self.directory, watch=True)
        self.assertEqual(done["outcome"], "inconclusive_invalid_evidence")
        self.assertEqual(done["findings"][1]["status"], "inconclusive")

    def test_cli_foreground_timer_finishes(self):
        self.assertEqual(self.cli("init", "--wait-seconds", "1").returncode, 0)
        result = self.cli("run", "--watch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
