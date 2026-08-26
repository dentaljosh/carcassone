#!/usr/bin/env bash
# =============================================================================
# run_cells.sh -- D2-R2 RUNG-COMPRESSION CELL LAUNCHER.
#
# THE PRE-REGISTERED INSTRUMENT-FIX SUCCESSOR to measurement/track_d2_prep,
# whose first attempt adjudicated U-UNREADABLE on four INSTRUMENT gates. See
# DESIGN.md §0 for the provenance banner. This file is that instrument fix.
#
# CELL R800 (--rung-sims 800) and CELL R1600 (--rung-sims 1600), deck-paired on
# ONE band and THE SAME 200 decks, against a frozen fair-PIMC probe (k4x1376,
# tie-arbiter OFF), vs the frozen HeuristicMCTS(h800 / h1600, c=3.0) rung.
#
# ⚠️ PROBE BUDGET AMENDED 2026-08-25 (DESIGN §0 banner item 9): k4x1032 -> k4x1376.
# The §9 pilot read ratio 0.659 vs bar [0.85,1.20] on BOTH boxes because FIX 1
# below (the R9 export) makes the python h800 rung ~58% dearer per move; the
# frozen budget had been derived against non-R9 rung figures. The re-pick is the
# ORCHESTRATOR's pair-level decision under READ_RULE §179-183, taken with the band
# UNSPENT (zero games), NOT a launcher re-pick. ⛔ It does not renew: a pilot FAIL
# at 1376 STOPS the run. See §0 item 9a for the standalone R9-cost finding and 9b
# for the CARC_PY execution deviation.
#
#   run_cells.sh <local|laptop-side> [--pilot] [--dry-run] [--band <SEED_START>]
#
# ⭐ THE TWO REAL CELLS DIFFER IN EXACTLY ONE EXPERIMENTAL ARGUMENT --
# `--rung-sims`. Both cells' argv are built from ONE shared COMMON array below,
# so G-SINGLEVAR is STRUCTURAL, not clerical. (They also differ in
# `--out-subdir` and `--claim-host`, which are BOOKKEEPING: two cells cannot
# share one output directory or one `--shared-claim` tag without corrupting
# each other.)
#
# =============================================================================
# THE FOUR INSTRUMENT FIXES vs measurement/track_d2_prep/run_cells.sh
# =============================================================================
# FIX 1 (G-RULES).  The old launcher never exported CARCASSONNE_FIX_R9, so
#   `fixed_v1` cells ran with `r9_env_ok=False`. R9 CANNOT live in the rules
#   profile: `base_deck` derives the farm data at IMPORT time and the Rust
#   registry latches a `OnceLock`, so it must be in the ENVIRONMENT before the
#   process starts (src/carcassonne_ai/rules_profile.py, R9_ENV_VAR). This
#   launcher EXPORTS it at the top of the file -- before any leg, including
#   --pilot and --dry-run -- and `assert_r9_env` REFUSES to run if it is unset
#   or not truthy.
#
# FIX 2 (G-LEAF).  The old launcher played the RUNG-DEFAULT v2.9 leaf, not the
#   champion curve125 leaf: for `--info fair --opponent h800` the harness does
#   NOT auto-inject curve125 (that auto-injection fires only for fair-netprior
#   / head-to-head / bare-net / greedy), so `cand_leaf_hash` read the rung's own
#   hash. The champion leaf reaches the CANDIDATE the way production play does:
#   the in-process `--cand-leaf-json` mechanism (champion_leaf_curve125.json),
#   NEVER by exporting CARCASSONNE_V29_MEEPLE_CURVE -- the harness's _CANON_ENV
#   uses setdefault, so a pre-set curve env would MOVE THE RUNG to curve125 too
#   and silently invalidate the CL-022 ruler. `preflight_leaf` builds one
#   champion through the harness's own module and asserts BOTH sides before
#   game 1: candidate == a36d2e15a3b3d71d AND rung == 42af12fce22e1a0f.
#
# FIX 3 (G-TOOL a).  The old launcher's two cells ran at DIFFERENT repo revs (a
#   commit landed on main between the legs via a freeze-latch override). This
#   launcher SNAPSHOTS `git rev-parse HEAD` + the code-path dirty fingerprint at
#   start, RE-CHECKS before EACH cell, and REFUSES to start a subsequent cell if
#   either moved -- loud, with both revs named.
#
# FIX 4 (G-TOOL b).  The pair's "BLIND_COMMIT in both manifests" sub-clause was
#   UNSATISFIABLE: eval_fair_puct.py had no stamping path at any address the
#   read-rule searches. A `--stamp-key KEY=VALUE` passthrough was added to the
#   harness's manifest writer (additive, inert unless passed, tested); this
#   launcher routes the BLIND_COMMIT file's content through it. The stamp lands
#   at BOTH searched addresses: `manifest["BLIND_COMMIT"]` and
#   `manifest["config"]["stamps"]["BLIND_COMMIT"]`.
#
# ALSO (G-TOOL, the dirty-tree half).  Both first-attempt manifests read
#   `<sha>-dirty`. `require_clean_code` REFUSES a real cell when any CODE path
#   is dirty, overridable ONLY by `LAUNCH_DIRTY=1` with a mandatory
#   `LAUNCH_DIRTY_REASON`. ⚠️ The refusal is scoped to CODE paths ON PURPOSE and
#   the reason is the structural test applied to this launcher's own guard: this
#   repo's working tree carries churning measurement artifacts at essentially
#   all times, and this launcher itself must drop `RUN_LIVE.json` inside
#   `measurement/` for the freeze-latch hook to see it -- so a whole-tree dirty
#   refusal would fail on EVERY healthy run, which is exactly the defect class
#   these fixes exist to remove. Non-code dirt is RECORDED (PRELAUNCH json +
#   log) and is not fatal. Dirty CODE is what would make `code_rev` a lie about
#   what actually played the games, and that is always fatal here.
#
# PRECONDITIONS, IN ORDER, ENFORCED BY THIS SCRIPT:
#   0. BLIND_COMMIT (a file in this directory, 40 hex chars) exists and is not a
#      placeholder.
#   1. BAND_CLAIMED (a file in this directory) exists -- the EXECUTOR drops it
#      after appending BAND_CLAIM_DRAFT.json's row to
#      governance/BAND_REGISTRY.csv. This script NEVER claims or invents a band.
#   2. --band, if given, must equal PINNED_BAND -- it may only CONFIRM the
#      pinned value, never shadow it. A disagreeing --band is FATAL.
#   3. --dry-run and --pilot are EXEMPT from preconditions 0-1 and from the
#      dirty-code refusal: neither spends blindness or a real band. The pilot
#      burns a disjoint throwaway seed range (DESIGN §9) that is discarded and
#      never pooled; --dry-run starts nothing at all. ⚠️ They are NOT exempt from
#      FIX 1 or FIX 2 -- a pilot that verified the equal-time ratio under the
#      wrong rules or the wrong leaf is not a pilot for THIS cell.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached
# jobs -- launch as:
#   setsid nohup ./run_cells.sh local </dev/null >/dev/null 2>&1 & disown
# =============================================================================
set -euo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SELF")"
# Resolve the repo from THIS FILE's location, so the launcher is correct in the
# main tree and inside a git worktree alike (and so a dry-run/pilot can be
# exercised from a build worktree without pointing at the live tree by accident).
REPO="$(git -C "$DIR" rev-parse --show-toplevel)"
# The interpreter is the repo venv. CARC_PY overrides it for ONE purpose only:
# exercising --dry-run / the pre-flights from a build worktree, which carries the
# CODE under test but no `.venv` of its own. A real cell on a real box never sets
# it, and the resolved value is logged either way.
PY="${CARC_PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || { echo "FATAL: no python at '$PY' (set CARC_PY to override)" >&2; exit 2; }
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
[ -f "$HARNESS" ] || { echo "FATAL: harness missing at '$HARNESS'" >&2; exit 2; }

