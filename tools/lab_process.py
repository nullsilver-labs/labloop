"""Linux-only lifetime containment for candidate processes, not a security sandbox.

A subreaper owns orphaned descendants even after setsid/double-fork. Only direct
children are signalled, through pidfds, then newly adopted children are drained.
Operator watchers do not enable this. No process-name, environment or UID scans.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def enable_subreaper() -> None:
    if not sys.platform.startswith("linux") or not hasattr(os, "pidfd_open"):
        raise RuntimeError("candidate containment requires Linux with pidfd support")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER")
    # Fail before launching anything if the kernel disallows pidfds.
    os.close(os.pidfd_open(os.getpid()))


def _children() -> list[int]:
    return [int(p) for p in Path(f"/proc/self/task/{os.getpid()}/children").read_text().split()]


def _signal_child(pid: int, sig: int) -> None:
    try:
        fd = os.pidfd_open(pid)
    except ProcessLookupError:
        return
    try:
        # Pin identity first, then verify ownership: a stale /proc PID cannot kill
        # an unrelated process even if it was reused between discovery and open.
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if int(stat[1]) == os.getpid():
            signal.pidfd_send_signal(fd, sig)
    except (FileNotFoundError, ProcessLookupError):
        pass
    finally:
        os.close(fd)


def cleanup(child: subprocess.Popen | None = None) -> bool:
    """TERM then KILL/reap only owned children; return whether live work remained.

    The caller must not publish completion if this raises (e.g. uninterruptible
    kernel I/O). The watcher retries while retaining the candidate's lease.
    """
    deadline = time.monotonic() + 6
    term_until = time.monotonic() + 1
    pending = False
    while True:
        if child is not None:
            child.poll()  # preserve Popen's exit status rather than reaping it below
        for pid in _children():
            if child is None or pid != child.pid:
                try:
                    if os.waitpid(pid, os.WNOHANG)[0]:
                        continue
                except ChildProcessError:
                    continue
            pending = True
            _signal_child(pid, signal.SIGTERM if time.monotonic() < term_until else signal.SIGKILL)
        if not _children():
            return pending
        if time.monotonic() >= deadline:
            raise RuntimeError("candidate descendants remain after SIGKILL; completion withheld")
        time.sleep(0.05)


def main() -> int:
    enable_subreaper()
    stopped = 0

    def stop(sig, _frame):
        nonlocal stopped
        stopped = sig

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    child = subprocess.Popen(sys.argv[1:])
    while child.poll() is None and not stopped:
        time.sleep(0.05)
    pending = cleanup(child)
    if stopped:
        return 128 + stopped
    if pending:
        print("lab-worker: lifecycle violation: CLI returned with live descendants; cleaned up", file=sys.stderr)
        return 125  # reserved wrapper status: live descendants at CLI return
    return child.returncode if child.returncode >= 0 else 128 - child.returncode


if __name__ == "__main__":
    sys.exit(main())
