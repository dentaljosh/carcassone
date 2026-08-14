#!/bin/bash
# OPEN-CITY ROUND 2 — DEPLOY-BUDGET CELLS. BOX-PARAMETERIZED, SEQUENTIAL DRIVER.
# Prereg: measurement/opencity_round2_20260814/DEPLOY_PREREG.md
#
# Usage (launched detached by the ORCHESTRATOR, after claiming a band):
#   laptop:  setsid nohup systemd-run --user --scope -p MemoryMax=8G \
#              nice -n 19 bash .../run_deploy_opencity_round2.sh laptop <BAND> \
#              > driver.log 2>&1 < /dev/null &
#   local:   setsid nohup nice -n 19 bash .../run_deploy_opencity_round2.sh local <BAND> \
#              > driver.log 2>&1 < /dev/null &
#
# The funded cells run ONE AFTER THE OTHER on the chosen box. Opponent in every cell =
# the unmodified production champion a36d2e15a3b3d71d; BOTH ARMS of every cell at the
# DEPLOY budget k8x1376 = 11008 via eval_fair_puct.py (fair PIMC), fixed_v1 + R9, rust,
# exact-K 2, n=800 deck-paired per cell, DISJOINT seed ranges (cell i: <BAND>+400*i ..
# +400*i+399) -- cells never share decks and are NEVER pooled.
#
# ADJUDICATES NOTHING. No promotion, no PRODUCTION.yaml, no results.csv row, no claim row.
#
# ⚠️ DELIBERATELY DOES NOT RUN menu_block_summary.py. The wiring gates O1-O12 must be
#    read from the manifest BEFORE the strength summary is opened (DEPLOY_PREREG §4).
#    This driver emits GATES_<cell>.json -- pass/fail ONLY -- and leaves the summary to
#    the reading session.
#
# ⚠️ PRE-FLIGHT (the orchestrator's job, per box, BEFORE launching this -- prereg §3 O0):
#    1. rebuild + install the CAP-CAPABLE carc_rs wheel (TERM_SPEC §10; the CL-080-era
#       wheel TypeErrors on capped cells, and a swallowed TypeError = champion-vs-champion)
#    2. chain_capability_probe.py --require opencity  [--cap N for capped cells]  PASS
#    3. O0: _leaf_hash(cell JSON) == expected AND != a36d2e15a3b3d71d, computed ON THE BOX
#
# RESUMABLE: re-running skips any cell with its DONE marker; menu_fair_cell resumes from
# the seed*.json records on the share.
set -u
BOX="${1:?usage: run_deploy_opencity_round2.sh <laptop|local> <BAND_SEED_START> [W]}"
BAND="${2:?usage: run_deploy_opencity_round2.sh <laptop|local> <BAND_SEED_START> [W]}"
case "$BAND" in ''|*[!0-9]*) echo "BAND must be numeric, got '$BAND'"; exit 2 ;; esac

case "$BOX" in
  laptop) SHARE=/mnt/carc-shared;   W_DEFAULT=22 ;;   # laptop-wsl mount prefix
  local)  SHARE=/mnt/c/carc-shared; W_DEFAULT=14 ;;   # 5900XT-box mount prefix
  *) echo "BOX must be laptop|local, got '$BOX'"; exit 2 ;;
esac
W="${3:-${W:-$W_DEFAULT}}"
# Optional 4th arg: a substring filter on the cell SUB-name, so the three funded cells
# can be SPLIT ACROSS BOXES instead of run sequentially on one. Purely an execution
# split -- the cells already own DISJOINT seed offsets (<BAND>+400*i) and are read
# independently, so which box plays which cell changes no statistic. Empty = all cells.
CELL_FILTER="${4:-}"

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
DIR=$REPO/measurement/opencity_round2_20260814
LOGS=$DIR/deploy_logs
OUT=$SHARE/opencity_round2_RERUN_20260814   # ISOLATED: void cell records must never share a glob
N=${N:-800}
CHAMP_HASH=a36d2e15a3b3d71d

mkdir -p "$LOGS" "$DIR/verdicts" "$OUT"
ts() { date +%F_%T; }
log() { echo "[oc-r2-deploy $(ts)] $*"; }

# cell_name : seed_offset : cand_leaf_json : expected_cand_leaf_hash : expected_dose : expected_offdefault_knobs_json
# expected_offdefault_knobs_json = the opencity_* knobs (BESIDES the dose) that sit OFF
# their defaults in this cell and therefore MUST appear in the manifest's cand_leaf_cfg
# with exactly these values; every other opencity_* knob MUST be absent (gate O4).
# FUNDED CELLS — from CALIB_READOUT.md (mechanical read against read-rule 9a2abcd5,
# branch FUND-SMALLEST in all three families; C_d16p0 is an ON-THE-BAR selection,
# 10.41% vs the 10% bar with the Wilson-95 straddling it — recorded there, binding at
# read time per DEPLOY_PREREG §4.8):
CELLS=(
  "oc2_C_d16p0_RERUN_deploy11008:0:$DIR/cells/opencity_C_d16p0_deploy_fixed_v1_vs_fairchamp11008.json:a4acf6d0925f7606:16.0:{\"opencity_size_min\": 6.0, \"opencity_edge_min\": 3}"
)

log "=== START box=$BOX band=$BAND W=$W n=$N per cell, SEQUENTIAL ==="
log "host=$(hostname) out=$OUT repo_head=$(git -C $REPO rev-parse --short HEAD)"

