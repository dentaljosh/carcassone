#!/usr/bin/env bash
# RoD v2 (v2.9 leaf) ruler screen — drives run_heur_eval_v29.sh over the agent x depth grid,
# 2-box work-stealing per cell, sequentially. h6400 (PRIMARY) first, then h3200 (secondary).
#
#   Agents (nets, all eval'd WITH the v2.9 Bmild_cap8 leaf):
#     rod1_v29      = RoD_iter_01 + v2.9 leaf, NO retrain (baseline)
#     rod2_iter02/04/06 = RoD v2 flywheel checkpoints
#   Opponent: heur@{6400,3200}_v2.9 (same frozen leaf). n=200 paired screen.
#   Main signal = vs h6400 (do NOT lean on adjacent-parent wins). Top-up handled separately.
#
# Launch (detached): nohup nice -n 19 bash scripts/rod_v2/run_v29_eval_screen.sh > /tmp/v29_screen.log 2>&1 & disown
set -uo pipefail
REPO=/home/doctor/projects/carcassone
SHARE=/mnt/c/carc-shared
EVALDIR=$SHARE/rod_v2_flywheel/evals
WRAP=$REPO/scripts/rod_v2/run_heur_eval_v29.sh
CKDIR=$SHARE/rod_v2_flywheel/ckpt
ROD1=$SHARE/rod_v28_continuation/ckpt/iter_01.pt
SUMMARY=$EVALDIR/V29_SCREEN_SUMMARY.md
cd "$REPO"; mkdir -p "$EVALDIR/logs"

# label   ckpt
AGENTS=(
  "rod1_v29|$ROD1"
  "rod2_iter02|$CKDIR/iter_02.pt"
  "rod2_iter04|$CKDIR/iter_04.pt"
  "rod2_iter06|$CKDIR/iter_06.pt"
)
# depth   OW_LOCAL OW_LAPTOP   (flat/cy leaf ~750M/worker steady; local 32T+41G: W40 = ~30G py
# + ~5G sys, ~6-12G headroom, fills the ~17% orch-wait idle without oversubscribing 32T.
# laptop maxed at W8 h6400 / W10 h3200 — leave it.)
DEPTHS=("6400|40|8" "3200|40|10")
SEED_BASE=1950000000; N=${N:-200}; ci=0

[ -f "$SUMMARY" ] || printf "# RoD v2 (v2.9 leaf) ruler screen — n=%s paired\n\nMain signal = vs h6400_v2.9. Started %s.\n\n| agent | vs | n | A_W | A_L | D | elo | note |\n|---|---|--:|--:|--:|--:|--:|---|\n" "$N" "$(date)" > "$SUMMARY"

echo "=== RoD v2 v2.9 ruler screen @ $(date) — ${#AGENTS[@]} agents x ${#DEPTHS[@]} depths, n=$N ==="
for depth_spec in "${DEPTHS[@]}"; do
  IFS='|' read -r HS OWL OWP <<< "$depth_spec"
  for agent_spec in "${AGENTS[@]}"; do
    IFS='|' read -r LABEL CKPT <<< "$agent_spec"
    ci=$((ci+1)); SEED=$(( SEED_BASE + ci*2000000 ))
    sub="${LABEL}_vs_heur${HS}_v29"
    if [ -f "$EVALDIR/$sub/DONE" ]; then echo "[$sub] already done — skip"; continue; fi
    echo ""; echo "########## CELL $ci: $LABEL vs heur@${HS}_v2.9  (seed $SEED) @ $(date) ##########"
    CKPT="$CKPT" LABEL="$LABEL" HSIMS="$HS" N="$N" SEED="$SEED" OW_LOCAL="$OWL" OW_LAPTOP="$OWP" \
      bash "$WRAP" 2>&1 | tee -a "$EVALDIR/logs/screen_${sub}.out"
    # parse the cell tally for the summary row
    tl="$EVALDIR/logs/${sub}_tally.log"
    row=$("$REPO/.venv/bin/python" - "$tl" "$LABEL" "heur@${HS}" <<'PY'
import re,sys
tl,label,opp=sys.argv[1],sys.argv[2],sys.argv[3]
try: t=open(tl).read()
except: t=""
def g(p,d="?"):
    m=re.search(p,t,re.I); return m.group(1) if m else d
games=g(r"games:\s*(\d+)")
wdl=re.search(r"(\d+)\s*W\s*/\s*(\d+)\s*D\s*/\s*(\d+)\s*L",t,re.I)
w,dd,l=(wdl.group(1),wdl.group(2),wdl.group(3)) if wdl else ("?","?","?")
wr=g(r"winrate\s+([\d.]+)"); elo=g(r"ELO \(A vs B\):\s*([-+]?[\d.]+)")
pz=g(r"margin\s+[-+]?[\d.]+\s+z\s*=\s*([-+]?[\d.]+)")
print(f"| {label} | {opp}_v2.9 | {games} | {w} | {l} | {dd} | {elo} | wr {wr}, paired z {pz} |")
PY
)
    echo "$row" >> "$SUMMARY"
    echo "  -> $row"
    touch "$EVALDIR/$sub/DONE"
  done
done
echo ""; echo "=== screen DONE @ $(date) — summary: $SUMMARY ==="
cat "$SUMMARY"
