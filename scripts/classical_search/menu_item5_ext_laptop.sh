#!/usr/bin/env bash
# ITEM 5 / BLOCK E — CL-072 n->800 EXTENSION, LAPTOP arm. Joins the SAME --shared-claim cell.
# Runs ON the laptop, so the share prefix is /mnt/carc-shared (it is /mnt/c/carc-shared locally).
# Spec: docs/LEVER_MENU_PLAN_20260810.md section 4.5.
#
# THE LAPTOP DOES NOT NEED THE LOCAL GPU, and this is not a guess: the n=400 cell already ran
# exactly this way -- the laptop served ITS OWN net from ITS OWN GPU through its own carc-orch
# at OW=12 while local ran OW=20 (teacher_h2h_94e9/logs/full_laptop.log).
# ⚠️ scripts/az_zero/laptop_joiner.sh is NOT the mechanism here: that is a self-play GENERATION
#    joiner for the az_zero loop (its ~16% contribution figure and its _clean_stranded residue
#    belong to that loop). The eval-side two-box pattern below is the one already proven.
#
# ⚠️ OW=12 IS SIZED FROM A MEASUREMENT, not a guess: the n=400 local arm showed 537 MB RSS per
#    eval worker. The laptop has ~10 GB available, so W12 -> 12 x 0.537 = 6.4 GB + ~1.5 GB orch
#    = ~7.9 GB with ~2 GB headroom, while W16 -> ~10.1 GB == the whole budget, no headroom. This
#    box has a documented WSL-VM-teardown-under-memory-pressure failure mode, so the MemoryMax
#    scope makes a breach fail CLOSED (the cell dies and --shared-claim resumes it) instead of
#    taking the whole VM down. systemd --user linger is ENABLED (2026-08-09), so the scope
#    survives ssh exit.
#
# ⚠️ ORCHESTRATOR HYGIENE (mandatory): OMP_NUM_THREADS=1 must reach the carc-orch SERVER, and
#    max_batch >= W. Both are set via the `env ...` prefix, which the server child inherits.
set -uo pipefail
REPO=/home/doctor/projects/carcassone
SHARE=/mnt/carc-shared
CKPT=$SHARE/distill_strong_20260723/ckpt/iter_03.pt
OUT_ROOT=$SHARE/teacher_h2h_94e9
SUBDIR=n800ext_paired_b94e9
N=400
BAND=94000000200                   # FRESH decks of band 94e9 (n=400 cell used ..000..199)
OW=${OW:-12}
LOG=$OUT_ROOT/logs/ext_laptop.log

[ -f "$CKPT" ] || { echo "FATAL: ckpt missing at $CKPT"; exit 1; }
mkdir -p "$OUT_ROOT/logs" "$OUT_ROOT/$SUBDIR"

if pgrep -f "eval_fair_puc[t].*$SUBDIR" >/dev/null 2>&1; then
  echo "$(date '+%F %T') laptop ext cell already live" >>"$LOG"; exit 0
fi

# Claim hygiene: OUR host's claims only, and only those with no record. A .claim NAMES the host
# that owns it -- sweeping a live sibling box's claim is how a duplicate worker gets started on
# a seed another box already owns (2026-07-30 near-miss).
n=0
for c in "$OUT_ROOT/$SUBDIR"/*.claim; do
  [ -e "$c" ] || continue
  grep -q '^menu-laptop' "$c" 2>/dev/null || continue
  [ -f "${c%.claim}.json" ] || { rm -f "$c"; n=$((n+1)); }
done
echo "$(date '+%F %T') cleared $n stranded laptop claims" >>"$LOG"

cd "$REPO" || exit 1
echo "$(date '+%F %T') laptop joining EXTENSION n=$N OW=$OW band=$BAND sub=$SUBDIR" >>"$LOG"
systemd-run --user --scope -p MemoryHigh=8G -p MemoryMax=9G \
  env CAND_CKPT="$CKPT" OW="$OW" ORCH_FWD=4 ORCH_MAX_BATCH="$OW" \
      OPP_K_DETS=8 OPP_SIMS=1376 \
      OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    nice -n 19 bash scripts/classical_search/fair_net_vs_net_orch.sh \
      --info fair-netprior --opponent fair-champion \
      --exact-k 2 --k-dets 4 --sims 688 \
      --n "$N" --paired --seed-start "$BAND" \
      --out-root "$OUT_ROOT" --out-subdir "$SUBDIR" \
      --shared-claim --claim-host menu-laptop --no-results-csv \
  >>"$LOG" 2>&1
rc=$?
echo "$(date '+%F %T') laptop ext cell exited rc=$rc" >>"$LOG"
exit 0
