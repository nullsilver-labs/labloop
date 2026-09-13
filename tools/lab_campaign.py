"""lab campaign | candidate | eval | job | run — the AIRA₂-style search loop.

See docs/aira2-loop-design.md (design) and NEXT.md (status). This module is registered into `tools/lab` and shares its helpers
(events, redaction, provenance, LEDGER, watchers), so `lab` stays the single writer
of population.json, LEDGER.md and events.jsonl.

The loop (`lab run`): reap finished jobs → enforce budgets (GPU-hours, and the Claude
Max window through the usage governor) → dispatch while a GPU slot is free
(rank-selected parent + operator; a job the window pushed out first) → stop on a stop
condition → freeze the best candidate by search fitness → evaluate it once on the
final split → REPORT.md. Campaign status: running | waiting_usage | stopping | finished.

Every job is a worker process under `lab watch`. The worker's contract:

  env  LAB_CANDIDATE_DIR   the candidate dir it may write to (and nothing else)
       LAB_JOB             job.json: operator, parents, lineage summaries, population
       LAB_OPERATOR        baseline | draft | improve | crossover | debug
       LAB_TASK            the task statement file
       LAB_TRAIN           training data (readable)
       LAB_SPLIT_INPUTS    inputs of the split to predict (search during the loop)
       LAB_PREDICTIONS_OUT where to write predictions for that split
       CUDA_VISIBLE_DEVICES the leased GPU, or "" for CPU

  must write   code/run.sh   — reads $LAB_SPLIT_INPUTS, writes $LAB_PREDICTIONS_OUT
               summary.md    — one page: what changed, what happened
  must run     code/run.sh once, so predictions for the search split exist on exit
  exit codes   0 contract met · 2 contract unmet (→ exec "invalid") · other → "failed"

`lab eval` is the only reader of labels. Fitness is written by `lab`, never by a
worker. The final split is read exactly once per campaign.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
import tomllib
from contextlib import redirect_stderr as _redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lab_findings as F

L: Any = None          # the `lab` module, injected by register()

POP_FILE = "population.json"
CARD_FILE = "finding.json"
MEMORY_POLICIES = ["legacy", "findings-v1"]
CAND_DIR = "candidates"
REPORT_FILE = "REPORT.md"
OPERATORS = ["baseline", "draft", "improve", "crossover", "debug"]
CAND_STATUS = ["queued", "running", "evaluated", "failed", "deferred", "frozen"]
EXEC_STATUS = ["completed", "failed", "killed", "invalid", "deferred"]
CAMPAIGN_STATUS = ["running", "waiting_usage", "stopping", "finished"]
# What a headless `claude -p` says when the subscription's rolling window is spent.
# Matched case-insensitively against the session result text, api_error_status and
# stderr — and only when the session did not end in success, so a worker that merely
# writes the words "rate limit" in its report is never mistaken for one.
RATE_LIMIT_RE_DEFAULT = (r"(hit your (usage |session |weekly )?limit|usage limit|rate[ _-]?limit"
                         r"|limit (has been )?reached|out of (extra )?usage|\b429\b|too many requests"
                         r"|resets? (at|in) )")
USAGE_DEFAULTS = {"soft": 0.70, "hard": 0.90, "session_cost": 0.50, "max_defers": 3}
CLAIMS = ["untested", "supported", "not_supported", "inconclusive"]
# Environment that would route a Claude Code session away from subscription login
# or to a paid path. `lab run` refuses to start while any of these is set.
PAID_ROUTE_ENV = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                  "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                  "ANTHROPIC_CUSTOM_HEADERS"]

# Trained artifacts are never inherited by a child candidate.
WEIGHT_PATTERNS = ["*.pt", "*.pth", "*.ckpt", "*.safetensors", "*.bin", "*.npz", "*.pkl",
                   "*.joblib", "*.h5", "*.onnx", "__pycache__"]

OPERATOR_TEXT = {
    "baseline": "Produce the trivial baseline exactly as the task describes it. No cleverness.",
    "draft": "Write a complete solution from the task statement. Prefer simple and "
             "runnable over ambitious. If the population below already holds candidates, "
             "take a different approach from theirs, not a variant of one. State in "
             "summary.md what you tried and why.",
    "improve": "You inherit the parent's code. Make ONE hypothesised change, state it in "
               "summary.md before running, run, and report what happened. Do not revert "
               "to a different approach; that is a draft.",
    "crossover": "You inherit parent A's code and can read parent B's. Combine the stated "
                 "strengths of both into one candidate. Say which parts came from where.",
    "debug": "The parent failed to run or produced no predictions. Make it run correctly. "
             "No improvements: a debug candidate should score like its parent would have.",
}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def parse_duration(v: Any, what: str) -> int:
    """'3h' | '90m' | '45s' | int seconds → seconds."""
    if isinstance(v, (int, float)):
        return int(v)
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*", str(v))
    if not m:
        L.die(f"{what}: cannot parse duration {v!r} (use e.g. '45s', '90m', '3h')")
    n, unit = float(m.group(1)), m.group(2) or "s"
    return int(n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit])


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def expand(p: str) -> Path:
    s = os.path.expandvars(os.path.expanduser(p))
    path = Path(s)
    return path if path.is_absolute() else (L.ROOT / path)


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(L.ROOT))
    except ValueError:
        return str(p)


def lab_bin() -> list[str]:
    return [sys.executable, str(Path(L.__file__).resolve())]


def _lab(*args: str, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    cp = subprocess.run(lab_bin() + list(args), cwd=str(L.ROOT), env=env,
                        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if check and cp.returncode != 0:
        L.die(f"`lab {' '.join(args[:3])}…` failed: {cp.stderr.strip() or cp.stdout.strip()}")
    return cp


class ledger_lock:
    """The same .lab/lab.lock the CLI takes for LEDGER/events read-modify-write."""
    def __enter__(self):
        L.LAB_DIR.mkdir(parents=True, exist_ok=True)
        self.f = open(L.LAB_DIR / "lab.lock", "w")
        t0 = time.time()
        while True:
            try:
                fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.time() - t0 > 120:
                    L.die("could not take .lab/lab.lock within 120s")
                time.sleep(0.2)

    def __exit__(self, *exc):
        self.f.close()


# ---------------------------------------------------------------------------
# campaign.toml
# ---------------------------------------------------------------------------

def load_campaign(path: Path) -> dict:
    if not path.is_absolute() and (L.ROOT / path).exists():
        path = L.ROOT / path          # relative paths are project-relative, like everything in lab
    if not path.exists():
        L.die(f"{path} not found")
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        L.die(f"{path.name}: {e}")

    def need(section: str, key: str, typ=None):
        sec = raw.get(section)
        if not isinstance(sec, dict) or key not in sec:
            L.die(f"{path.name}: [{section}] {key} is required")
        v = sec[key]
        if typ and not isinstance(v, typ):
            L.die(f"{path.name}: [{section}] {key} must be {typ.__name__}")
        return v

    cfg: dict[str, Any] = {"path": path, "sha256": sha256_file(path)}
    cid = need("campaign", "id", str)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", cid):
        L.die(f"{path.name}: campaign.id must be lowercase [a-z0-9-]")
    task = expand(need("campaign", "task", str))
    if not task.exists():
        L.die(f"{path.name}: campaign.task {task} does not exist")
    cfg["campaign"] = {"id": cid, "task": task, "kind": raw["campaign"].get("kind", "research")}

    d = raw.get("data", {})
    for k in ("train", "evaluator", "baseline"):
        need("data", k, str)
    for split in ("search", "final"):
        s = d.get(split)
        if not isinstance(s, dict) or "inputs" not in s or "labels" not in s:
            L.die(f"{path.name}: [data.{split}] needs inputs and labels")
    evaluator = expand(d["evaluator"])
    if not evaluator.exists():
        L.die(f"{path.name}: data.evaluator {evaluator} does not exist")
    cfg["data"] = {
        "train": expand(d["train"]),
        "evaluator": evaluator,
        "baseline": d["baseline"],
        "search": {"inputs": expand(d["search"]["inputs"]), "labels": expand(d["search"]["labels"])},
        "final": {"inputs": expand(d["final"]["inputs"]), "labels": expand(d["final"]["labels"])},
    }
    for split in ("search", "final"):
        if not cfg["data"][split]["inputs"].exists():
            L.die(f"{path.name}: data.{split}.inputs {cfg['data'][split]['inputs']} does not exist")
    if cfg["data"]["train"] != cfg["data"]["search"]["inputs"] and not cfg["data"]["train"].exists():
        L.die(f"{path.name}: data.train {cfg['data']['train']} does not exist")

    r = raw.get("resources", {})
    gpus = r.get("gpus", [])
    if not isinstance(gpus, list) or not all(isinstance(g, int) for g in gpus):
        L.die(f"{path.name}: resources.gpus must be a list of ints (may be empty for CPU)")
    slots = gpus if gpus else [None]
    cfg["resources"] = {
        "gpus": gpus,
        "slots": slots,
        "max_parallel_jobs": int(r.get("max_parallel_jobs", len(slots))),
        "gpu_hours_total": float(r.get("gpu_hours_total", 0)),
        "job_wall_clock_sec": parse_duration(r.get("job_wall_clock", "3h"), "resources.job_wall_clock"),
        "stall_min": int(r.get("stall_min", 0)),
        "worker_max_turns": int(r.get("worker_max_turns", 40)),
        "worker_model": r.get("worker_model", "claude-sonnet-5"),
        "min_free_vram_mb": int(r.get("min_free_vram_mb", 0)),
    }
    if cfg["resources"]["max_parallel_jobs"] < 1:
        L.die(f"{path.name}: resources.max_parallel_jobs must be >= 1")

    cfg["usage"] = parse_usage(raw, path.name)

    w = raw.get("worker", {})
    cmd = w.get("command")
    if not cmd or not isinstance(cmd, str):
        L.die(f"{path.name}: [worker] command is required (M0: a scripted worker; "
              "M1: the claude -p wrapper)")
    cfg["worker"] = {"command": cmd}

    s = raw.get("selection", {})
    cfg["selection"] = {
        "temperature": float(s.get("temperature", 0.3)),
        "crossover_p": float(s.get("crossover_p", 0.15)),
        "draft_p": float(s.get("draft_p", 0.0)),
        "max_debug_retries": int(s.get("max_debug_retries", 1)),
        "seed": int(s.get("seed", int(hashlib.sha256(cid.encode()).hexdigest()[:8], 16))),
    }
    if not (0 <= cfg["selection"]["crossover_p"] <= 1):
        L.die(f"{path.name}: selection.crossover_p must be in [0,1]")
    if not (0 <= cfg["selection"]["draft_p"] <= 1):
        L.die(f"{path.name}: selection.draft_p must be in [0,1]")
    if cfg["selection"]["draft_p"] + cfg["selection"]["crossover_p"] > 1:
        L.die(f"{path.name}: selection.draft_p + selection.crossover_p must not exceed 1")
    if cfg["selection"]["temperature"] <= 0:
        L.die(f"{path.name}: selection.temperature must be > 0")

    st = raw.get("stop", {})
    cfg["stop"] = {
        "max_candidates": int(st["max_candidates"]) if "max_candidates" in st else None,
        "no_improvement_for": int(st["no_improvement_for"]) if "no_improvement_for" in st else None,
        "wall_clock_sec": parse_duration(st["wall_clock"], "stop.wall_clock") if "wall_clock" in st else None,
    }
    if not any(v for v in cfg["stop"].values()) and not cfg["resources"]["gpu_hours_total"]:
        L.die(f"{path.name}: at least one stop condition is required "
              "([stop] max_candidates | no_improvement_for | wall_clock, or resources.gpu_hours_total)")

    rp = raw.get("report", {})
    if "success_threshold" not in rp:
        L.die(f"{path.name}: [report] success_threshold is required — fixed before the "
              "campaign, reported against at the end, never a blocker")
    cfg["report"] = {"success_threshold": float(rp["success_threshold"]),
                     "higher_is_better": bool(rp.get("higher_is_better", True))}

    mem = raw.get("memory", {})
    mode = mem.get("mode", "legacy") if isinstance(mem, dict) else None
    if mode not in MEMORY_POLICIES:
        L.die(f"{path.name}: [memory] mode must be one of {', '.join(MEMORY_POLICIES)} (got {mode!r})")
    cfg["memory"] = {"mode": mode}

    ev = raw.get("eval", {})
    cfg["eval"] = {"user": ev.get("user") or None,
                   "timeout_sec": parse_duration(ev.get("timeout", "10m"), "eval.timeout")}
    if cfg["eval"]["user"] is None:
        for split in ("search", "final"):
            if not cfg["data"][split]["labels"].exists():
                L.die(f"{path.name}: data.{split}.labels {cfg['data'][split]['labels']} does not "
                      "exist and no [eval] user is set to read it for you")
    return cfg


SCORE_STUB = """#!/usr/bin/env python3
\"\"\"score.py <predictions.json> <labels_dir> -> {"score": accuracy, "n": N}. Stdlib only:
this runs under `lab`'s python, not the candidates' environment.\"\"\"
import json, sys
preds = json.load(open(sys.argv[1]))
labels = json.load(open(sys.argv[2] + "/labels.json"))
if not isinstance(preds, list) or len(preds) != len(labels):
    print(f"expected a JSON list of {len(labels)} predictions", file=sys.stderr); sys.exit(2)
