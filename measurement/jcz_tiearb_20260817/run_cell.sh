#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — ONE CELL, ONE BOX, ONE DECK SUB-RANGE.
#
#   run_cell.sh <CELL_A|CELL_B name> <seed_base> <n_decks>
#
# Prereg of record: DESIGN.md + READ_RULE.md in this directory, both committed
# BEFORE the band claim and BEFORE game 1.
#
# ⭐ TWO-BOX EXECUTION (OWNER RULING 2026-08-17, DESIGN §0.1). This script now
# plays ONLY the deck sub-range it is handed. `scripts/jcz_match/match.py` has no
# `--shared-claim`, so the two boxes take DISJOINT, CONTIGUOUS ranges through
# `--seed-base` / `--decks`, each with `--champ-seat both`. `launch.sh` computes
# the split ONCE and hands the SAME (seed_base, n_decks) pair to BOTH cells on a
# given box — see `G-SPLIT` below.
#
# The two cells differ in EXACTLY the six `--champ-tiearb-*` arguments, which are
# ABSENT on CELL A and PRESENT on CELL B (DESIGN §3, READ_RULE `G-ARB`). Nothing
# else differs — same band, same decks, same seats, same budget, same rules, same
# jar, same `_JAVA_OPTIONS`, same worker count on a given box. This script is the
# ONLY place that guarantees it, which is why the fully-resolved argv is printed
# to the log before every pass: the diff between the two cells must be auditable
# from the logs alone.
#
# ⚠️ CLAIMS NO BAND. The band is read from the sentinel written by claim_band.sh
# and this script ABORTS if the sentinel is absent — a band that was not claimed
# before game 1 is `G-BAND` = U-UNREADABLE. It ALSO asserts that the sub-range it
# was handed lies inside [BAND, BAND+DECKS-1]: a sub-range outside the band is
# `G-COVER` = U-UNREADABLE and must die here, not in the adjudicator.
#
# ADJUDICATES NOTHING. No strength number is read here, no results.csv row is
# written, no analyzer is run. It plays games and writes a completion marker.
#
# PER-BOX, PER-BAND OUTPUTS (so the two boxes can never write the same file, AND
# this run can never touch the VOIDED first run's artifacts — see FREEZE.md and
# WORKERS.conf::BAND_TAG. Every name below carries `.$BAND_TAG` / `_$BAND_TAG`):
#   $RUN_DIR/<cell>.<host>.<tag>.jsonl                  the shard
#   $SHARE_RUN/<cell>.<host>.<tag>.jsonl                the shard, published for merge
#   $SHARE_RUN/<cell>.<host>.<tag>.hostmap.json         deck_seed -> host  (`G-SPLIT`)
#   $RUN_DIR/DONE_<cell>_<host>_<tag>   + on the share  the completion marker
#   $RUN_DIR/FAILED_<cell>_<host>_<tag> + on the share  the failure marker
# `merge_cells.sh` concatenates the shards into `<cell>.<tag>.jsonl` and verifies
# coverage exactly before anything is adjudicated.
#
# ⛔ THE TOTAL COMMIT FREEZE IS ENFORCED HERE, AND THIS IS THE LAYER WITH TEETH.
# Before game 1 this script compares `git rev-parse HEAD` against the band-claim-
# time sha in `$FREEZE_HEAD_FILE` and ABORTS (rc 26) if they differ, because
# `match.py` stamps `our_git_rev` PER RECORD at record-write time and `G-TOOL`
# conjunct 2 forbids a mixed-rev cell. A cell that has already written records
# under a second rev cannot be un-mixed, so the check must sit ahead of game 1.
# Read FREEZE.md. The voided 2026-08-17 run died on exactly this.
#
# SMOKE MODE (env `SMOKE=1`, driven by `launch.sh --smoke`): the SAME code path
# on a throwaway seed base, into `smoke_<cell>.<host>.jsonl`, at the smoke worker
# count for THIS box. It NEVER reads or writes the band sentinel and NEVER writes
# a DONE/FAILED marker for the real cells. It additionally SAMPLES peak RSS,
# per-worker RSS, JVM count/RSS and loadavg and emits `SMOKE_<host>.json`
# (DESIGN §0.1.3 — the split ratio comes from the smoke; §0.1.4 — W22 against
# 11 GB is validated, never assumed).
#
# DETACH IT. `launch.sh` wraps this box's two calls in one `setsid nohup` chain;
# a Mac-sleep SIGHUP or a WSL VM teardown kills anything tty-attached.
#
# RESUMABLE / IDEMPOTENT: a cell whose DONE marker exists on THIS host is skipped
# with rc=0 and replays nothing; otherwise match.py's `--resume` skips every
# (deck_seed, champ_seat, replicate) already in this host's shard.
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"
. "$HERE/_boxenv.sh"

CELL="${1:?usage: run_cell.sh <$CELL_A|$CELL_B> <seed_base> <n_decks>}"
SEED_BASE="${2:?usage: run_cell.sh <cell> <seed_base> <n_decks>}"
N_DECKS="${3:?usage: run_cell.sh <cell> <seed_base> <n_decks>}"

case "$SEED_BASE" in ''|*[!0-9]*) echo "FATAL: seed_base must be numeric, got '$SEED_BASE'" >&2; exit 2 ;; esac
case "$N_DECKS"   in ''|*[!0-9]*) echo "FATAL: n_decks must be numeric, got '$N_DECKS'"   >&2; exit 2 ;; esac
[ "$N_DECKS" -gt 0 ] || { echo "FATAL: n_decks must be > 0" >&2; exit 2; }

