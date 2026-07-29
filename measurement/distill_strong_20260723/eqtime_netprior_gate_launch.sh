#!/usr/bin/env bash
# =============================================================================
# CL-067 EQUAL-WALL-CLOCK GATE  —  PRE-REGISTERED 2026-07-28, BEFORE LAUNCH.
#
# THE QUESTION
#   CL-067 is settled at EQUAL SIMS: the distilled strong-teacher policy priors
#   (iter_03) beat the deploy champion by +35.7 +/- 12.3 elo pooled over 800
#   deck-paired games (bands 52e9 gate +42.8, 56e9 confirm +28.7; both statistics
#   past 2 sigma pooled). What is NOT settled is whether that edge survives its
#   own COST. Measured solver-free prefix ms/move ratios (candidate/champion) at
#   IDENTICAL sims:
#     gate (W28 loaded)          4.29x
#     confirm (W48+W26 loaded)   5.48x
#     unloaded W2 probe          4.24x   <- the honest single-agent deploy regime
#       (/mnt/c/carc-shared/distill_strong_20260723/cost_probe_unloaded_w2/summary.json:
#        champ_prefix 11675.3 ms vs rung 2752.0 ms => 4.24x)
#   So the candidate is ~4.2-5.5x MORE expensive per move at identical sims.
#   THIS CELL asks the deployment question directly: give the candidate a REDUCED
#   budget whose MEASURED per-move cost equals the champion's, and play it out.
#
#   It doubles as the fresh-band arm this configuration owes in its own right.
#
# DESIGN (single variable vs the CL-067 gate: the candidate's sims budget)
#   candidate : distilled iter_03 net POLICY priors + FROZEN curve125 leaf
#               (value loop SEVERED), fair PIMC, k_dets=4, sims=169  (676 total)
#   opponent  : DEPLOY champion, FairHeuristicPriorAgent, k_dets=4, sims=688
#   both      : exact-K 2 marginalized endgame, curve125 leaf a36d2e15a3b3d71d
#               auto-injected in-process on BOTH sides, c_puct 1.5, tau_p 5.0
#   n=400 deck-paired (200 decks x 2 seats)
#   width HELD AT k4 deliberately, matching the gate, so the ONLY variable is the
#     budget. See caveat 3 -- this is a knowingly PESSIMISTIC choice.
#
# HOW sims=169 WAS CHOSEN  (MEASURED, not divided -- see eqtime_netprior_probe.sh)
#   Probe: W16 per box, carc-orch SHM, fwd=6, max_batch=W, server libtorch pool
#   pinned OMP=1, n=32 paired, scratch band 99.5e9, per-host out-dir,
#   candidate k4x162 vs opponent k4x688. Measured prefix ms/move (cand / opp):
#     LOCAL  (RTX 5060 Ti):  3701.2 / 3854.9  = ratio 0.960   [per-sim 4.08x]
#     LAPTOP (RTX 4070 Lap): 4398.8 / 3294.7  = ratio 1.335   [per-sim 5.67x]
#   The local per-sim ratio 4.08x independently reproduces the 4.24x unloaded
#   figure; the LAPTOP is materially worse for the net (weaker GPU relative to its
#   CPU), reconfirming the 2026-07-19 note that the ratio is box-dependent.
#   => equal-time sims are 168.7 (local) and 121.3 (laptop). ONE sims value cannot
#      equalise both boxes, and per-box sims values are DISQUALIFIED: with
#      --shared-claim the two seats of one deck can land on different boxes, so
#      that would deck-pair two DIFFERENT agents against each other.
#   ACCEPT RULE (fixed before the probe): ratio must land in [0.90, 1.10].
#
# ==> TWO ARMS, NOT POOLED, EACH ON ITS OWN BAND:
#   A. PRIMARY / EQUAL-TIME  — LOCAL box only, band 82000000000, k4x169.
#      Predicted ratio 1.00. This is THE pre-registered cell; the verdict is read
#      off this arm alone. Local is also the box the production champion runs on.
#   B. COMPANION / CANDIDATE-FAVOURED — LAPTOP only, band 84000000000, k4x169.
#      Predicted ratio 1.39, i.e. the candidate is handed ~39% MORE wall-clock
#      than the champion. Its role is a one-sided bracket, fixed in advance:
#        - if the candidate LOSES even here, the equal-time loss is not a
#          knife-edge artefact of the sims choice;
#        - if it WINS here but not in arm A, the break-even clock multiple lies
#          between 1.0x and 1.4x -- an interval, which is the useful readout.
#      It is a SENSITIVITY arm. It is NOT the verdict and is NOT pooled with A
#      (different bands, different clock ratios; cross-band pooling has burned
#      this project twice -- L2-2, and CL-069's supersession of the halving screen).
#   Bands verified free by enumerating BAND_CLAIMS.txt plus every share
#   manifest.json seed_start >= 60e9 (60/62/64/66/68/70/72/74/76/78/80/90/91/99e9
#   burned), then claimed in /mnt/c/carc-shared/BAND_CLAIMS.txt before launch.
#
# PRE-REGISTERED PROJECTION: approximately a WASH, with a real tail risk of a
#   clear loss. Three independent priors bracket it:
#     (1) CL-060 budget exchange rate (k4, fixed width): 4.07x budget = +27.85
#         elo UP from deploy  =>  a ~4.1x cut costs ~-28  =>  net +35.7-28 = +8
#     (2) DIRECT measurement of this exact cut on the champion:
#         pareto_k4x172_688_vs_deploy (band 62e9, n=400 paired) = -46.3 elo
#         (margin -4.897 pts/deck, z -6.29)  =>  net +35.7-46.3 = -11
#         [the down-step is steeper than the up-step because the curve is concave:
#          flat above ~2064 (CL-068/CL-069), a cliff below 688]
#     (3) the FLYWHEEL net's own measured degradation (different lineage,
#         2026-07-19/20: 688 tie -> 395 = -8.7 -> 154 = -75.9) => a ~4.5x cut cost
#         THAT net ~76 elo  =>  net +35.7-76 = -40, a CLEAR LOSS.
#   Centre of mass: -11 to +8 (a wash). Tail: -40 if net-prior agents degrade with
#   budget as steeply as the flywheel net did rather than as the champion does.
#
# PRE-REGISTERED DECISION RULES (fixed BEFORE the run reads out) -- arm A only.
#   Report BOTH statistics always (winrate z AND deck-paired margin z); reporting
#   only the one that clears is how three overturned findings here got their start.
#   A. BOTH statistics >= +2 sigma  => the distilled priors are stronger AT EQUAL
#      WALL-CLOCK. A genuine production-upgrade candidate on its own terms, and it
#      FUNDS G3 (per-move cost reduction) as an amplifier, not a prerequisite.
#   B. Positive but sub-2-sigma (elo >= 0, at least one statistic >= +1 sigma)
#      => wall-clock-COMPETITIVE, not superior. FUNDS G3: the line's whole value
#      then hinges on making the net cheaper (quantisation, smaller net, batching
#      the k determinizations) -- exactly G3's stated unpark trigger.
#   C. WASH (both statistics inside +/-2 sigma, elo point estimate in [-20, 0))
#      => the +35.7 equal-sims edge is bought back entirely by the clock. Neither
#      deployable nor refuted; G3 stays parked unless Joshua funds cost work.
#      One-line summary: you can have the strength or the clock, not both.
#   D. BOTH statistics <= -2 sigma  => KILL the distilled line FOR DEPLOY at this
#      cost point. The strength question is answered and the answer does not
#      survive the clock; no further work on the STRENGTH axis can change it, and
#      the net would need to get >=3-4x cheaper before the line is worth revisiting.
#
# IN-FLIGHT COST GUARD (this is what makes the cell "equal time" rather than a
#   claim about it): the final summary's champ_prefix_ms_per_move (== CANDIDATE)
#   / rung_ms_per_move (== OPPONENT) must ALSO land in [0.90, 1.10] over the real
#   run. If it drifts outside, the cell is NOT equal-time and MUST be read as a
#   cell at whatever ratio it actually ran -- state the ratio, do not launder it.
#   Field semantics verified by READING THE EMITTER (eval_fair_puct.py:1606-1619),
#   not the field name: the 2026-07-26 "~4x cheaper" error came from the latter.
#   Both counters EXCLUDE the marginalized endgame solve, which is exact-K2 on
#   BOTH sides and identical by construction -- so equalising the PREFIX is right.
#
# CAVEATS, stated before the number exists
#   1. TRANSPORT: the net is served from the GPU via carc-orch SHM; the CL-067
#      rows on record used the same path. Cite as "same weights, GPU transport",
#      NEVER as bit-identical (CL-069).
#   2. The cost ratio is BOX- and LOAD-dependent. W=16 per box is fixed here and
#      was fixed for the probe -- chosen so the loaded ratio sits near the
#      UNLOADED 4.24x (the honest single-agent deployment regime) rather than the
#      5.48x of a W48+W26 harvest. Do NOT raise W: it would invalidate sims=169.
#   3. HOLDING k4 UNDER-ALLOCATES THE CANDIDATE. CL-068 found optimal width shrinks
#      with budget: at 688 total sims, k2x344 beat k4x172 by +8.8 elo (-37.5 vs
#      -46.3, same band 62e9). An equal-time netprior agent tuned for its OWN
#      budget would plausibly score ~+9 elo better than this cell measures. k4 is
#      held anyway because it isolates the budget variable against the gate.
#      => a NEGATIVE result here is NOT proof that no equal-time netprior wins.
#   4. Pooling across bands was never pre-registered for CL-067 and is not here.
#
# OPS: one carc-orch server per box (per-host SHM names), fwd=6, max_batch=W,
#   OMP/MKL/OPENBLAS=1 on the SERVER's env line. NO leaf env is exported
#   (fair_net_vs_net_orch.sh header note 2: the harness's _CANON_ENV setdefault
#   must win and curve125 is injected in-process). Detached; run_watchdog.sh armed
#   on BOTH boxes with a band-specific pgrep pattern. --shared-claim is kept so a
#   watchdog relaunch resumes rather than restarts (each arm is single-box, so it
#   is a resume mechanism here, not work-stealing).
#
# STABLE PATH (the watchdog re-execs this):
#   /mnt/c/carc-shared/eqtime_netprior_gate_launch.sh   (local)
#   /mnt/carc-shared/eqtime_netprior_gate_launch.sh     (laptop)
# =============================================================================
set -uo pipefail
cd /home/doctor/projects/carcassone

