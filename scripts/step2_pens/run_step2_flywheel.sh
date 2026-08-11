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
# Launch (detached, real run — arm B', 2-box, BENCHED W 2026-06-30):
#   TAG=step2_pens_armBprime VALUE_OBJECTIVE=ranking USE_LAPTOP=1 \
#   OW_LOCAL=24 OW_LAPTOP=12 EVAL_OW_LOCAL=40 EVAL_OW_LAPTOP=12 \
#   ARM=B nohup nice -n 19 bash scripts/step2_pens/run_step2_flywheel.sh \
#       > /tmp/step2_flywheel_Bprime.log 2>&1 & disown
#   (env seeds $OUT/run_config.env on FIRST launch; thereafter EDIT run_config.env
#    between stages to tune — no kill/restart needed. See the knob-surface block.)
#
# End-to-end firewall (1 iter, 8 games, sims 50, LOCAL-ONLY):
#   bash scripts/step2_pens/run_step2_flywheel.sh --smoke
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

# --- smoke flag (parse before anything else) ---
# Honor an inherited SMOKE=1 env var (the documented trigger) AND the --smoke arg.
SMOKE=${SMOKE:-0}
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
EVAL_ORCH=$REPO_LOCAL/scripts/step2_pens/eval_step2_orch.sh

# --- recipe (pilot defaults) ---
ITERS=${ITERS:-10}
GAMES=${GAMES:-600}
SIMS=${SIMS:-200}
EPOCHS_POLICY=${EPOCHS_POLICY:-3}
EPOCHS_VALUE=${EPOCHS_VALUE:-6}
BATCH=${BATCH:-256}
VLW=${VLW:-1.5}
CPUCT=3.0
EVAL_N=${EVAL_N:-200}      # verdict-grade screen (Joshua 2026-06-30; was 120)
SP_BASE=${SP_BASE:-570000000}
# EVAL through the 2-server carc-orch (eval_step2_orch.sh, ~2.4x+ over net-CPU);
# =0 falls back to net-on-CPU eval_step2.py. The eval is a NON-FATAL screen either
# way (chain continues on failure).
USE_ORCH_EVAL=${USE_ORCH_EVAL:-1}

# --- per-box GEN + EVAL worker counts (orch high-W). BENCHED 2026-06-30 on the
#     step2 ranking-objective path (sims=100 gen + --emit-ranking-groups; 2-server
#     orch eval) — these are the MEASURED optima, NOT the v29-residual figures.
#     GEN local: ranking emission (record_boards + per-root sibling extraction) is
#     CPU-heavy, so the throughput-optimal W is LOWER than the v29 gen-28 and well
#     under 42GB. GEN laptop: 11GB WSL RAM + 8GB GPU caps it. EVAL: heavy 89-feat
#     scalar value on 32/24 threads + TWO orch contexts on one GPU.
#     (feedback_worker_count_by_bottleneck — re-bench after any code-era change.) ---
OW_LOCAL=${OW_LOCAL:-24}        # gen, local 5900XT — BENCHED 2026-06-30: 24=5.91 g/min peak (20=4.91, 28=5.80, 36=2.91 craters); CPU-bound, RAM never binds (15.8GB@24)
OW_LAPTOP=${OW_LAPTOP:-12}      # gen, laptop — BENCHED: 12=4.38 g/min, 8.96GB peak / 4.94GB free (W16 risks OOM on 11GB WSL)
EVAL_OW_LOCAL=${EVAL_OW_LOCAL:-40}    # eval, local — BENCHED 2026-06-30: 40=8.70 g/min peak (28=7.16, 48=8.51); 21.5GB@40, scales higher than gen (orch keeps workers fed)
EVAL_OW_LAPTOP=${EVAL_OW_LAPTOP:-12}  # eval, laptop — BENCHED: 12=5.24 g/min, 7.64GB peak / 5.09GB free
USE_LAPTOP=${USE_LAPTOP:-1}     # 2-box work-stealing (gen AND eval) if --shared-claim + laptop reachable
LAPTOP_WARM_SECS=${LAPTOP_WARM_SECS:-45}  # claim-balance: warm the laptop's orch+workers this long BEFORE local starts claiming, so both race fairly (else local-warm+higher-W starves the laptop)

# --- in-loop VALUE objective: 'mse' (default = the cratering run, reproducible)
#     or 'ranking' (arm B': per-group ListNet over the in-loop sibling groups'
#     backed-up search-Q — the test that the warmstart's +43% was sibling-RANKING,
#     not outcome-MSE). When 'ranking': gen ALSO emits seed_*_rank.npz and the value
#     trainer consumes those listwise. EVERYTHING ELSE (blend/dropout schedule, sims,
#     games, eval, Path-A threading, POV fix) is IDENTICAL to the MSE run. ---
VALUE_OBJECTIVE=${VALUE_OBJECTIVE:-mse}

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

