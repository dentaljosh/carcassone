#!/bin/bash
# LEAF-COMPONENT KNOCKOUT ABLATION launcher — the first systematic SUBTRACTIVE ablation of
# the production champion leaf v2.9.2 (Bmild_cap8_curve125, fingerprint a36d2e15).
# Pre-registration: measurement/leaf_ablation_20260730/PREREG.md (COMMITTED before game 1).
#
# Structure lifted verbatim from scripts/classical_search/c7_s1_launcher.sh (the house
# two-box work-stealing pattern): local=primary (aggregates + writes results.csv/progress
# TSV), laptop=helper (contributes games into the SAME shared out-dir via --shared-claim).
#
# ============================ PRE-FLIGHT (read before launch) ============================
# 1. Process census BOTH boxes first. Net-free classical harness (NO carc-orch; CUDA masked).
# 2. Seed band consumed: 9.60e10 — seeds 96,000,000,000..96,000,000,199 (n=400 paired = 200
#    decks x 2 seats), ONE band shared by ALL cells (CRN: every cell plays the SAME 200 decks
#    against the SAME intact-champion opponent). VERIFIED FREE 2026-07-30 against BOTH
#    governance/BAND_REGISTRY.csv and the share-wide manifest seed_start census.
# 3. CHAMPION side = the INTACT champion leaf (env DEFAULT_CONFIG = v2.9.2 curve125 cap8,
#    hash a36d2e15a3b3d71d — runtime-verified 2026-07-30). CANDIDATE side = champion leaf
#    with exactly ONE component knocked out (cells/*.json). SIGN CONVENTION: elo is
#    candidate-minus-champion, so a NEGATIVE elo means the knocked-out component is WORTH
#    that much. The component's value == -elo.
# 4. ALL SIX CELLS STAY ON THE CYTHON FLOAT FAST PATH (verified 2026-07-30: every cell passes
#    _assert_cy_float_path AND is bit-exact cy==pure-python on 360 mid-game states). No leaf
#    source change was needed and none was made — every knockout is an EXISTING LeafConfig
#    field. capoff needs SUPPORTS_F6_SOFT_CAP; both boxes verified True.
# 5. Laptop must be code-synced FIRST (git bundle). No cy rebuild needed (no .pyx change).
# 6. Results land in <SHARE>/leaf_ablation/abl_<cell>/ (per-game json + summary.json +
#    manifest.json w/ per-side leaf_cfg+hash); primary appends results.csv rows exp_id
#    abl_<cell>_vs_puctchamp2750_k2 + one line/cell to
#    measurement/leaf_ablation_20260730/ABL_PROGRESS.tsv.
# =========================================================================================
#
# ================================ F7b ADDENDUM (2026-08-02) ==============================
# The two FARM cells F7 deferred (`farmbaseoff`, `farmgrowthoff`) are now runnable: the
# knockouts exist as default-off LeafConfig fields implemented in the Rust leaf + the Python
# reference (commit "F7b: default-off FARM-TERM KNOCKOUT knobs ..."), gated 0-mismatch by
# scripts/rustport/reconcile_leaf.py (`--configs all` = knobs-off, `--configs farmoff` =
# knobs-on py-vs-rust). Two launcher changes, both back-compatible:
#   * `--backend {python,rust}`, DEFAULT rust (port-1/G6 wiring, 2026-08-02). The F7 cells
#     ran the python route; passing `--backend python` reproduces them byte-for-byte.
#   * WORKERS accepts `auto` -> 32 local / 24 laptop (Joshua 2026-08-02: assume W* ~= threads
#     for the eval class; F7d measured W*=30/22, within the settle band — do NOT re-sweep).
# ⚠️ The farm knockouts have NO Cython implementation by design, so `--backend python` would
# run the candidate on the ~12.5x-slower pure-Python flat leaf. F7b cells run rust.
# Prereg: measurement/leaf_ablation_20260730/F7B_PREREG.md (its own FRESH band; F7's 9.60e10
# is RETIRED). Run them explicitly: --cells "farmbaseoff farmgrowthoff" --band <F7b band>.
# =========================================================================================
#
# ================================ F7c ADDENDUM (2026-08-03) ==============================
# The whole CL-074 component table is REMEASURED under the adopted rules profile `fixed_v1`
# (+ CARCASSONNE_FIX_R9=1). Rationale is feedback_bug_fix_shifts_optima applied to a whole
# rule set: R9 moved farm decomposition and the four fixed_v1 levers moved the meeple economy,
# so a component's *value* — not just a knob's optimum — may not transfer. (The caps/curve
# re-sweep, 2026-08-03, closed ALL NULL, so the optima cap8/oppcap8/curve125 are UNCHANGED and
# this run does NOT re-tune first.) One launcher change, back-compatible:
#   * `--rules-profile <name>`, DEFAULT `walled` == the F7/F7b behaviour byte-for-byte.
# A NON-walled profile changes four things and nothing else:
#   1. exports CARCASSONNE_FIX_R9=1 BEFORE the harness starts. R9 is env-latched at import
#      (base_deck derives the farm data; the Rust registry latches a OnceLock), so
#      `--rules-profile` cannot apply it and only STAMPS whether we did. Every manifest carries
#      rules_profile.name AND r9_env_ok; a cell whose manifest says otherwise is VOID whatever
#      this script printed. The per-cell guard below refuses to aggregate such a cell.
#   2. exp_id becomes abl_<cell>_<profile>_vs_puctchamp2750_k2. ⚠️ REQUIRED, not cosmetic:
#      scripts/append_result_row.py:check_rules_profile REFUSES a non-walled row whose exp_id
#      does not name its profile, and results.csv is otherwise the WALLED record.
#   3. out-subdir prefix becomes abl_<profile>_ so the fixed_v1 cells cannot collide with the
#      walled F7/F7b dirs under the same OUT_ROOT (still overridable by --out-sub-prefix).
#   4. progress TSV becomes ABL_PROGRESS_<profile>.tsv and gains `profile` + `r9_ok` columns —
#      this run's whole point is that the profile applied, so a row that cannot prove it is
#      not a result. The walled TSV keeps its original 12-column schema untouched.
# The cell JSONs are UNCHANGED (a knockout is a leaf config; it does not depend on the rules),
# so a fixed_v1 cell reads the same cells/abl_<cell>_vs_puctchamp2750_k2.json as its walled twin.
# ⚠️ A non-walled leg REQUIRES the 2026-08-03 rust_agent build that threads the profile into the
# CLAIRVOYANT mirrors (mirror_geometry_kwargs + the unconditional ply-0 digest check). Without
# it the rust mirror plays the ENGINE OF RECORD under a manifest that says fixed_v1.
# Prereg: measurement/leaf_ablation_20260730/F7C_PREREG.md (its own FRESH band).
# =========================================================================================
#
# Usage:
#   local  (primary): nice -n 19 bash scripts/classical_search/leaf_ablation_launcher.sh auto local
#   laptop (helper):  nice -n 19 bash scripts/classical_search/leaf_ablation_launcher.sh auto laptop
# Optional:
#   --cells "meepleoff ..."  subset/static split; default = the 6 F7 cells in PRIORITY order
#   --n 400                  override game count (smoke only)
#   --band 96000000000       override seed band (smoke only)
#   --backend rust|python    search engine for BOTH prefixes (default rust)
#   --rules-profile NAME     rules profile for BOTH sides (default walled == F7/F7b)
#   --out-sub-prefix abl_    out-subdir prefix (smoke uses a distinct prefix)
#   --smoke                  suppress the primary aggregate's results.csv row (throwaway runs)
#   --dry-run                print the per-cell harness commands and exit (no compute)
set -u
WORKERS="${1:?usage: leaf_ablation_launcher.sh <WORKERS|auto> <BOX_TAG local|laptop> [opts]}"
BOX_TAG="${2:?BOX_TAG required: local|primary or laptop|helper}"
shift 2

