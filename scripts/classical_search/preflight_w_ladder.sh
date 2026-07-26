#!/usr/bin/env bash
# ============================================================================
# carc-orch W ladder — brackets W above AND below the gate's W=28 (2026-07-26).
#
# ⚠️ max_batch is a DEPENDENT variable of W here, not an independent knob.
# WHY: on the fair-netprior path each worker request carries k=1 position
# (make_fair_net_prior_evaluator -> make_remote_single_evaluator), and the worker
# BLOCKS on its response semaphore until answered. So at most W requests are ever
# outstanding, and the collector batches on POSITIONS
# (rust/carc-orch/src/batcher.rs:186 `while total_k < max_batch`) => with k=1,
# max_batch counts requests. max_batch < W therefore STRUCTURALLY guarantees the
# server can never coalesce one round of workers into a single GPU forward.
#   the gate ran W=28 / mb=16 -> 57% round coverage, >=2 forwards per round, always.
# We set mb = W so each cell gets 100% round coverage and W is the only variable.
#
# fwd is held at 2 (the gate's value). Because workers block, the pipeline is
# all-W-request -> one forward -> all-W-released -> compute, so extra forwarders
# have little to overlap except via worker desynchronisation. Probe fwd separately
# AT THE WINNING W rather than confounding it into this ladder.
#
# PREREQ: run preflight_omp_ab.sh first. If the server's OMP pool is what owns the
# box (measured: carc-orch 2578% vs workers 364% at the gate's config), this ladder
# is measuring contention, not W. Bake the A/B's winning server env in below.
#
# Throwaway band 99e9, scratch out dirs, --no-results-csv. Nothing harvested.
# Instrument: aggregate CPU after warm-up (a game takes ~32 min; games-completed
# is unreadable in a short probe, and first-completions is the order-statistic trap).
# ============================================================================
set -uo pipefail
# ⚠️ `set -m` (job control) puts every background job in its OWN process group whose
# PGID == the job's PID. This is load-bearing, not cosmetic.
# BUG IT FIXES (hit on the laptop 2026-07-26, cost a 25-min orphan): the previous
# version launched cells with `setsid` and then read the group back via
# `ps -o pgid= -p $!`. setsid only forks when the caller is ALREADY a group leader,
# so on a box where the driver was itself a group leader the lookup returned the
# DRIVER'S OWN pgid. Consequences: the sampler found 0 workers (they were in another
# group) and wrote a row of zeros, then `kill -- -$CUR_PGID` KILLED THE DRIVER — while
# the real cell survived, orphaned, and kept running a 7-hour eval nobody was watching.
# With `set -m` the pgid is known by construction; no lookup, nothing to get wrong.
set -m
REPO=/home/doctor/projects/carcassone
# ⚠️ THE SHARE MOUNTS AT A DIFFERENT PATH PER BOX: local = /mnt/c/carc-shared,
# anything running ON the laptop/xeon = /mnt/carc-shared. Override both on remotes.
SHARE=${SHARE:-/mnt/c/carc-shared}
CKPT=${CKPT:-$SHARE/distill_strong_20260723/ckpt/iter_03.pt}
OUT_ROOT=${OUT_ROOT:-$SHARE/preflight_wladder_20260726}
WARMUP=${WARMUP:-240}
SAMPLES=${SAMPLES:-3}
SAMPLE_GAP=${SAMPLE_GAP:-20}
FWD=${FWD:-2}
# set by the OMP A/B verdict; 1 = pin the SERVER's libtorch pool
SERVER_OMP=${SERVER_OMP:-1}
W_LIST=${W_LIST:-"16 24 32 40 48"}
cd "$REPO"
mkdir -p "$OUT_ROOT"
RESULT="$OUT_ROOT/W_LADDER_RESULTS.tsv"
printf 'W\tmax_batch\tfwd\tserver_omp\tn_workers\tworker_agg_cpu\tworker_mean_cpu\torch_cpu\tgpu_w\n' > "$RESULT"

CUR_PGID=""
cleanup() {
  [ -n "$CUR_PGID" ] && { kill -TERM -- "-$CUR_PGID" 2>/dev/null; sleep 3; kill -KILL -- "-$CUR_PGID" 2>/dev/null; }
  rm -f /dev/shm/carc_fairnvn* /dev/shm/sem.carc_fairnvn* 2>/dev/null
}
trap 'echo "[driver] trapped"; cleanup; exit 130' INT TERM HUP EXIT

