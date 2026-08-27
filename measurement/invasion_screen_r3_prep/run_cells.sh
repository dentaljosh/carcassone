#!/usr/bin/env bash
# =============================================================================
# run_cells.sh -- INVASION-RISK TERM FAMILY, ROUND-3 FINE LADDERS + JOINT AT 2752. LAUNCHER.
#
# EIGHT cells (DESIGN.md SS6.4). The two boxes run CONCURRENTLY; the order below
# is the seed-allocation order, and the WITHIN-BOX order is the sequence:
#
#   LAPTOP, in this order (W=22):
#     A_LOW   invasion_beta  = 0.02                      vs CHAMPION   400 dk/800 g
#     A_MID   invasion_beta  = 0.05                      vs CHAMPION   400 dk/800 g
#     A_HIGH  invasion_beta  = 0.10                      vs CHAMPION   400 dk/800 g
#     J_LOW   invasion_beta 0.02 + invasion_gamma 0.03   vs CHAMPION   400 dk/800 g
#     J_HIGH  invasion_beta 0.05 + invasion_gamma 0.07   vs CHAMPION   400 dk/800 g
#   LOCAL, in this order (W=14):
#     C_LOW   invasion_gamma = 0.03   vs SHAPE-B INVADER               400 dk/800 g
#     C_MID   invasion_gamma = 0.07   vs SHAPE-B INVADER               400 dk/800 g
#     C_HIGH  invasion_gamma = 0.15   vs SHAPE-B INVADER               400 dk/800 g
#
# Every cell: k4x688 = 2752 total sims BOTH sides; rust BOTH sides; fixed_v1 + R9;
# exact-K 2 marginalized; tie-arbiter OFF both sides; deck-paired; band
# 153000000000, each cell on its OWN DISJOINT deck range.
#
# ⭐⭐ THE TWO **J** CELLS ARE THE ADOPTION-CHAIN-ELIGIBLE ONES. Their opponent is
# the CHAMPION OF RECORD and their candidate is the champion leaf carrying a light
# beta AND a light gamma AS ONE LEAF, so a J cell at z >= +2.0 fires PROMOTE-JOINT
# and licenses the production H2H per the frozen four-link chain -- ⛔ FOR THE
# PACKAGE, NOT FOR A PART. A joint cell moves two knobs at once and attributes
# NOTHING to either; attribution needs a later ABLATION pair on a fresh band. See
# screen_lib.JOINT_ATTRIBUTION_BAN and READ_RULE.md SS4.6b.
#
# ⭐ THE A AND J CELLS play the PLAIN CHAMPION (leaf a36d2e15a3b3d71d). THE C CELLS
# DO NOT -- their opponent is the SHAPE-B INVADER (champion + invasion_alpha 0.09 @
# cap 11.0, leaf 42adadc988784b44 == round 1's B_MID candidate bit-for-bit, and
# round 2's C opponent bit-for-bit), because SHAPES.md SS3 forbids screening a
# DEFENCE-ONLY term against an opponent that does not invade. The opponent leaf is
# moved by the ENV (DESIGN.md SS2.5); the candidate takes it back off with EXPLICIT
# ZEROS in its own --cand-leaf-json.
# ⭐ SHAPE B IS THE INVADER-GENERATOR **INSTRUMENT**, NOT A ROUND-3 CANDIDATE:
# round 2 demoted it on a noise signature, and round 3 runs no B candidate cell.
# Using a demoted shape as an instrument is not a claim about it as a candidate.
#
# ⭐ TWO BOXES (DESIGN.md SS6.5). The CELL->BOX ASSIGNMENT IS FROZEN IN
# screen_lib.py and G-HOST enforces it against the emitted manifest:
#
#     --host local   -> C_LOW C_MID C_HIGH                    (W=14, /mnt/c/carc-shared)
#     --host laptop  -> A_LOW A_MID A_HIGH J_LOW J_HIGH       (W=22, /mnt/carc-shared)
#
# ⛔ THIS IS THE OPPOSITE OF ROUND 2's ASSIGNMENT, and deliberately so. OWNER
# CONSTRAINT 2026-08-27, verbatim: "limit local to w14 starting at 11am" -- the
# round straddles the owner's interactive-use window, so W_LOCAL is FROZEN AT 14
# FOR THE WHOLE ROUND (never 22-then-14: --workers is per-invocation, a cell runs
# in bounded resumable passes, and a mid-round change would run one cell's passes
# at two different W). That cuts local throughput 36% and moves the balance point
# past the flip, so the fastest whole-shape split is now C-on-local / A+J-on-laptop.
# All six partitions are priced in DESIGN SS6.5(iii) and screen_lib.split_table(),
# and screen_lib.sanity_check() REFUSES a pair whose frozen assignment is not the
# fastest. ⚠️ W IS THROUGHPUT-ONLY: games are bit-identical at any W and no gate in
# this pair reads a clock.
#
# WHOLE CELLS PER BOX -- a cell's records are NEVER split across machines, and this
# launcher REFUSES to run a cell that is not frozen to its --host. Shapes are
# assigned WHOLE, so every pre-registered contrast (SS4.5), every interior-lift
# statistic (SS4.5b) and every SS4.7 noise-signature check is WITHIN one box; the
# round never relies on cross-box float identity, which this program HAS been
# bitten by (the Xeon was RE-RETIRED 2026-08-02 because AVX-512 makes the G0
# determinism check FAIL).
#
# THE TWO BOXES RUN CONCURRENTLY, so the round's wall clock is the MAX of the two
# (~4.98 h), not the sum (~171.5 core-h). The executor launches the laptop via the
# piped-script ssh pattern with setsid detach -- see DESIGN.md SS6.5(iv).
#
#   run_cells.sh --host local|laptop [--dry-run] [--smoke] [--only CELL] [--band SEED_START]
#
# eval_fair_puct.py has NO --limit flag, so each cell runs in bounded PASSES:
# one `timeout`d invocation over the FULL range under --shared-claim per pass
# (the harness skips already-recorded cells), and a FINAL sealing pass walks the
# whole range so the harness writes the pooled summary.json the adjudicator reads.
#
# ⛔ THIS FILE IS TRACKED AT MODE 644, DELIBERATELY NOT EXECUTABLE. `chmod +x` is
# the ORCHESTRATOR's own launch act, performed only after BLIND_COMMIT and
# PINNED_SRC_REV are real shas, BAND_CLAIMED exists, and DESIGN.md SS0's FUNDING
# line is signed off -- never by this build. NOT LAUNCHED as of this commit.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached jobs:
#   setsid nohup ./run_cells.sh </dev/null >/dev/null 2>&1 & disown
#
# ⭐ NOT AN EXCLUSIVE TENANT -- and that is a DESIGNED property, not laxity.
# This pair is SIMS-denominated: no equal-time gate, no burn-in, no timing bar.
# Every gate and the primary statistic are functions of GAME OUTCOMES, and
# outcomes are bit-identical under co-tenancy and at any W (the determinization
# merge is a sequential post-join fold -- rust/carc/carc-core/src/fair/mod.rs
# 22-32 -- and run-to-run byte-stability was verified empirically on this exact
# instrument at round 1's freeze). A co-tenant can move WALL CLOCK and nothing
# else. So the process census below is ADVISORY.
# ⚠️ THE EXCEPTION IS RAM, WHICH IS A HARD, FAIL-CLOSED CHECK: a WSL guest OOM
# tears down the WHOLE VM, not one worker (reference_wsl2_host_memory_teardown).
#
# ⛔ AND THE WHEEL IS NOT A FREE CHOICE. G-WHEEL-SAME keys on carc_rs_binary_sha,
# and round 3 inherits round 1's IDENT PASS -- for the SECOND time, round 2 having
# carried it once with all seven of its cells reporting the pinned sha, on BOTH
# boxes. The executor installs THE SAME WHEEL FILE on BOTH boxes ($WHEEL_FILE), so the
# sha is identical on every cell regardless of host. ⛔ NEVER a laptop-local
# rebuild: different bytes, different sha, and the gate REFUSES -- correctly.
# =============================================================================
set -euo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SELF")"
# shellcheck source=WORKERS.conf
. "$DIR/WORKERS.conf"

# Resolve the repo from THIS FILE's location, so the launcher is correct in the
# main tree and inside a git worktree alike -- and so --dry-run can be exercised
# from a build worktree without pointing at the live tree by accident.
REPO="$(git -C "$DIR" rev-parse --show-toplevel)"
# The interpreter is the repo venv. CARC_PY overrides it for ONE purpose only:
# exercising --dry-run / the pre-flights from a build worktree, which carries the
# CODE under test but no `.venv` of its own. A real cell never sets it, and the
# resolved value is logged either way.
PY="${CARC_PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || { echo "FATAL: no python at '$PY' (set CARC_PY to override)" >&2; exit 2; }
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
[ -f "$HARNESS" ] || { echo "FATAL: harness missing at '$HARNESS'" >&2; exit 2; }
# THE ONE IMPLEMENTATION of every bar and every cost figure. The launcher's
# per-cell pre-check imports this, so it CANNOT drift from the adjudicator's
# G-LEAF.
LIB="$DIR/screen_lib.py"
[ -f "$LIB" ] || { echo "FATAL: screen_lib.py missing at '$LIB'" >&2; exit 2; }
ADJ="$DIR/analyze_screen.py"

LOGS="$DIR/logs"
CODE_PATHS=(src engine scripts rust tests pyproject.toml setup.py)
# OUT and W are resolved from --host below (DESIGN.md SS6.5).
OUT=""
W=""
BOXROLE=""

# ---------------------------------------------------------------------------
# R9. Exported BEFORE anything can import carcassonne_ai. `fixed_v1` EXPECTS
# this and CANNOT apply it itself: import-time farm derivation + a Rust OnceLock.
# Without it every manifest reads rules_profile.r9_env_ok == false and every cell
# is U-UNREADABLE on G-RULES.
# ---------------------------------------------------------------------------
export CARCASSONNE_FIX_R9=1

# ⚠️ DELIBERATELY NOT EXPORTED HERE: CARCASSONNE_V29_MEEPLE_CURVE (exporting the
# curve would move the harness's env DEFAULT_CONFIG globally, which
# _assert_rung_is_ruler refuses and which would silently change what "the
# champion" means), and the two CARCASSONNE_INVASION_* variables. The invasion
# env is PER-CELL and is emitted INTO EACH ARGV by build_argv(), never exported
# process-wide -- a process-wide export would give the A and J cells a shape-B
# opponent too, which is the single most damaging thing this launcher could do.

DRY=0; SMOKE=0; ONLY=""; BAND_ARG=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --smoke)   SMOKE=1 ;;
    --host)    BOXROLE="${2:?--host needs local|laptop}"; shift ;;
    --only)    ONLY="${2:?--only needs a cell name}"; shift ;;
    --band)    BAND_ARG="${2:?--band needs a seed start}"; shift ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

# --------------------------------------------------------------------------- #
# ⭐ --host IS MANDATORY AND FAIL-CLOSED. There is no default.                  #
#                                                                              #
# A default would be the whole two-box hazard in one line: a launcher that      #
# silently assumed "local" on the laptop would run the WRONG CELLS, at the      #
# WRONG SHARE MOUNT, and G-HOST would void them AFTER the compute was spent.    #
# The cell->box assignment is frozen in the pair; the launcher must be told     #
# which side of it it is on.                                                    #
# --------------------------------------------------------------------------- #
case "$BOXROLE" in
  local)  W="$W_LOCAL";  SHARE="$SHARE_LOCAL" ;;
  laptop) W="$W_LAPTOP"; SHARE="$SHARE_LAPTOP" ;;
  "")  echo "FATAL: --host is REQUIRED (local|laptop). There is no default:" >&2
       echo "FATAL: the cell->box assignment is FROZEN in the prereg (DESIGN SS6.5)," >&2
       echo "FATAL: and a launcher that guessed would run the wrong cells at the" >&2
       echo "FATAL: wrong share mount and be voided by G-HOST after the fact." >&2
       exit 2 ;;
  *)   echo "FATAL: --host '$BOXROLE' is not a known box role (local|laptop)." >&2
       exit 2 ;;
esac
OUT="$SHARE/$OUT_LEAF"

# --band may only CONFIRM the pair's band, never shadow it.
if [ -n "$BAND_ARG" ] && [ "$BAND_ARG" != "$BAND" ]; then
  echo "FATAL: --band $BAND_ARG disagrees with the pair's BAND=$BAND." >&2
  echo "FATAL: this launcher never accepts a different band for a real cell --" >&2
  echo "FATAL: if the band must change, the PAIR changes (DESIGN.md SS5 + BAND_CLAIM.json)." >&2
  exit 2
fi

HOST="$(hostname)"
ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[invscreen-r3 $(ts) $HOST] $*"; }

# --------------------------------------------------------------------------- #
# THE CELL TABLE. ⚠️ Every field here is CROSS-CHECKED against screen_lib.py by  #
# cells_from_lib() below before any real game runs, so this shell cannot        #
# silently disagree with the bar library the adjudicator uses.                  #
# --------------------------------------------------------------------------- #
CELL_NAMES=(A_LOW A_MID A_HIGH J_LOW J_HIGH C_LOW C_MID C_HIGH)
declare -A CELL_SEED=( [A_LOW]=153000000000 [A_MID]=153000000400
                       [A_HIGH]=153000000800
                       [J_LOW]=153000001200 [J_HIGH]=153000001600
                       [C_LOW]=153000002000 [C_MID]=153000002400
                       [C_HIGH]=153000002800 )
