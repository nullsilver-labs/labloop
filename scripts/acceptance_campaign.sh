# acceptance_campaign.sh — sourced by acceptance.sh. No LLM involved.
#
# Drives the phaseless loop (`lab run`, docs/aira2-loop-design.md M0) end to end on a toy task with a
# scripted worker: baseline → draft → a simulated crash → debug → improve … → stop →
# freeze → one final-split read → REPORT.md. Asserts the plumbing docs/aira2-loop-design.md §4 insists on:
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

INIT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-init.XXXXXX")"
cp -R "$SRC/tools" "$SRC/templates" "$INIT_DIR/"
assert_ok   "campaign init scaffolds a new project"           env LAB_ROOT="$INIT_DIR" "$INIT_DIR/tools/lab" campaign init acc-init
assert_file "scaffold: campaign.toml"                          "$INIT_DIR/campaign.toml"
assert_file "scaffold: task.md"                                "$INIT_DIR/task.md"
assert_file "scaffold: eval/score.py"                          "$INIT_DIR/eval/score.py"
assert_file "scaffold: eval/baseline.sh"                       "$INIT_DIR/eval/baseline.sh"
assert_grep "scaffold: id substituted"                         'id   = "acc-init"' "$INIT_DIR/campaign.toml"
[ -d "$PRIV2/acc-init/final" ] && ok "scaffold: private label dirs created under LAB_PRIVATE" || bad "no $PRIV2/acc-init/final"
assert_ok   "scaffold passes campaign check as-is"             env LAB_ROOT="$INIT_DIR" "$INIT_DIR/tools/lab" campaign check
assert_fail "campaign init refuses to overwrite"               env LAB_ROOT="$INIT_DIR" "$INIT_DIR/tools/lab" campaign init acc-init
rm -rf "$INIT_DIR"

assert_ok   "campaign check accepts the toy campaign"          "$LAB2" campaign check campaign.toml
sed '/success_threshold/d' campaign.toml > broken.toml
assert_fail "campaign check refuses a campaign without a pre-fixed threshold" "$LAB2" campaign check broken.toml
assert_fail "auth preflight refuses to start with an API key in the environment" \
            env ANTHROPIC_API_KEY=sk-ant-test123 "$LAB2" run --once --poll-sec 1
[ ! -e population.json ] && ok "and creates no population" || bad "population.json created despite refusal"
export FAIL_ON=c0002    # the fixture worker crashes in this candidate, whenever it is dispatched

# --- one tick: the baseline is dispatched under a watcher ---------------------
mkdir -p .lab && echo "2026-01-01T00:00:00Z" > .lab/campaign.stop   # left by a previous campaign's `stop`
assert_ok   "first tick starts the campaign and launches the baseline" "$LAB2" run --once --poll-sec 1
[ ! -e .lab/campaign.stop ] && ok "a stale campaign.stop is cleared when a new campaign starts" || bad "stale .lab/campaign.stop kept"
assert_eq   "and the new campaign is running, not stopping" "$(python3 -c "import json;print(json.load(open('population.json'))['status'])")" running
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
assert_ok   "status --once renders the live layout"           bash -c '"$0" campaign status --once | grep -q "^ population "' "$LAB2"
assert_ok   "status --once fits 80 columns"                   bash -c 'COLUMNS=80 "$0" campaign status --once | awk "length(\$0) > 80 {exit 1}"' "$LAB2"
assert_ok   "status --once names the best candidate"          bash -c '"$0" campaign status --once | grep -q " best$"' "$LAB2"
assert_ok   "status --plain keeps the text shape"             bash -c '"$0" campaign status --plain | head -1 | grep -q "^campaign .* status finished "' "$LAB2"
assert_ok   "job card renders"                                "$LAB2" job card candidates/c0003
[ -z "$(ls .lab/watch/*.json 2>/dev/null)" ] && ok "every watcher was archived" || bad "watchers left in .lab/watch: $(ls .lab/watch/*.json)"

# --- the guard hook, as a worker session sees it --------------------------------
hook_worker() { printf '{"tool_name":"Bash","tool_input":{"command":%s}}' "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1")" \
  | LAB_ROLE=worker LAB_CANDIDATE_DIR="$WORK2/candidates/c0004" bash .claude/hooks/guard.sh; }
