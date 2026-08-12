#!/bin/bash
# OVERNIGHT SERIAL CHAIN 2026-08-12 — blocks D1 -> S1.
#
#   D1 = targeted-denial dose screen   (measurement/denial_screen_20260811/PREREG_DRAFT.md)
#        1..4 dose cells x n=200 deck-paired, ONE shared fresh band (CRN), at the 2750
#        ablation instrument (eval_puct_priors.py), rust both sides, fixed_v1+R9.
#   S1 = sims-split screen             (the play-time knob the simsplit census licenses;
#        measurement/simsplit_census_20260811/PREREG.md is the PRE-GATE, not this A/B)
#        1 cell n=200 deck-paired at the production budget k8x1376 both arms, candidate
#        carrying --sims-tile/--sims-meeple at FIXED per-turn total. HARD-GATED, see below.
#
# Successor to scripts/classical_search/menu_chain.sh; same shape on purpose (sequential
# blocks, per-block DONE sentinels, resumable --shared-claim legs, fail-stop verification,
# two-box work stealing). Read that file's header for the trap list — every one of them
# applies here and is reproduced, not re-derived.
#
# WHAT THIS SCRIPT DOES NOT DO. It adjudicates NOTHING: no verdict, no promotion, no
# results.csv row, no edit to governance/PRODUCTION.yaml, no top-up. It writes per-block
# extracts and stops. Reading and close-out belong to the orchestrating session.
#
# ============================ THE THREE THINGS THAT MATTER =========================
# 1. NO DEFAULTED KNOB VALUES. DENIAL_DOSES / DENIAL_SIZE_MIN / DENIAL_OPEN_MAX (and, for
#    S1, SIMS_TILE / SIMS_MEEPLE) are REQUIRED parameters with NO defaults. A defaulted
#    dose would run a cell nobody chose and nobody pre-registered.
# 2. CAPABILITY BEFORE COMPUTE. The installed carc_rs wheel predates BOTH knobs. A
#    candidate arm whose knob the loaded build ignores still runs, still completes, and
#    produces a beautiful, meaningless null. So every block probes, ON BOTH BOXES, that
#    the knob (a) exists, (b) is accepted by the loaded native build, and (c) CHANGES THE
#    NUMBER — and refuses to launch otherwise. See chain_capability_probe.py.
#    Belt AND braces: the candidate leaf hash is computed from the knob spec before game 1
#    and re-checked against the cell's own manifest at read time
#    (menu_block_summary.py --expect-cand-leaf-hash).
# 3. S1 IS HARD-GATED ON A HUMAN GO-FILE. The split knob's byte-identity gate may not come
#    back clean. S1 runs ONLY if BOTH: (a) $DIR/S1_AUTHORIZED exists (Joshua writes it by
#    hand — the chain NEVER creates it), and (b) eval_fair_puct.py actually advertises
#    --sims-tile/--sims-meeple. Either missing => S1 SKIPS LOUDLY and the chain finishes
#    clean. An unverified bit-exactness knob must not silently enter a measurement.
# ===================================================================================
#
# Bands: each block claims its OWN band from governance/BAND_REGISTRY.csv at ITS OWN
# launch (claim_next_band.py: next free above the high-water mark, memoized in a sentinel
# so a resume re-uses it instead of burning a second band). A block that never runs never
# claims. The chain writes the registry row; close-out flips it.
#
# Launch (the mkdir is not optional: the shell opens the redirect BEFORE this script runs,
# and logs/ is not a tracked directory):
#   mkdir -p measurement/night_chain_20260812/logs
#   DENIAL_DOSES="1.0,2.0" DENIAL_SIZE_MIN=5 DENIAL_OPEN_MAX=3 \
#   setsid nohup nice -n 19 bash scripts/classical_search/denial_simsplit_chain.sh \
#     >> measurement/night_chain_20260812/logs/chain.log 2>&1 < /dev/null &
# Rehearse:
#   DENIAL_DOSES="1.0,2.0" DENIAL_SIZE_MIN=5 DENIAL_OPEN_MAX=3 \
#     bash scripts/classical_search/denial_simsplit_chain.sh --dry-run
set -u

REPO="${CHAIN_REPO:-/home/doctor/projects/carcassone}"
# ⚠️ The interpreter is the MAIN TREE's venv even when CHAIN_REPO points at a git worktree:
# the venv is editable-installed against the main tree and a worktree has no venv of its own
# (worktree-isolation rule). CHAIN_PY overrides if you really mean something else.
PY="${CHAIN_PY:-/home/doctor/projects/carcassone/.venv/bin/python}"
REGISTRY="${CHAIN_REGISTRY:-$REPO/governance/BAND_REGISTRY.csv}"
DIR=$REPO/measurement/night_chain_20260812
LOGS=$DIR/logs
SHARE=/mnt/c/carc-shared            # LOCAL prefix
LSHARE=/mnt/carc-shared             # LAPTOP prefix (different mount, same store)
OUT=$SHARE/night_chain_20260812
LOUT=$LSHARE/night_chain_20260812
LAPTOP="${CHAIN_LAPTOP:-laptop-wsl}"
W_LOCAL=${W_LOCAL:-30}              # Joshua's numbers for tonight
W_LAPTOP=${W_LAPTOP:-22}

D1_N=${D1_N:-200}                   # per cell, deck-paired (100 decks x 2 seats)
S1_N=${S1_N:-200}
D1_SIMS=${D1_SIMS:-2750}            # the ablation instrument's per-side budget
S1_KDETS=${S1_KDETS:-8}             # production champion budget, both arms
S1_SIMS=${S1_SIMS:-1376}
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

PROBE=$REPO/scripts/classical_search/chain_capability_probe.py
CELLCMP=$REPO/scripts/classical_search/chain_compare_cell_tables.py
CLAIM=$REPO/scripts/classical_search/claim_next_band.py
SUMMARY=$REPO/scripts/classical_search/menu_block_summary.py
FAIRHARNESS=$REPO/scripts/classical_search/eval_fair_puct.py
S1_GO=$DIR/S1_AUTHORIZED

