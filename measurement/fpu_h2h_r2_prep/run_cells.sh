#!/usr/bin/env bash
# =========================================================================== #
# run_cells.sh — THE FPU PRODUCTION-H2H **ROUND 2** LAUNCHER                    #
#                                                                             #
# ⛔⛔ THE ROUND IS UNLAUNCHED. This script REFUSES a real chunk until the      #
#     orchestrator has done the pre-launch acts (DESIGN.md §8):               #
#       * this box's W is still TBD_FROM_SWEEP              -> REFUSE          #
#       * screen_lib.sanity_check() is non-empty            -> REFUSE          #
#       * analyze_h2h.py --selftest FAILS                   -> REFUSE          #
#       * the INHERITED golden gate is absent / not PASS    -> REFUSE          #
#       * the golden gate's wheel != THIS BOX's wheel       -> REFUSE          #
#       * the frozen budget != PRODUCTION.yaml's champion   -> REFUSE          #
#       * the frozen ARBITER != PRODUCTION.yaml's tiearb    -> REFUSE          #
#       * this box cannot express fpu_reduction=0.2         -> REFUSE          #
#       * this box has no --opp-tiearb-* plumbing           -> REFUSE          #
#       * BLIND_COMMIT is still the literal string PENDING  -> REFUSE          #
#       * the sibling BAND_CLAIMED file does not exist      -> REFUSE          #
#       * PINNED_SRC_REV is absent or does not name HEAD    -> REFUSE          #
#       * a CODE PATH is dirty, before OR after a chunk     -> REFUSE          #
#       * a chunk is CLAIMED BY THE OTHER BOX and has       -> REFUSE          #
#         records on disk (--reclaim only frees an EMPTY one)                 #
#     --dry-run, --plan and --smoke are EXEMPT from BLIND_COMMIT and          #
#     BAND_CLAIMED: they spend no blindness and no band (the smoke plays the  #
#     THROWAWAY range).                                                       #
#     ⚠️ --dry-run and --plan are additionally exempt from G-PROD and the      #
#     GOLDEN GATE (loud, not fatal) — they spend NO compute at all.           #
#     ⛔ --smoke is NOT exempt from either: it is real play on the real wheel. #
#     ⛔ NOTHING is exempt from the W check for the box it is running on.      #
#                                                                             #
# ⭐⭐ THE FLEXIBLE-BOX CLAUSE (DESIGN.md §6.4), PRE-REGISTERED BEFORE GAME 1:  #
#     BOX ASSIGNMENT IS **THROUGHPUT-ONLY** AND MAY CHANGE MID-ROUND. The 800  #
#     decks are executed as 8 CHUNKS of 100 that TILE the band; a chunk is the #
#     unit of box assignment AND of provenance. Frozen at launch: the LAPTOP   #
#     plays the full range. To add local later:                               #
#                                                                             #
#       1. CLEAN STOP of the laptop main, by EXACT PID (never `pkill -f`):     #
#            ssh laptop 'ps -eo pid,etime,pcpu,args' | grep eval_fair_puct     #
#            ssh laptop 'kill <MAIN_PID>'      # the mp MAIN first             #
#            ...let it settle...                                              #
#            ssh laptop 'ps -eo pid,args' | grep eval_fair_puct   # survivors  #
#            ssh laptop 'kill <SURVIVOR_PIDS>'  # spawn workers do NOT reap    #
#          ⚠️ A LIVE Pool REPLACES killed workers — kill the MAIN first, let   #
#          it settle, THEN the survivors (feedback_isolate_destructive_tool_   #
#          calls). ⛔ Never `pkill -f eval_fair_puct`: it would also match     #
#          this script's own command line.                                    #
#       2. ./run_cells.sh --role laptop --plan   # what is DONE / partial      #
#       3. Relaunch BOTH boxes on DISJOINT sub-ranges of the UN-PLAYED         #
#          remainder, e.g.                                                    #
#            laptop: ./run_cells.sh --role laptop --chunks 3-5                 #
#            local : ./run_cells.sh --role local  --chunks 6-7                 #
#          ⭐ Cached per-game records are skipped by the harness itself        #
#          (eval_fair_puct: `todo = [t for t in tasks if not <record>.exists`),#
#          so resuming an interrupted chunk costs only its unplayed games.     #
#                                                                             #
#     ⚠️⚠️ `eval_fair_puct` HAS NO --seed-lo/--seed-hi. Range restriction is   #
#     implemented HERE, by per-chunk seed-start/count arithmetic:              #
#         --seed-start <chunk lo>   --n <2 * decks_per_chunk>   --paired       #
#     (`_build_work(seed_start, n, paired=True)` yields seeds                  #
#      `seed_start .. seed_start + n/2 - 1`, each at a_seat 0 and 1). The      #
#     `--seed-lo/--seed-hi` flags below are a convenience over the SAME        #
#     arithmetic and MUST be chunk-aligned; screen_lib.CellSpec.               #
#     chunks_for_seed_range RAISES otherwise, because a partial chunk would    #
#     put two boxes' records in ONE out-dir — and that dir emits ONE           #
#     manifest.json with ONE `host`, so the provenance map would become a      #
#     silent lie that no gate could see.                                       #
#                                                                             #
# ⛔ THE PAIR IS LAW. The cell shape, band, chunking, dose, budget, arbiter    #
#    spec and box set are read from screen_lib.py, which is imported by BOTH   #
#    this launcher's precondition ladder and the adjudicator — so a launcher/  #
#    adjudicator drift is impossible by construction rather than by review.    #
#                                                                             #
# ⚠️ W IS THROUGHPUT-ONLY. Games are bit-identical at any W and no gate in     #
#    this pair reads a clock.                                                 #
#                                                                             #
# USAGE                                                                       #
#   ./run_cells.sh --role laptop [--chunks 0-7 | --seed-lo N --seed-hi N]     #
#                  [--plan] [--dry-run] [--smoke] [--reclaim]                 #
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

