#!/bin/bash
# Phase 1.1 overnight orchestrator (2026-07-06). Executes the PRE-REGISTERED decision
# tree in PLAN.md "Overnight decision tree" autonomously (survives Claude-session limits):
#   round-5 finishes -> launch n=400 confirm (both boxes) -> single read-out ->
#   FIRE(>=+35): K=4 n=200 same-band CRN check | (0,+35): extend same band to n=800 | <=0: stop.
# All launches detached; shared-claim makes every stage resumable after a box reboot.
set -u
REPO=/home/doctor/projects/carcassone
SC=$REPO/scripts/classical_search
LOG=$REPO/measurement/classical_search/overnight_orch.log
SHARE=/mnt/c/carc-shared
K2DIR=$SHARE/puct_confirm/c1.5_tau5_float_visits_s2750_k2
exec >> "$LOG" 2>&1
ts() { date +%F_%T; }
echo "[orch $(ts)] start (pid $$)"

# ---- 1. wait for the round-5 primary launcher to finish (aggregates cell 6) ----
while pgrep -f 'run_screen_sweep.sh primary.*puct_screen 5' >/dev/null; do sleep 60; done
echo "[orch $(ts)] round-5 complete:"
cat "$REPO/measurement/classical_search/SCREEN_PROGRESS_R5.tsv"

# ---- 2. sync launcher to laptop, launch the n=400 K=2 confirm on both boxes ----
scp -q "$SC/run_screen_sweep.sh" laptop-wsl:/home/doctor/projects/carcassone/scripts/classical_search/ \
  && echo "[orch $(ts)] launcher synced to laptop" || echo "[orch $(ts)] WARN scp failed; laptop may run stale launcher"
setsid nice -n 19 bash "$SC/run_screen_sweep.sh" primary 30 "$SHARE/puct_confirm" 6 </dev/null >/tmp/confirm_primary.log 2>&1 &
echo "[orch $(ts)] confirm primary launched (local W30)"
ssh laptop-wsl 'bash -s' <<'HELPER'
# wait for the round-5 helper to drain before taking the box for the confirm
while pgrep -f 'run_screen_sweep.sh helper.*puct_screen' >/dev/null; do sleep 30; done
cd /home/doctor/projects/carcassone || exit 1
setsid nice -n 19 bash scripts/classical_search/run_screen_sweep.sh helper 22 /mnt/carc-shared/puct_confirm 6 </dev/null >/tmp/confirm_helper.log 2>&1 &
sleep 2; ps -eo pid,args | grep '[r]un_screen_sweep.sh helper' | head -2
exit 0
HELPER
echo "[orch $(ts)] confirm helper launched (laptop W22)"

# ---- 3. wait for the confirm primary to exit (it aggregates + writes the TSV row) ----
sleep 120
while pgrep -f 'run_screen_sweep.sh primary.*puct_confirm 6' >/dev/null; do sleep 120; done
echo "[orch $(ts)] confirm primary exited; reading verdict"

# ---- 4. single read-out + pre-registered branch ----
BRANCH=$(python3 - "$K2DIR/summary.json" <<'PYEOF'
import json, sys
try:
    s = json.load(open(sys.argv[1]))
except Exception as e:
    print("broken"); raise SystemExit
n, elo = s.get("n", 0), s.get("elo", float("nan"))
if n < 400:            print("broken")
elif elo >= 35:        print("fire")
elif elo > 0:          print("extend")
else:                  print("stop")
PYEOF
)
ELO=$(python3 -c "import json;s=json.load(open('$K2DIR/summary.json'));print(s.get('n'),s.get('elo'),s.get('paired_z'))" 2>/dev/null)
echo "[orch $(ts)] CONFIRM VERDICT: branch=$BRANCH (n elo paired_z = $ELO)"
cp "$REPO/measurement/classical_search/CONFIRM_PROGRESS.tsv" "$REPO/measurement/classical_search/CONFIRM_PROGRESS_K2.tsv" 2>/dev/null

case "$BRANCH" in
  fire)
    echo "[orch $(ts)] FIRE >= +35 -> launching K=4 n=200 same-band CRN check (W12 local / W8 laptop)"
    CONF_K=4 CONF_N=200 setsid nice -n 19 bash "$SC/run_screen_sweep.sh" primary 12 "$SHARE/puct_confirm" 6 </dev/null >/tmp/confirm_k4_primary.log 2>&1 &
    ssh laptop-wsl 'bash -s' <<'K4HELPER'
while pgrep -f 'run_screen_sweep.sh helper.*puct_confirm' >/dev/null; do sleep 30; done
cd /home/doctor/projects/carcassone || exit 1
CONF_K=4 CONF_N=200 setsid nice -n 19 bash scripts/classical_search/run_screen_sweep.sh helper 8 /mnt/carc-shared/puct_confirm 6 </dev/null >/tmp/confirm_k4_helper.log 2>&1 &
sleep 2; ps -eo pid,args | grep '[r]un_screen_sweep.sh helper' | head -2
exit 0
K4HELPER
    echo "[orch $(ts)] K=4 check launched both boxes; orchestrator done (K4 primary self-aggregates)"
    ;;
  extend)
    echo "[orch $(ts)] AMBIGUOUS (0,+35) -> extending SAME band to n=800 (cached 400 reused; gate +25)"
    CONF_N=800 setsid nice -n 19 bash "$SC/run_screen_sweep.sh" primary 30 "$SHARE/puct_confirm" 6 </dev/null >/tmp/confirm_ext_primary.log 2>&1 &
    ssh laptop-wsl 'bash -s' <<'EXTHELPER'
while pgrep -f 'run_screen_sweep.sh helper.*puct_confirm' >/dev/null; do sleep 30; done
cd /home/doctor/projects/carcassone || exit 1
CONF_N=800 setsid nice -n 19 bash scripts/classical_search/run_screen_sweep.sh helper 22 /mnt/carc-shared/puct_confirm 6 </dev/null >/tmp/confirm_ext_helper.log 2>&1 &
sleep 2; ps -eo pid,args | grep '[r]un_screen_sweep.sh helper' | head -2
exit 0
EXTHELPER
    echo "[orch $(ts)] n=800 extension launched both boxes"
    ;;
  stop)
    echo "[orch $(ts)] KILL/NEGATIVE (elo <= 0) -> full stop, launching nothing. Audit 800<->2750 band parity next session."
    ;;
  *)
    echo "[orch $(ts)] BROKEN (summary missing or n<400) -> stopping without launches; inspect /tmp/confirm_primary.log"
    ;;
esac
echo "[orch $(ts)] orchestrator exit"
