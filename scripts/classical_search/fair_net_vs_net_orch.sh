#!/usr/bin/env bash
# Fair net-vs-net (or net-vs-fair-champion) through TWO carc-orch SHM GPU orchestrators
# — one server per net, the two contexts sharing the one GPU. The GPU-batched path for
# eval_fair_puct.py --opponent net; per-worker batch-1 CPU forwards are GPU-latency-bound,
# the orchestrator batches them (the standing default for all neural eval).
#
# Mirrors scripts/heuristic_v28/v28_net_vs_net_orch.sh (server lifecycle, stale cleanup,
# forwarder- readiness gate, trap/kill, per-side TorchScript export) with TWO deliberate
# differences — read these before editing:
#
#  1. ⚠️ PER-SERVER --n-ch. carc-orch DEFAULTS n_ch=78 (rust/carc-orch/src/main.rs:58).
#     v28 never passed it because every v28 net was 78ch — but the distill candidates are
#     cross-rep: sighted 81ch/42-scalar vs non-sighted 78ch/10. A sighted server left at
#     the 78 default silently corrupts every forward (wrong plane count => garbage priors,
#     a weak-but-plausible agent, no crash). Both --n-ch AND --n-scalar are peeked from
#     EACH checkpoint and passed per side. This is the stage-2 trap.
#
#  2. ⚠️ NO LEAF ENV. v28 exports a LEAFENV; this script deliberately exports NONE.
#     eval_fair_puct.py sets its own _CANON_ENV via os.environ.setdefault at import, and a
#     pre-set CARCASSONNE_V29_MEEPLE_CURVE would WIN over that setdefault and move
#     DEFAULT_CONFIG — i.e. move the h800 ruler and silently invalidate every cross-arm
#     comparison. The harness injects the candidate/opponent curve125 leaf IN-PROCESS.
#     Do NOT add a curve env here, and do NOT `source champ_env.sh` before running.
#
# The servers own the only nets (GPU); the client workers are CPU and ship
# (obs, scalars, mask) over shared memory. Keep OW modest on a shared box.
#
#   # cross-rep net-vs-net: sighted candidate vs non-sighted opponent
#   CAND_CKPT=/mnt/c/carc-shared/distill_flywheel_sighted_20260716/ckpt/iter_00.pt \
#   OPP_CKPT=/mnt/c/carc-shared/distill_flywheel_20260715/ckpt/iter_02.pt \
#   OW=4 bash scripts/classical_search/fair_net_vs_net_orch.sh \
#       --exact-k 2 --k-dets 2 --sims 32 --n 2 --paired \
#       --out-root /mnt/c/carc-shared/classical_search --no-results-csv
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=python3
CAND_CKPT=${CAND_CKPT:?set CAND_CKPT=<candidate distilled policy net .pt>}
# OPP_CKPT EMPTY/unset -> --opponent fair-champion: the opponent is the net-free
# PRODUCTION champion (heuristic priors), so only ONE server is needed. Non-empty ->
# --opponent net: a second server for the opponent's net.
OPP_CKPT=${OPP_CKPT:-}
if [ -n "$OPP_CKPT" ]; then MODE=net; else MODE=fair-champion; fi
OW=${OW:-4}                        # CPU workers = SHM slots per server. Keep low on a
                                   # shared box (a concurrent gen run owns the cores).
FWD=${ORCH_FWD:-2}
MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
# OPP_SIMS (optional): ASYMMETRIC search budgets — the opponent runs at this per-det
# sims while --sims (in "$@") stays the CANDIDATE budget (equal-WALL-CLOCK check).
# Empty/unset => --opp-sims is NOT passed (symmetric, byte-unchanged). --sims itself
# still comes through "$@" as before.
OPP_SIMS=${OPP_SIMS:-}
OPP_SIMS_ARGS=()
[ -n "$OPP_SIMS" ] && OPP_SIMS_ARGS=(--opp-sims "$OPP_SIMS")
# OPP_K_DETS (optional): the sibling axis — the opponent runs THIS many determinizations
# while --k-dets (in "$@") stays the CANDIDATE count. Needed for a whole-config A/B
# (CL-060: candidate k8x1376 vs the k4x688 DEPLOY champion), which OPP_SIMS alone cannot
# express. Empty/unset => --opp-k-dets is NOT passed (symmetric, byte-unchanged).
OPP_K_DETS=${OPP_K_DETS:-}
[ -n "$OPP_K_DETS" ] && OPP_SIMS_ARGS+=(--opp-k-dets "$OPP_K_DETS")
SRV="$REPO/rust/carc-orch/run_server.sh"
TS_C="/tmp/carc_fairnvnC_${HOST}.ts.pt"
TS_O="/tmp/carc_fairnvnO_${HOST}.ts.pt"
SHMN_C="fairnvnC${HOST}"
SHMN_O="fairnvnO${HOST}"
LOG_C="/tmp/carc_srvFAIRNVNC_${HOST}.log"
LOG_O="/tmp/carc_srvFAIRNVNO_${HOST}.log"

cd "$REPO"

