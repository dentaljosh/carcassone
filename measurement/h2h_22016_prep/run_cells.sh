#!/usr/bin/env bash
# =============================================================================
# run_cells.sh -- 22016-vs-11008 DIRECT BUDGET HEAD-TO-HEAD LAUNCHER.
#
# ONE cell: candidate F = k16x1376 (22016 sims) vs opponent E = the production
# champion k8x1376 (11008 sims), fair PIMC, rust BOTH sides, fixed_v1 + R9,
# curve125 leaf pinned to a36d2e15a3b3d71d, exact-K<=2 marginalized, tie-arbiter
# OFF on both sides, n=1400 games = 700 decks x 2 seatings, deck-paired, on the
# freshly claimed band 148000000000.
#
#   run_cells.sh [--dry-run] [--smoke]
#
# eval_fair_puct.py has NO --limit flag, so this runs the cell in bounded PASSES:
# each pass is one `timeout`d invocation over the FULL range under --shared-claim
# (the harness skips already-recorded cells, so each pass advances the archive),
# and the FINAL pass walks the whole range and therefore writes the pooled
# summary.json the adjudicator reads. Between passes the launcher re-asserts the
# rev pin, sweeps stale claims, checks RAM, and checks the void rate.
#
# ⛔ THIS FILE IS TRACKED AT MODE 644, DELIBERATELY NOT EXECUTABLE. `chmod +x` is
# the ORCHESTRATOR's own launch act, performed only after WORKERS.conf's
# BLIND_COMMIT and the sibling PINNED_SRC_REV are real shas and BAND_CLAIMED
# exists -- never by this build. NOT LAUNCHED as of this commit.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached jobs:
#   setsid nohup ./run_cells.sh </dev/null >/dev/null 2>&1 & disown
#
# ⚠️ EXCLUSIVE TENANT. Nothing else may run on the box (DESIGN.md SS6/SS7.4).
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=WORKERS.conf
. "$DIR/WORKERS.conf"

REPO="$REPO_LOCAL"
PY="${CARC_PY:-$REPO/.venv/bin/python}"
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
CAND_LEAF_JSON="$DIR/champion_leaf_curve125.json"
LOGS="$DIR/logs"
OUT="$REPO/$OUT_SUBDIR"
CELL_OUT="$OUT/$OUT_CELL"
CODE_PATHS=(src engine scripts rust tests pyproject.toml setup.py)

DRY=0
SMOKE=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --smoke)   SMOKE=1 ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[h2h22k $(ts) $(hostname)] $*"; }

[ -x "$PY" ] || { echo "FATAL: no python at '$PY' (set CARC_PY to override)" >&2; exit 2; }

# --------------------------------------------------------------------------- #
# ARGV. The SINGLE experimental axis is --k-dets (16 vs 8); --sims is 1376 on   #
# BOTH sides. ⛔ NO --cand-tiearb-* FLAG ANYWHERE (DESIGN.md SS2.2); the harness #
# default is disarmed and the opponent side has no arming flag at all.          #
# --------------------------------------------------------------------------- #
build_argv() {   # $1=n_games  $2=seed_start  $3=workers  $4=out_subdir
  local n="$1" seed="$2" w="$3" sub="$4"
  ARGV=(nice -n "$NICE" "$PY" -u "$HARNESS"
        --info "$INFO_MODE" --opponent "$OPPONENT_MODE" --backend "$BACKEND"
        --exact-k "$EXACT_K"
        --c-puct "$C_PUCT" --tau-p "$TAU_P"
        --leaf-quantize "$LEAF_QUANTIZE" --final-select "$FINAL_SELECT"
        --cand-leaf-json "$CAND_LEAF_JSON"
        --k-dets "$F_K_DETS"     --sims     "$F_SIMS_PER_DET"
        --opp-k-dets "$E_K_DETS" --opp-sims "$E_SIMS_PER_DET"
        --n "$n" --paired --seed-start "$seed"
        --rules-profile "$RULES_PROFILE" --workers "$w"
        --out-root "$OUT" --out-subdir "$sub"
        --shared-claim --claim-stale-secs "$CLAIM_STALE_SECS"
        --claim-host "h2h22k-$(hostname)"
        --no-results-csv)
}

