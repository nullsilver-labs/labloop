"""Operator-only feasibility checks, NOT a live adapter or proof of zero spending.

Only --version and official auth status --json may reach Claude. The latter is
explicitly opt-in. Its identity schema is unsupported; no raw JSON fields are
interpreted as a verified account. No inventory aliases become account identity.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

from labloop_resources import ResourceError, fingerprint, load_json, object_keys, private_path, require, resolve

CLAUDE_VERSION = "2.1.263"
MAX_OUTPUT = 65536
STATUS_TTL = 300
ATTESTATION_TTL = 86400
STATUS_ARGS = ["--setting-sources", "", "--settings", '{"disableAllHooks":true}',
               "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
               "auth", "status", "--json"]
# Presence is enough to deny, including empty or apparently false values. Never
# print caller-controlled names or values. Unknown environment is not inherited.
CONFLICT_PREFIXES = ("ANTHROPIC_", "CLAUDE_", "AWS_", "AMAZON_", "GOOGLE_", "GCLOUD_",
                     "AZURE_", "FOUNDRY_", "BEDROCK_", "VERTEX_", "OPENAI_", "LD_",
                     "DYLD_", "NODE_", "BUN_", "PYTHON")
CONFLICT_NAMES = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "NODE_OPTIONS",
                  "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE", "BASH_ENV", "ENV"}


def _arm_parent_death(expected_parent, prctl):
    # Linux does not deliver a retroactive death signal if the parent died before
    # registration. Compare against the PID captured BEFORE fork, not getppid()
    # in the child. SIGKILL also covers abrupt death after registration.
    require(prctl(1, signal.SIGKILL, 0, 0, 0) == 0, "parent-death enforcement unavailable")  # PR_SET_PDEATHSIG
    if os.getppid() != expected_parent:
        os.kill(os.getpid(), signal.SIGKILL)
        os._exit(127)  # Never exec if the expected parent has already died.


def bounded(argv, *, cwd, env, seconds=10):
    """Linux, single-threaded trusted tools only; NOT a candidate supervisor.

    Ordinary termination unwinds through process-group cleanup. Parent death kills
    the direct child while its PDEATHSIG is preserved, NOT its entire descendant
    tree: fork/credential changes or trusted tool behavior can lose that safeguard.
    """
    require(0 < seconds <= 30, "invalid subprocess bound")
    require(sys.platform == "linux" and threading.current_thread() is threading.main_thread()
            and threading.active_count() == 1, "bounded tools require single-threaded Linux main thread")
    # Resolve libc before fork; preexec_fn is unsupported in threaded callers.
    prctl = ctypes.CDLL(None, use_errno=True).prctl
    prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    prctl.restype = ctypes.c_int
    expected_parent = os.getpid()
    def limits():
        _arm_parent_death(expected_parent, prctl)
        os.umask(0o077)
        for kind, value in ((resource.RLIMIT_CORE, 0), (resource.RLIMIT_CPU, 20),
                            (resource.RLIMIT_AS, 4 * 1024**3), (resource.RLIMIT_FSIZE, 16 * 1024**2),
                            (resource.RLIMIT_NOFILE, 64), (resource.RLIMIT_NPROC, 64)):
            resource.setrlimit(kind, (value, value))
    process = None
    pending_signal = None
    previous_handlers = {}
    def terminate(signum, _frame):
        nonlocal pending_signal
        pending_signal = signum
        # Do not raise inside Popen construction: losing its handle would skip
        # group cleanup. Also do not let a repeated signal interrupt cleanup.
    def check_termination():
        if pending_signal is not None:
            raise SystemExit(128 + pending_signal)
    outputs = {"out": bytearray(), "err": bytearray()}
    deadline = time.monotonic() + seconds
    try:
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            previous_handlers[signum] = signal.signal(signum, terminate)
        check_termination()
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   close_fds=True, start_new_session=True, preexec_fn=limits)
        check_termination()
        with selectors.DefaultSelector() as selector:
            for stream, name in ((process.stdout, "out"), (process.stderr, "err")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map():
                check_termination()
                remaining = deadline - time.monotonic()
                require(remaining > 0, "bounded command timed out")
                for key, _ in selector.select(min(remaining, 0.1)):
                    data = os.read(key.fileobj.fileno(), 8192)
                    if not data:
                        selector.unregister(key.fileobj)
                    else:
                        outputs[key.data].extend(data)
                        require(sum(map(len, outputs.values())) <= MAX_OUTPUT, "bounded command output exceeded")
            while True:
                check_termination()
                remaining = deadline - time.monotonic()
                require(remaining > 0, "bounded command timed out")
                try:
                    code = process.wait(timeout=min(0.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    pass
            require(code == 0 and not outputs["err"], "bounded command failed or emitted diagnostics")
            return bytes(outputs["out"])
    finally:
        try:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
                process.stdout.close()
                process.stderr.close()
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
        check_termination()


def binary_contract(path, expected_sha256):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve(), "binary must be an absolute resolved path")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid in (0, os.getuid())
            and not info.st_mode & 0o022 and info.st_mode & 0o111, "unsafe binary metadata")
    require(re.fullmatch("[0-9a-f]{64}", expected_sha256 or ""), "binary SHA-256 approval required")
    require(info.st_size <= 512 * 1024**2, "binary too large")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        require(source.read(4) == b"\x7fELF", "native Linux ELF binary required (no wrapper scripts)")
        source.seek(0)
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    require(digest.hexdigest() == expected_sha256, "binary differs from operator-approved digest")
    return {"path": str(path), "sha256": expected_sha256, "version": CLAUDE_VERSION}


def conflict_snapshot(home, project, environ, managed=Path("/etc/claude-code")):
    """Conservative deny, not a credential/settings interpreter. No helpers run.

    All nonempty settings are unsupported, even seemingly benign ones. Legacy
    .claude.json is opaque and denied by presence, never opened as it may contain
    account data. Credentials are NEVER read by this function.
    """
    require(not any(k.upper().startswith(CONFLICT_PREFIXES) or k.upper() in CONFLICT_NAMES
                    for k in environ), "conflicting provider/runtime environment present")
    home, project = Path(home), Path(project).resolve()
    paths = [home / ".claude" / "settings.json", home / ".claude" / "settings.local.json",
             managed / "managed-settings.json", managed / "managed-mcp.json"]
    opaque = [home / ".claude.json", managed / "managed-settings.d"]
    for parent in (project, *project.parents):
        paths += [parent / ".claude" / "settings.json", parent / ".claude" / "settings.local.json"]
    for path in opaque:
        require(not path.exists() and not path.is_symlink(), "unsupported opaque configuration path present")
    snapshot = []
    for path in paths:
        if path.exists() or path.is_symlink():
            info = path.lstat()
            require(path == path.resolve() and stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    and info.st_uid in (0, os.getuid()) and not info.st_mode & 0o022, "unsafe settings path")
            require(load_json(path) == {}, "nonempty settings denied (provider, helper or hook paths may apply)")
            snapshot.append([str(path), "empty-object"])
        else:
            snapshot.append([str(path), "absent"])
    return fingerprint(snapshot)


def evidence_destination(path, project):
    path = Path(path)
    private_path(path.parent, directory=True)
    require(not path.resolve().is_relative_to(Path(project).resolve()), "evidence must stay outside project")
    require(not path.exists() and not path.is_symlink(), "evidence destination already exists")
    return path


def private_write(path, value, project):
    path = evidence_destination(path, project)
    # Exclusive creation: never replace old evidence or follow a file symlink.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as target:
        json.dump(value, target, sort_keys=True, allow_nan=False)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())


def collect_status(config, binary, expected_sha256, home, output, *, operator_inspect=False):
    require(operator_inspect, "account inspection requires explicit operator opt-in")
    require(os.getuid() != 0, "root preflight is unsupported")
    home = Path(home)
    require(home.is_absolute() and home == home.resolve(), "home must be an absolute resolved path")
    private_path(home, directory=True)
    evidence_destination(output, config["project_root"])
    contract = binary_contract(binary, expected_sha256)
    before = conflict_snapshot(home, config["project_root"], os.environ)
    # HOME is the sole explicit native credential source, used by official CLI,
    # never opened by Python. No caller PATH, proxy, key, loader or helper env.
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C",
           "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    started = int(time.time())
    with tempfile.TemporaryDirectory(prefix="labloop-auth-") as cwd:
        version = bounded([contract["path"], "--version"], cwd=cwd, env=env)
        require(version.strip() == f"{CLAUDE_VERSION} (Claude Code)".encode(), "unsupported Claude CLI version")
        raw = bounded([contract["path"], *STATUS_ARGS], cwd=cwd, env=env)
    require(before == conflict_snapshot(home, config["project_root"], os.environ), "configuration changed during inspection")
    require(contract == binary_contract(binary, expected_sha256), "binary changed during inspection")
    evidence = {"schema_version": 1, "source": "official_cli_status_uninterpreted",
                "observed_at": started, "expires_at": started + STATUS_TTL,
                "authorization_hash": config["authorization_hash"], "binary": contract,
                "context_hash": fingerprint({"settings": before, "home": str(home)}),
                "raw_status": raw.decode("utf-8"), "identity_status": "unsupported_schema",
                "eligible_for_live_dispatch": False}
    private_write(output, evidence, config["project_root"])
    return summary()


def validate_status_evidence(evidence, config_hash, contract, context_hash, now):
    """Reject stale/conflicting private observations; NEVER establish identity."""
    object_keys(evidence, ("schema_version", "source", "observed_at", "expires_at",
                           "authorization_hash", "binary", "context_hash", "raw_status",
                           "identity_status", "eligible_for_live_dispatch"), "status evidence")
    require(type(evidence["schema_version"]) is int and evidence["schema_version"] == 1
            and evidence["source"] == "official_cli_status_uninterpreted"
            and evidence["identity_status"] == "unsupported_schema"
            and evidence["eligible_for_live_dispatch"] is False, "unsupported status evidence")
    observed, expires = evidence["observed_at"], evidence["expires_at"]
    require(type(observed) is int and type(expires) is int and observed <= now < expires
            and 0 < expires - observed <= STATUS_TTL, "stale status evidence")
    require(evidence["authorization_hash"] == config_hash and evidence["binary"] == contract
            and evidence["context_hash"] == context_hash, "conflicting status evidence")
    require(isinstance(evidence["raw_status"], str)
            and len(evidence["raw_status"].encode()) <= MAX_OUTPUT, "invalid status payload")
    return summary()


def validate_attestation(attestation, binding, now):
    """Offline structural check only. Binding identity is operator-declared, NOT
    verified by this slice. No attestation can clear the unsupported identity gate.
    """
    object_keys(attestation, ("schema_version", "kind", "binding", "issued_at", "expires_at",
                             "overage_disabled", "auto_replenishment_disabled"), "attestation")
    require(type(attestation["schema_version"]) is int and attestation["schema_version"] == 1
            and attestation["kind"] == "operator_attestation_not_provider_verification", "unsupported attestation")
    object_keys(binding, ("declared_identity_sha256", "authorization_hash", "binary_sha256",
                          "cli_version", "context_hash", "status_evidence_sha256"), "binding")
    for key, value in binding.items():
        require(value == CLAUDE_VERSION if key == "cli_version" else
                isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value), "invalid attestation binding")
    require(attestation["binding"] == binding, "stale or conflicting attestation binding")
    issued, expires = attestation["issued_at"], attestation["expires_at"]
    require(type(issued) is int and type(expires) is int and issued <= now < expires
            and 0 < expires - issued <= ATTESTATION_TTL, "expired or invalid attestation time")
    require(attestation["overage_disabled"] is True and attestation["auto_replenishment_disabled"] is True,
            "operator must explicitly attest both billing controls disabled")
    return {"billing_evidence": "operator-attested", "provider_verified": False,
            "identity_verified": False, "eligible_for_live_dispatch": False}


def summary():
    return {"eligible_for_live_dispatch": False, "vendor_capacity": "unknown",
            "identity_status": "unsupported_schema", "billing_status": "not_provider_verified",
            "host_isolation": "unverified", "cli_contract_version": CLAUDE_VERSION,
            "blockers": ["official identity JSON schema/provenance not established",
                         "dated billing attestation cannot prove zero-spend",
                         "OS isolation host probe not run; no worker authority separation",
                         "bounded live adapter, multidimensional reserves and lease reconciliation absent"]}


def command(args):
    try:
        if args.preflight_action == "status":
            result = summary()  # No inventory, settings, home, binary or account reads.
        else:
            require(args.operator_inspect_account, "account inspection requires explicit operator opt-in")
            config = resolve(args.inventory, args.policy)
            result = collect_status(config, args.binary, args.binary_sha256, args.native_home,
                                    args.evidence, operator_inspect=True)
        print(json.dumps(result, sort_keys=True, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError):
        # Raw subprocess output, paths and parser diagnostics may contain secrets.
        raise SystemExit("preflight: denied; private evidence not accepted; live dispatch disabled") from None


def add_parser(sub):
    parser = sub.add_parser("preflight", help="fail-closed authentication feasibility; no live dispatch")
    actions = parser.add_subparsers(dest="preflight_action", required=True)
    actions.add_parser("status", help="static blockers only; no account inspection").set_defaults(func=command)
    inspect = actions.add_parser("inspect-account", help="opt-in official non-inference status; PRIVATE evidence")
    inspect.set_defaults(func=command)
    inspect.add_argument("--operator-inspect-account", action="store_true")
    for name in ("inventory", "policy", "binary", "native-home", "evidence"):
        inspect.add_argument("--" + name, type=Path, required=True)
    inspect.add_argument("--binary-sha256", required=True)
