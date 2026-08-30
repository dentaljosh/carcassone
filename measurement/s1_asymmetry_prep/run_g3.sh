#!/usr/bin/env bash
# =========================================================================== #
# run_g3.sh — S1 GATE G3'S LAUNCHER (the three-arm decomposition cell)         #
#                                                                             #
# ⛔⛔ THE CELL IS UNLAUNCHED. This script REFUSES a real arm until the         #
#     orchestrator has done the pre-launch acts (READ_RULE_G3.md §7):          #
#       * screen_lib_g3.sanity_check() is non-empty          -> REFUSE         #
#       * analyze_g3.py --selftest FAILS                     -> REFUSE         #
#       * the frozen budget != PRODUCTION.yaml's champion    -> REFUSE         #
#       * the SCOPE KNOB does not bind on this box           -> REFUSE         #
#       * the carc_rs WHEEL predates the R7 witness          -> REFUSE         #
#       * BLIND_COMMIT is still the literal string PENDING   -> REFUSE         #
#       * the sibling BAND_CLAIMED_G3 file does not exist    -> REFUSE         #
#       * PINNED_SRC_REV is absent or does not name HEAD     -> REFUSE         #
#     --dry-run and --smoke are EXEMPT from BLIND_COMMIT and BAND_CLAIMED_G3:  #
#     they spend no blindness and no band (they play the THROWAWAY range).     #
#                                                                             #
# ⛔ THE PAIR IS LAW. Every arm shape, band, knob, budget and box assignment    #
#    is read from screen_lib_g3.py, which is imported by BOTH this launcher's  #
#    precondition ladder and the adjudicator — so a launcher/adjudicator       #
#    drift is impossible by construction rather than by review.                #
#                                                                             #
# ⚠️ W IS THROUGHPUT-ONLY. Games are bit-identical at any W. The ONE clock any  #
#    gate reads is the N4 ms_ratio rider, which is a WITHIN-CELL ratio of the   #
#    two sides on the SAME box and is therefore W-invariant.                   #
#                                                                             #
# USAGE                                                                       #
#   ./run_g3.sh --role local|laptop [--dry-run] [--smoke] [--cell NAME]        #
#                                                                             #
# ⚠️ LAUNCH DETACHED. Joshua's Mac->Windows->WSL setup means Mac-sleep SIGHUP   #
#    AND WSL VM-teardown both kill tty-attached jobs:                          #
#      setsid nohup ./run_g3.sh --role local >> g3_local.log 2>&1 & disown     #
#    and on the laptop: ssh laptop 'bash -s' < run_g3.sh -- --role laptop      #
#    (the inline `ssh host 'cd .. && ..'` form gets the cd STRIPPED IN         #
#    TRANSIT — feedback_remote_ssh_pipe_script_mandatory).                     #
# =========================================================================== #
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
. "$HERE/WORKERS_G3.conf"

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
# and a real arm always runs from the main tree (which the rev pin re-asserts).
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python found" >&2; exit 2; }
case "$ROLE" in
  local)  W="$W_LOCAL";  SHARE="$SHARE_LOCAL" ;;
  laptop) W="$W_LAPTOP"; SHARE="$SHARE_LAPTOP" ;;
  *) echo "--role must be local|laptop" >&2; exit 2 ;;
esac
STAMP() { echo "[run_g3 $(date -u +%FT%TZ) $(hostname)/$ROLE] $*"; }
DIE() { STAMP "!!! $*"; exit 13; }

STAMP "role=$ROLE W=$W budget=k${K_DETS}x${SIMS_PER_DET}=${TOTAL_SIMS} " \
      "dose=$JR_DOSE mask=$JR_MASK tag=$OUT_TAG dry=$DRY smoke=$SMOKE"

# --------------------------------------------------------------------------- #
# 0. THE PRECONDITION LADDER                                                   #
# --------------------------------------------------------------------------- #
# ⭐ Resolved FROM screen_lib_g3, never re-typed here — the launcher and the
# adjudicator read ONE arm table, so they cannot drift apart.
CELLS_JSON="$("$PY" -c "
import json,sys
sys.path.insert(0, '$HERE')
import screen_lib_g3 as L
print(json.dumps([{'name':c.name,'role':c.role,'scope':c.scope,
                   'seed_start':c.seed_start,'n_games':c.n_games} for c in L.CELLS]))
