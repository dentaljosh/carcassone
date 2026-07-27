#!/usr/bin/env bash
cd /home/doctor/projects/carcassone
export CARCASSONNE_TT_CAP=200000
exec nice -n 19 .venv/bin/python -u \
    scripts/classical_search/eval_fair_puct.py \
    --info fair --opponent fair-champion \
    --exact-k 2 --k-dets 8 --sims 1376 --opp-k-dets 4 --opp-sims 688 \
    --n 400 --paired --seed-start 32000000000 --workers 16 \
    --out-root /mnt/c/carc-shared/classical_search \
    --out-subdir cl060_h2h_k8x1376_vs_deploy_k4x688 --shared-claim --no-results-csv
