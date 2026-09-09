#!/usr/bin/env python3
"""Offline v2 multidimensional accounting; never a real allowance/enforcer."""
import copy
import json
import multiprocessing
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_resources as v1
from test_resources import NOW
from labloop_resources import Ledger, ResourceError, DIMENSIONS

IDENTITY = {"host": "synthetic-host", "boot_id": "synthetic-boot", "pid": 123, "start_id": "start-1"}
COSTS = {d: 1 for d in DIMENSIONS}


def packet_contender(config, token, name, barrier, queue):
    ledger = Ledger(config)
    try:
        barrier.wait(timeout=10)
        ledger.reserve(name, now=NOW, lease=token, costs=COSTS)
        queue.put("admitted")
    except ResourceError:
        queue.put("blocked")
    finally:
        ledger.close()


class PacketTests(unittest.TestCase):
    setUp = v1.ResourceTests.setUp
    write_inventory = v1.ResourceTests.write_inventory
    resolve = v1.ResourceTests.resolve

    def v2(self, change=None):
        self.inventory["schema_version"] = 2
        self.write_inventory()
        for path in self.policies:
            policy = json.loads(path.read_text())
            policy["schema_version"] = 2
            allocation = policy["allocations"]["claude_max"]
            allocation["local_packet"] = {"inference_unit": "local_token",
                "campaign": {d: 6 for d in DIMENSIONS},
                "confirmation": dict(COSTS), "finalization": dict(COSTS)}
            if change:
                change(allocation)
            path.write_text(json.dumps(policy))
        return self.resolve()

    def open(self, config=None, verifier=None):
        config = config or self.resolve()
        ledger = Ledger(config, create=True, exit_verifier=verifier)
        self.addCleanup(ledger.close)
        ledger.authorize(config["authorization_hash"], now=NOW)
        return ledger

    def start(self, change=None):
        ledger = self.open(self.v2(change), verifier=lambda kind, record: 0)
        token = ledger.acquire_lease("owner", IDENTITY, now=NOW)
        return ledger, token

    def complete(self, ledger, token, name, costs=None, purpose="exploration", now=NOW):
        ledger.reserve(name, purpose, now=now, lease=token, costs=costs or COSTS)
        ledger.mark_dispatched(name, now=now, lease=token, job="job-" + name, process=IDENTITY)
        ledger.record_exit(name, 0, now=now + 1, lease=token)

    def test_each_dimension_exhausts_independently_without_borrowing(self):
        # Separate fresh synthetic project fixtures, never reset an activated ledger.
        for dimension in DIMENSIONS:
            with self.subTest(dimension=dimension):
                fixture = PacketTests()
                fixture.setUp()
                try:
                    ledger, token = fixture.start()
                    costs = {**COSTS, dimension: 4}
                    fixture.complete(ledger, token, "first", costs)
                    before = ledger.status(now=NOW)
                    with self.assertRaisesRegex(ResourceError, dimension):
                        ledger.reserve("denied", now=NOW, lease=token, costs=COSTS)
                    self.assertEqual(ledger.status(now=NOW), before)
                    self.assertIsNone(ledger.db.execute("SELECT * FROM session_packets WHERE session='denied'").fetchone())
                    self.assertEqual(before["local_packet_remaining"]["confirmation"], COSTS)
                    self.assertEqual(before["local_packet_remaining"]["finalization"], COSTS)
                    fixture.complete(ledger, token, "confirm", purpose="confirmation")
                    fixture.complete(ledger, token, "final", purpose="finalization")
                finally:
                    fixture.doCleanups()

    def test_worker_exhaustion_does_not_borrow_other_dimensions(self):
        ledger, token = self.start()
        self.complete(ledger, token, "first")
        self.complete(ledger, token, "second")
        with self.assertRaisesRegex(ResourceError, "slice allocation"):
            ledger.reserve("third", now=NOW, lease=token, costs=COSTS)
        self.assertEqual(ledger.packet_remaining()["exploration"], {d: 2 for d in DIMENSIONS})

    def test_deadline_wait_rechecks_entire_remaining_packet_at_dispatch(self):
        ledger, token = self.start()
        deadline = ledger.grant()["deadline"]
        ledger.reserve("waiting", now=deadline - 4, lease=token, costs=COSTS)
        before = ledger.status(now=deadline - 2)
        with self.assertRaisesRegex(ResourceError, "deadline"):
            ledger.mark_dispatched("waiting", now=deadline - 2, lease=token, job="wait-job", process=IDENTITY)
        self.assertEqual(ledger.status(now=deadline - 2), before)
        ledger.cancel_undispatched("waiting", now=deadline - 2, lease=token)
        with self.assertRaisesRegex(ResourceError, "deadline"):
            ledger.reserve("late", now=deadline - 2, lease=token, costs=COSTS)
        # Finalization may not borrow confirmation's time either.
        with self.assertRaisesRegex(ResourceError, "deadline"):
            ledger.reserve("late-final", "finalization", now=deadline - 1, lease=token, costs=COSTS)
        ledger.reserve("confirm", "confirmation", now=deadline - 2, lease=token, costs=COSTS)

    def test_remaining_protected_workers_need_all_dimensions(self):
        def change(a):
            a["campaign_slices"] = 5
            a["confirmation_slices"] = 2
            a["local_packet"]["confirmation"] = {d: 2 for d in DIMENSIONS}
        ledger, token = self.start(change)
        for dimension in DIMENSIONS:
            with self.subTest(dimension=dimension), self.assertRaisesRegex(ResourceError, "worker packet infeasible"):
                ledger.reserve("too-large", "confirmation", now=NOW, lease=token,
                               costs={**COSTS, dimension: 2})
        self.assertEqual(ledger.status(now=NOW)["reserved"], 0)
        self.complete(ledger, token, "confirm1", purpose="confirmation")
        self.complete(ledger, token, "confirm2", purpose="confirmation")

    def test_remaining_protected_wall_upper_bound_and_final_worker_are_atomic(self):
        for purpose in ("confirmation", "finalization"):
            with self.subTest(purpose=purpose):
                fixture = PacketTests()
                fixture.setUp()
                try:
                    def change(a):
                        a["campaign_slices"] = 5
                        a[purpose + "_slices"] = 2
                        a["local_packet"]["campaign"]["wall_seconds"] = 1805
                        a["local_packet"][purpose] = {**{d: 2 for d in DIMENSIONS}, "wall_seconds": 1800}
                    ledger, token = fixture.start(change)
                    before = list(ledger.db.iterdump())
                    with self.assertRaisesRegex(ResourceError, "remaining.*wall.*ceiling"):
                        ledger.reserve("undersized", purpose, now=NOW, lease=token, costs=COSTS)
                    self.assertEqual(list(ledger.db.iterdump()), before)
                    full = {**COSTS, "wall_seconds": 900}
                    fixture.complete(ledger, token, "first", full, purpose)
                    before = list(ledger.db.iterdump())
                    with self.assertRaisesRegex(ResourceError, "remaining.*wall.*ceiling"):
                        ledger.reserve("stranded-final-second", purpose, now=NOW, lease=token,
                                       costs={**COSTS, "wall_seconds": 899})
                    self.assertEqual(list(ledger.db.iterdump()), before)
                    fixture.complete(ledger, token, "last", full, purpose)
                    self.assertEqual(ledger.packet_remaining()[purpose]["wall_seconds"], 0)
                    self.assertEqual(ledger.status(now=NOW)["protected_remaining"][purpose], 0)
                finally:
                    fixture.doCleanups()

    def test_dispatch_rechecks_preexisting_infeasible_protected_wall_intent(self):
        def change(a):
            a["campaign_slices"] = 5
            a["confirmation_slices"] = 2
            a["local_packet"]["campaign"]["wall_seconds"] = 1805
            a["local_packet"]["confirmation"] = {**{d: 2 for d in DIMENSIONS}, "wall_seconds": 1800}
        ledger, token = self.start(change)
        for name, wall in (("old-first", 1), ("old-last", 899)):
            with self.subTest(name=name):
                # Model an immutable intent admitted by the pre-fix checker. Only
                # this test bypasses admission; real dispatch must recheck it.
                with patch.object(ledger, "check_packet", return_value=None):
                    ledger.reserve(name, "confirmation", now=NOW, lease=token,
                                   costs={**COSTS, "wall_seconds": wall})
                before = list(ledger.db.iterdump())
                with self.assertRaisesRegex(ResourceError, "remaining.*wall.*ceiling"):
                    ledger.mark_dispatched(name, now=NOW, lease=token, job="job-" + name, process=IDENTITY)
                self.assertEqual(list(ledger.db.iterdump()), before)
                ledger.cancel_undispatched(name, now=NOW, lease=token)
                self.complete(ledger, token, "valid-" + name, {**COSTS, "wall_seconds": 900}, "confirmation")
        self.assertEqual(ledger.packet_remaining()["confirmation"]["wall_seconds"], 0)

    def test_full_allotment_charge_immutable_across_reopen_no_refund(self):
        ledger, token = self.start()
        costs = {d: 2 for d in DIMENSIONS}
        ledger.reserve("stable", now=NOW, lease=token, costs=costs)
        with self.assertRaisesRegex(ResourceError, "immutable"):
            ledger.reserve("stable", now=NOW, lease=token, costs=COSTS)
        ledger.mark_dispatched("stable", now=NOW, lease=token, job="job", process=IDENTITY)
        ledger.exit_verifier = lambda kind, record: -9
        ledger.record_exit("stable", -9, now=NOW + 1, lease=token)
        before = ledger.status(now=NOW)
        grant = dict(ledger.grant())
        reopened = self.open()
        self.assertEqual(reopened.authorize(self.resolve()["authorization_hash"], now=NOW + 10**7), grant)
        self.assertEqual(reopened.status(now=NOW), before)
        self.assertEqual(before["local_packet_remaining"]["exploration"], {d: 2 for d in DIMENSIONS})
        self.assertFalse(before["live_dispatch_enabled"])
        self.assertEqual(before["vendor_capacity"], "unknown")
        path = self.policies[0]
        policy = json.loads(path.read_text())
        policy["allocations"]["claude_max"]["local_packet"]["campaign"]["cpu_seconds"] += 1
        path.write_text(json.dumps(policy))
        changed = self.open_without_authorize()
        with self.assertRaisesRegex(ResourceError, "changed"):
            changed.reserve("new", now=NOW, lease=token, costs=COSTS)
        with self.assertRaisesRegex(ResourceError, "changed"):
            changed.renew_lease(token, now=NOW)

    def open_without_authorize(self):
        ledger = Ledger(self.resolve())
        self.addCleanup(ledger.close)
        return ledger

    def test_v1_ledger_cannot_be_migrated_or_reset_by_v2(self):
        ledger = self.open()
        before = list(ledger.db.iterdump())
        cfg = self.v2()
        with self.assertRaisesRegex(ResourceError, "authoritative ledger"):
            Ledger(cfg, create=True)
        self.assertEqual(list(ledger.db.iterdump()), before)

    def test_strict_packet_units_fields_types_and_opt_in(self):
        self.v2()
        path = self.policies[0]
        original = json.loads(path.read_text())
        mutations = [lambda p: p.update(schema_version=1),
                     lambda p: p["allocations"]["claude_max"]["local_packet"].update(inference_unit="vendor_tokens"),
                     lambda p: p["allocations"]["claude_max"]["local_packet"].update(cash=0),
                     lambda p: p["allocations"]["claude_max"]["local_packet"]["campaign"].update(cpu_seconds=True),
                     lambda p: p["allocations"]["claude_max"]["local_packet"]["confirmation"].update(evaluator_runs=0)]
        for mutate in mutations:
            policy = copy.deepcopy(original)
            mutate(policy)
            path.write_text(json.dumps(policy))
            with self.assertRaises(ResourceError):
                self.resolve()
        path.write_text(json.dumps(original))
        ledger = self.open()
        token = ledger.acquire_lease("owner", IDENTITY, now=NOW)
        for costs in [None, {}, {**COSTS, "cash": 0}, {**COSTS, "cpu_seconds": True}, {**COSTS, "inference_units": 0}]:
            with self.assertRaises(ResourceError):
                ledger.reserve("bad", now=NOW, lease=token, costs=costs)
        self.assertEqual(ledger.status(now=NOW)["reserved"], 0)

    def test_v2_example_validation_stays_offline_and_does_not_activate(self):
        root = Path(__file__).resolve().parents[1]
        self.inventory = json.loads((root / "templates/resources.subscription.v2.example.json").read_text())
        self.inventory["ledger_path"] = str(self.private / "resources.sqlite3")
        self.write_inventory()
        self.policies[0].write_text((root / "templates/labloop.discovery.v2.example.json").read_text())
        cfg = self.resolve()
        self.assertEqual(cfg["policy"]["schema_version"], 2)
        result = v1.ResourceTests.cli(self, "route", "explain", "research")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["eligible_for_live_dispatch"])
        self.assertFalse(Path(self.inventory["ledger_path"]).exists())

    def test_daily_worker_opportunities_cannot_consume_confirmation_window(self):
        ledger, token = self.start()
        deadline = ledger.grant()["deadline"]
        self.complete(ledger, token, "early", now=deadline - 100)
        with self.assertRaisesRegex(ResourceError, "daily opportunities"):
            ledger.reserve("last-exploration", now=deadline - 90, lease=token, costs=COSTS)
        self.complete(ledger, token, "confirm", purpose="confirmation", now=deadline - 80)
        self.complete(ledger, token, "final", purpose="finalization", now=deadline - 70)

    def test_nonfinite_supervisor_time_cannot_authorize_unbounded_deadline(self):
        self.v2()
        ledger = Ledger(self.resolve(), create=True)
        self.addCleanup(ledger.close)
        for now in (float("inf"), float("nan"), True, -1):
            with self.assertRaisesRegex(ResourceError, "timestamp"):
                ledger.authorize(self.resolve()["authorization_hash"], now=now)
        self.assertEqual(ledger.db.execute("SELECT COUNT(*) FROM grants").fetchone()[0], 0)

    def test_atomic_all_or_nothing_packet_contention(self):
        ledger, token = self.start()
        ctx = multiprocessing.get_context("spawn")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=packet_contender, args=(self.resolve(), token, f"race-{i}", barrier, queue)) for i in range(2)]
        try:
            for p in processes:
                p.start()
            self.assertEqual(sorted(queue.get(timeout=15) for _ in processes), ["admitted", "blocked"])
            for p in processes:
                p.join(timeout=10)
                self.assertEqual(p.exitcode, 0)
            self.assertEqual(ledger.db.execute("SELECT COUNT(*) FROM session_packets").fetchone()[0], 1)
            self.assertEqual(ledger.packet_remaining()["exploration"], {d: 3 for d in DIMENSIONS})
        finally:
            for p in processes:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=5)
            queue.close()
            queue.join_thread()


if __name__ == "__main__":
    unittest.main()
