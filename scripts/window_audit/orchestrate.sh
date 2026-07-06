#!/usr/bin/env bash
# Window-audit downstream orchestrator: wait for champion-leaf self-play
# generation, then run the combined overflow audit + the h1600@W31 deep-search
# check on sampled dropped actions. Writes a DONE marker at the end.
set -u
cd /home/doctor/projects/carcassone

export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1

PY=/home/doctor/projects/carcassone/.venv/bin/python
GENLOG=measurement/window_audit/gen_games.log
STAMP=measurement/window_audit/orchestrate.log

echo "[orch] waiting for generation to finish..." > "$STAMP"
while ! grep -qE "wrote [0-9]+ games|Traceback|Error" "$GENLOG" 2>/dev/null; do
  sleep 8
done
echo "[orch] generation done: $(grep -E 'wrote [0-9]+ games' "$GENLOG" | tail -1)" >> "$STAMP"

# --- Combined overflow audit (real archived + generated) ---
echo "[orch] running combined audit..." >> "$STAMP"
CARCASSONNE_WINDOW_AUDIT=1 nice -n 19 "$PY" scripts/window_audit/run_audit.py \
  measurement/post_search_residual/data/games_mcts.jsonl \
  /mnt/c/carc-shared/l23_k4_expand.jsonl \
  measurement/level2/l23_k4_multisource.jsonl \
  measurement/window_audit/gen_games.jsonl \
  --out measurement/window_audit/audit_combined.json >> "$STAMP" 2>&1

# --- Deep-search preference check on sampled dropped actions ---
echo "[orch] running deep-search check (h1600@W31)..." >> "$STAMP"
nice -n 19 "$PY" scripts/window_audit/deep_search_check.py \
  --sample measurement/window_audit/audit_combined_dropped_sample.json \
  --n 20 --sims 1600 \
  --out measurement/window_audit/deep_search_result.json >> "$STAMP" 2>&1

echo "[orch] DONE" >> "$STAMP"
