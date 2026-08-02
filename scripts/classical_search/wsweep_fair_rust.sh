#!/bin/bash
# FAIR-EVAL W sweep, Rust era (2026-08-02) — the FLAGSHIP elo workload.
#
# Workload = `eval_fair_puct.py --info fair --backend rust` at the deploy champion's
# knobs (k_dets=8 x sims=1376 = 11008, exact-K2 marginalized handoff) against the
# FROZEN Python h800 rung, deck-paired. That asymmetric shape — Rust champion side,
# Python rung side, Python exact-K tail — is exactly what every future elo cell runs,
# so its W* is the number that matters, not the matched-W identity cell (G6,
# measurement/rustport_p6/G6_eval_fair_puct_wiring_PROD.json, which fixed W=10 for
# both legs because it was gating IDENTITY, not throughput).
#
# Metric: throughput_idx = W / champ_prefix_ms_per_move * 1000 — the champion side is
# what the Rust port bought and what the sweep prices. Read from each point's
# summary.json (emitter: eval_fair_puct._summarize, ~line 1769: champ_ms = sum(
# champ_prefix_secs) / sum(champ_prefix_moves) * 1e3), NOT from n/wallclock, which is
# polluted by the tail (last games idling workers) and by the order-statistic trap.
# rung_ms_per_move is recorded alongside because the unconverted Python rung is what
# caps the FARM-realised multiplier.
#
# Design notes:
# - NO champion-env exports here, unlike wsweep_f7d.sh. eval_fair_puct.py installs its
#   own _CANON_ENV with os.environ.setdefault (~line 269) and its header warns in a box
#   that a pre-set CARCASSONNE_V29_MEEPLE_CURVE WINS the setdefault and silently moves
#   DEFAULT_CONFIG (i.e. the rung). The harness's leaf_hash assert is the gate; leave
#   the leaf env alone. Only the net-free/thread-pinning vars are exported.
# - CARCASSONNE_TT_CAP deliberately UNSET, matching the G6 PROD cell this extends.
#   K=2 marginalized solves are the RAM-safe rung; a RAM sampler + <2G abort guards it.
# - --rust-threads deliberately UNSET: the harness's FARM RULE pins it to 1 whenever
#   --workers > 1 (resolve at ~line 2727). Passing it explicitly would only risk the
#   W16 x t8 = 128-hot-threads failure mode.
# - Each point runs INDEPENDENTLY and SEQUENTIALLY: no --shared-claim (a sweep point
#   must own the box), throwaway band 9.69e10 (NOT the G6 band 9.8e10 — that one is a
#   registered gate band), --no-results-csv (this eval never appends anyway; belt and
#   braces).
# - n scales with W (n = max(16, 2W), rounded to a paired even) so the box stays
#   saturated for most of the point's life.
#
# Usage (detach! nohup ... & disown):
#   nohup nice -n 19 bash scripts/classical_search/wsweep_fair_rust.sh local "8 12 16 24 32" \
#       > /tmp/wsweep_fair_local.log 2>&1 & disown
# Optional env: WSWEEP_N (floor games/point, default 16), WSWEEP_BAND (default
# 96900000000), WSWEEP_SIMS / WSWEEP_KDETS / WSWEEP_RUNG (smoke overrides only),
# WSWEEP_FAIR_OUT (out-root).
set -u
BOX_TAG="${1:?usage: wsweep_fair_rust.sh <local|laptop> \"<W list>\"}"
WLIST="${2:?quoted W list required, e.g. \"8 12 16 24 32\"}"

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_fair_puct.py
TAG="${WSWEEP_TAG:-}"
OUT_TSV=$REPO/measurement/classical_search/WSWEEP_FAIR_RUST_${BOX_TAG}${TAG}.tsv
OUT_ROOT="${WSWEEP_FAIR_OUT:-$HOME/carc_out/wsweep_fair_20260802}"

N_FLOOR="${WSWEEP_N:-16}"
BAND="${WSWEEP_BAND:-96900000000}"   # throwaway bench band; throughput only, no strength claim
SIMS="${WSWEEP_SIMS:-1376}"          # PRODUCTION champion budget k8 x 1376 = 11008
KDETS="${WSWEEP_KDETS:-8}"
RUNG="${WSWEEP_RUNG:-800}"           # frozen HeuristicMCTS rung (CL-022)
EXACT_K="${WSWEEP_EXACT_K:-2}"
BACKEND="${WSWEEP_BACKEND:-rust}"

