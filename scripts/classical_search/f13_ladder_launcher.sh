#!/bin/bash
# F13 — MODERN EXACT-K WINRATE LADDER under fixed_v1.
# Pre-registration: measurement/exact_k_ladder_20260803/PREREG_DRAFT.md (BINDING).
#
# Structure lifted from scripts/classical_search/leaf_ablation_launcher.sh (the house
# two-box work-stealing pattern): local=primary (aggregates + writes results.csv/progress
# TSV), laptop=helper (contributes games into the SAME shared out-dir via --shared-claim).
#
# ============================ WHAT THIS RUNS ============================================
# Both sides = the production champion in CLAIRVOYANT matched-mode (the --candidate puct /
# --opponent puct sibling A/B at the champion's own knobs). The ONLY difference between the
# arms is the exact endgame tail K:
#     candidate  = --exact-k <rung>          (rungs 2, 3, 5, 6)
#     incumbent  = --opp-exact-k 4           (production's clairvoyant tail)
# K=4-vs-K=4 is an IDENTITY, not a cell: it is the `--smoke-identity` pre-flight.
#
# Per-solve WALL CAPS (prereg): K<=4 uncapped, K=5 300 s, K=6 600 s, as a per-K MAP
# (--exact-wall-caps "5:300,6:600"), keyed on the SOLVE SIZE. On a cap hit the candidate's
# tail threshold steps DOWN to k-1 (floored at 4 == the incumbent) and the PREFIX SEARCH
# plays that ply — never a raw leaf, so the arm degrades toward the incumbent and the
# measured effect is biased toward ZERO. Every cap hit + fallback step is counted per-game
# and aggregated per-cell into summary.json AND manifest.json (key "f13"), so the
# >20%-censored rule is computable without dirname archaeology.
#
# ============================ PRE-FLIGHT (read before launch) ===========================
# 1. Process census BOTH boxes first. Net-free classical harness (NO carc-orch; CUDA masked).
# 2. ⚠️ CLAIM A FRESH BAND FIRST. The prereg's "1.05e11+ is free" is STALE — 1.05e11 was
#    claimed by F7c on 2026-08-03 (governance/BAND_REGISTRY.csv). Default here is 1.06e11;
#    VERIFY it against BOTH the registry and a share-wide manifest seed_start census, then
#    REGISTER it BEFORE game 1. All rungs share the ONE band (CRN / within-band contrasts).
# 3. Run `--smoke-identity` (K4 vs K4, 20 games) and require PASS before any cell.
# 4. Run `--smoke-k6` (10 games) and read the realized cap-hit rate BEFORE funding the K=6
#    rung — the prereg's bench-then-commit rider. If the smoke already reads >20%, the rung
#    is not-a-verdict by construction; raise the cap or drop the rung.
# 5. Laptop must be code-synced FIRST (git bundle) — this launcher needs the F13 harness
#    flags (--opp-exact-k / --exact-wall-caps / --exact-k-floor / --exact-solver) and the
#    rust_agent `mirror()` accessor on BOTH boxes.
# 6. ⚠️ The tail runs the RUST solver (--exact-solver rust), which requires --backend rust.
#    Both boxes need a carc_rs wheel with MirrorState.solve_endgame (the stale-wheel trap:
#    `python -c "import carc_rs;print(hasattr(carc_rs.MirrorState,'solve_endgame'))"`).
# 6b. ⚠️ W SIZING ON THE CAPPED RUNGS. A capped solve runs in a FORKED CHILD (see
#    exact_tail.py), so during a K=5/K=6 tail a worker can transiently be TWO resident
#    processes, not one. The rust solves are ~100-250 MB each, so W=30 can mean ~30
#    extra transient children at once. `--smoke-k6` prints PEAK RSS for exactly this
#    reason: read it before committing W, and drop W on the K=6 rung if it is tight
#    (bench-then-extrapolate-then-commit; do NOT scale W from the K=2 rung's footprint).
# 7. Results land in <SHARE>/exact_k_ladder/f13_fixed_v1_k<K>/ (per-game json + summary.json
#    + manifest.json with per-side leaf hash, caps, cap-hit totals, censored rate).
# ========================================================================================
#
# Usage:
#   local  (primary): nice -n 19 bash scripts/classical_search/f13_ladder_launcher.sh auto local
#   laptop (helper):  nice -n 19 bash scripts/classical_search/f13_ladder_launcher.sh auto laptop
#   detach:           setsid nohup nice -n 19 bash scripts/classical_search/f13_ladder_launcher.sh auto local >/tmp/f13.log 2>&1 & disown
# Optional:
#   --rungs "k2 k3 k5 k6"   subset/order (default: the full pre-registered ladder)
#   --band 106000000000     seed band (MUST be registered before game 1)
#   --n 400                 games/cell (smoke only)
#   --caps "5:300,6:600"    per-solve wall caps (prereg default)
#   --exact-solver rust|python
#   --backend rust|python
#   --rules-profile NAME    default fixed_v1 (the adopted profile; the prereg pins it)
#   --smoke-identity        K4-vs-K4 identity pre-flight (20 games), exits nonzero on divergence
#   --smoke-k6              10 games of the K6 arm: realized cap-hit rate, wall, peak RSS
#   --smoke                 suppress the results.csv row (throwaway cell runs)
#   --dry-run               print the per-cell harness commands and exit (no compute)
set -u
WORKERS="${1:?usage: f13_ladder_launcher.sh <WORKERS|auto> <BOX_TAG local|laptop> [opts]}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

