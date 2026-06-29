#!/bin/bash
set -e
cd /home/doctor/projects/carcassone
PY=.venv/bin/python
D=measurement/post_search_residual/data
echo "=== PHASE B GEN $(date) ==="
nice -n 19 $PY scripts/post_search_residual/gen_mcts_selfplay.py --n-games 400 --workers 16 --out $D/games_mcts.jsonl
echo "=== PHASE B BUILD $(date) ==="
nice -n 19 $PY scripts/post_search_residual/build_adaptive_dataset.py --roots-source mcts --n 12000 --workers 24 --out $D/roots_mcts.jsonl
echo "=== PHASEB_DONE $(date) ==="