")" || DIE "screen_lib_g3.py did not import — the instrument is broken, not the cell"

# The library's own invariants, BEFORE anything is spent.
"$PY" -c "
import sys; sys.path.insert(0,'$HERE')
import screen_lib_g3 as L
p = L.sanity_check()
sys.exit(0 if not p else print('\n'.join(p)) or 1)
" || DIE "screen_lib_g3.sanity_check() FAILED — the launcher and the adjudicator " \
         "share this file, so a defect here is a defect in BOTH."

# WORKERS_G3.conf must agree with the law it restates.
"$PY" -c "
import sys; sys.path.insert(0,'$HERE')
import screen_lib_g3 as L
want = ($K_DETS, $SIMS_PER_DET, $TOTAL_SIMS)
got  = (L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS)
if want != got:
    print(f'WORKERS_G3.conf budget {want} != screen_lib_g3 {got}'); sys.exit(1)
if $BAND_G3 != L.BAND:
    print('WORKERS_G3.conf BAND_G3 != screen_lib_g3.BAND'); sys.exit(1)
if $THROWAWAY_BASE != L.THROWAWAY_BASE:
    print('WORKERS_G3.conf THROWAWAY_BASE != screen_lib_g3'); sys.exit(1)
if (float('$JR_DOSE'), int('$JR_MASK')) != (L.JR_DOSE, L.JR_MASK):
    print('WORKERS_G3.conf dose/mask != screen_lib_g3'); sys.exit(1)
" || DIE "WORKERS_G3.conf disagrees with screen_lib_g3.py — the pair is law and " \
         "the launcher restates it; a restatement that drifts is a launcher defect."

# ⭐⭐ G-PROD — THE BUDGET-PROMOTION GUARD. The desktop champion moved
# 11008 -> 22016 on 2026-08-30. A frozen budget that has silently drifted from
# PRODUCTION.yaml means the arms measure the scope knob against a STALE OPPONENT
# — strictly worse than a wrong knob, because every other gate passes.
# Read the YAML, do not trust the restatement.
"$PY" -c "
import sys; sys.path.insert(0,'$HERE'); sys.path.insert(0,'$REPO/src')
import screen_lib_g3 as L
import yaml
spec = yaml.safe_load(open('$REPO/governance/PRODUCTION.yaml'))
fd = spec['champion']['fair_deploy']
k, s = int(fd['k_dets']), int(fd['sims_per_det'])
if (k, s, k*s) != (L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS):
    print(f'⛔ G-PROD: PRODUCTION.yaml fair_deploy is k{k}x{s}={k*s}, the cell '
          f'is frozen at k{L.K_DETS}x{L.SIMS_PER_DET}={L.TOTAL_SIMS}. '
          'The opponent of every arm IS the champion of record. Resolve it in '
          'the PAIR (an OWNER decision), never by editing the launcher.')
    sys.exit(1)
print(f'[G-PROD] PRODUCTION.yaml fair_deploy k{k}x{s}={k*s} == the frozen budget')
"
G_PROD_RC=$?
if [ "$G_PROD_RC" -ne 0 ]; then
  # A --dry-run spends NOTHING and its whole purpose is to let a builder read the
  # emitted argv on a tree that is not yet synced, so the mismatch is LOUD but
  # not fatal there. ⛔ It IS fatal for --smoke and for a real arm.
  if [ "$DRY" -eq 1 ]; then
    STAMP "⚠️⚠️ G-PROD MISMATCH — continuing ONLY because this is a --dry-run. " \
          "⛔ A --smoke or a real arm from this tree is REFUSED."
  else
    DIE "G-PROD FAILED — the frozen budget is not the champion of record."
  fi
fi

# The adjudicator's own selftest. ⭐ A PRE-LAUNCH CHECKLIST ITEM precisely
# because a launcher-side gate that runs once per round is NEVER exercised by
# the smoke.
"$PY" "$HERE/analyze_g3.py" --selftest > "$HERE/SELFTEST_G3_${ROLE}.json" 2>&1 \
  || DIE "analyze_g3.py --selftest FAILED — see SELFTEST_G3_${ROLE}.json"