for spec in "${CELLS[@]}"; do
  SUB=${spec%%:*};        rest=${spec#*:}
  if [ -n "$CELL_FILTER" ] && [[ "$SUB" != *"$CELL_FILTER"* ]]; then
    log "SKIP $SUB (CELL_FILTER='$CELL_FILTER' -- this cell runs on the other box)"
    continue
  fi
  OFF=${rest%%:*};        rest=${rest#*:}
  CELLJSON=${rest%%:*};   rest=${rest#*:}
  EXPECT_HASH=${rest%%:*}; rest=${rest#*:}
  EXPECT_DOSE=${rest%%:*}
  EXPECT_KNOBS=${rest#*:}
  SEED=$((BAND + OFF))

  if [ -f "$DIR/DONE_$SUB" ]; then
    log "cell $SUB already DONE (marker present) -- skipping"
    continue
  fi
  [ -f "$CELLJSON" ] || { log "!!! FAILED $SUB: missing cell json $CELLJSON"
    { echo "$(ts)"; echo "missing cell json $CELLJSON"; } > "$DIR/FAILED_$SUB"; exit 10; }

  log "--- cell $SUB seeds $SEED..$((SEED + N/2 - 1)) cand_hash=$EXPECT_HASH dose=$EXPECT_DOSE knobs=$EXPECT_KNOBS ---"
  mkdir -p "$OUT/$SUB"
  MENU_OUT_ROOT=$OUT nice -n 19 bash "$REPO/scripts/classical_search/menu_fair_cell.sh" "$W" "$BOX" \
      --sub "$SUB" --n "$N" --band "$SEED" \
      --k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376 \
      --cand-leaf-json "$CELLJSON" --drift > "$LOGS/cell_$SUB.log" 2>&1
  rc=$?
  GOT=$(find "$OUT/$SUB" -maxdepth 1 -name 'seed*.json' | wc -l)
  log "cell $SUB launcher rc=$rc records=$GOT/$N"

  # ---- wiring gates from the manifest. PASS/FAIL ONLY -- no strength number read here.
  MANIFEST="$OUT/$SUB/manifest.json" \
  EXPECT_HASH="$EXPECT_HASH" EXPECT_DOSE="$EXPECT_DOSE" EXPECT_KNOBS="$EXPECT_KNOBS" \
  EXPECT_SEED="$SEED" EXPECT_N="$N" GOT_N="$GOT" CHAMP_HASH="$CHAMP_HASH" SUB="$SUB" \
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
expect_knobs = json.loads(os.environ["EXPECT_KNOBS"])   # off-default knobs that MUST be present
g, res = [], True
def chk(n, ok, got):
    global res
    res &= bool(ok); g.append({"gate": n, "ok": bool(ok), "observed": got})
chk("O1_cand_leaf_hash", c.get("cand_leaf_hash") == os.environ["EXPECT_HASH"], c.get("cand_leaf_hash"))
chk("O1b_cand_hash_is_not_champion", c.get("cand_leaf_hash") != os.environ["CHAMP_HASH"], c.get("cand_leaf_hash"))
chk("O2_opp_leaf_hash", c.get("opp_leaf_hash") == os.environ["CHAMP_HASH"], c.get("opp_leaf_hash"))
# O3: the RESOLVED dose in the manifest. A moved cand_leaf_hash does NOT prove a live dose
# (round-1 DEPLOY_PREREG §3) -- this is the gate that does.
chk("O3_cand_opencity_dose_LIVE", float(cl.get("opencity_dose", 0.0)) == float(os.environ["EXPECT_DOSE"]),
    cl.get("opencity_dose"))
# O4 (round-2 form): every off-default knob of THIS ARM present with exactly its expected
# value; every other opencity_* knob (besides the dose) ABSENT (= at its default -- the
# _leaf_dict exclude-while-default recipe). A missing expected knob OR a stray knob means a
# DIFFERENT ARM ran and the cell is VOID.
seen = {k: v for k, v in cl.items() if k.startswith("opencity") and k != "opencity_dose"}
chk("O4_arm_knobs_exact", seen == {k: v for k, v in expect_knobs.items()},
    {"expected": expect_knobs, "observed": seen})
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
                               "(DEPLOY_PREREG.md section 4)."},
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
      echo "arm_knobs_expected $EXPECT_KNOBS";
      echo "workers $W (box $BOX only)"; echo "wiring_gates_all_pass $GPASS";
      echo "NOT ADJUDICATED - read DEPLOY_PREREG.md gates O1-O12 before any number."; } > "$DIR/DONE_$SUB"
    log "cell $SUB DONE ($GOT/$N) -> $DIR/DONE_$SUB"
    [ "$GOT" -lt "$N" ] && log "cell $SUB INCOMPLETE but >=90% - the 90% VOID rule applies at read time"
  else
    { echo "$(ts)"; echo "records $GOT/$N (<90%) - VOID by the standing rule";
      echo "launcher rc=$rc"; echo "see $LOGS/cell_$SUB.log"; } > "$DIR/FAILED_$SUB"
    log "!!! cell $SUB FAILED ($GOT/$N < 90%) -> $DIR/FAILED_$SUB. STOPPING; later cells NOT started."
    exit 11
  fi
done

: > "$DIR/DONE_DEPLOY_OPENCITY_ROUND2"
log "=== ALL CELLS COMPLETE (band $BAND, box $BOX). Nothing adjudicated, nothing promoted. ==="