correct = sum(1 for p, y in zip(preds, labels) if p == y)
print(json.dumps({"score": correct / len(labels), "n": len(labels)}))
"""

BASELINE_STUB = """#!/usr/bin/env bash
# The trivial baseline (always candidate c0000). Obeys the worker contract: writes
# code/run.sh, runs it once for the search split, writes summary.md.
set -euo pipefail
cd "$LAB_CANDIDATE_DIR"
cat > code/run.sh <<'RUN'
#!/usr/bin/env bash
set -euo pipefail
python3 - "$LAB_TRAIN/labels.json" "$LAB_SPLIT_INPUTS" "$LAB_PREDICTIONS_OUT" <<'PY'
import json, sys
from collections import Counter
labels = json.load(open(sys.argv[1]))
major = Counter(labels).most_common(1)[0][0]
n = len(json.load(open(sys.argv[2] + "/inputs.json")))     # EDIT: how many inputs the split has
json.dump([major] * n, open(sys.argv[3], "w"))
PY
RUN
bash code/run.sh
printf '# baseline\\n\\nPredicts the most frequent training label for every input.\\n' > summary.md
"""

TASK_STUB = """# Task: REPLACE-ME

One paragraph: what is being predicted, what the score is (and whether higher is
better), what the trivial baseline scores, what a good solution scores.

## Data (read-only)
- `$LAB_TRAIN/...` -- describe files and shapes
- `$LAB_SPLIT_INPUTS/...` -- the split to predict; labels are hidden, never look for them

## Environment
- Interpreter for `code/run.sh`: REPLACE-ME (absolute path; the system python3 has nothing)
- One GPU via `CUDA_VISIBLE_DEVICES`. No network, no installs.

## What `code/run.sh` must do
1. Train if no weights exist (save them inside the candidate dir), else load them.
2. Predict every input of `$LAB_SPLIT_INPUTS`, in order.
3. Write `$LAB_PREDICTIONS_OUT` (JSON).
4. Finish in under REPLACE-ME minutes.
Seed with the job card's seed. Write `summary.md`: what you built/changed, what you observed.
"""


def parse_usage(raw: dict, name: str = "campaign.toml") -> dict:
    """[usage] — the Claude Max window is the second scarce resource (docs/aira2-loop-design.md §4). The
    estimate governor needs a calibrated budget; without one only rate-limit detection
    runs. Legacy resources.usage_soft/usage_hard are honoured as defaults."""
    u, r = raw.get("usage", {}), raw.get("resources", {})
    cfg = {
        "window_sec": parse_duration(u.get("window", "5h"), "usage.window"),
        "window_budget": float(u["window_budget"]) if "window_budget" in u else None,
        "soft": float(u.get("soft", r.get("usage_soft", USAGE_DEFAULTS["soft"]))),
        "hard": float(u.get("hard", r.get("usage_hard", USAGE_DEFAULTS["hard"]))),
        "session_cost": float(u.get("session_cost", USAGE_DEFAULTS["session_cost"])),
        "retry_sec": parse_duration(u.get("retry", "30m"), "usage.retry"),
        "max_defers": int(u.get("max_defers", USAGE_DEFAULTS["max_defers"])),
        "rate_limit_regex": str(u.get("rate_limit_regex", RATE_LIMIT_RE_DEFAULT)),
    }
    if not (0 < cfg["soft"] <= cfg["hard"] <= 1.0):
        L.die(f"{name}: usage.soft and usage.hard must satisfy 0 < soft <= hard <= 1")
    if cfg["window_budget"] is not None and cfg["window_budget"] <= 0:
        L.die(f"{name}: usage.window_budget must be > 0 (list-price USD per window)")
    if cfg["session_cost"] < 0 or cfg["max_defers"] < 0:
        L.die(f"{name}: usage.session_cost and usage.max_defers must be >= 0")
    try:
        re.compile(cfg["rate_limit_regex"], re.I)
        re.compile(session_kill_regex({"usage": cfg}))
    except re.error as e:
        L.die(f"{name}: usage.rate_limit_regex: {e} (it is also embedded in the watcher's kill "
              "pattern after a line prefix: use scoped flags like (?i:...), not ^ or $)")
    return cfg


def cmd_campaign_init(args) -> None:
    """Scaffold a campaign in the current repo: campaign.toml, task.md, eval/, data/."""
    cid = args.id
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", cid):
        L.die("id must be lowercase [a-z0-9-]")
    root = L.ROOT
    if (root / "campaign.toml").exists() and not args.force:
        L.die("campaign.toml exists (use --force to overwrite the scaffold files)")
    tmpl = Path(L.__file__).resolve().parent.parent / "templates" / "campaign.toml"
    (root / "campaign.toml").write_text(tmpl.read_text().replace("ns-REPLACE-ME", cid))
    L.write_json_atomic(L.FORMAT_PATH, L.format_manifest())   # the contract, for consumers
    (root / "eval").mkdir(exist_ok=True)
    for name, body, mode in (("eval/score.py", SCORE_STUB, 0o755),
                             ("eval/baseline.sh", BASELINE_STUB, 0o755),
                             ("task.md", TASK_STUB, 0o644)):
        p = root / name
        if not p.exists() or args.force:
            p.write_text(body)
            p.chmod(mode)
    for d in ("data/train", "data/search", "data/final"):
        (root / d).mkdir(parents=True, exist_ok=True)
    priv = os.environ.get("LAB_PRIVATE")
    if priv:
        for split in ("search", "final"):
            Path(os.path.expanduser(priv), cid, split).mkdir(parents=True, exist_ok=True)
        os.chmod(os.path.expanduser(priv), 0o700)
    gi = root / ".gitignore"
    want = [".lab/", ".venv/", "*.pt", "*.pth", "*.npy", "__pycache__/"]
    have = gi.read_text().splitlines() if gi.exists() else []
    missing = [w for w in want if w not in have]
    if missing:
        gi.write_text("\n".join(have + missing) + "\n")
    where = (f"{priv}/{cid}/{{search,final}}/" if priv
             else f"$LAB_PRIVATE/{cid}/{{search,final}}/  (export LAB_PRIVATE first)")
    print(f"""scaffolded campaign {cid}:
  campaign.toml    edit [data], [resources], [stop], [report].success_threshold
  task.md          the statement workers receive verbatim (REPLACE-ME markers)
  eval/score.py    stdlib evaluator: <predictions> <labels_dir> -> {{"score","n"}}
  eval/baseline.sh the trivial baseline, run as candidate c0000
  data/train, data/search, data/final      inputs live here
  {where}   labels live here, outside the repo
then: tools/lab campaign check; see docs/campaign-setup.md (venv, trust, labeval).""")


def cmd_campaign_check(args) -> None:
    cfg = load_campaign(Path(args.file))
    print(json.dumps({
        "id": cfg["campaign"]["id"], "sha256": cfg["sha256"][:12],
        "slots": cfg["resources"]["slots"], "max_parallel_jobs": cfg["resources"]["max_parallel_jobs"],
        "stop": cfg["stop"], "gpu_hours_total": cfg["resources"]["gpu_hours_total"],
        "privilege_separation": bool(cfg["eval"]["user"]),
        "success_threshold": cfg["report"]["success_threshold"],
        "memory": cfg["memory"]["mode"],
        "usage_governor": ("estimate + rate-limit detection" if cfg["usage"]["window_budget"]
                           else "rate-limit detection only (no usage.window_budget)"),
        "usage": {k: v for k, v in cfg["usage"].items() if k != "rate_limit_regex"},
    }, indent=2))
    if not cfg["usage"]["window_budget"]:
        L.warn("no usage.window_budget: the loop cannot pace itself inside the Max window; "
               "it will only defer jobs after a rate-limit message. Calibrate one from "
               "`lab campaign usage` of a previous run before an unattended campaign.")


# ---------------------------------------------------------------------------
# population.json
# ---------------------------------------------------------------------------

def pop_path() -> Path:
    return L.ROOT / POP_FILE


def load_pop() -> dict | None:
    p = pop_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        L.die(f"{POP_FILE} is not valid JSON: {e}")


def save_pop(pop: dict) -> None:
    pop["format"] = L.FORMAT_VERSION
    pop["updated_at"] = L.now_iso()
    L.write_json_atomic(pop_path(), pop)


def auth_preflight() -> dict:
    """Refuse a paid or non-subscription route. Recorded in population.json and REPORT.md."""
    offending = [k for k in PAID_ROUTE_ENV if os.environ.get(k)]
    return {"checked_at": L.now_iso(), "paid_route_env_present": offending,
            "ok": not offending}


def init_pop(cfg: dict) -> dict:
    pre = auth_preflight()
    if not pre["ok"]:
        L.die("refusing to start: " + ", ".join(pre["paid_route_env_present"]) +
              " is set. The loop runs on subscription login only (docs/aira2-loop-design.md §4); unset it.")
    pop = {
        "format": L.FORMAT_VERSION,
        "campaign": cfg["campaign"]["id"],
        "campaign_file": rel(cfg["path"]),
        "campaign_sha256": cfg["sha256"],
        "status": "running",          # running | stopping | finished
        "started": L.now_iso(),
        "finished": None,
        "tick": 0,
        "seed": cfg["selection"]["seed"],
        "auth_preflight": pre,
        "candidates": {},
        "best": None,
        "settled": 0,
        "settled_at_best": 0,
        "gpu_seconds": 0.0,
        "stop_reason": None,
        "final": None,
        "claim": "untested",
        "usage": usage_defaults(),
        "memory": memory_snapshot(cfg),
    }
    save_pop(pop)
    L.emit("campaign.start", f"campaign {cfg['campaign']['id']} started: "
           f"{len(cfg['resources']['slots'])} slot(s), stop {json.dumps(cfg['stop'])}",
           {"campaign": cfg["campaign"]["id"], "campaign_sha256": cfg["sha256"],
            "slots": cfg["resources"]["slots"], "stop": cfg["stop"],
            "success_threshold": cfg["report"]["success_threshold"]})
    return pop


def memory_snapshot(cfg: dict) -> dict:
    """The effective memory policy and its limits, frozen into population.json when the
    campaign starts: a tooling update must not change a running campaign's memory."""
    if cfg["memory"]["mode"] == "findings-v1":
        return {"policy": F.POLICY, **findings_limits()}
    return {"policy": "legacy"}


def findings_limits() -> dict:
    """Every constant that shapes a card or a snapshot, as this lab implements it."""
    return {"schema": F.SCHEMA, "max_cards": F.MAX_CARDS, "max_bytes": F.MAX_BYTES,
            "field_bytes": dict(F.FIELD_BYTES), "topics_max": F.TOPICS_MAX,
            "topic_max_bytes": F.TOPIC_MAX_BYTES, "reason_max_bytes": F.REASON_MAX_BYTES,
            "max_warnings": F.MAX_WARNINGS, "warning_max_bytes": F.WARNING_MAX_BYTES,
            "provenance_max_bytes": F.PROVENANCE_MAX_BYTES}


