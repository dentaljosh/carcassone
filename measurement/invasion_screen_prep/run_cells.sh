#!/usr/bin/env bash
# =============================================================================
# run_cells.sh -- INVASION-RISK TERM FAMILY, ROUND-1 SCREEN AT 2752. LAUNCHER.
#
# FOUR cells, run in this order (cheapest-informative-first, DESIGN.md SS6.4):
#
#   IDENT  explicit weight-0 invasion config vs absent    200 decks /  400 games
#   A_MID  invasion_beta       = 0.12                     400 decks /  800 games
#   B_MID  invasion_alpha      = 0.09 @ alpha_cap 11.0    400 decks /  800 games
#   D_MID  invasion_delta_farm = 0.12                     400 decks /  800 games
#
# Every cell: candidate = champion curve125 leaf PLUS one invasion knob; opponent
# = the PLAIN champion curve125 leaf; k4x688 = 2752 total sims BOTH sides; rust
# BOTH sides; fixed_v1 + R9; exact-K 2 marginalized; tie-arbiter OFF both sides;
# deck-paired; band 151000000000, each cell on its OWN DISJOINT deck range.
#
#   run_cells.sh [--dry-run] [--smoke] [--only CELL] [--band SEED_START]
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
# instrument at freeze). A co-tenant can move WALL CLOCK and nothing else.
# So the process census below is ADVISORY and this cell MAY run beside e.g.
# scripts/rustport/reconcile_exact_solver.py --workers 1. DESIGN.md SS6.3 carries
# the full sensitivity-class argument.
# ⚠️ THE EXCEPTION IS RAM, WHICH IS A HARD, FAIL-CLOSED CHECK: a WSL guest OOM
# tears down the WHOLE VM, not one worker (reference_wsl2_host_memory_teardown).
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
# in-flight IDENT pre-check imports this, so it CANNOT drift from the
# adjudicator's G-IDENT.
LIB="$DIR/screen_lib.py"
[ -f "$LIB" ] || { echo "FATAL: screen_lib.py missing at '$LIB'" >&2; exit 2; }
ADJ="$DIR/analyze_screen.py"

LOGS="$DIR/logs"
OUT="$REPO/$OUT_SUBDIR"
CODE_PATHS=(src engine scripts rust tests pyproject.toml setup.py)

# ---------------------------------------------------------------------------
# R9. Exported BEFORE anything can import carcassonne_ai. `fixed_v1` EXPECTS
# this and CANNOT apply it itself: import-time farm derivation + a Rust OnceLock.
# Without it every manifest reads rules_profile.r9_env_ok == false and every cell
# is U-UNREADABLE on G-RULES.
# ---------------------------------------------------------------------------
export CARCASSONNE_FIX_R9=1

# ⚠️ DELIBERATELY NOT EXPORTED: CARCASSONNE_V29_MEEPLE_CURVE. The champion leaf is
# injected IN-PROCESS on the candidate side via --cand-leaf-json and on the
# opponent side by the harness's own _curve125_leaf_cfg(). Exporting the curve
# would move the harness's env DEFAULT_CONFIG, which _assert_rung_is_ruler
# refuses -- and would silently change what "the champion" means.

DRY=0; SMOKE=0; ONLY=""; BAND_ARG=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --smoke)   SMOKE=1 ;;
    --only)    ONLY="${2:?--only needs a cell name}"; shift ;;
    --band)    BAND_ARG="${2:?--band needs a seed start}"; shift ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

# --band may only CONFIRM the pair's band, never shadow it.
if [ -n "$BAND_ARG" ] && [ "$BAND_ARG" != "$BAND" ]; then
  echo "FATAL: --band $BAND_ARG disagrees with the pair's BAND=$BAND." >&2
  echo "FATAL: this launcher never accepts a different band for a real cell --" >&2
  echo "FATAL: if the band must change, the PAIR changes (DESIGN.md SS5 + BAND_CLAIM.json)." >&2
  exit 2
fi

HOST="$(hostname)"
ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[invscreen $(ts) $HOST] $*"; }

# --------------------------------------------------------------------------- #
# THE CELL TABLE. ⚠️ Every field here is CROSS-CHECKED against screen_lib.py by  #
# cells_from_lib() below before any real game runs, so this shell cannot        #
# silently disagree with the bar library the adjudicator uses.                  #
#   name | seed_start | n_decks | n_games | out_subdir | leaf_json | drift      #
# --------------------------------------------------------------------------- #
CELL_NAMES=(IDENT A_MID B_MID D_MID)
declare -A CELL_SEED=( [IDENT]=151000000000 [A_MID]=151000000200 [B_MID]=151000000600 [D_MID]=151000001000 )
declare -A CELL_DECKS=( [IDENT]=200 [A_MID]=400 [B_MID]=400 [D_MID]=400 )
declare -A CELL_GAMES=( [IDENT]=400 [A_MID]=800 [B_MID]=800 [D_MID]=800 )
declare -A CELL_SUB=(  [IDENT]=ident [A_MID]=a_mid [B_MID]=b_mid [D_MID]=d_mid )
declare -A CELL_LEAF=( [IDENT]=leaf_ident.json [A_MID]=leaf_a_mid.json
                       [B_MID]=leaf_b_mid.json [D_MID]=leaf_d_mid.json )
