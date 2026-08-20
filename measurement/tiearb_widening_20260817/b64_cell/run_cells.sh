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

# ---- W-FREEZE-LATCH sentinel (DEVIATIONS D5 (b)) -----------------------------
# ⭐ Dropped at leg start, cleared at close-out AND on any exit (trap), so an
# abort can never leave the tree latched. The PreToolUse latch
# (scripts/hooks/pretooluse_lint.py) refuses a MAIN-TREE commit while it exists.
# It is a FILE, not a convention: it is visible to WHOEVER commits, which is the
# point — the freeze discipline has failed twice and both times at the
# orchestrator's hands, not a builder's or an executor's.
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("W-FREEZE-LATCH sentinel (DEVIATIONS D5 (b)): a MAIN-TREE "
                   "commit while this leg is live can put two revisions into "
                   "one run — spawn respawns and each new --shared-claim cell "
                   "RE-IMPORT FROM DISK. Cleared at close-out and on any exit."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  echo "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

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

  if [ "$DRY" -eq 0 ]; then
    trap 'run_live_clear' EXIT INT TERM
    run_live_drop "b64_cell $TAG leg (role=$ROLE)"
  fi

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
    printf '[dry-run] smoke aggregation:'
    printf ' %q' "$PY" "$REPO/scripts/tiletie/analyze_b64_cell.py" aggregate-smoke \
                 --wide-dir "$SHARE_RUN/smoke/smoke_$CELL_SUBDIR_WIDE" \
                 --narrow-dir "$SHARE_RUN/smoke/smoke_$CELL_SUBDIR_NARROW" \
                 --band "$SMOKE_BAND" --out "$SHARE_RUN/smoke/SMOKE.json"
    printf '\n'
    printf '[dry-run] smoke gate check:'
    printf ' %q' "$PY" "$REPO/scripts/tiletie/analyze_b64_cell.py" smoke-check \
                 --smoke "$SHARE_RUN/smoke/SMOKE.json"
    printf '\n'
    printf '[dry-run] HALT bar (§9.3, one-sided): realized WIDE worker_secs_per_game > %s x %s = %s\n' \
           "$SMOKE_HALT_MULTIPLE" "$WORKER_S_COMMITTED_WIDE" "$SMOKE_HALT_BAR"
    return 0
  fi

  if [ "$SMOKE" -eq 1 ]; then
    # ---- THE AGGREGATION STEP ------------------------------------------------
    # ⭐ It did not exist, so §9.3 never evaluated: this block called smoke-check
    # on a SMOKE.json that NOTHING wrote, and the per-cell manifests carry none
    # of §9.2's whitelist fields — `worker_secs_per_game`, the single quantity
    # the HALT bar is defined on, was emitted nowhere. The aggregator reads the
    # two cells' OWN per-game records and computes it by DESIGN §7.1's own
    # equation (Σ elapsed_s / n).
    log "--- §9 aggregation: the two smoke cells -> SMOKE.json ---"
    set +e
    "$PY" "$REPO/scripts/tiletie/analyze_b64_cell.py" aggregate-smoke \
      --wide-dir "$SHARE_RUN/smoke/smoke_$CELL_SUBDIR_WIDE" \
      --narrow-dir "$SHARE_RUN/smoke/smoke_$CELL_SUBDIR_NARROW" \
      --band "$SMOKE_BAND" \
      --out "$SHARE_RUN/smoke/SMOKE.json"
    agg_rc=$?
    set -e
    if [ "$agg_rc" -ne 0 ]; then
      # ⚠️ NAME THE ACTUAL CONDITION. The aggregator prints its own refusal —
      # missing records, an unreadable record, a whitelist-external key, an
      # outcome key. Do NOT restate it as something else.
      log "!!! AGGREGATION REFUSED (rc=$agg_rc) — the aggregator's own message is"
      log "!!! above and names the actual condition. This launcher does not"
      log "!!! re-attribute it."
      exit 9
    fi

    # ---- §9.2's whitelist, on the artifact that now exists -------------------
    log "--- §9.2 whitelist check ---"
    set +e
    "$PY" "$REPO/scripts/tiletie/analyze_b64_cell.py" smoke-check \
      --smoke "$SHARE_RUN/smoke/SMOKE.json"
    chk_rc=$?
    set -e
    if [ "$chk_rc" -ne 0 ]; then
      # ⚠️ SAME SHAPE AS THE PREFLIGHT'S OLD G-J13 MISATTRIBUTION, and it bit
      # here too: this line used to assert "whitelist violation" for ANY nonzero
      # exit — and the real cause was a MISSING FILE. The checker prints the
      # failing condition itself; propagate it, never re-label it.
      if [ ! -f "$SHARE_RUN/smoke/SMOKE.json" ]; then
        log "!!! SMOKE.json is ABSENT at $SHARE_RUN/smoke/SMOKE.json — that is a"
        log "!!! MISSING ARTIFACT, not a whitelist violation."
      else
        log "!!! smoke-check REFUSED (rc=$chk_rc) — its own message above names"
        log "!!! the condition (a key outside §9.2's counts-and-cost whitelist,"
        log "!!! or an unreadable artifact). This launcher does not re-attribute it."
      fi
      exit 9
    fi

    log "HALT bar (§9.3): realized WIDE worker_secs_per_game > $SMOKE_HALT_BAR ⇒ HALT"
    log "⚠️ ONE-SIDED: an overrun HALTS, an underrun proceeds. On a HALT the real"
    log "⚠️ cells are NOT launched and the decision returns to the owner."
    log "⚠️ This launcher REPORTS the comparison; it adjudicates nothing."
  fi
  run_live_clear
  log "DONE tag=$TAG"
}

main "$@"
