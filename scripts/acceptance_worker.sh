# acceptance_worker.sh — sourced by acceptance_campaign.sh. No LLM involved.
#
# Exercises tools/lab-worker (M1's one-session-per-job wrapper) with a fake `claude`
# on PATH: a working session meets the contract and the candidate is evaluated; a
# session that does nothing yields an invalid candidate that is kept, with a
# mechanical summary; a paid-route credential refuses to start. Each campaign gets
# its own throwaway repo so no evidence is ever moved.
#
# Expects: helpers from acceptance.sh, $SRC, $PRIV2 (labels), $WORK2/campaign.toml.

section "D. lab-worker — one headless session per job (fake claude, no LLM)"

_saved_path="$PATH"
export PATH="$SRC/scripts/fixtures/campaign/fake-claude:$PATH"
unset FAIL_ON

worker_repo() {   # worker_repo <dir> <campaign-id> — a fresh repo with the toy task
  cp -R "$SRC/tools" "$SRC/templates" "$SRC/.claude" "$1/"
  mkdir -p "$1/scripts" && cp -R "$SRC/scripts/fixtures" "$1/scripts/"
  cp "$SRC/.lab-redact" "$SRC/.gitignore" "$1/"
  ( cd "$1" && git init -q . && git add -A && git -c user.email=a@b -c user.name=t commit -qm init )
  python3 "$SRC/scripts/fixtures/campaign/make_data.py" "$1" "$PRIV2"
  sed -e 's#^command = .*#command = "tools/lab-worker"#' -e 's/max_candidates = 9/max_candidates = 3/' \
      -e "s/id   = \"acc-quadratic\"/id   = \"$2\"/" "$WORK2/campaign.toml" > "$1/campaign.toml"
}

WORK3="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-worker.XXXXXX")"
worker_repo "$WORK3" acc-worker
cd "$WORK3" || return 1
export LAB_ROOT="$WORK3"
LAB3="$WORK3/tools/lab"

assert_fail "lab-worker refuses to run outside lab run"        "$WORK3/tools/lab-worker"
assert_fail "lab-worker refuses a paid route" \
            env LAB_CANDIDATE_DIR=/nonexistent LAB_JOB=x LAB_PREDICTIONS_OUT=y ANTHROPIC_API_KEY=sk-ant-x "$WORK3/tools/lab-worker"
assert_ok   "campaign with lab-worker runs to completion"      timeout 300 "$LAB3" run --poll-sec 1
assert_file "the worker stored the session result as provenance" candidates/c0001/session.json
assert_grep "session result carries the requested model"      '"claude-sonnet-5"' candidates/c0001/session.json
assert_ok   "the worker logged its contract check" \
            bash -c 'grep -q "contract met" .lab/watch/*job-c0001*.log'
assert_eq   "candidates driven by the fake claude were evaluated" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(sorted(set(c['status'] for c in p['candidates'].values() if c['operator']!='baseline')))")" "['evaluated', 'frozen']"
assert_nogrep "the job card never mentions the labels location" "$PRIV2" candidates/c0001/job.json
assert_grep "the job card tells the worker what it may write"  '"may_write": "candidates/c0001"' candidates/c0001/job.json

WORK4="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-lazy.XXXXXX")"
worker_repo "$WORK4" acc-lazy
cd "$WORK4" || return 1
export LAB_ROOT="$WORK4"
LAB4="$WORK4/tools/lab"
assert_ok   "campaign with a do-nothing session runs to completion" \
            env FAKE_CLAUDE_MODE=lazy timeout 300 "$LAB4" run --poll-sec 1
assert_eq   "do-nothing sessions become invalid candidates, kept" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(sorted(set(c['exec'] for c in p['candidates'].values() if c['operator']!='baseline')))")" "['invalid']"
assert_grep "the mechanical summary carries the session text"  "did nothing" candidates/c0001/summary.md
assert_eq   "the baseline is frozen and the claim reads against it" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(p['best'], p['claim'])")" "c0000 not_supported"

WORK5="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-crash.XXXXXX")"
worker_repo "$WORK5" acc-crash
cd "$WORK5" || return 1
export LAB_ROOT="$WORK5"
LAB5="$WORK5/tools/lab"
assert_ok   "campaign whose sessions fail to launch runs to completion" \
            env FAKE_CLAUDE_MODE=crash timeout 300 "$LAB5" run --poll-sec 1
assert_eq   "launch failures are failed candidates with exit code 3" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(sorted(set((c['exec'],c['exit_code']) for c in p['candidates'].values() if c['operator']!='baseline')))")" "[('failed', 3)]"
assert_eq   "each failed draft got exactly one debug attempt, then the loop moved on" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(len([c for c in p['candidates'].values() if c['operator']=='debug']))")" "1"

# shellcheck source=scripts/acceptance_usage.sh
. "$SRC/scripts/acceptance_usage.sh"

export PATH="$_saved_path"
[ "${KEEP:-0}" = "1" ] || rm -rf "$WORK3" "$WORK4" "$WORK5"
