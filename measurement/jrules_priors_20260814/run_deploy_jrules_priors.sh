#!/bin/bash
# J-RULES SURFACE B (POLICY PRIORS) — DEPLOY-BUDGET CELL. BOX-PARAMETERIZED DRIVER.
# Prereg of record: measurement/jrules_priors_20260814/DEPLOY_PREREG.md (commit fb6cc09e,
# committed BEFORE game 1). Cell spec: cells/jpriors_d0p5_deploy11008.json.
#
# Usage (launched DETACHED by the orchestrator):
#   local:  setsid nohup nice -n 19 bash \
#             /home/doctor/projects/carcassone/measurement/jrules_priors_20260814/run_deploy_jrules_priors.sh \
#             local 130000000000 30 > .../driver_local.log 2>&1 < /dev/null & disown
#
# ONE cell, n=800 deck-paired (400 decks x 2 seats, CRN), fair PIMC via eval_fair_puct.py,
# BOTH arms at the deploy budget k8x1376 = 11008, fixed_v1 + R9, rust both sides, exact-K 2
# shared. Candidate = the production champion with --cand-jrules-prior-dose 0.5 (mask 31,
# scope all). Opponent = the UNMODIFIED production champion.
#
# ADJUDICATES NOTHING. No promotion, no PRODUCTION.yaml, no results.csv row, no claim row.
#
# ⚠️ DELIBERATELY DOES NOT RUN menu_block_summary.py. The 13 wiring gates must be read from
#    the manifest BEFORE any strength number is opened (DEPLOY_PREREG §6). This driver emits
#    verdicts/GATES_<cell>.json -- pass/fail ONLY -- and leaves the summary to the reading
#    session.
#
# ⚠️⚠️ WHY THIS DRIVER CALLS eval_fair_puct.py DIRECTLY INSTEAD OF menu_fair_cell.sh.
#    menu_fair_cell.sh has no --cand-jrules-prior-* passthrough, and at build time the LAPTOP
#    was mid-flight on a live n=800 cell that re-imports that script from this same repo on
#    every resume pass. Editing it was therefore forbidden (worktree-isolation rule). The env
#    canon, clock-skew guard, claim hygiene and resume loop below are lifted from
#    menu_fair_cell.sh VERBATIM so this cell runs under identical conditions to its siblings;
#    the ONLY additions are the three surface-B flags and the pre-flight gate.
#
# ⚠️⚠️⚠️ THE LIVENESS GATE IS INVERTED FOR THIS SURFACE — THE SINGLE EASIEST WAY TO PRODUCE A
#    MEANINGLESS NULL. Surface-B knobs are SearchConfig, NOT LeafConfig, so NO LEAF HASH
#    MOVES: the candidate's leaf hash must EQUAL the champion's a36d2e15a3b3d71d, and a MOVED
#    hash is a DEFECT (a leaf change smuggled into a prior cell). Nothing about a hash can
#    prove this term live. Liveness rests entirely on:
#      (J4)  the RESOLVED config.cand_jrules_prior.dose in the manifest, and
#      (J13) preflight_surface_b.py / _assert_surface_b_live -- run BELOW, BEFORE game 1, on
#            this box, with its output captured under verdicts/. If it fails, THIS DRIVER
#            REFUSES TO PLAY: without it a zeroed dose grades a perfect champion-vs-champion
#            null wearing the exact shape of a real cell.
#
# RESUMABLE: re-running skips the cell if its DONE marker is present; otherwise the harness
# resumes from the seed*.json records on the share. The pre-flight re-runs on every attempt
# (per-box wheel guard); the FIRST attempt's verdict is preserved for gate J13.
set -u
BOX="${1:?usage: run_deploy_jrules_priors.sh <local|laptop> <BAND_SEED_START> [W]}"
BAND="${2:?usage: run_deploy_jrules_priors.sh <local|laptop> <BAND_SEED_START> [W]}"
case "$BAND" in ''|*[!0-9]*) echo "BAND must be numeric, got '$BAND'"; exit 2 ;; esac