# ---- canonical leaf env, exported HERE as well as in every launcher ----------------
# The capability probe resolves DEFAULT_CONFIG (the OPPONENT's leaf and the candidate's
# base) from this env at import time and asserts it hashes to a36d2e15a3b3d71d. Without
# these exports the probe computes candidate hashes against a DIFFERENT base leaf, and the
# expected-hash gate would then compare a cell against a hash from another dialect. Same
# values as menu_fair_cell.sh / capscurve_resweep_launcher.sh - do not "tidy".
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1

mkdir -p "$LOGS" "$DIR/verdicts"
[ "$DRY" = 1 ] || mkdir -p "$OUT"
ts() { date +%F_%T; }
log() { echo "[chain $(ts)] $*"; }
CUR_PID=""
blocked() {   # $1 = block id, $2... = reason
  local b="$1"; shift
  log "!!! BLOCK $b BLOCKED: $*"
  {
    echo "$(ts)"; echo "block: $b"; echo "reason: $*"
    # DELIBERATELY NOT KILLED. Killing an mp main does NOT reap its spawn workers - they
    # orphan and become invisible to a pattern kill - and games already in flight are
    # valid --shared-claim-checkpointed work. Kill by EXACT pid if you want the box back.
    [ -n "$CUR_PID" ] && echo "local launcher STILL RUNNING as pid $CUR_PID (not killed on purpose)"
    echo "resume: re-run this script - every leg is --shared-claim, completed blocks skip"
    echo "        on their DONE markers, and the band sentinel makes the band claim idempotent."
  } > "$DIR/BLOCKED_$b"
  log "chain STOPPED. Nothing further launches. Marker: $DIR/BLOCKED_$b"
  exit 10
}
skipped() {   # a NON-fatal stop of one block; the chain finishes clean
  local b="$1"; shift
  log "### BLOCK $b SKIPPED: $*"
  { echo "$(ts)"; echo "block: $b"; echo "skipped_because: $*"; } > "$DIR/SKIPPED_$b"
}

# ---------- census / verification helpers (lifted from menu_chain.sh) ----------
# Count BUSY PYTHON PROCESSES, matched on ARGS not comm: the harnesses fan out through
# multiprocessing SPAWN children whose cmdline is `python -c from multiprocessing.spawn
# import spawn_main` and therefore contains neither the harness name nor a distro-stable
# comm. `ps -C python` read a fully-loaded laptop as idle on 2026-08-10.
busy_py_local() { ps -eo pcpu,args --no-headers | awk '$1 > 20.0 && /python/' | wc -l; }
count_records() { find $1 -maxdepth 1 -name 'seed*.json' 2>/dev/null | wc -l; }
laptop_probe() {    # prints "<busy_py> <rev>"; empty on unreachable
  timeout 90 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' 2>/dev/null <<'RPROBE'
cd /home/doctor/projects/carcassone || exit 1
b=$(ps -eo pcpu,args --no-headers | awk '$1 > 20.0 && /python/' | wc -l)
r=$(git -C /home/doctor/projects/carcassone rev-parse HEAD)
echo "$b $r"
RPROBE
}
# CELL-SPECIFIC laptop proof: a generic "laptop is busy" count is not sufficient (on
# 2026-08-10 the laptop was busy at 16 workers on a DIFFERENT job while contributing zero
# games). A .claim NAMES its owning host, so counting claims that carry helper/laptop is
# direct proof the laptop joined THIS cell.
laptop_claims() {
  find $1 -maxdepth 1 -name 'seed*.claim' -print0 2>/dev/null \
    | xargs -0 -r grep -l -E 'helper|laptop' 2>/dev/null | wc -l
}
wait_laptop_quiet() {
  local dl="${1:-7200}" t0; t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt "$dl" ]; do
    local busy
    # ⚠️ NEVER `pgrep -fc PAT || echo 0`: -c PRINTS "0" **and** exits 1 on no match, so the
    # `|| echo 0` also fires and the caller reads a two-line "0\n0" that never equals "0" -
    # the hold then never releases (cost a stuck chain on 2026-08-10). Capture, then default.
    busy=$(timeout 90 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' 2>/dev/null <<'RQ'
cd /home/doctor/projects/carcassone || exit 1
n=$(pgrep -fc 'eval_fair_puc[t]|eval_puct_prior[s]|oracle_score_pilo[t]' 2>/dev/null)
echo "${n:-0}"
RQ
)
    busy=$(printf '%s' "$busy" | head -1 | tr -dc '0-9'); busy=${busy:-0}
    if [ "$busy" -eq 0 ] 2>/dev/null; then log "laptop is quiet - block may start"; return 0; fi
    log "laptop still busy ($busy game/scorer proc) - holding this block"
    sleep 120
  done
  log "WARNING: laptop did not go quiet within ${dl}s; proceeding (a throughput cost, not a validity cost). verify_two_box still has to see a laptop claim ON THIS CELL."
  return 0
}
launch_laptop() {   # $1 = local script file, piped to the laptop. BACKGROUND THE CALL.
  local f="$1"
  # A synchronous `ssh host "job &"` can HANG and starve every box launched after it; a DOWN
  # box masks the bug entirely. And a detached remote launch makes `timeout` return 124
  # AFTER the job is running: 124 == LAUNCHED, never retry on it (retries stack pools).
  ( timeout 180 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' < "$f" \
      >> "$LOGS/laptop_launch.log" 2>&1
    rc=$?
    echo "[laptop-launch $(date +%F_%T)] $(basename "$f") ssh rc=$rc (124 == launched-and-detached)" \
      >> "$LOGS/laptop_launch.log" ) &
}
# Run a script on the laptop and RETURN ITS OUTPUT+rc (the capability probes). Same
# pipe-a-script rule: `ssh host 'cd X && ...'` gets the cd stripped in transit.
laptop_run() { timeout "${2:-600}" ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' < "$1" 2>&1; }

# verify_two_box <block> <record-dir-glob> <deadline-workers-s> <deadline-records-s>
verify_two_box() {
  local b="$1" glob="$2" dlw="$3" dlr="$4"
  local base; base=$(count_records "$glob")
  local t0; t0=$(date +%s)
  local lw=0 pw=0 lc=0 lrev="" ok_w=0
  log "verify[$b]: baseline records=$base; waiting up to ${dlw}s for workers on BOTH boxes"
  while [ $(( $(date +%s) - t0 )) -lt "$dlw" ]; do
    lw=$(busy_py_local)
    read -r pw lrev <<< "$(laptop_probe)"
    pw=${pw:-0}
    lc=$(laptop_claims "$glob")
    if [ "$lw" -gt 1 ] && [ "$pw" -gt 1 ] && [ "$lc" -gt 0 ]; then ok_w=1; break; fi
    sleep 20
  done
  log "verify[$b]: busy python -> local=$lw laptop=$pw | laptop claims on this cell=$lc (laptop rev=${lrev:-UNREACHABLE})"
  [ "$ok_w" = 1 ] || blocked "$b" "two-box verification failed after ${dlw}s (local busy=$lw need >1; laptop busy=$pw need >1; laptop claims on this cell=$lc need >0). A block that runs on one box only is a throughput loss AND an unverified topology."
  log "verify[$b]: waiting up to ${dlr}s for the record count to grow past $base"
  t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt "$dlr" ]; do
    local now; now=$(count_records "$glob")
    if [ "$now" -gt "$base" ]; then
      log "verify[$b]: PASS - records $base -> $now, local=$lw laptop=$pw busy workers"
      return 0
    fi
    sleep 30
  done
  blocked "$b" "record count never grew past $base within ${dlr}s (workers were up: local=$lw laptop=$pw) - games are being claimed but not completing"
}

