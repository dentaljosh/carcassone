#!/usr/bin/env bash
# ============================================================================
# CL-067 UNLOADED COST PROBE — the measurement the deployability call rests on.
#
# WHY IT IS THE DECIDING NUMBER (2026-07-26):
#   The equal-SIMS strength result is settled: pooled over 800 deck-paired games
#   (bands 52e9 + 56e9) the distilled policy prior beats the deploy champion by
#   +35.7 +/- 12.3 elo, winrate z +2.90, deck-paired margin z +2.12 — both
#   statistics clear 2 sigma. What is NOT settled is what it COSTS.
#
#   Loaded ms/move ratios: gate 4.29x, confirmation 5.48x. Applying CL-060's own
#   measured exchange rate (4.07x budget => +27.85 elo), the champion given equal
#   wall-clock would gain +28.9 / +33.8 elo respectively — i.e. the candidate nets
#   -0.2 / -5.1 and is NOT deployable. But at the 1.74x figure that 2026-07-19's
#   UNLOADED W2 probe produced, the champion gains only +11.0 and the candidate
#   nets +17.7 — clearly deployable.
#
#   So the sign of the deployment verdict flips on this ratio, and every ratio
#   measured so far was taken under a harvest queue. On 2026-07-19 EVERY loaded
#   cost ratio in this project collapsed when re-probed unloaded (4.48x -> 1.74x).
#
# DESIGN: identical production knobs (k4 x 688, exact-K2, frozen curve125 both
#   sides) — ONLY the parallelism changes. W=2 so there is no harvest-queue
#   contention and no cross-worker interference; the harness's own solver-free
#   prefix counters then give a clean per-move cost for each side from a single run.
#
# ⚠️ W=2 is ALSO the honest deployment regime, not merely a quiet one: the
#   fair-netprior evaluator is make_remote_single_evaluator (k=1 per request) and
#   the worker BLOCKS on its response semaphore, so a single deployed agent gets
#   NO batching whatever. Per-forward latency is paid in full. This probe therefore
#   measures the cost a real deployment would actually pay.
#
# Throwaway band 99e9, scratch out dir, --no-results-csv. Not a strength cell.
# ============================================================================
set -euo pipefail
REPO=/home/doctor/projects/carcassone
CKPT=${CKPT:-/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt}
OUT_ROOT=${OUT_ROOT:-/mnt/c/carc-shared/distill_strong_20260723}
N=${N:-4}
OW=${OW:-2}
cd "$REPO"

echo "[cost-probe] UNLOADED: W=$OW n=$N k4x688 exact-K2 (production knobs, only parallelism differs)"
echo "[cost-probe] loaded ratios to beat/compare: gate 4.29x, confirm 5.48x, 2026-07-19 unloaded 1.74x"

CAND_CKPT="$CKPT" OW="$OW" ORCH_FWD=2 ORCH_MAX_BATCH="$OW" \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  nice -n 19 bash scripts/classical_search/fair_net_vs_net_orch.sh \
    --info fair-netprior --opponent fair-champion \
    --exact-k 2 --k-dets 4 --sims 688 \
    --n "$N" --paired --seed-start 99000000000 \
    --out-root "$OUT_ROOT" --out-subdir cost_probe_unloaded_w${OW} \
    --no-results-csv
