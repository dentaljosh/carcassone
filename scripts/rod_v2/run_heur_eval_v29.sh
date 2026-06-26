#!/usr/bin/env bash
# RoD v2 net (v2.9 leaf) vs heur@N_v2.9 ruler — 2-box work-stealing via v28_handoff_orch.sh.
# The net agent (agent-a, from CKPT) AND the heuristic opponent (agent-b, heur@N) BOTH use
# the frozen v2.9 leaf (Bmild_cap8): curve -8,-4,-1,0,2,3,4,5 replaces flat meeple, cap 8,
# 3-open. Driven entirely by env: eval_hybrid_handoff.py uses os.environ.setdefault for the
# leaf env, so pre-setting these (verified hash 7fc930b82801cb43) wins — no code fork.
# --meeple-k-a/-b 2.0 are inert (curve replaces the flat term), kept to match the harness.
#
# Usage: CKPT=/path/iter.pt LABEL=rod2_iter06 HSIMS=6400 N=200 SEED=... \
#        OW_LOCAL=20 OW_LAPTOP=6 bash scripts/rod_v2/run_heur_eval_v29.sh
set -uo pipefail
SHARE_LOCAL=/mnt/c/carc-shared; SHARE_REMOTE=/mnt/carc-shared
REPO=/home/doctor/projects/carcassone; LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}
PY=$REPO/.venv/bin/python
EVALDIR=$SHARE_LOCAL/rod_v2_flywheel/evals; EVALDIR_R=${EVALDIR/$SHARE_LOCAL/$SHARE_REMOTE}
CKPT=${CKPT:?need CKPT=/abs/path/iter.pt}; LABEL=${LABEL:?need LABEL=name}
HSIMS=${HSIMS:-6400}; N=${N:-200}; SEED=${SEED:?need SEED}
OW_LOCAL=${OW_LOCAL:-20}; OW_LAPTOP=${OW_LAPTOP:-6}
USE_LAPTOP=${USE_LAPTOP:-1}; TIMEOUT_S=${TIMEOUT_S:-14400}
HOH=scripts/heuristic_v28/v28_handoff_orch.sh
cand_r=${CKPT/$SHARE_LOCAL/$SHARE_REMOTE}
[ -f "$CKPT" ] || { echo "FATAL: $CKPT missing" >&2; exit 1; }
sub="${LABEL}_vs_heur${HSIMS}_v29"; dir=$EVALDIR/$sub
cd "$REPO"; mkdir -p "$dir" "$EVALDIR/logs"

# v2.9 FROZEN leaf env (Bmild_cap8). DROP_THREE_OPEN=0 -> 3-open (NOT v2.8's drop-3).
V29ENV="CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0 CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0"
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0 \
       CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5 CARCASSONNE_V25_MEEPLE_K=2.0

_reap(){ for p in carc-orch v28hndf eval_hybrid_handoff spawn_main; do
  pkill -9 -f "[${p:0:1}]${p:1}" 2>/dev/null||true
  [ "$USE_LAPTOP" = 1 ] && timeout 15 ssh -o ConnectTimeout=8 "$LAPTOP_SSH" "pkill -9 -f '[${p:0:1}]${p:1}'" </dev/null >/dev/null 2>&1||true
done; }
trap _reap EXIT

echo "### $LABEL vs heur@${HSIMS}_v2.9  n=$N OW=$OW_LOCAL/$OW_LAPTOP seed=$SEED @ $(date) ###"
for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.json" ] || rm -f "$c"; done
_reap; sleep 1

CKPT="$CKPT" OW="$OW_LOCAL" nohup nice -n 19 bash "$HOH" \
  --agent-a iter8 --meeple-k-a 2.0 --agent-b "heur@${HSIMS}" --meeple-k-b 2.0 \
  --n "$N" --paired --seed-start "$SEED" --shared-claim --claim-host local \
  --out-root "$EVALDIR" --out-subdir "$sub" > "$EVALDIR/logs/${sub}_local.log" 2>&1 & disown
if [ "$USE_LAPTOP" = 1 ]; then
  timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
    "cd $REPO && $V29ENV CKPT=$cand_r OW=$OW_LAPTOP setsid nice -n 19 bash $HOH --agent-a iter8 --meeple-k-a 2.0 --agent-b heur@${HSIMS} --meeple-k-b 2.0 --n $N --paired --seed-start $SEED --shared-claim --claim-host laptop --out-root $EVALDIR_R --out-subdir $sub > $EVALDIR_R/logs/${sub}_laptop.log 2>&1 </dev/null &" \
    </dev/null >/dev/null 2>&1 || echo "  (laptop launch rc=$? — local continues)"
fi

t=0; last=-1; stall=0
while [ "$(ls "$dir"/seed*_a*.json 2>/dev/null|wc -l)" -lt "$N" ]; do
  sleep 20; t=$((t+20)); cur=$(ls "$dir"/seed*_a*.json 2>/dev/null|wc -l)
  if [ "$cur" = "$last" ]; then stall=$((stall+1)); else stall=0; last=$cur; fi
  [ "$t" -ge "$TIMEOUT_S" ] && { echo "  TIMEOUT at $cur/$N (tally partial)"; break; }
  [ "$stall" -ge 45 ] && { echo "  STALL at $cur/$N (15min no progress; tally partial)"; break; }
done
_reap; sleep 2

env $V29ENV "$PY" scripts/level2/eval_hybrid_handoff.py --agent-a iter8 --meeple-k-a 2.0 --agent-b "heur@${HSIMS}" \
  --meeple-k-b 2.0 --ckpt "$CKPT" --shm-eval-server x --workers 1 --n "$N" --paired --seed-start "$SEED" \
  --out-root "$EVALDIR" --out-subdir "$sub" --summary-only > "$EVALDIR/logs/${sub}_tally.log" 2>&1
echo "=== $LABEL vs heur@${HSIMS}_v2.9 ($(ls "$dir"/seed*_a*.json 2>/dev/null|wc -l) games) ==="
grep -iE "ELO|paired|signal|tie|^A:|n=" "$EVALDIR/logs/${sub}_tally.log" | head -8 || tail -6 "$EVALDIR/logs/${sub}_tally.log"
