#!/usr/bin/env bash
# INTERIM SEALED (Joshua 2026-06-14 pm): is iter9 (current deepteacher best) a POWERED
# upgrade over iter0 (= warm-start = flywheel_residual_attempt2/iter8 = the PRODUCTION
# champion)? i.e. "is iter9 promote-to-prod worthy + did the deeper-teacher run net-gain?"
# Full 3-box, n=400 paired, vs heur@800-v2.7, scale 0.25, HELD-OUT band 1.6e9 (verified
# unused; keeps the reserved 1.8e9 pristine for the true end-of-run sealed).
# RUN WITH THE ORCHESTRATOR PAUSED (full cluster). Verdict: odo_paired_tally(base, champ).
set -uo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

SHARE_L=/mnt/c/carc-shared; SHARE_R=/mnt/carc-shared
REPO_L=/home/doctor/projects/carcassone; REPO_LAP=/home/pop/carcassone; REPO_XEON=/home/doctor/projects/carcassone
PY=$REPO_L/.venv/bin/python
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1"
SCALE=0.25; N=400; SIMS=800; HS=800; BAND=1600000000
W5=14; WL=20; WX=10
OUT=$SHARE_L/deepteacher/sealed_interim; OUTR=$SHARE_R/deepteacher/sealed_interim
mkdir -p "$OUT"; cd "$REPO_L" || exit 1
COMMON="--n $N --sims $SIMS --heur-sims $HS --c-puct 3.0 --heur-leaf v2_7 --seed-start $BAND --paired --shared-claim"

launch_side() {  # $1=local_ckpt $2=remote_ckpt $3=subdir
  local lck="$1" rck="$2" sub="$3"
  nohup nice -n 19 env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE "$PY" -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$lck" --workers $W5 --out-root "$OUT" --out-subdir "$sub" --claim-host 5800x $COMMON \
    > /tmp/sealedint_${sub}_5800x.log 2>&1 & disown
  # remote launches: setsid (detach) + backgrounded on THIS side (& ) so a hung ssh can't block
  ssh -o ConnectTimeout=20 laptop "cd $REPO_LAP && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE setsid nice -n 19 $REPO_LAP/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rck --workers $WL --out-root $OUTR --out-subdir $sub --claim-host laptop $COMMON > /tmp/sealedint_${sub}_laptop.log 2>&1 </dev/null &" </dev/null >/dev/null 2>&1 &
  ssh -o ConnectTimeout=20 xeon-wsl "cd $REPO_XEON && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE setsid nice -n 19 $REPO_XEON/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rck --workers $WX --out-root $OUTR --out-subdir $sub --claim-host xeon $COMMON > /tmp/sealedint_${sub}_xeon.log 2>&1 </dev/null &" </dev/null >/dev/null 2>&1 &
}

launch_side "$SHARE_L/deepteacher/best.pt"                       "$SHARE_R/deepteacher/best.pt"                       sealed9_champ
launch_side "$SHARE_L/flywheel_residual_attempt2/ckpt/iter8.pt"  "$SHARE_R/flywheel_residual_attempt2/ckpt/iter8.pt"  sealed9_base
sleep 3
echo "launched interim sealed: sealed9_champ(iter9) + sealed9_base(iter0=prod iter8), band $BAND, n=$N/side, 3-box (W $W5/$WL/$WX)"
echo "verdict when both =$N: $PY scripts/odo_paired_tally.py $OUT/sealed9_base $OUT/sealed9_champ"