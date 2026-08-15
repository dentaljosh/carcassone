#!/usr/bin/env bash
# Analysis chain for the OUT-OF-FAMILY re-pricing. Runs AFTER the main read.
#
#  1. merge the per-chunk out-of-family records into ONE root (per-chunk roots
#     exist because run_tiletie.verify_leg_records demands a records dir hold
#     exactly its own leg's rids -- DESIGN §0.A). analyze_tiletie.discover_records
#     REFUSES duplicates, so a double-merged chunk cannot pass silently.
#  2. stage the IN-FAMILY dev records by FILENAME only (DESIGN §0.B firewall).
#  3. run analyze_tiletie -- UNMODIFIED, same --plan-dir, same --full-supply-plan,
#     same --parity-base -- once per judge, so the scales and the estimators are
#     literally the same code on the same positions.
#  4. run analyze_oof to adjudicate READ_RULE.md.
set -euo pipefail
W=/home/doctor/projects/carcassone/.claude/worktrees/agent-a1badefaaed4b6d69
cd "$W"
M=$W/measurement/tiletie_oof_20260814
PY=/home/doctor/projects/carcassone/.venv/bin/python
SHARE=/mnt/c/carc-shared/tiletie_oof_20260814
FULL_SUPPLY=$W/measurement/tiletie_pricing_20260812/positions/POSITIONS_PLAN.json
export CARC_SRC_ROOT=/home/doctor/projects/carcassone/src

# ---- 1. merge chunk records --------------------------------------------------
"$PY" - <<'PYEOF'
import json, shutil, sys
from pathlib import Path
share = Path("/mnt/c/carc-shared/tiletie_oof_20260814")
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

# ---- 2. stage in-family dev records (filename-only firewall) -----------------
"$PY" scripts/tiletie/build_oof_plan.py \
  --source-dir /home/doctor/projects/carcassone/measurement/tiletie_pricing_20260812/positions_pooled \
  --stage-if > "$M/PLAN_SUMMARY_stage.json"

# ---- 3. the pre-registered estimators, once per judge ------------------------
"$PY" scripts/tiletie/analyze_tiletie.py \
  --records-root "$SHARE/if_dev/clair-puct" \
  --plan-dir "$M/positions_main" \
  --full-supply-plan "$FULL_SUPPLY" \
  --parity-base 1 \
  --label "tiletie-oof dev slice / IN-FAMILY clair-puct" \
  --out-dir "$M/readout_if" > "$M/logs/analyze_if.log" 2>&1

"$PY" scripts/tiletie/analyze_tiletie.py \
  --records-root "$SHARE/merged/tier1-greedy" \
  --plan-dir "$M/positions_main" \
  --full-supply-plan "$FULL_SUPPLY" \
  --parity-base 1 \
  --label "tiletie-oof dev slice / OUT-OF-FAMILY tier1-greedy" \
  --out-dir "$M/readout_oof" > "$M/logs/analyze_oof_leg.log" 2>&1

# ---- 4. adjudicate -----------------------------------------------------------
"$PY" scripts/tiletie/analyze_oof.py \
  --if-per-position  "$M/readout_if/per_position.jsonl" \
  --oof-per-position "$M/readout_oof/per_position.jsonl" \
  --if-verdict       "$M/readout_if/VERDICT.json" \
  --oof-verdict      "$M/readout_oof/VERDICT.json" \
  --if-records       "$SHARE/if_dev/clair-puct" \
  --oof-records      "$SHARE/merged/tier1-greedy" \
  --plan-dir         "$M/positions_main" \
  --out-dir          "$M"

touch "$M/DONE_ANALYSIS"
echo "[analysis] done"