# --------------------------------------------------------------------------- #
# SRC / REV pinning (d1-rebase G-REV machinery, ported).                        #
# --------------------------------------------------------------------------- #
src_is_clean() {
  local dirty
  dirty="$(git -C "$REPO" status --porcelain -- "${CODE_PATHS[@]}" || echo FAIL)"
  if [ -n "$dirty" ]; then
    log "!!! SOURCE TREE DIRTY (${CODE_PATHS[*]}):"
    echo "$dirty" | sed 's/^/[h2h22k]   /'
    return 1
  fi
  return 0
}

record_src_boundary() {   # $1 = label
  local rev; rev="$(git -C "$REPO" rev-parse HEAD)"
  "$PY" - "$DIR/$SRC_CLEAN_LOG" "$1" "$rev" <<'SEOF' || true
import json, sys, time
p, label, rev = sys.argv[1], sys.argv[2], sys.argv[3]
with open(p, "a") as f:
    f.write(json.dumps({"boundary": label, "head": rev,
                        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "src_clean": True}) + "\n")
SEOF
}

assert_rev_pinned() {   # $1 = boundary label
  local pinned rev
  pinned="$(tr -d '[:space:]' < "$DIR/$PINNED_SRC_REV_FILE")"
  rev="$(git -C "$REPO" rev-parse HEAD)"
  if [ "$pinned" != "$rev" ]; then
    log "!!! FATAL at boundary '$1': HEAD=$rev != PINNED_SRC_REV=$pinned"
    log "!!! The tree MOVED mid-run. This is the exact track_d2_prep mixed-rev defect."
    log "!!! ABORTING rather than producing a mixed-rev archive."
    exit 3
  fi
  if ! src_is_clean; then
    log "!!! FATAL at boundary '$1': ${CODE_PATHS[*]} dirty. ABORTING."
    exit 3
  fi
  record_src_boundary "$1"
}

write_blind_proof() {
  local bc head anc="no"
  bc="$(tr -d '[:space:]' < "$DIR/BLIND_COMMIT")"
  head="$(git -C "$REPO" rev-parse HEAD)"
  if git -C "$REPO" merge-base --is-ancestor "$bc" HEAD 2>/dev/null; then anc="yes"; fi
  "$PY" - "$DIR/BLIND_PROOF.json" "$bc" "$head" "$anc" <<'BEOF' || true
import json, sys, time
p, bc, head, anc = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
json.dump({"blind_commit": bc, "head_at_launch": head,
           "is_ancestor_of_head": anc == "yes",
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("READ_RULE.md SS3 G-BLIND is gated against THIS artifact plus a live "
                   "git-ancestry re-check. The blind commit is the commit that introduced "
                   "the FROZEN banner on DESIGN.md/READ_RULE.md; its sha is stamped by a "
                   "follow-up commit because a commit cannot name its own hash.")},
          open(p, "w"), indent=2, sort_keys=True)
BEOF
  if [ "$anc" != "yes" ]; then
    log "!!! FATAL: BLIND_COMMIT $bc is NOT an ancestor of HEAD -- G-BLIND cannot pass."
    exit 2
  fi
}

# --------------------------------------------------------------------------- #
# RAM. The laptop's WSL VM is capped near 11.7 GB and a guest OOM tears down    #
# the WHOLE VM, not one worker (reference_wsl2_host_memory_teardown).           #
# --------------------------------------------------------------------------- #
mem_avail_mb() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }

require_ram() {   # $1 = floor MB, $2 = context label
  local avail; avail="$(mem_avail_mb)"
  log "[ram] $2: MemAvailable=${avail} MB (floor ${1} MB)"
  if [ "$avail" -lt "$1" ]; then
    log "!!! FATAL: $2 MemAvailable ${avail} MB < floor ${1} MB. FAIL-CLOSED."
    log "!!! Riding a low-memory laptop at W=$W_LAPTOP risks a WSL VM TEARDOWN,"
    log "!!! which kills every worker AND the launcher AND the ssh session."
    return 1
  fi
  return 0
}

