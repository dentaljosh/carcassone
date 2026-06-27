#!/usr/bin/env bash
# High-gap distillation driver — Stage 4 (train) + Stage 5 (held-out eval).
# Policy-only soft-target (Q-softmax) fine-tune from iter04, with a decisive-state
# stabiliser mix (anti-forgetting). NOT a flywheel; no promotion. Run AFTER the gate
# (analyze_signal_density) passes and build_splits has written the tier npz.
set -euo pipefail
cd /home/doctor/projects/carcassone
PY=.venv/bin/python
M=measurement/high_gap_distillation
SHARE=/mnt/c/carc-shared/high_gap_distillation
mkdir -p "$SHARE"
I04=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_04.pt
I06=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_06.pt
STAB="$M/data/stabilizer/iter_00"
COMMON="--iter 0 --window 1 --epochs 15 --lr 2e-4 --batch-size 64 \
  --aux-weight 0 --value-loss-weight 0 --val-fraction 0 --entropy-floor-frac 0"

case "${1:-help}" in
  r1)  # 70% hard / 30% stabiliser, from iter04
    CUDA_VISIBLE_DEVICES=0 nice -n 19 $PY scripts/train_iter.py \
      --output-root "$M/data/hard_train" --warm-from "$I04" \
      --warmstart-root "$STAB" --warmstart-mix-fraction 0.30 \
      --output "$SHARE/R1_from_iter04.pt" $COMMON ;;
  r2)  # 50% hard / 50% stabiliser, from iter04
    CUDA_VISIBLE_DEVICES=0 nice -n 19 $PY scripts/train_iter.py \
      --output-root "$M/data/hard_train" --warm-from "$I04" \
      --warmstart-root "$STAB" --warmstart-mix-fraction 0.50 \
      --output "$SHARE/R2_from_iter04.pt" $COMMON ;;
  r3)  # hard-only (no stabiliser) — regression-risk probe
    CUDA_VISIBLE_DEVICES=0 nice -n 19 $PY scripts/train_iter.py \
      --output-root "$M/data/hard_train" --warm-from "$I04" \
      --warmstart-mix-fraction 0 \
      --output "$SHARE/R3_hardonly_from_iter04.pt" $COMMON ;;
  posteval)  # Stage 5 held-out hard TEST: baseline vs repaired
    $PY scripts/rod_v2/highgap/highgap_eval.py \
      --manifest "$M/manifest_hard_test.jsonl" --npz-dir "$M/data/hard_test" \
      --checkpoints "iter04=$I04,iter06=$I06,R1=$SHARE/R1_from_iter04.pt,R2=$SHARE/R2_from_iter04.pt" \
      --out "$M/HIGH_GAP_RESULTS.md" --title "Stage 5 — held-out hard TEST (baseline vs repaired)" ;;
  regression)  # Stage 5 regression on stabiliser (decisive, student-correct) states
    $PY scripts/rod_v2/highgap/highgap_eval.py \
      --manifest "$M/manifest_stabilizer.jsonl" --npz-dir "$M/data/stabilizer" \
      --checkpoints "iter04=$I04,R1=$SHARE/R1_from_iter04.pt,R2=$SHARE/R2_from_iter04.pt" \
      --out "$M/HIGH_GAP_RESULTS.md" --title "Stage 5 — ordinary/stabiliser regression" ;;
  *) echo "usage: $0 {r1|r2|r3|posteval|regression}"; exit 1 ;;
esac
