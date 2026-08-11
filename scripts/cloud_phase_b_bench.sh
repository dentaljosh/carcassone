#!/bin/bash
# Phase B: bundled bench on one rented box. Designed to retire all open
# v7-knob questions in one ~$0.40 box session.
#
# Bundle:
#   0. Hardware snapshot (lscpu, nproc, df, free)
#   1. W-sweep no-orch: W ∈ {32, 40, 44}, games=64, sims=200, batch=8
#      Captures wallclock, success count, failure count (looks for OOM),
#      mean GPU util.
#   2. Orchestrator-v2 with batch_timeout_ms=16: W=48 (matches failed
#      Phase-A condition), --orch-shards 1, --orch-batch-timeout-ms 16.
#      Tests whether bigger batch coalescing rescues the dispatcher.
#   3. Full-style iter at the W-sweep winner: selfplay + train + h2h +
#      anchor, captures per-stage wallclock. Real v7 per-iter cost.
#   4. Train profile: cProfile on one train epoch. Identifies the next
#      bottleneck (likely DataLoader num_workers / streaming).
#
# Usage on the cloud box:
#   cd /workspace/carcassone
#   export PYTHONPATH=/workspace/carcassone/src
#   bash scripts/cloud_phase_b_bench.sh

set -eo pipefail

cd /workspace/carcassone
export PYTHONPATH=/workspace/carcassone/src

CKPT="${CKPT:-/workspace/carcassone/checkpoints/warmstart_canonical.pt}"
SIMS="${SIMS:-200}"
GAMES="${GAMES:-64}"           # smaller than 80 so all W values divide cleanly
OUT_ROOT="${OUT_ROOT:-/tmp/phase_b_bench}"
mkdir -p "$OUT_ROOT"

# Mute torch deprecation noise that floods the log.
export PYTHONWARNINGS="ignore::DeprecationWarning"

echo "=== Phase B bench start: $(date) ==="

# ---------------------------------------------------------------------
# 0. Hardware snapshot
# ---------------------------------------------------------------------
{
    echo "=== nproc ==="
    nproc
    echo "=== lscpu summary ==="
    lscpu | grep -E "Model name|CPU\\(s\\)|Thread\\(s\\) per core|Core\\(s\\) per socket|Socket\\(s\\)|MHz" | head -20
    echo "=== free ==="
    free -h
    echo "=== df ==="
    df -h /workspace 2>/dev/null
    echo "=== nvidia-smi ==="
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    echo "=== torch ==="
    python -c "import torch; print(f'{torch.__version__}  cuda={torch.version.cuda}  cap=sm_{torch.cuda.get_device_capability(0)[0]}{torch.cuda.get_device_capability(0)[1]}')"
} > "$OUT_ROOT/00_hw_snapshot.txt" 2>&1
echo "  hw snapshot saved -> $OUT_ROOT/00_hw_snapshot.txt"

# ---------------------------------------------------------------------
# Helper: run one selfplay config, capture wallclock + result counts +
# GPU util samples.
# ---------------------------------------------------------------------
run_selfplay() {
    local label="$1"
    local workers="$2"
    shift 2
    local extra_args="$@"
    local out_dir="$OUT_ROOT/${label}"
    local log="$OUT_ROOT/${label}.log"
    echo "=== $label START $(date +%H:%M:%S) (W=$workers) ==="
    rm -rf "$out_dir"
    mkdir -p "$out_dir"

    nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader -l 2 \
        > "$OUT_ROOT/${label}_gpu.csv" &
    local SMI_PID=$!

    {
        echo "=== $label ==="
        date
        echo "extra_args: $extra_args"
        time python -u scripts/run_selfplay_iter.py \
            --checkpoint "$CKPT" \
            --output-root "$out_dir" --iter 0 \
            --games "$GAMES" --sims "$SIMS" --workers "$workers" \
            --batch-size 8 --virtual-loss 1.0 \
            $extra_args
        date
    } > "$log" 2>&1 || true

    kill $SMI_PID 2>/dev/null || true
    wait $SMI_PID 2>/dev/null || true

    # Compact result row
    local fresh=$(grep -oP "Done iter.*?\\K\\d+(?= fresh)" "$log" | head -1)
    local failed=$(grep -oP "Done iter.*?\\K\\d+(?= failed)" "$log" | head -1)
    local secs=$(grep -oP "Done iter.*?\\K[\\d.]+(?=s wallclock)" "$log" | head -1)
    fresh=${fresh:-0}; failed=${failed:-?}; secs=${secs:-?}
    local mem_peak=$(awk -F', ' 'NR>0 && $2 ~ /[0-9]+/ {gsub(" MiB","",$1); if ($1+0>mx) mx=$1+0} END{print mx+0}' "$OUT_ROOT/${label}_gpu.csv")
    local util_mean=$(awk -F', ' 'NR>0 && $2 ~ /[0-9]+/ {gsub(" %","",$2); s+=$2; n++} END{if(n>0) printf "%.1f", s/n}' "$OUT_ROOT/${label}_gpu.csv")
    echo "  RESULT $label: ${secs}s, ${fresh}/${GAMES} fresh, ${failed}/${GAMES} failed, peak_VRAM=${mem_peak}MiB, mean_util=${util_mean}%" \
        | tee -a "$OUT_ROOT/_results.txt"
}