# ============================================================================
# LIVE-TUNABLE KNOB SURFACE — $OUT/run_config.env
# ----------------------------------------------------------------------------
# The recurring pain was config being env-baked at launch: changing one knob
# (e.g. a worker count, or a blend schedule entry) meant kill + restart the whole
# run. Fix: at launch we WRITE the tunable knobs to $OUT/run_config.env (seeded
# from the launch-time env on FIRST write; an existing run_config.env is NOT
# clobbered on resume). Every stage (gen / train-policy / train-value / eval) of
# every iter RE-SOURCES this file FRESH at its start (_load_run_config), so the
# value each stage uses is read live, not from the launch env. So you can edit
# $OUT/run_config.env between stages — or kill, edit, relaunch (the per-stage
# done-markers under $OUT/done make finished stages resume-skip) — and the NEXT
# stage picks up the change WITHOUT redoing finished work.
#
# *** $OUT/run_config.env IS THE LIVE KNOB SURFACE — edit it, don't edit this
#     script for a running flywheel. ***
# Knobs: OW_LOCAL OW_LAPTOP EVAL_OW_LOCAL EVAL_OW_LAPTOP USE_LAPTOP GAMES SIMS
#        EVAL_N VALUE_OBJECTIVE LAPTOP_WARM_SECS BLEND_SCHED[] DROPOUT_SCHED[].
# (ITERS/ARM/TAG/seed ckpts are launch-fixed structural choices — NOT re-sourced.)
# ============================================================================
RUN_CONFIG="$OUT/run_config.env"
_write_run_config_seed() {
  # First-write only: seed run_config.env from the launch-time env. Never clobber
  # an existing one (resume / between-stage edits must survive).
  [ -f "$RUN_CONFIG" ] && { echo "  run_config.env exists — NOT clobbered (live-tunable; resume)"; return; }
  {
    echo "# Step-2 flywheel LIVE-TUNABLE knobs (re-sourced at the start of every stage)."
    echo "# Edit between stages (or kill->edit->relaunch); finished stages resume-skip via \$OUT/done."
    echo "# Seeded from the launch env @ $(date -u +%Y-%m-%dT%H:%M:%SZ). TAG=$TAG ARM=$ARM."
    echo "OW_LOCAL=$OW_LOCAL"
    echo "OW_LAPTOP=$OW_LAPTOP"
    echo "EVAL_OW_LOCAL=$EVAL_OW_LOCAL"
    echo "EVAL_OW_LAPTOP=$EVAL_OW_LAPTOP"
    echo "USE_LAPTOP=$USE_LAPTOP"
    echo "LAPTOP_WARM_SECS=$LAPTOP_WARM_SECS"
    echo "GAMES=$GAMES"
    echo "SIMS=$SIMS"
    echo "EVAL_N=$EVAL_N"
    echo "VALUE_OBJECTIVE=$VALUE_OBJECTIVE"
    echo "EPOCHS_POLICY=$EPOCHS_POLICY"
    echo "EPOCHS_VALUE=$EPOCHS_VALUE"
    echo "BATCH=$BATCH"
    echo "VLW=$VLW"
    # Schedules as bash array literals so re-source restores them verbatim.
    printf 'BLEND_SCHED=('; printf '%s ' "${BLEND_SCHED[@]}"; printf ')\n'
    printf 'DROPOUT_SCHED=('; printf '%s ' "${DROPOUT_SCHED[@]}"; printf ')\n'
  } > "$RUN_CONFIG"
  echo "  wrote live-tunable knob surface -> $RUN_CONFIG"
}
_load_run_config() {
  # Re-source the live knob surface at the start of a stage so edits between
  # stages take effect. Sourced in the CURRENT shell (updates OW_LOCAL etc.).
  [ -f "$RUN_CONFIG" ] || return 0
  # shellcheck disable=SC1090
  source "$RUN_CONFIG"
}
_write_run_config_seed

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
- In-loop VALUE objective: $VALUE_OBJECTIVE ($([ "$VALUE_OBJECTIVE" = frozen ] && echo "FROZEN: value pinned to warmstart for all iters, value-train SKIPPED — the retrain-vs-object tiebreak" || { [ "$VALUE_OBJECTIVE" = ranking ] && echo "arm B': per-group ListNet over in-loop backed-up search-Q" || echo "outcome-MSE on score_diff_wide — the cratering run"; })).
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
  if ! _gen_supports_claim; then
    echo "  NOTE: gen_step2.py has NO --shared-claim — running LOCAL-ONLY gen"
  # FAST liveness probe FIRST (ConnectTimeout 10) so a DOWN/flaky laptop costs ~10s,
  # not the 60s sync timeout. The laptop's :2222 flaps when the WSL VM isn't held
  # (reference_laptop_cluster_access) — a clean local-only fallback is mandatory.
  elif ! timeout 15 ssh -o ConnectTimeout=10 "$LAPTOP_SSH" true </dev/null >/dev/null 2>&1; then
    echo "  WARN: laptop ($LAPTOP_SSH) UNREACHABLE (probe failed) — LOCAL-ONLY gen"
  # git-bundle sync (offline_git_bundle_sync: remotes can't reach github; sync via
  # a bundle on the CIFS share + fetch/reset on the laptop). REQUIRED before any
  # 2-box run after local commits, else stale-code contamination.
  elif ! git bundle create "$SHARE_LOCAL/code_sync/carc_${BRANCH}.bundle" "$BRANCH" >/dev/null 2>&1; then
    echo "  WARN: bundle create FAILED — LOCAL-ONLY gen"
  elif timeout 60 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
        "git -C $REPO_LAPTOP fetch $SHARE_REMOTE/code_sync/carc_${BRANCH}.bundle $BRANCH && git -C $REPO_LAPTOP reset --hard FETCH_HEAD" \
        </dev/null >/dev/null 2>&1; then
    LAPTOP_OK=1
    echo "  bundle tip: $(git rev-parse --short "$BRANCH") — laptop synced; 2-box work-stealing (gen+eval) ENABLED"
  else
    echo "  WARN: laptop sync FAILED — LOCAL-ONLY gen"
  fi