# ---------------------------------------------------------------------------
# FIX 1 -- R9. Exported BEFORE anything can import carcassonne_ai. `fixed_v1`
# EXPECTS this (rules_profile.r9_env_expected=True) and CANNOT apply it itself:
# import-time farm derivation + a Rust OnceLock. Without it every manifest reads
# rules_profile.r9_env_ok == False and the cell is U-UNREADABLE on G-RULES.
# ---------------------------------------------------------------------------
export CARCASSONNE_FIX_R9=1

# ⚠️ DELIBERATELY NOT EXPORTED: CARCASSONNE_V29_MEEPLE_CURVE. The champion leaf
# is injected IN-PROCESS on the candidate side only (FIX 2). Exporting the curve
# would move the harness's DEFAULT_CONFIG and therefore MOVE THE RUNG -- see the
# CURVE125 block in eval_fair_puct.py and `_assert_rung_is_ruler`.

# the band pinned by the pair -- --band may only CONFIRM this, never shadow it
PINNED_BAND=144000000000
PILOT_SEED_START=144999999000   # DISJOINT throwaway range, DESIGN §9; never pooled, never claimed

# The two leaf hashes this cell's identity rests on (DESIGN §3.1, READ_RULE §3).
CHAMP_LEAF_HASH=a36d2e15a3b3d71d      # candidate: the curve125 production champion
RUNG_RULER_LEAF_HASH=42af12fce22e1a0f # rung: env DEFAULT_CONFIG, the CL-022 ruler
CAND_LEAF_JSON="$DIR/champion_leaf_curve125.json"

