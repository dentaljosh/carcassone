#!/bin/bash
# ITEM 2 / BLOCK 2a — THE WIRING GATE. HARD BLOCKER for block B.
# Spec: docs/LEVER_MENU_PLAN_20260810.md section 4.2.
#
# `farm_growth_off` has a complete code path to the fair harness but has NEVER been exercised
# through eval_fair_puct.py -- zero farm_growth_off manifests exist anywhere on the share. The
# precedent for treating that as a blocker rather than a formality is the caps/curve build,
# which caught the clairvoyant rust mirrors ignoring --rules-profile ENTIRELY. A silently
# dropped knob produces a perfectly plausible ~0 elo null.
#
# TWO micro-cells, LOCAL ONLY (the laptop is busy with item 6's oracle scorer, and a 4-minute
# smoke does not need two-box coordination), on sub-bands DISJOINT from item 2's cell decks:
#   1.189e11 + 0    farm_growth_off  n=32  -> the three manifest assertions
#   1.189e11 + 1000 farm_base_off    n=64  -> the SIGN CONTROL
#
# WHY THE CONTROL IS n=64 AND NOT n=32 (a deliberate deviation from the plan's "~32 games"):
# at n=32 the unpaired 1-sigma is ~+/-61 elo, so a TRUE -140 effect reads above the -40 bar
# about 5% of the time -- a 5% chance of falsely blocking the entire menu. n=64 halves that
# sigma to ~+/-43 and drops the false-block rate to ~1%. Cost is ~7 minutes on a block whose
# critical path is item 6, i.e. zero schedule cost.
#
# THROWAWAY GAMES. These decks are disjoint from the cell's, no results.csv row is written,
# and the gate cell's elo is explicitly NOT a result and NOT poolable.
# If the gate FAILS: item 2 STOPS and becomes a build task. Do NOT "fix it and keep the games".
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
DIR=$REPO/measurement/lever_menu_20260810
OUT=/mnt/c/carc-shared/lever_menu_20260810
W=${W:-14}
ts() { date +%F_%T; }

echo "[gate2a $(ts)] START (local only, W=$W)"

nice -n 19 bash $REPO/scripts/classical_search/menu_fair_cell.sh "$W" local \
  --sub gate2a_farmgrowthoff --n 32 --band 118900000000 \
  --cand-leaf-json "$DIR/cells/menu_farmgrowthoff_fixed_v1_vs_fairchamp11008.json" --drift \
  --k-dets 8 --sims 1376 --max-iter 8
RC1=$?
echo "[gate2a $(ts)] farm_growth_off micro-cell rc=$RC1"

nice -n 19 bash $REPO/scripts/classical_search/menu_fair_cell.sh "$W" local \
  --sub gate2a_farmbaseoff --n 64 --band 118900001000 \
  --cand-leaf-json "$DIR/cells/menu_farmbaseoff_fixed_v1_vs_fairchamp11008.json" --drift \
  --k-dets 8 --sims 1376 --max-iter 8
RC2=$?
echo "[gate2a $(ts)] farm_base_off SIGN CONTROL rc=$RC2"

$PY $REPO/scripts/classical_search/menu_gate_check.py \
  --gate-dir "$OUT/gate2a_farmgrowthoff" \
  --control-dir "$OUT/gate2a_farmbaseoff" \
  --out "$DIR/GATE2a_VERDICT.json"
GRC=$?
echo "[gate2a $(ts)] gate check rc=$GRC (0 = PASS, block B cleared)"
exit $GRC
