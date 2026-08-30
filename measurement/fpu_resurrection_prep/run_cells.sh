#!/usr/bin/env bash
# =========================================================================== #
# run_cells.sh — THE FPU-RESURRECTION ROUND'S LAUNCHER                        #
#                                                                             #
# ⛔⛔ THE ROUND IS UNLAUNCHED. This script REFUSES a real cell until the       #
#     orchestrator has done the pre-launch acts (DESIGN.md §8):               #
#       * screen_lib.sanity_check() is non-empty              -> REFUSE       #
#       * analyze_fpu.py --selftest FAILS                     -> REFUSE       #
#       * FPU_BITEXACT.json is absent or not PASS             -> REFUSE       #
#       * the frozen budget != PRODUCTION.yaml's champion     -> REFUSE       #
#       * BLIND_COMMIT is still the literal string PENDING    -> REFUSE       #
#       * the sibling BAND_CLAIMED file does not exist        -> REFUSE       #
#       * PINNED_SRC_REV is absent or does not name HEAD      -> REFUSE       #
#     --dry-run and --smoke are EXEMPT from BLIND_COMMIT and BAND_CLAIMED:    #
#     they spend no blindness and no band (they play the THROWAWAY range).    #
#                                                                             #
# ⛔ THE PAIR IS LAW. Every cell shape, band, knob, budget and box assignment  #
#    is read from screen_lib.py, which is imported by BOTH this launcher's    #
#    precondition ladder and the adjudicator — so a launcher/adjudicator      #
#    drift is impossible by construction rather than by review.               #
#                                                                             #
# ⚠️ W IS THROUGHPUT-ONLY. Games are bit-identical at any W and no gate in     #
#    this pair reads a clock.                                                 #
#                                                                             #
# USAGE                                                                       #
#   ./run_cells.sh --role local|laptop [--dry-run] [--smoke] [--cell NAME]    #
#                                                                             #
# ⚠️ LAUNCH DETACHED. Joshua's Mac->Windows->WSL setup means Mac-sleep SIGHUP  #
#    AND WSL VM-teardown both kill tty-attached jobs:                         #
#      setsid nohup ./run_cells.sh --role local >> log 2>&1 & disown          #
#    and on the laptop: ssh laptop 'bash -s' < run_cells.sh   (the inline     #
#    `ssh host 'cd .. && ..'` form gets the cd STRIPPED IN TRANSIT).          #
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

STAMP "role=$ROLE W=$W budget=k${K_DETS}x${SIMS_PER_DET}=${TOTAL_SIMS} tag=$OUT_TAG dry=$DRY smoke=$SMOKE"

# --------------------------------------------------------------------------- #
# 0. THE PRECONDITION LADDER                                                   #
# --------------------------------------------------------------------------- #
# ⭐ Resolved FROM screen_lib, never re-typed here — the launcher and the
# adjudicator read ONE cell table, so they cannot drift apart.
CELLS_JSON="$("$PY" -c "
import json,sys
sys.path.insert(0, '$HERE')
import screen_lib as L
print(json.dumps([{'name':c.name,'role':c.role,'knob':c.knob,'value':c.value,
                   'seed_start':c.seed_start,'n_games':c.n_games} for c in L.CELLS]))
")" || DIE "screen_lib.py did not import — the instrument is broken, not the round"

# The library's own invariants, BEFORE anything is spent.
"$PY" -c "
import sys; sys.path.insert(0,'$HERE')
import screen_lib as L
p = L.sanity_check()
sys.exit(0 if not p else print('\n'.join(p)) or 1)
" || DIE "screen_lib.sanity_check() FAILED — the launcher and the adjudicator " \
         "share this file, so a defect here is a defect in BOTH."

# WORKERS.conf must agree with the law it restates.
"$PY" -c "
import sys; sys.path.insert(0,'$HERE')
import screen_lib as L
want = ($K_DETS, $SIMS_PER_DET, $TOTAL_SIMS)
got  = (L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS)
if want != got:
    print(f'WORKERS.conf budget {want} != screen_lib {got}'); sys.exit(1)
bands = {'CELL_FPU02': $BAND_FPU02, 'CELL_FPU04': $BAND_FPU04,
         'CELL_CPUCT10': $BAND_CPUCT10}
if bands != L.BANDS:
    print(f'WORKERS.conf bands {bands} != screen_lib {L.BANDS}'); sys.exit(1)
if $THROWAWAY_BASE != L.THROWAWAY_BASE:
    print('WORKERS.conf THROWAWAY_BASE != screen_lib'); sys.exit(1)
" || DIE "WORKERS.conf disagrees with screen_lib.py — the pair is law and the " \
         "launcher restates it; a restatement that drifts is a launcher defect."

