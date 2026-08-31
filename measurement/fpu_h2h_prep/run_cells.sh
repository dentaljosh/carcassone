#!/usr/bin/env bash
# =========================================================================== #
# run_cells.sh — THE FPU PRODUCTION-H2H ROUND'S LAUNCHER                       #
#                                                                             #
# ⛔⛔ THE ROUND IS UNLAUNCHED. This script REFUSES a real cell until the       #
#     orchestrator has done the pre-launch acts (DESIGN.md §8):               #
#       * --role is laptop (the owner holds the local box)     -> REFUSE       #
#       * W_LAPTOP is still TBD_FROM_SWEEP                     -> REFUSE       #
#       * screen_lib.sanity_check() is non-empty               -> REFUSE       #
#       * analyze_h2h.py --selftest FAILS                      -> REFUSE       #
#       * the INHERITED golden gate is absent / not PASS       -> REFUSE       #
#       * the golden gate's wheel != THIS BOX's wheel          -> REFUSE       #
#       * the frozen budget != PRODUCTION.yaml's champion      -> REFUSE       #
#       * the frozen ARBITER != PRODUCTION.yaml's tiearb       -> REFUSE       #
#       * this box cannot express fpu_reduction=0.2            -> REFUSE       #
#       * this box has no --opp-tiearb-* plumbing              -> REFUSE       #
#       * BLIND_COMMIT is still the literal string PENDING     -> REFUSE       #
#       * the sibling BAND_CLAIMED file does not exist         -> REFUSE       #
#       * PINNED_SRC_REV is absent or does not name HEAD       -> REFUSE       #
#       * a CODE PATH is dirty, before OR after the cell       -> REFUSE       #
#     --dry-run and --smoke are EXEMPT from BLIND_COMMIT and BAND_CLAIMED:    #
#     they spend no blindness and no band (they play the THROWAWAY range).    #
#     ⚠️ --dry-run ALONE is additionally exempt from G-PROD and the GOLDEN     #
#     GATE (loud, not fatal) — it spends NO compute at all and its whole      #
#     purpose is to show the EMITTED ARGV before anything has been run.       #
#     ⛔ --smoke is NOT exempt from either: it is real play on the real wheel. #
#     ⛔ NOTHING is exempt from the W_LAPTOP check — a smoke at a W the round  #
#     will not run is a smoke of a different tenancy.                         #
#                                                                             #
# ⛔ THE PAIR IS LAW. The cell shape, band, dose, budget, arbiter spec and box #
#    assignment are read from screen_lib.py, which is imported by BOTH this    #
#    launcher's precondition ladder and the adjudicator — so a launcher/       #
#    adjudicator drift is impossible by construction rather than by review.    #
#                                                                             #
# ⚠️ W IS THROUGHPUT-ONLY. Games are bit-identical at any W and no gate in     #
#    this pair reads a clock.                                                 #
#                                                                             #
# USAGE                                                                       #
#   ./run_cells.sh --role laptop [--dry-run] [--smoke]                        #
#                                                                             #
# ⚠️ LAUNCH DETACHED. Joshua's Mac->Windows->WSL setup means Mac-sleep SIGHUP  #
#    AND WSL VM-teardown both kill tty-attached jobs. From the laptop:        #
#      setsid nohup nice -n 19 ./run_cells.sh --role laptop >> log 2>&1 & disown
#    and from here: ssh laptop 'bash -s' < run_cells.sh -- --role laptop      #
#    (the inline `ssh host 'cd .. && ..'` form gets the cd STRIPPED           #
#    IN TRANSIT — feedback_remote_ssh_pipe_script_mandatory).                 #
# =========================================================================== #
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
. "$HERE/WORKERS.conf"

ROLE=""; DRY=0; SMOKE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --role) ROLE="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --) shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$ROLE" ] || { echo "--role laptop is required" >&2; exit 2; }

# ⚠️ The venv is editable-installed against the MAIN tree, so a copy of this
# script running from a git WORKTREE has no `.venv` beside it. Fall back to the
# canonical one rather than dying — the worktree case is a BUILD/dry-run case,
# and a real cell always runs from the main tree (which the rev pin re-asserts).
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python found" >&2; exit 2; }

