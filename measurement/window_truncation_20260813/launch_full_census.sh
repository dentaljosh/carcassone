#!/usr/bin/env bash
# launch_full_census.sh — the FULL window-truncation census (DESIGN.md §8), launched by hand
# on 2026-08-13 evening at git 530368de, on BOTH boxes, against the freshly rebuilt carc_rs
# wheel (the one that carries `WindowTruncationError`, F-c).
#
# WHAT IT IS: a thin, box-agnostic wrapper around RUN_CMD.sh — which stays the single source
# of the actual census commands. This file adds only the four things RUN_CMD.sh deliberately
# does not do (they are the scheduler's job, and this launch is not going through the
# scheduler):
#   1. a self-describing LAUNCH_MANIFEST_<box>.json (full resolved config, house rule)
#   2. the CHAIN_STARTED_<box> marker the watchdog's cold-start guard keys on
#   3. a pre-flight that PROVES the wheel under test carries WindowTruncationError
#      (a stale wheel silently changes what this census can see)
#   4. publishing the results to the SHARE when the run ends — the 2026-08-13 11:46 laptop
#      census completed and was then invisible for 10 h because its artifacts existed only
#      in the laptop's own tree. Never again.
#
# ⚠️ FOREGROUND ON PURPOSE. Detaching is the caller's job:
#     local  : setsid nohup nice -n 19 bash <this> ... & disown
#     laptop : nohup systemd-run --user --scope -p MemoryMax=8G bash <this> ... & disown
#
# ⚠️ IT DOES NOT ADJUDICATE. No verdict, no P1/P2/P3 ruling, no band, no results.csv row,
#    no governance touch — DESIGN §6 pre-registers 0 games / no band / no claim.
#
# ENV: WTC_LAUNCH_W   (required) worker count, measured per box — see the manifest
#      WTC_LAUNCH_BOX (required) 'local' | 'laptop'
#      WTC_LAUNCH_NOTE (optional) free text into the manifest
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO" || { echo "cannot cd to repo root $REPO" >&2; exit 9; }

DIR="measurement/window_truncation_20260813"
LOGS="$DIR/logs"
PY="$REPO/.venv/bin/python"
W="${WTC_LAUNCH_W:?set WTC_LAUNCH_W}"
BOX="${WTC_LAUNCH_BOX:?set WTC_LAUNCH_BOX}"
NOTE="${WTC_LAUNCH_NOTE:-}"
mkdir -p "$LOGS"
say() { echo "[$(date -Is)] launch/$BOX: $*"; }

# --- share, resolved BY SENTINEL exactly like RUN_CMD.sh (both paths exist on the laptop) --
SENT=classical_search/move_agreement_k4_b28e9/roots.jsonl
SHARE=""
for c in /mnt/c/carc-shared /mnt/carc-shared; do   # allow-path
  [ -f "$c/$SENT" ] && { SHARE="$c"; break; }
done
[ -n "$SHARE" ] || { say "FATAL: no share candidate carries the sentinel $SENT"; exit 10; }

# --- pre-flight: the wheel under test -------------------------------------------------------
WHEEL=$("$PY" -c "import carc_rs;print(carc_rs.__file__)" 2>/dev/null) || { say "FATAL: carc_rs import failed"; exit 15; }
WTE=$("$PY" -c "import carc_rs;print(hasattr(carc_rs,'WindowTruncationError'))" 2>/dev/null)
if [ "$WTE" != "True" ]; then
  say "FATAL: carc_rs at $WHEEL has NO WindowTruncationError - that is the PRE-F-c wheel."
  say "       Refusing to run: a stale wheel silently changes what this census can see."
  exit 16
fi
GITREV=$(git -C "$REPO" rev-parse HEAD)
say "preflight ok - git $GITREV, wheel $WHEEL, WindowTruncationError=$WTE, share $SHARE, W=$W"

# --- markers + manifest ---------------------------------------------------------------------
echo "$(date -Is) box=$BOX W=$W git=$GITREV" > "$DIR/CHAIN_STARTED_$BOX"
cat > "$DIR/LAUNCH_MANIFEST_$BOX.json" <<JSON
{
  "schema": "carcassonne-window-truncation-census/launch-manifest/v1",
  "box": "$BOX",
  "workers": $W,
  "started": "$(date -Is)",
  "git_rev": "$GITREV",
  "git_branch": "$(git -C "$REPO" rev-parse --abbrev-ref HEAD)",
  "wheel": "$WHEEL",
  "wheel_has_WindowTruncationError": true,
  "wheel_mtime": "$(date -Is -r "$WHEEL" 2>/dev/null)",
  "share": "$SHARE",
  "runner": "$DIR/RUN_CMD.sh",
  "instrument": "scripts/measurement_infra/window_truncation_census.py",
  "design": "$DIR/DESIGN.md",
  "legs": ["walled (CL-070 bank, 898 roots)", "fixed_v1 (E4 champion plies, 1548 roots)"],
  "budget": "production k_dets=8 x sims_per_det=1376",
  "nproc": $(nproc),
  "mem_total_mb": $(free -m | awk '/^Mem:/{print $2}'),
  "mem_avail_mb_at_launch": $(free -m | awk '/^Mem:/{print $7}'),
  "nice": 19,
  "read_only": true,
  "plays_games": false,
  "band": null,
  "results_csv_row": false,
  "claim": null,
  "adjudicates": false,
  "note": "$NOTE"
}
JSON

# --- the census itself: RUN_CMD.sh owns the commands, foreground, exit code is the verdict --
T0=$(date +%s)
nice -n 19 bash "$DIR/RUN_CMD.sh" "$W" >>"$LOGS/launch_$BOX.log" 2>&1
RC=$?
ELAPSED=$(( $(date +%s) - T0 ))
say "RUN_CMD.sh exited rc=$RC after ${ELAPSED}s"

# --- publish to the share (results must never be box-local again) ---------------------------
PUB="$SHARE/window_truncation_20260813/$BOX"
mkdir -p "$PUB" || say "WARN: cannot mkdir $PUB"
for f in CENSUS_RESULT.md RUN_MANIFEST.json "LAUNCH_MANIFEST_$BOX.json" FAILED_CENSUS; do
  [ -e "$DIR/$f" ] && cp "$DIR/$f" "$PUB/" 2>/dev/null
done
for leg in walled fixed_v1; do
  mkdir -p "$PUB/census_$leg"
  for f in summary.json manifest.json rows.jsonl; do
    [ -e "$DIR/census_$leg/$f" ] && cp "$DIR/census_$leg/$f" "$PUB/census_$leg/" 2>/dev/null
  done
  [ -e "$LOGS/census_$leg.log" ] && cp "$LOGS/census_$leg.log" "$PUB/" 2>/dev/null
done
echo "rc=$RC elapsed=${ELAPSED}s box=$BOX W=$W git=$GITREV $(date -Is)" > "$PUB/EXIT_$BOX"
[ "$RC" -eq 0 ] && [ -f "$DIR/DONE_CENSUS" ] && cp "$DIR/DONE_CENSUS" "$PUB/DONE_CENSUS"
say "published to $PUB"
exit "$RC"
