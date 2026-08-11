#!/usr/bin/env bash
# OVERNIGHT CHAIN 2026-07-22 — finish the B3 capacity ladder unattended.
#
# Joshua pre-authorised the f256b8 cells (the local box is idle overnight either
# way, and the pre-registered gate defines the slope as the MEAN OF TWO STEP
# DELTAS — so without f256b8 the statistic cannot be computed as written).
#
# Sequence:
#   1. wait for the running 4-checkpoint solver-scoring pass to finish
#   2. gate on host memory, then train f256b8 s0 then s1 (SOLO, sequential)
#   3. re-score over ALL SIX checkpoints -> a separate output file
#
# ⚠️ f256b8 has never completed an epoch in this project's history. It needs
# ~13.5GB of 16GB VRAM and its HOST-memory cap sizing is unvalidated, so it runs
# at MEM_MAX=16G (not the 20G that f128b6 validated). run_capped_cell.sh supplies
# the cgroup ceiling + the Windows-free-RAM watchdog: a mis-sized cap kills the
# JOB, not the VM. See reference_wsl2_host_memory_teardown / commit 1c75a3e.
set -uo pipefail
cd /home/doctor/projects/carcassone

OUT=measurement/capacity_probe
LOG=$OUT/overnight_chain.log
exec >> "$LOG" 2>&1
echo "=== overnight chain started $(date +%F_%H:%M:%S) ==="

# --- 1. wait for the in-flight scoring pass ------------------------------- #
# (no self-match risk: this script's argv is "bash .../overnight_f256_chain.sh")
while pgrep -f 'solver_scor[e].py' >/dev/null 2>&1; do
  sleep 60
done
echo "[chain] 4-ckpt scoring finished $(date +%H:%M:%S); json=$(ls -la $OUT/solver_score_capacity.json 2>/dev/null | awk '{print $5}' || echo MISSING)"

# --- 2. host-memory gate, then the two f256b8 cells ----------------------- #
FREE=$(powershell.exe -NoProfile -Command \
  "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)" 2>/dev/null | tr -d '\r')
echo "[chain] windows_free=${FREE}GB before f256b8"
if [ -n "$FREE" ] && awk "BEGIN{exit !($FREE < 6)}"; then
  echo "[chain] ABORT: host below 6GB free — not starting f256b8"
  exit 1
fi

echo "[chain] launching f256b8 s0+s1 at MEM_MAX=16G $(date +%H:%M:%S)"
MEM_MAX=16G MEM_HIGH=12G bash scripts/probe_5a/run_capped_cell.sh "256:8:0 256:8:1"
echo "[chain] f256b8 phase done rc=$? $(date +%H:%M:%S)"

# --- 3. full 6-checkpoint re-score (separate file; never clobber the 4-ckpt) - #
N=$(ls $OUT/f*b*_s*/V4_listwise/ranknet_best.pt 2>/dev/null | wc -l)
echo "[chain] checkpoints present: $N"
if [ "$N" -ge 5 ]; then
  echo "[chain] re-scoring all $N checkpoints $(date +%H:%M:%S)"
  systemd-run --user --scope -q -p MemoryHigh=12G -p MemoryMax=16G -p MemorySwapMax=0 \
    nice -n 19 .venv/bin/python scripts/canonical_az/solver_score.py --max-k 2 \
      $(for d in $OUT/f*b*_s*/V4_listwise/ranknet_best.pt; do echo --arm-ckpt $d; done) \
      --workers 12 --out $OUT/solver_score_capacity_full6.json
  echo "[chain] full re-score rc=$? $(date +%H:%M:%S)"
else
  echo "[chain] SKIP re-score — only $N checkpoints, f256b8 did not produce both"
fi
echo "=== overnight chain finished $(date +%F_%H:%M:%S) ==="
