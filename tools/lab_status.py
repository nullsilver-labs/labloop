"""lab campaign status — the campaign at a glance, live in the terminal.

Read-only, standard library only. Every frame re-reads the population file, the
watch registry, the event feed and each candidate dir, and asks nvidia-smi once; it
writes nothing and never touches labels. Styled after nullsilver.com: two colours
(the page's near-black and its silver), a ramp of that silver for hierarchy, emphasis
by inversion, no status hues, sentence case, interpuncts in meta lines.

    lab campaign status               live on a terminal; plain text when piped
    lab campaign status --once        one frame of the live layout, then exit
    lab campaign status --plain       the one-line-per-candidate text (scripts, greps)

Keys: q quit · j/k or arrows scroll the population · r refresh · +/- refresh interval.
"""
from __future__ import annotations

import json
import os
import re
import select
import shutil
import subprocess
import sys
import termios
import time
import tty
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lab_campaign as C

L: Any = None

# nullsilver.com tokens.css: the brand silver #dedad2 over #0a0a0a and its ramp.
# Roles, not values, as on the site; the 256-colour column is the nearest grey.
ROLES = {
    "strong": ("#f8f7f5", 231),
    "text":   ("#dedad2", 253),
    "muted":  ("#9c9891", 247),
    "subtle": ("#78746e", 243),
    "faint":  ("#57534e", 240),
    "line":   ("#3a3733", 237),
    "track":  ("#232120", 235),
}
INVERT = (("#0a0a0a", 232), ("#dedad2", 253))   # fg, bg: silver fill, black text

BADGES = {"running": "Searching", "waiting_usage": "Waiting for the usage window",
          "stopping": "Finishing", "finished": "Finished"}
TRAIN_KEYS = ("train_seconds", "train_sec", "train_wall_s", "train_wall_seconds", "wall_seconds")
SMI_FIELDS = "index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw"
SPARK = "▁▂▃▄▅▆▇█"

Seg = list[tuple[str, str]]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _hex_rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def color_mode(force_off: bool = False) -> str | None:
    if force_off or os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return None
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return "truecolor"
    return "256"


def sgr(role: str, mode: str | None) -> str:
    if mode is None:
        return ""
    if role == "invert":
        (fg, fg256), (bg, bg256) = INVERT
        if mode == "truecolor":
            return "\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm" % (*_hex_rgb(fg), *_hex_rgb(bg))
        return f"\x1b[38;5;{fg256}m\x1b[48;5;{bg256}m"
    h, n = ROLES[role]
    if mode == "truecolor":
        return "\x1b[38;2;%d;%d;%dm" % _hex_rgb(h)
    return f"\x1b[38;5;{n}m"


def paint(segs: Seg, width: int, mode: str | None) -> str:
    """Segments (text, role) → one line, cut at `width` visible cells."""
    out, used = [], 0
    for text, role in segs:
        if used >= width:
            break
        room = width - used
        if len(text) > room:
            text = text[: max(0, room - 1)] + "…" if room > 1 else ""
        if mode is None and role == "track":
            text = text.replace("█", "·")      # no colour: the track must still read as empty
        used += len(text)
        out.append(sgr(role, mode) + text + ("\x1b[0m" if mode else ""))
    return "".join(out)


def _epoch(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def hhmm(s: str | None) -> str:
    return s[11:16] + "Z" if s and len(s) >= 16 else "?"


def dur(sec: float | None) -> str:
    """1h 55m · 15m 31s · 48s — for meta lines."""
    if sec is None:
        return "·"
    sec = max(0, int(sec))
    if sec >= 3600:
        return f"{sec // 3600}h" + (f" {sec % 3600 // 60:02d}m" if sec % 3600 else "")
    if sec >= 60:
        return f"{sec // 60}m" + (f" {sec % 60:02d}s" if sec % 60 else "")
    return f"{sec}s"


def mmss(sec: float | None) -> str:
    """15:31 · 1:02:15 — for table cells."""
    if sec is None:
        return "·"
    sec = max(0, int(sec))
    if sec >= 3600:
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"
    return f"{sec // 60}:{sec % 60:02d}"


def short_model(m: str | None) -> str:
    if not m:
        return "·"
    return re.sub(r"-\d{8}$", "", re.sub(r"^claude-", "", m))


def bar(frac: float | None, width: int) -> Seg:
    """A track in the surface colour with a silver fill; no second hue."""
    if frac is None:
        return [("·" * width, "line")]
    n = max(0, min(width, round(max(0.0, min(1.0, frac)) * width)))
    return [("█" * n, "text"), ("█" * (width - n), "track")]


def _read_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text()) or None
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# the snapshot: everything a frame shows, gathered once per refresh
# ---------------------------------------------------------------------------

