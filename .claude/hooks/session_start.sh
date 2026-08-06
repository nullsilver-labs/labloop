#!/usr/bin/env bash
# SessionStart hook — emits session.start and injects the state block into context.
# The agent never has to remember a reading order: everything it must know to act
# is printed here (stdout of a SessionStart hook is added to the session context).
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT" || exit 0
LAB="$ROOT/tools/lab"

input=$(cat 2>/dev/null || echo '{}')
sid=$(printf '%s' "$input" | python3 -c \
  'import json,sys;print(json.load(sys.stdin).get("session_id","unknown"))' 2>/dev/null || echo unknown)

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

mkdir -p .lab/sessions
python3 - "$sid" "$phase" "$run" <<'PY' 2>/dev/null
import json, os, sys, time
sid, phase, run = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({"session_id": sid, "start_epoch": time.time(), "phase": phase, "run": run},
          open(os.path.join(".lab", "sessions", f"{sid}.json"), "w"))
PY

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
