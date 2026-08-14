#!/bin/bash
# TIE-TRIGGERED SEARCH ESCALATION — ONE-SHOT holdout confirm (READ_RULE §4).
# Licensed ONLY by a dev E-FUND-DEV; the analyzer itself refuses otherwise.
# Usage: NAMED_RUNG=<sims/det> bash run_holdout_confirm.sh
set -u
cd "$(dirname "$0")/../.."
PY=/home/doctor/projects/carcassone/.venv/bin/python
W="${W:-22}"
: "${NAMED_RUNG:?set NAMED_RUNG to the dev-named rung (sims/det)}"
LOG=measurement/tieescalation_20260814/holdout_confirm.log
{
  echo "=== holdout confirm start $(date -u +%FT%TZ) named=$NAMED_RUNG W=$W rev=$(git rev-parse --short HEAD) ==="
  # guard: the dev readout must name this rung (the analyzer re-checks too)
  "$PY" - "$NAMED_RUNG" <<'EOF'
import json, sys
v = json.load(open("measurement/tieescalation_20260814/LADDER_READOUT.json"))["verdict"]
assert v.get("branch") == "E-FUND-DEV" and int(v.get("named_rung", -1)) == int(sys.argv[1]), v
EOF
  [ $? -eq 0 ] || { echo "GUARD FAILED — no E-FUND-DEV naming $NAMED_RUNG"; exit 3; }
  for PROF in walled fixed_v1 app_aug2; do
    echo "--- profile $PROF ---"
    nice -n 19 "$PY" scripts/tiletie/escalation_ladder.py \
      --search --profile "$PROF" --slice holdout --workers "$W" \
      --rungs "1376,$NAMED_RUNG"
    echo "--- profile $PROF rc=$? ---"
  done
  "$PY" scripts/tiletie/escalation_ladder.py --analyze --slice holdout \
    --named-rung "$NAMED_RUNG"
  echo "=== holdout confirm done $(date -u +%FT%TZ) ==="
  touch measurement/tieescalation_20260814/DONE_HOLDOUT_CONFIRM
} >> "$LOG" 2>&1
