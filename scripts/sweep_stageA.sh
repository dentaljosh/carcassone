#!/usr/bin/env bash
# Stage A2 sweep (wave 1): re-sweep v2.7 leaf CAP (owed after C1) + c_puct (owed
# after C2) on the NEW base-only bug-fixed game. Same checkpoint (iter_11) BOTH
# sides via eval_iter_head_to_head.py + --leaf-eval v2_5, so the ONLY difference
# per cell is the swept knob — isolates its effect on the production NeuralMCTS
# player. n=100 screen per cell, 3 boxes, disjoint seed shards into one cell dir
# (mirrors run_rebaseline.sh; resumable via per-game JSON). Winners -> n=400.
#
# Launch: nohup nice -n 19 bash /home/doctor/sweep_stageA.sh > /tmp/sweepA.log 2>&1 & disown
set -uo pipefail

REPO=/home/doctor/projects/carcassone
SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
CODE_SYNC=$SHARE_LOCAL/code_sync
LAPTOP_REPO=/home/pop/carcassone
XEON_REPO=/home/doctor/projects/carcassone
PY=.venv/bin/python
# Leave CAP/DROP at production defaults in the env; the per-cell --new/old-leaf-cap
# flags override the cap, drop-3-open stays = production (1) for the whole wave.
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"

CKPT_LOCAL="${CKPT:-$SHARE_LOCAL/pathb_loop/ckpt/iter_11.pt}"
SIMS="${SIMS:-200}"
OUT_LOCAL="${OUT:-$SHARE_LOCAL/sweepA}"
NGAMES="${NGAMES:-100}"
POLL="${POLL:-30}"
ck_remote=$(echo "$CKPT_LOCAL" | sed "s|^$SHARE_LOCAL|$SHARE_REMOTE|")
out_remote=$(echo "$OUT_LOCAL" | sed "s|^$SHARE_LOCAL|$SHARE_REMOTE|")

# Per-box shard sizes (sum must == NGAMES). Proportional to box speed.
declare -A SHARE_N=( [5800x]=40 [laptop]=35 [xeon]=25 )
declare -A SHARE_W=( [5800x]=14 [laptop]=12 [xeon]=10 )

# Cells: label|new_cap|old_cap|new_c|old_c|iter|vsiter|seedbase
# baseline = cap12 c3 (production). self-cell = noise sanity (~50% expected).
CELLS=(
  "self_cap12_c3|12|12|3.0|3.0|11|11|710000"
  "cap08|8|12|3.0|3.0|8|12|711000"
  "cap16|16|12|3.0|3.0|16|12|712000"
  "cpuct2|12|12|2.0|3.0|20|30|713000"
  "cpuct4|12|12|4.0|3.0|40|30|714000"
)

reap() {
  pkill -TERM -f eval_iter_head_to_head 2>/dev/null || true
  ssh -o ConnectTimeout=10 xeon "wsl -d Ubuntu-24.04 -- pkill -TERM -f eval_iter_head_to_head" 2>/dev/null || true
  ssh -o ConnectTimeout=10 laptop "pkill -TERM -f eval_iter_head_to_head" 2>/dev/null || true
  sleep 4
}

