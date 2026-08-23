#!/usr/bin/env bash
# =============================================================================
# > DRAFT -- NOT BLIND-COMMITTED -- NOT LAUNCHED. Prepared 2026-08-23 under
# > docs/TRACK_D_PREP_2026-08-23.md. No band is claimed, no games have been
# > played, no owner authorization exists. The blind-commit discipline (freeze
# > the pair, commit it, stamp BLIND_COMMIT=<sha> before game 1) is DEFERRED to
# > the orchestrator -- nothing here may be cited as a pre-registration until
# > that commit exists.
#
# run_cells_DRAFT.sh -- D2 RUNG-COMPRESSION CELL LAUNCHER (DRAFT).
# CELL R800 (--rung-sims 800) and CELL R1600 (--rung-sims 1600), deck-paired
# on ONE band and THE SAME 200 decks, against a frozen fair-PIMC probe
# (k4x688=2752, tie-arbiter OFF), vs the frozen HeuristicMCTS(h800) rung.
#
#   run_cells_DRAFT.sh <local|laptop-side> [--pilot] [--dry-run] [--band <SEED_START>]
#
# See measurement/track_d2_prep/DESIGN.md and READ_RULE.md for the full design
# and the read-out branches. This launcher is modeled closely on
# measurement/tiearb_widening_20260817/b32v64_cell/run_cells.sh -- read that
# for the house shape; this file does not reproduce all of it.
#
# ⭐ THE TWO REAL CELLS DIFFER IN EXACTLY ONE EXPERIMENTAL ARGUMENT --
# `--rung-sims`. That is the whole design (DESIGN §3): both cells' argv are
# built from ONE shared COMMON array below, so the single-variable property is
# STRUCTURAL, not clerical -- nobody has to remember to keep them in sync.
# (The two argv also differ in `--out-subdir` and `--claim-host`, which are
# BOOKKEEPING: two cells cannot share one output directory or one
# `--shared-claim` claim tag without corrupting each other. Same shape as
# b32v64_cell/run_cells.sh's own note about itself.)
#
# ⛔ THIS FILE IS LEFT NON-EXECUTABLE (mode 644) DELIBERATELY. It is a DRAFT.
# The orchestrator `chmod +x` this file only when authorizing a real launch,
# after BLIND_COMMIT and BAND_CLAIMED (below) are both real, not placeholders.
#
# PRECONDITIONS, IN ORDER, ENFORCED BY THIS SCRIPT:
#   0. BLIND_COMMIT (a file in this directory, 40 hex chars, no trailing
#      newline content beyond the hash) exists and is not a placeholder.
#   1. BAND_CLAIMED (a file in this directory) exists -- the EXECUTOR drops it
#      after appending BAND_CLAIM_DRAFT.json's row to
#      governance/BAND_REGISTRY.csv. This script NEVER claims or invents a
#      band; it only checks that someone else already did.
#   2. --band, if given, must equal PINNED_BAND -- it may only CONFIRM the
#      pinned value, never shadow it. A given --band that disagrees is FATAL.
#   3. --dry-run and --pilot are EXEMPT from preconditions 0-1: neither spends
#      blindness or a real band. The pilot burns a disjoint throwaway seed
#      range (§9 of DESIGN.md) that is discarded and never pooled; --dry-run
#      starts nothing at all.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached
# jobs -- launch as:
#   setsid nohup ./run_cells_DRAFT.sh local </dev/null >/dev/null 2>&1 & disown
# =============================================================================
set -euo pipefail

REPO=/home/doctor/projects/carcassone
DIR="$REPO/measurement/track_d2_prep"
PY="$REPO/.venv/bin/python"
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
LOGS="$DIR/logs"

# the band pinned by the pair -- --band may only CONFIRM this, never shadow it
PINNED_BAND=141000000000
PILOT_SEED_START=141999999000   # DISJOINT throwaway range, DESIGN §9; never pooled, never claimed

ROLE="${1:?usage: run_cells_DRAFT.sh <local|laptop-side> [--pilot] [--dry-run] [--band SEED_START]}"
shift || true
PILOT=0; DRY=0; BAND=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --pilot)   PILOT=1 ;;
    --dry-run) DRY=1 ;;
    --band)    BAND="${2:?--band needs a seed start}"; shift ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

# --band may only CONFIRM the pinned band, never override it (b32v64_cell precedent)
if [ -n "$BAND" ] && [ "$PILOT" -eq 0 ] && [ "$BAND" != "$PINNED_BAND" ]; then
  echo "FATAL: --band $BAND disagrees with the pair's PINNED_BAND=$PINNED_BAND." >&2
  echo "FATAL: this launcher never accepts a different band for a real cell --" >&2
  echo "FATAL: if the band must change, the PAIR changes (DESIGN §5 + BAND_CLAIM_DRAFT.json)." >&2
  exit 2
fi
BAND="${BAND:-$PINNED_BAND}"

