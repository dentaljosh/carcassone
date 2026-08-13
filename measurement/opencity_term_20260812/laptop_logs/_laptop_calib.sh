set -euo pipefail
cd /home/doctor/projects/carcassone
mkdir -p "/home/doctor/projects/carcassone/measurement/opencity_term_20260812/calib" "/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs"
rm -f "/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs/DONE_CALIB" "/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs/FAILED_CALIB"
chmod +x "/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs/CALIB_CMD.sh"
nohup systemd-run --user --scope -p MemoryMax=8G bash "/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs/CALIB_CMD.sh"   > "/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs/calib_scope.log" 2>&1 < /dev/null &
disown
echo "calibration launched detached at W=13 (MemoryMax=8G)"
