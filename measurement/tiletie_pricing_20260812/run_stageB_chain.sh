#!/usr/bin/env bash
# TILE-TIE PRICING — STAGE B chain (owner-authorized 2026-08-13, "yes please").
#
# Prereg of record: measurement/tiletie_pricing_20260812/DESIGN.md §7.3
#   "Stage B — extend to n = ceil((2 x sd_A / 0.174)^2), capped at 1,300 — funded only if
#    Stage A lands in branch 4 (inconclusive) ... --resume makes it a pure extension of the
#    same records directory: no re-scoring, no new ruler."
#   Arm composition is FIXED by the same section: "bought only on the rust arm"
#   (selfplay / walled). The E4/python arm is ~9.4x more expensive per position and is
#   NOT extended.
# Sizing + disjointness + the pooled-analysis rule: STAGE_B_ADDENDUM.md.
#
# THIS SCRIPT ADJUDICATES NOTHING. It scores positions. It never runs
# analyze_tiletie.py, never touches governance/, never writes a verdict.
#
# ───────────────────────────────────────────────────────────────────────────────────────
# WORKER GRANT (owner, 2026-08-13): local box "W30 until 11:00 local, then W14".
# Encoded exactly as scripts/joshuabot/tournament_chain.sh encodes it: W is chosen AT CELL
# START, W_HI only if the W_HI window is open AND this cell is PROJECTED to finish before
# it closes. A W_HI cell must never straddle 11:00.
# ───────────────────────────────────────────────────────────────────────────────────────
#
# CELLS are cumulative plan dirs (see scripts/tiletie/make_stageb_cells.py): cell k names
# Stage A + Stage B chunks 1..k. oracle_score_pilot --resume skips every rid whose record
# already exists, so cell k scores only its own ~98 new positions, while
# run_tiletie.verify_leg_records still sees the exact rid set of the shared records root.
# The last cell's plan dir == measurement/.../positions_pooled (the analyser's input).
#
# RESUME: safe to re-run. A cell with DONE_CELLnn is skipped; a half-finished cell resumes
# through the pilot's own --resume (per-record fsync write).
#
# USAGE (detached — Mac->Windows->WSL SIGHUP/teardown rule):
#   setsid nohup nice -n 19 bash \
#     /home/doctor/projects/carcassone/measurement/tiletie_pricing_20260812/run_stageB_chain.sh \
#     >> /home/doctor/projects/carcassone/measurement/tiletie_pricing_20260812/logs/stageB/chain.log 2>&1 &
#   disown
#
# ENV OVERRIDES: TT_W_HI=30 TT_W_LO=14 TT_SLOWDOWN_HI=1.6 TT_EFF=0.917 TT_CELLS="cell01 ..."

set -uo pipefail

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
P=$REPO/measurement/tiletie_pricing_20260812
CELLDIR=$P/positions_stageB/cells
LOGS=$P/logs/stageB
MANDIR=$P/manifests_stageB

DONE_MARK=$P/DONE_STAGEB
FAIL_MARK=$P/FAILED_STAGEB

W_HI=${TT_W_HI:-30}
W_LO=${TT_W_LO:-14}
# PLANNING CONSTANTS, not measurements (house convention — tournament_chain.sh JB_CONTENTION_*).
# The per-worker slowdown at W_HI is deliberately pessimistic: overestimating a cell's wall
# makes the chain MORE likely to fall back to W_LO, which is the safe side of "never straddle".
SLOWDOWN_HI=${TT_SLOWDOWN_HI:-1.6}
# REALIZED parallel efficiency of the Stage A rust arm: sum(elapsed_secs)=60,106.2 s over a
# 4,680.6 s wall at W=14 nominal => 12.84 effective workers = 91.7%.
EFF=${TT_EFF:-0.917}
# REALIZED worker-seconds per NEW Stage B position: the phase-weighted projection
# (81,576 worker-s / 393 positions) from Stage A's own per-record elapsed_secs by phase
# bucket — NOT DESIGN §0.B's planning constant c_rust=1.4755 (realized c is 1.5999).
SECS_PER_POS=${TT_SECS_PER_POS:-207.6}

mkdir -p "$LOGS" "$MANDIR"

ts() { date +%F_%T; }
log() { echo "[ttB $(ts)] $*"; }

fail() {
  { echo "FAILED $(ts)"; echo "reason: $*"; } > "$FAIL_MARK"
  log "FATAL: $*"
  log "wrote $FAIL_MARK — no further cells will run."
  exit 1
}

on_exit() {
  rc=$?
  if [ ! -f "$DONE_MARK" ] && [ ! -f "$FAIL_MARK" ]; then
    { echo "FAILED $(ts)"; echo "reason: chain exited rc=$rc without a DONE marker"; } \
      > "$FAIL_MARK"
    log "chain exited rc=$rc with no DONE marker — wrote $FAIL_MARK"
  fi
}
trap on_exit EXIT