REPO="$REPO_LOCAL"
PY="$REPO/.venv/bin/python"
DRIVER="$REPO/scripts/jcz_match/match.py"
LOGS="$RUN_DIR/logs"
SMOKE="${SMOKE:-0}"
MAXITER="${MAXITER:-20}"

mkdir -p "$LOGS" "$RUN_DIR/verdicts" "$SHARE_RUN"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[jcz-tiearb $(ts) $HOST $CELL] $*"; }
die() { log "FATAL: $*"; exit "${2:-1}"; }

# ---- the cell name is a closed set. A typo must not silently create a third cell.
case "$CELL" in
  "$CELL_A") ARB=no  ;;
  "$CELL_B") ARB=yes ;;
  *) echo "FATAL: cell must be '$CELL_A' or '$CELL_B', got '$CELL'" >&2; exit 2 ;;
esac

# =============================================================================
# ⛔⛔ THE TOTAL COMMIT FREEZE — CHECKED HERE, BEFORE GAME 1, AND IT ABORTS.
#
# FREEZE.md, verbatim: from the moment the band is claimed until the fourth
# DONE_<cell>_<host>_<BAND_TAG> marker exists, NO COMMIT MAY LAND IN THIS
# REPOSITORY — none, of any kind, including docs, measurement/, android/, and
# README typos.
#
# `scripts/jcz_match/match.py` stamps `our_git_rev` PER RECORD at record-write
# time, so ANY commit moves HEAD and splits a cell's records across revisions.
# READ_RULE `G-TOOL` conjunct 2 requires `our_git_rev` to be equal across CELL A
# and CELL B AND consistent within each cell (no mixed-rev cell) — a requirement
# that is SATISFIABLE (a run during which nobody commits satisfies it perfectly)
# and was violated by operator behaviour on 2026-08-17: two docs-only commits
# landed mid-run and produced 3 distinct revs in one cell and 2 in the other.
# The empty wheel-relevant diff did NOT rescue it (DISCLOSURE §3.3).
#
# WHY *BEFORE GAME 1* AND NOT LATER: records written under a second rev cannot be
# un-mixed afterwards. Aborting a cell that has not started costs nothing; a cell
# that starts on a moved HEAD is already void. So this is the one layer that
# refuses to proceed, and it fails CLOSED — a missing FREEZE_HEAD in real mode is
# an abort too, because "no witness" and "HEAD is fine" are not the same claim.
#
# On a RESUME this is exactly right: the freeze runs from the band claim to the
# fourth DONE, so a resume must still be on the band-claim-time HEAD.
# =============================================================================
# ⚠️ The already-DONE case short-circuits FIRST. A cell whose marker exists replays
# NOTHING, so it cannot write a record under any rev at all — aborting it after the
# freeze has legitimately lifted would break the idempotent resume for no safety.
FREEZE_SHA=""
if [ "${SMOKE:-0}" != "1" ] && [ -f "$RUN_DIR/DONE_${CELL}_${HOST}_${BAND_TAG}" ]; then
  echo "[jcz-tiearb] DONE marker present for $CELL on $HOST — freeze check skipped (replays nothing)." >&2
elif [ "${SMOKE:-0}" = "1" ]; then
  FREEZE_SHA="$(freeze_head || true)"
  echo "[jcz-tiearb] SMOKE: freeze check ADVISORY (no band is claimed in smoke mode)." >&2
  echo "[jcz-tiearb]        FREEZE_HEAD=${FREEZE_SHA:-<absent>} HEAD=$(git -C "$REPO_LOCAL" rev-parse HEAD)" >&2
else
  FREEZE_SHA="$(freeze_head || true)"
  HEAD_NOW="$(git -C "$REPO_LOCAL" rev-parse HEAD 2>/dev/null || true)"
  if [ -z "$FREEZE_SHA" ]; then
    {
      echo "!!! FREEZE_HEAD IS ABSENT on $HOST."
      echo "!!!   looked in : $FREEZE_HEAD_FILE"
      echo "!!!   and       : $SHARE_RUN/FREEZE_HEAD"
      echo "!!! launch.sh writes it at band-claim time and publishes it to the share;"
      echo "!!! its absence means either this cell was started outside launch.sh, or"
      echo "!!! the laptop never received it. Either way there is NO witness that HEAD"
      echo "!!! has not moved, and G-TOOL conjunct 2 cannot be honoured on faith."
      echo "!!! REFUSING TO PLAY. (FREEZE.md)"
    } >&2
    exit 26
  fi
  if [ "$HEAD_NOW" != "$FREEZE_SHA" ]; then
    {
      echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
      echo "!!! FREEZE VIOLATION — HEAD HAS MOVED. THIS CELL WILL NOT START."
      echo "!!!   host           $HOST"
      echo "!!!   cell           $CELL"
      echo "!!!   FREEZE_HEAD    $FREEZE_SHA   (stamped at band-claim time)"
      echo "!!!   HEAD now       ${HEAD_NOW:-<unreadable>}"
      echo "!!!"
      echo "!!! match.py stamps our_git_rev PER RECORD, so playing now would write"
      echo "!!! this cell's records under a SECOND revision. G-TOOL conjunct 2 voids"
      echo "!!! a mixed-rev cell, and a mixed cell cannot be un-mixed after the fact."
      echo "!!! That is precisely how the 2026-08-17 run was lost (DISCLOSURE §3)."
      echo "!!!"
      echo "!!! ⛔ DO NOT 'fix' this by re-stamping FREEZE_HEAD. If NO cell has"
      echo "!!!    started yet, the clean remedy is: reset the working state so HEAD"
      echo "!!!    is back at $FREEZE_SHA, or abandon this band and re-launch from"
      echo "!!!    scratch on a fresh one. If cells HAVE already recorded under the"
      echo "!!!    old sha, the run is compromised — disclose it, do not paper it."
      echo "!!! See FREEZE.md and DISCLOSURE.md §3."
      echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    } >&2
    exit 26
  fi