fi

# Stage the SEED scalar onto the share so the laptop can read it for iter-1 gen.
# (The seed scalar lives in local $HOME — /home/doctor/carc_step2_pens/warmstart/
# warmstart.pt — NOT under the share, so the path-rewrite in _gen_launch_laptop
# can't reach it. From iter 2+ the scalar is $OUT/ckpt_scalar/*.pt — already on the
# share. Copy once so the laptop's iter-1 gen finds it.) Result ckpts (policy +
# scalar) the eval reads also live under $OUT (share) — no extra staging there.
SEED_SCALAR_SHARE="$OUT/ckpt_scalar/seed_scalar.pt"
if [ "$LAPTOP_OK" = 1 ]; then
  if [ ! -s "$SEED_SCALAR_SHARE" ] || [ "$SEED_SCALAR" -nt "$SEED_SCALAR_SHARE" ]; then
    cp -f "$SEED_SCALAR" "$SEED_SCALAR_SHARE" 2>/dev/null \
      && echo "  staged seed scalar -> $SEED_SCALAR_SHARE (laptop iter-1 gen)" \
      || echo "  WARN: could not stage seed scalar to share — laptop iter-1 gen may fail to find it"
  fi
fi
echo "    cluster mode: $([ "$LAPTOP_OK" = 1 ] && echo "2-box (gen: local W$OW_LOCAL + laptop W$OW_LAPTOP; eval: local W$EVAL_OW_LOCAL + laptop W$EVAL_OW_LAPTOP; work-stealing)" || echo "LOCAL-ONLY (gen W$OW_LOCAL / eval W$EVAL_OW_LOCAL)")"

_status "RUNNING" "Starting iter 1 (arm $ARM). No iteration completed yet."

