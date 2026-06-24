#!/usr/bin/env bash
# Part C: learned agent (RoD_iter_01 / iter_08) vs the deeper heuristic ruler (heur@N_v2.8),
# full-game paired both-seats, via the carc-orch SHM orchestrator at HIGH W (the net forwards
# are batched on one GPU context; the heur@N search runs CPU-side per worker). v2.8 leaf on
# BOTH sides (--meeple-k 2.0). Clairvoyant-vs-clairvoyant information model (both descend the
# true deck) — like-for-like.
#
#   CKPT=/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt RULER=heur@6400 N=200 \
#       SEED=1924300000 OW=28 bash scripts/deeper_search/run_neural_vs_ruler.sh
set -euo pipefail
cd "$(cd "$(dirname "$0")/../.." && pwd)"          # repo root (cd on line 1 == ssh-safe)

CKPT=${CKPT:-/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt}
RULER=${RULER:-heur@6400}
N=${N:-200}
SEED=${SEED:?set SEED=<seed-start>}
OW=${OW:-28}                                        # high orch W (rust orch); heur CPU-bound -> keep <= ~threads
TAG=${TAG:-rod1}                                    # label for the net agent (rod1 / iter08)
OUT_ROOT=${OUT_ROOT:-/mnt/c/carc-shared/deeper_search_ruler}

SUB="${TAG}__vs__${RULER//@/}__n${N}_v28"
echo "[neural-vs-ruler] net=$TAG ($CKPT)  ruler=$RULER  n=$N seed=$SEED OW=$OW  out=$OUT_ROOT/$SUB"

CKPT="$CKPT" OW="$OW" bash scripts/heuristic_v28/v28_handoff_orch.sh \
  --agent-a iter8 --agent-b "$RULER" \
  --meeple-k-a 2.0 --meeple-k-b 2.0 \
  --n "$N" --paired --seed-start "$SEED" \
  --shared-claim --out-root "$OUT_ROOT" --out-subdir "$SUB"
