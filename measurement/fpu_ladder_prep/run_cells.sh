#!/usr/bin/env bash
# =========================================================================== #
# run_cells.sh — THE FPU DOSE-LADDER ROUND'S LAUNCHER                         #
#                                                                             #
# ⛔⛔ THE ROUND IS UNLAUNCHED. This script REFUSES a real rung until the       #
#     orchestrator has done the pre-launch acts (DESIGN.md §8):               #
#       * screen_lib.sanity_check() is non-empty              -> REFUSE       #
#       * analyze_ladder.py --selftest FAILS                  -> REFUSE       #
#       * FPU_BITEXACT_LADDER.json absent or not PASS         -> REFUSE       #
#       * the golden gate's wheel != THIS BOX's wheel         -> REFUSE       #
#       * the frozen budget != PRODUCTION.yaml's champion     -> REFUSE       #
#       * BLIND_COMMIT is still the literal string PENDING    -> REFUSE       #
#       * the sibling BAND_CLAIMED file does not exist        -> REFUSE       #
#       * PINNED_SRC_REV is absent or does not name HEAD      -> REFUSE       #
#       * a CODE PATH is dirty, before OR after any rung      -> REFUSE       #
#     --dry-run and --smoke are EXEMPT from BLIND_COMMIT and BAND_CLAIMED:    #
#     they spend no blindness and no band (they play the THROWAWAY range).    #
#     ⚠️ --dry-run ALONE is additionally exempt from G-PROD and the GOLDEN     #
#     GATE (loud, not fatal) — it spends NO compute at all and its whole      #
#     purpose is to show the EMITTED ARGV before anything has been run,       #
#     which at build time is necessarily before the gate exists. ⛔ --smoke   #
#     is NOT exempt from either: it is real play on the real wheel.           #
#                                                                             #
# ⛔ THE PAIR IS LAW. Every rung shape, band, dose, budget and box assignment  #
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
#      setsid nohup nice -n 19 ./run_cells.sh --role local >> log 2>&1 & disown
#    and on the laptop: ssh laptop 'bash -s' < run_cells.sh -- --role laptop  #
#    (the inline `ssh host 'cd .. && ..'` form gets the cd STRIPPED           #
#    IN TRANSIT — feedback_remote_ssh_pipe_script_mandatory).                 #
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
    --) shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$ROLE" ] || { echo "--role local|laptop is required" >&2; exit 2; }

# ⚠️ The venv is editable-installed against the MAIN tree, so a copy of this
# script running from a git WORKTREE has no `.venv` beside it. Fall back to the
# canonical one rather than dying — the worktree case is a BUILD/dry-run case,
# and a real rung always runs from the main tree (which the rev pin re-asserts).
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python found" >&2; exit 2; }
case "$ROLE" in
  local)  W="$W_LOCAL";  SHARE="$SHARE_LOCAL";  SMOKE_DOSE="$SMOKE_DOSE_LOCAL" ;;
  laptop) W="$W_LAPTOP"; SHARE="$SHARE_LAPTOP"; SMOKE_DOSE="$SMOKE_DOSE_LAPTOP" ;;
  *) echo "--role must be local|laptop" >&2; exit 2 ;;
esac
STAMP() { echo "[run_cells $(date -u +%FT%TZ) $(hostname)/$ROLE] $*"; }
DIE() { STAMP "!!! $*"; exit 13; }

STAMP "role=$ROLE W=$W budget=k${K_DETS}x${SIMS_PER_DET}=${TOTAL_SIMS} tag=$OUT_TAG dry=$DRY smoke=$SMOKE"

# --------------------------------------------------------------------------- #
# 0. THE PRECONDITION LADDER                                                   #
# --------------------------------------------------------------------------- #
# ⭐ Resolved FROM screen_lib, never re-typed here — the launcher and the
# adjudicator read ONE rung table, so they cannot drift apart.
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
bands = {'CELL_FPU005': $BAND_FPU005, 'CELL_FPU010': $BAND_FPU010,
         'CELL_FPU015': $BAND_FPU015, 'CELL_FPU030': $BAND_FPU030}
