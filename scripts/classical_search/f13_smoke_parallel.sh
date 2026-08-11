#!/usr/bin/env bash
# F13 identity pre-flight, parallelised.
#
# `f13_smoke.py --mode identity` is serial by construction (no --workers), so the
# pre-registered 20-game K4-vs-K4 identity check costs ~1 h of ONE core while the rest
# of the box idles. The games are independent and seeded, so the check parallelises
# trivially by splitting the seed range across N instances and requiring ALL to pass.
#
# Identity is a BINARY property: any single divergent action fails the gate, so
# "20 games in 5 shards" is exactly as strong as "20 games in one process".
#
# ⚠️ MODE=k6 IS A TIMING MEASUREMENT, so sharding contends and inflates every wall — which
# inflates the cap-hit rate. That is ACCEPTABLE HERE AND ONLY HERE because the bias is
# ONE-SIDED and points the safe way: the pre-registered rule is "cap-hit rate > 20% ⇒ the
# rung is censored / not-a-verdict", so a rate measured UNDER contention is an OVER-estimate.
# Reading under 20% while contended ⇒ under 20% clean. A rate ABOVE 20% here is NOT a verdict
# and must be re-measured serially (exclusive tenant) before the rung is dropped.
#
# Usage: f13_smoke_parallel.sh <identity|k6> [SHARDS] [GAMES_PER_SHARD]
set -uo pipefail

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
SMOKER="$REPO/scripts/classical_search/f13_smoke.py"
MODE="${1:?usage: f13_smoke_parallel.sh <identity|k6> [SHARDS] [GAMES_PER_SHARD]}"
case "$MODE" in identity|k6) ;; *) echo "bad mode: $MODE" >&2; exit 2 ;; esac

OUT=/mnt/c/carc-shared/f13_${MODE}_$(date +%Y%m%d_%H%M%S)

SHARDS="${2:-5}"
N_PER="${3:-4}"
# k6 draws from a DIFFERENT sub-range than identity so the two pre-flights never share a
# position (the launcher's own k6 path uses SMOKE_BAND+1000; +500000 keeps us clear of both).
SMOKE_BAND=106900000000
[ "$MODE" = k6 ] && SMOKE_BAND=$((SMOKE_BAND + 500000))
STRIDE=1000            # seed spacing between shards: >> games per shard, so no overlap

# ⚠️ MUST match f13_ladder_launcher.sh's env EXACTLY — several of these are latched at
# import (R9 flips a Rust OnceLock; the leaf knobs are read once), so exporting them after
# the process starts is silently too late. The smoke hard-fails rc=3 on r9_env_ok=False,
# which is how this was caught rather than run under the wrong rules.
export CARCASSONNE_FIX_R9=1
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1   # OpenBLAS oversubscription = the C5 ladder's "x1.75 hang"

mkdir -p "$OUT"
echo "[$MODE] $SHARDS shards x $N_PER games = $((SHARDS * N_PER)) games -> $OUT"

pids=()
for i in $(seq 0 $((SHARDS - 1))); do
  seed=$((SMOKE_BAND + i * STRIDE))
  nice -n 19 "$PY" "$SMOKER" --mode "$MODE" --n "$N_PER" --seed-start "$seed" \
      --exact-wall-caps 5:300,6:600 --exact-k-floor 4 \
      --exact-solver rust --backend rust --rules-profile fixed_v1 \
      --cand-sims 2750 --champ-sims 2750 --c-puct 1.5 --tau-p 5 \
      --leaf-quantize float --final-select visits \
      > "$OUT/shard_${i}_seed_${seed}.log" 2>&1 &
  pids+=($!)
  echo "[$MODE] shard $i seed $seed pid ${pids[-1]}"
done

fail=0
for i in "${!pids[@]}"; do
  if wait "${pids[$i]}"; then
    echo "[$MODE] shard $i done rc=0"
  else
    rc=$?
    echo "[$MODE] shard $i FAILED rc=$rc"
    fail=1
  fi
done

echo "----------------------------------------------------------------"
if [ "$fail" = 0 ]; then
  if [ "$MODE" = identity ]; then
    echo "[$MODE] ✅ ALL $SHARDS SHARDS PASS — $((SHARDS * N_PER)) games, 100% action identity"
  else
    echo "[$MODE] ✅ all shards completed — aggregate the per-shard cap-hit lines below"
    grep -h "REALIZED\|latch solves\|censored_rate\|wall/game\|peak RSS" "$OUT"/shard_*.log 2>/dev/null
  fi
else
  echo "[$MODE] ❌ a shard exited nonzero — for identity this means DIVERGENCE (do NOT launch any cell); for k6 read the logs (a cap-hit is NOT a nonzero exit)."
  grep -il "diverg\|mismatch\|FAIL" "$OUT"/shard_*.log 2>/dev/null | head
fi
echo "[$MODE] logs: $OUT"
exit "$fail"