# ⚠️ THE DRIFT-FLAG ASYMMETRY IS LOAD-BEARING, NOT AN OVERSIGHT (DESIGN.md SS2.2).
# _assert_netprior_leaf refuses a candidate whose leaf hash != a36d2e15a3b3d71d.
# A nonzero invasion weight MOVES that hash by design, so A/B/D need the flag.
# An explicit-ZERO invasion config hashes AS THE CHAMPION (it IS the champion
# leaf bit-for-bit, SHAPES.md SS6), so IDENT passes the STRICT assertion -- and
# withholding the flag there turns the harness's own check into a free extra
# gate. G-LEAF(c) adjudicates both directions.
declare -A CELL_DRIFT=( [IDENT]=0 [A_MID]=1 [B_MID]=1 [D_MID]=1 )
declare -A CELL_HASH=( [IDENT]=$CAND_LEAF_HASH_IDENT [A_MID]=$CAND_LEAF_HASH_A_MID
                       [B_MID]=$CAND_LEAF_HASH_B_MID [D_MID]=$CAND_LEAF_HASH_D_MID )

cell_out() { echo "$OUT/${CELL_SUB[$1]}"; }

# --------------------------------------------------------------------------- #
# ARGV. The SINGLE experimental axis WITHIN a cell is --cand-leaf-json (the      #
# candidate's invasion knob); the ONLY axis ACROSS cells is which knob.          #
# ⛔ NO --cand-tiearb-* FLAG ANYWHERE. The harness default is disarmed and the    #
# opponent side has no arming flag at all (verified in source).                  #
# --------------------------------------------------------------------------- #
build_argv() {   # $1=cell  $2=n_games  $3=seed_start  $4=workers  $5=out_subdir  $6=with-stamp|no-stamp
  local c="$1" n="$2" seed="$3" w="$4" sub="$5" stamp="${6:-with-stamp}"
  ARGV=(nice -n "$NICE" "$PY" -u "$HARNESS"
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
        --claim-host "invscreen-$c-$HOST"
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
# cross-checked field by field. A launcher that disagrees with the pair is a   #
# launcher defect; the pair does not move.                                     #
# --------------------------------------------------------------------------- #
require_table_agrees() {
  CARC_LIB="$LIB" CARC_BAND="$BAND" \
  CARC_TABLE="$(for c in "${CELL_NAMES[@]}"; do
                  printf '%s|%s|%s|%s|%s|%s|%s\n' "$c" "${CELL_SEED[$c]}" "${CELL_DECKS[$c]}" \
                    "${CELL_GAMES[$c]}" "${CELL_SUB[$c]}" "${CELL_DRIFT[$c]}" "${CELL_HASH[$c]}"
                done)" \
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
                             ("cand_hash",  r[6],      c.cand_leaf_hash)):
        if got != want:
            print(f"[table] !!! {name}.{label}: launcher {got!r} != screen_lib {want!r}"); ok = False
    print(f"[table] {name}: seeds {c.seed_start}..{c.seed_start + c.n_decks - 1} "
          f"({c.n_decks} decks / {c.n_games} games) drift={int(bool(c.allow_leaf_hash_drift))} "
          f"hash={c.cand_leaf_hash}")
# Ranges must be DISJOINT (DESIGN.md SS5.1) -- the property G-DECKS gates on.
spans = sorted((c.seed_start, c.seed_start + c.n_decks - 1, c.name) for c in L.CELLS)
for (s0, e0, n0), (s1, e1, n1) in zip(spans, spans[1:]):
    if s1 <= e0:
        print(f"[table] !!! ranges OVERLAP: {n0} {s0}..{e0} vs {n1} {s1}..{e1}"); ok = False
print(f"[table] cell ranges disjoint: {spans[0][0]}..{spans[-1][1]}")
sys.exit(0 if ok else 1)
TEOF
  log "[preflight] cell table agrees with screen_lib.py"
}

