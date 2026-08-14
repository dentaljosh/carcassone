#!/usr/bin/env bash
# OPEN-CITY ROUND 2 CALIBRATION — offline E4-replay pick-flip rates for the CL-080
# falsifier arms. Read-rule: measurement/opencity_round2_20260814/CALIB_READ_RULE.md
# (committed 9a2abcd5 BEFORE any flip rate was read — verify with `git log`).
#
#   run_calib_round2.sh [WORKERS] [REPO_ROOT]
#
# ZERO games, ZERO elo, NO deck band, NO governance write, NO results.csv row.
# Two runs, per the read-rule §1 (asymmetric is a run-level switch by design):
#   run 1 (symmetric):  C_d4p0 C_d8p0 C_d16p0  Acap1_d0p5 Acap1_d2p0 Acap3_d2p0
#                       -> calib/          (7 searches per champion ply)
#   run 2 (asymmetric): Asym_d0p5 Asym_d2p0
#                       -> calib_asym/     (3 searches per champion ply)
#
# REQUIRES a CAP-CAPABLE carc_rs on PYTHONPATH/site-packages (TERM_SPEC §10): the
# capped arms raise TypeError on a cap-stale wheel (fail-closed), and this script
# probes that BEFORE grading a single ply.
set -euo pipefail

W="${1:-12}"
REPO="${2:-/home/doctor/projects/carcassone}"
DIR=$REPO/measurement/opencity_round2_20260814
LOGS=$DIR/calib_logs
PY=${CARC_PY:-/home/doctor/projects/carcassone/.venv/bin/python}

# --- the champion leaf env canon (round-1 run_calib_laptop.sh, verbatim) ------
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_FIX_R9=1

mkdir -p "$LOGS"
log() { echo "[oc-r2-calib $(date +%F_%T)] $*" | tee -a "$LOGS/driver.log"; }
die() { log "ABORT: $*"; exit 1; }
cd "$REPO"

SYM_ARMS=(--arm C_d4p0:6:3:4 --arm C_d8p0:6:3:8 --arm C_d16p0:6:3:16
          --arm Acap1_d0p5:4:2:0.5:1 --arm Acap1_d2p0:4:2:2:1 --arm Acap3_d2p0:4:2:2:3)
ASYM_ARMS=(--arm Asym_d0p5:4:2:0.5 --arm Asym_d2p0:4:2:2)

# --- launch blocker: the cap-capable wheel probe (TERM_SPEC §10) --------------
nice -n 19 "$PY" scripts/classical_search/chain_capability_probe.py \
  --require opencity --doses 2.0 --size-min 4 --edge-min 2 --cap 1 \
  --json-out "$LOGS/PROBE_cap.json" > "$LOGS/probe_cap.log" 2>&1 \
  || die "cap-capable opencity capability probe FAILED (see $LOGS/probe_cap.log) — a cap-stale wheel grades champion-vs-champion"
# Arm C is gated on WIRING ONLY, never on bite: its predicate reads 0/288 on the
# probe's scripted playouts BY MEASURED FACT (round-1 §4b — and it read 3.60% on real
# human games anyway), so the round-1 driver's rule stands: gate the controls, report
# the bite. The probe's own rc conflates the two, hence the JSON read.
nice -n 19 "$PY" scripts/classical_search/chain_capability_probe.py \
  --require opencity --doses 4.0 --size-min 6 --edge-min 3 \
  --json-out "$LOGS/PROBE_C.json" > "$LOGS/probe_C.log" 2>&1 || true
"$PY" - "$LOGS/PROBE_C.json" <<'PYC' || die "arm-C probe WIRING checks failed (see $LOGS/probe_C.log) — identity/dose-0 control or kwarg seam broke; this is not the known inert-bite case"
import json, sys
r = json.load(open(sys.argv[1]))
f = r.get("functional") or {}
checks = {c["check"]: c["ok"] for c in r.get("checks", [])}
assert checks.get("carc_rs_accepts_opencity_kwargs"), "kwargs seam"
assert f.get("identity_control_breaks") == 0, "identity control"
assert f.get("rs_dose0_breaks") == 0 and f.get("rs_dose0_values_compared", 0) > 0, "rust dose-0"
assert f.get("py_dose0_breaks") == 0 and f.get("py_dose0_values_compared", 0) > 0, "python dose-0"
print(f"arm-C wiring OK (bite on scripted playouts: {f.get('values_moved')}/288 rust, "
      f"{f.get('py_values_moved')}/288 python — REPORTED, not gated; round-1 4b)")
PYC
log "capability probes PASS (cap seam gated; arm C wiring gated, bite reported). A probe pass is NOT bite (read-rule §1 / round-1 §4b)."

# --- run 1: symmetric families C + ACAP ---------------------------------------
log "run 1 (symmetric, 6 arms) starting at W=$W -> $DIR/calib"
nice -n 19 "$PY" -u scripts/classical_search/opencity_e4_replay.py \
  -o "$DIR/calib" --workers "$W" "${SYM_ARMS[@]}" >> "$LOGS/calib_sym.log" 2>&1 \
  || die "run 1 (symmetric) failed — see $LOGS/calib_sym.log (resumable; re-run after the fix)"
log "run 1 complete"

# --- run 2: asymmetric family -------------------------------------------------
log "run 2 (asymmetric, 2 arms) starting at W=$W -> $DIR/calib_asym"
nice -n 19 "$PY" -u scripts/classical_search/opencity_e4_replay.py \
  -o "$DIR/calib_asym" --workers "$W" --asymmetric "${ASYM_ARMS[@]}" >> "$LOGS/calib_asym.log" 2>&1 \
  || die "run 2 (asymmetric) failed — see $LOGS/calib_asym.log (resumable)"
log "run 2 complete"

touch "$LOGS/DONE_CALIB_ROUND2"
log "=== ROUND-2 CALIBRATION COMPLETE. Read per CALIB_READ_RULE.md §3; write CALIB_READOUT.md. ==="
