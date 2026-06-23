#!/usr/bin/env bash
# ============================================================================
# RoD v2.8 OVERNIGHT FLYWHEEL — latest-chain exploratory continuation from RoD_iter_01.
#
# Goal: run as many continuation iters as fit overnight (target 10-15), warm-from the
# PREVIOUS iter each time (latest-chain), using the EXACT validated v2.8 recipe that
# produced RoD_iter_01 — NO recipe changes:
#   leaf = v2.8 (v2.7 + meeple_k=2.0, CARCASSONNE_V25_MEEPLE_K=2.0, flat fast path)
#   batch 256 · 3 epochs · lr 1e-3 · AdamW wd 1e-4 · VLW 1.5 · residual_scale 0.25
#   NeuralMCTS sims=200 · c_puct=3.0 · 96x6 ResNet · games/iter=400 (attempt-2 flywheel cadence)
#
# Per iter: 2-box work-stealing self-play gen (carc-orch SHM, high W) -> local train ->
#           CHEAP screens (train-loss/entropy/collapse + tiny n=40 paired SMOKE vs prev) ->
#           manifest/log/csv append. NO expensive evals overnight (heur@3200 etc deferred
#           to tomorrow on selected checkpoints).
#
# Catastrophe -> STOP cleanly, preserve ALL partial artifacts. Self-heals gen stalls.
# MEASUREMENT ONLY: no promotion, PRODUCTION.yaml untouched, champion unchanged, v2.7 frozen.
#
# Launch (detached, overnight):
#   nohup nice -n 19 bash scripts/rod_v28/run_overnight_flywheel.sh > /tmp/rod_overnight.log 2>&1 & disown
# ============================================================================
set -uo pipefail

# --- paths ---
SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
REPO_LOCAL=/home/doctor/projects/carcassone
REPO_LAPTOP=/home/doctor/projects/carcassone
LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}
PY=$REPO_LOCAL/.venv/bin/python
TAG=${TAG:-rod_v28_overnight_flywheel}
OUT=$SHARE_LOCAL/$TAG
OUTR=$SHARE_REMOTE/$TAG
MEASURE=$REPO_LOCAL/measurement/$TAG
WARMSTART_ROOT=$REPO_LOCAL/data/warmstart/heuristic_tau05
SEED_ITER01=${SEED_ITER01:-$SHARE_LOCAL/rod_v28_continuation/ckpt/iter_01.pt}   # RoD_iter_01 = warm-from for it=2
SEED_ITER01_ID=${SEED_ITER01_ID:-RoD_iter_01}
SCREEN=$REPO_LOCAL/scripts/rod_v28/overnight_iter_screen.py

# --- THE FROZEN v2.8 RECIPE (do NOT change) ---
MEEPLE_K=2.0; SCALE=${SCALE:-0.25}; SIMS=${SIMS:-200}; CPUCT=3.0
GAMES=${GAMES:-400}; EPOCHS=3; BATCH=256; VLW=1.5

# --- worker counts (orch, per box). User dir: local 48 / laptop 26 (laptop smoke-validated). ---
OW_LOCAL=${OW_LOCAL:-48}
OW_LAPTOP=${OW_LAPTOP:-26}
USE_LAPTOP=${USE_LAPTOP:-1}

# --- loop control ---
START=${START:-2}                       # produce iter_02 .. iter_$ITERS (latest-chain from RoD_iter_01)
ITERS=${ITERS:-14}
DURATION_HOURS=${DURATION_HOURS:-10}
SP_BASE=${SP_BASE:-620000000}           # self-play seed bands (<1e9), per-iter disjoint
SMOKE_BASE=${SMOKE_BASE:-1940000000}    # smoke eval bands (>=1e9 floor), per-iter disjoint
DO_SMOKE=${DO_SMOKE:-1}
SMOKE_N=${SMOKE_N:-40}                   # tiny paired smoke (catastrophe detector ONLY, not a verdict)
SMOKE_OW=${SMOKE_OW:-22}                 # per-server workers for the two-context LOCAL smoke
SMOKE_TIMEOUT=${SMOKE_TIMEOUT:-1200}
SMOKE_CATASTROPHE_WR=${SMOKE_CATASTROPHE_WR:-0.25}

