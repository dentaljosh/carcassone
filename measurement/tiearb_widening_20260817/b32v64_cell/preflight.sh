#!/usr/bin/env bash
# =============================================================================
# b32v64_cell — PER-HOST PRE-FLIGHT. HARD BLOCKER. Run BEFORE game 1 ON EVERY
# BOX THAT PLAYS.
#
#   preflight.sh [LABEL]        LABEL defaults to FIRST; the smoke passes SMOKE
#
# A PARAMETERIZED SIBLING of `measurement/tiearb_widening_20260817/b64_cell/
# preflight.sh` (a SPENT, ADJUDICATED run — that file is READ here and NEVER
# edited). Everything it does, this does; the differences are named below.
#
#  (a) ⭐ IT RUNS THE TWO-SIDED CONTROL AT **BOTH** `B` VALUES — 64 AND 32,
#      in that order (HI then LO). `READ_RULE` §3 `G-J13` requires the control
#      *"at BOTH `B` values … on each host, before that host's game 1"*, and
#      `b64_cell/RULINGS_PREBLIND.md` RULING 2 makes the conjunct *"for EACH
#      host, BOTH `B` values appear across that host's witness records, each
#      with both booleans true."*
#
#  (b) ⭐ ONE WITNESS FILE PER HOST PER `B` —
#      `verdicts/PREFLIGHT_${HOST}_${LABEL}_B${B}.json`. That is RULING 4's
#      two-files-per-host shape (a scalar pinned path cannot carry two `B`
#      values in one file), and it is kept verbatim.
#
#  (c) ⭐ IT EMITS THE TWO BOOLEANS AT THE **PINNED** PATH —
#      `j13_witness.pick_changed` and `j13_witness.root_leaf_value_bits_unchanged`
#      — plus `j13_witness.B` and `expected.B`, BEFORE game 1. The probe
#      `measurement/tiearb2_stage2_20260817/preflight_tiearb.py` writes the two
#      booleans under `two_sided.*`; that file belongs to a SPENT, ADJUDICATED
#      run and is **not edited here** — this launcher POST-PROCESSES its output,
#      injecting the pinned keys and KEEPING `two_sided.*` for house
#      compatibility. The pinned path is authoritative.
#
#      ⭐⭐ AND IT NOW **ASSERTS** THE PINNED PATH RATHER THAN ONLY WRITING IT.
#      This closes `b64_cell/verdicts/READOUT_B64.md`'s LAST mismatch block —
#      the one unresolved residual of the B64 cell: *"RULING 2's pinned
#      addresses vs the known-good artefact … the B64 preflight emitter should
#      write the two booleans at the PINNED `j13_witness.*` path before game 1.
#      NOTED for the executor; the pair is not changed."* There the adjudicator
#      still had to FALL BACK to the older `two_sided.*` house shape. Here the
#      four pinned addresses are checked ON THIS HOST, BEFORE GAME 1, and an
#      ABSENT address FAILS — never coerced, never assumed (RULING 2's own
#      words: *"Absent `B` ⇒ FAIL"*).
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
RUN_DIR="$REPO/measurement/tiearb_widening_20260817/b32v64_cell"
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
for B in "$TIEARB_B_HI" "$TIEARB_B_LO"; do
  PF_NOW="$VERD/PREFLIGHT_${HOST}_${LABEL}_B${B}_$(date -u +%s).json"
  PF_OUT="$VERD/PREFLIGHT_${HOST}_${LABEL}_B${B}.json"
  log "--- G-J13 two-sided control  B=$B J=$TIEARB_J salt=$TIEARB_SALT eps=$TIEARB_EPS ---"
  # ⭐ THE PROVENANCE LINE, and it differs per B in THIS cell:
  #   B = 64 HAS been executed — b64_cell played 1,500 games at it and it is the
  #          DEPLOYED incumbent (governance/PRODUCTION.yaml::deploy.tiearb).
  #   B = 32 has NEVER been executed anywhere in a game — this cell is its first,
  #          and proving the arbiter is LIVE at the narrower width is the whole
  #          point of running the control at it.
  if [ "$B" = "$TIEARB_B_HI" ]; then
    log "⭐ B=$B HAS been executed (b64_cell, 1,500 games) and is the DEPLOYED incumbent"
  else
    log "⭐ B=$B has NEVER been executed anywhere in a game — this cell is its first"
  fi

  set +e
  PREFLIGHT_TIEARB_B="$B" \
  PREFLIGHT_TIEARB_J="$TIEARB_J" \
  PREFLIGHT_TIEARB_SALT="$TIEARB_SALT" \
  PREFLIGHT_TIEARB_EPS="$TIEARB_EPS" \
    nice -n "$NICE" "$PY" "$PF_PY" > "$PF_NOW" \
      2> "$LOGS/preflight_${HOST}_${LABEL}_B${B}.log"
  pfrc=$?
  set -e

  if [ ! -s "$PF_NOW" ]; then
    log "!!! PRE-FLIGHT PRODUCED NO VERDICT (rc=$pfrc) ON $HOST AT B=$B"
    log "!!!   stderr : $LOGS/preflight_${HOST}_${LABEL}_B${B}.log"
    { echo "utc $(ts)"; echo "NO VERDICT rc=$pfrc on $HOST at B=$B"; } \
      > "$RUN_DIR/FAILED_PREFLIGHT_${HOST}_B${B}"
    rc_all=13
    continue
  fi

  # ---- (c) THE PINNED PATH, PART 1 OF 2: THE INJECTION --------------------
  # TOOL: this launcher (b32v64_cell/preflight.sh), inline python.
  # ADDRESSES WRITTEN: j13_witness.B, j13_witness.pick_changed,
  #                    j13_witness.root_leaf_value_bits_unchanged  (expected.B
  #                    is the probe's own and is only CHECKED here).
  # RULING 2 pins `j13_witness.{B, pick_changed, root_leaf_value_bits_unchanged}`
  # and `expected.B`. The probe writes the two booleans under `two_sided.*`; it
  # is a SPENT run's file and is not edited, so they are injected here. ⚠️ The
  # injection COPIES, never invents: an absent boolean stays absent and the
  # assert below fails closed on it.
  #
  # ⛔ AND IT IS **NOT** GATED BEHIND THE PROBE'S AGGREGATE `all_preflight_pass`.
  # It runs whenever the probe produced a verdict at all. Gating it behind the
  # aggregate flag meant an UNRELATED failing row left the pinned keys unwritten
  # — the defect the injection exists to fix survived because something else
  # failed. (Observed on b64_cell's first real run: J13 passed at both B values
  # on both hosts and two pre-§13.1 TOOL sentinel rows failed, so nothing was
  # injected.)
  #
  # ⚠️ Carried from b64_cell VERBATIM IN BEHAVIOUR, including its failure mode:
  # a probe-vs-pinned `B` disagreement is FATAL and kills the script under
  # `set -e` (no sentinel) — that is a *probe emitting the wrong B*, which is a
  # broken instrument, not a run that may be retried.
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

  # ---- (c) THE PINNED PATH, PART 2 OF 2: THE ASSERT -----------------------
  # ⭐ THIS IS THE PARKED FIX. It closes the LAST mismatch block of
  # `b64_cell/verdicts/READOUT_B64.md` ("RULING 2's pinned addresses vs the
  # known-good artefact — ⚠️ RESIDUAL, reported for the emitter"), where the
  # adjudicator had to fall back to `two_sided.*` because nothing asserted the
  # pinned shape existed. It is asserted HERE, on THIS host, BEFORE game 1.
  #
  # TOOL: this launcher, inline python.  ADDRESSES READ (all four, strictly):
  #   j13_witness.B                                (int)
  #   expected.B                                   (int)
  #   j13_witness.pick_changed                     (bool)
  #   j13_witness.root_leaf_value_bits_unchanged   (bool)
  # HEALTHY RUN  -> all four present; both ints == $B; both booleans exactly
  #                 `true` (JSON true, i.e. python True — not 1, not "true").
  # FIRES        -> any of the four ABSENT, either int != $B, or either boolean
  #                 anything other than exactly true.
  # ⛔ ABSENT MUST FAIL. It is never coerced and never assumed (RULING 2).
  set +e
  PF_NOW="$PF_NOW" B="$B" "$PY" - <<'PYEOF'
