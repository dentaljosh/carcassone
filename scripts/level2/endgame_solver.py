"""Exact endgame solver for 2-player Carcassonne (Base+Farmers) — L2-3.

Solves the final K tiles of a game to label the GROUND-TRUTH optimal move at a
position, in two modes (see measurement/level2/LEVEL2_L23_PROTOCOL.md):

  mode="clairvoyant" : perfect-information minimax over the KNOWN real future
                       deck order ([next_tile]+state.deck), alpha-beta. The
                       optimum for clairvoyant agents (= production search).
  mode="marginalized": expectiminimax — at each draw a CHANCE node marginalizes
                       the unknown remaining bag (uniform over the remaining-tile
                       multiset). The honest game value under hidden future.
                       (PREFERRED ground truth.)

Leaf value = the REAL final score differential `flat_base_score(state, 0)` =
scores[0]-scores[1] with exact final (farm) scoring — NOT a heuristic leaf.
Minimax perspective is fixed to player 0: P0-to-move maximizes, P1 minimizes.

Returns per-position the optimal value V*, the optimal-action SET, and the exact
value of EVERY legal root action (so a regret harness can score any agent move:
regret = V*(best) - V*(agent move), in raw points, >= 0).

Pure CPU, no net. Resumable/parallel via the regret harness, not here.
"""
from __future__ import annotations

import math
import os
import sys
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carcassonne_ai.flat_leaf import flat_base_score
from carcassonne_ai.game_wrapper import Board, Game
from wingedsheep.carcassonne.objects.game_phase import GamePhase

_TILES = GamePhase.TILES
_MEEPLES = GamePhase.MEEPLES
_TIE = 1e-6  # float tolerance for optimal-set membership in the marginalized mode

# Alpha-beta TT bound flags (clairvoyant pruning path only).
_EXACT, _LOWER, _UPPER = 0, 1, 2


class BudgetExceeded(Exception):
    """Raised when a solve exceeds its node budget (position skipped, logged)."""


@dataclass
class SolveResult:
    mode: str
    value: float                       # V* (P0-perspective score diff under optimal play)
    to_move: int                       # player to move at the root
    optimal_actions: list[int]         # actions achieving V* (mover's best)
    child_values: dict[int, float]     # exact value of every legal root action
    nodes: int
    completed: bool                    # False if budget hit (then fields are partial)


def tile_key(tile) -> str:
    """Type identity for the remaining-bag multiset (interchangeable tiles)."""
    return tile.description


def _terminal(board: Board) -> bool:
    return board.state.next_tile is None


def _legal(game: Game, board: Board) -> np.ndarray:
    return np.flatnonzero(game.get_valid_moves(board))


def _clone_with_tile(board: Board, tile, remaining_deck: list) -> Board:
    """A copy of `board` whose in-hand tile is `tile` and future deck is
    `remaining_deck`. Board layout (offset/centroid) is unchanged by a deck
    swap, so we reuse it — only the engine state's next_tile/deck differ."""
    import copy
    st = copy.deepcopy(board.state)
    st.next_tile = tile
    st.deck = list(remaining_deck)
    return Board(state=st, total_tiles=board.total_tiles, offset=board.offset,
                 sum_row=board.sum_row, sum_col=board.sum_col, tile_count=board.tile_count)


