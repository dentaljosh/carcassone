#!/usr/bin/env bash
# ============================================================================
# CLIFF LADDER — RUNG 1376  (candidate k4x344 = 1376 total vs the DEPLOY
# champion k4x688 = 2752 total), n=400 deck-paired, **SHARED BAND 88e9**.
#
# WHY: G2/CL-068's open loose end — the LOW END's budget ORDERING is unmeasured.
# The G2 confirm put 1376 at -53.4 (band 76e9) BELOW 688 at -37.5 (band 62e9),
# cross-band z -0.64. Shaping the cliff needs 688 / 1376 / 2752 DECK-MATCHED on
# ONE shared band. Rung 688 already ran on 88e9 (Apple M5, -83.2 +/- 17.9,
# results.csv `cliff688_k4x172_vs_deploy_n400_b88e9`,
# measurement/classical_search/M5_CAMPAIGN_READOUT_20260729.md).
#
# *** BAND 88e9 IS NON-NEGOTIABLE. *** seed_start 88000000000, n=400 --paired
# (200 decks), exactly as rung 688. Changing the band destroys the deck match
# and with it the whole point of the ladder.
#
# THIS MIRRORS /mnt/c/carc-shared/cliff_ladder_688_m5/manifest.json EXACTLY
# except for two things:
#   1. candidate --sims 172 -> 344 (688 total -> 1376 total). The rung itself.
#   2. PLATFORM: that cell ran darwin-arm64 (Apple M5, W10); this runs x86-64
#      Linux (laptop-wsl, W16). Both sides of THIS cell share the platform, so
#      the cell is internally sound, but the ladder is cross-platform — that
#      caveat must travel with any 688-vs-1376 comparison.
#
# ⚠️ DO NOT `source champ_env.sh` and do NOT export CARCASSONNE_* here.
#    eval_fair_puct.py owns _CANON_ENV via os.environ.setdefault: a pre-set
#    CARCASSONNE_V29_MEEPLE_CURVE would WIN and move DEFAULT_CONFIG, silently
#    dragging the h800 RUNG onto curve125 and invalidating the ruler. The
#    curve125 candidate/opponent leaves are injected IN-PROCESS instead.
#
# COST (same box, same config, same n — measured, not extrapolated): the G2
# confirm `g2confirm_k4x344_1376_vs_deploy_b76000000000` is this cell on a
# different band: laptop W16, 3h 12m wall, 1880 ms/move candidate vs 3773
# ms/move opponent (0.50x ratio). Expect ~3h 10m.
#
# READ-OUT: report BOTH statistics (winrate z AND deck-paired margin z), the
# per-side ms/move, and the platform flag. Nothing here promotes anything.
# ============================================================================
set -uo pipefail
cd /home/doctor/projects/carcassone

SHARE=${SHARE:-/mnt/carc-shared}
W=${W:-16}
N=${N:-400}
SUBDIR=${SUBDIR:-cliff_ladder_1376_laptop}
LOG=${LOG:-measurement/classical_search/cliff_1376_$(hostname -s).log}

echo "[$(date +%F_%T)] cliff rung 1376 (k4x344 vs deploy k4x688) START on $(hostname -s) W=$W n=$N band 88e9 -> $SHARE/$SUBDIR" | tee -a "$LOG"

nice -n 19 .venv/bin/python -u \
    scripts/classical_search/eval_fair_puct.py \
    --info fair \
    --opponent fair-champion \
    --k-dets 4 --sims 344 \
    --opp-k-dets 4 --opp-sims 688 \
    --exact-k 2 \
    --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits \
    --value-norm 15 \
    --n "$N" --paired --seed-start 88000000000 --workers "$W" \
    --out-root "$SHARE" --out-subdir "$SUBDIR" \
    --shared-claim --no-results-csv >> "$LOG" 2>&1
# ⚠️ rc on the very next line: `echo "[$(date ...)] rc=$?"` logs 0 even for a FAILED
#    run — the command substitution runs during word expansion and clobbers $? first.
rc=$?

if [ "$rc" -ne 0 ]; then
  echo "[$(date +%F_%T)] FAILED rc=$rc on $(hostname -s) — cell INCOMPLETE, do NOT read its summary. See $LOG" | tee -a "$LOG"
  exit 1
fi
echo "[$(date +%F_%T)] exited rc=0 on $(hostname -s)" | tee -a "$LOG"
