# acceptance_findings.sh — sourced by acceptance.sh. No LLM involved.
#
# Drives `lab run` on a throwaway project with `[memory] mode = "findings-v1"`
# (docs/finding-cards-plan.md) and a scripted worker whose Finding section is spoiled
# one candidate at a time. Asserts what the plan's §6 asks for: one immutable card per
# settled attempt, an invented score that never becomes a measured one, malformed and
# oversized and missing reports kept as facts-only cards, secrets and private paths
# scrubbed, a corrupt card that stops dispatch instead of being overwritten, a deleted
# card recovered without re-scoring or duplicate events, byte-stable job cards, the
# guarded write paths, and legacy campaigns still working with no migration.
#
# Expects the helpers (ok/bad/assert_*) and $SRC from acceptance.sh.

section "G. Finding cards (opt-in memory) — scripted worker, no LLM"

WORKF="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-findings.XXXXXX")"
PRIVF="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-findings-private.XXXXXX")"
CAPF="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-findings-capture.XXXXXX")"
WORKR="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-recovery.XXXXXX")"
WORKB="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-binary.XXXXXX")"
WORKL="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-legacy.XXXXXX")"
WORKV="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-unknown-policy.XXXXXX")"
cleanup_findings() {
  if [ "${KEEP:-0}" = "1" ]; then echo "kept: $WORKF $PRIVF $CAPF $WORKR $WORKB $WORKL $WORKV"
  else rm -rf "$WORKF" "$PRIVF" "$CAPF" "$WORKR" "$WORKB" "$WORKL" "$WORKV"; fi
}
_saved_root_f="$LAB_ROOT"

findings_repo() {   # findings_repo <dir> — a fresh repo with the toy task and the labels
  cp -R "$SRC/tools" "$SRC/templates" "$SRC/.claude" "$1/"
  mkdir -p "$1/scripts" && cp -R "$SRC/scripts/fixtures" "$1/scripts/"
  cp "$SRC/.lab-redact" "$SRC/.gitignore" "$SRC/FORMAT.json" "$1/"
  ( cd "$1" && git init -q . && git add -A && git -c user.email=a@b -c user.name=t commit -qm init )
  python3 "$SRC/scripts/fixtures/campaign/make_data.py" "$1" "$PRIVF"
}

wait_idle() {       # every watcher of this project has stopped running
  for _ in $(seq 1 90); do
    st=$(python3 -c "import json,glob;e=[json.load(open(p)) for p in glob.glob('.lab/watch/*.json')];print(all(x['status']!='running' for x in e))" 2>/dev/null)
    [ "$st" = "True" ] && return 0
    sleep 1
  done
  return 0
}

findings_repo "$WORKF"
cd "$WORKF" || return 1
export LAB_ROOT="$WORKF"
export LAB_PRIVATE="$PRIVF"
export LAB_WATCH_POLL_SEC=1
unset ANTHROPIC_API_KEY
LABF="$WORKF/tools/lab"

cat > campaign.toml <<'EOF'
[campaign]
id   = "acc-findings"
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

[memory]
mode = "findings-v1"

[selection]
temperature = 0.3
crossover_p = 0.5
max_debug_retries = 1
seed = 7

[stop]
max_candidates = 10

[report]
success_threshold = -1.0
higher_is_better = true
EOF

# --- the pure module, on synthetic cards --------------------------------------
assert_ok   "lab_findings unit tests pass" \
            env LAB_TOOLS="$WORKF/tools" python3 "$WORKF/scripts/fixtures/findings/test_findings.py"

# --- opting in ----------------------------------------------------------------
assert_ok   "campaign check accepts an opted-in campaign"     "$LABF" campaign check campaign.toml
sed 's/mode = "findings-v1"/mode = "findings-v9"/' campaign.toml > bad-memory.toml
assert_fail "campaign check refuses an unknown memory mode"   "$LABF" campaign check bad-memory.toml
rm -f bad-memory.toml

export FAIL_ON=c0002
export FINDING_BAD="c0003=malformed c0004=missing c0005=invented c0006=oversize c0007=secret c0008=twice c0009=forge"
export FINDING_PRIVATE_PATH="$PRIVF/search"

# --- tick by tick: the baseline settles, then it has a card -------------------
assert_ok   "first tick launches the baseline"                "$LABF" run --once --poll-sec 1
assert_eq   "the frozen memory policy is findings-v1" \
  "$(python3 -c "import json;print(json.load(open('population.json'))['memory']['policy'])")" "findings-v1"
assert_eq   "the snapshot freezes the card budget" \
  "$(python3 -c "import json;m=json.load(open('population.json'))['memory'];print(m['max_cards'], m['max_bytes'])")" "8 12288"