# ABL_REPO / ABL_PY exist so a git-worktree SMOKE can point the launcher at unmerged
# code without editing it (worktree-isolation rule). Defaults == the main tree.
REPO="${ABL_REPO:-/home/doctor/projects/carcassone}"
PY="${ABL_PY:-$REPO/.venv/bin/python}"
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py
CELL_DIR=$REPO/measurement/leaf_ablation_20260730/cells
PROG=$REPO/measurement/leaf_ablation_20260730/ABL_PROGRESS.tsv   # --smoke redirects this

# ---- pre-registered knobs (PREREG.md "Cell configuration") ----
N=400                      # deck-paired: 200 decks x 2 seats
K=2                        # exact-K both sides (C7 convention)
BAND=96000000000           # 9.60e10, ONE band for all cells (CRN). Verified free 2026-07-30.
CPUCT=1.5; TAU=5; QUANT=float; SELECT=visits; SIMS=2750   # champion-sibling A/B knobs (C5/C7)

# PRIORITY ORDER (PREREG.md "Priority"). Cells run left-to-right; n=400 completes per-cell
# rather than spreading thin, so a partial night yields whole verdicts, not partial ones.
CELLS_F7="meepleoff oppanticoff anticoff selfanticoff meepleflat capoff"
CELLS_F7B="farmbaseoff farmgrowthoff farmgrowthoff_confirm"   # run these explicitly via --cells
CELLS_ALL="$CELLS_F7 $CELLS_F7B"               # the VALID id set