if bands != L.BANDS:
    print(f'WORKERS.conf bands {bands} != screen_lib {L.BANDS}'); sys.exit(1)
if $THROWAWAY_BASE != L.THROWAWAY_BASE:
    print('WORKERS.conf THROWAWAY_BASE != screen_lib'); sys.exit(1)
doses = sorted(c.value for c in L.CELLS)
if doses != sorted([0.05, 0.1, 0.15, 0.3]):
    print(f'screen_lib doses {doses} are not the funded ladder'); sys.exit(1)
# ⭐ the smoke doses this box will drive must be REAL rungs of the round: a
# smoke at a dose nobody runs exercises a code path nobody runs.
smoke = float('$SMOKE_DOSE')
if smoke not in doses:
    print(f'the {\"$ROLE\"} smoke dose {smoke} is not a rung of this round')
    sys.exit(1)
" || DIE "WORKERS.conf disagrees with screen_lib.py — the pair is law and the " \
         "launcher restates it; a restatement that drifts is a launcher defect."

# ⭐⭐ G-PROD — THE BUDGET GUARD. The opponent of every rung IS the champion of
# record; a frozen budget that has silently drifted from PRODUCTION.yaml means
# the rungs measure the dose against a STALE OPPONENT — a strictly worse defect
# than a wrong dose, because every other gate passes. Read the YAML, do not
# trust the restatement.
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
          'The opponent of every rung IS the champion of record, so a mismatch '
          'here means the round grades against a stale champion. Resolve it in '
          'the PAIR (an OWNER decision), never by editing the launcher.')
    print('⭐ THE FIX IS THE BUNDLE SYNC, not an edit: sync, re-pin '
          'PINNED_SRC_REV, re-run.')
    sys.exit(1)
print(f'[G-PROD] PRODUCTION.yaml fair_deploy k{k}x{s}={k*s} == the frozen budget')
"
G_PROD_RC=$?
if [ "$G_PROD_RC" -ne 0 ]; then
  # ⚠️ A --dry-run spends NOTHING — no compute, no band, no blindness — and its
  # whole purpose is to let a builder read the emitted argv on a tree that is
  # not yet synced. So the mismatch is LOUD but not fatal there, exactly as
  # BLIND_COMMIT and BAND_CLAIMED are exempt for a dry-run.
  # ⛔ It IS fatal for --smoke and for a real rung.
  if [ "$DRY" -eq 1 ]; then
    STAMP "⚠️⚠️ G-PROD MISMATCH — continuing ONLY because this is a --dry-run. " \
          "⛔ A --smoke or a real rung from this tree is REFUSED."
  else
    DIE "G-PROD FAILED — the frozen budget is not the champion of record."
  fi
fi

# The adjudicator's own selftest. ⭐ A PRE-LAUNCH CHECKLIST ITEM precisely
# because a launcher-side gate that runs once per round is NEVER exercised by
# the smoke.
"$PY" "$HERE/analyze_ladder.py" --selftest > "$HERE/SELFTEST_${ROLE}.json" 2>&1 \
  || DIE "analyze_ladder.py --selftest FAILED — see SELFTEST_${ROLE}.json"
STAMP "selftest PASS -> SELFTEST_${ROLE}.json"

