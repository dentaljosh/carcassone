#!/usr/bin/env bash
# ============================================================================
# az_zero — TABULA-RASA AlphaZero mini-loop (LOCAL ONLY).
#
# The project's net-value + net-policy self-play machinery (scripts/run_selfplay_iter.py
# / src/carcassonne_ai/selfplay.py), but started from a RANDOM-INIT network
# (iter_-1_random.pt from make_random_ckpt.py) instead of the heuristic warm-start.
# The FIRST true zero-start experiment in the project.
#
# Per iter:
#   gen  : 300 self-play games, NeuralMCTS sims=128, net PRIORS + net VALUE leaf
#          (--leaf-eval nn, --value-target score_diff = tanh((p0-p1)/15) OUTCOME),
#          Dirichlet(0.3)+eps(0.25) root noise, tau=1 for the opening then tau=0.
#          W14, nice -19, LOCAL ONLY (no laptop). Orch-SHM (GPU-batched) by
#          default; USE_ORCH=0 falls back to per-worker net-on-CPU.
#   train: scripts/train_iter.py --warm-from prev, window 4, epochs 3, batch 256,
#          aux-weight 0, value-loss-weight VLW, entropy-floor DISABLED (a random-
#          init baseline would false-trip the 0.5x floor as the policy sharpens).
#   screen (every SCREEN_EVERY iters + the final iter): n=50 games at sims=128 vs
#          (a) a uniform-random player, (b) the warm-start net-agent — the
#          "what does the heuristic scaffolding buy?" comparison.
#
# ⚠️ MEASUREMENT / EXPLORATORY. Touches NOTHING under governance/PRODUCTION.yaml,
# the champion, checkpoints/ lineage, or the live distill_strong_20260723 gen run.
# All az_zero artifacts live under $OUT (default /mnt/c/carc-shared/az_zero_20260724).
#
# Dry run (prints the exact per-iter commands, touches nothing):
#   bash scripts/az_zero/run_az_zero.sh --dry-run
# Real launch (detached; operator runs AFTER review):
#   nohup nice -n 19 bash scripts/az_zero/run_az_zero.sh > /tmp/az_zero.log 2>&1 & disown
# ============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# EDITABLE CONFIG (top-of-script knobs)
# ---------------------------------------------------------------------------
REPO_LOCAL=${REPO_LOCAL:-/home/doctor/projects/carcassone}
SHARE_LOCAL=${SHARE_LOCAL:-/mnt/c/carc-shared}
PY=$REPO_LOCAL/.venv/bin/python
TAG=${TAG:-az_zero_20260724}
BRANCH=${BRANCH:-rod_v2_flywheel}
OUT=${OUT:-$SHARE_LOCAL/$TAG}                 # run root (buffer + ckpt + logs)
MEASURE=${MEASURE:-$REPO_LOCAL/measurement/$TAG}
GEN=$REPO_LOCAL/scripts/run_selfplay_iter.py
GEN_ORCH=$REPO_LOCAL/scripts/canonical_az/gen_m2_orch.sh
TRAIN=$REPO_LOCAL/scripts/train_iter.py
SCREEN=$REPO_LOCAL/scripts/az_zero/eval_anchor_screen.py

# iter-0 warm-from = the RANDOM-INIT checkpoint (tabula rasa).
RANDOM_CKPT=${RANDOM_CKPT:-$OUT/ckpt/iter_-1_random.pt}

# --- self-play recipe (pure NN leaf: net priors + net value head) ---
GAMES=${GAMES:-300}                           # games/iter (LOCAL only)
SIMS=${SIMS:-128}                             # NeuralMCTS sims/move
CPUCT=${CPUCT:-3.0}
FPU=${FPU:-0.6}                               # first-play-urgency (M2 sighted precedent)
VALUE_TARGET=${VALUE_TARGET:-score_diff}      # OUTCOME target tanh((p0-p1)/15)
W_GEN=${W_GEN:-14}                            # LOCAL self-play workers