# ── the grant, encoded ────────────────────────────────────────────────────────────────
# W_HI window: open 17:00 through 10:59 local, closes at 11:00. A daytime start runs W_LO.
w_hi_open() { local h; h=$(date +%H); h=$((10#$h)); [ "$h" -ge 17 ] || [ "$h" -lt 11 ]; }
mins_to_close() {                      # minutes until the next 11:00; 0 if the window is shut
  if ! w_hi_open; then echo 0; return; fi
  local h m now
  h=$(date +%H); m=$(date +%M); now=$((10#$h * 60 + 10#$m))
  if [ "$now" -lt 660 ]; then echo $((660 - now)); else echo $((660 + 1440 - now)); fi
}
est_min() {                            # $1 = new positions in this cell, $2 = W
  awk -v n="$1" -v w="$2" -v s="$SECS_PER_POS" -v e="$EFF" -v hi="$W_HI" -v sd="$SLOWDOWN_HI" \
    'BEGIN { c = (w == hi ? sd : 1.0); printf "%d", (n*s) / (w*e/c) / 60 + 1 }'
}

CELLS=${TT_CELLS:-$(cd "$CELLDIR" && ls -d cell* | sort)}
[ -n "$CELLS" ] || fail "no cells under $CELLDIR"

log "===== STAGE B chain starting. cells: $CELLS"
log "grant: W_HI=$W_HI while the window is open AND the cell fits before 11:00; else W_LO=$W_LO"
log "realized-rate constants: ${SECS_PER_POS}s/new-position, eff=${EFF}, W_HI slowdown x${SLOWDOWN_HI}"

PREV_TOTAL=0
for CELL in $CELLS; do
  DIR=$CELLDIR/$CELL
  [ -d "$DIR" ] || fail "missing cell dir $DIR"
  CELL_DONE=$P/DONE_STAGEB_$CELL

  HERE=$("$PY" -c "import json,sys;print(json.load(open(sys.argv[1]))['stage_b_cell']['n_stage_b_here'])" \
         "$DIR/POSITIONS_PLAN.json") || fail "cannot read $DIR/POSITIONS_PLAN.json"
  NEW=$((HERE - PREV_TOTAL))
  PREV_TOTAL=$HERE

  if [ -f "$CELL_DONE" ]; then
    log "$CELL: DONE marker present — skipping (resume)."
    continue
  fi

  LEFT=$(mins_to_close)
  PER_HI=$(est_min "$NEW" "$W_HI")
  PER_LO=$(est_min "$NEW" "$W_LO")
  if [ "$LEFT" -gt 0 ] && [ "$PER_HI" -le "$LEFT" ]; then W=$W_HI; else W=$W_LO; fi
  log "$CELL: new_positions=$NEW cumulative=$HERE | est ${PER_HI}min@W$W_HI ${PER_LO}min@W$W_LO"\
"| W_HI window has ${LEFT}min left => W=$W"

  mkdir -p "$LOGS/$CELL"
  T0=$(date +%s)
  nice -n 19 "$PY" -u "$REPO/scripts/tiletie/run_tiletie.py" --yes \
      --workers "$W" \
      --positions-dir "$DIR" \
      --only-profiles walled \
      --logs-dir "$LOGS/$CELL" \
      --manifest-out "$MANDIR/RUN_MANIFEST_stageB_$CELL.json" \
      --gate-out "$MANDIR/GATE_BACKEND_RECHECK_stageB_$CELL.json" \
      > "$LOGS/${CELL}.log" 2>&1
  RC=$?
  T1=$(date +%s)
  log "$CELL: run_tiletie rc=$RC wall=$(( (T1-T0)/60 ))min — log $LOGS/${CELL}.log"

  [ "$RC" -eq 0 ] || fail "$CELL: run_tiletie exited $RC (see $LOGS/${CELL}.log and \
$MANDIR/RUN_MANIFEST_stageB_$CELL.json)"

  # Belt-and-braces on top of run_tiletie's own verify_leg_records: every walled leg must
  # have rc=0, no missing and no extra records. A silent shortfall here would be read by the
  # analyser as "partial", which is exactly the failure mode Stage A's read-out had to rule out.
  "$PY" - "$MANDIR/RUN_MANIFEST_stageB_$CELL.json" <<'EOF' || fail "$CELL: manifest verification failed"
import json, sys
m = json.load(open(sys.argv[1]))
bad = []
for leg in m.get("legs") or []:
    v = leg.get("records_verified") or {}
    if leg.get("rc") != 0 or v.get("missing") or v.get("extra"):
        bad.append({"leg": f"{leg.get('profile')}/leg{leg.get('leg')}", "rc": leg.get("rc"),
                    "missing": (v.get("missing") or [])[:5], "extra": (v.get("extra") or [])[:5]})
if not (m.get("legs") or []):
    bad.append("manifest names zero legs")
if bad:
    print("VERIFY FAIL:", json.dumps(bad)[:2000], file=sys.stderr)
    raise SystemExit(1)
print(f"verify ok: {len(m['legs'])} legs, all rc=0, no missing/extra records")
EOF

  { echo "DONE $(ts)"; echo "cell=$CELL new_positions=$NEW cumulative=$HERE W=$W"
    echo "wall_secs=$((T1-T0))"; } > "$CELL_DONE"
  log "$CELL: OK — wrote $CELL_DONE"
done

{ echo "DONE $(ts)"
  echo "stage=B  arm=selfplay/walled/rust  new_positions=393  pooled_positions=733"
  echo "pooled plan dir (analyser input): $P/positions_pooled"
  echo "records root: /mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct"
  echo "NOT adjudicated: analyze_tiletie.py has NOT been run. DESIGN §7.3 pools Stage A +"
  echo "Stage B into ONE estimate; see STAGE_B_ADDENDUM.md."; } > "$DONE_MARK"
log "===== STAGE B COMPLETE — wrote $DONE_MARK"
exit 0
