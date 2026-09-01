#!/usr/bin/env bash
# =========================================================================== #
# launch_budget44k.sh — THE 44032 BUDGET-RUNG ROUND LAUNCHER (LOCAL, W=30)     #
#                                                                             #
# Owner funding, verbatim (2026-09-01): "fund 44k at w30."                    #
#   -> LOCAL box, W = 30. This is an EXPLICIT OWNER OVERRIDE of the standing   #
#      "W = logical threads" default (local 32). W is THROUGHPUT-ONLY: no      #
#      gate, bar or branch reads it.                                          #
#                                                                             #
# ⛔⛔ THE ROUND IS UNLAUNCHED. This script REFUSES a real chunk until:         #
#       * screen_lib.sanity_check() is non-empty              -> REFUSE       #
#       * adjudicate_budget44k.py --selftest FAILS             -> REFUSE       #
#       * BLIND_COMMIT.json still reads "PENDING"              -> REFUSE       #
#       * the sibling BAND_CLAIMED file does not exist         -> REFUSE       #
#       * PINNED_SRC_REV is absent or does not name HEAD       -> REFUSE       #
#       * a code path is dirty (src/ , engine/ , scripts/      -> REFUSE       #
#         classical_search , this dir)                                        #
#     --dry-run, --smoke and --smoke-prod are EXEMPT from BLIND_COMMIT and     #
#     BAND_CLAIMED: they spend no blindness and no band (they play only the    #
#     THROWAWAY range). --dry-run additionally spends no compute at all.       #
#                                                                             #
# ⚠️⚠️ THE PINNED-ROUND COMMIT FREEZE (auto-memory reference_freeze_latch_hook, #
#     "BLIND SPOT" clause). This round is REV-PINNED and CHUNKED, so the pin   #
#     check below runs BEFORE EVERY CHUNK. While the round is live:            #
#        ⛔ NO main-tree git commits AT ALL — not even docs.                   #
#     A commit moves HEAD, the next chunk's pin check fails, and the launcher  #
#     dies mid-round. Re-pinning is NOT the fix (it makes a cross-chunk rev    #
#     split, which G-SHARD-IDENT then voids). Stage work and commit at round   #
#     end.                                                                    #
#                                                                             #
# ⚠️ LAUNCH DETACHED for real chunks. Joshua's Mac->Windows->WSL setup means   #
#    Mac-sleep SIGHUP AND WSL VM-teardown both kill tty-attached jobs:        #
#      setsid nohup nice -n 19 ./launch_budget44k.sh \                        #
#        >> budget44k_launch.log 2>&1 & disown                                #
#                                                                             #
# USAGE                                                                       #
#   ./launch_budget44k.sh --dry-run        # print every command, run nothing #
#   ./launch_budget44k.sh --smoke          # TINY ratio-preserving budgets,   #
#                                          # throwaway seeds, 4 games/cell,   #
#                                          # self-adjudicated; ALSO the way   #
#                                          # selftest_fixture/ is regenerated #
#   ./launch_budget44k.sh --smoke-prod     # PRODUCTION knobs, 2 games/cell,  #
#                                          # throwaway seeds — the pre-flight #
#                                          # smoke + the real timing datum    #
#   ./launch_budget44k.sh                  # THE REAL ROUND, chunk by chunk,  #
#                                          # resuming past any chunk marked   #
#                                          # DONE                             #
#   ./launch_budget44k.sh --cell CELL_K32  # one cell only                    #
# =========================================================================== #
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

# ⚠️ Frozen constants live in screen_lib.py — this script re-derives NOTHING
# numeric; it reads them back via python probes so the launcher and the
# adjudicator can never drift apart.
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python found" >&2; exit 2; }

DRY=0; SMOKE=0; SMOKE_PROD=0; ONLY_CELL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --smoke-prod) SMOKE_PROD=1; shift ;;
    --cell) ONLY_CELL="${2:-}"; shift 2 ;;
    --) shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

