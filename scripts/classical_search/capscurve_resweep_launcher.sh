#!/bin/bash
# CAPS/CURVE RE-SWEEP UNDER fixed_v1 — the gate on absolute fixed-rules strength claims.
# Pre-registration: measurement/capscurve_resweep_20260803/PREREG.md (COMMITTED before game 1).
#
# WHY THIS RUN EXISTS. Joshua adopted `fixed_v1` as the rules profile of record for new
# eval/desktop work on 2026-08-03, and governance/PRODUCTION.yaml's rules_profile note gates
# ABSOLUTE fixed-rules strength claims on this re-sweep. The standing rule is
# feedback_bug_fix_shifts_optima: R9 moved farm decomposition and the four fixed_v1 levers
# moved the meeple economy (a retail start tile, a redraw rule and a fixed cloister scan all
# change how many meeples are committed how early), so the v2.9.2 leaf's tuned optima —
# cap8 / opp_cap8 / curve125, every one of them established under `walled` in the C5 screens —
# are SUSPECT until re-measured under the new rules. This run measures whether they transfer.
#
# Structure lifted from scripts/classical_search/leaf_ablation_launcher.sh (the house two-box
# work-stealing pattern): local=primary (aggregates + writes results.csv/progress TSV),
# laptop=helper (contributes games into the SAME shared out-dir via --shared-claim).
#
# ============================ PRE-FLIGHT (read before launch) ============================
# 1. Process census BOTH boxes first. Net-free classical harness (NO carc-orch; CUDA masked).
# 2. Seed band: see BAND below. PROPOSED in the prereg, REGISTERED BY THE ORCHESTRATOR in
#    governance/BAND_REGISTRY.csv before game 1 — this script does not claim it.
# 3. CHAMPION side = the INTACT champion leaf (env DEFAULT_CONFIG = v2.9.2 curve125 cap8,
#    hash a36d2e15a3b3d71d). CANDIDATE side = that leaf with exactly ONE knob moved
#    (cells/*.json). SIGN CONVENTION: elo is candidate-minus-champion, so a cell that reads
#    POSITIVE says the incumbent value is NOT the optimum under fixed_v1.
# 4. ⚠️ BOTH SIDES RUN fixed_v1 + CARCASSONNE_FIX_R9=1. R9 is env-latched at import (the Rust
#    registry is a OnceLock, base_deck derives at import), so it is exported HERE, before the
#    harness starts — `--rules-profile` cannot apply it and only stamps whether we did.
#    Every manifest carries rules_profile.name == fixed_v1 AND r9_env_ok == true; a cell whose
#    manifest says otherwise is void, whatever this script printed.
# 5. Laptop must be code-synced FIRST (git bundle) AND `maturin develop --release` rebuilt:
#    this run depends on the 2026-08-03 rust_agent fix that threads the rules profile into the
#    CLAIRVOYANT mirrors (src/ change, no .rs change — a bundle+reinstall suffices, but rebuild
#    if in any doubt). Without it the rust mirror plays the ENGINE OF RECORD under a manifest
#    that says fixed_v1; that is the exact hole this run's build closed.
# 6. Results land in <SHARE>/capscurve_resweep/cc_<cell>/ (per-game json + summary.json +
#    manifest.json w/ per-side leaf_cfg+hash + the rules_profile block); primary appends
#    results.csv rows capscurve_<cell>_fixed_v1_vs_puctchamp2750_k2 + one line/cell to
#    measurement/capscurve_resweep_20260803/SWEEP_PROGRESS.tsv.
#    ⚠️ The exp_id MUST contain 'fixed_v1' — scripts/append_result_row.py:check_rules_profile
#    REFUSES a non-walled row whose exp_id does not name its profile. The cell ids below are
#    built to satisfy it; do not "simplify" them.
# =========================================================================================
#
# Usage:
#   local  (primary): nice -n 19 bash scripts/classical_search/capscurve_resweep_launcher.sh auto local
#   laptop (helper):  nice -n 19 bash scripts/classical_search/capscurve_resweep_launcher.sh auto laptop
# Optional:
#   --cells "cap5 ..."       subset/static split; default = the 6 cells in PRIORITY order
#   --n 200                  override game count (smoke/confirm only)
#   --band 103000000000      override seed band (smoke/confirm only)
#   --backend rust|python    search engine for BOTH prefixes (default rust)
#   --out-sub-prefix cc_     out-subdir prefix (smoke uses a distinct prefix)
#   --smoke                  suppress the primary aggregate's results.csv row (throwaway runs)
#   --dry-run                print the per-cell harness commands and exit (no compute)
set -u
WORKERS="${1:?usage: capscurve_resweep_launcher.sh <WORKERS|auto> <BOX_TAG local|laptop> [opts]}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

