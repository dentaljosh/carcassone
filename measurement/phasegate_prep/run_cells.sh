#!/usr/bin/env bash
# =========================================================================== #
# run_cells.sh — THE PHASE-GATED TIE ARBITRATION ROUND'S LAUNCHER (Option A1)  #
#                                                                             #
# ⛔⛔ THE ROUND IS UNFUNDED AND UNLAUNCHED. This script REFUSES a real cell    #
#     until the orchestrator has done the pre-launch acts (DESIGN.md §8):      #
#       * BLIND_COMMIT is still the literal string PENDING   -> REFUSE         #
#       * the sibling BAND_CLAIMED file does not exist       -> REFUSE         #
#       * PINNED_SRC_REV is absent or does not name HEAD     -> REFUSE         #
#       * IDENT_BITEXACT.json is absent or not PASS          -> REFUSE         #
#     --dry-run and --smoke are EXEMPT from the first two: they spend no       #
#     blindness and no band (they play the THROWAWAY sub-range only).          #
#                                                                             #
# ⛔ THE PAIR IS LAW. Every cell shape, window, budget and box assignment is    #
#    read from screen_lib.py, which is imported by BOTH this launcher's        #
#    precondition ladder and the adjudicator — so a launcher/adjudicator drift #
#    is impossible by construction rather than by review.                      #
#                                                                             #
# ⚠️ W IS THROUGHPUT-ONLY. Games are bit-identical at any W and no gate in this #
#    pair reads a clock. W moves wall clock and nothing else.                  #
#                                                                             #
# USAGE                                                                       #
#   ./run_cells.sh --role local|laptop [--dry-run] [--smoke] [--cell NAME]     #
#                                                                             #
# ⚠️ LAUNCH DETACHED. Joshua's Mac->Windows->WSL setup means Mac-sleep SIGHUP  #
#    AND WSL VM-teardown both kill tty-attached jobs:                          #
#      setsid nohup ./run_cells.sh --role local >> log 2>&1 & disown           #
#    and on the laptop: ssh laptop 'bash -s' < run_cells.sh   (the inline      #
#    `ssh host 'cd .. && ..'` form gets the cd STRIPPED IN TRANSIT).           #
# =========================================================================== #
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
. "$HERE/WORKERS.conf"

ROLE=""; DRY=0; SMOKE=0; ONLY_CELL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --role) ROLE="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --cell) ONLY_CELL="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$ROLE" ] || { echo "--role local|laptop is required" >&2; exit 2; }

# ⚠️ The venv is editable-installed against the MAIN tree, so a copy of this
# script running from a git WORKTREE has no `.venv` beside it. Fall back to the
# canonical one rather than dying — the worktree case is a BUILD/dry-run case,
# and a real cell always runs from the main tree (which the rev pin re-asserts).
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python found" >&2; exit 2; }
case "$ROLE" in
  local)  W="$W_LOCAL";  SHARE="$SHARE_LOCAL" ;;
  laptop) W="$W_LAPTOP"; SHARE="$SHARE_LAPTOP" ;;
  *) echo "--role must be local|laptop" >&2; exit 2 ;;
esac
STAMP() { echo "[run_cells $(date -u +%FT%TZ) $(hostname)/$ROLE] $*"; }
DIE() { STAMP "!!! $*"; exit 13; }

STAMP "role=$ROLE W=$W band=$BAND tag=$OUT_TAG dry=$DRY smoke=$SMOKE"

# --------------------------------------------------------------------------- #
# 0. THE PRECONDITION LADDER                                                   #
# --------------------------------------------------------------------------- #
# ⭐ Resolved FROM screen_lib, never re-typed here — the launcher and the
# adjudicator read ONE cell table, so they cannot drift apart.
CELLS_JSON="$("$PY" -c "
import json,sys
sys.path.insert(0, '$HERE')
import screen_lib as L
print(json.dumps([{'name':c.name,'role':c.role,'gate':c.phase_gate,
                   'seed_start':c.seed_start,'n_decks':c.n_decks,
                   'n_games':c.n_games,'pool':c.pool_key} for c in L.CELLS]))
