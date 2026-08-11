#!/usr/bin/env bash
# BLIND vs SIGHTED with the anchor's net ON THE GPU — eval_fair_puct.py
# `--opponent bare-net` served by ONE carc-orch SHM eval-server.
#
# Why a separate script from fair_net_vs_net_orch.sh: that script's topology is
# "the CANDIDATE has a net" (CAND_CKPT is mandatory; it always launches a candidate
# server, and optionally a second one for a `net` opponent). The bare-net cell is the
# MIRROR IMAGE — the candidate is net-free (`--info fair`, heuristic priors + the
# frozen curve125 leaf) and the OPPONENT owns the only net. Bending the other script
# into that shape means making CAND_CKPT optional and threading a third MODE through
# every branch of a file that produced live cells, for no shared code beyond ~20 lines
# of server lifecycle. That lifecycle (rep peek, parity-gated export, scoped stale
# cleanup, forwarder- readiness gate, trap) is mirrored here verbatim, INCLUDING both
# of its documented traps:
#
#  1. ⚠️ PER-SERVER --n-ch / --n-scalar. carc-orch DEFAULTS n_ch=78 n_scalar=12
#     (rust/carc-orch/src/main.rs). RoD-v2 iter_02 happens to BE 78ch/12sc, so the
#     defaults would work today by luck — they are still passed explicitly, peeked
#     from the checkpoint, because a wrong plane count is a silent mis-encode (garbage
#     priors, a weak-but-plausible agent, no crash), not a crash.
#  2. ⚠️ NO LEAF ENV. eval_fair_puct.py sets its own _CANON_ENV via
#     os.environ.setdefault; a pre-set CARCASSONNE_V29_MEEPLE_CURVE would WIN over that
#     setdefault and move DEFAULT_CONFIG — which for THIS cell would move the ANCHOR's
#     leaf (it is dataclasses.replace(DEFAULT_CONFIG, ...)) and silently replace the
#     agent the results.csv rows were played by. Do NOT add a curve env, do NOT
#     `source champ_env.sh`.
#
# ...plus two more that are specific to running a server at all:
#
#  3. ⚠️ OMP_NUM_THREADS=1 MUST be in the SERVER's environment. The Rust side never
#     calls torch::set_num_threads, so libtorch sizes its intra-op pool to the core
#     count and OpenMP SPIN-waits: measured 2574% CPU for the server vs 367% for all
#     workers combined. Pinning the Python client does nothing for it — the server is a
#     separate process. Pinned below on the server's own launch line (workers 2.54x,
#     GPU 37W -> 52W).
#  4. ⚠️ --max-batch >= --workers. max_batch counts POSITIONS
#     (rust/carc-orch/src/batcher.rs: `while total_k < max_batch`) and workers BLOCK on
#     their response semaphore, so max_batch < W structurally prevents one round of
#     workers from coalescing into a single forward. MB defaults to OW here and is
#     clamped up if set lower.
#
# ⚠️ TRANSPORT vs ANCHOR IDENTITY. Every RoD-v2 anchor row on record was played
#    net-on-CPU (fp32). This runs the SAME weights on the GPU. Weights, leaf, sims,
#    c_puct, residual_scale and clairvoyance are identical; float reduction order is
#    not, so a near-tied argmax can flip. Quantify before citing:
#      .venv/bin/python scripts/classical_search/bare_net_gpu_divergence.py \
#          --opp-net <ckpt> --max-positions 60
#
#   OPP_CKPT=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt OW=14 \
#     bash scripts/classical_search/bare_net_opp_orch.sh \
#       --exact-k 2 --k-dets 4 --sims 344 --n 200 --paired \
#       --seed-start 68000000000 --out-root /mnt/c/carc-shared/classical_search \
#       --out-subdir blind_k4x1376_vs_sighted_rodv2_it02_b68e9 \
#       --shared-claim --no-results-csv
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=python3
OPP_CKPT=${OPP_CKPT:?set OPP_CKPT=<the SIGHTED bare-NeuralMCTS anchor checkpoint .pt>}
OW=${OW:-14}                       # CPU workers = SHM slots. The candidate side is a
                                   # pure-CPU PIMC search, so W is CPU-bound: size it
                                   # to the box's cores, not to VRAM.
FWD=${ORCH_FWD:-2}
MB=${ORCH_MAX_BATCH:-$OW}
if [ "$MB" -lt "$OW" ]; then
  echo "[bare-net-orch] max_batch $MB < workers $OW -> clamping to $OW (trap 4)" >&2
  MB=$OW
fi
HOST=${HOST:-$(hostname)}
# The client's --workers MUST equal the server's --workers: it is the SHM SLOT COUNT,
# and each worker pops one slot id. A user-supplied --workers in "$@" would win on
# argparse's last-wins and desync the two -> workers indexing slots the server never
# allocated. Set it with OW=, never as a passthrough arg.
for _a in "$@"; do
  case "$_a" in
    --workers|--workers=*)
      echo "FATAL: pass the worker count as OW=<n>, not --workers — it must match the" >&2
      echo "       server's SHM slot count (this script sets both)." >&2
      exit 2;;
  esac
done
SRV="$REPO/rust/carc-orch/run_server.sh"
TS_O="/tmp/carc_barenet_${HOST}.ts.pt"
SHMN="barenet${HOST}"
LOG="/tmp/carc_srvBARENET_${HOST}.log"

cd "$REPO"