# --- train recipe ---
WINDOW=${WINDOW:-4}                           # replay buffer = last 4 iters
EPOCHS=${EPOCHS:-3}; BATCH=${BATCH:-256}
# value-loss-weight: 1.0 = AZ-canonical equal weighting (train_iter default). NOTE:
# policy CE (over ~2511 actions) out-magnitudes value MSE ~5-10x, so 1.0 UNDER-
# weights the value head — and here the value head IS the self-play leaf. If the
# value↔outcome corr stalls low, bump to 1.5-3 (the distill flywheel used 1.5 for
# outcome targets). Left at 1.0 as the least-surprising default; see DESIGN.md.
VLW=${VLW:-1.0}
AUX_WEIGHT=${AUX_WEIGHT:-0}                    # ownership head OFF (per spec)
# entropy-floor OFF: the warm-from at iter 0 is the RANDOM net (near-uniform, high-
# entropy policy). Legitimate AZ policy sharpening drops entropy well below the
# 0.5x floor -> a FALSE collapse halt. Disable it for the zero-start lineage.
ENTROPY_FLOOR=${ENTROPY_FLOOR:-0}
TRAIN_GPU=${TRAIN_GPU:-0}                      # train on this CUDA device index

# --- anchor screen ---
SCREEN_EVERY=${SCREEN_EVERY:-2}               # screen at iters 0,2,4,... + final
SCREEN_N=${SCREEN_N:-50}
SCREEN_W=${SCREEN_W:-8}
# ⚠️ ANCHOR_CKPT default = warmstart_canonical.pt (BLIND 78ch/10) per the task.
# It confounds REP (blind vs the sighted candidate) with SCAFFOLDING. For a clean
# "what scaffolding buys" comparison use the SAME-ARCH sighted warm-start:
#   ANCHOR_CKPT=/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt
# The eval harness peeks each ckpt's dims and gives each side its own encoder, so
# either works. See DESIGN.md "Known caveats".
ANCHOR_CKPT=${ANCHOR_CKPT:-$REPO_LOCAL/checkpoints/warmstart_canonical.pt}

# --- gen transport: 1 = carc-orch SHM (GPU-batched), 0 = net-on-CPU fallback ---
USE_ORCH=${USE_ORCH:-1}

# --- loop control ---
START=${START:-0}
END=${END:-11}                                # 12 iters (0..11)
SEED_BASE=${SEED_BASE:-0}                      # run_selfplay_iter seeds = iter*10000 + seed_start

# --- production leaf env: only the Cython FEATURIZER matters here (leaf VALUE is
#     the net head, so the v2.9 curve/leaf knobs are INERT under --leaf-eval nn). ---
export CARCASSONNE_USE_CY_REPR=${CARCASSONNE_USE_CY_REPR:-1}
export CARCASSONNE_USE_FLAT_LEAF=${CARCASSONNE_USE_FLAT_LEAF:-1}
export CARCASSONNE_USE_CY_LEAF=${CARCASSONNE_USE_CY_LEAF:-1}
# ⚠️ Cap BLAS/torch intra-op threads to 1. net-on-CPU (the gen fallback + the
# net-on-CPU anchor screen) OVERSUBSCRIBES cores otherwise — one worker spawns ~all
# cores of torch threads, 2 workers thrash (measured: 875%% CPU/worker at W2). One
# thread per worker + more WORKERS is the right knob (memory: desktop_friendly_selfplay).
# Harmless for the orch path (net on GPU; workers do Python/Cython search) and train.
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
export MKL_NUM_THREADS=${MKL_NUM_THREADS:-1}
export OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-1}

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# ---------------------------------------------------------------------------
_nn()       { printf "%02d" "$1"; }
_warm_for() { if [ "$1" -eq 0 ]; then echo "$RANDOM_CKPT"; else echo "$OUT/ckpt/iter_$(_nn $(( $1 - 1 ))).pt"; fi; }

