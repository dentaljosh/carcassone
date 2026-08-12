cd /home/doctor/projects/carcassone || exit 1
/home/doctor/projects/carcassone/.venv/bin/python \
  /home/doctor/projects/carcassone/scripts/classical_search/chain_capability_probe.py \
  --require simsplit --harness /home/doctor/projects/carcassone/scripts/classical_search/eval_fair_puct.py \
  --sims-tile 2408 --sims-meeple 344 --sims 1376
