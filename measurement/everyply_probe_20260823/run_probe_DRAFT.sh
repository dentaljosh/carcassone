#!/usr/bin/env bash
# =============================================================================
# > ⛔ DRAFT -- NOT BLIND-COMMITTED -- NOT LAUNCHED. Prepared 2026-08-23 by
# > transcription from measurement/everyply_probe_plan_20260823/PLAN.md. Owner
# > funding of record: Joshua 2026-08-23 "every ply. fund." -- SIZE-1 ONLY.
# > The blind-commit discipline (freeze DESIGN.md + READ_RULE.md, commit them,
# > stamp BLIND_COMMIT=<sha> before the first PRICING leg) is DEFERRED to the
# > orchestrator. Nothing here may be cited as a pre-registration until that
# > commit exists.
#
# run_probe_DRAFT.sh -- EVERY-PLY ROLLOUT ARBITRATION, SIZE-1 KILL-SCREEN.
#
#   run_probe_DRAFT.sh <local|laptop> [--stage plan|pilot|corpus|arb|sel|if|analyze|all]
#                                     [--chunks N] [--dry-run]
#
# See DESIGN.md (the pipeline is §6.1) and READ_RULE.md (the branches are §4).
# Launcher shape is modeled on measurement/tiearb_20260816/run_main.sh (the
# chunked offline-probe precedent) and measurement/track_d2_prep/run_cells.sh
# (the BLIND_COMMIT + RUN_LIVE freeze-latch precedent).
#
# ⛔ THIS FILE IS LEFT NON-EXECUTABLE (mode 644) DELIBERATELY. It is a DRAFT.
# The orchestrator `chmod +x` it only when authorizing a real launch, after
# BLIND_COMMIT is real and the two OWED BUILDS (DESIGN §6.3) exist.
#
# PRECONDITIONS, IN ORDER, ENFORCED BY THIS SCRIPT:
#   0. BLIND_COMMIT (a file in this directory holding 40 hex chars) exists and
#      is not a placeholder.  [--dry-run and --stage plan are EXEMPT: neither
#      spends blindness -- the plan stage is a pure query over a tracked census
#      and produces no statistic.]
#   1. The two OWED BUILDS exist:
#        scripts/tiletie/build_everyply_corpus.py
#        scripts/tiletie/analyze_everyply.py
#      This script REFUSES rather than half-running a pipeline (DESIGN §6.3).
#   2. G-KNOWNGOOD passes before ANY pricing leg (READ_RULE §3).
#   3. ⛔ NO BAND IS CLAIMED, EVER. There is no --band flag and there is no
#      BAND_CLAIMED gate, BY DESIGN -- this probe consumes no deck band on any
#      branch (BAND_NOTE.md). If you find yourself wanting to add one, STOP and
#      re-read BAND_NOTE.md §4: wanting a band means the design changed.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached
# jobs. Launch as:
#   setsid nohup <this> laptop --stage all </dev/null >/dev/null 2>&1 & disown
# =============================================================================
set -uo pipefail

REPO="${CARC_REPO:-/home/doctor/projects/carcassone}"
DIR="$REPO/measurement/everyply_probe_20260823"
PY="$REPO/.venv/bin/python"
LOGS="$DIR/logs"

RUN_ID=everyply_probe_20260823
N_POOL=450            # DESIGN §5.3 -- SIZE-1 pool
N_PRICED=400          # DESIGN §5.3 -- IF selective read point (the ONLY read point)
CAP_PER_GAME=2        # DESIGN §2.4
HOLDOUT_FRAC=0.25     # DESIGN §6.4
M_WORLDS=32           # DESIGN §3.1 -- M=32, NOT 128
ORACLE_SIMS=100       # DESIGN §5.1 -- the only value any artifact prices
PILOT_N=20            # DESIGN §12

ROLE="${1:?usage: run_probe_DRAFT.sh <local|laptop> [--stage S] [--chunks N] [--dry-run]}"
shift || true
STAGE=all; CHUNKS=4; DRY=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --stage)   STAGE="${2:?--stage needs a value}"; shift ;;
    --chunks)  CHUNKS="${2:?--chunks needs a value}"; shift ;;
    --dry-run) DRY=1 ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

