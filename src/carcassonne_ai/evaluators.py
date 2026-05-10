"""Network-evaluator factories for NeuralMCTS callers.

Two flavors:

- `make_single_evaluator`: `Callable[[Board], (priors[A], value)]` — one GPU
  forward per board. Use with `NeuralMCTS(batch_size=1, ...)` (the default
  serial path) and pass as `evaluator=...`.

- `make_batch_evaluator`: `Callable[[list[Board]], (priors[B,A], values[B])]`
  — one GPU forward per K boards. Use with `NeuralMCTS(batch_size=K, ...)`
  and pass as `batch_evaluator=...` to enable the virtual-loss / batched-eval
  path.

Both canonicalize each board from its own `current_player`'s perspective —
this matches NeuralMCTS's expectation that `(priors, value)` come back from
the board's player-to-move POV. The mask is applied via
`net.policy_softmax_with_mask` so invalid actions get zero probability.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import torch

from .game_wrapper import Board, Game
from .network import CarcassonneNet


def make_single_evaluator(
    net: CarcassonneNet, device: torch.device, game: Game
) -> Callable[[Board], tuple[np.ndarray, float]]:
    """Single-board GPU evaluator. Returns (priors[A], value)."""
    def evaluator(board: Board) -> tuple[np.ndarray, float]:
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(device)
        scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(device)
        with torch.no_grad():
            logits, value = net(obs_t, scalars_t)
            mask = game.get_valid_moves(board)
            mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(device)
            probs = net.policy_softmax_with_mask(logits, mask_t)
        return probs[0].cpu().numpy(), float(value.item())
    return evaluator


def make_batch_evaluator(
    net: CarcassonneNet, device: torch.device, game: Game
) -> Callable[[list[Board]], tuple[np.ndarray, np.ndarray]]:
    """K-board batched GPU evaluator. Stacks K canonical encodings into one
    forward pass; returns (priors[B,A], values[B])."""
    def batch_evaluator(
        boards: list[Board],
    ) -> tuple[np.ndarray, np.ndarray]:
        if not boards:
            return (
                np.empty((0,), dtype=np.float32),
                np.empty((0,), dtype=np.float32),
            )
        obs_list = []
        scalars_list = []
        masks_list = []
        for b in boards:
            obs, scalars = game.get_canonical_form(b, b.state.current_player)
            obs_list.append(obs)
            scalars_list.append(scalars)
            masks_list.append(game.get_valid_moves(b))
        obs_t = torch.from_numpy(np.stack(obs_list)).float().to(device)
        scalars_t = torch.from_numpy(np.stack(scalars_list)).float().to(device)
        masks_t = torch.from_numpy(np.stack(masks_list).copy()).bool().to(device)
        with torch.no_grad():
            logits, values = net(obs_t, scalars_t)
            probs = net.policy_softmax_with_mask(logits, masks_t)
        return probs.cpu().numpy(), values.cpu().numpy()
    return batch_evaluator
