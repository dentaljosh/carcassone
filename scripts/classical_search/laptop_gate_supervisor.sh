#!/bin/bash
# LOCAL-side supervisor for the chunked phase-seam gate running on the LAPTOP.
#
# WHY IT HAS TO LIVE ON THIS BOX. The laptop's failure mode is a whole-VM teardown
# (WSL 0x80370107 / host memory pressure). Anything armed INSIDE that VM -- the old
# gate_watchdog.sh, wd2.sh -- dies with it and nothing ever restarts the run. Only an
# off-box supervisor can re-boot the VM and re-launch. The chunked gate is resumable
# by artifact, so a blind "just run it again" is exactly the right recovery action.
#
# Loop, every SUPERVISE_EVERY seconds:
#   1. share has .DONE          -> done, exit (pull_and_chain.sh takes it from here)
#   2. laptop VM down           -> boot it via the Windows hop
#   3. gate not running there   -> relaunch it detached (it resumes from its chunks)
#   4. log a heartbeat with the chunk-artifact count so progress is visible from here
#
# Deliberately does NOT touch night_chain: /home/doctor/gate_ops/pull_and_chain.sh
# already owns the pull + chain step and waits on the same .DONE marker.
set -u
SHARE=/mnt/c/carc-shared/_sync/phase_seam_gate/RESULT   # allow-path (LOCAL box share path)
LOG=/home/doctor/gate_ops/supervisor.log
EVERY=${SUPERVISE_EVERY:-300}
ts() { date +%F_%T; }
echo "$(ts) supervisor start (pid $$)" >> "$LOG"

while true; do
  if [ -f "$SHARE/.DONE" ]; then
    echo "$(ts) share .DONE=$(cat "$SHARE/.DONE" 2>/dev/null) -- supervisor exiting" >> "$LOG"
    exit 0
  fi

  # Is the VM alive? ssh laptop-wsl is the discriminator; the Windows hop is the fixer.
  if ! ssh -o ConnectTimeout=20 -o BatchMode=yes laptop-wsl true 2>/dev/null; then
    echo "$(ts) laptop-wsl unreachable -- booting the VM via the Windows hop" >> "$LOG"
    ssh -o ConnectTimeout=30 laptop 'wsl --shutdown' >> "$LOG" 2>&1
    sleep 10   # allow-sleep (detached daemon)
    ssh -o ConnectTimeout=60 laptop 'wsl -d Ubuntu -u root -- uptime' >> "$LOG" 2>&1
    sleep 20   # allow-sleep (detached daemon)
  fi

  STATE=$(ssh -o ConnectTimeout=30 -o BatchMode=yes laptop-wsl 'bash -s' <<'EOF' 2>/dev/null
OUT=/home/doctor/projects/carcassone/measurement/curve_shape_scope_20260809/PHASE_SEAM_GATE
N=$(ls "$OUT"/chunks/*/*.json 2>/dev/null | wc -l)
E=$(bash /home/doctor/gate_ops/phase_seam_gate_chunked.sh --plan 2>/dev/null | wc -l); E=$((E * 2))
if [ -f "$OUT/VERDICT" ]; then V=$(cat "$OUT/VERDICT"); else V=none; fi
if pgrep -f phase_seam_gate_chunked.sh > /dev/null 2>&1; then R=running; else R=stopped; fi
echo "$R $N $V $E"
EOF
)
  if [ -z "$STATE" ]; then
    echo "$(ts) could not read laptop state; retrying next tick" >> "$LOG"
    sleep "$EVERY"; continue   # allow-sleep (detached daemon)
  fi
  set -- $STATE
  RUN=$1; NART=$2; VERD=$3; NEXP=${4:-?}
  echo "$(ts) laptop: gate=$RUN artifacts=$NART/$NEXP verdict=$VERD" >> "$LOG"

  if [ "$RUN" != running ]; then
    echo "$(ts) relaunching the gate on the laptop (resumes from $NART artifacts)" >> "$LOG"
    ssh -o ConnectTimeout=30 laptop-wsl 'bash -s' <<'EOF' >> "$LOG" 2>&1
cd /home/doctor/gate_ops
setsid nohup nice -n 19 bash /home/doctor/gate_ops/run_gate_laptop.sh </dev/null \
    >> /home/doctor/gate_ops/driver_stdout.log 2>&1 &
disown
sleep 3
echo "driver_pid=$(pgrep -f run_gate_laptop.sh | head -1) gate_pid=$(pgrep -f phase_seam_gate_chunked.sh | head -1)"
EOF
  fi
  sleep "$EVERY"   # allow-sleep (detached daemon)
done
