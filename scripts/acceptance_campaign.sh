# acceptance_campaign.sh — sourced by acceptance.sh. No LLM involved.
#
# Drives the phaseless loop (`lab run`, NEXT.md M0) end to end on a toy task with a
# scripted worker: baseline → draft → a simulated crash → debug → improve … → stop →
# freeze → one final-split read → REPORT.md. Asserts the plumbing NEXT.md insists on:
# labels never reach a worker, fitness is written only by lab, measurements are
# idempotent across restarts, failed candidates are kept, the final split is read once,
# the auth preflight refuses a paid route, and evidence is immutable.
#
# Expects the helpers (ok/bad/assert_*) and $SRC from acceptance.sh.

section "C. The campaign loop (lab run) — scripted worker, no LLM"

WORK2="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-campaign.XXXXXX")"
PRIV2="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-private.XXXXXX")"
cleanup_campaign() { if [ "${KEEP:-0}" = "1" ]; then echo "kept: $WORK2 $PRIV2"; else rm -rf "$WORK2" "$PRIV2"; fi; }
_saved_root="$LAB_ROOT"
cp -R "$SRC/tools" "$SRC/templates" "$SRC/.claude" "$WORK2/"
mkdir -p "$WORK2/scripts" && cp -R "$SRC/scripts/fixtures" "$WORK2/scripts/"
cp "$SRC/.lab-redact" "$SRC/.gitignore" "$WORK2/"
cd "$WORK2" || return 1
export LAB_ROOT="$WORK2"
export LAB_PRIVATE="$PRIV2"
export LAB_WATCH_POLL_SEC=1
unset ANTHROPIC_API_KEY FAIL_ON
git init -q . && git add -A && git -c user.email=a@b -c user.name=t commit -qm init
LAB2="$WORK2/tools/lab"
python3 scripts/fixtures/campaign/make_data.py "$WORK2" "$PRIV2"

cat > campaign.toml <<'EOF'
[campaign]
id   = "acc-quadratic"
task = "scripts/fixtures/campaign/task.md"

[data]
train     = "data/train"
evaluator = "scripts/fixtures/campaign/eval_mse.py"
baseline  = "bash scripts/fixtures/campaign/baseline.sh"
[data.search]
inputs = "data/search"
labels = "$LAB_PRIVATE/search"
[data.final]
inputs = "data/final"
labels = "$LAB_PRIVATE/final"

[resources]
gpus = []
max_parallel_jobs = 2
job_wall_clock = "2m"

[worker]
command = "bash scripts/fixtures/campaign/worker.sh"

[selection]
temperature = 0.01
crossover_p = 0.0
max_debug_retries = 1
seed = 7

[stop]
max_candidates = 9

[report]
success_threshold = -1.0
higher_is_better = true
EOF

assert_ok   "campaign check accepts the toy campaign"          "$LAB2" campaign check campaign.toml
sed '/success_threshold/d' campaign.toml > broken.toml
assert_fail "campaign check refuses a campaign without a pre-fixed threshold" "$LAB2" campaign check broken.toml
assert_fail "auth preflight refuses to start with an API key in the environment" \
            env ANTHROPIC_API_KEY=sk-ant-test123 "$LAB2" run --once --poll-sec 1
[ ! -e population.json ] && ok "and creates no population" || bad "population.json created despite refusal"
export FAIL_ON=c0002    # the fixture worker crashes in this candidate, whenever it is dispatched

# --- one tick: the baseline is dispatched under a watcher ---------------------
assert_ok   "first tick starts the campaign and launches the baseline" "$LAB2" run --once --poll-sec 1
assert_file "population.json exists"                          population.json
assert_grep "campaign.start is in the feed"                   '"type":"campaign.start"' events.jsonl
assert_grep "candidate.launch for c0000"                      '"candidate":"c0000"' events.jsonl
assert_eq   "c0000 is the baseline" "$(python3 -c "import json;print(json.load(open('population.json'))['candidates']['c0000']['operator'])")" baseline
assert_file "c0000 has provenance"                            candidates/c0000/config.json
assert_file "c0000 has a job card"                            candidates/c0000/job.json
assert_grep "LEDGER has a running row for c0000"              "| c0000 | running |" LEDGER.md
assert_fail "campaign.toml cannot change under a running campaign" \
            bash -c 'sed -i "s/max_candidates = 9/max_candidates = 10/" campaign.toml && "$0" run --once --poll-sec 1' "$LAB2"
sed -i "s/max_candidates = 10/max_candidates = 9/" campaign.toml

# --- wait for the baseline; settle it twice; nothing doubles ------------------
for _ in $(seq 1 60); do
  st=$(python3 -c "import json,glob;e=[json.load(open(p)) for p in glob.glob('.lab/watch/*.json')];print(all(x['status']!='running' for x in e))")
  [ "$st" = "True" ] && break; sleep 1
