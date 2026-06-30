#!/usr/bin/env bash
# ============================================================================
# STEP-2 "PeNS" WEANED FLYWHEEL LAUNCHER (MEASUREMENT ONLY).
#
# A 2-arm weaned net-value loop. The leaf value at each MCTS leaf is a wean-blend
# of the FROZEN v2.9 heuristic h and a scalar MLP over 89 PeNS features:
#       value = (1 - blend) * h + blend * v_nn
# blend (the WEAN parameter) and a per-leaf LEAF_DROPOUT are scheduled per iter.
#
# Per iter, in order:
#   1. GEN   — gen_step2.py self-play (base POLICY net + weaned scalar-MLP VALUE).
#              Produces ResNet-policy training data AND the per-ply 89-vec +
#              score_diff_wide value target for the scalar MLP.
#   2. TRAIN POLICY — train_iter.py retrains the ResNet (warm-from prev policy).
#   3. TRAIN VALUE  — train_value_iter.py retrains the scalar MLP (MSE on
#              score_diff_wide, warm-from prev scalar ckpt, FIXED normalization).
#   4. EVAL  — eval_step2.py: candidate (new policy + new scalar + this iter's
#              blend) vs RoD2 iter_02, paired net-vs-net @ sims, cheap screen.
#
# TWO ARMS (select via TAG/env ARM):
#   ARM=A  (control)   — blend FIXED at BLEND_A (~0.2, ~the validated alpha=0.25
#                        residual weight), dropout FIXED at 0.
#   ARM=B  (treatment) — blend ANNEALED ~0.2 -> ~0.85 over the pilot, dropout
#                        RISING 0 -> ~0.3 (heuristic out, net in; force the net path).
# The schedules are bash arrays (one entry per iter index 1..ITERS); they isolate
# the single variable (weaning) between the two arms.
#
# Starting checkpoints:
#   policy  = RoD2 iter_02  (/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt)
#   scalar  = warmstart.pt  (/home/doctor/carc_step2_pens/warmstart/warmstart.pt)
#
# CLUSTER: gen_step2.py (current version) plays N games LOCALLY with a Pool and
# does NOT expose --shared-claim. We PROBE for claim support; if present and
# USE_LAPTOP=1 we run 2-box work-stealing (local 5800x + laptop; Xeon OUT), else
# LOCAL-ONLY (logged). git-bundle sync to the laptop happens first either way.
#
# MEASUREMENT/EXPLORATORY: NO promotion, PRODUCTION.yaml untouched, champion
# unchanged, v2.7/v2.9 FROZEN. Authorized by Joshua (Step-2 PeNS directive).
#
# Launch (detached, real run):
#   ARM=B nohup nice -n 19 bash scripts/step2_pens/run_step2_flywheel.sh \
#       > /tmp/step2_flywheel_B.log 2>&1 & disown
#
# End-to-end firewall (1 iter, 8 games, sims 50, LOCAL-ONLY):
#   bash scripts/step2_pens/run_step2_flywheel.sh --smoke
# ============================================================================
set -uo pipefail

# --- smoke flag (parse before anything else) ---
SMOKE=0
[ "${1:-}" = "--smoke" ] && SMOKE=1

# --- paths ---
SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
REPO_LOCAL=/home/doctor/projects/carcassone
REPO_LAPTOP=/home/doctor/projects/carcassone
LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}
PY=$REPO_LOCAL/.venv/bin/python
BRANCH=${BRANCH:-rod_v2_flywheel}

# --- arm selection ---
ARM=${ARM:-B}
TAG=${TAG:-step2_pens_arm${ARM}}
OUT=$SHARE_LOCAL/$TAG
OUTR=$SHARE_REMOTE/$TAG
MEASURE=$REPO_LOCAL/measurement/$TAG

# --- seed checkpoints ---
SEED_POLICY=${SEED_POLICY:-$SHARE_LOCAL/rod_v2_flywheel/ckpt/iter_02.pt}
SEED_SCALAR=${SEED_SCALAR:-/home/doctor/carc_step2_pens/warmstart/warmstart.pt}
REF_CKPT=${REF_CKPT:-$SHARE_LOCAL/rod_v2_flywheel/ckpt/iter_02.pt}   # eval reference = RoD2 iter_02
WARMSTART_ROOT=$REPO_LOCAL/data/warmstart/heuristic_tau05

