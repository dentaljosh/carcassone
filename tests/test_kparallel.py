"""k-PARALLEL INFERENCE (G6 stage 1) — the DETERMINISM PROOF.

The fair champion's ``k_dets`` determinization worlds are independent until the
pooled-Q argmax, so running them on separate processes must be BEHAVIOR-IDENTICAL,
not a search change. That claim is the whole lever: it is what lets the split be
adopted on a latency bench alone, with no strength re-eval. This module is the
evidence.

  (a) ``parallel_workers=None`` is the untouched sequential path (no pool, no
      parallel counters move) — the invariant the Chaquopy/Android bridge relies
      on, since Android has no ``multiprocessing`` at all.
  (b) the parent-side permutation recipe reproduces
      ``reshuffled_determinization`` EXACTLY (this is the one place the split
      leans on a CPython implementation detail — ``random.Random.shuffle`` draws
      depend on ``len(x)`` only — so it is proven, not assumed);
  (c) FULL GAMES stepped side by side, sequential vs parallel, from identical
      seeds: the CHOSEN ACTION is identical at every move, and the pooled root
      stats (N and W, the inputs to the pooled-Q pick) are float-EQUAL at every
      move;
  (d) the exact marginalized endgame (K<=2) still fires and still agrees under
      the parallel mode;
  (e) the option combinations the split cannot honour are rejected loudly.
"""
import os
import random
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "level2"))

from carcassonne_ai import fair_agent as FA  # noqa: E402
from carcassonne_ai.champion_factory import make_production_champion  # noqa: E402
from carcassonne_ai.fair_agent import (  # noqa: E402
    FairHeuristicMCTSAgent,
    FairHeuristicPriorAgent,
)
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig  # noqa: E402

# The compact-leaf test toggle is a MODULE global set by conftest, not an env var
# the spawn child can inherit, so a worker would silently search the other leaf.
pytestmark = pytest.mark.skipif(
    os.environ.get("CARC_TEST_COMPACT_LEAF") == "1",
    reason="compact-leaf toggle is a conftest module global; spawn workers can't see it",
)

SIMS = 32        # per determinization — small enough for full games in a test
K_DETS = 4


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _champion(game, seed, workers, sims=SIMS, k_dets=K_DETS):
    """The PRODUCTION fair champion (routed through champion_factory so the
    kwarg threading is covered too). verify=False only skips the leaf re-proof.

    ``backend="python"`` is PINNED, not inherited (F-3, 2026-08-02): the SPAWN split
    this module tests is a python-only feature — the Rust core folds the same k worlds
    across OS threads and the factory RAISES on the pair — so these cases must keep
    naming their engine if the factory default is ever flipped off ``python``."""
    return make_production_champion(
        "fair", game=game, seed=seed, sims=sims, k_dets=k_dets,
        verify=False, backend="python", parallel_workers=workers)


class _PoolSpy:
    """Capture every (agg_n, agg_w) handed to the pooled-Q pick, in call order."""

    def __init__(self):
        self.calls = []
        self._real = FA.pooled_q_argmax

    def __call__(self, agg_n, agg_w, min_visits=FA.DEFAULT_MIN_POOLED_VISITS):
        self.calls.append((dict(agg_n), dict(agg_w)))
        return self._real(agg_n, agg_w, min_visits)


def _play_side_by_side(deck_seed, agent_seed, workers, max_moves=None,
                       k_dets=K_DETS):
    """Step a sequential and a parallel champion over the SAME game, asserting
    move-for-move identity. Returns (n_moves, seq_agent, par_agent)."""
    random.seed(deck_seed)              # seeds the engine deck shuffle
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    # A SECOND Game for the parallel agent: it must not share the sequential
    # agent's legal-move memo, or the test could hide a cache-coupling bug.
    game_par = Game(enable_legal_moves_cache=True)

    seq = _champion(game, agent_seed, None, k_dets=k_dets)
    par = _champion(game_par, agent_seed, workers, k_dets=k_dets)
    spy = _PoolSpy()
    FA.pooled_q_argmax = spy
    n = 0
    try:
        while game.get_game_ended(board, 0) == 0.0:
            if max_moves is not None and n >= max_moves:
                break
            before = len(spy.calls)
            a_seq = seq.choose_action(board)
            mid = len(spy.calls)
            a_par = par.choose_action(board)
            after = len(spy.calls)
            assert a_seq == a_par, (
                f"move {n}: sequential chose {a_seq}, parallel chose {a_par}")
            # Both took the same branch (both searched, or both were forced /
            # solved) — a mode that skipped the search would be a silent divergence.
            assert (mid - before) == (after - mid), (
                f"move {n}: search-branch mismatch "
                f"(seq pooled {mid - before}x, par pooled {after - mid}x)")
            if mid - before == 1:
                n_seq, w_seq = spy.calls[before]
                n_par, w_par = spy.calls[mid]
                assert n_seq == n_par, f"move {n}: pooled N differs"
                assert w_seq == w_par, f"move {n}: pooled W differs"   # float equality
            assert seq.last_pooled_visits == par.last_pooled_visits, n
            board, _ = game.get_next_state(board, a_seq)
            n += 1
    finally:
        FA.pooled_q_argmax = spy._real
        par.close()
    return n, seq, par


# --------------------------------------------------------------------------- #
# (a) OFF is the untouched sequential path                                     #
# --------------------------------------------------------------------------- #
def test_default_is_none_and_never_builds_a_pool():
    random.seed(11)
    game = Game(enable_legal_moves_cache=True)
    a = FairHeuristicPriorAgent(game, HeuristicPriorConfig(), sims=8, k_dets=2, seed=3)
    assert a.parallel_workers is None
    assert a._pool is None
    b = game.get_init_board()
    a.choose_action(b)
    assert a._pool is None
    assert a.kparallel_moves == 0
    assert a.kparallel_dispatch_secs == 0.0
    assert a.kparallel_worker_secs == 0.0


