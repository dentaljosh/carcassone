#!/bin/bash
cd /home/doctor/projects/carcassone/.claude/worktrees/agent-a936038f9f56f3351 || exit 1
export PYTHONPATH="$PWD/src:$PWD/engine"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
nice -19 /home/doctor/projects/carcassone/.venv/bin/python -u \
  measurement/omd2_chain_values_20260830/probe_collision.py