case "$BOX" in
  local)  SHARE=/mnt/c/carc-shared; ROLE=primary; W_DEFAULT=30 ;;   # 5900XT-box mount prefix
  laptop) SHARE=/mnt/carc-shared;   ROLE=helper;  W_DEFAULT=22 ;;   # laptop-wsl mount prefix
  *) echo "BOX must be local|laptop, got '$BOX'"; exit 2 ;;
esac
W="${3:-${W:-$W_DEFAULT}}"

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_fair_puct.py
DIR=$REPO/measurement/jrules_priors_20260814
LOGS=$DIR/deploy_logs
OUT=$SHARE/jrules_priors_deploy_20260814
SUB=jpriors_d0p5_deploy11008
CELLSPEC=$DIR/cells/$SUB.json
N=${N:-800}
MAXITER=${MAXITER:-60}
CHAMP_HASH=a36d2e15a3b3d71d
DOSE=0.5
MASK=31
SCOPE=all

mkdir -p "$LOGS" "$DIR/verdicts" "$OUT/$SUB"
ts() { date +%F_%T; }
log() { echo "[jp-b-deploy $(ts)] $*"; }
dir="$OUT/$SUB"

# ---- canonical leaf env (VERBATIM from menu_fair_cell.sh): the INTACT v2.9.2 curve125
# champion (hash a36d2e15a3b3d71d). This cell injects NO leaf override on either side, so
# BOTH arms resolve their leaf from exactly this env.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
# ⚠️ R9 is env-latched at IMPORT, so it MUST be exported before the harness process starts.
export CARCASSONNE_FIX_R9=1
cd "$REPO" || exit 1
HOST=$(hostname)

log "=== START box=$BOX band=$BAND W=$W n=$N cell=$SUB ==="
log "host=$HOST out=$dir repo_head=$(git -C $REPO rev-parse --short HEAD)"
log "knob: --cand-jrules-prior-dose $DOSE --cand-jrules-prior-mask $MASK --cand-jrules-prior-scope $SCOPE (CANDIDATE side only; NO --cand-leaf-json)"

[ -f "$CELLSPEC" ] || { log "!!! missing cell spec $CELLSPEC"; exit 9; }
if [ -f "$DIR/DONE_$SUB" ]; then
  log "cell $SUB already DONE (marker present) -- nothing to do"; exit 0
fi

# ==========================================================================
# PRE-FLIGHT (prereg gate J13) — BEFORE GAME 1, ON THIS BOX. HARD BLOCKER.
# Verifies the installed carc_rs wheel carries the surface-B prior knobs AND runs the
# positive control _assert_surface_b_live (dose 1.0 must move the expansion priors on a
# pinned root). No hash check can substitute for this on surface B.
# ==========================================================================
PF_NOW="$DIR/verdicts/PREFLIGHT_${SUB}_${HOST}_$(date +%s).json"
PF_FIRST="$DIR/verdicts/PREFLIGHT_${SUB}_${HOST}_FIRST.json"
log "--- PRE-FLIGHT (wheel + _assert_surface_b_live positive control) on $HOST ---"
PREFLIGHT_DOSE=$DOSE PREFLIGHT_MASK=$MASK PREFLIGHT_SCOPE=$SCOPE \
  nice -n 19 $PY "$DIR/preflight_surface_b.py" > "$PF_NOW" 2>"$LOGS/preflight_$SUB.log"
pfrc=$?
cat "$PF_NOW"
if [ "$pfrc" -ne 0 ]; then
  log "!!! PRE-FLIGHT FAILED (rc=$pfrc) on $HOST -- see $PF_NOW and $LOGS/preflight_$SUB.log"
  log "!!! REFUSING TO PLAY. A dead prior surface grades a champion-vs-champion null that no"
  log "!!! wiring gate on this surface could ever detect. Rebuild the carc_rs wheel on THIS box."
  { echo "$(ts)"; echo "PRE-FLIGHT FAILED rc=$pfrc on $HOST"; echo "see $PF_NOW"; } > "$DIR/FAILED_$SUB"
  exit 13