assert_fail "guard: a worker reading labels is blocked"       hook_worker "cat \$LAB_PRIVATE/search/labels.json"
assert_fail "guard: a worker writing another candidate is blocked" hook_worker "echo x > candidates/c0001/code/run.sh"
assert_ok   "guard: a worker writing its own candidate is fine" hook_worker "echo x > candidates/c0004/code/run.sh"
# read scope: a worker reads its own dir and its job card's parents, nothing else
_gp=$(python3 -c 'import json,sys;p=json.load(open(sys.argv[1]))["parents"];print(p[0]["id"] if p else "")' "$WORK2/candidates/c0004/job.json")
_go=$(python3 -c 'import json,sys;p={x["id"] for x in json.load(open(sys.argv[1]))["parents"]}|{"c0004"};print(next(c for c in ("c0001","c0002","c0003","c0005") if c not in p))' "$WORK2/candidates/c0004/job.json")
assert_fail "guard: a worker reading a candidate outside its job card is blocked" hook_worker "cat candidates/$_go/summary.md"
assert_fail "guard: a worker globbing every candidate is blocked" hook_worker "cat candidates/*/summary.md"
assert_fail "guard: a worker grepping the candidates dir is blocked" hook_worker "grep -r lr candidates/"
assert_fail "guard: an interpreter heredoc opening another candidate is blocked" hook_worker "python3 - <<'EOF'
print(open('candidates/$_go/summary.md').read())
EOF"
assert_ok   "guard: a summary heredoc may name any candidate" hook_worker "cat > candidates/c0004/summary.md <<'EOF'
unlike candidates/$_go this one converged
EOF"
assert_ok   "guard: a worker reading the task and the training data is fine" hook_worker "cat task.md; ls data/train"
if [ -n "$_gp" ]; then
  assert_ok   "guard: a worker reading its parent is fine" hook_worker "cat candidates/$_gp/summary.md"
  assert_ok   "guard: copying from the parent into its own dir is fine" hook_worker "cp candidates/$_gp/code/run.sh candidates/c0004/code/run.sh"
  assert_fail "guard: copying from its own dir into the parent is blocked" hook_worker "cp candidates/c0004/code/run.sh candidates/$_gp/code/run.sh"
fi
printf '{"ts":"t","argv":["best"],"ids":["%s"],"bytes":1}\n' "$_go" >> "$WORK2/candidates/c0004/queries.jsonl"
assert_ok   "guard: a candidate the worker's own index query returned is readable" hook_worker "cat candidates/$_go/summary.md"
sed -i '$d' "$WORK2/candidates/c0004/queries.jsonl"
hook_worker_read() { printf '{"tool_name":"Read","tool_input":{"file_path":"%s"}}' "$1" \
  | LAB_ROLE=worker LAB_CANDIDATE_DIR="$WORK2/candidates/c0004" bash .claude/hooks/guard.sh; }
assert_fail "guard: the Read tool on a candidate outside the job card is blocked" hook_worker_read "candidates/$_go/summary.md"
assert_ok   "guard: the Read tool on its own dir is fine" hook_worker_read "candidates/c0004/job.json"
# read scope, the forms that got past the textual check (hsrc-v1 Acrip c0009 read a sibling's
# summary once): a glob, a variable, a cd, a .. hop, a recursive search, a tool without a path.
# hook_at DIR TOOL INPUT-JSON runs the guard with the session cwd the hook input carries.
hook_at() { printf '{"tool_name":"%s","cwd":"%s","tool_input":%s}' "$2" "$1" "$3" \
  | LAB_ROLE=worker LAB_CANDIDATE_DIR="$WORK2/candidates/c0004" bash .claude/hooks/guard.sh; }
hook_bash_at() { hook_at "$1" Bash "$(python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$2")"; }
_own="$WORK2/candidates/c0004"
for _cmd in \
  "cat */$_go/summary.md" \
  "cat cand*/$_go/summary.md" \
  "P=candidates; cat \$P/$_go/summary.md" \
  "cd candidates && cat $_go/summary.md" \
  "cat candidates/c0004/../$_go/summary.md" \
  "ls candidates" \
  "find . -name summary.md -exec head {} \\;" \
  "find candidates -name summary.md" \
  "grep -r converged ." \
  "grep -rl converged" \
  "rg converged" \
  "tar cf - . | tar tvf -" \
  "python3 -c \"import glob;[print(open(f).read()) for f in glob.glob('*/c*/summary.md')]\"" \
  "python3 -c \"import os;[print(r) for r,d,f in os.walk('.')]\"" \
  "cat \$LAB_CANDIDATE_DIR/../$_go/summary.md" \
  "cat $WORK2/../elsewhere/candidates/c0004/summary.md"
