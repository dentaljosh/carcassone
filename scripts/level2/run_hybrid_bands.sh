#!/usr/bin/env bash
# L2 hybrid-handoff bands (measurement only). Cheapest-decisive-first:
#   Phase 1 (this script): hybrid:K:3200 vs iter8, n=N paired, K in {2,3,5,8} +
#     compute-sanity hybrid:5:800 vs iter8. All share ONE fresh band (seed-start)
#     so decks match across agents. Phase 2 (hybrid vs heur@3200) is launched
#     separately, only for K that beat iter8.
#
# Box-portable: pass SHARE as $1 (local 5800x = /mnt/c/carc-shared,
# xeon/laptop = /mnt/carc-shared). nice -19 per the shared-box rule.
#
# Usage:
#   scripts/level2/run_hybrid_bands.sh /mnt/c/carc-shared 200 14 [--shared-claim]
set -euo pipefail

SHARE="${1:?pass the share mount path}"
N="${2:-200}"
W="${3:-14}"
EXTRA="${4:-}"   # e.g. --shared-claim

CKPT="$SHARE/flywheel_residual_attempt2/ckpt/iter8.pt"
OUT="$SHARE/level2_hybrid"
SEED=3400000000          # fresh band "b340", shared across all agents
DEV="${CARC_DEVICE:-cuda}"

# v2.7 production leaf env (the script also setdefaults these, but be explicit)
export CARCASSONNE_V25_CAP=12
export CARCASSONNE_V25_DROP_THREE_OPEN=1
export CARCASSONNE_USE_FLAT_LEAF=1
export CARCASSONNE_V25_VALUE_BLEND=0

run() {  # $1=agent_a  $2=subdir
  echo "=== $1 vs iter8  (n=$N, band b340) ==="
  nice -n 19 python -u scripts/level2/eval_hybrid_handoff.py \
    --agent-a "$1" --agent-b iter8 --ckpt "$CKPT" \
    --n "$N" --paired --seed-start "$SEED" --workers "$W" --device "$DEV" \
    --out-root "$OUT" --out-subdir "$2" $EXTRA
}

run "hybrid:2:3200" "hybridK2h3200__vs__iter8_b340_n${N}"
run "hybrid:3:3200" "hybridK3h3200__vs__iter8_b340_n${N}"
run "hybrid:5:3200" "hybridK5h3200__vs__iter8_b340_n${N}"
run "hybrid:8:3200" "hybridK8h3200__vs__iter8_b340_n${N}"
# compute sanity: shallower heur endgame
run "hybrid:5:800"  "hybridK5h800__vs__iter8_b340_n${N}"

echo "=== Phase 1 done. Summaries: ==="
for d in hybridK2h3200 hybridK3h3200 hybridK5h3200 hybridK8h3200 hybridK5h800; do
  echo "--- $d ---"; cat "$OUT/${d}__vs__iter8_b340_n${N}/summary.json" 2>/dev/null || echo "(no summary)"
done