# CODE paths: dirt here makes `code_rev` a lie about what played the games.
CODE_PATHS=(src engine scripts rust tests pyproject.toml setup.py)

ROLE="${1:?usage: run_cells.sh <local|laptop-side> [--pilot] [--dry-run] [--band SEED_START]}"
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
  echo "FATAL: if the band must change, the PAIR changes (DESIGN §5 + BAND_CLAIM_DRAFT.json)." >&2
  exit 2
fi
BAND="${BAND:-$PINNED_BAND}"

case "$ROLE" in
  local)       SHARE=/mnt/c/carc-shared;   W=22 ;;
  laptop-side) SHARE=/mnt/carc-shared;     W=16 ;;
  *) echo "FATAL: bad role '$ROLE' (local | laptop-side)" >&2; exit 2 ;;
esac
# ⚠️ W is PER-BOX and NOT extrapolated (local 22, laptop 16). The h-rung side of
# every cell is Python by design (DESIGN §3.3), so this is NOT the same worker
# profile as an all-rust invocation -- do not reuse a W tuned for one.
HOST="$(hostname)"
OUT="$SHARE/track_d2r2_prep"
# Logs, sentinels and the pre-launch record live on the SHARE, not in the repo:
# a launcher that writes into its own working tree dirties the very tree whose
# cleanliness it is asserting.
LOGS="$OUT/logs"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[d2r2 $(ts) $HOST/$ROLE] $*"; }

# --------------------------------------------------------------------------- #
# FIX 1 assertion. Refuses if the export above was somehow undone (a wrapper    #
# that scrubs the env, a `env -i` invocation, an edited copy of this file).     #
# Runs for EVERY leg including --pilot and --dry-run.                           #
# --------------------------------------------------------------------------- #
assert_r9_env() {
  local v="${CARCASSONNE_FIX_R9:-}"
  case "$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) log "[G-RULES] CARCASSONNE_FIX_R9=$v (fixed_v1 expects it; import-latched)" ;;
    *)
      log "!!! FATAL: CARCASSONNE_FIX_R9 is unset or not truthy (got '${v}')."
      log "!!! fixed_v1 declares r9_env_expected=True and CANNOT apply R9 itself"
      log "!!! (import-time farm derivation + a Rust OnceLock), so every manifest"
      log "!!! would read rules_profile.r9_env_ok=False -> G-RULES VOID."
      exit 3 ;;
  esac
}

