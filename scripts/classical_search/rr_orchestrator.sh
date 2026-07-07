#!/bin/bash
# Phase 1.1b round-robin orchestrator (pre-reg 2d2ab10; launcher d7510f6; harness 8b008ab).
# Sequential chain, two-box work-stealing per cell:
#   orch servers up (both boxes) -> PRE-FLIGHT n=4 RR-1 smoke (throwaway band) ->
#   RR-1 -> RR-2 -> servers down -> RR-3 -> RR-4 -> gate math (G1/G2).
# Detach with setsid. Each cell resumable via shared-claim.
set -u
REPO=/home/doctor/projects/carcassone
SC=$REPO/scripts/classical_search
MDIR=$REPO/measurement/classical_search
LOG=$MDIR/rr_orch.log
PY=$REPO/.venv/bin/python
SHARE=/mnt/c/carc-shared
SHM=rrIter02
exec >> "$LOG" 2>&1
ts() { date +%F_%T; }
echo "[rr-orch $(ts)] start (pid $$) HEAD=$(git -C $REPO rev-parse --short HEAD)"

run_cell() {  # $1=cell  $2=orch(0|1)
  local cell="$1" orch="$2"
  echo "[rr-orch $(ts)] CELL $cell launch (orch=$orch)"
  ssh laptop-wsl 'bash -s' <<HELP &
while pgrep -f 'run_round_robin.sh helper' >/dev/null; do sleep 30; done
cd /home/doctor/projects/carcassone || exit 1
$( [ "$orch" = 1 ] && echo "export CARC_ORCH_SHM=$SHM" )
setsid nice -n 19 bash scripts/classical_search/run_round_robin.sh helper $cell </dev/null >/tmp/rr_helper_$cell.log 2>&1 &
sleep 2; ps -eo pid,args | grep '[r]un_round_robin.sh helper' | head -2
exit 0
HELP
  # local primary foreground (blocks until cell aggregated)
  if [ "$orch" = 1 ]; then CARC_ORCH_SHM=$SHM nice -n 19 bash "$SC/run_round_robin.sh" primary "$cell" >/tmp/rr_primary_$cell.log 2>&1
  else nice -n 19 bash "$SC/run_round_robin.sh" primary "$cell" >/tmp/rr_primary_$cell.log 2>&1; fi
  echo "[rr-orch $(ts)] CELL $cell primary exited -> $(tail -1 "$MDIR/ROUND_ROBIN_PROGRESS.tsv" 2>/dev/null)"
}

# ---- Phase A: orch servers on both boxes ----
echo "[rr-orch $(ts)] exporting torchscript + starting orch servers"
$PY $REPO/scripts/export_torchscript.py --checkpoint $SHARE/rod_v2_flywheel/ckpt/iter_02.pt --out /tmp/carc_rr_iter02.ts.pt --device cuda \
  && echo "[rr-orch $(ts)] local TS export OK" || { echo "[rr-orch $(ts)] FATAL local TS export failed"; exit 1; }
setsid nice -n 19 bash $REPO/rust/carc-orch/run_server.sh --model /tmp/carc_rr_iter02.ts.pt --transport shm \
  --shm-name $SHM --workers 48 --n-scalar 12 --device cuda --max-batch 16 --batch-timeout-ms 2.0 \
  --forwarders 4 --watchdog-secs 30 </dev/null >/tmp/rr_orch_server_local.log 2>&1 &
sleep 8
grep -qiE 'listening|ready|serving' /tmp/rr_orch_server_local.log && echo "[rr-orch $(ts)] local orch server UP" \
  || echo "[rr-orch $(ts)] WARN local orch server status unclear (log tail: $(tail -1 /tmp/rr_orch_server_local.log))"
ssh laptop-wsl 'bash -s' <<'LSRV'
cd /home/doctor/projects/carcassone || exit 1
.venv/bin/python scripts/export_torchscript.py --checkpoint /mnt/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt --out /tmp/carc_rr_iter02.ts.pt --device cuda \
  && echo "laptop TS export OK" || { echo "laptop TS export FAILED"; exit 1; }
