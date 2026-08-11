#!/usr/bin/env bash
# v2.10 Track A reweight screen (docs/V210_LEAF_SPEC_2026-07-04.md, grid:
# measurement/v210_leaf/TRACK_A_GRID.md). One solver pass, baseline + 19 variants,
# 1,119 exact K<=2 marginalized roots, solve-once-score-many.
set -euo pipefail
cd /home/doctor/projects/carcassone

C075="-8,-4,-1,0,1.5,2.25,3,3.75"
C125="-8,-4,-1,0,2.5,3.75,5,6.25"

exec nice -n 19 .venv/bin/python scripts/canonical_az/solver_score.py \
  --max-k 2 --workers "${1:-12}" \
  --leaf-variant 'cap6:{"V25_CAP":"6"}' \
  --leaf-variant 'cap10:{"V25_CAP":"10"}' \
  --leaf-variant 'cap12:{"V25_CAP":"12"}' \
  --leaf-variant "curve075:{\"V29_MEEPLE_CURVE\":\"$C075\"}" \
  --leaf-variant "curve125:{\"V29_MEEPLE_CURVE\":\"$C125\"}" \
  --leaf-variant 'flatk15:{"V29_MEEPLE_CURVE":"","V25_MEEPLE_K":"1.5"}' \
  --leaf-variant 'flatk20:{"V29_MEEPLE_CURVE":"","V25_MEEPLE_K":"2.0"}' \
  --leaf-variant 'flatk25:{"V29_MEEPLE_CURVE":"","V25_MEEPLE_K":"2.5"}' \
  --leaf-variant 'drop3:{"V25_DROP_THREE_OPEN":"1"}' \
  --leaf-variant "cap6_curve075:{\"V25_CAP\":\"6\",\"V29_MEEPLE_CURVE\":\"$C075\"}" \
  --leaf-variant "cap6_curve125:{\"V25_CAP\":\"6\",\"V29_MEEPLE_CURVE\":\"$C125\"}" \
  --leaf-variant "cap10_curve075:{\"V25_CAP\":\"10\",\"V29_MEEPLE_CURVE\":\"$C075\"}" \
  --leaf-variant "cap10_curve125:{\"V25_CAP\":\"10\",\"V29_MEEPLE_CURVE\":\"$C125\"}" \
  --leaf-variant "cap12_curve075:{\"V25_CAP\":\"12\",\"V29_MEEPLE_CURVE\":\"$C075\"}" \
  --leaf-variant "cap12_curve125:{\"V25_CAP\":\"12\",\"V29_MEEPLE_CURVE\":\"$C125\"}" \
  --leaf-variant 'drop3_cap6:{"V25_DROP_THREE_OPEN":"1","V25_CAP":"6"}' \
  --leaf-variant 'drop3_cap10:{"V25_DROP_THREE_OPEN":"1","V25_CAP":"10"}' \
  --leaf-variant "drop3_curve075:{\"V25_DROP_THREE_OPEN\":\"1\",\"V29_MEEPLE_CURVE\":\"$C075\"}" \
  --leaf-variant "drop3_curve125:{\"V25_DROP_THREE_OPEN\":\"1\",\"V29_MEEPLE_CURVE\":\"$C125\"}" \
  --out measurement/v210_leaf/screen_trackA.json
