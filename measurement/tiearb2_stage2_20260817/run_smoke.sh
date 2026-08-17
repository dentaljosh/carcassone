#!/usr/bin/env bash
# =============================================================================
# tiearb2 STAGE 2 PHASE B — PRE-FLIGHT-AT-PRODUCTION-KNOBS SMOKE.
#
#   run_smoke.sh <local|laptop> <THROWAWAY_BAND> <N_GAMES>
#
# ⚠️ THIS IS NOT A CELL AND ITS NUMBERS ARE NOT A RESULT. It plays a handful of
# games on a THROWAWAY band, far outside the registry, purely to measure what a
# launch decision needs and cannot get any other way:
#
#   * per-game wall clock, per cell  -> the ETA for n=800 x 2
#   * the REALIZED `phi`, per cell   -> READ_RULE `G-FIRE`'s floor is 1.0/game,
#     and DESIGN §2.1 pre-registers that the offline 22.96 ESTIMATES the runtime
#     rate rather than equalling it. This is the first look at the real one.
#   * `ms_ratio_cand_over_opp`, per cell -> DESIGN §5 predicts ~1.1985 against
#     an N4 trigger of 1.20, i.e. it predicts the bar will be BRUSHED. ⚠️ THE
#     FIELD-NAME TRAP: `champ_prefix_ms_per_move` IS THE CANDIDATE SIDE in
#     eval_fair_puct (the opposite of eval_puct_priors). Swapping them inverts
#     the cost verdict.
#   * the pick-change rate -> READ_RULE §4.3's companion.
#
# PRODUCTION KNOBS, only the game count differs (the house pre-flight-smoke
# rule): same sims, same k, same exact-K, same backend, same rules profile, same
# leaf env, same worker count, same two modes. A cheap-smoke extrapolation from
# lower sims is unreliable — per-leaf cost grows nonlinearly with game length.
#
# ⚠️ EXCLUSIVE TENANT. A timing measurement shares the box with nothing. Census
# before, census after, and treat a co-tenant as a void.
#
# NO --shared-claim (each box measures ITS OWN throughput; two boxes stealing
# each other's games would measure neither), NO results.csv row, NO band claim,
# and the output goes to a `_SMOKE` directory that is never read as a cell.
# =============================================================================
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"

BOX="${1:?usage: run_smoke.sh <local|laptop> <THROWAWAY_BAND> <N_GAMES>}"
BAND="${2:?usage: run_smoke.sh <local|laptop> <THROWAWAY_BAND> <N_GAMES>}"
NS="${3:?usage: run_smoke.sh <local|laptop> <THROWAWAY_BAND> <N_GAMES>}"
case "$BAND" in ''|*[!0-9]*) echo "BAND must be numeric"; exit 2 ;; esac

# The real band is 132000000000. A smoke that touched it would burn the cell's
# decks before game 1 of the cell.
if [ "$BAND" = "132000000000" ]; then
  echo "REFUSING: 132000000000 is the CELL's band, not a throwaway"; exit 2
fi

case "$BOX" in
  local)  SHARE="$SHARE_LOCAL";  REPO="$REPO_LOCAL";  W="$W_LOCAL" ;;
  laptop) SHARE="$SHARE_REMOTE"; REPO="$REPO_REMOTE"; W="$W_LAPTOP" ;;
  *) echo "BOX must be local|laptop"; exit 2 ;;
esac

cd "$REPO" || { echo "FATAL: cannot cd to '$REPO'" >&2; exit 1; }

PY="$REPO/.venv/bin/python"
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
OUT="$SHARE/${RUN_ID}_SMOKE"
LOGS="$HERE/logs"
HOST="$(hostname)"
mkdir -p "$LOGS" "$OUT"
ts() { date +%F_%T; }
log() { echo "[smoke $(ts)] $*"; }

export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1
export RUSTUP_TOOLCHAIN="$RUST_TOOLCHAIN"

log "=== SMOKE box=$BOX host=$HOST band=$BAND n=$NS W=$W ==="
log "--- census BEFORE (a timing bench is an EXCLUSIVE tenant) ---"
ps -o pid,etime,%cpu,comm -C python --sort=-etime | head -8
cat /proc/loadavg

smoke_cell() {
  local SUB="$1" MODE="$2"
  local dir="$OUT/${SUB}_${HOST}"
  rm -rf "$dir"; mkdir -p "$dir"
  local t0 t1
  t0=$(date +%s)
  nice -n "$NICE" "$PY" -u "$HARNESS" \
    --info fair --opponent fair-champion --backend rust \
    --k-dets "$K_DETS" --sims "$SIMS" --opp-k-dets "$K_DETS" --opp-sims "$SIMS" \
    --exact-k "$EXACT_K" --c-puct 1.5 --tau-p 5 \
    --leaf-quantize float --final-select visits \
    --n "$NS" --paired --seed-start "$BAND" \
    --rules-profile fixed_v1 --workers "$W" \
    --out-root "$OUT" --out-subdir "${SUB}_${HOST}" \
    --no-results-csv \
    --cand-tiearb-enabled --cand-tiearb-b "$TIEARB_B" --cand-tiearb-j "$TIEARB_J" \
    --cand-tiearb-mode "$MODE" --cand-tiearb-salt "$TIEARB_SALT" \
    --cand-tiearb-eps "$TIEARB_EPS" \
    > "$LOGS/smoke_${SUB}_${HOST}.log" 2>&1
  local rc=$?
  t1=$(date +%s)
  log "cell $SUB (mode=$MODE) rc=$rc wall=$((t1-t0))s records=$(find "$dir" -maxdepth 1 -name 'seed*.json' | wc -l)/$NS"
  echo "$((t1-t0))" > "$dir/.wall_secs"
}

smoke_cell "$CELL_ARB" argmax
smoke_cell "$CELL_RND" random

log "--- census AFTER ---"
ps -o pid,etime,%cpu,comm -C python --sort=-etime | head -8
cat /proc/loadavg
log "=== SMOKE DONE on $HOST -> $OUT ==="
