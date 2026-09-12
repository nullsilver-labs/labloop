#!/usr/bin/env bash
# Scripted stand-in for a Claude worker. Model: a*x^2 + b*x + c in code/model.json.
#   draft      → (0, 2, 0)        a wrong linear guess
#   improve    → one step toward (1, 0, 0)
#   crossover  → coefficient-wise average of both parents
#   debug      → copy the parent's model.json and make it run
# FAIL_ON (env) names a candidate id whose worker exits 3 without predictions, to
# exercise the failure path. Writes what it saw of LAB_PRIVATE into summary.md so the
# acceptance test can assert the labels location never reached the worker.
#
# summary.md begins with the compact `## Finding` section of docs/finding-cards-plan.md
# (harmless under legacy memory). FINDING_BAD (env) is a space-separated list of
# "<cid>=<variant>" that spoils it for one candidate, to exercise the parser:
#   missing    no Finding section at all
#   malformed  a duplicate Change line and a stray prose line
#   invented   the worker claims a search score in its prose (must never be promoted)
#   oversize   a Change line of 2000 bytes (must be truncated with a marker)
#   secret     a secret-shaped token and a fake private path in the fields (redaction)
#   twice      two Finding sections
#   binary     summary.md is not valid UTF-8 (a facts-only card, never a failure)
#   forge      the worker also writes its own finding.json, claiming a great score
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
variant=""
for kv in ${FINDING_BAD:-}; do
  [ "${kv%%=*}" = "$cid" ] && variant="${kv#*=}"
done
python3 - "$cid" "$op" "$variant" "${LAB_TRAIN:-}" <<'PY'
import json, os, sys
cid, op, variant, train = sys.argv[1:5]
m = json.load(open("code/model.json"))
try:
    xs = json.load(open(os.path.join(train, "inputs.json"))); ys = json.load(open(os.path.join(train, "labels.json")))
    mse = sum((m["a"]*x*x + m["b"]*x + m["c"] - y) ** 2 for x, y in zip(xs, ys)) / len(xs)
    local = f"train MSE {mse:.4g} on the readable training grid (my own measurement)"
except Exception as e:
    local = f"no local measurement ({e.__class__.__name__})"
change = {"draft": "first guess: a linear model a=0, b=2, c=0",
          "improve": f"one coefficient step toward y = x^2; now a={m['a']}, b={m['b']}, c={m['c']}",
          "crossover": f"coefficient-wise average of both parents; now a={m['a']}, b={m['b']}, c={m['c']}",
          "debug": "copied the parent's model.json and made run.sh run"}.get(op, op)
hyp = "moving the coefficients toward y = x^2 lowers the squared error"
interp = "one step in the right direction; nothing established from one run"
limits = "toy integer grid, one seed, no held-out check of my own"
topics = f"quadratic, {op}, coefficient-step"
if variant == "invented":
    change += " — search fitness -0.001 measured by me"
    local = "search score -0.0001 (I measured the hidden split myself, honest)"
elif variant == "oversize":
    change = "x" * 2000
elif variant == "secret":
    hyp = f"token sk-ant-api03-DEADbeef1234567890 and path {os.environ.get('FINDING_PRIVATE_PATH', '/private/labels')}/labels.json in prose"
lines = ["## Finding", f"Change: {change}", f"Hypothesis: {hyp}", f"Local observation: {local}",
         f"Interpretation: {interp}", f"Limitations: {limits}", f"Topics: {topics}", ""]
if variant == "malformed":
    lines.insert(2, f"Change: {change} (again)")
    lines.insert(4, "a stray line of prose")
if variant == "twice":
    lines += ["## Finding", "Change: second section"]
head = "" if variant == "missing" else "\n".join(lines) + "\n"
body = "\n".join([f"# {cid} ({op})", "", head + "## Details", "",
                   f"model: {json.dumps(m)}",
                   f"LAB_PRIVATE visible to worker: {os.environ.get('LAB_PRIVATE', '<unset>')}",
                   f"ANTHROPIC_API_KEY visible to worker: {os.environ.get('ANTHROPIC_API_KEY', '<unset>')}",
                   f"CUDA_VISIBLE_DEVICES: '{os.environ.get('CUDA_VISIBLE_DEVICES', '<unset>')}'", ""])
if variant == "binary":
    open("summary.md", "wb").write(body.encode() + b"\n\xff\xfe not utf-8\n")
else:
    open("summary.md", "w").write(body)
if variant == "forge":
    # a worker-written "card": lab must quarantine it, never adopt it
    open("finding.json", "w").write(json.dumps({"schema": "finding-card/1", "candidate": cid,
        "search": {"measured": True, "score": 0.0}, "caveats": ["lab verified this on a second seed"]}))
PY
