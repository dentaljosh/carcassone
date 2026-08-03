#!/usr/bin/env bash
# F9/A3 gate legs, part 2 — the search regate and the grid-confound disentangler.
#
#   1b. flags-OFF SEARCH regate (the G3 pattern), zero tolerance.
#   5.  redraw + row 18 ONLY (no retail): the compose leg varied the grid AND the
#       start rule together and showed 1.4% of games affected vs 7.8% walled, so
#       this leg isolates the grid. If the rate stays low, a large share of the
#       audit's "unplaceable tile" events are WALL ARTIFACTS (RF-C-1), not
#       genuine rules events — which resizes A3's blast radius.
set -uo pipefail
cd "$(dirname "$0")/../.."
ROOT="$(pwd -P)"
PY="/home/doctor/projects/carcassone/.venv/bin/python"
export PYTHONPATH="$ROOT/.rsshadow:$ROOT/src:$ROOT/engine"
OUT="$ROOT/measurement/f9_a3"
mkdir -p "$OUT"

echo "=== 1b. flags-off SEARCH regate (reconcile_search, G3 pattern, sample) ==="
nice -n 19 $PY scripts/rustport/reconcile_search.py \
    --limit 12 --stride 24 --per-game 4 --workers 4 --tag a3_regate
echo "rc=$?"

echo
echo "=== 5. redraw + row 18 only (grid confound disentangler) ==="
nice -n 19 $PY scripts/rustport/lockstep_fuzz.py --games 1000 --workers 4 \
    --draw-rule redraw --start-row 18 --tag a3_row18 \
    --out "$OUT/A3_fuzz_redraw_row18.json"
echo "rc=$?"

echo
echo "=== A3 GATES PART 2 DONE ==="
