#!/usr/bin/env bash
# ============================================================================
# RoD v2 FLYWHEEL — latest-chain continuation from RoD_iter_01 with the FROZEN
# v2.9 leaf (Bmild_cap8) swapped in for v2.8.
#
# Recipe == the validated RoD v2.8 overnight recipe, ONE change: the heuristic leaf
# is the frozen v2.9 classical substrate (governance/LEAF_SUBSTRATES.yaml
# v2_9_bmild_cap8) — nonlinear meeple liquidity CURVE (-8,-4,-1,0,2,3,4,5) REPLACES
# flat meeple_k, bonus_cap=8, 3-open closure. Everything else held:
#   batch 256 · 3 epochs · lr 1e-3 · AdamW wd 1e-4 · VLW 1.5 · residual_scale 0.25
#   NeuralMCTS sims=200 · c_puct=3.0 · 96x6 ResNet · games/iter=400
#
# Per iter: 2-box (local+laptop) work-stealing self-play gen (carc-orch SHM, high W,
#           v2.9 leaf) -> local train (warm-from previous iter) -> train-metrics
#           collapse screen + manifest/log/csv. GEN + TRAIN ONLY — NO eval between
#           iters (DO_SMOKE=0). 12 iters (RoD_iter_02 .. RoD_iter_13).
#
# Catastrophe (train collapse) -> STOP cleanly, preserve ALL partial artifacts.
# MEASUREMENT/EXPLORATORY: no promotion, PRODUCTION.yaml untouched, champion unchanged,
# v2.7 frozen, v2.8 production, v2.9 opt-in. Authorized by Joshua (RoD v2 directive).
#
# Launch (detached):
#   nohup nice -n 19 bash scripts/rod_v2/run_rod_v2_flywheel.sh > /tmp/rod_v2.log 2>&1 & disown
# ============================================================================
set -uo pipefail

# --- paths ---
SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
REPO_LOCAL=/home/doctor/projects/carcassone
REPO_LAPTOP=/home/doctor/projects/carcassone
LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}
PY=$REPO_LOCAL/.venv/bin/python
TAG=${TAG:-rod_v2_flywheel}
BRANCH=${BRANCH:-rod_v2_flywheel}
OUT=$SHARE_LOCAL/$TAG
OUTR=$SHARE_REMOTE/$TAG
MEASURE=$REPO_LOCAL/measurement/$TAG
WARMSTART_ROOT=$REPO_LOCAL/data/warmstart/heuristic_tau05
SEED_ITER01=${SEED_ITER01:-$SHARE_LOCAL/rod_v28_continuation/ckpt/iter_01.pt}   # RoD_iter_01 = warm-from for it=2
SEED_ITER01_ID=${SEED_ITER01_ID:-RoD_iter_01}
SCREEN=$REPO_LOCAL/scripts/rod_v28/overnight_iter_screen.py
GENV29=$SHARE_LOCAL/code_sync/gen_flywheel_v29.sh
GENV29_R=$SHARE_REMOTE/code_sync/gen_flywheel_v29.sh

# --- THE v2.9 LEAF (frozen Bmild_cap8) + recipe (do NOT change) ---
V29_CURVE="-8,-4,-1,0,2,3,4,5"
SCALE=${SCALE:-0.25}; SIMS=${SIMS:-200}; CPUCT=3.0
GAMES=${GAMES:-400}; EPOCHS=3; BATCH=256; VLW=1.5

# --- GEN worker counts (orch, per box) — gen W, NOT eval W (gen trees are heavier) ---
OW_LOCAL=${OW_LOCAL:-28}
OW_LAPTOP=${OW_LAPTOP:-8}
USE_LAPTOP=${USE_LAPTOP:-1}

# --- loop control: 12 iters RoD_iter_02..iter_13, latest-chain from RoD_iter_01 ---
START=${START:-2}
ITERS=${ITERS:-13}
DURATION_HOURS=${DURATION_HOURS:-0}     # 0 = run all 12 iters (no deadline)
SP_BASE=${SP_BASE:-640000000}           # v2 self-play seed band (distinct from v2.8 overnight's 620M); <1e9
DO_SMOKE=${DO_SMOKE:-0}                  # GEN+TRAIN ONLY — no eval/games between iters (Joshua's directive)

# --- self-heal ---
HEAL_CAP=${HEAL_CAP:-8}; STALL_GEN=${STALL_GEN:-15}

