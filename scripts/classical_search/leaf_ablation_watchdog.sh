#!/usr/bin/env bash
# leaf_ablation_watchdog.sh — chain wrapper around scripts/measurement_infra/run_watchdog.sh
# for the multi-cell LEAF-COMPONENT KNOCKOUT ABLATION (measurement/leaf_ablation_20260730/).
#
# WHY A WRAPPER: run_watchdog.sh watches ONE cell (one records glob, one expected_n) and its
# orphan-claim guard derives CELL_DIR from `dirname "$GLOB"`. A multi-cell glob like
# '.../abl_*/seed*_a*.json' would give CELL_DIR='.../abl_*', and because that glob char
# arrives via a QUOTED expansion it is NOT re-globbed by the guard's `for c in "$CELL_DIR"/*.claim`
# — the guard would silently match nothing and never clear an orphan claim. So: watch the cells
# ONE AT A TIME, in the same priority order the launcher runs them, each with its own real glob.
#
# For each cell: skip if already full, else block in run_watchdog.sh until that cell reaches N
# (or run_watchdog gives up), then move to the next. The relaunch command is the LAUNCHER itself,
# which is resume-safe (--shared-claim + a `cell_complete` cache check skips finished cells).
#
# Usage (arm detached, ALONGSIDE an already-launched run — it does not start the first driver):
#   setsid nohup scripts/classical_search/leaf_ablation_watchdog.sh local >/dev/null 2>&1 & disown
#   setsid nohup scripts/classical_search/leaf_ablation_watchdog.sh laptop >/dev/null 2>&1 & disown
set -uo pipefail

BOX_TAG="${1:?usage: leaf_ablation_watchdog.sh <local|laptop> [WORKERS]}"
WORKERS="${2:-16}"
REPO=/home/doctor/projects/carcassone
BAND=96000000000
N=400
CELLS="meepleoff oppanticoff anticoff selfanticoff meepleflat capoff"   # PRIORITY ORDER

case "$BOX_TAG" in
  local|primary) SHARE=/mnt/c/carc-shared ;;
  laptop|helper) SHARE=/mnt/carc-shared ;;
  *) echo "bad box tag '$BOX_TAG'" >&2; exit 2 ;;
esac
OUT_ROOT="$SHARE/leaf_ablation"
LOG="$REPO/measurement/leaf_ablation_20260730/watchdog_${BOX_TAG}.log"
PAT="seed-start $BAND"     # matches the harness argv only (the launcher's argv lacks the band)

say() { echo "$(date '+%F %T') [chain-$BOX_TAG] $*" >>"$LOG"; }
say "chain watchdog armed: cells=[$CELLS] n=$N out_root=$OUT_ROOT pattern='$PAT'"

for c in $CELLS; do
  dir="$OUT_ROOT/abl_$c"
  mkdir -p "$dir"
  got=$(ls "$dir"/seed*_a*.json 2>/dev/null | grep -vc summary)
  if [ "$got" -ge "$N" ]; then
    say "cell $c already full ($got/$N) -> skip"
    continue
  fi
  say "watching cell $c ($got/$N)"
  # blocks until this cell is full (rc 0) or run_watchdog exhausts its relaunch budget (rc 1)
  "$REPO/scripts/measurement_infra/run_watchdog.sh" \
      "$dir/seed*_a*.json" "$N" "$PAT" "$LOG" \
      -- nice -n 19 bash "$REPO/scripts/classical_search/leaf_ablation_launcher.sh" "$WORKERS" "$BOX_TAG"
  rc=$?
  say "cell $c watch ended rc=$rc ($(ls "$dir"/seed*_a*.json 2>/dev/null | grep -vc summary)/$N records)"
  [ "$rc" -eq 0 ] || say "WARNING: cell $c did not reach $N — chain continues to the next cell"
done
say "chain watchdog finished (all cells processed)"
