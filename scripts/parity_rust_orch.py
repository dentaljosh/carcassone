"""End-to-end parity: drive the Rust carc-orch server through the REAL Python
socket client (remote_socket_handles.connect_remote) and compare its
(priors, values) against the local eager net eval on byte-identical inputs.

Validates the whole Rust path — npy decode, cross-request concat, CUDA forward,
masked softmax, npy encode, framing — not just the model (export_torchscript.py
already proved the traced graph vs eager). Diffs should be fp32 batch-noise
(<1e-4 priors, <1e-3 value); anything larger means a wire/shape/transpose bug.
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
PORT = 53917
SERVER = "/home/doctor/projects/carcassone/rust/carc-orch/run_server.sh"
LOG = "/tmp/carc_orch_parity_server.log"
TOL_P, TOL_V = 1e-4, 1e-3


def _wait_ready(proc, log_path, timeout=90.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            sys.stderr.write(Path(log_path).read_text())
            raise RuntimeError(f"server exited early (code {proc.returncode})")
        txt = Path(log_path).read_text() if Path(log_path).exists() else ""
        if "READY" in txt:
            return
        time.sleep(0.2)
    raise RuntimeError("server did not become READY in time")


def main() -> int:
    logf = open(LOG, "w")
    proc = subprocess.Popen(
        [SERVER, "--model", TS, "--port", str(PORT), "--device", "cuda"],
        stdout=subprocess.DEVNULL, stderr=logf, text=True,
    )
    try:
        _wait_ready(proc, LOG)
        print(f"[parity] server READY on :{PORT}")

        device = torch.device("cuda")
        ckpt = torch.load(CKPT, map_location=device, weights_only=False)
        n_scalar = int(ckpt.get("n_scalar_features", 10))
        net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"],
                             n_scalar_features=n_scalar).to(device)
        net.load_state_dict(ckpt["model_state"]); net.train(False)
        with torch.no_grad():
            A = net(torch.zeros(1, N_CHANNELS, 25, 25, device=device),
                    torch.zeros(1, n_scalar, device=device))[0].shape[1]
        print(f"[parity] net loaded: C={N_CHANNELS} S={n_scalar} A={A}")

        handles = connect_remote("127.0.0.1", PORT, 0)
        rng = np.random.default_rng(0)
        ok = True
        for rid, k in enumerate([1, 4, 8, 37, 200]):
            obs = rng.standard_normal((k, N_CHANNELS, 25, 25), dtype=np.float32)
            scl = rng.standard_normal((k, n_scalar), dtype=np.float32)
            mask = rng.random((k, A)) > 0.5
            mask[:, 0] = True  # guarantee a legal action so softmax isn't all -inf
            with torch.no_grad():
                logits, val = net(torch.from_numpy(obs).to(device),
                                  torch.from_numpy(scl).to(device))
                pri_ref = net.policy_softmax_with_mask(
                    logits, torch.from_numpy(mask).to(device)).cpu().numpy()
                val_ref = val.cpu().numpy()
            handles.request_q.put(EvalRequest(worker_id=0, request_id=rid,
                                              obs=obs, scalars=scl, mask=mask))
            resp = handles.response_q.get(timeout=30)
            shape_ok = resp.priors.shape == (k, A) and resp.values.shape == (k,)
            dp = float(np.abs(pri_ref - resp.priors).max()) if shape_ok else float("nan")
            dv = float(np.abs(val_ref - resp.values).max()) if shape_ok else float("nan")
            good = shape_ok and dp < TOL_P and dv < TOL_V
            ok = ok and good
            print(f"  k={k:4d}: shapes={resp.priors.shape},{resp.values.shape} "
                  f"max|dpriors|={dp:.2e} max|dvalue|={dv:.2e} {'OK' if good else 'FAIL'}")
        print(f"\n[parity] {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
    finally:
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        logf.close()
        print("[parity] server stats tail:")
        tail = Path(LOG).read_text().splitlines()[-4:]
        print("\n".join("    " + ln for ln in tail))


if __name__ == "__main__":
    raise SystemExit(main())