STAMP "selftest PASS -> SELFTEST_G3_${ROLE}.json"

# --- the two acts that gate a REAL arm (dry-run and smoke are exempt) -------
if [ "$DRY" -eq 0 ] && [ "$SMOKE" -eq 0 ]; then
  [ "$BLIND_COMMIT" != "PENDING" ] \
    || DIE "⛔⛔ BLIND_COMMIT is PENDING — REFUSING TO LAUNCH A REAL ARM. " \
           "A commit cannot name its own hash; a FOLLOW-UP commit must stamp " \
           "the freeze commit's 40-hex sha into WORKERS_G3.conf first. " \
           "A read that was not blind is not a read (CL-079 / CL-084)."
  echo "$BLIND_COMMIT" | grep -Eq '^[0-9a-f]{40}$' \
    || DIE "BLIND_COMMIT is not a 40-hex sha: $BLIND_COMMIT"
  [ -f "$HERE/BAND_CLAIMED_G3" ] \
    || DIE "⛔⛔ BAND_CLAIMED_G3 ABSENT — the band is PROPOSED, not claimed. " \
           "The orchestrator must RE-RUN THE TREE SWEEP, append the row(s) " \
           "from BAND_CLAIM_G3.json::_csv_rows to governance/BAND_REGISTRY.csv, " \
           "and THEN drop BAND_CLAIMED_G3. ⚠️ 146e9 is the trap this order " \
           "exists for: absent from the registry but referenced in the tree."
else
  STAMP "(dry-run/smoke: EXEMPT from BLIND_COMMIT and BAND_CLAIMED_G3 — they " \
        "spend no blindness and no band, and play the throwaway sub-range only)"
fi

# --- G-REV's launcher half: the rev pin, asserted BEFORE and AFTER ----------
# ⚠️⚠️ P2 — THE PRIMARY ASYMMETRY CONTRAST — RUNS ITS TWO ARMS ON DIFFERENT
# BOXES (OPP local, OWN laptop). A mixed-rev or mixed-wheel round would land
# ASYMMETRICALLY on exactly that contrast. G-REV catches it at adjudication;
# this catches it before the compute is spent.
PIN_FILE="$HERE/PINNED_SRC_REV_${ROLE}"
assert_rev() {
  [ -f "$PIN_FILE" ] || DIE "PINNED_SRC_REV_${ROLE} ABSENT — ABSENT is FAIL. Run " \
      "'git -C $REPO rev-parse HEAD > $PIN_FILE' ON THIS BOX, after the bundle sync."
  local pin head dirty
  pin="$(tr -d ' \n' < "$PIN_FILE")"
  echo "$pin" | grep -Eq '^[0-9a-f]{40}$' || DIE "PINNED_SRC_REV is not 40-hex"
  head="$(git -C "$REPO" rev-parse HEAD)"
  [ "$pin" = "$head" ] || DIE "⛔ HEAD MOVED under the cell ($head != $pin) — " \
      "refusing rather than banking a MIXED-REV archive."
  dirty="$(git -C "$REPO" status --porcelain -- src engine scripts rust tests | head -5)"
  if [ -n "$dirty" ]; then
    DIE "⛔ a CODE PATH is dirty at $1: $(echo "$dirty" | tr '\n' ' ')"
  fi
  echo "{\"at\":\"$1\",\"utc\":\"$(date -u +%FT%TZ)\",\"role\":\"$ROLE\",\"rev\":\"$pin\",\"clean\":true}" \
    >> "$HERE/SRC_CLEAN_G3.jsonl"
}
assert_rev "before"

