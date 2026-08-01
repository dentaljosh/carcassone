#!/usr/bin/env bash
# run_kwidth_110k_20260801.sh — the "champ vs 10x champ" oracle-scored disagreement SCREEN.
#
# Pre-registration: measurement/classical_search/KWIDTH_110K_PREREG_20260801.md
# Arms: A = k8x1376 = 11008 (the champion of record) vs B = k80x1376 = 110080 (10x,
#       WIDTH-scaled at fixed sims_per_det — the allocation the world-prefix cost trick
#       requires and the direction the 2026-07-29 22016 arm measured).
# Phase 1 (picks)  : kwidth_agreement_probe.py --k-a 8 --k-b 80 — 110080 sims/cell (arm A
#                    is the world-0..7 PREFIX pool, PROVEN per run by --verify-agent-parity).
# Phase 2 (scoring): oracle_score_pilot.py — CRN world-paired oracle, M=32, sims 100,
#                    IDENTICAL judge knobs to the 22016 rung so the rungs are commensurable.
#
# RUNS ON THE LAPTOP (laptop-wsl). The local 5900XT is owned by the P6 gate.
#   bank  : /mnt/carc-shared/...   (the remote spelling of the share; local is /mnt/c/...)
#   output: LAPTOP-LOCAL disk, NOT the share — the share is 99% full and an 8 h run must
#           not depend on SMB staying up for every per-record write. Synced back at the end.
#
# Resume-safe throughout (per-record atomic writes + --resume), so a re-exec is free.
#
# Usage:  run_kwidth_110k_20260801.sh <stage> [n]
#           probe20  — the PRE-FLIGHT: 20 cells, ALL 20 agent-parity-verified. Proves the
#                      prefix trick at k80 and measures cost at PRODUCTION knobs.
#           picksN N — extend the pick phase to N cells (prefix of the same fixed order)
#           score  N — score N disagreements with the oracle
set -uo pipefail

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
OUT=/home/doctor/carc_out/oracle_110k_20260801
BANK=/mnt/carc-shared/classical_search/move_agreement_k4_b28e9
LOGS="$REPO/measurement/classical_search"
W=16
K_A=8
K_B=80

STAGE="${1:?stage: probe20 | picksN | score}"
N="${2:-20}"

mkdir -p "$OUT" "$LOGS"

case "$STAGE" in
  probe20|picksN)
    VERIFY=20
    [ "$STAGE" = probe20 ] && N=20
    nice -n 19 "$PY" -u "$REPO/scripts/measurement_infra/kwidth_agreement_probe.py" \
      --run-dir "$BANK" --n "$N" --workers "$W" \
      --k-a "$K_A" --k-b "$K_B" --sims-per-det 1376 \
      --wall-cap 5400 \
      --verify-agent-parity "$VERIFY" --resume \
      --out-root "$OUT" --out-subdir picks \
      >>"$LOGS/kwidth_110k_picks.log" 2>&1
    ;;
  score)
    # --level-* are the q_pick_by_level KEYS (TOTAL budgets), which is how the pick
    # records are keyed; --alloc-* states the real allocation in the manifest.
    nice -n 19 "$PY" -u "$REPO/scripts/measurement_infra/oracle_score_pilot.py" \
      --records-dir "$OUT/picks/records" --roots "$BANK/roots.jsonl" \
      --level-a 11008 --level-b 110080 --alloc-a k8x1376 --alloc-b k80x1376 \
      --n "$N" --sample-seed 20260801 --m 32 --oracle-sims 100 \
      --world-seed-salt kwidth-110k-v1 \
      --workers "$W" --resume \
      --out-root "$OUT" --out-subdir score \
      >>"$LOGS/kwidth_110k_score.log" 2>&1
    ;;
  *)
    echo "unknown stage: $STAGE" >&2; exit 2 ;;
esac
