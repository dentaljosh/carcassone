#!/bin/bash
# EV-LOSS GRADE THE 5 NEW E4 ARCHIVES (pull 3d69c5b8, 2026-08-12 23:01 -> 08-14 11:04).
#
# Mirrors the 2026-08-12 batch invocation VERBATIM (commit 7437bc90) so the 28-game
# fixed_v1 corpus stays gradeable as one series: budget from each archive's OWN stamp
# (--sims 0 / --k-dets 0 defaults), rules profile resolved from the archive's own
# rules_profile stamp (NEVER from start_rule/grid_rule), --seed 12345 --calibration-seed 777.
#
# 0 GAMES PLAYED. Read-only replay of banked archives. Mints no results.csv row, no band,
# no claim; PRODUCTION.yaml untouched. The QUESTION: does the grade-vs-outcome inversion
# (26/26 through the last batch) still hold on the 10-game unbeaten run?
#
# ⚠️ SLOW BY CONSTRUCTION: the rust clairvoyant judge cannot mirror E4 rules profiles, so
#    E4-corpus oracle grading is PYTHON-ONLY (~9.4x). Budget hours, not minutes.
# ⚠️ EXCLUSIVE TENANT on whichever box runs it -- a co-tenant makes the timings meaningless
#    and this box is DRAM-bound. Do not start it beside a live measurement cell.
set -u
REPO=/home/doctor/projects/carcassone
OUT=$REPO/measurement/analyzer_evloss_20260805
LOG=$REPO/measurement/analyzer_evloss_20260805/grade_20260814.log

ARCHIVES=(
  1786590116_64346
  1786591802_1104719504
  1786680851_216289
  1786684476_1793735743
  1786719876_241820
)

cd $REPO
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE="-10,-5,-1.25,0,2.5,3.75,5,6.25"
export CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export CARCASSONNE_V25_VALUE_BLEND=0 CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1

for a in "${ARCHIVES[@]}"; do
  if [ -f "$OUT/EV_LOSS_$a.json" ]; then
    echo "[$(date +%F_%T)] SKIP $a (already graded)" >> $LOG
    continue
  fi
  echo "[$(date +%F_%T)] grading $a" >> $LOG
  nice -n 19 $REPO/.venv/bin/python $REPO/scripts/analyzer/ev_loss.py \
      "$REPO/measurement/e4_games/$a.json" \
      -o "$OUT" --label "$a" --seed 12345 --calibration-seed 777 \
      >> $LOG 2>&1
  echo "[$(date +%F_%T)] $a rc=$?" >> $LOG
done
echo "[$(date +%F_%T)] === ALL 5 GRADED. Instrument gates first, THEN the inversion count. ===" >> $LOG