case "$BOX_TAG" in
  local|primary)  ROLE=primary; SHARE=/mnt/c/carc-shared; W_AUTO=32 ;;
  laptop|helper)  ROLE=helper;  SHARE=/mnt/carc-shared;   W_AUTO=24 ;;
  *) echo "bad BOX_TAG '$BOX_TAG' (local|primary|laptop|helper)"; exit 1 ;;
esac
[ "$WORKERS" = auto ] && WORKERS=$W_AUTO
OUT_ROOT="${ABL_OUT_ROOT:-$SHARE/leaf_ablation}"

CELLS="$CELLS_F7"; DRYRUN=0; SUBPREFIX=; BACKEND=rust; SMOKE=0; PROFILE=walled
while [ $# -gt 0 ]; do
  case "$1" in
    --cells)   CELLS="${2:?--cells needs a quoted id list}"; shift 2 ;;
    --n)       N="${2:?--n needs a count}"; shift 2 ;;
    --band)    BAND="${2:?--band needs a seed}"; shift 2 ;;
    --backend) BACKEND="${2:?--backend needs python|rust}"; shift 2 ;;
    --rules-profile) PROFILE="${2:?--rules-profile needs a name}"; shift 2 ;;
    --out-sub-prefix) SUBPREFIX="${2:?}"; shift 2 ;;
    --smoke)   SMOKE=1; shift ;;
    --dry-run) DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done
case "$BACKEND" in python|rust) ;; *) echo "bad --backend '$BACKEND' (python|rust)"; exit 1 ;; esac

# ---- F7c: rules profile (default walled == the F7/F7b path, byte-for-byte) ----------------
# EXP_PROF is the exp_id infix demanded by append_result_row.py:check_rules_profile; the
# out-subdir prefix and the progress TSV are profile-scoped for the same reason (a fixed_v1
# cell must not land in, or be read out of, its walled twin's directory/record).
EXP_PROF=""
if [ "$PROFILE" != walled ]; then
  EXP_PROF="_${PROFILE}"
  [ -z "$SUBPREFIX" ] && SUBPREFIX="abl_${PROFILE}_"
  PROG="${PROG%.tsv}_${PROFILE}.tsv"
  # ⚠️ R9 (D0) is env-latched at IMPORT — base_deck derives the farm data and the Rust
  # registry latches a OnceLock — so it MUST be exported before the harness process starts.
  # `fixed_v1` declares r9_env_expected=True; the manifest's r9_env_ok is how a leg that
  # forgot is caught (and the per-cell guard below refuses to aggregate such a cell).
  export CARCASSONNE_FIX_R9=1
fi
[ -z "$SUBPREFIX" ] && SUBPREFIX=abl_
# ------------------------------------------------------------------------------------------

