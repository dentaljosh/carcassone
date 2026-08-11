#!/usr/bin/env bash
# STEP B.1 ranking-loss SWEEP driver (Shabbos autonomous run, 2026-06-05).
#
# For each (alpha, temp) config: train the value head with the listwise
# sibling-ranking loss on the shared search_value_rank dataset, then run the
# full lambda-curve (lambda in {0, 0.5, 1.0}) vs HeuristicMCTS@200. Writes
# checkpoints, per-eval manifests, and a per-config .done marker. Fully
# RESUMABLE (skips configs whose .done exists; the eval skips cached games).
#
# Self-contained per box: each box runs its OWN config subset sequentially
# (train + eval all local) — no cross-box coordination, so one box wedging
# never stalls the others. Run the SAME script on 5800x/laptop/xeon with
# different CONFIGS.
#
# Env (all required unless noted):
#   SHARE   per-box share mount (5800x /mnt/c/carc-shared; remotes /mnt/carc-shared)
#   REPO    repo path (5800x/xeon /home/doctor/projects/carcassone; laptop /home/pop/carcassone)
#   WORKERS eval/train worker count for this box
#   CONFIGS space-separated "tag:alpha:temp" triples (e.g. "a10t01:1.0:0.1 a30t01:3.0:0.1")
#   N       eval games per lambda (default 200)
#   DATASET dataset run dir name under SHARE (default rank_data)
#   WARM    warm-from checkpoint (default $SHARE/stage_b/ckpt/iter_01.pt)
#   OUT     sweep output dir (default $SHARE/rank_sweep)
set -uo pipefail

SHARE="${SHARE:?set SHARE}"
REPO="${REPO:?set REPO}"
WORKERS="${WORKERS:-12}"
CONFIGS="${CONFIGS:?set CONFIGS}"
N="${N:-200}"
DATASET="${DATASET:-rank_data}"
WARM="${WARM:-$SHARE/stage_b/ckpt/iter_01.pt}"
OUT="${OUT:-$SHARE/rank_sweep}"
PY="$REPO/.venv/bin/python"
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"

mkdir -p "$OUT/ckpt" "$OUT/done"
cd "$REPO" || { echo "FATAL: cannot cd $REPO" >&2; exit 1; }
echo "=== rank_sweep on $(hostname) @ $(date): CONFIGS=[$CONFIGS] N=$N WORKERS=$WORKERS SHARE=$SHARE ==="

lam_tag() { echo "$1" | sed 's/\.//'; }   # 0.5 -> 05 ; 1.0 -> 10 ; 0 -> 0

for spec in $CONFIGS; do
  tag="${spec%%:*}"; rest="${spec#*:}"; alpha="${rest%%:*}"; temp="${rest##*:}"
  done_marker="$OUT/done/$tag"
  if [ -f "$done_marker" ]; then echo "[$tag] already done — skip"; continue; fi
  ckpt="$OUT/ckpt/$tag.pt"

  echo ""; echo "########## [$tag] alpha=$alpha temp=$temp @ $(date) ##########"

  # --- train (skip if checkpoint already present) ---
  if [ -f "$ckpt" ]; then
    echo "[$tag] train: ckpt exists — skip"
  else
    echo "[$tag] train @ $(date)"
    nice -n 19 env $ENVV $PY -u scripts/train_iter.py \
      --output-root "$SHARE/$DATASET" --warmstart-root "$REPO/data/warmstart/heuristic_tau05" \
      --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight 1.0 \
      --rank-weight "$alpha" --rank-temp "$temp" \
      --stage-local "/tmp/rank_stage_$tag" \
      --warm-from "$WARM" --output "$ckpt" --epochs 3
    trc=$?
    rm -rf "/tmp/rank_stage_$tag" 2>/dev/null || true
    if [ $trc -ne 0 ] || [ ! -f "$ckpt" ]; then
      echo "[$tag] TRAIN FAILED (rc=$trc) — skipping config" >&2
      continue
    fi
  fi

  # --- lambda-curve eval (each lambda; eval self-caches per game) ---
  eval_ok=1
  for lam in 0 0.5 1.0; do
    lt=$(lam_tag "$lam")
    sub="eval_${tag}_b${lt}"
    echo "[$tag] eval lambda=$lam -> $sub @ $(date)"
    nice -n 19 env $ENVV CARCASSONNE_V25_VALUE_BLEND="$lam" $PY -u scripts/eval_net_vs_heuristic.py \
      --checkpoint "$ckpt" --n "$N" --sims 200 --heur-sims 200 --c-puct 3.0 \
      --workers "$WORKERS" --out-root "$OUT" --out-subdir "$sub" \
      --seed-start 1000000000 --paired
    [ $? -ne 0 ] && { echo "[$tag] eval lambda=$lam FAILED" >&2; eval_ok=0; }
  done

  if [ $eval_ok -eq 1 ]; then
    date > "$done_marker"
    echo "[$tag] DONE @ $(date)"
  else
    echo "[$tag] left UNMARKED (an eval failed) — will retry on resume" >&2
  fi
done
echo "=== rank_sweep on $(hostname) FINISHED @ $(date) ==="
