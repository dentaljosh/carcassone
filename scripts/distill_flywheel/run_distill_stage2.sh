#!/usr/bin/env bash
# ============================================================================
# DISTILL-FLYWHEEL — STAGE 2 (iters 4..11): the FAIR-NET-PRIOR flywheel. [SIGHTED]
#
# Spec: measurement/distill_flywheel_20260715/STAGE2_FLYWHEEL_SPEC.md
#       + DESIGN_FAIR_ADDENDUM.md ("The fair flywheel stage") + DESIGN.md (§5/§6).
#
# CONTINUES the SIGHTED stage-1 run (SAME TAG dir) at iter 4. Per iter:
#   LOCAL  : export the SIGHTED net iter_(N-1) -> TorchScript (parity-gated) -> start a
#            per-iter carc-orch SHM server (--n-ch 81 --n-scalar 42, GPU) -> net-priors
#            FAIR gen (FairHeuristicPriorAgent with the SEVERED-VALUE-LOOP evaluator:
#            net POLICY head -> priors, FROZEN champion leaf -> value) at W28 through the
#            orch -> NET_GAMES=450 games. Kill the orch when the iter's gen completes.
#   LAPTOP : fair-CHAMPION side-stream (net-free, --sighted, W12, orch-OFF) -> CHAMP_GAMES
#            =150 games (the 25% anti-drift champion anchor). ckpt-independent, free-runs.
#   Both --shared-claim into <SHARE>/<TAG>/iter_<NN>/ (DISJOINT seed ranges) -> LOCAL train
#   accumulate ALL iters (--output-root <SHARE> --iter <it> --window 12; warm from iter_(N-1))
#   -> overnight_iter_screen collapse detector (rc=3 halts) -> probe_metrics fidelity probe.
#   Net ckpt for iter N gen = iter_(N-1).pt (the flywheel bootstrap).
#
# GEN + TRAIN ONLY — no in-loop game eval (probe_metrics is a pure forward pass).
# MEASUREMENT/EXPLORATORY: no promotion, PRODUCTION.yaml untouched, champion unchanged.
#
# ⚠️ RECIPE (NET_KDETS/NET_SIMS/NET_GAMES/CHAMP_GAMES) is GATED on the stage-1 result +
#    a strength eval — the MAIN AGENT tunes it before the real launch. Defaults below
#    mirror the fair champion budget (k4x688). Do NOT launch without Joshua's go.
#
# Dry run (prints the exact per-iter commands incl. the orch lifecycle, touches nothing):
#   bash scripts/distill_flywheel/run_distill_stage2.sh --dry-run
# Real launch (detached; operator runs this AFTER stage-1 + a strength eval + bundle sync):
#   nohup nice -n 19 bash scripts/distill_flywheel/run_distill_stage2.sh > /tmp/distill_stage2.log 2>&1 & disown
# ============================================================================
set -uo pipefail

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
TAG=${TAG:-distill_flywheel_sighted_20260716}  # CONTINUES the sighted stage-1 run (same dir)
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
EXPORT_TS=$REPO_LOCAL/scripts/export_torchscript.py
RUN_SERVER=$REPO_LOCAL/rust/carc-orch/run_server.sh

# --- FAIR-NET-prior gen recipe (severed value loop; frozen champion leaf value) ---
# Defaults mirror the fair champion budget (k4x688=2752). RECIPE — main agent may tune.
NET_KDETS=${NET_KDETS:-4}                       # determinizations/move (net-priors fair PIMC)
NET_SIMS=${NET_SIMS:-688}                       # PUCT sims/det (k4 x 688 = 2752 budget)
NET_BATCH=${NET_BATCH:-8}                        # within-search leaf batching for the NET priors (LATENCY, 2026-07-16):
                                                 # each per-det NeuralMCTS collects this many leaves under virtual loss
                                                 # -> ONE orch forward instead of a blocking round-trip per expansion.
                                                 # 8 = the SHM MAX_K cap (no gain past it); gen already ran batch-1.
                                                 # ONLY the NET stream batches; the champ side-stream stays serial+byte-exact.
