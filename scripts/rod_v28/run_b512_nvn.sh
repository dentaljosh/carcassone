#!/usr/bin/env bash
# rod_batch512_calibration Phase 4/5 net-vs-net launcher (thin wrapper over
# scripts/heuristic_v28/v28_net_vs_net_orch.sh). Holds the arms/bands constant so
# the n=200 screen and the n=400 top-up are the SAME command with a different N
# (the harness caches per-seed, so top-up reuses the screen's games).
#
#   phase4 = ROD_ITER1_B512_TEST (A) vs frozen ITER8_V28_PARENT (B)  — band 1.922e9
#            (SAME decks as the B256-vs-parent matchup -> directly comparable margins;
#             single candidate, so this is a controlled comparison, not a spent-panel reuse)
#   phase5 = ROD_ITER1_B512_TEST (A) vs ROD_ITER1_B256_REFERENCE (B) — band 1.923e9 (fresh)
#
# elo sign: diff = A - B, so elo>0 => B512 stronger. MEASUREMENT ONLY; v2.7 frozen; no promotion.
#
# Usage: bash scripts/rod_v28/run_b512_nvn.sh <phase4|phase5> <n_even>
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
PHASE=${1:?usage: run_b512_nvn.sh <phase4|phase5> <n_even>}
N=${2:?usage: run_b512_nvn.sh <phase4|phase5> <n_even>}

B512=/mnt/c/carc-shared/rod_batch512_calibration/ckpt/iter_01_b512.pt
ITER8=/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt
B256=/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt
OUTROOT=/mnt/c/carc-shared/rod_b512_calib

case "$PHASE" in
  phase4) CKA=$B512; CKB=$ITER8; SEED=1922000000 ;;
  phase5) CKA=$B512; CKB=$B256;  SEED=1923000000 ;;
  *) echo "FATAL: phase must be phase4 or phase5" >&2; exit 1 ;;
esac

[ -f "$CKA" ] || { echo "FATAL: missing A checkpoint $CKA" >&2; exit 1; }
[ -f "$CKB" ] || { echo "FATAL: missing B checkpoint $CKB" >&2; exit 1; }

echo "[run_b512_nvn] $PHASE  A=$(basename "$CKA")  B=$(basename "$CKB")  n=$N  seed_start=$SEED  out=$OUTROOT"
CKPT_A="$CKA" CKPT_B="$CKB" OW=24 SIMS=200 \
  bash "$REPO/scripts/heuristic_v28/v28_net_vs_net_orch.sh" \
    --n "$N" --paired --c-puct 3.0 --residual-scale 0.25 \
    --meeple-k-a 2.0 --meeple-k-b 2.0 --seed-start "$SEED" \
    --out-root "$OUTROOT"
