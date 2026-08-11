#!/usr/bin/env bash
# F1 release-integrity audit runner. Runs the semantic/property suite (tests/release/) +
# the adversarial state replay (scripts/release/replay_audit.py) and writes a machine-
# generated REPORT.md under measurement/release_audit_<date>/. Re-run after ANY leaf /
# search / config change that touches the champion — cheap by design (CPU-only, net-free).
#
# Usage:
#   scripts/release_audit.sh                 # smoke: full property suite + ~2k-state replay
#   REPLAY_GAMES=700 REPLAY_SYNTH=200 REPLAY_WORKERS=14 scripts/release_audit.sh   # full replay
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${CARC_PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || PY="python3"
DATE="$(date +%Y%m%d)"
OUT="$REPO/measurement/release_audit_${DATE}"
mkdir -p "$OUT"

# Production leaf shape (cap8 frozen-v2.9 base; the factory injects curve125). The three
# audit switches (WINDOW_STRICT / CACHE_COLLIDE_CHECK / WINDOW_AUDIT) are NOT exported
# globally: they change get_valid_moves behavior, and the property suite plays random games
# (and sets those flags per-test via monkeypatch where it needs them). replay_audit.py sets
# them itself (os.environ.setdefault) so ONLY the replay step runs strict. nice -n 19: shared box.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE="-8,-4,-1,0,2,3,4,5" CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_V25_VALUE_BLEND=0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_USE_CY_REPR=1
export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CARCASSONNE_CLIP_TRACE_DIR="$OUT/collisions"   # built-in collision detector output (replay step)
mkdir -p "$CARCASSONNE_CLIP_TRACE_DIR"

REPLAY_GAMES="${REPLAY_GAMES:-15}"
REPLAY_SYNTH="${REPLAY_SYNTH:-5}"
REPLAY_WORKERS="${REPLAY_WORKERS:-1}"

echo "== F1 release audit ($DATE) -> $OUT =="

# 1. semantic / property suite ------------------------------------------------
echo "[1/2] semantic/property suite (tests/release/) ..."
nice -n 19 "$PY" -m pytest "$REPO/tests/release/" -q -p no:cacheprovider \
    --junit-xml="$OUT/pytest.xml" > "$OUT/pytest.log" 2>&1
PYTEST_RC=$?
tr '\r' '\n' < "$OUT/pytest.log" | tail -2

# 2. adversarial state replay -------------------------------------------------
echo "[2/2] adversarial state replay (strict window + key collisions + manifest drift) ..."
nice -n 19 "$PY" "$REPO/scripts/release/replay_audit.py" \
    --games "$REPLAY_GAMES" --synthetic "$REPLAY_SYNTH" --workers "$REPLAY_WORKERS" \
    --out "$OUT/replay.json" > "$OUT/replay.log" 2>&1
REPLAY_RC=$?
tail -1 "$OUT/replay.log"

# 3. machine-generated REPORT.md ---------------------------------------------
CARC_REPORT_OUT="$OUT" CARC_REPORT_PYTEST_RC="$PYTEST_RC" CARC_REPORT_REPLAY_RC="$REPLAY_RC" \
    "$PY" "$REPO/scripts/release/write_report.py"
REPORT_RC=$?

echo
if [ "$PYTEST_RC" -eq 0 ] && [ "$REPLAY_RC" -eq 0 ]; then
    echo "F1 RELEASE AUDIT: PASS -> $OUT/REPORT.md"
    echo "STATUS one-liner: F1 release audit $DATE PASS (property suite + ~${REPLAY_GAMES}-game replay; 0 divergences) -> $OUT/REPORT.md"
    exit 0
else
    echo "F1 RELEASE AUDIT: FAIL (pytest_rc=$PYTEST_RC replay_rc=$REPLAY_RC) -> $OUT/REPORT.md"
    exit 1
fi
