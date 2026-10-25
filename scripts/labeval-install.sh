#!/usr/bin/env bash
# labeval-install.sh — the human's root step for one campaign's hidden labels (docs/labeval.md).
# Never run by lab or by an agent: read it, then run it yourself.
#
#   sudo bash scripts/labeval-install.sh <campaign-id> <evaluator> [helper ...] \
#        [--labels DIR] [--docker IMAGE@sha256:...] [--drop-general-line]
#
#   <evaluator>          the campaign's evaluator (score.py, or any executable); helpers are
#                        files it imports from its own dir (measure.py, …)
#   --labels DIR         DIR/search and DIR/final are copied to /srv/labloop-private/<id>/
#   --docker IMAGE@...   the evaluator runs candidate code in this image: installs a root-owned
#                        sandbox wrapper labeval may run as root, instead of the docker group
#   --drop-general-line  remove /etc/sudoers.d/labloop-eval when it is the old general line
#                        (`… NOPASSWD: /usr/bin/python3`); only once no running campaign uses it
#
# What it leaves:
#   /opt/labloop-eval/<id>/            root:root 755, a copy of the evaluator and its helpers (644)
#   /opt/labloop-eval/<id>/evaluate    root:root 755, the one path the sudoers line names;
#                                      campaign.toml's data.evaluator points here
#   /etc/sudoers.d/labloop-eval-<id>   <you> ALL=(labeval) NOPASSWD: /opt/labloop-eval/<id>/evaluate
#   /srv/labloop-private/<id>/         labeval:labeval 700 (with --labels)
#   with --docker: /opt/labloop-eval/<id>/sandbox (root:root 755), its sudoers line for labeval,
#   and /var/lib/labloop-eval/<id>/work (labeval:labeval 700), the only dir it mounts
set -euo pipefail

die() { echo "labeval-install: $*" >&2; exit 2; }
[ "$(id -u)" = 0 ] || die "run it with sudo (it writes /etc/sudoers.d and root-owned dirs)"
OWNER="${SUDO_USER:-}"
[ -n "$OWNER" ] && [ "$OWNER" != root ] || die "run it with sudo from the account that runs \`lab run\`"

ID="" LABELS="" IMAGE="" DROP=0 FILES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --labels) LABELS="$2"; shift 2 ;;
    --docker) IMAGE="$2"; shift 2 ;;
    --drop-general-line) DROP=1; shift ;;
    -*) die "unknown option $1" ;;
    *) if [ -z "$ID" ]; then ID="$1"; else FILES+=("$1"); fi; shift ;;
  esac
done
[[ "$ID" =~ ^[a-z0-9][a-z0-9-]{1,63}$ ]] || die "first argument is the campaign id (lowercase [a-z0-9-])"
[ "${#FILES[@]}" -ge 1 ] || die "name the evaluator after the campaign id"
for f in "${FILES[@]}"; do [ -f "$f" ] || die "$f is not a file"; done
if [ -n "$IMAGE" ]; then
  [[ "$IMAGE" == *@sha256:* ]] || die "--docker takes an image pinned by digest (name@sha256:…), so the sandbox cannot be swapped by a retag"
  command -v docker >/dev/null || die "--docker given but no docker on PATH"
fi

# --- the eval user ----------------------------------------------------------------------
id labeval >/dev/null 2>&1 || adduser --system --group --no-create-home labeval
if id -nG labeval | tr ' ' '\n' | grep -qx docker; then
  gpasswd -d labeval docker >/dev/null
  echo "removed labeval from the docker group (the sandbox wrapper replaces it)"
fi

# --- the evaluator: a root-owned copy, and the one path sudo may run ----------------------
DST=/opt/labloop-eval/$ID
install -d -o root -g root -m 755 /opt/labloop-eval "$DST"
for f in "${FILES[@]}"; do install -o root -g root -m 644 "$f" "$DST/$(basename "$f")"; done
ENTRY="$DST/$(basename "${FILES[0]}")"
case "$ENTRY" in
  # -E -s: no PYTHON* variables and no user site; the root-owned dir stays first on sys.path
  *.py) RUN="exec /usr/bin/python3 -E -s $ENTRY \"\$@\"" ;;
  *)    chmod 755 "$ENTRY"; RUN="exec $ENTRY \"\$@\"" ;;
esac
cat > "$DST/evaluate.tmp" <<EOF
#!/bin/sh
# labloop evaluator for campaign $ID: runs the root-owned copy beside it, nothing else.
# Installed by scripts/labeval-install.sh; change it only by running that again.
$RUN
EOF
chown root:root "$DST/evaluate.tmp" && chmod 755 "$DST/evaluate.tmp" && mv "$DST/evaluate.tmp" "$DST/evaluate"

if [ -n "$IMAGE" ]; then
  WORKROOT=/var/lib/labloop-eval/$ID/work
  install -d -o root -g root -m 755 /var/lib/labloop-eval
  install -d -o labeval -g labeval -m 700 "/var/lib/labloop-eval/$ID" "$WORKROOT"
  cat > "$DST/sandbox.tmp" <<EOF