fi

# =============================================================================
# CANONICAL LEAF ENV — copied VERBATIM from
# measurement/tiearb2_stage2_20260817/run_cells.sh (the INTACT v2.9.2 curve125
# champion, leaf hash a36d2e15a3b3d71d). This cell injects NO leaf override on
# either side, so BOTH cells resolve their leaf from exactly this env and
# `G-LEAF` is an EQUALITY gate: the arbiter moves NO leaf hash.
# =============================================================================
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
# ⚠️ R9 is env-latched at IMPORT, so it MUST be exported before the harness starts.
# match.py RAISES if it is off — it is the only configuration in which our engine
# and JCZ are provably rules-identical (DESIGN §2).
export CARCASSONNE_FIX_R9="$FIX_R9"
# READ_RULE G-TOOL: the pinned rust toolchain.
export RUSTUP_TOOLCHAIN="$RUST_TOOLCHAIN"

# =============================================================================
# THE JVM ENVIRONMENT — IDENTICAL ON BOTH BOXES AND BOTH CELLS (DESIGN §0.1.4).
#
# `_JAVA_OPTIONS` caps each JVM heap and forces a single-threaded GC, because
# W=22 on the laptop means 22 python+rust workers AND 22 JVMs against 11 GB, and
# default G1 spawns GC threads per core (24T) — a thread explosion that ends in a
# Windows-side WSL teardown (`reference_wsl2_host_memory_teardown`), which kills
# the whole leg with no Linux-side error.
#
# It is exported UNCONDITIONALLY, on BOTH boxes and in BOTH cells, precisely so
# that it CANNOT become a box confound or a cell confound: applying it only where
# it is needed would put a JVM difference inside the deck-paired difference `D`.
# Heap size and GC policy cannot change LegacyRanking's deterministic arithmetic,
# so JCZ's PLAY is untouched.
#
# The "Picked up _JAVA_OPTIONS: …" banner goes to STDERR, and JCZ's protocol is
# STDOUT-only — verified by reading, not assumed, and neither file is modified:
#   scripts/jcz_oracle/jcz_driver.py:66-77 — stderr is redirected to a real FILE
#       (a NamedTemporaryFile), never to a pipe and never to stdout;
#   scripts/jcz_match/ai_engine.py:222-245 — `_recv()` reads `self._p.stdout`
#       only, and additionally requires a parsed JSON object carrying one of
#       PROTOCOL_KEYS, so a non-protocol stdout line is captured to `log_lines`
#       and skipped rather than parsed.
# =============================================================================
jvm_opts_export
log "_JAVA_OPTIONS=$_JAVA_OPTIONS  (identical on both boxes and both cells)"

# =============================================================================
# THE `java` BINARY. match.py has NO override hook — `java` is a constructor
# DEFAULT of the literal string "java" in jcz_driver.JczEngine.__init__ and is
# resolved from PATH at Popen time inside each spawn worker. Those files are
# sibling-owned and NOT patched. `resolve_java` therefore pins PATH to
# $JAVA_BIN's directory, PROVES `command -v java` resolves to $JAVA_BIN
# (following the alternatives symlink), aborts if it does not, and records the
# resolved path and version into this cell's log. See _boxenv.sh for the full
# chain of custody.
# =============================================================================
resolve_java || die "java resolution failed on $HOST" 25
log "java resolved: $JAVA_RESOLVED  ($JAVA_VERSION_LINE)"
log "java pin     : $JAVA_BIN"

# =============================================================================
# G-JCZ (PER-HOST) — the pinned jar, verified by CONTENT and not by path, ON THIS
# BOX. A jar swapped under us is the one provenance failure that no manifest
# field would catch, because the manifest stamps the path it was handed.
# =============================================================================
[ -f "$JCZ_JAR" ] || die "JCZ jar not found at $JCZ_JAR on $HOST (G-JCZ)"
JAR_SHA="$(sha256sum "$JCZ_JAR" | awk '{print $1}')"
if [ "$JAR_SHA" != "$JCZ_JAR_SHA256" ]; then
  log "!!! G-JCZ VIOLATION on $HOST — Engine.jar sha256 MISMATCH"
  log "!!!   expected $JCZ_JAR_SHA256"
  log "!!!   observed $JAR_SHA"
  log "!!!   path     $JCZ_JAR"
  die "refusing to play against an unpinned JCZ build" 21
fi
log "G-JCZ jar sha256 OK on $HOST ($JAR_SHA)"

