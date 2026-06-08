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
# FLYWHEEL_TAG lets a fresh attempt write to its own dir (so it does NOT resume the
# prior null run's iterN_data / done markers). Default = the original dir.
FLYWHEEL_TAG=${FLYWHEEL_TAG:-flywheel_residual}
OUT=$SHARE_LOCAL/$FLYWHEEL_TAG
OUTR=$SHARE_REMOTE/$FLYWHEEL_TAG
PY=$REPO_LOCAL/.venv/bin/python
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"
WARMSTART_ROOT=$REPO_LOCAL/data/warmstart/heuristic_tau05

SCALE=${SCALE:-0.25}; GAMES=${GAMES:-400}; SIMS=${SIMS:-200}
ITERS=${ITERS:-3}; N_GATE=${N_GATE:-300}; START=${START:-1}
# Late ITERS override: a control file at $OUT/ITERS_OVERRIDE wins over the passed env, so a
# long-running launcher's baked-in ITERS can be changed before the flywheel reaches its loop.
if [ -f "$OUT/ITERS_OVERRIDE" ]; then _ov=$(tr -dc 0-9 < "$OUT/ITERS_OVERRIDE" 2>/dev/null); case "$_ov" in ''|0) echo "  ITERS_OVERRIDE empty/0 — keeping ITERS=$ITERS" >&2 ;; *) ITERS=$_ov ;; esac; fi
GATE_SEED=${GATE_SEED:-1000000000}   # CLEAN-ruler namespace (≥ EVAL_SEED_FLOOR=1e9). eval_net_vs_heuristic HARD-ERRORS on seed<1e9 (overlaps self-play decks); was 900000 pre-clean-ruler.
# Out-of-lineage ODOMETER: every ODO_EVERY iters, run the current best (scale SCALE) vs
# heur@ODO_HEUR_SIMS (4× our depth, never-gated) on a DISTINCT clean seed → the CL-011
# out-of-lineage signal. LOGGED (→ $OUT/odometer.csv), NOT gated: keep-best stays on the
# fast in-ecosystem gate. heur@800 is the charter's ratified Track-B gating rung.
ODO_EVERY=${ODO_EVERY:-3}; ODO_N=${ODO_N:-200}; ODO_HEUR_SIMS=${ODO_HEUR_SIMS:-800}; ODO_SEED=${ODO_SEED:-1500000000}
# Overnight controls: KEEP_MARGIN = elo a new iter must beat best by to be kept
# (gate noise ~±21 at n=300, so default +12 ≈ 0.6σ — modest). DURATION_HOURS>0 =
# wall-clock budget; the loop won't START a new iter past start+DURATION_HOURS
# (last iter may overrun ~2h). 0 = no deadline (iter-count/plateau limited).
KEEP_MARGIN=${KEEP_MARGIN:-12}; DURATION_HOURS=${DURATION_HOURS:-0}
START_EPOCH=$(date +%s)
DEADLINE=0; [ "$DURATION_HOURS" != "0" ] && DEADLINE=$(awk -v s=$START_EPOCH -v h=$DURATION_HOURS 'BEGIN{printf "%d", s+h*3600}')
# iter0 = the confirmed residual net (Lever 1 winner).
ITER0_CKPT=$SHARE_LOCAL/lever_seq/ckpt/residual.pt

mkdir -p $OUT/ckpt $OUT/done $OUT/gate
cd $REPO_LOCAL || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
[ -f "$ITER0_CKPT" ] || { echo "FATAL: iter0 residual ckpt missing: $ITER0_CKPT" >&2; exit 1; }
echo "=== residual FLYWHEEL @ $(date): TAG=$FLYWHEEL_TAG ITERS=$START..$ITERS SCALE=$SCALE GAMES=$GAMES N_GATE=$N_GATE VLW=${VLW:-1.0} KEEP_MARGIN=$KEEP_MARGIN ==="

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
if n==0:
    print("-9999.0 0.0 0"); sys.exit()     # sentinel: no data → keep-best can never promote this
wr=(w+0.5*dd)/n
eps=0.5/n                                   # ±0.5-game continuity correction → wr never 0/1 → never nan
wr=min(1-eps, max(eps, wr))
elo=400*math.log10(wr/(1-wr)); sig=(400/math.log(10))*math.sqrt(wr*(1-wr)/n)/(wr*(1-wr))
print(f"{elo:.1f} {sig:.1f} {n}")
PY
}

