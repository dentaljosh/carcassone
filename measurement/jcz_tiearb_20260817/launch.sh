#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — THE ONE COMMAND THAT RUNS THE WHOLE THING, ON TWO BOXES.
#
#   ./launch.sh              the real run: 2 cells x 400 decks x 2 seats = 1600 games
#   ./launch.sh --smoke      the SAME path at 4 decks/cell/box on a throwaway base
#
# Prereg of record: DESIGN.md + READ_RULE.md in this directory, both committed
# BEFORE the band claim and BEFORE game 1.
#
# ⭐⭐ TWO BOXES, BY OWNER RULING (2026-08-17, verbatim: "make sure its both
# boxes, w22 and w30 respectively"). DESIGN §0.1 is the operative text; §6.3's
# single-box deviation is OVERRIDDEN and retained only as an audit trail. The
# ruling was made with the band UNCLAIMED and NO game played, so the blind
# ordering is intact and no adjudicating bar moves.
#
# EXECUTION MODEL (DESIGN §0.1.1). `scripts/jcz_match/match.py` has NO
# `--shared-claim`, so each box takes a DISJOINT, CONTIGUOUS deck range through
# `--seed-base` / `--decks` with `--champ-seat both`. BOTH BOXES RUN
# CONCURRENTLY; WITHIN A BOX THE TWO CELLS RUN SEQUENTIALLY (running them
# concurrently would halve each cell's workers and destroy the throughput and RSS
# readings the smoke exists to take).
#
# ORDER, ENFORCED, each step failing loudly and stopping:
#   1. CENSUS BOTH BOXES. A timing-sensitive, DRAM-bound cell is an EXCLUSIVE
#      tenant. If a solver/eval/match leg is live ON EITHER BOX we ABORT and tell
#      the operator to wait — we NEVER kill anything we did not start.
#   2. TREE + the `--champ-tiearb-*` probe. HARD on the local box; on the laptop
#      it is recorded but ADVISORY here, because the laptop cannot possibly have
#      the plumbing until step 3 syncs it. See step 3b.
#   3. BUNDLE-SYNC THE LAPTOP to the launch commit, and VERIFY its HEAD equals
#      ours. HARD PREREQUISITE: stale code on the laptop is a MIXED-REV CELL, and
#      a mixed-rev cell is exactly the thing `G-TOOL` exists to void.
#   3b. RE-PROBE `--champ-tiearb-*` on the laptop, now HARD.
#   4. CLAIM THE BAND (idempotent via the sentinel, LOCAL ONLY — the band is then
#      passed to both boxes). Skipped in --smoke. ⛔ THE TOTAL COMMIT FREEZE
#      STARTS HERE, and this step stamps `$RUN_DIR/FREEZE_HEAD` + publishes it to
#      the share so both boxes can check themselves against it. Read FREEZE.md.
#   5. PRE-FLIGHT ON BOTH BOXES (`G-J13`, `G-JCZ`, `G-TOOL` are PER-HOST,
#      READ_RULE §0.F.1). Abort if EITHER fails. Verdicts synced to the share.
#   6. LAUNCH one detached chain PER BOX: CELL A's sub-range then CELL B's.
#   7. ARM THE WATCHDOG, detached, ON BOTH BOXES.
#   8. PRINT pids / logs / every marker path, and EXIT. It does not wait.
#
# ⚠️⚠️ WHY THE PRE-FLIGHT SITS AT STEP 5 AND NOT ANYWHERE ELSE (READ_RULE §3.1).
#   `G-TOOL` requires
#       git diff --name-only <preflight_commit>..<manifest_commit> -- rust/ src/ engine/ scripts/
#   to be EMPTY or the range DEGENERATE. So the pre-flight must be generated
#   AFTER any wheel rebuild AND AFTER the bundle sync, and BEFORE the detached
#   launch. Stage 2's `launch_both.sh` had NO pre-flight step: it rebuilt the
#   wheel and launched, so HEAD moved between the pre-flight and the manifest on
#   EVERY healthy run and `G-TOOL` was unsatisfiable by construction — that
#   defect cost Stage 2 an adjudication. It is FIXED here, not inherited: this
#   script generates the pre-flight itself, at step 5, on BOTH boxes, and ASSERTS
#   that HEAD has not moved on either box between the pre-flight and the launch.
#
# ⚠️ IT REBUILDS NO WHEEL, ON EITHER BOX. If a rebuild is needed, do it BEFORE
#   running this script — that ordering is exactly what keeps the commit range
#   degenerate. The laptop's wheel must be rebuilt AFTER its bundle sync, so the
#   sequence for a code change is: commit → `git bundle` + `sync.sh` (or one
#   throwaway `./launch.sh` that aborts at step 5) → rebuild on the laptop →
#   `./launch.sh`. The per-host `G-J13` pre-flight is what CATCHES a stale wheel:
#       RUSTUP_TOOLCHAIN=<from WORKERS.conf> .venv/bin/maturin develop --release \
#           -m rust/carc/carc-py/Cargo.toml
#
# ⚠️ SSH DISCIPLINE (house-critical, all three traps).
#   * EVERY multi-step remote command is `ssh $LAPTOP_HOST 'bash -s' < script.sh`
#     with `cd` on line 1. The inline `ssh host 'cd X && …'` form gets the `cd`
#     STRIPPED in transit — a documented Claude Code failure mode that persists
#     through correction, so retrying the inline form cannot work.
#   * The share path DIFFERS BY BOX: `$SHARE_LOCAL` locally, `$SHARE_REMOTE`
#     inside ssh. They are never crossed. (`/mnt/c/carc-shared` exists on BOTH
#     boxes and points at different disks, so "whichever exists" is WRONG.)
#   * A detached ssh launch can return rc=124 from `timeout` AFTER successfully
#     launching. 124 is treated as LAUNCHED and is NEVER retried — a retry stacks
#     a second worker pool on the box.
#   * The remote launch CALL is backgrounded, because a synchronous
#     `ssh host "job &"` can hang and starve every box launched after it.
#
# ADJUDICATES NOTHING. No results.csv row, no analyzer, no PRODUCTION.yaml.
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"
. "$HERE/_boxenv.sh"

