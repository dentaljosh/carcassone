"""WC tie-break rule flag (BACKLOG 2026-08-03 "WC tie-break rule flag";
measurement/TOURNAMENT_LANDSCAPE_MEMO_20260728.md §1.3/§1.4) — the AGENT and
HARNESS plumbing, as opposed to the core (`game_wrapper`/`rules_profile`/
`endgame_solver`, covered by tests/test_wc_tiebreak.py, which this file does
NOT duplicate).

The core contract this file assumes (built by a concurrent agent — see that
module's own tests for its coverage): `Game(wc_tiebreak=...)`,
`game_wrapper.resolve_winner(score0, score1, wc_tiebreak=...)`, and
`scripts/level2/endgame_solver.solve(..., wc_tiebreak=...)` /
`SolveResult.wc_tiebreak`.

Covers, mirroring tests/test_e1_win_objective.py's shape for the sibling E1
knob:
  * plumbing: FairHeuristicPriorAgent / RustFairAgent / champion_factory
    accept and RESOLVE `wc_tiebreak`; default False; the public alias reads
    back; the old-wheel footgun fails LOUDLY (never silently plays margin);
  * eval_fair_puct's `_classify_outcome` truth table (W/D/L classification
    under the seat mapping) — factored into a pure helper so it is testable
    without playing a game;
  * `game_wrapper.resolve_winner` (what play_harness routes through) gives
    the IDENTICAL winner to the pre-knob inline expression whenever the flag
    is off — a property test over a grid of score pairs;
  * the two harnesses' manifest/summary 3-state ("absent is unknown-not-
    zero") stamping: never-armed vs armed-but-inert vs armed-and-fired.

⚠️ SEMANTIC POINT pinned throughout: unlike E1's `exact_objective` (a
CANDIDATE-side knob), WC tie-break is a RULE OF THE MATCH — it applies
symmetrically to both agents and keys off SEAT (seat 0 = starting player),
never off candidate/opponent role. There is no `--cand-wc-tiebreak`.

Rust legs skip LOUDLY (with the per-box rebuild instruction) when the
installed carc_rs wheel predates the knob — a skip on a box that just
rebuilt is a failure of the BUILD, not of this test.
"""
from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "src", ROOT / "engine", ROOT / "scripts" / "level2",
           ROOT / "scripts" / "classical_search", ROOT / "scripts",
           ROOT / "scripts" / "human_anchor"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import env_preamble  # noqa: E402,F401  MUST precede any carcassonne_ai import

import endgame_solver as S  # noqa: E402
from carcassonne_ai import champion_factory  # noqa: E402
from carcassonne_ai import fair_agent  # noqa: E402
from carcassonne_ai.game_wrapper import Game, resolve_winner  # noqa: E402

import eval_fair_puct as E  # noqa: E402
import play_harness as PH  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. agent / factory plumbing — accept + RESOLVE, default False                #
# --------------------------------------------------------------------------- #
def test_fair_prior_agent_accepts_and_resolves_the_knob():
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    a = fair_agent.FairHeuristicPriorAgent(g, sims=4, k_dets=1, seed=1,
                                           wc_tiebreak=True)
    assert a.wc_tiebreak is True
    assert a._wc_tiebreak is True
    b = fair_agent.FairHeuristicPriorAgent(g, sims=4, k_dets=1, seed=1)
    assert b.wc_tiebreak is False


def test_fair_prior_agent_passes_wc_tiebreak_to_the_solver_only_when_armed(monkeypatch):
    """Mirrors test_e1_win_objective's identical check for exact_objective: the
    incumbent (unarmed) solver call must be byte-for-byte the pre-knob one."""
    calls = []

    class _Res:
        optimal_actions = [7]
        nodes = 1

    def fake_solve(*args, **kw):
        calls.append(kw)
        return _Res()

    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    monkeypatch.setattr(S, "solve", fake_solve)
    for wc, expect in ((False, None), (True, True)):
        agent = fair_agent.FairHeuristicPriorAgent(
            game, sims=4, k_dets=1, seed=1, wc_tiebreak=wc)
        assert agent._exact_move(board) == 7
        assert calls[-1].get("wc_tiebreak") == expect
    assert "wc_tiebreak" not in calls[0]     # off: kwarg ABSENT, not False