# ⭐⭐ G-PROD — THE BUDGET-PROMOTION GUARD. The desktop champion moved
# 11008 -> 22016 on 2026-08-30, in the same week this round was funded. A frozen
# budget that has silently drifted from PRODUCTION.yaml means the cells measure
# the knob against a STALE OPPONENT — which is a strictly worse defect than a
# wrong knob, because every other gate passes. Read the YAML, do not trust the
# restatement.
"$PY" -c "
import sys; sys.path.insert(0,'$HERE'); sys.path.insert(0,'$REPO/src')
import screen_lib as L
import yaml
spec = yaml.safe_load(open('$REPO/governance/PRODUCTION.yaml'))
fd = spec['champion']['fair_deploy']
k, s = int(fd['k_dets']), int(fd['sims_per_det'])
if (k, s, k*s) != (L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS):
    print(f'⛔ G-PROD: PRODUCTION.yaml fair_deploy is k{k}x{s}={k*s}, the round '
          f'is frozen at k{L.K_DETS}x{L.SIMS_PER_DET}={L.TOTAL_SIMS}. '
          'The opponent of every cell IS the champion of record, so a mismatch '
          'here means the round grades against a stale champion. Resolve it in '
          'the PAIR (an OWNER decision), never by editing the launcher.')
    print('⚠️ EXPECTED CAUSE (2026-08-30): the desktop champion was promoted '
          '11008 -> 22016 in the same week this round was built. A tree that '
          'predates that commit reads k8 here. THE FIX IS THE BUNDLE SYNC, not '
          'an edit: sync, re-pin PINNED_SRC_REV, re-run.')
    sys.exit(1)
print(f'[G-PROD] PRODUCTION.yaml fair_deploy k{k}x{s}={k*s} == the frozen budget')
"
G_PROD_RC=$?
if [ "$G_PROD_RC" -ne 0 ]; then
  # ⚠️ A --dry-run spends NOTHING — no compute, no band, no blindness — and its
  # whole purpose is to let a builder read the emitted argv on a tree that is
  # not yet synced. So the mismatch is LOUD but not fatal there, exactly as
  # BLIND_COMMIT and BAND_CLAIMED are exempt for a dry-run.
  # ⛔ It IS fatal for --smoke and for a real cell: a smoke at the wrong budget
  # re-prices nothing, and a real cell would grade against a stale champion.
  if [ "$DRY" -eq 1 ]; then
    STAMP "⚠️⚠️ G-PROD MISMATCH — continuing ONLY because this is a --dry-run. " \
          "⛔ A --smoke or a real cell from this tree is REFUSED."
  else
    DIE "G-PROD FAILED — the frozen budget is not the champion of record."
  fi
fi

# The adjudicator's own selftest. ⭐ A PRE-LAUNCH CHECKLIST ITEM precisely
# because a launcher-side gate that runs once per round is NEVER exercised by
# the smoke. It also re-asserts the GOLDEN GATE artefact.
"$PY" "$HERE/analyze_fpu.py" --selftest > "$HERE/SELFTEST_${ROLE}.json" 2>&1 \
  || DIE "analyze_fpu.py --selftest FAILED — see SELFTEST_${ROLE}.json"
STAMP "selftest PASS -> SELFTEST_${ROLE}.json"

# ⭐⭐ THE GOLDEN GATE — A HARD ABORT (DESIGN.md §9). Without it the knob is not
# proven to BIND and the default path is not proven UNMOVED, and a cell over a
# knob that never bound is champion-vs-champion wearing a candidate's name.
if [ -f "$HERE/FPU_BITEXACT.json" ]; then
  grep -q '"verdict": *"PASS"' "$HERE/FPU_BITEXACT.json" \
    || DIE "FPU_BITEXACT.json is not PASS — fpu=None is not proven to be the " \
           "champion bit-for-bit, or fpu=0.2 is not proven to differ from it."
  STAMP "GOLDEN GATE PASS (bit-exact at None + positive control at 0.2)"
else
  DIE "FPU_BITEXACT.json ABSENT — ABSENT is FAIL. Run " \
      "selftest_fixture/identity_fixture.py on the PRE- and POST-change trees " \
      "and adjudicate them with identity_diff.py."
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
    || DIE "⛔⛔ BAND_CLAIMED ABSENT — the THREE bands are PROPOSED, not claimed. " \
           "The orchestrator must re-run the tree sweep, append THREE rows from " \
           "BAND_CLAIM.json::_csv_rows to governance/BAND_REGISTRY.csv, and " \
           "THEN drop BAND_CLAIMED. ⚠️ 146e9 is the trap this order exists for."
