#!/usr/bin/env bash
# SessionStart hook — emits session.start and injects the state block into context.
# The agent never has to remember a reading order: everything it must know to act
# is printed here (stdout of a SessionStart hook is added to the session context).
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT" || exit 0
LAB="$ROOT/tools/lab"

input=$(cat 2>/dev/null || echo '{}')
# transcript_path prints last: `read` folds any remaining words into its final var.
read -r sid transcript <<<"$(printf '%s' "$input" | python3 -c \
  'import json,sys;d=json.load(sys.stdin);print(d.get("session_id","unknown"),
   d.get("transcript_path",""))' 2>/dev/null || echo "unknown ")"

# A campaign worker (launched by `lab run` via tools/lab-worker) is briefed by its job
# card, not by the phase machine. Record the session for `lab usage` and stop here.
if [ "${LAB_ROLE:-}" = "worker" ]; then
  mkdir -p .lab/sessions
  python3 - "$sid" "worker" "${transcript:-}" "${LAB_CANDIDATE_DIR:-}" <<'PY' 2>/dev/null
import json, os, sys, time
sid, role, transcript, cdir = sys.argv[1:5]
json.dump({"session_id": sid, "start_epoch": time.time(), "phase": None, "run": None,
           "role": role, "candidate_dir": cdir, "transcript_path": transcript},
          open(os.path.join(".lab", "sessions", f"{sid}.json"), "w"))
PY
  cat <<EOF
## Lab — you are a campaign WORKER (one job, one session)

Your whole brief is the job card in your prompt: operator, task, contract, parents.
You may write only inside \`${LAB_CANDIDATE_DIR:-your candidate dir}\`. Fitness comes from
\`lab eval\`, never from you; you never look for labels. When code/run.sh has run and
out/predictions-search.json and summary.md exist, stop. If you cannot finish within
your turn budget, write summary.md saying what you learned and stop. The rest of
CLAUDE.md (phases, HANDOFF.md, gates) does not apply to you.
EOF
  exit 0
fi

if [ ! -f state.json ]; then
  cat <<'EOF'
## nullsilver lab — not initialized

This repo has no `state.json` yet. If `PROTOCOL.md` is still the template skeleton,
the human writes revision 1 first (see README.md). Once it is written, run
`tools/lab init`. Do not create state.json or events.jsonl by hand.
EOF
  exit 0
fi

phase=$("$LAB" state get phase 2>/dev/null || echo unknown)
run=$("$LAB" state get run 2>/dev/null || echo 0)
# LAB_ROLE tells the hooks what this session is. The drivers set it explicitly:
# loop.sh and the orchestrator launch phase sessions with LAB_ROLE=phase; an
# attended operator session sets LAB_ROLE=orchestrator. A session with no
# LAB_ROLE is an ad-hoc interactive one (a human working in the repo): it owes
# no handoff, emits nothing to the feed, and must not move the state machine.
role="${LAB_ROLE:-adhoc}"

mkdir -p .lab/sessions
python3 - "$sid" "$phase" "$run" "$role" "${transcript:-}" <<'PY' 2>/dev/null
import json, os, sys, time
sid, phase, run, role, transcript = sys.argv[1:6]
json.dump({"session_id": sid, "start_epoch": time.time(), "phase": phase,
           "run": run, "role": role, "transcript_path": transcript},
          open(os.path.join(".lab", "sessions", f"{sid}.json"), "w"))
PY

if [ "$role" = "orchestrator" ]; then
  echo "## Lab state — you are the ORCHESTRATOR (operator session, not a phase)"
  echo
  echo "You drive phases and relay gates. You do not do lab work, you emit no events,"
  echo "and you edit no project files. Follow \`.claude/commands/orchestrate.md\`."
  echo
  echo '```json'
  cat state.json
  echo '```'
  exit 0
fi

if [ "$role" = "adhoc" ]; then
  echo "## Lab state — AD-HOC session (interactive, not a phase)"
  echo
  echo "You were not launched by a driver, so you are not a phase session: you owe no"
  echo "handoff, you emit no events, and you do not move the state machine or write"
  echo "HANDOFF.md unless the human explicitly asks. Working on the machinery, the"
  echo "code, or answering questions is fine. To run a phase properly, use ./loop.sh"
  echo "or /orchestrate (they set LAB_ROLE=phase)."
  echo
  echo '```json'
  cat state.json
  echo '```'
  exit 0
fi

# The pointer lets `lab` find this session's transcript mid-session: that is
# where served-model provenance (fallbacks included) comes from. The requested
# model rides in as LAB_MODEL; `lab` stamps both onto events and trials itself.
printf '%s' "$sid" > .lab/session-current

"$LAB" log session.start --msg "session start in phase $phase (run $run)" >/dev/null 2>&1

echo "## Lab state (injected by the SessionStart hook — this is your reading order)"
echo
echo "### state.json"
echo '```json'
cat state.json
echo '```'
echo
echo "### Last 20 events (events.jsonl)"
echo '```jsonl'
"$LAB" events tail -n 20 2>/dev/null
echo '```'
echo
echo "### LEDGER tail"
echo '```'
tail -n 12 LEDGER.md 2>/dev/null || echo "(no LEDGER.md yet)"
echo '```'
echo
echo "### HANDOFF.md (full)"
echo '```markdown'
cat HANDOFF.md 2>/dev/null || echo "(no HANDOFF.md yet)"
echo '```'
echo
echo "Your phase prompt is \`.claude/prompts/${phase}.md\`. Judgment rules are in"
echo "CLAUDE.md. All writes to state.json and events.jsonl go through \`tools/lab\`."
echo "You cannot end this session until HANDOFF.md is updated and \`tools/lab validate\` passes."
exit 0
