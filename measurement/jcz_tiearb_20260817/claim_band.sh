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
#
# =============================================================================
# ⭐ THE BAND_FLOOR ASSERTION (added for the re-run; DISCLOSURE §4.3).
#
# The first run's band 133000000000 is SPENT and retires from confirmatory use.
# This run must land on 134000000000 and on nothing else — a surprise band would
# either collide with a spent one or silently move the run onto ground the
# registry has not reserved for it.
#
# ⚠️ `claim_next_band.py` HAS NO `--floor` FLAG. Read it: `next_free_band()` takes
# a `floor` parameter, but `main()` calls it as `next_free_band(existing)` and
# argparse exposes no `--floor`. So the floor CANNOT be requested; the allocation
# is always registry-high-water + 1e9. (High-water is 133000000000, so the
# allocation IS 134000000000 == BAND_FLOOR — but that is a fact to be VERIFIED,
# not assumed.)
#
# So this script PEEKS with `--dry-run` first — which appends nothing and touches
# no file — and ABORTS if the claimer would hand back anything other than
# BAND_FLOOR. Only then does it make the real claim, and it re-checks the value
# that came back. Fail-closed in both directions: a band that is not BAND_FLOOR
# is never appended, and a band that somehow came back wrong is never returned to
# the caller as if it were fine.
#
# On RESUME the sentinel already holds the band, the claimer short-circuits on it,
# and both the peek and the claim return that memoized value — which must still
# equal BAND_FLOOR, so a resume against a stale sentinel is caught too.
# =============================================================================
set -euo pipefail
. "$(dirname "$0")/WORKERS.conf"

PY="$REPO_LOCAL/.venv/bin/python"
CLAIMER="$REPO_LOCAL/scripts/classical_search/claim_next_band.py"

[ -x "$PY" ]      || { echo "FATAL: no venv python at $PY" >&2; exit 1; }
[ -f "$CLAIMER" ] || { echo "FATAL: no claim script at $CLAIMER" >&2; exit 1; }

: "${BAND_FLOOR:?FATAL: BAND_FLOOR is not set in WORKERS.conf}"
: "${BAND_TAG:?FATAL: BAND_TAG is not set in WORKERS.conf}"
case "$BAND_FLOOR" in ''|*[!0-9]*) echo "FATAL: BAND_FLOOR must be numeric, got '$BAND_FLOOR'" >&2; exit 1 ;; esac

mkdir -p "$RUN_DIR"

NOTES="RE-RUN. The first attempt on band 133000000000 was VOIDED U-UNREADABLE by READ_RULE \
G-TOOL conjunct 2 (our_git_rev mixed WITHIN both cells: two docs-only commits landed mid-run \
and our_git_rev is stamped per record at record-write time). No bar was moved and no strength \
statistic from that run is quotable; see measurement/$RUN_ID/DISCLOSURE.md. 133000000000 is \
SPENT and retires from confirmatory use. This re-run runs under a TOTAL COMMIT FREEZE \
(measurement/$RUN_ID/FREEZE.md) and tags every artifact '$BAND_TAG' so it cannot collide with \
the voided run, whose artifacts are preserved untouched as the audit trail. \
Two deck-paired cells on ONE band and ONE deck set. \
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

run_claimer() {
  "$PY" "$CLAIMER" \
    --sentinel "$BAND_SENTINEL" \
    --label "$RUN_ID" \
    --tier claim \
    --evidence "measurement/$RUN_ID/DESIGN.md" \
    --notes "$NOTES" \
    "$@"
}

# ---- 1. PEEK. `--dry-run` appends nothing and creates no sentinel. -----------
PEEK_OUT="$(run_claimer --dry-run "$@")" \
  || { echo "FATAL: the dry-run peek failed — refusing to claim blind" >&2; exit 1; }
PEEK_BAND="$(printf '%s\n' "$PEEK_OUT" | tail -1)"

case "$PEEK_BAND" in ''|*[!0-9]*)
  echo "FATAL: the dry-run peek returned no numeric band (got '$PEEK_BAND')" >&2
  printf '%s\n' "$PEEK_OUT" | sed 's/^/    [peek] /' >&2
  exit 1 ;;
esac

if [ "$PEEK_BAND" != "$BAND_FLOOR" ]; then
  {
    echo "!!! BAND_FLOOR ASSERTION FAILED — NOTHING WAS APPENDED TO THE REGISTRY."
    echo "!!!   claim_next_band.py would allocate : $PEEK_BAND"
    echo "!!!   WORKERS.conf BAND_FLOOR expects   : $BAND_FLOOR"
    echo "!!!   sentinel                          : $BAND_SENTINEL"
    echo "!!!"
    echo "!!! The claimer has NO --floor flag, so this cannot be forced — it always"
    echo "!!! returns registry-high-water + 1e9, or the sentinel's memoized value."
    echo "!!! Either the registry moved (someone else claimed 134000000000), or the"
    echo "!!! sentinel is stale, or BAND_FLOOR in WORKERS.conf is out of date."
    echo "!!! RESOLVE IT DELIBERATELY. Do not 'just take whatever it gives' — band"
    echo "!!! identity is load-bearing (CLAUDE.md: a band that influenced a decision"
    echo "!!! retires from confirmatory use, and 133000000000 already has)."
    echo "!!! The peek output was:"
    printf '%s\n' "$PEEK_OUT" | sed 's/^/!!!   /'
  } >&2
  exit 26
fi

# ---- 2. THE REAL CLAIM (or the caller's own --dry-run, passed through). ------
OUT="$(run_claimer "$@")" || { echo "FATAL: claim_next_band.py failed" >&2; exit 1; }
BAND="$(printf '%s\n' "$OUT" | tail -1)"
if [ "$BAND" != "$BAND_FLOOR" ]; then
  echo "FATAL: the claimer returned band '$BAND' but BAND_FLOOR is $BAND_FLOOR." >&2
  echo "FATAL: the registry may now carry a row for a band this run will NOT play —" >&2
  echo "FATAL: inspect governance/BAND_REGISTRY.csv and $BAND_SENTINEL by hand." >&2
  exit 26
fi

# stdout, unchanged contract: the band is the LAST line.
printf '%s\n' "$OUT"
