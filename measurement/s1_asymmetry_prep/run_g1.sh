#!/usr/bin/env bash
# S1 GATE G1 — EXPRESSION. 0 games, 0 band, 0 results.csv rows.
#
# Read rule of record: measurement/s1_asymmetry_prep/READ_RULE_G1.md, committed
# BEFORE this script ever produced a number. Design: DESIGN.md §6.2.
#
# WHAT THIS RUNS: the banked E4 corpus replayed at the CURRENT deploy budget
# (k16 x 1376 = 22016), champion vs four scope='opp' dose rungs, CRN across arms.
# Two statistics: E1 (root pick-flip rate) and E2 (root visit-distribution TV).
#
#   ./run_g1.sh              # the full pass  (W defaults to 22)
#   W=30 ./run_g1.sh         # local box at W30
#   SMOKE=1 ./run_g1.sh      # the wiring smoke: 1 archive, 6 plies, 1 worker
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached jobs:
#   setsid nohup ./run_g1.sh > g1.log 2>&1 < /dev/null & disown
#
# ⚠️ EXCLUSIVE TENANCY for the full pass. This is a saturated W-parallel job on a
# DRAM-bound box; a single niced co-tenant has been measured to inflate such a
# run ~1.8x/move. Census by FULL ARGS (`ps -eo args`), never `-C python`.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${PY:-$REPO/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  # A git WORKTREE has no .venv of its own. Say so with the fix rather than
  # letting `nice` emit a bare "No such file or directory".
  echo "[g1] FATAL: no interpreter at $PY" >&2
  echo "[g1]   In a worktree, point PY at the main tree's venv and put the" >&2
  echo "[g1]   worktree ahead of it on PYTHONPATH, e.g.:" >&2
  echo "[g1]     PY=/home/doctor/projects/carcassone/.venv/bin/python \\" >&2
  echo "[g1]     PYTHONPATH=<shadow-wheel>:$REPO/src:$REPO/engine ./run_g1.sh" >&2
  exit 2
fi
W="${W:-22}"
STAMP="${STAMP:-$(date +%Y%m%d)}"

if [[ "${SMOKE:-0}" == "1" ]]; then
  OUT="${OUT:-$REPO/measurement/s1_asymmetry_prep/g1_smoke_${STAMP}}"
  EXTRA=(--limit-games 1 --limit-plies "${SMOKE_PLIES:-6}")
  W=1
else
  OUT="${OUT:-$REPO/measurement/s1_asymmetry_prep/g1_${STAMP}}"
  EXTRA=()
fi

# The four frozen rungs (READ_RULE_G1 §2.1). Mask 31, scope opp, all four.
ARMS=(
  --arm s1_d0p25:0.25:31:opp
  --arm s1_d0p5:0.5:31:opp
  --arm s1_d1p0:1.0:31:opp
  --arm s1_d2p0:2.0:31:opp
)

echo "[g1] repo=$REPO out=$OUT workers=$W smoke=${SMOKE:-0}"
echo "[g1] read rule: measurement/s1_asymmetry_prep/READ_RULE_G1.md"
mkdir -p "$OUT"

# FREEZE LATCH. Each archive is graded in its own SUBPROCESS that re-imports
# `carcassonne_ai` and `carc_rs` FROM DISK, so a source edit or a wheel
# reinstall mid-run silently produces MIXED-REV archives inside one out-dir.
# The sentinel makes main-tree commits refuse while this is live; the trap
# clears it on any exit path, including SIGINT/SIGTERM.
LATCH="$OUT/RUN_LIVE.json"
cleanup() { rm -f "$LATCH"; }
trap cleanup EXIT INT TERM
printf '{"run":"s1_g1","out":"%s","pid":%d,"started":"%s","workers":%s}\n' \
  "$OUT" "$$" "$(date -Is)" "$W" > "$LATCH"

# nice 19: yields to interactive use, per the house default for long workers.
# NOT `exec` — exec would replace this shell and the trap would never fire.
nice -n 19 "$PY" -u "$REPO/scripts/classical_search/jrules_priors_e4_replay.py" \
  --archive-dir "$REPO/measurement/e4_games" \
  -o "$OUT" \
  "${ARMS[@]}" \
  --sims 1376 --k-dets 16 \
  --seed 12345 \
  --workers "$W" \
  "${EXTRA[@]}"
rc=$?
echo "[g1] instrument exited rc=$rc; RUN_LIVE cleared"
exit "$rc"
