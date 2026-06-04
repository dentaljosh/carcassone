#!/usr/bin/env python3
"""GATE (precondition) for the value-target-source rebuild.

Hypothesis: the value head is stuck at ~strong-amateur because it's trained on the noisy
raw-MC game outcome. A lower-variance target -- the MCTS SEARCH VALUE (root.Q after a
v2.7-leaf search, = "v2.7 + lookahead") -- might let a head become a BETTER leaf than v2.7.

This gate tests the PRECONDITION cheaply (no encoding, no head training): is the search
value even a better outcome-predictor than raw v2.7? Plays NeuralMCTS(iter_01) self-play,
and per ply records (search_value root.Q, v2.7 value, final POV margin). Then:

  corr(search_value, margin) >> corr(v2.7, margin)  -> search value carries info v2.7 lacks
       -> a head trained to amortize it could beat v2.7 -> proceed to head-training test.
  corr(search_value, margin) ~= corr(v2.7, margin)  -> search adds nothing over v2.7 at the
       root -> training a head to mimic it won't beat v2.7 -> lever likely dead.

All three quantities are current-player POV; corr is over all plies (+ ply-bucket breakdown).
Run with env CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 (production leaf).
"""
import argparse
import math
from multiprocessing import Pool

import numpy as np
import torch

from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

_net = _device = _include_farm = None
_sims = _cpuct = None


def _init(ckpt, sims, cpuct):
    global _net, _device, _include_farm, _sims, _cpuct
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(ckpt, map_location=_device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    _include_farm = ns > 10
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns).to(_device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    _net = net
    _sims, _cpuct = sims, cpuct


def _play(seed):
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=_include_farm)
    board = game.get_init_board()
    base = make_single_evaluator(_net, _device, game)
    leaf = make_v25_value_wrapper(base)
    mcts = NeuralMCTS(game=game, evaluator=leaf, simulations=_sims, seed=seed, c_puct=_cpuct)
    rec = []  # (search_value, v27_value, player, ply)
    ply = 0
    while game.get_game_ended(board, 0) == 0.0:
        st = board.state
        cur = st.current_player
        mcts.clear()
        mcts.search(board)
        root = mcts._nodes[game.string_representation(board)]
        sv = float(root.Q)                                   # search value, cur-player POV
        v27 = math.tanh(virtual_score_v2(st, cur, DEFAULT_CONFIG) / 15.0)
        rec.append((sv, v27, cur, ply))
        action = mcts.best_action(board)                     # reuses the searched tree
        board, _ = game.get_next_state(board, action)
        ply += 1
    s0, s1 = board.state.scores
    out = []
    for sv, v27, p, ply_i in rec:
        margin = (s0 - s1) if p == 0 else (s1 - s0)
        out.append((sv, v27, float(margin), ply_i))
    return out


def corr(a, b):
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="/mnt/c/carc-shared/stage_b/ckpt/iter_01.pt")
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed-start", type=int, default=900000)
    a = ap.parse_args()
    seeds = list(range(a.seed_start, a.seed_start + a.games))
    print(f"generating {a.games} games (sims={a.sims}, W={a.workers}) ...")
    recs = []
    with Pool(a.workers, initializer=_init, initargs=(a.checkpoint, a.sims, a.c_puct)) as pool:
        for i, r in enumerate(pool.imap_unordered(_play, seeds), 1):
            recs.extend(r)
            if i % 5 == 0 or i == a.games:
                print(f"  {i}/{a.games} games, {len(recs)} positions")
    sv = np.array([r[0] for r in recs])
    v27 = np.array([r[1] for r in recs])
    mg = np.array([r[2] for r in recs])
    ply = np.array([r[3] for r in recs])
    print(f"\n{len(recs)} positions. metric = corr(estimator, true POV margin); higher = better\n")
    print(f"  v2.7 value     : corr = {corr(v27, mg):+.3f}")
    print(f"  search value   : corr = {corr(sv, mg):+.3f}   (root.Q, sims={a.sims})")
    # win/loss sign agreement
    print(f"\n  sign-accuracy (predict who's ahead):")
    print(f"    v2.7   : {np.mean(np.sign(v27) == np.sign(mg)):.3f}")
    print(f"    search : {np.mean(np.sign(sv) == np.sign(mg)):.3f}")
    # late-game (ply>=80) where it matters most
    late = ply >= 80
    if late.sum() > 10:
        print(f"\n  late game (ply>=80, n={int(late.sum())}):")
        print(f"    v2.7   corr = {corr(v27[late], mg[late]):+.3f}")
        print(f"    search corr = {corr(sv[late], mg[late]):+.3f}")


if __name__ == "__main__":
    main()
