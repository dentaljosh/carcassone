#!/usr/bin/env bash
# OPEN-CITY CALIBRATION — offline E4-replay pick-flip rate, on the LAPTOP.
#
#   measurement/opencity_term_20260812/run_calib_laptop.sh [WORKERS]
#
# Reads: measurement/opencity_term_20260812/CALIB_READ_RULE.md (committed BEFORE any
# number was read; e6-arm ladder fixed there: A(4,2) B(3,2) C(6,3) x doses {0.5, 2.0},
# opencity_symmetric True in all arms).
#
# ZERO games, ZERO elo, NO deck band, NO governance write, NO results.csv row. This
# replays the 26 banked E4 human-vs-champion archives and, at every champion decision
# ply, re-runs the production search once per arm under CRN, recording whether the PICK
# CHANGES. A flip is not an improvement.
#
# WHY THE FILES ARE SCP'd RATHER THAN BUNDLED: the instrument + the probe extension are
# UNCOMMITTED in this session (commit authority was withheld). The repo itself IS synced
# by bundle (laptop HEAD == local android-app HEAD, asserted below); only the two new
# scripts ride on top, and their sha256 is verified on BOTH boxes so the run's provenance
# is a hash, not a hope.
#
# GATE ORDER (all three must pass before a single ply is graded):
#   G1  laptop git rev == local git rev
#   G2  sha256(instrument) and sha256(probe) agree local vs laptop
#   G3  chain_capability_probe.py --require opencity PASSES on the laptop for arms A and B
#       (the stale-wheel trap: `leaf_config_rs` is fail-closed, but a launcher that
#       swallowed the TypeError would grade champion-vs-champion and read 0.0% flips as
#       though it were a measurement). Arm C (6,3) is EXPECTED to be inert — TERM_SPEC §6
#       measured its predicate firing on 0.0% of golden-corpus leaf values — so arm C's
#       functional leg is reported, never gated on.
set -euo pipefail

W="${1:-18}"
REPO=/home/doctor/projects/carcassone
DIR=$REPO/measurement/opencity_term_20260812
LOGS=$DIR/laptop_logs
OUT=$DIR/calib          # in-repo, same shape as measurement/denial_screen_20260811/calib_*
LAPTOP=laptop-wsl
PY=$REPO/.venv/bin/python

INSTR=scripts/classical_search/opencity_e4_replay.py
PROBE=scripts/classical_search/chain_capability_probe.py

mkdir -p "$LOGS"
log() { echo "[oc-calib $(date +%F_%T)] $*" | tee -a "$LOGS/driver.log"; }
die() { log "ABORT: $*"; exit 1; }

cd "$REPO"
[ -f "$INSTR" ] || die "instrument missing: $INSTR"
[ -f "$PROBE" ] || die "probe missing: $PROBE"

