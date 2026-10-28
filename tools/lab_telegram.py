"""lab telegram — the campaign on your phone: results as they land, a digest, questions, and stop.

`lab run` starts it on a thread of its own whenever a bot is configured (`--no-telegram` or
LAB_TELEGRAM=0 to leave it out; a --once or --max-ticks run never starts it), and posts what is
left in the feed before it exits. `lab telegram run` does the same for a campaign run elsewhere.

    lab telegram setup            after messaging the bot once: prints your chat id
    lab telegram run              post and answer until ^C
    lab telegram preview [cNNNN…] print the posts for these candidates (default the last three
                                  settled), model lines included; sends nothing

TELEGRAM_TOKEN and TELEGRAM_CHAT_ID come from the environment or ~/.config/labloop-telegram/env.
Only that chat is answered. State (feed offsets, mute, last digest) is in .lab/telegram.json.

What is posted. A result is posted silently, a new best and the campaign's start, stopping and
end with a notification; launches, usage pauses and kills by a stop are not posted. A digest
(every $LAB_TELEGRAM_DIGEST_HOURS, default 6, 0 for none) sums up what happened since the last
one. /mute [h] holds results back (new bests and the end still come, silently) until /unmute;
$LAB_TELEGRAM_QUIET=23-8 makes everything silent between those local hours.

The numbers in a post are the bot's, from population.json. Two lines in each result post, what
was changed and what the worker found, are written by the local model (`nullsilver-slm ask
--no-tools`, a few seconds on the CPU) from the Finding section of the candidate's summary.md
and marked as its reading; without the model, or with LAB_TELEGRAM_SLM=0, the post carries the
summary's Change line instead.

Commands: /status /digest /top [n] /summary cNNNN /ask Q /mute [h] /unmute /stop /help. A reply
to a result asks the local model about that candidate (read-only tools inside this dir, as the
web view's Ask). /stop asks first, with buttons: stop after the running jobs, or now (kills
them); either runs `lab campaign stop`. Standard library only.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import lab_campaign as C
import lab_status as S
import lab_ui as U

L: Any = None

ENV_FILE = Path.home() / ".config/labloop-telegram/env"
CID_RE = re.compile(r"\bc\d{4,}\b")
MAX_LEN = 4000                     # Telegram's limit is 4096
EVENTS_POLL_SEC = 5
CONFIRM_SEC = 300                  # a /stop button older than this is refused
COMMANDS = [("status", "campaign state"), ("digest", "what happened since the last digest"),
            ("top", "best candidates: /top [n]"), ("summary", "a candidate's summary: /summary cNNNN"),
            ("ask", "ask the local model: /ask QUESTION"), ("mute", "hold results back: /mute [hours]"),
            ("unmute", "post results again"), ("stop", "stop the campaign (asks first)"),
            ("help", "what the bot does")]
HELP = ("<b>lab telegram</b>\n\nResults come in silently; a new best and the campaign's end notify. "
        "Reply to a result to ask the local model about that candidate.\n\n"
        + "\n".join(f"/{c} · {d}" for c, d in COMMANDS))


def config() -> tuple[str, str | None] | None:
    env = {}
    try:
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    token = os.environ.get("TELEGRAM_TOKEN") or env.get("TELEGRAM_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or env.get("TELEGRAM_CHAT_ID")
    return (token, chat) if token else None


def log(msg: str) -> None:
    print(f"lab telegram: {msg}", file=sys.stderr, flush=True)


class ApiError(Exception):
    def __init__(self, code: int, desc: str, retry_after: int | None = None):
        super().__init__(f"{code} {desc}")
        self.code, self.retry_after = code, retry_after


class Api:
    def __init__(self, token: str, chat_id: str | None):
        self.base = f"https://api.telegram.org/bot{token}/"
        self.chat_id = chat_id

    def call(self, method: str, http_timeout: float = 30, **params: Any) -> Any:
        data = urllib.parse.urlencode({k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                                       for k, v in params.items() if v is not None}).encode()
        for attempt in range(3):
            try:
                with urllib.request.urlopen(self.base + method, data, timeout=http_timeout) as r:
                    out = json.load(r)
            except urllib.error.HTTPError as e:
                try:
                    out = json.load(e)
                except ValueError:
                    out = {"error_code": e.code, "description": e.reason}
            if out.get("ok"):
                return out["result"]
            after = (out.get("parameters") or {}).get("retry_after")
            if out.get("error_code") == 429 and after and attempt < 2:
                time.sleep(after + 1)
                continue
            raise ApiError(out.get("error_code") or 0, out.get("description") or "?", after)

    def send(self, text: str, silent: bool = False, reply_to: int | None = None,
             buttons: list[list[tuple[str, str]]] | None = None, force_reply: bool = False) -> dict | None:
        """Posts text in Telegram's HTML subset (callers escape what they did not write), split
        at paragraph breaks past the limit; a part Telegram cannot parse goes again as plain
        text. Returns the first message."""
        markup = None
        if buttons:
            markup = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row]
                                          for row in buttons]}
        elif force_reply:
            markup = {"force_reply": True, "input_field_placeholder": "your question"}
        parts, first = split_html(text), None
        for i, chunk in enumerate(parts):
            part = dict(chat_id=self.chat_id, text=chunk,
                        disable_notification="true" if silent else None,
                        reply_to_message_id=reply_to if i == 0 else None,
                        allow_sending_without_reply="true",
                        reply_markup=markup if i == len(parts) - 1 else None,
                        link_preview_options={"is_disabled": True})
            try:
                m = self.call("sendMessage", parse_mode="HTML", **part)
            except ApiError as e:
                if e.code != 400:
                    raise
                log(f"Telegram refused the HTML ({e}); sent as plain text")
                part["text"] = strip_tags(chunk)[:MAX_LEN]
                m = self.call("sendMessage", **part)
            first = first or m
        return first

    def edit(self, message_id: int, text: str) -> None:
        try:
            self.call("editMessageText", chat_id=self.chat_id, message_id=message_id, text=text)
        except ApiError as e:
            log(f"edit: {e}")


def esc(s: Any) -> str:
    return html.escape(str(s), quote=False)


def strip_tags(h: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def split_html(text: str) -> list[str]:
    """Telegram-sized parts, cut between paragraphs so every tag closes inside its part; a
    paragraph longer than a message goes as escaped plain pieces."""
    parts, cur = [], ""
    for block in text.split("\n\n"):
        if len(block) > MAX_LEN:
            if cur:
                parts.append(cur)
                cur = ""
            flat = strip_tags(block)
            parts += [esc(flat[i:i + MAX_LEN - 400]) for i in range(0, len(flat), MAX_LEN - 400)]
        elif len(cur) + len(block) + 2 > MAX_LEN:
            parts.append(cur)
            cur = block
        else:
            cur = f"{cur}\n\n{block}" if cur else block
    return [p for p in parts + [cur] if p.strip()] or [" "]


def md_inline(s: str) -> str:
    out = []
    for p in re.split(r"(`[^`\n]+`)", s):
        if len(p) > 2 and p[0] == p[-1] == "`":
            out.append(f"<code>{esc(p[1:-1])}</code>")
            continue
        p = esc(p)
        p = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: f"<b>{m[1] or m[2]}</b>", p)
        p = re.sub(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])", r"<i>\1</i>", p)
        p = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', p)
        out.append(p)
    return "".join(out)


def md_table(rows: list[str]) -> str:
    cells = [[c.strip()[:28] for c in r.strip().strip("|").split("|")] for r in rows
             if not re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", r)]
    widths = [max(len(r[i]) if i < len(r) else 0 for r in cells) for i in range(max(map(len, cells)))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in cells)


def md_html(md: str) -> str:
    """Markdown as workers and the model write it, in Telegram's HTML: headings and **bold**
    bold, `code`, tables and fenced blocks as <pre>, list items with a bullet, [links](url)."""
    lines, out, i = re.sub(r"\s*【([^】]*)】", r" (\1)", md).splitlines(), [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            j, buf = i + 1, []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(lines[j])
                j += 1
            out.append(f"<pre>{esc(chr(10).join(buf).strip(chr(10)))}</pre>")
            i = j + 1
            continue
        if ln.lstrip().startswith("|"):
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                buf.append(lines[i])
                i += 1
            out.append(f"<pre>{esc(md_table(buf))}</pre>")
            continue
        m = re.match(r"#{1,6}\s+(.*)", ln) or re.fullmatch(r"\*\*([^*]+)\*\*", ln.strip())
        if m:
            out += ([""] if out and out[-1] else []) + [f"<b>{md_inline(m[1])}</b>"]
        elif (m := re.match(r"(\s*)[-*+]\s+(.*)", ln)):
            out.append(f"{m[1]}• {md_inline(m[2])}")
        else:
            out.append(md_inline(ln))
        i += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


# ---------------------------------------------------------------------------
# what a post says
# ---------------------------------------------------------------------------

class Campaign:
    """The campaign dir, read fresh on every call: lab run writes it while the bot reads."""

    def __init__(self) -> None:
        self.probe = S.Probe()

    def brief(self) -> dict:
        return U.campaign_brief(U._toml())

    def pop(self) -> dict:
        try:
            return json.loads((L.ROOT / C.POP_FILE).read_text())
        except (OSError, ValueError):
            return {"candidates": {}}

    def state(self) -> dict:
        return U.state(self.probe)

    def summary(self, cid: str) -> str | None:
        try:
            return (L.ROOT / C.CAND_DIR / cid / "summary.md").read_text()
        except OSError:
            return None

    def finding(self, cid: str) -> str:
        """The Change and Interpretation lines of the summary's Finding, or "" without them.
        Only those two: the 2B model given the whole section mixed up who was compared to whom."""
        s = self.summary(cid) or ""
        lines = [m.group(0).strip() for k in ("Change", "Interpretation")
                 for m in [re.search(rf"^{k}:\s*\S.*$", s, re.M)] if m]
        return "\n".join(lines)[:3000] if len(lines) == 2 else ""

    def ui_url(self) -> str | None:
        u = U._json_file(L.LAB_DIR / "ui.json") or {}
        pid = u.get("pid")
        if not (u.get("url") and pid):
            return None
        try:
            os.kill(pid, 0)
        except OSError:
            return None
        return u["url"]


def fnum(x: Any) -> str:
    return f"{x:.4f}" if isinstance(x, (int, float)) else "—"


def delta(a: Any, b: Any) -> str:
    return f"{a - b:+.4f}" if isinstance(a, (int, float)) and isinstance(b, (int, float)) else ""


def progress(c: Campaign, pop: dict) -> str:
    b = c.brief()
    gpu = f"GPU {pop.get('gpu_seconds', 0) / 3600:.1f}" + (f"/{b['gpu_hours_total']}" if b.get("gpu_hours_total") else "") + " h"
    settled = f"{pop.get('settled', 0)}" + (f"/{b['max_candidates']}" if b.get("max_candidates") else "")
    return f"{pop.get('campaign') or b.get('id')} · {settled} settled · {gpu}"


def slm_lines(c: Campaign, cid: str) -> str | None:
    """What was changed and what the worker found, in two sentences by the local model, or
    None (no model, switched off, timed out, nothing to read)."""
    if os.environ.get("LAB_TELEGRAM_SLM") == "0":
        return None
    b, finding = U.slm_bin(), c.finding(cid)
    if not (b and finding):
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".md", prefix="lab-telegram-", delete=False) as f:
        f.write(finding + "\n")
        ctx = f.name
    try:
        cp = subprocess.run(
            [b, "ask", "--no-tools", "--plain", "--context-file", ctx, "--timeout", "60",
             "Shorten the two lines above for a phone notification. Write exactly two sentences in "
             "plain English: first what was changed (from Change), then what was concluded and how "
             "confidently (from Interpretation). Keep names like c0025, NorMuon or BPE as written. "
             "Add nothing that is not in the lines. No markdown."],
            capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        os.unlink(ctx)
    out = plain(cp.stdout) if cp.returncode == 0 else ""
    if re.search(r"\b(I'm sorry|I’m sorry|I can't|I can’t|don't have access|don’t have access)\b", out):
        return None
    return out[:600] or None


def cand_title(cid: str) -> str:
    """The web view's one-line title of a candidate, with its id as written (title_of capitalizes)."""
    return re.sub(r"^C(\d{4,})\b", r"c\1", U.title_of(cid) or "")