STAMP() { echo "[run_cells $(date -u +%FT%TZ) $(hostname)/$ROLE] $*"; }
DIE() { STAMP "!!! $*"; exit 13; }

# --------------------------------------------------------------------------- #
# ⛔⛔ 0a. THE BOX. THE ROUND IS LAPTOP ONLY.                                   #
# --------------------------------------------------------------------------- #
# The local box is the OWNER'S DESKTOP and he is holding it. This is not a
# throughput opinion — it is a standing constraint on this round, and
# screen_lib.CELLS[0].role restates it so the adjudicator's G-HOST voids a cell
# that ran anywhere else.
case "$ROLE" in
  laptop) W="$W_LAPTOP"; SHARE="$SHARE_LAPTOP" ;;
  local)  DIE "⛔⛔ --role local is REFUSED. This round is LAPTOP ONLY: the "\
              "owner holds the local box. G-HOST would void a cell run here "\
              "anyway (screen_lib freezes role='laptop'), so the refusal is "\
              "at launch rather than at adjudication, after ~7 h of compute." ;;
  *) DIE "--role must be laptop" ;;
esac

# --------------------------------------------------------------------------- #
# ⛔⛔ 0b. W_LAPTOP MUST BE THE SWEPT VALUE — NOT EXEMPT FOR ANYTHING           #
# --------------------------------------------------------------------------- #
# ⚠️ W is THROUGHPUT-ONLY and moves no bar, gate or branch — so this refusal is
# NOT about correctness of the statistic. It is about the SMOKE meaning
# something: a smoke run at a W the round will not run is a smoke of a different
# tenancy (feedback_no_agent_compute_beside_eval quantified a 1.8x/move
# inflation from ONE stray niced core), and about the ETA the orchestrator
# reports being derived from the W actually used.
case "$W" in
  ''|*[!0-9]*)
    DIE "⛔⛔ W_LAPTOP is '$W' — the SWEPT VALUE HAS NOT BEEN STAMPED. A laptop "\
        "W sweep was live when this instrument was built; the orchestrator "\
        "writes its result into WORKERS.conf (W_LAPTOP=<int>) at launch. "\
        "⭐ NOTHING ELSE in the pair moves with it: DESIGN §6 gives the ETA as "\
        "a FORMULA in W precisely so this number can be filled in last." ;;
esac
[ "$W" -ge 1 ] || DIE "W_LAPTOP=$W must be >= 1"

STAMP "role=$ROLE W=$W budget=k${K_DETS}x${SIMS_PER_DET}=${TOTAL_SIMS} " \
      "arb=B${TIEARB_B}/J${TIEARB_J}/${TIEARB_MODE}/${TIEARB_PHASE_GATE} " \
      "fpu=$FPU_DOSE tag=$OUT_TAG dry=$DRY smoke=$SMOKE"

# --------------------------------------------------------------------------- #
# 1. THE PRECONDITION LADDER                                                   #
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
if $BAND_H2H != L.BAND:
    print(f'WORKERS.conf BAND_H2H $BAND_H2H != screen_lib {L.BAND}'); sys.exit(1)
if $THROWAWAY_BASE != L.THROWAWAY_BASE:
    print('WORKERS.conf THROWAWAY_BASE != screen_lib'); sys.exit(1)
if len(L.CELLS) != 1 or L.CELLS[0].role != '$ROLE':
    print(f'the round is not ONE {\"$ROLE\"} cell: {[(c.name,c.role) for c in L.CELLS]}')
    sys.exit(1)
if float(L.CELLS[0].value) != float('$FPU_DOSE'):
    print(f'WORKERS.conf FPU_DOSE $FPU_DOSE != the frozen {L.CELLS[0].value}')
    sys.exit(1)
want_arb = {'enabled': True, 'B': $TIEARB_B, 'J': $TIEARB_J,
            'mode': '$TIEARB_MODE', 'salt': '$TIEARB_SALT',
            'eps': float('$TIEARB_EPS'), 'phase_gate': '$TIEARB_PHASE_GATE'}
