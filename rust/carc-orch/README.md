# carc-orch — Rust GPU inference orchestrator

A drop-in replacement for the Python `eval_server` + `remote_eval_bridge` pair.
It speaks the **exact same** len-prefixed npy TCP protocol, so existing Python
self-play workers connect to it unchanged via `--remote-eval-server HOST:PORT`.

## Status (2026-06-15): WON 1.33x — deployed local-only

**The CUDA-streams gambit succeeded: stream-SHM W28 BEATS orch-off W14 by 1.33x**
(56 vs 42 games/360s, confirmed n=2). Additions beyond the original TCP server
documented below:
1. **Per-forwarder CUDA streams** (`csrc/cuda_stream_shim.cpp` + `build.rs` — tch
   0.24 has no stream API) — *the win*: W28 runs on ONE shared CUDA context and
   the forwarders' kernels overlap instead of serializing on the default stream.
2. **Zero-copy SHM transport** (`--transport shm`, client
   `src/carcassonne_ai/shm_eval_handles.py`, wired via
   `run_selfplay_iter --shm-eval-server NAME`) — the production path; per-worker
   `/dev/shm` slots + POSIX sems, no np.save round-trip.
3. **N-forwarder batcher** (`--forwarders`, each its own module copy + stream).
4. **Stall watchdog** (`--watchdog-secs`, default 30) — exits loud on a wedged
   forwarder so workers fail clean and the flywheel heal-loop restarts.

Squeeze exhausted (cuDNN / more-forwarders / H2D double-buffer all
neutral-or-worse → **1.33x is the ceiling**; the per-worker CPU v2.7 leaf is the
bottleneck, not the GPU server). **Deployed** into the flywheel's local-box gen
via the share `gen_flywheel.sh` orchestrator branch (`USE_ORCH=1`). xeon/laptop
deferred (no Rust; laptop torch 2.12 ≠ local 2.11). Full detail: STATUS.md
"carc-orch" block + memory `reference_carc_orch_verdict`. The architecture below
describes the TCP transport; SHM mirrors it zero-copy.

## Why

Self-play in residual mode is **GPU-forward-dispatch-limited**: every MCTS node
fires a small net forward (v2.7 flat-leaf + 0.25·net-value). The Python
orchestrator collapsed under three overheads on that hot path —

1. the bridge→eval_server **pickle/mp.Queue hop**,
2. **GIL contention** across the per-connection broker threads,
3. a single **GIL-bound dequeue** thread feeding the GPU.

carc-orch removes all three: one OS thread per connection reads frames and
decodes npy with **no GIL**, and a single lock-free batcher owns the CUDA module
and aggregates across *all* connections into one big forward. Workers become
cheap CPU-only clients (no per-worker net VRAM), so worker count `W` can go far
above the orch-off optimum.

## Architecture

```
 Python worker 1 ─┐  (TCP, npy frames)
 Python worker 2 ─┤        reader thread per conn ──┐
        ...       ┤   (parse npy, no GIL)           │  crossbeam
 Python worker N ─┘                                 ├─► batcher thread
                                                    │   (owns CUDA CModule)
   each reader: send Job ─► batcher ─► recv slice   │   concat across conns,
   ◄──────────── framed npy response ───────────────┘   one forward, scatter
```

- Per connection is **synchronous one-in-flight** (matches the client contract
  in `remote_evaluators._wait_for_response`, which asserts `request_id` match).
- The batcher mirrors `eval_server._server_loop`: block for the first job,
  accumulate to `--max-batch` or `--batch-timeout-ms`, forward once, scatter.

## The model

The net is a `CarcassonneNet` checkpoint exported to TorchScript by
`scripts/export_torchscript.py`, which bakes in the masked softmax so the
scripted signature is exactly `(obs, scalars, mask) -> (priors, value)` — the
wire payload. tch-rs (`tch = 0.24`) loads it on CUDA via the **same libtorch
2.11/cu128** the venv uses (`LIBTORCH_USE_PYTORCH=1`), so the CUDA kernels are
identical to the Python path (fp32 batch-stacking noise only).

## Build

```bash
source /tmp/carc_rust_env.sh      # sets LIBTORCH_USE_PYTORCH, mold, LD paths
cd rust/carc-orch
cargo build --release
```

Uses **mold** for fast relinking against the heavy libtorch .so
(`.cargo/config.toml`). `LIBTORCH_BYPASS_VERSION_CHECK=1` is needed because tch
0.24 predates libtorch 2.11; the C++ ABI is compatible.

## Run

```bash
# export a checkpoint to TorchScript (once per net)
python scripts/export_torchscript.py --checkpoint <ckpt.pt> --out model.ts.pt

# launch the server (LD_PRELOAD of libtorch_cuda.so is baked into run_server.sh
# — the --as-needed linker drops it otherwise, leaving CUDA unregistered)
rust/carc-orch/run_server.sh --model model.ts.pt --port 53918 --device cuda \
    --max-batch 512 --batch-timeout-ms 2.0

# point self-play workers at it. PASS --checkpoint EVEN THOUGH the server owns
# the net (see gotcha below).
python scripts/run_selfplay_iter.py ... --checkpoint <ckpt.pt> \
    --remote-eval-server 127.0.0.1:53918 --workers <W>
```

### ⚠️ Scalar-width gotcha — always pass `--checkpoint` on the workers

The worker's `Game.get_canonical_form` must emit scalars of the **same width**
the server's net expects (10 for legacy nets, **12** for farm-scalar Path-B/E
nets like the residual flywheel champions). `run_selfplay_iter.py` derives that
width by peeking `n_scalar_features` from `--checkpoint`; with no checkpoint it
defaults to **10**, so a 12-scalar server net gets 10-wide features and the
forward crashes (`mat1 and mat2 shapes cannot be multiplied`). The worker never
*loads* the checkpoint in remote mode (the orchestrator branch returns early) —
the main process only reads its metadata — so passing it costs one cheap CPU
metadata read and no per-worker net/VRAM. **Always pass `--checkpoint` matching
the server's `--model`.**

## Validation

- **TorchScript parity** (`export_torchscript.py`): scripted vs eager net match
  to fp32 tolerance (priors <1e-4, value <1e-3) across batch sizes. ✅
- **End-to-end parity** (`scripts/parity_rust_orch.py`): Rust server driven
  through the real Python socket client matches the local net on byte-identical
  inputs (k≤8 bit-identical, k≥37 within fp32 batch-noise). ✅
- **Throughput** (`~/orch_rust_bench.sh`): total-games-in-equal-wall vs
  orch-off — see STATUS.md for the current verdict.
