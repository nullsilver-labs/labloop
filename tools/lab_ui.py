"""lab ui — the campaign in a browser: a read-only web view of this campaign dir.

`lab run` serves it by default for as long as the campaign runs (`--no-ui` to leave it out);
`lab ui` serves it on its own, for a finished campaign or one run from another shell.

    lab ui [--host H] [--port P]           serve until ^C; prints the url
    lab run [--no-ui] [--ui-host H] [--ui-port P]

The host defaults to $LAB_UI_HOST, else 127.0.0.1; the port to the first free one from 5390.
The url is written to .lab/ui.json. Standard library only.

It reads what `lab campaign status` reads, plus each candidate's summary, finding card,
records and code, and the campaign's own markdown. It never reads labels (they are not in
this dir) and writes nothing but .lab/ui.json. A file is served only from inside a
candidate dir or from a short list of the campaign's documents, never through a symlink
that leaves them.

Ask: a question about the campaign goes to the local model (`nullsilver-slm ask`, found
on $NULLSILVER_SLM, PATH or /mnt/data/projects/nullsilver/slm/bin), which has read-only
tools confined to this dir. One question at a time.
"""
from __future__ import annotations

import difflib
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import lab_campaign as C
import lab_status as S

L: Any = None

UI_DIR = Path(__file__).resolve().parent / "ui"
DEFAULT_PORT = 5390
PORT_TRIES = 20
FILE_MAX = 512 * 1024
LIST_MAX = 600
DOCS = ["REPORT.md", "READ.md", "task.md", "LEDGER.md", "RESUME.md", "PREREG.md", "CLAUDE.md",
        "campaign.toml", "README.md", "NEXT.md"]
CID_RE = re.compile(r"^c\d{4,}$")
SLM_FALLBACK = Path("/mnt/data/projects/nullsilver/slm/bin/nullsilver-slm")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json",
         ".woff2": "font/woff2", ".svg": "image/svg+xml", ".txt": "text/plain; charset=utf-8"}


# ---------------------------------------------------------------------------
# what the page shows, gathered per request
# ---------------------------------------------------------------------------

_titles: dict[str, tuple[float, str | None]] = {}


def title_of(cid: str) -> str | None:
    """One line for a candidate: what it changed, from its summary. A baseline's summary
    names itself in its heading; a worker's opens with `Change:` under `## Finding`."""
    p = C.cand_dir(cid) / "summary.md"
    try:
        mt = p.stat().st_mtime
    except OSError:
        return None
    hit = _titles.get(cid)
    if hit and hit[0] == mt:
        return hit[1]
    title = None
    try:
        text = p.read_text(errors="replace")
    except OSError:
        text = ""
    m = re.search(r"^\s*(?:[-*]\s*)?\**Change\**:\s*(.+)$", text, re.M)
    if m:
        title = m.group(1)
    else:
        for line in text.splitlines():
            s = line.strip()
            h = re.match(r"#+\s*(?:c\d{4,}\s*[:—-]\s*)?(.+)", s)
            if h and not s.startswith("##"):
                title = h.group(1)
                break
            if s and not s.startswith(("#", "|", "```", "-")):
                title = s
                break
    if title:
        title = re.sub(r"[*_`]", "", title).strip()
        title = title[:1].upper() + title[1:]
        cut = re.search(r"(?<=[a-z0-9)\]])[.;](\s|$)", title)
        if cut and cut.start() > 40:
            title = title[:cut.start()]
        if len(title) > 220:
            title = title[:217].rsplit(" ", 1)[0] + "…"
    _titles[cid] = (mt, title)
    return title


