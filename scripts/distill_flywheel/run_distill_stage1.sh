#!/usr/bin/env bash
# ============================================================================
# DISTILL-FLYWHEEL — STAGE 1 ONLY (iters 0..3): pure FAIR-champion distillation.
#
# Spec: measurement/distill_flywheel_20260715/DESIGN_FAIR_ADDENDUM.md (the fair pivot)
#       + DESIGN.md (dir layout §5, per-iter diagnostics/gates §6, close-out).
#
# Each iter: net-free FAIR-champion self-play gen (FairHeuristicPriorAgent, blind PIMC,
# k_dets=4 x sims=688 = 2752 budget, curve125 leaf) on BOTH boxes (local W16 + laptop
# W12) work-stealing via --shared-claim into <SHARE>/iter_<NN>/, recording the pooled
# root-visit POLICY target + game-outcome VALUE target -> LOCAL train (accumulate ALL
# iters via --output-root <SHARE> --iter <it> --window 12; warm iter0 from
# warmstart_canonical.pt, iterN from iter_(N-1)) -> overnight_iter_screen collapse
# detector (rc=3 halts the chain) -> probe_metrics distillation-fidelity probe.
#
# ⚠️ STAGE 1 ONLY. The loop STOPS after iter 3 (STAGE_SPLIT boundary). The fair-net
# FLYWHEEL (iters 4..11, net-priors gen through carc-orch) is a SEPARATE task — this
# driver does NOT build or enter stage 2.
#
# GEN + TRAIN ONLY — no in-loop game eval (probe_metrics is a pure forward pass, not a
# game). MEASUREMENT/EXPLORATORY: no promotion, PRODUCTION.yaml untouched, champion
# unchanged. Detached-launch + laptop bundle sync are done by the operator (main agent).
#
# Dry run (prints the exact per-iter commands, touches nothing):
#   bash scripts/distill_flywheel/run_distill_stage1.sh --dry-run
# Real launch (detached; operator runs this after the bundle sync + probe-set gen):
#   nohup nice -n 19 bash scripts/distill_flywheel/run_distill_stage1.sh > /tmp/distill_stage1.log 2>&1 & disown
# ============================================================================
set -uo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# EDITABLE CONFIG (top-of-script knobs)
# ---------------------------------------------------------------------------
# --- paths (⚠️ share prefix differs by box: local /mnt/c/carc-shared, laptop /mnt/carc-shared) ---
SHARE_LOCAL=${SHARE_LOCAL:-/mnt/c/carc-shared}
SHARE_REMOTE=${SHARE_REMOTE:-/mnt/carc-shared}
REPO_LOCAL=${REPO_LOCAL:-/home/doctor/projects/carcassone}
REPO_LAPTOP=${REPO_LAPTOP:-/home/doctor/projects/carcassone}
LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}          # direct WSL :2222 (operators/setsid work); `laptop` = Windows hop
PY=$REPO_LOCAL/.venv/bin/python
TAG=${TAG:-distill_flywheel_20260715}
BRANCH=${BRANCH:-rod_v2_flywheel}
OUT=$SHARE_LOCAL/$TAG                          # local view of the run root
OUTR=$SHARE_REMOTE/$TAG                         # laptop view of the SAME CIFS dir
MEASURE=$REPO_LOCAL/measurement/$TAG
GEN=$REPO_LOCAL/scripts/distill_flywheel/gen_fair_distill.py
GENR=$REPO_LAPTOP/scripts/distill_flywheel/gen_fair_distill.py
CHAMP_ENV=$REPO_LOCAL/scripts/distill_flywheel/champ_env.sh
CHAMP_ENV_R=$REPO_LAPTOP/scripts/distill_flywheel/champ_env.sh
SCREEN=$REPO_LOCAL/scripts/rod_v28/overnight_iter_screen.py
PROBE=$REPO_LOCAL/scripts/distill_flywheel/probe_metrics.py
WARM0=${WARM0:-$REPO_LOCAL/checkpoints/warmstart_canonical.pt}   # iter-0 warm-from (78ch/10-scalar 96x6)

