#!/bin/bash
# F6 pre-gate launcher (worktree-safe PYTHONPATH prefix; see CLAUDE.md worktree rule)
cd "$(dirname "$0")/../.." || exit 1
export PYTHONPATH="$PWD/src:$PWD/engine"
exec /home/doctor/projects/carcassone/.venv/bin/python scripts/analyzer/f6_winprob_pregate.py "$@"
