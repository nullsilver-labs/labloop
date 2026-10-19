#!/usr/bin/env python3
"""A small OpenAI-compatible /v1/embeddings server for a local sentence-embedding checkpoint,
on CPU, in RAM. One of the things `[memory.embedder] url` can point at; llama.cpp with
`--embedding`, TEI, vLLM or a hosted API are the others — `lab index` only speaks the protocol.

    PY=/path/to/venv/bin/python   # needs torch and transformers; never installs anything
    $PY scripts/embed-server.py MODEL_DIR [--port 8789] [--alias NAME] [--pooling cls|mean]

Like scripts/llm-server.sh it is started by the human (or under `lab watch start`), never by
`lab run`. Binds 127.0.0.1 only. The model id it reports is --alias (default: the dir name).
"""
from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

ap = argparse.ArgumentParser()
ap.add_argument("model_dir")
ap.add_argument("--port", type=int, default=8789)
ap.add_argument("--alias")
ap.add_argument("--pooling", choices=("cls", "mean"), default="cls")
ap.add_argument("--max-tokens", type=int, default=512)
a = ap.parse_args()

alias = a.alias or Path(a.model_dir.rstrip("/")).name
tok = AutoTokenizer.from_pretrained(a.model_dir)
model = AutoModel.from_pretrained(a.model_dir).eval()
lock = threading.Lock()


def encode(texts: list[str]) -> list[list[float]]:
    with lock, torch.no_grad():
        b = tok(texts, padding=True, truncation=True, max_length=a.max_tokens, return_tensors="pt")
        h = model(**b).last_hidden_state
        if a.pooling == "cls":
            v = h[:, 0]
        else:
            m = b["attention_mask"].unsqueeze(-1).to(h.dtype)
            v = (h * m).sum(1) / m.sum(1).clamp(min=1)
        return torch.nn.functional.normalize(v.float(), dim=-1).tolist()


class H(BaseHTTPRequestHandler):
    def _send(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok"})
        if self.path == "/v1/models":
            return self._send(200, {"object": "list", "data": [{"id": alias, "object": "model"}]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") not in ("/v1/embeddings", "/embeddings"):
            return self._send(404, {"error": "not found"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            texts = req["input"] if isinstance(req["input"], list) else [req["input"]]
            vecs = encode([str(t) for t in texts])
        except Exception as e:
            return self._send(400, {"error": str(e)})
        self._send(200, {"object": "list", "model": alias,
                         "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vecs)]})

    def log_message(self, *args):
        pass


print(f"embed-server: {alias} ({a.pooling} pooling) on http://127.0.0.1:{a.port}/v1", flush=True)
ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
