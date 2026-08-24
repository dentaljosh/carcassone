#!/usr/bin/env bash
# =============================================================================
# run_cells.sh -- FAIR-RULER RE-BASELINE (the D1 compute item). FROZEN.
#
# SIX deck-paired cells on ONE band and THE SAME 400 decks.
#
#   FIVE LADDER cells: the fair PIMC champion at five budgets -- k4x200=800,
#   k4x400=1600, k4x688=2752, k4x1376=5504, k8x1376=11008 -- each vs the FROZEN
#   clairvoyant HeuristicMCTS(h800, c=3.0) rung, on the PRODUCTION EXECUTION:
#   rust backend, rules_profile fixed_v1 WITH the R9 env latch, curve125
#   champion leaf, tie-arbiter OFF.
#
#   ONE ATTRIBUTION cell (W2752, owner-funded 2026-08-23): cell C2752 re-run on
#   the SAME decks under rules_profile `walled` with R9 OFF. Statistic
#   A = M_C2752 - M_W2752 -- the rules-only axis, within-band, same code rev.
#
# ⚠️⚠️ THE R9 INVERSION IS THIS LAUNCHER'S SHARPEST TRAP. The five ladder cells
# need CARCASSONNE_FIX_R9=1 exported BEFORE process start (R9 is import-latched).
# W2752 needs it OFF: `walled` carries r9_env_expected=False, so r9_env_ok==true
# on that artifact means r9_env_observed==FALSE. A file-scope export alone
# SILENTLY produces a walled artifact with r9_env_ok=false and voids the
# attribution read. W2752 therefore runs under `env -u CARCASSONNE_FIX_R9`, and
# `assert_r9_argv` (below) structurally asserts BOTH directions, fail-loud,
# before EVERY invocation (real cell and pilot arm alike) -- not just a
# post-hoc manifest read.
#
#   run_cells.sh <local|laptop> [--pilot] [--dry-run] [--band <SEED_START>]
#
# See DESIGN.md and READ_RULE.md for the full design and the branches.
#
# ⭐ THE FIVE LADDER CELLS DIFFER IN EXACTLY TWO EXPERIMENTAL ARGUMENTS --
# `--k-dets` and `--sims` -- which jointly name ONE thing: the candidate's total
# per-move budget. All argv are built from ONE shared COMMON array plus ONE cell
# table below, so the single-axis property is STRUCTURAL, not clerical. The
# ATTRIBUTION cell differs from C2752 in EXACTLY `--rules-profile` (+ the R9
# env inversion), for the same structural reason.
# (They also differ in `--out-subdir` and `--claim-host`, which are
# BOOKKEEPING: six cells cannot share one output directory or one
# `--shared-claim` tag without corrupting each other.)
#
# =============================================================================
# ⭐⭐ THE FOUR D2 INSTRUMENT FIXES (carried from the DRAFT, unchanged in intent):
#
#  (1) G-LEAF  the "champion" probe must run curve125 (a36d2e15a3b3d71d), never
#              the rung's own default leaf (42af12fce22e1a0f). FIX: CAND_LEAF_JSON
#              points at a FILE (champion_leaf_curve125.json, the D2-R2 route --
#              see PRE-FREEZE RECONCILIATION item (1) below) and `preflight_leaf`
#              asserts BOTH sides through the harness's OWN module before game 1,
#              on every leg, not just the pilot's post-hoc manifest read.
#
#  (2) G-RULES R9 cannot live in the profile (base_deck derives farm data at
#              import; the Rust registry latches a OnceLock) -- it MUST be
#              exported before the process starts for fixed_v1, and MUST be
#              absent for walled. FIX: `export CARCASSONNE_FIX_R9=1` at file
#              scope + `assert_r9_argv` (structural, both directions, fail-loud,
#              every invocation) + a child-process pre-flight assertion + the
#              pilot's record check.
#
#  (3) G-REV   the main tree must not move mid-run. FIX: PINNED_SRC_REV file +
#              a pre-flight refusal on dirty CODE paths + a re-assertion BETWEEN
#              EVERY CELL (before AND after) that ABORTS the sequence rather than
#              producing a mixed-rev ladder. CODE_PATHS is broadened per the
#              PRE-FREEZE RECONCILIATION item (3) below.
#
#  (4) G-BLIND READ_RULE.md gates G-BLIND against THIS launcher's BLIND_COMMIT
#              file + git ancestry, never the manifest (eval_fair_puct.py had no
#              stamping path at draft time). FORWARD-COMPATIBLE: `--stamp-key`
#              now EXISTS in the harness (confirmed at freeze time -- PRE-FREEZE
#              RECONCILIATION item (4)) so `detect_stamp_key` finds it and
#              G-BLIND gains the ADDITIVE manifest clause automatically.
# =============================================================================
#
# ⭐⭐⭐ PRE-FREEZE RECONCILIATION vs measurement/track_d2r2_prep/run_cells.sh
#     (DESIGN.md §7.1.1 named this OWED at draft time because track_d2r2_prep
#     did not exist on disk yet. It exists now -- reconciled at freeze time,
#     2026-08-24, DESIGN.md §0.4 is the pair-level record; this header is the
#     launcher-level one.)
#
#  (1) LEAF INJECTION VIA FILE ROUTE. d2r2 passes `--cand-leaf-json` a FILE path
#      (champion_leaf_curve125.json), not an inline JSON string, and builds a
#      champion THROUGH THE HARNESS'S OWN MODULE to assert both leaf hashes
#      before game 1 (its `preflight_leaf`). ADOPTED HERE VERBATIM: CAND_LEAF_JSON
#      now points at a file in this directory, and `preflight_leaf` (below) is
#      d2r2's function, unmodified except for the profile-argnostic call site
#      (this launcher calls it once per invocation, independent of rules_profile,
#      since leaf identity does not depend on the rules profile).
#
#  (2) R9 STRUCTURAL ASSERTION ON EVERY LEG. d2r2's `assert_r9_env` runs
#      unconditionally at the top of `main`, before --pilot/--dry-run branch out,
#      because ALL its cells want R9 ON. This launcher's cells want BOTH
#      directions (fixed_v1 ON, walled OFF), so a single top-of-main assertion
#      cannot serve both -- ADOPTED IN SPIRIT, NOT VERBATIM: `assert_r9_argv`
#      is a per-invocation, per-profile, BOTH-DIRECTIONS-EXPLICIT, fail-loud
#      check, called immediately before every real cell's `"${ARGV[@]}"` and
#      every pilot arm's `"${PARGV[@]}"` -- covering the DRAFT's gap (the DRAFT
#      never asserted R9 direction on the --pilot path at all).
#
#  (3) CODE_PATHS BROADENED. d2r2's rev-guard covers `src engine scripts rust
#      tests pyproject.toml setup.py`; the DRAFT covered only `src engine
#      scripts`. This band's ladder cells run the RUST backend, so a change
#      under `rust/` mid-run is exactly the D2-class defect (`code_rev` becomes
#      a lie about what played the games) and was NOT covered by the DRAFT.
#      ADOPTED: CODE_PATHS below matches d2r2's set. The DRAFT's stricter
#      posture (require CLEAN, not merely UNMOVED -- no `LAUNCH_DIRTY` override
#      exists here) is KEPT, not weakened to d2r2's tolerant form: this cell has
#      no precedent needing a dirty-code override, and READ_RULE §3.1's
#      G-REV text already commits to "clean source tree, identical rev".
#
#  (4) DUAL-ADDRESS --stamp-key. The DRAFT already auto-detected `--stamp-key`
#      and stamps BOTH addresses (BLIND_PROOF.json artifact + manifest, when
#      present) -- this is UNCHANGED, and CONFIRMED at freeze time: `--stamp-key`
#      now exists in `scripts/classical_search/eval_fair_puct.py` (added for
#      d2r2), so `detect_stamp_key` resolves `blind_stamp_mode=manifest` on a
#      real run of this launcher, same code path as before, no edit needed.
#
#  (5) REPO SELF-RESOLUTION (not d2r2-named, but load-bearing for the LAUNCH
#      step of THIS pair -- an isolated worktree on the laptop). The DRAFT
#      hardcoded `REPO=/home/doctor/projects/carcassone`; d2r2 resolves REPO
#      from the SCRIPT's own location (`git -C "$DIR" rev-parse --show-toplevel`),
#      which is correct in a worktree AND the main tree alike. ADOPTED: a
#      hardcoded REPO would silently run the LAUNCH worktree's launcher against
#      the MAIN tree's git history / BLIND_COMMIT / BAND_REGISTRY -- exactly
#      the kind of mixed-rev defect this whole reconciliation exists to close.
#      `CARC_PY` override is also adopted (exercising --dry-run from a build
#      worktree with no `.venv` of its own).
#
#  (6) PYTHONPATH / venv identity check. Neither script asserted this at draft
#      time; added here per the standing worktree-isolation rule
#      (CLAUDE.md / feedback-worktree-isolation-live-tree): PYTHONPATH is
#      exported to THIS repo's own src/engine (never the main tree's, once REPO
#      resolves per-worktree per (5)), and `preflight_leaf`'s python child
#      prints `carcassonne_ai.__file__` so a launch log states, in the record,
#      which tree's package actually loaded.
#
#  NOT ADOPTED, WITH REASON: d2r2's tolerant "code dirty is OK with
#  LAUNCH_DIRTY=1 + a mandatory reason" override. This pair's own G-REV text
#  commits to zero tolerance; introducing an override here would be a silent
#  weakening of a bar READ_RULE.md already states, not a reconciliation.
#
#  PER-CELL RE-CHECK BEFORE **AND** AFTER (`assert_rev_pinned` in the DRAFT) is
#  ALREADY STRICTER than d2r2's before-only `assert_rev_unmoved` and is KEPT.
#
# =============================================================================
# ADDITIONAL LAUNCHER-SAFETY HARDENING (owed at freeze, not from either prior
# launcher -- see DESIGN.md §0.4 items 7-9):
#
#  (7) PER-CELL DONE/FAILED SENTINELS. The DRAFT touched `DONE_cell_$NAME`
#      UNCONDITIONALLY after logging a nonzero rc -- a latent defect (a failed
#      cell looked identical to a completed one to anything reading sentinels
#      alone). FIXED: DONE_cell_$NAME is touched ONLY on rc==0; a nonzero rc
#      touches FAILED_cell_$NAME instead (cleared on a subsequent clean rc, so a
#      resumed-and-now-clean cell does not carry a stale FAILED marker).
#
#  (8) VOID-RATE ABORT (LAUNCHER SAFETY, NOT A STATISTICAL GATE). If any cell's
#      realized void rate (n_failed / games) reaches >=10%, the launcher ABORTS
#      the whole sequence immediately -- a coarse circuit breaker to stop
#      burning core-hours against a broken instrument, checked BEFORE any
#      adjudication. This is explicitly NOT READ_RULE.md's `G-N` gate (which is
#      a <2% ADJUDICATION threshold, decided by the read-rule against a frozen
#      record after the fact); the 10% figure here is a pre-adjudication launch
#      safety, and DESIGN.md §0.4 records it as such so a future reader cannot
#      mistake it for a bar on any statistic.
#
#  (9) chmod-as-launch-act. This file is committed at mode 644 (non-executable)
#      DELIBERATELY, per the DRAFT's own convention. `chmod +x` is a LAUNCH ACT,
#      performed by the executor immediately before the real launch, never
#      baked into the freeze commit.
# =============================================================================
#
# PRECONDITIONS, IN ORDER, ENFORCED BY THIS SCRIPT:
#   0. BLIND_COMMIT (a file in this directory, 40 hex chars) exists, is not a
#      placeholder, and is an ANCESTOR of HEAD.
#   1. PINNED_SRC_REV (a file in this directory, 40 hex chars) exists and
#      equals `git rev-parse HEAD`.
#   2. `git status --porcelain -- <CODE_PATHS>` is EMPTY.
#   3. BAND_CLAIMED (a file in this directory) exists -- the EXECUTOR drops it
#      after appending the band claim's row to governance/BAND_REGISTRY.csv.
#      This script NEVER claims or invents a band; it only checks that someone
#      else already did.
#   4. --band, if given, must equal PINNED_BAND -- it may only CONFIRM the
#      pinned value, never shadow it. A given --band that disagrees is FATAL.
#   5. --dry-run and --pilot are EXEMPT from 0-1 and 3 (neither spends
#      blindness nor touches the claimed band); --pilot still enforces 2,
#      because a pilot run on a dirty source tree proves nothing about the
#      cells that follow. Neither is exempt from the R9/leaf structural asserts.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached
# jobs -- launch as:
#   setsid nohup ./run_cells.sh local </dev/null >/dev/null 2>&1 & disown
#
# ⚠️ CENSUS FIRST (standing repo rule): this is a ~5.4-8.5 h exclusive tenant on
# whichever box runs it, and it carries a TIMING witness (W-TIMING). Nothing
# else may run beside it -- `ps -o pid,etime,%cpu,comm -C python --sort=-etime`
# on the target box, and the cluster dashboard, BEFORE launch.
#
# ⛔ THIS FILE IS COMMITTED NON-EXECUTABLE (mode 644) DELIBERATELY -- item (9)
# above. The executor `chmod +x` it only when authorizing a real launch, after
# BLIND_COMMIT, PINNED_SRC_REV and BAND_CLAIMED are all real, not placeholders.
# =============================================================================
set -euo pipefail

