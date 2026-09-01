#!/usr/bin/env bash
# E-1b LOCAL LAUNCH — the pre-launch ladder, then the detached cell.
#
#   REPO=<worktree> ./launch_local.sh            # ladder + smoke + launch cell
#   REPO=<worktree> STOP_AFTER=smoke ./launch_local.sh   # ladder + smoke, no cell
#
# ⚠️ Share is /mnt/c/carc-shared LOCALLY (/mnt/carc-shared on the laptop).
# W=32 is the standing default (owner ruling 2026-09-01: W = logical threads).
# It is THROUGHPUT-ONLY: every unit is deterministic in
# (deck_seed, ply, world, arm, family), so results are bit-identical at any W
# and no reading depends on the worker count.
set -u

REPO="${REPO:-/home/doctor/projects/carcassone}"
export REPO
D="$REPO/measurement/e1b_armed_continuation_20260901"
PY="${PY:-/home/doctor/projects/carcassone/.venv/bin/python}"
export PY
export BOX=local
export W="${W:-32}"
export SHARE=/mnt/c/carc-shared
export MEM_CAP_GB="${MEM_CAP_GB:-6}"
export ARM_CAP_S="${ARM_CAP_S:-1800}"
export THREADS="${THREADS:-1}"
export CHUNK="${CHUNK:-4}"
export SUFFIX="${SUFFIX:-}"
STOP_AFTER="${STOP_AFTER:-}"

DIE() { echo "⛔ $*" >&2; exit 1; }
chmod +x "$D/run_e1b.sh"
mkdir -p "$D/logs"

# --- 0. THE PRE-LAUNCH LADDER — every rung fail-closed ----------------------
# 1. the band. The orchestrator drops BAND_CLAIMED only AFTER a fresh tree sweep
#    and the BAND_REGISTRY.csv append, in that order.
[ -f "$D/BAND_CLAIMED" ] || DIE "BAND_CLAIMED is absent — see BAND_CLAIMED.placeholder.
   ⛔ E-1b re-prices FROZEN banked plies and draws NO new decks, so it consumes
   no deck band; the orchestrator still gates the launch on an explicit
   acknowledgement that no band is being spent. Drop the file to proceed."
# 2. blindness: the freeze commit must have named itself.
grep -q '"blind_commit": *"[0-9a-f]\{40\}"' "$D/BLIND_COMMIT.json" \
  || DIE "BLIND_COMMIT.json still says PENDING — a commit cannot name its own
   hash, so the FREEZE commit must be followed by a stamping commit."
# 3. the contract tests and the adjudicator selftest.
"$PY" -m pytest "$D/test_e1b.py" -q || DIE "contract tests FAILED"
"$PY" "$D/adjudicate_e1b.py" --selftest || DIE "adjudicator selftest FAILED"
# 4. a process census BY FULL ARGS (never -C python / comm: a silent long job is
#    invisible otherwise — auto-memory feedback_no_agent_compute_beside_eval).
echo "=== process census (ps -eo args) ==="
ps -eo pid,etime,pcpu,args --sort=-etime | grep -v grep \
  | awk 'NR==1 || /python|carc|cargo/' | head -30
echo "=== load ==="; uptime

# --- 1. the unit lists -------------------------------------------------------
[ -f "$D/units_local_fixed_v1.txt" ] || \
  "$PY" "$D/plan_units.py" --targets "$D/targets_continuation.jsonl" \
        --out-dir "$D" --box local > "$D/logs/plan_units.log" 2>&1 \
  || DIE "plan_units FAILED"

# --- 2. THE SMOKE — production knobs, tiny unit count, own out dir ----------
# Adjudicated from its OWN emitted manifest; nonzero exit on an empty cell.
if [ ! -f "$D/SMOKE_PASSED" ]; then
  MODE=smoke W=4 "$D/run_e1b.sh" || DIE "SMOKE FAILED — the cell does not launch"
  date -Is > "$D/SMOKE_PASSED"
fi
[ "$STOP_AFTER" = "smoke" ] && { echo "STOP_AFTER=smoke — cell NOT launched"; exit 0; }

# --- 3. THE CELL — detached ---------------------------------------------------
# setsid + nohup: the harness's background flag is NOT enough — a Mac-sleep
# SIGHUP or a WSL VM teardown both kill a tty-attached child.
setsid nohup "$D/run_e1b.sh" \
    > "$D/logs/driver_local${SUFFIX}.out" 2>&1 < /dev/null &
disown
echo "LAUNCHED local W=$W suffix='${SUFFIX}' arm_cap=${ARM_CAP_S}s chunk=$CHUNK"
echo "sentinel: $D/RUN_LIVE_CELL_local${SUFFIX}.json"
echo "ETA: ~2.5 h (2.2-3.0 h) — see PREREG.md §5"
