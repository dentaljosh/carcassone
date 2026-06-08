#!/usr/bin/env bash
# AUTONOMOUS CHAIN — PROTOCOL_002 head-to-head → (maybe n=1500) → Track-B flywheel #1.
#
# Wired per Joshua (2026-06-07): "wire up those shits to auto launch."
#   (a) n=1500 escalation: fire ONLY if the n=400 deck-paired |z| lands in the
#       pre-registered 1.3 < |z| < 2 band (PROTOCOL_002 top-up rule). Otherwise the
#       n=400 verdict stands (≥2σ → crown a production agent; <1.3σ → "~equivalent").
#   (b) Track-B flywheel: launch the FRESH retuned residual flywheel (attempt #1 of the
#       ≤2-attempt budget, PROJECT_CHARTER) once the h2h verdict is final.
#
# EVAL-then-TRAIN. Fully detached (run via setsid); survives SSH death. NYC local time.
# Writes the final verdict to $VERDICT for the paperwork pass (PROTOCOL_002/registry/commit).
set -uo pipefail
export TZ=America/New_York
export PYTHONUNBUFFERED=1

SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
REPO=/home/doctor/projects/carcassone
REPO_LAPTOP=/home/pop/carcassone
REPO_XEON=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
H2H_DIR=$SHARE_LOCAL/h2h_runs/residual_rs025_vs_iter11_s200/eval/iter_01_vs_11
VERDICT=$SHARE_LOCAL/h2h_runs/AUTOCHAIN_VERDICT.json

# --- Track-B flywheel attempt #1 knobs (vetoable before the h2h finishes) ---
FW_TAG=flywheel_residual_v2     # fresh dir → does NOT resume the prior null run
FW_NGATE=400                    # charter-ratified gate n (was 300; ±21→±17 noise)
FW_KEEP=15                      # KEEP_MARGIN = the charter's +15-elo/iter climb bar
FW_VLW=1.5                      # value-loss-weight 1.5 (was 1.0): attacks CL-008 (value gradient-starvation), the cited null mechanism
FW_SCALE=0.25; FW_GAMES=400; FW_SIMS=200; FW_ITERS=3

ts(){ date '+%Y-%m-%d %H:%M:%S %Z'; }
say(){ echo "[$(ts)] $*"; }

count(){ find "$H2H_DIR" -maxdepth 1 -name '*seed*.json' 2>/dev/null | wc -l; }

clean_stranded(){   # free .claim with no .json (shared-claim orphan-stall heal)
  local c
  for c in "$H2H_DIR"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.json" ] || rm -f "$c"; done
}

launch_h2h(){   # $1 = N (target file count); fan the 3-box shared-claim pool
  local N="$1"
  ( cd "$REPO" && N="$N" nice -n 19 bash scripts/run_h2h_residual_vs_iter11.sh > /tmp/h2h_${N}_5800x.log 2>&1 & )
  ssh -o ConnectTimeout=20 laptop "cd $REPO_LAPTOP && SHARE=$SHARE_REMOTE W=20 N=$N setsid nice -n 19 bash scripts/run_h2h_residual_vs_iter11.sh > /tmp/h2h_${N}_laptop.log 2>&1 </dev/null &" || say "laptop h2h launch rc=$?"
  ssh -o ConnectTimeout=20 xeon-wsl "cd $REPO_XEON && SHARE=$SHARE_REMOTE W=10 N=$N setsid nice -n 19 bash scripts/run_h2h_residual_vs_iter11.sh > /tmp/h2h_${N}_xeon.log 2>&1 </dev/null &" || say "xeon h2h launch rc=$?"
}

wait_h2h(){   # $1 = target file count; self-heal the orphan-stall
  local target="$1" last=-1 stall=0 cur
  while :; do
    cur=$(count)
    say "h2h $cur/$target"
    [ "$cur" -ge "$target" ] && { say "h2h reached $target"; break; }
    if [ "$cur" -eq "$last" ]; then stall=$((stall+1)); else stall=0; last=$cur; fi
    if [ "$stall" -ge 8 ]; then     # ~8 min no progress → workers died → heal + relaunch
      say "h2h STALLED at $cur/$target — clean stranded claims + relaunch 3-box"
      clean_stranded; launch_h2h "$target"; stall=0
    fi
    sleep 60
  done
}

