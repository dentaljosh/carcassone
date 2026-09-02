#!/usr/bin/env bash
# =========================================================================== #
# THE GT-M1 CVaR-POOLING GOLDEN GATE — four legs + the adjudication.          #
#                                                                             #
#   OLD     the tree at --old-rev, extracted by `git archive`, running the     #
#           carc_rs ALREADY INSTALLED IN THE VENV (which predates GT-M1 and    #
#           is verified to have no `pool` getter). Flag unset.                 #
#   NEW     this worktree, running the FRESHLY BUILT wheel. Flag unset.        #
#   CVAR25  the same NEW tree+wheel at --cand-pool-mode cvar --alpha 0.25.     #
#   ALPHA1  the same NEW tree+wheel at alpha 1.0 — the EQUAL-WEIGHT arm.       #
#           ⚠️⚠️ NOT an identity control; see identity_diff.py's              #
#           ALPHA1-EQUALWEIGHT-ARM check and the census DEVIATIONS D-1.        #
#                                                                             #
# ⚠️⚠️ UNLIKE THE tau_p GATE, BOTH THE TREE AND THE WHEEL ARE SWUNG. GT-M1     #
#    touches rust/carc/carc-{core,py}, src/carcassonne_ai/{heuristic_prior_    #
#    mcts,rust_agent,champion_factory}.py AND scripts/classical_search/        #
#    eval_fair_puct.py, so a leg must be a coherent tree END TO END. That is   #
#    STRONGER than the tau_p precedent's one-file swing, not weaker.           #
#                                                                             #
# ⛔ THE NEW WHEEL IS NEVER INSTALLED INTO THE VENV. It is `pip install        #
#    --target`ed into a scratch dir and prepended to PYTHONPATH, because the   #
#    venv serves a live strength run. The OLD leg simply omits that prefix.    #
#                                                                             #
# ETA ~6-9 min total on a quiet local box (4 legs x 12 games x k4x96).         #
#                                                                             #
# USAGE   ./run_gate.sh [--old-rev REV] [--seeds N] [--wheel-dir DIR]          #
# =========================================================================== #
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"

OLD_REV="HEAD"; SEEDS=12
SCRATCH_ROOT="${CVAR_GATE_SCRATCH:-${TMPDIR:-/tmp}/cvar_gate_$$}"
WHEEL_DIR="${CVAR_WHEEL_DIR:-}"
# ⚠️ `--old-tree` / `--wheel-dir` exist because the gate may have to run on a box
# that is NOT the build box. The local box was saturated by a live band-spending
# round (`--arm-cap-secs 1800`, i.e. an added tenant can LOSE units, not merely
# slow them) when this gate was first run, so the trees and the wheel were built
# here and shipped to the idle LAPTOP — which is also the box the round's cells
# play on, so proving the gate there proves it where it matters. When both are
# supplied this script neither builds nor archives anything.
OLD_TREE_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --old-rev)    OLD_REV="$2"; shift 2 ;;
    --old-tree)   OLD_TREE_ARG="$2"; shift 2 ;;
    --seeds)      SEEDS="$2"; shift 2 ;;
    --wheel-dir)  WHEEL_DIR="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

PY="/home/doctor/projects/carcassone/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 2; }

mkdir -p "$SCRATCH_ROOT"
OLDTREE="$SCRATCH_ROOT/oldtree"

# --------------------------------------------------------------------------- #
# 0. THE NEW WHEEL — built from THIS worktree, installed to a scratch --target #
#    ⛔ NEVER into the venv: it serves a live strength run.                     #
# --------------------------------------------------------------------------- #
if [ -z "$WHEEL_DIR" ]; then
  WHEEL_DIR="$SCRATCH_ROOT/wheel"
  echo "== building carc_rs from this worktree =="
  # ⚠️ THE TOOLCHAIN PIN DOES NOT APPLY FROM THE REPO ROOT (docs/CLUSTER_OPS.md).
  # rustup resolves the toolchain from the CWD, and rust/carc/rust-toolchain.toml
  # is never seen from here — so it is forced explicitly and VERIFIED.
  export RUSTUP_TOOLCHAIN=1.96.0
  RUSTC_V="$(rustc --version)"
  case "$RUSTC_V" in
    "rustc 1.96.0"*) : ;;
    *) echo "⛔ toolchain is '$RUSTC_V', not 1.96.0 — bumping the pin invalidates" >&2
       echo "   the G0 bit-exactness evidence. Refusing." >&2; exit 2 ;;
  esac
  mkdir -p "$SCRATCH_ROOT/whl"
  nice -n 19 "$PY" -m maturin build --release \
      -m "$REPO/rust/carc/carc-py/Cargo.toml" -i "$PY" \
      --out "$SCRATCH_ROOT/whl" -j 6 >/dev/null
  "$PY" -m pip install --quiet --target "$WHEEL_DIR" --no-deps --upgrade \
      "$SCRATCH_ROOT"/whl/carc_rs-*.whl
