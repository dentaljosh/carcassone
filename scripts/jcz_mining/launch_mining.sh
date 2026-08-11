#!/bin/bash
# JCZ DISAGREEMENT MINING — gated launcher, PER-BOX.
# Pre-registration: measurement/jcz_mining_20260809/MINING_PREREG.md §8.
#
# ============================ HARD CONSTRAINTS (§8) =========================
# * WORKER CAP IS PER-BOX, resolved via --box {local,laptop,auto} (default
#   auto, from `hostname`): local="Doctor" -> W=14 (DRAM-latency-bound AND
#   Joshua's interactive machine); laptop="laptop-wsl" -> W=22 (see the
#   PROVENANCE CAVEAT below — this is NOT a clean measured number for this
#   workload). An unrecognised hostname fails SAFE to local's W=14, never to
#   laptop's looser cap. run_mining.py clamps independently; this script
#   states the rationale BEFORE ever calling it. All workers run nice -n 19.
#
# * ⚠️ LAPTOP W=22 PROVENANCE CAVEAT. The figure comes from
#   measurement/classical_search/WSWEEP_F7D_laptop.tsv, a RUST-backend sweep.
#   oracle_score_pilot.py defaults to --backend python, and tier1-greedy is
#   PYTHON-ONLY by construction — so W=22 is an EXTRAPOLATION ACROSS WORKLOAD
#   CLASSES, unverified for this run. The laptop is also memory-constrained
#   (~12.2 GB total) and its WSL VM has already been force-exited once today
#   under memory pressure (memory: reference_wsl2_host_memory_teardown).
#   CALIBRATE after the first ~10 records: check aggregate worker RSS against
#   the ~12.2 GB ceiling and observed worker-min/position against the 28.7
#   min/position clair-puct baseline (farm-war RUN_MANIFEST.json). If RSS x W
#   exceeds ~60% of the box, kill and relaunch at W=16 -- the run is
#   per-position checkpointed, --resume loses nothing.
#
# * REFUSES to start if a higher-priority tenant is running -- the blocked
#   pattern list is ALSO PER-BOX (see BLOCKED_PATTERNS below): the local box
#   defers to the phase-arm ladder; the laptop defers to the chunked seam gate
#   currently running there (memory: feedback_no_agent_compute_beside_eval —
#   a compute tenant beside a live timing/eval run contaminates or starves it).
#
# * Detached (setsid nohup ... & disown), under a `systemd-run --user --scope
#   -p MemoryMax=...` cap sized PER BOX (20G local, 8G laptop -- the laptop's
#   VM ceiling is much lower, see the W=22 caveat: an overrun must kill the
#   RUN, not the VM). Memory: reference_wsl2_host_memory_teardown.
#
# * Per-position checkpointed (oracle_score_pilot's own records/<rid>.json) and
#   --resume-able via run_mining.py, so the run can be killed for box priority
#   (or for the W=22 calibration check above) at any moment and picked back up
#   without losing a scored cell.
# ==============================================================================
#
# Usage:
#   bash scripts/jcz_mining/launch_mining.sh [--dry-run] [--box local|laptop|auto]
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

BOX=auto
WORKERS=
M=32
ORACLE_SIMS=100
OUT_ROOT=
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)     DRY_RUN=1; shift ;;
    --box)         BOX="${2:?--box needs a value}"; shift 2 ;;
    --workers)     WORKERS="${2:?--workers needs a value}"; shift 2 ;;
    --m)           M="${2:?--m needs a value}"; shift 2 ;;
    --oracle-sims) ORACLE_SIMS="${2:?--oracle-sims needs a value}"; shift 2 ;;
    --out-root)    OUT_ROOT="${2:?--out-root needs a value}"; shift 2 ;;
    --strata)      STRATA="${2:?--strata needs a value}"; shift 2 ;;
    *) echo "[launch_mining] unknown arg '$1'" >&2; exit 1 ;;
  esac
done

# --------------------------- 0. RESOLVE BOX ----------------------------------
# Mirrors run_mining.py's resolve_box(): local="Doctor", laptop="laptop-wsl",
# unrecognised -> fail SAFE to local (the tighter cap), never to laptop.
case "$BOX" in
  local|laptop) ;;
  auto)
    HN="$(hostname)"
    case "$HN" in
      Doctor)      BOX=local ;;
      laptop-wsl)  BOX=laptop ;;
      *)
        echo "[launch_mining] WARNING: unrecognised hostname '$HN' for --box auto" >&2
        echo "[launch_mining]   -- failing SAFE to 'local' (W=14), NOT 'laptop' (W=22)." >&2
        BOX=local
        ;;
    esac
    ;;
  *) echo "[launch_mining] unknown --box '$BOX' (expected local/laptop/auto)" >&2; exit 1 ;;
esac

if [ "$BOX" = laptop ]; then
  BOX_CAP=22
  MEM_MAX=8G
  OUT_ROOT_DEFAULT="/mnt/carc-shared/jcz_mining_20260809"
  BLOCKED_PATTERNS=(
    "phase_seam_gate_chunked.sh"
    "run_gate_laptop.sh"
    "pytest"
    "oracle_score_pilot.py"
  )
