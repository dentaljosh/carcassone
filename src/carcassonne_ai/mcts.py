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
    """Ameneyro et al. 2020 §III.B equivalent — estimate final score
    differential without playing rollouts to game end.

    Implementation in `src/carcassonne_ai/virtual_score.py`. Returns a raw
    integer differential; apply `tanh(diff / 15)` to get a value-head target.
    """
    from .virtual_score import virtual_score
    return virtual_score(board.state, player)


# ---------------------------------------------------------------------------
# NeuralMCTS — Phase 3 acceptance Tournament 2 (net+MCTS vs vanilla MCTS).
# ---------------------------------------------------------------------------

DEFAULT_PUCT_C = 1.5  # AlphaZero-typical PUCT exploration constant


@dataclass
class _NeuralNode:
    """An MCTS tree node with cached network priors for PUCT selection."""
    state_key: str
    player_to_move: int
    is_terminal: bool = False
    terminal_value: float = 0.0
    children: dict[int, "_NeuralNode"] = field(default_factory=dict)
    valid_actions: list[int] = field(default_factory=list)
    priors: dict[int, float] = field(default_factory=dict)
    leaf_value: float = 0.0  # network's value at this node (from leaf-player perspective)
    expanded: bool = False
    N: int = 0
    W: float = 0.0  # total value from player_to_move's perspective

    @property
    def Q(self) -> float:
        return self.W / self.N if self.N > 0 else 0.0


