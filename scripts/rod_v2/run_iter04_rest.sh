#!/usr/bin/env bash
# iter04 interrogation cells 2-4 (after the h6400 top-up frees the boxes):
#   2) iter04 vs RoD1_v29   (net-vs-net, single-box local)
#   3) iter04 vs h3200_v2.9 (net-vs-heur, 2-box)
#   4) iter06 vs iter04     (net-vs-net, single-box local — optional regression check)
# Waits for the running h6400 top-up to finish first. Launch detached.
set -uo pipefail
REPO=/home/doctor/projects/carcassone; SHARE=/mnt/c/carc-shared
EVALDIR=$SHARE/rod_v2_flywheel/evals
HEUR=$REPO/scripts/rod_v2/run_heur_eval_v29.sh
NVN=$REPO/scripts/rod_v2/net_vs_net_v29.sh
CKDIR=$SHARE/rod_v2_flywheel/ckpt
ROD1=$SHARE/rod_v28_continuation/ckpt/iter_01.pt
cd "$REPO"; mkdir -p "$EVALDIR/logs"

# --- wait for the h6400 top-up (n=400) to complete ---
echo "[rest] waiting for h6400 top-up (>=395/400 or wrapper exit) @ $(date)"
while [ "$(ls "$EVALDIR"/rod2_iter04_vs_heur6400_v29/seed*_a*.json 2>/dev/null | wc -l)" -lt 395 ] \
      && pgrep -f '[r]un_heur_eval_v29' >/dev/null; do sleep 30; done
sleep 5; pkill -9 -f '[c]arc-orch' 2>/dev/null; sleep 2
echo "[rest] top-up done ($(ls "$EVALDIR"/rod2_iter04_vs_heur6400_v29/seed*_a*.json 2>/dev/null|wc -l) games) — starting cells 2-4 @ $(date)"

# --- CELL 2: iter04 vs RoD1 (net-vs-net) ---
sub=iter04_vs_rod1_v29
echo "[rest] CELL 2: $sub @ $(date)"
CKPT_A=$CKDIR/iter_04.pt CKPT_B=$ROD1 OW=24 SIMS=200 \
  bash "$NVN" --n 200 --paired --c-puct 3.0 --residual-scale 0.25 --meeple-k-a 2.0 --meeple-k-b 2.0 \
    --seed-start 1960000000 --shared-claim --claim-host local --out-root "$EVALDIR" --out-subdir "$sub" \
    > "$EVALDIR/logs/${sub}.log" 2>&1 || echo "[rest] cell2 rc=$?"
pkill -9 -f '[c]arc-orch' 2>/dev/null; sleep 3

# --- CELL 3: iter04 vs h3200 n=200 (net-vs-heur, 2-box, laptop W10) ---
echo "[rest] CELL 3: iter04 vs h3200 @ $(date)"
CKPT=$CKDIR/iter_04.pt LABEL=rod2_iter04 HSIMS=3200 N=200 SEED=1957000000 OW_LOCAL=40 OW_LAPTOP=10 \
  bash "$HEUR" || echo "[rest] cell3 rc=$?"
pkill -9 -f '[c]arc-orch' 2>/dev/null; sleep 3

# --- CELL 4: iter06 vs iter04 (net-vs-net, optional regression confirm) ---
sub=iter06_vs_iter04_v29
echo "[rest] CELL 4: $sub @ $(date)"
CKPT_A=$CKDIR/iter_06.pt CKPT_B=$CKDIR/iter_04.pt OW=24 SIMS=200 \
  bash "$NVN" --n 200 --paired --c-puct 3.0 --residual-scale 0.25 --meeple-k-a 2.0 --meeple-k-b 2.0 \
    --seed-start 1962000000 --shared-claim --claim-host local --out-root "$EVALDIR" --out-subdir "$sub" \
    > "$EVALDIR/logs/${sub}.log" 2>&1 || echo "[rest] cell4 rc=$?"
pkill -9 -f '[c]arc-orch' 2>/dev/null

echo ""; echo "=== iter04 INTERROGATION COMPLETE @ $(date) ==="
"$REPO/.venv/bin/python" "$REPO/scripts/rod_v2/extract_iter04_table.py"
