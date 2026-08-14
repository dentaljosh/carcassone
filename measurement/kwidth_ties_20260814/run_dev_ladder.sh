#!/bin/bash
# k-WIDTH / DETERMINIZATION AT TIED PLIES — dev ladder driver (DESIGN.md §3, READ_RULE.md).
# Sequential per rules profile (CARCASSONNE_FIX_R9 is import-latched), then the
# dev analyze. Detach with setsid; resume-able (per-position records), so each
# profile gets up to 3 attempts — a re-attempt re-searches ONLY the positions
# whose record is missing or incomplete.
set -u
cd "$(dirname "$0")/../.."     # the repo/worktree root this script lives in
PY=/home/doctor/projects/carcassone/.venv/bin/python
W="${W:-22}"
DIR=measurement/kwidth_ties_20260814
LOG=$DIR/dev_ladder.log
{
  echo "=== kwidth dev ladder start $(date -u +%FT%TZ) W=$W rev=$(git rev-parse --short HEAD) host=$(hostname) ==="
  for PROF in walled fixed_v1 app_aug2; do
    for TRY in 1 2 3; do
      echo "--- profile $PROF attempt $TRY ---"
      nice -n 19 "$PY" scripts/tiletie/kwidth_ladder.py \
        --search --profile "$PROF" --workers "$W"
      RC=$?
      echo "--- profile $PROF attempt $TRY rc=$RC ---"
      [ "$RC" -eq 0 ] && break
    done
  done
  "$PY" scripts/tiletie/kwidth_ladder.py --analyze
  echo "=== kwidth dev ladder done $(date -u +%FT%TZ) ==="
  touch "$DIR/DONE_DEV_LADDER"
} >> "$LOG" 2>&1
