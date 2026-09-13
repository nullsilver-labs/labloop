#!/usr/bin/env bash
# The trivial baseline: predict 0 everywhere. Obeys the worker contract.
set -euo pipefail
cd "$LAB_CANDIDATE_DIR"
echo '{"a": 0, "b": 0, "c": 0}' > code/model.json
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
  echo "# baseline"; echo; echo "Predicts 0 for every x."
  echo "LAB_PRIVATE visible to worker: ${LAB_PRIVATE:-<unset>}"
} > summary.md
