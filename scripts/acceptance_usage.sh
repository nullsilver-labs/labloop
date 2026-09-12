# acceptance_usage.sh — sourced by acceptance_campaign.sh. No LLM involved.
#
# The usage governor (docs/aira2-loop-design.md M3): the Claude Max window as a resource. With the fake
# `claude` reporting a list-price cost per session, asserts that the loop pauses at
# the soft threshold and dispatches nothing while waiting, resumes when the window
# turns, records the wait, defers (never fails) a job whose session hit a rate-limit
# message and re-dispatches it after the stated reset, and at the hard threshold kills
# a running session and defers its job. Each scenario is its own throwaway repo.
#
# Expects: helpers from acceptance.sh, $SRC, $PRIV2, worker_repo() from
# acceptance_worker.sh, the fake claude already on PATH.

section "E. The usage governor — the Max window as a resource (fake claude, no LLM)"

usage_toml() {   # usage_toml <dir> <max_candidates> <parallel> <usage table lines...>
  local dir="$1" maxc="$2" par="$3"; shift 3
  sed -i -e "s/max_candidates = 3/max_candidates = $maxc/" -e "s/max_parallel_jobs = 2/max_parallel_jobs = $par/" "$dir/campaign.toml"
  { echo; echo "[usage]"; printf '%s\n' "$@"; } >> "$dir/campaign.toml"
}
pj() { python3 -c "import json,sys;p=json.load(open('population.json'));print($1)"; }
assert_egrep() { grep -Eq "$2" "$3" && ok "$1" || bad "$1 (no /$2/ in $3)"; }
wait_settled() {   # wait_settled <cid> — tick until the candidate is no longer queued/running
  for _ in $(seq 1 40); do
    "$LABU" run --once --poll-sec 1 >/dev/null 2>&1
    st=$(pj "p['candidates'].get('$1',{}).get('status')")
    case "$st" in queued|running|None) sleep 1;; *) return 0;; esac
  done
  return 1
}

# --- E1: soft threshold pauses dispatch; the window turning resumes it ----------
WORKU="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-usage.XXXXXX")"
worker_repo "$WORKU" acc-usage-soft
usage_toml "$WORKU" 3 1 'window = "8s"' 'window_budget = 1.0' 'soft = 0.5' 'hard = 0.95' 'session_cost = 0.1'
cd "$WORKU" || return 1
export LAB_ROOT="$WORKU"
LABU="$WORKU/tools/lab"
export FAKE_CLAUDE_COST=0.6
assert_ok   "campaign check reports the estimate governor"     bash -c '"$0" campaign check | grep -q "estimate + rate-limit"' "$LABU"
assert_ok   "baseline settles"                                 wait_settled c0000
assert_ok   "first draft settles"                              wait_settled c0001
assert_eq   "c0001 recorded its session cost"                  "$(pj "p['candidates']['c0001']['session']['cost_usd']")" 0.6
assert_grep "served model recorded in provenance from the session" '"served_source": "session.json modelUsage"' candidates/c0001/config.json
assert_eq   "the loop is waiting on usage (0.6 of 1.0 >= soft 0.5)" "$(pj "p['status']")" waiting_usage
assert_eq   "and dispatched nothing while waiting"             "$(pj "len(p['candidates'])")" 2
assert_egrep "campaign.paused is in the feed with a next-eligible time" '"type":"campaign.paused".*"next_eligible":"20' events.jsonl
assert_ok   "status shows the governor's view"                 bash -c '"$0" campaign status | grep -q "level soft, next eligible"' "$LABU"
assert_ok   "usage --json exposes the state"                   bash -c '"$0" campaign usage --json | python3 -c "import json,sys;d=json.load(sys.stdin);assert d[\"state\"][\"level\"]==\"soft\" and d[\"state\"][\"fraction\"]>=0.5"' "$LABU"
assert_ok   "a restart while waiting stays waiting and launches nothing" "$LABU" run --once --poll-sec 1
assert_eq   "still two candidates"                             "$(pj "len(p['candidates'])")" 2
assert_eq   "exactly one pause so far"                         "$(pj "p['usage']['pauses']")" 1
sleep 9
export FAKE_CLAUDE_COST=0.1
assert_ok   "after the window turns the loop resumes"          "$LABU" run --once --poll-sec 1
assert_eq   "status is running again"                          "$(pj "p['status']")" running
assert_eq   "and the next candidate was launched"              "$(pj "len(p['candidates'])")" 3
assert_egrep "the resume is in the feed with the time waited"   'resumed after .* min waiting on usage' events.jsonl
assert_ok   "campaign runs to completion"                      timeout 120 "$LABU" run --poll-sec 1
assert_eq   "waiting time was accounted"                       "$(pj "p['usage']['waiting_seconds'] > 5")" True
assert_grep "REPORT carries the usage section"                 "## Usage (the Claude Max window)" REPORT.md
assert_grep "REPORT names the governor"                        "estimate against \$1 per" REPORT.md
assert_grep "REPORT counts the pause"                          "| pauses on usage | 1 (0 after a rate-limit message, 0 session(s) killed at hard) |" REPORT.md
assert_grep "REPORT reports idle time as a share of wall clock" "% of wall clock |" REPORT.md
assert_eq   "no candidate was launched between pause and resume" \
  "$(python3 -c "
