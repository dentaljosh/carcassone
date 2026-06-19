#!/usr/bin/env bash
# L2 hybrid-handoff Phase 2 (CONDITIONAL — only for K that beat iter8 in Phase 1):
#   hybrid:K:3200 vs heur@3200, n=N paired, SAME fresh band b340 (shared decks).
# This is the champion check. EXPENSIVE: the opponent is a FULL heur@3200 side
# (~36 turns x 3200 sims/game), like Joshua #8. Run only the winning K(s).
#
# Box-portable + shared-claim across boxes. nice -19.
#
# Usage:
#   scripts/level2/run_hybrid_phase2.sh /mnt/c/carc-shared 200 16 "5 8" [--shared-claim]
set -euo pipefail

SHARE="${1:?pass the share mount path}"
N="${2:-200}"
W="${3:-16}"
KS="${4:?pass winning K values, e.g. \"5 8\"}"
EXTRA="${5:-}"

CKPT="$SHARE/flywheel_residual_attempt2/ckpt/iter8.pt"
OUT="$SHARE/level2_hybrid"
SEED=3400000000          # same band b340 as Phase 1 -> shared decks
DEV="${CARC_DEVICE:-cuda}"

export CARCASSONNE_V25_CAP=12
export CARCASSONNE_V25_DROP_THREE_OPEN=1
export CARCASSONNE_USE_FLAT_LEAF=1
export CARCASSONNE_V25_VALUE_BLEND=0

for K in $KS; do
  echo "=== hybrid:${K}:3200 vs heur@3200  (n=$N, band b340) ==="
  nice -n 19 python -u scripts/level2/eval_hybrid_handoff.py \
    --agent-a "hybrid:${K}:3200" --agent-b "heur@3200" --ckpt "$CKPT" \
    --n "$N" --paired --seed-start "$SEED" --workers "$W" --device "$DEV" \
    --out-root "$OUT" --out-subdir "hybridK${K}h3200__vs__heur3200_b340_n${N}" $EXTRA
done
