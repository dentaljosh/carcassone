#!/usr/bin/env bash
# =============================================================================
# b32v64_cell — THE TWO-CELL LAUNCHER. `B32` (`B` = 32, the cheaper CANDIDATE)
# and `B64` (`B` = 64, a fresh-band replicate of the DEPLOYED INCUMBENT),
# deck-paired on ONE fresh band and THE SAME DECKS, against the unmodified
# champion, at production budget k8x1376 = 11,008, exact-K 2.
#
#   run_cells.sh <local|laptop-side> [--smoke] [--dry-run] [--band <SEED_START>]
#
# ⭐ THE TWO INVOCATIONS DIFFER IN EXACTLY ONE EXPERIMENTAL ARGUMENT —
# `--cand-tiearb-b`. That is the whole design: `B` = 64 is a STRICT REFINEMENT
# of `B` = 32, not a different experiment, because the world seed is a pure
# function of `j` and never of `B`, so `B` = 64's worlds 0..31 are byte-identical
# to `B` = 32's entire set (`gate_nest.py` is the witness). Any second
# experimental difference would break the nesting the "increment" framing rests
# on. (The two argv also differ in `--out-subdir` and `--claim-host`, which are
# BOOKKEEPING: two cells cannot share one output directory or one claim tag.
# Same shape as `b64_cell/run_cells.sh`.)
#
# ⛔ THE PAIR IS LAW. Every knob comes from `WORKERS.conf`, which reads them from
# the pair. A launcher that disagrees with the pair is a LAUNCHER defect: report
# it, do not "fix" it here.
#
# PRECONDITIONS, IN ORDER, AND THIS SCRIPT ENFORCES THEM:
#   0. `WORKERS.conf::BLIND_COMMIT` carries a real hash — NOT `PENDING`. The
#      EXECUTOR writes it after the pair's blind commit lands on `main`.
#   1. `preflight.sh` has PASSED on THIS host at BOTH `B` values (G-J13).
#   2. the smoke has run and its HALT bar has been evaluated (G-SMOKE) — unless
#      this IS the smoke.
#   3. the band was claimed from `governance/BAND_REGISTRY.csv` BEFORE game 1
#      (G-BAND) — the claim is the EXECUTOR's act and its sentinel is passed in
#      with `--band`; ⛔ this script never claims a band and never invents one.
#   4. the ADJUDICATOR `scripts/tiletie/analyze_b32v64_cell.py` EXISTS. It is a
#      NAMED LAUNCH PRECONDITION (DESIGN §12.1), not a rider. It is BUILT; this
#      script still refuses the smoke aggregation if it is ever absent, and
#      NEVER stubs it.
#   5. ⭐ the §9.3 HALT BAR HAS NOT FIRED, AND A SMOKE HAS ACTUALLY RUN.
#      `smoke-check` writes `SMOKE_HALT.json` (DESIGN §9.3.1); this script READS
#      it and REFUSES a real-cell launch unless it EXISTS and reads
#      `halt == false`. ⛔ AN ABSENT RECORD REFUSES TOO: "no smoke has run" is
#      not a pass, and it is not distinguishable from "record deleted".
#      ⛔ THERE IS NO OVERRIDE FLAG — a HALT holds until the OWNER rules (stop,
#      or re-fund at the realized cost), and neither is a launcher decision.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached jobs:
#   setsid nohup ./run_cells.sh local </dev/null >/dev/null 2>&1 &
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$HERE/WORKERS.conf"

# the band pinned by the pair, before `--band` parsing can shadow it
PINNED_BAND="$BAND"

ROLE="${1:?usage: run_cells.sh <local|laptop-side> [--smoke] [--dry-run] [--band SEED_START]}"
shift || true
SMOKE=0; DRY=0; BAND=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --smoke)   SMOKE=1 ;;
    --dry-run) DRY=1 ;;
    --band)    BAND="${2:?--band needs a seed start}"; shift ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