import json
ev=[json.loads(l) for l in open('events.jsonl')]
paused=[i for i,e in enumerate(ev) if e['type']=='campaign.paused'][0]
resumed=[i for i,e in enumerate(ev) if 'resumed after' in e.get('msg','')][0]
print([e['type'] for e in ev[paused+1:resumed] if e['type']=='candidate.launch'])")" "[]"

# --- E2: a rate-limit message defers the job, never fails it -------------------
WORKR="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-ratelimit.XXXXXX")"
worker_repo "$WORKR" acc-usage-ratelimit
usage_toml "$WORKR" 3 1 'retry = "4s"' 'rate_limit_regex = "hit your limit"'
cd "$WORKR" || return 1
export LAB_ROOT="$WORKR"
LABU="$WORKR/tools/lab"
unset FAKE_CLAUDE_COST
export FAKE_CLAUDE_RATELIMIT=c0001 FAKE_CLAUDE_RESET="in 5s"
assert_eq   "reset times parse: clock, 24h, relative, ISO" \
  "$(python3 -c "
import sys, time; sys.path.insert(0, 'tools'); import lab_campaign as m
now = 1_800_000_000.0
r = [m.parse_reset_time('You\'ve hit your limit · resets 3pm', now) is not None,
     m.parse_reset_time('resets at 14:30', now) is not None,
     m.parse_reset_time('resets in 2h 15m', now) == now + 2*3600 + 15*60,
     m.parse_reset_time('resets 2026-09-10T09:00:00Z', now) == 1789030800.0,
     m.parse_reset_time('nothing here', now) is None,
     0 < m.parse_reset_time('resets 3pm', now) - now <= 86400]
print(all(r), r)")" "True [True, True, True, True, True, True]"
assert_ok   "campaign check warns without a window budget"     bash -c '"$0" campaign check 2>&1 | grep -q "no usage.window_budget"' "$LABU"
assert_ok   "campaign with one rate-limited session runs to completion" timeout 120 "$LABU" run --poll-sec 1
assert_eq   "the rate-limited candidate is deferred, not failed" "$(pj "(p['candidates']['c0001']['status'], p['candidates']['c0001']['exec'])")" "('deferred', 'deferred')"
assert_egrep "its LEDGER note names the usage limit message"    "c0001 \| deferred \|.*usage limit: .*hit your limit" LEDGER.md
assert_grep "its summary carries the session's last words"     "hit your limit" candidates/c0001/summary.md
assert_eq   "the session record says rate-limited with a parsed reset time" \
  "$(pj "(p['candidates']['c0001']['session']['rate_limited'], p['candidates']['c0001']['session']['reset_at'] is not None)")" "(True, True)"
