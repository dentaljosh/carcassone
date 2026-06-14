#!/usr/bin/env bash
# cluster_resume_after_fan.sh — resume the deepteacher flywheel after the 5800x came
# back from the VRM fan install (2026-06-14). Run this ON the 5800x once it's booted
# and the Windows CIFS share is re-serving. Safe to run even after an UNgraceful
# power-off (it pre-cleans whatever was left in-flight).
#
# It: (1) pre-cleans stranded .claim files (killed in-flight games) so the iter9
# selection doesn't 30-min-stall-then-heal, (2) relaunches the orchestrator START=9,
# which SKIPS the done iter9 gen (done/gen9 marker) and RESUMES the partial iter9
# selection on all 3 boxes (5800x+xeon+laptop) via --shared-claim, then continues
# iters 10-12 + the sealed confirmation. best.pt=iter8 is already safe on disk.
set -uo pipefail
REPO=/home/doctor/projects/carcassone; cd "$REPO" || exit 1
SHARE=/mnt/c/carc-shared
TAG=deepteacher
echo "=== resume $TAG after fan @ $(date) ==="

# 0) sanity — is the share back?
[ -d "$SHARE/$TAG" ] || { echo "FATAL: $SHARE/$TAG missing — Windows share not re-served / WSL mount down. Fix the mount first."; exit 1; }
[ -f "$SHARE/flywheel_residual_attempt2/ckpt/iter8.pt" ] || { echo "FATAL: ITER0 ckpt (iter8) missing on share — wrong mount?"; exit 1; }

# 1) pre-clean stranded claims (claim with no result) — gen9 npz + both iter9 selection sides
_clean() {  # $1=dir $2=result-ext
  local d="$1" ext="$2" n=0
  [ -d "$d" ] || { echo "  (skip, no dir: $(basename "$d"))"; return; }
  for c in "$d"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.$ext" ] || { rm -f "$c"; n=$((n+1)); }; done
  echo "  cleaned $n stranded claims in $(basename "$d")"
}
_clean "$SHARE/$TAG/iter9_data/iter_00" npz
_clean "$SHARE/$TAG/odo/sel_it9_new"  json
_clean "$SHARE/$TAG/odo/sel_it9_best" json

# 2) remotes: confirm share mounted (fstab nofail should auto-remount; best-effort remount if stale)
for h in laptop xeon-wsl; do
  r=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$h" 'mountpoint -q /mnt/carc-shared && echo OK || echo NOMOUNT' </dev/null 2>/dev/null) || r=UNREACHABLE
  if [ "$r" = NOMOUNT ]; then
    ssh -o ConnectTimeout=15 "$h" 'sudo mount -a 2>/dev/null; mountpoint -q /mnt/carc-shared && echo remounted || echo STILL-DOWN' </dev/null 2>/dev/null
    r="(remount attempted)"
  fi
  echo "  $h share: $r"
done

# 3) relaunch orchestrator START=9 (resumes iter9 selection → iters 10-12 → sealed)
FLYWHEEL_TAG=$TAG SIMS=800 START=9 ITERS=12 \
  ITER0_CKPT=$SHARE/flywheel_residual_attempt2/ckpt/iter8.pt \
  nohup nice -n 19 bash scripts/run_residual_flywheel_v2.sh > /tmp/deepteacher_postfan.log 2>&1 &
disown
echo "  orchestrator relaunched pid $! -> /tmp/deepteacher_postfan.log"
echo "=== RESUMED. Watch: tail -f /tmp/deepteacher_postfan.log  |  selection log: $SHARE/$TAG/selection.csv ==="
