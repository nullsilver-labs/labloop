#!/usr/bin/env bash
# matched_audit.sh — one read-only terminal-audit snapshot of a matched-pair arm.
#
#   scripts/matched_audit.sh ARM_ROOT BUNDLE_ROOT
#
# Prints what LAUNCH.md asks the operator to check before the next arm or the
# comparison: campaign status, watcher registry (anything not terminal), frozen
# bundle hashes, GPU/process state, and the newest write under candidates/ so two
# snapshots taken minutes apart show whether anything is still writing. It changes
# nothing; run it twice, separated, and keep both outputs as evidence files.
set -u
arm=$(cd "$1" && pwd) || exit 2
bundle=$(cd "$2" && pwd) || exit 2
echo "# audit snapshot $(date -u +%Y-%m-%dT%H:%M:%SZ)  arm=$arm"
echo
echo "## campaign"
(cd "$arm" && tools/lab campaign status 2>&1 | head -2)
echo
echo "## watchers not terminal (expect none)"
(cd "$arm" && tools/lab watch list --json 2>/dev/null | python3 -c '
import json,sys
ws=json.load(sys.stdin)
live=[w for w in ws if w.get("status") not in ("done","killed","failed")]
print("none" if not live else "\n".join("%s %s pid=%s child=%s" % (w["id"], w["status"], w.get("pid"), w.get("child_pid")) for w in live))
print("registry: %d live records; done/: " % len(ws), end="")'; ls "$arm/.lab/watch/done" 2>/dev/null | wc -l)
echo
echo "## cleanup_error in watcher records (expect none)"
grep -l '"cleanup_error"' "$arm"/.lab/watch/*.json "$arm"/.lab/watch/done/*.json 2>/dev/null || echo none
echo
echo "## frozen bundle hashes"
(cd "$bundle" && sha256sum -c --quiet SHA256SUMS && echo "all $(grep -c . SHA256SUMS) entries match")
echo
echo "## GPU"
nvidia-smi --query-gpu=index,uuid,utilization.gpu,memory.used --format=csv,noheader
echo "compute processes:"; nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | sed 's/^/  /'; echo "  (end)"
echo
echo "## processes referencing the arm (expect none after settlement)"
pgrep -af "$arm" | grep -v "matched_audit" | cut -c1-150 || echo none
echo
echo "## newest writes under candidates/ (compare across two snapshots)"
find "$arm/candidates" -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %p\n' 2>/dev/null | sort | tail -5 | sed "s|$arm/||"
echo
echo "## population"
python3 - "$arm" <<'PY'
import json,sys,os
P=json.load(open(os.path.join(sys.argv[1],"population.json")))
print(f"status {P['status']} settled {P.get('settled')} gpu_seconds {P.get('gpu_seconds')} stop {P.get('stop_reason')!r} final {P.get('final')} claim {P.get('claim')}")
PY
