#!/usr/bin/env bash
# ============================================================================
# BUDGET/ELO PARETO CURVE — overnight cell queue (both boxes, work-stealing).
#
# Pre-registration: measurement/classical_search/PARETO_CURVE_PREREG.md
#   (read it before touching anything here — cells, bands, n and the read-out
#   rules are FIXED there, and were fixed before any cell ran.)
#
# WHAT THIS RUNS: the classical deploy champion at a range of search budgets,
# head-to-head against the deploy champion itself (k4x688 = 2752). Pure CPU —
# `--info fair` instantiates no net, so there is no carc-orch, no GPU and no
# OMP-pin concern here. The elo axis is "distance from the config we would field";
# the cost axis is each cell's own measured prefix ms/move.
#
# WIDTH IS RE-SOLVED AT EACH BUDGET (cells come in pairs sharing a seed band, so
# the k4-vs-k2 contrast is a deck-matched double-CRN delta). At 8x, allocation was
# the ENTIRE effect: k8x2752 +3.5 vs k16x1376 +35.6 at the same total. A budget
# point measured at one arbitrary allocation is uninterpretable.
#
# WORK STEALING: every cell uses --shared-claim against one pool on the share, so
# both boxes drain the same cell together and a box that exhausts the pool moves
# to the next cell on its own. Cells are individually resumable — re-running this
# script picks up cached games and skips completed cells.
#
# ⚠️ IF YOU KILL THIS: clean stranded .claim files before resuming, or the resume
#    stalls forever waiting on claims whose owner is dead
#    (memory: feedback_shared_claim_orphan_stall). Claims self-expire after
#    --claim-stale-secs (2h) but that is a slow path, not a substitute.
#
# USAGE (each box, detached):
#   SHARE=/mnt/c/carc-shared W=16 nohup setsid .../pareto_curve_queue.sh &
#   local box  -> SHARE=/mnt/c/carc-shared
#   laptop/remote -> SHARE=/mnt/carc-shared      (the mount path DIFFERS by box)
# ============================================================================
set -uo pipefail          # NOT -e: one failed cell must not abandon the queue
cd /home/doctor/projects/carcassone

SHARE=${SHARE:-/mnt/c/carc-shared}
W=${W:-16}
N=${N:-400}
OUT_ROOT="$SHARE/classical_search"
LOG=${LOG:-measurement/classical_search/pareto_curve_$(hostname -s).log}

export CARCASSONNE_TT_CAP=${CARCASSONNE_TT_CAP:-200000}

[ -d "$SHARE" ] || { echo "FATAL: share not mounted at $SHARE" >&2; exit 1; }
mkdir -p "$OUT_ROOT"

# cell := name : k_dets : sims : band     (opponent is always the deploy champion)
# Priority order — the sub-deploy region first: it is the decision-relevant one
# (clock margin), and cells 1-4 are the cheapest, so a short night still lands them.
CELLS=(
  "pareto_k4x344_1376_vs_deploy:4:344:60000000000"     # 0.5x, deploy width
  "pareto_k2x688_1376_vs_deploy:2:688:60000000000"     # 0.5x, alt width (shares band -> deck-matched)
  "pareto_k4x172_688_vs_deploy:4:172:62000000000"      # 0.25x, deploy width
  "pareto_k2x344_688_vs_deploy:2:344:62000000000"      # 0.25x, alt width (shares band)
  "pareto_k4x1376_5504_vs_deploy:4:1376:64000000000"   # 2x  — never measured H2H vs deploy
)

echo "[$(date +%F_%T)] === pareto curve queue START on $(hostname -s) ===" | tee -a "$LOG"
echo "[$(date +%F_%T)] share=$SHARE W=$W n=$N rev=$(git rev-parse --short HEAD)" | tee -a "$LOG"

for cell in "${CELLS[@]}"; do
  IFS=: read -r name kd sims band <<< "$cell"
  total=$(( kd * sims ))

  if [ -f "$OUT_ROOT/$name/summary.json" ]; then
    echo "[$(date +%F_%T)] SKIP $name (summary.json already present)" | tee -a "$LOG"
    continue
  fi

  echo "[$(date +%F_%T)] --- CELL $name : k${kd}x${sims} = $total sims vs deploy 2752, band $band" | tee -a "$LOG"
  nice -n 19 .venv/bin/python -u \
      scripts/classical_search/eval_fair_puct.py \
      --info fair --opponent fair-champion \
      --exact-k 2 --k-dets "$kd" --sims "$sims" \
      --opp-k-dets 4 --opp-sims 688 \
      --n "$N" --paired --seed-start "$band" --workers "$W" \
      --out-root "$OUT_ROOT" --out-subdir "$name" \
      --shared-claim --no-results-csv >> "$LOG" 2>&1
  rc=$?
  echo "[$(date +%F_%T)] --- CELL $name exited rc=$rc" | tee -a "$LOG"
done

echo "[$(date +%F_%T)] === pareto curve queue DONE on $(hostname -s) ===" | tee -a "$LOG"
