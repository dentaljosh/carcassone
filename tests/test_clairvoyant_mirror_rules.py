"""F9-A0 hole: the CLAIRVOYANT Rust mirrors must run the ACTIVE rules profile.

Discovered 2026-08-03 while building the caps/curve re-sweep under `fixed_v1`.
`--rules-profile` reached `game_wrapper.Game` (via `rules_profile.active()`) and
reached `RustFairAgent` (via `champion_factory`'s explicit geometry forwarding),
but the two clairvoyant adapters — the ones `eval_puct_priors --backend rust`
builds for BOTH sides — seated their mirrors with a bare
`MirrorState.from_deck(descs)`, i.e. always on the engine of record.

Measured before the fix, under `fixed_v1`:

    PY : (((18, 15, 'city_top_straight_road', ...),), ...)   # retail tile placed
    RS : ((), ...)                                            # empty engine6 board

and `_check_sync` is gated on `CARC_RS_RECONCILE` (default OFF), so a
`--backend rust --rules-profile fixed_v1` eval would have graded two agents
reading a different game from the referee, silently, on both sides.

What is asserted here:

  * **`walled` is untouched** — `mirror_geometry_kwargs` returns `{}` for the
    engine of record, so the FFI call is byte-identical to the pre-fix one. This
    is the default-off contract the whole rules_profile module rests on.
  * **`fixed_v1` reaches the mirror** — all four levers, and the mirror's own
    `start_rule()` read-back agrees.
  * **A full-game lockstep** under each profile: the referee applies actions, the
    mirror advances, and every ply's digest matches. This is what would have
    failed before the fix, and it covers the levers (`cloister_scan_fix`,
    `draw_rule`) that have no ply-0 board tell.
  * **The ply-0 check is UNCONDITIONAL** — a mirror built on the wrong geometry
    raises at `start_game` even with reconcile off, so the silent class is closed
    structurally rather than by remembering an env var.
"""
from __future__ import annotations

import random

import pytest

carc_rs = pytest.importorskip("carc_rs")

from carcassonne_ai import rules_profile as rp  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig  # noqa: E402
from carcassonne_ai.rust_agent import (  # noqa: E402
    MirrorDesync,
    RustCarryClairvoyantAgent,
    RustClairvoyantAgent,
    mirror_geometry_kwargs,
)
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

# Tiny budget: this fixture proves the mirror's RULES, not the search's strength.
SIMS = 24


@pytest.fixture(autouse=True)
def _clean_profile():
    rp.reset()
    yield
    rp.reset()


def _cfg(**kw):
    return HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, leaf_quantize="float",
                                final_select="visits", leaf_cfg=DEFAULT_CONFIG, **kw)


def _lockstep(agent, game, board, plies: int) -> int:
    """Referee applies, mirror advances, every ply digest-checked. Returns plies."""
    n = 0
    for _ in range(plies):
        if game.get_game_ended(board, 0):
            break
        action = agent.move(board)
        board = game.get_next_state(board, action)[0]
        agent.advance(action, board_after=board)   # reconcile-gated...
        agent.check_sync(board, f"ply {n}")        # ...so assert unconditionally
        n += 1
    return n


# --------------------------------------------------------------------------- #
# The default-off contract                                                     #
# --------------------------------------------------------------------------- #
def test_walled_adds_no_mirror_geometry():
    """The engine of record must add NO kwarg — that is what keeps it identical."""
    rp.activate("walled")
    assert mirror_geometry_kwargs(Game()) == {}


def test_no_profile_is_walled():
    assert mirror_geometry_kwargs(Game()) == {}


def test_explicit_game_kwargs_are_honoured_without_a_profile():
    """Geometry is read off the GAME, not the profile — an explicitly built
    Game(draw_rule=...) must reach the mirror too."""
    g = Game(draw_rule="redraw", cloister_scan_fix=True)
    assert mirror_geometry_kwargs(g) == {"cloister_scan_fix": True,
                                         "draw_rule": "redraw"}


