#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — ONE CELL of the out-of-lineage pricing of the tie arbiter.
#
#   run_cell.sh <CELL_A|CELL_B name>
#
# Prereg of record: DESIGN.md + READ_RULE.md in this directory, both committed
# BEFORE the band claim and BEFORE game 1.
#
# The two cells differ in EXACTLY the six `--champ-tiearb-*` arguments, which are
# ABSENT on CELL A and PRESENT on CELL B (DESIGN §3, READ_RULE `G-ARB`). Nothing
# else differs — same band, same decks, same seats, same budget, same rules, same
# jar, same worker count. This script is the ONLY place that guarantees it, which
# is why the fully-resolved argv is printed to the log before every pass: the
# diff between the two cells must be auditable from the logs alone.
#
# ⚠️ CLAIMS NO BAND. The band is read from the sentinel written by claim_band.sh
# and this script ABORTS if the sentinel is absent — a band that was not claimed
# before game 1 is `G-BAND` = U-UNREADABLE.
#
# ADJUDICATES NOTHING. No strength number is read here, no results.csv row is
# written, no analyzer is run. It plays games and writes a completion marker.
#
# SMOKE MODE (env `SMOKE=1`, driven by `launch.sh --smoke`): the SAME code path
# at `--decks $SMOKE_DECKS` on a throwaway seed base, into `smoke_<cell>.jsonl`,
# at `W_SMOKE` workers. It NEVER reads or writes the band sentinel and NEVER
# writes a DONE/FAILED marker for the real cells (DESIGN §6.2 — per-worker RSS
# and throughput at W24 are measured before the long run commits).
#
# DETACH IT. `launch.sh` wraps the two calls in one `setsid nohup` chain; a
# Mac-sleep SIGHUP or a WSL VM teardown kills anything tty-attached.
#
# RESUMABLE / IDEMPOTENT: a cell whose DONE marker exists is skipped with rc=0
# and replays nothing; otherwise match.py's `--resume` skips every
# (deck_seed, champ_seat, replicate) already in the jsonl.
# =============================================================================
set -euo pipefail
. "$(dirname "$0")/WORKERS.conf"

CELL="${1:?usage: run_cell.sh <$CELL_A|$CELL_B>}"

REPO="$REPO_LOCAL"
PY="$REPO/.venv/bin/python"
DRIVER="$REPO/scripts/jcz_match/match.py"
LOGS="$RUN_DIR/logs"
HOST="$(hostname)"
SMOKE="${SMOKE:-0}"
SMOKE_DECKS="${SMOKE_DECKS:-4}"
SMOKE_SEED_BASE="${SMOKE_SEED_BASE:-900000200000}"
MAXITER="${MAXITER:-20}"

mkdir -p "$LOGS" "$RUN_DIR/verdicts" "$SHARE_RUN_LOCAL"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[jcz-tiearb $(ts) $CELL] $*"; }
die() { log "FATAL: $*"; exit "${2:-1}"; }

# ---- the cell name is a closed set. A typo must not silently create a third cell.
case "$CELL" in
  "$CELL_A") ARB=no  ;;
  "$CELL_B") ARB=yes ;;
  *) echo "FATAL: cell must be '$CELL_A' or '$CELL_B', got '$CELL'" >&2; exit 2 ;;
esac

# =============================================================================
# CANONICAL LEAF ENV — copied VERBATIM from
# measurement/tiearb2_stage2_20260817/run_cells.sh (the INTACT v2.9.2 curve125
# champion, leaf hash a36d2e15a3b3d71d). This cell injects NO leaf override on
# either side, so BOTH cells resolve their leaf from exactly this env and
# `G-LEAF` is an EQUALITY gate: the arbiter moves NO leaf hash.
# =============================================================================
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
# ⚠️ R9 is env-latched at IMPORT, so it MUST be exported before the harness starts.
# match.py RAISES if it is off — it is the only configuration in which our engine
# and JCZ are provably rules-identical (DESIGN §2).
export CARCASSONNE_FIX_R9="$FIX_R9"
# READ_RULE G-TOOL: the pinned rust toolchain.
export RUSTUP_TOOLCHAIN="$RUST_TOOLCHAIN"

# =============================================================================
# G-JCZ — the pinned jar, verified by CONTENT and not by path. A jar swapped
# under us is the one provenance failure that no manifest field would catch,
# because the manifest stamps the path it was handed.
# =============================================================================
[ -f "$JCZ_JAR" ] || die "JCZ jar not found at $JCZ_JAR (G-JCZ)"
JAR_SHA="$(sha256sum "$JCZ_JAR" | awk '{print $1}')"
if [ "$JAR_SHA" != "$JCZ_JAR_SHA256" ]; then
  log "!!! G-JCZ VIOLATION — Engine.jar sha256 MISMATCH"
  log "!!!   expected $JCZ_JAR_SHA256"
  log "!!!   observed $JAR_SHA"
  log "!!!   path     $JCZ_JAR"
  die "refusing to play against an unpinned JCZ build" 21