")" || DIE "screen_lib.py did not import — the instrument is broken, not the round"

# The library's own invariants, BEFORE anything is spent.
"$PY" -c "
import sys; sys.path.insert(0,'$HERE')
import screen_lib as L
p = L.sanity_check()
sys.exit(0 if not p else print('\n'.join(p)) or 1)
" || DIE "screen_lib.sanity_check() FAILED — the launcher and the adjudicator " \
         "share this file, so a defect here is a defect in BOTH."

# The adjudicator's own selftest. ⭐ A PRE-LAUNCH CHECKLIST ITEM precisely
# because a launcher-side gate that runs once per round is NEVER exercised by
# the smoke (the IS-D1 instrument-hardening note).
"$PY" "$HERE/analyze_phasegate.py" --selftest > "$HERE/SELFTEST_${ROLE}.json" 2>&1 \
  || DIE "analyze_phasegate.py --selftest FAILED — see SELFTEST_${ROLE}.json"
STAMP "selftest PASS -> SELFTEST_${ROLE}.json"

# ⭐ IDENT-BITEXACT — A HARD ABORT (DESIGN.md §8 item 5). A non-identity here
# voids the BUILD, not the round, and no cell may be played over it.
if [ -f "$HERE/IDENT_BITEXACT.json" ]; then
  grep -q '"verdict": *"PASS"' "$HERE/IDENT_BITEXACT.json" \
    || DIE "IDENT_BITEXACT.json is not PASS — gate=all is not proven to be the " \
           "ungated arbiter and gate=none is not proven to be the champion."
  STAMP "IDENT-BITEXACT PASS"
else
  DIE "IDENT_BITEXACT.json ABSENT — ABSENT is FAIL. Run " \
      "selftest_fixture/identity_fixture.py under BOTH wheels and diff them."
fi

# --- the two acts that gate a REAL cell (dry-run and smoke are exempt) ------
if [ "$DRY" -eq 0 ] && [ "$SMOKE" -eq 0 ]; then
  [ "$BLIND_COMMIT" != "PENDING" ] \
    || DIE "⛔⛔ BLIND_COMMIT is PENDING — REFUSING TO LAUNCH A REAL CELL. " \
           "A commit cannot name its own hash; a FOLLOW-UP commit must stamp the " \
           "freeze commit's 40-hex sha into WORKERS.conf and the sibling " \
           "BLIND_COMMIT file first. A read that was not blind is not a read."
  echo "$BLIND_COMMIT" | grep -Eq '^[0-9a-f]{40}$' \
    || DIE "BLIND_COMMIT is not a 40-hex sha: $BLIND_COMMIT"
  [ -f "$HERE/BAND_CLAIMED" ] \
    || DIE "⛔⛔ BAND_CLAIMED ABSENT — the band $BAND is PROPOSED, not claimed. " \
           "The orchestrator must re-run the tree sweep, append " \
           "BAND_CLAIM.json::_csv_row to governance/BAND_REGISTRY.csv, and " \
           "THEN drop BAND_CLAIMED. ⚠️ 146e9 is the trap this order exists for."
else
  STAMP "(dry-run/smoke: EXEMPT from BLIND_COMMIT and BAND_CLAIMED — they spend " \
        "no blindness and no band, and play the throwaway sub-range only)"
fi