done
assert_ok   "second tick settles the baseline"                "$LAB2" run --once --poll-sec 1
fit1=$(sha256sum candidates/c0000/fitness.json)
assert_ok   "third tick is a no-op for c0000"                 "$LAB2" run --once --poll-sec 1
assert_eq   "fitness.json of c0000 is written once"           "$(sha256sum candidates/c0000/fitness.json)" "$fit1"
assert_eq   "exactly one candidate.done for c0000" "$(grep -c '"type":"candidate.done".*"candidate":"c0000"' events.jsonl)" 1
assert_grep "baseline fitness is recorded by lab, from the hidden labels" '"score": -' candidates/c0000/fitness.json
assert_grep "the baseline worker never saw LAB_PRIVATE"       "LAB_PRIVATE visible to worker: <unset>" candidates/c0000/summary.md

# --- crash the loop mid-job, restart, run to completion -----------------------
FAIL_ON=c0002 "$LAB2" run --poll-sec 1 >/dev/null 2>&1 &
_bg=$!
sleep 2
kill -9 "$_bg" 2>/dev/null; wait "$_bg" 2>/dev/null
assert_ok   "the loop restarts from disk and runs to completion" \
            env FAIL_ON=c0002 timeout 300 "$LAB2" run --poll-sec 1
assert_file "REPORT.md written"                               REPORT.md
assert_grep "campaign.stop is in the feed"                    '"type":"campaign.stop"' events.jsonl
assert_eq   "exactly one baseline in the population" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(sum(1 for c in p['candidates'].values() if c['operator']=='baseline'))")" 1
assert_eq   "campaign is finished" "$(python3 -c "import json;print(json.load(open('population.json'))['status'])")" finished
assert_eq   "stopped on max_candidates" \
  "$(python3 -c "import json;print(json.load(open('population.json'))['stop_reason'])")" "max_candidates 9 reached"
assert_eq   "the simulated crash is kept as a failed candidate" \
  "$(python3 -c "import json;c=json.load(open('population.json'))['candidates']['c0002'];print(c['status'],c['exec'])")" "failed failed"
assert_grep "candidate.failed is in the feed"                 '"type":"candidate.failed"' events.jsonl
assert_eq   "exactly one debug child was dispatched for it" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(len([c for c in p['candidates'].values() if c['operator']=='debug' and c['parents']==['c0002']]))")" 1
assert_grep "the failed candidate got a facts-only summary"   "exec: failed" candidates/c0002/summary.md
assert_grep "LEDGER keeps the failed row"                     "| c0002 | failed |" LEDGER.md
assert_eq   "search fitness improved over the baseline" \
  "$(python3 -c "
import json;p=json.load(open('population.json'));c=p['candidates']
print(c[p['best']]['fitness'] > c['c0000']['fitness'])")" True
assert_eq   "best candidate is frozen" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(p['candidates'][p['best']]['status'])")" frozen
assert_eq   "final split was read exactly once, on the frozen candidate" \
  "$(python3 -c "
import json,glob
n=sum(1 for f in glob.glob('candidates/*/fitness.json') if 'final' in json.load(open(f)))
print(n)")" 1
assert_eq   "claim is supported (fit converged; final -mse >= -1.0)" \
  "$(python3 -c "import json;print(json.load(open('population.json'))['claim'])")" supported
assert_grep "REPORT names the claim"                          "| claim | **supported** |" REPORT.md
assert_grep "REPORT states privilege separation is off"       "privilege separation for labels | OFF" REPORT.md
assert_nogrep "no worker ever saw LAB_PRIVATE"                "LAB_PRIVATE visible to worker: $PRIV2" candidates/c0005/summary.md
assert_nogrep "the private path is not in the public feed"    "$PRIV2" events.jsonl
assert_nogrep "the token is not in the public feed"           "tok_supersecret_value_0987" events.jsonl
assert_ok   "a finished campaign is a no-op"                  "$LAB2" run --once --poll-sec 1
assert_fail "the final split is never evaluated on request"   "$LAB2" eval candidates/c0000 --split final
assert_ok   "status renders"                                  "$LAB2" campaign status
assert_ok   "job card renders"                                "$LAB2" job card candidates/c0003
[ -z "$(ls .lab/watch/*.json 2>/dev/null)" ] && ok "every watcher was archived" || bad "watchers left in .lab/watch: $(ls .lab/watch/*.json)"

# --- the guard hook, as a worker session sees it --------------------------------
hook_worker() { printf '{"tool_name":"Bash","tool_input":{"command":%s}}' "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1")" \
  | LAB_ROLE=worker LAB_CANDIDATE_DIR="$WORK2/candidates/c0004" bash .claude/hooks/guard.sh; }
assert_fail "guard: a worker reading labels is blocked"       hook_worker "cat \$LAB_PRIVATE/search/labels.json"
assert_fail "guard: a worker writing another candidate is blocked" hook_worker "echo x > candidates/c0001/code/run.sh"
assert_ok   "guard: a worker writing its own candidate is fine" hook_worker "echo x > candidates/c0004/code/run.sh"
assert_fail "guard: nobody deletes a candidate dir"           hook_worker "rm -rf candidates/c0002"
assert_fail "guard: nobody writes fitness.json by hand"       hook_worker "echo 1 > candidates/c0004/fitness.json"
assert_fail "guard: nobody writes population.json by hand"    hook_worker "echo {} > population.json"

cd "$WORK" || return 1
export LAB_ROOT="$_saved_root"
unset LAB_PRIVATE LAB_WATCH_POLL_SEC FAIL_ON
cleanup_campaign
