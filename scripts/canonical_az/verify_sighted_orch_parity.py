"""PARITY GATE for the sighted (81ch/42-scalar) carc-orch SHM path (M2, Task A4).

Proves the carc-orch SHM forward on a SIGHTED net matches the orch-OFF eager
forward bit-close, on a batch of REAL featurized positions — the same parity
discipline as export_torchscript's gate, but end-to-end through the Rust
orchestrator instead of only the TorchScript trace. A silently-wrong orch would
corrupt the whole M2 dataset, so this must pass before any sighted orch gen/eval.

What it does:
  1. Load the sighted net eager (GPU); play random moves in a Game(sighted=True)
     to collect real 81ch/42-scalar boards.
  2. eager ref: net(obs,scalars) -> policy_softmax_with_mask + value head.
  3. Export the net -> TorchScript (parity-gated internally), launch
     `carc-orch --transport shm --n-ch 81 --n-scalar 42`, connect a SHM client,
     forward the SAME boards through make_remote_batch_evaluator.
  4. Compare max|dpriors| / max|dvalue| across several batch sizes; PASS iff all
     within the export tolerances (priors 5e-4, value 5e-3 — fp32 batch-stacking
     + cudnn-algo noise, ~200-1000x below a real logic error).

Usage:
  PYTHONPATH=src .venv/bin/python scripts/canonical_az/verify_sighted_orch_parity.py \
      --checkpoint <sighted.pt> [--n 64] [--workers 2]
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.network import CarcassonneNet  # noqa: E402
from carcassonne_ai.remote_evaluators import make_remote_batch_evaluator  # noqa: E402
from carcassonne_ai.shm_eval_handles import connect_shm  # noqa: E402

# Same bars as export_torchscript (fp32 batch-stacking + cudnn-algo noise).
_TOL_PRIORS = 5e-4
_TOL_VALUE = 5e-3


def _load_net(path: str, device):
    ck = torch.load(path, map_location=device, weights_only=False)
    n_ch = int(ck.get("n_input_channels", 78))
    n_scalar = int(ck.get("n_scalar_features", 10))
    sighted = bool(ck.get("sighted", False))
    net = CarcassonneNet(
        n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
        n_input_channels=n_ch, n_scalar_features=n_scalar,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    return net, n_ch, n_scalar, sighted


def _collect_boards(game: Game, n: int, seed: int = 0):
    """Play random legal moves across a few games to collect `n` mid-game boards."""
    rng = np.random.default_rng(seed)
    boards = []
    while len(boards) < n:
        b = game.get_init_board()
        # random-length rollout so boards span the game
        steps = int(rng.integers(3, 40))
        for _ in range(steps):
            if game.get_game_ended(b, 0) != 0.0:
                break
            legal = np.flatnonzero(game.get_valid_moves(b))
            if len(legal) == 0:
                break
            a = int(rng.choice(legal))
            b, _ = game.get_next_state(b, a)
        if game.get_game_ended(b, 0) == 0.0 and int(game.get_valid_moves(b).sum()) > 0:
            boards.append(b)
    return boards[:n]


def _eager_forward(net, game: Game, boards, device):
    obs = np.stack([game.get_canonical_form(b, b.state.current_player)[0] for b in boards])
    scl = np.stack([game.get_canonical_form(b, b.state.current_player)[1] for b in boards])
    msk = np.stack([game.get_valid_moves(b) for b in boards])
    obs_t = torch.from_numpy(obs).to(device)
    scl_t = torch.from_numpy(scl).to(device)
    msk_t = torch.from_numpy(msk).to(device)
    with torch.no_grad():
        logits, value = net(obs_t, scl_t)
        priors = net.policy_softmax_with_mask(logits, msk_t)
    return priors.cpu().numpy(), value.cpu().numpy().reshape(-1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--n", type=int, default=64, help="total boards to test")
    ap.add_argument("--workers", type=int, default=2, help="orch shm workers")
    ap.add_argument("--shm-name", default="paritychk")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net, n_ch, n_scalar, sighted = _load_net(args.checkpoint, device)
    print(f"[parity] net: n_ch={n_ch} n_scalar={n_scalar} sighted={sighted} device={device}")

    game = Game(enable_legal_moves_cache=True, sighted=sighted,
                include_farm_scalars=((n_scalar > 10) and not sighted))
    boards = _collect_boards(game, args.n)
    print(f"[parity] collected {len(boards)} real boards")

    priors_ref, values_ref = _eager_forward(net, game, boards, device)

    # --- export TS + launch carc-orch shm ---
    ts = Path(f"/tmp/carc_parity_{args.shm_name}.ts.pt")
    srv = REPO / "rust/carc-orch/run_server.sh"
    rc = subprocess.call([str(REPO / ".venv/bin/python"),
                          str(REPO / "scripts/export_torchscript.py"),
                          "--checkpoint", args.checkpoint, "--out", str(ts),
                          "--device", "cuda"])
    if rc != 0:
        print("[parity] FATAL: export/parity failed", file=sys.stderr)
        return 1

    shm_path = f"/dev/shm/carc_{args.shm_name}"
    for f in [shm_path] + list(Path("/dev/shm").glob(f"sem.carc_{args.shm_name}_*")):
        try:
            os.remove(f)
        except OSError:
            pass

    log = Path(f"/tmp/carc_paritysrv_{args.shm_name}.log")
    srv_proc = subprocess.Popen(
        [str(srv), "--model", str(ts), "--transport", "shm",
         "--shm-name", args.shm_name, "--workers", str(args.workers),
         "--n-ch", str(n_ch), "--n-scalar", str(n_scalar),
         "--device", "cuda", "--max-batch", "64", "--batch-timeout-ms", "5.0",
         "--forwarders", "2", "--watchdog-secs", "0"],
        stdout=open(log, "w"), stderr=subprocess.STDOUT)
    try:
        # wait for server ready
        ready = False
        for _ in range(160):
            if log.exists() and "forwarder-" in log.read_text():
                ready = True
                break
            if srv_proc.poll() is not None:
                print(f"[parity] FATAL: carc-orch died early:\n{log.read_text()[-1500:]}",
                      file=sys.stderr)
                return 1
            time.sleep(0.5)
        if not ready:
            print(f"[parity] FATAL: server not ready:\n{log.read_text()[-1500:]}", file=sys.stderr)
            return 1
        print(f"[parity] server ready (n_ch={n_ch} n_scalar={n_scalar})")

        handles = connect_shm(args.shm_name, 0, n_scalar, n_ch)
        orch_eval = make_remote_batch_evaluator(handles, game)

        ok = True
        # (1) Sequential per-request parity. MAX_K=8 boards per request (the MCTS
        # batch_size cap); each call is its own forward through the SHM slot.
        print("[parity] (1) per-request forward (k<=MAX_K=8):")
        for k in (1, 3, 8):
            sub = boards[:k]
            p_ref = priors_ref[:k]
            v_ref = values_ref[:k]
            p_orch, v_orch = orch_eval(sub)
            dp = float(np.abs(p_ref - p_orch).max())
            dv = float(np.abs(v_ref - v_orch).max())
            good = dp < _TOL_PRIORS and dv < _TOL_VALUE
            ok = ok and good
            print(f"    k={k:2d}: max|dpriors|={dp:.2e}  max|dvalue|={dv:.2e}  "
                  f"{'OK' if good else 'FAIL'}")

        # (2) CONCURRENT cross-request stacking. `args.workers` threads each own a
        # SHM slot and fire a k=8 request at the same instant (a barrier), so the
        # collector concatenates them into ONE forward of total_k = 8*W at 81ch —
        # the real orch throughput path (many workers' leaves in one batch). Prove
        # each worker's slice still matches its eager reference.
        import threading
        W = args.workers
        print(f"[parity] (2) concurrent stacking: {W} workers x k=8 -> total_k up to {8*W}:")
        barrier = threading.Barrier(W)
        results: dict[int, tuple] = {}
        # distinct 8-board slice per worker so a mixup would show as a mismatch
        slices = [boards[(w * 8) % (len(boards) - 8): (w * 8) % (len(boards) - 8) + 8]
                  for w in range(W)]

        def _run(w):
            h = connect_shm(args.shm_name, w, n_scalar, n_ch)
            ev = make_remote_batch_evaluator(h, game)
            barrier.wait()
            results[w] = ev(slices[w])

        threads = [threading.Thread(target=_run, args=(w,)) for w in range(W)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for w in range(W):
            p_ref, v_ref = _eager_forward(net, game, slices[w], device)
            p_orch, v_orch = results[w]
            dp = float(np.abs(p_ref - p_orch).max())
            dv = float(np.abs(v_ref - v_orch).max())
            good = dp < _TOL_PRIORS and dv < _TOL_VALUE
            ok = ok and good
            print(f"    worker {w}: max|dpriors|={dp:.2e}  max|dvalue|={dv:.2e}  "
                  f"{'OK' if good else 'FAIL'}")

        print(f"[parity] {'PASS' if ok else 'FAIL'} (tol priors<{_TOL_PRIORS}, value<{_TOL_VALUE})")
        return 0 if ok else 1
    finally:
        srv_proc.send_signal(signal.SIGTERM)
        try:
            srv_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            srv_proc.kill()
        for f in [shm_path] + list(Path("/dev/shm").glob(f"sem.carc_{args.shm_name}_*")):
            try:
                os.remove(f)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