MODE=real
case "${1:-}" in
  "")        ;;
  --smoke)   MODE=smoke ;;
  -h|--help) sed -n '2,98p' "$0"; exit 0 ;;
  *) echo "usage: launch.sh [--smoke]" >&2; exit 2 ;;
esac

REPO="$REPO_LOCAL"
PY="$REPO/.venv/bin/python"
LOGS="$RUN_DIR/logs"
mkdir -p "$LOGS" "$RUN_DIR/verdicts" "$SHARE_RUN/verdicts"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[launch $(ts)] $*"; }
die() { log "FATAL: $*"; exit "${2:-1}"; }

# This script must run on the LOCAL box: it claims the band, creates the bundle
# on `$SHARE_LOCAL`, and drives the laptop over ssh.
if [ "$IS_LAPTOP" = "1" ]; then
  die "launch.sh runs on the LOCAL box only (it drives $LAPTOP_HOST over ssh); this is $HOST" 2
fi

SMOKE_DECKS="${SMOKE_DECKS:-4}"
SMOKE_SEED_BASE="${SMOKE_SEED_BASE:-900000200000}"

log "=== jcz_tiearb_20260817 — out-of-lineage pricing of the tie arbiter (mode=$MODE) ==="
log "TWO BOXES by owner ruling: $HOST (W=$W_LOCAL) + $LAPTOP_HOST (W=$W_LAPTOP), CONCURRENT"
log "cells within a box: $CELL_A (champion) then $CELL_B (champion + arbiter), SEQUENTIAL"

# =============================================================================
# 1. CENSUS — BOTH BOXES, BY DEFAULT, and ABORT rather than kill.
# =============================================================================
log "--- 1. CENSUS (both boxes) ---"

# ⚠️ The pattern requires the `.py` SUFFIX, and shell wrappers are filtered out.
# A watcher shell (`until ! pgrep -f reconcile_exact_solver; do ...`) carries the
# bare name in its own argv and would otherwise read as a live compute leg and
# block the launch forever. The real legs are `.../reconcile_exact_solver.py`.
BUSY_PAT='reconcile_exact_solver\.py|eval_fair_puct\.py|match\.py'

echo "=== LOCAL ($HOST) ==="
ps -eo pid,etime,pcpu,rss,args --sort=-etime 2>/dev/null \
  | grep -iE 'python|java' | grep -v ' grep ' | head -30 || true
echo "--- /proc/loadavg ---"; cat /proc/loadavg
echo "--- free -g ---";       free -g

BUSY_LOCAL="$(pgrep -af "$BUSY_PAT" 2>/dev/null \
        | grep -v -e 'shell-snapshots' -e 'pgrep' -e 'until !' || true)"

cat > "$LOGS/_census_laptop.sh" <<EOF
cd $REPO_REMOTE || exit 1
echo "=== LAPTOP (\$(hostname)) ==="
ps -eo pid,etime,pcpu,rss,args --sort=-etime 2>/dev/null | grep -iE 'python|java' | grep -v ' grep ' | head -30
echo "--- /proc/loadavg ---"; cat /proc/loadavg
echo "--- free -g ---";       free -g
pgrep -af '$BUSY_PAT' 2>/dev/null | grep -v -e 'shell-snapshots' -e 'pgrep' -e 'until !' | sed 's/^/BUSY:/' || true
EOF
LAPTOP_CENSUS="$(timeout 120 ssh "$LAPTOP_HOST" 'bash -s' < "$LOGS/_census_laptop.sh" 2>&1)" \
  || die "$LAPTOP_HOST unreachable or census failed — fix the box before launching a 2-box cell:
$LAPTOP_CENSUS" 4
echo "$LAPTOP_CENSUS"
BUSY_LAPTOP="$(echo "$LAPTOP_CENSUS" | grep '^BUSY:' || true)"

if [ -n "$BUSY_LOCAL" ] || [ -n "$BUSY_LAPTOP" ]; then
  log "!!! A COMPUTE LEG IS ALIVE:"
  # ⚠️ `if`, not `[ … ] && { … }`: under `set -e` a false AND-OR list would kill
  # the script with rc=1 before the explanation and the deliberate `exit 3`.
  if [ -n "$BUSY_LOCAL" ];  then echo "  --- on $HOST ---";        echo "$BUSY_LOCAL"  | sed 's/^/    /'; fi
  if [ -n "$BUSY_LAPTOP" ]; then echo "  --- on $LAPTOP_HOST ---"; echo "$BUSY_LAPTOP" | sed 's/^/    /'; fi
  log "!!! ABORTING. This cell is DRAM-bound at W=$W_LOCAL / W=$W_LAPTOP and is an"
  log "!!! EXCLUSIVE tenant on BOTH boxes: sharing either one would corrupt the"
  log "!!! throughput measurement, the neighbouring run, AND — because a busy box"
  log "!!! is a SLOW box — the per-box split ratio itself"
  log "!!! (feedback_no_agent_compute_beside_eval)."
  log "!!! WAIT for the live leg to finish. Do NOT kill it — this script never does."
  exit 3
fi
log "census clean on BOTH boxes"

# =============================================================================
# 2. TREE + THE ENABLING-CHANGE PROBE (local HARD, laptop advisory-until-sync)
# =============================================================================
log "--- 2. TREE ---"
HEAD_BEFORE="$(git -C "$REPO" rev-parse HEAD)"
log "local git HEAD = $HEAD_BEFORE"

[ -x "$PY" ] || die "no venv python at $PY"
MATCH_PY="$REPO/scripts/jcz_match/match.py"
[ -f "$MATCH_PY" ] || die "driver missing at $MATCH_PY"

