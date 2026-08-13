#!/bin/bash
# OPEN-CITY DISCIPLINE — DEPLOY-BUDGET CELLS. LAPTOP-ONLY, SEQUENTIAL DRIVER.
# Prereg: measurement/opencity_term_20260812/DEPLOY_PREREG.md
#
# TWO cells, run ONE AFTER THE OTHER on this box (the local 5900XT box is running the
# Joshua-bot tournament at W30 and is unavailable):
#   1. A_d0p5  cand = champion leaf + opencity dose 0.5 / size_min 4 TILES / edge_min 2 /
#              symmetric  (cand_leaf_hash c128083fb485d20d)   seeds <band>+0   .. +399
#   2. A_d2p0  same predicate at dose 2.0 (cand_leaf_hash 2cf0b7507e6a0921)
#                                                             seeds <band>+400 .. +799
#   opponent BOTH cells = the unmodified production champion a36d2e15a3b3d71d.
#   BOTH ARMS of BOTH cells at the DEPLOY budget k8x1376 = 11008 via eval_fair_puct.py.
#   THE TWO CELLS DO NOT SHARE DECKS (disjoint seed ranges) -- there is no A-vs-B statistic.
#
# ADJUDICATES NOTHING. No promotion, no PRODUCTION.yaml, no results.csv row, no claim row.
#
# ⚠️ DELIBERATELY DOES NOT RUN menu_block_summary.py. DEPLOY_PREREG.md §4 rule 7 requires the
#    wiring gates O1-O12 to be read from the manifest BEFORE the strength summary is opened.
#    So this driver emits GATES_<cell>.json -- pass/fail ONLY, no strength number anywhere in
#    it -- and leaves the summary to the reading session. That ordering is the point.
#
# Pre-flight gates that ran BEFORE this script was launched (recorded in the prereg §3):
#   tree identity src/engine/rust with the local repo · sha256 identity of the six
#   load-bearing scripts · O0 _leaf_hash(cell json) == expected and != champion, computed ON
#   THIS BOX · chain_capability_probe.py --require opencity --doses 0.5,2.0 PASS on THIS BOX.
#
# Usage (launched detached from the orchestrating session):
#   setsid nohup systemd-run --user --scope -p MemoryMax=8G \
#     nice -n 19 bash .../run_deploy_opencity_laptop.sh <BAND> > driver.log 2>&1 < /dev/null &
#
# RESUMABLE: re-running it skips any cell that already has its DONE marker, and menu_fair_cell
# itself resumes from the seed*.json records already on the share.
set -u
BAND="${1:?usage: run_deploy_opencity_laptop.sh <BAND_SEED_START>}"
case "$BAND" in ''|*[!0-9]*) echo "BAND must be numeric, got '$BAND'"; exit 2 ;; esac

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
DIR=$REPO/measurement/opencity_term_20260812
LOGS=$DIR/deploy_logs
OUT=/mnt/carc-shared/opencity_deploy_20260813     # LAPTOP mount prefix (local reads /mnt/c/...)
W=${W_LAPTOP:-22}
N=${N:-800}
CHAMP_HASH=a36d2e15a3b3d71d

mkdir -p "$LOGS" "$DIR/verdicts" "$OUT"
ts() { date +%F_%T; }
log() { echo "[opencity-deploy $(ts)] $*"; }

# cell_name : seed_offset : cand_leaf_json : expected_cand_leaf_hash : expected_dose
CELLS=(
  "opencity_A_d0p5_deploy11008:0:$DIR/cells/opencity_A_d0p5_deploy_fixed_v1_vs_fairchamp11008.json:c128083fb485d20d:0.5"
  "opencity_A_d2p0_deploy11008:400:$DIR/cells/opencity_A_d2p0_deploy_fixed_v1_vs_fairchamp11008.json:2cf0b7507e6a0921:2.0"
)

log "=== START band=$BAND W=$W n=$N per cell, SEQUENTIAL, laptop-only ==="
log "host=$(hostname) out=$OUT repo_head=$(git -C $REPO rev-parse --short HEAD)"