_gen_cmd() {   # printed by --dry-run AND run by the real launch (never drift)
  local it="$1" warm nn; nn=$(_nn "$it"); warm=$(_warm_for "$it")
  if [ "$USE_ORCH" = 1 ]; then
    echo "REPO=$REPO_LOCAL HOST=5800x WARM=$warm ITER=$it OUT=$OUT \\"
    echo "  GAMES=$GAMES SIMS=$SIMS CPUCT=$CPUCT FPU=$FPU VALUE_TARGET=$VALUE_TARGET OW=$W_GEN SEED_START=$SEED_BASE \\"
    echo "  nice -n 19 bash $GEN_ORCH --leaf-eval nn"
  else
    echo "CUDA_VISIBLE_DEVICES=\"\" nice -n 19 $PY -u $GEN \\"
    echo "  --checkpoint $warm --iter $it --games $GAMES --sims $SIMS --c-puct $CPUCT --fpu $FPU \\"
    echo "  --value-target $VALUE_TARGET --leaf-eval nn --workers $W_GEN \\"
    echo "  --seed-start $SEED_BASE --output-root $OUT > $OUT/logs/gen_it${nn}.log 2>&1"
  fi
}

_train_cmd() {
  local it="$1" nn warm; nn=$(_nn "$it"); warm=$(_warm_for "$it")
  echo "CUDA_VISIBLE_DEVICES=$TRAIN_GPU nice -n 19 $PY -u $TRAIN \\"
  echo "  --output-root $OUT --iter $it --window $WINDOW --warm-from $warm --output $OUT/ckpt/iter_${nn}.pt \\"
  echo "  --epochs $EPOCHS --batch-size $BATCH --value-loss-weight $VLW --aux-weight $AUX_WEIGHT \\"
  echo "  --entropy-floor-frac $ENTROPY_FLOOR --stage-local /tmp/az_zero_stage_${it} \\"
  echo "  --prov-value-target $VALUE_TARGET --prov-selfplay-leaf nn_value_head --prov-run-tag az_zero_it${it}"
}

_screen_cmd() {   # two calls: vs random + vs warm-start net
  local it="$1" nn ck; nn=$(_nn "$it"); ck=$OUT/ckpt/iter_${nn}.pt
  echo "CUDA_VISIBLE_DEVICES=\"\" nice -n 19 $PY -u $SCREEN --cand-ckpt $ck --opponent random \\"
  echo "  --n $SCREEN_N --sims $SIMS --c-puct $CPUCT --fpu $FPU --workers $SCREEN_W --device cpu \\"
  echo "  --out $OUT/screens/iter_${nn}/vs_random"
  echo "CUDA_VISIBLE_DEVICES=\"\" nice -n 19 $PY -u $SCREEN --cand-ckpt $ck --opponent net --anchor-ckpt $ANCHOR_CKPT \\"
  echo "  --n $SCREEN_N --sims $SIMS --c-puct $CPUCT --fpu $FPU --workers $SCREEN_W --device cpu \\"
  echo "  --out $OUT/screens/iter_${nn}/vs_warmstart"
}

_screen_iter() { local it="$1"; [ $(( it % SCREEN_EVERY )) -eq 0 ] || [ "$it" -eq "$END" ]; }

# ---------------------------------------------------------------------------
# DRY RUN
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = 1 ]; then
  echo "=== az_zero DRY RUN — iters $START..$END (TABULA RASA, LOCAL ONLY) ==="
  echo "run root       : $OUT"
  echo "random ckpt    : $RANDOM_CKPT"
  echo "gen            : GAMES=$GAMES sims=$SIMS c_puct=$CPUCT fpu=$FPU value_target=$VALUE_TARGET W=$W_GEN  transport=$([ "$USE_ORCH" = 1 ] && echo orch-SHM || echo net-on-CPU)"
  echo "train          : window=$WINDOW epochs=$EPOCHS batch=$BATCH vlw=$VLW aux_weight=$AUX_WEIGHT entropy_floor=$ENTROPY_FLOOR (OFF)"
  echo "screen         : every $SCREEN_EVERY iters (+final) — n=$SCREEN_N sims=$SIMS vs random + vs $(basename "$ANCHOR_CKPT")"
  for it in $(seq "$START" "$END"); do
    echo ""; echo "########## ITER $it -> iter_$(_nn "$it") (warm from $(basename "$(_warm_for "$it")")) ##########"
    echo "--- gen ---";   _gen_cmd "$it"
    echo "--- train ---"; _train_cmd "$it"
    if _screen_iter "$it"; then echo "--- screen (n=$SCREEN_N vs random + vs warm-start) ---"; _screen_cmd "$it"; fi
  done
  echo ""; echo "=== END DRY RUN ==="
  exit 0
