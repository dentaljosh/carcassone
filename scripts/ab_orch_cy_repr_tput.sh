#!/usr/bin/env bash
# 5800x carc-orch W28 WARM-THROUGHPUT A/B: CARCASSONNE_USE_CY_REPR off vs on.
# At fixed W28 the server's steady examples/s IS the game-rate (examples/game is
# identical for cy off/on -> bit-identical games), so we compare steady examples/s
# + fwd_busy instead of waiting ~13min/game for completed-game counts. Samples the
# throughput curve so warmup-vs-steady is visible.
#   Env: DUR=480 (seconds of self-play per arm)
set -uo pipefail
R=/home/doctor/projects/carcassone; cd "$R"
CKPT="${CKPT:-/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt}"
TS="${TS:-rust/carc-orch/iter8.ts.pt}"
W="${W:-28}"; SIMS="${SIMS:-800}"; DUR="${DUR:-480}"
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1"
SP="--iter 0 --games 9000 --sims $SIMS --leaf-eval v2_5 --value-blend 0 --residual-scale 0.25 --value-target residual --batch-size 8 --checkpoint $CKPT --seed-start 5000000"
RESULT=/tmp/ab_orch_cyrepr_tput.txt; : > "$RESULT"
cleanup(){
  pgrep -f 'release/carc-orch' | xargs -r kill -9 2>/dev/null
  pgrep -f 'run_selfplay_iter|multiprocessing.spawn' | xargs -r kill -9 2>/dev/null
  rm -f /dev/shm/carc_* /dev/shm/sem.carc_* 2>/dev/null
  sleep 3
  for _ in $(seq 1 20); do awk '{exit !($1<3)}' /proc/loadavg && break; sleep 2; done
}

run_arm(){
  local cy=$1
  local SHMN="tput${cy}"
  local OUT="/tmp/ab_tput_cy${cy}_out"
  local SLOG="/tmp/ab_tput_cy${cy}_srv.log"
  local PLOG="/tmp/ab_tput_cy${cy}_play.log"
  rm -rf "$OUT"; mkdir -p "$OUT"; cleanup
  echo "=== ARM cy=$cy : carc-orch W=$W sims=$SIMS dur=${DUR}s ==="
  setsid bash -c "rust/carc-orch/run_server.sh --model $TS --transport shm --shm-name $SHMN --workers $W --n-scalar 12 --forwarders 4 --max-batch 16 --watchdog-secs 0" </dev/null >"$SLOG" 2>&1 &
  for i in $(seq 1 150); do grep -q READY "$SLOG" && break; sleep 1; done
  if ! grep -q READY "$SLOG"; then echo "cy=$cy SERVER-FAIL"; tail -5 "$SLOG"; echo "cy=$cy SERVER-FAIL" >> "$RESULT"; return; fi
  setsid bash -c "env $ENVV CARCASSONNE_USE_CY_REPR=$cy timeout $DUR nice -n 19 .venv/bin/python -u scripts/run_selfplay_iter.py $SP --output-root $OUT --workers $W --shm-eval-server $SHMN" </dev/null >"$PLOG" 2>&1 &
  local APID=$!
  # sample the throughput curve every 20s while the arm runs
  echo "  cy=$cy throughput curve (t: examples/s fwd_busy% loadavg):"
  while kill -0 "$APID" 2>/dev/null; do
    local es; es=$(grep -oE "examples/s=[0-9]+" "$SLOG"|tail -1|cut -d= -f2)
    local fb; fb=$(grep -oE "fwd_busy=[0-9]+%" "$SLOG"|tail -1|cut -d= -f2)
    printf "    %s  es=%s  fwd=%s  load=%s\n" "$(date +%M:%S)" "${es:-0}" "${fb:-?}" "$(cut -d' ' -f1 /proc/loadavg)"
    sleep 20
  done
  # steady tail = median of the last 8 examples/s readings in the server log
  local tail_es; tail_es=$(grep -oE "examples/s=[0-9]+" "$SLOG"|tail -8|cut -d= -f2|sort -n|awk '{a[NR]=$1}END{print a[int(NR/2)+1]}')
  local last_fb; last_fb=$(grep -oE "fwd_busy=[0-9]+%" "$SLOG"|tail -1)
  echo "ARM cy=$cy: steady_examples_s≈$tail_es  ${last_fb}"
  echo "cy=$cy steady_es=$tail_es ${last_fb}" >> "$RESULT"
}

echo "=== 5800x carc-orch W$W WARM-THROUGHPUT cy-repr A/B (sims=$SIMS, ${DUR}s/arm) $(date +%T) ==="
run_arm 0
run_arm 1
cleanup
echo "=== SUMMARY ==="; cat "$RESULT"
python3 - "$RESULT" <<'PY'
import sys, re
d={}
for ln in open(sys.argv[1]):
    m=re.search(r'cy=(\d).*steady_es=(\d+)', ln)
    if m: d[m.group(1)]=int(m.group(2))
if '0' in d and '1' in d and d['0']>0:
    print(f"\ncy-repr ON/OFF throughput = {d['1']/d['0']:.3f}x   (off {d['0']} -> on {d['1']} examples/s)")
    print("(examples/s ∝ game-rate at fixed W since examples/game is identical; fwd_busy ~100% in both => server-bound => null)")
PY
echo "=== A/B DONE $(date +%T) ==="
