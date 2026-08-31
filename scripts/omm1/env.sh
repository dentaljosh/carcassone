#!/usr/bin/env bash
# OM-M1 — the one place the run's paths and environment are defined.
# Sourced by run_frame.sh / run_gate.sh so an invocation needs no arguments.
#
# ⛔ The wheel: a SHADOW `pip install --target` build from THIS worktree. The
# shared .venv is never touched — tonight's rounds pin the installed wheel and
# swapping it would change the code under live rev-pinned cells (memory
# `feedback_worktree_isolation_live_tree`).

WT=/home/doctor/projects/carcassone/.claude/worktrees/agent-a6de39b2de1b23a94
MAIN=/home/doctor/projects/carcassone
VENV="$MAIN/.venv"
SP=/tmp/claude-1000/-home-doctor-projects-carcassone/d538aba0-bcf8-4b08-a01a-684a1ae3c7eb/scratchpad
OUT="$WT/measurement/omm1_refuter_gate_20260830"
LOGDIR="$OUT/logs"

export PYTHONPATH="$SP/pyext_rel"
# Read-only fallback for the UNTRACKED tiearb2_850 corpus (DEVIATIONS OM-D3).
export OMM1_MAIN_TREE="$MAIN"
OMM1_WHEEL_FILE="$(ls -t "$SP"/wheel/*.whl | head -1)"
export OMM1_WHEEL_FILE
OMM1_WHEEL_SHA256="$(sha256sum "$OMM1_WHEEL_FILE" | cut -d' ' -f1)"
export OMM1_WHEEL_SHA256

mkdir -p "$LOGDIR"
