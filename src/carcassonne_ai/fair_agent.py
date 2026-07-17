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
from .mcts import HeuristicMCTS, NeuralMCTS
from .heuristic_prior_mcts import (
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
    make_heuristic_prior_evaluator_with_net_value,
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
                 sims: int = 688, k_dets: int = 4, seed: int | None = None,   # deploy default = adopted k4×688=2752 (CL-054, 2026-07-13; was k8×344)
                 min_pooled_visits: int = DEFAULT_MIN_POOLED_VISITS,
                 exact_endgame: bool = True, exact_max_k: int = EXACT_MAX_K,
                 exact_budget: int = DEFAULT_EXACT_BUDGET,
                 net=None, evaluator=None, sighted_game: Game | None = None,
                 batch_size: int = 1, batch_evaluator=None,
                 virtual_loss: float = 1.0):
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

    # --- deterministic per-move seed derivation (mirrors FairHeuristicMCTSAgent) --
    def det_seed_base(self, move_idx: int) -> int:
        return (self._seed * 1_000_003 + move_idx * 8191) & 0x7FFFFFFF

    def det_search_seed(self, move_idx: int, det_idx: int) -> int:
        return self.det_seed_base(move_idx) + 100 + det_idx

    # --- the fair PIMC move -------------------------------------------------
    def _pimc_move(self, board: Board, move_idx: int) -> int:
        self.heur_moves += 1
        legal = np.flatnonzero(self._game.get_valid_moves(board))
        if legal.size == 0:
            raise ValueError("fair agent asked to move with no legal actions")
        if legal.size == 1:
            self.last_pooled_visits = {int(legal[0]): 1.0}   # forced: one-hot policy
            return int(legal[0])   # forced move: skip the K searches
        base = self.det_seed_base(move_idx)
        det_rng = random.Random(base + 1)          # deck reshuffles
        root_key = self._game.string_representation(board)
        agg_n: dict[int, float] = defaultdict(float)
        agg_w: dict[int, float] = defaultdict(float)
        for i in range(self._k_dets):
            b = FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
            m = NeuralMCTS(game=self._game, evaluator=self._evaluator,
                           simulations=self._sims, c_puct=self._c_puct,
                           seed=base + 100 + i,
                           batch_size=self._batch_size,
                           batch_evaluator=self._batch_evaluator,
                           virtual_loss=self._virtual_loss)
            m.search(b)
            # deck order isn't in the key, so the reshuffled root shares the
            # original board's key (same fallback as FairHeuristicMCTSAgent).
            root = m._nodes.get(root_key) or m._nodes[self._game.string_representation(b)]
            pool_root_stats(root, agg_n, agg_w)
            m.clear()
        if not agg_n:                              # pathological: nothing visited
            self.last_pooled_visits = {}           # no search signal -> value-only row
            return int(legal[0])
        # ADDITIVE: stash the pooled visit distribution (the fair policy target)
        # BEFORE the pooled-Q pick. This does NOT change the returned action.
        self.last_pooled_visits = dict(agg_n)
        return pooled_q_argmax(agg_n, agg_w, self._min_pooled_visits)

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
                self.last_pooled_visits = {}   # exact-endgame row: value-only (no policy)
                return a
            # BudgetExceeded: fair PIMC fallback for THIS decision only.
        return self._pimc_move(board, move_idx)

    move = choose_action
