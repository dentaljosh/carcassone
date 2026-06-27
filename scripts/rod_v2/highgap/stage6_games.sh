#!/usr/bin/env bash
# High-gap distillation — Stage 6 game screen (ONLY if Stage 5/5b pass).
# Repaired R2 vs h6400_v2.9, mirroring the autopsy iter04-vs-h6400 config exactly so
# WR is directly comparable to iter04's 0.463 (Elo -26.1, n=400). Shared-claim across
# local+laptop (the proven path). MEAS-ONLY; no promotion.
#
# usage: stage6_games.sh <local|laptop> <opp: h6400|h3200|iter04> <n> [checkpoint]
set -euo pipefail
cd /home/doctor/projects/carcassone
# ---- v2.9 FROZEN leaf env (so the HeuristicMCTS opponent IS v2.9) ----
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0

BOX=${1:-local}; OPP=${2:-h6400}; N=${3:-160}
CKPT=${4:-/mnt/c/carc-shared/high_gap_distillation/R2_from_iter04.pt}
case "$BOX" in
  local)  SHARE=/mnt/c/carc-shared; W=${W:-14}; PY=.venv/bin/python ;;
  laptop) SHARE=/mnt/carc-shared;  W=${W:-20}; PY=.venv/bin/python ;;
esac
case "$OPP" in
  h6400) HS=6400 ;; h3200) HS=3200 ;; *) HS=6400 ;;
esac
OUT="$SHARE/high_gap_distillation/games/R2_vs_${OPP}_n${N}"
mkdir -p "$OUT"
echo "[stage6] box=$BOX opp=$OPP n=$N W=$W ckpt=$(basename "$CKPT") out=$OUT"
nice -n 19 $PY scripts/eval_net_vs_heuristic.py \
  --checkpoint "$CKPT" --heur-leaf v2_7 --heur-sims "$HS" \
  --sims 200 --c-puct 3.0 --residual-scale 0.25 \
  --n "$N" --paired --shared-claim --claim-host "$BOX" \
  --workers "$W" --out-root "$OUT"
