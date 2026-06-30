"""Independent, out-of-ecosystem rollout-MCTS opponent (Step 7 stage-1).

WHY THIS EXISTS
---------------
Every current strength ruler in this repo — HeuristicMCTS, h6400_v2.9, the
trained checkpoints — derives its leaf value from the SAME hand-crafted v2.7/v2.9
``virtual_score`` evaluation. Beating those rulers may only prove we exploit that
one heuristic's blind spots, not that we are genuinely strong. This module
provides an opponent whose EVALUATION shares ZERO DNA with the v2.7/v2.9 leaf:
its only value signal is the outcome of random/light playouts to terminal — the
Ameneyro et al. 2020 baseline ("Playing Carcassonne with Monte Carlo Tree
Search", arXiv:2009.12974).

HARD CONSTRAINT (enforced by construction)
------------------------------------------
This player NEVER calls ``virtual_score`` / ``virtual_score_v2`` / ``flat_leaf``
/ ``make_v25_value_wrapper`` / any network. It reuses the project's vanilla
``mcts.MCTS`` class, whose ``_rollout`` is a pure uniform-random playout to game
end (mcts.py lines ~233-269) and whose only imports are stdlib + numpy +
``game_wrapper``. The RAVE variant subclasses that same leaf-free engine and adds
only AMAF bookkeeping; it introduces no heuristic. There is intentionally no
import of any leaf module in this file. (Verified: ``grep -n
"virtual_score\\|flat_leaf\\|leaf_v29\\|network\\|make_v25" ameneyro_mcts.py``
returns nothing.)

ALGORITHM (Ameneyro et al. 2020)
--------------------------------
Vanilla rollout MCTS:
  - Selection: UCT, argmax_i( Q_i + c * sqrt(ln N_parent / n_i) ). Unvisited
    children are taken first (UCT convention). Already implemented in MCTS.
  - Expansion: add one untried child on first visit to a leaf.
  - Simulation: uniform-random legal moves to a terminal state.
  - Backprop: the terminal score differential (perspective-correct) up the path.
Optional MCTS-RAVE (``use_rave=True``): the All-Moves-As-First (AMAF) variant.
Each node also tracks, per action a, the value of every simulation in which a was
played anywhere below the node (not just as the immediate child). Selection
blends the UCT estimate Q with the AMAF estimate Q_amaf via a schedule
  beta = sqrt( k / (3 * N_child + k) )            (Silver/Gelly minimum-MSE form)
so RAVE dominates early (few visits) and decays to pure UCT as a child is
sampled more. ``rave_k`` is the equivalence parameter (visits at which UCT and
AMAF are weighted equally-ish); default 1000, exposed as a param.

CLAIRVOYANCE REGIME
-------------------
Matches the rest of the project's MCTS exactly: search rolls out against the
engine's pre-shuffled, seeded deck (single-determinization / clairvoyant). No
fair-information deck re-sampling — that is a separate later step. This keeps the
comparison apples-to-apples with HeuristicMCTS / NeuralMCTS.

PLAYER INTERFACE
----------------
Exposes BOTH project player contracts so it drops into either eval harness
unchanged:
  - ``best_action(board) -> int``        (the mcts.MCTS / NeuralMCTS contract;
    callers do ``p.clear(); p.best_action(board)`` between root moves — see
    scripts/eval_rule_player.py and scripts/ladder_rung_eval.py)
  - ``choose_action(game, board, valid_mask) -> int``  (the RuleBasedPlayer
    contract — handles its own per-move tree clearing internally)
"""
from __future__ import annotations

import math
import random

import numpy as np

from .game_wrapper import Board, Game
# NOTE: the ONLY MCTS import is the leaf-free vanilla engine. We deliberately do
# NOT import HeuristicMCTS / NeuralMCTS / any virtual_score / flat_leaf module.
from .mcts import MCTS


# Sane defaults. The paper uses an exploration constant near sqrt(2)~1.41; the
# project's vanilla MCTS uses C=3 (mcts.DEFAULT_C). We default to the literature
# value 1.41 for an honestly "out-of-ecosystem" baseline, but expose it so a
# sweep can move it. (Tuning of c_uct is an open follow-up — see module docstring
# / the deliverable notes; 1.41 is a reasonable, paper-aligned starting point.)
DEFAULT_C_UCT = 1.41421356  # sqrt(2)
DEFAULT_SIMS = 100
DEFAULT_RAVE_K = 1000.0  # AMAF/UCT equivalence parameter (Silver & Gelly)