# ---- the AI shim must already be present. Without it every `%aimove` is an
# unknown directive JCZ answers with SILENCE, so the fleet HANGS rather than
# failing — exactly how the 2026-08-09 smoke was lost. The classes are COPIED
# (not rebuilt) onto the laptop, so both hosts run byte-identical bytecode.
[ -d "$AI_CLASSES" ] || die "JCZ AI shim classes missing at $AI_CLASSES on $HOST — see DESIGN §0.1" 22
SHIM_N="$(find "$AI_CLASSES" -name '*.class' 2>/dev/null | wc -l | tr -d ' ')"
if [ "$SHIM_N" -ne "$JCZ_SHIM_CLASS_COUNT_EXPECT" ]; then
  die "JCZ shim class count on $HOST is $SHIM_N, expected $JCZ_SHIM_CLASS_COUNT_EXPECT (G-JCZ)" 22
fi
export JCZ_AI_CLASSES="$AI_CLASSES"
log "G-JCZ shim classes OK on $HOST ($SHIM_N at $AI_CLASSES)"

# =============================================================================
# THE BAND — read, never claimed. Sentinel absent ⇒ the band was not claimed
# before game 1 ⇒ `G-BAND` VOIDS the run. Fail closed, here, before game 1.
#
# AND the sub-range is checked against the band: `G-COVER` requires the union of
# the per-box ranges to cover [BAND, BAND+DECKS-1] exactly once per cell, so a
# sub-range that starts before the band or runs past its end is already a void.
# =============================================================================
if [ "$SMOKE" = "1" ]; then
  BAND="(smoke: throwaway)"
  W="$W_BOX_SMOKE"
  # ⚠️ DELIBERATE DEVIATION from "smoke.<host>.jsonl" in the rework brief, and the
  # reason is a correctness bug, not taste: the two cells play the SAME
  # (deck_seed, champ_seat) keys, so a single per-host smoke file would make
  # match.py's `--resume` skip EVERY cell-B game as already-recorded. Cell B
  # would exit instantly at zero cost and the smoke would report a throughput and
  # an RSS that the real CELL B — the expensive one — cannot possibly match. The
  # per-BOX aggregate the brief actually asks for is `SMOKE_<host>.json` below,
  # which spans both cells; only the raw jsonl is split per cell.
  # ⚠️ BAND-TAGGED even in smoke mode, and NOT for tidiness: the VOIDED first run
  # left `smoke_<cell>.<host>.jsonl` in this directory as part of the audit trail,
  # and an accidental `--smoke` must not overwrite it. The re-run overwrites
  # nothing the voided run wrote.
  OUT_JSONL="$RUN_DIR/smoke_${CELL}.${HOST}.${BAND_TAG}.jsonl"
  LOGFILE="$LOGS/smoke_${CELL}.${HOST}.${BAND_TAG}.log"
  log "SMOKE MODE: decks=$N_DECKS seed_base=$SEED_BASE (THROWAWAY, not a claimed band) W=$W"
  log "SMOKE MODE: no band is claimed, no DONE/FAILED marker for the real cell is written"
else
  [ -f "$BAND_SENTINEL" ] || die "band sentinel $BAND_SENTINEL is ABSENT — run claim_band.sh BEFORE game 1 (G-BAND)" 23
  BAND="$(grep -m1 -E '^[0-9]+$' "$BAND_SENTINEL" || true)"
  case "$BAND" in ''|*[!0-9]*) die "band sentinel $BAND_SENTINEL holds no numeric band" 23 ;; esac
  BAND_END=$(( BAND + DECKS - 1 ))
  SUB_END=$(( SEED_BASE + N_DECKS - 1 ))
  if [ "$SEED_BASE" -lt "$BAND" ] || [ "$SUB_END" -gt "$BAND_END" ]; then
    log "!!! G-COVER VIOLATION: sub-range [$SEED_BASE, $SUB_END] is not inside the band [$BAND, $BAND_END]"
    die "refusing to play decks outside the claimed band" 24
  fi
  W="$W_BOX"
  OUT_JSONL="$RUN_DIR/${CELL}.${HOST}.${BAND_TAG}.jsonl"
  LOGFILE="$LOGS/${CELL}.${HOST}.${BAND_TAG}.log"
  log "sub-range [$SEED_BASE, $SUB_END] inside band [$BAND, $BAND_END] — OK"
  # ⚠️ The band the sentinel holds must be the band WORKERS.conf tagged the
  # artifacts for. A `$BAND_TAG` that no longer names `$BAND` would silently
  # label this run's files with another run's identity — the one thing the tag
  # exists to prevent.
  if [ "$BAND" != "$BAND_FLOOR" ]; then
    log "!!! BAND/TAG MISMATCH: sentinel holds $BAND but WORKERS.conf BAND_FLOOR=$BAND_FLOOR"
    log "!!! (artifacts would be tagged '$BAND_TAG'). Refusing to mislabel the run."
    die "resolve WORKERS.conf::BAND_FLOOR/BAND_TAG against $BAND_SENTINEL by hand" 24
  fi
fi
TARGET=$(( N_DECKS * 2 ))          # --champ-seat both ⇒ two games per deck

