#!/usr/bin/env bash
# INTERIM SEALED (Joshua 2026-06-14): is the deepteacher climb iter2->8 real?
# champion (iter8=best.pt) vs iter2, EACH vs heur@800-v2.7, on HELD-OUT band 1.9e9
# (verified unused), n=200 paired, 3-box shared-claim. Mirrors the flywheel's own
# sealed methodology (eval_net_vs_heuristic --heur-leaf v2_7, scale 0.25, net@200).
# Runs PARALLEL to the live iter9+ run with LOW workers (nice -19) so it doesn't
# starve the main gen. Verdict via odo_paired_tally(base_it2, champ_it8).
set -uo pipefail
SHARE_L=/mnt/c/carc-shared; SHARE_R=/mnt/carc-shared
REPO_L=/home/doctor/projects/carcassone; REPO_LAP=/home/pop/carcassone; REPO_XEON=/home/doctor/projects/carcassone
PY=$REPO_L/.venv/bin/python
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1"
SCALE=0.25; N=200; SIMS=200; HS=800; BAND=1900000000
OUT=$SHARE_L/deepteacher/interim_sealed; OUTR=$SHARE_R/deepteacher/interim_sealed
mkdir -p "$OUT"
cd "$REPO_L" || exit 1

launch_side() {  # $1=ckpt_local $2=ckpt_remote $3=subdir
  local lck="$1" rck="$2" sub="$3"
  nice -n 19 env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE "$PY" -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$lck" --n $N --sims $SIMS --heur-sims $HS --c-puct 3.0 --heur-leaf v2_7 \
    --workers 4 --out-root "$OUT" --out-subdir "$sub" --seed-start $BAND --paired --shared-claim --claim-host 5800x \
    > /tmp/interim_${sub}_5800x.log 2>&1 &
  ssh -o ConnectTimeout=20 laptop "cd $REPO_LAP && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE nice -n 19 $REPO_LAP/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rck --n $N --sims $SIMS --heur-sims $HS --c-puct 3.0 --heur-leaf v2_7 --workers 6 --out-root $OUTR --out-subdir $sub --seed-start $BAND --paired --shared-claim --claim-host laptop > /tmp/interim_${sub}_laptop.log 2>&1 </dev/null &" </dev/null || echo "  laptop $sub launch rc=$?"
  ssh -o ConnectTimeout=20 xeon-wsl "cd $REPO_XEON && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE setsid nice -n 19 $REPO_XEON/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rck --n $N --sims $SIMS --heur-sims $HS --c-puct 3.0 --heur-leaf v2_7 --workers 3 --out-root $OUTR --out-subdir $sub --seed-start $BAND --paired --shared-claim --claim-host xeon > /tmp/interim_${sub}_xeon.log 2>&1 </dev/null &" </dev/null || echo "  xeon $sub launch rc=$?"
}

launch_side "$SHARE_L/deepteacher/best.pt"        "$SHARE_R/deepteacher/best.pt"        champ_it8
launch_side "$SHARE_L/deepteacher/ckpt/iter2.pt"  "$SHARE_R/deepteacher/ckpt/iter2.pt"  base_it2
echo "launched interim sealed: champ_it8(best=iter8) + base_it2, band $BAND, n=$N/side, heur@${HS}-v2.7, scale $SCALE, LOW workers (5800x4/laptop6/xeon3 per side)"
echo "verdict when both =$N: cd $REPO_L && $PY scripts/odo_paired_tally.py $OUT/base_it2 $OUT/champ_it8"