declare -A CELL_DECKS=( [A_LOW]=400 [A_MID]=400 [A_HIGH]=400
                        [J_LOW]=400 [J_HIGH]=400
                        [C_LOW]=400 [C_MID]=400 [C_HIGH]=400 )
declare -A CELL_GAMES=( [A_LOW]=800 [A_MID]=800 [A_HIGH]=800
                        [J_LOW]=800 [J_HIGH]=800
                        [C_LOW]=800 [C_MID]=800 [C_HIGH]=800 )
declare -A CELL_SUB=(  [A_LOW]=a_low [A_MID]=a_mid [A_HIGH]=a_high
                       [J_LOW]=j_low [J_HIGH]=j_high
                       [C_LOW]=c_low [C_MID]=c_mid [C_HIGH]=c_high )
declare -A CELL_LEAF=( [A_LOW]=leaf_a_low.json [A_MID]=leaf_a_mid.json
                       [A_HIGH]=leaf_a_high.json
                       [J_LOW]=leaf_j_low.json [J_HIGH]=leaf_j_high.json
                       [C_LOW]=leaf_c_low.json [C_MID]=leaf_c_mid.json
                       [C_HIGH]=leaf_c_high.json )
# ⚠️ EVERY round-3 cell carries a nonzero weight, so EVERY one needs the drift
# flag -- and the two J cells carry TWO. That removes the harness's own hash
# assertion on BOTH sides everywhere, which is exactly why G-LEAF is STRICTER
# (per-cell, two-sided, EXACT against a pre-registered pin) rather than looser.
# See DESIGN.md SS2.2.
declare -A CELL_DRIFT=( [A_LOW]=1 [A_MID]=1 [A_HIGH]=1 [J_LOW]=1 [J_HIGH]=1
                        [C_LOW]=1 [C_MID]=1 [C_HIGH]=1 )
declare -A CELL_HASH=( [A_LOW]=$CAND_LEAF_HASH_A_LOW [A_MID]=$CAND_LEAF_HASH_A_MID
                       [A_HIGH]=$CAND_LEAF_HASH_A_HIGH
                       [J_LOW]=$CAND_LEAF_HASH_J_LOW [J_HIGH]=$CAND_LEAF_HASH_J_HIGH
                       [C_LOW]=$CAND_LEAF_HASH_C_LOW [C_MID]=$CAND_LEAF_HASH_C_MID
                       [C_HIGH]=$CAND_LEAF_HASH_C_HIGH )
declare -A CELL_OPPHASH=( [A_LOW]=$OPP_LEAF_HASH_A_LOW [A_MID]=$OPP_LEAF_HASH_A_MID
                          [A_HIGH]=$OPP_LEAF_HASH_A_HIGH
                          [J_LOW]=$OPP_LEAF_HASH_J_LOW [J_HIGH]=$OPP_LEAF_HASH_J_HIGH
                          [C_LOW]=$OPP_LEAF_HASH_C_LOW [C_MID]=$OPP_LEAF_HASH_C_MID
                          [C_HIGH]=$OPP_LEAF_HASH_C_HIGH )
# ⭐ THE ENV REGIME, PER CELL. 1 => this cell's OPPONENT is the shape-B invader.
# ⛔ 0 ON BOTH J CELLS, and that is load-bearing: the J cells are the
# adoption-chain-eligible ones and their opponent MUST be the champion of record.
# A stray 1 here would silently turn the round's headline cells into something
# that licenses nothing.
declare -A CELL_BENV=( [A_LOW]=0 [A_MID]=0 [A_HIGH]=0 [J_LOW]=0 [J_HIGH]=0
                       [C_LOW]=1 [C_MID]=1 [C_HIGH]=1 )
# ⭐ THE FROZEN CELL->BOX ASSIGNMENT (DESIGN.md SS6.5). Cross-checked against
# screen_lib.CellSpec.box by require_table_agrees(), and re-checked after the fact
# by G-HOST against the emitted manifest.
# ⛔ NOT ROUND 2's ASSIGNMENT -- W_LOCAL=14 flips it. See the banner.
declare -A CELL_BOX=( [A_LOW]=laptop [A_MID]=laptop [A_HIGH]=laptop
                      [J_LOW]=laptop [J_HIGH]=laptop
                      [C_LOW]=local [C_MID]=local [C_HIGH]=local )
# ⭐ THE PER-BOX SS9 SMOKE (screen_lib.SMOKE_BY_BOX is the frozen source).
declare -A BOX_SMOKE_CELL=( [local]=C_MID [laptop]=J_HIGH )
declare -A BOX_SMOKE_SEED=( [local]=153999999000 [laptop]=153999999100 )
# ⛔ NO SMOKE_WORKERS. Each box smokes at ITS OWN FROZEN W -- uniformity beats
# speed, W_LOCAL is an owner constraint rather than a free choice, and a 16-game
# leg does not saturate W either way.
SMOKE_WORKERS="$W"

cell_out() { echo "$OUT/${CELL_SUB[$1]}"; }

# The cells this invocation is allowed to run -- exactly the ones frozen to its box.
box_cells() {
  local c
  for c in "${CELL_NAMES[@]}"; do
    [ "${CELL_BOX[$c]}" = "$BOXROLE" ] && echo "$c"
  done
}

# ⛔ REFUSE A CELL THAT IS NOT THIS BOX'S. A cell run on the wrong box breaks the
# property the assignment exists to protect -- that no pre-registered contrast is
# ever computed across the two boxes -- and G-HOST would void it only AFTER the
# compute was spent. This is the cheap, up-front half of the same check.
require_cell_is_mine() {   # $1 = cell
  if [ "${CELL_BOX[$1]:-}" != "$BOXROLE" ]; then
    log "!!! FATAL: cell $1 is FROZEN to box '${CELL_BOX[$1]:-?}', not '$BOXROLE'."
    log "!!! DESIGN.md SS6.5 freezes the cell->box assignment in the prereg, WHOLE"
    log "!!! CELLS PER BOX, precisely so that every SS4.5 contrast and the SS4.7"
    log "!!! noise-signature check stays WITHIN one machine. Running $1 here would"
    log "!!! make its shape's contrast a CROSS-BOX statistic, and this program has"
    log "!!! been bitten by cross-box float drift before (the Xeon's AVX-512 G0"
    log "!!! failure, 2026-08-02)."
    log "!!! This box runs: $(box_cells | tr '\n' ' ')"
    exit 2
  fi
}

# --------------------------------------------------------------------------- #
# ARGV. The experimental axes WITHIN a cell are --cand-leaf-json (the           #
# candidate's invasion knob) and, on the C cells, the two CARCASSONNE_INVASION_* #
# env variables that move the OPPONENT's leaf.                                  #
# ⛔ NO --cand-tiearb-* FLAG ANYWHERE. The harness default is disarmed and the    #
# opponent side has no arming flag at all (verified in source).                  #
#                                                                              #
# ⭐ THE ENV IS EMITTED INTO THE ARGV, NEVER EXPORTED -- and it is emitted on    #
# EVERY cell, pinned to 0.0/0.0 on the A and J cells. Two reasons, both load-bearing:#
#   (1) a process-wide export would give the A and J cells a shape-B opponent too;   #
#   (2) pinning the regime OFF explicitly means a stray CARCASSONNE_INVASION_*   #
#       in the orchestrator's shell cannot reach an A or J cell. float("0.0") IS    #
#       the dataclass default, so a pinned-off cell is byte-identical to an      #
#       unset one -- verified in virtual_score_v2._config_from_env.              #
# --------------------------------------------------------------------------- #
build_argv() {   # $1=cell  $2=n_games  $3=seed_start  $4=workers  $5=out_subdir  $6=with-stamp|no-stamp
  local c="$1" n="$2" seed="$3" w="$4" sub="$5" stamp="${6:-with-stamp}"
  local a="0.0" cap="0.0"
  if [ "${CELL_BENV[$c]}" = "1" ]; then a="$SHAPE_B_ALPHA"; cap="$SHAPE_B_ALPHA_CAP"; fi
  ARGV=(nice -n "$NICE"
        env "CARCASSONNE_INVASION_ALPHA=$a" "CARCASSONNE_INVASION_ALPHA_CAP=$cap"
        "$PY" -u "$HARNESS"
        --info "$INFO_MODE" --opponent "$OPPONENT_MODE" --backend "$BACKEND"
        --exact-k "$EXACT_K"
        --c-puct "$C_PUCT" --tau-p "$TAU_P"
        --leaf-quantize "$LEAF_QUANTIZE" --final-select "$FINAL_SELECT"
        --cand-leaf-json "$DIR/${CELL_LEAF[$c]}"
        --k-dets "$K_DETS"     --sims     "$SIMS_PER_DET"
        --opp-k-dets "$K_DETS" --opp-sims "$SIMS_PER_DET"
        --n "$n" --paired --seed-start "$seed"
        --rules-profile "$RULES_PROFILE" --workers "$w"
        --out-root "$OUT" --out-subdir "$sub"
        --shared-claim --claim-stale-secs "$CLAIM_STALE_SECS"
        --claim-host "invscreenr3-$c-$HOST"
        --no-results-csv)
  if [ "${CELL_DRIFT[$c]}" = "1" ]; then
    ARGV+=(--allow-leaf-hash-drift)
  fi
  if [ "$stamp" = "with-stamp" ]; then
    ARGV+=(--stamp-key "BLIND_COMMIT=$(blind_commit_value)"
           --stamp-key "SCREEN_CELL=$c")
  fi
}

blind_commit_value() { tr -d '[:space:]' < "$DIR/BLIND_COMMIT" 2>/dev/null || echo PENDING; }

# =========================================================================== #
# PRECONDITION LADDER                                                         #
# =========================================================================== #

# --------------------------------------------------------------------------- #
# (1) THE CELL TABLE AGREES WITH THE BAR LIBRARY.                              #
# The shell owns exactly ONE numeric literal that matters -- BAND -- and this  #
# check proves even that one agrees with screen_lib. Everything else is        #
# cross-checked field by field, INCLUDING the opponent hash and the env regime #
# (opponent hash, env regime and box -- exactly the kind of field a shell table   #
# silently). A launcher that disagrees with the pair is a launcher defect.     #
# --------------------------------------------------------------------------- #
require_table_agrees() {
  CARC_LIB="$LIB" CARC_BAND="$BAND" \
  CARC_TABLE="$(for c in "${CELL_NAMES[@]}"; do
                  printf '%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\n' "$c" "${CELL_SEED[$c]}" \
                    "${CELL_DECKS[$c]}" "${CELL_GAMES[$c]}" "${CELL_SUB[$c]}" \
                    "${CELL_DRIFT[$c]}" "${CELL_HASH[$c]}" "${CELL_OPPHASH[$c]}" \
                    "${CELL_BENV[$c]}" "${CELL_BOX[$c]}"
                done)" \
  CARC_ROLE="$BOXROLE" CARC_W="$W" CARC_SHARE="$SHARE" \
  CARC_SMOKE="${BOX_SMOKE_CELL[$BOXROLE]}|${BOX_SMOKE_SEED[$BOXROLE]}" \
  "$PY" - <<'TEOF' || { log "!!! FATAL: the launcher's cell table disagrees with screen_lib.py."; exit 2; }
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("screen_lib", os.environ["CARC_LIB"])
L = importlib.util.module_from_spec(spec)
# ⚠️ MUST be in sys.modules BEFORE exec_module: @dataclass resolves its field
# annotations through sys.modules[cls.__module__], and a module loaded from a
# heredoc-fed stdin is not registered by module_from_spec alone -> TypeError
# deep inside dataclasses._is_type. Registering it first is the fix.
sys.modules["screen_lib"] = L
spec.loader.exec_module(L)
ok = True
if int(os.environ["CARC_BAND"]) != int(L.BAND):
    print(f"[table] !!! BAND {os.environ['CARC_BAND']} != screen_lib.BAND {L.BAND}"); ok = False
rows = [r.split("|") for r in os.environ["CARC_TABLE"].strip().splitlines()]
by = {c.name: c for c in L.CELLS}
if [r[0] for r in rows] != [c.name for c in L.CELLS]:
    print(f"[table] !!! cell ORDER differs: shell {[r[0] for r in rows]} vs lib {[c.name for c in L.CELLS]}")
    ok = False
for r in rows:
    name = r[0]
    if name not in by:
        print(f"[table] !!! unknown cell {name!r}"); ok = False; continue
    c = by[name]
    for label, got, want in (("seed_start", int(r[1]), int(c.seed_start)),
                             ("n_decks",    int(r[2]), int(c.n_decks)),
                             ("n_games",    int(r[3]), int(c.n_games)),
                             ("out_subdir", r[4],      c.out_subdir),
                             ("drift",      int(r[5]), int(bool(c.allow_leaf_hash_drift))),
                             ("cand_hash",  r[6],      c.cand_leaf_hash),
                             ("opp_hash",   r[7],      c.opp_leaf_hash),
                             ("shape_b_env", int(r[8]), int(bool(c.shape_b_env))),
                             ("box",        r[9],      c.box)):
        if got != want:
            print(f"[table] !!! {name}.{label}: launcher {got!r} != screen_lib {want!r}"); ok = False
    print(f"[table] {name}: seeds {c.seed_start}..{c.seed_start + c.n_decks - 1} "
          f"({c.n_decks} decks / {c.n_games} games) drift={int(bool(c.allow_leaf_hash_drift))} "
          f"cand={c.cand_leaf_hash} opp={c.opp_leaf_hash} ({c.opponent}) "
          f"benv={int(bool(c.shape_b_env))} box={c.box}")

