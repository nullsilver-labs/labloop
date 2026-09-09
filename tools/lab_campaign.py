"""lab campaign | candidate | eval | job | run — the AIRA₂-style search loop.

See NEXT.md. This module is registered into `tools/lab` and shares its helpers
(events, redaction, provenance, LEDGER, watchers), so `lab` stays the single writer
of population.json, LEDGER.md and events.jsonl.

The loop (`lab run`): reap finished jobs → enforce budgets → dispatch while a GPU slot
is free (rank-selected parent + operator) → stop on a stop condition → freeze the
best candidate by search fitness → evaluate it once on the final split → REPORT.md.

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

L: Any = None          # the `lab` module, injected by register()

POP_FILE = "population.json"
CAND_DIR = "candidates"
REPORT_FILE = "REPORT.md"
OPERATORS = ["baseline", "draft", "improve", "crossover", "debug"]
CAND_STATUS = ["queued", "running", "evaluated", "failed", "frozen"]
EXEC_STATUS = ["completed", "failed", "killed", "invalid"]
CLAIMS = ["untested", "supported", "not_supported", "inconclusive"]
# Environment that would route a Claude Code session away from subscription login
# or to a paid path. `lab run` refuses to start while any of these is set.
PAID_ROUTE_ENV = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                  "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                  "ANTHROPIC_CUSTOM_HEADERS"]

OPERATOR_TEXT = {
    "baseline": "Produce the trivial baseline exactly as the task describes it. No cleverness.",
    "draft": "Write a first complete solution from the task statement. Prefer simple and "
             "runnable over ambitious. State in summary.md what you tried and why.",
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
        "usage_soft": float(r.get("usage_soft", 0.7)),
        "usage_hard": float(r.get("usage_hard", 0.9)),
    }
    if cfg["resources"]["max_parallel_jobs"] < 1:
        L.die(f"{path.name}: resources.max_parallel_jobs must be >= 1")

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
        "max_debug_retries": int(s.get("max_debug_retries", 1)),
        "seed": int(s.get("seed", int(hashlib.sha256(cid.encode()).hexdigest()[:8], 16))),
    }
    if not (0 <= cfg["selection"]["crossover_p"] <= 1):
        L.die(f"{path.name}: selection.crossover_p must be in [0,1]")
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

    ev = raw.get("eval", {})
    cfg["eval"] = {"user": ev.get("user") or None,
                   "timeout_sec": parse_duration(ev.get("timeout", "10m"), "eval.timeout")}
    if cfg["eval"]["user"] is None:
        for split in ("search", "final"):
            if not cfg["data"][split]["labels"].exists():
                L.die(f"{path.name}: data.{split}.labels {cfg['data'][split]['labels']} does not "
                      "exist and no [eval] user is set to read it for you")
    return cfg


def cmd_campaign_check(args) -> None:
    cfg = load_campaign(Path(args.file))
    print(json.dumps({
        "id": cfg["campaign"]["id"], "sha256": cfg["sha256"][:12],
        "slots": cfg["resources"]["slots"], "max_parallel_jobs": cfg["resources"]["max_parallel_jobs"],
        "stop": cfg["stop"], "gpu_hours_total": cfg["resources"]["gpu_hours_total"],
        "privilege_separation": bool(cfg["eval"]["user"]),
        "success_threshold": cfg["report"]["success_threshold"],
    }, indent=2))


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
              " is set. The loop runs on subscription login only (NEXT.md §4); unset it.")
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
    }
    save_pop(pop)
    L.emit("campaign.start", f"campaign {cfg['campaign']['id']} started: "
           f"{len(cfg['resources']['slots'])} slot(s), stop {json.dumps(cfg['stop'])}",
           {"campaign": cfg["campaign"]["id"], "campaign_sha256": cfg["sha256"],
            "slots": cfg["resources"]["slots"], "stop": cfg["stop"],
            "success_threshold": cfg["report"]["success_threshold"]})
    return pop


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
        t = p.read_text().strip()
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
                  gpu: int | None, rng: random.Random) -> str:
    cid = f"c{len(pop['candidates']):04d}"
    cdir = cand_dir(cid)
    cdir.mkdir(parents=True, exist_ok=False)
    (cdir / "code").mkdir()
    (cdir / "out").mkdir()
    if parents:
        src = cand_dir(parents[0]) / "code"
        if src.exists():
            shutil.copytree(src, cdir / "code", dirs_exist_ok=True)
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
    }
    L.write_json_atomic(cdir / "config.json", snapshot)

    card = {
        "candidate": cid,
        "operator": operator,
        "instructions": OPERATOR_TEXT[operator],
        "task_file": rel(cfg["campaign"]["task"]),
        "candidate_dir": rel(cdir),
        "seed": seed,
        "parents": [{
            "id": p, "path": rel(cand_dir(p)),
            "fitness": pop["candidates"][p].get("fitness"),
            "exec": pop["candidates"][p].get("exec"),
            "fail_reason": pop["candidates"][p].get("fail_reason"),
            "summary": read_summary(p),
        } for p in parents],
        "lineage": [{"id": a, "operator": pop["candidates"][a]["operator"],
                     "fitness": pop["candidates"][a].get("fitness"),
                     "summary": read_summary(a, 400)}
                    for a in (lineage(pop, parents[0])[1:] if parents else [])],
        "population": [{"id": k, "operator": v["operator"], "status": v["status"],
                        "fitness": v.get("fitness")}
                       for k, v in pop["candidates"].items()],
        "best": pop.get("best"),
        "contract": {
            "write": "code/run.sh (reads $LAB_SPLIT_INPUTS, writes $LAB_PREDICTIONS_OUT) and summary.md",
            "run": "code/run.sh once for the search split before exiting",
            "predictions": "out/predictions-search.json",
            "may_write": rel(cdir), "may_read": [rel(cfg["data"]["train"]),
                                                  rel(cfg["data"]["search"]["inputs"]),
                                                  rel(cfg["campaign"]["task"])] +
                                                 [rel(cand_dir(p)) for p in parents],
            "max_turns": cfg["resources"]["worker_max_turns"],
        },
    }
    L.write_json_atomic(cdir / "job.json", card)

    pop["candidates"][cid] = {
        "id": cid, "operator": operator, "parents": parents, "status": "queued",
        "exec": None, "gpu": gpu, "watch": None, "launched": None, "ended": None,
        "fitness": None, "n": None, "fail_reason": None, "debugged": False,
        "path": rel(cdir),
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
        "CUDA_VISIBLE_DEVICES": "" if gpu is None else str(gpu),
    })
    return env


def launch(cfg: dict, pop: dict, cid: str) -> None:
    c = pop["candidates"][cid]
    env = worker_env(cfg, cid, c["operator"], c["gpu"])
    command = cfg["data"]["baseline"] if c["operator"] == "baseline" else cfg["worker"]["command"]
    budget_min = max(1, math.ceil(cfg["resources"]["job_wall_clock_sec"] / 60))
    args = ["watch", "start", "--op", f"job-{cid}", "--budget-min", str(budget_min)]
    if cfg["resources"]["stall_min"]:
        args += ["--stall-min", str(cfg["resources"]["stall_min"])]
    args += ["--", "bash", "-c", command]
    cp = _lab(*args, env=env)
    wid = cp.stdout.strip().splitlines()[-1]
    c.update({"status": "running", "watch": wid, "launched": L.now_iso()})
    with ledger_lock():
        L.ledger_upsert(cid, {"run": pop["campaign"], "exp": c["operator"], "status": "running",
                              "verdict": "", "path": c["path"], "note": ""})
    L.emit("candidate.launch",
           f"{cid} {c['operator']}" + (f" from {','.join(c['parents'])}" if c["parents"] else "") +
           (f" on gpu {c['gpu']}" if c["gpu"] is not None else " on cpu"),
           {"candidate": cid, "operator": c["operator"], "parents": c["parents"],
            "gpu": c["gpu"], "watch": wid, "campaign": pop["campaign"]})


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
    if p.exists() and p.read_text().strip():
        return
    p.write_text(f"# summary — {title}\n\n" + "".join(f"- {f}\n" for f in facts) +
                 "\nFacts-only stub written mechanically by `lab run`; the worker left no summary.\n")


def settle(cfg: dict, pop: dict, cid: str, entry: dict) -> None:
    c = pop["candidates"][cid]
    cdir = cand_dir(cid)
    status = entry.get("status")
    exec_status = {"done": "completed", "failed": "failed", "killed": "killed"}.get(status, "failed")
    c["ended"] = entry.get("ended") or L.now_iso()
    c["exit_code"] = entry.get("exit_code")
    if c.get("gpu") is not None:
        pop["gpu_seconds"] += _duration_sec(entry.get("started"), entry.get("ended"))

    preds = cdir / "out" / "predictions-search.json"
    reason = None
    if exec_status == "completed" and preds.exists():
        fit = evaluate(cfg, cdir, "search")
        if fit.get("score") is None:
            exec_status, reason = "invalid", f"evaluator: {fit.get('error', 'no score')}"
        else:
            c["fitness"], c["n"] = fit["score"], fit.get("n")
    elif exec_status == "completed":
        exec_status, reason = "invalid", "worker exited 0 but wrote no out/predictions-search.json"
    elif exec_status == "killed":
        reason = entry.get("kill_reason") or "killed by watcher"
    elif entry.get("exit_code") == 2:
        # the worker's own verdict: the session ran but left no runnable candidate
        exec_status, reason = "invalid", "worker reported the contract unmet (exit 2)"
    else:
        reason = f"worker exited {entry.get('exit_code')}"
    c["exec"] = exec_status
    c["fail_reason"] = reason
    c["status"] = "evaluated" if exec_status == "completed" else "failed"

    stub_summary(cdir, f"{cid} ({c['operator']}, {exec_status})",
                 [f"operator: {c['operator']}, parents: {', '.join(c['parents']) or 'none'}",
                  f"exec: {exec_status}" + (f" — {reason}" if reason else ""),
                  f"started {entry.get('started')}, ended {c['ended']}, exit code {c['exit_code']}",
                  f"search fitness: {c['fitness']}"])

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


def choose_job(cfg: dict, pop: dict, rng: random.Random) -> tuple[str, list[str]] | None:
    cands = pop["candidates"]
    running = [c for c in cands.values() if c["status"] in ("queued", "running")]
    if not any(c["operator"] == "baseline" for c in cands.values()):
        return ("baseline", [])
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
                return ("debug", [c["id"]])
            c["debugged"] = True
    non_baseline = [c for c in evaluated if c["operator"] != "baseline"]
    if not non_baseline:
        # nothing to improve on yet: draft, but don't stack more drafts than slots
        if len([c for c in running if c["operator"] == "draft"]) < cfg["resources"]["max_parallel_jobs"]:
            return ("draft", [])
        return None
    if len(evaluated) >= 2 and rng.random() < cfg["selection"]["crossover_p"]:
        a, b = rank_select(cfg, evaluated, rng, k=2)
        return ("crossover", [a["id"], b["id"]])
    (a,) = rank_select(cfg, evaluated, rng, k=1)
    return ("improve", [a["id"]])


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
        cp = _lab("watch", "start", "--op", f"final-{best}", "--budget-min", str(budget_min),
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
        f"| wall clock | {wall:.2f} h |",
        f"| stop reason | {pop.get('stop_reason') or '—'} |",
        f"| privilege separation for labels | {'on (' + cfg['eval']['user'] + ')' if cfg['eval']['user'] else 'OFF — labels were readable to the evaluator user only by convention'} |",
        f"| auth preflight | {'ok' if pop['auth_preflight']['ok'] else 'FAILED'} at {pop['auth_preflight']['checked_at']} |",
        f"| campaign.toml sha256 | `{pop['campaign_sha256'][:16]}` |",
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
    lines += ["", "## Best candidate summary", "", read_summary(best["id"], 4000) if best else "_none_", ""]
    (L.ROOT / REPORT_FILE).write_text("\n".join(lines))


def finish(cfg: dict, pop: dict, poll_sec: float) -> None:
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

def free_slots(cfg: dict, pop: dict) -> list[int | None]:
    busy = [c["gpu"] for c in pop["candidates"].values() if c["status"] in ("queued", "running")]
    n_running = len(busy)
    if n_running >= cfg["resources"]["max_parallel_jobs"]:
        return []
    if cfg["resources"]["gpus"]:
        return [g for g in cfg["resources"]["gpus"] if g not in busy][: cfg["resources"]["max_parallel_jobs"] - n_running]
    return [None] * (cfg["resources"]["max_parallel_jobs"] - n_running)


def tick(cfg: dict, pop: dict) -> None:
    pop["tick"] += 1
    rng = random.Random(f"{pop['campaign']}:{pop['seed']}:{pop['tick']}")
    reap(cfg, pop)
    if pop["status"] == "running":
        reason = stop_reason(cfg, pop)
        if reason:
            pop["status"], pop["stop_reason"] = "stopping", reason
            L.emit("note", f"campaign {pop['campaign']} stopping: {reason}",
                   {"campaign": pop["campaign"], "reason": reason})
    if pop["status"] == "running":
        for gpu in free_slots(cfg, pop):
            job = choose_job(cfg, pop, rng)
            if job is None:
                break
            op, parents = job
            cid = new_candidate(cfg, pop, op, parents, gpu, rng)
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
                      "best": pop["best"]}))


def cmd_campaign_status(args) -> None:
    pop = load_pop()
    if pop is None:
        L.die(f"no {POP_FILE}: no campaign has started here")
    rows = [(k, v["operator"], ",".join(v["parents"]) or "-", v["exec"] or v["status"],
             "-" if v["fitness"] is None else f"{v['fitness']:.6g}") for k, v in pop["candidates"].items()]
    print(f"campaign {pop['campaign']}  status {pop['status']}  tick {pop['tick']}  "
          f"settled {pop['settled']}  best {pop['best']}  claim {pop['claim']}  "
          f"gpu-h {pop['gpu_seconds']/3600:.2f}")
    for r in rows:
        print("  " + "  ".join(f"{x:<12}" if i < 4 else x for i, x in enumerate(r)))


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
    out = [f"# Job {card['candidate']} — operator `{card['operator']}`", "",
           card["instructions"], "",
           "## Task", "", task.strip(), "",
           "## Contract", "",
           f"- You may write only inside `{card['contract']['may_write']}`.",
           f"- You may read: {', '.join('`' + p + '`' for p in card['contract']['may_read'])}.",
           f"- Write `{card['contract']['write']}`.",
           f"- Run `{card['contract']['run']}`; `{card['contract']['predictions']}` must exist when you exit.",
           f"- Seed everything with {card['seed']}.",
           f"- Turn budget: {card['contract']['max_turns']}. If you cannot finish, write summary.md "
           "saying what you learned and exit; the job is re-dispatched once with your summary.",
           ""]
    if card["parents"]:
        out += ["## Parents", ""]
        for p in card["parents"]:
            out += [f"### {p['id']} — fitness {p['fitness']} — exec {p['exec']}"
                    + (f" — {p['fail_reason']}" if p.get("fail_reason") else ""),
                    f"code: `{p['path']}/code`", "", p["summary"] or "_no summary_", ""]
    if card["lineage"]:
        out += ["## Lineage (newest first)", ""]
        for a in card["lineage"]:
            out += [f"- **{a['id']}** ({a['operator']}, fitness {a['fitness']}): {a['summary'] or '_no summary_'}"]
        out += [""]
    out += ["## Population", "", "| id | operator | status | fitness |", "|---|---|---|---|"]
    out += [f"| {p['id']} | {p['operator']} | {p['status']} | {p['fitness']} |" for p in card["population"]]
    out += ["", f"Best so far: {card['best']}", ""]
    print("\n".join(out))


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

def register(sub, lab_module) -> None:
    global L
    L = lab_module

    sp = sub.add_parser("campaign", help="the search loop's campaign: check | status | stop")
    s2 = sp.add_subparsers(dest="campaign_cmd", required=True)
    q = s2.add_parser("check", help="validate a campaign.toml")
    q.add_argument("file", nargs="?", default="campaign.toml")
    q.set_defaults(func=cmd_campaign_check)
    q = s2.add_parser("status", help="population at a glance")
    q.set_defaults(func=cmd_campaign_status)
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