# Remove STRANDED claims (a .claim with no .json = the claiming worker died, e.g. a
# killed/crashed eval) so those seeds can be re-claimed. Without this the gate count
# never reaches N_GATE and the wait loop spins forever (the shared-claim orphan-stall
# / 556-600 bug). $1=dir $2=only-if-older-than-min (0 = all; in-loop uses 4 to spare
# genuinely in-flight claims).
_clean_stranded() {   # $1=dir $2=output-ext(json|npz) $3=only-if-older-than-min (0=all)
  local dir="$1" ext="$2" age="${3:-0}" c
  if [ "$age" = "0" ]; then
    for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done
  else
    while IFS= read -r c; do [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done \
      < <(find "$dir" -name '*.claim' -mmin +"$age" 2>/dev/null)
  fi
}

# Launch the 3-box shared-claim eval for one (scale, subdir). $1=s $2=sub $3=rckpt $4=ckpt
_gate_launch() {
  local s="$1" sub="$2" rckpt="$3" ckpt="$4"
  nice -n 19 env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE="$s" $PY -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$ckpt" --n "$N_GATE" --sims "$SIMS" --heur-sims "$SIMS" --c-puct 3.0 --heur-leaf v2_7 \
    --workers 14 --out-root "$OUT/gate" --out-subdir "$sub" \
    --seed-start "$GATE_SEED" --paired --shared-claim --claim-host 5800x >/tmp/fw_gate5800x.log 2>&1 &
  ssh -o ConnectTimeout=20 laptop "cd $REPO_LAPTOP && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$s nice -n 19 $REPO_LAPTOP/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $N_GATE --sims $SIMS --heur-sims $SIMS --c-puct 3.0 --heur-leaf v2_7 --workers 14 --out-root $OUTR/gate --out-subdir $sub --seed-start $GATE_SEED --paired --shared-claim --claim-host laptop > /tmp/fw_gatelaptop.log 2>&1 </dev/null &" || echo "  gate laptop launch rc=$?" >&2
  ssh -o ConnectTimeout=20 xeon-wsl "cd $REPO_XEON && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$s setsid nice -n 19 $REPO_XEON/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $N_GATE --sims $SIMS --heur-sims $SIMS --c-puct 3.0 --heur-leaf v2_7 --workers 10 --out-root $OUTR/gate --out-subdir $sub --seed-start $GATE_SEED --paired --shared-claim --claim-host xeon > /tmp/fw_gatexeon.log 2>&1 </dev/null &" || echo "  gate xeon launch rc=$?" >&2
}

# Scale-curve gate (scale0 + scaleSCALE) fanned 3-box (~3× single-box: the eval is
# CPU-bound on the v2.7 leaf + per-worker GPU thrash). Self-heals the orphan-stall.
# $1=ckpt(5800x path) $2=label -> echoes scale0.25 elo.
run_gate() {
  local ckpt="$1" label="$2" s tag sub dir rckpt last stall cur
  rckpt=${ckpt/$SHARE_LOCAL/$SHARE_REMOTE}   # translate to remotes' mount
  for s in 0 $SCALE; do
    tag=$(knob_tag "$s"); sub="${label}_s${tag}"; dir="$OUT/gate/$sub"; mkdir -p "$dir"
    if [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -lt "$N_GATE" ]; then
      _clean_stranded "$dir" json 0      # pre-launch: free any stranded claims (resume after kill/crash)
      _gate_launch "$s" "$sub" "$rckpt" "$ckpt"
      last=-1; stall=0
      while [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -lt "$N_GATE" ]; do
        sleep 30
        cur=$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)
        if [ "$cur" -eq "$last" ]; then stall=$((stall+1)); else stall=0; last=$cur; fi
        if [ "$stall" -ge 12 ]; then      # ~6min no new game (>1 game-time) = workers died → heal
          echo "  [gate $sub] STALLED at $cur/$N_GATE — self-heal: clean stale claims + relaunch" >&2
          _clean_stranded "$dir" json 4; _gate_launch "$s" "$sub" "$rckpt" "$ckpt"; stall=0
        fi
      done
    fi
  done
  local s0 s25; s0=$(gate_elo "$OUT/gate/${label}_s0"); s25=$(gate_elo "$OUT/gate/${label}_s$(knob_tag $SCALE)")
  echo "  [gate $label] scale0=$s0 | scale$SCALE=$s25  (marginal=$(echo "$s25 $s0" | awk '{printf "%+.1f",$1-$4}'))" >&2
  echo "$s25" | awk '{print $1}'
}