# ⚠️ THE SHARE MOUNT PATH DIFFERS BY BOX (CLUSTER_OPS): local commands use
# /mnt/c/carc-shared; anything running INSIDE the laptop uses /mnt/carc-shared.
# W is PER-BOX and NOT extrapolated. The DESIGN assumes the laptop (§5.5)
# because the local 5900XT was censused BUSY at drafting time.
case "$ROLE" in
  local)  SHARE=/mnt/c/carc-shared;  W=16 ;;
  laptop) SHARE=/mnt/carc-shared;    W=16 ;;
  *) echo "FATAL: bad role '$ROLE' (local | laptop)" >&2; exit 2 ;;
esac
OUT="$SHARE/$RUN_ID"
HOST="$(hostname)"

export CARC_SRC_ROOT="$REPO/src"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[everyply $(ts) $HOST/$ROLE] $*"; }
run() {
  if [ "$DRY" -eq 1 ]; then printf '[dry-run]'; printf ' %q' "$@"; printf '\n'; return 0; fi
  "$@"
}

# --------------------------------------------------------------------------- #
# guards                                                                       #
# --------------------------------------------------------------------------- #
require_blind() {
  local bc="$DIR/BLIND_COMMIT"
  if [ ! -f "$bc" ] || ! grep -qE '^[0-9a-f]{40}$' "$bc"; then
    log "!!! FATAL: $bc is missing or does not hold a 40-hex-char sha."
    log "!!! The ORCHESTRATOR writes it AFTER DESIGN.md + READ_RULE.md are frozen"
    log "!!! and committed. (--dry-run and --stage plan are exempt.)"
    exit 2
  fi
}

require_owed_builds() {
  local missing=0
  for f in "$REPO/scripts/tiletie/build_everyply_corpus.py" \
           "$REPO/scripts/tiletie/analyze_everyply.py"; do
    if [ ! -f "$f" ]; then log "!!! FATAL: OWED BUILD missing: $f"; missing=1; fi
  done
  if [ "$missing" -ne 0 ]; then
    log "!!! DESIGN §6.3 names both builds with their scope. This launcher REFUSES"
    log "!!! to half-run the pipeline. Build them (NEW FILES ONLY -- never edit"
    log "!!! build_positions.py / champ_picks.py / analyze_tiearb.py in a live tree),"
    log "!!! land their tests, then re-run."
    exit 2
  fi
}

# ⛔ READ_RULE §3 G-KNOWNGOOD. Runs the `knowngood` SUBCOMMAND ONLY -- `grade`,
# `preflight` and `sweep` call require_knowngood against constants hard-pinned to
# the OLD 733/399 corpus and would fail-always here (DESIGN §6.2).
gate_knowngood() {
  log "GATE G-KNOWNGOOD -- probe_pickers.py knowngood (must reproduce arb=+0.2065)"
  run nice -n 19 "$PY" "$REPO/scripts/tiletie/probe_pickers.py" knowngood \
      --out-dir "$DIR" >> "$LOGS/knowngood.log" 2>&1
  local rc=$?
  if [ "$DRY" -eq 0 ] && [ "$rc" -ne 0 ]; then
    log "!!! FATAL: G-KNOWNGOOD FAILED (rc=$rc). NO OTHER NUMBER IN THIS HARNESS"
    log "!!! MAY BE READ. See $DIR/KNOWNGOOD.json and $LOGS/knowngood.log."
    exit 2
  fi
  log "GATE G-KNOWNGOOD PASS"
}

