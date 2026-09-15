"""Pi (pi.dev) as a worker backend — the session converter and the endpoint preflight.

Pi has no `--output-format json` result object; `pi -p --mode json` streams one JSON
event per line. `convert()` folds that stream into the same `session.json` shape
`claude -p` produces, so `lab run`'s accounting (turns, cost, served models, error
text for the rate-limit regex) is backend-agnostic. `check_model()` is what `lab run`
and `lab campaign check` ask before a Pi-backed campaign starts: is the provider
configured, and does its endpoint serve the requested model.

A worker model id names the backend: `claude-…` is Claude Code, `provider/model[:level]`
is Pi's own syntax and runs through tools/lab-worker-pi. The provider comes from Pi's
own configuration (`~/.pi/agent/models.json`, or PI_CODING_AGENT_DIR), never from
labloop: a fork points Pi at any OpenAI-compatible server or a hosted API the same
way it would for interactive use.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

TURN_CAP_MARKER = "lab: turn budget"        # the extension's block reason starts with this


def backend_for(model: str) -> str:
    """'pi' for provider/model ids, 'claude' otherwise."""
    return "pi" if "/" in (model or "") else "claude"


def split_model(model: str) -> tuple[str, str]:
    """('provider', 'model') from 'provider/model[:thinking]'."""
    provider, _, rest = model.partition("/")
    return provider, rest.rsplit(":", 1)[0] if ":" in rest else rest


def pi_config_dir() -> Path:
    return Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi" / "agent")


def provider_config(provider: str) -> dict | None:
    """The provider's entry in Pi's models.json, or None (a built-in provider)."""
    p = pi_config_dir() / "models.json"
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    entry = (data.get("providers") or {}).get(provider)
    return entry if isinstance(entry, dict) else None


def check_model(model: str, timeout: float = 5.0) -> dict:
    """Is `provider/model` reachable? For a provider defined in models.json with a
    baseUrl, GET <baseUrl>/models and require the id among the served ones (a llama.cpp
    server answers with its --alias, a hosted API with its catalogue). For a built-in
    provider, `pi auth check`. Never raises; the dict says what was checked."""
    provider, mid = split_model(model)
    out = {"model": model, "provider": provider, "id": mid, "ok": False, "base_url": None,
           "served": [], "context_declared": None, "context_served": None, "detail": ""}
    if not provider or not mid:
        out["detail"] = "a Pi model id is provider/model"
        return out
    cfg = provider_config(provider)
    if cfg and cfg.get("baseUrl"):
        base = str(cfg["baseUrl"]).rstrip("/")
        out["base_url"] = base
        models = [m for m in (cfg.get("models") or []) if isinstance(m, dict)]
        ids = [m.get("id") for m in models]
        mine = next((m for m in models if m.get("id") == mid), {})
        # what Pi believes the window is: it compacts against this number, so it must
        # not exceed what the server actually serves
        declared = mine.get("contextWindow") or cfg.get("contextWindow")
        out["context_declared"] = int(declared) if isinstance(declared, (int, float)) else None
        if mid not in ids:
            out["detail"] = (f"{mid} is not listed under providers.{provider}.models in "
                             f"{pi_config_dir() / 'models.json'}")
            return out
        req = urllib.request.Request(base + "/models", headers={"Accept": "application/json"})
        key = str(cfg.get("apiKey") or "")
        if key and not key.startswith(("$", "!")):
            req.add_header("Authorization", f"Bearer {key}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, OSError, ValueError) as e:
            out["detail"] = f"{base}/models: {getattr(e, 'reason', e)}"
            return out
        served = [str(m.get("id")) for m in (data.get("data") or []) if isinstance(m, dict)]
        out["served"] = served
        out["context_served"] = _served_context(base, key, timeout)
        ctx = (f"; context declared {out['context_declared'] or '?'}, "
               f"served {out['context_served'] or 'unknown (no /props)'}")
        if mid in served and out["context_declared"] and out["context_served"] \
                and out["context_declared"] > out["context_served"]:
            out["detail"] = (f"{mid} declares a {out['context_declared']}-token context in Pi's "
                             f"models.json but {base} serves {out['context_served']}: Pi would never "
                             "compact before the server refuses a request. Lower contextWindow or "
                             "start the server with a larger -c")
        elif mid in served:
            out["ok"] = True
            out["detail"] = f"{base} serves {mid}{ctx}"
        else:
            out["detail"] = (f"{base} serves {', '.join(served) or 'nothing'}, not {mid}; "
                             "start the server with that model (scripts/llm-server.sh)")
        return out
    cp = subprocess.run(["pi", "auth", "check", "--provider", provider, "--json"],
                        capture_output=True, text=True,
                        env={**os.environ, "PI_OFFLINE": "1", "PI_SKIP_VERSION_CHECK": "1"})
    out["ok"] = cp.returncode == 0
    out["detail"] = (cp.stdout or cp.stderr).strip()[:300] or f"pi auth check exit {cp.returncode}"
    return out


def _served_context(base: str, key: str, timeout: float) -> int | None:
    """llama.cpp reports the loaded window on /props (at the server root, not under /v1);
    a hosted API has no such route and the declared window is all there is."""
    root = base[:-3] if base.endswith("/v1") else base
    req = urllib.request.Request(root + "/props", headers={"Accept": "application/json"})
    if key and not key.startswith(("$", "!")):
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        n = (data.get("default_generation_settings") or {}).get("n_ctx")
        return int(n) if isinstance(n, (int, float)) and n > 0 else None
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# the stream → session.json
# ---------------------------------------------------------------------------

def _text_of(message: dict) -> str:
    return "\n".join(b.get("text", "") for b in (message.get("content") or [])
                     if isinstance(b, dict) and b.get("type") == "text").strip()


def convert(lines, model_requested: str, duration_ms: int | None = None) -> dict:
    """One result object from Pi's JSON event lines, in `claude -p` vocabulary:
    session_id, num_turns, duration_ms, is_error, subtype, result (the last assistant
    text), total_cost_usd, usage, modelUsage — plus what Pi adds: provider, model, api,
    stop_reason, error, turns_capped, backend."""
    sid = None
    turns = 0
    last_text = ""
    last_stop = None
    last_error = None
    assistant_msgs = 0
    completed = 0
    capped = False
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
             "cache_creation_input_tokens": 0}
    cost = 0.0
    by_model: dict[str, dict] = {}
    provider = api = model = None
    for line in lines:
        try:
            e = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        t = e.get("type")
        if t == "session":
            sid = e.get("id")
        elif t == "turn_end":
            turns += 1
        elif t == "message_end":
            m = e.get("message") or {}
            role = m.get("role")
            if role == "assistant":
                assistant_msgs += 1
                provider, model, api = m.get("provider"), m.get("model"), m.get("api")
                last_stop = m.get("stopReason")
                last_error = m.get("errorMessage") or None
                if last_stop not in (None, "error"):
                    completed += 1
                text = _text_of(m)
                if text:
                    last_text = text
                u = m.get("usage") or {}
                add = {"input_tokens": int(u.get("input") or 0), "output_tokens": int(u.get("output") or 0),
                       "cache_read_input_tokens": int(u.get("cacheRead") or 0),
                       "cache_creation_input_tokens": int(u.get("cacheWrite") or 0)}
                for k, v in add.items():
                    usage[k] += v
                c = float(((u.get("cost") or {}).get("total")) or 0.0)
                cost += c
                key = f"{provider}/{model}" if provider and model else model_requested
                mu = by_model.setdefault(key, {"inputTokens": 0, "outputTokens": 0,
                                               "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0,
                                               "costUSD": 0.0})
                mu["inputTokens"] += add["input_tokens"]; mu["outputTokens"] += add["output_tokens"]
                mu["cacheReadInputTokens"] += add["cache_read_input_tokens"]
                mu["cacheCreationInputTokens"] += add["cache_creation_input_tokens"]
                mu["costUSD"] += c
            elif role == "toolResult":
                if TURN_CAP_MARKER in _text_of(m):
                    capped = True
    # "started" means at least one model completion succeeded. Pi retries a failed
    # request a few times before giving up, each as its own assistant message with
    # stopReason "error", so a server that is down looks like several turns of nothing.
    ran = completed > 0
    if capped:
        subtype = "error_max_turns"
    elif last_stop == "error" or last_error:
        subtype = "error_during_execution"
    elif last_stop == "aborted":
        subtype = "error_during_execution"
    else:
        subtype = "success"
    return {
        "type": "result", "backend": "pi", "subtype": subtype,
        "is_error": subtype != "success",
        "session_id": sid, "num_turns": turns, "duration_ms": duration_ms,
        "result": last_text, "error": last_error, "stop_reason": last_stop,
        "session_started": ran, "turns_capped": capped,
        "provider": provider, "model": model, "api": api,
        "total_cost_usd": round(cost, 6), "usage": usage, "modelUsage": by_model,
    }


def main(argv: list[str]) -> int:
    """lab_pi.py convert <stream.jsonl> <model> <duration_ms> > session.json
       lab_pi.py check <provider/model>"""
    if len(argv) >= 2 and argv[0] == "convert":
        stream = Path(argv[1])
        model = argv[2] if len(argv) > 2 else ""
        dur = int(argv[3]) if len(argv) > 3 else None
        lines = stream.read_text(encoding="utf-8", errors="replace").splitlines() if stream.exists() else []
        print(json.dumps(convert(lines, model, dur), indent=1))
        return 0
    if len(argv) == 2 and argv[0] == "check":
        r = check_model(argv[1])
        print(json.dumps(r, indent=1))
        return 0 if r["ok"] else 1
    print(main.__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