# --------------------------------------------------------------------------- #
# FIX 2 assertion. Build the champion leaf THROUGH THE HARNESS'S OWN MODULE     #
# (importing eval_fair_puct applies its _CANON_ENV exactly as a real cell does) #
# and assert BOTH sides before game 1:                                          #
#   candidate (--cand-leaf-json) == a36d2e15a3b3d71d   -> G-LEAF                #
#   rung      (env DEFAULT_CONFIG) == 42af12fce22e1a0f -> G-RUNG / the ruler    #
# The second half is not decoration: it is what catches someone sourcing        #
# champ_env.sh (or exporting the curve) and silently moving the ruler.          #
# --------------------------------------------------------------------------- #
preflight_leaf() {
  [ -f "$CAND_LEAF_JSON" ] || { log "!!! FATAL: missing $CAND_LEAF_JSON"; exit 4; }
  CARC_PREFLIGHT_LEAF_JSON="$CAND_LEAF_JSON" \
  CARC_PREFLIGHT_CHAMP_HASH="$CHAMP_LEAF_HASH" \
  CARC_PREFLIGHT_RUNG_HASH="$RUNG_RULER_LEAF_HASH" \
  CARC_PREFLIGHT_REPO="$REPO" \
  "$PY" - <<'PFEOF' || { log "!!! FATAL: champion-leaf pre-flight FAILED -- see above. No game runs."; exit 4; }
import os, sys
repo = os.environ["CARC_PREFLIGHT_REPO"]
sys.path.insert(0, os.path.join(repo, "scripts", "classical_search"))
# Importing the harness module applies its _CANON_ENV (setdefault) exactly as a
# real cell does, and is side-effect-free otherwise (it is __main__-guarded).
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
print(f"[preflight-leaf] candidate curve     = {cand.v29_meeple_curve}")
print(f"[preflight-leaf] rung      curve     = {H.DEFAULT_CONFIG.v29_meeple_curve}")
print(f"[preflight-leaf] r9 env observed     = {os.environ.get('CARCASSONNE_FIX_R9')!r}")
if got_cand != want_cand:
    print("[preflight-leaf] !!! G-LEAF WOULD VOID: the candidate is not the champion leaf.")
    ok = False
if got_rung != want_rung:
    print("[preflight-leaf] !!! G-RUNG WOULD VOID: the rung is not the CL-022 curve100 ruler.")
    print("[preflight-leaf] !!! Did something export CARCASSONNE_V29_MEEPLE_CURVE / source "
          "champ_env.sh? _CANON_ENV uses setdefault, so a pre-set curve MOVES THE RULER.")
    ok = False
if got_cand == got_rung:
    print("[preflight-leaf] !!! candidate and rung resolve the SAME leaf -- the probe is "
          "not the champion. VOID.")
    ok = False
sys.exit(0 if ok else 1)
PFEOF
  log "[G-LEAF/G-RUNG] champion-leaf pre-flight PASS (cand $CHAMP_LEAF_HASH / rung $RUNG_RULER_LEAF_HASH)"
}

# --------------------------------------------------------------------------- #
# FIX 3 -- rev pinning. Snapshot at start; re-check before EACH cell.          #
# --------------------------------------------------------------------------- #
code_dirty_list() {
  git -C "$REPO" status --porcelain -- "${CODE_PATHS[@]}" 2>/dev/null || true
}
tree_dirty_count() {
  git -C "$REPO" status --porcelain 2>/dev/null | wc -l | tr -d ' '
}
snapshot_rev() {
  SNAP_REV="$(git -C "$REPO" rev-parse HEAD)"
  SNAP_CODE_DIRTY="$(code_dirty_list | sort | md5sum | awk '{print $1}')"
  SNAP_CODE_DIRTY_N="$(code_dirty_list | grep -c . || true)"
  log "[G-TOOL] rev snapshot: HEAD=$SNAP_REV code-dirty-files=$SNAP_CODE_DIRTY_N fp=$SNAP_CODE_DIRTY"
  log "[G-TOOL] whole-tree dirty entries (informational, NOT fatal): $(tree_dirty_count)"
}
assert_rev_unmoved() {
  local who="$1"
  local now_rev now_fp now_n
  now_rev="$(git -C "$REPO" rev-parse HEAD)"
  now_fp="$(code_dirty_list | sort | md5sum | awk '{print $1}')"
  now_n="$(code_dirty_list | grep -c . || true)"
  if [ "$now_rev" != "$SNAP_REV" ]; then
    log "!!! FATAL (G-TOOL): the repo rev MOVED between cells."
    log "!!!   at launch : $SNAP_REV"
    log "!!!   now ($who): $now_rev"
    log "!!! The first D2 attempt died exactly here: a commit landed on main between"
    log "!!! the two legs, so the two cells were not the same instrument. REFUSING to"
    log "!!! start $who. Re-run the whole pair at ONE rev; do not salvage half a pair."
    exit 5
  fi
  if [ "$now_fp" != "$SNAP_CODE_DIRTY" ]; then
    log "!!! FATAL (G-TOOL): the CODE dirty-state CHANGED between cells."
    log "!!!   at launch : $SNAP_CODE_DIRTY_N file(s), fp=$SNAP_CODE_DIRTY"
    log "!!!   now ($who): $now_n file(s), fp=$now_fp"
    log "!!! Same rev, different working code -> the two cells are not the same"
    log "!!! instrument even though code_rev would read the same sha. REFUSING."
    code_dirty_list | sed 's/^/!!!   /' | while read -r l; do log "$l"; done
    exit 5
  fi
  log "[G-TOOL] rev re-check OK before $who: HEAD=$now_rev, code dirt unchanged ($now_n)"
}

