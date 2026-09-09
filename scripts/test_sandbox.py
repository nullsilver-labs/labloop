#!/usr/bin/env python3
"""Offline argument/adversarial packet fixtures. NO namespace/host isolation probe."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import labloop_sandbox as sandbox
from labloop_resources import ResourceError


class SandboxContractTests(unittest.TestCase):
    def test_default_plan_unverified_no_launch(self):
        with patch.object(sandbox, "bounded", side_effect=AssertionError("no launch")):
            self.assertEqual(sandbox.plan()["host_isolation"], "unverified")
            self.assertFalse(sandbox.plan()["eligible_for_live_dispatch"])
            with self.assertRaisesRegex(ResourceError, "opt-in"):
                sandbox.operator_probe(Path("unused"))

    def test_deny_by_default_namespace_and_mount_argument_contract(self):
        argv = sandbox.probe_argv("/private/build/probe", "/private/host-secret", "net:[1]", "pid:[2]", "mnt:[3]")
        self.assertEqual(argv[0], "/usr/bin/bwrap")
        for namespace in ("user", "pid", "net", "ipc", "uts", "cgroup"):
            self.assertIn("--unshare-" + namespace, argv)
        for flag in ("--die-with-parent", "--new-session", "--disable-userns", "--assert-userns-disabled",
                     "--clearenv", "--remount-ro"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--cap-drop") + 1], "ALL")
        self.assertEqual(argv[argv.index("--uid") + 1], "65534")
        self.assertEqual(argv[argv.index("--gid") + 1], "65534")
        self.assertEqual(argv[argv.index("--ro-bind") + 1:argv.index("--ro-bind") + 3],
                         ["/private/build/probe", "/probe"])
        self.assertEqual(argv.count("--ro-bind"), 1)
        for dangerous in ("--bind", "--dev-bind", "--ro-bind-try", "--unshare-user-try", "--share-net",
                          "--preserve-fds", "--setenv", "/home", "/repo", "/usr", "/lib", "/etc", "/dev"):
            self.assertNotIn(dangerous, argv)
        self.assertEqual(argv[argv.index("--") + 1:], ["/probe", "/private/host-secret", "net:[1]", "pid:[2]", "mnt:[3]"])

    def test_adversarial_filesystem_env_fd_process_network_packets_each_deny(self):
        passed = {key: True for key in sandbox.CHECKS}
        self.assertEqual(sandbox.validate_probe_output(json.dumps(passed)), passed)
        for attack in sandbox.CHECKS:
            # Mocked observations, not claims that the host blocked these attacks.
            with self.subTest(attack=attack):
                for packet in ({**passed, attack: False}, {**passed, attack: 1},
                               {k: v for k, v in passed.items() if k != attack}):
                    with self.assertRaises(ResourceError):
                        sandbox.validate_probe_output(json.dumps(packet))
        for raw in ("[]", "{}", "not JSON", json.dumps({**passed, "extra": True}),
                    json.dumps(passed)[:-1] + ',"network":true}'):
            with self.assertRaises(ValueError):
                sandbox.validate_probe_output(raw)

    def test_fixed_probe_source_has_positive_and_adversarial_checks_not_evaluator(self):
        source = sandbox.SOURCE.read_text()
        for fixture in ("/state.json", "/events.jsonl", "/evaluator", "/repo/evaluator", "/home/credential",
                        "/proc/1/root/state.json", "/proc/self/root/state.json", "/tmp/escape",
                        "environ[0] == NULL", "F_GETFD", "/proc/self/ns/net", "/proc/self/ns/pid", "/proc/self/ns/mnt",
                        "127.0.0.1", "198.51.100.1", "ENETUNREACH", "/tmp/control"):
            self.assertIn(fixture, source)
        self.assertNotIn("system(", source)
        self.assertNotIn("exec", source)

    def test_cli_plan_and_missing_opt_in_never_probe(self):
        base = [sys.executable, str(ROOT / "tools/lab"), "sandbox"]
        run = subprocess.run([*base, "plan"], capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["host_isolation"], "unverified")
        run = subprocess.run([*base, "probe", "--evidence", "/not-created"],
                             capture_output=True, text=True, timeout=10)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("no fallback", run.stderr)

    def test_no_arbitrary_command_option(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/lab"), "sandbox", "probe", "--help"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--command", result.stdout)
        self.assertNotIn("--probe-binary", result.stdout)


if __name__ == "__main__":
    unittest.main()
