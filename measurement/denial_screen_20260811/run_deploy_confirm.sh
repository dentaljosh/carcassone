#!/bin/bash
# TARGETED-DENIAL DEPLOY-BUDGET CONFIRM driver.
# Prereg: measurement/denial_screen_20260811/PREREG_DEPLOY_CONFIRM.md
#
# ONE cell, n=800 deck-paired, FRESH band:
#   cand = champion leaf + denial dose 1.0 / size_min 5 / open_max 3 (hash effeca41772e3e78)
#   opp  = the unmodified production champion (hash a36d2e15a3b3d71d)
#   BOTH arms at the DEPLOY budget k8x1376 = 11008, via eval_fair_puct.py (NOT the 2750
#   ablation instrument -- the instrument change is the entire point of this cell).
#
# ADJUDICATES NOTHING. No promotion, no PRODUCTION.yaml, no results.csv row, no claim row.
#
# Gates run BEFORE game 1 (all fail-stop):
#   D0  _leaf_hash(cell json) == effeca41772e3e78     (the explicit curve125 must be a no-op)
#   P   chain_capability_probe.py --require denial     on BOTH boxes
#   rev identity on both boxes
# The band is claimed only after every gate passes.
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
DIR=$REPO/measurement/denial_screen_20260811
LOGS=$DIR/deploy_logs
OUT=/mnt/c/carc-shared/denial_deploy_20260812      # LOCAL prefix
LOUT=/mnt/carc-shared/denial_deploy_20260812       # LAPTOP prefix (same store)
LAPTOP=laptop-wsl
# ⚠️ W_LOCAL=14 (NOT 30) by Joshua's 2026-08-12 mid-session instruction: the local box runs
# lighter from this cell onward. The laptop is unchanged at 22. This does NOT affect the
# strength statistic (deck-paired, both arms in the SAME process pool, so the ratio is
# first-order insensitive to contention) but it DOES change games/h and the absolute
# ms/move, so it is recorded here, in the prereg and in the band-registry row -- a future
# reader comparing throughput or cost across this session's cells needs to know the worker
# count changed between the sims-split cells (W30) and this one (W14).
W_LOCAL=${W_LOCAL:-14}
W_LAPTOP=${W_LAPTOP:-22}
N=${N:-800}
SUB=denial_d1_s5_o3_deploy11008
CELLJSON=$DIR/cells/denial_d1_s5_o3_deploy_fixed_v1_vs_fairchamp11008.json
EXPECT_HASH=effeca41772e3e78
CHAMP_HASH=a36d2e15a3b3d71d
SUMMARY=$REPO/scripts/classical_search/menu_block_summary.py
PROBE=$REPO/scripts/classical_search/chain_capability_probe.py

# canonical champion leaf env (the probe resolves DEFAULT_CONFIG from it at import time)
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1
export CHAIN_PY=$PY

mkdir -p "$LOGS" "$DIR/verdicts" "$OUT"
ts() { date +%F_%T; }
log() { echo "[denial-deploy $(ts)] $*"; }
die() { log "!!! BLOCKED: $*"; { echo "$(ts)"; echo "reason: $*"; } > "$DIR/BLOCKED_DEPLOY"; exit 10; }

cd "$REPO" || die "cannot cd to repo"

# ---------------- GATE: rev identity ----------------
LREV=$(git -C "$REPO" rev-parse HEAD)
RREV=$(timeout 120 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' 2>/dev/null <<'RQ'
cd /home/doctor/projects/carcassone || exit 1
git -C /home/doctor/projects/carcassone rev-parse HEAD
RQ
)
RREV=$(printf '%s' "$RREV" | tr -d '[:space:]')
[ -n "$RREV" ] || die "laptop unreachable"
[ "$LREV" = "$RREV" ] || die "rev mismatch: local $LREV vs laptop $RREV. Bundle-sync before relaunching."
log "rev identity OK ($LREV)"

# ---------------- GATE D0: the cell JSON hashes to D1's candidate leaf ----------------
[ -f "$CELLJSON" ] || die "missing cell json $CELLJSON"
GOT=$($PY - "$CELLJSON" <<'PYEOF'
import sys, pathlib
sys.path.insert(0, "/home/doctor/projects/carcassone/scripts/classical_search")
from c5_leaf_override import _leaf_hash, _load_cand_leaf_cfg
cfg = _load_cand_leaf_cfg(sys.argv[1])
print(_leaf_hash(cfg))
PYEOF
)
GOT=$(printf '%s' "$GOT" | tail -1 | tr -d '[:space:]')
log "GATE D0: cell json leaf hash = $GOT (expected $EXPECT_HASH)"
[ "$GOT" = "$EXPECT_HASH" ] || die "GATE D0 FAILED: cell json hashes to '$GOT', not D1's candidate leaf '$EXPECT_HASH'. Either the explicit curve125 is NOT a no-op or the denial knobs differ from D1's. This would be a DIFFERENT candidate leaf than the screen ran, so the confirm would not confirm anything."
[ "$GOT" = "$CHAMP_HASH" ] && die "GATE D0 FAILED: the candidate hash IS the champion's - the knob did not reach the leaf."