class _RaveMCTS(MCTS):
    """Vanilla rollout MCTS + MCTS-RAVE (AMAF) selection.

    Subclasses the leaf-free :class:`mcts.MCTS`: the rollout is inherited
    unchanged (pure uniform-random playout to terminal — NO heuristic). The only
    additions are (a) per-node AMAF accumulators ``amaf_W`` / ``amaf_N`` keyed by
    action, (b) recording the actions played during selection+rollout so they can
    be credited as AMAF to every ancestor, and (c) a beta-weighted UCT+AMAF
    selection rule overriding ``_select_child``.

    AMAF semantics: for a node n and an action a, ``amaf_N[a]`` counts the
    simulations passing through n in which a was played at any later point
    (deeper selection step, expansion, or rollout). ``amaf_W[a]`` accumulates
    those simulations' values from n.player_to_move's perspective.
    """

    def __init__(self, *args, rave_k: float = DEFAULT_RAVE_K, **kwargs):
        super().__init__(*args, **kwargs)
        self.rave_k = float(rave_k)
        # node.state_key -> {action_idx: [W, N]} AMAF stats (n.player_to_move POV)
        self._amaf: dict[str, dict[int, list[float]]] = {}

    def clear(self) -> None:  # type: ignore[override]
        super().clear()
        self._amaf.clear()

    def _amaf_for(self, key: str) -> dict[int, list[float]]:
        d = self._amaf.get(key)
        if d is None:
            d = {}
            self._amaf[key] = d
        return d

    def _select_child(self, node):  # type: ignore[override]
        """Beta-weighted UCT + AMAF selection.

        score = (1-beta)*Q_uct + beta*Q_amaf + c*sqrt(ln N_parent / n_child)
        with beta = sqrt(k / (3*n_child + k)). Unvisited children (n==0 and no
        AMAF data) are taken first, exactly like vanilla UCT.
        """
        log_parent = math.log(max(node.N, 1))
        amaf = self._amaf.get(node.state_key, {})
        best_score = -math.inf
        best_action = -1
        best_child = None
        for action, child in node.children.items():
            a_stat = amaf.get(action)
            has_amaf = a_stat is not None and a_stat[1] > 0
            if child.N == 0 and not has_amaf:
                # Never-sampled and no AMAF evidence — take it (UCT convention).
                return action, child

            # UCT exploitation term (node.player_to_move's perspective).
            if child.N > 0:
                q_uct = child.Q if child.player_to_move == node.player_to_move else -child.Q
            else:
                q_uct = 0.0
            # AMAF exploitation term — already stored from node.player_to_move's POV.
            q_amaf = (a_stat[0] / a_stat[1]) if has_amaf else q_uct

            n_child = child.N
            beta = math.sqrt(self.rave_k / (3.0 * n_child + self.rave_k)) if (n_child or has_amaf) else 1.0
            exploit = (1.0 - beta) * q_uct + beta * q_amaf
            explore = self.c * math.sqrt(log_parent / n_child) if n_child > 0 else math.inf
            score = exploit + explore
            if score > best_score:
                best_score, best_action, best_child = score, action, child
        assert best_child is not None
        return best_action, best_child

    def _simulate(self, root_board: Board, root) -> None:  # type: ignore[override]
        """One RAVE iteration: select -> expand -> rollout -> backprop UCT+AMAF.

        Mirrors MCTS._simulate but records the actions taken (selection,
        expansion, and rollout) so they can be credited as AMAF to every node on
        the path. The rollout itself is the inherited leaf-free random playout
        (re-implemented here only to also surface the actions it played).
        """
        path = [root]
        played: list[int] = []  # actions taken from each node on the path, in order
        board = root_board
        node = root

        # 1. Selection.
        while node.is_fully_expanded and not node.is_terminal:
            action, node = self._select_child(node)
            board, _ = self.game.get_next_state(board, action)
            played.append(action)
            path.append(node)

        # 2. Expansion.
        if not node.is_terminal and node.untried_actions:
            action = self.rng.choice(node.untried_actions)
            node.untried_actions.remove(action)
            board, _ = self.game.get_next_state(board, action)
            child = self._get_or_create_node(board)
            child.parent = node
            child.parent_action = action
            node.children[action] = child
            played.append(action)
            path.append(child)
            node = child

        # 3. Simulation — random rollout, recording actions for AMAF credit.
        leaf_player = node.player_to_move
        leaf_value, rollout_actions = self._rollout_record(board)

        # 4a. Standard UCT backprop (N, W per node, perspective-flipped).
        for n in path:
            n.N += 1
            n.W += leaf_value if n.player_to_move == leaf_player else -leaf_value

        # 4b. AMAF backprop. For each node on the path, every action that was
        # played at or below it (the suffix of `played` from that node's
        # position onward, plus the rollout actions) gets AMAF credit, valued
        # from that node's player_to_move perspective.
        # `played[i]` is the action taken FROM path[i] toward path[i+1].
        all_future = played + rollout_actions
        for i, n in enumerate(path):
            if n.is_terminal:
                continue
            v = leaf_value if n.player_to_move == leaf_player else -leaf_value
            d = self._amaf_for(n.state_key)
            # Actions taken from this node onward. De-dupe so an action that
            # recurs in a long rollout is credited once per simulation (AMAF
            # is "as-first": first occurrence in the simulation).
            seen: set[int] = set()
            for a in all_future[i:]:
                if a in seen:
                    continue
                seen.add(a)
                stat = d.get(a)
                if stat is None:
                    d[a] = [v, 1.0]
                else:
                    stat[0] += v
                    stat[1] += 1.0

    def _rollout_record(self, board: Board) -> tuple[float, list[int]]:
        """Identical to MCTS._rollout (pure uniform-random playout to terminal)
        but also returns the sequence of actions played, for AMAF credit. NO
        heuristic leaf — value is the engine's terminal score differential."""
        import copy as _copy

        from .mcts import ROLLOUT_DEPTH_LIMIT

        scratch = Board(
            state=_copy.deepcopy(board.state),
            total_tiles=board.total_tiles,
            offset=board.offset,
            sum_row=board.sum_row,
            sum_col=board.sum_col,
            tile_count=board.tile_count,
        )
        leaf_player = scratch.state.current_player
        actions: list[int] = []
        steps = 0
        while True:
            v = self.game.get_game_ended(scratch, leaf_player)
            if v != 0.0:
                return v, actions
            if steps >= ROLLOUT_DEPTH_LIMIT:
                return (self.game.get_game_ended(scratch, leaf_player) or 0.0), actions
            mask = self.game.get_valid_moves(scratch)
            legal = np.flatnonzero(mask)
            action = int(self.rng.choice(legal))
            self.game.apply_action_inplace(scratch, action)
            actions.append(action)
            steps += 1