# ---- EVERY artifact carries $BAND_TAG. See FREEZE.md / WORKERS.conf::BAND_TAG:
# the VOIDED first run's files sit in this same directory and on this same share
# as the audit trail, and NOTHING here may collide with them.
SHARE_JSONL="$SHARE_RUN/$(basename "$OUT_JSONL")"
DONE_MARKER="$RUN_DIR/DONE_${CELL}_${HOST}_${BAND_TAG}"
FAIL_MARKER="$RUN_DIR/FAILED_${CELL}_${HOST}_${BAND_TAG}"
SHARE_DONE="$SHARE_RUN/DONE_${CELL}_${HOST}_${BAND_TAG}"
SHARE_FAIL="$SHARE_RUN/FAILED_${CELL}_${HOST}_${BAND_TAG}"
HOSTMAP="$RUN_DIR/${CELL}.${HOST}.${BAND_TAG}.hostmap.json"
SHARE_HOSTMAP="$SHARE_RUN/${CELL}.${HOST}.${BAND_TAG}.hostmap.json"

# ---- IDEMPOTENCE: a finished cell ON THIS HOST replays nothing.
if [ "$SMOKE" != "1" ] && [ -f "$DONE_MARKER" ]; then
  log "DONE marker already present at $DONE_MARKER — nothing to do, exiting 0"
  exit 0
fi

GIT_HEAD="$(git -C "$REPO" rev-parse HEAD)"

# =============================================================================
# THE ARGV. Common to both cells; CELL B additionally and ONLY gets the six
# `--champ-tiearb-*` arguments (DESIGN §3, READ_RULE `G-ARB`).
# =============================================================================
ARGS=(--decks "$N_DECKS"
      --seed-base "$SEED_BASE"
      --champ-seat both
      --workers "$W"
      --jar "$JCZ_JAR"
      --ai-classes "$AI_CLASSES"
      --ai-class "$JCZ_AI_CLASS"
      --out "$OUT_JSONL"
      --resume)

if [ "$ARB" = "yes" ]; then
  ARGS+=(--champ-tiearb-enabled
         --champ-tiearb-b "$TIEARB_B"
         --champ-tiearb-j "$TIEARB_J"
         --champ-tiearb-mode "$TIEARB_MODE"
         --champ-tiearb-salt "$TIEARB_SALT"
         --champ-tiearb-eps "$TIEARB_EPS")
fi

# =============================================================================
# THE HOST STAMP (`G-SPLIT`). The records themselves carry no host field and
# `match.py` is sibling-owned and NOT modified to add one. Instead every deck in
# THIS sub-range is written to a sidecar mapping deck_seed -> hostname, next to
# the shard on the share. `merge_cells.sh` merges the sidecars per cell and
# `adjudicate.py` gates `G-SPLIT` — the deck→host assignment must be IDENTICAL
# across CELL A and CELL B (DESIGN §0.1.2), because `D` is deck-paired and any
# per-box difference that landed on one side of the pairing only would be
# arithmetically indistinguishable from the arbiter's effect.
#
# Written BEFORE game 1 (declaration) and refreshed at the end (with the realized
# record count), so a crashed leg still leaves its claim on record.
# =============================================================================
write_hostmap() {
  local state="$1" got="$2"
  CELL="$CELL" HOSTNAME_="$HOST" SEED_BASE="$SEED_BASE" N_DECKS="$N_DECKS" \
  BAND_="$BAND" GIT_HEAD="$GIT_HEAD" STATE="$state" GOT="$got" \
  OUT_JSONL="$OUT_JSONL" WW="$W" SMOKE_="$SMOKE" \
  BAND_TAG_="$BAND_TAG" FREEZE_SHA_="${FREEZE_SHA:-}" \
    "$PY" - > "$HOSTMAP".tmp <<'PYEOF'
import json, os, sys, datetime
sb = int(os.environ["SEED_BASE"]); n = int(os.environ["N_DECKS"])
host = os.environ["HOSTNAME_"]
doc = {
    "witness": "G-SPLIT",
    "cell": os.environ["CELL"],
    "host": host,
    "band": os.environ["BAND_"],
    "seed_base": sb,
    "n_decks": n,
    "deck_range": [sb, sb + n - 1],
    "games_expected": n * 2,
    "records_observed": int(os.environ["GOT"]),
    "state": os.environ["STATE"],
    "smoke": os.environ["SMOKE_"] == "1",
    "workers": int(os.environ["WW"]),
    "shard": os.environ["OUT_JSONL"],
    "git_head": os.environ["GIT_HEAD"],
    # ⚠️ neither key is a `parse_hostmap_doc` wrapper name ("hostmap", "host_map",
    # "decks", "deck_hosts"), so adding them cannot change which object G-SPLIT reads.
    "band_tag": os.environ["BAND_TAG_"],
    "freeze_head": os.environ["FREEZE_SHA_"] or None,
    "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    # ⚠️ THE KEY MUST BE `hostmap`. `adjudicate.py::parse_hostmap_doc` accepts the
    # wrappers ("hostmap", "host_map", "decks", "deck_hosts") and a BARE
    # deck→host object, and treats anything else as an UNPARSEABLE sidecar, which
    # VOIDS `G-SPLIT` ("a split that cannot be READ is exactly the unverifiable
    # split the gate exists to catch"). `hostmap` is the first wrapper it tries.
    # The mapping itself: every deck this box is responsible for, in THIS cell.
    "hostmap": {str(sb + i): host for i in range(n)},
}
json.dump(doc, sys.stdout, indent=1)
print()
PYEOF
  mv -f "$HOSTMAP".tmp "$HOSTMAP"
  cp -f "$HOSTMAP" "$SHARE_HOSTMAP" 2>/dev/null || log "WARN: could not publish hostmap to $SHARE_HOSTMAP"
}

