#!/usr/bin/env bash
# K=4 solver-grounded regret probe on the MULTI-SOURCE suite, clairvoyant + alpha-beta.
#
# Scores each agent's move (iter8 / heur@800 / heur@3200 / greedy) against the EXACT
# clairvoyant optimum at K=4 (alpha-beta solver; perfect-information labels). The
# multi-source suite (gen_endgame_multisource.py) lets the aggregator check
# selection bias + by-source robustness (aggregate_k4_probe.py).
#
# Clairvoyant (perfect-info) ONLY here — marginalized (bag-expectation) is a
# separate, much harder solve (no alpha-beta; tractability tested separately).
# Node-budgeted = reproducible "unsolved"; shared-claim => can split across boxes.
#
# Usage:
#   SHARE=/mnt/c/carc-shared SUITE=measurement/level2/l23_k4_multisource.jsonl \
#     W=12 BUDGET=2000000 KS=4 bash scripts/level2/run_k4_probe.sh [--shared-claim]
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-python}
SHARE=${SHARE:?set SHARE=<share mount>}
SUITE=${SUITE:-measurement/level2/l23_k4_multisource.jsonl}
CKPT=${CKPT:-$SHARE/flywheel_residual_attempt2/ckpt/iter8.pt}
OUT=${OUT:-$SHARE/l23_k4_probe}
W=${W:-12}
BUDGET=${BUDGET:-2000000}          # AB K=4 solved at ~130-261k nodes; 2M = generous headroom
KS=${KS:-4}
AGENTS=${AGENTS:-"iter8 heur@800 heur@3200 greedy"}
MODES=${MODES:-clairvoyant}        # perfect-info labels; alpha-beta applies
EXTRA="${1:-}"
HOST=${HOST:-$(hostname)}

cd "$REPO"
echo "[k4-probe] suite=$SUITE KS=$KS agents=[$AGENTS] modes=$MODES budget=$BUDGET W=$W out=$OUT host=$HOST"
nice -n 19 "$PY" -u scripts/level2/endgame_regret.py \
  --suite "$SUITE" --out-root "$OUT" --ckpt "$CKPT" \
  --ks $KS --workers "$W" --budget "$BUDGET" \
  --modes $MODES --alphabeta --agents $AGENTS \
  --claim-host "$HOST" $EXTRA
echo "[k4-probe] done -> aggregate: python scripts/level2/aggregate_k4_probe.py $OUT"
