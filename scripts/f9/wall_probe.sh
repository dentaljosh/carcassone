#!/usr/bin/env bash
# F9 Gate A1-a — the 400-game champion-play WALL PROBE.
#
#   docs/F9_BUILD_SPEC_20260802.md §A1 ("Gate A1-a, the decider, ~1 box-hour"):
#   build W4, then generate 400 CHAMPION-PLAY games (not random play) with the
#   sentinel armed, and let the measurement choose between W2 (recentre only,
#   free) and W3 (runtime board size, provable, costs a leaf bench).
#
# ⚠️ THIS IS DESCRIPTIVE. Throwaway seeds, NO band claim, NO elo, NO
#    experiments/results.csv row, governance/PRODUCTION.yaml untouched. It
#    measures event RATES under the policy the cells actually run — nothing about
#    strength, and nothing that could be mistaken for a cell.
#
# WHY IT GENERATES AT centered18 AND RE-PRICES row 6, NOT THE REVERSE.
#   A trajectory played on the walled grid has already been bent by the wall: its
#   denial count is what the wall permitted, not what champion play wanted. Row 18
#   denies nothing under natural play (400 random games, DECISIONS 2026-08-02
#   early), so a row-18 corpus is UNCENSORED, and `analyze_wall_probe.py` prices
#   row 6 — and any W3 candidate — from the recorded relative coordinates. That is
#   `diagnose_grid_wall.py`'s oversized-twin trick done from the record, for the
#   cost of zero extra games.
#   Also run `--profile walled` if you want the as-played row-6 arm as a control;
#   the two are directly comparable because the deck seeds are the same.
#
# COST. Champion-play generation at the production budget k8x1376 = 11008 measures
#   ~328 games/h local, ~260 laptop, ~590 two-box (DECISIONS 2026-08-02 late
#   afternoon). So n=400 is ~73 min local-only, ~41 min two-box.
#   ⚠️ RE-SWEEP W BEFORE A REAL FARM (spec §5.2 rider): the F7d W* is STALE, and
#   the sentinel is itself a (tiny) workload change on top. The W below is the
#   2026-08-02 gen heuristic, not a measured optimum for this workload.
#
# ⚠️ CENSUS FIRST, AND DO NOT RUN THIS BESIDE A LIVE EVAL (memory
#    `feedback_no_agent_compute_beside_eval`): nice + thread caps are NOT
#    coexistence on the DRAM-bound box.
#
# Usage:
#   scripts/f9/wall_probe.sh [--profile centered18|walled] [--games 400]
#                            [--workers N] [--seed-start S] [--out DIR]
#                            [--backend rust|python] [--smoke]
# Then:
#   scripts/f9/analyze_wall_probe.py DIR --json DIR/A1a_REPORT.json
set -euo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

# The interpreter. A git WORKTREE has no `.venv` of its own (the venv is editable-
# installed against the main tree), so a worktree build sets CARC_PYTHON + PYTHONPATH
# rather than pretending one exists — memory `feedback-worktree-isolation-live-tree`.
PY="${CARC_PYTHON:-$REPO/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "no interpreter at $PY — set CARC_PYTHON (and PYTHONPATH, in a worktree)" >&2
  exit 2
fi

PROFILE=centered18
GAMES=400
WORKERS=16
# THROWAWAY seeds, top of the block docs/F9_BUILD_SPEC_20260802.md §5.3 reserves for
# F9 (1.00e11-1.10e11), deliberately far from the bottom where the CONFIRMATORY
# Phase-B cells will land, and clear of F7b's 1.00e11+0..199. No BAND_REGISTRY row:
# a descriptive corpus claims no band (spec §3, Gate C).
SEED_START=109000000000
OUT=""
BACKEND=rust
KDETS=8
SIMS=1376
SMOKE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)     PROFILE="$2"; shift 2 ;;
    --games)       GAMES="$2"; shift 2 ;;
    --workers)     WORKERS="$2"; shift 2 ;;
    --seed-start)  SEED_START="$2"; shift 2 ;;
    --out)         OUT="$2"; shift 2 ;;
    --backend)     BACKEND="$2"; shift 2 ;;
    --smoke)       SMOKE=1; GAMES=4; WORKERS=2; KDETS=2; SIMS=32; shift ;;
    -h|--help)     sed -n '2,40p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -z "$OUT" ]] && OUT="/mnt/c/carc-shared/f9_wall_probe_20260802/${PROFILE}"
if [[ "$SMOKE" == "1" ]]; then OUT="/tmp/f9_wall_probe_smoke_${PROFILE}"; fi

# The curve125 champion leaf env — the probe must run the CHAMPION's leaf, not the
# scripts' curve100 default, or "under champion play" is a different sentence.
# shellcheck disable=SC1091
source "$REPO/scripts/distill_flywheel/champ_env.sh"

echo "F9 A1-a wall probe"
echo "  profile     : $PROFILE   (descriptive; no band, no elo, no results.csv row)"
echo "  budget      : k${KDETS}x${SIMS} = $((KDETS*SIMS))  backend=$BACKEND"
echo "  games       : $GAMES   seeds ${SEED_START}..$((SEED_START+GAMES-1))  workers=$WORKERS"
echo "  out         : $OUT"
if [[ "$SMOKE" == "1" ]]; then echo "  *** SMOKE ***"; fi
echo

# --actions-only: this is a DESCRIPTIVE corpus, so the ~28 MB/game of obs tensors
# are pure waste — the sentinel shards and the action log carry everything the
# analysis reads. The sentinel is default-ON; --shared-claim lets a second box join.
CMD=( nice -n 19 "$PY" -u
      "$REPO/scripts/distill_flywheel/gen_fair_distill.py"
      --games "$GAMES" --k-dets "$KDETS" --sims "$SIMS"
      --workers "$WORKERS" --seed-start "$SEED_START"
      --backend "$BACKEND" --rules-profile "$PROFILE"
      --actions-only --shared-claim
      --out "$OUT" )

if [[ "$SMOKE" == "1" ]]; then
  "${CMD[@]}"
  echo
  "$PY" "$REPO/scripts/f9/analyze_wall_probe.py" "$OUT"
else
  # ⚠️ DETACHED (CLAUDE.md): Mac-sleep SIGHUP and WSL VM teardown both kill
  # tty-attached jobs, and run_in_background alone is not enough.
  mkdir -p "$OUT"
  nohup setsid "${CMD[@]}" > "$OUT/probe.log" 2>&1 < /dev/null &
  disown || true
  echo "launched detached; log: $OUT/probe.log"
  echo "when it finishes:"
  echo "  scripts/f9/analyze_wall_probe.py $OUT --json $OUT/A1a_REPORT.json"
fi
