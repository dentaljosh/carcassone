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

import atexit
import copy
import dataclasses
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from wingedsheep.carcassonne.objects.game_phase import GamePhase

from . import intra_reuse as intra_carry
from .game_wrapper import Board, Game
from .mcts import HeuristicMCTS, NeuralMCTS
from .heuristic_prior_mcts import (
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
    make_heuristic_prior_evaluator_with_net_value,
)
# Track-F Gate A oracle-prior extraction — the SINGLE-SOURCE helpers shared with the
# clairvoyant screen (eval_puct_priors re-exports the same functions). Imported here so
# the fair per-world pre-search folds/floors IDENTICALLY (no copy-paste divergence).
from .oracle_prior import (
    LeafCounter,
    oracle_prior_from_visits,
    root_action_groups,
)

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


def root_stats_list(root) -> list:
    """One search tree's deduped root-child stats as ``[(action, N, W_rootpov)]``.

    Dedup by child object identity, lowest action kept — exactly the base
    MCTS.best_action convention (rotations of a symmetric tile share one child
    node; without dedup that move would be pooled once per alias). W is signed
    into the ROOT player's perspective. Verbatim the harvest half of the probe's
    `_pool_root_stats` (fairness_decision_probe.py), split out so the k-PARALLEL
    split can ship a world's contribution across a process boundary and have the
    PARENT do the identical accumulation (see `_merge_root_stats`). The emitted
    tuple carries the RAW `a` / `ch.N` / signed `ch.W` objects — no casts — so a
    pickled round trip reproduces the same additions bit-for-bit."""
    out: list = []
    seen: set[int] = set()
    for a in sorted(root.children):
        ch = root.children[a]
        if ch.N <= 0 or id(ch) in seen:
            continue
        seen.add(id(ch))
        sw = ch.W if ch.player_to_move == root.player_to_move else -ch.W
        out.append((a, ch.N, sw))
    return out


def _merge_root_stats(stats, agg_n: dict, agg_w: dict) -> None:
    """Accumulate one world's `root_stats_list` into the PIMC pools.

    THE single accumulation point for both the sequential and the k-parallel
    path: float addition is order-sensitive, so identity across the two modes
    rests on the parent merging worlds in the SAME order (0..k_dets-1) with the
    SAME `+=` sequence."""
    for a, n, w in stats:
        agg_n[a] += n
        agg_w[a] += w


def pool_root_stats(root, agg_n: dict, agg_w: dict) -> None:
    """Harvest one search tree's deduped root-child stats into the PIMC pools.

    (Public API unchanged — now a thin `root_stats_list` + `_merge_root_stats`.)"""
    _merge_root_stats(root_stats_list(root), agg_n, agg_w)


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


# --------------------------------------------------------------------------- #
# ONE determinization world's search — the shared body of the SEQUENTIAL loop   #
# and of the k-PARALLEL worker (G6 stage 1). Single source of truth: if this    #
# function is the only place a world is searched, the two modes cannot diverge. #
# --------------------------------------------------------------------------- #
def search_one_world(game, evaluator, det_board: Board, root_key: str, *,
                     sims: int, c_puct: float, seed: int,
                     batch_size: int = 1, batch_evaluator=None,
                     virtual_loss: float = 1.0, meeple_dedup=None,
                     oracle_prior_mult: int | None = None,
                     oracle_prior_eps_coef: float = 1e-3):
    """Run ONE already-determinized world's PUCT search.

    Returns ``(tree, stats, telem)`` where ``stats`` is `root_stats_list(root)`
    and ``telem`` is the oracle-probe cost dict (all zeros / None when the probe
    is off). The caller owns the tree (``clear()`` it, or retain it for the
    C3-INTRA carry)."""
    telem = {"presearch_secs": 0.0, "mainsearch_secs": 0.0,
             "presearch_leaf_calls": 0, "mainsearch_leaf_calls": 0,
             "override": None}
    if oracle_prior_mult is not None:
        # Track-F Gate A per-world pre-search: on THIS world's reshuffled deck, run a
        # fresh champion search at mult x sims, read its deduped root visit
        # distribution, convert it to a ROOT-prior override (identical alias-fold +
        # eps-floor as the clairvoyant screen), then run this world's normal
        # sims-budget search with the ROOT priors REPLACED. The pre-search tree is NOT
        # reused into the main search (a fresh NeuralMCTS) so the probe isolates the
        # prior channel from deeper search. Each world gets ITS OWN override (its own
        # reshuffled deck -> its own pre-search distribution).
        pre = NeuralMCTS(game=game, evaluator=LeafCounter(evaluator),
                         simulations=sims * oracle_prior_mult,
                         c_puct=c_puct, seed=seed, meeple_dedup=meeple_dedup)
        _t = time.perf_counter()
        pre.search(det_board)
        counts, actions = pre.root_visit_distribution(det_board)
        telem["presearch_secs"] = time.perf_counter() - _t
        telem["presearch_leaf_calls"] = pre.evaluator.n
        groups = root_action_groups(game, det_board)
        counts_by_action = {int(a): float(c) for a, c in zip(actions, counts)}
        override = oracle_prior_from_visits(
            groups, counts_by_action, oracle_prior_eps_coef)
        telem["override"] = override
        m = NeuralMCTS(game=game, evaluator=LeafCounter(evaluator), simulations=sims,
                       c_puct=c_puct, seed=seed, batch_size=batch_size,
                       batch_evaluator=batch_evaluator, virtual_loss=virtual_loss,
                       meeple_dedup=meeple_dedup)
        m.set_root_prior_override(override)   # one-shot, survives the search's expand
        _t = time.perf_counter()
        m.search(det_board)
        telem["mainsearch_secs"] = time.perf_counter() - _t
        telem["mainsearch_leaf_calls"] = m.evaluator.n
    else:
        m = NeuralMCTS(game=game, evaluator=evaluator, simulations=sims,
                       c_puct=c_puct, seed=seed, batch_size=batch_size,
                       batch_evaluator=batch_evaluator, virtual_loss=virtual_loss,
                       meeple_dedup=meeple_dedup)
        m.search(det_board)
    # deck order isn't in the key, so the reshuffled root shares the original
    # board's key (the fallback kept verbatim from the probe).
    root = m._nodes.get(root_key) or m._nodes[game.string_representation(det_board)]
    return m, root_stats_list(root), telem


