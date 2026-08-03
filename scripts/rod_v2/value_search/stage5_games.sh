#!/usr/bin/env bash
# Value/Search Autopsy — Stage 5 game screen. Tests whether classical h200's +11pp
# root-level edge over neural iter04 converts to GAME strength, on the v2.9 leaf.
# Three paired, seat-balanced matchups via the canonical eval_hybrid_handoff harness
# (--shared-claim -> local+laptop work-steal). v2.9 leaf hard-set via env (overrides
# EH's setdefault v2.7) + meeple_k=2.0 on both agents to match the autopsy exactly.
#
#   SHARE=/mnt/c/carc-shared CKPT=.../iter_04.pt WORKERS=30 N=200 ./stage5_games.sh
# Run the SAME command on BOTH boxes (different SHARE/CKPT/WORKERS) for work-stealing.
set -euo pipefail

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

export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE="-8,-4,-1,0,2,3,4,5" CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python3"
EH="$REPO/scripts/level2/eval_hybrid_handoff.py"
SHARE="${SHARE:?}"; CKPT="${CKPT:?}"; WORKERS="${WORKERS:-16}"; N="${N:-200}"
OUT="$SHARE/value_search_games"
COMMON=(--ckpt "$CKPT" --n "$N" --paired --shared-claim --device cpu \
        --meeple-k-a 2.0 --meeple-k-b 2.0 --workers "$WORKERS" --out-root "$OUT")

# m1 PRIMARY: classical h200 vs neural iter04 — head-to-head at matched 200 sims
nice -n 19 "$PY" "$EH" --agent-a "heur@200" --agent-b "iter8" \
    --out-subdir m1_classical_vs_iter04 --seed-start 5100000000 "${COMMON[@]}" 2>&1 | tail -6
# m2: neural iter04 vs h6400_v2.9 (re-measured under this harness for comparability)
nice -n 19 "$PY" "$EH" --agent-a "iter8" --agent-b "heur@6400" \
    --out-subdir m2_iter04_vs_h6400 --seed-start 5200000000 "${COMMON[@]}" 2>&1 | tail -6
# m3: classical h200 vs h6400_v2.9 (anchors classical on the same vs-teacher scale)
nice -n 19 "$PY" "$EH" --agent-a "heur@200" --agent-b "heur@6400" \
    --out-subdir m3_classical_vs_h6400 --seed-start 5300000000 "${COMMON[@]}" 2>&1 | tail -6
echo "### STAGE5 GAMES DONE ($(date +%H:%M:%S)) host=$(hostname)"
