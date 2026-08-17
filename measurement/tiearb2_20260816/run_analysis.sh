#!/usr/bin/env bash
# =============================================================================
# tiearb2_20260816 — THE ANALYSIS CHAIN.  ⚠️ LOCAL BOX ONLY.
#
#   1. RUN_PROVENANCE.json          (make_provenance.py — the blind-ordering record)
#   2. split_tiearb2.py             -> SPLIT.json      (the DESIGN §5.4 stratified
#                                      symmetric half-split, seed 20260816)
#   3. split_tiearb2.py --verify    (re-derive and assert byte-identity)
#   4. gate_disjoint.py             (ONLY if DISJOINTNESS.json is absent —
#                                      DESIGN §4.4/§9 pre-launch abort)
#   5. analyze_tiearb2.py           -> READOUT.md / READOUT.json / per_position.jsonl
#                                      (the join, the §5 statistics, the two arms,
#                                      the B-ladder, and the mechanical READ_RULE
#                                      adjudication — no owner call adjudicates
#                                      any outcome)
#
# ⚠️ WHY LOCAL ONLY. The laptop's `/mnt/c` resolves to its OWN Windows drive, so
# `/mnt/c/carc-shared` there is NOT the project share — the analysis would read a
# different (or empty) set of records and silently produce a wrong read-out. The
# guard below refuses to run unless the share carries artefacts that exist only
# on the real one. See docs/CLUSTER_OPS.md.
#
# This script never launches a scoring run and never plays a game.
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=WORKERS.conf
. "$HERE/WORKERS.conf"

REPO="$REPO_LOCAL"
PY="$REPO/.venv/bin/python"
SHARE_RUN="$SHARE_RUN_LOCAL"
LOGS="$HERE/logs"
PLAN_DIR="$HERE/corpus/positions"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

export CARC_SRC_ROOT="$REPO/src"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

mkdir -p "$LOGS"
LOG="$LOGS/run_analysis_$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

banner() { printf '%s\n' "=============================================================================="; }
die() { banner; echo "  ⛔ $*"; banner; exit 1; }
run() { printf '[analysis] EXACT:'; printf ' %q' "$@"; echo; "$@"; }

echo "[analysis] $(date -Is) run=$RUN_ID host=$(hostname) log=$LOG"

# ---- 0. ⚠️ LOCAL-BOX GUARD — the loud one --------------------------------- #
# $SHARE_LOCAL must be the REAL project share, not the laptop's Windows C:.
# Markers chosen because they are committed run artefacts that exist ONLY there.
if [ "$SHARE_LOCAL" != "/mnt/c/carc-shared" ]; then
  die "LOCAL-BOX GUARD: WORKERS.conf sets SHARE_LOCAL='$SHARE_LOCAL', but the
  analysis chain is defined against the local box's '/mnt/c/carc-shared'.
  Refusing rather than reading an unknown share."
fi
for marker in "$SHARE_LOCAL/tiletie_pricing_20260812/clair-puct" \
              "$SHARE_LOCAL/tiletie_oof_20260814/pilot/tier1-greedy" \
              "$SHARE_LOCAL/$RUN_ID"; do
  [ -d "$marker" ] || die "LOCAL-BOX GUARD: '$marker' is absent, so '$SHARE_LOCAL'
  is NOT the project share. run_analysis.sh is LOCAL-BOX ONLY — the laptop's
  /mnt/c is its own Windows drive and would silently read the WRONG share
  (docs/CLUSTER_OPS.md). Refusing."
done
echo "[analysis] local-share guard OK ($SHARE_LOCAL)"

[ -f "$PLAN_DIR/ARMS.json" ] || die "the fresh corpus plan dir $PLAN_DIR is missing"

# ---- 1. provenance -------------------------------------------------------- #
run nice -n "$NICE" "$PY" "$HERE/make_provenance.py" \
  --out "$HERE/RUN_PROVENANCE.json" \
  || die "make_provenance.py failed"