# --------------------------------------------------------------------------- #
# (2) ⛔ THE WHEEL. THE PRECONDITION UNIQUE TO THIS PAIR (DESIGN.md SS7).       #
#                                                                              #
# rust_agent.leaf_config_rs forwards the invasion knobs as CONDITIONAL kwargs,  #
# so a carc_rs build predating the family serves every default-off (champion)   #
# config UNCHANGED AND SILENTLY. That is the right fail-closed design, and it   #
# is also why a stale wheel is this pair's worst failure mode: a stale-wheel    #
# IDENT cell would PASS, and only a TypeError on the first A/B/D game would     #
# reveal it -- after 8 core-h. So we do not probe with hasattr; we perform the  #
# ACTUAL NONZERO FORWARD, in a CHILD process, on the real cell configs.         #
# --------------------------------------------------------------------------- #
preflight_wheel() {
  CARC_REPO="$REPO" CARC_DIR="$DIR" CARC_LIB="$LIB" \
  "$PY" - <<'WEOF' || { log "!!! FATAL: carc_rs WHEEL PRE-FLIGHT FAILED -- see above. No game runs."; exit 4; }
import dataclasses as dc, importlib.util, json, os, sys, time
repo = os.environ["CARC_REPO"]; d = os.environ["CARC_DIR"]
sys.path.insert(0, os.path.join(repo, "src"))
sys.path.insert(0, os.path.join(repo, "scripts", "classical_search"))

REBUILD = ("    maturin build --release -m rust/carc/carc-py/Cargo.toml -o <wheeldir>\n"
           "    .venv/bin/pip install --force-reinstall --no-deps <wheeldir>/carc_rs-*.whl")

import carcassonne_ai
print(f"[wheel] carcassonne_ai.__file__ = {carcassonne_ai.__file__}")
if not carcassonne_ai.__file__.startswith(repo):
    print(f"[wheel] !!! carcassonne_ai loaded OUTSIDE {repo} -- the venv's editable install "
          f"points at the wrong tree. VOID."); sys.exit(1)

try:
    import carc_rs
except Exception as e:
    print(f"[wheel] !!! carc_rs will not import: {type(e).__name__}: {e}"); sys.exit(1)
print(f"[wheel] carc_rs.__file__ = {carc_rs.__file__}")

# ⚠️ carc_rs.__version__ is the CARGO version and is permanently "0.1.0" -- it
# CANNOT tell a fresh wheel from a stale one. It is printed for the record only;
# the real discriminator is the live nonzero forward below, and the manifest's
# carc_rs_build (a content-derived id) is what G-WHEEL gates on.
from carcassonne_ai.rust_agent import (backend_provenance, carc_rs_build_id,
                                       carc_rs_binary_sha, leaf_config_rs)
prov = backend_provenance()
print(f"[wheel] carc_rs_version = {prov.get('carc_rs_version')!r}  (NOT a build discriminator)")
print(f"[wheel] carc_rs_build   = {prov.get('carc_rs_build')!r}")
print(f"[wheel] binary_sha      = {prov.get('carc_rs_binary_sha')!r}")

if not hasattr(carc_rs.MirrorState, "invasion_terms"):
    print("[wheel] !!! STALE WHEEL: carc_rs.MirrorState has no `invasion_terms` -- this build "
          "predates the invasion-risk family entirely.\n[wheel] !!! REBUILD:\n" + REBUILD)
    sys.exit(1)

# THE REAL PROBE: build every cell's resolved candidate leaf and forward it to
# rust exactly as a game would. A stale wheel raises TypeError HERE, before any
# game, with the rebuild command attached.
import eval_fair_puct as H
spec = importlib.util.spec_from_file_location("screen_lib", os.environ["CARC_LIB"])
L = importlib.util.module_from_spec(spec)
# ⚠️ MUST be in sys.modules BEFORE exec_module: @dataclass resolves its field
# annotations through sys.modules[cls.__module__], and a module loaded from a
# heredoc-fed stdin is not registered by module_from_spec alone -> TypeError
# deep inside dataclasses._is_type. Registering it first is the fix.
sys.modules["screen_lib"] = L
spec.loader.exec_module(L)

# ⚠️ THE TOP-LEVEL KEY NAMES ARE screen_lib.WHEEL_PROBE_REQUIRED_TRUE's, NOT this
# script's invention: screen_lib.wheel_probe_ok() is the ONE definition of what
# this file must contain, so the writer (here) and the reader (G-WHEEL) cannot
# drift. Each names a DIFFERENT failure the stale wheel produces.
probe = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "carc_rs_build": prov.get("carc_rs_build"),
         "carc_rs_version": prov.get("carc_rs_version"),
         "carc_rs_binary_sha": prov.get("carc_rs_binary_sha"),
         "rust_toolchain": prov.get("rust_toolchain"),
         "carc_rs_path": prov.get("carc_rs_path"),
         "invasion_terms_attr": True,      # asserted above, before this dict exists
         "nonzero_kwarg_forward_ok": True,  # ANDed down per cell below
         "cap_biconditional_ok": True,      # ANDed down per cell below
         "cells": {}}
