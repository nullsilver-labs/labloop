#!/usr/bin/env bash
# loop.sh — the unattended driver for the phase state machine.
#
# Not an agent: it reads state.json, launches one fresh Claude Code session per
# phase (context reset by construction), and stops when the lab needs a human.
# Interchangeable with attended mode (`/orchestrate`) — both drive the same state
# machine through the same `lab` CLI, so you can switch at any gate.
#
#   ./loop.sh                      run until a gate, conclusion, or the iteration cap
#   ./loop.sh --max-iterations 5   stop after 5 phase sessions
#   ./loop.sh --dry-run            print what it would launch, launch nothing
#
# Exit codes: 0 = stopped cleanly (gate / concluded / cap), 1 = the repo or the
# environment is broken, 2 = repeated session failures.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1
LAB="$ROOT/tools/lab"
CONF="$ROOT/.claude/loop.conf"

MAX_ITERATIONS=""
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --max-iterations) MAX_ITERATIONS="${2:-}"; shift 2 ;;
    --dry-run)        DRY_RUN=1; shift ;;
    -h|--help)        sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "loop.sh: unknown argument '$1'" >&2; exit 1 ;;
  esac
done

command -v claude >/dev/null 2>&1 || { echo "loop.sh: 'claude' is not on PATH" >&2; exit 1; }
[ -f "$CONF" ] || { echo "loop.sh: $CONF not found" >&2; exit 1; }

conf() { "$LAB" conf "$1"; }

PERMISSION_MODE="$(conf permission_mode)"
MAX_ITERATIONS="${MAX_ITERATIONS:-$(conf max_iterations)}"
MAX_ITERATIONS="${MAX_ITERATIONS:-50}"
BACKOFF="$(conf backoff_sec)"; BACKOFF="${BACKOFF:-30}"
MAX_FAILURES="$(conf max_failures)"; MAX_FAILURES="${MAX_FAILURES:-3}"
MAX_NO_PROGRESS="$(conf max_no_progress)"; MAX_NO_PROGRESS="${MAX_NO_PROGRESS:-2}"
PUSH="$(conf push)"; PUSH="${PUSH:-false}"

case "$PERMISSION_MODE" in
  auto|bypassPermissions) ;;
  *) echo "loop.sh: permission_mode must be auto|bypassPermissions (got '$PERMISSION_MODE')" >&2
     exit 1 ;;
esac
if [ "$PERMISSION_MODE" = "bypassPermissions" ]; then
  echo "loop.sh: WARNING — bypassPermissions. Only safe in an isolated container/VM"
  echo "         without credentials, never as root. (.claude/loop.conf)"
fi

mkdir -p .lab/sessions

log() { printf '[loop %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# Fingerprint of "has anything moved": phase, run, revision, gate state.
snapshot() {
  "$LAB" state get 2>/dev/null | python3 -c \
    'import json,sys;d=json.load(sys.stdin);print(d.get("phase"),d.get("run"),
     d.get("revision"),d.get("status"),(d.get("awaiting") or {}).get("since"))' 2>/dev/null
}

iteration=0
failures=0
no_progress=0

while :; do
  if [ "$iteration" -ge "$MAX_ITERATIONS" ]; then
    log "reached --max-iterations $MAX_ITERATIONS; stopping"
    exit 0
  fi

  if ! validate_out=$("$LAB" validate 2>&1); then
    echo "$validate_out" >&2
    log "lab validate failed — the repo is not in a runnable state. Fix it, then rerun."
    exit 1
  fi

  status="$("$LAB" state get status)"
  phase="$("$LAB" state get phase)"
  run="$("$LAB" state get run)"

  case "$status" in
    concluded)
      log "project concluded. See REPORT.md and CLAIMS.md."
      exit 0 ;;
    awaiting_gate)
      question="$("$LAB" state get awaiting | python3 -c \
        'import json,sys;print(json.load(sys.stdin).get("question",""))' 2>/dev/null)"
      log "waiting for human: $question"
      log "answer with: tools/lab gate resolve --approve|--reject --note \"...\"  then rerun ./loop.sh"
      exit 0 ;;
  esac

  model="$(conf "$phase")"
  if [ -z "$model" ]; then
    log "no model configured for phase '$phase' in .claude/loop.conf"
    exit 1
  fi

  prompt_file=".claude/prompts/${phase}.md"
  [ -f "$prompt_file" ] || { log "missing $prompt_file"; exit 1; }

  before="$(snapshot)"
  iteration=$((iteration + 1))
  session_log=".lab/sessions/$(date -u +%Y%m%dT%H%M%S)-${phase}.log"
  log "iteration $iteration: phase=$phase run=$run model=$model -> $session_log"

  if [ "$DRY_RUN" = "1" ]; then
    log "dry run: would launch claude -p \"\$(cat $prompt_file)\" --model $model --permission-mode $PERMISSION_MODE"
    exit 0
  fi

  # LAB_MODEL travels with the session so `lab` can record which model produced
  # each event and each trial. loop.conf is current config; this is the record.
  export LAB_MODEL="$model"

  # </dev/null: headless sessions otherwise wait on stdin before starting.
  claude -p "$(cat "$prompt_file")" \
      --model "$model" \
      --permission-mode "$PERMISSION_MODE" \
      --output-format stream-json --verbose \
      >"$session_log" 2>&1 </dev/null
  rc=$?

  if [ $rc -ne 0 ]; then
    failures=$((failures + 1))
    "$LAB" log error --msg "phase $phase session failed (exit $rc), attempt $failures" \
      --data "{\"phase\":\"$phase\",\"exit_code\":$rc,\"log\":\"$session_log\"}" >/dev/null 2>&1
    if [ "$failures" -ge "$MAX_FAILURES" ]; then
      log "$failures consecutive session failures; giving up. Last log: $session_log"
      exit 2
    fi
    log "session failed (exit $rc); backing off ${BACKOFF}s. Log: $session_log"
    sleep "$BACKOFF"
    BACKOFF=$((BACKOFF * 2))
    [ "$BACKOFF" -gt 600 ] && BACKOFF=600
    continue
  fi
  failures=0

  after="$(snapshot)"
  if [ "$before" = "$after" ]; then
    no_progress=$((no_progress + 1))
    log "session made no progress ($no_progress/$MAX_NO_PROGRESS)"
    if [ "$no_progress" -ge "$MAX_NO_PROGRESS" ]; then
      "$LAB" gate request --type stalled \
        --question "phase $phase made no progress in $no_progress sessions; last log: $session_log" \
        >/dev/null 2>&1
      log "raised a stalled gate; stopping. Inspect $session_log, then resolve and rerun."
      exit 0
    fi
  else
    no_progress=0
    log "state: $after"
    if [ "$PUSH" = "true" ] && git rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1; then
      git push --quiet && log "pushed" || log "push failed (continuing; git is the source of truth)"
    fi
  fi
done