# --- FAIR champion gen recipe (PRODUCTION.yaml fair_deploy; do NOT change) ---
KDETS=${KDETS:-4}                              # determinizations/move (CL-054)
CHAMP_SIMS=${CHAMP_SIMS:-688}                  # sims/det; k4 x 688 = 2752 total budget
CPUCT=${CPUCT:-1.5}; TAUP=${TAUP:-5.0}; VALUE_NORM=${VALUE_NORM:-15.0}
GAMES=${GAMES:-600}                            # games/iter (both boxes, shared-claim)

# --- train recipe ---
WINDOW=${WINDOW:-12}                           # accumulate ALL iters (globs iter_00..iter_it)
EPOCHS=${EPOCHS:-3}; BATCH=${BATCH:-256}; VLW=${VLW:-1.5}
# ⚠️ AUX_WEIGHT=0: the fair emitter has NO ownership labels (dummy zeros). Training the
# ownership head on dummies would corrupt it, so ownership loss is OFF. Distillation is
# policy CE + value MSE only — exactly what probe_metrics.py measures.
AUX_WEIGHT=${AUX_WEIGHT:-0}
TRAIN_GPU=${TRAIN_GPU:-0}                       # champ_env.sh hides CUDA for gen; train/probe re-enable it
# ⚠️ Collapse-screen val_pol_loss threshold: the pooled-visit distillation TARGET entropy
# is ~1.35, so a perfectly-healthy fit's policy CE > 1.0 (the self-play-tuned default) —
# raised to 4.0 to avoid a FALSE collapse every iter. The NaN + entropy-floor + relative-
# rise screens (distribution-agnostic) still catch a real collapse.
VAL_POL_COLLAPSE_THRESH=${VAL_POL_COLLAPSE_THRESH:-4.0}

# --- boxes / workers (net-free CPU gen -> orch-OFF; the mapped orch-OFF optima) ---
W_LOCAL=${W_LOCAL:-16}
W_LAPTOP=${W_LAPTOP:-12}
USE_LAPTOP=${USE_LAPTOP:-1}

# --- loop control: STAGE 1 = iters 0..3 (STOP after 3; do NOT enter stage 2) ---
START=${START:-0}
STAGE_SPLIT=${STAGE_SPLIT:-4}                   # first stage-2 iter; stage 1 runs [START, STAGE_SPLIT-1]
END=$(( STAGE_SPLIT - 1 ))
SEED_BASE=${SEED_BASE:-700000000}              # champ stream seed = SEED_BASE + it*100000 (DESIGN §3)

# --- self-heal (gen watchdog) ---
HEAL_CAP=${HEAL_CAP:-8}; STALL_GEN=${STALL_GEN:-15}
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# ---------------------------------------------------------------------------
_seed_for()  { echo $(( SEED_BASE + $1 * 100000 )); }
_nn()        { printf "%02d" "$1"; }
_warm_for()  { if [ "$1" -eq 0 ]; then echo "$WARM0"; else echo "$OUT/ckpt/iter_$(_nn $(( $1 - 1 ))).pt"; fi; }

