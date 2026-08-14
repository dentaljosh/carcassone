cd /home/doctor/projects/carcassone || exit 9
set -u
REPO=/home/doctor/projects/carcassone
DIR=/home/doctor/projects/carcassone/measurement/jrules_on_search_20260813
PY=/home/doctor/projects/carcassone/.venv/bin/python
BUNDLE="/mnt/carc-shared/bundles/jrules_d0p25_20260813_133750.bundle"
[ -f "$BUNDLE" ] || { echo "bundle $BUNDLE not visible from the laptop" >&2; exit 3; }
drift=$(( $(date +%s) - $(stat -c %Y "$BUNDLE") )); drift=${drift#-}
if [ "$drift" -gt 300 ]; then
  echo "CLOCK DRIFT ${drift}s vs bundle mtime — a drifted client STEALS every sibling claim. Fix with date -s first." >&2
  exit 4
fi
# ⚠️ REFUSE TO reset --hard OVER UNCOMMITTED WORK. Another session may be mid-rebuild of
# the carc_rs wheel on this box (G3 is owed per box), and a blind reset would silently
# destroy its tracked edits. A dirty laptop tree is a HUMAN decision, not a sync failure:
# fail loudly and let the local leg run alone rather than clobber someone's work.
dirty=$(git status --porcelain 2>/dev/null | head -20)
if [ -n "$dirty" ]; then
  echo "LAPTOP SYNC REFUSED: the laptop repo has uncommitted changes and syncing would" >&2
  echo "  'git reset --hard' over them. Someone may be mid-rebuild here. Resolve by hand," >&2
  echo "  then re-join with: bash /home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/run_deploy_jrules_d0p25.sh --laptop-only" >&2
  echo "$dirty" >&2
  exit 6
fi
git fetch "$BUNDLE" android-app || exit 5
git reset --hard FETCH_HEAD  || exit 5
echo "laptop synced to $(git rev-parse --short HEAD)"
# ---- the launcher env canon, byte-identical to menu_fair_cell.sh -----------------------
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1

mkdir -p "$DIR/verdicts" "$DIR/logs"

# ---- share resolution ON THE LAPTOP, by content. BOTH candidate paths exist here. ------
SHARE=""
for cand in /mnt/c/carc-shared /mnt/carc-shared; do   # allow-path
  [ -d "$cand" ] || { echo "  laptop share candidate $cand: REJECTED (not a directory)"; continue; }
  if [ ! -f "$cand/BAND_CLAIMS.txt" ]; then
    echo "  laptop share candidate $cand: REJECTED (no sentinel; $(ls -A "$cand" 2>/dev/null | wc -l) entries — this is the laptop's own C:, not the share)"
  elif [ -z "$SHARE" ]; then
    SHARE="$cand"; echo "  laptop share candidate $cand: ACCEPTED (sentinel present)"
  fi
done
[ -n "$SHARE" ] || { echo "FATAL: no laptop share mount carries BAND_CLAIMS.txt — refusing to guess" >&2; exit 10; }

# ---- G3 (per box): the wheel really carries the term, and Rust == Python on the corpus.
# This is the SOLE Rust-parity guard for jrules (test_rust_parity_spot_check skips
# STRUCTURALLY — carc_rs exposes no direct leaf entry point — so it will never become a
# pass on any rebuilt box). A stale wheel here is fail-closed, but a launcher that swallowed
# it would produce a champion-vs-champion cell reading as "the strategy is worth nothing"
# rather than "it never ran".
echo "--- laptop G3: reconcile_leaf.py --configs jrules --corpus golden ---"
if ! "$PY" "$REPO/scripts/rustport/reconcile_leaf.py" --configs jrules --corpus golden \
        --workers 8 --out "$DIR/verdicts/G3_reconcile_laptop.json" \
        > "$DIR/logs/g3_reconcile_laptop.log" 2>&1; then
  echo "LAPTOP GATE FAIL: G3 reconcile FAILED — the carc_rs wheel is stale or Rust/Python diverge." >&2
  echo "  see $DIR/logs/g3_reconcile_laptop.log" >&2
  exit 30
fi
echo "laptop G3 PASS"

echo "--- laptop G4: chain_capability_probe.py --require jrules --doses 0.25 ---"
if ! "$PY" "$REPO/scripts/classical_search/chain_capability_probe.py" \
        --require jrules --doses 0.25 \
        --json-out "$DIR/verdicts/G4_probe_laptop.json" \
        > "$DIR/logs/g4_probe_laptop.log" 2>&1; then
  echo "LAPTOP GATE FAIL: G4 capability probe FAILED — see $DIR/verdicts/G4_probe_laptop.json" >&2
  exit 31
fi
echo "laptop G4 PASS"
echo "--- laptop O0: leaf hashes under the launcher env canon ---"
CELLJSON=/home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/cells/jrules_d0p25_deploy_fixed_v1_vs_fairchamp11008.json EXPECT_CAND_HASH=15948beccf3472d3 CHAMP_HASH=a36d2e15a3b3d71d \
EXPECT_DOSE=0.25 EXPECT_MASK=31 TRAP_HASH=92ac0da996e1b37b \
"$PY" "/home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/o0_leaf_gate.py" "/home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/verdicts/O0_laptop.json" || {
  echo "LAPTOP GATE FAIL: O0 leaf gate FAILED — see /home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/verdicts/O0_laptop.json" >&2; exit 32; }
echo "laptop O0 PASS"

# ---- launch, DETACHED and memory-capped ------------------------------------------------
# setsid + nohup + disown: the laptop VM is torn down by Windows memory pressure and a
# systemd --user scope dies with the last ssh session, so the job must outlive this ssh.
mkdir -p "$SHARE/jrules_deploy_20260813/jrules_d0p25_deploy11008"
MENU_OUT_ROOT="$SHARE/jrules_deploy_20260813" setsid nohup systemd-run --user --scope -p MemoryMax=8G \
  nice -n 19 bash "/home/doctor/projects/carcassone/scripts/classical_search/menu_fair_cell.sh" \
    16 laptop --sub jrules_d0p25_deploy11008 --n 800 --band 128000000000 --k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376 --exact-k 2 --cand-leaf-json /home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/cells/jrules_d0p25_deploy_fixed_v1_vs_fairchamp11008.json --drift  \
  >> "/home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/logs/cell_laptop.log" 2>&1 < /dev/null &
disown
echo "laptop leg LAUNCHED detached (W=16, MemoryMax=8G) -> $SHARE/jrules_deploy_20260813/jrules_d0p25_deploy11008"