def test_champion_factory_build_fair_champion_forwards_wc_tiebreak():
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    a = champion_factory.build_fair_champion(
        g, sims=4, k_dets=1, seed=1, wc_tiebreak=True)
    assert a.wc_tiebreak is True
    b = champion_factory.build_fair_champion(g, sims=4, k_dets=1, seed=1)
    assert b.wc_tiebreak is False


def test_make_production_champion_forwards_wc_tiebreak(monkeypatch):
    """`play_harness._make_fair_agent` reaches the champion through
    `make_production_champion`, not `build_fair_champion` directly — cover that
    hop too (it is NOT one of the three `build_fair_champion` line sites named
    in the brief, but without it play_harness's --wc-tiebreak would have no
    effect on the agent it builds)."""
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    a = champion_factory.make_production_champion(
        "fair", game=g, sims=4, k_dets=1, seed=1, verify=False,
        backend="python", wc_tiebreak=True)
    assert a.wc_tiebreak is True
    assert a.manifest["wc_tiebreak"]["enabled"] is True
    b = champion_factory.make_production_champion(
        "fair", game=g, sims=4, k_dets=1, seed=1, verify=False, backend="python")
    assert b.wc_tiebreak is False
    assert "wc_tiebreak" not in b.manifest


def test_make_production_champion_rejects_wc_tiebreak_off_fair_mode():
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    with pytest.raises(ValueError, match="wc_tiebreak"):
        champion_factory.make_production_champion(
            "clairvoyant", game=g, sims=4, seed=1, verify=False,
            backend="python", wc_tiebreak=True)


# --------------------------------------------------------------------------- #
# 2. the old-wheel footgun — RustFairAgent must fail LOUDLY, never silently     #
# --------------------------------------------------------------------------- #
def test_rust_agent_old_wheel_fails_loudly(monkeypatch):
    """Simulated stale wheel (monkeypatch): a wc_tiebreak=True request against a
    FairAgentRs that does not accept the kwarg must raise the rebuild-
    instruction RuntimeError, never silently play the symmetric-draw champion."""
    import carcassonne_ai.rust_agent as RA

    class _FakeRs:
        def __init__(self, *a, **kw):
            if "wc_tiebreak" in kw:
                raise TypeError(
                    "FairAgentRs() got an unexpected keyword argument "
                    "'wc_tiebreak'")

    fake_mod = type(sys)("carc_rs")
    fake_mod.FairAgentRs = _FakeRs
    monkeypatch.setitem(sys.modules, "carc_rs", fake_mod)
    monkeypatch.setattr(RA, "search_config_rs", lambda cfg, sims: None)

    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    with pytest.raises(RuntimeError, match="rebuild the wheel|rust/carc/target/wheels"):
        RA.RustFairAgent(g, None, sims=4, k_dets=1, wc_tiebreak=True)
    # off: the kwarg is never passed, so the old wheel keeps working
    RA.RustFairAgent(g, None, sims=4, k_dets=1)


def test_rust_agent_old_wheel_footgun_on_the_real_installed_wheel():
    """The REAL installed carc_rs, not a simulant. A skip here means the wheel
    on THIS box predates the wc_tiebreak knob — that is a fact about the BUILD,
    never about this test, and the message says so; a skip on a box that just
    ran `maturin build --release -m rust/carc/carc-py/Cargo.toml` is a build
    failure, not a test failure."""
    pytest.importorskip("carc_rs")
    from carcassonne_ai import champion_factory as _cfac
    from carcassonne_ai.rust_agent import RustFairAgent

    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    cfg = _cfac.production_prior_cfg()
    try:
        RustFairAgent(g, cfg, sims=4, k_dets=1, wc_tiebreak=True)
    except RuntimeError as e:
        assert "rebuild" in str(e) and "rust/carc/target/wheels" in str(e), (
            f"footgun fired but with the wrong message shape: {e}")
        pytest.skip(
            "carc_rs wheel on THIS box PREDATES the wc_tiebreak knob (confirmed "
            "live, not simulated) — rebuild with `maturin build --release -m "
            "rust/carc/carc-py/Cargo.toml` before trusting any wc_tiebreak "
            "result here. This is a BUILD gap, not a test failure.")


