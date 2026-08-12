#!/bin/bash
# launch_denial_e4_calib.sh — offline dose/threshold CALIBRATION for the targeted-denial term.
#
# WHY: the build smoke found the term barely expresses at the drafted screen doses
# (0/56 plies flipped at dose 0.5, 1/56 at dose 1.0; the predicate fires on only ~2% of
# midgame positions at the default thresholds SIZE_MIN=8 / OPEN_MAX=2). A screen on a term
# that changes ~1% of decisions cannot produce a resolvable elo signal — it would burn a
# deck band and a night of games to measure nothing. So the doses and thresholds are
# calibrated FIRST, on replays of already-banked E4 human-vs-champion games: zero games
# played, no deck band consumed, no elo statistic read.
#
# NOT gate-shopping: the quantity read here is PICK-FLIP RATE (does the term change play at
# all, and where), not strength. The screen's elo statistic is measured later on a fresh
# band of SELF-PLAY decks — a disjoint corpus from this calibration set — and its prereg is
# written after this readout, per the standard census -> screen pattern.
#
# Two arms, because dose and threshold are NOT interchangeable: at a fixed predicate that
# fires on ~2% of positions, no dose can push the flip rate much past ~2%, so if arm A
# saturates low the binding constraint is the THRESHOLD, not the dose.
#   A = default thresholds  (size_min 8, open_max 2)  x doses {1.0, 4.0}
#   B = loosened thresholds (size_min 5, open_max 3)  x doses {1.0, 4.0}
#
# carc_rs: the venv's installed build PREDATES the denial term, so both arms run against the
# freshly-built denial-capable wheel unpacked in the scratchpad, via PYTHONPATH. This is
# deliberate — installing into the shared venv while another agent is mid-build against it
# would swap the extension module under its tests.
set -u

REPO=/home/doctor/projects/carcassone
RS=/tmp/claude-1000/-home-doctor-projects-carcassone/c0b61ee1-6d62-430c-ba1e-fd232f3cbd5a/scratchpad/carc_rs_denial
OUT=$REPO/measurement/denial_screen_20260811
PY=$REPO/.venv/bin/python

export PYTHONPATH="$RS:$REPO/src:$REPO/engine"

mkdir -p "$OUT/calib_A_default" "$OUT/calib_B_loose" "$OUT/logs"

cd "$REPO" || exit 1

nohup nice -n 19 "$PY" scripts/classical_search/denial_e4_replay.py \
  -o "$OUT/calib_A_default" --doses 1.0,4.0 --size-min 8 --open-max 2 \
  > "$OUT/logs/calib_A.log" 2>&1 < /dev/null &
disown

nohup nice -n 19 "$PY" scripts/classical_search/denial_e4_replay.py \
  -o "$OUT/calib_B_loose" --doses 1.0,4.0 --size-min 5 --open-max 3 \
  > "$OUT/logs/calib_B.log" 2>&1 < /dev/null &
disown

echo "launched calib A (default thresholds) + B (loosened) — logs in $OUT/logs/"