# --------------------------------------------------------------------------- #
# RECONCILIATION (5): REPO resolved from THIS FILE's own location, so this
# launcher is correct in the main tree and inside a git worktree alike -- the
# LAUNCH step runs it from an isolated worktree on the laptop, and a hardcoded
# path would silently point back at the wrong tree's git history.
# --------------------------------------------------------------------------- #
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SELF")"
REPO="$(git -C "$DIR" rev-parse --show-toplevel)"
PY="${CARC_PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || { echo "FATAL: no python at '$PY' (set CARC_PY to override)" >&2; exit 2; }
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
[ -f "$HARNESS" ] || { echo "FATAL: harness missing at '$HARNESS'" >&2; exit 2; }
LOGS="$DIR/logs"

# RECONCILIATION (6): PYTHONPATH pinned to THIS repo's own src/engine (never
# the main tree's, once REPO resolves per-worktree above).
export PYTHONPATH="$REPO/src:$REPO/engine${PYTHONPATH:+:$PYTHONPATH}"

# --------------------------------------------------------------------------- #
# D2 FIX (2) / RECONCILIATION (2): the R9 env latch, file-scope. fixed_v1
# expects this ON; walled needs it OFF (assert_r9_argv enforces the inversion
# structurally, per invocation, below).
# --------------------------------------------------------------------------- #
export CARCASSONNE_FIX_R9=1

