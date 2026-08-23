#!/usr/bin/env bash
# =============================================================================
# tiearb2 STAGE 2 PHASE B — THE DEFERRED FULL RECONCILE GATES.
#
#   deferred_full_gates.sh          (do not launch this by hand — see below)
#
# ⚠️ LAUNCH VIA THE LAUNCHER, NOT DIRECTLY:
#
#   /home/doctor/projects/carcassone/measurement/tiearb2_stage2_20260817/launch_deferred_gates.sh
#
# It is one command, it detaches (setsid + nohup + disown), it caps memory, it
# refuses to double-launch, and it writes the log this script's stamps point at.
#
# -----------------------------------------------------------------------------
# WHAT THIS RUNS, AND WHAT IS ALREADY DONE
# -----------------------------------------------------------------------------
# The 2026-08-17 post-cell reconcile re-run left two gates PARTIAL, cut by a
# wall-clock cap rather than by any failure. This suite runs both at their
# committed, UNCAPPED settings.
#
#   reconcile_backend       ✅ DONE — G6 PASS banked 2026-08-19T16:43:56Z.
#                           100/100 games, 14384/14384 actions agree, 0
#                           mismatches over 101088 checks, 14041 s.
#                           -> measurement/rustport_p6/G6_backend_run.json
#                           This suite now SKIPS it, but only after
#                           `gate_status.py` re-proves the PASS still covers
#                           the code that is here TODAY (identical carc_rs
#                           binary sha + unmoved Python paths). If either
#                           moved, or FORCE_BACKEND=1, it runs again (~3 h 54 m).
#
#   reconcile_exact_solver  ❌ NOT DONE — killed twice mid-flight.
#                           Attempt 1 (08-18 22:56) never reached it; the
#                           backend gate under it was cut by box contention.
#                           Attempt 2 (08-19 12:43) ran it for ~7 h 33 m and
#                           reached 82 of ~179 jobs, 0 mismatches, before the
#                           host went down. This is the whole remaining job.
#
# -----------------------------------------------------------------------------
# RESUMABILITY — THE THIRD KILL MUST NOT ZERO IT
# -----------------------------------------------------------------------------
# Two independent layers, because a ~17 h gate that loses everything on a kill
# is a gate that never finishes:
#
#   PER-GATE STAMPS   verdicts/deferred_gates/STAMP_<gate>.json is written the
#                     moment a gate settles. A re-launch reads them and skips
#                     what already passed. Idempotent: launching this three
#                     times in a row does the remaining work once.
#
#   PER-JOB RESUME    reconcile_exact_solver appends every finished job to
#                     G7_exact_solver_<tag>_rows.jsonl as it lands, and (new,
#                     2026-08-23) stamps each row with a `job_key`, so
#                     `--resume` skips jobs already recorded instead of
#                     re-solving them. A kill now costs at most the jobs in
#                     flight, not the run.
#
# ⚠️ THE 2026-08-19 ROWS FILE CANNOT BE RESUMED FROM. It predates job keys AND
# it is contaminated: it holds 28 golden + 24 v2 rows for a 14-golden/12-v2
# plan, i.e. two attempts' rows appended into one file, so a --from-rows
# rebuild of it over-reports checks. Worse, the plan it recorded is not
# reproducible — the sub-sampler was seeded with `hash()`, which CPython salts
# per process (that is why the logs read `jobs=186` on 08-17 and `jobs=179` on
# 08-19 from identical arguments). Both are fixed as of 2026-08-23; this script
# archives that file aside, once, and starts a clean keyed one. The archived
# rows remain readable with `--from-rows` as the honest partial record they are.
#
# -----------------------------------------------------------------------------
# ⚠️ IT MUST NOT RUN BESIDE A LIVE CELL. It blocks until all FOUR JCZ markers
# exist AND the box is actually quiet, then censuses again before each gate. A
# reconcile suite beside a live cell would both slow the cell and (for anything
# timing-adjacent) contaminate it.
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