# ---------- required parameters: NO DEFAULTS, EVER ----------
require_denial_params() {
  [ -n "${DENIAL_DOSES:-}" ]    || blocked D1 "DENIAL_DOSES is unset. It is a REQUIRED parameter with no default - the doses come from Joshua's offline calibration. Relaunch with e.g. DENIAL_DOSES=\"1.0,2.0\" DENIAL_SIZE_MIN=5 DENIAL_OPEN_MAX=3."
  [ -n "${DENIAL_SIZE_MIN:-}" ] || blocked D1 "DENIAL_SIZE_MIN is unset (REQUIRED, no default)."
  [ -n "${DENIAL_OPEN_MAX:-}" ] || blocked D1 "DENIAL_OPEN_MAX is unset (REQUIRED, no default)."
}

# ---------- parameter persistence (so a WATCHDOG RESTART is not a silent re-parameterization)
# The knob values arrive as environment variables, and cron/the watchdog have no environment.
# A restart that lost DENIAL_DOSES would either die (best case) or, if defaults existed,
# quietly measure a different cell - which is why nothing here has a default. The chain
# persists the resolved parameters as assign-if-unset lines, so: a live env always WINS,
# and a bare restart inherits exactly what game 1 ran under.
PARAMS=$DIR/PARAMS.env
# shellcheck disable=SC1090
[ -f "$PARAMS" ] && . "$PARAMS"

# ---------- pre-flight ----------
log "=== DENIAL / SIMS-SPLIT CHAIN START (dry_run=$DRY) ==="
log "D1 prereg: measurement/denial_screen_20260811/PREREG_DRAFT.md | S1 pre-gate: measurement/simsplit_census_20260811/PREREG.md"
LOCAL_REV=$(git -C "$REPO" rev-parse HEAD)
log "local rev $LOCAL_REV | W_LOCAL=$W_LOCAL W_LAPTOP=$W_LAPTOP | D1_N=$D1_N S1_N=$S1_N"
require_denial_params
log "D1 params: doses=[$DENIAL_DOSES] size_min=$DENIAL_SIZE_MIN open_max=$DENIAL_OPEN_MAX"
if [ -f "$S1_GO" ]; then
  log "S1 go-file PRESENT ($S1_GO): $(head -3 "$S1_GO" 2>/dev/null | tr '\n' ' ')"
  [ -n "${SIMS_TILE:-}" ] && [ -n "${SIMS_MEEPLE:-}" ] || \
    blocked PREFLIGHT "the S1 go-file exists but SIMS_TILE/SIMS_MEEPLE are unset. They are REQUIRED parameters with no default. Failing NOW rather than after D1's hours of compute."
  log "S1 params: sims_tile=$SIMS_TILE sims_meeple=$SIMS_MEEPLE (fixed per-turn total 2x$S1_SIMS)"
else
  log "S1 go-file ABSENT ($S1_GO) - S1 will SKIP unless it appears before block S1 starts."
fi

