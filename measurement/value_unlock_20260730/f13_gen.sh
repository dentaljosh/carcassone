#!/usr/bin/env bash
# F13 verification gen: reproduce the ATTEMPT-2 residual-target emitter at its own
# knobs (scripts/gen_flywheel.sh SP_COMMON, orch-off branch) for a small sample, so
# the residual value TARGETS can be histogrammed against the tanh head's [-1,1] range.
# The attempt-2 npz corpora were deleted in a disk sweep; this regenerates the same
# quantity from the same code path. MEASUREMENT ONLY.
set -uo pipefail
REPO=/home/doctor/projects/carcassone
WARM=/mnt/c/carc-shared/flywheel_residual_attempt2/warm.pt
OUT=/mnt/c/carc-shared/value_unlock_20260730/f13_residual_probe
PY="$REPO/.venv/bin/python"
cd "$REPO" || exit 1
mkdir -p "$OUT"
env CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 \
  nice -n 19 "$PY" -u scripts/run_selfplay_iter.py \
  --iter 0 --games "${GAMES:-24}" --sims "${SIMS:-200}" --leaf-eval v2_5 --value-blend 0 \
  --residual-scale 0.25 --value-target residual --batch-size 8 --checkpoint "$WARM" \
  --anchor-fraction 0 --output-root "$OUT" --seed-start 700000 \
  --workers "${WORKERS:-12}"
echo "=== f13_gen DONE rc=$? @ $(date) ==="
