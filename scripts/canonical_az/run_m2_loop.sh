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
GEN_OW="${GEN_OW:-28}"             # LOCAL orch gen workers; orch-off default 14
LAPTOP_GEN_OW="${LAPTOP_GEN_OW:-8}"  # laptop orch gen workers (8GB 4070m ceiling)
GEN_WORKERS="${GEN_WORKERS:-14}"   # orch-off per-worker self-play W (USE_ORCH=0)
EVAL_OW="${EVAL_OW:-28}"           # dual-server eval workers/server (local 28 / laptop 16)
REF_CKPT="${REF_CKPT:-/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt}"  # FIXED blind anchor
EVAL_H3200_ALSO="${EVAL_H3200_ALSO:-0}"   # 1 = also run the slower h3200 deep check
EVAL_HEUR_SIMS="${EVAL_HEUR_SIMS:-3200}"

# multi-box gen (optional; requires laptop carc-orch rebuilt + shared paths)
SHARED_CLAIM="${SHARED_CLAIM:-0}"
LAPTOP_HOST="${LAPTOP_HOST:-}"                 # e.g. laptop-wsl (blank = local-only)
LAPTOP_REPO="${LAPTOP_REPO:-/home/doctor/projects/carcassone}"

# gen wait-for-pool barrier (self-healing; mirrors run_rod_v2_flywheel.sh)
GEN_POLL="${GEN_POLL:-30}"         # poll interval (s) for the shared-pool barrier
STALL_GEN="${STALL_GEN:-5}"        # consecutive no-progress polls before a heal (5*30s=2.5min)
HEAL_CAP="${HEAL_CAP:-10}"         # max heals per iter before FATAL
STALE_MIN="${STALE_MIN:-5}"        # a .claim (no .npz) older than this (min) is stranded (game<60s @sims200)
GEN_LOGS="${GEN_LOGS:-$OUT/logs}"; mkdir -p "$GEN_LOGS"

[ -f "$WARMSTART_CKPT" ] || { echo "FATAL: warmstart ckpt not found: $WARMSTART_CKPT (train it first — see M2_ORCH_READY.md)"; exit 1; }
mkdir -p "$OUT/ckpt" "$OUT/buffer" "$OUT/eval"

claim_flag=""; [ "$SHARED_CLAIM" = "1" ] && claim_flag="--shared-claim --claim-host $HOST"

