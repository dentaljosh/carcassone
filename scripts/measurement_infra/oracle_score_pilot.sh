#!/usr/bin/env bash
# Launcher for the oracle-scored disagreement PILOT (oracle_score_pilot.py).
#
# STATUS: PILOT ONLY, local box only. Measures the per-position sd of the world-CRN-paired
# oracle delta on ~20 CL-070 disagreement positions — the one unknown that decides whether
# the full ~652-position probe is powered (memo §4.2 fork: sd 0.5 => z 2.2, sd 1.5 => z 0.75).
#
# Detaches per the standing rule (Mac sleep / WSL teardown kill tty-attached jobs) and runs
# niced so it yields to interactive use.
#
# Usage:
#   scripts/measurement_infra/oracle_score_pilot.sh                 # the real 20-position pilot
#   scripts/measurement_infra/oracle_score_pilot.sh --smoke         # 2 positions, M=4, W=2
#   scripts/measurement_infra/oracle_score_pilot.sh --fg -- <args>  # foreground, args passed through
#
# Any trailing args after `--` are forwarded verbatim to oracle_score_pilot.py.
set -euo pipefail

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
SCRIPT="$REPO/scripts/measurement_infra/oracle_score_pilot.py"

WORKERS=${WORKERS:-8}
N=${N:-20}
M=${M:-32}
ORACLE_SIMS=${ORACLE_SIMS:-100}
OUT_SUBDIR=${OUT_SUBDIR:-oracle_score_pilot}
FG=0
PASS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke)  N=2; M=4; WORKERS=2; OUT_SUBDIR=oracle_score_pilot_smoke; FG=1; shift ;;
    --fg)     FG=1; shift ;;
    --)       shift; PASS=("$@"); break ;;
    *)        PASS+=("$1"); shift ;;
  esac
done

ARGS=(--n "$N" --m "$M" --oracle-sims "$ORACLE_SIMS" --workers "$WORKERS"
      --out-subdir "$OUT_SUBDIR" --resume)
if [[ ${#PASS[@]} -gt 0 ]]; then ARGS+=("${PASS[@]}"); fi

LOG=${LOG:-$REPO/measurement/classical_search/${OUT_SUBDIR}.log}
mkdir -p "$(dirname "$LOG")"

# Pre-launch process census — standing rule, do it BY DEFAULT.
echo "=== process census (python, by age) ==="
ps -o pid,etime,%cpu,comm -C python --sort=-etime 2>/dev/null | head -15 || true
echo "load: $(cut -d' ' -f1-3 /proc/loadavg)"
echo "=== launching: $PY $SCRIPT ${ARGS[*]} ==="

if [[ "$FG" == "1" ]]; then
  exec nice -n 19 "$PY" -u "$SCRIPT" "${ARGS[@]}"
else
  nohup nice -n 19 "$PY" -u "$SCRIPT" "${ARGS[@]}" >"$LOG" 2>&1 &
  disown
  echo "launched pid $! -> $LOG"
fi