# --------------------------------------------------------------------------- #
# Leaf + R9 pre-flight, in a CHILD process (the same import path the cells use).#
# R9 is import-latched; a parent-only check proves nothing about the children.  #
# --------------------------------------------------------------------------- #
preflight_env() {
  [ -f "$CAND_LEAF_JSON" ] || { log "!!! FATAL: missing $CAND_LEAF_JSON"; exit 4; }
  CARC_PF_LEAF_JSON="$CAND_LEAF_JSON" \
  CARC_PF_HASH="$PROD_LEAF_HASH" \
  CARC_PF_REPO="$REPO" \
  CARC_PF_PROFILE="$RULES_PROFILE" \
  "$PY" - <<'PFEOF' || { log "!!! FATAL: leaf/R9 pre-flight FAILED. No game runs."; exit 4; }
import os, sys
repo = os.environ["CARC_PF_REPO"]
sys.path.insert(0, os.path.join(repo, "src"))
sys.path.insert(0, os.path.join(repo, "scripts", "classical_search"))
import carcassonne_ai
print(f"[preflight] carcassonne_ai.__file__ = {carcassonne_ai.__file__}")
if not carcassonne_ai.__file__.startswith(repo):
    print(f"[preflight] !!! carcassonne_ai loaded OUTSIDE {repo} -- the venv's editable "
          f"install points at the wrong tree. VOID."); sys.exit(1)

from carcassonne_ai import rules_profile as rp
assert rp.r9_env_on(), "CARCASSONNE_FIX_R9 not latched in a CHILD process"
prof = rp.resolve(os.environ["CARC_PF_PROFILE"])
m = prof.as_manifest()
assert m["r9_env_ok"] is True, m
print(f"[preflight] {os.environ['CARC_PF_PROFILE']} resolved, r9_env_ok=True")

import eval_fair_puct as H
cfg = H._load_cand_leaf_cfg(os.environ["CARC_PF_LEAF_JSON"])
got = H._leaf_hash(cfg)
want = os.environ["CARC_PF_HASH"]
print(f"[preflight] candidate leaf hash = {got} (want {want})")
if got != want:
    print("[preflight] !!! LEAF HASH MISMATCH -- refusing to spend 1400 games on the "
          "wrong leaf."); sys.exit(1)
print("[preflight] leaf + rules OK")
PFEOF
}

# --------------------------------------------------------------------------- #
# Foreign-run + census guards. The laptop is busy with carcasum_arb_challenge   #
# until ~05:00 EDT; wait on the ARTIFACT, never on a human clock.               #
# --------------------------------------------------------------------------- #
require_box_free() {
  local foreign
  foreign="$(find "$REPO/measurement" -name RUN_LIVE.json 2>/dev/null \
             | grep -v "^$DIR/RUN_LIVE.json$" || true)"
  if [ -n "$foreign" ]; then
    log "!!! FATAL: a FOREIGN run is live -- RUN_LIVE.json present at:"
    echo "$foreign" | sed 's/^/[h2h22k]   /'
    log "!!! This cell is an EXCLUSIVE TENANT (DESIGN.md SS6). Wait for the sentinel to"
    log "!!! clear; do NOT delete it without confirming the other run is actually dead."
    return 1
  fi
  local tenants
  tenants="$(pgrep -af 'eval_fair_puct|eval_puct_priors|gen_fair_distill|carcasum_driver|match\.py' \
             | grep -v run_cells || true)"
  if [ -n "$tenants" ]; then
    log "!!! FATAL: process census NOT clean -- co-tenants found:"
    echo "$tenants" | sed 's/^/[h2h22k]   /'
    log "!!! feedback_no_agent_compute_beside_eval: nice+thread-caps are NOT coexistence"
    log "!!! on this box. FAIL-CLOSED."
    return 1
  fi
  log "[census] clean: no foreign RUN_LIVE.json, no co-tenant process"
  return 0
}