ROLE=""; DRY=0; SMOKE=0; PLAN=0; RECLAIM=0
CHUNK_SPEC=""; SEED_LO=""; SEED_HI=""
while [ $# -gt 0 ]; do
  case "$1" in
    --role) ROLE="$2"; shift 2 ;;
    --chunks) CHUNK_SPEC="$2"; shift 2 ;;
    --seed-lo) SEED_LO="$2"; shift 2 ;;
    --seed-hi) SEED_HI="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --plan) PLAN=1; shift ;;
    --reclaim) RECLAIM=1; shift ;;
    --) shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$ROLE" ] || { echo "--role laptop|local is required" >&2; exit 2; }

# ⚠️ The venv is editable-installed against the MAIN tree, so a copy of this
# script running from a git WORKTREE has no `.venv` beside it. Fall back to the
# canonical one rather than dying — the worktree case is a BUILD/dry-run case,
# and a real chunk always runs from the main tree (which the rev pin re-asserts).
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python found" >&2; exit 2; }

STAMP() { echo "[run_cells $(date -u +%FT%TZ) $(hostname)/$ROLE] $*"; }
DIE() { STAMP "!!! $*"; exit 13; }

# --------------------------------------------------------------------------- #
# ⭐⭐ 0a. THE BOX — BOTH ARE LEGAL, AND THAT IS THE POINT (DESIGN §6.4)        #
# --------------------------------------------------------------------------- #
# ⛔ Round 1 was LAPTOP ONLY and refused --role local at launch. ROUND 2 DOES
# NOT: the owner funded a flexible split, box assignment is THROUGHPUT-ONLY, and
# the read pools every chunk on the one band. What replaces that refusal is
# PROVENANCE — every chunk stamps its own host, G-HOST publishes the chunk ->
# host -> range map, and G-NODUP proves the ranges did not overlap.
# ⚠️ THE SHARE MOUNT PATH DIFFERS BY BOX and both are defined in WORKERS.conf.
case "$ROLE" in
  laptop) W="$W_LAPTOP"; SHARE="$SHARE_LAPTOP"; W_VAR="W_LAPTOP" ;;
  local)  W="$W_LOCAL";  SHARE="$SHARE_LOCAL";  W_VAR="W_LOCAL" ;;
  *) DIE "--role must be laptop or local" ;;
esac
OUT_ROOT="$SHARE/$OUT_TAG"

