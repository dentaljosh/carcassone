#!/usr/bin/env bash
# OM-M1 — build carc_rs from THIS worktree into a SHADOW install dir.
#
# ⛔ NEVER touches the shared .venv: tonight's rounds pin the installed wheel,
# and swapping it mid-round would change the code under live rev-pinned cells
# (memory `feedback_worktree_isolation_live_tree`). The wheel is installed with
# `pip install --target` into a scratch directory that the harness prepends to
# PYTHONPATH.
#
# Usage: scripts/omm1/build_wheel.sh <scratch_dir>
set -euo pipefail

SP="${1:?usage: build_wheel.sh <scratch_dir>}"
WT=/home/doctor/projects/carcassone/.claude/worktrees/agent-a6de39b2de1b23a94
VENV=/home/doctor/projects/carcassone/.venv

mkdir -p "$SP/wheel" "$SP/pyext_rel"
cd "$WT/rust/carc/carc-py"

export CARGO_TARGET_DIR="$SP/omm1_target_rel"
export PATH="/home/doctor/.cargo/bin:$PATH"

echo "=== maturin build --release (nice 19, -j 8) ==="
nice -n 19 "$VENV/bin/maturin" build --release --out "$SP/wheel" -j 8

WHL=$(ls -t "$SP"/wheel/*.whl | head -1)
echo "=== wheel: $WHL"
sha256sum "$WHL"

echo "=== pip install --target $SP/pyext_rel (SHADOW, not the venv) ==="
nice -n 19 "$VENV/bin/pip" install --quiet --no-deps --force-reinstall \
    --target "$SP/pyext_rel" "$WHL"

echo "=== import check (shadow dir first on PYTHONPATH) ==="
PYTHONPATH="$SP/pyext_rel" "$VENV/bin/python" - <<'PY'
import carc_rs
print("carc_rs        :", carc_rs.__file__)
print("has legs API   :", hasattr(carc_rs, "tiearb_arbitrate_legs"))
PY
echo "=== venv wheel UNTOUCHED (sanity) ==="
"$VENV/bin/python" -c "import carc_rs; print('venv carc_rs   :', carc_rs.__file__)"
