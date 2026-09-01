#!/usr/bin/env bash
# Deployed-config s/move probe at 22016 — the "re-measure owed" by PRODUCTION.yaml's
# measured_s_per_move stale note (2026-08-30), run on the flattening+A+L2 wheel
# (sha256 c1250fe2, installed 2026-09-01).
#
# CONDITIONS (the informal roll-in probe was search-only/no-R9/n=1 and was NOT stamped):
#   - arbiter ARMED BOTH SEATS at the full deployed dict (B=64/J=4/argmax/
#     tiearb2-deploy-v1/eps 0.0/phase_gate all — constants verbatim from
#     measurement/fpu_h2h_r2_prep/WORKERS.conf, the deployed spec of record)
#   - CARCASSONNE_FIX_R9=1 exported (env-latched at import)
#   - fixed_v1, backend rust, k16x1376=22016, W=1 sequential (clean per-move timing),
#     nice -n 19, EXCLUSIVE tenant (census the box first; no agents, no other runs)
#   - n=3 games, throwaway seeds 900000000010..12 (--allow-selfplay-seeds; NOT a band)
# READ: champ_prefix_ms_per_move = the CANDIDATE side (field-name trap memory);
#   report per-game values AND the mean; n=3 prices no distribution — this is a
#   deploy-cost figure, not a strength cell.
set -euo pipefail
cd /home/doctor/projects/carcassone
export CARCASSONNE_FIX_R9=1
OUT=measurement/wheel_rollin_20260901
nice -n 19 .venv/bin/python scripts/classical_search/eval_fair_puct.py \
  --info fair --opponent fair-champion --backend rust \
  --k-dets 16 --sims 1376 \
  --n 3 --workers 1 --seed-start 900000000010 --allow-selfplay-seeds \
  --rules-profile fixed_v1 \
  --cand-tiearb-enabled --cand-tiearb-b 64 --cand-tiearb-j 4 \
  --cand-tiearb-mode argmax --cand-tiearb-salt tiearb2-deploy-v1 \
  --cand-tiearb-eps 0.0 --cand-tiearb-phase-gate all \
  --opp-tiearb-enabled --opp-tiearb-b 64 --opp-tiearb-j 4 \
  --opp-tiearb-mode argmax --opp-tiearb-salt tiearb2-deploy-v1 \
  --opp-tiearb-eps 0.0 --opp-tiearb-phase-gate all \
  --out-root "$OUT" --out-subdir bench22016_arbon --no-results-csv
touch "$OUT/BENCH_DONE"
echo "bench22016_deployed: done"
