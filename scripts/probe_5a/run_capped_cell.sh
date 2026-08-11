#!/usr/bin/env bash
# CAPACITY-PROBE cell launcher WITH A HOST-SAFE MEMORY CAP (2026-07-21).
#
# Why this wrapper exists — the 2026-07-21 WSL teardown:
#   run_capacity_probe.sh (lines 74-75) deliberately keeps the 30GB obs memmap
#   hot in page cache across runs ("the speedup, not a leak"). That reasoning is
#   correct on native Linux, where page cache is reclaimable and free. It is
#   FALSE under WSL2: guest page cache inflates the utility VM's host-side
#   footprint, and .wslconfig grants memory=42GB on a 47.9GB host (~6GB left for
#   Windows). At 13:55:35 Windows logged Event 26 "Virtual Memory Minimum Too
#   Low"; 7s later the VM was torn down. f128b6_s0 died at exactly 437 bytes,
#   right after [leaf-alone TEST] — byte-identical to its 2026-07-04 death, i.e.
#   the crash REPRODUCES and is caused by this cell, not by a random dirty reboot.
#
# Fix: run the training inside a cgroup-v2 user scope with a hard memory ceiling,
# so the guest kernel RECLAIMS page cache at the limit instead of ballooning the
# VM. Costs disk re-reads (slower epochs); buys not killing the box. No
# `wsl --shutdown` and no .wslconfig edit required.
#
# Safety net: a watchdog polls Windows FreePhysicalMemory and aborts the training
# if the host drops below ABORT_GB, so a mis-sized cap degrades to a dead job
# rather than a dead VM.
#
# Usage (detached):
#   setsid nohup bash scripts/probe_5a/run_capped_cell.sh "128:6:0" \
#     > measurement/capacity_probe/capped_128b6_s0.log 2>&1 & disown
set -uo pipefail
cd /home/doctor/projects/carcassone

CELLS_ARG="${1:?usage: run_capped_cell.sh <filters:blocks:seed> [more cells...]}"
MEM_HIGH="${MEM_HIGH:-16G}"    # soft: start reclaiming here
MEM_MAX="${MEM_MAX:-20G}"      # hard: never exceed
ABORT_GB="${ABORT_GB:-4}"      # kill training if Windows free physical drops below this
POLL_SECS="${POLL_SECS:-60}"

echo "[capped] cells=$CELLS_ARG MemoryHigh=$MEM_HIGH MemoryMax=$MEM_MAX abort<${ABORT_GB}GB"
echo "[capped] started $(date +%F_%H:%M:%S)"

# --- watchdog: guard the HOST, not the guest ------------------------------- #
watchdog () {
  local scope_pat="$1"
  while true; do
    sleep "$POLL_SECS"
    # no training left -> nothing to guard
    pgrep -f 'step1_trai[n].py' >/dev/null 2>&1 || { echo "[watchdog] training gone; exiting"; return 0; }
    local freegb
    freegb=$(powershell.exe -NoProfile -Command \
      "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)" 2>/dev/null | tr -d '\r')
    [ -z "$freegb" ] && continue
    echo "[watchdog] $(date +%H:%M:%S) windows_free=${freegb}GB"
    if awk "BEGIN{exit !($freegb < $ABORT_GB)}"; then
      echo "[watchdog] ABORT: Windows free ${freegb}GB < ${ABORT_GB}GB — killing training to save the VM"
      pkill -f 'step1_trai[n].py'
      return 1
    fi
  done
}
watchdog "$CELLS_ARG" &
WD_PID=$!

# --- the training, inside the capped scope --------------------------------- #
CELLS="$CELLS_ARG" systemd-run --user --scope -q \
  -p MemoryHigh="$MEM_HIGH" -p MemoryMax="$MEM_MAX" -p MemorySwapMax=0 \
  bash scripts/probe_5a/run_capacity_probe.sh
RC=$?

kill "$WD_PID" 2>/dev/null
echo "[capped] finished $(date +%F_%H:%M:%S) rc=$RC"
exit $RC