# ⭐ THE TWO-BOX CONSISTENCY CHECKS (DESIGN.md SS6.5).
role = os.environ["CARC_ROLE"]
if role not in L.BOXES:
    print(f"[table] !!! --host {role!r} is not a known box role"); ok = False
else:
    if int(os.environ["CARC_W"]) != int(L.BOXES[role]["W"]):
        print(f"[table] !!! W {os.environ['CARC_W']} != screen_lib.BOXES[{role}].W "
              f"{L.BOXES[role]['W']}"); ok = False
    if os.environ["CARC_SHARE"] != L.BOXES[role]["share_mount"]:
        print(f"[table] !!! share mount {os.environ['CARC_SHARE']!r} != screen_lib's "
              f"{L.BOXES[role]['share_mount']!r} for box {role} -- the archive would "
              f"land outside the share and the adjudicator would never see it"); ok = False
    sm_cell, sm_seed = os.environ["CARC_SMOKE"].split("|")
    want_sm = L.SMOKE_BY_BOX[role]
    if sm_cell != want_sm["cell"] or int(sm_seed) != int(want_sm["seed_start"]):
        print(f"[table] !!! this box's smoke ({sm_cell}@{sm_seed}) != screen_lib's "
              f"({want_sm['cell']}@{want_sm['seed_start']})"); ok = False
    mine = [c.name for c in L.cells_of_box(role)]
    print(f"[table] box {role}: W={L.BOXES[role]['W']} share={L.BOXES[role]['share_mount']} "
          f"cells={mine} smoke={want_sm['cell']}@{want_sm['seed_start']}")
# every SHAPE must sit wholly on one box, else SS4.5's contrast goes cross-box
for sh in L.SHAPES:
    boxes = sorted({c.box for c in L.cells_of_shape(sh)})
    if len(boxes) != 1:
        print(f"[table] !!! shape {sh} is SPLIT across boxes {boxes}"); ok = False
print(f"[table] every shape sits wholly on one box: "
      f"{ {sh: L.cells_of_shape(sh)[0].box for sh in L.SHAPES} }")
# Ranges must be DISJOINT (DESIGN.md SS5.1) -- the property G-DECKS gates on.
spans = sorted((c.seed_start, c.seed_start + c.n_decks - 1, c.name) for c in L.CELLS)
for (s0, e0, n0), (s1, e1, n1) in zip(spans, spans[1:]):
    if s1 <= e0:
        print(f"[table] !!! ranges OVERLAP: {n0} {s0}..{e0} vs {n1} {s1}..{e1}"); ok = False
print(f"[table] cell ranges disjoint: {spans[0][0]}..{spans[-1][1]}")
probs = L.sanity_check()
for p in probs:
    print(f"[table] !!! screen_lib.sanity_check: {p}"); ok = False
print(f"[table] screen_lib.sanity_check(): {len(probs)} problem(s)")
sys.exit(0 if ok else 1)
TEOF
  log "[preflight] cell table agrees with screen_lib.py"
}

