#!/usr/bin/env bash
# STAGE-3 VALUE-UNLOCK offline training run (2026-07-30).
#
# Warm from CL-067 iter_03 (the distill_strong champion-distilled net) and refine
# the VALUE head on the SAME strong corpus (iters 00-03, net-free champion at
# k8x1376 = 11008, manifest-verified) with the value term made load-bearing.
#
# Deltas vs the iter_03 recipe (its own provenance train_command, read off
# /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.metrics.json):
#   --value-loss-weight 1.5 -> 5.0   (G-T2 round-2 audit: policy CE dominates the
#                                     value MSE 5-10x unweighted; sweep 1-5 at Stage B)
#   --lr 1e-3 (flat)        -> 3e-4 + cosine   (G-T1: low-LR value refine phase)
#   --epochs 3              -> 4
# Everything else identical (batch 256, aux 0 = the corpus's ownership is dummy,
# val-fraction 0.05, seed 0). train_iter.py has NO policy-freeze flag, so this is a
# JOINT policy+value train with the value term up-weighted -- the simplest thing the
# existing trainer supports (documented in the readout).
#
# F13 target-shape decision (THIS RUN ONLY, no shared default changed): the corpus's
# `values` are mover-POV outcomes tanh((p0-p1)/15), measured range
# [-0.999988, +0.999988] -- ALREADY inside the tanh head's [-1,+1]. The F13 defect is
# specific to the RESIDUAL target (Q - leaf, structurally +/-2); it does not apply
# here, so no rescale/clamp is applied.
#
# MEASUREMENT ONLY. No PRODUCTION.yaml, no champion change.
set -euo pipefail
REPO=/home/doctor/projects/carcassone
OUT=/mnt/c/carc-shared/value_unlock_20260730
mkdir -p "$OUT/ckpt"
cd "$REPO"
nice -n 19 "$REPO/.venv/bin/python" -u scripts/train_iter.py \
  --output-root /mnt/c/carc-shared/distill_strong_20260723 \
  --iter 3 --window 4 \
  --warm-from /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
  --output "$OUT/ckpt/value_unlock_v1.pt" \
  --epochs 4 --batch-size 256 \
  --lr 3e-4 --lr-schedule cosine \
  --value-loss-weight 5.0 --aux-weight 0 \
  --val-fraction 0.05 --seed 0 \
  --stage-local /tmp/vu_stage \
  --prov-value-target outcome \
  --prov-selfplay-leaf v2_9_bmild_cap8_curve125 \
  --prov-seed-range 50000000000-50000300599 \
  --prov-run-tag value_unlock_20260730_v1
echo "=== train_value_unlock DONE rc=$? @ $(date) ==="
