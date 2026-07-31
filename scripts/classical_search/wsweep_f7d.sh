#!/bin/bash
# F7d — W sweep for the CPU-only leaf-eval workload class (eval_puct_priors, sims=2750,
# exact-K2, Cython leaf, net-free). Authorized by Joshua 2026-07-31 00:15 ("pretty sure it
# should be w16 for CPU leaf evals. you can do proper sweeps on both boxes when they free
# up"); roadmap F7d. House protocol (memory feedback_worker_count_by_bottleneck): crude
# multi-point -> refine at the knee -> settle the SMALLEST W within ~5-10% of peak; PER-BOX.
#
# Design notes:
# - Workload = the leaf-ablation anticoff cell config (the ~null knockout: same code paths,
#   ms_ratio 1.00 vs the intact champion), so the W number transfers to the F7 workload
#   class directly. Cell json: measurement/leaf_ablation_20260730/cells/.
# - Metric = steady-state throughput index W / mean(ms_per_move), read from the per-point
#   summary.json prefix-ms fields — NOT n/wallclock, which is polluted by the tail (last
#   games idling workers) and by the order-statistic trap (first-completions bias).
# - Each point runs INDEPENDENTLY per box: NO --shared-claim (a sweep point must measure
#   this box alone), throwaway smoke band 9.69e10 + per-box out-subdir (throughput only —
#   no strength claim, band unregistered, n far below any reporting threshold).
# - Points run SEQUENTIALLY on a box (a point must own the box); the two boxes run their
#   sweeps in parallel (different out-subdirs; the share is only storage here).
# - --no-results-csv always: this is a bench, not an experiment row.
#
# Usage (detach! nohup ... & disown):
#   local : nohup nice -n 19 bash scripts/classical_search/wsweep_f7d.sh local  "12 16 24 30" > /tmp/wsweep_local.log  2>&1 & disown
#   laptop: nohup nice -n 19 bash scripts/classical_search/wsweep_f7d.sh laptop "12 16 22 30" > /tmp/wsweep_laptop.log 2>&1 & disown
# Optional env: WSWEEP_N (games/point, default 24), WSWEEP_BAND (default 96900000000).
set -u
BOX_TAG="${1:?usage: wsweep_f7d.sh <local|laptop> \"<W list>\"}"
WLIST="${2:?quoted W list required, e.g. \"12 16 24 30\"}"

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
CELL_JSON=$REPO/measurement/leaf_ablation_20260730/cells/abl_anticoff_vs_puctchamp2750_k2.json
OUT_TSV=$REPO/measurement/classical_search/WSWEEP_F7D_${BOX_TAG}.tsv

N="${WSWEEP_N:-24}"                 # 12 decks x 2 seats per point — enough moves for stable ms
BAND="${WSWEEP_BAND:-96900000000}"  # the ablation smoke's throwaway band (9.69e10)
K=2; CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits; SIMS=2750

case "$BOX_TAG" in
  local)  SHARE=/mnt/c/carc-shared ;;
  laptop) SHARE=/mnt/carc-shared ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|laptop)"; exit 1 ;;
esac
OUT_ROOT=$SHARE/leaf_ablation
[ -f "$CELL_JSON" ] || { echo "missing cell json $CELL_JSON"; exit 1; }

# champion env — identical to leaf_ablation_launcher.sh (the workload being calibrated)
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd $REPO || exit 1
ts() { date +%F_%T; }

[ -f "$OUT_TSV" ] || echo -e "box\tW\tn\tsecs_wall\tcand_ms_per_move\tchamp_ms_per_move\tthroughput_idx\tsolver_secs_per_game\ttimestamp" > "$OUT_TSV"
echo "[wsweep $BOX_TAG $(ts)] start: W list = [$WLIST], n/point=$N, band=$BAND"

for W in $WLIST; do
  # a point must saturate the box for most of its life: n >= 2*W (rounded up to a paired even)
  PN=$N; [ "$PN" -lt $((2*W)) ] && PN=$((2*W)); PN=$(( (PN+1)/2*2 ))
  sub="wsweep_${BOX_TAG}_w${W}"
  dir="$OUT_ROOT/$sub"
  if [ -f "$dir/summary.json" ] && $PY -c "import json,sys;s=json.load(open(sys.argv[1]));sys.exit(0 if s.get('n',0)>=int(sys.argv[2]) else 1)" "$dir/summary.json" "$PN" 2>/dev/null; then
    echo "[wsweep $BOX_TAG $(ts)] W=$W cached -> skip"
  else
    mkdir -p "$dir"
    echo "[wsweep $BOX_TAG $(ts)] W=$W point start (n=$PN)"
    t0=$(date +%s)
    nice -n 19 $PY "$HARNESS" \
      --candidate puct --opponent puct \
      --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT \
      --cand-sims $SIMS --exact-k $K --n $PN --paired \
      --cand-leaf-json "$CELL_JSON" --exp-id "wsweep_${BOX_TAG}_w${W}" \
      --seed-start $BAND --out-root "$OUT_ROOT" --out-subdir "$sub" \
      --workers "$W" --no-results-csv > "/tmp/wsweep_${BOX_TAG}_w${W}.log" 2>&1
    secs=$(( $(date +%s) - t0 ))
    echo "$secs" > "$dir/.wall_secs"
  fi
  $PY - "$BOX_TAG" "$W" "$dir" >> "$OUT_TSV" <<'PYEOF'
import json, sys, time, os
box, w, d = sys.argv[1:4]
s = json.load(open(os.path.join(d, "summary.json")))
wall = open(os.path.join(d, ".wall_secs")).read().strip() if os.path.exists(os.path.join(d, ".wall_secs")) else "-"
cand = s.get("cand_prefix_ms_per_move", float("nan")); champ = s.get("champ_prefix_ms_per_move", float("nan"))
mean_ms = (cand + champ) / 2.0
idx = float(w) / mean_ms * 1000.0  # moves/sec across the box, tail-free
print(f"{box}\t{w}\t{s.get('n','-')}\t{wall}\t{cand:.1f}\t{champ:.1f}\t{idx:.3f}\t{s.get('solver_secs_per_game',float('nan')):.1f}\t{time.strftime('%F_%T')}")
PYEOF
  echo "[wsweep $BOX_TAG $(ts)] W=$W -> $(tail -1 "$OUT_TSV")"
done
echo "[wsweep $BOX_TAG $(ts)] SWEEP DONE"
cat "$OUT_TSV"