fi
[ -f "$PF_FIRST" ] || cp "$PF_NOW" "$PF_FIRST"
log "PRE-FLIGHT PASS on $HOST (all_preflight_pass=true) -> $PF_NOW ; first-attempt copy $PF_FIRST"

# ==========================================================================
# CLOCK-SKEW GUARD (VERBATIM from menu_fair_cell.sh). claim.py:is_stale() compares the
# SHARE's mtime clock against this client's time.time(); a drifted client sees every sibling
# claim as stale and STEALS it, silently halving throughput with no error.
# ==========================================================================
probe="$OUT/.clock_probe_$$"
: > "$probe" 2>/dev/null
if [ -f "$probe" ]; then
  skew=$(( $(date +%s) - $(stat -c %Y "$probe") )); rm -f "$probe"; askew=${skew#-}
  if [ "$askew" -gt 60 ]; then
    log "FATAL: clock skew vs the share = ${skew}s (>60s). Fix with: sudo -n date -s @\$(...)"
    exit 3
  fi
  log "clock-skew guard OK (${skew}s)"
else
  log "WARNING: could not write a clock probe to $OUT - skew unchecked"
fi

count_records() { find "$1" -maxdepth 1 -name 'seed*.json' 2>/dev/null | wc -l; }
# Claims-without-records only, and only ones older than $2 minutes, so a claim taken seconds
# ago by a sibling is never swept.
clean_stale_claims() {
  local d="$1" age="${2:-}"; local a=(-maxdepth 1 -name 'seed*.claim')
  [ -n "$age" ] && a+=(-mmin "+$age")
  find "$d" "${a[@]}" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}

args=(--info fair --opponent fair-champion --backend rust
      --k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376 --exact-k 2
      --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
      --n "$N" --paired --seed-start "$BAND"
      --rules-profile fixed_v1 --workers "$W"
      --out-root "$OUT" --out-subdir "$SUB"
      --shared-claim --claim-host "jpriors-$ROLE-$HOST" --claim-stale-secs 900
      --no-results-csv
      --cand-jrules-prior-dose "$DOSE"
      --cand-jrules-prior-mask "$MASK"
      --cand-jrules-prior-scope "$SCOPE")
log "harness argv: $PY -u $HARNESS ${args[*]}"

clean_stale_claims "$dir" 10
t0=$(date +%s); iter=0
while [ "$(count_records "$dir")" -lt "$N" ] && [ "$iter" -lt "$MAXITER" ]; do
  nice -n 19 $PY -u "$HARNESS" "${args[@]}" >> "$LOGS/cell_$SUB.log" 2>&1
  # ⚠️ CAPTURE rc ON ITS OWN LINE (a `$(ts)` in the same echo clobbers $?; cost 2 h once).
  rc=$?
  iter=$((iter+1))
  log "harness pass $iter rc=$rc records=$(count_records "$dir")/$N"
  clean_stale_claims "$dir" 10
  [ "$(count_records "$dir")" -lt "$N" ] && sleep 15
done
secs=$(( $(date +%s) - t0 ))
GOT=$(count_records "$dir")
log "cell $SUB END records=$GOT/$N in ${secs}s after $iter pass(es)"

# ==========================================================================
# THE 13 WIRING GATES (DEPLOY_PREREG.md §6 N0). PASS/FAIL ONLY -- no strength number is
# read here, by design. ⚠️ J1 IS AN EQUALITY GATE: the candidate leaf hash must EQUAL the
# champion's. This is INVERTED relative to every leaf-term cell and is not a typo.
# ==========================================================================
MANIFEST="$dir/manifest.json" RECDIR="$dir" \
CHAMP_HASH="$CHAMP_HASH" EXPECT_DOSE="$DOSE" EXPECT_MASK="$MASK" EXPECT_SCOPE="$SCOPE" \
EXPECT_SEED="$BAND" EXPECT_N="$N" GOT_N="$GOT" SUB="$SUB" \
PREFLIGHT="$PF_FIRST" ELAPSED="$secs" WORKERS="$W" BOX="$BOX" \
$PY - > "$DIR/verdicts/GATES_$SUB.json" 2>"$LOGS/gates_$SUB.log" <<'PYEOF'
import glob, json, os, sys

MAN = os.environ["MANIFEST"]
m = json.load(open(MAN))
c = m.get("config", {})
rp = m.get("rules_profile") or {}
le = m.get("leaf_env") or {}
cl = c.get("cand_leaf_cfg") or {}
ol = c.get("opp_leaf_cfg") or {}
ch = c.get("champion") or {}
op = c.get("opponent") or {}
eg = c.get("endgame") or {}
be = c.get("backend") or {}
jp = c.get("cand_jrules_prior") or {}
CHAMP = os.environ["CHAMP_HASH"]

g, res = [], True
def chk(n, ok, got, note=None):
    global res
    res &= bool(ok)
    row = {"gate": n, "ok": bool(ok), "observed": got}
    if note:
        row["note"] = note
    g.append(row)

# ---- J1: ⚠️ INVERTED. EQUALITY, not inequality. Surface B moves NO leaf hash; a DIFFERING
#      hash means a leaf change was smuggled into a prior cell => VOID.
chk("J1_INVERTED_cand_leaf_hash_EQUALS_champion",
    c.get("cand_leaf_hash") == CHAMP, c.get("cand_leaf_hash"),
    "EQUALITY GATE. A MOVED hash is a DEFECT on this surface, not evidence of a live term.")
chk("J2_opp_leaf_hash_EQUALS_champion", c.get("opp_leaf_hash") == CHAMP, c.get("opp_leaf_hash"))
chk("J3_cand_leaf_json_is_null", c.get("cand_leaf_json") is None, c.get("cand_leaf_json"))

# ---- J4: THE LIVENESS GATE. The resolved dose in the manifest is the ONLY manifest field
#      that can prove this term ran. Nonzero AND equal to the funded dose.
_dose = jp.get("dose")
chk("J4_LIVENESS_cand_jrules_prior_dose",
    _dose is not None and float(_dose) == float(os.environ["EXPECT_DOSE"]) and float(_dose) != 0.0,
    {"cand_jrules_prior": jp, "expected_dose": float(os.environ["EXPECT_DOSE"])},
    "THE liveness gate. No hash on this surface can substitute for it (see also J13).")
chk("J5_cand_jrules_prior_mask",
    jp.get("mask") is not None and int(jp["mask"]) == int(os.environ["EXPECT_MASK"]), jp.get("mask"))
chk("J6_cand_jrules_prior_scope", jp.get("scope") == os.environ["EXPECT_SCOPE"], jp.get("scope"))

# ---- J7: no jrules_* key rode into the candidate LEAF, and no jrules* key of ANY kind
#      (static bundle or prior knob) sits on the opponent side.
cand_leaf_jr = {k: v for k, v in cl.items() if "jrules" in k}
opp_jr = {k: v for k, v in ol.items() if "jrules" in k}
opp_cfg_jr = {k: v for k, v in c.items() if "jrules" in k and k != "cand_jrules_prior"}
chk("J7_no_jrules_on_cand_leaf_or_anywhere_on_opponent",
    not cand_leaf_jr and not opp_jr and not opp_cfg_jr,
    {"cand_leaf_cfg": cand_leaf_jr, "opp_leaf_cfg": opp_jr, "other_config": opp_cfg_jr})

# ---- J8: budget on BOTH sides, read as NUMBERS (never the equal_wall_clock_note prose --
#      MANIFEST_LABEL_TRAPS applies).
chk("J8_both_budgets_8x1376_11008",
    (ch.get("k_dets"), ch.get("sims_per_det"), ch.get("total_sims")) == (8, 1376, 11008)
    and (op.get("k_dets"), op.get("sims_per_det"), op.get("total_sims")) == (8, 1376, 11008),
    {"champion": [ch.get("k_dets"), ch.get("sims_per_det"), ch.get("total_sims")],
     "opponent": [op.get("k_dets"), op.get("sims_per_det"), op.get("total_sims")]})

chk("J9_rules_fixed_v1_R9",
    rp.get("name") == "fixed_v1" and rp.get("r9_env_expected") is True
    and le.get("CARCASSONNE_FIX_R9") == "1",
    {"name": rp.get("name"), "r9_env_expected": rp.get("r9_env_expected"),
     "r9_env_observed": rp.get("r9_env_observed"), "r9_env_ok": rp.get("r9_env_ok"),
     "leaf_env.CARCASSONNE_FIX_R9": le.get("CARCASSONNE_FIX_R9")})

chk("J10_backend_rust", be.get("requested") == "rust",
    {"requested": be.get("requested"), "name": be.get("name"),
     "converted_sides": be.get("converted_sides")})

# ---- J11: 800 records, 800 unique (deck seed, seat), 0 missing, 0 extra, 400 decks fully
#      paired, and every seed inside the claimed band.
recs, bad = [], []
for p in glob.glob(os.path.join(os.environ["RECDIR"], "seed*.json")):
    try:
        recs.append(json.load(open(p)))
    except Exception as e:
        bad.append(f"{os.path.basename(p)}: {type(e).__name__}")
band0 = int(os.environ["EXPECT_SEED"])
exp_n = int(os.environ["EXPECT_N"])
exp_decks = exp_n // 2
pairs = {}
for r in recs:
    pairs[(r.get("seed"), r.get("a_seat"))] = pairs.get((r.get("seed"), r.get("a_seat")), 0) + 1
seat_count = {}
for (s, _a) in pairs:
    seat_count[s] = seat_count.get(s, 0) + 1
expected_pairs = {(band0 + i, a) for i in range(exp_decks) for a in (0, 1)}
missing = expected_pairs - set(pairs)
extra = set(pairs) - expected_pairs
dups = [k for k, v in pairs.items() if v > 1]
chk("J11_records_800_unique_pairs_400_decks_fully_paired",
    len(recs) == exp_n and len(pairs) == exp_n and not missing and not extra and not dups
    and not bad and sum(1 for v in seat_count.values() if v == 2) == exp_decks,
    {"records": len(recs), "unique_pairs": len(pairs), "missing": len(missing),
     "extra": len(extra), "dup_keys": len(dups), "unreadable": bad[:5],
     "fully_paired_decks": sum(1 for v in seat_count.values() if v == 2),
     "band": [band0, band0 + exp_decks - 1]})

# ---- J12: SURROGATE variant-id (eval_fair_puct emits no variant_id field -- learned from
#      surface A). ONE manifest, and every record agreeing on the identity tuple.
AGREE = ("sims", "k_dets", "exact_k", "opponent", "info", "rung_sims")
tuples = {tuple(r.get(k) for k in AGREE) for r in recs}
n_manifests = len(glob.glob(os.path.join(os.environ["RECDIR"], "manifest*.json")))
chk("J12_one_manifest_and_records_agree",
    n_manifests == 1 and len(tuples) == 1,
    {"n_manifests": n_manifests, "distinct_identity_tuples": len(tuples),
     "keys": list(AGREE), "tuples": [list(t) for t in sorted(tuples, key=str)[:4]]})

# ---- J13: the surface-B POSITIVE CONTROL ran and PASSED on this box BEFORE game 1.
#      The per-box stale-wheel / zeroed-dose guard that no hash can provide here.
pf_path = os.environ["PREFLIGHT"]
try:
    pf = json.load(open(pf_path))
    pf_ok = bool(pf.get("all_preflight_pass"))
    p1 = next((x for x in pf.get("checks", []) if x["check"].startswith("P1_")), None)
    pf_ok &= bool(p1 and p1.get("ok"))
    # "before game 1": the first-attempt pre-flight verdict predates the oldest record.
    rec_files = glob.glob(os.path.join(os.environ["RECDIR"], "seed*.json"))
    before = bool(rec_files) and os.path.getmtime(pf_path) <= min(os.path.getmtime(f) for f in rec_files)
    chk("J13_positive_control_passed_before_game1", pf_ok and before,
        {"preflight": os.path.basename(pf_path), "all_preflight_pass": pf.get("all_preflight_pass"),
         "P1": (p1 or {}).get("observed"), "predates_first_record": before,
         "host": pf.get("host")},
        "_assert_surface_b_live. Without this a zeroed dose grades a perfect "
        "champion-vs-champion null wearing the shape of a real cell.")
except Exception as e:
    chk("J13_positive_control_passed_before_game1", False, f"{type(e).__name__}: {e}")

# ---- REPORTED, NOT GATED: the N5 validity input and the run's own conditions. No strength
#      statistic appears anywhere in this file, by design.
n_failed = int(m.get("n_failed") or 0)
observed = {
    "n_failed": n_failed,
    "failure_rate": m.get("failure_rate"),
    "failed_by_seat": m.get("failed_by_seat"),
    "N5_trigger_0p5pct_exceeded": bool(n_failed > 0.005 * int(os.environ["EXPECT_N"])),
    "band_seed_start": c.get("band_seed_start"),
    "n_decks": c.get("n_decks"),
    "seatings_per_deck": c.get("seatings_per_deck"),
    "cand_curve_drift_allowed": c.get("cand_curve_drift_allowed"),
    "endgame": {"exact_k": eg.get("exact_k"), "shared_by_both_arms": eg.get("shared_by_both_arms")},
    "code_rev": m.get("code_rev"),
    "host": m.get("host"),
    "box": os.environ["BOX"],
    "workers": int(os.environ["WORKERS"]),
    "elapsed_s": int(os.environ["ELAPSED"]),
}

json.dump({"cell": os.environ["SUB"],
           "prereg": "measurement/jrules_priors_20260814/DEPLOY_PREREG.md",
           "all_gates_pass": res,
           "records": f"{int(os.environ['GOT_N'])}/{int(os.environ['EXPECT_N'])}",
           "gates": g,
           "observed_not_gated": observed,
           "note": "WIRING ONLY -- contains no strength statistic by design "
                   "(DEPLOY_PREREG.md §6 N0). ⚠️ J1 is an EQUALITY gate: surface B moves no "
                   "leaf hash, so a MOVED candidate hash is a DEFECT, not evidence."},
          sys.stdout, indent=2)
sys.stdout.write("\n")
PYEOF
grc=$?
GPASS=$($PY -c "import json;print(json.load(open('$DIR/verdicts/GATES_$SUB.json'))['all_gates_pass'])" 2>/dev/null || echo "UNREADABLE")
log "cell $SUB wiring gates: all_gates_pass=$GPASS (gate-script rc=$grc) -> $DIR/verdicts/GATES_$SUB.json"

MIN=$(( N * 9 / 10 ))
if [ "$GOT" -ge "$MIN" ]; then
  { echo "$(ts)"; echo "records $GOT/$N"; echo "band_seed_start $BAND";
    echo "cand_jrules_prior dose=$DOSE mask=$MASK scope=$SCOPE (candidate side only)";
    echo "cand_leaf_hash_expected $CHAMP_HASH  <-- EQUALITY: surface B moves NO leaf hash";
    echo "preflight_first $PF_FIRST";
    echo "workers $W (box $BOX only)"; echo "elapsed_s $secs";
    echo "wiring_gates_all_pass $GPASS";
    echo "NOT ADJUDICATED - read DEPLOY_PREREG.md gates J1-J13 before any number."; } > "$DIR/DONE_$SUB"
  log "cell $SUB DONE ($GOT/$N) -> $DIR/DONE_$SUB"
  [ "$GOT" -lt "$N" ] && log "cell $SUB INCOMPLETE but >=90% - the 90% VOID rule applies at read time"
else
  { echo "$(ts)"; echo "records $GOT/$N (<90%) - VOID by the standing rule";
    echo "see $LOGS/cell_$SUB.log"; } > "$DIR/FAILED_$SUB"
  log "!!! cell $SUB FAILED ($GOT/$N < 90%) -> $DIR/FAILED_$SUB"
  exit 11
fi

: > "$DIR/DONE_DEPLOY_JRULES_PRIORS_B"
log "=== CELL COMPLETE (band $BAND, box $BOX). Nothing adjudicated, nothing promoted. ==="
