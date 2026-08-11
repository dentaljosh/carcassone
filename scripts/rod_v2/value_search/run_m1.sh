#!/usr/bin/env bash
# Stage 5 m1 ONLY: classical h200 vs neural iter04, head-to-head @200 sims, v2.9 leaf.
# net-on-CPU at W=cores (NOT oversubscribed). Run on BOTH boxes (shared-claim work-steal).
#   SHARE=... CKPT=... WORKERS=16 N=200 ./run_m1.sh
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
SHARE="${SHARE:?}"; CKPT="${CKPT:?}"; WORKERS="${WORKERS:-16}"; N="${N:-200}"
nice -n 19 "$REPO/.venv/bin/python3" "$REPO/scripts/level2/eval_hybrid_handoff.py" \
  --agent-a "heur@200" --agent-b "iter8" --ckpt "$CKPT" --n "$N" --paired --device cpu \
  --meeple-k-a 2.0 --meeple-k-b 2.0 --workers "$WORKERS" --shared-claim \
  --seed-start 5100000000 --out-root "$SHARE/value_search_games" --out-subdir m1_classical_vs_iter04
echo "### m1 DONE host=$(hostname)"