#!/bin/sh
# sandbox <workdir> <argv...> — runs argv in $IMAGE with <workdir> as /work, nothing else
# mounted, no network, as labeval. labeval may run this (and only this) as root; it is
# not in the docker group. <workdir> must be labeval's, under $WORKROOT.
set -eu
[ \$# -ge 2 ] || { echo "usage: sandbox <workdir> <argv...>" >&2; exit 2; }
work=\$(realpath -e -- "\$1"); shift
case "\$work" in $WORKROOT/?*) ;; *) echo "sandbox: \$work is not under $WORKROOT" >&2; exit 2 ;; esac
[ -d "\$work" ] && [ "\$(stat -c %U "\$work")" = labeval ] || { echo "sandbox: \$work is not a dir labeval owns" >&2; exit 2; }
exec $(command -v docker) run --rm --network none --cpus 1 --memory 2g --pids-limit 256 \\
  --cap-drop ALL --security-opt no-new-privileges --user $(id -u labeval):$(id -g labeval) \\
  -v "\$work:/work" -w /work $IMAGE "\$@"
EOF
  chown root:root "$DST/sandbox.tmp" && chmod 755 "$DST/sandbox.tmp" && mv "$DST/sandbox.tmp" "$DST/sandbox"
fi

# --- sudoers: one path each, checked before it is installed ------------------------------
SUD=/etc/sudoers.d/labloop-eval-$ID
{
  echo "# labloop campaign $ID (scripts/labeval-install.sh): the evaluator, nothing else"
  echo "$OWNER ALL=(labeval) NOPASSWD: $DST/evaluate"
  [ -z "$IMAGE" ] || echo "labeval ALL=(root) NOPASSWD: $DST/sandbox"
} > "$SUD.tmp"
chmod 440 "$SUD.tmp"
visudo -cf "$SUD.tmp" >/dev/null || { rm -f "$SUD.tmp"; die "visudo rejected the new sudoers file"; }
mv "$SUD.tmp" "$SUD"

GEN=/etc/sudoers.d/labloop-eval
if [ -f "$GEN" ] && grep -qE 'NOPASSWD:[[:space:]]*/usr/bin/python3[[:space:]]*$' "$GEN"; then
  if [ "$DROP" = 1 ]; then
    install -d -o root -g root -m 700 /root/labloop-eval-backup
    mv "$GEN" "/root/labloop-eval-backup/labloop-eval.$(date +%Y%m%d%H%M%S)"
    echo "removed the general line $GEN (backup under /root/labloop-eval-backup)"
  else
    echo "WARNING: $GEN still grants python3 as labeval: any process of yours can read every"
    echo "         label. Re-run with --drop-general-line once no running campaign uses it."
  fi
fi

# --- the labels ----------------------------------------------------------------------------
install -d -o labeval -g labeval -m 700 /srv/labloop-private
if [ -n "$LABELS" ]; then
  for s in search final; do [ -d "$LABELS/$s" ] || die "$LABELS/$s is not a dir"; done
  install -d -o labeval -g labeval -m 700 "/srv/labloop-private/$ID"
  for s in search final; do
    rm -rf "/srv/labloop-private/$ID/$s"
    cp -R "$LABELS/$s" "/srv/labloop-private/$ID/$s"
  done
  chown -R labeval:labeval "/srv/labloop-private/$ID"
  chmod -R go-rwx "/srv/labloop-private/$ID"
  echo "labels installed under /srv/labloop-private/$ID; remove the staged copy in $LABELS yourself"
fi

# --- what still reads every file ----------------------------------------------------------
for g in docker lxd; do
  if id -nG "$OWNER" | tr ' ' '\n' | grep -qx "$g"; then
    echo "WARNING: $OWNER is in the $g group, which mounts any path, /srv/labloop-private included."
    echo "         A worker running as $OWNER can read the labels that way; see docs/labeval.md."
  fi
done

# --- check ------------------------------------------------------------------------------------
if sudo -u "$OWNER" sudo -n -u labeval /usr/bin/python3 -c 'pass' 2>/dev/null; then
  echo "CHECK FAILED: $OWNER can still run python3 as labeval"
else
  echo "check: $OWNER cannot run python3 as labeval"
fi
sudo -l -U "$OWNER" 2>/dev/null | grep -F "$DST/evaluate" >/dev/null \
  && echo "check: $OWNER may run $DST/evaluate as labeval" \
  || echo "CHECK FAILED: the sudoers line for $DST/evaluate is not in effect"
cat <<EOF

campaign.toml:
  [data]
  evaluator = "$DST/evaluate"
  [data.search]
  labels = "/srv/labloop-private/$ID/search"
  [data.final]
  labels = "/srv/labloop-private/$ID/final"
  [eval]
  user = "labeval"
EOF
