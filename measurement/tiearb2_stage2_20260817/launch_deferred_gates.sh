#!/usr/bin/env bash
# =============================================================================
# ONE COMMAND. Fires the deferred reconcile suite, detached, and returns.
#
#   /home/doctor/projects/carcassone/measurement/tiearb2_stage2_20260817/launch_deferred_gates.sh
#
# It detaches properly (setsid + nohup + </dev/null + disown), so neither a
# Mac-sleep SIGHUP nor a closed WSL tty can take it down — the harness's own
# backgrounding is NOT enough, the python child has to be detached too.
#
# It writes:
#   logs/deferred_gates.log                    the suite's own log
#   verdicts/deferred_gates/STAMP_<gate>.json  per-gate progress, survives a kill
#   DONE_DEFERRED_GATES | FAILED_DEFERRED_GATES  the terminal stamp
#   RUN_LIVE.json                              freeze-latch sentinel while live
#
# Knobs (all optional, passed straight through):
#   FORCE_BACKEND=1  FORCE_EXACT=1  EXACT_WORKERS=N  EXACT_TAG=name  SMOKE=1
#   MEM_MAX=28G      cgroup cap for the whole suite (see below)
#   NO_SCOPE=1       launch without the systemd scope (fallback)
#
# ⚠️ MEMORY CAP — NOT DECORATION. The 2026-08-19 attempt died ~7.5 h in to a
# host reboot. The uncapped exact-solver gate is the box's worst memory profile
# in the repo: `marginalized` mode has no alpha-beta, so its Python transposition
# tables grow without a pruning bound, three of them at once, for hours. That is
# the same self-inflicted-memory-pressure signature the local box's dirty
# reboots were re-attributed to (see the local-box memory note). Capping the
# suite's cgroup turns "the host went down" into "one gate OOMed and stamped a
# failure", which is a result instead of a loss. Raise MEM_MAX only after
# measuring, never on a hunch.
# =============================================================================
set -eu

REPO=/home/doctor/projects/carcassone
HERE="$REPO/measurement/tiearb2_stage2_20260817"
LOG="$HERE/logs/deferred_gates.log"
SUITE="$HERE/deferred_full_gates.sh"
SENTINEL="$HERE/RUN_LIVE.json"
MEM_MAX=${MEM_MAX:-28G}
NO_SCOPE=${NO_SCOPE:-0}

mkdir -p "$HERE/logs" "$HERE/verdicts/deferred_gates"

# --- refuse to double-launch. Two copies of this suite would fight over the
# --- same rows file and the same box. `pgrep -f` exits 1 on no match, which is
# --- the expected case, so it must not be allowed to trip `set -e`.
if pgrep -f "deferred_full_gates\.sh" >/dev/null 2>&1; then
  echo "REFUSING: deferred_full_gates.sh is already running:" >&2
  pgrep -af "deferred_full_gates\.sh" >&2 || true
  exit 1
fi

if [ -f "$HERE/DONE_DEFERRED_GATES" ] && [ "${FORCE_EXACT:-0}" != "1" ] \
   && [ "${FORCE_BACKEND:-0}" != "1" ]; then
  echo "NOTE: DONE_DEFERRED_GATES already exists:" >&2
  sed 's/^/  /' "$HERE/DONE_DEFERRED_GATES" >&2
  echo "Re-launch anyway with FORCE_EXACT=1 (or FORCE_BACKEND=1)." >&2
  exit 1
fi

# --- freeze-latch sentinel: main-tree commits refuse while this exists, which
# --- is exactly right for a multi-hour gate reading the tree it certifies.
# --- The suite removes it on exit, including on a kill (trap in the wrapper).
cat > "$SENTINEL" <<EOF
{"run": "tiearb2_stage2_deferred_gates",
 "launched": "$(date +%FT%T)",
 "log": "$LOG",
 "note": "deferred reconcile gates (backend + exact_solver). Removed on exit."}
EOF

WRAP=$(mktemp "${TMPDIR:-/tmp}/deferred_gates_wrap.XXXXXX.sh")
cat > "$WRAP" <<EOF
#!/usr/bin/env bash
cleanup() { rm -f "$SENTINEL"; }
trap cleanup EXIT INT TERM
bash "$SUITE"
EOF
chmod +x "$WRAP"

echo "launching: $SUITE"
echo "  log      : $LOG"
echo "  stamps   : $HERE/verdicts/deferred_gates/"
echo "  mem cap  : $MEM_MAX  (NO_SCOPE=$NO_SCOPE)"

if [ "$NO_SCOPE" = "1" ] || ! command -v systemd-run >/dev/null 2>&1; then
  setsid nohup nice -n 19 bash "$WRAP" >> "$LOG" 2>&1 < /dev/null &
else
  # `--scope` keeps it in this session's cgroup tree; `--collect` reaps the unit
  # when it exits so a re-launch does not collide with a stale unit name.
  setsid nohup systemd-run --user --scope --collect \
      -p MemoryMax="$MEM_MAX" -p MemorySwapMax=0 \
      --unit="carc-deferred-gates-$(date +%s)" \
      nice -n 19 bash "$WRAP" >> "$LOG" 2>&1 < /dev/null &
fi
disown || true

sleep 3
echo
echo "--- verify ---"
pgrep -af "deferred_full_gates\.sh" || echo "  (no suite process yet — check $LOG)"
tail -5 "$LOG" 2>/dev/null || true
echo
echo "Suite is detached. It stamps per gate, so a kill costs the jobs in flight,"
echo "not the run; re-run this launcher to pick up where it stopped."