# --- scripts ---
GEN=$REPO_LOCAL/scripts/step2_pens/gen_step2.py
TRAIN_POLICY=$REPO_LOCAL/scripts/train_iter.py
TRAIN_VALUE=$REPO_LOCAL/scripts/step2_pens/train_value_iter.py
EVAL=$REPO_LOCAL/scripts/step2_pens/eval_step2.py

# --- recipe (pilot defaults) ---
ITERS=${ITERS:-10}
GAMES=${GAMES:-600}
SIMS=${SIMS:-200}
EPOCHS_POLICY=${EPOCHS_POLICY:-3}
EPOCHS_VALUE=${EPOCHS_VALUE:-6}
BATCH=${BATCH:-256}
VLW=${VLW:-1.5}
CPUCT=3.0
EVAL_N=${EVAL_N:-120}      # cheap screen
SP_BASE=${SP_BASE:-570000000}

# --- per-box gen worker counts (orch high-W; re-bench before trusting) ---
OW_LOCAL=${OW_LOCAL:-28}
OW_LAPTOP=${OW_LAPTOP:-8}
USE_LAPTOP=${USE_LAPTOP:-1}     # only honored if gen_step2 supports --shared-claim

# --- the v2.9 frozen leaf env (matches build_dataset's guard block; step2_leaf
#     import also sets it, but we set it explicitly for the trainers' provenance) ---
V29_CURVE="-8,-4,-1,0,2,3,4,5"
SCALE=${SCALE:-0.25}            # carried into the policy train provenance only

# --- wean schedules (index by iter 1..ITERS; arrays are 0-indexed so [it-1]) ---
# ARM A (control): blend FIXED ~0.2, dropout 0.
# ARM B (treatment): blend annealed 0.2 -> 0.85, dropout rising 0 -> 0.3.
BLEND_A=${BLEND_A:-0.2}
declare -a BLEND_SCHED DROPOUT_SCHED
if [ "$ARM" = "A" ]; then
  for i in $(seq 1 "$ITERS"); do BLEND_SCHED+=("$BLEND_A"); DROPOUT_SCHED+=("0.0"); done
else
  # 10-step linear-ish wean (clamped/repeated if ITERS != 10).
  B_DEF=(0.20 0.27 0.34 0.41 0.48 0.55 0.63 0.71 0.78 0.85)
  D_DEF=(0.00 0.03 0.07 0.10 0.13 0.17 0.20 0.23 0.27 0.30)
  for i in $(seq 1 "$ITERS"); do
    k=$((i-1)); [ "$k" -ge 10 ] && k=9
    BLEND_SCHED+=("${B_DEF[$k]}"); DROPOUT_SCHED+=("${D_DEF[$k]}")
  done
fi

# --- smoke overrides (end-to-end firewall) ---
if [ "$SMOKE" = 1 ]; then
  TAG=${TAG}_smoke; OUT=$SHARE_LOCAL/$TAG; OUTR=$SHARE_REMOTE/$TAG; MEASURE=$REPO_LOCAL/measurement/$TAG
  ITERS=1; GAMES=8; SIMS=50; EVAL_N=4; USE_LAPTOP=0
  EPOCHS_POLICY=1; EPOCHS_VALUE=1
  BLEND_SCHED=("${BLEND_SCHED[0]:-0.5}"); DROPOUT_SCHED=("${DROPOUT_SCHED[0]:-0.2}")
  [ "$ARM" = "A" ] && { BLEND_SCHED=("0.5"); DROPOUT_SCHED=("0.2"); }   # force the scalar path in smoke
  echo "=== SMOKE: 1 iter, GAMES=8 SIMS=50 EVAL_N=4 LOCAL-ONLY, arm=$ARM blend=${BLEND_SCHED[0]} dropout=${DROPOUT_SCHED[0]} ==="
fi

mkdir -p "$OUT/ckpt_policy" "$OUT/ckpt_scalar" "$OUT/done" "$OUT/logs" "$OUT/eval" "$MEASURE"
cd "$REPO_LOCAL" || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
[ -s "$SEED_POLICY" ] || { echo "FATAL: seed policy missing: $SEED_POLICY" >&2; exit 1; }
[ -s "$SEED_SCALAR" ] || { echo "FATAL: seed scalar missing: $SEED_SCALAR" >&2; exit 1; }
[ -s "$REF_CKPT" ]    || { echo "FATAL: eval reference missing: $REF_CKPT" >&2; exit 1; }

