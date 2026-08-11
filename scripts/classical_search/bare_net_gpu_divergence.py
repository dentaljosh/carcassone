"""Does moving the bare-net anchor's forwards CPU -> GPU change the AGENT?

`eval_fair_puct.py --opponent bare-net` can serve the RoD-v2 anchor's net either from
a per-worker CPU net (the historical path — every `net:<ckpt>` anchor row in
experiments/results.csv was played that way) or from the carc-orch SHM GPU server
(`--opp-orch-shm-name`, ~an order of magnitude faster). Weights, leaf, sims, c_puct,
residual_scale and clairvoyance are IDENTICAL across the two; only the float reduction
order differs (CPU fp32 vs CUDA fp32, plus TorchScript trace vs eager). That is ~1e-6
noise per forward — but a 200-sim PUCT search amplifies it, and a near-tied argmax can
flip. Whether that matters is an EMPIRICAL question, so measure it instead of asserting
either way.

WHAT THIS MEASURES, on REAL root positions drawn from REAL cell games (our blind fair
champion vs the anchor, the exact `--opponent bare-net` loop):

  1. DECISION divergence — the fraction of anchor-to-move positions where the CPU
     agent and the GPU agent pick a DIFFERENT action, everything else identical
     (same board, same seed, same cleared tree, same 200 sims). This is the number
     that decides whether a GPU-transport cell may be cited against a CPU-transport
     anchor row.
  2. Raw forward divergence at those roots — max|dpriors|, |dvalue|, and whether the
     net's own policy argmax flips. (Root only: the leaves deeper in the tree are
     where most of the amplification happens, so this UNDERSTATES the per-forward
     divergence budget the search is exposed to. The decision rate in (1) already
     includes that amplification, so it is the load-bearing figure.)
  3. The DECISION MARGIN at divergent positions — the CPU search's top-2 (Q, N) gap.
     If divergences sit only on near-ties, they are numerically-inevitable coin flips
     between near-equal moves; if they sit on wide margins, something is wrong with
     the transport, not with float arithmetic.

The game is driven by the CPU agent's choice, so the trajectory is the historical
(CPU) one and the GPU agent is a pure probe.

------------------------------------------------------------------------------
MEASURED 2026-07-27 — RoD-v2 iter_02, k4x344 candidate, K=2, 4 games, band 99e9
------------------------------------------------------------------------------
    positions (anchor to move)              140
    CHOSEN ACTION differs                   0   (0.0%)
    raw net policy ARGMAX differs (root)    0   (0.0%)
    max|dpriors| per root forward   med/p95/max   3.82e-05 / 1.37e-04 / 2.49e-04
    |dvalue|     per root forward   med/p95/max   7.73e-06 / 3.12e-05 / 6.14e-05
    top-2 Q gap at all positions    median        0.0168

Corroborated end-to-end: a 4-game n=4 cell run BOTH ways (same seeds, same band)
produced per-game results identical in every non-timing field — scores, diff,
moves, deck_hash, latch_k, prefix/exact move counts — i.e. four complete games of
identical play, not merely identical summary statistics.

READ IT HONESTLY: 0/140 is not proof of 0. By the rule of three the 95% upper
bound on the per-move divergence rate is ~2.1%; at ~35 anchor moves per game that
still admits up to ~1 flipped move in some games. What the measurement DOES
establish is that divergence is not common enough to see at n=140, that the raw
forward noise (<=2.5e-04 on priors, <=6.1e-05 on value) is 3-4 orders of magnitude
below the median top-2 decision margin (1.7e-02), and that no observed decision
sat close enough to a tie for that noise to move it. Disclose the transport in the
cell write-up; do not claim bit-identity.

Usage (launches and tears down its own carc-orch server):
    .venv/bin/python scripts/classical_search/bare_net_gpu_divergence.py \
        --opp-net /mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt --games 4

⚠️ Single-process and CPU-heavy on the champion side (~1-2 s/move at k4x344). Size
   --games to the time you have; --sims/--k-dets default to the production cell.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))          # endgame_solver
sys.path.insert(0, str(Path(__file__).resolve().parent))      # sibling harness

# ⚠️ Import order matters: eval_fair_puct pins the leaf env (and CUDA_VISIBLE_DEVICES="")
# at import, BEFORE carcassonne_ai loads. We want exactly the harness's leaf, so import
# it first and take every construction from it rather than re-deriving anything.
import eval_fair_puct as E  # noqa: E402

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.shm_eval_handles import connect_shm  # noqa: E402


def _server_env() -> dict:
    """Env for the carc-orch child.

    ⚠️ TWO corrections to our own process env, both load-bearing:
      * DROP CUDA_VISIBLE_DEVICES — eval_fair_puct's _CANON_ENV sets it to "" at
        import, and a child inherits it, which would leave the server with NO GPU
        (it would abort, or worse, quietly run CPU under --allow-cpu).
      * PIN OMP/MKL to 1 — the Rust side never calls set_num_threads, so libtorch
        sizes its intra-op pool to core count and OpenMP spin-waits (measured 2574%
        CPU for the server vs 367% for all workers). Pinning our own process does
        nothing for it; this env is what the server actually gets.
    """
    env = dict(os.environ)
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    return env


def _start_server(ckpt: str, rep: dict, shm_name: str, workers: int, max_batch: int):
    """Export -> TorchScript (parity-gated) and launch carc-orch on CUDA. Returns
    (proc, log_path) or raises."""
    ts = Path(f"/tmp/carc_bndiv_{shm_name}.ts.pt")
    rc = subprocess.call(
        [str(REPO / ".venv/bin/python"), str(REPO / "scripts/export_torchscript.py"),
         "--checkpoint", ckpt, "--out", str(ts), "--device", "cuda"],
        env=_server_env())
    if rc != 0:
        raise SystemExit("FATAL: TorchScript export/parity gate failed")

    for f in [Path(f"/dev/shm/carc_{shm_name}"), *Path("/dev/shm").glob(f"sem.carc_{shm_name}_*")]:
        try:
            os.remove(f)
        except OSError:
            pass

    log = Path(f"/tmp/carc_bndivsrv_{shm_name}.log")
    proc = subprocess.Popen(
        [str(REPO / "rust/carc-orch/run_server.sh"), "--model", str(ts),
         "--transport", "shm", "--shm-name", shm_name, "--workers", str(workers),
         "--n-ch", str(rep["n_input_channels"]), "--n-scalar", str(rep["n_scalar_features"]),
         "--device", "cuda", "--max-batch", str(max_batch), "--batch-timeout-ms", "2.0",
         "--forwarders", "2", "--watchdog-secs", "0"],
        stdout=open(log, "w"), stderr=subprocess.STDOUT, env=_server_env())
    for _ in range(160):
        if log.exists() and "forwarder-" in log.read_text():
            return proc, log
        if proc.poll() is not None:
            raise SystemExit(f"FATAL: carc-orch died early:\n{log.read_text()[-2000:]}")
        time.sleep(0.5)
    raise SystemExit(f"FATAL: carc-orch not ready:\n{log.read_text()[-2000:]}")


def _gpu_mem_mib() -> float | None:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True, env=_server_env())
        return float(out.strip().splitlines()[0])
    except Exception:
        return None


def _root_ranking(mcts, board):
    """The CPU search's root children as [(action, N, signed_Q)] sorted the way
    NeuralMCTS.best_action sorts them. Used only to size the decision MARGIN."""
    key = mcts.game.string_representation(board)
    root = mcts._nodes.get(key)
    if root is None:
        return []
    out = []
    for a, child in mcts._deduped_children(root):
        if child.N <= 0:
            continue
        q = child.Q if child.player_to_move == root.player_to_move else -child.Q
        out.append((int(a), int(child.N), float(q)))
    out.sort(key=lambda t: (t[2], t[1]), reverse=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opp-net", required=True, help="the bare-net anchor checkpoint")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--max-positions", type=int, default=0,
                    help="stop after this many anchor-to-move positions (0 = no cap)")
    ap.add_argument("--sims", type=int, default=344, help="CANDIDATE per-det sims")
    ap.add_argument("--k-dets", type=int, default=4, help="CANDIDATE determinizations")
    ap.add_argument("--exact-k", type=int, default=2, help="CANDIDATE endgame tail")
    ap.add_argument("--seed-start", type=int, default=99_000_000_000,
                    help="probe band — NOT an eval band (these games are not scored)")
    ap.add_argument("--shm-name", default=f"bndiv{os.uname().nodename}")
    ap.add_argument("--json-out", default="", help="optional path for the raw record")
    args = ap.parse_args()

    # --- both sides' leaves, from the harness (never re-derived here) ---
    opp_leaf_cfg = E._bare_net_leaf_cfg()
    cand_leaf_cfg = E._curve125_leaf_cfg()
    prov = E._assert_bare_net_leaf(opp_leaf_cfg, cand_cfg=cand_leaf_cfg)
    cand_cfg = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, cand_leaf_cfg)
    print(f"[div] anchor leaf={prov['leaf_hash']}  candidate leaf="
          f"{E._leaf_hash(cand_leaf_cfg)}  (differ: "
          f"{prov['leaf_hash'] != E._leaf_hash(cand_leaf_cfg)})")

    net, rep = E._load_net_rep(args.opp_net, device="cpu")
    import torch
    torch.set_num_threads(1)
    print(f"[div] anchor rep={'SIGHTED' if rep['sighted'] else 'NON-SIGHTED'} "
          f"{rep['n_input_channels']}ch/{rep['n_scalar_features']}sc  "
          f"sims={E.BARE_NET_SIMS} c_puct={E.BARE_NET_CPUCT:g} "
          f"rs={E.BARE_NET_RESIDUAL_SCALE:g}")

    mem_before = _gpu_mem_mib()
    proc, log = _start_server(args.opp_net, rep, args.shm_name, workers=2, max_batch=8)
    try:
        mem_after = _gpu_mem_mib()
        if mem_before is not None and mem_after is not None:
            print(f"[div] GPU memory.used {mem_before:.0f} -> {mem_after:.0f} MiB "
                  f"(delta {mem_after - mem_before:+.0f} MiB) — the net is on the GPU")
        handles = connect_shm(args.shm_name, 0, int(rep["n_scalar_features"]),
                              int(rep["n_input_channels"]))

        # raw per-forward probes (root only), one per transport, on a shared encoder
        from carcassonne_ai.evaluators import make_single_evaluator
        from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
        enc = Game(enable_legal_moves_cache=True, sighted=bool(rep["sighted"]),
                   include_farm_scalars=bool(rep.get(
                       "include_farm_scalars", int(rep["n_scalar_features"]) > 10)))
        raw_cpu = make_single_evaluator(net, torch.device("cpu"), enc)
        raw_gpu = make_remote_single_evaluator(
            connect_shm(args.shm_name, 1, int(rep["n_scalar_features"]),
                        int(rep["n_input_channels"])), enc)

        recs = []
        t0 = time.perf_counter()
        for g in range(args.games):
            seed = args.seed_start + g
            a_seat = g % 2                      # the CANDIDATE's seat, alternating
            random.seed(seed)
            game = Game(enable_legal_moves_cache=True)
            board = game.get_init_board()
            champ = E._make_champion("fair", cand_cfg, args.sims, args.k_dets,
                                     args.exact_k, seed,
                                     Game(enable_legal_moves_cache=True))
            # SAME seed on both transports (seed+1, exactly as _make_opponent does), so
            # the only difference between the two agents is where the forward runs.
            opp_cpu = E._make_bare_net_opponent(net, rep, seed + 1, leaf_cfg=opp_leaf_cfg)
            opp_gpu = E._make_bare_net_opponent(None, rep, seed + 1, leaf_cfg=opp_leaf_cfg,
                                                handles=handles)
            assert opp_cpu.mcts.fair_chance is False and opp_gpu.mcts.fair_chance is False
            assert E._leaf_hash(opp_gpu.leaf_cfg) == E._leaf_hash(opp_cpu.leaf_cfg)

            while game.get_game_ended(board, 0) == 0.0:
                if board.state.current_player == a_seat:
                    board, _ = game.get_next_state(board, champ.move(board))
                    continue
                # --- the probe: one anchor-to-move position, both transports ---
                a_cpu = opp_cpu.move(board)
                rank = _root_ranking(opp_cpu.mcts, board)
                a_gpu = opp_gpu.move(board)
                p_c, v_c = raw_cpu(board)
                p_g, v_g = raw_gpu(board)
                margin_q = (rank[0][2] - rank[1][2]) if len(rank) > 1 else None
                margin_n = (rank[0][1] - rank[1][1]) if len(rank) > 1 else None
                recs.append({
                    "game": g, "seed": seed, "move_no": len(recs),
                    "n_legal": int(game.get_valid_moves(board).sum()),
                    "a_cpu": int(a_cpu), "a_gpu": int(a_gpu),
                    "agree": bool(a_cpu == a_gpu),
                    "d_priors_max": float(np.abs(p_c - p_g).max()),
                    "d_value_abs": float(abs(v_c - v_g)),
                    "raw_argmax_cpu": int(np.argmax(p_c)),
                    "raw_argmax_gpu": int(np.argmax(p_g)),
                    "raw_argmax_agree": bool(int(np.argmax(p_c)) == int(np.argmax(p_g))),
                    "top2_q_gap": margin_q, "top2_n_gap": margin_n,
                    "root_children": len(rank),
                })
                board, _ = game.get_next_state(board, a_cpu)
                if args.max_positions and len(recs) >= args.max_positions:
                    break
            el = time.perf_counter() - t0
            print(f"[div] game {g+1}/{args.games}: {len(recs)} positions so far, "
                  f"{el/60:.1f} min elapsed", flush=True)
            if args.max_positions and len(recs) >= args.max_positions:
                break

        # ------------------------------- report ------------------------------- #
        n = len(recs)
        if n == 0:
            print("[div] no positions collected")
            return 1
        dis = [r for r in recs if not r["agree"]]
        raw_dis = [r for r in recs if not r["raw_argmax_agree"]]
        dp = np.array([r["d_priors_max"] for r in recs])
        dv = np.array([r["d_value_abs"] for r in recs])
        qg = np.array([r["top2_q_gap"] for r in recs if r["top2_q_gap"] is not None])
        qg_dis = np.array([r["top2_q_gap"] for r in dis if r["top2_q_gap"] is not None])

        print("\n" + "=" * 72)
        print("CPU vs GPU decision divergence — bare-net anchor (same weights)")
        print("=" * 72)
        print(f"positions (anchor to move, real cell games) : {n}")
        print(f"CHOSEN ACTION differs                       : {len(dis)}  "
              f"({100.0*len(dis)/n:.1f}%)")
        print(f"raw net policy ARGMAX differs (at root)     : {len(raw_dis)}  "
              f"({100.0*len(raw_dis)/n:.1f}%)")
        print(f"max|dpriors| per root forward   median/p95/max : "
              f"{np.median(dp):.2e} / {np.quantile(dp, 0.95):.2e} / {dp.max():.2e}")
        print(f"|dvalue|     per root forward   median/p95/max : "
              f"{np.median(dv):.2e} / {np.quantile(dv, 0.95):.2e} / {dv.max():.2e}")
        if qg.size:
            print(f"top-2 Q gap at ALL positions   median        : {np.median(qg):.4f}")
        if qg_dis.size:
            print(f"top-2 Q gap at DIVERGENT ones  median/max    : "
                  f"{np.median(qg_dis):.4f} / {qg_dis.max():.4f}")
        elif dis:
            print("top-2 Q gap at DIVERGENT ones  : n/a (single-child roots)")
        print("=" * 72)
        print("Read: the raw-forward diffs size the NOISE; the CHOSEN ACTION rate is\n"
              "the amplified effect after 200 PUCT sims and is the figure to disclose.\n"
              "Divergences concentrated on small top-2 gaps = coin flips between\n"
              "near-equal moves (elo-neutral in expectation). A rate that is large OR\n"
              "sits on wide margins means the GPU cell is a different agent and must\n"
              "not be pooled with CPU-transport anchor rows.")
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(
                {"n": n, "n_action_diff": len(dis), "n_raw_argmax_diff": len(raw_dis),
                 "opp_net": args.opp_net, "sims": E.BARE_NET_SIMS,
                 "records": recs}, indent=2))
            print(f"[div] wrote {args.json_out}")
        return 0
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        for f in [Path(f"/dev/shm/carc_{args.shm_name}"),
                  *Path("/dev/shm").glob(f"sem.carc_{args.shm_name}_*")]:
            try:
                os.remove(f)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
