#!/usr/bin/env bash
# OM-M1 — step 2: the four legs. ⚠️ THIS IS THE ONLY STEP THAT BUYS COMPUTE.
#
# Usage: scripts/omm1/run_gate.sh [workers] [limit] [bitexact_stride] [out_subdir]
#   limit = 0 -> the whole frame.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$HERE/env.sh"

W="${1:-30}"
LIMIT="${2:-0}"
STRIDE="${3:-20}"
SUB="${4:-LEGS}"

cd "$WT"
exec nice -n 19 "$VENV/bin/python" "$HERE/run_gate.py" \
    --frame "$OUT/FIRED_PLIES.jsonl" \
    --out-dir "$OUT/$SUB" \
    --workers "$W" \
    --limit "$LIMIT" \
    --bitexact-stride "$STRIDE" \
    --b 64