CPUCT=${CPUCT:-1.5}; TAUP=${TAUP:-5.0}; VALUE_NORM=${VALUE_NORM:-15.0}
NET_GAMES=${NET_GAMES:-450}                     # LOCAL net-priors gen games/iter
# --- FAIR champion side-stream recipe (net-free, laptop; PRODUCTION.yaml fair_deploy) ---
KDETS=${KDETS:-4}                               # champ determinizations/move (CL-054)
CHAMP_SIMS=${CHAMP_SIMS:-688}                   # champ sims/det; k4 x 688 = 2752 budget
CHAMP_GAMES=${CHAMP_GAMES:-150}                 # LAPTOP champ side-stream games/iter (25% anchor)
GAMES=${GAMES:-$(( NET_GAMES + CHAMP_GAMES ))}  # total games/iter (gen-wait threshold)

# --- carc-orch SHM server (LOCAL only, GPU; per-iter launch/kill) ---
SHM_NAME=${SHM_NAME:-distill_stage2}            # /dev/shm/carc_<SHM_NAME>
ORCH_WORKERS=${ORCH_WORKERS:-28}               # SHM slots (>= W_LOCAL_NET)
FORWARDERS=${FORWARDERS:-4}; MAX_BATCH=${MAX_BATCH:-16}
BATCH_TIMEOUT_MS=${BATCH_TIMEOUT_MS:-2.0}; WATCHDOG_SECS=${WATCHDOG_SECS:-30}
NCH=${NCH:-81}; NSCALAR=${NSCALAR:-42}          # ⚠️ SIGHTED: run_server defaults to 78/12 — MUST pass 81/42
ORCH_READY_SECS=${ORCH_READY_SECS:-120}         # max wait for the server READY line (torch/cuda init)

# --- train recipe (identical to stage 1) ---
WINDOW=${WINDOW:-12}                            # accumulate ALL iters (globs iter_00..iter_it)
EPOCHS=${EPOCHS:-3}; BATCH=${BATCH:-256}; VLW=${VLW:-1.5}
AUX_WEIGHT=${AUX_WEIGHT:-0}                      # ownership OFF (fair emitter has no ownership labels)
TRAIN_GPU=${TRAIN_GPU:-0}                        # champ_env.sh hides CUDA for gen; train/probe re-enable it
VAL_POL_COLLAPSE_THRESH=${VAL_POL_COLLAPSE_THRESH:-4.0}   # pooled-visit target entropy ~1.35 -> 4.0 (as stage 1)

# --- boxes / workers ---
W_LOCAL_NET=${W_LOCAL_NET:-28}                  # LOCAL orch net-priors gen (orch-ON, GPU-batched forwards)
W_LAPTOP=${W_LAPTOP:-12}                         # LAPTOP champ side-stream (orch-OFF, net-free CPU)
USE_LAPTOP=${USE_LAPTOP:-1}

# --- loop control: STAGE 2 = iters 4..11 (continues the sighted run) ---
START=${START:-4}
END=${END:-11}
SEED_BASE=${SEED_BASE:-700000000}               # champ stream seed = SEED_BASE + it*100000 (DESIGN §3)
NET_SEED_OFF=${NET_SEED_OFF:-50000}             # net stream seed = champ seed + 50000 (disjoint ranges)

# --- self-heal (gen watchdog) ---
HEAL_CAP=${HEAL_CAP:-8}; STALL_GEN=${STALL_GEN:-15}
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# ---------------------------------------------------------------------------
_champ_seed_for() { echo $(( SEED_BASE + $1 * 100000 )); }
_net_seed_for()   { echo $(( SEED_BASE + $1 * 100000 + NET_SEED_OFF )); }
_nn()             { printf "%02d" "$1"; }
_prev_ckpt()      { echo "$OUT/ckpt/iter_$(_nn $(( $1 - 1 ))).pt"; }        # net ckpt = iter_(N-1)
_prev_ts()        { echo "$OUT/ckpt/iter_$(_nn $(( $1 - 1 ))).ts.pt"; }     # its TorchScript

