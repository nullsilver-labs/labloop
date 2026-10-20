#!/usr/bin/env python3
"""score.py <predictions.json> <labels_dir>  →  {"score": -mse, "n": k, "parts": {"lo": -mse, "hi": -mse}}
(parts: the two halves of the split, for [selection] components_key tests)"""
import json, sys
preds = json.load(open(sys.argv[1]))
labels = json.load(open(sys.argv[2] + "/labels.json"))
if len(preds) != len(labels):
    print(f"length mismatch: {len(preds)} predictions vs {len(labels)} labels", file=sys.stderr)
    sys.exit(2)
sq = [(float(p) - float(y)) ** 2 for p, y in zip(preds, labels)]
h = len(sq) // 2 or 1
mse = sum(sq) / len(labels)
print(json.dumps({"score": -mse, "n": len(labels),
                  "parts": {"lo": -sum(sq[:h]) / h, "hi": -sum(sq[h:]) / max(1, len(sq) - h)}}))