fi
log "G-JCZ jar sha256 OK ($JAR_SHA)"

# ---- the AI shim must already be compiled. Without it every `%aimove` is an
# unknown directive JCZ answers with SILENCE, so the fleet HANGS rather than
# failing — exactly how the 2026-08-09 smoke was lost.
AI_CLASSES="${JCZ_AI_CLASSES:-$HOME/jcz_spike/ai_classes}"
[ -d "$AI_CLASSES" ] || die "JCZ AI shim classes missing at $AI_CLASSES — run scripts/jcz_match/build_ai_shim.sh" 22

# =============================================================================
# THE BAND — read, never claimed. Sentinel absent ⇒ the band was not claimed
# before game 1 ⇒ `G-BAND` VOIDS the run. Fail closed, here, before game 1.
# =============================================================================
if [ "$SMOKE" = "1" ]; then
  BAND="$SMOKE_SEED_BASE"
  N_DECKS="$SMOKE_DECKS"
  W="$W_SMOKE"
  OUT_JSONL="$RUN_DIR/smoke_${CELL}.jsonl"
  LOGFILE="$LOGS/smoke_${CELL}.log"
  log "SMOKE MODE: decks=$N_DECKS seed_base=$BAND (THROWAWAY, not the claimed band) W=$W"
  log "SMOKE MODE: no band is claimed, no DONE/FAILED marker for the real cell is written"
else
  [ -f "$BAND_SENTINEL" ] || die "band sentinel $BAND_SENTINEL is ABSENT — run claim_band.sh BEFORE game 1 (G-BAND)" 23
  BAND="$(grep -m1 -E '^[0-9]+$' "$BAND_SENTINEL" || true)"
  case "$BAND" in ''|*[!0-9]*) die "band sentinel $BAND_SENTINEL holds no numeric band" 23 ;; esac
  N_DECKS="$DECKS"
  W="$W_LOCAL"
  OUT_JSONL="$RUN_DIR/${CELL}.jsonl"
  LOGFILE="$LOGS/${CELL}.log"
fi
TARGET=$(( N_DECKS * 2 ))          # --champ-seat both ⇒ two games per deck

DONE_MARKER="$RUN_DIR/DONE_${CELL}"
FAIL_MARKER="$RUN_DIR/FAILED_${CELL}"
SHARE_DONE="$SHARE_RUN_LOCAL/DONE_${CELL}"

# ---- IDEMPOTENCE: a finished cell replays nothing.
if [ "$SMOKE" != "1" ] && [ -f "$DONE_MARKER" ]; then
  log "DONE marker already present at $DONE_MARKER — nothing to do, exiting 0"
  exit 0
fi

# =============================================================================
# THE ARGV. Common to both cells; CELL B additionally and ONLY gets the six
# `--champ-tiearb-*` arguments (DESIGN §3, READ_RULE `G-ARB`).
# =============================================================================
ARGS=(--decks "$N_DECKS"
      --seed-base "$BAND"
      --champ-seat both
      --workers "$W"
      --jar "$JCZ_JAR"
      --ai-class "$JCZ_AI_CLASS"
      --out "$OUT_JSONL"
      --resume)

if [ "$ARB" = "yes" ]; then
  ARGS+=(--champ-tiearb-enabled
         --champ-tiearb-b "$TIEARB_B"
         --champ-tiearb-j "$TIEARB_J"
         --champ-tiearb-mode "$TIEARB_MODE"
         --champ-tiearb-salt "$TIEARB_SALT"
         --champ-tiearb-eps "$TIEARB_EPS")
fi

GIT_HEAD="$(git -C "$REPO" rev-parse HEAD)"

# ⚠️ `if`, not `&& || `: under `set -e` an AND-OR list whose first command fails
# is a failed command, and this function is called from loop conditions.
count_records() {
  if [ -f "$OUT_JSONL" ]; then wc -l < "$OUT_JSONL" | tr -d ' '; else echo 0; fi
}