def test_fixed_v1_carries_all_four_levers_to_the_mirror():
    rp.activate("fixed_v1")
    assert mirror_geometry_kwargs(Game()) == {
        "start_row": 18, "start_col": 15,
        "start_rule": "retail",
        "cloister_scan_fix": True,
        "draw_rule": "redraw",
    }


# --------------------------------------------------------------------------- #
# End to end, per adapter                                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("profile", ["walled", "fixed_v1"])
@pytest.mark.parametrize("cls", [RustClairvoyantAgent, RustCarryClairvoyantAgent])
def test_mirror_stays_in_lockstep_under_profile(profile, cls):
    rp.activate(profile)
    game = Game(enable_legal_moves_cache=True)
    random.seed(20260803)
    board = game.get_init_board()
    agent = cls(game, _cfg(), simulations=SIMS, seed=0)
    agent.start_game(board)              # unconditional ply-0 digest check inside
    assert _lockstep(agent, game, board, plies=10) == 10


def test_fixed_v1_mirror_reports_retail_start_rule():
    rp.activate("fixed_v1")
    game = Game(enable_legal_moves_cache=True)
    random.seed(7)
    board = game.get_init_board()
    agent = RustClairvoyantAgent(game, _cfg(), simulations=SIMS, seed=0)
    agent.start_game(board)
    assert agent._ms.start_rule() == "retail"


def test_walled_mirror_reports_engine_start_rule():
    rp.activate("walled")
    game = Game(enable_legal_moves_cache=True)
    random.seed(7)
    board = game.get_init_board()
    agent = RustClairvoyantAgent(game, _cfg(), simulations=SIMS, seed=0)
    agent.start_game(board)
    assert agent._ms.start_rule() == "engine"


# --------------------------------------------------------------------------- #
# The silent class is closed structurally                                      #
# --------------------------------------------------------------------------- #
def test_ply0_check_is_unconditional_with_reconcile_off(monkeypatch):
    """A mirror seated on the WRONG rules must raise at start_game even with
    CARC_RS_RECONCILE unset — this is the exact pre-fix failure mode."""
    monkeypatch.delenv("CARC_RS_RECONCILE", raising=False)
    rp.activate("fixed_v1")
    game = Game(enable_legal_moves_cache=True)
    random.seed(11)
    board = game.get_init_board()
    agent = RustClairvoyantAgent(game, _cfg(), simulations=SIMS, seed=0)
    assert agent._reconcile is False           # per-ply checking really is off
    agent._geom = {}                           # simulate the pre-fix construction
    agent._mirror_preplaces = False
    with pytest.raises((MirrorDesync, RuntimeError)):
        agent.start_game(board)


def test_window_size_may_not_contradict_the_game():
    """`window_size` used to be stored and never passed to the FFI. Now that it
    is live, a caller's value silently losing to the Game's would be a second
    silent class — so a contradiction raises."""
    rp.activate("walled")
    game = Game(enable_legal_moves_cache=True)      # window 25
    with pytest.raises(ValueError, match="contradicts"):
        RustClairvoyantAgent(game, _cfg(), simulations=SIMS, window_size=13)
    with pytest.raises(ValueError, match="contradicts"):
        RustCarryClairvoyantAgent(game, _cfg(), simulations=SIMS, window_size=13)
    # ...and the agreeing case is accepted.
    assert RustClairvoyantAgent(game, _cfg(), simulations=SIMS,
                                window_size=25)._window_size == 25


def test_retail_board_with_engine_mirror_refuses_loudly():
    """`_draw_order_for_mirror`'s refusal is reachable from this adapter: a board
    with a pre-placed start tile and an engine-rule mirror must not run."""
    rp.activate("fixed_v1")
    game = Game(enable_legal_moves_cache=True)
    random.seed(3)
    board = game.get_init_board()
    agent = RustClairvoyantAgent(game, _cfg(), simulations=SIMS, seed=0)
    agent._mirror_preplaces = False
    with pytest.raises(RuntimeError, match="start_rule='engine'"):
        agent.start_game(board)
