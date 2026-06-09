#!/bin/bash
# Quick contention-free leaf-speed probe: run run_selfplay_iter OFF vs FLAT at a
# given (W, G), NO warmup (single-thread W=1 is thermally stable; same fixed seed
# => identical games => the only delta is leaf speed). Prints games/min + FLAT/OFF
# ratio, and whether the position counts DIVERGED (the canonical-fsum signature =
# hard proof the flat path actually fired and was not silently bypassed).
#
# Purpose: the at-scale W=14 bench gave 1.02x; this isolates WHY. W=1 ratio = the
# pure Amdahl ceiling (no bandwidth/SMT contention) => tells us the leaf's true
# share of self-play wall time. W=1 >> W=14 => bandwidth wall. W=1 ~= W=14 => the
# leaf is simply a small fraction (NN priors + MCTS dominate).
#
# Usage:  W=1 G=2 bash scripts/quick_leaf_ratio.sh
set -u
WT=/home/doctor/projects/carc-leafdev
PY=/home/doctor/projects/carcassone/.venv/bin/python
W="${W:-1}"; G="${G:-2}"; SEED="${SEED:-2000000}"; SIMS="${SIMS:-200}"; BATCH="${BATCH:-8}"
CKPT_SRC="${CKPT:-/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter4.pt}"
OUTROOT=/tmp/quick_leaf_ratio
export PYTHONPATH="$WT/src:$WT/engine"
COMMON_ENV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"
cd "$WT" || { echo "FATAL no worktree"; exit 1; }
[ -f "$CKPT_SRC" ] || { echo "FATAL no ckpt $CKPT_SRC"; exit 1; }
mkdir -p "$OUTROOT"; CKPT=$OUTROOT/ckpt.pt; cp -f "$CKPT_SRC" "$CKPT"

run_one() {  # $1=mode $2=extra_env  -> echoes "pos wall"
  local mode=$1 xenv=$2; local TMP=$OUTROOT/${mode}; rm -rf "$TMP"; mkdir -p "$TMP"
  local OUT
  OUT=$(nice -n 19 env $COMMON_ENV $xenv $PY -u scripts/run_selfplay_iter.py \
    --iter 0 --games "$G" --sims "$SIMS" --leaf-eval v2_5 --value-blend 0.0 \
    --value-target score_diff --workers "$W" --batch-size "$BATCH" \
    --checkpoint "$CKPT" --anchor-fraction 0.3 --anchor-checkpoint "$CKPT" \
    --output-root "$TMP" --seed-start "$SEED" 2>&1)
  rm -rf "$TMP"
  printf '%s\n' "$OUT" | grep -oE '[0-9]+ positions, [0-9.]+s wallclock' | tail -1
}

echo "### quick leaf ratio  W=$W G=$G sims=$SIMS seed=$SEED @ $(date +%H:%M:%S)"
OFF=$(run_one OFF "");                         echo "  OFF : $OFF"
FLAT=$(run_one FLAT "CARCASSONNE_USE_FLAT_LEAF=1"); echo "  FLAT: $FLAT"
op=$(echo "$OFF"  | grep -oE '^[0-9]+'); ow=$(echo "$OFF"  | grep -oE '[0-9.]+s' | tr -d s)
fp=$(echo "$FLAT" | grep -oE '^[0-9]+'); fw=$(echo "$FLAT" | grep -oE '[0-9.]+s' | tr -d s)
[ -z "$op" ] || [ -z "$fw" ] && { echo "PARSE FAIL"; exit 1; }
awk "BEGIN{
  ogpm=$G/($ow/60); fgpm=$G/($fw/60);
  printf \"  -> OFF %.2f g/min (%ss)  FLAT %.2f g/min (%ss)  ratio %.3fx\n\", ogpm,$ow,fgpm,$fw,fgpm/ogpm;
  printf \"  positions: OFF=%d FLAT=%d  %s\n\", $op,$fp, ($op==$fp?\"(identical — check firing!)\":\"(DIVERGED — flat fired, canonical-sum signature)\")
}"