# --------------------------------------------------------------------------- #
# ⛔⛔ 0b. THIS BOX'S W MUST BE THE SWEPT VALUE — NOT EXEMPT FOR ANYTHING       #
# --------------------------------------------------------------------------- #
# ⚠️ W is THROUGHPUT-ONLY and moves no bar, gate or branch — so this refusal is
# NOT about correctness of the statistic. It is about the SMOKE meaning
# something: a smoke run at a W the box will not run is a smoke of a different
# tenancy (feedback_no_agent_compute_beside_eval quantified a 1.8x/move
# inflation from ONE stray niced core), and about the ETA the orchestrator
# reports being derived from the W actually used.
# ⭐ W_LAPTOP is BANKED (26, the 2026-08-31 arb-on sweep) so the laptop launches
# NOW. ⛔ W_LOCAL is UNSET because no arb-on LOCAL sweep exists at the freeze
# commit — LOCAL CANNOT JOIN UNTIL IT IS STAMPED, and that refusal is the
# round-1 W_LAPTOP refusal carried forward onto the box that now needs it.
if [ "$PLAN" -eq 0 ]; then
  case "$W" in
    ''|*[!0-9]*)
      DIE "⛔⛔ $W_VAR is '$W' — THE SWEPT VALUE HAS NOT BEEN STAMPED for the "\
          "'$ROLE' box, so this box may not play. The orchestrator writes the "\
          "sweep's result into WORKERS.conf ($W_VAR=<int>) at launch. "\
          "⭐ NOTHING ELSE in the pair moves with it: DESIGN §6 gives the ETA "\
          "as a FORMULA in W precisely so this number can be filled in last. "\
          "⚠️ For --role local the sweep is measurement/wsweep_local_*/"\
          "READOUT.md; the LAPTOP is already stamped at $W_LAPTOP and is "\
          "unaffected." ;;
  esac
  [ "$W" -ge 1 ] || DIE "$W_VAR=$W must be >= 1"
fi

STAMP "role=$ROLE W=${W} budget=k${K_DETS}x${SIMS_PER_DET}=${TOTAL_SIMS} " \
      "arb=B${TIEARB_B}/J${TIEARB_J}/${TIEARB_MODE}/${TIEARB_PHASE_GATE} " \
      "fpu=$FPU_DOSE band=$BAND_H2H chunks=${CHUNK_SPEC:-ALL} " \
      "out=$OUT_ROOT dry=$DRY smoke=$SMOKE plan=$PLAN"

# --------------------------------------------------------------------------- #
# 1. THE PRECONDITION LADDER                                                   #
# --------------------------------------------------------------------------- #
# ⭐ Resolved FROM screen_lib, never re-typed here — the launcher and the
# adjudicator read ONE chunk plan, so they cannot drift apart.
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
if ($N_CHUNKS, $DECKS_PER_CHUNK) != (L.N_CHUNKS, L.DECKS_PER_CHUNK):
    print(f'WORKERS.conf chunking ($N_CHUNKS x $DECKS_PER_CHUNK) != screen_lib '
          f'({L.N_CHUNKS} x {L.DECKS_PER_CHUNK})'); sys.exit(1)
if len(L.CELLS) != 1:
    print(f'the round is not ONE cell: {[c.name for c in L.CELLS]}'); sys.exit(1)
if '$ROLE' not in L.ROLES:
    print(f'role $ROLE is not one of the funded boxes {L.ROLES}'); sys.exit(1)
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
# ⭐⭐ 1b. RESOLVE THIS INVOCATION'S CHUNKS (the range-restriction arithmetic)  #
# --------------------------------------------------------------------------- #
# ⛔ ONE implementation, in screen_lib, shared with the adjudicator. It RAISES
# on a non-chunk-aligned --seed-lo/--seed-hi rather than silently rounding.
CHUNKS="$("$PY" -c "
import sys; sys.path.insert(0,'$HERE')
import screen_lib as L
c = L.CELLS[0]
spec, lo, hi = '$CHUNK_SPEC', '$SEED_LO', '$SEED_HI'
if spec and (lo or hi):
    print('give --chunks OR --seed-lo/--seed-hi, not both', file=sys.stderr)
    sys.exit(1)
try:
    if spec:
        a, _, b = spec.partition('-')
        b = b or a
        idx = list(range(int(a), int(b) + 1))
        for i in idx:
            c.chunk_range(i)          # IndexError if out of range
    elif lo or hi:
        if not (lo and hi):
            print('--seed-lo and --seed-hi must be given together',
                  file=sys.stderr)
            sys.exit(1)
        idx = c.chunks_for_seed_range(int(lo), int(hi))
    else:
        idx = list(range(c.n_chunks))
except (ValueError, IndexError) as e:
    print(str(e), file=sys.stderr); sys.exit(1)
for i in idx:
    a, b = c.chunk_range(i)
    print(f'{i} {c.chunk_name(i)} {a} {b} {c.decks_per_chunk * 2}')
")" || DIE "the chunk range could not be resolved — see the message above. " \
           "⛔ DESIGN §6.4 assigns WHOLE CHUNKS: a partial chunk would put two " \
           "boxes' records in ONE out-dir, which emits ONE manifest with ONE " \
           "host, and the provenance map would silently become false."