# A smoke must not append to the REAL run's progress record (its rows carry a
# throwaway band and an under-powered n, and would read as run history).
[ "$SMOKE" = 1 ] && PROG="${PROG%.tsv}_SMOKE.tsv"
for c in $CELLS; do
  case " $CELLS_ALL " in *" $c "*) ;; *) echo "unknown cell id '$c' (valid: $CELLS_ALL)"; exit 1 ;; esac
  # F7b farm knockouts have no Cython leaf by design (see the F7b addendum): on the
  # python backend the candidate would run the ~12.5x-slower pure-Python flat leaf.
  case " $CELLS_F7B " in
    *" $c "*) [ "$BACKEND" = python ] && echo "[abl] WARNING: cell '$c' (F7b farm knockout) on --backend python runs the pure-Python flat leaf (~12.5x slower per leaf)" ;;
  esac
  [ -f "$CELL_DIR/abl_${c}_vs_puctchamp2750_k2.json" ] || { echo "missing cell json for '$c'"; exit 1; }
done

# production leaf env for the CHAMPION (opponent) side — the INTACT v2.9.2 champion.
# ** curve125 = the ADOPTED champion (v2_9_2_Bmild_cap8_curve125). Hash a36d2e15a3b3d71d. **
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
# ⚠️ OPENBLAS too — the C5 curve ladder's "x1.75 hang" was root-caused (e006036) to OpenBLAS
# thread oversubscription: the canon env pinned OMP/MKL but NOT this, so every worker spawned
# a 32-thread busy-wait pool. Free insurance and result-neutral (clair games barely touch BLAS).
export OPENBLAS_NUM_THREADS=1
cd $REPO || exit 1
HOST=$(hostname)
ts() { date +%F_%T; }