def _toml() -> dict:
    try:
        return tomllib.loads((L.ROOT / "campaign.toml").read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def campaign_brief(raw: dict) -> dict:
    """The settings worth showing, from campaign.toml as written."""
    g = lambda *ks: _dig(raw, *ks)
    return {
        "id": g("campaign", "id"), "kind": g("campaign", "kind"),
        "threshold": g("report", "success_threshold"),
        "higher_is_better": g("report", "higher_is_better") is not False,
        "max_candidates": g("stop", "max_candidates"), "wall_clock": g("stop", "wall_clock"),
        "gpus": g("resources", "gpus"), "slots": g("resources", "max_parallel_jobs"),
        "gpu_hours_total": g("resources", "gpu_hours_total"),
        "job_wall_clock": g("resources", "job_wall_clock"),
        "worker_model": g("resources", "worker_model"),
        "models_by_operator": g("resources", "worker_model_by_operator") or {},
        "selection": g("selection") or {}, "memory": g("memory", "mode"),
        "usage": g("usage") or {}, "eval_user": g("eval", "user"),
    }


def _dig(d: Any, *ks: str) -> Any:
    for k in ks:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def read_all_events(limit: int = 600) -> list[dict]:
    """The feed without metric events (chart data the page does not use), newest last."""
    out: list[dict] = []
    try:
        with open(L.EVENTS_PATH, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("type") != "metric":
                    out.append({k: e.get(k) for k in ("ts", "type", "candidate", "msg", "data")})
    except OSError:
        pass
    return out[-limit:]


def state(probe: S.Probe) -> dict:
    try:
        snap = S.snapshot(probe)
    except SystemExit:
        return {"empty": True, "root": str(L.ROOT), "campaign": campaign_brief(_toml()),
                "docs": [d for d in DOCS if (L.ROOT / d).exists()], "now": time.time()}
    pop = snap["pop"]
    cands = pop["candidates"]
    rows = []
    for r in snap["rows"]:
        c = cands.get(r["id"], {})
        r = dict(r)
        r.update({"launched": c.get("launched"), "ended": c.get("ended"),
                  "components": c.get("components"), "debugged": c.get("debugged"),
                  "defers": c.get("defers"), "title": title_of(r["id"])})
        rows.append(r)
    brief = campaign_brief(_toml())
    final = pop.get("final") or None
    if final:
        final = {k: final.get(k) for k in ("candidate", "score", "started", "ended")}
    head = {k: pop.get(k) for k in ("campaign", "status", "started", "finished", "tick", "best",
                                    "settled", "settled_at_best", "gpu_seconds", "stop_reason",
                                    "claim", "updated_at", "seed")}
    u = pop.get("usage") or {}
    return {
        "root": str(L.ROOT), "now": snap["now"], "pop": head, "final": final,
        "campaign": brief, "rows": rows, "gpus": snap["gpus"], "events": read_all_events(),
        "usage": {"state": snap["usage"], **{k: u.get(k) for k in (
            "waiting_seconds", "waiting_since", "waiting_reason", "next_eligible", "pauses",
            "rate_limits", "deferred", "peak_fraction", "blocked_until", "blocked_reason")}},
        "campaign_watch": bool(snap["campaign_watch"]), "stop_requested": snap["stop_requested"],
        "wrote_age": snap["wrote_age"], "median_lease": snap["median_lease"], "eta": snap["eta"],
        "train_seconds_total": snap["train_seconds_total"],
        "docs": [d for d in DOCS if (L.ROOT / d).exists()],
    }


def _json_file(p: Path) -> Any:
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _text(p: Path, limit: int = FILE_MAX) -> str | None:
    try:
        with open(p, "rb") as f:
            b = f.read(limit + 1)
    except OSError:
        return None
    return b[:limit].decode("utf-8", "replace") + ("\n… (cut at 512 KB)" if len(b) > limit else "")


def candidate(cid: str) -> dict | None:
    if not CID_RE.match(cid):
        return None
    d = C.cand_dir(cid)
    if not d.is_dir():
        return None
    pop = C.load_pop() or {"candidates": {}}
    rec = pop["candidates"].get(cid, {})
    files, base = [], d.resolve()
    for p in sorted(d.rglob("*")):
        if len(files) >= LIST_MAX:
            break
        try:
            if p.is_symlink() or not p.is_file():
                continue
            files.append({"path": str(p.relative_to(d)), "size": p.stat().st_size})
        except OSError:
            continue
    children = sorted(k for k, c in pop["candidates"].items() if cid in (c.get("parents") or []))
    cfg = _json_file(d / "config.json")
    return {
        "id": cid, "record": rec, "title": title_of(cid), "children": children,
        "summary": _text(d / "summary.md"), "fitness": _json_file(d / "fitness.json"),
        "finding": _json_file(d / "finding.json"), "config": cfg,
        "job": _json_file(d / "job.json"), "train_stats": _json_file(d / "out" / "train_stats.json"),
        "files": files, "base": str(base),
    }


DIFF_MAX = 400 * 1024


def _code_files(cid: str) -> dict[str, Path]:
    """A candidate's code/, by path inside it: real files only, no caches, no links out."""
    base = (C.cand_dir(cid) / "code").resolve()
    out: dict[str, Path] = {}
    if not base.is_dir():
        return out
    for p in sorted(base.rglob("*")):
        if len(out) >= LIST_MAX:
            break
        try:
            if p.is_symlink() or not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
                continue
            out[str(p.relative_to(base))] = p
        except OSError:
            continue
    return out


def code_diff(cid: str, other: str) -> dict | None:
    """The candidate's code/ against another candidate's, file by file, as unified diffs.
    Unchanged files are counted, binaries are named, the whole is cut at DIFF_MAX."""
    if not (CID_RE.match(cid) and CID_RE.match(other)) or not C.cand_dir(cid).is_dir() or not C.cand_dir(other).is_dir():
        return None
    a, b = _code_files(other), _code_files(cid)
    files, same, budget = [], 0, DIFF_MAX
    for rel in sorted(set(a) | set(b)):
        try:
            ba = a[rel].read_bytes()[:FILE_MAX] if rel in a else b""
            bb = b[rel].read_bytes()[:FILE_MAX] if rel in b else b""
        except OSError:
            continue
        if ba == bb:
            same += 1
            continue
        status = "added" if rel not in a else "removed" if rel not in b else "changed"
        if b"\x00" in ba[:8192] or b"\x00" in bb[:8192]:
            files.append({"path": rel, "status": status, "binary": True})
            continue
        lines = list(difflib.unified_diff(ba.decode("utf-8", "replace").splitlines(), bb.decode("utf-8", "replace").splitlines(),
                                          n=3, lineterm=""))[2:]
        text = "\n".join(lines)
        if budget <= 0:
            text = ""
        elif len(text) > budget:
            text = text[:budget] + "\n… (cut)"
        budget -= len(text)
        files.append({"path": rel, "status": status, "diff": text,
                      "adds": sum(1 for x in lines if x.startswith("+")),
                      "dels": sum(1 for x in lines if x.startswith("-"))})
    return {"id": cid, "against": other, "files": files, "same": same}


def safe_file(cid: str, rel: str) -> Path | None:
    """A file inside the candidate's dir, after resolving every link; None otherwise."""
    if not CID_RE.match(cid) or not rel or "\x00" in rel:
        return None
    base = C.cand_dir(cid).resolve()
    try:
        p = (base / rel).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if base not in p.parents or not p.is_file():
        return None
    return p


# ---------------------------------------------------------------------------
# ask: the local model, read-only, confined to this dir
# ---------------------------------------------------------------------------

_ask_lock = threading.Lock()
_slm_status: dict = {"at": 0.0, "value": None}


def slm_bin() -> str | None:
    env = os.environ.get("NULLSILVER_SLM")
    if env:
        return env
    found = shutil.which("nullsilver-slm")
    if found:
        return found
    return str(SLM_FALLBACK) if SLM_FALLBACK.exists() else None


def slm_status() -> dict:
    now = time.time()
    if now - _slm_status["at"] < 15 and _slm_status["value"] is not None:
        return _slm_status["value"]
    b = slm_bin()
    v: dict = {"up": False, "installed": bool(b)}
    if b:
        try:
            cp = subprocess.run([b, "status", "--json"], capture_output=True, text=True, timeout=8)
            line = (cp.stdout.strip().splitlines() or ["{}"])[-1]
            v.update(json.loads(line))
        except (OSError, subprocess.TimeoutExpired, ValueError) as e:
            v["error"] = str(e)
    v["busy"] = _ask_lock.locked()
    _slm_status.update(at=now, value=v)
    return v


def ask_context(st: dict) -> str:
    """A short briefing the model reads before the files, so a small model starts oriented."""
    c, p = st.get("campaign") or {}, st.get("pop") or {}
    rows = [r for r in st.get("rows", []) if r.get("fitness") is not None]
    hib = c.get("higher_is_better", True)
    rows.sort(key=lambda r: r["fitness"], reverse=hib)
    lines = [
        f"You are answering questions about the labloop campaign `{c.get('id')}` in {st.get('root')}.",
        f"Status: {p.get('status')}; {p.get('settled')} candidates settled of {c.get('max_candidates')} allowed; "
        f"best on the search split {p.get('best')}; claim {p.get('claim') or 'not read yet'}; "
        f"success threshold {c.get('threshold')} ({'higher' if hib else 'lower'} is better), "
        "read only on the final split.",
    ]
    if st.get("final"):
        f = st["final"]
        lines.append(f"Final split: {f.get('candidate')} scored {f.get('score')}.")
    lines.append("Top candidates by search fitness (id, operator, parents, fitness, what it changed):")
    for r in rows[:8]:
        lines.append(f"- {r['id']} {r['operator']} parents={','.join(r['parents']) or '-'} "
                     f"fitness={r['fitness']}: {r.get('title') or ''}")
    bad = [r for r in st.get("rows", []) if r.get("exec") in ("failed", "killed", "invalid")]
    if bad:
        lines.append("Failed, killed or invalid: " + "; ".join(
            f"{r['id']} {r['exec']} ({r.get('fail_reason') or 'no reason recorded'})" for r in bad[:12]))
    lines.append("Files: campaign.toml, task.md, REPORT.md, LEDGER.md, events.jsonl, population.json, "
                 "candidates/cNNNN/{summary.md,fitness.json,config.json,finding.json,code/}. "
                 "Cite the files you read. You cannot change anything.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# the server
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "labloop-ui"
    probe: S.Probe

    def log_message(self, fmt, *args):  # quiet: a campaign's log is not an access log
        pass

    def _send(self, code: int, body: bytes, ctype: str, cache: str = "no-store") -> None:
        if len(body) > 2048 and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            body = gzip.compress(body, 5)
            self.send_response(code)
            self.send_header("Content-Encoding", "gzip")
        else:
            self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj, default=str).encode(), "application/json")

    def _err(self, code: int, msg: str) -> None:
        self._json({"error": msg}, code)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        path, q = unquote(u.path), parse_qs(u.query)
        try:
            if path == "/api/state":
                return self._json(state(self.probe))
            if path.startswith("/api/candidate/"):
                parts = path.split("/")[3:]
                cid = parts[0] if parts else ""
                if len(parts) == 1:
                    c = candidate(cid)
                    return self._json(c) if c else self._err(404, f"no candidate {cid}")
                if len(parts) == 2 and parts[1] == "file":
                    p = safe_file(cid, (q.get("path") or [""])[0])
                    if not p:
                        return self._err(404, "no such file in that candidate")
                    with open(p, "rb") as f:
                        head = f.read(8192)
                    if b"\x00" in head:
                        return self._json({"binary": True, "size": p.stat().st_size})
                    return self._json({"text": _text(p), "size": p.stat().st_size})
                if len(parts) == 2 and parts[1] == "diff":
                    d = code_diff(cid, (q.get("against") or [""])[0])
                    return self._json(d) if d else self._err(404, "no such pair of candidates")
                return self._err(404, "not found")
            if path.startswith("/api/doc/"):
                name = path[len("/api/doc/"):]
                if name not in DOCS:
                    return self._err(404, "not a campaign document")
                t = _text(L.ROOT / name)
                return self._json({"name": name, "text": t}) if t is not None else self._err(404, "missing")
            if path == "/api/ask/status":
                return self._json(slm_status())
            return self._static(path)
        except Exception as e:  # a view must never take the campaign down with it
            return self._err(500, f"{type(e).__name__}: {e}")

    def _static(self, path: str) -> None:
        if path in ("", "/"):
            path = "/index.html"
        p = (UI_DIR / path.lstrip("/")).resolve()
        if UI_DIR.resolve() not in p.parents or not p.is_file():
            p = UI_DIR / "index.html"  # the page routes by its hash; anything else is the page
        cache = "public, max-age=86400" if p.suffix == ".woff2" else "no-cache"
        self._send(200, p.read_bytes(), TYPES.get(p.suffix, "application/octet-stream"), cache)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/ask":
            return self._err(404, "not found")
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 65536)) or b"{}")
        except (ValueError, OSError):
            return self._err(400, "a JSON body with a question")
        question = str(body.get("question") or "").strip()[:2000]
        if not question:
            return self._err(400, "an empty question")
        b = slm_bin()
        if not b:
            return self._err(503, "nullsilver-slm is not installed on this machine")
        if not _ask_lock.acquire(blocking=False):
            return self._err(429, "the model is answering another question")
        try:
            self._ask(b, question, body.get("history") or [])
        finally:
            _ask_lock.release()

    def _ask(self, b: str, question: str, history: list) -> None:
        ctx = ask_context(state(self.probe))
        if history:
            ctx += "\n\nEarlier in this conversation:\n" + "\n".join(
                f"{'Q' if h.get('role') == 'user' else 'A'}: {str(h.get('text'))[:1500]}"
                for h in history[-6:] if isinstance(h, dict))
        with tempfile.NamedTemporaryFile("w", suffix=".md", prefix="lab-ui-ask-", delete=False) as f:
            f.write(ctx)
            ctx_path = f.name
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        proc = None
        try:
            proc = subprocess.Popen([b, "ask", "--dir", str(L.ROOT), "--context-file", ctx_path, question],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                    start_new_session=True)
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                except ValueError:
                    line = json.dumps({"type": "text", "delta": line + "\n"})
                self.wfile.write(f"data: {line}\n\n".encode())
                self.wfile.flush()
            rc = proc.wait(timeout=30)
            if rc != 0:
                self.wfile.write(f"data: {json.dumps({'type': 'error', 'message': f'nullsilver-slm exited {rc}'})}\n\n".encode())
            self.wfile.write(b"data: {\"type\":\"end\"}\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if proc and proc.poll() is None:
                try:
                    os.killpg(proc.pid, 15)
                except OSError:
                    pass
            os.unlink(ctx_path)


def serve(host: str | None, port: int | None) -> tuple[ThreadingHTTPServer, str]:
    """Bind the first free port from `port` (or 5390); return the server and its url."""
    host = host or os.environ.get("LAB_UI_HOST") or "127.0.0.1"
    Handler.probe = S.Probe()
    start = port or int(os.environ.get("LAB_UI_PORT") or DEFAULT_PORT)
    last: OSError | None = None
    for p in range(start, start + (1 if port else PORT_TRIES)):
        try:
            srv = ThreadingHTTPServer((host, p), Handler)
            break
        except OSError as e:
            last = e
    else:
        raise OSError(f"no free port from {start} on {host}: {last}")
    srv.daemon_threads = True
    url = f"http://{host}:{srv.server_address[1]}"
    try:
        L.LAB_DIR.mkdir(parents=True, exist_ok=True)
        (L.LAB_DIR / "ui.json").write_text(json.dumps(
            {"url": url, "pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
    except OSError:
        pass
    return srv, url


def start_background(host: str | None, port: int | None) -> str | None:
    """For `lab run`: serve from a daemon thread, so the view ends with the campaign. A
    view that cannot start is a warning, never a reason for the campaign not to run."""
    try:
        srv, url = serve(host, port)
    except Exception as e:
        L.warn(f"lab ui did not start ({e}); the campaign runs without it")
        return None
    threading.Thread(target=srv.serve_forever, name="lab-ui", daemon=True).start()
    print(f"lab ui: {url}", file=sys.stderr, flush=True)
    return url


def cmd_ui(args) -> None:
    srv, url = serve(args.host, args.port)
    print(f"lab ui: {url}  (^C to stop)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def register(sub, lab_module) -> None:
    global L
    L = lab_module
    S.L = lab_module
    q = sub.add_parser("ui", help="the campaign in a browser: a read-only web view of this dir")
    q.add_argument("--host", help="address to bind ($LAB_UI_HOST, else 127.0.0.1)")
    q.add_argument("--port", type=int, help=f"port (first free from {DEFAULT_PORT})")
    q.set_defaults(func=cmd_ui)
