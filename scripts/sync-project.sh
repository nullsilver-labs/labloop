#!/usr/bin/env bash
# sync-project.sh <project-dir> — refresh a campaign project's copy of the labloop
# tooling (tools/, .claude/, templates/, CLAUDE.md, .lab-redact, FORMAT.json) from this repo.
# Evidence (candidates/, population.json, LEDGER.md, events.jsonl, REPORT.md), data and
# campaign.toml are never touched. Run it before a campaign, never during one: a
# running `lab run` must keep the tools it started with.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DST="${1:?usage: sync-project.sh <project-dir>}"
[ -d "$DST" ] || { echo "no such dir: $DST" >&2; exit 1; }
if [ -e "$DST/.lab/campaign.lock" ] && command -v flock >/dev/null 2>&1 \
   && ! flock -n "$DST/.lab/campaign.lock" true 2>/dev/null; then
  echo "refusing: a lab run holds $DST/.lab/campaign.lock" >&2; exit 1
fi
for d in tools .claude templates; do
  rm -rf "$DST/$d.sync-new"
  cp -R "$SRC/$d" "$DST/$d.sync-new"
  # agent worktrees under .claude/ are this repo's scratch, not tooling (2026-09-14:
  # they carried 2 MB of embedded git repos into every arm)
  rm -rf "$DST/$d.sync-new/worktrees"
  rm -rf "$DST/$d.sync-old"
  [ -e "$DST/$d" ] && mv "$DST/$d" "$DST/$d.sync-old"
  mv "$DST/$d.sync-new" "$DST/$d"
  rm -rf "$DST/$d.sync-old"
done
# FORMAT.json is generated from the tools (`lab format sync`); an arm must carry the
# contract of the tools it runs, so it is copied with them
cp "$SRC/CLAUDE.md" "$SRC/.lab-redact" "$SRC/FORMAT.json" "$DST/"
rev="$(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "synced tools/ .claude/ templates/ CLAUDE.md .lab-redact FORMAT.json into $DST from labloop $rev"