# deck-paired tally: echoes "elo sigma z n wins draws losses decks"
tally(){
  "$PY" - "$H2H_DIR" <<'PY'
import json, glob, math, sys, collections, statistics as st
d=sys.argv[1]
by=collections.defaultdict(dict)        # seed -> {seat: net_score in {1,0.5,0}}
for jf in glob.glob(f"{d}/*seed*.json"):
    try: r=json.load(open(jf))
    except Exception: continue
    s=r.get("seed"); seat=r.get("new_player")
    v=0.5 if r.get("drew") else (1.0 if r.get("won_by_new") else 0.0)
    by[s][seat]=v
decks=[sum(v.values())/len(v) for v in by.values() if v]     # per-deck mean over seats
n=sum(len(v) for v in by.values()); nd=len(decks)
wins=sum(1 for v in by.values() for x in v.values() if x==1.0)
dr  =sum(1 for v in by.values() for x in v.values() if x==0.5)
ls  =n-wins-dr
wr=sum(decks)/nd if nd else 0.0
if 0<wr<1 and nd>1:
    se=st.pstdev(decks)/math.sqrt(nd)                         # paired SE of mean wr
    elo=400*math.log10(wr/(1-wr))
    sig=(400/(math.log(10)*wr*(1-wr)))*se
    z=elo/sig if sig else 0.0
else:
    elo=sig=z=float('nan')
print(f"{elo:.1f} {sig:.1f} {z:.2f} {n} {wins} {dr} {ls} {nd}")
PY
}

verdict_label(){   # $1=z ; pre-registered thresholds (residual − iter_11 perspective)
  awk -v z="$1" 'BEGIN{
    az=(z<0)?-z:z
    if (az>=2)      print (z>0)?"residual_wins":"iter11_wins"
    else           print "equivalent_no_large_edge"
  }'
}

in_escalation_band(){   # $1=z → echo 1 iff 1.3 < |z| < 2
  awk -v z="$1" 'BEGIN{ az=(z<0)?-z:z; print (az>1.3 && az<2)?1:0 }'
}

say "=== AUTO-CHAIN start: wait h2h(400) → maybe n=1500 → Track-B flywheel ($FW_TAG) ==="

# ---- 1. wait for the running n=400 h2h ----
wait_h2h 400

# ---- 2. tally + decide escalation (pre-registered) ----
read elo sig z n wins draws losses decks < <(tally)
say "h2h n=400: elo=$elo ± $sig (z=$z) | W/D/L=$wins/$draws/$losses over $decks decks"
ESC=$(in_escalation_band "$z"); FINAL_N=400

if [ "$ESC" = "1" ]; then
  say ">>> z=$z in (1.3,2) → PRE-REGISTERED ESCALATION to n=1500"
  clean_stranded
  launch_h2h 1500
  wait_h2h 1500
  read elo sig z n wins draws losses decks < <(tally)
  FINAL_N=1500
  say "h2h n=1500: elo=$elo ± $sig (z=$z) | W/D/L=$wins/$draws/$losses over $decks decks"
else
  say ">>> z=$z NOT in escalation band → n=400 verdict stands (no top-up)"
fi

VLABEL=$(verdict_label "$z")
say "VERDICT: $VLABEL  (elo=$elo z=$z n=$FINAL_N)"

# ---- 3. write the machine-readable verdict for the paperwork pass ----
cat > "$VERDICT" <<JSON
{
  "experiment_id": "cleaneval_h2h_residual_rs025_vs_iter11",
  "protocol": "PROTOCOL_002",
  "ts_nyc": "$(ts)",
  "final_n": $FINAL_N,
  "escalated": $([ "$ESC" = "1" ] && echo true || echo false),
  "elo_residual_minus_iter11": $elo,
  "sigma": $sig,
  "z": $z,
  "wins": $wins, "draws": $draws, "losses": $losses, "decks": $decks,
  "verdict": "$VLABEL",
  "flywheel_warm_start": "lever_seq/ckpt/residual.pt",
  "flywheel_tag": "$FW_TAG"
}
JSON
say "wrote verdict → $VERDICT"

# ---- 4. launch Track-B flywheel attempt #1 (fresh, retuned) — detached ----
# Warm-start = the residual net regardless of the h2h winner: the flywheel needs a
# residual-trained value head (iter_11's is outcome-trained, unusable for residual self-play).
say "launching Track-B flywheel: TAG=$FW_TAG N_GATE=$FW_NGATE KEEP_MARGIN=$FW_KEEP VLW=$FW_VLW SCALE=$FW_SCALE ITERS=$FW_ITERS"
cd "$REPO" || exit 2
setsid env FLYWHEEL_TAG="$FW_TAG" N_GATE="$FW_NGATE" KEEP_MARGIN="$FW_KEEP" VLW="$FW_VLW" \
       SCALE="$FW_SCALE" GAMES="$FW_GAMES" SIMS="$FW_SIMS" ITERS="$FW_ITERS" START=1 \
       nice -n 19 bash scripts/run_residual_flywheel.sh > /tmp/flywheel_v2.log 2>&1 < /dev/null &
disown || true
say "=== AUTO-CHAIN done: verdict written, flywheel launched (log /tmp/flywheel_v2.log) ==="
