#!/bin/bash
# Phase 1.1b transitivity round-robin launcher (ROUND_ROBIN_PLAN.md, pre-reg 2d2ab10).
# Two-box work-stealing via --shared-claim, same pattern as run_screen_sweep.sh.
# Usage: run_round_robin.sh <primary|helper> <cell> [workers]
#   cell in {rr1,rr2,rr3,rr4}. Workers default per Joshua 2026-07-06:
#   CPU-only cells (rr3/rr4): local 30 / laptop 22. Orch cells (rr1/rr2): local 48 / laptop 26.
set -u
ROLE="${1:?role primary|helper}"; CELL="${2:?cell rr1|rr2|rr3|rr4}"; WOVR="${3:-}"
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
N=200; K=2
NET_CKPT=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt
HOST=$(hostname)
# share root differs by box: local sees /mnt/c/carc-shared, laptop /mnt/carc-shared
if [ -d /mnt/c/carc-shared ]; then SHARE=/mnt/c/carc-shared; else SHARE=/mnt/carc-shared; NET_CKPT=/mnt/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt; fi
OUT_ROOT=$SHARE/puct_roundrobin

case "$CELL" in
  rr1) CAND="puct";  OPP="net:$NET_CKPT"; BAND=9500000000; ORCH=1;;
  rr2) CAND="h6400"; OPP="net:$NET_CKPT"; BAND=9500000000; ORCH=1;;
  rr3) CAND="puct";  OPP="h12800";        BAND=9600000000; ORCH=0;;
  rr4) CAND="h6400"; OPP="h12800";        BAND=9600000000; ORCH=0;;
  *) echo "bad cell $CELL"; exit 1;;
esac
if [ -n "$WOVR" ]; then W=$WOVR
elif [ "$ORCH" = 1 ]; then { [ "$SHARE" = /mnt/c/carc-shared ] && W=48 || W=26; }
else { [ "$SHARE" = /mnt/c/carc-shared ] && W=30 || W=22; }
fi
SUB="rr_${CAND}_vs_${OPP//[:\/]/-}_k${K}"; SUB="rr_${CELL}_k${K}"   # stable short name; harness manifest carries full spec
DIR="$OUT_ROOT/$SUB"; mkdir -p "$DIR"
PROG=$REPO/measurement/classical_search/ROUND_ROBIN_PROGRESS.tsv

export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
ORCH_FLAGS=""
if [ "$ORCH" = 1 ]; then
  # carc-orch SHM client (harness --shm-eval-server). Start the server on THIS box first
  # (it owns the GPU; the harness workers are CPU-only SHM clients), then export
  # CARC_ORCH_SHM=<shm-name> before running this launcher. Server recipe (per box):
  #   $PY scripts/export_torchscript.py --checkpoint $NET_CKPT --out /tmp/carc_rr_iter02.ts.pt --device cuda
  #   nice -n 19 rust/carc-orch/run_server.sh --model /tmp/carc_rr_iter02.ts.pt --transport shm \
  #     --shm-name <shm-name> --workers <W> --n-scalar 12 --device cuda --max-batch 16 \
  #     --batch-timeout-ms 2.0 --forwarders 4 --watchdog-secs 30
  # (iter_02.pt n_scalar_features=12. Without CARC_ORCH_SHM the cell still runs, net-on-CPU.)
  [ -n "${CARC_ORCH_SHM:-}" ] && ORCH_FLAGS="--shm-eval-server ${CARC_ORCH_SHM}"
else
  export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
fi
cd $REPO || exit 1

count_results() { ls "$1"/seed*_a*.json 2>/dev/null | grep -vc summary; }
clean_stale() { find "$1" -name 'seed*.claim' -mmin +4 2>/dev/null | while read -r c; do [ -f "${c%.claim}.json" ] || rm -f "$c"; done; }

[ "$ROLE" = primary ] && clean_stale "$DIR"
echo "[$ROLE $HOST] $CELL start W=$W ($(count_results "$DIR")/$N cached)"
t0=$(date +%s); iter=0
while [ "$(count_results "$DIR")" -lt "$N" ] && [ $iter -lt 80 ]; do
  # shellcheck disable=SC2086
  $PY "$HARNESS" --candidate "$CAND" --opponent "$OPP" $ORCH_FLAGS \
    --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits \
    --cand-sims 2750 --champ-sims 6400 --exact-k $K --n $N --paired \
    --workers "$W" --shared-claim --claim-host "$ROLE-$HOST" --claim-stale-secs 300 \
    --no-results-csv --seed-start $BAND --out-root "$OUT_ROOT" --out-subdir "$SUB" \
    > /tmp/rr_${ROLE}_${CELL}.log 2>&1
  clean_stale "$DIR"; iter=$((iter+1))
  [ "$(count_results "$DIR")" -lt "$N" ] && sleep 5
done
if [ "$ROLE" = primary ]; then
  # shellcheck disable=SC2086
  $PY "$HARNESS" --candidate "$CAND" --opponent "$OPP" $ORCH_FLAGS \
    --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits \
    --cand-sims 2750 --champ-sims 6400 --exact-k $K --n $N --paired \
    --seed-start $BAND --out-root "$OUT_ROOT" --out-subdir "$SUB" > /tmp/rr_agg_${CELL}.log 2>&1
  secs=$(( $(date +%s) - t0 ))
  [ -f "$PROG" ] || echo -e "cell\tn\tW\tD\tL\telo\tsigma\tpaired_z\tsecs" > "$PROG"
  $PY - "$DIR/summary.json" "$CELL" "$secs" >> "$PROG" 2>/tmp/rr_parse_${CELL}.log <<'PYEOF'
import json,sys
p,cell,secs=sys.argv[1:4]
s=json.load(open(p))
print(f"{cell}\t{s['n']}\t{s['W']}\t{s['D']}\t{s['L']}\t{s['elo']:.1f}\t{s['elo_sig_1sigma']:.1f}\t{s.get('paired_z',float('nan')):.2f}\t{secs}")
PYEOF
  echo "[primary] $CELL DONE in ${secs}s -> $(tail -1 "$PROG")"
fi
