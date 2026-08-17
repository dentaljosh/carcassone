#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — CLAIM THE BAND, immediately before game 1 and never
# earlier (DESIGN §5, READ_RULE `G-BAND`).
#
#   claim_band.sh [--dry-run]
#
# IDEMPOTENT BY THE SENTINEL. `claim_next_band.py` reads `$BAND_SENTINEL` first
# and, if it holds a band, re-uses it and touches the registry not at all. So a
# crash resume, a watchdog restart, or an operator re-running launch.sh re-uses
# the SAME band instead of burning a second one — which would also split one
# cell's decks across two bands, the exact cross-band pooling the house forbids.
#
# `--dry-run` is passed straight through: it prints the row it WOULD append,
# prints the band, and appends nothing.
#
# Prints the claimed band on stdout (and nothing else on the last line), so a
# caller can capture it.
# =============================================================================
set -euo pipefail
. "$(dirname "$0")/WORKERS.conf"

PY="$REPO_LOCAL/.venv/bin/python"
CLAIMER="$REPO_LOCAL/scripts/classical_search/claim_next_band.py"

[ -x "$PY" ]      || { echo "FATAL: no venv python at $PY" >&2; exit 1; }
[ -f "$CLAIMER" ] || { echo "FATAL: no claim script at $CLAIMER" >&2; exit 1; }

mkdir -p "$RUN_DIR"

NOTES="Two deck-paired cells on ONE band and ONE deck set. \
CELL A ($CELL_A) = the UNMODIFIED production champion vs JCloisterZone LegacyAiPlayer; \
CELL B ($CELL_B) = the same champion PLUS the tie arbiter \
(B=$TIEARB_B J=$TIEARB_J mode=$TIEARB_MODE salt=$TIEARB_SALT eps=$TIEARB_EPS). \
Both cells: fair PIMC k${K_DETS}x${SIMS}=$(( K_DETS * SIMS )), exact-K $EXACT_K, rust backend, \
rules $RULES_PROFILE + CARCASSONNE_FIX_R9=$FIX_R9, cand_leaf_hash $CHAMP_LEAF_HASH \
(the arbiter moves NO leaf hash). $DECKS decks x 2 seatings = $N_GAMES games per cell. \
PRIMARY STATISTIC is the deck-paired DELTA-OF-MARGINS D = M_B - M_A between the two cells, \
within this band, deck-matched. \
Opponent: JCloisterZone rev $JCZ_REV, tile set $JCZ_TILES, ai class $JCZ_AI_CLASS. \
Prereg: measurement/$RUN_ID/DESIGN.md + READ_RULE.md, both committed before this claim."

exec "$PY" "$CLAIMER" \
  --sentinel "$BAND_SENTINEL" \
  --label "$RUN_ID" \
  --tier claim \
  --evidence "measurement/$RUN_ID/DESIGN.md" \
  --notes "$NOTES" \
  "$@"
