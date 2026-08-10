#!/bin/bash
# Part C ATTEMPT 2 — fresh band 1.16e11 after the band-1.15e11 wiring-gate false-fire.
# See PREREG_DRAFT.md AMENDMENT 1 (2026-08-10) and BAND_REGISTRY rows 1.15e11 / 1.16e11.
# Refuses to start while the voided attempt's processes are still alive.
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
DIR=$REPO/measurement/curve_shape_scope_20260809
LOGS=$DIR/logs
SHARE=/mnt/c/carc-shared
ts() { date +%F_%T; }

if pgrep -f "[e]val_fair_puct|[c]urvephase_ladder_launcher|[n]ight_chain" > /dev/null; then
  echo "[relaunch $(ts)] REFUSING: voided attempt still running. Kill it first."
  exit 1
fi

# Void the band-1.15e11 cells (prereg 6.1: abort, no cell counts). Records preserved.
VOID="$SHARE/curvephase_ladder_VOID_band115_wiring"
mkdir -p "$VOID"
for d in "$SHARE"/curvephase_ladder/cp_*; do
  [ -d "$d" ] && mv "$d" "$VOID/" && echo "[relaunch $(ts)] voided $(basename $d)"
done
[ -f "$DIR/PROGRESS_phase.tsv" ] && mv "$DIR/PROGRESS_phase.tsv" "$DIR/PROGRESS_phase_VOID_band115.tsv"

echo "[relaunch $(ts)] launching Part C attempt 2 on band 116000000000, W=14 local"
nice -n 19 bash $REPO/scripts/classical_search/curvephase_ladder_launcher.sh 14 local \
    --band 116000000000 > "$LOGS/cp_local_band116.log" 2>&1
echo "[relaunch $(ts)] launcher rc=$?"

$PY $REPO/scripts/classical_search/analyze_curvephase.py --n-expected 200 \
    --out "$DIR/READOUT_partC.json" > "$LOGS/readout_partC.txt" 2>&1
echo "[relaunch $(ts)] Part C verdict: $($PY -c "import json;print(json.load(open('$DIR/READOUT_partC.json'))['verdict'])" 2>/dev/null)"
echo "[relaunch $(ts)] attempt 2 finished"