class Probe:
    """nvidia-smi once per frame, with a short utilisation history per card."""

    def __init__(self) -> None:
        self.available = shutil.which("nvidia-smi") is not None
        self.history: dict[int, list[int]] = {}

    def read(self) -> list[dict]:
        if not self.available:
            return []
        try:
            cp = subprocess.run(["nvidia-smi", f"--query-gpu={SMI_FIELDS}",
                                 "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return []
        if cp.returncode != 0:
            return []
        rows = []
        for line in cp.stdout.splitlines():
            p = [x.strip() for x in line.split(",")]
            if len(p) != 7:
                continue
            try:
                g = {"index": int(p[0]), "name": p[1], "util": int(float(p[2])),
                     "used_mb": int(float(p[3])), "total_mb": int(float(p[4])),
                     "temp": int(float(p[5])) if p[5].replace(".", "").isdigit() else None,
                     "power": float(p[6]) if p[6].replace(".", "").isdigit() else None}
            except ValueError:
                continue
            h = self.history.setdefault(g["index"], [])
            h.append(g["util"])
            del h[:-8]
            g["history"] = list(h)
            rows.append(g)
        return rows


def read_events(limit: int = 40) -> list[dict]:
    """The last events of the feed, from its tail; metric events are chart data."""
    try:
        with open(L.EVENTS_PATH, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 32768))
            chunk = f.read().decode("utf-8", "replace")
    except OSError:
        return []
    out = []
    for line in chunk.splitlines()[1 if size > 32768 else 0:]:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") != "metric":
            out.append(e)
    return out[-limit:]


def train_seconds(cdir: Path) -> float | None:
    """Training wall time when the candidate recorded one (a convention, not a
    contract: code/train_stats.json or out/memory_config.json, first known key)."""
    for rel in ("code/train_stats.json", "out/memory_config.json"):
        d = _read_json(cdir / rel)
        if d:
            for k in TRAIN_KEYS:
                v = d.get(k)
                if isinstance(v, (int, float)):
                    return float(v)
    return None


def phase(cdir: Path, sess_written: bool) -> str:
    """What a running candidate has produced so far, from the files it leaves."""
    if (cdir / "out" / "predictions-search.json").exists():
        return "predicted"
    if train_seconds(cdir) is not None:
        return "trained"
    if sess_written:
        return "session ended"
    return "in session"


def snapshot(probe: Probe) -> dict:
    now = time.time()
    pop = C.load_pop()
    if pop is None:
        L.die(f"no {C.POP_FILE}: no campaign has started here")
    pop.setdefault("usage", C.usage_defaults())
    cfg = C._campaign_cfg(pop)
    full = cfg if cfg and not cfg.get("partial") else {}
    st = C.usage_state(cfg, pop, now) if cfg else None
    watches = {e["id"]: e for e in L._watch_entries()}
    campaign_watch = next((e for e in watches.values()
                           if e.get("name") == "campaign" and e.get("status") == "running"), None)

    rows = []
    for cid, c in pop["candidates"].items():
        cdir = C.cand_dir(cid)
        launched, ended = _epoch(c.get("launched")), _epoch(c.get("ended"))
        running = c.get("status") in ("queued", "running")
        w = watches.get(c.get("watch") or "") or {}
        sess = c.get("session") or {}
        sess_written = False
        try:
            sj = cdir / "session.json"
            sess_written = sj.exists() and sj.stat().st_size > 0
        except OSError:
            pass
        models = [m for m in sess.get("models") or [] if "haiku" not in m]
        hb = _epoch(w.get("heartbeat"))
        rows.append({
            "id": cid, "operator": c.get("operator"), "parents": c.get("parents") or [],
            "gpu": c.get("gpu"), "status": c.get("status"), "exec": c.get("exec"),
            "running": running, "fitness": c.get("fitness"), "fail_reason": c.get("fail_reason"),
            "lease": ((ended or now) - launched) if launched else None,
            "train": train_seconds(cdir),
            "turns": sess.get("turns"), "cost": sess.get("cost_usd"),
            "model": short_model(models[-1] if models else None),
            "budget_sec": w.get("budget_min", 0) * 60 if w else None,
            "heartbeat_age": (now - hb) if hb else None,
            "phase": phase(cdir, sess_written) if running else None,
            "redispatch_of": c.get("redispatch_of"),
        })

    leases = sorted(r["lease"] for r in rows
                    if r["operator"] != "baseline" and not r["running"] and r["lease"] is not None)
    median_lease = leases[len(leases) // 2] if leases else None
    max_c = full.get("stop", {}).get("max_candidates")
    slots = full.get("resources", {}).get("max_parallel_jobs", 1)
    eta = None
    if max_c and median_lease and pop["status"] in ("running", "waiting_usage") and pop["settled"] < max_c:
        eta = now + (max_c - pop["settled"]) * median_lease / max(1, slots)

    return {
        "now": now, "pop": pop, "cfg": full, "usage": st, "rows": rows,
        "gpus": probe.read(), "events": read_events(),
        "campaign_watch": campaign_watch,
        "stop_requested": (L.LAB_DIR / "campaign.stop").exists(),
        "wrote_age": now - (_epoch(pop.get("updated_at")) or now),
        "median_lease": median_lease, "eta": eta, "max_candidates": max_c,
        "gpu_list": full.get("resources", {}).get("gpus"),
        "gpu_hours_total": full.get("resources", {}).get("gpu_hours_total"),
    }


# ---------------------------------------------------------------------------
# rendering: segment lines, painted to a width
# ---------------------------------------------------------------------------

SEP: tuple[str, str] = ("  ·  ", "faint")


def _meta(parts: list[Seg]) -> Seg:
    """Join meta clauses with the site's interpunct."""
    out: Seg = []
    for i, p in enumerate(parts):
        if i:
            out.append(SEP)
        out += p
    return out


def _flow(parts: list[Seg], width: int, lead: Seg | None = None) -> list[Seg]:
    """Meta clauses packed into as many lines as the width needs, never cut mid-clause.
    `lead` opens the first line; later lines are indented under it."""
    lead = lead or [(" ", "text")]
    indent = " " * sum(len(t) for t, _ in lead)
    lines: list[Seg] = []
    cur: Seg = list(lead)
    used = len(indent)
    first = True
    for p in parts:
        w = sum(len(t) for t, _ in p) + (0 if first else len(SEP[0]))
        if not first and used + w > width:
            lines.append(cur)
            cur, used, first = [(indent, "text")], len(indent), True
            w -= len(SEP[0])
        if not first:
            cur.append(SEP)
        cur += p
        used += w
        first = False
    lines.append(cur)
    return lines


def header(s: dict, width: int) -> list[Seg]:
    pop, now, st = s["pop"], s["now"], s["usage"]
    best = pop.get("best")
    best_fit = pop["candidates"].get(best, {}).get("fitness") if best else None
    settled = f"{pop['settled']} settled" + (f" of {s['max_candidates']}" if s["max_candidates"] else "")
    lead: Seg = [(f" {pop['campaign']} ", "strong"),
                 (f" {BADGES.get(pop['status'], pop['status'])} ", "invert"), ("   ", "text")]
    top: list[Seg] = [[("tick ", "subtle"), (str(pop["tick"]), "text")],
                      [(settled, "text")],
                      [("best ", "subtle"), (best or "·", "text"),
                       (f" {best_fit:.4g}" if best_fit is not None else "", "strong")],
                      [("claim ", "subtle"), (pop.get("claim") or "untested", "text")]]
    if pop.get("final") is not None:
        top.append([("final ", "subtle"), (f"{pop['final']}", "strong")])

    started, finished = _epoch(pop.get("started")), _epoch(pop.get("finished"))
    gpu_h = pop.get("gpu_seconds", 0) / 3600
    parts: list[Seg] = [[("started ", "subtle"), (hhmm(pop.get("started")), "text")],
                        [("wall ", "subtle"), (dur(((finished or now) - started) if started else None), "text")],
                        [("gpu ", "subtle"), (f"{gpu_h:.2f} h", "text"),
                         (f" of {s['gpu_hours_total']:g}" if s["gpu_hours_total"] else "", "subtle")]]
    if s["median_lease"]:
        parts.append([("median lease ", "subtle"), (dur(s["median_lease"]), "text")])
    if s["eta"]:
        parts.append([("done ≈ ", "subtle"),
                      (datetime.fromtimestamp(s["eta"], timezone.utc).strftime("%H:%MZ"), "text")])
    w = s["campaign_watch"]
    if w:
        used = now - (_epoch(w.get("started")) or now)
        hb = now - (_epoch(w.get("heartbeat")) or now)
        parts.append([("watcher ", "subtle"), (f"{dur(used)} of {dur(w.get('budget_min', 0) * 60)}", "text"),
                      (f", heartbeat {dur(hb)} ago", "subtle" if hb < 60 else "strong")])
    elif pop["status"] in ("running", "waiting_usage", "stopping"):
        parts.append([("no campaign watcher entry", "muted")])
    wrote = s["wrote_age"]
    parts.append([("loop wrote ", "subtle"), (dur(wrote) + " ago", "text" if wrote < 90 else "strong")])
    if s["stop_requested"]:
        parts.append([("stop requested", "strong")])
    if pop.get("stop_reason"):
        parts.append([(pop["stop_reason"], "muted")])
    lines = _flow(top, width, lead) + _flow(parts, width)

    if st:
        u = pop["usage"]
        if st["budget"]:
            spend: Seg = [("window ", "subtle"), (f"${st['spend']:.2f}", "text"), (" spent + ", "subtle"),
                          (f"${st['reserved']:.2f}", "text"), (" reserved of ", "subtle"),
                          (f"${st['budget']:g}", "text"), (f"  {st['fraction']:.0%}", "strong")]
        else:
            spend = [("window ", "subtle"), (f"${st['spend']:.2f}", "text"),
                     (" spent, no window_budget", "subtle")]
        up: list[Seg] = [spend,
                         [(f"{st['sessions_in_window']} sessions in {st['window_sec'] / 3600:g} h", "text")],
                         [("level ", "subtle"), (st["level"], "text" if st["level"] == "ok" else "strong")]]
        if st["level"] != "ok" and st.get("next_eligible"):
            up.append([("next eligible ", "subtle"), (hhmm(st["next_eligible"]), "text")])
        up.append([(f"{u['pauses']} pauses", "text"), (f", {dur(u['waiting_seconds'])} waited", "subtle")])
        up.append([(f"{u['deferred']} deferred", "text")])
        up.append([(f"{u['rate_limits']} rate limits", "text")])
        l3: Seg = [(" ", "text")]
        if st["budget"]:
            l3 += bar(st["fraction"], 10) + [("  ", "text")]
        lines += _flow(up, width, l3)
    elif pop.get("campaign_file"):
        lines.append([(" usage: campaign file not readable from here", "muted")])
    return lines


def section(title: str, width: int) -> Seg:
    return [(f" {title} ", "muted"), ("─" * max(0, width - len(title) - 3), "line")]


def job_segs(r: dict, room: int) -> Seg:
    seg: Seg = [(r["id"], "strong"), (f" {r['operator']}", "text")]
    if r["parents"]:
        seg.append((f" ← {','.join(r['parents'])}", "subtle"))
    seg.append(("  ", "text"))
    if r["budget_sec"]:
        seg += bar(r["lease"] / r["budget_sec"] if r["lease"] is not None else None, 8)
        seg.append((f" {dur(r['lease'])} of {dur(r['budget_sec'])}", "text"))
    else:
        seg.append((dur(r["lease"]), "text"))
    if room > 70:
        seg.append((f"  ·  {r['phase']}", "muted"))
        if r["train"] is not None:
            seg.append((f", trained {dur(r['train'])}", "muted"))
        if r["heartbeat_age"] is not None and r["heartbeat_age"] > 60:
            seg.append((f"  ·  heartbeat {dur(r['heartbeat_age'])} ago", "strong"))
    return seg


def gpu_pane(s: dict, width: int) -> list[Seg]:
    rows = s["rows"]
    by_gpu = {r["gpu"]: r for r in rows if r["running"] and r["gpu"] is not None}
    cards = {g["index"]: g for g in s["gpus"]}
    indices = list(s["gpu_list"] or [])
    for i in sorted(cards):
        if i not in indices and (i in by_gpu or not indices):
            indices.append(i)
    lines: list[Seg] = []
    if not indices:
        cpu = [r for r in rows if r["running"]]
        for r in cpu:
            lines.append([("  cpu  ", "muted")] + job_segs(r, width - 7))
        if not cpu:
            lines.append([("  no gpu in the campaign; nothing running", "faint")])
        return lines

    def name(g: dict) -> str:
        return g["name"].replace("NVIDIA ", "").replace("GeForce ", "")

    name_w = min(20 if width >= 120 else 12,
                 max((len(name(cards[i])) for i in indices if i in cards), default=10))
    for i in indices:
        g = cards.get(i)
        seg: Seg = [(f"  {i}  ", "strong")]
        if g:
            seg.append((f"{name(g)[:name_w]:<{name_w}}  ", "text"))
            seg.append((f"{g['util']:>3} %  ", "text" if g["util"] else "subtle"))
            if width >= 120:
                spark = "".join(SPARK[min(7, u * 8 // 101)] for u in g["history"])
                seg.append((f"{spark:<8}  ", "muted"))
            seg.append((f"{g['used_mb'] / 1024:>4.1f}/{g['total_mb'] / 1024:.0f} GiB  ", "text"))
            if width >= 100:
                seg.append((f"{g['temp'] if g['temp'] is not None else '·':>3}°  ", "subtle"))
                seg.append((f"{g['power']:>4.0f} W  " if g["power"] is not None else "   ·    ", "subtle"))
        else:
            seg.append((f"{'no reading':<{name_w}}  ", "faint"))
        used = sum(len(t) for t, _ in seg)
        r = by_gpu.get(i)
        if r:
            seg += job_segs(r, width - used)
        elif g and g["util"] >= 5:
            seg.append(("in use outside the campaign", "muted"))
        else:
            seg.append(("idle", "faint"))
        lines.append(seg)
    return lines


# columns: key, header, width, align, priority (the highest is dropped first when narrow)
COLUMNS = [("id", "id", 6, "<", 0), ("operator", "operator", 9, "<", 0), ("parent", "parent", 7, "<", 3),
           ("gpu", "gpu", 3, ">", 1), ("lease", "lease", 7, ">", 0), ("train", "train", 6, ">", 3),
           ("turns", "turns", 5, ">", 2), ("cost", "cost", 6, ">", 2), ("model", "model", 9, "<", 4),
           ("fitness", "fitness", 9, ">", 0), ("bar", "", 12, "<", 5), ("note", "", 0, "<", 1)]


def pick_columns(width: int, rows: list[dict]) -> list[tuple]:
    """The columns that fit, widest content first; parent and model grow to fit."""
    grow = {"parent": max([7] + [len(",".join(r["parents"])) for r in rows]),
            "model": max([9] + [len(r["model"]) for r in rows])}
    cols = [(k, t, min(16, grow.get(k, w)), al, p) for k, t, w, al, p in COLUMNS]
    for prio in (5, 4, 3, 2):
        if sum(c[2] + 2 for c in cols if c[0] != "note") + 32 <= width:
            break
        cols = [c for c in cols if c[4] < prio]
    return cols


def population_pane(s: dict, width: int, height: int, scroll: int) -> tuple[list[Seg], int]:
    rows, pop = s["rows"], s["pop"]
    cols = pick_columns(width, rows)
    fits = [r["fitness"] for r in rows if r["fitness"] is not None]
    lo, hi = (min(fits), max(fits)) if fits else (0, 1)
    hib = s["cfg"].get("report", {}).get("higher_is_better", True)

    head: Seg = [(" ", "text")] + [(f"{title:{al}{w}}  " if key != "note" else "", "subtle")
                                   for key, title, w, al, _ in cols]
    body: list[Seg] = []
    for r in rows:
        best = r["id"] == pop.get("best")
        live_row = r["status"] in ("evaluated", "frozen") or r["running"]
        role = "text" if live_row else "muted"
        seg: Seg = [(" ", "text")]
        for key, _, w, al, _ in cols:
            if key == "id":
                seg.append((f"{r['id']:{al}{w}}  ", "strong" if best or r["running"] else role))
            elif key == "operator":
                seg.append((f"{r['operator']:{al}{w}}  ", role))
            elif key == "parent":
                seg.append((f"{(','.join(r['parents']) or '·'):{al}{w}}  ", "subtle"))
            elif key == "gpu":
                seg.append((f"{('·' if r['gpu'] is None else r['gpu']):{al}{w}}  ", "subtle"))
            elif key == "lease":
                seg.append((f"{mmss(r['lease']):{al}{w}}  ", role))
            elif key == "train":
                seg.append((f"{mmss(r['train']):{al}{w}}  ", role if r["train"] is not None else "faint"))
            elif key == "turns":
                seg.append((f"{(r['turns'] if r['turns'] is not None else '·'):{al}{w}}  ", role))
            elif key == "cost":
                cost = f"${r['cost']:.2f}" if r["cost"] is not None else "·"
                seg.append((f"{cost:{al}{w}}  ", role))
            elif key == "model":
                seg.append((f"{r['model']:{al}{w}}  ", "subtle"))
            elif key == "fitness":
                if r["fitness"] is None:
                    seg.append((f"{'·':{al}{w}}  ", "faint"))
                elif best:
                    seg.append((f" {r['fitness']:.4g} "[:w + 2].rjust(w + 2), "invert"))
                else:
                    seg.append((f"{r['fitness']:.4g}"[:w].rjust(w) + "  ",
                                "strong" if r["status"] == "evaluated" else role))
            elif key == "bar":
                if r["fitness"] is None or hi == lo:
                    seg.append((" " * (w + 2), "text"))
                else:
                    frac = (r["fitness"] - lo) / (hi - lo)
                    seg += bar(frac if hib else 1 - frac, w) + [("  ", "text")]
            elif key == "note":
                if r["running"]:
                    where = f"gpu {r['gpu']}" if r["gpu"] is not None else "cpu"
                    seg.append((f"running on {where}, {r['phase']}", "muted"))
                elif best:
                    seg.append(("best", "strong"))
                elif r["status"] == "frozen":
                    seg.append(("frozen for the final read", "text"))
                elif r["fail_reason"]:
                    seg.append((f"{r['exec']}: {r['fail_reason']}", "muted"))
                elif r["redispatch_of"]:
                    seg.append((f"re-dispatch of {r['redispatch_of']}", "subtle"))
        body.append(seg)

    room = max(1, height - 1)
    max_scroll = max(0, len(body) - room)
    scroll = min(scroll, max_scroll)
    start = max_scroll - scroll         # scroll 0 = the newest rows at the bottom
    shown = body[start:start + room]
    if start > 0:
        shown[0] = [(f" … {start} earlier, k to scroll up", "faint")]
    if start + room < len(body):
        shown[-1] = [(f" … {len(body) - start - room} later, j to scroll down", "faint")]
    return [head] + shown, scroll


def log_pane(s: dict, height: int) -> list[Seg]:
    ev = s["events"][-height:] if height > 0 else []
    if not ev:
        return [[(" no events yet", "faint")]]
    out = []
    for e in ev:
        ts = e.get("ts", "")
        stamp = ts[11:19] if len(ts) >= 19 else ts
        out.append([(f" {stamp}  ", "subtle"),
                    (e.get("msg", ""), "strong" if e.get("type") == "error" else "text")])
    return out


def render(s: dict, width: int, height: int | None, scroll: int, interval: float,
           mode: str | None) -> tuple[list[str], int]:
    """height None = no limit (--once). Returns painted lines and the clamped scroll."""
    top = header(s, width)
    gpus = gpu_pane(s, width)
    fixed = len(top) + len(gpus) + 8          # blanks, section rules, the footer
    n_rows = len(s["rows"]) + 1
    if height is None:
        pop_h, log_h = n_rows, min(10, max(3, len(s["events"])))
    else:
        free = max(0, height - fixed)
        log_h = max(3, min(8, free // 4))
        pop_h = max(2, free - log_h)
        if n_rows < pop_h:
            pop_h, log_h = n_rows, max(1, min(len(s["events"]) or 1, free - n_rows))
    pop_lines, scroll = population_pane(s, width, pop_h, scroll)
    log_lines = log_pane(s, log_h)
    stamp = datetime.fromtimestamp(s["now"], timezone.utc).strftime("%H:%M:%SZ")
    foot_l = " q quit  ·  j/k scroll  ·  r refresh  ·  +/- interval" if height is not None else ""
    foot_r = (f"every {interval:g} s  ·  " if height is not None else "") + stamp
    footer: Seg = [(foot_l, "faint"), (" " * max(1, width - len(foot_l) - len(foot_r) - 1), "text"),
                   (foot_r, "faint")]
    segs: list[Seg] = [*top, [], section("gpus", width), *gpus, [],
                       section("population", width), *pop_lines, [],
                       section("log", width), *log_lines, [], footer]
    return [paint(sg, width, mode) for sg in segs], scroll


# ---------------------------------------------------------------------------
# the loop
# ---------------------------------------------------------------------------

def live(interval: float, mode: str | None) -> None:
    probe = Probe()
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    out = sys.stdout
    scroll, snap, last = 0, None, 0.0
    out.write("\x1b[?1049h\x1b[?25l")
    out.flush()
    try:
        tty.setcbreak(fd)
        while True:
            now = time.time()
            if snap is None or now - last >= interval:
                try:
                    snap = snapshot(probe)
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                    if snap is None:
                        raise
                    pass                      # a file mid-write: keep the last good frame
                last = now
            cols, rows = shutil.get_terminal_size((100, 40))
            lines, scroll = render(snap, cols, rows, scroll, interval, mode)
            out.write("\x1b[H" + "\x1b[K\n".join(lines[:rows]) + "\x1b[K\x1b[J")
            out.flush()
            wait = max(0.05, interval - (time.time() - last))
            r, _, _ = select.select([fd], [], [], min(wait, 1.0))
            if not r:
                continue
            key = os.read(fd, 8)
            if key in (b"q", b"Q", b"\x03", b"\x1b"):
                return
            if key in (b"j", b"\x1b[B"):
                scroll = max(0, scroll - 1)
            elif key in (b"k", b"\x1b[A"):
                scroll += 1
            elif key == b"r":
                last = 0.0
            elif key in (b"+", b"="):
                interval = min(60.0, interval * 2)
            elif key == b"-":
                interval = max(0.5, interval / 2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        out.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        out.flush()


def once(mode: str | None) -> None:
    snap = snapshot(Probe())
    cols = shutil.get_terminal_size((110, 40)).columns     # honours $COLUMNS when piped
    lines, _ = render(snap, cols, None, 0, 0.0, mode)
    print("\n".join(lines))


def plain() -> None:
    """The original text: one campaign line, the governor's line, one row per
    candidate. Scripts grep it; it does not change shape."""
    pop = C.load_pop()
    if pop is None:
        L.die(f"no {C.POP_FILE}: no campaign has started here")
    pop.setdefault("usage", C.usage_defaults())
    rows = [(k, v["operator"], ",".join(v["parents"]) or "-", v["exec"] or v["status"],
             "-" if v["fitness"] is None else f"{v['fitness']:.6g}") for k, v in pop["candidates"].items()]
    print(f"campaign {pop['campaign']}  status {pop['status']}  tick {pop['tick']}  "
          f"settled {pop['settled']}  best {pop['best']}  claim {pop['claim']}  "
          f"gpu-h {pop['gpu_seconds']/3600:.2f}")
    cfg = C._campaign_cfg(pop)
    if cfg is not None:
        st = C.usage_state(cfg, pop)
        print("  usage: " + C._usage_line(cfg, pop, st))
    for r in rows:
        print("  " + "  ".join(f"{x:<12}" if i < 4 else x for i, x in enumerate(r)))


def cmd_status(args) -> None:
    mode = color_mode(args.no_color)
    interactive = sys.stdout.isatty() and sys.stdin.isatty()
    if args.plain or (not args.once and not interactive):
        plain()
    elif args.once:
        once(mode)
    else:
        try:
            live(args.interval, mode)
        except KeyboardInterrupt:
            pass


def register(sub, lab_module) -> None:
    global L
    L = lab_module
    q = sub.add_parser("status", help="the campaign at a glance: live on a terminal, "
                                      "plain text when piped")
    q.add_argument("--once", action="store_true", help="one frame of the live layout, then exit")
    q.add_argument("--plain", action="store_true", help="the one-line-per-candidate text")
    q.add_argument("--interval", type=float, default=2.0, help="seconds between refreshes (2)")
    q.add_argument("--no-color", action="store_true")
    q.set_defaults(func=cmd_status)