# --- peek EACH side's rep from its OWN checkpoint (n_ch + n_scalar + sighted). The rep is
#     never assumed: picking the wrong encoder/dims is a silent mis-encode, not a crash.
read -r NC_C NS_C SG_C < <("$PY" - "$CAND_CKPT" <<'EOF'
import sys, torch
ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
print(int(ck.get("n_input_channels", 78)), int(ck.get("n_scalar_features", 10)),
      "sighted" if ck.get("sighted", False) else "non-sighted")
EOF
)
echo "[fair-nvn-orch] CAND $(basename "$CAND_CKPT"): ${NC_C}ch/${NS_C}sc ($SG_C)"
if [ "$MODE" = net ]; then
  read -r NC_O NS_O SG_O < <("$PY" - "$OPP_CKPT" <<'EOF'
import sys, torch
ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
print(int(ck.get("n_input_channels", 78)), int(ck.get("n_scalar_features", 10)),
      "sighted" if ck.get("sighted", False) else "non-sighted")
EOF
)
  echo "[fair-nvn-orch] OPP  $(basename "$OPP_CKPT"): ${NC_O}ch/${NS_O}sc ($SG_O)"
else
  echo "[fair-nvn-orch] OPP  = fair-champion (net-free heuristic priors) -> ONE server only"
fi

# --- export per side -> TorchScript (parity-gated; abort on fail) ---
echo "[fair-nvn-orch] exporting -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CAND_CKPT" --out "$TS_C" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed for CANDIDATE" >&2; exit 1; }
if [ "$MODE" = net ]; then
  "$PY" scripts/export_torchscript.py --checkpoint "$OPP_CKPT" --out "$TS_O" --device cuda \
    || { echo "FATAL: TorchScript export/parity failed for OPPONENT" >&2; exit 1; }
fi

# --- clean any stale carc-orch / shm for THESE two names ONLY (scoped to fairnvn* by -f,
#     NOT a blanket `pkill carc-orch`: this eval may run CONCURRENTLY with a self-play gen
#     orch on the same box — a blanket kill would nuke that gen orch. Keep it scoped.) ---
pkill -f '[f]airnvn' 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN_C" /dev/shm/sem.carc_"${SHMN_C}"_* \
      "/dev/shm/carc_$SHMN_O" /dev/shm/sem.carc_"${SHMN_O}"_* 2>/dev/null || true

# --- launch BOTH servers, each with ITS OWN dims (the n_ch trap above) ---
echo "[fair-nvn-orch] start carc-orch CAND (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN_C n_ch=$NC_C n_scalar=$NS_C"
nice -n 19 "$SRV" --model "$TS_C" --transport shm --shm-name "$SHMN_C" --workers "$OW" \
  --n-ch "$NC_C" --n-scalar "$NS_C" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG_C" 2>&1 &
SRV_C_PID=$!
SRV_O_PID=""
SIDES="C"
if [ "$MODE" = net ]; then
  echo "[fair-nvn-orch] start carc-orch OPP  (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN_O n_ch=$NC_O n_scalar=$NS_O"
  nice -n 19 "$SRV" --model "$TS_O" --transport shm --shm-name "$SHMN_O" --workers "$OW" \
    --n-ch "$NC_O" --n-scalar "$NS_O" \
    --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
    > "$LOG_O" 2>&1 &
  SRV_O_PID=$!
  SIDES="C O"
fi
# shellcheck disable=SC2064
trap 'kill $SRV_C_PID $SRV_O_PID 2>/dev/null; pkill -f '[f]airnvn' 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN_C"'" /dev/shm/sem.carc_'"$SHMN_C"'_* "/dev/shm/carc_'"$SHMN_O"'" /dev/shm/sem.carc_'"$SHMN_O"'_*' EXIT

# --- wait for "forwarder-" in each started log (80 x 0.5s each); FATAL if any dies ---
for side in $SIDES; do
  eval "LOG=\$LOG_$side; PID=\$SRV_${side}_PID"
  for _ in $(seq 1 80); do
    grep -q "forwarder-" "$LOG" 2>/dev/null && break
    kill -0 "$PID" 2>/dev/null || { echo "FATAL: carc-orch $side died early" >&2; tail -15 "$LOG" >&2; exit 1; }
    sleep 0.5
  done
  grep -q "forwarder-" "$LOG" 2>/dev/null \
    || { echo "FATAL: carc-orch $side failed to start" >&2; tail -12 "$LOG" >&2; exit 1; }
done
if [ "$MODE" = net ]; then
  echo "[fair-nvn-orch] BOTH servers READY | CAND shm='$SHMN_C' ${NC_C}ch/${NS_C}sc | OPP shm='$SHMN_O' ${NC_O}ch/${NS_O}sc | client W=$OW"
else
  echo "[fair-nvn-orch] server READY | CAND shm='$SHMN_C' ${NC_C}ch/${NS_C}sc | OPP fair-champion (net-free, no server) | client W=$OW"
fi

# --- run the client. NO leaf env (see header note 2): the harness's _CANON_ENV setdefault
#     must win, and the curve125 leaf is injected in-process per side.
if [ "$MODE" = net ]; then
  nice -n 19 "$PY" -u scripts/classical_search/eval_fair_puct.py \
    --info fair-netprior --net "$CAND_CKPT" \
    --opponent net --opp-net "$OPP_CKPT" \
    --orch-shm-name "$SHMN_C" --opp-orch-shm-name "$SHMN_O" \
    --workers "$OW" "${OPP_SIMS_ARGS[@]}" "$@"
else
  nice -n 19 "$PY" -u scripts/classical_search/eval_fair_puct.py \
    --info fair-netprior --net "$CAND_CKPT" \
    --opponent fair-champion \
    --orch-shm-name "$SHMN_C" \
    --workers "$OW" "${OPP_SIMS_ARGS[@]}" "$@"
fi