assert_eq   "no candidate.failed for it in the feed"           "$(grep -c '"type":"candidate.failed"' events.jsonl || true)" 0
assert_grep "the deferral is a note in the feed"               'c0001 draft deferred, not failed' events.jsonl
assert_grep "LEDGER keeps the row as deferred"                 "| c0001 | deferred |" LEDGER.md
assert_egrep "the campaign paused on the rate limit"            '"type":"campaign.paused".*"level":"blocked"' events.jsonl
assert_eq   "the job was re-dispatched as a new candidate with the same operator" \
  "$(pj "[(c['id'],c['operator'],c['defers']) for c in p['candidates'].values() if c.get('redispatch_of')=='c0001']")" "[('c0002', 'draft', 1)]"
assert_grep "provenance records the re-dispatch"               '"redispatch_of": "c0001"' candidates/c0002/config.json
assert_grep "the launch says it is a re-dispatch"              'c0002 draft on cpu (re-dispatch of c0001)' events.jsonl
assert_eq   "the re-dispatched candidate was evaluated"        "$(pj "p['candidates']['c0002']['exec']")" completed
assert_eq   "deferred candidates do not count as settled"      "$(pj "(p['settled'], len(p['candidates']))")" "(3, 4)"
assert_eq   "one rate-limit message, one deferral counted"     "$(pj "(p['usage']['rate_limits'], p['usage']['deferred'])")" "(1, 1)"
assert_grep "REPORT counts the rate limit"                     "(1 after a rate-limit message" REPORT.md
assert_grep "REPORT shows the deferred row"                    "| c0001 | draft | — | deferred |" REPORT.md
unset FAKE_CLAUDE_RATELIMIT FAKE_CLAUDE_RESET

# --- E2b: a limit message from a session that KEEPS RUNNING is enforced by the watcher --
# docs/aira2-loop-design.md M3 kill criterion: a worker never continues past a rate-limit message. The
# fake CLI prints the message to stderr and then retries forever; lab-worker echoes the
# CLI's stderr under a prefix and `lab run` launched the job with a kill pattern scoped
# to that prefix, so the watcher ends the session within a poll, long before the job's
# 2-minute wall clock, and the job is deferred and re-dispatched like any rate limit.
WORKK="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-ratelimit-hang.XXXXXX")"
worker_repo "$WORKK" acc-usage-hang
usage_toml "$WORKK" 3 1 'retry = "4s"' 'rate_limit_regex = "hit your limit"'
cd "$WORKK" || return 1
export LAB_ROOT="$WORKK"
LABU="$WORKK/tools/lab"
export FAKE_CLAUDE_HANG=c0001 FAKE_CLAUDE_HANG_STYLE=noeol FAKE_CLAUDE_RESET="in 5s"
assert_eq   "the stderr prefixer tags every line and flushes a partial one" \
  "$(printf 'one\ntwo\n\nthree' | "$SRC/tools/lab-stderr-prefix" | od -An -c | tr -s ' \n' ' ')" \
  "$(printf '[claude stderr] one\n[claude stderr] two\n\n[claude stderr] three' | od -An -c | tr -s ' \n' ' ')"
assert_eq   "a configured regex with global inline flags still compiles inside the kill pattern" \
  "$(python3 -c "
import re, sys; sys.path.insert(0, 'tools'); import lab_campaign as m
rx = re.compile(m.session_kill_regex({'usage': {'rate_limit_regex': '(?i)usage LIMIT'}}))
print(bool(rx.search('[claude stderr] Usage limit reached')), bool(rx.search('usage limit reached')))")" "True False"
t_hang0=$(date +%s)
assert_ok   "campaign with a session that keeps running past its limit message runs to completion" timeout 150 "$LABU" run --poll-sec 1
t_hang=$(( $(date +%s) - t_hang0 ))
assert_eq   "the hung session's candidate is deferred, not failed" "$(pj "(p['candidates']['c0001']['status'], p['candidates']['c0001']['exec'])")" "('deferred', 'deferred')"
assert_eq   "its reason says the watcher ended the session"    "$(pj "'kept running past it and was killed by the watcher' in p['candidates']['c0001']['fail_reason']")" True
assert_eq   "the session record is rate-limited with the parsed reset time" \
  "$(pj "(p['candidates']['c0001']['session']['rate_limited'], p['candidates']['c0001']['session']['reset_at'] is not None)")" "(True, True)"
