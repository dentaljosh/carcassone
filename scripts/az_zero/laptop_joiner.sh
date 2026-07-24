#!/usr/bin/env bash
# ============================================================================
# az_zero — LAPTOP work-stealing JOINER (runs ON the laptop; laptop-side GPU).
#
# Additive helper for scripts/az_zero/run_az_zero.sh (the LOCAL loop driver).
# It contributes self-play games to whatever az_zero gen iteration the local
# driver is CURRENTLY generating, using the LAPTOP's own 4070m through a
# LAPTOP-side carc-orch SHM server — the first time the orch has served az gen
# off-box. It touches NOTHING the local driver owns: it only adds seed_*.npz
# into the SAME shared iter dir; the local driver counts npz there, so laptop
# games fold in automatically.
#
# It is a thin wrapper around scripts/canonical_az/gen_m2_orch.sh (which already
# exports the net -> TorchScript with a parity gate, starts/【trap-】cleans up a
# per-box carc-orch SHM server named m2gen<HOST>, and runs run_selfplay_iter.py).
# The joiner adds only: (1) detect the current in-progress iter, (2) mirror the
# az_zero recipe, (3) call gen_m2_orch.sh with --shared-claim --claim-host laptop.
#
# ⚠️ COORDINATION NOTE (read before trusting "no double play"):
#   The LOCAL az driver runs gen_m2_orch.sh WITHOUT --shared-claim (it is
#   "LOCAL ONLY" by design), so it neither writes nor reads .claim files.
#   Cross-box de-dup therefore rests on the UNCONDITIONAL npz-existence cache in
#   run_selfplay_iter._play_one_pool (line ~317: `if path.exists(): cached`),
#   which BOTH boxes honour regardless of the claim flag — each box skips any
#   seed the other has already written. The remaining overlap is seeds both
#   boxes are ACTIVELY playing at the same moment (the shared frontier / tail).
#   Those are HARMLESS: GameDataset.save writes a host+pid-unique temp
#   `.<stem>.<host>.<pid>.partial.npz` then atomically renames — last writer
#   wins, both datasets valid, never a partial read (see warmstart.py save()
#   docstring). We still pass --shared-claim here: it makes run_selfplay shuffle
#   the laptop's seed walk (crc32("laptop")) so the laptop starts far from the
#   local box's ascending frontier — minimising the overlap — and it coordinates
#   the laptop's own workers. For CLEAN O_EXCL cross-box work-stealing the LOCAL
#   driver would also need --shared-claim (a one-line add to run_az_zero.sh's gen
#   call, for the NEXT run — do NOT edit the live process).
#
# ⚠️ There is NO per-iter manifest.json in the az gen dirs (only seed_*.npz), so
#   the joiner cannot read config from disk. The recipe below MIRRORS
#   run_az_zero.sh's live defaults (GAMES/SIMS/CPUCT/FPU/VALUE_TARGET/SEED_BASE).
#   If the local driver was launched with non-default knobs, override via env.
#
# LAUNCH (from the local box, via the pipe-a-script rule; detached on the laptop):
#   ssh laptop-wsl 'bash -s' <<'EOF'
#   cd /home/doctor/projects/carcassone
#   mkdir -p /mnt/carc-shared/az_zero_20260724/logs
#   setsid nice -n 19 bash scripts/az_zero/laptop_joiner.sh \
#     > /mnt/carc-shared/az_zero_20260724/logs/laptop_joiner.log 2>&1 </dev/null &
#   echo "joiner pid $!"
#   EOF
#
# STOP: `touch <RUN_ROOT>/STOP`  (clean loop exit), or kill the joiner pid.
# ============================================================================
set -uo pipefail

# --- paths (LAPTOP mount!) --------------------------------------------------
REPO=${REPO:-/home/doctor/projects/carcassone}
SHARE=${SHARE:-/mnt/carc-shared}                 # laptop share mount (NOT /mnt/c)
TAG=${TAG:-az_zero_20260724}
RUN_ROOT=${RUN_ROOT:-$SHARE/$TAG}                 # the SAME run root the local driver writes
GEN_ORCH=${GEN_ORCH:-$REPO/scripts/canonical_az/gen_m2_orch.sh}

# --- mirrored self-play recipe (== run_az_zero.sh defaults) -----------------
GAMES=${GAMES:-300}
SIMS=${SIMS:-128}
CPUCT=${CPUCT:-3.0}
FPU=${FPU:-0.6}
VALUE_TARGET=${VALUE_TARGET:-score_diff}
SEED_BASE=${SEED_BASE:-0}                          # run_selfplay seed = iter*10000 + SEED_BASE + i
RANDOM_CKPT=${RANDOM_CKPT:-$RUN_ROOT/ckpt/iter_-1_random.pt}   # iter-0 warm-from

# --- laptop knobs -----------------------------------------------------------
W_LAPTOP=${W_LAPTOP:-8}                            # gen workers (== gen_m2_orch server W); GPU-trip-bound
CLAIM_HOST=${CLAIM_HOST:-laptop}
START=${START:-0}; END=${END:-11}                 # iter window (matches run_az_zero START/END)
POLL=${POLL:-15}                                  # idle re-scan interval (s)
STOP_FILE=${STOP_FILE:-$RUN_ROOT/STOP}
ONESHOT=${ONESHOT:-0}                             # 1 = join exactly one iter then exit (smoke)

