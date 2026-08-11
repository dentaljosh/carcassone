#!/usr/bin/env bash
# run_kwidth_22016_20260729.sh — the 11008-vs-22016 budget-curve plateau discriminator.
#
# Pre-registration: measurement/classical_search/KWIDTH_22016_PREREG_20260729.md
# Phase 1 (picks)  : kwidth_agreement_probe.py — 22016 sims/cell (the k8 arm is the
#                    world-0..7 PREFIX pool, PROVEN per run by --verify-agent-parity).
# Phase 2 (scoring): oracle_score_pilot.py — CRN world-paired oracle, M=32, sims 100.
#
# Stage 1 is the ADAPTIVE BATCH (prereg §5): 200 cells, read D-hat, then size the rest.
# Resume-safe throughout (per-record atomic writes + --resume), so a re-exec is free.
#
# Usage:  run_kwidth_22016_20260729.sh <stage> [n_cells]
#           picks1   — batch 1: 200 cells, 20 of them agent-parity-verified
#           picksN N — extend the pick phase to N cells (prefix of the same fixed order)
#           score  N — score N disagreements with the oracle
set -uo pipefail

REPO=/home/doctor/projects/carcassone
PY="$REPO/.venv/bin/python"
OUT=/mnt/c/carc-shared/oracle_22016_20260729
BANK=/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9
LOGS="$REPO/measurement/classical_search"
W=16

STAGE="${1:?stage: picks1 | picksN | score}"
N="${2:-200}"

mkdir -p "$OUT"

case "$STAGE" in
  picks1|picksN)
    [ "$STAGE" = picks1 ] && N=200
    nice -n 19 "$PY" -u "$REPO/scripts/measurement_infra/kwidth_agreement_probe.py" \
      --run-dir "$BANK" --n "$N" --workers "$W" \
      --verify-agent-parity 20 --resume \
      --out-root "$OUT" --out-subdir picks \
      >>"$LOGS/kwidth_22016_picks.log" 2>&1
    ;;
  score)
    # --alloc-* states the REAL budgets: these arms differ in PIMC WIDTH, so the harness's
    # historical `4 x level` would write a wrong total into the manifest. --level-* here are
    # the q_pick_by_level KEYS (total budgets), which is how the pick records are keyed.
    nice -n 19 "$PY" -u "$REPO/scripts/measurement_infra/oracle_score_pilot.py" \
      --records-dir "$OUT/picks/records" --roots "$BANK/roots.jsonl" \
      --level-a 11008 --level-b 22016 --alloc-a k8x1376 --alloc-b k16x1376 \
      --n "$N" --sample-seed 20260729 --m 32 --oracle-sims 100 \
      --world-seed-salt kwidth-22016-v1 \
      --workers "$W" --resume \
      --out-root "$OUT" --out-subdir score \
      >>"$LOGS/kwidth_22016_score.log" 2>&1
    ;;
  *)
    echo "unknown stage: $STAGE" >&2; exit 2 ;;
esac
