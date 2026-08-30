#!/usr/bin/env bash
# =========================================================================== #
# run_golden_gate.sh — THE FPU DOSE-LADDER'S GOLDEN GATE, END TO END          #
#                                                                             #
# ⛔⛔ IT HAS NOT BEEN RUN. It is a LAUNCH PRECONDITION (DESIGN.md §9) and     #
#     `run_cells.sh` REFUSES every real rung until                            #
#     `../FPU_BITEXACT_LADDER.json` exists, reads PASS, and carries THIS      #
#     BOX's own installed `carc_rs_binary_sha`.                               #
#                                                                             #
# ⚠️⚠️ RUN IT ON EVERY BOX THAT WILL PLAY A RUNG, AT THE LAUNCH REV.          #
#     `carc_rs_binary_sha` is BOX-LOCAL — two boxes compiling identical       #
#     source produce different bytes — so one box's gate does not cover the   #
#     other's, exactly as `G-WHEEL-SAME` is asserted per box.                 #
#                                                                             #
# WHY IT EXISTS AT ALL, when the parent round already banked one:             #
#     `measurement/fpu_resurrection_prep/FPU_BITEXACT.json` is PASS, and its  #
#     `ONE-WHEEL` check binds all three of its legs to carc_rs binary         #
#     `f6316d42838574de`. The S1 `R7`/`R6` merge (commit `316df67d`,          #
#     2026-08-30) then changed `carc_core::search` and                        #
#     `fair::search_worlds` — the modules that implement the FPU rule and the #
#     PIMC descent this round plays on — and the installed binary has moved   #
#     twice since (`5c53dd8b` for the parent's own cells, then `2ef38b51`).   #
#     The R7 counters are ARGUED to be play-neutral. ⛔ "Argued play-neutral"  #
#     is precisely what the hard-coded `None` also was, and this whole family #
#     of rounds exists because that argument was wrong once already.          #
#                                                                             #
# WHAT IT ADDS OVER THE PARENT'S (DESIGN.md §9.1):                            #
#     * a POSITIVE control PER RUNG, including 0.05 — the smallest dose, and  #
#       the one a dose-blind build would be hardest to tell from the champion #
#     * ⭐⭐ DOSE-DISTINCT — the four dosed legs must differ FROM EACH OTHER.   #
#       A build that clamped or bucketed the dose would pass every POSITIVE   #
#       and still flatten the ladder into one measurement repeated four times #
#     * the wheel STAMPED into the artefact, so the launcher can refuse a     #
#       gate that was run on a different binary than the one it will play     #
#                                                                             #
# COST: 6 legs x 20 seeded self-play games at k2 x 96. Minutes, not hours.    #
#                                                                             #
# USAGE                                                                       #
#     ./run_golden_gate.sh [--old-rev <sha>] [--seeds N] [--keep]             #
#                                                                             #
#   --old-rev  the PRE-PLUMBING commit whose `src`+`engine` become the OLD    #
#              leg. Default: the parent of a369f437 ("fpu: thread             #
#              fpu_reduction end-to-end"), discovered at run time so a        #
#              rebased history cannot silently point it at the wrong tree.    #
#   --seeds    fewer than 20 = a cheap PREVIEW. ⛔ THE GATE ITSELF USES 20;    #
#              `ladder_diff.py` records the count and a short run is visible. #
# =========================================================================== #
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREP="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$PREP/../.." && pwd)"

OLD_REV=""; SEEDS=20; KEEP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --old-rev) OLD_REV="$2"; shift 2 ;;
    --seeds) SEEDS="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python found" >&2; exit 2; }

STAMP() { echo "[golden_gate $(date -u +%FT%TZ) $(hostname)] $*"; }
DIE() { STAMP "!!! $*"; exit 13; }

# --------------------------------------------------------------------------- #
# 0. RESOLVE THE PRE-PLUMBING COMMIT                                           #
# --------------------------------------------------------------------------- #
# ⭐ DISCOVERED, NOT HARD-CODED: `git log -S` finds the commit that INTRODUCED
# the `fpu_reduction` field, and the OLD leg is its FIRST PARENT. A hard-coded
# sha would silently point at the wrong tree after any history rewrite, and the
# leg would then be "new code run twice" — which `TWO-TREES` catches, but only
# after the compute is spent.
if [ -z "$OLD_REV" ]; then
  PLUMB="$(git -C "$REPO" log --format=%H -S 'fpu_reduction' \
             -- src/carcassonne_ai/heuristic_prior_mcts.py | tail -1)"
  [ -n "$PLUMB" ] || DIE "could not find the commit that introduced fpu_reduction"
  OLD_REV="$(git -C "$REPO" rev-parse "${PLUMB}^")"
  STAMP "fpu plumbing landed in $PLUMB; OLD leg = its parent $OLD_REV"
fi
git -C "$REPO" cat-file -e "${OLD_REV}^{commit}" 2>/dev/null \
  || DIE "--old-rev $OLD_REV is not a commit in this repo"