# --- production leaf env (only the featurizer matters under --leaf-eval nn) --
export CARCASSONNE_USE_CY_REPR=${CARCASSONNE_USE_CY_REPR:-1}
export CARCASSONNE_USE_FLAT_LEAF=${CARCASSONNE_USE_FLAT_LEAF:-1}
export CARCASSONNE_USE_CY_LEAF=${CARCASSONNE_USE_CY_LEAF:-1}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
export MKL_NUM_THREADS=${MKL_NUM_THREADS:-1}
export OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-1}

_nn()       { printf "%02d" "$1"; }
_warm_for() { if [ "$1" -eq 0 ]; then echo "$RANDOM_CKPT"; else echo "$RUN_ROOT/ckpt/iter_$(_nn $(( $1 - 1 ))).pt"; fi; }
_npz_count(){ ls "$RUN_ROOT/iter_$(_nn "$1")"/seed_*.npz 2>/dev/null | wc -l; }

# Highest iter that is (a) not gen-done, (b) not already fully generated
# (npz < GAMES), (c) has its warm net ready, (d) has been STARTED by the local
# driver (its iter dir exists — so the joiner never runs ahead of local).
_find_joinable() {
  local it warm n
  for it in $(seq "$END" -1 "$START"); do
    [ -f "$RUN_ROOT/done/gen$it" ] && continue
    n=$(_npz_count "$it"); [ "$n" -ge "$GAMES" ] && continue
    warm=$(_warm_for "$it"); [ -s "$warm" ] || continue
    [ -d "$RUN_ROOT/iter_$(_nn "$it")" ] || continue
    echo "$it"; return 0
  done
  return 1
}

# Reap ONLY this joiner's gen: our unique run_selfplay main + our uniquely-named
# orch server (m2genlaptop). Deliberately does NOT match gen_fair_distill.py (the
# live laptop distill workers) nor the local box's m2gen5800x server. Self-match
# guarded with [r]/[c]. gen_m2_orch.sh ALSO traps its own server on exit; this is
# belt-and-suspenders for the case where the joiner itself is signalled mid-gen.
_cleanup() {
  pkill -9 -f "[r]un_selfplay_iter.py" 2>/dev/null || true
  pkill -9 -f "[c]arc-orch.*--shm-name m2genlaptop" 2>/dev/null || true
}
trap '_cleanup; echo "=== az_zero laptop joiner EXIT @ $(date) ==="' EXIT
trap 'echo "[signal] joiner TERM/INT @ $(date) — finalizing"; exit 130' INT TERM

cd "$REPO" || { echo "FATAL: cannot cd $REPO" >&2; exit 1; }
mkdir -p "$RUN_ROOT/logs"
echo "=== az_zero LAPTOP JOINER @ $(date) ==="
echo "    run root : $RUN_ROOT   (share=$SHARE)"
echo "    recipe   : GAMES=$GAMES sims=$SIMS c_puct=$CPUCT fpu=$FPU value_target=$VALUE_TARGET seed_base=$SEED_BASE"
echo "    laptop   : W=$W_LAPTOP claim-host=$CLAIM_HOST  iters $START..$END  poll=${POLL}s oneshot=$ONESHOT"
echo "    gen unit : $GEN_ORCH  (laptop orch shm=m2genlaptop, GPU=cuda/4070m)"

while true; do
  if [ -f "$STOP_FILE" ]; then echo "[joiner] STOP file present ($STOP_FILE) — exiting"; break; fi
  if [ -f "$RUN_ROOT/done/iter$END" ]; then echo "[joiner] run complete (done/iter$END) — exiting"; break; fi

  if it=$(_find_joinable); then
    nn=$(_nn "$it"); warm=$(_warm_for "$it"); glog="$RUN_ROOT/logs/gen_laptop_it${nn}.log"
    echo "[joiner] JOIN iter $it (warm=$(basename "$warm"), npz so far=$(_npz_count "$it")/$GAMES) @ $(date) -> $glog"
    REPO="$REPO" HOST=laptop WARM="$warm" ITER="$it" OUT="$RUN_ROOT" \
      GAMES="$GAMES" SIMS="$SIMS" CPUCT="$CPUCT" FPU="$FPU" VALUE_TARGET="$VALUE_TARGET" \
      OW="$W_LAPTOP" SEED_START="$SEED_BASE" \
      nice -n 19 bash "$GEN_ORCH" --leaf-eval nn --shared-claim --claim-host "$CLAIM_HOST" \
      > "$glog" 2>&1
    rc=$?
    echo "[joiner] iter $it gen returned rc=$rc (npz now=$(_npz_count "$it")/$GAMES) @ $(date)"
    if [ "$rc" -ne 0 ]; then echo "[joiner] WARN: gen_m2_orch rc=$rc; tail:"; tail -8 "$glog"; fi
    if [ "$ONESHOT" = 1 ]; then echo "[joiner] ONESHOT — exiting after one iter"; break; fi
    # brief settle so we don't re-scan the same iter before local's done marker /
    # the last cross-box npz lands (the npz>=GAMES guard usually already skips it).
    sleep "$POLL"
  else
    # nothing to join right now — local is between iters (training/screening).
    sleep "$POLL"
  fi
done