# --------------------------------------------------------------------------- #
# (2) ⛔ THE WHEEL. THE PRECONDITION UNIQUE TO THIS FAMILY (DESIGN.md SS7).     #
#                                                                              #
# rust_agent.leaf_config_rs forwards the invasion knobs as CONDITIONAL kwargs,  #
# so a carc_rs build predating the family serves every default-off (champion)   #
# config UNCHANGED AND SILENTLY. So we do not probe with hasattr; we perform    #
# the ACTUAL NONZERO FORWARD, in a CHILD process, on the real cell configs.     #
#                                                                              #
# ⭐ THE PROBE RUNS **TWICE**, ONCE PER ENV REGIME, AND THAT IS                  #
# STRUCTURAL, NOT BELT-AND-BRACES. `DEFAULT_CONFIG` is resolved from the        #
# environment at `virtual_score_v2` IMPORT time and never re-read, so a single  #
# process cannot observe both the plain champion opponent and the shape-B one.  #
# Each regime writes its half; the launcher merges them into WHEEL_PROBE.json.  #
#                                                                              #
# ⭐ AND IT PROBES THE **OPPONENT** SIDE, which round 1 never did: on a C cell   #
# the OPPONENT carries a nonzero weight through the same conditional kwargs.    #
#                                                                              #
# ⭐⭐ AND ROUND 3 ADDS THE **TWO-KNOB** CONJUNCT, WHICH NOTHING HAS EVER         #
# EXERCISED. `rust_agent.leaf_config_rs` forwards each invasion knob as its own #
# CONDITIONAL kwarg, so a wheel that forwarded beta and dropped gamma would     #
# produce a manifest that LOOKS like a joint cell and a GAME that is a          #
# single-term cell -- an error no downstream gate could unpick from the numbers, #
# on the only cells in this round that can license a production H2H. The probe  #
# therefore counts the NONZERO invasion knobs that survive the forward on every #
# J cell and requires exactly TWO (`joint_two_knob_forward_ok`).                 #
#                                                                              #
# ⭐ AND IT ASSERTS G-WHEEL-SAME AT PRE-FLIGHT: round 3 carries no IDENT cell,   #
# so a rebuilt wheel must be caught BEFORE 6400 games, not at adjudication.     #
# --------------------------------------------------------------------------- #
preflight_wheel_regime() {   # $1 = plain|bshape
  CARC_REPO="$REPO" CARC_DIR="$DIR" CARC_LIB="$LIB" CARC_REGIME="$1" \
  CARC_ALPHA="$SHAPE_B_ALPHA" CARC_CAP="$SHAPE_B_ALPHA_CAP" \
  "$PY" - <<'WEOF' || { log "!!! FATAL: carc_rs WHEEL PRE-FLIGHT FAILED (regime $1) -- see above. No game runs."; exit 4; }
import importlib.util, json, os, sys, time
repo = os.environ["CARC_REPO"]; d = os.environ["CARC_DIR"]
regime = os.environ["CARC_REGIME"]

REBUILD = ("    maturin build --release -m rust/carc/carc-py/Cargo.toml -o <wheeldir>\n"
           "    .venv/bin/pip install --force-reinstall --no-deps <wheeldir>/carc_rs-*.whl")

# ⛔ THE ENV GOES IN BEFORE THE IMPORT. DEFAULT_CONFIG is resolved at
# virtual_score_v2 import time and never re-read; this is the whole mechanism by
# which a C cell's OPPONENT becomes the shape-B agent, so the probe has to set it
# the same way a real cell's argv does.
if regime == "bshape":
    os.environ["CARCASSONNE_INVASION_ALPHA"] = os.environ["CARC_ALPHA"]
    os.environ["CARCASSONNE_INVASION_ALPHA_CAP"] = os.environ["CARC_CAP"]
else:
    os.environ["CARCASSONNE_INVASION_ALPHA"] = "0.0"
    os.environ["CARCASSONNE_INVASION_ALPHA_CAP"] = "0.0"

sys.path.insert(0, os.path.join(repo, "src"))
sys.path.insert(0, os.path.join(repo, "scripts", "classical_search"))

import carcassonne_ai
print(f"[wheel:{regime}] carcassonne_ai.__file__ = {carcassonne_ai.__file__}")
if not carcassonne_ai.__file__.startswith(repo):
    print(f"[wheel:{regime}] !!! carcassonne_ai loaded OUTSIDE {repo} -- the venv's "
          f"editable install points at the wrong tree. VOID."); sys.exit(1)

try:
    import carc_rs
except Exception as e:
    print(f"[wheel:{regime}] !!! carc_rs will not import: {type(e).__name__}: {e}"); sys.exit(1)
print(f"[wheel:{regime}] carc_rs.__file__ = {carc_rs.__file__}")

# ⚠️ carc_rs.__version__ is the CARGO version and is permanently "0.1.0" -- it
# CANNOT tell a fresh wheel from a stale one, and NEITHER CAN carc_rs_build,
# whose embedded rev is the REPO REV AT CALL TIME. The wheel discriminator is
# carc_rs_binary_sha and nothing else (screen_lib.R1_WHEEL_BINARY_SHA's banner).
from carcassonne_ai.rust_agent import (backend_provenance, leaf_config_rs)
prov = backend_provenance()
print(f"[wheel:{regime}] carc_rs_version = {prov.get('carc_rs_version')!r}  (NOT a discriminator)")
print(f"[wheel:{regime}] carc_rs_build   = {prov.get('carc_rs_build')!r}  (code-rev fact, NOT a wheel id)")
print(f"[wheel:{regime}] binary_sha      = {prov.get('carc_rs_binary_sha')!r}  <- THE fingerprint")

if not hasattr(carc_rs.MirrorState, "invasion_terms"):
    print(f"[wheel:{regime}] !!! STALE WHEEL: carc_rs.MirrorState has no `invasion_terms` "
          "-- this build predates the invasion-risk family entirely.\n"
          "[wheel] !!! REBUILD:\n" + REBUILD)
    sys.exit(1)

import eval_fair_puct as H
spec = importlib.util.spec_from_file_location("screen_lib", os.environ["CARC_LIB"])
L = importlib.util.module_from_spec(spec)
sys.modules["screen_lib"] = L
spec.loader.exec_module(L)

# ⭐ G-WHEEL-SAME, ASSERTED AT PRE-FLIGHT. Round 2 carries NO IDENT cell.
same_ok, same_why = L.wheel_is_r1s(prov.get("carc_rs_binary_sha"),
                                   prov.get("carc_rs_build"))
print(f"[wheel:{regime}] G-WHEEL-SAME {'PASS' if same_ok else 'FAIL'}: {same_why}")

# ⭐ THE OPPONENT SIDE. `_curve125_leaf_cfg()` is EXACTLY what the harness hands
# the head-to-head opponent (eval_fair_puct.py:3774), so probing it here probes
# the real thing rather than a reconstruction.
opp_cfg = H._curve125_leaf_cfg()
opp_hash = H._leaf_hash(opp_cfg)
opp_inv = {k: v for k, v in H._leaf_dict(opp_cfg).items() if k.startswith("invasion")}
print(f"[wheel:{regime}] OPPONENT leaf hash = {opp_hash}  invasion={opp_inv}")
try:
    leaf_config_rs(opp_cfg)
    opp_fwd_ok, opp_err = True, None
except Exception as e:
    opp_fwd_ok, opp_err = False, f"{type(e).__name__}: {e}"
if not opp_fwd_ok:
    print(f"[wheel:{regime}] !!! the OPPONENT leaf did NOT reach rust: {opp_err}")
    print("[wheel] !!! REBUILD:\n" + REBUILD)

ok = same_ok and opp_fwd_ok
cells = {}
for c in L.CELLS:
    if bool(c.shape_b_env) != (regime == "bshape"):
        continue
    cfg = H._load_cand_leaf_cfg(os.path.join(d, c.leaf_json))
    got_hash = H._leaf_hash(cfg)
    curve_ok = tuple(cfg.v29_meeple_curve or ()) == tuple(L.CURVE125)
    cand_inv = {k: v for k, v in H._leaf_dict(cfg).items() if k.startswith("invasion")}
    # the cap-forwarding BICONDITIONAL (DESIGN.md SS2.3 / G-CAPFWD), BOTH SIDES
    def _cap_ok(inv):
        a = float(inv.get("invasion_alpha", 0.0) or 0.0)
        cp = float(inv.get("invasion_alpha_cap", 0.0) or 0.0)
        st = int(inv.get("invasion_stub_max_tiles", 2) or 2)
        return ((cp == 0.0) or (a != 0.0)) and ((st == 2) or (a != 0.0))
    cap_ok = _cap_ok(cand_inv) and _cap_ok(opp_inv)
    try:
        leaf_config_rs(cfg)
        fwd_ok, err = True, None
    except Exception as e:                       # TypeError == stale wheel
        fwd_ok, err = False, f"{type(e).__name__}: {e}"
    # ⭐ THE TWO-SIDED GATE, through screen_lib's ONE implementation -- the same
    # function analyze_screen.py's G-LEAF calls, so the live check and the
    # post-hoc check cannot drift.
    lg = L.leaf_gate(c, got_hash, opp_hash, cfg.v29_meeple_curve)
    # ⭐ THE JOINT CONJUNCT. A J cell's candidate leaf must reach rust carrying
    # BOTH nonzero knobs -- `leaf_config_rs` forwards the invasion knobs as
    # CONDITIONAL kwargs, so a wheel that forwarded one and dropped the other
    # would produce a manifest that LOOKS like a joint cell and a GAME that is a
    # single-term cell. Nothing in rounds 1 or 2 ever exercised two-at-once.
    n_nonzero = sum(1 for k, v in cand_inv.items()
                    if k in ("invasion_beta", "invasion_gamma", "invasion_alpha",
                             "invasion_delta_farm") and float(v or 0.0) != 0.0)
    joint_ok = (not c.is_joint) or (fwd_ok and n_nonzero == 2)
    cells[c.name] = {"leaf_json": c.leaf_json, "regime": regime,
                     "cand_leaf_hash": got_hash,
                     "cand_leaf_hash_expected": c.cand_leaf_hash,
                     "opp_leaf_hash": opp_hash,
                     "opp_leaf_hash_expected": c.opp_leaf_hash,
                     "cand_invasion": cand_inv, "opp_invasion": opp_inv,
                     "leaf_gate_ok": lg["ok"], "leaf_gate_conjuncts": lg["conjuncts"],
                     "curve_ok": curve_ok, "cap_biconditional_ok": bool(cap_ok),
                     "is_joint": bool(c.is_joint),
                     "n_nonzero_invasion_knobs": n_nonzero,
                     "joint_two_knob_forward_ok": bool(joint_ok),
                     "nonzero_forward_ok": fwd_ok, "forward_error": err}
    print(f"[wheel:{regime}] {c.name:6s} cand={got_hash}(want {c.cand_leaf_hash}) "
          f"opp={opp_hash}(want {c.opp_leaf_hash}) curve125={curve_ok} "
          f"cap_ok={cap_ok} fwd={'OK' if fwd_ok else 'FAIL'} "
          f"knobs={n_nonzero}{' JOINT' if c.is_joint else ''} "
          f"G-LEAF={'PASS' if lg['ok'] else 'FAIL'}")
    if not joint_ok:
        print(f"[wheel:{regime}] !!! {c.name}: a JOINT cell must forward TWO nonzero "
              f"invasion knobs; this leaf carries {n_nonzero}. `leaf_config_rs` "
              "forwards the invasion knobs as CONDITIONAL kwargs, so a dropped "
              "second knob yields a manifest that LOOKS joint and a GAME that is "
              "not -- and the J cells are the round's only adoption-chain-eligible "
              "cells."); ok = False
    if not fwd_ok:
        print(f"[wheel:{regime}] !!! {c.name}: the CANDIDATE leaf did NOT reach rust: {err}")
        print("[wheel] !!! This is the STALE-WHEEL signature. A stale carc_rs serves every "
              "default-off config unchanged and raises only on a NONZERO weight -- which is "
              "why this probe forwards the real cell configs instead of checking hasattr.")
        print("[wheel] !!! REBUILD (orchestrator, from the merged tree):\n" + REBUILD)
        ok = False
    if not lg["ok"]:
        print(f"[wheel:{regime}] !!! {c.name}: G-LEAF WOULD VOID -- {lg['why']}")
        print(f"[wheel:{regime}] !!! conjuncts: {lg['conjuncts']}")
        ok = False
    if not curve_ok:
        print(f"[wheel:{regime}] !!! {c.name}: candidate curve is NOT curve125. "
              "_assert_netprior_leaf HARD-fails on this even with --allow-leaf-hash-drift."); ok = False
    if not cap_ok:
        print(f"[wheel:{regime}] !!! {c.name}: G-CAPFWD WOULD VOID -- an inert shape-B knob "
              "is set without a nonzero invasion_alpha on one of the sides; leaf_config_rs "
              "would DROP it silently (rust_agent.py:181-185) and the manifest would lie "
              "about the running leaf."); ok = False

# Merge this regime's half into the shared probe artifact. ⚠️ The TOP-LEVEL key
# names are screen_lib.WHEEL_PROBE_REQUIRED_TRUE's, NOT this script's invention:
# screen_lib.wheel_probe_ok() is the ONE definition of what this file must
# contain, so the writer (here) and the reader (G-WHEEL) cannot drift.
path = os.path.join(d, L.WHEEL_PROBE_FILENAME)
try:
    probe = json.load(open(path))
    if not isinstance(probe, dict):
        probe = {}
except Exception:
    probe = {}
probe.setdefault("cells", {})
probe["cells"].update(cells)
probe["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
probe["carc_rs_build"] = prov.get("carc_rs_build")
probe["carc_rs_version"] = prov.get("carc_rs_version")
probe["carc_rs_binary_sha"] = prov.get("carc_rs_binary_sha")
probe["rust_toolchain"] = prov.get("rust_toolchain")
probe["carc_rs_path"] = prov.get("carc_rs_path")
probe["invasion_terms_attr"] = True          # asserted above
probe.setdefault("regimes", {})[regime] = {"opp_leaf_hash": opp_hash,
                                           "opp_invasion": opp_inv,
                                           "opp_side_forward_ok": opp_fwd_ok}
# AND the per-cell results down into the contract keys G-WHEEL reads.
allc = probe["cells"].values()
probe["nonzero_kwarg_forward_ok"] = bool(allc) and all(v.get("nonzero_forward_ok") for v in allc)
probe["cap_biconditional_ok"] = bool(allc) and all(v.get("cap_biconditional_ok") for v in allc)
probe["opp_side_forward_ok"] = all(r.get("opp_side_forward_ok") is True
                                   for r in probe["regimes"].values())
# ⭐ ROUND 3's NEW CONTRACT KEY. It is TRUE only once at least one JOINT cell has
# been probed AND every probed cell satisfies the conjunct -- so a probe that
# somehow never saw a J cell reads FALSE rather than vacuously true.
_j = [v for v in allc if v.get("is_joint")]
probe["joint_two_knob_forward_ok"] = (
    bool(_j) and all(v.get("joint_two_knob_forward_ok") is True for v in allc))
probe["wheel_is_round_1s"] = bool(same_ok)
probe["ok"] = bool(probe.get("ok", True)) and ok
json.dump(probe, open(path, "w"), indent=2, sort_keys=True)
print(f"[wheel:{regime}] wrote {path}")
sys.exit(0 if ok else 1)
WEOF
  log "[G-WHEEL] carc_rs wheel pre-flight PASS for regime '$1'"
}

preflight_wheel() {
  # A stale artifact from a previous run would let a half-probed round through.
  rm -f "$DIR/WHEEL_PROBE.json" 2>/dev/null || true
  preflight_wheel_regime plain
  preflight_wheel_regime bshape
  # Final contract check, through the ONE reader.
  CARC_LIB="$LIB" CARC_DIR="$DIR" "$PY" - <<'PEOF' || { log "!!! FATAL: the merged WHEEL_PROBE.json does not satisfy screen_lib.wheel_probe_ok()."; exit 4; }
import importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location("screen_lib", os.environ["CARC_LIB"])
L = importlib.util.module_from_spec(spec); sys.modules["screen_lib"] = L
spec.loader.exec_module(L)
p = json.load(open(os.path.join(os.environ["CARC_DIR"], L.WHEEL_PROBE_FILENAME)))
missing = [c.name for c in L.CELLS if c.name not in p.get("cells", {})]
if missing:
    print(f"[wheel] !!! the merged probe is missing cells: {missing} -- one regime did not run")
    sys.exit(1)
ok, why = L.wheel_probe_ok(p)
print(f"[wheel] merged probe contract: {'PASS' if ok else 'FAIL'} -- {why}")
sys.exit(0 if ok else 1)
PEOF
  log "[G-WHEEL] merged wheel probe satisfies the contract -- both regimes, both sides"
}

# --------------------------------------------------------------------------- #
# (3) R9 + rules profile, in a CHILD process (the same import path the cells    #
# use). R9 is import-latched; a parent-only check proves nothing about children.#
# --------------------------------------------------------------------------- #
preflight_rules() {
  CARC_REPO="$REPO" CARC_PROFILE="$RULES_PROFILE" \
  "$PY" - <<'REOF' || { log "!!! FATAL: rules/R9 pre-flight FAILED. No game runs."; exit 4; }
import os, sys
repo = os.environ["CARC_REPO"]
sys.path.insert(0, os.path.join(repo, "src"))
from carcassonne_ai import rules_profile as rp
assert rp.r9_env_on(), "CARCASSONNE_FIX_R9 not latched in a CHILD process"
prof = rp.resolve(os.environ["CARC_PROFILE"])
m = prof.as_manifest()
assert m["r9_env_ok"] is True, m
print(f"[rules] {os.environ['CARC_PROFILE']} resolved, r9_env_ok=True")
REOF
  log "[G-RULES] rules/R9 pre-flight PASS"
}

# --------------------------------------------------------------------------- #
# (4) REV PINNING + dirty-CODE refusal. Dirt here makes `code_rev` a lie about  #
# what played the games (the track_d2_prep mixed-rev defect).                   #
# ⚠️ measurement/ is DELIBERATELY EXCLUDED from CODE_PATHS -- RUN_LIVE.json,     #
# PINNED_SRC_REV and WHEEL_PROBE.json all live there and necessarily dirty it.  #
# --------------------------------------------------------------------------- #
code_dirty_list() { git -C "$REPO" status --porcelain -- "${CODE_PATHS[@]}" 2>/dev/null || echo "FAIL"; }

require_clean_code() {
  local dirt n
  dirt="$(code_dirty_list)"
  n="$(printf '%s' "$dirt" | grep -c . || true)"
  if [ "$n" -eq 0 ]; then log "[preflight] code paths clean (${CODE_PATHS[*]})"; return 0; fi
  log "!!! CODE PATHS ARE DIRTY ($n entr(ies)) -- code_rev would be a lie about what ran:"
  printf '%s\n' "$dirt" | sed 's/^/[invscreen-r3]   /'
  if [ "${LAUNCH_DIRTY:-0}" = "1" ]; then
    if [ -z "${LAUNCH_DIRTY_REASON:-}" ]; then
      log "!!! FATAL: LAUNCH_DIRTY=1 requires LAUNCH_DIRTY_REASON=<why>. No reason, no override."
      exit 6
    fi
    log "!!! OVERRIDE ACCEPTED: LAUNCH_DIRTY=1"
    log "!!! REASON: $LAUNCH_DIRTY_REASON"
    log "!!! Recorded in this log and in SRC_CLEAN.jsonl. Manifests will read <sha>-dirty."
    return 0
  fi
  log "!!! FATAL: refusing to start a real cell on dirty CODE."
  log "!!! Commit or stash the code paths, or re-run with"
  log "!!!   LAUNCH_DIRTY=1 LAUNCH_DIRTY_REASON='<why>' $SELF"
  exit 6
}

record_src_boundary() {   # $1 = label
  local rev; rev="$(git -C "$REPO" rev-parse HEAD)"
  CARC_P="$DIR/$SRC_CLEAN_LOG" CARC_L="$1" CARC_R="$rev" \
  CARC_C="$([ -z "$(code_dirty_list)" ] && echo 1 || echo 0)" \
  "$PY" - <<'SEOF' || true
import json, os, time
with open(os.environ["CARC_P"], "a") as f:
    f.write(json.dumps({"boundary": os.environ["CARC_L"], "head": os.environ["CARC_R"],
                        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "src_clean": os.environ["CARC_C"] == "1"}) + "\n")
SEOF
}

assert_rev_pinned() {   # $1 = boundary label
  local pinned rev
  pinned="$(tr -d '[:space:]' < "$DIR/$PINNED_SRC_REV_FILE")"
  rev="$(git -C "$REPO" rev-parse HEAD)"
  if [ "$pinned" != "$rev" ]; then
    log "!!! FATAL at boundary '$1': HEAD=$rev != PINNED_SRC_REV=$pinned"
    log "!!! The tree MOVED mid-run. This is the track_d2_prep mixed-rev defect, and this"
    log "!!! pair is EIGHT cells long -- a mid-round move would split the round across revs."
    log "!!! ABORTING rather than producing a mixed-rev archive."
    exit 3
  fi
  require_clean_code
  record_src_boundary "$1"
}

# --------------------------------------------------------------------------- #
# (5) BLIND_COMMIT + BAND_CLAIMED -- both real files. The launcher NEVER claims  #
# a band itself.                                                                #
# --------------------------------------------------------------------------- #
write_blind_proof() {
  local bc head anc="no"
  bc="$(blind_commit_value)"
  head="$(git -C "$REPO" rev-parse HEAD)"
  if git -C "$REPO" merge-base --is-ancestor "$bc" HEAD 2>/dev/null; then anc="yes"; fi
  CARC_P="$DIR/BLIND_PROOF.json" CARC_BC="$bc" CARC_HEAD="$head" CARC_ANC="$anc" \
  "$PY" - <<'BEOF' || true
import json, os, time
json.dump({"blind_commit": os.environ["CARC_BC"], "head_at_launch": os.environ["CARC_HEAD"],
           "is_ancestor_of_head": os.environ["CARC_ANC"] == "yes",
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("READ_RULE.md SS3 G-BLIND is gated against THIS artifact plus a live "
                   "git-ancestry re-check. The blind commit is the commit that introduced "
                   "the FROZEN banner on DESIGN.md/READ_RULE.md; its sha is stamped by a "
                   "follow-up commit because a commit cannot name its own hash.")},
          open(os.environ["CARC_P"], "w"), indent=2, sort_keys=True)
BEOF
  if [ "$anc" != "yes" ]; then
    log "!!! FATAL: BLIND_COMMIT $bc is NOT an ancestor of HEAD -- G-BLIND cannot pass."
    exit 2
  fi
}

require_blind_and_band() {
  local bc="$DIR/BLIND_COMMIT" bcl="$DIR/$BAND_SENTINEL" psr="$DIR/$PINNED_SRC_REV_FILE"
  if [ ! -f "$bc" ] || ! grep -qE '^[0-9a-f]{40}$' "$bc"; then
    log "!!! FATAL: $bc is missing or does not hold a 40-hex sha."
    log "!!! It currently reads: '$(blind_commit_value)'"
    log "!!! A FOLLOW-UP commit stamps the freeze commit's own sha before any launch."
    log "!!! (--dry-run and --smoke are exempt -- neither spends blindness.)"
    exit 2
  fi
  if [ "$BLIND_COMMIT" = "PENDING" ] || ! [[ "$BLIND_COMMIT" =~ ^[0-9a-f]{8,40}$ ]]; then
    log "!!! FATAL: WORKERS.conf::BLIND_COMMIT is still the PENDING placeholder."
    exit 2
  fi
  if [[ "$(blind_commit_value)" != "$BLIND_COMMIT"* ]]; then
    log "!!! FATAL: BLIND_COMMIT file and WORKERS.conf::BLIND_COMMIT disagree."
    exit 2
  fi
  if [ ! -f "$psr" ] || ! grep -qE '^[0-9a-f]{40}$' "$psr"; then
    log "!!! FATAL: $psr missing or not a 40-hex sha (the mixed-rev fix)."
    exit 2
  fi
  if [ ! -f "$bcl" ]; then
    log "!!! FATAL: $bcl is missing."
    log "!!! The ORCHESTRATOR drops it AFTER appending BAND_CLAIM.json's row to"
    log "!!! governance/BAND_REGISTRY.csv AND after DESIGN.md SS0's FUNDING line is"
    log "!!! signed off by the owner. This script NEVER claims a band and never funds itself."
    exit 2
  fi
}

# --------------------------------------------------------------------------- #
# (6) TENANCY: ADVISORY census + a HARD RAM floor.                             #
#                                                                              #
# ⭐ THE CENSUS IS DELIBERATELY NON-FATAL. See the banner and DESIGN.md SS6.3:  #
# this pair is SIMS-denominated, its gates read no clock, and game outcomes are #
# bit-identical under co-tenancy and at any W. `feedback_no_agent_compute_      #
# beside_eval` is honoured, not evaded: that rule's own text scopes exclusivity #
# to a TIMING bench. This isn't one.                                           #
# --------------------------------------------------------------------------- #
mem_avail_mb() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }

