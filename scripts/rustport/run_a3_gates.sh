#!/usr/bin/env bash
# F9/A3 gate runner — the four heavy legs, in order, low-W and niced so they can
# share a box with a live eval farm (`feedback_no_agent_compute_beside_eval`).
#
#   1. flags-OFF regate      — replay sample + G3-pattern search sample, zero
#                              tolerance. Proves the flag changed nothing while off.
#   2. flags-ON lockstep     — 1,000 games python<->rust under `--draw-rule redraw`.
#   3. compose-with-P5       — 1,000 games with redraw + retail + row 18 together.
#   4. flags-OFF lockstep    — 1,000 games control, so leg 2's "0 mismatches" has
#                              a same-instrument baseline.
#
# Usage: bash scripts/rustport/run_a3_gates.sh [OUTDIR] [WORKERS]
set -uo pipefail
cd "$(dirname "$0")/../.."
ROOT="$(pwd -P)"
OUT="${1:-$ROOT/measurement/f9_a3}"
W="${2:-4}"
PY="/home/doctor/projects/carcassone/.venv/bin/python"
export PYTHONPATH="$ROOT/.rsshadow:$ROOT/src:$ROOT/engine"
mkdir -p "$OUT"

run () { echo; echo "=== $1 ==="; shift; nice -n 19 "$@"; echo "rc=$?"; }

run "1a. flags-off REPLAY regate (reconcile_engine, sample)" \
    $PY scripts/rustport/reconcile_engine.py --corpus champ --limit 60 \
        --workers "$W" --out "$OUT/A3_regate_engine.json"

run "1b. flags-off SEARCH regate (reconcile_search, G3 pattern, sample)" \
    $PY scripts/rustport/reconcile_search.py --limit 12 --stride 24 --per-game 4 \
        --workers "$W" --tag a3_regate

run "2. flags-ON lockstep fuzz, 1000 games (--draw-rule redraw)" \
    $PY scripts/rustport/lockstep_fuzz.py --games 1000 --workers "$W" \
        --draw-rule redraw --tag a3_redraw --out "$OUT/A3_fuzz_redraw.json"

run "3. COMPOSE leg: redraw + retail start + row 18" \
    $PY scripts/rustport/lockstep_fuzz.py --games 1000 --workers "$W" \
        --draw-rule redraw --start-rule retail --start-row 18 \
        --tag a3_compose --out "$OUT/A3_fuzz_compose.json"

run "4. flags-OFF lockstep control, 1000 games" \
    $PY scripts/rustport/lockstep_fuzz.py --games 1000 --workers "$W" \
        --tag a3_control --out "$OUT/A3_fuzz_control.json"

echo; echo "=== ALL A3 GATE LEGS DONE ==="
