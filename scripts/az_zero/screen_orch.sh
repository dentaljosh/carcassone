#!/usr/bin/env bash
# az_zero anchor screen through carc-orch SHM GPU orchestrator(s) — ONE server per
# net, replacing the net-on-CPU forwards (both sides searching sims=128 on CPU,
# ~1h/screen-point) with GPU-batched forwards (~10-15 min). Mirrors
# scripts/classical_search/fair_net_vs_net_orch.sh (server lifecycle, stale-SHM
# cleanup, forwarder-readiness gate, trap/kill, per-side parity-gated TorchScript
# export) — read that file's header before editing. Two things worth repeating:
#
#  1. ⚠️ PER-SERVER --n-ch/--n-scalar. carc-orch DEFAULTS n_ch=78. The az_zero
#     candidate is SIGHTED (81ch/42-scalar) while the warm-start anchor is BLIND
#     (78ch/10) — a sighted server left at the 78 default silently mis-encodes
#     every forward (garbage priors, a weak-but-plausible agent, NO crash). Both
#     --n-ch AND --n-scalar are peeked from EACH checkpoint and passed per side.
#
#  2. NO LEAF ENV. The screen's leaf IS the net value head (pure-NN agent, no
#     v2.7/v2.9 heuristic leaf, no solver) — so there is nothing to inject and no
#     curve env to set. Do NOT `source champ_env.sh`.
#
# vs_random needs ONLY the candidate server (the opponent is a net-free uniform
# mover). vs a net anchor (OPPONENT=net) starts a SECOND server for the anchor net.
#
#   # vs random (candidate server only):
#   CAND_CKPT=<iter_NN.pt> OPPONENT=random OW=32 HOST=5800x \
#     bash scripts/az_zero/screen_orch.sh \
#         --n 50 --sims 128 --c-puct 3.0 --fpu 0.6 --out <dir>
#   # vs a fixed anchor net (dual server, cross-rep):
#   CAND_CKPT=<iter_NN.pt> OPPONENT=net ANCHOR_CKPT=<warmstart.pt> OW=32 HOST=5800x \
#     bash scripts/az_zero/screen_orch.sh \
#         --n 50 --sims 128 --c-puct 3.0 --fpu 0.6 --out <dir>
#
# MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED.
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=python3
CAND_CKPT=${CAND_CKPT:?set CAND_CKPT=<candidate net .pt>}
OPPONENT=${OPPONENT:-random}       # random (candidate server only) | net (dual server)
ANCHOR_CKPT=${ANCHOR_CKPT:-}
if [ "$OPPONENT" = net ] && [ -z "$ANCHOR_CKPT" ]; then
  echo "FATAL: OPPONENT=net requires ANCHOR_CKPT=<anchor net .pt>" >&2; exit 1
fi
OW=${OW:-8}                         # CPU workers = SHM slots per server. = SCREEN_W in
                                    # production. Keep modest on a shared box.
FWD=${ORCH_FWD:-2}
MB=${ORCH_MAX_BATCH:-16}
HOST=${HOST:-$(hostname)}
SRV="$REPO/rust/carc-orch/run_server.sh"
TS_C="/tmp/carc_azscreenC_${HOST}.ts.pt"
TS_A="/tmp/carc_azscreenA_${HOST}.ts.pt"
SHMN_C="azscreenC${HOST}"
SHMN_A="azscreenA${HOST}"
LOG_C="/tmp/carc_srvAZSCREENC_${HOST}.log"
LOG_A="/tmp/carc_srvAZSCREENA_${HOST}.log"

cd "$REPO"

# --- peek EACH side's rep from its OWN checkpoint (n_ch + n_scalar + sighted). The
#     rep is never assumed: the wrong encoder/dims is a silent mis-encode, not a crash.
read -r NC_C NS_C SG_C < <("$PY" - "$CAND_CKPT" <<'EOF'
import sys, torch
ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
print(int(ck.get("n_input_channels", 78)), int(ck.get("n_scalar_features", 10)),
      "sighted" if ck.get("sighted", False) else "non-sighted")
EOF
)
echo "[az-screen-orch] CAND $(basename "$CAND_CKPT"): ${NC_C}ch/${NS_C}sc ($SG_C)"
if [ "$OPPONENT" = net ]; then
  read -r NC_A NS_A SG_A < <("$PY" - "$ANCHOR_CKPT" <<'EOF'
import sys, torch
ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
print(int(ck.get("n_input_channels", 78)), int(ck.get("n_scalar_features", 10)),
      "sighted" if ck.get("sighted", False) else "non-sighted")
EOF
)
  echo "[az-screen-orch] ANCHOR $(basename "$ANCHOR_CKPT"): ${NC_A}ch/${NS_A}sc ($SG_A)"
