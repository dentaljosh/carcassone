#!/usr/bin/env bash
# M2 canonical-AZ sighted loop (MEASUREMENT ONLY — see measurement/canonical_az/M2_PLAN.md).
#
# The "never-run cell": sighted CNN (81ch/42-scalar) x pooled value head x
# non-degenerate target (score_diff_wide) x FPU=0.6 installed. This runs the
# short gen->train->eval loop off a FRESH sighted warmstart. Do NOT confuse with
# scripts/rod_v2/run_rod_v2_flywheel.sh (that is the v2.9-residual recipe on the
# SHM orchestrator; sighted CANNOT use the orch — its transport is fixed at
# 78ch/12-scalar — so this loop runs gen ORCH-OFF, per-worker).
#
# Resumable: skips any iter whose checkpoint already exists. Checkpoints land in
# $OUT/ckpt/iter_NN.pt; self-play buffer in $OUT/buffer/iter_NN/. Detach with
#   setsid nohup nice -n 19 bash scripts/canonical_az/run_m2_loop.sh > /tmp/m2.log 2>&1 < /dev/null & disown
#
# This is the loop the HUMAN GREEN-LIGHTS. It is a ~2-3 day / ~15-25 box-hour
# budget commit (M2_PLAN go/no-go) — launch deliberately, not silently.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"
export PYTHONPATH="$REPO/src"
export CARCASSONNE_USE_FLAT_LEAF="${CARCASSONNE_USE_FLAT_LEAF:-1}"
export CARCASSONNE_USE_CY_REPR="${CARCASSONNE_USE_CY_REPR:-1}"
# v2.9 champion leaf curve — makes the eval opponent's --heur-leaf v2_7 == h_v2.9
# (the production leaf `v2_9_1_Bmild_cap8`; governance/PRODUCTION.yaml). This env
# affects ONLY the HeuristicMCTS opponent's leaf, not the sighted net.
export CARCASSONNE_V29_MEEPLE_CURVE="${CARCASSONNE_V29_MEEPLE_CURVE:--8,-4,-1,0,2,3,4,5}"

PY="$REPO/.venv/bin/python"

# --- knobs (env-overridable) -------------------------------------------------
WARMSTART_CKPT="${WARMSTART_CKPT:-$REPO/checkpoints/warmstart_sighted.pt}"
OUT="${OUT:-$REPO/data/m2_sighted}"
START="${START:-0}"
ITERS="${ITERS:-4}"          # inclusive; START=0 ITERS=4 -> iters 0,1,2,3,4 = 5 iters
GAMES="${GAMES:-400}"
SIMS="${SIMS:-200}"          # PUCT@200 (Gumbel not built — M2_PLAN MVP fallback)
CPUCT="${CPUCT:-3.0}"
FPU="${FPU:-0.6}"            # M2 fixed ingredient (M3: weaned value craters without it)
VALUE_TARGET="${VALUE_TARGET:-score_diff_wide}"
VLW="${VLW:-1.5}"
EPOCHS="${EPOCHS:-3}"
WINDOW="${WINDOW:-5}"        # replay-buffer window (iters)
GEN_WORKERS="${GEN_WORKERS:-14}"   # per-worker nets; local 5900XT self-play optimum
TRAIN_BATCH="${TRAIN_BATCH:-256}"
EVAL_N="${EVAL_N:-200}"
EVAL_HEUR_SIMS="${EVAL_HEUR_SIMS:-3200}"   # h3200 opponent
SHARED_CLAIM="${SHARED_CLAIM:-0}"   # set 1 (+ launch on each box) for multi-box work-stealing

[ -f "$WARMSTART_CKPT" ] || { echo "FATAL: warmstart ckpt not found: $WARMSTART_CKPT (train it first — see M2_BUILD_STATUS)"; exit 1; }
mkdir -p "$OUT/ckpt" "$OUT/buffer"

claim_flag=""; [ "$SHARED_CLAIM" = "1" ] && claim_flag="--shared-claim"

PREV="$WARMSTART_CKPT"
for it in $(seq "$START" "$ITERS"); do
  CKPT="$OUT/ckpt/iter_$(printf %02d "$it").pt"
  if [ -f "$CKPT" ]; then echo "[iter $it] ckpt exists ($CKPT) — resume-skip"; PREV="$CKPT"; continue; fi

  echo "=== [iter $it] GEN ($GAMES games, sims=$SIMS, fpu=$FPU, $VALUE_TARGET, ORCH-OFF) ==="
  nice -n 19 "$PY" -u scripts/run_selfplay_iter.py \
    --checkpoint "$PREV" --iter "$it" --games "$GAMES" \
    --sims "$SIMS" --c-puct "$CPUCT" --fpu "$FPU" \
    --value-target "$VALUE_TARGET" --leaf-eval nn \
    --workers "$GEN_WORKERS" $claim_flag \
    --output-root "$OUT/buffer"

  echo "=== [iter $it] TRAIN (global-pool, vlw=$VLW, epochs=$EPOCHS) ==="
  # First loop iter re-inits the value head fresh (--warm-value-fresh): the sighted
  # warmstart's value head was trained on the heuristic tanh(vs/15) target, but the
  # loop learns the score_diff_wide outcome target. Later iters continue the head.
  wvf=""; [ "$it" = "$START" ] && wvf="--warm-value-fresh"
  nice -n 19 "$PY" -u scripts/train_iter.py \
    --iter "$it" --window "$WINDOW" \
    --warm-from "$PREV" --output "$CKPT" --output-root "$OUT/buffer" \
    --global-pool $wvf --value-loss-weight "$VLW" \
    --batch-size "$TRAIN_BATCH" --epochs "$EPOCHS" \
    --warmstart-mix-fraction 0.0 \
    --prov-value-target "$VALUE_TARGET" --prov-selfplay-leaf "sighted_nn_head"

  echo "=== [iter $it] EVAL vs h_v2.9@${EVAL_HEUR_SIMS} (n=$EVAL_N, fpu=$FPU) ==="
  nice -n 19 "$PY" -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$CKPT" --n "$EVAL_N" --sims "$SIMS" \
    --heur-sims "$EVAL_HEUR_SIMS" --heur-leaf v2_7 --fpu "$FPU" \
    --c-puct "$CPUCT" --out-root "$OUT/eval" || echo "[iter $it] eval nonzero exit (non-fatal)"

  PREV="$CKPT"
done
echo "=== M2 loop done (iters $START..$ITERS). Solver-scored read-out is a SEPARATE step (M2_PLAN Part A). ==="
