#!/usr/bin/env bash
# MEEPLE-DEDUP — SCREEN (cheap-first), SYMMETRIC head-to-head.
#
# ⚠️⚠️ BAND IS A REQUIRED ARGUMENT AND YOU MUST ENUMERATE experiments/results.csv FIRST.
# ⚠️⚠️ Many CRN bands are already burned, and ANOTHER THREAD IS BURNING MORE RIGHT NOW.
# ⚠️⚠️ Re-using a band that this candidate (or its opponent) has already played makes the
# ⚠️⚠️ result a re-read of old noise, not a new measurement. Before launching:
# ⚠️⚠️     grep -o 'seed_start[^,]*' experiments/results.csv | sort -u
# ⚠️⚠️     grep -rl '"seed_start"' /mnt/c/carc-shared/*/manifest.json | xargs grep -h seed_start | sort -u
# ⚠️⚠️ then pick a band NOBODY has used and record your claim on it before you start.
#
# THE QUESTION -------------------------------------------------------------------------
# 60.75% of the fair champion's ACTIONABLE meeple decisions offer >=2 GAME-EQUIVALENT
# actions (the same connected on-tile feature reached from several sides), and 28.6% of
# its actual placements were chosen out of such a visit-diluted group
# (measurement/classical_search/meeple_dedup_census_20260727.json). The search cannot see
# this: equivalent actions produce DIFFERENT state encodings, so the existing
# byte-identical-transposition machinery (child_canon/child_aliases) never fires and the
# tree carries two subtrees for one move, with the prior mass split between them.
# CARCASSONNE_MEEPLE_DEDUP / --meeple-dedup masks all but the lowest-action-id member of
# each group BEFORE expansion. Does recovering that wasted budget buy elo?
#
# THE DESIGN ---------------------------------------------------------------------------
# --opponent fair-champion = the SYMMETRIC head-to-head: candidate and opponent are the
# SAME production agent, same curve125 leaf (auto-injected on both sides for a
# head-to-head), same k_dets x sims, same marginalized endgame at K=2. The ONLY
# difference in the cell is that the CANDIDATE carries --meeple-dedup and the opponent
# does NOT (meeple_dedup is a per-AGENT kwarg; _make_opponent never forwards it). So the
# delta is attributable to the mask and nothing else — no ruler, no leaf asymmetry.
#
# LOW SIMS ON PURPOSE. Dilution is a budget-scarcity effect: splitting 172 sims across a
# duplicated subtree costs proportionally far more than splitting 688. The deploy budget
# (k4x688=2752) is where a dedup gain would be SMALLEST, so screening there would be the
# blindest possible test. Two cells bracket the k axis at fixed low per-det depth:
#
#   cell      k_dets  sims/det  total   note
#   k2x172      2       172      344    cheapest signal; most dilution-sensitive
#   k4x172      4       172      688    deploy's k, quarter depth
#
# If BOTH cells are flat at n=200 paired (1 sigma ~ +-24 elo paired), the lever is dead at
# low sims and there is no reason to fund a deploy-budget confirm. If either clears ~2
# sigma, the confirm is a k4x688 cell on a FRESH band — NOT this one.
#
# Usage:  meeple_dedup_screen.sh <WORKERS> <OUT_ROOT> <BAND> [N]
#   local:  meeple_dedup_screen.sh 30 /mnt/c/carc-shared 41000000000 200
#   laptop: meeple_dedup_screen.sh 22 /mnt/carc-shared   41000000000 200
set -uo pipefail
cd /home/doctor/projects/carcassone            # line-1 cd (path-stable for ssh bash -s)

W="${1:?worker count}"
OUT_ROOT="${2:?out root (/mnt/c/carc-shared local | /mnt/carc-shared laptop)}"
BAND="${3:?CRN seed band — ENUMERATE experiments/results.csv FIRST, see the header}"
N="${4:-200}"                                  # paired => must be EVEN (n/2 decks x 2 seats)
PY=/home/doctor/projects/carcassone/.venv/bin/python
EVAL=/home/doctor/projects/carcassone/scripts/classical_search/eval_fair_puct.py

if [ $((N % 2)) -ne 0 ]; then echo "N must be EVEN for --paired (got $N)" >&2; exit 2; fi

# ---- production leaf knobs + BLAS pins. NOTE: NO CARCASSONNE_V29_MEEPLE_CURVE export —
# ---- a head-to-head injects curve125 into BOTH sides itself; exporting the curve here
# ---- would move env DEFAULT_CONFIG and silently change what "the champion" means.
# ---- NO CARCASSONNE_MEEPLE_DEDUP export either: the flag is per-AGENT via
# ---- --meeple-dedup, so that the OPPONENT in the same worker process stays OFF.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export CARCASSONNE_TT_CAP=200000

declare -a KDETS=(2   4)      # cheapest cell FIRST = earliest read
declare -a PERDET=(172 172)

for i in "${!KDETS[@]}"; do
  K="${KDETS[$i]}"; S="${PERDET[$i]}"
  echo "=== meeple-dedup-screen k_dets=$K (sims/det=$S total=$((K*S))) W=$W band=$BAND n=$N $(date -u +%H:%M:%S) ==="
  nice -n 19 "$PY" -u "$EVAL" \
    --info fair --opponent fair-champion --exact-k 2 \
    --k-dets "$K" --sims "$S" \
    --meeple-dedup \
    --n "$N" --paired --seed-start "$BAND" --workers "$W" \
    --out-root "$OUT_ROOT" --out-subdir "meepledup_k${K}x${S}_tot$((K*S))_vs_champ_off_b${BAND}" \
    --shared-claim --claim-stale-secs 300 --no-results-csv
  echo "=== cell k${K}x${S} DONE rc=$? $(date -u +%H:%M:%S) ==="
done
echo "=== meeple-dedup-screen ALL CELLS DONE W=$W band=$BAND $(date -u +%H:%M:%S) ==="