# the band pinned by the pair -- --band may only CONFIRM this, never shadow it
PINNED_BAND=145000000000
PILOT_SEED_START=145999999000   # DISJOINT throwaway range, DESIGN §9; never pooled, never claimed

# RECONCILIATION (1): leaf injected via a FILE, not an inline string -- the
# d2r2 route. Byte-identical curve to the inline string the DRAFT (and the five
# G2 fair_ruler_* cells) passed.
CAND_LEAF_JSON="$DIR/champion_leaf_curve125.json"
EXPECT_CAND_LEAF_HASH=a36d2e15a3b3d71d
EXPECT_RUNG_LEAF_HASH=42af12fce22e1a0f

# RECONCILIATION (3): CODE_PATHS broadened to d2r2's set. Dirt here makes
# `code_rev` a lie about what played the games. (This launcher's posture stays
# STRICT -- no LAUNCH_DIRTY override exists; see the header's "NOT ADOPTED".)
CODE_PATHS=(src engine scripts rust tests pyproject.toml setup.py)

# --------------------------------------------------------------------------- #
# D2 FIX (4): BLIND stamping into the MANIFEST, forward-compatible. CONFIRMED
# at freeze time that `--stamp-key` now exists (added to the harness for
# d2r2) -- detect_stamp_key finds it and mode flips to "manifest" on a real run.
# --------------------------------------------------------------------------- #
STAMP_ARGS=()
BLIND_STAMP_MODE=artifact
detect_stamp_key() {
  if "$PY" "$HARNESS" --help 2>/dev/null | grep -q -- '--stamp-key'; then
    BLIND_STAMP_MODE=manifest
    STAMP_ARGS=(--stamp-key "BLIND_COMMIT=$(tr -d '[:space:]' < "$DIR/BLIND_COMMIT")")
    log "[blind] harness supports --stamp-key -> manifest stamping ENABLED (mode=manifest)"
  else
    BLIND_STAMP_MODE=artifact
    STAMP_ARGS=()
    log "[blind] harness has no --stamp-key -> G-BLIND reads BLIND_PROOF.json + git (mode=artifact)"
  fi
}

ROLE="${1:?usage: run_cells.sh <local|laptop> [--pilot] [--dry-run] [--band SEED_START]}"
shift || true
PILOT=0; DRY=0; BAND=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --pilot)   PILOT=1 ;;
    --dry-run) DRY=1 ;;
    --band)    BAND="${2:?--band needs a seed start}"; shift ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

if [ -n "$BAND" ] && [ "$PILOT" -eq 0 ] && [ "$BAND" != "$PINNED_BAND" ]; then
  echo "FATAL: --band $BAND disagrees with the pair's PINNED_BAND=$PINNED_BAND." >&2
  echo "FATAL: this launcher never accepts a different band for a real cell --" >&2
  echo "FATAL: if the band must change, the PAIR changes (DESIGN §5)." >&2
  exit 2
fi
BAND="${BAND:-$PINNED_BAND}"