# --- G-REV's launcher half: the rev pin, asserted BEFORE and AFTER ----------
PIN_FILE="$HERE/PINNED_SRC_REV"
assert_rev() {
  [ -f "$PIN_FILE" ] || DIE "PINNED_SRC_REV ABSENT — ABSENT is FAIL. Run " \
      "'git -C $REPO rev-parse HEAD > $PIN_FILE' ON THIS BOX, after the bundle sync."
  local pin head
  pin="$(tr -d ' \n' < "$PIN_FILE")"
  echo "$pin" | grep -Eq '^[0-9a-f]{40}$' || DIE "PINNED_SRC_REV is not 40-hex"
  head="$(git -C "$REPO" rev-parse HEAD)"
  [ "$pin" = "$head" ] || DIE "⛔ HEAD MOVED under the round ($head != $pin) — " \
      "refusing rather than banking a MIXED-REV archive."
  # code-path-scoped cleanliness (the whole-tree -dirty marker is informational)
  local dirty
  dirty="$(git -C "$REPO" status --porcelain -- src engine scripts rust tests | head -5)"
  if [ -n "$dirty" ]; then
    DIE "⛔ a CODE PATH is dirty at $1: $(echo "$dirty" | tr '\n' ' ')"
  fi
  echo "{\"at\":\"$1\",\"utc\":\"$(date -u +%FT%TZ)\",\"role\":\"$ROLE\",\"rev\":\"$pin\",\"clean\":true}" \
    >> "$HERE/SRC_CLEAN.jsonl"
}
assert_rev "before"

# --- census by FULL ARGS, never -C python ----------------------------------
# ⚠️ QUANTIFIED 2026-08-26: ONE niced 1-core DRAM-churner inflated a saturated
# W=22 eval ~1.8x/move. No timing statistic is a branch input here, so tenancy
# is RESULT-safe — but the census is still owed, and a silent long job is
# invisible to `ps -C python`.
STAMP "process census (FULL ARGS):"
ps -eo pid,etime,pcpu,args --sort=-etime | grep -E "python|carc" | grep -v grep \
  | head -20 | sed 's/^/    /'

export CARCASSONNE_FIX_R9="$CARCASSONNE_FIX_R9"   # ⚠️ env-latched at IMPORT
export PYTHONUNBUFFERED=1

# --------------------------------------------------------------------------- #
# 1. ONE CELL                                                                  #
# --------------------------------------------------------------------------- #
run_cell() {
  local name="$1" gate="$2" seed_start="$3" n_games="$4"
  local out="$SHARE/$OUT_TAG/$name"
  # ⭐ G-HOST is structural here: DISJOINT --out-subdir per cell means there are
  # no shared claims to race over, which is the real protection. The manifest's
  # `host` proves the SEALING PASS ran on the assigned box.
  mkdir -p "$out"
  local args=(
    "$REPO/scripts/classical_search/eval_fair_puct.py"
    --backend "$BACKEND" --info fair
    --k-dets "$K_DETS" --sims "$SIMS_PER_DET"
    --opp-k-dets "$K_DETS" --opp-sims "$SIMS_PER_DET"
    --exact-k "$EXACT_K"
    --opponent fair-champion
    # ⛔⛔ PG-D9: WITHOUT --paired THE ROUND HAS NO PRIMARY. eval_fair_puct's
    # _build_work (:2865) returns n DISTINCT decks at ONE seat each when paired is
    # false, so NO deck appears in both seatings, n_paired = 0 on every cell, and
    # the cell ALSO walks 2*n_decks seeds — outside its own frozen range and
    # straight through its sibling sub-cell's. With --paired, --n 2074 is exactly
    # 1037 decks x 2 seatings. Both precedent launchers pass it
    # (tiearb2_stage2:213, invasion_screen_r3:322).
    --n "$n_games" --paired --seed-start "$seed_start"
    # ⚠️ PG-D7: `--out` is AMBIGUOUS in eval_fair_puct (--out-root / --out-subdir)
    # and argparse REFUSES it. The out dir is root/sub (eval_fair_puct.py:4351-4353),
    # so this pair of flags names EXACTLY the "$SHARE/$OUT_TAG/$name" above.
    --workers "$W" --out-root "$SHARE/$OUT_TAG" --out-subdir "$name"
    # ⚠️ PG-D8: WITHOUT THIS THE ROUND RUNS `walled` — rules_profile's argparse
    # default is DEFAULT_PROFILE ("walled", the pre-F9 engine of record), NOT the
    # fixed_v1 the pair freezes (DESIGN §2.4). G-CONFIG asserts
    # manifest:rules_profile.name == screen_lib.RULES_PROFILE == "fixed_v1", so
    # every cell would have voided at adjudication.
    --rules-profile "$RULES_PROFILE"
    # ⛔⛔ THE SINGLE VARIABLE. Without --cand-tiearb-enabled the gate is a
    # SILENT NO-OP and the harness refuses at launch (champion-vs-champion
    # wearing a gated cell's name).
    --cand-tiearb-enabled
    --cand-tiearb-b "$ARB_B" --cand-tiearb-j "$ARB_J"
    --cand-tiearb-mode "$ARB_MODE" --cand-tiearb-salt "$ARB_SALT"
    --cand-tiearb-eps "$ARB_EPS"
    --cand-tiearb-phase-gate "$gate"
  )
  if [ "$BLIND_COMMIT" != "PENDING" ]; then
    args+=(--stamp-key "BLIND_COMMIT=$BLIND_COMMIT")
  fi
  if [ "$DRY" -eq 1 ]; then
    STAMP "[dry-run] $name gate=$gate seeds=${seed_start}.. n=$n_games -> $out"
    printf '    %q ' "$PY" "${args[@]}"; echo
    return 0
  fi
  STAMP "$name gate=$gate seeds=${seed_start}.. n=$n_games W=$W -> $out"
  nice -n 19 "$PY" "${args[@]}" || DIE "$name FAILED"
  assert_rev "after:$name"
}

