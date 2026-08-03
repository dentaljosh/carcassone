#!/usr/bin/env bash
# CL-060 DECOMPOSITION CELL — isolate BUDGET at fixed width.
#   candidate: k_dets=4 x sims=2752  (total 11008)
#   opponent : deploy champion k_dets=4 x sims=688 (total 2752)
# Sibling cell to cl060_h2h_k8x1376_vs_deploy_k4x688 (which varied width AND budget).
# LOCAL box (5900XT), W16, share = /mnt/c/carc-shared

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

cd /home/doctor/projects/carcassone
export CARCASSONNE_TT_CAP=200000
exec nice -n 19 .venv/bin/python -u \
    scripts/classical_search/eval_fair_puct.py \
    --info fair --opponent fair-champion \
    --exact-k 2 --k-dets 4 --sims 2752 --opp-k-dets 4 --opp-sims 688 \
    --n 400 --paired --seed-start 44000000000 --workers 16 \
    --out-root /mnt/c/carc-shared/classical_search \
    --out-subdir cl060_budget_k4x2752_vs_deploy_k4x688 \
    --shared-claim --no-results-csv
