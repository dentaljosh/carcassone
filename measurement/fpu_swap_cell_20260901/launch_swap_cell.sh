#!/usr/bin/env bash
# =========================================================================== #
# launch_swap_cell.sh — THE FPU-INSTEAD-OF-THE-ARBITER SWAP CELL LAUNCHER      #
#                                                                             #
# ⛔⛔ THE ROUND IS UNLAUNCHED. This script REFUSES a real chunk until:         #
#       * screen_lib.sanity_check() is non-empty              -> REFUSE       #
#       * adjudicate_swap_cell.py --selftest FAILS             -> REFUSE       #
#       * this box's W is not the frozen laptop value (24)     -> REFUSE       #
#       * BLIND_COMMIT.json still reads "PENDING"              -> REFUSE       #
#       * the sibling BAND_CLAIMED file does not exist         -> REFUSE       #
#       * PINNED_SRC_REV is absent or does not name HEAD       -> REFUSE       #
#       * a code path is dirty (src/ , engine/ , this dir)     -> REFUSE       #
#     --dry-run and --smoke are EXEMPT from BLIND_COMMIT and BAND_CLAIMED:     #
#     they spend no blindness and no band (the smoke plays the THROWAWAY       #
#     range only). --dry-run additionally spends no compute at all.            #
#                                                                             #
# USAGE                                                                       #
#   ./launch_swap_cell.sh --smoke              # production knobs, 8 games,   #
#                                               # throwaway seeds, adjudicated #
#   ./launch_swap_cell.sh --dry-run            # print the real command, run   #
#                                               # nothing                      #
#   ./launch_swap_cell.sh                      # THE REAL CELL — 400 decks x   #
#                                               # 2 seatings = 800 games        #
#                                                                             #
# ⚠️ LAUNCH DETACHED for the real cell. Joshua's Mac->Windows->WSL setup means #
#    Mac-sleep SIGHUP AND WSL VM-teardown both kill tty-attached jobs:         #
#      setsid nohup nice -n 19 ./launch_swap_cell.sh >> swap_cell.log 2>&1 &   #
#      disown                                                                 #
#    From the DESKTOP box, over ssh to the laptop:                            #
#      ssh laptop 'bash -s' < launch_swap_cell.sh -- --smoke                  #
#    (the inline `ssh host 'cd .. && ..'` form gets the cd STRIPPED IN         #
#    TRANSIT — feedback_remote_ssh_pipe_script_mandatory; this script never    #
#    relies on the remote shell's starting cwd, only on $BASH_SOURCE).         #
# =========================================================================== #
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

# ⚠️ Frozen constants live in screen_lib.py — this script re-derives NOTHING
# numeric; it reads them back via a python probe so the launcher and the
# adjudicator can never drift apart.
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python found" >&2; exit 2; }

DRY=0; SMOKE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --) shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

STAMP() { echo "[launch_swap_cell $(date -u +%FT%TZ) $(hostname)] $*"; }
DIE() { STAMP "!!! $*"; exit 13; }

# --------------------------------------------------------------------------- #
# 0. PRECONDITIONS — screen_lib is law                                        #
# --------------------------------------------------------------------------- #
"$PY" -c "
import sys; sys.path.insert(0, '$HERE')
import screen_lib as L
bad = L.sanity_check()
if bad:
    print('⛔⛔ screen_lib.sanity_check() FAILED:')
    for b in bad:
        print(' -', b)
    sys.exit(1)
print('[probe] screen_lib sanity OK — BAR_SWAP', L.BAR_SWAP,
      'SE_400', round(L.SE_400, 4), 'PROPOSED_BAND', L.PROPOSED_BAND)
" || DIE "screen_lib.sanity_check() is not clean — fix the library before launching"

"$PY" "$HERE/adjudicate_swap_cell.py" --selftest \
  || DIE "adjudicate_swap_cell.py --selftest FAILED — a broken adjudicator " \
         "voids every branch it would ever adjudicate"

# ⚠️ W is THROUGHPUT-ONLY per this tree's standing convention — no gate, bar or
# branch reads it. It is checked anyway because a smoke run at a W the box will
# not run for the real cell is a smoke of a different tenancy
# (feedback_no_agent_compute_beside_eval quantified a 1.8x/move inflation from
# ONE stray niced core).
W="${W_LAPTOP:-24}"   # owner ruling 2026-09-01: laptop logical threads = 24
if [ "$W" -ne 24 ]; then
  STAMP "⚠️ W=$W (not the frozen 24) — throughput-only, proceeding, but the "
        "smoke/real cell are not tenancy-comparable to each other unless W matches"
fi

STAMP "process census (FULL ARGS):"
ps -eo pid,etime,pcpu,args --sort=-etime 2>/dev/null | grep -E "python|carc" \
  | grep -v grep | head -20 | sed 's/^/    /'