# F13_REPO / F13_PY exist so a git-worktree SMOKE can point the launcher at unmerged code
# without editing it (worktree-isolation rule). Defaults == the main tree.
REPO="${F13_REPO:-/home/doctor/projects/carcassone}"
PY="${F13_PY:-$REPO/.venv/bin/python}"
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
SMOKER=$REPO/scripts/classical_search/f13_smoke.py
PROG=$REPO/measurement/exact_k_ladder_20260803/F13_PROGRESS.tsv   # --smoke redirects this

# ---- pre-registered knobs (PREREG_DRAFT.md "Design") ----
N=400                      # deck-paired: 200 decks x 2 seats
BAND=106000000000          # 1.06e11 — MUST be verified free + REGISTERED before game 1
INCUMBENT_K=4              # production's clairvoyant tail == both-sides base
CAPS="5:300,6:600"         # per-SOLVE-SIZE wall caps; K<=4 uncapped
K_FLOOR=4                  # the fallback ladder floors AT the incumbent (never below)
CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits; SIMS=2750   # champion-sibling A/B knobs
CENSOR=0.20                # >20% of latch solves capped => not-a-verdict banner

# Rungs in PRE-REGISTERED PRIORITY ORDER. n=400 completes per-rung rather than spreading
# thin, so a partial night yields whole verdicts. K=2 is the negative control (expects <=0
# and, per decision-map branch 4, a >+2sigma read is an INSTRUMENT ALARM, not a finding).
# K=6 is scheduled last: it is the expensive, censorable one.
RUNGS_ALL="k2 k3 k5 k6"
RUNGS="$RUNGS_ALL"

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared; W_AUTO=30 ;;
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared;   W_AUTO=26 ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|primary|laptop|helper)"; exit 1 ;;
esac
[ "$WORKERS" = auto ] && WORKERS=$W_AUTO
OUT_ROOT="${F13_OUT_ROOT:-$SHARE/exact_k_ladder}"

