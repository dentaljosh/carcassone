#!/bin/bash
# PART C — MEEPLE-CURVE PHASE (beta) DOSE LADDER. Independent of Parts A and B.
# Pre-registration: measurement/curve_shape_scope_20260809/PREREG_DRAFT.md Part C
# Rationale:        measurement/curve_shape_scope_20260809/SCOPE.md §1.3
#
# WHY THIS RUN EXISTS, AND WHY IT IS NOT A RE-RUN OF A KILLED LEVER. The 2026-06-22
# `v28_meeple_recovery_t0` cell measured -75 elo and closed "phase-indexed meeple value".
# That kill is CONFOUNDED: its multiplier `min(1, k/t0) <= 1` everywhere, so it did not only
# change the phase PROFILE, it lowered the term's MEAN MAGNITUDE -- an axis C5 later showed is
# worth +/-60 elo on its own. Its own autopsy said the flips came from magnitude crossing rank
# boundaries, i.e. it was measuring scale and blaming phase. THE E[f]=1 RENORMALIZATION IS THE
# ONLY THING LICENSING THIS RETRY, and it is what makes phase orthogonal to the thrice-swept
# scale axis. A negative slope here RECONFIRMS v28 on clean ground and closes the axis for good.
#
# PRIMARY STATISTIC IS THE FITTED WITHIN-DECK SLOPE OF margin ON beta ACROSS THE FIVE POINTS --
# not any individual cell ("a trend beats underpowered steps"). Each cell alone is
# underpowered at n=200 (~+/-17 elo at 1 sigma) BY DESIGN; the line is the measurement.
#
# ============================ PRE-FLIGHT ============================
# 1. Band 1.15e11, claimed before game 1. ALL FIVE CELLS SHARE IT (within-band deck-matched).
# 2. beta=0.0 RUNS FIRST and is the wiring gate (|elo| < 25). It is injected through
#    --cand-leaf-json exactly like the others, with the DEFAULT values (beta 0.0, norm 1.0),
#    so it proves the injection path is INERT at beta=0 rather than merely bypassing it.
#    Because those are the defaults the resolved leaf hash stays a36d2e15a3b3d71d and the
#    STANDARD curve125 assert passes -- so this cell needs no drift flag. The beta!=0 cells do
#    move the hash (the knobs leave the default-off exclusion set once non-default), so they
#    pass --allow-cand-curve-drift, which STAMPS the candidate leaf instead of asserting it.
#    ⚠️ The flag is named for its first use (curve shape); here it is carrying a phase knob.
#    The curve VALUES are untouched in Part C -- only the multiplier moves.
# 3. Norms are pre-computed (compute_phase_norm.py) and pinned in the cell JSONs; they are an
#    approximation of the MCTS leaf-k histogram (~0.5% residue vs the ~10% confound removed).
# 4. Same R9 / OPENBLAS / rules-profile discipline as the Part-A launcher. Same VOID rule:
#    a cell under 90% completion is void and its number is not quoted.
# =====================================================================
#
# Usage:
#   local:  nice -n 19 bash scripts/classical_search/curvephase_ladder_launcher.sh auto local
#   laptop: nice -n 19 bash scripts/classical_search/curvephase_ladder_launcher.sh auto laptop
set -u
WORKERS="${1:?usage: curvephase_ladder_launcher.sh <WORKERS|auto> <BOX_TAG> [opts]}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

REPO="${CP_REPO:-/home/doctor/projects/carcassone}"
PY="${CP_PY:-/home/doctor/projects/carcassone/.venv/bin/python}"
HARNESS=$REPO/scripts/classical_search/eval_fair_puct.py
CELL_DIR=$REPO/measurement/curve_shape_scope_20260809/cells_phase
PROG=$REPO/measurement/curve_shape_scope_20260809/PROGRESS_phase.tsv

N=200
# Band 1.16e11 = Part C ATTEMPT 2. ⚠️ 1.15e11 was VOIDED 2026-08-10 (attempt 1: the
# retired |elo|<25 wiring gate false-fired at n=200 — PREREG AMENDMENT 1) and must NEVER
# be reused: a band that influenced a decision retires from confirmatory use.
BAND=116000000000
KDETS=8; SIMS=1376; K=2
CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits
PROFILE=fixed_v1
BACKEND=rust
# beta=0 FIRST (the wiring gate), then outward in both directions so a partial session still
# yields a SIGNED, BRACKETED subset rather than one arm of the ladder.
CELLS_ALL="b0p0 bm0p3 b0p3 bm0p6 b0p6"

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared; W_AUTO=30 ;;
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared;   W_AUTO=22 ;;
  *) echo "bad BOX_TAG '$BOX_TAG'"; exit 1 ;;
esac
[ "$WORKERS" = auto ] && WORKERS=$W_AUTO
OUT_ROOT="${CP_OUT_ROOT:-$SHARE/curvephase_ladder}"

