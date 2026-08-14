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

import hashlib
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

# E1 (measurement/e1_winobj_20260814/DESIGN.md §1): tolerance on the WIN
# component of the lexicographic (w, m) value — w is an expectation of
# {0, 0.5, 1} over rational bag probabilities, so mathematically-equal w's can
# differ by float-order noise; without a tolerance the margin tiebreak would be
# decided by that noise instead of by margin.
_WIN_TIE = 1e-9


def _outcome(m: float) -> float:
    """The terminal WIN lattice, P0 POV: win > draw > loss, draw = half a win
    (the lattice the eval harness scores W/D/L on). `m` is an exact integral
    score differential at terminals, so the comparisons are exact."""
    return 1.0 if m > 0 else (0.5 if m == 0 else 0.0)


def _lex_better(x: tuple, v: tuple, maximize: bool) -> bool:
    """Lexicographic (w, m) comparison with _WIN_TIE on the win component.
    True when `x` is strictly better than `v` for the mover; the caller only
    replaces on strict improvement (keep-first scan, Python max/min shape)."""
    dw = x[0] - v[0]
    if maximize:
        return dw > _WIN_TIE or (abs(dw) <= _WIN_TIE and x[1] > v[1])
    return dw < -_WIN_TIE or (abs(dw) <= _WIN_TIE and x[1] < v[1])

# Alpha-beta TT bound flags (clairvoyant pruning path only).
_EXACT, _LOWER, _UPPER = 0, 1, 2


class BudgetExceeded(Exception):
    """Raised when a solve exceeds its node budget (position skipped, logged)."""


@dataclass
class SolveResult:
    mode: str
    value: float                       # V* (P0-perspective score diff under optimal play;
                                       # under objective="win": the MARGIN component of the
                                       # lexicographic optimum, i.e. E[margin] under the
                                       # win-first policy)
    to_move: int                       # player to move at the root
    optimal_actions: list[int]         # actions achieving V* (mover's best)
    child_values: dict[int, float]     # exact value of every legal root action
    nodes: int
    completed: bool                    # False if budget hit (then fields are partial)
    # E1 win objective only (None/None under objective="margin" — the liveness
    # discriminator; additive with defaults so every existing constructor and
    # caller is untouched):
    win_value: float | None = None                 # E[outcome] of the optimum
    child_win_values: dict | None = None           # per-action E[outcome]
    objective: str = "margin"


def tile_key(tile) -> str:
    """Type identity for the remaining-bag multiset (interchangeable tiles)."""
    return tile.description


def _terminal(board: Board) -> bool:
    return board.state.next_tile is None


def _legal(game: Game, board: Board) -> np.ndarray:
    return np.flatnonzero(game.get_valid_moves(board))


