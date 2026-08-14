#!/bin/bash
# TIE-TRIGGERED SEARCH ESCALATION — dev ladder driver (DESIGN.md §3, READ_RULE.md).
# Sequential per rules profile (CARCASSONNE_FIX_R9 is import-latched), then the
# dev analyze. Detach with setsid; resume-able (per-position records).
set -u
cd "$(dirname "$0")/../.."     # the repo/worktree root this script lives in
PY=/home/doctor/projects/carcassone/.venv/bin/python
W="${W:-22}"
LOG=measurement/tieescalation_20260814/dev_ladder.log
{
  echo "=== dev ladder start $(date -u +%FT%TZ) W=$W rev=$(git rev-parse --short HEAD) ==="
  for PROF in walled fixed_v1 app_aug2; do
    echo "--- profile $PROF ---"
    nice -n 19 "$PY" scripts/tiletie/escalation_ladder.py \
      --search --profile "$PROF" --slice dev --workers "$W"
    echo "--- profile $PROF rc=$? ---"
  done
  "$PY" scripts/tiletie/escalation_ladder.py --analyze --slice dev
  echo "=== dev ladder done $(date -u +%FT%TZ) ==="
  touch measurement/tieescalation_20260814/DONE_DEV_LADDER
} >> "$LOG" 2>&1
