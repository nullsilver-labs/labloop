# acceptance_pi.sh — sourced by acceptance_worker.sh. No LLM involved.
#
# Exercises the Pi backend: a `provider/model` worker model hands tools/lab-worker over
# to tools/lab-worker-pi, which runs a fake `pi` on PATH that prints the JSON event
# stream `pi -p --mode json` prints. The endpoint preflight is tested against Pi's
# models.json in a private PI_CODING_AGENT_DIR: a provider without a baseUrl goes
# through `pi auth check` (the fake says ready), one with a baseUrl is asked for
# /models (a static server here, a closed port for the down case).
#
# Expects: helpers from acceptance.sh and acceptance_usage.sh (pj, assert_egrep),
# worker_repo from acceptance_worker.sh, $SRC, $PRIV2.

section "P. Pi workers — tools/lab-worker-pi with a fake pi (no LLM)"

export PATH="$SRC/scripts/fixtures/campaign/fake-pi:$PATH"
PIDIR="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-piconf.XXXXXX")"
export PI_CODING_AGENT_DIR="$PIDIR"
STATIC="$PIDIR/static"; mkdir -p "$STATIC/v1"
echo '{"object":"list","data":[{"id":"other-model","object":"model"}]}' > "$STATIC/v1/models"
port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
( cd "$STATIC" && timeout 300 python3 -m http.server "$port" --bind 127.0.0.1 >/dev/null 2>&1 ) &
static_pid=$!
cat > "$PIDIR/models.json" <<JSON
{"providers": {
  "fake":   {"api": "openai-completions", "models": [{"id": "model-x"}]},
  "static": {"baseUrl": "http://127.0.0.1:$port/v1", "api": "openai-completions", "apiKey": "x",
             "models": [{"id": "model-x"}, {"id": "other-model"}]},
  "down":   {"baseUrl": "http://127.0.0.1:1/v1", "api": "openai-completions", "apiKey": "x",
             "models": [{"id": "model-x"}]}
}}
JSON
for _ in $(seq 1 20); do curl -sf "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1 && break; sleep 0.2; done

assert_ok   "the extension's turn budget, guard bridge and label refusal (node)" node "$SRC/scripts/test_pi_extension.mjs"
assert_eq   "a model id names its backend" \
  "$(python3 -c "import sys; sys.path.insert(0,'$SRC/tools'); import lab_pi as P; print([P.backend_for(m) for m in ('claude-sonnet-5','local/gpt-oss-20b','fake/model-x:high')], P.split_model('local/q:high'))")" \
  "['claude', 'pi', 'pi'] ('local', 'q')"
assert_ok   "the preflight accepts a served model"            python3 "$SRC/tools/lab_pi.py" check static/other-model
assert_fail "the preflight refuses a model the endpoint does not serve" python3 "$SRC/tools/lab_pi.py" check static/model-x
assert_eq   "… and says what is served instead" \
  "$(python3 "$SRC/tools/lab_pi.py" check static/model-x 2>&1 | grep -c 'serves other-model, not model-x')" 1
assert_fail "the preflight refuses a down endpoint"            python3 "$SRC/tools/lab_pi.py" check down/model-x
assert_ok   "a provider without a baseUrl is checked through pi auth" python3 "$SRC/tools/lab_pi.py" check fake/model-x
assert_eq   "the kill pattern is scoped to the Pi prefix as well" \
  "$(python3 -c "
import re, sys; sys.path.insert(0, '$SRC/tools'); import lab_campaign as m
rx = re.compile(m.session_kill_regex({'usage': {'rate_limit_regex': m.RATE_LIMIT_RE_DEFAULT}}))
print([bool(rx.search(s)) for s in ('[pi stderr] Error: 429 Too Many Requests', '[claude stderr] API Error: 429', 'epoch 429 rate limit')])")" "[True, True, False]"

pi_repo() {   # pi_repo <dir> <campaign-id> <worker_model>
  worker_repo "$1" "$2"
  python3 - "$1/campaign.toml" "$3" <<'PY'
import re, sys
p, model = sys.argv[1], sys.argv[2]
s = open(p).read()
if re.search(r"^worker_model\s*=", s, re.M):
    s = re.sub(r"^worker_model\s*=.*$", f'worker_model = "{model}"', s, flags=re.M)
else:
    s = s.replace("[resources]\n", f'[resources]\nworker_model = "{model}"\n', 1)
open(p, "w").write(s)
PY
}

