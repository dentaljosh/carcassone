"""Vanilla MCTS for Phase 2 — reproducing the Ameneyro et al. 2020 baseline.

NOT IMPLEMENTED YET. This module is a skeleton outlining the class shape and
key parameters from the paper. Phase 2 work will fill in the methods.

Reference: Ameneyro et al. 2020, "Playing Carcassonne with Monte Carlo Tree
Search," arXiv:2009.12974. Default UCT exploration constant C=3,
s=100 simulations per move, default rollout policy = uniform random.

Phase 2 acceptance criterion: MCTS bot beats random 100/100 games at s=100,
matching the paper's reported numbers within statistical noise.

Phase 4 swap: replace the random rollout policy with a network-driven prior +
value estimate. The Game wrapper's `enable_legal_moves_cache=True` flag is
already wired and should be turned on by the MCTS at construction.

Implementation notes for Phase 2:
- Construct one Game per MCTS instance with `enable_legal_moves_cache=True`.
  Call `game.clear_caches()` between root moves to bound memory.
- Random rollouts can mutate state in place once the BACKLOG item
  "In-place state mutation for MCTS rollouts" lands. Until then, every
  simulation step pays a deepcopy.
- For multiprocessing-parallel MCTS (one search per worker), the Game and
  its cache cross process boundaries cleanly — dicts of np.ndarrays
  serialize fine. But masks lose their writable=False flag after the
  cross-process round-trip and become mutable; workers should not share
  cached masks, only their own.
- For batched-GPU MCTS (Phase 4), don't cross process boundaries at all —
  use virtual-loss MCTS with a single Game per worker and a
  leaf-collection pattern that batches network forwards. See BACKLOG.md.
"""
from __future__ import annotations

# from dataclasses import dataclass, field
# from typing import TYPE_CHECKING
#
# import math
# import random
#
# import numpy as np
#
# from .game_wrapper import Board, Game
#
#
# DEFAULT_C = 3.0  # Ameneyro et al. 2020 — UCT exploration constant
# DEFAULT_SIMS = 100  # paper's "s" parameter
#
#
# @dataclass
# class Node:
#     """An MCTS tree node. Parameterized by state-key + parent-edge metadata."""
#
#     state_key: str            # from game.string_representation
#     player_to_move: int       # whose decision is at this node
#     phase: str                # "tiles" or "meeples"
#     parent: "Node | None" = None
#     children: dict[int, "Node"] = field(default_factory=dict)  # action_idx -> Node
#     N: int = 0                # visit count
#     W: float = 0.0            # total value (from this node's player's perspective)
#     legal_mask: np.ndarray | None = None  # cached on first expansion
#
#     @property
#     def Q(self) -> float:
#         return self.W / self.N if self.N > 0 else 0.0
#
#
# class MCTS:
#     def __init__(
#         self,
#         game: Game,
#         simulations: int = DEFAULT_SIMS,
#         c: float = DEFAULT_C,
#         seed: int | None = None,
#     ):
#         # Game must have legal-moves cache enabled for performance.
#         self.game = game
#         self.simulations = simulations
#         self.c = c
#         self.rng = random.Random(seed)
#
#     def search(self, root_board: Board) -> np.ndarray:
#         """Run `simulations` rollouts from root. Returns a visit distribution
#         over the action space."""
#         # 1. Build root node, expand if needed
#         # 2. For sim in range(simulations):
#         #    a. Selection: walk the tree using UCT until a leaf
#         #    b. Expansion: add a child for the chosen action
#         #    c. Simulation: random rollout from the new leaf to game end
#         #    d. Backprop: update N, W along the path
#         # 3. Return visit-count distribution at root
#         raise NotImplementedError("Phase 2 implementation pending")
#
#     def best_action(self, root_board: Board) -> int:
#         """Return the action with the highest visit count after `search`."""
#         raise NotImplementedError("Phase 2 implementation pending")
#
#
# def virtual_score_estimate(board: "Board", player: int) -> float:
#     """Ameneyro et al. heuristic value function: estimated final score
#     differential without playing rollouts to game end. Used as a leaf
#     estimator in their reduced-rollout variant. Phase 3 will train the
#     network value head to mimic this on labeled positions.
#     """
#     raise NotImplementedError("Phase 2 implementation pending")
