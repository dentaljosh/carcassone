#!/bin/bash
# PHASE-SEAM GATE (d) — the one acceptance gate commit 549c0d1 left UNKNOWN.
#
# 549c0d1 (worktree agent-a195cbd889c3187bf) is byte-identity GREEN on every direct measure:
#   leaf hash a36d2e15a3b3d71d unchanged · golden 194 passed 0 mismatches ·
#   reconcile --configs all 0/3325532 · reconcile --configs phase 0/3199556 (knob ON) ·
#   cargo test 103 passed · doc_lint 0.
# What it never established is that the FULL PYTEST SUITE is no worse than before: its runs
# died without a summary and the failures it glimpsed were never baselined. This script does
# exactly the missing comparison and nothing else.
#
# METHOD (deliberately the cheap direction):
#   1. Run the full suite ONCE against the seam worktree -> collect failing test IDs.
#   2. Run ONLY those IDs against the main tree (no phase seam) -> pre-existing or not.
#   3. Any ID failing on the seam but PASSING on main is NOVEL => the phase arm is a FULL STOP.
#
# TWO INVOCATION RULES, both learned the hard way and both mandatory:
#   * SERIAL, never xdist. virtual_score_v2.DEFAULT_CONFIG is env-latched at import, so
#     parallel workers can manufacture failures serial execution would not — an xdist diff
#     is inadmissible evidence.
#   * `tests/` and `tests/rustport/` run SEPARATELY: prod_leaf_env hard-raises at collection
#     if imported after carcassonne_ai. That is the house invocation, not a failure to triage.
#
# The seam's Rust half lives in a scratch wheel that is PREPENDED to PYTHONPATH; the shared
# site-packages carc_rs is never touched, so the main-tree baseline leg is genuinely stock.
set -u
REPO=/home/doctor/projects/carcassone
WT=$REPO/.claude/worktrees/agent-a195cbd889c3187bf
PY=$REPO/.venv/bin/python
# Wheel lives under the measurement dir, NOT /tmp — the 2026-08-09 06:51 dirty reboot wiped
# the session scratchpad mid-chain and the gate false-blocked on the missing artifact.
WHEEL_DIR=/home/doctor/projects/carcassone/measurement/curve_shape_scope_20260809/PHASE_SEAM_GATE/wheels
WHEEL=$WHEEL_DIR/carc_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl
if [ ! -f "$WHEEL" ]; then
  echo "[gate $(ts)] seam wheel absent; rebuilding from the seam worktree (maturin build, release)"
  /home/doctor/projects/carcassone/.venv/bin/maturin build --release \
    -m /home/doctor/projects/carcassone/.claude/worktrees/agent-a195cbd889c3187bf/rust/carc/carc-py/Cargo.toml \
    -o "$WHEEL_DIR" || { echo "[gate $(ts)] FATAL: wheel rebuild failed"; exit 2; }
fi
SHADOW=$SCRATCH/carc_rs_shadow
OUT=$REPO/measurement/curve_shape_scope_20260809/PHASE_SEAM_GATE
mkdir -p "$OUT"
ts() { date +%F_%T; }

echo "[gate $(ts)] unpacking the seam's carc_rs wheel to a shadow dir (site-packages untouched)"
rm -rf "$SHADOW"; mkdir -p "$SHADOW"
$PY -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$WHEEL" "$SHADOW" || {
  echo "[gate $(ts)] FATAL: could not unpack $WHEEL"; exit 2; }

run_suite() {  # $1=label  $2=tree  $3=extra PYTHONPATH prefix ("" for stock)
  local label="$1" tree="$2" pre="${3:-}"
  local pp="$tree/src:$tree/engine"
  [ -n "$pre" ] && pp="$pre:$pp"
  echo "[gate $(ts)] === $label suite (serial) ==="
  ( cd "$tree" && PYTHONPATH="$pp" nice -n 19 "$PY" -m pytest tests/ -q -p no:randomly \
      -p no:cacheprovider --ignore=tests/rustport -rf ) > "$OUT/${label}_main.txt" 2>&1
  echo "[gate $(ts)] $label tests/ rc=$?"
  ( cd "$tree" && PYTHONPATH="$pp" nice -n 19 "$PY" -m pytest tests/rustport -q -p no:randomly \
      -p no:cacheprovider -rf ) > "$OUT/${label}_rustport.txt" 2>&1
  echo "[gate $(ts)] $label tests/rustport rc=$?"
  # verify we imported what we think we imported
  ( cd "$tree" && PYTHONPATH="$pp" "$PY" -c "
import carcassonne_ai, sys
print('carcassonne_ai:', carcassonne_ai.__file__)
try:
    import carc_rs; print('carc_rs:', carc_rs.__file__)
except Exception as e: print('carc_rs import failed:', e)
" ) >> "$OUT/${label}_provenance.txt" 2>&1
}

collect_ids() {  # failing/erroring IDs from a pytest -rf short summary
  grep -hE '^(FAILED|ERROR) ' "$@" 2>/dev/null | awk '{print $2}' | sed 's/[[:space:]]*$//' | sort -u
}

run_suite seam "$WT" "$SHADOW"
collect_ids "$OUT/seam_main.txt" "$OUT/seam_rustport.txt" > "$OUT/seam_failures.txt"
NF=$(wc -l < "$OUT/seam_failures.txt")
echo "[gate $(ts)] seam-side failing/erroring IDs: $NF"

if [ "$NF" = "0" ]; then
  echo "[gate $(ts)] VERDICT: GREEN — full suite clean on the seam worktree."
  echo GREEN > "$OUT/VERDICT"; exit 0
fi

echo "[gate $(ts)] === replaying the SAME ids on the main tree (no phase seam) ==="
: > "$OUT/base_replay.txt"
while read -r id; do
  [ -z "$id" ] && continue
  ( cd "$REPO" && nice -n 19 "$PY" -m pytest "$id" -q -p no:randomly -p no:cacheprovider ) \
      > "$OUT/_one.txt" 2>&1
  rc=$?
  echo "$rc  $id" >> "$OUT/base_replay.txt"
done < "$OUT/seam_failures.txt"

# rc != 0 on base => the failure is pre-existing. rc == 0 on base => NOVEL to the seam.
awk '$1 == 0 {sub(/^[0-9]+[[:space:]]+/, ""); print}' "$OUT/base_replay.txt" > "$OUT/novel_failures.txt"
NN=$(wc -l < "$OUT/novel_failures.txt")
echo "[gate $(ts)] IDs failing on the seam but PASSING on main (novel): $NN"
if [ "$NN" = "0" ]; then
  echo "[gate $(ts)] VERDICT: GREEN — every seam-side failure reproduces on main (pre-existing)."
  echo GREEN > "$OUT/VERDICT"
else
  echo "[gate $(ts)] VERDICT: FAIL — novel failures introduced by the seam:"
  cat "$OUT/novel_failures.txt"
  echo FAIL > "$OUT/VERDICT"
fi
echo "[gate $(ts)] artifacts in $OUT"