START_EPOCH=$(date +%s)
DEADLINE=0; [ "$DURATION_HOURS" != "0" ] && DEADLINE=$(( START_EPOCH + DURATION_HOURS*3600 ))

mkdir -p "$OUT/ckpt" "$OUT/done" "$OUT/logs" "$MEASURE"
cd "$REPO_LOCAL" || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
[ -f "$SEED_ITER01" ] || { echo "FATAL: RoD_iter_01 warm-from missing: $SEED_ITER01" >&2; exit 1; }
[ -f "$GENV29" ] || { echo "FATAL: v2.9 gen script not deployed to share: $GENV29" >&2; exit 1; }

# ----------------------------------------------------------------------------
_status() {
  local state="$1" detail="$2"
  cat > "$MEASURE/RODV2_STATUS.md" <<EOF
# RoD v2 Flywheel (v2.9 leaf Bmild_cap8) — LIVE STATUS

**State:** $state
**Updated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Branch:** $BRANCH · **Tag:** $TAG
**Deadline:** $( [ "$DEADLINE" = 0 ] && echo "none (run all iters)" || date -u -d @"$DEADLINE" +%Y-%m-%dT%H:%M:%SZ )

$detail

---
- Leaf (FROZEN v2.9): Bmild_cap8 — curve $V29_CURVE replaces flat meeple · cap 8 · 3-open
- Recipe (FROZEN): batch $BATCH · $EPOCHS epochs · VLW $VLW · residual_scale $SCALE · sims $SIMS · c_puct $CPUCT · games/iter $GAMES
- Lineage: latest-chain $SEED_ITER01_ID → iter_02 → … (warm-from previous iter)
- Workers (orch, GEN): local W$OW_LOCAL · laptop W$OW_LAPTOP ($([ "$USE_LAPTOP" = 1 ] && echo enabled || echo DISABLED))
- GEN + TRAIN ONLY — no eval between iters. Checkpoints: \`$OUT/ckpt/iter_*.pt\` (all retained).
- MEASUREMENT/EXPLORATORY — no promotion, PRODUCTION.yaml unchanged, champion unchanged, v2.7 frozen.
EOF
}

_share_writable() { ( touch "$SHARE_LOCAL/.rodv2_probe" 2>/dev/null && rm -f "$SHARE_LOCAL/.rodv2_probe" 2>/dev/null ); }

_kill_one() {
  local pat="[${1:0:1}]${1:1}"
  pkill -9 -f "$pat" 2>/dev/null || true
  [ "$USE_LAPTOP" = 1 ] && timeout 20 ssh -o ConnectTimeout=10 "$LAPTOP_SSH" "pkill -9 -f '$pat'" </dev/null >/dev/null 2>&1 || true
}
_kill_gen() {
  _kill_one carc-orch
  _kill_one run_selfplay_iter
  _kill_one gen_flywheel
  _kill_one spawn_main
  _kill_one multiprocessing.resource_tracker
  rm -f /dev/shm/carc_fwgenv295800x /dev/shm/sem.carc_fwgenv295800x_* 2>/dev/null || true
}

_clean_stranded() {
  local dir="$1" ext="$2" age="${3:-0}" c
  if [ "$age" = "0" ]; then
    for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done
  else
    while IFS= read -r c; do [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done \
      < <(find "$dir" -name '*.claim' -mmin +"$age" 2>/dev/null)
  fi
}

_ssh_bg() {
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

# Launch the 2-box v2.9 work-stealing self-play gen for iter $1 (seed $2; parent ckpt local $3 / remote $4).
_gen_launch() {
  local it="$1" sp_seed="$2" warm_l="$3" warm_r="$4"
  SHARE=$SHARE_LOCAL REPO=$REPO_LOCAL HOST=5800x USE_ORCH=1 ORCH_WORKERS=$OW_LOCAL BRANCH=$BRANCH \
    WARM=$warm_l OUT=$OUT/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS SEED_START=$sp_seed \
    nohup nice -n 19 bash "$GENV29" > "$OUT/logs/gen5800x_it${it}.log" 2>&1 & disown
  [ "$USE_LAPTOP" = 1 ] && _ssh_bg "$LAPTOP_SSH" \
    "SHARE=$SHARE_REMOTE REPO=$REPO_LAPTOP HOST=laptop USE_ORCH=1 ORCH_WORKERS=$OW_LAPTOP BRANCH=$BRANCH WARM=$warm_r OUT=$OUTR/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS SEED_START=$sp_seed setsid nice -n 19 bash $GENV29_R > /tmp/rodv2_gen_laptop_it${it}.log 2>&1 </dev/null &" \
    "[it$it] laptop gen" &
}

_FINALIZED=0
_finalize() {
  [ "$_FINALIZED" = 1 ] && return; _FINALIZED=1
  _kill_gen
  echo "=== RoD v2 flywheel exiting @ $(date) (cleaned gen pools + orch on both boxes) ==="
}
trap _finalize EXIT
trap 'echo "[signal] caught TERM/INT @ $(date) — finalizing"; _status "INTERRUPTED" "Caught a termination signal; gen pools cleaned, all completed checkpoints + manifests preserved under \`$OUT/ckpt\`."; exit 130' INT TERM

# ----------------------------------------------------------------------------
echo "=== RoD v2 FLYWHEEL (v2.9 leaf Bmild_cap8) @ $(date) — TAG=$TAG iters $START..$ITERS games=$GAMES ==="
echo "    leaf: v2.9 Bmild_cap8 (curve $V29_CURVE, cap8, 3-open) · batch $BATCH · $EPOCHS ep · VLW $VLW · scale $SCALE · sims $SIMS · cpuct $CPUCT"
echo "    workers (GEN): local W$OW_LOCAL  laptop W$OW_LAPTOP (use_laptop=$USE_LAPTOP) · smoke=$DO_SMOKE (gen+train only)"

# Fresh code bundle so the laptop gen runs current ($BRANCH) code (incl. the v2.9 curve wiring).
git bundle create "$SHARE_LOCAL/code_sync/carc_${BRANCH}.bundle" "$BRANCH" >/dev/null 2>&1 \
  && echo "  bundle tip: $(git rev-parse --short "$BRANCH")" || { echo "FATAL: bundle create failed for $BRANCH" >&2; exit 1; }
if [ "$USE_LAPTOP" = 1 ]; then
  if timeout 60 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
       "git -C $REPO_LAPTOP fetch $SHARE_REMOTE/code_sync/carc_${BRANCH}.bundle $BRANCH && git -C $REPO_LAPTOP reset --hard FETCH_HEAD" \
       </dev/null >/dev/null 2>&1; then
    echo "  laptop synced to $(git rev-parse --short "$BRANCH")"
  else
    echo "  WARN: laptop sync FAILED — disabling laptop, running LOCAL-ONLY gen"
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

  if [ "$it" -eq 2 ]; then
    PREV_CKPT=$SEED_ITER01; PREV_ID=$SEED_ITER01_ID
  else
    pp=$(printf "%02d" $((it-1))); PREV_CKPT=$OUT/ckpt/iter_${pp}.pt; PREV_ID="RoDv2_iter_${pp}"
  fi
  PREV_CKPT_R=${PREV_CKPT/$SHARE_LOCAL/$SHARE_REMOTE}
  [ -s "$PREV_CKPT" ] || { echo "[it$it] FATAL: parent $PREV_CKPT missing/empty" >&2; _status "ERROR" "iter $it: parent checkpoint $PREV_ID missing — stopping."; exit 1; }
  cc=$(printf "%02d" "$it"); CKPT=$OUT/ckpt/iter_${cc}.pt; DATA=$OUT/iter${it}_data
  SP_SEED=$(( SP_BASE + it*100000 ))
  echo ""; echo "########## RoD v2 ITER $it -> RoDv2_iter_${cc} @ $(date) (warm from $PREV_ID) ##########"
  _status "RUNNING" "iter $it (RoDv2_iter_${cc}) IN PROGRESS — warm from $PREV_ID. Completed so far: $COMPLETED. Stage: gen."

  # ---- self-play gen (2-box work-stealing, v2.9 leaf) ----
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
    _kill_gen; sleep 1
    GEN_NPZ=$(ls "$DATA"/iter_00/*.npz 2>/dev/null | wc -l)
    echo "[it$it] gen complete ($GEN_NPZ npz) @ $(date)"
    date > "$OUT/done/gen$it"
  else
    echo "[it$it] gen — done, skip"
    GEN_NPZ=$(ls "$DATA"/iter_00/*.npz 2>/dev/null | wc -l)
  fi
  GEN_SEC=$(( $(date +%s) - GEN_T0 ))

  # ---- train (LOCAL only; v2.9 leaf env, batch 256, 3 epochs, VLW 1.5) ----
  _status "RUNNING" "iter $it (RoDv2_iter_${cc}) — gen done ($GEN_NPZ npz). Stage: train. Completed: $COMPLETED."
  TR_T0=$(date +%s)
  if [ ! -f "$CKPT" ]; then
    echo "[it$it] train @ $(date)"
    nice -n 19 env CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V29_MEEPLE_CURVE="$V29_CURVE" \
      CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_USE_FLAT_LEAF=1 \
      "$PY" -u scripts/train_iter.py \
      --output-root "$DATA" --warmstart-root "$WARMSTART_ROOT" \
      --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight "$VLW" --batch-size "$BATCH" \
      --stage-local "/tmp/rodv2_stage_$it" --warm-from "$PREV_CKPT" --output "$CKPT" --epochs "$EPOCHS" \
      --prov-value-target residual --prov-selfplay-leaf v2_9_bmild_cap8 \
      --prov-seed-range "${SP_SEED}-$((SP_SEED+GAMES-1))" --prov-run-tag "rod_v2_it${it}" \
      > "$OUT/logs/train_it${it}.log" 2>&1
    rm -rf "/tmp/rodv2_stage_$it" 2>/dev/null || true
    [ -f "$CKPT" ] || { echo "[it$it] TRAIN FAILED — halting" >&2; tail -20 "$OUT/logs/train_it${it}.log" >&2; _status "ERROR" "iter $it train FAILED (see logs/train_it${it}.log). Completed: $COMPLETED."; exit 1; }
  else
    echo "[it$it] train — ckpt exists, skip"
  fi
  TRAIN_SEC=$(( $(date +%s) - TR_T0 ))
  CKPT_METRICS="${CKPT%.pt}.metrics.json"

  # ---- screen (train-metrics collapse detector ONLY — no games; DO_SMOKE=0) ----
  echo "[it$it] screen @ $(date)"
  "$PY" "$SCREEN" --iter "$it" --ckpt "$CKPT" --metrics "$CKPT_METRICS" \
    --parent-ckpt "$PREV_CKPT" --parent-id "$PREV_ID" --measure-dir "$MEASURE" \
    --sp-seed "$SP_SEED" --games "$GAMES" --gen-npz "${GEN_NPZ:-0}" \
    --gen-sec "$GEN_SEC" --train-sec "$TRAIN_SEC" \
    --smoke-dir "" --smoke-seed "" --smoke-catastrophe-wr 0.25 \
    --leaf-label "v2.9 Bmild_cap8 (curve $V29_CURVE replaces flat meeple; cap 8; 3-open)" \
    --id-prefix RoDv2 --manifest-branch "$BRANCH" \
    --manifest-doc "RoD v2 flywheel (v2.9 leaf Bmild_cap8) — checkpoint manifest (appended per iter)"
  SCREEN_RC=$?

  date > "$OUT/done/iter$it"; COMPLETED=$((COMPLETED+1))
  if [ "$SCREEN_RC" = 3 ]; then
    echo "[it$it] ⚠️ CATASTROPHE (train collapse) — stopping the chain, preserving all artifacts @ $(date)"
    _status "STOPPED-CATASTROPHE" "iter $it (RoDv2_iter_${cc}) tripped the COLLAPSE screen. Chain STOPPED at last-sane = $PREV_ID. Completed healthy iters: $((COMPLETED-1)). All checkpoints preserved under \`$OUT/ckpt\`."
    break
  fi
  echo "[it$it] ✅ iter complete (screen HEALTHY) @ $(date) — chain advances to RoDv2_iter_${cc}"
  _status "RUNNING" "Last completed: RoDv2_iter_${cc} (iter $it). Total completed: $COMPLETED. Next: iter $((it+1))."
done

LAST=$(ls "$OUT"/ckpt/iter_*.pt 2>/dev/null | sort | tail -1)
echo ""; echo "=== RoD v2 FLYWHEEL DONE @ $(date) — completed $COMPLETED iters; latest ckpt: $LAST ==="
_status "DONE" "Run finished. Completed $COMPLETED iteration(s). Latest checkpoint: \`$LAST\`. All checkpoints retained under \`$OUT/ckpt\`. Next: evals (vs RoD_iter_01, vs the v2.8 chain, vs heur@N_v2.8) on selected checkpoints — separate, explicit step."
