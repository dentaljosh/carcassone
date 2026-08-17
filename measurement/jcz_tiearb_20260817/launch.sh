#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — THE ONE COMMAND THAT RUNS THE WHOLE THING.
#
#   ./launch.sh              the real run: 2 cells x 400 decks x 2 seats = 1600 games
#   ./launch.sh --smoke      the SAME path at 4 decks/cell on a throwaway seed base
#
# Prereg of record: DESIGN.md + READ_RULE.md in this directory, both committed
# BEFORE the band claim and BEFORE game 1.
#
# ORDER, ENFORCED, each step failing loudly and stopping:
#   1. CENSUS. A timing-sensitive, DRAM-bound, 24-worker cell is an EXCLUSIVE
#      tenant. If a solver/eval/match leg is live we ABORT and tell the operator
#      to wait — we NEVER kill anything we did not start.
#   2. TREE. Record HEAD, and probe `match.py --help` for `--champ-tiearb-enabled`:
#      without the enabling change merged, CELL B would silently run as a second
#      copy of CELL A and D would be a structural zero.
#   3. CLAIM THE BAND (idempotent via the sentinel). Skipped in --smoke.
#   4. PRE-FLIGHT. G-J13 (two-sided arbiter control) + G-TOOL (env witness).
#   5. LAUNCH the two cells SEQUENTIALLY in ONE detached chain.
#   6. ARM THE WATCHDOG, detached.
#   7. PRINT pids / logs / markers, and EXIT. It does not wait.
#
# ⚠️⚠️ WHY THE PRE-FLIGHT SITS AT STEP 4 AND NOT ANYWHERE ELSE (READ_RULE §3.1).
#   `G-TOOL` requires
#       git diff --name-only <preflight_commit>..<manifest_commit> -- rust/ src/ engine/ scripts/
#   to be EMPTY or the range DEGENERATE. So the pre-flight must be generated
#   AFTER any wheel rebuild and BEFORE the detached launch. Stage 2's
#   `launch_both.sh` had NO pre-flight step: it rebuilt the wheel and launched, so
#   HEAD moved between the pre-flight and the manifest on EVERY healthy run and
#   `G-TOOL` was unsatisfiable by construction — that defect cost Stage 2 an
#   adjudication. It is FIXED here, not inherited: this script generates the
#   pre-flight itself, at step 4, and ASSERTS that HEAD has not moved between the
#   pre-flight and the launch at step 5.
#
# ⚠️ IT REBUILDS NO WHEEL. If a rebuild is needed, do it BEFORE running this
#   script — that ordering is exactly what keeps the commit range degenerate:
#       RUSTUP_TOOLCHAIN=<from WORKERS.conf> .venv/bin/maturin develop --release \
#           -m rust/carc/carc-py/Cargo.toml
#
# SINGLE BOX. DESIGN §6.3: the laptop has no JVM and no Engine.jar, so it is
# DECLINED, not forgotten. There is no ssh anywhere in this directory and no
# remote share path is ever referenced.
#
# ADJUDICATES NOTHING. No results.csv row, no analyzer, no PRODUCTION.yaml.
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"

MODE=real
case "${1:-}" in
  "")        ;;
  --smoke)   MODE=smoke ;;
  -h|--help) sed -n '2,50p' "$0"; exit 0 ;;
  *) echo "usage: launch.sh [--smoke]" >&2; exit 2 ;;
esac

REPO="$REPO_LOCAL"
PY="$REPO/.venv/bin/python"
LOGS="$RUN_DIR/logs"
mkdir -p "$LOGS" "$RUN_DIR/verdicts" "$SHARE_RUN_LOCAL"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[launch $(ts)] $*"; }
die() { log "FATAL: $*"; exit "${2:-1}"; }

log "=== jcz_tiearb_20260817 — out-of-lineage pricing of the tie arbiter (mode=$MODE) ==="
log "cells: $CELL_A (champion) then $CELL_B (champion + arbiter), SEQUENTIAL, one box"

# =============================================================================
# 1. CENSUS — do it BY DEFAULT, and ABORT rather than kill.
# =============================================================================
log "--- 1. CENSUS ---"
echo "--- python/java processes ---"
ps -eo pid,etime,pcpu,rss,args --sort=-etime 2>/dev/null \
  | grep -iE 'python|java' | grep -v ' grep ' | head -30 || true
echo "--- /proc/loadavg ---"; cat /proc/loadavg
echo "--- free -g ---";       free -g

# ⚠️ The pattern requires the `.py` SUFFIX, and shell wrappers are filtered out.
# A watcher shell (`until ! pgrep -f reconcile_exact_solver; do ...`) carries the
# bare name in its own argv and would otherwise read as a live compute leg and
# block the launch forever. The real legs are `.../reconcile_exact_solver.py`.
BUSY="$(pgrep -af 'reconcile_exact_solver\.py|eval_fair_puct\.py|match\.py' 2>/dev/null \
        | grep -v -e 'shell-snapshots' -e 'pgrep' -e 'until !' || true)"