# --------------------------------------------------------------------------- #
# ⭐⭐ THE KNOB AND THE WHEEL, ON THIS BOX, FROM THE SOURCE THAT WILL RUN        #
# --------------------------------------------------------------------------- #
# ⛔⛔ TWO SEPARATE REFUSALS, and they fail for DIFFERENT reasons:
#
#   (a) THE SCOPE KNOB. A `carc_rs` predating S1 rejects `scope='opp'` at config
#       construction (fail-closed ValueError, never a silent champion-vs-champion
#       null). Good — but it must be proven HERE, per box, not assumed.
#
#   (b) ⭐ THE R7 WITNESS WHEEL (2026-08-30). G-WITNESS reads the play-derived
#       `jr_expansions` census, and those pyo3 stats fields only exist in a wheel
#       rebuilt AFTER the R7 witness landed. On a stale wheel an armed candidate
#       now raises "STALE carc_rs wheel" LOUDLY rather than banking a config
#       echo — which is fail-closed and correct, but it wastes the launch and, on
#       the laptop, wastes it silently until someone reads the log. ⛔ G3 MUST NOT
#       LAUNCH UNTIL THE WHEEL IS REBUILT AND INSTALLED ON **EVERY** PARTICIPATING
#       BOX. This probe is the cheap version of that rule.
"$PY" -c "
import sys
sys.path.insert(0,'$REPO/scripts/human_anchor')
try:
    import env_preamble  # noqa: F401  (freeze the leaf shape before carcassonne_ai)
except Exception:
    pass
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
from carcassonne_ai.rust_agent import search_config_rs

# (a) the scope knob binds at all
try:
    cfg = HeuristicPriorConfig(jrules_prior_dose=$JR_DOSE,
                               jrules_prior_mask=$JR_MASK,
                               jrules_prior_scope='opp')
except Exception as e:
    print('⛔⛔ HeuristicPriorConfig REFUSED scope=opp on this box: %r' % (e,))
    print('The python source here predates S1. Sync the bundle.')
    sys.exit(1)
try:
    r = repr(search_config_rs(cfg, $K_DETS))
except Exception as e:
    print('⛔⛔ THIS BOX CANNOT EXPRESS scope=opp INTO carc_rs: %r' % (e,))
    print('A carc_rs predating S1 rejects scope at config construction. '
          'REBUILD AND INSTALL THE WHEEL ON THIS BOX.')
    sys.exit(1)
if 'opp' not in r.lower():
    print('⛔⛔ the resolved SearchConfigRs does not carry the scope: ' + r)
    sys.exit(1)
print('[knob] this box binds jrules_prior_scope: ' + r)

# (b) ⭐ THE R7 WITNESS FIELDS. Without them G-WITNESS VOIDS every arm this box
# runs, so refuse now rather than after 10 hours of compute.
# G3-D1 (2026-08-30, pre-launch, statistics-blind): the original probe grepped
# dir(carc_rs) for 'jr_expansions' — but the fields are DICT KEYS returned by
# FairAgentRs.stats(), invisible to dir() by construction, so the probe refused
# a HEALTHY wheel (ad211fd3) whose emitted smoke summary carried the real
# counters (SMOKE_OPP: candidate boosted 4,528,040 / opponent 0, G-WITNESS
# PASS). Replaced with the honest probe: one throwaway 8-sim search, then read
# the stats() keys themselves.
try:
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.rust_agent import RustFairAgent
    from carcassonne_ai.champion_factory import production_prior_cfg
    _g = Game()
    _a = RustFairAgent(_g, production_prior_cfg(), sims=4, k_dets=2, seed=1)
    _a.get_action(_g.get_init_board())
    _keys = set(_a._rs.stats())
except Exception as e:
    print('⛔ witness probe could not run a throwaway search: %r' % (e,)); sys.exit(9)
_need = {'jr_expansions_total', 'jr_expansions_own_mover', 'jr_expansions_boosted'}
if not _need <= _keys:
    print('⛔⛔ STALE carc_rs WHEEL (probe): stats() lacks %s on this box. '
          'G-WITNESS reads the play-derived expansion census and ABSENT is '
          'VOID. REBUILD AND INSTALL THE WHEEL ON THIS BOX, re-pin '
          'PINNED_SRC_REV_${ROLE}, re-run.' % (sorted(_need - _keys),))
    sys.exit(9)
