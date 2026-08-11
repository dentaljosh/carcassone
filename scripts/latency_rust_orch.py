"""Measure the per-forward round-trip latency through the carc-orch server via
the real Python socket client, and translate it into a per-game cost estimate.

This pinpoints WHY remote self-play got 0 games: each MCTS move issues ~sims/8
SEQUENTIAL batch-8 forwards (each depends on the previous tree state), and every
one pays a TCP + npy-serialize + batch-wait round-trip. If that round-trip is
big vs a local GPU forward, games crawl even though the server's aggregate
examples/s looks fine and the GPU is near-idle.
"""
from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.eval_server import EvalRequest
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.remote_socket_handles import connect_remote

CKPT = "/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt"
TS = "/tmp/carc_iter8.ts.pt"
PORT = 53921
SERVER = "/home/doctor/projects/carcassone/rust/carc-orch/run_server.sh"
LOG = "/tmp/carc_orch_lat_server.log"
SIMS = 200
BATCH = 8


def main() -> int:
    logf = open(LOG, "w")
    proc = subprocess.Popen(
        [SERVER, "--model", TS, "--port", str(PORT), "--device", "cuda",
         "--max-batch", "512", "--batch-timeout-ms", "2.0"],
        stdout=subprocess.DEVNULL, stderr=logf, text=True)
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            if Path(LOG).exists() and "READY" in Path(LOG).read_text():
                break
            time.sleep(0.2)
        ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
        n_scalar = int(ckpt.get("n_scalar_features", 10))
        with torch.no_grad():
            net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"],
                                 n_scalar_features=n_scalar)
            A = net(torch.zeros(1, N_CHANNELS, 25, 25), torch.zeros(1, n_scalar))[0].shape[1]

        handles = connect_remote("127.0.0.1", PORT, 0)
        rng = np.random.default_rng(0)
        # warm
        for _ in range(5):
            obs = rng.standard_normal((BATCH, N_CHANNELS, 25, 25), dtype=np.float32)
            scl = rng.standard_normal((BATCH, n_scalar), dtype=np.float32)
            msk = np.ones((BATCH, A), dtype=bool)
            handles.request_q.put(EvalRequest(0, 0, obs, scl, msk))
            handles.response_q.get(timeout=30)

        N = 300
        lat = []
        for i in range(N):
            obs = rng.standard_normal((BATCH, N_CHANNELS, 25, 25), dtype=np.float32)
            scl = rng.standard_normal((BATCH, n_scalar), dtype=np.float32)
            msk = np.ones((BATCH, A), dtype=bool)
            t = time.perf_counter()
            handles.request_q.put(EvalRequest(0, i, obs, scl, msk))
            handles.response_q.get(timeout=30)
            lat.append((time.perf_counter() - t) * 1000)
        lat = np.array(lat)
        per_fwd_ms = float(np.median(lat))
        fwds_per_move = SIMS / BATCH
        # a self-play game is ~70 moves; each move = sims/batch SEQUENTIAL round-trips
        game_s = per_fwd_ms / 1000 * fwds_per_move * 70
        print(f"\n=== single-client round-trip latency (batch={BATCH}, obs {BATCH}x{N_CHANNELS}x25x25 = {BATCH*N_CHANNELS*625*4/1e6:.2f} MB) ===")
        print(f"  per-forward round-trip: median={per_fwd_ms:.2f} ms  mean={lat.mean():.2f}  p90={np.percentile(lat,90):.2f}  min={lat.min():.2f}")
        print(f"  -> {fwds_per_move:.0f} sequential forwards/move x 70 moves = ~{game_s:.0f}s/game/worker (1 client, no GPU contention)")
        print(f"  (orch-off completes a game in ~117s/worker; >{game_s:.0f}s here even uncontended explains the 0-games window)")
        return 0
    finally:
        try:
            proc.send_signal(signal.SIGINT); proc.wait(timeout=5)
        except Exception:
            proc.kill()
        logf.close()


if __name__ == "__main__":
    raise SystemExit(main())