TIEARB_FLAGS="--champ-tiearb-enabled --champ-tiearb-b --champ-tiearb-j \
--champ-tiearb-mode --champ-tiearb-salt --champ-tiearb-eps"

# ⚠️ THE STRUCTURAL ZERO GUARD. If the `--champ-tiearb-*` plumbing is not merged,
# CELL B is a byte-identical second copy of CELL A and D is zero BY CONSTRUCTION —
# a perfect champion-vs-champion null wearing the shape of a real cell. Probe the
# real parser, not the source text. AND probe it on BOTH boxes: a laptop running
# pre-plumbing code would make HALF of CELL B a structural zero, which is worse
# than all of it, because the halves would not even be self-consistent.
log "probing $MATCH_PY --help for the six --champ-tiearb-* flags (local)"
HELP="$("$PY" "$MATCH_PY" --help 2>&1 || true)"
# shellcheck disable=SC2086  # deliberate word-splitting: TIEARB_FLAGS is a list
for flag in $TIEARB_FLAGS; do
  case "$HELP" in
    *"$flag"*) ;;
    *) log "!!! $MATCH_PY on $HOST does NOT accept $flag"
       log "!!! The enabling change (DESIGN §6.1) must be MERGED before launch:"
       log "!!! without it CELL B runs as a second copy of CELL A and D is a"
       log "!!! STRUCTURAL ZERO that no gate downstream could distinguish from a null."
       exit 4 ;;
  esac
done
log "all six --champ-tiearb-* flags present on $HOST"

cat > "$LOGS/_probe_laptop.sh" <<EOF
cd $REPO_REMOTE || exit 1
echo "REMOTE_HEAD=\$(git -C $REPO_REMOTE rev-parse HEAD)"
H="\$($REPO_REMOTE/.venv/bin/python $REPO_REMOTE/scripts/jcz_match/match.py --help 2>&1 || true)"
miss=0
for f in $TIEARB_FLAGS; do
  case "\$H" in *"\$f"*) ;; *) echo "MISSING_FLAG:\$f"; miss=1 ;; esac
done
echo "PROBE_RC=\$miss"
EOF
# ADVISORY here by construction: the laptop cannot have the plumbing until step 3
# syncs it, so failing hard at this point would make a first-time launch
# impossible. Step 3b re-probes and IS hard.
PROBE_PRE="$(timeout 180 ssh "$LAPTOP_HOST" 'bash -s' < "$LOGS/_probe_laptop.sh" 2>&1 || true)"
log "laptop pre-sync probe (ADVISORY): $(echo "$PROBE_PRE" | tr '\n' ' ')"

# =============================================================================
# 3. BUNDLE-SYNC THE LAPTOP TO THE LAUNCH COMMIT — HARD PREREQUISITE.
#
# The remotes cannot reach github (no DNS over Tailscale), so `git push`/`pull`
# does not work: the house mechanism is a `git bundle` on the CIFS share plus
# `git fetch <bundle>` + `git reset --hard` on the remote
# (`reference_offline_git_bundle_sync`). A FULL bundle, not a shallow one — a
# shallow bundle gives a parentless `code_rev` and makes the manifest's
# provenance unreadable, and `G-TOOL`'s commit-range conjunct unresolvable.
#
# STALE CODE ON THE LAPTOP IS A MIXED-REV CELL. Half of each cell would be played
# by a different revision of the champion, inside the same deck-paired statistic.
# That is precisely what `G-TOOL` voids on, and it is far better to abort here.
# =============================================================================
log "--- 3. BUNDLE-SYNC $LAPTOP_HOST TO $HEAD_BEFORE ---"
BUNDLE_DIR="$SHARE_LOCAL/bundles"
BUNDLE_NAME="jcz_tiearb_$(git -C "$REPO" rev-parse --short HEAD).bundle"
mkdir -p "$BUNDLE_DIR"
git -C "$REPO" bundle create "$BUNDLE_DIR/$BUNDLE_NAME" --all \
  || die "git bundle create failed" 5
log "bundle: $BUNDLE_DIR/$BUNDLE_NAME ($(stat -c %s "$BUNDLE_DIR/$BUNDLE_NAME") bytes)"

cat > "$LOGS/_sync_laptop.sh" <<EOF
cd $REPO_REMOTE || exit 1
set -u
git -C $REPO_REMOTE fetch "$SHARE_REMOTE/bundles/$BUNDLE_NAME" '+refs/heads/*:refs/remotes/bundle/*' || exit 6
git -C $REPO_REMOTE reset --hard $HEAD_BEFORE || exit 7
echo "SYNCED \$(git -C $REPO_REMOTE rev-parse HEAD)"
EOF
SYNC_OUT="$(timeout 900 ssh "$LAPTOP_HOST" 'bash -s' < "$LOGS/_sync_laptop.sh" 2>&1)" \
  || die "laptop bundle sync FAILED:
$SYNC_OUT" 6
echo "$SYNC_OUT"
LAPTOP_HEAD="$(echo "$SYNC_OUT" | sed -n 's/^SYNCED //p' | tail -1)"
if [ "$LAPTOP_HEAD" != "$HEAD_BEFORE" ]; then
  log "!!! LAPTOP HEAD MISMATCH after the bundle sync"
  log "!!!   local  $HEAD_BEFORE"
  log "!!!   laptop ${LAPTOP_HEAD:-<none reported>}"
  die "refusing to launch a MIXED-REV cell (G-TOOL)" 7
fi
log "laptop HEAD == local HEAD == $HEAD_BEFORE"

# --- 3b. the enabling-change probe on the laptop, now HARD -------------------
log "--- 3b. --champ-tiearb-* probe on $LAPTOP_HOST (HARD, post-sync) ---"
PROBE_POST="$(timeout 180 ssh "$LAPTOP_HOST" 'bash -s' < "$LOGS/_probe_laptop.sh" 2>&1)" \
  || die "laptop flag probe failed to run:
