#!/usr/bin/env bash
# Deeper-search ruler ladder: heur@N_v2.8 vs heur@M_v2.8 paired full-game eval.
# Pure heuristic MCTS — NO net, NO orchestrator (HeuristicMCTS never touches the net),
# so this is plain CPU multiprocessing. v2.8 leaf = v2.7 base (set at import) + flat
# meeple_k=2.0 (--meeple-k-a/-b 2.0). Paired decks, both seats. Resumable (stable subdir).
# Emits WDL / winrate / winrate-Elo / paired score margin / paired_z + manifest.json.
#
#   AGENT_A=heur@6400 AGENT_B=heur@3200 N=400 SEED=1924100000 W=16 bash scripts/deeper_search/run_heur_ladder.sh
#   AGENT_A=heur@12800 AGENT_B=heur@6400 N=200 SEED=1924200000 W=16 bash scripts/deeper_search/run_heur_ladder.sh
set -euo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

cd "$(cd "$(dirname "$0")/../.." && pwd)"          # repo root (cd on line 1 == ssh-safe)

AGENT_A=${AGENT_A:?set AGENT_A=heur@N}
AGENT_B=${AGENT_B:?set AGENT_B=heur@M}
N=${N:-100}
SEED=${SEED:?set SEED=<seed-start>}
W=${W:-16}                                          # heur is RAM-light (~0.6GB/worker baseline)
OUT_ROOT=${OUT_ROOT:-/mnt/c/carc-shared/deeper_search_ruler}
# inert placeholder ckpt (argparse-required but NEVER loaded for heur-vs-heur)
CKPT=${CKPT:-/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt}
CLAIM=${CLAIM:-1}                                   # shared-claim work-stealing across boxes

SUB="${AGENT_A//@/}__vs__${AGENT_B//@/}__n${N}_v28"
CLAIM_FLAG=""; [ "$CLAIM" = "1" ] && CLAIM_FLAG="--shared-claim"
echo "[heur-ladder] A=$AGENT_A B=$AGENT_B n=$N seed=$SEED W=$W out=$OUT_ROOT/$SUB"

exec nice -n 19 .venv/bin/python -u scripts/level2/eval_hybrid_handoff.py \
  --agent-a "$AGENT_A" --agent-b "$AGENT_B" \
  --meeple-k-a 2.0 --meeple-k-b 2.0 \
  --ckpt "$CKPT" --device cpu \
  --n "$N" --paired --seed-start "$SEED" --workers "$W" \
  $CLAIM_FLAG \
  --out-root "$OUT_ROOT" --out-subdir "$SUB"
