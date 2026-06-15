"""Validate the carc-orch shared-memory transport in isolation: parity vs the
local net + per-forward round-trip latency (expect ~1-2ms vs the TCP path's
24ms). Starts the server in --transport shm and drives it via connect_shm.
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
from carcassonne_ai.shm_eval_handles import connect_shm

CKPT = "/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt"
TS = "/tmp/carc_iter8.ts.pt"
SERVER = "/home/doctor/projects/carcassone/rust/carc-orch/run_server.sh"
NAME = "testshm"
LOG = "/tmp/carc_orch_shm_test.log"
TOL_P, TOL_V = 1e-4, 1e-3
BATCH = 8
SIMS = 200


def main() -> int:
    # clean stale shm
    try:
        Path(f"/dev/shm/carc_{NAME}").unlink()
    except FileNotFoundError:
        pass
    logf = open(LOG, "w")
    proc = subprocess.Popen(
        [SERVER, "--model", TS, "--transport", "shm", "--shm-name", NAME,
         "--workers", "4", "--n-scalar", "12", "--device", "cuda"],
        stdout=subprocess.DEVNULL, stderr=logf, text=True)
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            if proc.poll() is not None:
                sys.stderr.write(Path(LOG).read_text()); raise RuntimeError("server died")
            if Path(LOG).exists() and "READY" in Path(LOG).read_text():
                break
            time.sleep(0.2)
        print("[shm] server READY")

        device = torch.device("cuda")
        ckpt = torch.load(CKPT, map_location=device, weights_only=False)
        n_scalar = int(ckpt.get("n_scalar_features", 10))
        net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"],
                             n_scalar_features=n_scalar).to(device)
        net.load_state_dict(ckpt["model_state"]); net.train(False)
        with torch.no_grad():
            A = net(torch.zeros(1, N_CHANNELS, 25, 25, device=device),
                    torch.zeros(1, n_scalar, device=device))[0].shape[1]
        print(f"[shm] net: C={N_CHANNELS} S={n_scalar} A={A}")

        h = connect_shm(NAME, 0, n_scalar)
        rng = np.random.default_rng(0)

        # --- parity ---
        ok = True
        for rid, k in enumerate([1, 4, 8]):
            obs = rng.standard_normal((k, N_CHANNELS, 25, 25), dtype=np.float32)
            scl = rng.standard_normal((k, n_scalar), dtype=np.float32)
            mask = rng.random((k, A)) > 0.5
            mask[:, 0] = True
            with torch.no_grad():
                lg, val = net(torch.from_numpy(obs).to(device), torch.from_numpy(scl).to(device))
                pri_ref = net.policy_softmax_with_mask(lg, torch.from_numpy(mask).to(device)).cpu().numpy()
                val_ref = val.cpu().numpy()
            h.request_q.put(EvalRequest(0, rid, obs, scl, mask))
            resp = h.response_q.get(timeout=30)
            shape_ok = resp.priors.shape == (k, A) and resp.values.shape == (k,)
            dp = float(np.abs(pri_ref - resp.priors).max()) if shape_ok else float("nan")
            dv = float(np.abs(val_ref - resp.values).max()) if shape_ok else float("nan")
            good = shape_ok and dp < TOL_P and dv < TOL_V
            ok = ok and good
            print(f"  parity k={k}: dpriors={dp:.2e} dvalue={dv:.2e} {'OK' if good else 'FAIL'}")
        if not ok:
            print("[shm] PARITY FAILED"); return 1

        # --- latency ---
        for _ in range(10):
            obs = rng.standard_normal((BATCH, N_CHANNELS, 25, 25), dtype=np.float32)
            scl = rng.standard_normal((BATCH, n_scalar), dtype=np.float32)
            msk = np.ones((BATCH, A), dtype=bool)
            h.request_q.put(EvalRequest(0, 0, obs, scl, msk)); h.response_q.get(timeout=30)
        lat = []
        for i in range(300):
            obs = rng.standard_normal((BATCH, N_CHANNELS, 25, 25), dtype=np.float32)
            scl = rng.standard_normal((BATCH, n_scalar), dtype=np.float32)
            msk = np.ones((BATCH, A), dtype=bool)
            t = time.perf_counter()
            h.request_q.put(EvalRequest(0, i, obs, scl, msk))
            h.response_q.get(timeout=30)
            lat.append((time.perf_counter() - t) * 1000)
        lat = np.array(lat)
        med = float(np.median(lat))
        game_s = med / 1000 * (SIMS / BATCH) * 70
        print(f"\n[shm] PARITY PASS")
        print(f"[shm] round-trip: median={med:.2f}ms mean={lat.mean():.2f} p90={np.percentile(lat,90):.2f} min={lat.min():.2f}")
        print(f"[shm] -> ~{game_s:.0f}s/game/worker uncontended  (TCP was 24ms -> 42s; orch-off ~117s)")
        return 0
    finally:
        try:
            proc.send_signal(signal.SIGINT); proc.wait(timeout=5)
        except Exception:
            proc.kill()
        logf.close()
        try:
            Path(f"/dev/shm/carc_{NAME}").unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