if [ "$DRY" = 0 ]; then
  {
    echo "# written by denial_simsplit_chain.sh at $(ts) - assign-if-unset, so a live env WINS."
    echo "# The watchdog sources this on restart; without it a restart has no knob values."
    echo ": \"\${DENIAL_DOSES:=$DENIAL_DOSES}\""
    echo ": \"\${DENIAL_SIZE_MIN:=$DENIAL_SIZE_MIN}\""
    echo ": \"\${DENIAL_OPEN_MAX:=$DENIAL_OPEN_MAX}\""
    echo ": \"\${W_LOCAL:=$W_LOCAL}\""
    echo ": \"\${W_LAPTOP:=$W_LAPTOP}\""
    echo ": \"\${D1_N:=$D1_N}\""
    echo ": \"\${S1_N:=$S1_N}\""
    [ -n "${SIMS_TILE:-}" ]   && echo ": \"\${SIMS_TILE:=$SIMS_TILE}\""
    [ -n "${SIMS_MEEPLE:-}" ] && echo ": \"\${SIMS_MEEPLE:=$SIMS_MEEPLE}\""
    echo "export DENIAL_DOSES DENIAL_SIZE_MIN DENIAL_OPEN_MAX W_LOCAL W_LAPTOP D1_N S1_N SIMS_TILE SIMS_MEEPLE"
  } > "$PARAMS"
  log "parameters persisted to $PARAMS (the watchdog sources this on restart)"
  read -r PRE_W PRE_REV <<< "$(laptop_probe)"
  [ -n "${PRE_REV:-}" ] || blocked PREFLIGHT "laptop unreachable at chain start (ssh $LAPTOP)"
  log "laptop rev $PRE_REV (busy python $PRE_W)"
  if [ "$PRE_REV" != "$LOCAL_REV" ]; then
    blocked PREFLIGHT "laptop is at rev $PRE_REV but local is at $LOCAL_REV. Stale remote code is a CONTAMINATION class, not an inconvenience. Bundle-sync the laptop and relaunch: git bundle create $SHARE/sync/night2.bundle <branch> (local) then git fetch $LSHARE/sync/night2.bundle <branch> && git reset --hard FETCH_HEAD (laptop, inside a PIPED script with cd on line 1)."
  fi
else
  log "[dry-run] skipping the laptop reach/rev pre-flight (no ssh in a rehearsal)"
fi

# =====================================================================================
# BLOCK D1 - targeted-denial dose screen. 1..4 cells x n=200, ONE shared fresh band (CRN).
# =====================================================================================
if [ -f "$DIR/DONE_D1" ]; then
  log "BLOCK D1 already DONE - skipping"
else
  # The CANONICAL table both launchers read, written only AFTER the two-box gate passes.
  CELLS_TSV_LOCAL=$OUT/d1_cells.tsv
  CELLS_TSV_LAPTOP=$LOUT/d1_cells.tsv
  # ⚠️ Gate artifacts must have BOX-DISTINCT BASENAMES. $OUT/x and $LOUT/x are the SAME
  # physical file (one CIFS store, two mount prefixes), so if both probes write "the same"
  # filename the second write overwrites the first and the agreement gate compares a file to
  # ITSELF - passing unconditionally, including when the boxes genuinely disagree. Distinct
  # basenames make that vacuity structurally impossible; chain_compare_cell_tables.py
  # re-checks dev+ino anyway so a future "tidy" cannot quietly restore it.
  CELLS_PROBE_LOCAL=$OUT/d1_cells.local.tsv          # written by the local probe
  CELLS_PROBE_LAPTOP_REMOTE=$LOUT/d1_cells.laptop.tsv # written by the laptop probe (its prefix)
  CELLS_PROBE_LAPTOP_HERE=$OUT/d1_cells.laptop.tsv    # SAME file, LOCAL prefix - what we read
  LAPTOP_JSON_REMOTE=$LOUT/D1_capability_laptop.json
  LAPTOP_JSON_HERE=$OUT/D1_capability_laptop.json
  PROBE_ARGS=(--require denial --doses "$DENIAL_DOSES" --size-min "$DENIAL_SIZE_MIN"
              --open-max "$DENIAL_OPEN_MAX" --max-cells 4)

  if [ "$DRY" = 1 ]; then
    log "--- [dry-run] BLOCK D1 ---"
    echo "[dry-run] capability probe (LOCAL, runtime):"
    echo "[dry-run]   $PY $PROBE ${PROBE_ARGS[*]} --cells-out $CELLS_PROBE_LOCAL --json-out $DIR/verdicts/D1_capability_local.json"
    echo "[dry-run] capability probe (LAPTOP, runtime, piped script with cd on line 1):"
    echo "[dry-run]   ssh $LAPTOP 'bash -s' < $LOGS/_laptop_D1_probe.sh   # same probe, --cells-out $CELLS_PROBE_LAPTOP_REMOTE --json-out $LAPTOP_JSON_REMOTE"
    echo "[dry-run] two-box agreement gate (BOTH paths carry the LOCAL prefix - this process"
    echo "[dry-run] reads them from THIS box; box-distinct basenames keep it non-vacuous):"
    echo "[dry-run]   $PY $CELLCMP --local $CELLS_PROBE_LOCAL --remote $CELLS_PROBE_LAPTOP_HERE --remote-label laptop --newer-than <probe-start-epoch>"
    echo "[dry-run] then the agreed table is promoted: cp $CELLS_PROBE_LOCAL $CELLS_TSV_LOCAL"
    echo "[dry-run] band claim (idempotent, sentinel $DIR/BAND_D1):"
    $PY "$CLAIM" --label "D1 dry-run" --notes "-" --evidence "-" \
        --sentinel "$DIR/BAND_D1" --registry "$REGISTRY" --dry-run 2>&1 | sed 's/^/[dry-run]   /'
    D1_BAND_SHOWN=$($PY "$CLAIM" --label x --notes - --evidence - --sentinel "$DIR/BAND_D1" --registry "$REGISTRY" --dry-run 2>/dev/null | tail -1)
    # Rehearsal cells land in-repo, NOT on the share: a dry-run must never write into the
    # path a live run reads from. The real run writes $CELLS_TSV_LOCAL (and its laptop twin).
    TMPCELLS=$DIR/d1_cells.dryrun.tsv
    $PY "$PROBE" "${PROBE_ARGS[@]}" --no-runtime-probe --cells-out "$TMPCELLS" \
        > "$LOGS/D1_probe_dryrun.log" 2>&1
    prc=$?
    [ "$prc" = 0 ] || echo "[dry-run] ⚠️ the STRUCTURE-ONLY probe itself failed (rc=$prc) - a real" \
                           "run would BLOCK here. See $LOGS/D1_probe_dryrun.log"
    echo "[dry-run] resolved cells (tag / cand_leaf_json / expected cand_leaf_hash), from a"
    echo "[dry-run] STRUCTURE-ONLY probe (--no-runtime-probe); the real run also proves the"
    echo "[dry-run] loaded carc_rs accepts the kwargs AND that the dose moves the leaf value:"
    sed 's/^/[dry-run]   /' "$TMPCELLS"
    echo "[dry-run] LOCAL leg (real run passes --cells-file $CELLS_TSV_LOCAL):"
    DN_OUT_ROOT=$OUT bash "$REPO/scripts/classical_search/denial_cell_launcher.sh" "$W_LOCAL" local \
        --cells-file "$TMPCELLS" --n "$D1_N" --band "${D1_BAND_SHOWN:-<band>}" --out-root "$OUT" \
        --sims "$D1_SIMS" --dry-run | sed 's/^/[dry-run]   /'
    echo "[dry-run] LAPTOP leg (piped to '$LAPTOP' as a script whose line 1 is a cd):"
    echo "[dry-run]   cd /home/doctor/projects/carcassone"
    echo "[dry-run]   setsid nohup nice -n 19 bash scripts/classical_search/denial_cell_launcher.sh $W_LAPTOP laptop \\"
    echo "[dry-run]     --cells-file $CELLS_TSV_LAPTOP --n $D1_N --band ${D1_BAND_SHOWN:-<band>} --out-root $LOUT --sims $D1_SIMS \\"
    echo "[dry-run]     > $LOUT/laptop_D1.log 2>&1 < /dev/null & disown"
    echo "[dry-run] per-cell verdict extract:"
    while IFS=$'\t' read -r c j h; do
      [ -n "${c:-}" ] || continue
      echo "[dry-run]   $PY $SUMMARY --dir $OUT/$c --label ${c}_n${D1_N}_b<band> --expected-rules-profile fixed_v1 --expect-cand-leaf-hash $h --out $DIR/verdicts/BLOCK_D1_${c}.json"
    done < "$TMPCELLS"
    echo "[dry-run] then: touch $DIR/DONE_D1"
  else
    wait_laptop_quiet 10800
    log "--- BLOCK D1: targeted-denial dose screen, n=$D1_N/cell, instrument=eval_puct_priors@$D1_SIMS ---"

    # (1) CAPABILITY, LOCAL. Refuses on a carc_rs that predates the denial term.
    if ! $PY "$PROBE" "${PROBE_ARGS[@]}" --cells-out "$CELLS_PROBE_LOCAL" \
            --json-out "$DIR/verdicts/D1_capability_local.json" >> "$LOGS/D1_probe.log" 2>&1; then
      blocked D1 "LOCAL capability probe FAILED - see $DIR/verdicts/D1_capability_local.json and $LOGS/D1_probe.log. The loaded carc_rs almost certainly predates the targeted-denial term; rebuild and install the combined wheel (maturin develop --release) on this box. Refusing to run: a default-off candidate arm produces a beautiful, meaningless null."
    fi
    log "D1: local capability probe PASS -> $CELLS_PROBE_LOCAL"

    # (2) CAPABILITY, LAPTOP. It plays ~40% of the games; a stale wheel THERE contaminates
    # the same cell dir with default-off games that are indistinguishable at read time.
    # Delete this run's laptop artifacts FIRST and record the epoch: a table left behind by
    # an earlier run must never be mistaken for this run's second opinion.
    rm -f "$CELLS_PROBE_LAPTOP_HERE" "$LAPTOP_JSON_HERE"
    LAPTOP_PROBE_T0=$(date +%s)
    # ⚠️ The canonical champion-leaf env MUST be exported inside this remote script. The
    # probe resolves DEFAULT_CONFIG from the environment at import time; without these the
    # laptop hashes curve100 (84c1c7f313dbf876) instead of the champion a36d2e15a3b3d71d and
    # every candidate hash it derives belongs to a different leaf dialect. Keep in sync with
    # the exports at the top of this file.
    cat > "$LOGS/_laptop_D1_probe.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1
