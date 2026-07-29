#!/usr/bin/env bash
# chain_kwidth_22016_20260729.sh — run the G7 probe to completion unattended.
#
# Waits for the pick phase to bank its summary, then launches the oracle scoring phase
# and arms run_watchdog.sh on it. Both phases are --resume safe, so this script is safe
# to re-exec at any point. Detach it: setsid ... </dev/null >/dev/null 2>&1 &
#
# Prereg: measurement/classical_search/KWIDTH_22016_PREREG_20260729.md
set -uo pipefail

REPO=/home/doctor/projects/carcassone
OUT=/mnt/c/carc-shared/oracle_22016_20260729
LOGS="$REPO/measurement/classical_search"
DRIVER="$REPO/scripts/measurement_infra/run_kwidth_22016_20260729.sh"
CHAIN_LOG="$LOGS/kwidth_22016_chain.log"

say() { echo "$(date '+%F %T') $*" >>"$CHAIN_LOG"; }

say "chain armed; waiting for the pick phase"

# --- wait for the pick phase ------------------------------------------------------
# The probe rewrites summary.json at the END of every invocation, so "summary exists AND
# no probe process is alive" is the completion test. Cap the wait at 4 h.
for _ in $(seq 1 1440); do
  if [ -f "$OUT/picks/summary.json" ] \
     && ! ps -eo args --no-headers | grep -q '[k]width_agreement_probe.py'; then
    break
  fi
  sleep 10
done

if ! [ -f "$OUT/picks/summary.json" ]; then
  say "FATAL: pick phase produced no summary within the wait cap; NOT scoring"
  exit 1
fi

NDIS=$(python3 -c "import json;print(json.load(open('$OUT/picks/summary.json'))['n_disagreements'])")
NOK=$(python3 -c "import json;print(json.load(open('$OUT/picks/summary.json'))['n_ok'])")
say "pick phase done: n_ok=$NOK disagreements=$NDIS -> scoring all of them"

# Prereg 5: score the FROZEN disagreement set. --n above the population is a no-op
# (sample_positions returns the whole population), so passing NDIS scores every one.
setsid nice -n 19 bash "$DRIVER" score "$NDIS" </dev/null >/dev/null 2>&1 &
sleep 20
say "scoring launched; arming the watchdog for $NDIS records"

setsid "$REPO/scripts/measurement_infra/run_watchdog.sh" \
  "$OUT/score/records/*.json" "$NDIS" 'oracle_score_pilot' \
  "$LOGS/kwidth_22016_score_watchdog.log" \
  -- bash "$DRIVER" score "$NDIS" </dev/null >/dev/null 2>&1 &

say "watchdog armed; chain done"