def _drew_a_tile(board: Board, nb: Board, was_meeples: bool) -> bool:
    """Did the transition `board -> nb` DRAW a replacement tile from the bag?

    Two transitions draw. The MEEPLES-phase one (`was_meeples`) has always been
    marginalized. The second is the F9/A3 redraw: under `draw_rule="redraw"` a
    TILES-phase Pass sets the unplaceable tile aside and draws again, and that
    draw is a chance event of exactly the same kind.

    Marginalizing it is REQUIRED, not cosmetic: `_key` hashes the SORTED bag in
    marginalized mode (the multiset is the information set), so if the value of
    a redraw depended on which tile happened to sit at the front of `state.deck`
    the TT would return one deck order's answer for another's. Marginalizing
    restores order-independence and makes the key sound again.

    (The same unsoundness is latent on the flag-OFF discard path, which also
    pops the front without marginalizing. It is deliberately NOT fixed: flags
    off must stay byte-identical, and the gate that proves it would fail if
    this returned True there. See spec docs/F9_BUILD_SPEC_20260802.md §A3.)
    """
    if was_meeples:
        return True
    return (nb.state.redraw_unplaceable
            and len(nb.state.set_aside_tiles) > len(board.state.set_aside_tiles))


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
        # E1 win mode's (w, m) table. Exactly one of tt/tt_win is used per
        # solve; tt_cap applies to whichever it is.
        self.tt_win: dict = {}
        # Optional TT entry cap (memory bound). 0/unset = unlimited. When the table
        # is full we FREEZE it: new keys are not inserted (so the dict stops growing
        # -> bounded RSS), but existing keys may still be updated (no growth) and are
        # still read. This is correctness-NEUTRAL: the TT is pure memoization, so a
        # missing entry only forces recomputation -> more nodes, identical values
        # (and AB bound flags stay valid). It trades memory for node count.
        self.tt_cap = int(os.environ.get("CARCASSONNE_TT_CAP", "0"))

    def _put(self, key, val) -> None:
        if key in self.tt or not self.tt_cap or len(self.tt) < self.tt_cap:
            self.tt[key] = val

    def _tick(self):
        self.nodes += 1
        if self.nodes > self.budget:
            raise BudgetExceeded(f"> {self.budget} nodes")

    def _key(self, board: Board):
        sr = self.game.string_representation(board)
        descs = (t.description for t in board.state.deck)
        deck = tuple(descs) if self.mode == "clairvoyant" else tuple(sorted(descs))
        # COMPACT key: hash the (sr, deck) identity to a 128-bit digest (~16B) instead
        # of storing the ~7KB `string_representation` string per TT entry. The TT holds
        # ~1M entries on hard positions, so fat string keys are what blow RSS to ~12GB
        # (measured: sr ~6876 chars/key); the 16B digest cuts per-entry ~140x -> RSS
        # collapses, letting workers run uncapped at high W. 128-bit -> collision prob
        # ~1e-27 at 1M entries (safe for a ground-truth solver). Semantically identical
        # to the (sr, deck) tuple key except for (astronomically unlikely) collisions;
        # node counts + V* are bit-identical to the string-key solver (validated). A
        # true incremental Zobrist hash would also skip building `sr`, but that's a
        # bigger change; this captures the entire MEMORY win for ~free CPU (blake2b on
        # an already-computed 7KB string is ~microseconds vs the ~ms/node solve cost).
        h = hashlib.blake2b(digest_size=16)
        h.update(sr.encode())
        h.update(b"\x00")
        h.update("\x1f".join(deck).encode())
        return h.digest()

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
            if (self.mode == "marginalized" and not _terminal(nb)
                    and _drew_a_tile(board, nb, was_meeples)):
                vals.append(self._chance(nb))   # marginalize the just-happened draw
            else:
                vals.append(self._value(nb))
        v = max(vals) if mover == 0 else min(vals)
        self._put(key, v)
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

    # ---- E1 win-objective mirror of _value/_chance -------------------------
    # A PARALLEL pair, not a parameterization of the margin pair: the margin
    # path must stay untouched code (flag-off bit-identity is structural).
    # Node value is the pair (w, m): w = E[outcome] (win 1 / draw 0.5 / loss 0,
    # P0 POV), m = E[margin] under the win-first policy. Decision nodes compare
    # lexicographically (w first within _WIN_TIE, then m); chance nodes take
    # component-wise expectations with the SAME grouping and accumulation order
    # as _chance. See measurement/e1_winobj_20260814/DESIGN.md §1.

    def _put_win(self, key, val) -> None:
        if key in self.tt_win or not self.tt_cap or len(self.tt_win) < self.tt_cap:
            self.tt_win[key] = val

    def _value_win(self, board: Board) -> tuple:
        if _terminal(board):
            m = float(flat_base_score(board.state, 0))
            return (_outcome(m), m)
        key = self._key(board)
        cached = self.tt_win.get(key)
        if cached is not None:
            return cached
        self._tick()
        mover = board.state.current_player
        was_meeples = (board.state.phase == _MEEPLES)
        vals = []
        for a in _legal(self.game, board):
            nb, _ = self.game.get_next_state(board, int(a))
            if not _terminal(nb) and _drew_a_tile(board, nb, was_meeples):
                vals.append(self._chance_win(nb))
            else:
                vals.append(self._value_win(nb))
        v = vals[0]
        for x in vals[1:]:
            if _lex_better(x, v, mover == 0):
                v = x
        self._put_win(key, v)
        return v

    def _chance_win(self, nb: Board) -> tuple:
        bag = [nb.state.next_tile] + list(nb.state.deck)
        total = len(bag)
        groups: dict[str, list] = {}
        for t in bag:
            groups.setdefault(tile_key(t), []).append(t)
        ew = 0.0
        em = 0.0
        for tiles in groups.values():
            rep = tiles[0]
            remaining = [t for t in bag if t is not rep]
            child = _clone_with_tile(nb, rep, remaining)
            w, m = self._value_win(child)
            p = len(tiles) / total
            ew += p * w
            em += p * m
        return (ew, em)

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
        self._put(key, (best, flag))
        return best