STAMP "chunks this invocation owns:"
echo "$CHUNKS" | sed 's/^/    /'

# --------------------------------------------------------------------------- #
# ⭐ 1c. --plan — READ THE SHARE, REPORT STATE, PROPOSE A SPLIT. NO COMPUTE.    #
# --------------------------------------------------------------------------- #
# ⛔ It spends nothing: no band, no blindness, no games, no W. It exists so the
# owner's "add local now" decision is made against DISK, not against memory.
if [ "$PLAN" -eq 1 ]; then
  "$PY" -c "
import json, sys
from pathlib import Path
sys.path.insert(0,'$HERE')
import screen_lib as L
c = L.CELLS[0]
root = Path('$OUT_ROOT')
rows, remaining_games = [], 0
for row in L.chunk_plan(c):
    d = root / row['name']
    recs = sorted(d.glob('seed*_a*.json')) if d.is_dir() else []
    man = d / 'manifest.json'
    summ = d / 'summary.json'
    claim = d / 'CLAIM.json'
    host = None
    if claim.is_file():
        try:
            host = json.loads(claim.read_text()).get('host')
        except Exception:
            host = '<unreadable CLAIM.json>'
    elif man.is_file():
        try:
            host = json.loads(man.read_text()).get('host')
        except Exception:
            host = '<unreadable manifest>'
    done = (d / 'DONE').is_file()
    state = ('DONE' if done and summ.is_file() else
             'COMPLETE-NO-SENTINEL' if summ.is_file() else
             'PARTIAL (resume it — records are cached)' if recs else
             'UNTOUCHED')
    remaining_games += 0 if summ.is_file() else (row['n_games'] - len(recs))
    rows.append({'chunk': row['chunk'], 'name': row['name'],
                 'seeds': [row['seed_lo'], row['seed_hi']],
                 'games_on_disk': len(recs), 'games_total': row['n_games'],
                 'summary': summ.is_file(), 'manifest': man.is_file(),
                 'claimed_by': host, 'state': state})
free = [r for r in rows if r['state'] != 'DONE']
gl, gc = $G_PER_H_LAPTOP, $G_PER_H_LOCAL
share_laptop = gl / float(gl + gc)
n_lap = max(0, min(len(free), round(len(free) * share_laptop)))
plan = {
 'out_root': str(root),
 'chunks': rows,
 'remaining_games': remaining_games,
 'eta_h_laptop_only': round(remaining_games / float(gl), 2),
 'eta_h_both_boxes': round(remaining_games / float(gl + gc), 2),
 'rates_g_per_h': {'laptop_MEASURED_W26_arb_on': gl,
                   'local_MEASURED_W30_arb_on': gc},
 'suggested_split': {
   'laptop': [r['name'] for r in free[:n_lap]],
   'local':  [r['name'] for r in free[n_lap:]]},
 '⛔ WARNINGS': [
  '⛔ THIS IS A THROUGHPUT PLAN AND NOTHING ELSE. Box assignment moves no bar, '
  'gate or branch (DESIGN §6.4).',
  '⛔ AN INTERRUPTED CHUNK IS RESUMED ON THE BOX THAT CLAIMED IT. --reclaim '
  'frees a chunk ONLY if it has ZERO records; a partially-played chunk that '
  'changed hands would put two hosts inside one out-dir, which emits ONE '
  'manifest with ONE host, and G-HOST would publish a false map.',
  '⛔ A BOX WHOSE W READS TBD_FROM_SWEEP CANNOT PLAY, in any mode. The split '
  'above is arithmetic, not a licence.',
  '⭐ BOTH RATES ARE MEASURED, arb-on, at this round exact cell shape (laptop '
  'W26 = 135 g/h from round 1; local W30 = 162.0 g/h from '
  'measurement/wsweep_local_20260831). Still re-derive from each box own first '
  'hour (feedback_eta_before_launch: use the MEAN over completed records, '
  'never the first completions of a parallel run).',
 ]}
print(json.dumps(plan, indent=2, ensure_ascii=False))
" | tee "$HERE/PLAN_${ROLE}.json"
  STAMP "plan written -> PLAN_${ROLE}.json (⛔ NO COMPUTE SPENT)"
  exit 0
fi