STAMP() { echo "[budget44k $(date -u +%FT%TZ) $(hostname)] $*"; }
DIE() { STAMP "!!! $*"; exit 13; }

PROBE() { "$PY" -c "
import sys; sys.path.insert(0, '$HERE')
import screen_lib as L
$1"; }

# --------------------------------------------------------------------------- #
# 0. PRECONDITIONS — screen_lib is law                                        #
# --------------------------------------------------------------------------- #
"$PY" -c "
import sys; sys.path.insert(0, '$HERE')
import screen_lib as L
bad = L.sanity_check()
if bad:
    print('⛔⛔ screen_lib.sanity_check() FAILED:')
    for b in bad: print(' -', b)
    sys.exit(1)
print('[probe] screen_lib sanity OK — BAR_M', L.BAR_M,
      '| SE_primary %.4f SE_screen %.4f' % (L.SE_PRIMARY, L.SE_SCREEN),
      '| MDE80_primary %.3f' % L.mde(L.SE_PRIMARY),
      '| PROPOSED_BAND', L.PROPOSED_BAND,
      '| ETA model %.1fh + %.1fh' % (L.eta_hours(1600), L.eta_hours(800)))
" || DIE "screen_lib.sanity_check() is not clean — fix the library before launching"

"$PY" "$HERE/adjudicate_budget44k.py" --selftest \
  || DIE "adjudicate_budget44k.py --selftest FAILED — a broken adjudicator " \
         "voids every branch it would ever adjudicate"

# --------------------------------------------------------------------------- #
# 0.1 W — owner override, throughput-only                                     #
# --------------------------------------------------------------------------- #
W_FROZEN="$(PROBE "print(L.W_LOCAL)")"
W="${W:-$W_FROZEN}"
if [ "$W" -ne "$W_FROZEN" ]; then
  STAMP "⚠️ W=$W (not the owner-frozen $W_FROZEN) — throughput-only, proceeding,"
  STAMP "   but this run is not tenancy-comparable to a W=$W_FROZEN chunk"
fi

STAMP "process census (FULL ARGS — never -C python/comm, a silent long job is"
STAMP "invisible otherwise; feedback_no_agent_compute_beside_eval):"
ps -eo pid,etime,pcpu,args --sort=-etime 2>/dev/null | grep -E "python|carc" \
  | grep -v grep | head -25 | sed 's/^/    /'
STAMP "loadavg: $(cat /proc/loadavg)"

export CARCASSONNE_FIX_R9=1        # ⚠️ env-latched at IMPORT
export PYTHONUNBUFFERED=1

BLIND_COMMIT="$("$PY" -c "
import json
print(json.load(open('$HERE/BLIND_COMMIT.json'))['blind_commit'])
")"

SHARE="${SHARE:-/mnt/c/carc-shared}"    # LOCAL path (the laptop's is /mnt/carc-shared)

# --------------------------------------------------------------------------- #
# freeze-latch sentinel (auto-memory: reference_freeze_latch_hook)             #
# --------------------------------------------------------------------------- #
# Present for the lifetime of any real compute this script does; removed on
# clean exit via the trap. NOT dropped for --dry-run, which spends no compute.
# A STALE sentinel (crashed run) must only be cleaned after confirming the run
# is actually dead — never blind-deleted.
if [ "$DRY" -eq 0 ]; then
  if   [ "$SMOKE" -eq 1 ];      then TAG=SMOKE
  elif [ "$SMOKE_PROD" -eq 1 ]; then TAG=SMOKE_PROD
  else                               TAG=ROUND; fi
  LIVE="$HERE/RUN_LIVE_${TAG}.json"
  "$PY" -c "
import json, socket
from datetime import datetime, timezone
json.dump({'tag': '$TAG', 'host': socket.gethostname(), 'W': $W,
           'started_at': datetime.now(timezone.utc).isoformat(),
           'repo': '$REPO',
           'what': 'budget44k_prep — does the post-wheel budget doubling '
                   '22016 -> 44032 pay, and at which allocation? Two cells '
                   '(k32x1376 powered primary, k16x2752 screen) vs the '
                   'deployed k16x1376 champion, both seats tie-arb ARMED.'},
          open('$LIVE', 'w'), indent=2)
"
  trap 'rm -f "$LIVE"' EXIT
fi

# --------------------------------------------------------------------------- #
# 1. run_chunk() — ONE chunk of ONE cell                                      #
# --------------------------------------------------------------------------- #
# ⛔⛔ THE SINGLE VARIABLE IS THE CANDIDATE'S BUDGET, AND NOTHING ELSE.
#  * --k-dets/--sims           = CANDIDATE side (44032 at this cell's shape)
#  * --opp-k-dets/--opp-sims   = OPPONENT side (the deployed k16x1376 = 22016)
#    Both flag families VERIFIED present in eval_fair_puct.py's argparse at
#    build time. ⛔ OMITTING the --opp-* pair does NOT error — the opponent
#    silently inherits the shared --k-dets/--sims and the cell becomes a
#    44032-vs-44032 null that looks perfectly healthy. That is exactly what
#    G-BUDGET / G-BUDGET-RATIO exist to catch, from the EMITTED MANIFEST.
#  * BOTH seats carry the deployed tie-arbiter (B=64/J=4/argmax/
#    tiearb2-deploy-v1/eps 0.0/phase_gate all), spelled out verbatim on each
#    side. Constants/incantation mirrored from
#    measurement/fpu_h2h_r2_prep/{WORKERS.conf,run_cells.sh}.
run_chunk() {
  local cell="$1" name="$2" seed_start="$3" n_games="$4"
  local ck="$5" cs="$6" ok_="$7" os_="$8" out_root="$9" workers="${10}"
  local out="$out_root/$name"

  if [ "$DRY" -eq 0 ] && [ -f "$out/DONE" ]; then
    STAMP "$name already DONE — skipping (resume)"
    return 0
  fi
  [ "$DRY" -eq 1 ] || mkdir -p "$out"

  local args=(
    "$REPO/scripts/classical_search/eval_fair_puct.py"
    --backend rust --info fair
    # ⭐⭐ THE ASYMMETRY: candidate 44032, opponent the deployed 22016.
    --k-dets "$ck" --sims "$cs"
    --opp-k-dets "$ok_" --opp-sims "$os_"
    --exact-k 2
    --opponent fair-champion
    # ⛔⛔ WITHOUT --paired the round has no primary: _build_work returns n
    # DISTINCT decks at ONE seat each, n_paired = 0.
    --n "$n_games" --paired --seed-start "$seed_start"
    --workers "$workers" --out-root "$out_root" --out-subdir "$name"
    --rules-profile fixed_v1
    # ⭐ BOTH SEATS ARMED — the budget is the only variable.
    --cand-tiearb-enabled --cand-tiearb-b 64 --cand-tiearb-j 4
    --cand-tiearb-mode argmax --cand-tiearb-salt tiearb2-deploy-v1
    --cand-tiearb-eps 0.0 --cand-tiearb-phase-gate all
    --opp-tiearb-enabled --opp-tiearb-b 64 --opp-tiearb-j 4
    --opp-tiearb-mode argmax --opp-tiearb-salt tiearb2-deploy-v1
    --opp-tiearb-eps 0.0 --opp-tiearb-phase-gate all
  )
  if [ "$BLIND_COMMIT" != "PENDING" ]; then
    args+=(--stamp-key "BLIND_COMMIT=$BLIND_COMMIT")
  fi
  case "$name" in
    SMOKE_*) args+=(--allow-selfplay-seeds) ;;   # the throwaway range sits
                                                  # outside every registered
                                                  # clean-eval band, on purpose
  esac

  if [ "$DRY" -eq 1 ]; then
    STAMP "[dry-run] $name  cand k${ck}x${cs}=$((ck*cs))  opp k${ok_}x${os_}=$((ok_*os_))  seeds=${seed_start}..  n=$n_games  W=$workers -> $out"
    printf '    %q ' "$PY" "${args[@]}"; echo
    return 0
  fi

  STAMP "$name  cand k${ck}x${cs}=$((ck*cs))  opp k${ok_}x${os_}=$((ok_*os_))  seeds=${seed_start}..  n=$n_games  W=$workers -> $out"
  local t0 t1
  t0="$(date +%s)"
  nice -n 19 "$PY" "${args[@]}" || DIE "$name FAILED"
  t1="$(date +%s)"
  touch "$out/DONE"
  # ⭐ ETA RE-DERIVATION FROM THE ROUND'S OWN THROUGHPUT
  # (feedback_eta_before_launch: never trust a model where a measurement
  # exists; and never derive a rate from the FIRST completions of a parallel
  # run — this uses the whole chunk's wall-clock, i.e. the mean).
  "$PY" -c "
import sys; sys.path.insert(0,'$HERE')
import screen_lib as L
secs = max(1, $t1 - $t0); gph = $n_games / (secs/3600.0)
print('[eta] %s finished in %.2f h -> %.1f g/h realized (model %.1f g/h).' %
      ('$name', secs/3600.0, gph, L.g_per_h_44k()))
rem_p = L.CELLS[L.PRIMARY_CELL]['n_games']; rem_s = L.CELLS[L.SCREEN_CELL]['n_games']
print('[eta] AT THE REALIZED RATE the full round (%d games) is %.1f h '
      '(model said %.1f h).' % (rem_p+rem_s, (rem_p+rem_s)/gph,
                                L.eta_hours(rem_p+rem_s)))
"
}