if [ -n "$BUSY" ]; then
  log "!!! A COMPUTE LEG IS ALIVE ON THIS BOX:"
  echo "$BUSY" | sed 's/^/    /'
  log "!!! ABORTING. This cell is DRAM-bound at W=$W_LOCAL and is an EXCLUSIVE tenant:"
  log "!!! sharing the box would corrupt BOTH the throughput measurement and the"
  log "!!! neighbouring run (feedback_no_agent_compute_beside_eval)."
  log "!!! WAIT for the live leg to finish. Do NOT kill it — this script never does."
  exit 3
fi
log "census clean — no reconcile_exact_solver / eval_fair_puct / match.py leg is alive"

# =============================================================================
# 2. TREE + THE ENABLING-CHANGE PROBE
# =============================================================================
log "--- 2. TREE ---"
HEAD_BEFORE="$(git -C "$REPO" rev-parse HEAD)"
log "git HEAD = $HEAD_BEFORE"

[ -x "$PY" ] || die "no venv python at $PY"
MATCH_PY="$REPO/scripts/jcz_match/match.py"
[ -f "$MATCH_PY" ] || die "driver missing at $MATCH_PY"

# ⚠️ THE STRUCTURAL ZERO GUARD. If the `--champ-tiearb-*` plumbing is not merged,
# CELL B is a byte-identical second copy of CELL A and D is zero BY CONSTRUCTION —
# a perfect champion-vs-champion null wearing the shape of a real cell. Probe the
# real parser, not the source text.
log "probing $MATCH_PY --help for --champ-tiearb-enabled"
HELP="$("$PY" "$MATCH_PY" --help 2>&1 || true)"
for flag in --champ-tiearb-enabled --champ-tiearb-b --champ-tiearb-j \
            --champ-tiearb-mode --champ-tiearb-salt --champ-tiearb-eps; do
  case "$HELP" in
    *"$flag"*) ;;
    *) log "!!! $MATCH_PY does NOT accept $flag"
       log "!!! The enabling change (DESIGN §6.1) must be MERGED before launch:"
       log "!!! without it CELL B runs as a second copy of CELL A and D is a"
       log "!!! STRUCTURAL ZERO that no gate downstream could distinguish from a null."
       exit 4 ;;
  esac
done
log "all six --champ-tiearb-* flags present"

# =============================================================================
# 3. CLAIM THE BAND (idempotent; skipped for the smoke, which uses a throwaway)
# =============================================================================
if [ "$MODE" = "real" ]; then
  log "--- 3. CLAIM THE BAND ---"
  BAND="$("$HERE/claim_band.sh" | tail -1)"
  case "$BAND" in ''|*[!0-9]*) die "claim_band.sh did not return a numeric band (got '$BAND')" 5 ;; esac
  log "band = $BAND (sentinel $BAND_SENTINEL)"
else
  log "--- 3. CLAIM SKIPPED (smoke uses a throwaway seed base, NOT a claimed band) ---"
  BAND="(smoke: throwaway)"
fi

# =============================================================================
# 4. PRE-FLIGHT — G-J13 + G-TOOL. HARD BLOCKER. See the ordering banner above.
# =============================================================================
log "--- 4. PRE-FLIGHT (must be AFTER any wheel build, BEFORE the launch) ---"
if [ "$MODE" = "real" ]; then PF_LABEL=FIRST; else PF_LABEL=SMOKE; fi
"$HERE/preflight.sh" "$PF_LABEL" || die "pre-flight FAILED — refusing to launch" 13

# =============================================================================
# 5. THE DETACHED CHAIN — CELL A then CELL B, SEQUENTIALLY.
#    They share ONE box: running them concurrently would halve each one's workers
#    and destroy the throughput/RSS reading the smoke exists to take.
# =============================================================================
HEAD_AFTER="$(git -C "$REPO" rev-parse HEAD)"
if [ "$HEAD_AFTER" != "$HEAD_BEFORE" ]; then
  die "HEAD MOVED between the census and the launch ($HEAD_BEFORE -> $HEAD_AFTER). \
G-TOOL's <preflight>..<manifest> range would be non-degenerate. Re-run preflight.sh, then relaunch." 15
fi
log "HEAD stable at $HEAD_AFTER across the pre-flight — G-TOOL range is degenerate"

