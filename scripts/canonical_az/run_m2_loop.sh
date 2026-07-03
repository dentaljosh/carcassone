#!/usr/bin/env bash
# M2 canonical-AZ sighted loop (MEASUREMENT ONLY — see measurement/canonical_az/M2_PLAN.md).
#
# The "never-run cell": sighted CNN (81ch/42-scalar) x pooled value head x
# non-degenerate target (score_diff_wide) x FPU=0.6 installed. Runs the short
# gen->train->eval loop off a FRESH sighted warmstart.
#
# ORCH-ACCELERATED (2026-07-03): with USE_ORCH=1 (default) gen runs through the
# channel-configurable carc-orch SHM orchestrator (~1.33x over orch-off on one
# shared GPU context) and the per-iter health check is a FAST net-vs-FIXED-net
# through two orch servers (sighted cand @81ch vs blind RoD-v2 iter_02 @78ch),
# NOT the slow net-vs-h3200. USE_ORCH=0 falls back to orch-off gen + h3200 eval.
#
# Multi-box: SHARED_CLAIM=1 pools gen across boxes; set LAPTOP_HOST + LAPTOP_REPO
# to also drive the laptop's gen (requires the laptop carc-orch REBUILT for the
# 81ch layout + WARMSTART_CKPT/OUT on the shared mount). See M2_ORCH_READY.md.
#
# Resumable: skips any iter whose checkpoint already exists. Detach with
#   setsid nohup nice -n 19 bash scripts/canonical_az/run_m2_loop.sh > /tmp/m2.log 2>&1 < /dev/null & disown
#
# This is the loop the HUMAN GREEN-LIGHTS (~2-3 day / ~15-25 box-hour budget commit).
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"
export PYTHONPATH="$REPO/src"
export CARCASSONNE_USE_FLAT_LEAF="${CARCASSONNE_USE_FLAT_LEAF:-1}"
export CARCASSONNE_USE_CY_REPR="${CARCASSONNE_USE_CY_REPR:-1}"
# v2.9 champion leaf curve — makes the eval opponent's leaf == h_v2.9 (production
# `v2_9_1_Bmild_cap8`). Affects ONLY the HeuristicMCTS/leaf-value path, not the net.
export CARCASSONNE_V29_MEEPLE_CURVE="${CARCASSONNE_V29_MEEPLE_CURVE:--8,-4,-1,0,2,3,4,5}"

PY="$REPO/.venv/bin/python"
HOST="${HOST:-$(hostname)}"

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
TRAIN_BATCH="${TRAIN_BATCH:-256}"
SEED_START="${SEED_START:-0}"
EVAL_N="${EVAL_N:-200}"

# orch knobs
USE_ORCH="${USE_ORCH:-1}"          # 1 = orch gen + dual-net eval; 0 = orch-off + h3200
GEN_OW="${GEN_OW:-28}"             # orch gen workers (local 28 / laptop 8); orch-off default 14
GEN_WORKERS="${GEN_WORKERS:-14}"   # orch-off per-worker self-play W (USE_ORCH=0)
EVAL_OW="${EVAL_OW:-28}"           # dual-server eval workers/server (local 28 / laptop 16)
REF_CKPT="${REF_CKPT:-/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt}"  # FIXED blind anchor
EVAL_H3200_ALSO="${EVAL_H3200_ALSO:-0}"   # 1 = also run the slower h3200 deep check
EVAL_HEUR_SIMS="${EVAL_HEUR_SIMS:-3200}"

# multi-box gen (optional; requires laptop carc-orch rebuilt + shared paths)
SHARED_CLAIM="${SHARED_CLAIM:-0}"
LAPTOP_HOST="${LAPTOP_HOST:-}"                 # e.g. laptop (blank = local-only)
LAPTOP_REPO="${LAPTOP_REPO:-/home/doctor/projects/carcassone}"

[ -f "$WARMSTART_CKPT" ] || { echo "FATAL: warmstart ckpt not found: $WARMSTART_CKPT (train it first — see M2_ORCH_READY.md)"; exit 1; }
mkdir -p "$OUT/ckpt" "$OUT/buffer" "$OUT/eval"

claim_flag=""; [ "$SHARED_CLAIM" = "1" ] && claim_flag="--shared-claim --claim-host $HOST"

# Kick the laptop's gen for this iter in the background (shared-claim pool). Uses
# the mandatory .sh-pipe remote pattern (cd on line 1). Translates the local
# /mnt/c/carc-shared share path to the laptop's /mnt/carc-shared. NOT smoke-tested
# from the build session — verify the laptop binary is rebuilt (81ch) first.
_kick_laptop_gen() {
  local it="$1"
  local lwarm="${WARMSTART_CKPT/\/mnt\/c\/carc-shared//mnt/carc-shared}"
  local lout="${OUT/\/mnt\/c\/carc-shared//mnt/carc-shared}"
  local lref="${REF_CKPT/\/mnt\/c\/carc-shared//mnt/carc-shared}"
  echo "[m2-loop] kicking laptop gen (iter $it) on $LAPTOP_HOST"
  ssh "$LAPTOP_HOST" 'bash -s' <<EOF &
cd "$LAPTOP_REPO" || exit 1
REPO="$LAPTOP_REPO" HOST=laptop WARM="$lwarm" ITER="$it" OUT="$lout/buffer" \\
  GAMES="$GAMES" SIMS="$SIMS" FPU="$FPU" CPUCT="$CPUCT" OW=8 SEED_START="$SEED_START" \\
  setsid nohup bash scripts/canonical_az/gen_m2_orch.sh --shared-claim --claim-host laptop \\
  > /tmp/m2_laptop_gen_${it}.log 2>&1 < /dev/null &
EOF
}

