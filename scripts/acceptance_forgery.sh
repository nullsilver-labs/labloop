# acceptance_forgery.sh — sourced by acceptance.sh. No LLM involved.
#
# A worker that hands lab a score instead of predictions, and a worker that reaches for
# the labels through sudo. Runs a small campaign with the scripted worker where:
#   c0001  lab began its evaluation, wrote the record and died before saving the
#          settlement: the restart adopts lab's own record (eval_started), once;
#   c0002  its code/run.sh writes ../fitness.json with a perfect score;
#   c0003  the worker copies c0000's fitness.json into its own dir (a `cp -r` parent);
#   final  every run.sh writes a forged "final" record when it runs on the final split.
# Then: the evaluator is frozen at the start and checked before every evaluation, and
# the guard refuses sudo in a worker's commands and in the scripts it writes.
#
# Expects the helpers (ok/bad/assert_*) and $SRC from acceptance.sh.

section "I. forged scores and the frozen evaluator — scripted worker, no LLM"

WORKG="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-forgery.XXXXXX")"
PRIVG="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-forgery-private.XXXXXX")"
_saved_root="$LAB_ROOT"
cp -R "$SRC/tools" "$SRC/templates" "$SRC/.claude" "$WORKG/"
mkdir -p "$WORKG/scripts" && cp -R "$SRC/scripts/fixtures" "$WORKG/scripts/"
cp "$SRC/.lab-redact" "$SRC/.gitignore" "$SRC/FORMAT.json" "$WORKG/"
cd "$WORKG" || return 1
export LAB_ROOT="$WORKG"
export LAB_PRIVATE="$PRIVG"
export LAB_WATCH_POLL_SEC=1
unset ANTHROPIC_API_KEY FAIL_ON FINDING_BAD
git init -q . && git add -A && git -c user.email=a@b -c user.name=t commit -qm init
LABG="$WORKG/tools/lab"
python3 scripts/fixtures/campaign/make_data.py "$WORKG" "$PRIVG"
cp scripts/fixtures/campaign/eval_mse.py eval_mse.py     # its own copy: this section changes it

cat > campaign.toml <<'EOF'
[campaign]
id   = "acc-forgery"
task = "scripts/fixtures/campaign/task.md"

[data]
train     = "data/train"
evaluator = "eval_mse.py"
baseline  = "bash scripts/fixtures/campaign/baseline.sh"
[data.search]
inputs = "data/search"
labels = "$LAB_PRIVATE/search"
[data.final]
inputs = "data/final"
labels = "$LAB_PRIVATE/final"

[resources]
gpus = []
max_parallel_jobs = 1
job_wall_clock = "2m"

[worker]
command = "bash scripts/fixtures/campaign/worker.sh"

[selection]
temperature = 0.01
crossover_p = 0.0
max_debug_retries = 0
seed = 7

[stop]
max_candidates = 6

[report]
success_threshold = -1.0
higher_is_better = true
EOF

pjg() { python3 -c "import json;p=json.load(open('population.json'));c=p['candidates'];print($1)"; }
wait_jobs() {
  for _ in $(seq 1 60); do
    [ "$(python3 -c "import json,glob;print(all(json.load(open(p))['status']!='running' for p in glob.glob('.lab/watch/*.json')))")" = True ] && return 0
    sleep 1
  done
}
export FORGE_FITNESS="c0002=run c0003=copy" FORGE_FINAL=1

assert_ok   "forgery campaign: first tick launches the baseline" "$LABG" run --once --poll-sec 1
assert_eq   "the evaluator's sha256 is frozen into population.json at the start" \
  "$(pjg "p['evaluator_sha256']")" "$(sha256sum eval_mse.py | cut -d' ' -f1)"
wait_jobs
assert_ok   "second tick settles the baseline and launches the draft" "$LABG" run --once --poll-sec 1
wait_jobs

# --- lab's own record survives a crash between evaluate() and the saved settlement ---
python3 - <<'PY'
import json
p = json.load(open("population.json"))
assert p["candidates"]["c0001"]["status"] == "running", p["candidates"]["c0001"]["status"]
p["candidates"]["c0001"]["eval_started"] = "2026-01-01T00:00:00Z"   # settle got this far, then died
json.dump(p, open("population.json", "w"), indent=2)
PY
assert_ok   "lab writes c0001's search record, as the crashed settle had"  "$LABG" eval candidates/c0001
fitc1=$(sha256sum candidates/c0001/fitness.json)
assert_ok   "the restarted loop settles c0001"                  "$LABG" run --once --poll-sec 1
assert_eq   "a record lab wrote before the crash is adopted, not quarantined" \
  "$(pjg "(c['c0001']['exec'], c['c0001']['fitness'] == json.load(open('candidates/c0001/fitness.json'))['search']['score'])")" \
  "('completed', True)"
assert_eq   "and it is not rewritten"                           "$(sha256sum candidates/c0001/fitness.json)" "$fitc1"
[ ! -e candidates/c0001/fitness.worker.json ] && ok "nothing of c0001 was quarantined" || bad "c0001 has a fitness.worker.json"

# --- run to completion: two forged search scores, one forged final read ----------------
assert_ok   "the forgery campaign runs to completion"           timeout 300 "$LABG" run --poll-sec 1
assert_eq   "it finished on max_candidates" "$(pjg "(p['status'], p['stop_reason'])")" "('finished', 'max_candidates 6 reached')"
for _c in c0002 c0003; do
  assert_eq   "$_c: a fitness.json lab did not write makes the candidate invalid" \
    "$(pjg "(c['$_c']['status'], c['$_c']['exec'], c['$_c']['fitness'], 'quarantined as fitness.worker.json' in c['$_c']['fail_reason'])")" \
    "('failed', 'invalid', None, True)"
  assert_file "$_c: the worker's file is kept as evidence"      "candidates/$_c/fitness.worker.json"
  [ ! -e "candidates/$_c/fitness.json" ] && ok "$_c: no fitness.json is left to adopt" || bad "$_c still has a fitness.json"
  assert_grep "$_c: LEDGER carries the reason"                  "a fitness.json lab did not write" LEDGER.md
