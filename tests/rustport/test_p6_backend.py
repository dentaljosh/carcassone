"""Fast always-on guards for the rustport P6 desktop integration: the adapter
(`carcassonne_ai.rust_agent.RustFairAgent`) and the `champion_factory`
``backend="rust"`` selector.

The full G6 gate is `scripts/rustport/reconcile_backend.py --leg all` at
k8x1376 over >=100 deck-paired games.  These are the cheap subset plus the
unit-level contracts a game sweep can only catch indirectly:

* the factory's semantic guards RUN AGAINST carc_rs when the Rust backend is
  selected (the leaf VALUE PANEL re-evaluated by `carc_core::leaf`) — the whole
  point of the selector is that a wrong Rust leaf cannot reach the board;
* the ``backend="python"`` manifest is BYTE-IDENTICAL to the pre-feature one, so
  the selector costs no re-review for any existing caller;
* the mirror lifecycle: `start_game(board)` reads the real deck out of the
  caller's board and lands on the same state `start_game_from_seed` does;
* **reconcile mode really fires** — a deliberately desynced mirror must raise
  `MirrorDesync`.  A drift detector nobody has ever seen fire is not evidence;
* `stats()` carries every field the eval harness reads, in both the agent shape
  and the `_MarginalizedHandoff` wrapper shape;
* action identity vs the Python champion on a short game at a cheap budget, and
  thread-count invariance through the adapter.

⚠️ `fair_common` MUST be imported before `carcassonne_ai`, so it is imported
before every other project import in this file.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

try:                                    # noqa: E402
    import fair_common as F             # applies the leaf env preamble
except RuntimeError as _e:              # pragma: no cover - import-order guard
    # Some earlier module in this session froze `carcassonne_ai` against a
    # different environment, so the PYTHON oracle here could not be the champion.
    # Skipping is the only honest option — a green gate against the wrong
    # champion is worse than a red one (the P4 war story). Run this module in its
    # own process (`pytest tests/rustport`) to gate it.
    pytest.skip(f"production leaf env was not frozen into carcassonne_ai: {_e}",
                allow_module_level=True)

from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai import rust_agent as RA  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

# Cheap but non-degenerate: 2 worlds x 48 sims still exercises the pool merge,
# the priors, the PUCT descent and the pooled-Q tiebreaks.
SIMS, KDETS = 48, 2
DECK = 98_000_000_777          # throwaway fuzz seed, NOT a registered band


def _fresh(deck_seed: int = DECK):
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True)
    return game, game.get_init_board()


def _rs(game, *, sims=SIMS, k_dets=KDETS, seed=101, threads=1, **kw):
    return CF.make_production_champion(
        "fair", game=game, seed=seed, sims=sims, k_dets=k_dets, verify=True,
        exact_budget=F.EXACT_BUDGET, backend="rust", rust_threads=threads, **kw)


# --------------------------------------------------------------------------- #
# The factory selector                                                         #
# --------------------------------------------------------------------------- #
def test_rust_leaf_value_panel_matches_the_golden():
    """The factory's DEEPEST guard, computed by the engine that will play."""
    leaf_cfg = CF.production_leaf_cfg()
    panel = RA.leaf_value_panel_rs(leaf_cfg)
    assert panel == {k: v[2] for k, v in CF._LEAF_VALUE_PANEL.items()}
    # ... and it is the same panel the Python leaf produces.
    assert panel == CF._leaf_value_panel(leaf_cfg)


def test_verify_leaf_backend_rust_records_both_panels():
    prov = CF.verify_leaf(CF.production_leaf_cfg(), backend="rust")
    assert prov["leaf_value_panel_rust"] == prov["leaf_value_panel"]
    assert prov["hashes"]["harness_leaf_hash"] == CF.LEAF_HASH_HARNESS


def test_verify_leaf_backend_rust_raises_on_a_wrong_leaf():
    """A leaf that is NOT the champion must be refused on the rust path too."""
    import dataclasses as dc

    bad = dc.replace(CF.production_leaf_cfg(), v29_meeple_curve=CF.CURVE100)
    with pytest.raises(Exception) as e:
        CF.verify_leaf(bad, backend="rust")
    assert "curve" in str(e.value)


def test_python_backend_manifest_is_byte_identical():
    """The selector must cost EXACTLY nothing for every existing caller."""
    man = CF.resolved_manifest("fair")
    assert "backend" not in man
    assert "leaf_value_panel_rust" not in man
    assert man == CF.resolved_manifest("fair", backend="python")


def test_rust_backend_stamps_the_manifest():
    man = CF.resolved_manifest("fair", backend="rust")
    b = man["backend"]
    assert b["name"] == "rust" and b["default"] == "python"
    assert b["carc_rs_version"] and b["tile_data_source_sha256"]
    assert man["leaf_value_panel_rust"] == man["leaf_value_panel"]


def test_rust_backend_rejects_the_wrong_modes_and_knobs():
    with pytest.raises(ValueError, match="FAIR-mode"):
        CF.make_production_champion("clairvoyant", sims=8, backend="rust")
    with pytest.raises(ValueError, match="rust_threads"):
        CF.make_production_champion("fair", sims=8, k_dets=1, rust_threads=4)
    with pytest.raises(ValueError, match="python-only|parallel_workers"):
        CF.make_production_champion("fair", sims=8, k_dets=1, backend="rust",
                                    parallel_workers=2)
    with pytest.raises(ValueError, match="backend"):
        CF.make_production_champion("fair", sims=8, k_dets=1, backend="julia")


