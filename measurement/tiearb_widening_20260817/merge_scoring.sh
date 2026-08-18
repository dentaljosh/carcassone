#!/usr/bin/env bash
# =============================================================================
# tiearb_widening_20260817 — MERGE the two boxes' per-chunk scoring output into
# the EXACT layout the frozen READ_RULE.md addresses.
#
#   merge_scoring.sh [stratum ...] [--dry-run]
#     stratum : s1 | s2   (omitted => $STRATUM_ORDER from ALLOCATION.conf)
#
# RUN IT ON THE LOCAL BOX, and only after BOTH boxes' chunks have landed on the
# share. The laptop writes to /mnt/carc-shared, the local box reads the SAME
# files at /mnt/c/carc-shared — the merge is a file copy, there is no transfer.
#
#   from : $SHARE_RUN/chunks/<stratum>/chunk<k>/<judge>/walled/leg<N>/records/<rid>.json
#   to   : $SHARE_RUN/<stratum>/<judge>/walled/leg<N>/records/<rid>.json
#          $SHARE_RUN/<stratum>/<judge>/walled/leg<N>/manifest.json   (merged)
#          shared_run/RUN_MANIFEST_{S1,S2}.json                       (merged)
#
# `build_widening_corpus.sh 6` then copies every manifest.json from
# $SHARE_RUN/<stratum>/ back to shared_run/legs/<stratum>/… — the address
# G-SALT / G-M / G-BACKEND / G-PREFIX read. G-CRN's per-record fallback reads
# the records tree this script assembles, directly on the share.
#
# ⚠️ FAILS LOUDLY on any gap or duplicate. Every rid the CORPUS plan places on a
# leg must appear exactly once, for BOTH judges. Exit 1 + the offending rids.
#
# ⚠️ NEVER OPENS A RECORD. rids come from FILE NAMES; bytes are copied. No value,
# mean, sd, Δ or CI passes through. Per-leg `summary.json` (which DOES carry
# outcome statistics) is copied verbatim to `summary_chunk<k>.json` and is never
# parsed — a merged summary would be a computed statistic this layer has no
# licence to produce.
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONF="$HERE/WORKERS.conf"
[ -f "$CONF" ] || CONF="$HERE/../WORKERS.conf"
[ -f "$CONF" ] || { echo "[merge] FATAL: WORKERS.conf not found" >&2; exit 2; }
# shellcheck disable=SC1090
. "$CONF"
ALLOC="$HERE/ALLOCATION.conf"
[ -f "$ALLOC" ] || { echo "[merge] FATAL: $ALLOC missing" >&2; exit 2; }
# shellcheck disable=SC1090
. "$ALLOC"

for v in SHARE_RUN_LOCAL REPO_LOCAL RUN_ID STRATUM_ORDER; do
  [ -n "${!v:-}" ] || { echo "[merge] FATAL: $CONF/$ALLOC does not set $v" >&2; exit 2; }
done

REPO="$REPO_LOCAL"
SHARE_RUN="$SHARE_RUN_LOCAL"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "[merge] FATAL: no venv python at $PY" >&2; exit 2; }

DRY=""
STRATA=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY="--dry-run" ;;
    s1|s2)     STRATA="$STRATA $a" ;;
    *) echo "[merge] FATAL: bad argument '$a' (s1 | s2 | --dry-run)" >&2; exit 2 ;;
  esac
done
[ -n "${STRATA// /}" ] || STRATA="$STRATUM_ORDER"

cd "$REPO" || { echo "[merge] FATAL: cannot cd to '$REPO'" >&2; exit 1; }

CAMPAIGN="$REPO/measurement/$RUN_ID"
RUN_DIR="$CAMPAIGN/shared_run"
LOGS="$CAMPAIGN/logs"
mkdir -p "$LOGS"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOGS/merge_$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

echo "[merge] $(date -Is) strata='$STRATA' dry='${DRY:-no}'"
echo "[merge] share-run=$SHARE_RUN  log=$LOG"
[ -d "$SHARE_RUN" ] || { echo "[merge] FATAL: '$SHARE_RUN' absent — run this on the LOCAL box." >&2; exit 1; }

rc_all=0
for S in $STRATA; do
  UPPER="$(echo "$S" | tr '[:lower:]' '[:upper:]')"
  CHUNKS_ROOT="$SHARE_RUN/chunks/$S"
  OUT_DIR="$SHARE_RUN/$S"
  POSDIR="$RUN_DIR/corpus/positions_$S"

  [ -d "$CHUNKS_ROOT" ] || { echo "[merge] $S: no chunk output at $CHUNKS_ROOT — skip"; continue; }
  [ -d "$POSDIR" ] || { echo "[merge] FATAL: $S: corpus positions dir $POSDIR absent" >&2; rc_all=1; continue; }

  echo "[merge] ===== $S: $CHUNKS_ROOT -> $OUT_DIR"
  CMD=("$PY" -u "$CAMPAIGN/merge_legs.py"
       --stratum "$S"
       --chunks-root "$CHUNKS_ROOT"
       --out-dir "$OUT_DIR"
       --positions-dir "$POSDIR"
       --manifests-dir "$CAMPAIGN/chunks/manifests"
       --run-manifest-out "$RUN_DIR/RUN_MANIFEST_${UPPER}.json"
       --report "$CAMPAIGN/MERGE_REPORT_${S}.json")
  [ -n "$DRY" ] && CMD+=("$DRY")
  printf '[merge] EXACT:'; printf ' %q' "${CMD[@]}"; echo
  "${CMD[@]}"
  rc=$?
  echo "[merge] $S rc=$rc"
  [ "$rc" -ne 0 ] && rc_all=$rc
done

if [ "$rc_all" -eq 0 ] && [ -z "$DRY" ]; then
  echo "=============================================================================="
  echo "  ✅ merge COMPLETE for '$STRATA' — every rid present exactly once, both judges."
  echo "  Next: scripts/tiletie/build_widening_corpus.sh 6    (leg-manifest copy-back"
  echo "        to shared_run/legs/<stratum>/… — the address the READ_RULE reads)"
  echo "=============================================================================="
fi

echo "[merge] DONE rc_all=$rc_all $(date -Is)"
exit "$rc_all"