# --------------------------------------------------------------------------- #
# ⭐⭐ THE GOLDEN GATE — A HARD ABORT, AND IT IS NOT INHERITED (DESIGN §9)      #
# --------------------------------------------------------------------------- #
# ⛔⛔ THE PARENT ROUND'S FPU_BITEXACT.json IS NOT ACCEPTED HERE. It was
# adjudicated under a ONE-WHEEL check on carc_rs binary f6316d42838574de, and
# the S1 R7/R6 merge (2026-08-30, commit 316df67d) has since changed
# `carc_core::search` and `fair::search_worlds` — the modules that implement the
# FPU rule and the PIMC descent this round plays on. The counters are ARGUED to
# be play-neutral; "argued play-neutral" is exactly the class of claim the
# hard-coded `None` also satisfied, and this family exists because that argument
# was wrong once already.
#
# So: FPU_BITEXACT_LADDER.json must exist, read PASS, and its `wheel.binary_sha`
# must be THIS BOX's installed binary.
#
# ⚠️ A --dry-run is EXEMPT (loud, not fatal), exactly as it is for G-PROD and for
# BLIND_COMMIT/BAND_CLAIMED. It spends NO compute, NO band and NO blindness, and
# its whole purpose is to let the executor read the EMITTED ARGV before anything
# is run — which at build time is necessarily BEFORE the gate has been run at
# all. ⛔ A --smoke is NOT exempt: it is real play, on the real wheel, on the
# real code path, and it is the last thing that happens before the round.
GG_FATAL=1
[ "$DRY" -eq 0 ] || GG_FATAL=0
GG_DIE() { if [ "$GG_FATAL" -eq 1 ]; then DIE "$@"; else
    STAMP "⚠️⚠️ GOLDEN GATE NOT SATISFIED — continuing ONLY because this is a " \
          "--dry-run (it spends nothing). ⛔ A --smoke or a real rung is " \
          "REFUSED. Reason: $*"; fi; }
if [ -f "$HERE/FPU_BITEXACT_LADDER.json" ]; then
  grep -q '"verdict": *"PASS"' "$HERE/FPU_BITEXACT_LADDER.json" \
    || GG_DIE "FPU_BITEXACT_LADDER.json is not PASS — fpu=None is not proven to be " \
           "the champion bit-for-bit ON THIS WHEEL, or a rung's dose is not " \
           "proven to differ from it."
  "$PY" -c "
import json,sys
sys.path.insert(0,'$REPO/scripts/human_anchor')
import env_preamble  # noqa: F401
from carcassonne_ai.rust_agent import carc_rs_binary_sha
v = json.load(open('$HERE/FPU_BITEXACT_LADDER.json'))
gate_sha = ((v.get('wheel') or {}).get('binary_sha'))
here_sha = carc_rs_binary_sha()
if not gate_sha:
    print('⛔ FPU_BITEXACT_LADDER.json carries no wheel.binary_sha'); sys.exit(1)
if gate_sha != here_sha:
    print(f'⛔⛔ THE GOLDEN GATE WAS RUN ON A DIFFERENT WHEEL: gate {gate_sha} '
          f'vs this box {here_sha}. ⚠️ carc_rs_binary_sha is BOX-LOCAL — two '
          'boxes compiling identical source produce different bytes — so EACH '
          'BOX runs its OWN golden gate before its own rungs. Run '
          'golden_gate/run_golden_gate.sh on THIS box.')
    sys.exit(1)
print(f'[GOLDEN GATE] PASS on the wheel THIS BOX will play: {here_sha}')
" || GG_DIE "the golden gate does not match this box's wheel — REFUSING."
else
  GG_DIE "FPU_BITEXACT_LADDER.json ABSENT — ABSENT is FAIL. Run " \
      "golden_gate/run_golden_gate.sh ON THIS BOX, AT THE LAUNCH REV. ⛔ The " \
      "parent round's measurement/fpu_resurrection_prep/FPU_BITEXACT.json is " \
      "NOT a substitute: its wheel is gone (DESIGN §9)."
fi

# --- the two acts that gate a REAL rung (dry-run and smoke are exempt) ------
if [ "$DRY" -eq 0 ] && [ "$SMOKE" -eq 0 ]; then
  [ "$BLIND_COMMIT" != "PENDING" ] \
    || DIE "⛔⛔ BLIND_COMMIT is PENDING — REFUSING TO LAUNCH A REAL RUNG. " \
           "A commit cannot name its own hash; a FOLLOW-UP commit must stamp the " \
           "freeze commit's 40-hex sha into WORKERS.conf first. A read that was " \
           "not blind is not a read."
  echo "$BLIND_COMMIT" | grep -Eq '^[0-9a-f]{40}$' \
    || DIE "BLIND_COMMIT is not a 40-hex sha: $BLIND_COMMIT"
  [ -f "$HERE/BAND_CLAIMED" ] \
    || DIE "⛔⛔ BAND_CLAIMED ABSENT — the FOUR bands are PROPOSED, not claimed. " \
           "The orchestrator must re-run the tree sweep, append FOUR rows from " \
           "BAND_CLAIM.json::_csv_rows to governance/BAND_REGISTRY.csv, and " \
           "THEN drop BAND_CLAIMED. ⚠️ 146e9 is the trap this order exists for."
