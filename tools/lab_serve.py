"""lab serve — a read-only page for a campaign, for a phone on the LAN.

Standard library only. Every request re-reads population.json, events.jsonl, the
candidate dirs and REPORT.md, so the page is correct by construction and cannot
drift from the files. It writes nothing, accepts only GET, escapes everything it
shows, runs displayed text through the feed's redaction, and never touches labels
or LAB_PRIVATE. Stopping a campaign stays a deliberate command (`lab campaign stop`);
there is no button for it here.

    lab serve [--bind 0.0.0.0] [--port 8791]

Routes:  /                 the campaign: header, usage, population, timeline
         /candidate/cNNNN  one candidate: provenance, session, summary.md, fitness
         /report           REPORT.md, once written
         /api/state.json   population.json plus the governor's view, as JSON
         /api/events.jsonl the last 200 events
"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import lab_campaign as C

L: Any = None
CAND_RE = re.compile(r"^c\d{4}$")

CSS = """
:root{color-scheme:light dark;--fg:#1a1a1a;--bg:#fafaf8;--mute:#666;--faint:#aaa;--line:#ddd;--acc:#1f5fbf}
@media(prefers-color-scheme:dark){:root{--fg:#e8e6e1;--bg:#111;--mute:#a9a7a2;--faint:#666;--line:#333;--acc:#7fb0ff}}
*{box-sizing:border-box}body{margin:0;padding:16px;font:14px/1.45 system-ui,sans-serif;color:var(--fg);background:var(--bg)}
main{max-width:64rem;margin:0 auto}h1{font-size:1.25rem;margin:0 0 4px}h2{font-size:1rem;margin:28px 0 8px;color:var(--mute)}
.meta{color:var(--mute)}.badge{display:inline-block;padding:1px 8px;border:1px solid var(--line);border-radius:4px;color:var(--fg)}
.kv{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin-top:10px}.kv div:nth-child(odd){color:var(--mute)}
.wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px 6px 0;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;vertical-align:top}
th{color:var(--mute);font-weight:normal}.num{text-align:right}tr.best td{font-weight:600}
td.msg,td.wrapok{white-space:normal}a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
pre{white-space:pre-wrap;word-break:break-word;font:12.5px/1.45 ui-monospace,monospace;padding:12px;border:1px solid var(--line);border-radius:4px;overflow-x:auto}
.foot{margin-top:28px;color:var(--faint);font-size:12px}.warn{color:#b3261e}
"""


def esc(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def shown(text: str) -> str:
    """Redacted (the feed's rules) then escaped."""
    return esc(L.redact(text))


def fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{digits}g}"
    except (TypeError, ValueError):
        return esc(v)


def age(iso: str | None) -> str:
    t = C._iso_epoch(iso)
    if t is None:
        return "—"
    s = int(time.time() - t)
    if s < 90:
        return f"{s}s ago"
    if s < 5400:
        return f"{s // 60}m ago"
    if s < 172800:
        return f"{s // 3600}h {(s % 3600) // 60:02d}m ago"
    return f"{s // 86400}d ago"


def page(title: str, body: str, refresh: int | None = 30) -> bytes:
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f'<meta name=viewport content="width=device-width,initial-scale=1">{meta}'
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body><main>{body}"
            f"<p class=foot>read-only · re-read from the files on every request · "
            f"{esc(L.now_iso())}</p></main></body></html>").encode()


def load() -> tuple[dict | None, dict | None, dict | None]:
    pop = C.load_pop()
    if pop is None:
        return None, None, None
    pop.setdefault("usage", C.usage_defaults())
    cfg = C._campaign_cfg(pop)
    st = C.usage_state(cfg, pop) if cfg else None
    return pop, cfg, st


def events(n: int = 50) -> list[dict]:
    p = L.EVENTS_PATH
    if not p.exists():
        return []
    out = []
    try:
        lines = p.read_text(errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-n:]:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") != "metric":
            out.append(e)
    return out


def watchers() -> list[dict]:
    """Live watch entries, read without repair (the page never writes)."""
    return [e for e in L._watch_entries() if e.get("status") == "running"]


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------

def view_index() -> bytes:
    pop, cfg, st = load()
    if pop is None:
        body = ("<h1>lab</h1><p class=meta>No campaign has run here yet. "
                "<code>lab run campaign.toml</code> starts one.</p>")
        return page("lab", body)
    cands = list(pop["candidates"].values())
    best = pop["candidates"].get(pop["best"]) if pop.get("best") else None
    fin = pop.get("final") or {}
    wall = C._duration_sec(pop["started"], pop.get("finished") or L.now_iso()) / 3600
    u = pop["usage"]
    status = pop["status"]
    badge = {"running": "Searching", "waiting_usage": "Waiting for the usage window",
             "stopping": "Finishing", "finished": "Finished"}.get(status, status)
    live = watchers()

    rows = []
    for c in reversed(cands):
        s = c.get("session") or {}
        state = "frozen" if c["status"] == "frozen" else (c.get("exec") or c["status"])
        note = c.get("fail_reason") or ""
        rows.append(
            f'<tr class="{"best" if c["id"] == pop.get("best") else ""}">'
            f'<td><a href="/candidate/{esc(c["id"])}">{esc(c["id"])}</a></td>'
            f'<td>{esc(c["operator"])}</td><td>{esc(", ".join(c.get("parents") or []))}</td>'
            f'<td>{esc(state)}</td><td class=num>{fmt(c.get("fitness"))}</td>'
            f'<td class=num>{esc(s.get("turns") or "—")}</td>'
            f'<td class=num>{fmt(s.get("cost_usd"), 3) if s.get("cost_usd") is not None else "—"}</td>'
            f'<td>{esc(age(c.get("ended") or c.get("launched")))}</td>'
            f'<td class=wrapok>{shown(note[:120])}</td></tr>')

    ev_rows = []
    for e in reversed(events(50)):
        ev_rows.append(f'<tr><td>{esc(e.get("ts", "")[5:16].replace("T", " "))}</td>'
                       f'<td>{esc(e.get("type"))}</td><td class=msg>{esc(e.get("msg"))}</td></tr>')

    usage_line = C._usage_line(cfg, pop, st) if cfg and st else "—"
    stop = cfg["stop"] if cfg and "stop" in cfg else {}
    body = f"""
<h1>{esc(pop["campaign"])} <span class=badge>{esc(badge)}</span></h1>
<p class=meta>{esc(pop["settled"])} settled of {len(cands)} candidates
{" · best " + esc(best["id"]) + " at " + fmt(best.get("fitness")) if best else ""}
 · claim {esc(pop.get("claim"))}{" · final " + fmt(fin.get("score")) if fin.get("score") is not None else ""}
 · {wall:.2f} h wall · {pop.get("gpu_seconds", 0) / 3600:.2f} GPU-h
{" · <a href=/report>REPORT.md</a>" if (L.ROOT / C.REPORT_FILE).exists() else ""}</p>
<div class=kv>
<div>stop</div><div>{esc(pop.get("stop_reason") or ("max " + esc(stop.get("max_candidates")) + " candidates · no improvement for " + esc(stop.get("no_improvement_for")) + " · " + esc((stop.get("wall_clock_sec") or 0) // 3600) + " h" if stop else "—"))}</div>
<div>usage</div><div>{esc(usage_line)}</div>
<div>waiting</div><div>{esc(u.get("waiting_reason") or "—")}{" · next eligible " + esc(u.get("next_eligible")) if u.get("next_eligible") else ""}</div>
<div>live</div><div>{", ".join(esc(w["name"]) + " (" + esc(age(w.get("heartbeat"))) + ")" for w in live) or "no watcher running" + (" — the loop is not running" if status in ("running", "waiting_usage") else "")}</div>
<div>updated</div><div>{esc(age(pop.get("updated_at")))} ({esc(pop.get("updated_at"))})</div>
</div>
<h2>Population (newest first)</h2>
<div class=wrap><table><thead><tr><th>id</th><th>operator</th><th>parents</th><th>state</th>
<th class=num>search fitness</th><th class=num>turns</th><th class=num>list $</th><th>ended</th><th>note</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<h2>Timeline (last 50, newest first)</h2>
<div class=wrap><table><thead><tr><th>UTC</th><th>type</th><th>msg</th></tr></thead><tbody>{"".join(ev_rows)}</tbody></table></div>
"""
    return page(f"{pop['campaign']} · {badge}", body)


def view_candidate(cid: str) -> bytes | None:
    pop, cfg, st = load()
    if pop is None or cid not in pop["candidates"]:
        return None
    c = pop["candidates"][cid]
    cdir = C.cand_dir(cid)
    try:
        conf = json.loads((cdir / "config.json").read_text())
    except (OSError, json.JSONDecodeError):
        conf = {}
    try:
        summary = (cdir / "summary.md").read_text(errors="replace")
    except OSError:
        summary = "(no summary.md yet)"
    try:
        fitness = (cdir / "fitness.json").read_text()
    except OSError:
        fitness = "(no fitness.json)"
    s = c.get("session") or {}
    agent = conf.get("agent") or {}
    body = f"""
<p class=meta><a href="/">← {esc(pop["campaign"])}</a></p>
<h1>{esc(cid)} <span class=badge>{esc(c.get("exec") or c["status"])}</span></h1>
<div class=kv>
<div>operator</div><div>{esc(c["operator"])}{" from " + esc(", ".join(c["parents"])) if c.get("parents") else ""}{" · re-dispatch of " + esc(c["redispatch_of"]) if c.get("redispatch_of") else ""}</div>
<div>search fitness</div><div>{fmt(c.get("fitness"))}{" (n=" + esc(c.get("n")) + ")" if c.get("n") else ""}{" · best so far" if pop.get("best") == cid else ""}</div>
<div>status</div><div>{esc(c["status"])}{" · " + shown(c["fail_reason"]) if c.get("fail_reason") else ""}</div>
<div>timing</div><div>launched {esc(c.get("launched") or "—")} · ended {esc(c.get("ended") or "—")} · gpu {esc(c.get("gpu") if c.get("gpu") is not None else "cpu")} · exit {esc(c.get("exit_code"))}</div>
<div>session</div><div>{esc(s.get("id") or "—")} · {esc(s.get("turns") or "—")} turns · list ${fmt(s.get("cost_usd"), 3) if s.get("cost_usd") is not None else "—"} · {esc(", ".join(s.get("models") or []) or "—")}{" · <b class=warn>rate limited</b>" if s.get("rate_limited") else ""}</div>
<div>provenance</div><div>seed {esc(conf.get("seed"))} · commit {esc(conf.get("git_commit"))}{" (dirty)" if conf.get("git_dirty") else ""} · requested {esc(agent.get("requested") or "—")} · served {esc(", ".join(agent.get("served") or []) or "—")}</div>
</div>
<h2>summary.md</h2><pre>{shown(summary)}</pre>
<h2>fitness.json</h2><pre>{shown(fitness)}</pre>
"""
    return page(f"{cid} · {pop['campaign']}", body, refresh=None)


def view_report() -> bytes | None:
    p = L.ROOT / C.REPORT_FILE
    if not p.exists():
        return None
    try:
        text = p.read_text(errors="replace")
    except OSError:
        return None
    body = f'<p class=meta><a href="/">← back</a></p><h1>REPORT.md</h1><pre>{shown(text)}</pre>'
    return page("REPORT.md", body, refresh=None)


def api_state() -> bytes:
    pop, cfg, st = load()
    return json.dumps({"population": L.redact(pop), "usage_state": st,
                       "watchers": watchers(), "now": L.now_iso()}, default=str).encode()


# ---------------------------------------------------------------------------
# server
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "lab-serve"

    def log_message(self, fmt_: str, *args: Any) -> None:   # quiet
        pass

    def _send(self, body: bytes, ctype: str = "text/html; charset=utf-8", code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:   # noqa: N802
        path = urlparse(self.path).path
        try:
            if path in ("", "/"):
                self._send(view_index())
            elif path.startswith("/candidate/"):
                cid = path[len("/candidate/"):]
                out = view_candidate(cid) if CAND_RE.match(cid) else None
                if out is None:
                    self._send(page("not found", "<h1>no such candidate</h1>", None), code=404)
                else:
                    self._send(out)
            elif path == "/report":
                out = view_report()
                if out is None:
                    self._send(page("no report", "<h1>no REPORT.md yet</h1><p class=meta>"
                                    "written once when the campaign finishes</p>", None), code=404)
                else:
                    self._send(out)
            elif path == "/api/state.json":
                self._send(api_state(), "application/json")
            elif path == "/api/events.jsonl":
                body = "\n".join(json.dumps(e) for e in events(200)) + "\n"
                self._send(body.encode(), "application/x-ndjson")
            else:
                self._send(page("not found", "<h1>not found</h1>", None), code=404)
        except Exception as e:   # a broken file must not take the page down
            self._send(page("error", f"<h1>error</h1><pre>{esc(e)}</pre>", 30), code=500)

    def do_POST(self) -> None:   # noqa: N802
        self._send(b"read-only", "text/plain", 405)


def cmd_serve(args) -> None:
    srv = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"lab serve: read-only view of {L.ROOT} on http://{args.bind}:{args.port}/ "
          f"(Ctrl-C to stop)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


def register(sub, lab_module) -> None:
    global L
    L = lab_module
    sp = sub.add_parser("serve", help="read-only web page for this campaign (LAN, phone)")
    sp.add_argument("--bind", default="0.0.0.0", help="address to listen on (default all interfaces)")
    sp.add_argument("--port", type=int, default=8791)
    sp.set_defaults(func=cmd_serve)
