#!/usr/bin/env bash
# ============================================================================
# SUB-PRODUCTION BUDGET CURVE, graded on an OUT-OF-LINEAGE opponent.
#   BLIND champion (fair PIMC, curve125, exact-K<=2) vs SIGHTED RoD-v2 iter_02
#   (bare NeuralMCTS, fair_chance=False, anchor knobs, net on the GPU via carc-orch).
#
# WHY THIS AND NOT MORE OF THE PARETO CURVE. Last night's curve graded the champion
# against ITSELF, and on that anchor halving the budget looked free (+0.9 +-17.4 at
# 1376). Against RoD2 the same halving looked ~50 elo costly (2750 -> +230.2,
# 1376 -> +179.5; diff -50.7 +-41.1, z 1.23, n.s. and cross-band). Not a
# contradiction -- but a self-anchored comparison CANNOT see a weakness both sides
# share, and an out-of-lineage opponent can. This curve is the instrument that does
# not have that blind spot.
#
# It is affordable because the blind cell did NOT saturate: wr 0.6475 at 1376
# (band 68e9), so there is dynamic range both up and down. A rung that saturates
# (wr > ~0.9) is ceiling-compressed and its elo is a floor, not a measurement --
# SAY SO in the read-out rather than quoting it.
#
# DESIGN
#  * ONE seed band (70e9) for EVERY rung -> adjacent budgets are deck-matched (CRN),
#    the CL-046 ladder design. Absolute levels are then correlated across rungs; the
#    DELTAS are the sharp quantity. Do not quote the absolutes as independent.
#  * FIXED width k4 -> a clean single budget axis. ⚠️ Known cost of this choice:
#    CL-068 found optimal width GROWS with budget and k2 beat k4 at 688, so the
#    lowest rungs here are deliberately UNDER-ALLOCATED and their elo is a slight
#    underestimate of what that budget can do. Fixing width is still right for a
#    curve -- otherwise two axes move at once.
#  * The 1376 rung is a deliberate re-run on the new band: it makes that point
#    CRN-comparable with its neighbours AND serves as the owed fresh-band
#    replication of the 68e9 +105.6 (never promote from a single screen).
#
# READ-OUT (fixed before the run): per rung report BOTH statistics (winrate z AND
# deck-paired margin z) AND the raw winrate so saturation is visible; report each
# rung's own ms/move both sides (this is NOT cost-matched -- at 1376 we spent 1.38x
# the opponent). Adjacent-rung deltas are deck-matched; absolutes are not
# independent. Nothing here promotes anything.
#
# ⚠️ INTERPRETATION, corrected 2026-07-27. A candidate WIN is NOT a clean
# "conservative lower bound". The asymmetries do not all point the same way:
#     information -> we are HANDICAPPED (blind vs sighted; tax ~156 elo, large)
#     leaf        -> we are ADVANTAGED (curve125 vs curve100+residual; CL-051
#                    established curve125 is a real leaf-strength win)
#     endgame     -> we are ADVANTAGED (exact-K<=2 tail vs their bare, no tail)
#     cost        -> we SPEND MORE (1.38x per move at the 1376 rung)
# So the net direction is UNDETERMINED. The honest claim is the narrow one: our
# champion, blind and at budget B, beats the RoD-v2 anchor agent playing sighted.
# It does NOT license "therefore the lineage gap is at least this".
# ============================================================================
set -uo pipefail
cd /home/doctor/projects/carcassone

SHARE=${SHARE:-/mnt/c/carc-shared}
OW=${OW:-16}
N=${N:-200}
BAND=${BAND:-70000000000}
OPP_CKPT=${OPP_CKPT:-$SHARE/rod_v2_flywheel/ckpt/iter_02.pt}
LOG=${LOG:-measurement/classical_search/blind_curve_$(hostname -s).log}

[ -f "$OPP_CKPT" ] || { echo "FATAL: opponent ckpt missing: $OPP_CKPT" >&2; exit 1; }

# k_dets fixed at 4; only sims/det moves.  sims_per_det:total:xdeploy
RUNGS=(
  "86:344:0.125x"
  "172:688:0.25x"
  "344:1376:0.5x"
  "516:2064:0.75x"
  "688:2752:1x_PRODUCTION"
)

echo "[$(date +%F_%T)] === blind curve START on $(hostname -s) (OW=$OW n=$N band=$BAND) ===" | tee -a "$LOG"

for rung in "${RUNGS[@]}"; do
  IFS=: read -r sims total tag <<< "$rung"
  name="blindcurve_k4x${sims}_${total}_vs_sighted_rodv2_b70e9"

  if [ -f "$SHARE/classical_search/$name/summary.json" ]; then
    echo "[$(date +%F_%T)] SKIP $name (already complete)" | tee -a "$LOG"
    continue
  fi

  echo "[$(date +%F_%T)] --- RUNG $tag : k4x${sims} = ${total} sims" | tee -a "$LOG"
  OPP_CKPT="$OPP_CKPT" OW="$OW" nice -n 19 \
    bash scripts/classical_search/bare_net_opp_orch.sh \
      --exact-k 2 --k-dets 4 --sims "$sims" \
      --n "$N" --paired --seed-start "$BAND" \
      --out-root "$SHARE/classical_search" --out-subdir "$name" \
      --shared-claim --no-results-csv >> "$LOG" 2>&1
  echo "[$(date +%F_%T)] --- RUNG $tag exited rc=$?" | tee -a "$LOG"
done

echo "[$(date +%F_%T)] === blind curve DONE on $(hostname -s) ===" | tee -a "$LOG"