# The exact per-iter commands (used by both the dry-run printer and the real launch,
# so they can never drift).
_export_cmd() {
  local it="$1" prev ts; prev=$(_prev_ckpt "$it"); ts=$(_prev_ts "$it")
  echo "# CUDA VISIBLE (clean shell — NOT champ_env.sh) — parity-gated TorchScript export:"
  echo "$PY $EXPORT_TS --checkpoint $prev --out $ts --device cuda"
}
_orch_cmd() {
  local it="$1" ts; ts=$(_prev_ts "$it")
  echo "# CUDA VISIBLE — per-iter carc-orch SHM server (SIGHTED $NCH ch / $NSCALAR scalars):"
  echo "nice -n 19 $RUN_SERVER --model $ts --transport shm --shm-name $SHM_NAME \\"
  echo "    --workers $ORCH_WORKERS --forwarders $FORWARDERS --max-batch $MAX_BATCH \\"
  echo "    --batch-timeout-ms $BATCH_TIMEOUT_MS --watchdog-secs $WATCHDOG_SECS \\"
  echo "    --n-ch $NCH --n-scalar $NSCALAR --device cuda > $OUT/logs/orch_it$(_nn "$it").log 2>&1 & disown"
}
_gen_cmd_local() {   # net-priors FAIR gen through the orch (workers hide CUDA, read priors over SHM)
  local it="$1" seed data nn prev; nn=$(_nn "$it"); seed=$(_net_seed_for "$it"); data="$OUT/iter_${nn}"; prev=$(_prev_ckpt "$it")
  echo "source $CHAMP_ENV && nohup nice -n 19 $PY -u $GEN \\"
  echo "    --games $NET_GAMES --k-dets $NET_KDETS --sims $NET_SIMS --c-puct $CPUCT --tau-p $TAUP --value-norm $VALUE_NORM \\"
  echo "    --sighted --net-ckpt $prev --shm-eval-server $SHM_NAME --workers $W_LOCAL_NET --batch-size $NET_BATCH \\"
  echo "    --seed-start $seed --out $data --shared-claim --claim-host 5800x \\"
  echo "    > $OUT/logs/gen_local_it${nn}.log 2>&1 & disown"
}
_gen_cmd_laptop() {   # fair-CHAMPION side-stream (net-free) — body piped via `ssh 'bash -s'` (cd on line 1)
  local it="$1" seed nn; nn=$(_nn "$it"); seed=$(_champ_seed_for "$it")
  echo "cd $REPO_LAPTOP || exit 1"
  echo "source $CHAMP_ENV_R"
  echo "setsid nice -n 19 $REPO_LAPTOP/.venv/bin/python -u $GENR \\"
  echo "    --games $CHAMP_GAMES --k-dets $KDETS --sims $CHAMP_SIMS --c-puct $CPUCT --tau-p $TAUP --value-norm $VALUE_NORM \\"
  echo "    --sighted --workers $W_LAPTOP --seed-start $seed --out $OUTR/iter_${nn} --shared-claim --claim-host laptop \\"
  echo "    > /tmp/distill_gen_laptop_it${nn}.log 2>&1 </dev/null &"
}
_train_cmd() {
  local it="$1" nn prev seed; nn=$(_nn "$it"); prev=$(_prev_ckpt "$it"); seed=$(_net_seed_for "$it")
  echo "source $CHAMP_ENV && CUDA_VISIBLE_DEVICES=$TRAIN_GPU nice -n 19 $PY -u scripts/train_iter.py \\"
  echo "    --output-root $OUT --iter $it --window $WINDOW --warm-from $prev --output $OUT/ckpt/iter_${nn}.pt \\"
  echo "    --epochs $EPOCHS --batch-size $BATCH --value-loss-weight $VLW --aux-weight $AUX_WEIGHT \\"
  echo "    --stage-local /tmp/distill_stage_${it} \\"
  echo "    --prov-value-target outcome --prov-selfplay-leaf v2_9_bmild_cap8_curve125 \\"
  echo "    --prov-seed-range ${seed}-$(( seed + NET_GAMES - 1 )) --prov-run-tag distill_stage2_it${it}"
}

