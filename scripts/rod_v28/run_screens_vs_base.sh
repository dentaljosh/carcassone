#!/usr/bin/env bash
# Generalized post-hoc net-vs-net EVAL screens for rod_v28_overnight_flywheel — 2-BOX work-stealing.
# Same machinery as run_overnight_evals.sh, but the B baseline is PARAMETERIZED:
#   BASE_CKPT (default RoD_iter_01) and BASE_TAG (label used in the subdir + summary).
# Use for the conditional "candidate vs iter_08" screens (BASE_CKPT=.../iter_08.pt BASE_TAG=iter08)
# without editing the running run_overnight_evals.sh.
#
# ⚠️ W LESSON: net-vs-net = TWO carc-orch contexts = EVAL workload. local OW=48 / laptop OW=16
# (RAM-validated). See docs/CLUSTER_OPS.md "GEN W != EVAL W".
#
# Usage: BASE_CKPT=<path> BASE_TAG=iter08 OW_LOCAL=48 OW_LAPTOP=16 N=100 \
#          bash scripts/rod_v28/run_screens_vs_base.sh <iter>:<seed> ...
# elo sign: A=candidate, B=BASE -> elo>0 => candidate STRONGER than the baseline.
set -uo pipefail
SHARE_LOCAL=/mnt/c/carc-shared; SHARE_REMOTE=/mnt/carc-shared
REPO_LOCAL=/home/doctor/projects/carcassone; REPO_LAPTOP=/home/doctor/projects/carcassone
LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}
PY=$REPO_LOCAL/.venv/bin/python
BASE_CKPT=${BASE_CKPT:-$SHARE_LOCAL/rod_v28_continuation/ckpt/iter_01.pt}
BASE_TAG=${BASE_TAG:-iter01}
BASE_R=${BASE_CKPT/$SHARE_LOCAL/$SHARE_REMOTE}
CKPT_DIR=$SHARE_LOCAL/rod_v28_overnight_flywheel/ckpt
EVALDIR=$SHARE_LOCAL/rod_v28_overnight_flywheel/evals
EVALDIR_R=${EVALDIR/$SHARE_LOCAL/$SHARE_REMOTE}
HARNESS=scripts/heuristic_v28/v28_net_vs_net_orch.py
HARNESS_SH=scripts/heuristic_v28/v28_net_vs_net_orch.sh
OW_LOCAL=${OW_LOCAL:-48}; OW_LAPTOP=${OW_LAPTOP:-16}; N=${N:-100}
USE_LAPTOP=${USE_LAPTOP:-1}
mkdir -p "$EVALDIR/logs"; cd "$REPO_LOCAL"
[ -f "$BASE_CKPT" ] || { echo "FATAL: BASE ckpt missing $BASE_CKPT" >&2; exit 1; }
[ $# -ge 1 ] || { echo "usage: BASE_CKPT=.. BASE_TAG=iter08 N=100 $0 <iter>:<seed> ..." >&2; exit 1; }

_reap() {   # both boxes: carc-orch FIRST (SHM workers self-exit) + the client + spawn orphans
  for pat in carc-orch v28_net_vs_net spawn_main; do
    pkill -9 -f "[${pat:0:1}]${pat:1}" 2>/dev/null || true
    [ "$USE_LAPTOP" = 1 ] && timeout 15 ssh -o ConnectTimeout=8 "$LAPTOP_SSH" "pkill -9 -f '[${pat:0:1}]${pat:1}'" </dev/null >/dev/null 2>&1 || true
  done
}
trap '_reap' EXIT

# --- one-time laptop sync to THIS branch ---
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
  sub="iter${it}_vs_${BASE_TAG}_n${N}"; dir=$EVALDIR/$sub
  echo ""; echo "########## SCREEN iter_$it vs $BASE_TAG  n=$N seed=$seed OW=$OW_LOCAL/$OW_LAPTOP @ $(date) ##########"
  mkdir -p "$dir"
  for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.json" ] || rm -f "$c"; done
  _reap; sleep 1

  CKPT_A="$cand" CKPT_B="$BASE_CKPT" OW="$OW_LOCAL" SIMS=200 \
    nohup nice -n 19 bash "$HARNESS_SH" --n "$N" --paired --c-puct 3.0 --residual-scale 0.25 \
      --meeple-k-a 2.0 --meeple-k-b 2.0 --seed-start "$seed" --out-root "$EVALDIR" --out-subdir "$sub" \
      --shared-claim --claim-host local > "$EVALDIR/logs/${sub}_local.log" 2>&1 & disown
  if [ "$USE_LAPTOP" = 1 ]; then
    timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
      "cd $REPO_LAPTOP && CKPT_A=$cand_r CKPT_B=$BASE_R OW=$OW_LAPTOP SIMS=200 setsid nice -n 19 bash $HARNESS_SH --n $N --paired --c-puct 3.0 --residual-scale 0.25 --meeple-k-a 2.0 --meeple-k-b 2.0 --seed-start $seed --out-root $EVALDIR_R --out-subdir $sub --shared-claim --claim-host laptop > $EVALDIR_R/logs/${sub}_laptop.log 2>&1 </dev/null &" \
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

  "$PY" "$HARNESS" --checkpoint-a "$cand" --checkpoint-b "$BASE_CKPT" \
    --shm-eval-server-a x --shm-eval-server-b y --out-root "$EVALDIR" --out-subdir "$sub" \
    --n "$N" --paired --seed-start "$seed" --summary-only > "$EVALDIR/logs/${sub}_tally.log" 2>&1
  echo "[iter_$it] complete tally ($(_count "$dir") games):"
  grep -E "^A:|paired:|signal" "$EVALDIR/logs/${sub}_tally.log" | sed 's/^/    /' || tail -4 "$EVALDIR/logs/${sub}_tally.log"
done

echo ""; echo "===== SCREEN SUMMARY (A=candidate vs B=$BASE_TAG; elo>0 => candidate stronger) ====="
printf "%-9s %5s %8s %8s %7s  %s\n" "cand" "n" "elo" "pair_z" "wr" "signal"
for spec in "$@"; do
  it=${spec%%:*}; rj=$EVALDIR/iter${it}_vs_${BASE_TAG}_n${N}/result.json
  [ -f "$rj" ] || { printf "%-9s  (no result.json)\n" "iter_$it"; continue; }
  "$PY" -c "
import json; d=json.load(open('$rj')); pz=d.get('paired_z'); pz=0.0 if pz is None else pz
print('%-9s %5s %+8.1f %+8.2f %7.3f  %s' % ('iter_$it', d['n'], d['elo'], pz, d['winrate'], d['signal']))
"
done