assert_eq   "the snapshot freezes the card schema" \
  "$(python3 -c "import json;print(json.load(open('population.json'))['memory']['schema'])")" "finding-card/1"
[ ! -e candidates/c0000/finding.json ] && ok "no card exists before the attempt settles" \
  || bad "candidates/c0000/finding.json exists while c0000 is still running"
wait_idle
assert_ok   "second tick settles the baseline"                "$LABF" run --once --poll-sec 1
assert_file "the settled baseline has a finding card"         candidates/c0000/finding.json
assert_ok   "the card is valid JSON with the card schema"     python3 -c "
import json;c=json.load(open('candidates/c0000/finding.json'));assert c['schema']=='finding-card/1',c['schema']"
assert_eq   "the baseline wrote no Finding section, so the report is missing" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0000/finding.json'))['report']['status'])")" missing
assert_eq   "the card's search score is the one lab measured" \
  "$(python3 -c "
import json
c=json.load(open('candidates/c0000/finding.json')); f=json.load(open('candidates/c0000/fitness.json'))
print(c['search']['score'] == f['search']['score'] and c['search']['measured'])")" True
assert_eq   "the card names the candidate it belongs to" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0000/finding.json'))['candidate'])")" c0000
assert_grep "the card says a measured facts card is not a proved claim" \
            "no causal attribution" candidates/c0000/finding.json

# --- keep ticking until c0003 is dispatched, and freeze its job card ----------
for _ in $(seq 1 90); do
  [ -f candidates/c0003/job.json ] && break
  "$LABF" run --once --poll-sec 1 >/dev/null 2>&1
  sleep 1
done
assert_file "c0003 was dispatched tick by tick"               candidates/c0003/job.json
"$LABF" job card candidates/c0003 > "$CAPF/c0003-jobcard-mid.txt" 2>/dev/null
assert_grep "the job card renders the findings section"       "## Findings from earlier candidates" "$CAPF/c0003-jobcard-mid.txt"
assert_grep "the job card marks the worker prose as worker-reported" "worker-reported" "$CAPF/c0003-jobcard-mid.txt"
assert_grep "the job card asks for the compact Finding section" "## Finding" "$CAPF/c0003-jobcard-mid.txt"

python3 -c "
import glob,hashlib,json,os
out={os.path.basename(os.path.dirname(f)): hashlib.sha256(open(f,'rb').read()).hexdigest()
     for f in sorted(glob.glob('candidates/*/finding.json'))}
json.dump(out, open('$CAPF/cards-before-final.json','w'))"

# --- run to completion --------------------------------------------------------
assert_ok   "the opted-in campaign runs to completion"        timeout 300 "$LABF" run --poll-sec 1
assert_eq   "the campaign finished on max_candidates" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(p['status'], p['stop_reason'])")" \
  "finished max_candidates 10 reached"
assert_ok   "every settled candidate has a finding card"      python3 -c "
import json,os
p=json.load(open('population.json'))
miss=[k for k,v in p['candidates'].items() if v.get('exec') and not os.path.exists(f'candidates/{k}/finding.json')]
assert not miss, miss"
assert_ok   "lab validate accepts the cards"                  "$LABF" validate
assert_ok   "every card is schema-valid on its own terms"     python3 -c "
import glob,json,sys
sys.path.insert(0,'tools'); import lab_findings as F
bad=[(f,F.validate_card(json.load(open(f)))) for f in sorted(glob.glob('candidates/*/finding.json'))]
bad=[x for x in bad if x[1]]
assert not bad, bad"

# --- the failed candidate: an execution outcome is not a verdict on the method -
assert_eq   "the simulated crash is recorded as failed" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0002/finding.json'))['execution']['exec'])")" failed
assert_grep "a failed attempt is not evidence about the method" \
            "not evidence about the method" candidates/c0002/finding.json
assert_eq   "a failed attempt has no measured score" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0002/finding.json'))['search']['measured'])")" False
assert_eq   "the crash got exactly one debug child" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(len([c for c in p['candidates'].values() if c['operator']=='debug' and c['parents']==['c0002']]))")" 1

# --- the spoiled reports: kept, explained, never promoted ---------------------
assert_eq   "a duplicated field makes the report malformed" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0003/finding.json'))['report']['status'])")" malformed
assert_ok   "the malformed report names the duplicate field"  python3 -c "
import json;w=json.load(open('candidates/c0003/finding.json'))['report']['warnings']
assert any('duplicate field Change' in x for x in w), w"
assert_eq   "a malformed report yields no topics" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0003/finding.json'))['report']['topics'])")" "[]"
assert_eq   "a malformed report yields no prose either" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0003/finding.json'))['report']['change'])")" None
assert_grep "the raw summary of c0003 is untouched"           "a stray line of prose" candidates/c0003/summary.md
assert_eq   "a summary with no Finding section reports missing" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0004/finding.json'))['report']['status'])")" missing
assert_eq   "a missing report is still a settled candidate with facts" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0004/finding.json'))['search']['measured'])")" True
assert_eq   "two Finding sections make the report malformed" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0008/finding.json'))['report']['status'])")" malformed
assert_ok   "the reason says how many sections it found"      python3 -c "
import json;w=json.load(open('candidates/c0008/finding.json'))['report']['warnings']
assert any('2 \`## Finding\` sections' in x for x in w), w"

