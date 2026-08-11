#!/usr/bin/env bash
# G2 — THE RULER PASS. One solver pass over the 1,119 exact K<=2 marginalized
# h6400_v2.9 sibling roots; every ranker scored on the SAME solves:
#
#   v29_leaf (curve100, provenance self-check) | curve125 (the CHAMPION's leaf,
#   the pre-registered baseline) | iter_03 (CL-067 warm parent) |
#   value_unlock_v1 (the published CL-073 ResNet) |
#   g2_{resnet_scratch,tf_match,tf_large} x {best,final}
#
# The instrument, the roots, the metric and the bar are UNCHANGED from
# measurement/value_unlock_20260730/run_ruler.sh -- the only addition is the
# --g2-checkpoint flag. INTEGRITY GATE: v29_leaf and curve125 must reproduce
# regret 0.9508 / top1 0.6095 / tau 0.6153 to 4 dp, or the pass is VOID
# (PREREG.md sect 4.3).
#
# MEASUREMENT ONLY. Pure CPU (the harness masks CUDA at import).
set -euo pipefail
WT="${G2_TREE:-/home/doctor/projects/carcassone/.claude/worktrees/agent-a1860cb7f9dc6f899}"
PY=/home/doctor/projects/carcassone/.venv/bin/python
CK=/mnt/c/carc-shared/paper_g2_20260803
OUT="$WT/measurement/paper_g2_20260803"
cd "$WT"

ARGS=()
for arm in resnet_scratch tf_match tf_large; do
  for sel in best final; do
    f="$CK/$arm/$sel.pt"
    [ -f "$f" ] && ARGS+=(--g2-checkpoint "g2_${arm}_${sel}:$f")
  done
done

nice -n 19 "$PY" -u "$WT/scripts/canonical_az/solver_score.py" \
  --max-k 2 --workers "${W:-16}" \
  --leaf-variant 'curve125:{"V29_MEEPLE_CURVE":"-8,-4,-1,0,2.5,3.75,5,6.25"}' \
  --checkpoint /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
  --checkpoint /mnt/c/carc-shared/value_unlock_20260730/ckpt/value_unlock_v1.pt \
  "${ARGS[@]}" \
  --out "$OUT/solver_score_g2.json"
echo "=== run_g2_ruler DONE rc=$? @ $(date -Is) ==="
