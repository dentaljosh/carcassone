#!/usr/bin/env bash
# Residual value FLYWHEEL (Lever 3) — does the confirmed +46-elo residual marginal
# COMPOUND when value+policy co-adapt? Per iter: 3-box residual self-play (leaf =
# v2.7 + SCALE·Δ, value head active, value_target=residual) → train the residual
# head on that co-adapted distribution → gate (scale-curve vs HeuristicMCTS@200) →
# KEEP-BEST on the scale0.25 elo (reject regressions, re-branch from best, KataGo/
# G-S3 style). Plateau-stop after 2 non-improving iters. RESUMABLE (per-iter markers).
#
# Runs ON the 5800x; orchestrates 3-box gen via the staged gen_flywheel.sh (work-
# stealing). ⚠️ The gate is IN-ECOSYSTEM (vs our own HeuristicMCTS) — a climb here
# is necessary but NOT sufficient for "beat the v2.7 ceiling"; confirm a real winner
# on the out-of-lineage odometer (ladder_asymmetric.py) before any strength claim.
#
# Env: ITERS(3) SCALE(0.25) GAMES(400) SIMS(200) N_GATE(300) START(1)
# Launch: nohup nice -n 19 bash scripts/run_residual_flywheel.sh > /tmp/flywheel.log 2>&1 & disown
set -uo pipefail

SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
REPO_LOCAL=/home/doctor/projects/carcassone
REPO_XEON=/home/doctor/projects/carcassone
REPO_LAPTOP=/home/pop/carcassone
OUT=$SHARE_LOCAL/flywheel_residual
OUTR=$SHARE_REMOTE/flywheel_residual
PY=$REPO_LOCAL/.venv/bin/python
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"
WARMSTART_ROOT=$REPO_LOCAL/data/warmstart/heuristic_tau05

SCALE=${SCALE:-0.25}; GAMES=${GAMES:-400}; SIMS=${SIMS:-200}
ITERS=${ITERS:-3}; N_GATE=${N_GATE:-300}; START=${START:-1}
GATE_SEED=900000
# iter0 = the confirmed residual net (Lever 1 winner).
ITER0_CKPT=$SHARE_LOCAL/lever_seq/ckpt/residual.pt

mkdir -p $OUT/ckpt $OUT/done $OUT/gate
cd $REPO_LOCAL || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
[ -f "$ITER0_CKPT" ] || { echo "FATAL: iter0 residual ckpt missing: $ITER0_CKPT" >&2; exit 1; }
echo "=== residual FLYWHEEL @ $(date): ITERS=$START..$ITERS SCALE=$SCALE GAMES=$GAMES N_GATE=$N_GATE ==="

# Fresh bundle so remotes run the residual-scale-in-selfplay fix (>= 1d5ae26).
git bundle create $SHARE_LOCAL/code_sync/carc_stage-b-wiring.bundle stage-b-wiring >/dev/null 2>&1
echo "  bundle tip: $(git rev-parse --short stage-b-wiring)"
# Sync remotes ONCE up front (the iter0 gate fans across boxes BEFORE any gen, so
# they need the residual code now — gen_flywheel.sh re-syncs but runs later).
echo "  syncing remotes to bundle…"
ssh -o ConnectTimeout=20 laptop "cd $REPO_LAPTOP && git fetch $SHARE_REMOTE/code_sync/carc_stage-b-wiring.bundle stage-b-wiring && git reset --hard FETCH_HEAD" >/dev/null 2>&1 && echo "  laptop synced" || echo "  laptop sync FAILED (gate fan may run stale)"
ssh -o ConnectTimeout=20 xeon-wsl "cd $REPO_XEON && git fetch $SHARE_REMOTE/code_sync/carc_stage-b-wiring.bundle stage-b-wiring && git reset --hard FETCH_HEAD" >/dev/null 2>&1 && echo "  xeon synced" || echo "  xeon sync FAILED (gate fan may run stale)"

knob_tag() { echo "$1" | sed 's/\.//'; }