import json, os, sys

MISSING = object()

def at(doc, path):
    cur = doc
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return MISSING
        cur = cur[k]
    return cur

p = os.environ["PF_NOW"]
B = int(os.environ["B"])
d = json.loads(open(p).read())

bad = []
for path in ("j13_witness.B", "expected.B"):
    v = at(d, path)
    if v is MISSING:
        bad.append(f"{path} ABSENT")
    elif v != B:
        bad.append(f"{path}={v!r} != {B}")
for path in ("j13_witness.pick_changed",
             "j13_witness.root_leaf_value_bits_unchanged"):
    v = at(d, path)
    if v is MISSING:
        bad.append(f"{path} ABSENT")
    elif v is not True:
        bad.append(f"{path}={v!r} is not exactly true")

d["pinned_address_assert"] = {
    "tool": "b32v64_cell/preflight.sh (the pinned-address assert)",
    "addresses": ["j13_witness.B", "expected.B", "j13_witness.pick_changed",
                  "j13_witness.root_leaf_value_bits_unchanged"],
    "B": B,
    "violations": bad,
    "ok": not bad,
    "why": ("closes the LAST mismatch block of b64_cell/verdicts/READOUT_B64.md "
            "— RULING 2 pins four addresses and, on b64_cell, the two booleans "
            "were only ever written under two_sided.* so the adjudicator had to "
            "fall back. They are ASSERTED here, before game 1. An ABSENT "
            "address FAILS: it is never coerced and never assumed."),
}
open(p, "w").write(json.dumps(d, indent=2, sort_keys=True) + "\n")

