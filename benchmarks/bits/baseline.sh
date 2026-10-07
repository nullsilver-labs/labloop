#!/usr/bin/env bash
# The trivial baseline (always candidate c0000): the training unigram, add-one smoothed,
# for every input. It scores 0 by construction.
set -euo pipefail
cd "$LAB_CANDIDATE_DIR"
mkdir -p code out
cat > code/run.sh <<'RUN'
#!/usr/bin/env bash
set -euo pipefail
python3 - "$LAB_TRAIN/train.txt" "$LAB_SPLIT_INPUTS/inputs.txt" "$LAB_PREDICTIONS_OUT" <<'PY'
import json, sys
cnt = [1.0] * 16
for line in open(sys.argv[1]):
    for ch in line.strip():
        cnt[int(ch, 16)] += 1
p = [c / sum(cnt) for c in cnt]
n = sum(1 for _ in open(sys.argv[2]))
json.dump([p] * n, open(sys.argv[3], "w"))
PY
RUN
bash code/run.sh
printf '# baseline\n\nThe training unigram (add-one) for every input. Scores 0 by construction.\n' > summary.md
