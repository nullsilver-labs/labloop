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
  trust_dir "$1"
}

# Claude Code's trust flags, in a throwaway config: `lab run` refuses a campaign dir that is
# not trusted when lab-worker drives claude (admission rules v0.3, change 8).
export CLAUDE_CONFIG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-claudecfg.XXXXXX")"
trust_dir() {   # trust_dir <dir> [0] — mark a dir trusted, or untrusted with 0
  python3 - "$CLAUDE_CONFIG_DIR/.claude.json" "$1" "${2:-1}" <<'PY'
import json, os, sys
f, d, on = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3] == "1"
c = json.load(open(f)) if os.path.exists(f) else {}
c.setdefault("projects", {}).setdefault(d, {})["hasTrustDialogAccepted"] = on
json.dump(c, open(f, "w"))
PY
}

WORK3="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-worker.XXXXXX")"
worker_repo "$WORK3" acc-worker
cd "$WORK3" || return 1
export LAB_ROOT="$WORK3"
LAB3="$WORK3/tools/lab"

assert_fail "lab-worker refuses to run outside lab run"        "$WORK3/tools/lab-worker"
assert_fail "lab-worker refuses a paid route" \
            env LAB_CANDIDATE_DIR=/nonexistent LAB_JOB=x LAB_PREDICTIONS_OUT=y ANTHROPIC_API_KEY=sk-ant-x "$WORK3/tools/lab-worker"
trust_dir "$WORK3" 0
assert_fail "lab run refuses a campaign dir Claude Code does not trust" timeout 60 "$LAB3" run --poll-sec 1
assert_ok   "lab campaign check names the untrusted dir" \
            bash -c '"$0" campaign check 2>&1 | grep -q "NOT trusted"' "$LAB3"
assert_fail "the refused start wrote no population" test -e population.json
trust_dir "$WORK3"
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

# A blind arm under admission rules v0.3 (item 3): its card is a one-shot's, a population
# table holding only the baseline, whatever else has settled. With an operator text
# override (the effort pair, docs/meta-loop-plan.md §9), the card carries the new text.
WORK6="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-blind.XXXXXX")"
worker_repo "$WORK6" acc-blind
cd "$WORK6" || return 1
export LAB_ROOT="$WORK6"
LAB6="$WORK6/tools/lab"
python3 - <<'EOF'
import re
t = re.sub(r"(?ms)^\[selection\]\n.*?(?=^\[|\Z)", "", open("campaign.toml").read())
t += '\n[selection]\nblind = true\ndraft_p = 1.0\ncrossover_p = 0.0\n'
open("bad-text.toml", "w").write(t + '\n[worker.operator_text]\nsummarise = "x"\n')
open("campaign.toml", "w").write(t + '\n[worker.operator_text]\ndraft = "Draft boldly from the task statement."\n')
EOF
assert_fail "campaign check refuses an operator text for an unknown operator" "$LAB6" campaign check bad-text.toml
rm -f bad-text.toml
assert_ok   "a blind campaign with lab-worker runs to completion" timeout 300 "$LAB6" run --poll-sec 1
assert_eq   "a v0.3 blind card shows only the baseline, as a one-shot's does" \
  "$(python3 -c "import json;j=json.load(open('candidates/c0002/job.json'));print([r['id'] for r in j['population']], j['best'], j['blind_card'])")" "['c0000'] c0000 oneshot"
assert_grep "the operator text override is the card's instructions" "Draft boldly from the task statement." candidates/c0002/job.json
_b6card="$("$LAB6" job card candidates/c0002)"
assert_ok   "the rendered v0.3 blind card has the population table and best-so-far" \
            bash -c 'grep -q "^## Population" <<<"$0" && grep -q "Best so far: c0000" <<<"$0"' "$_b6card"
assert_fail "the rendered v0.3 blind card names no other candidate" bash -c 'grep -q "c0001" <<<"$0"' "$_b6card"
assert_fail "the rendered v0.3 blind card has no blind-arm notice (a one-shot's has none)" \
            bash -c 'grep -q "^## Blind arm" <<<"$0"' "$_b6card"