# ⛔ AND PROVE IT IS ACTUALLY PRE-PLUMBING, rather than trusting the log walk.
git -C "$REPO" show "${OLD_REV}:src/carcassonne_ai/heuristic_prior_mcts.py" \
  | grep -q 'fpu_reduction' \
  && DIE "⛔ $OLD_REV ALREADY carries fpu_reduction — it is not a pre-plumbing " \
         "tree and the IDENTITY leg would compare the new code to itself."
STAMP "verified: $OLD_REV has NO fpu_reduction field (the pre-plumbing tree)"

# --------------------------------------------------------------------------- #
# 1. MATERIALISE THE OLD TREE                                                  #
# --------------------------------------------------------------------------- #
# ⚠️ `git archive` of `src` + `engine` ONLY. The two legs must differ in the
# PYTHON SOURCE and in NOTHING ELSE — same wheel, same venv, same env.
OLD_TREE="${TMPDIR:-/tmp}/fpu_ladder_oldtree_${OLD_REV:0:12}"
WORK="${TMPDIR:-/tmp}/fpu_ladder_gg_$$"
mkdir -p "$OLD_TREE" "$WORK" || DIE "could not create the scratch dirs"
if [ ! -d "$OLD_TREE/src" ]; then
  git -C "$REPO" archive "$OLD_REV" src engine | tar -x -C "$OLD_TREE" \
    || DIE "git archive of $OLD_REV failed"
fi
[ -d "$OLD_TREE/src/carcassonne_ai" ] || DIE "the OLD tree has no src/carcassonne_ai"
STAMP "OLD tree at $OLD_TREE"
STAMP "NEW tree at $REPO"

# ⛔ THE TWO TREES MUST NOT BE THE SAME PATH. `ladder_diff.py`'s TWO-TREES check
# catches it too, but not before six legs of compute.
[ "$OLD_TREE" != "$REPO" ] || DIE "OLD and NEW resolved the same path"

# --------------------------------------------------------------------------- #
# 2. THE SIX LEGS                                                              #
# --------------------------------------------------------------------------- #
# ⚠️ EVERY leg runs against THIS BOX's ONE installed carc_rs wheel. Only
# PYTHONPATH changes between OLD and NEW; only `--fpu` changes among the CTRLs.
# ⚠️ R9 is env-latched at IMPORT, and the leaf shape is frozen by
# scripts/human_anchor/env_preamble before carcassonne_ai is imported (the leg
# script does that itself, first thing).
export CARCASSONNE_FIX_R9=1
export PYTHONUNBUFFERED=1

leg() {  # leg <label> <tree> <fpu-or-empty> <outfile>
  local label="$1" tree="$2" fpu="$3" out="$4"
  local args=("$HERE/identity_leg.py" --seeds "$SEEDS" --label "$label"
              --out "$out")
  [ -z "$fpu" ] || args+=(--fpu "$fpu")
  STAMP "leg $label (tree=$tree fpu=${fpu:-None}) ..."
  PYTHONPATH="$tree/src:$tree/engine" nice -n 19 "$PY" "${args[@]}" \
    || DIE "leg $label FAILED"
}

leg OLD  "$OLD_TREE" ""     "$WORK/OLD.json"
leg NEW  "$REPO"     ""     "$WORK/NEW.json"
leg CTRL_005 "$REPO" 0.05   "$WORK/CTRL_005.json"
leg CTRL_010 "$REPO" 0.1    "$WORK/CTRL_010.json"
leg CTRL_015 "$REPO" 0.15   "$WORK/CTRL_015.json"
leg CTRL_030 "$REPO" 0.3    "$WORK/CTRL_030.json"

# --------------------------------------------------------------------------- #
# 3. ADJUDICATE                                                                #
# --------------------------------------------------------------------------- #
"$PY" "$HERE/ladder_diff.py" \
  "$WORK/OLD.json" "$WORK/NEW.json" \
  "$WORK/CTRL_005.json" "$WORK/CTRL_010.json" \
  "$WORK/CTRL_015.json" "$WORK/CTRL_030.json" \
  --out "$PREP/FPU_BITEXACT_LADDER.json"
RC=$?

if [ "$KEEP" -eq 1 ]; then
  STAMP "legs kept at $WORK"
else
  cp "$WORK"/*.json "$HERE/" 2>/dev/null || true
  STAMP "legs copied beside this script (git-ignored); scratch was $WORK"
fi

if [ "$RC" -ne 0 ]; then
  DIE "⛔ THE GOLDEN GATE FAILED — see $PREP/FPU_BITEXACT_LADDER.json. " \
      "⛔ NO RUNG MAY BE PLAYED. run_cells.sh will refuse."
fi
STAMP "⭐ GOLDEN GATE PASS -> $PREP/FPU_BITEXACT_LADDER.json"
STAMP "⚠️ This artefact is BOX-LOCAL (it stamps this box's carc_rs_binary_sha). " \
      "Run this script on the OTHER box before that box plays a rung."