# --------------------------------------------------------------------------- #
# k-PARALLEL INFERENCE (G6 stage 1, 2026-07-28) — the k determinization worlds  #
# are fully independent until the pooled-Q argmax, so splitting them across     #
# processes is BEHAVIOR-IDENTICAL, not a search change. Purely a single-GAME    #
# LATENCY lever (eval farms already saturate throughput with game-level W).     #
#                                                                              #
# TRANSPORT (measured 2026-07-28 on a 15-tile midgame board): the parent ships  #
# the CURRENT board once per WORKER (pickle ~19 KiB / ~0.5 ms) plus one         #
# int-permutation per world; the worker rebuilds each determinization locally.  #
# Shipping the k already-determinized boards instead would cost k pickles for   #
# no gain, and the parent-side deepcopy would stay on the critical path.        #
#                                                                              #
# WHY A PERMUTATION AND NOT A DECK: `reshuffled_determinization` canonicalizes  #
# the unseen deck (sort by description) and then `random.Random.shuffle`s it.   #
# CPython's shuffle draws `_randbelow(i+1)` for i in reversed(range(1,n)) —     #
# it depends on len(x) ONLY, never on the elements — so shuffling               #
# `list(range(n))` in description-sorted order consumes the IDENTICAL rng draws #
# and yields the identical permutation. The parent therefore reproduces every   #
# world's deck order without a single deepcopy, and the shared `det_rng` state  #
# advances exactly as the sequential loop advances it. This equivalence is not  #
# assumed — tests/test_kparallel.py::test_permutation_recipe_matches_reshuffle  #
# proves it against `reshuffled_determinization` on this interpreter.           #
# --------------------------------------------------------------------------- #

# Leaf-shaping env knobs. The spawn child inherits os.environ, so these MUST
# already agree; the worker re-checks and raises rather than silently searching
# a different leaf (a mismatch would be invisible in the pooled stats).
_LEAF_ENV_KEYS = (
    "CARCASSONNE_V25_CAP", "CARCASSONNE_V25_OPP_CAP",
    "CARCASSONNE_V25_DROP_THREE_OPEN", "CARCASSONNE_V29_MEEPLE_CURVE",
    "CARCASSONNE_V25_MEEPLE_K", "CARCASSONNE_USE_FLAT_LEAF",
    "CARCASSONNE_USE_CY_LEAF", "CARCASSONNE_USE_CY_REPR",
    "CARCASSONNE_V25_VALUE_BLEND", "CARCASSONNE_MEEPLE_DEDUP",
)

_KP_WORKER: dict | None = None

# Every live k-parallel pool in THIS process. A killed mp main does not reap its
# spawn children, so the pools are tracked (not the agents — an atexit closure over
# a bound method would pin the agent forever) and torn down at interpreter exit.
_KP_LIVE_POOLS: set = set()


@atexit.register
def _kparallel_close_all() -> None:      # pragma: no cover - interpreter teardown
    for pool in list(_KP_LIVE_POOLS):
        _KP_LIVE_POOLS.discard(pool)
        try:
            pool.terminate()
            pool.join()
        except Exception:
            pass


def _kparallel_worker_init(game_spec: dict, cfg, world_kw: dict,
                           env_fp: dict) -> None:
    """spawn-child bootstrap: build this worker's OWN Game + heuristic-prior
    evaluator once, then reuse them for every move of the game.

    A per-worker Game is correctness-neutral: `Game`'s only mutable state is the
    legal-move MEMO (`_legal_cache`, a pure function of the board key) and its
    hit/miss counters. `NeuralMCTS.clear()` flushes it per world exactly as it
    does in the sequential path."""
    global _KP_WORKER
    from .game_wrapper import Game

    bad = {k: (env_fp.get(k), os.environ.get(k))
           for k in _LEAF_ENV_KEYS if env_fp.get(k) != os.environ.get(k)}
    if bad:
        raise RuntimeError(
            f"k-parallel worker leaf-env mismatch (parent, child): {bad} — the "
            "worker would search a DIFFERENT leaf than the parent. Export the "
            "production preamble before constructing the agent.")
    game = Game(**game_spec)
    _KP_WORKER = {
        "game": game,
        "evaluator": make_heuristic_prior_evaluator(game, cfg),
        "kw": world_kw,
    }


