#!/usr/bin/env bash
# ============================================================================
# tiearb2_20260816 — DESIGN §10 COST / INTEGRITY PILOT.
#
# ⚠️ IT READS NO STRENGTH NUMBER. It runs on SPENT-corpus positions (the
# 2026-08-14 OOF run's own cost-pilot rids, already burned for inference) and
# reads ONLY wall-clock / elapsed_secs / n_ok / n_failed / crn_verified /
# checksum_ok, the world+playout-seed identity witnesses, and the G-REPRO
# bit-reproduction COUNT. See pilot_report.py's docstring for the three
# mechanisms that enforce that.
#
# WHAT IT PRODUCES: PILOT.json, carrying c_tier1, the full rho_wall ladder and
# the FROZEN B* — written BEFORE one position of the fresh corpus is scored.
#
# ABORT RULE (DESIGN §10 rule 1, mechanical, no owner call): n_failed > 0, or
# any crn_verified/checksum_ok false, or any seed/arm mismatch vs the primary
# clair-puct record, or G-REPRO short of its expected count  =>  this script
# exits NON-ZERO with a loud banner and run_main.sh must NOT be run.
#
# BOX: LOCAL only (judge tier1-greedy, W_LOCAL, nice -n 19).
# DETACH IT (Mac->Windows->WSL SIGHUP + WSL VM teardown both kill tty-attached
# jobs). This script NEVER self-launches:
#
#     setsid nohup measurement/tiearb2_20260816/run_pilot.sh \
#       > measurement/tiearb2_20260816/logs/run_pilot.out 2>&1 < /dev/null &
#     disown
# ============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=WORKERS.conf
. "$HERE/WORKERS.conf"

W="$REPO_LOCAL"
M="$HERE"
PY="$W/.venv/bin/python"
SHARE_RUN="$SHARE_RUN_LOCAL"
LOGS="$M/logs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

export CARC_SRC_ROOT="$W/src"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

mkdir -p "$LOGS"
LOG="$LOGS/run_pilot_$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

banner() { printf '%s\n' "=============================================================================="; }
die() { banner; echo "  ⛔ $*"; banner; exit 1; }

echo "[pilot] $(date -Is)  run=$RUN_ID  host=$(hostname)  log=$LOG"

# ---- 0. LOCAL-BOX GUARD ----------------------------------------------------
# The laptop's /mnt/c is its OWN Windows drive and carries none of these. A
# silent read of the wrong share is the failure this guard exists to prevent.
for marker in "$SHARE_LOCAL/tiletie_pricing_20260812/clair-puct" \
              "$SHARE_LOCAL/tiletie_oof_20260814/pilot/tier1-greedy"; do
  [ -d "$marker" ] || die "LOCAL-BOX GUARD: '$marker' is absent, so $SHARE_LOCAL is NOT the project share. run_pilot.sh is LOCAL-ONLY (CLUSTER_OPS: the laptop's /mnt/c is its own Windows drive). Refusing."
done
echo "[pilot] local-share guard OK ($SHARE_LOCAL)"

# ---- 1. process census (house rule: reflex, not response) ------------------
echo "[pilot] ---- process census ----"
ps -o pid,etime,%cpu,comm -C python --sort=-etime 2>/dev/null || echo "[pilot] no python processes"
cat /proc/loadavg

# ---- 2. stage the pilot positions (SPENT corpus x the OOF pilot rids) ------
PILOT_DIR="$M/positions_pilot"
if [ -f "$PILOT_DIR/ARMS.json" ]; then
  echo "[pilot] positions_pilot already staged -- verifying"
  CMD_STAGE=(nice -n "$NICE" "$PY" "$M/stage_plans.py" pilot --out-dir "$PILOT_DIR" --verify)
else
  CMD_STAGE=(nice -n "$NICE" "$PY" "$M/stage_plans.py" pilot --out-dir "$PILOT_DIR")
fi
echo "[pilot] EXACT COMMAND:"; printf '  %q' "${CMD_STAGE[@]}"; echo
"${CMD_STAGE[@]}" || die "staging positions_pilot failed"

# ---- 3. score, judge tier1-greedy only ------------------------------------
# ⚠️ --strict-crn is NOT a run_tiletie.py flag. It is an oracle_score_pilot.py
#    flag that DEFAULTS ON, and run_tiletie.leg_command never passes
#    --no-strict-crn -- so strict CRN is on by construction, not by a flag.
# ⚠️ The world-seed salt is likewise NOT a flag here: WORLD_SEED_SALT =
#    "tiletie-v1" is a hardcoded module constant in run_tiletie.py (L102) that
#    it injects into every leg command (DESIGN §0.A.1).
CMD=(nice -n "$NICE" "$PY" "$W/scripts/tiletie/run_tiletie.py"
     --positions-dir "$PILOT_DIR"
     --judges tier1-greedy
     --m 32
     --oracle-sims 100
     --workers "$W_LOCAL"
     --out-root "$SHARE_RUN/pilot"
     --logs-dir "$LOGS"
     --gate-out "$M/GATE_BACKEND_RECHECK_pilot.json"
     --manifest-out "$M/RUN_MANIFEST_pilot.json"
     --yes)
echo "[pilot] EXACT COMMAND:"; printf '  %q' "${CMD[@]}"; echo
"${CMD[@]}"
rc=$?
echo "[pilot] run_tiletie rc=$rc  $(date -Is)"
[ "$rc" -eq 0 ] || die "run_tiletie failed (rc=$rc) -- PILOT.json not written, main run NOT authorised"

# ---- 4. the report + the mechanical rule ----------------------------------
CMD_REPORT=(nice -n "$NICE" "$PY" "$M/pilot_report.py"
            --new-root     "$SHARE_RUN/pilot"
            --primary-root "$SHARE_LOCAL/tiletie_oof_20260814/pilot"
            --plan         "$M/corpus/positions/POSITIONS_PLAN.json"
            --out          "$M/PILOT.json")
echo "[pilot] EXACT COMMAND:"; printf '  %q' "${CMD_REPORT[@]}"; echo
"${CMD_REPORT[@]}"
prc=$?

if [ "$prc" -ne 0 ]; then
  banner
  echo "  ⛔ PILOT ABORT (pilot_report rc=$prc)."
  echo "  THE FRESH CORPUS IS NOT SCORED AND STAYS UNBURNED."
  echo "  DO NOT RUN run_main.sh. See $M/PILOT.json for the integrity block."
  banner
  exit "$prc"
fi

touch "$M/DONE_PILOT"
banner
echo "  ✅ PILOT CLEAN — B* frozen in $M/PILOT.json. The main run may launch."
banner
exit 0
