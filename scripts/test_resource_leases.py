#!/usr/bin/env python3
"""Cooperative fencing tests with synthetic trusted-observation callbacks only."""
import multiprocessing
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_resource_packets as packets
from test_resource_packets import IDENTITY, COSTS
from test_resources import NOW
from labloop_resources import Ledger, ResourceError

OTHER_IDENTITY = {**IDENTITY, "pid": 456, "start_id": "start-2"}


def lease_contender(config, owner, barrier, queue):
    ledger = Ledger(config)
    try:
        barrier.wait(timeout=10)
        token = ledger.acquire_lease(owner, {**IDENTITY, "start_id": owner}, now=NOW)
        queue.put(("admitted", token))
    except ResourceError:
        queue.put(("blocked", None))
    finally:
        ledger.close()


class LeaseTests(unittest.TestCase):
    setUp = packets.PacketTests.setUp
    write_inventory = packets.PacketTests.write_inventory
    resolve = packets.PacketTests.resolve
    v2 = packets.PacketTests.v2
    open = packets.PacketTests.open
    start = packets.PacketTests.start
    complete = packets.PacketTests.complete

    def active(self):
        ledger, token = self.start()
        ledger.reserve("session", now=NOW, lease=token, costs=COSTS)
        ledger.mark_dispatched("session", now=NOW, lease=token, job="stable-job", process=IDENTITY)
        return ledger, token

    def test_two_supervisors_compete_for_one_pool(self):
        ledger = self.open(self.v2())
        self.open(self.resolve(1))
        ctx = multiprocessing.get_context("spawn")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=lease_contender, args=(self.resolve(i), f"owner-{i}", barrier, queue)) for i in range(2)]
        try:
            for p in processes:
                p.start()
            results = [queue.get(timeout=15) for _ in processes]
            self.assertEqual(sorted(r[0] for r in results), ["admitted", "blocked"])
            for p in processes:
                p.join(timeout=10)
                self.assertEqual(p.exitcode, 0)
            self.assertEqual(ledger.db.execute("SELECT generation FROM leases").fetchone()[0], 1)
            self.assertEqual(ledger.db.execute("SELECT COUNT(*) FROM leases").fetchone()[0], 1)
        finally:
            for p in processes:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=5)
            queue.close()
            queue.join_thread()

    def test_old_worker_presumed_alive_even_after_owner_exit_and_lease_expiry(self):
        ledger, token = self.active()
        ledger.mark_uncertain("session", now=NOW + 1000, lease=token)
        seen = []
        def verifier(kind, record):
            seen.append((kind, record))
            return 0 if kind == "supervisor" else None
        recovered = self.open(verifier=verifier)
        before = list(recovered.db.iterdump())
        with self.assertRaisesRegex(ResourceError, "unknown"):
            recovered.acquire_lease("replacement", OTHER_IDENTITY, now=NOW + 10**7)
        self.assertEqual(list(recovered.db.iterdump()), before)
        self.assertEqual([k for k, _ in seen], ["supervisor", "job"])
        self.assertEqual(seen[1][1]["job"], "stable-job")
        self.assertEqual(recovered.status(now=NOW)["uncertain"], 1)
        with self.assertRaisesRegex(ResourceError, "unresolved"):
            recovered.reserve("blocked", now=NOW, lease=token, costs=COSTS)

    def test_no_bare_worker_exit_assertion_or_default_verifier(self):
        ledger, token = self.active()
        recovered = self.open()
        with self.assertRaisesRegex(ResourceError, "verifier required"):
            recovered.record_exit("session", 0, now=NOW, lease=token)
        for result in (None, True, {"exited": True}, "0"):
            recovered.exit_verifier = lambda kind, record: result
            with self.assertRaisesRegex(ResourceError, "unknown"):
                recovered.record_exit("session", 0, now=NOW, lease=token)
        recovered.exit_verifier = lambda kind, record: 1
        with self.assertRaisesRegex(ResourceError, "differs"):
            recovered.record_exit("session", 0, now=NOW, lease=token)
        self.assertEqual(ledger.status(now=NOW)["reserved"], 1)

    def test_reconcile_fences_every_stale_session_mutation_and_renewal(self):
        ledger, old = self.active()
        recovered = self.open(verifier=lambda kind, record: -9)
        token = recovered.acquire_lease("replacement", OTHER_IDENTITY, now=NOW + 1000)
        self.assertEqual(token["generation"], old["generation"] + 1)
        self.assertEqual(recovered.session("session")["exit_code"], -9)
        self.assertEqual(recovered.status(now=NOW)["spent"], 1)
        mutations = [lambda: ledger.reserve("new", now=NOW, lease=old, costs=COSTS),
                     lambda: ledger.mark_dispatched("session", now=NOW, lease=old, job="bad", process=IDENTITY),
                     lambda: ledger.cancel_undispatched("session", now=NOW, lease=old),
                     lambda: ledger.mark_uncertain("session", now=NOW, lease=old),
                     lambda: ledger.record_exit("session", -9, now=NOW, lease=old),
                     lambda: ledger.renew_lease(old, now=NOW)]
        before = list(ledger.db.iterdump())
        for mutate in mutations:
            with self.assertRaisesRegex(ResourceError, "stale"):
                mutate()
            self.assertEqual(list(ledger.db.iterdump()), before)
        with self.assertRaisesRegex(ResourceError, "another lease generation"):
            recovered.record_exit("session", -9, now=NOW, lease=token)
        recovered.reserve("replacement-job", now=NOW, lease=token, costs=COSTS)

    def test_restart_same_identity_and_settlement_are_idempotent(self):
        ledger, token = self.active()
        observed = []
        def verifier(kind, record):
            observed.append((kind, record))
            return 0
        recovered = self.open(verifier=verifier)
        before = list(ledger.db.iterdump())
        self.assertEqual(recovered.acquire_lease("owner", IDENTITY, now=NOW + 1000), token)
        self.assertEqual(list(ledger.db.iterdump()), before)
        self.assertEqual(observed, [])
        recovered.record_exit("session", 0, now=NOW + 1001, lease=token)
        after = list(ledger.db.iterdump())
        recovered.record_exit("session", 0, now=NOW + 1002, lease=token)
        self.assertEqual(list(ledger.db.iterdump()), after)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][1]["generation"], token["generation"])
        with self.assertRaisesRegex(ResourceError, "conflicting"):
            recovered.record_exit("session", 1, now=NOW, lease=token)
        with self.assertRaisesRegex(ResourceError, "only reserved"):
            recovered.mark_dispatched("session", now=NOW, lease=token, job="stable-job", process=IDENTITY)

    def test_reconciliation_rechecks_generation_after_unlocked_verifier(self):
        ledger, old = self.active()
        winner = self.open(verifier=lambda kind, record: 0)
        calls = []
        def verifier(kind, record):
            if not calls:
                calls.append(winner.acquire_lease("winner", OTHER_IDENTITY, now=NOW))
            return 0
        loser = self.open(verifier=verifier)
        with self.assertRaisesRegex(ResourceError, "changed during reconciliation"):
            loser.acquire_lease("loser", {**OTHER_IDENTITY, "pid": 789}, now=NOW)
        self.assertEqual(ledger.status(now=NOW)["lease"]["owner"], "winner")
        self.assertEqual(ledger.status(now=NOW)["lease"]["generation"], 2)
        self.assertEqual(ledger.status(now=NOW)["spent"], 1)

    def test_settlement_rechecks_fence_after_unlocked_verifier(self):
        ledger, old = self.active()
        winner = self.open(verifier=lambda kind, record: 0)
        ledger.exit_verifier = lambda kind, record: (winner.acquire_lease("winner", OTHER_IDENTITY, now=NOW) and 0)
        with self.assertRaisesRegex(ResourceError, "stale"):
            ledger.record_exit("session", 0, now=NOW, lease=old)
        self.assertEqual(ledger.status(now=NOW)["spent"], 1)

    def test_owner_exit_reconciles_only_undispatched_intent_without_job_exit(self):
        ledger, old = self.start()
        ledger.reserve("intent", now=NOW, lease=old, costs=COSTS)
        observed = []
        def verifier(kind, record):
            observed.append(kind)
            return 0
        ledger.exit_verifier = verifier
        token = ledger.acquire_lease("new-owner", OTHER_IDENTITY, now=NOW)
        self.assertEqual(observed, ["supervisor"])
        self.assertEqual(ledger.session("intent")["status"], "cancelled")
        self.assertEqual(ledger.packet_remaining()["exploration"], {d: 4 for d in COSTS})
        before = list(ledger.db.iterdump())
        self.assertEqual(ledger.acquire_lease("new-owner", OTHER_IDENTITY, now=NOW + 1), token)
        self.assertEqual(list(ledger.db.iterdump()), before)
        with self.assertRaisesRegex(ResourceError, "stale"):
            ledger.mark_dispatched("intent", now=NOW, lease=old, job="zombie", process=IDENTITY)

    def test_missing_token_and_reused_job_identity_fail_closed(self):
        ledger, token = self.start()
        with self.assertRaises(ResourceError):
            ledger.reserve("unfenced", now=NOW, costs=COSTS)
        self.complete(ledger, token, "one")
        ledger.reserve("two", now=NOW, lease=token, costs=COSTS)
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            ledger.mark_dispatched("two", now=NOW, lease=token, job="job-one", process=IDENTITY)
        self.assertEqual(ledger.session("two")["status"], "reserved")
        with self.assertRaises(ResourceError):
            ledger.mark_dispatched("two", now=NOW, lease=token, job="two", process={"pid": 123})


if __name__ == "__main__":
    unittest.main()