# --------------------------------------------------------------------------- #
# ⭐⭐ G-PROD — THE DEPLOY GUARD: BUDGET **AND** ARBITER                        #
# --------------------------------------------------------------------------- #
# The opponent of this cell IS the DEPLOYED champion — budget AND arbiter. A
# frozen constant that has silently drifted from PRODUCTION.yaml means the cell
# grades the dose against a stale champion, and every other gate passes it.
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
          "⛔ A --smoke or a real chunk from this tree is REFUSED."
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
# RATHER THAN ASSUMING IT. Its inheritance now has THREE sources, and the third
# is new to round 2:
#   * measurement/fpu_ladder_prep/FPU_BITEXACT_LADDER.json — PASS on the wheel,
#     proving fpu=None is the champion BIT-FOR-BIT plus a POSITIVE control at
#     each of 0.05/0.1/0.15/0.3, plus DOSE-DISTINCT;
#   * the b64-era arbiter certificates (GATE_NEST, the wiring smoke);
#   * ⭐⭐ ROUND 1's OWN BANKED PASS — 800 games of the EXACT arms of this cell
#     that cleared every gate in this family including G-TIEARB-SIDES and
#     G-TIEARB-FIRE on both seats. ⛔ THAT IS AN INSTRUMENT CERTIFICATE, NOT A
#     STATISTICAL ONE: round 1's NUMBER is a context row that is never pooled
#     (CL-068), while the fact that its ARCHIVE passed the gates is evidence
#     about the CODE PATH and is inherited as such.
# ⚠️⚠️ AND ROUND 1's PASS IS INHERITED **PER BOX**: it was banked on the LAPTOP.
# ⛔ The LOCAL box has never run a gate-passing cell of this family, which is
# exactly why --smoke is MANDATORY PER BOX below and why local's smoke is not a
# formality.
# ⚠️ THE LADDER ARTEFACT IS BOX-LOCAL AND GITIGNORED (carc_rs_binary_sha differs
# between boxes compiling identical source).
GG="$HERE/../fpu_ladder_prep/FPU_BITEXACT_LADDER.json"
GG_FATAL=1
[ "$DRY" -eq 0 ] || GG_FATAL=0
GG_DIE() { if [ "$GG_FATAL" -eq 1 ]; then DIE "$@"; else
    STAMP "⚠️⚠️ GOLDEN GATE NOT SATISFIED — continuing ONLY because this is a " \
          "--dry-run (it spends nothing). ⛔ A --smoke or a real chunk is " \
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
print('⭐ ROUND 1 additionally banked a full gate-passing 800-game cell of '
      'these EXACT arms — an INSTRUMENT certificate, inherited per BOX. It was '
      'banked on the LAPTOP; a box that did not run it must pass its OWN '
      '--smoke, which is mandatory here for every box regardless.')
" || GG_DIE "the inherited golden gate does not match this box's wheel — REFUSING."
else
  GG_DIE "measurement/fpu_ladder_prep/FPU_BITEXACT_LADDER.json ABSENT ON THIS " \
      "BOX — ABSENT is FAIL. ⚠️ The artefact is BOX-LOCAL and gitignored, so a " \
      "box that ran the dose ladder HAS one; a box that did not must run " \
      "measurement/fpu_ladder_prep/golden_gate/run_golden_gate.sh first."
fi

# --- the two acts that gate a REAL chunk (dry-run and smoke are exempt) -----
if [ "$DRY" -eq 0 ] && [ "$SMOKE" -eq 0 ]; then
  [ "$BLIND_COMMIT" != "PENDING" ] \
    || DIE "⛔⛔ BLIND_COMMIT is PENDING — REFUSING TO LAUNCH A REAL CHUNK. " \
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
# ⚠️⚠️ THIS IS THIS FAMILY'S PRIMARY PROVENANCE RISK, AND THE FLEXIBLE-BOX
# CLAUSE MAKES IT WORSE, NOT BETTER. BOTH the fpu plumbing and the
# --opp-tiearb-* plumbing are PYTHON-ONLY, so a box running pre-fix source
# serves a dose-FREE candidate and/or an UNARMED opponent with a perfectly
# healthy carc_rs_build, a healthy binary sha and the correct leaf hash.
# ⛔⛔ ADDING A SECOND BOX MID-ROUND ADDS A SECOND CHANCE TO GET THIS WRONG, and
# the second box is the one most likely to be on a stale bundle (it was not part
# of the launch checklist). G-REV requires EVERY box's PINNED_SRC_REV to be the
# SAME 40-hex sha and every emitted short rev to canonicalize to it — never by
# comparing one box's short rev to another's (the IS-A1 defect).
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
  echo "{\"at\":\"$1\",\"utc\":\"$(date -u +%FT%TZ)\",\"role\":\"$ROLE\",\"host\":\"$(hostname)\",\"rev\":\"$pin\",\"clean\":true}" \
    >> "$HERE/SRC_CLEAN_${ROLE}.jsonl"
}
assert_rev "before"