def memory_policy(pop: dict) -> dict:
    """A campaign without a snapshot (started by an older lab) is legacy; an unknown
    policy is a hard error, never a silent fallback."""
    mem = pop.get("memory") or {"policy": "legacy"}
    if mem.get("policy") not in MEMORY_POLICIES:
        L.die(f"{POP_FILE} records memory policy {mem.get('policy')!r}, which this lab does not "
              f"implement (known: {', '.join(MEMORY_POLICIES)}). Refusing to run under a policy "
              "it cannot honour.")
    if mem["policy"] == F.POLICY:
        # The complete snapshot is required, and every value must be what this tool
        # implements: a campaign frozen under other limits is run by the tool version
        # that started it, never silently re-parsed under new constants.
        for k, v in findings_limits().items():
            if k not in mem:
                L.die(f"{POP_FILE} memory snapshot lacks {k}; this lab cannot honour an incomplete "
                      f"{F.POLICY} policy")
            if mem[k] != v:
                L.die(f"{POP_FILE} froze memory {k}={mem[k]!r} but this lab implements {v!r}; "
                      "a tooling update must not change a running campaign's memory. Run it "
                      "with the tool version that started it, or start a new campaign.")
    return mem


def usage_defaults() -> dict:
    return {"waiting_seconds": 0.0, "waiting_since": None, "waiting_reason": None,
            "next_eligible": None, "pauses": 0, "rate_limits": 0, "deferred": 0,
            "hard_kills": 0, "peak_fraction": 0.0, "blocked_until": None,
            "blocked_reason": None, "deferred_jobs": []}


def better(cfg: dict, a: float | None, b: float | None) -> bool:
    """Is a strictly better than b?"""
    if a is None:
        return False
    if b is None:
        return True
    return a > b if cfg["report"]["higher_is_better"] else a < b


# ---------------------------------------------------------------------------
# candidates
# ---------------------------------------------------------------------------

def cand_dir(cid: str) -> Path:
    return L.ROOT / CAND_DIR / cid


def read_summary(cid: str, limit: int = 1200) -> str:
    p = cand_dir(cid) / "summary.md"
    try:
        t = p.read_bytes().decode("utf-8", errors="replace").strip()   # a worker's bytes, whatever they are
    except OSError:
        return ""
    return t if len(t) <= limit else t[:limit].rstrip() + " …"


def lineage(pop: dict, cid: str, depth: int = 5) -> list[str]:
    out, cur = [], cid
    while cur and len(out) < depth:
        c = pop["candidates"].get(cur)
        if not c:
            break
        out.append(cur)
        cur = (c.get("parents") or [None])[0]
    return out


def new_candidate(cfg: dict, pop: dict, operator: str, parents: list[str],
                  gpu: int | None, rng: random.Random, origin: dict | None = None) -> str:
    """origin: the deferred job this candidate re-dispatches ({from, defers}), if any."""
    cid = f"c{len(pop['candidates']):04d}"
    cdir = cand_dir(cid)
    mem = memory_policy(pop)
    findings = None
    if mem["policy"] == F.POLICY:
        # The versioned findings snapshot: selected deterministically now, from the
        # cards as they are, and stored whole so the job card is reproducible byte for
        # byte after later candidates end. Consumes no scheduler randomness. Selected
        # before the dir exists, so a tooling error here leaves no orphan.
        try:
            findings = F.select_context(load_cards(pop), parents, max_cards=mem["max_cards"],
                                        max_bytes=mem["max_bytes"])
        except F.ToolingError as e:
            L.die(f"cannot build the findings context for {cid}: {e}")
    cdir.mkdir(parents=True, exist_ok=False)
    (cdir / "code").mkdir()
    (cdir / "out").mkdir()
    if parents:
        # Inherit the parent's code, never its trained artifacts: a child that finds
        # weights would load them and skip training, and "improve" would silently be
        # the parent scored twice (seen on the first live run).
        src = cand_dir(parents[0]) / "code"
        if src.exists():
            shutil.copytree(src, cdir / "code", dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(*WEIGHT_PATTERNS))
    seed = rng.randrange(2**31)
    snapshot = {
        "format": L.FORMAT_VERSION,
        "candidate": cid,
        "campaign": cfg["campaign"]["id"],
        "campaign_sha256": cfg["sha256"],
        "operator": operator,
        "parents": parents,
        "seed": seed,
        "start_time": L.now_iso(),
        "gpu": gpu,
        "job_wall_clock_sec": cfg["resources"]["job_wall_clock_sec"],
        "command": cfg["worker"]["command"] if operator != "baseline" else cfg["data"]["baseline"],
        "argv": sys.argv,
        "cwd": str(Path.cwd()),
        "git_commit": L.git("rev-parse", "--short", "HEAD") or "no-git",
        "git_dirty": bool(L.git("status", "--porcelain")),
        "hardware": L.hardware_fingerprint(),
        "packages": L.package_versions([]),
        "agent": {"requested": cfg["resources"]["worker_model"] if operator != "baseline" else None,
                  "requested_source": "campaign.toml", "served": [], "served_source": "none"},
        "redispatch_of": origin["from"] if origin else None,
        "defers": origin["defers"] if origin else 0,
    }
    L.write_json_atomic(cdir / "config.json", snapshot)

    card = {
        "candidate": cid,
        "operator": operator,
        "instructions": OPERATOR_TEXT[operator],
        "task_file": rel(cfg["campaign"]["task"]),
        "candidate_dir": rel(cdir),
        "seed": seed,
        "memory": mem["policy"],
        "parents": [{
            "id": p, "path": rel(cand_dir(p)),
            "fitness": pop["candidates"][p].get("fitness"),
            "exec": pop["candidates"][p].get("exec"),
            # evaluator stderr can name the labels dir: a worker sees a sanitized line
            "fail_reason": F.sanitize_text(pop["candidates"][p].get("fail_reason"),
                                           lambda s: L.redact(s), _private_paths(cfg)),
            "summary": read_summary(p) if findings is None else None,
            "summary_file": rel(cand_dir(p) / "summary.md"),
        } for p in parents],
        "lineage": [{"id": a, "operator": pop["candidates"][a]["operator"],
                     "fitness": pop["candidates"][a].get("fitness"),
                     "summary": read_summary(a, 400)}
                    for a in (lineage(pop, parents[0])[1:] if parents and findings is None else [])],
        "findings": findings,
        "population": [{"id": k, "operator": v["operator"], "status": v["status"],
                        "fitness": v.get("fitness")}
                       for k, v in pop["candidates"].items()],
        "best": pop.get("best"),
        "contract": {
            "write": "code/run.sh (reads $LAB_SPLIT_INPUTS, writes $LAB_PREDICTIONS_OUT) and summary.md",
            "run": "code/run.sh once for the search split before exiting, synchronously in the foreground "
                   f"(job wall-clock cap {cfg['resources']['job_wall_clock_sec']} seconds). "
                   "Use a bounded Bash timeout within the remaining job budget; never run_in_background, "
                   "shell &, nohup, setsid or nested lab watch. Wait for exit, check its exit code and "
                   "predictions, then write summary.md before ending the session. An end_turn is not "
                   "a handoff: pending work is killed and the candidate is invalid",
            "inherited": "the parent's code/ without its trained weights (*.pt etc.); you train afresh",
            "final": "lab re-runs code/run.sh later with LAB_SPLIT_INPUTS pointing at the final split; "
                     "it must reuse what you trained (persist weights inside the candidate dir and "
                     "load them when present), so the final score is of the same model",
            "predictions": "out/predictions-search.json",
            "may_write": rel(cdir), "may_read": [rel(cfg["data"]["train"]),
                                                  rel(cfg["data"]["search"]["inputs"]),
                                                  rel(cfg["campaign"]["task"])] +
                                                 [rel(cand_dir(p)) for p in parents],
            "max_turns": cfg["resources"]["worker_max_turns"],
            "summary_format": F.SUMMARY_FORMAT if findings is not None else None,
        },
    }
    L.write_json_atomic(cdir / "job.json", card)

    pop["candidates"][cid] = {
        "id": cid, "operator": operator, "parents": parents, "status": "queued",
        "exec": None, "gpu": gpu, "watch": None, "launched": None, "ended": None,
        "fitness": None, "n": None, "fail_reason": None, "debugged": False,
        "path": rel(cdir), "session": None,
        "redispatch_of": origin["from"] if origin else None,
        "defers": origin["defers"] if origin else 0,
    }
    return cid


