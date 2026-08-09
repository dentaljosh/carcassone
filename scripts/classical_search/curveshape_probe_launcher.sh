#!/bin/bash
# PART A — MEEPLE-CURVE SHAPE CURVATURE PROBE (the funding gate on the ~3.9-box-day sweep).
# Pre-registration: measurement/curve_shape_scope_20260809/PREREG_DRAFT.md Part A
# Rationale/cost:    measurement/curve_shape_scope_20260809/SCOPE.md §6.3
#
# WHY THIS RUN EXISTS. The production leaf's largest single term is the 8-entry hand-written
# `v29_meeple_curve` (CL-074: whole term ~300 elo, of which the SHAPE is ~136 under fixed_v1).
# The ENTIRE shape record is one 2026-06-25 wave of 5 hand-picked shapes that ended in a
# declared TIE — production is the winner of a coin-flip. Everything measured since moved the
# SCALE, never the shape. This probe asks the cheap question first (SCOPE §6.3): does the shape
# response surface have ANY curvature this instrument can see? If not, a TPE sweep with a
# ±35-elo screen cannot navigate it and must not be funded.
#
# ⚠️ DESIGN DEVIATION, RECORDED (approved 2026-08-09). PREREG §3 specifies the candidate arm as
# "identical in every respect except v29_meeple_curve, injected via --cand-leaf-json". That was
# NOT RUNNABLE: eval_fair_puct's `_assert_netprior_leaf` hard-exits unless the candidate curve
# is exactly curve125. The fix is `--allow-cand-curve-drift` (merged 0974ee4, gate PASS with
# feature-off parity proven against a pre-change HEAD copy) — the seam the prereg assumed
# existed. The alternative (`--opponent h800`) would have changed the opponent, the plane and
# the margin_z definition, i.e. an actual design change, and was rejected.
#
# ============================ PRE-FLIGHT (read before launch) ============================
# 1. Process census BOTH boxes. Net-free classical harness (no carc-orch; CUDA masked).
# 2. Band 1.10e11 — claimed in governance/BAND_REGISTRY.csv BEFORE game 1 (this script does
#    not claim it). ⚠️ ALL FOUR CELLS SHARE THE BAND ON PURPOSE: the robust contrast class is
#    within-band deck-matched, and cross-band contrasts carry ~1.5-2x sigma inflation.
# 3. C0_identity RUNS FIRST AND IS THE GATE. A-gate 0: |elo| < 25 and identical leaf hashes
#    both arms, else ABORT — no cell counts, fix wiring, restart on a NEW band.
# 4. ⚠️ BOTH SIDES fixed_v1 + CARCASSONNE_FIX_R9=1, exported HERE: R9 is env-latched at IMPORT
#    (base_deck derives farm data; the Rust registry latches a OnceLock), so --rules-profile
#    can only STAMP it, not apply it. Every manifest must carry rules_profile.name == fixed_v1
#    AND r9_env_ok == true; a cell whose manifest says otherwise is VOID whatever this printed.
# 5. ⚠️ OPENBLAS_NUM_THREADS=1 is MANDATORY (PREREG §6.4): the C5 x1.75 cell hung at 141/400
#    from OpenBLAS oversubscription and produced a hang-biased +134 that looked like a find.
#    Completion fraction is checked before ANY number is quoted (<90% => VOID, read nothing).
# 6. Laptop must be code-synced FIRST (git bundle) — the --allow-cand-curve-drift seam is new.
# 7. RESUME: --shared-claim gives per-GAME resume across boxes; re-running this launcher after
#    a crash resumes rather than restarts. Clean claims-without-results first (done below).
# =========================================================================================
#
# Usage:
#   local  (primary): nice -n 19 bash scripts/classical_search/curveshape_probe_launcher.sh auto local
#   laptop (helper):  nice -n 19 bash scripts/classical_search/curveshape_probe_launcher.sh auto laptop
# Optional:
#   --cells "C0_identity ..."  subset / ordering (default: all four, C0 FIRST)
#   --n 400                    game count override (smoke only)
#   --band 110000000000        band override (smoke only)
#   --out-sub-prefix cs_       out-subdir prefix (smoke uses a distinct one)
#   --dry-run                  print the per-cell harness commands and exit
set -u
WORKERS="${1:?usage: curveshape_probe_launcher.sh <WORKERS|auto> <BOX_TAG local|laptop> [opts]}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