export CARCASSONNE_FIX_R9=1        # ⚠️ env-latched at IMPORT
export PYTHONUNBUFFERED=1

BLIND_COMMIT="$("$PY" -c "
import json
print(json.load(open('$HERE/BLIND_COMMIT.json'))['blind_commit'])
")"

# --------------------------------------------------------------------------- #
# freeze-latch sentinel (auto-memory: reference_freeze_latch_hook)             #
# --------------------------------------------------------------------------- #
# Present for the lifetime of any real compute this script does (SMOKE or the
# real cell); removed on clean exit via the trap. NOT dropped for --dry-run,
# which spends no compute at all. A STALE sentinel (crashed run) must only be
# cleaned after confirming the run is actually dead — never blind-deleted.
if [ "$DRY" -eq 0 ]; then
  TAG="$([ "$SMOKE" -eq 1 ] && echo SMOKE || echo CELL_SWAP)"
  LIVE="$HERE/RUN_LIVE_${TAG}.json"
  "$PY" -c "
import json, socket
from datetime import datetime, timezone
json.dump({'tag': '$TAG', 'smoke': $SMOKE, 'host': socket.gethostname(),
           'started_at': datetime.now(timezone.utc).isoformat(),
           'repo': '$REPO', 'what': 'fpu_swap_cell_20260901 — fpu-alone '
           '(arb-off) candidate vs arb-alone (B64-armed) opponent, direct '
           'head-to-head, the shape declined-by-arithmetic on '
           'docs/LEVER_INDEX.md'},
          open('$LIVE', 'w'), indent=2)
"
  trap 'rm -f "$LIVE"' EXIT
fi

# --------------------------------------------------------------------------- #
# 1. THE ONE CELL — run_cell()                                                #
# --------------------------------------------------------------------------- #
# ⛔⛔ THE SINGLE VARIABLE, and the ASYMMETRIC ARBITER, in one function.
# ⚠️ `fpu` is a positional so the SMOKE and IDENT legs (if ever added) can drop
# it exactly the way fpu_h2h_r2_prep's run_cell does — a real cell NEVER passes
# an empty fpu.
run_cell() {
  local name="$1" seed_start="$2" n_games="$3" fpu="$4" out_root="$5"
  local out="$out_root/$name"
  [ "$DRY" -eq 1 ] || mkdir -p "$out"   # --dry-run spends no compute, no I/O
  local args=(
    "$REPO/scripts/classical_search/eval_fair_puct.py"
    --backend rust --info fair
    --k-dets 16 --sims 1376 --opp-k-dets 16 --opp-sims 1376
    --exact-k 2
    --opponent fair-champion
    # ⛔⛔ WITHOUT --paired the round has no primary: _build_work returns n
    # DISTINCT decks at ONE seat each, n_paired = 0.
    --n "$n_games" --paired --seed-start "$seed_start"
    --workers "$W" --out-root "$out_root" --out-subdir "$name"
    --rules-profile fixed_v1
    # ⭐⭐ THE ASYMMETRY. Note there is NO --cand-tiearb-* flag anywhere in this
    # function — the candidate seat is unarmed by ABSENCE, the harness's own
    # convention for "this seat did not arbitrate" (tiearb_gates.py).
    --opp-tiearb-enabled --opp-tiearb-b 64 --opp-tiearb-j 4
    --opp-tiearb-mode argmax --opp-tiearb-salt tiearb2-deploy-v1
    --opp-tiearb-eps 0.0 --opp-tiearb-phase-gate all
  )
  if [ -n "$fpu" ]; then
    args+=(--cand-fpu-reduction "$fpu")
  fi
  if [ "$BLIND_COMMIT" != "PENDING" ]; then
    args+=(--stamp-key "BLIND_COMMIT=$BLIND_COMMIT")
  fi
  case "$name" in
    SMOKE_*) args+=(--allow-selfplay-seeds) ;;  # the throwaway range is
                                                 # outside every registered
                                                 # clean-eval band, on purpose
  esac
  if [ "$DRY" -eq 1 ]; then
    STAMP "[dry-run] $name fpu=${fpu:-NONE} k16x1376 seeds=${seed_start}.. n=$n_games -> $out"
    printf '    %q ' "$PY" "${args[@]}"; echo
    return 0
  fi
  STAMP "$name fpu=${fpu:-NONE} k16x1376 seeds=${seed_start}.. n=$n_games W=$W -> $out"
  nice -n 19 "$PY" "${args[@]}" || DIE "$name FAILED"
}

# --------------------------------------------------------------------------- #
# 2. --smoke: production knobs, throwaway seeds, 8 games, self-adjudicated    #
# --------------------------------------------------------------------------- #
if [ "$SMOKE" -eq 1 ]; then
  THROWAWAY_BASE="$("$PY" -c "