CAND_SIMS="${CAND_SIMS:-169}"
OPP_SIMS_V="${OPP_SIMS_V:-688}"
W="${W:-16}"
N="${N:-400}"
BAND="${BAND:-82000000000}"
HOSTS="$(hostname -s)"
if [ -d /mnt/c/carc-shared ]; then SHARE=/mnt/c/carc-shared; else SHARE=/mnt/carc-shared; fi
OUT_ROOT="${OUT_ROOT:-$SHARE}"
CKPT="$SHARE/distill_strong_20260723/ckpt/iter_03.pt"
SUBDIR="eqtime_netprior_k4x${CAND_SIMS}_vs_deploy_b${BAND}"

[ -f "$CKPT" ] || { echo "FATAL: ckpt missing: $CKPT" >&2; exit 1; }
[ -d "$OUT_ROOT" ] || { echo "FATAL: share not mounted at $OUT_ROOT" >&2; exit 1; }

echo "=== EQTIME GATE | host=$HOSTS cand k4x${CAND_SIMS} vs deploy k4x${OPP_SIMS_V} | W=$W n=$N band=$BAND rev=$(git rev-parse --short HEAD) $(date -u +%F_%T) ==="

CAND_CKPT="$CKPT" OW="$W" ORCH_FWD=6 ORCH_MAX_BATCH="$W" OPP_SIMS="$OPP_SIMS_V" \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  nice -n 19 bash scripts/classical_search/fair_net_vs_net_orch.sh \
    --info fair-netprior --opponent fair-champion \
    --exact-k 2 --k-dets 4 --sims "$CAND_SIMS" --opp-k-dets 4 \
    --n "$N" --paired --seed-start "$BAND" \
    --out-root "$OUT_ROOT" --out-subdir "$SUBDIR" \
    --shared-claim --no-results-csv
rc=$?
echo "=== EQTIME GATE exited rc=$rc $(date -u +%F_%T) ==="
exit $rc