if want_arb != L.DEPLOYED_TIEARB:
    print(f'WORKERS.conf arbiter {want_arb} != screen_lib {L.DEPLOYED_TIEARB}')
    sys.exit(1)
if '$RULES_PROFILE' != L.RULES_PROFILE or '$BACKEND' != L.BACKEND:
    print('WORKERS.conf rules/backend != screen_lib'); sys.exit(1)
if $EXACT_K != L.EXACT_K:
    print('WORKERS.conf EXACT_K != screen_lib'); sys.exit(1)
" || DIE "WORKERS.conf disagrees with screen_lib.py — the pair is law and the " \
         "launcher restates it; a restatement that drifts is a launcher defect."

# --------------------------------------------------------------------------- #
# ⭐⭐ G-PROD — THE DEPLOY GUARD: BUDGET **AND** ARBITER                        #
# --------------------------------------------------------------------------- #
# The opponent of this cell IS the DEPLOYED champion — budget AND arbiter. A
# frozen constant that has silently drifted from PRODUCTION.yaml means the cell
# grades the dose against a stale champion, and every other gate passes it.
# ⚠️ THE LADDER'S G-PROD CHECKED THE BUDGET ONLY, because its arbiter was OFF.
# Here the arbiter is half the definition of the opponent, so it is checked too.
# ⚠️ PRODUCTION.yaml carries no `phase_gate` key: the deployed arbiter is
# UNGATED and "all" is how the harness spells that. The absence is asserted
# explicitly rather than defaulted.
"$PY" -c "
import sys; sys.path.insert(0,'$HERE'); sys.path.insert(0,'$REPO/src')
import screen_lib as L
import yaml
spec = yaml.safe_load(open('$REPO/governance/PRODUCTION.yaml'))
fd = spec['champion']['fair_deploy']
k, s = int(fd['k_dets']), int(fd['sims_per_det'])
bad = []
if (k, s, k*s) != (L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS):
    bad.append(f'PRODUCTION.yaml fair_deploy is k{k}x{s}={k*s}, the round is '
               f'frozen at k{L.K_DETS}x{L.SIMS_PER_DET}={L.TOTAL_SIMS}')
ta = fd.get('tiearb') or {}
if not ta:
    bad.append('PRODUCTION.yaml carries NO champion.fair_deploy.tiearb block — '
               'the DEPLOYED champion this cell claims to play has no arbiter, '
               'so arming one on both seats would be a DEVIATION, not a deploy')
