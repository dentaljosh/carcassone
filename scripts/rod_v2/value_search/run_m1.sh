#!/usr/bin/env bash
# Stage 5 m1 ONLY: classical h200 vs neural iter04, head-to-head @200 sims, v2.9 leaf.
# net-on-CPU at W=cores (NOT oversubscribed). Run on BOTH boxes (shared-claim work-steal).
#   SHARE=... CKPT=... WORKERS=16 N=200 ./run_m1.sh
set -euo pipefail
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE="-8,-4,-1,0,2,3,4,5" CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
REPO=/home/doctor/projects/carcassone
SHARE="${SHARE:?}"; CKPT="${CKPT:?}"; WORKERS="${WORKERS:-16}"; N="${N:-200}"
nice -n 19 "$REPO/.venv/bin/python3" "$REPO/scripts/level2/eval_hybrid_handoff.py" \
  --agent-a "heur@200" --agent-b "iter8" --ckpt "$CKPT" --n "$N" --paired --device cpu \
  --meeple-k-a 2.0 --meeple-k-b 2.0 --workers "$WORKERS" --shared-claim \
  --seed-start 5100000000 --out-root "$SHARE/value_search_games" --out-subdir m1_classical_vs_iter04
echo "### m1 DONE host=$(hostname)"
