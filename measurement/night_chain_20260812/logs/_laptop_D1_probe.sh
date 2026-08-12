cd /home/doctor/projects/carcassone || exit 1
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1
mkdir -p /mnt/carc-shared/night_chain_20260812
/home/doctor/projects/carcassone/.venv/bin/python \
  /home/doctor/projects/carcassone/scripts/classical_search/chain_capability_probe.py \
  --require denial --doses "1.0,4.0" --size-min 5 \
  --open-max 3 --max-cells 4 \
  --cells-out /mnt/carc-shared/night_chain_20260812/d1_cells.laptop.tsv --json-out /mnt/carc-shared/night_chain_20260812/D1_capability_laptop.json