def plain(text: str) -> str:
    """The model writes markdown now and then; a post gets plain text."""
    text = re.sub(r"\s*【([^】]*)】", r" (\1)", text)
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
    return re.sub(r"`([^`]*)`", r"\1", text).strip()


def vs(a: Any, b: Any, label: str, hib: bool) -> str:
    """'▲ +0.0477 c0025': the difference to b, the arrow up when it is better."""
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return ""
    arrow = "=" if a == b else ("▲" if (a > b) == hib else "▼")
    return f"{arrow} {a - b:+.4f} {esc(label)}"


def result_post(c: Campaign, cid: str, best: bool, use_slm: bool = True) -> str:
    pop = c.pop()
    cands, hib = pop.get("candidates") or {}, c.brief()["higher_is_better"]
    v = cands.get(cid) or {}
    f = v.get("fitness")
    head = f"{'🏆' if best else '✅'} <b>{esc(cid)}</b> · {esc(v.get('operator') or '')}"
    if v.get("parents"):
        head += " ← " + " × ".join(esc(p) for p in v["parents"])
    if best:
        head += " · <b>new best</b>"
    ref = [vs(f, (cands.get(p) or {}).get("fitness"), p, hib) for p in v.get("parents") or []]
    others = [x for k, x in cands.items() if k != cid and isinstance(x.get("fitness"), (int, float))
              and (x.get("ended") or "") <= (v.get("ended") or "~")]  # settled before this one
    top = (max if hib else min)(others, key=lambda x: x["fitness"]) if others else None
    if top and top["id"] not in (v.get("parents") or []):
        ref.append(vs(f, top["fitness"], f"{top['id']} ({'was ' if best else ''}best)", hib))
    if cid != "c0000":
        ref.append(vs(f, (cands.get("c0000") or {}).get("fitness"), "baseline", hib))
    lines = [head, "", f"<b>{fnum(f)}</b> search"]
    lines += [f"<code>{r}</code>" for r in ref if r]
    comp = v.get("components") or {}
    if comp:
        lines.append("<code>" + esc("  ".join(f"{k} {x:.3f}" if isinstance(x, (int, float)) else f"{k} {x}"
                                              for k, x in comp.items())) + "</code>")
    prose = slm_lines(c, cid) if use_slm else None
    if prose:
        lines += ["", f"<blockquote>{esc(prose)}</blockquote>", "<i>the local model's reading of summary.md</i>"]
    elif cand_title(cid):
        lines += ["", f"<blockquote>{esc(cand_title(cid))}</blockquote>"]
    lines += ["", f"<i>{esc(progress(c, pop))}</i>"]
    return "\n".join(lines)