done
assert_grep "c0002: the quarantined file is the one its run.sh wrote" '"evaluator_sha256": "forged"' candidates/c0002/fitness.worker.json
assert_ok   "c0003: the quarantined file is c0000's record, byte for byte" cmp -s candidates/c0003/fitness.worker.json candidates/c0000/fitness.json
assert_eq   "neither forged candidate is the best"              "$(pjg "p['best'] not in ('c0002', 'c0003') and p['best'] != 'c0000'")" True
BESTG=$(pjg "p['best']")
assert_eq   "the final run's forged record was not read as the final score" \
  "$(pjg "(p['claim'], p['final']['score'], 'changed fitness.json' in (p['final'].get('error') or ''))")" \
  "('inconclusive', None, True)"
assert_grep "the frozen candidate's forged final record is kept as evidence" '"final"' "candidates/$BESTG/fitness.worker.json"
assert_eq   "lab's search record is restored, with no final key" \
  "$(pjg "(sorted(json.load(open('candidates/$BESTG/fitness.json'))), json.load(open('candidates/$BESTG/fitness.json'))['search']['score'] == c['$BESTG']['fitness'])")" \
  "(['search'], True)"
assert_nogrep "no fitness.json anywhere holds a forged record"  "forged" <(cat candidates/*/fitness.json)
assert_ok   "lab validate accepts the population"               "$LABG" validate
assert_grep "REPORT records the frozen evaluator"               "| evaluator sha256 | \`$(sha256sum eval_mse.py | cut -c1-16)\`" REPORT.md
assert_grep "REPORT says why the claim is inconclusive"         "changed fitness.json" REPORT.md

# --- the evaluator is checked before every evaluation ---------------------------------
echo "# changed after the start" >> eval_mse.py
assert_fail "an evaluator changed since the start is refused"   "$LABG" eval candidates/c0002
assert_ok   "and the refusal says so" bash -c '"$0" eval candidates/c0002 2>&1 | grep -q "changed since the campaign started"' "$LABG"
[ ! -e candidates/c0002/fitness.json ] && ok "no record is written by a changed evaluator" || bad "a changed evaluator wrote candidates/c0002/fitness.json"
git checkout -q eval_mse.py 2>/dev/null || cp scripts/fixtures/campaign/eval_mse.py eval_mse.py
{ cat campaign.toml; printf '\n[eval]\nuser = "labeval-acceptance"\n'; } > evaluser.toml
assert_ok   "campaign check warns when an eval user's evaluator is not root-owned" \
            bash -c '"$0" campaign check evaluser.toml 2>&1 | grep -q "not root-owned"' "$LABG"
rm -f evaluser.toml
unset FORGE_FITNESS FORGE_FINAL

# --- sudo: a worker never changes user ---------------------------------------------------
hook_g() { printf '{"tool_name":"Bash","tool_input":{"command":%s}}' "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1")" \
  | LAB_ROLE=worker LAB_CANDIDATE_DIR="$WORKG/candidates/c0004" bash .claude/hooks/guard.sh; }
hook_gw() { python3 -c 'import json,sys;print(json.dumps({"tool_name":"Write","tool_input":{"file_path":sys.argv[1],"content":sys.argv[2]}}))' "$1" "$2" \
  | LAB_ROLE=worker LAB_CANDIDATE_DIR="$WORKG/candidates/c0004" bash .claude/hooks/guard.sh; }
for _cmd in \
  "sudo -n -u labeval python3 -c 'print(1)'" \
  "ls && sudo -n -u labeval cat /srv/x" \
  "env FOO=1 /usr/bin/sudo -n true" \
  "timeout 5 sudo -l" \
  "python3 -c \"import subprocess; subprocess.run(['sudo', '-n', '-u', 'labeval', 'true'])\"" \
  "cat > candidates/c0004/code/run.sh <<'EOF'
#!/usr/bin/env bash
sudo -n -u labeval /usr/bin/python3 -c 'import os; print(os.listdir(\"/srv\"))'
EOF"
do
  assert_fail "guard: a worker may not: ${_cmd%%$'\n'*}" hook_g "$_cmd"
done
assert_fail "guard: the Write tool may not put sudo into a worker's run.sh" \
            hook_gw "$WORKG/candidates/c0004/code/run.sh" $'#!/usr/bin/env bash\nsudo -n -u labeval true\n'
assert_ok   "guard: prose that mentions sudo is fine"           hook_g "echo 'no sudo was used' >> candidates/c0004/summary.md"
assert_ok   "guard: a worker's ordinary run.sh is fine"         hook_gw "$WORKG/candidates/c0004/code/run.sh" $'#!/usr/bin/env bash\npython3 train.py\n'
assert_ok   "guard: an operator session may still use sudo"     bash -c 'printf "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"sudo -n true\"}}" | env -u LAB_ROLE bash .claude/hooks/guard.sh'

cd "$WORK" || return 1
export LAB_ROOT="$_saved_root"
unset LAB_PRIVATE LAB_WATCH_POLL_SEC
if [ "${KEEP:-0}" = "1" ]; then echo "kept: $WORKG $PRIVG"; else rm -rf "$WORKG" "$PRIVG"; fi