if bad:
    print("[preflight]   ⛔ PINNED ADDRESS ASSERT FAILED:")
    for b in bad:
        print(f"[preflight]     - {b}")
    sys.exit(1)
print("[preflight]   pinned addresses OK: j13_witness.B / expected.B = "
      f"{B}, pick_changed = true, root_leaf_value_bits_unchanged = true")
sys.exit(0)
PYEOF
  arc=$?
  set -e
  if [ "$arc" -ne 0 ]; then
    log "!!! PINNED ADDRESS ASSERT FAILED ON $HOST AT B=$B — the violating"
    log "!!! address(es) are NAMED above and in $PF_NOW::pinned_address_assert.violations"
    log "!!! (RULING 2: an ABSENT address FAILS — never coerced, never assumed.)"
    { echo "utc $(ts)"; echo "PINNED ADDRESS ASSERT FAILED on $HOST at B=$B"; \
      echo "see $PF_NOW::pinned_address_assert.violations"; } \
      > "$RUN_DIR/FAILED_PREFLIGHT_${HOST}_B${B}"
    cp -f "$RUN_DIR/FAILED_PREFLIGHT_${HOST}_B${B}" "$SHARE_RUN/" 2>/dev/null || true
    cp -f "$PF_NOW" "$SHARE_RUN/verdicts/" 2>/dev/null || true
    exit 14
  fi

  # ---- THE LAUNCHER'S OWN VERDICT LAYER -----------------------------------
  # ⭐ b64_cell/DESIGN.md §13.1's class — the unsatisfiable gate. The probe
  # carries two PRE-§13.1 sentinel rows that treat normal production values as
  # failures:
  #
  #   TOOL_rust_toolchain_is_pinned_and_real   reads RUSTUP_TOOLCHAIN, which is
  #       UNSET in production (`rust_agent.py:372` defaults it to "unpinned"), so
  #       it grades an env var's null instead of the RESOLVED rustc the box
  #       actually ran.
  #   TOOL_carc_rs_build_is_real_not_a_sentinel   treats "+rustcunpinned" as a
  #       sentinel when §13.1 rules it THE NORMAL PRODUCTION VALUE, which PASSES
  #       provided both boxes emit it byte-identically. That row is the exact
  #       defect §13.1 caught in the b64 pair's own G-TOOL.
  #
  # The probe belongs to a SPENT, ADJUDICATED run and is NEVER edited, and its
  # verdicts are never rewritten. Instead this launcher evaluates the PAIR'S OWN
  # RULED READING over the probe's RAW FIELDS and records its verdict — with the
  # citation — in its own block. Any OTHER failing row is a REAL failure and
  # still refuses.
  #
  # ⚠️ CITATION CHANGE vs b64_cell, and the reason. b64 cited §13.1 *plus*
  # `b64_cell/KNOWNGOOD_EVAL.json::rows.G-TOOL` as standing evidence. THIS CELL
  # HAS NO `KNOWNGOOD_EVAL.json` YET, so citing one would be a pointer to a file
  # nothing writes — the same disease as a check reading an address nothing
  # writes. The KNOWNGOOD half is DROPPED and only the ruling is cited, by the
  # path where it actually lives: `b64_cell/DESIGN.md §13.1` (this cell inherits
  # the class ruling; it does not restate it).
  set +e
  PF_NOW="$PF_NOW" B="$B" HOST="$HOST" "$PY" - <<'PYEOF'