[ "${KEEP:-0}" = "1" ] || rm -rf "$WORK6"

# v2 C2: a fresh draft once the chain has stalled. The scripted worker's improves converge
# on y = x^2 in four steps and then repeat it; with restart_after = 2 a second draft follows.
WORK7="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-restart.XXXXXX")"
worker_repo "$WORK7" acc-restart
cd "$WORK7" || return 1
export LAB_ROOT="$WORK7"
LAB7="$WORK7/tools/lab"
python3 - <<'EOF'
import re
t = open("campaign.toml").read()
t = re.sub(r'(?m)^command = .*$', 'command = "bash scripts/fixtures/campaign/worker.sh"', t)
t = re.sub(r'(?m)^max_candidates = \d+', 'max_candidates = 18', t)   # two slots: improves settle in identical pairs
t = re.sub(r"(?ms)^\[selection\]\n.*?(?=^\[|\Z)", "", t)
t += '\n[selection]\ntemperature = 0.01\ncrossover_p = 0.0\nrestart_after = 2\nrestart_min_step = 0.0\nseed = 7\n'
open("campaign.toml", "w").write(t)
open("bad-restart.toml", "w").write(t.replace("restart_after = 2", "restart_after = -1"))
EOF
assert_fail "campaign check refuses a negative restart_after" "$LAB7" campaign check bad-restart.toml
rm -f bad-restart.toml
assert_ok   "a campaign with restart_after runs to completion" timeout 300 "$LAB7" run --poll-sec 1
assert_ok   "a stalled chain got a second draft (initial_drafts 1, draft_p 0)" \
            bash -c 'python3 -c "import json,sys;p=json.load(open(\"population.json\"));sys.exit(0 if sum(c[\"operator\"]==\"draft\" for c in p[\"candidates\"].values())>=2 else 1)"'
assert_ok   "the restart came only after improves that did not raise the best" \
            bash -c 'python3 - <<"PY"
import json, sys
p = json.load(open("population.json"))["candidates"]
order = sorted((v for v in p.values() if v.get("ended")), key=lambda v: (v["ended"], v["id"]))
drafts = [i for i, v in enumerate(order) if v["operator"] == "draft"]
second = drafts[1]
before = [v for v in order[:second] if v["operator"] in ("improve", "crossover")][-2:]
best = max(v["fitness"] for v in order[:second - 2] if v.get("fitness") is not None)
sys.exit(0 if len(before) == 2 and all((v.get("fitness") or -1e9) <= best for v in before) else 1)
PY'
assert_ok   "B1: a converged improve is recorded as having its parent's output" \
            bash -c 'python3 -c "import json,sys;p=json.load(open(\"population.json\"))[\"candidates\"];sys.exit(0 if any(c.get(\"same_output_as_parent\") for c in p.values()) else 1)"'
assert_ok   "B1: a moving improve is recorded as not having it" \
            bash -c 'python3 -c "import json,sys;p=json.load(open(\"population.json\"))[\"candidates\"];sys.exit(0 if any(c.get(\"same_output_as_parent\") is False for c in p.values()) else 1)"'
assert_grep "B1: REPORT.md counts them" "with their parent's output (B1)" REPORT.md
[ "${KEEP:-0}" = "1" ] || rm -rf "$WORK7"

