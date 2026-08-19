#!/usr/bin/env bash
# =============================================================================
# b64_cell — THE TWO-CELL LAUNCHER. `WIDE` (`B` = 64) and `NARROW` (`B` = 16),
# deck-paired on ONE fresh band and THE SAME DECKS, against the unmodified
# champion, at production budget k8x1376 = 11,008, exact-K 2.
#
#   run_cells.sh <local|laptop-side> [--smoke] [--dry-run] [--band <SEED_START>]
#
# ⭐ THE TWO INVOCATIONS DIFFER IN EXACTLY ONE ARGUMENT — `--cand-tiearb-b`.
# That is the whole design (DESIGN §1.3): `WIDE` is a STRICT REFINEMENT of
# `NARROW`, not a different experiment, because the world seed is a pure function
# of `j` and never of `B`, so `B` = 64's worlds 0..15 are byte-identical to
# `B` = 16's entire set. Any second difference would break the nesting the whole
# "increment" framing rests on.
#
# ⛔ THE PAIR IS BLIND-COMMITTED (`ad089bda`) AND IS LAW. Every knob comes from
# `WORKERS.conf`, which reads them from the pair. A launcher that disagrees with
# the pair is a LAUNCHER defect: report it, do not "fix" it here.
#
# PRECONDITIONS, IN ORDER, AND THIS SCRIPT ENFORCES THEM:
#   1. `preflight.sh` has PASSED on THIS host at BOTH `B` values (G-J13).
#   2. the smoke has run and its HALT bar has been evaluated (G-SMOKE, §9.3) —
#      unless this IS the smoke.
#   3. the band was claimed from `governance/BAND_REGISTRY.csv` BEFORE game 1
#      (G-BAND) — the claim is the EXECUTOR's act and its sentinel is passed in
#      with `--band`; ⛔ this script never claims a band and never invents one.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached jobs:
#   setsid nohup ./run_cells.sh local </dev/null >/dev/null 2>&1 &
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$HERE/WORKERS.conf"

ROLE="${1:?usage: run_cells.sh <local|laptop-side> [--smoke] [--dry-run] [--band SEED_START]}"
shift || true
SMOKE=0; DRY=0; BAND=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --smoke)   SMOKE=1 ;;
    --dry-run) DRY=1 ;;
    --band)    BAND="${2:?--band needs a seed start}"; shift ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

case "$ROLE" in
  local)       REPO="$REPO_LOCAL";  SHARE="$SHARE_LOCAL";  W="$W_LOCAL" ;;
  laptop-side) REPO="$REPO_REMOTE"; SHARE="$SHARE_REMOTE"; W="$W_LAPTOP" ;;
  *) echo "FATAL: bad role '$ROLE' (local | laptop-side)" >&2; exit 2 ;;
esac
HOST="$(hostname)"
PY="$REPO/.venv/bin/python"
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
DIR="$REPO/measurement/tiearb_widening_20260817/b64_cell"
SHARE_RUN="$SHARE/$RUN_ID"
OUT="$SHARE_RUN"
LOGS="$DIR/logs"

if [ "$SMOKE" -eq 1 ]; then
  # §9.1: production knobs — ONLY the game count differs. §9.1's condition of
  # acceptance: the throwaway band DECLARES ITSELF throwaway and is NEVER claimed.
  N="$N_SMOKE"; BAND="${BAND:-$SMOKE_BAND}"; TAG=smoke
  case "$ROLE" in local) W="$W_SMOKE_LOCAL" ;; *) W="$W_SMOKE_LAPTOP" ;; esac
  OUT="$SHARE_RUN/smoke"
else
  N="$N_GAMES"; TAG=cells
fi

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[run_cells $(ts) $HOST/$ROLE] $*"; }

# --------------------------------------------------------------------------- #
# the argv for ONE cell — built ONCE so the dry-run prints EXACTLY what runs    #
# --------------------------------------------------------------------------- #
cell_argv() {   # $1 = cell name, $2 = B, $3 = out-subdir
  local NAME="$1" B="$2" SUB="$3"
  ARGV=(nice -n "$NICE" "$PY" -u "$HARNESS"
        --info fair --opponent fair-champion --backend rust
        --k-dets "$K_DETS" --sims "$SIMS"
        --opp-k-dets "$K_DETS" --opp-sims "$SIMS" --exact-k "$EXACT_K"
        --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
        --n "$N" --paired --seed-start "$BAND"
        --rules-profile "$RULES_PROFILE" --workers "$W"
        --out-root "$OUT" --out-subdir "$SUB"
        --shared-claim --claim-host "b64-$NAME-$HOST" --claim-stale-secs 1800
        --no-results-csv
        --cand-tiearb-enabled
        --cand-tiearb-b "$B"
        --cand-tiearb-j "$TIEARB_J"
        --cand-tiearb-mode "$TIEARB_MODE"
        --cand-tiearb-salt "$TIEARB_SALT"
        --cand-tiearb-eps "$TIEARB_EPS")
}

