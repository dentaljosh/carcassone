set -uo pipefail
cd /home/doctor/projects/carcassone
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1
L=/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs
rc_total=0
probe_arm () {   # name size_min edge_min  (rc is FATAL only for the arms we gate on)
  .venv/bin/python scripts/classical_search/chain_capability_probe.py \
    --require opencity --doses 0.5,2.0 --size-min "$2" --edge-min "$3" \
    --json-out "$L/PROBE_opencity_$1.json" > "$L/probe_$1.log" 2>&1
  echo "arm $1 (size_min=$2 edge_min=$3) probe rc=$?"
}
probe_arm A 4 2
probe_arm B 3 2
probe_arm C 6 3