# --- self-heal ---
HEAL_CAP=${HEAL_CAP:-8}; STALL_GEN=${STALL_GEN:-15}   # 15 polls x 60s = 15 min no-progress -> heal

START_EPOCH=$(date +%s)
DEADLINE=0; [ "$DURATION_HOURS" != "0" ] && DEADLINE=$(( START_EPOCH + DURATION_HOURS*3600 ))

mkdir -p "$OUT/ckpt" "$OUT/done" "$OUT/smoke" "$OUT/logs" "$MEASURE"
cd "$REPO_LOCAL" || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
[ -f "$SEED_ITER01" ] || { echo "FATAL: RoD_iter_01 warm-from missing: $SEED_ITER01" >&2; exit 1; }

# ----------------------------------------------------------------------------
_status() {   # write the live OVERNIGHT_STATUS.md
  local state="$1" detail="$2"
  cat > "$MEASURE/OVERNIGHT_STATUS.md" <<EOF
# RoD v2.8 Overnight Flywheel — LIVE STATUS

**State:** $state
**Updated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Branch:** rod_v28_overnight_flywheel · **Tag:** $TAG
**Deadline:** $( [ "$DEADLINE" = 0 ] && echo "none" || date -u -d @"$DEADLINE" +%Y-%m-%dT%H:%M:%SZ ) ($DURATION_HOURS h)

$detail

---
- Recipe (FROZEN): v2.8 leaf (meeple_k=$MEEPLE_K) · batch $BATCH · $EPOCHS epochs · VLW $VLW · residual_scale $SCALE · sims $SIMS · c_puct $CPUCT · games/iter $GAMES
- Lineage: latest-chain $SEED_ITER01_ID → iter_02 → … (warm-from previous iter)
- Workers (orch): local W$OW_LOCAL · laptop W$OW_LAPTOP ($([ "$USE_LAPTOP" = 1 ] && echo enabled || echo DISABLED))
- Live deliverables: CHECKPOINT_MANIFEST.json · TRAINING_LOG_SUMMARY.md · CHEAP_SCREEN_RESULTS.csv
- Checkpoints: \`$OUT/ckpt/iter_*.pt\` (all retained) · logs \`$OUT/logs/\`
- MEASUREMENT ONLY — no promotion, PRODUCTION.yaml unchanged, champion unchanged, v2.7 frozen.
EOF
}

_share_writable() { ( touch "$SHARE_LOCAL/.rodov_probe" 2>/dev/null && rm -f "$SHARE_LOCAL/.rodov_probe" 2>/dev/null ); }

_kill_one() {   # bracket 1st char so the regex matches workers but never the pkill shell itself
  local pat="[${1:0:1}]${1:1}"
  pkill -9 -f "$pat" 2>/dev/null || true
  [ "$USE_LAPTOP" = 1 ] && timeout 20 ssh -o ConnectTimeout=10 "$LAPTOP_SSH" "pkill -9 -f '$pat'" </dev/null >/dev/null 2>&1 || true
}
_kill_gen() {   # full reset of the gen pools + orch servers on BOTH boxes (heal / cleanup)
  _kill_one run_selfplay_iter
  _kill_one gen_flywheel
  _kill_one carc-orch
}

_clean_stranded() {   # $1=dir $2=ext $3=age-min(0=all): remove .claim files with no matching output
  local dir="$1" ext="$2" age="${3:-0}" c
  if [ "$age" = "0" ]; then
    for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done
  else
    while IFS= read -r c; do [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done \
      < <(find "$dir" -name '*.claim' -mmin +"$age" 2>/dev/null)
  fi
}

_ssh_bg() {   # detached remote launch; treat WSL rc=124 (held-open channel) as LAUNCHED, never retry
  local host="$1" cmd="$2" label="$3" try rc
  for try in 1 2 3; do
    timeout 45 ssh -o ConnectTimeout=20 "$host" "$cmd" </dev/null && return 0
    rc=$?
    [ "$rc" = "124" ] && { echo "  $label launched (detached; ssh held open, rc=124 — not retried)"; return 0; }
    [ "$rc" = "255" ] || { echo "  $label launch rc=$rc"; return "$rc"; }
    echo "  $label ssh rc=255 (try $try/3) — retry"; sleep 3
  done
  echo "  $label ssh FAILED after 3 tries (box dropped this iter)"; return 255
}

# Launch the 2-box v2.8 work-stealing self-play gen for iter $1 (seed $2; parent ckpt local $3 / remote $4).
_gen_launch() {
  local it="$1" sp_seed="$2" warm_l="$3" warm_r="$4"
  CARCASSONNE_V25_MEEPLE_K=$MEEPLE_K SHARE=$SHARE_LOCAL REPO=$REPO_LOCAL HOST=5800x USE_ORCH=1 ORCH_WORKERS=$OW_LOCAL \
    WARM=$warm_l OUT=$OUT/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS SEED_START=$sp_seed \
    nohup nice -n 19 bash $SHARE_LOCAL/code_sync/gen_flywheel.sh > "$OUT/logs/gen5800x_it${it}.log" 2>&1 & disown
  [ "$USE_LAPTOP" = 1 ] && _ssh_bg "$LAPTOP_SSH" \
    "CARCASSONNE_V25_MEEPLE_K=$MEEPLE_K SHARE=$SHARE_REMOTE REPO=$REPO_LAPTOP HOST=laptop USE_ORCH=1 ORCH_WORKERS=$OW_LAPTOP WARM=$warm_r OUT=$OUTR/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS SEED_START=$sp_seed setsid nice -n 19 bash $SHARE_REMOTE/code_sync/gen_flywheel.sh > /tmp/rodov_gen_laptop_it${it}.log 2>&1 </dev/null &" \
    "[it$it] laptop gen" &
}

# Final cleanup on ANY exit — kill orphans, leave a clean status.
_FINALIZED=0
_finalize() {
  [ "$_FINALIZED" = 1 ] && return; _FINALIZED=1
  _kill_gen
  echo "=== overnight flywheel exiting @ $(date) (cleaned gen pools + orch on both boxes) ==="
}
trap _finalize EXIT
trap 'echo "[signal] caught TERM/INT @ $(date) — finalizing"; _status "INTERRUPTED" "Caught a termination signal; gen pools cleaned, all completed checkpoints + manifests preserved under \`$OUT/ckpt\`."; exit 130' INT TERM

# ----------------------------------------------------------------------------
echo "=== RoD v2.8 OVERNIGHT FLYWHEEL @ $(date) — TAG=$TAG iters $START..$ITERS games=$GAMES deadline=${DURATION_HOURS}h ==="
echo "    recipe: v2.8 leaf meeple_k=$MEEPLE_K · batch $BATCH · $EPOCHS ep · VLW $VLW · scale $SCALE · sims $SIMS · cpuct $CPUCT"
echo "    workers: local W$OW_LOCAL  laptop W$OW_LAPTOP (use_laptop=$USE_LAPTOP)"

# Fresh code bundle so the laptop gen runs current (== stage-b-wiring) gen code.
# gen_flywheel.sh on remotes hard-fetches carc_stage-b-wiring.bundle / ref stage-b-wiring.
git bundle create "$SHARE_LOCAL/code_sync/carc_stage-b-wiring.bundle" stage-b-wiring >/dev/null 2>&1 \
  && echo "  bundle tip: $(git rev-parse --short stage-b-wiring)" || echo "  WARN: bundle create failed"
if [ "$USE_LAPTOP" = 1 ]; then
  if timeout 40 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
       "cd $REPO_LAPTOP && git fetch $SHARE_REMOTE/code_sync/carc_stage-b-wiring.bundle stage-b-wiring && git reset --hard FETCH_HEAD" \
       </dev/null >/dev/null 2>&1; then
    echo "  laptop synced to $(git rev-parse --short stage-b-wiring)"
  else
    echo "  WARN: laptop sync FAILED — disabling laptop, running LOCAL-ONLY gen (night not wasted on stale code)"
    USE_LAPTOP=0
  fi
fi

_status "RUNNING" "Starting iter $START. No iteration completed yet."

COMPLETED=0
for it in $(seq "$START" "$ITERS"); do
  if [ "$DEADLINE" -gt 0 ] && [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "=== DEADLINE reached (${DURATION_HOURS}h) — not starting iter $it ==="; break
  fi
  if [ -f "$OUT/done/iter$it" ]; then echo "[it$it] already complete — skip"; COMPLETED=$((COMPLETED+1)); continue; fi

  # parent (latest-chain)
  if [ "$it" -eq 2 ]; then
    PREV_CKPT=$SEED_ITER01; PREV_ID=$SEED_ITER01_ID
  else
    pp=$(printf "%02d" $((it-1))); PREV_CKPT=$OUT/ckpt/iter_${pp}.pt; PREV_ID="RoD_iter_${pp}"
  fi
  PREV_CKPT_R=${PREV_CKPT/$SHARE_LOCAL/$SHARE_REMOTE}
  [ -s "$PREV_CKPT" ] || { echo "[it$it] FATAL: parent $PREV_CKPT missing/empty" >&2; _status "ERROR" "iter $it: parent checkpoint $PREV_ID missing — stopping."; exit 1; }
  cc=$(printf "%02d" "$it"); CKPT=$OUT/ckpt/iter_${cc}.pt; DATA=$OUT/iter${it}_data
  SP_SEED=$(( SP_BASE + it*100000 ))
  echo ""; echo "########## OVERNIGHT ITER $it -> RoD_iter_${cc} @ $(date) (warm from $PREV_ID) ##########"
  _status "RUNNING" "iter $it (RoD_iter_${cc}) IN PROGRESS — warm from $PREV_ID. Completed so far: $COMPLETED. Stage: gen."

  # ---- self-play gen (2-box work-stealing, v2.8) ----
  GEN_T0=$(date +%s)
  if [ ! -f "$OUT/done/gen$it" ]; then
    echo "[it$it] gen seed_start=$SP_SEED -> $DATA/iter_00 @ $(date)"
    mkdir -p "$DATA/iter_00"; _clean_stranded "$DATA/iter_00" npz 0
    _kill_gen; sleep 2
    _gen_launch "$it" "$SP_SEED" "$PREV_CKPT" "$PREV_CKPT_R"
    glast=-1; gstall=0; gheals=0
    while [ "$(ls "$DATA"/iter_00/*.npz 2>/dev/null | wc -l)" -lt "$GAMES" ]; do
      sleep 60
      if [ "$DEADLINE" -gt 0 ] && [ "$(date +%s)" -ge "$DEADLINE" ]; then
        echo "[it$it] DEADLINE hit mid-gen ($(ls "$DATA"/iter_00/*.npz 2>/dev/null|wc -l)/$GAMES) — abandoning this partial iter"
        _kill_gen; _status "DEADLINE" "Stopped mid-gen on iter $it (partial, discarded). Completed iters: $COMPLETED."; exit 0
      fi
      gcur=$(ls "$DATA"/iter_00/*.npz 2>/dev/null | wc -l)
      if [ "$gcur" -eq "$glast" ]; then gstall=$((gstall+1)); else gstall=0; glast=$gcur; fi
      if [ "$gstall" -ge "$STALL_GEN" ]; then
        gheals=$((gheals+1))
        [ "$gheals" -gt "$HEAL_CAP" ] && { echo "[it$it] FATAL: $gheals gen heals, stuck $gcur/$GAMES" >&2; _status "ERROR" "iter $it gen stuck at $gcur/$GAMES after $HEAL_CAP heals. Completed: $COMPLETED."; exit 1; }
        _share_writable || { echo "[it$it] share not writable — backing off (heal $gheals)"; continue; }
        echo "[it$it] gen STALLED $gcur/$GAMES — heal $gheals: kill+clean+relaunch @ $(date)"
        _kill_gen; sleep 2; _clean_stranded "$DATA/iter_00" npz 30
        _gen_launch "$it" "$SP_SEED" "$PREV_CKPT" "$PREV_CKPT_R"; gstall=0
      fi
    done
    _kill_gen; sleep 1   # gen done -> tear down pools/servers so train has the GPU
    GEN_NPZ=$(ls "$DATA"/iter_00/*.npz 2>/dev/null | wc -l)
    echo "[it$it] gen complete ($GEN_NPZ npz) @ $(date)"
    date > "$OUT/done/gen$it"
  else
    echo "[it$it] gen — done, skip"
    GEN_NPZ=$(ls "$DATA"/iter_00/*.npz 2>/dev/null | wc -l)
  fi
  GEN_SEC=$(( $(date +%s) - GEN_T0 ))

  # ---- train (LOCAL only; batch 256, 3 epochs, VLW 1.5, v2.8 prov) ----
  _status "RUNNING" "iter $it (RoD_iter_${cc}) — gen done ($GEN_NPZ npz). Stage: train. Completed: $COMPLETED."
  TR_T0=$(date +%s)
  if [ ! -f "$CKPT" ]; then
    echo "[it$it] train @ $(date)"
    nice -n 19 env CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 \
      "$PY" -u scripts/train_iter.py \
      --output-root "$DATA" --warmstart-root "$WARMSTART_ROOT" \
      --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight "$VLW" --batch-size "$BATCH" \
      --stage-local "/tmp/rodov_stage_$it" --warm-from "$PREV_CKPT" --output "$CKPT" --epochs "$EPOCHS" \
      --prov-value-target residual --prov-selfplay-leaf v2_8_meeple_k2 \
      --prov-seed-range "${SP_SEED}-$((SP_SEED+GAMES-1))" --prov-run-tag "rod_v28_overnight_it${it}" \
      > "$OUT/logs/train_it${it}.log" 2>&1
    rm -rf "/tmp/rodov_stage_$it" 2>/dev/null || true
    [ -f "$CKPT" ] || { echo "[it$it] TRAIN FAILED — halting" >&2; tail -20 "$OUT/logs/train_it${it}.log" >&2; _status "ERROR" "iter $it train FAILED (see logs/train_it${it}.log). Completed: $COMPLETED."; exit 1; }
  else
    echo "[it$it] train — ckpt exists, skip"
  fi
  TRAIN_SEC=$(( $(date +%s) - TR_T0 ))
  [ -f "$CKPT.metrics.json" ] || CKPT_METRICS="${CKPT%.pt}.metrics.json"
  CKPT_METRICS="${CKPT%.pt}.metrics.json"

  # ---- cheap SMOKE (LOCAL-only two-context net-vs-net, new vs prev) — catastrophe detector ONLY ----
  SMOKE_DIR=""
  if [ "$DO_SMOKE" = 1 ] && [ "$(date +%s)" -lt "$((DEADLINE>0?DEADLINE:9999999999))" ]; then
    _status "RUNNING" "iter $it (RoD_iter_${cc}) — trained. Stage: smoke (n=$SMOKE_N vs $PREV_ID). Completed: $COMPLETED."
    SMOKE_SEED=$(( SMOKE_BASE + it*100000 )); SMOKE_SUB="it${it}_vs_prev"
    echo "[it$it] smoke n=$SMOKE_N RoD_iter_${cc} vs $PREV_ID seed=$SMOKE_SEED @ $(date)"
    CKPT_A="$CKPT" CKPT_B="$PREV_CKPT" OW="$SMOKE_OW" SIMS="$SIMS" \
      timeout "$SMOKE_TIMEOUT" nice -n 19 bash scripts/heuristic_v28/v28_net_vs_net_orch.sh \
        --n "$SMOKE_N" --paired --c-puct "$CPUCT" --residual-scale "$SCALE" \
        --meeple-k-a "$MEEPLE_K" --meeple-k-b "$MEEPLE_K" --seed-start "$SMOKE_SEED" \
        --out-root "$OUT/smoke" --out-subdir "$SMOKE_SUB" \
        > "$OUT/logs/smoke_it${it}.log" 2>&1 \
      && SMOKE_DIR="$OUT/smoke/$SMOKE_SUB" \
      || { echo "[it$it] smoke had issues (non-fatal) — continuing with train-metrics screen only"; SMOKE_DIR="$OUT/smoke/$SMOKE_SUB"; }
    pkill -9 -f "[c]arc-orch" 2>/dev/null || true
  fi

  # ---- screen + manifest/log/csv ----
  echo "[it$it] screen @ $(date)"
  "$PY" "$SCREEN" --iter "$it" --ckpt "$CKPT" --metrics "$CKPT_METRICS" \
    --parent-ckpt "$PREV_CKPT" --parent-id "$PREV_ID" --measure-dir "$MEASURE" \
    --sp-seed "$SP_SEED" --games "$GAMES" --gen-npz "${GEN_NPZ:-0}" \
    --gen-sec "$GEN_SEC" --train-sec "$TRAIN_SEC" \
    --smoke-dir "$SMOKE_DIR" --smoke-seed "${SMOKE_SEED:-}" \
    --smoke-catastrophe-wr "$SMOKE_CATASTROPHE_WR"
  SCREEN_RC=$?

  date > "$OUT/done/iter$it"; COMPLETED=$((COMPLETED+1))
  if [ "$SCREEN_RC" = 3 ]; then
    echo "[it$it] ⚠️ CATASTROPHE (collapse) — stopping the chain, preserving all artifacts @ $(date)"
    _status "STOPPED-CATASTROPHE" "iter $it (RoD_iter_${cc}) tripped the COLLAPSE screen (see CHEAP_SCREEN_RESULTS.csv / TRAINING_LOG_SUMMARY.md). Chain STOPPED at last-sane = $PREV_ID. Completed healthy iters: $((COMPLETED-1)). All checkpoints preserved under \`$OUT/ckpt\`."
    break
  fi
  echo "[it$it] ✅ iter complete (screen HEALTHY/AMBIGUOUS) @ $(date) — chain advances to RoD_iter_${cc}"
  _status "RUNNING" "Last completed: RoD_iter_${cc} (iter $it). Total completed: $COMPLETED. Next: iter $((it+1))."
done

LAST=$(ls "$OUT"/ckpt/iter_*.pt 2>/dev/null | sort | tail -1)
echo ""; echo "=== RoD v2.8 OVERNIGHT FLYWHEEL DONE @ $(date) — completed $COMPLETED iters; latest ckpt: $LAST ==="
_status "DONE" "Run finished. Completed $COMPLETED iteration(s). Latest checkpoint: \`$LAST\`. All checkpoints retained under \`$OUT/ckpt\`. See CHECKPOINT_MANIFEST.json + CHEAP_SCREEN_RESULTS.csv + TRAINING_LOG_SUMMARY.md. Tomorrow: serious evals (vs RoD_iter_01, vs frozen ITER8_V28_PARENT, vs heur@3200_v2.8) on selected checkpoints."
