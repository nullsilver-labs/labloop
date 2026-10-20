#!/usr/bin/env python3
"""score.py <predictions.json> <labels_dir> -> {"score": gap_closed, "n": N, "bits": b}.

Predictions: a JSON list, one entry per line of inputs.txt, each a list of 16
non-negative numbers (a distribution over the next symbol; normalised here). Each is
mixed with eps of the uniform distribution, so one confident miss costs at most
log2(16/eps) bits. score = (baseline_bits - bits) / (baseline_bits - oracle_bits):
0 is the unigram baseline, 1 is the source itself. Stdlib only.
"""
import json, math, sys

K = 16
preds = json.load(open(sys.argv[1]))
lab = json.load(open(sys.argv[2] + "/labels.json"))
ys, eps = lab["labels"], lab["eps"]
if not isinstance(preds, list) or len(preds) != len(ys):
    print(f"expected a JSON list of {len(ys)} distributions", file=sys.stderr); sys.exit(2)
tot = 0.0
for i, (p, y) in enumerate(zip(preds, ys)):
    if not isinstance(p, list) or len(p) != K:
        print(f"prediction {i}: expected a list of {K} numbers", file=sys.stderr); sys.exit(2)
    try:
        p = [float(v) for v in p]
    except (TypeError, ValueError):
        print(f"prediction {i}: not numbers", file=sys.stderr); sys.exit(2)
    s = sum(p)
    if not all(math.isfinite(v) and v >= 0 for v in p) or s <= 0:
        print(f"prediction {i}: needs finite non-negative numbers with a positive sum",
              file=sys.stderr); sys.exit(2)
    tot -= math.log2((1 - eps) * p[y] / s + eps / K)
bits = tot / len(ys)
gap = lab["baseline_bits"] - lab["oracle_bits"]
print(json.dumps({"score": (lab["baseline_bits"] - bits) / gap, "n": len(ys), "bits": bits}))