# elo of scale0.25 in a gate dir (echoes "elo sigma n"); reads *seed*.json.
gate_elo() {
  $PY - "$1" <<'PY'
import json, glob, math, sys
d=sys.argv[1]; w=dd=n=0
for jf in glob.glob(f"{d}/*seed*.json"):
    try: r=json.loads(open(jf).read())
    except: continue
    n+=1
    if r.get("won_by_net"): w+=1
    elif r.get("drew"): dd+=1
wr=(w+0.5*dd)/n if n else 0
if 0<wr<1:
    elo=400*math.log10(wr/(1-wr)); sig=(400/math.log(10))*math.sqrt(wr*(1-wr)/n)/(wr*(1-wr))
else: elo=float('nan'); sig=float('nan')
print(f"{elo:.1f} {sig:.1f} {n}")
PY
}

# run the scale-curve gate (scale0 + scaleSCALE) FANNED across all 3 boxes via
# shared-claim (the eval is slow single-box: ~3 g/min on the 5800x with per-worker
# CUDA thrash; the 24-thread laptop + xeon ~3× it). $1=ckpt(5800x path) $2=label
# -> echoes scale0.25 elo.
run_gate() {
  local ckpt="$1" label="$2" s tag sub dir rckpt
  rckpt=${ckpt/$SHARE_LOCAL/$SHARE_REMOTE}   # translate to remotes' mount
  for s in 0 $SCALE; do
    tag=$(knob_tag "$s"); sub="${label}_s${tag}"; dir="$OUT/gate/$sub"
    if [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -lt "$N_GATE" ]; then
      nice -n 19 env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE="$s" $PY -u scripts/eval_net_vs_heuristic.py \
        --checkpoint "$ckpt" --n "$N_GATE" --sims "$SIMS" --heur-sims "$SIMS" --c-puct 3.0 \
        --workers 14 --out-root "$OUT/gate" --out-subdir "$sub" \
        --seed-start "$GATE_SEED" --paired --shared-claim --claim-host 5800x >/tmp/fw_gate5800x.log 2>&1 &
      ssh -o ConnectTimeout=20 laptop "cd $REPO_LAPTOP && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$s nice -n 19 $REPO_LAPTOP/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $N_GATE --sims $SIMS --heur-sims $SIMS --c-puct 3.0 --workers 14 --out-root $SHARE_REMOTE/flywheel_residual/gate --out-subdir $sub --seed-start $GATE_SEED --paired --shared-claim --claim-host laptop > /tmp/fw_gatelaptop.log 2>&1 </dev/null &" || echo "  gate laptop launch rc=$?" >&2
      ssh -o ConnectTimeout=20 xeon-wsl "cd $REPO_XEON && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$s setsid nice -n 19 $REPO_XEON/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $N_GATE --sims $SIMS --heur-sims $SIMS --c-puct 3.0 --workers 10 --out-root $SHARE_REMOTE/flywheel_residual/gate --out-subdir $sub --seed-start $GATE_SEED --paired --shared-claim --claim-host xeon > /tmp/fw_gatexeon.log 2>&1 </dev/null &" || echo "  gate xeon launch rc=$?" >&2
      while [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -lt "$N_GATE" ]; do sleep 30; done
    fi
  done
  local s0 s25; s0=$(gate_elo "$OUT/gate/${label}_s0"); s25=$(gate_elo "$OUT/gate/${label}_s$(knob_tag $SCALE)")
  echo "  [gate $label] scale0=$s0 | scale$SCALE=$s25  (marginal=$(echo "$s25 $s0" | awk '{printf "%+.1f",$1-$4}'))" >&2
  echo "$s25" | awk '{print $1}'
}

# --- iter0 baseline at the gate seed (clean climb reference) ---
BEST=$ITER0_CKPT
if [ -f "$OUT/best_elo.txt" ]; then
  BEST_ELO=$(cat "$OUT/best_elo.txt"); [ -f "$OUT/best.pt" ] && BEST=$OUT/best.pt
  echo "  resuming: BEST_ELO=$BEST_ELO"
else
  echo "--- gate iter0 (the confirmed residual net) @ $(date) ---"
  BEST_ELO=$(run_gate "$ITER0_CKPT" "iter0")
  cp "$ITER0_CKPT" "$OUT/best.pt"; echo "$BEST_ELO" > "$OUT/best_elo.txt"
  echo "  iter0 scale$SCALE elo = $BEST_ELO (baseline)"
fi