# Knobs (env, all optional):
#   FORCE_BACKEND=1   run the backend gate even if its PASS still covers today
#   FORCE_EXACT=1     ignore STAMP_exact_solver.json and run it again
#   EXACT_WORKERS=N   fork workers for the exact-solver gate (default 3)
#   EXACT_TAG=name    rows/verdict tag for the exact-solver gate (default run2)
#   SMOKE=1           do everything EXCEPT the two long solves; used to prove
#                     the suite is wired correctly without paying for it
#   ALLOW_DIRTY=1     let the backend gate SKIP even though guarded Python
#                     files are uncommitted in the tree. Default 0 = a dirty
#                     src/ forces the backend gate to actually run, because a
#                     banked PASS cannot vouch for code it never saw.
#   SKIP_WAIT=1       skip the marker + quiet waits. HONOURED ONLY UNDER
#                     SMOKE=1 — it exists to prove the gate wiring on a busy
#                     box without adding load, and a real run that skipped the
#                     quiet wait is precisely the contamination this suite
#                     exists to prevent.
FORCE_BACKEND=${FORCE_BACKEND:-0}
FORCE_EXACT=${FORCE_EXACT:-0}
EXACT_WORKERS=${EXACT_WORKERS:-3}
EXACT_TAG=${EXACT_TAG:-run2}
SMOKE=${SMOKE:-0}
ALLOW_DIRTY=${ALLOW_DIRTY:-0}
SKIP_WAIT=${SKIP_WAIT:-0}
if [ "$SKIP_WAIT" = "1" ] && [ "$SMOKE" != "1" ]; then
  echo "SKIP_WAIT=1 is only honoured with SMOKE=1 — refusing." >&2
  exit 2
fi

ts() { date +%F_%T; }
log() { echo "[deferred-gates $(ts)] $*"; }

STAMP_PREFIX=STAMP
DONE_NAME=DONE_DEFERRED_GATES
FAILED_NAME=FAILED_DEFERRED_GATES
if [ "$SMOKE" = "1" ]; then
  # A smoke must leave NO artifact a later launch would read as real work.
  # (It used to write DONE_DEFERRED_GATES, which makes the launcher refuse to
  # start the actual gates — a smoke that blocks the run it was proving.)
  STAMP_PREFIX=SMOKE_STAMP
  DONE_NAME=SMOKE_DEFERRED_GATES
  FAILED_NAME=SMOKE_DEFERRED_GATES_FAILED
fi

stamp() {  # stamp <gate> <rc> <note>
  "$PY" - "$OUT/${STAMP_PREFIX}_$1.json" "$1" "$2" "$3" <<'PYEOF'
import json, sys, time
path, gate, rc, note = sys.argv[1:5]
json.dump({"gate": gate, "rc": int(rc), "settled": time.strftime("%FT%T"),
           "note": note}, open(path, "w"), indent=2)
PYEOF
  log "stamped $1 rc=$2 ($3)"
}

stamp_says_pass() {  # stamp_says_pass <gate>  -> 0 if a rc=0 stamp exists
  [ -f "$OUT/STAMP_$1.json" ] || return 1
  [ "$("$PY" -c "import json,sys;print(json.load(open(sys.argv[1]))['rc'])" \
        "$OUT/STAMP_$1.json" 2>/dev/null)" = "0" ]
}

if [ "$SKIP_WAIT" = "1" ]; then
  log "⚠️ SMOKE + SKIP_WAIT — marker wait and quiet wait BYPASSED (wiring proof only)"
fi

log "=== WAITING for the JCZ cell pair (4 markers) ==="

# The four completion markers the coordinator named, verbatim.
MARKERS=(
  "$JCZ_SHARE/DONE_jcz_CHAMP_deploy11008_Doctor_b134"
  "$JCZ_SHARE/DONE_jcz_ARB_B16J4_deploy11008_Doctor_b134"
  "$JCZ_SHARE/DONE_jcz_CHAMP_deploy11008_laptop-wsl_b134"
  "$JCZ_SHARE/DONE_jcz_ARB_B16J4_deploy11008_laptop-wsl_b134"
)
for m in "${MARKERS[@]}"; do log "  marker: $m"; done

# --- wait for all four markers. No timeout: the cells own the boxes until they
# --- are done, and a gate suite that gave up early and ran anyway would be the
# --- exact failure this script exists to prevent.
while [ "$SKIP_WAIT" != "1" ]; do
  missing=0
  for m in "${MARKERS[@]}"; do [ -f "$m" ] || missing=$((missing+1)); done
  [ "$missing" -eq 0 ] && break
  sleep 120
done
log "all 4 JCZ markers present"