case "$ROLE" in
  local)       REPO="$REPO_LOCAL";  SHARE="$SHARE_LOCAL";  W="$W_LOCAL" ;;
  laptop-side) REPO="$REPO_REMOTE"; SHARE="$SHARE_REMOTE"; W="$W_LAPTOP" ;;
  *) echo "FATAL: bad role '$ROLE' (local | laptop-side)" >&2; exit 2 ;;
esac
HOST="$(hostname)"
PY="$REPO/.venv/bin/python"
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
DIR="$REPO/measurement/tiearb_widening_20260817/b32v64_cell"
ADJ="$REPO/$ADJUDICATOR"          # scripts/tiletie/analyze_b32v64_cell.py
SHARE_RUN="$SHARE/$RUN_ID"
OUT="$SHARE_RUN"
LOGS="$DIR/logs"

if [ "$SMOKE" -eq 1 ]; then
  # §9.1: production knobs — ONLY the game count differs. §9.1's condition of
  # acceptance: the throwaway band DECLARES ITSELF throwaway and is NEVER claimed.
  N="$N_SMOKE"; BAND="${BAND:-$SMOKE_BAND}"; TAG=smoke
  case "$ROLE" in local) W="$W_SMOKE_LOCAL" ;; *) W="$W_SMOKE_LAPTOP" ;; esac
  OUT="$SHARE_RUN/smoke"
else
  N="$N_GAMES"; TAG=cells
fi

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[run_cells $(ts) $HOST/$ROLE] $*"; }

# --------------------------------------------------------------------------- #
# the argv for ONE cell — built ONCE so the dry-run prints EXACTLY what runs    #
# --------------------------------------------------------------------------- #
cell_argv() {   # $1 = cell name, $2 = B, $3 = out-subdir
  local NAME="$1" B="$2" SUB="$3"
  ARGV=(nice -n "$NICE" "$PY" -u "$HARNESS"
        --info fair --opponent fair-champion --backend rust
        --k-dets "$K_DETS" --sims "$SIMS"
        --opp-k-dets "$K_DETS" --opp-sims "$SIMS" --exact-k "$EXACT_K"
        --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
        --n "$N" --paired --seed-start "$BAND"
        --rules-profile "$RULES_PROFILE" --workers "$W"
        --out-root "$OUT" --out-subdir "$SUB"
        --shared-claim --claim-host "b32v64-$NAME-$HOST" --claim-stale-secs 1800
        --no-results-csv
        --cand-tiearb-enabled
        --cand-tiearb-b "$B"
        --cand-tiearb-j "$TIEARB_J"
        --cand-tiearb-mode "$TIEARB_MODE"
        --cand-tiearb-salt "$TIEARB_SALT"
        --cand-tiearb-eps "$TIEARB_EPS")
}

require_preflight() {
  # TOOL: preflight.sh.  ADDRESS: verdicts/PREFLIGHT_${HOST}_FIRST_B{64,32}.json
  # HEALTHY RUN  -> both files exist on THIS host (RULING 4's two-files-per-host
  #                 shape, one per B).
  # FIRES        -> either file absent ⇒ this host has not passed G-J13 at both
  #                 B values before its game 1.
  local missing=0 f
  for B in "$TIEARB_B_HI" "$TIEARB_B_LO"; do
    f="$DIR/verdicts/PREFLIGHT_${HOST}_FIRST_B${B}.json"
    [ -f "$f" ] || { log "!!! G-J13: MISSING $f"; missing=1; }
  done
  [ "$missing" -eq 0 ] || {
    log "!!! REFUSING TO LAUNCH: run ./preflight.sh on THIS host first — it must"
    log "!!! pass at BOTH B values before this host's game 1 (READ_RULE §3 G-J13)."
    exit 13; }
}