import json, os, sys

SUPERSEDED = {
    "TOOL_rust_toolchain_is_pinned_and_real": (
        "reads RUSTUP_TOOLCHAIN, which is UNSET in production, instead of the "
        "RESOLVED rustc the box ran. The launcher re-evaluates it on "
        "toolchain.rustc."),
    "TOOL_carc_rs_build_is_real_not_a_sentinel": (
        "treats '+rustcunpinned' as a sentinel when b64_cell/DESIGN.md §13.1 "
        "rules it the NORMAL PRODUCTION VALUE, which PASSES provided both boxes "
        "emit it byte-identically. G-TOOL's conjunct is EQUALITY ACROSS BOXES "
        "and NOTHING ELSE."),
}
# ⚠️ b64_cell's citation had a second half — KNOWNGOOD_EVAL.json::rows.G-TOOL.
# DROPPED here: this cell has no KNOWNGOOD_EVAL.json, and a citation to a file
# nothing writes is a dead pointer. The class ruling itself is inherited and is
# cited by the path where it lives.
CITATION = ("b64_cell/DESIGN.md §13.1 (the unsatisfiable-gate class; G-TOOL's "
            "conjunct is equality of carc_rs_build across boxes and nothing "
            "else) — inherited by b32v64_cell, which does not restate it. "
            "(b64_cell/KNOWNGOOD_EVAL.json is deliberately NOT cited: this cell "
            "has no known-good evaluation of its own yet.)")

p = os.environ["PF_NOW"]
d = json.loads(open(p).read())
rows = {c.get("check"): c for c in (d.get("checks") or [])}
failed = sorted(k for k, c in rows.items() if not c.get("ok"))

# --- the pair's own ruled reading, over the probe's RAW fields --------------
tc = (d.get("toolchain") or {})
rustc = tc.get("rustc")
build = d.get("carc_rs_build")
resolved = {
    "rustc_resolved": rustc,
    "rustc_ok": bool(rustc) and str(rustc).startswith("rustc "),
    "carc_rs_build": build,
    "carc_rs_build_present": bool(build),
    "carc_rs_binary_sha": d.get("carc_rs_binary_sha"),
    "binary_sha_note": ("BOX-LOCAL — never compared across boxes; the .so is "
                        "not machine-reproducible"),
    "cross_box_conjunct": ("G-TOOL compares carc_rs_build ACROSS BOXES at "
                           "adjudication; this per-host verdict records the "
                           "value, it does not decide the cross-box question"),
}
superseded = [k for k in failed if k in SUPERSEDED]
real_failures = [k for k in failed if k not in SUPERSEDED]
# a superseded row is only superseded if the RULED reading actually holds
if superseded and not (resolved["rustc_ok"] and resolved["carc_rs_build_present"]):
    real_failures += superseded
    superseded = []

j13 = {k: bool(c.get("ok")) for k, c in rows.items() if k.startswith("J13")}
j13_ok = bool(j13) and all(j13.values())