# ----------------------------------------------------------------------------
_status() {
  cat > "$MEASURE/STEP2_STATUS.md" <<EOF
# Step-2 PeNS Weaned Flywheel — LIVE STATUS

**State:** $1
**Updated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Arm:** $ARM ($([ "$ARM" = A ] && echo "control: blend FIXED $BLEND_A, dropout 0" || echo "treatment: blend annealed, dropout rising")) · **Tag:** $TAG

$2

---
- Leaf value: (1-blend)*h_v2.9 + blend*scalar_mlp(feat89); blend/dropout scheduled per iter.
- Recipe: GAMES $GAMES · SIMS $SIMS · policy-epochs $EPOCHS_POLICY · value-epochs $EPOCHS_VALUE · batch $BATCH · VLW $VLW · eval_n $EVAL_N
- Seeds: policy=$(basename "$SEED_POLICY") scalar=$(basename "$SEED_SCALAR"); eval-ref=$(basename "$REF_CKPT")
- Cluster: $([ "$USE_LAPTOP" = 1 ] && echo "2-box (local+laptop) if gen supports --shared-claim, else LOCAL-ONLY" || echo "LOCAL-ONLY")
- MEASUREMENT/EXPLORATORY — no promotion, PRODUCTION.yaml/champion/v2.7/v2.9 UNCHANGED.
EOF
}

# Does the (sibling-owned) gen_step2.py expose --shared-claim for cross-box work-stealing?
_gen_supports_claim() { "$PY" "$GEN" --help 2>/dev/null | grep -q -- "--shared-claim"; }

_kill_one() {
  local pat="[${1:0:1}]${1:1}"
  pkill -9 -f "$pat" 2>/dev/null || true
  [ "$USE_LAPTOP" = 1 ] && timeout 20 ssh -o ConnectTimeout=10 "$LAPTOP_SSH" "pkill -9 -f '$pat'" </dev/null >/dev/null 2>&1 || true
}
_kill_gen() { _kill_one gen_step2; _kill_one carc-orch; _kill_one spawn_main; }

_FINALIZED=0
_finalize() {
  [ "$_FINALIZED" = 1 ] && return; _FINALIZED=1
  _kill_gen
  echo "=== step2 flywheel exiting @ $(date) (cleaned gen pools) ==="
}
trap _finalize EXIT
trap 'echo "[signal] TERM/INT @ $(date)"; _status "INTERRUPTED" "Caught a termination signal; gen cleaned, completed artifacts preserved under \`$OUT\`."; exit 130' INT TERM

# ----------------------------------------------------------------------------
echo "=== STEP-2 PeNS FLYWHEEL (arm $ARM) @ $(date) — TAG=$TAG iters 1..$ITERS games=$GAMES sims=$SIMS ==="
echo "    blend sched: ${BLEND_SCHED[*]}"
echo "    dropout sched: ${DROPOUT_SCHED[*]}"

# Decide the cluster mode up-front.
LAPTOP_OK=0
if [ "$USE_LAPTOP" = 1 ]; then
  if _gen_supports_claim; then
    # bundle the current branch so the laptop runs current code
    if git bundle create "$SHARE_LOCAL/code_sync/carc_${BRANCH}.bundle" "$BRANCH" >/dev/null 2>&1; then
      echo "  bundle tip: $(git rev-parse --short "$BRANCH")"
      if timeout 60 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
          "git -C $REPO_LAPTOP fetch $SHARE_REMOTE/code_sync/carc_${BRANCH}.bundle $BRANCH && git -C $REPO_LAPTOP reset --hard FETCH_HEAD" \
          </dev/null >/dev/null 2>&1; then
        LAPTOP_OK=1; echo "  laptop synced — 2-box work-stealing gen ENABLED (gen_step2 has --shared-claim)"
      else
        echo "  WARN: laptop sync FAILED — LOCAL-ONLY gen"
      fi
    else
      echo "  WARN: bundle create FAILED — LOCAL-ONLY gen"
    fi
  else
    echo "  NOTE: gen_step2.py has NO --shared-claim (current version) — running LOCAL-ONLY gen"
    echo "        (when the sibling agent adds claim support, set USE_LAPTOP=1 to fan out 2-box)"
  fi
