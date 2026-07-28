#!/usr/bin/env bash
# PROTOCOL_002 — residual-net(scale 0.25) vs iter_11 head-to-head. EVAL ONLY, no
# training. Box-agnostic (env SHARE/PY/W), --shared-claim into one shared pool.
#
#   5800x : SHARE=/mnt/c/carc-shared  PY=.venv/bin/python  W=14
#   xeon  : SHARE=/mnt/carc-shared    PY=.venv/bin/python  W=10
#   laptop: SHARE=/mnt/carc-shared    PY=.venv/bin/python  W=20
#
# NEW = residual.pt @ residual-scale 0.25 (value head ON); OLD = iter_11.pt @ 0
# (pure v2.7 policy). Per-side residual scale so the asymmetric value heads are
# fair. n=400 paired, seed 1e9, sims=200, matched v2.7 env, orchestrator, nice -n 19.
set -u

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
SHARE="${SHARE:-/mnt/c/carc-shared}"
PY="${PY:-$REPO/.venv/bin/python}"
W="${W:-14}"
N="${N:-400}"
SIMS="${SIMS:-200}"
SEED="${SEED:-1000000000}"
OUT="$SHARE/h2h_runs"
HOST="$(hostname)"

export CARCASSONNE_V25_CAP=12
export CARCASSONNE_V25_DROP_THREE_OPEN=1
export PYTHONUNBUFFERED=1

mkdir -p "$OUT"
cd "$REPO" || exit 2
echo "[$(date -u +%H:%M:%S)] h2h residual@0.25 vs iter_11 on $HOST | SHARE=$SHARE W=$W N=$N sims=$SIMS seed=$SEED"

nice -n 19 "$PY" -u scripts/eval_iter_head_to_head.py \
    --new-checkpoint "$SHARE/lever_seq/ckpt/residual.pt" --new-leaf-residual-scale 0.25 \
    --old-checkpoint "$SHARE/pathb_loop/ckpt/iter_11.pt" \
    --output-root "$OUT/residual_rs025_vs_iter11_s${SIMS}" --iter 1 --vs-iter 11 \
    --games "$N" --sims "$SIMS" --leaf-eval v2_5 --c-puct 3.0 \
    --workers "$W" --orchestrator --paired --seed-start "$SEED" \
    --shared-claim --claim-host "$HOST" --no-elo-log
# ⚠️ rc on the very next line — inline `rc=$?` beside $(date ...) always reads 0, because
#    the command substitution runs during word expansion and clobbers $? first.
rc=$?
echo "[$(date -u +%H:%M:%S)] <<< rc=$rc"
exit $rc