# --------------------------------------------------------------------------- #
# 2. --smoke / --smoke-prod : throwaway seeds, self-adjudicated               #
# --------------------------------------------------------------------------- #
if [ "$SMOKE" -eq 1 ] || [ "$SMOKE_PROD" -eq 1 ]; then
  THROWAWAY_BASE="$(PROBE "print(L.THROWAWAY_BASE)")"
  if [ "$SMOKE_PROD" -eq 1 ]; then
    OUT_ROOT="$SHARE/budget44k_smoke_prod"
    # 4 games = 2 seat-balanced decks: the smallest n for which the deck-paired
    # statistic is computable at all. ⛔ --n 2 would give ONE deck and
    # paired_margin would return None, making the smoke blind to the very
    # statistic the round is built on.
    SMOKE_GAMES=4
    SMOKE_W=4
    SUFFIX="prod"
  else
    OUT_ROOT="$SHARE/budget44k_smoke"
    SMOKE_GAMES=4
    SMOKE_W=4
    SUFFIX="tiny"
  fi

  rc=0
  i=0
  for cell in $(PROBE "print(' '.join(L.CELLS))"); do
    [ -n "$ONLY_CELL" ] && [ "$cell" != "$ONLY_CELL" ] && continue
    i=$((i+1))
    if [ "$SMOKE_PROD" -eq 1 ]; then
      # PRODUCTION KNOBS — the CLAUDE.md pre-flight norm: same budget, same
      # arbiter, same rules, same backend; only the game COUNT differs.
      read -r CK CS OK_ OS_ <<<"$(PROBE "
