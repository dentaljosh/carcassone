#!/usr/bin/env bash
# ============================================================================
# rr_puct1376_vs_net-iter02_k2 — the champion at HALF budget vs the independent
# neural lineage (RoD-v2 iter_02). Joshua, 2026-07-27 ("humor me").
#
# WHAT THIS IS: a single-variable replication of the existing round-robin cell
#   results.csv rr_puct2750_vs_net-iter02_k2 (2026-07-07, n=200 screen):
#   155W/6D/39L = +230.2 elo (wr z +8.20, paired z +11.03), cand 6200 ms/move
#   vs opp 3007.
# ONLY cand_sims changes: 2750 -> 1376. Every other knob is held at that cell's
# values (c_puct 1.5, tau_p 5.0, quant float, select visits, exact-K<=2) so the
# two are directly comparable and the delta is attributable to budget alone.
#
# WHY 1376: last night's Pareto curve found 1376 is the KNEE — at the deploy
# champion's own anchor it is statistically indistinguishable from 2752 (+0.9
# +-17.4) at 14.6% of the tournament clock vs 26%. This asks whether that
# also holds against an opponent OUTSIDE the champion's lineage.
#
# ⚠️ THREE THINGS THIS IS NOT — read before quoting the number.
#  1. NOT the FAIR deploy config. This harness is CLAIRVOYANT matched-mode by
#     construction (both sides descend the true deck) and its candidate is the
#     clairvoyant HeuristicPriorAgent, not the fair PIMC k4x344 agent. It is the
#     right harness anyway: eval_fair_puct.py's `--opponent net` runs the net as
#     a fair-NETPRIOR agent over OUR curve125 leaf, which is not RoD2's identity
#     at all. Here `net:<ckpt>` pins RoD2 to its anchor config (sims=200,
#     c_puct=3.0, v2.9 leaf + residual_scale 0.25, BARE, no exact tail), which is
#     how every RoD2 anchor row was played.
#  2. NOT equal wall-clock. The 2750 cell ran 6200 vs 3007 ms/move (~2x); at 1376
#     the candidate should land near ~3100, i.e. roughly COST-MATCHED by accident.
#     That is a nice property, not a designed one -- do not read it as an
#     equal-cost verdict without checking the run's own ms/move.
#  3. NOT expected to be informative if it saturates. RoD2 iter_02 is a ~h3200-tier
#     yardstick and the champion cleared it by +230 at 2750. If this returns a
#     winrate above ~0.9 the cell is ceiling-compressed and the elo is a lower
#     bound, not a measurement -- exactly the failure that made CL-060's h800-rung
#     closure read "flat past 2752" at z=0.86 before a direct H2H refuted it at
#     z=3.48. SAY SO in the read-out rather than quoting the number.
#
# READ-OUT (fixed before the run): report BOTH statistics (winrate z AND
# deck-paired margin z), report the winrate explicitly so saturation is visible,
# and report the run's own ms/move both sides. n=200 is a SCREEN -- the same
# power as the 2750 cell it replicates, deliberately, so the two are comparable.
# Nothing here promotes anything.
#
# BAND 66e9 — fresh, chosen by enumeration (60/62/64e9 burned by the Pareto
# curve last night; 9.5e9 was the 2750 cell's own band).
# ============================================================================
set -uo pipefail
cd /home/doctor/projects/carcassone

SHARE=${SHARE:-/mnt/c/carc-shared}
W=${W:-16}
N=${N:-200}
CKPT="$SHARE/rod_v2_flywheel/ckpt/iter_02.pt"
LOG=${LOG:-measurement/classical_search/rr_1376_vs_rod2_$(hostname -s).log}

[ -f "$CKPT" ] || { echo "FATAL: rod2 ckpt missing: $CKPT" >&2; exit 1; }

echo "[$(date +%F_%T)] rr_puct1376_vs_net-iter02_k2 START on $(hostname -s) (W=$W n=$N)" | tee -a "$LOG"

nice -n 19 .venv/bin/python -u \
    scripts/classical_search/eval_puct_priors.py \
    --candidate puct --cand-sims 1376 \
    --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits \
    --opponent "net:$CKPT" \
    --exact-k 2 \
    --n "$N" --paired --seed-start 66000000000 --workers "$W" \
    --out-root "$SHARE/classical_search" \
    --out-subdir rr_puct1376_vs_net-iter02_k2 \
    --shared-claim --no-results-csv >> "$LOG" 2>&1

echo "[$(date +%F_%T)] exited rc=$? on $(hostname -s)" | tee -a "$LOG"
