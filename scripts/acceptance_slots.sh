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

WORKP="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-sync.XXXXXX")"
mkdir -p "$WORKP/tools" "$WORKP/candidates/c0000" && echo old > "$WORKP/tools/lab" && echo evidence > "$WORKP/candidates/c0000/summary.md" && echo '[campaign]' > "$WORKP/campaign.toml"
assert_ok   "sync-project refreshes tooling"                   bash "$SRC/scripts/sync-project.sh" "$WORKP"
assert_ok   "synced tools/lab is the current one"              cmp -s "$SRC/tools/lab" "$WORKP/tools/lab"
assert_file "synced hooks"                                     "$WORKP/.claude/hooks/guard.sh"
assert_grep "evidence untouched"                               evidence "$WORKP/candidates/c0000/summary.md"
assert_grep "campaign.toml untouched"                          '[campaign]' "$WORKP/campaign.toml"
[ "${KEEP:-0}" = "1" ] || rm -rf "$WORKS" "$WORKP"