else
  STAMP "(dry-run/smoke: EXEMPT from BLIND_COMMIT and BAND_CLAIMED — they spend " \
        "no blindness and no band, and play the throwaway sub-range only)"
fi

# --- G-REV's launcher half: the rev pin, asserted BEFORE and AFTER ----------
# ⚠️⚠️ THIS IS THIS FAMILY'S PRIMARY PROVENANCE RISK. The fpu plumbing is
# PYTHON-ONLY — so a box running pre-fix source serves a dose-FREE candidate
# with a perfectly healthy `carc_rs_build`, a perfectly healthy binary sha and
# the correct leaf hash. The bundle sync + these pins are the only thing
# standing between that and a credible-looking null. G-TWOSIDED catches it at
# adjudication; this catches it before the compute is spent.
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
# ⭐⭐ PROBED AT THE SMALLEST DOSE THE ROUND RUNS (0.05), not at a convenient
# one: a plumbing bug that rounded or clamped small values would pass a 0.2
# probe and silently flatten the bottom of the ladder.
"$PY" -c "
import sys; sys.path.insert(0,'$REPO/scripts/human_anchor')
import env_preamble  # noqa: F401  (freeze the leaf shape before carcassonne_ai)
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
from carcassonne_ai.rust_agent import search_config_rs
bad = []
for dose in (0.05, 0.1, 0.15, 0.3):
    r = repr(search_config_rs(HeuristicPriorConfig(fpu_reduction=dose), 8))
    if f'fpu=Some({dose})' not in r:
        bad.append(f'{dose} -> {r}')
if bad:
    print('⛔⛔ THIS BOX CANNOT EXPRESS fpu_reduction AT: ' + '; '.join(bad))
    print('The source here predates the fpu plumbing, or a value is being '
          'clamped/rounded on the way to the SearchConfigRs slot. Every rung '
          'run from this box would be champion-vs-champion, or would be a '
          'DIFFERENT dose than the one the band claims. Sync the bundle.')
    sys.exit(1)