setsid nice -n 19 bash rust/carc-orch/run_server.sh --model /tmp/carc_rr_iter02.ts.pt --transport shm \
  --shm-name rrIter02 --workers 26 --n-scalar 12 --device cuda --max-batch 16 --batch-timeout-ms 2.0 \
  --forwarders 4 --watchdog-secs 30 </dev/null >/tmp/rr_orch_server.log 2>&1 &
sleep 8; grep -qiE 'listening|ready|serving' /tmp/rr_orch_server.log && echo "laptop orch server UP" || echo "laptop orch WARN: $(tail -1 /tmp/rr_orch_server.log)"
exit 0
LSRV
echo "[rr-orch $(ts)] laptop server phase done"

# ---- Phase B: pre-flight smoke (production knobs, n=4, throwaway band, local only) ----
echo "[rr-orch $(ts)] PRE-FLIGHT: n=4 RR-1 smoke (orch, throwaway band 9.99e9)"
CARC_ORCH_SHM=$SHM nice -n 19 $PY $SC/eval_puct_priors.py --candidate puct --opponent net:$SHARE/rod_v2_flywheel/ckpt/iter_02.pt \
  --shm-eval-server $SHM --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits \
  --cand-sims 2750 --champ-sims 6400 --exact-k 2 --n 4 --paired --workers 4 \
  --no-results-csv --seed-start 9990000000 --out-root "$SHARE/puct_rr_smoke" --out-subdir preflight >/tmp/rr_preflight.log 2>&1
if $PY -c "import json;s=json.load(open('$SHARE/puct_rr_smoke/preflight/summary.json'));assert s['n']==4;print('preflight OK n=4')"; then
  echo "[rr-orch $(ts)] PRE-FLIGHT OK -> full cells"
else
  echo "[rr-orch $(ts)] PRE-FLIGHT FAILED -> stop before burning real bands. tail: $(tail -3 /tmp/rr_preflight.log)"; exit 1
fi

# ---- Phase C: the orch cells (RPS-decisive) ----
run_cell rr1 1
run_cell rr2 1

# ---- Phase D: servers down, CPU cells ----
echo "[rr-orch $(ts)] stopping orch servers"
pkill -f "run_server.sh.*$SHM" || true; pkill -f "carc-orch.*$SHM" || true
ssh laptop-wsl 'pkill -f "run_server.sh.*rrIter02" || true; pkill -f "carc-orch.*rrIter02" || true; echo laptop servers stopped' || true
run_cell rr3 0
run_cell rr4 0

# ---- Phase E: gate math ----
echo "[rr-orch $(ts)] ALL CELLS DONE:"; cat "$MDIR/ROUND_ROBIN_PROGRESS.tsv"
$PY - "$SHARE/puct_roundrobin" <<'PYEOF'
import json, sys, math, os
root = sys.argv[1]
def load(c):
    p = os.path.join(root, f"rr_{c}_k2", "summary.json")
    s = json.load(open(p)); return s["elo"], s["elo_sig_1sigma"]
try:
    (m1,s1),(m2,s2),(m3,s3),(m4,s4) = load("rr1"), load("rr2"), load("rr3"), load("rr4")
except Exception as e:
    print(f"GATE MATH SKIPPED (missing cell): {e}"); raise SystemExit
sd12 = math.hypot(s1,s2); sd34 = math.hypot(s3,s4)
print(f"M1(puct vs net)={m1:+.1f} M2(h6400 vs net)={m2:+.1f}  diff={m1-m2:+.1f} (2sd={2*sd12:.1f})")
print(f"M3(puct vs h12800)={m3:+.1f} M4(h6400 vs h12800)={m4:+.1f}  transitivity predicts M1-M2~+148, M3~148+M4")
g1 = "PASS" if (m1 - m2) >= -2*sd12 else "RPS FLAG"
g2 = "PASS" if m3 >= 2*s3 else ("inconclusive-positive" if m3 > 0 else "FLAG")
print(f"G1 (RPS gate): {g1}   G2 (compute-odds): {g2}")
PYEOF
echo "[rr-orch $(ts)] rr-orchestrator exit"