class NeuralMCTS:
    """MCTS with PUCT selection and network-driven leaf evaluation.

    Each simulation:
      1. Selection: walk down using PUCT = Q + c * P * sqrt(N_parent) / (1 + N_child).
      2. Expansion: when reaching an unexpanded leaf, query the network for
         (priors, value). Store priors on the node, do NOT random-rollout.
      3. Backprop: propagate the network's value back up the path.

    The network evaluator must be Callable[[Board], tuple[np.ndarray, float]]
    where the array is a length-action_size policy distribution (probabilities,
    only normalized over valid actions) and the float is in [-1, +1] from
    board.state.current_player's perspective.

    Used for Phase 3 acceptance Tournament 2: NeuralMCTS(s=50) vs vanilla
    MCTS(s=100). Network adds the prior + leaf value; vanilla random-rollouts.
    """

    def __init__(
        self,
        game: Game,
        evaluator,  # Callable[[Board], tuple[np.ndarray, float]]
        simulations: int = 50,
        c_puct: float = DEFAULT_PUCT_C,
        seed: int | None = None,
        dirichlet_alpha: float = 0.0,
        dirichlet_eps: float = 0.0,
    ):
        if game._legal_cache is None:
            game._legal_cache = {}
        self.game = game
        self.evaluator = evaluator
        self.simulations = simulations
        self.c_puct = c_puct
        self.rng = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)
        self.dirichlet_alpha = float(dirichlet_alpha)
        self.dirichlet_eps = float(dirichlet_eps)
        self._nodes: dict[str, _NeuralNode] = {}
        # Roots that have already had Dirichlet noise mixed into their priors.
        # Per AlphaZero, noise is applied once per new root (= per move), not
        # every search call. clear() resets this so a fresh tree starts noisy
        # again at its root.
        self._noisy_roots: set[str] = set()

    def search(self, root_board: Board) -> dict[int, int]:
        """Run `simulations` PUCT iterations from `root_board`. Returns a
        {action_idx: visit_count} dict for the root's children."""
        root_key = self.game.string_representation(root_board)
        root = self._nodes.get(root_key)
        if root is None:
            root = self._create_node(root_board)
            self._nodes[root_key] = root
        if not root.expanded and not root.is_terminal:
            self._expand(root, root_board)
        # AlphaZero-style root-only Dirichlet noise: applied once per fresh
        # root to encourage exploration in self-play. No-op if either alpha
        # or eps is 0 (the default — keeps tournament/eval code paths
        # unchanged).
        if (
            self.dirichlet_alpha > 0.0
            and self.dirichlet_eps > 0.0
            and root.expanded
            and not root.is_terminal
            and root_key not in self._noisy_roots
        ):
            self._mix_dirichlet_noise(root)
            self._noisy_roots.add(root_key)
        for _ in range(self.simulations):
            self._simulate(root_board, root)
        return {a: child.N for a, child in root.children.items()}

    def select_for_training(
        self, root_board: Board, temperature: float
    ) -> int:
        """Sample an action proportional to root visit counts ** (1/τ).

        AlphaZero self-play uses τ=1 for the first ~15 plies (exploration),
        then τ→0 (greedy). At τ=0 we fall back to argmax visits — note this
        differs from `best_action` which picks by Q + N tiebreak. Following
        the AlphaZero spec for training-target generation here, since we want
        the visit distribution, not a Q estimate, to drive policy learning.

        Always runs `search` first if the root has zero visits — same UX as
        `best_action`.
        """
        root_key = self.game.string_representation(root_board)
        root = self._nodes.get(root_key)
        if root is None or root.N == 0:
            self.search(root_board)
            root = self._nodes[root_key]
        visited = [(a, c.N) for a, c in root.children.items() if c.N > 0]
        if not visited:
            return next(iter(root.children))
        actions, visits = zip(*visited)
        v = np.asarray(visits, dtype=np.float64)
        if temperature <= 1e-6:
            return int(actions[int(v.argmax())])
        # weights = v ** (1/τ); normalize and sample
        logw = np.log(v) / float(temperature)
        logw -= logw.max()  # stabilize against overflow
        w = np.exp(logw)
        w /= w.sum()
        return int(actions[int(self._np_rng.choice(len(actions), p=w))])

    def root_visit_distribution(
        self, root_board: Board
    ) -> tuple[np.ndarray, list[int]]:
        """Return (counts, action_indices) for the root's children.

        Used by self-play to build a policy training target: normalize
        counts, then scatter into a length-action_size vector. Reuses the
        already-computed root from the most recent search.
        """
        root_key = self.game.string_representation(root_board)
        root = self._nodes.get(root_key)
        if root is None:
            self.search(root_board)
            root = self._nodes[root_key]
        actions = list(root.children.keys())
        counts = np.array(
            [root.children[a].N for a in actions], dtype=np.float64
        )
        return counts, actions

    def best_action(self, root_board: Board) -> int:
        root_key = self.game.string_representation(root_board)
        root = self._nodes.get(root_key)
        if root is None or root.N == 0:
            self.search(root_board)
            root = self._nodes[root_key]
        visited = [(a, c) for a, c in root.children.items() if c.N > 0]
        if not visited:
            return next(iter(root.children))

        def score(item):
            action, child = item
            q = child.Q if child.player_to_move == root.player_to_move else -child.Q
            return (q, child.N)
        return max(visited, key=score)[0]

    def clear(self) -> None:
        self._nodes.clear()
        self._noisy_roots.clear()
        self.game.clear_caches()

    def _mix_dirichlet_noise(self, root: "_NeuralNode") -> None:
        """Mix Dirichlet(α) noise into root.priors per AlphaZero spec.

        new_p[a] = (1 - ε) * priors[a] + ε * dir[a]   for a ∈ valid_actions

        α is typically chosen ≈ 10 / mean_legal_moves; for our action space
        the BACKLOG measurement gave ~0.53. Default at the constructor is 0
        (noise disabled) so non-self-play call sites are unaffected.
        """
        if not root.valid_actions:
            return
        n = len(root.valid_actions)
        noise = self._np_rng.dirichlet([self.dirichlet_alpha] * n)
        eps = self.dirichlet_eps
        for i, action in enumerate(root.valid_actions):
            p = root.priors.get(action, 0.0)
            root.priors[action] = (1.0 - eps) * p + eps * float(noise[i])

    # --- Internals ---------------------------------------------------------

    def _create_node(self, board: Board) -> _NeuralNode:
        key = self.game.string_representation(board)
        terminal_value = self.game.get_game_ended(board, board.state.current_player)
        return _NeuralNode(
            state_key=key,
            player_to_move=board.state.current_player,
            is_terminal=(terminal_value != 0.0),
            terminal_value=terminal_value,
        )

    def _expand(self, node: _NeuralNode, board: Board) -> None:
        """Query the network at this state; populate node.priors, node.leaf_value,
        node.valid_actions. Idempotent — safe to call multiple times.

        Defensive: a bad checkpoint can return NaN/inf priors or wrong shape;
        falls back to uniform-over-legal in any of those cases. Likewise an
        all-zero or negative-sum prior distribution → uniform.
        """
        if node.expanded:
            return
        if node.is_terminal:
            node.leaf_value = node.terminal_value
            node.expanded = True
            return
        priors, value = self.evaluator(board)
        mask = self.game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            node.leaf_value = 0.0
            node.expanded = True
            return

        # Sanitize priors: shape, finiteness, non-negativity, sum.
        # Negative finite priors would also pass NaN/inf checks but produce
        # weird negative PUCT exploration terms — treat them as malformed.
        priors_ok = (
            isinstance(priors, np.ndarray)
            and priors.shape == mask.shape
            and np.isfinite(priors).all()
            and (priors[legal] >= 0).all()
        )
        if priors_ok:
            legal_priors = priors[legal]
            s = float(legal_priors.sum())
            if s <= 0 or not math.isfinite(s):
                priors_ok = False
        if not priors_ok:
            legal_priors = np.full(legal.size, 1.0 / legal.size, dtype=np.float32)
        else:
            legal_priors = legal_priors / s

        # Sanitize value: finite scalar in [-1, 1].
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = 0.0
        if not math.isfinite(v):
            v = 0.0
        v = max(-1.0, min(1.0, v))

        node.valid_actions = [int(a) for a in legal]
        node.priors = {int(a): float(p) for a, p in zip(legal, legal_priors)}
        node.leaf_value = v
        node.expanded = True

    def _select_child_puct(self, node: _NeuralNode) -> int:
        """PUCT: argmax over valid actions of Q + c * P * sqrt(N_parent) / (1 + N_child)."""
        sqrt_parent_N = math.sqrt(max(node.N, 1))
        best_action = node.valid_actions[0]
        best_score = -math.inf
        for action in node.valid_actions:
            child = node.children.get(action)
            if child is None:
                q = 0.0
                n = 0
            else:
                q = child.Q if child.player_to_move == node.player_to_move else -child.Q
                n = child.N
            u = self.c_puct * node.priors[action] * sqrt_parent_N / (1 + n)
            score = q + u
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    def _simulate(self, root_board: Board, root: _NeuralNode) -> None:
        """One PUCT iteration: select → (expand) → backprop with leaf_value."""
        path: list[_NeuralNode] = [root]
        board = root_board
        node = root

        # Selection: walk down using PUCT, treating expanded nodes as internal.
        while node.expanded and not node.is_terminal:
            action = self._select_child_puct(node)
            board, _ = self.game.get_next_state(board, action)
            child = node.children.get(action)
            if child is None:
                # First time this parent reaches this state via this action.
                # Check the transposition table — another path may have already
                # created a node for the same state. If so, share it (counts
                # combine across paths). Otherwise register a new one.
                fresh = self._create_node(board)
                child = self._nodes.setdefault(fresh.state_key, fresh)
                if child is fresh and not child.expanded:
                    self._expand(child, board)
                node.children[action] = child
                path.append(child)
                node = child
                break
            else:
                path.append(child)
                node = child

        # If we exited because we hit a terminal node, leaf_value is already set
        # by _create_node / terminal_value. Otherwise it's set by _expand above.
        leaf_value = node.leaf_value
        leaf_player = node.player_to_move

        # Backprop.
        for n in path:
            n.N += 1
            n.W += leaf_value if n.player_to_move == leaf_player else -leaf_value
