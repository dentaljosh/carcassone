#!/usr/bin/env bash
# F3 public-state oracle — detached-safe, resumable suite runner (spec §5.3/§5.4).
#
# Pure CPU, net-free. RAM is the binding constraint: the marginalized TT reaches ~1M
# entries on hard K=3 roots, so W is capped LOW and CARCASSONNE_TT_CAP freezes the
# table (correctness-neutral — a miss just recomputes). A vanished worker = OOM-killer;
# watch RAM. Resumable: run_oracle writes one atomic <root_id>.json per root and skips
# any that already exist, so re-invoking after a stop continues where it left off.
#
# Usage:
#   scripts/f3_public_state_oracle/run_suite.sh <roots.jsonl> <out_dir> [workers] [budget] [tt_cap] [sims] [k_dets]
# Detach (survives Mac-sleep SIGHUP + WSL teardown):
#   setsid nohup scripts/f3_public_state_oracle/run_suite.sh ... </dev/null >LOG 2>&1 &
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${REPO}/.venv/bin/python"

ROOTS="${1:?roots.jsonl required}"
OUT_DIR="${2:?out_dir required}"
WORKERS="${3:-4}"          # W <= RAM/~2GB; laptop K=3 default 4 (spec §5.3)
BUDGET="${4:-2000000}"     # per-root solver node budget (BudgetExceeded -> coverage miss)
TT_CAP="${5:-1500000}"     # CARCASSONNE_TT_CAP: freeze the TT at ~1.5M entries (~a few GB/worker)
SIMS="${6:-688}"           # k4x688 = the production fair budget
K_DETS="${7:-4}"
WALL_CAP="${8:-300}"       # per-root wall-clock cap seconds (SIGALRM); §5.3 '2M nodes / 300 s'

mkdir -p "${OUT_DIR}"
LOG="${OUT_DIR}/run.log"

echo "[$(date -Is)] F3 oracle suite: roots=${ROOTS} out=${OUT_DIR} W=${WORKERS} budget=${BUDGET} tt_cap=${TT_CAP} k${K_DETS}x${SIMS} wall=${WALL_CAP}s" | tee -a "${LOG}"

# nice -n 19: yield to interactive use / other cluster jobs on the shared box.
exec nice -n 19 env CARCASSONNE_TT_CAP="${TT_CAP}" \
  "${PY}" "${REPO}/scripts/f3_public_state_oracle/run_oracle.py" \
    --roots "${ROOTS}" \
    --out-dir "${OUT_DIR}" \
    --workers "${WORKERS}" \
    --budget "${BUDGET}" \
    --tt-cap "${TT_CAP}" \
    --sims "${SIMS}" \
    --k-dets "${K_DETS}" \
    --wall-cap "${WALL_CAP}" \
    >> "${LOG}" 2>&1
