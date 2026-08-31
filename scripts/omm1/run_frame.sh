#!/usr/bin/env bash
# OM-M1 — step 1: build the FIRED-PLY frame. Leaf calls only, NO playouts.
# Usage: scripts/omm1/run_frame.sh [workers]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$HERE/env.sh"

W="${1:-30}"
cd "$WT"
exec nice -n 19 "$VENV/bin/python" "$HERE/build_fired_plies.py" \
    --workers "$W" --out-dir "$OUT"