# ---------------------------------------------------------------------
# 1. W-sweep, no orchestrator
# ---------------------------------------------------------------------
echo
echo "=== Phase 1: W-sweep (no orchestrator) ==="
for W in 32 40 44; do
    run_selfplay "W${W}_no_orch" $W
done

# ---------------------------------------------------------------------
# 2. Orchestrator v2 at W=48 with longer batch_timeout (16ms vs 2ms default)
# ---------------------------------------------------------------------
echo
echo "=== Phase 2: orchestrator W=48 batch_timeout_ms=16 ==="
run_selfplay "W48_orch_t16" 48 --orchestrator --orch-shards 1 --orch-batch-timeout-ms 16

# ---------------------------------------------------------------------
# 3. Pick the W-sweep winner (lowest wallclock with all games succeeding),
#    run a full-style iter (selfplay + train + h2h + anchor) for real
#    per-iter timing data.
# ---------------------------------------------------------------------
echo
echo "=== Phase 3: pick winner + full iter ==="
WINNER_W=$(python3 - <<PY
import re, glob
best = None
for label in ['W32_no_orch', 'W40_no_orch', 'W44_no_orch']:
    log = f"$OUT_ROOT/{label}.log"
    try:
        txt = open(log).read()
    except FileNotFoundError:
        continue
    m = re.search(r"Done iter=0:\s*(\d+) fresh \+ \d+ cached \+ (\d+) failed.*?([\d.]+)s wallclock", txt)
    if not m: continue
    fresh, failed, secs = int(m.group(1)), int(m.group(2)), float(m.group(3))
    if failed > 0: continue
    if best is None or secs < best[1]:
        best = (label, secs)
print(best[0] if best else 'W32_no_orch')
PY
)
WINNER_W_VAL=$(echo "$WINNER_W" | grep -oP "\d+")
echo "  winner_W=$WINNER_W_VAL (label=$WINNER_W)"

# Full iter via run_phase4_smoke (single iter only)
FULL_ITER_LOG="$OUT_ROOT/full_iter.log"
echo "=== full iter at W=$WINNER_W_VAL ==="
{
    echo "=== full_iter START ==="
    date
    time python -u scripts/run_phase4_smoke.py \
        --iters 1 --games 64 --sims 200 \
        --eval-sims 100 --eval-games 32 \
        --workers $WINNER_W_VAL --eval-workers $WINNER_W_VAL \
        --batch-size 8 --virtual-loss 1.0 \
        --window 30 \
        --warmstart-mix-schedule "1.0" \
        --best-so-far-warmstart \
        --anchor-gate \
        --anchor-checkpoint "$CKPT" \
        --anchor-games 16 --anchor-sims 50 \
        --anchor-min-winrate 0.4 --anchor-max-fails 3 \
        --checkpoint-root "$OUT_ROOT/full_iter_ckpt" \
        --output-root "$OUT_ROOT/full_iter_data"
    date
    echo "=== full_iter DONE ==="
} > "$FULL_ITER_LOG" 2>&1 || true
echo "  full iter log -> $FULL_ITER_LOG"

# ---------------------------------------------------------------------
# 4. Train profile: cProfile a train on the W-sweep winner's data
# ---------------------------------------------------------------------
echo
echo "=== Phase 4: train cProfile ==="
TRAIN_PROF="$OUT_ROOT/train.prof"
TRAIN_LOG="$OUT_ROOT/train_profile.log"
{
    echo "=== train cProfile START ==="
    date
    python -m cProfile -o "$TRAIN_PROF" scripts/train_iter.py \
        --data-root "$OUT_ROOT/${WINNER_W}/iter_00" \
        --warm-from "$CKPT" \
        --output "$OUT_ROOT/train_profile_out.pt" \
        --epochs 1 --batch-size 256 --workers 4
    date
    echo "=== train cProfile DONE ==="
} > "$TRAIN_LOG" 2>&1 || true

# Dump top by tottime
python3 - <<PY > "$OUT_ROOT/train_profile_top.txt" 2>&1 || true
import pstats
try:
    s = pstats.Stats("$TRAIN_PROF").strip_dirs()
    print("--- TOP 30 by tottime ---")
    s.sort_stats("tottime").print_stats(30)
    print("\n--- TOP 30 by cumtime ---")
    s.sort_stats("cumulative").print_stats(30)
except Exception as e:
    print(f"profile parse failed: {e}")
PY

echo
echo "=== Phase B bench complete: $(date) ==="
echo
echo "=== Summary ==="
cat "$OUT_ROOT/_results.txt" 2>/dev/null
echo
echo "Per-stage timing (full iter):"
grep -E "selfplay iter|Done iter|Iter \d+ training|head_to_head_records|anchor wr|^real" "$FULL_ITER_LOG" 2>/dev/null | head -30
echo
echo "Train profile top:"
head -20 "$OUT_ROOT/train_profile_top.txt" 2>/dev/null
echo
echo "Artifacts in $OUT_ROOT"
ls -la "$OUT_ROOT" | head -40