CELLS="$CELLS_ALL"; DRYRUN=0; SUBPREFIX=cp_
while [ $# -gt 0 ]; do
  case "$1" in
    --cells)   CELLS="${2:?}"; shift 2 ;;
    --n)       N="${2:?}"; shift 2 ;;
    --band)    BAND="${2:?}"; shift 2 ;;
    --out-sub-prefix) SUBPREFIX="${2:?}"; shift 2 ;;
    --dry-run) DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done
for c in $CELLS; do
  [ -f "$CELL_DIR/curvephase_${c}_${PROFILE}_vs_fairchamp11008.json" ] || {
    echo "missing cell json for '$c'"; exit 1; }
done

export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1
cd "$REPO" || exit 1
HOST=$(hostname); ts() { date +%F_%T; }

probe="$OUT_ROOT/.clock_probe_$$"
mkdir -p "$OUT_ROOT" && : > "$probe" 2>/dev/null
if [ -f "$probe" ]; then
  skew=$(( $(date +%s) - $(stat -c %Y "$probe") )); rm -f "$probe"; askew=${skew#-}
  [ "$askew" -gt 60 ] && { echo "[cp $ROLE $HOST $(ts)] FATAL: clock skew ${skew}s"; exit 3; }
  echo "[cp $ROLE $HOST $(ts)] clock-skew guard OK (${skew}s)"
fi

clean_stale_claims() {
  find "$1" -name "seed*.claim" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}
cell_complete() {
  [ -f "$1/summary.json" ] || return 1
  $PY -c "import json,sys;s=json.load(open(sys.argv[1]));sys.exit(0 if s.get('n',0)>=int(sys.argv[2]) else 1)" \
      "$1/summary.json" "$N" 2>/dev/null
}

if [ "$DRYRUN" = 0 ] && [ ! -f "$PROG" ]; then
  echo -e "cell\tbeta\tstatus\tn\tW\tD\tL\telo\tsigma\tpaired_z\tpaired_margin\tprofile\tr9_ok\tsecs\ttimestamp" > "$PROG"
fi
echo "[cp $ROLE $HOST $(ts)] start: W=$WORKERS budget=k${KDETS}x${SIMS} band=$BAND n=$N cells=[$CELLS]"

for c in $CELLS; do
  sub="${SUBPREFIX}$c"; dir="$OUT_ROOT/$sub"
  cj="$CELL_DIR/curvephase_${c}_${PROFILE}_vs_fairchamp11008.json"
  args=(--info fair --opponent fair-champion --backend "$BACKEND"
        --k-dets $KDETS --sims $SIMS --exact-k $K
        --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
        --n $N --paired --seed-start $BAND
        --rules-profile "$PROFILE" --workers "$WORKERS"
        --out-root "$OUT_ROOT" --out-subdir "$sub"
        --shared-claim --no-results-csv --cand-leaf-json "$cj")
  # beta=0 injects the DEFAULTS, so its hash is unchanged and the standard assert passes.
  # Only the non-zero betas move the hash and therefore need the stamping path.
  [ "$c" != b0p0 ] && args+=(--allow-cand-curve-drift)
  if [ "$DRYRUN" = 1 ]; then echo "[dry-run $c] $PY $HARNESS ${args[*]}"; continue; fi
  if cell_complete "$dir"; then echo "[cp $ROLE $HOST $(ts)] $c complete — skip"; continue; fi
  mkdir -p "$dir"; clean_stale_claims "$dir"
  echo "[cp $ROLE $HOST $(ts)] === cell $c -> $dir ==="
  t0=$(date +%s); nice -n 19 $PY -u "$HARNESS" "${args[@]}"; rc=$?; t1=$(date +%s)
  if [ "$ROLE" = primary ] && [ -f "$dir/summary.json" ]; then
    $PY - "$c" "$cj" "$rc" "$dir/summary.json" "$dir/manifest.json" "$((t1-t0))" >> "$PROG" <<'PYEOF'
import json, os, sys, time
cell, cj, rc, sp, mp, secs = sys.argv[1:7]
s = json.load(open(sp)); beta = json.load(open(cj)).get("v29_phase_beta")
prof, r9 = "?", "?"
if os.path.exists(mp):
    rp = (json.load(open(mp)).get("rules_profile") or {})
    prof = rp.get("name", "?"); r9 = str(rp.get("r9_env_ok", "?")).lower()
pz = s.get("paired_z"); pz = float("nan") if pz is None else float(pz)
pm = s.get("paired_mean_margin"); pm = float("nan") if pm is None else float(pm)
print(f"{cell}\t{beta}\trc{rc}\t{s.get('n')}\t{s.get('W')}\t{s.get('D')}\t{s.get('L')}\t"
      f"{s.get('elo',float('nan')):.1f}\t{s.get('elo_sig_1sigma',float('nan')):.1f}\t"
      f"{pz:.2f}\t{pm:+.3f}\t{prof}\t{r9}\t{secs}\t{time.strftime('%F_%T')}")
PYEOF
  fi
  echo "[cp $ROLE $HOST $(ts)] cell $c done rc=$rc in $((t1-t0))s"
done
echo "[cp $ROLE $HOST $(ts)] launcher finished"
