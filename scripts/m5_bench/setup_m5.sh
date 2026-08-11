#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_m5.sh — prepare this directory to run bench_champion.py.
#
# Works on macOS (Apple silicon, the target) and on Linux (where it is used to
# verify the same code before shipping). Creates a venv NEXT TO this script and
# installs exactly what the champion's play path needs:
#
#     numpy   pyyaml            <- the only third-party imports in the bundle
#                                  (android/tools/sync_python.py ALLOWED_EXTERNAL)
#
# Then, OPTIONALLY, builds the two Cython fast paths natively for this arch. That
# step is allowed to fail: both call sites in the library catch ImportError and
# fall back to pure Python, so a compiler-less machine still produces a CORRECT
# (just slower -- measured 4.5x per decision on the 5900XT at k1x32, same
# positions both ways) measurement. bench_champion.py records which path
# actually bound as `cython.leaf_active` in its JSON output, so the two regimes
# can never be confused after the fact.
#
#   ./setup_m5.sh              # venv + deps + try the Cython build
#   ./setup_m5.sh --no-cython  # venv + deps only (pure-Python leaf)
#   ./setup_m5.sh --python /opt/homebrew/bin/python3.12
#
# Idempotent: re-running reuses the venv and rebuilds the extensions.
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="$HERE/bundle"
VENV="$HERE/.venv"
PY_BIN=""
WANT_CYTHON=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-cython) WANT_CYTHON=0; shift ;;
    --python)    PY_BIN="$2"; shift 2 ;;
    -h|--help)   sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "setup_m5: unknown argument $1" >&2; exit 2 ;;
  esac
done

echo "== setup_m5 =="
echo "   dir    : $HERE"
uname -srm

# --------------------------------------------------------------------------
# 1. Interpreter — needs >= 3.10 (the bundle uses `X | Y` unions and match-free
#    3.10 syntax throughout; 3.9 fails at import, not at run time).
# --------------------------------------------------------------------------
if [[ -z "$PY_BIN" ]]; then
  for cand in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then PY_BIN="$(command -v "$cand")"; break; fi
  done
fi
if [[ -z "$PY_BIN" ]]; then
  echo "setup_m5: FATAL — no python3 found on PATH." >&2
  echo "  macOS: install one with   brew install python@3.12" >&2
  exit 1
fi

PY_VER="$("$PY_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "   python : $PY_BIN ($PY_VER)"
if ! "$PY_BIN" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)'; then
  echo "setup_m5: FATAL — python $PY_VER is too old; the bundle needs >= 3.10." >&2
  echo "  macOS: brew install python@3.12  then re-run with --python \$(brew --prefix)/bin/python3.12" >&2
  exit 1
fi

# --------------------------------------------------------------------------
# 2. venv + the two runtime deps.
#    Deliberately a FRESH venv, not the system interpreter: on a machine that
#    also has the repo checked out, an editable `carcassonne_ai` install would
#    shadow the bundle and we would silently bench the wrong tree.
#    (bench_champion.bind_bundle asserts against exactly that, and would abort.)
# --------------------------------------------------------------------------
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "-- creating venv at $VENV"
  "$PY_BIN" -m venv "$VENV"
else
  echo "-- reusing venv at $VENV"
fi
VPY="$VENV/bin/python"

"$VPY" -m pip install --quiet --upgrade pip setuptools wheel
echo "-- installing runtime deps (numpy, pyyaml)"
"$VPY" -m pip install --quiet numpy pyyaml

# --------------------------------------------------------------------------
# 3. OPTIONAL: native Cython build of the leaf + board encoder.
#    Non-fatal by design. `set -e` is suspended around it.
# --------------------------------------------------------------------------
CY_STATUS="skipped"
if [[ "$WANT_CYTHON" -eq 1 ]]; then
  echo "-- attempting native Cython build (optional)"
  set +e
  "$VPY" -m pip install --quiet cython
  CY_PIP=$?
  if [[ $CY_PIP -ne 0 ]]; then
    CY_STATUS="failed: pip install cython"
  else
    ( cd "$BUNDLE" && "$VPY" setup_cy.py build_ext --inplace ) >"$HERE/cython_build.log" 2>&1
    if [[ $? -eq 0 ]]; then
      CY_STATUS="built"
    else
      CY_STATUS="failed: compile (see $HERE/cython_build.log)"
    fi
  fi
  set -e
  echo "   cython : $CY_STATUS"
  if [[ "$CY_STATUS" != "built" ]]; then
    echo "   (this is OK — the pure-Python leaf is correct, just ~4.5x slower per decision."
    echo "    On macOS a compiler needs:  xcode-select --install )"
  fi
fi

# --------------------------------------------------------------------------
# 4. Prove the bundle imports standalone and report which leaf path bound.
#    PYTHONPATH is cleared: the bundle must stand on its own.
# --------------------------------------------------------------------------
echo "-- verifying the bundle imports standalone"
env -u PYTHONPATH "$VPY" - "$BUNDLE" <<'PYEOF'
import os, sys
from pathlib import Path

bundle = Path(sys.argv[1]).resolve()
# The production leaf env, byte-identical to android_bridge.PROD_ENV. MUST be set
# before carcassonne_ai is imported: DEFAULT_CONFIG freezes at import time.
for k, v in {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}.items():
    os.environ.setdefault(k, v)

sys.path.insert(0, str(bundle))
import random
import carcassonne_ai
got = Path(carcassonne_ai.__file__).resolve()
assert bundle in got.parents, f"imported {got}, not the bundle {bundle}"

from carcassonne_ai import champion_factory, flat_leaf
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import virtual_score_v2

champion_factory.PRODUCTION_YAML = bundle / "carcassonne_ai" / "data" / "PRODUCTION.yaml"
spec = champion_factory.load_production_spec()

random.seed(0)
board = Game().get_init_board()
virtual_score_v2(board.state, 0, None)          # fires the lazy cython bind
cy = bool(flat_leaf._CY_FLAT_V2) and bool(flat_leaf._CY_SUPPORTS_CURVE)

# The real proof: build the champion with verify=True. The factory checks the leaf's
# curve VALUES and OUTPUTS on real boards plus three hash dialects, and RAISES on any
# mismatch — so this line succeeding means the bundle runs the champion of record.
agent = champion_factory.make_production_champion(
    "fair", game=Game(enable_legal_moves_cache=True), seed=0,
    sims=8, k_dets=1, exact_endgame=True, verify=True)

print(f"   OK  champion  : {spec.champion_id}")
print(f"   OK  leaf hash : {agent.manifest['leaf_hashes']['harness_leaf_hash']}")
print(f"   OK  budget    : YAML k{spec.k_dets}x{spec.sims_per_det}")
print(f"   OK  leaf path : {'CYTHON' if cy else 'PURE PYTHON'}")
PYEOF

echo
echo "== setup_m5 done =="
echo "   cython build : $CY_STATUS"
echo
echo "Next (smoke first, ~1-2 min):"
echo "   $VENV/bin/python $HERE/bench_champion.py --budgets k1x32"
echo "Then the full ladder:"
echo "   $VENV/bin/python $HERE/bench_champion.py"