# v2 B2: shared snapshot seeding. A source campaign with two drafts; a target that starts
# from its c0000..c0002, and the refusals that keep a seeded population meaning the same.
scripted_repo() {   # scripted_repo <dir> <id> <max_candidates> <extra toml>
  worker_repo "$1" "$2"
  python3 - "$1/campaign.toml" "$3" "$4" <<'EOF'
import re, sys
f, n, extra = sys.argv[1:4]
t = open(f).read()
t = re.sub(r'(?m)^command = .*$', 'command = "bash scripts/fixtures/campaign/worker.sh"', t)
t = re.sub(r'(?m)^max_candidates = \d+', f'max_candidates = {n}', t)
t = re.sub(r"(?ms)^\[selection\]\n.*?(?=^\[|\Z)", "", t)
t = t.replace('[campaign]\n', '[campaign]\n' + "".join(l + "\n" for l in extra.split("|") if l.startswith("seed_")), 1)
for l in extra.split("|"):
    if l.startswith("MEMORY="):   # replace the memory table whole, so no table appears twice
        t = re.sub(r"(?ms)^\[memory\]\n.*?(?=^\[|\Z)", "", t) + f'\n[memory]\nmode = "{l[7:]}"\n'
t += "\n[selection]\nseed = 3\n" + "".join(l + "\n" for l in extra.split("|") if l and not l.startswith(("seed_", "MEMORY=")))
open(f, "w").write(t)
EOF
}
WSRC="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-seedsrc.XXXXXX")"
scripted_repo "$WSRC" acc-seed-src 3 "initial_drafts = 2"
( cd "$WSRC" && LAB_ROOT="$WSRC" timeout 300 "$WSRC/tools/lab" run --poll-sec 1 >/dev/null 2>&1 )
# a worker's bytecode cache names the source dir; it is neither scanned nor copied
mkdir -p "$WSRC/candidates/c0001/scratch/__pycache__" && printf '%s' "$WSRC/candidates/c0001/scratch/x.py" > "$WSRC/candidates/c0001/scratch/__pycache__/x.cpython-312.pyc"
WSEED="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-seeded.XXXXXX")"
scripted_repo "$WSEED" acc-seeded 7 "seed_from = \"$WSRC\"|seed_upto = \"c0002\""
cd "$WSEED" || return 1
export LAB_ROOT="$WSEED"
LABS="$WSEED/tools/lab"
assert_ok   "B2: a campaign seeded from another's opening runs to completion" timeout 300 "$LABS" run --poll-sec 1
assert_eq   "B2: c0000-c0002 are the source's, marked seeded; new jobs start at c0003" \
  "$(python3 -c "import json;p=json.load(open('population.json'));c=p['candidates'];print([k for k in sorted(c) if c[k].get('seeded_from')], c['c0003']['operator'], p['seeded']['n'])")" \
  "['c0000', 'c0001', 'c0002'] improve 3"
assert_ok   "B2: every seeded dir is byte-identical to its source but for seeded.json, fitness.json and the final run; the source is unchanged" \
  bash -c 'for i in c0000 c0001 c0002; do diff -r -x seeded.json -x fitness.json -x predictions-final.json -x __pycache__ "$0/candidates/$i" "candidates/$i" >/dev/null || exit 1; done; python3 -c "import json,sys;sys.exit(0 if len(json.load(open(\"$0/population.json\"))[\"candidates\"])==3 else 1)"' "$WSRC"
assert_ok   "B2: a bytecode cache naming the source dir is not copied (and does not refuse the seed)" \
  bash -c '[ -e "$0/candidates/c0001/scratch/__pycache__/x.cpython-312.pyc" ] && [ ! -e candidates/c0001/scratch/__pycache__ ]' "$WSRC"
assert_ok   "B2: the source's final read never comes along (no predictions-final.json, fitness.json keeps search only)" \
  bash -c 'b=$(python3 -c "import json;print(json.load(open(\"$0/population.json\"))[\"best\"])"); [ -e "$0/candidates/$b/out/predictions-final.json" ] && ! ls candidates/c000[012]/out/predictions-final.json >/dev/null 2>&1 && python3 -c "import json,sys;sys.exit(0 if all(list(json.load(open(f\"candidates/{i}/fitness.json\")))==[\"search\"] for i in (\"c0001\",\"c0002\")) else 1)"' "$WSRC"
assert_eq   "B2: the run stopped on max_candidates, seeded ones counted" \
  "$(python3 -c "import json;print(json.load(open('population.json'))['stop_reason'])")" "max_candidates 7 reached"