def result_buttons(cid: str) -> list[list[tuple[str, str]]]:
    return [[("Summary", f"sum:{cid}"), ("Ask about it", f"ask:{cid}")]]


def fmt_status(c: Campaign) -> str:
    st = c.state()
    if st.get("empty"):
        return f"<b>{esc(st['campaign'].get('id') or 'this dir')}</b>: no population yet"
    p, b, u = st["pop"], st["campaign"], st["usage"]
    rows = {r["id"]: r for r in st["rows"]}
    best, icon = p.get("best"), {"running": "🟢", "waiting_usage": "⏸", "stopping": "🛑", "finished": "🏁"}
    lines = [f"{icon.get(p['status'], '•')} <b>{esc(p['campaign'])}</b> · {esc(p['status'])}"
             + (" (stop requested)" if st.get("stop_requested") else ""), "",
             f"<b>best</b> {esc(best)} <code>{fnum((rows.get(best) or {}).get('fitness'))}</code> search · "
             f"threshold <code>{esc(b.get('threshold'))}</code> final"]
    if st.get("final"):
        lines.append(f"<b>final</b> {esc(st['final']['candidate'])} <code>{fnum(st['final']['score'])}</code>"
                     f" → claim <b>{esc(p.get('claim'))}</b>")
    lines.append(f"<b>done</b> {esc(progress(c, c.pop()).split(' · ', 1)[1])}")
    if p["status"] == "waiting_usage":
        lines.append(f"<b>usage</b> waiting until {esc((u.get('next_eligible') or '?')[11:16])}Z")
    elif u.get("waiting_seconds"):
        lines.append(f"<b>usage</b> held {u['waiting_seconds'] / 3600:.1f} h in all ({u.get('pauses') or 0} pauses)")
    running = [r for r in st["rows"] if r.get("running")]
    if running:
        lines += ["", "<b>running</b>"]
        lines.append("<pre>" + esc("\n".join(
            f"{r['id']} {r['operator']:<9} gpu{r.get('gpu')} {(r.get('lease') or 0) / 60:4.0f} min"
            + (f"  {r['phase']}" if r.get("phase") else "") for r in running)) + "</pre>")
    elif p["status"] != "finished":
        lines.append("<b>running</b> nothing")
    if st.get("eta"):
        lines.append(f"<b>eta</b> last candidate around {time.strftime('%a %H:%M', time.localtime(st['eta']))}")
    url = c.ui_url()
    if url:
        lines += ["", f'<a href="{esc(url)}">web view</a>']
    return "\n".join(lines)