fi
echo "    cluster mode: $([ "$LAPTOP_OK" = 1 ] && echo "2-box (local W$OW_LOCAL + laptop W$OW_LAPTOP)" || echo "LOCAL-ONLY (local W$OW_LOCAL)")"

_status "RUNNING" "Starting iter 1 (arm $ARM). No iteration completed yet."

# Launch one box's gen (orch high-W). $1=iter $2=seed_start $3=policy_ckpt $4=scalar_ckpt $5=blend $6=dropout $7=outdir
_gen_launch_local() {
  local it="$1" seed="$2" pol="$3" sca="$4" bl="$5" dr="$6" od="$7"
  # GEN through the carc-orch SHM GPU orchestrator: gen_step2_orch.sh TorchScript-
  # exports the policy net (parity-gated), starts ONE carc-orch SHM server for the
  # priors (the 85%-of-per-leaf-cost policy forward, GPU-batched), runs gen_step2
  # --shm-eval-server, and trap-cleans the server. The scalar-MLP VALUE is computed
  # in-worker on CPU (cheap). CKPT/SCALAR/OW/SIMS go via env; the rest via "$@".
  CKPT="$pol" SCALAR="$sca" OW="$OW_LOCAL" SIMS="$SIMS" \
    nice -n 19 bash "$REPO_LOCAL/scripts/step2_pens/gen_step2_orch.sh" \
    --games "$GAMES" --blend "$bl" --dropout "$dr" --iter "$it" --out "$od" \
    --value-target score_diff_wide \
    > "$OUT/logs/gen_local_it${it}.log" 2>&1
}
_gen_launch_laptop() {
  local it="$1" seed="$2" pol="$3" sca="$4" bl="$5" dr="$6" od="$7"
  local polr=${pol/$SHARE_LOCAL/$SHARE_REMOTE} odr=${od/$SHARE_LOCAL/$SHARE_REMOTE}
  # scalar ckpt may live outside the share; require it on the share for the laptop.
  local scar=${sca/$SHARE_LOCAL/$SHARE_REMOTE}
  timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
    "setsid nice -n 19 $REPO_LAPTOP/.venv/bin/python -u $REPO_LAPTOP/scripts/step2_pens/gen_step2.py --checkpoint $polr --scalar-ckpt $scar --out $odr --games $GAMES --sims $SIMS --blend $bl --dropout $dr --workers $OW_LAPTOP --value-target score_diff_wide --iter $it --shared-claim --claim-host laptop > /tmp/step2_gen_laptop_it${it}.log 2>&1 </dev/null &" \
    </dev/null >/dev/null 2>&1 || true
}