print('[knob] this box binds every rung dose: 0.05 / 0.1 / 0.15 / 0.3')
" || DIE "the FPU knob does not bind at every rung dose on this box — REFUSING."

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
# 1. ONE RUNG                                                                  #
# --------------------------------------------------------------------------- #
run_cell() {
  local name="$1" knob="$2" value="$3" seed_start="$4" n_games="$5"
  local out="$SHARE/$OUT_TAG/$name"
  # ⭐ G-HOST is structural here: DISJOINT --out-subdir per rung means there are
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
    # every rung, and the rung ALSO walks 2*n_decks seeds — outside its own
    # frozen band. With --paired, --n 800 is exactly 400 decks x 2 seatings.
    --n "$n_games" --paired --seed-start "$seed_start"
    # ⚠️ `--out` is AMBIGUOUS in eval_fair_puct (--out-root / --out-subdir) and
    # argparse REFUSES it (PG-D7). The out dir is root/sub, so this pair of
    # flags names EXACTLY the "$SHARE/$OUT_TAG/$name" above.
    --workers "$W" --out-root "$SHARE/$OUT_TAG" --out-subdir "$name"
    # ⚠️ WITHOUT THIS THE ROUND RUNS `walled` — rules_profile's argparse default
    # is DEFAULT_PROFILE ("walled", the pre-F9 engine of record), NOT the
    # fixed_v1 the pair freezes (PG-D8). G-RULES asserts fixed_v1, so every rung
    # would have voided at adjudication.
    --rules-profile "$RULES_PROFILE"
  )
  # ⛔⛔ THE SINGLE VARIABLE — and note there is NO --cand-tiearb-* flag and no
  # --cand-c-puct flag anywhere in this script, by construction. `--c-puct` and
  # `--tau-p` are the SHARED flags: they build champ_cfg_dict, which
  # _make_opponent feeds through the SAME _cfg_from_dict, so they move BOTH
  # SIDES and a rung built on one is champion-vs-champion.
  case "$knob" in
    fpu_reduction) args+=(--cand-fpu-reduction "$value") ;;
    *) DIE "unknown knob $knob for rung $name — every rung of this round owns " \
           "fpu_reduction" ;;
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
# 2. THE SMOKE (DESIGN.md §9.3)                                                #
# --------------------------------------------------------------------------- #
# Per box, at that box's OWN frozen W, on the THROWAWAY sub-range, PRODUCTION
# KNOBS, only the game count reduced. ⛔ The smoke emits NO OUTCOME KEY.
# ⭐⭐ Its one substantive job beyond liveness: it drives the REAL argparse and
# the adjudicator reads the RESOLVED DOSE back out of the EMITTED manifest. That
# is the PG-D7..D9 lesson in one line — three separate launcher defects (an
# ambiguous --out, a defaulted rules profile, a missing --paired) all survived
# review and were only caught by a smoke adjudicated against emitted output.
# ⚠️ The local box smokes 0.05 and the laptop smokes 0.30 — the ladder's two
# EXTREMES, each on a box that will run that dose. 0.05 is the load-bearing one.
if [ "$SMOKE" -eq 1 ]; then
  SMOKE_NAME="SMOKE_$(echo "$SMOKE_DOSE" | tr -d '.')"
  SMOKE_SEED=$((THROWAWAY_BASE + 500))
  run_cell "$SMOKE_NAME" fpu_reduction "$SMOKE_DOSE" \
           "$SMOKE_SEED" "$SMOKE_GAMES"
  if [ "$DRY" -eq 0 ]; then
    # ⭐ Adjudicated against the EMITTED archive, from the smoke's own directory,
    # so `resolved_knobs` in the output is read off manifest.json rather than
    # restated from the command line.
    # ⭐⭐ R1 (carried from the fpu_resurrection pre-launch merge review) —
    # `--smoke-cell` IS REQUIRED. `--root` is the PARENT, and the round's rung
    # table names only the four ROUND rungs, so before this flag existed a smoke
    # read adjudicated ZERO cells, reported `"cells": {}` / `"resolved_knobs":
    # {}` and STILL EXITED 0 — the `|| DIE` below was unreachable and the smoke
    # proved nothing. The spec is passed from HERE (the launcher is the only
    # thing that knows what it asked for) and analyze_ladder then checks it
    # against the EMITTED manifest.json, including that the dose landed on the
    # CANDIDATE SIDE ONLY (G-TWOSIDED).
    "$PY" "$HERE/analyze_ladder.py" --root "$SHARE/$OUT_TAG" --smoke-mode \
      --smoke-cell "${SMOKE_NAME}=fpu_reduction:${SMOKE_DOSE}:${SMOKE_SEED}:${SMOKE_GAMES}:${ROLE}" \
      --out "$HERE/SMOKE_${ROLE}.json" || DIE "the smoke adjudication FAILED"
    "$PY" -c "
import json,sys
d = json.load(open('$HERE/SMOKE_${ROLE}.json'))
k = (d.get('resolved_knobs') or {})
print('[smoke] resolved knobs FROM THE EMITTED MANIFEST:', json.dumps(k))
" || true
    STAMP "smoke adjudicated -> SMOKE_${ROLE}.json (structural keys only)"
    STAMP "⚠️ REVIEW SMOKE_${ROLE}.json BY HAND before the round: the resolved " \
          "dose must be the one this box was told to smoke, read off " \
          "manifest.json, and it must be on the CANDIDATE SIDE ONLY."
  fi
  STAMP "SMOKE DONE role=$ROLE"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 3. THE ROUND — whole rungs per box (G-HOST)                                  #
# --------------------------------------------------------------------------- #
# ⭐ 2 local + 2 laptop, per DESIGN §6's realized-rate arithmetic. The residual
# imbalance is DISCLOSED there, not engineered away by sub-celling (which would
# need a G-SUBPOOL gate and a pooled primary).
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