# CC_REPO / CC_PY exist so a git-worktree SMOKE can point the launcher at unmerged code
# without editing it (worktree-isolation rule). Defaults == the main tree.
REPO="${CC_REPO:-/home/doctor/projects/carcassone}"
PY="${CC_PY:-/home/doctor/projects/carcassone/.venv/bin/python}"
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
CELL_DIR=$REPO/measurement/capscurve_resweep_20260803/cells
PROG=$REPO/measurement/capscurve_resweep_20260803/SWEEP_PROGRESS.tsv   # --smoke redirects

# ---- pre-registered knobs (PREREG.md "Cell configuration") ----
N=200                      # SCREEN tier, deck-paired: 100 decks x 2 seats
K=2                        # exact-K both sides (C7 convention)
BAND=103000000000          # 1.03e11 — PROPOSED in the prereg; orchestrator registers it
CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits; SIMS=2750   # champion-sibling A/B knobs (C5/C7)
PROFILE=fixed_v1           # BOTH sides. Not overridable by flag on purpose: a walled leg of
                           # this run would answer a different question under the same exp_id.

# PRIORITY ORDER. Cells run left-to-right and each completes n=N before the next starts, so a
# partial session yields whole cells, not partial ones. The CURVE axis leads: curve125 is the
# only leaf knob ever PROMOTED (2026-07-13, the first leaf change to the champion), so it is
# the optimum most likely to have been rules-specific and the most valuable to price first.
# curve175 ADDED 2026-08-10 for lever-menu item 4 (docs/LEVER_MENU_PLAN_20260810.md §4.4). It is
# the x1.75 rung of the SAME base curve the other rungs scale (base = curve100 = [-8,-4,-1,0,2,3,
# 4,5]; curve150 == 1.50x base reproduces the existing cell json byte-for-byte, which is how the
# 1.75x values were verified). NOT a virgin rung: c5_s2_curve175_n400 already read +77.7 +/- 17.7
# paired z 4.19 under `walled` (2026-07-13, post-OpenBLAS-fix), statistically tied with curve125's
# +66.8 -- which is WHY curve125 was adopted (CL-051). The menu cell is a fixed_v1 RE-MEASURE.
# It is NOT in the default CELLS_ALL run order: pass it explicitly via --cells.
CELLS_ALL="curve100 curve150 cap5 cap12 oppcap4 oppcap12 curve175"

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared; W_AUTO=30 ;;   # CLUSTER_OPS 4th profile
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared;   W_AUTO=26 ;;   # (re-swept 2026-08-03)
  *) echo "bad BOX_TAG '$BOX_TAG' (local|primary|laptop|helper)"; exit 1 ;;
esac
[ "$WORKERS" = auto ] && WORKERS=$W_AUTO
OUT_ROOT="${CC_OUT_ROOT:-$SHARE/capscurve_resweep}"

CELLS="$CELLS_ALL"; DRYRUN=0; SUBPREFIX=cc_; BACKEND=rust; SMOKE=0; EXP_SUFFIX=""
while [ $# -gt 0 ]; do
  case "$1" in
    --cells)   CELLS="${2:?--cells needs a quoted id list}"; shift 2 ;;
    --n)       N="${2:?--n needs a count}"; shift 2 ;;
    --band)    BAND="${2:?--band needs a seed}"; shift 2 ;;
    # --exp-suffix: appended to the results.csv exp_id ONLY (the cell-json filename is
    # unchanged). Added 2026-08-10 so a RE-RUN of a cell id at a different n/band cannot
    # append a SECOND row under the exp_id the 2026-08-03 n=200 screen already owns —
    # results.csv is the source of truth and a duplicated exp_id makes it ambiguous.
    # ⚠️ The suffix must keep 'fixed_v1' in the exp_id (append, never replace):
    # scripts/append_result_row.py:check_rules_profile REFUSES a non-walled row whose
    # exp_id does not name its profile.
    --exp-suffix) EXP_SUFFIX="${2:?--exp-suffix needs a string}"; shift 2 ;;
    --backend) BACKEND="${2:?--backend needs python|rust}"; shift 2 ;;
    --out-sub-prefix) SUBPREFIX="${2:?}"; shift 2 ;;
    --smoke)   SMOKE=1; shift ;;
    --dry-run) DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done
case "$BACKEND" in python|rust) ;; *) echo "bad --backend '$BACKEND' (python|rust)"; exit 1 ;; esac
[ "$SMOKE" = 1 ] && PROG="${PROG%.tsv}_SMOKE.tsv"
for c in $CELLS; do
  case " $CELLS_ALL " in *" $c "*) ;; *) echo "unknown cell id '$c' (valid: $CELLS_ALL)"; exit 1 ;; esac
  [ -f "$CELL_DIR/capscurve_${c}_${PROFILE}_vs_puctchamp2750_k2.json" ] || { echo "missing cell json for '$c'"; exit 1; }
