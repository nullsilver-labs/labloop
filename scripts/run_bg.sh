#!/usr/bin/env bash
# run_bg.sh — launch an experiment in a detached tmux session (background run).
#
# Why this exists: pi's bash tool is synchronous (no background bash), so a naked
# `python experiments/expNN.py` would block the whole agent session until it finishes.
# This wraps the command in a detached tmux session so the run survives, tees console
# output per the AGENTS.md §2c contract, and registers the job so mon.sh / watchdog.sh
# can track and budget-enforce it. Works identically under pi and Claude Code.
#
# Usage:
#   scripts/run_bg.sh <expid> <tag> -- <command...>
# Example:
#   scripts/run_bg.sh exp03 lr3e4 -- python experiments/exp03_decodability.py --lr 3e-4
#
# Env / options:
#   RUN_BUDGET_SEC   per-run wall-clock budget in seconds (default 10800 = 3 h,
#                    matching CONSTRAINTS.md). The watchdog kills runs past this.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$#" -lt 4 ] || [ "$3" != "--" ]; then
  echo "usage: scripts/run_bg.sh <expid> <tag> -- <command...>" >&2
  exit 2
fi

EXPID=$1; TAG=$2; shift 3   # drop expid, tag, and the "--"
CMD=("$@")
BUDGET_SEC=${RUN_BUDGET_SEC:-10800}

JOBDIR=logs/.jobs
mkdir -p "$JOBDIR"
# Collision-proof session name (two launches the same second must not clash).
SESSION="labloop-${EXPID}-${TAG}-$(date +%H%M%S)-$RANDOM"
LOG="logs/console_${EXPID}_${TAG}.log"

# Parallel runs are fine, but two LIVE runs with the same <expid>/<tag> would
# interleave in one console log — warn so the agent picks a distinct tag.
if tmux ls -F '#S' 2>/dev/null | grep -q "^labloop-${EXPID}-${TAG}-"; then
  echo "warning: a live run of ${EXPID}/${TAG} already exists — output will interleave in $LOG; prefer a distinct tag" >&2
fi
START_EPOCH=$(date +%s)

# Persist the job record for mon.sh / watchdog.sh (dependency-free: a sourceable env file).
REG="$JOBDIR/$SESSION.env"
{
  printf 'SESSION=%q\n' "$SESSION"
  printf 'EXPID=%q\n'   "$EXPID"
  printf 'TAG=%q\n'     "$TAG"
  printf 'CMD=%q\n'     "${CMD[*]}"
  printf 'LOG=%q\n'     "$LOG"
  printf 'START_EPOCH=%q\n' "$START_EPOCH"
  printf 'BUDGET_SEC=%q\n'  "$BUDGET_SEC"
} > "$REG"

# Launch detached. tee -a honours the per-<expid>_<tag> console-log contract; the exit
# code is recorded so mon.sh can distinguish a clean finish from a crash/kill.
QUOTED=$(printf '%q ' "${CMD[@]}")
tmux new-session -d -s "$SESSION" bash -lc "
  set -o pipefail
  echo \"[run_bg] $(date -u +'%Y-%m-%d %H:%M:%SZ') start :: $SESSION :: ${QUOTED}\" | tee -a '$LOG'
  { ${QUOTED}; } 2>&1 | tee -a '$LOG'
  code=\${PIPESTATUS[0]}
  echo \"[run_bg] $(date -u +'%Y-%m-%d %H:%M:%SZ') exit=\$code :: $SESSION\" | tee -a '$LOG'
  echo \"\$code\" > '$JOBDIR/$SESSION.exit'
"

echo "launched  session=$SESSION"
echo "console   $LOG"
echo "budget    ${BUDGET_SEC}s (~$((BUDGET_SEC/60)) min)"
echo "attach    tmux attach -t $SESSION      # Ctrl-b d to detach"
echo "monitor   scripts/mon.sh"