# --------------------------------------------------------------------------- #
# BOX PARAMETERISATION. ⚠️ The share mount path DIFFERS BY BOX and W is PER-BOX,
# never extrapolated (standing repo rules). These are the launch-brief defaults;
# re-bench after any code-era change. The DESIGN §6 cost calibration is a LOCAL
# measurement -- the laptop's per-core speed for this python-rung/rust-probe mix
# is UNMEASURED, which is why --pilot re-projects the wall on the actual box
# before any real cell fires.
# --------------------------------------------------------------------------- #
case "$ROLE" in
  local)   SHARE=/mnt/c/carc-shared;  W=14 ;;
  laptop)  SHARE=/mnt/carc-shared;    W=22 ;;
  *) echo "FATAL: bad role '$ROLE' (local | laptop)" >&2; exit 2 ;;
esac
HOST="$(hostname)"
OUT="$SHARE/track_d1_fair_rebase"

# the local-calibrated rung cost, DESIGN §6 (d2_rung800, 2026-08-23, W=22)
LOCAL_RUNG_MS_PER_MOVE=624.3
PILOT_RUNG_MS_TOLERANCE=1.25     # >25% over the local figure => re-cost + owner re-confirm

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[fair_rebase $(ts) $HOST/$ROLE] $*"; }

# --------------------------------------------------------------------------- #
# RECONCILIATION (1): leaf pre-flight, d2r2's route, verbatim in spirit. Builds
# a candidate config THROUGH THE HARNESS'S OWN MODULE (importing eval_fair_puct
# applies its _CANON_ENV exactly as a real cell does) and asserts BOTH sides
# before game 1 -- candidate == curve125, rung == the CL-022 ruler, and that
# they are NOT the same leaf. Called on EVERY leg (pilot, real cells) below.
# Also prints carcassonne_ai.__file__ (RECONCILIATION (6)) so the log states
# which tree's package actually loaded.
# --------------------------------------------------------------------------- #
preflight_leaf() {
  [ -f "$CAND_LEAF_JSON" ] || { log "!!! FATAL: missing $CAND_LEAF_JSON"; exit 4; }
  CARC_PREFLIGHT_LEAF_JSON="$CAND_LEAF_JSON" \
  CARC_PREFLIGHT_CHAMP_HASH="$EXPECT_CAND_LEAF_HASH" \
  CARC_PREFLIGHT_RUNG_HASH="$EXPECT_RUNG_LEAF_HASH" \
  CARC_PREFLIGHT_REPO="$REPO" \
  "$PY" - <<'PFEOF' || { log "!!! FATAL: champion-leaf pre-flight FAILED -- see above. No game runs."; exit 4; }
import os, sys
repo = os.environ["CARC_PREFLIGHT_REPO"]
sys.path.insert(0, os.path.join(repo, "scripts", "classical_search"))
import carcassonne_ai
print(f"[preflight-leaf] carcassonne_ai.__file__ = {carcassonne_ai.__file__}")
if not carcassonne_ai.__file__.startswith(repo):
    print(f"[preflight-leaf] !!! carcassonne_ai loaded OUTSIDE this repo ({repo}) -- "
          f"the venv's editable install is pointing at the wrong tree. VOID.")
    sys.exit(1)
import eval_fair_puct as H
want_cand = os.environ["CARC_PREFLIGHT_CHAMP_HASH"]
want_rung = os.environ["CARC_PREFLIGHT_RUNG_HASH"]
cand = H._load_cand_leaf_cfg(os.environ["CARC_PREFLIGHT_LEAF_JSON"])
H._assert_cy_float_path(cand)
got_cand = H._leaf_hash(cand)
got_rung = H._leaf_hash(H.DEFAULT_CONFIG)
ok = True
print(f"[preflight-leaf] candidate leaf_hash = {got_cand}  (want {want_cand})")
print(f"[preflight-leaf] rung      leaf_hash = {got_rung}  (want {want_rung})")
if got_cand != want_cand:
    print("[preflight-leaf] !!! G-LEAF WOULD VOID: the candidate is not the champion leaf.")
    ok = False
if got_rung != want_rung:
    print("[preflight-leaf] !!! G-RUNG WOULD VOID: the rung is not the CL-022 ruler.")
    ok = False
if got_cand == got_rung:
    print("[preflight-leaf] !!! candidate and rung resolve the SAME leaf -- not the champion. VOID.")
    ok = False
sys.exit(0 if ok else 1)
PFEOF
  log "[G-LEAF/G-RUNG] champion-leaf pre-flight PASS (cand $EXPECT_CAND_LEAF_HASH / rung $EXPECT_RUNG_LEAF_HASH)"
}

# --------------------------------------------------------------------------- #
# RECONCILIATION (2): the R9 inversion, structural, both directions explicit,
# fail-loud, checked immediately before EVERY invocation (real cell or pilot
# arm) by inspecting the argv PREFIX about to run -- not the launcher's own
# shell env (which never changes; only the CHILD's env is modified via
# `env -u`). This closes the DRAFT's gap: its pilot path never asserted R9
# direction at all.
# --------------------------------------------------------------------------- #
assert_r9_argv() {   # $1 = profile (fixed_v1|walled), $2... = the PRE array elements
  local prof="$1"; shift
  local has_unset=0 tok
  for tok in "$@"; do
    if [ "$tok" = "-u" ]; then has_unset=1; fi
  done
  case "$prof" in
    fixed_v1)
      if [ "$has_unset" -eq 1 ]; then
        log "!!! FATAL: fixed_v1 invocation unsets CARCASSONNE_FIX_R9 -- it must stay ON. Aborting."
        exit 3
      fi
      log "[R9] fixed_v1: CARCASSONNE_FIX_R9 stays exported (file-scope, unmodified) -- correct."
      ;;
    walled)
      if [ "$has_unset" -ne 1 ]; then
        log "!!! FATAL: walled invocation does NOT unset CARCASSONNE_FIX_R9 -- the R9 INVERSION"
        log "!!! trap (DESIGN §3.6). A file-scope export alone silently voids the attribution"
        log "!!! read. Aborting BEFORE spending the band."
        exit 3
      fi
      log "[R9] walled: CARCASSONNE_FIX_R9 explicitly UNSET via 'env -u' -- the inversion, correct."
      ;;
    *) log "!!! FATAL: unknown rules profile '$prof' in assert_r9_argv"; exit 3 ;;
  esac
}

