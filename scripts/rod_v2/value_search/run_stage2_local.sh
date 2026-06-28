#!/usr/bin/env bash
# Value/Search Autopsy — Stage 2 full local driver. Runs AFTER Stage 1 (I0_local.jsonl).
# Builds the miss set + miss-probe, then runs the intervention matrix on local (W=16),
# sequential, nice-19. Each leg logs to data/. ~90 min for the sims<=800 legs; s1600 is
# launched separately only if the 400/800 trend warrants it.
set -euo pipefail
REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python3"
D="$REPO/measurement/value_search_autopsy/data"
AGG="$REPO/scripts/rod_v2/value_search/agg_miss.py"
PILOT="$REPO/measurement/high_gap_distillation/qprobe/probe.jsonl"
SCALEDA="$REPO/measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl"
CKPT04=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_04.pt

echo "### build miss set + reproduction fragment"
"$PY" "$AGG" missset --i0 "$D/I0_local.jsonl" --baseline-ckpt iter04 \
    --out-misses "$D/misses_iter04.jsonl" > "$D/MISS_SET_frag.md"
echo "### build miss-probe (action_q rows for miss seeds)"
"$PY" "$AGG" missprobe --misses "$D/misses_iter04.jsonl" --probe "$PILOT,$SCALEDA" \
    --out "$D/miss_probe.jsonl"

export PROBE="$D/miss_probe.jsonl" CKPT04="$CKPT04" OUTDIR="$D" WORKERS=16
export MISSES="$D/misses_iter04.jsonl"
RL="$REPO/scripts/rod_v2/value_search/run_leg.sh"

for leg in forced flat teacher rs0 rs05 s400 s800; do
    echo "### LEG $leg  ($(date +%H:%M:%S))"
    bash "$RL" "$leg" 2>&1 | tail -2
done
echo "### Stage 2 (sims<=800) DONE  ($(date +%H:%M:%S))"
