#!/usr/bin/env bash
# Stage A2 VERDICT run: n=400 PAIRED (G-M2) head-to-head, iter_11 both sides,
# confirming the wave-1 screen finding (c_puct=2.0 >> production 3.0) + bracket,
# plus an FPU screen. Paired = each deck played both colors → first-player
# advantage cancels (the wave-1 self-cell came out 42% unpaired; paired should
# be ~50%, which the self_c3 cell VALIDATES). Seeds at 1e9 (G-M6, no self-play
# collision). 3 boxes, disjoint DECK shards (offsets = cumulative games/2).
#
# Launch: nohup nice -n 19 bash /home/doctor/sweep_stageA_verdict.sh > /tmp/verdictA.log 2>&1 & disown
set -uo pipefail

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

# Per-box game shares for an n=400 cell (sum=400, all even). FPU cells override to n=200.
# label|newc|oldc|newfpu|oldfpu|iter|vsiter|ngames|seedbase
#   fpu "none" => omit the flag (legacy q=0). seedbase distinct per cell (+1e6).
CELLS=(
  "self_c3|3.0|3.0|none|none|3|30|400|1000000000"
  "c15|1.5|3.0|none|none|15|30|400|1001000000"
  "c20|2.0|3.0|none|none|20|30|400|1002000000"
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
  # per-box game shares proportional to ~16/12/10 threads, all even, summing to ng
  local n5 nl nx
  n5=$(( (ng*40/100) / 2 * 2 )); nl=$(( (ng*35/100) / 2 * 2 )); nx=$(( ng - n5 - nl ))
  # deck-shard offsets (paired → each box consumes ng_box/2 deck seeds)
  local ss5 ssl ssx; ss5=$sbase; ssl=$(( sbase + n5/2 )); ssx=$(( sbase + n5/2 + nl/2 ))
  echo ""; echo "########## CELL $label  newc=$newc oldc=$oldc newfpu=$newfpu  n=$ng PAIRED -> $celldir @ $(date) ##########"
  reap
  local nf of; nf=$(fpu_flag "$newfpu"); of=$(ofpu_flag "$oldfpu")
  local common="--iter $it --vs-iter $vit --sims $SIMS --leaf-eval v2_5 --new-c-puct $newc --old-c-puct $oldc $nf $of --no-elo-log --paired"

  # 5800x
  nohup bash -c "cd $REPO && env $ENVV nice -n 19 $PY -u scripts/eval_iter_head_to_head.py --new-checkpoint $CKPT_LOCAL --old-checkpoint $CKPT_LOCAL --output-root $OUT_LOCAL/$label $common --workers 14 --games $n5 --seed-start $ss5" \
    > /tmp/verdictA_5800x_$label.log 2>&1 < /dev/null & disown
  echo "  5800x ss=$ss5 n=$n5 W=14"
  # laptop
  nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 laptop \
    "cd $LAPTOP_REPO && env $ENVV nice -n 19 $PY -u scripts/eval_iter_head_to_head.py --new-checkpoint $ck_remote --old-checkpoint $ck_remote --output-root $out_remote/$label $common --workers 12 --games $nl --seed-start $ssl" \
    > /tmp/verdictA_laptop_$label.log 2>&1 < /dev/null & disown
  echo "  laptop ss=$ssl n=$nl W=12"
  # xeon (stage + held-ssh, operators inside the .sh)
  cat > "$CODE_SYNC/launch_xeon_verdictA.sh" <<EOF
#!/usr/bin/env bash
set -uo pipefail
SHARE=$SHARE_REMOTE
mountpoint -q "\$SHARE" || sudo mount -t cifs //192.168.0.195/carc-shared "\$SHARE" -o credentials=/home/doctor/.carc-smb.creds,uid=1000,gid=1000,forceuid,forcegid,file_mode=0644,dir_mode=0755,vers=3.1.1,nobrl,actimeo=1,noserverino
mountpoint -q "\$SHARE" || { echo "FATAL: \$SHARE not mounted" >&2; exit 1; }
cd $XEON_REPO || exit 1
env $ENVV nice -n 19 $PY -u scripts/eval_iter_head_to_head.py --new-checkpoint $ck_remote --old-checkpoint $ck_remote --output-root $out_remote/$label $common --workers 10 --games $nx --seed-start $ssx
EOF
  chmod +x "$CODE_SYNC/launch_xeon_verdictA.sh"
  ssh -o ConnectTimeout=15 xeon "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/stage_launcher.sh verdictA'" > /tmp/verdictA_xeon_stage_$label.log 2>&1 || echo "  [xeon] stage rc=$?"
  nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 xeon \
    "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/launch_xeon_verdictA.sh'" > /tmp/verdictA_xeon_$label.log 2>&1 < /dev/null & disown
  echo "  xeon ss=$ssx n=$nx W=10"

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

echo "=== STAGE-A2 VERDICT (n=400 PAIRED) @ $(date) ; ckpt=$(basename "$CKPT_LOCAL") sims=$SIMS ==="
for spec in "${CELLS[@]}"; do run_cell "$spec"; done
echo ""; echo "=== VERDICT DONE @ $(date) ==="
for spec in "${CELLS[@]}"; do
  IFS='|' read -r label _ _ _ _ it vit _ _ <<< "$spec"
  nn=$(printf "%02d" "$it"); vv=$(printf "%02d" "$vit")
  tally_cell "$label" "$OUT_LOCAL/$label/eval/iter_${nn}_vs_${vv}"
done
