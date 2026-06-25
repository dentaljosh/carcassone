#!/usr/bin/env bash
# Wave-1 screen: every first-wave v2.9 candidate vs v2.8, sims=200 n=200 paired.
# Coarse screen (~5 min/cell, ±~35 elo) — kills losers, flags wr>=0.55. Local 5900XT.
# cd on line 1 (remote-ssh-pipe rule; harmless locally).
cd /home/doctor/projects/carcassone || exit 1
set -uo pipefail
PY=.venv/bin/python
OUT=/mnt/c/carc-shared/v29_eval
N=200; SIMS=200; W=14; SEED=1000000000
# null control (v28 vs v28 ~0.500) + A sweep + B curves/controls + D(near-inert) + E
CANDS="v28 A8 A12 A16 A24 A32 A48 Bmild Baggr Bk1 Bk3 D2 E1 E2"
echo "=== WAVE1 SCREEN START $(date '+%F %H:%M') | n=$N sims=$SIMS W=$W cands=$(echo $CANDS|wc -w) ==="
for C in $CANDS; do
  echo "--- [$C] $(date '+%H:%M') ---"
  nice -n 19 $PY -u scripts/v29/eval_v29_vs_v28.py --candidate "$C" --n $N --sims $SIMS \
    --paired --workers $W --seed-start $SEED --out-root "$OUT" 2>&1 | grep -vE "min left\)$"
done
echo "=== WAVE1 SCREEN DONE $(date '+%F %H:%M') ==="
