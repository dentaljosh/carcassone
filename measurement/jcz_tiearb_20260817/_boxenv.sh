#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — PER-BOX DERIVATION. Sourced AFTER WORKERS.conf by every
# launcher in this directory:
#
#     . "$(dirname "$0")/WORKERS.conf"
#     . "$(dirname "$0")/_boxenv.sh"
#
# ⚠️ IT DEFINES NO CONSTANT. Every value here is DERIVED from WORKERS.conf.
# WORKERS.conf remains the one place a worker count, a path, or a rung is set.
# This file exists so the host→share and host→W mappings have exactly ONE
# definition: a copy of them that drifted in one script would be a silent,
# cross-box, data-corrupting bug (see the share-path trap below).
#
# ⚠️⚠️ THE SHARE PATH IS RESOLVED BY **HOSTNAME**, NEVER BY EXISTENCE.
# `/mnt/c/carc-shared` EXISTS ON BOTH BOXES — the laptop is also WSL and also has
# a `/mnt/c`, pointing at the LAPTOP's own C: drive, a completely different
# folder that is NOT the shared CIFS mount. VERIFIED 2026-08-17: the laptop
# reports both `/mnt/c/carc-shared` and `/mnt/carc-shared` present. So the
# house's usual "first path that exists wins" probe picks the WRONG directory on
# the laptop and writes shards nobody ever merges. Hostname it is.
# =============================================================================

# --- who am I ----------------------------------------------------------------
HOST="$(hostname)"

case "$HOST" in
  "$LAPTOP_HOST")
    IS_LAPTOP=1
    SHARE_BASE="$SHARE_REMOTE"      # /mnt/carc-shared  — the CIFS mount
    W_BOX="$W_LAPTOP"
    W_BOX_SMOKE="$W_SMOKE_LAPTOP"
    DECKS_BOX_DEFAULT="$DECKS_LAPTOP"
    ;;
  *)
    IS_LAPTOP=0
    SHARE_BASE="$SHARE_LOCAL"       # /mnt/c/carc-shared — the share HOST's own C:
    W_BOX="$W_LOCAL"
    W_BOX_SMOKE="$W_SMOKE_LOCAL"
    DECKS_BOX_DEFAULT="$DECKS_LOCAL"
    ;;
esac

SHARE_RUN="$SHARE_BASE/$RUN_ID"

# The repo path is identical on both boxes (WORKERS.conf: REPO_LOCAL ==
# REPO_REMOTE), so RUN_DIR from WORKERS.conf is already correct on either box.
# Restated here only so a future divergence is caught at one site.
if [ "$REPO_LOCAL" != "$REPO_REMOTE" ]; then
  echo "FATAL(_boxenv): REPO_LOCAL != REPO_REMOTE — every path in this run assumes they are equal" >&2
  exit 2
fi

