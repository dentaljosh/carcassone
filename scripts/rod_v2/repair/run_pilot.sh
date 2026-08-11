#!/usr/bin/env bash
# Hard-policy-repair PILOT driver (reference / reproducibility). Run stages
# INDIVIDUALLY — inspect the Stage-2 baseline (must reproduce the autopsy's
# lean≈0 / P_neither≈0.775) BEFORE fine-tuning. Not a one-shot pipeline.
set -uo pipefail
REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
M=$REPO/measurement/hard_policy_repair
SHARE=/mnt/c/carc-shared/hard_policy_repair
RES=$M/HARD_POLICY_REPAIR_RESULTS.md
ROD1=/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt
I04=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_04.pt
I06=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_06.pt
cd "$REPO" || exit 1

stage="${1:-help}"
case "$stage" in

baseline)   # Stage 2 — P0 baseline on held-out hard TEST set (also harness sanity check)
  "$PY" scripts/rod_v2/repair/hardset_eval.py \
    --manifest "$M/manifest_test.jsonl" --npz-dir "$M/data/test" \
    --checkpoints "rod1=$ROD1,iter04=$I04,iter06=$I06" \
    --title "Stage 2 — P0 baseline (held-out hard test)" --out "$RES"
  ;;

p1)         # Stage 3 — P1 policy-only fine-tune from iter04 (low LR)
  CUDA_VISIBLE_DEVICES="${CUDA:-0}" nice -n 19 "$PY" -u scripts/train_iter.py \
    --output-root "$M/data/train" --iter 0 --window 1 \
    --warm-from "$I04" --output "$SHARE/p1_from_iter04.pt" \
    --epochs "${EPOCHS:-15}" --lr "${LR:-2e-4}" --batch-size "${BS:-64}" \
    --aux-weight 0 --value-loss-weight 0 \
    --warmstart-mix-fraction 0 --val-fraction 0 --entropy-floor-frac 0 \
    --num-workers 2 --seed 0 \
    --prov-run-tag hard_policy_repair_p1 --prov-value-target residual \
    --prov-selfplay-leaf v2_9_bmild_cap8
  ;;

p2)         # Stage 3 — P2 = P1 + ordinary-state mix (forgetting guard)
  CUDA_VISIBLE_DEVICES="${CUDA:-0}" nice -n 19 "$PY" -u scripts/train_iter.py \
    --output-root "$M/data/train" --iter 0 --window 1 \
    --warmstart-root "$M/data/ordinary/iter_00" --warmstart-mix-fraction "${MIX:-0.4}" \
    --warm-from "$I04" --output "$SHARE/p2_from_iter04_mix.pt" \
    --epochs "${EPOCHS:-15}" --lr "${LR:-2e-4}" --batch-size "${BS:-64}" \
    --aux-weight 0 --value-loss-weight 0 \
    --val-fraction 0 --entropy-floor-frac 0 --num-workers 2 --seed 0 \
    --prov-run-tag hard_policy_repair_p2 --prov-value-target residual \
    --prov-selfplay-leaf v2_9_bmild_cap8
  ;;

p3)         # Stage 3 — P3 = P1 but from RoD1_v29
  CUDA_VISIBLE_DEVICES="${CUDA:-0}" nice -n 19 "$PY" -u scripts/train_iter.py \
    --output-root "$M/data/train" --iter 0 --window 1 \
    --warm-from "$ROD1" --output "$SHARE/p3_from_rod1.pt" \
    --epochs "${EPOCHS:-15}" --lr "${LR:-2e-4}" --batch-size "${BS:-64}" \
    --aux-weight 0 --value-loss-weight 0 \
    --warmstart-mix-fraction 0 --val-fraction 0 --entropy-floor-frac 0 \
    --num-workers 2 --seed 0 \
    --prov-run-tag hard_policy_repair_p3 --prov-value-target residual \
    --prov-selfplay-leaf v2_9_bmild_cap8
  ;;

posteval)   # Stage 4 — repaired nets on held-out hard TEST set
  "$PY" scripts/rod_v2/repair/hardset_eval.py \
    --manifest "$M/manifest_test.jsonl" --npz-dir "$M/data/test" \
    --checkpoints "iter04=$I04,p1=$SHARE/p1_from_iter04.pt" \
    --title "Stage 4 — post-repair (held-out hard test)" --out "$RES"
  ;;

regression) # Stage 5 — ordinary (agreement) states: did normal play survive?
  "$PY" scripts/rod_v2/repair/hardset_eval.py \
    --manifest "$M/manifest_ordinary.jsonl" --npz-dir "$M/data/ordinary" \
    --checkpoints "iter04=$I04,p1=$SHARE/p1_from_iter04.pt" \
    --title "Stage 5 — ordinary-state regression" --out "$RES"
  ;;

*) echo "usage: $0 {baseline|p1|p2|p3|posteval|regression}"; exit 1 ;;
esac
