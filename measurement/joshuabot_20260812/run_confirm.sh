#!/usr/bin/env bash
# Joshua-bot tournament CONFIRM — prereg section 5 rule 4. Top screen cell = J7ZERO
# (margin -17.99, best of six). Fresh SEALED band 1.26e11, n=400 decks x 2 seats = 800 games.
set -euo pipefail
cd /home/doctor/projects/carcassone
P=measurement/joshuabot_20260812
mkdir -p "$P/logs" "$P/confirm"
trap 'rc=$?; [ $rc -ne 0 ] && echo "rc=$rc $(date -Is)" >> '"$P"'/FAILED_CONFIRM' EXIT
nice -n 19 .venv/bin/python -u scripts/joshuabot/h2h.py \
  --decks 400 --seed-base 126000000000 --preset current --j7-weight 0.0 \
  --profile fixed_v1 --workers 30 \
  --out "$P/confirm/J7ZERO_confirm.jsonl" --resume \
  > "$P/logs/confirm_j7zero.log" 2>&1
touch "$P/DONE_CONFIRM"
