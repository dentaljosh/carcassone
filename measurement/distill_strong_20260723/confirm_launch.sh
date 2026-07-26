#!/usr/bin/env bash
# ============================================================================
# CL-067 CONFIRMATION CELL — the owed fresh-band replication (drafted 2026-07-26).
#
# ⚠️ NOT YET APPROVED TO RUN. Needs (a) Joshua's go and (b) the orch operating
# point from the pre-flights (preflight_omp_ab.sh / preflight_w_ladder.sh).
#
# WHAT IT REPLICATES
#   results.csv distill_strong_iter03_netprior_vs_champ_deploy_k4x688_n400_paired
#   = the gate: iter_03 net POLICY priors + FROZEN curve125 leaf (value severed)
#   at DEPLOY budget k4x688 exact-K2 vs the deploy champion. n=400 deck-paired,
#   band 52e9: 221W-7D-172L, elo +42.8 (1sig 17.5), winrate z +2.45, deck-paired
#   margin +1.595 pts/deck (se 0.931, paired z +1.71).
#
# WHY IT IS OWED (CL-067 is Provisional, NOT promoted)
#   The two statistics disagree in strength: more GAMES won (z 2.45, clears 2sig)
#   by SMALLER margins (z 1.71, does not). Coherent for a policy-prior gain that
#   converts close games, but at the edge of what n=400 resolves -- and three
#   prior findings of exactly this shape were later overturned here (c=3 "+47",
#   anchor-fraction "+39", flywheel "+88.7" which went -3.5 on a fresh band).
#   Project rule: never promote from a single screen.
#
# SEED BAND: 56e9. Chosen by ENUMERATION, not eyeball -- 22/24/26/28/32/44/46/
#   52e9 are already burned in results.csv (52e9 is the gate itself). 99e9 is
#   pre-flight scratch and is never harvested.
#
# ⚠️ EQUAL-SIMS, BY DESIGN. This cell replicates CL-067 AS WRITTEN, and CL-067 is
#   an equal-SIMS claim. It deliberately does NOT settle deployability: the
#   candidate costs ~4.29x the champion per move in the gate's own summary
#   (verified 2026-07-26 -- the earlier "~4x cheaper" reading had the sign
#   backwards; fair-champion is in _HEAD_TO_HEAD so both figures are solver-free
#   prefix counters). That ratio was measured under orch contention and the true
#   multiple lies in 1.74x-4.29x. An equal-WALL-CLOCK arm (--opp-sims, harness
#   5ca3e70) is a SEPARATE cell and the one that decides deployment.
#
# READ-OUT (pre-registered here, before the run):
#   PROMOTE-ELIGIBLE only if the fresh band reproduces a positive effect.
#   A tie or reversal returns the thread to the analyzer pivot per CL-067's
#   next-test field. Champion + governance/PRODUCTION.yaml stay UNTOUCHED either
#   way until Joshua rules on the combined evidence. Report BOTH statistics
#   (winrate z AND deck-paired margin z) -- reporting only the one that clears
#   is how the three overturned findings got their start.
# ============================================================================
set -euo pipefail
REPO=/home/doctor/projects/carcassone
CKPT=${CKPT:-/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt}
OUT_ROOT=${OUT_ROOT:-/mnt/c/carc-shared/distill_strong_20260723}
BAND=${BAND:-56000000000}
N=${N:-400}

# --- orch operating point: FILL FROM THE PRE-FLIGHT VERDICT before running ---
# Gate ran OW=28 ORCH_FWD=2 ORCH_MAX_BATCH=16 (mb<W => 57% round coverage) with
# the server's libtorch pool unpinned (carc-orch 2578% vs workers 364%).
OW=${OW:-28}
ORCH_FWD=${ORCH_FWD:-2}
ORCH_MAX_BATCH=${ORCH_MAX_BATCH:-$OW}   # keep mb >= W (see w_ladder header)
SERVER_OMP=${SERVER_OMP:-1}             # pin the SERVER's pool; 0 = gate's behaviour

[ -f "$CKPT" ] || { echo "FATAL: ckpt missing: $CKPT" >&2; exit 1; }
if pgrep -f 'gen_fair_distil[l]' >/dev/null; then
  echo "FATAL: gen running — do not steal its cores" >&2; exit 1
fi
if [ "$ORCH_MAX_BATCH" -lt "$OW" ]; then
  echo "WARN: max_batch ($ORCH_MAX_BATCH) < W ($OW) — the server cannot coalesce" >&2
  echo "      one round of workers into a single forward. See w_ladder header." >&2
fi
cd "$REPO"

ENVS=(CAND_CKPT="$CKPT" OW="$OW" ORCH_FWD="$ORCH_FWD" ORCH_MAX_BATCH="$ORCH_MAX_BATCH")
[ "$SERVER_OMP" = "1" ] && ENVS+=(OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1)

echo "[confirm] band=$BAND n=$N OW=$OW fwd=$ORCH_FWD mb=$ORCH_MAX_BATCH server_omp=$SERVER_OMP"
echo "[confirm] replicating CL-067 at EQUAL SIMS (deployability is a separate cell)"

# --shared-claim so a second box can join the same out-subdir (bundle-sync it first).
env "${ENVS[@]}" nice -n 19 \
  bash scripts/classical_search/fair_net_vs_net_orch.sh \
    --info fair-netprior --opponent fair-champion \
    --exact-k 2 --k-dets 4 --sims 688 \
    --n "$N" --paired --seed-start "$BAND" \
    --out-root "$OUT_ROOT" --out-subdir eval_iter03_vs_champ_CONFIRM_56e9 \
    --shared-claim --no-results-csv
