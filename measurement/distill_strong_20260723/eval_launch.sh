#!/usr/bin/env bash
# ============================================================================
# DISTILL-STRONG-TEACHER — post-gen EVAL launcher (DRAFT, written 2026-07-23 while
# gen was running; DO NOT RUN until gen iter_03 completes and both boxes are free).
#
# Spec: docs/DISTILL_STRONG_TEACHER_SPEC_2026-07-23.md §shape step 3.
# Candidate = the distilled net (policy priors + FROZEN curve125 leaf, value severed)
# via eval_fair_puct.py --info fair-netprior, GPU-batched through the carc-orch SHM
# wrapper (fair_net_vs_net_orch.sh). ⚠️ Wrapper traps (its header, read before editing):
#   - do NOT `source champ_env.sh` first (leaf env injected in-process; a pre-set curve
#     env would move the ruler)
#   - per-side n_ch/n_scalar peeked from the ckpt (sighted 81ch/42) — automatic
#   - OPP_K_DETS/OPP_SIMS are ENV VARS to the wrapper, not CLI flags
#
# CELL 1 (PRIMARY, the gate): net-priors at DEPLOY budget vs the deploy champion.
#   Win condition: beats champ, deck-paired n=400, production depth. Full retention
#   ~+40; partial +20 still a production upgrade; tie => thread closes (analyzer pivot).
# CELL 2 (SECONDARY, retention %): same candidate vs the TEACHER config k8x1376.
#   n=200 first (teacher side is 4x cost, ~1400 s/game); extend only if decision-relevant.
#
# Seed bands: 52e9 (cell 1), 53e9 (cell 2) — fresh, disjoint from 44/46/48/50e9.
# ============================================================================
set -euo pipefail
REPO=/home/doctor/projects/carcassone
CKPT=${CKPT:-/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt}
OUT_ROOT=${OUT_ROOT:-/mnt/c/carc-shared/distill_strong_20260723}
CELL=${1:?usage: eval_launch.sh <champ|teacher>}
[ -f "$CKPT" ] || { echo "FATAL: candidate ckpt missing: $CKPT" >&2; exit 1; }
if pgrep -f 'gen_fair_distil[l]' >/dev/null; then
  echo "FATAL: gen still running — do not steal its cores" >&2; exit 1
fi
cd "$REPO"

case "$CELL" in
  champ)   # PRIMARY: deploy budget both sides, n=400 paired
    CAND_CKPT="$CKPT" OW=${OW:-28} nice -n 19 \
      bash scripts/classical_search/fair_net_vs_net_orch.sh \
        --info fair-netprior --opponent fair-champion \
        --exact-k 2 --k-dets 4 --sims 688 \
        --n 400 --paired --seed-start 52000000000 \
        --out-root "$OUT_ROOT" --out-subdir eval_iter03_vs_champ_deploy \
        --no-results-csv
    ;;
  teacher) # SECONDARY: candidate at deploy budget vs the k8x1376 teacher, n=200
    CAND_CKPT="$CKPT" OPP_K_DETS=8 OPP_SIMS=1376 OW=${OW:-16} nice -n 19 \
      bash scripts/classical_search/fair_net_vs_net_orch.sh \
        --info fair-netprior --opponent fair-champion \
        --exact-k 2 --k-dets 4 --sims 688 \
        --n 200 --paired --seed-start 53000000000 \
        --out-root "$OUT_ROOT" --out-subdir eval_iter03_vs_teacher \
        --no-results-csv
    ;;
  *) echo "bad cell '$CELL' (champ|teacher)" >&2; exit 1 ;;
esac
