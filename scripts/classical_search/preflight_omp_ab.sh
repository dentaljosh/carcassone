#!/usr/bin/env bash
# ============================================================================
# carc-orch OMP A/B — isolates ONE variable (2026-07-26).
#
# FINDING THAT MOTIVATES IT (measured, this box, W=28 fwd=2 max_batch=16):
#   python workers 12.1% CPU each (364% total)  |  carc-orch 2578%  |  GPU 39W
#   => the box is SATURATED BY THE SERVER, not idle. The workers doing the actual
#   game-playing got 3.6 of 16 physical cores. STATUS's "87% idle" was wrong;
#   its "14.6% worker CPU" symptom was right.
#
# HYPOTHESIS: fair_net_vs_net_orch.sh launches carc-orch with NO thread limit
# (line ~114) and the Rust side never calls set_num_threads, so libtorch sizes
# its intra-op pool to core count and OpenMP spin-waits. The wrapper sets
# OMP_NUM_THREADS=1 for the PYTHON CLIENT only; that env never reaches the server.
#
# THE A/B: identical knobs, identical everything, one variable — whether the
# SERVER process inherits OMP/MKL_NUM_THREADS=1. Exporting it here is safe for
# the client too: the harness's _CANON_ENV already pins the client to 1 via
# setdefault, so cell B changes the SERVER only.
#
# Not a strength measurement: throwaway band 99e9, scratch out dir,
# --no-results-csv. Nothing is harvested.
#
# Instrument note: a game takes ~32 min here, so games-completed cannot be read
# in a short probe (and reading a rate off FIRST completions is the
# order-statistic trap). We sample aggregate CPU after warm-up instead.
# ============================================================================
set -uo pipefail
REPO=/home/doctor/projects/carcassone
CKPT=/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt
OUT_ROOT=/mnt/c/carc-shared/preflight_omp_20260726
WARMUP=${WARMUP:-240}
SAMPLES=${SAMPLES:-3}
SAMPLE_GAP=${SAMPLE_GAP:-20}
OW=28; FWD=2; MB=16          # the gate's EXACT knobs — do not vary in this A/B
cd "$REPO"
mkdir -p "$OUT_ROOT"
RESULT="$OUT_ROOT/OMP_AB_RESULTS.tsv"
printf 'cell\tserver_omp\tn_workers\tworker_agg_cpu\tworker_mean_cpu\torch_cpu\torch_threads\tgpu_w\n' > "$RESULT"

CUR_PGID=""
cleanup() {
  if [ -n "$CUR_PGID" ]; then
    kill -TERM -- "-$CUR_PGID" 2>/dev/null
    sleep 3
    kill -KILL -- "-$CUR_PGID" 2>/dev/null
  fi
  rm -f /dev/shm/carc_fairnvn* /dev/shm/sem.carc_fairnvn* 2>/dev/null
}
# ⚠️ the previous probe's driver was killed and left the cell ORPHANED (nothing
# to sample or stop it). Trap so the running cell always dies with the driver.
trap 'echo "[driver] trapped — cleaning up"; cleanup; exit 130' INT TERM HUP EXIT