# ---------------------------------------------------------------------------
# DRY RUN: print the exact commands per iter, touch nothing, exit.
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = 1 ]; then
  echo "=== DISTILL STAGE-2 (fair-NET-prior flywheel) DRY RUN — iters $START..$END ==="
  echo "run root (local)  : $OUT"
  echo "run root (laptop) : $OUTR"
  echo "net recipe        : NET_GAMES=$NET_GAMES  k_dets=$NET_KDETS x sims=$NET_SIMS (=$(( NET_KDETS*NET_SIMS )) budget)  c_puct=$CPUCT tau_p=$TAUP value_norm=$VALUE_NORM"
  echo "champ side-stream : CHAMP_GAMES=$CHAMP_GAMES  k_dets=$KDETS x sims=$CHAMP_SIMS (=$(( KDETS*CHAMP_SIMS )) budget) [net-free anchor]"
  echo "gen total/iter    : GAMES=$GAMES (net $NET_GAMES local + champ $CHAMP_GAMES laptop, DISJOINT seeds, shared-claim)"
  echo "orch              : SHM $SHM_NAME  workers=$ORCH_WORKERS forwarders=$FORWARDERS max_batch=$MAX_BATCH n_ch=$NCH n_scalar=$NSCALAR (SIGHTED)"
  echo "train             : window=$WINDOW epochs=$EPOCHS batch=$BATCH vlw=$VLW aux_weight=$AUX_WEIGHT (ownership OFF)"
  echo "boxes             : LOCAL orch net W$W_LOCAL_NET + LAPTOP champ W$W_LAPTOP (use_laptop=$USE_LAPTOP)"
  echo "warm-from iter N  : iter_(N-1).pt  (net ckpt for iter N gen = iter_(N-1).pt) — iter4 needs iter_03.pt from stage 1"
  for it in $(seq "$START" "$END"); do
    echo ""; echo "########## ITER $it -> iter_$(_nn "$it") (warm/net-ckpt = iter_$(_nn $(( it-1 ))).pt) ##########"
    echo "--- 1. export TS ---";        _export_cmd "$it"
    echo "--- 2. start orch ---";       _orch_cmd "$it"
    echo "--- 3a. gen LOCAL (net-priors fair, orch) ---"; _gen_cmd_local "$it"
    if [ "$USE_LAPTOP" = 1 ]; then
      echo "--- 3b. gen LAPTOP (fair champion side-stream, net-free) ---"; _gen_cmd_laptop "$it"
    fi
    echo "--- 4. wait: poll $OUT/iter_$(_nn "$it")/*.npz until >= $GAMES (watchdog STALL_GEN=$STALL_GEN, HEAL_CAP=$HEAL_CAP) ---"
    echo "--- 5. STOP orch (pkill carc-orch $SHM_NAME + rm /dev/shm/carc_$SHM_NAME) ---"
    echo "--- 6. train (LOCAL, accumulate iter_00..iter_$(_nn "$it")) ---"; _train_cmd "$it"
    echo "--- 7. screen (rc=3 -> HALT) + probe_metrics ---"
  done
  echo ""; echo "=== END DRY RUN (iters $START..$END) ==="
  exit 0
fi

# ---------------------------------------------------------------------------
# REAL RUN
# ---------------------------------------------------------------------------
mkdir -p "$OUT/ckpt" "$OUT/done" "$OUT/logs" "$MEASURE"
cd "$REPO_LOCAL" || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
[ -f "$GEN" ]        || { echo "FATAL: emitter missing: $GEN" >&2; exit 1; }
[ -f "$CHAMP_ENV" ]  || { echo "FATAL: champ_env.sh missing: $CHAMP_ENV" >&2; exit 1; }
[ -f "$EXPORT_TS" ]  || { echo "FATAL: export_torchscript.py missing: $EXPORT_TS" >&2; exit 1; }
[ -x "$RUN_SERVER" ] || { echo "FATAL: run_server.sh missing/not-exec: $RUN_SERVER" >&2; exit 1; }
[ -s "$(_prev_ckpt "$START")" ] || { echo "FATAL: stage-1 seed ckpt missing: $(_prev_ckpt "$START") (run stage 1 to iter $((START-1)) first)" >&2; exit 1; }