ok = True
for c in L.CELLS:
    cfg = H._load_cand_leaf_cfg(os.path.join(d, c.leaf_json))
    got_hash = H._leaf_hash(cfg)
    curve_ok = tuple(cfg.v29_meeple_curve or ()) == tuple(L.CURVE125)
    # the cap-forwarding BICONDITIONAL (DESIGN.md SS2.3 / G-CAPFWD): a cap set
    # without a nonzero alpha is SILENTLY DROPPED by leaf_config_rs, producing a
    # manifest that lies about the running leaf.
    alpha = float(getattr(cfg, "invasion_alpha", 0.0))
    cap   = float(getattr(cfg, "invasion_alpha_cap", 0.0))
    stub  = int(getattr(cfg, "invasion_stub_max_tiles", 2))
    cap_ok = (cap == 0.0) or (alpha != 0.0)
    stub_ok = (stub == 2) or (alpha != 0.0)
    try:
        rc = leaf_config_rs(cfg)
        fwd_ok, err = True, None
    except Exception as e:                       # TypeError == stale wheel
        rc, fwd_ok, err = None, False, f"{type(e).__name__}: {e}"
    hash_ok = (got_hash == c.cand_leaf_hash)
    probe["cells"][c.name] = {"leaf_json": c.leaf_json, "cand_leaf_hash": got_hash,
                              "cand_leaf_hash_expected": c.cand_leaf_hash,
                              "hash_ok": hash_ok, "curve_ok": curve_ok,
                              "cap_biconditional_ok": bool(cap_ok and stub_ok),
                              "nonzero_forward_ok": fwd_ok, "forward_error": err}
    # AND the per-cell results down into the top-level contract keys G-WHEEL reads.
    probe["nonzero_kwarg_forward_ok"] = bool(probe["nonzero_kwarg_forward_ok"] and fwd_ok)
    probe["cap_biconditional_ok"] = bool(probe["cap_biconditional_ok"] and cap_ok and stub_ok)
    print(f"[wheel] {c.name:6s} hash={got_hash} (want {c.cand_leaf_hash}) curve125={curve_ok} "
          f"cap_ok={cap_ok and stub_ok} forward={'OK' if fwd_ok else 'FAIL'}")
    if not fwd_ok:
        print(f"[wheel] !!! {c.name}: the leaf did NOT reach rust: {err}")
        print("[wheel] !!! This is the STALE-WHEEL signature. A stale carc_rs serves every "
              "default-off config unchanged and raises only on a NONZERO weight -- which is "
              "why this probe forwards the real cell configs instead of checking hasattr.")
        print("[wheel] !!! REBUILD (orchestrator, from the merged tree):\n" + REBUILD)
        ok = False
    if not hash_ok:
        print(f"[wheel] !!! {c.name}: G-LEAF WOULD VOID -- resolved hash != the frozen hash."); ok = False
    if not curve_ok:
        print(f"[wheel] !!! {c.name}: candidate curve is NOT curve125. _assert_netprior_leaf "
              f"HARD-fails on this even with --allow-leaf-hash-drift."); ok = False
    if not (cap_ok and stub_ok):
        print(f"[wheel] !!! {c.name}: G-CAPFWD WOULD VOID -- an inert shape-B knob is set "
              f"without a nonzero invasion_alpha; leaf_config_rs would DROP it silently "
              f"(rust_agent.py:181-185) and the manifest would lie about the running leaf."); ok = False

# The IDENT/A-B-D hash asymmetry, asserted here and gated by G-LEAF(c).
ident = next(c for c in L.CELLS if c.name == "IDENT")
if ident.cand_leaf_hash != L.PROD_LEAF_HASH:
    print("[wheel] !!! IDENT's frozen candidate hash is not the champion hash -- the "
          "explicit-zero identity property is broken."); ok = False
for c in L.CELLS:
    if c.name != "IDENT" and c.cand_leaf_hash == L.PROD_LEAF_HASH:
        print(f"[wheel] !!! {c.name} hashes AS the champion -- its knob is not reaching the leaf."); ok = False

probe["ok"] = ok
json.dump(probe, open(os.path.join(d, "WHEEL_PROBE.json"), "w"), indent=2, sort_keys=True)
print(f"[wheel] wrote {os.path.join(d, 'WHEEL_PROBE.json')}")
sys.exit(0 if ok else 1)
WEOF
  log "[G-WHEEL] carc_rs wheel pre-flight PASS -- nonzero invasion kwargs forward to rust"
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
  printf '%s\n' "$dirt" | sed 's/^/[invscreen]   /'
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
    log "!!! pair is FOUR cells long -- a mid-round move would split the round across revs."
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
# bit-identical under co-tenancy and at any W. A co-tenant moves WALL CLOCK and #
# nothing else -- so refusing the box here would cost throughput and buy no     #
# result integrity. `feedback_no_agent_compute_beside_eval` is honoured, not    #
# evaded: that rule's own text scopes exclusivity to a TIMING bench. This isn't.#
#                                                                              #
# The ONE thing that IS fatal is a FOREIGN RUN_LIVE.json -- which is about      #
# freeze-latch discipline and mixed-rev archives, not about CPU -- and RAM.     #
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

