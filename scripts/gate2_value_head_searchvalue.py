#!/usr/bin/env python3
"""GATE-2 (definitive) for the value-target-source lever.

The value head OVERFITS: trained on the game OUTCOME (one label per game shared across
~144 positions) it hits corr 0.79 train / 0.32 held-out << v2.7 ~0.65 -> hurts in search.
The MCTS SEARCH VALUE (root.Q) is distinct PER POSITION (~100x more independent labels).

This gate generates games recording per ply {features (obs,scalars), search-value root.Q,
outcome margin, v2.7 value}, then trains the SAME deep CNN on two targets and compares
HELD-OUT (by-game split) generalization:
  - OUTCOME target  (current approach; expected to overfit, ~0.32-0.5 held-out)
  - SEARCH-VALUE target (per-position; the lever)
vs v2.7's held-out corr (~0.65). If the search-value head generalizes >> outcome head
(and approaches/beats v2.7) -> per-position targets fix the overfitting -> the lever
works -> justify the full self-play retrain with search-value targets.

Generation is cached to <gen-dir>/seed_*.npz (reuse on re-run). Phase 1 is the slow part
(both-sides NeuralMCTS self-play); Phase 2 (training) is fast.
Run with env CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12.
"""
import argparse
import glob
import math
import os
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

_net = _device = _include_farm = _sims = _cpuct = _gendir = None


def _init(ckpt, sims, cpuct, gendir):
    global _net, _device, _include_farm, _sims, _cpuct, _gendir
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(ckpt, map_location=_device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    _include_farm = ns > 10
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns).to(_device)
    net.load_state_dict(ck["model_state"]); net.train(False)
    _net = net; _sims = sims; _cpuct = cpuct; _gendir = gendir


def _gen_one(seed):
    out = Path(_gendir) / f"seed_{seed:06d}.npz"
    if out.exists():
        return str(out)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=_include_farm)
    board = game.get_init_board()
    base = make_single_evaluator(_net, _device, game)
    leaf = make_v25_value_wrapper(base)
    mcts = NeuralMCTS(game=game, evaluator=leaf, simulations=_sims, seed=seed, c_puct=_cpuct)
    obs_l, sc_l, sv_l, v27_l, pl_l = [], [], [], [], []
    while game.get_game_ended(board, 0) == 0.0:
        st = board.state; cur = st.current_player
        obs, scalars = game.get_canonical_form(board, cur)
        mcts.clear(); mcts.search(board)
        root = mcts._nodes[game.string_representation(board)]
        obs_l.append(obs.astype(np.float32)); sc_l.append(scalars.astype(np.float32))
        sv_l.append(float(root.Q))
        v27_l.append(math.tanh(virtual_score_v2(st, cur, DEFAULT_CONFIG) / 15.0))
        pl_l.append(cur)
        board, _ = game.get_next_state(board, mcts.best_action(board))
    s0, s1 = board.state.scores
    pl = np.array(pl_l)
    margin = np.where(pl == 0, s0 - s1, s1 - s0).astype(np.float32)
    np.savez(out, boards=np.stack(obs_l), scalars=np.stack(sc_l),
             search_value=np.array(sv_l, np.float32), v27=np.array(v27_l, np.float32),
             margin=margin)
    return str(out)


class ValCNN(nn.Module):
    def __init__(self, in_ch, ns=12):
        super().__init__()
        self.c = nn.Sequential(
            nn.Conv2d(in_ch, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1))
        self.h = nn.Sequential(nn.Linear(64 + ns, 64), nn.ReLU(), nn.Linear(64, 1), nn.Tanh())

    def forward(self, b, s):
        return self.h(torch.cat([self.c(b).flatten(1), s], 1)).squeeze(1)


def corr(a, b):
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def train_eval(games, tr, va, target_key, scale, seed, dev, epochs):
    torch.manual_seed(seed)
    def pk(idx):
        B = np.concatenate([games[i]["boards"] for i in idx])
        S = np.concatenate([games[i]["scalars"] for i in idx])
        mg = np.concatenate([games[i]["margin"] for i in idx])
        if target_key == "outcome":
            t = np.tanh(mg / 15.0).astype(np.float32)
        else:  # search_value
            t = np.concatenate([games[i]["search_value"] for i in idx]).astype(np.float32)
        return (torch.from_numpy(B).to(dev), torch.from_numpy(S).to(dev),
                torch.from_numpy(t).to(dev), mg)
    Btr, Str, Ttr, _ = pk(tr); Bva, Sva, _, mva = pk(va)
    net = ValCNN(Btr.shape[1]).to(dev); opt = torch.optim.Adam(net.parameters(), 1e-3)
    lf = nn.MSELoss(); n = Btr.shape[0]
    for _ in range(epochs):
        net.train(); perm = torch.randperm(n, device=dev)
        for i in range(0, n, 256):
            j = perm[i:i + 256]; opt.zero_grad(); lf(net(Btr[j], Str[j]), Ttr[j]).backward(); opt.step()
    net.eval()
    with torch.no_grad():
        pred = net(Bva, Sva).cpu().numpy()
    return corr(pred, mva)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="/mnt/c/carc-shared/stage_b/ckpt/iter_01.pt")
    ap.add_argument("--gen-dir", default="/mnt/c/carc-shared/vts_gen")
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--seed-start", type=int, default=910000)
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    Path(a.gen_dir).mkdir(parents=True, exist_ok=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    seeds = list(range(a.seed_start, a.seed_start + a.games))
    have = len(glob.glob(f"{a.gen_dir}/seed_*.npz"))
    if have < a.games:
        print(f"PHASE 1 generate: {have}/{a.games} cached, generating rest (sims={a.sims}, W={a.workers}) ...")
        with Pool(a.workers, initializer=_init, initargs=(a.checkpoint, a.sims, a.c_puct, a.gen_dir)) as pool:
            for i, _ in enumerate(pool.imap_unordered(_gen_one, seeds), 1):
                if i % 5 == 0 or i == a.games:
                    print(f"  {i}/{a.games} games")
    files = sorted(glob.glob(f"{a.gen_dir}/seed_*.npz"))[:a.games]
    games = [dict(np.load(f)) for f in files]
    npos = sum(len(g["margin"]) for g in games)
    print(f"\nPHASE 2 train: {len(games)} games, {npos} positions, dev={dev}")
    rng = np.random.default_rng(0); order = rng.permutation(len(games))
    cut = int(len(games) * 0.8); tr, va = list(order[:cut]), list(order[cut:])
    # v2.7 held-out baseline
    v27 = np.concatenate([games[i]["v27"] for i in va])
    mva = np.concatenate([games[i]["margin"] for i in va])
    sv = np.concatenate([games[i]["search_value"] for i in va])
    print(f"\nHELD-OUT corr(estimator, true margin):")
    print(f"  v2.7 value              : {corr(v27, mva):+.3f}")
    print(f"  search-value (root.Q)   : {corr(sv, mva):+.3f}   <- precondition (target quality)")
    for tk, scale, name in [("outcome", 15, "head trained on OUTCOME    "),
                            ("search_value", None, "head trained on SEARCH-VAL ")]:
        cs = [train_eval(games, tr, va, tk, scale, s, dev, a.epochs) for s in range(a.seeds)]
        print(f"  {name}: {np.mean(cs):+.3f} ±{np.std(cs):.3f}")


if __name__ == "__main__":
    main()
