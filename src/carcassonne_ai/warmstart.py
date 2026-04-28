"""Warm-start dataset utilities — labeled-position generation, IO, and a
torch Dataset that wraps the saved .npz files.

Two label strategies (Phase 3 smoke-compares them before committing to the
full run):
  - "mcts":      policy = MCTS(s=N).visit_distribution; value = virtual_score
  - "heuristic": policy = softmax(virtual_score after each legal action);
                 value = virtual_score

Storage: one .npz per game under data/warmstart/<strategy>/seed_<NNNNN>.npz.
Each file holds N sampled positions from that game, all four arrays:
  boards:      (N, n_channels, W, W) float32
  scalars:     (N, n_scalar_features) float32
  policies:    (N, action_size) float32     - rows sum to 1 over valid moves
  values:      (N,) float32                  - tanh(diff/15)
  valid_masks: (N, action_size) bool

Resume by skipping seeds whose .npz already exists.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from .action_space import action_size as compute_action_size
from .game_wrapper import Game
from .virtual_score import virtual_score


SCORE_NORM_SCALE_FOR_LABELS = 15.0  # matches game_wrapper's reward normalization


def normalized_value_target(state, player: int) -> float:
    diff = virtual_score(state, player)
    return math.tanh(diff / SCORE_NORM_SCALE_FOR_LABELS)


@dataclass
class GameDataset:
    boards: np.ndarray       # (N, C, W, W) float32
    scalars: np.ndarray      # (N, S) float32
    policies: np.ndarray     # (N, A) float32
    values: np.ndarray       # (N,) float32
    valid_masks: np.ndarray  # (N, A) bool

    def save(self, path: Path) -> None:
        """Save to a sibling .partial.npz then rename to the final path. The
        rename is atomic on POSIX; readers see only fully-written files. A
        worker killed mid-write leaves a .partial.npz which the next run
        overwrites or ignores (the loader skips files matching the partial
        glob)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        # np.savez_compressed appends .npz if the path doesn't already end in it,
        # so use an explicit .npz extension on the partial.
        partial = path.with_name(path.stem + ".partial.npz")
        np.savez_compressed(
            partial,
            boards=self.boards,
            scalars=self.scalars,
            policies=self.policies,
            values=self.values,
            valid_masks=self.valid_masks,
        )
        partial.replace(path)

    @classmethod
    def load(cls, path: Path) -> "GameDataset":
        with np.load(path) as data:
            return cls(
                boards=data["boards"],
                scalars=data["scalars"],
                policies=data["policies"],
                values=data["values"],
                valid_masks=data["valid_masks"],
            )

    def __len__(self) -> int:
        return self.boards.shape[0]


def _heuristic_policy(game: Game, board, valid_mask: np.ndarray) -> np.ndarray:
    """Policy target via 1-ply virtual_score lookahead. For each legal action,
    apply it, score the resulting state, softmax across legal actions.

    Returns a length-action_size float32 array, zeros on invalid actions."""
    legal = np.flatnonzero(valid_mask)
    if legal.size == 0:
        return np.zeros_like(valid_mask, dtype=np.float32)
    scores = np.empty(legal.size, dtype=np.float32)
    player = board.state.current_player
    for i, action_idx in enumerate(legal):
        next_board, _ = game.get_next_state(board, int(action_idx))
        # virtual_score from CURRENT player's perspective; positive = good for us
        scores[i] = virtual_score(next_board.state, player)
    # softmax with a temperature so the policy isn't degenerate.
    # tau=10 is a reasonable middle: spreads probability across roughly-equal
    # actions but still prefers the best.
    tau = 10.0
    z = scores / tau
    z -= z.max()
    e = np.exp(z)
    p = e / e.sum()
    out = np.zeros(valid_mask.shape[0], dtype=np.float32)
    out[legal] = p
    return out


