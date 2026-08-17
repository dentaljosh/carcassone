#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — PER-BOX PRE-FLIGHT. HARD BLOCKER. Run BEFORE game 1.
#
#   preflight.sh [LABEL]        LABEL defaults to FIRST; launch.sh --smoke passes SMOKE
#
# It produces the two witnesses READ_RULE §3 names:
#
#   verdicts/PREFLIGHT_<host>_FIRST.json   `G-J13` — the TWO-SIDED arbiter positive
#       control: at a constructed tied ply the arbiter must CHANGE the pick AND
#       leave the root leaf value bits UNCHANGED. The arbiter's knobs live on
#       SearchConfig, not LeafConfig, so NO LEAF HASH MOVES when it is armed —
#       every moved-hash wiring gate this program owns is INERT on this surface.
#       Without this control "a zeroed dose grades a perfect champion-vs-champion
#       null wearing the shape of a real cell."
#
#   verdicts/PREFLIGHT_<host>_ENV.json     `G-TOOL` — git HEAD, the carc_rs binary
#       sha256 + build id, rustc, the JCZ jar sha256, java, and the resolved
#       worker count. Single box ⇒ the same-box binary-sha witness is strictly
#       stronger than Stage 2's cross-box build-id comparison (DESIGN §6.3).
#
# ⚠️⚠️ ORDERING, AND IT IS LOAD-BEARING (READ_RULE §3.1).
#   The pre-flight MUST be generated **AFTER** any wheel rebuild and **BEFORE**
#   the detached launch, so that `G-TOOL`'s conjunct
#       git diff --name-only <preflight_commit>..<manifest_commit> -- rust/ src/ engine/ scripts/
#   is EMPTY or the range is DEGENERATE on a healthy run.
#   Stage 2's `launch_both.sh` had NO pre-flight step at all: it rebuilt the wheel
#   and launched, so HEAD moved between the pre-flight and the manifest on EVERY
#   healthy run, and `G-TOOL` was unsatisfiable by construction. That cost Stage 2
#   an adjudication. `launch.sh` in this directory ENFORCES the order (census →
#   flag probe → claim → preflight → detached launch) and asserts HEAD is
#   unchanged between the pre-flight and the launch.
#
# Exits NONZERO on any failure, and launch.sh aborts on that. ADJUDICATES
# NOTHING, plays no game, reads no strength number.
# =============================================================================
set -euo pipefail
. "$(dirname "$0")/WORKERS.conf"

LABEL="${1:-FIRST}"
case "$LABEL" in
  FIRST|SMOKE) ;;
  *) echo "FATAL: LABEL must be FIRST or SMOKE, got '$LABEL'" >&2; exit 2 ;;
esac

REPO="$REPO_LOCAL"
PY="$REPO/.venv/bin/python"
PF_PY="$REPO/measurement/tiearb2_stage2_20260817/preflight_tiearb.py"
HOST="$(hostname)"
VERD="$RUN_DIR/verdicts"
LOGS="$RUN_DIR/logs"
mkdir -p "$VERD" "$LOGS"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[preflight $(ts)] $*"; }

[ -x "$PY" ]    || { log "FATAL: no venv python at $PY"; exit 1; }
[ -f "$PF_PY" ] || { log "FATAL: pre-flight probe missing at $PF_PY"; exit 1; }

# Same leaf/rules env the cells run under — the probe must resolve the champion
# exactly as the cells will.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9="$FIX_R9"
export RUSTUP_TOOLCHAIN="$RUST_TOOLCHAIN"