for spec in "${CELLS[@]}"; do
  SUB=${spec%%:*};       rest=${spec#*:}
  OFF=${rest%%:*};       rest=${rest#*:}
  CELLJSON=${rest%%:*};  rest=${rest#*:}
  EXPECT_HASH=${rest%%:*}
  EXPECT_DOSE=${rest##*:}
  SEED=$((BAND + OFF))

  if [ -f "$DIR/DONE_$SUB" ]; then
    log "cell $SUB already DONE (marker present) -- skipping"
    continue
  fi
  [ -f "$CELLJSON" ] || { log "!!! FAILED $SUB: missing cell json $CELLJSON"
    { echo "$(ts)"; echo "missing cell json $CELLJSON"; } > "$DIR/FAILED_$SUB"; exit 10; }

  log "--- cell $SUB  seeds $SEED..$((SEED + N/2 - 1))  cand_hash=$EXPECT_HASH dose=$EXPECT_DOSE ---"
  mkdir -p "$OUT/$SUB"
  MENU_OUT_ROOT=$OUT nice -n 19 bash "$REPO/scripts/classical_search/menu_fair_cell.sh" "$W" laptop \
      --sub "$SUB" --n "$N" --band "$SEED" \
      --k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376 \
      --cand-leaf-json "$CELLJSON" --drift > "$LOGS/cell_$SUB.log" 2>&1
  rc=$?
  GOT=$(find "$OUT/$SUB" -maxdepth 1 -name 'seed*.json' | wc -l)
  log "cell $SUB launcher rc=$rc records=$GOT/$N"

  # ---- wiring gates from the manifest. PASS/FAIL ONLY -- no strength number is read here.
  MANIFEST="$OUT/$SUB/manifest.json" \
  EXPECT_HASH="$EXPECT_HASH" EXPECT_DOSE="$EXPECT_DOSE" EXPECT_SEED="$SEED" \
  EXPECT_N="$N" GOT_N="$GOT" CHAMP_HASH="$CHAMP_HASH" SUB="$SUB" \
  $PY - > "$DIR/verdicts/GATES_$SUB.json" 2>"$LOGS/gates_$SUB.log" <<'PYEOF'
import json, os, sys
m = json.load(open(os.environ["MANIFEST"]))
c = m.get("config", {})
rp = m.get("rules_profile") or {}
le = m.get("leaf_env") or {}
cl = c.get("cand_leaf_cfg") or {}
ol = c.get("opp_leaf_cfg") or {}
ch = c.get("champion") or {}
op = c.get("opponent") or {}
eg = c.get("endgame") or {}
be = c.get("backend") or {}
cd = c.get("cand_curve_drift") or {}
CURVE125 = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]
g, res = [], True
def chk(n, ok, got):
    global res
    res &= bool(ok); g.append({"gate": n, "ok": bool(ok), "observed": got})
chk("O1_cand_leaf_hash", c.get("cand_leaf_hash") == os.environ["EXPECT_HASH"], c.get("cand_leaf_hash"))
chk("O1b_cand_hash_is_not_champion", c.get("cand_leaf_hash") != os.environ["CHAMP_HASH"], c.get("cand_leaf_hash"))
chk("O2_opp_leaf_hash", c.get("opp_leaf_hash") == os.environ["CHAMP_HASH"], c.get("opp_leaf_hash"))
chk("O3_cand_opencity_dose_LIVE", float(cl.get("opencity_dose", 0.0)) == float(os.environ["EXPECT_DOSE"]),
    cl.get("opencity_dose"))
chk("O4_cand_thresholds_are_armA_defaults",
    not any(k in cl for k in ("opencity_size_min", "opencity_edge_min", "opencity_symmetric")),
    {k: v for k, v in cl.items() if k.startswith("opencity")})
chk("O5_opponent_leaf_intact", not any(k.startswith("opencity") for k in ol),
    {k: v for k, v in ol.items() if k.startswith("opencity")})
chk("O6_rules_profile_fixed_v1_R9",
    rp.get("name") == "fixed_v1" and rp.get("r9_env_ok") is True and le.get("CARCASSONNE_FIX_R9") == "1",
    [rp.get("name"), rp.get("r9_env_ok"), le.get("CARCASSONNE_FIX_R9")])
chk("O7_cand_budget_8x1376_11008",
    (ch.get("k_dets"), ch.get("sims_per_det"), ch.get("total_sims")) == (8, 1376, 11008),
    [ch.get("k_dets"), ch.get("sims_per_det"), ch.get("total_sims")])
chk("O8_opp_budget_8x1376_11008",
    (op.get("k_dets"), op.get("sims_per_det"), op.get("total_sims")) == (8, 1376, 11008),
    [op.get("k_dets"), op.get("sims_per_det"), op.get("total_sims")])
chk("O9_curve_drift_is_curve125",
    c.get("cand_curve_drift_allowed") is True and list(cd.get("curve_values") or []) == CURVE125,
    [c.get("cand_curve_drift_allowed"), cd.get("curve_values")])
chk("O10_band_and_pairing",
    (c.get("band_seed_start"), c.get("n_decks"), c.get("seatings_per_deck"))
    == (int(os.environ["EXPECT_SEED"]), int(os.environ["EXPECT_N"]) // 2, 2),
    [c.get("band_seed_start"), c.get("n_decks"), c.get("seatings_per_deck")])
chk("O11_rust_exactk2_shared",
    be.get("requested") == "rust" and eg.get("exact_k") == 2 and eg.get("shared_by_both_arms") is True,
    [be.get("requested"), eg.get("exact_k"), eg.get("shared_by_both_arms")])
got_n, exp_n = int(os.environ["GOT_N"]), int(os.environ["EXPECT_N"])
chk("O12_completion_ge_90pct", got_n >= 0.9 * exp_n, f"{got_n}/{exp_n}")
json.dump({"cell": os.environ["SUB"], "all_gates_pass": res, "records": f"{got_n}/{exp_n}",
           "gates": g, "note": "WIRING ONLY -- contains no strength statistic by design "
                               "(DEPLOY_PREREG.md section 4 rule 7)."},
          sys.stdout, indent=2)
sys.stdout.write("\n")
PYEOF
  grc=$?
  GPASS=$($PY -c "import json;print(json.load(open('$DIR/verdicts/GATES_$SUB.json'))['all_gates_pass'])" 2>/dev/null || echo "UNREADABLE")
  log "cell $SUB wiring gates: all_gates_pass=$GPASS (gate-script rc=$grc) -> $DIR/verdicts/GATES_$SUB.json"

  MIN=$(( N * 9 / 10 ))
  if [ "$GOT" -ge "$MIN" ]; then
    { echo "$(ts)"; echo "records $GOT/$N"; echo "band_seed_start $SEED";
      echo "cand_leaf_hash_expected $EXPECT_HASH"; echo "opencity_dose_expected $EXPECT_DOSE";
      echo "workers $W (laptop only)"; echo "wiring_gates_all_pass $GPASS";
      echo "NOT ADJUDICATED - read DEPLOY_PREREG.md gates O1-O12 before any number."; } > "$DIR/DONE_$SUB"
    log "cell $SUB DONE ($GOT/$N) -> $DIR/DONE_$SUB"
    [ "$GOT" -lt "$N" ] && log "cell $SUB INCOMPLETE but >=90% - the 90% VOID rule applies at read time"
  else
    { echo "$(ts)"; echo "records $GOT/$N (<90%) - VOID by the standing rule";
      echo "launcher rc=$rc"; echo "see $LOGS/cell_$SUB.log"; } > "$DIR/FAILED_$SUB"
    log "!!! cell $SUB FAILED ($GOT/$N < 90%) -> $DIR/FAILED_$SUB. STOPPING; the second cell is NOT started."
    exit 11
  fi
done

: > "$DIR/DONE_DEPLOY_OPENCITY"
log "=== ALL CELLS COMPLETE (band $BAND). Nothing adjudicated, nothing promoted. ==="
