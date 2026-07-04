"""FairHeuristicMCTSAgent — production fair-play (non-clairvoyant) HeuristicMCTS.

WHY THIS EXISTS: the base MCTS (mcts.py) descends the engine's pre-shuffled TRUE
`state.deck` order, so HeuristicMCTS is structurally CLAIRVOYANT — every simulation
sees the actual upcoming tiles. A deployed/fair player must not. NeuralMCTS grew
`fair_chance`/`fair_isolate` for this; HeuristicMCTS had no fair machinery at all.
This module is the production fair mode for the classical (heuristic-leaf) champion.

MECHANISM — root-determinization PIMC, the pattern validated by
scripts/canonical_az/fairness_decision_probe.py (commit 7237803):
  per move, K determinizations; each one:
    1. deepcopy the board (the caller's board is NEVER mutated);
    2. rng.shuffle ONLY the unseen `state.deck` (multiset preserved; `next_tile`
       — the already-revealed in-hand tile — untouched: exactly the
       NeuralMCTS._reshuffled_root semantics);
    3. run a FRESH HeuristicMCTS on that copy (fresh tree per determinization =
       no cross-determinization leak — the fair_isolate discipline);
    4. harvest its deduped root-child stats into pooled (N, W) accumulators.
  Then pick by POOLED-Q (rule below).

AGGREGATION = POOLED-Q, **not** pooled visit counts.  Decision made from the
probe's smoke results: pooled-N picked an 11-point blunder on a smoke root while
pooled-Q was move-identical to the clairvoyant champion on every smoke root.

THE POOLED-Q RULE (as implemented in `pooled_q_argmax`):
  * Per root action a (deduped by child object identity within each tree — the
    base MCTS.best_action convention, so symmetric-rotation aliases pool once):
      N[a] = sum of root-child visits over the determinizations that visited a,
      W[a] = sum of root-POV-signed child W over those same determinizations,
      Q[a] = W[a] / N[a].
    An action MISSING from some determinizations is pooled only over the ones
    that visited it — Q is a mean, so it is not diluted by absence (and a tile
    that a determinization never explored contributes neither signal nor noise).
  * MIN-VISITS FLOOR: only actions with N[a] >= min_pooled_visits are eligible
    for the argmax (default 2 — excludes 1-visit noise picks, whose Q is a
    single leaf sample). If NO action reaches the floor (pathological: tiny
    sims), all visited actions become eligible so a move is always returned.
  * Pick argmax over eligible actions by (Q[a], N[a], -a): pooled Q primary,
    pooled N tiebreak, lowest action index as the final deterministic tiebreak
    (matches best_action's Q-then-N rule generalized to the ensemble).

ENDGAME (flag-gated, `exact_endgame=True` default): the FAIR exact handoff.
On the first TILES-phase decision with k_remaining <= 2 the agent latches (the
eval_hybrid_handoff._ExactAgent trigger — turn-atomic, one-way) and plays the
MARGINALIZED expectiminimax solver (scripts/level2/endgame_solver.py,
mode="marginalized") for the rest of the game. Marginalized = honest hidden-bag
value — fair-legit at any K, tractable only at K <= 2 (no alpha-beta over chance
nodes). There is NO clairvoyant K=3-4 solve here: that would be the cheating
path. A BudgetExceeded solve falls back to the fair PIMC move for THAT decision
only (counted in n_timeouts; the agent stays latched and retries next ply).

DETERMINISM: fully deterministic given (seed, sequence of boards). Per-move
seeds derive from (seed, move_index) — see `det_seed_base` — so replaying the
same game with the same seed reproduces every determinization and search.
No global-RNG use (all `random.Random` instances).

INTERFACE: `choose_action(board) -> int`, with `move(board)` as an alias — the
eval_hybrid_handoff.py agent convention (`.move(board)` + the counter attributes
neural_moves/heur_moves/latch_k/exact_moves/n_timeouts/solver_secs/solver_nodes/
max_solve_secs), so this agent drops into that harness's GameResult
instrumentation unchanged. (ladder_rung_eval.py uses `.move(game, board, mask)`;
a 3-line adapter covers it there.)

LEAF: `leaf_cfg` is passed straight to HeuristicMCTS (None -> virtual_score_v2
DEFAULT_CONFIG, which the CALLER's env preamble shapes — this library module
sets no environment variables). `c_puct` is HeuristicMCTS's UCT `c`
(champion: 3.0).
"""
from __future__ import annotations

import copy
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from wingedsheep.carcassonne.objects.game_phase import GamePhase