def test_factory_manifest_unstamped_when_off_and_stamped_when_on():
    # backend PINNED on BOTH legs (2026-08-03): the factory default is now "auto", and
    # an OFF leg on the yaml engine vs an ON leg on python would be a two-variable
    # contrast in a test about one manifest key.
    off = make_production_champion("fair", seed=0, sims=8, k_dets=2, verify=False,
                                   backend="python")
    assert "parallel_workers" not in off.manifest      # no hash drift when OFF
    on = make_production_champion("fair", seed=0, sims=8, k_dets=2, verify=False,
                                  backend="python", parallel_workers=2)
    try:
        assert on.manifest["parallel_workers"]["workers"] == 2
        assert on.parallel_workers == 2
    finally:
        on.close()


# --------------------------------------------------------------------------- #
# (b) the permutation recipe == reshuffled_determinization                     #
# --------------------------------------------------------------------------- #
def test_permutation_recipe_matches_reshuffle():
    """The parent derives each world's deck order by shuffling an INT list in
    description-sorted order instead of deepcopying the board. Prove that (i) the
    resulting deck is tile-for-tile the one ``reshuffled_determinization`` builds
    and (ii) the shared ``det_rng`` ends in the SAME state, for several worlds in
    a row (the rng is consumed sequentially across the k worlds)."""
    random.seed(4242)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    for _ in range(12):                 # step into midgame (partial deck)
        legal = np.flatnonzero(game.get_valid_moves(board))
        board, _ = game.get_next_state(board, int(legal[0]))

    rng_a = random.Random(9001)
    rng_b = random.Random(9001)
    deck = board.state.deck
    order = sorted(range(len(deck)), key=lambda i: deck[i].description)
    for world in range(6):
        det = FairHeuristicMCTSAgent.reshuffled_determinization(board, rng_a)
        perm = list(order)
        rng_b.shuffle(perm)
        rebuilt = [deck[i] for i in perm]
        assert len(rebuilt) == len(det.state.deck)
        assert all(rebuilt[j].description == det.state.deck[j].description
                   for j in range(len(rebuilt))), f"world {world}: deck order differs"
        assert rng_a.getstate() == rng_b.getstate(), f"world {world}: rng drift"
    # ...and the caller's board was never mutated by either recipe.
    assert board.state.deck is deck


# --------------------------------------------------------------------------- #
# (c)+(d) THE PROOF: full games, sequential vs parallel                        #
# --------------------------------------------------------------------------- #
@pytest.mark.slow      # ~2.5 min each: two agents playing a full game move-for-move
@pytest.mark.parametrize("deck_seed,agent_seed,workers", [(7, 101, 4), (23, 202, 2)])
def test_full_game_action_identity(deck_seed, agent_seed, workers):
    """A FULL game stepped side by side: identical action at every move, and
    float-equal pooled root stats at every searched move. Two games (two params)
    at two worker counts, including workers < k_dets (2 worlds per process)."""
    n, seq, par = _play_side_by_side(deck_seed, agent_seed, workers)
    assert n > 40, f"game ended suspiciously early ({n} moves)"
    assert par.kparallel_moves > 0, "the parallel path never ran"
    assert seq.heur_moves == par.heur_moves
    # (d) the marginalized exact endgame latched and agreed under the split.
    assert seq.exact_moves > 0 and par.exact_moves == seq.exact_moves
    assert seq.latch_k == par.latch_k
    assert seq.n_timeouts == par.n_timeouts == 0


def test_k8_split_four_ways_over_a_prefix():
    """k8 split 4 ways (2 worlds/process) — the CL-068 k8x1376 shape, at test
    sims — over a game prefix. Covers the ceil(k/workers) chunking."""
    n, seq, par = _play_side_by_side(31, 303, 4, max_moves=14, k_dets=8)
    assert n == 14
    assert par.kparallel_moves > 0


# --------------------------------------------------------------------------- #
# (e) loud rejection of the combinations the split cannot honour               #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kw,msg", [
    ({"parallel_workers": 0}, "parallel_workers must be >= 1"),
    ({"parallel_workers": 2, "batch_size": 4}, "batch_size=1"),
    ({"parallel_workers": 2, "evaluator": lambda b: None}, "CHAMPION evaluator only"),
    ({"parallel_workers": 2, "intra_reuse": True}, "mutually exclusive"),
])
def test_rejected_combinations(kw, msg):
    game = Game(enable_legal_moves_cache=True)
    with pytest.raises(ValueError, match=msg):
        FairHeuristicPriorAgent(game, HeuristicPriorConfig(), sims=4, k_dets=2, **kw)


def test_factory_rejects_parallel_in_clairvoyant_mode():
    with pytest.raises(ValueError, match="FAIR-mode feature"):
        make_production_champion("clairvoyant", seed=0, sims=8, verify=False,
                                 backend="python", parallel_workers=2)


def test_close_is_idempotent_and_reaps_the_pool():
    random.seed(5)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    a = FairHeuristicPriorAgent(game, HeuristicPriorConfig(), sims=8, k_dets=2,
                                seed=1, parallel_workers=2)
    while a.kparallel_moves == 0:        # skip forced moves (they never search)
        board, _ = game.get_next_state(board, a.choose_action(board))
    assert a._pool is not None
    procs = list(a._pool._pool)
    a.close()
    a.close()                            # idempotent
    assert a._pool is None
    for p in procs:
        p.join(10)
        assert not p.is_alive(), "a k-parallel spawn worker outlived close()"