# --------------------------------------------------------------------------- #
# 2. THE SMOKE (DESIGN.md §9)                                                  #
# --------------------------------------------------------------------------- #
# Per box, at that box's OWN frozen W, on the THROWAWAY band, PRODUCTION KNOBS,
# only the game count reduced. Local runs an ARB_EARLY-shaped leg, the laptop an
# ARB_FULL-shaped leg. ⛔ The smoke emits NO OUTCOME KEY.
# ⭐ Its one substantive job beyond liveness: it returns the REALIZED per-phase
# fired counts — the first real measurement of DESIGN §6.2's proxy — so a
# materially different early share revises the ETA BEFORE the round starts
# rather than being discovered inside it.
if [ "$SMOKE" -eq 1 ]; then
  case "$ROLE" in
    local)  SMOKE_GATE=early; SMOKE_NAME=SMOKE_EARLY ;;
    laptop) SMOKE_GATE=all;   SMOKE_NAME=SMOKE_FULL ;;
  esac
  run_cell "$SMOKE_NAME" "$SMOKE_GATE" "$((THROWAWAY_BASE + 500))" "$SMOKE_GAMES"
  if [ "$DRY" -eq 0 ]; then
    "$PY" "$HERE/analyze_phasegate.py" --root "$SHARE/$OUT_TAG" --smoke-mode \
      --out "$HERE/SMOKE_${ROLE}.json" || DIE "the smoke adjudication FAILED"
    STAMP "smoke adjudicated -> SMOKE_${ROLE}.json (structural keys only)"
  fi
  STAMP "SMOKE DONE role=$ROLE"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 3. THE ROUND — whole cells per box (G-HOST)                                  #
# --------------------------------------------------------------------------- #
echo "$CELLS_JSON" | "$PY" -c "
import json,sys
for c in json.load(sys.stdin):
    print(c['name'], c['role'], c['gate'], c['seed_start'], c['n_games'])
" | while read -r name role gate seed_start n_games; do
  [ "$role" = "$ROLE" ] || continue
  [ -z "$ONLY_CELL" ] || [ "$ONLY_CELL" = "$name" ] || continue
  if [ -f "$SHARE/$OUT_TAG/$name/DONE" ]; then
    STAMP "$name already DONE — skipping"
    continue
  fi
  run_cell "$name" "$gate" "$seed_start" "$n_games"
  [ "$DRY" -eq 1 ] || touch "$SHARE/$OUT_TAG/$name/DONE"
done

STAMP "DONE role=$ROLE"