# --- P1: a campaign whose endpoint does not serve the model never starts ---
WORKP0="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-pi-down.XXXXXX")"
pi_repo "$WORKP0" acc-pi-down static/model-x
cd "$WORKP0" || return 1
export LAB_ROOT="$WORKP0"
assert_eq   "campaign check names the backend" \
  "$("$WORKP0/tools/lab" campaign check campaign.toml 2>&1 | grep -c '"static/model-x": "pi"')" 1
assert_fail "lab run refuses to start when the endpoint serves another model" timeout 60 "$WORKP0/tools/lab" run --once --poll-sec 1
assert_eq   "… and says so" \
  "$(timeout 60 "$WORKP0/tools/lab" run --once --poll-sec 1 2>&1 | grep -c 'refusing to start: Pi model static/model-x')" 1
assert_eq   "nothing was dispatched"                           "$(ls candidates 2>/dev/null | wc -l)" 0

# --- P2: a campaign on the Pi backend runs to completion ---
WORKP1="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-pi.XXXXXX")"
pi_repo "$WORKP1" acc-pi fake/model-x
cd "$WORKP1" || return 1
export LAB_ROOT="$WORKP1"
LABP="$WORKP1/tools/lab"
assert_ok   "campaign with Pi workers runs to completion"      timeout 300 "$LABP" run --poll-sec 1
assert_eq   "candidates driven by the fake pi were evaluated" \
  "$(pj "sorted(set(c['status'] for c in p['candidates'].values() if c['operator']!='baseline'))")" "['evaluated', 'frozen']"
assert_grep "the session result says which backend ran"        '"backend": "pi"' candidates/c0001/session.json
assert_grep "the session result carries the served model"      '"fake/model-x"' candidates/c0001/session.json
assert_eq   "served model recorded in config.json from the session" \
  "$(python3 -c "import json;a=json.load(open('candidates/c0001/config.json'))['agent'];print(a['backend'],a['requested'],a['served'])")" "pi fake/model-x ['fake/model-x']"
assert_file "the event stream is kept beside the candidate"    candidates/c0001/session.stream.jsonl
assert_ok   "Pi's own session file is kept under the candidate" bash -c 'ls candidates/c0001/session-pi/*.jsonl >/dev/null'
assert_ok   "the worker logged its contract check"             bash -c 'grep -q "lab-worker-pi: contract met" .lab/watch/*job-c0001*.log'
assert_eq   "the preflight is recorded with the population"    "$(pj "p['auth_preflight']['pi']['fake/model-x']['ok']")" True
assert_grep "REPORT explains Pi session costs"                 "Pi sessions (tools/lab-worker-pi) cost what Pi computes" REPORT.md
assert_eq   "lab usage counts the Pi session's tokens and turns" \
  "$("$LABP" usage 2>&1 | grep -Ec 'fake/model-x|worker +c0001 +[1-9]')" 2
assert_nogrep "the job card never mentions the labels location" "$PRIV2" candidates/c0001/job.json

# --- P3: a session that does nothing is an invalid candidate, kept ---
WORKP2="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-pi-lazy.XXXXXX")"
pi_repo "$WORKP2" acc-pi-lazy fake/model-x
cd "$WORKP2" || return 1
export LAB_ROOT="$WORKP2"
assert_ok   "campaign with do-nothing Pi sessions runs to completion" env FAKE_PI_MODE=lazy timeout 300 "$WORKP2/tools/lab" run --poll-sec 1
assert_eq   "do-nothing sessions become invalid candidates, kept" \
  "$(pj "sorted(set(c['exec'] for c in p['candidates'].values() if c['operator']!='baseline'))")" "['invalid']"
assert_grep "the mechanical summary carries the session text"  "did nothing" candidates/c0001/summary.md