from .game_wrapper import Board, Game
from .mcts import HeuristicMCTS

# Marginalized-solver handoff band. NOT a tuning knob: K<=2 is both the
# tractability frontier of the no-alpha-beta expectiminimax AND the L2-3 band
# the marginalized ground truth is validated on. Above it, fair PIMC search.
EXACT_MAX_K = 2

DEFAULT_MIN_POOLED_VISITS = 2
DEFAULT_EXACT_BUDGET = 2_000_000   # matches eval_hybrid_handoff EXACT_BUDGET


def k_remaining(state) -> int:
    """Tiles left = undrawn deck + the one in hand. IDENTICAL to
    gen_endgame_positions.k_remaining / eval_hybrid_handoff.k_remaining, so
    "K<=2" here is the same band as the L2-3 verdicts."""
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def _import_solver():
    """Lazy import of scripts/level2/endgame_solver (not a src package)."""
    try:
        import endgame_solver as S  # already on sys.path (harness/scripts)
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "level2"))
        import endgame_solver as S
    return S


def pool_root_stats(root, agg_n: dict, agg_w: dict) -> None:
    """Harvest one search tree's deduped root-child stats into the PIMC pools.

    Dedup by child object identity, lowest action kept — exactly the base
    MCTS.best_action convention (rotations of a symmetric tile share one child
    node; without dedup that move would be pooled once per alias). W is signed
    into the ROOT player's perspective before pooling. Verbatim the probe's
    `_pool_root_stats` (fairness_decision_probe.py)."""
    seen: set[int] = set()
    for a in sorted(root.children):
        ch = root.children[a]
        if ch.N <= 0 or id(ch) in seen:
            continue
        seen.add(id(ch))
        sw = ch.W if ch.player_to_move == root.player_to_move else -ch.W
        agg_n[a] += ch.N
        agg_w[a] += sw


def pooled_q_argmax(agg_n: dict, agg_w: dict,
                    min_visits: int = DEFAULT_MIN_POOLED_VISITS) -> int:
    """THE production pooled-Q pick (rule documented in the module docstring).

    argmax over eligible actions (pooled N >= min_visits; fallback to all
    visited actions if none qualify) of (Q=W/N, N, -action)."""
    if not agg_n:
        raise ValueError("pooled_q_argmax: no visited root actions to pool")
    eligible = [a for a, n in agg_n.items() if n >= min_visits]
    if not eligible:            # pathological (tiny sims): never return nothing
        eligible = list(agg_n)
    return int(max(eligible, key=lambda a: (agg_w[a] / agg_n[a], agg_n[a], -a)))