# Launch one box's gen (orch high-W). $1=iter $2=seed_start $3=policy_ckpt $4=scalar_ckpt $5=blend $6=dropout $7=outdir
_gen_launch_local() {
  local it="$1" seed="$2" pol="$3" sca="$4" bl="$5" dr="$6" od="$7"
  # GEN through the carc-orch SHM GPU orchestrator: gen_step2_orch.sh TorchScript-
  # exports the policy net (parity-gated), starts ONE carc-orch SHM server for the
  # priors (the 85%-of-per-leaf-cost policy forward, GPU-batched), runs gen_step2
  # --shm-eval-server, and trap-cleans the server. The scalar-MLP VALUE is computed
  # in-worker on CPU (cheap). CKPT/SCALAR/OW/SIMS go via env; the rest via "$@".
  local rank_flag=""
  [ "$VALUE_OBJECTIVE" = "ranking" ] && rank_flag="--emit-ranking-groups"
  # In 2-box mode the local arm MUST also claim (else it double-plays the seeds the
  # laptop is producing). Same $GAMES range, same OUT, distinct claim-host -> atomic
  # work-stealing. LOCAL-ONLY (LAPTOP_OK=0) keeps the lean non-claim Pool path.
  local claim_flag=""
  [ "$LAPTOP_OK" = 1 ] && claim_flag="--shared-claim --claim-host 5800x"
  CKPT="$pol" SCALAR="$sca" OW="$OW_LOCAL" SIMS="$SIMS" HOST=5800x \
    nice -n 19 bash "$REPO_LOCAL/scripts/step2_pens/gen_step2_orch.sh" \
    --games "$GAMES" --blend "$bl" --dropout "$dr" --iter "$it" --out "$od" \
    --value-target score_diff_wide $rank_flag $claim_flag \
    > "$OUT/logs/gen_local_it${it}.log" 2>&1
}
_gen_launch_laptop() {
  local it="$1" seed="$2" pol="$3" sca="$4" bl="$5" dr="$6" od="$7"
  # Rewrite local-share paths to the laptop's share mount (local /mnt/c/carc-shared
  # -> laptop /mnt/carc-shared). The ckpts + OUT live on the share so the laptop
  # reads the SAME warm policy/scalar and writes its .npz into the SAME OUT/iter
  # dir the local box is claiming against (one shared dir, atomic .claim arbitration).
  local polr=${pol/$SHARE_LOCAL/$SHARE_REMOTE} odr=${od/$SHARE_LOCAL/$SHARE_REMOTE}
  # Resolve the scalar to a SHARE-visible path for the laptop: if it's already
  # under the share, rewrite the mount; else it's the local-$HOME seed scalar (not
  # on the share) -> use the staged share copy ($OUT/ckpt_scalar/seed_scalar.pt).
  local scar
  if [ "${sca#"$SHARE_LOCAL"}" != "$sca" ]; then
    scar=${sca/$SHARE_LOCAL/$SHARE_REMOTE}
  else
    scar=${SEED_SCALAR_SHARE/$SHARE_LOCAL/$SHARE_REMOTE}
  fi
  local rank_flag=""
  [ "$VALUE_OBJECTIVE" = "ranking" ] && rank_flag="--emit-ranking-groups"
  # The laptop runs its OWN carc-orch on its GPU via gen_step2_orch.sh (net-on-CPU
  # was the ~145s/game blocker). gen_step2_orch.sh self-cd's to its REPO ($(dirname
  # "$0")/../..) so the absolute-path invocation is path-stable (no inline `cd` —
  # the SSH cd-strip rule). CKPT/SCALAR/OW/SIMS go via env (in front of the remote
  # command); the gen flags (incl --shared-claim --claim-host laptop) ride "$@" of
  # the orch script straight into gen_step2.py. setsid + </dev/null detaches so a
  # dropped ssh (Mac sleep / WSL teardown) doesn't SIGHUP-kill it. We BACKGROUND the
  # ssh call itself (in the caller) so a hung/flaky laptop never starves local; a
  # timeout-124 here means LAUNCHED (feedback_wsl_ssh_launch_pkill_traps) — never retry.
  timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
    "setsid env CKPT=$polr SCALAR=$scar OW=$OW_LAPTOP SIMS=$SIMS HOST=laptop nice -n 19 bash $REPO_LAPTOP/scripts/step2_pens/gen_step2_orch.sh --games $GAMES --blend $bl --dropout $dr --iter $it --out $odr --value-target score_diff_wide $rank_flag --shared-claim --claim-host laptop > /tmp/step2_gen_laptop_it${it}.log 2>&1 </dev/null &" \
    </dev/null >/dev/null 2>&1 || true
}

# Launch the laptop's EVAL (its OWN cand+ref carc-orch servers via eval_step2_orch.sh,
# --shared-claim --claim-host laptop, writing per-game JSON into the SAME shared eval
# OUT the local box claims against). $1=cand_ckpt $2=ref_ckpt $3=scalar_ckpt $4=blend
# $5=dropout $6=n $7=sims $8=seed_start $9=eval_out_dir
_eval_launch_laptop() {
  local cand="$1" ref="$2" sca="$3" bl="$4" dr="$5" n="$6" sims="$7" ss="$8" od="$9"
  # Rewrite share-local paths to the laptop's share mount. Cand/ref/scalar all live
  # under $OUT or the RoD2 share dir (both under $SHARE_LOCAL) — rewrite reaches them.
  local candr=${cand/$SHARE_LOCAL/$SHARE_REMOTE} refr=${ref/$SHARE_LOCAL/$SHARE_REMOTE}
  local odr=${od/$SHARE_LOCAL/$SHARE_REMOTE}
  local scar
  if [ "${sca#"$SHARE_LOCAL"}" != "$sca" ]; then
    scar=${sca/$SHARE_LOCAL/$SHARE_REMOTE}
  else
    scar=${SEED_SCALAR_SHARE/$SHARE_LOCAL/$SHARE_REMOTE}
  fi
  # eval_step2_orch.sh self-cd's to its REPO; absolute-path invocation is path-stable
  # (SSH cd-strip rule). Contract via env in front of the remote command; the eval
  # flags (incl --shared-claim --claim-host laptop) ride "$@" of the orch script into
  # eval_step2.py. setsid + </dev/null detaches (Mac-sleep/WSL-teardown SIGHUP-safe).
  # The CALLER backgrounds this ssh so a hung laptop never starves local; a timeout-124
  # means LAUNCHED (feedback_wsl_ssh_launch_pkill_traps) — never retry. The laptop runs
  # the SAME n/seed-start range against the SAME shared eval OUT -> whole-deck claim
  # arbitration load-balances the deck pool (pairing per-deck -> paired-z unchanged).
  timeout 45 ssh -o ConnectTimeout=20 "$LAPTOP_SSH" \
    "setsid env CAND_CKPT=$candr REF_CKPT=$refr SCALAR=$scar OW=$EVAL_OW_LAPTOP SIMS=$sims N=$n BLEND=$bl DROPOUT=$dr SEED_START=$ss OUT=$odr HOST=laptop nice -n 19 bash $REPO_LAPTOP/scripts/step2_pens/eval_step2_orch.sh --shared-claim --claim-host laptop > /tmp/step2_eval_laptop.log 2>&1 </dev/null &" \
    </dev/null >/dev/null 2>&1 || true
}

