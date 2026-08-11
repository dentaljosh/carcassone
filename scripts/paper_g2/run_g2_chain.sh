#!/usr/bin/env bash
# G2 architecture control — the serial training chain (cheapest-informative-first).
#
#   1. g2_resnet_scratch  (~0.8 h)  the in-experiment matched-budget ResNet control
#   2. g2_tf_match        (~1.3 h)  THE HEADLINE transformer control (7.73M params)
#   3. g2_tf_large        (~7.7 h)  the capacity leg (28.06M params)
#
# Bars: measurement/paper_g2_20260803/PREREG.md (committed before this ran).
# MEASUREMENT ONLY. No PRODUCTION.yaml, no champion change, no shared default changed.
#
# Launch DETACHED (the box has a dirty-reboot history and a Mac->Windows->WSL
# SIGHUP path):
#   setsid nohup .../run_g2_chain.sh > /mnt/c/carc-shared/paper_g2_20260803/chain.log 2>&1 < /dev/null &
# Every arm checkpoints EVERY epoch and accepts --resume, so a reboot costs at
# most one epoch. Re-running this script resumes each arm where it stopped.
set -uo pipefail

WT="${G2_TREE:-/home/doctor/projects/carcassone/.claude/worktrees/agent-a1860cb7f9dc6f899}"
PY=/home/doctor/projects/carcassone/.venv/bin/python
OUT=/mnt/c/carc-shared/paper_g2_20260803
EPOCHS="${G2_EPOCHS:-16}"

mkdir -p "$OUT"
cd "$WT"
export PYTHONPATH="$WT/src:$WT/engine:${PYTHONPATH:-}"

run_arm () {
  local arm="$1" micro="$2"
  local dir="$OUT/$arm"
  if [ -f "$dir/final.pt" ]; then
    echo "=== SKIP $arm (final.pt exists) @ $(date -Is)"
    return 0
  fi
  echo "=== START $arm micro=$micro epochs=$EPOCHS @ $(date -Is)"
  nice -n 19 "$PY" -u "$WT/scripts/paper_g2/train_g2.py" \
    --arm "$arm" --out-dir "$dir" --epochs "$EPOCHS" \
    --micro-batch "$micro" --num-workers 4 \
    --stage-local "/tmp/g2_stage" --resume
  echo "=== END   $arm rc=$? @ $(date -Is)"
}

"$PY" -c "import carcassonne_ai, sys; print('carcassonne_ai:', carcassonne_ai.__file__)"

run_arm resnet_scratch 256
run_arm tf_match       256
run_arm tf_large        64

echo "=== G2 CHAIN COMPLETE @ $(date -Is)"