require_ram() {   # $1 = floor MB, $2 = context label
  local avail; avail="$(mem_avail_mb)"
  log "[ram] $2: MemAvailable=${avail} MB (floor ${1} MB)"
  if [ "$avail" -lt "$1" ]; then
    log "!!! FATAL: $2 MemAvailable ${avail} MB < floor ${1} MB. FAIL-CLOSED."
    log "!!! RAM is this pair's ONLY hard resource check (DESIGN.md SS6.3): a WSL guest OOM"
    log "!!! tears down the WHOLE VM, not one worker, and the reconcile solver this cell may"
    log "!!! legitimately share the box with carries a 30 GB job cap."
    return 1
  fi
  return 0
}

# --------------------------------------------------------------------------- #
# ⚠️ THE SHARE MUST BE MOUNTED, AND THE CLOCK MUST BE SANE (the F7c class).     #
#                                                                              #
# Both are two-box concerns. The out-root lives on the SHARE so the LOCAL box   #
# can adjudicate over BOTH boxes' archives; a box whose share is not mounted    #
# would write to a local directory nobody ever reads.                           #
#                                                                              #
# ⚠️ WSL CLOCK DRIFT (`reference_wsl_clock_drift_after_sleep`): a WSL2 clock    #
# can jump HOURS after a host sleep, and a fast-clocked box silently STEALS     #
# stale `--shared-claim` claims -- no error, just missing games. ⭐ IT CANNOT   #
# HAPPEN ACROSS THE TWO BOXES HERE, and that is structural rather than lucky:   #
# the boxes are given DISJOINT CELLS and therefore DISJOINT `--out-subdir`s, so #
# there are no shared claims to steal. It CAN still bite WITHIN a box's own     #
# pass-resume loop, which is what `--claim-stale-secs` and the orphan sweep are #
# for. The check below is a cheap sanity read against the share host's own      #
# epoch, logged rather than enforced.                                          #
# --------------------------------------------------------------------------- #
require_share_mounted() {
  if [ ! -d "$SHARE" ]; then
    log "!!! FATAL: the share is not mounted at '$SHARE' on box '$BOXROLE'."
    log "!!! The out-root MUST be on the share: the LOCAL box adjudicates over BOTH"
    log "!!! boxes' archives and can only see this box's cells if they land there."
    log "!!! ⚠️ The mount spelling differs by box: local $SHARE_LOCAL, laptop $SHARE_LAPTOP."
    exit 2
  fi
  log "[share] $SHARE mounted; out-root $OUT"
}

clock_sanity_advisory() {
  local probe="$SHARE/.clock_probe_$$" skew
  if touch "$probe" 2>/dev/null; then
    skew=$(( $(date +%s) - $(stat -c %Y "$probe" 2>/dev/null || date +%s) ))
    rm -f "$probe" 2>/dev/null || true
    log "[clock] ADVISORY: local-vs-share mtime skew ~${skew}s"
    if [ "${skew#-}" -gt 300 ]; then
      log "[clock] ⚠️ ADVISORY: skew > 300s. WSL2 clocks jump hours after a host sleep"
      log "[clock] ⚠️ (reference_wsl_clock_drift_after_sleep). It cannot cross-contaminate"
      log "[clock] ⚠️ the two boxes here -- they hold DISJOINT cells and therefore share no"
      log "[clock] ⚠️ claims -- but it CAN disturb this box's own resume loop. Consider"
      log "[clock] ⚠️ 'sudo date -s @<share-host epoch>' before a long run."
    fi
  fi
}

census_advisory() {
  local tenants
  tenants="$(pgrep -af 'eval_fair_puct|eval_puct_priors|gen_fair_distill|carcasum_driver|reconcile_exact_solver|match\.py' \
             | grep -v run_cells || true)"
  if [ -n "$tenants" ]; then
    log "[census] ADVISORY (NON-FATAL -- this pair is result-safe beside other compute):"
    echo "$tenants" | sed 's/^/[invscreen-r3]   /'
    log "[census] ADVISORY: expect longer wall-clock. No statistic, gate or claim moves"
    log "[census] ADVISORY: with co-tenancy or with W (DESIGN.md SS6.3)."
  else
    log "[census] ADVISORY: box is exclusive right now (not required)."
  fi
  local np; np="$(nproc)"
  if [ "$np" -lt "$W" ]; then
    log "!!! FATAL: nproc=$np < W=$W. An under-provisioned box thrashes silently."
    exit 2
  fi
  log "[preflight] nproc=$np >= W=$W"
}

require_no_foreign_run_live() {
  local foreign
  foreign="$(find "$REPO/measurement" -name RUN_LIVE.json 2>/dev/null \
             | grep -v "^$DIR/RUN_LIVE.json$" || true)"
  if [ -n "$foreign" ]; then
    log "!!! FATAL: a FOREIGN run is live -- RUN_LIVE.json present at:"
    echo "$foreign" | sed 's/^/[invscreen-r3]   /'
    log "!!! This is NOT a CPU-exclusivity check (this pair does not need one). It is"
    log "!!! FREEZE-LATCH discipline: a foreign live run means the main tree may move"
    log "!!! under us, and a mid-round rev move splits the round across revs (G-REV)."
    log "!!! Wait for the sentinel to clear; do NOT delete it without confirming the"
    log "!!! other run is actually dead."
    return 1
  fi
  return 0
}

require_preconditions() {
  require_share_mounted                  # (0) two-box: the out-root is on the share
  require_blind_and_band                 # (5)
  write_blind_proof                      # (5) ancestry
  require_table_agrees                   # (1)  <- incl. the box/W/share/smoke checks
  preflight_rules                        # (3)
  preflight_wheel                        # (2)  <- both regimes, both sides, G-WHEEL-SAME
  assert_rev_pinned "pre-flight"         # (4)
  census_advisory                        # (6) advisory + nproc
  clock_sanity_advisory                  # (6) advisory, the F7c class
  require_ram "$PREFLIGHT_RAM_FLOOR_MB" "pre-flight" || exit 8
  require_no_foreign_run_live || exit 7
  log "[preflight] ALL PRECONDITIONS PASS on box '$BOXROLE' -- clear to launch"
  log "[preflight] this box runs: $(box_cells | tr '\n' ' ')"
}

# --------------------------------------------------------------------------- #
# RUN_LIVE.json freeze-latch sentinel. MUST live under measurement/ for the     #
# repo's PreToolUse hook to see it, so this one file necessarily dirties the    #
# working tree -- which is why the dirty refusal above is scoped to CODE paths. #
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# ⭐ PUBLISH THIS BOX'S LAUNCH ARTIFACTS TO THE SHARE (DESIGN.md SS6.5).        #
#                                                                              #
# G-REV, G-BLIND and G-WHEEL are evaluated PER CELL against THAT CELL'S BOX's   #
# artifacts -- but each box writes PINNED_SRC_REV / SRC_CLEAN.jsonl /           #
# BLIND_PROOF.json / WHEEL_PROBE.json into ITS OWN repo checkout, which the     #
# LOCAL adjudicator cannot see. So each box copies them to                      #
# <out-root>/_provenance/<role>/ on the SHARE, and the adjudicator reads each   #
# cell's gates from its own box's copy (falling back to its own directory, so a #
# single-box run and the SS9 smoke keep working unchanged).                     #
#                                                                              #
# Called after the pre-flight ladder and again after EVERY cell, so a round     #
# that dies mid-way still leaves a readable provenance trail for what DID run.  #
# --------------------------------------------------------------------------- #
publish_provenance() {
  local pdir="$OUT/_provenance/$BOXROLE" f
  mkdir -p "$pdir" 2>/dev/null || true
  for f in "$PINNED_SRC_REV_FILE" "$SRC_CLEAN_LOG" BLIND_PROOF.json \
           WHEEL_PROBE.json BLIND_COMMIT; do
    [ -f "$DIR/$f" ] && cp -f "$DIR/$f" "$pdir/$f" 2>/dev/null || true
  done
  log "[provenance] published this box's launch artifacts -> $pdir"
}

run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  CARC_P="$(run_live_path)" CARC_W="$1" "$PY" - <<'RLEOF' || true
import json, os, socket, time
json.dump({"what": os.environ["CARC_W"], "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("Invasion-screen round-3 freeze-latch sentinel: a MAIN-TREE commit while "
                   "this round is live risks a mixed-rev archive across EIGHT cells (the "
                   "track_d2_prep defect)."),
           "cleared_by": "the launcher's EXIT trap"},
          open(os.environ["CARC_P"], "w"), indent=2, sort_keys=True)
RLEOF
  log "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

# --------------------------------------------------------------------------- #
# Archive accounting.                                                          #
#                                                                              #
# ⚠️ -maxdepth 1 IS LOAD-BEARING. eval_fair_puct.py writes SUCCESS records as    #
# <cell>/seed%012d_a%d.json but FAILURE records into a SUBDIRECTORY,            #
# <cell>/failed/, using the SAME filename. A recursive find would count         #
# failures as completions and walk this launcher straight past a broken cell.   #
# --------------------------------------------------------------------------- #
n_records()        { find "$1" -maxdepth 1 -name 'seed*_a*.json' 2>/dev/null | wc -l; }
n_failed_records() { find "$1/failed" -maxdepth 1 -name 'seed*_a*.json' 2>/dev/null | wc -l; }

# A pass killed by `timeout` strands .claim files, and a stranded claim stalls
# resume until it ages past CLAIM_STALE_SECS (feedback_shared_claim_orphan_stall).
sweep_stale_claims() {
  local swept=0 c base
  while IFS= read -r c; do
    [ -n "$c" ] || continue
    base="${c%.claim}"
    if [ ! -f "$base.json" ]; then rm -f "$c" && swept=$((swept + 1)); fi
  done < <(find "$1" -maxdepth 1 -name '*.claim' 2>/dev/null || true)
  [ "$swept" -gt 0 ] && log "[claims] swept $swept orphan claim(s) with no matching record"
  return 0
}

# LAUNCHER-SAFETY void breaker, DISTINCT from READ_RULE SS3's G-N adjudication
# bar (<2%, decided after the fact against a frozen record).
check_void_rate() {   # $1 = cell out dir
  local sumfile
  sumfile="$(find "$1" -maxdepth 1 -name summary.json 2>/dev/null | sort | tail -1)"
  [ -n "$sumfile" ] && [ -f "$sumfile" ] || { log "[void-rate] no summary.json yet -- skipping"; return 0; }
  CARC_S="$sumfile" CARC_PCT="$VOID_RATE_ABORT_PCT" "$PY" - <<'VEOF'
import json, os, sys
s = json.load(open(os.environ["CARC_S"])); pct = float(os.environ["CARC_PCT"])
n_failed = s.get("n_failed", 0) or 0
n_scored = s.get("n", 0) or 0
denom = max(n_scored + n_failed, 1)
rate = n_failed / denom
print(f"[void-rate] n_failed={n_failed} denom={denom} void_rate={rate:.3%}")
if rate * 100 >= pct:
    print(f"[void-rate] !!! ABORT: {rate:.1%} >= {pct}% -- LAUNCHER-SAFETY breaker. This is NOT "
          f"the READ_RULE G-N adjudication gate; it is a pre-adjudication abort to stop burning "
          f"compute against a broken instrument.")
    sys.exit(1)
print(f"[void-rate] OK (< {pct}% launcher-safety threshold).")
VEOF
}