# ---- 2. the DESIGN §5.4 stratified symmetric half-split ------------------- #
run nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/split_tiearb2.py" \
  --arms "$PLAN_DIR/ARMS.json" \
  --out  "$HERE/SPLIT.json" \
  --seed 20260816 \
  || die "split_tiearb2.py failed"

# ---- 3. ...re-derived and asserted byte-identical -------------------------- #
run nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/split_tiearb2.py" \
  --arms "$PLAN_DIR/ARMS.json" \
  --out  "$HERE/SPLIT.json" \
  --seed 20260816 \
  --verify \
  || die "split_tiearb2.py --verify FAILED: SPLIT.json is not the seeded
  re-derivation. G-SPLIT is a §3 precondition — DO NOT read the analyser's
  output until this is resolved."

# ---- 4. G-DISJOINT, only if it has never been evaluated -------------------- #
if [ -f "$HERE/DISJOINTNESS.json" ]; then
  echo "[analysis] DISJOINTNESS.json present — not re-running the gate (it is a"
  echo "[analysis] PRE-LAUNCH abort and its verdict is already on record)."
else
  run nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/gate_disjoint.py" \
    --spent-dir "$REPO/measurement/tiletie_pricing_20260812/positions_pooled" \
    --new-dir   "$PLAN_DIR" \
    --out       "$HERE/DISJOINTNESS.json" \
    || die "G-DISJOINT FAILED — DESIGN §4.4/§9: the corpus should never have been
  scored. The read-out is a harness report, not a read."
fi
"$PY" -c 'import json,sys;d=json.load(open(sys.argv[1]));print("[analysis] G-DISJOINT passed=%s layers=%s"%(d.get("passed"),{k:v.get("n_intersection") for k,v in (d.get("layers") or {}).items()}))' \
  "$HERE/DISJOINTNESS.json"

# ---- 5. the join, the statistics and the mechanical adjudication ---------- #
# Record roots: one per judge, produced by run_main.sh's merge-by-copy.
# `analyze_tiearb.resolve_records_root` accepts either the judge dir or its
# parent, and analyze_tiearb2 descends into `clair-puct/` for --if-records.
MERGED="$SHARE_RUN/main/merged"
[ -d "$MERGED/clair-puct" ]   || die "no clair-puct records at $MERGED/clair-puct — run_main.sh has not merged them"
[ -d "$MERGED/tier1-greedy" ] || die "no tier1-greedy records at $MERGED/tier1-greedy — run_main.sh has not merged them"
echo "[analysis] records: clair-puct=$(find "$MERGED/clair-puct" -path '*/records/*.json' | wc -l) tier1-greedy=$(find "$MERGED/tier1-greedy" -path '*/records/*.json' | wc -l)"

run nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/analyze_tiearb2.py" \
  --if-records  "$MERGED/clair-puct" \
  --arb-records "$MERGED/tier1-greedy" \
  --plan-dir    "$PLAN_DIR" \
  --split       "$HERE/SPLIT.json" \
  --pilot       "$HERE/PILOT.json" \
  --n-floor-pooled 1040 \
  --n-floor-slice  400 \
  --boot-seed 20260816 \
  --rnd-seed  20260816 \
  --parity-base 1 \
  --out-dir "$HERE"
arc=$?
echo "[analysis] analyze_tiearb2 rc=$arc"
[ "$arc" -eq 0 ] || die "analyze_tiearb2.py failed (rc=$arc)"

touch "$HERE/DONE_ANALYSIS"
banner
echo "  ✅ ANALYSIS DONE — READOUT.md / READOUT.json / per_position.jsonl in"
echo "     $HERE"
echo "  ⚠️ 0 strength games. No experiments/results.csv row, no band, no claim id,"
echo "     governance/PRODUCTION.yaml untouched — on EVERY branch (READ_RULE §5)."
banner
exit 0