def fmt_top(c: Campaign, n: int) -> str:
    hib = c.brief()["higher_is_better"]
    rows = [v for v in c.pop().get("candidates", {}).values() if isinstance(v.get("fitness"), (int, float))]
    rows.sort(key=lambda v: v["fitness"], reverse=hib)
    out = [f"<b>top {min(n, len(rows))}</b> by search fitness", ""]
    for i, v in enumerate(rows[:n], 1):
        out.append(f"{i}. <b>{esc(v['id'])}</b> <code>{v['fitness']:.4f}</code> {esc(v['operator'])}\n"
                   f"<i>{esc(cand_title(v['id'])[:140])}</i>")
    return "\n".join(out) if rows else "no results yet"


FIELDS = r"(Change|Hypothesis|Local observation|Interpretation|Limitations|Topics)"


def fmt_summary(c: Campaign, cid: str) -> str:
    s = c.summary(cid)
    v = (c.pop().get("candidates") or {}).get(cid, {})
    if s is None:
        st = v.get("status")
        return f"<b>{esc(cid)}</b>: no summary.md yet" + (f" (status {esc(st)})" if st else " (no such candidate)")
    head = f"📄 <b>{esc(cid)}</b> · {esc(v.get('operator') or '')}"
    if v.get("parents"):
        head += " ← " + " × ".join(esc(p) for p in v["parents"])
    if isinstance(v.get("fitness"), (int, float)):
        head += f" · <code>{v['fitness']:.4f}</code>"
    body = re.sub(rf"(?m)^{FIELDS}:", r"<b>\1:</b>", md_html(s))
    return f"{head}\n\n{body}"