run_cell () {
  local label=$1 omp=$2
  local log="$OUT_ROOT/${label}.log"
  echo "=== CELL $label (server OMP=$omp | W=$OW fwd=$FWD max_batch=$MB) ==="
  rm -rf "$OUT_ROOT/scratch_${label}"
  if [ "$omp" = "1" ]; then
    CAND_CKPT="$CKPT" OW="$OW" ORCH_FWD="$FWD" ORCH_MAX_BATCH="$MB" \
      OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
      setsid nice -n 19 bash scripts/classical_search/fair_net_vs_net_orch.sh \
        --info fair-netprior --opponent fair-champion \
        --exact-k 2 --k-dets 4 --sims 688 \
        --n 200 --paired --seed-start 99000000000 \
        --out-root "$OUT_ROOT" --out-subdir "scratch_${label}" \
        --no-results-csv > "$log" 2>&1 &
  else
    CAND_CKPT="$CKPT" OW="$OW" ORCH_FWD="$FWD" ORCH_MAX_BATCH="$MB" \
      setsid nice -n 19 bash scripts/classical_search/fair_net_vs_net_orch.sh \
        --info fair-netprior --opponent fair-champion \
        --exact-k 2 --k-dets 4 --sims 688 \
        --n 200 --paired --seed-start 99000000000 \
        --out-root "$OUT_ROOT" --out-subdir "scratch_${label}" \
        --no-results-csv > "$log" 2>&1 &
  fi
  local wpid=$!
  CUR_PGID=$(ps -o pgid= -p "$wpid" 2>/dev/null | tr -d ' ')
  echo "  wrapper pid=$wpid pgid=$CUR_PGID log=$log"
  sleep "$WARMUP"

  if ! kill -0 "$wpid" 2>/dev/null; then
    echo "  !! died during warm-up"; tail -20 "$log"
    printf '%s\t%s\tDIED\tDIED\tDIED\tDIED\tDIED\tDIED\n' "$label" "$omp" >> "$RESULT"
    CUR_PGID=""; return
  fi

  local agg=0 nw=0 orch=0 thr=0 gpu=0 i
  for i in $(seq 1 "$SAMPLES"); do
    # match on pgid + comm: mp SPAWN workers do NOT carry the script name in argv
    read -r c n < <(ps -eo pgid=,pcpu=,comm= 2>/dev/null \
      | awk -v g="$CUR_PGID" '$1==g && $3 ~ /^python/ {s+=$2; k++} END {print s+0, k+0}')
    local oc ot
    oc=$(ps -eo pgid=,pcpu=,comm= 2>/dev/null \
      | awk -v g="$CUR_PGID" '$1==g && $3 ~ /carc-orch/ {s+=$2} END {print s+0}')
    ot=$(ps -eo pgid=,nlwp=,comm= 2>/dev/null \
      | awk -v g="$CUR_PGID" '$1==g && $3 ~ /carc-orch/ {s+=$2} END {print s+0}')
    agg=$(awk -v a="$agg" -v c="$c"  'BEGIN{print a+c}')
    nw=$(awk  -v a="$nw"  -v c="$n"  'BEGIN{print a+c}')
    orch=$(awk -v a="$orch" -v c="$oc" 'BEGIN{print a+c}')
    thr=$(awk -v a="$thr" -v c="$ot" 'BEGIN{print a+c}')
    gpu=$(awk -v a="$gpu" -v c="$(nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits 2>/dev/null || echo 0)" 'BEGIN{print a+c}')
    [ "$i" -lt "$SAMPLES" ] && sleep "$SAMPLE_GAP"
  done
  agg=$(awk  -v a="$agg"  -v s="$SAMPLES" 'BEGIN{printf "%.0f", a/s}')
  nw=$(awk   -v a="$nw"   -v s="$SAMPLES" 'BEGIN{printf "%.0f", a/s}')
  orch=$(awk -v a="$orch" -v s="$SAMPLES" 'BEGIN{printf "%.0f", a/s}')
  thr=$(awk  -v a="$thr"  -v s="$SAMPLES" 'BEGIN{printf "%.0f", a/s}')
  gpu=$(awk  -v a="$gpu"  -v s="$SAMPLES" 'BEGIN{printf "%.0f", a/s}')
  local mean; mean=$(awk -v a="$agg" -v n="$nw" 'BEGIN{printf "%.1f", (n>0? a/n : 0)}')
  echo "  workers=$nw agg=${agg}% mean=${mean}% | orch=${orch}% threads=${thr} | gpu=${gpu}W"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$label" "$omp" "$nw" "$agg" "$mean" "$orch" "$thr" "$gpu" >> "$RESULT"

  kill -TERM -- "-$CUR_PGID" 2>/dev/null; sleep 4
  kill -KILL -- "-$CUR_PGID" 2>/dev/null; sleep 2
  echo "  survivors: $(ps -eo pgid= 2>/dev/null | awk -v g="$CUR_PGID" '$1==g' | wc -l)"
  CUR_PGID=""
  rm -f /dev/shm/carc_fairnvn* /dev/shm/sem.carc_fairnvn* 2>/dev/null
  sleep 3
}

run_cell "A_control_no_omp_limit" "0"
run_cell "B_server_omp1"          "1"

trap - INT TERM HUP EXIT
echo
echo "================ OMP A/B RESULTS ================"
column -t "$RESULT"
echo "================================================="
echo "Want: B frees cores from orch -> worker_agg_cpu UP, orch_cpu DOWN."