run_w () {
  local w=$1 mb=$1     # mb = W by construction (see header)
  local log="$OUT_ROOT/w${w}.log"
  echo "=== W=$w (max_batch=$mb fwd=$FWD server_omp=$SERVER_OMP) ==="
  rm -rf "$OUT_ROOT/scratch_w${w}"
  local envs=(CAND_CKPT="$CKPT" OW="$w" ORCH_FWD="$FWD" ORCH_MAX_BATCH="$mb")
  [ "$SERVER_OMP" = "1" ] && envs+=(OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1)
  env "${envs[@]}" nice -n 19 bash scripts/classical_search/fair_net_vs_net_orch.sh \
      --info fair-netprior --opponent fair-champion \
      --exact-k 2 --k-dets 4 --sims 688 \
      --n 200 --paired --seed-start 99000000000 \
      --out-root "$OUT_ROOT" --out-subdir "scratch_w${w}" \
      --no-results-csv > "$log" 2>&1 &
  local wpid=$!
  CUR_PGID="$wpid"        # guaranteed by `set -m`; never look this up
  # Refuse to continue if the cell's group is somehow our own — killing that group
  # is a driver suicide, and it is silent (see the set -m note above).
  local own_pgid; own_pgid=$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')
  if [ "$CUR_PGID" = "$own_pgid" ] || [ -z "$CUR_PGID" ]; then
    echo "FATAL: cell pgid ($CUR_PGID) == driver pgid ($own_pgid) — refusing to sample/kill" >&2
    CUR_PGID=""; return 1
  fi
  echo "  pid=$wpid pgid=$CUR_PGID (driver pgid $own_pgid)"
  sleep "$WARMUP"
  if ! kill -0 "$wpid" 2>/dev/null; then
    echo "  !! died"; tail -20 "$log"
    printf '%s\t%s\t%s\t%s\tDIED\tDIED\tDIED\tDIED\tDIED\n' "$w" "$mb" "$FWD" "$SERVER_OMP" >> "$RESULT"
    CUR_PGID=""; return
  fi
  local agg=0 nw=0 orch=0 gpu=0 i
  for i in $(seq 1 "$SAMPLES"); do
    read -r c n < <(ps -eo pgid=,pcpu=,comm= 2>/dev/null \
      | awk -v g="$CUR_PGID" '$1==g && $3 ~ /^python/ {s+=$2; k++} END {print s+0, k+0}')
    local oc
    oc=$(ps -eo pgid=,pcpu=,comm= 2>/dev/null \
      | awk -v g="$CUR_PGID" '$1==g && $3 ~ /carc-orch/ {s+=$2} END {print s+0}')
    agg=$(awk -v a="$agg" -v c="$c" 'BEGIN{print a+c}')
    nw=$(awk -v a="$nw" -v c="$n" 'BEGIN{print a+c}')
    orch=$(awk -v a="$orch" -v c="$oc" 'BEGIN{print a+c}')
    gpu=$(awk -v a="$gpu" -v c="$(nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits 2>/dev/null || echo 0)" 'BEGIN{print a+c}')
    [ "$i" -lt "$SAMPLES" ] && sleep "$SAMPLE_GAP"
  done
  agg=$(awk -v a="$agg" -v s="$SAMPLES" 'BEGIN{printf "%.0f", a/s}')
  nw=$(awk -v a="$nw" -v s="$SAMPLES" 'BEGIN{printf "%.0f", a/s}')
  orch=$(awk -v a="$orch" -v s="$SAMPLES" 'BEGIN{printf "%.0f", a/s}')
  gpu=$(awk -v a="$gpu" -v s="$SAMPLES" 'BEGIN{printf "%.0f", a/s}')
  local mean; mean=$(awk -v a="$agg" -v n="$nw" 'BEGIN{printf "%.1f", (n>0? a/n : 0)}')
  echo "  workers=$nw agg=${agg}% mean=${mean}% orch=${orch}% gpu=${gpu}W"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$w" "$mb" "$FWD" "$SERVER_OMP" "$nw" "$agg" "$mean" "$orch" "$gpu" >> "$RESULT"
  kill -TERM -- "-$CUR_PGID" 2>/dev/null; sleep 4
  kill -KILL -- "-$CUR_PGID" 2>/dev/null; sleep 2
  CUR_PGID=""
  rm -f /dev/shm/carc_fairnvn* /dev/shm/sem.carc_fairnvn* 2>/dev/null
  sleep 3
}

for w in $W_LIST; do run_w "$w"; done

trap - INT TERM HUP EXIT
echo
echo "================ W LADDER ================"
column -t "$RESULT"
echo "=========================================="
echo "Peak worker_agg_cpu = the operating point. Check it is INTERIOR to the ladder;"
echo "if the peak is at an endpoint the ladder did not bracket it — extend before adopting."