# --------------------------------------------------------------------------- #
# ⭐ THE PER-CELL PRE-CHECK -- CARRIED FROM ROUND 2, WHERE IT RAN CLEAN 7/7     #
#                                                                              #
# Round 1 refused to start A/B/D until its IDENT cell had run AND passed its    #
# bar, so a wiring defect cost 8 core-h instead of 62. Round 3 has no IDENT     #
# cell -- but it has EIGHT cells and ~171 core-h, so it needs the same shape of #
# protection. It gets the STRICTER one round 2 introduced: after EVERY cell     #
# seals, the launcher re-reads that cell's own EMITTED manifest and refuses to  #
# start the NEXT cell unless it passes. A wiring defect therefore costs ONE     #
# cell (~21 core-h), not eight, wherever in the round it appears.               #
#                                                                              #
# ⭐ AND ROUND 3 HAS A SEAM WORTH GUARDING: on the LAPTOP the three A cells run  #
# first and the two JOINT cells last, so the interlock fires three times on     #
# proven one-knob plumbing before the round's genuinely new machinery -- a      #
# candidate leaf carrying TWO invasion knobs -- spends a deck. The SS9 laptop    #
# smoke has already run J_HIGH's exact config by then, so the joint path is     #
# checked twice before it is trusted once.                                      #
#                                                                              #
# ⚠️ THE ARITHMETIC IS screen_lib's, NOT this shell's: it calls the SAME        #
# `leaf_gate()` the adjudicator's G-LEAF calls, so the live check and the       #
# post-hoc check CANNOT DRIFT APART. That is the whole reason the bar library   #
# exists as a separate importable file (the track_d2r2_prep defect).            #
#                                                                              #
# ⚠️ AND IT READS `manifest.json` FOR CONFIG, `summary.json` FOR STATISTICS --   #
# round 1's deviation IS-D1 was exactly this reader taking config off           #
# summary.json, getting `{}`, and fail-closed voiding a HEALTHY cell (while a   #
# vacuous `{} == {}` made a second conjunct pass). The fixed address is carried #
# here, and the vacuity is now impossible because leaf_gate() requires the      #
# hashes to be present STRINGS, not merely equal.                               #
# --------------------------------------------------------------------------- #
cell_precheck() {   # $1 = cell name
  local c="$1" co; co="$(cell_out "$c")"
  CARC_LIB="$LIB" CARC_CELL_OUT="$co" CARC_CELL="$c" "$PY" - <<'IEOF'
import glob, importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location("screen_lib", os.environ["CARC_LIB"])
L = importlib.util.module_from_spec(spec)
# ⚠️ MUST be in sys.modules BEFORE exec_module (the @dataclass annotation lookup).
sys.modules["screen_lib"] = L
spec.loader.exec_module(L)
out = os.environ["CARC_CELL_OUT"]
c = L.cell_by_name(os.environ["CARC_CELL"])

# ⚠️ NON-RECURSIVE on purpose -- <cell>/failed/ holds failure records with the
# SAME filename pattern and must never be counted as completions.
recs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(out, "seed*_a*.json")))]
if not recs:
    print(f"[precheck {c.name}] !!! no records found -- cannot proceed."); sys.exit(1)
mean, z, n, se, _ = L.paired_margin(recs)

# DEVIATION IS-D1's fixed address: config-shaped conjuncts come from manifest.json;
# summary.json carries NO config block at all. n_failed is a statistic and stays
# on summary.json.
mans = sorted(glob.glob(os.path.join(out, "manifest.json")))
sums = sorted(glob.glob(os.path.join(out, "summary.json")))
cfg = json.load(open(mans[-1])).get("config", {}) if mans else {}
n_failed = json.load(open(sums[-1])).get("n_failed") if sums else None

lg = L.leaf_gate(c, cfg.get("cand_leaf_hash"), cfg.get("opp_leaf_hash"),
                 (cfg.get("cand_leaf_cfg") or {}).get("v29_meeple_curve"))
cand_inv = {k: v for k, v in (cfg.get("cand_leaf_cfg") or {}).items()
            if k.startswith("invasion") and v != L.INVASION_DEFAULTS.get(k)}
opp_inv = {k: v for k, v in (cfg.get("opp_leaf_cfg") or {}).items()
           if k.startswith("invasion") and v != L.INVASION_DEFAULTS.get(k)}
inv_ok = (cand_inv == dict(c.cand_invasion)) and (opp_inv == dict(c.opp_invasion))
bsha = json.load(open(mans[-1])).get("carc_rs_binary_sha") if mans else None
same_ok, same_why = L.wheel_is_r1s(bsha)

conj = {"leaf_gate": lg["ok"], "invasion_blocks": inv_ok,
        "n_failed_zero": (n_failed == 0), "wheel_is_round_1s": same_ok,
        "has_statistic": (z is not None)}
ok = all(conj.values())
print(f"[precheck {c.name}] n_paired={n} D={mean if mean is None else round(mean, 4)} "
      f"SE={se if se is None else round(se, 4)} z={z if z is None else round(z, 4)}")
print(f"[precheck {c.name}] cand {cfg.get('cand_leaf_hash')} (want {c.cand_leaf_hash}) "
      f"vs opp {cfg.get('opp_leaf_hash')} (want {c.opp_leaf_hash}, {c.opponent})")
print(f"[precheck {c.name}] cand_invasion={cand_inv} (want {dict(c.cand_invasion)})")
print(f"[precheck {c.name}] opp_invasion={opp_inv} (want {dict(c.opp_invasion)})")
for k, v in conj.items():
    print(f"[precheck {c.name}]   {'PASS' if v else 'FAIL'}  {k}")
if not ok:
    print(f"[precheck {c.name}] !!! {lg['why']}")
    print(f"[precheck {c.name}] !!! {same_why}")
    print(f"[precheck {c.name}] !!! STOPPING THE ROUND HERE. A cell whose leaves are not the")
    print(f"[precheck {c.name}] !!! pre-registered ones is U-UNREADABLE at adjudication, and a")
    print(f"[precheck {c.name}] !!! defect that reached this cell will reach the next. That is")
    print(f"[precheck {c.name}] !!! the entire point of checking after every cell: it costs ONE")
    print(f"[precheck {c.name}] !!! cell (~21 core-h), not eight (~171).")
    print(f"[precheck {c.name}] !!! ⛔ This pre-check is STATISTICS-BLIND: it reads no bar and")
    print(f"[precheck {c.name}] !!! no branch. It cannot stop the round for a DISAPPOINTING")
    print(f"[precheck {c.name}] !!! result, only for a BROKEN one.")
sys.exit(0 if ok else 1)
IEOF
}

