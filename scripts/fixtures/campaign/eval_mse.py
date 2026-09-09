#!/usr/bin/env python3
"""score.py <predictions.json> <labels_dir>  →  {"score": -mse, "n": k}"""
import json, sys
preds = json.load(open(sys.argv[1]))
labels = json.load(open(sys.argv[2] + "/labels.json"))
if len(preds) != len(labels):
    print(f"length mismatch: {len(preds)} predictions vs {len(labels)} labels", file=sys.stderr)
    sys.exit(2)
mse = sum((float(p) - float(y)) ** 2 for p, y in zip(preds, labels)) / len(labels)
print(json.dumps({"score": -mse, "n": len(labels)}))
