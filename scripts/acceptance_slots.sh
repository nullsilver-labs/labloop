# acceptance_slots.sh — sourced by acceptance_worker.sh. No LLM involved.
#
# M4 plumbing: GPU slots are leased only when their VRAM is free (fake nvidia-smi on
# PATH), and two free slots in one tick never take the same (operator, parents) job
# when another is available. Also: scripts/sync-project.sh refreshes a project's
# tooling without touching its evidence.
#
# Expects: helpers from acceptance.sh, $SRC, $PRIV2, worker_repo() from acceptance_worker.sh.

section "F. GPU slots — VRAM check, no duplicate dispatch; project sync (no LLM)"

WORKS="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-slots.XXXXXX")"
worker_repo "$WORKS" acc-slots
cd "$WORKS" || return 1
export LAB_ROOT="$WORKS"
LABS="$WORKS/tools/lab"
sed -i -e 's#^command = .*#command = "bash scripts/fixtures/campaign/worker.sh"#' \
       -e 's/^gpus = \[\]/gpus = [0, 1]\nmin_free_vram_mb = 1000/' -e 's/max_candidates = 3/max_candidates = 6/' campaign.toml
_saved_path_s="$PATH"
export PATH="$SRC/scripts/fixtures/campaign/fake-smi:$PATH"
export FAKE_SMI='0, 24000, 24576\n1, 100, 24576'     # index, used, total: gpu 0 busy (576 MiB free), gpu 1 free
assert_ok   "first tick with gpu 0 occupied"                   "$LABS" run --once --poll-sec 1
assert_eq   "the baseline was leased gpu 1, not the occupied gpu 0" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print([c['gpu'] for c in p['candidates'].values()])")" "[1]"
assert_grep "the feed says why gpu 0 was skipped"              "gpu 0 has 576 MiB free, below 1000; not leasing it" events.jsonl
assert_eq   "exactly one note for the held gpu"                "$(grep -c 'not leasing it' events.jsonl)" 1
assert_ok   "second tick, gpu 0 still occupied"                "$LABS" run --once --poll-sec 1
assert_eq   "no second note while it stays held"               "$(grep -c 'not leasing it' events.jsonl)" 1
export FAKE_SMI='0, 24000, 24576\n1, 24000, 24576'
for _ in $(seq 1 30); do "$LABS" run --once --poll-sec 1 >/dev/null 2>&1; [ "$(python3 -c "import json;p=json.load(open('population.json'));print(p['settled'])")" -ge 1 ] && break; sleep 1; done
assert_eq   "with both gpus occupied nothing new is launched" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print(len(p['candidates']))")" 1
export FAKE_SMI='0, 24000, 24576\n1, 100, 24576'
assert_ok   "gpu 1 freed: a draft is launched there"           "$LABS" run --once --poll-sec 1
assert_eq   "the draft got gpu 1"                              "$(python3 -c "import json;p=json.load(open('population.json'));print(p['candidates']['c0001']['gpu'])")" 1
export FAKE_SMI='0, 100, 24576\n1, 100, 24576'
assert_ok   "gpu 0 freed too"                                  "$LABS" run --once --poll-sec 1
assert_grep "the feed says gpu 0 is leased again"              "gpu 0 has 24476 MiB free again; leasing it" events.jsonl
assert_ok   "campaign runs to completion on two leased gpus"   timeout 200 "$LABS" run --poll-sec 1
assert_grep "the worker saw CUDA_VISIBLE_DEVICES=1"            "CUDA_VISIBLE_DEVICES: '1'" candidates/c0001/summary.md
assert_grep "REPORT names the gpus and the VRAM floor"         "| GPUs | 0, 1; max parallel 2; min free VRAM 1000 MiB |" REPORT.md
assert_grep "REPORT reports settled candidates per GPU-hour"   "| settled candidates per GPU-hour |" REPORT.md
assert_eq   "both gpus were used"                              "$(python3 -c "import json;p=json.load(open('population.json'));print(sorted(set(c['gpu'] for c in p['candidates'].values())))")" "[0, 1]"
export PATH="$_saved_path_s"; unset FAKE_SMI

assert_eq   "two free slots do not take the same improve job when another parent exists" \
  "$(python3 -c "
import sys, random; sys.path.insert(0, 'tools'); import lab_campaign as m
cfg = {'selection': {'temperature': 1.0, 'crossover_p': 0.0, 'max_debug_retries': 1},
       'report': {'higher_is_better': True}, 'resources': {'max_parallel_jobs': 2}}
