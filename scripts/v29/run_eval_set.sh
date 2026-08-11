#!/usr/bin/env bash
# Run a set of v2.9 candidates vs v2.8 at a given n / sims. Reusable across waves:
#   Wave-1 verdict:   run_eval_set.sh "A16 Bmild"  400 200
#   Washout check:    run_eval_set.sh "A16 Bmild"  400 800
#   Combination:      run_eval_set.sh "A16+Bmild"  400 200
# Same seed-start as the screen (1e9) => the first 100 deck-pairs are REUSED from the
# n=200 screen (resumable cache hit); only the new pairs are played. Writes to the same
# per-candidate dir, so analyze_screen.py reports the larger n automatically.
cd /home/doctor/projects/carcassone || exit 1
set -uo pipefail
CANDS="${1:?usage: run_eval_set.sh \"CAND...\" N SIMS [seed] [workers]}"
N="${2:?n}"; SIMS="${3:?sims}"; SEED="${4:-1000000000}"; W="${5:-14}"
PY=.venv/bin/python; OUT=/mnt/c/carc-shared/v29_eval
echo "=== EVAL SET START $(date '+%F %H:%M') | n=$N sims=$SIMS W=$W | $CANDS ==="
for C in $CANDS; do
  echo "--- [$C] n=$N sims=$SIMS $(date '+%H:%M') ---"
  nice -n 19 $PY -u scripts/v29/eval_v29_vs_v28.py --candidate "$C" --n "$N" --sims "$SIMS" \
    --paired --workers "$W" --seed-start "$SEED" --out-root "$OUT" 2>&1 | grep -vE "min left\)$"
done
echo "=== EVAL SET DONE $(date '+%F %H:%M') ==="