# --------------------------------------------------------------------------- #
# D2 FIX (3) / RECONCILIATION (3): source-rev pinning + inter-cell
# re-assertion, over the broadened CODE_PATHS. Stricter than d2r2 (before AND
# after every cell; no dirty override) -- kept from the DRAFT unmodified in
# posture, broadened only in which paths count as "code".
# --------------------------------------------------------------------------- #
src_is_clean() {
  local dirty
  dirty="$(git -C "$REPO" status --porcelain -- "${CODE_PATHS[@]}" || echo FAIL)"
  if [ -n "$dirty" ]; then
    log "!!! SOURCE TREE DIRTY (${CODE_PATHS[*]}):"
    echo "$dirty" | sed 's/^/[fair_rebase]   /'
    return 1
  fi
  return 0
}

record_src_boundary() {   # $1 = label
  local rev; rev="$(git -C "$REPO" rev-parse HEAD)"
  "$PY" - "$DIR/SRC_CLEAN.jsonl" "$1" "$rev" <<'SEOF' || true
import json, sys, time
p, label, rev = sys.argv[1], sys.argv[2], sys.argv[3]
with open(p, "a") as f:
    f.write(json.dumps({"boundary": label, "head": rev,
                        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "src_clean": True}) + "\n")
SEOF
}

assert_rev_pinned() {   # $1 = boundary label
  local pinned rev
  pinned="$(tr -d '[:space:]' < "$DIR/PINNED_SRC_REV")"
  rev="$(git -C "$REPO" rev-parse HEAD)"
  if [ "$pinned" != "$rev" ]; then
    log "!!! FATAL at boundary '$1': HEAD=$rev != PINNED_SRC_REV=$pinned"
    log "!!! The tree MOVED mid-run. This is the exact D2 mixed-rev defect."
    log "!!! ABORTING rather than producing a mixed-rev ladder."
    exit 3
  fi
  if ! src_is_clean; then
    log "!!! FATAL at boundary '$1': ${CODE_PATHS[*]} dirty. ABORTING."
    exit 3
  fi
  record_src_boundary "$1"
}

# --------------------------------------------------------------------------- #
# D2 FIX (4): BLIND_COMMIT proof written HERE, from git -- never expected in
# the manifest alone (the artifact + ancestry form always stands; the manifest
# form is ADDITIVE per RECONCILIATION (4)).
# --------------------------------------------------------------------------- #
write_blind_proof() {
  local bc; bc="$(tr -d '[:space:]' < "$DIR/BLIND_COMMIT")"
  local head; head="$(git -C "$REPO" rev-parse HEAD)"
  local anc="no"
  if git -C "$REPO" merge-base --is-ancestor "$bc" HEAD 2>/dev/null; then anc="yes"; fi
  "$PY" - "$DIR/BLIND_PROOF.json" "$bc" "$head" "$anc" "$BLIND_STAMP_MODE" <<'BEOF' || true
import json, sys, time
p, bc, head, anc, mode = sys.argv[1:6]
json.dump({"blind_commit": bc, "head_at_launch": head,
           "is_ancestor_of_head": anc == "yes",
           "blind_stamp_mode": mode,
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("eval_fair_puct.py's --stamp-key path (when present) is ADDITIVE; "
                   "READ_RULE §3 G-BLIND is gated against THIS artifact plus git ancestry "
                   "ALWAYS, and against the manifest ADDITIONALLY when blind_stamp_mode==manifest.")},
          open(p, "w"), indent=2, sort_keys=True)
BEOF
  if [ "$anc" != "yes" ]; then
    log "!!! FATAL: BLIND_COMMIT $bc is NOT an ancestor of HEAD -- G-BLIND cannot pass."
    exit 2
  fi
}

require_preconditions() {
  local bc="$DIR/BLIND_COMMIT" psr="$DIR/PINNED_SRC_REV" bcl="$DIR/BAND_CLAIMED"
  if [ ! -f "$bc" ] || ! grep -qE '^[0-9a-f]{40}$' "$bc"; then
    log "!!! FATAL: $bc missing or not a 40-hex sha."
    exit 2
  fi
  if [ ! -f "$psr" ] || ! grep -qE '^[0-9a-f]{40}$' "$psr"; then
    log "!!! FATAL: $psr missing or not a 40-hex sha (D2 mixed-rev fix)."
    exit 2
  fi
  if [ ! -f "$bcl" ]; then
    log "!!! FATAL: $bcl missing. The EXECUTOR drops it AFTER appending the band claim's"
    log "!!! row to governance/BAND_REGISTRY.csv. This script never claims a band."
    exit 2
  fi
  detect_stamp_key
  write_blind_proof
  assert_rev_pinned "pre-flight"
  # R9 latch, asserted in a CHILD process -- the same import path the cells use.
  "$PY" -c "
import sys
sys.path.insert(0, '$REPO/src')
from carcassonne_ai import rules_profile as rp
assert rp.r9_env_on(), 'CARCASSONNE_FIX_R9 not latched in a child process'
prof = rp.resolve('fixed_v1')
m = prof.as_manifest()
assert m['r9_env_ok'] is True, m
print('[preflight] fixed_v1 resolved, r9_env_ok=True')
" || { log "!!! FATAL: R9 pre-flight FAILED -- this is the D2 G-RULES defect."; exit 2; }
}

