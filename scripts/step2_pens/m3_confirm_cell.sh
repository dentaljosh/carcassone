#!/usr/bin/env bash
# M3 CONFIRM at VERDICT power (n=400). One FPU cell per invocation, single-box,
# via the carc-orch fast path (eval_step2_orch.sh). additive leaf, BLEND=0.27,
# SIMS=100. --shared-claim ON (distinct --claim-host) so a killed run self-heals
# stranded .deckclaim files on restart (orphan-claim sweep). Candidate-only
# c_puct/fpu; reference stays CPUCT=3.0/fpu=None.
#
# Env (all have defaults except FPU/OUT/HOSTTAG):
#   FPU=0.4|0.6   OUT=<dir>   HOSTTAG=<claim-host>   OW=28   REPO_SHARE=/mnt/c/carc-shared
#
# MEASUREMENT ONLY — no champion / PRODUCTION.yaml / v2.7 / v2.9 changes.
set -uo pipefail
REPO=/home/doctor/projects/carcassone
cd "$REPO"

SHARE=${REPO_SHARE:?set REPO_SHARE=/mnt/c/carc-shared (local) or /mnt/carc-shared (laptop)}
FPU=${FPU:?set FPU=0.4 or 0.6}
OUT=${OUT:?set OUT=<output dir>}
HOSTTAG=${HOSTTAG:-$(hostname)}
OW=${OW:-28}

CK=$SHARE/rod_v2_flywheel/ckpt/iter_02.pt
SC=$SHARE/step2_pens/warmstart/warmstart.pt

echo "=== M3 CONFIRM fpu=$FPU n=400 sims=100 blend=0.27 additive OW=$OW host=$HOSTTAG @ $(date) ==="
CAND_CKPT=$CK REF_CKPT=$CK SCALAR=$SC OW=$OW SIMS=100 N=400 BLEND=0.27 DROPOUT=0.0 \
  OUT=$OUT bash scripts/step2_pens/eval_step2_orch.sh \
  --leaf-mode additive --c-puct 3.0 --fpu "$FPU" \
  --shared-claim --claim-host "$HOSTTAG" \
  || echo "M3 confirm fpu=$FPU rc=$?"
echo "=== M3 CONFIRM fpu=$FPU DONE @ $(date) ==="
if [ -f "$OUT/summary.json" ]; then
  "$REPO/.venv/bin/python" -c "import json,sys;s=json.load(open(sys.argv[1]));print('RESULT fpu=$FPU winrate=%.4f n=%s'%(s['winrate'],s.get('n','?')))" "$OUT/summary.json"
fi