_npz_count() { ls "$1"/*.npz 2>/dev/null | wc -l; }

# Remove .claim files with no matching .npz (owner died mid-game). age=0 -> all;
# age>0 -> only claims older than `age` MINUTES (so a live game, <60s @sims200, is
# never falsely freed). Mirrors run_rod_v2_flywheel.sh::_clean_stranded.
_clean_stranded() {
  local dir="$1" age="${2:-0}" c
  if [ "$age" = "0" ]; then
    for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.npz" ] || rm -f "$c"; done
  else
    while IFS= read -r c; do [ -e "${c%.claim}.npz" ] || rm -f "$c"; done \
      < <(find "$dir" -name '*.claim' -mmin +"$age" 2>/dev/null)
  fi
}

# Kill the M2 gen pool (carc-orch m2gen server + run_selfplay) on local AND laptop
# + clear the local m2gen shm. Scoped to m2gen shm-names so it never touches the
# eval servers or a sibling job. Bracket-trick patterns avoid self-match.
_kill_gen() {
  pkill -9 -f "[c]arc-orch.*m2gen" 2>/dev/null || true
  pkill -9 -f "[r]un_selfplay_iter" 2>/dev/null || true
  pkill -9 -f "[g]en_m2_orch" 2>/dev/null || true
  rm -f /dev/shm/carc_m2gen"$HOST" /dev/shm/sem.carc_m2gen"${HOST}"_* 2>/dev/null || true
  if [ -n "$LAPTOP_HOST" ] && [ "$SHARED_CLAIM" = "1" ]; then
    timeout 20 ssh -o ConnectTimeout=10 "$LAPTOP_HOST" \
      "pkill -9 -f '[c]arc-orch.*m2gen'; pkill -9 -f '[r]un_selfplay_iter'; pkill -9 -f '[g]en_m2_orch'; rm -f /dev/shm/carc_m2genlaptop /dev/shm/sem.carc_m2genlaptop_*" \
      </dev/null >/dev/null 2>&1 || true
  fi
}

# Launch the (1- or 2-box) shared-claim gen pool for iter $1 (parent ckpt $2).
# LOCAL gen_m2_orch backgrounded; LAPTOP gen via the mandatory .sh-pipe remote
# pattern (cd on line 1), backgrounded so a slow/hung laptop ssh can't starve the
# barrier. The laptop reads the parent ckpt from the share (path-translated).
_gen_launch() {
  local it="$1" prev="$2"
  REPO="$REPO" HOST="$HOST" WARM="$prev" ITER="$it" OUT="$OUT/buffer" \
    GAMES="$GAMES" SIMS="$SIMS" FPU="$FPU" CPUCT="$CPUCT" OW="$GEN_OW" \
    VALUE_TARGET="$VALUE_TARGET" SEED_START="$SEED_START" \
    nohup nice -n 19 bash scripts/canonical_az/gen_m2_orch.sh --shared-claim --claim-host "$HOST" \
    > "$GEN_LOGS/gen_${HOST}_it${it}.log" 2>&1 & disown
  if [ -n "$LAPTOP_HOST" ] && [ "$SHARED_CLAIM" = "1" ]; then
    local lprev="${prev/\/mnt\/c\/carc-shared//mnt/carc-shared}"
    local lout="${OUT/\/mnt\/c\/carc-shared//mnt/carc-shared}"
    echo "[m2-loop] launch laptop gen (iter $it, parent $(basename "$prev")) on $LAPTOP_HOST OW=$LAPTOP_GEN_OW"
    ssh "$LAPTOP_HOST" 'bash -s' <<EOF &
cd "$LAPTOP_REPO" || exit 1
REPO="$LAPTOP_REPO" HOST=laptop WARM="$lprev" ITER="$it" OUT="$lout/buffer" \\
  GAMES="$GAMES" SIMS="$SIMS" FPU="$FPU" CPUCT="$CPUCT" OW="$LAPTOP_GEN_OW" SEED_START="$SEED_START" \\
  setsid nohup nice -n 19 bash scripts/canonical_az/gen_m2_orch.sh --shared-claim --claim-host laptop \\
  > /tmp/m2_laptop_gen_${it}.log 2>&1 < /dev/null &
EOF
  fi
}

# Kill any lingering M2 gen pool on exit (both boxes) so a Ctrl-C / reboot doesn't
# strand a laptop server.
trap '_kill_gen 2>/dev/null || true' EXIT

PREV="$WARMSTART_CKPT"
for it in $(seq "$START" "$ITERS"); do
  CKPT="$OUT/ckpt/iter_$(printf %02d "$it").pt"
  if [ -f "$CKPT" ]; then echo "[iter $it] ckpt exists ($CKPT) — resume-skip"; PREV="$CKPT"; continue; fi

  DATA="$OUT/buffer/iter_$(printf %02d "$it")"
  mkdir -p "$DATA"
  # ---------- GEN ----------
  if [ "$USE_ORCH" = "1" ]; then
    if [ "$(_npz_count "$DATA")" -ge "$GAMES" ]; then
      echo "=== [iter $it] GEN already complete ($(_npz_count "$DATA")/$GAMES) — resume-skip ==="
    else
      echo "=== [iter $it] GEN ORCH ($GAMES games, sims=$SIMS, fpu=$FPU, $VALUE_TARGET, --leaf-eval nn; local W$GEN_OW${LAPTOP_HOST:+ + laptop W$LAPTOP_GEN_OW}) ==="
      # Clean stranded claims (prior-run deaths), kill any lingering pool, launch
      # the shared-claim gen on both boxes, then WAIT for the pool to fill
      # (self-healing: a stall -> clean stranded + relaunch). This barrier is what
      # keeps train from running on partial data + lets the laptop carry the pool
      # across a local reboot (on resume, existing npz are kept, only missing
      # seeds are replayed — NO wipe).
      _clean_stranded "$DATA" 0
      _kill_gen; sleep 2
      _gen_launch "$it" "$PREV"
      glast=-1; gstall=0; gheals=0
      while [ "$(_npz_count "$DATA")" -lt "$GAMES" ]; do
        sleep "$GEN_POLL"  # allow-sleep
        gcur=$(_npz_count "$DATA")
        echo "[iter $it] gen $gcur/$GAMES @ $(date +%H:%M:%S)"
        if [ "$gcur" -eq "$glast" ]; then gstall=$((gstall+1)); else gstall=0; glast=$gcur; fi
        if [ "$gstall" -ge "$STALL_GEN" ]; then
          gheals=$((gheals+1))
          [ "$gheals" -gt "$HEAL_CAP" ] && { echo "FATAL: gen stuck $gcur/$GAMES after $HEAL_CAP heals (iter $it)"; exit 1; }
          echo "[iter $it] gen STALLED $gcur/$GAMES — heal $gheals: kill+clean+relaunch @ $(date +%H:%M:%S)"
          _kill_gen; sleep 2; _clean_stranded "$DATA" "$STALE_MIN"
          _gen_launch "$it" "$PREV"; gstall=0
        fi
      done
      _kill_gen; sleep 1
      echo "[iter $it] gen complete ($(_npz_count "$DATA")/$GAMES npz) @ $(date +%H:%M:%S)"
    fi
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
