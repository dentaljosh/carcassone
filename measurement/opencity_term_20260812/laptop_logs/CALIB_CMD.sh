#!/usr/bin/env bash
cd /home/doctor/projects/carcassone
L=measurement/opencity_term_20260812/laptop_logs
nice -n 19 .venv/bin/python -u scripts/classical_search/opencity_e4_replay.py \
  -o measurement/opencity_term_20260812/calib \
  --workers 13 \
  >> $L/calib.log 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then touch $L/DONE_CALIB; else echo "rc=$rc $(date -Is)" >> $L/FAILED_CALIB; fi