case "$BOX_TAG" in
  local|laptop) ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|laptop)"; exit 1 ;;
esac
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd $REPO || exit 1
ts() { date +%F_%T; }
mkdir -p "$OUT_ROOT"

[ -f "$OUT_TSV" ] || echo -e "box\tW\tn\tsecs_wall\tchamp_ms_per_move\trung_ms_per_move\tthroughput_idx\tsolver_secs_per_game\tpeak_ram_used_g\tmin_avail_g\ttimestamp" > "$OUT_TSV"
echo "[fairsweep $BOX_TAG $(ts)] start: W=[$WLIST] k${KDETS}x${SIMS} K$EXACT_K rung h$RUNG backend=$BACKEND band=$BAND out=$OUT_ROOT"

for W in $WLIST; do
  PN=$N_FLOOR; [ "$PN" -lt $((2*W)) ] && PN=$((2*W)); PN=$(( (PN+1)/2*2 ))
  sub="fair_${BOX_TAG}_${BACKEND}_k${KDETS}x${SIMS}_w${W}"
  dir="$OUT_ROOT/$sub"
  if [ -f "$dir/summary.json" ] && $PY -c "import json,sys;s=json.load(open(sys.argv[1]));sys.exit(0 if s.get('n',0)>=int(sys.argv[2]) else 1)" "$dir/summary.json" "$PN" 2>/dev/null; then
    echo "[fairsweep $BOX_TAG $(ts)] W=$W cached -> skip"
  else
    mkdir -p "$dir"
    ramlog="$dir/.ram.log"; : > "$ramlog"
    ( while true; do free -g | awk '/^Mem:/{print $3, $7}'; sleep 30; done >> "$ramlog" ) &
    RAMPID=$!
    echo "[fairsweep $BOX_TAG $(ts)] W=$W point start (n=$PN)"
    t0=$(date +%s)
    nice -n 19 $PY -u "$HARNESS" \
      --info fair --opponent h800 \
      --k-dets $KDETS --sims $SIMS --exact-k $EXACT_K --rung-sims $RUNG \
      --n $PN --paired --seed-start $BAND \
      --backend "$BACKEND" --workers "$W" \
      --out-root "$OUT_ROOT" --out-subdir "$sub" \
      --no-results-csv > "$dir/run.log" 2>&1
    rc=$?
    secs=$(( $(date +%s) - t0 ))
    kill $RAMPID 2>/dev/null || true
    [ $rc -ne 0 ] && { echo "[fairsweep $BOX_TAG $(ts)] W=$W FAILED rc=$rc — see $dir/run.log"; tail -20 "$dir/run.log"; exit $rc; }
    echo "$secs" > "$dir/.wall_secs"
  fi
  $PY - "$BOX_TAG" "$W" "$dir" >> "$OUT_TSV" <<'PYEOF'
import json, sys, time, os
box, w, d = sys.argv[1:4]
s = json.load(open(os.path.join(d, "summary.json")))
wp = os.path.join(d, ".wall_secs")
wall = open(wp).read().strip() if os.path.exists(wp) else "-"
champ = s.get("champ_prefix_ms_per_move", float("nan"))
rung = s.get("rung_ms_per_move", float("nan"))
idx = float(w) / champ * 1000.0   # champion moves/sec across the box, tail-free
used, avail = [], []
rl = os.path.join(d, ".ram.log")
if os.path.exists(rl):
    for line in open(rl):
        try:
            u, a = line.split(); used.append(int(u)); avail.append(int(a))
        except ValueError:
            pass
print(f"{box}\t{w}\t{s.get('n','-')}\t{wall}\t{champ:.1f}\t{rung:.1f}\t{idx:.3f}\t"
      f"{s.get('solver_secs_per_game', float('nan')):.1f}\t"
      f"{max(used) if used else -1}\t{min(avail) if avail else -1}\t{time.strftime('%F_%T')}")
PYEOF
  echo "[fairsweep $BOX_TAG $(ts)] W=$W -> $(tail -1 "$OUT_TSV")"
  av=$(awk '{print $2}' "$dir/.ram.log" 2>/dev/null | sort -n | head -1)
  if [ -n "$av" ] && [ "$av" -lt 2 ]; then
    echo "[fairsweep $BOX_TAG $(ts)] RAM guard: min avail ${av}G < 2G — STOPPING sweep"; exit 3
  fi
done
echo "[fairsweep $BOX_TAG $(ts)] SWEEP DONE"
cat "$OUT_TSV"
