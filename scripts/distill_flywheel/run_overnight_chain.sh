#!/usr/bin/env bash
# ============================================================================
# OVERNIGHT CHAIN — wait out sighted stage-1, run BOTH head-to-heads, then launch
# the stage-2 flywheel UNCONDITIONALLY.
#
#   step 1  WAIT   for the sighted stage-1 driver to exit (poll run_distill_[s]ighted)
#   step 2  HH1    distilled sighted net  vs  the PRODUCTION fair CHAMPION  (the money shot)
#   step 3  HH2    distilled sighted net  vs  the NON-SIGHTED distilled net (rep A/B)
#   step 4  LAUNCH scripts/distill_flywheel/run_distill_stage2.sh  (detached)
#
# ⚠️ STEP 4 IS UNCONDITIONAL — Joshua's explicit call (2026-07-16). The flywheel launches
#    regardless of what the head-to-heads say, and EVEN IF a head-to-head crashed, and
#    even if stage-1 died without iter_03.pt. Nothing in steps 1-3 may gate it. Every HH
#    step is wrapped so a failure is logged loudly and the chain CONTINUES.
#
# Both HHs run on the SAME fresh CRN band with --paired, so they are deck-matched to each
# other AND seat-balanced (a_seat alternates 0/1 per deck — eval_fair_puct._build_work).
#
# ⚠️ TRANSPORT = per-worker CPU NETS, **NOT** carc-orch. This is deliberate and it
#    overrides the "orch is the default for neural eval" standing rule for THIS run:
#    a k4x688 orch bench (2026-07-16, the HH1 config exactly) CRASHED after ~5 min /
#    ~28k forwards with
#        BrokenServerError: no response from eval_server within 60.0s (request_id=...)
#    The carc-orch watchdog did NOT fire (it only trips on jobs-in/no-batches-out) and the
#    server was still batching — the CLIENT-side 60s wait expired. This is the project's
#    KNOWN open orch stall item (memory `reference_exact_solver_eval_infra`: long
#    endgame solves starve the SHM server -> 60s timeout -> BrokenServerError -> the whole
#    eval dies; the documented workaround is net-on-CPU). It did NOT reproduce at toy knobs
#    (k2x32), which is why the earlier plumbing smokes passed. An UNATTENDED overnight run
#    must not sit on a known crash: the CPU path is tested end-to-end through the real Pool
#    and cannot lose a server. Set ORCH=1 to opt back in once the stall is fixed.
#    (K=2 keeps the solver TT small, so net-on-CPU's RAM-bound failure mode is not in play;
#     CARCASSONNE_TT_CAP is set anyway.)
#
# BOXES: LOCAL ONLY. The flywheel (step 4) does its own 2-box thing exactly as it always
# has. --shared-claim is still passed, so a second box CAN join a running HH by hand
# (same command, same out-dir) without a code change — but nothing depends on it.
#
# Dry run (prints the exact command for every step, touches NOTHING, waits for nothing):
#   bash scripts/distill_flywheel/run_overnight_chain.sh --dry-run
# Real launch (DETACHED — the operator runs this; Mac-sleep/WSL-teardown safe):
#   setsid nice -n 19 bash scripts/distill_flywheel/run_overnight_chain.sh \
#       </dev/null > /mnt/c/carc-shared/distill_flywheel_sighted_20260716/logs/overnight_chain.log 2>&1 &
# ============================================================================
set -uo pipefail          # NOT -e: a failing HH must never abort the chain (step 4).

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

REPO=${REPO:-/home/doctor/projects/carcassone}
SHARE=${SHARE:-/mnt/c/carc-shared}
TAG=${TAG:-distill_flywheel_sighted_20260716}
OUT="$SHARE/$TAG"
LOGS="$OUT/logs"
STATUS="$OUT/OVERNIGHT_CHAIN_STATUS.md"
PY="$REPO/.venv/bin/python"

# --- the checkpoints under test ---
CAND_CKPT=${CAND_CKPT:-$OUT/ckpt/iter_03.pt}                              # sighted 81ch/42
OPP_CKPT=${OPP_CKPT:-$SHARE/distill_flywheel_20260715/ckpt/iter_02.pt}    # non-sighted 78ch/10