assert_eq   "a worker's invented score never becomes the measured one" \
  "$(python3 -c "
import json
c=json.load(open('candidates/c0005/finding.json')); f=json.load(open('candidates/c0005/fitness.json'))
s=c['search']['score']
print(s == f['search']['score'] and s not in (-0.001, -0.0001))")" True
assert_grep "the invented number stays in the worker's own quoted words" \
            "search fitness -0.001 measured by me" candidates/c0005/finding.json
assert_grep "the worker's local number is labelled worker-reported" \
            "worker-reported in summary.md; not measured by lab" candidates/c0005/finding.json

assert_eq   "an oversized field is named as truncated" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0006/finding.json'))['report']['truncated'])")" "['change']"
assert_ok   "the truncated field ends with the marker inside its byte bound" python3 -c "
v=__import__('json').load(open('candidates/c0006/finding.json'))['report']['change']
assert v.endswith('… [truncated]'), repr(v[-20:])
assert len(v.encode('utf-8')) <= 512, len(v.encode('utf-8'))"
assert_eq   "an oversized report is still ok, not malformed" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0006/finding.json'))['report']['status'])")" ok

assert_grep "a secret in worker prose is redacted in the card" "[REDACTED]" candidates/c0007/finding.json
assert_nogrep "the secret itself never reaches the card"      "sk-ant-api03-DEADbeef" candidates/c0007/finding.json
assert_nogrep "the private label path never reaches the card" "$PRIVF" candidates/c0007/finding.json
assert_grep "the private path is marked, not silently dropped" "[private path]" candidates/c0007/finding.json

# --- a worker that forges its own card ----------------------------------------
assert_file "the worker's own finding.json was quarantined"   candidates/c0009/finding.worker.json
assert_grep "the quarantined file keeps the worker's own words" \
            "lab verified this on a second seed" candidates/c0009/finding.worker.json
assert_file "lab published its own card for that candidate"   candidates/c0009/finding.json
assert_eq   "a worker that wrote a card is invalid, not evaluated" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0009/finding.json'))['execution']['exec'])")" invalid
assert_grep "the card says the worker's card was quarantined" "quarantined" candidates/c0009/finding.json
assert_eq   "the forged score is not carried as a measurement" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0009/finding.json'))['search']['measured'])")" False
assert_nogrep "the forged claim is nowhere in lab's card"     "lab verified" candidates/c0009/finding.json
assert_eq   "the population records the quarantine" \
  "$(python3 -c "import json;c=json.load(open('population.json'))['candidates']['c0009'];print(c['exec'], 'quarantined' in (c['fail_reason'] or ''))")" \
  "invalid True"
assert_ok   "no job card anywhere repeats the forged claim"   python3 -c "
import glob,json
for f in sorted(glob.glob('candidates/*/job.json')):
    assert 'lab verified this' not in json.dumps(json.load(open(f)), ensure_ascii=False), f"

# --- the final read changes no card -------------------------------------------
assert_ok   "every card settled before the final read is byte-identical after it" python3 -c "
import hashlib,json
before=json.load(open('$CAPF/cards-before-final.json'))
assert before, 'no cards were captured before the final read'
for cid,sha in before.items():
    now=hashlib.sha256(open(f'candidates/{cid}/finding.json','rb').read()).hexdigest()
    assert now==sha, (cid, sha, now)"

# --- nothing about the final split, ever --------------------------------------
assert_ok   "no card holds a final key or a private path anywhere" python3 -c "
import glob,json,os
priv=os.environ['LAB_PRIVATE']
def keys(o):
    if isinstance(o,dict):
        for k,v in o.items():
            yield k
            yield from keys(v)
    elif isinstance(o,list):
        for v in o: yield from keys(v)
for f in sorted(glob.glob('candidates/*/finding.json')):
    raw=open(f).read()
    assert 'final' not in set(keys(json.loads(raw))), f
    assert priv not in raw, f"
assert_eq   "the frozen best candidate did get a final read" \
  "$(python3 -c "
