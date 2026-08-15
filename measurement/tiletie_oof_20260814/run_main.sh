#!/usr/bin/env bash
# TILE-TIE OUT-OF-FAMILY RE-PRICING -- the main read.
#
# DESIGN §0.A: the committed seeded permutation is cut into CHUNKS and the chunks
# run STRICTLY SEQUENTIALLY, because load_positions_jsonl sorts by root_id and a
# line-order prefix would be stratum-biased. Any number of COMPLETED chunks is an
# unbiased read at its realized n.
#
# Resumable: a chunk with DONE_CHUNK<k> is skipped, and run_tiletie passes
# --resume to the pilot, whose unit of done-ness is records/<rid>.json.
#
# Usage: run_main.sh [N_CHUNKS]      (default 4 -- DESIGN §0.A)
set -uo pipefail
W=/home/doctor/projects/carcassone/.claude/worktrees/agent-a1badefaaed4b6d69
cd "$W"
M=$W/measurement/tiletie_oof_20260814
PY=/home/doctor/projects/carcassone/.venv/bin/python
SHARE=/mnt/c/carc-shared/tiletie_oof_20260814
NCH=${1:-4}
WORKERS=${WORKERS:-30}

export CARC_SRC_ROOT=/home/doctor/projects/carcassone/src   # main tree: carries the cy .so
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

echo "[main] $(date -Is) chunks=$NCH workers=$WORKERS"

for k in $(seq 1 "$NCH"); do
  if [ -f "$M/DONE_CHUNK$k" ]; then
    echo "[main] chunk$k already DONE -- skipping"
    continue
  fi
  echo "[main] ===== chunk$k start $(date -Is)"
  nice -n 19 "$PY" scripts/tiletie/run_tiletie.py \
    --positions-dir "$M/positions_chunk$k" \
    --judges tier1-greedy \
    --workers "$WORKERS" \
    --out-root "$SHARE/chunk$k" \
    --logs-dir "$M/logs" \
    --gate-out "$M/GATE_BACKEND_RECHECK_chunk$k.json" \
    --manifest-out "$M/RUN_MANIFEST_chunk$k.json" \
    --yes
  rc=$?
  echo "[main] ===== chunk$k rc=$rc $(date -Is)"
  if [ "$rc" -ne 0 ]; then
    echo "[main] chunk$k FAILED (rc=$rc) -- stopping the chain; completed chunks are"
    echo "[main] still an unbiased read (DESIGN §0.A). Re-run this script to resume."
    exit "$rc"
  fi
  touch "$M/DONE_CHUNK$k"
done

touch "$M/DONE_MAIN"
echo "[main] ALL CHUNKS DONE $(date -Is)"