# Launch the 3-box out-of-lineage odometer (best @scale SCALE vs heur@ODO_HEUR_SIMS, clean
# ODO_SEED). Same shared-claim machinery as the gate, but heur-sims=800 and a distinct seed.
_odo_launch() {   # $1=scale $2=sub $3=rckpt $4=ckpt
  local s="$1" sub="$2" rckpt="$3" ckpt="$4"
  nice -n 19 env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE="$s" $PY -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$ckpt" --n "$ODO_N" --sims "$SIMS" --heur-sims "$ODO_HEUR_SIMS" --c-puct 3.0 --heur-leaf v2_7 \
    --workers 14 --out-root "$OUT/odo" --out-subdir "$sub" \
    --seed-start "$ODO_SEED" --paired --shared-claim --claim-host 5800x >/tmp/fw_odo5800x.log 2>&1 &
  ssh -o ConnectTimeout=20 laptop "cd $REPO_LAPTOP && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$s nice -n 19 $REPO_LAPTOP/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $ODO_N --sims $SIMS --heur-sims $ODO_HEUR_SIMS --c-puct 3.0 --heur-leaf v2_7 --workers 14 --out-root $OUTR/odo --out-subdir $sub --seed-start $ODO_SEED --paired --shared-claim --claim-host laptop > /tmp/fw_odolaptop.log 2>&1 </dev/null &" || echo "  odo laptop launch rc=$?" >&2
  ssh -o ConnectTimeout=20 xeon-wsl "cd $REPO_XEON && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$s setsid nice -n 19 $REPO_XEON/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $ODO_N --sims $SIMS --heur-sims $ODO_HEUR_SIMS --c-puct 3.0 --heur-leaf v2_7 --workers 10 --out-root $OUTR/odo --out-subdir $sub --seed-start $ODO_SEED --paired --shared-claim --claim-host xeon > /tmp/fw_odoxeon.log 2>&1 </dev/null &" || echo "  odo xeon launch rc=$?" >&2
}

# Out-of-lineage odometer for one iter: best @SCALE vs heur@ODO_HEUR_SIMS. Self-heals the
# orphan-stall (heur@800 games are slow → 10-min stall threshold). Logs elo + appends odometer.csv.
run_odometer() {   # $1=ckpt(5800x path) $2=iter-label
  local ckpt="$1" it="$2" rckpt sub dir last stall cur res
  rckpt=${ckpt/$SHARE_LOCAL/$SHARE_REMOTE}
  sub="odo_iter${it}"; dir="$OUT/odo/$sub"; mkdir -p "$dir"
  if [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -lt "$ODO_N" ]; then
    _clean_stranded "$dir" json 0
    _odo_launch "$SCALE" "$sub" "$rckpt" "$ckpt"
    last=-1; stall=0
    while [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -lt "$ODO_N" ]; do
      sleep 30
      cur=$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)
      if [ "$cur" -eq "$last" ]; then stall=$((stall+1)); else stall=0; last=$cur; fi
      if [ "$stall" -ge 20 ]; then    # ~10min no new game (heur@800 is slow) = workers died → heal
        echo "  [odo $sub] STALLED at $cur/$ODO_N — self-heal: clean stale claims + relaunch" >&2
        _clean_stranded "$dir" json 4; _odo_launch "$SCALE" "$sub" "$rckpt" "$ckpt"; stall=0
      fi
    done
  fi
  res=$(gate_elo "$dir")   # "elo sigma n" (sigma is unpaired/conservative; raw JSON saved for paired re-tally)
  echo "  [ODOMETER it$it] best(scale$SCALE) vs heur@${ODO_HEUR_SIMS} = $res elo  | OUT-OF-LINEAGE (charter bar: +15/iter, cum +45; iter0 baseline was ~ -29 vs heur@800)" >&2
  echo "${it},$(echo "$res" | tr ' ' ',')" >> "$OUT/odometer.csv"
}