# --------------------------------------------------------------------------- #
# RUN_LIVE.json freeze-latch sentinel. The repo's PreToolUse hook refuses a
# MAIN-TREE git commit while this file exists. Dropped for the WHOLE six-cell
# sequence, cleared on ANY exit via trap.
# --------------------------------------------------------------------------- #
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("fair-ruler re-baseline freeze-latch sentinel: a MAIN-TREE commit "
                   "while this leg is live risks a mixed-rev ladder (the D2 defect). "
                   "Cleared on the launcher's EXIT trap."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  log "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

print_cost_estimate() {
  cat <<EOF
[dry-run] cost estimate (DESIGN §6, calibrated on realized 2026-08-23 records,
[dry-run] model validated to -1.5% against d2_rung800 / d2_rung1600 wall-clock):
[dry-run]   A800     54.7 s/game x 800 =  43,760 s = 12.2 core-h
[dry-run]   B1600    63.2 s/game x 800 =  50,560 s = 14.0 core-h
[dry-run]   C2752    75.3 s/game x 800 =  60,240 s = 16.7 core-h
[dry-run]   D5504   104.2 s/game x 800 =  83,360 s = 23.2 core-h
[dry-run]   E11008  162.2 s/game x 800 = 129,760 s = 36.0 core-h
[dry-run]   ---- ladder subtotal          367,680 s = 102.1 core-h
[dry-run]   W2752    75.3 s/game x 800 =  60,240 s = 16.7 core-h  (attribution, walled)
[dry-run]   TOTAL, FUNDED                427,920 s = 118.8 core-h   (4,800 games)
[dry-run]   wall @ W=$W  =>  ~$(awk "BEGIN{printf \"%.1f\", 427920/$W/3600}") h   (local W14 => ~8.5 h; laptop/local W22 => ~5.4 h)
EOF
}

# --------------------------------------------------------------------------- #
# VOID-RATE ABORT (LAUNCHER SAFETY, NOT A STATISTICAL GATE -- see header (8)).
# Reads the most recently written summary.json under the cell's out-subdir and
# aborts the WHOLE sequence if n_failed / games >= 10%.
# --------------------------------------------------------------------------- #
check_void_rate() {   # $1 = out-subdir, $2 = expected games, $3 = context label
  local sub="$1" expect_n="$2" ctx="$3"
  local sumfile
  sumfile="$(find "$OUT/$sub" -name summary.json 2>/dev/null | sort | tail -1)"
  if [ -z "$sumfile" ] || [ ! -f "$sumfile" ]; then
    log "[void-rate] WARNING: no summary.json found under $OUT/$sub for $ctx -- skipping check (not fatal by itself)."
    return 0
  fi
  "$PY" - "$sumfile" "$expect_n" "$ctx" <<'VEOF'
import json, sys
p, expect_n, ctx = sys.argv[1], int(sys.argv[2]), sys.argv[3]
s = json.load(open(p))
n_failed = s.get("n_failed", 0) or 0
n_scored = s.get("n_scored", s.get("n", expect_n))
denom = max(n_scored + n_failed, expect_n, 1)
rate = n_failed / denom
print(f"[void-rate] {ctx}: n_failed={n_failed} denom={denom} void_rate={rate:.3%}")
if rate >= 0.10:
    print(f"[void-rate] !!! ABORT: {ctx} void rate {rate:.1%} >= 10% -- LAUNCHER SAFETY circuit "
          f"breaker (NOT the READ_RULE G-N adjudication gate, which is a separate <2% threshold "
          f"decided after the fact against a frozen record; this is a pre-adjudication abort to "
          f"stop burning compute against a broken instrument).")
    sys.exit(1)
print(f"[void-rate] {ctx} OK (< 10% launcher-safety threshold).")
VEOF
}

# --------------------------------------------------------------------------- #
# ONE shared COMMON array + ONE budget table => the five cells' single-axis    #
# property is STRUCTURAL (READ_RULE §3 G-SINGLEVAR / G-BUDGET).                #
# --------------------------------------------------------------------------- #
build_common() {
  local PROF="${1:-fixed_v1}"
  # ⚠️ --n 800 counts GAMES; --paired gives 2 seatings per deck, so --n 800 =
  # 400 DECKS. DO NOT "fix" this to 400 -- that would halve the deck set
  # DESIGN §4/§5/§6 costed and gated.
  COMMON=(--info fair --opponent h800 --backend rust
          --exact-k 2
          --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
          --rung-sims 800
          --cand-leaf-json "$CAND_LEAF_JSON"
          --n 800 --paired --seed-start "$BAND"
          --rules-profile "$PROF" --workers "$W"
          --out-root "$OUT"
          --shared-claim --claim-stale-secs 1800
          --no-results-csv)
  # ⛔ NO --cand-tiearb-* FLAG ANYWHERE. DESIGN §3.4: the ruler is arbiter-off
  # on every rung, deliberately, and READ_RULE §3 G-TIEARB voids on any cell
  # whose manifest reads cand_tiearb.enabled=true.
}

# name : k_dets : sims/det : total : out-subdir : rules-profile
# ⚠️ ORDER MATTERS: the LADDER cells run first, so a box/time problem costs the
# BUNDLED extra cell and not the funded deliverable. W2752 runs last.
CELLS=(
  "A800:4:200:800:fr_a800:fixed_v1"
  "B1600:4:400:1600:fr_b1600:fixed_v1"
  "C2752:4:688:2752:fr_c2752:fixed_v1"
  "D5504:4:1376:5504:fr_d5504:fixed_v1"
  "E11008:8:1376:11008:fr_e11008:fixed_v1"
  "W2752:4:688:2752:fr_w2752:walled"
)

cell_argv() {
  local NAME="$1" KD="$2" SD="$3" SUB="$4" PROF="$5"
  build_common "$PROF"
  # ⭐ THE R9 INVERSION. `walled` expects R9 OFF (r9_env_expected=False), so the
  # attribution cell MUST start from an environment without the latch -- R9 is
  # import-time and cannot be undone inside the process.
  PRE=()
  if [ "$PROF" = "walled" ]; then PRE=(env -u CARCASSONNE_FIX_R9); fi
  assert_r9_argv "$PROF" "${PRE[@]:-}"
  ARGV=("${PRE[@]}" nice -n 19 "$PY" -u "$HARNESS" "${COMMON[@]}"
        --k-dets "$KD"
        --sims "$SD"
        --out-subdir "$SUB"
        --claim-host "d1fr-$NAME-$HOST"
        "${STAMP_ARGS[@]}")
}

# $1 = rules profile (fixed_v1 | walled). BOTH ARMS ARE MANDATORY (DESIGN §9):
# the walled arm is ~2 min and is the ONLY thing that catches the R9 inversion
# before 17 core-h are spent on a voided attribution cell.
run_pilot_arm() {
  local PROF="$1" sub="pilot_${1}"
  log "PILOT[$PROF] -- n=16 (8 decks x 2 seatings), seed-start=$PILOT_SEED_START"
  local PRE=()
  if [ "$PROF" = "walled" ]; then
    PRE=(env -u CARCASSONNE_FIX_R9)
    log "PILOT[walled] -- under \`env -u CARCASSONNE_FIX_R9\`; expects r9_env_observed=FALSE"
  fi
  assert_r9_argv "$PROF" "${PRE[@]:-}"
  local PARGV=("${PRE[@]}" nice -n 19 "$PY" -u "$HARNESS"
        --info fair --opponent h800 --backend rust --exact-k 2
        --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
        --rung-sims 800 --cand-leaf-json "$CAND_LEAF_JSON"
        --k-dets 4 --sims 200
        --n 16 --paired --seed-start "$PILOT_SEED_START"
        --rules-profile "$PROF" --workers "$W"
        --out-root "$OUT" --out-subdir "$sub"
        --shared-claim --claim-stale-secs 1800
        --claim-host "d1fr-pilot-$PROF-$HOST"
        --no-results-csv)
  if [ "$DRY" -eq 1 ]; then
    printf '[dry-run] pilot[%s] argv:' "$PROF"; printf ' %q' "${PARGV[@]}"; printf '\n'; return 0
  fi
  mkdir -p "$LOGS" "$OUT/$sub"
  "${PARGV[@]}" >> "$LOGS/pilot_$PROF.log" 2>&1 || \
    log "pilot[$PROF] rc=$? (the harness is resumable under --shared-claim)"
  log "PILOT[$PROF] DONE -- sweeping every invocation-property gate against the REAL records"
  check_void_rate "$sub" 16 "pilot[$PROF]"
  "$PY" - "$OUT/$sub" "$EXPECT_CAND_LEAF_HASH" "$EXPECT_RUNG_LEAF_HASH" \
          "$LOCAL_RUNG_MS_PER_MOVE" "$PILOT_RUNG_MS_TOLERANCE" "$W" "$PROF" <<'PEOF'
import json, sys, pathlib
d, want_cand, want_rung = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
local_rung_ms, tol, W, prof = float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6]), sys.argv[7]
mans = sorted(d.glob("**/manifest.json")); sums = sorted(d.glob("**/summary.json"))
if not mans or not sums:
    print("[pilot] !!! no manifest.json / summary.json under", d); sys.exit(1)
