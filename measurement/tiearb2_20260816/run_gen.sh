#!/usr/bin/env bash
# run_gen.sh — PHASE 1: fresh champion self-play games (CORPUS SUBSTRATE ONLY).
#
# These games are corpus material for mining tied tile plies. They are NOT a
# strength evaluation: 0 strength games, no band, no experiments/results.csv row.
#
# Generation config is MATCHED VERBATIM to the existing champ_action_logs corpus
# (measurement/champ_action_logs/CORPUS_MANIFEST.json) so the fresh roots are drawn
# from the SAME position distribution as the spent corpus's self-play stratum:
#   FairHeuristicPriorAgent, k_dets=4 x sims=688 (=2752, PRODUCTION.yaml fair_deploy),
#   exact_endgame K<=2, leaf v2_9_2_Bmild_cap8_curve125, rules_profile=walled.
# ONLY the deck-seed band differs -> ROOT-LEVEL DISJOINTNESS BY CONSTRUCTION.
#
#   old corpus band : 28000000000 .. 28000000449   (449 games, consumed)
#   old "_b" leg    : 28000010000 ..               (16 orphan claims, no shards)
#   THIS RUN        : 28100000000 .. 28100000849   (850 games)  <-- disjoint
#
# Usage:  ./run_gen.sh local     (or)   ./run_gen.sh laptop-side
# Both boxes run the SAME command against the SAME --out on the share with
# --shared-claim O_EXCL work-stealing, so a slow box simply claims fewer games.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/WORKERS.conf"

BOX="${1:-local}"
case "$BOX" in
  local)       W="$W_LOCAL";  REPO="$REPO_LOCAL";  SHARE="$SHARE_LOCAL" ;;
  laptop-side) W="$W_LAPTOP"; REPO="$REPO_REMOTE"; SHARE="$SHARE_REMOTE" ;;
  *) echo "usage: $0 {local|laptop-side}" >&2; exit 2 ;;
esac

OUT="$SHARE/$RUN_ID/gen"
GAMES=850
SEED_START=28100000000

mkdir -p "$OUT"
# shellcheck disable=SC1091
. "$REPO/scripts/distill_flywheel/champ_env.sh"

echo "[gen] box=$BOX W=$W out=$OUT games=$GAMES seed_start=$SEED_START"

exec nice -n "$NICE" "$REPO/.venv/bin/python" -u \
  "$REPO/scripts/distill_flywheel/gen_fair_distill.py" \
  --games "$GAMES" \
  --k-dets 4 --sims 688 \
  --exact-endgame --exact-max-k 2 \
  --rules-profile walled \
  --workers "$W" \
  --seed-start "$SEED_START" \
  --log-actions --actions-only \
  --out "$OUT" \
  --shared-claim
