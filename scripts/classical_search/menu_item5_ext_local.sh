#!/usr/bin/env bash
# ITEM 5 / BLOCK E — CL-072 n->800 EXTENSION, LOCAL arm. Band 94e9, FRESH DECKS.
# Spec: docs/LEVER_MENU_PLAN_20260810.md section 4.5 + scripts/distill_flywheel/TEACHER_H2H_PREREG.md.
#
# WHAT FIRED THIS. CL-072's own pre-registration pre-commits: "if |elo| in [5, 25], extend the
# SAME cell to n=800 on fresh decks of the same band, then verdict." The n=400 cell read
# |elo| = 20.87, so the trigger FIRED on 2026-07-30 and the extension was never run. Funded
# 2026-08-10 ("its all funded").
#
# ⚠️ BAND POLICY — the ONE licensed exception to fresh-band. governance/BAND_REGISTRY.csv row
#    94000000000 is still `claimed`, not retired, precisely so this extension can draw FRESH
#    DECKS OF THIS BAND. The n=400 cell consumed seeds 94000000000..94000000199; this arm
#    starts at 94000000200 (200 fresh decks x 2 seats = 400 games). NO new band is claimed.
#
# Arms, stated precisely (the n=400 readout mis-stated them once):
#   candidate = CL-067's distilled net used as POLICY PRIORS with the FROZEN curve125 leaf
#               (value severed), k4x688 = 2752, served through carc-orch.
#   opponent  = the PRODUCTION classical champion FairHeuristicPriorAgent at the promoted
#               fair_deploy k8x1376 = 11008 -- a classical agent at the corpus teacher's tier,
#               NOT a teacher checkpoint. OPP_K_DETS + OPP_SIMS are BOTH required; --opp-sims
#               alone cannot express the k-axis.
#
# ⚠️ MANDATORY ORCHESTRATOR HYGIENE, else the server owns the box: OMP_NUM_THREADS=1 must reach
#    the carc-orch SERVER process (fair_net_vs_net_orch.sh never calls set_num_threads on the
#    Rust side, so an unpinned libtorch pool spins ~30 stray threads and outruns the workers
#    2574% to 367%), and max_batch >= W (k=1 with blocking workers). Both are set below via
#    `env ... bash`, which propagates to the server child.
#
# Structure is the proven n=400 cell script (/mnt/c/carc-shared/teacher_h2h_94e9/cells/h2h_full.sh)
# with the subdir/band/n moved to the extension. IDEMPOTENT + RESUME-SAFE.
set -uo pipefail
REPO=/home/doctor/projects/carcassone
CKPT=/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt
OUT_ROOT=/mnt/c/carc-shared/teacher_h2h_94e9
SUBDIR=n800ext_paired_b94e9
N=400
BAND=94000000200
OW=${OW:-14}                       # local cap is Joshua's W=14; orch workers block on the GPU
LOG=$OUT_ROOT/logs/ext_full.log

[ -f "$CKPT" ] || { echo "FATAL: ckpt missing at $CKPT"; exit 1; }
mkdir -p "$OUT_ROOT/logs" "$OUT_ROOT/$SUBDIR"

# refuse to double-run this cell on this box
if pgrep -f "eval_fair_puc[t].*$SUBDIR" >/dev/null 2>&1; then
  echo "$(date '+%F %T') local ext cell already live" >>"$LOG"; exit 0
fi

# Claim hygiene: claims-without-records ONLY, and only ours. The eval path fails OPEN -- a
# stranded claim makes the cell finish SHORT with a plausible summary.json at the wrong n.
# A .claim NAMES the host that owns it; never sweep a live sibling box's claim.
n=0
for c in "$OUT_ROOT/$SUBDIR"/*.claim; do
  [ -e "$c" ] || continue
  grep -q '^laptop' "$c" 2>/dev/null && continue
  [ -f "${c%.claim}.json" ] || { rm -f "$c"; n=$((n+1)); }
done
echo "$(date '+%F %T') cleared $n local claims-without-records" >>"$LOG"

cd "$REPO" || exit 1
echo "$(date '+%F %T') launching EXTENSION n=$N OW=$OW band=$BAND sub=$SUBDIR" >>"$LOG"
env CAND_CKPT="$CKPT" OW="$OW" ORCH_FWD=4 ORCH_MAX_BATCH="$OW" \
    OPP_K_DETS=8 OPP_SIMS=1376 \
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  nice -n 19 bash scripts/classical_search/fair_net_vs_net_orch.sh \
    --info fair-netprior --opponent fair-champion \
    --exact-k 2 --k-dets 4 --sims 688 \
    --n "$N" --paired --seed-start "$BAND" \
    --out-root "$OUT_ROOT" --out-subdir "$SUBDIR" \
    --shared-claim --claim-host "menu-local-$(hostname)" --no-results-csv \
  >> "$LOG" 2>&1
rc=$?
echo "$(date '+%F %T') local ext cell exited rc=$rc" >>"$LOG"
exit 0