def worker_env(cfg: dict, cid: str, operator: str, gpu: int | None, split: str = "search") -> dict:
    """The worker's environment: no LAB_PRIVATE (labels), no paid-route credentials."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("LAB_PRIVATE", "LAB_ROLE") and k not in PAID_ROUTE_ENV}
    cdir = cand_dir(cid)
    env.update({
        "LAB_ROLE": "worker",
        "LAB_CANDIDATE_DIR": str(cdir),
        "LAB_JOB": str(cdir / "job.json"),
        "LAB_OPERATOR": operator,
        "LAB_TASK": str(cfg["campaign"]["task"]),
        "LAB_TRAIN": str(cfg["data"]["train"]),
        "LAB_SPLIT": split,
        "LAB_SPLIT_INPUTS": str(cfg["data"][split]["inputs"]),
        "LAB_PREDICTIONS_OUT": str(cdir / "out" / f"predictions-{split}.json"),
        "LAB_WORKER_MODEL": cfg["resources"]["worker_model"],
        "LAB_WORKER_MAX_TURNS": str(cfg["resources"]["worker_max_turns"]),
        "LAB_JOB_WALL_CLOCK_SEC": str(cfg["resources"]["job_wall_clock_sec"]),
        "CUDA_VISIBLE_DEVICES": "" if gpu is None else str(gpu),
    })
    return env


STDERR_PREFIX = "[claude stderr] "   # lab-worker echoes the CLI's stderr under this
KILL_PATTERN_PREFIX = "kill pattern matched:"


_GLOBAL_FLAGS = re.compile(r"^\(\?([aiLmsux]+)\)")


def session_kill_regex(cfg: dict) -> str:
    """The watcher's kill pattern for a worker job: the usage rate-limit regex, but only
    on lines lab-worker echoes from the CLI's stderr. A rate-limit message that the CLI
    prints while it keeps running (waiting or retrying for the window) ends the session
    within a watcher poll; the job is then settled as deferred, never failed. Nothing
    the candidate's own run prints can match. A configured regex that starts with
    global inline flags, `(?i)…`, is embedded as the scoped form `(?i:…)`, which Python
    accepts anywhere; parse_usage compiles the result once so a bad combination is a
    campaign.toml error, not a job that silently runs without its kill pattern."""
    rx = cfg["usage"]["rate_limit_regex"]
    m = _GLOBAL_FLAGS.match(rx)
    inner = f"(?{m.group(1)}:{rx[m.end():]})" if m else f"(?:{rx})"
    return rf"(?im)^{re.escape(STDERR_PREFIX)}.*{inner}"


def launch(cfg: dict, pop: dict, cid: str) -> None:
    c = pop["candidates"][cid]
    env = worker_env(cfg, cid, c["operator"], c["gpu"])
    command = cfg["data"]["baseline"] if c["operator"] == "baseline" else cfg["worker"]["command"]
    budget_min = max(1, math.ceil(cfg["resources"]["job_wall_clock_sec"] / 60))
    args = ["watch", "start", "--op", f"job-{cid}", "--budget-min", str(budget_min),
            "--candidate-dir", str(cand_dir(cid))]
    if cfg["resources"]["stall_min"]:
        args += ["--stall-min", str(cfg["resources"]["stall_min"])]
    if c["operator"] != "baseline":
        args += ["--kill-regex", session_kill_regex(cfg)]
    args += ["--", "bash", "-c", command]
    env.pop("LAB_ROLE", None)  # the watcher is the operator; only its child is a worker
    cp = _lab(*args, env=env)
    wid = cp.stdout.strip().splitlines()[-1]
    c.update({"status": "running", "watch": wid, "launched": L.now_iso()})
    with ledger_lock():
        L.ledger_upsert(cid, {"run": pop["campaign"], "exp": c["operator"], "status": "running",
                              "verdict": "", "path": c["path"], "note": ""})
    L.emit("candidate.launch",
           f"{cid} {c['operator']}" + (f" from {','.join(c['parents'])}" if c["parents"] else "") +
           (f" on gpu {c['gpu']}" if c["gpu"] is not None else " on cpu") +
           (f" (re-dispatch of {c['redispatch_of']})" if c.get("redispatch_of") else ""),
           {"candidate": cid, "operator": c["operator"], "parents": c["parents"],
            "gpu": c["gpu"], "watch": wid, "campaign": pop["campaign"],
            "redispatch_of": c.get("redispatch_of")})


def watch_entry(wid: str) -> dict | None:
    for d in (L.WATCH_DIR, L.WATCH_ARCHIVE):
        p = d / f"{wid}.json"
        if p.exists():
            try:
                return json.loads(p.read_text())
            except (json.JSONDecodeError, OSError):
                return None
    return None


def _duration_sec(a: str | None, b: str | None) -> float:
    try:
        return max(0.0, (datetime.fromisoformat(b.replace("Z", "+00:00")) -
                         datetime.fromisoformat(a.replace("Z", "+00:00"))).total_seconds())
    except Exception:
        return 0.0


def stub_summary(cdir: Path, title: str, facts: list[str]) -> None:
    p = cdir / "summary.md"
    try:
        if p.exists() and p.read_bytes().strip():   # never decoded: invalid UTF-8 is still a summary
            return
    except OSError:
        return
    p.write_text(f"# summary — {title}\n\n" + "".join(f"- {f}\n" for f in facts) +
                 "\nFacts-only stub written mechanically by `lab run`; the worker left no summary.\n")


def _iso_epoch(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _epoch_iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_reset_time(text: str, now: float) -> float | None:
    """'resets 3pm', 'resets at 14:30', 'resets in 2h 15m', an ISO timestamp → epoch.
    Clock times are read in the local timezone, as Claude Code prints them; a time
    already past today means tomorrow. None when nothing parses."""
    m = re.search(r"resets?\s+(?:at\s+)?(\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-]\d{2}:?\d{2})?)", text, re.I)
    if m:
        t = _iso_epoch(m.group(1))
        if t:
            return t
    m = re.search(r"resets?\s+in\s+((?:\d+\s*(?:h|hr|hours?|m|min|minutes?|s|sec)\s*)+)", text, re.I)
    if m:
        secs = 0
        for n, unit in re.findall(r"(\d+)\s*(h|hr|hours?|m|min|minutes?|s|sec)", m.group(1), re.I):
            secs += int(n) * (3600 if unit.lower().startswith("h") else 60 if unit.lower().startswith("m") else 1)
        return now + secs if secs else None
    m = re.search(r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text, re.I)
    if m:
        hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if not (0 <= hour < 24 and 0 <= minute < 60):
            return None
        local = datetime.fromtimestamp(now).astimezone()
        cand = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if cand.timestamp() <= now:
            cand = datetime.fromtimestamp(cand.timestamp() + 86400).astimezone()
        return cand.timestamp()
    return None


def _empty_session() -> dict:
    """The session record's full shape with nothing known (no session.json, no stderr)."""
    return {"id": None, "turns": None, "duration_ms": None, "cost_usd": None, "subtype": None,
            "is_error": None, "api_error_status": None, "models": [], "output_tokens": None,
            "cache_read_input_tokens": None, "rate_limited": False, "message": None, "reset_at": None}