d["launcher_verdict"] = {
    "layer": "b32v64_cell/preflight.sh — the launcher's OWN verdict over the "
             "probe's artifact. The probe belongs to a SPENT, ADJUDICATED run "
             "and is NEVER edited; its verdicts are never rewritten.",
    "host": os.environ["HOST"], "B": int(os.environ["B"]),
    "probe_all_preflight_pass": d.get("all_preflight_pass"),
    "j13_rows": j13, "j13_ok": j13_ok,
    "superseded_rows": {k: {"probe_ok": rows[k].get("ok"),
                            "probe_observed": rows[k].get("observed"),
                            "why_superseded": SUPERSEDED[k],
                            "citation": CITATION}
                        for k in superseded},
    "ruled_reading": resolved,
    "real_failures": real_failures,
    "verdict": "PASS" if (j13_ok and not real_failures) else "FAIL",
    "note": ("⛔ A superseded row is recorded WITH ITS CITATION, never deleted "
             "and never silently passed. Any row outside the superseded set "
             "still refuses."),
}
open(p, "w").write(json.dumps(d, indent=2, sort_keys=True) + "\n")

for k in superseded:
    print(f"[preflight]   SUPERSEDED {k} — {SUPERSEDED[k][:80]}…")
print(f"[preflight]   ruled reading: rustc={rustc!r} carc_rs_build={build!r}")
if not j13_ok:
    print(f"[preflight]   ⛔ J13 ROWS FAILED: "
          f"{sorted(k for k, v in j13.items() if not v)}")
if real_failures:
    print(f"[preflight]   ⛔ REAL FAILING ROWS: {real_failures}")
sys.exit(0 if (j13_ok and not real_failures) else 1)
PYEOF
  vrc=$?
  set -e
  if [ "$vrc" -ne 0 ]; then
    # ⚠️ NAME THE ROWS THAT ACTUALLY FAILED. The old message convicted G-J13 on
    # every nonzero rc — and on b64_cell's first real run J13 had PASSED at both
    # B values on both hosts while two TOOL sentinel rows failed. A log that
    # convicts the wrong gate is how a wrong cause survives into a close-out.
    log "!!! PRE-FLIGHT REFUSED ON $HOST AT B=$B — see the rows named above"
    log "!!!   verdict: $PF_NOW  (launcher_verdict.real_failures / .j13_rows)"
    log "!!!   stderr : $LOGS/preflight_${HOST}_${LABEL}_B${B}.log"
    log "!!! ⚠️ This refusal names the FAILING ROWS. It does NOT attribute the"
    log "!!! failure to G-J13 unless a J13 row is among them."
    { echo "utc $(ts)"; echo "PRE-FLIGHT REFUSED on $HOST at B=$B"; \
      echo "see $PF_NOW::launcher_verdict"; } \
      > "$RUN_DIR/FAILED_PREFLIGHT_${HOST}_B${B}"
    cp -f "$RUN_DIR/FAILED_PREFLIGHT_${HOST}_B${B}" "$SHARE_RUN/" 2>/dev/null || true
    cp -f "$PF_NOW" "$SHARE_RUN/verdicts/" 2>/dev/null || true
    rc_all=13
    continue
  fi
  rm -f "$RUN_DIR/FAILED_PREFLIGHT_${HOST}_B${B}" \
        "$SHARE_RUN/FAILED_PREFLIGHT_${HOST}_B${B}" 2>/dev/null || true

  [ -f "$PF_OUT" ] || cp "$PF_NOW" "$PF_OUT"
  cp -f "$PF_NOW" "$SHARE_RUN/verdicts/" 2>/dev/null || true
  cp -f "$PF_OUT" "$SHARE_RUN/verdicts/" 2>/dev/null || true
  log "G-J13 PASS on $HOST at B=$B -> $PF_NOW (gate witness: $PF_OUT)"
done

if [ "$rc_all" -ne 0 ]; then
  log "!!! one or more B values FAILED the two-sided control — REFUSING TO LAUNCH"
  exit "$rc_all"
fi

log "G-J13 PASS on $HOST at BOTH B values ($TIEARB_B_HI and $TIEARB_B_LO)"
log "⚠️ ADJUDICATES NOTHING. No game played, no strength number read."
exit 0
