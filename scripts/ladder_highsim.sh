#!/usr/bin/env bash
# Overnight HIGH-SIM HeuristicMCTS reference rung (measurement-wall yardstick).
# iter_11 (current best) vs HeuristicMCTS at MATCHED high sims, 3 boxes, DISJOINT
# seed shards (proven legacy eval_net_vs_heuristic path — robustness over
# work-stealing for an unattended run; per-game JSON = resumable). All boxes write
# to the same --out-subdir on the share → consolidates. Detached; survives logout.
#
# Launch: nohup nice -n 19 bash /home/doctor/ladder_highsim.sh > /tmp/ladder.log 2>&1 & disown
set -uo pipefail

REPO=/home/doctor/projects/carcassone
SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
CODE_SYNC=$SHARE_LOCAL/code_sync
LAPTOP_REPO=/home/pop/carcassone
XEON_REPO=/home/doctor/projects/carcassone
PY=.venv/bin/python
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"

CKPT_LOCAL=$SHARE_LOCAL/pathb_loop/ckpt/iter_11.pt
CKPT_REMOTE=$SHARE_REMOTE/pathb_loop/ckpt/iter_11.pt
SIMS=${SIMS:-800}
CPUCT=3.0
SUBDIR=iter11_s${SIMS}_h${SIMS}_c30
OUTROOT_LOCAL=$SHARE_LOCAL/ladder_highsim
OUTROOT_REMOTE=$SHARE_REMOTE/ladder_highsim
NTOTAL=${NTOTAL:-800}
SB=${SB:-1000000000}   # clean-eval floor 1e9 (eval_net_vs_heuristic hard-errors on seed<1e9)
POLL=120

# disjoint shards proportional to throughput (5800x .40 / laptop .35 / xeon .25)
n5=$(( NTOTAL*40/100 )); nl=$(( NTOTAL*35/100 )); nx=$(( NTOTAL - n5 - nl ))
s5=$SB; sl=$(( SB + n5 )); sx=$(( SB + n5 + nl ))
celldir=$OUTROOT_LOCAL/$SUBDIR
mkdir -p "$celldir"

echo "=== LADDER HIGH-SIM @ $(date) : iter_11 vs HeuristicMCTS sims=$SIMS n=$NTOTAL (5800x=$n5 laptop=$nl xeon=$nx) ==="

# --- 5800x (local) ---
nohup bash -c "cd $REPO && env $ENVV nice -n 19 $PY -u scripts/eval_net_vs_heuristic.py --checkpoint $CKPT_LOCAL --n $n5 --sims $SIMS --heur-sims $SIMS --c-puct $CPUCT --workers 16 --out-root $OUTROOT_LOCAL --out-subdir $SUBDIR --seed-start $s5" \
  > /tmp/ladder_5800x.log 2>&1 < /dev/null & disown
echo "  5800x n=$n5 ss=$s5 W=16"

# --- laptop (native, nohup survives) ---
nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 laptop \
  "cd $LAPTOP_REPO && env $ENVV nice -n 19 $PY -u scripts/eval_net_vs_heuristic.py --checkpoint $CKPT_REMOTE --n $nl --sims $SIMS --heur-sims $SIMS --c-puct $CPUCT --workers 12 --out-root $OUTROOT_REMOTE --out-subdir $SUBDIR --seed-start $sl" \
  > /tmp/ladder_laptop.log 2>&1 < /dev/null & disown
echo "  laptop n=$nl ss=$sl W=12"

# --- xeon (held-ssh-FG; operators inside the staged .sh) ---
cat > "$CODE_SYNC/launch_xeon_ladder.sh" <<EOF
#!/usr/bin/env bash
set -uo pipefail
SHARE=$SHARE_REMOTE
mountpoint -q "\$SHARE" || sudo mount -t cifs //192.168.0.195/carc-shared "\$SHARE" -o credentials=/home/doctor/.carc-smb.creds,uid=1000,gid=1000,forceuid,forcegid,file_mode=0644,dir_mode=0755,vers=3.1.1,nobrl,actimeo=1,noserverino
mountpoint -q "\$SHARE" || { echo "FATAL: \$SHARE not mounted" >&2; exit 1; }
cd $XEON_REPO || exit 1
env $ENVV nice -n 19 $PY -u scripts/eval_net_vs_heuristic.py --checkpoint $CKPT_REMOTE --n $nx --sims $SIMS --heur-sims $SIMS --c-puct $CPUCT --workers 10 --out-root $OUTROOT_REMOTE --out-subdir $SUBDIR --seed-start $sx
EOF
chmod +x "$CODE_SYNC/launch_xeon_ladder.sh"
ssh -o ConnectTimeout=15 xeon "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/stage_launcher.sh ladder'" > /tmp/ladder_xeon_stage.log 2>&1 || echo "  [xeon] stage rc=$?"
nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 xeon \
  "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/launch_xeon_ladder.sh'" > /tmp/ladder_xeon.log 2>&1 < /dev/null & disown
echo "  xeon n=$nx ss=$sx W=10"

# --- poll to completion (detached launcher; not interactive polling) ---
stuck=0; prev=-1
while true; do
  cnt=$(find "$celldir" -name 'n*.json' 2>/dev/null | wc -l)  # eval_net_vs_heuristic names files n<sims>_h..._seed....json
  echo "[$(date +%H:%M)] ladder $cnt/$NTOTAL"
  [ "$cnt" -ge "$NTOTAL" ] && { echo "[ladder] COMPLETE $cnt/$NTOTAL @ $(date)"; break; }
  [ "$cnt" -eq "$prev" ] && stuck=$((stuck+1)) || stuck=0; prev=$cnt
  [ "$stuck" -ge 60 ] && { echo "[ladder] NO PROGRESS 2h — stop at $cnt/$NTOTAL"; break; }
  sleep $POLL
done

echo "=== TALLY @ $(date) ==="
cd $REPO && env $ENVV $PY scripts/eval_net_vs_heuristic.py --checkpoint $CKPT_LOCAL --n $NTOTAL --sims $SIMS --heur-sims $SIMS --c-puct $CPUCT --out-root $OUTROOT_LOCAL --out-subdir $SUBDIR --seed-start $SB --summary-only
