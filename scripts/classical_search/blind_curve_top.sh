#!/usr/bin/env bash
# ============================================================================
# BLIND CURVE — TOP EXTENSION, at the MEASURED-OPTIMAL allocation per budget.
# Continues measurement/classical_search band 70e9 so the new rungs stay
# DECK-MATCHED to the five that landed 2026-07-27 (344/688/1376/2064/2752, k4).
#
# WHY EXTEND. The landed ladder is not saturated at the top (wr 0.675 at 2752)
# and its WITHIN-DECK TREND is decisive: winrate +0.0789/doubling (z +6.07),
# margin +3.72 pts/deck/doubling (z +6.59), 100 shared decks. No individual step
# above 1376 clears 2sigma, but the LINE is the measurement -- the same standard
# CL-054 used to call a coherent monotone axis credible rather than a lone spike.
# Fitted slope projects wr ~0.75 at 5504 and ~0.83 at 11008, so saturation (~0.9)
# should not bite until ~22016. That is the headroom worth spending.
#
# ⚠️ ALLOCATION IS NO LONGER FIXED k4 -- these rungs use the MEASURED optimum,
# which is why the axis changes character here. From the record:
#   5504  -> k4x1376 : k8x688 was -1.99 pts/deck vs k4x1376 (z -1.48), SAME band
#                      => more worlds does NOT beat more depth at 2x (CL-060).
#   11008 -> k8x1376 : k8x1376 nominally +1.83 pts/deck over k4x2752 (z +1.41),
#                      and the H2H width residual was +22 elo (z 1.16) -- both
#                      UNRESOLVED, but k8 is the best-supported pick (CL-060).
#   22016 -> k16x1376: +35.6 vs k8x2752's +3.5 at the SAME total => allocation was
#                      the entire effect (CL-060 budget-curve extension). Not run
#                      here; queue it only after seeing where 11008 lands.
# Note the frontier holds sims/det at 1376 and grows WIDTH, not depth.
#
# ⚠️ CONSEQUENCE FOR THE SLOPE FIT, state it in any read-out: the five landed
# rungs are all k4, so a slope fit across ALL SEVEN mixes two axes (budget and
# width) and is NOT a clean budget slope. Report the k4-only subset (344..5504)
# as the clean axis, and the full set as the ACHIEVABLE FRONTIER. They answer
# different questions; do not merge them silently.
#
# ⚠️ ELO AGAINST A FIXED OPPONENT INFLATES AS WE CLIMB (the scale compresses near
# the top), so this slope is NOT comparable to CL-060's ~+14 elo/doubling, which
# was measured against the deploy champion. Compare slopes only within one
# opponent.
#
# NOT RUN HERE, BUT NOW CHEAP AND VALUABLE: a k4x2752 arm at 11008 on THIS band
# would be deck-matched against the k8x1376 rung below and would directly settle
# CL-060's OWN named #1 open test ("k8x1376 vs k4x2752 head-to-head at FIXED
# 11008 on ONE band -- resolves width directly instead of by quadrature
# difference"). The band stays available, so it can be added later at no penalty.
#
# READ-OUT: BOTH statistics per rung plus the RAW WINRATE so saturation is
# visible; a rung above wr ~0.9 is ceiling-compressed and its elo is a floor.
# Adjacent rungs are deck-matched; absolutes are correlated. Nothing promotes.
# ============================================================================
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

cd /home/doctor/projects/carcassone

SHARE=${SHARE:-/mnt/c/carc-shared}
OW=${OW:-16}
N=${N:-200}
BAND=${BAND:-70000000000}
OPP_CKPT=${OPP_CKPT:-$SHARE/rod_v2_flywheel/ckpt/iter_02.pt}
LOG=${LOG:-measurement/classical_search/blind_curve_top_$(hostname -s).log}

[ -f "$OPP_CKPT" ] || { echo "FATAL: opponent ckpt missing: $OPP_CKPT" >&2; exit 1; }

# k_dets:sims_per_det:total:tag   — the MEASURED optimum at each budget
RUNGS=(
  "4:1376:5504:2x_k4optimal"
  "8:1376:11008:4x_k8optimal"
)

echo "[$(date +%F_%T)] === blind curve TOP START on $(hostname -s) (OW=$OW n=$N band=$BAND) ===" | tee -a "$LOG"

# ⚠️ NEVER write `echo "[$(date ...)] rc=$?"`. Bash expands the word LEFT TO RIGHT, so the
#    command substitution RUNS FIRST and resets $? to date's status (0) before the later
#    $? is expanded -- a failed rung then logs "rc=0". That is exactly how the 2026-07-27
#    18:15 k8x1376 rung reported success after bare_net_opp_orch.sh correctly exited 1
#    (missing carc-orch binary in the pinned worktree). The wrapper was never at fault.
#    Capture rc into a variable on the VERY NEXT LINE after the command, then log $rc.
FAILED=0
for rung in "${RUNGS[@]}"; do
  IFS=: read -r kd sims total tag <<< "$rung"
  name="blindcurve_k${kd}x${sims}_${total}_vs_sighted_rodv2_b70e9"

  if [ -f "$SHARE/classical_search/$name/summary.json" ]; then
    echo "[$(date +%F_%T)] SKIP $name (already complete)" | tee -a "$LOG"
    continue
  fi

  echo "[$(date +%F_%T)] --- RUNG $tag : k${kd}x${sims} = ${total} sims" | tee -a "$LOG"
  OPP_CKPT="$OPP_CKPT" OW="$OW" nice -n 19 \
    bash scripts/classical_search/bare_net_opp_orch.sh \
      --exact-k 2 --k-dets "$kd" --sims "$sims" \
      --n "$N" --paired --seed-start "$BAND" \
      --out-root "$SHARE/classical_search" --out-subdir "$name" \
      --shared-claim --no-results-csv >> "$LOG" 2>&1
  rc=$?
  if [ "$rc" -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "[$(date +%F_%T)] --- RUNG $tag FAILED rc=$rc — the cell is INCOMPLETE; do NOT read its summary. See $LOG" | tee -a "$LOG"
  else
    echo "[$(date +%F_%T)] --- RUNG $tag exited rc=0" | tee -a "$LOG"
  fi
done

if [ "$FAILED" -ne 0 ]; then
  echo "[$(date +%F_%T)] === blind curve TOP FINISHED on $(hostname -s) with $FAILED FAILED RUNG(S) ===" | tee -a "$LOG"
  exit 1
fi
echo "[$(date +%F_%T)] === blind curve TOP DONE on $(hostname -s) (all rungs rc=0) ===" | tee -a "$LOG"