# ⚠️ `if`, not `&& || `: under `set -e` an AND-OR list whose first command fails
# is a failed command, and this function is called from loop conditions.
count_records() {
  if [ -f "$OUT_JSONL" ]; then wc -l < "$OUT_JSONL" | tr -d ' '; else echo 0; fi
}

publish_shard() {
  cp -f "$OUT_JSONL" "$SHARE_JSONL" 2>/dev/null \
    || log "WARN: could not publish shard to $SHARE_JSONL (merge_cells.sh will fall back to $RUN_DIR)"
}

# =============================================================================
# SMOKE SAMPLER (smoke only) — the numbers that set DECKS_LOCAL/DECKS_LAPTOP and
# validate W=$W_LAPTOP against the laptop's 11 GB (DESIGN §0.1.3, §0.1.4).
# Bench, THEN extrapolate, THEN commit — never the other way round.
#
# Appends one CSV row every 5 s to a per-HOST file that spans BOTH cells, so the
# peaks in SMOKE_<host>.json are the box's true peaks over the whole smoke.
# =============================================================================
# (band-tagged for the same reason as the smoke jsonl: the voided run's
# SMOKE_<host>.* files are audit-trail artifacts and must not be overwritten.)
SMOKE_CSV="$RUN_DIR/SMOKE_${HOST}.${BAND_TAG}.samples.csv"
SMOKE_TIMING="$RUN_DIR/SMOKE_${HOST}.${BAND_TAG}.timing.csv"
SMOKE_JSON="$RUN_DIR/SMOKE_${HOST}.${BAND_TAG}.json"
SAMPLER_PID=""

start_sampler() {
  [ -f "$SMOKE_CSV" ] || echo "utc,cell,n_workers,rss_workers_kb,rss_worker_max_kb,n_jvm,rss_jvm_kb,rss_jvm_max_kb,rss_total_kb,load1,mem_avail_kb" > "$SMOKE_CSV"
  (
    while true; do
      wpids="$(pgrep -f 'jcz_match/match\.py' 2>/dev/null || true)"
      jpids="$(pgrep -f "$JCZ_AI_CLASS" 2>/dev/null || true)"
      wsum=0; wmax=0; wn=0
      if [ -n "$wpids" ]; then
        # shellcheck disable=SC2086
        read -r wn wsum wmax <<<"$(ps -o rss= -p $(echo "$wpids" | tr '\n' ',' | sed 's/,$//') 2>/dev/null \
          | awk '{n++; s+=$1; if($1>m) m=$1} END{printf "%d %d %d", n+0, s+0, m+0}')"
      fi
      jsum=0; jmax=0; jn=0
      if [ -n "$jpids" ]; then
        # shellcheck disable=SC2086
        read -r jn jsum jmax <<<"$(ps -o rss= -p $(echo "$jpids" | tr '\n' ',' | sed 's/,$//') 2>/dev/null \
          | awk '{n++; s+=$1; if($1>m) m=$1} END{printf "%d %d %d", n+0, s+0, m+0}')"
      fi
      tot=$(( wsum + jsum ))
      l1="$(cut -d' ' -f1 /proc/loadavg)"
      ma="$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)"
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),$CELL,$wn,$wsum,$wmax,$jn,$jsum,$jmax,$tot,$l1,$ma" >> "$SMOKE_CSV"
      sleep 5
    done
  ) &
  SAMPLER_PID=$!
  log "smoke sampler pid=$SAMPLER_PID -> $SMOKE_CSV (5 s cadence)"
}

stop_sampler() {
  if [ -n "$SAMPLER_PID" ]; then
    kill "$SAMPLER_PID" 2>/dev/null || true
    wait "$SAMPLER_PID" 2>/dev/null || true
    SAMPLER_PID=""
  fi
}
trap 'stop_sampler' EXIT

{
  echo "==================================================================="
  echo "[jcz-tiearb $(ts)] CELL=$CELL arbiter=$ARB host=$HOST smoke=$SMOKE"
  echo "[jcz-tiearb] band=$BAND sub_range_base=$SEED_BASE decks=$N_DECKS target_games=$TARGET"
  echo "[jcz-tiearb] workers=$W nice=$NICE  (W resolved from WORKERS.conf by hostname)"
  echo "[jcz-tiearb] repo_head=$GIT_HEAD"
  echo "[jcz-tiearb] FREEZE_HEAD=${FREEZE_SHA:-<n/a: smoke or already-DONE>}  (TOTAL COMMIT FREEZE, FREEZE.md)"
  echo "[jcz-tiearb] band_tag=$BAND_TAG  (every artifact of this run carries it)"
  echo "[jcz-tiearb] java=$JAVA_RESOLVED  ($JAVA_VERSION_LINE)"
  echo "[jcz-tiearb] _JAVA_OPTIONS=$_JAVA_OPTIONS"
  echo "[jcz-tiearb] jar=$JCZ_JAR sha256=$JAR_SHA ai_class=$JCZ_AI_CLASS ai_classes=$AI_CLASSES ($SHIM_N classes)"
  echo "[jcz-tiearb] rules: profile=$RULES_PROFILE (hard-coded in match.py) CARCASSONNE_FIX_R9=$CARCASSONNE_FIX_R9"
  echo "[jcz-tiearb] leaf of record (EQUALITY gate G-LEAF): $CHAMP_LEAF_HASH"
  echo "[jcz-tiearb] shard=$OUT_JSONL  share=$SHARE_JSONL"
  echo "[jcz-tiearb] RESOLVED ARGV:"
  echo "[jcz-tiearb]   $PY -u $DRIVER ${ARGS[*]}"
  echo "==================================================================="
} | tee -a "$LOGFILE"