PREV="$WARMSTART_CKPT"
for it in $(seq "$START" "$ITERS"); do
  CKPT="$OUT/ckpt/iter_$(printf %02d "$it").pt"
  if [ -f "$CKPT" ]; then echo "[iter $it] ckpt exists ($CKPT) — resume-skip"; PREV="$CKPT"; continue; fi

  # ---------- GEN ----------
  if [ "$USE_ORCH" = "1" ]; then
    echo "=== [iter $it] GEN ORCH ($GAMES games, sims=$SIMS, fpu=$FPU, $VALUE_TARGET, --leaf-eval nn) ==="
    [ -n "$LAPTOP_HOST" ] && [ "$SHARED_CLAIM" = "1" ] && _kick_laptop_gen "$it"
    # local orch gen (foreground; exits when the shared pool is complete). gen_m2_orch
    # exports the sighted net, launches carc-orch --n-ch 81 --n-scalar 42, runs
    # run_selfplay_iter --shm-eval-server; passes claim flags through.
    REPO="$REPO" HOST="$HOST" WARM="$PREV" ITER="$it" OUT="$OUT/buffer" \
      GAMES="$GAMES" SIMS="$SIMS" FPU="$FPU" CPUCT="$CPUCT" OW="$GEN_OW" \
      VALUE_TARGET="$VALUE_TARGET" SEED_START="$SEED_START" \
      bash scripts/canonical_az/gen_m2_orch.sh $claim_flag \
      || { echo "FATAL: orch gen failed (iter $it)"; exit 1; }
  else
    echo "=== [iter $it] GEN ORCH-OFF ($GAMES games, sims=$SIMS, fpu=$FPU, $VALUE_TARGET) ==="
    nice -n 19 "$PY" -u scripts/run_selfplay_iter.py \
      --checkpoint "$PREV" --iter "$it" --games "$GAMES" \
      --sims "$SIMS" --c-puct "$CPUCT" --fpu "$FPU" \
      --value-target "$VALUE_TARGET" --leaf-eval nn \
      --workers "$GEN_WORKERS" --seed-start "$SEED_START" $claim_flag \
      --output-root "$OUT/buffer" || { echo "FATAL: orch-off gen failed (iter $it)"; exit 1; }
  fi

  # ---------- TRAIN (local, GPU-latency-bound single-proc) ----------
  echo "=== [iter $it] TRAIN (global-pool, vlw=$VLW, epochs=$EPOCHS) ==="
  # First loop iter re-inits the value head fresh (--warm-value-fresh): the sighted
  # warmstart's value head learned the heuristic tanh(vs/15) target, but the loop
  # learns the score_diff_wide OUTCOME target. Later iters continue the head.
  wvf=""; [ "$it" = "$START" ] && wvf="--warm-value-fresh"
  nice -n 19 "$PY" -u scripts/train_iter.py \
    --iter "$it" --window "$WINDOW" \
    --warm-from "$PREV" --output "$CKPT" --output-root "$OUT/buffer" \
    --global-pool $wvf --value-loss-weight "$VLW" \
    --batch-size "$TRAIN_BATCH" --epochs "$EPOCHS" \
    --warmstart-mix-fraction 0.0 \
    --prov-value-target "$VALUE_TARGET" --prov-selfplay-leaf "sighted_nn_head" \
    || { echo "FATAL: train failed (iter $it)"; exit 1; }

  # ---------- EVAL (per-iter health check) ----------
  if [ "$USE_ORCH" = "1" ]; then
    echo "=== [iter $it] EVAL dual-net: sighted cand vs FIXED $(basename "$REF_CKPT") (n=$EVAL_N, sims=$SIMS, fpu=$FPU) ==="
    CAND="$CKPT" REF="$REF_CKPT" HOST="$HOST" OW="$EVAL_OW" SIMS="$SIMS" N="$EVAL_N" \
      FPU="$FPU" CPUCT="$CPUCT" OUT="$OUT/eval" \
      bash scripts/canonical_az/eval_m2_dual_orch.sh --paired \
      || echo "[iter $it] dual-net eval nonzero exit (non-fatal)"
  fi
  if [ "$USE_ORCH" != "1" ] || [ "$EVAL_H3200_ALSO" = "1" ]; then
    echo "=== [iter $it] EVAL vs h_v2.9@${EVAL_HEUR_SIMS} (n=$EVAL_N, fpu=$FPU) [deep check] ==="
    nice -n 19 "$PY" -u scripts/eval_net_vs_heuristic.py \
      --checkpoint "$CKPT" --n "$EVAL_N" --sims "$SIMS" \
      --heur-sims "$EVAL_HEUR_SIMS" --heur-leaf v2_7 --fpu "$FPU" \
      --c-puct "$CPUCT" --out-root "$OUT/eval_h3200" || echo "[iter $it] h3200 eval nonzero exit (non-fatal)"
  fi

  PREV="$CKPT"
done
echo "=== M2 loop done (iters $START..$ITERS). Solver-scored read-out is a SEPARATE step (M2_PLAN Part A). ==="