fi

# ---------------------------------------------------------------------------
# REAL RUN
# ---------------------------------------------------------------------------
mkdir -p "$OUT/ckpt" "$OUT/done" "$OUT/logs" "$OUT/screens" "$MEASURE"
cd "$REPO_LOCAL" || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
[ -f "$RANDOM_CKPT" ] || { echo "FATAL: random-init ckpt missing: $RANDOM_CKPT (run make_random_ckpt.py)" >&2; exit 1; }
[ -f "$ANCHOR_CKPT" ] || echo "WARN: anchor ckpt $ANCHOR_CKPT missing — the vs-warmstart screen will fail (vs-random still runs)"

_kill_gen() {   # reap ONLY the self-play main + THIS loop's orch server. Deliberately
  # SPECIFIC: gen runs synchronously (the `with Pool` reaps its own workers on
  # normal exit), so this is belt-and-suspenders for a crashed prior attempt.
  # ⚠️ Do NOT pkill 'multiprocessing.resource_tracker' or generic spawn patterns —
  # that would also kill any OTHER multiprocessing job on the box (e.g. a live
  # production gen). run_selfplay_iter.py is our unique main; m2gen5800x is the
  # unique shm-name gen_m2_orch.sh launches. Self-match guarded ([r]/[c]).
  pkill -9 -f "[r]un_selfplay_iter.py" 2>/dev/null || true
  pkill -9 -f "[c]arc-orch.*--shm-name m2gen5800x" 2>/dev/null || true
}
_FINALIZED=0
_finalize() { [ "$_FINALIZED" = 1 ] && return; _FINALIZED=1; _kill_gen; echo "=== az_zero exiting @ $(date) (cleaned gen pools) ==="; }
trap _finalize EXIT
trap 'echo "[signal] TERM/INT @ $(date) — finalizing"; exit 130' INT TERM

echo "=== az_zero @ $(date) — TAG=$TAG iters $START..$END games=$GAMES sims=$SIMS ==="
echo "    tabula rasa warm-from: $RANDOM_CKPT"
echo "    gen transport: $([ "$USE_ORCH" = 1 ] && echo 'orch-SHM (GPU-batched)' || echo 'net-on-CPU'), W=$W_GEN, LOCAL ONLY"

