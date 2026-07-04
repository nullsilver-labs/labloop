#!/usr/bin/env bash
# Generates HW.md — hardware & software inventory for this machine.
# Usage: scripts/hwprobe.sh   (writes HW.md in the repo root)
set -u
cd "$(dirname "$0")/.."
OUT=HW.md

have() { command -v "$1" >/dev/null 2>&1; }

{
  echo "# HW.md — hardware inventory (auto-generated, do not edit)"
  echo
  echo "- Generated: $(date -u +'%Y-%m-%d %H:%M UTC') on host \`$(hostname)\`"
  echo "- Regenerate with: \`scripts/hwprobe.sh\`"
  echo
  echo "## System"
  echo '```'
  uname -srmo
  if [ -r /etc/os-release ]; then . /etc/os-release; echo "OS: ${PRETTY_NAME:-unknown}"; fi
  echo '```'
  echo
  echo "## CPU"
  echo '```'
  if have lscpu; then
    lscpu | grep -E '^(Model name|Socket|Core|Thread|CPU\(s\)|CPU max MHz)' || true
  else
    grep -m1 'model name' /proc/cpuinfo || echo "unknown"
  fi
  echo '```'
  echo
  echo "## Memory"
  echo '```'
  free -h | head -2
  echo '```'
  echo
  echo "## GPUs"
  echo '```'
  if have nvidia-smi; then
    nvidia-smi --query-gpu=index,name,memory.total,driver_version,compute_cap \
      --format=csv,noheader 2>/dev/null || nvidia-smi -L
    echo "CUDA (driver): $(nvidia-smi | grep -oP 'CUDA Version: \K[0-9.]+' | head -1)"
  elif have rocm-smi; then
    rocm-smi --showproductname 2>/dev/null || echo "rocm-smi present, query failed"
  else
    echo "none detected"
  fi
  echo '```'
  echo
  echo "## Disk (repo filesystem)"
  echo '```'
  df -h . | tail -1 | awk '{print "size:", $2, " used:", $3, " free:", $4, " ("$5" used)"}'
  echo '```'
  echo
  echo "## Software"
  echo '```'
  have python3 && echo "python: $(python3 --version 2>&1)"
  python3 - <<'PY' 2>/dev/null || true
for m in ("torch", "transformers", "numpy", "jax", "tensorflow"):
    try:
        mod = __import__(m)
        extra = ""
        if m == "torch":
            extra = f" (cuda {mod.version.cuda}, cudnn {mod.backends.cudnn.version()})" if mod.cuda.is_available() else " (no cuda)"
        print(f"{m}: {mod.__version__}{extra}")
    except Exception:
        pass
PY
  have git && echo "git: $(git --version | awk '{print $3}')"
  echo '```'
} > "$OUT"

echo "wrote $OUT"
