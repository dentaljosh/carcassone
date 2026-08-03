#!/usr/bin/env bash
# Post-hoc net-vs-net EVAL screens for rod_v28_overnight_flywheel — 2-BOX work-stealing.
# Each candidate iter vs RoD_iter_01 (known baseline), v2.8 leaf, paired, NeuralMCTS@200.
# local + laptop drain ONE game pool via --shared-claim; authoritative tally via --summary-only.
#
# ⚠️ W LESSON: net-vs-net = TWO carc-orch contexts = EVAL workload (NOT gen). Use EVAL worker
# counts — local OW=48 (tuned single-net eval; b512-proven for two-context), laptop OW=16
# (two-context, host-RAM-bound) — NOT the gen W (28/8). Eval workers are lighter than gen
# (no position buffer), but RAM-monitor matchup 1. See docs/CLUSTER_OPS.md "GEN W != EVAL W".
#
# Usage: OW_LOCAL=48 OW_LAPTOP=16 N=100 bash scripts/rod_v28/run_overnight_evals.sh <iter>:<seed> ...
#   e.g. ... 10:1953000000 04:1950000000 07:1951000000 08:1952000000
# elo sign: A=candidate, B=RoD_iter_01, diff=A-B -> elo>0 => candidate STRONGER than RoD_iter_01.
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
REPO_LOCAL=/home/doctor/projects/carcassone; REPO_LAPTOP=/home/doctor/projects/carcassone
LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}
PY=$REPO_LOCAL/.venv/bin/python
RoD1=$SHARE_LOCAL/rod_v28_continuation/ckpt/iter_01.pt
RoD1_R=${RoD1/$SHARE_LOCAL/$SHARE_REMOTE}
CKPT_DIR=$SHARE_LOCAL/rod_v28_overnight_flywheel/ckpt
EVALDIR=$SHARE_LOCAL/rod_v28_overnight_flywheel/evals
EVALDIR_R=${EVALDIR/$SHARE_LOCAL/$SHARE_REMOTE}
HARNESS=scripts/heuristic_v28/v28_net_vs_net_orch.py
HARNESS_SH=scripts/heuristic_v28/v28_net_vs_net_orch.sh
OW_LOCAL=${OW_LOCAL:-48}; OW_LAPTOP=${OW_LAPTOP:-16}; N=${N:-100}
USE_LAPTOP=${USE_LAPTOP:-1}
mkdir -p "$EVALDIR/logs"; cd "$REPO_LOCAL"
[ -f "$RoD1" ] || { echo "FATAL: RoD_iter_01 missing $RoD1" >&2; exit 1; }
[ $# -ge 1 ] || { echo "usage: OW_LOCAL=48 OW_LAPTOP=16 N=100 $0 <iter>:<seed> ..." >&2; exit 1; }

_reap() {   # both boxes: carc-orch FIRST (SHM workers self-exit) + the client + spawn orphans
  for pat in carc-orch v28_net_vs_net spawn_main; do
    pkill -9 -f "[${pat:0:1}]${pat:1}" 2>/dev/null || true
    [ "$USE_LAPTOP" = 1 ] && timeout 15 ssh -o ConnectTimeout=8 "$LAPTOP_SSH" "pkill -9 -f '[${pat:0:1}]${pat:1}'" </dev/null >/dev/null 2>&1 || true
  done
}
trap '_reap' EXIT

# --- one-time laptop sync to THIS branch (ccc33c2 from the flywheel lacks the net-vs-net harness) ---
if [ "$USE_LAPTOP" = 1 ]; then
  BR=$(git branch --show-current)
  git bundle create "$SHARE_LOCAL/code_sync/carc_eval.bundle" "$BR" >/dev/null 2>&1 || echo "WARN: bundle create failed"
  if timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
       "cd $REPO_LAPTOP && git fetch $SHARE_REMOTE/code_sync/carc_eval.bundle $BR && git reset --hard FETCH_HEAD" \
       </dev/null >/dev/null 2>&1; then
    echo "laptop synced to $BR ($(git rev-parse --short "$BR"))"
  else
    echo "WARN: laptop sync FAILED -> running LOCAL-ONLY"; USE_LAPTOP=0
  fi
fi

_count() { ls "$1"/*seed*.json 2>/dev/null | wc -l; }   # per-game files (exclude result.json/meta)

for spec in "$@"; do
  it=${spec%%:*}; seed=${spec##*:}
  cand=$CKPT_DIR/iter_${it}.pt; cand_r=${cand/$SHARE_LOCAL/$SHARE_REMOTE}
  [ -f "$cand" ] || { echo "[skip] iter_$it ckpt missing: $cand" >&2; continue; }
  sub="iter${it}_vs_iter01_n${N}"; dir=$EVALDIR/$sub
  echo ""; echo "########## SCREEN iter_$it vs RoD_iter_01  n=$N seed=$seed OW=$OW_LOCAL/$OW_LAPTOP @ $(date) ##########"
  mkdir -p "$dir"
  for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.json" ] || rm -f "$c"; done
  _reap; sleep 1

  CKPT_A="$cand" CKPT_B="$RoD1" OW="$OW_LOCAL" SIMS=200 \
    nohup nice -n 19 bash "$HARNESS_SH" --n "$N" --paired --c-puct 3.0 --residual-scale 0.25 \
      --meeple-k-a 2.0 --meeple-k-b 2.0 --seed-start "$seed" --out-root "$EVALDIR" --out-subdir "$sub" \
      --shared-claim --claim-host local > "$EVALDIR/logs/${sub}_local.log" 2>&1 & disown
  if [ "$USE_LAPTOP" = 1 ]; then
    timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
      "cd $REPO_LAPTOP && CKPT_A=$cand_r CKPT_B=$RoD1_R OW=$OW_LAPTOP SIMS=200 setsid nice -n 19 bash $HARNESS_SH --n $N --paired --c-puct 3.0 --residual-scale 0.25 --meeple-k-a 2.0 --meeple-k-b 2.0 --seed-start $seed --out-root $EVALDIR_R --out-subdir $sub --shared-claim --claim-host laptop > $EVALDIR_R/logs/${sub}_laptop.log 2>&1 </dev/null &" \
      </dev/null >/dev/null 2>&1 || echo "  (laptop launch rc=$? — continuing; local + heal cover it)"
  fi

  t=0; last=-1; stall=0
  while [ "$(_count "$dir")" -lt "$N" ]; do
    sleep 15; t=$((t+15)); cur=$(_count "$dir")
    if [ "$cur" = "$last" ]; then stall=$((stall+1)); else stall=0; last=$cur; fi
    [ "$t" -ge 2400 ] && { echo "  [iter_$it] TIMEOUT at $cur/$N (40min)"; break; }
    [ "$stall" -ge 40 ] && { echo "  [iter_$it] STALL at $cur/$N (10min no progress)"; break; }
  done
  _reap; sleep 2

  "$PY" "$HARNESS" --checkpoint-a "$cand" --checkpoint-b "$RoD1" \
    --shm-eval-server-a x --shm-eval-server-b y --out-root "$EVALDIR" --out-subdir "$sub" \
    --n "$N" --paired --seed-start "$seed" --summary-only > "$EVALDIR/logs/${sub}_tally.log" 2>&1
  echo "[iter_$it] complete tally ($(_count "$dir") games):"
  grep -E "^A:|paired:|signal" "$EVALDIR/logs/${sub}_tally.log" | sed 's/^/    /' || tail -4 "$EVALDIR/logs/${sub}_tally.log"
done

echo ""; echo "===== SCREEN SUMMARY (A=candidate vs B=RoD_iter_01; elo>0 => candidate stronger) ====="
printf "%-9s %5s %8s %8s %7s  %s\n" "cand" "n" "elo" "pair_z" "wr" "signal"
for spec in "$@"; do
  it=${spec%%:*}; rj=$EVALDIR/iter${it}_vs_iter01_n${N}/result.json
  [ -f "$rj" ] || { printf "%-9s  (no result.json)\n" "iter_$it"; continue; }
  "$PY" -c "
import json; d=json.load(open('$rj')); pz=d.get('paired_z'); pz=0.0 if pz is None else pz
print('%-9s %5s %+8.1f %+8.2f %7.3f  %s' % ('iter_$it', d['n'], d['elo'], pz, d['winrate'], d['signal']))
"
done