$PROBE_POST" 4
echo "$PROBE_POST"
case "$PROBE_POST" in
  *MISSING_FLAG:*|*"PROBE_RC=1"*)
    log "!!! $LAPTOP_HOST's match.py does NOT accept every --champ-tiearb-* flag"
    log "!!! even after the sync. Half of CELL B would be a STRUCTURAL ZERO."
    exit 4 ;;
esac
case "$PROBE_POST" in
  *"PROBE_RC=0"*) log "all six --champ-tiearb-* flags present on $LAPTOP_HOST" ;;
  *) die "laptop flag probe returned no PROBE_RC — cannot confirm the plumbing" 4 ;;
esac

# =============================================================================
# 4. CLAIM THE BAND (idempotent; LOCAL ONLY; skipped for the smoke)
#    The band is claimed ONCE, here, and PASSED to both boxes. The laptop never
#    touches the registry — a second claim would burn a band and split one cell's
#    decks across two of them, the exact cross-band pooling the house forbids.
# =============================================================================
if [ "$MODE" = "real" ]; then
  log "--- 4. CLAIM THE BAND (local only) ---"
  BAND="$("$HERE/claim_band.sh" | tail -1)"
  case "$BAND" in ''|*[!0-9]*) die "claim_band.sh did not return a numeric band (got '$BAND')" 5 ;; esac
  [ "$BAND" = "$BAND_FLOOR" ] || die "claim_band.sh returned $BAND but BAND_FLOOR is $BAND_FLOOR" 5
  log "band = $BAND (tag $BAND_TAG, sentinel $BAND_SENTINEL)"

  # =========================================================================
  # ⛔⛔ THE TOTAL COMMIT FREEZE STARTS *NOW*, AT THE CLAIM. FREEZE.md is the
  # rule, verbatim; this is where the witness is stamped.
  #
  # `scripts/jcz_match/match.py` stamps `our_git_rev` PER RECORD at record-write
  # time, so ANY commit — docs, measurement/, android/, a README typo — moves
  # HEAD and splits a cell's records across revisions. `G-TOOL` conjunct 2
  # requires `our_git_rev` equal across CELL A and CELL B AND consistent within
  # each cell. The 2026-08-17 run was VOIDED by exactly this: a freeze scoped to
  # wheel-relevant paths only let two docs-only commits land (DISCLOSURE §3).
  # The remedy needed no amendment to the gate — only a freeze that is TOTAL.
  #
  # The sha is published to the share so the LAPTOP has a witness too: its own
  # HEAD is set to this same sha by the step-3 bundle sync, so one sha binds both
  # boxes. `run_cell.sh` ABORTS on a mismatch; `watchdog.sh` only LOGS one.
  # =========================================================================
  {
    echo "$HEAD_BEFORE"
    echo "# TOTAL COMMIT FREEZE — see measurement/$RUN_ID/FREEZE.md"
    echo "# stamped at band-claim time: $(ts)"
    echo "# band $BAND   band_tag $BAND_TAG"
    echo "# NO COMMIT MAY LAND IN THIS REPOSITORY — none, of any kind, including"
    echo "# docs, measurement/, android/, and README typos — until ALL FOUR of"
    echo "# these markers exist:"
    echo "#   $SHARE_RUN/DONE_${CELL_A}_${HOST}_${BAND_TAG}"
    echo "#   $SHARE_RUN/DONE_${CELL_B}_${HOST}_${BAND_TAG}"
    echo "#   $SHARE_RUN/DONE_${CELL_A}_${LAPTOP_HOST}_${BAND_TAG}"
    echo "#   $SHARE_RUN/DONE_${CELL_B}_${LAPTOP_HOST}_${BAND_TAG}"
  } > "$FREEZE_HEAD_FILE"
  cp -f "$FREEZE_HEAD_FILE" "$SHARE_RUN/FREEZE_HEAD" \
    || die "could not publish FREEZE_HEAD to $SHARE_RUN — the laptop would start with no freeze witness and run_cell.sh would refuse it" 16
  log "⛔ TOTAL COMMIT FREEZE ARMED at HEAD $HEAD_BEFORE -> $FREEZE_HEAD_FILE (+ share)"
else
  log "--- 4. CLAIM SKIPPED (smoke uses a throwaway seed base, NOT a claimed band) ---"
  log "    (no band claimed ⇒ no commit freeze armed; run_cell.sh's freeze check is ADVISORY in smoke mode)"
  BAND="$SMOKE_SEED_BASE"
fi

# =============================================================================
# ⭐⭐ THE DECK SPLIT — COMPUTED **ONCE**, HERE, AND USED FOR **BOTH** CELLS.
#
# THIS IS THE LOAD-BEARING LINE OF THE WHOLE TWO-BOX REWORK (DESIGN §0.1.2,
# READ_RULE `G-SPLIT`). `D = M_B − M_A` is DECK-PAIRED: deck d contributes
# margin_B(d) − margin_A(d). If deck d ran on the laptop in CELL A and on the
# local box in CELL B, then EVERY per-box difference — the JVM packaging
# (17.0.19+10-1-24.04.2 locally vs +10-1-26.04.2 on the laptop), the different W
# and hence different contention, the different RAM headroom — lands INSIDE that
# paired difference and is ARITHMETICALLY INDISTINGUISHABLE from the arbiter's
# effect. With the split identical across cells, every per-box effect is common
# to both terms and CANCELS EXACTLY.
#
# So the four numbers below are computed ONCE and the SAME pair is handed to BOTH
# `run_cell.sh` invocations on a given box. There is deliberately no per-cell
# recomputation, no shuffling, no "balance the tail" adjustment between cells,
# and no re-read of WORKERS.conf between the two calls. `G-SPLIT` verifies it
# from the records afterwards; this is where it is GUARANTEED beforehand.
#
# The ratio itself (DECKS_LOCAL / DECKS_LAPTOP in WORKERS.conf) comes from the
# SMOKE's measured per-box s/game, not from W (DESIGN §0.1.3): the boxes are not
# equal-throughput, so splitting by W alone leaves one box idle at the tail.
# =============================================================================
if [ "$MODE" = "real" ]; then
  N_LOCAL="$DECKS_LOCAL"
  N_LAPTOP="$DECKS_LAPTOP"
  if [ $(( N_LOCAL + N_LAPTOP )) -ne "$DECKS" ]; then
    die "DECKS_LOCAL($N_LOCAL) + DECKS_LAPTOP($N_LAPTOP) = $(( N_LOCAL + N_LAPTOP )) != DECKS($DECKS) \
— the split would leave a GAP or an OVERLAP and G-COVER would VOID the run. Fix WORKERS.conf." 8
  fi
