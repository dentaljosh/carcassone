#!/usr/bin/env bash
# 4-LEVER value-loss sequencer (2026-06-05). After STEP B.1's ranking-loss sweep
# helped but missed the marginal≥0 gate, run the remaining levers SEQUENTIALLY +
# automatically, each judged by the MARGINAL (knob>0 elo − knob=0 elo):
#
#   Lever 1 (residual): gen residual-target self-play → train (plain MSE on
#       Δ=search-Q−v2.7) → scale-curve eval (CARCASSONNE_V25_RESIDUAL_SCALE).
#       The leaf = clip(v2.7 + scale·Δ) inherits v2.7's sibling-ranking BY
#       CONSTRUCTION, so its marginal can't crater the way pure-NN-leaf does.
#   Lever 2 (centered): NO gen — retrain on the existing rank_data (group_id) with
#       the per-node-centered MSE (--center-weight) → λ-curve eval.
#
# Then lever_summary.py reports both marginals + the gate verdict and writes
# VERDICT.txt (WINNER=l1|l2|none). On a confident winner → print (or, with
# FLYWHEEL_ON_WIN=1, launch) the Lever 3 flywheel; else flag the Lever 4 branch.
#
# Self-contained, single-box, RESUMABLE (per-stage .done markers; eval self-caches
# per game). Mirrors rank_sweep.sh's robustness — no cross-box coordination, so it
# survives a box hiccup by re-running (it resumes from the last incomplete stage).
# Launch detached: nohup nice -n 19 bash scripts/lever_sequencer.sh > /tmp/lever_seq.log 2>&1 & disown
#
# Env (all optional unless noted):
#   SHARE   per-box share mount (REQUIRED; 5800x /mnt/c/carc-shared)
#   REPO    repo path (default /home/doctor/projects/carcassone)
#   WORKERS gen/train/eval worker count (default 14)
#   N       eval games per knob (default 200)
#   GEN_GAMES residual-gen self-play games (default 300)
#   SIMS    MCTS sims for gen + eval (default 200)
#   WARM    warm-from + gen priors checkpoint (default $SHARE/stage_b/ckpt/iter_01.pt)
#   RANK_DATA  lever-2 dataset run dir under SHARE (default rank_data)
#   BETA    lever-2 --center-weight (default 1.0)
#   LEVERS  which to run, space-sep (default "1 2")
#   L1_SCALES residual scale-curve knobs (default "0 0.25 0.5")
#   L2_LAMBDAS centered λ-curve knobs (default "0 0.5 1.0")
#   FLYWHEEL_ON_WIN  1 → auto-launch the flywheel on a confident winner (default 0)
#   OUT     output dir (default $SHARE/lever_seq)
set -uo pipefail

SHARE="${SHARE:?set SHARE}"
REPO="${REPO:-/home/doctor/projects/carcassone}"
WORKERS="${WORKERS:-14}"
N="${N:-200}"
GEN_GAMES="${GEN_GAMES:-300}"
SIMS="${SIMS:-200}"
WARM="${WARM:-$SHARE/stage_b/ckpt/iter_01.pt}"
RANK_DATA="${RANK_DATA:-rank_data}"
BETA="${BETA:-1.0}"
LEVERS="${LEVERS:-1 2}"
L1_SCALES="${L1_SCALES:-0 0.25 0.5}"
L2_LAMBDAS="${L2_LAMBDAS:-0 0.5 1.0}"
FLYWHEEL_ON_WIN="${FLYWHEEL_ON_WIN:-0}"
OUT="${OUT:-$SHARE/lever_seq}"
PY="$REPO/.venv/bin/python"
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"
WARMSTART_ROOT="$REPO/data/warmstart/heuristic_tau05"

mkdir -p "$OUT/ckpt" "$OUT/done"
cd "$REPO" || { echo "FATAL: cannot cd $REPO" >&2; exit 1; }
[ -f "$WARM" ] || { echo "FATAL: WARM checkpoint missing: $WARM" >&2; exit 1; }
echo "=== lever_sequencer on $(hostname) @ $(date): LEVERS=[$LEVERS] N=$N GEN_GAMES=$GEN_GAMES WORKERS=$WORKERS ==="
echo "    WARM=$WARM  RANK_DATA=$SHARE/$RANK_DATA  OUT=$OUT"