# Launch the 3-box residual self-play gen for iter $1 (work-stealing into iter${1}_data).
_gen_launch() {
  local it="$1"
  SHARE=$SHARE_LOCAL REPO=$REPO_LOCAL HOST=5800x WORKERS=14 WARM=$OUT/warm.pt OUT=$OUT/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS \
    nohup nice -n 19 bash $SHARE_LOCAL/code_sync/gen_flywheel.sh > /tmp/fw_gen5800x_$it.log 2>&1 & disown
  ssh -o ConnectTimeout=20 laptop "SHARE=$SHARE_REMOTE REPO=$REPO_LAPTOP HOST=laptop WORKERS=14 WARM=$OUTR/warm.pt OUT=$OUTR/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS setsid nice -n 19 bash $SHARE_REMOTE/code_sync/gen_flywheel.sh > /tmp/fw_genlaptop_$it.log 2>&1 </dev/null &" || echo "[it$it] laptop launch rc=$?"
  ssh -o ConnectTimeout=20 xeon-wsl "SHARE=$SHARE_REMOTE REPO=$REPO_XEON HOST=xeon WORKERS=10 WARM=$OUTR/warm.pt OUT=$OUTR/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS setsid nice -n 19 bash $SHARE_REMOTE/code_sync/gen_flywheel.sh > /tmp/fw_genxeon_$it.log 2>&1 </dev/null &" || echo "[it$it] xeon launch rc=$?"
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
  echo "--- iter0 out-of-lineage odometer (clean baseline) @ $(date) ---"
  [ "$ODO_EVERY" -gt 0 ] && run_odometer "$OUT/best.pt" "0"
fi

flat=0
for it in $(seq $START $ITERS); do
  if [ "$DEADLINE" -gt 0 ] && [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "=== DEADLINE reached ($DURATION_HOURS h) — not starting iter $it; winding down ==="; break
  fi
  echo ""; echo "########## FLYWHEEL ITER $it @ $(date) (warm from best, elo=$BEST_ELO) ##########"
  DATA=$OUT/iter${it}_data; CKPT=$OUT/ckpt/iter${it}.pt
  cp "$OUT/best.pt" "$OUT/warm.pt"

  # --- 3-box residual self-play (work-stealing), self-healing the orphan-stall ---
  if [ ! -f "$OUT/done/gen$it" ]; then
    echo "[it$it] launch 3-box residual gen @ $(date)"
    mkdir -p "$DATA/iter_00"; _clean_stranded "$DATA/iter_00" npz 0   # resume: free stranded claims
    _gen_launch "$it"
    glast=-1; gstall=0
    while [ "$(ls $DATA/iter_00/*.npz 2>/dev/null | wc -l)" -lt "$GAMES" ]; do
      sleep 60
      gcur=$(ls $DATA/iter_00/*.npz 2>/dev/null | wc -l)
      if [ "$gcur" -eq "$glast" ]; then gstall=$((gstall+1)); else gstall=0; glast=$gcur; fi
      if [ "$gstall" -ge 6 ]; then        # ~6min no new npz = gen workers died → heal
        echo "[it$it] gen STALLED at $gcur/$GAMES — self-heal: clean stale claims + relaunch" >&2
        _clean_stranded "$DATA/iter_00" npz 4; _gen_launch "$it"; gstall=0
      fi
    done
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
      --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight ${VLW:-1.0} \
      --stage-local "/tmp/fw_stage_$it" --warm-from "$OUT/warm.pt" --output "$CKPT" --epochs 3 \
      --prov-value-target residual --prov-selfplay-leaf "v2_7+residual${SCALE}" \
      --prov-seed-range "0-$((GAMES-1))" --prov-run-tag "flywheel_residual_it${it}"
    rm -rf "/tmp/fw_stage_$it" 2>/dev/null || true
    [ -f "$CKPT" ] || { echo "[it$it] TRAIN FAILED — halting" >&2; exit 1; }
  fi

  # --- gate + keep-best ---
  ELO=$(run_gate "$CKPT" "iter$it")
  echo "[it$it] scale$SCALE elo = $ELO  (best so far = $BEST_ELO)"
  improved=$(awk -v e="$ELO" -v b="$BEST_ELO" -v m="$KEEP_MARGIN" 'BEGIN{el=tolower(e);bl=tolower(b); if(e==""||b==""||el~/nan|inf/||bl~/nan|inf/){print 0;exit} print (e+0>b+0+m+0)?1:0}')
  if [ "$improved" = "1" ]; then
    cp "$CKPT" "$OUT/best.pt"; BEST_ELO=$ELO; echo "$BEST_ELO" > "$OUT/best_elo.txt"; flat=0
    echo "[it$it] ✅ NEW BEST (climbed to $ELO) — flywheel is compounding"
  else
    flat=$((flat+1))
    echo "[it$it] ✗ no climb (flat=$flat/2); best stays $BEST_ELO"
    if [ "$flat" -ge 2 ]; then echo "[it$it] PLATEAU (2 flat iters) — stopping the flywheel" >&2; break; fi
  fi

  # --- out-of-lineage odometer every ODO_EVERY iters (LOGGED, not gated) ---
  if [ "$ODO_EVERY" -gt 0 ] && [ $(( it % ODO_EVERY )) -eq 0 ]; then
    echo "[it$it] === out-of-lineage odometer: best vs heur@${ODO_HEUR_SIMS} (clean seed $ODO_SEED, n=$ODO_N) @ $(date) ==="
    run_odometer "$OUT/best.pt" "$it"
  fi
done

echo ""; echo "=== FLYWHEEL DONE @ $(date): best scale$SCALE elo = $BEST_ELO (iter0 baseline was the residual net's +68) ==="
echo "    best ckpt: $OUT/best.pt  | gate dirs: $OUT/gate/"
echo "    ⚠️ in-ecosystem (vs HeuristicMCTS); confirm a winner on the out-of-lineage odometer before any strength claim."
