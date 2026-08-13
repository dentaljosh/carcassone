#!/usr/bin/env bash
OUT=/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs
bash "$OUT/BUILD_CMD.sh" >> "$OUT/sync_build.log" 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then touch "$OUT/DONE_BUILD"; else echo "rc=$rc $(date -Is)" >> "$OUT/FAILED_BUILD"; fi
