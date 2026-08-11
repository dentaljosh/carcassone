#!/usr/bin/env bash
# Phase 4C/4D orchestrator — train every value-ranking arm on the 4B dataset, gauge each
# on held-out Kendall-tau / regret vs the deep oracle, and aggregate vs the 4A label
# ceiling + the v2.7 reference. Smoke arm A first (2 epochs) to catch breakage cheaply.
#
#   bash scripts/run_value_ranking_arms.sh [DATASET_DIR] [CEILING_JSON] [OUT_ROOT]
set -uo pipefail
cd /home/doctor/projects/carcassone
PY=.venv/bin/python
DATASET=${1:-/mnt/c/carc-shared/value_ranking/dataset}
CEILING=${2:-/mnt/c/carc-shared/value_ranking/label_reliability/summary.json}
OUT=${3:-/mnt/c/carc-shared/value_ranking}
EPOCHS=${EPOCHS:-40}
ARMS=${ARMS:-"A B C C0 E"}

[ -f "$DATASET/rows.npz" ] || { echo "FATAL: no dataset at $DATASET/rows.npz" >&2; exit 1; }
echo "=== value-ranking arms @ $(date): dataset=$DATASET epochs=$EPOCHS arms=$ARMS ==="

echo "--- SMOKE arm A (2 epochs) ---"
nice -n 19 $PY -u scripts/value_ranking_train.py --arm A --dataset "$DATASET" \
  --epochs 2 --out /tmp/vr_arm_smoke 2>&1 | tail -8
[ -f /tmp/vr_arm_smoke/summary.json ] || { echo "FATAL: arm smoke failed" >&2; exit 1; }
echo "--- smoke OK; running full arms ---"

for arm in $ARMS; do
  echo ""; echo "########## ARM $arm @ $(date) ##########"
  nice -n 19 $PY -u scripts/value_ranking_train.py --arm "$arm" --dataset "$DATASET" \
    --epochs "$EPOCHS" --ceiling-json "$CEILING" --out "$OUT/arm_$arm" 2>&1 | tail -12
done

echo ""; echo "===== VALUE-RANKING RESULTS ($(date)) ====="
$PY - "$OUT" "$CEILING" $ARMS <<'PY'
import json, sys
out=sys.argv[1]; ceiling_path=sys.argv[2]; arms=sys.argv[3:]
ceil=None
try:
    cj=json.load(open(ceiling_path)); c=cj.get("ceiling",{}).get("tau_ab")
    ceil=c["mean"] if c else None
except Exception: pass
print(f"{'arm':<5}{'params(k)':>10}{'tau':>12}{'top1':>8}{'pair':>8}{'regret':>9}{'%ceiling':>10}")
rows=[]
for a in arms:
    try: s=json.load(open(f"{out}/arm_{a}/summary.json"))
    except Exception as e: print(f"{a:<5} MISSING ({e})"); continue
    tau=s["tau"]["mean"]; pc=(100*tau/ceil) if ceil else float('nan')
    print(f"{a:<5}{s['n_params']/1e3:>10.0f}{tau:>+12.3f}{s['top1']['mean']:>8.3f}"
          f"{s['pair']['mean']:>8.3f}{s['regret']['mean']:>9.4f}{pc:>9.0f}%")
    rows.append((a,s))
print(f"\nReference: 4A oracle self-agreement ceiling tau(A,B) = {ceil:+.3f}" if ceil else "no ceiling")
print("v2.7 leaf tau (decision_ranking_svtree) = +0.579; value-net (prod, MSE) = +0.081")
# emit RESULTS.csv
with open(f"{out}/VALUE_RANKING_RESULTS.csv","w") as f:
    f.write("arm,n_params,tau,tau_se,top1,pair,regret,tau_high_spread,tau_low_spread,best_val_loss,ceiling_tau_ab\n")
    for a,s in rows:
        hs=s.get('tau_high_spread') or {}; ls=s.get('tau_low_spread') or {}
        f.write(f"{a},{s['n_params']},{s['tau']['mean']:.4f},{s['tau']['se']:.4f},"
                f"{s['top1']['mean']:.4f},{s['pair']['mean']:.4f},{s['regret']['mean']:.4f},"
                f"{hs.get('mean','')},{ls.get('mean','')},{s['best_val_loss']:.4f},{ceil if ceil else ''}\n")
print(f"-> wrote {out}/VALUE_RANKING_RESULTS.csv")
PY
echo "=== ARMS DONE @ $(date) ==="
