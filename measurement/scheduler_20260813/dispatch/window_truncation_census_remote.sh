cd /home/doctor/projects/carcassone || exit 9
set -uo pipefail
BUNDLE="/mnt/carc-shared/bundles/sched_window_truncation_census_20260813_114611.bundle"
drift=$(( $(date +%s) - $(stat -c %Y "$BUNDLE") )); drift=${drift#-}
if [ "$drift" -gt 300 ]; then
  echo "CLOCK DRIFT ${drift}s vs bundle mtime - fix with date -s before launching" >&2; exit 3
fi
git fetch "$BUNDLE" android-app || exit 5
git reset --hard FETCH_HEAD || exit 5
.venv/bin/python -c "import carcassonne_ai" >/dev/null 2>&1 || { echo "venv import failed" >&2; exit 4; }
[ -f "measurement/window_truncation_20260813/RUN_CMD.sh" ] || { echo "launch command measurement/window_truncation_20260813/RUN_CMD.sh absent after sync" >&2; exit 6; }
mkdir -p "/mnt/carc-shared/scheduler_20260813/markers"
nohup systemd-run --user --scope -p MemoryMax=8G bash "/mnt/carc-shared/scheduler_20260813/dispatch/window_truncation_census_run.sh"   >"/mnt/carc-shared/scheduler_20260813/dispatch/window_truncation_census_scope.log" 2>&1 </dev/null &
disown
echo "launched window_truncation_census detached under a MemoryMax=8G scope"
