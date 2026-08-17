#!/usr/bin/env bash
# =============================================================================
# tiearb2 STAGE 2 PHASE B — THE TWO DECK-PAIRED GAME CELLS. PER-BOX DRIVER.
#
#   run_cells.sh <local|laptop> <BAND_SEED_START> [W]
#
# Prereg of record: measurement/tiearb2_stage2_20260817/DESIGN.md +
# READ_RULE.md (committed at b2faa238, BEFORE this instrument existed; amended
# pre-run at 6c281f9e, before the band claim and before game 1).
#
# TWO cells, n=800 deck-paired each (400 decks x 2 seats, CRN), on the SAME band
# and the SAME decks, fair PIMC via eval_fair_puct.py, BOTH arms at the deploy
# budget k8x1376 = 11008, fixed_v1 + R9, rust both sides, exact-K 2 shared:
#
#   ARB  --cand-tiearb-mode argmax   candidate = champion + the tie arbiter
#   RND  --cand-tiearb-mode random   candidate = champion + the arbiter running
#                                    the IDENTICAL playouts on the IDENTICAL
#                                    worlds at the IDENTICAL plies over the
#                                    IDENTICAL arm set, values DISCARDED, arm
#                                    drawn by a seeded RNG
#
# RND is the MATCHED-WALL-CLOCK CONTROL (DESIGN §1, condition (a)) and the
# mechanism statistic is D = M_arb - M_rnd. The two cells therefore MUST be run
# with identical everything except `--cand-tiearb-mode`; this driver is the only
# place that guarantees it.
#
# ⚠️ THE BAND IS A PARAMETER. This script NEVER claims a band and never runs
# claim_next_band.py. The orchestrator claims 132000000000 immediately before
# game 1 and passes it in. A band that is not claimed is `G-BAND` = U-UNREADABLE.
#
# ADJUDICATES NOTHING. No promotion, no PRODUCTION.yaml, no results.csv row, no
# claim row, and DELIBERATELY no menu_block_summary.py — the wiring gates must be
# read from the manifest BEFORE any strength number is opened. This driver emits
# verdicts/GATES_<cell>.json (pass/fail only) and leaves the read-out to the
# reading session.
#
# ⚠️⚠️ THE LIVENESS GATE IS INVERTED FOR THIS SURFACE — the single easiest way to
# produce a meaningless null. The arbiter's knobs are SearchConfig, NOT
# LeafConfig, so NO LEAF HASH MOVES: the candidate's leaf hash must EQUAL the
# champion's a36d2e15a3b3d71d, and a MOVED hash is a DEFECT. Liveness rests
# entirely on
#   (J4)  the RESOLVED cand_tiearb dict in the manifest,
#   (FIRE) summary.json::tiearb_phi, the realized firing rate, and
#   (J13) preflight_tiearb.py's TWO-SIDED control — run BELOW, BEFORE game 1, on
#         THIS box, output captured under verdicts/. If it fails, THIS DRIVER
#         REFUSES TO PLAY: "Without this a zeroed dose grades a perfect
#         champion-vs-champion null wearing the shape of a real cell."
#
# DETACH IT (Mac->Windows->WSL SIGHUP + WSL VM teardown both kill tty jobs):
#   setsid nohup nice -n 19 bash \
#     /home/doctor/projects/carcassone/measurement/tiearb2_stage2_20260817/run_cells.sh \
#     local 132000000000 > .../logs/driver_local.log 2>&1 < /dev/null & disown
#
# RESUMABLE: a cell with its DONE marker is skipped; otherwise the harness
# resumes from the seed*.json records on the share. The pre-flight re-runs on
# every attempt (per-box wheel guard); the FIRST attempt's verdict is preserved
# for gate J13.
# =============================================================================
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"

BOX="${1:?usage: run_cells.sh <local|laptop> <BAND_SEED_START> [W]}"
BAND="${2:?usage: run_cells.sh <local|laptop> <BAND_SEED_START> [W]}"
case "$BAND" in ''|*[!0-9]*) echo "BAND must be numeric, got '$BAND'"; exit 2 ;; esac

case "$BOX" in
  local)  SHARE="$SHARE_LOCAL";  REPO="$REPO_LOCAL";  ROLE=primary; W_DEFAULT="$W_LOCAL" ;;
  laptop) SHARE="$SHARE_REMOTE"; REPO="$REPO_REMOTE"; ROLE=helper;  W_DEFAULT="$W_LAPTOP" ;;
  *) echo "BOX must be local|laptop, got '$BOX'"; exit 2 ;;