class FairHeuristicMCTSAgent:
    """Production fair-play PIMC wrapper around HeuristicMCTS (see module doc).

    Parameters
    ----------
    game : Game            shared engine wrapper (like _HeurAgent's game_plain)
    sims : int             HeuristicMCTS simulations PER determinization
    k_dets : int           number of root determinizations per move (PIMC K)
    c_puct : float         HeuristicMCTS UCT ``c`` (champion: 3.0)
    seed : int             base seed; the agent is deterministic given it
    leaf_cfg               virtual_score_v2 LeafConfig (None -> DEFAULT_CONFIG)
    heur_leaf : str        "v2_7" (production) or "v1"
    min_pooled_visits :    the pooled-Q eligibility floor (see rule)
    exact_endgame : bool   True (default) -> marginalized solver at K<=2
    exact_budget : int     solver node budget per solve (BudgetExceeded -> PIMC)
    """

    def __init__(self, game: Game, sims: int = 400, k_dets: int = 4,
                 c_puct: float = 3.0, seed: int | None = None, leaf_cfg=None,
                 heur_leaf: str = "v2_7",
                 min_pooled_visits: int = DEFAULT_MIN_POOLED_VISITS,
                 exact_endgame: bool = True,
                 exact_budget: int = DEFAULT_EXACT_BUDGET):
        if k_dets < 1:
            raise ValueError(f"k_dets must be >= 1, got {k_dets}")
        self._game = game
        self._sims = int(sims)
        self._k_dets = int(k_dets)
        self._c = float(c_puct)
        self._seed = 0 if seed is None else int(seed)
        self._leaf_cfg = leaf_cfg
        self._heur_leaf = heur_leaf
        self._min_pooled_visits = int(min_pooled_visits)
        self._exact_endgame = bool(exact_endgame)
        self._exact_budget = int(exact_budget)
        self._move_idx = 0
        self._latched = False
        # eval_hybrid_handoff harness-compatible instrumentation
        self.neural_moves = 0        # always 0 — harness symmetry only
        self.heur_moves = 0          # PIMC (fair search) decisions
        self.latch_k = None
        self.exact_moves = 0
        self.n_timeouts = 0
        self.solver_secs = 0.0
        self.solver_nodes = 0
        self.max_solve_secs = 0.0

    # --- deterministic per-move seed derivation (public so tests can mirror it)
    def det_seed_base(self, move_idx: int) -> int:
        """Stable per-(agent seed, move index) base for this move's RNGs."""
        return (self._seed * 1_000_003 + move_idx * 8191) & 0x7FFFFFFF

    def det_search_seed(self, move_idx: int, det_idx: int) -> int:
        """Seed of the fresh HeuristicMCTS for determinization `det_idx`."""
        return self.det_seed_base(move_idx) + 100 + det_idx

    # --- determinization -------------------------------------------------
    @staticmethod
    def reshuffled_determinization(board: Board, rng: random.Random) -> Board:
        """A deepcopy of `board` whose UNSEEN `state.deck` is reshuffled
        (multiset preserved). `next_tile` and every other field are untouched;
        the caller's board is never mutated. The NeuralMCTS._reshuffled_root /
        probe semantics."""
        b = copy.deepcopy(board)
        rng.shuffle(b.state.deck)
        b._str_repr_cache = None   # deck order isn't in the key; be safe
        return b

    # --- the fair PIMC move ----------------------------------------------
    def _pimc_move(self, board: Board, move_idx: int) -> int:
        self.heur_moves += 1
        legal = np.flatnonzero(self._game.get_valid_moves(board))
        if legal.size == 0:
            raise ValueError("fair agent asked to move with no legal actions")
        if legal.size == 1:
            return int(legal[0])   # forced move: skip the K searches
        base = self.det_seed_base(move_idx)
        det_rng = random.Random(base + 1)          # deck reshuffles
        root_key = self._game.string_representation(board)
        agg_n: dict[int, float] = defaultdict(float)
        agg_w: dict[int, float] = defaultdict(float)
        for i in range(self._k_dets):
            b = self.reshuffled_determinization(board, det_rng)
            m = HeuristicMCTS(game=self._game, simulations=self._sims,
                              c=self._c, seed=base + 100 + i,
                              heur_leaf=self._heur_leaf, leaf_cfg=self._leaf_cfg)
            m.search(b)
            # deck order isn't in the key, so the reshuffled root shares the
            # original board's key (fallback kept verbatim from the probe).
            root = m._nodes.get(root_key) or m._nodes[self._game.string_representation(b)]
            pool_root_stats(root, agg_n, agg_w)
            m.clear()
        if not agg_n:                              # pathological: nothing visited
            return int(legal[0])
        return pooled_q_argmax(agg_n, agg_w, self._min_pooled_visits)

    # --- the fair exact endgame -------------------------------------------
    def _exact_move(self, board: Board) -> int | None:
        """Marginalized solve; min(optimal_actions) (deterministic, value-
        irrelevant within the optimal set — the _ExactAgent convention).
        Returns None on BudgetExceeded (caller falls back to PIMC, stays
        latched)."""
        S = _import_solver()
        t0 = time.perf_counter()
        try:
            res = S.solve(self._game, board, mode="marginalized",
                          budget=self._exact_budget, alphabeta=False)
        except S.BudgetExceeded:
            self.solver_secs += time.perf_counter() - t0
            self.n_timeouts += 1
            return None
        dt = time.perf_counter() - t0
        self.solver_secs += dt
        self.max_solve_secs = max(self.max_solve_secs, dt)
        self.solver_nodes += res.nodes
        self.exact_moves += 1
        return int(min(res.optimal_actions))

    # --- public API ---------------------------------------------------------
    def choose_action(self, board: Board) -> int:
        """Pick the fair move for `board`. Never mutates the caller's board."""
        move_idx = self._move_idx
        self._move_idx += 1
        if self._exact_endgame and not self._latched:
            st = board.state
            k = k_remaining(st)
            # Latch only on a TILES decision (turn-atomic: the boundary tile AND
            # its meeple go to the solver, never split). One-way: k_remaining is
            # monotone non-increasing.
            if st.phase == GamePhase.TILES and k <= EXACT_MAX_K:
                self._latched = True
                self.latch_k = k
        if self._latched:
            a = self._exact_move(board)
            if a is not None:
                return a
            # BudgetExceeded: fair PIMC fallback for THIS decision only.
        return self._pimc_move(board, move_idx)

    # eval_hybrid_handoff harness convention (`agent.move(board) -> int`).
    move = choose_action
