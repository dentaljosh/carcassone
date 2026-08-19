#!/usr/bin/env bash
# =============================================================================
# b64_cell — PER-HOST PRE-FLIGHT. HARD BLOCKER. Run BEFORE game 1 ON EVERY BOX
# THAT PLAYS.
#
#   preflight.sh [LABEL]        LABEL defaults to FIRST; the smoke passes SMOKE
#
# Adapted from `measurement/jcz_tiearb_20260817/preflight.sh` (the closest
# precedent: per-host FIRST.json emission) with TWO REQUIRED CHANGES, both of
# them from this pair's own text:
#
#  (a) ⭐ IT RUNS THE TWO-SIDED CONTROL AT **BOTH** `B` VALUES — 64 AND 16.
#      `READ_RULE` §3 `G-J13` requires the control *"at BOTH `B` values … on each
#      host, before that host's game 1"*, and `RULINGS_PREBLIND.md` RULING 2
#      makes the conjunct *"for EACH host, BOTH `B ∈ {64, 16}` appear across that
#      host's witness records, each with both booleans true."* The jcz precedent
#      runs a single `$TIEARB_B`. ⚠️ **A `B` = 64 control has never been executed
#      anywhere** — this is its first run, and proving the arbiter is LIVE at the
#      widened width is the whole point of the gate.
#
#  (b) ⭐ IT EMITS THE TWO BOOLEANS AT THE **PINNED** PATH —
#      `j13_witness.pick_changed` and `j13_witness.root_leaf_value_bits_unchanged`
#      (RULING 2; the adjudicator reads exactly those, `analyze_b64_cell.py`
#      `PREFLIGHT_CHANGED_PATH` / `PREFLIGHT_UNCHANGED_PATH`). The probe
#      `measurement/tiearb2_stage2_20260817/preflight_tiearb.py` writes them
#      under `two_sided.*`; that file belongs to a SPENT, ADJUDICATED run and is
#      **not edited here** — this launcher POST-PROCESSES its output, injecting
#      the pinned keys and KEEPING `two_sided.*` for house compatibility. The
#      pinned path is authoritative.
#
# ⚠️ ORDERING, AND IT IS LOAD-BEARING. The pre-flight MUST be generated AFTER any
#   wheel rebuild on that host and BEFORE that host's detached launch. Stage 2
#   rebuilt-then-launched with no pre-flight step, so HEAD moved between the
#   pre-flight and the manifest on EVERY healthy run and `G-TOOL` was
#   unsatisfiable by construction. That cost Stage 2 an adjudication.
#
# ⚠️ A NON-INTERACTIVE ssh shell does NOT get rustup on PATH. `$HOME/.cargo/env`
#   is sourced explicitly so the `rustc` witness is a version string on both
#   hosts and not an error string on one — which would read as a cross-box
#   toolchain difference that is not there.
#
# Exits NONZERO on any failure. ADJUDICATES NOTHING, plays no game, reads no
# strength number.
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$HERE/WORKERS.conf"

LABEL="${1:-FIRST}"
case "$LABEL" in
  FIRST|SMOKE) ;;
  *) echo "FATAL: LABEL must be FIRST or SMOKE, got '$LABEL'" >&2; exit 2 ;;
esac

HOST="$(hostname)"
case "$HOST" in
  *laptop*) SHARE="$SHARE_REMOTE"; REPO="$REPO_REMOTE"; W_BOX="$W_LAPTOP" ;;
  *)        SHARE="$SHARE_LOCAL";  REPO="$REPO_LOCAL";  W_BOX="$W_LOCAL" ;;
esac
PY="$REPO/.venv/bin/python"
PF_PY="$REPO/measurement/tiearb2_stage2_20260817/preflight_tiearb.py"
RUN_DIR="$REPO/measurement/tiearb_widening_20260817/b64_cell"
SHARE_RUN="$SHARE/$RUN_ID"
VERD="$RUN_DIR/verdicts"
LOGS="$RUN_DIR/logs"
mkdir -p "$VERD" "$LOGS" "$SHARE_RUN/verdicts"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[preflight $(ts) $HOST] $*"; }

log "host=$HOST share=$SHARE_RUN label=$LABEL W_BOX=$W_BOX blind_commit=$BLIND_COMMIT"
[ -x "$PY" ]    || { log "FATAL: no venv python at $PY"; exit 1; }
[ -f "$PF_PY" ] || { log "FATAL: probe missing at $PF_PY (is this box bundle-synced?)"; exit 1; }