# --------------------------------------------------------------------------- #
# ALSO -- dirty-CODE refusal (real cells only; pilot/dry-run exempt).          #
# --------------------------------------------------------------------------- #
require_clean_code() {
  local dirt n
  dirt="$(code_dirty_list)"
  n="$(printf '%s' "$dirt" | grep -c . || true)"
  if [ "$n" -eq 0 ]; then
    log "[G-TOOL] code paths clean (${CODE_PATHS[*]})"
    return 0
  fi
  log "!!! CODE PATHS ARE DIRTY ($n entr(ies)) -- code_rev would be a lie about what ran:"
  printf '%s\n' "$dirt" | sed 's/^/!!!   /'
  if [ "${LAUNCH_DIRTY:-0}" = "1" ]; then
    if [ -z "${LAUNCH_DIRTY_REASON:-}" ]; then
      log "!!! FATAL: LAUNCH_DIRTY=1 requires LAUNCH_DIRTY_REASON=<why>. No reason, no override."
      exit 6
    fi
    log "!!! OVERRIDE ACCEPTED: LAUNCH_DIRTY=1"
    log "!!! REASON: $LAUNCH_DIRTY_REASON"
    log "!!! This is recorded in the PRELAUNCH record and in this log. The manifests"
    log "!!! will still read <sha>-dirty; the adjudicator reads this line to know why."
    return 0
  fi
  log "!!! FATAL: refusing to start a real cell on dirty CODE."
  log "!!! Commit or stash the code paths, or re-run with"
  log "!!!   LAUNCH_DIRTY=1 LAUNCH_DIRTY_REASON='<why>' $SELF $ROLE"
  exit 6
}

# --------------------------------------------------------------------------- #
# BLIND_COMMIT + BAND_CLAIMED -- both real files.                               #
# --------------------------------------------------------------------------- #
require_blind_and_band() {
  local bc="$DIR/BLIND_COMMIT" bcl="$DIR/BAND_CLAIMED"
  if [ ! -f "$bc" ] || ! grep -qE '^[0-9a-f]{40}$' "$bc"; then
    log "!!! FATAL: $bc is missing or does not hold a 40-hex-char sha."
    log "!!! The EXECUTOR writes it AFTER DESIGN.md + READ_RULE.md land on main."
    log "!!! (--dry-run and --pilot are exempt -- neither spends blindness.)"
    exit 2
  fi
  if [ ! -f "$bcl" ]; then
    log "!!! FATAL: $bcl is missing."
    log "!!! The EXECUTOR drops it AFTER appending BAND_CLAIM_DRAFT.json's row"
    log "!!! to governance/BAND_REGISTRY.csv. This script never claims a band."
    exit 2
  fi
}

blind_commit_value() { tr -d '[:space:]' < "$DIR/BLIND_COMMIT"; }