COMPLETED=0
for it in $(seq 1 "$ITERS"); do
  if [ -f "$OUT/done/iter$it" ]; then echo "[it$it] already complete — skip"; COMPLETED=$((COMPLETED+1)); continue; fi

  BLEND=${BLEND_SCHED[$((it-1))]}
  DROPOUT=${DROPOUT_SCHED[$((it-1))]}
  if [ "$it" -eq 1 ]; then
    PREV_POLICY=$SEED_POLICY; PREV_SCALAR=$SEED_SCALAR
  else
    pp=$(printf "%02d" $((it-1)))
    PREV_POLICY=$OUT/ckpt_policy/iter_${pp}.pt
    PREV_SCALAR=$OUT/ckpt_scalar/iter_${pp}.pt
  fi
  [ -s "$PREV_POLICY" ] || { echo "[it$it] FATAL: prev policy $PREV_POLICY missing" >&2; _status "ERROR" "iter $it: prev policy missing."; exit 1; }
  [ -s "$PREV_SCALAR" ] || { echo "[it$it] FATAL: prev scalar $PREV_SCALAR missing" >&2; _status "ERROR" "iter $it: prev scalar missing."; exit 1; }
  cc=$(printf "%02d" "$it")
  POLICY_CKPT=$OUT/ckpt_policy/iter_${cc}.pt
  SCALAR_CKPT=$OUT/ckpt_scalar/iter_${cc}.pt
  DATA=$OUT/iter${it}_data
  SP_SEED=$(( SP_BASE + it*100000 ))
  echo ""; echo "########## STEP-2 ITER $it (arm $ARM) @ $(date) — blend=$BLEND dropout=$DROPOUT (warm pol=$(basename "$PREV_POLICY") sca=$(basename "$PREV_SCALAR")) ##########"
  _status "RUNNING" "iter $it IN PROGRESS — blend=$BLEND dropout=$DROPOUT. Completed: $COMPLETED. Stage: gen."

  # ---- 1. GEN (gen_step2.py) ----
  GEN_T0=$(date +%s)
  if [ ! -f "$OUT/done/gen$it" ]; then
    mkdir -p "$DATA/iter_00"
    echo "[it$it] gen -> $DATA/iter_00 @ $(date)"
    _kill_gen; sleep 1
    # gen_step2 (current) is a BLOCKING single-box run; launch it in the foreground
    # of a subshell so its exit gates the iter. If/when --shared-claim lands, the
    # laptop launch below contributes to the same OUT via the claim mechanism.
    [ "$LAPTOP_OK" = 1 ] && _gen_launch_laptop "$it" "$SP_SEED" "$PREV_POLICY" "$PREV_SCALAR" "$BLEND" "$DROPOUT" "$DATA/iter_00" &
    _gen_launch_local "$it" "$SP_SEED" "$PREV_POLICY" "$PREV_SCALAR" "$BLEND" "$DROPOUT" "$DATA/iter_00"
    GEN_RC=$?
    _kill_gen; sleep 1
    GEN_NPZ=$(ls "$DATA"/iter_00/seed_*.npz 2>/dev/null | wc -l)
    if [ "$GEN_RC" != 0 ] || [ "$GEN_NPZ" -lt 1 ]; then
      echo "[it$it] GEN FAILED (rc=$GEN_RC, npz=$GEN_NPZ) — halting" >&2
      tail -25 "$OUT/logs/gen_local_it${it}.log" >&2
      _status "ERROR" "iter $it gen FAILED (rc=$GEN_RC, npz=$GEN_NPZ). See logs/gen_local_it${it}.log."
      exit 1
    fi
    echo "[it$it] gen complete ($GEN_NPZ npz) @ $(date)"
    date > "$OUT/done/gen$it"
  else
    echo "[it$it] gen — done, skip"; GEN_NPZ=$(ls "$DATA"/iter_00/seed_*.npz 2>/dev/null | wc -l)
  fi
  # SEPARATE the companion *_pens.npz (89-vec + value_target for the scalar-MLP value
  # retrain) OUT of the gen dir BEFORE train_iter globs iter_00 — train_iter expects the
  # GameDataset schema ('values' etc.) and KeyErrors on the pens companions.
  mkdir -p "$DATA/iter_00_pens"
  mv "$DATA"/iter_00/*_pens.npz "$DATA/iter_00_pens/" 2>/dev/null || true
  GEN_SEC=$(( $(date +%s) - GEN_T0 ))

  # ---- 2. TRAIN POLICY (train_iter.py, v2.9 leaf env) ----
  _status "RUNNING" "iter $it — gen done ($GEN_NPZ npz). Stage: train-policy. Completed: $COMPLETED."
  TRP_T0=$(date +%s)
  if [ ! -f "$POLICY_CKPT" ]; then
    echo "[it$it] train POLICY @ $(date)"
    nice -n 19 env CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V29_MEEPLE_CURVE="$V29_CURVE" \
      CARCASSONNE_V25_MEEPLE_K=2.0 CARCASSONNE_USE_FLAT_LEAF=1 \
      "$PY" -u "$TRAIN_POLICY" \
      --output-root "$DATA" --warmstart-root "$WARMSTART_ROOT" \
      --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight "$VLW" --batch-size "$BATCH" \
      --stage-local "/tmp/step2_stage_${ARM}_$it" --warm-from "$PREV_POLICY" --output "$POLICY_CKPT" --epochs "$EPOCHS_POLICY" \
      --prov-value-target score_diff_wide --prov-selfplay-leaf v2_9_bmild_cap8 \
      --prov-seed-range "${SP_SEED}-$((SP_SEED+GAMES-1))" --prov-run-tag "step2_${ARM}_it${it}" \
      > "$OUT/logs/train_policy_it${it}.log" 2>&1
    rm -rf "/tmp/step2_stage_${ARM}_$it" 2>/dev/null || true
    [ -s "$POLICY_CKPT" ] || { echo "[it$it] POLICY TRAIN FAILED — halting" >&2; tail -20 "$OUT/logs/train_policy_it${it}.log" >&2; _status "ERROR" "iter $it policy train FAILED."; exit 1; }
  else
    echo "[it$it] train POLICY — exists, skip"
  fi
  TRP_SEC=$(( $(date +%s) - TRP_T0 ))

  # ---- 3. TRAIN VALUE (train_value_iter.py — scalar MLP, MSE, fixed norm) ----
  _status "RUNNING" "iter $it — policy done. Stage: train-value. Completed: $COMPLETED."
  TRV_T0=$(date +%s)
  if [ ! -f "$SCALAR_CKPT" ]; then
    echo "[it$it] train VALUE (scalar MLP) @ $(date)"
    nice -n 19 "$PY" -u "$TRAIN_VALUE" \
      --gen-dir "$DATA/iter_00_pens" --warm-from "$PREV_SCALAR" --out "$SCALAR_CKPT" --epochs "$EPOCHS_VALUE" \
      > "$OUT/logs/train_value_it${it}.log" 2>&1
    [ -s "$SCALAR_CKPT" ] || { echo "[it$it] VALUE TRAIN FAILED — halting" >&2; tail -20 "$OUT/logs/train_value_it${it}.log" >&2; _status "ERROR" "iter $it value train FAILED (likely the gen-npz seam — check --feat-field)."; exit 1; }
  else
    echo "[it$it] train VALUE — exists, skip"
  fi
  TRV_SEC=$(( $(date +%s) - TRV_T0 ))

  # ---- 4. EVAL (eval_step2.py — cheap paired screen vs RoD2 iter_02) ----
  _status "RUNNING" "iter $it — value done. Stage: eval. Completed: $COMPLETED."
  EV_T0=$(date +%s)
  echo "[it$it] eval (screen) blend=$BLEND vs RoD2 iter_02, paired n=$EVAL_N @ sims=$SIMS @ $(date)"
  nice -n 19 "$PY" -u "$EVAL" \
    --ckpt "$POLICY_CKPT" --scalar-ckpt "$SCALAR_CKPT" --ref-ckpt "$REF_CKPT" \
    --blend "$BLEND" --dropout "$DROPOUT" --n "$EVAL_N" --sims "$SIMS" \
    --workers "$OW_LOCAL" --out "$OUT/eval/iter_${cc}" \
    --seed-start $(( 5715000000 + it*1000000 )) \
    > "$OUT/logs/eval_it${it}.log" 2>&1
  EV_RC=$?
  EV_SEC=$(( $(date +%s) - EV_T0 ))
  if [ "$EV_RC" != 0 ]; then
    echo "[it$it] WARN: eval rc=$EV_RC (screen non-fatal; chain continues)"; tail -10 "$OUT/logs/eval_it${it}.log"
  fi
  # surface the screen verdict line
  if [ -f "$OUT/eval/iter_${cc}/summary.json" ]; then
    "$PY" - "$OUT/eval/iter_${cc}/summary.json" <<'PYEOF'
import json,sys
s=json.load(open(sys.argv[1]))
print(f"  [screen it] wr={s.get('winrate'):.3f} (z={s.get('winrate_z'):+.2f}) "
      f"elo={s.get('elo'):+.1f} paired_margin={s.get('paired_mean_margin')} "
      f"paired_z={s.get('paired_z'):+.2f} n={s.get('n')}")
PYEOF
  fi

  date > "$OUT/done/iter$it"; COMPLETED=$((COMPLETED+1))
  echo "[it$it] ✅ iter complete @ $(date) — gen ${GEN_SEC}s / pol ${TRP_SEC}s / val ${TRV_SEC}s / eval ${EV_SEC}s"
  _status "RUNNING" "Last completed: iter $it (blend $BLEND). Total: $COMPLETED. Next: iter $((it+1))."
done

echo ""; echo "=== STEP-2 PeNS FLYWHEEL (arm $ARM) DONE @ $(date) — completed $COMPLETED iters ==="
_status "DONE" "Run finished. Completed $COMPLETED iteration(s). Policy ckpts under \`$OUT/ckpt_policy\`, scalar ckpts under \`$OUT/ckpt_scalar\`, per-iter screens under \`$OUT/eval\`. Next: the lean-in-loop derivative read (arm B slope) + a powered h6400_v2.9 verdict on the surviving checkpoint — separate explicit step."
