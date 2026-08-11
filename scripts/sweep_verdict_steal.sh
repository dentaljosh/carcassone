#!/usr/bin/env bash
# Stage A2 VERDICT — WORK-STEALING variant (Joshua: "work-steal whenever possible").
# Remaining cells only: c25 (reuses the 318 already on disk), fpu02, fpu04.
# All 3 boxes point at the SAME full seed range per cell with --shared-claim;
# they atomically claim (seed,player) via .claim sidecars, so no box sits idle
# while another grinds the tail. exists-check skips the already-done c25 games.
#
# Launch: nohup nice -n 19 bash /home/doctor/sweep_verdict_steal.sh > /tmp/verdictS.log 2>&1 & disown
set -uo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

REPO=/home/doctor/projects/carcassone
SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
CODE_SYNC=$SHARE_LOCAL/code_sync
LAPTOP_REPO=/home/pop/carcassone
XEON_REPO=/home/doctor/projects/carcassone
PY=.venv/bin/python
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"

CKPT_LOCAL="${CKPT:-$SHARE_LOCAL/pathb_loop/ckpt/iter_11.pt}"
SIMS="${SIMS:-200}"
OUT_LOCAL="${OUT:-$SHARE_LOCAL/verdictA}"
POLL="${POLL:-30}"
ck_remote=$(echo "$CKPT_LOCAL" | sed "s|^$SHARE_LOCAL|$SHARE_REMOTE|")
out_remote=$(echo "$OUT_LOCAL" | sed "s|^$SHARE_LOCAL|$SHARE_REMOTE|")

# label|newc|oldc|newfpu|oldfpu|iter|vsiter|ngames|seedbase
CELLS=(
  "c25|2.5|3.0|none|none|25|30|400|1003000000"
  "fpu02|3.0|3.0|0.2|none|2|31|200|1004000000"
  "fpu04|3.0|3.0|0.4|none|4|31|200|1005000000"
)

reap() {
  pkill -9 -f eval_iter_head_to_head 2>/dev/null || true
  pkill -9 -f multiprocessing.spawn 2>/dev/null || true
  ssh -o ConnectTimeout=10 xeon "wsl -d Ubuntu-24.04 -- pkill -9 -f eval_iter_head_to_head" 2>/dev/null || true
  ssh -o ConnectTimeout=10 laptop "pkill -9 -f eval_iter_head_to_head" 2>/dev/null || true
  sleep 4
}

fpu_flag() { [ "$1" = "none" ] && echo "" || echo "--new-fpu $1"; }
ofpu_flag() { [ "$1" = "none" ] && echo "" || echo "--old-fpu $1"; }

