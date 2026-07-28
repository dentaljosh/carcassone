#!/bin/bash
cd /home/doctor/projects/carcassone
export CARC_SRC_ROOT=/home/doctor/projects/carc-pinned-c72053a/src
export CARC_REQUIRE_SRC_ROOT=/home/doctor/projects/carc-pinned-c72053a/src
D=/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9
exec nice -n 19 .venv/bin/python scripts/measurement_infra/move_agreement_probe.py \
  --roots $D/roots.jsonl --out-dir $D/records \
  --replicates 3 --salt-base 1 --workers 16 --wall-cap-secs 3600 \
  --tag MAIN-local-5900XT