import sys; sys.path.insert(0,'$HERE'); import screen_lib as L
print(L.THROWAWAY_BASE)")"
  SHARE="${SHARE:-/mnt/carc-shared}"   # laptop path; local would be /mnt/c/carc-shared
  OUT_ROOT="$SHARE/fpu_swap_cell_smoke"
  SMOKE_NAME="SMOKE_laptop"
  SMOKE_SEED=$((THROWAWAY_BASE))
  SMOKE_GAMES=8

  run_cell "$SMOKE_NAME" "$SMOKE_SEED" "$SMOKE_GAMES" "0.2" "$OUT_ROOT"

  if [ "$DRY" -eq 0 ]; then
    "$PY" "$HERE/adjudicate_swap_cell.py" --smoke-mode \
      --root "$OUT_ROOT/$SMOKE_NAME" --out "$HERE/SMOKE_laptop.json" \
      || DIE "the smoke adjudication FAILED — the emitted manifest does not " \
             "carry the asymmetric arb/fpu shape this launcher requested"
    STAMP "smoke adjudicated -> SMOKE_laptop.json — review it by hand before " \
          "the real cell plays: candidate fpu=0.2 arb-UNARMED, opponent " \
          "fpu=null arb-ARMED-AND-FIRED"
  fi
  STAMP "SMOKE DONE"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 3. THE REAL CELL — refused until claimed + stamped                          #
# --------------------------------------------------------------------------- #
if [ "$DRY" -eq 0 ]; then
  [ -f "$HERE/BAND_CLAIMED" ] \
    || DIE "BAND_CLAIMED does not exist — see BAND_CLAIMED.placeholder. " \
           "This agent proposed a band; it did NOT claim one."
  [ "$BLIND_COMMIT" != "PENDING" ] \
    || DIE "BLIND_COMMIT.json still reads PENDING — stamp the freeze " \
           "commit's 40-hex sha first (a commit cannot name its own hash, so " \
           "this is a mandatory SECOND commit, not an oversight)."
  PINNED_SRC_REV_FILE="$HERE/PINNED_SRC_REV"
  [ -f "$PINNED_SRC_REV_FILE" ] \
    || DIE "PINNED_SRC_REV is absent — stamp it (git -C \"$REPO\" rev-parse HEAD) " \
           "before a real chunk plays."
  PINNED="$(cat "$PINNED_SRC_REV_FILE")"
  HEAD="$(git -C "$REPO" rev-parse HEAD)"
  [ "$PINNED" = "$HEAD" ] \
    || DIE "PINNED_SRC_REV ($PINNED) != HEAD ($HEAD) — re-pinning mid-round is " \
           "NOT the fix (it creates a cross-cell rev split); resolve by hand."
  DIRTY="$(git -C "$REPO" status --porcelain -- src engine \
           scripts/classical_search "$HERE" 2>/dev/null)"
  [ -z "$DIRTY" ] \
    || DIE "the code path is DIRTY: $DIRTY — commit or stash before a real " \
           "chunk plays (blindness protection)."
fi

if [ -f "$HERE/BAND_CLAIMED" ]; then
  CLAIMED_BAND="$("$PY" -c "
import re
m = re.search(r'BAND CLAIMED:\s*(\d+)', open('$HERE/BAND_CLAIMED').read())
print(m.group(1) if m else '')
" 2>/dev/null)"
  [ -n "$CLAIMED_BAND" ] || DIE "BAND_CLAIMED exists but no band id could be parsed out of it"
elif [ "$DRY" -eq 1 ]; then
  # ⚠️ --dry-run has no claimed band yet (that is normal, pre-launch) — fall
  # back to screen_lib's PROPOSED band purely so the printed command shape is
  # inspectable. This is NEVER reached for a real chunk (guarded above).
  CLAIMED_BAND="$("$PY" -c "
import sys; sys.path.insert(0,'$HERE'); import screen_lib as L
print(L.PROPOSED_BAND)")"
  STAMP "[dry-run] BAND_CLAIMED does not exist yet — using the PROPOSED band " \
        "$CLAIMED_BAND for this preview only; the real launch will refuse " \
        "until it is actually claimed"
else
  DIE "BAND_CLAIMED does not exist — see BAND_CLAIMED.placeholder"
fi

SHARE="${SHARE:-/mnt/carc-shared}"
OUT_ROOT="$SHARE/fpu_swap_cell_20260901"
CELL_NAME="CELL_SWAP"
out="$OUT_ROOT/$CELL_NAME"
if [ -f "$out/DONE" ]; then
  STAMP "$CELL_NAME already DONE — nothing to do"
  exit 0
fi

run_cell "$CELL_NAME" "$CLAIMED_BAND" 800 "0.2" "$OUT_ROOT"

if [ "$DRY" -eq 0 ]; then
  touch "$out/DONE"
  STAMP "$CELL_NAME complete -> $out. Adjudicate with:"
  STAMP "  $PY $HERE/adjudicate_swap_cell.py --root $out --pinned-src-rev $HEAD --out $HERE/VERDICT.json"
fi