DRYRUN=0; SUBPREFIX=; BACKEND=rust; SMOKE=0; PROFILE=fixed_v1
SOLVER=rust; SMOKE_IDENTITY=0; SMOKE_K6=0; SMOKE_N=
while [ $# -gt 0 ]; do
  case "$1" in
    --rungs)   RUNGS="${2:?--rungs needs a quoted id list}"; shift 2 ;;
    --n)       N="${2:?--n needs a count}"; shift 2 ;;
    --band)    BAND="${2:?--band needs a seed}"; shift 2 ;;
    --caps)    CAPS="${2:?--caps needs a K:SECS map}"; shift 2 ;;
    --k-floor) K_FLOOR="${2:?--k-floor needs an int}"; shift 2 ;;
    --backend) BACKEND="${2:?--backend needs python|rust}"; shift 2 ;;
    --exact-solver) SOLVER="${2:?--exact-solver needs python|rust}"; shift 2 ;;
    --rules-profile) PROFILE="${2:?--rules-profile needs a name}"; shift 2 ;;
    --out-sub-prefix) SUBPREFIX="${2:?}"; shift 2 ;;
    --smoke-identity) SMOKE_IDENTITY=1; shift ;;
    --smoke-k6)       SMOKE_K6=1; shift ;;
    --smoke-n) SMOKE_N="${2:?--smoke-n needs a count}"; shift 2 ;;
    --smoke)   SMOKE=1; shift ;;
    --dry-run) DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done
case "$BACKEND" in python|rust) ;; *) echo "bad --backend '$BACKEND' (python|rust)"; exit 1 ;; esac
case "$SOLVER" in python|rust) ;; *) echo "bad --exact-solver '$SOLVER' (python|rust)"; exit 1 ;; esac
if [ "$SOLVER" = rust ] && [ "$BACKEND" != rust ]; then
  echo "--exact-solver rust requires --backend rust (the tail solves on the PREFIX's live MirrorState)"; exit 1
fi
for r in $RUNGS; do
  case " $RUNGS_ALL " in *" $r "*) ;; *) echo "unknown rung '$r' (valid: $RUNGS_ALL)"; exit 1 ;; esac
done

# ---- rules profile (F7c pattern; F13 pins fixed_v1, the ADOPTED profile) ------------------
# EXP_PROF is the exp_id infix demanded by append_result_row.py:check_rules_profile; the
# out-subdir prefix and the progress TSV are profile-scoped for the same reason.
EXP_PROF=""
if [ "$PROFILE" != walled ]; then
  EXP_PROF="_${PROFILE}"
  [ -z "$SUBPREFIX" ] && SUBPREFIX="f13_${PROFILE}_"
  PROG="${PROG%.tsv}_${PROFILE}.tsv"
  # ⚠️ R9 (D0) is env-latched at IMPORT — base_deck derives the farm data and the Rust
  # registry latches a OnceLock — so it MUST be exported before the harness process starts.
  # `fixed_v1` declares r9_env_expected=True; the manifest's r9_env_ok is how a leg that
  # forgot is caught (and the per-cell guard below refuses to aggregate such a cell).
  export CARCASSONNE_FIX_R9=1
fi
[ -z "$SUBPREFIX" ] && SUBPREFIX=f13_
# ------------------------------------------------------------------------------------------

# A smoke must not append to the REAL run's progress record.
[ "$SMOKE" = 1 ] && PROG="${PROG%.tsv}_SMOKE.tsv"

# production leaf env for BOTH sides — the INTACT champion leaf (v2.9.2 curve125 cap8,
# hash a36d2e15a3b3d71d). F13 changes ONLY the endgame tail; the leaf is identical both
# sides and both arms (the manifest stamps cand_leaf_hash == champ_leaf_hash).
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
# ⚠️ OPENBLAS too — the C5 curve ladder's "x1.75 hang" was OpenBLAS thread oversubscription.
export OPENBLAS_NUM_THREADS=1
cd $REPO || exit 1
HOST=$(hostname)
ts() { date +%F_%T; }

