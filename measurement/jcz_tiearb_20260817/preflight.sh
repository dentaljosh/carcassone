#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — PER-HOST PRE-FLIGHT. HARD BLOCKER. Run BEFORE game 1
# ON EVERY BOX THAT PLAYS.
#
#   preflight.sh [LABEL]        LABEL defaults to FIRST; launch.sh --smoke passes SMOKE
#
# ⭐ PER-HOST, BY OWNER RULING (DESIGN §0.1.5, READ_RULE §0.F.1). `G-J13` and
# `G-JCZ` are PER-HOST gates: each box writes its own
# `verdicts/PREFLIGHT_<host>_FIRST.json`, generated AFTER any wheel build on that
# box and BEFORE that box's own game 1. READ_RULE `G-J13` voids on "a host that
# played with no pre-flight", so this script runs on the local box AND on the
# laptop, and both verdict files are synced to the share so the local
# adjudicator can read the laptop's.
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
#   verdicts/PREFLIGHT_<host>_ENV.json     `G-TOOL` + `G-JCZ` — git HEAD, the
#       carc_rs binary sha256 + build id, rustc, the JCZ jar sha256 ON THIS HOST,
#       the shim class count ON THIS HOST, `$JAVA_BIN -version`, and the resolved
#       worker count for THIS host. `G-TOOL` is back in its Stage-2 CROSS-BOX
#       shape (pre-flights compared with each other, manifests with each other —
#       never a pre-flight against a manifest) PLUS the same-box
#       `carc_rs_binary_sha` witness.
#
# ⚠️⚠️ ORDERING, AND IT IS LOAD-BEARING (READ_RULE §3.1). UNCHANGED BY THE
#   TWO-BOX REWORK — only the number of hosts it runs on changed.
#   The pre-flight MUST be generated **AFTER** any wheel rebuild on that host and
#   **BEFORE** the detached launch, so that `G-TOOL`'s conjunct
#       git diff --name-only <preflight_commit>..<manifest_commit> -- rust/ src/ engine/ scripts/
#   is EMPTY or the range is DEGENERATE on a healthy run.
#   Stage 2's `launch_both.sh` had NO pre-flight step at all: it rebuilt the wheel
#   and launched, so HEAD moved between the pre-flight and the manifest on EVERY
#   healthy run, and `G-TOOL` was unsatisfiable by construction. That cost Stage 2
#   an adjudication. `launch.sh` in this directory ENFORCES the order (census →
#   flag probe → bundle sync → claim → preflight on BOTH boxes → detached launch)
#   and asserts HEAD is unchanged, on both boxes, between the pre-flight and the
#   launch.
#
# ⚠️ A NON-INTERACTIVE ssh shell does NOT get rustup on PATH (the profile that
#   adds it is only sourced for login/interactive shells) — observed on the
#   laptop 2026-08-17 and re-observed by probe today (`rustc` absent from the
#   laptop's non-interactive PATH). `$HOME/.cargo/env` is sourced explicitly
#   below so the `rustc` witness is a version string on both hosts and not an
#   error string on one, which would read as a cross-box toolchain difference.
#
# Exits NONZERO on any failure, and launch.sh aborts on that. ADJUDICATES
# NOTHING, plays no game, reads no strength number.
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"
. "$HERE/_boxenv.sh"

LABEL="${1:-FIRST}"
case "$LABEL" in
  FIRST|SMOKE) ;;
  *) echo "FATAL: LABEL must be FIRST or SMOKE, got '$LABEL'" >&2; exit 2 ;;
esac

REPO="$REPO_LOCAL"
PY="$REPO/.venv/bin/python"
PF_PY="$REPO/measurement/tiearb2_stage2_20260817/preflight_tiearb.py"
VERD="$RUN_DIR/verdicts"
LOGS="$RUN_DIR/logs"
mkdir -p "$VERD" "$LOGS" "$SHARE_RUN/verdicts"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[preflight $(ts) $HOST] $*"; }

log "host=$HOST  share=$SHARE_RUN  label=$LABEL"
[ -x "$PY" ]    || { log "FATAL: no venv python at $PY"; exit 1; }
[ -f "$PF_PY" ] || { log "FATAL: pre-flight probe missing at $PF_PY (is this box bundle-synced?)"; exit 1; }

