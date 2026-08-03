#!/usr/bin/env bash
# Candidate iter (neural, v2.8 leaf) vs heur@N_v2.8 ruler — 2-box work-stealing via v28_handoff_orch.sh.
# Answers the continuation's "decisive open test": does the chain's best push ABOVE heur@3200_v28
# (the parity RoD_iter_01 reached)? agent-a iter8 = neural from --ckpt; agent-b heur@N = HeuristicMCTS.
#
# ⚠️ W LESSON #3: heur@3200 workers hold a 3200-sim MCTS tree (the W=20-OOM profile) AND it's
# CPU-bound (the deep search runs on the worker). Conservative + monitored: local OW=24 / laptop OW=8.
# Single net context (the candidate) via carc-orch; the heuristic side is pure CPU.
#
# Usage: OW_LOCAL=24 OW_LAPTOP=8 N=200 HSIMS=3200 bash scripts/rod_v28/run_heur_eval.sh <iter> <seed>
set -uo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

SHARE_LOCAL=/mnt/c/carc-shared; SHARE_REMOTE=/mnt/carc-shared
REPO=/home/doctor/projects/carcassone; LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}
PY=$REPO/.venv/bin/python
CKPT_DIR=$SHARE_LOCAL/rod_v28_overnight_flywheel/ckpt
EVALDIR=$SHARE_LOCAL/rod_v28_overnight_flywheel/evals; EVALDIR_R=${EVALDIR/$SHARE_LOCAL/$SHARE_REMOTE}
OW_LOCAL=${OW_LOCAL:-24}; OW_LAPTOP=${OW_LAPTOP:-8}; N=${N:-200}; HSIMS=${HSIMS:-3200}
USE_LAPTOP=${USE_LAPTOP:-1}; TIMEOUT_S=${TIMEOUT_S:-6000}
HOH=scripts/heuristic_v28/v28_handoff_orch.sh
it=${1:?usage: run_heur_eval.sh <iter> <seed>}; seed=${2:?need seed}
cand=$CKPT_DIR/iter_${it}.pt; cand_r=${cand/$SHARE_LOCAL/$SHARE_REMOTE}
[ -f "$cand" ] || { echo "FATAL: $cand missing" >&2; exit 1; }
sub="iter${it}_vs_heur${HSIMS}_v28"; dir=$EVALDIR/$sub
cd "$REPO"; mkdir -p "$dir" "$EVALDIR/logs"

_reap(){ for p in carc-orch v28hndf eval_hybrid_handoff spawn_main; do
  pkill -9 -f "[${p:0:1}]${p:1}" 2>/dev/null||true
  [ "$USE_LAPTOP" = 1 ] && timeout 15 ssh -o ConnectTimeout=8 "$LAPTOP_SSH" "pkill -9 -f '[${p:0:1}]${p:1}'" </dev/null >/dev/null 2>&1||true
done; }
trap _reap EXIT

echo "### iter_$it vs heur@${HSIMS}_v28  n=$N OW=$OW_LOCAL/$OW_LAPTOP seed=$seed @ $(date) ###"
for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.json" ] || rm -f "$c"; done
_reap; sleep 1

CKPT="$cand" OW="$OW_LOCAL" nohup nice -n 19 bash "$HOH" \
  --agent-a iter8 --meeple-k-a 2.0 --agent-b "heur@${HSIMS}" --meeple-k-b 2.0 \
  --n "$N" --paired --seed-start "$seed" --shared-claim --claim-host local \
  --out-root "$EVALDIR" --out-subdir "$sub" > "$EVALDIR/logs/${sub}_local.log" 2>&1 & disown
if [ "$USE_LAPTOP" = 1 ]; then
  timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
    "cd $REPO && CKPT=$cand_r OW=$OW_LAPTOP setsid nice -n 19 bash $HOH --agent-a iter8 --meeple-k-a 2.0 --agent-b heur@${HSIMS} --meeple-k-b 2.0 --n $N --paired --seed-start $seed --shared-claim --claim-host laptop --out-root $EVALDIR_R --out-subdir $sub > $EVALDIR_R/logs/${sub}_laptop.log 2>&1 </dev/null &" \
    </dev/null >/dev/null 2>&1 || echo "  (laptop launch rc=$? — local continues)"
fi

t=0; last=-1; stall=0
while [ "$(ls "$dir"/seed*_a*.json 2>/dev/null|wc -l)" -lt "$N" ]; do
  sleep 20; t=$((t+20)); cur=$(ls "$dir"/seed*_a*.json 2>/dev/null|wc -l)
  if [ "$cur" = "$last" ]; then stall=$((stall+1)); else stall=0; last=$cur; fi
  [ "$t" -ge "$TIMEOUT_S" ] && { echo "  TIMEOUT at $cur/$N (will tally partial)"; break; }
  [ "$stall" -ge 30 ] && { echo "  STALL at $cur/$N (10min no progress; tally partial)"; break; }
done
_reap; sleep 2

"$PY" scripts/level2/eval_hybrid_handoff.py --agent-a iter8 --meeple-k-a 2.0 --agent-b "heur@${HSIMS}" \
  --meeple-k-b 2.0 --ckpt "$cand" --shm-eval-server x --workers 1 --n "$N" --paired --seed-start "$seed" \
  --out-root "$EVALDIR" --out-subdir "$sub" --summary-only > "$EVALDIR/logs/${sub}_tally.log" 2>&1
echo "=== iter_$it vs heur@${HSIMS}_v28 ($(ls "$dir"/seed*_a*.json 2>/dev/null|wc -l) games) ==="
grep -iE "ELO|paired|signal|tie|^A:|n=" "$EVALDIR/logs/${sub}_tally.log" | head -8 || tail -6 "$EVALDIR/logs/${sub}_tally.log"
