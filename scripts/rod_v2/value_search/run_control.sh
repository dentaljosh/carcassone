#!/usr/bin/env bash
# Value/Search Autopsy — Stage 2b CONTROL: the full-pool (un-confounded) test.
# The miss-set legs show flat-prior / classical win — but ON THE MISSES (where the net
# prior was wrong by construction). This re-runs the key legs on the FULL gap>=0.02 pool
# (4277 roots) so the comparison is vs the SAME states iter04's neural NMCTS@200 scored
# 0.799 on. Waits for the main Stage-2 driver to finish, then runs (local, W=16).
set -euo pipefail
REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python3"
D="$REPO/measurement/value_search_autopsy/data"
PILOT="$REPO/measurement/high_gap_distillation/qprobe/probe.jsonl"
SCALEDA="$REPO/measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl"
CKPT04=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_04.pt
H="$REPO/scripts/rod_v2/value_search/miss_harness.py"
C="$REPO/scripts/rod_v2/value_search/classical_leg.py"

echo "### control: waiting for main Stage 2 to finish"
until grep -qE "Stage 2 \(sims<=800\) DONE|Traceback|Killed" "$D/stage2.log" 2>/dev/null; do sleep 20; done
echo "### control: main done, running full-pool legs ($(date +%H:%M:%S))"

# classical h200 on the full gap>=0.02 pool
nice -n 19 "$PY" "$C" --probe "$PILOT,$SCALEDA" --gap-min 0.02 --sims 200 \
    --workers 16 --out "$D/CTRL_h200_fullpool.jsonl" 2>&1 | tail -2
# flat-prior neural on the full pool
nice -n 19 "$PY" "$H" --probe "$PILOT,$SCALEDA" --checkpoints "iter04=$CKPT04" \
    --gap-min 0.02 --sims 200 --prior flat --workers 16 --tag CTRL_flat \
    --out "$D/CTRL_flat_fullpool.jsonl" 2>&1 | tail -2
# rs0 (no neural value) neural on the full pool — does the value head matter overall?
nice -n 19 "$PY" "$H" --probe "$PILOT,$SCALEDA" --checkpoints "iter04=$CKPT04" \
    --gap-min 0.02 --sims 200 --residual-scale 0.0 --workers 16 --tag CTRL_rs0 \
    --out "$D/CTRL_rs0_fullpool.jsonl" 2>&1 | tail -2
echo "### CONTROL DONE ($(date +%H:%M:%S))"