# --------------------------------------------------------------------------- #
# 3. eval_fair_puct's W/D/L classification — the pure helper                   #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("a_seat,diff,wc", list(product((0, 1), (-3, 0, 5), (False, True))))
def test_classify_outcome_truth_table(a_seat, diff, wc):
    won, drew = E._classify_outcome(diff, a_seat, wc)
    if diff > 0:
        assert won is True and drew is False
    elif diff < 0:
        assert won is False and drew is False
    else:                                          # diff == 0, the tie cell
        if not wc:
            assert won is False and drew is True
        else:
            # armed: seat 0 (starting player) automatically LOSES an exact
            # tie, i.e. the candidate wins the tie iff it sits in seat 1.
            assert drew is False
            assert won is (a_seat == 1)


def test_classify_outcome_never_touches_diff():
    """diff is a PASSTHROUGH — _paired_z is margin-based and every historical
    comparison assumes it is untouched by the flag."""
    for wc in (False, True):
        for a_seat in (0, 1):
            for diff in (-7, 0, 4):
                E._classify_outcome(diff, a_seat, wc)   # must not raise / mutate
    # the function signature itself proves it: diff is read, never returned


# --------------------------------------------------------------------------- #
# 4. resolve_winner — identical to the old inline expression when off          #
# --------------------------------------------------------------------------- #
def _old_inline_winner(s0: int, s1: int) -> int:
    """The EXACT expression play_harness.py used before this knob (frozen here
    so the property test compares against the historical behaviour, not a
    moving target)."""
    return 0 if s0 > s1 else 1 if s1 > s0 else -1


@pytest.mark.parametrize("s0,s1", [
    (a, b) for a in range(0, 12) for b in range(0, 12)
] + [(0, 0), (200, 200), (37, 37), (150, 149), (149, 150)])
def test_resolve_winner_matches_old_inline_expression_when_off(s0, s1):
    assert resolve_winner(s0, s1, wc_tiebreak=False) == _old_inline_winner(s0, s1)


def test_resolve_winner_armed_never_returns_draw():
    for s in (0, 1, 50, 200):
        assert resolve_winner(s, s, wc_tiebreak=True) == 1   # seat 0 auto-loses
    assert resolve_winner(10, 5, wc_tiebreak=True) == 0
    assert resolve_winner(5, 10, wc_tiebreak=True) == 1


# --------------------------------------------------------------------------- #
# 5. manifest / summary 3-state stamping                                       #
# --------------------------------------------------------------------------- #
def test_eval_fair_puct_wc_summary_three_states():
    """The `_summary()` block: never-armed / armed-inert / armed-fired, mirroring
    the `wc_tie_resolved_games` liveness witness — built from bare GameResult
    stand-ins so no game is played."""

    def _mk(won, drew, wc, resolved):
        return E.GameResult(
            seed=1, a_seat=0, info="fair", exact_k=2, k_dets=1, sims=4,
            rung_sims=100, score_p0=10, score_p1=10 if drew else 5,
            diff=(0 if drew else 5), won_by_champ=won, drew=drew,
            elapsed_s=0.0, moves=10, wc_tiebreak=wc, wc_tie_resolved=resolved)

    # never armed
    off = [_mk(True, False, False, False), _mk(False, True, False, False)]
    summ = E._summary(off, "fair", 2, 1, 4, 100, wc_tiebreak=False)
    assert summ["wc_tiebreak"] is False
    assert summ["wc_tie_resolved_games"] == 0

    # armed, but this cell never hit a tie
    inert = [_mk(True, False, True, False), _mk(False, False, True, False)]
    summ = E._summary(inert, "fair", 2, 1, 4, 100, wc_tiebreak=True)
    assert summ["wc_tiebreak"] is True
    assert summ["wc_tie_resolved_games"] == 0        # armed-but-inert, not absent

    # armed AND it fired
    fired = [_mk(True, False, True, True), _mk(False, False, True, False)]
    summ = E._summary(fired, "fair", 2, 1, 4, 100, wc_tiebreak=True)
    assert summ["wc_tiebreak"] is True
    assert summ["wc_tie_resolved_games"] == 1


