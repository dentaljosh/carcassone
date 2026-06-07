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

import copy
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
        # Dedup transposition collisions: rotations of a symmetric tile share
        # one child node object (root.children[a1] is root.children[a2]); keep
        # the lowest-index action per unique child. (Outcome-neutral here —
        # equivalent actions yield the same board — but keeps the iteration
        # consistent with NeuralMCTS and avoids scoring one child twice.)
        _seen: set[int] = set()
        visited = []
        for a in sorted(root.children):
            c = root.children[a]
            if c.N <= 0 or id(c) in _seen:
                continue
            _seen.add(id(c))
            visited.append((a, c))
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
# HeuristicMCTS — Tier-1's 1-ply heuristic with UCT search depth on top.
# ---------------------------------------------------------------------------

HEURISTIC_VALUE_NORM = 15.0  # matches warmstart value-head target normalization


class HeuristicMCTS(MCTS):
    """Vanilla MCTS structure with a virtual_score leaf replacing the random rollout.

    Tier-1 (RuleBasedPlayer) picks the action that maximizes virtual_score one
    ply ahead. HeuristicMCTS adds UCT search on top, so a simulation can look
    multiple plies deep and weigh tradeoffs that 1-ply argmax misses.

    ``heur_leaf`` selects which leaf the rollout-replacement uses:
      - ``"v1"`` (DEFAULT, legacy): base ``virtual_score`` (engine end-of-game
        scoring of the current board). This is the historical reference-ladder
        opponent — keep it the default so prior ladder numbers stay comparable.
      - ``"v2_7"``: ``virtual_score_v2`` with the env-built DEFAULT_CONFIG
        (cap/drop-three-open from CARCASSONNE_V25_*). Use this to MATCH the leaf
        the neural agent plays with (make_v25_value_wrapper), so a net-vs-heur
        eval isolates the learned policy instead of confounding it with the
        v2.7-vs-v1 leaf gap. (See the 2026-06-07 outside-review finding R1: the
        ladder opponent had been running v1 while the agent ran v2.7.)

    Leaf values are normalized to [-1, +1] via tanh(diff / HEURISTIC_VALUE_NORM)
    so the UCT exploration term is on a comparable scale to the exploit term —
    raw integer differentials would dominate Q+UCT and collapse exploration.
    Terminal leaves return the engine's signed terminal value unchanged.
    """

    def __init__(self, *args, heur_leaf: str = "v1", **kwargs):
        super().__init__(*args, **kwargs)
        if heur_leaf not in ("v1", "v2_7"):
            raise ValueError(f"heur_leaf must be 'v1' or 'v2_7'; got {heur_leaf!r}")
        self._heur_leaf = heur_leaf

    def _rollout(self, board: Board) -> float:
        leaf_player = board.state.current_player
        v = self.game.get_game_ended(board, leaf_player)
        if v != 0.0:
            return v
        if self._heur_leaf == "v2_7":
            from .virtual_score_v2 import virtual_score_v2
            diff = virtual_score_v2(board.state, leaf_player)
        else:
            diff = virtual_score_estimate(board, leaf_player)
        return math.tanh(diff / HEURISTIC_VALUE_NORM)


# ---------------------------------------------------------------------------
# NeuralMCTS — Phase 3 acceptance Tournament 2 (net+MCTS vs vanilla MCTS).
# ---------------------------------------------------------------------------