knob_tag() { echo "$1" | sed 's/\.//; s/^0$/0/'; }  # 0->0 0.25->025 0.5->05 1.0->10

# eval one checkpoint at one leaf knob (env var name + value) into a subdir.
# $1=ckpt $2=knob_env_name $3=knob_value $4=out_subdir
run_eval() {
  local ckpt="$1" env_name="$2" knob="$3" sub="$4"
  echo "  [eval] $sub  ($env_name=$knob)  @ $(date)"
  nice -n 19 env $ENVV "$env_name=$knob" $PY -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$ckpt" --n "$N" --sims "$SIMS" --heur-sims "$SIMS" --c-puct 3.0 \
    --workers "$WORKERS" --out-root "$OUT" --out-subdir "$sub" \
    --seed-start 700000 --paired
  return $?
}

############################## LEVER 1 — residual ##############################
if echo " $LEVERS " | grep -q " 1 "; then
  echo ""; echo "########## LEVER 1 (predict-v2.7 + residual) @ $(date) ##########"
  GENDIR="$OUT/residual_data"
  RESID_CKPT="$OUT/ckpt/residual.pt"

  # --- gen (residual targets) ---
  if [ -f "$OUT/done/l1_gen" ]; then
    echo "[L1] gen — done, skip"
  else
    echo "[L1] gen $GEN_GAMES residual-target games @ $(date)"
    nice -n 19 env $ENVV $PY -u scripts/run_selfplay_iter.py \
      --iter 0 --games "$GEN_GAMES" --sims "$SIMS" --leaf-eval v2_5 --value-blend 0 \
      --value-target residual --workers "$WORKERS" --batch-size 8 \
      --checkpoint "$WARM" --anchor-fraction 0 \
      --output-root "$GENDIR" --seed-start 0
    nnpz=$(ls "$GENDIR"/iter_00/*.npz 2>/dev/null | wc -l)
    if [ "$nnpz" -lt $((GEN_GAMES * 9 / 10)) ]; then
      echo "[L1] GEN FAILED — only $nnpz/$GEN_GAMES npz; aborting lever 1" >&2
    else
      date > "$OUT/done/l1_gen"; echo "[L1] gen done ($nnpz npz)"
    fi
  fi

  # --- train (plain MSE on the residual value column) ---
  if [ -f "$OUT/done/l1_gen" ] && [ ! -f "$RESID_CKPT" ]; then
    echo "[L1] train residual head @ $(date)"
    nice -n 19 env $ENVV $PY -u scripts/train_iter.py \
      --output-root "$GENDIR" --warmstart-root "$WARMSTART_ROOT" \
      --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight 1.0 \
      --stage-local "/tmp/lever_stage_residual" \
      --warm-from "$WARM" --output "$RESID_CKPT" --epochs 3
    rm -rf "/tmp/lever_stage_residual" 2>/dev/null || true
    [ -f "$RESID_CKPT" ] || echo "[L1] TRAIN FAILED — no $RESID_CKPT" >&2
  fi

  # --- scale-curve eval ---
  if [ -f "$RESID_CKPT" ] && [ ! -f "$OUT/done/l1" ]; then
    l1_ok=1
    for s in $L1_SCALES; do
      run_eval "$RESID_CKPT" CARCASSONNE_V25_RESIDUAL_SCALE "$s" "eval_residual_s$(knob_tag "$s")" \
        || { echo "[L1] eval scale=$s FAILED" >&2; l1_ok=0; }
    done
    [ $l1_ok -eq 1 ] && { date > "$OUT/done/l1"; echo "[L1] DONE @ $(date)"; } \
      || echo "[L1] left UNMARKED (an eval failed) — retry on resume" >&2
  fi
fi

############################## LEVER 2 — centered ##############################
if echo " $LEVERS " | grep -q " 2 "; then
  echo ""; echo "########## LEVER 2 (per-node-centered MSE, beta=$BETA) @ $(date) ##########"
  CENT_CKPT="$OUT/ckpt/centered.pt"

  # --- train (reuse rank_data — NO gen) ---
  if [ ! -f "$CENT_CKPT" ]; then
    if [ ! -d "$SHARE/$RANK_DATA/iter_00" ]; then
      echo "[L2] FATAL: rank_data missing at $SHARE/$RANK_DATA/iter_00 — skip lever 2" >&2
    else
      echo "[L2] train centered head (center-weight=$BETA) @ $(date)"
      nice -n 19 env $ENVV $PY -u scripts/train_iter.py \
        --output-root "$SHARE/$RANK_DATA" --warmstart-root "$WARMSTART_ROOT" \
        --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight 1.0 \
        --center-weight "$BETA" \
        --stage-local "/tmp/lever_stage_centered" \
        --warm-from "$WARM" --output "$CENT_CKPT" --epochs 3
      rm -rf "/tmp/lever_stage_centered" 2>/dev/null || true
      [ -f "$CENT_CKPT" ] || echo "[L2] TRAIN FAILED — no $CENT_CKPT" >&2
    fi
  fi

  # --- lambda-curve eval ---
  if [ -f "$CENT_CKPT" ] && [ ! -f "$OUT/done/l2" ]; then
    l2_ok=1
    for lam in $L2_LAMBDAS; do
      run_eval "$CENT_CKPT" CARCASSONNE_V25_VALUE_BLEND "$lam" "eval_centered_b$(knob_tag "$lam")" \
        || { echo "[L2] eval lambda=$lam FAILED" >&2; l2_ok=0; }
    done
    [ $l2_ok -eq 1 ] && { date > "$OUT/done/l2"; echo "[L2] DONE @ $(date)"; } \
      || echo "[L2] left UNMARKED (an eval failed) — retry on resume" >&2
  fi
fi

################################# SUMMARIZE ###################################
echo ""; echo "########## SUMMARY @ $(date) ##########"
$PY scripts/lever_summary.py --out "$OUT"
WINNER=$(sed -n 's/^WINNER=//p' "$OUT/VERDICT.txt" 2>/dev/null)
echo "    VERDICT: WINNER=$WINNER"

if [ "$WINNER" != "none" ] && [ -n "$WINNER" ]; then
  # Map winner -> the value net + value_target the flywheel should iterate on.
  case "$WINNER" in
    l1) FW_CKPT="$OUT/ckpt/residual.pt"; FW_VT="residual";   FW_BLENDENV="CARCASSONNE_V25_RESIDUAL_SCALE" ;;
    l2) FW_CKPT="$OUT/ckpt/centered.pt"; FW_VT="search_value_rank"; FW_BLENDENV="CARCASSONNE_V25_VALUE_BLEND" ;;
  esac
  echo ""
  echo "  ✅ Lever winner = $WINNER. Lever 3 (flywheel): use this value net as a"
  echo "     λ-leaf in NEW self-play and ITERATE (value+search co-adapt, KataGo)."
  echo "     Suggested launch (3-box, REVIEW the marginal first):"
  echo "       RUN=flywheel_$WINNER WARM_SRC=$FW_CKPT VALUE_TARGET=$FW_VT \\"
  echo "       STAGE_B_BLEND=1 ITERS=4 GAMES=400 bash /home/doctor/run_pathb_cluster_loop.sh"
  if [ "$FLYWHEEL_ON_WIN" = "1" ]; then
    echo "  FLYWHEEL_ON_WIN=1 → launching the flywheel now (detached)."
    RUN="flywheel_$WINNER" WARM_SRC="$FW_CKPT" VALUE_TARGET="$FW_VT" STAGE_B_BLEND=1 \
      ITERS=4 GAMES=400 nohup nice -n 19 bash /home/doctor/run_pathb_cluster_loop.sh \
      > "/tmp/flywheel_$WINNER.log" 2>&1 &
    disown
    echo "  flywheel PID=$! log=/tmp/flywheel_$WINNER.log"
  else
    echo "  (FLYWHEEL_ON_WIN=0 — NOT auto-launching; a multi-hour 3-box run wants a"
    echo "   human OK on the marginal first.)"
  fi
else
  echo ""
  echo "  ✗ No lever cleared the marginal≥0 gate → Lever 4 decision branch:"
  echo "    the v2.7-leaf ceiling holds (now ~7× confirmed). Options: build the"
  echo "    non-saturated odometer (ladder_asymmetric + diverse opponents), pursue"
  echo "    a different leaf (better hand-features), or accept ~strong-human and"
  echo "    revisit the goal. Not an auto-run — a branch/decision for Joshua."
fi
echo "=== lever_sequencer on $(hostname) FINISHED @ $(date) ==="