def test_rust_threads_stamp_only_when_asked():
    game, _ = _fresh()
    a = CF.make_production_champion("fair", game=game, sims=8, k_dets=1,
                                    backend="rust")
    assert "rust_threads" not in a.manifest
    b = _rs(Game(enable_legal_moves_cache=True), sims=8, k_dets=1, threads=2)
    assert b.manifest["rust_threads"]["threads"] == 2


# --------------------------------------------------------------------------- #
# The mirror lifecycle                                                         #
# --------------------------------------------------------------------------- #
def test_start_game_from_board_equals_start_game_from_seed():
    """`[next_tile] + deck` IS the draw order — no RNG assumption needed."""
    game, board = _fresh()
    a = _rs(game)
    a.start_game(board)
    from_board = a.state_digest()
    b = _rs(Game(enable_legal_moves_cache=True))
    b.start_game_from_seed(DECK)
    assert from_board == b.state_digest()
    assert a.string_repr() == game.string_representation(board)


def test_advance_is_the_only_way_the_mirror_moves():
    game, board = _fresh()
    a = _rs(game)
    with pytest.raises(RuntimeError, match="advance before start_game"):
        a.advance(0)
    a.start_game(board)
    legal = [i for i, v in enumerate(game.get_valid_moves(board)) if v]
    board2, _ = game.get_next_state(board, legal[0])
    # The mirror is STILL at the old position until advance() is called.
    assert a.string_repr() == game.string_representation(board)
    a.advance(legal[0], board_after=board2)
    assert a.string_repr() == game.string_representation(board2)


def test_reconcile_mode_actually_fires(monkeypatch):
    """A drift detector nobody has seen fire is not evidence. Desync on purpose."""
    monkeypatch.setenv(RA.RECONCILE_ENV, "1")
    game, board = _fresh()
    a = _rs(game)
    a.start_game(board)
    legal = [i for i, v in enumerate(game.get_valid_moves(board)) if v]
    board2, _ = game.get_next_state(board, legal[0])
    # Move the MIRROR only: the python board stays at ply 0.
    a.advance(legal[0])
    with pytest.raises(RA.MirrorDesync) as e:
        a.choose_action(board)
    assert "desync" in str(e.value)
    # And the same drift is caught on the post-action side.
    with pytest.raises(RA.MirrorDesync):
        a.check_sync(board, "explicit")


def test_reconcile_off_by_default():
    assert RA.reconcile_enabled() is False
    assert RA.reconcile_enabled(True) is True


# --------------------------------------------------------------------------- #
# The agent surface                                                            #
# --------------------------------------------------------------------------- #
_AGENT_FIELDS = ("neural_moves", "heur_moves", "forced_moves", "exact_moves",
                 "n_timeouts", "solver_secs", "solver_nodes", "max_solve_secs",
                 "latched", "latch_k", "move_idx", "last_pooled_visits")
_WRAPPER_FIELDS = ("prefix_moves", "prefix_secs")


def test_stats_carries_every_field_the_harness_reads():
    game, board = _fresh()
    a = _rs(game)
    a.start_game(board)
    a.choose_action(board)
    s = a.stats()
    for f in _AGENT_FIELDS + _WRAPPER_FIELDS:
        assert f in s, f
    # The wrapper clock is COMPUTED, not copied: a non-latched decision is a
    # prefix move and its time is positive.
    assert s["prefix_moves"] == 1 and s["prefix_secs"] > 0.0
    assert s["heur_moves"] == 1 and s["move_idx"] == 1
    assert s["backend"] == "rust"
    # Attribute access mirrors FairHeuristicPriorAgent, not just the dict.
    assert a.heur_moves == 1 and a.exact_moves == 0 and a.neural_moves == 0


def test_seeded_counters_are_settable_like_the_python_agent():
    game, board = _fresh()
    a = _rs(game)
    a.start_game(board)
    a._move_idx = 40
    assert a._move_idx == 40
    a._latched = True
    a.latch_k = 2
    assert a._latched is True and a.latch_k == 2
    assert a.det_seed_base(40) == (101 * 1_000_003 + 40 * 8191) & 0x7FFFFFFF
    assert a.det_search_seed(40, 3) == a.det_seed_base(40) + 103


# --------------------------------------------------------------------------- #
# Identity vs the Python champion                                              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("deck_seed", [98_000_000_777, 98_000_000_778])
def test_adapter_matches_the_python_champion_move_for_move(deck_seed):
    """The G6 gate in miniature: same deck, every decision compared including
    the pooled (N, W) accumulators as raw f64 bits."""
    game, board = _fresh(deck_seed)
    pa = F.py_agent(game, sims=SIMS, k_dets=KDETS, seed=101)
    ra = _rs(Game(enable_legal_moves_cache=True))
    ra.start_game(board)
    import reconcile_backend as RB

    n = 0
    with F.PoolSpy() as spy:
        while n < 12 and not game.get_game_ended(board, 0):
            p = F.py_decision(pa, board, spy)
            r = RB.rs_decision(ra, board)
            assert F.compare_decision(p, r, f"ply{n}") == []
            board, _ = game.get_next_state(board, p["action"])
            ra.advance(p["action"])
            n += 1
    assert n == 12
    pa.close()


def test_thread_count_invariance_through_the_adapter():
    """The k-world merge is a sequential fold in world order, so the thread count
    is execution-only (G4 gated {1,4,8} bit-identical; this holds it at the
    adapter boundary, where the threads kwarg actually arrives)."""
    acts = {}
    for t in (1, 4):
        game, board = _fresh()
        agent = _rs(Game(enable_legal_moves_cache=True), threads=t)
        agent.start_game(board)
        seq = []
        for _ in range(8):
            a = int(agent.choose_action(board))
            seq.append(a)
            board, _ = game.get_next_state(board, a)
            agent.advance(a)
        acts[t] = seq
        game.clear_caches()
    assert acts[1] == acts[4]
