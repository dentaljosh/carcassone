#!/bin/bash
# Gen W-sweep, Rust era (2026-08-02) — gen_fair_distill at PRODUCTION knobs
# (k8x1376, exact-K2, --backend rust, farm rust-threads=1) per box.
#
# Metric: steady-state throughput from shard mtimes with the FIRST WAVE DROPPED
# (first W shards = warmup; order-statistic trap memory). throughput_idx =
# plies_after_wave / (t_last - t_waveW) — plies read from the --log-actions json.
# RAM is the second axis (gen W is historically RAM-capped): peak `free -g` sampled
# every 30 s per point and reported; a point that pushes available <2G aborts the sweep.
#
# Usage (detach): nohup nice -n 19 bash scripts/classical_search/wsweep_gen_rust.sh laptop "8 12 16 20" > /tmp/wsweep_gen_laptop.log 2>&1 & disown
set -u
BOX_TAG="${1:?usage: wsweep_gen_rust.sh <local|laptop> \"<W list>\"}"
WLIST="${2:?quoted W list required}"
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
GEN=$REPO/scripts/distill_flywheel/gen_fair_distill.py
OUT_ROOT="${WSWEEP_GEN_OUT:-$HOME/carc_out/wsweep_gen_20260802}"
OUT_TSV=$REPO/measurement/classical_search/WSWEEP_GEN_RUST_${BOX_TAG}.tsv
ROUNDS="${WSWEEP_GEN_ROUNDS:-3}"   # games per worker per point
SEED0="${WSWEEP_GEN_SEED0:-96900000000}"  # throwaway; throughput only, no strength claim

# champion env — identical to the production gen launchers (leaf must hash to the
# champion config, else the sweep prices a different workload)
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd $REPO || exit 1
ts() { date +%F_%T; }
[ -f "$OUT_TSV" ] || echo -e "box\tW\tn_games\tplies_total\tsecs_steady\tms_per_move_steady\tthroughput_idx\tpeak_ram_used_g\tmin_avail_g\ttimestamp" > "$OUT_TSV"
echo "[gensweep $BOX_TAG $(ts)] start: W=[$WLIST] rounds=$ROUNDS out=$OUT_ROOT"

for W in $WLIST; do
  N=$((W*ROUNDS)); dir="$OUT_ROOT/w${W}"; mkdir -p "$dir"
  echo "[gensweep $BOX_TAG $(ts)] W=$W point start (n=$N)"
  # RAM sampler (30s) alongside the point
  ramlog="$dir/.ram.log"; : > "$ramlog"
  ( while true; do free -g | awk '/^Mem:/{print $3, $7}'; sleep 30; done >> "$ramlog" ) &
  RAMPID=$!
  nice -n 19 $PY "$GEN" --games $N --k-dets 8 --sims 1376 --exact-max-k 2 \
    --backend rust --workers $W --seed-start $SEED0 \
    --out "$dir" --log-actions > "$dir/run.log" 2>&1
  rc=$?
  kill $RAMPID 2>/dev/null || true
  [ $rc -ne 0 ] && { echo "[gensweep $BOX_TAG $(ts)] W=$W FAILED rc=$rc — see $dir/run.log"; exit $rc; }
  $PY - "$BOX_TAG" "$W" "$dir" >> "$OUT_TSV" <<'PYEOF'
import json, sys, time, os, glob
box, w, d = sys.argv[1], int(sys.argv[2]), sys.argv[3]
shards = sorted(glob.glob(os.path.join(d, "seed_*.npz")), key=os.path.getmtime)
plies = {}
for j in glob.glob(os.path.join(d, "seed_*.json")) + glob.glob(os.path.join(d, "actions", "seed_*.json")):
    r = json.load(open(j)); plies[r["deck_seed"]] = r["n_plies"]
def seed_of(p): return int(os.path.basename(p)[5:17])
if len(shards) <= w:
    print(f"{box}\t{w}\tTOO_FEW_SHARDS\t-\t-\t-\t-\t-\t-\t{time.strftime('%F_%T')}"); sys.exit()
t_wave = os.path.getmtime(shards[w-1]); t_last = os.path.getmtime(shards[-1])
steady = shards[w:]
pl = sum(plies.get(seed_of(p), 0) for p in steady)
secs = t_last - t_wave
ms = secs*1000.0/pl if pl else float("nan")
idx = pl/secs if secs > 0 else float("nan")
used, avail = [], []
for line in open(os.path.join(d, ".ram.log")):
    try: u, a = line.split(); used.append(int(u)); avail.append(int(a))
    except ValueError: pass
print(f"{box}\t{w}\t{len(shards)}\t{pl}\t{secs:.0f}\t{ms:.1f}\t{idx:.3f}\t{max(used) if used else -1}\t{min(avail) if avail else -1}\t{time.strftime('%F_%T')}")
PYEOF
  echo "[gensweep $BOX_TAG $(ts)] W=$W -> $(tail -1 "$OUT_TSV")"
  av=$(awk '{print $2}' "$ramlog" | sort -n | head -1)
  if [ -n "$av" ] && [ "$av" -lt 2 ]; then echo "[gensweep $BOX_TAG $(ts)] RAM guard: min avail ${av}G < 2G — STOPPING sweep"; exit 3; fi
done
echo "[gensweep $BOX_TAG $(ts)] SWEEP DONE"
cat "$OUT_TSV"
