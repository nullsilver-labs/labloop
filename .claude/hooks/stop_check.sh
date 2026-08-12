#!/usr/bin/env bash
# Stop hook — "never skip the handoff, even interrupted" made mechanical.
#
# Blocks the stop (exit 2) unless all three hold:
#   (a) HANDOFF.md was modified during this session,
#   (b) `lab validate` passes,
#   (c) the phase changed, or a gate was raised, or trials are still running.
#
# Claude Code sets stop_hook_active=true once it has already been blocked and
# continued. To avoid an unbreakable loop we block at most once: on a second
# attempt the stop is allowed but an `error` event records the incomplete handoff,
# so the gap is visible in the feed rather than silent.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT" || exit 0
LAB="$ROOT/tools/lab"

[ -f state.json ] || exit 0   # uninitialized template repo: nothing to hand off

input=$(cat 2>/dev/null || echo '{}')
# transcript_path prints last: `read` folds any remaining words into its final var.
read -r sid active transcript <<<"$(printf '%s' "$input" | python3 -c \
  'import json,sys;d=json.load(sys.stdin);print(d.get("session_id","unknown"),
   str(d.get("stop_hook_active", False)).lower(),
   d.get("transcript_path",""))' 2>/dev/null || echo "unknown false ")"

# The phase this session actually ran. A session ends *after* transitioning, so
# reading state.json here would attribute the end to the phase that follows it.
phase_ran=$(python3 -c \
  'import json,sys;print(json.load(open(sys.argv[1])).get("phase") or "")' \
  ".lab/sessions/${sid}.json" 2>/dev/null || echo "")

# Only phase sessions owe the handoff contract. Operator (orchestrator) and
# ad-hoc interactive sessions are exempt: the session record's role wins, the
# env is the fallback, and a missing record with no LAB_ROLE defaults to phase
# so a legacy headless launch is still held to the contract.
file_role=$(grep -o '"role": *"[a-z]*"' ".lab/sessions/${sid}.json" 2>/dev/null \
            | sed 's/.*"\([a-z]*\)"$/\1/')
role="${file_role:-${LAB_ROLE:-phase}}"
if [ "$role" != "phase" ]; then
  exit 0
fi

validate_out=$("$LAB" validate 2>&1) ; validate_rc=$?

reasons=$(python3 - "$sid" "$validate_rc" "${transcript:-}" <<'PY'
import calendar, json, os, sys, time

sid, validate_rc, transcript = sys.argv[1], int(sys.argv[2]), sys.argv[3]
sess_path = os.path.join(".lab", "sessions", f"{sid}.json")
reasons = []

try:
    sess = json.load(open(sess_path))
    start = float(sess["start_epoch"])
    phase_at_start = sess.get("phase")
except Exception:
    # SessionStart never ran (hook added mid-session): record a start now and skip
    # the handoff-mtime check this once, but keep the other two.
    os.makedirs(os.path.join(".lab", "sessions"), exist_ok=True)
    start, phase_at_start = None, None
    try:
        state = json.load(open("state.json"))
        json.dump({"session_id": sid, "start_epoch": time.time(),
                   "phase": state.get("phase"), "run": state.get("run"),
                   "transcript_path": transcript},
                  open(sess_path, "w"))
    except Exception:
        pass

# (a) handoff written this session
if start is not None:
    try:
        if os.path.getmtime("HANDOFF.md") < start:
            reasons.append("HANDOFF.md was not updated this session. Overwrite it: "
                           "Just happened (with the headline numbers inline) / State of "
                           "the run / Next phase should / Open questions / For the human.")
    except OSError:
        reasons.append("HANDOFF.md does not exist. Write it before ending the session.")

# (b) repo validates
if validate_rc != 0:
    reasons.append("`tools/lab validate` fails — fix the problems it printed "
                   "(they are on stderr above) before ending.")

# (c) something actually moved
try:
    state = json.load(open("state.json"))
except Exception:
    state = {}

progressed = False
if phase_at_start is not None and state.get("phase") != phase_at_start:
    progressed = True
if state.get("status") in ("awaiting_gate", "concluded"):
    progressed = True
if state.get("active_trials"):
    progressed = True
if start is not None and not progressed:
    try:
        with open("events.jsonl") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") in ("gate.requested", "protocol.revised"):
                    ts = calendar.timegm(time.strptime(ev["ts"], "%Y-%m-%dT%H:%M:%SZ"))
                    if ts >= start - 5:
                        progressed = True
                        break
    except OSError:
        pass
elif start is None:
    progressed = True   # cannot tell; do not block on this criterion alone

if not progressed:
    reasons.append("nothing moved this session: the phase did not change, no gate was "
                   "raised, and no trials are running. End with `tools/lab state set "
                   "phase=<next>`, or `tools/lab gate request` if you are blocked.")

print("\n".join(f"- {r}" for r in reasons))
PY
)

if [ -n "$reasons" ]; then
  if [ "$active" = "true" ]; then
    "$LAB" log error --msg "session ended with an incomplete handoff" \
      --data "{\"reasons\":$(printf '%s' "$reasons" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')}" >/dev/null 2>&1
    rm -f .lab/session-current   # the session is over; a stale pointer would misattribute
    echo "Stop allowed (already blocked once), but the handoff is incomplete — logged." >&2
    exit 0
  fi
  {
    echo "This session cannot end yet:"
    echo "$reasons"
    if [ $validate_rc -ne 0 ]; then
      echo
      echo "lab validate said:"
      echo "$validate_out"
    fi
  } >&2
  exit 2
fi

# session.end is where served-model provenance lands: `lab` reads the session's
# transcript through the pointer and stamps requested + served onto the event.
# Ensure the pointer exists (SessionStart may have been added mid-session), emit,
# then clear it — the transcript stops being "the live session" the moment we exit.
printf '%s' "$sid" > .lab/session-current
"$LAB" log session.end --msg "session end in phase ${phase_ran:-$("$LAB" state get phase)}" \
  --data "{\"phase_ran\":\"${phase_ran}\"}" >/dev/null 2>&1
rm -f .lab/session-current
exit 0
