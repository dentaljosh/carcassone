#!/usr/bin/env bash
# Analysis chain for TERMINAL-GROUNDED TIE ARBITRATION. Runs AFTER the main read.
#
#  1. merge the per-chunk ARB records into ONE root (per-chunk roots exist because
#     run_tiletie.verify_leg_records demands a records dir hold exactly its own
#     chunk's rids -- DESIGN §5). analyze_tiletie.discover_records REFUSES
#     duplicates, so a double-merged chunk cannot pass silently.
#  2. run analyze_tiearb.py -- the join, the §4 statistics and the mechanical
#     READ_RULE adjudication -- against the pooled 733-position plan and the
#     THREE ARB record roots that together cover the corpus:
#        tiletie_oof_20260814/merged  (DEV main, 2026-08-14)
#        tiletie_oof_20260814/pilot   (DEV pilot, 2026-08-14)
#        tiearb_20260816/merged       (HOLDOUT, this run)
#
# Runs in the MAIN TREE.
set -euo pipefail
W=/home/doctor/projects/carcassone
cd "$W"
M=$W/measurement/tiearb_20260816
PY=/home/doctor/projects/carcassone/.venv/bin/python
SHARE=/mnt/c/carc-shared/tiearb_20260816
FULL_SUPPLY=$W/measurement/tiletie_pricing_20260812/positions/POSITIONS_PLAN.json
export CARC_SRC_ROOT=/home/doctor/projects/carcassone/src
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

mkdir -p "$M/logs"

# ---- 1. merge chunk records --------------------------------------------------
nice -n 19 "$PY" - <<'PYEOF'
import json, shutil, sys
from pathlib import Path
share = Path("/mnt/c/carc-shared/tiearb_20260816")
dst_root = share / "merged/tier1-greedy"
merged, dupes = 0, []
for ch in sorted(share.glob("chunk*/tier1-greedy")):
    for rec in sorted(ch.glob("*/leg*/records/*.json")):
        rel = rec.relative_to(ch)
        dst = dst_root / rel
        if dst.exists():
            dupes.append(str(rel)); continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rec, dst); merged += 1
print(json.dumps({"merged": merged, "already_present": len(dupes)}))
if dupes:
    print("NOTE: %d records already merged (idempotent re-run)" % len(dupes), file=sys.stderr)
PYEOF

# ---- 2. join + adjudicate ----------------------------------------------------
nice -n 19 "$PY" scripts/tiletie/analyze_tiearb.py \
  --if-records  /mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct \
  --arb-records /mnt/c/carc-shared/tiletie_oof_20260814/merged \
  --arb-records /mnt/c/carc-shared/tiletie_oof_20260814/pilot \
  --arb-records "$SHARE/merged" \
  --plan-dir         "$W/measurement/tiletie_pricing_20260812/positions_pooled" \
  --full-supply-plan "$FULL_SUPPLY" \
  --holdout-roots    "$W/measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json" \
  --boot-seed 20260816 \
  --rnd-seed  20260816 \
  --out-dir "$M" 2>&1 | tee "$M/logs/analyze_tiearb.log"

touch "$M/DONE_ANALYSIS"
echo "[analysis] done"