# --------------------------------------------------------------------------- #
# ⭐⭐ THE TWO PLUMBING PROBES, ON THIS BOX, FROM THE SOURCE THAT WILL RUN      #
# --------------------------------------------------------------------------- #
# One import each. Both failure modes produce a healthy-looking archive that no
# per-cell gate on the OTHER axis would catch, so both are probed BEFORE the
# compute rather than after it. ⛔ THEY RUN ON EVERY BOX, EVERY INVOCATION —
# which is the point when a box joins mid-round.
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

# (2) THE OPPONENT SEAT. Until 2026-08-31 eval_fair_puct._make_opponent took NO
#     tiearb parameter and _cfg_from_dict read five keys by name, so the
#     opponent was STRUCTURALLY disarmed. A box on that source arms the
#     CANDIDATE ONLY and produces a CONFOUNDED arb+fpu cell claiming a single
#     variable — with a healthy wheel and leaf hash.
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

# (3) ⭐⭐ NEW IN ROUND 2 — THE RANGE-RESTRICTION ARITHMETIC THIS LAUNCHER
#     DEPENDS ON. eval_fair_puct has no --seed-lo/--seed-hi; the flexible-box
#     clause is implemented as per-chunk --seed-start/--n over _build_work. If
#     that function's contract ever changed, every chunk would quietly play the
#     WRONG SEEDS with every other gate passing at its own address.
w = E._build_work(1000, 6, True)
if w != [(1000,0),(1000,1),(1001,0),(1001,1),(1002,0),(1002,1)]:
    bad.append('_build_work(seed_start, n, paired=True) no longer yields '
               'seed_start..seed_start+n/2-1 at both seats: ' + repr(w))

if bad:
    print('⛔⛔ THIS BOX CANNOT EXPRESS THE CELL: ' + '; '.join(bad))
    print('The source here predates the fpu plumbing (2026-08-29) and/or the '
          'opponent-side tie-arbiter plumbing (2026-08-31), or the paired '
          'paired work-builder has changed shape. A chunk run from this box '
          'would be champion-vs-champion, a CONFOUNDED arb+fpu cell claiming '
          'one variable, or a cell on the wrong seeds. Sync the bundle.')
    sys.exit(1)
print('[probe] this box binds fpu=$FPU_DOSE, can arm the OPPONENT seat, and '
      '_build_work still yields the contiguous paired range this launcher '
      'slices chunks with')
" || DIE "a plumbing probe FAILED on this box — REFUSING."

# --- census by FULL ARGS, never -C python ----------------------------------
# ⚠️ QUANTIFIED 2026-08-26: ONE niced 1-core DRAM-churner inflated a saturated
# W=22 eval ~1.8x/move. No timing statistic is a branch input here, so tenancy
# is RESULT-safe — but the census is still owed, and a silent long job is
# invisible to `ps -C python`. ⛔⛔ IT MATTERS MORE IN ROUND 2: the local box is
# the OWNER'S DESKTOP, and adding it mid-round means launching INTO whatever is
# already there.
STAMP "process census (FULL ARGS):"
ps -eo pid,etime,pcpu,args --sort=-etime | grep -E "python|carc" | grep -v grep \
  | head -20 | sed 's/^/    /'

export CARCASSONNE_FIX_R9="$CARCASSONNE_FIX_R9"   # ⚠️ env-latched at IMPORT
export PYTHONUNBUFFERED=1

