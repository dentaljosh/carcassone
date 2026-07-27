#!/usr/bin/env bash
# ============================================================================
# WIDTH DISCRIMINATOR AT FIXED 11008 — the k4x2752 arm.
#
# This is CL-060's OWN NAMED #1 OPEN TEST, verbatim from its decision field:
#   "SHARP NEXT TESTS, in order of value: (1) k8x1376 vs k4x2752 head-to-head at
#    FIXED 11008 on ONE band, n>=400 paired -- resolves width directly instead of
#    by quadrature difference"
# Open since 2026-07-22. CL-060 could only estimate the width residual by adding
# two independent cells from DIFFERENT seed bands in quadrature: +21.99 +- 18.96,
# z 1.16 -- explicitly UNRESOLVED, and its own counterevidence field says so.
#
# WHY IT IS NEARLY FREE NOW. The blind curve already runs k8x1376 at 11008 on
# band 70e9 (scripts/classical_search/blind_curve_top.sh). Running k4x2752 on the
# SAME band against the SAME sighted opponent makes the two arms DECK-MATCHED, so
# the contrast is a paired double-CRN delta rather than a quadrature difference of
# two independent estimates. That is exactly the design CL-060 asked for.
#
# ⚠️ POWER: CL-060 asked for n>=400. This runs n=200 (100 shared decks) to match
# the rest of the ladder. A deck-matched paired contrast at 100 decks is far
# tighter than the quadrature estimate it replaces, but it is NOT the n>=400 the
# claim requested -- if the delta lands near the 2sigma boundary, say "sharpened,
# not settled" and top up rather than declaring the axis closed.
#
# ⚠️ THIS IS A DIFFERENT QUESTION FROM THE CURVE. The curve rungs use the
# MEASURED-OPTIMAL allocation per budget; this arm deliberately uses the
# SUB-OPTIMAL one at 11008 in order to price the width choice. Do NOT plot it as
# a curve point -- it is the k4 arm of a width contrast, and plotting it would
# put two different allocations at the same x with no marking.
#
# ⚠️ RUN IT ONLY AFTER blind_curve_top.sh HAS FINISHED. Running concurrently
# would have the two jobs contend for the same cores and each other's orch
# servers, corrupting both ETAs and the ms/move columns.
# ============================================================================
set -uo pipefail
cd /home/doctor/projects/carcassone

SHARE=${SHARE:-/mnt/c/carc-shared}
OW=${OW:-16}
N=${N:-200}
BAND=${BAND:-70000000000}
OPP_CKPT=${OPP_CKPT:-$SHARE/rod_v2_flywheel/ckpt/iter_02.pt}
LOG=${LOG:-measurement/classical_search/blind_width11008_$(hostname -s).log}
NAME=blindcurve_k4x2752_11008_vs_sighted_rodv2_b70e9

[ -f "$OPP_CKPT" ] || { echo "FATAL: opponent ckpt missing: $OPP_CKPT" >&2; exit 1; }

if pgrep -f "blind_curve_to[p]" >/dev/null; then
  echo "FATAL: blind_curve_top.sh is still running — refusing to contend for cores." >&2
  echo "       Wait for it to finish, then re-run this." >&2
  exit 1
fi

if [ -f "$SHARE/classical_search/$NAME/summary.json" ]; then
  echo "[$(date +%F_%T)] SKIP $NAME (already complete)" | tee -a "$LOG"; exit 0
fi

echo "[$(date +%F_%T)] === width discriminator k4x2752 @ 11008 START on $(hostname -s) (OW=$OW n=$N) ===" | tee -a "$LOG"

OPP_CKPT="$OPP_CKPT" OW="$OW" nice -n 19 \
  bash scripts/classical_search/bare_net_opp_orch.sh \
    --exact-k 2 --k-dets 4 --sims 2752 \
    --n "$N" --paired --seed-start "$BAND" \
    --out-root "$SHARE/classical_search" --out-subdir "$NAME" \
    --shared-claim --no-results-csv >> "$LOG" 2>&1

echo "[$(date +%F_%T)] === exited rc=$? on $(hostname -s) ===" | tee -a "$LOG"