CHAIN="$LOGS/_chain_${MODE}.sh"
CHAINLOG="$LOGS/chain_${MODE}.log"
{
  echo '#!/usr/bin/env bash'
  echo '# GENERATED BY launch.sh — the sequential two-cell chain. Do not edit by hand.'
  echo 'set -uo pipefail'
  echo "echo \"[chain \$(date -u +%Y-%m-%dT%H:%M:%SZ)] START mode=$MODE band=$BAND head=$HEAD_AFTER\""
  if [ "$MODE" = "smoke" ]; then
    echo "export SMOKE=1"
    echo "export SMOKE_DECKS=${SMOKE_DECKS:-4}"
    echo "export SMOKE_SEED_BASE=${SMOKE_SEED_BASE:-900000200000}"
  fi
  # ⚠️ CHAINED WITH `;`, NOT `&&`: a VOID or short first cell must not silently
  # cancel the second. Both cells are attempted, both markers are written, and
  # the reading session decides.
  echo "bash \"$HERE/run_cell.sh\" \"$CELL_A\"; rcA=\$?"
  echo "bash \"$HERE/run_cell.sh\" \"$CELL_B\"; rcB=\$?"
  echo "echo \"[chain \$(date -u +%Y-%m-%dT%H:%M:%SZ)] END rc_A=\$rcA rc_B=\$rcB\""
  echo 'exit $(( rcA != 0 || rcB != 0 ))'
} > "$CHAIN"
chmod +x "$CHAIN"

log "--- 5. LAUNCH (detached: setsid nohup ... & disown) ---"
log "chain script: $CHAIN"
# ⚠️ setsid + nohup + disown, not the harness's own backgrounding. Joshua's
# Mac -> Windows -> WSL setup means a Mac-sleep SIGHUP and a WSL VM teardown both
# kill tty-attached jobs; the python child must be explicitly detached.
setsid nohup nice -n "$NICE" bash "$CHAIN" > "$CHAINLOG" 2>&1 < /dev/null &
CHAIN_PID=$!
disown
log "chain pid = $CHAIN_PID  (log $CHAINLOG)"

# =============================================================================
# 6. THE WATCHDOG — on-disk heartbeat, detached, restarts nothing.
# =============================================================================
log "--- 6. WATCHDOG ---"
setsid nohup bash "$HERE/watchdog.sh" "$CHAIN_PID" "$MODE" \
  > "$LOGS/watchdog_stdout.log" 2>&1 < /dev/null &
WD_PID=$!
disown
log "watchdog pid = $WD_PID  (heartbeat $LOGS/watchdog.log, every 60 s)"

# =============================================================================
# 7. WHAT TO WATCH. Then EXIT — this script does not wait.
# =============================================================================
cat <<EOF

=============================================================================
LAUNCHED (mode=$MODE). Nothing adjudicated, nothing promoted, PRODUCTION.yaml untouched.

  chain pid       $CHAIN_PID
  watchdog pid    $WD_PID
  band            $BAND
  workers         $([ "$MODE" = "real" ] && echo "$W_LOCAL" || echo "$W_SMOKE")
  git HEAD        $HEAD_AFTER

LOGS
  $CHAINLOG
EOF
if [ "$MODE" = "real" ]; then
cat <<EOF
  $LOGS/${CELL_A}.log
  $LOGS/${CELL_B}.log
  $LOGS/watchdog.log                      <- 60 s heartbeat; crash-vs-hang discriminator

WATCH FOR THESE MARKERS (the completion signal)
  $RUN_DIR/DONE_${CELL_A}
  $RUN_DIR/DONE_${CELL_B}
  $SHARE_RUN_LOCAL/DONE_${CELL_A}
  $SHARE_RUN_LOCAL/DONE_${CELL_B}
  $RUN_DIR/FAILED_${CELL_A}               <- on failure, carries the exit code
  $RUN_DIR/FAILED_${CELL_B}

OUTPUT ARCHIVES
  $RUN_DIR/${CELL_A}.jsonl
  $RUN_DIR/${CELL_B}.jsonl

GATE WITNESSES (already written)
  $RUN_DIR/verdicts/PREFLIGHT_$(hostname)_FIRST.json    G-J13
  $RUN_DIR/verdicts/PREFLIGHT_$(hostname)_ENV.json      G-TOOL
EOF
else
cat <<EOF
  $LOGS/smoke_${CELL_A}.log
  $LOGS/smoke_${CELL_B}.log
  $LOGS/watchdog.log

SMOKE ARTIFACTS (no band claimed, NO DONE marker for the real cells)
  $RUN_DIR/smoke_${CELL_A}.jsonl
  $RUN_DIR/smoke_${CELL_B}.jsonl
  $RUN_DIR/SMOKE_${CELL_A}.txt
  $RUN_DIR/SMOKE_${CELL_B}.txt

Read per-worker RSS and throughput at W=$W_SMOKE off the smoke before committing
the long run (DESIGN §6.2: bench, then extrapolate, then commit).
EOF
fi
echo "============================================================================="
exit 0
