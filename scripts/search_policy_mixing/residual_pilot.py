"""Phase 3/5 — full-game residual-role pilot (measurement only).

Plays N paired, seat-balanced games between two NeuralMCTS agents that share the
EXACT production config (net policy prior, v2.7 leaf, sims, c_puct) and differ ONLY
in residual_scale. This isolates the net value-head contribution end-to-end:

    --scale-a 0.25  (= ITER8_PROD)   vs   --scale-b 0.0  (= ITER8_NORESID / policy+v2.7 leaf)

Both agents get the SAME net forward (priors + v_nn); the residual_scale=0 wrapper
simply discards v_nn (leaf = tanh(v2.7/15)), so a single net copy / orch server feeds
both. Reuses eval_hybrid_handoff's GameResult + paired-z/elo stats verbatim so the
result sits on the same Level-2 statistic as the hybrid verdict.

NOT production code. No training, no promotion, no champion change. Fresh seed band
(NOT the spent 1.7e9 sealed panel).

Usage (pilot, then scale):
  python -u scripts/search_policy_mixing/residual_pilot.py \
      --scale-a 0.25 --scale-b 0.0 --ckpt <iter8.pt> \
      --n 20 --paired --seed-start 3600000000 --workers 14 \
      --out-root /mnt/c/carc-shared/spm_residual
"""
from __future__ import annotations

import os
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import dataclasses
import json
import socket
import sys
import time
from multiprocessing import get_context
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "level2"))

import torch
from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
from carcassonne_ai.eval_provenance import deck_hash
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.run_manifest import game_tag, write_manifest
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

# reuse the canonical Level-2 stats + result schema (no divergence)
from eval_hybrid_handoff import (GameResult, _paired_z, _summary, _result_path,
                                 _try_load, _save, _build_work, _try_claim)

SIMS = 200
CPUCT = 3.0
_W: dict = {}


class _ScaledIter8:
    """NeuralMCTS: net policy prior + v2.7 leaf with a given residual_scale."""
    def __init__(self, base_eval, game_farm, scale, seed):
        cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=scale)
        leaf = make_v25_value_wrapper(base_eval, cfg)
        self._m = NeuralMCTS(game=game_farm, evaluator=leaf, simulations=SIMS,
                             seed=seed, c_puct=CPUCT)
        self.neural_moves = 0
        self.heur_moves = 0
        self.latch_k = None

    def move(self, board) -> int:
        self._m.clear()
        self.neural_moves += 1
        return int(self._m.best_action(board))


def _worker_init(ckpt, device_str, shared_claim, claim_host, claim_stale_secs,
                 shm_name="", id_q=None, ns=10):
    torch.set_num_threads(1)
    _W.update(shared_claim=shared_claim, claim_host=claim_host,
              claim_stale_secs=claim_stale_secs, net=None, handles=None, orch=False,
              farm=ns > 10)
    if shm_name:
        from carcassonne_ai.shm_eval_handles import connect_shm
        _W["orch"] = True
        _W["dev"] = torch.device("cpu")
        _W["handles"] = connect_shm(shm_name, id_q.get(), ns)
        return
    dev = torch.device(device_str)
    _W["dev"] = dev
    ck = torch.load(ckpt, map_location=dev, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
    net.load_state_dict(ck["model_state"]); net.train(False)
    _W["net"] = net
    _W["farm"] = ns > 10


def _play_one(task):
    out_str, seed, a_seat, scale_a, scale_b = task
    out = Path(out_str)
    p = _result_path(out, seed, a_seat)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale_secs"]):
            return None

    import random
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    dh = deck_hash(board)
    farm = _W.get("farm", False)
    ga = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    gb = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    if _W.get("orch"):
        def base_factory(gf):
            return make_remote_single_evaluator(_W["handles"], gf)
    else:
        def base_factory(gf):
            return make_single_evaluator(_W["net"], _W["dev"], gf)
    a = _ScaledIter8(base_factory(ga), ga, scale_a, seed)
    b = _ScaledIter8(base_factory(gb), gb, scale_b, seed + 1)

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        agent = a if cur == a_seat else b
        action = agent.move(board)
        if not mask[action]:
            raise RuntimeError(f"illegal action {action}")
        board, _ = game.get_next_state(board, action)
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    r = GameResult(seed=seed, a_seat=a_seat,
                   agent_a=f"iter8_resid{scale_a}", agent_b=f"iter8_resid{scale_b}",
                   score_p0=int(s0), score_p1=int(s1), diff=int(diff),
                   won_by_a=(diff > 0), drew=(diff == 0), elapsed_s=elapsed, moves=moves,
                   deck_hash=dh, a_neural_moves=a.neural_moves, b_neural_moves=b.neural_moves)
    _save(p, r)
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(prog="residual_pilot")
    ap.add_argument("--scale-a", type=float, default=0.25)
    ap.add_argument("--scale-b", type=float, default=0.0)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--seed-start", type=int, default=3_600_000_000)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--device", default=("cuda" if torch.cuda.is_available() else "cpu"))
    ap.add_argument("--shm-eval-server", type=str, default=None)
    ap.add_argument("--out-root", type=str, default="/mnt/c/carc-shared/spm_residual")
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=5400)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    args = ap.parse_args(argv)
    if args.paired and args.n % 2:
        ap.error("--paired requires even --n")

    sub = args.out_subdir or f"resid{args.scale_a}__vs__resid{args.scale_b}"
    out = Path(args.out_root) / sub
    out.mkdir(parents=True, exist_ok=True)

    agent_a = f"iter8_resid{args.scale_a}"
    agent_b = f"iter8_resid{args.scale_b}"
    tasks = [(str(out), seed, a_seat, args.scale_a, args.scale_b)
             for seed, a_seat in _build_work(args.seed_start, args.n, args.paired)]

    _ns = 10
    _ck = torch.load(str(args.ckpt), map_location="cpu", weights_only=False)
    _ns = int(_ck.get("n_scalar_features", 10)); del _ck
    write_manifest(out, kind="residual_pilot", game=game_tag(Game()),
                   config={"agent_a": agent_a, "agent_b": agent_b, "ckpt": str(args.ckpt),
                           "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
                           "sims": SIMS, "c_puct": CPUCT, "scale_a": args.scale_a,
                           "scale_b": args.scale_b, "leaf": "v2_7", "orch": args.shm_eval_server,
                           "note": "isolates residual head: same net forward, only residual_scale differs"})

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    print(f"[residual_pilot] {agent_a} vs {agent_b}: n={args.n}, {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, W={args.workers}, device={args.device}, orch={args.shm_eval_server}, out={out}",
          flush=True)

    results = []
    if todo:
        t0 = time.perf_counter()
        ctx = get_context("spawn")
        id_q = None
        if args.shm_eval_server:
            id_q = ctx.Queue()
            for _w in range(args.workers):
                id_q.put(_w)
        with ctx.Pool(processes=args.workers, initializer=_worker_init,
                      initargs=(str(args.ckpt), args.device, args.shared_claim, args.claim_host,
                                args.claim_stale_secs, args.shm_eval_server or "", id_q, _ns)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r); done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, ~{(len(todo)-done)*el/done/60:.0f} min left)", flush=True)
    for t in tasks:
        p = _result_path(out, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_seat == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    if results:
        summ = _summary(results, agent_a, agent_b)
        json.dump(summ, open(out / "summary.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