require_no_halt() {
  # ⭐ DESIGN §9.3.1 — THIS SCRIPT IS THE **ENFORCER**.
  # TOOL: this launcher.  ADDRESS READ: $DIR/SMOKE_HALT.json (written by
  #       `analyze_b32v64_cell.py smoke-check`, the WRITER).
  # HEALTHY RUN  -> the record is absent (no smoke yet on this tree) or reads
  #                 `"halt": false`.
  # FIRES        -> `"halt": true` ⇒ the smoke overran §9.3's 1.50x bar and the
  #                 real cells MUST NOT launch.
  # ⛔ NO OVERRIDE FLAG. §9.3's only permitted responses to a HALT are *stop* or
  # *the owner re-funds at the realized cost*. Neither is a switch an executor
  # flips. The ONE argument this takes selects PRESENCE strictness, never halt
  # strictness — there is no value of it that lets a `halt == true` record pass.
  #
  # ⭐ `strict` (the REAL-CELL path, REVIEW R2 finding N5): the record must EXIST
  # and read `halt == false`. An ABSENT record used to return 0 — so "no smoke
  # has ever run" was indistinguishable from "the smoke passed", and precondition
  # 2 (*"the smoke has run and its HALT bar has been evaluated"*) was declared in
  # the header and enforced nowhere. The adjudicator is fail-closed behind it
  # (absent SMOKE.json ⇒ G-SMOKE fires ⇒ U-UNREADABLE), so no run could be
  # MIS-ADJUDICATED — but the loss would be ~35 two-box wall-hours and 6,000
  # games discovered at READ time. ⚠️ KILL QUALITY: refuse the launch instead.
  #
  # `lenient` (the SMOKE path's belt-and-braces re-read): absence is fine there —
  # `smoke-check` writes the record moments earlier, and demanding it back would
  # only mask whatever actually went wrong upstream.
  local mode="${1:-lenient}"
  local rec="$DIR/$SMOKE_HALT_RECORD"
  if [ ! -f "$rec" ]; then
    if [ "$mode" = "strict" ]; then
      log "!!! ⛔⛔ NO §9.3 HALT RECORD — REFUSING TO LAUNCH THE REAL CELLS."
      log "!!! MISSING ADDRESS: $rec"
      log "!!! That address is written by \`smoke-check\` (DESIGN §9.3.1 WRITER),"
      log "!!! so its absence means NO SMOKE HAS RUN on this tree — or its record"
      log "!!! was deleted. Precondition 2 requires the smoke to have RUN and its"
      log "!!! HALT bar to have been EVALUATED before game 1; absence is NOT a pass."
      log "!!! Do this first:   ./run_cells.sh $ROLE --smoke"
      log "!!! ⚠️ Why this refuses rather than warns: launching without a smoke"
      log "!!! costs ~35 two-box wall-hours and 6,000 games before G-SMOKE reports"
      log "!!! present:false and the whole run reads U-UNREADABLE. A refused"
      log "!!! launch costs seconds."
      exit 9
    fi
    return 0
  fi
  local halt
  halt="$("$PY" - "$rec" <<'HEOF'
import json, sys
try:
    print("true" if json.load(open(sys.argv[1])).get("halt") is True else "false")
except Exception as exc:                       # unreadable record => fail closed
    print("true")
HEOF
)"
  if [ "$halt" = "true" ]; then
    log "!!! ⛔⛔ §9.3 HALT IS IN FORCE — REFUSING TO LAUNCH THE REAL CELLS."
    log "!!! The smoke's realized CELL_B64 worker_secs_per_game exceeded the bar"
    log "!!! ($SMOKE_HALT_MULTIPLE x $WORKER_S_COMMITTED_B64 = $SMOKE_HALT_BAR worker-s/game)."
    log "!!! Record: $rec"
    "$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));print('    '+str(d.get('why')))" "$rec" 2>/dev/null || true
    log "!!! On a HALT the real cells are NOT launched, the smoke numbers and the"
    log "!!! revised bill are reported, and THE DECISION RETURNS TO THE OWNER."
    log "!!! Permitted responses (DESIGN §9.3): STOP, or the OWNER RE-FUNDS at the"
    log "!!! realized cost. ⛔ No re-tuning of B, the trigger, J, eps or the"
    log "!!! playout is licensed by a HALT, and there is NO override flag here."
    exit 9
  fi
}