# ---------------------------------------------------------------------------
# the feed, the digest and the chat
# ---------------------------------------------------------------------------

def read_events(start: int) -> tuple[list[tuple[dict, int]], int]:
    """Whole lines of the feed from byte offset start, each with the offset just past it,
    and the offset after the last whole line."""
    out, off = [], start
    try:
        with open(L.EVENTS_PATH, "rb") as f:
            f.seek(start)
            for raw in f:
                if not raw.endswith(b"\n"):
                    break  # a line still being written
                off += len(raw)
                try:
                    out.append((json.loads(raw), off))
                except ValueError:
                    continue
    except OSError:
        pass
    return out, off


def in_quiet_hours() -> bool:
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", os.environ.get("LAB_TELEGRAM_QUIET", ""))
    if not m:
        return False
    a, b, h = int(m[1]), int(m[2]), time.localtime().tm_hour
    return (a <= h < b) if a <= b else (h >= a or h < b)


def digest_text(c: Campaign, events: list[dict], since: float) -> str | None:
    done = [e for e in events if e.get("type") == "candidate.done"]
    failed = [e for e in events if e.get("type") == "candidate.failed"
              and "campaign stopped" not in ((e.get("data") or {}).get("reason") or "")]
    paused = sum(1 for e in events if e.get("type") == "campaign.paused")
    waited = sum((e.get("data") or {}).get("waited_sec") or 0 for e in events
                 if e.get("type") == "note" and "resumed after" in (e.get("msg") or ""))
    if not (done or failed or paused):
        return None
    hours = (time.time() - since) / 3600
    score = lambda e: f"{esc(e['candidate'])} <code>{fnum(e['data'].get('fitness'))}</code>"
    lines = [f"🗒 <b>digest</b> · the last {hours:.0f} h", "",
             f"<b>{len(done)}</b> settled" + (f", <b>{len(failed)}</b> failed" if failed else "")]
    bests = [e for e in done if (e.get("data") or {}).get("best")]
    if bests:
        lines.append(f"🏆 new best{' (last 3 of ' + str(len(bests)) + ')' if len(bests) > 3 else ''}: "
                     + ", ".join(score(e) for e in bests[-3:]))
    if done:
        hib = c.brief()["higher_is_better"]
        top = sorted(done, key=lambda e: e["data"].get("fitness") or 0, reverse=hib)[:3]
        lines.append("top of these: " + ", ".join(score(e) for e in top))
    for e in failed[:5]:
        lines.append(f"❌ {esc(e['msg'])}")
    if paused or waited:
        lines.append(f"⏸ {paused} usage pause(s), {waited / 60:.0f} min waited")
    lines += ["", "—", "", fmt_status(c)]
    return "\n".join(lines)