# --- HH knobs. n/band are the two things to re-check before launch. ---
# BAND: a FRESH CRN band, deliberately disjoint from every band in use —
#   13.0e9 (eval_fair_puct default), 15.0-15.1e9 (C5/S3 + test_c5_fair_leaf_ab),
#   20.0-20.2e9 (T3/C7 cells), 9.99e9 (older screens), 0.7e9 (distill gen self-play).
# 21.0e9 is clean. Both HHs share it -> the two cells are deck-matched.
BAND=${BAND:-21000000000}
N_HH=${N_HH:-200}            # --paired -> N_HH/2 decks x 2 seats. See the ETA note below.
KDETS=${KDETS:-4}
SIMS=${SIMS:-688}            # k4x688 = 2752 = the deployed fair champion budget (CL-054)
EXACT_K=${EXACT_K:-2}
OW=${OW:-14}                 # CPU workers (local box, 5900XT 16C/32T)
ORCH=${ORCH:-0}              # 0 = per-worker CPU nets (DEFAULT — see the TRANSPORT note
                             # in the header: orch has a KNOWN 60s BrokenServerError stall
                             # at production knobs). 1 = route via carc-orch (opt-in).
TT_CAP=${TT_CAP:-200000}     # CARCASSONNE_TT_CAP for the marginalized endgame solver
POLL=${POLL:-120}            # seconds between stage-1 liveness polls
# SKIP_WAIT=1 -> skip step 1 entirely. For a LATE START (stage-1 already finished and its
# driver is gone) or a restart of a chain whose wait already completed. The candidate-ckpt
# sanity check below still runs, so this cannot skip the HH gate.
SKIP_WAIT=${SKIP_WAIT:-0}
# WAIT_PATTERN is the pgrep pattern for step 1. ⚠️ Keep the bracket ([s]) — an unbracketed
# 'run_distill_sighted' matches this script's OWN pgrep command line and the loop never exits.
WAIT_PATTERN=${WAIT_PATTERN:-run_distill_[s]ighted}

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

mkdir -p "$LOGS" 2>/dev/null

# ---------------------------------------------------------------------------
_now() { date '+%Y-%m-%d %H:%M:%S'; }
_log() { echo "[chain $(_now)] $*"; }

