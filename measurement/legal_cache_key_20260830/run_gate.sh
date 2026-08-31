#!/usr/bin/env bash
# Legal-cache injective-key fix — the full gate battery.
#
# Every combination is a SEPARATE process because both flags are import-latched:
#   CARCASSONNE_FIX_LEGAL_CACHE_KEY  (the key under test; default 1 since 2026-08-30)
#   CARCASSONNE_FIX_R9               (farm-data latch; changes base_deck at import)
#
#   A  fixed  x R9=0   300 games   G-MASK + G-COVER
#   B  fixed  x R9=1   300 games   G-MASK + G-COVER
#   C  legacy x R9=0   300 games   G-WITNESS (defect reproduces; both witness tiles)
#   D  legacy x R9=1    60 games   G-WITNESS (defect is not R9-specific)
#   E  cache effectiveness, one MCTS-driven game, both key modes  -> G-CACHE
#
# nice 19 / small W on purpose: a timing-sensitive eval round owns this box.
set -uo pipefail
cd "$(dirname "$0")/../.."
ROOT="$PWD"
OUT="$ROOT/measurement/legal_cache_key_20260830"
PY="/home/doctor/projects/carcassone/.venv/bin/python"
W="${W:-2}"
export PYTHONPATH="$ROOT/src:$ROOT/engine"
export OMP_NUM_THREADS=1

run() {  # run <label> <fix> <r9> <games> <outfile>
  echo "=== $1  fix=$2 r9=$3 games=$4 ==="
  CARCASSONNE_FIX_LEGAL_CACHE_KEY="$2" CARCASSONNE_FIX_R9="$3" \
    nice -n 19 "$PY" "$OUT/gate_fuzz.py" \
      --mode "$([ "$2" = 1 ] && echo fixed || echo legacy)" \
      --games "$4" --workers "$W" --out "$5"
  echo "--- $1 exit=$? ---"
}

run A 1 0 300 "$OUT/GATE_fixed_r9off.json"
run B 1 1 300 "$OUT/GATE_fixed_r9on.json"
run C 0 0 300 "$OUT/GATE_legacy_r9off.json"
run D 0 1  60 "$OUT/GATE_legacy_r9on.json"

for f in 1 0; do
  echo "=== E cache effectiveness fix=$f ==="
  CARCASSONNE_FIX_LEGAL_CACHE_KEY="$f" nice -n 19 "$PY" \
    "$OUT/cache_effectiveness.py" \
    --out "$OUT/CACHE_$([ "$f" = 1 ] && echo fixed || echo legacy).json"
done
echo "=== GATE BATTERY DONE ==="
