"""Linux OS-boundary feasibility seam: fixed probe only, never arbitrary workers.

Default is a static plan. Actual namespace creation requires explicit operator
opt-in. An offline argument test is NOT host isolation evidence. No fallback to
unshare, host execution, root or broad filesystem mounts is permitted.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time

from labloop_preflight import bounded, evidence_destination, private_write
from labloop_resources import require

BWRAP = Path("/usr/bin/bwrap")
COMPILER = Path("/usr/bin/cc")
SOURCE = Path(__file__).with_name("labloop_probe.c")
CHECKS = ("filesystem", "environment", "fds", "process", "network", "control")


def plan():
    return {"kind": "fixed_linux_probe_only", "host_isolation": "unverified",
            "eligible_for_live_dispatch": False,
            "enforced_contract": ["no host home/repo/runtime directory mounts", "empty environment",
                                  "close inherited FDs", "new user/pid/net/ipc/uts/cgroup namespaces",
                                  "drop all capabilities", "read-only root and probe; private writable tmp",
                                  "bounded foreground fixed probe, no worker command parameter"],
            "blockers": ["host adversarial probe not run", "no candidate runner or evaluator boundary release",
                         "no live supervision/resource/lease integration", "same-user harness remains trusted"]}


def probe_argv(probe, secret, net_namespace, pid_namespace, mount_namespace):
    """Pure argument contract; calling this function creates no namespaces."""
    return [str(BWRAP), "--unshare-user", "--unshare-pid", "--unshare-net", "--unshare-ipc",
            "--unshare-uts", "--unshare-cgroup", "--disable-userns", "--assert-userns-disabled",
            "--die-with-parent", "--new-session", "--uid", "65534", "--gid", "65534",
            "--cap-drop", "ALL", "--clearenv", "--hostname", "labloop-probe",
            "--ro-bind", str(probe), "/probe", "--proc", "/proc", "--tmpfs", "/tmp",
            "--remount-ro", "/", "--chdir", "/tmp", "--", "/probe", str(secret),
            net_namespace, pid_namespace, mount_namespace]


def validate_probe_output(raw):
    # Exact fixture packet; extra output/fields or false claims deny. A mock may
    # exercise this parser but cannot manufacture the operator-run evidence tag.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate probe field")
            result[key] = value
        return result
    data = json.loads(raw, object_pairs_hook=unique)
    require(type(data) is dict and set(data) == set(CHECKS)
            and all(data[key] is True for key in CHECKS), "OS probe did not pass every check")
    return data


def trusted_tool(path):
    resolved = path.resolve(strict=True)
    info = resolved.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0
            and info.st_mode & 0o111 and not info.st_mode & 0o6022, "unsafe host tool")
    return str(resolved)


def operator_probe(output, *, operator_run=False):
    require(operator_run, "host namespace probe requires explicit operator opt-in")
    require(os.getuid() != 0 and os.uname().sysname == "Linux", "non-root Linux required")
    evidence_destination(output, SOURCE.parent.parent)
    compiler, bwrap = trusted_tool(COMPILER), trusted_tool(BWRAP)
    require(bwrap == str(BWRAP.resolve()), "unexpected bwrap")
    with tempfile.TemporaryDirectory(prefix="labloop-os-probe-") as folder:
        root = Path(folder)
        source, binary, secret = root / "probe.c", root / "probe", root / "host-secret"
        source.write_bytes(SOURCE.read_bytes())
        secret.write_text("SYNTHETIC harness credential/evaluator/state canary; never mount\n")
        secret.chmod(0o600)
        # Build only bundled fixed source, no user compiler flags/source/command.
        bounded([compiler, "-static", "-O2", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(binary)],
                cwd=folder, env={"PATH": "/usr/bin:/bin", "LANG": "C"}, seconds=30)
        argv = probe_argv(binary, secret, os.readlink("/proc/self/ns/net"),
                          os.readlink("/proc/self/ns/pid"), os.readlink("/proc/self/ns/mnt"))
        argv[0] = bwrap
        raw = bounded(argv, cwd=folder, env={}, seconds=10)
        checks = validate_probe_output(raw)
        result = {"kind": "operator_run_fixed_probe", "observed_at": int(time.time()),
                  "checks": checks, "probe_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                  "probe_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                  "kernel": os.uname().release, "host_isolation": "observed_for_fixed_probe_only",
                  "eligible_for_live_dispatch": False}
        private_write(output, result, SOURCE.parent.parent)
    return {"host_isolation": "observed_for_fixed_probe_only", "eligible_for_live_dispatch": False}


def command(args):
    try:
        result = operator_probe(args.evidence, operator_run=args.operator_run_host_probe) if args.sandbox_action == "probe" else plan()
        print(json.dumps(result, sort_keys=True, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit("sandbox: denied; host isolation not established; no fallback") from None


def add_parser(sub):
    parser = sub.add_parser("sandbox", help="fixed OS feasibility probe only; default does not launch namespaces")
    actions = parser.add_subparsers(dest="sandbox_action", required=True)
    actions.add_parser("plan").set_defaults(func=command)
    probe = actions.add_parser("probe")
    probe.add_argument("--operator-run-host-probe", action="store_true")
    probe.add_argument("--evidence", type=Path, required=True)
    probe.set_defaults(func=command)
