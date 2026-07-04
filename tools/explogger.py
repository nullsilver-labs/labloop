"""Minimal, dependency-free run logger implementing the run-dir contract (AGENTS.md §3).

Every run gets logs/<exp_id>/<run_id>/ with:
  config.json    — config + seed + git commit + command line + env fingerprint
  results.jsonl  — append-only metrics, one JSON object per call to .log()
  summary.md     — written via .write_summary() when the run ends

run_id is collision-proof: timestamp + 4 hex chars of entropy (two runs launched in
the same second must not share a dir — learned the hard way).

Usage:
    from tools.explogger import ExpLogger

    logger = ExpLogger("exp03_decodability", config={"lr": 3e-4, "seed": 0})
    for step in range(n):
        ...
        logger.log(step=step, loss=float(loss))
    logger.write_summary("# exp03 run — summary\\n\\nVerdict: GO ...")
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


def _git_commit(repo_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        commit = out.stdout.strip() or "no-git"
        dirty = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return commit + ("-dirty" if dirty else "")
    except Exception:
        return "no-git"


def _package_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for name in ("torch", "transformers", "numpy", "datasets", "jax"):
        try:
            versions[name] = __import__(name).__version__
        except Exception:
            pass
    return versions


def _gpu_fingerprint() -> list[str]:
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            return [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    except Exception:
        pass
    return []


class ExpLogger:
    def __init__(
        self,
        exp_id: str,
        config: dict[str, Any] | None = None,
        logs_root: str | Path | None = None,
    ):
        repo_root = Path(__file__).resolve().parent.parent
        root = Path(logs_root) if logs_root else repo_root / "logs"
        run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        self.exp_id = exp_id
        self.dir = root / exp_id / run_id
        self.dir.mkdir(parents=True, exist_ok=False)
        self._results = open(self.dir / "results.jsonl", "a", buffering=1)
        self._t0 = time.time()

        snapshot = {
            "exp_id": exp_id,
            "run_id": run_id,
            "config": config or {},
            "seed": (config or {}).get("seed"),
            "argv": sys.argv,
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S %z"),
            "git_commit": _git_commit(repo_root),
            "hostname": platform.node(),
            "gpus": _gpu_fingerprint(),
            "packages": _package_versions(),
        }
        (self.dir / "config.json").write_text(json.dumps(snapshot, indent=2, default=str))
        print(f"[explogger] run dir: {self.dir}")

    def log(self, **metrics: Any) -> None:
        """Append one record to results.jsonl. Values must be JSON-serializable."""
        metrics.setdefault("t", round(time.time() - self._t0, 1))
        self._results.write(json.dumps(metrics, default=str) + "\n")

    def write_summary(self, markdown: str) -> None:
        """Write summary.md. Call exactly once, when the run ends (or is killed)."""
        (self.dir / "summary.md").write_text(markdown)
        self._results.flush()

    def artifact_path(self, name: str) -> Path:
        """Path inside the run dir for checkpoints etc. (gitignored by extension)."""
        return self.dir / name

    def close(self) -> None:
        self._results.close()

    def __enter__(self) -> "ExpLogger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None and not (self.dir / "summary.md").exists():
            self.write_summary(
                f"# {self.exp_id} — CRASHED\n\n`{exc_type.__name__}: {exc}`\n\n"
                "Results up to the crash are in results.jsonl. See console log.\n"
            )
        self.close()