# --------------------------------------------------------------------------- #
# ONE shared COMMON array -- both real cells' argv extend it (G-SINGLEVAR is    #
# STRUCTURAL). FIX 2 and FIX 4 live here, so neither cell can be built without  #
# them.                                                                        #
# --------------------------------------------------------------------------- #
build_common() {
  # ⚠️ --n 400: the harness's --n counts GAMES; --paired gives 2 seatings per
  # deck, so --n 400 = 200 DECKS (DESIGN §4/§5's costed and gated deck count).
  # DO NOT "fix" this to 200.
  # ⚠️ --sims 1376: DESIGN §0 banner item 9 (AMENDMENT 2026-08-25), the
  # ORCHESTRATOR-level re-pick taken under READ_RULE §179-183's own delegation
  # after the §9 pilot read 0.659 vs bar [0.85,1.20] on BOTH boxes. Cause: FIX 1
  # (the R9 export) makes the python h800 rung ~58% dearer per move (553.8 ->
  # 877.2 ms), and the frozen budget was derived against non-R9 rung figures.
  # k4x1376 = 5504 total = `fair_ruler_rebase_5504`, a NAMED lineage budget ->
  # 5504 x 0.140 ms/total-sim = 770.6 ms => projected ratio 0.878, in-bar.
  # SUPERSEDES §0 item 5's k4x1032 (which superseded §3.1's verbatim 688).
  # ⛔ THE ALLOWANCE IS EXHAUSTED AND DOES NOT RENEW: if the pilot fails at 1376
  # the run STOPS and returns to the orchestrator. No third re-pick.
  COMMON=(--info fair --opponent h800 --backend rust
          --k-dets 4 --sims 1376 --exact-k 2
          --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
          --n 400 --paired --seed-start "$BAND"
          --rules-profile fixed_v1 --workers "$W"
          --cand-leaf-json "$CAND_LEAF_JSON"
          --out-root "$OUT"
          --shared-claim --claim-stale-secs 1800
          --no-results-csv)
  if [ "$1" = "with-stamp" ]; then
    COMMON+=(--stamp-key "BLIND_COMMIT=$(blind_commit_value)")
  fi
}

# $1 = cell name (R800|R1600), $2 = rung-sims, $3 = out-subdir, $4 = with-stamp|no-stamp
cell_argv() {
  local NAME="$1" RS="$2" SUB="$3" STAMP="${4:-with-stamp}"
  build_common "$STAMP"
  ARGV=(nice -n 19 "$PY" -u "$HARNESS" "${COMMON[@]}"
        --rung-sims "$RS"
        --out-subdir "$SUB"
        --claim-host "d2r2-$NAME-$HOST")
}

