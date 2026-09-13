#!/usr/bin/env python3
"""make_data.py <root> <private>  — y = x*x on integer grids; labels of search/final go to <private>."""
import json, os, sys
root, private = sys.argv[1], sys.argv[2]
splits = {"train": range(-5, 6), "search": range(6, 13), "final": range(-12, -5)}
for name, xs in splits.items():
    xs = list(xs)
    ys = [x * x for x in xs]
    d = os.path.join(root, "data", name); os.makedirs(d, exist_ok=True)
    json.dump(xs, open(os.path.join(d, "inputs.json"), "w"))
    if name == "train":
        json.dump(ys, open(os.path.join(d, "labels.json"), "w"))
    else:
        p = os.path.join(private, name); os.makedirs(p, exist_ok=True)
        json.dump(ys, open(os.path.join(p, "labels.json"), "w"))
