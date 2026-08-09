#!/bin/bash
# LAPTOP-side driver for the chunked phase-seam gate.
# Lives OUTSIDE both git trees on purpose: tests/test_shell_harness_hygiene.py greps
# REPO/scripts, so dropping a new script into either tree would perturb the very
# comparison this gate is making. /home/doctor/gate_ops is neutral ground.
#
# Runs the gate (which resumes itself from its chunk artifacts), then publishes.
#   VERDICT present      -> rsync PHASE_SEAM_GATE (minus wheels) to the share, .DONE=<verdict>
#   VERDICT_BLOCKED      -> .DONE=GATE_DIED (pull_and_chain.sh aborts rather than chaining)
# Idempotent and safe to re-run: a second invocation while one is live exits at the lock.
set -u
REPO=/home/doctor/projects/carcassone
OUT=$REPO/measurement/curve_shape_scope_20260809/PHASE_SEAM_GATE
SHARE=/mnt/carc-shared/_sync/phase_seam_gate/RESULT   # allow-path (LAPTOP share path)
LOG=/home/doctor/gate_ops/chunked_gate.log
LOCK=/home/doctor/gate_ops/.gate.lock
ts() { date +%F_%T; }

# Operator knobs (GATE_DEFER, GATE_MAX_ATTEMPTS, ...) without editing this file,
# so they survive a supervisor-driven relaunch too.
if [ -f /home/doctor/gate_ops/gate.env ]; then
  . /home/doctor/gate_ops/gate.env
  export GATE_DEFER GATE_ONLY GATE_MAX_ATTEMPTS 2>/dev/null || true
fi

exec 9>"$LOCK"
if ! flock -n 9; then echo "$(ts) another gate driver holds the lock; exiting" >> "$LOG"; exit 0; fi

if [ -f "$OUT/VERDICT" ] && [ -f "$SHARE/.DONE" ]; then
  echo "$(ts) verdict already published; nothing to do" >> "$LOG"; exit 0
fi

echo "$(ts) ===== chunked gate driver start (pid $$) =====" >> "$LOG"
bash /home/doctor/gate_ops/phase_seam_gate_chunked.sh >> "$LOG" 2>&1
rc=$?
echo "$(ts) gate script exited rc=$rc" >> "$LOG"

mkdir -p "$SHARE"
if [ -f "$OUT/VERDICT" ]; then
  V=$(cat "$OUT/VERDICT")
  cp -a "$LOG" "$OUT/gate_run_laptop.log" 2>/dev/null
  rsync -a --exclude wheels "$OUT/" "$SHARE/" >> "$LOG" 2>&1
  sync
  echo "$V" > "$SHARE/.DONE"
  echo "$(ts) PUBLISHED VERDICT=$V to $SHARE" >> "$LOG"
  exit 0
fi

# No verdict. Do NOT publish GATE_DIED just because the process was interrupted --
# the supervisor will restart us and the chunk artifacts make that free.
#
# Only INCONCLUSIVE is final: a chunk that would not complete after MAX_ATTEMPTS.
# INCOMPLETE_n_OF_m is the OPPOSITE -- it means chunks are simply still missing
# (interrupted, or deliberately deferred), which is a RESUMABLE state. Publishing
# GATE_DIED for it would make pull_and_chain abort the whole chain over a run that
# just needed to be restarted. (Bug found 2026-08-09 while deferring a chunk under
# debug; it would have thrown away 45 good chunks.)
BLOCKED=$(cat "$OUT/VERDICT_BLOCKED" 2>/dev/null || echo "")
case "$BLOCKED" in
  INCOMPLETE_*)
    echo "$(ts) $BLOCKED -- resumable, NOT publishing GATE_DIED. Supervisor will resume." >> "$LOG"
    exit 2 ;;
esac
if [ -f "$OUT/VERDICT_BLOCKED" ]; then
  cp -a "$LOG" "$OUT/gate_run_laptop.log" 2>/dev/null
  rsync -a --exclude wheels "$OUT/" "$SHARE/" >> "$LOG" 2>&1
  sync
  echo "GATE_DIED" > "$SHARE/.DONE"
  echo "$(ts) PUBLISHED GATE_DIED (blocked: $(cat "$OUT/VERDICT_BLOCKED"))" >> "$LOG"
  exit 1
fi
echo "$(ts) no verdict and not blocked -- interrupted. Supervisor will resume." >> "$LOG"
exit 2