require_blind_commit() {
  # ⭐ NEW, FAIL-CLOSED. The pair is blind-committed; a real cell launched while
  # the hash is still the drafted placeholder cannot carry it into a manifest.
  # TOOL: this launcher.  ADDRESS READ: WORKERS.conf::BLIND_COMMIT.
  # HEALTHY RUN  -> an 8..40 hex-char commit hash written by the EXECUTOR after
  #                 the DESIGN.md + READ_RULE.md pair lands on `main`.
  # FIRES        -> the literal string `PENDING` (the drafted value) or empty.
  # ⛔ `--dry-run` and `--smoke` are EXEMPT and the exemption is deliberate:
  # both are COUNTS-AND-COST ONLY and NEITHER SPENDS BLINDNESS (DESIGN §9.2) —
  # the smoke runs on a throwaway band that is never claimed and reads no
  # outcome, so gating it on the blind commit would only stall the cost check
  # that has to happen BEFORE the pair is worth committing.
  if [ "${BLIND_COMMIT:-}" = "PENDING" ] || [ -z "${BLIND_COMMIT:-}" ]; then
    log "!!! FATAL: BLIND_COMMIT is '${BLIND_COMMIT:-<empty>}' — a REAL cell may"
    log "!!! not launch against a placeholder. The EXECUTOR writes the blind-commit"
    log "!!! hash into $HERE/WORKERS.conf AFTER the DESIGN.md + READ_RULE.md pair"
    log "!!! lands on main; every manifest must carry it (READ_RULE §4.3 item 12)."
    log "!!! (--dry-run and --smoke are exempt: counts-and-cost only, no blindness"
    log "!!! is spent by either.)"
    exit 2
  fi
}

# --------------------------------------------------------------------------- #