else
  STAMP "(dry-run/smoke: EXEMPT from BLIND_COMMIT and BAND_CLAIMED — they spend " \
        "no blindness and no band, and play the throwaway sub-range only)"
fi

# --- G-REV's launcher half: the rev pin, asserted BEFORE and AFTER ----------
# ⚠️⚠️ THIS IS THIS ROUND'S PRIMARY PROVENANCE RISK, and it is a NEW shape. The
# fpu plumbing is PYTHON-ONLY — no rust change, no wheel move — so a box running
# the pre-fix source serves a knob-FREE candidate with a perfectly healthy
# `carc_rs_build`, a perfectly healthy binary sha and the correct leaf hash.
# The bundle sync + these pins are the only thing standing between that and a
# credible-looking null. G-TWOSIDED catches it at adjudication; this catches it
# before the compute is spent.
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
  local dirty
  dirty="$(git -C "$REPO" status --porcelain -- src engine scripts rust tests | head -5)"
  if [ -n "$dirty" ]; then
    DIE "⛔ a CODE PATH is dirty at $1: $(echo "$dirty" | tr '\n' ' ')"
  fi
  echo "{\"at\":\"$1\",\"utc\":\"$(date -u +%FT%TZ)\",\"role\":\"$ROLE\",\"rev\":\"$pin\",\"clean\":true}" \
    >> "$HERE/SRC_CLEAN.jsonl"
}
assert_rev "before"

# ⭐ AND THE KNOB ITSELF, ON THIS BOX, FROM THE SOURCE THAT WILL RUN. One import
# and one repr: if this box's `rust_agent.search_config_rs` still passes the
# hard-coded None, the whole round on this box is champion-vs-champion.
"$PY" -c "
import sys; sys.path.insert(0,'$REPO/scripts/human_anchor')
import env_preamble  # noqa: F401  (freeze the leaf shape before carcassonne_ai)
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
from carcassonne_ai.rust_agent import search_config_rs
cfg = HeuristicPriorConfig(fpu_reduction=0.2)
r = repr(search_config_rs(cfg, 8))
if 'fpu=Some(0.2)' not in r:
    print('⛔⛔ THIS BOX CANNOT EXPRESS fpu_reduction. repr: ' + r)
    print('The source here predates measurement/fpu_resurrection_prep — '
          'rust_agent.search_config_rs is still passing a hard-coded None into '
          'the SearchConfigRs slot. Every cell run from this box would be '
          'champion-vs-champion. Sync the bundle.')
    sys.exit(1)
print('[knob] this box binds fpu_reduction: ' + r)
" || DIE "the FPU knob does not bind on this box — REFUSING."

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
  local name="$1" knob="$2" value="$3" seed_start="$4" n_games="$5"
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
    # ⛔⛔ WITHOUT --paired THE ROUND HAS NO PRIMARY (the PG-D9 defect):
    # eval_fair_puct._build_work returns n DISTINCT decks at ONE seat each when
    # paired is false, so NO deck appears in both seatings, n_paired = 0 on
    # every cell, and the cell ALSO walks 2*n_decks seeds — outside its own
    # frozen band. With --paired, --n 800 is exactly 400 decks x 2 seatings.
    --n "$n_games" --paired --seed-start "$seed_start"
    # ⚠️ `--out` is AMBIGUOUS in eval_fair_puct (--out-root / --out-subdir) and
    # argparse REFUSES it (PG-D7). The out dir is root/sub, so this pair of
    # flags names EXACTLY the "$SHARE/$OUT_TAG/$name" above.
    --workers "$W" --out-root "$SHARE/$OUT_TAG" --out-subdir "$name"
    # ⚠️ WITHOUT THIS THE ROUND RUNS `walled` — rules_profile's argparse default
    # is DEFAULT_PROFILE ("walled", the pre-F9 engine of record), NOT the
    # fixed_v1 the pair freezes (PG-D8). G-RULES asserts fixed_v1, so every cell
    # would have voided at adjudication.
    --rules-profile "$RULES_PROFILE"
  )
  # ⛔⛔ THE SINGLE VARIABLE — and note there is NO --cand-tiearb-* flag anywhere
  # in this script, by construction (WORKERS.conf's arbiter block).
  case "$knob" in
    fpu_reduction) args+=(--cand-fpu-reduction "$value") ;;
    c_puct)        args+=(--cand-c-puct "$value") ;;
    # ⚠️ NOT `--c-puct`: that is the SHARED flag and it builds the OPPONENT too
    # (_make_opponent -> _cfg_from_dict on the same champ_cfg_dict), so a cell
    # built on it is champion-vs-champion. Only --cand-c-puct is candidate-only.
    *) DIE "unknown knob $knob for cell $name" ;;
  esac
  if [ "$BLIND_COMMIT" != "PENDING" ]; then
    args+=(--stamp-key "BLIND_COMMIT=$BLIND_COMMIT")
  fi
  if [ "$DRY" -eq 1 ]; then
    STAMP "[dry-run] $name $knob=$value seeds=${seed_start}.. n=$n_games -> $out"
    printf '    %q ' "$PY" "${args[@]}"; echo
    return 0
  fi
  STAMP "$name $knob=$value seeds=${seed_start}.. n=$n_games W=$W -> $out"
  nice -n 19 "$PY" "${args[@]}" || DIE "$name FAILED"
  assert_rev "after:$name"
}