else
  N_LOCAL="$SMOKE_DECKS"
  N_LAPTOP="$SMOKE_DECKS"
fi
BASE_LOCAL="$BAND"
BASE_LAPTOP=$(( BAND + N_LOCAL ))

log "--- THE SPLIT (identical for CELL A and CELL B, by construction) ---"
log "  $HOST        : --seed-base $BASE_LOCAL  --decks $N_LOCAL   (decks $BASE_LOCAL..$(( BASE_LOCAL + N_LOCAL - 1 )))"
log "  $LAPTOP_HOST : --seed-base $BASE_LAPTOP --decks $N_LAPTOP  (decks $BASE_LAPTOP..$(( BASE_LAPTOP + N_LAPTOP - 1 )))"
log "  union covers $(( N_LOCAL + N_LAPTOP )) decks x 2 seatings per cell, exactly once (G-COVER)"

# =============================================================================
# 5. PRE-FLIGHT ON BOTH BOXES — G-J13 + G-JCZ + G-TOOL, all PER-HOST.
#    HARD BLOCKER on either box. See the ordering banner above.
# =============================================================================
log "--- 5. PRE-FLIGHT (per-host; AFTER the sync, BEFORE the launch) ---"
if [ "$MODE" = "real" ]; then PF_LABEL=FIRST; else PF_LABEL=SMOKE; fi

log "pre-flight on $HOST"
"$HERE/preflight.sh" "$PF_LABEL" || die "pre-flight FAILED on $HOST — refusing to launch" 13

cat > "$LOGS/_preflight_laptop.sh" <<EOF
cd $REPO_REMOTE || exit 1
bash $RUN_DIR/preflight.sh $PF_LABEL
EOF
log "pre-flight on $LAPTOP_HOST"
if ! timeout 1800 ssh "$LAPTOP_HOST" 'bash -s' < "$LOGS/_preflight_laptop.sh" 2>&1 \
       | tee "$LOGS/preflight_${LAPTOP_HOST}_${PF_LABEL}_driver.log"; then
  log "!!! PRE-FLIGHT FAILED ON $LAPTOP_HOST — see $LOGS/preflight_${LAPTOP_HOST}_${PF_LABEL}_driver.log"
  log "!!! READ_RULE G-J13 voids on 'a host that played with no pre-flight', so a"
  log "!!! laptop that cannot pass its own control MUST NOT play. The usual cause"
  log "!!! is a stale carc_rs wheel: rebuild it on the laptop AFTER the sync —"
  log "!!!   ssh $LAPTOP_HOST 'bash -s' <<< 'cd $REPO_REMOTE"
  log "!!!     . \$HOME/.cargo/env; RUSTUP_TOOLCHAIN=$RUST_TOOLCHAIN \\"
  log "!!!     $REPO_REMOTE/.venv/bin/maturin develop --release -m rust/carc/carc-py/Cargo.toml'"
  die "refusing to launch a two-box cell with one unverified box" 13
fi

# The laptop writes its verdicts to the share itself (preflight.sh step 3), but
# assert it here so a silent CIFS failure cannot leave the adjudicator blind.
for f in "PREFLIGHT_${LAPTOP_HOST}_${PF_LABEL}.json" "PREFLIGHT_${LAPTOP_HOST}_ENV.json"; do
  [ -f "$SHARE_RUN/verdicts/$f" ] \
    || die "$LAPTOP_HOST's $f is not on the share at $SHARE_RUN/verdicts/ — G-J13 cannot be read for that host" 13
done
# and pull the laptop's verdicts into the local run dir, which is what gets
# committed and what `adjudicate.py --verdicts` reads by default.
cp -f "$SHARE_RUN/verdicts/PREFLIGHT_${LAPTOP_HOST}"_*.json "$RUN_DIR/verdicts/" 2>/dev/null || true
log "pre-flight PASSED on BOTH hosts; verdicts in $RUN_DIR/verdicts and $SHARE_RUN/verdicts"

# =============================================================================
# 6. THE DETACHED CHAINS — one per box, CONCURRENT with each other; within a box
#    CELL A then CELL B, SEQUENTIALLY.
# =============================================================================
HEAD_AFTER="$(git -C "$REPO" rev-parse HEAD)"
if [ "$HEAD_AFTER" != "$HEAD_BEFORE" ]; then
  die "HEAD MOVED between the census and the launch ($HEAD_BEFORE -> $HEAD_AFTER). \
G-TOOL's <preflight>..<manifest> range would be non-degenerate. Re-run preflight.sh on BOTH boxes, then relaunch." 15
fi
log "HEAD stable at $HEAD_AFTER across the pre-flight — G-TOOL range is degenerate"