import json;p=json.load(open('population.json'))
print('final' in json.load(open('candidates/%s/fitness.json' % p['best'])))")" True
assert_ok   "every card's search digest is that of its own search record only" python3 -c "
import glob,hashlib,json,os
def canon(o): return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
for f in sorted(glob.glob('candidates/*/finding.json')):
    c=json.load(open(f)); d=os.path.dirname(f)
    rec=(json.load(open(d+'/fitness.json')) if os.path.exists(d+'/fitness.json') else {}).get('search')
    want='sha256:'+hashlib.sha256(canon(rec)).hexdigest() if isinstance(rec,dict) else None
    assert c['integrity']['search_record_sha256']==want, (f, c['integrity']['search_record_sha256'], want)"
assert_ok   "every card's summary digest matches the summary on disk" python3 -c "
import glob,hashlib,json,os
for f in sorted(glob.glob('candidates/*/finding.json')):
    c=json.load(open(f)); s=os.path.dirname(f)+'/summary.md'
    want='sha256:'+hashlib.sha256(open(s,'rb').read()).hexdigest() if os.path.exists(s) else None
    assert c['integrity']['summary_sha256']==want, f"

# --- the job snapshots: what the worker actually saw --------------------------
CX=$(python3 -c "
import glob,json
pick=''
for f in sorted(glob.glob('candidates/*/job.json')):
    j=json.load(open(f))
    if j.get('findings') and len(j['findings']['cards'])>=4: pick=j['candidate']
print(pick)")
assert_ok   "a later job carries at least four finding cards" bash -c '[ -n "$0" ]' "$CX"
assert_eq   "the job snapshot records the policy version" \
  "$(python3 -c "import json;print(json.load(open('candidates/$CX/job.json'))['findings']['policy'])")" "findings-v1"
assert_eq   "the first card of that snapshot is a direct parent" \
  "$(python3 -c "import json;print(json.load(open('candidates/$CX/job.json'))['findings']['cards'][0]['reason'])")" "direct parent"
assert_eq   "that job's parents carry no inlined summary" \
  "$(python3 -c "import json;print(all(p['summary'] is None for p in json.load(open('candidates/$CX/job.json'))['parents']))")" True
assert_eq   "that job's parents still point at the full summary file" \
  "$(python3 -c "import json;print(all(p['summary_file'] for p in json.load(open('candidates/$CX/job.json'))['parents']))")" True
assert_eq   "the lineage snippets are gone under findings-v1" \
  "$(python3 -c "import json;print(json.load(open('candidates/$CX/job.json'))['lineage'])")" "[]"
assert_grep "the job's contract asks for the compact Finding section" \
            '## Finding' candidates/$CX/job.json
assert_ok   "every job snapshot cites the digest of the card it quoted" python3 -c "
import glob,hashlib,json
def canon(o): return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
for f in sorted(glob.glob('candidates/*/job.json')):
    j=json.load(open(f))
    for c in (j.get('findings') or {}).get('cards', []):
        card=json.load(open('candidates/%s/finding.json' % c['id']))
        want='sha256:'+hashlib.sha256(canon(card)).hexdigest()
        assert c['digest']==want, (f, c['id'], c['digest'], want)"
assert_ok   "every job snapshot respects both budgets"        python3 -c "
import glob,json
for f in sorted(glob.glob('candidates/*/job.json')):
    fn=json.load(open(f)).get('findings')
    if not fn: continue
    assert len(fn['cards']) <= 8, (f, len(fn['cards']))
    assert len(fn['rendered'].encode('utf-8')) <= 12288, (f, len(fn['rendered'].encode('utf-8')))
    assert fn['bytes'] == len(fn['rendered'].encode('utf-8')), f"
assert_ok   "no job snapshot quotes the same card twice"      python3 -c "
import glob,json
for f in sorted(glob.glob('candidates/*/job.json')):
    ids=[c['id'] for c in (json.load(open(f)).get('findings') or {}).get('cards', [])]
    assert len(ids)==len(set(ids)), (f, ids)"
assert_ok   "some job saw a useful finding from outside its own lineage" python3 -c "
import glob,json
hits=[(f,c['reason']) for f in sorted(glob.glob('candidates/*/job.json'))
      for c in (json.load(open(f)).get('findings') or {}).get('cards', [])
      if c['reason'].startswith('did not beat its strongest parent') or c['reason'].startswith('shares topics')]
assert hits, 'no cross-branch topic pick in any job'"
assert_ok   "a crossover job lists both of its parents, in id order" python3 -c "
import glob,json
seen=False
for f in sorted(glob.glob('candidates/*/job.json')):
    j=json.load(open(f)); fn=j.get('findings')
    if not fn or len(j['parents'])<2: continue
    seen=True
    ids=[c['id'] for c in fn['cards'][:2]]
    assert ids==sorted(p['id'] for p in j['parents']), (f, ids)
    assert all(c['reason']=='direct parent' for c in fn['cards'][:2]), (f, fn['cards'][:2])
assert seen, 'no crossover job in this campaign'"
assert_ok   "no job card carries the private path or a session token anywhere" python3 -c "
import glob,json,os
priv=os.environ['LAB_PRIVATE']
for f in sorted(glob.glob('candidates/*/job.json')):
    blob=json.dumps(json.load(open(f)), ensure_ascii=False)
    assert priv not in blob, f
    assert 'tok_supersecret' not in blob, f"
assert_ok   "a failed parent's reason reaches the next worker sanitized and bounded" python3 -c "
import glob,json
seen=False
for f in sorted(glob.glob('candidates/*/job.json')):
    for p in json.load(open(f))['parents']:
        fr=p.get('fail_reason')
        if fr is None: continue
        seen=True
        assert isinstance(fr,str) and fr and '\n' not in fr and len(fr.encode('utf-8'))<=240, (f,fr)
assert seen, 'no job in this campaign quotes a failed parent'"
assert_ok   "no job snapshot mentions the private path or a final score" python3 -c "
import glob,json,os
priv=os.environ['LAB_PRIVATE']
for f in sorted(glob.glob('candidates/*/job.json')):
    fn=json.load(open(f)).get('findings')
    if fn: assert priv not in fn['rendered'], f"

# --- the job card is byte-stable after the campaign ends ----------------------
"$LABF" job card candidates/c0003 > "$CAPF/c0003-jobcard-end.txt" 2>/dev/null
assert_ok   "c0003's job card is byte-identical after every later job ended" \
            cmp -s "$CAPF/c0003-jobcard-mid.txt" "$CAPF/c0003-jobcard-end.txt"
assert_ok   "every job card still renders"                    bash -c '
for d in candidates/c*; do "$0" job card "$d" >/dev/null || exit 1; done' "$LABF"

# --- crash points around publication, on a project of their own ---------------
# The drills below perturb a card by hand, so they get a throwaway campaign to
# themselves: the evidence of the campaign above stays exactly as `lab` wrote it.
# Its workers sleep, so nothing settles under the drills: the accounting a recovery
# tick must not touch stays still for long enough to be compared.
findings_repo "$WORKR"
sed -e 's/id   = "acc-findings"/id   = "acc-recovery"/' \
    -e 's#^command = .*#command = "sleep 25"#' "$WORKF/campaign.toml" > "$WORKR/campaign.toml"
cd "$WORKR" || return 1
export LAB_ROOT="$WORKR"
LABR="$WORKR/tools/lab"
assert_ok   "the recovery fixture launches its baseline"      "$LABR" run --once --poll-sec 1
wait_idle
assert_ok   "and settles it with a card"                      "$LABR" run --once --poll-sec 1
assert_file "the recovery fixture has a card to perturb"      candidates/c0000/finding.json
cp candidates/c0000/finding.json "$CAPF/c0000-card.json"

# --- a missing card for a settled attempt is recovered, once ------------------
acct() { python3 -c "
import json
p=json.load(open('population.json')); u=p['usage']
print(p['settled'], round(p['gpu_seconds'], 3), u['deferred'], u['pauses'])"; }
acct_before=$(acct)
done_before=$(grep -c '"type":"candidate.done"' events.jsonl)
failed_before=$(grep -c '"type":"candidate.failed"' events.jsonl || true)
rm -f candidates/c0000/finding.json
python3 -c "
import pathlib; pathlib.Path('candidates/c0000/finding.json.tmp99999').write_text('half a card, from a crash mid-publication\n')"
assert_ok   "a tick recovers a missing card for a settled attempt" "$LABR" run --once --poll-sec 1
assert_file "the recovered card is back"                      candidates/c0000/finding.json
assert_eq   "the recovered card is byte-identical (created_at is the recorded settlement time, not the clock)" \
  "$(sha256sum < candidates/c0000/finding.json)" "$(sha256sum < "$CAPF/c0000-card.json")"
[ ! -e candidates/c0000/finding.json.tmp99999 ] \
  && ok "the stale temp file of a crashed publication is swept up" \
  || bad "candidates/c0000/finding.json.tmp99999 survived the recovery tick"
assert_eq   "recovery re-scored nothing: no second candidate.done" \
  "$(grep -c '"type":"candidate.done"' events.jsonl)" "$done_before"
assert_eq   "recovery emitted no candidate.failed either" \
  "$(grep -c '"type":"candidate.failed"' events.jsonl || true)" "$failed_before"
assert_eq   "exactly one candidate.done for c0000 in the whole feed" \
  "$(grep -c '"type":"candidate.done".*"candidate":"c0000"' events.jsonl)" 1
assert_eq   "recovery charged nothing: settled, gpu seconds, defers and pauses are untouched" \
  "$(acct)" "$acct_before"

# --- a corrupt card stops dispatch and is left exactly as it is ---------------
n_before=$(ls -d candidates/c* | wc -l)
python3 -c "
import pathlib; pathlib.Path('candidates/c0000/finding.json').write_text('{ this is not a card }\n')"
assert_fail "a corrupt card stops the next tick"              "$LABR" run --once --poll-sec 1
assert_eq   "no new candidate was dispatched while a card is corrupt" \
  "$(ls -d candidates/c* | wc -l)" "$n_before"
assert_grep "the corrupt card is left in place, not overwritten" \
            "this is not a card" candidates/c0000/finding.json
cp "$CAPF/c0000-card.json" candidates/c0000/finding.json
assert_ok   "the loop runs again once the operator restores the card" "$LABR" run --once --poll-sec 1

# --- a schema-valid card that disagrees with its sources is not adopted -------
n_before=$(ls -d candidates/c* | wc -l)
python3 -c "
import json,pathlib
p=pathlib.Path('candidates/c0000/finding.json'); d=json.loads(p.read_text())
d['caveats']=['an operator edited this caveat by hand']
d['metric']['higher_is_better']=not d['metric']['higher_is_better']
p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + '\n')"
assert_fail "a card that disagrees with its sources stops the next tick" \
            "$LABR" run --once --poll-sec 1
assert_ok   "the failure says the card differs from the one rebuilt from its sources" \
            bash -c '"$0" run --once --poll-sec 1 2>&1 | grep -q "differs from the card rebuilt"' "$LABR"
assert_grep "the operator's edit is left in place, never overwritten" \
            "an operator edited this caveat by hand" candidates/c0000/finding.json
assert_eq   "no new candidate was dispatched over a conflicting card" \
  "$(ls -d candidates/c* | wc -l)" "$n_before"
cp "$CAPF/c0000-card.json" candidates/c0000/finding.json
assert_ok   "the loop runs again once the card agrees with its sources" "$LABR" run --once --poll-sec 1
wait_idle

cd "$WORKF" || return 1
export LAB_ROOT="$WORKF"

# --- the guard: workers cannot write a generated card -------------------------
hook_f() {    # hook_f <json payload> — the guard as a worker session in c0004 sees it
  printf '%s' "$1" | LAB_ROLE=worker LAB_CANDIDATE_DIR="$WORKF/candidates/c0004" bash .claude/hooks/guard.sh
}
hook_bash_f() { hook_f "$(python3 -c 'import json,sys;print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$1")"; }
hook_file_f() { hook_f "$(python3 -c 'import json,sys;print(json.dumps({"tool_name":sys.argv[1],"tool_input":{"file_path":sys.argv[2],"content":"{}"}}))' "$1" "$2")"; }
hook_cwd_f() { hook_f "$(python3 -c 'import json,sys;print(json.dumps({"tool_name":sys.argv[1],"tool_input":{"file_path":sys.argv[2],"content":"{}"},"cwd":sys.argv[3]}))' "$1" "$2" "$3")"; }
hook_nb_f() { hook_f "$(python3 -c 'import json,sys;print(json.dumps({"tool_name":"NotebookEdit","tool_input":{"notebook_path":sys.argv[1]}}))' "$1")"; }
assert_fail "guard: a shell redirect into a finding card is blocked" \
            hook_bash_f "echo x > candidates/c0004/finding.json"
assert_fail "guard: tee into a finding card is blocked" \
            hook_bash_f "tee candidates/c0004/finding.json < /dev/null"
assert_fail "guard: a Write tool call on a finding card is blocked" \
            hook_file_f Write "candidates/c0004/finding.json"
assert_fail "guard: an Edit tool call on a finding card is blocked" \
            hook_file_f Edit "candidates/c0004/finding.json"
assert_fail "guard: a worker editing another candidate's file is blocked" \
            hook_file_f Edit "candidates/c0001/code/run.sh"
assert_fail "guard: a worker writing another candidate's summary is blocked" \
            hook_file_f Write "candidates/c0001/summary.md"
assert_fail "guard: a worker escaping its own dir through .. is blocked" \
            hook_file_f Write "candidates/c0004/../c0001/summary.md"
assert_fail "guard: a MultiEdit of population.json is blocked" \
            hook_file_f MultiEdit "population.json"
assert_fail "guard: a MultiEdit of a finding card is blocked" \
            hook_file_f MultiEdit "candidates/c0004/finding.json"
assert_fail "guard: a NotebookEdit of a finding card is blocked" \
            hook_nb_f "candidates/c0004/finding.json"
assert_fail "guard: a NotebookEdit of population.json is blocked" \
            hook_nb_f "population.json"
assert_ok   "guard: a worker writing its own summary.md is fine" \
            hook_file_f Write "candidates/c0004/summary.md"
assert_ok   "guard: an operator editing tools/lab_findings.py is fine" \
            hook_file_f Write "tools/lab_findings.py"
assert_fail "guard: copying a file over a finding card is blocked" \
            hook_bash_f "cp x candidates/c0004/finding.json"
assert_fail "guard: installing a file over a finding card is blocked" \
            hook_bash_f "install -m 644 x candidates/c0004/finding.json"
assert_fail "guard: moving a file over fitness.json is blocked" \
            hook_bash_f "mv x candidates/c0004/fitness.json"
assert_fail "guard: touching a finding card into existence is blocked" \
            hook_bash_f "touch candidates/c0004/finding.json"
# The rule matches a machine file anywhere after the verb, so copying a card *out*
# is blocked too. Over-broad by a little, in the safe direction: `cat` still reads it.
assert_fail "guard: copying a card out is blocked as well (the rule matches either side)" \
            hook_bash_f "cp candidates/c0004/finding.json /tmp/x"
assert_ok   "guard: reading a card with cat is fine"          hook_bash_f "cat candidates/c0004/finding.json"
assert_fail "guard: sed -i on a finding card is blocked" \
            hook_bash_f "sed -i s/a/b/ candidates/c0004/finding.json"
assert_fail "guard: perl -i on population.json is blocked" \
            hook_bash_f "perl -pi -e s/a/b/ population.json"
assert_fail "guard: a worker writing up out of its own dir is blocked" \
            hook_cwd_f Write "../c0001/summary.md" "$WORKF/candidates/c0004"
assert_ok   "guard: the same relative path inside its own dir is fine" \
            hook_cwd_f Write "./summary.md" "$WORKF/candidates/c0004"
assert_fail "guard: a relative path onto its own finding card is blocked" \
            hook_cwd_f Write "./finding.json" "$WORKF/candidates/c0004"

# --- a summary.md that is not valid UTF-8 -------------------------------------
# The worker's bytes are its own: an unreadable summary costs the next worker its
# narrative, never the candidate its measurement.
findings_repo "$WORKB"
sed -e 's/id   = "acc-findings"/id   = "acc-binary"/' \
    -e 's/max_candidates = 10/max_candidates = 3/' "$WORKF/campaign.toml" > "$WORKB/campaign.toml"
cd "$WORKB" || return 1
export LAB_ROOT="$WORKB"
export FINDING_BAD="c0001=binary"
unset FAIL_ON
LABB="$WORKB/tools/lab"
assert_ok   "a campaign whose worker writes unreadable bytes runs to completion" \
            timeout 300 "$LABB" run --poll-sec 1
assert_eq   "the campaign finished"  \
  "$(python3 -c "import json;print(json.load(open('population.json'))['status'])")" finished
assert_eq   "an unreadable summary is not a failed candidate" \
  "$(python3 -c "import json;c=json.load(open('population.json'))['candidates']['c0001'];print(c['exec'], c['status'])")" \
  "completed evaluated"
assert_file "it still gets a card"                            candidates/c0001/finding.json
assert_eq   "the card says the report could not be decoded" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0001/finding.json'))['report']['status'])")" undecodable
assert_eq   "the measurement is unaffected" \
  "$(python3 -c "
import json
c=json.load(open('candidates/c0001/finding.json')); f=json.load(open('candidates/c0001/fitness.json'))
print(c['search']['measured'] and c['search']['score'] == f['search']['score'])")" True
assert_eq   "no prose is invented from unreadable bytes" \
  "$(python3 -c "import json;r=json.load(open('candidates/c0001/finding.json'))['report'];print(r['change'], r['topics'])")" \
  "None []"
assert_ok   "the card warns about the encoding"               python3 -c "
import json
w=json.load(open('candidates/c0001/finding.json'))['report']['warnings']
assert any('UTF-8' in x for x in w), w"
assert_ok   "the worker's bytes are left exactly as written"  python3 -c "
import hashlib,json
b=open('candidates/c0001/summary.md','rb').read()
try:
    b.decode('utf-8')
    raise AssertionError('summary.md was rewritten as valid UTF-8')
except UnicodeDecodeError:
    pass
c=json.load(open('candidates/c0001/finding.json'))
assert c['integrity']['summary_sha256'] == 'sha256:' + hashlib.sha256(b).hexdigest()"
assert_ok   "lab validate accepts the campaign"               "$LABB" validate
assert_ok   "the next job card renders around the unreadable summary" \
            bash -c 'for d in candidates/c*; do "$0" job card "$d" >/dev/null || exit 1; done' "$LABB"
unset FINDING_BAD

# --- legacy: a campaign without [memory] is untouched -------------------------
findings_repo "$WORKL"
sed -e '/^\[memory\]/,+1d' -e 's/id   = "acc-findings"/id   = "acc-legacy"/' \
    -e 's/max_candidates = 10/max_candidates = 3/' "$WORKF/campaign.toml" > "$WORKL/campaign.toml"
cd "$WORKL" || return 1
export LAB_ROOT="$WORKL"
unset FAIL_ON FINDING_BAD FINDING_PRIVATE_PATH
LABL="$WORKL/tools/lab"
assert_ok   "a campaign without [memory] passes campaign check" "$LABL" campaign check campaign.toml
assert_ok   "a legacy campaign runs to completion"            timeout 300 "$LABL" run --poll-sec 1
assert_eq   "a legacy campaign records the legacy policy" \
  "$(python3 -c "import json;print(json.load(open('population.json'))['memory']['policy'])")" legacy
assert_eq   "a legacy campaign publishes no cards" \
  "$(ls candidates/*/finding.json 2>/dev/null | wc -l)" 0
assert_eq   "a legacy job carries no findings snapshot" \
  "$(python3 -c "import json;print(json.load(open('candidates/c0001/job.json'))['findings'])")" None
assert_ok   "a legacy job still inlines its parents' summaries" python3 -c "
import glob,json
for f in sorted(glob.glob('candidates/*/job.json')):
    j=json.load(open(f))
    for p in j['parents']:
        assert isinstance(p['summary'], str) and p['summary'], (f, p['id'])"
assert_ok   "lab validate passes on a legacy campaign"        "$LABL" validate
assert_ok   "a legacy job card still renders"                 "$LABL" job card candidates/c0001
python3 -c "
import json,os
os.makedirs('candidates/legacy-fixture', exist_ok=True)
job={'candidate':'c0001','operator':'improve',
     'instructions':'Improve on the parent.','task_file':'scripts/fixtures/campaign/task.md',
     'candidate_dir':'candidates/legacy-fixture','seed':4242,
     'parents':[{'id':'c0000','path':'candidates/c0000','fitness':-8533.0,'exec':'completed',
                 'fail_reason':None,
                 'summary':'a format 2.0 job card inlined the parent summary right here'}],
     'lineage':[{'id':'c0000','operator':'baseline','fitness':-8533.0,'summary':'the baseline'}],
     'population':[{'id':'c0000','operator':'baseline','status':'evaluated','fitness':-8533.0}],
     'best':'c0000',
     'contract':{'write':'code/run.sh and summary.md','run':'code/run.sh once',
                 'inherited':\"the parent's code/\",'final':'lab re-runs code/run.sh later',
                 'predictions':'out/predictions-search.json',
                 'may_write':'candidates/legacy-fixture','may_read':['data/train','data/search'],
                 'max_turns':40}}
json.dump(job, open('candidates/legacy-fixture/job.json','w'), indent=2)"
assert_ok   "a pre-2.1 job.json still renders"                "$LABL" job card candidates/legacy-fixture
"$LABL" job card candidates/legacy-fixture > "$CAPF/legacy-jobcard.txt" 2>/dev/null
assert_grep "the old job card still lists its parents"        "## Parents" "$CAPF/legacy-jobcard.txt"
assert_grep "the old job card still inlines the parent summary" \
            "a format 2.0 job card inlined the parent summary right here" "$CAPF/legacy-jobcard.txt"
assert_nogrep "and asks for no Finding section"               "## Findings from earlier candidates" "$CAPF/legacy-jobcard.txt"
rm -rf candidates/legacy-fixture
assert_ok   "format sync is a no-op on a legacy project"      "$LABL" format sync
assert_ok   "validate is still clean after a format sync"     "$LABL" validate

# --- an unknown policy snapshot fails clearly, never falls back ---------------
findings_repo "$WORKV"
cp "$WORKF/campaign.toml" "$WORKV/campaign.toml"
cd "$WORKV" || return 1
export LAB_ROOT="$WORKV"
LABV="$WORKV/tools/lab"
assert_ok   "the unknown-policy fixture starts a normal campaign" "$LABV" run --once --poll-sec 1
wait_idle
assert_ok   "and settles its baseline"                        "$LABV" run --once --poll-sec 1
wait_idle
python3 -c "
import json,pathlib
p=pathlib.Path('population.json'); d=json.loads(p.read_text())
d['memory']['policy']='findings-v9'
p.write_text(json.dumps(d, indent=2))"
assert_fail "an unknown memory policy in population.json stops the loop" \
            "$LABV" run --once --poll-sec 1
assert_fail "and lab validate reports it too"                 "$LABV" validate

cd "$WORK" || return 1
export LAB_ROOT="$_saved_root_f"
unset LAB_PRIVATE LAB_WATCH_POLL_SEC FAIL_ON FINDING_BAD FINDING_PRIVATE_PATH
cleanup_findings
