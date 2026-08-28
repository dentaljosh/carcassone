#!/usr/bin/env bash
# =============================================================================
# S0v2 SCRIPTED EXPLOITER — SIGNATURE SMOKE.  ⛔ SMOKE, NOT A CELL.
#
#   * NO band is claimed. The seed range 900000010000..900000010029 is a
#     deliberately throwaway one, DISJOINT from the 900000000000-area range
#     s0_smoke.py burned and from the 900000009000-area calibration range.
#     These decks are burned and must never be cited in a measurement.
#   * NO results.csv row, NO gate ladder, NO blind commit, NO adoption chain.
#   * Every artifact it writes is stamped "smoke": true.
#
# THREE arms (DESIGN.md SS3), all against the CHAMPION OF RECORD at the r3
# screening instrument (k4x688 = 2752 both sides, rust both sides, fixed_v1+R9,
# exact-K 2 marginalized, tie-arbiter off), deck-paired AND deck-matched across
# arms (all three run the SAME 30 decks):
#
#   CTRL     champion vs champion, no plan module      30 decks / 60 games
#   S0V2_M   MERGE fire only                           30 decks / 60 games
#   S0V2_F   SETUP -> FOOTHOLD -> MERGE                30 decks / 60 games
#
# Each arm resumes: a game whose output file exists is skipped, and
# --time-budget stops the driver at a game boundary, so a long arm is a
# sequence of short bounded foreground invocations.
#
#   run_smoke.sh play <ARM> [TIME_BUDGET_SECS]     # one bounded pass (0 = all)
#   run_smoke.sh grade <ARM>                       # census + signature read-out
#   run_smoke.sh grade-all
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="$(git -C "$DIR" rev-parse --show-toplevel)"
REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
OUT=/mnt/c/carc-shared/s0v2_smoke_20260828
W=8                       # another agent shares the box; W8 is the cap
SEED=900000010000
DECKS=30
export PYTHONPATH="$TREE/src:$TREE/engine"

CENSUS="$REPO/measurement/e4_exploit_grading_20260825/stage_a_census.py"
SIG="$REPO/measurement/s0_exploiter_prep/s0_signature.py"

arm_plan() {   # $1 = arm -> echoes the --plan profile
  case "$1" in
    CTRL)   echo off ;;
    S0V2_M) echo merge ;;
    S0V2_F) echo full ;;
    *) echo "FATAL: unknown arm '$1'" >&2; exit 2 ;;
  esac
}

cmd="${1:?play|grade|grade-all}"

case "$cmd" in
  play)
    arm="${2:?arm}"; budget="${3:-400}"
    plan="$(arm_plan "$arm")"
    exec nice -n 19 "$PY" "$DIR/s0v2_smoke.py" \
        --label "$arm" --plan "$plan" --decks "$DECKS" --seed-start "$SEED" \
        --workers "$W" --out "$OUT/$(echo "$arm" | tr 'A-Z' 'a-z')" \
        --time-budget "$budget"
    ;;
  grade)
    arm="${2:?arm}"
    lo="$(echo "$arm" | tr 'A-Z' 'a-z')"
    "$PY" "$CENSUS" --games-dir "$OUT/$lo" --out-dir "$OUT/${lo}_rows" \
        --profile fixed_v1 --out-name rows.jsonl
    aname="S0V2"; [ "$arm" = "CTRL" ] && aname="CHAMP_A"
    bname="CHAMP"; [ "$arm" = "CTRL" ] && bname="CHAMP_B"
    "$PY" "$SIG" --rows "$OUT/${lo}_rows/rows.jsonl" \
        --label "$arm" --a-name "$aname" --b-name "$bname" \
        --out "$OUT/${lo}_rows/signature.json"
    "$PY" "$DIR/s0v2_readout.py" --games-dir "$OUT/$lo" \
        --rows "$OUT/${lo}_rows/rows.jsonl" --label "$arm" \
        --out "$OUT/${lo}_rows/telemetry.json"
    ;;
  grade-all)
    for a in CTRL S0V2_M S0V2_F; do
      [ -d "$OUT/$(echo "$a" | tr 'A-Z' 'a-z')" ] || continue
      "$0" grade "$a"
      echo
    done
    ;;
  *) echo "FATAL: unknown command '$cmd'" >&2; exit 2 ;;
esac
