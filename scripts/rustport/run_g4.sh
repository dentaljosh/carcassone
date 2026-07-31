#!/usr/bin/env bash
# rustport P4 / G4 — the three heavy legs, chained (they contend for the same
# thread budget, so they must NOT run concurrently).  Launch detached:
#   nohup nice -n 19 scripts/rustport/run_g4.sh > measurement/rustport_p4/run_g4.log 2>&1 & disown
set -u
cd /home/doctor/projects/carcassone
PY=.venv/bin/python
W=${W:-10}

echo "=== [1/3] game leg: FULL-GAME lockstep at k8x1376 (12 golden + 2 E4) ==="
# 14 jobs -> 14 workers so it is ONE wave (wall = the slowest game, not 2x it).
nice -n 19 $PY -u scripts/rustport/reconcile_fair.py --leg game \
  --sims 1376 --k-dets 8 --n-games 12 --threads 1 --workers "${WG:-14}" --tag game_k8x1376
echo "rc=$?"

echo "=== [2/3] pos leg: ALL 449 champ + 2 E4 + 12 golden, stride 30, k8x1376 ==="
nice -n 19 $PY -u scripts/rustport/reconcile_fair.py --leg pos \
  --sims 1376 --k-dets 8 --stride 30 --threads 1 --workers "$W" --tag pos_k8x1376_s30
echo "rc=$?"

echo "=== [3/3] MOBILE profile k4x688: 50 champ + 2 E4 + 12 golden, EVERY ply ==="
nice -n 19 $PY -u scripts/rustport/reconcile_fair.py --leg pos \
  --sims 688 --k-dets 4 --stride 1 --limit 50 --threads 1 --workers "$W" \
  --tag pos_k4x688_full
echo "rc=$?"
echo "=== done ==="
