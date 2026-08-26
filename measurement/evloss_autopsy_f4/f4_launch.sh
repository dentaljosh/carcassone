#!/usr/bin/env bash
# f4_launch.sh — the laptop-side entry point for the F4 out-of-family judge leg.
#
# `cd` is on line 1 by house rule (Claude Code strips inline `cd` from ssh commands), and
# this file is always delivered as `ssh laptop-wsl 'bash -s' < f4_launch.sh` or run by
# absolute path.
#
# It does exactly what run/common.sh does for the rules-profile env — source champ_env.sh,
# then UNSET CARCASSONNE_FIX_R9 (rules_profile.walled.r9_env_expected = False) — and nothing
# else from the R1 launcher, so no R0/R1 stage marker or sentinel is in reach.
#
#   usage:  f4_launch.sh smoke  <W> <HEAD>          synchronous, writes F4_SMOKE_*.json
#           f4_launch.sh run    <W> <RUNG>          DETACHED, writes F4_DONE.json
set -euo pipefail
cd /home/doctor/evloss_autopsy/run/f4

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
SHARE=/mnt/carc-shared/evloss_autopsy_20260824     # laptop spelling of the CIFS share
F4DIR=/home/doctor/evloss_autopsy/run/f4
LOGDIR=$F4DIR/logs
mkdir -p "$LOGDIR"

# ---- the champion leaf env, verbatim from the repo (point, don't copy) -------
# shellcheck disable=SC1091
. "$REPO/scripts/distill_flywheel/champ_env.sh"
# `walled` expects CARCASSONNE_FIX_R9 unset/0.
unset CARCASSONNE_FIX_R9 2>/dev/null || true
export PYTHONUNBUFFERED=1

MODE="${1:?usage: f4_launch.sh smoke|run <W> [HEAD|RUNG]}"
W="${2:?worker count}"

case "$MODE" in
  smoke)
    HEAD="${3:-10}"
    echo "[f4] SMOKE: head=$HEAD W=$W  (synchronous)"
    exec "$PY" -u "$F4DIR/f4_judge_leg.py" \
      --share "$SHARE" --repo "$REPO" --python "$PY" \
      --workers "$W" --legs sib2 --head "$HEAD" --stride \
      --out-root "$SHARE/judge_f4_smoke" 2>&1 | tee "$LOGDIR/f4_smoke.log"
    ;;
  run)
    RUNG="${3:-L1}"
    LOG="$LOGDIR/f4_leg.log"
    echo "[f4] LAUNCH rung=$RUNG W=$W -> $LOG"
    setsid nohup nice -n 19 "$PY" -u "$F4DIR/f4_judge_leg.py" \
      --share "$SHARE" --repo "$REPO" --python "$PY" \
      --workers "$W" --rung "$RUNG" \
      --sentinel "$SHARE/F4_DONE.json" \
      >> "$LOG" 2>&1 < /dev/null &
    disown || true
    echo "[f4] detached pid=$!"
    ;;
  *)
    echo "unknown mode $MODE" >&2; exit 2 ;;
esac