# --- then wait for the box to actually go quiet. A marker says the DRIVER
# --- finished; it does not say every worker has exited (an mp Pool's children
# --- routinely outlive their main). Require two consecutive quiet samples.
# ⚠️⚠️ THIRD LATENT HANG, FIXED 2026-08-18 — this loop could NEVER have advanced.
#
# `pgrep -c` prints its count AND EXITS 1 when the count is zero. The old form
#     n=$(pgrep -cf "..." 2>/dev/null || echo 0)
# therefore produced the TWO-LINE string "0\n0" on a genuinely quiet box: pgrep's
# own "0" plus the fallback's. `[ "0\n0" -eq 0 ]` is not a false test — it is a
# BASH ERROR ("integer expression expected"), so the `if` took the else branch,
# `quiet` was reset to 0, and the script logged `box still busy (procs=0 …)`
# forever. Measured, not reasoned: a two-line reproducer returns exactly that.
# The failure mode is identical to the marker bug above — it hangs precisely when
# its condition is SATISFIED — and it sat immediately downstream of it, so fixing
# only the markers would have moved the hang forty lines later.
#
# `|| true` + an explicit numeric guard: pgrep's count is used when it is a
# number, and anything else (empty, multi-line, an error) reads as 0.
#
# ⚠️ The pattern is WIDENED to a bare `match\.py` per the re-run brief: the old
# `jcz_match/match\.py` only matched an argv carrying the full relative path, and
# a spawn worker re-exec'd with a different argv shape would have read as quiet
# while it was still holding the box. `match\.py` subsumes it and this repo has
# exactly one `match.py` (scripts/jcz_match/). A quiet check must fail toward
# "still busy". No self-match risk: this script's own argv is
# `bash …/deferred_full_gates.sh` and carries none of these strings.
quiet=0
[ "$SKIP_WAIT" = "1" ] && quiet=2
while [ "$quiet" -lt 2 ]; do
  # ⚠️ WIDENED 2026-08-18 — `run_tiletie` added. The pattern could see generation
  # (`gen_fair`) but NOT the tie-arbiter widening run's SCORING legs, so the box
  # would have read "quiet" the moment generation drained and fired a ~4 h
  # reconcile suite into a live 15-16 h scoring run. `run_tiletie` is the
  # resident parent of every scoring leg (it spawns oracle_score_pilot /
  # tier1_rust_leg as children and blocks on them), so matching it covers the
  # whole leg. A quiet check must fail toward "still busy".
  n=$(pgrep -cf "eval_fair_puct|gen_fair|run_cell\.sh|match\.py|run_tiletie" 2>/dev/null || true)
  case "$n" in ''|*[!0-9]*) n=0 ;; esac
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

# =============================================================================
# GATE 1 — reconcile_backend
# =============================================================================
if stamp_says_pass backend && [ "$FORCE_BACKEND" != "1" ]; then
  BACKEND_DECISION=ALREADY
elif [ "$FORCE_BACKEND" = "1" ]; then
  log "reconcile_backend: FORCED by FORCE_BACKEND=1"
  BACKEND_DECISION=RUN
else
  # Not "is there a file called G6_backend_run.json" — "does its PASS still
  # cover the binary and the Python source that are here right now". Any
  # failure of the check itself falls toward RUN: a gate suite must never skip
  # on a question it could not answer.
  gs_flags=""
  [ "$ALLOW_DIRTY" = "1" ] && gs_flags="--allow-dirty"
  gs_out=$("$PY" "$HERE/gate_status.py" \
      "$REPO/measurement/rustport_p6/G6_backend_run.json" $gs_flags \
      2>"$OUT/gate_status_backend.log")
  gs_rc=$?
  while IFS= read -r l; do log "  $l"; done < "$OUT/gate_status_backend.log"
  if [ "$gs_rc" -ne 0 ]; then
    log "  gate_status.py itself failed (rc=$gs_rc) — running the gate"
    BACKEND_DECISION=RUN
  else
    BACKEND_DECISION=$(echo "$gs_out" | tr -d '[:space:]')
  fi
  BACKEND_DECISION=${BACKEND_DECISION:-RUN}
fi

if [ "$BACKEND_DECISION" = "ALREADY" ]; then
  log "=== reconcile_backend: SKIP (this suite already stamped it rc=0) ==="
elif [ "$BACKEND_DECISION" = "SKIP" ]; then
  log "=== reconcile_backend: SKIP — the banked G6 PASS still covers today ==="
  stamp backend 0 "skipped: banked G6 PASS at measurement/rustport_p6/G6_backend_run.json still covers this binary and source"