class _Solver:
    """Plain minimax (clairvoyant) / expectiminimax (marginalized) with an
    EXACT-value transposition table. No alpha-beta — the TT collapses the
    heavy endgame move-order transpositions, and storing exact subtree values
    (vs alpha-beta bound-flags) keeps a GROUND-TRUTH solver simple to trust.
    TT key = observable state (string_representation) + the deck ORDER
    (clairvoyant) or the sorted bag MULTISET (marginalized = the spec's V5
    no-leak key: states differing only in unrevealed order collide)."""

    def __init__(self, game: Game, mode: str, budget: int, alphabeta: bool = False):
        assert mode in ("clairvoyant", "marginalized")
        # Alpha-beta is EXACT (it only prunes provably-irrelevant subtrees), but
        # it is sound only for pure minimax — chance (expectation) nodes have no
        # cutoff bound, so it is restricted to the clairvoyant mode. The exact
        # no-prune `_value` path is retained as the validation oracle (the AB
        # result must match it bit-for-bit on the already-solved K2/K3 suites).
        assert not (alphabeta and mode == "marginalized"), \
            "alpha-beta is clairvoyant-only (chance nodes break minimax cutoffs)"
        self.game = game
        self.mode = mode
        self.budget = budget
        self.alphabeta = alphabeta
        self.nodes = 0
        self.tt: dict = {}

    def _tick(self):
        self.nodes += 1
        if self.nodes > self.budget:
            raise BudgetExceeded(f"> {self.budget} nodes")

    def _key(self, board: Board):
        sr = self.game.string_representation(board)
        descs = (t.description for t in board.state.deck)
        deck = tuple(descs) if self.mode == "clairvoyant" else tuple(sorted(descs))
        return (sr, deck)

    def _value(self, board: Board) -> float:
        if _terminal(board):
            return float(flat_base_score(board.state, 0))
        key = self._key(board)
        cached = self.tt.get(key)
        if cached is not None:
            return cached
        self._tick()
        mover = board.state.current_player
        was_meeples = (board.state.phase == _MEEPLES)
        vals = []
        for a in _legal(self.game, board):
            nb, _ = self.game.get_next_state(board, int(a))
            if self.mode == "marginalized" and was_meeples and not _terminal(nb):
                vals.append(self._chance(nb))   # marginalize the just-happened draw
            else:
                vals.append(self._value(nb))
        v = max(vals) if mover == 0 else min(vals)
        self.tt[key] = v
        return v

    def _chance(self, nb: Board) -> float:
        """`nb` is post-draw; treat the just-drawn tile as random and take the
        expectation over the remaining-bag multiset (group by type)."""
        bag = [nb.state.next_tile] + list(nb.state.deck)
        total = len(bag)
        groups: dict[str, list] = {}
        for t in bag:
            groups.setdefault(tile_key(t), []).append(t)
        exp = 0.0
        for tiles in groups.values():
            rep = tiles[0]
            remaining = [t for t in bag if t is not rep]  # drop one instance
            child = _clone_with_tile(nb, rep, remaining)
            exp += (len(tiles) / total) * self._value(child)
        return exp

    def _value_ab(self, board: Board, alpha: float, beta: float) -> float:
        """Exact alpha-beta minimax for the clairvoyant mode. Returns V* of the
        subtree when called with a full window (alpha=-inf, beta=+inf); inside a
        narrowed window it returns a fail-soft bound that the TT flag records.
        P0 maximizes, P1 minimizes (same convention as `_value`)."""
        if _terminal(board):
            return float(flat_base_score(board.state, 0))
        key = self._key(board)
        cached = self.tt.get(key)
        if cached is not None:
            val, flag = cached
            if flag == _EXACT:
                return val
            if flag == _LOWER:
                if val >= beta:
                    return val
                alpha = val if val > alpha else alpha
            elif flag == _UPPER:
                if val <= alpha:
                    return val
                beta = val if val < beta else beta
            if alpha >= beta:
                return val
        self._tick()
        mover = board.state.current_player
        a0, b0 = alpha, beta
        if mover == 0:                      # maximizer
            best = -math.inf
            for a in _legal(self.game, board):
                nb, _ = self.game.get_next_state(board, int(a))
                v = self._value_ab(nb, alpha, beta)
                if v > best:
                    best = v
                if best > alpha:
                    alpha = best
                if alpha >= beta:
                    break                   # beta cutoff
        else:                               # minimizer
            best = math.inf
            for a in _legal(self.game, board):
                nb, _ = self.game.get_next_state(board, int(a))
                v = self._value_ab(nb, alpha, beta)
                if v < best:
                    best = v
                if best < beta:
                    beta = best
                if beta <= alpha:
                    break                   # alpha cutoff
        # Fail-soft bound classification for the TT.
        if best <= a0:
            flag = _UPPER                   # failed low -> best is an upper bound
        elif best >= b0:
            flag = _LOWER                   # failed high -> best is a lower bound
        else:
            flag = _EXACT
        self.tt[key] = (best, flag)
        return best


def solve(game: Game, board: Board, mode: str = "marginalized",
          budget: int = 4_000_000, alphabeta: bool = False) -> SolveResult:
    """Solve the position. Evaluates EVERY legal root action exactly (no
    cross-action pruning at the root) so regret can be scored for any move.

    `alphabeta` (clairvoyant only) prunes inside each root child's subtree —
    every child is solved with a FULL window (-inf, +inf) so its returned value
    is exact (cross-sibling narrowing would only bound the suboptimal moves,
    which the regret harness still needs). Exact-equal to the no-prune path."""
    s = _Solver(game, mode, budget, alphabeta=alphabeta)
    to_move = board.state.current_player
    was_meeples = (board.state.phase == _MEEPLES)
    legal = _legal(game, board)
    child_values: dict[int, float] = {}
    for a in legal:
        a = int(a)
        nb, _ = game.get_next_state(board, a)
        if _terminal(nb):
            child_values[a] = float(flat_base_score(nb.state, 0))
        elif mode == "marginalized" and was_meeples:
            child_values[a] = s._chance(nb)
        elif alphabeta:                       # clairvoyant + pruning (full window)
            child_values[a] = s._value_ab(nb, -math.inf, math.inf)
        else:
            child_values[a] = s._value(nb)
    if not child_values:
        raise ValueError("no legal actions at root")
    vstar = max(child_values.values()) if to_move == 0 else min(child_values.values())
    tol = _TIE if mode == "marginalized" else 0
    optimal = [a for a, v in child_values.items() if abs(v - vstar) <= tol]
    return SolveResult(mode=mode, value=float(vstar), to_move=to_move,
                       optimal_actions=optimal, child_values=child_values,
                       nodes=s.nodes, completed=True)


def regret_of(res: SolveResult, action: int) -> float:
    """Points the `action` loses vs optimal, from the mover's perspective (>=0).
    Returns +inf if the action is not among the scored legal actions."""
    if action not in res.child_values:
        return math.inf
    v = res.child_values[action]
    # mover 0 maximizes the P0-perspective value; mover 1 minimizes it.
    return (res.value - v) if res.to_move == 0 else (v - res.value)