# --------------------------------------------------------------------------- #
# RUN_LIVE.json freeze-latch sentinel. MUST live under measurement/ for the     #
# repo's PreToolUse hook to see it, so this one file necessarily dirties the    #
# working tree -- which is why the dirty refusal above is scoped to CODE paths. #
# --------------------------------------------------------------------------- #
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("D2-R2 rung-compression cell freeze-latch sentinel: a MAIN-TREE "
                   "commit while this leg is live is what produced the first "
                   "attempt's two-revision pair. Cleared on the launcher's EXIT trap."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  log "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

write_prelaunch() {
  mkdir -p "$OUT"
  CARC_PL_OUT="$OUT/PRELAUNCH_${HOST}.json" \
  CARC_PL_REV="$SNAP_REV" CARC_PL_FP="$SNAP_CODE_DIRTY" \
  CARC_PL_N="$SNAP_CODE_DIRTY_N" CARC_PL_TREE_N="$(tree_dirty_count)" \
  CARC_PL_BAND="$BAND" CARC_PL_ROLE="$ROLE" CARC_PL_W="$W" \
  CARC_PL_BLIND="$(blind_commit_value)" \
  CARC_PL_CAND="$CHAMP_LEAF_HASH" CARC_PL_RUNG="$RUNG_RULER_LEAF_HASH" \
  CARC_PL_DIRTY_OVERRIDE="${LAUNCH_DIRTY:-0}" \
  CARC_PL_DIRTY_REASON="${LAUNCH_DIRTY_REASON:-}" \
  "$PY" - <<'PLEOF' || true
import json, os, socket, time
d = {
    "run_id": "track_d2r2_prep",
    "host": socket.gethostname(), "role": os.environ["CARC_PL_ROLE"],
    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "band_seed_start": int(os.environ["CARC_PL_BAND"]),
    "workers": int(os.environ["CARC_PL_W"]),
    "blind_commit": os.environ["CARC_PL_BLIND"],
    "code_rev_head": os.environ["CARC_PL_REV"],
    "code_dirty_fingerprint": os.environ["CARC_PL_FP"],
    "code_dirty_files": int(os.environ["CARC_PL_N"]),
    "tree_dirty_entries": int(os.environ["CARC_PL_TREE_N"]),
    "dirty_override": os.environ["CARC_PL_DIRTY_OVERRIDE"] == "1",
    "dirty_override_reason": os.environ["CARC_PL_DIRTY_REASON"] or None,
    "r9_env": os.environ.get("CARCASSONNE_FIX_R9"),
    "expected_cand_leaf_hash": os.environ["CARC_PL_CAND"],
    "expected_rung_leaf_hash": os.environ["CARC_PL_RUNG"],
    "note": ("Per-box pre-launch record for the D2-R2 instrument-fix successor. "
             "Adjudicates nothing; it is the witness that FIX 1-4 were in force "
             "on THIS box before game 1."),
}
json.dump(d, open(os.environ["CARC_PL_OUT"], "w"), indent=2, sort_keys=True)
print("[prelaunch] wrote", os.environ["CARC_PL_OUT"])
PLEOF
}

print_dry_run() {
  local name="$1" rs="$2" sub="$3"
  cell_argv "$name" "$rs" "$sub" no-stamp
  printf '[dry-run] cell %s (rung-sims=%s):' "$name" "$rs"
  printf ' %q' "${ARGV[@]}"
  printf '\n'
  printf '[dry-run]   (a real cell also carries --stamp-key BLIND_COMMIT=<sha from %s>)\n' \
    "$DIR/BLIND_COMMIT"
}

run_pilot() {
  log "PILOT -- CELL R800 config only, n=16 (8 decks x 2 seatings), seed-start=$PILOT_SEED_START"
  log "PILOT band is DISCARDED and never pooled with the real cell band (DESIGN §9)."
  log "⚠️ Budget is k4x1376 per DESIGN §0 item 9 (AMENDMENT 2026-08-25) -- the"
  log "⚠️ ORCHESTRATOR's pair-level re-pick after k4x1032 read 0.659 on both boxes."
  log "⚠️ This pilot must REALIZE the projected 0.878 in-bar. ⛔ THE ALLOWANCE IS NOW"
  log "⚠️ EXHAUSTED: a FAIL here STOPS the run and returns to the orchestrator."
  local sub="pilot_r800"
  local PARGV=(nice -n 19 "$PY" -u "$HARNESS"
        --info fair --opponent h800 --backend rust
        --k-dets 4 --sims 1376 --exact-k 2
        --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
        --n 16 --paired --seed-start "$PILOT_SEED_START"
        --rules-profile fixed_v1 --workers "$W"
        --cand-leaf-json "$CAND_LEAF_JSON"
        --out-root "$OUT" --out-subdir "$sub"
        --shared-claim --claim-stale-secs 1800
        --claim-host "d2r2-pilot-$HOST"
        --no-results-csv
        --rung-sims 800)
  if [ "$DRY" -eq 1 ]; then
    printf '[dry-run] pilot argv:'
    printf ' %q' "${PARGV[@]}"
    printf '\n'
    return 0
  fi
  mkdir -p "$LOGS" "$OUT/$sub"
  "${PARGV[@]}" >> "$LOGS/pilot_r800.log" 2>&1 || \
    log "pilot rc=$? (the harness is resumable under --shared-claim)"
  log "PILOT DONE -- checking summary.json for the equal-time ratio (DESIGN §9 / §7 G-TIMING)"
  "$PY" - "$OUT/$sub" <<'PEOF'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1])
cands = sorted(d.glob("**/summary.json"))
if not cands:
    print("[pilot] !!! no summary.json found under", d); sys.exit(1)
s = json.load(open(cands[-1]))
champ_ms = s.get("champ_prefix_ms_per_move")
rung_ms = s.get("rung_ms_per_move")
if champ_ms is None or rung_ms is None:
    print("[pilot] !!! summary.json missing champ_prefix_ms_per_move or rung_ms_per_move"); sys.exit(1)
