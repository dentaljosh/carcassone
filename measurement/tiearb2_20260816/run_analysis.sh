#!/usr/bin/env bash
# =============================================================================
# tiearb2_20260816 — READ-RULE ANALYSIS.  ⚠️ LOCAL BOX ONLY.
#
# The laptop's /mnt/c is its OWN Windows drive and carries none of the project
# share, so an analysis run there would silently read the wrong tree. The guard
# below refuses rather than reading something plausible-looking.
#
# Order: G-DISJOINT (if absent) -> split carve + --verify -> analyse.
# It adjudicates measurement/tiearb2_20260816/READ_RULE.md verbatim, for BOTH
# arbiter arms (honest B=16 and cheap B=B*), and writes READOUT.{md,json} +
# per_position.jsonl.
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"

REPO="$REPO_LOCAL"
PY="$REPO/.venv/bin/python"
LOGS="$HERE/logs"
mkdir -p "$LOGS"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOGS/analysis_$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

banner() { printf '%s\n' "=============================================================================="; }
die() { banner; echo "  ⛔ $*"; banner; exit 1; }

echo "[analysis] $(date -Is) host=$(hostname) log=$LOG"

# ---- LOCAL-BOX GUARD -------------------------------------------------------
for marker in "$SHARE_LOCAL/tiletie_pricing_20260812/clair-puct" \
              "$SHARE_LOCAL/tiearb2_20260816/gen"; do
  [ -d "$marker" ] || die "LOCAL-BOX GUARD: '$marker' absent, so $SHARE_LOCAL is NOT the project share. run_analysis.sh is LOCAL-ONLY (CLUSTER_OPS: the laptop's /mnt/c is its own Windows drive). Refusing."
done
echo "[analysis] local-share guard OK ($SHARE_LOCAL)"

MERGED="$SHARE_RUN_LOCAL/main/merged"

# ---- 1. G-DISJOINT (pre-launch abort; re-assert if the report is absent) ----
if [ ! -f "$HERE/DISJOINTNESS.json" ]; then
  echo "[analysis] DISJOINTNESS.json absent — running the gate"
  nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/gate_disjoint.py" \
    --spent-dir "$REPO/measurement/tiletie_pricing_20260812/positions_pooled" \
    --new-dir   "$HERE/corpus/positions" \
    --out       "$HERE/DISJOINTNESS.json" || die "G-DISJOINT FAILED — the corpus must not be analysed"
fi
"$PY" - "$HERE/DISJOINTNESS.json" <<'PY' || die "G-DISJOINT did not pass"
import json,sys
d=json.load(open(sys.argv[1]))
print(f"[analysis] G-DISJOINT passed={d['passed']} violated={d['n_layers_violated']}")
sys.exit(0 if d.get("passed") else 1)
PY

# ---- 2. the split carve + its reproducibility witness ----------------------
if [ ! -f "$HERE/SPLIT.json" ]; then
  nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/split_tiearb2.py" \
    --arms "$HERE/corpus/positions/ARMS.json" --out "$HERE/SPLIT.json" --seed 20260816 \
    || die "split carve failed"
fi
nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/split_tiearb2.py" \
  --arms "$HERE/corpus/positions/ARMS.json" --out "$HERE/SPLIT.json" --seed 20260816 --verify \
  || die "SPLIT.json is NOT byte-identical to a fresh derivation (G-SPLIT witness failed)"

# ---- 3. adjudicate --------------------------------------------------------
[ -d "$MERGED/clair-puct" ]   || die "no clair-puct records at $MERGED/clair-puct"
[ -d "$MERGED/tier1-greedy" ] || die "no tier1-greedy records at $MERGED/tier1-greedy"
echo "[analysis] IF  records: $(find "$MERGED/clair-puct"   -path '*/records/*.json' | wc -l)"
echo "[analysis] ARB records: $(find "$MERGED/tier1-greedy" -path '*/records/*.json' | wc -l)"

CMD=(nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/analyze_tiearb2.py"
     --if-records  "$MERGED/clair-puct"
     --arb-records "$MERGED/tier1-greedy"
     --plan-dir    "$HERE/corpus/positions"
     --split       "$HERE/SPLIT.json"
     --pilot       "$HERE/PILOT.json"
     --out-dir     "$HERE"
     --n-floor-pooled 1040
     --n-floor-slice  400
     --boot-seed 20260816
     --rnd-seed  20260816
     --parity-base 1)
printf '[analysis] EXACT:'; printf ' %q' "${CMD[@]}"; echo
"${CMD[@]}"
rc=$?
echo "[analysis] analyze_tiearb2 rc=$rc $(date -Is)"
[ "$rc" -eq 0 ] || die "analyse failed (rc=$rc)"

touch "$HERE/DONE_ANALYSIS"
banner
echo "  ✅ ANALYSIS COMPLETE — $HERE/READOUT.md"
grep -m1 -E '^\*\*Branch' "$HERE/READOUT.md" || true
banner
exit 0