COMPLETED=0
for it in $(seq "$START" "$END"); do
  nn=$(_nn "$it"); CKPT=$OUT/ckpt/iter_${nn}.pt; DATA=$OUT/iter_${nn}
  PREV=$(_warm_for "$it")
  if [ -f "$OUT/done/iter$it" ]; then echo "[it$it] already complete — skip (resume)"; COMPLETED=$((COMPLETED+1)); continue; fi
  [ -s "$PREV" ] || { echo "[it$it] FATAL: warm-from $PREV missing/empty" >&2; exit 1; }
  echo ""; echo "########## AZ_ZERO ITER $it -> iter_${nn} @ $(date) (warm from $(basename "$PREV")) ##########"

  # ---- gen ----
  GEN_T0=$(date +%s)
  if [ ! -f "$OUT/done/gen$it" ]; then
    echo "[it$it] gen -> $DATA @ $(date)"
    _kill_gen; sleep 2
    if [ "$USE_ORCH" = 1 ]; then
      REPO=$REPO_LOCAL HOST=5800x WARM="$PREV" ITER="$it" OUT="$OUT" \
        GAMES="$GAMES" SIMS="$SIMS" CPUCT="$CPUCT" FPU="$FPU" VALUE_TARGET="$VALUE_TARGET" \
        OW="$W_GEN" SEED_START="$SEED_BASE" \
        nice -n 19 bash "$GEN_ORCH" --leaf-eval nn > "$OUT/logs/gen_it${nn}.log" 2>&1
    else
      CUDA_VISIBLE_DEVICES="" nice -n 19 "$PY" -u "$GEN" \
        --checkpoint "$PREV" --iter "$it" --games "$GAMES" --sims "$SIMS" --c-puct "$CPUCT" --fpu "$FPU" \
        --value-target "$VALUE_TARGET" --leaf-eval nn --workers "$W_GEN" \
        --seed-start "$SEED_BASE" --output-root "$OUT" > "$OUT/logs/gen_it${nn}.log" 2>&1
    fi
    GEN_NPZ=$(ls "$DATA"/seed_*.npz 2>/dev/null | wc -l)
    if [ "$GEN_NPZ" -lt "$GAMES" ]; then
      echo "[it$it] GEN INCOMPLETE ($GEN_NPZ/$GAMES npz) — halting" >&2; tail -20 "$OUT/logs/gen_it${nn}.log" >&2; exit 1
    fi
    echo "[it$it] gen complete ($GEN_NPZ npz) @ $(date)"; date > "$OUT/done/gen$it"
  else
    echo "[it$it] gen — done, skip"; GEN_NPZ=$(ls "$DATA"/seed_*.npz 2>/dev/null | wc -l)
  fi
  GEN_SEC=$(( $(date +%s) - GEN_T0 ))

  # ---- train (LOCAL, GPU) ----
  if [ ! -f "$CKPT" ]; then
    echo "[it$it] train (window $WINDOW, warm $(basename "$PREV")) @ $(date)"
    CUDA_VISIBLE_DEVICES=$TRAIN_GPU nice -n 19 "$PY" -u "$TRAIN" \
      --output-root "$OUT" --iter "$it" --window "$WINDOW" --warm-from "$PREV" --output "$CKPT" \
      --epochs "$EPOCHS" --batch-size "$BATCH" --value-loss-weight "$VLW" --aux-weight "$AUX_WEIGHT" \
      --entropy-floor-frac "$ENTROPY_FLOOR" --stage-local "/tmp/az_zero_stage_${it}" \
      --prov-value-target "$VALUE_TARGET" --prov-selfplay-leaf nn_value_head --prov-run-tag "az_zero_it${it}" \
      > "$OUT/logs/train_it${nn}.log" 2>&1
    rm -rf "/tmp/az_zero_stage_${it}" 2>/dev/null || true
    [ -f "$CKPT" ] || { echo "[it$it] TRAIN FAILED — halting" >&2; tail -25 "$OUT/logs/train_it${nn}.log" >&2; exit 1; }
  else
    echo "[it$it] train — ckpt exists, skip"
  fi

  # ---- screen (every SCREEN_EVERY iters + final) ----
  if _screen_iter "$it"; then
    echo "[it$it] anchor screen (n=$SCREEN_N vs random + vs $(basename "$ANCHOR_CKPT")) @ $(date)"
    CUDA_VISIBLE_DEVICES="" nice -n 19 "$PY" -u "$SCREEN" --cand-ckpt "$CKPT" --opponent random \
      --n "$SCREEN_N" --sims "$SIMS" --c-puct "$CPUCT" --fpu "$FPU" --workers "$SCREEN_W" --device cpu \
      --out "$OUT/screens/iter_${nn}/vs_random" > "$OUT/logs/screen_random_it${nn}.log" 2>&1 \
      || echo "[it$it] WARN: vs-random screen failed (non-fatal)"
    if [ -f "$ANCHOR_CKPT" ]; then
      CUDA_VISIBLE_DEVICES="" nice -n 19 "$PY" -u "$SCREEN" --cand-ckpt "$CKPT" --opponent net --anchor-ckpt "$ANCHOR_CKPT" \
        --n "$SCREEN_N" --sims "$SIMS" --c-puct "$CPUCT" --fpu "$FPU" --workers "$SCREEN_W" --device cpu \
        --out "$OUT/screens/iter_${nn}/vs_warmstart" > "$OUT/logs/screen_warm_it${nn}.log" 2>&1 \
        || echo "[it$it] WARN: vs-warmstart screen failed (non-fatal)"
    fi
  fi

  date > "$OUT/done/iter$it"; COMPLETED=$((COMPLETED+1))
  echo "[it$it] ✅ iter complete (gen ${GEN_SEC}s) @ $(date)"
done

LAST=$(ls "$OUT"/ckpt/iter_*.pt 2>/dev/null | grep -v random | sort | tail -1)
echo ""; echo "=== az_zero DONE @ $(date) — completed $COMPLETED iter(s); latest: $LAST ==="
