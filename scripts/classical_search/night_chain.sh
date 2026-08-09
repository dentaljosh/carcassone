#!/bin/bash
# OVERNIGHT CHAIN — Part A finishes, then the phase-seam gate decides whether Part C runs.
#
# Order is forced by the ruling of record:
#   1. Part A (curvature probe) owns the boxes until its conductor exits.
#   2. THEN, on a quiet box, the phase-seam gate (d) runs: full suite on the seam worktree,
#      failing IDs replayed on main. That comparison is inadmissible if anything else is
#      competing for the box, which is why it cannot start earlier.
#   3. GREEN  -> merge 549c0d1 and run the Part C beta ladder, then write its readout.
#      FAIL   -> the phase arm is a FULL STOP: no merge, no cell, and a marker file is left
#               for the write-up. Part A's close-out is unaffected either way.
#
# This script NEVER promotes anything and never edits governance/PRODUCTION.yaml.
# Resume: every fleet leg is --shared-claim, so re-running this after a crash resumes.
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
DIR=$REPO/measurement/curve_shape_scope_20260809
LOGS=$DIR/logs
GATE_OUT=$DIR/PHASE_SEAM_GATE
ts() { date +%F_%T; }
mkdir -p "$LOGS"

echo "[night $(ts)] waiting for the Part-A conductor to exit..."
while pgrep -f "curveshape_conductor.sh" > /dev/null 2>&1; do sleep 60; done
echo "[night $(ts)] Part A conductor has exited."

# Part A readout (idempotent; the conductor writes one too, this re-runs it on final state)
$PY $REPO/scripts/classical_search/analyze_curveshape.py --n-expected 400 \
    --out "$DIR/READOUT_partA.json" > "$LOGS/readout_partA.txt" 2>&1
echo "[night $(ts)] Part A verdict: $($PY -c "import json;print(json.load(open('$DIR/READOUT_partA.json'))['verdict'])" 2>/dev/null)"

if [ -f "$DIR/ABORTED_GATE_FAILED" ]; then
  echo "[night $(ts)] Part A aborted at its own wiring gate; not proceeding to the phase arm."
  exit 2
fi

# ---- wait for genuine quiet before the timing/consistency-sensitive gate ----
echo "[night $(ts)] waiting for the boxes to go quiet before the phase-seam gate..."
while [ "$(ps -eo args | grep -c '[e]val_fair_puct')" -gt 0 ]; do sleep 30; done
echo "[night $(ts)] quiet. Running phase-seam gate (d)."

# If a verdict already exists (e.g. the gate ran on ANOTHER box after the local one kept
# dirty-crashing mid-suite — 2026-08-09, crashes #4 and #5 both killed it), don't re-run 3h.
if [ ! -f "$GATE_OUT/VERDICT" ]; then
  nice -n 19 bash $REPO/scripts/classical_search/phase_seam_gate.sh > "$LOGS/phase_gate.log" 2>&1
fi
V=$(cat "$GATE_OUT/VERDICT" 2>/dev/null || echo MISSING)
echo "[night $(ts)] phase-seam gate verdict: $V"

if [ "$V" != "GREEN" ]; then
  echo "[night $(ts)] PHASE ARM IS A FULL STOP. 549c0d1 stays unmerged; no phase cell runs."
  : > "$DIR/PHASE_ARM_BLOCKED"
  exit 3
fi

echo "[night $(ts)] merging the phase seam (gate green)"
git -C "$REPO" merge --no-ff worktree-agent-a195cbd889c3187bf -m \
"Merge the DEFAULT-OFF phase multiplier (549c0d1): Part C's leaf seam

Gate (d) -- the full pytest suite -- was the one acceptance gate 549c0d1 left
UNKNOWN. It is now established by the comparison the seam agent named as missing:
the full suite run serially against the seam worktree, and every failing ID
replayed on the main tree. All failures reproduce on main, i.e. pre-existing.
Artifacts: measurement/curve_shape_scope_20260809/PHASE_SEAM_GATE/.

The direct byte-identity gates were already green at commit time: leaf hash
a36d2e15a3b3d71d unchanged, golden 194/0 mismatches, reconcile --configs all
0/3325532, reconcile --configs phase 0/3199556 with the knob ON, cargo 103.

Default-off is byte-identical BY CONSTRUCTION: beta==0.0 takes an early branch
through the unmodified expression on every substrate, and the branch keys on beta
alone so a stray norm cannot perturb the champion.

PRODUCTION.yaml untouched. Nothing promoted.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" >> "$LOGS/phase_merge.log" 2>&1
if [ $? -ne 0 ]; then
  echo "[night $(ts)] MERGE FAILED — stopping, phase arm blocked."; : > "$DIR/PHASE_ARM_BLOCKED"; exit 4
fi
echo "[night $(ts)] merged. HEAD=$(git -C $REPO rev-parse --short HEAD)"

# The merged seam changes src/ and the rust crate, so the LAPTOP needs both a code sync and a
# carc_rs rebuild before it can contribute. Rather than risk a half-built helper producing
# games under a manifest that says fixed_v1, Part C runs LOCAL-ONLY. n=200 cells are half the
# size of Part A's, so single-box is affordable; correctness beats wall-clock here.
echo "[night $(ts)] rebuilding the local cython + carc_rs for the merged seam"
( cd "$REPO" && nice -n 19 $PY setup_flat_leaf_cy.py build_ext --inplace ) >> "$LOGS/phase_build.log" 2>&1
# Absolute maturin path: a detached launch does NOT inherit the venv PATH, and a bare
# `maturin` exits 127 — after which the ladder would sweep beta against a STALE carc_rs
# (phase multiplier absent from the substrate) and produce a silent null. Found 2026-08-09.
( cd "$REPO" && nice -n 19 "$REPO/.venv/bin/maturin" develop --release -m rust/carc/carc-py/Cargo.toml ) >> "$LOGS/phase_build.log" 2>&1
BUILD_RC=$?
echo "[night $(ts)] build rc=$BUILD_RC"
if [ "$BUILD_RC" -ne 0 ]; then
  echo "[night $(ts)] FATAL: carc_rs rebuild failed (rc=$BUILD_RC); Part C would run on a stale substrate. STOPPING."
  : > "$DIR/PHASE_ARM_BLOCKED"
  exit 4
fi
$PY -c "
import carc_rs, carcassonne_ai
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG as c
import scripts.classical_search.c5_leaf_override as o
assert getattr(carc_rs, 'SUPPORTS_V29_PHASE', False), 'rebuilt carc_rs lacks SUPPORTS_V29_PHASE - stale substrate'
" >> "$LOGS/phase_build.log" 2>&1 || {
  echo "[night $(ts)] FATAL: post-build import/capability check failed. STOPPING."
  : > "$DIR/PHASE_ARM_BLOCKED"; exit 4; }

echo "[night $(ts)] launching the Part C beta ladder (local only)"
# W=14 (was 30): Joshua is working on the box (2026-08-09 afternoon) — leave headroom.
nice -n 19 bash $REPO/scripts/classical_search/curvephase_ladder_launcher.sh 14 local \
    > "$LOGS/cp_local.log" 2>&1
echo "[night $(ts)] Part C launcher returned rc=$?"

$PY $REPO/scripts/classical_search/analyze_curvephase.py --n-expected 200 \
    --out "$DIR/READOUT_partC.json" > "$LOGS/readout_partC.txt" 2>&1
echo "[night $(ts)] Part C verdict: $($PY -c "import json;print(json.load(open('$DIR/READOUT_partC.json'))['verdict'])" 2>/dev/null)"
echo "[night $(ts)] night chain finished"
