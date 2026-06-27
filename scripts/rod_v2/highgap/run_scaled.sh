#!/usr/bin/env bash
# Post-labeling driver: merge the two sharded label legs, build scaled tier splits,
# retrain R1/R2/R3 from iter04, run held-out + regression eval. One command after
# both labeling legs finish. MEAS-ONLY; no promotion.
set -euo pipefail
cd /home/doctor/projects/carcassone
M=measurement/high_gap_distillation
QA=$M/scaled/qprobe_A
QB=/mnt/c/carc-shared/high_gap_distillation/qprobe_B
TEMP=${TEMP:-0.03}

echo "=== cross-leg density check (contamination guard) ==="
echo "leg A:"; grep 'Q-gap >=' "$M/scaled/probe_A.log" | tail -4
echo "leg B:"; grep 'Q-gap >=' "$M/scaled/probe_B.log" 2>/dev/null | tail -4 || \
  grep 'Q-gap >=' /mnt/c/carc-shared/high_gap_distillation/probe_B.log | tail -4

echo "=== clear pilot splits (avoid stale npz in _load_npz glob) ==="
rm -rf "$M"/data/hard_train "$M"/data/hard_val "$M"/data/hard_test "$M"/data/stabilizer

echo "=== merged build_splits (temp=$TEMP) ==="
.venv/bin/python scripts/rod_v2/highgap/build_splits.py \
  --probe "$QA/probe.jsonl,$QB/probe.jsonl" \
  --npz-dir "$QA/data,$QB/data" --temp "$TEMP"

echo "=== retrain (EPOCHS=${EPOCHS:-20}) ==="
EPOCHS=${EPOCHS:-20} bash scripts/rod_v2/highgap/run_highgap.sh r1
EPOCHS=${EPOCHS:-20} bash scripts/rod_v2/highgap/run_highgap.sh r2

echo "=== reset RESULTS.md to a fresh header (scaled run is conclusive) ==="
HT=$(wc -l < "$M/manifest_hard_test.jsonl"); HR=$(wc -l < "$M/manifest_hard_train.jsonl")
cat > "$M/HIGH_GAP_RESULTS.md" <<EOF
# High-Contrast Decision-Signal Distillation — RESULTS (scaled)

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEAS/DIAGNOSTIC ONLY.** No promotion · v2.9 frozen.
Plan: [HIGH_GAP_PLAN.md](HIGH_GAP_PLAN.md) · Gate: [HIGH_GAP_SIGNAL_DENSITY.md](HIGH_GAP_SIGNAL_DENSITY.md) ·
Decision: [HIGH_GAP_DECISION.md](HIGH_GAP_DECISION.md).

Scaled pool: 20160 roots (1120 fresh games, k=2..62) labeled h6400_v2.9 across local(A)+laptop(B),
soft Q-softmax targets (temp=$TEMP). Hard train=$HR, held-out hard TEST=$HT (game-disjoint).
Repair: policy-only fine-tune from iter04 (+stabiliser mix). Pilot (1616-pool) precedent: regret
-16% mean / -32% median, top1 0->0.135 strong-gap on n=96.
EOF
echo "=== Stage 5 held-out + regression ==="
bash scripts/rod_v2/highgap/run_highgap.sh posteval
bash scripts/rod_v2/highgap/run_highgap.sh regression
echo "=== DONE — read $M/HIGH_GAP_RESULTS.md ==="