log "starting — full log $LOGFILE"
write_hostmap "STARTED" "$(count_records)"
# ⚠️ `if`, not `[ … ] && …`: under `set -e` a false AND-OR list at top level is a
# failed command and would kill the cell before game 1.
if [ "$SMOKE" = "1" ]; then start_sampler; fi

rc=0
iter=0
t0=$(date +%s)
prev=$(count_records)
while [ "$(count_records)" -lt "$TARGET" ] && [ "$iter" -lt "$MAXITER" ]; do
  set +e
  nice -n "$NICE" "$PY" -u "$DRIVER" "${ARGS[@]}" >> "$LOGFILE" 2>&1
  rc=$?
  set -e
  iter=$((iter + 1))
  got=$(count_records)
  log "pass $iter rc=$rc records=$got/$TARGET"
  if [ "$got" -le "$prev" ] && [ "$rc" -eq 0 ]; then
    log "pass $iter made NO progress at rc=0 — the remaining cells are unplayable, not stalled; stopping"
    break
  fi
  prev="$got"
  if [ "$got" -lt "$TARGET" ]; then sleep 5; fi   # short poll sleep, < 10 s by house rule
done
secs=$(( $(date +%s) - t0 ))
GOT=$(count_records)
stop_sampler
log "END records=$GOT/$TARGET in ${secs}s after $iter pass(es), last rc=$rc"

publish_shard
write_hostmap "$([ "$GOT" -ge "$TARGET" ] && echo COMPLETE || echo SHORT)" "$GOT"

# =============================================================================
# SMOKE CLOSE-OUT — the per-BOX report the split ratio and the memory decision
# are read off (DESIGN §0.1.3 / §0.1.4). Spans BOTH cells on this box.
# =============================================================================
if [ "$SMOKE" = "1" ]; then
  [ -f "$SMOKE_TIMING" ] || echo "cell,host,workers,decks,games_target,games_recorded,elapsed_s,last_rc" > "$SMOKE_TIMING"
  echo "$CELL,$HOST,$W,$N_DECKS,$TARGET,$GOT,$secs,$rc" >> "$SMOKE_TIMING"

  SM_HOST="$HOST" SM_W="$W" SM_WSMOKE="$W_BOX_SMOKE" SM_CSV="$SMOKE_CSV" \
  SM_TIMING="$SMOKE_TIMING" SM_GIT="$GIT_HEAD" SM_JVMOPTS="$_JAVA_OPTIONS" \
  SM_JAVA="$JAVA_RESOLVED" SM_JAVAV="$JAVA_VERSION_LINE" \
  SM_WREAL_LOCAL="$W_LOCAL" SM_WREAL_LAPTOP="$W_LAPTOP" \
    "$PY" - > "$SMOKE_JSON".tmp <<'PYEOF'
import csv, json, os, sys, datetime

csv_path = os.environ["SM_CSV"]
rows = []
try:
    with open(csv_path) as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
except FileNotFoundError:
    pass

def imax(key):
    vals = [int(r[key]) for r in rows if r.get(key, "").strip().isdigit()]
    return max(vals) if vals else 0

def fmax(key):
    vals = []
    for r in rows:
        try:
            vals.append(float(r[key]))
        except (TypeError, ValueError):
            pass
    return max(vals) if vals else 0.0

def imin(key):
    vals = [int(r[key]) for r in rows if r.get(key, "").strip().isdigit()]
    return min(vals) if vals else 0

timing = []
try:
    with open(os.environ["SM_TIMING"]) as fh:
        timing = list(csv.DictReader(fh))
except FileNotFoundError:
    pass

per_cell = []
for t in timing:
    games = int(t["games_recorded"] or 0)
    el = float(t["elapsed_s"] or 0)
    per_cell.append({
        "cell": t["cell"],
        "workers": int(t["workers"]),
        "decks": int(t["decks"]),
        "games_target": int(t["games_target"]),
        "games_recorded": games,
        "elapsed_s": el,
        # WALL seconds per game at this W — the throughput number the split
        # ratio is computed from. Multiply by W for worker-seconds/game.
        "s_per_game_wall": round(el / games, 3) if games else None,
        "worker_s_per_game": round(el * int(t["workers"]) / games, 1) if games else None,
        "last_rc": int(t["last_rc"]),
    })