else
  BOX_CAP=14
  MEM_MAX=20G
  OUT_ROOT_DEFAULT="/mnt/c/carc-shared/jcz_mining_20260809"
  BLOCKED_PATTERNS=(
    "eval_fair_puct.py"
    "curvephase_ladder_launcher.sh"
    "phase_seam_gate"
    "night_chain"
    "pull_and_chain.sh"
    "oracle_score_pilot.py"
  )
fi
[ -n "$WORKERS" ] || WORKERS="$BOX_CAP"
[ -n "$OUT_ROOT" ] || OUT_ROOT="$OUT_ROOT_DEFAULT"

echo "[launch_mining] resolved box=$BOX (cap W=$BOX_CAP, out_root_default=$OUT_ROOT_DEFAULT)"

# Rationale, caveat and ETA are printed BEFORE the process gate (deliberately —
# they must stay visible even on a refusal, so an operator who gets refused
# still sees the W=22 provenance caveat and the calibration guidance).

# --------------------------- 1. WORKER RATIONALE -----------------------------
if [ "$BOX" = laptop ]; then
  echo "[launch_mining] W=$WORKERS on laptop (24 nproc, ~12.2GB RAM): W=22 comes from"
  echo "[launch_mining]   WSWEEP_F7D_laptop.tsv, a RUST-backend sweep -- oracle_score_pilot"
  echo "[launch_mining]   defaults to --backend python and tier1-greedy is PYTHON-ONLY, so"
  echo "[launch_mining]   this is an EXTRAPOLATION ACROSS WORKLOAD CLASSES, UNVERIFIED for"
  echo "[launch_mining]   this run. CALIBRATE after the first ~10 records: check aggregate"
  echo "[launch_mining]   worker RSS against the ~12.2GB ceiling and worker-min/position"
  echo "[launch_mining]   against the 28.7 clair-puct baseline. If RSS x W exceeds ~60% of"
  echo "[launch_mining]   the box, kill and relaunch at W=16 -- --resume loses nothing."
else
  echo "[launch_mining] W=$WORKERS on local: the box is a 5900XT 16C/32T, but self-play/eval"
  echo "[launch_mining]   is DRAM-latency-bound so W* is ~14-16 regardless of core count, AND"
  echo "[launch_mining]   this is Joshua's interactive machine -- 14 is a HARD CAP, not a"
  echo "[launch_mining]   tuning knob (run_mining.py clamps independently)."
fi
echo "[launch_mining] All workers run nice -n 19."

# --------------------------- 2. ETA ------------------------------------------
# Design constants: 160 primary positions (A=40+B=40+C=80), 80 secondary
# (A+B). Rates from farm-war's RUN_MANIFEST.json (concurrent-legs-corrected):
# clair-puct 28.7 worker-min/position, tier1-greedy 3.0.
ETA="$("$PY" -c "
w = int('$WORKERS')
primary_min = 160 * 28.7 / w
secondary_min = 80 * 3.0 / w
total_h = (primary_min + secondary_min) / 60
primary_h = primary_min / 60
print(f'{total_h:.1f} {primary_h:.1f}')
")"
ETA_TOTAL="${ETA%% *}"; ETA_PRIMARY="${ETA##* }"
echo "[launch_mining] ETA at W=$WORKERS on $BOX: ~${ETA_TOTAL}h total (primary/clair-puct"
echo "[launch_mining]   ~${ETA_PRIMARY}h, the deciding statistic; sign-check/tier1-greedy nearly free)."
echo "[launch_mining]   Reference: ~6h at W=14 local, ~3.7h at W=22 laptop [UNVERIFIED, see"
echo "[launch_mining]   caveat above]; budget 6-8h. Per-position checkpointed and"
echo "[launch_mining]   --resume-able -- safe to kill for box priority at any time."

# --------------------------- 3. PROCESS GATE (per box) ----------------------
# `pgrep -f X || true` -- a no-match exit-1 is expected, never treated as an
# error (standing rule: wrap pkill/pgrep exit codes).
CONFLICT=0
for pat in "${BLOCKED_PATTERNS[@]}"; do
  pids="$(pgrep -f "$pat" || true)"
  if [ -n "$pids" ]; then
    echo "[launch_mining] REFUSING ($BOX): pattern '$pat' matched running pid(s): $pids" >&2
    CONFLICT=1
  fi
done
if [ "$CONFLICT" -ne 0 ]; then
  echo "[launch_mining] a higher-priority tenant is running on $BOX -- not launching." >&2
  exit 1
fi
echo "[launch_mining] process gate clear ($BOX) -- no blocked pattern is running"

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
     --strata "$STRATA" --box "$BOX" --out-root "$OUT_ROOT"
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
   && systemd-run --user --scope -p MemoryMax="$MEM_MAX" true >/dev/null 2>&1; then
  MEM_WRAP=(systemd-run --user --scope -p MemoryMax="$MEM_MAX" -p MemorySwapMax=0)
  echo "[launch_mining] memory scope ACTIVE (MemoryMax=$MEM_MAX on $BOX) -- an overrun kills"
  echo "[launch_mining]   THIS RUN, not the VM (memory: reference_wsl2_host_memory_teardown)."
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
