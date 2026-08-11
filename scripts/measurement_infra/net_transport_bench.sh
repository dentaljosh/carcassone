#!/usr/bin/env bash
# Launcher for the G3 net forward-transport bench (net_transport_bench.py).
#
#   ./net_transport_bench.sh                 # the real bench (QUIET WINDOW ONLY)
#   ./net_transport_bench.sh --smoke --out /path/smoke.json
#
# The bench REFUSES to run at 1m loadavg > 4 (pass --force to override). Run it
# with NOTHING else on the box: it is a latency measurement, and every cost ratio
# in this project has moved when re-probed unloaded.
#
# Detached by default (Mac->Windows->WSL SIGHUP kills tty-attached jobs); the
# real bench is ~2-5 min, so it is nohup'd and the log is tailed at the end.
set -euo pipefail

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY=python3
BENCH="$REPO/scripts/measurement_infra/net_transport_bench.py"

OUT_DEFAULT="$REPO/measurement/net_transport/net_transport_bench_$(date +%Y%m%d_%H%M).json"

# --smoke short-circuits the detach (it is sub-minute and its output is a
# plumbing proof, not a measurement).
for a in "$@"; do
  if [ "$a" = "--smoke" ]; then
    exec "$PY" "$BENCH" "$@"
  fi
done

mkdir -p "$(dirname "$OUT_DEFAULT")"
LOG="${OUT_DEFAULT%.json}.log"

echo "pre-flight census (this bench needs a QUIET box):"
cat /proc/loadavg
ps -o pid,etime,%cpu,comm -C python --sort=-etime 2>/dev/null | head -15 || true
command -v nvidia-smi >/dev/null && nvidia-smi \
  --query-gpu=name,power.draw,utilization.gpu,memory.used --format=csv,noheader || true

nohup nice -n 19 "$PY" "$BENCH" --out "$OUT_DEFAULT" "$@" >"$LOG" 2>&1 &
disown
echo "launched pid $! -> $LOG"
echo "result JSON -> $OUT_DEFAULT"
