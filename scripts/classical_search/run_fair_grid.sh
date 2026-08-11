#!/usr/bin/env bash
# A2 — equal-wall-clock fair-PIMC grid launcher (docs/PROGRAM_ROADMAP_2026-07-07.md A2).
#
# Sweeps the fair champion (FairHeuristicPriorAgent, PUCT+heuristic priors) vs the
# fixed h800 CL-022 rung over K (fair marginalized endgame handoff depth). Each cell
# is deck-paired, self-describing (summary.json + manifest.json), --no-results-csv,
# nice -n 19, CARCASSONNE_TT_CAP honored. Detached with setsid (Mac->Win->WSL SIGHUP
# safe). ONE box only — pass --shared-claim to fan across boxes yourself.
#
#   ⚠️ K>=3 is the RAM/OOM regime (marginalized solve has no alpha-beta over chance
#      nodes). K=2 is auto-safe; K=4/K=8 = ATTENDED ONLY, run one at a time and watch RAM.
#
# Usage:
#   scripts/classical_search/run_fair_grid.sh <K> [n] [seed_start] [k_dets] [sims] [workers] [info]
# Examples:
#   scripts/classical_search/run_fair_grid.sh 2 100 13000000000        # K=2 screen (auto-safe)
#   scripts/classical_search/run_fair_grid.sh 2 100 13000000000 8 344 14 clair   # CL-022 clair arm
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

REPO="/home/doctor/projects/carcassone"
PY="${REPO}/.venv/bin/python"
SCRIPT="${REPO}/scripts/classical_search/eval_fair_puct.py"

K="${1:?usage: run_fair_grid.sh <K> [n] [seed_start] [k_dets] [sims] [workers] [info]}"
N="${2:-100}"
SEED_START="${3:-13000000000}"
K_DETS="${4:-8}"
SIMS="${5:-344}"
WORKERS="${6:-14}"
INFO="${7:-fair}"
RUNG_SIMS="${RUNG_SIMS:-800}"
OUT_ROOT="${OUT_ROOT:-/mnt/c/carc-shared/classical_search}"
export CARCASSONNE_TT_CAP="${CARCASSONNE_TT_CAP:-200000}"

if [[ "${K}" -ge 3 ]]; then
  echo "⚠️  K=${K} is the RAM/OOM regime (marginalized, no alpha-beta). ATTENDED ONLY — watch RAM." >&2
fi

LOG="${OUT_ROOT}/fair_grid_${INFO}_k${K}_kd${K_DETS}_s${SIMS}_n${N}.log"
mkdir -p "${OUT_ROOT}"

echo "launching: info=${INFO} K=${K} k_dets=${K_DETS} sims=${SIMS} n=${N} seed=${SEED_START} "\
     "rung=h${RUNG_SIMS} W=${WORKERS} TT_CAP=${CARCASSONNE_TT_CAP} -> ${LOG}"

setsid nice -n 19 "${PY}" -u "${SCRIPT}" \
  --info "${INFO}" --exact-k "${K}" --k-dets "${K_DETS}" --sims "${SIMS}" \
  --rung-sims "${RUNG_SIMS}" --n "${N}" --paired --seed-start "${SEED_START}" \
  --workers "${WORKERS}" --out-root "${OUT_ROOT}" --shared-claim --no-results-csv \
  </dev/null >"${LOG}" 2>&1 &
disown || true
echo "detached pid $! ; tail -f ${LOG}"