mkdir -p $LOUT
/home/doctor/projects/carcassone/.venv/bin/python \\
  /home/doctor/projects/carcassone/scripts/classical_search/chain_capability_probe.py \\
  --require denial --doses "$DENIAL_DOSES" --size-min $DENIAL_SIZE_MIN \\
  --open-max $DENIAL_OPEN_MAX --max-cells 4 \\
  --cells-out $CELLS_PROBE_LAPTOP_REMOTE --json-out $LAPTOP_JSON_REMOTE
EOF
    laptop_run "$LOGS/_laptop_D1_probe.sh" 900 > "$LOGS/D1_probe_laptop.log" 2>&1
    lrc=$?
    if [ "$lrc" -ne 0 ]; then
      blocked D1 "LAPTOP capability probe FAILED (rc=$lrc) - see $LOGS/D1_probe_laptop.log. The laptop's carc_rs is very likely the pre-denial wheel. It plays a large share of every cell and its games are INDISTINGUISHABLE from the local box's at read time, so a stale wheel there silently dilutes the candidate arm toward the champion. Rebuild+install on the laptop, then re-run this chain."
    fi
    # Durable laptop evidence next to the local verdict (the probe's own JSON, not just a log).
    if [ -f "$LAPTOP_JSON_HERE" ]; then
      cp -f "$LAPTOP_JSON_HERE" "$DIR/verdicts/D1_capability_laptop.json"
    else
      blocked D1 "the LAPTOP capability probe exited 0 but left NO verdict JSON at $LAPTOP_JSON_REMOTE (read here as $LAPTOP_JSON_HERE). A probe that cannot persist its own result is not evidence that the laptop is capable - see $LOGS/D1_probe_laptop.log."
    fi

    # (3) TWO-BOX AGREEMENT. Same doses must yield the same candidate hashes on both boxes,
    # or the two boxes are not computing the same candidate leaf (different leaf era / env /
    # dialect). BOTH paths below carry the LOCAL prefix because THIS process reads them from
    # the local box - the pre-fix gate spelled the laptop side with the LAPTOP prefix
    # (/mnt/carc-shared, an empty stub here), so diff exited 2 on a missing file and the
    # chain reported "hashes disagree" about a table it had never read.
    if ! $PY "$CELLCMP" --local "$CELLS_PROBE_LOCAL" --remote "$CELLS_PROBE_LAPTOP_HERE" \
            --remote-label laptop --newer-than "$LAPTOP_PROBE_T0" \
            >> "$LOGS/D1_probe.log" 2>&1; then
      blocked D1 "two-box candidate-leaf agreement gate FAILED - see the [cells-gate] line at the end of $LOGS/D1_probe.log for the exact reason (missing/stale laptop table, a vacuous same-file comparison, or genuinely disagreeing candidate leaf hashes). Local table: $CELLS_PROBE_LOCAL | laptop table: $CELLS_PROBE_LAPTOP_REMOTE (read here as $CELLS_PROBE_LAPTOP_HERE)."
    fi
    log "D1: laptop capability probe PASS, cell tables identical on both boxes (two distinct files compared)"

    # (4) PROMOTE the agreed table to the canonical name both launchers read. Nothing writes
    # $CELLS_TSV_LOCAL before this point, so a run that blocks above leaves no table for a
    # launcher to pick up.
    cp -f "$CELLS_PROBE_LOCAL" "$CELLS_TSV_LOCAL"

    # (5) BAND — claimed HERE, after the gates, immediately before game 1.
    D1_CELL_LIST=$(cut -f1 "$CELLS_TSV_LOCAL" | tr '\n' ' ')
    D1_NOTES="Seeds <band>..<band+$((D1_N/2-1))> ($((D1_N/2)) decks x 2 seats, CRN-shared by all cells). Doses/thresholds chosen from the 2026-08-11 offline calibration: doses=[$DENIAL_DOSES] size_min=$DENIAL_SIZE_MIN open_max=$DENIAL_OPEN_MAX. Cells: $D1_CELL_LIST. Candidate = champion leaf + targeted denial injected CANDIDATE-SIDE ONLY via --cand-leaf-json; opponent = the intact champion a36d2e15a3b3d71d. Both sides fixed_v1 + CARCASSONNE_FIX_R9=1, rust, 2750 ablation instrument. Capability probe (knob exists / accepted by the loaded carc_rs / CHANGES the leaf value) PASSED ON BOTH BOXES before game 1; per-cell expected cand_leaf_hash re-checked against each manifest at read time. Screen resolution ~+/-35 elo at 2 sigma - a null here is a BOUNDED null. Registered before game 1. FLIP TO retired AT CLOSE-OUT."
    D1_BAND=$($PY "$CLAIM" --label "D1 - TARGETED-DENIAL DOSE SCREEN: $(wc -l < "$CELLS_TSV_LOCAL") cells x n=$D1_N deck-paired vs the intact champion leaf, at the 2750 ablation instrument (eval_puct_priors.py --cand-sims $D1_SIMS both sides), rust both sides, fixed_v1+R9. ALL CELLS SHARE THIS BAND with CRN." \
        --tier claim --evidence "measurement/denial_screen_20260811/PREREG_DRAFT.md" \
        --notes "$D1_NOTES" --sentinel "$DIR/BAND_D1" --registry "$REGISTRY" 2>>"$LOGS/D1_probe.log" | tail -1)
    case "$D1_BAND" in
      ''|*[!0-9]*) blocked D1 "band claim failed (got '$D1_BAND') - see $LOGS/D1_probe.log" ;;
    esac
    log "D1: claimed band $D1_BAND (registry row written; sentinel $DIR/BAND_D1)"

    # (6) LAUNCH. Laptop first (backgrounded CALL), then local in this shell's background.
    cat > "$LOGS/_laptop_D1.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