done

# production leaf env for the CHAMPION (opponent) side — the INTACT v2.9.2 champion.
# ** curve125 = the ADOPTED champion (v2_9_2_Bmild_cap8_curve125). Hash a36d2e15a3b3d71d. **
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
# ⚠️ OPENBLAS too — the C5 curve ladder's "×1.75 hang" was root-caused (e006036) to OpenBLAS
# thread oversubscription: the canon env pinned OMP/MKL but NOT this, so every worker spawned
# a 32-thread busy-wait pool. That incident happened on THIS axis (the curve confirm) with a
# comparable W; the pin is free insurance and result-neutral (clair games barely touch BLAS).
export OPENBLAS_NUM_THREADS=1
# ⚠️ R9 (D0) is env-latched at IMPORT — base_deck derives the farm data and the Rust registry
# latches a OnceLock, so this MUST be exported before the harness process starts. fixed_v1
# declares `r9_env_expected=True`; the manifest's r9_env_ok is how a leg that forgot is caught.
export CARCASSONNE_FIX_R9=1
cd $REPO || exit 1
HOST=$(hostname)
ts() { date +%F_%T; }

# ---- CLOCK-SKEW GUARD (inherited from the F7 launch incident; see leaf_ablation_launcher) ---
# claim.py:is_stale() compares the share's SERVER mtime against this CLIENT's time.time(); a
# fast client sees every sibling claim as stale and steals it, silently halving two-box
# throughput. Refuse to start rather than run at half speed for a session.
probe="$OUT_ROOT/.clock_probe_$$"
mkdir -p "$OUT_ROOT" && : > "$probe" 2>/dev/null
if [ -f "$probe" ]; then
  skew=$(( $(date +%s) - $(stat -c %Y "$probe") ))
  rm -f "$probe"
  askew=${skew#-}
  if [ "$askew" -gt 60 ]; then
    echo "[cc $ROLE $HOST $(ts)] FATAL: clock skew vs the share's mtime clock = ${skew}s (>60s)."
    echo "  Fix the clock, then relaunch, e.g.:  sudo -n date -s @\$(ssh <box-with-the-share> date +%s)"
    exit 3
  fi
  echo "[cc $ROLE $HOST $(ts)] clock-skew guard OK (${skew}s vs the share)"
else
  echo "[cc $ROLE $HOST $(ts)] WARNING: could not write a clock probe to $OUT_ROOT — skew unchecked"
fi
# -----------------------------------------------------------------------------------------

count_results() { ls "$1"/seed*_a*.json 2>/dev/null | grep -vc summary; }
clean_stale_claims() {   # drop .claim files with no result; arg2=min-age-minutes (empty=all)
  local d="$1" age="${2:-}"; local args=(-name "seed*.claim")
  [ -n "$age" ] && args+=(-mmin "+$age")
  find "$d" "${args[@]}" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}
cell_complete() {  # $1 = cell dir -> rc 0 iff summary.json exists with n >= N
  [ -f "$1/summary.json" ] || return 1
  $PY -c "import json,sys;s=json.load(open(sys.argv[1]));sys.exit(0 if s.get('n',0)>=int(sys.argv[2]) else 1)" \
      "$1/summary.json" "$N" 2>/dev/null
}
# The progress TSV carries the RULES COLUMNS as well as the numbers: this run's whole point is
# that the profile was applied, so a row that cannot prove it is not a result.
tsv_line() {  # $1=cell $2=status $3=summary.json(or -) $4=secs $5=manifest.json(or -)
  if [ "$3" != "-" ] && [ -f "$3" ]; then
    $PY - "$1" "$2" "$3" "$4" "${5:--}" >> "$PROG" <<'PYEOF'
import json, os, sys, time
cell, status, path, secs, man_path = sys.argv[1:6]
s = json.load(open(path))
ms = s.get("cand_prefix_ms_per_move", 0.0) / max(1e-9, s.get("champ_prefix_ms_per_move", 1.0))
pz = s.get("paired_z"); pz = float("nan") if pz is None else pz
prof, r9 = "?", "?"
if man_path != "-" and os.path.exists(man_path):
    m = json.load(open(man_path))
    rp = m.get("rules_profile") or {}
    prof = rp.get("name", "?")
    r9 = str(rp.get("r9_env_ok", "?")).lower()
print(f"{cell}\t{status}\t{s['n']}\t{s['W']}\t{s['D']}\t{s['L']}\t{s['elo']:.1f}\t"
      f"{s['elo_sig_1sigma']:.1f}\t{pz:.2f}\t{ms:.2f}\t{prof}\t{r9}\t{secs}\t"
      f"{time.strftime('%F_%T')}")
PYEOF
  else
    printf "%s\t%s\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\t%s\t%s\n" "$1" "$2" "$4" "$(ts)" >> "$PROG"
  fi
}

[ "$DRYRUN" = 0 ] && { [ -f "$PROG" ] || echo -e "cell\tstatus\tn\tW\tD\tL\telo\tsigma\tpaired_z\tms_ratio\tprofile\tr9_ok\tsecs\ttimestamp" > "$PROG"; }
echo "[cc $ROLE $HOST $(ts)] start: W=$WORKERS backend=$BACKEND profile=$PROFILE r9=$CARCASSONNE_FIX_R9 out_root=$OUT_ROOT band=$BAND n=$N cells=[$CELLS]"

for c in $CELLS; do
  cell_base="capscurve_${c}_${PROFILE}_vs_puctchamp2750_k2"
  exp="${cell_base}${EXP_SUFFIX}"
  cell_json="$CELL_DIR/$cell_base.json"
  sub="${SUBPREFIX}$c"
  dir="$OUT_ROOT/$sub"
  base_args=(--candidate puct --opponent puct
             --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
             --cand-sims $SIMS --exact-k $K --n $N --paired --backend "$BACKEND"
             --rules-profile "$PROFILE"
             --cand-leaf-json "$cell_json" --exp-id "$exp"
             --seed-start $BAND --out-root "$OUT_ROOT" --out-subdir "$sub")
  agg_args=("${base_args[@]}")
  [ "$SMOKE" = 1 ] && agg_args+=(--no-results-csv)
  if [ "$DRYRUN" = 1 ]; then
    echo "[dry-run] $exp -> nice -n 19 $PY $HARNESS ${base_args[*]} --workers $WORKERS" \
         "--shared-claim --claim-host cc-$ROLE-$HOST --claim-stale-secs 300 --no-results-csv"
    continue
  fi
  mkdir -p "$dir"
  t0=$(date +%s)

  if cell_complete "$dir"; then
    if [ "$ROLE" = primary ] && ! grep -q "^$exp," "$REPO/experiments/results.csv"; then
      echo "[cc $(ts)] $exp complete but results.csv row missing -> re-aggregate"
      nice -n 19 $PY "$HARNESS" "${agg_args[@]}" > "/tmp/cc_agg_${c}.log" 2>&1
    fi
    tsv_line "$c" cached "$dir/summary.json" 0 "$dir/manifest.json"
    echo "[cc $ROLE $(ts)] cell $exp CACHED ($(count_results "$dir")/$N) -> skip"
    continue
  fi

  [ "$ROLE" = primary ] && clean_stale_claims "$dir" ""
  echo "[cc $ROLE $(ts)] cell $exp start ($(count_results "$dir")/$N cached)"
  iter=0
  while [ "$(count_results "$dir")" -lt "$N" ] && [ $iter -lt 60 ]; do
    nice -n 19 $PY "$HARNESS" "${base_args[@]}" \
      --workers "$WORKERS" --shared-claim --claim-host "cc-$ROLE-$HOST" --claim-stale-secs 300 \
      --no-results-csv > "/tmp/cc_${ROLE}_${c}.log" 2>&1
    clean_stale_claims "$dir" 4
    iter=$((iter+1))
    [ "$(count_results "$dir")" -lt "$N" ] && sleep 5
  done
  secs=$(( $(date +%s) - t0 ))
  if [ "$(count_results "$dir")" -lt "$N" ]; then
    tsv_line "$c" STALLED - "$secs" -
    echo "[cc $ROLE $(ts)] cell $exp STALLED at $(count_results "$dir")/$N -> next cell (NO row written)"
    continue
  fi
  if [ "$ROLE" = primary ]; then
    nice -n 19 $PY "$HARNESS" "${agg_args[@]}" > "/tmp/cc_agg_${c}.log" 2>&1
    tsv_line "$c" DONE "$dir/summary.json" "$secs" "$dir/manifest.json"
    echo "[cc primary $(ts)] cell $exp DONE in ${secs}s -> $(tail -1 "$PROG")"
  else
    tsv_line "$c" helper-done - "$secs" -
    echo "[cc helper $(ts)] cell $exp games reached $N in ${secs}s (primary aggregates)"
  fi
done
echo "[cc $ROLE $HOST $(ts)] ALL CELLS PROCESSED"
[ "$ROLE" = primary ] && [ "$DRYRUN" = 0 ] && { echo "=== CAPS/CURVE RE-SWEEP PROGRESS ==="; cat "$PROG"; }
exit 0