def cand(i, fit): return {'id': i, 'operator': 'draft' if i != 'c0000' else 'baseline', 'parents': [], 'status': 'evaluated', 'fitness': fit, 'debugged': False}
pop = {'candidates': {'c0000': cand('c0000', 0.1), 'c0001': cand('c0001', 0.9), 'c0002': cand('c0002', 0.8)}, 'usage': m.usage_defaults()}
rng = random.Random(3)
first = m.pick_job(cfg, pop, rng, set())
second = m.pick_job(cfg, pop, rng, {(first[0], tuple(first[1]))})
print(first[0], second[0], first[1] != second[1])")" "improve improve True"

assert_eq   "selection.draft_p draws a fresh draft before crossover; 0 leaves the old random stream intact" \
  "$(python3 -c "
import sys, random; sys.path.insert(0, 'tools'); import lab_campaign as m
def cand(i, fit): return {'id': i, 'operator': 'draft' if i != 'c0000' else 'baseline', 'parents': [], 'status': 'evaluated', 'fitness': fit, 'debugged': False}
pop = {'candidates': {'c0000': cand('c0000', 0.1), 'c0001': cand('c0001', 0.9), 'c0002': cand('c0002', 0.8)}, 'usage': m.usage_defaults()}
def run(sel):
    cfg = {'selection': dict(temperature=1.0, max_debug_retries=1, **sel), 'report': {'higher_is_better': True}, 'resources': {'max_parallel_jobs': 1}}
    return [m.choose_job(cfg, pop, random.Random(5))[:2] for _ in range(1)][0]
always = run({'crossover_p': 0.0, 'draft_p': 1.0})
never = run({'crossover_p': 0.0, 'draft_p': 0.0})
legacy = run({'crossover_p': 0.0})
print(always[0], always[1] == [], never == legacy, never[0])")" "draft True True improve"

assert_eq   "selection.initial_drafts: 1 is today's stream, N drafts come before the first improve, a re-dispatch is not a second draft" \
  "$(python3 -c "
import sys, random; sys.path.insert(0, 'tools'); import lab_campaign as m
def cand(i, op, status, fit=None, redis=None, dbg=True):
    return {'id': i, 'operator': op, 'parents': [], 'status': status, 'fitness': fit, 'debugged': dbg, 'redispatch_of': redis}
def cfg(mpj=1, **sel):
    return {'selection': dict(temperature=1.0, crossover_p=0.0, max_debug_retries=1, **sel),
            'report': {'higher_is_better': True}, 'resources': {'max_parallel_jobs': mpj}}
def pop(*cs): return {'candidates': {c['id']: c for c in cs}, 'usage': m.usage_defaults()}
B = cand('c0000', 'baseline', 'evaluated', 0.1)
D = cand('c0001', 'draft', 'evaluated', 0.9)
legacy = m.choose_job(cfg(), pop(B, D), random.Random(5))[:2]
one = m.choose_job(cfg(initial_drafts=1), pop(B, D), random.Random(5))[:2]
second = m.choose_job(cfg(initial_drafts=3), pop(B, D), random.Random(5))[0]
done = m.choose_job(cfg(initial_drafts=3), pop(B, D, cand('c0002', 'draft', 'failed'), cand('c0003', 'draft', 'running')), random.Random(5))[0]
redis = m.choose_job(cfg(2, initial_drafts=3), pop(B, D, cand('c0002', 'draft', 'deferred'), cand('c0003', 'draft', 'running', redis='c0002')), random.Random(5))[0]
cap = m.choose_job(cfg(2, initial_drafts=4), pop(B, D, cand('c0002', 'draft', 'running'), cand('c0003', 'draft', 'queued')), random.Random(5))
print(legacy[0], legacy == one, second, done, redis, cap)")" "improve True draft improve draft None"

assert_eq   "selection.initial_drafts is not doubled by a second slot: the other slot waits for the opening draft, then both fill" \
  "$(python3 -c "
import sys, random; sys.path.insert(0, 'tools'); import lab_campaign as m
def cand(i, op, status, fit=None, parents=None):
    return {'id': i, 'operator': op, 'parents': parents or [], 'status': status, 'fitness': fit, 'debugged': True}
