#!/usr/bin/env bash
# =============================================================================
# eff_linus ROUND 3 — the Pop!_OS (bare-metal Linux) arm.
# =============================================================================
# Mirrors scripts/measurement_infra/wsl_vs_native_ab.sh's *WSL-arm* cell
# invocations byte-for-byte (same COMMON_ENV, same M5 bundle, same staged pysrc
# @17ba2ce, same --limit/--calls/--warmup). The comparison arm is NOT run here:
# it is the committed round-2 WSL arm on this same silicon
# (measurement/eff_linus/run_laptop_20260729/), because dual-boot makes
# same-session alternation impossible.
#
# ARMS (alternated A/B/B/A rep-by-rep so drift cannot masquerade as an arm):
#   pin    -> taskset -c 0-15  (the 8 P-cores, verified via lscpu -e)
#   free   -> unpinned control (does the Linux scheduler demote us to E-cores
#             the way Windows' Thread Director did? round-2 §4)
# Both niced -n 19, matching the round-2 driver.
# =============================================================================
set -uo pipefail

BENCH=/home/pop/carc-pop-bench
PY=$BENCH/.venv/bin/python
M5=$BENCH/m5_bench_20260728
STAGE=$BENCH/stage
CKPT=$M5/bundle/net/distill_iter_03.pt
OUT="${1:-$BENCH/out/run_$(date +%Y%m%d_%H%M%S)}"
CELLS="${2:-champ_k1x32,champ_k4x172}"
ARMS="${3:-pin,free}"
REPS="${4:-3}"
NICE="${5-nice -n 19}"
PMASK="0-15"

mkdir -p "$OUT/cells"
NDJSON="$OUT/runs.ndjson"
: > "$NDJSON"

COMMON_ENV=(
  "PYTHONUTF8=1"
  "PYTHONHASHSEED=0"
  "PYTHONDONTWRITEBYTECODE=1"
  "CARCASSONNE_USE_FLAT_LEAF=1"
  "CARCASSONNE_USE_CY_LEAF=0"
  "CARCASSONNE_USE_CY_REPR=0"
)

snap() {
  local la gov epp gpu t
  la="$(cat /proc/loadavg)"
  gov="$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)"
  epp="$(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null)"
  gpu="$(nvidia-smi --query-gpu=power.draw,utilization.gpu,memory.used,clocks.sm --format=csv,noheader,nounits 2>/dev/null | head -1)"
  t="$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)"
  printf '{"loadavg":"%s","governor":"%s","epp":"%s","nvidia_smi":"%s","tz0_mC":"%s"}' \
     "$la" "$gov" "$epp" "$gpu" "$t"
}

echo "== eff_linus round 3 :: Pop!_OS arm =="
echo "   out   : $OUT"
echo "   cells : $CELLS  arms: $ARMS  reps: $REPS  nice: '$NICE'"
echo "   gov   : $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)  epp: $(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference)"
echo "   load  : $(cat /proc/loadavg)"

# warm-up: first-touch of the venv / page cache, discarded (mirrors round-2 §4)
env "${COMMON_ENV[@]}" "$PY" -c "import numpy, yaml; print('pop warm', numpy.__version__)" || true

run_cell() {   # run_cell <cell> <arm> <rep>
  local cell="$1" arm="$2" rep="$3"
  local tag="${cell}__pop_${arm}__rep${rep}"
  local cj="$OUT/cells/$tag.json"
  local log="$OUT/cells/$tag.log"
  local pre post rc t0 t1 aff
  case "$arm" in
    pin)  aff=(taskset -c "$PMASK") ;;
    free) aff=() ;;
    *) echo "unknown arm $arm" >&2; return 2 ;;
  esac
  pre="$(snap)"
  t0="$(date +%s.%N)"
  case "$cell" in
    champ_*)
      local budget="${cell#champ_}"
      env "${COMMON_ENV[@]}" ${NICE} "${aff[@]}" "$PY" -u "$M5/bench_champion.py" \
          --bundle "$M5/bundle" --budgets "$budget" --limit 12 --warmup 1 \
          --tag "eff_linus:$tag" --out "$cj" > "$log" 2>&1
      rc=$? ;;
    net_*)
      local row="${cell#net_}"
      env "${COMMON_ENV[@]}" "PYTHONPATH=$STAGE/pysrc" ${NICE} "${aff[@]}" \
          "$PY" -u "$STAGE/net_transport_bench.py" \
          --ckpt "$CKPT" --rows "$row" --calls 2000 --warmup 200 --out "$cj" \
          > "$log" 2>&1
      rc=$? ;;
    *) echo "unknown cell $cell" >&2; return 2 ;;
  esac
  t1="$(date +%s.%N)"
  post="$(snap)"
  printf '{"cell":"%s","arm":"pop_%s","rep":%s,"rc":%s,"wallclock_s":%s,"affinity":"%s","nice":"%s","child_json":"%s","state_before":%s,"state_after":%s}\n' \
     "$cell" "$arm" "$rep" "$rc" \
     "$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.3f", b-a}')" \
     "$( [ "$arm" = pin ] && echo "$PMASK" || echo "unpinned")" "$NICE" "$cj" \
     "$pre" "$post" >> "$NDJSON"
  printf '   %-38s rc=%s  %ss\n' "$tag" "$rc" \
     "$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')"
}

IFS=',' read -r -a CELL_ARR <<< "$CELLS"
IFS=',' read -r -a ARM_ARR <<< "$ARMS"
for cell in "${CELL_ARR[@]}"; do
  for rep in $(seq 1 "$REPS"); do
    if [ "${#ARM_ARR[@]}" -eq 2 ] && [ $((rep % 2)) -eq 0 ]; then
      order=("${ARM_ARR[1]}" "${ARM_ARR[0]}")
    else
      order=("${ARM_ARR[@]}")
    fi
    for arm in "${order[@]}"; do run_cell "$cell" "$arm" "$rep"; done
  done
done

echo "DONE $(date -u +%FT%TZ)"
touch "$OUT/.done"
