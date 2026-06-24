#!/usr/bin/env bash
# Part C campaign wrapper: full-game exact-endgame-hybrid eval via carc-orch SHM.
# The exact agent = RoD1 (v2.8) prefix until first TILES decision with k_remaining<=K,
# then exact clairvoyant solve. Opponent (RoD1 / heur@3200 / heur@6400) is also v2.8.
# Clairvoyant exact vs clairvoyant-search opponents = like-for-like information model.
#
#   AGENT_A=exact:2:clair AGENT_B=iter8     N=100 SEED=1909240000 bash scripts/exact_hybrid/run_exact_eval.sh
#   AGENT_A=exact:2:clair AGENT_B=heur@3200 N=100 SEED=1909250000 bash scripts/exact_hybrid/run_exact_eval.sh
set -euo pipefail
cd "$(cd "$(dirname "$0")/../.." && pwd)"          # repo root (cd on line 1 == ssh-safe)

AGENT_A=${AGENT_A:-exact:2:clair}
AGENT_B=${AGENT_B:-iter8}                            # iter8 == the loaded RoD1 net; heur@3200 / heur@6400
N=${N:-100}
SEED=${SEED:?set SEED=<seed-start>}
OW=${OW:-20}                                         # orch workers; exact solver is CPU-side -> keep < threads
OUT_ROOT=${OUT_ROOT:-/mnt/c/carc-shared/exact_endgame_hybrid}
CKPT_ROD1=${CKPT_ROD1:-/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt}

# stable, descriptive subdir (so re-runs resume; manifest carries the full config)
SUB="${AGENT_A//:/_}__vs__${AGENT_B//@/}__n${N}_v28"
echo "[exact-eval] A=$AGENT_A  B=$AGENT_B  n=$N  seed=$SEED  OW=$OW  out=$OUT_ROOT/$SUB"

CKPT="$CKPT_ROD1" OW="$OW" bash scripts/heuristic_v28/v28_handoff_orch.sh \
  --agent-a "$AGENT_A" --agent-b "$AGENT_B" \
  --meeple-k-a 2.0 --meeple-k-b 2.0 \
  --n "$N" --paired --seed-start "$SEED" \
  --shared-claim --out-root "$OUT_ROOT" --out-subdir "$SUB"
