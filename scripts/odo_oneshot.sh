#!/usr/bin/env bash
# One-shot 3-box out-of-lineage ODOMETER (post-flywheel recovery).
# Runs a single net checkpoint @ scale 0.25 vs HeuristicMCTS@800-v2.7, clean seed,
# paired, shared-claim — a faithful replica of run_residual_flywheel.sh's
# run_odometer/_odo_launch (same ENVV/leaf/c-puct/seed) so the result is deck-paired
# comparable to the iter0 odometer (52.5 @ seed 1.5e9, n=200).
#
# WHY: the flywheel's plateau `break` (line 257) fires BEFORE the per-iter odometer
# block (line 260), so the iter3 out-of-lineage odometer was skipped. This recovers it.
#
# Usage: CKPT=<5800x abs path> SUB=<odo subdir> [N=200] [SEED=1500000000] bash scripts/odo_oneshot.sh
set -uo pipefail
export TZ=America/New_York
export PYTHONUNBUFFERED=1

SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
REPO_LOCAL=/home/doctor/projects/carcassone
REPO_XEON=/home/doctor/projects/carcassone
REPO_LAPTOP=/home/pop/carcassone
PY=$REPO_LOCAL/.venv/bin/python
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"
OUT=$SHARE_LOCAL/flywheel_residual_v2
OUTR=$SHARE_REMOTE/flywheel_residual_v2
SCALE=0.25; SIMS=200; HEUR_SIMS=800
N=${N:-200}; SEED=${SEED:-1500000000}
CKPT=${CKPT:?set CKPT to a 5800x-visible checkpoint path}
SUB=${SUB:?set SUB to the odo output subdir name}
rckpt=${CKPT/$SHARE_LOCAL/$SHARE_REMOTE}
dir=$OUT/odo/$SUB; mkdir -p "$dir"

ts(){ date '+%H:%M:%S %Z'; }
count(){ find "$dir" -maxdepth 1 -name '*seed*.json' ! -name '*.partial.json' 2>/dev/null | wc -l; }
clean_stranded(){ local c; for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.json" ] || rm -f "$c"; done; }

launch(){
  nice -n 19 env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE $PY -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$CKPT" --n "$N" --sims "$SIMS" --heur-sims "$HEUR_SIMS" --c-puct 3.0 --heur-leaf v2_7 \
    --workers 14 --out-root "$OUT/odo" --out-subdir "$SUB" \
    --seed-start "$SEED" --paired --shared-claim --claim-host 5800x >/tmp/odo1_5800x.log 2>&1 &
  ssh -o ConnectTimeout=20 laptop "cd $REPO_LAPTOP && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE nice -n 19 $REPO_LAPTOP/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $N --sims $SIMS --heur-sims $HEUR_SIMS --c-puct 3.0 --heur-leaf v2_7 --workers 14 --out-root $OUTR/odo --out-subdir $SUB --seed-start $SEED --paired --shared-claim --claim-host laptop > /tmp/odo1_laptop.log 2>&1 </dev/null &" || echo "  laptop odo launch rc=$?"
  ssh -o ConnectTimeout=20 xeon-wsl "cd $REPO_XEON && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE setsid nice -n 19 $REPO_XEON/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $N --sims $SIMS --heur-sims $HEUR_SIMS --c-puct 3.0 --heur-leaf v2_7 --workers 10 --out-root $OUTR/odo --out-subdir $SUB --seed-start $SEED --paired --shared-claim --claim-host xeon > /tmp/odo1_xeon.log 2>&1 </dev/null &" || echo "  xeon odo launch rc=$?"
}

cd "$REPO_LOCAL" || { echo "FATAL: cannot cd $REPO_LOCAL"; exit 1; }
echo "[$(ts)] ODO start: CKPT=$CKPT SUB=$SUB N=$N SEED=$SEED scale=$SCALE vs heur@${HEUR_SIMS}-v2_7"
clean_stranded; launch
last=-1; stall=0
while [ "$(count)" -lt "$N" ]; do
  sleep 30
  cur=$(count); echo "[$(ts)] odo $SUB $cur/$N"
  if [ "$cur" -eq "$last" ]; then stall=$((stall+1)); else stall=0; last=$cur; fi
  if [ "$stall" -ge 20 ]; then    # ~10min no progress (heur@800 is slow) → heal: clean + relaunch
    echo "[$(ts)] odo $SUB STALLED at $cur/$N — clean stranded + relaunch 3-box"
    clean_stranded; launch; stall=0
  fi
done
echo "[$(ts)] odo $SUB DONE ($(count)/$N) → $dir"