_status() {
  local state="$1" detail="$2"
  cat > "$MEASURE/STAGE2_STATUS.md" <<EOF
# Distill-flywheel STAGE 2 (fair-NET-prior flywheel) — LIVE STATUS

**State:** $state
**Updated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Branch:** $BRANCH · **Tag:** $TAG · **Iters:** $START..$END (STAGE 2)

$detail

---
- Gen agent (LOCAL): FairHeuristicPriorAgent + net-priors evaluator (severed value loop: net POLICY -> priors, FROZEN champion leaf -> value), k_dets=$NET_KDETS x sims=$NET_SIMS, through carc-orch SHM ($SHM_NAME, $NCH ch/$NSCALAR sc).
- Champ side-stream (LAPTOP, net-free): FairHeuristicPriorAgent k_dets=$KDETS x sims=$CHAMP_SIMS, curve125 — the 25% anti-drift anchor.
- Recipe: net $NET_GAMES + champ $CHAMP_GAMES = $GAMES/iter · window=$WINDOW · epochs=$EPOCHS · batch=$BATCH · vlw=$VLW · aux_weight=$AUX_WEIGHT.
- Warm: iter N <- iter_(N-1).pt (net ckpt for iter N gen = iter_(N-1).pt). Accumulate ALL iters. Checkpoints: \`$OUT/ckpt/iter_*.pt\`.
- GEN + TRAIN ONLY — no in-loop game eval. MEASUREMENT/EXPLORATORY; PRODUCTION.yaml untouched. STOP after iter $END (eval = separate task).
EOF
}

_stop_orch() {   # kill the local orch server + clear its SHM segments (idempotent)
  pkill -9 -f "carc-orch.*--shm-name $SHM_NAME" 2>/dev/null || true
  pkill -9 -f "carc-orch.*$SHM_NAME" 2>/dev/null || true
  rm -f "/dev/shm/carc_${SHM_NAME}" /dev/shm/sem.carc_${SHM_NAME}_* 2>/dev/null || true
}

_start_orch() {   # export TS (parity-gated) + start the orch server + wait for READY
  local it="$1" prev ts nn; nn=$(_nn "$it"); prev=$(_prev_ckpt "$it"); ts=$(_prev_ts "$it")
  # 1. parity-gated TorchScript export (CUDA visible — a CLEAN shell, no champ_env CUDA-hide).
  if [ ! -s "$ts" ] || [ "$ts" -ot "$prev" ]; then
    echo "[it$it] export TS: $prev -> $ts @ $(date)"
    if ! "$PY" "$EXPORT_TS" --checkpoint "$prev" --out "$ts" --device cuda > "$OUT/logs/export_it${nn}.log" 2>&1; then
      echo "[it$it] FATAL: TorchScript export/parity FAILED" >&2; tail -20 "$OUT/logs/export_it${nn}.log" >&2
      _status "ERROR" "iter $it: TorchScript export/parity FAILED (logs/export_it${nn}.log)."; exit 1
    fi
  fi
  # 2. start the SHM server (SIGHTED n_ch/n_scalar — run_server defaults to 78/12) + wait READY.
  _stop_orch; sleep 1
  nice -n 19 "$RUN_SERVER" --model "$ts" --transport shm --shm-name "$SHM_NAME" \
    --workers "$ORCH_WORKERS" --forwarders "$FORWARDERS" --max-batch "$MAX_BATCH" \
    --batch-timeout-ms "$BATCH_TIMEOUT_MS" --watchdog-secs "$WATCHDOG_SECS" \
    --n-ch "$NCH" --n-scalar "$NSCALAR" --device cuda \
    > "$OUT/logs/orch_it${nn}.log" 2>&1 &
  local ready=0 i
  for i in $(seq 1 "$ORCH_READY_SECS"); do
    if grep -q "READY" "$OUT/logs/orch_it${nn}.log" 2>/dev/null && [ -e "/dev/shm/carc_${SHM_NAME}" ]; then ready=1; break; fi
    sleep 1
  done
  if [ "$ready" != 1 ]; then
    echo "[it$it] FATAL: orch not READY in ${ORCH_READY_SECS}s" >&2; tail -20 "$OUT/logs/orch_it${nn}.log" >&2
    _status "ERROR" "iter $it: carc-orch server never reached READY (logs/orch_it${nn}.log)."; _stop_orch; exit 1
  fi
  echo "[it$it] orch READY ($(grep -m1 READY "$OUT/logs/orch_it${nn}.log"))"
}

_kill_one() {   # kill pattern on both boxes; [x]yz self-match guard so this pkill can't hit itself
  local pat="[${1:0:1}]${1:1}"
  pkill -9 -f "$pat" 2>/dev/null || true
  [ "$USE_LAPTOP" = 1 ] && timeout 20 ssh -o ConnectTimeout=10 "$LAPTOP_SSH" "pkill -9 -f '$pat'" </dev/null >/dev/null 2>&1 || true
}
_kill_gen() {   # reap the gen pools (fork/spawn workers inherit argv) + the mp tracker; orch handled separately
  _kill_one gen_fair_distill
  _kill_one multiprocessing.resource_tracker
  _kill_one multiprocessing.spawn
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

_gen_launch() {   # (re)start the orch + local net gen + (backgrounded) laptop champ gen for iter $1
  local it="$1" nn seed prev; nn=$(_nn "$it"); seed=$(_net_seed_for "$it"); prev=$(_prev_ckpt "$it")
  _start_orch "$it"
  # LOCAL net-priors fair gen through the orch (source champ_env for the frozen leaf +
  # CUDA-hide in the GEN workers; the orch server started ABOVE keeps CUDA — separate proc).
  ( source "$CHAMP_ENV" && nohup nice -n 19 "$PY" -u "$GEN" \
      --games "$NET_GAMES" --k-dets "$NET_KDETS" --sims "$NET_SIMS" --c-puct "$CPUCT" \
      --tau-p "$TAUP" --value-norm "$VALUE_NORM" --sighted --net-ckpt "$prev" \
      --shm-eval-server "$SHM_NAME" --workers "$W_LOCAL_NET" --batch-size "$NET_BATCH" \
      --seed-start "$seed" --out "$OUT/iter_${nn}" --shared-claim --claim-host 5800x \
      > "$OUT/logs/gen_local_it${nn}.log" 2>&1 & )
  # LAPTOP fair-champion side-stream (net-free; background the ssh call — rc=124=launched).
  if [ "$USE_LAPTOP" = 1 ]; then
    local script="/tmp/distill_stage2_laptop_gen_it${nn}.sh"
    _gen_cmd_laptop "$it" > "$script"
    (
      timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" 'bash -s' < "$script"
      rc=$?
      if [ "$rc" = 124 ]; then echo "  [it$it] laptop champ gen launched (rc=124, setsid held ssh — not retried)"
      elif [ "$rc" != 0 ]; then echo "  [it$it] laptop champ gen launch rc=$rc (box may be down this iter)"; fi
    ) &
  fi
}

_FINALIZED=0
_finalize() {
  [ "$_FINALIZED" = 1 ] && return; _FINALIZED=1
  _kill_gen; _stop_orch
  echo "=== distill stage-2 exiting @ $(date) (cleaned gen pools + orch on both boxes) ==="
}
trap _finalize EXIT
trap 'echo "[signal] TERM/INT @ $(date) — finalizing"; _status "INTERRUPTED" "Caught a termination signal; gen pools + orch cleaned, all completed checkpoints preserved under \`$OUT/ckpt\`."; exit 130' INT TERM

echo "=== DISTILL STAGE-2 (fair-NET-prior flywheel) @ $(date) — TAG=$TAG iters $START..$END ==="
echo "    gen (LOCAL): net-priors FairHeuristicPriorAgent k_dets=$NET_KDETS x sims=$NET_SIMS via orch $SHM_NAME ($NCH/$NSCALAR) · $NET_GAMES games"
echo "    champ (LAPTOP): net-free fair champion k_dets=$KDETS x sims=$CHAMP_SIMS · $CHAMP_GAMES games (25% anchor)"
echo "    train: window $WINDOW · aux_weight $AUX_WEIGHT · warm iter N <- iter_(N-1)"

# --- git-bundle code sync (stub — operator does the authoritative sync; this makes the
#     laptop run current $BRANCH code incl. the fair-net gen path) ---
git bundle create "$SHARE_LOCAL/code_sync/carc_${BRANCH}.bundle" "$BRANCH" >/dev/null 2>&1 \
  && echo "  bundle tip: $(git rev-parse --short "$BRANCH")" || echo "  WARN: bundle create failed (operator will sync)"
if [ "$USE_LAPTOP" = 1 ]; then
  if timeout 60 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
       "git -C $REPO_LAPTOP fetch $SHARE_REMOTE/code_sync/carc_${BRANCH}.bundle $BRANCH && git -C $REPO_LAPTOP reset --hard FETCH_HEAD" \
       </dev/null >/dev/null 2>&1; then
    echo "  laptop synced to $(git rev-parse --short "$BRANCH")"
  else
    echo "  WARN: laptop sync FAILED — disabling laptop, running LOCAL-net-ONLY (no champ anchor this run)"; USE_LAPTOP=0
  fi
fi

_status "RUNNING" "Starting iter $START. No stage-2 iteration completed yet."
COMPLETED=0

for it in $(seq "$START" "$END"); do
  nn=$(_nn "$it"); CKPT=$OUT/ckpt/iter_${nn}.pt; DATA=$OUT/iter_${nn}
  NSEED=$(_net_seed_for "$it"); PREV=$(_prev_ckpt "$it")
  if [ -f "$OUT/done/iter$it" ]; then echo "[it$it] already complete — skip (reboot-resume)"; COMPLETED=$((COMPLETED+1)); continue; fi
  [ -s "$PREV" ] || { echo "[it$it] FATAL: net/warm ckpt $PREV missing/empty" >&2; _status "ERROR" "iter $it: iter_$(_nn $((it-1))).pt missing — stopped."; exit 1; }
  echo ""; echo "########## DISTILL STAGE-2 ITER $it -> iter_${nn} @ $(date) (net/warm = $(basename "$PREV")) ##########"
  _status "RUNNING" "iter $it (iter_${nn}) IN PROGRESS — net/warm $(basename "$PREV"). Completed so far: $COMPLETED. Stage: gen."

  # ---- gen (LOCAL net-priors fair via orch + LAPTOP champ side-stream, work-stealing) ----
  GEN_T0=$(date +%s)
  if [ ! -f "$OUT/done/gen$it" ]; then
    echo "[it$it] gen net_seed=$NSEED (+champ) -> $DATA @ $(date)"
    mkdir -p "$DATA"; _clean_stranded "$DATA" 0
    _kill_gen; _stop_orch; sleep 2; _gen_launch "$it"
    glast=-1; gstall=0; gheals=0
    while [ "$(ls "$DATA"/*.npz 2>/dev/null | wc -l)" -lt "$GAMES" ]; do
      sleep 60
      gcur=$(ls "$DATA"/*.npz 2>/dev/null | wc -l)
      if [ "$gcur" -eq "$glast" ]; then gstall=$((gstall+1)); else gstall=0; glast=$gcur; fi
      if [ "$gstall" -ge "$STALL_GEN" ]; then
        gheals=$((gheals+1))
        [ "$gheals" -gt "$HEAL_CAP" ] && { echo "[it$it] FATAL: $gheals gen heals, stuck $gcur/$GAMES" >&2; _status "ERROR" "iter $it gen stuck at $gcur/$GAMES after $HEAL_CAP heals."; exit 1; }
        echo "[it$it] gen STALLED $gcur/$GAMES — heal $gheals: kill+clean+relaunch (orch too) @ $(date)"
        _kill_gen; _stop_orch; sleep 2; _clean_stranded "$DATA" 30; _gen_launch "$it"; gstall=0
      fi
    done
    _kill_gen; _stop_orch; sleep 1
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
        --prov-seed-range "${NSEED}-$(( NSEED + NET_GAMES - 1 ))" --prov-run-tag "distill_stage2_it${it}" \
        > "$OUT/logs/train_it${it}.log" 2>&1 )
    rm -rf "/tmp/distill_stage_${it}" 2>/dev/null || true
    [ -f "$CKPT" ] || { echo "[it$it] TRAIN FAILED — halting" >&2; tail -20 "$OUT/logs/train_it${it}.log" >&2; _status "ERROR" "iter $it train FAILED (logs/train_it${it}.log)."; exit 1; }
  else
    echo "[it$it] train — ckpt exists, skip"
  fi
  TRAIN_SEC=$(( $(date +%s) - TR_T0 )); CKPT_METRICS="${CKPT%.pt}.metrics.json"

  # ---- screen (train-metrics collapse detector ONLY — no games) ----
  echo "[it$it] screen @ $(date)"
  PARENT_ID="iter_$(_nn $(( it - 1 )))"
  "$PY" "$SCREEN" --iter "$it" --ckpt "$CKPT" --metrics "$CKPT_METRICS" \
    --parent-ckpt "$PREV" --parent-id "$PARENT_ID" --measure-dir "$MEASURE" \
    --sp-seed "$NSEED" --games "$GAMES" --gen-npz "${GEN_NPZ:-0}" \
    --gen-sec "$GEN_SEC" --train-sec "$TRAIN_SEC" \
    --smoke-dir "" --smoke-seed "" --smoke-catastrophe-wr 0.25 \
    --val-pol-collapse-thresh "$VAL_POL_COLLAPSE_THRESH" \
    --leaf-label "v2.9 Bmild_cap8 curve125 (fair-net-prior flywheel; severed value loop)" \
    --id-prefix distill --manifest-branch "$BRANCH" \
    --manifest-doc "Distill-flywheel stage-2 (fair-net-prior flywheel) — checkpoint manifest (appended per iter)"
  SCREEN_RC=$?

  # ---- probe (distillation-fidelity forward pass; skip if the probe set isn't gen'd yet) ----
  PROBE_DIR=$OUT/probe_data/iter_00
  if ls "$PROBE_DIR"/seed_*.npz >/dev/null 2>&1; then
    echo "[it$it] probe_metrics @ $(date)"
    CUDA_VISIBLE_DEVICES=$TRAIN_GPU "$PY" "$PROBE" --iter "$it" --ckpt "$CKPT" \
      --probe-dir "$PROBE_DIR" --out "$OUT" --device cuda \
      >> "$OUT/logs/probe_it${it}.log" 2>&1 || echo "[it$it] WARN: probe_metrics failed (non-fatal)"
  else
    echo "[it$it] probe set absent ($PROBE_DIR) — skipping probe_metrics"
  fi

  date > "$OUT/done/iter$it"; COMPLETED=$((COMPLETED+1))
  if [ "$SCREEN_RC" = 3 ]; then
    echo "[it$it] ⚠️ CATASTROPHE (train collapse) — stopping the chain, preserving artifacts @ $(date)"
    _status "STOPPED-CATASTROPHE" "iter $it tripped the COLLAPSE screen. Chain STOPPED. Completed healthy stage-2 iters: $((COMPLETED-1)). Checkpoints preserved under \`$OUT/ckpt\`."
    break
  fi
  echo "[it$it] ✅ iter complete (screen HEALTHY) @ $(date)"
  _status "RUNNING" "Last completed: iter_${nn} (iter $it). Total stage-2 completed: $COMPLETED. Next: iter $((it+1))."
done

LAST=$(ls "$OUT"/ckpt/iter_*.pt 2>/dev/null | sort | tail -1)
echo ""; echo "=== DISTILL STAGE-2 DONE @ $(date) — completed $COMPLETED stage-2 iter(s); latest: $LAST ==="
_status "DONE" "STAGE 2 finished. Completed $COMPLETED stage-2 iteration(s). Latest: \`$LAST\`. Next: the fair iter-12 eval (sighted net vs fair champion + net-iterN ladder) — a SEPARATE task."