census_advisory() {
  local tenants
  tenants="$(pgrep -af 'eval_fair_puct|eval_puct_priors|gen_fair_distill|carcasum_driver|reconcile_exact_solver|match\.py' \
             | grep -v run_cells || true)"
  if [ -n "$tenants" ]; then
    log "[census] ADVISORY (NON-FATAL -- this pair is result-safe beside other compute):"
    echo "$tenants" | sed 's/^/[invscreen]   /'
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
    echo "$foreign" | sed 's/^/[invscreen]   /'
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
  require_blind_and_band                 # (5)
  write_blind_proof                      # (5) ancestry
  require_table_agrees                   # (1)
  preflight_rules                        # (3)
  preflight_wheel                        # (2)  <- the one unique to this pair
  assert_rev_pinned "pre-flight"         # (4)
  census_advisory                        # (6) advisory + nproc
  require_ram "$PREFLIGHT_RAM_FLOOR_MB" "pre-flight" || exit 8
  require_no_foreign_run_live || exit 7
  log "[preflight] ALL PRECONDITIONS PASS -- clear to launch"
}

# --------------------------------------------------------------------------- #
# RUN_LIVE.json freeze-latch sentinel. MUST live under measurement/ for the     #
# repo's PreToolUse hook to see it, so this one file necessarily dirties the    #
# working tree -- which is why the dirty refusal above is scoped to CODE paths. #
# --------------------------------------------------------------------------- #
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  CARC_P="$(run_live_path)" CARC_W="$1" "$PY" - <<'RLEOF' || true
import json, os, socket, time
json.dump({"what": os.environ["CARC_W"], "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("Invasion-screen round-1 freeze-latch sentinel: a MAIN-TREE commit while "
                   "this round is live risks a mixed-rev archive across FOUR cells (the "
                   "track_d2_prep defect). Cleared on the launcher's EXIT trap."),
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
# The harness writes the claim beside the record as <same-stem>.claim, so "claim
# with no sibling .json" is exactly the orphan set. Applied proactively.
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
# ⭐ THE IN-FLIGHT IDENT PRE-CHECK.                                             #
#                                                                              #
# IDENT is a PRECONDITION on the other three cells (DESIGN.md SS3.1): a defect  #
# that moves a ZERO-weight leaf moves every nonzero one too, so reading A/B/D   #
# past a broken IDENT would be un-attributable. The launcher therefore refuses  #
# to start A/B/D until IDENT's archive is complete and passes its bar.          #
#                                                                              #
# ⚠️ THE ARITHMETIC IS screen_lib's, NOT this shell's, so this pre-check and the #
# adjudicator's G-IDENT CANNOT DRIFT APART. That is the whole reason the bar    #
# library exists as a separate importable file.                                 #
# --------------------------------------------------------------------------- #
ident_precheck() {
  local co; co="$(cell_out IDENT)"
  CARC_LIB="$LIB" CARC_CELL_OUT="$co" "$PY" - <<'IEOF'
import glob, importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location("screen_lib", os.environ["CARC_LIB"])
L = importlib.util.module_from_spec(spec)
# ⚠️ MUST be in sys.modules BEFORE exec_module: @dataclass resolves its field
# annotations through sys.modules[cls.__module__], and a module loaded from a
# heredoc-fed stdin is not registered by module_from_spec alone -> TypeError
# deep inside dataclasses._is_type. Registering it first is the fix.
sys.modules["screen_lib"] = L
spec.loader.exec_module(L)
out = os.environ["CARC_CELL_OUT"]
# ⚠️ NON-RECURSIVE on purpose -- <cell>/failed/ holds failure records with the
# SAME filename pattern and must never be counted as completions.
recs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(out, "seed*_a*.json")))]
if not recs:
    print("[ident-precheck] !!! no IDENT records found -- cannot proceed."); sys.exit(1)
mean, z, n, se, _ = L.paired_margin(recs)

# The three NON-statistical conjuncts of G-IDENT, read off the emitted summary
# rather than assumed. ⚠️ Each is passed EXPLICITLY -- ident_gate takes them as
# required keyword args with no defaults, precisely so a caller that cannot
# answer one fails the gate CLOSED instead of inheriting a permissive default.
sums = sorted(glob.glob(os.path.join(out, "summary.json")))
cfg = json.load(open(sums[-1])).get("config", {}) if sums else {}
n_failed = json.load(open(sums[-1])).get("n_failed") if sums else None
cand_h = cfg.get("cand_leaf_hash")
inv = {k: v for k, v in (cfg.get("cand_leaf_cfg") or {}).items() if k.startswith("invasion")}
opp_inv = {k: v for k, v in (cfg.get("opp_leaf_cfg") or {}).items() if k.startswith("invasion")}
g = L.ident_gate(mean, z, n,
                 leaf_hash_ok=(cand_h == L.PROD_LEAF_HASH),
                 n_failed=(0 if n_failed is None and not sums else n_failed),
                 leaf_diff_empty=(inv == opp_inv))
