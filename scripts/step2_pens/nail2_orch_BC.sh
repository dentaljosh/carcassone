#!/bin/bash
# Nail-2 arms B (convex) + C (additive) via the carc-orch fast path (GPU-batched
# priors; the additive/convex value is cheap in-worker). Sequential — one GPU.
# Same policy both sides (RoD2 iter_02), same decks (same SEED_START) -> B vs C is
# a clean paired leaf comparison. MEASUREMENT ONLY.
set -uo pipefail
cd /home/doctor/projects/carcassone
CK=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt
SC=/home/doctor/carc_step2_pens/warmstart/warmstart.pt
NB=/mnt/c/carc-shared/step2_pens/nail2

echo "=== NAIL2 arm B (convex 0.27) via orch @ $(date) ==="
CAND_CKPT=$CK REF_CKPT=$CK SCALAR=$SC OW=28 SIMS=100 N=100 BLEND=0.27 DROPOUT=0.0 \
  OUT=$NB/armB_convex027 bash scripts/step2_pens/eval_step2_orch.sh --leaf-mode convex \
  || echo "arm B orch rc=$?"

echo "=== NAIL2 arm C (additive 0.27 — THE TEST) via orch @ $(date) ==="
CAND_CKPT=$CK REF_CKPT=$CK SCALAR=$SC OW=28 SIMS=100 N=100 BLEND=0.27 DROPOUT=0.0 \
  OUT=$NB/armC_addbeta027 bash scripts/step2_pens/eval_step2_orch.sh --leaf-mode additive \
  || echo "arm C orch rc=$?"

echo "=== NAIL2 ORCH B+C DONE @ $(date) ==="