require_preconditions() {
  local bc="$DIR/BLIND_COMMIT" psr="$DIR/$PINNED_SRC_REV_FILE" bcl="$DIR/$BAND_SENTINEL"

  # (1) BLIND_COMMIT -- real sha, not PENDING, and consistent with WORKERS.conf.
  if [ ! -f "$bc" ] || ! grep -qE '^[0-9a-f]{40}$' "$bc"; then
    log "!!! FATAL: $bc missing or not a 40-hex sha (still PENDING?)."
    log "!!! A follow-up commit must stamp the freeze commit's own sha before any launch."
    exit 2
  fi
  if [ "$BLIND_COMMIT" = "PENDING" ] || ! [[ "$BLIND_COMMIT" =~ ^[0-9a-f]{8,40}$ ]]; then
    log "!!! FATAL: WORKERS.conf::BLIND_COMMIT is still the PENDING placeholder."
    exit 2
  fi
  if [[ "$(tr -d '[:space:]' < "$bc")" != "$BLIND_COMMIT"* ]]; then
    log "!!! FATAL: BLIND_COMMIT file and WORKERS.conf::BLIND_COMMIT disagree."
    exit 2
  fi

  # (2) PINNED_SRC_REV -- real sha.
  if [ ! -f "$psr" ] || ! grep -qE '^[0-9a-f]{40}$' "$psr"; then
    log "!!! FATAL: $psr missing or not a 40-hex sha (the mixed-rev fix)."
    exit 2
  fi

  # (4) BAND_CLAIMED -- this script NEVER claims a band itself.
  if [ ! -f "$bcl" ]; then
    log "!!! FATAL: $bcl missing. The ORCHESTRATOR drops it AFTER appending DESIGN.md SS4's"
    log "!!! row to governance/BAND_REGISTRY.csv. This script never claims a band."
    exit 2
  fi

  write_blind_proof                 # (1) ancestry
  assert_rev_pinned "pre-flight"    # (2)(3) rev + clean src, logged
  preflight_env                     # (5)(6) R9 latch + leaf hash, in a CHILD

  # (7) nproc >= W
  local np; np="$(nproc)"
  if [ "$np" -lt "$W_LAPTOP" ]; then
    log "!!! FATAL: nproc=$np < W=$W_LAPTOP. An under-provisioned box thrashes silently."
    exit 2
  fi
  log "[preflight] nproc=$np >= W=$W_LAPTOP"

  require_ram "$PREFLIGHT_RAM_FLOOR_MB" "pre-flight" || exit 2   # (8)
  require_box_free || exit 2                                     # (9)(10)
  log "[preflight] ALL 10 CHECKS PASS -- clear to launch"
}