# ---- clock-skew guard (shared) — scripts/measurement_infra/clock_skew_guard.sh -----------
# A client whose clock runs FAST by more than --claim-stale-secs treats every sibling box's
# live claim as stale and steals it; two-box work-stealing silently becomes worth ~1 box.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found"; exit 3; }
carc_clock_skew_guard
# -----------------------------------------------------------------------------------------

# ================================ SMOKES (no cells) ======================================
# Both use a THROWAWAY seed band far from the ladder's, so a smoke can never contaminate,
# pre-warm, or consume the claimed band. Neither writes results.csv or a band claim.
SMOKE_BAND=$(( BAND + 900000000 ))
if [ "$SMOKE_IDENTITY" = 1 ]; then
  n=${SMOKE_N:-20}
  echo "[f13 $ROLE $HOST $(ts)] IDENTITY SMOKE: K4-vs-K4, n=$n, band $SMOKE_BAND (throwaway)"
  nice -n 19 $PY "$SMOKER" --mode identity --n "$n" --seed-start "$SMOKE_BAND" \
      --exact-wall-caps "$CAPS" --exact-k-floor "$K_FLOOR" \
      --exact-solver "$SOLVER" --backend "$BACKEND" --rules-profile "$PROFILE" \
      --cand-sims $SIMS --champ-sims $SIMS --c-puct $CPUCT --tau-p $TAU \
      --leaf-quantize $QUANT --final-select $SELECT
  rc=$?
  echo "[f13 $ROLE $(ts)] identity smoke rc=$rc"
  [ "$rc" -ne 0 ] && { echo "[f13] IDENTITY SMOKE FAILED — do NOT launch the ladder"; exit "$rc"; }
fi
if [ "$SMOKE_K6" = 1 ]; then
  n=${SMOKE_N:-10}
  echo "[f13 $ROLE $HOST $(ts)] K6 BENCH SMOKE: K6-vs-K$INCUMBENT_K, n=$n, band $((SMOKE_BAND+1000)) (throwaway)"
  nice -n 19 $PY "$SMOKER" --mode k6 --n "$n" --seed-start "$((SMOKE_BAND+1000))" \
      --cand-k 6 --opp-k "$INCUMBENT_K" \
      --exact-wall-caps "$CAPS" --exact-k-floor "$K_FLOOR" \
      --exact-solver "$SOLVER" --backend "$BACKEND" --rules-profile "$PROFILE" \
      --cand-sims $SIMS --champ-sims $SIMS --c-puct $CPUCT --tau-p $TAU \
      --leaf-quantize $QUANT --final-select $SELECT
  rc=$?
  echo "[f13 $ROLE $(ts)] k6 bench smoke rc=$rc"
  [ "$rc" -ne 0 ] && exit "$rc"