case "$ROLE" in
  local)       SHARE=/mnt/c/carc-shared;   W=22 ;;
  laptop-side) SHARE=/mnt/carc-shared;     W=16 ;;
  *) echo "FATAL: bad role '$ROLE' (local | laptop-side)" >&2; exit 2 ;;
esac
# ⚠️ W is PER-BOX and NOT extrapolated -- these are the launch-brief defaults
# (local 22, laptop 16). Re-bench after any code-era change (repo standing
# rule); the h-rung side of every cell is Python by design (DESIGN §3.3), so
# the worker mix here is NOT the same profile as an all-rust cell -- do not
# reuse a W tuned for an all-rust harness invocation without re-checking.
HOST="$(hostname)"
OUT="$SHARE/track_d2_prep"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[run_cells_DRAFT $(ts) $HOST/$ROLE] $*"; }

# --------------------------------------------------------------------------- #
# ONE shared COMMON array -- both real cells' argv are built by extending it, #
# so "the two cells differ in exactly --rung-sims" is STRUCTURAL, not         #
# clerical (DESIGN §3, §7 G-SINGLEVAR).                                       #
# --------------------------------------------------------------------------- #
build_common() {
  # ⚠️ --n 400: the harness's --n counts GAMES; --paired gives 2 seatings per
  # deck, so --n 400 = 200 DECKS. This matches fair_ruler_rebase_2752's own
  # manifest (n: 400, n_paired: 200). DO NOT "fix" this to 200 -- that would
  # halve the deck set DESIGN §4/§5 costed and gated.
  COMMON=(--info fair --opponent h800 --backend rust
          --k-dets 4 --sims 1032 --exact-k 2
          --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
          --n 400 --paired --seed-start "$BAND"
          --rules-profile fixed_v1 --workers "$W"
          --out-root "$OUT"
          --shared-claim --claim-stale-secs 1800
          --no-results-csv)
}

# $1 = cell name (R800|R1600), $2 = rung-sims, $3 = out-subdir
cell_argv() {
  local NAME="$1" RS="$2" SUB="$3"
  build_common
  ARGV=(nice -n 19 "$PY" -u "$HARNESS" "${COMMON[@]}"
        --rung-sims "$RS"
        --out-subdir "$SUB"
        --claim-host "d2-$NAME-$HOST")
}

# --------------------------------------------------------------------------- #
# hard refuse-to-run guard -- BLIND_COMMIT + BAND_CLAIMED, both real files.   #
# --dry-run and --pilot are exempt: neither spends blindness (no real cell    #
# statistic exists yet) nor touches the claimed band (the pilot's range is    #
# disjoint and never claimed at all).                                        #
# --------------------------------------------------------------------------- #
require_blind_and_band() {
  local bc="$DIR/BLIND_COMMIT" bcl="$DIR/BAND_CLAIMED"
  if [ ! -f "$bc" ] || ! grep -qE '^[0-9a-f]{40}$' "$bc"; then
    log "!!! FATAL: $bc is missing or does not hold a 40-hex-char sha."
    log "!!! The EXECUTOR writes it AFTER DESIGN.md + READ_RULE.md land on main."
    log "!!! (--dry-run and --pilot are exempt -- neither spends blindness.)"
    exit 2
  fi
  if [ ! -f "$bcl" ]; then
    log "!!! FATAL: $bcl is missing."
    log "!!! The EXECUTOR drops it AFTER appending BAND_CLAIM_DRAFT.json's row"
    log "!!! to governance/BAND_REGISTRY.csv. This script never claims a band."
    log "!!! (--dry-run and --pilot are exempt -- the pilot band is never claimed.)"
    exit 2
  fi
}

