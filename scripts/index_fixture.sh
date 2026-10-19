#!/usr/bin/env bash
# The zero-GPU fixture of docs/experiment-index-plan.md §4.1: every finished Sonnet arm on
# engram w0, namespaced, as one population. usage: scripts/index_fixture.sh OUT.sqlite3 [--stem]
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd); up=$(dirname "$here")
out=$1; shift
"$here/tools/lab" index --db "$out" build "$@" \
  --arm mem1L="$up/labloop-engram-mem-legacy-20260913"  --arm mem1F="$up/labloop-engram-mem-findings-20260913" \
  --arm mem2L="$up/labloop-mem2-legacy-20260914"        --arm mem2F="$up/labloop-mem2-findings-20260914" \
  --arm mem3L="$up/labloop-mem3-legacy-20260915"        --arm mem3F="$up/labloop-mem3-findings-20260915" \
  --arm dr1="$up/labloop-drafts-1-20260914"             --arm dr4="$up/labloop-drafts-4-20260914" \
  --arm mixed="$up/labloop-mixed-20260914-arm"