else
  echo "[az-screen-orch] opponent = uniform-random (net-free) -> ONE server only"
fi

# --- export per side -> TorchScript (parity-gated; abort on fail) ---
echo "[az-screen-orch] exporting -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$CAND_CKPT" --out "$TS_C" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed for CANDIDATE" >&2; exit 1; }
if [ "$OPPONENT" = net ]; then
  "$PY" scripts/export_torchscript.py --checkpoint "$ANCHOR_CKPT" --out "$TS_A" --device cuda \
    || { echo "FATAL: TorchScript export/parity failed for ANCHOR" >&2; exit 1; }
fi

# --- clean any stale carc-orch / shm for THESE names ONLY (scoped to azscreen* by -f,
#     NOT a blanket `pkill carc-orch`: this screen may run CONCURRENTLY with a self-play
#     gen orch on the same box — a blanket kill would nuke that gen orch). ---
pkill -f '[a]zscreen' 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN_C" /dev/shm/sem.carc_"${SHMN_C}"_* \
      "/dev/shm/carc_$SHMN_A" /dev/shm/sem.carc_"${SHMN_A}"_* 2>/dev/null || true

# --- launch server(s), each with ITS OWN dims (the n_ch trap above) ---
echo "[az-screen-orch] start carc-orch CAND (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN_C n_ch=$NC_C n_scalar=$NS_C"
nice -n 19 "$SRV" --model "$TS_C" --transport shm --shm-name "$SHMN_C" --workers "$OW" \
  --n-ch "$NC_C" --n-scalar "$NS_C" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG_C" 2>&1 &
SRV_C_PID=$!
SRV_A_PID=""
SIDES="C"
if [ "$OPPONENT" = net ]; then
  echo "[az-screen-orch] start carc-orch ANCHOR (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN_A n_ch=$NC_A n_scalar=$NS_A"
  nice -n 19 "$SRV" --model "$TS_A" --transport shm --shm-name "$SHMN_A" --workers "$OW" \
    --n-ch "$NC_A" --n-scalar "$NS_A" \
    --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
    > "$LOG_A" 2>&1 &
  SRV_A_PID=$!
  SIDES="C A"
fi
# shellcheck disable=SC2064
trap 'kill $SRV_C_PID $SRV_A_PID 2>/dev/null; pkill -f '[a]zscreen' 2>/dev/null; rm -f "/dev/shm/carc_'"$SHMN_C"'" /dev/shm/sem.carc_'"$SHMN_C"'_* "/dev/shm/carc_'"$SHMN_A"'" /dev/shm/sem.carc_'"$SHMN_A"'_*' EXIT

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

# --- run the screen client through the SHM server(s). The wrapper injects --cand-ckpt,
#     --opponent, --anchor-ckpt, --workers, and the --*-orch-shm-name flags; "$@" carries
#     the per-run knobs (--n --sims --c-puct --fpu --out ...). Do NOT pass --workers or a
#     server flag in "$@" (argparse duplicate). ---
if [ "$OPPONENT" = net ]; then
  echo "[az-screen-orch] servers READY | CAND shm='$SHMN_C' ${NC_C}ch/${NS_C}sc | ANCHOR shm='$SHMN_A' ${NC_A}ch/${NS_A}sc | client W=$OW"
  nice -n 19 "$PY" -u scripts/az_zero/eval_anchor_screen.py \
    --cand-ckpt "$CAND_CKPT" --opponent net --anchor-ckpt "$ANCHOR_CKPT" \
    --orch-shm-name "$SHMN_C" --anchor-orch-shm-name "$SHMN_A" \
    --workers "$OW" "$@"
else
  echo "[az-screen-orch] server READY | CAND shm='$SHMN_C' ${NC_C}ch/${NS_C}sc | opponent uniform-random (no server) | client W=$OW"
  nice -n 19 "$PY" -u scripts/az_zero/eval_anchor_screen.py \
    --cand-ckpt "$CAND_CKPT" --opponent random \
    --orch-shm-name "$SHMN_C" \
    --workers "$OW" "$@"
fi
