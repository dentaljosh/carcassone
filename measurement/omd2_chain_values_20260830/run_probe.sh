#!/bin/bash
# OM-D2 localisation probe launcher (read-only; nice -19; single process).
cd /home/doctor/projects/carcassone/.claude/worktrees/agent-a936038f9f56f3351 || exit 1
export PYTHONPATH="$PWD/src:$PWD/engine"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
LOG=/tmp/claude-1000/-home-doctor-projects-carcassone/d538aba0-bcf8-4b08-a01a-684a1ae3c7eb/scratchpad/omd2_probe.log
nohup nice -19 /home/doctor/projects/carcassone/.venv/bin/python -u \
  measurement/omd2_chain_values_20260830/probe_witnesses.py > "$LOG" 2>&1 &
disown
echo "launched pid $! log $LOG"