ok = g["ok"]
print(f"[ident-precheck] n_paired={n} D={mean if mean is None else round(mean, 4)} "
      f"SE={se if se is None else round(se, 4)} z={z if z is None else round(z, 4)} "
      f"(bar |z| <= {L.IDENT_ABS_Z_MAX})")
for k, v in g["conjuncts"].items():
    print(f"[ident-precheck]   {'PASS' if v else 'FAIL'}  {k}")
print(f"[ident-precheck] {'PASS' if ok else 'FAIL'}: {g['reading']}")
if not ok:
    print("[ident-precheck] !!! G-IDENT WOULD VOID THE WHOLE ROUND (READ_RULE.md SS3.4).")
    print("[ident-precheck] !!! Stopping BEFORE A_MID/B_MID/D_MID -- that is the entire point")
    print("[ident-precheck] !!! of running IDENT first: the defect costs ~8 core-h, not ~62.")
    print("[ident-precheck] !!! ⚠️ A null bar can also fail by BAD LUCK ~5% of the time with")
    print("[ident-precheck] !!! perfect wiring. READ_RULE.md SS3.4: report this as AMBIGUOUS")
    print("[ident-precheck] !!! between defect and draw. Diagnose via the leaf-hash conjunct")
    print("[ident-precheck] !!! and a re-run on a FRESH band; do not assert a defect.")
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
  log "band            : $BAND   (4 cells, DISJOINT ranges, no deck reuse)"
  log "budget          : k${K_DETS} x ${SIMS_PER_DET} = ${TOTAL_SIMS} total sims, BOTH sides"
  log "                  (SCREENING budget; production is k8x1376=11008 -- expect the harness's"
  log "                   non-fatal [warn] about the PRODUCTION.yaml deviation, DO NOT suppress it)"
  log "tie-arbiter     : OFF both sides -- NO --cand-tiearb-* flag is emitted below"
  log "tenancy         : NON-EXCLUSIVE, RESULT-SAFE (sims-denominated; DESIGN.md SS6.3)"
  log "W               : $W   (throughput only -- games are bit-identical at any W)"
  log ""
  local c
  for c in "${CELL_NAMES[@]}"; do
    [ -z "$ONLY" ] || [ "$ONLY" = "$c" ] || continue
    build_argv "$c" "${CELL_GAMES[$c]}" "${CELL_SEED[$c]}" "$W" "${CELL_SUB[$c]}" no-stamp
    printf '[dry-run] CELL %-6s:' "$c"; printf ' %q' "${ARGV[@]}"; printf '\n'
    log "  decks         : ${CELL_SEED[$c]}..$(( CELL_SEED[$c] + CELL_DECKS[$c] - 1 )) (${CELL_DECKS[$c]} decks / ${CELL_GAMES[$c]} games)"
    log "  candidate leaf: ${CELL_LEAF[$c]}  -> pinned hash ${CELL_HASH[$c]}"
    log "  opponent leaf : the harness's own _curve125_leaf_cfg() = $PROD_LEAF_HASH (plain champion)"
    log "  drift flag    : $( [ "${CELL_DRIFT[$c]}" = 1 ] && echo '--allow-leaf-hash-drift (nonzero weight moves the hash BY DESIGN)' || echo 'NONE -- IDENT runs under the STRICT hash assertion (explicit zeros hash AS the champion)' )"
    log ""
  done
  log "⭐ SINGLE-VARIABLE PROPERTY, visible in the argv above:"
  log "   WITHIN a cell -- --k-dets/--sims and --opp-k-dets/--opp-sims are the SAME numbers,"
  log "     and the ONLY asymmetric flag is --cand-leaf-json (a candidate-side-only knob:"
  log "     eval_fair_puct.py:3769-3778 gives the opponent _curve125_leaf_cfg() unconditionally)."
  log "   ACROSS cells -- the argv differ ONLY in --cand-leaf-json, --seed-start, --n,"
  log "     --out-subdir, --claim-host and the presence of --allow-leaf-hash-drift."
  log "   Both properties are re-verified against the EMITTED manifest by G-SINGLEVAR."
  log ""
  build_argv "$SMOKE_CELL" "$SMOKE_GAMES" "$SMOKE_SEED_START" "$SMOKE_WORKERS" "smoke_${CELL_SUB[$SMOKE_CELL]}" no-stamp
  printf '[dry-run] SMOKE (%s cfg):' "$SMOKE_CELL"; printf ' %q' "${ARGV[@]}"; printf '\n'
  log "  smoke decks   : $SMOKE_SEED_START..$(( SMOKE_SEED_START + SMOKE_GAMES/2 - 1 )) -- DISJOINT, discarded, never pooled"
  log ""
  CARC_LIB="$LIB" "$PY" - <<'CEOF' || true
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("screen_lib", os.environ["CARC_LIB"])
L = importlib.util.module_from_spec(spec)
# ⚠️ MUST be in sys.modules BEFORE exec_module: @dataclass resolves its field
# annotations through sys.modules[cls.__module__], and a module loaded from a
# heredoc-fed stdin is not registered by module_from_spec alone -> TypeError
# deep inside dataclasses._is_type. Registering it first is the fix.
sys.modules["screen_lib"] = L
spec.loader.exec_module(L)
print("[dry-run] projected cost (screen_lib.project_round_cost, DESIGN.md SS6.1/SS6.2):")
for label, margin in (("base", 0.0), ("+cand margin", L.CAND_MARGIN_TABLE)):
    r = L.project_round_cost(cand_margin=margin)
    print(f"[dry-run]   -- {label} (cand_margin={margin:.2f}) --")
    for c in L.CELLS:
        p = r["per_cell"][c.name]
        tag = "  (weight-0 BOTH sides: no invasion arithmetic)" if c.name == "IDENT" else ""
        print(f"[dry-run]     {c.name:6s} {c.n_games:4d} games -> {p['core_hours']:5.1f} core-h"
              f"  ~{p['wall_minutes']:4.0f} min wall{tag}")
    print(f"[dry-run]     TOTAL              -> {r['core_hours']:5.1f} core-h"
          f"  ~{r['wall_hours']:4.1f} h wall  (at W=22, {L.W_UTIL:.0%} util)")