# rustup is not on a non-interactive PATH; source it before anything reads rustc.
if [ -f "$HOME/.cargo/env" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
fi
PATH="$HOME/.cargo/bin:$PATH"; export PATH

# Same leaf/rules env the cells run under — the probe must resolve the champion
# exactly as the cells will.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9="$FIX_R9"
export RUSTUP_TOOLCHAIN="$RUST_TOOLCHAIN"
# Exported here too so the pre-flight resolves the champion under EXACTLY the JVM
# environment the cells will use (DESIGN §0.1.4). It changes nothing about the
# probe, and a pre-flight run under a different env is a weaker witness.
jvm_opts_export

# ==========================================================================
# 0. PER-HOST ARTIFACT PROVENANCE (`G-JCZ` is a PER-HOST gate, READ_RULE §3).
#    Cheapest checks first: a wrong jar or a missing shim must not cost the
#    30-90 s the J13 control takes.
# ==========================================================================
log "--- G-JCZ (per-host artifact provenance on $HOST) ---"

resolve_java || { log "FATAL: java resolution failed on $HOST"; exit 25; }
log "java: $JAVA_RESOLVED  ($JAVA_VERSION_LINE)"
# the full 3-line banner, minus the JVM's own "Picked up _JAVA_OPTIONS" noise —
# this is the per-host string G-JCZ's disclosed packaging difference is read from
# (17.0.19+10-1-24.04.2-Ubuntu locally vs +10-1-26.04.2-Ubuntu on the laptop).
JAVA_VERSION_FULL="$("$JAVA_BIN" -version 2>&1 | grep -v '^Picked up ' | tr '\n' '|')"

[ -f "$JCZ_JAR" ] || { log "FATAL: JCZ jar missing at $JCZ_JAR on $HOST"; exit 1; }
JAR_SHA="$(sha256sum "$JCZ_JAR" | awk '{print $1}')"
if [ "$JAR_SHA" != "$JCZ_JAR_SHA256" ]; then
  log "!!! G-JCZ VIOLATION on $HOST: Engine.jar sha256 $JAR_SHA != pinned $JCZ_JAR_SHA256"
  log "!!! The jar is verified ON EACH HOST because G-JCZ is a PER-HOST gate"
  log "!!! (DESIGN §0.1: the laptop's jar was staged via the share and sha-verified)."
  exit 21
fi
log "jar sha256 OK on $HOST ($JAR_SHA)"

[ -d "$AI_CLASSES" ] || { log "FATAL: JCZ AI shim classes missing at $AI_CLASSES on $HOST"; exit 22; }
SHIM_N="$(find "$AI_CLASSES" -name '*.class' 2>/dev/null | wc -l | tr -d ' ')"
if [ "$SHIM_N" -ne "$JCZ_SHIM_CLASS_COUNT_EXPECT" ]; then
  log "!!! G-JCZ VIOLATION on $HOST: $SHIM_N shim .class files, expected $JCZ_SHIM_CLASS_COUNT_EXPECT"
  log "!!! DESIGN §0.1: the shim is COPIED, not rebuilt, so both hosts run byte-identical bytecode."
  exit 22
fi
export JCZ_AI_CLASSES="$AI_CLASSES"
log "shim classes OK on $HOST ($SHIM_N at $AI_CLASSES)"

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
  log "!!! G-J13 PRE-FLIGHT FAILED (rc=$pfrc) ON $HOST"
  log "!!!   verdict: $PF_NOW"
  log "!!!   stderr : $LOGS/preflight_${HOST}_${LABEL}.log"
  log "!!! REFUSING TO LAUNCH. A dead arbitration surface grades a perfect"
  log "!!! champion-vs-champion null wearing the shape of a real cell, and NO"
  log "!!! leaf-hash gate on this surface could ever detect it."
  log "!!! Rebuild the wheel on THIS box, THEN re-run this pre-flight:"
  log "!!!   RUSTUP_TOOLCHAIN=$RUST_TOOLCHAIN $REPO/.venv/bin/maturin develop --release -m rust/carc/carc-py/Cargo.toml"
  { echo "utc $(ts)"; echo "G-J13 PRE-FLIGHT FAILED rc=$pfrc on $HOST"; echo "see $PF_NOW"; } \
    > "$RUN_DIR/FAILED_PREFLIGHT_${HOST}"
  cp -f "$RUN_DIR/FAILED_PREFLIGHT_${HOST}" "$SHARE_RUN/" 2>/dev/null || true
  cp -f "$PF_NOW" "$SHARE_RUN/verdicts/" 2>/dev/null || true
  exit 13
fi
rm -f "$RUN_DIR/FAILED_PREFLIGHT_${HOST}" "$SHARE_RUN/FAILED_PREFLIGHT_${HOST}"
[ -f "$PF_OUT" ] || cp "$PF_NOW" "$PF_OUT"
log "G-J13 PASS on $HOST -> $PF_NOW (gate witness: $PF_OUT)"

# ==========================================================================
# 2. G-TOOL / G-JCZ — the PER-HOST environment witness.
#    `carc_rs_binary_sha` is the same-box staleness evidence (it is NOT
#    cross-box comparable — two boxes legitimately produce different binaries
#    from the same source, which is exactly why READ_RULE `G-TOOL` compares
#    pre-flights WITH EACH OTHER and manifests WITH EACH OTHER, and never a
#    pre-flight against a manifest).
# ==========================================================================
ENV_OUT="$VERD/PREFLIGHT_${HOST}_ENV.json"

PF_ENV_LABEL="$LABEL" \
PF_ENV_HOST="$HOST" \
PF_ENV_IS_LAPTOP="$IS_LAPTOP" \
PF_ENV_JAR="$JCZ_JAR" \
PF_ENV_JAR_SHA="$JAR_SHA" \
PF_ENV_JAR_SHA_EXPECT="$JCZ_JAR_SHA256" \
PF_ENV_JCZ_REV="$JCZ_REV" \
PF_ENV_AI_CLASS="$JCZ_AI_CLASS" \
PF_ENV_AI_CLASSES="$AI_CLASSES" \
PF_ENV_SHIM_N="$SHIM_N" \
PF_ENV_SHIM_N_EXPECT="$JCZ_SHIM_CLASS_COUNT_EXPECT" \
PF_ENV_TILES="$JCZ_TILES" \
PF_ENV_W_BOX="$W_BOX" \
PF_ENV_W_BOX_SMOKE="$W_BOX_SMOKE" \
PF_ENV_W_LOCAL="$W_LOCAL" \
PF_ENV_W_LAPTOP="$W_LAPTOP" \
PF_ENV_DECKS_BOX="$DECKS_BOX_DEFAULT" \
PF_ENV_JAVA_BIN="$JAVA_BIN" \
PF_ENV_JAVA_RESOLVED="$JAVA_RESOLVED" \
PF_ENV_JAVA_VERSION="$JAVA_VERSION_FULL" \
PF_ENV_JVM_OPTS="$JVM_OPTS" \
PF_ENV_SHARE="$SHARE_RUN" \
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
    "witness": "G-TOOL + G-JCZ (PER-HOST)",
    "label": os.environ["PF_ENV_LABEL"],
    "host": os.environ["PF_ENV_HOST"],
    "is_laptop": os.environ["PF_ENV_IS_LAPTOP"] == "1",
    "utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip(),
    "git_head": run("git", "-C", repo, "rev-parse", "HEAD"),
    "git_head_short": run("git", "-C", repo, "rev-parse", "--short", "HEAD"),
    "git_branch": run("git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"),
    # The load-bearing half of "is the tree dirty": measurement artifacts churn
    # constantly, so only a dirty CODE path makes `git_head` a lie about what ran.
    "git_dirty_code_paths": [
        ln for ln in subprocess.run(
            ["git", "-C", repo, "status", "--porcelain", "--",
             "src/", "rust/", "engine/", "scripts/"],
            capture_output=True, text=True).stdout.splitlines() if ln.strip()],
    # ---- toolchain / binary (G-TOOL) ----
    "carc_rs_binary_sha": prov.get("carc_rs_binary_sha"),
    "carc_rs_build_id": prov.get("carc_rs_build"),
    "carc_rs_version": prov.get("carc_rs_version"),
    "carc_rs_path": prov.get("carc_rs_path"),
    "tile_data_source_sha256": prov.get("tile_data_source_sha256"),
    "tile_data_semantic_digest": prov.get("tile_data_semantic_digest"),
    "rustc": run("rustc", "--version"),
    "cargo": run("cargo", "--version"),
    "rustup_toolchain": os.environ.get("RUSTUP_TOOLCHAIN"),
    "python": run(sys.executable, "--version"),
    "uname": run("uname", "-srvm"),
    "nproc": run("nproc"),
    # ---- JVM / JCZ provenance (G-JCZ, per host) ----
    "java_bin_pinned": os.environ["PF_ENV_JAVA_BIN"],
    "java_resolved_on_path": os.environ["PF_ENV_JAVA_RESOLVED"],
    "java_version": os.environ["PF_ENV_JAVA_VERSION"],
    "java_matches_pin": (os.environ["PF_ENV_JAVA_RESOLVED"]
                         == os.environ["PF_ENV_JAVA_BIN"]),
    "jvm_opts": os.environ["PF_ENV_JVM_OPTS"],
    "jcz_jar": os.environ["PF_ENV_JAR"],
    "jcz_jar_sha256": os.environ["PF_ENV_JAR_SHA"],
    "jcz_jar_sha256_expected": os.environ["PF_ENV_JAR_SHA_EXPECT"],
    "jcz_jar_sha256_match": os.environ["PF_ENV_JAR_SHA"] == os.environ["PF_ENV_JAR_SHA_EXPECT"],
    "jcz_rev": os.environ["PF_ENV_JCZ_REV"],
    "jcz_ai_class": os.environ["PF_ENV_AI_CLASS"],
    "jcz_ai_classes_dir": os.environ["PF_ENV_AI_CLASSES"],
    "jcz_shim_class_count": int(os.environ["PF_ENV_SHIM_N"]),
    "jcz_shim_class_count_expected": int(os.environ["PF_ENV_SHIM_N_EXPECT"]),
    "jcz_shim_class_count_match": (os.environ["PF_ENV_SHIM_N"]
                                   == os.environ["PF_ENV_SHIM_N_EXPECT"]),
    "jcz_tiles": os.environ["PF_ENV_TILES"],
    # ---- resolved execution parameters for THIS host ----
    "w_resolved_this_host": int(os.environ["PF_ENV_W_BOX"]),
    "w_smoke_this_host": int(os.environ["PF_ENV_W_BOX_SMOKE"]),
    "w_local_conf": int(os.environ["PF_ENV_W_LOCAL"]),
    "w_laptop_conf": int(os.environ["PF_ENV_W_LAPTOP"]),
    "decks_this_host_conf": int(os.environ["PF_ENV_DECKS_BOX"]),
    "share_run_dir": os.environ["PF_ENV_SHARE"],
    "j13_verdict_path": os.environ["PF_ENV_J13"],
    "ordering_note": (
        "READ_RULE §3.1: this witness is generated AFTER any wheel rebuild on "
        "THIS host and BEFORE the detached launch, so G-TOOL's "
        "<preflight>..<manifest> commit range is degenerate on a healthy run. "
        "G-J13 and G-JCZ are PER-HOST (READ_RULE §0.F.1): a host that played "
        "with no pre-flight VOIDS the run."),
}
json.dump(doc, sys.stdout, indent=1)
print()
PYEOF

