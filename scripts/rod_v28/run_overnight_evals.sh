#!/usr/bin/env bash
# Post-hoc net-vs-net EVAL screens for the rod_v28_overnight_flywheel.
# Each candidate iter vs RoD_iter_01 (the known baseline), v2.8 leaf, paired, NeuralMCTS@200.
#
# ⚠️ W LESSON: this is net-vs-net EVAL (TWO carc-orch contexts), NOT gen. Use the EVAL worker
# count (OW~32-40 two-context), NOT the gen W (28). Eval workers are lighter than gen workers
# (no position buffer) but STILL RAM-monitor the first matchup. See docs/CLUSTER_OPS.md
# "Worker counts — GEN W != EVAL W".
#
# LOCAL-ONLY by design: the local client plays all N and prints/writes a COMPLETE paired tally
# (work-stealing would leave the last box's tally incomplete). v28_net_vs_net_orch.sh trap-cleans
# its own two carc-orch servers on exit, so a normal completion leaves no orphans.
#
# Usage: OW=40 N=100 bash run_overnight_evals.sh <iter>:<seed> [<iter>:<seed> ...]
#   e.g. OW=40 N=100 bash scripts/rod_v28/run_overnight_evals.sh 10:1953000000 04:1950000000
# elo sign: A=candidate, B=RoD_iter_01, diff=A-B -> elo>0 => candidate STRONGER than RoD_iter_01.
set -uo pipefail
REPO=/home/doctor/projects/carcassone
SHARE=/mnt/c/carc-shared
RoD1=$SHARE/rod_v28_continuation/ckpt/iter_01.pt
CKPT_DIR=$SHARE/rod_v28_overnight_flywheel/ckpt
EVALDIR=$SHARE/rod_v28_overnight_flywheel/evals
OW=${OW:-40}; N=${N:-100}
PY=$REPO/.venv/bin/python
mkdir -p "$EVALDIR/logs"
[ -f "$RoD1" ] || { echo "FATAL: RoD_iter_01 missing $RoD1" >&2; exit 1; }
[ $# -ge 1 ] || { echo "usage: OW=40 N=100 $0 <iter>:<seed> ..." >&2; exit 1; }

for spec in "$@"; do
  it=${spec%%:*}; seed=${spec##*:}
  cand=$CKPT_DIR/iter_${it}.pt
  [ -f "$cand" ] || { echo "[skip] iter_$it ckpt missing: $cand" >&2; continue; }
  sub="iter${it}_vs_iter01_n${N}"
  echo ""; echo "########## SCREEN iter_$it vs RoD_iter_01  n=$N OW=$OW seed=$seed @ $(date) ##########"
  CKPT_A="$cand" CKPT_B="$RoD1" OW="$OW" SIMS=200 \
    nice -n 19 bash "$REPO/scripts/heuristic_v28/v28_net_vs_net_orch.sh" \
      --n "$N" --paired --c-puct 3.0 --residual-scale 0.25 --meeple-k-a 2.0 --meeple-k-b 2.0 \
      --seed-start "$seed" --out-root "$EVALDIR" --out-subdir "$sub" \
      > "$EVALDIR/logs/${sub}.log" 2>&1
  echo "[iter_$it] done @ $(date):"
  grep -E "^A:|paired:|signal:" "$EVALDIR/logs/${sub}.log" | sed 's/^/    /' || tail -5 "$EVALDIR/logs/${sub}.log"
done

echo ""; echo "===== SCREEN SUMMARY (A=candidate vs B=RoD_iter_01; elo>0 => candidate stronger) ====="
printf "%-9s %5s %8s %8s %7s  %s\n" "cand" "n" "elo" "pair_z" "wr" "signal"
for spec in "$@"; do
  it=${spec%%:*}; rj=$EVALDIR/iter${it}_vs_iter01_n${N}/result.json
  [ -f "$rj" ] || { printf "%-9s  (no result.json)\n" "iter_$it"; continue; }
  "$PY" -c "
import json; d=json.load(open('$rj'))
pz=d.get('paired_z'); pz=0.0 if pz is None else pz
print('%-9s %5s %8s %8s %7s  %s' % ('iter_$it', d['n'], ('%+.1f'%d['elo']), ('%+.2f'%pz), ('%.3f'%d['winrate']), d['signal']))
"
done