# STATUS.md — one file the operator reads in the morning. Mirrors the stage-1 driver's
# _status idiom (rewrite-in-place, per-step start/end/result).
S_WAIT="pending"; S_HH1="pending"; S_HH2="pending"; S_FLY="pending"
S_NOTE=""
_status() {
  cat > "$STATUS" <<EOF
# Overnight chain — STATUS ($1)

_Last update: $(_now). Chain: wait stage-1 -> HH1 (vs champion) -> HH2 (rep A/B) -> flywheel._

| step | what | state |
|---|---|---|
| 1 | wait for sighted stage-1 to exit | $S_WAIT |
| 2 | HH1 — sighted net vs FAIR CHAMPION | $S_HH1 |
| 3 | HH2 — sighted net vs NON-SIGHTED net | $S_HH2 |
| 4 | launch stage-2 flywheel (UNCONDITIONAL) | $S_FLY |

$2

## Config
- candidate: \`$CAND_CKPT\` (sighted 81ch/42)
- HH2 opponent: \`$OPP_CKPT\` (non-sighted 78ch/10)
- budget: k_dets=$KDETS x sims=$SIMS (=$((KDETS*SIMS)), the deployed fair champion budget), exact-k=$EXACT_K
- n=$N_HH --paired, CRN band=$BAND (fresh; both HHs share it -> deck-matched), workers=$OW, LOCAL box only
- transport: $( [ "$ORCH" = 1 ] && echo "carc-orch SHM (opt-in ORCH=1)" || echo "per-worker CPU nets (orch DISABLED — known 60s BrokenServerError stall at production knobs)" )
- ⚠️ step 4 is UNCONDITIONAL: it launches regardless of HH results or HH crashes (Joshua's call).

## Where to look
- HH1 log: \`$LOGS/hh1_vs_champion.log\`  · results+manifest+summary.json under \`$OUT/hh1_vs_champion/\`
- HH2 log: \`$LOGS/hh2_rep_ab.log\`       · results+manifest+summary.json under \`$OUT/hh2_rep_ab/\`
- flywheel log: \`$LOGS/stage2_launch.log\` (then the stage-2 driver's own STATUS file)
- this chain's log: \`$LOGS/overnight_chain.log\`
$S_NOTE
EOF
}

# Kill any carc-orch + clean OUR shm between steps. The HH scripts trap-clean their own,
# but a hard-killed server can strand a segment; never leak one into the flywheel (step 4
# starts its own per-iter server and a stale one would collide on the GPU).
_clean_orch() {
  pkill carc-orch 2>/dev/null || true
  sleep 2
  rm -f /dev/shm/carc_fairnvnC* /dev/shm/sem.carc_fairnvnC*_* \
        /dev/shm/carc_fairnvnO* /dev/shm/sem.carc_fairnvnO*_* 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# step 1 — WAIT for sighted stage-1
# ---------------------------------------------------------------------------
_wait_stage1() {
  # bracket the pattern ([s]ighted) so this pgrep can never match its OWN command line —
  # an unbracketed 'run_distill_sighted' self-matches and the loop never exits.
  if [ "$DRY" = 1 ]; then
    echo "  while pgrep -f '$WAIT_PATTERN' >/dev/null; do sleep $POLL; done   # SKIP_WAIT=1 bypasses"
    echo "  # then require: [ -s $CAND_CKPT ]"
    return 0
  fi
  if [ "$SKIP_WAIT" = 1 ]; then
    _log "step 1: SKIP_WAIT=1 — not waiting for stage-1 (late start / restart)"
    return 0
  fi
  _log "step 1: waiting for sighted stage-1 (pgrep -f '$WAIT_PATTERN', poll every ${POLL}s)"
  while pgrep -f "$WAIT_PATTERN" >/dev/null 2>&1; do sleep "$POLL"; done
  _log "step 1: sighted stage-1 driver has exited"
}

# ---------------------------------------------------------------------------
# step 2/3 — the head-to-heads. Never allowed to abort the chain.
# ---------------------------------------------------------------------------
_hh() {   # $1=name  $2=subdir  $3=log  $4=OPP_CKPT ("" -> fair-champion)
  local name=$1 sub=$2 log=$3 opp=$4
  local cmd
  if [ "$ORCH" = 1 ]; then
    # opt-in orch route (one server for fair-champion, two for net-vs-net). ⚠️ KNOWN to
    # hit a 60s BrokenServerError at production knobs — see the header TRANSPORT note.
    cmd=(env "CAND_CKPT=$CAND_CKPT" "OPP_CKPT=$opp" "OW=$OW" "CARCASSONNE_TT_CAP=$TT_CAP"
         bash "$REPO/scripts/classical_search/fair_net_vs_net_orch.sh"
         --exact-k "$EXACT_K" --k-dets "$KDETS" --sims "$SIMS"
         --n "$N_HH" --paired --seed-start "$BAND"
         --out-root "$OUT" --out-subdir "$sub" --shared-claim --no-results-csv)
  else
    # DEFAULT: per-worker CPU nets, straight at the harness. No server to lose.
    cmd=(env "CARCASSONNE_TT_CAP=$TT_CAP"
         "$PY" -u "$REPO/scripts/classical_search/eval_fair_puct.py"
         --info fair-netprior --net "$CAND_CKPT")
    if [ -n "$opp" ]; then cmd+=(--opponent net --opp-net "$opp")
    else                   cmd+=(--opponent fair-champion); fi
    cmd+=(--exact-k "$EXACT_K" --k-dets "$KDETS" --sims "$SIMS"
          --n "$N_HH" --paired --seed-start "$BAND" --workers "$OW"
          --out-root "$OUT" --out-subdir "$sub" --shared-claim --no-results-csv)
  fi
  if [ "$DRY" = 1 ]; then
    printf '  %q ' "${cmd[@]}"; printf '\n    > %s 2>&1\n' "$log"
    return 0
  fi
  _log "$name: START -> $log"
  _clean_orch
  nice -n 19 "${cmd[@]}" > "$log" 2>&1
  local rc=$?
  _clean_orch
  if [ $rc -eq 0 ]; then
    _log "$name: DONE rc=0"
  else
    # LOUD, but non-fatal: the chain MUST continue to step 4.
    _log "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    _log "!! $name FAILED rc=$rc — see $log"
    _log "!! CONTINUING ANYWAY (step 4 is unconditional)"
    _log "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    tail -20 "$log" 2>/dev/null | sed 's/^/    | /'
  fi
  return $rc
}

_hh_result() {  # one-line verdict pulled out of the cell's summary.json, for STATUS.md
  local sub=$1
  "$PY" - "$OUT/$sub/summary.json" <<'EOF' 2>/dev/null || echo "no summary.json"
import json, sys
try:
    s = json.load(open(sys.argv[1]))
except Exception as e:
    print(f"unreadable summary.json ({e})"); raise SystemExit
print(f"n={s['n']} W/D/L={s['W']}/{s['D']}/{s['L']} wr={s['winrate']:.3f} "
      f"elo={s['elo']:+.1f}+/-{s.get('elo_sig_1sigma', float('nan')):.1f} "
      f"paired_margin={s.get('paired_mean_margin')} z={s.get('paired_z')}")
EOF
}

# ---------------------------------------------------------------------------
# step 4 — the flywheel. UNCONDITIONAL.
# ---------------------------------------------------------------------------
_launch_flywheel() {
  local log="$LOGS/stage2_launch.log"
  if [ "$DRY" = 1 ]; then
    echo "  setsid nice -n 19 bash $REPO/scripts/distill_flywheel/run_distill_stage2.sh \\"
    echo "      </dev/null > $log 2>&1 &"
    echo "  # UNCONDITIONAL — runs even if stage-1 crashed or both HHs failed."
    return 0
  fi
  _clean_orch     # never hand the flywheel a stale server/segment
  _log "step 4: launching stage-2 flywheel (UNCONDITIONAL) -> $log"
  setsid nice -n 19 bash "$REPO/scripts/distill_flywheel/run_distill_stage2.sh" \
      </dev/null > "$log" 2>&1 &
  local pid=$!
  sleep 5
  if kill -0 "$pid" 2>/dev/null; then
    _log "step 4: flywheel LAUNCHED pid=$pid (detached; it owns the box from here)"
    S_FLY="**LAUNCHED** $(_now) (pid=$pid, detached)"
  else
    # It may have exited fast (a real failure) — say so; do not pretend it is running.
    _log "step 4: WARNING — flywheel pid=$pid not alive 5s after launch; check $log"
    S_FLY="**LAUNCH SUSPECT** — pid=$pid died within 5s. See \`logs/stage2_launch.log\`."
    tail -20 "$log" 2>/dev/null | sed 's/^/    | /'
  fi
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if [ "$DRY" = 1 ]; then
  echo "=============================================================="
  echo "OVERNIGHT CHAIN — DRY RUN (nothing is launched, nothing waits)"
  echo "=============================================================="
  echo "candidate : $CAND_CKPT"
  echo "HH2 opp   : $OPP_CKPT"
  echo "budget    : k_dets=$KDETS x sims=$SIMS (=$((KDETS*SIMS))) exact-k=$EXACT_K"
  echo "n=$N_HH --paired  band=$BAND  workers=$OW  box=LOCAL only"
  echo "status    : $STATUS"
  echo
  echo "--- step 1: WAIT for sighted stage-1 -------------------------"
  _wait_stage1
  echo
  echo "--- step 2: HH1 — sighted net vs FAIR CHAMPION ---------------"
  _hh HH1 hh1_vs_champion "$LOGS/hh1_vs_champion.log" ""
  echo
  echo "--- step 3: HH2 — sighted net vs NON-SIGHTED net (cross-rep) -"
  _hh HH2 hh2_rep_ab "$LOGS/hh2_rep_ab.log" "$OPP_CKPT"
  echo
  echo "--- step 4: LAUNCH stage-2 flywheel (UNCONDITIONAL) ----------"
  _launch_flywheel
  echo
  echo "--- between every step: _clean_orch --------------------------"
  echo "  pkill carc-orch; rm -f /dev/shm/carc_fairnvn{C,O}* /dev/shm/sem.carc_fairnvn{C,O}*_*"
  echo "=============================================================="
  exit 0
fi

_log "overnight chain START (pid=$$)"
_status "RUNNING" "Chain started $(_now). Waiting for sighted stage-1 to finish."
trap '_log "[signal] TERM/INT — chain interrupted"; S_NOTE="

⚠️ The chain caught a termination signal and stopped early."; _status "INTERRUPTED" "Caught a termination signal."; _clean_orch; exit 130' INT TERM

# ---- step 1
S_WAIT="waiting…"; _status "RUNNING" "Step 1: waiting for sighted stage-1."
_wait_stage1
S_WAIT="done $(_now)"

# ---- gate the HHs (NOT step 4) on the candidate ckpt existing
RUN_HH=1
if [ ! -s "$CAND_CKPT" ]; then
  _log "########################################################################"
  _log "## stage-1 EXITED WITHOUT $CAND_CKPT"
  _log "## -> stage-1 most likely CRASHED or was halted (collapse screen)."
  _log "## -> SKIPPING both head-to-heads (nothing to evaluate)."
  _log "## -> STILL LAUNCHING THE FLYWHEEL (step 4 is unconditional, Joshua's call)."
  _log "########################################################################"
  RUN_HH=0
  S_HH1="**SKIPPED** — candidate ckpt missing"
  S_HH2="**SKIPPED** — candidate ckpt missing"
  S_NOTE="

## ⚠️ stage-1 finished WITHOUT \`$(basename "$CAND_CKPT")\`
The sighted driver exited but the expected candidate checkpoint is missing/empty — it
probably crashed or tripped the collapse screen. Both head-to-heads were SKIPPED (there is
nothing to evaluate). **The flywheel was still launched** (step 4 is unconditional). Check
\`$OUT/STAGE1_STATUS.md\` and \`$LOGS/\` for the stage-1 failure."
  _status "RUNNING" "Step 1 done — but candidate ckpt MISSING. HHs skipped; going straight to step 4."
else
  _log "step 1: sanity OK — $CAND_CKPT present ($(stat -c%s "$CAND_CKPT") bytes)"
fi

# ---- step 2 / 3
if [ "$RUN_HH" = 1 ]; then
  S_HH1="running since $(_now)"; _status "RUNNING" "Step 2: HH1 (sighted net vs fair champion), n=$N_HH."
  if _hh HH1 hh1_vs_champion "$LOGS/hh1_vs_champion.log" ""; then
    S_HH1="**done** $(_now) — \`$(_hh_result hh1_vs_champion)\`"
  else
    S_HH1="**FAILED** $(_now) — see \`logs/hh1_vs_champion.log\` (chain continued)"
  fi
  _status "RUNNING" "Step 2 finished. Starting step 3 (HH2)."

  S_HH2="running since $(_now)"; _status "RUNNING" "Step 3: HH2 (rep A/B, cross-rep), n=$N_HH."
  if _hh HH2 hh2_rep_ab "$LOGS/hh2_rep_ab.log" "$OPP_CKPT"; then
    S_HH2="**done** $(_now) — \`$(_hh_result hh2_rep_ab)\`"
  else
    S_HH2="**FAILED** $(_now) — see \`logs/hh2_rep_ab.log\` (chain continued)"
  fi
fi

# ---- step 4 — ALWAYS
_status "RUNNING" "Steps 1-3 finished. Launching the stage-2 flywheel (unconditional)."
_launch_flywheel
_status "CHAIN COMPLETE" "All four steps attempted. The flywheel now owns the box; follow its own STATUS file."
_log "overnight chain COMPLETE"
