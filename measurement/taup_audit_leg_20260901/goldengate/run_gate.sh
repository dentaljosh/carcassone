#!/usr/bin/env bash
# =========================================================================== #
# THE --cand-tau-p GOLDEN GATE — three legs + the adjudication.               #
#                                                                             #
#   OLD   `git show HEAD:scripts/classical_search/eval_fair_puct.py`, i.e. the #
#         harness BEFORE this leg's patch, extracted to a scratch dir.        #
#   NEW   the worktree's patched harness, --cand-tau-p UNSET.                 #
#   CTRL  the same patched harness, --cand-tau-p set to the PLUMBING dose.    #
#                                                                             #
# ⛔ Run this BEFORE the freeze commit, while HEAD still predates the patch.   #
#    After the commit, pass --old-rev <the pre-patch sha> explicitly.         #
#                                                                             #
# ⚠️ src/ engine/ and the carc_rs wheel are byte-identical across the legs and #
#    are HELD CONSTANT (ONE-SRC / ONE-WHEEL). The variable is one file.       #
#                                                                             #
# ETA ~4-5 min total on the local box (3 legs x 12 games x k2x96).            #
#                                                                             #
# USAGE   ./run_gate.sh [--old-rev REV] [--seeds N] [--ctrl-tau 2.5]          #
# =========================================================================== #
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"

OLD_REV="HEAD"; SEEDS=12; CTRL_TAU=2.5
while [ $# -gt 0 ]; do
  case "$1" in
    --old-rev) OLD_REV="$2"; shift 2 ;;
    --seeds)   SEEDS="$2"; shift 2 ;;
    --ctrl-tau) CTRL_TAU="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"

# ⚠️ The venv is editable-installed against the MAIN tree. Every leg must resolve
# carcassonne_ai from THIS worktree, and ONE-SRC in the verdict is what proves it.
export PYTHONPATH="$REPO/src:$REPO/engine${PYTHONPATH:+:$PYTHONPATH}"

# ⚠️⚠️ THE OLD LEG NEEDS A MIRRORED TREE, NOT A LOOSE FILE. eval_fair_puct.py
# derives `REPO = Path(__file__).resolve().parent.parent.parent` and inserts
# REPO/src and REPO/scripts/level2 onto sys.path at import. A copy dropped in a
# flat scratch dir therefore computes a WRONG repo root — it fails outright on
# `import endgame_solver`, and anything it did not fail on would be a leg running
# with a silently different notion of the tree. So the scratch is a SYMLINK
# MIRROR: every sibling module, src/, engine/, level2/ and governance/ point at
# THIS worktree's real files, and the ONLY real file in it is the old harness.
SCRATCH="${TMPDIR:-/tmp}/taup_gate_$$"
mkdir -p "$SCRATCH/scripts/classical_search"
trap 'rm -rf "$SCRATCH"' EXIT
for d in src engine governance; do ln -s "$REPO/$d" "$SCRATCH/$d"; done
for d in level2 human_anchor measurement_infra; do
  ln -s "$REPO/scripts/$d" "$SCRATCH/scripts/$d"
done
for f in "$REPO"/scripts/classical_search/*.py; do
  ln -s "$f" "$SCRATCH/scripts/classical_search/$(basename "$f")"
done
rm -f "$SCRATCH/scripts/classical_search/eval_fair_puct.py"
git -C "$REPO" show "$OLD_REV:scripts/classical_search/eval_fair_puct.py" \
  > "$SCRATCH/scripts/classical_search/eval_fair_puct.py"
OLDMOD="$SCRATCH/scripts/classical_search/eval_fair_puct.py"
NEWMOD="$REPO/scripts/classical_search/eval_fair_puct.py"

if cmp -s "$OLDMOD" "$NEWMOD"; then
  echo "⛔ $OLD_REV's eval_fair_puct.py is IDENTICAL to the worktree's — there is" >&2
  echo "   no OLD leg to run. Pass --old-rev <a pre-patch sha>." >&2
  exit 2
fi

echo "== leg OLD  ($OLD_REV, --cand-tau-p unset) =="
"$PY" "$HERE/identity_fixture.py" --evalmod "$OLDMOD" \
      --seeds "$SEEDS" --out "$HERE/OLD.json"
echo "== leg NEW  (worktree, --cand-tau-p unset) =="
"$PY" "$HERE/identity_fixture.py" --evalmod "$NEWMOD" \
      --seeds "$SEEDS" --out "$HERE/NEW.json"
echo "== leg CTRL (worktree, --cand-tau-p $CTRL_TAU) =="
"$PY" "$HERE/identity_fixture.py" --evalmod "$NEWMOD" --cand-tau-p "$CTRL_TAU" \
      --seeds "$SEEDS" --out "$HERE/NEW_CTRL.json"

echo "== adjudication =="
"$PY" "$HERE/identity_diff.py" "$HERE/OLD.json" "$HERE/NEW.json" \
      "$HERE/NEW_CTRL.json" --out "$HERE/../TAUP_BITEXACT.json"