# =============================================================================
# resolve_java — THE `java` BINARY QUESTION, ANSWERED HONESTLY.
#
# There is NO override hook. Chain of custody, read 2026-08-17:
#   scripts/jcz_match/match.py:482   JczAiEngine(jar=…, tiles=…, ai_classes=…, main_class=…)
#   scripts/jcz_match/ai_engine.py   JczAiEngine.__init__ → super().__init__(*a, **kw)
#   scripts/jcz_oracle/jcz_driver.py:57  def __init__(self, jar=None, tiles=None, java: str = "java")
#   scripts/jcz_oracle/jcz_driver.py:72  self.cmd = self._launch_cmd(java)
# `java` is a CONSTRUCTOR DEFAULT of the literal string "java". match.py passes
# no `java=`, exposes no `--java` flag, and reads no JAVA env var. So the binary
# is resolved from **PATH, at Popen time, inside each spawn worker**.
#
# Those files are sibling-owned and are NOT patched. Instead this function makes
# PATH resolution DETERMINISTIC and then PROVES it:
#   1. prepend $(dirname $JAVA_BIN) so the pinned binary is first on PATH;
#   2. resolve `command -v java` and compare it to $JAVA_BIN, following symlinks
#      (/usr/bin/java is an alternatives symlink on both boxes);
#   3. ABORT if they differ — a second JVM on PATH is a per-host confound, and
#      `G-JCZ` is a per-host gate;
#   4. RECORD the resolved path and `java -version` into the caller's log.
# Sets: JAVA_RESOLVED, JAVA_VERSION_LINE.
# =============================================================================
resolve_java() {
  [ -x "$JAVA_BIN" ] || { echo "FATAL: JAVA_BIN $JAVA_BIN is not executable on $HOST" >&2; return 25; }
  PATH="$(dirname "$JAVA_BIN"):/usr/bin:$PATH"
  export PATH
  JAVA_RESOLVED="$(command -v java || true)"
  [ -n "$JAVA_RESOLVED" ] || { echo "FATAL: no 'java' on PATH after prepending $(dirname "$JAVA_BIN")" >&2; return 25; }
  if [ "$JAVA_RESOLVED" != "$JAVA_BIN" ]; then
    a="$(readlink -f "$JAVA_RESOLVED" 2>/dev/null || echo "$JAVA_RESOLVED")"
    b="$(readlink -f "$JAVA_BIN"      2>/dev/null || echo "$JAVA_BIN")"
    if [ "$a" != "$b" ]; then
      echo "FATAL: PATH resolves java to '$JAVA_RESOLVED' ($a) but the pin is '$JAVA_BIN' ($b) on $HOST" >&2
      echo "FATAL: match.py has no --java hook, so PATH IS the binding — refusing to play on an unpinned JVM" >&2
      return 25
    fi
  fi
  # ⚠️ `grep -v '^Picked up'` — with `_JAVA_OPTIONS` set (and it always is here,
  # DESIGN §0.1.4) the JVM prints its "Picked up _JAVA_OPTIONS: …" banner on
  # stderr BEFORE the version, so a bare `head -1` records the banner as the
  # version string. That would put the wrong value in every host's `java_version`
  # witness and make the two hosts look identical where G-JCZ wants them compared.
  JAVA_VERSION_LINE="$("$JAVA_BIN" -version 2>&1 | grep -v '^Picked up ' | head -1)"
  export JAVA_RESOLVED JAVA_VERSION_LINE
  return 0
}

# =============================================================================
# jvm_opts_export — the laptop-memory mitigation (DESIGN §0.1.4).
#
# Exported IDENTICALLY on BOTH boxes and BOTH cells so it can never become a box
# confound or a cell confound. The JVM's "Picked up _JAVA_OPTIONS: …" banner goes
# to **stderr**; VERIFIED 2026-08-17 that stderr cannot reach the protocol:
#   jcz_driver.py:66-77  stderr=self._err  — a NamedTemporaryFile, NOT a pipe,
#                        NOT stdout ("stderr goes to a real file, not a pipe")
#   ai_engine.py:222-245 _recv() reads self._p.stdout ONLY, and additionally
#                        requires a parsed JSON object carrying a PROTOCOL_KEYS
#                        member, so even a stray stdout line is skipped, not fatal.
# Neither file is modified.
# =============================================================================
jvm_opts_export() {
  export _JAVA_OPTIONS="$JVM_OPTS"
}

# The number of JCZ AI shim .class files expected on every host (READ_RULE
# G-JCZ; DESIGN §0.1 "10 .class files, byte-identical bytecode on both hosts").
JCZ_SHIM_CLASS_COUNT_EXPECT=10
AI_CLASSES="${JCZ_AI_CLASSES:-$HOME/jcz_spike/ai_classes}"

# The per-host, per-run share subtree. Created lazily by the callers that write.
export HOST IS_LAPTOP SHARE_BASE SHARE_RUN W_BOX W_BOX_SMOKE DECKS_BOX_DEFAULT AI_CLASSES