COMPLETED=0
for it in $(seq 1 "$ITERS"); do
  if [ -f "$OUT/done/iter$it" ]; then echo "[it$it] already complete — skip"; COMPLETED=$((COMPLETED+1)); continue; fi

  # Re-source the live knob surface at the TOP of the iter (covers the gen stage +
  # the per-iter blend/dropout/seed derivation below). Each subsequent stage
  # re-sources again so a between-stage edit is picked up.
  _load_run_config
  BLEND=${BLEND_SCHED[$((it-1))]}
  DROPOUT=${DROPOUT_SCHED[$((it-1))]}
  if [ "$it" -eq 1 ]; then
    PREV_POLICY=$SEED_POLICY; PREV_SCALAR=$SEED_SCALAR
  else
    pp=$(printf "%02d" $((it-1)))
    PREV_POLICY=$OUT/ckpt_policy/iter_${pp}.pt
    PREV_SCALAR=$OUT/ckpt_scalar/iter_${pp}.pt
  fi
  # FROZEN-value mode (VALUE_OBJECTIVE=frozen): the scalar is NEVER retrained, so
  # gen AND eval ALWAYS use the warmstart SEED_SCALAR for the value — never a
  # per-iter iter_N scalar. Pin PREV_SCALAR (gen's value) to the seed regardless
  # of iter so the wean blends the FROZEN warmstart value in. (mse/ranking: prev
  # scalar is the prior iter's retrained ckpt, unchanged.)
  [ "$VALUE_OBJECTIVE" = "frozen" ] && PREV_SCALAR=$SEED_SCALAR
  [ -s "$PREV_POLICY" ] || { echo "[it$it] FATAL: prev policy $PREV_POLICY missing" >&2; _status "ERROR" "iter $it: prev policy missing."; exit 1; }
  [ -s "$PREV_SCALAR" ] || { echo "[it$it] FATAL: prev scalar $PREV_SCALAR missing" >&2; _status "ERROR" "iter $it: prev scalar missing."; exit 1; }
  cc=$(printf "%02d" "$it")
  POLICY_CKPT=$OUT/ckpt_policy/iter_${cc}.pt
  # FROZEN: the eval's scalar is the warmstart seed (no per-iter scalar exists).
  # mse/ranking: the candidate scalar is this iter's freshly-trained ckpt.
  if [ "$VALUE_OBJECTIVE" = "frozen" ]; then
    SCALAR_CKPT=$SEED_SCALAR
  else
    SCALAR_CKPT=$OUT/ckpt_scalar/iter_${cc}.pt
  fi
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
    # 2-box work-stealing with CLAIM-BALANCE (warm-laptop-first): BACKGROUND the
    # laptop ssh launch FIRST (so a hung/flaky laptop can't starve the local arm —
    # feedback_background_remote_launches_in_loop), then WARM-WAIT LAPTOP_WARM_SECS
    # so the laptop's orch + workers are up and CLAIMING before the local box (warm
    # + higher-W) starts — else local wins every early claim race and the laptop is
    # starved to ~0 (the bug this rework fixes). Then run the local arm in the
    # FOREGROUND. Both --shared-claim against the SAME OUT/iter_00; each seed goes to
    # whichever box claims it first (no double-play). The local arm's exit gates the
    # iter — it NEVER blocks on the laptop. Dynamic load-balancing is preserved (both
    # race the shared pool); the warm-wait only removes local's cold-start head start.
    if [ "$LAPTOP_OK" = 1 ]; then
      _gen_launch_laptop "$it" "$SP_SEED" "$PREV_POLICY" "$PREV_SCALAR" "$BLEND" "$DROPOUT" "$DATA/iter_00" &
      echo "[it$it] gen: laptop launched (W$OW_LAPTOP) — warming ${LAPTOP_WARM_SECS}s before local starts claiming"
      sleep "$LAPTOP_WARM_SECS"   # allow-sleep (claim-balance warm-wait; bounded, deliberate)
    fi
    _gen_launch_local "$it" "$SP_SEED" "$PREV_POLICY" "$PREV_SCALAR" "$BLEND" "$DROPOUT" "$DATA/iter_00"
    GEN_RC=$?
    # In 2-box mode the local pool can DRAIN (all seeds claimed) while the laptop is
    # still finishing its claimed games. BOUNDED drain-wait so those contributions
    # land before we kill (else .claim-without-.npz strands -> fewer than GAMES; the
    # orphan-stall). Hard cap (GEN_DRAIN_CAP, default 20 min) so a dead/slow laptop
    # can NOT stall the iter — local is authoritative. Poll the npz count; stop early
    # once it reaches GAMES or plateaus for GEN_DRAIN_IDLE consecutive polls.
    if [ "$LAPTOP_OK" = 1 ]; then
      GEN_DRAIN_CAP=${GEN_DRAIN_CAP:-1200}; GEN_DRAIN_IDLE=${GEN_DRAIN_IDLE:-6}
      _drain_t0=$(date +%s); _last_npz=-1; _idle=0
      while :; do
        # count GAME npz only (exclude _pens/_rank companions, which also match seed_*.npz).
        _n=$(ls "$DATA"/iter_00/seed_*.npz 2>/dev/null | grep -cvE '_pens\.npz$|_rank\.npz$')
        [ "$_n" -ge "$GAMES" ] && { echo "[it$it] 2-box drain: $_n/$GAMES game npz — full"; break; }
        if [ "$_n" -le "$_last_npz" ]; then _idle=$((_idle+1)); else _idle=0; _last_npz=$_n; fi
        [ "$_idle" -ge "$GEN_DRAIN_IDLE" ] && { echo "[it$it] 2-box drain: plateaued at $_n/$GAMES npz (laptop idle/done)"; break; }
        [ $(( $(date +%s) - _drain_t0 )) -ge "$GEN_DRAIN_CAP" ] && { echo "[it$it] 2-box drain: hit ${GEN_DRAIN_CAP}s cap at $_n/$GAMES npz — proceeding (local authoritative)"; break; }
        sleep 5
      done
    fi
    _kill_gen; sleep 1
    GEN_NPZ=$(ls "$DATA"/iter_00/seed_*.npz 2>/dev/null | grep -cvE '_pens\.npz$|_rank\.npz$')
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
  # Same for the RANKING companions (arm B', VALUE_OBJECTIVE=ranking): the
  # seed_*_rank.npz hold the per-root sibling groups (89-vec + backed-up search-Q +
  # group_id) the listwise value trainer consumes. Separate them out of iter_00 too
  # (train_iter globs iter_00 for the GameDataset schema and would KeyError on them).
  if [ "$VALUE_OBJECTIVE" = "ranking" ]; then
    mkdir -p "$DATA/iter_00_rank"
    mv "$DATA"/iter_00/*_rank.npz "$DATA/iter_00_rank/" 2>/dev/null || true
  fi
  GEN_SEC=$(( $(date +%s) - GEN_T0 ))

  # ---- 2. TRAIN POLICY (train_iter.py, v2.9 leaf env) ----
  _load_run_config   # re-source live knobs (VLW/BATCH/EPOCHS_POLICY) at stage start
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
  # FROZEN mode: the value is FIXED at the warmstart for every iter, so this stage
  # is SKIPPED entirely — no train_value_iter call, no per-iter scalar ckpt produced
  # or required. SCALAR_CKPT already == SEED_SCALAR (set above) so gen/eval use the
  # frozen value; resume is unaffected because the per-iter done-marker is iter$it,
  # not a scalar ckpt. (mse/ranking: trains as before.)
  _load_run_config   # re-source live knobs (EPOCHS_VALUE/VALUE_OBJECTIVE) at stage start
  _status "RUNNING" "iter $it — policy done. Stage: train-value. Completed: $COMPLETED."
  TRV_T0=$(date +%s)
  if [ "$VALUE_OBJECTIVE" = "frozen" ]; then
    echo "[it$it] train VALUE — SKIPPED (VALUE_OBJECTIVE=frozen; value pinned to warmstart $(basename "$SEED_SCALAR"))"
  elif [ ! -f "$SCALAR_CKPT" ]; then
    echo "[it$it] train VALUE (scalar MLP, objective=$VALUE_OBJECTIVE) @ $(date)"
    # MSE (default): consume the per-ply 89-vec + score_diff_wide from iter_00_pens.
    # RANKING (arm B'): consume the per-root sibling groups from iter_00_rank,
    # listwise over backed-up search-Q (--objective ranking).
    if [ "$VALUE_OBJECTIVE" = "ranking" ]; then
      VAL_GEN_DIR="$DATA/iter_00_rank"; VAL_OBJ_FLAG="--objective ranking"
    else
      VAL_GEN_DIR="$DATA/iter_00_pens"; VAL_OBJ_FLAG="--objective mse"
    fi
    nice -n 19 "$PY" -u "$TRAIN_VALUE" \
      --gen-dir "$VAL_GEN_DIR" $VAL_OBJ_FLAG --warm-from "$PREV_SCALAR" --out "$SCALAR_CKPT" --epochs "$EPOCHS_VALUE" \
      > "$OUT/logs/train_value_it${it}.log" 2>&1
    [ -s "$SCALAR_CKPT" ] || { echo "[it$it] VALUE TRAIN FAILED — halting" >&2; tail -20 "$OUT/logs/train_value_it${it}.log" >&2; _status "ERROR" "iter $it value train FAILED (likely the gen-npz seam — check --feat-field)."; exit 1; }
  else
    echo "[it$it] train VALUE — exists, skip"
  fi
  TRV_SEC=$(( $(date +%s) - TRV_T0 ))

  # ---- 4. EVAL (eval_step2.py — paired screen vs RoD2 iter_02) ----
  # Applies EVAL_OW_LOCAL/EVAL_OW_LAPTOP + the 2-box laptop eval + claim-balance
  # from iter 1 onward (no iter-1 special-case). Re-source the live knobs first.
  _load_run_config
  _status "RUNNING" "iter $it — value done. Stage: eval. Completed: $COMPLETED."
  EV_T0=$(date +%s)
  EV_SEED_START=$(( 5715000000 + it*1000000 ))
  EVAL_OUT="$OUT/eval/iter_${cc}"
  if [ "$USE_ORCH_EVAL" = 1 ]; then
    echo "[it$it] eval (ORCH 2-server screen) blend=$BLEND vs RoD2 iter_02, paired n=$EVAL_N @ sims=$SIMS @ $(date)"
    # eval_step2_orch.sh: 2 carc-orch SHM servers (cand + ref) batch BOTH policy
    # forwards on the one local GPU (~2.4x+ over net-CPU). Contract via env;
    # SEED_START keeps per-iter seed separation (the orch script forwards it).
    # _kill_gen first so any prior carc-orch on this box is gone (the eval starts
    # its OWN servers with host-scoped shm-names).
    _kill_gen; sleep 1
    # 2-box eval with CLAIM-BALANCE (warm-laptop-first), mirroring gen: WARM-LAUNCH
    # the laptop's eval (its own cand+ref orch servers, --shared-claim --claim-host
    # laptop, into the SAME shared EVAL_OUT) FIRST, warm-wait, then run the local
    # eval (--shared-claim --claim-host 5800x). Whole-deck claim arbitration splits
    # the n paired decks across boxes; paired-z is per-deck so it's statistically
    # unchanged. LOCAL-ONLY keeps the lean non-claim path. The laptop ssh is
    # backgrounded so a hung laptop never starves local; local's exit + drain gates.
    local_claim=""   # plain var (not 'local' — we're in the main loop, not a function)
    if [ "$LAPTOP_OK" = 1 ]; then
      local_claim="--shared-claim --claim-host 5800x"
      _eval_launch_laptop "$POLICY_CKPT" "$REF_CKPT" "$SCALAR_CKPT" "$BLEND" "$DROPOUT" \
        "$EVAL_N" "$SIMS" "$EV_SEED_START" "$EVAL_OUT" &
      echo "[it$it] eval: laptop launched (W$EVAL_OW_LAPTOP) — warming ${LAPTOP_WARM_SECS}s before local starts claiming"
      sleep "$LAPTOP_WARM_SECS"   # allow-sleep (claim-balance warm-wait; bounded, deliberate)
    fi
    # shellcheck disable=SC2086
    CAND_CKPT="$POLICY_CKPT" REF_CKPT="$REF_CKPT" SCALAR="$SCALAR_CKPT" \
      OW="$EVAL_OW_LOCAL" SIMS="$SIMS" N="$EVAL_N" BLEND="$BLEND" DROPOUT="$DROPOUT" \
      SEED_START="$EV_SEED_START" OUT="$EVAL_OUT" HOST=5800x \
      nice -n 19 bash "$EVAL_ORCH" $local_claim \
      > "$OUT/logs/eval_it${it}.log" 2>&1
    EV_RC=$?
    # 2-box drain: the local eval pool can drain (all decks claimed) while the laptop
    # is still finishing its claimed decks. BOUNDED drain-wait so those land (else a
    # half-played deck strands and n drops). Hard cap so a dead/slow laptop can't
    # stall — local is authoritative. Poll the result-JSON count; stop at EVAL_N (one
    # JSON per paired work-unit: _build_work makes EVAL_N units = EVAL_N//2 decks x 2
    # seats, so the on-disk JSON target is EVAL_N, NOT 2*EVAL_N) or on plateau.
    if [ "$LAPTOP_OK" = 1 ]; then
      EVAL_DRAIN_CAP=${EVAL_DRAIN_CAP:-900}; EVAL_DRAIN_IDLE=${EVAL_DRAIN_IDLE:-6}
      _need="$EVAL_N"; _dt0=$(date +%s); _last=-1; _idle=0
      while :; do
        _nj=$(ls "$EVAL_OUT"/seed*_a*.json 2>/dev/null | wc -l)
        [ "$_nj" -ge "$_need" ] && { echo "[it$it] eval drain: $_nj/$_need result-json — full"; break; }
        if [ "$_nj" -le "$_last" ]; then _idle=$((_idle+1)); else _idle=0; _last=$_nj; fi
        [ "$_idle" -ge "$EVAL_DRAIN_IDLE" ] && { echo "[it$it] eval drain: plateaued at $_nj/$_need (laptop idle/done)"; break; }
        [ $(( $(date +%s) - _dt0 )) -ge "$EVAL_DRAIN_CAP" ] && { echo "[it$it] eval drain: hit ${EVAL_DRAIN_CAP}s cap at $_nj/$_need — proceeding (local authoritative)"; break; }
        sleep 5
      done
      # Post-drain RE-SUMMARIZE over ALL result JSONs now on disk (local + laptop)
      # via eval_step2 --summarize-only — NO play, NO orch relaunch (cheap; just
      # gathers the per-game JSONs and rewrites summary.json so the laptop's claimed
      # decks land in the paired-z). The first local client already wrote a summary
      # over its own decks; this folds the laptop's in.
      nice -n 19 "$PY" -u "$EVAL" \
        --ckpt "$POLICY_CKPT" --scalar-ckpt "$SCALAR_CKPT" --ref-ckpt "$REF_CKPT" \
        --blend "$BLEND" --dropout "$DROPOUT" --n "$EVAL_N" --sims "$SIMS" \
        --out "$EVAL_OUT" --seed-start "$EV_SEED_START" --summarize-only \
        >> "$OUT/logs/eval_it${it}.log" 2>&1 || true
    fi
    _kill_gen; sleep 1
  else
    echo "[it$it] eval (net-CPU screen) blend=$BLEND vs RoD2 iter_02, paired n=$EVAL_N @ sims=$SIMS @ $(date)"
    nice -n 19 "$PY" -u "$EVAL" \
      --ckpt "$POLICY_CKPT" --scalar-ckpt "$SCALAR_CKPT" --ref-ckpt "$REF_CKPT" \
      --blend "$BLEND" --dropout "$DROPOUT" --n "$EVAL_N" --sims "$SIMS" \
      --workers "$EVAL_OW_LOCAL" --out "$EVAL_OUT" \
      --seed-start "$EV_SEED_START" \
      > "$OUT/logs/eval_it${it}.log" 2>&1
    EV_RC=$?
  fi
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

  # Gate the done-marker on a real eval result. A MISSING summary.json means eval
  # produced ZERO games (orch crash / export-parity FATAL / etc.) — do NOT fabricate
  # a "complete" iter with no measurement: that silently SKIPS the iter on resume AND
  # loses the data point the experiment exists for. HALT loudly instead. A summary
  # that DOES exist (even with rc!=0 / partial games) is the by-design non-fatal
  # screen → proceed. (review BUG-2 — this is the frozen-iter2 0/200 fabrication.)
  if [ ! -f "$OUT/eval/iter_${cc}/summary.json" ]; then
    echo "[it$it] FATAL: eval produced NO summary.json (rc=$EV_RC, 0 results) — NOT marking iter done; halting so the eval failure is noticed (likely orch / export-parity). Fix + resume." >&2
    _status "ERROR" "iter $it: eval produced 0 results (no summary.json). Halted — fix the eval and resume."
    exit 1
  fi
  date > "$OUT/done/iter$it"; COMPLETED=$((COMPLETED+1))
  echo "[it$it] ✅ iter complete @ $(date) — gen ${GEN_SEC}s / pol ${TRP_SEC}s / val ${TRV_SEC}s / eval ${EV_SEC}s"
  _status "RUNNING" "Last completed: iter $it (blend $BLEND). Total: $COMPLETED. Next: iter $((it+1))."
done

echo ""; echo "=== STEP-2 PeNS FLYWHEEL (arm $ARM) DONE @ $(date) — completed $COMPLETED iters ==="
_status "DONE" "Run finished. Completed $COMPLETED iteration(s). Policy ckpts under \`$OUT/ckpt_policy\`, scalar ckpts under \`$OUT/ckpt_scalar\`, per-iter screens under \`$OUT/eval\`. Next: the lean-in-loop derivative read (arm B slope) + a powered h6400_v2.9 verdict on the surviving checkpoint — separate explicit step."