# ---------------- GATE P: denial capability probe, BOTH boxes ----------------
$PY "$PROBE" --require denial --doses 1.0 --size-min 5 --open-max 3 --max-cells 1 \
    --cells-out "$OUT/probe_cells.local.tsv" \
    --json-out "$DIR/verdicts/DEPLOY_capability_local.json" > "$LOGS/probe_local.log" 2>&1 \
    || die "LOCAL denial capability probe FAILED - see $LOGS/probe_local.log. A stale carc_rs serves a default-off leaf and would produce a meaningless null."
log "GATE P: local denial capability probe PASS"

cat > "$LOGS/_laptop_probe.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1
export CHAIN_PY=/home/doctor/projects/carcassone/.venv/bin/python
mkdir -p $LOUT
/home/doctor/projects/carcassone/.venv/bin/python \\
  /home/doctor/projects/carcassone/scripts/classical_search/chain_capability_probe.py \\
  --require denial --doses 1.0 --size-min 5 --open-max 3 --max-cells 1 \\
  --cells-out $LOUT/probe_cells.laptop.tsv \\
  --json-out $LOUT/DEPLOY_capability_laptop.json
EOF
timeout 900 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' < "$LOGS/_laptop_probe.sh" \
    > "$LOGS/probe_laptop.log" 2>&1 \
    || die "LAPTOP denial capability probe FAILED - see $LOGS/probe_laptop.log. It plays ~40% of the cell and its default-off games are indistinguishable at read time."
# The laptop wrote through ITS mount prefix ($LOUT); this box reads the same file as $OUT.
cp -f "$OUT/DEPLOY_capability_laptop.json" "$DIR/verdicts/DEPLOY_capability_laptop.json" 2>/dev/null \
    || die "the laptop probe exited 0 but left no verdict JSON at $LOUT/DEPLOY_capability_laptop.json (read here as $OUT/) - a probe that cannot persist its own result is not evidence."
LHASH=$(cut -f3 "$OUT/probe_cells.laptop.tsv" 2>/dev/null | head -1 | tr -d '[:space:]')
[ "$LHASH" = "$EXPECT_HASH" ] || die "the LAPTOP derives candidate leaf hash '$LHASH', not '$EXPECT_HASH' - the two boxes are not computing the same candidate leaf."
log "GATE P: laptop denial capability probe PASS, candidate hash agrees ($LHASH)"

# ---------------- BAND (claimed only now, after every gate) ----------------
NOTES="Seeds <band>..<band+399> (400 decks x 2 seats). DEPLOY-BUDGET CONFIRM of the D1 targeted-denial kill: candidate = champion leaf + denial dose 1.0 / size_min 5 / open_max 3 (cand_leaf_hash effeca41772e3e78, THE SAME candidate leaf D1 ran), opponent = the unmodified production champion a36d2e15a3b3d71d. BOTH ARMS AT THE DEPLOY BUDGET k8x1376=11008 via eval_fair_puct.py --info fair --opponent fair-champion -- NOT the 2750 ablation instrument. THE INSTRUMENT CHANGE IS THE ENTIRE POINT: D1 killed denial at ~1/4 of deploy budget, and this project has twice paid for the lesson that a leaf knob's value depends on the search that consumes it (curve125 was NULL under random-expansion UCT and a WIN under PUCT+priors, CL-051; meeple_K was killed cheap and later worth +179 elo). NOT POOLABLE WITH THE D1 CELLS, EVER - different instrument AND different band; the D1 pooled result (n=400 band 1.21e11: elo -30.479 +/- 17.439, margin -1.570, z -2.2932, between-half z +0.08) is a PRIOR, never a summand. Both boxes passed the denial capability probe with agreeing candidate hashes, and the cell JSON's leaf hash was gated against effeca41772e3e78, BEFORE game 1. Power: n=800 gives 1sigma ~+/-12.3 elo, 2sigma ~+/-24.6, margin 2sigma ~+/-0.9-1.4 pts/deck; the screen effect is ~2.2-3.5 sigma at this n so the cell is decisive on the face-value prior and NOT on a curse-calibrated half-size effect. Branch map: z<=-2.0 the kill REPLICATES at deploy budget and the lever closes on strong ground; |z|<1.5 the ablation-instrument kill DOES NOT TRANSFER and LEVER_INDEX must say so rather than claim a deploy-budget kill; z>=+2.0 the cheap instrument produced a FALSE KILL, a finding about our SCREENING METHODOLOGY as much as about denial; 1.5<=|z|<2.0 one top-up on RESERVED fresh decks <band+400>..<band+799>. Nothing is proposed for PRODUCTION.yaml on any branch. WORKER COUNT: W_LOCAL=14 / W_LAPTOP=22 (36 total), CHANGED MID-SESSION on Joshua's 2026-08-12 instruction that the local box run lighter -- the sims-split cells on band 1.23e11 ran W30/W22 (52 total). Deck-paired with both arms in the SAME process pool, so the strength statistic and ms_ratio are first-order insensitive to this; games/h and every ABSOLUTE ms/move are NOT, so any throughput or cost comparison across this session's cells must condition on the worker count. Registered before game 1. FLIP TO retired AT CLOSE-OUT."
BAND=$($PY "$REPO/scripts/classical_search/claim_next_band.py" \
  --label "TARGETED-DENIAL DEPLOY-BUDGET CONFIRM: 1 cell n=800 deck-paired, cand = champion leaf + denial dose 1.0/size_min 5/open_max 3 (effeca41772e3e78) vs the unmodified champion (a36d2e15a3b3d71d), BOTH arms FAIR PIMC k8x1376=11008 (eval_fair_puct.py, NOT the 2750 ablation instrument), fixed_v1+R9, rust, exact-K 2." \
  --tier claim --evidence "measurement/denial_screen_20260811/PREREG_DEPLOY_CONFIRM.md" \
  --notes "$NOTES" --sentinel "$DIR/BAND_DEPLOY" \
  --registry "$REPO/governance/BAND_REGISTRY.csv" 2>>"$LOGS/band.log" | tail -1)
