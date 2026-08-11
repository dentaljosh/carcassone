#!/bin/bash
# Phase A perf-validation bench on rented cloud box.
#
# Goal: verify the 5 MCTS perf patches survive at production scale
# (sims=200, batch=8, games=80, workers=48 on 5090 + 48-core EPYC) and
# measure the new bottleneck breakdown. Validates the local 7.6× speedup
# claim against real production hardware.
#
# Two configs, back-to-back on the same box (eliminates host-variance):
#   A1: --workers 48 --sims 200 --games 80 --batch-size 8         (no orchestrator)
#   A2: same + --orchestrator --orch-shards 1                     (orchestrator on)
#
# Each is ~80 games × ~10s/game / 48 workers ≈ ~20-40s wallclock,
# plus ~10s overhead. Total bench ~5-10 min; with bootstrap ~15-20 min.
# Expected cost: ~$0.15 at $0.40/hr.
#
# Usage on the cloud box (after bootstrap_cloud.sh has run):
#   cd /workspace/carcassone
#   export PYTHONPATH=/workspace/carcassone/src
#   bash scripts/cloud_phase_a_bench.sh

set -eo pipefail

cd /workspace/carcassone
export PYTHONPATH=/workspace/carcassone/src

CKPT="${CKPT:-/workspace/carcassone/checkpoints/warmstart_canonical.pt}"
GAMES="${GAMES:-80}"
SIMS="${SIMS:-200}"
WORKERS="${WORKERS:-48}"
OUT_ROOT="${OUT_ROOT:-/tmp/phase_a_bench}"

mkdir -p "$OUT_ROOT"

echo "=== Phase A bench start: $(date) ==="
echo "ckpt=$CKPT games=$GAMES sims=$SIMS workers=$WORKERS"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo

run_config() {
    local label="$1"
    shift
    local extra_args="$@"
    local out_dir="$OUT_ROOT/${label}"
    local log="$OUT_ROOT/${label}.log"
    echo "=== $label START $(date +%H:%M:%S) ==="
    rm -rf "$out_dir"
    mkdir -p "$out_dir"

    # Pre-flight GPU snapshot
    nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader \
        > "$OUT_ROOT/${label}_gpu_pre.txt"

    # Sample GPU util every 2s in the background while the bench runs.
    nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader \
        -l 2 > "$OUT_ROOT/${label}_gpu_samples.csv" &
    local SMI_PID=$!

    {
        echo "=== $label ==="
        date
        echo "extra_args: $extra_args"
        time python -u scripts/run_selfplay_iter.py \
            --checkpoint "$CKPT" \
            --output-root "$out_dir" --iter 0 \
            --games "$GAMES" --sims "$SIMS" --workers "$WORKERS" \
            --batch-size 8 --virtual-loss 1.0 \
            $extra_args
        date
    } > "$log" 2>&1 || true

    kill $SMI_PID 2>/dev/null || true
    wait $SMI_PID 2>/dev/null || true

    nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader \
        > "$OUT_ROOT/${label}_gpu_post.txt"

    echo "=== $label DONE $(date +%H:%M:%S) — see $log ==="
}

run_config "A1_no_orchestrator"
run_config "A2_orchestrator" "--orchestrator --orch-shards 1"

echo
echo "=== Phase A bench complete: $(date) ==="
echo
echo "=== Summary ==="
for label in A1_no_orchestrator A2_orchestrator; do
    echo "--- $label ---"
    grep -E "Done iter=|^real|^user|^sys" "$OUT_ROOT/${label}.log" || true
    echo "  GPU samples: $(wc -l < "$OUT_ROOT/${label}_gpu_samples.csv") rows"
    if [ -s "$OUT_ROOT/${label}_gpu_samples.csv" ]; then
        # Compute mean GPU util from samples (col 2)
        awk -F', ' '
            NR>0 && $2 ~ /[0-9]+/ {
                gsub(" %","",$2); util_sum += $2; util_n++
                gsub(" MiB","",$1); mem_max = ($1+0 > mem_max ? $1+0 : mem_max)
            }
            END {
                if (util_n > 0)
                    printf "  mean GPU util: %.1f%%  peak VRAM: %d MiB  (n=%d samples)\n",
                           util_sum/util_n, mem_max, util_n
            }
        ' "$OUT_ROOT/${label}_gpu_samples.csv"
    fi
done
echo
echo "Artifacts: $OUT_ROOT/"
ls -la "$OUT_ROOT"
