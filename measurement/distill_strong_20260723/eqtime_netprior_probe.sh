#!/usr/bin/env bash
# ============================================================================
# CL-067 EQUAL-WALL-CLOCK GATE — TIMING PROBE (throwaway, NOT a strength cell)
#
# PURPOSE: find the candidate per-det sims S* such that the MEASURED solver-free
# prefix ms/move of the distilled net-priors agent (k4 x S*) equals that of the
# DEPLOY champion (k4 x 688), IN THE SAME LOAD REGIME the real cell will run in
# (W16 per box, carc-orch SHM server, fwd=6, max_batch>=W, server OMP pinned).
#
# WHY MEASURE RATHER THAN DIVIDE: the recorded cost ratios for this exact pair
# are 4.29x (gate, W28 loaded), 5.48x (confirm, W48+W26 loaded) and 4.24x
# (unloaded W2 probe, /mnt/c/carc-shared/distill_strong_20260723/cost_probe_unloaded_w2).
# The ratio is LOAD- and BOX-dependent (2026-07-19: "laptop GPU ratio ~4.5x,
# box-dependent"), so 688/4.29 is a starting point, not an answer.
#
# The counters used are the harness's OWN solver-free prefix counters
# (eval_fair_puct.py:1606-1619): champ_prefix_ms_per_move == CANDIDATE,
# rung_ms_per_move == OPPONENT for a _HEAD_TO_HEAD opponent. Verified by reading
# the emitter, not the field name (the 2026-07-26 sign error came from the latter).
# Both exclude the marginalized endgame solve, which is exact-K2 on BOTH sides and
# therefore identical by construction -- equalising the PREFIX is the right target.
#
# Throwaway band 99.5e9, per-host out-dir, --no-results-csv, NOT --shared-claim
# (each box needs its OWN ratio).
#
# Usage:  CAND_SIMS=162 W=16 N=32 bash <this>
# ============================================================================
set -uo pipefail
cd /home/doctor/projects/carcassone

CAND_SIMS="${CAND_SIMS:-162}"
OPP_SIMS_V="${OPP_SIMS_V:-688}"
W="${W:-16}"
N="${N:-32}"
BAND="${BAND:-99500000000}"
HOSTS="$(hostname -s)"
# share mount path differs by box: /mnt/c/carc-shared locally, /mnt/carc-shared remote
if [ -d /mnt/c/carc-shared ]; then SHARE=/mnt/c/carc-shared; else SHARE=/mnt/carc-shared; fi
OUT_ROOT="${OUT_ROOT:-$SHARE}"
CKPT="$SHARE/distill_strong_20260723/ckpt/iter_03.pt"
SUBDIR="eqtime_probe_${HOSTS}_s${CAND_SIMS}_w${W}"

[ -f "$CKPT" ] || { echo "FATAL: ckpt missing: $CKPT" >&2; exit 1; }

echo "=== EQTIME PROBE | host=$HOSTS cand k4x${CAND_SIMS} vs opp k4x${OPP_SIMS_V} | W=$W n=$N band=$BAND rev=$(git rev-parse --short HEAD) $(date -u +%F_%T) ==="

# NO leaf env exported on purpose (fair_net_vs_net_orch.sh header note 2): the
# harness's own _CANON_ENV setdefault must win and curve125 is injected in-process.
# OMP/MKL/OPENBLAS=1 here pin the carc-orch SERVER's libtorch pool (memory
# feedback_pin_orch_omp_threads) -- without it the server owns the box.
CAND_CKPT="$CKPT" OW="$W" ORCH_FWD=6 ORCH_MAX_BATCH="$W" OPP_SIMS="$OPP_SIMS_V" \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  nice -n 19 bash scripts/classical_search/fair_net_vs_net_orch.sh \
    --info fair-netprior --opponent fair-champion \
    --exact-k 2 --k-dets 4 --sims "$CAND_SIMS" --opp-k-dets 4 \
    --n "$N" --paired --seed-start "$BAND" \
    --out-root "$OUT_ROOT" --out-subdir "$SUBDIR" \
    --no-results-csv
rc=$?
echo "=== EQTIME PROBE exited rc=$rc $(date -u +%F_%T) ==="
exit $rc
