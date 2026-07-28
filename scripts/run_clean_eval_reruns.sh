#!/usr/bin/env bash
# Clean-eval Phase-3 reruns — 5 EVAL cells, no training. Box-agnostic: resolve
# SHARE / PY / W / REPO from the environment so the SAME script runs on every box
# with --shared-claim work-stealing into one shared output pool.
#
#   5800x : SHARE=/mnt/c/carc-shared  PY=.venv/bin/python  W=14   (16 threads)
#   xeon  : SHARE=/mnt/carc-shared    PY=.venv/bin/python  W=10   (12 threads)
#   laptop: SHARE=/mnt/carc-shared    PY=.venv/bin/python  W=20
#
# All cells: n=400 paired, --seed-start 1e9 (clean namespace), sims=200, matched
# v2.7 opponent, env CAP=12 DROP_THREE_OPEN=1 (production v2.7), nice -n 19.
set -u

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
SHARE="${SHARE:-/mnt/c/carc-shared}"
PY="${PY:-$REPO/.venv/bin/python}"
W="${W:-14}"
N="${N:-400}"
SIMS="${SIMS:-200}"
SEED="${SEED:-1000000000}"
OUT="$SHARE/clean_eval_runs"
HOST="$(hostname)"

export CARCASSONNE_V25_CAP=12
export CARCASSONNE_V25_DROP_THREE_OPEN=1
export PYTHONUNBUFFERED=1

mkdir -p "$OUT"
cd "$REPO" || exit 2
echo "[$(date -u +%H:%M:%S)] clean-eval reruns on $HOST | SHARE=$SHARE W=$W N=$N sims=$SIMS seed=$SEED"

# ⚠️ rc is captured BEFORE the $(date ...) in the log line. Inline `rc=$?` next to a
#    command substitution always reads 0: bash expands the word left to right, so
#    $(date) runs and overwrites $? before the later $? is expanded — a failed leg
#    then logs "<<< rc=0". Also propagate: a failed leg must not look like a clean run.
run() {
  echo "[$(date -u +%H:%M:%S)] >>> $*"
  nice -n 19 "$@"
  local rc=$?
  echo "[$(date -u +%H:%M:%S)] <<< rc=$rc"
  return $rc
}

COMMON=(--n "$N" --sims "$SIMS" --paired --seed-start "$SEED" --shared-claim \
        --claim-host "$HOST" --workers "$W" --out-root "$OUT")

# R1 — pure leaf gap: HeuristicMCTS v2.7 vs v1 (no net)
run "$PY" scripts/eval_heur_vs_heur.py "${COMMON[@]}" \
    --out-subdir r1_leafgap_heur_v2_7_vs_v1_s${SIMS}

# R2 — iter_11 vs matched v2.7
run "$PY" scripts/eval_net_vs_heuristic.py "${COMMON[@]}" \
    --checkpoint "$SHARE/pathb_loop/ckpt/iter_11.pt" --heur-leaf v2_7 \
    --out-subdir r2_iter11_vs_heurv2_7_s${SIMS}

# R3 — Stage-B iter_01 vs matched v2.7 (clean rerun of the +48.1 cell)
run "$PY" scripts/eval_net_vs_heuristic.py "${COMMON[@]}" \
    --checkpoint "$SHARE/stage_b/ckpt/iter_01.pt" --heur-leaf v2_7 \
    --out-subdir r3_stageb_iter01_vs_heurv2_7_s${SIMS}

# R4a — residual net, scale 0 (value head OFF: pure-v2.7 control)
run "$PY" scripts/eval_net_vs_heuristic.py "${COMMON[@]}" \
    --checkpoint "$SHARE/lever_seq/ckpt/residual.pt" --residual-scale 0 --heur-leaf v2_7 \
    --out-subdir r4_residual_rs0_vs_heurv2_7_s${SIMS}

# R4b/R5 — residual net, scale 0.25 (value head ON). Marginal vs R4a; absolute vs v2.7.
run "$PY" scripts/eval_net_vs_heuristic.py "${COMMON[@]}" \
    --checkpoint "$SHARE/lever_seq/ckpt/residual.pt" --residual-scale 0.25 --heur-leaf v2_7 \
    --out-subdir r5_residual_rs025_vs_heurv2_7_s${SIMS}

echo "[$(date -u +%H:%M:%S)] all reruns dispatched on $HOST"
