#!/usr/bin/env bash
# Part B (micro-validation): endgame regret vs the EXACT solver for RoD1 / iter_08 /
# ITER8_V28_PARENT, directly comparable to the cached iter8/heur@3200 L2-3 numbers.
# Reuses the TRUSTED L2-3 regret harness unmodified — one run per net (the solve is
# identical across nets, so the per-net out-dirs just re-score the same ground truth;
# K=2 re-solve is ~cheap). Each run scores [iter8(=that net), heur@3200] under the
# clairvoyant solver (== marginalized at K=2). Aggregate with partb_aggregate.py.
#
#   KS="2" bash scripts/exact_hybrid/run_partb_regret.sh           # K=2 (cheap, ~min)
#   KS="2 3" ALPHABETA=1 bash scripts/exact_hybrid/run_partb_regret.sh   # add K=3 (slow)
set -euo pipefail
cd "$(cd "$(dirname "$0")/../.." && pwd)"

KS=${KS:-2}
W=${W:-14}
BUDGET=${BUDGET:-2000000}
ALPHABETA=${ALPHABETA:-1}
OUT_BASE=${OUT_BASE:-/mnt/c/carc-shared/exact_endgame_hybrid/partb_regret}
SUITE=measurement/level2/l23_positions.jsonl
declare -A CK=(
  [rod1]=/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt
  [iter08]=/mnt/c/carc-shared/rod_v28_overnight_flywheel/ckpt/iter_08.pt
  [parent]=/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt
)
AB=""; [ "$ALPHABETA" = "1" ] && AB="--alphabeta"

for name in rod1 iter08 parent; do
  echo "[partb] regret for $name (K=$KS) -> $OUT_BASE/$name"
  CARCASSONNE_V25_MEEPLE_K=2.0 nice -n 19 .venv/bin/python -u scripts/level2/endgame_regret.py \
    --suite "$SUITE" --out-root "$OUT_BASE/$name" --ckpt "${CK[$name]}" \
    --workers "$W" --budget "$BUDGET" --modes clairvoyant $AB \
    --agents iter8 heur@3200 --ks $KS
done
echo "[partb] done -> aggregate with: .venv/bin/python scripts/exact_hybrid/partb_aggregate.py"