assert_grep "B2: REPORT.md says what was seeded" "seeded (B2)" REPORT.md
assert_grep "B2: the LEDGER carries the seeded rows" "seeded from acc-seed-src/c0001" LEDGER.md
assert_ok   "B2: a child of a seeded draft may read it" \
  bash -c 'grep -q "candidates/c000[12]" candidates/c0003/job.json'
_refuse() {   # _refuse <label> <extra toml> <expected words in the refusal>
  local d; d="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-seedno.XXXXXX")"
  scripted_repo "$d" acc-seed-no 5 "$2"
  assert_ok   "B2 refuses: $1" bash -c 'cd "$0" && ! LAB_ROOT="$0" timeout 60 tools/lab run --once --poll-sec 1 >out.txt 2>&1 && grep -q -- "$1" out.txt' "$d" "$3"
  assert_fail "B2 refuses without writing anything: $1" test -e "$d/population.json"
  [ "${KEEP:-0}" = "1" ] || rm -rf "$d"
}
_refuse "a prefix holding an improve" "seed_from = \"$WSEED\"|seed_upto = \"c0003\"" "are improves or crossovers"
_refuse "a prefix past the source's end" "seed_from = \"$WSRC\"|seed_upto = \"c0005\"" "the source lacks"
_refuse "more initial drafts than seeded ones" "seed_from = \"$WSRC\"|seed_upto = \"c0002\"|initial_drafts = 3" "initial_drafts 3 >"
_refuse "a blind arm" "seed_from = \"$WSRC\"|seed_upto = \"c0002\"|blind = true|draft_p = 1.0|crossover_p = 0.0" "a blind arm shows"
_refuse "a findings memory" "seed_from = \"$WSRC\"|seed_upto = \"c0002\"|MEMORY=findings-v3" "seeding is legacy-only"
# labels that differ: the seeded fitness does not re-score to the same value here
_badlab="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-badlab.XXXXXX")"; cp -R "$PRIV2/search" "$_badlab/search"; cp -R "$PRIV2/final" "$_badlab/final"
python3 -c "import json,sys;f=sys.argv[1]+'/search/labels.json';y=json.load(open(f));json.dump([v+1 for v in y],open(f,'w'))" "$_badlab"
_d="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-seedno.XXXXXX")"
scripted_repo "$_d" acc-seed-badlab 5 "seed_from = \"$WSRC\"|seed_upto = \"c0002\""
sed -i "s#\$LAB_PRIVATE/search#$_badlab/search#" "$_d/campaign.toml"
assert_ok   "B2 refuses: search labels that are not the source's (by re-scoring, not by reading them)" \
  bash -c 'cd "$0" && ! LAB_ROOT="$0" timeout 60 tools/lab run --once --poll-sec 1 >out.txt 2>&1 && grep -q "re-scores here to" out.txt && [ ! -e population.json ] && [ ! -d candidates/c0000 ]' "$_d"
# a symlink in the source survives no copy
ln -s /etc/hostname "$WSRC/candidates/c0001/code/link"
_refuse "a symlink in the prefix" "seed_from = \"$WSRC\"|seed_upto = \"c0002\"" "holds a symlink"
rm -f "$WSRC/candidates/c0001/code/link"
[ "${KEEP:-0}" = "1" ] || rm -rf "$_d" "$_badlab"
assert_fail "B2: campaign check refuses seed_from without seed_upto" bash -c 'd=$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-seedck.XXXXXX"); cp campaign.toml "$d/c.toml"; sed -i "/^seed_upto/d" "$d/c.toml"; "$0" campaign check "$d/c.toml"' "$LABS"
[ "${KEEP:-0}" = "1" ] || rm -rf "$WSRC" "$WSEED"

# shellcheck source=scripts/acceptance_usage.sh
. "$SRC/scripts/acceptance_usage.sh"
# shellcheck source=scripts/acceptance_slots.sh
. "$SRC/scripts/acceptance_slots.sh"
# shellcheck source=scripts/acceptance_pi.sh
. "$SRC/scripts/acceptance_pi.sh"

export PATH="$_saved_path"
[ "${KEEP:-0}" = "1" ] || rm -rf "$WORK3" "$WORK4" "$WORK5"