class AmeneyroMCTSPlayer:
    """Rollout-MCTS player (Ameneyro et al. 2020) — leaf value from random
    playouts only, ZERO v2.7/v2.9 DNA.

    Drops into the project eval harness via either contract:
      * ``best_action(board) -> int`` (the MCTS-family contract; do
        ``p.clear()`` between root moves as the harness already does for
        MCTS/HeuristicMCTS/NeuralMCTS — see scripts/eval_rule_player.py)
      * ``choose_action(game, board, valid_mask) -> int`` (the RuleBasedPlayer
        contract; clears its own tree each move so it is stateless across moves)

    Args:
        sims: playout budget (UCT iterations) per move. Default 100.
        c_uct: UCT exploration constant. Default sqrt(2) ~ 1.41 (paper-aligned).
        rollout_policy: only 'random' is supported (the canonical independent
            baseline). Any other value raises — we will NOT silently substitute a
            heuristic rollout, which would reintroduce v2.7/v2.9 circularity.
        use_rave: enable MCTS-RAVE (AMAF) selection. Default False (vanilla).
        rave_k: RAVE equivalence parameter (only used when use_rave=True).
        seed: RNG seed for rollouts / expansion tie-breaks (reproducible).

    A note on the Game it searches with: pass ``game`` to share the harness's
    Game instance (recommended — keeps window_size/scope identical), or omit it
    and the player builds its own ``Game(enable_legal_moves_cache=True)``.
    """

    def __init__(
        self,
        game: Game | None = None,
        sims: int = DEFAULT_SIMS,
        c_uct: float = DEFAULT_C_UCT,
        rollout_policy: str = "random",
        use_rave: bool = False,
        rave_k: float = DEFAULT_RAVE_K,
        seed: int | None = None,
    ):
        if rollout_policy != "random":
            raise ValueError(
                f"rollout_policy={rollout_policy!r} unsupported. Only 'random' is "
                "allowed — a heuristic rollout would reintroduce the v2.7/v2.9 leaf "
                "this opponent exists to avoid."
            )
        self.sims = int(sims)
        self.c_uct = float(c_uct)
        self.rollout_policy = rollout_policy
        self.use_rave = bool(use_rave)
        self.rave_k = float(rave_k)
        self.seed = seed
        self._game = game if game is not None else Game(enable_legal_moves_cache=True)
        if self.use_rave:
            self._engine: MCTS = _RaveMCTS(
                game=self._game, simulations=self.sims, c=self.c_uct,
                seed=seed, rave_k=self.rave_k,
            )
        else:
            self._engine = MCTS(
                game=self._game, simulations=self.sims, c=self.c_uct, seed=seed,
            )

    # --- MCTS-family contract -------------------------------------------------

    def search(self, board: Board) -> dict[int, int]:
        return self._engine.search(board)

    def best_action(self, board: Board) -> int:
        """Run a search from `board` and return the best LEGAL root action.

        Matches the mcts.MCTS contract: the harness is expected to call
        ``clear()`` between root moves (it does for the MCTS family). Returns a
        guaranteed-legal action.

        Robustness note (upstream bug worked around here): the shared
        ``mcts.MCTS``/``HeuristicMCTS`` engine can occasionally surface a root
        child action that is NOT legal at the current board. The cause is a
        ``Game.string_representation`` transposition collision in the meeples
        phase — two boards with different window offsets collide on one key, so
        action indices encoded against one offset leak into a node decoded
        against another. It reproduces identically with the production
        HeuristicMCTS ladder opponent (action range ~2506-2507, meeples phase);
        the existing eval harness merely raises on it (eval_rule_player.py:287).
        Rather than fix string_representation (which would shift every prior
        ladder result), this player restricts the pick to the live legal mask so
        it never returns an illegal action.
        """
        return self._best_legal_action(board)

    def _fresh_legal(self, board: Board) -> set[int]:
        """Compute the legal-action set DIRECTLY from the engine, bypassing the
        Game's legal-moves cache.

        Why bypass the cache: the cache is keyed by ``string_representation``,
        which collides across boards that differ only in window offset (the
        meeples-phase collision documented in best_action). A collision returns a
        mask encoded against the WRONG offset, so the cached set can be subtly
        wrong (e.g. {2506,2508,2510} when the engine truth is {2507,2509,2510}).
        Recomputing here makes the player's legality decision authoritative and
        offset-correct regardless of cache state. (Cheap: one engine enumeration.)
        """
        from wingedsheep.carcassonne.utils.action_util import ActionUtil

        from .action_space import WindowOverflowError, encode

        legal: set[int] = set()
        for action in ActionUtil.get_possible_actions(board.state):
            try:
                idx = encode(action, board.offset, board.state.phase.value)
            except WindowOverflowError:
                continue
            legal.add(int(idx))
        return legal

    def _best_legal_action(self, board: Board) -> int:
        """Run a search and return the best action that is ALSO legal NOW.

        Picks among root children using the same priority as mcts.MCTS.best_action
        (Q from root perspective, tie-broken by visit count N), but filtered to
        the FRESH (uncached, offset-correct) legal set. Falls back to the most-
        visited legal child, then to any legal action, so it is robust to the
        upstream legal-moves-cache poisoning described in best_action's docstring.
        """
        eng = self._engine
        legal = self._fresh_legal(board)
        root_key = self.game.string_representation(board)
        root = eng._nodes.get(root_key)
        if root is None or root.N == 0:
            eng.search(board)
            root = eng._nodes[root_key]

        best = None
        best_score = None
        seen_children: set[int] = set()
        for a in sorted(root.children):
            if a not in legal:
                continue  # drop leaked illegal actions (upstream collision)
            child = root.children[a]
            if child.N <= 0 or id(child) in seen_children:
                continue
            seen_children.add(id(child))
            q = child.Q if child.player_to_move == root.player_to_move else -child.Q
            score = (q, child.N)
            if best_score is None or score > best_score:
                best_score, best = score, a
        if best is not None:
            return int(best)
        # No visited legal child (pathological — e.g. all visits went to leaked
        # illegal actions). Return any legal action deterministically.
        return int(min(legal))

    @property
    def game(self) -> Game:
        return self._game

    def clear(self) -> None:
        """Drop the search tree (and AMAF stats, if RAVE). Call between root
        moves, exactly as the harness does for the other MCTS players."""
        self._engine.clear()

    # --- RuleBasedPlayer contract --------------------------------------------

    def choose_action(self, game: Game, board: Board, valid_mask: np.ndarray) -> int:
        """RuleBasedPlayer-style entry point. Self-clears the tree each move so
        the player is stateless across moves (the harness for this contract does
        NOT call clear() itself). `valid_mask` is honored as the legal set; the
        returned action is always in it.

        Note: `game` is accepted for interface compatibility but the search runs
        on the player's own engine-bound Game (same scope). The forced-move
        shortcut below uses `valid_mask` directly so it never even searches when
        there is a single legal action.
        """
        legal = np.flatnonzero(valid_mask)
        if len(legal) == 0:
            raise RuntimeError("no legal moves — game should have ended")
        if len(legal) == 1:
            return int(legal[0])
        self._engine.clear()
        # _best_legal_action restricts to the FRESH (uncached, offset-correct)
        # legal set — authoritative even when `valid_mask` is a cache-poisoned
        # mask (see best_action's docstring). We deliberately do NOT raise on
        # `valid_mask[action]` being False: a False there means the *passed mask*
        # is the poisoned one, not that our action is illegal.
        return int(self._best_legal_action(board))