def _mcts_policy(mcts_visits: dict, action_size_: int) -> np.ndarray:
    """Policy target = MCTS visit count distribution, normalized."""
    out = np.zeros(action_size_, dtype=np.float32)
    if not mcts_visits:
        return out
    total = sum(mcts_visits.values())
    for action, n in mcts_visits.items():
        out[action] = n / total
    return out


def generate_one_game_dataset(
    seed: int,
    label_strategy: str,
    *,
    n_positions_per_game: int = 10,
    mcts_sims: int = 50,
    skip_early: int = 10,
    skip_late: int = 10,
) -> GameDataset:
    """Play a random game; sample N mid-game positions; label each.

    label_strategy: "mcts" or "heuristic".
    """
    if label_strategy not in ("mcts", "heuristic"):
        raise ValueError(f"label_strategy must be 'mcts' or 'heuristic', got {label_strategy!r}")

    rng = random.Random(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    # Walk the game, recording at each step the data we'd need to label
    # later, then sample positions to actually label.
    snapshots: list[tuple] = []  # (board_snapshot, valid_mask, current_player)
    while game.get_game_ended(board, 0) == 0.0:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        # Snapshot BEFORE we apply the action.
        snapshots.append((board, mask, board.state.current_player))
        board, _ = game.get_next_state(board, int(rng.choice(legal)))

    n_total = len(snapshots)
    eligible_lo = skip_early
    eligible_hi = max(skip_early + 1, n_total - skip_late)
    if eligible_hi <= eligible_lo:
        eligible_indices = list(range(n_total))
    else:
        eligible_indices = list(range(eligible_lo, eligible_hi))

    # Sample n_positions_per_game positions from eligible mid-game.
    if len(eligible_indices) <= n_positions_per_game:
        chosen = eligible_indices
    else:
        chosen = sorted(rng.sample(eligible_indices, n_positions_per_game))

    # Label each chosen position.
    A = compute_action_size(game.window_size)
    boards_arr = []
    scalars_arr = []
    policies_arr = []
    values_arr = []
    masks_arr = []

    # Defer MCTS imports so heuristic-only runs don't pay the cost.
    # Share one MCTS-side Game across all positions in this run; the legal-moves
    # cache is reusable across positions (same engine state-key semantics) and
    # we save N×Game-construction overhead.
    if label_strategy == "mcts":
        from .mcts import MCTS
        mcts_game = Game(enable_legal_moves_cache=True)

    for idx in chosen:
        snap_board, mask, player = snapshots[idx]
        obs, scalars = game.get_canonical_form(snap_board, player)
        if label_strategy == "heuristic":
            policy = _heuristic_policy(game, snap_board, mask)
        else:
            mcts = MCTS(game=mcts_game, simulations=mcts_sims, seed=seed * 1000 + idx)
            visits = mcts.search(snap_board)
            policy = _mcts_policy(visits, A)
            mcts_game.clear_caches()  # bound per-search memory; cache is per-MCTS anyway
            del mcts
        value = float(normalized_value_target(snap_board.state, player))
        boards_arr.append(obs.astype(np.float32))
        scalars_arr.append(scalars.astype(np.float32))
        policies_arr.append(policy)
        values_arr.append(value)
        masks_arr.append(mask.astype(bool))

    return GameDataset(
        boards=np.stack(boards_arr) if boards_arr else np.empty((0, 0, 0, 0), dtype=np.float32),
        scalars=np.stack(scalars_arr) if scalars_arr else np.empty((0, 0), dtype=np.float32),
        policies=np.stack(policies_arr) if policies_arr else np.empty((0, A), dtype=np.float32),
        values=np.array(values_arr, dtype=np.float32),
        valid_masks=np.stack(masks_arr) if masks_arr else np.empty((0, A), dtype=bool),
    )


def iter_game_dataset_files(root: Path) -> Iterator[Path]:
    """Yield all .npz files in the warmstart root, sorted by name."""
    yield from sorted(root.glob("seed_*.npz"))
