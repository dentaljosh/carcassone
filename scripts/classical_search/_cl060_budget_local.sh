#!/usr/bin/env bash
# CL-060 DECOMPOSITION CELL — isolate BUDGET at fixed width.
#   candidate: k_dets=4 x sims=2752  (total 11008)
#   opponent : deploy champion k_dets=4 x sims=688 (total 2752)
# Sibling cell to cl060_h2h_k8x1376_vs_deploy_k4x688 (which varied width AND budget).
# LOCAL box (5900XT), W16, share = /mnt/c/carc-shared
cd /home/doctor/projects/carcassone
export CARCASSONNE_TT_CAP=200000
exec nice -n 19 .venv/bin/python -u \
    scripts/classical_search/eval_fair_puct.py \
    --info fair --opponent fair-champion \
    --exact-k 2 --k-dets 4 --sims 2752 --opp-k-dets 4 --opp-sims 688 \
    --n 400 --paired --seed-start 44000000000 --workers 16 \
    --out-root /mnt/c/carc-shared/classical_search \
    --out-subdir cl060_budget_k4x2752_vs_deploy_k4x688 \
    --shared-claim --no-results-csv