run_cell() {
  IFS='|' read -r label newc oldc newfpu oldfpu it vit ng sbase <<< "$1"
  local nn vv celldir; nn=$(printf "%02d" "$it"); vv=$(printf "%02d" "$vit")
  celldir=$OUT_LOCAL/$label/eval/iter_${nn}_vs_${vv}; mkdir -p "$celldir"
  local have; have=$(find "$celldir" -maxdepth 1 -name 's*.json' 2>/dev/null | wc -l)
  if [ "$have" -ge "$ng" ]; then echo "[$label] already $have/$ng — skip"; return 0; fi
  echo ""; echo "########## CELL $label  newc=$newc oldc=$oldc newfpu=$newfpu  n=$ng PAIRED SHARED-CLAIM (have $have) @ $(date) ##########"
  reap
  local nf of; nf=$(fpu_flag "$newfpu"); of=$(ofpu_flag "$oldfpu")
  # IDENTICAL across boxes: full seed range + shared-claim. Boxes race to claim.
  local common="--iter $it --vs-iter $vit --sims $SIMS --leaf-eval v2_5 --new-c-puct $newc --old-c-puct $oldc $nf $of --no-elo-log --paired --shared-claim --seed-start $sbase --games $ng"

  # 5800x
  nohup bash -c "cd $REPO && env $ENVV nice -n 19 $PY -u scripts/eval_iter_head_to_head.py --new-checkpoint $CKPT_LOCAL --old-checkpoint $CKPT_LOCAL --output-root $OUT_LOCAL/$label $common --workers 14 --claim-host 5800x" \
    > /tmp/verdictS_5800x_$label.log 2>&1 < /dev/null & disown
  echo "  5800x W=14 (claim)"
  # laptop
  nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 laptop \
    "cd $LAPTOP_REPO && env $ENVV nice -n 19 $PY -u scripts/eval_iter_head_to_head.py --new-checkpoint $ck_remote --old-checkpoint $ck_remote --output-root $out_remote/$label $common --workers 12 --claim-host laptop" \
    > /tmp/verdictS_laptop_$label.log 2>&1 < /dev/null & disown
  echo "  laptop W=12 (claim)"
  # xeon (stage + held-ssh, operators inside the .sh)
  cat > "$CODE_SYNC/launch_xeon_verdictS.sh" <<EOF
#!/usr/bin/env bash
set -uo pipefail
SHARE=$SHARE_REMOTE
mountpoint -q "\$SHARE" || sudo mount -t cifs //192.168.0.195/carc-shared "\$SHARE" -o credentials=/home/doctor/.carc-smb.creds,uid=1000,gid=1000,forceuid,forcegid,file_mode=0644,dir_mode=0755,vers=3.1.1,nobrl,actimeo=1,noserverino
mountpoint -q "\$SHARE" || { echo "FATAL: \$SHARE not mounted" >&2; exit 1; }
cd $XEON_REPO || exit 1
env $ENVV nice -n 19 $PY -u scripts/eval_iter_head_to_head.py --new-checkpoint $ck_remote --old-checkpoint $ck_remote --output-root $out_remote/$label $common --workers 10 --claim-host xeon
EOF
  chmod +x "$CODE_SYNC/launch_xeon_verdictS.sh"
  ssh -o ConnectTimeout=15 xeon "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/stage_launcher.sh verdictS'" > /tmp/verdictS_xeon_stage_$label.log 2>&1 || echo "  [xeon] stage rc=$?"
  nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 xeon \
    "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/launch_xeon_verdictS.sh'" > /tmp/verdictS_xeon_$label.log 2>&1 < /dev/null & disown
  echo "  xeon W=10 (claim)"

  local stuck=0 prev=-1 cnt
  while true; do
    cnt=$(find "$celldir" -maxdepth 1 -name 's*.json' 2>/dev/null | wc -l)
    echo "[$(date +%H:%M)] $label $cnt/$ng"
    [ "$cnt" -ge "$ng" ] && { echo "[$label] COMPLETE $cnt/$ng"; break; }
    [ "$cnt" -eq "$prev" ] && stuck=$((stuck+1)) || stuck=0; prev=$cnt
    [ "$stuck" -ge 30 ] && { echo "[$label] NO PROGRESS — moving on at $cnt/$ng"; break; }
    sleep "$POLL"
  done
  reap
  tally_cell "$label" "$celldir"
}

tally_cell() {
  "$REPO/$PY" - "$1" "$2" <<'PYT'
import json,sys,glob,os,math
label,d=sys.argv[1],sys.argv[2]
w=l=dr=0
for f in glob.glob(os.path.join(d,"s*.json")):
    try:r=json.load(open(f))
    except:continue
    if r.get("drew"):dr+=1
    elif r.get("won_by_new"):w+=1
    else:l+=1
t=w+l+dr; wr=(w+0.5*dr)/t if t else 0
elo=-400*math.log10(1/wr-1) if 0<wr<1 else 0
se=math.sqrt(wr*(1-wr)/t)*100 if t else 0
z=(wr-0.5)/(se/100) if se else 0
print(f"  >>> VERDICT {label}: {w}W/{dr}D/{l}L of {t}  wr={wr:.1%}  elo~{elo:+.1f}  (se={se:.1f}pp, z={z:+.2f} vs 50%)")
PYT
}

echo "=== STAGE-A2 VERDICT (WORK-STEALING) @ $(date) ; ckpt=$(basename "$CKPT_LOCAL") sims=$SIMS ==="
for spec in "${CELLS[@]}"; do run_cell "$spec"; done
echo ""; echo "=== VERDICT-STEAL DONE @ $(date) ==="
for spec in "${CELLS[@]}"; do
  IFS='|' read -r label _ _ _ _ it vit _ _ <<< "$spec"
  nn=$(printf "%02d" "$it"); vv=$(printf "%02d" "$vit")
  tally_cell "$label" "$OUT_LOCAL/$label/eval/iter_${nn}_vs_${vv}"
done