do
  assert_fail "guard: from the campaign root a worker cannot read with: $_cmd" hook_bash_at "$WORK2" "$_cmd"
done
for _cmd in \
  "cat ../$_go/summary.md" \
  "head -c 1500 ../$_go/summary.md" \
  "cat ../*/summary.md" \
  "ls .." \
  "cd .. && cat $_go/summary.md" \
  "grep -r converged ../.." \
  "find ../.. -name summary.md" \
  "ln -s ../$_go code/p" \
  "cat \"\$(dirname \"\$PWD\")\"/c000?/summary.md" \
  "python3 -c \"print(open('../c00'+'${_go#c00}/summary.md').read())\""
do
  assert_fail "guard: from its own dir a worker cannot read with: $_cmd" hook_bash_at "$_own" "$_cmd"
done
assert_fail "guard: from the campaign root a worker cannot read with: head */*/summary.md" hook_bash_at "$WORK2" "head */*/summary.md"
# Claude Code's Bash cwd persists between calls: a session already sitting in candidates/
for _cmd in "cat */summary.md" "grep -rn converged ." "head -20 $_go/summary.md"; do
  assert_fail "guard: from the candidates dir a worker cannot read with: $_cmd" hook_bash_at "$WORK2/candidates" "$_cmd"
done
assert_fail "guard: a Glob rooted at . reaches another candidate" hook_at "$WORK2" Glob '{"pattern":"*/*/summary.md","path":"."}'
assert_fail "guard: a Grep rooted at . searches every candidate" hook_at "$WORK2" Grep '{"pattern":"mod 1000","path":"."}'
assert_fail "guard: a Glob over the campaign root reaches every candidate" hook_at "$WORK2" Glob '{"pattern":"**/summary.md"}'
assert_fail "guard: a Glob through a wildcard dir reaches another candidate" hook_at "$WORK2" Glob "{\"pattern\":\"*/$_go/summary.md\"}"
assert_fail "guard: a Grep without a path searches every candidate" hook_at "$WORK2" Grep '{"pattern":"converged"}'
assert_fail "guard: a Grep over the campaign root searches every candidate" hook_at "$WORK2" Grep "{\"pattern\":\"converged\",\"path\":\"$WORK2\"}"
ln -s "../$_go" "$_own/sib"
assert_fail "guard: the Read tool through a symlink to another candidate is blocked" hook_at "$WORK2" Read "{\"file_path\":\"$_own/sib/summary.md\"}"
rm -f "$_own/sib"
# ...and what a worker does every job still passes
for _cmd in \
  "ls; ls candidates/c0004 candidates/c0004/code; head -c 1500 data/train/dev.txt" \
  "find candidates/c0004 -name '*.py'" \
  "grep -rn lr candidates/c0004/code" \
  "for f in candidates/c0004/code/*.sh; do bash -n \$f; done" \
  "cd candidates/c0004 && bash -n code/run.sh" \
  "awk '{print \$1/2}' data/train/dev.txt | head -3" \
  "cat \$LAB_CANDIDATE_DIR/summary.md" \
  "tools/lab index best"
do
  assert_ok "guard: from the campaign root a worker may: $_cmd" hook_bash_at "$WORK2" "$_cmd"
done
for _cmd in \
  "cat summary.md; ls code; head -c 200 ../../data/train/dev.txt" \
  "python3 -c \"import os;[print(r) for r,d,f in os.walk('code')]\""
do
  assert_ok "guard: from its own dir a worker may: $_cmd" hook_bash_at "$_own" "$_cmd"
done
if [ -n "$_gp" ]; then
  assert_ok "guard: from its own dir a worker may read its parent" hook_bash_at "$_own" "diff ../$_gp/code/run.sh code/run.sh"