elif [ "$SMOKE" = "1" ]; then
  log "=== reconcile_backend: SMOKE — would RUN, not running ==="
else
  log "=== reconcile_backend, COMMITTED default (100 games) at 14 workers (owner W14 desktop-friendly window from 2026-08-24 morning) ==="
  # The gate's own default is --workers 14; 28 is a throughput choice only and
  # moves no value (game-level fork pool, results index-addressed).
  nice -n 19 "$PY" scripts/rustport/reconcile_backend.py --games 100 --workers 14 \
    > "$OUT/backend_full.log" 2>&1
  rc_backend=$?
  log "reconcile_backend rc=$rc_backend"
  tail -8 "$OUT/backend_full.log"
  stamp backend "$rc_backend" "ran here; log $OUT/backend_full.log"
fi

log "--- census between gates ---"
cat /proc/loadavg

# =============================================================================
# GATE 2 — reconcile_exact_solver
# =============================================================================
EX_DIR="$REPO/measurement/rustport_exact_solver"
ROWS="$EX_DIR/G7_exact_solver_${EXACT_TAG}_rows.jsonl"

if stamp_says_pass exact_solver && [ "$FORCE_EXACT" != "1" ]; then
  log "=== reconcile_exact_solver: SKIP (this suite already stamped it rc=0) ==="
else
  # ARCHIVE, ONCE, any rows file this tag cannot resume from (see the header).
  if [ -f "$ROWS" ] && ! "$PY" -c "
import json,sys
bad=[1 for l in open(sys.argv[1]) if l.strip() and 'job_key' not in json.loads(l)]
sys.exit(1 if bad else 0)" "$ROWS"; then
    mv "$ROWS" "$ROWS.unkeyed_$(date +%Y%m%d_%H%M%S).bak"
    log "archived an unkeyed rows file aside: $ROWS.unkeyed_*.bak (readable with --from-rows)"
  fi

  if [ "$SMOKE" = "1" ]; then
    log "=== reconcile_exact_solver: SMOKE — plan only, no solves ==="
    nice -n 19 "$PY" scripts/rustport/reconcile_exact_solver.py --plan-only \
      > "$OUT/exact_solver_plan.log" 2>&1
    rc_exact=$?
    log "reconcile_exact_solver --plan-only rc=$rc_exact"
    cat "$OUT/exact_solver_plan.log"
  else
    log "=== reconcile_exact_solver, UNCAPPED (tag=$EXACT_TAG workers=$EXACT_WORKERS, --resume) ==="
    nice -n 19 "$PY" scripts/rustport/reconcile_exact_solver.py \
      --tag "$EXACT_TAG" --workers "$EXACT_WORKERS" --resume \
      > "$OUT/exact_solver_full.log" 2>&1
    rc_exact=$?
    log "reconcile_exact_solver rc=$rc_exact"
    tail -8 "$OUT/exact_solver_full.log"
    stamp exact_solver "$rc_exact" "ran here; rows $ROWS; log $OUT/exact_solver_full.log"
  fi
fi

log "--- census AFTER ---"
ps -o pid,etime,%cpu,comm -C python --sort=-etime | head -6
cat /proc/loadavg

{
  echo "$(ts)"
  echo "reconcile_backend  rc=$rc_backend"
  if [ -f "$OUT/backend_full.log" ]; then
    grep -aE "games, .* actions agree|PASS|FAIL" "$OUT/backend_full.log" | tail -3
  else
    echo "  (not run here — see $OUT/${STAMP_PREFIX}_backend.json)"
  fi
  echo "reconcile_exact_solver (uncapped, tag=$EXACT_TAG) rc=$rc_exact"
  if [ -f "$OUT/exact_solver_full.log" ]; then
    grep -aE "jobs, .* checks|PASS|FAIL" "$OUT/exact_solver_full.log" | tail -3
  fi
  echo "stamps: $OUT/${STAMP_PREFIX}_backend.json $OUT/${STAMP_PREFIX}_exact_solver.json"
  echo "logs: $OUT/"
  echo "NOT ADJUDICATED - a regression gate, no strength statistic, no governance touch."
} > "$HERE/$( [ "$rc_backend" -eq 0 ] && [ "$rc_exact" -eq 0 ] && echo "$DONE_NAME" || echo "$FAILED_NAME" )"

log "=== DEFERRED GATES COMPLETE (backend rc=$rc_backend, exact_solver rc=$rc_exact) ==="
