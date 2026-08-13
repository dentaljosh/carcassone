#!/usr/bin/env bash
# Stage A chain (owner-authorized 2026-08-12 "Do it all"): champ_picks -> rebuild with
# picks -> rust arm (walled selfplay) -> python arm (fixed_v1+app_aug2 E4), sequential,
# full box each (the dedupe agent measured a mixed launch starves the python legs).
# Detach with setsid nohup; DONE/FAILED markers for the session monitor.
set -euo pipefail
cd /home/doctor/projects/carcassone
P=measurement/tiletie_pricing_20260812
mkdir -p "$P/logs"
trap 'rc=$?; if [ $rc -ne 0 ]; then echo "rc=$rc $(date -Is)" >> '"'"'measurement/tiletie_pricing_20260812/FAILED_STAGEA'"'"'; fi' EXIT

nice -n 19 .venv/bin/python -u scripts/tiletie/champ_picks.py \
  --rules-profile walled --workers 14 > "$P/logs/champ_picks.log" 2>&1

nice -n 19 .venv/bin/python scripts/tiletie/build_positions.py \
  --n-selfplay 280 --n-e4 60 --allow-missing-champ-picks \
  --champ-picks "$P/champ_picks/champ_picks.jsonl" \
  --out-dir "$P/positions_stageA" > "$P/logs/rebuild_stageA.log" 2>&1

nice -n 19 .venv/bin/python -u scripts/tiletie/run_tiletie.py --yes --workers 14 \
  --positions-dir "$P/positions_stageA" --only-profiles walled \
  --manifest-out "$P/RUN_MANIFEST_stageA_rust.json" \
  --gate-out "$P/GATE_BACKEND_RECHECK_stageA_rust.json" > "$P/logs/stageA_rust.log" 2>&1

nice -n 19 .venv/bin/python -u scripts/tiletie/run_tiletie.py --yes --workers 14 \
  --positions-dir "$P/positions_stageA" --only-profiles fixed_v1 app_aug2 \
  --manifest-out "$P/RUN_MANIFEST_stageA_python.json" \
  --gate-out "$P/GATE_BACKEND_RECHECK_stageA_python.json" > "$P/logs/stageA_python.log" 2>&1

touch "$P/DONE_STAGEA"
