#!/usr/bin/env bash
# Level-2 L2-1 adjacent-rung sanity matrix. Pure-CPU heuristic/rule rungs.
# Runs each adjacent comparison SEQUENTIALLY (one box not oversubscribed across
# comparisons), n=200 paired, disjoint fresh bands (see LEVEL2_LADDER_PROTOCOL.md).
#
# Usage:  scripts/level2/run_l2_ladder.sh <OUT_ROOT> [WORKERS] [SHARED_CLAIM]
#   OUT_ROOT      e.g. /mnt/c/carc-shared/level2_ladder  (share for 3-box) or a local dir
#   WORKERS       parallel games (CPU-bound -> <= threads; default 28)
#   SHARED_CLAIM  pass "claim" to enable --shared-claim work-stealing
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

cd "$(dirname "$0")/../.."

OUT_ROOT="${1:?usage: run_l2_ladder.sh OUT_ROOT [WORKERS] [SHARED_CLAIM]}"
WORKERS="${2:-28}"
CLAIM_FLAG=""
[ "${3:-}" = "claim" ] && CLAIM_FLAG="--shared-claim"

export CARCASSONNE_V25_CAP=12
export CARCASSONNE_V25_DROP_THREE_OPEN=1
export CARCASSONNE_USE_FLAT_LEAF=1
export CARCASSONNE_V25_VALUE_BLEND=0

N=200
run() {  # rung_a rung_b seed_start
  echo "=== $(date +%T)  $1 vs $2  (band $3) ==="
  nice -n 19 python -u scripts/ladder_rung_eval.py \
    --rung-a "$1" --rung-b "$2" --n "$N" --paired \
    --seed-start "$3" --workers "$WORKERS" \
    --out-root "$OUT_ROOT" $CLAIM_FLAG
}

run greedy        random        3000000000   # R1 vs R0
run heur_v1@200   greedy        3010000000   # R2 vs R1
run heur_v2_7@200 heur_v1@200   3020000000   # R3 vs R2
run heur_v2_7@800 heur_v2_7@200 3030000000   # R4 vs R3
run heur_v2_7@1600 heur_v2_7@800 3040000000  # R5 vs R4  (saturation gate)

echo "=== $(date +%T)  L2-1 matrix complete ==="