DEFAULT_PUCT_C = 1.5
# AlphaZero-typical PUCT exploration constant. Empirically validated 2026-05-15
# (iter_00 + v2.7 leaf vs Tier-1, n=20 sims=200): c=1.5 = 80% wr, c=2.0 = 85%
# (tied at 84/88% n=50, indistinguishable), c=1.0 = 52.5%, c=0.5 = 67.5%.
# Low c is CATASTROPHIC — search over-explores into virtual_score's blind spots.
# Don't lower this without re-benching at n=50 minimum.


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
    # The board at this node, stored ONLY when the owning NeuralMCTS has
    # record_boards=True (flywheel step 1, DECISIONS 2026-06-04). Lets self-play
    # harvest tree-INTERIOR (board, Q) pairs as value targets so the value head
    # sees the off-trajectory positions search actually visits — the fix for the
    # −576 pure-NN-leaf distribution mismatch. None in the normal (eval) path so
    # search keeps its small per-node footprint.
    board: object = None
    expanded: bool = False
    N: int = 0
    W: float = 0.0  # total value from player_to_move's perspective
    # --- transposition-collision bookkeeping (C2 search-side fix) ---
    # Rotations of a symmetric tile produce the IDENTICAL child board, so several
    # actions link to the SAME child object. Without this, PUCT scores that one
    # move once PER colliding action (each with its own prior) — the move gets
    # multiple bites at the selection apple. We collapse them: the FIRST action
    # to link a given child is its representative; later colliding actions become
    # ALIASES (skipped in selection) and their prior is folded into the
    # representative's `prior_bonus` so the move competes once with summed prior.
    child_canon: dict[int, int] = field(default_factory=dict)   # id(child) -> repr action
    child_aliases: set[int] = field(default_factory=set)        # actions to skip in PUCT
    prior_bonus: dict[int, float] = field(default_factory=dict)  # repr action -> folded prior

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
        batch_size: int = 1,
        batch_evaluator=None,  # Callable[[list[Board]], tuple[np.ndarray, np.ndarray]]
        virtual_loss: float = 1.0,
        fair_chance: bool = False,
        fpu_reduction: float | None = None,
        record_boards: bool = False,
    ):
        if game._legal_cache is None:
            game._legal_cache = {}
        self.game = game
        self.evaluator = evaluator
        self.simulations = simulations
        self.c_puct = c_puct
        # fair_chance=True makes the search NON-CLAIRVOYANT: the engine's deck is
        # pre-shuffled in its TRUE future order, so by default every simulation
        # descends along the actual upcoming tiles (single-determinization /
        # perfect-info search — the agent "sees" future draws). With fair_chance
        # the search instead runs on a copy of the root whose UNSEEN deck is
        # re-shuffled (contents preserved, order randomized) — one plausible
        # future per move, the information a real player actually has. The real
        # game board is never mutated (we descend from a copy), so the actual
        # draw order is unchanged. This is single-determinization, NOT an
        # expectation over draws — the exact-chance-node ensemble is a separate,
        # larger change (the tree keys children by action, which assumes a
        # placement yields one child; per-draw branching needs real chance nodes).
        self.fair_chance = bool(fair_chance)
        # FPU (first-play urgency) for UNVISITED children in PUCT (round-2 audit
        # G-T/F-D-FPU). None (default) = legacy optimistic-zero (q=0). A float r
        # uses q = parent.Q - r, so an unvisited child is valued near the
        # parent's own estimate minus a reduction instead of a hardcoded 0 (which
        # is mis-scaled against the [-1,1] Q range, esp. once a raw net value
        # drives the leaf at Stage B). A/B'd via --new-fpu/--old-fpu.
        self.fpu_reduction = fpu_reduction
        # record_boards: store each expanded node's board on the node so self-play
        # can harvest tree-interior (board, Q) value targets (flywheel step 1,
        # DECISIONS 2026-06-04). Default False → eval/anchor searches keep the
        # lean per-node footprint; only the learner's self-play MCTS turns it on.
        self.record_boards = bool(record_boards)
        self.rng = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)
        self.dirichlet_alpha = float(dirichlet_alpha)
        self.dirichlet_eps = float(dirichlet_eps)
        # Virtual-loss-MCTS knobs. batch_size=1 → existing serial path; >1 →
        # collect K leaf paths with vloss applied, batch-eval, backup with
        # vloss undo. batch_evaluator is the GPU-batched (priors, value)
        # function; if None, falls back to per-board calls of `evaluator`
        # (still gets vloss diversification but no GPU batching speedup —
        # useful for tests).
        self.batch_size = max(1, int(batch_size))
        self.batch_evaluator = batch_evaluator
        self.virtual_loss = float(virtual_loss)
        self._nodes: dict[str, _NeuralNode] = {}
        # Roots that have already had Dirichlet noise mixed into their priors.
        # Per AlphaZero, noise is applied once per new root (= per move), not
        # every search call. clear() resets this so a fresh tree starts noisy
        # again at its root.
        self._noisy_roots: set[str] = set()

    def _reshuffled_root(self, board: Board) -> Board:
        """Return a copy of `board` whose UNSEEN deck is re-shuffled (contents
        preserved, order randomized) — the fair-chance / non-clairvoyant root.
        `next_tile` (the already-revealed current tile) is left untouched; only
        the not-yet-drawn `state.deck` is permuted. The caller's board is never
        mutated, so the real game's draw order is preserved. Cheap: one board
        deepcopy + one list shuffle per move (negligible vs the sims)."""
        b = copy.deepcopy(board)
        self.rng.shuffle(b.state.deck)
        b._str_repr_cache = None  # deck order isn't in the key, but be safe
        return b

    def search(self, root_board: Board) -> dict[int, int]:
        """Run `simulations` PUCT iterations from `root_board`. Returns a
        {action_idx: visit_count} dict for the root's children."""
        if self.fair_chance:
            # One plausible future per move; the search can no longer see the
            # true upcoming tiles. Same root_key (deck ORDER isn't in the key),
            # so node lookup/expansion are unchanged — only the descent differs.
            root_board = self._reshuffled_root(root_board)
        root_key = self.game.string_representation(root_board)
        root = self._nodes.get(root_key)
        if root is None:
            root = self._create_node(root_board)
            self._nodes[root_key] = root
        if not root.expanded and not root.is_terminal:
            # Use _eval_boards so the root expansion goes through the
            # batched path when one is wired (single-call boards=[root]).
            priors_b, values_b = self._eval_boards([root_board])
            self._expand_with_priors(
                root, root_board, priors_b[0], float(values_b[0])
            )
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
        if self.batch_size > 1:
            sims_done = 0
            while sims_done < self.simulations:
                this_batch = min(self.batch_size, self.simulations - sims_done)
                self._run_batch(root_board, root, this_batch)
                sims_done += this_batch
        else:
            for _ in range(self.simulations):
                self._simulate(root_board, root)
        return {a: child.N for a, child in root.children.items()}

    def _deduped_children(
        self, root: "_NeuralNode"
    ) -> list[tuple[int, "_NeuralNode"]]:
        """Return [(action, child)] with transposition collisions removed.

        Rotationally-symmetric tiles (straight roads, etc.) emit ≥2 rotations
        that produce the IDENTICAL resulting board → identical state_key → the
        transposition table hands BOTH action slots the SAME child node object
        (root.children[a1] is root.children[a2]). That child accumulates visits
        from either edge, so reading children[a].N per-action counts its visit
        mass once PER colliding slot — ~2× inflation on ~20% of decision nodes,
        corrupting the policy target and best_action.

        Collapse each group of actions sharing one child to its lowest-index
        action (deterministic). The actions are interchangeable by definition —
        they yield the same board the search already treats as one node — so the
        combined visit count belongs to a single slot; the others get nothing.
        """
        out: list[tuple[int, "_NeuralNode"]] = []
        seen: set[int] = set()
        for a in sorted(root.children):
            child = root.children[a]
            if id(child) in seen:
                continue
            seen.add(id(child))
            out.append((a, child))
        return out

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
        visited = [(a, c.N) for a, c in self._deduped_children(root) if c.N > 0]
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
        items = self._deduped_children(root)
        actions = [a for a, _ in items]
        counts = np.array([c.N for _, c in items], dtype=np.float64)
        return counts, actions

    def root_value(self, root_board: Board) -> float:
        """Return the root's search value Q (root current-player POV) from the
        most recent search.

        root.Q = W/N from `root.player_to_move`'s perspective (= the player to
        move at the root = the position's current player), so the returned value
        is in [-1, +1] from the current player's POV — the SAME POV convention as
        the self-play value targets (`values_arr`). Used to record per-position
        MCTS search-value targets (the overfitting fix, DECISIONS 2026-06-04):
        ~100× more independent value labels than the one-per-game outcome z.

        Reuses the already-computed root from the most recent search; runs one
        search if the root is missing or unvisited (same UX as best_action /
        root_visit_distribution).
        """
        root_key = self.game.string_representation(root_board)
        root = self._nodes.get(root_key)
        if root is None or root.N == 0:
            self.search(root_board)
            root = self._nodes[root_key]
        return float(root.Q)

    def interior_value_targets(
        self,
        root_board: Board,
        *,
        min_visits: int = 8,
        max_nodes: int = 16,
    ) -> list[tuple[object, int, float]]:
        """Harvest (board, player_to_move, Q) value targets from the SEARCH
        TREE INTERIOR — the off-trajectory positions the value head never sees
        in plain self-play (flywheel step 1, DECISIONS 2026-06-04). These are
        the fix for the −576 pure-NN-leaf cliff: the value was trained only on
        played-trajectory positions, then queried at tree-interior nodes it
        never saw. Training on (interior board → its converged search Q)
        teaches the raw value to predict search outcomes at exactly the
        positions search visits → bootstraps the value/leaf flywheel.

        Requires the owning MCTS was constructed with record_boards=True (else
        every node.board is None and this returns []). The search must already
        have run for `root_board` (self-play calls this right after search()).

        Selection:
          - EXCLUDE the search root (already recorded as a full trajectory row
            with policy+ownership) and terminal nodes (Q == terminal_value, no
            learning signal beyond the outcome target).
          - keep nodes with N >= min_visits (a well-converged Q, not N=1 noise);
          - return the top `max_nodes` by visit count (bounds the per-move row
            blow-up / dataset size — the interior dwarfs the one trajectory row).

        Q is W/N from node.player_to_move's POV (same sign convention as
        root.Q and the value targets), so pair it with
        get_canonical_form(board, player_to_move) — no extra sign flip.
        """
        root_key = self.game.string_representation(root_board)
        cands = [
            node
            for key, node in self._nodes.items()
            if key != root_key
            and not node.is_terminal
            and node.board is not None
            and node.N >= min_visits
        ]
        cands.sort(key=lambda n: n.N, reverse=True)
        return [
            (node.board, node.player_to_move, float(node.Q))
            for node in cands[:max_nodes]
        ]

    def interior_sibling_groups(
        self,
        root_board: Board,
        *,
        min_parent_visits: int = 16,
        min_child_visits: int = 3,
        max_groups: int = 6,
        max_children: int = 8,
    ) -> list[list[tuple[object, int, float]]]:
        """Harvest SIBLING GROUPS from the search tree for the ranking loss
        (STEP B.1, DECISIONS 2026-06-05 pm-3). For each well-visited interior
        PARENT node, return its visited children as a group:
        `[(child_board, child_player_to_move, child_Q)]` with child_Q in the
        child's OWN POV.

        Why this works: STEP A/B.0 showed an MSE-trained value head ranks
        sibling moves at CHANCE (τ≈0.08) even when it fits the target globally
        (corr 0.86) — MSE optimizes global calibration, not local ordering. A
        listwise ranking loss over these groups trains the head to ORDER a node's
        children by their search Q — the local discrimination a leaf needs. All
        children of a node share one player-to-move (Carcassonne splits tile vs
        meeple actions), so own-POV Q IS the ordering the leaf must reproduce
        (no per-child flip), and the head's group outputs are directly comparable.

        Requires record_boards=True. Selection: parent expanded, non-terminal,
        board recorded, N≥min_parent_visits; children (deduped) non-terminal,
        board recorded, N≥min_child_visits; a group needs ≥2 such children. Top
        max_groups parents by N; top max_children by N within each group.
        """
        scored: list[tuple[int, list[tuple[object, int, float]]]] = []
        for node in self._nodes.values():
            if (not node.expanded) or node.is_terminal or node.board is None:
                continue
            if node.N < min_parent_visits:
                continue
            kids: list[tuple[int, object, int, float]] = []
            for _a, child in self._deduped_children(node):
                if (
                    child.board is None
                    or child.is_terminal
                    or child.N < min_child_visits
                ):
                    continue
                kids.append((child.N, child.board, child.player_to_move, float(child.Q)))
            if len(kids) < 2:
                continue
            kids.sort(key=lambda t: t[0], reverse=True)
            kids = kids[:max_children]
            scored.append((node.N, [(b, p, q) for (_n, b, p, q) in kids]))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [g for (_n, g) in scored[:max_groups]]

    def best_action(self, root_board: Board) -> int:
        root_key = self.game.string_representation(root_board)
        root = self._nodes.get(root_key)
        if root is None or root.N == 0:
            self.search(root_board)
            root = self._nodes[root_key]
        visited = [(a, c) for a, c in self._deduped_children(root) if c.N > 0]
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

    def _link_child(
        self, node: _NeuralNode, action: int, child: _NeuralNode
    ) -> None:
        """Attach `child` to `node` under `action`, maintaining the
        transposition-collision alias structure (C2 search-side fix).

        The FIRST action to link a given child object becomes that child's
        representative. A later action that links the SAME object (a symmetric
        rotation yielding the identical board) is recorded as an alias — skipped
        by `_select_child_puct` — and its prior is folded once into the
        representative's `prior_bonus`, so the move competes in PUCT exactly once
        with the summed prior instead of once per colliding rotation.
        """
        node.children[action] = child
        cid = id(child)
        canon = node.child_canon.get(cid)
        if canon is None:
            node.child_canon[cid] = action
        elif canon != action and action not in node.child_aliases:
            node.child_aliases.add(action)
            node.prior_bonus[canon] = (
                node.prior_bonus.get(canon, 0.0) + node.priors.get(action, 0.0)
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
        self._expand_with_priors(node, board, priors, value)

    def _expand_with_priors(
        self,
        node: _NeuralNode,
        board: Board,
        priors: np.ndarray,
        value: float,
    ) -> None:
        """Same as _expand but uses pre-computed priors/value (from a
        batched evaluator). Same sanitization as _expand: malformed priors
        fall back to uniform-over-legal; non-finite values clamp to 0;
        finite values clamp to [-1, 1]."""
        if node.expanded:
            return
        # Capture the board for tree-interior value harvesting (flywheel step 1).
        # Gated on record_boards so the eval path pays nothing. Stored before the
        # terminal/no-legal early-returns are irrelevant — interior_value_targets
        # filters terminals; non-terminal expanded nodes are exactly what we want.
        if self.record_boards:
            node.board = board
        if node.is_terminal:
            node.leaf_value = node.terminal_value
            node.expanded = True
            return
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

    def _eval_boards(
        self, boards: list[Board]
    ) -> tuple[np.ndarray, np.ndarray]:
        """Evaluate a list of boards. Returns (priors_array, values_array)
        where priors has shape (B, A) and values has shape (B,).

        Uses self.batch_evaluator if set; otherwise falls back to per-board
        self.evaluator calls (so this works in tests where no batched
        evaluator is wired)."""
        if not boards:
            return np.empty((0,)), np.empty((0,))
        # Only use the batched evaluator when batched mode is actually
        # active — keeps serial-mode (`batch_size=1`) call sites unchanged
        # even when both evaluators are wired.
        if self.batch_size > 1 and self.batch_evaluator is not None:
            return self.batch_evaluator(boards)
        priors_list = []
        values_list = []
        for b in boards:
            p, v = self.evaluator(b)
            priors_list.append(p)
            values_list.append(float(v))
        return np.stack(priors_list), np.array(values_list, dtype=np.float32)

    def _select_child_puct(self, node: _NeuralNode) -> int:
        """PUCT: argmax over valid actions of Q + c * P * sqrt(N_parent) / (1 + N_child)."""
        sqrt_parent_N = math.sqrt(max(node.N, 1))
        best_action = node.valid_actions[0]
        best_score = -math.inf
        aliases = node.child_aliases
        prior_bonus = node.prior_bonus
        for action in node.valid_actions:
            # Skip transposition aliases: a colliding rotation whose move is
            # already represented by another action (its prior was folded in).
            if aliases and action in aliases:
                continue
            child = node.children.get(action)
            if child is None:
                # FPU: legacy q=0 (None) or parent.Q - reduction. node.Q is from
                # node.player_to_move's POV — same POV the unvisited child is
                # scored in here — so no sign flip is needed.
                q = 0.0 if self.fpu_reduction is None else node.Q - self.fpu_reduction
                n = 0
            else:
                q = child.Q if child.player_to_move == node.player_to_move else -child.Q
                n = child.N
            p = node.priors[action]
            if prior_bonus:
                p += prior_bonus.get(action, 0.0)
            u = self.c_puct * p * sqrt_parent_N / (1 + n)
            score = q + u
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    # --- Virtual-loss / batched-evaluation path ---------------------------
    #
    # Virtual loss makes a node-in-flight look temporarily WORSE to its
    # parent's PUCT, so subsequent sims in the same batch pick a different
    # branch and diversify. Net per node: N += 1, W += signed_real_value —
    # identical to the serial backup.
    #
    # Subtlety: in negamax-style trees, child.Q is viewed by parent as
    # `child.Q if same_player else -child.Q`. To make Q_parent_view DROP by
    # `virtual_loss / N`, we need:
    #   - same player: child.W -= virtual_loss
    #   - different player: child.W += virtual_loss
    # i.e., apply the penalty in the PARENT'S perspective, then store it
    # in child's own-perspective W via the appropriate sign flip.
    #
    # Root has no parent, so we only bump root.N (root.W doesn't affect
    # PUCT for selecting any child).

    def _apply_vloss_at_child(
        self, parent: _NeuralNode, child: _NeuralNode
    ) -> None:
        child.N += 1
        if parent.player_to_move == child.player_to_move:
            child.W -= self.virtual_loss
        else:
            child.W += self.virtual_loss

    def _undo_vloss_at_child(
        self, parent: _NeuralNode, child: _NeuralNode
    ) -> None:
        # N stays (now a real visit count); undo only the W penalty.
        if parent.player_to_move == child.player_to_move:
            child.W += self.virtual_loss
        else:
            child.W -= self.virtual_loss

    def _select_leaf_with_vloss(
        self, root_board: Board, root: _NeuralNode
    ) -> tuple[list[_NeuralNode], _NeuralNode, Board, bool]:
        """Walk root → leaf using PUCT, applying vloss to each non-root
        node on the path (in parent's perspective). Stops at the first
        terminal or unexpanded node.

        Returns (path, leaf, leaf_board, needs_eval) where needs_eval is
        True iff the leaf is non-terminal AND not yet expanded.
        """
        path: list[_NeuralNode] = [root]
        board = root_board
        node = root
        node.N += 1  # root vloss: just bump the visit count
        if node.is_terminal:
            return path, node, board, False
        if not node.expanded:
            return path, node, board, True
        while True:
            action = self._select_child_puct(node)
            board, _ = self.game.get_next_state(board, action)
            parent = node
            child = parent.children.get(action)
            if child is None:
                fresh = self._create_node(board)
                child = self._nodes.setdefault(fresh.state_key, fresh)
                self._link_child(parent, action, child)
                self._apply_vloss_at_child(parent, child)
                path.append(child)
                needs_eval = (not child.is_terminal) and (not child.expanded)
                return path, child, board, needs_eval
            self._apply_vloss_at_child(parent, child)
            path.append(child)
            if child.is_terminal:
                return path, child, board, False
            if not child.expanded:
                # Transposition: this node was created earlier on a sibling
                # path but never expanded. Send it through batch eval.
                return path, child, board, True
            node = child

    def _run_batch(
        self, root_board: Board, root: _NeuralNode, batch_size: int
    ) -> None:
        """Collect `batch_size` leaf paths with vloss, batch-evaluate the
        unexpanded leaves in one call, then backup all paths."""
        # Phase 1: select K leaves with vloss applied along each path.
        selections: list[tuple[list[_NeuralNode], _NeuralNode, Board]] = []
        boards_to_eval: list[Board] = []
        eval_target_indices: list[int] = []  # index into selections
        seen_leaf_id: dict[int, int] = {}  # id(leaf) -> index in boards_to_eval
        for _ in range(batch_size):
            path, leaf, leaf_board, needs_eval = self._select_leaf_with_vloss(
                root_board, root
            )
            selections.append((path, leaf, leaf_board))
            if needs_eval and id(leaf) not in seen_leaf_id:
                seen_leaf_id[id(leaf)] = len(boards_to_eval)
                boards_to_eval.append(leaf_board)
                eval_target_indices.append(len(selections) - 1)

        # Phase 2: batch-evaluate the unexpanded leaves (deduped across the
        # batch — multiple paths converging on the same node only get
        # evaluated once).
        if boards_to_eval:
            priors_b, values_b = self._eval_boards(boards_to_eval)
            for j, sel_idx in enumerate(eval_target_indices):
                _, leaf, leaf_board = selections[sel_idx]
                self._expand_with_priors(
                    leaf, leaf_board, priors_b[j], float(values_b[j])
                )

        # Phase 3: backup each path. For each child node on the path, undo
        # the vloss W penalty (in its parent's perspective) then add the
        # signed real value (in its own perspective). Root has no vloss W
        # to undo — just add the signed real value.
        for path, leaf, _ in selections:
            leaf_value = (
                leaf.leaf_value if leaf.expanded else leaf.terminal_value
            )
            leaf_player = leaf.player_to_move
            for i, n in enumerate(path):
                if i > 0:
                    self._undo_vloss_at_child(path[i - 1], n)
                if n.player_to_move == leaf_player:
                    n.W += leaf_value
                else:
                    n.W -= leaf_value

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
                # Expand any unexpanded leaf — whether freshly created here or
                # a transposition created (but not yet expanded) on another
                # path. The old `child is fresh` guard skipped the latter,
                # leaving leaf_value at its 0.0 default and backing up a bogus
                # zero. (Matches _select_leaf_with_vloss's needs_eval logic.)
                if not child.expanded:
                    self._expand(child, board)
                self._link_child(node, action, child)
                path.append(child)
                node = child
                break
            else:
                path.append(child)
                node = child

        # Every node reaching here has been through _expand — the loop only
        # descends into expanded nodes, and the break-path expands its leaf.
        # _expand sets leaf_value: the net's value for a non-terminal node,
        # or terminal_value for a terminal one.
        leaf_value = node.leaf_value
        leaf_player = node.player_to_move

        # Backprop.
        for n in path:
            n.N += 1
            n.W += leaf_value if n.player_to_move == leaf_player else -leaf_value