# --------------------------------------------------------------------------- #
# RUN_LIVE.json freeze-latch sentinel -- the repo's PreToolUse hook refuses a #
# MAIN-TREE git commit while this file exists (feedback_worktree_isolation /  #
# the freeze-latch discipline). Dropped at real-cell launch, cleared on ANY   #
# exit via trap so an abort never leaves the tree latched. NEVER dropped on   #
# --dry-run (no games start, so nothing needs freezing).                     #
# --------------------------------------------------------------------------- #
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("D2 rung-compression cell freeze-latch sentinel: a MAIN-TREE "
                   "commit while this leg is live risks two revisions in one "
                   "run. Cleared on the launcher's EXIT trap."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  log "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

print_dry_run() {
  local name="$1" rs="$2" sub="$3"
  cell_argv "$name" "$rs" "$sub"
  printf '[dry-run] cell %s (rung-sims=%s):' "$name" "$rs"
  printf ' %q' "${ARGV[@]}"
  printf '\n'
}

print_cost_estimate() {
  cat <<'EOF'
[dry-run] cost estimate (DESIGN §6, from realized per-game records):
[dry-run]   CELL R800   ~58.6 s/game x 400 games = 23,440 core-s = 6.5 core-h
[dry-run]   CELL R1600  ~86.1 s/game x 400 games = 34,440 core-s = 9.6 core-h
[dry-run]   TOTAL       ~16.1 core-hours  (local W22 => ~0.75 h wall; W16 => ~1.0 h wall)
[dry-run]   R1600 is rung-dominated: the ~8x rust probe speedup does NOT shrink
[dry-run]   the Python-by-design rung side (DESIGN §3.3/§6).
EOF
}

run_pilot() {
  log "PILOT -- CELL R800 config only, n=16 (8 decks x 2 seatings), seed-start=$PILOT_SEED_START"
  log "PILOT band is DISCARDED and never pooled with the real cell band (DESIGN §9)."
  local sub="pilot_r800"
  build_common
  # override --n and --seed-start for the pilot; everything else matches CELL R800
  local PARGV=(nice -n 19 "$PY" -u "$HARNESS"
        --info fair --opponent h800 --backend rust
        --k-dets 4 --sims 1032 --exact-k 2
        --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
        --n 16 --paired --seed-start "$PILOT_SEED_START"
        --rules-profile fixed_v1 --workers "$W"
        --out-root "$OUT" --out-subdir "$sub"
        --shared-claim --claim-stale-secs 1800
        --claim-host "d2-pilot-$HOST"
        --no-results-csv
        --rung-sims 800)
  if [ "$DRY" -eq 1 ]; then
    printf '[dry-run] pilot argv:'
    printf ' %q' "${PARGV[@]}"
    printf '\n'
    return 0
  fi
  mkdir -p "$LOGS" "$OUT/$sub"
  "${PARGV[@]}" >> "$LOGS/pilot_r800.log" 2>&1 || \
    log "pilot rc=$? (the harness is resumable under --shared-claim)"
  log "PILOT DONE -- checking summary.json for the equal-time ratio (DESIGN §9 / §7 G-TIMING)"
  "$PY" - "$OUT/$sub" <<'PEOF'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1])
cands = sorted(d.glob("**/summary.json"))
if not cands:
    print("[pilot] !!! no summary.json found under", d); sys.exit(1)
s = json.load(open(cands[-1]))
champ_ms = s.get("champ_prefix_ms_per_move")
rung_ms = s.get("rung_ms_per_move")
if champ_ms is None or rung_ms is None:
    print("[pilot] !!! summary.json missing champ_prefix_ms_per_move or rung_ms_per_move"); sys.exit(1)
ratio = champ_ms / rung_ms
lo, hi = 0.85, 1.20
ok = lo <= ratio <= hi
print(f"[pilot] champ_prefix_ms_per_move={champ_ms:.3f} rung_ms_per_move={rung_ms:.3f} ratio={ratio:.4f}")
print(f"[pilot] bar=[{lo},{hi}]  =>  {'PASS' if ok else 'FAIL -- re-pick --sims ONCE on the pilot, before any cell band is touched'}")
sys.exit(0 if ok else 1)
PEOF
}

main() {
  if [ "$PILOT" -eq 1 ]; then
    run_pilot
    return 0
  fi

  if [ "$DRY" -eq 1 ]; then
    log "role=$ROLE W=$W band=$BAND (dry-run: no games start, no guards enforced beyond argv construction)"
    print_dry_run R800  800  d2_rung800
    print_dry_run R1600 1600 d2_rung1600
    print_cost_estimate
    return 0
  fi

  require_blind_and_band
  log "role=$ROLE W=$W band=$BAND out=$OUT"
  log "⭐ the two real cells differ in EXACTLY ONE EXPERIMENTAL argument: --rung-sims"
  log "⚠️ they also differ in --out-subdir and --claim-host, which are BOOKKEEPING"
  log "   (two cells cannot share one output dir or one --shared-claim tag)."

  mkdir -p "$LOGS" "$OUT"
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "d2 rung-compression cell (role=$ROLE)"

  for pair in "R800:800:d2_rung800" "R1600:1600:d2_rung1600"; do
    IFS=: read -r NAME RS SUB <<< "$pair"
    if [ -f "$DIR/DONE_cells_$NAME" ]; then
      log "cell $NAME already DONE -- skipping"; continue
    fi
    cell_argv "$NAME" "$RS" "$SUB"
    log "cell $NAME (rung-sims=$RS) -> $OUT/$SUB"
    "${ARGV[@]}" >> "$LOGS/cells_$NAME.log" 2>&1 || \
      log "cell $NAME rc=$? (the harness is resumable under --shared-claim)"
    touch "$DIR/DONE_cells_$NAME"
  done

  if [ -f "$DIR/DONE_cells_R800" ] && [ -f "$DIR/DONE_cells_R1600" ]; then
    run_live_clear
    log "DONE -- both cells complete, RUN_LIVE cleared"
  else
    log "one or more cells did not complete -- RUN_LIVE stays until both DONE sentinels exist"
  fi
}

main "$@"