fi
assert_ok   "guard: a Glob inside its own dir is fine" hook_at "$WORK2" Glob '{"pattern":"candidates/c0004/**/*.sh"}'
assert_ok   "guard: a Grep inside its own dir is fine" hook_at "$WORK2" Grep '{"pattern":"lr","path":"candidates/c0004"}'
# pinf K2 (2026-10-17): `cd $_` took the hook's own $_ (its python3), so every later path
# resolved under it and candidates/<own>/code read as another campaign's. $_ is the last
# argument of the previous command; the shell state the hook cannot see is unknown.
_infer="cat > infer <<'E'
import json, sys
tasks = json.load(open(sys.argv[1]))['tasks']
E
chmod +x infer; cd ../../..; python3 eval/measure.py candidates/c0004/code"
_train="python3 - <<'E'
import json
d=json.load(open('data/train/train_tasks.json'))['tasks']
a=json.load(open('data/train/train_answers.json'))
for t in d[:12]: print(t['id'], len(t['train']))
E"
for _cwd in "$WORK2" "$_own"; do
  assert_ok "guard: a worker may mkdir its code dir, cd \$_ into it and work there (from ${_cwd#$WORK2/})" \
    hook_bash_at "$_cwd" "mkdir -p $_own/code && cd \$_ && cp ../../../eval/run.sh run.sh && $_infer"
  assert_ok "guard: ...also into a code dir that does not exist yet (from ${_cwd#$WORK2/})" \
    hook_bash_at "$_cwd" "mkdir -p $_own/code2 && cd \$_ && cp ../../../eval/run.sh run.sh && ${_infer//code/code2}"
  assert_ok "guard: a worker may read the training data in a python heredoc (from ${_cwd#$WORK2/})" \
    hook_bash_at "$_cwd" "cd $WORK2; ls; ls data/train; echo \$LAB_TRAIN; $_train"
  assert_fail "guard: ...but not after listing every candidate (from ${_cwd#$WORK2/})" \
    hook_bash_at "$_cwd" "cd $WORK2; ls; ls candidates/*; ls data/train; $_train"
done
assert_ok   "guard: cd \$_ after a mkdir through a variable is followed" hook_bash_at "$WORK2" "mkdir -p \${LAB_CANDIDATE_DIR}/code && cd \$_ && grep -rn lr ."
assert_ok   "guard: cd - back to where the command started is followed" hook_bash_at "$WORK2" "cd candidates/c0004/code; cd -; ls data/train/*"
assert_ok   "guard: ~- is the dir the command came from" hook_bash_at "$WORK2" "cd candidates/c0004; ls ~-/data/train"
# ...and the shell state it cannot see, or a cd that may not have happened, is not guessed
for _c in \
  "$_own|echo \${U:-..}; cd \$_; cat */summary.md" \
  "$_own|true; cd \$_; cat ../*/summary.md" \
  "$WORK2|true; cd \$_; cat */*/summary.md" \
  "$WORK2|cd candidates/c0004; cd -; cat */*/summary.md" \
  "$WORK2|cd candidates/c0004; cd ~-; cat */*/summary.md" \
  "$WORK2|cd candidates/c0004; cat ~-/*/*/summary.md" \
  "$WORK2|cd \$OLDPWD; cat */*/summary.md" \
  "$_own|cd / x; cat ../*/summary.md" \
  "$_own|cd -x; cat ../*/summary.md" \
  "$WORK2|pushd /tmp; popd; cat */*/summary.md" \
  "$WORK2|cd ~1; cat */*/summary.md" \
  "$WORK2|CDPATH=\$(echo \$PWD/cand*); X=${_go%?}; cd \${X}${_go: -1} && cat summary.md" \
  "$WORK2|cd nowhere; cat */*/summary.md" \
  "$_own|cd code | true; cat ../*/summary.md"
do
  [ "${_c%%|*}" = "$WORK2" ] && _l="the campaign root" || _l="its own dir"
  assert_fail "guard: from $_l a worker cannot read with: ${_c#*|}" hook_bash_at "${_c%%|*}" "${_c#*|}"
done

# --- the default cards (2026-10-19): no "Make ONE hypothesised change", no "Prefer simple" -
assert_ok   "the default draft and improve texts no longer ask for one small, simple step" \
  bash -c 'cd "$0/tools" && python3 -c "import sys; sys.path.insert(0, \".\"); import lab_campaign as C; t = C.OPERATOR_TEXT; sys.exit(0 if \"ONE\" not in t[\"improve\"] and \"simple\" not in t[\"draft\"] and \"State your hypothesis\" in t[\"improve\"] else 1)"' "$WORK2"

# --- a blind arm ([selection] blind, admission rules v0.2's crippled arm) -------------
# Every job a fresh draft that sees no other candidate, no score and no best-so-far.
python3 - <<'EOF'
import re
s = open("campaign.toml").read()
def variant(path, lines, mem=None):
    # the [selection] block replaced whole, so no key appears twice
    t = re.sub(r"(?ms)^\[selection\]\n.*?(?=^\[|\Z)", "", s)
    t += "\n[selection]\n" + "\n".join(lines) + "\n"
    if mem:
        t = re.sub(r"(?ms)^\[memory\]\n.*?(?=^\[|\Z)", "", t) + f'\n[memory]\nmode = "{mem}"\n'
    open(path, "w").write(t)
