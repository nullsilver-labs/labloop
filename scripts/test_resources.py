#!/usr/bin/env python3
"""No-network tests for private config and account-wide local slice admission."""
import copy
import json
import multiprocessing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from labloop_resources import Ledger, ResourceError, resolve

NOW = 1788696000  # fixed UTC time; no inference, no real subscription telemetry


def contender(config, name, barrier, queue):
    ledger = Ledger(config)
    try:
        barrier.wait(timeout=10)
        ledger.reserve(name, now=NOW)
        queue.put("admitted")
    except ResourceError:
        queue.put("blocked")
    finally:
        ledger.close()


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.inventory_path = self.private / "resources.json"
        self.inventory = {
            "schema_version": 1, "ledger_path": str(self.private / "resources.sqlite3"),
            "new_cash_spending": {"enabled": False, "currency": "EUR", "monthly_limit": "0.00"},
            "providers": {"claude_personal": {"enabled": True, "adapter": "claude_code_cli",
                "authentication": "native_subscription", "pool": "claude_max", "models": {"research": "sonnet"},
                "allow_subagents": False, "allow_paid_features": False}},
            "pools": {"claude_max": {"kind": "subscription", "max_parallel_sessions": 1,
                "max_worker_slices_per_day": 3, "max_turns_per_slice": 20,
                "max_slice_wall_seconds": 900, "allow_paid_overage": False}},
        }
        self.write_inventory()
        self.policies = []
        for project in ("project-a", "project-b"):
            folder = self.root / project
            folder.mkdir(mode=0o700)
            (folder / "MISSION.md").write_text("Study a fixed objective against a fixed baseline.\n")
            policy = {"schema_version": 1, "project_id": project, "mode": "discovery",
                      "mission_file": "MISSION.md", "routing": {"research": ["claude_personal:research"]},
                      "allocations": {"claude_max": {"campaign_slices": 4, "daily_slices": 3,
                          "confirmation_slices": 1, "finalization_slices": 1}}, "max_campaign_wall_hours": 168}
            path = folder / "labloop.json"
            path.write_text(json.dumps(policy))
            self.policies.append(path)
        self.config = self.resolve()

    def write_inventory(self):
        self.inventory_path.write_text(json.dumps(self.inventory))
        self.inventory_path.chmod(0o600)

    def resolve(self, project=0):
        return resolve(self.inventory_path, self.policies[project])

    def ledger(self, project=0, authorize=True):
        cfg = self.resolve(project)
        ledger = Ledger(cfg, create=authorize)
        self.addCleanup(ledger.close)
        if authorize:
            ledger.authorize(cfg["authorization_hash"], now=NOW)
        return ledger

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "tools/lab"), *args,
                               "--inventory", str(self.inventory_path), "--policy", str(self.policies[0])],
                              capture_output=True, text=True, timeout=15)

    def complete(self, ledger, name, purpose="exploration", now=NOW):
        ledger.reserve(name, purpose, now=now)
        ledger.mark_dispatched(name, now=now)
        ledger.record_exit(name, 0, now=now + 1)

    def test_validate_and_route_make_no_ledger_and_never_claim_live_eligibility(self):
        for args in (("resources", "validate"), ("route", "explain", "research")):
            result = self.cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["authorization_hash"], self.config["authorization_hash"])
            self.assertFalse(data["eligible_for_live_dispatch"])
            self.assertEqual(data["vendor_capacity"], "unknown")
        self.assertFalse(Path(self.inventory["ledger_path"]).exists())

    def test_hash_bound_authorization_is_idempotent_never_resets_spending_or_deadline(self):
        ledger = self.ledger()
        original = ledger.authorize(self.config["authorization_hash"], now=NOW)
        self.complete(ledger, "slice-one")
        repeated = ledger.authorize(self.config["authorization_hash"], now=NOW + 10**7)
        self.assertEqual(original, repeated)
        self.assertEqual(ledger.status(now=NOW)["spent"], 1)
        with self.assertRaisesRegex(ResourceError, "deadline"):
            ledger.reserve("slice-too-late", now=NOW + 10**7)
        with self.assertRaisesRegex(ResourceError, "hash"):
            ledger.authorize("wrong")

    def test_cli_wrong_hash_cannot_even_create_ledger(self):
        result = self.cli("campaign", "authorize", "--expected-hash", "wrong")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(Path(self.inventory["ledger_path"]).exists())

    def test_mission_change_invalidates_authorization(self):
        self.ledger()
        (self.policies[0].parent / "MISSION.md").write_text("A different objective")
        cfg = self.resolve()
        self.assertNotEqual(cfg["authorization_hash"], self.config["authorization_hash"])
        with LedgerContext(cfg) as changed:
            with self.assertRaisesRegex(ResourceError, "changed"):
                changed.reserve("changed", now=NOW)
            with self.assertRaisesRegex(ResourceError, "different hash"):
                changed.authorize(cfg["authorization_hash"])

    def test_approved_snapshot_is_durable_but_not_printed_by_cli(self):
        mission = self.policies[0].parent / "MISSION.md"
        mission.write_text("Private mission sentinel: DO-NOT-PRINT-THIS-TEXT")
        config = self.resolve()
        result = self.cli("campaign", "authorize", "--expected-hash", config["authorization_hash"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DO-NOT-PRINT-THIS-TEXT", result.stdout)
        with sqlite3.connect(self.inventory["ledger_path"]) as db:
            approved = json.loads(db.execute("SELECT approved_config FROM grants").fetchone()[0])
        self.assertEqual(approved["mission_text"], mission.read_text())
        self.assertEqual(approved["policy"]["project_id"], "project-a")

    def test_resolved_config_cannot_be_accidentally_mutated_before_open(self):
        config = self.resolve()
        config["inventory"]["pools"]["claude_max"]["max_worker_slices_per_day"] = 99
        with self.assertRaisesRegex(ResourceError, "modified"):
            Ledger(config, create=True)
        self.assertFalse(Path(self.inventory["ledger_path"]).exists())

    def test_changed_inventory_cannot_raise_authoritative_ceilings(self):
        self.ledger()
        self.inventory["pools"]["claude_max"]["max_worker_slices_per_day"] = 10
        self.write_inventory()
        with self.assertRaisesRegex(ResourceError, "authoritative ledger"):
            Ledger(self.resolve(), create=True)

    def test_two_processes_two_projects_only_one_admitted(self):
        a, b = self.ledger(0), self.ledger(1)
        # Two of three account slices are spent: contenders race for the last one.
        self.complete(a, "a-before-race")
        self.complete(b, "b-before-race")
        ctx = multiprocessing.get_context("spawn")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=contender, args=(self.resolve(i), f"race-{i}", barrier, queue)) for i in range(2)]
        try:
            for p in processes:
                p.start()
            outcomes = sorted(queue.get(timeout=15) for _ in processes)
            for p in processes:
                p.join(timeout=10)
                self.assertEqual(p.exitcode, 0)
            self.assertEqual(outcomes, ["admitted", "blocked"])
            winner = a.db.execute("SELECT id, project FROM sessions WHERE status='reserved'").fetchone()
            owner, other = (a, b) if winner["project"] == "project-a" else (b, a)
            owner.mark_dispatched(winner["id"], now=NOW)
            owner.record_exit(winner["id"], 0, now=NOW)
            with self.assertRaisesRegex(ResourceError, "account daily"):
                other.reserve("loser-retry", now=NOW)
        finally:
            for p in processes:
                if p.is_alive():
                    p.terminate()
                    p.join()
            queue.close()
            queue.join_thread()

    def test_shared_account_daily_limit_across_projects(self):
        a, b = self.ledger(0), self.ledger(1)
        self.complete(a, "a1")
        self.complete(b, "b1")
        self.complete(a, "a2")
        with self.assertRaisesRegex(ResourceError, "account daily"):
            b.reserve("b2", now=NOW)
        # Tomorrow restores only the local daily allowance, not campaign budgets.
        self.complete(b, "b2", now=NOW + 86400)
        with self.assertRaisesRegex(ResourceError, "exploration slice allocation"):
            b.reserve("b3", now=NOW + 86400)

    def test_protected_confirmation_and_finalization_are_not_exploration(self):
        ledger = self.ledger()
        self.complete(ledger, "explore-1")
        self.complete(ledger, "explore-2")
        with self.assertRaisesRegex(ResourceError, "protected"):
            ledger.reserve("explore-3", now=NOW)
        self.complete(ledger, "confirm", "confirmation")
        self.complete(ledger, "finalize", "finalization", now=NOW + 86400)
        status = ledger.status(now=NOW + 86400)
        self.assertEqual(status["spent"], 4)
        self.assertEqual(status["remaining_total"], 0)
        self.assertEqual(status["available_for_exploration"], 0)
        self.assertEqual(status["protected_remaining"], {"confirmation": 0, "finalization": 0})
        with self.assertRaisesRegex(ResourceError, "finalization slice allocation"):
            ledger.reserve("extra-finalize", "finalization", now=NOW + 86400)

    def test_uncertain_use_survives_reopen_and_never_releases_slot_on_timeout(self):
        a, b = self.ledger(0), self.ledger(1)
        a.reserve("unknown", now=NOW)
        a.mark_dispatched("unknown", now=NOW)
        a.mark_uncertain("unknown", now=NOW + 901)
        a.mark_uncertain("unknown", now=NOW + 902)
        with LedgerContext(self.config) as recovered:
            status = recovered.status(now=NOW + 86400)
            self.assertEqual(status["uncertain"], 1)
            self.assertEqual(status["remaining_total"], 3)
            with self.assertRaisesRegex(ResourceError, "cannot be cancelled"):
                recovered.cancel_undispatched("unknown")
            with self.assertRaisesRegex(ResourceError, "unresolved"):
                b.reserve("blocked", now=NOW + 86400)
            recovered.record_exit("unknown", 1, now=NOW + 86400)
            recovered.record_exit("unknown", 1, now=NOW + 86400 + 1)
            self.assertEqual(recovered.status()["spent"], 1)
            self.assertEqual(recovered.status()["uncertain"], 0)
        b.reserve("unblocked", now=NOW + 86400)

    def test_exit_observation_conflict_and_undispatched_settlement_rejected(self):
        ledger = self.ledger()
        ledger.reserve("reserved", now=NOW)
        with self.assertRaisesRegex(ResourceError, "only dispatched"):
            ledger.record_exit("reserved", 0)
        ledger.mark_dispatched("reserved", now=NOW)
        ledger.record_exit("reserved", 0)
        with self.assertRaisesRegex(ResourceError, "conflicting exit"):
            ledger.record_exit("reserved", 1)

    def test_idempotency_keys_do_not_dispatch_or_charge_twice(self):
        a, b = self.ledger(0), self.ledger(1)
        original = a.reserve("stable-id", now=NOW)
        self.assertEqual(a.reserve("stable-id", now=NOW + 1), original)
        with self.assertRaisesRegex(ResourceError, "another operation"):
            b.reserve("stable-id", now=NOW)
        a.mark_dispatched("stable-id", now=NOW)
        with self.assertRaisesRegex(ResourceError, "only reserved"):
            a.mark_dispatched("stable-id", now=NOW)
        a.record_exit("stable-id", 0)
        self.assertEqual(a.reserve("stable-id", now=NOW)["status"], "settled")
        self.assertEqual(a.status()["spent"], 1)

    def test_cancel_only_before_dispatch_and_cannot_reuse_cancelled_id(self):
        ledger = self.ledger()
        ledger.reserve("cancel", now=NOW)
        ledger.cancel_undispatched("cancel", now=NOW)
        ledger.cancel_undispatched("cancel", now=NOW)
        self.assertEqual(ledger.reserve("cancel", now=NOW)["status"], "cancelled")
        with self.assertRaisesRegex(ResourceError, "only reserved"):
            ledger.mark_dispatched("cancel", now=NOW)
        self.assertEqual(ledger.status()["remaining_total"], 4)
        self.assertEqual(ledger.status()["available_for_exploration"], 2)
        ledger.reserve("replacement", now=NOW)

    def test_reservation_must_not_bypass_new_day_or_campaign_deadline(self):
        ledger = self.ledger()
        ledger.reserve("old", now=NOW)
        with self.assertRaisesRegex(ResourceError, "day changed"):
            ledger.mark_dispatched("old", now=NOW + 86400)
        with self.assertRaisesRegex(ResourceError, "campaign deadline"):
            ledger.mark_dispatched("old", now=NOW + 10**7)
        self.assertEqual(ledger.status()["reserved"], 1)

    def test_cross_project_session_mutations_rejected(self):
        a, b = self.ledger(0), self.ledger(1)
        a.reserve("owned", now=NOW)
        with self.assertRaisesRegex(ResourceError, "not owned"):
            b.cancel_undispatched("owned")

    def test_private_permissions_symlinks_and_repository_locations(self):
        self.inventory_path.chmod(0o644)
        with self.assertRaisesRegex(ResourceError, "group/other"):
            self.resolve()
        self.inventory_path.chmod(0o600)
        unsafe = self.policies[0].parent / "resources.json"
        unsafe.write_text(json.dumps(self.inventory))
        unsafe.chmod(0o600)
        with self.assertRaisesRegex(ResourceError, "outside"):
            resolve(unsafe, self.policies[0])
        self.inventory["ledger_path"] = str(self.policies[0].parent / "resources.sqlite3")
        self.write_inventory()
        with self.assertRaisesRegex(ResourceError, "outside"):
            self.resolve()
        target = self.private / "actual"
        target.write_text("")
        target.chmod(0o600)
        link = self.private / "symlink"
        link.symlink_to(target)
        self.inventory["ledger_path"] = str(link)
        self.write_inventory()
        with self.assertRaisesRegex(ResourceError, "symlink"):
            Ledger(self.resolve(), create=True)

    def test_unsafe_private_ledger_directory_rejected(self):
        self.private.chmod(0o755)
        with self.assertRaisesRegex(ResourceError, "group/other"):
            Ledger(self.config, create=True)

    def test_unknown_fields_paid_routes_multiple_pools_and_boolean_limits_rejected(self):
        original = copy.deepcopy(self.inventory)
        alterations = [
            lambda i: i.update({"ignored_safety_setting": True}),
            lambda i: i["new_cash_spending"].update({"enabled": True}),
            lambda i: i["new_cash_spending"].update({"monthly_limit": "1.00"}),
            lambda i: i["providers"]["claude_personal"].update({"adapter": "configured_api"}),
            lambda i: i["providers"]["claude_personal"].update({"allow_subagents": True}),
            lambda i: i["providers"]["claude_personal"].update({"allow_paid_features": True}),
            lambda i: i["providers"]["claude_personal"].update({"enabled": False}),
            lambda i: i["pools"]["claude_max"].update({"allow_paid_overage": True}),
            lambda i: i["pools"]["claude_max"].update({"kind": "prepaid"}),
            lambda i: i["pools"]["claude_max"].update({"max_parallel_sessions": 2}),
            lambda i: i["pools"]["claude_max"].update({"max_worker_slices_per_day": True}),
            lambda i: i["pools"].update({"fake_new_capacity": copy.deepcopy(i["pools"]["claude_max"])}),
        ]
        for change in alterations:
            self.inventory = copy.deepcopy(original)
            change(self.inventory)
            self.write_inventory()
            with self.assertRaises(ResourceError):
                self.resolve()

    def test_duplicate_json_keys_and_nonfinite_numbers_rejected(self):
        self.inventory_path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ResourceError, "duplicate"):
            self.resolve()
        self.inventory_path.write_text('{"schema_version":NaN}')
        with self.assertRaisesRegex(ResourceError, "nonfinite"):
            self.resolve()

    def test_zero_exploration_means_disabled_not_unlimited(self):
        policy = json.loads(self.policies[0].read_text())
        policy["allocations"]["claude_max"]["campaign_slices"] = 2
        self.policies[0].write_text(json.dumps(policy))
        ledger = self.ledger()
        with self.assertRaisesRegex(ResourceError, "exploration slice allocation exhausted"):
            ledger.reserve("no-exploration", now=NOW)
        self.complete(ledger, "final-only", "finalization")

    def test_status_does_not_create_or_reset_missing_ledger(self):
        result = self.cli("budget", "status")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(Path(self.inventory["ledger_path"]).exists())

    def test_cli_authorization_and_private_status(self):
        result = self.cli("campaign", "authorize", "--expected-hash", self.config["authorization_hash"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(self.inventory["ledger_path"]).stat().st_mode & 0o777, 0o600)
        result = self.cli("budget", "status")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["authorized"], 4)
        self.assertEqual(data["vendor_capacity"], "unknown")
        self.assertFalse(data["live_dispatch_enabled"])
        self.assertFalse((self.policies[0].parent / "state.json").exists())


class LedgerContext:
    def __init__(self, config):
        self.ledger = Ledger(config)
    def __enter__(self):
        return self.ledger
    def __exit__(self, *_):
        self.ledger.close()


if __name__ == "__main__":
    unittest.main()