# ---- W-FREEZE-LATCH sentinel (DEVIATIONS D5 (b)) -----------------------------
# ⭐ Dropped at leg start, cleared at close-out AND on any exit (trap), so an
# abort can never leave the tree latched. The PreToolUse latch
# (scripts/hooks/pretooluse_lint.py; tests/test_freeze_latch.py) refuses a
# MAIN-TREE commit while it exists. It is a FILE, not a convention: it is
# visible to WHOEVER commits, which is the point — the freeze discipline has
# failed twice and both times at the orchestrator's hands, not a builder's or an
# executor's.
# ⛔ NEVER DROPPED ON A `--dry-run`: a dry run starts no games, so a latch it
# left behind would freeze the tree for a run that does not exist. The only call
# site is inside `if [ "$DRY" -eq 0 ]`, and the dry-run path returns before the
# close-out clear.
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("W-FREEZE-LATCH sentinel (DEVIATIONS D5 (b)): a MAIN-TREE "
                   "commit while this leg is live can put two revisions into "
                   "one run — spawn respawns and each new --shared-claim cell "
                   "RE-IMPORT FROM DISK. Cleared at close-out and on any exit."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  echo "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

main() {
  mkdir -p "$LOGS" "$OUT"
  [ -n "$BAND" ] || { log "!!! FATAL: no band. The EXECUTOR claims it from"
                      log "!!! governance/BAND_REGISTRY.csv BEFORE game 1 and passes"
                      log "!!! it with --band; this script never claims or invents one"
                      log "!!! (READ_RULE §3 G-BAND)."; exit 2; }
  # HEALTHY RUN  -> smoke on $SMOKE_BAND; real cell on $PINNED_BAND.
  # FIRES        -> smoke off the throwaway band / real cell ON the throwaway
  #                 band / real cell on any band the pair did not pin.
  if [ "$SMOKE" -eq 1 ] && [ "$BAND" != "$SMOKE_BAND" ]; then
    log "!!! FATAL: the smoke runs on the THROWAWAY band $SMOKE_BAND only"; exit 2
  fi
  if [ "$SMOKE" -eq 0 ] && [ "$BAND" = "$SMOKE_BAND" ]; then
    log "!!! FATAL: the throwaway band may never carry a real cell"; exit 2
  fi
  if [ "$SMOKE" -eq 0 ] && [ "$BAND" != "$PINNED_BAND" ]; then
    # ⭐ NEW CLAUSE. The band is PINNED in WORKERS.conf by the pair
    # (BAND=$PINNED_BAND, claimed from governance/BAND_REGISTRY.csv). A real
    # cell on any other band is a DIFFERENT experiment wearing this cell's name.
    log "!!! FATAL: --band $BAND is not the band the pair pinned ($PINNED_BAND)."
    log "!!! The launcher does not accept another band for a real cell; if the"
    log "!!! band must change, the PAIR changes, not this script (G-BAND)."
    exit 2
  fi
  [ "$DRY" -eq 1 ] || [ "$SMOKE" -eq 1 ] || require_blind_commit
  # ⭐ B6 link 2 of 3: the ENFORCER. A real cell may not launch under a HALT —
  # and (N5) may not launch with NO halt record at all.
  # ⚠️ The smoke itself is exempt — re-running the smoke is how a HALT gets
  # RE-MEASURED, and gating it on its own previous result would be circular.
  [ "$DRY" -eq 1 ] || [ "$SMOKE" -eq 1 ] || require_no_halt strict

  log "role=$ROLE W=$W N=$N band=$BAND tag=$TAG out=$OUT"
  log "blind_commit=$BLIND_COMMIT  champion_leaf_hash=$CHAMP_LEAF_HASH"
  log "⭐ the two cells differ in EXACTLY ONE EXPERIMENTAL argument: --cand-tiearb-b"
  log "⚠️ they also differ in --out-subdir and --claim-host, which are BOOKKEEPING:"
  log "⚠️ two cells cannot share one output dir or one --shared-claim tag without"
  log "⚠️ corrupting each other (DESIGN §13.2 item 6). No other knob moves."

  [ "$DRY" -eq 1 ] || [ "$SMOKE" -eq 1 ] || require_preflight

  if [ "$DRY" -eq 0 ]; then
    trap 'run_live_clear' EXIT INT TERM
    run_live_drop "b32v64_cell $TAG leg (role=$ROLE)"
  fi

  # ⭐ CELL ORDER: B32 (the cheaper CANDIDATE) FIRST, then B64 (the fresh-band
  # replicate of the DEPLOYED incumbent).
  for pair in "$CELL_LO:$TIEARB_B_LO:$CELL_SUBDIR_LO" \
              "$CELL_HI:$TIEARB_B_HI:$CELL_SUBDIR_HI"; do
    IFS=: read -r NAME B SUB <<< "$pair"
    [ "$SMOKE" -eq 1 ] && SUB="smoke_$SUB"
    cell_argv "$NAME" "$B" "$SUB"
    if [ "$DRY" -eq 1 ]; then
      printf '[dry-run] cell %s (B=%s):' "$NAME" "$B"
      printf ' %q' "${ARGV[@]}"
      printf '\n'
      continue
    fi
    if [ -f "$DIR/DONE_${TAG}_$NAME" ]; then
      log "cell $NAME already DONE — skipping"; continue
    fi
    log "cell $NAME (B=$B) -> $OUT/$SUB"
    "${ARGV[@]}" >> "$LOGS/${TAG}_$NAME.log" 2>&1 || \
      log "cell $NAME rc=$? (the harness is resumable under --shared-claim)"
    touch "$DIR/DONE_${TAG}_$NAME"
  done

  if [ "$DRY" -eq 1 ]; then
    printf '[dry-run] smoke aggregation:'
    printf ' %q' "$PY" "$ADJ" aggregate-smoke \
                 --lo-dir "$SHARE_RUN/smoke/smoke_$CELL_SUBDIR_LO" \
                 --hi-dir "$SHARE_RUN/smoke/smoke_$CELL_SUBDIR_HI" \
                 --band "$SMOKE_BAND" --out "$SHARE_RUN/smoke/SMOKE.json"
    printf '\n'
    printf '[dry-run] smoke gate check + §9.3 HALT record:'
    printf ' %q' "$PY" "$ADJ" smoke-check --smoke "$SHARE_RUN/smoke/SMOKE.json" \
                 --halt-out "$DIR/$SMOKE_HALT_RECORD"
    printf '\n'
    # informational ONLY on a dry run — the refusal lives on the real smoke path
    if [ -f "$ADJ" ]; then
      printf '[dry-run] adjudicator: PRESENT at %s\n' "$ADJ"
    else
      printf '[dry-run] adjudicator: ABSENT at %s — DESIGN §12.1 names it a LAUNCH PRECONDITION; build it before launching\n' "$ADJ"
    fi
    printf '[dry-run] HALT bar (§9.3, one-sided): realized CELL_B64 worker_secs_per_game > %s x %s = %s\n' \
           "$SMOKE_HALT_MULTIPLE" "$WORKER_S_COMMITTED_B64" "$SMOKE_HALT_BAR"
    if [ -f "$DIR/$SMOKE_HALT_RECORD" ]; then
      printf '[dry-run] HALT record: PRESENT at %s — a real-cell launch is REFUSED while halt==true (no override flag)\n' \
             "$DIR/$SMOKE_HALT_RECORD"
      "$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));print('[dry-run]   halt=%s realized=%s bar=%s' % (d.get('halt'),d.get('realized'),d.get('bar')))" \
             "$DIR/$SMOKE_HALT_RECORD" 2>/dev/null || true
    else
      printf '[dry-run] HALT record: ABSENT at %s — written by `smoke-check` (DESIGN §9.3.1 WRITER).\n' \
             "$DIR/$SMOKE_HALT_RECORD"
      printf '[dry-run]   ⛔ A REAL-CELL LAUNCH WOULD BE REFUSED RIGHT NOW: absence means no smoke has run,\n'
      printf '[dry-run]   and absence is NOT a pass (READ_RULE precondition 2). Run `--smoke` first.\n'
    fi
    printf '[dry-run] blind_commit=%s (a real cell REFUSES on PENDING; dry-run and smoke are exempt)\n' \
           "$BLIND_COMMIT"
    return 0
  fi

  if [ "$SMOKE" -eq 1 ]; then
    # ---- THE ADJUDICATOR PRE-CHECK ------------------------------------------
    # TOOL: this launcher.  ADDRESS READ: the file $ADJ on disk.
    # HEALTHY RUN  -> the file exists (it is BUILT, and the EXECUTOR keeps it so).
    # FIRES        -> the file is absent: it is a NAMED LAUNCH PRECONDITION, not
    #                 a rider, so its absence stops the leg rather than being
    #                 discovered late.
    # ⛔ It is never stubbed, never faked, and the refusal never masquerades as
    # an aggregation failure.
    if [ ! -f "$ADJ" ]; then
      log "!!! ADJUDICATOR ABSENT at $ADJ — DESIGN §12.1 names it a LAUNCH PRECONDITION"
      log "!!! The smoke cells have RUN; nothing is aggregated and nothing is"
      log "!!! adjudicated. Build the adjudicator, then re-run this leg."
      exit 9
    fi

    # ---- THE AGGREGATION STEP ------------------------------------------------
    # ⭐ In b64_cell this block did not exist at first, so §9.3 never evaluated:
    # it called smoke-check on a SMOKE.json that NOTHING wrote, and the per-cell
    # manifests carry none of §9.2's whitelist fields — `worker_secs_per_game`,
    # the single quantity the HALT bar is defined on, was emitted nowhere. The
    # aggregator reads the two cells' OWN per-game records and computes it by
    # DESIGN §7.1's own equation (Σ elapsed_s / n).
    log "--- §9 aggregation: the two smoke cells -> SMOKE.json ---"
    set +e
    "$PY" "$ADJ" aggregate-smoke \
      --lo-dir "$SHARE_RUN/smoke/smoke_$CELL_SUBDIR_LO" \
      --hi-dir "$SHARE_RUN/smoke/smoke_$CELL_SUBDIR_HI" \
      --band "$SMOKE_BAND" \
      --out "$SHARE_RUN/smoke/SMOKE.json"
    agg_rc=$?
    set -e
    if [ "$agg_rc" -ne 0 ]; then
      # ⚠️ NAME THE ACTUAL CONDITION. The aggregator prints its own refusal —
      # missing records, an unreadable record, a whitelist-external key, an
      # outcome key. Do NOT restate it as something else.
      log "!!! AGGREGATION REFUSED (rc=$agg_rc) — the aggregator's own message is"
      log "!!! above and names the actual condition. This launcher does not"
      log "!!! re-attribute it."
      exit 9
    fi

    # ---- §9.2's whitelist, on the artifact that now exists -------------------
    log "--- §9.2 whitelist check ---"
    set +e
    "$PY" "$ADJ" smoke-check --smoke "$SHARE_RUN/smoke/SMOKE.json" \
      --halt-out "$DIR/$SMOKE_HALT_RECORD"
    chk_rc=$?
    set -e
    if [ "$chk_rc" -ne 0 ]; then
      # ⚠️ SAME SHAPE AS THE PREFLIGHT'S OLD G-J13 MISATTRIBUTION, and it bit
      # b64_cell here too: this line used to assert "whitelist violation" for ANY
      # nonzero exit — and the real cause was a MISSING FILE. The checker prints
      # the failing condition itself; propagate it, never re-label it.
      if [ ! -f "$SHARE_RUN/smoke/SMOKE.json" ]; then
        log "!!! SMOKE.json is ABSENT at $SHARE_RUN/smoke/SMOKE.json — that is a"
        log "!!! MISSING ARTIFACT, not a whitelist violation."
      else
        # ⚠️ NAME THE ACTUAL CONDITION. `smoke-check` now has THREE ways to exit
        # non-zero — an emitter-whitelist key, a forbidden outcome key, and the
        # §9.3 HALT — and calling a HALT a "whitelist violation" is exactly the
        # misattribution class this block was already burned by once.
        log "!!! smoke-check REFUSED (rc=$chk_rc) — its own message above names"
        log "!!! the condition. This launcher does not re-attribute it."
        require_no_halt      # prints the full §9.3 disclosure IF that was the cause
        log "!!! (not a HALT: the cause is a key outside §9.2's counts-and-cost"
        log "!!! whitelist, a forbidden OUTCOME key, or an unreadable artifact.)"
      fi
      exit 9
    fi

    # ---- §9.3's HALT BAR, ACTUALLY COMPARED ---------------------------------
    # ⭐ B6 link 3 of 3. This block used to LOG the bar's value and nothing else:
    # no arithmetic, no branch, no non-zero exit — the smoke leg returned 0 on a
    # 3x overrun exactly as on an underrun. The comparison now happens in
    # `smoke-check` (the WRITER, whose exit code carries `halt`) and the record
    # it writes is re-read HERE so the leg's own exit status carries it too.
    log "--- §9.3 HALT bar (one-sided; graded on CELL_B64 only) ---"
    log "  bar = $SMOKE_HALT_MULTIPLE x $WORKER_S_COMMITTED_B64 = $SMOKE_HALT_BAR worker-s/game"
    if [ "$chk_rc" -eq 0 ]; then
      log "  §9.3: UNDER the bar — the real cells may proceed."
    fi
    # (a HALT already exited 9 above via chk_rc; this is the belt-and-braces
    # read of the record itself, so a future change to smoke-check's exit code
    # cannot silently re-open the hole)
    require_no_halt
  fi
  run_live_clear
  log "DONE tag=$TAG"
}

main "$@"
