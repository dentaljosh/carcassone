#!/usr/bin/env bash
# Run the CL-067 LiteRT delegate ladder on an attached Android device.
#
#   scripts/pixel_npu/phone_bench/run_ladder.sh [OUT_DIR] [SHARE_DIR]
#
# Pushes the benchmark binary + every .tflite artifact, then runs each
# (model x delegate x thread-count) cell, teeing the RAW benchmark_model output to its own log.
# `parse_ladder.py` turns those logs into JSON + a markdown table. Nothing is transcribed by
# hand: every number that reaches a document is parsed from a file in OUT_DIR.
#
# Assumes adb is already connected (see RUNBOOK_PIXEL.md §2). Phone-polite: the whole ladder is
# a few minutes of short runs, not an endurance loop.
set -uo pipefail

OUT_DIR="${1:-/mnt/c/carc-shared/pixel_npu_20260729/phone_results}"
SHARE="${2:-/mnt/c/carc-shared/pixel_npu_20260729}"
ADB="${ADB:-$HOME/Android/Sdk/platform-tools/adb}"
D=/data/local/tmp/carcnpu

RUNS=200
WARMUP=50

mkdir -p "$OUT_DIR"

if ! "$ADB" devices | grep -q "device$"; then
  echo "run_ladder: no adb device in state 'device'. See RUNBOOK_PIXEL.md section 2." >&2
  exit 1
fi

# --- device + battery state: a thermal/battery caveat is part of the measurement ------------
{
  echo "=== adb devices ==="; "$ADB" devices -l
  echo "=== device ==="
  for P in ro.product.model ro.soc.model ro.board.platform ro.build.version.release \
           ro.build.version.sdk ro.build.fingerprint; do
    echo "$P=$("$ADB" shell getprop $P | tr -d '\r')"
  done
  echo "=== battery BEFORE ==="; "$ADB" shell dumpsys battery
  echo "=== thermal ==="; "$ADB" shell dumpsys thermalservice 2>/dev/null | head -40
} > "$OUT_DIR/device_state_before.txt" 2>&1
echo "run_ladder: device state -> $OUT_DIR/device_state_before.txt"

# --- push ------------------------------------------------------------------------------------
"$ADB" shell mkdir -p $D
"$ADB" push "$SHARE/benchmark_model_android_aarch64" $D/benchmark_model >/dev/null
"$ADB" shell chmod +x $D/benchmark_model
for F in "$SHARE"/cl067_iter03_*.tflite; do
  B=$(basename "$F")
  # Skip the re-push if the device already has a byte-identical copy; pushing 30 MB over a
  # tailnet is the slowest thing in this script.
  REMOTE_SZ=$("$ADB" shell "stat -c %s $D/$B 2>/dev/null" | tr -d '\r')
  LOCAL_SZ=$(stat -c %s "$F")
  if [ "$REMOTE_SZ" = "$LOCAL_SZ" ]; then echo "  = $B (already present)"; continue; fi
  echo "  + $B"
  "$ADB" push "$F" $D/ >/dev/null
done

# --- the ladder --------------------------------------------------------------------------------
# label|model|extra flags
# Ordered cheap->interesting, and every cell records which delegate ACTUALLY executed the graph
# (benchmark_model prints either "will be completely executed by the delegate" or "will not be
# executed by the delegate" + the fallback it used). parse_ladder.py keys on those lines, so a
# silent CPU fallback can never be reported as a delegate result.
LADDER=$(cat <<'EOF'
cpu1_fp32|fp32|--num_threads=1 --use_xnnpack=false
xnn1_fp32|fp32|--num_threads=1 --use_xnnpack=true
xnn4_fp32|fp32|--num_threads=4 --use_xnnpack=true
xnn1_fp32_forcefp16|fp32|--num_threads=1 --use_xnnpack=true --xnnpack_force_fp16=true
gpu_fp16|fp16|--use_gpu=true --gpu_precision_loss_allowed=true
gpu_fp32_exact|fp32|--use_gpu=true --gpu_precision_loss_allowed=false
gpu_fp32_lossy|fp32|--use_gpu=true --gpu_precision_loss_allowed=true
nnapi_default_fp32|fp32|--use_nnapi=true
nnapi_edgetpu_fp32|fp32|--use_nnapi=true --nnapi_accelerator_name=google-edgetpu
nnapi_reference_fp32|fp32|--use_nnapi=true --nnapi_accelerator_name=nnapi-reference
xnn1_int8dyn|int8dyn_EXPERIMENTAL|--num_threads=1 --use_xnnpack=true
xnn4_int8dyn|int8dyn_EXPERIMENTAL|--num_threads=4 --use_xnnpack=true
gpu_int8dyn|int8dyn_EXPERIMENTAL|--use_gpu=true --gpu_precision_loss_allowed=true --gpu_experimental_enable_quant=true
nnapi_edgetpu_int8dyn|int8dyn_EXPERIMENTAL|--use_nnapi=true --nnapi_accelerator_name=google-edgetpu
xnn1_int8full|int8full_EXPERIMENTAL|--num_threads=1 --use_xnnpack=true
gpu_int8full|int8full_EXPERIMENTAL|--use_gpu=true --gpu_precision_loss_allowed=true --gpu_experimental_enable_quant=true
nnapi_edgetpu_int8full|int8full_EXPERIMENTAL|--use_nnapi=true --nnapi_accelerator_name=google-edgetpu
EOF
)

while IFS='|' read -r LABEL MODEL FLAGS; do
  [ -z "$LABEL" ] && continue
  G="$D/cl067_iter03_${MODEL}.tflite"
  LOG="$OUT_DIR/${LABEL}.log"
  echo "-- $LABEL"
  {
    echo "### label=$LABEL"
    echo "### model=$MODEL"
    echo "### flags=$FLAGS"
    echo "### cmd=$D/benchmark_model --graph=$G $FLAGS --num_runs=$RUNS --warmup_runs=$WARMUP"
  } > "$LOG"
  # A cell that hard-fails (e.g. NNAPI rejecting the graph) is a RESULT, not a script error --
  # keep going and let the parser record the failure.
  #
  # `< /dev/null` is LOAD-BEARING: `adb shell` reads stdin, and without it the first cell
  # swallows the rest of the here-string feeding this while-loop, so the ladder silently runs
  # exactly one row and reports success. (Cost one full ladder pass on 2026-07-29.)
  "$ADB" shell "$D/benchmark_model --graph=$G $FLAGS \
      --num_runs=$RUNS --warmup_runs=$WARMUP --report_peak_memory_footprint=true" \
      >> "$LOG" 2>&1 < /dev/null
  grep -E "Inference \(avg\)|Benchmarking failed|not be executed" "$LOG" | tail -2 | sed 's/^/     /'
done <<< "$LADDER"

"$ADB" shell dumpsys battery > "$OUT_DIR/device_state_after.txt" 2>&1
echo "run_ladder: done. Logs in $OUT_DIR; now run parse_ladder.py."
