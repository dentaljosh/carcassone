#!/usr/bin/env bash
# Resume the G7 reconcile exact-solver walled suite (tag run2) to 185/185.
#
# WHY THIS SCRIPT EXISTS (2026-08-26 diagnosis): the suite kept "pausing at
# 154/185 with 31 jobs that complete without rows". That was NOT a row-writer
# bug — the remaining 31 jobs (13 f3-champion K=3 corpus + 18 synth K1-3) are
# long, silent, sequential jobs at workers=1: the driver prints progress only
# every 10 jobs, a first job can legitimately run toward the 7200s RLIMIT_CPU
# cap, and every prior incarnation was killed (host sleep / manual pause)
# before the first row landed. Probe evidence: the per-job child ran healthy at
# 99.9% CPU. The fix is operational, not code: detach properly, expect hours of
# silence, and judge liveness by the CHILD's CPU, not by log output.
#
# Launch (detached — Mac-sleep SIGHUP and WSL teardown both kill tty jobs):
#   setsid nohup scripts/rustport/resume_run2_suite.sh \
#     </dev/null >/dev/null 2>&1 & disown
#
# Do NOT run while measurement/track_d2r3_prep is live (exclusive-tenancy
# window) or beside any clock-sensitive cell.
set -euo pipefail
cd /home/doctor/projects/carcassone

LOG="measurement/rustport_exact_solver/logs/run2_resume_$(date +%Y%m%d_%H%M%S).log"
mkdir -p measurement/rustport_exact_solver/logs

# Refuse to start beside a live clock-sensitive run.
if compgen -G "measurement/*/RUN_LIVE.json" > /dev/null; then
  echo "REFUSED: RUN_LIVE.json sentinel(s) present:" | tee -a "$LOG"
  ls measurement/*/RUN_LIVE.json | tee -a "$LOG"
  exit 3
fi

{
  echo "[resume_run2] start $(date -Is) host=$(hostname)"
  # workers=1 is the campaign shape (RAM headroom under the 30GiB per-job cap);
  # each job is single-threaded, worst case 31 jobs x <=2h CPU. Expect long
  # silences: progress prints every 10 jobs only.
  CARCASSONNE_RULES_PROFILE=walled nice -n 19 .venv/bin/python -u \
    scripts/rustport/reconcile_exact_solver.py \
    --leg all --budget 4000000 --workers 1 --tag run2 --resume \
    --job-mem-cap-gb 30 --job-time-cap-secs 7200
  rc=$?
  echo "[resume_run2] driver exited rc=$rc $(date -Is)"
} >> "$LOG" 2>&1
