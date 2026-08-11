#!/usr/bin/env bash
# Autonomous Phase-2 gate for the hybrid-handoff experiment. Runs detached on the
# LOCAL box: waits for Phase 1 (5 bands x n=200) to complete, decides which K beat
# iter8 (paired_z>=GATE & margin>0), then conditionally launches Phase 2
# (hybrid:K:3200 vs heur@3200 + n=400 top-up of the vs-iter8 band) on BOTH boxes
# via the orch launcher. Writes a decision/log file the operator reads on return.
#
# Usage (detached):
#   setsid bash -c 'nohup bash scripts/level2/auto_phase2.sh > \
#     /mnt/c/carc-shared/level2_hybrid/auto_phase2.log 2>&1' </dev/null &
set -uo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-python}
SHARE_LOCAL=${SHARE_LOCAL:-/mnt/c/carc-shared}
SHARE_LAPTOP=${SHARE_LAPTOP:-/mnt/carc-shared}
OW_LOCAL=${OW_LOCAL:-48}   # Phase-2 local W (measured orch-eval optimum; Joshua's call)
OW_LAPTOP=${OW_LAPTOP:-26}
GATE=${GATE:-1.5}
MAXK=${MAXK:-2}
N=${N:-200}
D="$SHARE_LOCAL/level2_hybrid"
DEC="$D/PHASE2_DECISION.txt"
cd "$REPO"

log(){ echo "[auto-phase2 $(date -u +%H:%M:%S)] $*"; }

# Phase-1 bands that must each reach n=200.
BANDS=(hybridK2h3200__vs__iter8_b340_n${N} hybridK3h3200__vs__iter8_b340_n${N} \
       hybridK5h3200__vs__iter8_b340_n${N} hybridK8h3200__vs__iter8_b340_n${N} \
       hybridK5h800__vs__iter8_b340_n${N})

log "waiting for Phase 1 (5 bands x $N) to complete ..."
for i in $(seq 1 1200); do        # ~6.7h at 20s
  done1=1
  for b in "${BANDS[@]}"; do
    c=$(find "$D/$b" -name 'seed*_a*.json' 2>/dev/null | wc -l)
    [ "$c" -ge "$N" ] || done1=0
  done
  if [ "$done1" = 1 ]; then log "Phase 1 complete (all 5 bands >= $N)"; break; fi
  sleep 20
done

# Grace: let the Phase-1 launchers finish summaries + tear down their SHM servers
# (Phase 2 reuses the same per-host SHM name).
log "grace 90s for Phase-1 launchers to exit + free SHM ..."
sleep 90

log "computing Phase-1 verdict (gate paired_z>=$GATE, margin>0, top $MAXK) ..."
"$PY" scripts/level2/report_hybrid.py --root "$D" --md "$D/PHASE1_TABLE.md" || true
WINNERS=$("$PY" scripts/level2/report_hybrid.py --root "$D" --phase2-winners --gate "$GATE" --max-k "$MAXK" 2>/dev/null | tr -s ' ')
WINNERS=$(echo "$WINNERS" | xargs)   # trim

{
  echo "=== PHASE-2 DECISION  $(date -u) ==="
  echo "gate: paired_z >= $GATE AND margin > 0   (n=$N screen)"
  echo "winning K (beat iter8): '${WINNERS:-<none>}'"
  echo
  echo "Phase-1 table:"
  cat "$D/PHASE1_TABLE.md" 2>/dev/null
} > "$DEC"

if [ -z "$WINNERS" ]; then
  log "NO K beat iter8 at gate $GATE -> NO Phase 2. Verdict: endgame weakness NOT"
  log "separable by simple phase handoff (or limited full-game impact). Done."
  echo "RESULT: no Phase-2 launched (no hybrid beat iter8)." >> "$DEC"
  exit 0
fi

log "Phase-2 candidates K=[$WINNERS]. Launching champion check + n=400 top-up on both boxes."
echo "RESULT: launching Phase 2 for K=[$WINNERS] (vs heur@3200, + vs-iter8 top-up to n=400)." >> "$DEC"

# Local Phase 2 (own server, shared-claim).
setsid bash -c "SHARE=$SHARE_LOCAL OW=$OW_LOCAL N=$N PH=2 KS=\"$WINNERS\" TOPUP=400 \
  nohup bash scripts/level2/run_hybrid_bands_orch.sh --shared-claim \
  > $D/local_phase2.log 2>&1" </dev/null &
log "local Phase-2 launched."

# Laptop Phase 2 (own server, shared-claim) — background the ssh call (hang trap).
timeout 40 ssh laptop-wsl "cd ~/projects/carcassone && source .venv/bin/activate && \
  SHARE=$SHARE_LAPTOP OW=$OW_LAPTOP N=$N PH=2 KS=\"$WINNERS\" TOPUP=400 \
  setsid nohup bash scripts/level2/run_hybrid_bands_orch.sh --shared-claim \
  > $SHARE_LAPTOP/level2_hybrid/laptop_phase2.log 2>&1 </dev/null & echo LAUNCH_ISSUED" \
  >> "$DEC" 2>&1 &
log "laptop Phase-2 launch issued. auto_phase2 done; Phase 2 running."