# ---- the chain body. IDENTICAL SHAPE ON BOTH BOXES; only the sub-range differs.
# ⚠️ $SB and $ND are used TWICE each — once for CELL A, once for CELL B — and
# that is the guarantee `G-SPLIT` is checking (DESIGN §0.1.2). Do not "improve"
# this by recomputing the range per cell.
gen_chain() {                       # gen_chain <outfile> <seed_base> <n_decks> <tag>
  local out="$1" sb="$2" nd="$3" tag="$4"
  {
    echo '#!/usr/bin/env bash'
    echo "# GENERATED BY launch.sh — the sequential two-cell chain for $tag."
    echo '# Do not edit by hand. Regenerate by re-running launch.sh.'
    echo 'set -uo pipefail'
    echo "echo \"[chain \$(date -u +%Y-%m-%dT%H:%M:%SZ)] START host=\$(hostname) mode=$MODE band=$BAND seed_base=$sb decks=$nd head=$HEAD_AFTER\""
    if [ "$MODE" = "smoke" ]; then
      echo "export SMOKE=1"
    fi
    # ⚠️ CHAINED WITH `;`, NOT `&&`: a VOID or short first cell must not silently
    # cancel the second. Both cells are attempted, both markers are written, and
    # the reading session decides.
    # ⭐ THE SAME $sb / $nd ON BOTH LINES — the identical-split guarantee.
    echo "bash \"$RUN_DIR/run_cell.sh\" \"$CELL_A\" $sb $nd; rcA=\$?"
    echo "bash \"$RUN_DIR/run_cell.sh\" \"$CELL_B\" $sb $nd; rcB=\$?"
    echo "echo \"[chain \$(date -u +%Y-%m-%dT%H:%M:%SZ)] END host=\$(hostname) rc_A=\$rcA rc_B=\$rcB\""
    echo 'exit $(( rcA != 0 || rcB != 0 ))'
  } > "$out"
  chmod +x "$out"
}

# ⚠️ band-tagged, like every other artifact: the VOIDED run's `_chain_real_*.sh`
# and `chain_real_*.log` are on this disk and on the share as the audit trail.
CHAIN_LOCAL="$LOGS/_chain_${MODE}_${BAND_TAG}_local.sh"
CHAIN_LAPTOP_SRC="$LOGS/_chain_${MODE}_${BAND_TAG}_laptop.sh"
CHAINLOG_LOCAL="$LOGS/chain_${MODE}_${BAND_TAG}_${HOST}.log"
gen_chain "$CHAIN_LOCAL"      "$BASE_LOCAL"  "$N_LOCAL"  "$HOST"
gen_chain "$CHAIN_LAPTOP_SRC" "$BASE_LAPTOP" "$N_LAPTOP" "$LAPTOP_HOST"

log "--- 6. LAUNCH (detached on BOTH boxes) ---"
log "chain scripts: $CHAIN_LOCAL  |  $CHAIN_LAPTOP_SRC"

# ---- 6a. the laptop FIRST, and its ssh call BACKGROUNDED --------------------
# ⚠️ A synchronous `ssh host "job &"` can HANG and starve every box launched
# after it, and a DOWN box masks the problem. So the remote launch call itself is
# backgrounded and its result is collected from a file afterwards.
# The chain script is staged through the SHARE rather than a nested heredoc: the
# repo path is identical on both boxes, but the chain is generated per-run and
# the share is the only channel that needs no second ssh round-trip.
mkdir -p "$SHARE_RUN"
cp -f "$CHAIN_LAPTOP_SRC" "$SHARE_RUN/_chain_${MODE}_${BAND_TAG}_laptop.sh"

cat > "$LOGS/_launch_laptop.sh" <<EOF
cd $REPO_REMOTE || exit 1
mkdir -p $RUN_DIR/logs
# ⛔ The freeze witness FIRST. run_cell.sh on this box ABORTS (rc 26) without it,
# so a chain launched before the copy lands would die at cell A with a confusing
# "FREEZE_HEAD IS ABSENT". It is copied, not fetched lazily, so the failure (if
# the share is unreadable) happens HERE, visibly, before anything is detached.
cp -f $SHARE_REMOTE/$RUN_ID/FREEZE_HEAD $RUN_DIR/FREEZE_HEAD || echo "WARN_NO_FREEZE_HEAD=1"
cp -f $SHARE_REMOTE/$RUN_ID/_chain_${MODE}_${BAND_TAG}_laptop.sh $RUN_DIR/logs/_chain_${MODE}_${BAND_TAG}_laptop.sh || exit 9
chmod +x $RUN_DIR/logs/_chain_${MODE}_${BAND_TAG}_laptop.sh
setsid nohup nice -n $NICE bash $RUN_DIR/logs/_chain_${MODE}_${BAND_TAG}_laptop.sh \
  > $RUN_DIR/logs/chain_${MODE}_${BAND_TAG}_\$(hostname).log 2>&1 < /dev/null &
CH=\$!
disown
echo "LAPTOP_CHAIN_PID=\$CH"
setsid nohup bash $RUN_DIR/watchdog.sh \$CH $MODE $N_LAPTOP \
  > $RUN_DIR/logs/watchdog_stdout_${BAND_TAG}_\$(hostname).log 2>&1 < /dev/null &
WD=\$!
disown
echo "LAPTOP_WATCHDOG_PID=\$WD"
EOF

LAPTOP_LAUNCH_OUT="$LOGS/launch_${LAPTOP_HOST}_${MODE}.out"
: > "$LAPTOP_LAUNCH_OUT"
( timeout 300 ssh "$LAPTOP_HOST" 'bash -s' < "$LOGS/_launch_laptop.sh" \
    > "$LAPTOP_LAUNCH_OUT" 2>&1
  echo "SSH_RC=$?" >> "$LAPTOP_LAUNCH_OUT" ) &
LAPTOP_SSH_PID=$!
log "laptop launch call backgrounded (pid $LAPTOP_SSH_PID) -> $LAPTOP_LAUNCH_OUT"

# ---- 6b. the local chain ----------------------------------------------------
# ⚠️ setsid + nohup + disown, not the harness's own backgrounding. Joshua's
# Mac -> Windows -> WSL setup means a Mac-sleep SIGHUP and a WSL VM teardown both
# kill tty-attached jobs; the python child must be explicitly detached.
setsid nohup nice -n "$NICE" bash "$CHAIN_LOCAL" > "$CHAINLOG_LOCAL" 2>&1 < /dev/null &
CHAIN_PID=$!
disown
log "local chain pid = $CHAIN_PID  (log $CHAINLOG_LOCAL)"