else:
    for key, yaml_key in (('enabled','enabled'), ('B','B'), ('J','J'),
                          ('mode','mode'), ('salt','salt'), ('eps','eps')):
        want = L.DEPLOYED_TIEARB[key]
        got = ta.get(yaml_key)
        if key == 'eps':
            ok = got is not None and float(got) == float(want)
        else:
            ok = got == want
        if not ok:
            bad.append(f'PRODUCTION.yaml tiearb.{yaml_key} = {got!r}, the round '
                       f'is frozen at {want!r}')
    if 'phase_gate' in ta and ta['phase_gate'] != L.DEPLOYED_TIEARB['phase_gate']:
        bad.append(f\"PRODUCTION.yaml tiearb.phase_gate = {ta['phase_gate']!r}, \"
                   f\"the round is frozen at \"
                   f\"{L.DEPLOYED_TIEARB['phase_gate']!r}\")
if bad:
    print('⛔ G-PROD: ' + '; '.join(bad))
    print('The opponent of this cell IS the champion of record, so a mismatch '
          'here means the round grades against a stale champion. Resolve it in '
          'the PAIR (an OWNER decision), never by editing the launcher.')
    print('⭐ THE FIX IS THE BUNDLE SYNC, not an edit: sync, re-pin '
          'PINNED_SRC_REV, re-run.')
    sys.exit(1)
print(f'[G-PROD] PRODUCTION.yaml fair_deploy k{k}x{s}={k*s} AND tiearb '
      f'{ {kk: ta.get(kk) for kk in (\"enabled\",\"B\",\"J\",\"mode\",\"salt\",\"eps\")} } '
      '== the frozen deploy (phase_gate absent in the YAML == UNGATED == \"all\")')
"
G_PROD_RC=$?
if [ "$G_PROD_RC" -ne 0 ]; then
  if [ "$DRY" -eq 1 ]; then
    STAMP "⚠️⚠️ G-PROD MISMATCH — continuing ONLY because this is a --dry-run. " \
          "⛔ A --smoke or a real cell from this tree is REFUSED."
  else
    DIE "G-PROD FAILED — the frozen deploy is not the champion of record."
  fi
fi

# The adjudicator's own selftest. ⭐ A PRE-LAUNCH CHECKLIST ITEM precisely
# because a launcher-side gate that runs once per round is NEVER exercised by
# the smoke.
"$PY" "$HERE/analyze_h2h.py" --selftest > "$HERE/SELFTEST_${ROLE}.json" 2>&1 \
  || DIE "analyze_h2h.py --selftest FAILED — see SELFTEST_${ROLE}.json"
STAMP "selftest PASS -> SELFTEST_${ROLE}.json"

# --------------------------------------------------------------------------- #
# ⭐⭐ THE GOLDEN GATE — INHERITED, WITH THE WHEEL RE-ASSERTED (DESIGN §9)      #
# --------------------------------------------------------------------------- #
# ⛔ THIS ROUND DOES NOT BUILD A NEW GOLDEN GATE, AND DESIGN §9 STATES WHY
# RATHER THAN ASSUMING IT:
#   * measurement/fpu_ladder_prep/FPU_BITEXACT_LADDER.json is PASS on wheel
#     a9bb2311ab9a635d and proves fpu=None is the champion BIT-FOR-BIT on that
#     wheel, plus a POSITIVE control at each of 0.05/0.1/0.15/0.3, plus
#     DOSE-DISTINCT. It ran hours ago, not epochs ago.
#   * The check below re-asserts its wheel.binary_sha against THIS BOX's
#     installed binary, so the inheritance is MECHANICALLY CHECKED. If the wheel
#     has moved since the ladder, the inheritance is void and the ladder's own
#     golden_gate/run_golden_gate.sh must be re-run on this box FIRST.
#   * ⛔⛔ ITS TWO GAPS ARE NAMED AND ARE **NOT** WAVED THROUGH: (1) no
#     certificate has ever exercised fpu AND the arbiter together, and (2) 0.2
#     is not one of its four control doses. THE --smoke IDENT LEGS PAY THEM.
# ⚠️ THE ARTEFACT IS BOX-LOCAL AND GITIGNORED (carc_rs_binary_sha differs
# between boxes compiling identical source), which is why this reads the LADDER
# round's copy on THIS box rather than anything committed.
GG="$HERE/../fpu_ladder_prep/FPU_BITEXACT_LADDER.json"
GG_FATAL=1
[ "$DRY" -eq 0 ] || GG_FATAL=0
GG_DIE() { if [ "$GG_FATAL" -eq 1 ]; then DIE "$@"; else
    STAMP "⚠️⚠️ GOLDEN GATE NOT SATISFIED — continuing ONLY because this is a " \
          "--dry-run (it spends nothing). ⛔ A --smoke or a real cell is " \
          "REFUSED. Reason: $*"; fi; }
if [ -f "$GG" ]; then
  grep -q '"verdict": *"PASS"' "$GG" \
    || GG_DIE "the inherited FPU_BITEXACT_LADDER.json is not PASS — fpu=None is " \
              "not proven to be the champion bit-for-bit on this wheel."
  "$PY" -c "
import json,sys
sys.path.insert(0,'$REPO/scripts/human_anchor')
import env_preamble  # noqa: F401
from carcassonne_ai.rust_agent import carc_rs_binary_sha
v = json.load(open('$GG'))
gate_sha = ((v.get('wheel') or {}).get('binary_sha'))
here_sha = carc_rs_binary_sha()
if not gate_sha:
    print('⛔ FPU_BITEXACT_LADDER.json carries no wheel.binary_sha'); sys.exit(1)
if gate_sha != here_sha:
    print(f'⛔⛔ THE INHERITED GOLDEN GATE WAS RUN ON A DIFFERENT WHEEL: gate '
          f'{gate_sha} vs this box {here_sha}. ⚠️ carc_rs_binary_sha is '
          'BOX-LOCAL — two boxes compiling identical source produce different '
          'bytes — AND it moves whenever carc_core is rebuilt. The inheritance '
          'is VOID. Run measurement/fpu_ladder_prep/golden_gate/'
          'run_golden_gate.sh ON THIS BOX, AT THE LAUNCH REV, before this '
          'round.')
    sys.exit(1)
print(f'[GOLDEN GATE] INHERITED PASS on the wheel THIS BOX will play: {here_sha}')
print('⚠️ ITS TWO GAPS ARE PAID BY THE --smoke IDENT LEGS, not by it: (1) no '
      'certificate has exercised fpu AND the arbiter together; (2) 0.2 is not '
      'one of its four control doses (0.05/0.1/0.15/0.3), and all four are '
      'ARBITER-OFF.')
" || GG_DIE "the inherited golden gate does not match this box's wheel — REFUSING."
else
  GG_DIE "measurement/fpu_ladder_prep/FPU_BITEXACT_LADDER.json ABSENT ON THIS " \
      "BOX — ABSENT is FAIL. ⚠️ The artefact is BOX-LOCAL and gitignored, so a " \
      "box that ran the dose ladder HAS one; a box that did not must run " \
      "measurement/fpu_ladder_prep/golden_gate/run_golden_gate.sh first."
fi

# --- the two acts that gate a REAL cell (dry-run and smoke are exempt) ------
if [ "$DRY" -eq 0 ] && [ "$SMOKE" -eq 0 ]; then
  [ "$BLIND_COMMIT" != "PENDING" ] \
    || DIE "⛔⛔ BLIND_COMMIT is PENDING — REFUSING TO LAUNCH A REAL CELL. " \
           "A commit cannot name its own hash; a FOLLOW-UP commit must stamp the " \
           "freeze commit's 40-hex sha into WORKERS.conf first. A read that was " \
           "not blind is not a read."
  echo "$BLIND_COMMIT" | grep -Eq '^[0-9a-f]{40}$' \
    || DIE "BLIND_COMMIT is not a 40-hex sha: $BLIND_COMMIT"
  [ -f "$HERE/BAND_CLAIMED" ] \
    || DIE "⛔⛔ BAND_CLAIMED ABSENT — the band is PROPOSED, not claimed. " \
           "The orchestrator must re-run the tree sweep, append the ONE row from " \
           "BAND_CLAIM.json::_csv_rows to governance/BAND_REGISTRY.csv, and " \
           "THEN drop BAND_CLAIMED. ⚠️ 146e9 is the trap this order exists for."
else
  STAMP "(dry-run/smoke: EXEMPT from BLIND_COMMIT and BAND_CLAIMED — they spend " \
        "no blindness and no band, and play the throwaway sub-range only)"
fi

# --- G-REV's launcher half: the rev pin, asserted BEFORE and AFTER ----------
# ⚠️⚠️ THIS IS THIS FAMILY'S PRIMARY PROVENANCE RISK, AND IT NOW HAS TWO HEADS.
# BOTH the fpu plumbing and the --opp-tiearb-* plumbing are PYTHON-ONLY, so a
# box running pre-fix source serves a dose-FREE candidate and/or an UNARMED
# opponent with a perfectly healthy carc_rs_build, a healthy binary sha and the
# correct leaf hash. The bundle sync + these pins + the two probes below are the
# only thing standing between that and a credible-looking number.
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

# --------------------------------------------------------------------------- #
# ⭐⭐ THE TWO PLUMBING PROBES, ON THIS BOX, FROM THE SOURCE THAT WILL RUN      #
# --------------------------------------------------------------------------- #
# One import each. Both failure modes produce a healthy-looking archive that no
# per-cell gate on the OTHER axis would catch, so both are probed BEFORE the
# compute rather than after it.
"$PY" -c "
import inspect, sys
sys.path.insert(0,'$REPO/scripts/human_anchor')
import env_preamble  # noqa: F401  (freeze the leaf shape before carcassonne_ai)
bad = []

# (1) THE DOSE. If this box's rust_agent.search_config_rs still passes the
#     hard-coded None, the whole cell is champion-vs-champion.
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
from carcassonne_ai.rust_agent import search_config_rs
r = repr(search_config_rs(HeuristicPriorConfig(fpu_reduction=$FPU_DOSE), 8))
if 'fpu=Some($FPU_DOSE)' not in r:
    bad.append('the FPU knob does not bind at $FPU_DOSE: ' + r)

# (2) THE OPPONENT SEAT. ⛔⛔ NEW IN THIS ROUND. Until 2026-08-31
#     eval_fair_puct._make_opponent took NO tiearb parameter and _cfg_from_dict
#     read five keys by name, so the opponent was STRUCTURALLY disarmed. A box
#     on that source arms the CANDIDATE ONLY and produces a CONFOUNDED arb+fpu
#     cell claiming a single variable — with a healthy wheel and leaf hash.
sys.path.insert(0,'$REPO/scripts/classical_search')
import eval_fair_puct as E
if 'tiearb' not in inspect.signature(E._make_opponent).parameters:
    bad.append('eval_fair_puct._make_opponent has NO tiearb parameter')
if not hasattr(E, '_opp_tiearb_telemetry'):
    bad.append('eval_fair_puct has no _opp_tiearb_telemetry (no play-derived '
               'witness for the opponent seat)')
import tiearb_gates as G
if not hasattr(G, 'assert_tiearb_sides'):
    bad.append('scripts/classical_search/tiearb_gates.py has no '
               'assert_tiearb_sides')

if bad:
    print('⛔⛔ THIS BOX CANNOT EXPRESS THE CELL: ' + '; '.join(bad))
    print('The source here predates the fpu plumbing (2026-08-29) and/or the '
          'opponent-side tie-arbiter plumbing (2026-08-31). A cell run from '
          'this box would be champion-vs-champion, or a CONFOUNDED arb+fpu '
          'cell claiming one variable. Sync the bundle.')
    sys.exit(1)
print('[probe] this box binds fpu=$FPU_DOSE AND can arm the OPPONENT seat')
" || DIE "a plumbing probe FAILED on this box — REFUSING."

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
# 2. ONE CELL                                                                  #
# --------------------------------------------------------------------------- #
# `k_dets_override` / `sims_override` / `fpu_flag` exist ONLY so the §9.3 IDENT
# legs can reuse this function at the golden gate's tiny budget with the dose
# dropped. ⛔ THE REAL CELL PASSES NONE OF THEM and runs the frozen production
# knobs; `run_cell` is called with the empty string for each.
run_cell() {
  local name="$1" seed_start="$2" n_games="$3" fpu="$4" kd="$5" sims="$6"
  local out="$SHARE/$OUT_TAG/$name"
  mkdir -p "$out"
  [ -n "$kd" ] || kd="$K_DETS"
  [ -n "$sims" ] || sims="$SIMS_PER_DET"
  local args=(
    "$REPO/scripts/classical_search/eval_fair_puct.py"
    --backend "$BACKEND" --info fair
    --k-dets "$kd" --sims "$sims"
    --opp-k-dets "$kd" --opp-sims "$sims"
    --exact-k "$EXACT_K"
    --opponent fair-champion
    # ⛔⛔ WITHOUT --paired THE ROUND HAS NO PRIMARY (the PG-D9 defect):
    # _build_work returns n DISTINCT decks at ONE seat each when paired is
    # false, so NO deck appears in both seatings, n_paired = 0, and the cell
    # ALSO walks 2*n_decks seeds — outside its own frozen band. With --paired,
    # --n 800 is exactly 400 decks x 2 seatings.
    --n "$n_games" --paired --seed-start "$seed_start"
    # ⚠️ `--out` is AMBIGUOUS in eval_fair_puct (--out-root / --out-subdir) and
    # argparse REFUSES it (PG-D7). The out dir is root/sub, so this pair of
    # flags names EXACTLY the "$SHARE/$OUT_TAG/$name" above.
    --workers "$W" --out-root "$SHARE/$OUT_TAG" --out-subdir "$name"
    # ⚠️ WITHOUT THIS THE ROUND RUNS `walled` — rules_profile's argparse default
    # is DEFAULT_PROFILE ("walled", the pre-F9 engine of record), NOT the
    # fixed_v1 the pair freezes (PG-D8).
    --rules-profile "$RULES_PROFILE"
    # ⭐⭐ THE ARBITER, ON **BOTH** SEATS, AT THE FULL DEPLOYED SPEC.
    # ⛔ The --opp-* half is what makes this cell single-variable. Without it the
    # candidate would be champion+arb+fpu and the opponent plain champion — a
    # CONFOUNDED arb+fpu cell, which is what this leg was INEXPRESSIBLE as until
    # 2026-08-31. G-TIEARB-SIDES and G-TIEARB-FIRE both read the emitted archive
    # for it; this is where it goes on the wire.
    --cand-tiearb-enabled --cand-tiearb-b "$TIEARB_B" --cand-tiearb-j "$TIEARB_J"
    --cand-tiearb-mode "$TIEARB_MODE" --cand-tiearb-salt "$TIEARB_SALT"
    --cand-tiearb-eps "$TIEARB_EPS" --cand-tiearb-phase-gate "$TIEARB_PHASE_GATE"
    --opp-tiearb-enabled --opp-tiearb-b "$TIEARB_B" --opp-tiearb-j "$TIEARB_J"
    --opp-tiearb-mode "$TIEARB_MODE" --opp-tiearb-salt "$TIEARB_SALT"
    --opp-tiearb-eps "$TIEARB_EPS" --opp-tiearb-phase-gate "$TIEARB_PHASE_GATE"
  )
  # ⛔⛔ THE SINGLE VARIABLE — and note there is NO --cand-c-puct, no bare
  # --c-puct and no --tau-p anywhere in this script, by construction. The last
  # two are the SHARED flags: they build champ_cfg_dict, which _make_opponent
  # feeds through the SAME _cfg_from_dict, so they move BOTH SIDES.
  # ⚠️ An EMPTY "$fpu" is the §9.3 IDENT leg B — the dose DROPPED on purpose.
  if [ -n "$fpu" ]; then
    args+=(--cand-fpu-reduction "$fpu")
  fi
  if [ "$BLIND_COMMIT" != "PENDING" ]; then
    args+=(--stamp-key "BLIND_COMMIT=$BLIND_COMMIT")
  fi
  if [ "$DRY" -eq 1 ]; then
    STAMP "[dry-run] $name fpu=${fpu:-NONE} k${kd}x${sims} seeds=${seed_start}.. n=$n_games -> $out"
    printf '    %q ' "$PY" "${args[@]}"; echo
    return 0
  fi
  STAMP "$name fpu=${fpu:-NONE} k${kd}x${sims} seeds=${seed_start}.. n=$n_games W=$W -> $out"
  nice -n 19 "$PY" "${args[@]}" || DIE "$name FAILED"
}

# --------------------------------------------------------------------------- #
# 3. THE SMOKE (DESIGN.md §9.2) + THE IDENT LEGS (§9.3)                        #
# --------------------------------------------------------------------------- #
if [ "$SMOKE" -eq 1 ]; then
  # --- 3a. the production-knobs smoke ---------------------------------------
  # ⭐⭐ Its substantive jobs beyond liveness: drive the REAL argparse and read
  # the RESOLVED DOSE **and the RESOLVED ARBITER DICT FOR BOTH SEATS** back out
  # of the EMITTED manifest.json. That is the PG-D7..D9 lesson plus the
  # 2026-08-31 one, and it is why --smoke-cell is REQUIRED (R1: without a spec
  # the read adjudicated ZERO cells, reported "cells": {} and STILL EXITED 0,
  # making the `|| DIE` below unreachable).
  SMOKE_NAME="SMOKE_H2H"
  SMOKE_SEED=$((THROWAWAY_BASE + 500))
  run_cell "$SMOKE_NAME" "$SMOKE_SEED" "$SMOKE_GAMES" "$FPU_DOSE" "" ""
  if [ "$DRY" -eq 0 ]; then
    "$PY" "$HERE/analyze_h2h.py" --root "$SHARE/$OUT_TAG" --smoke-mode \
      --smoke-cell "${SMOKE_NAME}=fpu_reduction:${FPU_DOSE}:${SMOKE_SEED}:${SMOKE_GAMES}:${ROLE}" \
      --out "$HERE/SMOKE_${ROLE}.json" || DIE "the smoke adjudication FAILED"
    STAMP "smoke adjudicated -> SMOKE_${ROLE}.json (structural keys only)"
  fi

  # --- 3b. ⭐⭐ THE IDENT LEGS ----------------------------------------------
  # ⛔⛔ THE TWO PROPOSITIONS NO BANKED CERTIFICATE COVERS (DESIGN §9.3):
  #   A vs A2  IDENT-REPRODUCES — the arb-on-both-seats path reproduces across
  #            processes. The arbiter is a STOCHASTIC root hook driven by a CRN
  #            salt; if it does not reproduce, this cell's numbers are not
  #            reproducible and NO downstream gate would notice.
  #   A vs B   POSITIVE-ARB-ON — dropping the dose at the SAME seeds with the
  #            arbiter still live CHANGES PLAY. ⛔ The inherited golden gate
  #            CANNOT give this: its positive controls are 0.05/0.1/0.15/0.3 and
  #            all four are ARBITER-OFF.
  # ⚠️ THE BUDGET IS THE GOLDEN GATE'S OWN (k2 x 96), deliberately — the
  # proposition is about a CODE PATH, not a budget, and fpu_reduction is read on
  # EVERY unvisited-child PUCT score. ⛔ NO NUMBER IN THESE LEGS IS A STRENGTH
  # MEASUREMENT.
  IDENT_SEED=$((THROWAWAY_BASE + 700))
  run_cell "SMOKE_IDENT_A"  "$IDENT_SEED" "$IDENT_GAMES" "$FPU_DOSE" \
           "$IDENT_K_DETS" "$IDENT_SIMS"
  run_cell "SMOKE_IDENT_A2" "$IDENT_SEED" "$IDENT_GAMES" "$FPU_DOSE" \
           "$IDENT_K_DETS" "$IDENT_SIMS"
  run_cell "SMOKE_IDENT_B"  "$IDENT_SEED" "$IDENT_GAMES" ""           \
           "$IDENT_K_DETS" "$IDENT_SIMS"
  if [ "$DRY" -eq 0 ]; then
    "$PY" "$HERE/analyze_h2h.py" --ident-mode \
      --ident-a  "$SHARE/$OUT_TAG/SMOKE_IDENT_A" \
      --ident-a2 "$SHARE/$OUT_TAG/SMOKE_IDENT_A2" \
      --ident-b  "$SHARE/$OUT_TAG/SMOKE_IDENT_B" \
      --out "$HERE/IDENT_${ROLE}.json" || DIE "the IDENT adjudication FAILED"
    STAMP "IDENT legs adjudicated -> IDENT_${ROLE}.json"
    STAMP "⚠️ REVIEW SMOKE_${ROLE}.json AND IDENT_${ROLE}.json BY HAND before " \
          "the round: the resolved dose must be $FPU_DOSE on the CANDIDATE " \
          "SIDE ONLY, the resolved arbiter must be the DEPLOYED dict on BOTH " \
          "SEATS with nonzero fires on each, and both IDENT propositions must " \
          "read ok."
  fi
  STAMP "SMOKE DONE role=$ROLE"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 4. THE ROUND — ONE CELL (G-HOST)                                             #
# --------------------------------------------------------------------------- #
echo "$CELLS_JSON" | "$PY" -c "
import json,sys
for c in json.load(sys.stdin):
    print(c['name'], c['role'], c['value'], c['seed_start'], c['n_games'])
" | while read -r name role value seed_start n_games; do
  [ "$role" = "$ROLE" ] || continue
  if [ -f "$SHARE/$OUT_TAG/$name/DONE" ]; then
    STAMP "$name already DONE — skipping"
    continue
  fi
  run_cell "$name" "$seed_start" "$n_games" "$value" "" ""
  [ "$DRY" -eq 1 ] || assert_rev "after:$name"
  [ "$DRY" -eq 1 ] || touch "$SHARE/$OUT_TAG/$name/DONE"
done

STAMP "DONE role=$ROLE"
