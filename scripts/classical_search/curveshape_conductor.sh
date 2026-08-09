#!/bin/bash
# PART-A CONDUCTOR — enforce A-gate 0 in code, then drive the remaining cells two-box.
#
# The prereg says C0_identity is checked FIRST and a failure ABORTS with no cell counting.
# Running the other three cells before that read would risk burning the band; waiting for a
# human to read it would idle both boxes for ~an hour. This script does the honest thing:
# it BLOCKS on C0's summary, applies the gate mechanically via analyze_curveshape.py, and
# launches C1/C2/C3 only if the gate passes. If the gate fails it writes an ABORT marker and
# stops, leaving the band burnt but the record clean.
#
# Resume: every leg is --shared-claim, so re-running this conductor after a crash resumes
# from banked games rather than restarting. Cells already at n>=400 are skipped by the
# launcher itself.
#
# Usage: nohup nice -n 19 bash scripts/classical_search/curveshape_conductor.sh > log 2>&1 &
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
SHARE=/mnt/c/carc-shared/curveshape_probe
DIR=$REPO/measurement/curve_shape_scope_20260809
LOGS=$DIR/logs
LAPTOP_SH=$LOGS/_laptop_leg.sh
N=400
ts() { date +%F_%T; }
mkdir -p "$LOGS"

echo "[cond $(ts)] waiting for the C0_identity gate cell to complete..."
while [ ! -f "$SHARE/cs_C0_identity/summary.json" ]; do sleep 30; done
echo "[cond $(ts)] C0 summary present; applying A-gate 0"

$PY $REPO/scripts/classical_search/analyze_curveshape.py --n-expected $N \
    --out "$DIR/READOUT_gate.json" > "$LOGS/gate.json" 2>&1
V=$($PY -c "import json;print(json.load(open('$DIR/READOUT_gate.json'))['verdict'])" 2>/dev/null)
echo "[cond $(ts)] gate verdict: $V"
case "$V" in
  INSTRUMENT-BROKEN|VOID_INCOMPLETE)
    echo "[cond $(ts)] ABORT — gate failed. No further cell is launched; no cell counts."
    $PY -c "import json;d=json.load(open('$DIR/READOUT_gate.json'));print(d['why'])"
    : > "$DIR/ABORTED_GATE_FAILED"
    exit 2 ;;
  PENDING)
    # PENDING here means C0 completed but the analyzer still wants the other cells; that is
    # the EXPECTED state at this point (gate itself passed — it would have said
    # INSTRUMENT-BROKEN otherwise). Continue.
    echo "[cond $(ts)] gate passed (PENDING = awaiting the off-production cells). Continuing." ;;
  *)
    echo "[cond $(ts)] gate passed with verdict $V; continuing." ;;
esac

for c in C1_flattop C2_broadlow C3_hoard; do
  if [ -f "$SHARE/cs_$c/summary.json" ]; then
    done_n=$($PY -c "import json;print(json.load(open('$SHARE/cs_$c/summary.json')).get('n',0))" 2>/dev/null || echo 0)
    if [ "${done_n:-0}" -ge "$N" ]; then
      echo "[cond $(ts)] $c already complete — skipping"; continue
    fi
  fi
  echo "[cond $(ts)] === launching cell $c on BOTH boxes ==="
  # laptop leg: synchronous inside a locally-nohup'd ssh. The detached-on-remote form dies
  # when the ssh session ends (WSL tears the VM down when nothing holds it), so the live
  # session must own the process. A dropped laptop is safe: --shared-claim just means it
  # stops stealing games and the local leg finishes the cell.
  cat > "$LAPTOP_SH" <<EOF
cd /home/doctor/projects/carcassone || exit 1
nice -n 19 bash scripts/classical_search/curveshape_probe_launcher.sh 22 laptop --cells "$c"
EOF
  nohup ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=1000 laptop 'bash -s' \
      < "$LAPTOP_SH" > "$LOGS/cs_laptop_$c.log" 2>&1 &
  LAP=$!
  nice -n 19 bash $REPO/scripts/classical_search/curveshape_probe_launcher.sh 30 local \
      --cells "$c" > "$LOGS/cs_local_$c.log" 2>&1
  echo "[cond $(ts)] local leg for $c returned rc=$?"
  wait $LAP 2>/dev/null
  echo "[cond $(ts)] laptop leg for $c returned"
done

echo "[cond $(ts)] all cells attempted; final readout:"
$PY $REPO/scripts/classical_search/analyze_curveshape.py --n-expected $N \
    --out "$DIR/READOUT_partA.json" | tail -40
echo "[cond $(ts)] conductor finished"
