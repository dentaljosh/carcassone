#!/bin/bash
# Chain the laptop's SECOND funded cell (Acap3_d2p0) after the FIRST (C_d16p0) finishes.
# The two laptop cells are sequential by design (one box, W=22); the third cell (Asym)
# runs concurrently on the local box. Execution split only -- disjoint seed offsets,
# cells read independently, so box/order changes no statistic.
#
# allow-path: this script RUNS ON THE LAPTOP, where the share is /mnt/carc-shared.
# allow-sleep: this is a detached on-box waiter, not a foreground poll in a session.
set -u
DIR=/home/doctor/projects/carcassone/measurement/opencity_round2_20260814
OUT=/mnt/carc-shared/opencity_round2_deploy_20260814
DONE_C=$OUT/markers/DONE_oc2_C_d16p0_deploy11008
LOG=$DIR/deploy_logs/chain_laptop_acap3.log
echo "[chain $(date +%F_%T)] waiting for $DONE_C" >> $LOG
while [ ! -f "$DONE_C" ]; do
  if ! pgrep -f "run_deploy_opencity_round2.sh laptop 129000000000 22 d16p0" > /dev/null; then
    echo "[chain $(date +%F_%T)] ABORT: cell-1 driver gone and no DONE marker" >> $LOG
    exit 1
  fi
  sleep 60
done
echo "[chain $(date +%F_%T)] cell 1 DONE -- launching Acap3" >> $LOG
cd /home/doctor/projects/carcassone
exec systemd-run --user --scope -p MemoryMax=20G nice -n 19 \
  bash $DIR/run_deploy_opencity_round2.sh laptop 129000000000 22 Acap3 \
  >> $DIR/deploy_logs/driver_laptop_Acap3.log 2>&1