esac
W="${3:-${W:-$W_DEFAULT}}"

# ⚠️ MUST run from the repo root. Claude Code silently drops `cd` from inline SSH
# commands, which is why the two-box launcher PIPES this file
# (`ssh laptop 'bash -s' < run_cells.sh`) and why the cd lives HERE, in the
# script, rather than in the ssh command line.
cd "$REPO" || { echo "FATAL: cannot cd to repo root '$REPO'" >&2; exit 1; }

PY="$REPO/.venv/bin/python"
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
DIR="$HERE"
LOGS="$DIR/logs"
OUT="$SHARE/$RUN_ID"
MAXITER="${MAXITER:-80}"
N="${N:-$N_GAMES}"
HOST="$(hostname)"

mkdir -p "$LOGS" "$DIR/verdicts" "$OUT"
ts() { date +%F_%T; }
log() { echo "[tiearb2-s2 $(ts)] $*"; }

# ---- canonical leaf env (VERBATIM from menu_fair_cell.sh): the INTACT v2.9.2
# curve125 champion (hash a36d2e15a3b3d71d). This cell injects NO leaf override
# on either side, so BOTH arms resolve their leaf from exactly this env.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
# ⚠️ R9 is env-latched at IMPORT, so it MUST be exported before the harness starts.
export CARCASSONNE_FIX_R9=1
# READ_RULE G-TOOL: the SAME rust toolchain on both boxes.
export RUSTUP_TOOLCHAIN="$RUST_TOOLCHAIN"

log "=== START box=$BOX host=$HOST band=$BAND W=$W n=$N ==="
log "repo_head=$(git -C "$REPO" rev-parse --short HEAD)  out=$OUT"
log "cells: $CELL_ARB (argmax) + $CELL_RND (random) — same band, same decks"
log "knob: --cand-tiearb-enabled --cand-tiearb-b $TIEARB_B --cand-tiearb-j $TIEARB_J --cand-tiearb-eps $TIEARB_EPS --cand-tiearb-salt $TIEARB_SALT"

if [ -f "$DIR/DONE_STAGE2_PHASE_B" ]; then
  log "both cells already DONE (marker present) -- nothing to do"; exit 0
fi

# ==========================================================================
# TOOLCHAIN STAMP (READ_RULE G-TOOL). Recorded per box so a mixed-build cell is
# detectable off disk instead of inferred.
# ==========================================================================
{
  echo "host $HOST"
  echo "rustup_toolchain ${RUSTUP_TOOLCHAIN:-unset}"
  rustc --version 2>&1
  cargo --version 2>&1
  echo "code_rev $(git -C "$REPO" rev-parse HEAD)"
  echo "code_rev_short $(git -C "$REPO" rev-parse --short HEAD)"
  echo "dirty $(git -C "$REPO" status --porcelain | wc -l)"
  "$PY" -c 'import carc_rs,json;print("carc_rs",carc_rs.__version__,carc_rs.__file__);print("tile_digests",json.dumps(list(carc_rs.tile_data_digests())))' 2>&1
} > "$DIR/verdicts/TOOLCHAIN_${HOST}.txt"
cat "$DIR/verdicts/TOOLCHAIN_${HOST}.txt"

# ==========================================================================
# PRE-FLIGHT (prereg gate J13) — BEFORE GAME 1, ON THIS BOX. HARD BLOCKER.
# TWO-SIDED: the arbiter must CHANGE the pick at a constructed tied ply AND
# leave root_leaf_value_bits UNCHANGED. Also re-checks J1 (EQUALITY) and J4
# (the resolved knob) through the production construction path.
# ==========================================================================
PF_NOW="$DIR/verdicts/PREFLIGHT_${HOST}_$(date +%s).json"
PF_FIRST="$DIR/verdicts/PREFLIGHT_${HOST}_FIRST.json"
log "--- PRE-FLIGHT (wheel + J1 + J4 + the TWO-SIDED J13 control) on $HOST ---"
PREFLIGHT_TIEARB_B="$TIEARB_B" PREFLIGHT_TIEARB_J="$TIEARB_J" \
PREFLIGHT_TIEARB_SALT="$TIEARB_SALT" PREFLIGHT_TIEARB_EPS="$TIEARB_EPS" \
  nice -n "$NICE" "$PY" "$DIR/preflight_tiearb.py" > "$PF_NOW" 2>"$LOGS/preflight_${HOST}.log"