def read_session(cfg: dict, cdir: Path) -> dict | None:
    """What the worker's one Claude Code session cost and how it ended, from the
    session.json that lab-worker stores (and session.stderr when the CLI died before
    writing one). None for candidates that ran no session (the baseline)."""
    sj, se = cdir / "session.json", cdir / "session.stderr"
    if not sj.exists() and not se.exists():
        return None
    r: dict = {}
    if sj.exists():
        try:
            r = json.loads(sj.read_text()) or {}
        except (json.JSONDecodeError, OSError):
            r = {}
    stderr = ""
    if se.exists():
        try:
            stderr = se.read_text(errors="replace")[-4000:]
        except OSError:
            stderr = ""
    usage = r.get("usage") or {}
    rec = {
        "id": r.get("session_id"),
        "turns": r.get("num_turns"),
        "duration_ms": r.get("duration_ms"),
        "cost_usd": r.get("total_cost_usd"),
        "subtype": r.get("subtype"),
        "is_error": bool(r.get("is_error")) if r else None,
        "api_error_status": r.get("api_error_status"),
        "models": sorted((r.get("modelUsage") or {}).keys()),
        "output_tokens": usage.get("output_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "rate_limited": False, "message": None, "reset_at": None,
    }
    succeeded = bool(r) and r.get("subtype") == "success" and not r.get("is_error") \
        and not r.get("api_error_status")
    haystack = " ".join(str(r.get(k) or "") for k in ("result", "subtype", "api_error_status",
                                                      "terminal_reason", "error")) + "\n" + stderr
    m = re.search(cfg["usage"]["rate_limit_regex"], haystack, re.I)
    if m and not succeeded:
        rec["rate_limited"] = True
        line = next((ln for ln in haystack.splitlines() if re.search(cfg["usage"]["rate_limit_regex"], ln, re.I)), "")
        rec["message"] = re.sub(r"\s+", " ", line).strip()[:100] or m.group(0)
        t = parse_reset_time(haystack, time.time())
        rec["reset_at"] = _epoch_iso(t) if t else None
    return rec


def _record_served(cdir: Path, sess: dict | None) -> None:
    """Fill config.json's agent.served from the session's modelUsage (provenance)."""
    if not sess or not sess.get("models"):
        return
    try:
        cfgp = cdir / "config.json"
        snap = json.loads(cfgp.read_text())
        snap.setdefault("agent", {})["served"] = sess["models"]
        snap["agent"]["served_source"] = "session.json modelUsage"
        L.write_json_atomic(cfgp, snap)
    except (OSError, json.JSONDecodeError):
        pass


def settle(cfg: dict, pop: dict, cid: str, entry: dict) -> None:
    c = pop["candidates"][cid]
    cdir = cand_dir(cid)
    status = entry.get("status")
    exec_status = {"done": "completed", "failed": "failed", "killed": "killed"}.get(status, "failed")
    c["ended"] = entry.get("ended") or L.now_iso()
    c["exit_code"] = entry.get("exit_code")
    if c.get("gpu") is not None:
        pop["gpu_seconds"] += _duration_sec(entry.get("started"), entry.get("ended"))
    sess = read_session(cfg, cdir) if c["operator"] != "baseline" else None
    c["session"] = sess
    _record_served(cdir, sess)

    preds = cdir / "out" / "predictions-search.json"
    reason = None
    kill_reason = entry.get("kill_reason") or ""
    forged = quarantine_worker_card(cid) if memory_policy(pop)["policy"] == F.POLICY else None
    if forged:
        # lab publishes a card only after settlement, so one that exists now was written
        # by the worker: a forged account of its own attempt. Kept, never adopted.
        exec_status, reason = "invalid", f"worker wrote {CARD_FILE}; quarantined as {forged}"
    elif exec_status == "completed" and preds.exists():
        fit = evaluate(cfg, cdir, "search")
        if fit.get("score") is None:
            exec_status, reason = "invalid", f"evaluator: {fit.get('error', 'no score')}"
        else:
            c["fitness"], c["n"] = fit["score"], fit.get("n")
    elif exec_status == "killed" and kill_reason.startswith(KILL_PATTERN_PREFIX):
        # the CLI printed a usage-limit message and kept running; the watcher's kill
        # pattern (session_kill_regex) ended it. Deferred like any rate limit; the
        # reset time comes from the same stderr line via read_session.
        if not sess:
            sess = c["session"] = _empty_session()
        if not sess.get("rate_limited"):
            sess["rate_limited"], sess["message"], sess["reset_at"] = True, kill_reason[:100], None
        exec_status = "deferred"
        reason = (f"usage limit: {sess['message']}; the session kept running past it and was "
                  "killed by the watcher")
    elif sess and sess["rate_limited"]:
        # the window is spent: not the candidate's fault, never `failed` (docs/aira2-loop-design.md §4)
        exec_status, reason = "deferred", f"usage limit: {sess['message']}"
    elif exec_status == "killed" and kill_reason.startswith("usage_hard"):
        exec_status, reason = "deferred", kill_reason
    elif exec_status == "completed":
        exec_status, reason = "invalid", "worker exited 0 but wrote no out/predictions-search.json"
    elif exec_status == "killed":
        reason = kill_reason or "killed by watcher"
    elif entry.get("exit_code") == 2:
        # the worker's own verdict: the session ran but left no runnable candidate
        exec_status, reason = "invalid", "worker reported the contract unmet (exit 2)"
    else:
        reason = f"worker exited {entry.get('exit_code')}"
    c["exec"] = exec_status
    c["fail_reason"] = reason
    c["status"] = {"completed": "evaluated", "deferred": "deferred"}.get(exec_status, "failed")

    stub_summary(cdir, f"{cid} ({c['operator']}, {exec_status})",
                 [f"operator: {c['operator']}, parents: {', '.join(c['parents']) or 'none'}",
                  f"exec: {exec_status}" + (f" — {reason}" if reason else ""),
                  f"started {entry.get('started')}, ended {c['ended']}, exit code {c['exit_code']}",
                  f"search fitness: {c['fitness']}"]
                 + ([f"session: {sess['id']}, {sess['turns']} turns, list-price ${sess['cost_usd']}"]
                    if sess and sess.get("id") else []))

    if c["status"] == "deferred":
        defer_job(cfg, pop, c, reason or "deferred")
    else:
        pop["settled"] += 1
        if c["status"] == "evaluated" and better(cfg, c["fitness"], pop["candidates"].get(pop["best"], {}).get("fitness") if pop["best"] else None):
            pop["best"] = cid
            pop["settled_at_best"] = pop["settled"]

    save_pop(pop)   # measurement is durable before the ledger/feed/archive side effects
    with ledger_lock():
        L.ledger_upsert(cid, {"run": pop["campaign"], "exp": c["operator"],
                              "status": "done" if c["status"] == "evaluated" else exec_status,
                              "verdict": "", "path": c["path"],
                              "note": (f"fitness {c['fitness']:.6g}" if c["fitness"] is not None else (reason or ""))})
    if c["status"] == "evaluated":
        L.emit("candidate.done", f"{cid} {c['operator']} search fitness {c['fitness']:.6g}"
               + (" (new best)" if pop["best"] == cid else ""),
               {"candidate": cid, "operator": c["operator"], "parents": c["parents"],
                "fitness": c["fitness"], "n": c["n"], "best": pop["best"] == cid,
                "campaign": pop["campaign"]})
    elif c["status"] == "deferred":
        job = pop["usage"]["deferred_jobs"][-1] if pop["usage"]["deferred_jobs"] else None
        again = job is not None and job.get("from") == cid
        short = (f"usage limit message, resets {sess['reset_at'] or 'unstated'}" if sess and sess["rate_limited"]
                 else "killed at usage_hard")
        L.emit("note", f"{cid} {c['operator']} deferred, not failed: {short}"
               + ("; re-dispatched when the window has room" if again
                  else f"; dropped after {c['defers'] + 1} deferrals"),
               {"candidate": cid, "operator": c["operator"], "parents": c["parents"],
                "exec": exec_status, "reason": reason, "redispatch": again,
                "next_eligible": pop["usage"].get("blocked_until"), "campaign": pop["campaign"]})
    else:
        L.emit("candidate.failed", f"{cid} {c['operator']} {exec_status}: {reason}",
               {"candidate": cid, "operator": c["operator"], "parents": c["parents"],
                "exec": exec_status, "reason": reason, "campaign": pop["campaign"]})
    if entry.get("status") != "running" and (L.WATCH_DIR / f"{entry['id']}.json").exists():
        _lab("watch", "close", entry["id"], check=False)


def reap(cfg: dict, pop: dict) -> None:
    for cid, c in list(pop["candidates"].items()):
        if c["status"] != "running":
            continue
        entry = watch_entry(c["watch"]) if c.get("watch") else None
        if entry is None:
            settle(cfg, pop, cid, {"id": c.get("watch") or "?", "status": "failed",
                                   "kill_reason": "watch entry lost", "exit_code": None,
                                   "started": c.get("launched"), "ended": L.now_iso()})
            continue
        entry = L._watch_repair(entry)
        if entry.get("status") == "running":
            continue
        settle(cfg, pop, cid, entry)


# ---------------------------------------------------------------------------
# finding cards — one immutable finding.json per settled attempt (opt-in memory)
# ---------------------------------------------------------------------------
#
# docs/finding-cards-plan.md §2. Built by lab_findings from an allowlist of recorded
# facts (population.json, config.json, fitness.json's search record, summary.md) after
# settlement is durable; written once, atomically; never overwritten. Every tick checks
# that each settled candidate has a card that agrees with its sources before anything
# new is dispatched — a missing card is recovered from the artifacts, a corrupt or
# conflicting one stops dispatch as a tooling error and is left in place.


def card_path(cid: str) -> Path:
    return cand_dir(cid) / CARD_FILE


def quarantine_worker_card(cid: str) -> str | None:
    """A finding.json present before lab has published one is the worker's: rename it
    (bytes kept as evidence) so it can never be mistaken for a generated card, and
    return the new name."""
    p = card_path(cid)
    if not p.exists() and not p.is_symlink():
        # a crash between the rename and the saved settlement leaves the quarantined
        # file as the durable verdict; only this function ever creates that name
        prior = sorted(p.parent.glob("finding.worker*.json"))
        return prior[-1].name if prior else None
    for n in range(1, 100):
        q = p.with_name(f"finding.worker{'' if n == 1 else n}.json")
        if not q.exists() and not q.is_symlink():
            os.rename(p, q)
            return q.name
    L.die(f"{rel(p)}: too many quarantined worker cards")


def _private_paths(cfg: dict) -> tuple[str, ...]:
    out = [str(cfg["data"][s]["labels"]) for s in ("search", "final")]
    priv = os.environ.get("LAB_PRIVATE")
    if priv:
        out.append(os.path.expanduser(priv))
    return tuple(p for p in out if p and p != "/")


def _read_json(p: Path) -> dict | None:
    try:
        v = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return v if isinstance(v, dict) else None


def _read_bytes(p: Path) -> bytes | None:
    try:
        return p.read_bytes()
    except OSError:
        return None


def build_candidate_card(cfg: dict, pop: dict, cid: str) -> dict:
    c = pop["candidates"][cid]
    cdir = cand_dir(cid)
    parents = []
    for p in c["parents"]:
        pc = pop["candidates"].get(p)
        if pc is None:
            raise F.ToolingError(f"{cid}: parent {p} is not in the population")
        pcfg = _read_json(cand_dir(p) / "config.json") or {}
        parents.append({"id": p, "score": pc.get("fitness"), "seed": pcfg.get("seed")})
    return F.build_card(
        campaign={"id": pop["campaign"], "sha256": pop["campaign_sha256"],
                  "higher_is_better": cfg["report"]["higher_is_better"]},
        candidate={"id": cid, "operator": c["operator"], "parents": list(c["parents"]),
                   "exec": c.get("exec"), "fail_reason": c.get("fail_reason"),
                   "redispatch_of": c.get("redispatch_of"), "defers": c.get("defers", 0)},
        config=_read_json(cdir / "config.json"),
        fitness=_read_json(cdir / "fitness.json"),
        parents=parents,
        summary=_read_bytes(cdir / "summary.md"),
        # the recorded settlement time, not the clock: a card recovered after a loss is
        # byte-identical to the one the job snapshots already cite
        created_at=c.get("ended") or L.now_iso(),
        redact=lambda s: L.redact(s),
        private_paths=_private_paths(cfg),
    )


def write_json_once(path: Path, obj: dict) -> None:
    """Atomic and write-once: a temp file linked into place fails if the path exists.
    A crash mid-write leaves only a temp file, which the next pass removes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for stale in path.parent.glob(path.name + ".tmp*"):
        stale.unlink(missing_ok=True)        # this process is the only publisher (campaign.lock)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with open(tmp, "w") as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    try:
        # link, never a fallback that could expose a half-written card: a filesystem
        # without hard links is a tooling error to fix, not a place to publish evidence
        os.link(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def ensure_cards(cfg: dict, pop: dict) -> None:
    """Every settled candidate has a valid card that agrees with its sources; publish the
    missing ones. Dies — dispatch blocked, evidence untouched — on a corrupt or
    conflicting card, naming the card and the failed check."""
    if memory_policy(pop)["policy"] != F.POLICY:
        return
    for cid, c in pop["candidates"].items():
        if c.get("exec") not in F.EXEC_STATUSES:
            continue      # queued or running: not settled yet
        p = card_path(cid)
        try:
            built = build_candidate_card(cfg, pop, cid)
        except F.ToolingError as e:
            L.die(f"cannot build the finding card for {cid}: {e}")
        if not p.exists():
            try:
                write_json_once(p, built)
            except FileExistsError:
                pass      # appeared meanwhile; compared below like any other card
            except OSError as e:
                L.die(f"cannot publish finding card {rel(p)}: {e}")
        # An existing card is never adopted on trust: it must be valid, agree with its
        # sources, and equal what this lab builds from them now (build_card is
        # deterministic, created_at included). Cheap, and a drift is a tooling error.
        raw = _read_bytes(p)
        try:
            card = json.loads(raw.decode("utf-8")) if raw is not None else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            card = None
        problems = F.validate_card(card) if card is not None else ["not valid JSON"]
        if not problems:
            cdir = cand_dir(cid)
            problems = F.check_card_sources(
                card, campaign_id=pop["campaign"], campaign_sha256=pop["campaign_sha256"],
                candidate={"id": cid, "operator": c["operator"], "parents": list(c["parents"]),
                           "exec": c.get("exec")},
                summary=_read_bytes(cdir / "summary.md"), fitness=_read_json(cdir / "fitness.json"))
        if not problems and not F.same_card(card, built, F.cleaner(lambda s: L.redact(s), _private_paths(cfg))):
            diff = sorted(k for k in set(card) | set(built) if card.get(k) != built.get(k))
            problems = [f"differs from the card rebuilt from its sources in {', '.join(diff)}"]
        if problems:
            L.die(f"finding card {rel(p)} fails its check: {'; '.join(problems)}. The card and "
                  "the candidate are left as they are; no new job is dispatched until an "
                  "operator decides (v1 has no automatic repair or supersession).")


def load_cards(pop: dict) -> dict[str, dict]:
    """The cards of every settled candidate, for context selection. ensure_cards has
    run in this tick, so a missing or invalid card here is a tooling error."""
    cards: dict[str, dict] = {}
    for cid, c in pop["candidates"].items():
        if c.get("exec") not in F.EXEC_STATUSES:
            continue
        card = _read_json(card_path(cid))
        if card is None or F.validate_card(card):
            L.die(f"finding card {rel(card_path(cid))} is missing or invalid at dispatch time")
        cards[cid] = card
    return cards


# ---------------------------------------------------------------------------
# evaluation — the only reader of labels
# ---------------------------------------------------------------------------

def evaluate(cfg: dict, cdir: Path, split: str) -> dict:
    fpath = cdir / "fitness.json"
    fitness = json.loads(fpath.read_text()) if fpath.exists() else {}
    if split in fitness:
        return fitness[split]                      # idempotent: a measurement is final
    preds = cdir / "out" / f"predictions-{split}.json"
    labels = cfg["data"][split]["labels"]
    evaluator = cfg["data"]["evaluator"]
    cmd = ([sys.executable, str(evaluator)] if evaluator.suffix == ".py" else [str(evaluator)]) + \
          [str(preds), str(labels)]
    user = cfg["eval"]["user"]
    if user:
        cmd = ["sudo", "-n", "-u", user] + cmd
    rec: dict[str, Any] = {"split": split, "ts": L.now_iso(), "evaluator": rel(evaluator),
                           "evaluator_sha256": sha256_file(evaluator),
                           "privilege_separation": bool(user), "score": None, "n": None}
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=cfg["eval"]["timeout_sec"],
                            cwd=str(L.ROOT), stdin=subprocess.DEVNULL)
        if cp.returncode != 0:
            rec["error"] = (cp.stderr.strip() or f"exit {cp.returncode}")[-500:]
        else:
            out = cp.stdout.strip().splitlines()[-1] if cp.stdout.strip() else ""
            try:
                val = json.loads(out)
            except json.JSONDecodeError:
                val = None
            if isinstance(val, dict) and isinstance(val.get("score"), (int, float)):
                rec["score"], rec["n"] = float(val["score"]), val.get("n")
            elif isinstance(val, (int, float)):
                rec["score"] = float(val)
            else:
                rec["error"] = f"evaluator printed no score: {out[:200]!r}"
    except subprocess.TimeoutExpired:
        rec["error"] = f"evaluator timed out after {cfg['eval']['timeout_sec']}s"
    if rec["score"] is not None and not math.isfinite(rec["score"]):
        rec["score"], rec["error"] = None, "evaluator returned a non-finite score"
    fitness[split] = rec
    L.write_json_atomic(fpath, fitness)
    return rec


def cmd_eval(args) -> None:
    cfg = load_campaign(Path(args.campaign))
    cdir = Path(args.dir)
    if not cdir.is_absolute():
        cdir = L.ROOT / cdir
    if not (cdir / "config.json").exists():
        L.die(f"{args.dir} is not a candidate dir")
    if args.split == "final":
        L.die("the final split is read once, by `lab run`, after the search stops — "
              "never on request")
    rec = evaluate(cfg, cdir, args.split)
    print(json.dumps(rec))
    if rec.get("score") is None:
        sys.exit(1)


# ---------------------------------------------------------------------------
# the usage governor — the Claude Max window as a resource (docs/aira2-loop-design.md §4, M3)
# ---------------------------------------------------------------------------
#
# Two signals, one policy. The *estimate*: list-price cost of every worker session
# that ended inside the rolling window (from session.json, as `claude -p` reports it),
# plus a reservation per running session, against `usage.window_budget`; at `soft`
# nothing new is dispatched, at `hard` running sessions are killed (a session cannot
# be paused) and their jobs deferred. The *fact*: a rate-limit message in a session's
# result defers that job and blocks dispatch until the stated reset time, or
# `usage.retry` later. Waiting is a campaign status, `waiting_usage`, with a reason
# and a next-eligible time; nobody polls the API for it.

def defer_job(cfg: dict, pop: dict, c: dict, reason: str) -> None:
    u = pop["usage"]
    u["deferred"] += 1
    sess = c.get("session") or {}
    now = time.time()
    if sess.get("rate_limited"):
        u["rate_limits"] += 1
        until = _iso_epoch(sess.get("reset_at")) or (now + cfg["usage"]["retry_sec"])
        until = max(until, _iso_epoch(u.get("blocked_until")) or 0)
        u["blocked_until"] = _epoch_iso(until)
        u["blocked_reason"] = (f"usage limit message in {c['id']}'s session"
                               + (f" (resets {sess['reset_at']})" if sess.get("reset_at")
                                  else f" (no reset time stated; retry in {cfg['usage']['retry_sec'] // 60} min)"))
    if c.get("defers", 0) < cfg["usage"]["max_defers"]:
        u["deferred_jobs"].append({"operator": c["operator"], "parents": list(c["parents"]),
                                   "from": c["id"], "defers": c.get("defers", 0) + 1,
                                   "reason": reason})


def usage_state(cfg: dict, pop: dict, now: float | None = None) -> dict:
    """The governor's view of the window: what was spent, what is reserved, how full
    the window is, and when dispatch becomes eligible again. Pure; no side effects."""
    now = now or time.time()
    u, ucfg = pop["usage"], cfg["usage"]
    win, budget = ucfg["window_sec"], ucfg["window_budget"]
    in_window: list[tuple[float, float]] = []
    all_costs: list[float] = []
    running = 0
    for c in pop["candidates"].values():
        if c["operator"] == "baseline":
            continue
        if c["status"] in ("queued", "running"):
            running += 1
            continue
        s = c.get("session") or {}
        cost = s.get("cost_usd")
        if cost is None:
            continue
        all_costs.append(float(cost))
        end = _iso_epoch(c.get("ended")) or _iso_epoch(c.get("launched"))
        if end is not None and now - end < win:
            in_window.append((end, float(cost)))
    if len(all_costs) >= 3:
        srt = sorted(all_costs)
        reserve_each = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
    else:
        reserve_each = ucfg["session_cost"]
    spend = sum(cost for _, cost in in_window)
    reserved = reserve_each * running
    st = {"window_sec": win, "budget": budget, "spend": round(spend, 4), "reserved": round(reserved, 4),
          "reserve_each": round(reserve_each, 4), "sessions_in_window": len(in_window),
          "running": running, "fraction": None, "level": "ok", "reason": None,
          "next_eligible": None, "now": _epoch_iso(now)}
    blocked_until = _iso_epoch(u.get("blocked_until"))
    if blocked_until and blocked_until > now:
        st["level"], st["reason"], st["next_eligible"] = "blocked", u.get("blocked_reason"), u["blocked_until"]
    if budget:
        frac = (spend + reserved) / budget
        st["fraction"] = round(frac, 4)
        level = "hard" if frac >= ucfg["hard"] else "soft" if frac >= ucfg["soft"] else "ok"
        if level != "ok":
            remaining = spend + reserved
            t = None
            for end, cost in sorted(in_window):
                remaining -= cost
                if remaining < ucfg["soft"] * budget:
                    t = end + win
                    break
            t = t or (now + win)
            reason = (f"window estimate {frac:.0%} of budget ${budget:g} "
                      f"(${spend:.2f} spent in the last {win // 3600}h{(win % 3600) // 60:02d}m"
                      + (f" + ${reserved:.2f} reserved for {running} running" if running else "")
                      + f") ≥ {level} {ucfg[level]:.0%}")
            if st["level"] != "blocked" or (st["next_eligible"] and _iso_epoch(st["next_eligible"]) < t):
                st["level"], st["reason"], st["next_eligible"] = level, reason, _epoch_iso(t)
            elif st["level"] == "blocked":
                st["level"] = level   # a hard level still kills; keep the later next_eligible
                st["reason"] = f"{u.get('blocked_reason')}; also {reason}"
    return st


def _close_wait(pop: dict, now: float) -> None:
    u = pop["usage"]
    since = _iso_epoch(u.get("waiting_since"))
    if since is not None:
        u["waiting_seconds"] += max(0.0, now - since)
    u["waiting_since"] = None


def govern(cfg: dict, pop: dict) -> dict:
    """Move the campaign between running and waiting_usage; kill at hard. Returns the state."""
    now = time.time()
    st = usage_state(cfg, pop, now)
    u = pop["usage"]
    if st["fraction"] is not None:
        u["peak_fraction"] = max(u.get("peak_fraction", 0.0), st["fraction"])
    if st["level"] == "hard":
        for c in pop["candidates"].values():
            if c["status"] == "running" and c["operator"] != "baseline" and c.get("watch") \
                    and not c.get("usage_kill"):
                c["usage_kill"] = True
                u["hard_kills"] += 1
                _lab("watch", "kill", c["watch"], "--reason",
                     f"usage_hard: {st['reason']}", check=False)
    blocked = st["level"] != "ok"
    if blocked and pop["status"] == "running":
        pop["status"] = "waiting_usage"
        u["waiting_since"] = _epoch_iso(now)
        u["pauses"] += 1
        u["waiting_reason"], u["next_eligible"] = st["reason"], st["next_eligible"]
        L.emit("campaign.paused",
               f"campaign {pop['campaign']} waiting on usage ({st['level']}): next eligible "
               f"{st['next_eligible']}",
               {"campaign": pop["campaign"], "level": st["level"], "reason": st["reason"],
                "next_eligible": st["next_eligible"], "spend": st["spend"], "reserved": st["reserved"],
                "budget": st["budget"], "fraction": st["fraction"],
                "kills": u["hard_kills"] if st["level"] == "hard" else 0})
    elif blocked and pop["status"] == "waiting_usage":
        u["waiting_reason"], u["next_eligible"] = st["reason"], st["next_eligible"]
    elif not blocked and pop["status"] == "waiting_usage":
        since = _iso_epoch(u.get("waiting_since")) or now
        _close_wait(pop, now)
        pop["status"] = "running"
        u["waiting_reason"], u["next_eligible"] = None, None
        L.emit("note", f"campaign {pop['campaign']} resumed after {(now - since) / 60:.1f} min "
                       f"waiting on usage; {len(u['deferred_jobs'])} deferred job(s) queued",
               {"campaign": pop["campaign"], "waited_sec": round(now - since),
                "waiting_total_sec": round(u["waiting_seconds"]),
                "deferred_jobs": len(u["deferred_jobs"])})
    return st


# ---------------------------------------------------------------------------
# selection — AIRA₂ temperature-scaled rank selection
# ---------------------------------------------------------------------------

def rank_select(cfg: dict, pool: list[dict], rng: random.Random, k: int = 1) -> list[dict]:
    hib = cfg["report"]["higher_is_better"]
    ranked = sorted(pool, key=lambda c: c["fitness"], reverse=hib)
    n = len(ranked)
    tau = cfg["selection"]["temperature"]
    weights = [math.exp(-(i / max(1, n - 1)) / tau) for i in range(n)]
    chosen: list[dict] = []
    idx = list(range(n))
    for _ in range(min(k, n)):
        pick = rng.choices(idx, weights=[weights[i] for i in idx])[0]
        chosen.append(ranked[pick])
        idx.remove(pick)
    return chosen


def choose_job(cfg: dict, pop: dict, rng: random.Random) -> tuple[str, list[str], dict | None] | None:
    """(operator, parents, origin) — origin names the deferred job being re-dispatched."""
    cands = pop["candidates"]
    running = [c for c in cands.values() if c["status"] in ("queued", "running")]
    if not any(c["operator"] == "baseline" for c in cands.values()):
        return ("baseline", [], None)
    # a job the window pushed out comes back before anything new is chosen
    while pop["usage"]["deferred_jobs"]:
        job = pop["usage"]["deferred_jobs"].pop(0)
        if all(p in cands for p in job["parents"]):
            return (job["operator"], list(job["parents"]), {"from": job["from"], "defers": job["defers"]})
    evaluated = [c for c in cands.values() if c["status"] == "evaluated" and c["fitness"] is not None]
    # a failed candidate under its retry cap gets one debug child before anything else
    for c in sorted(cands.values(), key=lambda c: c["id"]):
        if c["status"] == "failed" and not c["debugged"] and c["operator"] != "baseline":
            depth = 0
            cur = c
            while cur and cur["operator"] == "debug" and cur["parents"]:
                depth += 1
                cur = cands.get(cur["parents"][0])
            if depth < cfg["selection"]["max_debug_retries"]:
                c["debugged"] = True
                return ("debug", [c["id"]], None)
            c["debugged"] = True
    non_baseline = [c for c in evaluated if c["operator"] != "baseline"]
    if not non_baseline:
        # nothing to improve on yet: draft, but don't stack more drafts than slots
        if len([c for c in running if c["operator"] == "draft"]) < cfg["resources"]["max_parallel_jobs"]:
            return ("draft", [], None)
        return None
    # a fresh approach, not a tweak: drawn before crossover, and only when draft_p > 0 so
    # a campaign without the key consumes exactly the random stream it always did
    if cfg["selection"].get("draft_p", 0.0) > 0 and rng.random() < cfg["selection"]["draft_p"]:
        return ("draft", [], None)
    if len(evaluated) >= 2 and rng.random() < cfg["selection"]["crossover_p"]:
        a, b = rank_select(cfg, evaluated, rng, k=2)
        return ("crossover", [a["id"], b["id"]], None)
    (a,) = rank_select(cfg, evaluated, rng, k=1)
    return ("improve", [a["id"]], None)


# ---------------------------------------------------------------------------
# stop, finish, report
# ---------------------------------------------------------------------------

def stop_reason(cfg: dict, pop: dict) -> str | None:
    st = cfg["stop"]
    if (L.LAB_DIR / "campaign.stop").exists():
        return "stopped by `lab campaign stop`"
    if st["max_candidates"] and pop["settled"] >= st["max_candidates"]:
        return f"max_candidates {st['max_candidates']} reached"
    if st["no_improvement_for"] and pop["best"] and \
            pop["settled"] - pop["settled_at_best"] >= st["no_improvement_for"]:
        return f"no improvement in {st['no_improvement_for']} settled candidates"
    if st["wall_clock_sec"] and _duration_sec(pop["started"], L.now_iso()) >= st["wall_clock_sec"]:
        return f"wall clock {st['wall_clock_sec']}s reached"
    if cfg["resources"]["gpu_hours_total"] and \
            pop["gpu_seconds"] / 3600 >= cfg["resources"]["gpu_hours_total"]:
        return f"gpu_hours_total {cfg['resources']['gpu_hours_total']} reached"
    return None


def run_final(cfg: dict, pop: dict, poll_sec: float) -> None:
    """Freeze the best candidate, run its code once on the final inputs under a watcher,
    evaluate once. Restart-safe: population.json records every step."""
    best = pop.get("best")
    fin = pop.get("final") or {}
    if not best:
        pop["final"] = {"candidate": None, "score": None, "n": None,
                        "note": "no evaluated candidate to freeze"}
        pop["claim"] = "inconclusive"
        save_pop(pop)
        return
    c = pop["candidates"][best]
    cdir = cand_dir(best)
    if c["status"] != "frozen":
        c["status"] = "frozen"
        save_pop(pop)
    if fin.get("score") is not None or fin.get("error"):
        return
    if not fin.get("watch"):
        env = worker_env(cfg, best, "final", c["gpu"], split="final")
        budget_min = max(1, math.ceil(cfg["resources"]["job_wall_clock_sec"] / 60))
        env.pop("LAB_ROLE", None)
        cp = _lab("watch", "start", "--op", f"final-{best}", "--budget-min", str(budget_min),
                  "--candidate-dir", str(cdir),
                  "--", "bash", "-c", f"cd {cdir} && bash code/run.sh", env=env)
        fin = {"candidate": best, "watch": cp.stdout.strip().splitlines()[-1],
               "started": L.now_iso(), "score": None, "n": None}
        pop["final"] = fin
        save_pop(pop)
    while True:
        entry = watch_entry(fin["watch"])
        if entry is None:
            fin["error"] = "final watch entry lost"
            break
        entry = L._watch_repair(entry)
        if entry.get("status") != "running":
            break
        time.sleep(poll_sec)
    if not fin.get("error"):
        if entry.get("status") != "done":
            fin["error"] = f"final run {entry.get('status')}: {entry.get('kill_reason') or entry.get('exit_code')}"
        else:
            rec = evaluate(cfg, cdir, "final")
            fin["score"], fin["n"] = rec.get("score"), rec.get("n")
            if rec.get("score") is None:
                fin["error"] = rec.get("error")
        if (L.WATCH_DIR / f"{fin['watch']}.json").exists():
            _lab("watch", "close", fin["watch"], check=False)
    fin["ended"] = L.now_iso()
    thr = cfg["report"]["success_threshold"]
    if fin.get("score") is None:
        pop["claim"] = "inconclusive"
    else:
        ok = fin["score"] >= thr if cfg["report"]["higher_is_better"] else fin["score"] <= thr
        pop["claim"] = "supported" if ok else "not_supported"
    pop["final"] = fin
    save_pop(pop)


def write_report(cfg: dict, pop: dict) -> None:
    cands = pop["candidates"]
    base = next((c for c in cands.values() if c["operator"] == "baseline"), None)
    best = cands.get(pop["best"]) if pop.get("best") else None
    fin = pop.get("final") or {}
    counts: dict[str, int] = {}
    for c in cands.values():
        counts[c["exec"] or c["status"]] = counts.get(c["exec"] or c["status"], 0) + 1
    hours = pop["gpu_seconds"] / 3600
    wall = _duration_sec(pop["started"], pop.get("finished") or L.now_iso()) / 3600
    thr = cfg["report"]["success_threshold"]
    fmt = lambda v: "—" if v is None else f"{v:.6g}"
    lines = [
        f"# REPORT — campaign {pop['campaign']}",
        "",
        f"Written once by `lab run` on {L.now_iso()}. Search fitness is measured on the hidden "
        "search split and is optimistic by construction; the final score is one read of the "
        "final split, never used during search.",
        "",
        "| | |",
        "|---|---|",
        f"| claim | **{pop['claim']}** |",
        f"| success threshold (fixed before the campaign) | {fmt(thr)} ({'higher' if cfg['report']['higher_is_better'] else 'lower'} is better) |",
        f"| final score (best candidate, final split, read once) | {fmt(fin.get('score'))}" + (f" — {fin['error']}" if fin.get("error") else "") + " |",
        f"| best candidate by search fitness | {best['id'] if best else '—'} ({best['operator']}) {fmt(best['fitness']) if best else ''} |",
        f"| baseline search fitness | {fmt(base['fitness']) if base else '—'} |",
        f"| candidates settled | {pop['settled']} ({', '.join(f'{k} {v}' for k, v in sorted(counts.items()))}) |",
        f"| GPU-hours | {hours:.2f} of {cfg['resources']['gpu_hours_total'] or '∞'} |",
        f"| settled candidates per GPU-hour | {(pop['settled'] / hours):.2f} |" if hours > 0
        else "| settled candidates per GPU-hour | — (no GPU time recorded) |",
        f"| GPUs | {', '.join(str(g) for g in cfg['resources']['gpus']) or 'none (CPU)'}; "
        f"max parallel {cfg['resources']['max_parallel_jobs']}"
        + (f"; min free VRAM {cfg['resources']['min_free_vram_mb']} MiB" if cfg['resources']['min_free_vram_mb'] else "") + " |",
        f"| wall clock | {wall:.2f} h |",
        f"| stop reason | {pop.get('stop_reason') or '—'} |",
        f"| privilege separation for labels | {'on (' + cfg['eval']['user'] + ')' if cfg['eval']['user'] else 'OFF — labels were readable to the evaluator user only by convention'} |",
        f"| auth preflight | {'ok' if pop['auth_preflight']['ok'] else 'FAILED'} at {pop['auth_preflight']['checked_at']} |",
        f"| campaign.toml sha256 | `{pop['campaign_sha256'][:16]}` |",
        f"| memory | {memory_policy(pop)['policy']}"
        + (" — one finding card per settled candidate (candidates/cNNNN/finding.json); each job saw a "
           "bounded snapshot of cards stored in its job.json" if memory_policy(pop)["policy"] == F.POLICY
           else " — first-parent lineage of clipped summaries") + " |",
        "",
        "## Population",
        "",
        "| id | operator | parents | exec | search fitness | note |",
        "|---|---|---|---|---|---|",
    ]
    for cid, c in cands.items():
        lines.append(f"| {cid} | {c['operator']} | {','.join(c['parents']) or '—'} | "
                     f"{c['exec'] or c['status']} | {fmt(c['fitness'])} | "
                     f"{(c.get('fail_reason') or ('frozen' if c['status'] == 'frozen' else '')).replace('|', '/')} |")
    lines += ["", "## Usage (the Claude Max window)", ""] + usage_report_lines(cfg, pop, wall)
    lines += ["", "## Best candidate summary", "", read_summary(best["id"], 4000) if best else "_none_", ""]
    (L.ROOT / REPORT_FILE).write_text("\n".join(lines))


def usage_report_lines(cfg: dict, pop: dict, wall_hours: float) -> list[str]:
    u = pop.get("usage") or usage_defaults()
    ucfg = cfg["usage"]
    sessions = [c["session"] for c in pop["candidates"].values() if c.get("session")]
    costs = sorted(float(s["cost_usd"]) for s in sessions if s.get("cost_usd") is not None)
    turns = [s["turns"] for s in sessions if s.get("turns") is not None]
    total = sum(costs)
    median = (costs[len(costs) // 2] if len(costs) % 2 else
              (costs[len(costs) // 2 - 1] + costs[len(costs) // 2]) / 2) if costs else None
    waited_h = u["waiting_seconds"] / 3600
    idle_pct = (waited_h / wall_hours * 100) if wall_hours > 0 else 0.0
    win = ucfg["window_sec"]
    gov = (f"estimate against ${ucfg['window_budget']:g} per {win / 3600:g} h window, "
           f"soft {ucfg['soft']:.0%} / hard {ucfg['hard']:.0%}, plus rate-limit detection"
           if ucfg["window_budget"] else
           "OFF — no usage.window_budget; rate-limit detection only")
    return [
        "| | |", "|---|---|",
        f"| governor | {gov} |",
        f"| worker sessions | {len(sessions)} (turns: median {sorted(turns)[len(turns) // 2] if turns else '—'}, "
        f"max {max(turns) if turns else '—'}) |",
        f"| list-price equivalent, all sessions | ${total:.2f} (median ${median:.2f} per session) |" if costs
        else "| list-price equivalent, all sessions | — (no session.json costs) |",
        f"| peak window estimate | {u['peak_fraction']:.0%} of budget |" if ucfg["window_budget"]
        else "| peak window estimate | — |",
        f"| pauses on usage | {u['pauses']} ({u['rate_limits']} after a rate-limit message, "
        f"{u['hard_kills']} session(s) killed at hard) |",
        f"| time waiting on usage | {waited_h:.2f} h = {idle_pct:.1f}% of wall clock |",
        f"| jobs deferred | {u['deferred']} (re-dispatched: "
        f"{sum(1 for c in pop['candidates'].values() if c.get('redispatch_of'))}) |",
        "",
        "All costs are the list-price equivalents `claude -p` reports for a subscription session; "
        "the subscription itself is prepaid. Sessions ran on subscription login only "
        f"(auth preflight {'ok' if pop['auth_preflight']['ok'] else 'FAILED'}).",
    ]


def finish(cfg: dict, pop: dict, poll_sec: float) -> None:
    pop.setdefault("usage", usage_defaults())
    _close_wait(pop, time.time())
    run_final(cfg, pop, poll_sec)
    pop["status"] = "finished"
    pop["finished"] = pop.get("finished") or L.now_iso()
    save_pop(pop)
    write_report(cfg, pop)
    fin = pop.get("final") or {}
    L.emit("campaign.stop",
           f"campaign {pop['campaign']} finished: claim {pop['claim']}, best {pop.get('best')} "
           f"final {fin.get('score') if fin.get('score') is not None else 'n/a'} vs threshold "
           f"{cfg['report']['success_threshold']:.6g}; {pop['settled']} candidates",
           {"campaign": pop["campaign"], "claim": pop["claim"], "best": pop.get("best"),
            "final_score": fin.get("score"), "success_threshold": cfg["report"]["success_threshold"],
            "settled": pop["settled"], "gpu_hours": round(pop["gpu_seconds"] / 3600, 3),
            "stop_reason": pop.get("stop_reason"), "report": REPORT_FILE})


# ---------------------------------------------------------------------------
# the loop
# ---------------------------------------------------------------------------

def gpu_free_vram_mb() -> dict[int, int] | None:
    """{gpu index: free MiB} from nvidia-smi, or None when it is unavailable."""
    try:
        cp = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used,memory.total",
                             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if cp.returncode != 0:
        return None
    out: dict[int, int] = {}
    for line in cp.stdout.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) == 3 and all(x.lstrip("-").isdigit() for x in parts):
            out[int(parts[0])] = int(parts[2]) - int(parts[1])
    return out


def free_slots(cfg: dict, pop: dict) -> list[int | None]:
    """GPU slots (or CPU slots) that may take a job this tick. A GPU whose free VRAM is
    under resources.min_free_vram_mb — something else is using it — is skipped, once
    per tick, with a note the first time; it is leased again when the memory is back."""
    busy = [c["gpu"] for c in pop["candidates"].values() if c["status"] in ("queued", "running")]
    n_running = len(busy)
    if n_running >= cfg["resources"]["max_parallel_jobs"]:
        return []
    room = cfg["resources"]["max_parallel_jobs"] - n_running
    if not cfg["resources"]["gpus"]:
        return [None] * room
    idle = [g for g in cfg["resources"]["gpus"] if g not in busy]
    need = cfg["resources"]["min_free_vram_mb"]
    if idle and need > 0:
        free = gpu_free_vram_mb()
        if free is not None:
            held = pop.setdefault("vram_held", {})
            ok = []
            for g in idle:
                have = free.get(g)
                if have is not None and have < need:
                    if not held.get(str(g)):
                        held[str(g)] = L.now_iso()
                        L.emit("note", f"gpu {g} has {have} MiB free, below {need}; not leasing it "
                                       "until the memory is back", {"gpu": g, "free_mb": have,
                                                                    "min_free_vram_mb": need})
                    continue
                if held.get(str(g)):
                    held.pop(str(g), None)
                    L.emit("note", f"gpu {g} has {have} MiB free again; leasing it",
                           {"gpu": g, "free_mb": have})
                ok.append(g)
            idle = ok
    return idle[:room]


def pick_job(cfg: dict, pop: dict, rng: random.Random, in_flight: set) -> tuple | None:
    """choose_job, but two free slots in one tick must not both improve (or cross) the
    same parents: with a seeded worker that is the same job twice. Re-sample a few
    times; a persistent duplicate (tiny population) is accepted rather than idling."""
    job = choose_job(cfg, pop, rng)
    for _ in range(8):
        if job is None or job[2] is not None or job[0] in ("baseline", "draft", "debug") \
                or (job[0], tuple(job[1])) not in in_flight:
            break
        job = choose_job(cfg, pop, rng)
    return job


def tick(cfg: dict, pop: dict) -> None:
    pop["tick"] += 1
    rng = random.Random(f"{pop['campaign']}:{pop['seed']}:{pop['tick']}")
    pop.setdefault("usage", usage_defaults())
    reap(cfg, pop)
    save_pop(pop)          # settlement is durable before any card is published
    ensure_cards(cfg, pop)
    if pop["status"] in ("running", "waiting_usage"):
        reason = stop_reason(cfg, pop)
        if reason:
            _close_wait(pop, time.time())
            pop["status"], pop["stop_reason"] = "stopping", reason
            L.emit("note", f"campaign {pop['campaign']} stopping: {reason}",
                   {"campaign": pop["campaign"], "reason": reason})
    if pop["status"] in ("running", "waiting_usage"):
        govern(cfg, pop)
    if pop["status"] == "running":
        in_flight = {(c["operator"], tuple(c["parents"])) for c in pop["candidates"].values()
                     if c["status"] in ("queued", "running")}
        for gpu in free_slots(cfg, pop):
            job = pick_job(cfg, pop, rng, in_flight)
            if job is None:
                break
            op, parents, origin = job
            in_flight.add((op, tuple(parents)))
            cid = new_candidate(cfg, pop, op, parents, gpu, rng, origin)
            save_pop(pop)
            launch(cfg, pop, cid)
            save_pop(pop)
    save_pop(pop)


def cmd_run(args) -> None:
    cfg = load_campaign(Path(args.campaign))
    L.LAB_DIR.mkdir(parents=True, exist_ok=True)
    lockf = open(L.LAB_DIR / "campaign.lock", "w")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        L.die("another `lab run` holds .lab/campaign.lock")
    pop = load_pop()
    if pop is None:
        pop = init_pop(cfg)
    elif pop["campaign_sha256"] != cfg["sha256"]:
        L.die(f"{cfg['path'].name} changed since this campaign started (population.json records "
              f"{pop['campaign_sha256'][:12]}, file is {cfg['sha256'][:12]}). A changed campaign "
              "is a new campaign: move population.json, candidates/ and REPORT.md aside first.")
    elif pop["campaign"] != cfg["campaign"]["id"]:
        L.die(f"population.json belongs to campaign {pop['campaign']}, not {cfg['campaign']['id']}")
    if pop["status"] == "finished":
        print(f"campaign {pop['campaign']} is finished; see {REPORT_FILE}")
        return
    pop.setdefault("usage", usage_defaults())
    mem = memory_policy(pop)
    if mem["policy"] == "legacy" and cfg["memory"]["mode"] != "legacy":
        L.warn(f"{POP_FILE} has no memory policy snapshot: this campaign stays legacy "
               f"(campaign.toml asks for {cfg['memory']['mode']}, which applies to new campaigns)")

    ticks = 0
    while True:
        tick(cfg, pop)
        ticks += 1
        running = [c for c in pop["candidates"].values() if c["status"] in ("queued", "running")]
        if pop["status"] == "stopping" and not running:
            finish(cfg, pop, args.poll_sec)
            print(f"finished: claim {pop['claim']}; see {REPORT_FILE}")
            return
        if args.once or (args.max_ticks and ticks >= args.max_ticks):
            break
        time.sleep(args.poll_sec)
    print(json.dumps({"status": pop["status"], "tick": pop["tick"], "settled": pop["settled"],
                      "running": len([c for c in pop["candidates"].values() if c["status"] == "running"]),
                      "best": pop["best"], "next_eligible": pop["usage"].get("next_eligible")}))


def _campaign_cfg(pop: dict) -> dict | None:
    """The campaign config for read-only views. A full load needs LAB_PRIVATE and the
    data dirs; when that fails (another shell, a finished campaign moved elsewhere) fall
    back to the [usage] table alone, which is all the governor's view needs."""
    p = L.ROOT / pop.get("campaign_file", "campaign.toml")
    if not p.exists():
        return None
    try:
        with open(os.devnull, "w") as sink, _redirect_stderr(sink):
            return load_campaign(p)
    except SystemExit:
        try:
            raw = tomllib.loads(p.read_text())
            return {"usage": parse_usage(raw, p.name), "partial": True}
        except (SystemExit, tomllib.TOMLDecodeError, OSError):
            return None


def cmd_campaign_status(args) -> None:
    pop = load_pop()
    if pop is None:
        L.die(f"no {POP_FILE}: no campaign has started here")
    pop.setdefault("usage", usage_defaults())
    rows = [(k, v["operator"], ",".join(v["parents"]) or "-", v["exec"] or v["status"],
             "-" if v["fitness"] is None else f"{v['fitness']:.6g}") for k, v in pop["candidates"].items()]
    print(f"campaign {pop['campaign']}  status {pop['status']}  tick {pop['tick']}  "
          f"settled {pop['settled']}  best {pop['best']}  claim {pop['claim']}  "
          f"gpu-h {pop['gpu_seconds']/3600:.2f}")
    cfg = _campaign_cfg(pop)
    if cfg is not None:
        st = usage_state(cfg, pop)
        print("  usage: " + _usage_line(cfg, pop, st))
    for r in rows:
        print("  " + "  ".join(f"{x:<12}" if i < 4 else x for i, x in enumerate(r)))


def _usage_line(cfg: dict, pop: dict, st: dict) -> str:
    u = pop["usage"]
    if st["budget"]:
        head = (f"${st['spend']:.2f} spent + ${st['reserved']:.2f} reserved of ${st['budget']:g} "
                f"({st['fraction']:.0%}) in the last {st['window_sec'] / 3600:g} h, "
                f"{st['sessions_in_window']} session(s)")
    else:
        head = (f"${st['spend']:.2f} spent in the last {st['window_sec'] / 3600:g} h, "
                f"{st['sessions_in_window']} session(s); no window_budget (rate-limit detection only)")
    tail = f"; level {st['level']}"
    if st["level"] != "ok":
        tail += f", next eligible {st['next_eligible']}"
    tail += (f"; waited {u['waiting_seconds'] / 60:.0f} min over {u['pauses']} pause(s)"
             f", {u['deferred']} deferred, {u['rate_limits']} rate-limit message(s)")
    return head + tail


def cmd_campaign_usage(args) -> None:
    """The governor's view: what the window holds and when dispatch is eligible.
    The number to calibrate `usage.window_budget` from: run a short campaign, read the
    spend per session here, and set the budget to what the plan tolerated."""
    pop = load_pop()
    if pop is None:
        L.die(f"no {POP_FILE}: no campaign has started here")
    pop.setdefault("usage", usage_defaults())
    cfg = _campaign_cfg(pop)
    if cfg is None:
        L.die(f"{pop.get('campaign_file')} not found; the governor needs the campaign file")
    st = usage_state(cfg, pop)
    sessions = [{"candidate": k, "ended": v.get("ended"), **{kk: v["session"].get(kk) for kk in
                 ("id", "turns", "cost_usd", "rate_limited", "reset_at")}}
                for k, v in pop["candidates"].items() if v.get("session")]
    if args.json:
        print(json.dumps({"state": st, "governor": pop["usage"], "sessions": sessions,
                          "config": {k: v for k, v in cfg["usage"].items() if k != "rate_limit_regex"}},
                         indent=2))
        return
    print(f"campaign {pop['campaign']}  status {pop['status']}")
    print("usage: " + _usage_line(cfg, pop, st))
    if pop["usage"]["deferred_jobs"]:
        print("deferred jobs queued: " + ", ".join(
            f"{j['operator']}({','.join(j['parents']) or '-'}) from {j['from']}" for j in pop["usage"]["deferred_jobs"]))
    print(f"{'candidate':10} {'ended (UTC)':20} {'turns':>5} {'cost $':>8}  note")
    for s in sessions:
        note = "RATE LIMITED" + (f", resets {s['reset_at']}" if s.get("reset_at") else "") if s.get("rate_limited") else ""
        cost = "—" if s.get("cost_usd") is None else f"{float(s['cost_usd']):.2f}"
        print(f"{s['candidate']:10} {(s.get('ended') or '?'):20} {str(s.get('turns') or '—'):>5} {cost:>8}  {note}")


def cmd_campaign_stop(args) -> None:
    L.LAB_DIR.mkdir(parents=True, exist_ok=True)
    (L.LAB_DIR / "campaign.stop").write_text(L.now_iso() + "\n")
    if args.now:
        pop = load_pop() or {"candidates": {}}
        for c in pop["candidates"].values():
            if c["status"] == "running" and c.get("watch"):
                _lab("watch", "kill", c["watch"], "--reason", "campaign stopped --now", check=False)
    print("stop requested; `lab run` finishes when running jobs end"
          + (" (kills requested)" if args.now else ""))


def cmd_candidate_list(args) -> None:
    pop = load_pop()
    if pop is None:
        L.die(f"no {POP_FILE}")
    for k, v in pop["candidates"].items():
        print(json.dumps({"id": k, "operator": v["operator"], "parents": v["parents"],
                          "status": v["status"], "exec": v["exec"], "fitness": v["fitness"]}))


def cmd_job_card(args) -> None:
    cdir = Path(args.dir)
    if not cdir.is_absolute():
        cdir = L.ROOT / cdir
    card = json.loads((cdir / "job.json").read_text())
    task = (L.ROOT / card["task_file"]).read_text()
    print(render_job_card(card, task))


def render_job_card(card: dict, task: str) -> str:
    """The prompt a worker receives, from its job.json snapshot and the task text."""
    out = [f"# Job {card['candidate']} — operator `{card['operator']}`", "",
           card["instructions"], "",
           "## Task", "", task.strip(), "",
           "## Contract", "",
           f"- You may write only inside `{card['contract']['may_write']}`.",
           f"- You may read: {', '.join('`' + p + '`' for p in card['contract']['may_read'])}.",
           f"- Write `{card['contract']['write']}`.",
           f"- Run `{card['contract']['run']}`; `{card['contract']['predictions']}` must exist when you exit.",
           f"- {card['contract']['final']}.",
           f"- Inherited: {card['contract'].get('inherited', 'nothing')}.",
           f"- Seed everything with {card['seed']}.",
           f"- Turn budget: {card['contract']['max_turns']}. If you cannot finish, write summary.md "
           "saying what you learned and exit; the job is re-dispatched once with your summary.",
           ""]
    findings = card.get("findings")
    if card["contract"].get("summary_format"):
        out += ["## summary.md format", "", card["contract"]["summary_format"], ""]
    if card["parents"]:
        out += ["## Parents", ""]
        for p in card["parents"]:
            out += [f"### {p['id']} — fitness {p['fitness']} — exec {p['exec']}"
                    + (f" — {p['fail_reason']}" if p.get("fail_reason") else ""),
                    f"code: `{p['path']}/code`"]
            if findings is None:
                out += ["", p["summary"] or "_no summary_", ""]
            else:
                out += [f"full summary: `{p.get('summary_file', p['path'] + '/summary.md')}` "
                        "(its finding card is below)", ""]
    if findings is not None:
        # Rendered at dispatch and stored in job.json; never re-selected here, so the
        # card a worker saw is what this prints, whatever has ended since.
        out += [findings["rendered"].rstrip("\n"), ""]
    if card["lineage"]:
        out += ["## Lineage (newest first)", ""]
        for a in card["lineage"]:
            out += [f"- **{a['id']}** ({a['operator']}, fitness {a['fitness']}): {a['summary'] or '_no summary_'}"]
        out += [""]
    out += ["## Population", "", "| id | operator | status | fitness |", "|---|---|---|---|"]
    out += [f"| {p['id']} | {p['operator']} | {p['status']} | {p['fitness']} |" for p in card["population"]]
    out += ["", f"Best so far: {card['best']}", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

def register(sub, lab_module) -> None:
    global L
    L = lab_module
    import lab_serve
    lab_serve.register(sub, lab_module)

    sp = sub.add_parser("campaign", help="the search loop's campaign: check | status | stop")
    s2 = sp.add_subparsers(dest="campaign_cmd", required=True)
    q = s2.add_parser("init", help="scaffold campaign.toml, task.md, eval/, data/ here")
    q.add_argument("id")
    q.add_argument("--force", action="store_true")
    q.set_defaults(func=cmd_campaign_init)
    q = s2.add_parser("check", help="validate a campaign.toml")
    q.add_argument("file", nargs="?", default="campaign.toml")
    q.set_defaults(func=cmd_campaign_check)
    q = s2.add_parser("status", help="population at a glance")
    q.set_defaults(func=cmd_campaign_status)
    q = s2.add_parser("usage", help="the usage governor's view of the Max window; calibrate "
                                    "usage.window_budget from it")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_campaign_usage)
    q = s2.add_parser("stop", help="stop dispatching; finish when running jobs end")
    q.add_argument("--now", action="store_true", help="also kill running jobs")
    q.set_defaults(func=cmd_campaign_stop)

    sp = sub.add_parser("candidate", help="candidates of the running campaign")
    s2 = sp.add_subparsers(dest="candidate_cmd", required=True)
    q = s2.add_parser("list")
    q.set_defaults(func=cmd_candidate_list)

    sp = sub.add_parser("eval", help="score a candidate's predictions on the search split "
                                     "(the only reader of labels)")
    sp.add_argument("dir")
    sp.add_argument("--split", default="search", choices=["search", "final"])
    sp.add_argument("--campaign", default="campaign.toml")
    sp.set_defaults(func=cmd_eval)

    sp = sub.add_parser("job", help="job cards for workers")
    s2 = sp.add_subparsers(dest="job_cmd", required=True)
    q = s2.add_parser("card", help="print the job card for a candidate dir as markdown")
    q.add_argument("dir")
    q.set_defaults(func=cmd_job_card)

    sp = sub.add_parser("run", help="run the campaign loop (reap → enforce → dispatch → stop → report)")
    sp.add_argument("campaign", nargs="?", default="campaign.toml")
    sp.add_argument("--once", action="store_true", help="one tick, then exit")
    sp.add_argument("--max-ticks", type=int, default=0)
    sp.add_argument("--poll-sec", type=float, default=15.0)
    sp.set_defaults(func=cmd_run)
