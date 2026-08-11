#!/usr/bin/env bash
# wbench2.sh — high-W extension of the eval-W micro-sweep.
# Adds: N env (bigger workload to kill wave-quantization at high W) and a RAM gate
# (skip a point if available RAM < GATE_MIN_G — protects the 11G laptop from sshd-wedge).
set -uo pipefail
SHARE=${SHARE:?}; PTS=${PTS:?}; HOSTTAG=${HOSTTAG:?}; N=${N:-48}; GATE_MIN_G=${GATE_MIN_G:-0}
REPO=/home/doctor/projects/carcassone
ROOT="$SHARE/distill_flywheel_sighted_20260716"
WRAP="$REPO/scripts/classical_search/fair_net_vs_net_orch.sh"
cd "$REPO" || exit 1
ts() { date '+%F %T'; }
echo "[wbench2 $(ts)] START host=$HOSTTAG points=$PTS n=$N gate=${GATE_MIN_G}G"
for W in $PTS; do
  avail=$(free -g | awk 'NR==2{print $7}')
  if [ "$avail" -lt "$GATE_MIN_G" ]; then
    echo "[wbench2 $(ts)] SKIP W=$W: avail ${avail}G < gate ${GATE_MIN_G}G"
    continue
  fi
  SUB="wbench_${HOSTTAG}_w${W}_n${N}"
  echo "[wbench2 $(ts)] POINT W=$W n=$N (avail ${avail}G) -> $SUB"
  CAND_CKPT="$ROOT/ckpt/iter_20.pt" \
  OPP_CKPT="$SHARE/rod_v2_flywheel/ckpt/iter_02.pt" \
  OW=$W OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  nice -n 19 bash "$WRAP" \
    --exact-k 2 --k-dets 2 --sims 200 --n "$N" --paired \
    --seed-start 90000000000 \
    --out-root "$ROOT" --out-subdir "$SUB" --no-results-csv
  # ⚠️ rc FIRST, before any $(...) in the log line: command substitutions execute during
  #    word expansion and reset $?, so an inline `rc=$?` alongside $(ts)/$(ls) reports 0
  #    for a failed point.
  rc=$?
  echo "[wbench2 $(ts)] POINT W=$W exit rc=$rc ($(ls "$ROOT/$SUB"/seed*_a*.json 2>/dev/null | wc -l)/$N jsons, avail now $(free -g | awk 'NR==2{print $7}')G)"
done
echo "[wbench2 $(ts)] SWEEP DONE"