# =========================================================================== #
# DRY RUN                                                                     #
# =========================================================================== #
print_dry_run() {
  log "DRY RUN -- no games start, no band is spent, no guards enforced beyond argv construction"
  log "repo            : $REPO"
  log "python          : $PY"
  log "⭐ BOX ROLE     : $BOXROLE   W=$W   share=$SHARE"
  log "   this box runs: $(box_cells | tr '\n' ' ')"
  log "   out-root     : $OUT   (ON THE SHARE -- the LOCAL box adjudicates over BOTH"
  log "                  boxes' archives and can only see this box's cells if they land there)"
  log "   smoke        : ${BOX_SMOKE_CELL[$BOXROLE]} @ ${BOX_SMOKE_SEED[$BOXROLE]}"
  log "   ⛔ WHOLE CELLS PER BOX, assignment FROZEN in the prereg; G-HOST re-checks it"
  log "      against the emitted manifest, and this launcher refuses a foreign cell up front."
  log "band            : $BAND   (8 cells, DISJOINT ranges, no deck reuse)"
  log "⛔ W_LOCAL=14 FOR THE WHOLE ROUND -- owner constraint 2026-08-27, verbatim \"limit"
  log "   local to w14 starting at 11am\" (the interactive-use window). NEVER 22-then-14:"
  log "   --workers is per-invocation and a cell runs in bounded resumable passes, so a"
  log "   mid-round change would run one cell's passes at two different W. ⚠️ It moves"
  log "   WALL CLOCK and the box assignment, and NOTHING ELSE -- games are bit-identical"
  log "   at any W and no gate in this pair reads a clock."
  log "budget          : k${K_DETS} x ${SIMS_PER_DET} = ${TOTAL_SIMS} total sims, BOTH sides"
  log "                  (SCREENING budget; production is k8x1376=11008 -- expect the harness's"
  log "                   non-fatal [warn] about the PRODUCTION.yaml deviation, DO NOT suppress it)"
  log "tie-arbiter     : OFF both sides -- NO --cand-tiearb-* flag is emitted below"
  log "tenancy         : NON-EXCLUSIVE, RESULT-SAFE (sims-denominated; DESIGN.md SS6.3)"
  log "W               : $W   (throughput only -- games are bit-identical at any W)"
  log "inherited IDENT : round 1's PASS (z 0.9624, n=400). ⛔ NO IDENT CELL THIS ROUND."
  log "                  G-WHEEL-SAME pins carc_rs_binary_sha == $R1_WHEEL_BINARY_SHA;"
  log "                  a changed wheel -- or a different BOX -- re-owes an IDENT."
  log ""
  local c
  for c in "${CELL_NAMES[@]}"; do
    [ -z "$ONLY" ] || [ "$ONLY" = "$c" ] || continue
    if [ "${CELL_BOX[$c]}" != "$BOXROLE" ]; then
      log "[dry-run] CELL $c: ⛔ NOT THIS BOX'S (frozen to ${CELL_BOX[$c]}) -- refused at launch"
      continue
    fi
    build_argv "$c" "${CELL_GAMES[$c]}" "${CELL_SEED[$c]}" "$W" "${CELL_SUB[$c]}" no-stamp
    printf '[dry-run] CELL %-6s:' "$c"; printf ' %q' "${ARGV[@]}"; printf '\n'
    log "  decks         : ${CELL_SEED[$c]}..$(( CELL_SEED[$c] + CELL_DECKS[$c] - 1 )) (${CELL_DECKS[$c]} decks / ${CELL_GAMES[$c]} games)"
    log "  candidate leaf: ${CELL_LEAF[$c]}  -> pinned hash ${CELL_HASH[$c]}"
    if [ "${CELL_BENV[$c]}" = "1" ]; then
      log "  opponent leaf : ⭐ THE SHAPE-B AGENT -> pinned hash ${CELL_OPPHASH[$c]}"
      log "                  (champion curve125 + invasion_alpha $SHAPE_B_ALPHA @ cap $SHAPE_B_ALPHA_CAP,"
      log "                   bit-for-bit round 1's B_MID candidate). Set by the two"
      log "                   CARCASSONNE_INVASION_* variables in the argv above, which move"
      log "                   the harness's env DEFAULT_CONFIG and therefore _curve125_leaf_cfg()."
      log "                  The CANDIDATE takes them back off with EXPLICIT ZEROS in its JSON."
    else
      log "  opponent leaf : the plain champion -> pinned hash ${CELL_OPPHASH[$c]}"
      log "                  (the argv PINS the invasion env OFF at 0.0/0.0 rather than relying"
      log "                   on absence -- a stray export cannot reach this cell)"
    fi
    log "  drift flag    : --allow-leaf-hash-drift (every round-3 cell carries a nonzero weight; the J cells carry TWO)"
    log ""
  done
  log "⭐ SINGLE-VARIABLE PROPERTY, visible in the argv above:"
  log "   WITHIN a cell -- --k-dets/--sims and --opp-k-dets/--opp-sims are the SAME numbers,"
  log "     and the only asymmetric inputs are --cand-leaf-json (a candidate-side-only knob:"
  log "     eval_fair_puct.py:3769-3778 gives the opponent _curve125_leaf_cfg() unconditionally)"
  log "     and, on the C cells, the env that moves _curve125_leaf_cfg() itself."
  log "   ⭐ ROUND 3's STATEMENT OF IT: the two sides differ in EXACTLY the pre-registered term"
  log "     knobs -- ONE key on an A cell (beta), TWO on a J cell (beta and gamma, both on the"
  log "     candidate, against the plain champion), THREE on a C cell (the candidate's gamma"
  log "     plus the OPPONENT's alpha and cap). G-SINGLEVAR checks that set equality TWO-SIDED"
  log "     against the emitted manifest, and G-LEAF checks BOTH pinned hashes."
  log "   ⛔ A J CELL IS NOT 'TWO EXPERIMENTS IN ONE CELL'. It is ONE leaf with one hash,"
  log "     screened against the champion as one thing, and its margin attributes NOTHING to"
  log "     either knob (screen_lib.JOINT_ATTRIBUTION_BAN). Attribution needs a later ABLATION"
  log "     pair on a fresh band -- a fresh pair and a fresh funding decision."
  log ""
  local sc="${BOX_SMOKE_CELL[$BOXROLE]}" ss="${BOX_SMOKE_SEED[$BOXROLE]}"
  build_argv "$sc" "$SMOKE_GAMES" "$ss" "$SMOKE_WORKERS" "smoke_${CELL_SUB[$sc]}" no-stamp
  # (the REAL smoke additionally carries --stamp-key BLIND_COMMIT=<sha> and
  #  --stamp-key SCREEN_CELL=<cell>, exactly as a real cell does -- G-BLIND
  #  requires the stamp on the smoke archive too)
  printf '[dry-run] SMOKE (%s cfg, box %s):' "$sc" "$BOXROLE"; printf ' %q' "${ARGV[@]}"; printf '\n'
  log "  smoke decks   : $ss..$(( ss + SMOKE_GAMES/2 - 1 )) -- DISJOINT, discarded, never pooled"
  log "  ⭐ ONE SMOKE PER BOX: each box smokes its OWN most-plumbing cell config, on the"
  log "     machine that will spend its decks. The LAPTOP's (J_HIGH, the two-knob joint leaf"
  log "     that has never emitted a manifest on any box) is the load-bearing one."
  log ""
  CARC_LIB="$LIB" "$PY" - <<'CEOF' || true
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("screen_lib", os.environ["CARC_LIB"])
L = importlib.util.module_from_spec(spec)
sys.modules["screen_lib"] = L
spec.loader.exec_module(L)
print("[dry-run] PINNED LEAF HASHES, BOTH SIDES OF EVERY CELL, AND THE FROZEN BOX:")
print(f"[dry-run]   {'cell':7s} {'box':7s} {'shape/rung':11s} {'dose':46s} "
      f"{'candidate':17s} {'opponent':17s} who        chain?")
for c in L.CELLS:
    print(f"[dry-run]   {c.name:7s} {c.box:7s} {c.shape + ' ' + c.rung:11s} "
          f"{c.dose_label:46s} {c.cand_leaf_hash:17s} "
          f"{c.opp_leaf_hash:17s} {c.opponent:10s} "
          f"{'⭐ ADOPTION-CHAIN-ELIGIBLE' if c.chain_eligible else '⛔ never the chain'}")
print("")
print("[dry-run] ⭐⭐ THE TWO JOINT CELLS ARE THE ADOPTION-CHAIN-ELIGIBLE NOVELTY:")
print(f"[dry-run]   {L.JOINT_WHAT_IT_IS}")
print(f"[dry-run]   {L.JOINT_LICENSES}")
print(f"[dry-run]   {L.JOINT_ATTRIBUTION_BAN}")
print("")
print("[dry-run] ⭐ THE WEIGHTS, AND WHERE THEY CAME FROM (DESIGN SS3.2):")
wd = L.WEIGHT_DERIVATION
print(f"[dry-run]   A: local quadratic through D(0)=0 (structural), 0.04 -> +0.936 (r2), "
      f"0.12 -> +0.524 (r1)")
print(f"[dry-run]      peak at beta {wd['A']['peak'] if False else L.A_FIT[3]:.4f}; "
      f"ladder {wd['A']['chosen']} brackets it AND round 2's best point (0.04)")
print(f"[dry-run]   C: TWO readings, deliberately both. r2-only -> CONVEX, vertex a MINIMUM "
      f"at {L.C_FIT_R2_ONLY[3]:.4f} => peak <= 0.08.")
print(f"[dry-run]      anchored at gamma=0 by r1's B_MID sign-flipped -> peak "
      f"{L.C_FIT_ANCHORED[3]:.4f} => peak > 0.08. They DISAGREE, so the ladder")
print(f"[dry-run]      {wd['C']['chosen']} brackets the WHOLE contested region.")
print(f"[dry-run]   J: rung-matched to the two ladders -- J_LOW=(A_LOW beta, C_LOW gamma), "
      f"J_HIGH=(A_MID beta, C_MID gamma).")
print(f"[dry-run]   ⛔ ALL EIGHT WEIGHTS SIT INSIDE THE LICENSED INTERVALS "
      f"{L.LICENSED_INTERVALS}; sanity_check() refuses otherwise.")
print("")
print("[dry-run] ⭐ THE SPLIT ARITHMETIC -- ALL SIX WHOLE-SHAPE PARTITIONS AT THIS ROUND'S W")
print("[dry-run]   (local W=14 by owner constraint, laptop W=22; ROUND WALL is the MAX):")
for r in L.split_table():
    mark = "  <== FROZEN" if r["chosen"] else ""
    print(f"[dry-run]   #{r['rank']}  local={str(r['local']):14s} {r['local_core_hours']:6.2f} ch "
          f"-> {r['local_wall_hours']:5.2f} h | laptop={str(r['laptop']):14s} "
          f"{r['laptop_core_hours']:6.2f} ch -> {r['laptop_wall_hours']:5.2f} h | "
          f"ROUND WALL {r['round_wall_hours']:5.2f} h{mark}")
print("")
print(f"[dry-run] ⭐ {L.BOX_ASSIGNMENT_RULE}")
print("")
print("[dry-run] projected cost (screen_lib.round_cost_envelope, DESIGN.md SS6):")
env = L.round_cost_envelope()
for c in L.CELLS:
    p = env["point"]["per_cell"][c.name]
    tag = ("  ⚠️ BOTH sides pay invasion arithmetic (gamma vs alpha)" if c.shape == "C"
           else "  ⚠️ the CANDIDATE pays it TWICE — ⛔ the round's ONE unmeasured cost"
           if c.shape == "J" else "")
    ratio = "" if p["box_ratio_is_measured"] else f"  [x{p['box_ratio']} ASSUMED]"
    print(f"[dry-run]   {c.name:7s} [{p['box']:6s}] {c.n_games:4d} games -> "
          f"{p['core_hours']:5.1f} core-h  ~{p['wall_minutes']:4.0f} min wall  "
          f"({p['s_per_game']:.1f} s/game{ratio}){tag}")
print("[dry-run]   -- PER BOX (⭐ THEY RUN CONCURRENTLY: the round's wall is the MAX) --")
for role, b in env["point"]["per_box"].items():
    print(f"[dry-run]     {role:7s} W={b['W']:<3d} {len(b['cells'])} cells -> "
          f"{b['core_hours']:5.1f} core-h  ~{b['wall_hours']:4.2f} h wall  {b['cells']}")
print(f"[dry-run]   TOTAL across both boxes -> {env['point']['core_hours']:5.1f} core-h"
      f"   ROUND WALL ~{env['point']['wall_hours']:4.2f} h (the MAX, not the sum)")
print(f"[dry-run]   (local-equivalent compute: {env['point']['core_hours_local_equiv']:.1f} "
      f"core-h; single-box local would be ~{env['point']['wall_hours_single_box_local']:.2f} h "
      f"wall, so the split buys ~"
      f"{env['point']['wall_hours_single_box_local'] - env['point']['wall_hours']:.2f} h)")
print(f"[dry-run]   ENVELOPE            -> {env['low']['core_hours']:.1f} .. "
      f"{env['high']['core_hours']:.1f} core-h  "
      f"({env['low']['wall_hours']:.2f} .. {env['high']['wall_hours']:.2f} h round wall)")
print(f"[dry-run]   ⚠️ {env['why']}")
print(f"[dry-run]   ⚠️ {L.LAPTOP_RATIO_NOTE}")
print(f"[dry-run]   ⛔ {L.W_LOCAL_NOTE}")
print("[dry-run]   ⛔ every other figure is round-2 REALIZED, and the model reproduces")
print("[dry-run]      round 2's three shapes WITHOUT EVER UNDER-PREDICTING and by no more")
print("[dry-run]      than +5% (A +1.00%, B +3.23%, C-on-laptop +1.08%) -- a DIRECTIONAL")
print("[dry-run]      assertion in sanity_check(), because a model that decides funding")
print("[dry-run]      should err DEAR.")
CEOF
  log ""
  log "adjudicator     : $REPO/$ADJUDICATOR  (run --selftest before trusting any real read)"
  log "⛔ NOT LAUNCHED. A real cell additionally requires: BLIND_COMMIT stamped, PINNED_SRC_REV"
  log "   written, BAND_CLAIMED dropped, the wheel VERIFIED IDENTICAL to round 1's, and"
  log "   DESIGN.md SS0(a) funding."
}

# =========================================================================== #
# SMOKE                                                                       #
# =========================================================================== #
run_smoke() {
  local c="${BOX_SMOKE_CELL[$BOXROLE]}"
  local seed="${BOX_SMOKE_SEED[$BOXROLE]}"
  local sub="smoke_${CELL_SUB[$c]}" so="$OUT/smoke_${CELL_SUB[$c]}"
  log "SMOKE (DESIGN.md SS9) on box '$BOXROLE': ${SMOKE_GAMES} games at $c's EXACT"
  log "  production knobs, throwaway seed $seed, W=$SMOKE_WORKERS. Never pooled, never"
  log "  claimed, never adjudicated as a result. It spends NO BAND and drops NO"
  log "  BAND_CLAIMED -- but it DOES write its own PINNED_SRC_REV / BLIND_PROOF.json /"
  log "  SRC_CLEAN boundaries, because G-REV and G-BLIND are NOT in READ_RULE SS3.5's"
  log "  allowed set and must PASS on the smoke."
  log "  ⭐ ONE SMOKE PER BOX, each running THAT BOX'S OWN most-plumbing cell config."
  log "  A single-box round could smoke once; a two-box round cannot -- each box has its"
  log "  own wheel install, repo checkout, share mount and W, and the leg exists to prove"
  log "  the plumbing ON THE MACHINE THAT WILL SPEND THE DECKS."
  if [ "$BOXROLE" = "laptop" ]; then
    log "  ⛔ THIS IS THE LOAD-BEARING ONE: the laptop owns the A ladder AND BOTH JOINT"
    log "  cells, and the JOINT candidate leaf -- TWO invasion knobs on ONE leaf, a"
    log "  two-key leaf diff, and the round's only adoption-chain-eligible novelty --"
    log "  has NEVER emitted a manifest on any box in any round. J_HIGH rather than"
    log "  J_LOW because it carries the larger dose of both knobs, so a forwarding"
    log "  failure on either has the most room to show."
  else
    log "  The local box owns the three C cells, whose shape-B ENV regime round 2 proved"
    log "  end to end -- so this leg re-confirms the launcher, the wheel install and the"
    log "  env regime ON THIS BOX rather than seeing any of it for the first time."
    log "  ⚠️ It is also this box's first run at W=14, which is a wall-clock fact and"
    log "  nothing more: games are bit-identical at any W."
  fi
  require_share_mounted
  require_table_agrees
  preflight_rules
  preflight_wheel
  census_advisory

  # ------------------------------------------------------------------------- #
  # ⭐ THE SMOKE WRITES ITS OWN LAUNCH ARTIFACTS (round 1's amendment 1).       #
  #                                                                            #
  # G-REV and G-BLIND are NOT in READ_RULE SS3.5's pinned allowed set, so both  #
  # must PASS on the smoke archive. But `PINNED_SRC_REV`, `SRC_CLEAN.jsonl` and #
  # `BLIND_PROOF.json` are otherwise only written on the REAL-cell path, so     #
  # G-REV read "PINNED_SRC_REV ABSENT -- ABSENT is FAIL" on EVERY round-1 smoke #
  # and the leg exited 11 before a single real game could be authorised.        #
  #                                                                            #
  # ⛔ THE FIX IS TO SUPPLY THE WITNESS, NEVER TO WIDEN THE ALLOWED SET.        #
  # ABSENT-is-FAIL stays sacred: the launcher knows the rev, so it writes it.   #
  # SAFE and non-pre-empting -- measurement/ is excluded from CODE_PATHS, and a #
  # real launch overwrites the file from `git rev-parse HEAD` anyway.           #
  # The smoke still claims NO band and drops NO BAND_CLAIMED.                   #
  # ------------------------------------------------------------------------- #
  git -C "$REPO" rev-parse HEAD > "$DIR/$PINNED_SRC_REV_FILE"
  log "SMOKE wrote $PINNED_SRC_REV_FILE = $(tr -d '[:space:]' < "$DIR/$PINNED_SRC_REV_FILE")"
  write_blind_proof
  record_src_boundary "pre-flight"

  mkdir -p "$LOGS" "$so"
  # ⭐ WITH-STAMP, EXACTLY AS A REAL CELL (round 1's amendment round 2).
  # G-BLIND requires every adjudicated manifest to carry `stamps.BLIND_COMMIT`,
  # and G-BLIND is NOT in READ_RULE SS3.5's allowed set -- so it must PASS on the
  # smoke archive too. ⛔ The fix is to make the SMOKE match the real cells, NEVER
  # to special-case the gate.
  build_argv "$c" "$SMOKE_GAMES" "$seed" "$SMOKE_WORKERS" "$sub" with-stamp
  set +e
  "${ARGV[@]}" 2>&1 | tee "$LOGS/smoke.log"
  local rc=${PIPESTATUS[0]}
  set -e
  if [ "$rc" -ne 0 ]; then
    log "!!! SMOKE FAILED rc=$rc -- do NOT launch. See $LOGS/smoke.log"
    exit 1
  fi

  log "SMOKE -- asserting n_failed == 0 on the emitted archive"
  CARC_OUT="$so" "$PY" - <<'SMEOF' || { log "!!! FATAL: smoke leg did not produce a clean archive."; exit 10; }
import glob, json, os, sys
cands = sorted(glob.glob(os.path.join(os.environ["CARC_OUT"], "**", "summary.json"), recursive=True))
if not cands:
    print("[smoke] !!! no summary.json found under", os.environ["CARC_OUT"]); sys.exit(1)
s = json.load(open(cands[-1]))
nf = s.get("n_failed")
if nf is None:
    print("[smoke] !!! summary.json has no n_failed field"); sys.exit(1)
if int(nf) != 0:
    print(f"[smoke] !!! n_failed = {nf} -- the config does not run clean. FATAL."); sys.exit(1)
print(f"[smoke] n_failed = 0 over n = {s.get('n')} games")
cm = s.get("champ_prefix_ms_per_move"); om = s.get("rung_ms_per_move")
if cm and om:
    print("")
    print("*** NOT A GATE -- a 16-game leg does not saturate W, and this pair has NO timing "
          "bar at all (DESIGN.md SS6.3). Printed for information; it adjudicates nothing. ***")
    print(f"[smoke] candidate {cm:.1f} ms/move  opponent {om:.1f} ms/move  ratio {cm/om:.3f}")
    print(f"[smoke] combined {cm + om:.1f} ms/move -- compare against DESIGN SS6.2's")
    print("[smoke]   local-box projection for this cell. ⭐ ON THE LAPTOP this is also the")
    print("[smoke]   FIRST CHECK OF THE per-game RATIO the two-box ETA MEASURED this round")
    print("[smoke]   (1.0935x, from the SAME shape-B leaf run on BOTH boxes in round 2 --")
    print("[smoke]   ⭐ MEASURED, not round 2's assumed 1.4x). ⭐ AND ON A J CELL THE")
    print("[smoke]   COMBINED figure is the FIRST OBSERVATION EVER of a two-knob invasion")
    print("[smoke]   leaf's per-move cost -- round 3's ONE unmeasured input, carried as an")
    print("[smoke]   ADDITIVE point estimate (836.4 ms/move) inside a [760.5, 872.9] envelope.")
    print("[smoke]   ⚠️ ON A C CELL BOTH SIDES PAY INVASION ARITHMETIC, so the ratio is")
    print("[smoke]   gamma-vs-alpha, NOT term-vs-plain.")
    print("[smoke]   ⛔ REPORT both discrepancies; do NOT re-freeze on either. This pair is")
    print("[smoke]   sims-denominated: no gate reads a clock and no bar moves with cost.")
SMEOF

  # --------------------------------------------------------------------- #
  # ⭐ THE STANDING RULE (h2h_22016_prep's post-mortem, adopted by          #
  # track_d2r4_prep and by round 1, carried here): the smoke step ENDS by   #
  # running the pair's OWN adjudicator against the archive the harness just #
  # EMITTED, and requires it to fail only on the pinned allowed set that a  #
  # 16-game throwaway cannot satisfy by construction.                       #
  # --------------------------------------------------------------------- #
  if [ ! -f "$ADJ" ]; then
    log "!!! FATAL: the pair's adjudicator is missing at $ADJ."
    log "!!! The smoke leg is not complete until analyze_screen.py --smoke-mode has read the"
    log "!!! archive the harness just emitted. Do not launch a real cell against an"
    log "!!! adjudicator that has never seen an emitted manifest."
    exit 11
  fi
  record_src_boundary "smoke-after"
  publish_provenance

  log "SMOKE -- running the pair's own adjudicator in --smoke-mode against $so"
  "$PY" "$ADJ" --smoke-mode --cell "$so" || {
    log "!!! FATAL: analyze_screen.py --smoke-mode returned nonzero on the smoke archive."
    log "!!! In --smoke-mode the adjudicator PASSES iff the ONLY failures are READ_RULE SS3.5's"
    log "!!! pinned allowed set (G-BAND G-DECKS G-N G-SAT G-HOST RECON/n_paired)."
    log "!!! ⛔ G-WHEEL-SAME IS NOT IN THAT SET -- a TIGHTENING over round 1, which had no"
    log "!!! such gate. The smoke runs the same wheel the cells will."
    log "!!! A nonzero exit means a REAL gate is broken on EMITTED output -- exactly what"
    log "!!! this step exists to catch before 6400 games are spent."
    exit 11
  }
  log "SMOKE PASS -- plumbing clean, adjudicator reads emitted output."
  log "NEXT: $PY $REPO/$ADJUDICATOR --selftest   (must exit 0)"
}