def _kparallel_worker_chunk(payload):
    """Search this worker's slice of the move's determinization worlds.

    payload = (board, root_key, [(world_idx, deck_perm, seed), ...]);
    returns (chunk_wall_secs, [(world_idx, stats, telem), ...]).

    `chunk_wall_secs` is the IN-WORKER wall time (determinization rebuild + the
    searches). The parent's `dispatch - max(chunk_wall_secs)` is therefore the
    measured TRANSPORT + scheduling overhead of the split — the number the G6
    latency claim has to survive."""
    t_chunk = time.perf_counter()
    board, root_key, jobs = payload
    st = _KP_WORKER
    if st is None:                      # pragma: no cover - defensive
        raise RuntimeError("k-parallel worker used before its initializer ran")
    game, evaluator, kw = st["game"], st["evaluator"], st["kw"]
    out = []
    for world_idx, perm, seed in jobs:
        b = copy.deepcopy(board)
        src = list(b.state.deck)
        b.state.deck[:] = [src[i] for i in perm]   # == reshuffled_determinization
        b._str_repr_cache = None                   # deck order isn't in the key; be safe
        m, stats, telem = search_one_world(
            game, evaluator, b, root_key, seed=seed, **kw)
        m.clear()
        out.append((world_idx, stats, telem))
    return time.perf_counter() - t_chunk, out


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
        probe semantics.

        HARDENING (fair-handoff audit 2026-07-06, probe C): the unseen deck is
        CANONICALIZED (sorted by tile description) BEFORE the reshuffle, so the
        sampled determinization is a pure function of the unseen *multiset* + the
        rng — invariant to the engine's (unobservable) TRUE deck order. Without
        the sort, `random.Random.shuffle` yields a different permutation from a
        different INPUT order, so a fair decision could depend on the hidden order
        (the audit saw 19% of permutation trials flip a PIMC move) even though the
        order *signal* is destroyed in expectation. This closes the last
        order-dependency for reproducibility + honest imperfect information; it
        changes nothing about legality or expected play (tied-description tiles
        are interchangeable, and deck order is not in the transposition key)."""
        b = copy.deepcopy(board)
        b.state.deck.sort(key=lambda t: t.description)   # canonical order (audit hardening)
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


class FairHeuristicPriorAgent:
    """Production fair-play PIMC wrapper around the PUCT-with-heuristic-priors
    CHAMPION (``heuristic_prior_mcts.HeuristicPriorAgent``'s ``NeuralMCTS`` core).

    WHY THIS EXISTS: as of the 2026-07-06 champion flip, production strength is
    ``HeuristicPriorAgent`` — PUCT selection with softmax(Δleaf/τ_p) heuristic
    priors + a v2.9 leaf value (``src/carcassonne_ai/heuristic_prior_mcts.py``;
    c_puct=1.5, τ_p=5, leaf_quantize=float, final_select=visits, ~2750 sims). But
    as shipped it plays CLAIRVOYANT — its ``NeuralMCTS`` descends the engine's
    pre-shuffled TRUE ``state.deck``, so every simulation sees the actual upcoming
    tiles. A deployed/fair player (any human/superhuman strength claim) must not.
    This is the fair (imperfect-information / PIMC) mode for that champion — the
    PUCT sibling of ``FairHeuristicMCTSAgent`` above, reusing its VALIDATED
    determinization + pooled-Q + marginalized-endgame machinery verbatim.

    MECHANISM — identical to ``FairHeuristicMCTSAgent`` (root-determinization
    PIMC), only the per-determinization search engine differs (a fresh
    heuristic-prior ``NeuralMCTS`` instead of ``HeuristicMCTS``):
      per move, ``k_dets`` determinizations; each one:
        1. deepcopy the board (the caller's board is NEVER mutated);
        2. rng.shuffle ONLY the unseen ``state.deck`` (multiset preserved;
           ``next_tile`` untouched — the ``NeuralMCTS._reshuffled_root`` semantics,
           reused via ``FairHeuristicMCTSAgent.reshuffled_determinization``);
        3. run a FRESH ``NeuralMCTS`` wired with the SAME heuristic-prior evaluator
           on that copy (fresh tree per determinization = fair_isolate discipline;
           the search itself is CLAIRVOYANT on the *reshuffled* deck, which is the
           point — one plausible world per determinization);
        4. harvest its deduped root-child stats into pooled (N, W) accumulators
           (``pool_root_stats`` — the ``_NeuralNode`` root has the same
           ``children``/``N``/``W``/``player_to_move`` fields + id-dedup as the
           ``HeuristicMCTS`` node, so the harvester is engine-agnostic).
      Then pick by POOLED-Q (``pooled_q_argmax``).

    NOTE — ``cfg.final_select`` is INERT in fair mode: the champion's
    ``final_select`` ("visits") only governs a *single-search* root pick; the fair
    ensemble aggregates across ``k_dets`` worlds by pooled-Q (the probe-validated
    PIMC rule). The knobs that DO shape the search — ``c_puct``, ``τ_p``,
    ``leaf_quantize``, ``value_norm``, ``leaf_cfg`` — ride on ``cfg`` unchanged.

    ENDGAME (``exact_endgame=True`` default): the SAME fair marginalized exact
    handoff as ``FairHeuristicMCTSAgent`` — latch on the first TILES decision with
    ``k_remaining <= exact_max_k`` and play the marginalized (honest hidden-bag)
    expectiminimax solver for the rest of the game. ``exact_max_k`` is a knob here
    (``FairHeuristicMCTSAgent`` hard-codes 2) so the A2 grid can sweep the fair
    endgame depth K∈{2,4,8}; K>2 marginalized solves are expensive (no alpha-beta
    over chance nodes) → BudgetExceeded falls back to the fair PIMC move for that
    decision (counted in ``n_timeouts``; the agent stays latched). There is NO
    clairvoyant solve here (that would be the cheating path).

    DETERMINISM / INTERFACE / instrumentation: identical contract to
    ``FairHeuristicMCTSAgent`` (``choose_action``/``move``; per-move seeds from
    ``det_seed_base``; the neural_moves/heur_moves/latch_k/exact_moves/n_timeouts/
    solver_secs/solver_nodes/max_solve_secs counters). ``heur_moves`` counts fair
    PIMC (prefix) decisions.

    Parameters
    ----------
    game : Game                 shared engine wrapper (referee/eval owns its own).
    cfg : HeuristicPriorConfig  the champion's resolved knobs (c_puct/τ_p/leaf).
    sims : int                  PUCT sims PER determinization.
    k_dets : int                number of root determinizations per move (PIMC K).
    seed : int                  base seed; the agent is deterministic given it.
    min_pooled_visits : int     pooled-Q eligibility floor (see pooled_q_argmax).
    exact_endgame : bool        True (default) -> marginalized solver at k<=exact_max_k.
    exact_max_k : int           fair-endgame handoff depth K (default 2).
    exact_budget : int          solver node budget per solve (BudgetExceeded -> PIMC).
    net                         OPTIONAL deck-aware value net (C-cheap). When given
                                (and evaluator is None), the per-determinization
                                search uses IDENTICAL heuristic priors but the
                                learned net value as the leaf value
                                (make_heuristic_prior_evaluator_with_net_value). The
                                net must be an 81ch/42-scalar sighted net.
    evaluator                   OPTIONAL pre-built evaluator override (takes
                                precedence over net). Callable[[Board],(priors,val)].
    sighted_game                OPTIONAL Game(sighted=True) encoder for `net`
                                (built internally if None). Ignored unless net.
    batch_size : int            leaves collected per forward inside EACH
                                per-determinization search (default 1 = the
                                byte-identical serial champion path). >1 engages
                                NeuralMCTS's virtual-loss batch machinery.
    batch_evaluator             OPTIONAL Callable[[list[Board]], (priors[N,A],
                                values[N])] — e.g.
                                heuristic_prior_mcts.make_fair_net_prior_batch_evaluator.
                                Only consulted when batch_size>1 (NeuralMCTS._eval_boards);
                                passing it at batch_size=1 raises rather than silently
                                no-op'ing. Without it, batch_size>1 still batches the TREE
                                but falls back to per-board `evaluator` calls (no
                                transport win).
    virtual_loss : float        NeuralMCTS virtual loss (default 1.0; inert at
                                batch_size=1 — it is only read on the batched path).

    intra_reuse                 C3-INTRA WITHIN-TURN TREE CARRY (flag-gated, default
                                OFF via ``CARCASSONNE_INTRA_TURN_REUSE``; None =
                                inherit). When ON, the forest built for a turn's TILE
                                decision — the k_dets trees AND their determinized decks
                                — is carried into that same turn's MEEPLE decision:
                                each tree is re-rooted at the child under the tile action
                                actually played, and the meeple search runs its full
                                ``sims`` on top of the carried visits instead of
                                redrawing k_dets worlds and starting from nothing.
                                FAIR-LEGAL because no hidden information arrives between
                                the two decisions (the engine draws the next tile only at
                                the END of the meeple phase — verified in
                                ``StateUpdater._apply_action_to``), so the tile
                                decision's determinizations are equally valid samples of
                                the information state at the meeple decision. This is
                                precisely what is NOT true across moves — see
                                ``carcassonne_ai.intra_reuse`` for the full argument and
                                the CL-044 boundary that must not be weakened.
                                ⚠️ ON does MORE total work per turn at the same nominal
                                ``sims``; a positive screen needs an equal-WALL-CLOCK
                                confirm. Mutually exclusive with ``oracle_prior_mult``.

    parallel_workers            k-PARALLEL INFERENCE (G6 stage 1, 2026-07-28). None
                                (default) = the SEQUENTIAL k-loop, byte-for-byte the
                                deployed champion — the Android/Chaquopy bridge, which
                                has no ``multiprocessing`` at all, only ever sees this
                                path. An int W runs the move's ``k_dets`` worlds on
                                ``min(W, k_dets)`` SPAWN processes (ceil(k/W) worlds
                                each) and merges them through the SAME pooled-Q code.
                                BEHAVIOR-IDENTICAL, not a search change: the worlds are
                                independent until the pooled argmax, each is handed the
                                same determinized deck and the same
                                ``det_seed_base+100+i`` seed, and the parent accumulates
                                them in world order so even the float additions match.
                                It buys single-GAME LATENCY only (an eval farm already
                                saturates throughput with game-level W, which is why
                                this was never built before) — the prize is CL-068's
                                clock closure, measured under an unstated single-stream
                                assumption. Requires the champion evaluator (net=None,
                                evaluator=None), ``batch_size=1``, and ``intra_reuse``
                                OFF; each is rejected loudly. The pool is persistent and
                                torn down by ``close()``/atexit.

    ⚠️ BIT-EXACT DEFAULT: with net=None AND evaluator=None AND batch_size=1 (the
    defaults) the agent builds the SAME make_heuristic_prior_evaluator as before and
    constructs NeuralMCTS with its own defaults — byte-for-byte the heuristic-value
    fair champion. The net/evaluator/batch hooks are purely additive.

    ⚠️ LEAF BATCHING CHANGES THE SEARCH — the CHAMPION MUST NOT USE IT. Virtual loss
    is an approximation: it perturbs PUCT selection so K leaves can be collected before
    any of them is evaluated, so a batch_size>1 tree does NOT reproduce the serial tree.
    That is ACCEPTABLE for the distilled net candidate (the gen path already accepts it
    at --batch-size 8) but NOT for the heuristic-priors fair champion, which is our
    opponent/ruler AND stage-1's teacher and must stay byte-identical. Hence the default
    is 1: batching is strictly opt-in, per agent instance.
    WHY IT EXISTS: the net candidate's evaluator is a GPU/IPC round-trip (~7ms); at
    batch_size=1 the ~2752 expansions/move serialize into 57s/move (measured 2026-07-16,
    12.67x the heuristic champion) with the GPU ~15% utilized. The champion's leaf is
    in-process Cython, so it has no round-trip to amortize and gains nothing here.
    """

    def __init__(self, game: Game, cfg: HeuristicPriorConfig | None = None,
                 sims: int = 688, k_dets: int = 4, seed: int | None = None,   # ⚠️ NO LONGER THE DEPLOY BUDGET (2026-07-29): the champion of record is
                                                                             # k8×1376=11008 (governance/PRODUCTION.yaml champion.fair_deploy) and is
                                                                             # reached via champion_factory, which passes these explicitly. These
                                                                             # constructor defaults stay at the historical k4×688=2752 so every existing
                                                                             # caller/test keeps its budget; do NOT read them as "the champion".
                 min_pooled_visits: int = DEFAULT_MIN_POOLED_VISITS,
                 exact_endgame: bool = True, exact_max_k: int = EXACT_MAX_K,
                 exact_budget: int = DEFAULT_EXACT_BUDGET,
                 net=None, evaluator=None, sighted_game: Game | None = None,
                 batch_size: int = 1, batch_evaluator=None,
                 virtual_loss: float = 1.0,
                 oracle_prior_mult: int | None = None,
                 oracle_prior_eps_coef: float = 1e-3,
                 meeple_dedup: bool | None = None,
                 intra_reuse: bool | None = None,
                 parallel_workers: int | None = None):
        if k_dets < 1:
            raise ValueError(f"k_dets must be >= 1, got {k_dets}")
        if exact_max_k < 0:
            raise ValueError(f"exact_max_k must be >= 0, got {exact_max_k}")
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")
        if batch_evaluator is not None and batch_size <= 1:
            raise ValueError(
                "batch_evaluator given with batch_size=1 — it would never be called "
                "(NeuralMCTS only uses the batched path when batch_size>1). Pass "
                "batch_size>1 to batch, or drop batch_evaluator."
            )
        # --- Track-F Gate A oracle-prior probe (F2, 2026-07-19; default OFF = None ->
        # byte-identical to the pre-probe fair champion). When set to N (>=2), EACH
        # determinization world runs a PRE-SEARCH at N x sims on a FRESH tree FIRST, its
        # deduped root visit distribution is converted to a ROOT-prior override
        # (oracle_prior.oracle_prior_from_visits — the SAME alias-fold/eps-floor as the
        # clairvoyant screen), and that world's normal sims-budget search runs with the
        # ROOT priors REPLACED via NeuralMCTS.set_root_prior_override. Pooling across
        # worlds (pooled-Q) is UNCHANGED. See eval_fair_puct.py --oracle-prior-mult.
        if oracle_prior_mult is not None:
            if int(oracle_prior_mult) < 2:
                raise ValueError(
                    f"oracle_prior_mult must be >= 2 (a pre-search LARGER than the "
                    f"production budget), got {oracle_prior_mult}")
            if batch_size > 1:
                raise ValueError(
                    "oracle_prior_mult requires batch_size=1: leaf batching perturbs PUCT "
                    "selection (virtual loss), which would confound the ROOT-prior probe. "
                    "Run the oracle candidate serial.")
            if intra_carry.resolve(intra_reuse):
                raise ValueError(
                    "oracle_prior_mult and intra_reuse are mutually exclusive: the oracle "
                    "probe deliberately runs its pre-search on a FRESH tree to isolate the "
                    "prior channel from deeper search, which is exactly what a carried "
                    "subtree would confound. Run one or the other.")
        # --- k-PARALLEL INFERENCE (G6 stage 1). None (default) = today's SEQUENTIAL
        # loop, byte-for-byte. An int W runs the k worlds on min(W, k_dets) spawn
        # processes and merges them with the SAME pooled-argmax code path. It is a
        # LATENCY lever only — the chosen action is identical (tests/test_kparallel.py).
        if parallel_workers is not None:
            if int(parallel_workers) < 1:
                raise ValueError(
                    f"parallel_workers must be >= 1 (None = sequential), got "
                    f"{parallel_workers}")
            if batch_size > 1 or batch_evaluator is not None:
                raise ValueError(
                    "parallel_workers requires batch_size=1 and no batch_evaluator: "
                    "leaf batching exists to amortize a GPU/IPC round trip for the NET "
                    "candidate, whose evaluator cannot be rebuilt inside a spawn worker. "
                    "The champion's leaf is in-process Cython and gains nothing from it.")
            if net is not None or evaluator is not None:
                raise ValueError(
                    "parallel_workers supports the CHAMPION evaluator only (net=None, "
                    "evaluator=None): the worker rebuilds "
                    "make_heuristic_prior_evaluator(game, cfg) from a pickled cfg, and "
                    "an arbitrary callable / a CUDA net is not transportable.")
            if intra_carry.resolve(intra_reuse):
                raise ValueError(
                    "parallel_workers and intra_reuse are mutually exclusive: the "
                    "within-turn carry retains LIVE trees between two decisions, and a "
                    "tree that lives in a worker process cannot be re-rooted by the "
                    "parent. Run one or the other.")
        self._parallel_workers = None if parallel_workers is None else int(parallel_workers)
        self.parallel_workers = self._parallel_workers   # public alias (manifest read-off)
        self._pool = None
        self._pool_workers = 0
        self._pool_closed = False
        # per-move transport cost of the parallel path (parent-side): seconds spent
        # building the permutations + the pool round trip MINUS the worlds' own search
        # time is not separable here, so we record the two ends we CAN measure.
        self.kparallel_moves = 0
        self.kparallel_dispatch_secs = 0.0   # wall time inside pool.map (search + IPC)
        self.kparallel_prep_secs = 0.0       # parent-side permutation build + payload
        self.kparallel_worker_secs = 0.0     # summed SLOWEST in-worker chunk per move
        # => transport+scheduling overhead == dispatch_secs - worker_secs (+ prep).
        self._game = game
        self._cfg = cfg if cfg is not None else HeuristicPriorConfig()
        self._sims = int(sims)
        self._k_dets = int(k_dets)
        self._c_puct = float(self._cfg.c_puct)
        self._seed = 0 if seed is None else int(seed)
        self._min_pooled_visits = int(min_pooled_visits)
        self._exact_endgame = bool(exact_endgame)
        self._exact_max_k = int(exact_max_k)
        self._exact_budget = int(exact_budget)
        # LATENCY: within-search leaf batching (default 1 = the byte-identical champion
        # path). batch_size>1 makes each per-determinization NeuralMCTS collect that many
        # leaves under VIRTUAL LOSS and evaluate them in ONE `batch_evaluator` call
        # instead of firing one forward per expansion and waiting a full round-trip.
        # See the class docstring's LEAF BATCHING note for the invariant.
        self._batch_size = int(batch_size)
        self._batch_evaluator = batch_evaluator
        self._virtual_loss = float(virtual_loss)
        # MEEPLE-DEDUP, per agent. None (default) = inherit the process-wide
        # CARCASSONNE_MEEPLE_DEDUP flag, which itself defaults OFF -> byte-for-byte
        # the deployed champion. An explicit True/False binds THIS agent regardless
        # of the env, so a dedup-ON candidate and a dedup-OFF champion can play each
        # other inside one worker process. Forwarded to every per-determinization
        # NeuralMCTS below (the pre-search tree of the oracle probe included, so the
        # probe's two trees never disagree about the action space).
        self._meeple_dedup = meeple_dedup
        self.meeple_dedup = meeple_dedup   # public alias (harness/manifest read-off)
        # C3-INTRA within-turn tree carry, per agent. None (default) = inherit the
        # process-wide CARCASSONNE_INTRA_TURN_REUSE flag, which itself defaults OFF ->
        # byte-for-byte the deployed champion. See carcassonne_ai.intra_reuse for the
        # information-legality argument (no hidden info arrives between a turn's tile
        # and meeple decisions) and for why the ACROSS-move sibling is not legal.
        self._intra_reuse = intra_carry.resolve(intra_reuse)
        self.intra_reuse = intra_reuse     # public alias (harness/manifest read-off)
        self._intra: intra_carry.RetainedTurn | None = None
        # The heuristic-prior evaluator is STATELESS (a pure Callable[[Board],
        # (priors, value)] over `game`), so build it ONCE and share it across the
        # fresh per-determinization NeuralMCTS trees — exactly how HeuristicPriorAgent
        # wires it. Reshuffled determinizations are the SAME position (deck order is
        # not in the transposition key), so sharing `game`'s legal-move cache is
        # correctness-neutral.
        #
        # C-cheap value swap (additive; default OFF): an explicit `evaluator` wins;
        # else a `net` builds the deck-aware net-value evaluator (identical priors,
        # learned value); else the byte-for-byte heuristic-value evaluator. With
        # net=None and evaluator=None this is EXACTLY the pre-C-cheap agent.
        self._net = net
        if evaluator is not None:
            self._evaluator = evaluator
        elif net is not None:
            self._evaluator = make_heuristic_prior_evaluator_with_net_value(
                game, self._cfg, net, sighted_game=sighted_game)
        else:
            self._evaluator = make_heuristic_prior_evaluator(game, self._cfg)
        self._move_idx = 0
        self._latched = False
        # eval-harness-compatible instrumentation (mirrors FairHeuristicMCTSAgent).
        self.neural_moves = 0        # always 0 — harness symmetry only
        self.heur_moves = 0          # PIMC (fair search) decisions
        self.latch_k = None
        self.exact_moves = 0
        self.n_timeouts = 0
        self.solver_secs = 0.0
        self.solver_nodes = 0
        self.max_solve_secs = 0.0
        # ADDITIVE distillation hook (no behavior change): after every choose_action
        # this holds the POOLED root-visit distribution {action: summed N over k_dets}
        # — the fair policy TARGET (== agg_n). One-hot {a:1.0} on a forced move; {} on
        # the exact-endgame latch (value-only row). Does NOT touch the pooled-Q pick.
        self.last_pooled_visits: dict | None = None
        # --- Track-F Gate A oracle-prior config + per-game cost telemetry. All zero /
        # None unless oracle_prior_mult is set, so the OFF agent is byte-identical.
        self._oracle_prior_mult = None if oracle_prior_mult is None else int(oracle_prior_mult)
        self._oracle_prior_eps_coef = float(oracle_prior_eps_coef)
        # public alias (harness telemetry read-off keys on this being non-None)
        self.oracle_prior_mult = self._oracle_prior_mult
        self.oracle_moves = 0            # PIMC moves where the oracle pre-search ran
        self.oracle_presearch_worlds = 0  # per-world pre-searches (= k_dets x oracle_moves)
        self.oracle_presearch_secs = 0.0
        self.oracle_mainsearch_secs = 0.0
        self.oracle_presearch_leaf_calls = 0
        self.oracle_mainsearch_leaf_calls = 0
        self.last_reached_root = False    # last move: override reached EVERY world's root
        # per-world overrides of the LAST oracle move (evidence the distribution is
        # per-world, not shared) — None until an oracle move runs. Small (k_dets dicts).
        self.last_world_oracle_priors: list[dict] | None = None
        # --- C3-INTRA telemetry. All zero/None/empty unless the carry is ON, so the
        # OFF agent is byte-identical and pays only a couple of boolean tests per move.
        self.intra_reuse_hits = 0          # decisions served from a carried forest
        self.intra_turns_retained = 0      # tile decisions whose forest was kept
        self.intra_carried_visits_total = 0  # summed carried root visits (all worlds)
        # {reason: count} over every retained forest that was DISCARDED instead of
        # reused — the fallback matrix, observable in a real game. Keys are the
        # intra_reuse.R_* constants.
        self.intra_reuse_discards: dict[str, int] = {}
        # per-world carried root visits of the LAST decision — None when that decision
        # did NOT reuse (forced move, tile decision, any fallback), a list of k_dets
        # ints when it did. The primary "reuse fired" probe.
        self.last_intra_carried_visits: list[int] | None = None
        # per-world root visits AFTER the carried search — i.e. the EFFECTIVE budget the
        # meeple decision actually searched with. The ON contract is
        # last_intra_root_visits[i] == last_intra_carried_visits[i] + sims: the carry is
        # a warm start, it does not replace any of the new simulations.
        self.last_intra_root_visits: list[int] | None = None
        # the determinized worlds the LAST decision actually searched (flag-ON only) —
        # lets a test prove the meeple call kept the tile call's decks rather than
        # redrawing them.
        self.last_det_boards: list | None = None

    # --- deterministic per-move seed derivation (mirrors FairHeuristicMCTSAgent) --
    def det_seed_base(self, move_idx: int) -> int:
        return (self._seed * 1_000_003 + move_idx * 8191) & 0x7FFFFFFF

    def det_search_seed(self, move_idx: int, det_idx: int) -> int:
        return self.det_seed_base(move_idx) + 100 + det_idx

    # --- the fair PIMC move -------------------------------------------------
    def _pimc_move(self, board: Board, move_idx: int) -> int:
        self.heur_moves += 1
        if self._intra_reuse:
            self.last_intra_carried_visits = None   # per-decision; refilled on a hit
            self.last_intra_root_visits = None
            self.last_det_boards = None
        legal = np.flatnonzero(self._game.get_valid_moves(board))
        if legal.size == 0:
            raise ValueError("fair agent asked to move with no legal actions")
        if legal.size == 1:
            # Forced move: no search runs, so there is nothing to carry INTO and the
            # retained forest (if any) can never be continued past here.
            self._intra_drop(intra_carry.R_FORCED)
            self.last_pooled_visits = {int(legal[0]): 1.0}   # forced: one-hot policy
            return int(legal[0])   # forced move: skip the K searches
        base = self.det_seed_base(move_idx)
        det_rng = random.Random(base + 1)          # deck reshuffles
        root_key = self._game.string_representation(board)
        agg_n: dict[int, float] = defaultdict(float)
        agg_w: dict[int, float] = defaultdict(float)
        oracle = self._oracle_prior_mult is not None
        if oracle:
            self.oracle_moves += 1
            self.last_world_oracle_priors = []
            _reached = True
        # --- C3-INTRA (flag-gated) -------------------------------------------------
        # `carried` is the tile decision's forest, re-rooted at the position we were
        # just handed — or None, which means "search fresh" and is ALWAYS safe.
        # `retain` says this decision's forest is worth keeping for the meeple half.
        carried = self._intra_try_reuse(board, move_idx, root_key) if self._intra_reuse else None
        retain = self._intra_reuse and board.state.phase == GamePhase.TILES
        kept: list = []
        worlds: list = []
        # --- k-PARALLEL (G6 stage 1): run the k independent worlds on min(W, k)
        # spawn processes. Mutually exclusive with the C3-INTRA carry (rejected at
        # construction), so `carried` is None and `retain` False here; everything
        # after this block — the pooled accumulators, the pooled-Q pick — is the
        # SAME code the sequential path runs, fed the SAME per-world stats in the
        # SAME world order.
        k_range = range(self._k_dets)
        if self._parallel_workers is not None:
            k_range = range(0)                    # the sequential loop below is inert
            for stats, telem in self._parallel_worlds(board, base, det_rng, root_key):
                if oracle:
                    _reached = self._absorb_world_telem(telem) and _reached
                _merge_root_stats(stats, agg_n, agg_w)
        for i in k_range:
            if carried is not None:
                # SAME determinization as the tile decision (its deck is provably
                # untouched by the placement — see intra_reuse's module docstring), and
                # the SAME tree, re-rooted at the child under the action we played. The
                # search below adds a full `sims` on top of the carried visits.
                m, b = carried[i]
                m.search(b)
                # POOL BEFORE CLEARING — clear() wipes _nodes, and the harvest below
                # reads the root out of it.
                root = m._nodes.get(root_key) or m._nodes[self._game.string_representation(b)]
                pool_root_stats(root, agg_n, agg_w)
                self.last_intra_root_visits.append(int(root.N))
                if retain:
                    kept.append((m, b))
                    # clear() would ALSO wipe the tree we are keeping; do only its other
                    # half so the shared Game's legal-cache cadence stays exactly what it
                    # is with the flag OFF (Phase-0.3: never serve a stale rotation mask).
                    self._game.clear_caches()
                else:
                    m.clear()
                worlds.append(b)
                continue
            b = FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
            m, stats, telem = search_one_world(
                self._game, self._evaluator, b, root_key,
                sims=self._sims, c_puct=self._c_puct, seed=base + 100 + i,
                batch_size=self._batch_size, batch_evaluator=self._batch_evaluator,
                virtual_loss=self._virtual_loss, meeple_dedup=self._meeple_dedup,
                oracle_prior_mult=self._oracle_prior_mult,
                oracle_prior_eps_coef=self._oracle_prior_eps_coef)
            if oracle:
                _reached = self._absorb_world_telem(telem) and _reached
            _merge_root_stats(stats, agg_n, agg_w)
            if retain:
                kept.append((m, b))   # keep the tree ALIVE for the meeple decision
                self._game.clear_caches()   # clear()'s other half — see the note above
            else:
                m.clear()
            if self._intra_reuse:
                worlds.append(b)
        if oracle:
            self.last_reached_root = bool(_reached)
        if self._intra_reuse:
            self.last_det_boards = worlds
        if not agg_n:                              # pathological: nothing visited
            for _m, _b in kept:                    # nothing worth carrying
                _m.clear()
            self.last_pooled_visits = {}           # no search signal -> value-only row
            return int(legal[0])
        # ADDITIVE: stash the pooled visit distribution (the fair policy target)
        # BEFORE the pooled-Q pick. This does NOT change the returned action.
        self.last_pooled_visits = dict(agg_n)
        action = pooled_q_argmax(agg_n, agg_w, self._min_pooled_visits)
        if retain:
            self._intra_retain(kept, action, board, move_idx, root_key)
        return action

    # --- oracle-probe telemetry (shared by the sequential + parallel paths) -----
    def _absorb_world_telem(self, telem: dict) -> bool:
        """Fold ONE world's oracle-probe cost record into the agent counters.

        Returns whether that world's root-prior override was non-empty (the
        `last_reached_root` conjunct). Only called on an oracle move."""
        self.oracle_presearch_secs += telem["presearch_secs"]
        self.oracle_presearch_leaf_calls += telem["presearch_leaf_calls"]
        self.oracle_presearch_worlds += 1
        self.oracle_mainsearch_secs += telem["mainsearch_secs"]
        self.oracle_mainsearch_leaf_calls += telem["mainsearch_leaf_calls"]
        override = telem["override"]
        self.last_world_oracle_priors.append(override)
        return bool(override)

    # --- k-PARALLEL: the process pool + the per-move dispatch -------------------
    def _game_spec(self) -> dict:
        """The kwargs that rebuild THIS agent's Game inside a spawn worker."""
        g = self._game
        return {
            "players": g.players,
            "tile_sets": g.tile_sets,
            "supplementary_rules": g.supplementary_rules,
            "window_size": g.window_size,
            "enable_legal_moves_cache": True,
            "include_farm_scalars": g.include_farm_scalars,
            "sighted": g.sighted,
        }

    def _world_kw(self) -> dict:
        """The `search_one_world` kwargs shared by every world of every move.

        MEEPLE-DEDUP is RESOLVED here rather than shipped as None: the child would
        re-resolve it from its own env, and binding the parent's answer makes the
        split immune to an env that differs across the process boundary."""
        from . import meeple_equiv

        return {
            "sims": self._sims,
            "c_puct": self._c_puct,
            "batch_size": self._batch_size,
            "batch_evaluator": None,      # rejected at construction
            "virtual_loss": self._virtual_loss,
            "meeple_dedup": bool(meeple_equiv.resolve(self._meeple_dedup)),
            "oracle_prior_mult": self._oracle_prior_mult,
            "oracle_prior_eps_coef": self._oracle_prior_eps_coef,
        }

    def _ensure_pool(self, workers: int):
        """Lazily create (and memoize) the spawn pool. Persistent for the agent's
        life — a per-move pool would spend the whole latency win on fork+import."""
        import multiprocessing as mp

        if self._pool is not None and self._pool_workers == workers:
            return self._pool
        self.close()
        # Bind the leaf cfg NOW so the worker's evaluator can never fall through to
        # its own env-built DEFAULT_CONFIG (the env is inherited, but an explicitly
        # resolved cfg removes the dependence entirely).
        cfg = self._cfg
        if getattr(cfg, "leaf_cfg", None) is None:
            cfg = dataclasses.replace(cfg, leaf_cfg=cfg.resolved_leaf_cfg())
        env_fp = {k: os.environ.get(k) for k in _LEAF_ENV_KEYS}
        ctx = mp.get_context("spawn")
        try:
            self._pool = ctx.Pool(
                processes=workers,
                initializer=_kparallel_worker_init,
                initargs=(self._game_spec(), cfg, self._world_kw(), env_fp),
            )
        except AssertionError as e:      # "daemonic processes are not allowed..."
            raise RuntimeError(
                "k-parallel could not start a worker pool — this agent is running "
                "inside a DAEMONIC process (an eval-farm worker). The lever targets "
                "single-GAME latency; an eval farm already parallelizes at the game "
                "level, so run the farm's agents with parallel_workers=None."
            ) from e
        self._pool_workers = workers
        self._pool_closed = False
        _KP_LIVE_POOLS.add(self._pool)
        return self._pool

    def close(self) -> None:
        """Terminate the k-parallel pool. Idempotent; safe to call when off.

        Pool workers are daemonic AND block on the task pipe, so they also exit on
        their own if the parent dies — but a killed mp main does NOT reap spawn
        children in general, so the lifecycle is made explicit here and registered
        with atexit."""
        pool, self._pool = self._pool, None
        self._pool_workers = 0
        if pool is not None:
            _KP_LIVE_POOLS.discard(pool)
            pool.terminate()
            pool.join()
        self._pool_closed = True

    def __del__(self):                   # pragma: no cover - interpreter teardown
        try:
            self.close()
        except Exception:
            pass

    def _parallel_worlds(self, board: Board, base: int, det_rng: random.Random,
                         root_key: str):
        """Search this move's k determinization worlds on the pool.

        Yields ``(stats, telem)`` in WORLD ORDER 0..k_dets-1 — the order the
        sequential loop merges them in, which is what makes the float accumulation
        bit-identical.

        `det_rng` is consumed here exactly as `reshuffled_determinization` would
        consume it (one shuffle of an n-element list per world), so the agent's RNG
        stream is the same in both modes."""
        workers = min(self._parallel_workers, self._k_dets)
        pool = self._ensure_pool(workers)   # OUTSIDE the timers: one-off spawn cost
        deck = board.state.deck
        n = len(deck)
        t0 = time.perf_counter()
        # Stable sort by description == the canonicalization inside
        # reshuffled_determinization; order[j] is the ORIGINAL index of the j-th
        # canonical tile, so after the shuffle perm[j] is the original index of the
        # tile the sequential path would have at deck position j.
        order = sorted(range(n), key=lambda i: deck[i].description)
        perms = []
        for _ in range(self._k_dets):
            p = list(order)
            det_rng.shuffle(p)
            perms.append(p)
        per = -(-self._k_dets // workers)          # ceil(k / workers)
        payloads = []
        for s in range(0, self._k_dets, per):
            jobs = [(i, perms[i], base + 100 + i)
                    for i in range(s, min(s + per, self._k_dets))]
            payloads.append((board, root_key, jobs))
        self.kparallel_prep_secs += time.perf_counter() - t0
        t1 = time.perf_counter()
        results = pool.map(_kparallel_worker_chunk, payloads, chunksize=1)
        self.kparallel_dispatch_secs += time.perf_counter() - t1
        self.kparallel_moves += 1
        by_world = {}
        slowest = 0.0
        for chunk_secs, chunk_out in results:
            slowest = max(slowest, chunk_secs)
            for world_idx, stats, telem in chunk_out:
                by_world[world_idx] = (stats, telem)
        # The critical path a perfect (zero-overhead) split would have cost.
        self.kparallel_worker_secs += slowest
        for i in range(self._k_dets):
            yield by_world[i]

    # --- C3-INTRA: within-turn tree carry (flag-gated; see intra_reuse.py) ------
    def _intra_retain(self, kept: list, action: int, board: Board,
                      move_idx: int, root_key: str) -> None:
        """Hold this TILE decision's forest for the meeple decision that follows it."""
        self._intra = intra_carry.RetainedTurn(
            move_idx=move_idx, action=int(action),
            player=int(board.state.current_player), root_key=root_key,
            trees=[m for m, _ in kept], boards=[b for _, b in kept])
        self.intra_turns_retained += 1

    def _intra_drop(self, reason: str) -> None:
        """Discard any retained forest, freeing its trees, and count why.

        A no-op when nothing is retained (the common case), so the discard counter
        reads as "forests we kept and then could not use" rather than being dominated
        by decisions that never had one."""
        if self._intra is None:
            return
        for m in self._intra.trees:
            m.clear()
        self._intra = None
        self.intra_reuse_discards[reason] = self.intra_reuse_discards.get(reason, 0) + 1

    def discard_intra_carry(self) -> None:
        """Public invalidation hook for a harness that moves the agent off its own
        game timeline (save/restore, a replayed prefix, seat reuse across games).

        Calling it is never REQUIRED for correctness — ``intra_reuse.match`` re-derives
        each retained world's post-placement position and demands it equal the position
        actually presented, so a stale forest cannot be served even if ``_move_idx`` is
        re-seated onto a colliding index (and if that derived check DID pass, the carry
        would by definition be a correct continuation). It exists so a caller can drop
        the memory eagerly and make the intent explicit."""
        self._intra_drop(intra_carry.R_NOT_PRIOR)

    def _intra_try_reuse(self, board: Board, move_idx: int, root_key: str):
        """Return the re-rooted per-world ``(tree, board)`` pairs, or None to search fresh.

        ALL-OR-NOTHING: if any world fails either the continuation check or the
        search-side re-root guard, the whole forest is dropped and the decision runs a
        normal fresh PIMC search. A partially-carried pool would mix worlds searched to
        different depths into one pooled-Q, which is not a thing we want to reason about.
        """
        retained = self._intra
        worlds, reason = intra_carry.match(self._game, retained, board, move_idx, root_key)
        if worlds is None:
            self._intra_drop(reason)
            return None
        out, carried = [], []
        for m, nb in zip(retained.trees, worlds):
            n = m.reroot_to(nb)
            if n == 0:                 # guard rejected (see NeuralMCTS.reroot_to)
                self._intra_drop(intra_carry.R_REROOT)
                return None
            out.append((m, nb))
            carried.append(n)
        self._intra = None             # consumed; the trees live on in `out`
        self.intra_reuse_hits += 1
        self.last_intra_carried_visits = carried
        self.last_intra_root_visits = []   # filled per world as each search completes
        self.intra_carried_visits_total += int(sum(carried))
        return out

    # --- the fair exact endgame (marginalized; identical to FairHeuristicMCTSAgent
    #     but with the configurable exact_max_k band) --------------------------
    def _exact_move(self, board: Board) -> int | None:
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

    # --- public API ----------------------------------------------------------
    def choose_action(self, board: Board) -> int:
        """Pick the fair move for `board`. Never mutates the caller's board."""
        move_idx = self._move_idx
        self._move_idx += 1
        if self._exact_endgame and not self._latched:
            st = board.state
            k = k_remaining(st)
            if st.phase == GamePhase.TILES and k <= self._exact_max_k:
                self._latched = True
                self.latch_k = k
        if self._latched:
            a = self._exact_move(board)
            if a is not None:
                # The solver owns this decision — no search runs, so a retained forest
                # can never be continued past it. Drop it here rather than leaving it
                # to expire against the next continuation check.
                self._intra_drop(intra_carry.R_LATCHED)
                self.last_pooled_visits = {}   # exact-endgame row: value-only (no policy)
                return a
            # BudgetExceeded: fair PIMC fallback for THIS decision only. A forest
            # retained by an EARLIER PIMC fallback in this same turn is still a valid
            # continuation, so _pimc_move is allowed to use it (the derived key check
            # is what decides, not the latch).
        return self._pimc_move(board, move_idx)

    move = choose_action