if [ -f "$HOME/.cargo/env" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
fi
PATH="$HOME/.cargo/bin:$PATH"; export PATH

# The same leaf/rules env the cells run under — the probe must resolve the
# champion exactly as the cells will, or it is a weaker witness.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1
export CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
[ -n "$RUST_TOOLCHAIN" ] && export RUSTUP_TOOLCHAIN="$RUST_TOOLCHAIN"

# ==========================================================================
# `G-J13` — the TWO-SIDED positive control, AT BOTH `B` VALUES, on THIS host.
# The FIRST attempt's verdict is the gate witness and is NEVER overwritten by a
# resume (Stage-2 pattern): every attempt writes its own timestamped verdict and
# only the first is promoted to the name the gate reads.
# ==========================================================================
rc_all=0
for B in "$TIEARB_B_WIDE" "$TIEARB_B_NARROW"; do
  PF_NOW="$VERD/PREFLIGHT_${HOST}_${LABEL}_B${B}_$(date -u +%s).json"
  PF_OUT="$VERD/PREFLIGHT_${HOST}_${LABEL}_B${B}.json"
  log "--- G-J13 two-sided control  B=$B J=$TIEARB_J salt=$TIEARB_SALT eps=$TIEARB_EPS ---"
  [ "$B" = "$TIEARB_B_WIDE" ] && log "⭐ B=$B has NEVER been executed anywhere — this is its first run"

  set +e
  PREFLIGHT_TIEARB_B="$B" \
  PREFLIGHT_TIEARB_J="$TIEARB_J" \
  PREFLIGHT_TIEARB_SALT="$TIEARB_SALT" \
  PREFLIGHT_TIEARB_EPS="$TIEARB_EPS" \
    nice -n "$NICE" "$PY" "$PF_PY" > "$PF_NOW" \
      2> "$LOGS/preflight_${HOST}_${LABEL}_B${B}.log"
  pfrc=$?
  set -e

  if [ "$pfrc" -ne 0 ]; then
    log "!!! G-J13 PRE-FLIGHT FAILED (rc=$pfrc) ON $HOST AT B=$B"
    log "!!!   verdict: $PF_NOW"
    log "!!!   stderr : $LOGS/preflight_${HOST}_${LABEL}_B${B}.log"
    log "!!! REFUSING TO LAUNCH. A dead arbitration surface grades a perfect"
    log "!!! champion-vs-champion null wearing the shape of a real cell, and NO"
    log "!!! leaf-hash gate on this surface could ever detect it (the arbiter's"
    log "!!! knobs live on SearchConfig, not LeafConfig — no leaf hash moves)."
    { echo "utc $(ts)"; echo "G-J13 PRE-FLIGHT FAILED rc=$pfrc on $HOST at B=$B";
      echo "see $PF_NOW"; } > "$RUN_DIR/FAILED_PREFLIGHT_${HOST}_B${B}"
    cp -f "$RUN_DIR/FAILED_PREFLIGHT_${HOST}_B${B}" "$SHARE_RUN/" 2>/dev/null || true
    cp -f "$PF_NOW" "$SHARE_RUN/verdicts/" 2>/dev/null || true
    rc_all=13
    continue
  fi

  # ---- (b) THE PINNED PATH ------------------------------------------------
  # RULING 2 pins `j13_witness.{B, pick_changed, root_leaf_value_bits_unchanged}`
  # and `expected.B`. The probe writes the two booleans under `two_sided.*`; it
  # is a SPENT run's file and is not edited, so they are injected here. ⚠️ The
  # injection COPIES, never invents: an absent boolean stays absent and the gate
  # fails closed on it.
  PF_NOW="$PF_NOW" B="$B" "$PY" - <<'PYEOF'
import json, os, sys
p = os.environ["PF_NOW"]
B = int(os.environ["B"])
d = json.loads(open(p).read())
w = d.setdefault("j13_witness", {})
ts_block = d.get("two_sided") or {}
# B is authoritative from the probe's own witness; assert rather than overwrite
if w.get("B") is None:
    w["B"] = B
if w.get("B") != B:
    sys.exit(f"FATAL: probe emitted j13_witness.B={w.get('B')!r}, expected {B}")
if "pick_changed" in ts_block:
    w["pick_changed"] = ts_block["pick_changed"]
if "root_leaf_value_bits_unchanged" in ts_block:
    w["root_leaf_value_bits_unchanged"] = ts_block["root_leaf_value_bits_unchanged"]
exp = d.setdefault("expected", {})
if exp.get("B") != B:
    sys.exit(f"FATAL: expected.B={exp.get('B')!r} != {B}")
d["pinned_addresses_note"] = (
    "RULING 2 (b64_cell/RULINGS_PREBLIND.md): the adjudicator reads "
    "j13_witness.B / expected.B and the two booleans at j13_witness.*. "
    "two_sided.* is kept for house compatibility; the pinned path is "
    "authoritative. An ABSENT B FAILS — it is never assumed.")
open(p, "w").write(json.dumps(d, indent=2, sort_keys=True) + "\n")
PYEOF

  # fail closed if either pinned boolean is missing or not true
  PF_NOW="$PF_NOW" "$PY" - <<'PYEOF' || { log "!!! G-J13 pinned witness NOT satisfied"; exit 13; }
import json, os, sys
w = json.loads(open(os.environ["PF_NOW"]).read()).get("j13_witness") or {}
ok = (w.get("pick_changed") is True
      and w.get("root_leaf_value_bits_unchanged") is True)
sys.exit(0 if ok else 1)
PYEOF

  [ -f "$PF_OUT" ] || cp "$PF_NOW" "$PF_OUT"
  cp -f "$PF_NOW" "$SHARE_RUN/verdicts/" 2>/dev/null || true
  cp -f "$PF_OUT" "$SHARE_RUN/verdicts/" 2>/dev/null || true
  log "G-J13 PASS on $HOST at B=$B -> $PF_NOW (gate witness: $PF_OUT)"
done

if [ "$rc_all" -ne 0 ]; then
  log "!!! one or more B values FAILED the two-sided control — REFUSING TO LAUNCH"
  exit "$rc_all"
fi

log "G-J13 PASS on $HOST at BOTH B values ($TIEARB_B_WIDE and $TIEARB_B_NARROW)"
log "⚠️ ADJUDICATES NOTHING. No game played, no strength number read."
exit 0