{
  echo "==================================================================="
  echo "[jcz-tiearb $(ts)] CELL=$CELL arbiter=$ARB host=$HOST smoke=$SMOKE"
  echo "[jcz-tiearb] band=$BAND decks=$N_DECKS target_games=$TARGET workers=$W nice=$NICE"
  echo "[jcz-tiearb] repo_head=$GIT_HEAD"
  echo "[jcz-tiearb] jar=$JCZ_JAR sha256=$JAR_SHA ai_class=$JCZ_AI_CLASS ai_classes=$AI_CLASSES"
  echo "[jcz-tiearb] rules: profile=$RULES_PROFILE (hard-coded in match.py) CARCASSONNE_FIX_R9=$CARCASSONNE_FIX_R9"
  echo "[jcz-tiearb] leaf of record (EQUALITY gate G-LEAF): $CHAMP_LEAF_HASH"
  echo "[jcz-tiearb] RESOLVED ARGV:"
  echo "[jcz-tiearb]   $PY -u $DRIVER ${ARGS[*]}"
  echo "==================================================================="
} | tee -a "$LOGFILE"

log "starting — full log $LOGFILE"

rc=0
iter=0
t0=$(date +%s)
prev=$(count_records)
while [ "$(count_records)" -lt "$TARGET" ] && [ "$iter" -lt "$MAXITER" ]; do
  set +e
  nice -n "$NICE" "$PY" -u "$DRIVER" "${ARGS[@]}" >> "$LOGFILE" 2>&1
  rc=$?
  set -e
  iter=$((iter + 1))
  got=$(count_records)
  log "pass $iter rc=$rc records=$got/$TARGET"
  if [ "$got" -le "$prev" ] && [ "$rc" -eq 0 ]; then
    log "pass $iter made NO progress at rc=0 — the remaining cells are unplayable, not stalled; stopping"
    break
  fi
  prev="$got"
  if [ "$got" -lt "$TARGET" ]; then sleep 5; fi   # short poll sleep, < 10 s by house rule
done
secs=$(( $(date +%s) - t0 ))
GOT=$(count_records)
log "END records=$GOT/$TARGET in ${secs}s after $iter pass(es), last rc=$rc"

if [ "$SMOKE" = "1" ]; then
  { echo "smoke_cell $CELL"; echo "records $GOT/$TARGET"; echo "seed_base $BAND (THROWAWAY)";
    echo "workers $W"; echo "elapsed_s $secs"; echo "last_rc $rc";
    echo "utc $(ts)"; echo "git_head $GIT_HEAD";
    echo "NOT A REAL CELL — no band claimed, nothing adjudicated."; } \
      > "$RUN_DIR/SMOKE_${CELL}.txt"
  log "smoke summary -> $RUN_DIR/SMOKE_${CELL}.txt"
  if [ "$GOT" -ge "$TARGET" ]; then exit 0; fi
  exit 11
fi

if [ "$GOT" -ge "$TARGET" ]; then
  {
    echo "cell $CELL"
    echo "band $BAND"
    echo "decks_requested $N_DECKS"
    echo "games_requested $TARGET"
    echo "games_recorded $GOT"
    echo "utc $(ts)"
    echo "git_head $GIT_HEAD"
    echo "host $HOST"
    echo "workers $W"
    echo "elapsed_s $secs"
    echo "passes $iter"
    echo "out $OUT_JSONL"
    echo "arbiter $ARB"
    if [ "$ARB" = "yes" ]; then
      echo "champ_tiearb enabled=true B=$TIEARB_B J=$TIEARB_J mode=$TIEARB_MODE salt=$TIEARB_SALT eps=$TIEARB_EPS"
    else
      echo "champ_tiearb ABSENT (G-ARB: CELL A must carry NO champ_tiearb key)"
    fi
    echo "jcz_jar_sha256 $JAR_SHA"
    echo "cand_leaf_hash_expected $CHAMP_LEAF_HASH  <-- EQUALITY: this surface moves NO leaf hash"
    echo "NOT ADJUDICATED — read READ_RULE.md §3 preconditions before any number."
  } | tee "$DONE_MARKER" > "$SHARE_DONE"
  log "DONE ($GOT/$TARGET) -> $DONE_MARKER and $SHARE_DONE"
  rm -f "$FAIL_MARKER"
  exit 0
fi

{
  echo "cell $CELL"
  echo "band $BAND"
  echo "games_requested $TARGET"
  echo "games_recorded $GOT"
  echo "exit_code $rc"
  echo "passes $iter"
  echo "elapsed_s $secs"
  echo "utc $(ts)"
  echo "git_head $GIT_HEAD"
  echo "log $LOGFILE"
  echo "resume with: $0 $CELL   (match.py --resume skips what is already recorded)"
} > "$FAIL_MARKER"
log "!!! FAILED ($GOT/$TARGET, rc=$rc) -> $FAIL_MARKER"
exit 11