cfg = {'selection': {'temperature': 1.0, 'crossover_p': 0.0, 'max_debug_retries': 1, 'initial_drafts': 1},
       'report': {'higher_is_better': True}, 'resources': {'max_parallel_jobs': 2}}
def pop(*cs): return {'candidates': {c['id']: c for c in cs}, 'usage': m.usage_defaults()}
B = cand('c0000', 'baseline', 'evaluated', 0.1)
opening = pop(B)
rng = random.Random(7)
first = m.pick_job(cfg, opening, rng, set())
opening['candidates']['c0001'] = cand('c0001', 'draft', 'running')
idle = m.pick_job(cfg, opening, rng, {('draft', ())})
opening['candidates']['c0001'] = cand('c0001', 'draft', 'evaluated', 0.9)
a = m.pick_job(cfg, opening, rng, set())
b = m.pick_job(cfg, opening, rng, {(a[0], tuple(a[1]))})
print(first[0], idle, a[0], (a[0], a[1]) != (b[0], b[1]))")" "draft None improve True"

assert_eq   "with initial_drafts 4 two slots draft at once, and the fourth draft still comes before the first improve" \
  "$(python3 -c "
import sys, random; sys.path.insert(0, 'tools'); import lab_campaign as m
def cand(i, op, status, fit=None):
    return {'id': i, 'operator': op, 'parents': [], 'status': status, 'fitness': fit, 'debugged': True}
cfg = {'selection': {'temperature': 1.0, 'crossover_p': 0.0, 'max_debug_retries': 1, 'initial_drafts': 4},
       'report': {'higher_is_better': True}, 'resources': {'max_parallel_jobs': 2}}
def pop(*cs): return {'candidates': {c['id']: c for c in cs}, 'usage': m.usage_defaults()}
B = cand('c0000', 'baseline', 'evaluated', 0.1)
rng = random.Random(7)
p = pop(B)
first = m.pick_job(cfg, p, rng, set())
p['candidates']['c0001'] = cand('c0001', 'draft', 'running')
second = m.pick_job(cfg, p, rng, {('draft', ())})
three = pop(B, cand('c0001', 'draft', 'evaluated', 0.9), cand('c0002', 'draft', 'evaluated', 0.8),
            cand('c0003', 'draft', 'evaluated', 0.7))
fourth = m.choose_job(cfg, three, random.Random(7))[0]
four = pop(B, cand('c0001', 'draft', 'evaluated', 0.9), cand('c0002', 'draft', 'evaluated', 0.8),
           cand('c0003', 'draft', 'evaluated', 0.7), cand('c0004', 'draft', 'evaluated', 0.6))
after = m.choose_job(cfg, four, random.Random(7))[0]
print(first[0], second[0], fourth, after)")" "draft draft draft improve"

assert_eq   "the rescue draft only fires when nothing is left in flight: a dead campaign restarts, a live one waits" \
  "$(python3 -c "
import sys, random; sys.path.insert(0, 'tools'); import lab_campaign as m
def cand(i, op, status, fit=None, parents=None):
    return {'id': i, 'operator': op, 'parents': parents or [], 'status': status, 'fitness': fit, 'debugged': True}
cfg = {'selection': {'temperature': 1.0, 'crossover_p': 0.0, 'max_debug_retries': 1, 'initial_drafts': 1},
       'report': {'higher_is_better': True}, 'resources': {'max_parallel_jobs': 2}}
def pop(*cs): return {'candidates': {c['id']: c for c in cs}, 'usage': m.usage_defaults()}
B = cand('c0000', 'baseline', 'evaluated', 0.1)
F = cand('c0001', 'draft', 'failed')
waiting = m.pick_job(cfg, pop(B, F, cand('c0002', 'debug', 'running', parents=['c0001'])), random.Random(7), set())
dead = m.pick_job(cfg, pop(B, F, cand('c0002', 'debug', 'failed', parents=['c0001'])), random.Random(7), set())
print(waiting, dead[0], dead[1])")" "None draft []"

assert_eq   "resources.worker_model_by_operator resolves per operator and names the key it came from" \
  "$(python3 -c "
