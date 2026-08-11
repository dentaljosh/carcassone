#!/bin/bash
cd /home/doctor/projects/carcassone
export CARC_SRC_ROOT=/home/doctor/projects/carc-pinned-c72053a/src
export CARC_REQUIRE_SRC_ROOT=/home/doctor/projects/carc-pinned-c72053a/src
D=/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9
exec nice -n 19 .venv/bin/python scripts/measurement_infra/move_agreement_probe.py \
  --roots $D/roots.jsonl --out-dir $D/verify --n 40 \
  --replicates 1 --salt-base 1 --workers 4 --wall-cap-secs 7200 \
  --verify-bit-exact --verify-agent-parity --tag VERIFY-subset