# --------------------------------------------------------------------------- #
# RUN_LIVE.json freeze-latch sentinel -- the repo's PreToolUse hook refuses a   #
# MAIN-TREE git commit while this file exists. Dropped when a stage that writes #
# records starts, cleared on ANY exit via trap so an abort never leaves the     #
# tree latched. NEVER dropped on --dry-run or --stage plan (nothing runs).      #
# --------------------------------------------------------------------------- #
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("every-ply probe freeze-latch sentinel: a MAIN-TREE commit while "
                   "this leg is live can put two revisions into one run -- spawn "
                   "respawns and each new leg RE-IMPORTS FROM DISK. Cleared on the "
                   "launcher's EXIT trap."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  log "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

# --------------------------------------------------------------------------- #
# stages                                                                       #
# --------------------------------------------------------------------------- #

# STAGE plan -- pure query over the TRACKED census. No engine, no champion, no
# judge, no value. Costs ~0 and spends no blindness, so it is exempt from the
# BLIND_COMMIT guard.
stage_plan() {
  log "STAGE plan -- frame query, strata, seeded draw, holdout split, chunks"
  run nice -n 19 "$PY" "$REPO/scripts/tiletie/build_everyply_plan.py" \
      --out-dir "$DIR" \
      --n "$N_POOL" --n-priced "$N_PRICED" \
      --cap-per-game "$CAP_PER_GAME" --holdout-frac "$HOLDOUT_FRAC" \
      --chunks "$CHUNKS" >> "$LOGS/plan.log" 2>&1
  [ "$DRY" -eq 1 ] || log "STAGE plan DONE -> $DIR/{FRAME,POSITION_ORDER,PLAN_SUMMARY}.json + SELECTION.jsonl"
}

# STAGE corpus -- champion re-search + pooled-Q top-K arms + dedupe + leg files.
# ⚠️ Carries the root_stats_list dedup trap and the pre-committed leaf-top-K
# fallback (DESIGN §3.1). Which builder ran is STAMPED and printed on every branch.
stage_corpus() {
  local k="$1"
  if [ -f "$DIR/DONE_corpus_chunk$k" ]; then log "corpus chunk$k already DONE -- skipping"; return 0; fi
  log "STAGE corpus chunk$k -- fresh champion search x positions (t_champ ~13.8-25 s each)"
  run nice -n 19 "$PY" "$REPO/scripts/tiletie/build_everyply_corpus.py" \
      --mode arms --arm-builder leaf_topk \
      --selection "$DIR/SELECTION.jsonl" --chunk "$k" \
      --out-dir "$DIR/positions_chunk$k" \
      --rules-profile walled \
      --workers "$W" >> "$LOGS/corpus_chunk$k.log" 2>&1
  local rc=$?
  if [ "$DRY" -eq 0 ] && [ "$rc" -ne 0 ]; then
    log "corpus chunk$k FAILED rc=$rc -- stopping the chain; completed chunks remain"
    log "an unbiased read at their realized n (DESIGN §2.4). Re-run to resume."
    return "$rc"
  fi
  [ "$DRY" -eq 1 ] || touch "$DIR/DONE_corpus_chunk$k"
}

# STAGE arb -- tier1-greedy on ALL K=4 arms, rust backend, M=32, B=16.
stage_arb() {
  local k="$1"
  if [ -f "$DIR/DONE_arb_chunk$k" ]; then log "arb chunk$k already DONE -- skipping"; return 0; fi
  log "STAGE arb chunk$k -- tier1-greedy (rust) all K arms, M=$M_WORLDS"
  run nice -n 19 "$PY" "$REPO/scripts/tiletie/run_tiletie.py" \
      --positions-dir "$DIR/positions_chunk$k" \
      --judges tier1-greedy \
      --arb-backend rust \
      --m "$M_WORLDS" \
      --workers "$W" \
      --out-root "$OUT/arb/chunk$k" \
      --logs-dir "$LOGS" \
      --gate-out "$DIR/GATE_BACKEND_RECHECK_arb_chunk$k.json" \
      --manifest-out "$DIR/RUN_MANIFEST_arb_chunk$k.json" \
      --yes >> "$LOGS/arb_chunk$k.log" 2>&1
  local rc=$?
  if [ "$DRY" -eq 0 ] && [ "$rc" -ne 0 ]; then log "arb chunk$k FAILED rc=$rc"; return "$rc"; fi
  [ "$DRY" -eq 1 ] || touch "$DIR/DONE_arb_chunk$k"
}

# STAGE sel -- the SELECTIVE PRICING step (DESIGN §5.2). Reads the ARB records
# ONLY (never a clair-puct value -- that is what keeps it non-circular) and emits
# the reduced IF plan dir: arms_to_price = {champ} U {a_arb(fold1), a_arb(fold2)}.
# Positions where that set is a singleton are ZERO-FILLED, not dropped (G-ZEROFILL).
stage_sel() {
  local k="$1"
  if [ -f "$DIR/DONE_sel_chunk$k" ]; then log "sel chunk$k already DONE -- skipping"; return 0; fi
  log "STAGE sel chunk$k -- selective arm subset from ARB records (2.19x saving)"
  run nice -n 19 "$PY" "$REPO/scripts/tiletie/build_everyply_corpus.py" \
      --mode selective \
      --plan-dir "$DIR/positions_chunk$k" \
      --arb-records "$OUT/arb/chunk$k" \
      --m "$M_WORLDS" \
      --out-dir "$DIR/positions_if_chunk$k" \
      --zerofill-out "$DIR/ZEROFILL_chunk$k.json" >> "$LOGS/sel_chunk$k.log" 2>&1
  local rc=$?
  if [ "$DRY" -eq 0 ] && [ "$rc" -ne 0 ]; then log "sel chunk$k FAILED rc=$rc"; return "$rc"; fi
  [ "$DRY" -eq 1 ] || touch "$DIR/DONE_sel_chunk$k"
}

# STAGE if -- clair-puct pricing on the selective arm subset. THE FIRST STAGE
# THAT PRODUCES A PRICED VALUE => the first stage that spends blindness.
stage_if() {
  local k="$1"
  if [ -f "$DIR/DONE_if_chunk$k" ]; then log "if chunk$k already DONE -- skipping"; return 0; fi
  log "STAGE if chunk$k -- clair-puct (rust) selective, M=$M_WORLDS sims=$ORACLE_SIMS"
  run nice -n 19 "$PY" "$REPO/scripts/tiletie/run_tiletie.py" \
      --positions-dir "$DIR/positions_if_chunk$k" \
      --judges clair-puct \
      --m "$M_WORLDS" \
      --oracle-sims "$ORACLE_SIMS" \
      --workers "$W" \
      --out-root "$OUT/if/chunk$k" \
      --logs-dir "$LOGS" \
      --gate-out "$DIR/GATE_BACKEND_RECHECK_if_chunk$k.json" \
      --manifest-out "$DIR/RUN_MANIFEST_if_chunk$k.json" \
      --yes >> "$LOGS/if_chunk$k.log" 2>&1
  local rc=$?
  if [ "$DRY" -eq 0 ] && [ "$rc" -ne 0 ]; then log "if chunk$k FAILED rc=$rc"; return "$rc"; fi
  [ "$DRY" -eq 1 ] || touch "$DIR/DONE_if_chunk$k"
}

# STAGE analyze -- the join, the statistics, and the MECHANICAL READ_RULE §4
# adjudication. No owner call adjudicates any outcome.
stage_analyze() {
  log "STAGE analyze -- join + READ_RULE §4 mechanical adjudication"
  local ARB_ARGS=() IF_ARGS=()
  for k in $(seq 1 "$CHUNKS"); do
    ARB_ARGS+=(--arb-records "$OUT/arb/chunk$k")
    IF_ARGS+=(--if-records "$OUT/if/chunk$k")
  done
  run nice -n 19 "$PY" "$REPO/scripts/tiletie/analyze_everyply.py" \
      "${ARB_ARGS[@]}" "${IF_ARGS[@]}" \
      --plan-dir "$DIR" \
      --selection "$DIR/SELECTION.jsonl" \
      --holdout-games "$DIR/HOLDOUT_GAMES.json" \
      --knowngood "$DIR/KNOWNGOOD.json" \
      --blind-commit "$DIR/BLIND_COMMIT" \
      --boot-seed 20260823 \
      --out-dir "$DIR" >> "$LOGS/analyze.log" 2>&1
  local rc=$?
  if [ "$DRY" -eq 0 ] && [ "$rc" -ne 0 ]; then log "analyze FAILED rc=$rc"; return "$rc"; fi
  [ "$DRY" -eq 1 ] || touch "$DIR/DONE_analyze"
  log "STAGE analyze DONE -> $DIR/READOUT.md + READOUT.json"
}

# STAGE pilot -- DESIGN §12. Reads ONLY wall-clock, integrity and coverage. It
# does NOT read values_a/values_b/delta/kappa/q or anything derived from them.
stage_pilot() {
  log "STAGE pilot -- $PILOT_N positions from chunk 1's head, production knobs"
  log "⚠️ the pilot reads ONLY wall-clock, integrity and coverage -- NO statistic"
  run nice -n 19 "$PY" "$REPO/scripts/tiletie/build_everyply_corpus.py" \
      --mode arms --arm-builder leaf_topk --selection "$DIR/SELECTION.jsonl" --chunk 1 --limit "$PILOT_N" \
      --out-dir "$DIR/positions_pilot" --rules-profile walled --workers "$W" \
      >> "$LOGS/pilot.log" 2>&1
  local rc=$?
  if [ "$DRY" -eq 0 ] && [ "$rc" -ne 0 ]; then
    log "pilot corpus build FAILED rc=$rc"
    return "$rc"
  fi
  run nice -n 19 "$PY" "$REPO/scripts/tiletie/run_tiletie.py" \
      --positions-dir "$DIR/positions_pilot" --judges tier1-greedy --arb-backend rust \
      --m "$M_WORLDS" --workers "$W" --out-root "$OUT/pilot/arb" --logs-dir "$LOGS" \
      --gate-out "$DIR/GATE_BACKEND_RECHECK_pilot.json" \
      --manifest-out "$DIR/RUN_MANIFEST_pilot.json" --yes >> "$LOGS/pilot.log" 2>&1
  rc=$?
  if [ "$DRY" -eq 0 ] && [ "$rc" -ne 0 ]; then
    log "pilot arb FAILED rc=$rc"
    return "$rc"
  fi
  [ "$DRY" -eq 1 ] && return 0
  touch "$DIR/DONE_pilot"
  log "PILOT DONE -- apply DESIGN §12's mechanical rule before launching any chunk."
  log "  1. n_failed>0 | any crn_verified false | seed mismatch | coverage<$PILOT_N/$PILOT_N => ABORT"
  log "  2. H = SIZE-1 playouts * c / (3600*$W);  H<=3.0 => all $CHUNKS chunks;"
  log "     H>3.0 => first ceil($CHUNKS*3.0/H) chunks, floor 2"
  log "  3. if pooled-Q extraction failed, the leaf-top-K fallback engages ONCE, HERE, and FREEZES"
}

print_cost() {
  cat <<EOF
[cost] DESIGN §5.3 -- SIZE-1, from realized on-disk constants (lo / central / hi):
[cost]   corpus build (champion re-search, n=$N_POOL)      1.72 /  2.38 /  3.13 wh
[cost]   ARB judge    (tier1-greedy rust, all K, M=$M_WORLDS)  4.28 /  4.28 /  4.28 wh
[cost]   IF pricing   (clair-puct, SELECTIVE, n=$N_PRICED)    10.24 / 15.64 / 21.72 wh
[cost]   TOTAL                                          16.2 / 22.3 / 29.1 wh
[cost]   wall @ W=$W                                       1.0 /  1.4 /  1.8 h
[cost] ⛔ SIZE-2 / SIZE-3 are NOT funded and NOT pre-authorised (DESIGN §5.4).
EOF
}

# --------------------------------------------------------------------------- #
main() {
  mkdir -p "$LOGS"
  log "role=$ROLE W=$W share=$SHARE stage=$STAGE chunks=$CHUNKS out=$OUT"
  log "⛔ NO BAND IS CLAIMED ON ANY BRANCH (BAND_NOTE.md). 0 games on every branch."
  print_cost

  case "$STAGE" in
    plan)    stage_plan; return $? ;;
    pilot)   require_owed_builds; stage_pilot; return $? ;;
  esac

  require_owed_builds
  [ "$DRY" -eq 1 ] || require_blind

  if [ "$DRY" -eq 0 ]; then
    trap 'run_live_clear' EXIT INT TERM
    run_live_drop "every-ply probe SIZE-1 (role=$ROLE, stage=$STAGE)"
  fi

  case "$STAGE" in
    corpus)  for k in $(seq 1 "$CHUNKS"); do stage_corpus "$k" || return $?; done ;;
    arb)     for k in $(seq 1 "$CHUNKS"); do stage_arb    "$k" || return $?; done ;;
    sel)     for k in $(seq 1 "$CHUNKS"); do stage_sel    "$k" || return $?; done ;;
    if)      gate_knowngood
             for k in $(seq 1 "$CHUNKS"); do stage_if     "$k" || return $?; done ;;
    analyze) gate_knowngood; stage_analyze || return $? ;;
    all)
      stage_plan || return $?
      gate_knowngood
      for k in $(seq 1 "$CHUNKS"); do
        stage_corpus "$k" || return $?
        stage_arb    "$k" || return $?
        stage_sel    "$k" || return $?
        stage_if     "$k" || return $?
        log "===== chunk$k COMPLETE $(ts) -- the prefix is now an unbiased read at its realized n"
      done
      stage_analyze || return $?
      ;;
    *) echo "FATAL: bad stage '$STAGE'" >&2; exit 2 ;;
  esac

  if [ "$DRY" -eq 0 ] && [ -f "$DIR/DONE_analyze" ]; then
    run_live_clear
    log "DONE -- READOUT written, RUN_LIVE cleared."
    log "⚠️ The branch that fired is taken VERBATIM (READ_RULE §4). At SIZE-1 the"
    log "   POSITIVE branches E-FUND/E-CLEAN CANNOT fire (READ_RULE §0.A)."
  fi
}

main "$@"