import sys; sys.path.insert(0, 'tools'); import lab_campaign as m
plain = {'resources': {'worker_model': 'claude-sonnet-5', 'worker_model_by_operator': {}}}
byop = {'resources': {'worker_model': 'claude-sonnet-5', 'worker_model_by_operator': {'draft': 'claude-opus-5'}}}
print(m.worker_model_for(plain, 'draft'), m.worker_model_for(byop, 'draft'), m.worker_model_for(byop, 'improve'))")" \
  "('claude-sonnet-5', 'campaign.toml') ('claude-opus-5', 'campaign.toml worker_model_by_operator.draft') ('claude-sonnet-5', 'campaign.toml worker_model')"

assert_grep "without the table a candidate's provenance still reads plain campaign.toml" \
            '"requested_source": "campaign.toml",' candidates/c0001/config.json
{ cat campaign.toml; printf '\n[resources.worker_model_by_operator]\ndraft = "claude-opus-5"\n'; } > by-op.toml
assert_ok   "campaign check accepts a per-operator worker model"          "$LABS" campaign check by-op.toml
assert_ok   "campaign check prints the per-operator model" \
            bash -c '"$0" campaign check by-op.toml | grep -q claude-opus-5' "$LABS"
{ cat campaign.toml; printf '\n[resources.worker_model_by_operator]\nimporve = "claude-opus-5"\n'; } > bad-op.toml
assert_fail "campaign check refuses an unknown operator key"              "$LABS" campaign check bad-op.toml
{ cat campaign.toml; printf '\n[resources.worker_model_by_operator]\nbaseline = "claude-opus-5"\n'; } > bad-base.toml
assert_fail "campaign check refuses a model for the baseline"             "$LABS" campaign check bad-base.toml
sed 's/^crossover_p = .*/&\ninitial_drafts = 0/' campaign.toml > bad-drafts.toml
assert_fail "campaign check refuses initial_drafts below 1"               "$LABS" campaign check bad-drafts.toml

# The two keys end to end: two opening drafts, then an improve, on a per-operator model.
WORKM="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-models.XXXXXX")"
worker_repo "$WORKM" acc-models
cd "$WORKM" || return 1
export LAB_ROOT="$WORKM"
LABM="$WORKM/tools/lab"
sed -i -e 's#^command = .*#command = "bash scripts/fixtures/campaign/worker.sh"#' \
       -e 's/^max_candidates = 3/max_candidates = 4/' -e 's/^crossover_p = .*/&\ninitial_drafts = 2/' campaign.toml
printf '\n[resources.worker_model_by_operator]\ndraft = "claude-opus-5"\n' >> campaign.toml
assert_ok   "campaign with two opening drafts and a per-operator model completes" timeout 200 "$LABM" run --poll-sec 1
assert_eq   "both opening drafts came before the first improve" \
  "$(python3 -c "import json;p=json.load(open('population.json'));print([p['candidates'][c]['operator'] for c in ('c0001','c0002','c0003')])")" \
  "['draft', 'draft', 'improve']"
assert_grep "a draft was requested on the per-operator model"  '"requested": "claude-opus-5"' candidates/c0001/config.json
assert_grep "and its provenance names the table key"           '"requested_source": "campaign.toml worker_model_by_operator.draft"' candidates/c0001/config.json
assert_grep "the improve fell back to worker_model"            '"requested": "claude-sonnet-5"' candidates/c0003/config.json
assert_grep "and says so"                                      '"requested_source": "campaign.toml worker_model"' candidates/c0003/config.json
assert_grep "the baseline requested no model at all"           '"requested": null' candidates/c0000/config.json
assert_grep "REPORT lists the requested model per operator"    "| worker model requested | claude-sonnet-5; draft claude-opus-5 |" REPORT.md

WORKP="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-sync.XXXXXX")"
mkdir -p "$WORKP/tools" "$WORKP/candidates/c0000" && echo old > "$WORKP/tools/lab" && echo evidence > "$WORKP/candidates/c0000/summary.md" && echo '[campaign]' > "$WORKP/campaign.toml"
assert_ok   "sync-project refreshes tooling"                   bash "$SRC/scripts/sync-project.sh" "$WORKP"
assert_ok   "synced tools/lab is the current one"              cmp -s "$SRC/tools/lab" "$WORKP/tools/lab"
assert_file "synced hooks"                                     "$WORKP/.claude/hooks/guard.sh"
assert_grep "evidence untouched"                               evidence "$WORKP/candidates/c0000/summary.md"
assert_grep "campaign.toml untouched"                          '[campaign]' "$WORKP/campaign.toml"
[ "${KEEP:-0}" = "1" ] || rm -rf "$WORKS" "$WORKP" "$WORKM"
