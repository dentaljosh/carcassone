#!/usr/bin/env bash
# One-shot chain helper for the 2026-07-21 B3 capacity-probe resume.
#
# Waits (non-blocking to the session) for the CURRENTLY RUNNING capped cell
# (f128b6 s0) to exit, verifies it actually produced a checkpoint AND that the
# host still has headroom, and only THEN launches the NEXT cell — also capped.
# If the running cell died, or Windows free physical is low, this STOPS and
# does not launch anything (the "don't naively retry" rule from
# run_capped_cell.sh).
#
# Strictly sequential/solo is preserved: nothing is launched while a training
# is alive.
#
# ⚠️ SCOPE (2026-07-21, deliberate): this chain launches ONLY 128:6:1 and then
# STOPS. The f256b8 cells are NOT launched and must not be added here without
# Joshua's decision. Reason — two specs conflict on B3's scope:
#   * measurement/capacity_probe/CAPACITY_PROBE.md (2026-07-04) pre-registers a
#     3-size ladder (64/128/256) whose gate needs "the mean of the two step
#     deltas", i.e. it REQUIRES f256b8.
#   * docs/PROGRAM_ROADMAP_2026-07-07.md line 45 is DATED LATER (after the
#     07-04 crash) and re-scopes B3 to "f64b4-vs-f128b6 solver-tau slope on the
#     memory-safe ~2GB subset, laptop only" — dropping f256b8 and the full
#     dataset.
# 128:6:1 is what BOTH specs need, so it runs. f256b8 (~10-25h under the cap)
# is deferred pending the scope call.
set -uo pipefail
cd /home/doctor/projects/carcassone

LOG=measurement/capacity_probe/chain_rest.log
CKPT0=measurement/capacity_probe/f128b6_s0/V4_listwise/ranknet_best.pt

echo "[chain] $(date +%F_%H:%M:%S) waiting for the running cell to exit" >> "$LOG"

# --- wait for the in-flight training (no foreground sleep in the session) --- #
while pgrep -f 'step1_trai[n].py' >/dev/null 2>&1; do
  sleep 60
done
echo "[chain] $(date +%F_%H:%M:%S) no training alive" >> "$LOG"

# --- gate 1: did the running cell actually finish? -------------------------- #
if [ ! -f "$CKPT0" ]; then
  echo "[chain] STOP: f128b6_s0 produced no ranknet_best.pt — cell FAILED." >> "$LOG"
  echo "[chain] NOT launching the rest. Inspect measurement/capacity_probe/f128b6_s0.log" >> "$LOG"
  exit 2
fi
echo "[chain] OK f128b6_s0 -> $CKPT0" >> "$LOG"

# --- gate 2: is the host healthy? ------------------------------------------ #
FREE=$(powershell.exe -NoProfile -Command \
  "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)" 2>/dev/null | tr -d '\r')
echo "[chain] windows_free=${FREE}GB" >> "$LOG"
if [ -n "$FREE" ] && awk "BEGIN{exit !($FREE < 6)}"; then
  echo "[chain] STOP: Windows free ${FREE}GB < 6GB — host has not recovered. Not launching." >> "$LOG"
  exit 3
fi

# --- launch ONLY 128:6:1, capped ------------------------------------------- #
# Do NOT extend this list to 256:8:* — see the SCOPE note in the header.
echo "[chain] $(date +%F_%H:%M:%S) launching 128:6:1 ONLY (capped); f256b8 deferred pending scope call" >> "$LOG"
exec setsid nohup bash scripts/probe_5a/run_capped_cell.sh "128:6:1" \
  > measurement/capacity_probe/capped_rest.log 2>&1
