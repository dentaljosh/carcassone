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
# Usage: f13_identity_parallel.sh [SHARDS] [GAMES_PER_SHARD]
set -uo pipefail

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
SMOKER="$REPO/scripts/classical_search/f13_smoke.py"
OUT=/mnt/c/carc-shared/f13_identity_$(date +%Y%m%d_%H%M%S)

SHARDS="${1:-5}"
N_PER="${2:-4}"
SMOKE_BAND=106900000000
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
echo "[identity] $SHARDS shards x $N_PER games = $((SHARDS * N_PER)) games -> $OUT"

pids=()
for i in $(seq 0 $((SHARDS - 1))); do
  seed=$((SMOKE_BAND + i * STRIDE))
  nice -n 19 "$PY" "$SMOKER" --mode identity --n "$N_PER" --seed-start "$seed" \
      --exact-wall-caps 5:300,6:600 --exact-k-floor 4 \
      --exact-solver rust --backend rust --rules-profile fixed_v1 \
      --cand-sims 2750 --champ-sims 2750 --c-puct 1.5 --tau-p 5 \
      --leaf-quantize float --final-select visits \
      > "$OUT/shard_${i}_seed_${seed}.log" 2>&1 &
  pids+=($!)
  echo "[identity] shard $i seed $seed pid ${pids[-1]}"
done

fail=0
for i in "${!pids[@]}"; do
  if wait "${pids[$i]}"; then
    echo "[identity] shard $i PASS"
  else
    rc=$?
    echo "[identity] shard $i FAIL rc=$rc"
    fail=1
  fi
done

echo "----------------------------------------------------------------"
if [ "$fail" = 0 ]; then
  echo "[identity] ✅ ALL $SHARDS SHARDS PASS — $((SHARDS * N_PER)) games, 100% action identity"
else
  echo "[identity] ❌ DIVERGENCE — the K4-vs-K4 identity gate FAILED. Do NOT launch any cell."
  grep -il "diverg\|mismatch\|FAIL" "$OUT"/shard_*.log 2>/dev/null | head
fi
echo "[identity] logs: $OUT"
exit "$fail"