# =============================================================================
# 7. THE WATCHDOGS — on-disk heartbeat, detached, restart nothing. One per box.
#    (The laptop's was armed inside _launch_laptop.sh, in the same ssh call, so a
#    second ssh round-trip cannot leave it unwatched.)
# =============================================================================
log "--- 7. WATCHDOG (local; the laptop's was armed with its chain) ---"
setsid nohup bash "$HERE/watchdog.sh" "$CHAIN_PID" "$MODE" "$N_LOCAL" \
  > "$LOGS/watchdog_stdout_${BAND_TAG}_${HOST}.log" 2>&1 < /dev/null &
WD_PID=$!
disown
log "local watchdog pid = $WD_PID  (heartbeat $LOGS/watchdog_${HOST}_${BAND_TAG}.log, every 60 s)"

# ---- collect the laptop launch result --------------------------------------
wait "$LAPTOP_SSH_PID" 2>/dev/null || true
cat "$LAPTOP_LAUNCH_OUT" | sed 's/^/    [laptop] /'
LAPTOP_SSH_RC="$(sed -n 's/^SSH_RC=//p' "$LAPTOP_LAUNCH_OUT" | tail -1)"
LAPTOP_CHAIN_PID="$(sed -n 's/^LAPTOP_CHAIN_PID=//p' "$LAPTOP_LAUNCH_OUT" | tail -1)"
LAPTOP_WD_PID="$(sed -n 's/^LAPTOP_WATCHDOG_PID=//p' "$LAPTOP_LAUNCH_OUT" | tail -1)"
# ⚠️ rc=124 means `timeout` fired AFTER the launch had already happened. It is
# LAUNCHED, and it is NEVER retried: a retry stacks a second pool on the box.
if grep -q '^WARN_NO_FREEZE_HEAD=1' "$LAPTOP_LAUNCH_OUT" 2>/dev/null; then
  log "!!! the laptop could NOT copy FREEZE_HEAD from the share."
  log "!!! run_cell.sh on that box will ABORT rc=26 at cell A ('FREEZE_HEAD IS ABSENT')."
  log "!!! Fix the share copy and relaunch the LAPTOP leg only — the local leg is"
  log "!!! already running and this script kills nothing:"
  log "!!!   $SHARE_RUN/FREEZE_HEAD  ->  $LAPTOP_HOST:$FREEZE_HEAD_FILE"
fi
if [ "${LAPTOP_SSH_RC:-}" = "124" ]; then
  log "laptop launch returned 124 from timeout — treat as LAUNCHED, do NOT retry"
elif [ -z "$LAPTOP_CHAIN_PID" ]; then
  log "!!! the laptop launch reported NO chain pid (ssh rc=${LAPTOP_SSH_RC:-?})."
  log "!!! The LOCAL leg is already running and is NOT killed by this script."
  log "!!! Verify by hand before assuming the laptop is idle — do not relaunch blind:"
  log "!!!   ssh $LAPTOP_HOST 'pgrep -af jcz_match/match.py || echo none'"
fi

# =============================================================================
# 8. WHAT TO WATCH. Then EXIT — this script does not wait.
# =============================================================================
cat <<EOF

=============================================================================
LAUNCHED ON TWO BOXES (mode=$MODE). Nothing adjudicated, nothing promoted,
PRODUCTION.yaml untouched.

  local  ($HOST)        chain pid $CHAIN_PID          watchdog $WD_PID
  laptop ($LAPTOP_HOST) chain pid ${LAPTOP_CHAIN_PID:-<unknown>}  watchdog ${LAPTOP_WD_PID:-<unknown>}
  band                  $BAND          band_tag $BAND_TAG (stamped into EVERY artifact)
  split (BOTH cells)    $HOST: base $BASE_LOCAL x $N_LOCAL decks
                        $LAPTOP_HOST: base $BASE_LAPTOP x $N_LAPTOP decks
  workers               $HOST=$([ "$MODE" = "real" ] && echo "$W_LOCAL" || echo "$W_SMOKE_LOCAL") \
$LAPTOP_HOST=$([ "$MODE" = "real" ] && echo "$W_LAPTOP" || echo "$W_SMOKE_LAPTOP")
  _JAVA_OPTIONS         $JVM_OPTS   (identical on both boxes and both cells)
  git HEAD              $HEAD_AFTER  (both boxes)

LOGS
  $CHAINLOG_LOCAL
  $LOGS/chain_${MODE}_${BAND_TAG}_${LAPTOP_HOST}.log     <- on the LAPTOP's disk
  $LOGS/watchdog_${HOST}_${BAND_TAG}.log                 <- 60 s heartbeat, local
  $LOGS/watchdog_${LAPTOP_HOST}_${BAND_TAG}.log          <- 60 s heartbeat, on the LAPTOP's disk
  ssh $LAPTOP_HOST 'tail -f $RUN_DIR/logs/watchdog_${LAPTOP_HOST}_${BAND_TAG}.log'
EOF
if [ "$MODE" = "real" ]; then
cat <<EOF
  $LOGS/${CELL_A}.${HOST}.${BAND_TAG}.log
  $LOGS/${CELL_B}.${HOST}.${BAND_TAG}.log

⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔
⛔                       TOTAL COMMIT FREEZE IS NOW ON                       ⛔
⛔                                                                           ⛔
⛔  From this moment until the FOURTH DONE marker below exists,              ⛔
⛔  NO COMMIT MAY LAND IN THIS REPOSITORY — none, of any kind,               ⛔
⛔  including docs, measurement/, android/, and README typos.                ⛔
⛔                                                                           ⛔
⛔  match.py stamps our_git_rev PER RECORD at record-write time, so ANY      ⛔
⛔  commit moves HEAD and splits a cell's records across revisions.          ⛔
⛔  G-TOOL conjunct 2 voids a mixed-rev cell. The 2026-08-17 run was VOIDED  ⛔
⛔  by exactly this — a freeze scoped to wheel-relevant paths only let two   ⛔
⛔  DOCS-ONLY commits land. An empty wheel diff did NOT rescue it.           ⛔
⛔                                                                           ⛔
⛔  Rule: measurement/$RUN_ID/FREEZE.md      ⛔
⛔  Why : measurement/$RUN_ID/DISCLOSURE.md §3  ⛔
⛔  Head: $HEAD_AFTER  ⛔
⛔  File: $FREEZE_HEAD_FILE  ⛔
⛔                                                                           ⛔
⛔  ETA ~2.5 h. Park your commits; land them all at once afterwards.         ⛔
⛔  git add / git stash / editing files are FINE — they move no HEAD.        ⛔
⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔⛔

  Enforcement, three layers:
    launch.sh    RECORDS the sha (done, above) and printed this banner
    run_cell.sh  ABORTS rc=26 before each cell if HEAD != FREEZE_HEAD
    watchdog.sh  LOGS '!!! FREEZE VIOLATION' every 60 s; kills NOTHING

WATCH FOR THESE MARKERS (four of them — the run is done, AND THE FREEZE LIFTS,
when ALL FOUR exist)
  $SHARE_RUN/DONE_${CELL_A}_${HOST}_${BAND_TAG}
  $SHARE_RUN/DONE_${CELL_B}_${HOST}_${BAND_TAG}
  $SHARE_RUN/DONE_${CELL_A}_${LAPTOP_HOST}_${BAND_TAG}
  $SHARE_RUN/DONE_${CELL_B}_${LAPTOP_HOST}_${BAND_TAG}
  (the same four also land in $RUN_DIR on each box's own disk)
  $SHARE_RUN/FAILED_<cell>_<host>_${BAND_TAG}   <- on failure, carries the exit code
  ⚠️ a FAILED marker does NOT lift the freeze — a resume runs on the same HEAD.

OUTPUT SHARDS (per box — NOT readable on their own)
  $RUN_DIR/${CELL_A}.${HOST}.${BAND_TAG}.jsonl   + $SHARE_RUN/${CELL_A}.${HOST}.${BAND_TAG}.jsonl
  $RUN_DIR/${CELL_B}.${HOST}.${BAND_TAG}.jsonl   + $SHARE_RUN/${CELL_B}.${HOST}.${BAND_TAG}.jsonl
  $SHARE_RUN/${CELL_A}.${LAPTOP_HOST}.${BAND_TAG}.jsonl
  $SHARE_RUN/${CELL_B}.${LAPTOP_HOST}.${BAND_TAG}.jsonl
  $SHARE_RUN/<cell>.<host>.${BAND_TAG}.hostmap.json  <- the deck->host stamp (G-SPLIT)
  ⚠️ The VOIDED 133000000000 run's UNTAGGED files sit beside these as the audit
     trail. Nothing here overwrites them; nothing there is read by this run.

⭐ NEXT STEP WHEN ALL FOUR MARKERS EXIST — DO NOT ADJUDICATE A SHARD:
  $RUN_DIR/merge_cells.sh
     -> ${CELL_A}.${BAND_TAG}.jsonl / ${CELL_B}.${BAND_TAG}.jsonl  (the merged cells)
     -> COVER_<cell>.${BAND_TAG}.json     (G-COVER: exact coverage)
     -> <cell>.${BAND_TAG}.hostmap.json   (the merged deck->host map)
     -> SPLIT_CHECK.${BAND_TAG}.json      (G-SPLIT: A's map == B's map)
  Only then READ_RULE.md §3, then adjudicate.py.

GATE WITNESSES (already written, both hosts)
  $RUN_DIR/verdicts/PREFLIGHT_${HOST}_FIRST.json          G-J13
  $RUN_DIR/verdicts/PREFLIGHT_${HOST}_ENV.json            G-TOOL / G-JCZ
  $RUN_DIR/verdicts/PREFLIGHT_${LAPTOP_HOST}_FIRST.json   G-J13   (synced from the share)
  $RUN_DIR/verdicts/PREFLIGHT_${LAPTOP_HOST}_ENV.json     G-TOOL / G-JCZ
EOF
else
cat <<EOF
  $LOGS/smoke_${CELL_A}.${HOST}.${BAND_TAG}.log
  $LOGS/smoke_${CELL_B}.${HOST}.${BAND_TAG}.log

SMOKE ARTIFACTS (no band claimed, no commit freeze, NO DONE marker for the real
cells; band-tagged anyway so the VOIDED run's smoke files are never overwritten)
  $RUN_DIR/smoke_<cell>.${HOST}.${BAND_TAG}.jsonl
  $SHARE_RUN/smoke_<cell>.${LAPTOP_HOST}.${BAND_TAG}.jsonl
  $RUN_DIR/SMOKE_${HOST}.${BAND_TAG}.json          <- peaks + s/game for THIS box
  $SHARE_RUN/SMOKE_${LAPTOP_HOST}.${BAND_TAG}.json <- peaks + s/game for the LAPTOP
  $RUN_DIR/SMOKE_<host>.${BAND_TAG}.samples.csv    <- the 5 s RSS/load sample stream
  $RUN_DIR/SMOKE_<host>.${BAND_TAG}.timing.csv     <- per-cell elapsed / games

⭐ READ BOTH SMOKE_<host>.json BEFORE COMMITTING THE LONG RUN:
  1. s_per_game_wall on each box sets DECKS_LOCAL / DECKS_LAPTOP in WORKERS.conf
     (DESIGN §0.1.3 — the boxes are NOT equal-throughput, so splitting by W alone
     leaves one box idle at the tail). Keep DECKS_LOCAL + DECKS_LAPTOP == $DECKS.
  2. peak_rss_total_gb / peak_n_jvm / min_mem_available_gb on the LAPTOP validate
     W=$W_LAPTOP against its 11 GB (DESIGN §0.1.4). If it does not fit, that is
     REPORTED TO THE OWNER, NOT silently reduced — W is an owner-set value.
EOF
fi
echo "============================================================================="
exit 0
