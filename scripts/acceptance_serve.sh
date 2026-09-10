# acceptance_serve.sh — sourced by acceptance_campaign.sh after the toy campaign has
# finished in $WORK2. No LLM involved.
#
# `lab serve` is a read-only page over the campaign's files. Asserts it renders the
# population, a candidate, the report and the JSON view; refuses writes and bad
# paths; and redacts secrets before showing summaries.

section "C2. lab serve — the read-only page"

echo "leaked token tok_supersecret_value_0987 in a summary" >> candidates/c0001/summary.md
PORT=$((20000 + RANDOM % 20000))
"$LAB2" serve --bind 127.0.0.1 --port "$PORT" >/dev/null 2>&1 &
_srv=$!
for _ in $(seq 1 30); do curl -s -o /dev/null "http://127.0.0.1:$PORT/" && break; sleep 0.5; done
code() { curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$1"; }
assert_eq   "index renders"                                    "$(code /)" 200
curl -s "http://127.0.0.1:$PORT/" -o serve-index.html
assert_grep "index names the campaign"                         "acc-quadratic" serve-index.html
assert_grep "index shows the finished badge"                   "Finished" serve-index.html
assert_grep "index links the report"                           'href=/report' serve-index.html
assert_grep "index lists a candidate"                          '/candidate/c0003' serve-index.html
assert_grep "index shows the failed candidate's state"         '<td>failed</td>' serve-index.html
assert_grep "index carries the timeline"                       'campaign.stop' serve-index.html
curl -s "http://127.0.0.1:$PORT/candidate/c0001" -o serve-c0001.html
assert_grep "candidate page shows the summary"                 'model:' serve-c0001.html
assert_nogrep "candidate page redacts the env secret"          "tok_supersecret_value_0987" serve-c0001.html
assert_grep "candidate page carries the redaction marker"      "[REDACTED]" serve-c0001.html
assert_eq   "report renders"                                   "$(code /report)" 200
assert_eq   "unknown candidate is 404"                         "$(code /candidate/c9999)" 404
assert_eq   "a path that is not a candidate id is 404"         "$(code /candidate/..%2Fcampaign.toml)" 404
assert_eq   "unknown route is 404"                             "$(code /LEDGER.md)" 404
assert_eq   "POST is refused"                                  "$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/")" 405
assert_ok   "api state is JSON with the population and governor view" bash -c 'curl -s "http://127.0.0.1:'"$PORT"'/api/state.json" | python3 -c "import json,sys;d=json.load(sys.stdin);assert d[\"population\"][\"status\"]==\"finished\" and \"usage_state\" in d"'
assert_ok   "api events is ndjson"                             bash -c 'curl -s "http://127.0.0.1:'"$PORT"'/api/events.jsonl" | head -1 | python3 -c "import json,sys;json.loads(sys.stdin.read())"'
kill "$_srv" 2>/dev/null; wait "$_srv" 2>/dev/null
rm -f serve-index.html serve-c0001.html
assert_nogrep "the page wrote nothing to the feed"             "lab-serve" events.jsonl
