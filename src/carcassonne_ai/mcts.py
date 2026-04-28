"""Vanilla MCTS reproducing the Ameneyro et al. 2020 baseline.

Reference: Ameneyro et al. 2020, "Playing Carcassonne with Monte Carlo Tree
Search," arXiv:2009.12974. UCT exploration constant C=3 (paper default),
s=100 simulations per move, default rollout policy = uniform random play to
game end.

Acceptance: MCTS(s=100) beats random 100/100 in 2-player games (within noise).

Phase 4 swap: replace random rollout policy with network-driven prior + value
estimate. The Game wrapper's `enable_legal_moves_cache=True` is already wired
and turned on by the MCTS at construction.

Implementation notes:
- One Game per MCTS instance, cache enabled. clear_caches() between root moves.
- Random rollouts deepcopy state per step (engine's apply_action does the copy
  internally; our wrapper no longer adds a redundant outer copy).
- Tile draws use the engine's pre-shuffled deterministic deck. No POMDP-style
  re-shuffling at chance nodes — the 2020 paper does not model chance, and our
  MCTS-vs-MCTS games fix the deck at game start. Comment notes the Phase 4
  consideration if we want to add re-shuffling later.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np

from .game_wrapper import Board, Game


DEFAULT_C = 3.0       # Ameneyro et al. 2020 — UCT exploration constant
DEFAULT_SIMS = 100    # Paper's "s" parameter
ROLLOUT_DEPTH_LIMIT = 1000  # Defensive cap; real games are ~165 decisions


@dataclass
class Node:
    """An MCTS tree node.

    state_key uniquely identifies the position (via Game.string_representation).
    Two paths reaching the same state share a node — the tree is technically
    a DAG, but we expand each node once on first visit and reuse it.
    """
    state_key: str
    player_to_move: int
    is_terminal: bool = False
    terminal_value: float = 0.0  # value from player_to_move's perspective
    parent: "Node | None" = None
    parent_action: int | None = None
    children: dict[int, "Node"] = field(default_factory=dict)
    untried_actions: list[int] = field(default_factory=list)
    N: int = 0
    W: float = 0.0  # total value from this node's player_to_move perspective

    @property
    def Q(self) -> float:
        return self.W / self.N if self.N > 0 else 0.0

    @property
    def is_fully_expanded(self) -> bool:
        return not self.untried_actions and not self.is_terminal


class MCTS:
    """Vanilla MCTS with UCT selection, expansion, random rollout, backprop.

    The same Game instance is reused across simulations. Boards are re-derived
    from string_representation when needed (i.e., we walk the action sequence
    from the root to reproduce a leaf board, since we don't store boards on
    nodes — that would be memory-heavy and string_representation is enough).
    """

    def __init__(
        self,
        game: Game,
        simulations: int = DEFAULT_SIMS,
        c: float = DEFAULT_C,
        seed: int | None = None,
    ):
        if game._legal_cache is None:
            # Don't fail loudly; just enable. The cache is correctness-neutral.
            game._legal_cache = {}
        self.game = game
        self.simulations = simulations
        self.c = c
        self.rng = random.Random(seed)
        # Map state_key -> Node so transpositions share counts.
        self._nodes: dict[str, Node] = {}

    # --- Public API ------------------------------------------------------

    def search(self, root_board: Board) -> dict[int, int]:
        """Run `simulations` UCT iterations from `root_board`. Returns a
        {action_idx: visit_count} dict for the root's children."""
        root = self._get_or_create_node(root_board)
        for _ in range(self.simulations):
            self._simulate(root_board, root)
        return {a: child.N for a, child in root.children.items()}

    def best_action(self, root_board: Board) -> int:
        """Return the best action at the root after a search.

        Selection priority (in order):
          1. Highest mean rollout value Q (most informative at low s, where
             visit counts are sparse and tied at 1).
          2. Tie-broken by visit count (acts like the standard high-s pick).

        At the canonical AlphaZero high-s regime, Q and N agree (UCT shifts
        visits to high-Q actions). At low s (e.g. s=10 with ~50 actions),
        many children have N=1 — picking by N then is essentially random
        across them, while Q discriminates by their single rollout value.

        If no search has been run for this state, runs one now.
        """
        root = self._nodes.get(self.game.string_representation(root_board))
        if root is None or root.N == 0:
            self.search(root_board)
            root = self._nodes[self.game.string_representation(root_board)]
        # Only consider visited children. Unvisited (N==0) have undefined Q.
        visited = [(a, c) for a, c in root.children.items() if c.N > 0]
        if not visited:
            # Pathological: search ran but no child was visited. Fall back to
            # any legal action.
            return next(iter(root.children))
        # Q is from child's player_to_move perspective; flip if different
        # player than root.
        def score(item):
            action, child = item
            q = child.Q if child.player_to_move == root.player_to_move else -child.Q
            return (q, child.N)
        return max(visited, key=score)[0]

    def clear(self) -> None:
        """Drop the search tree and the legal-moves cache. Call between root
        moves to bound memory."""
        self._nodes.clear()
        self.game.clear_caches()

    # --- Internals -------------------------------------------------------

    def _get_or_create_node(self, board: Board) -> Node:
        key = self.game.string_representation(board)
        node = self._nodes.get(key)
        if node is not None:
            return node
        terminal_value = self.game.get_game_ended(board, board.state.current_player)
        is_terminal = terminal_value != 0.0
        if is_terminal:
            untried: list[int] = []
        else:
            mask = self.game.get_valid_moves(board)
            untried = list(map(int, np.flatnonzero(mask)))
        node = Node(
            state_key=key,
            player_to_move=board.state.current_player,
            is_terminal=is_terminal,
            terminal_value=terminal_value,
            untried_actions=untried,
        )
        self._nodes[key] = node
        return node

    def _select_child(self, node: Node) -> tuple[int, "Node"]:
        """UCT: pick the child maximizing Q + C * sqrt(log(N_parent) / N_child)."""
        log_parent = math.log(max(node.N, 1))
        best_score = -math.inf
        best_action = -1
        best_child: Node | None = None
        for action, child in node.children.items():
            if child.N == 0:
                # Always prefer an unvisited expansion (UCT convention).
                return action, child
            exploit = child.Q if child.player_to_move == node.player_to_move else -child.Q
            explore = self.c * math.sqrt(log_parent / child.N)
            score = exploit + explore
            if score > best_score:
                best_score, best_action, best_child = score, action, child
        assert best_child is not None
        return best_action, best_child

    def _simulate(self, root_board: Board, root: Node) -> None:
        """One MCTS iteration: select → expand → rollout → backprop."""
        path: list[Node] = [root]
        board = root_board
        node = root

        # 1. Selection: walk down through fully-expanded internal nodes.
        while node.is_fully_expanded and not node.is_terminal:
            action, node = self._select_child(node)
            board, _ = self.game.get_next_state(board, action)
            path.append(node)

        # 2. Expansion: add a child for one untried action (if any).
        if not node.is_terminal and node.untried_actions:
            action = self.rng.choice(node.untried_actions)
            node.untried_actions.remove(action)
            board, _ = self.game.get_next_state(board, action)
            child = self._get_or_create_node(board)
            child.parent = node
            child.parent_action = action
            node.children[action] = child
            path.append(child)
            node = child

        # 3. Simulation: random rollout from the leaf to game end.
        leaf_value = self._rollout(board)

        # 4. Backprop: update N and W along the path. Each node's W is from
        # its own player_to_move's perspective, so we flip when the player
        # at that node differs from the player whose value we have.
        # leaf_value is from `node.player_to_move`'s perspective at the leaf.
        leaf_player = node.player_to_move
        for n in path:
            n.N += 1
            n.W += leaf_value if n.player_to_move == leaf_player else -leaf_value

    def _rollout(self, board: Board) -> float:
        """Random rollout to game end. Returns value from the leaf player's
        perspective.

        Uses `apply_action_inplace` to mutate the rollout state in place,
        avoiding the deepcopy that dominates mid-game state-copy cost. The
        first call deepcopies once (so the leaf state isn't destroyed); from
        then on all rollout steps mutate the same Board.
        """
        # Deepcopy ONCE so we don't destroy the leaf node's logical state.
        # All subsequent steps mutate this scratch board in place.
        import copy as _copy

        scratch = Board(
            state=_copy.deepcopy(board.state),
            total_tiles=board.total_tiles,
            offset=board.offset,
        )
        leaf_player = scratch.state.current_player
        steps = 0
        while True:
            v = self.game.get_game_ended(scratch, leaf_player)
            if v != 0.0:
                return v
            if steps >= ROLLOUT_DEPTH_LIMIT:
                return self.game.get_game_ended(scratch, leaf_player) or 0.0
            mask = self.game.get_valid_moves(scratch)
            legal = np.flatnonzero(mask)
            action = int(self.rng.choice(legal))
            self.game.apply_action_inplace(scratch, action)
            steps += 1


def virtual_score_estimate(board: Board, player: int) -> float:
    """Ameneyro et al. heuristic value function: estimated final score
    differential without playing rollouts to game end.

    Components (matching the paper's structure):
      - Current scores
      - Expected closure value of partially-completed features owned by each
        player (cities, roads, cloisters)
      - Field/farmer expected end-game contribution

    NOT IMPLEMENTED YET — Phase 2 stretch goal. Vanilla MCTS uses random
    rollouts, which is the paper's primary configuration. The virtual_score
    estimator is used in their "reduced-rollout" variant and would be useful
    for Phase 3 as the heuristic-warm-start training target.
    """
    raise NotImplementedError(
        "virtual_score_estimate is a Phase 3 prerequisite; "
        "vanilla MCTS in Phase 2 uses uniform random rollouts."
    )
