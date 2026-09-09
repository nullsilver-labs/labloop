#!/usr/bin/env bash
# Scripted stand-in for a Claude worker. Model: a*x^2 + b*x + c in code/model.json.
#   draft      → (0, 2, 0)        a wrong linear guess
#   improve    → one step toward (1, 0, 0)
#   crossover  → coefficient-wise average of both parents
#   debug      → copy the parent's model.json and make it run
# FAIL_ON (env) names a candidate id whose worker exits 3 without predictions, to
# exercise the failure path. Writes what it saw of LAB_PRIVATE into summary.md so the
# acceptance test can assert the labels location never reached the worker.
set -euo pipefail
cd "$LAB_CANDIDATE_DIR"
cid="$(basename "$LAB_CANDIDATE_DIR")"
op="$LAB_OPERATOR"
job="$LAB_JOB"
if [ "${FAIL_ON:-}" = "$cid" ]; then
  echo "fixture: simulated crash in $cid" >&2
  exit 3
fi
python3 - "$op" "$job" <<'PY'
import json, sys, os
op, job = sys.argv[1], json.load(open(sys.argv[2]))
def load(pid):
    return json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[2]))), pid, "code", "model.json")))
if op == "draft":
    m = {"a": 0, "b": 2, "c": 0}
elif op == "improve":
    m = load(job["parents"][0]["id"])
    if m["a"] < 1: m["a"] = min(1, m["a"] + 0.5)
    elif m["b"] != 0: m["b"] = m["b"] - (1 if m["b"] > 0 else -1)
elif op == "crossover":
    A, B = load(job["parents"][0]["id"]), load(job["parents"][1]["id"])
    m = {k: (A[k] + B[k]) / 2 for k in A}
elif op == "debug":
    m = load(job["parents"][0]["id"])
else:
    raise SystemExit(f"unknown operator {op}")
json.dump(m, open("code/model.json", "w"))
PY
cat > code/run.sh <<'RUN'
#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
python3 - "$here/model.json" "$LAB_SPLIT_INPUTS/inputs.json" "$LAB_PREDICTIONS_OUT" <<'PY'
import json, sys
m = json.load(open(sys.argv[1])); xs = json.load(open(sys.argv[2]))
json.dump([m["a"]*x*x + m["b"]*x + m["c"] for x in xs], open(sys.argv[3], "w"))
PY
RUN
bash code/run.sh
{
  echo "# $cid ($op)"
  echo
  echo "model: $(cat code/model.json)"
  echo "LAB_PRIVATE visible to worker: ${LAB_PRIVATE:-<unset>}"
  echo "ANTHROPIC_API_KEY visible to worker: ${ANTHROPIC_API_KEY:-<unset>}"
  echo "CUDA_VISIBLE_DEVICES: '${CUDA_VISIBLE_DEVICES-<unset>}'"
} > summary.md