s = L.CELLS['$cell']
print(s['k_dets'], s['sims_per_det'], L.OPP_K_DETS, L.OPP_SIMS_PER_DET)")"
    else
      # TINY, RATIO-PRESERVING budgets — small enough to run in seconds while
      # still expressing this cell's ALLOCATION SHAPE, so G-BUDGET-RATIO (the
      # magnitude-free flag-wiring gate) is genuinely exercised. G-BUDGET
      # (the frozen magnitudes) is EXPECTED to fail here, and the selftest
      # asserts that it does.
      read -r CK CS OK_ OS_ <<<"$(PROBE "
s = L.CELLS['$cell']
ok_, os_ = 2, 32
ck = ok_ * (s['k_dets'] // L.OPP_K_DETS)
cs = os_ * (s['sims_per_det'] // L.OPP_SIMS_PER_DET)
print(ck, cs, ok_, os_)")"
    fi
    NAME="SMOKE_${SUFFIX}_${cell}__c1"
    SEED=$((THROWAWAY_BASE + i * 100))
    run_chunk "$cell" "$NAME" "$SEED" "$SMOKE_GAMES" \
              "$CK" "$CS" "$OK_" "$OS_" "$OUT_ROOT" "$SMOKE_W"
    if [ "$DRY" -eq 0 ]; then
      "$PY" "$HERE/adjudicate_budget44k.py" --smoke-mode --cell "$cell" \
        --root "$OUT_ROOT/$NAME" --out "$HERE/SMOKE_${SUFFIX}_${cell}.json" \
        || { STAMP "⛔ the $cell smoke adjudication FAILED — the emitted " \
                   "manifest does not carry the budget/arbiter shape this " \
                   "launcher requested"; rc=1; }
      # ⭐ --smoke-prod runs the REAL magnitudes, so it is the ONE smoke that
      # can also satisfy G-BUDGET (the frozen 44032/22016 pin). Assert it here
      # rather than leaving it to a human eyeballing the JSON — this is the
      # pre-flight that proves the production incantation is right BEFORE
      # ~21 h of box time is spent on it.
      if [ "$SMOKE_PROD" -eq 1 ]; then
        "$PY" -c "
import json, sys
sys.path.insert(0, '$HERE')
import screen_lib as L
d = '$OUT_ROOT/$NAME'
man = json.load(open(d + '/manifest.json'))
summ = json.load(open(d + '/summary.json'))
g = L.budget_gate(man, summ, '$cell')
print('[smoke-prod] G-BUDGET:', 'PASS' if g['ok'] else 'FAIL', '—', g['why'])
sys.exit(0 if g['ok'] else 1)
" || { STAMP "⛔⛔ $cell --smoke-prod FAILED G-BUDGET at the REAL magnitudes " \
             "— do NOT launch the round"; rc=1; }
      fi
    fi
  done
  if [ "$DRY" -eq 0 ] && [ "$SMOKE" -eq 1 ]; then
    STAMP "to refresh selftest_fixture/ from this smoke:"
    for cell in $(PROBE "print(' '.join(L.CELLS))"); do
      STAMP "  cp $OUT_ROOT/SMOKE_${SUFFIX}_${cell}__c1/{manifest.json,summary.json,seed*_a*.json} $HERE/selftest_fixture/$cell/"
    done
  fi
  STAMP "SMOKE DONE (rc=$rc)"
  exit "$rc"
fi

# --------------------------------------------------------------------------- #
# 3. THE REAL ROUND — refused until claimed + stamped + pinned + clean         #
# --------------------------------------------------------------------------- #
check_launch_preconditions() {
  [ -f "$HERE/BAND_CLAIMED" ] \
    || DIE "BAND_CLAIMED does not exist — see BAND_CLAIMED.placeholder. " \
           "This agent PROPOSED a band; it did NOT claim one."
  [ "$BLIND_COMMIT" != "PENDING" ] \
    || DIE "BLIND_COMMIT.json still reads PENDING — stamp the freeze commit's " \
           "40-hex sha first (a commit cannot name its own hash, so this is a " \
           "mandatory SECOND commit, not an oversight)."
  [ -f "$HERE/PINNED_SRC_REV" ] \
    || DIE "PINNED_SRC_REV is absent — stamp it " \
           "(git -C \"$REPO\" rev-parse HEAD) before a real chunk plays."
  PINNED="$(cat "$HERE/PINNED_SRC_REV")"
  HEAD_NOW="$(git -C "$REPO" rev-parse HEAD)"
  [ "$PINNED" = "$HEAD_NOW" ] \
    || DIE "PINNED_SRC_REV ($PINNED) != HEAD ($HEAD_NOW) — a commit landed " \
           "while a rev-pinned round is live. Re-pinning is NOT the fix (it " \
           "makes a cross-chunk rev split, which G-SHARD-IDENT then voids); " \
           "reset HEAD back to the pin, or resolve by hand."
  DIRTY="$(git -C "$REPO" status --porcelain -- src engine \
           scripts/classical_search "$HERE" 2>/dev/null)"
  [ -z "$DIRTY" ] \
    || DIE "the code path is DIRTY: $DIRTY — commit or stash before a real " \
           "chunk plays (blindness protection)."
}

if [ "$DRY" -eq 0 ]; then
  check_launch_preconditions
fi

if [ -f "$HERE/BAND_CLAIMED" ]; then
  CLAIMED_BAND="$("$PY" -c "
import re
m = re.search(r'BAND CLAIMED:\s*(\d+)', open('$HERE/BAND_CLAIMED').read())
print(m.group(1) if m else '')
" 2>/dev/null)"
  [ -n "$CLAIMED_BAND" ] || DIE "BAND_CLAIMED exists but no band id could be parsed out of it"
elif [ "$DRY" -eq 1 ]; then
  CLAIMED_BAND="$(PROBE "print(L.PROPOSED_BAND)")"
  STAMP "[dry-run] BAND_CLAIMED does not exist yet — using the PROPOSED band " \
        "$CLAIMED_BAND for this preview only; the real launch refuses until " \
        "it is actually claimed"
else
  DIE "BAND_CLAIMED does not exist — see BAND_CLAIMED.placeholder"
fi

OUT_ROOT="$SHARE/budget44k_20260901"
[ "$DRY" -eq 1 ] || mkdir -p "$OUT_ROOT"

# ⭐ CELL ORDER: the POWERED PRIMARY plays FIRST. If box time is cut short, the
# cell that licenses the decision is the one that completed.
for cell in $(PROBE "print(L.PRIMARY_CELL, L.SCREEN_CELL)"); do
  [ -n "$ONLY_CELL" ] && [ "$cell" != "$ONLY_CELL" ] && continue
  read -r CK CS NCHUNK DPC <<<"$(PROBE "
s = L.CELLS['$cell']
print(s['k_dets'], s['sims_per_det'], s['chunks'], s['decks_per_chunk'])")"
  STAMP "=== $cell : candidate k${CK}x${CS}=$((CK*CS)) vs opponent k16x1376=22016, ${NCHUNK} chunk(s) x ${DPC} decks ==="
  for c in $(seq 1 "$NCHUNK"); do
    # Re-check the pin/dirty guard BEFORE EVERY CHUNK: a chunked round is
    # exposed to a mid-round commit in a way a single-shot round is not.
    [ "$DRY" -eq 1 ] || check_launch_preconditions
    SEED=$((CLAIMED_BAND + (c - 1) * DPC))
    run_chunk "$cell" "${cell}__c${c}" "$SEED" $((2 * DPC)) \
              "$CK" "$CS" 16 1376 "$OUT_ROOT" "$W"
  done
done

if [ "$DRY" -eq 0 ]; then
  STAMP "ROUND COMPLETE -> $OUT_ROOT. Adjudicate with:"
  STAMP "  $PY $HERE/adjudicate_budget44k.py --out-root $OUT_ROOT \\"
  STAMP "      --pinned-src-rev $(cat "$HERE/PINNED_SRC_REV") \\"
  STAMP "      --out $HERE/VERDICT.json"
fi