mkdir -p $LOUT
setsid nohup nice -n 19 bash \\
  scripts/classical_search/denial_cell_launcher.sh $W_LAPTOP laptop \\
    --cells-file $CELLS_TSV_LAPTOP --n $D1_N --band $D1_BAND --out-root $LOUT --sims $D1_SIMS \\
  > $LOUT/laptop_D1.log 2>&1 < /dev/null & disown
echo "laptop D1 launched pid \$!"
EOF
    launch_laptop "$LOGS/_laptop_D1.sh"
    nice -n 19 bash "$REPO/scripts/classical_search/denial_cell_launcher.sh" "$W_LOCAL" local \
        --cells-file "$CELLS_TSV_LOCAL" --n "$D1_N" --band "$D1_BAND" --out-root "$OUT" \
        --sims "$D1_SIMS" > "$LOGS/D1_local.log" 2>&1 &
    D1_PID=$!; CUR_PID=$D1_PID
    log "BLOCK D1: local launcher pid $D1_PID; laptop joiner launch backgrounded"
    verify_two_box D1 "$OUT/d1_denial_*" 900 2400
    wait $D1_PID
    D1_RC=$?; CUR_PID=""
    log "BLOCK D1: local launcher exited rc=$D1_RC"

    # (7) READ-TIME GATES + extracts. Note the hash gate: it is the second, independent
    # check that the knob reached the leaf (the probe was the first, before game 1).
    D1_FAIL=0
    while IFS=$'\t' read -r cell cjson chash; do
      [ -n "${cell:-}" ] || continue
      got=$(count_records "$OUT/$cell")
      log "BLOCK D1: cell $cell records $got/$D1_N"
      [ "$got" -lt $(( D1_N * 90 / 100 )) ] && D1_FAIL=1
      $PY "$SUMMARY" --dir "$OUT/$cell" --label "${cell}_n${D1_N}_b${D1_BAND}" \
          --expected-rules-profile fixed_v1 --expect-cand-leaf-hash "$chash" \
          --out "$DIR/verdicts/BLOCK_D1_${cell}.json" >> "$LOGS/D1_local.log" 2>&1
    done < "$CELLS_TSV_LOCAL"
    [ "$D1_FAIL" = 1 ] && blocked D1 "at least one denial cell is under 90% completion (VOID by the standing rule) - not proceeding to S1 on a contaminated queue"
    : > "$DIR/DONE_D1"
    log "BLOCK D1 COMPLETE -> $DIR/verdicts/BLOCK_D1_*.json (band $D1_BAND)"
  fi