require_preflight() {
  local missing=0 f
  for B in "$TIEARB_B_WIDE" "$TIEARB_B_NARROW"; do
    f="$DIR/verdicts/PREFLIGHT_${HOST}_FIRST_B${B}.json"
    [ -f "$f" ] || { log "!!! G-J13: MISSING $f"; missing=1; }
  done
  [ "$missing" -eq 0 ] || {
    log "!!! REFUSING TO LAUNCH: run ./preflight.sh on THIS host first — it must"
    log "!!! pass at BOTH B values before this host's game 1 (READ_RULE §3 G-J13)."
    exit 13; }
}

# --------------------------------------------------------------------------- #
main() {
  mkdir -p "$LOGS" "$OUT"
  [ -n "$BAND" ] || { log "!!! FATAL: no band. The EXECUTOR claims it from"
                      log "!!! governance/BAND_REGISTRY.csv BEFORE game 1 and passes"
                      log "!!! it with --band; this script never claims or invents one"
                      log "!!! (READ_RULE §3 G-BAND)."; exit 2; }
  if [ "$SMOKE" -eq 1 ] && [ "$BAND" != "$SMOKE_BAND" ]; then
    log "!!! FATAL: the smoke runs on the THROWAWAY band $SMOKE_BAND only"; exit 2
  fi
  if [ "$SMOKE" -eq 0 ] && [ "$BAND" = "$SMOKE_BAND" ]; then
    log "!!! FATAL: the throwaway band may never carry a real cell"; exit 2
  fi

  log "role=$ROLE W=$W N=$N band=$BAND tag=$TAG out=$OUT"
  log "blind_commit=$BLIND_COMMIT  champion_leaf_hash=$CHAMP_LEAF_HASH"
  log "⭐ the two cells differ in EXACTLY ONE argument: --cand-tiearb-b"

  [ "$DRY" -eq 1 ] || [ "$SMOKE" -eq 1 ] || require_preflight

  for pair in "$CELL_WIDE:$TIEARB_B_WIDE:$CELL_SUBDIR_WIDE" \
              "$CELL_NARROW:$TIEARB_B_NARROW:$CELL_SUBDIR_NARROW"; do
    IFS=: read -r NAME B SUB <<< "$pair"
    [ "$SMOKE" -eq 1 ] && SUB="smoke_$SUB"
    cell_argv "$NAME" "$B" "$SUB"
    if [ "$DRY" -eq 1 ]; then
      printf '[dry-run] cell %s (B=%s):' "$NAME" "$B"
      printf ' %q' "${ARGV[@]}"
      printf '\n'
      continue
    fi
    if [ -f "$DIR/DONE_${TAG}_$NAME" ]; then
      log "cell $NAME already DONE — skipping"; continue
    fi
    log "cell $NAME (B=$B) -> $OUT/$SUB"
    "${ARGV[@]}" >> "$LOGS/${TAG}_$NAME.log" 2>&1 || \
      log "cell $NAME rc=$? (the harness is resumable under --shared-claim)"
    touch "$DIR/DONE_${TAG}_$NAME"
  done

  if [ "$DRY" -eq 1 ]; then
    printf '[dry-run] smoke gate check:'
    printf ' %q' "$PY" "$REPO/scripts/tiletie/analyze_b64_cell.py" smoke-check \
                 --smoke "$SHARE_RUN/smoke/SMOKE.json"
    printf '\n'
    printf '[dry-run] HALT bar (§9.3, one-sided): realized WIDE worker_secs_per_game > %s x %s = %s\n' \
           "$SMOKE_HALT_MULTIPLE" "$WORKER_S_COMMITTED_WIDE" "$SMOKE_HALT_BAR"
    return 0
  fi

  if [ "$SMOKE" -eq 1 ]; then
    log "--- §9.2 whitelist + §9.3 HALT bar ---"
    "$PY" "$REPO/scripts/tiletie/analyze_b64_cell.py" smoke-check \
      --smoke "$SHARE_RUN/smoke/SMOKE.json" || {
        log "!!! §9.2 REFUSAL: SMOKE.json carries a key outside the counts-and-cost"
        log "!!! whitelist. The smoke may not read an outcome."; exit 9; }
    log "HALT bar: realized WIDE worker_secs_per_game > $SMOKE_HALT_BAR ⇒ HALT"
    log "⚠️ ONE-SIDED: an overrun HALTS, an underrun proceeds. On a HALT the real"
    log "⚠️ cells are NOT launched and the decision returns to the owner."
  fi
  log "DONE tag=$TAG"
}

main "$@"