run_cell() {
  local spec=$1
  IFS='|' read -r label ncap ocap nc oc it vit sbase <<< "$spec"
  local nn vv celldir
  nn=$(printf "%02d" "$it"); vv=$(printf "%02d" "$vit")
  celldir=$OUT_LOCAL/$label/eval/iter_${nn}_vs_${vv}
  mkdir -p "$celldir"
  local have
  have=$(find "$celldir" -maxdepth 1 -name 's*.json' 2>/dev/null | wc -l)
  if [ "$have" -ge "$NGAMES" ]; then echo "[$label] already has $have/$NGAMES — skip"; return 0; fi
  echo ""; echo "########## CELL $label (new_cap=$ncap old_cap=$ocap new_c=$nc old_c=$oc) -> $celldir @ $(date) ##########"
  reap

  local s5 sl sx
  s5=$sbase; sl=$((sbase + SHARE_N[5800x])); sx=$((sbase + SHARE_N[5800x] + SHARE_N[laptop]))

  # 5800x (local)
  local lcommon5="--new-checkpoint $CKPT_LOCAL --old-checkpoint $CKPT_LOCAL --output-root $OUT_LOCAL/$label --iter $it --vs-iter $vit --sims $SIMS --leaf-eval v2_5 --new-c-puct $nc --old-c-puct $oc --new-leaf-cap $ncap --old-leaf-cap $ocap --no-elo-log"
  nohup bash -c "cd $REPO && env $ENVV nice -n 19 $PY -u scripts/eval_iter_head_to_head.py $lcommon5 --workers ${SHARE_W[5800x]} --games ${SHARE_N[5800x]} --seed-start $s5" \
    > /tmp/sweepA_5800x_$label.log 2>&1 < /dev/null & disown
  echo "  launched 5800x ss=$s5 n=${SHARE_N[5800x]} W=${SHARE_W[5800x]}"

  # laptop / xeon (remote paths)
  local lcommon="--new-checkpoint $ck_remote --old-checkpoint $ck_remote --output-root $out_remote/$label --iter $it --vs-iter $vit --sims $SIMS --leaf-eval v2_5 --new-c-puct $nc --old-c-puct $oc --new-leaf-cap $ncap --old-leaf-cap $ocap --no-elo-log"
  nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 laptop \
    "cd $LAPTOP_REPO && env $ENVV nice -n 19 $PY -u scripts/eval_iter_head_to_head.py $lcommon --workers ${SHARE_W[laptop]} --games ${SHARE_N[laptop]} --seed-start $sl" \
    > /tmp/sweepA_laptop_$label.log 2>&1 < /dev/null & disown
  echo "  launched laptop ss=$sl n=${SHARE_N[laptop]} W=${SHARE_W[laptop]}"

  # xeon (stage + held-ssh FG, operators inside the .sh)
  cat > "$CODE_SYNC/launch_xeon_sweepA.sh" <<EOF
#!/usr/bin/env bash
set -uo pipefail
SHARE=$SHARE_REMOTE
mountpoint -q "\$SHARE" || sudo mount -t cifs //192.168.0.195/carc-shared "\$SHARE" -o credentials=/home/doctor/.carc-smb.creds,uid=1000,gid=1000,forceuid,forcegid,file_mode=0644,dir_mode=0755,vers=3.1.1,nobrl,actimeo=1,noserverino
mountpoint -q "\$SHARE" || { echo "FATAL: \$SHARE not mounted" >&2; exit 1; }
cd $XEON_REPO || exit 1
env $ENVV nice -n 19 $PY -u scripts/eval_iter_head_to_head.py $lcommon --workers ${SHARE_W[xeon]} --games ${SHARE_N[xeon]} --seed-start $sx
EOF
  chmod +x "$CODE_SYNC/launch_xeon_sweepA.sh"
  ssh -o ConnectTimeout=15 xeon "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/stage_launcher.sh sweepA'" > /tmp/sweepA_xeon_stage_$label.log 2>&1 || echo "  [xeon] stage rc=$? (continuing)"
  nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 xeon \
    "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/launch_xeon_sweepA.sh'" > /tmp/sweepA_xeon_$label.log 2>&1 < /dev/null & disown
  echo "  launched xeon ss=$sx n=${SHARE_N[xeon]} W=${SHARE_W[xeon]}"

  # wait
  local stuck=0 prev=-1 cnt
  while true; do
    cnt=$(find "$celldir" -maxdepth 1 -name 's*.json' 2>/dev/null | wc -l)
    echo "[$(date +%H:%M)] $label $cnt/$NGAMES"
    [ "$cnt" -ge "$NGAMES" ] && { echo "[$label] COMPLETE $cnt/$NGAMES"; break; }
    [ "$cnt" -eq "$prev" ] && stuck=$((stuck+1)) || stuck=0
    prev=$cnt
    [ "$stuck" -ge 30 ] && { echo "[$label] NO PROGRESS 30*POLL — moving on at $cnt/$NGAMES @ $(date)"; break; }
    sleep "$POLL"
  done
  reap
  tally_cell "$label" "$celldir"
}

tally_cell() {
  local label=$1 dir=$2
  "$REPO/$PY" - "$label" "$dir" <<'PYT'
import json, sys, glob, os, math
label, d = sys.argv[1], sys.argv[2]
w=l=dr=0; diff=0.0
for f in glob.glob(os.path.join(d, "s*.json")):
    try: r = json.load(open(f))
    except Exception: continue
    if r.get("drew"): dr += 1
    elif r.get("won_by_new"): w += 1
    else: l += 1
    diff += float(r.get("score_diff_new", r.get("avg_diff", 0)) or 0)
tot = w+l+dr
wr = (w + 0.5*dr)/tot if tot else 0.0
# elo from wr; sigma on wr -> elo
elo = -400*math.log10(1/wr-1) if 0<wr<1 else 0.0
se = math.sqrt(wr*(1-wr)/tot) if tot else 0.0
print(f"  >>> SWEEP-A {label}: {w}W/{dr}D/{l}L of {tot}  wr={wr:.1%}  elo~{elo:+.1f}  (se={se*100:.1f}pp, avgdiff={diff/max(1,tot):+.1f})")
PYT
}

echo "=== STAGE-A SWEEP (wave 1: cap + c_puct) @ $(date) ; ckpt=$(basename "$CKPT_LOCAL") sims=$SIMS n=$NGAMES/cell ==="
for spec in "${CELLS[@]}"; do run_cell "$spec"; done
echo ""; echo "=== STAGE-A SWEEP WAVE 1 DONE @ $(date) ==="
echo "Summary of all cells:"
for spec in "${CELLS[@]}"; do
  IFS='|' read -r label _ _ _ _ it vit _ <<< "$spec"
  nn=$(printf "%02d" "$it"); vv=$(printf "%02d" "$vit")
  tally_cell "$label" "$OUT_LOCAL/$label/eval/iter_${nn}_vs_${vv}"
done