def solve(game: Game, board: Board, mode: str = "marginalized",
          budget: int = 4_000_000, alphabeta: bool = False,
          objective: str = "margin") -> SolveResult:
    """Solve the position. Evaluates EVERY legal root action exactly (no
    cross-action pruning at the root) so regret can be scored for any move.

    `alphabeta` (clairvoyant only) prunes inside each root child's subtree —
    every child is solved with a FULL window (-inf, +inf) so its returned value
    is exact (cross-sibling narrowing would only bound the suboptimal moves,
    which the regret harness still needs). Exact-equal to the no-prune path.

    `objective` (E1, measurement/e1_winobj_20260814/DESIGN.md): "margin"
    (default — the untouched incumbent code path, bit-identical) or "win" —
    node value is the lexicographic pair (E[outcome], E[margin]) with the
    margin breaking outcome ties (win > draw > loss, draw = half a win).
    MARGINALIZED-ONLY: a clairvoyant future is deterministic and outcome is a
    monotone transform of the deterministic margin, so margin-max is already
    win-optimal there — a clairvoyant "win mode" would be a live-looking no-op
    flag, hence the loud assert. At the deployed exact_max_k=2 the two
    objectives PROVABLY coincide (every chance bag is a singleton; DESIGN §2);
    divergence requires K>=3."""
    assert objective in ("margin", "win"), f"objective must be margin|win, got {objective!r}"
    assert not (objective == "win" and mode != "marginalized"), \
        "objective='win' is marginalized-only (clairvoyant margin-max is already win-optimal)"
    s = _Solver(game, mode, budget, alphabeta=alphabeta)
    to_move = board.state.current_player
    was_meeples = (board.state.phase == _MEEPLES)
    legal = _legal(game, board)

    if objective == "win":
        pairs: dict[int, tuple] = {}
        for a in legal:
            a = int(a)
            nb, _ = game.get_next_state(board, a)
            if _terminal(nb):
                m = float(flat_base_score(nb.state, 0))
                pairs[a] = (_outcome(m), m)
            elif _drew_a_tile(board, nb, was_meeples):
                pairs[a] = s._chance_win(nb)
            else:
                pairs[a] = s._value_win(nb)
        if not pairs:
            raise ValueError("no legal actions at root")
        vstar = next(iter(pairs.values()))
        for x in pairs.values():
            if _lex_better(x, vstar, to_move == 0):
                vstar = x
        # the lexicographic tie set: win-tied (_WIN_TIE) AND margin-tied (_TIE)
        optimal = [a for a, v in pairs.items()
                   if abs(v[0] - vstar[0]) <= _WIN_TIE and abs(v[1] - vstar[1]) <= _TIE]
        return SolveResult(mode=mode, value=float(vstar[1]), to_move=to_move,
                           optimal_actions=optimal,
                           child_values={a: float(v[1]) for a, v in pairs.items()},
                           nodes=s.nodes, completed=True,
                           win_value=float(vstar[0]),
                           child_win_values={a: float(v[0]) for a, v in pairs.items()},
                           objective="win")

    child_values: dict[int, float] = {}
    for a in legal:
        a = int(a)
        nb, _ = game.get_next_state(board, a)
        if _terminal(nb):
            child_values[a] = float(flat_base_score(nb.state, 0))
        elif mode == "marginalized" and _drew_a_tile(board, nb, was_meeples):
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