fi

# =====================================================================================
# BLOCK S1 - sims-split screen. HARD-GATED: human go-file AND the flags must exist.
# =====================================================================================
if [ -f "$DIR/DONE_S1" ]; then
  log "BLOCK S1 already DONE - skipping"
elif [ ! -f "$S1_GO" ] && [ "$DRY" = 0 ]; then
  skipped S1 "no go-file at $S1_GO. S1 is authorized BY HAND ONLY (the split knob's byte-identity gate is a human attestation - this chain cannot verify it and must not assume it). Chain finishes clean; re-run after creating the go-file to pick S1 up."
else
  if [ "$DRY" = 1 ]; then
    log "--- [dry-run] BLOCK S1 (shown as if BOTH gates passed; at runtime either one missing => SKIP) ---"
    echo "[dry-run] gate (a): test -f $S1_GO      # created BY HAND by Joshua, never by this chain"
    echo "[dry-run] gate (b): $PY $FAIRHARNESS --help | grep -- --sims-tile / --sims-meeple  (probe, both boxes)"
    echo "[dry-run]   $PY $PROBE --require simsplit --harness $FAIRHARNESS --sims-tile ${SIMS_TILE:-<SIMS_TILE>} --sims-meeple ${SIMS_MEEPLE:-<SIMS_MEEPLE>} --sims $S1_SIMS --json-out $DIR/verdicts/S1_capability_local.json"
    echo "[dry-run] band claim (idempotent, sentinel $DIR/BAND_S1):"
    $PY "$CLAIM" --label "S1 dry-run" --notes "-" --evidence "-" \
        --sentinel "$DIR/BAND_S1" --registry "$REGISTRY" --dry-run 2>&1 | sed 's/^/[dry-run]   /'
    echo "[dry-run]   NOTE: in a REAL run D1 has already taken that band, so S1's claim lands"
    echo "[dry-run]   one step higher. A rehearsal claims nothing, so both blocks show the same"
    echo "[dry-run]   next-free number here."
    echo "[dry-run] LOCAL leg:"
    MENU_OUT_ROOT=$OUT bash "$REPO/scripts/classical_search/menu_fair_cell.sh" "$W_LOCAL" local \
        --sub s1_simsplit --n "$S1_N" --band "<band>" \
        --k-dets "$S1_KDETS" --sims "$S1_SIMS" \
        --sims-tile "${SIMS_TILE:-<SIMS_TILE>}" --sims-meeple "${SIMS_MEEPLE:-<SIMS_MEEPLE>}" \
        --dry-run | sed 's/^/[dry-run]   /'
    echo "[dry-run] LAPTOP leg (piped script, cd on line 1):"
    echo "[dry-run]   cd /home/doctor/projects/carcassone"
    echo "[dry-run]   setsid nohup env MENU_OUT_ROOT=$LOUT nice -n 19 bash scripts/classical_search/menu_fair_cell.sh $W_LAPTOP laptop \\"
    echo "[dry-run]     --sub s1_simsplit --n $S1_N --band <band> --k-dets $S1_KDETS --sims $S1_SIMS \\"
    echo "[dry-run]     --sims-tile ${SIMS_TILE:-<SIMS_TILE>} --sims-meeple ${SIMS_MEEPLE:-<SIMS_MEEPLE>} \\"
    echo "[dry-run]     > $LOUT/s1_simsplit/laptop.log 2>&1 < /dev/null & disown"
    echo "[dry-run] verdict extract:"
    echo "[dry-run]   $PY $SUMMARY --dir $OUT/s1_simsplit --label s1_simsplit_t${SIMS_TILE:-T}_m${SIMS_MEEPLE:-M}_n${S1_N}_b<band> --expected-rules-profile fixed_v1 --out $DIR/verdicts/BLOCK_S1.json"
    echo "[dry-run] then: touch $DIR/DONE_S1"
  else
    log "--- BLOCK S1: sims-split screen (go-file present) ---"
    [ -n "${SIMS_TILE:-}" ] && [ -n "${SIMS_MEEPLE:-}" ] || \
      blocked S1 "the S1 go-file exists but SIMS_TILE/SIMS_MEEPLE are unset. REQUIRED parameters, no defaults. This is a BLOCK, not a skip: an authorized-but-unparameterized S1 must never be silently passed over."

    # gate (b), LOCAL: do the flags actually exist on the harness that will run?
    if ! $PY "$PROBE" --require simsplit --harness "$FAIRHARNESS" \
            --sims-tile "$SIMS_TILE" --sims-meeple "$SIMS_MEEPLE" --sims "$S1_SIMS" \
            --json-out "$DIR/verdicts/S1_capability_local.json" >> "$LOGS/S1_probe.log" 2>&1; then
      skipped S1 "the sims-split capability probe FAILED on the LOCAL box - either eval_fair_puct.py does not advertise --sims-tile/--sims-meeple (the knob did not land) or the split does not sum to the fixed per-turn total 2x$S1_SIMS. See $DIR/verdicts/S1_capability_local.json. SKIPPING (not failing) so the chain finishes clean and D1's result is not held hostage."
      log "=== CHAIN FINISHED (D1 done, S1 skipped) ==="
      exit 0
    fi
    # gate (b), LAPTOP: it must have the flags too, or it silently contributes UNSPLIT games.
    cat > "$LOGS/_laptop_S1_probe.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