# =========================================================================== #
# ONE CELL, in bounded passes                                                 #
# =========================================================================== #
run_cell() {   # $1 = cell name
  local c="$1" co n_target sub
  co="$(cell_out "$c")"; n_target="${CELL_GAMES[$c]}"; sub="${CELL_SUB[$c]}"
  local done_sentinel="$DIR/DONE_cell_$c"
  if [ -f "$done_sentinel" ]; then
    log "cell $c already DONE -- skipping. Remove $done_sentinel to force a re-run."
    return 0
  fi
  rm -f "$DIR/FAILED_cell_$c" 2>/dev/null || true
  mkdir -p "$co"

  local pass=0 n_done prev_done t0 t1 dt
  n_done="$(n_records "$co")"
  log "CELL $c: starting from $n_done/$n_target records on disk "
  log "CELL $c: decks ${CELL_SEED[$c]}..$(( CELL_SEED[$c] + CELL_DECKS[$c] - 1 )), leaf ${CELL_LEAF[$c]}"
  log "CELL $c: candidate ${CELL_HASH[$c]} vs opponent ${CELL_OPPHASH[$c]} (shape_b_env=${CELL_BENV[$c]})"

  while [ "$n_done" -lt "$n_target" ]; do
    pass=$((pass + 1))
    if [ "$pass" -gt "$MAX_PASSES" ]; then
      log "!!! FATAL: MAX_PASSES=$MAX_PASSES exhausted at $n_done/$n_target on cell $c."
      log "!!! FAIL-CLOSED -- a resume loop that cannot finish is a defect, not a retry."
      touch "$DIR/FAILED_cell_$c"; exit 6
    fi
    assert_rev_pinned "$c-before-pass-$pass"
    require_ram "$RUNTIME_RAM_FLOOR_MB" "$c-before-pass-$pass" || { touch "$DIR/FAILED_RAM"; exit 8; }

    prev_done="$n_done"
    build_argv "$c" "$n_target" "${CELL_SEED[$c]}" "$W" "$sub" with-stamp
    log "CELL $c pass $pass/$MAX_PASSES: $n_done/$n_target records, timeout ${PASS_TIMEOUT_SECS}s"
    t0="$(date +%s)"
    set +e
    timeout --preserve-status "${PASS_TIMEOUT_SECS}s" "${ARGV[@]}" >> "$LOGS/cell_$c.log" 2>&1
    local rc=$?
    set -e
    t1="$(date +%s)"; dt=$((t1 - t0))
    assert_rev_pinned "$c-after-pass-$pass"
    sweep_stale_claims "$co"
    n_done="$(n_records "$co")"
    local made=$((n_done - prev_done))
    if [ "$made" -gt 0 ]; then
      log "CELL $c pass $pass: rc=$rc, ${dt}s wall, +$made games -> $n_done/$n_target"
      log "CELL $c pass $pass: REALIZED $(( dt * W / made )) worker-s/game (round 2 REALIZED 84.75 A / 79.25 B local, 100.67 C on laptop; round 3 projects 85.6 A / 93.1 C / 96.8 J in LOCAL-EQUIVALENT worker-s, x1.0935 on the laptop)"
    else
      log "CELL $c pass $pass: rc=$rc, ${dt}s wall, +0 games -> $n_done/$n_target"
    fi

    if [ "$rc" -eq 124 ]; then
      log "  pass hit its ${PASS_TIMEOUT_SECS}s timeout -- expected for a sized pass; the"
      log "  archive is resumable and the next pass continues it."
    elif [ "$rc" -ne 0 ]; then
      log "  pass rc=$rc (non-timeout). The harness is resumable under --shared-claim;"
      log "  continuing, but a pass that makes NO progress fails closed below."
    fi

    if [ "$made" -eq 0 ]; then
      local nf; nf="$(n_failed_records "$co")"
      log "!!! FATAL: cell $c pass $pass produced 0 new games at $n_done/$n_target."
      log "!!! failure records in $co/failed/ : $nf"
      if [ "$nf" -gt 0 ]; then
        log "!!! => the shortfall is PERMANENTLY-FAILING GAMES, not a stall. Failures are"
        log "!!! deck-deterministic on this harness (same deck, same seeds, same deterministic"
        log "!!! players => the same raise), so retrying cannot help. READ_RULE SS3 G-N requires"
        log "!!! $n_target scored with n_failed == 0 (a rate <2% is REPORTED, never silently"
        log "!!! absorbed). Diagnose the failure class before spending another pass."
      else
        log "!!! => a stalled resume loop with NO failures is a launcher/harness defect, not"
        log "!!! something to retry silently. Check $LOGS/cell_$c.log and look for stranded"
        log "!!! .claim files under $co (the sweep above should have cleared any orphan)."
      fi
      log "!!! FAIL-CLOSED."
      touch "$DIR/FAILED_cell_$c"; exit 5
    fi

    check_void_rate "$co" || { log "!!! ABORTING: void-rate breaker tripped on cell $c."
                               touch "$DIR/FAILED_VOID_RATE"; exit 7; }
  done

  # Final settling pass over the FULL range: every game is already recorded, so
  # this does no new work -- it exists so the harness writes the POOLED
  # summary.json over all n_target games that the adjudicator reads.
  log "CELL $c: all $n_done/$n_target records present -- running the FINAL POOLED SUMMARY pass"
  assert_rev_pinned "$c-before-seal"
  build_argv "$c" "$n_target" "${CELL_SEED[$c]}" "$W" "$sub" with-stamp
  set +e
  timeout --preserve-status "${PASS_TIMEOUT_SECS}s" "${ARGV[@]}" >> "$LOGS/cell_$c.log" 2>&1
  local src=$?
  set -e
  assert_rev_pinned "$c-after-seal"
  if [ "$src" -ne 0 ]; then
    log "!!! FATAL: cell $c's sealing pass exited rc=$src -- no pooled summary.json is trustworthy."
    touch "$DIR/FAILED_cell_$c"; exit 9
  fi
  check_void_rate "$co" || { touch "$DIR/FAILED_VOID_RATE"; exit 7; }
  touch "$done_sentinel"
  log "CELL $c DONE -- $n_done/$n_target games, $pass pass(es) + seal"
}

# =========================================================================== #
main() {
  mkdir -p "$LOGS"
  if [ "$DRY" -eq 1 ]; then print_dry_run; return 0; fi
  if [ "$SMOKE" -eq 1 ]; then run_smoke; return 0; fi

  require_preconditions
  mkdir -p "$OUT"
  publish_provenance
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "invasion-screen round 3, band $BAND, box $BOXROLE, cells $(box_cells | tr '\n' ' '), W=$W"

  [ -z "$ONLY" ] || require_cell_is_mine "$ONLY"

  local c
  for c in $(box_cells); do
    if [ -n "$ONLY" ] && [ "$ONLY" != "$c" ]; then
      log "skipping $c (--only $ONLY)"
      continue
    fi
    require_cell_is_mine "$c"
    run_cell "$c"
    # ⭐ THE PER-CELL INTERLOCK (DESIGN.md SS6.4 / SS3.1). Round 1 gated the whole
    # round on ONE identity cell; round 3 has no identity cell and EIGHT arms, so
    # it re-checks the EMITTED leaves after EVERY cell and refuses to continue on
    # a defect. A wiring failure costs ONE cell, not eight -- wherever it appears,
    # including at the laptop's A -> J seam where the two-knob leaf switches on.
    if ! cell_precheck "$c"; then
      log "!!! FATAL: the post-cell pre-check FAILED on $c. Stopping the round here."
      log "!!! ⛔ STATISTICS-BLIND: this check reads no bar and no branch. It cannot stop"
      log "!!! the round for a disappointing result, only for a broken one."
      touch "$DIR/FAILED_PRECHECK_$c"; exit 13
    fi
    publish_provenance
  done

  publish_provenance
  run_live_clear
  log "BOX '$BOXROLE' DONE -- its cells complete, RUN_LIVE cleared"
  log ""
  log "⛔ THE ROUND IS NOT DONE UNTIL **BOTH** BOXES ARE. Adjudication needs all"
  log "   eight cells: G-WHEEL-SAME is round-wide, G-REV checks ONE code_rev across"
  log "   BOTH boxes, and READ_RULE SS4's round table reads every cell."
  log "   This box ran: $(box_cells | tr '\n' ' ')"
  log ""
  log "NEXT (on the LOCAL box, once BOTH boxes' archives are on the share):"
  log "      $PY $REPO/$ADJUDICATOR --selftest   (must exit 0), then"
  log "      $PY $REPO/$ADJUDICATOR --run-dir $SHARE_LOCAL/$OUT_LEAF"
  log "The fired branch IS the authorization to report it (READ_RULE.md SS4/SS7) -- but every"
  log "ACTION a branch licenses is a fresh funding decision and a fresh pair."
}

main "$@"