# --------------------------------------------------------------------------- #
# 2. THE SMOKE (DESIGN.md §9)                                                  #
# --------------------------------------------------------------------------- #
# Per box, at that box's OWN frozen W, on the THROWAWAY sub-range, PRODUCTION
# KNOBS, only the game count reduced. ⛔ The smoke emits NO OUTCOME KEY.
# ⭐⭐ Its one substantive job beyond liveness: it drives the REAL argparse and
# the adjudicator reads the RESOLVED KNOB back out of the EMITTED manifest. That
# is the PG-D7..D9 lesson in one line — three separate launcher defects (an
# ambiguous --out, a defaulted rules profile, a missing --paired) all survived
# review and were only caught by a smoke adjudicated against emitted output.
# ⚠️ The local box smokes the FPU flag and the laptop smokes the C-PUCT flag,
# because they are DIFFERENT code paths in `_build_champ_cfg` and each box must
# exercise the one it will actually run.
if [ "$SMOKE" -eq 1 ]; then
  case "$ROLE" in
    local)  SMOKE_KNOB=fpu_reduction; SMOKE_VAL=0.2; SMOKE_NAME=SMOKE_FPU ;;
    laptop) SMOKE_KNOB=c_puct;        SMOKE_VAL=1.0; SMOKE_NAME=SMOKE_CPUCT ;;
  esac
  run_cell "$SMOKE_NAME" "$SMOKE_KNOB" "$SMOKE_VAL" \
           "$((THROWAWAY_BASE + 500))" "$SMOKE_GAMES"
  if [ "$DRY" -eq 0 ]; then
    # ⭐ Adjudicated against the EMITTED archive, from the smoke's own directory,
    # so `resolved_knobs` in the output is read off manifest.json rather than
    # restated from the command line.
    "$PY" "$HERE/analyze_fpu.py" --root "$SHARE/$OUT_TAG" --smoke-mode \
      --out "$HERE/SMOKE_${ROLE}.json" || DIE "the smoke adjudication FAILED"
    "$PY" -c "
import json,sys
d = json.load(open('$HERE/SMOKE_${ROLE}.json'))
k = (d.get('resolved_knobs') or {})
print('[smoke] resolved knobs FROM THE EMITTED MANIFEST:', json.dumps(k))
" || true
    STAMP "smoke adjudicated -> SMOKE_${ROLE}.json (structural keys only)"
    STAMP "⚠️ REVIEW SMOKE_${ROLE}.json BY HAND before the round: the resolved " \
          "knob must be the one this box will run, read off manifest.json."
  fi
  STAMP "SMOKE DONE role=$ROLE"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 3. THE ROUND — whole cells per box (G-HOST)                                  #
# --------------------------------------------------------------------------- #
# ⭐ Whole cells per box, per the funding brief. The realized local:laptop rate
# ratio is ~1.46:1, so 2 local + 1 laptop is the best balance a 3-cell / 2-box
# whole-cell split admits; the residual imbalance is DISCLOSED in SIZING (§6),
# not engineered away by sub-celling.
echo "$CELLS_JSON" | "$PY" -c "
import json,sys
for c in json.load(sys.stdin):
    print(c['name'], c['role'], c['knob'], c['value'], c['seed_start'], c['n_games'])
" | while read -r name role knob value seed_start n_games; do
  [ "$role" = "$ROLE" ] || continue
  [ -z "$ONLY_CELL" ] || [ "$ONLY_CELL" = "$name" ] || continue
  if [ -f "$SHARE/$OUT_TAG/$name/DONE" ]; then
    STAMP "$name already DONE — skipping"
    continue
  fi
  run_cell "$name" "$knob" "$value" "$seed_start" "$n_games"
  [ "$DRY" -eq 1 ] || touch "$SHARE/$OUT_TAG/$name/DONE"
done

STAMP "DONE role=$ROLE"