# ⚠️ FIELD-NAME TRAP (DESIGN §3.3): in eval_fair_puct, champ_prefix_ms_per_move is
# the CANDIDATE side -- the opposite convention from eval_puct_priors.
ratio = champ_ms / rung_ms
lo, hi = 0.85, 1.20
ok = lo <= ratio <= hi
print(f"[pilot] champ_prefix_ms_per_move={champ_ms:.3f} rung_ms_per_move={rung_ms:.3f} ratio={ratio:.4f}")
print(f"[pilot] bar=[{lo},{hi}]  =>  {'PASS' if ok else 'FAIL'}")
if not ok:
    print("[pilot] !!! The re-pick allowance is EXHAUSTED TWICE OVER: k4x1032 was picked "
          "on the first attempt's pilot band (DESIGN §0 item 5), and k4x1376 is the "
          "ORCHESTRATOR's own pair-level re-pick of 2026-08-25 (§0 item 9), taken after "
          "1032 read 0.659 on both boxes. ⛔ A FAIL HERE STOPS THE RUN and returns to the "
          "orchestrator. There is no third re-pick, and none by this launcher ever.")
sys.exit(0 if ok else 1)
PEOF
}

main() {
  assert_r9_env                      # FIX 1 -- every leg, no exemptions
  preflight_leaf                     # FIX 2 -- every leg, no exemptions

  if [ "$PILOT" -eq 1 ]; then
    run_pilot
    return 0
  fi

  if [ "$DRY" -eq 1 ]; then
    snapshot_rev
    log "role=$ROLE W=$W band=$BAND (dry-run: no games start, no blind/band guards enforced)"
    print_dry_run R800  800  d2r2_rung800
    print_dry_run R1600 1600 d2r2_rung1600
    return 0
  fi

  require_blind_and_band
  snapshot_rev                       # FIX 3 -- the baseline both cells are pinned to
  require_clean_code                 # ALSO -- dirty-CODE refusal (real cells only)

  log "role=$ROLE W=$W band=$BAND out=$OUT"
  log "BLIND_COMMIT=$(blind_commit_value) (stamped into BOTH manifests via --stamp-key)"
  log "⭐ the two real cells differ in EXACTLY ONE EXPERIMENTAL argument: --rung-sims"
  log "⚠️ they also differ in --out-subdir and --claim-host, which are BOOKKEEPING."

  mkdir -p "$LOGS" "$OUT"
  write_prelaunch
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "d2r2 rung-compression cell (role=$ROLE)"

  for pair in "R800:800:d2r2_rung800" "R1600:1600:d2r2_rung1600"; do
    IFS=: read -r NAME RS SUB <<< "$pair"
    if [ -f "$OUT/DONE_cells_${NAME}_${HOST}" ]; then
      log "cell $NAME already DONE on $HOST -- skipping"; continue
    fi
    assert_rev_unmoved "cell $NAME"  # FIX 3 -- re-checked before EACH cell
    cell_argv "$NAME" "$RS" "$SUB" with-stamp
    log "cell $NAME (rung-sims=$RS) -> $OUT/$SUB"
    "${ARGV[@]}" >> "$LOGS/cells_$NAME.log" 2>&1 || \
      log "cell $NAME rc=$? (the harness is resumable under --shared-claim)"
    touch "$OUT/DONE_cells_${NAME}_${HOST}"
  done

  if [ -f "$OUT/DONE_cells_R800_${HOST}" ] && [ -f "$OUT/DONE_cells_R1600_${HOST}" ]; then
    run_live_clear
    log "DONE -- both cells complete on $HOST, RUN_LIVE cleared"
  else
    log "one or more cells did not complete -- RUN_LIVE stays until both DONE sentinels exist"
  fi
}

# Testability seam. `CARC_D2R2_LIB_ONLY=1 source run_cells.sh local` defines every
# guard above and runs NOTHING — so tests/test_d2r2_instrument_fix.py can call
# assert_r9_env / preflight_leaf / assert_rev_unmoved / require_clean_code directly
# instead of asserting on log text. It changes no behaviour of a real launch: the
# variable is never set on a box, and an unset variable takes the `main` branch.
if [ "${CARC_D2R2_LIB_ONLY:-0}" != "1" ]; then
  main "$@"
fi
