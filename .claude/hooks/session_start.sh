#!/usr/bin/env bash
# SessionStart hook — records the session for `lab usage` and briefs it.
# stdout of a SessionStart hook is added to the session context, so the agent never
# has to remember a reading order: what it must know to act is printed here.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT" || exit 0
LAB="$ROOT/tools/lab"

input=$(cat 2>/dev/null || echo '{}')
# transcript_path prints last: `read` folds any remaining words into its final var.
read -r sid transcript <<<"$(printf '%s' "$input" | python3 -c \
  'import json,sys;d=json.load(sys.stdin);print(d.get("session_id","unknown"),
   d.get("transcript_path",""))' 2>/dev/null || echo "unknown ")"

# Two kinds of session. A WORKER is launched by `lab run` (via tools/lab-worker) with
# LAB_ROLE=worker and is briefed by its job card. Anything else is an OPERATOR: a
# human (or an agent the human is driving) working in the repo. Both are recorded
# under .lab/sessions/ so `lab usage` can account for their tokens; neither emits
# events by itself — the feed is written by `lab run`.
role="${LAB_ROLE:-operator}"
mkdir -p .lab/sessions
python3 - "$sid" "$role" "${transcript:-}" "${LAB_CANDIDATE_DIR:-}" <<'PY' 2>/dev/null
import json, os, sys, time
sid, role, transcript, cdir = sys.argv[1:5]
json.dump({"session_id": sid, "start_epoch": time.time(), "role": role,
           "candidate_dir": cdir or None, "transcript_path": transcript},
          open(os.path.join(".lab", "sessions", f"{sid}.json"), "w"))
PY

if [ "$role" = "worker" ]; then
  cat <<EOF
## Lab — you are a campaign WORKER (one job, one session)

Your whole brief is the job card in your prompt: operator, task, contract, parents.
You may write only inside \`${LAB_CANDIDATE_DIR:-your candidate dir}\`. Fitness comes from
\`lab eval\`, never from you; you never look for labels. Run code/run.sh synchronously
in the foreground with a bounded Bash timeout inside the remaining job budget. No
run_in_background, shell &, nohup, setsid or nested lab watch: your job already has
a watcher. Wait for exit, check the exit code and out/predictions-search.json, then
write summary.md and stop. Ending the session kills pending work; it is not a handoff.
If you cannot finish within
your turn budget, write summary.md saying what you learned and stop.
EOF
  exit 0
fi

echo "## Lab — OPERATOR session (interactive; the campaign loop runs on its own)"
echo
if [ -f population.json ]; then
  echo "A campaign has run here. \`tools/lab campaign status\` and \`tools/lab campaign usage\`"
  echo "show it; \`lab run\` is the only writer of population.json, LEDGER.md and events.jsonl."
  echo "Candidate dirs, LEDGER rows and events are evidence: never edit or delete them."
  echo
  echo '```'
  "$LAB" campaign status 2>/dev/null | head -20 || echo "(status unavailable)"
  echo '```'
elif [ -f campaign.toml ]; then
  echo "campaign.toml exists and no campaign has run yet. \`tools/lab campaign check\`"
  echo "validates it; \`tools/lab run campaign.toml\` (under \`lab watch\`) starts the search."
  echo "See docs/campaign-setup.md."
else
  echo "No campaign here yet. \`tools/lab campaign init <id>\` scaffolds one; the human writes"
  echo "campaign.toml, the task statement, the evaluator and the baseline (docs/campaign-setup.md)."
fi
echo
echo "Judgment rules are in CLAUDE.md. You emit no events and you do not touch a running"
echo "campaign's files; \`tools/lab campaign stop\` is how a campaign is ended by hand."
exit 0