# --- P4: a session whose first request fails is a failed launch (exit 3) ---
WORKP3="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-pi-crash.XXXXXX")"
pi_repo "$WORKP3" acc-pi-crash fake/model-x
cd "$WORKP3" || return 1
export LAB_ROOT="$WORKP3"
assert_ok   "campaign whose Pi sessions cannot reach the model runs to completion" env FAKE_PI_MODE=down timeout 300 "$WORKP3/tools/lab" run --poll-sec 1
assert_eq   "a session that never completed a model turn is a failed candidate with exit code 3" \
  "$(pj "sorted(set((c['exec'],c['exit_code']) for c in p['candidates'].values() if c['operator']!='baseline'))")" "[('failed', 3)]"
assert_grep "session.json says the session never started"      '"session_started": false' candidates/c0001/session.json

# --- P5: the extension's turn cap shows in the session result ---
WORKP4="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-pi-cap.XXXXXX")"
pi_repo "$WORKP4" acc-pi-cap fake/model-x
cd "$WORKP4" || return 1
export LAB_ROOT="$WORKP4"
assert_ok   "campaign whose Pi sessions hit the turn budget runs to completion" env FAKE_PI_MODE=capped timeout 300 "$WORKP4/tools/lab" run --poll-sec 1
assert_grep "session.json records the cap"                     '"turns_capped": true' candidates/c0001/session.json
assert_grep "… as the max-turns subtype"                       '"subtype": "error_max_turns"' candidates/c0001/session.json
assert_eq   "a capped session with no predictions is invalid, kept" "$(pj "p['candidates']['c0001']['exec']")" invalid

# --- P6: a provider rate limit defers the job, like a spent Max window ---
WORKP5="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-pi-429.XXXXXX")"
pi_repo "$WORKP5" acc-pi-429 fake/model-x
{ echo; echo "[usage]"; echo 'retry = "4s"'; } >> "$WORKP5/campaign.toml"
cd "$WORKP5" || return 1
export LAB_ROOT="$WORKP5"
assert_ok   "campaign with one rate-limited Pi session runs to completion" \
            env FAKE_PI_RATELIMIT=c0001 FAKE_PI_RESET="in 4s" timeout 300 "$WORKP5/tools/lab" run --poll-sec 1
assert_eq   "the rate-limited session's candidate is deferred, not failed" "$(pj "(p['candidates']['c0001']['status'], p['candidates']['c0001']['exec'])")" "('deferred', 'deferred')"
assert_eq   "the job was re-dispatched and evaluated"          "$(pj "[(c['id'],c['exec']) for c in p['candidates'].values() if c.get('redispatch_of')=='c0001']")" "[('c0002', 'completed')]"
assert_ok   "Pi's stderr reached the watcher log under its prefix" bash -c 'grep -rl "^\[pi stderr\] Error: 429" .lab/ >/dev/null'

# --- P7: backends mixed per operator ---
WORKP6="$(mktemp -d "${TMPDIR:-/tmp}/nullsilver-pi-mixed.XXXXXX")"
pi_repo "$WORKP6" acc-pi-mixed claude-sonnet-5
printf '\n[resources.worker_model_by_operator]\ndraft = "fake/model-x"\n' >> "$WORKP6/campaign.toml"
cd "$WORKP6" || return 1
export LAB_ROOT="$WORKP6"
assert_ok   "campaign with a Pi draft and Claude improves runs to completion" timeout 300 "$WORKP6/tools/lab" run --poll-sec 1
assert_eq   "each operator ran on its backend" \
  "$(python3 -c "import json;print([(c,json.load(open(f'candidates/{c}/config.json'))['agent']['backend']) for c in ('c0001','c0002')])")" "[('c0001', 'pi'), ('c0002', 'claude')]"
assert_eq   "both were evaluated"                              "$(pj "sorted(set(c['status'] for c in p['candidates'].values() if c['operator']!='baseline'))")" "['evaluated', 'frozen']"
assert_grep "the Claude session carries its model"             '"claude-sonnet-5"' candidates/c0002/session.json
assert_nogrep "… and no Pi marker"                             '"backend": "pi"' candidates/c0002/session.json

kill "$static_pid" 2>/dev/null; wait "$static_pid" 2>/dev/null
unset PI_CODING_AGENT_DIR
[ "${KEEP:-0}" = "1" ] || rm -rf "$PIDIR" "$WORKP0" "$WORKP1" "$WORKP2" "$WORKP3" "$WORKP4" "$WORKP5" "$WORKP6"