m = json.load(open(mans[-1])); s = json.load(open(sums[-1])); c = m["config"]
fails = []
def chk(name, got, want):
    ok = got == want
    print(f"[pilot] {'PASS' if ok else 'FAIL'}  {name}: {got!r} (want {want!r})")
    if not ok: fails.append(name)
chk("G-LEAF cand_leaf_hash",  c.get("cand_leaf_hash"), want_cand)
chk("G-LEAF rung.leaf_hash",  (c.get("rung") or {}).get("leaf_hash"), want_rung)
chk(f"G-RULES name [{prof}]",      (m.get("rules_profile") or {}).get("name"), prof)
chk(f"G-RULES r9_env_ok [{prof}]", (m.get("rules_profile") or {}).get("r9_env_ok"), True)
chk(f"G-RULES r9_env_observed [{prof}]",
    (m.get("rules_profile") or {}).get("r9_env_observed"), prof == "fixed_v1")
chk("G-BACKEND name",         (c.get("backend") or {}).get("name"), "rust")
chk("G-BACKEND requested",    (c.get("backend") or {}).get("requested"), "rust")
chk("G-BACKEND mixed_builds", m.get("mixed_builds"), False)
print("[pilot] G-BACKEND converted_sides:", (c.get("backend") or {}).get("converted_sides"))
if "candidate" not in ((c.get("backend") or {}).get("converted_sides") or []):
    fails.append("G-BACKEND converted_sides")
chk("G-RUNG agent",           (c.get("rung") or {}).get("agent"), "HeuristicMCTS")
chk("G-RUNG c",               (c.get("rung") or {}).get("c"), 3.0)
chk("G-RUNG sims",            (c.get("rung") or {}).get("sims"), 800)
chk("G-TIEARB enabled",       (c.get("cand_tiearb") or {}).get("enabled"), False)
chk("G-EXACT exact_k",        (c.get("endgame") or {}).get("exact_k"), 2)
chk("G-EXACT mode",           (c.get("endgame") or {}).get("mode"), "marginalized")
chk("G-BUDGET k_dets",        (c.get("champion") or {}).get("k_dets"), 4)
chk("G-BUDGET total_sims",    (c.get("champion") or {}).get("total_sims"), 800)
chk("G-N n_failed",           s.get("n_failed"), 0)
rung_ms, cand_ms = s.get("rung_ms_per_move"), s.get("champ_prefix_ms_per_move")
solver = s.get("solver_secs_per_game")
print(f"[pilot] rung_ms_per_move={rung_ms}  champ_prefix_ms_per_move={cand_ms} "
      f"(⚠️ champ_prefix_* is the CANDIDATE side in eval_fair_puct)  solver_s/game={solver}")
if rung_ms is None or cand_ms is None:
    fails.append("W-COST fields absent")