REPO="${CS_REPO:-/home/doctor/projects/carcassone}"
PY="${CS_PY:-/home/doctor/projects/carcassone/.venv/bin/python}"
HARNESS=$REPO/scripts/classical_search/eval_fair_puct.py
CELL_DIR=$REPO/measurement/curve_shape_scope_20260809/cells
PROG=$REPO/measurement/curve_shape_scope_20260809/PROGRESS.tsv

# ---- pre-registered knobs (PREREG §3 "Fixed experimental conditions") ----
N=400                      # deck-paired: 200 decks x 2 seatings
BAND=110000000000          # 1.10e11 — claimed by the orchestrator before game 1
KDETS=8; SIMS=1376         # k8 x 1376 = 11008, the production fair deploy budget
K=2                        # fair deploy handoff: exact K<=2 marginalized
CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits
PROFILE=fixed_v1
BACKEND=rust
# C0 FIRST: it is the wiring gate, and a partial session must yield the gate before anything
# it would license. Cells run left-to-right, each completing n=N before the next starts.
CELLS_ALL="C0_identity C1_flattop C2_broadlow C3_hoard"

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared; W_AUTO=30 ;;
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared;   W_AUTO=26 ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|primary|laptop|helper)"; exit 1 ;;
esac
[ "$WORKERS" = auto ] && WORKERS=$W_AUTO
OUT_ROOT="${CS_OUT_ROOT:-$SHARE/curveshape_probe}"

CELLS="$CELLS_ALL"; DRYRUN=0; SUBPREFIX=cs_
while [ $# -gt 0 ]; do
  case "$1" in
    --cells)   CELLS="${2:?--cells needs a quoted id list}"; shift 2 ;;
    --n)       N="${2:?--n needs a count}"; shift 2 ;;
    --band)    BAND="${2:?--band needs a seed}"; shift 2 ;;
    --out-sub-prefix) SUBPREFIX="${2:?}"; shift 2 ;;
    --dry-run) DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done
for c in $CELLS; do
  case " $CELLS_ALL " in *" $c "*) ;; *) echo "unknown cell id '$c' (valid: $CELLS_ALL)"; exit 1 ;; esac
  if [ "$c" != C0_identity ]; then
    [ -f "$CELL_DIR/curveshape_${c}_${PROFILE}_vs_fairchamp11008.json" ] || {
      echo "missing cell json for '$c'"; exit 1; }
  fi
done

# ---- production champion leaf env (the OPPONENT arm, and C0's candidate arm too) ----
# curve125 = the adopted champion (v2_9_2_Bmild_cap8_curve125), leaf hash a36d2e15a3b3d71d.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1     # PREREG §6.4 — the C5 hang-bias incident. Mandatory.
export CARCASSONNE_FIX_R9=1       # env-latched at import; --rules-profile only stamps it
cd "$REPO" || exit 1
HOST=$(hostname)
ts() { date +%F_%T; }