class Notifier:
    def __init__(self, api: Api, interactive: bool = True):
        self.api, self.c, self.interactive = api, Campaign(), interactive
        self.path = L.LAB_DIR / "telegram.json"
        self.lock = threading.RLock()      # one drain at a time, and state writes
        self.ask_lock = threading.Lock()
        self.stopped = threading.Event()
        self.digest_h = float(os.environ.get("LAB_TELEGRAM_DIGEST_HOURS") or 6)
        st = U._json_file(self.path)
        if isinstance(st, dict) and "events_offset" in st:
            self.st = st
        else:  # a new campaign from its first event; one already under way from now on
            fresh = not self.c.pop().get("settled")
            _, end = read_events(0)
            self.st = {"events_offset": 0 if fresh else end, "update_offset": 0, "mute_until": 0,
                       "digest_at": time.time(), "digest_offset": 0 if fresh else end}
            if not fresh:
                self.post(f"👀 watching\n\n{fmt_status(self.c)}", silent=True)
        self.save()

    def save(self) -> None:
        with self.lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st))
            tmp.replace(self.path)

    def post(self, text: str, silent: bool = False, **kw: Any) -> dict | None:
        return self.api.send(text, silent=silent or in_quiet_hours(), **kw)

    def muted(self) -> bool:
        return time.time() < (self.st.get("mute_until") or 0)

    # the feed --------------------------------------------------------------

    def on_event(self, e: dict) -> None:
        t, d, cid = e.get("type"), e.get("data") or {}, e.get("candidate")
        if t == "candidate.done":
            if self.muted() and not d.get("best"):
                return
            self.post(result_post(self.c, cid, bool(d.get("best"))), silent=self.muted() or not d.get("best"),
                      buttons=result_buttons(cid))
        elif t == "candidate.failed":
            if not self.muted() and "campaign stopped" not in (d.get("reason") or ""):
                self.post(f"❌ <b>{esc(cid)}</b> · {esc(d.get('operator') or '')} · {esc(d.get('exec') or 'failed')}\n\n"
                          f"<blockquote>{esc(d.get('reason') or e.get('msg'))}</blockquote>",
                          silent=True, buttons=[[("Summary", f"sum:{cid}")]])
        elif t == "campaign.start":
            b, stop = self.c.brief(), d.get("stop") or {}
            limits = [f"{stop['max_candidates']} candidates" if stop.get("max_candidates") else "",
                      f"{b['gpu_hours_total']} GPU h" if b.get("gpu_hours_total") else "",
                      f"{len(d.get('slots') or [])} slot(s)"]
            self.post(f"🔔 <b>{esc(e['campaign'])}</b> started\n\n"
                      f"<b>budget</b> {esc(' · '.join(x for x in limits if x))}\n"
                      f"<b>threshold</b> <code>{esc(d.get('success_threshold'))}</code> on the final split, fixed now")
        elif t == "note" and " stopping: " in (e.get("msg") or ""):
            self.post(f"🛑 <b>{esc(e['campaign'])}</b> stopping\n\n<blockquote>{esc(d.get('reason') or '')}</blockquote>\n"
                      "running jobs finish, then the final split is read")
        elif t == "campaign.stop":
            claim = d.get("claim")
            ok = {"supported": "✅", "not_supported": "✖️"}.get(claim, "🏁")
            self.post(f"{ok} <b>{esc(e['campaign'])}</b> finished · claim <b>{esc(claim)}</b>\n\n"
                      f"<b>final</b> {esc(d.get('best'))} <code>{fnum(d.get('final_score'))}</code> vs threshold "
                      f"<code>{esc(d.get('success_threshold'))}</code>\n"
                      f"<b>spent</b> {esc(d.get('settled'))} candidates · {esc(d.get('gpu_hours'))} GPU h\n"
                      f"<b>stop</b> {esc(d.get('stop_reason'))}\n\n<i>{esc(d.get('report'))} has the rest</i>")

    def drain(self) -> None:
        """Post the feed from the saved offset. The offset moves past each event once it is
        handled, so a crash repeats at most one post and a lost network none."""
        with self.lock:
            try:
                if self.st["events_offset"] > L.EVENTS_PATH.stat().st_size:  # a new feed file
                    self.st.update(events_offset=0, digest_offset=0)
            except OSError:
                return
            events, end = read_events(self.st["events_offset"])
            for e, after in events:
                try:
                    self.on_event(e)
                except ApiError as ex:
                    log(f"post failed ({ex}); skipping {e.get('type')} {e.get('candidate') or ''}")
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    return  # the network: the same events next time
                self.st["events_offset"] = after
                self.save()
            self.st["events_offset"] = end
            self.save()
            if self.digest_h and time.time() - self.st.get("digest_at", 0) >= self.digest_h * 3600:
                self.digest(scheduled=True)

    def digest(self, scheduled: bool = False) -> None:
        events, end = read_events(self.st.get("digest_offset", 0))
        text = digest_text(self.c, [e for e, _ in events], self.st.get("digest_at") or time.time())
        if text or not scheduled:
            self.post(text or f"nothing settled since the last digest\n\n{fmt_status(self.c)}", silent=True)
        self.st.update(digest_at=time.time(), digest_offset=end)
        self.save()

    # the chat --------------------------------------------------------------

    def ask(self, question: str, reply_to: int, about: str | None = None) -> None:
        b = U.slm_bin()
        if not b:
            self.api.send("the local model (nullsilver-slm) is not installed here", reply_to=reply_to)
            return
        if not self.ask_lock.acquire(blocking=False):
            self.api.send("still answering the last question; ask again in a minute", reply_to=reply_to)
            return

        def work() -> None:
            ctx_path = None
            try:
                ctx = U.ask_context(self.c.state())
                if about:
                    ctx += f"\n\nThe question is about candidate {about}; start with candidates/{about}/summary.md."
                with tempfile.NamedTemporaryFile("w", suffix=".md", prefix="lab-telegram-ask-", delete=False) as f:
                    f.write(ctx)
                    ctx_path = f.name
                self.api.call("sendChatAction", chat_id=self.api.chat_id, action="typing")
                cp = subprocess.run([b, "ask", "--dir", str(L.ROOT), "--context-file", ctx_path, question],
                                    capture_output=True, text=True, timeout=420, start_new_session=True)
                answer, read, err = None, [], None
                for line in cp.stdout.splitlines():
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if ev.get("type") == "tool" and ev.get("path"):
                        read.append(ev["path"])
                    elif ev.get("type") == "done":
                        answer = ev.get("answer")
                    elif ev.get("type") == "error":
                        err = ev.get("message")
                if not answer:
                    self.api.send(esc(f"no answer: {err or f'nullsilver-slm exited {cp.returncode}'}"), reply_to=reply_to)
                    return
                tail = f"\n\n<i>read {esc(', '.join(dict.fromkeys(read)))}</i>" if read else ""
                self.api.send(f"💬 {md_html(answer)}{tail}", reply_to=reply_to)
            except subprocess.TimeoutExpired:
                self.api.send("no answer within 7 minutes; the model gave up", reply_to=reply_to)
            except Exception as ex:  # the thread must not die silently
                self.api.send(esc(f"error while asking: {ex}"), reply_to=reply_to)
            finally:
                self.ask_lock.release()
                if ctx_path:
                    os.unlink(ctx_path)

        threading.Thread(target=work, name="lab-telegram-ask", daemon=True).start()

    def stop_prompt(self) -> None:
        pop = self.c.pop()
        if pop.get("status") in ("stopping", "finished"):
            self.api.send(f"{pop.get('campaign')} is already {pop['status']}")
            return
        n = sum(1 for v in pop.get("candidates", {}).values() if v.get("status") == "running")
        now = int(time.time())
        rows = [[("Stop after running jobs", f"stop:soft:{now}")]]
        if n:
            rows.append([(f"Stop now, kill {n}", f"stop:now:{now}")])
        rows.append([("Cancel", "stop:cancel:0")])
        self.api.send(f"🛑 Stop <b>{esc(pop.get('campaign'))}</b>? {n} job(s) running.\n\n"
                      "<i>Either way the final split is read and REPORT.md written.</i>", buttons=rows)

    def stop(self, how: str, at: int, message_id: int) -> None:
        if how == "cancel":
            return self.api.edit(message_id, "not stopped")
        if time.time() - at > CONFIRM_SEC:
            return self.api.edit(message_id, "that button expired; send /stop again")
        if self.c.pop().get("status") in ("stopping", "finished"):
            return self.api.edit(message_id, "already stopping")
        C.cmd_campaign_stop(argparse.Namespace(now=how == "now"))
        self.api.edit(message_id, "stop requested" + (", running jobs killed" if how == "now" else
                                                      "; running jobs finish first")
                      + f" ({time.strftime('%H:%M')}). The campaign posts when it ends.")

    def on_message(self, msg: dict) -> None:
        text = (msg.get("text") or "").strip()
        mid = msg["message_id"]
        cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
        arg = text.split(None, 1)[1].strip() if " " in text else ""
        if cmd in ("/start", "/help"):
            self.api.send(HELP)
        elif cmd == "/status":
            self.api.send(fmt_status(self.c))
        elif cmd == "/digest":
            self.digest()
        elif cmd == "/top":
            self.api.send(fmt_top(self.c, int(arg) if arg.isdigit() else 5))
        elif cmd in ("/summary", "/arch"):
            m = CID_RE.search(arg)
            self.api.send(fmt_summary(self.c, m.group(0)) if m else "/summary cNNNN", reply_to=mid)
        elif cmd == "/ask":
            self.ask(arg, mid) if arg else self.api.send("/ask QUESTION")
        elif cmd == "/mute":
            h = float(arg) if re.fullmatch(r"\d+(\.\d+)?", arg) else 8.0
            self.st["mute_until"] = time.time() + h * 3600
            self.save()
            self.api.send(f"results held back for {h:g} h (new bests and the end still come, silently); "
                          "the digest has the rest. /unmute to undo")
        elif cmd == "/unmute":
            self.st["mute_until"] = 0
            self.save()
            self.api.send("results are posted again")
        elif cmd == "/stop":
            self.stop_prompt()
        elif cmd:
            self.api.send(HELP)
        else:
            replied = CID_RE.search((msg.get("reply_to_message") or {}).get("text") or "")
            bare = CID_RE.fullmatch(text)
            if bare:
                self.api.send(fmt_summary(self.c, bare.group(0)), reply_to=mid)
            elif replied:
                self.ask(text, mid, about=replied.group(0))
            elif text:
                self.ask(text, mid)

    def on_callback(self, q: dict) -> None:
        try:
            self.api.call("answerCallbackQuery", callback_query_id=q["id"])
        except ApiError:
            pass  # an old button press: the query has expired, the press still counts
        kind, _, rest = (q.get("data") or "").partition(":")
        mid = (q.get("message") or {}).get("message_id")
        if kind == "sum":
            self.api.send(fmt_summary(self.c, rest), reply_to=mid)
        elif kind == "ask":
            self.api.send(f"💬 Ask about <b>{esc(rest)}</b>: reply to this message with your question",
                          reply_to=mid, force_reply=True)
        elif kind == "stop":
            how, _, at = rest.partition(":")
            self.stop(how, int(at or 0), mid)

    def poll_updates(self) -> None:
        conflict_logged = False
        while not self.stopped.is_set():
            try:
                updates = self.api.call("getUpdates", http_timeout=40, timeout=25,
                                        offset=self.st.get("update_offset", 0),
                                        allowed_updates=["message", "callback_query"])
            except ApiError as ex:
                if ex.code == 409 and not conflict_logged:  # another bot process reads this token's updates
                    log("another process is reading this bot's messages; posting only until it stops")
                    conflict_logged = True
                time.sleep(60 if ex.code == 409 else 30)
                continue
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as ex:
                log(f"getUpdates: {ex!r}")
                time.sleep(30)
                continue
            conflict_logged = False
            for u in updates:
                self.st["update_offset"] = u["update_id"] + 1
                self.save()
                chat = ((u.get("message") or (u.get("callback_query") or {}).get("message") or {}).get("chat") or {})
                if str(chat.get("id")) != str(self.api.chat_id):
                    continue
                try:
                    if "message" in u:
                        self.on_message(u["message"])
                    elif "callback_query" in u:
                        self.on_callback(u["callback_query"])
                except Exception as ex:  # a bad command must not end the bot
                    log(f"handling an update: {ex!r}")
                    try:
                        self.api.send(esc(f"error: {ex}"))
                    except Exception:
                        pass

    def watch_events(self) -> None:
        while not self.stopped.is_set():
            try:
                self.drain()
            except Exception as ex:  # the feed thread must outlive a bad line or a lost network
                log(f"feed: {ex!r}")
            self.stopped.wait(EVENTS_POLL_SEC)

    def start(self) -> None:
        threading.Thread(target=self.watch_events, name="lab-telegram-feed", daemon=True).start()
        if self.interactive:
            try:
                self.api.call("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS])
            except Exception as ex:
                log(f"setMyCommands: {ex!r}")
            threading.Thread(target=self.poll_updates, name="lab-telegram-chat", daemon=True).start()

    def close(self, timeout: float = 120) -> None:
        """Stop the threads and post what is still in the feed (the campaign's end, usually)."""
        self.stopped.set()
        t = threading.Thread(target=self.drain, daemon=True)
        t.start()
        t.join(timeout)


def start_background() -> Notifier | None:
    """For `lab run`: a bot that cannot start is a line on stderr, never a reason for the
    campaign not to run. Not configured is silent."""
    cfg = config()
    if not cfg:
        return None
    if not cfg[1]:
        log("TELEGRAM_CHAT_ID not set (`lab telegram setup`); the campaign runs without the bot")
        return None
    try:
        n = Notifier(Api(*cfg))
        n.start()
    except Exception as e:
        log(f"did not start ({e!r}); the campaign runs without it")
        return None
    log(f"posting to chat {cfg[1]}")
    return n


def cmd_telegram(args) -> None:
    cfg = config()
    if not cfg:
        L.die(f"TELEGRAM_TOKEN not set (environment or {ENV_FILE})")
    if args.telegram_cmd == "setup":
        chats = {}
        for u in Api(cfg[0], None).call("getUpdates"):
            chat = (u.get("message") or {}).get("chat")
            if chat:
                chats[chat["id"]] = chat.get("username") or chat.get("title") or chat.get("first_name")
        if not chats:
            L.die("no messages yet: send your bot any message in Telegram, then run this again")
        for cid, name in chats.items():
            print(f"TELEGRAM_CHAT_ID={cid}   # {name}  (add it to {ENV_FILE})")
    elif args.telegram_cmd == "preview":
        c = Campaign()
        pop = c.pop()
        ids = args.candidates or [k for k, v in pop.get("candidates", {}).items()
                                  if isinstance(v.get("fitness"), (int, float))][-3:]
        for cid in ids:
            t0 = time.time()
            text = result_post(c, cid, cid == pop.get("best"), use_slm=not args.no_slm)
            print(f"--- {cid} ({time.time() - t0:.1f} s)\n{html.unescape(re.sub(r'<[^>]+>', '', text))}\n")
    elif args.telegram_cmd == "run":
        if not cfg[1]:
            L.die("TELEGRAM_CHAT_ID not set; run `lab telegram setup` first")
        n = Notifier(Api(*cfg))
        n.start()
        print(f"lab telegram: posting {L.ROOT.name} to chat {cfg[1]} (^C to stop)", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            n.close(30)


def register(sub, lab_module) -> None:
    global L
    L = lab_module
    q = sub.add_parser("telegram", help="the campaign on your phone: results, a digest, questions and stop")
    s2 = q.add_subparsers(dest="telegram_cmd", required=True)
    s2.add_parser("setup", help="print the chat id of whoever messaged the bot")
    s2.add_parser("run", help="post this campaign's results and answer commands until ^C")
    p = s2.add_parser("preview", help="print result posts as they would be sent; sends nothing")
    p.add_argument("candidates", nargs="*")
    p.add_argument("--no-slm", action="store_true", help="leave the local model's lines out")
    q.set_defaults(func=cmd_telegram)
