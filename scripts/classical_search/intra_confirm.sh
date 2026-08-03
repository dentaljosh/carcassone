#!/usr/bin/env bash
# C3-INTRA (within-turn tile->meeple tree carry) — POWERED CONFIRM, n=600 paired.
# TRANCHE 2: band 80e9  (tranche 1 was band 78e9, n=600, COMPLETE)
#
# ⛔ STATUS 2026-07-28: BOTH TRANCHES RUN — VERDICT: the lever is 🅿️ PARKED (does not clear).
# T1 (b78e9) +27.3 +- 14.2 (z 1.92) · T2 (b80e9) +5.2 +- 14.2 (z 0.37) · COMBINED n=1200
# +16.2 +- 10.0 (z +1.62), paired margin +0.770 (z +1.55), 95% CI [-3.5,+35.9] INCLUDES ZERO.
# The screen's +40.1 is EXCLUDED from the pool as the selecting observation; the monotone decay
# +40.1 -> +27.3 -> +5.2 with rising power is the winner's-curse signature the screen read-out
# pre-flagged (2x total compute buys only +12.2 elo, CL-068). Tranche heterogeneity z +1.10 =>
# pooling legitimate. Equal-wall-clock obligation DISCHARGED (ms-ratio 0.994/1.011/1.010x).
# NOT ADOPTED; PRODUCTION.yaml untouched; flag stays default OFF. PARKED not killed — all three
# point estimates positive. Re-open bar: n~4800 paired (~32 box-hours) or a mechanism argument
# for a different budget/allocation. See the CONFIRM section of
# measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md;
# results.csv intrareuse_k4x688_confirm_{t1,t2,COMBINED}; DECISIONS 2026-07-28.
#
# ⚠️ The CODE REV note below names tranche 1 as 4e67f2b — that was the pre-launch expectation.
# The cell MANIFEST is the authority and records 693ef39 for tranche 1 (the tree advanced between
# the HEAD check and the launch); tranche 2 is 81f6e5d as stated. The bit-exactness argument is
# unaffected and was independently corroborated: solver time/game fell 1.27x (candidate) and
# 1.26x (opponent) between tranches — BOTH arms equally, so it cannot bias the comparison.
#
# Lineage:
#   SCREEN    (band 74e9, n=200, selection-biased — the cell that motivated the confirm):
#             +40.1 elo (z +1.62), paired margin +1.65 pts/deck (z +1.32), ms-ratio 0.994x
#   TRANCHE 1 (band 78e9, n=600, unbiased): +27.3 +/- 14.2 (z 1.92), paired +1.20 (z 1.76),
#             ms-ratio 1.011x — just under the 2-sigma bar, sign-consistent across bands.
#   TRANCHE 2 (this cell, band 80e9, n=600): settles it. Combined n=1200 across 78e9+80e9.
#
# ⚠️ CODE REV NOTE: tranche 1 ran at rev 4e67f2b; tranche 2 runs at 81f6e5d. The delta includes
# a merged flat_base_score->Cython dispatch under USE_CY_LEAF, PROVEN bit-exact by
# scripts/reconcile_cy_leaf.py (0 mismatches over ~87k base evals incl. 9k endgame states),
# plus a golden-fixture regen (hash-only). Behaviour is identical, so combining the two tranches
# is defensible — but the differing code_rev MUST be recorded in the read-out.
#
# ⚠️ This deliberately does NOT call scripts/classical_search/intra_reuse_screen.sh: that script
# runs TWO cells (k4x344 then k4x688) and would spend hours on a k4x344 cell nobody asked for.
# Everything below — env block, agent flags, endgame, claim knobs — is copied VERBATIM from that
# script's k4x688 iteration so the confirm is config-identical to the screen cell it confirms.
#
# ⚠️ EQUAL-WALL-CLOCK: measured ms/move ratio candidate/opponent is 0.994x (screen) / 1.011x
# (tranche 1) at this exact budget, i.e. nominal-equal sims ARE equal wall-clock here (tighter
# than CL-044's accepted 1.06x). So these cells double as the mandatory equal-wall-clock confirm.
#
# Usage: intra_confirm.sh <WORKERS> <OUT_ROOT>
#   local:  intra_confirm.sh 16 /mnt/c/carc-shared
#   laptop: intra_confirm.sh 16 /mnt/carc-shared
# Resume-safe: --shared-claim, so re-running resumes remaining games (the watchdog relies on this).
set -uo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

cd /home/doctor/projects/carcassone            # line-1 cd (path-stable for ssh bash -s)

W="${1:?worker count}"
OUT_ROOT="${2:?out root (/mnt/c/carc-shared local | /mnt/carc-shared laptop)}"
BAND=80000000000                               # claimed in /mnt/c/carc-shared/BAND_CLAIMS.txt
N=600                                          # paired => even; 300 decks x 2 seats
K=4
S=688
PY=/home/doctor/projects/carcassone/.venv/bin/python
EVAL=/home/doctor/projects/carcassone/scripts/classical_search/eval_fair_puct.py

# ---- production leaf knobs + BLAS pins — VERBATIM from intra_reuse_screen.sh.
# ---- NO CARCASSONNE_V29_MEEPLE_CURVE export (a head-to-head injects curve125 into BOTH sides
# ---- itself; exporting it here would move env DEFAULT_CONFIG and change what "champion" means).
# ---- NO CARCASSONNE_INTRA_TURN_REUSE export either: the flag is per-AGENT via --intra-reuse,
# ---- so the OPPONENT in the same worker process stays OFF.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export CARCASSONNE_TT_CAP=200000

[ -d "$OUT_ROOT" ] || { echo "FATAL: share not mounted at $OUT_ROOT" >&2; exit 1; }

echo "=== intra-reuse CONFIRM T2 k_dets=$K sims/det=$S total=$((K*S)) W=$W band=$BAND n=$N host=$(hostname -s) rev=$(git rev-parse --short HEAD) $(date -u +%H:%M:%S) ==="
nice -n 19 "$PY" -u "$EVAL" \
  --info fair --opponent fair-champion --exact-k 2 \
  --k-dets "$K" --sims "$S" \
  --intra-reuse \
  --n "$N" --paired --seed-start "$BAND" --workers "$W" \
  --out-root "$OUT_ROOT" --out-subdir "intrareuse_k${K}x${S}_tot$((K*S))_vs_champ_off_b${BAND}_n600" \
  --shared-claim --claim-stale-secs 300 --no-results-csv
echo "=== intra-reuse CONFIRM T2 DONE rc=$? $(date -u +%H:%M:%S) ==="