else:
    per_sim_ms = cand_ms / 800.0
    tot = 0.0
    for name, S in (("A800",800),("B1600",1600),("C2752",2752),("D5504",5504),("E11008",11008)):
        # DESIGN.md §6.2.2 amendment: 0.070/0.071 already ARE the ms->s scale of the
        # ~70/71 moves/game the DESIGN §6 model names (70/1000, 71/1000) -- do NOT
        # divide by 1000 again (that was the decimal-scale bug: printed re-projected
        # core-h/wall were ~1000x too small). This is the informational print only;
        # the W-COST gate comparison below (rung_ms vs local_rung_ms*tol) is untouched.
        sg = 0.070*per_sim_ms*S + 0.071*rung_ms + (solver or 1.11)
        sg *= 1.02
        tot += sg*800
        print(f"[pilot]   re-projected {name}: {sg:6.1f} s/game  -> {sg*800/3600:5.2f} core-h")
    print(f"[pilot]   re-projected TOTAL: {tot/3600:.1f} core-h  ->  {tot/W/3600:.1f} h wall at W={W}")
    if rung_ms > local_rung_ms * tol:
        print(f"[pilot] !!! rung_ms_per_move {rung_ms:.1f} exceeds the local-calibrated "
              f"{local_rung_ms} by >{(tol-1)*100:.0f}% -- RE-COST AND RE-CONFIRM WITH THE "
              f"OWNER before launch (DESIGN §6.2). Do not absorb this.")
        fails.append("W-COST rung ms/move over tolerance")
print()
if fails:
    print("[pilot] ⛔ PILOT FAILED:", ", ".join(fails))
    print("[pilot] ⛔ Fix the LAUNCHER and re-pilot. The band has not been touched.")
    sys.exit(1)
print("[pilot] ✅ every invocation-property gate PASSES on a real record; band untouched.")
PEOF
}

main() {
  preflight_leaf                     # RECONCILIATION (1) -- every leg, no exemptions

  if [ "$PILOT" -eq 1 ]; then
    log "PILOT band is DISCARDED and never pooled with the real band (DESIGN §9)."
    if ! src_is_clean; then
      log "!!! FATAL: pilot refuses to run on a dirty ${CODE_PATHS[*]} --"
      log "!!! a pilot on a moving tree proves nothing about the cells that follow."
      exit 2
    fi
    run_pilot_arm fixed_v1
    run_pilot_arm walled
    log "PILOT COMPLETE -- BOTH arms swept. Neither the band nor blindness was spent."
    return 0
  fi

  if [ "$DRY" -eq 1 ]; then
    log "role=$ROLE W=$W band=$BAND share=$SHARE (dry-run: nothing starts, no guards enforced)"
    for spec in "${CELLS[@]}"; do
      IFS=: read -r NAME KD SD TOT SUB PROF <<< "$spec"
      cell_argv "$NAME" "$KD" "$SD" "$SUB" "$PROF"
      printf '[dry-run] cell %s (k%sx%s = %s total sims, rules=%s):' "$NAME" "$KD" "$SD" "$TOT" "$PROF"
      printf ' %q' "${ARGV[@]}"; printf '\n'
    done
    print_cost_estimate
    return 0
  fi

  require_preconditions
  log "role=$ROLE W=$W band=$BAND out=$OUT"
  log "⭐ the five cells differ in EXACTLY --k-dets and --sims (one axis: total budget)"
  log "⚠️ they also differ in --out-subdir and --claim-host, which are BOOKKEEPING"
  log "⛔ tie-arbiter OFF on every rung (DESIGN §3.4) -- no --cand-tiearb-* flag exists here"

  mkdir -p "$LOGS" "$OUT"
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "fair-ruler re-baseline, 6 cells (role=$ROLE)"

  for spec in "${CELLS[@]}"; do
    IFS=: read -r NAME KD SD TOT SUB PROF <<< "$spec"
    if [ -f "$DIR/DONE_cell_$NAME" ]; then
      log "cell $NAME already DONE -- skipping"; continue
    fi
    assert_rev_pinned "before-$NAME"          # D2 FIX (3)
    cell_argv "$NAME" "$KD" "$SD" "$SUB" "$PROF"
    log "cell $NAME (k${KD}x${SD} = $TOT total sims, rules=$PROF) -> $OUT/$SUB"
    if [ "$PROF" = "walled" ]; then
      log "⭐ ATTRIBUTION CELL -- running under \`env -u CARCASSONNE_FIX_R9\` (the R9 INVERSION):"
      log "   walled expects R9 OFF, so r9_env_ok==true here means r9_env_observed==FALSE."
      log "   A FAIL of the §3B GW-* gates voids the ATTRIBUTION READ ONLY, never the ladder."
    fi
    set +e
    "${ARGV[@]}" >> "$LOGS/cell_$NAME.log" 2>&1
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      log "cell $NAME rc=$rc (the harness is resumable under --shared-claim)"
      touch "$DIR/FAILED_cell_$NAME"
    else
      rm -f "$DIR/FAILED_cell_$NAME" 2>/dev/null || true
    fi
    assert_rev_pinned "after-$NAME"           # D2 FIX (3)
    check_void_rate "$SUB" 800 "cell $NAME" || {
      log "!!! ABORTING the sequence: VOID-RATE launcher-safety breaker tripped for $NAME."
      exit 7
    }
    if [ "$rc" -eq 0 ]; then
      touch "$DIR/DONE_cell_$NAME"
    fi
  done

  local all_done=1
  for spec in "${CELLS[@]}"; do
    IFS=: read -r NAME _ _ _ _ _ <<< "$spec"
    [ -f "$DIR/DONE_cell_$NAME" ] || all_done=0
  done
  if [ "$all_done" -eq 1 ]; then
    run_live_clear
    log "DONE -- all six cells complete, RUN_LIVE cleared"
    log "NEXT: the adjudicator is written from READ_RULE.md's text ALONE, by a"
    log "session that has seen NO statistic from this run (blind-adjudication"
    log "discipline, READ_RULE §4)."
  else
    log "one or more cells did not complete -- RUN_LIVE stays until every DONE sentinel exists"
  fi
}

main "$@"