variant("blind-ok.toml", ["blind = true", "draft_p = 1.0", "crossover_p = 0.0"])
variant("blind-mix.toml", ["blind = true", "draft_p = 0.5", "crossover_p = 0.0"])
variant("blind-mem.toml", ["blind = true", "draft_p = 1.0", "crossover_p = 0.0"], mem="findings-v3")
EOF
assert_ok   "campaign check accepts a blind draft-only arm"           "$LAB2" campaign check blind-ok.toml
assert_fail "campaign check refuses blind with draft_p < 1"           "$LAB2" campaign check blind-mix.toml
assert_fail "campaign check refuses blind with a findings memory"     "$LAB2" campaign check blind-mem.toml
_bcard=$(cd "$WORK2/tools" && python3 - <<'EOF'
import sys; sys.path.insert(0, ".")
import lab_campaign as C
# a v0.2 blind job.json (no blind_card): old evidence renders as it was shown
card = {"candidate": "c0003", "operator": "draft", "instructions": "Write a complete solution.",
        "blind": True, "seed": 1, "parents": [], "lineage": [], "findings": None,
        "population": [], "best": None,
        "contract": {"may_write": "candidates/c0003", "may_read": ["data/train", "task.md"],
                     "write": "w", "run": "r", "predictions": "p", "final": "f", "max_turns": 9}}
print(C.render_job_card(card, "the task"))
EOF
)
assert_ok   "a v0.2 blind job card still says it is blind" bash -c 'grep -q "^## Blind arm" <<<"$0"' "$_bcard"
assert_fail "a v0.2 blind job card has no population table" bash -c 'grep -q "^## Population" <<<"$0"' "$_bcard"
assert_fail "a v0.2 blind job card has no best-so-far" bash -c 'grep -q "Best so far" <<<"$0"' "$_bcard"
assert_fail "a v0.2 blind draft is not told to differ from the population" bash -c 'grep -q "population below" <<<"$0"' "$_bcard"
_bl="$WORK2/blindcase"; mkdir -p "$_bl/candidates/c0000" "$_bl/candidates/c0001/code" "$_bl/.lab/watch" "$_bl/data/train"
printf '{"blind": true, "operator": "draft", "contract": {"may_read": ["data/train", "task.md"]}}\n' > "$_bl/candidates/c0001/job.json"
for _f in population.json LEDGER.md events.jsonl REPORT.md task.md; do echo x > "$_bl/$_f"; done
echo x > "$_bl/candidates/c0000/summary.md"; echo x > "$_bl/.lab/watch/a.log"
hook_blind() { printf '{"tool_name":"%s","cwd":"%s","tool_input":%s}' "$2" "$1" "$3" \
  | LAB_ROLE=worker LAB_CANDIDATE_DIR="$_bl/candidates/c0001" bash .claude/hooks/guard.sh; }
hook_blind_bash() { hook_blind "$1" Bash "$(python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$2")"; }
for _cmd in \
  "cat population.json" \
  "head -5 LEDGER.md" \
  "tail events.jsonl" \
  "cat ./REPORT.md" \
  "cat *.json" \
  "ls .lab/watch" \
  "tools/lab campaign status --once" \
  "tools/lab index best" \
  "python3 -c \"print(open('population.json').read())\"" \
  "cat candidates/c0000/summary.md"
do
  assert_fail "guard, blind arm: from the campaign root a worker may not: $_cmd" hook_blind_bash "$_bl" "$_cmd"
