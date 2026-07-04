#!/usr/bin/env bash
# mon.sh — status of background experiment runs launched via run_bg.sh.
# Tracks any number of concurrent runs.
#
# Modes:
#   scripts/mon.sh                 one-shot snapshot of all registered runs, exits
#   scripts/mon.sh --watch [min]   block up to <min> minutes (default CADENCE_MIN, 25);
#                                  return EARLY the moment ANY run changes state
#                                  (finishes, crashes, goes over budget) — immediately
#                                  if nothing is live — then print one snapshot and
#                                  exit. One bounded wait per call; the agent owns the
#                                  loop. Under pi run it in the foreground (pi has no
#                                  self-wake); under Claude Code run it as a background
#                                  task so its exit notification wakes you.
#   scripts/mon.sh --ack <session>|all
#                                  archive finished runs you've handled: moves their
#                                  records to logs/.jobs/archive/ so the snapshot and
#                                  the watch stay about current work. Refuses to ack
#                                  a live run.
#
# Env:
#   CADENCE_MIN     default interval for --watch when no minutes given (default 25)
#   WATCH_POLL_SEC  internal poll granularity for early return (default 30)
set -euo pipefail
cd "$(dirname "$0")/.."
JOBDIR=logs/.jobs

# State string for one registered job, given its .env registry file.
state_for() {
  ( SESSION= EXPID= TAG= CMD= LOG= START_EPOCH= BUDGET_SEC=
    # shellcheck disable=SC1090
    source "$1"
    now=$(date +%s); elapsed=$(( now - START_EPOCH ))
    exitf="$JOBDIR/$SESSION.exit"
    if tmux has-session -t "$SESSION" 2>/dev/null; then
      [ "$elapsed" -gt "$BUDGET_SEC" ] && echo "OVER-BUDGET" || echo "RUNNING"
    elif [ -f "$exitf" ]; then
      code=$(cat "$exitf" 2>/dev/null || echo '?')
      [ "$code" = "0" ] && echo "DONE" || echo "FAILED(exit=$code)"
    else
      echo "GONE"
    fi )
}

# Number of live (RUNNING / OVER-BUDGET) registered jobs.
active_count() {
  shopt -s nullglob
  local n=0 REG
  for REG in "$JOBDIR"/*.env; do
    case "$(state_for "$REG")" in RUNNING|OVER-BUDGET) n=$((n+1));; esac
  done
  echo "$n"
}

# Compact signature of all jobs' states — used to detect change for early return.
signature() {
  shopt -s nullglob
  local sig="" REG
  for REG in "$JOBDIR"/*.env; do
    sig+="$(basename "$REG"):$(state_for "$REG");"
  done
  echo "$sig"
}

snapshot() {
  echo "=== labloop runs @ $(date -u +'%Y-%m-%d %H:%M:%SZ') ==="
  shopt -s nullglob
  local regs=("$JOBDIR"/*.env)
  if [ ${#regs[@]} -eq 0 ]; then echo "(no registered runs)"; return; fi
  local REG st finished=0
  for REG in "${regs[@]}"; do
    st=$(state_for "$REG")
    case "$st" in RUNNING|OVER-BUDGET) ;; *) finished=$((finished+1));; esac
    ( SESSION= EXPID= TAG= CMD= LOG= START_EPOCH= BUDGET_SEC=
      # shellcheck disable=SC1090
      source "$REG"
      now=$(date +%s); elapsed=$(( now - START_EPOCH ))
      printf -- '- %-10s %-16s %s  elapsed %dm/%dm\n' \
        "$EXPID/$TAG" "$st" "$SESSION" "$((elapsed/60))" "$((BUDGET_SEC/60))"
      # Latest metric line from the newest run dir for this experiment, if any.
      jsonls=("logs/$EXPID"/*/results.jsonl)
      if [ ${#jsonls[@]} -gt 0 ]; then
        last_jsonl=$(ls -t "${jsonls[@]}" 2>/dev/null | head -1 || true)
        [ -n "$last_jsonl" ] && printf '    metric  %s\n' "$(tail -n 1 "$last_jsonl")"
      fi
      [ -f "$LOG" ] && printf '    console %s\n' "$(tail -n 1 "$LOG")"
    )
  done
  if [ "$finished" -gt 0 ]; then
    echo "($finished finished — after handling, archive with: scripts/mon.sh --ack <session>|all)"
  fi
}

case "${1:-}" in
--ack)
  TARGET=${2:-}
  if [ -z "$TARGET" ]; then
    echo "usage: scripts/mon.sh --ack <session>|all" >&2; exit 2
  fi
  mkdir -p "$JOBDIR/archive"
  shopt -s nullglob
  matched=0
  for REG in "$JOBDIR"/*.env; do
    s=$(basename "$REG" .env)
    [ "$TARGET" = "all" ] || [ "$TARGET" = "$s" ] || continue
    matched=$((matched+1))
    st=$(state_for "$REG")
    case "$st" in
      RUNNING|OVER-BUDGET)
        echo "skip  $s: still $st (wait, or kill via scripts/watchdog.sh, then ack)" ;;
      *)
        mv "$REG" "$JOBDIR/archive/"
        [ -f "$JOBDIR/$s.exit" ] && mv "$JOBDIR/$s.exit" "$JOBDIR/archive/"
        echo "acked $s ($st)" ;;
    esac
  done
  [ "$matched" -gt 0 ] || { echo "no registered run matches '$TARGET'" >&2; exit 1; }
  ;;
--watch)
  MIN=${2:-${CADENCE_MIN:-25}}
  POLL=${WATCH_POLL_SEC:-30}
  # awk keeps this correct for fractional minutes too (bash arithmetic is integer-only).
  target=$(awk "BEGIN{printf \"%d\", $MIN*60}" 2>/dev/null || echo "")
  if [ -z "$target" ] || [ "$target" -lt 1 ] 2>/dev/null; then
    echo "usage: scripts/mon.sh --watch <minutes>   (positive number)" >&2; exit 2
  fi
  if [ "$(active_count)" -eq 0 ]; then
    echo "[watch returned: nothing live]"
    snapshot
    exit 0
  fi
  base=$(signature)
  start=$(date +%s)
  reason="interval elapsed"
  while :; do
    now=$(date +%s); elapsed=$(( now - start ))
    [ "$elapsed" -ge "$target" ] && { reason="interval elapsed (${MIN}m)"; break; }
    if [ "$(signature)" != "$base" ]; then reason="state change"; break; fi
    remaining=$(( target - elapsed ))
    sleep "$(( remaining < POLL ? remaining : POLL ))"
  done
  echo "[watch returned: $reason]"
  snapshot
  ;;
*)
  snapshot
  ;;
esac
