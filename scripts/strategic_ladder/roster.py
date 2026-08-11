"""Agent roster for the strategic-behavior ladder. Uniform interface:
    player.choose(game, board) -> int   (action index)

Reuses the EXACT production agent construction (HeuristicMCTS v2.7 leaf, NeuralMCTS
iter8-style residual_scale=0.25 + meeple_k, c_puct=3.0, sims=200) so harvested
choices match how these agents actually play. v2.8 = v2.7 + flat meeple_k=2.0.

The neural agents (rod1, iter08) load per-process CPU nets. The audit's cost is
dominated by the HEURISTIC agents (h6400 = pure-CPU MCTS, no net) -- so the
parallelism lever is high-W fork pools + cross-box work-stealing, not the
orchestrator (which only batches the light neural forwards).
"""
from __future__ import annotations
import os

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")

import dataclasses
import numpy as np
import torch

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

ITER8_SIMS = 200
ITER8_CPUCT = 3.0
ITER8_RESIDUAL_SCALE = 0.25
MEEPLE_K_V28 = 2.0


def share_root() -> str:
    for r in ("/mnt/c/carc-shared", "/mnt/carc-shared"):
        if os.path.isdir(r):
            return r
    return "/mnt/c/carc-shared"


CKPTS = {
    "rod1": "rod_v28_continuation/ckpt/iter_01.pt",
    "iter08": "rod_v28_overnight_flywheel/ckpt/iter_08.pt",
}

# panel for the counterfactual harvest (weak -> strong ladder order)
PANEL = ["random", "greedy", "h200_v27", "h200", "h800", "h3200", "h6400", "rod1", "iter08"]


def ckpt_path(name: str) -> str:
    return os.path.join(share_root(), CKPTS[name])


# ---- players --------------------------------------------------------------- #
class _Random:
    def __init__(self, seed):
        self.rng = np.random.RandomState(seed & 0x7FFFFFFF)

    def choose(self, game, board):
        legal = np.flatnonzero(game.get_valid_moves(board))
        return int(self.rng.choice(legal))


class _Greedy:
    def __init__(self, seed):
        self.p = RuleBasedPlayer(seed=seed)

    def choose(self, game, board):
        mask = game.get_valid_moves(board)
        return int(self.p.choose_action(game, board, mask))


class _Heur:
    def __init__(self, sims, seed, meeple_k):
        gp = Game(enable_legal_moves_cache=True)
        cfg = dataclasses.replace(DEFAULT_CONFIG, meeple_k=meeple_k) if meeple_k else None
        self.m = HeuristicMCTS(game=gp, simulations=sims, seed=seed, heur_leaf="v2_7", leaf_cfg=cfg)

    def choose(self, game, board):
        self.m.clear()
        return int(self.m.best_action(board))


class _Neural:
    def __init__(self, base_eval, game_farm, seed, meeple_k):
        cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=ITER8_RESIDUAL_SCALE, meeple_k=meeple_k)
        leaf = make_v25_value_wrapper(base_eval, cfg)
        self.m = NeuralMCTS(game=game_farm, evaluator=leaf, simulations=ITER8_SIMS,
                            seed=seed, c_puct=ITER8_CPUCT)

    def choose(self, game, board):
        self.m.clear()
        return int(self.m.best_action(board))


_NET_CACHE: dict = {}   # ckpt -> (base_eval, game_farm)


def _base_eval(name, dev="cpu"):
    ck_path = ckpt_path(name)
    if ck_path in _NET_CACHE:
        return _NET_CACHE[ck_path]
    dev = torch.device(dev)
    game_farm = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    ck = torch.load(ck_path, map_location=dev, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    base = make_single_evaluator(net, dev, game_farm)
    _NET_CACHE[ck_path] = (base, game_farm)
    return base, game_farm


def make_player(spec: str, seed: int):
    """spec in PANEL or {h<N>, h<N>_v27}. seed makes the agent deterministic + distinct."""
    if spec == "random":
        return _Random(seed)
    if spec == "greedy":
        return _Greedy(seed)
    if spec in ("rod1", "iter08"):
        base, gf = _base_eval(spec)
        return _Neural(base, gf, seed, MEEPLE_K_V28)
    if spec.startswith("h"):
        v27 = spec.endswith("_v27")
        sims = int(spec[1:].split("_")[0])
        return _Heur(sims, seed, 0.0 if v27 else MEEPLE_K_V28)
    raise ValueError(f"unknown agent spec {spec!r}")


def needs_net(spec: str) -> bool:
    return spec in ("rod1", "iter08")