/home/doctor/projects/carcassone/.venv/bin/python \\
  /home/doctor/projects/carcassone/scripts/classical_search/chain_capability_probe.py \\
  --require simsplit --harness /home/doctor/projects/carcassone/scripts/classical_search/eval_fair_puct.py \\
  --sims-tile $SIMS_TILE --sims-meeple $SIMS_MEEPLE --sims $S1_SIMS
EOF
    laptop_run "$LOGS/_laptop_S1_probe.sh" 900 > "$LOGS/S1_probe_laptop.log" 2>&1
    src=$?
    if [ "$src" -ne 0 ]; then
      skipped S1 "the sims-split capability probe FAILED on the LAPTOP (rc=$src, see $LOGS/S1_probe_laptop.log). Its games would be UNSPLIT and indistinguishable from the split ones in the same cell dir. SKIPPING the block."
      log "=== CHAIN FINISHED (D1 done, S1 skipped) ==="
      exit 0
    fi
    log "S1: capability probes PASS on both boxes (flags present, split sums to 2x$S1_SIMS)"

    wait_laptop_quiet 10800
    S1_NOTES="Seeds <band>..<band+$((S1_N/2-1))> ($((S1_N/2)) decks x 2 seats). Candidate = the production champion with per-phase sims (--sims-tile $SIMS_TILE / --sims-meeple $SIMS_MEEPLE, fixed per-turn total 2x$S1_SIMS), opponent = the UNMODIFIED champion; both arms k${S1_KDETS}x${S1_SIMS}=$((S1_KDETS*S1_SIMS)), fixed_v1+R9, rust, FAIR PIMC (eval_fair_puct.py --info fair --opponent fair-champion). Pre-gate: measurement/simsplit_census_20260811/PREREG.md. AUTHORIZED BY HAND (go-file measurement/night_chain_20260812/S1_AUTHORIZED) - the split knob's byte-identity gate is a human attestation; the chain verified only that the flags exist on BOTH boxes. n=$S1_N deck-paired is a SCREEN (~+/-35 elo at 2 sigma), never a promotion. Registered before game 1. FLIP TO retired AT CLOSE-OUT."
    S1_BAND=$($PY "$CLAIM" --label "S1 - SIMS-SPLIT SCREEN at fixed per-turn budget: cand = champion with sims_tile=$SIMS_TILE / sims_meeple=$SIMS_MEEPLE vs the unmodified champion, n=$S1_N deck-paired, k${S1_KDETS}x${S1_SIMS} both arms, fixed_v1+R9, rust." \
        --tier claim --evidence "measurement/simsplit_census_20260811/PREREG.md" \
        --notes "$S1_NOTES" --sentinel "$DIR/BAND_S1" --registry "$REGISTRY" 2>>"$LOGS/S1_probe.log" | tail -1)
    case "$S1_BAND" in
      ''|*[!0-9]*) blocked S1 "band claim failed (got '$S1_BAND') - see $LOGS/S1_probe.log" ;;
    esac
    log "S1: claimed band $S1_BAND (registry row written; sentinel $DIR/BAND_S1)"

    mkdir -p "$OUT/s1_simsplit"
    cat > "$LOGS/_laptop_S1.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
mkdir -p $LOUT/s1_simsplit
setsid nohup env MENU_OUT_ROOT=$LOUT nice -n 19 bash \\
  scripts/classical_search/menu_fair_cell.sh $W_LAPTOP laptop \\
    --sub s1_simsplit --n $S1_N --band $S1_BAND \\
    --k-dets $S1_KDETS --sims $S1_SIMS \\
    --sims-tile $SIMS_TILE --sims-meeple $SIMS_MEEPLE \\
  > $LOUT/s1_simsplit/laptop.log 2>&1 < /dev/null & disown
echo "laptop S1 launched pid \$!"
EOF
    launch_laptop "$LOGS/_laptop_S1.sh"
    MENU_OUT_ROOT=$OUT nice -n 19 bash "$REPO/scripts/classical_search/menu_fair_cell.sh" "$W_LOCAL" local \
        --sub s1_simsplit --n "$S1_N" --band "$S1_BAND" \
        --k-dets "$S1_KDETS" --sims "$S1_SIMS" \
        --sims-tile "$SIMS_TILE" --sims-meeple "$SIMS_MEEPLE" \
        > "$LOGS/S1_local.log" 2>&1 &
    S1_PID=$!; CUR_PID=$S1_PID
    log "BLOCK S1: local launcher pid $S1_PID; laptop joiner launch backgrounded"
    verify_two_box S1 "$OUT/s1_simsplit" 900 3600
    wait $S1_PID
    S1_RC=$?; CUR_PID=""
    log "BLOCK S1: local launcher exited rc=$S1_RC"
    S1_GOT=$(count_records "$OUT/s1_simsplit")
    log "BLOCK S1: records $S1_GOT/$S1_N"
    [ "$S1_GOT" -lt $(( S1_N * 90 / 100 )) ] && blocked S1 "only $S1_GOT/$S1_N records (<90%) - VOID by the standing rule"
    $PY "$SUMMARY" --dir "$OUT/s1_simsplit" \
        --label "s1_simsplit_t${SIMS_TILE}_m${SIMS_MEEPLE}_n${S1_N}_b${S1_BAND}" \
        --expected-rules-profile fixed_v1 --out "$DIR/verdicts/BLOCK_S1.json" \
        >> "$LOGS/S1_local.log" 2>&1
    : > "$DIR/DONE_S1"
    log "BLOCK S1 COMPLETE -> $DIR/verdicts/BLOCK_S1.json (band $S1_BAND)"
  fi
fi

log "=== CHAIN FINISHED (D1/S1) ==="
log "Nothing was promoted. governance/PRODUCTION.yaml untouched. No verdict was adjudicated."
log "Per-block extracts: $DIR/verdicts/ - the orchestrating session reads and closes out."