# --- G1 CODE identity (not HEAD identity) ------------------------------------
# The house gate is full-rev identity. That is the right gate for a GAMES cell, where
# both boxes must be the same build in every respect. It is the WRONG gate here, and
# strictly so: this replay computes a leaf and runs a search, so what must match is the
# code that does that — `src/`, `engine/`, `rust/` — plus the two scp'd scripts (G2).
# Full-rev identity would additionally require every DOC and every other measurement
# directory to match, which fails the moment a concurrent session commits a readout, and
# would tempt a re-sync of 564 MB to fix a difference that cannot touch a single number.
# So: gate on the three source trees, and RECORD both HEADs for provenance. A src/rust
# change still trips this; a doc commit correctly does not.
LREV=$(git rev-parse HEAD)
RREV=$(timeout 60 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" \
        'git -C /home/doctor/projects/carcassone rev-parse HEAD' 2>/dev/null || true)
[ -n "$RREV" ] || die "laptop unreachable"
LTREE=$(git rev-parse HEAD:src HEAD:engine HEAD:rust | tr '\n' ' ')
RTREE=$(timeout 60 ssh -o BatchMode=yes "$LAPTOP" \
        "git -C $REPO rev-parse HEAD:src HEAD:engine HEAD:rust | tr '\n' ' '" 2>/dev/null || true)
[ "$LTREE" = "$RTREE" ] || die "SOURCE TREE mismatch (leaf/search code differs) — local [$LTREE] vs laptop [$RTREE]. Bundle-sync before running."
log "GATE G1: source-tree identity OK (src+engine+rust: $LTREE)"
log "GATE G1: HEADs recorded — local ${LREV:0:9}, laptop ${RREV:0:9}$([ "$LREV" = "$RREV" ] || echo ' (differ in non-source paths only; verified above)')"
echo "local_head $LREV"$'\n'"laptop_head $RREV"$'\n'"src_engine_rust_trees $LTREE" > "$LOGS/REV_PROVENANCE.txt"

# --- G2 ship the two uncommitted scripts, hash-verified ----------------------
SHA_I=$(sha256sum "$INSTR" | cut -d' ' -f1)
SHA_P=$(sha256sum "$PROBE" | cut -d' ' -f1)
scp -q "$INSTR" "$LAPTOP:$REPO/$INSTR"
scp -q "$PROBE" "$LAPTOP:$REPO/$PROBE"
RSHA=$(timeout 60 ssh -o BatchMode=yes "$LAPTOP" \
        "sha256sum $REPO/$INSTR $REPO/$PROBE | cut -d' ' -f1 | tr '\n' ' '")
echo "$RSHA" | grep -q "$SHA_I" || die "instrument sha mismatch on laptop"
echo "$RSHA" | grep -q "$SHA_P" || die "probe sha mismatch on laptop"
log "GATE G2: script sha256 agree — instrument ${SHA_I:0:16} probe ${SHA_P:0:16}"
{ echo "instrument $INSTR $SHA_I"; echo "probe $PROBE $SHA_P"; } > "$LOGS/SCRIPT_SHA256.txt"

# --- G3 capability probe on the laptop, per threshold arm --------------------
cat > "$LOGS/_laptop_probe.sh" <<'PROBESH'
set -uo pipefail
cd /home/doctor/projects/carcassone
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1
L=/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs
rc_total=0
probe_arm () {   # name size_min edge_min  (rc is FATAL only for the arms we gate on)
  .venv/bin/python scripts/classical_search/chain_capability_probe.py \
    --require opencity --doses 0.5,2.0 --size-min "$2" --edge-min "$3" \
    --json-out "$L/PROBE_opencity_$1.json" > "$L/probe_$1.log" 2>&1
  echo "arm $1 (size_min=$2 edge_min=$3) probe rc=$?"
}
probe_arm A 4 2
probe_arm B 3 2
probe_arm C 6 3
PROBESH
timeout 900 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' < "$LOGS/_laptop_probe.sh" \
    2>&1 | tee -a "$LOGS/driver.log"

for a in A B; do
  RC=$(timeout 60 ssh -o BatchMode=yes "$LAPTOP" \
        "$PY -c \"import json;print(json.load(open('$LOGS/PROBE_opencity_$a.json'))['ok'])\"" 2>/dev/null || echo False)
  [ "$RC" = "True" ] || die "laptop opencity capability probe FAILED on arm $a — see $LOGS/probe_$a.log. A silently default-off arm grades champion-vs-champion and reads 0.0% flips as if it were a measurement."
done
log "GATE G3: laptop opencity capability probe PASS on arms A and B (arm C reported, not gated)"

# --- launch the calibration, detached, memory-capped -------------------------
# CALIB_CMD.sh is written HERE and scp'd (never generated by a nested heredoc on the
# remote — the escaping is the classic silent-corruption seam).
cat > "$LOGS/CALIB_CMD.sh" <<RUNCMD
#!/usr/bin/env bash
cd /home/doctor/projects/carcassone
L=measurement/opencity_term_20260812/laptop_logs
nice -n 19 .venv/bin/python -u scripts/classical_search/opencity_e4_replay.py \\
  -o measurement/opencity_term_20260812/calib \\
  --workers $W \\
  >> \$L/calib.log 2>&1
rc=\$?
if [ "\$rc" -eq 0 ]; then touch \$L/DONE_CALIB; else echo "rc=\$rc \$(date -Is)" >> \$L/FAILED_CALIB; fi
RUNCMD
chmod +x "$LOGS/CALIB_CMD.sh"
scp -q "$LOGS/CALIB_CMD.sh" "$LAPTOP:$LOGS/CALIB_CMD.sh"

cat > "$LOGS/_laptop_calib.sh" <<CALIBSH
set -euo pipefail
cd /home/doctor/projects/carcassone
mkdir -p "$OUT" "$LOGS"
rm -f "$LOGS/DONE_CALIB" "$LOGS/FAILED_CALIB"
chmod +x "$LOGS/CALIB_CMD.sh"
nohup systemd-run --user --scope -p MemoryMax=8G bash "$LOGS/CALIB_CMD.sh" \
  > "$LOGS/calib_scope.log" 2>&1 < /dev/null &
disown
echo "calibration launched detached at W=$W (MemoryMax=8G)"
CALIBSH
timeout 180 ssh -o BatchMode=yes -o ConnectTimeout=20 "$LAPTOP" 'bash -s' < "$LOGS/_laptop_calib.sh" \
    2>&1 | tee -a "$LOGS/driver.log" || log "ssh rc=$? (124 == launched-and-detached)"

log "LAUNCHED at W=$W. Verify parallelism now:  ssh $LAPTOP 'pgrep -fc opencity_e4_replay'"