# ---- CLOCK-SKEW GUARD (F7c; in all 62 launchers) --------------------------------------
# claim.py:is_stale() compares the share's SERVER mtime against this CLIENT's time.time(); a
# fast client sees every sibling claim as stale and steals it, silently halving throughput.
probe="$OUT_ROOT/.clock_probe_$$"
mkdir -p "$OUT_ROOT" && : > "$probe" 2>/dev/null
if [ -f "$probe" ]; then
  skew=$(( $(date +%s) - $(stat -c %Y "$probe") )); rm -f "$probe"; askew=${skew#-}
  if [ "$askew" -gt 60 ]; then
    echo "[cs $ROLE $HOST $(ts)] FATAL: clock skew vs the share = ${skew}s (>60s)."
    echo "  Fix: sudo -n date -s @\$(ssh <share-host> date +%s)   then relaunch."
    exit 3
  fi
  echo "[cs $ROLE $HOST $(ts)] clock-skew guard OK (${skew}s)"
else
  echo "[cs $ROLE $HOST $(ts)] WARNING: no clock probe writable at $OUT_ROOT — skew unchecked"
fi
# ---------------------------------------------------------------------------------------

clean_stale_claims() {   # drop .claim files with no result (resume hygiene)
  find "$1" -name "seed*.claim" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}
cell_complete() {  # rc 0 iff summary.json exists with n >= N
  [ -f "$1/summary.json" ] || return 1
  $PY -c "import json,sys;s=json.load(open(sys.argv[1]));sys.exit(0 if s.get('n',0)>=int(sys.argv[2]) else 1)" \
      "$1/summary.json" "$N" 2>/dev/null
}
tsv_line() {  # $1=cell $2=status $3=summary.json|- $4=secs $5=manifest.json|-
  if [ "$3" != "-" ] && [ -f "$3" ]; then
    $PY - "$1" "$2" "$3" "$4" "${5:--}" >> "$PROG" <<'PYEOF'
import json, os, sys, time
cell, status, path, secs, man_path = sys.argv[1:6]
s = json.load(open(path))
pz = s.get("paired_z"); pz = float("nan") if pz is None else float(pz)
mz = s.get("margin_z", s.get("paired_margin_z")); mz = float("nan") if mz is None else float(mz)
prof, r9, ch, co = "?", "?", "?", "?"
if man_path != "-" and os.path.exists(man_path):
    m = json.load(open(man_path))
    rp = m.get("rules_profile") or {}
    prof = rp.get("name", "?"); r9 = str(rp.get("r9_env_ok", "?")).lower()
    ch = str(m.get("cand_leaf_hash", "?"))[:16]; co = str(m.get("opp_leaf_hash", "?"))[:16]
print(f"{cell}\t{status}\t{s.get('n','?')}\t{s.get('W','?')}\t{s.get('D','?')}\t{s.get('L','?')}\t"
      f"{s.get('elo',float('nan')):.1f}\t{s.get('elo_sig_1sigma',float('nan')):.1f}\t"
      f"{mz:.2f}\t{pz:.2f}\t{prof}\t{r9}\t{ch}\t{co}\t{secs}\t{time.strftime('%F_%T')}")
PYEOF
  else
    printf "%s\t%s\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\t%s\t%s\n" "$1" "$2" "$4" "$(ts)" >> "$PROG"
  fi
}

if [ "$DRYRUN" = 0 ] && [ ! -f "$PROG" ]; then
  echo -e "cell\tstatus\tn\tW\tD\tL\telo\tsigma\tmargin_z\tpaired_z\tprofile\tr9_ok\tcand_leaf\topp_leaf\tsecs\ttimestamp" > "$PROG"
fi
echo "[cs $ROLE $HOST $(ts)] start: W=$WORKERS backend=$BACKEND profile=$PROFILE r9=$CARCASSONNE_FIX_R9"
echo "[cs $ROLE $HOST $(ts)] budget=k${KDETS}x${SIMS}=$((KDETS*SIMS)) band=$BAND n=$N cells=[$CELLS] out=$OUT_ROOT"

for c in $CELLS; do
  sub="${SUBPREFIX}$c"; dir="$OUT_ROOT/$sub"
  args=(--info fair --opponent fair-champion --backend "$BACKEND"
        --k-dets $KDETS --sims $SIMS --exact-k $K
        --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
        --n $N --paired --seed-start $BAND
        --rules-profile "$PROFILE" --workers "$WORKERS"
        --out-root "$OUT_ROOT" --out-subdir "$sub"
        --shared-claim --no-results-csv)
  if [ "$c" != C0_identity ]; then
    args+=(--allow-cand-curve-drift --cand-leaf-json "$CELL_DIR/curveshape_${c}_${PROFILE}_vs_fairchamp11008.json")
  fi
  if [ "$DRYRUN" = 1 ]; then
    echo "[dry-run $c] $PY $HARNESS ${args[*]}"; continue
  fi
  if cell_complete "$dir"; then
    echo "[cs $ROLE $HOST $(ts)] $c already complete (n>=$N) — skipping"; continue
  fi
  mkdir -p "$dir"; clean_stale_claims "$dir"
  echo "[cs $ROLE $HOST $(ts)] === cell $c -> $dir ==="
  t0=$(date +%s)
  nice -n 19 $PY -u "$HARNESS" "${args[@]}"; rc=$?
  t1=$(date +%s)
  if [ "$ROLE" = primary ]; then
    st=ok; [ "$rc" = 0 ] || st="rc$rc"
    cell_complete "$dir" || st="${st}_SHORT"
    tsv_line "$c" "$st" "$dir/summary.json" "$((t1-t0))" "$dir/manifest.json"
  fi
  echo "[cs $ROLE $HOST $(ts)] cell $c done rc=$rc in $((t1-t0))s"
done
echo "[cs $ROLE $HOST $(ts)] launcher finished"
