#!/bin/bash
# Phase 1.1 overnight orchestrator (2026-07-06 v2). Executes the PRE-REGISTERED decision
# tree in PLAN.md autonomously (survives Claude-session limits). Fully SEQUENTIAL: each
# stage's primary runs in the FOREGROUND (blocks until its n is reached + aggregated), the
# laptop helper is launched async per stage. shared-claim makes every stage resumable after
# a box reboot. Chain:
#   round-5 done -> n=400 K=2 confirm (W30+W22) -> single read-out ->
#     FIRE  (>=+35): K=4 n=200 same-band CRN check (W10+W6, RAM-safe) -> tau bracket (W30+W22)
#     AMBIG (0,+35): extend same band to n=800 (gate +25); if it clears -> K=4 -> tau bracket
#     KILL  (<=0):   full stop, launch nothing
#   tau bracket (round 7): tau in {3,8} at c1.5/2750/visits, gates nothing (robustness only)
set -u
REPO=/home/doctor/projects/carcassone
SC=$REPO/scripts/classical_search
MDIR=$REPO/measurement/classical_search
LOG=$MDIR/overnight_orch.log
SHARE=/mnt/c/carc-shared
K2DIR=$SHARE/puct_confirm/c1.5_tau5_float_visits_s2750_k2
exec >> "$LOG" 2>&1
ts() { date +%F_%T; }
echo "[orch $(ts)] start (pid $$)"

# read-out helper: prints "n elo paired_z" from a summary.json (or "MISSING")
readout() { python3 -c "import json;s=json.load(open('$1'));print(s.get('n'),round(s.get('elo',0),1),round(s.get('paired_z',0),2))" 2>/dev/null || echo MISSING; }

# run one stage to completion. $1=label $2=round $3=localW $4=laptopW.
# CONF_K/CONF_N/CONF_BAND are read from the environment by the launcher (exported by caller).
run_stage() {
  local label="$1" round="$2" lw="$3" hw="$4"
  local RENV="${CONF_K:+CONF_K=$CONF_K} ${CONF_N:+CONF_N=$CONF_N} ${CONF_BAND:+CONF_BAND=$CONF_BAND}"
  echo "[orch $(ts)] STAGE $label launched (round=$round localW=$lw laptopW=$hw env=[$RENV])"
  # laptop helper async (waits for any prior helper to drain first); background the ssh call
  # itself so a hung channel can't starve the local primary.
  ssh laptop-wsl 'bash -s' <<HELP &
while pgrep -f 'run_screen_sweep.sh helper' >/dev/null; do sleep 30; done
cd /home/doctor/projects/carcassone || exit 1
$RENV setsid nice -n 19 bash scripts/classical_search/run_screen_sweep.sh helper $hw /mnt/carc-shared/puct_confirm $round </dev/null >/tmp/orch_helper_$label.log 2>&1 &
sleep 2; ps -eo pid,args | grep '[r]un_screen_sweep.sh helper' | head -2
exit 0
HELP
  # local primary FOREGROUND: blocks until n reached + aggregated, then returns.
  nice -n 19 bash "$SC/run_screen_sweep.sh" primary "$lw" "$SHARE/puct_confirm" "$round" >/tmp/orch_primary_$label.log 2>&1
  echo "[orch $(ts)] STAGE $label primary exited"
}

k4_then_tau() {   # shared tail for the positive branches
  echo "[orch $(ts)] -> K=4 n=200 same-band CRN endgame check (conservative W10/W6 for solver RAM)"
  export CONF_K=4 CONF_N=200; run_stage k4 6 10 6; unset CONF_K CONF_N
  cp "$MDIR/CONFIRM_PROGRESS.tsv" "$MDIR/CONFIRM_PROGRESS_K4.tsv" 2>/dev/null
  echo "[orch $(ts)] K=4 readout (n elo z): $(readout "$SHARE/puct_confirm/c1.5_tau5_float_visits_s2750_k4/summary.json")"
  echo "[orch $(ts)] -> TAU BRACKET (tau 3,8 @ c1.5/2750/visits; gates nothing)"
  run_stage taubracket 7 30 22
  echo "[orch $(ts)] tau3 readout: $(readout "$SHARE/puct_confirm/c1.5_tau3_float_visits_s2750_k2/summary.json")"
  echo "[orch $(ts)] tau8 readout: $(readout "$SHARE/puct_confirm/c1.5_tau8_float_visits_s2750_k2/summary.json")"
}

# ---- 1. wait for round-5 primary to finish (it aggregates cell 6) ----
while pgrep -f 'run_screen_sweep.sh primary.*puct_screen 5' >/dev/null; do sleep 60; done
echo "[orch $(ts)] round-5 complete:"; cat "$MDIR/SCREEN_PROGRESS_R5.tsv"

# ---- 2. sync launcher to laptop (it predates ROUND=6/7) + n=400 K=2 confirm ----
scp -q "$SC/run_screen_sweep.sh" laptop-wsl:/home/doctor/projects/carcassone/scripts/classical_search/ \
  && echo "[orch $(ts)] launcher synced to laptop" || echo "[orch $(ts)] WARN scp failed; laptop may run stale launcher"
run_stage confirm 6 30 22
cp "$MDIR/CONFIRM_PROGRESS.tsv" "$MDIR/CONFIRM_PROGRESS_K2.tsv" 2>/dev/null

# ---- 3. single read-out + pre-registered branch ----
BRANCH=$(python3 - "$K2DIR/summary.json" <<'PYEOF'
import json, sys
try: s = json.load(open(sys.argv[1]))
except Exception: print("broken"); raise SystemExit
n, elo = s.get("n", 0), s.get("elo", float("nan"))
print("broken" if n < 400 else "fire" if elo >= 35 else "extend" if elo > 0 else "stop")
PYEOF
)
echo "[orch $(ts)] CONFIRM VERDICT: branch=$BRANCH (n elo z = $(readout "$K2DIR/summary.json"))"

case "$BRANCH" in
  fire)
    echo "[orch $(ts)] FIRE (>=+35): champion-flip is PROPOSABLE (pending human review)."
    k4_then_tau ;;
  extend)
    echo "[orch $(ts)] AMBIGUOUS (0,+35): extend SAME band to n=800 (cached 400 reused; gate +25)"
    export CONF_N=800; run_stage ext800 6 30 22; unset CONF_N
    cp "$MDIR/CONFIRM_PROGRESS.tsv" "$MDIR/CONFIRM_PROGRESS_N800.tsv" 2>/dev/null
    E8=$(python3 -c "import json;print(json.load(open('$K2DIR/summary.json')).get('elo',0))" 2>/dev/null)
    echo "[orch $(ts)] n=800 readout (n elo z): $(readout "$K2DIR/summary.json")"
    if python3 -c "import sys;sys.exit(0 if float('$E8')>=25 else 1)" 2>/dev/null; then
      echo "[orch $(ts)] n=800 clears +25 -> proceeding to K=4 + tau"; k4_then_tau
    else
      echo "[orch $(ts)] n=800 below +25 -> stop (leave K=4/tau for human review)"
    fi ;;
  stop)
    echo "[orch $(ts)] KILL (elo<=0): full stop. Audit 800<->2750 band parity next session." ;;
  *)
    echo "[orch $(ts)] BROKEN (summary missing / n<400): stop; inspect /tmp/orch_primary_confirm.log" ;;
esac
echo "[orch $(ts)] orchestrator exit"
