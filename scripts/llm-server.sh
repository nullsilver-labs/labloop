#!/usr/bin/env bash
# llm-server.sh — a local OpenAI-compatible model server for Pi-backed workers.
#
# Runs llama.cpp's CUDA server image under docker, one GGUF at a time, pinned to one
# GPU, bound to localhost. It is NOT part of `lab run`: start it once, outside any
# campaign, and any client on this host (Pi interactively, a campaign's workers,
# anything OpenAI-compatible) shares it. A campaign only checks, before it starts,
# that the endpoint Pi's models.json names serves the requested model id.
#
#   scripts/llm-server.sh start <alias> [gpu] [ctx]   e.g. start gpt-oss-20b 0 32768
#   scripts/llm-server.sh stop | status | logs
#
# <alias> is the model id Pi uses (providers.local.models[].id in ~/.pi/agent/models.json)
# and the id the server reports on /v1/models; the GGUF it maps to is in MODELS below.
# The docker daemon supervises the container (restart=no); it is a service, not a job,
# so it needs no `lab watch`.
set -euo pipefail

NAME="${LLM_SERVER_NAME:-labloop-llm}"
IMAGE="${LLM_SERVER_IMAGE:-ghcr.io/ggml-org/llama.cpp:server-cuda}"
PORT="${LLM_SERVER_PORT:-8083}"
GGUF_DIR="${LLM_SERVER_MODELS:-/mnt/fast-data/models/ggufs}"

# alias → path under $GGUF_DIR. One line per model a campaign may name.
declare -A MODELS=(
  ["gpt-oss-20b"]="gpt-oss-20b-mxfp4.gguf"
  ["qwen3.8-27b"]="Qwen3.8-27b/Qwen3.8-27B-Q4_K_M.gguf"
  ["qwen3.5-27b"]="Qwen3.5-27B-UD-Q4_K_XL.gguf"
  ["gemma-4-31b"]="gemma-4-31B-it-qat-UD-Q4_K_XL.gguf"
)

cmd="${1:-status}"
case "$cmd" in
  start)
    alias="${2:?usage: llm-server.sh start <alias> [gpu] [ctx]}"
    gpu="${3:-0}"
    ctx="${4:-32768}"
    file="${MODELS[$alias]:-}"
    [ -n "$file" ] || { echo "unknown alias $alias; known: ${!MODELS[*]}" >&2; exit 2; }
    [ -f "$GGUF_DIR/$file" ] || { echo "missing $GGUF_DIR/$file" >&2; exit 2; }
    if docker ps -q -f "name=^${NAME}$" | grep -q .; then
      echo "$NAME is already running: $(docker inspect -f '{{.Config.Cmd}}' "$NAME" | tr -s ' ' | cut -c1-120)"; exit 1
    fi
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker run -d --name "$NAME" --restart=no \
      --gpus "\"device=$gpu\"" \
      -v "$GGUF_DIR:/models:ro" \
      -p "127.0.0.1:$PORT:$PORT" \
      "$IMAGE" \
      -m "/models/$file" --alias "$alias" \
      --host 0.0.0.0 --port "$PORT" \
      -ngl 999 -c "$ctx" -fa on -ctk q8_0 -ctv q8_0 \
      --jinja --parallel 1 --no-warmup >/dev/null
    echo "started $NAME: $alias on gpu $gpu, ctx $ctx, http://127.0.0.1:$PORT/v1"
    for i in $(seq 1 120); do
      if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
        echo "ready: $(curl -s "http://127.0.0.1:$PORT/v1/models" | python3 -c 'import json,sys; print(", ".join(m["id"] for m in json.load(sys.stdin)["data"]))')"
        exit 0
      fi
      if ! docker ps -q -f "name=^${NAME}$" | grep -q .; then
        echo "container exited:" >&2; docker logs --tail 20 "$NAME" >&2; exit 1
      fi
      sleep 2
    done
    echo "not ready after 240 s; see: $0 logs" >&2; exit 1;;
  stop)
    docker rm -f "$NAME" >/dev/null 2>&1 && echo "stopped $NAME" || echo "$NAME was not running";;
  status)
    if docker ps -q -f "name=^${NAME}$" | grep -q .; then
      echo "$NAME: $(docker ps -f "name=^${NAME}$" --format '{{.Status}}')"
      curl -s "http://127.0.0.1:$PORT/v1/models" | python3 -c 'import json,sys; print("serving:", ", ".join(m["id"] for m in json.load(sys.stdin)["data"]))' 2>/dev/null || echo "not answering yet"
    else
      echo "$NAME: not running"; exit 1
    fi;;
  logs)
    docker logs --tail "${2:-50}" "$NAME";;
  *)
    echo "usage: $0 start <alias> [gpu] [ctx] | stop | status | logs [n]" >&2; exit 2;;
esac