print("[dry-run]   ⚠️ the candidate-side invasion arithmetic is UNMEASURED (0..+25%/game);")
print("[dry-run]      DESIGN.md SS0(a)'s funding line is the range, not a point estimate.")
CEOF
  log ""
  log "adjudicator     : $REPO/$ADJUDICATOR  (run --selftest before trusting any real read)"
  log "⛔ NOT LAUNCHED. A real cell additionally requires: BLIND_COMMIT stamped, PINNED_SRC_REV"
  log "   written, BAND_CLAIMED dropped, a FRESH carc_rs wheel, and DESIGN.md SS0(a) funding."
}

# =========================================================================== #
# SMOKE                                                                       #
# =========================================================================== #
run_smoke() {
  local c="$SMOKE_CELL" sub="smoke_${CELL_SUB[$SMOKE_CELL]}" so="$OUT/smoke_${CELL_SUB[$SMOKE_CELL]}"
  log "SMOKE (DESIGN.md SS9): ${SMOKE_GAMES} games at $c's EXACT production knobs, throwaway"
  log "  seed $SMOKE_SEED_START, W=$SMOKE_WORKERS. Never pooled, never claimed, never adjudicated"
  log "  as a result. It spends NO BAND and drops NO BAND_CLAIMED -- but it DOES write its"
  log "  own PINNED_SRC_REV / BLIND_PROOF.json / SRC_CLEAN boundaries, because G-REV and"
  log "  G-BLIND are NOT in READ_RULE SS3.5's allowed set and must PASS on the smoke."
  log "  $c is the smoke cell because it has the MOST plumbing to break: a nonzero weight,"
  log "  the --allow-leaf-hash-drift flag, AND the cap-forwarding biconditional."
  require_table_agrees
  preflight_rules
  preflight_wheel
  census_advisory

  # ------------------------------------------------------------------------- #
  # ⭐ THE SMOKE WRITES ITS OWN LAUNCH ARTIFACTS (PRE-GAME-1 AMENDMENT).        #
  #                                                                            #
  # G-REV and G-BLIND are NOT in READ_RULE §3.5's pinned allowed set, so both   #
  # must PASS on the smoke archive. But `PINNED_SRC_REV`, `SRC_CLEAN.jsonl` and #
  # `BLIND_PROOF.json` were only ever written on the REAL-cell path, so         #
  # G-REV read "PINNED_SRC_REV ABSENT — ABSENT is FAIL" on EVERY smoke and the  #
  # leg exited 11 before a single real game could be authorised. Found by       #
  # running the smoke from the main tree.                                      #
  #                                                                            #
  # ⛔ THE FIX IS TO SUPPLY THE WITNESS, NEVER TO WIDEN THE ALLOWED SET.        #
  # ABSENT-is-FAIL stays sacred: the launcher knows the rev, so it writes it.   #
  # This is SAFE and does not pre-empt a real launch — measurement/ is excluded #
  # from CODE_PATHS (so writing it cannot dirty the tree the gate checks), and  #
  # a real launch overwrites the file from `git rev-parse HEAD` anyway.         #
  # The smoke still claims NO band and drops NO BAND_CLAIMED.                   #
  # ------------------------------------------------------------------------- #
  git -C "$REPO" rev-parse HEAD > "$DIR/$PINNED_SRC_REV_FILE"
  log "SMOKE wrote $PINNED_SRC_REV_FILE = $(tr -d '[:space:]' < "$DIR/$PINNED_SRC_REV_FILE")"
  write_blind_proof
  record_src_boundary "pre-flight"

  mkdir -p "$LOGS" "$so"
  build_argv "$c" "$SMOKE_GAMES" "$SMOKE_SEED_START" "$SMOKE_WORKERS" "$sub" no-stamp
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
    print(f"[smoke] candidate {cm:.1f} ms/move  opponent {om:.1f} ms/move  "
          f"invasion-arithmetic multiplier ~= {cm/om:.3f}")
SMEOF

  # --------------------------------------------------------------------- #
  # ⭐ THE STANDING RULE (h2h_22016_prep's post-mortem, adopted by          #
  # track_d2r4_prep, carried here): the smoke step ENDS by running the     #
  # pair's OWN adjudicator against the archive the harness just EMITTED,   #
  # and requires it to fail only on the pinned allowed set that a 16-game  #
  # throwaway cannot satisfy by construction. This is the fix for gates    #
  # written against a manifest the DESIGN described rather than one the    #
  # harness WROTE -- which would have voided a healthy archive once.       #
  # --------------------------------------------------------------------- #
  if [ ! -f "$ADJ" ]; then
    log "!!! FATAL: the pair's adjudicator is missing at $ADJ."
    log "!!! The smoke leg is not complete until analyze_screen.py --smoke-mode has read the"
    log "!!! archive the harness just emitted. Do not launch a real cell against an"
    log "!!! adjudicator that has never seen an emitted manifest."
    exit 11
  fi
  # The closing SRC_CLEAN boundary, so G-REV's SRC_CLEAN conjunct has both a
  # pre-flight and an after- boundary to read (and both must be CLEAN).
  record_src_boundary "smoke-after"

  log "SMOKE -- running the pair's own adjudicator in --smoke-mode against $so"
  "$PY" "$ADJ" --smoke-mode --cell "$so" || {
    log "!!! FATAL: analyze_screen.py --smoke-mode returned nonzero on the smoke archive."
    log "!!! In --smoke-mode the adjudicator PASSES iff the ONLY failures are READ_RULE SS3.5's"
    log "!!! pinned allowed set (G-BAND G-DECKS G-N G-SAT G-IDENT RECON/n_paired)."
    log "!!! A nonzero exit therefore means a REAL gate is broken on EMITTED output -- exactly"
    log "!!! what this step exists to catch before 2800 games are spent."
    exit 11
  }
  log "SMOKE PASS -- plumbing clean, adjudicator reads emitted output."
  log "NEXT: $PY $REPO/$ADJUDICATOR --selftest   (must exit 0, seeded from THIS archive)"
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
  log "CELL $c: decks ${CELL_SEED[$c]}..$(( CELL_SEED[$c] + CELL_DECKS[$c] - 1 )), leaf ${CELL_LEAF[$c]} (hash ${CELL_HASH[$c]})"

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
      log "CELL $c pass $pass: REALIZED $(( dt * W / made )) worker-s/game (model: 72)"
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
        log "!!! .claim files under $co (the sweep above should have cleared any orphan; a"
        log "!!! claim WITH a sibling record is not an orphan)."
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
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "invasion-screen round 1, band $BAND, 4 cells / 2800 games, W=$W"

  local c
  for c in "${CELL_NAMES[@]}"; do
    if [ -n "$ONLY" ] && [ "$ONLY" != "$c" ]; then
      log "skipping $c (--only $ONLY)"
      continue
    fi
    # ⭐ THE IDENT INTERLOCK (DESIGN.md SS6.4 / SS3.1). A/B/D do not start until
    # IDENT's archive is complete AND passes screen_lib's own G-IDENT arithmetic.
    if [ "$c" != "IDENT" ]; then
      local io; io="$(cell_out IDENT)"
      if [ ! -f "$DIR/DONE_cell_IDENT" ] || [ "$(n_records "$io")" -lt "${CELL_GAMES[IDENT]}" ]; then
        log "!!! FATAL: refusing to start $c -- the IDENT cell is not complete."
        log "!!! IDENT is a PRECONDITION on every other cell (READ_RULE.md SS3.4): a defect that"
        log "!!! moves a ZERO-weight leaf moves every nonzero one too, and no A/B/D reading could"
        log "!!! then be attributed to the term rather than to the wiring."
        touch "$DIR/FAILED_cell_$c"; exit 12
      fi
      if ! ident_precheck; then
        log "!!! FATAL: the IDENT pre-check FAILED. Stopping the round here."
        touch "$DIR/FAILED_IDENT"; exit 13
      fi
    fi
    run_cell "$c"
  done

  run_live_clear
  log "ROUND DONE -- RUN_LIVE cleared"
  log "NEXT: $PY $REPO/$ADJUDICATOR --selftest   (must exit 0), then"
  log "      $PY $REPO/$ADJUDICATOR --run-dir $OUT"
  log "The fired branch IS the authorization to report it (READ_RULE.md SS4/SS7) -- but every"
  log "ACTION a branch licenses is a fresh funding decision and a fresh pair."
}

main "$@"