done
assert_fail "guard, blind arm: a .. hop to the ledger from its own dir is blocked" hook_blind_bash "$_bl/candidates/c0001" "cat ../../LEDGER.md"
assert_fail "guard, blind arm: the Read tool on population.json is blocked" hook_blind "$_bl" Read '{"file_path":"population.json"}'
assert_fail "guard, blind arm: a Glob matching the ledger is blocked" hook_blind "$_bl" Glob '{"pattern":"*.md"}'
assert_ok   "guard, blind arm: the task statement is readable" hook_blind_bash "$_bl" "cat task.md; ls data/train"
assert_ok   "guard, blind arm: its own dir is readable and writable" hook_blind_bash "$_bl" "cat candidates/c0001/job.json; echo s > candidates/c0001/summary.md"
assert_ok   "guard, blind arm: the Read tool on its own job card is fine" hook_blind "$_bl" Read '{"file_path":"candidates/c0001/job.json"}'
assert_ok   "guard: a worker that is not blind may still read population.json" hook_worker "cat population.json"
rm -f blind-ok.toml blind-mix.toml blind-mem.toml
# --- lab index: one writer, reproducible, read-only for workers -------------------
assert_ok   "index: build over the finished campaign"            "$LAB2" index build
cp index/experiments.sqlite3 "$WORK2/.index-first"
assert_ok   "index: a second build is byte-identical"            bash -c '"$0" index build >/dev/null && cmp -s index/experiments.sqlite3 "$1"' "$LAB2" "$WORK2/.index-first"
assert_ok   "index: best lists a non-baseline candidate"         bash -c '"$0" index best | grep -q "^  c0"' "$LAB2"
assert_ok   "index: open shows the candidate line"               bash -c '"$0" index open c0001 | grep -q "^c0001 "' "$LAB2"
assert_ok   "index: nothing of the final split is in the file"   bash -c '! strings index/experiments.sqlite3 | grep -qi "predictions-final\|final_score"'
assert_fail "index: a worker cannot build"                       env LAB_ROLE=worker "$LAB2" index build
rm -f candidates/c0004/queries.jsonl.test
assert_ok   "index: a worker query is logged in its own dir"     bash -c 'LAB_ROLE=worker LAB_CANDIDATE_DIR="$1/candidates/c0004" "$0" index best >/dev/null && tail -1 "$1/candidates/c0004/queries.jsonl" | grep -q "\"best\""' "$LAB2" "$WORK2"
# hybrid search: any embeddings endpoint, cached vectors, lexical when it is down
_eport=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
python3 "$SRC/scripts/fixtures/fake_embedder.py" "$_eport" & _epid=$!
for _ in $(seq 1 50); do python3 -c "import socket;socket.create_connection(('127.0.0.1',$_eport),1)" 2>/dev/null && break; sleep 0.1; done
assert_ok   "index: build with an embedder gives every text row a vector" bash -c '"$0" index --db "$1/.hy.sqlite3" build --embed-url "http://127.0.0.1:$2" --embed-model fake >/dev/null && python3 -c "
import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); a=c.execute(\"select count(*) from fields\").fetchone(); b=c.execute(\"select count(*) from vectors\").fetchone(); assert a==b and a[0]>0,(a,b)" "$1/.hy.sqlite3"' "$LAB2" "$WORK2" "$_eport"
cp "$WORK2/.hy.sqlite3" "$WORK2/.hy.first"
assert_ok   "index: the rebuild reads the vector cache and is byte-identical" bash -c '"$0" index --db "$1/.hy.sqlite3" build --embed-url "http://127.0.0.1:$2" --embed-model fake | grep -q "\"embedded_now\": 0" && cmp -s "$1/.hy.sqlite3" "$1/.hy.first"' "$LAB2" "$WORK2" "$_eport"
assert_ok   "index: search is hybrid when the embedder answers" bash -c '"$0" index --db "$1/.hy.sqlite3" search "baseline mean" | grep -q "hybrid (lexical + fake"' "$LAB2" "$WORK2"
kill "$_epid" 2>/dev/null; wait "$_epid" 2>/dev/null
assert_ok   "index: search answers lexically when the embedder is down, and says so" bash -c '"$0" index --db "$1/.hy.sqlite3" search "baseline mean" | grep -q "lexical only: the embedder did not answer"' "$LAB2" "$WORK2"
assert_ok   "index: an index built without an embedder is lexical" bash -c '"$0" index search "baseline mean" | grep -q " — lexical$"' "$LAB2"
rm -f "$WORK2/.hy.sqlite3" "$WORK2/.hy.first" "$WORK2/embeddings.sqlite3"
assert_fail "guard: nobody writes the index by hand"             hook_worker "cp /tmp/x index/experiments.sqlite3"
assert_fail "guard: nobody deletes a candidate dir"           hook_worker "rm -rf candidates/c0002"
assert_fail "guard: nobody writes fitness.json by hand"       hook_worker "echo 1 > candidates/c0004/fitness.json"
assert_fail "guard: nobody writes population.json by hand"    hook_worker "echo {} > population.json"

. "$SRC/scripts/acceptance_worker.sh"

cd "$WORK" || return 1
export LAB_ROOT="$_saved_root"
unset LAB_PRIVATE LAB_WATCH_POLL_SEC FAIL_ON
cleanup_campaign