flat=0
for it in $(seq $START $ITERS); do
  echo ""; echo "########## FLYWHEEL ITER $it @ $(date) (warm from best, elo=$BEST_ELO) ##########"
  DATA=$OUT/iter${it}_data; CKPT=$OUT/ckpt/iter${it}.pt
  cp "$OUT/best.pt" "$OUT/warm.pt"

  # --- 3-box residual self-play (work-stealing) ---
  if [ ! -f "$OUT/done/gen$it" ]; then
    echo "[it$it] launch 3-box residual gen @ $(date)"
    SHARE=$SHARE_LOCAL REPO=$REPO_LOCAL HOST=5800x WORKERS=14 WARM=$OUT/warm.pt OUT=$DATA SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS \
      nohup nice -n 19 bash $SHARE_LOCAL/code_sync/gen_flywheel.sh > /tmp/fw_gen5800x_$it.log 2>&1 & disown
    ssh -o ConnectTimeout=20 laptop "SHARE=$SHARE_REMOTE REPO=$REPO_LAPTOP HOST=laptop WORKERS=14 WARM=$OUTR/warm.pt OUT=$OUTR/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS setsid nice -n 19 bash $SHARE_REMOTE/code_sync/gen_flywheel.sh > /tmp/fw_genlaptop_$it.log 2>&1 </dev/null &" || echo "[it$it] laptop launch rc=$?"
    ssh -o ConnectTimeout=20 xeon-wsl "SHARE=$SHARE_REMOTE REPO=$REPO_XEON HOST=xeon WORKERS=10 WARM=$OUTR/warm.pt OUT=$OUTR/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS setsid nice -n 19 bash $SHARE_REMOTE/code_sync/gen_flywheel.sh > /tmp/fw_genxeon_$it.log 2>&1 </dev/null &" || echo "[it$it] xeon launch rc=$?"
    # wait for GAMES npz (poll local share)
    while [ "$(ls $DATA/iter_00/*.npz 2>/dev/null | wc -l)" -lt "$GAMES" ]; do sleep 60; done
    echo "[it$it] gen complete ($(ls $DATA/iter_00/*.npz 2>/dev/null | wc -l) npz) @ $(date)"
    date > "$OUT/done/gen$it"
  else
    echo "[it$it] gen — done, skip"
  fi

  # --- train the residual head on the co-adapted data ---
  if [ ! -f "$CKPT" ]; then
    echo "[it$it] train @ $(date)"
    nice -n 19 env $ENVV $PY -u scripts/train_iter.py \
      --output-root "$DATA" --warmstart-root "$WARMSTART_ROOT" \
      --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight 1.0 \
      --stage-local "/tmp/fw_stage_$it" --warm-from "$OUT/warm.pt" --output "$CKPT" --epochs 3
    rm -rf "/tmp/fw_stage_$it" 2>/dev/null || true
    [ -f "$CKPT" ] || { echo "[it$it] TRAIN FAILED — halting" >&2; exit 1; }
  fi

  # --- gate + keep-best ---
  ELO=$(run_gate "$CKPT" "iter$it")
  echo "[it$it] scale$SCALE elo = $ELO  (best so far = $BEST_ELO)"
  improved=$(echo "$ELO $BEST_ELO" | awk '{print ($1 > $2 + 10) ? 1 : 0}')   # +10 elo margin
  if [ "$improved" = "1" ]; then
    cp "$CKPT" "$OUT/best.pt"; BEST_ELO=$ELO; echo "$BEST_ELO" > "$OUT/best_elo.txt"; flat=0
    echo "[it$it] ✅ NEW BEST (climbed to $ELO) — flywheel is compounding"
  else
    flat=$((flat+1))
    echo "[it$it] ✗ no climb (flat=$flat/2); best stays $BEST_ELO"
    if [ "$flat" -ge 2 ]; then echo "[it$it] PLATEAU (2 flat iters) — stopping the flywheel" >&2; break; fi
  fi
done

echo ""; echo "=== FLYWHEEL DONE @ $(date): best scale$SCALE elo = $BEST_ELO (iter0 baseline was the residual net's +68) ==="
echo "    best ckpt: $OUT/best.pt  | gate dirs: $OUT/gate/"
echo "    ⚠️ in-ecosystem (vs HeuristicMCTS); confirm a winner on the out-of-lineage odometer before any strength claim."