pfrc=$?
cat "$PF_NOW"
if [ "$pfrc" -ne 0 ]; then
  log "!!! PRE-FLIGHT FAILED (rc=$pfrc) on $HOST -- see $PF_NOW and $LOGS/preflight_${HOST}.log"
  log "!!! REFUSING TO PLAY. A dead arbitration surface grades a champion-vs-champion"
  log "!!! null that no wiring gate on this surface could ever detect. Rebuild the"
  log "!!! carc_rs wheel on THIS box (RUSTUP_TOOLCHAIN=$RUST_TOOLCHAIN maturin develop --release)."
  { echo "$(ts)"; echo "PRE-FLIGHT FAILED rc=$pfrc on $HOST"; echo "see $PF_NOW"; } > "$DIR/FAILED_PREFLIGHT_${HOST}"
  exit 13
fi
[ -f "$PF_FIRST" ] || cp "$PF_NOW" "$PF_FIRST"
log "PRE-FLIGHT PASS on $HOST -> $PF_NOW ; first-attempt copy $PF_FIRST"

# ==========================================================================
# CLOCK-SKEW GUARD (VERBATIM from menu_fair_cell.sh). claim.py:is_stale()
# compares the SHARE's mtime clock against this client's time.time(); a drifted
# client sees every sibling claim as stale and STEALS it, silently halving
# throughput with no error.
# ==========================================================================
probe="$OUT/.clock_probe_$$"
: > "$probe" 2>/dev/null
if [ -f "$probe" ]; then
  skew=$(( $(date +%s) - $(stat -c %Y "$probe") )); rm -f "$probe"; askew=${skew#-}
  if [ "$askew" -gt 60 ]; then
    log "FATAL: clock skew vs the share = ${skew}s (>60s). Fix with: sudo -n date -s @<share-host-epoch>"
    exit 3
  fi
  log "clock-skew guard OK (${skew}s)"
else
  log "WARNING: could not write a clock probe to $OUT - skew unchecked"
fi

count_records() { find "$1" -maxdepth 1 -name 'seed*.json' 2>/dev/null | wc -l; }
# Claims-without-records only, and only ones older than $2 minutes, so a claim
# taken seconds ago by a sibling is never swept.
clean_stale_claims() {
  local d="$1" age="${2:-}"; local a=(-maxdepth 1 -name 'seed*.claim')
  [ -n "$age" ] && a+=(-mmin "+$age")
  find "$d" "${a[@]}" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}

# ==========================================================================
# run_cell <sub> <mode>
# The two invocations differ in EXACTLY ONE ARGUMENT (`--cand-tiearb-mode`).
# That is the whole design: RND is not a different experiment, it is the same
# experiment with the argmax replaced by a seeded draw.
# ==========================================================================
run_cell() {
  local SUB="$1" MODE="$2"
  local dir="$OUT/$SUB"
  mkdir -p "$dir"
  if [ -f "$DIR/DONE_$SUB" ]; then
    log "cell $SUB already DONE (marker present) -- skipping"; return 0
  fi
  local args=(--info fair --opponent fair-champion --backend rust
              --k-dets "$K_DETS" --sims "$SIMS"
              --opp-k-dets "$K_DETS" --opp-sims "$SIMS" --exact-k "$EXACT_K"
              --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
              --n "$N" --paired --seed-start "$BAND"
              --rules-profile fixed_v1 --workers "$W"
              --out-root "$OUT" --out-subdir "$SUB"
              --shared-claim --claim-host "tiearb2s2-$ROLE-$HOST" --claim-stale-secs 1800
              --no-results-csv
              --cand-tiearb-enabled
              --cand-tiearb-b "$TIEARB_B"
              --cand-tiearb-j "$TIEARB_J"
              --cand-tiearb-mode "$MODE"
              --cand-tiearb-salt "$TIEARB_SALT"
              --cand-tiearb-eps "$TIEARB_EPS")
  log "cell $SUB (mode=$MODE) argv: $PY -u $HARNESS ${args[*]}"

  clean_stale_claims "$dir" 20
  local t0 iter rc GOT secs
  t0=$(date +%s); iter=0
  while [ "$(count_records "$dir")" -lt "$N" ] && [ "$iter" -lt "$MAXITER" ]; do
    nice -n "$NICE" "$PY" -u "$HARNESS" "${args[@]}" >> "$LOGS/cell_$SUB.log" 2>&1
    # ⚠️ CAPTURE rc ON ITS OWN LINE (a `$(ts)` in the same echo clobbers $?).
    rc=$?
    iter=$((iter+1))
    log "cell $SUB harness pass $iter rc=$rc records=$(count_records "$dir")/$N"
    clean_stale_claims "$dir" 20
    [ "$(count_records "$dir")" -lt "$N" ] && sleep 20
  done
  secs=$(( $(date +%s) - t0 ))
  GOT=$(count_records "$dir")
  log "cell $SUB END records=$GOT/$N in ${secs}s after $iter pass(es)"

  # ---- the wiring gates. PASS/FAIL ONLY -- no strength number is read here.
  MANIFEST="$dir/manifest.json" SUMMARY="$dir/summary.json" RECDIR="$dir" \
  CHAMP_HASH="$CHAMP_LEAF_HASH" EXPECT_MODE="$MODE" EXPECT_B="$TIEARB_B" \
  EXPECT_J="$TIEARB_J" EXPECT_SALT="$TIEARB_SALT" EXPECT_EPS="$TIEARB_EPS" \
  EXPECT_SEED="$BAND" EXPECT_N="$N" GOT_N="$GOT" SUB="$SUB" \
  PREFLIGHT="$PF_FIRST" ELAPSED="$secs" WORKERS="$W" BOX="$BOX" \
  "$PY" "$DIR/gate_cell.py" > "$DIR/verdicts/GATES_$SUB.json" 2>"$LOGS/gates_$SUB.log"
  local grc=$?
  local GPASS
  GPASS=$("$PY" -c "import json;print(json.load(open('$DIR/verdicts/GATES_$SUB.json'))['all_gates_pass'])" 2>/dev/null || echo "UNREADABLE")
  log "cell $SUB wiring gates: all_gates_pass=$GPASS (gate-script rc=$grc) -> $DIR/verdicts/GATES_$SUB.json"

  local MIN=$(( N * 9 / 10 ))
  if [ "$GOT" -ge "$MIN" ]; then
    { echo "$(ts)"; echo "records $GOT/$N"; echo "band_seed_start $BAND";
      echo "cand_tiearb enabled=true B=$TIEARB_B J=$TIEARB_J mode=$MODE salt=$TIEARB_SALT eps=$TIEARB_EPS";
      echo "cand_leaf_hash_expected $CHAMP_LEAF_HASH  <-- EQUALITY: this surface moves NO leaf hash";
      echo "preflight_first $PF_FIRST";
      echo "workers $W (box $BOX only)"; echo "elapsed_s $secs";
      echo "wiring_gates_all_pass $GPASS";
      echo "NOT ADJUDICATED - read READ_RULE.md §3 preconditions before any number."; } > "$DIR/DONE_$SUB"
    log "cell $SUB DONE ($GOT/$N) -> $DIR/DONE_$SUB"
    [ "$GOT" -lt "$N" ] && log "cell $SUB INCOMPLETE but >=90% - the 90% VOID rule applies at read time"
    return 0
  fi
  { echo "$(ts)"; echo "records $GOT/$N (<90%) - VOID by the standing rule";
    echo "see $LOGS/cell_$SUB.log"; } > "$DIR/FAILED_$SUB"
  log "!!! cell $SUB FAILED ($GOT/$N < 90%) -> $DIR/FAILED_$SUB"
  return 11
}

# ⚠️ CHAINED WITH `;`, NOT `&&`: a VOID first cell must not silently cancel the
# second. Both cells are attempted, both markers are written, and the read-out
# decides.
rc_arb=0; rc_rnd=0
run_cell "$CELL_ARB" argmax; rc_arb=$?
run_cell "$CELL_RND" random; rc_rnd=$?

log "cell results: $CELL_ARB rc=$rc_arb  $CELL_RND rc=$rc_rnd"
if [ "$rc_arb" -eq 0 ] && [ "$rc_rnd" -eq 0 ]; then
  { echo "$(ts)"; echo "box $BOX host $HOST band $BAND workers $W";
    echo "$CELL_ARB DONE"; echo "$CELL_RND DONE";
    echo "NOT ADJUDICATED - the read-out is the reading session's."; } > "$DIR/DONE_STAGE2_PHASE_B_${HOST}"
  log "=== BOTH CELLS COMPLETE on $HOST (band $BAND). Nothing adjudicated, nothing promoted. ==="
  exit 0
fi
log "!!! at least one cell did not reach the 90% bar on this box (see FAILED_* markers)"
exit 11