# --------------------------------------------------------------------------- #
# RUN_LIVE freeze-latch sentinel.                                              #
# --------------------------------------------------------------------------- #
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("22016-vs-11008 budget H2H freeze-latch sentinel: a MAIN-TREE commit "
                   "while this cell is live risks a mixed-rev archive (the track_d2_prep "
                   "defect). Cleared on the launcher's EXIT trap."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  log "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

# --------------------------------------------------------------------------- #
# Archive accounting.                                                          #
#                                                                              #
# ⚠️ -maxdepth 1 IS LOAD-BEARING. eval_fair_puct.py writes SUCCESS records as    #
# <cell>/seed%012d_a%d.json but FAILURE records into a SUBDIRECTORY,            #
# <cell>/failed/ (FAILED_DIRNAME), using the SAME filename. Its own comment:    #
# "NOT the cell dir itself -- every downstream reader globs the cell dir        #
# NON-RECURSIVELY." A recursive find would count failures as completions and    #
# walk this launcher straight past a broken cell.                              #
# --------------------------------------------------------------------------- #
n_records() { find "$CELL_OUT" -maxdepth 1 -name 'seed*_a*.json' 2>/dev/null | wc -l; }

# Stale-claim sweep: a pass killed by `timeout` strands .claim files, and a
# stranded claim stalls resume until it ages past CLAIM_STALE_SECS
# (feedback_shared_claim_orphan_stall). The harness writes the claim beside the
# record as <same-stem>.claim, so "claim with no sibling .json" is exactly the
# orphan set. Applied proactively, not after a stall.
sweep_stale_claims() {
  local swept=0 c base
  while IFS= read -r c; do
    [ -n "$c" ] || continue
    base="${c%.claim}"
    if [ ! -f "$base.json" ]; then
      rm -f "$c" && swept=$((swept + 1))
    fi
  done < <(find "$CELL_OUT" -maxdepth 1 -name '*.claim' 2>/dev/null || true)
  [ "$swept" -gt 0 ] && log "[claims] swept $swept orphan claim(s) with no matching record"
  return 0
}

n_failed_records() { find "$CELL_OUT/failed" -maxdepth 1 -name 'seed*_a*.json' 2>/dev/null | wc -l; }

# LAUNCHER-SAFETY void breaker (10%), DISTINCT from READ_RULE SS3's G-N
# adjudication bar (<2%, decided after the fact against a frozen record).
check_void_rate() {
  local sumfile
  sumfile="$(find "$CELL_OUT" -maxdepth 1 -name summary.json 2>/dev/null | sort | tail -1)"
  [ -n "$sumfile" ] && [ -f "$sumfile" ] || { log "[void-rate] no summary.json yet -- skipping"; return 0; }
  "$PY" - "$sumfile" "$VOID_RATE_ABORT_PCT" <<'VEOF'
import json, sys
p, pct = sys.argv[1], float(sys.argv[2])
s = json.load(open(p))
n_failed = s.get("n_failed", 0) or 0
n_scored = s.get("n_scored", s.get("n", 0)) or 0
denom = max(n_scored + n_failed, 1)
rate = n_failed / denom
print(f"[void-rate] n_failed={n_failed} denom={denom} void_rate={rate:.3%}")
if rate * 100 >= pct:
    print(f"[void-rate] !!! ABORT: {rate:.1%} >= {pct}% -- LAUNCHER-SAFETY breaker. This is "
          f"NOT the READ_RULE G-N adjudication gate; it is a pre-adjudication abort to stop "
          f"burning compute against a broken instrument.")
    sys.exit(1)
print(f"[void-rate] OK (< {pct}% launcher-safety threshold).")
VEOF
}

# --------------------------------------------------------------------------- #
print_dry_run() {
  build_argv "$N_GAMES" "$DECK_SEED_START" "$W_LAPTOP" "$OUT_CELL"
  printf '[dry-run] REAL CELL:'; printf ' %q' "${ARGV[@]}"; printf '\n'
  build_argv "$SMOKE_GAMES" "$SMOKE_SEED_START" "$SMOKE_WORKERS" "smoke_$OUT_CELL"
  printf '[dry-run] SMOKE    :'; printf ' %q' "${ARGV[@]}"; printf '\n'
  log "band            : $DECK_SEED_START..$DECK_SEED_END ($N_DECKS decks, no top-up)"
  log "n               : $N_GAMES games = $N_DECKS decks x 2 seatings (deck-paired)"
  log "axis            : --k-dets $F_K_DETS (=$F_TOTAL_SIMS) vs --opp-k-dets $E_K_DETS (=$E_TOTAL_SIMS)"
  log "                  sims_per_det = $F_SIMS_PER_DET on BOTH sides (must-not-differ)"
  log "tie-arbiter     : OFF both sides -- NO --cand-tiearb-* flag is emitted above"
  log "passes          : up to $MAX_PASSES x ${PASS_TIMEOUT_SECS}s (expect ~14); ceiling $((MAX_PASSES*PASS_TIMEOUT_SECS/3600)) h"
  log "cost model      : 442 worker-s/game at W=$W_LAPTOP -> ~6.6 h projected (DESIGN.md SS7)"
  log "RAM floors      : preflight ${PREFLIGHT_RAM_FLOOR_MB} MB / runtime ${RUNTIME_RAM_FLOOR_MB} MB"
  log "adjudicator     : $ADJUDICATOR  (run --selftest before trusting a real read)"
}

run_smoke() {
  log "SMOKE (DESIGN.md SS9): $SMOKE_GAMES games at PRODUCTION knobs, dev seed "
  log "  $SMOKE_SEED_START, W=$SMOKE_WORKERS. Never pooled, never claimed, never adjudicated."
  log "  EXEMPT from the blind/band preconditions -- it spends no blindness and no band."
  preflight_env
  mkdir -p "$LOGS"
  build_argv "$SMOKE_GAMES" "$SMOKE_SEED_START" "$SMOKE_WORKERS" "smoke_$OUT_CELL"
  set +e
  "${ARGV[@]}" 2>&1 | tee "$LOGS/smoke.log"
  local rc=${PIPESTATUS[0]}
  set -e
  if [ "$rc" -ne 0 ]; then
    log "!!! SMOKE FAILED rc=$rc -- do NOT launch. See $LOGS/smoke.log"
    exit 1
  fi
  log "SMOKE completed rc=0. NOW CHECK THE SIX BARS BY HAND (DESIGN.md SS9):"
  log "  1. 2/2 games, n_failed == 0"
  log "  2. backend.converted_sides == [candidate, opponent] AND mixed_builds == false"
  log "  3. cand_leaf_hash == $PROD_LEAF_HASH on BOTH sides"
  log "  4. cand_tiearb absent/disabled, no *_tiearb key armed"
  log "  5. budgets read back (16,1376,22016)/(8,1376,11008), products hold"
  log "     (expect a NON-FATAL [warn] 'k_dets=16 (production 8)' -- correct, do not suppress)"
  log "  6. champ_prefix_ms_per_move within +-25% of 3555 ms/move (W=2, near-unloaded)"
  log "Then: $PY $REPO/$ADJUDICATOR --selftest   (must exit 0)"
}

main() {
  mkdir -p "$LOGS"

  if [ "$DRY" -eq 1 ]; then
    log "DRY RUN -- no games start, no guards enforced beyond argv construction"
    print_dry_run
    return 0
  fi

  if [ "$SMOKE" -eq 1 ]; then
    run_smoke
    return 0
  fi

  local done_sentinel="$DIR/DONE_cell_$OUT_CELL"
  if [ -f "$done_sentinel" ]; then
    log "cell already DONE -- nothing to do. Remove $done_sentinel to force a re-run."
    return 0
  fi
  rm -f "$DIR/FAILED_cell_$OUT_CELL" "$DIR/FAILED_VOID_RATE" "$DIR/FAILED_RAM" 2>/dev/null || true

  require_preconditions
  mkdir -p "$CELL_OUT"
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "22016-vs-11008 direct budget H2H, band $BAND, n=$N_GAMES, W=$W_LAPTOP"

  local pass=0 n_done prev_done t0 t1 dt
  n_done="$(n_records)"
  log "starting from $n_done/$N_GAMES records already on disk"

  while [ "$n_done" -lt "$N_GAMES" ]; do
    pass=$((pass + 1))
    if [ "$pass" -gt "$MAX_PASSES" ]; then
      log "!!! FATAL: MAX_PASSES=$MAX_PASSES exhausted at $n_done/$N_GAMES records."
      log "!!! FAIL-CLOSED -- a resume loop that cannot finish is a defect, not a retry."
      touch "$DIR/FAILED_cell_$OUT_CELL"
      exit 6
    fi

    assert_rev_pinned "before-pass-$pass"
    require_ram "$RUNTIME_RAM_FLOOR_MB" "before-pass-$pass" || {
      touch "$DIR/FAILED_RAM"; exit 8; }

    prev_done="$n_done"
    build_argv "$N_GAMES" "$DECK_SEED_START" "$W_LAPTOP" "$OUT_CELL"
    log "pass $pass/$MAX_PASSES: $n_done/$N_GAMES records, timeout ${PASS_TIMEOUT_SECS}s"

    t0="$(date +%s)"
    set +e
    timeout --preserve-status "${PASS_TIMEOUT_SECS}s" "${ARGV[@]}" \
      >> "$LOGS/cell.log" 2>&1
    local rc=$?
    set -e
    t1="$(date +%s)"; dt=$((t1 - t0))

    assert_rev_pinned "after-pass-$pass"
    sweep_stale_claims
    n_done="$(n_records)"

    local made=$((n_done - prev_done))
    if [ "$made" -gt 0 ]; then
      log "pass $pass: rc=$rc, ${dt}s wall, +$made games -> $n_done/$N_GAMES"
      log "pass $pass: REALIZED $(( dt * W_LAPTOP / made )) worker-s/game (model: 442)"
    else
      log "pass $pass: rc=$rc, ${dt}s wall, +0 games -> $n_done/$N_GAMES"
    fi

    if [ "$rc" -eq 124 ]; then
      log "pass $pass hit its ${PASS_TIMEOUT_SECS}s timeout -- expected for a sized pass;"
      log "  the archive is resumable and the next pass continues it."
    elif [ "$rc" -ne 0 ]; then
      log "pass $pass rc=$rc (non-timeout). The harness is resumable under --shared-claim;"
      log "  continuing, but a pass that makes NO progress fails closed below."
    fi

    if [ "$made" -eq 0 ]; then
      local nf; nf="$(n_failed_records)"
      log "!!! FATAL: pass $pass produced 0 new games at $n_done/$N_GAMES."
      log "!!! failure records in $CELL_OUT/failed/ : $nf"
      if [ "$nf" -gt 0 ]; then
        log "!!! => the shortfall is PERMANENTLY-FAILING GAMES, not a stall. READ_RULE SS3"
        log "!!! G-N requires 1400 scored with n_failed == 0 (a rate <2% is REPORTED, never"
        log "!!! silently absorbed), so this cell cannot adjudicate as-is. Diagnose the"
        log "!!! failure class before spending another pass."
      else
        log "!!! => a stalled --resume loop with NO failures is a launcher/harness defect,"
        log "!!! not something to retry silently. Check $LOGS/cell.log and look for"
        log "!!! stranded .claim files under $CELL_OUT (the sweep above should have"
        log "!!! cleared any orphan; a claim WITH a sibling record is not an orphan)."
      fi
      log "!!! FAIL-CLOSED."
      touch "$DIR/FAILED_cell_$OUT_CELL"
      exit 5
    fi

    check_void_rate || {
      log "!!! ABORTING: void-rate launcher-safety breaker tripped."
      touch "$DIR/FAILED_VOID_RATE"
      exit 7
    }
  done

  # Final settling pass over the FULL range: every game is already recorded, so
  # this does no new work -- it exists so the harness writes the POOLED
  # summary.json over all N_GAMES that the adjudicator reads (READ_RULE SS3).
  log "all $n_done/$N_GAMES records present -- running the FINAL POOLED SUMMARY pass"
  assert_rev_pinned "before-seal"
  build_argv "$N_GAMES" "$DECK_SEED_START" "$W_LAPTOP" "$OUT_CELL"
  set +e
  timeout --preserve-status "${PASS_TIMEOUT_SECS}s" "${ARGV[@]}" >> "$LOGS/cell.log" 2>&1
  local src=$?
  set -e
  assert_rev_pinned "after-seal"
  if [ "$src" -ne 0 ]; then
    log "!!! FATAL: the sealing pass exited rc=$src -- no pooled summary.json is trustworthy."
    touch "$DIR/FAILED_cell_$OUT_CELL"
    exit 9
  fi
  check_void_rate || { touch "$DIR/FAILED_VOID_RATE"; exit 7; }

  run_live_clear
  touch "$done_sentinel"
  log "DONE -- $n_done/$N_GAMES games, $pass pass(es) + seal; RUN_LIVE cleared"
  log "NEXT: $PY $REPO/$ADJUDICATOR --selftest   (must exit 0), then"
  log "      $PY $REPO/$ADJUDICATOR --run-dir $CELL_OUT"
  log "The fired branch IS the authorization to report it (READ_RULE SS4)."
}

main "$@"