# ==========================================================================
# 1. G-J13 — the TWO-SIDED positive control, at the funded rung from
#    WORKERS.conf. NOTHING is hard-coded here.
# ==========================================================================
# The FIRST attempt's verdict is the gate witness and is NEVER overwritten by a
# resume (Stage-2 pattern): every attempt writes its own timestamped verdict and
# only the first one is promoted to the `_FIRST.json` name G-J13 reads.
PF_NOW="$VERD/PREFLIGHT_${HOST}_${LABEL}_$(date -u +%s).json"
PF_OUT="$VERD/PREFLIGHT_${HOST}_${LABEL}.json"
log "--- G-J13 two-sided arbiter control (B=$TIEARB_B J=$TIEARB_J salt=$TIEARB_SALT eps=$TIEARB_EPS) ---"
set +e
PREFLIGHT_TIEARB_B="$TIEARB_B" \
PREFLIGHT_TIEARB_J="$TIEARB_J" \
PREFLIGHT_TIEARB_SALT="$TIEARB_SALT" \
PREFLIGHT_TIEARB_EPS="$TIEARB_EPS" \
  nice -n "$NICE" "$PY" "$PF_PY" > "$PF_NOW" 2> "$LOGS/preflight_${HOST}_${LABEL}.log"
pfrc=$?
set -e
cat "$PF_NOW" || true
if [ "$pfrc" -ne 0 ]; then
  log "!!! G-J13 PRE-FLIGHT FAILED (rc=$pfrc)"
  log "!!!   verdict: $PF_NOW"
  log "!!!   stderr : $LOGS/preflight_${HOST}_${LABEL}.log"
  log "!!! REFUSING TO LAUNCH. A dead arbitration surface grades a perfect"
  log "!!! champion-vs-champion null wearing the shape of a real cell, and NO"
  log "!!! leaf-hash gate on this surface could ever detect it."
  log "!!! Rebuild the wheel on THIS box, THEN re-run this pre-flight:"
  log "!!!   RUSTUP_TOOLCHAIN=$RUST_TOOLCHAIN $REPO/.venv/bin/maturin develop --release -m rust/carc/carc-py/Cargo.toml"
  { echo "utc $(ts)"; echo "G-J13 PRE-FLIGHT FAILED rc=$pfrc on $HOST"; echo "see $PF_NOW"; } \
    > "$RUN_DIR/FAILED_PREFLIGHT_${HOST}"
  exit 13
fi
rm -f "$RUN_DIR/FAILED_PREFLIGHT_${HOST}"
[ -f "$PF_OUT" ] || cp "$PF_NOW" "$PF_OUT"
log "G-J13 PASS -> $PF_NOW (gate witness: $PF_OUT)"

# ==========================================================================
# 2. G-TOOL — the environment witness. Single box, so `carc_rs_binary_sha` is
#    the authoritative staleness evidence (it is NOT cross-box comparable, and
#    there is no second box here to mis-compare it against).
# ==========================================================================
ENV_OUT="$VERD/PREFLIGHT_${HOST}_ENV.json"
[ -f "$JCZ_JAR" ] || { log "FATAL: JCZ jar missing at $JCZ_JAR"; exit 1; }
JAR_SHA="$(sha256sum "$JCZ_JAR" | awk '{print $1}')"
if [ "$JAR_SHA" != "$JCZ_JAR_SHA256" ]; then
  log "!!! G-JCZ VIOLATION: Engine.jar sha256 $JAR_SHA != pinned $JCZ_JAR_SHA256"
  exit 21
fi

PF_ENV_LABEL="$LABEL" \
PF_ENV_HOST="$HOST" \
PF_ENV_JAR="$JCZ_JAR" \
PF_ENV_JAR_SHA="$JAR_SHA" \
PF_ENV_JAR_SHA_EXPECT="$JCZ_JAR_SHA256" \
PF_ENV_JCZ_REV="$JCZ_REV" \
PF_ENV_AI_CLASS="$JCZ_AI_CLASS" \
PF_ENV_TILES="$JCZ_TILES" \
PF_ENV_W_LOCAL="$W_LOCAL" \
PF_ENV_W_SMOKE="$W_SMOKE" \
PF_ENV_REPO="$REPO" \
PF_ENV_J13="$PF_OUT" \
  "$PY" - <<'PYEOF' > "$ENV_OUT"
import json, os, subprocess, sys