fi
{ [ "$SMOKE_IDENTITY" = 1 ] || [ "$SMOKE_K6" = 1 ]; } && { echo "[f13 $(ts)] smokes done (no cells run)"; exit 0; }
# =========================================================================================

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
# manifest_profile_ok <manifest.json> -> rc 0 iff it stamps THIS run's profile and r9_env_ok
manifest_profile_ok() {
  [ "$PROFILE" = walled ] && return 0
  [ -f "$1" ] || return 1
  $PY -c "import json,sys;rp=(json.load(open(sys.argv[1])).get('rules_profile') or {});
sys.exit(0 if rp.get('name')==sys.argv[2] and rp.get('r9_env_ok') is True else 1)" \
      "$1" "$PROFILE" 2>/dev/null
}
# The TSV carries the CENSORING columns as first-class result fields: a rung whose
# cap-hit rate cannot be read off the record is not interpretable (prereg branch 3).
tsv_line() {  # $1=rung $2=status $3=summary.json(or -) $4=secs $5=manifest.json(or -)
  if [ "$3" != "-" ] && [ -f "$3" ]; then
    $PY - "$1" "$2" "$3" "$4" "${5:--}" "$PROFILE" "$CENSOR" >> "$PROG" <<'PYEOF'
import json, os, sys, time
rung, status, path, secs, man_path, profile, censor = sys.argv[1:8]
s = json.load(open(path))
pz = s.get("paired_z"); pz = float("nan") if pz is None else pz
f13 = s.get("f13") or {}
cand = f13.get("candidate") or {}
rate = f13.get("censored_rate", float("nan"))
cols = [rung, status, str(s["n"]), str(s["W"]), str(s["D"]), str(s["L"]),
        f"{s['elo']:.1f}", f"{s['elo_sig_1sigma']:.1f}", f"{pz:.2f}",
        str(cand.get("latch_solves", "-")), str(cand.get("cap_hits", "-")),
        str(cand.get("fallback_depth", "-")),
        (f"{rate:.3f}" if rate == rate else "-"),
        ("CENSORED" if f13.get("censored") else "ok")]
prof, r9 = "?", "?"
if man_path != "-" and os.path.exists(man_path):
    rp = (json.load(open(man_path)).get("rules_profile") or {})
    prof = rp.get("name", "?"); r9 = str(rp.get("r9_env_ok", "?")).lower()
cols += [prof, r9, secs, time.strftime("%F_%T")]
print("\t".join(cols))
PYEOF
  else
    printf "%s\t%s\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\t%s\t%s\n" "$1" "$2" "$4" "$(ts)" >> "$PROG"
  fi
}

HDR="rung\tstatus\tn\tW\tD\tL\telo\tsigma\tpaired_z\tlatch_solves\tcap_hits\tfallback\tcensored_rate\tcensor\tprofile\tr9_ok\tsecs\ttimestamp"
[ "$DRYRUN" = 0 ] && { [ -f "$PROG" ] || echo -e "$HDR" > "$PROG"; }
echo "[f13 $ROLE $HOST $(ts)] start: W=$WORKERS backend=$BACKEND solver=$SOLVER profile=$PROFILE r9=${CARCASSONNE_FIX_R9:-unset} caps=$CAPS floor=$K_FLOOR out_root=$OUT_ROOT band=$BAND n=$N rungs=[$RUNGS]"