# The exact local + laptop gen commands for iter $1 (used by both the dry-run printer
# and the real launch, so they can never drift).
_gen_cmd_local() {
  local it="$1" seed data nn; nn=$(_nn "$it"); seed=$(_seed_for "$it"); data="$OUT/iter_${nn}"
  echo "source $CHAMP_ENV && nohup nice -n 19 $PY -u $GEN \\"
  echo "    --games $GAMES --k-dets $KDETS --sims $CHAMP_SIMS --c-puct $CPUCT --tau-p $TAUP --value-norm $VALUE_NORM \\"
  echo "    --workers $W_LOCAL --seed-start $seed --out $data --shared-claim --claim-host 5800x \\"
  echo "    > $OUT/logs/gen_local_it${nn}.log 2>&1 & disown"
}
_gen_cmd_laptop() {   # body of the script piped via `ssh $LAPTOP_SSH 'bash -s'` (cd on line 1)
  local it="$1" seed nn; nn=$(_nn "$it"); seed=$(_seed_for "$it")
  echo "cd $REPO_LAPTOP || exit 1"
  echo "source $CHAMP_ENV_R"
  echo "setsid nice -n 19 $REPO_LAPTOP/.venv/bin/python -u $GENR \\"
  echo "    --games $GAMES --k-dets $KDETS --sims $CHAMP_SIMS --c-puct $CPUCT --tau-p $TAUP --value-norm $VALUE_NORM \\"
  echo "    --workers $W_LAPTOP --seed-start $seed --out $OUTR/iter_${nn} --shared-claim --claim-host laptop \\"
  echo "    > /tmp/distill_gen_laptop_it${nn}.log 2>&1 </dev/null &"
}
_train_cmd() {
  local it="$1" nn warm seed; nn=$(_nn "$it"); warm=$(_warm_for "$it"); seed=$(_seed_for "$it")
  echo "source $CHAMP_ENV && CUDA_VISIBLE_DEVICES=$TRAIN_GPU nice -n 19 $PY -u scripts/train_iter.py \\"
  echo "    --output-root $OUT --iter $it --window $WINDOW --warm-from $warm --output $OUT/ckpt/iter_${nn}.pt \\"
  echo "    --epochs $EPOCHS --batch-size $BATCH --value-loss-weight $VLW --aux-weight $AUX_WEIGHT \\"
  echo "    --stage-local /tmp/distill_stage_${it} \\"
  echo "    --prov-value-target outcome --prov-selfplay-leaf v2_9_bmild_cap8_curve125 \\"
  echo "    --prov-seed-range ${seed}-$(( seed + GAMES - 1 )) --prov-run-tag distill_stage1_it${it}"
}

# ---------------------------------------------------------------------------
# DRY RUN: print the exact commands per iter, touch nothing, exit.
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = 1 ]; then
  echo "=== DISTILL STAGE-1 DRY RUN — iters $START..$END (STAGE_SPLIT=$STAGE_SPLIT) ==="
  echo "run root (local)  : $OUT"
  echo "run root (laptop) : $OUTR"
  echo "recipe            : GAMES=$GAMES  k_dets=$KDETS x sims=$CHAMP_SIMS (=$(( KDETS*CHAMP_SIMS )) budget)  c_puct=$CPUCT tau_p=$TAUP value_norm=$VALUE_NORM"
  echo "train             : window=$WINDOW epochs=$EPOCHS batch=$BATCH vlw=$VLW aux_weight=$AUX_WEIGHT (ownership OFF — no fair labels)"
  echo "boxes             : local W$W_LOCAL + laptop W$W_LAPTOP (use_laptop=$USE_LAPTOP), shared-claim, orch-OFF (net-free)"
  echo "warm-from iter0   : $WARM0"
  for it in $(seq "$START" "$END"); do
    echo ""; echo "########## ITER $it -> iter_$(_nn "$it") (warm from $(basename "$(_warm_for "$it")")) ##########"
    echo "--- gen LOCAL ---";  _gen_cmd_local "$it"
    if [ "$USE_LAPTOP" = 1 ]; then
      echo "--- gen LAPTOP (ssh $LAPTOP_SSH 'bash -s' < <<script>>; rc=124=launched) ---"; _gen_cmd_laptop "$it"
    fi
    echo "--- wait: poll $OUT/iter_$(_nn "$it")/*.npz until >= $GAMES (watchdog STALL_GEN=$STALL_GEN, HEAL_CAP=$HEAL_CAP) ---"
    echo "--- train (LOCAL) ---"; _train_cmd "$it"
    echo "--- screen (overnight_iter_screen; rc=3 -> HALT chain) ---"
    echo "--- probe (probe_metrics.py --iter $it --ckpt iter_$(_nn "$it").pt --probe-dir $OUT/probe_data/iter_00 --out $OUT) ---"
  done
  echo ""; echo "=== END DRY RUN (STOP after iter $END — stage 2 is a SEPARATE task) ==="
  exit 0
