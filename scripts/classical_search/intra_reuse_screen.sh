#!/usr/bin/env bash
# C3-INTRA (within-turn tree carry, tile -> meeple) — SCREEN, SYMMETRIC head-to-head.
#
# STATUS 2026-07-28: RUN (band 74e9, n=200 paired per cell) — screen is INCONCLUSIVE-POSITIVE:
# k4x688 (the DEPLOY budget) +40.1 elo / z +1.62 with the deck-paired margin agreeing in sign
# (+1.650 pts/deck, z +1.32) at measured ms-ratio 0.994x (candidate marginally CHEAPER, so the
# header's "more work per turn" confound is empirically discharged); k4x344 flat (−5.2, z −0.21).
# No cell clears the 2σ screen bar; the effect GROWS with depth (anti-washout). Winner's-curse
# suspect — 2× compute buys only +12.2 elo (CL-068). A k4x688 n=600 deck-paired confirm on a
# FRESH band is FUNDED (band 78e9 claimed in /mnt/c/carc-shared/BAND_CLAIMS.txt). NOT promoted.
# See measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md; results.csv
# intrareuse_k4x344_screen / intrareuse_k4x688_screen; LEVER_INDEX 'within-turn tree carry'.
#
# ⚠️⚠️ BAND IS A REQUIRED ARGUMENT AND YOU MUST ENUMERATE THE BURNED BANDS FIRST.
# ⚠️⚠️ Many CRN bands are already burned, and ANOTHER THREAD IS BURNING MORE RIGHT NOW.
# ⚠️⚠️ Re-using a band that this candidate (or its opponent) has already played makes the
# ⚠️⚠️ result a re-read of old noise, not a new measurement. Before launching:
# ⚠️⚠️ ⛔ DO NOT grep experiments/results.csv for seed_start — it HAS NO BAND COLUMN and the
# ⚠️⚠️ grep silently returns NOTHING (bands live only in prose in the `note` field), which
# ⚠️⚠️ reads as "no bands burned". The share manifests are the enumeration surface:
# ⚠️⚠️     grep -h seed_start /mnt/c/carc-shared/*/manifest.json /mnt/c/carc-shared/*/*/manifest.json | sort -u
# ⚠️⚠️     cat /mnt/c/carc-shared/BAND_CLAIMS.txt          # bands claimed but not yet written
# ⚠️⚠️ then pick a band NOBODY has used and append your claim to BAND_CLAIMS.txt before you start.
#
# ⚠️⚠️ READ-OUT CAVEAT — THIS SCREEN CANNOT BE READ AS A STRENGTH RESULT ON ITS OWN.
# ⚠️⚠️ At equal NOMINAL sims the ON candidate does MORE total work per turn: its meeple
# ⚠️⚠️ decision runs a full `sims` per determinization ON TOP of a carried subtree
# ⚠️⚠️ (measured warm start ~34% of a fresh budget, max ~81%, at k4x172). So a positive
# ⚠️⚠️ delta here is "more effective search per turn helps" — which we already know —
# ⚠️⚠️ NOT "the carry is free elo". A POSITIVE SCREEN MUST BE FOLLOWED BY AN
# ⚠️⚠️ EQUAL-WALL-CLOCK CONFIRM (the house rule from CL-044's ms-ratio verification:
# ⚠️⚠️ that lever only counted because the confirm reproduced +39.3 at ms-ratio 1.06).
# ⚠️⚠️ Check `champ_prefix_ms_per_move` in the cell's results before believing anything,
# ⚠️⚠️ and read the field's EMITTER first — a prior thread read that exact field backwards.
#
# THE QUESTION -------------------------------------------------------------------------
# The fair champion is asked for TWO decisions per turn and searches both from scratch;
# the meeple half was MEASURED at 52.5% of champion search time (30-decision probe, zero
# forced skips, 2026-07-27). The tile search ALREADY builds the meeple-decision subtree
# under every candidate placement and then throws the forest away. Between the two
# decisions NO hidden information arrives — the engine draws the next tile only at the
# END of the meeple phase (StateUpdater._apply_action_to) — so carrying the k_dets trees
# AND their determinizations forward is information-LEGAL. (This is exactly what is NOT
# true across moves: CL-044 reuse is clairvoyant-only and must stay that way.)
# Does recovering that thrown-away half-turn of search buy elo?
#
# THE DESIGN ---------------------------------------------------------------------------
# --opponent fair-champion = the SYMMETRIC head-to-head: candidate and opponent are the
# SAME production agent, same curve125 leaf (auto-injected on both sides), same k_dets x
# sims, same marginalized endgame at K=2. The ONLY difference in the cell is that the
# CANDIDATE carries --intra-reuse and the opponent does NOT (intra_reuse is a per-AGENT
# kwarg; _make_opponent never forwards it). So the delta is attributable to the carry.
#
# DEPLOY-ADJACENT BUDGETS ON PURPOSE. Unlike meeple-dedup (a visit-DILUTION effect, which
# is worst at low sims), this is a search-EFFICIENCY effect whose value should hold at
# depth — the across-move sibling (CL-044) fired at the full deploy budget and dodged
# sims-washout. Screening it cheap would test the wrong regime, so both cells sit at the
# adopted allocation:
#
#   cell      k_dets  sims/det  total   note
#   k4x344     4        344      1376   half-depth at the DEPLOYED width (k4, CL-054)
#   k4x688     4        688      2752   the DEPLOYED budget exactly
#
# If both are flat at n=200 paired (1 sigma ~ +-24 elo paired), the lever is dead at the
# budgets we actually ship and there is no reason to fund an equal-time confirm. If
# either clears ~2 sigma, the confirm is an EQUAL-WALL-CLOCK k4x688 cell on a FRESH band
# — sized by the measured ms-ratio, NOT this one.
#
# Usage:  intra_reuse_screen.sh <WORKERS> <OUT_ROOT> <BAND> [N]
#   local:  intra_reuse_screen.sh 30 /mnt/c/carc-shared 42000000000 200
#   laptop: intra_reuse_screen.sh 22 /mnt/carc-shared   42000000000 200
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
# ---- NO CARCASSONNE_INTRA_TURN_REUSE export either: the flag is per-AGENT via
# ---- --intra-reuse, so that the OPPONENT in the same worker process stays OFF.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export CARCASSONNE_TT_CAP=200000

declare -a KDETS=(4   4)      # cheaper cell FIRST = earliest read
declare -a PERDET=(344 688)

for i in "${!KDETS[@]}"; do
  K="${KDETS[$i]}"; S="${PERDET[$i]}"
  echo "=== intra-reuse-screen k_dets=$K (sims/det=$S total=$((K*S))) W=$W band=$BAND n=$N $(date -u +%H:%M:%S) ==="
  nice -n 19 "$PY" -u "$EVAL" \
    --info fair --opponent fair-champion --exact-k 2 \
    --k-dets "$K" --sims "$S" \
    --intra-reuse \
    --n "$N" --paired --seed-start "$BAND" --workers "$W" \
    --out-root "$OUT_ROOT" --out-subdir "intrareuse_k${K}x${S}_tot$((K*S))_vs_champ_off_b${BAND}" \
    --shared-claim --claim-stale-secs 300 --no-results-csv
  echo "=== cell k${K}x${S} DONE rc=$? $(date -u +%H:%M:%S) ==="
done
echo "=== intra-reuse-screen ALL CELLS DONE W=$W band=$BAND $(date -u +%H:%M:%S) ==="