# ---- CLOCK-SKEW GUARD (added 2026-07-30 after this bit us live) --------------------------
# carcassonne_ai/claim.py:is_stale() compares the claim file's CIFS mtime (the SERVER's clock —
# here the Windows host that exports /mnt/c) against the CLIENT's time.time(). A client whose
# clock runs FAST by more than --claim-stale-secs therefore sees EVERY claim on the share as
# stale — including claims a sibling box is actively working — and steals them all instead of
# picking up unclaimed work. Failure shape observed 2026-07-30 23:26: the laptop's WSL2 clock
# had drifted +11697 s (3h15m) after a host sleep; within 3 minutes ALL 16 of the local box's
# fresh claims had been re-owned by the laptop, so both boxes were computing the SAME seeds and
# two-box work-stealing was silently worth ~1 box. Nothing crashes and nothing warns — the
# duplicate work is "harmless" by claim.py's own contract, so it only shows up as missing
# throughput. Refuse to start rather than run at half speed for a night.
probe="$OUT_ROOT/.clock_probe_$$"
mkdir -p "$OUT_ROOT" && : > "$probe" 2>/dev/null
if [ -f "$probe" ]; then
  skew=$(( $(date +%s) - $(stat -c %Y "$probe") ))
  rm -f "$probe"
  askew=${skew#-}
  if [ "$askew" -gt 60 ]; then
    echo "[abl $ROLE $HOST $(ts)] FATAL: clock skew vs the share's mtime clock = ${skew}s (>60s)."
    echo "  This box would treat sibling boxes' live claims as stale and steal them (claim.py:is_stale"
    echo "  compares SERVER mtime to CLIENT time.time()). Fix the clock, then relaunch, e.g.:"
    echo "    sudo -n date -s @\$(ssh <box-with-the-share> date +%s)"
    exit 3
  fi
  echo "[abl $ROLE $HOST $(ts)] clock-skew guard OK (${skew}s vs the share)"
else
  echo "[abl $ROLE $HOST $(ts)] WARNING: could not write a clock probe to $OUT_ROOT — skew unchecked"
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
# Under a NON-walled profile the TSV also carries the RULES COLUMNS (profile, r9_ok) read
# straight off the cell's manifest — a row that cannot prove the profile applied is not a
# result. The walled schema is left exactly as F7/F7b wrote it.
tsv_line() {  # $1=cell $2=status $3=summary.json(or -) $4=secs $5=manifest.json(or -)
  if [ "$3" != "-" ] && [ -f "$3" ]; then
    $PY - "$1" "$2" "$3" "$4" "${5:--}" "$PROFILE" >> "$PROG" <<'PYEOF'
import json, os, sys, time
cell, status, path, secs, man_path, profile = sys.argv[1:7]
s = json.load(open(path))
ms = s.get("cand_prefix_ms_per_move", 0.0) / max(1e-9, s.get("champ_prefix_ms_per_move", 1.0))
pz = s.get("paired_z"); pz = float("nan") if pz is None else pz
cols = [cell, status, str(s["n"]), str(s["W"]), str(s["D"]), str(s["L"]),
        f"{s['elo']:.1f}", f"{s['elo_sig_1sigma']:.1f}", f"{pz:.2f}", f"{ms:.2f}"]
if profile != "walled":
    prof, r9 = "?", "?"
    if man_path != "-" and os.path.exists(man_path):
        rp = (json.load(open(man_path)).get("rules_profile") or {})
        prof = rp.get("name", "?")
        r9 = str(rp.get("r9_env_ok", "?")).lower()
    cols += [prof, r9]
cols += [secs, time.strftime("%F_%T")]
print("\t".join(cols))
PYEOF
  else
    extra=""; [ "$PROFILE" != walled ] && extra="-\t-\t"
    printf "%s\t%s\t-\t-\t-\t-\t-\t-\t-\t-\t%b%s\t%s\n" "$1" "$2" "$extra" "$4" "$(ts)" >> "$PROG"
  fi
}
# manifest_profile_ok <manifest.json> -> rc 0 iff it stamps THIS run's profile and r9_env_ok
manifest_profile_ok() {
  [ "$PROFILE" = walled ] && return 0
  [ -f "$1" ] || return 1
  $PY -c "import json,sys;rp=(json.load(open(sys.argv[1])).get('rules_profile') or {});
sys.exit(0 if rp.get('name')==sys.argv[2] and rp.get('r9_env_ok') is True else 1)" \
      "$1" "$PROFILE" 2>/dev/null
}

HDR="cell\tstatus\tn\tW\tD\tL\telo\tsigma\tpaired_z\tms_ratio\tsecs\ttimestamp"
[ "$PROFILE" != walled ] && HDR="cell\tstatus\tn\tW\tD\tL\telo\tsigma\tpaired_z\tms_ratio\tprofile\tr9_ok\tsecs\ttimestamp"
[ "$DRYRUN" = 0 ] && { [ -f "$PROG" ] || echo -e "$HDR" > "$PROG"; }
echo "[abl $ROLE $HOST $(ts)] start: W=$WORKERS backend=$BACKEND profile=$PROFILE r9=${CARCASSONNE_FIX_R9:-unset} out_root=$OUT_ROOT band=$BAND n=$N cells=[$CELLS]"

for c in $CELLS; do
  # The cell JSON is the WALLED-named one for every profile: a knockout is a leaf config and
  # does not depend on the rules. Only the exp_id (results.csv label) carries the profile.
  cell_json="$CELL_DIR/abl_${c}_vs_puctchamp2750_k2.json"
  exp="abl_${c}${EXP_PROF}_vs_puctchamp2750_k2"
  sub="${SUBPREFIX}$c"
  dir="$OUT_ROOT/$sub"
  base_args=(--candidate puct --opponent puct
             --c-puct $CPUCT --tau-p $TAU --leaf-quantize $QUANT --final-select $SELECT
             --cand-sims $SIMS --exact-k $K --n $N --paired --backend "$BACKEND"
             --rules-profile "$PROFILE"
             --cand-leaf-json "$cell_json" --exp-id "$exp"
             --seed-start $BAND --out-root "$OUT_ROOT" --out-subdir "$sub")
  # The per-wave harness calls always pass --no-results-csv; only the primary's
  # AGGREGATE call writes the row. --smoke suppresses that too — otherwise a smoke
  # through this launcher banks a real results.csv row for the real exp_id off a
  # throwaway band, which is exactly the disorganisation results.csv exists to stop.
  agg_args=("${base_args[@]}")
  [ "$SMOKE" = 1 ] && agg_args+=(--no-results-csv)
  if [ "$DRYRUN" = 1 ]; then
    echo "[dry-run] $exp -> nice -n 19 $PY $HARNESS ${base_args[*]} --workers $WORKERS" \
         "--shared-claim --claim-host abl-$ROLE-$HOST --claim-stale-secs 300 --no-results-csv"
    continue
  fi
  mkdir -p "$dir"
  t0=$(date +%s)

  # resume: a cell with a COMPLETE summary.json is done — but primary re-checks the
  # results.csv row (crash-between-summary-and-row recovery; aggregate replays 0 games).
  if cell_complete "$dir"; then
    if [ "$ROLE" = primary ] && ! grep -q "^$exp," "$REPO/experiments/results.csv"; then
      echo "[abl $(ts)] $exp complete but results.csv row missing -> re-aggregate"
      nice -n 19 $PY "$HARNESS" "${agg_args[@]}" > "/tmp/abl_agg_${c}.log" 2>&1
    fi
    tsv_line "$c" cached "$dir/summary.json" 0 "$dir/manifest.json"
    echo "[abl $ROLE $(ts)] cell $exp CACHED ($(count_results "$dir")/$N) -> skip"
    continue
  fi

  # primary force-cleans ALL orphan claims at cell start (killed-run recovery)
  [ "$ROLE" = primary ] && clean_stale_claims "$dir" ""
  echo "[abl $ROLE $(ts)] cell $exp start ($(count_results "$dir")/$N cached)"
  iter=0
  while [ "$(count_results "$dir")" -lt "$N" ] && [ $iter -lt 60 ]; do
    nice -n 19 $PY "$HARNESS" "${base_args[@]}" \
      --workers "$WORKERS" --shared-claim --claim-host "abl-$ROLE-$HOST" --claim-stale-secs 300 \
      --no-results-csv > "/tmp/abl_${ROLE}_${c}.log" 2>&1
    clean_stale_claims "$dir" 4
    iter=$((iter+1))
    [ "$(count_results "$dir")" -lt "$N" ] && sleep 5
  done
  secs=$(( $(date +%s) - t0 ))
  if [ "$(count_results "$dir")" -lt "$N" ]; then
    tsv_line "$c" STALLED - "$secs" -
    echo "[abl $ROLE $(ts)] cell $exp STALLED at $(count_results "$dir")/$N -> next cell (NO row written)"
    continue
  fi
  # F7c fail-loud: a non-walled cell whose manifest does not stamp THIS profile with
  # r9_env_ok=true is VOID — do not let it into results.csv under a fixed_v1 exp_id.
  if ! manifest_profile_ok "$dir/manifest.json"; then
    tsv_line "$c" VOID-PROFILE - "$secs" -
    echo "[abl $ROLE $(ts)] cell $exp VOID: manifest.json does not stamp profile=$PROFILE + r9_env_ok=true (NO row written)"
    continue
  fi
  if [ "$ROLE" = primary ]; then
    nice -n 19 $PY "$HARNESS" "${agg_args[@]}" > "/tmp/abl_agg_${c}.log" 2>&1
    tsv_line "$c" DONE "$dir/summary.json" "$secs" "$dir/manifest.json"
    echo "[abl primary $(ts)] cell $exp DONE in ${secs}s -> $(tail -1 "$PROG")"
  else
    tsv_line "$c" helper-done - "$secs" -
    echo "[abl helper $(ts)] cell $exp games reached $N in ${secs}s (primary aggregates)"
  fi
done
echo "[abl $ROLE $HOST $(ts)] ALL CELLS PROCESSED"
[ "$ROLE" = primary ] && [ "$DRYRUN" = 0 ] && { echo "=== LEAF ABLATION PROGRESS ==="; cat "$PROG"; }
exit 0