# --------------------------------------------------------------------------- #
# 2. ONE CHUNK                                                                 #
# --------------------------------------------------------------------------- #
# `k_dets_override` / `sims_override` / `fpu_flag` exist ONLY so the §9.3 IDENT
# legs can reuse this function at the golden gate's tiny budget with the dose
# dropped. ⛔ A REAL CHUNK PASSES NONE OF THEM and runs the frozen production
# knobs; `run_cell` is called with the empty string for each.
run_cell() {
  local name="$1" seed_start="$2" n_games="$3" fpu="$4" kd="$5" sims="$6"
  local out="$OUT_ROOT/$name"
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
    # ALSO walks 2*n_decks seeds — outside its own frozen band.
    # ⭐⭐ AND IT IS ALSO THE RANGE-RESTRICTION MECHANISM (DESIGN §6.4): with
    # --paired, `--seed-start <chunk lo> --n <2*decks_per_chunk>` is EXACTLY
    # that chunk's contiguous sub-range at both seats and nothing else.
    --n "$n_games" --paired --seed-start "$seed_start"
    # ⚠️ `--out` is AMBIGUOUS in eval_fair_puct (--out-root / --out-subdir) and
    # argparse REFUSES it (PG-D7). The out dir is root/sub, so this pair of
    # flags names EXACTLY the "$OUT_ROOT/$name" above.
    --workers "$W" --out-root "$OUT_ROOT" --out-subdir "$name"
    # ⚠️ WITHOUT THIS THE ROUND RUNS `walled` — rules_profile's argparse default
    # is DEFAULT_PROFILE ("walled", the pre-F9 engine of record), NOT the
    # fixed_v1 the pair freezes (PG-D8).
    --rules-profile "$RULES_PROFILE"
    # ⭐⭐ THE ARBITER, ON **BOTH** SEATS, AT THE FULL DEPLOYED SPEC.
    # ⛔ The --opp-* half is what makes this cell single-variable.
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
# 3. THE SMOKE (DESIGN.md §9.2) + THE IDENT LEGS (§9.3) — ⭐ PER BOX           #
# --------------------------------------------------------------------------- #
# ⛔⛔ EVERY BOX SMOKES BEFORE IT PLAYS A CHUNK, ON ITS OWN THROWAWAY OFFSET.
# Round 1 needed one smoke because one box played. Here a box may join
# mid-round, and it is the box LEAST likely to have been on the launch
# checklist — so its smoke is the only thing that proves it can express the
# cell at all. The offsets are per-box (screen_lib.SMOKE_OFFSETS /
# IDENT_OFFSETS) so one box's smoke can never stand in for the other's.
if [ "$SMOKE" -eq 1 ]; then
  OFFSETS="$("$PY" -c "
import sys; sys.path.insert(0,'$HERE')
import screen_lib as L
print(L.SMOKE_OFFSETS['$ROLE'], L.IDENT_OFFSETS['$ROLE'])
")" || DIE "could not resolve this box's throwaway offsets"
  SMOKE_OFF="$(echo "$OFFSETS" | cut -d' ' -f1)"
  IDENT_OFF="$(echo "$OFFSETS" | cut -d' ' -f2)"

  # --- 3a. the production-knobs smoke ---------------------------------------
  SMOKE_NAME="SMOKE_H2H2_${ROLE}"
  SMOKE_SEED=$((THROWAWAY_BASE + SMOKE_OFF))
  run_cell "$SMOKE_NAME" "$SMOKE_SEED" "$SMOKE_GAMES" "$FPU_DOSE" "" ""
  if [ "$DRY" -eq 0 ]; then
    "$PY" "$HERE/analyze_h2h.py" --root "$OUT_ROOT" --smoke-mode \
      --smoke-cell "${SMOKE_NAME}=fpu_reduction:${FPU_DOSE}:${SMOKE_SEED}:${SMOKE_GAMES}:${ROLE}" \
      --out "$HERE/SMOKE_${ROLE}.json" || DIE "the smoke adjudication FAILED"
    STAMP "smoke adjudicated -> SMOKE_${ROLE}.json (structural keys only)"
  fi

  # --- 3b. ⭐⭐ THE IDENT LEGS ----------------------------------------------
  IDENT_SEED=$((THROWAWAY_BASE + IDENT_OFF))
  run_cell "SMOKE_IDENT_A_${ROLE}"  "$IDENT_SEED" "$IDENT_GAMES" "$FPU_DOSE" \
           "$IDENT_K_DETS" "$IDENT_SIMS"
  run_cell "SMOKE_IDENT_A2_${ROLE}" "$IDENT_SEED" "$IDENT_GAMES" "$FPU_DOSE" \
           "$IDENT_K_DETS" "$IDENT_SIMS"
  run_cell "SMOKE_IDENT_B_${ROLE}"  "$IDENT_SEED" "$IDENT_GAMES" ""           \
           "$IDENT_K_DETS" "$IDENT_SIMS"
  if [ "$DRY" -eq 0 ]; then
    "$PY" "$HERE/analyze_h2h.py" --ident-mode \
      --ident-a  "$OUT_ROOT/SMOKE_IDENT_A_${ROLE}" \
      --ident-a2 "$OUT_ROOT/SMOKE_IDENT_A2_${ROLE}" \
      --ident-b  "$OUT_ROOT/SMOKE_IDENT_B_${ROLE}" \
      --out "$HERE/IDENT_${ROLE}.json" || DIE "the IDENT adjudication FAILED"
    STAMP "IDENT legs adjudicated -> IDENT_${ROLE}.json"
    STAMP "⚠️ REVIEW SMOKE_${ROLE}.json AND IDENT_${ROLE}.json BY HAND before " \
          "this box plays a chunk: the resolved dose must be $FPU_DOSE on the " \
          "CANDIDATE SIDE ONLY, the resolved arbiter must be the DEPLOYED dict " \
          "on BOTH SEATS with nonzero fires on each, and both IDENT " \
          "propositions must read ok."
  fi
  STAMP "SMOKE DONE role=$ROLE"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 4. THE ROUND — THIS BOX'S CHUNKS, IN ORDER                                    #
# --------------------------------------------------------------------------- #
# ⭐⭐ THE CLAIM PROTOCOL — the flexible-box clause's own safety interlock.
# A chunk dir carries CLAIM.json {host, role, utc, rev}. This box refuses a
# chunk claimed by a DIFFERENT host unless --reclaim is passed AND the chunk has
# ZERO records on disk.
# ⛔⛔ WHY THE ZERO-RECORDS CONDITION IS NOT NEGOTIABLE: an out-dir emits exactly
# ONE manifest.json with exactly ONE `host`. If a partially-played chunk changed
# hands, its records would come from two boxes while its manifest named one, and
# G-HOST would publish a map that is FALSE — with every other gate passing.
# ⭐ So: an INTERRUPTED chunk is resumed on the box that started it, and only
# UNTOUCHED chunks move. That is why §6.4's split is computed over the UN-PLAYED
# remainder and lands on chunk boundaries.
echo "$CHUNKS" | while read -r idx name seed_start hi n_games; do
  [ -n "$name" ] || continue
  out="$OUT_ROOT/$name"
  if [ -f "$out/DONE" ]; then
    STAMP "$name already DONE — skipping"
    continue
  fi
  if [ "$DRY" -eq 0 ]; then
    mkdir -p "$out"
    if [ -f "$out/CLAIM.json" ]; then
      owner="$("$PY" -c "
import json,sys
print((json.load(open('$out/CLAIM.json')) or {}).get('host',''))
" 2>/dev/null)"
      if [ -n "$owner" ] && [ "$owner" != "$(hostname)" ]; then
        n_recs="$(ls -1 "$out"/seed*_a*.json 2>/dev/null | wc -l)"
        if [ "$RECLAIM" -eq 1 ] && [ "$n_recs" -eq 0 ]; then
          STAMP "⚠️ RECLAIMING $name from '$owner' — it holds ZERO records, so "\
                "no record of another box's play can end up under this box's "\
                "manifest."
        else
          DIE "⛔⛔ $name IS CLAIMED BY '$owner' AND HOLDS $n_recs RECORD(S). "\
              "An out-dir emits ONE manifest with ONE host: if a partially "\
              "played chunk changed hands, G-HOST would publish a FALSE "\
              "provenance map with every other gate passing. ⭐ RESUME THIS "\
              "CHUNK ON '$owner' (its records are cached, so the resume costs "\
              "only the unplayed games), or hand this box a DIFFERENT chunk. "\
              "--reclaim frees a chunk ONLY when it holds ZERO records."
        fi
      fi
    fi
    "$PY" -c "
import json,socket,datetime
json.dump({'host': socket.gethostname(), 'role': '$ROLE',
           'utc': datetime.datetime.utcnow().isoformat() + 'Z',
           'chunk': $idx, 'seed_lo': $seed_start, 'n_games': $n_games,
           'rev': open('$PIN_FILE').read().strip(),
           'note': '⭐ PROVENANCE + the box-change interlock. Box assignment is '
                   'THROUGHPUT-ONLY (DESIGN 6.4) and moves no bar, gate or '
                   'branch; this file only stops a PARTIALLY PLAYED chunk from '
                   'changing hands, which would make G-HOST publish a false '
                   'map.'},
          open('$out/CLAIM.json','w'), indent=1)
" || DIE "could not write $out/CLAIM.json"
  fi
  run_cell "$name" "$seed_start" "$n_games" "$FPU_DOSE" "" ""
  [ "$DRY" -eq 1 ] || assert_rev "after:$name"
  [ "$DRY" -eq 1 ] || touch "$out/DONE"
done

STAMP "DONE role=$ROLE chunks=${CHUNK_SPEC:-ALL}"