print('[wheel] the R7 jr_expansions witness surface is present on this box')
"
KNOB_RC=$?
if [ "$KNOB_RC" -eq 9 ]; then
  # ⚠️⚠️ THE PROBE IS NECESSARILY WEAKER THAN THE GATE, and saying so is the
  # point. It walks `dir()` over the module and its top-level classes; if the R7
  # build surfaces the census only as a KEY IN A RETURNED DICT, `dir()` cannot
  # see it and a healthy box would be refused forever — a launcher-side PG-A1
  # (a gate no healthy box can pass).
  #
  # ⭐ SO THE SMOKE, NOT THE PROBE, IS THE BINDING CHECK: it plays real games and
  # `G-WITNESS` reads `jr_expansions` out of the EMITTED `summary.json`, which is
  # the only authoritative answer. The smoke is therefore allowed through a
  # failed probe (loudly) — it is 8 games on the throwaway range and it SETTLES
  # the question. ⛔ A REAL ARM IS NOT: it is fail-closed, exactly as G-PROD is.
  if [ "$SMOKE" -eq 1 ] || [ "$DRY" -eq 1 ]; then
    STAMP "⚠️⚠️ THE WHEEL PROBE FOUND NO jr_expansions SURFACE. Continuing " \
          "ONLY because this is a --smoke/--dry-run: the smoke's own " \
          "G-WITNESS adjudication reads the EMITTED summary.json and is the " \
          "binding check. ⛔ IF THE SMOKE'S G-WITNESS FAILS, THE WHEEL IS " \
          "STALE — REBUILD IT ON THIS BOX BEFORE THE ROUND. A real arm from " \
          "this tree is REFUSED."
  else
    DIE "⛔⛔ THE R7 WITNESS WHEEL IS NOT INSTALLED ON THIS BOX — REFUSING. " \
        "G3 MUST NOT LAUNCH UNTIL carc_rs IS REBUILT AND INSTALLED ON EVERY " \
        "PARTICIPATING BOX (READ_RULE_G3 §7.5). If you believe the probe is " \
        "wrong, run './run_g3.sh --role $ROLE --smoke' — its G-WITNESS reads " \
        "the EMITTED summary.json and is the authoritative answer."
  fi
elif [ "$KNOB_RC" -ne 0 ]; then
  DIE "the scope knob is NOT usable on this box — REFUSING."
fi

# --- census by FULL ARGS, never -C python ----------------------------------
# ⚠️ QUANTIFIED 2026-08-26: ONE niced 1-core DRAM-churner inflated a saturated
# W=22 eval ~1.8x/move. The only clock any gate here reads is the WITHIN-CELL
# N4 ms_ratio (both sides on the same box, so tenancy is common-mode and the
# rider is RESULT-safe) — but the census is still owed, and a silent long job is
# invisible to `ps -C python`.
STAMP "process census (FULL ARGS):"
ps -eo pid,etime,pcpu,args --sort=-etime | grep -E "python|carc" | grep -v grep \
  | head -20 | sed 's/^/    /'

export CARCASSONNE_FIX_R9="$CARCASSONNE_FIX_R9"   # ⚠️ env-latched at IMPORT
export PYTHONUNBUFFERED=1