case "$BAND" in ''|*[!0-9]*) die "band claim failed (got '$BAND') - see $LOGS/band.log" ;; esac
log "claimed band $BAND (sentinel $DIR/BAND_DEPLOY)"

# ---------------- LAUNCH ----------------
mkdir -p "$OUT/$SUB"
LCELLJSON=$CELLJSON   # in-repo path, identical on both boxes
cat > "$LOGS/_laptop_cell.sh" <<EOF
cd /home/doctor/projects/carcassone || exit 1
mkdir -p $LOUT/$SUB
setsid nohup env MENU_OUT_ROOT=$LOUT nice -n 19 bash \\
  scripts/classical_search/menu_fair_cell.sh $W_LAPTOP laptop \\
    --sub $SUB --n $N --band $BAND \\
    --k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376 \\
    --cand-leaf-json $LCELLJSON --drift \\
  > $LOUT/$SUB/laptop.log 2>&1 < /dev/null & disown
echo "laptop cell launched pid \$!"
EOF
( timeout 180 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' < "$LOGS/_laptop_cell.sh" \
    >> "$LOGS/laptop_launch.log" 2>&1
  echo "[laptop-launch $(date +%F_%T)] ssh rc=$? (124 == launched-and-detached)" >> "$LOGS/laptop_launch.log" ) &

MENU_OUT_ROOT=$OUT nice -n 19 bash "$REPO/scripts/classical_search/menu_fair_cell.sh" "$W_LOCAL" local \
    --sub "$SUB" --n "$N" --band "$BAND" \
    --k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376 \
    --cand-leaf-json "$CELLJSON" --drift > "$LOGS/cell_local.log" 2>&1 &
PID=$!
log "local launcher pid $PID"

busy_py_local() { ps -eo pcpu,args --no-headers | awk '$1 > 20.0 && /python/' | wc -l; }
laptop_claims() { find "$1" -maxdepth 1 -name 'seed*.claim' -print0 2>/dev/null \
                  | xargs -0 -r grep -l -E 'helper|laptop' 2>/dev/null | wc -l; }
t0=$(date +%s); ok=0
while [ $(( $(date +%s) - t0 )) -lt 1200 ]; do
  lw=$(busy_py_local)
  pw=$(timeout 90 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' 2>/dev/null <<'RQ'
ps -eo pcpu,args --no-headers | awk '$1 > 20.0 && /python/' | wc -l
RQ
)
  pw=$(printf '%s' "$pw" | head -1 | tr -dc '0-9'); pw=${pw:-0}
  lc=$(laptop_claims "$OUT/$SUB")
  if [ "$lw" -gt 1 ] && [ "$pw" -gt 1 ] && [ "$lc" -gt 0 ]; then ok=1; break; fi
  sleep 30
done
log "two-box check local_busy=${lw:-0} laptop_busy=${pw:-0} laptop_claims_on_cell=${lc:-0} ok=$ok"

wait $PID
log "local launcher exited rc=$?"
GOTN=$(find "$OUT/$SUB" -maxdepth 1 -name 'seed*.json' | wc -l)
log "records $GOTN/$N"
$PY "$SUMMARY" --dir "$OUT/$SUB" --label "${SUB}_n${N}_b${BAND}" \
    --expected-rules-profile fixed_v1 --expect-cand-leaf-hash "$EXPECT_HASH" \
    --topup-trigger --out "$DIR/verdicts/DEPLOY_CONFIRM.json" >> "$LOGS/cell_local.log" 2>&1
: > "$DIR/DONE_DEPLOY"
log "=== COMPLETE -> $DIR/verdicts/DEPLOY_CONFIRM.json (band $BAND). Nothing promoted. ==="
