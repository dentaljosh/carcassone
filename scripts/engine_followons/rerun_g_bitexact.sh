#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Re-run the banked §2 G-BITEXACT certificate against THIS branch.
#
# WHY THIS EXISTS
# ---------------
# `carc_core::tier1::best_by_virtual_score` is the function G-BITEXACT grades.
# Engine follow-on B (the tier1 meeple-phase decomposition hoist, 2026-08-30)
# EDITS it, so the banked 2026-08-29 PASS —
#
#     sha256_values_rust == 0c2e39fed5259320bf9891c221796be67b6805c057d98df02f426bc0e6b88e80
#     15,360 / 15,360 playouts bit-identical at legal_mask_cache = true
#
# — no longer certifies the deployed code. It must be RE-RUN and must reproduce
# that exact digest before the hoist merges to production use. That re-run is a
# MERGE PRECONDITION, not a nice-to-have.
#
# The full run needs an EXCLUSIVE box (240 legs x 32 worlds x 2 arms, 30
# workers). Beside a live eval round it is neither runnable nor readable. So
# this script has two modes:
#
#   smoke  — a deterministic prefix of the committed draw, sized to finish in
#            about a minute on a contended box. It cannot grant the gate; it
#            can only REFUSE it early. `--legs-limit` forces `pass:false` by
#            design and the script reads `smoke_pass` instead.
#   full   — the gate. Run it in the quiet window, with nothing else on the box.
#
# USAGE
#   scripts/engine_followons/rerun_g_bitexact.sh smoke [N_LEGS]   # default 6
#   scripts/engine_followons/rerun_g_bitexact.sh full             # THE GATE
#
# It builds a wheel from THIS worktree into a shadow dir and never touches the
# venv's installed `carc_rs` (house pattern, `GATES_DEFERRED.md` §2).
# ---------------------------------------------------------------------------
set -euo pipefail

MODE="${1:-smoke}"
SMOKE_LEGS="${2:-6}"

REPO=/home/doctor/projects/carcassone
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${G_BITEXACT_OUT:-/tmp/g_bitexact_followon_b}"
BANKED="$WT/measurement/tiearb2_stage2_20260817/BITEXACT.json"
RECORDS_ROOT=/mnt/c/carc-shared/tiearb2_20260816/main   # allow-path: local box
WORKERS="${G_BITEXACT_WORKERS:-30}"
# maturin shells out to `cargo`, which lives in the rustup dir and is not on a
# non-login PATH.
export PATH="$HOME/.cargo/bin:$PATH"

echo "[rerun] mode=$MODE worktree=$WT out=$OUT"
mkdir -p "$OUT/wheel" "$OUT/shadow"

# --- 0. preconditions ------------------------------------------------------
[[ -d "$RECORDS_ROOT" ]] || { echo "[rerun] FATAL: $RECORDS_ROOT not mounted"; exit 2; }
[[ -f "$BANKED" ]] || { echo "[rerun] FATAL: banked reference $BANKED missing"; exit 2; }

echo "[rerun] census:"; cat /proc/loadavg
ps -eo pcpu,args --sort=-pcpu | head -4 || true
if [[ "$MODE" == "full" ]]; then
  echo "[rerun] ⚠️  FULL MODE. The gate's criterion assumes an EXCLUSIVE box."
  echo "[rerun] ⚠️  If the census above shows an eval round or self-play, STOP."
fi

# --- 1. wheel from THIS worktree (site-packages untouched) ------------------
echo "[rerun] building carc_rs from $WT ..."
rm -f "$OUT"/wheel/carc_rs-*.whl
nice -n 19 "$REPO/.venv/bin/maturin" build --release \
  -m "$WT/rust/carc/carc-py/Cargo.toml" -o "$OUT/wheel" >"$OUT/maturin.log" 2>&1 \
  || { echo "[rerun] FATAL: maturin build failed, see $OUT/maturin.log"; tail -20 "$OUT/maturin.log"; exit 2; }

WHEEL=$(ls -t "$OUT"/wheel/carc_rs-*.whl | head -1)
rm -rf "$OUT/shadow"; mkdir -p "$OUT/shadow"
"$REPO/.venv/bin/python" -c \
  "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
  "$WHEEL" "$OUT/shadow"

# --- 2. provenance: the shadow carc_rs must be the BRANCH build -------------
echo "[rerun] provenance:"
PYTHONPATH="$OUT/shadow" "$REPO/.venv/bin/python" -c \
  "import carc_rs,sys; \
   p=carc_rs.__file__; \
   assert p.startswith('$OUT/shadow'), 'WRONG carc_rs: '+p; \
   print('  ', p, getattr(carc_rs,'__version__','?'))"

# --- 3. the run ------------------------------------------------------------
if [[ "$MODE" == "smoke" ]]; then
  JSON="$OUT/BITEXACT_smoke.json"
  PYTHONPATH="$OUT/shadow" OMP_NUM_THREADS=1 nice -n 19 "$REPO/.venv/bin/python" \
    "$WT/scripts/tiletie/verify_tier1_rust.py" \
    --workers "$WORKERS" --legs-limit "$SMOKE_LEGS" --out "$JSON"
  rc=$?
  echo "[rerun] smoke rc=$rc -> $JSON"
  exit $rc
fi

JSON="$OUT/BITEXACT_followon_b.json"
PYTHONPATH="$OUT/shadow" OMP_NUM_THREADS=1 nice -n 19 "$REPO/.venv/bin/python" \
  "$WT/scripts/tiletie/verify_tier1_rust.py" \
  --workers "$WORKERS" --out "$JSON" || true

# --- 4. adjudicate against the BANKED pass, key by key ---------------------
"$REPO/.venv/bin/python" - "$JSON" "$BANKED" <<'PY'
import json, sys
new = json.load(open(sys.argv[1]))
old = json.load(open(sys.argv[2]))
KEYS = ["pass","n_legs_found","n_playouts_compared","n_value_bit_identical",
        "n_value_mismatch","n_plies_identical","n_plies_mismatch",
        "n_seed_witness_ok","digests_equal","sha256_values_rust",
        "sha256_values_python"]
bad = [k for k in KEYS if new.get(k) != old.get(k)]
DIGEST = "0c2e39fed5259320bf9891c221796be67b6805c057d98df02f426bc0e6b88e80"
if new.get("sha256_values_rust") != DIGEST:
    bad.append("sha256_values_rust != the banked 0c2e39fe…")
if new.get("smoke"):
    bad.append("this JSON is a SMOKE run, not the gate")
print("G-BITEXACT RE-RUN:", "PASS" if not bad and new.get("pass") else f"FAIL on {bad}")
sys.exit(0 if (not bad and new.get("pass")) else 1)
PY