# --------------------------------------------------------------------------- #
# 1. ONE ARM                                                                   #
# --------------------------------------------------------------------------- #
run_cell() {
  local name="$1" scope="$2" seed_start="$3" n_games="$4"
  local out="$SHARE/$OUT_TAG/$name"
  # ⭐ G-HOST is structural here: DISJOINT --out-subdir per arm means there are
  # no shared claims to race over, which is the real protection. The manifest's
  # `host` proves the arm ran on the box it was assigned.
  mkdir -p "$out"
  local args=(
    "$REPO/scripts/classical_search/eval_fair_puct.py"
    --backend "$BACKEND" --info fair
    --k-dets "$K_DETS" --sims "$SIMS_PER_DET"
    --opp-k-dets "$K_DETS" --opp-sims "$SIMS_PER_DET"
    --exact-k "$EXACT_K"
    --opponent fair-champion
    # ⛔⛔ WITHOUT --paired THE CELL HAS NO PRIMARY (the PG-D9 defect):
    # eval_fair_puct._build_work returns n DISTINCT decks at ONE seat each when
    # paired is false, so NO deck appears in both seatings, n_paired = 0 on
    # every arm, and the arm ALSO walks 2*n_decks seeds — OUTSIDE its own band,
    # which would ALSO break the CRN that P2 is funded on.
    --n "$n_games" --paired --seed-start "$seed_start"
    # ⚠️ `--out` is AMBIGUOUS in eval_fair_puct (--out-root / --out-subdir) and
    # argparse REFUSES it (PG-D7). The out dir is root/sub, so this pair of
    # flags names EXACTLY the "$SHARE/$OUT_TAG/$name" above.
    --workers "$W" --out-root "$SHARE/$OUT_TAG" --out-subdir "$name"
    # ⚠️ WITHOUT THIS THE CELL RUNS `walled` — rules_profile's argparse default
    # is DEFAULT_PROFILE ("walled", the pre-F9 engine of record), NOT the
    # fixed_v1 the pair freezes (PG-D8). G-RULES asserts fixed_v1, so every arm
    # would have voided at adjudication.
    --rules-profile "$RULES_PROFILE"
    # ⛔⛔ THE SINGLE VARIABLE. All three flags are --cand-*, i.e. CANDIDATE-SIDE
    # ONLY: `_cfg_from_dict` threads `jrules_prior` into the candidate alone
    # (eval_fair_puct.py:2156-2167), and `_make_opponent` builds from the SHARED
    # `champ_cfg_dict`, which carries no jrules key at all. There is NO shared
    # `--jrules-prior-*` flag to get this wrong with — unlike `--c-puct`, whose
    # both-sides trap is what produced the FPU round's DEVIATIONS D1.
    # ⚠️ DOSE AND MASK ARE IDENTICAL ON EVERY ARM. Scope is the only mover.
    --cand-jrules-prior-dose "$JR_DOSE"
    --cand-jrules-prior-mask "$JR_MASK"
    --cand-jrules-prior-scope "$scope"
    # ⛔ There is deliberately NO --cand-tiearb-* flag here: the arbiter is OFF
    # on both sides (WORKERS_G3.conf's arbiter block), by construction.
  )
  if [ "$BLIND_COMMIT" != "PENDING" ]; then
    args+=(--stamp-key "BLIND_COMMIT=$BLIND_COMMIT")
  fi
  if [ "$DRY" -eq 1 ]; then
    STAMP "[dry-run] $name scope=$scope seeds=${seed_start}.. n=$n_games -> $out"
    printf '    %q ' "$PY" "${args[@]}"; echo
    return 0
  fi
  # FREEZE LATCH. Each arm's workers re-import `carcassonne_ai` and `carc_rs`
  # FROM DISK on respawn, so a source edit or a wheel reinstall mid-run silently
  # produces MIXED-REV archives inside one out-dir. The sentinel makes main-tree
  # commits refuse while this is live; the trap clears it on every exit path.
  local latch="$out/RUN_LIVE.json"
  printf '{"run":"s1_g3","cell":"%s","out":"%s","pid":%d,"started":"%s","workers":%s}\n' \
    "$name" "$out" "$$" "$(date -Is)" "$W" > "$latch"
  # shellcheck disable=SC2064
  trap "rm -f '$latch'" EXIT INT TERM
  STAMP "$name scope=$scope seeds=${seed_start}.. n=$n_games W=$W -> $out"
  nice -n 19 "$PY" "${args[@]}"
  local rc=$?
  rm -f "$latch"
  trap - EXIT INT TERM
  [ "$rc" -eq 0 ] || DIE "$name FAILED rc=$rc"
  assert_rev "after:$name"
}

