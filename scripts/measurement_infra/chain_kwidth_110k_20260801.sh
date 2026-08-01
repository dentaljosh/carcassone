#!/usr/bin/env bash
# chain_kwidth_110k_20260801.sh — run the "champ vs 10x champ" SCREEN to completion
# unattended on the laptop, then sync the artifacts back to the share.
#
# Waits for the pick phase to bank its summary, then launches the oracle scoring phase over
# the FROZEN disagreement set and arms run_watchdog.sh on it. Both phases are --resume safe,
# so this script is safe to re-exec at any point. Detach it:
#   setsid nohup bash chain_kwidth_110k_20260801.sh </dev/null >/dev/null 2>&1 & disown
#
# Prereg: measurement/classical_search/KWIDTH_110K_PREREG_20260801.md
set -uo pipefail

REPO=/home/doctor/projects/carcassone
OUT=/home/doctor/carc_out/oracle_110k_20260801
SHARE_OUT=/mnt/carc-shared/oracle_110k_20260801
LOGS="$REPO/measurement/classical_search"
DRIVER="$REPO/scripts/measurement_infra/run_kwidth_110k_20260801.sh"
CHAIN_LOG="$LOGS/kwidth_110k_chain.log"

say() { echo "$(date '+%F %T') $*" >>"$CHAIN_LOG"; }

say "chain armed; waiting for the pick phase"

# --- wait for the pick phase ------------------------------------------------------
# The probe rewrites summary.json at the END of every invocation, so "summary exists AND
# no probe process is alive" is the completion test. Cap the wait at 6 h.
for _ in $(seq 1 2160); do
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

# Score the FROZEN disagreement set. --n at/above the population is a no-op
# (sample_positions returns the whole population), so passing NDIS scores every one.
setsid nice -n 19 bash "$DRIVER" score "$NDIS" </dev/null >/dev/null 2>&1 &
sleep 20
say "scoring launched; arming the watchdog for $NDIS records"

setsid "$REPO/scripts/measurement_infra/run_watchdog.sh" \
  "$OUT/score/records/*.json" "$NDIS" 'oracle_score_pilot' \
  "$LOGS/kwidth_110k_score_watchdog.log" \
  -- bash "$DRIVER" score "$NDIS" </dev/null >/dev/null 2>&1 &
WD=$!
say "watchdog armed (pid $WD)"

# --- wait for scoring, then sync artifacts to the share ---------------------------
for _ in $(seq 1 4320); do
  n=$(ls "$OUT/score/records"/*.json 2>/dev/null | wc -l)
  if [ -f "$OUT/score/summary.json" ] && [ "$n" -ge "$NDIS" ] \
     && ! ps -eo args --no-headers | grep -q '[o]racle_score_pilot.py'; then
    break
  fi
  sleep 20
done

say "scoring settled ($(ls "$OUT/score/records"/*.json 2>/dev/null | wc -l)/$NDIS records); syncing to the share"
mkdir -p "$SHARE_OUT"
rsync -a "$OUT/" "$SHARE_OUT/" >>"$CHAIN_LOG" 2>&1 \
  && say "rsync to $SHARE_OUT OK" || say "rsync FAILED — artifacts remain at $OUT"
say "chain done"
