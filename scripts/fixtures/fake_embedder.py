#!/usr/bin/env python3
"""A deterministic stand-in for an embeddings endpoint: hashed bag of words, dim 64.
usage: fake_embedder.py PORT"""
import hashlib, json, re, sys
from http.server import BaseHTTPRequestHandler, HTTPServer


def vec(text):
    v = [0.0] * 64
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        v[int(hashlib.sha256(w.encode()).hexdigest(), 16) % 64] += 1.0
    return v if any(v) else [1.0] + [0.0] * 63


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        body = json.dumps({"data": [{"index": i, "embedding": vec(t)} for i, t in enumerate(req["input"])]}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