for r in $RUNGS; do
  K="${r#k}"
  if [ "$K" = "$INCUMBENT_K" ]; then
    echo "[f13 $(ts)] rung $r == the incumbent K=$INCUMBENT_K: that is the IDENTITY SMOKE, not a cell -> skip"
    continue
  fi
  exp="f13_exactk${K}${EXP_PROF}_vs_champk${INCUMBENT_K}_n${N}"
  sub="${SUBPREFIX}k${K}"
  dir="$OUT_ROOT/$sub"
  base_args=(--candidate puct --opponent puct
             --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
             --cand-sims $SIMS --champ-sims $SIMS
             --exact-k "$K" --opp-exact-k "$INCUMBENT_K"
             --exact-wall-caps "$CAPS" --exact-k-floor "$K_FLOOR"
             --exact-solver "$SOLVER" --backend "$BACKEND"
             --n $N --paired --rules-profile "$PROFILE" --exp-id "$exp"
             --seed-start $BAND --out-root "$OUT_ROOT" --out-subdir "$sub")
  # The per-wave harness calls always pass --no-results-csv; only the primary's AGGREGATE
  # call writes the row. --smoke suppresses that too.
  agg_args=("${base_args[@]}")
  [ "$SMOKE" = 1 ] && agg_args+=(--no-results-csv)
  if [ "$DRYRUN" = 1 ]; then
    echo "[dry-run] $exp -> nice -n 19 $PY $HARNESS ${base_args[*]} --workers $WORKERS" \
         "--shared-claim --claim-host f13-$ROLE-$HOST --claim-stale-secs 300 --no-results-csv"
    continue
  fi
  mkdir -p "$dir"
  t0=$(date +%s)

  # resume-by-existence: a rung with a COMPLETE summary.json is done. The per-GAME layer
  # underneath it (one json per seed/seat, written atomically) is what makes a dirty reboot
  # cost at most the games in flight — assume the run WILL be interrupted.
  if cell_complete "$dir"; then
    if [ "$ROLE" = primary ] && ! grep -q "^$exp," "$REPO/experiments/results.csv"; then
      echo "[f13 $(ts)] $exp complete but results.csv row missing -> re-aggregate"
      nice -n 19 $PY "$HARNESS" "${agg_args[@]}" > "/tmp/f13_agg_${r}.log" 2>&1
    fi
    tsv_line "$r" cached "$dir/summary.json" 0 "$dir/manifest.json"
    echo "[f13 $ROLE $(ts)] rung $exp CACHED ($(count_results "$dir")/$N) -> skip"
    continue
  fi

  # primary force-cleans ALL orphan claims at rung start (killed-run / dirty-reboot recovery)
  [ "$ROLE" = primary ] && clean_stale_claims "$dir" ""
  echo "[f13 $ROLE $(ts)] rung $exp start ($(count_results "$dir")/$N cached)"
  iter=0
  while [ "$(count_results "$dir")" -lt "$N" ] && [ $iter -lt 60 ]; do
    nice -n 19 $PY "$HARNESS" "${base_args[@]}" \
      --workers "$WORKERS" --shared-claim --claim-host "f13-$ROLE-$HOST" --claim-stale-secs 300 \
      --no-results-csv > "/tmp/f13_${ROLE}_${r}.log" 2>&1
    clean_stale_claims "$dir" 4
    iter=$((iter+1))
    [ "$(count_results "$dir")" -lt "$N" ] && sleep 5
  done
  secs=$(( $(date +%s) - t0 ))
  if [ "$(count_results "$dir")" -lt "$N" ]; then
    tsv_line "$r" STALLED - "$secs" -
    echo "[f13 $ROLE $(ts)] rung $exp STALLED at $(count_results "$dir")/$N -> next rung (NO row written)"
    continue
  fi
  # fail-loud: a non-walled rung whose manifest does not stamp THIS profile with
  # r9_env_ok=true is VOID — do not let it into results.csv under a fixed_v1 exp_id.
  if ! manifest_profile_ok "$dir/manifest.json"; then
    tsv_line "$r" VOID-PROFILE - "$secs" -
    echo "[f13 $ROLE $(ts)] rung $exp VOID: manifest.json does not stamp profile=$PROFILE + r9_env_ok=true (NO row written)"
    continue
  fi
  if [ "$ROLE" = primary ]; then
    nice -n 19 $PY "$HARNESS" "${agg_args[@]}" > "/tmp/f13_agg_${r}.log" 2>&1
    tsv_line "$r" DONE "$dir/summary.json" "$secs" "$dir/manifest.json"
    echo "[f13 primary $(ts)] rung $exp DONE in ${secs}s -> $(tail -1 "$PROG")"
    # The censoring rule is pre-registered and applies REGARDLESS of z: surface it here
    # so an overnight log carries the banner, not just the JSON.
    $PY -c "import json,sys;f=(json.load(open(sys.argv[1])).get('f13') or {});
print('[f13 CENSORING] ' + (f.get('banner') or 'rung not censored (rate %.3f)' % f.get('censored_rate', 0.0)))" \
        "$dir/summary.json" 2>/dev/null
  else
    tsv_line "$r" helper-done - "$secs" -
    echo "[f13 helper $(ts)] rung $exp games reached $N in ${secs}s (primary aggregates)"
  fi
done
echo "[f13 $ROLE $HOST $(ts)] ALL RUNGS PROCESSED"
[ "$ROLE" = primary ] && [ "$DRYRUN" = 0 ] && { echo "=== F13 LADDER PROGRESS ==="; cat "$PROG"; }
exit 0