doc = {
    "witness": "SMOKE (DESIGN §0.1.3 split ratio, §0.1.4 laptop memory)",
    "host": os.environ["SM_HOST"],
    "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "git_head": os.environ["SM_GIT"],
    "workers_smoke": int(os.environ["SM_WSMOKE"]),
    "workers_production_local": int(os.environ["SM_WREAL_LOCAL"]),
    "workers_production_laptop": int(os.environ["SM_WREAL_LAPTOP"]),
    "java": os.environ["SM_JAVA"],
    "java_version": os.environ["SM_JAVAV"],
    "_JAVA_OPTIONS": os.environ["SM_JVMOPTS"],
    "n_samples": len(rows),
    "sample_csv": csv_path,
    # ---- peaks over the WHOLE smoke on this box (both cells) ----
    "peak_rss_total_kb": imax("rss_total_kb"),
    "peak_rss_total_gb": round(imax("rss_total_kb") / 1048576.0, 2),
    "peak_rss_worker_max_kb": imax("rss_worker_max_kb"),
    "peak_rss_workers_sum_kb": imax("rss_workers_kb"),
    "peak_n_workers": imax("n_workers"),
    "peak_n_jvm": imax("n_jvm"),
    "peak_rss_jvm_sum_kb": imax("rss_jvm_kb"),
    "peak_rss_jvm_max_kb": imax("rss_jvm_max_kb"),
    "peak_load1": fmax("load1"),
    "min_mem_available_kb": imin("mem_avail_kb"),
    "min_mem_available_gb": round(imin("mem_avail_kb") / 1048576.0, 2),
    "per_cell": per_cell,
    "note": (
        "s_per_game_wall is the per-box throughput the DECKS_LOCAL/DECKS_LAPTOP "
        "split is set from (DESIGN §0.1.3). peak_rss_* validate W against this "
        "box's RAM (DESIGN §0.1.4). If W does not fit, that is REPORTED TO THE "
        "OWNER, never silently reduced — W is an owner-set value."),
}
json.dump(doc, sys.stdout, indent=1)
print()
PYEOF
  mv -f "$SMOKE_JSON".tmp "$SMOKE_JSON"
  cp -f "$SMOKE_JSON" "$SHARE_RUN/" 2>/dev/null || true
  cp -f "$SMOKE_CSV" "$SMOKE_TIMING" "$SHARE_RUN/" 2>/dev/null || true
  log "smoke report -> $SMOKE_JSON (peaks span BOTH cells on $HOST)"
  cat "$SMOKE_JSON" || true
  if [ "$GOT" -ge "$TARGET" ]; then exit 0; fi
  exit 11
fi

if [ "$GOT" -ge "$TARGET" ]; then
  {
    echo "cell $CELL"
    echo "host $HOST"
    echo "band $BAND"
    echo "seed_base $SEED_BASE"
    echo "n_decks $N_DECKS"
    echo "deck_range $SEED_BASE..$(( SEED_BASE + N_DECKS - 1 ))"
    echo "games_requested $TARGET"
    echo "games_recorded $GOT"
    echo "record_count $GOT"
    echo "utc $(ts)"
    echo "git_head $GIT_HEAD"
    echo "freeze_head ${FREEZE_SHA:-<none>}  <-- TOTAL COMMIT FREEZE (FREEZE.md); equal to git_head above by construction"
    echo "band_tag $BAND_TAG"
    echo "workers $W"
    echo "elapsed_s $secs"
    echo "passes $iter"
    echo "out $OUT_JSONL"
    echo "share_out $SHARE_JSONL"
    echo "hostmap $SHARE_HOSTMAP"
    echo "arbiter $ARB"
    echo "java $JAVA_RESOLVED"
    echo "java_version $JAVA_VERSION_LINE"
    echo "_JAVA_OPTIONS $_JAVA_OPTIONS"
    if [ "$ARB" = "yes" ]; then
      echo "champ_tiearb enabled=true B=$TIEARB_B J=$TIEARB_J mode=$TIEARB_MODE salt=$TIEARB_SALT eps=$TIEARB_EPS"
    else
      echo "champ_tiearb ABSENT (G-ARB: CELL A must carry NO champ_tiearb key)"
    fi
    echo "jcz_jar_sha256 $JAR_SHA"
    echo "jcz_shim_classes $SHIM_N"
    echo "cand_leaf_hash_expected $CHAMP_LEAF_HASH  <-- EQUALITY: this surface moves NO leaf hash"
    echo "PARTIAL BY DESIGN — this is ONE BOX's shard. Run merge_cells.sh before any read."
    echo "NOT ADJUDICATED — read READ_RULE.md §3 preconditions before any number."
  } | tee "$DONE_MARKER" > "$SHARE_DONE"
  log "DONE ($GOT/$TARGET) -> $DONE_MARKER and $SHARE_DONE"
  rm -f "$FAIL_MARKER" "$SHARE_FAIL"
  exit 0
fi

{
  echo "cell $CELL"
  echo "host $HOST"
  echo "band $BAND"
  echo "seed_base $SEED_BASE"
  echo "n_decks $N_DECKS"
  echo "games_requested $TARGET"
  echo "games_recorded $GOT"
  echo "record_count $GOT"
  echo "exit_code $rc"
  echo "passes $iter"
  echo "elapsed_s $secs"
  echo "utc $(ts)"
  echo "git_head $GIT_HEAD"
  echo "freeze_head ${FREEZE_SHA:-<none>}"
  echo "band_tag $BAND_TAG"
  echo "workers $W"
  echo "log $LOGFILE"
  echo "out $OUT_JSONL"
  echo "resume with: $0 $CELL $SEED_BASE $N_DECKS   (match.py --resume skips what is already recorded)"
} | tee "$FAIL_MARKER" > "$SHARE_FAIL"
log "!!! FAILED ($GOT/$TARGET, rc=$rc) -> $FAIL_MARKER and $SHARE_FAIL"
exit 11
