#!/usr/bin/env bash
# =============================================================================
# tiearb2 STAGE 2 PHASE B — THE DEFERRED FULL RECONCILE GATES.
#
#   deferred_full_gates.sh          (launch DETACHED; it waits, then runs)
#
# The 2026-08-17 post-cell reconcile re-run left two gates PARTIAL, cut by a
# wall-clock cap rather than by any failure — both were emitting unbroken zeros
# when they were stopped:
#
#   reconcile_backend      21/28 games, 3,023/3,023 actions agree, 0 mismatches
#                          (the COMMITTED default is 100 games; at its default
#                          14 workers that measures ~4 h)
#   reconcile_exact_solver 30/186 jobs, 88 checks, 0 mismatches
#                          (3 workers against a 4M-node budget, and the
#                          marginalized mode has no alpha-beta — the documented
#                          cost wall; jobs 21-30 alone took 536 s)
#
# This runs BOTH at their committed, UNCAPPED settings so the close-out record
# carries the full gate rather than a labelled subset.
#
# ⚠️ IT MUST NOT RUN BESIDE A LIVE CELL. It blocks until all FOUR JCZ markers
# exist AND the box is actually quiet, then censuses again before each gate. A
# reconcile suite beside a live cell would both slow the cell and (for anything
# timing-adjacent) contaminate it.
#
# LAUNCH:
#   setsid nohup nice -n 19 bash \
#     /home/doctor/projects/carcassone/measurement/tiearb2_stage2_20260817/deferred_full_gates.sh \
#     > /home/doctor/projects/carcassone/measurement/tiearb2_stage2_20260817/logs/deferred_gates.log \
#     2>&1 < /dev/null & disown
#
# It writes DONE_DEFERRED_GATES (content-bearing) or FAILED_DEFERRED_GATES.
# It ADJUDICATES NOTHING and touches no governance file.
# =============================================================================
set -u

REPO=/home/doctor/projects/carcassone
cd "$REPO" || exit 1
HERE="$REPO/measurement/tiearb2_stage2_20260817"
JCZ="$REPO/measurement/jcz_tiearb_20260817"
# ⚠️ RE-KEYED 2026-08-18 — TWO LATENT BUGS FIXED, both found while the box was quiet.
#
# (1) WRONG LOCATION. The MARKERS below used to point at "$JCZ" (the LOCAL run
#     dir). Only the two `Doctor` markers are ever written there; each box writes
#     its own markers to ITS OWN disk plus the SHARE, so the two `laptop-wsl`
#     markers never appear locally. Verified: all four of the voided run's markers
#     exist at /mnt/c/carc-shared/jcz_tiearb_20260817/, only two locally. This
#     script would therefore have blocked FOREVER and never fired its gates.
#     THE SHARE IS THE ONLY LOCATION BOTH BOXES PUBLISH TO.
# (2) STALE BAND. The 133000000000 run was VOIDED (see the JCZ dir's
#     DISCLOSURE.md); its markers still exist and would have satisfied a
#     band-agnostic wait immediately. The re-run tags every artifact `b134`, so
#     the markers below are band-qualified and cannot be satisfied by the void.
JCZ_SHARE=/mnt/c/carc-shared/jcz_tiearb_20260817   # allow-path (LOCAL box only; this script never runs over ssh)
LOGS="$HERE/logs"
OUT="$HERE/verdicts/deferred_gates"
PY="$REPO/.venv/bin/python"
mkdir -p "$LOGS" "$OUT"

ts() { date +%F_%T; }
log() { echo "[deferred-gates $(ts)] $*"; }

# The four completion markers the coordinator named, verbatim.
MARKERS=(
  "$JCZ_SHARE/DONE_jcz_CHAMP_deploy11008_Doctor_b134"
  "$JCZ_SHARE/DONE_jcz_ARB_B16J4_deploy11008_Doctor_b134"
  "$JCZ_SHARE/DONE_jcz_CHAMP_deploy11008_laptop-wsl_b134"
  "$JCZ_SHARE/DONE_jcz_ARB_B16J4_deploy11008_laptop-wsl_b134"
)