fi

# ---------------------------------------------------------------------------
# REAL RUN
# ---------------------------------------------------------------------------
mkdir -p "$OUT/ckpt" "$OUT/done" "$OUT/logs" "$MEASURE"
cd "$REPO_LOCAL" || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
[ -f "$WARM0" ] || { echo "FATAL: iter-0 warm-from missing: $WARM0" >&2; exit 1; }
[ -f "$GEN" ]   || { echo "FATAL: emitter missing: $GEN" >&2; exit 1; }
[ -f "$CHAMP_ENV" ] || { echo "FATAL: champ_env.sh missing: $CHAMP_ENV" >&2; exit 1; }

_status() {
  local state="$1" detail="$2"
  cat > "$MEASURE/STAGE1_STATUS.md" <<EOF
# Distill-flywheel STAGE 1 (fair-champion distillation) — LIVE STATUS

**State:** $state
**Updated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Branch:** $BRANCH · **Tag:** $TAG · **Iters:** $START..$END (STAGE 1 only)

$detail

---
- Teacher: FairHeuristicPriorAgent (blind PIMC), k_dets=$KDETS x sims=$CHAMP_SIMS (=$(( KDETS*CHAMP_SIMS )) budget), curve125 leaf.
- Recipe: GAMES/iter=$GAMES · window=$WINDOW · epochs=$EPOCHS · batch=$BATCH · vlw=$VLW · aux_weight=$AUX_WEIGHT.
- Boxes (gen): local W$W_LOCAL + laptop W$W_LAPTOP ($([ "$USE_LAPTOP" = 1 ] && echo enabled || echo DISABLED)), shared-claim, orch-OFF.
- Warm: iter0 <- warmstart_canonical.pt; iterN <- iter_(N-1). Accumulate ALL iters. Checkpoints: \`$OUT/ckpt/iter_*.pt\`.
- GEN + TRAIN ONLY — no in-loop game eval. MEASUREMENT/EXPLORATORY; PRODUCTION.yaml untouched. STOP after iter $END (stage 2 = separate task).
EOF
}

_kill_one() {   # kill pattern on both boxes; [x]yz self-match guard so this pkill can't hit itself
  local pat="[${1:0:1}]${1:1}"
  pkill -9 -f "$pat" 2>/dev/null || true
  [ "$USE_LAPTOP" = 1 ] && timeout 20 ssh -o ConnectTimeout=10 "$LAPTOP_SSH" "pkill -9 -f '$pat'" </dev/null >/dev/null 2>&1 || true
}
_kill_gen() {   # Pool uses fork -> workers inherit argv (gen_fair_distill visible to pkill); reap them + the mp tracker
  _kill_one gen_fair_distill
  _kill_one multiprocessing.resource_tracker
}

_clean_stranded() {   # delete .claim files with no matching .npz (shared-claim orphan-stall fix)
  local dir="$1" age="${2:-0}" c
  if [ "$age" = "0" ]; then
    for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.npz" ] || rm -f "$c"; done
  else
    while IFS= read -r c; do [ -e "${c%.claim}.npz" ] || rm -f "$c"; done \
      < <(find "$dir" -name '*.claim' -mmin +"$age" 2>/dev/null)
  fi
}

_gen_launch() {   # launch local + (backgrounded) laptop gen for iter $1
  local it="$1" nn; nn=$(_nn "$it")
  # local: source champ_env in a subshell, nohup-detach the net-free CPU gen.
  ( source "$CHAMP_ENV" && nohup nice -n 19 "$PY" -u "$GEN" \
      --games "$GAMES" --k-dets "$KDETS" --sims "$CHAMP_SIMS" --c-puct "$CPUCT" \
      --tau-p "$TAUP" --value-norm "$VALUE_NORM" --workers "$W_LOCAL" \
      --seed-start "$(_seed_for "$it")" --out "$OUT/iter_${nn}" --shared-claim --claim-host 5800x \
      > "$OUT/logs/gen_local_it${nn}.log" 2>&1 & )
  # laptop: pipe a self-contained per-iter script (cd on line 1) via `ssh 'bash -s'`.
  # BACKGROUND the ssh call (setsid can hold the channel -> a synchronous call would
  # starve the loop; rc=124 from the timeout = LAUNCHED, never retried — memory rule).
  if [ "$USE_LAPTOP" = 1 ]; then
    local script="/tmp/distill_laptop_gen_it${nn}.sh"
    _gen_cmd_laptop "$it" > "$script"
    (
      timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" 'bash -s' < "$script"
      rc=$?
      if [ "$rc" = 124 ]; then echo "  [it$it] laptop gen launched (rc=124, setsid held ssh — not retried)"
      elif [ "$rc" != 0 ]; then echo "  [it$it] laptop gen launch rc=$rc (box may be down this iter)"; fi
    ) &
  fi
}

_FINALIZED=0
_finalize() {
  [ "$_FINALIZED" = 1 ] && return; _FINALIZED=1
  _kill_gen
  echo "=== distill stage-1 exiting @ $(date) (cleaned gen pools on both boxes) ==="
}
trap _finalize EXIT
trap 'echo "[signal] TERM/INT @ $(date) — finalizing"; _status "INTERRUPTED" "Caught a termination signal; gen pools cleaned, all completed checkpoints preserved under \`$OUT/ckpt\`."; exit 130' INT TERM

echo "=== DISTILL STAGE-1 @ $(date) — TAG=$TAG iters $START..$END games=$GAMES ==="
echo "    teacher: FairHeuristicPriorAgent k_dets=$KDETS x sims=$CHAMP_SIMS (curve125) · window $WINDOW · aux_weight $AUX_WEIGHT"
echo "    boxes (gen): local W$W_LOCAL  laptop W$W_LAPTOP (use_laptop=$USE_LAPTOP) · orch-OFF (net-free CPU)"

# --- git-bundle code sync (stub — operator does the authoritative sync; this makes the
#     laptop run current $BRANCH code incl. gen_fair_distill.py + fair_agent Change 2) ---
git bundle create "$SHARE_LOCAL/code_sync/carc_${BRANCH}.bundle" "$BRANCH" >/dev/null 2>&1 \
  && echo "  bundle tip: $(git rev-parse --short "$BRANCH")" || echo "  WARN: bundle create failed (operator will sync)"
if [ "$USE_LAPTOP" = 1 ]; then
  if timeout 60 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
       "git -C $REPO_LAPTOP fetch $SHARE_REMOTE/code_sync/carc_${BRANCH}.bundle $BRANCH && git -C $REPO_LAPTOP reset --hard FETCH_HEAD" \
       </dev/null >/dev/null 2>&1; then
    echo "  laptop synced to $(git rev-parse --short "$BRANCH")"
  else
    echo "  WARN: laptop sync FAILED — disabling laptop, running LOCAL-ONLY gen"; USE_LAPTOP=0
  fi
fi

_status "RUNNING" "Starting iter $START. No iteration completed yet."
COMPLETED=0

for it in $(seq "$START" "$END"); do
  nn=$(_nn "$it"); CKPT=$OUT/ckpt/iter_${nn}.pt; DATA=$OUT/iter_${nn}
  SEED=$(_seed_for "$it"); PREV=$(_warm_for "$it")
  if [ -f "$OUT/done/iter$it" ]; then echo "[it$it] already complete — skip (reboot-resume)"; COMPLETED=$((COMPLETED+1)); continue; fi
  [ -s "$PREV" ] || { echo "[it$it] FATAL: warm-from $PREV missing/empty" >&2; _status "ERROR" "iter $it: warm-from missing — stopped."; exit 1; }
  echo ""; echo "########## DISTILL ITER $it -> iter_${nn} @ $(date) (warm from $(basename "$PREV")) ##########"
  _status "RUNNING" "iter $it (iter_${nn}) IN PROGRESS — warm from $(basename "$PREV"). Completed so far: $COMPLETED. Stage: gen."

  # ---- gen (2-box work-stealing, net-free fair champion) ----
  GEN_T0=$(date +%s)
  if [ ! -f "$OUT/done/gen$it" ]; then
    echo "[it$it] gen seed_start=$SEED -> $DATA @ $(date)"
    mkdir -p "$DATA"; _clean_stranded "$DATA" 0
    _kill_gen; sleep 2; _gen_launch "$it"
    glast=-1; gstall=0; gheals=0
    while [ "$(ls "$DATA"/*.npz 2>/dev/null | wc -l)" -lt "$GAMES" ]; do
      sleep 60
      gcur=$(ls "$DATA"/*.npz 2>/dev/null | wc -l)
      if [ "$gcur" -eq "$glast" ]; then gstall=$((gstall+1)); else gstall=0; glast=$gcur; fi
      if [ "$gstall" -ge "$STALL_GEN" ]; then
        gheals=$((gheals+1))
        [ "$gheals" -gt "$HEAL_CAP" ] && { echo "[it$it] FATAL: $gheals gen heals, stuck $gcur/$GAMES" >&2; _status "ERROR" "iter $it gen stuck at $gcur/$GAMES after $HEAL_CAP heals."; exit 1; }
        echo "[it$it] gen STALLED $gcur/$GAMES — heal $gheals: kill+clean+relaunch @ $(date)"
        _kill_gen; sleep 2; _clean_stranded "$DATA" 30; _gen_launch "$it"; gstall=0
      fi
    done
    _kill_gen; sleep 1
    GEN_NPZ=$(ls "$DATA"/*.npz 2>/dev/null | wc -l)
    echo "[it$it] gen complete ($GEN_NPZ npz) @ $(date)"; date > "$OUT/done/gen$it"
  else
    echo "[it$it] gen — done, skip"; GEN_NPZ=$(ls "$DATA"/*.npz 2>/dev/null | wc -l)
  fi
  GEN_SEC=$(( $(date +%s) - GEN_T0 ))

  # ---- train (LOCAL only; accumulate iter_00..iter_it via --output-root/--window) ----
  _status "RUNNING" "iter $it (iter_${nn}) — gen done ($GEN_NPZ npz). Stage: train. Completed: $COMPLETED."
  TR_T0=$(date +%s)
  if [ ! -f "$CKPT" ]; then
    echo "[it$it] train (accumulate iter_00..iter_${nn}, window $WINDOW) @ $(date)"
    ( source "$CHAMP_ENV" && CUDA_VISIBLE_DEVICES=$TRAIN_GPU nice -n 19 "$PY" -u scripts/train_iter.py \
        --output-root "$OUT" --iter "$it" --window "$WINDOW" --warm-from "$PREV" --output "$CKPT" \
        --epochs "$EPOCHS" --batch-size "$BATCH" --value-loss-weight "$VLW" --aux-weight "$AUX_WEIGHT" \
        --stage-local "/tmp/distill_stage_${it}" \
        --prov-value-target outcome --prov-selfplay-leaf v2_9_bmild_cap8_curve125 \
        --prov-seed-range "${SEED}-$(( SEED + GAMES - 1 ))" --prov-run-tag "distill_stage1_it${it}" \
        > "$OUT/logs/train_it${it}.log" 2>&1 )
    rm -rf "/tmp/distill_stage_${it}" 2>/dev/null || true
    [ -f "$CKPT" ] || { echo "[it$it] TRAIN FAILED — halting" >&2; tail -20 "$OUT/logs/train_it${it}.log" >&2; _status "ERROR" "iter $it train FAILED (logs/train_it${it}.log)."; exit 1; }
  else
    echo "[it$it] train — ckpt exists, skip"
  fi
  TRAIN_SEC=$(( $(date +%s) - TR_T0 )); CKPT_METRICS="${CKPT%.pt}.metrics.json"

  # ---- screen (train-metrics collapse detector ONLY — no games) ----
  echo "[it$it] screen @ $(date)"
  if [ "$it" -eq 0 ]; then PARENT_ID="warmstart_canonical"; else PARENT_ID="iter_$(_nn $(( it - 1 )))"; fi
  "$PY" "$SCREEN" --iter "$it" --ckpt "$CKPT" --metrics "$CKPT_METRICS" \
    --parent-ckpt "$PREV" --parent-id "$PARENT_ID" --measure-dir "$MEASURE" \
    --sp-seed "$SEED" --games "$GAMES" --gen-npz "${GEN_NPZ:-0}" \
    --gen-sec "$GEN_SEC" --train-sec "$TRAIN_SEC" \
    --smoke-dir "" --smoke-seed "" --smoke-catastrophe-wr 0.25 \
    --val-pol-collapse-thresh "$VAL_POL_COLLAPSE_THRESH" \
    --leaf-label "v2.9 Bmild_cap8 curve125 (fair-champion distillation)" \
    --id-prefix distill --manifest-branch "$BRANCH" \
    --manifest-doc "Distill-flywheel stage-1 (fair-champion distillation) — checkpoint manifest (appended per iter)"
  SCREEN_RC=$?

  # ---- probe (distillation-fidelity forward pass; skip if the probe set isn't gen'd yet) ----
  PROBE_DIR=$OUT/probe_data/iter_00
  if ls "$PROBE_DIR"/seed_*.npz >/dev/null 2>&1; then
    echo "[it$it] probe_metrics @ $(date)"
    CUDA_VISIBLE_DEVICES=$TRAIN_GPU "$PY" "$PROBE" --iter "$it" --ckpt "$CKPT" \
      --probe-dir "$PROBE_DIR" --out "$OUT" --device cuda \
      >> "$OUT/logs/probe_it${it}.log" 2>&1 || echo "[it$it] WARN: probe_metrics failed (non-fatal)"
  else
    echo "[it$it] probe set absent ($PROBE_DIR) — skipping probe_metrics (operator gens it at launch)"
  fi

  date > "$OUT/done/iter$it"; COMPLETED=$((COMPLETED+1))
  if [ "$SCREEN_RC" = 3 ]; then
    echo "[it$it] ⚠️ CATASTROPHE (train collapse) — stopping the chain, preserving artifacts @ $(date)"
    _status "STOPPED-CATASTROPHE" "iter $it tripped the COLLAPSE screen. Chain STOPPED. Completed healthy iters: $((COMPLETED-1)). Checkpoints preserved under \`$OUT/ckpt\`."
    break
  fi
  echo "[it$it] ✅ iter complete (screen HEALTHY) @ $(date)"
  _status "RUNNING" "Last completed: iter_${nn} (iter $it). Total completed: $COMPLETED. Next: iter $((it+1))."
done

LAST=$(ls "$OUT"/ckpt/iter_*.pt 2>/dev/null | sort | tail -1)
echo ""; echo "=== DISTILL STAGE-1 DONE @ $(date) — completed $COMPLETED iter(s); latest: $LAST ==="
_status "DONE" "STAGE 1 finished. Completed $COMPLETED iteration(s). Latest: \`$LAST\`. STOP — stage 2 (fair-net flywheel, iters 4..11) is a SEPARATE task. Next: post-stage-1 review + the stage-2 build."