# --- peek the anchor's rep from ITS OWN checkpoint (never assumed) ---
read -r NC NS SG < <("$PY" - "$OPP_CKPT" <<'EOF'
import sys, torch
ck = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
print(int(ck.get("n_input_channels", 78)), int(ck.get("n_scalar_features", 10)),
      "sighted" if ck.get("sighted", False) else "non-sighted")
EOF
)
echo "[bare-net-orch] OPP $(basename "$OPP_CKPT"): ${NC}ch/${NS}sc ($SG)"

# --- export -> TorchScript (parity-gated internally; abort on fail) ---
echo "[bare-net-orch] exporting -> TorchScript (parity-gated)"
"$PY" scripts/export_torchscript.py --checkpoint "$OPP_CKPT" --out "$TS_O" --device cuda \
  || { echo "FATAL: TorchScript export/parity failed for the anchor" >&2; exit 1; }

# --- clean stale carc-orch / shm for THIS name ONLY (scoped by -f, never a blanket
#     `pkill carc-orch`: a concurrent gen orch may own the same box) ---
# ⚠️ Match the SERVER BINARY + this shm name, never a bare 'barenet' substring: a
#    caller whose own command line contains that string (e.g. --out-subdir
#    smoke_barenet_gpu) would be killed by its own cleanup. Scoped so a concurrent
#    gen/eval orch on another shm name is untouched.
pkill -f "[c]arc-orch .*--shm-name $SHMN" 2>/dev/null || true; sleep 1
rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true

# --- launch THE server. OMP/MKL pinned HERE (trap 3): this env is the server's own.
echo "[bare-net-orch] start carc-orch (W=$OW fwd=$FWD max_batch=$MB) shm=$SHMN n_ch=$NC n_scalar=$NS"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
nice -n 19 "$SRV" --model "$TS_O" --transport shm --shm-name "$SHMN" --workers "$OW" \
  --n-ch "$NC" --n-scalar "$NS" \
  --device cuda --max-batch "$MB" --batch-timeout-ms 2.0 --forwarders "$FWD" --watchdog-secs 30 \
  > "$LOG" 2>&1 &
SRV_PID=$!
# shellcheck disable=SC2064
# ⚠️ Every cleanup step is `|| true`-guarded and the trap ends with an explicit
#    `exit $rc`: without that, a `kill`/`pkill` that matches nothing (exit 1 — the
#    NORMAL case, since the server is already dead) becomes the SCRIPT's exit status
#    and a successful run reports failure to whatever launched it.
_cleanup() {
  rc=$?
  kill "$SRV_PID" 2>/dev/null || true
  pkill -f "[c]arc-orch .*--shm-name $SHMN" 2>/dev/null || true
  rm -f "/dev/shm/carc_$SHMN" /dev/shm/sem.carc_"${SHMN}"_* 2>/dev/null || true
  exit $rc
}
trap _cleanup EXIT

# --- wait for "forwarder-" in the log (80 x 0.5s); FATAL if it dies early ---
for _ in $(seq 1 80); do
  grep -q "forwarder-" "$LOG" 2>/dev/null && break
  kill -0 "$SRV_PID" 2>/dev/null || { echo "FATAL: carc-orch died early" >&2; tail -15 "$LOG" >&2; exit 1; }
  sleep 0.5
done
grep -q "forwarder-" "$LOG" 2>/dev/null \
  || { echo "FATAL: carc-orch failed to start" >&2; tail -12 "$LOG" >&2; exit 1; }
# Prove the net is on the GPU rather than silently on the CPU: run_server.sh exits
# non-zero without CUDA (require_cuda defaults true unless --allow-cpu/--device cpu),
# but assert the allocation too — a silent CPU fallback that still "works" is the worst
# outcome, since it produces a plausible number at 1/Nx the speed and different floats.
if command -v nvidia-smi >/dev/null 2>&1; then
  SRV_VRAM=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null \
             | awk -F'[, ]+' -v p="$SRV_PID" '$1==p {print $2}')
  if [ -n "$SRV_VRAM" ]; then
    echo "[bare-net-orch] GPU CONFIRMED: carc-orch pid $SRV_PID holds ${SRV_VRAM} MiB VRAM"
  else
    echo "[bare-net-orch] WARNING: carc-orch pid $SRV_PID has no VRAM allocation visible to" >&2
    echo "[bare-net-orch]          nvidia-smi. On WSL2 --query-compute-apps is often empty" >&2
    echo "[bare-net-orch]          even for a live CUDA process; check total used-memory" >&2
    echo "[bare-net-orch]          delta or the log below instead of trusting this line." >&2
  fi
fi
echo "[bare-net-orch] server READY | shm='$SHMN' ${NC}ch/${NS}sc | client W=$OW"
echo "[bare-net-orch] ⚠️ anchor rows on record were net-on-CPU; this cell is net-on-GPU."
echo "[bare-net-orch]    Same weights/leaf/knobs; float reduction order differs. Disclose it."

# --- run the client. NO leaf env (trap 2). The candidate is the net-free fair PIMC
#     champion, so there is no --net and no candidate server.
CARCASSONNE_TT_CAP=${CARCASSONNE_TT_CAP:-200000} \
nice -n 19 "$PY" -u scripts/classical_search/eval_fair_puct.py \
  --info fair --opponent bare-net --opp-net "$OPP_CKPT" \
  --opp-orch-shm-name "$SHMN" \
  --workers "$OW" "$@"
