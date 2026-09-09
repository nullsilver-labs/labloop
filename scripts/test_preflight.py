#!/usr/bin/env python3
"""Synthetic account fixtures only. Never runs installed Claude/auth or namespaces."""
from contextlib import contextmanager
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import labloop_preflight as pre
from labloop_resources import ResourceError


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.private = self.root / "private"
        for path in (self.home, self.project, self.private):
            path.mkdir(mode=0o700)
        self.output = self.private / "status.json"
        self.config = {"project_root": str(self.project), "authorization_hash": "a" * 64}
        # Fake ELF is hashed but NEVER executed; all CLI observations are mocked.
        self.binary = self.private / "claude-fixture"
        self.binary.write_bytes(b"\x7fELFSYNTHETIC-NOT-EXECUTABLE")
        self.binary.chmod(0o700)
        self.digest = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        self.contract = pre.binary_contract(self.binary, self.digest)

    def collect(self, **kwargs):
        return pre.collect_status(self.config, self.binary, self.digest, self.home,
                                  self.output, **kwargs)

    def mock_collect(self, outputs=None):
        with patch.object(pre, "bounded", side_effect=outputs or [
                b"2.1.263 (Claude Code)\n", b'{"fixtureOnly":"PRIVATE_ACCOUNT_SENTINEL"}']) as run, \
             patch.object(pre, "conflict_snapshot", return_value="c" * 64), \
             patch.object(pre.os, "getuid", return_value=os.getuid() or 1000):
            result = self.collect(operator_inspect=True)
        return result, run

    def test_default_no_inspection_or_provider_command(self):
        with patch.object(pre, "bounded", side_effect=AssertionError("must not run")):
            self.assertFalse(pre.summary()["eligible_for_live_dispatch"])
            with self.assertRaisesRegex(ResourceError, "opt-in"):
                self.collect()
        self.assertFalse(self.output.exists())

    def test_mocked_official_command_private_output_and_unknown_identity(self):
        result, run = self.mock_collect()
        self.assertEqual(run.call_count, 2)
        args, kw = run.call_args
        self.assertEqual(args[0], [str(self.binary), *pre.STATUS_ARGS])
        self.assertNotIn("--print", args[0])
        self.assertEqual(set(kw["env"]), {"HOME", "PATH", "LANG", "DISABLE_AUTOUPDATER",
                                          "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"})
        self.assertNotEqual(kw["cwd"], str(self.project))
        self.assertEqual(kw["env"]["HOME"], str(self.home))
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        self.assertIn("PRIVATE_ACCOUNT_SENTINEL", self.output.read_text())
        self.assertNotIn("PRIVATE_ACCOUNT_SENTINEL", json.dumps(result))
        self.assertEqual(result["identity_status"], "unsupported_schema")
        self.assertFalse(result["eligible_for_live_dispatch"])

    def test_inventory_alias_never_becomes_identity(self):
        self.config["provider"] = "pretend-subscription-identity"
        self.mock_collect()
        evidence = json.loads(self.output.read_text())
        self.assertNotIn("pretend-subscription-identity", json.dumps(evidence))
        self.assertEqual(evidence["identity_status"], "unsupported_schema")

    def test_wrong_version_never_calls_auth_or_writes_evidence(self):
        with patch.object(pre, "bounded", return_value=b"2.1.262 (Claude Code)") as run, \
             patch.object(pre, "conflict_snapshot", return_value="c" * 64):
            with self.assertRaises(ResourceError):
                self.collect(operator_inspect=True)
        self.assertLessEqual(run.call_count, 1)
        self.assertFalse(self.output.exists())

    def test_binary_requires_digest_elf_exact_path_and_safe_mode(self):
        for digest in ("0" * 64, "", "bad"):
            with self.assertRaises(ResourceError):
                pre.binary_contract(self.binary, digest)
        link = self.private / "link"
        link.symlink_to(self.binary)
        with self.assertRaises(ResourceError):
            pre.binary_contract(link, self.digest)
        self.binary.chmod(0o777)
        with self.assertRaises(ResourceError):
            pre.binary_contract(self.binary, self.digest)
        self.binary.chmod(0o700)
        self.binary.write_bytes(b"#!/bin/sh\necho wrapper")
        with self.assertRaisesRegex(ResourceError, "ELF"):
            pre.binary_contract(self.binary, hashlib.sha256(self.binary.read_bytes()).hexdigest())

    def test_provider_environment_conflicts_deny_without_echoing_values(self):
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
                    "CLAUDE_CONFIG_DIR", "AWS_PROFILE", "GOOGLE_APPLICATION_CREDENTIALS",
                    "AZURE_API_KEY", "https_proxy", "LD_PRELOAD", "NODE_OPTIONS", "PYTHONPATH"):
            for value in ("PRIVATE_SENTINEL", "", "0"):
                with self.assertRaises(ResourceError) as err:
                    pre.conflict_snapshot(self.home, self.project, {key: value}, self.root / "managed")
                self.assertNotIn(key, str(err.exception))
                self.assertNotIn("PRIVATE_SENTINEL", str(err.exception))

    def snapshot(self):
        return pre.conflict_snapshot(self.home, self.project, {}, self.root / "managed")

    def test_settings_helpers_hooks_paid_paths_and_unknown_settings_denied_without_execution(self):
        folder = self.project / ".claude"
        folder.mkdir()
        settings = folder / "settings.json"
        for config in ({"apiKeyHelper": "touch NEVER"}, {"env": {"ANTHROPIC_API_KEY": "SECRET"}},
                       {"hooks": {"SessionStart": "touch NEVER"}}, {"unknown": True}):
            settings.write_text(json.dumps(config))
            settings.chmod(0o600)
            with self.assertRaises(ResourceError):
                self.snapshot()
        self.assertFalse((self.project / "NEVER").exists())
        settings.write_text("{}")
        self.assertRegex(self.snapshot(), "^[a-f0-9]{64}$")
        settings.write_text('{"x":1,"x":2}')
        with self.assertRaises(ResourceError):
            self.snapshot()

    def test_ancestor_local_managed_and_opaque_paths_denied(self):
        for path in (self.root / ".claude/settings.local.json",
                     self.home / ".claude/settings.json", self.root / "managed/managed-settings.json"):
            path.parent.mkdir(exist_ok=True)
            path.write_text('{"apiKeyHelper":"SECRET"}')
            path.chmod(0o600)
            with self.assertRaises(ResourceError):
                self.snapshot()
            path.unlink()
        for path in (self.home / ".claude.json", self.root / "managed/managed-settings.d"):
            path.write_text("not read: private auth material")
            with patch.object(pre, "load_json", side_effect=AssertionError("opaque must not be read")):
                with self.assertRaises(ResourceError):
                    self.snapshot()
            path.unlink()

    def test_settings_symlink_denied_and_credentials_never_read(self):
        folder = self.home / ".claude"
        folder.mkdir()
        credentials = folder / ".credentials.json"
        credentials.write_text("PRIVATE_NOT_JSON")
        with patch.object(pre, "load_json", side_effect=AssertionError("credential read")):
            self.snapshot()
        settings = folder / "settings.json"
        settings.symlink_to(credentials)
        with self.assertRaises(ResourceError):
            self.snapshot()
        settings.unlink()
        os.link(credentials, settings)
        with patch.object(pre, "load_json", side_effect=AssertionError("hardlink credential read")):
            with self.assertRaises(ResourceError):
                self.snapshot()
        settings.unlink()
        credentials.unlink()
        folder.rmdir()
        alternate = self.root / "alternate"
        alternate.mkdir()
        (alternate / "settings.json").write_text("{}")
        folder.symlink_to(alternate, target_is_directory=True)
        with self.assertRaises(ResourceError):
            self.snapshot()

    def test_config_race_denied_without_evidence(self):
        with patch.object(pre, "bounded", side_effect=[b"2.1.263 (Claude Code)", b"{}"]), \
             patch.object(pre, "conflict_snapshot", side_effect=["before", "after"]):
            with self.assertRaises(ResourceError):
                self.collect(operator_inspect=True)
        self.assertFalse(self.output.exists())

    def test_evidence_is_exclusive_private_and_outside_project(self):
        pre.private_write(self.output, {"private": True}, self.project)
        with self.assertRaises(ResourceError):
            pre.private_write(self.output, {}, self.project)
        self.assertEqual(json.loads(self.output.read_text()), {"private": True})
        with self.assertRaises(ResourceError):
            pre.private_write(self.project / "evidence", {}, self.project)
        self.private.chmod(0o755)
        with self.assertRaises(ResourceError):
            pre.private_write(self.private / "unsafe", {}, self.project)

    def test_status_stale_future_conflicting_and_forged_live_claim_denied(self):
        self.mock_collect()
        evidence = json.loads(self.output.read_text())
        now = evidence["observed_at"]
        check = lambda e, n: pre.validate_status_evidence(e, self.config["authorization_hash"],
                                                         self.contract, evidence["context_hash"], n)
        self.assertFalse(check(evidence, now)["eligible_for_live_dispatch"])
        for n in (now - 1, now + pre.STATUS_TTL):
            with self.assertRaises(ResourceError):
                check(evidence, n)
        for key, val in (("authorization_hash", "bad"), ("binary", {}), ("context_hash", "bad"),
                         ("identity_status", "verified"), ("eligible_for_live_dispatch", True)):
            changed = {**evidence, key: val}
            with self.assertRaises(ResourceError):
                check(changed, now)

    def test_attestation_is_explicit_expiring_identity_config_version_bound_not_verification(self):
        binding = {key: "a" * 64 for key in ("declared_identity_sha256", "authorization_hash", "binary_sha256",
                                             "context_hash", "status_evidence_sha256")}
        binding["cli_version"] = pre.CLAUDE_VERSION
        att = {"schema_version": 1, "kind": "operator_attestation_not_provider_verification",
               "binding": binding, "issued_at": 100, "expires_at": 200,
               "overage_disabled": True, "auto_replenishment_disabled": True}
        result = pre.validate_attestation(att, binding, 100)
        self.assertFalse(result["provider_verified"])
        self.assertFalse(result["identity_verified"])
        self.assertFalse(result["eligible_for_live_dispatch"])
        for now in (99, 200):
            with self.assertRaises(ResourceError):
                pre.validate_attestation(att, binding, now)
        for key in binding:
            changed = copy.deepcopy(att)
            changed["binding"][key] = "other"
            with self.assertRaises(ResourceError):
                pre.validate_attestation(changed, binding, 100)
        for key, value in (("overage_disabled", False), ("auto_replenishment_disabled", 1),
                           ("expires_at", 1000000), ("issued_at", True), ("kind", "provider_verified")):
            with self.assertRaises(ResourceError):
                pre.validate_attestation({**att, key: value}, binding, 100)

    def test_cli_static_status_no_sensitive_output(self):
        run = subprocess.run([sys.executable, str(ROOT / "tools/lab"), "preflight", "status"],
                             capture_output=True, timeout=10, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(json.loads(run.stdout)["eligible_for_live_dispatch"])
        self.assertNotIn("raw_status", run.stdout)

    def test_bounded_trusted_fixture_environment_and_inherited_fds(self):
        # Actual host subprocess, but ONLY Python synthetic fixture; no provider.
        secret = os.open(self.binary, os.O_RDONLY)
        os.set_inheritable(secret, True)
        self.addCleanup(os.close, secret)
        source = ('import os,json\n'
                  'try: os.fstat(' + str(secret) + '); leaked=True\n'
                  'except OSError: leaked=False\n'
                  'print(json.dumps([dict(os.environ),leaked]))')
        raw = pre.bounded([sys.executable, "-I", "-S", "-c", source], cwd=self.root,
                          env={"LC_ALL": "C", "PYTHONCOERCECLOCALE": "0"})
        env, leaked = json.loads(raw)
        self.assertFalse(leaked)
        self.assertNotIn("HOME", env)
        self.assertNotIn("ANTHROPIC_API_KEY", env)

    def test_bounded_fixture_descendant_cannot_keep_output_open_after_parent_exit(self):
        source = "import os,time\nif os.fork() == 0: time.sleep(10)\nelse: os._exit(0)"
        start = time.monotonic()
        # RLIMIT_NPROC counts all host processes of this UID, not just this tool.
        # Keep the production ceiling unchanged; isolate group-cleanup testing
        # from unrelated host occupancy by mocking ONLY this one limit.
        real_setrlimit = pre.resource.setrlimit
        def fixture_limits(kind, limits):
            if kind != pre.resource.RLIMIT_NPROC:
                real_setrlimit(kind, limits)
        with patch.object(pre.resource, "setrlimit", side_effect=fixture_limits):
            with self.assertRaisesRegex(ResourceError, "timed out"):
                pre.bounded([sys.executable, "-I", "-S", "-c", source], cwd=self.root, env={}, seconds=0.2)
        self.assertLess(time.monotonic() - start, 2)

    @contextmanager
    def supervisor_fixture(self, pause_before_arm=False, close_output=False):
        # Adopt/reap the synthetic child after an abruptly killed outer process;
        # do not leave cleanup to the host's PID 1. This is process-local prctl,
        # not namespace creation or host configuration.
        libc = ctypes.CDLL(None, use_errno=True)
        previous = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(previous), 0, 0, 0), 0)  # GET_CHILD_SUBREAPER
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)  # SET_CHILD_SUBREAPER
        ready, release, executed = (self.root / name for name in ("child-pid", "release", "executed"))
        for path in (ready, release, executed):
            path.unlink(missing_ok=True)
        child_source = (f"import os,time;from pathlib import Path;Path({str(executed)!r}).touch();"
                        + ("os.close(1);os.close(2);" if close_output else "")
                        + f"Path({str(ready)!r}).write_text(str(os.getpid()));time.sleep(20)")
        source = (f"import os,sys,time;from pathlib import Path\n"
                  f"sys.path.insert(0,{str(ROOT / 'tools')!r})\nimport labloop_preflight as pre\n")
        if pause_before_arm:
            source += ("original=pre._arm_parent_death\n"
                       "def paused(parent,prctl):\n"
                       f" Path({str(ready)!r}).write_text(str(os.getpid()))\n"
                       f" while not Path({str(release)!r}).exists(): time.sleep(0.01)\n"
                       " original(parent,prctl)\npre._arm_parent_death=paused\n")
        source += (f"pre.bounded([sys.executable,'-I','-S','-c',{child_source!r}],"
                   f"cwd={str(self.root)!r},env={{}},seconds=20)\n")
        outer = None
        child_fd = None
        child_pid = None
        try:
            outer = subprocess.Popen([sys.executable, "-I", "-S", "-c", source],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE, close_fds=True, env={})
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if ready.exists() and ready.read_text().strip():
                    child_pid = int(ready.read_text())
                    break
                if outer.poll() is not None:
                    self.fail("outer fixture exited before child readiness: " + outer.stderr.read().decode())
                time.sleep(0.01)
            self.assertIsNotNone(child_pid, "synthetic child did not become ready")
            child_fd = os.pidfd_open(child_pid)
            yield outer, child_fd, release, executed
        finally:
            release.touch()
            if outer is not None:
                if outer.poll() is None:
                    outer.kill()
                outer.wait(timeout=5)
                outer.stderr.close()
            # Read the rendezvous even after a failed readiness assertion so the
            # paused preexec child is never abandoned by a failed test.
            if child_pid is None and ready.exists() and ready.read_text().strip():
                child_pid = int(ready.read_text())
                try:
                    child_fd = os.pidfd_open(child_pid)
                except ProcessLookupError:
                    pass
            if child_fd is not None:
                if not select.select([child_fd], [], [], 0)[0]:
                    signal.pidfd_send_signal(child_fd, signal.SIGKILL)
                self.assertTrue(select.select([child_fd], [], [], 5)[0], "fixture cleanup could not establish exit")
                os.close(child_fd)
            if child_pid is not None:
                try:
                    os.waitpid(child_pid, 0)
                except ChildProcessError:
                    pass  # Ordinary-termination path was already reaped by outer.
            self.assertEqual(libc.prctl(36, previous.value, 0, 0, 0), 0)

    def test_bounded_supervisor_ordinary_signals_kill_child_and_exit_promptly(self):
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            for close_output in (False, True):
                with self.subTest(signal=signum, closed_output=close_output):
                    with self.supervisor_fixture(close_output=close_output) as (outer, child_fd, _, _):
                        outer.send_signal(signum)
                        self.assertEqual(outer.wait(timeout=3), 128 + signum)
                        self.assertTrue(select.select([child_fd], [], [], 2)[0], "child survived supervisor termination")

    def test_bounded_signal_during_popen_construction_retains_cleanup_handle(self):
        with self.supervisor_fixture(pause_before_arm=True) as (outer, child_fd, release, _):
            outer.send_signal(signal.SIGTERM)
            # The handler records termination rather than throwing out of Popen
            # before the process handle can be assigned for group cleanup.
            time.sleep(0.05)
            self.assertIsNone(outer.poll())
            release.touch()
            self.assertEqual(outer.wait(timeout=3), 128 + signal.SIGTERM)
            self.assertTrue(select.select([child_fd], [], [], 2)[0])

    def test_bounded_abrupt_supervisor_death_kills_direct_child(self):
        with self.supervisor_fixture() as (outer, child_fd, _, executed):
            self.assertTrue(executed.exists())
            outer.kill()
            self.assertEqual(outer.wait(timeout=3), -signal.SIGKILL)
            self.assertTrue(select.select([child_fd], [], [], 2)[0], "PDEATHSIG did not terminate direct child")

    def test_bounded_parent_death_before_registration_never_executes_fixture(self):
        with self.supervisor_fixture(pause_before_arm=True) as (outer, child_fd, release, executed):
            outer.kill()
            self.assertEqual(outer.wait(timeout=3), -signal.SIGKILL)
            self.assertFalse(select.select([child_fd], [], [], 0)[0], "race fixture did not pause before registration")
            release.touch()
            self.assertTrue(select.select([child_fd], [], [], 2)[0], "pre-registration parent death escaped detection")
            self.assertFalse(executed.exists(), "fixture executed after its supervisor died")

    def test_bounded_handlers_restored_and_parent_death_setup_failure_denied(self):
        signals = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
        before = {s: signal.getsignal(s) for s in signals}
        for source in ("pass", "raise SystemExit(1)"):
            try:
                pre.bounded([sys.executable, "-I", "-S", "-c", source], cwd=self.root, env={})
            except ResourceError:
                self.assertIn("SystemExit", source)
            self.assertEqual({s: signal.getsignal(s) for s in signals}, before)
        with self.assertRaisesRegex(ResourceError, "parent-death enforcement unavailable"):
            pre._arm_parent_death(os.getpid(), lambda *_: -1)

    def test_bounded_fixture_timeout_output_limit_and_diagnostics_fail_closed(self):
        for source, seconds in (("import time;time.sleep(10)", 0.15),
                                ("print('x'*70000)", 2),
                                ("import sys;sys.stderr.write('PRIVATE_SENTINEL')", 2),
                                ("raise SystemExit(7)", 2)):
            start = time.monotonic()
            with self.assertRaises(ResourceError) as err:
                pre.bounded([sys.executable, "-I", "-S", "-c", source], cwd=self.root, env={}, seconds=seconds)
            self.assertNotIn("PRIVATE_SENTINEL", str(err.exception))
            self.assertLess(time.monotonic() - start, 5)


if __name__ == "__main__":
    unittest.main()