assert_ok   "the watch entry records a kill by pattern, not by wall clock" bash -c 'grep -rl "kill pattern matched" .lab/ >/dev/null'
assert_ok   "the CLI's stderr reached the watcher log under its prefix" bash -c 'grep -rl "^\[claude stderr\] You.ve hit your limit" .lab/ >/dev/null'
assert_grep "session.stderr still holds the CLI's stderr"      "hit your limit" candidates/c0001/session.stderr
assert_ok   "the whole campaign took well under the 2-minute job wall clock (${t_hang}s)" test "$t_hang" -lt 100
assert_eq   "no candidate.failed in the feed"                  "$(grep -c '"type":"candidate.failed"' events.jsonl || true)" 0
assert_eq   "the job was re-dispatched and evaluated"          "$(pj "[(c['id'],c['exec']) for c in p['candidates'].values() if c.get('redispatch_of')=='c0001']")" "[('c0002', 'completed')]"
assert_eq   "one rate-limit message, one deferral counted"     "$(pj "(p['usage']['rate_limits'], p['usage']['deferred'])")" "(1, 1)"
assert_eq   "a training run that prints the words is not matched by the kill pattern" \
  "$(python3 -c "
import re, sys; sys.path.insert(0, 'tools'); import lab_campaign as m
rx = re.compile(m.session_kill_regex({'usage': {'rate_limit_regex': m.RATE_LIMIT_RE_DEFAULT}}))
print([bool(rx.search(s)) for s in ('epoch 3: rate limit of the optimizer reached', 'RATE_LIMIT hit in run.sh',
                                     '[claude stderr] You\'ve hit your limit · resets 3pm', '[claude stderr] API Error: 429 rate_limit_error')])")" "[False, False, True, True]"
unset FAKE_CLAUDE_HANG FAKE_CLAUDE_HANG_STYLE FAKE_CLAUDE_RESET

# --- E3: at the hard threshold a running session is killed and its job deferred ---
WORKH="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-hard.XXXXXX")"
worker_repo "$WORKH" acc-usage-hard
usage_toml "$WORKH" 3 2 'window = "10s"' 'window_budget = 1.0' 'soft = 0.5' 'hard = 0.7' 'session_cost = 0.1'
cd "$WORKH" || return 1
export LAB_ROOT="$WORKH"
LABU="$WORKH/tools/lab"
export FAKE_CLAUDE_COST=0.05 FAKE_CLAUDE_SLEEP_c0001=40 FAKE_CLAUDE_COST_c0002=0.8
assert_ok   "campaign with a hard-threshold kill runs to completion" timeout 150 "$LABU" run --poll-sec 1
assert_eq   "the slow session was killed at hard and its job deferred" \
  "$(pj "(p['candidates']['c0001']['status'], p['candidates']['c0001']['exec'], p['candidates']['c0001']['fail_reason'].startswith('usage_hard'))")" "('deferred', 'deferred', True)"
assert_eq   "the expensive session that tripped hard was evaluated normally" "$(pj "p['candidates']['c0002']['exec']")" completed
assert_eq   "the killed job came back as a new draft"          "$(pj "[c['id'] for c in p['candidates'].values() if c.get('redispatch_of')=='c0001']")" "['c0003']"
assert_eq   "one hard kill counted"                            "$(pj "p['usage']['hard_kills']")" 1
assert_egrep "campaign.paused at hard names the kill"           '"type":"campaign.paused".*"level":"hard".*"kills":1' events.jsonl
assert_eq   "peak window estimate exceeded hard"               "$(pj "p['usage']['peak_fraction'] >= 0.7")" True
assert_eq   "campaign finished with the claim read"            "$(pj "(p['status'], p['claim'] in ('supported','not_supported'))")" "('finished', True)"
unset FAKE_CLAUDE_COST FAKE_CLAUDE_SLEEP_c0001 FAKE_CLAUDE_COST_c0002

[ "${KEEP:-0}" = "1" ] || rm -rf "$WORKU" "$WORKR" "$WORKH"
