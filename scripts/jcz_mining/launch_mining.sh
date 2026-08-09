#!/bin/bash
# JCZ DISAGREEMENT MINING — gated launcher.
# Pre-registration: measurement/jcz_mining_20260809/MINING_PREREG.md §8.
#
# ============================ HARD CONSTRAINTS (§8) =========================
# * W = 14 HARD CAP. Not a tuning choice — the box is DRAM-latency-bound
#   (W* ~= 14-16 regardless of the 16C/32T core count) AND it is Joshua's
#   interactive machine. run_mining.py clamps independently; this script states
#   the rationale BEFORE ever calling it. All workers run nice -n 19.
# * REFUSES to start if a higher-priority tenant is running (eval_fair_puct.py,
#   curvephase_ladder_launcher.sh, phase_seam_gate*, night_chain* /
#   pull_and_chain.sh, or another oracle_score_pilot.py) — the phase-arm ladder
#   has first claim on this box tonight (memory:
#   feedback_no_agent_compute_beside_eval — a compute tenant beside a live
#   timing/eval run contaminates or starves it).
# * Detached (setsid nohup ... & disown), optionally under a
#   `systemd-run --user --scope -p MemoryMax=20G` cap — the local box has taken
#   repeated WSL-VM teardowns from unsegmented memory pressure (memory:
#   reference_wsl2_host_memory_teardown).
# * Per-position checkpointed (oracle_score_pilot's own records/<rid>.json) and
#   --resume-able via run_mining.py, so the run can be killed for box priority
#   at any moment and picked back up without losing a scored cell.
# ==============================================================================
#
# Usage:
#   bash scripts/jcz_mining/launch_mining.sh [--dry-run]
#       [--workers N] [--m N] [--oracle-sims N] [--out-root DIR] [--strata PATH]
#
# --strata overrides the default measurement/jcz_mining_20260809/mining/STRATA.json
# (mainly for testing the launcher's gates against a fixture without depending on
# the extractor having already run).
set -euo pipefail

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY=python3
RUNNER="$REPO/scripts/jcz_mining/run_mining.py"
MINING="$REPO/measurement/jcz_mining_20260809/mining"
STRATA="$MINING/STRATA.json"
LOG="$MINING/launch_mining.log"

WORKERS=14
M=32
ORACLE_SIMS=100
OUT_ROOT="/mnt/c/carc-shared/jcz_mining_20260809"
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)     DRY_RUN=1; shift ;;
    --workers)     WORKERS="${2:?--workers needs a value}"; shift 2 ;;
    --m)           M="${2:?--m needs a value}"; shift 2 ;;
    --oracle-sims) ORACLE_SIMS="${2:?--oracle-sims needs a value}"; shift 2 ;;
    --out-root)    OUT_ROOT="${2:?--out-root needs a value}"; shift 2 ;;
    --strata)      STRATA="${2:?--strata needs a value}"; shift 2 ;;
    *) echo "[launch_mining] unknown arg '$1'" >&2; exit 1 ;;
  esac
done

# --------------------------- 1. PROCESS GATE --------------------------------
# The phase-arm ladder (and any other measurement harness already touching the
# box) has first claim. `pgrep -f X || true` — a no-match exit-1 is expected,
# never treated as an error (standing rule: wrap pkill/pgrep exit codes).
BLOCKED_PATTERNS=(
  "eval_fair_puct.py"
  "curvephase_ladder_launcher.sh"
  "phase_seam_gate"
  "night_chain"
  "pull_and_chain.sh"
  "oracle_score_pilot.py"
)
CONFLICT=0
for pat in "${BLOCKED_PATTERNS[@]}"; do
  pids="$(pgrep -f "$pat" || true)"
  if [ -n "$pids" ]; then
    echo "[launch_mining] REFUSING: pattern '$pat' matched running pid(s): $pids" >&2
    CONFLICT=1
  fi
done
if [ "$CONFLICT" -ne 0 ]; then
  echo "[launch_mining] a higher-priority tenant is running — not launching." >&2
  exit 1
fi
echo "[launch_mining] process gate clear — no blocked pattern is running"

# --------------------------- 2. WORKER RATIONALE -----------------------------
echo "[launch_mining] W=$WORKERS: the box is a 5900XT 16C/32T, but self-play/eval"
echo "[launch_mining]   is DRAM-latency-bound so W* is ~14-16 regardless of core"
echo "[launch_mining]   count, AND this is Joshua's interactive machine -- 14 is a"
echo "[launch_mining]   HARD CAP, not a tuning knob (run_mining.py clamps"
echo "[launch_mining]   independently). All workers run nice -n 19."

# --------------------------- 3. ETA ------------------------------------------
echo "[launch_mining] ETA: ~4-6h at W=14 for BOTH judges; the primary judge"
echo "[launch_mining]   (clair-puct, the deciding statistic) completes at ~3-4h."
echo "[launch_mining]   The run is per-position checkpointed"
echo "[launch_mining]   (oracle_score_pilot records/<rid>.json) and --resume-able,"
echo "[launch_mining]   so it can be killed for box priority at any time."

# --------------------------- 4. STRATA GATE ----------------------------------
if [ ! -f "$STRATA" ]; then
  echo "[launch_mining] REFUSING: $STRATA does not exist -- the extractor" >&2
  echo "[launch_mining]   (mine_disagreements.py) has not produced strata yet." >&2
  exit 1
fi
GATE_OK="$("$PY" -c "import json,sys; print(bool(json.load(open(sys.argv[1])).get('gate_ok')))" "$STRATA")"
if [ "$GATE_OK" != "True" ]; then
  echo "[launch_mining] REFUSING: $STRATA has gate_ok != true -- the pre-" >&2
  echo "[launch_mining]   registered n>=min_n_gate sampling gate did not pass." >&2
  exit 1
fi
echo "[launch_mining] STRATA.json gate_ok=True -- sampling gate passed"

# --------------------------- 5. BUILD THE COMMAND ----------------------------
CMD=("$PY" "$RUNNER"
     --strata "$STRATA" --out-root "$OUT_ROOT"
     --m "$M" --oracle-sims "$ORACLE_SIMS" --workers "$WORKERS")

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[launch_mining] --dry-run: every gate passed. Would run:"
  printf '  '
  printf '%q ' "${CMD[@]}"
  printf '\n'
  exit 0
fi

# --------------------------- 6. DETACHED LAUNCH ------------------------------
mkdir -p "$MINING"
MEM_WRAP=()
if command -v systemd-run >/dev/null 2>&1 \
   && systemd-run --user --scope -p MemoryMax=20G true >/dev/null 2>&1; then
  MEM_WRAP=(systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0)
  echo "[launch_mining] memory scope ACTIVE (MemoryMax=20G) -- the local box has"
  echo "[launch_mining]   taken repeated WSL-VM teardowns from unsegmented memory"
  echo "[launch_mining]   pressure; this run is capped."
else
  echo "[launch_mining] WARNING: systemd-run --user --scope unavailable --" >&2
  echo "[launch_mining]   running WITHOUT a memory cap." >&2
fi

echo "[launch_mining] launching detached -> $LOG"
setsid nohup "${MEM_WRAP[@]}" "${CMD[@]}" > "$LOG" 2>&1 < /dev/null &
disown
echo "[launch_mining] launched pid=$!"
echo "[launch_mining] log: $LOG"
echo "[launch_mining] check on it:  tail -f $LOG   (or: pgrep -fa run_mining.py)"