# --------------------------------------------------------------------------- #
# 2. THE SMOKE                                                                 #
# --------------------------------------------------------------------------- #
# Per box, at that box's OWN frozen W, on the THROWAWAY sub-range, PRODUCTION
# KNOBS, only the game count reduced. ⛔ The smoke emits NO OUTCOME KEY.
# ⭐⭐ Its two substantive jobs beyond liveness:
#   (1) it drives the REAL argparse and the adjudicator reads the RESOLVED SCOPE
#       back out of the EMITTED manifest (the PG-D7..D9 lesson: three separate
#       launcher defects — an ambiguous --out, a defaulted rules profile, a
#       missing --paired — all survived review and were only caught by a smoke
#       adjudicated against emitted output);
#   (2) ⭐ it proves the scope BOUND IN PLAY via the R7 `jr_expansions` census —
#       the pre-launch condition G1's verdict set, because a played `scope=opp`
#       cell used to carry only a config echo.
# ⚠️ EVERY SCOPE THIS BOX WILL RUN IS SMOKED. "It is the same code path" is
# exactly the argument that produced the FPU round.
if [ "$SMOKE" -eq 1 ]; then
  case "$ROLE" in
    local)  SMOKE_SCOPES="opp all" ;;
    laptop) SMOKE_SCOPES="own" ;;
  esac
  SPECS=()
  i=0
  for sc in $SMOKE_SCOPES; do
    nm="SMOKE_$(echo "$sc" | tr '[:lower:]' '[:upper:]')"
    sd=$((THROWAWAY_BASE + 500 + i * 20))
    run_cell "$nm" "$sc" "$sd" "$SMOKE_GAMES"
    SPECS+=(--smoke-cell "${nm}=${sc}:${sd}:${SMOKE_GAMES}:${ROLE}")
    i=$((i + 1))
  done
  if [ "$DRY" -eq 0 ]; then
    # ⭐ Adjudicated against the EMITTED archive, so `resolved_scopes` in the
    # output is read off manifest.json / summary.json rather than restated from
    # the command line.
    # ⭐⭐ `--smoke-cell` IS REQUIRED (the FPU R1 fix, carried). `--root` is the
    # PARENT, and the cell table names only the three ROUND arms, so without
    # this flag a smoke read adjudicates ZERO cells, reports `"cells": {}` and
    # STILL EXITS 0 — the `|| DIE` below would be UNREACHABLE and the smoke
    # would prove nothing. The spec is passed from HERE (the launcher is the
    # only thing that knows what it asked for) and analyze_g3 then checks it
    # against the EMITTED documents.
    "$PY" "$HERE/analyze_g3.py" --root "$SHARE/$OUT_TAG" --smoke-mode \
      "${SPECS[@]}" --out "$HERE/SMOKE_G3_${ROLE}.json" \
      || DIE "the smoke adjudication FAILED — see SMOKE_G3_${ROLE}.json and the " \
             "stderr above. ⛔ DO NOT LAUNCH THE ROUND."
    "$PY" -c "
import json
d = json.load(open('$HERE/SMOKE_G3_${ROLE}.json'))
print('[smoke] resolved scopes + witness FROM THE EMITTED DOCUMENTS:')
print(json.dumps(d.get('resolved_scopes') or {}, indent=2)[:4000])
" || true
    STAMP "smoke adjudicated -> SMOKE_G3_${ROLE}.json (structural keys only)"
    STAMP "⚠️ REVIEW SMOKE_G3_${ROLE}.json BY HAND before the round: the " \
          "resolved scope must be the one this box will run, and " \
          "jr_expansions.candidate.boosted must be > 0 with " \
          "jr_expansions.opponent.boosted == 0."
  fi
  STAMP "SMOKE DONE role=$ROLE"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 3. THE ROUND — whole arms per box (G-HOST)                                   #
# --------------------------------------------------------------------------- #
# ⭐ local:laptop capacity is ~1.49:1 (W 30 vs 22/1.0935), so OPP(1200) +
# ALL(800) local and OWN(1200) laptop is the balanced whole-arm split of 3,200
# games. ⚠️ P2's two arms therefore sit on different boxes — DISCLOSED in
# screen_lib_g3.CELLS and gated by the round-level G-REV/G-TOOL. The co-located
# variant (run all three with --role local) changes NO bar, NO band and NO seed.
echo "$CELLS_JSON" | "$PY" -c "
import json,sys
for c in json.load(sys.stdin):
    print(c['name'], c['role'], c['scope'], c['seed_start'], c['n_games'])
" | while read -r name role scope seed_start n_games; do
  [ "$role" = "$ROLE" ] || continue
  [ -z "$ONLY_CELL" ] || [ "$ONLY_CELL" = "$name" ] || continue
  if [ -f "$SHARE/$OUT_TAG/$name/DONE" ]; then
    STAMP "$name already DONE — skipping"
    continue
  fi
  run_cell "$name" "$scope" "$seed_start" "$n_games"
  [ "$DRY" -eq 1 ] || touch "$SHARE/$OUT_TAG/$name/DONE"
done

STAMP "DONE role=$ROLE"