log "=== WAITING for the JCZ cell pair (4 markers) ==="
for m in "${MARKERS[@]}"; do log "  marker: $m"; done

# --- wait for all four markers. No timeout: the cells own the boxes until they
# --- are done, and a gate suite that gave up early and ran anyway would be the
# --- exact failure this script exists to prevent.
while :; do
  missing=0
  for m in "${MARKERS[@]}"; do [ -f "$m" ] || missing=$((missing+1)); done
  [ "$missing" -eq 0 ] && break
  sleep 120
done
log "all 4 JCZ markers present"

# --- then wait for the box to actually go quiet. A marker says the DRIVER
# --- finished; it does not say every worker has exited (an mp Pool's children
# --- routinely outlive their main). Require two consecutive quiet samples.
quiet=0
while [ "$quiet" -lt 2 ]; do
  n=$(pgrep -cf "eval_fair_puct|gen_fair|run_cell.sh|jcz_match/match\.py" 2>/dev/null || echo 0)
  la=$(cut -d' ' -f1 /proc/loadavg)
  if [ "$n" -eq 0 ] && [ "${la%.*}" -lt 4 ]; then
    quiet=$((quiet+1))
  else
    quiet=0
    log "box still busy (procs=$n load=$la) — holding"
  fi
  sleep 60
done
log "box quiet — proceeding"

log "--- census BEFORE ---"
ps -o pid,etime,%cpu,comm -C python --sort=-etime | head -10
cat /proc/loadavg

export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1
export CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export RUSTUP_TOOLCHAIN=1.96.0
# ⚠️ CARCASSONNE_FIX_R9 deliberately NOT exported: it is import-latched and moves
# the live engine's semantics, which makes tile_data_drift's digest comparison
# fail for reasons that have nothing to do with the port.

rc_backend=0
rc_exact=0

log "=== reconcile_backend, COMMITTED default (100 games) at 28 workers ==="
# The gate's own default is --workers 14; 28 is a throughput choice only and
# moves no value (game-level fork pool, results index-addressed).
nice -n 19 "$PY" scripts/rustport/reconcile_backend.py --games 100 --workers 28 \
  > "$OUT/backend_full.log" 2>&1
rc_backend=$?
log "reconcile_backend rc=$rc_backend"
tail -8 "$OUT/backend_full.log"

log "--- census between gates ---"
cat /proc/loadavg

log "=== reconcile_exact_solver, UNCAPPED ==="
nice -n 19 "$PY" scripts/rustport/reconcile_exact_solver.py \
  > "$OUT/exact_solver_full.log" 2>&1
rc_exact=$?
log "reconcile_exact_solver rc=$rc_exact"
tail -8 "$OUT/exact_solver_full.log"

log "--- census AFTER ---"
ps -o pid,etime,%cpu,comm -C python --sort=-etime | head -6
cat /proc/loadavg

{
  echo "$(ts)"
  echo "reconcile_backend  (--games 100 --workers 28) rc=$rc_backend"
  grep -aE "games, .* actions agree|PASS|FAIL" "$OUT/backend_full.log" | tail -3
  echo "reconcile_exact_solver (uncapped) rc=$rc_exact"
  grep -aE "jobs, .* checks|PASS|FAIL" "$OUT/exact_solver_full.log" | tail -3
  echo "logs: $OUT/"
  echo "NOT ADJUDICATED - a regression gate, no strength statistic, no governance touch."
} > "$HERE/$( [ "$rc_backend" -eq 0 ] && [ "$rc_exact" -eq 0 ] && echo DONE_DEFERRED_GATES || echo FAILED_DEFERRED_GATES )"

log "=== DEFERRED GATES COMPLETE (backend rc=$rc_backend, exact_solver rc=$rc_exact) ==="
