#!/usr/bin/env bash
# Value/Search Autopsy — Stage 2 leg driver. Runs ONE intervention leg of the
# matrix on the miss-probe (probe rows w/ action_q restricted to iter04 misses).
# Box-agnostic: pass PROBE / CKPT04 / OUTDIR / WORKERS via env (paths differ per box).
#
#   PROBE=... CKPT04=... OUTDIR=... WORKERS=14 ./run_leg.sh <leg>
# legs: flat teacher rs0 rs05 s400 s800 s1600 forced
set -euo pipefail
LEG="${1:?leg name}"
REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python3"
PROBE="${PROBE:?}"; CKPT04="${CKPT04:?}"; OUTDIR="${OUTDIR:?}"; WORKERS="${WORKERS:-14}"
mkdir -p "$OUTDIR"
H="$REPO/scripts/rod_v2/value_search/miss_harness.py"
common=(--probe "$PROBE" --checkpoints "iter04=$CKPT04" --gap-min 0.0 --workers "$WORKERS")

case "$LEG" in
  flat)    nice -n 19 "$PY" "$H" "${common[@]}" --sims 200 --prior flat    --tag I3_flat   --out "$OUTDIR/I3_flat.jsonl" ;;
  teacher) nice -n 19 "$PY" "$H" "${common[@]}" --sims 200 --prior teacher --prior-temp 0.03 --tag I2_teacher --out "$OUTDIR/I2_teacher.jsonl" ;;
  rs0)     nice -n 19 "$PY" "$H" "${common[@]}" --sims 200 --residual-scale 0.0 --tag I4_rs0  --out "$OUTDIR/I4_rs0.jsonl" ;;
  rs05)    nice -n 19 "$PY" "$H" "${common[@]}" --sims 200 --residual-scale 0.5 --tag I4_rs05 --out "$OUTDIR/I4_rs05.jsonl" ;;
  s400)    nice -n 19 "$PY" "$H" "${common[@]}" --sims 400  --tag I1_s400  --out "$OUTDIR/I1_s400.jsonl" ;;
  s800)    nice -n 19 "$PY" "$H" "${common[@]}" --sims 800  --tag I1_s800  --out "$OUTDIR/I1_s800.jsonl" ;;
  s1600)   nice -n 19 "$PY" "$H" "${common[@]}" --sims 1600 --tag I1_s1600 --out "$OUTDIR/I1_s1600.jsonl" ;;
  forced)  nice -n 19 "$PY" "$REPO/scripts/rod_v2/value_search/forced_move.py" \
               --misses "${MISSES:?forced needs MISSES=miss rows w/ nmcts_top}" \
               --checkpoint "$CKPT04" --workers "$WORKERS" --out "$OUTDIR/I6_forced.jsonl" ;;
  *) echo "unknown leg $LEG"; exit 2 ;;
esac
echo "leg $LEG DONE -> $OUTDIR"