fi
[ -d "$WHEEL_DIR/carc_rs" ] || { echo "⛔ no carc_rs in $WHEEL_DIR" >&2; exit 2; }

# --------------------------------------------------------------------------- #
# 1. THE OLD TREE — `git archive`, not a worktree.                             #
#    A registered worktree would mutate the repo's worktree list; an archive    #
#    is a pure read. Everything the fixture touches (src/, engine/, scripts/,   #
#    governance/) comes out of it, so the leg is a COHERENT tree rather than a  #
#    new file dropped beside old siblings.                                     #
# --------------------------------------------------------------------------- #
if [ -n "$OLD_TREE_ARG" ]; then
  OLDTREE="$(cd "$OLD_TREE_ARG" && pwd)"
  echo "== OLD tree supplied: $OLDTREE =="
elif [ ! -d "$OLDTREE" ]; then
  echo "== extracting OLD tree at $OLD_REV =="
  mkdir -p "$OLDTREE"
  git -C "$REPO" archive "$OLD_REV" src engine scripts governance \
    | tar -x -C "$OLDTREE"
fi
OLDMOD="$OLDTREE/scripts/classical_search/eval_fair_puct.py"
NEWMOD="$REPO/scripts/classical_search/eval_fair_puct.py"
[ -f "$OLDMOD" ] || { echo "⛔ no eval_fair_puct.py in the OLD tree" >&2; exit 2; }
if cmp -s "$OLDMOD" "$NEWMOD"; then
  echo "⛔ $OLD_REV's eval_fair_puct.py is IDENTICAL to the worktree's — there is" >&2
  echo "   no OLD leg to run. Pass --old-rev <a pre-patch sha>." >&2
  exit 2
fi

# ⛔ THE PRE-FLIGHT THAT MAKES `IDENTITY` MEAN SOMETHING: the venv's installed
# carc_rs must PREDATE GT-M1. If someone has already installed the new wheel
# fleet-wide, the OLD leg would silently run the NEW binary and IDENTITY would
# be comparing the change to itself.
"$PY" - <<'PYSTALE' || { echo "⛔ the OLD leg's wheel precondition FAILED" >&2; exit 2; }
import sys
import carc_rs
if hasattr(carc_rs.SearchConfigRs, "pool"):
    print("⛔⛔ the carc_rs INSTALLED IN THE VENV already has the `pool` getter, "
          "i.e. it is a POST-GT-M1 build. The OLD leg would run the NEW binary "
          "and IDENTITY would compare the change to itself. Point --old-rev at a "
          "box whose venv still carries the pre-change wheel, or uninstall.")
    sys.exit(1)
print("[pre-flight] the venv's carc_rs is PRE-GT-M1 (no `pool` getter) — OK")
PYSTALE

# --------------------------------------------------------------------------- #
# 2. THE FOUR LEGS                                                             #
# --------------------------------------------------------------------------- #
run_leg() {  # name tree evalmod wheel_prefix out [extra args...]
  local name="$1" tree="$2" mod="$3" wheel="$4" out="$5"; shift 5
  echo "== leg $name =="
  if [ -n "$wheel" ]; then
    PYTHONPATH="$wheel:$tree/src:$tree/engine" \
      nice -n 19 "$PY" "$HERE/identity_fixture.py" --tree "$tree" \
        --evalmod "$mod" --seeds "$SEEDS" --out "$out" "$@"
  else
    PYTHONPATH="$tree/src:$tree/engine" \
      nice -n 19 "$PY" "$HERE/identity_fixture.py" --tree "$tree" \
        --evalmod "$mod" --seeds "$SEEDS" --out "$out" "$@"
  fi
}

run_leg OLD    "$OLDTREE" "$OLDMOD" ""           "$HERE/OLD.json"
run_leg NEW    "$REPO"    "$NEWMOD" "$WHEEL_DIR" "$HERE/NEW.json"
run_leg CVAR25 "$REPO"    "$NEWMOD" "$WHEEL_DIR" "$HERE/NEW_CVAR25.json" \
        --cand-pool-mode cvar --cand-pool-alpha 0.25
run_leg ALPHA1 "$REPO"    "$NEWMOD" "$WHEEL_DIR" "$HERE/NEW_ALPHA1.json" \
        --cand-pool-mode cvar --cand-pool-alpha 1.0

echo "== adjudication =="
"$PY" "$HERE/identity_diff.py" "$HERE/OLD.json" "$HERE/NEW.json" \
      "$HERE/NEW_CVAR25.json" "$HERE/NEW_ALPHA1.json" \
      --out "$HERE/../CVAR_BITEXACT.json"