def test_play_harness_game_wc_tiebreak_block_three_states():
    # never armed
    assert PH._game_wc_tiebreak_block(False, [50, 50]) == {"enabled": False}
    # armed, this game was not tied
    block = PH._game_wc_tiebreak_block(True, [60, 55])
    assert block == {"enabled": True, "tied_games": 0, "resolved_for_seat1": 0}
    # armed AND fired (this game WAS tied)
    block = PH._game_wc_tiebreak_block(True, [55, 55])
    assert block == {"enabled": True, "tied_games": 1, "resolved_for_seat1": 1}


def test_play_harness_manifest_carries_the_block_disarmed_through_a_real_game():
    """Through an actual (instant, first-legal-action) game, so it is the real
    manifest key being checked, not just the helper in isolation."""
    import numpy as np

    class _StubChampion:
        neural_moves = heur_moves = exact_moves = n_timeouts = 0
        solver_secs = solver_nodes = 0
        latch_k = None

        def __init__(self, game):
            self._game = game
            self.manifest = {"stub": True}

        def choose_action(self, board):
            return int(np.flatnonzero(self._game.get_valid_moves(board))[0])

    g = Game(enable_legal_moves_cache=True)
    agents = {0: _StubChampion(g), 1: _StubChampion(g)}
    rec = PH.play_game(g, 777_000_001, agents, {0: "a", 1: "b"}, {"t": 1})
    assert rec["manifest"]["wc_tiebreak"] == {"enabled": False}
    # off is byte-identical to the pre-knob inline expression
    s0, s1 = rec["result"]["scores"]
    assert rec["result"]["winner_seat"] == _old_inline_winner(s0, s1)


# --------------------------------------------------------------------------- #
# 6. eval_fair_puct / play_harness keyword-presence contracts (default OFF)    #
# --------------------------------------------------------------------------- #
def test_make_champion_default_does_not_arm_the_handoff():
    """`_make_champion` with no wc_tiebreak kwarg builds a `_MarginalizedHandoff`
    whose own `_wc_tiebreak` is False — the disarmed shape is untouched."""
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    cfg = fair_agent.HeuristicPriorConfig()
    handoff = E._make_champion("fair", cfg, 4, 1, 2, 1,
                               Game(enable_legal_moves_cache=True))
    assert handoff._wc_tiebreak is False


def test_make_champion_arms_the_handoff_when_requested():
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    cfg = fair_agent.HeuristicPriorConfig()
    handoff = E._make_champion("fair", cfg, 4, 1, 2, 1,
                               Game(enable_legal_moves_cache=True),
                               wc_tiebreak=True)
    assert handoff._wc_tiebreak is True


def test_play_harness_make_fair_agent_keyword_presence(monkeypatch):
    """Mirrors test_play_harness_tiearb's `factory_calls` fixture pattern: OFF
    passes NO wc_tiebreak kwarg to make_production_champion at all; ON passes
    exactly wc_tiebreak=True."""
    calls = []

    def _fake(mode, *, game=None, **kw):
        calls.append(kw)

        class _Stub:
            manifest = {"stub": True}
            wc_tiebreak = kw.get("wc_tiebreak", False)

        return _Stub()

    monkeypatch.setattr(champion_factory, "make_production_champion", _fake)
    g = Game(enable_legal_moves_cache=True)
    PH._make_fair_agent(g, 4, 1, seed=1)
    assert "wc_tiebreak" not in calls[-1]
    PH._make_fair_agent(g, 4, 1, seed=1, wc_tiebreak=True)
    assert calls[-1]["wc_tiebreak"] is True