cat "$ENV_OUT"
log "G-TOOL/G-JCZ env witness -> $ENV_OUT"

# A dirty CODE path means `git_head` is a lie about what will actually run.
DIRTY_N="$("$PY" -c "import json,sys;print(len(json.load(open(sys.argv[1]))['git_dirty_code_paths']))" "$ENV_OUT")"
if [ "$DIRTY_N" -ne 0 ]; then
  log "!!! $DIRTY_N dirty CODE path(s) under src/ rust/ engine/ scripts/ on $HOST — see $ENV_OUT"
  log "!!! G-TOOL's commit-range conjunct cannot be resolved against an uncommitted tree:"
  log "!!! the recorded git_head would be a lie about what actually ran."
  log "!!! On the LAPTOP this additionally means the bundle sync did not land cleanly."
  if [ "${ALLOW_DIRTY_CODE:-0}" = "1" ]; then
    log "!!! ALLOW_DIRTY_CODE=1 — proceeding under operator override. The dirty paths are"
    log "!!! recorded in $ENV_OUT and the adjudicator MUST read G-TOOL against them."
  else
    log "!!! Commit or stash the code change, then re-run this pre-flight."
    log "!!! (deliberate override: ALLOW_DIRTY_CODE=1 ./preflight.sh $LABEL)"
    exit 14
  fi
fi

# ==========================================================================
# 3. PUBLISH TO THE SHARE. The adjudicator runs on the LOCAL box and must be
#    able to read the LAPTOP's verdicts; `G-J13` names both expected hosts
#    (`Doctor`, `laptop-wsl`) and voids on "a host that played with no
#    pre-flight", so an unsynced verdict is indistinguishable from a missing one.
# ==========================================================================
mkdir -p "$SHARE_RUN/verdicts"
cp -f "$VERD"/PREFLIGHT_"$HOST"_*.json "$SHARE_RUN/verdicts/" 2>/dev/null \
  || log "WARN: could not publish verdicts to $SHARE_RUN/verdicts"
log "verdicts published -> $SHARE_RUN/verdicts/  ($(ls "$SHARE_RUN/verdicts" 2>/dev/null | tr '\n' ' '))"

log "PRE-FLIGHT COMPLETE on $HOST (label=$LABEL). Launch may proceed; HEAD must not move from here."
exit 0
