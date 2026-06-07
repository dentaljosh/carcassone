#!/usr/bin/env bash
# Clean-eval TOP-UP — resolve the two INCONCLUSIVE cells from the Phase-3 pass.
# EVAL ONLY, no training. Box-agnostic (env SHARE/PY/W/REPO), --shared-claim into
# one shared pool so all 3 boxes work-steal the same todo list.
#
#   5800x : SHARE=/mnt/c/carc-shared  PY=.venv/bin/python  W=14
#   xeon  : SHARE=/mnt/carc-shared    PY=.venv/bin/python  W=10
#   laptop: SHARE=/mnt/carc-shared    PY=.venv/bin/python  W=20
#
# Two questions this run answers:
#   (1) RESIDUAL VALUE-HEAD MARGINAL — extend the scale-0 and scale-0.25 cells
#       from n=400 -> n=1200 paired (resumes the existing r4/r5 dirs, adds 800
#       games each). At n_paired=1200 the +0.0375 winrate marginal (z=1.30 @ 400)
#       reaches z~2.25 IF real, else resolves as null.
#   (2) NON-TRANSITIVITY — clean net-vs-heur-`v1` cells for iter_11 & Stage-B at
#       n=400, on the SAME decks as the clean v2.7 cells (r2/r3). Replaces the old
#       CONTAMINATED v1 numbers (iter_11 +25.2, Stage-B +86.9) with clean ones, so
#       the 2x2 (net x {v1,v2.7} leaf) is fully on the repaired ruler.
#
# All cells: paired, --seed-start 1e9 (clean namespace), sims=200, env
# CAP=12 DROP_THREE_OPEN=1 (production v2.7), deck hashes, evaluator manifest,
# runtime-verified provenance, nice -n 19.
set -u

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
SHARE="${SHARE:-/mnt/c/carc-shared}"
PY="${PY:-$REPO/.venv/bin/python}"
W="${W:-14}"
RESID_N="${RESID_N:-1200}"   # target per residual cell (was 400; +800 new each)
V1_N="${V1_N:-400}"          # per non-transitivity cell
SIMS="${SIMS:-200}"
SEED="${SEED:-1000000000}"
OUT="$SHARE/clean_eval_runs"
HOST="$(hostname)"

export CARCASSONNE_V25_CAP=12
export CARCASSONNE_V25_DROP_THREE_OPEN=1
export PYTHONUNBUFFERED=1

mkdir -p "$OUT"
cd "$REPO" || exit 2
echo "[$(date -u +%H:%M:%S)] clean-eval TOP-UP on $HOST | SHARE=$SHARE W=$W resid_n=$RESID_N v1_n=$V1_N sims=$SIMS seed=$SEED"

run() { echo "[$(date -u +%H:%M:%S)] >>> $*"; nice -n 19 "$@"; echo "[$(date -u +%H:%M:%S)] <<< rc=$?"; }

COMMON_RESID=(--n "$RESID_N" --sims "$SIMS" --paired --seed-start "$SEED" --shared-claim \
        --claim-host "$HOST" --workers "$W" --out-root "$OUT")
COMMON_V1=(--n "$V1_N" --sims "$SIMS" --paired --seed-start "$SEED" --shared-claim \
        --claim-host "$HOST" --workers "$W" --out-root "$OUT")

# (1a) residual scale 0 — EXTEND r4 to RESID_N (value head OFF: pure-v2.7 control)
run "$PY" scripts/eval_net_vs_heuristic.py "${COMMON_RESID[@]}" \
    --checkpoint "$SHARE/lever_seq/ckpt/residual.pt" --residual-scale 0 --heur-leaf v2_7 \
    --out-subdir r4_residual_rs0_vs_heurv2_7_s${SIMS}

# (1b) residual scale 0.25 — EXTEND r5 to RESID_N (value head ON). Marginal vs (1a).
run "$PY" scripts/eval_net_vs_heuristic.py "${COMMON_RESID[@]}" \
    --checkpoint "$SHARE/lever_seq/ckpt/residual.pt" --residual-scale 0.25 --heur-leaf v2_7 \
    --out-subdir r5_residual_rs025_vs_heurv2_7_s${SIMS}

# (2a) iter_11 vs heur-v1 (clean) — non-transitivity vs the +89.7 v2.7 cell (r2)
run "$PY" scripts/eval_net_vs_heuristic.py "${COMMON_V1[@]}" \
    --checkpoint "$SHARE/pathb_loop/ckpt/iter_11.pt" --heur-leaf v1 \
    --out-subdir t1_iter11_vs_heurv1_s${SIMS}

# (2b) Stage-B iter_01 vs heur-v1 (clean) — non-transitivity vs the +34.9 v2.7 cell (r3)
run "$PY" scripts/eval_net_vs_heuristic.py "${COMMON_V1[@]}" \
    --checkpoint "$SHARE/stage_b/ckpt/iter_01.pt" --heur-leaf v1 \
    --out-subdir t2_stageb_iter01_vs_heurv1_s${SIMS}

echo "[$(date -u +%H:%M:%S)] all top-up cells dispatched on $HOST"
