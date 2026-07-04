#!/usr/bin/env bash
# watchdog.sh — agent-independent enforcement of the wall-clock budget.
#
# Why this exists: pi has no agent-side scheduler, so "check every 25 min and kill runs
# past 3 h" cannot rely on an agent being awake. This script is the mechanical half:
# run it from cron / a systemd timer (or by hand) and it kills any registered run past
# its budget and appends a heartbeat line the agent reads on its next turn. It makes no
# scientific judgement — it only enforces the hard wall-clock rule from CONSTRAINTS.md.
# Safe to run repeatedly (idempotent) and works under pi and Claude Code alike.
#
# Usage:
#   scripts/watchdog.sh            # one sweep; kill over-budget runs, write heartbeat
#
# Cron example (every 25 min):
#   */25 * * * * cd /path/to/labloop && scripts/watchdog.sh >> logs/.jobs/watchdog.cron.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
JOBDIR=logs/.jobs
mkdir -p "$JOBDIR"
HEARTBEAT="$JOBDIR/heartbeat.log"
STAMP=$(date -u +'%Y-%m-%d %H:%M:%SZ')

shopt -s nullglob
killed=0 running=0
for REG in "$JOBDIR"/*.env; do
  ( # subshell so sourced vars don't leak between jobs
    SESSION= EXPID= TAG= CMD= LOG= START_EPOCH= BUDGET_SEC=
    # shellcheck disable=SC1090
    source "$REG"
    tmux has-session -t "$SESSION" 2>/dev/null || exit 0   # not running: nothing to enforce
    now=$(date +%s); elapsed=$(( now - START_EPOCH ))
    if [ "$elapsed" -gt "$BUDGET_SEC" ]; then
      msg="[watchdog] $STAMP KILL $SESSION ($EXPID/$TAG) elapsed $((elapsed/60))m > budget $((BUDGET_SEC/60))m"
      echo "$msg"
      echo "$msg" >> "$HEARTBEAT"
      # Leave a trace in the run's own console log — the run dir is evidence (AGENTS.md §3).
      [ -n "${LOG:-}" ] && echo "$msg" >> "$LOG" 2>/dev/null || true
      tmux kill-session -t "$SESSION" 2>/dev/null || true
      echo "137" > "$JOBDIR/$SESSION.exit"   # SIGKILL-ish marker: killed, not clean
      exit 10
    fi
    echo "[watchdog] $STAMP ok   $SESSION ($EXPID/$TAG) elapsed $((elapsed/60))m/$((BUDGET_SEC/60))m"
    exit 11
  )
  case $? in 10) killed=$((killed+1));; 11) running=$((running+1));; esac
done

echo "[watchdog] $STAMP sweep done: $running within budget, $killed killed" >> "$HEARTBEAT"
echo "sweep done: $running within budget, $killed killed"