def run(*cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return (p.stdout + p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr) else ""
    except Exception as e:                                   # noqa: BLE001
        return f"<{type(e).__name__}: {e}>"

repo = os.environ["PF_ENV_REPO"]
sys.path.insert(0, os.path.join(repo, "src"))
try:
    from carcassonne_ai.rust_agent import backend_provenance
    prov = backend_provenance()
except Exception as e:                                       # noqa: BLE001
    prov = {"ERROR": f"{type(e).__name__}: {e}"}

doc = {
    "witness": "G-TOOL",
    "label": os.environ["PF_ENV_LABEL"],
    "host": os.environ["PF_ENV_HOST"],
    "utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip(),
    "git_head": run("git", "-C", repo, "rev-parse", "HEAD"),
    "git_head_short": run("git", "-C", repo, "rev-parse", "--short", "HEAD"),
    # The load-bearing half of "is the tree dirty": measurement artifacts churn
    # constantly, so only a dirty CODE path makes `git_head` a lie about what ran.
    "git_dirty_code_paths": [
        ln for ln in subprocess.run(
            ["git", "-C", repo, "status", "--porcelain", "--",
             "src/", "rust/", "engine/", "scripts/"],
            capture_output=True, text=True).stdout.splitlines() if ln.strip()],
    "carc_rs_binary_sha": prov.get("carc_rs_binary_sha"),
    "carc_rs_build_id": prov.get("carc_rs_build"),
    "carc_rs_version": prov.get("carc_rs_version"),
    "carc_rs_path": prov.get("carc_rs_path"),
    "tile_data_source_sha256": prov.get("tile_data_source_sha256"),
    "tile_data_semantic_digest": prov.get("tile_data_semantic_digest"),
    "rustc": run("rustc", "--version"),
    "cargo": run("cargo", "--version"),
    "rustup_toolchain": os.environ.get("RUSTUP_TOOLCHAIN"),
    "java": run("java", "-version"),
    "jcz_jar": os.environ["PF_ENV_JAR"],
    "jcz_jar_sha256": os.environ["PF_ENV_JAR_SHA"],
    "jcz_jar_sha256_expected": os.environ["PF_ENV_JAR_SHA_EXPECT"],
    "jcz_jar_sha256_match": os.environ["PF_ENV_JAR_SHA"] == os.environ["PF_ENV_JAR_SHA_EXPECT"],
    "jcz_rev": os.environ["PF_ENV_JCZ_REV"],
    "jcz_ai_class": os.environ["PF_ENV_AI_CLASS"],
    "jcz_tiles": os.environ["PF_ENV_TILES"],
    "w_local_resolved": int(os.environ["PF_ENV_W_LOCAL"]),
    "w_smoke_resolved": int(os.environ["PF_ENV_W_SMOKE"]),
    "j13_verdict_path": os.environ["PF_ENV_J13"],
    "ordering_note": (
        "READ_RULE §3.1: this witness is generated AFTER any wheel rebuild and "
        "BEFORE the detached launch, so G-TOOL's <preflight>..<manifest> commit "
        "range is degenerate on a healthy run."),
}
json.dump(doc, sys.stdout, indent=1)
print()
PYEOF

cat "$ENV_OUT"
log "G-TOOL env witness -> $ENV_OUT"

# A dirty CODE path means `git_head` is a lie about what will actually run.
DIRTY_N="$("$PY" -c "import json,sys;print(len(json.load(open(sys.argv[1]))['git_dirty_code_paths']))" "$ENV_OUT")"
if [ "$DIRTY_N" -ne 0 ]; then
  log "!!! $DIRTY_N dirty CODE path(s) under src/ rust/ engine/ scripts/ — see $ENV_OUT"
  log "!!! G-TOOL's commit-range conjunct cannot be resolved against an uncommitted tree:"
  log "!!! the recorded git_head would be a lie about what actually ran."
  if [ "${ALLOW_DIRTY_CODE:-0}" = "1" ]; then
    log "!!! ALLOW_DIRTY_CODE=1 — proceeding under operator override. The dirty paths are"
    log "!!! recorded in $ENV_OUT and the adjudicator MUST read G-TOOL against them."
  else
    log "!!! Commit or stash the code change, then re-run this pre-flight."
    log "!!! (deliberate override: ALLOW_DIRTY_CODE=1 ./preflight.sh $LABEL)"
    exit 14
  fi
fi

log "PRE-FLIGHT COMPLETE (label=$LABEL). Launch may proceed; HEAD must not move from here."
exit 0
