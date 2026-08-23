"""WC tie-break rule flag (BACKLOG.md 2026-08-03 "WC tie-break rule flag",
measurement/TOURNAMENT_LANDSCAPE_MEMO_20260728.md §1.4 gap #1).

Official WC rule: "in the unlikely case of a draw / tie in all games ... the
starting player always loses automatically!" Our engine's incumbent behaviour
is a symmetric draw. `wc_tiebreak` (OPT-IN, DEFAULT OFF) flips that for a tied
final score: the STARTING player (seat 0 — pinned below, `get_init_board` sets
`state.current_player = 0`) automatically loses.

Covers, python-only (the rust mirror is a separate agent's parity test):
  * flag-off byte-identity — `Game()` vs `Game(wc_tiebreak=False)` are the same
    object graph, same `get_game_ended` on a terminal corpus, and a full
    seeded game plays an IDENTICAL action sequence and final state either way;
  * armed correctness on constructed AND real tied terminals — the sign flips
    for seat 0 only, antisymmetry survives, non-tied terminals are untouched;
  * `resolve_winner`'s truth table in both modes, including "draw unreachable
    when armed";
  * `rules_profile`'s `wc_tiebreak` field — every named profile stays False,
    `walled.game_kwargs() == {}` is untouched, a hand-built armed profile
    reaches `Game.__init__` (both directly and via the env-activate path spawn
    workers rely on), and `as_manifest()` always stamps the key;
  * the exact solver's `_outcome` truth table in both modes, margin-objective
    INERTNESS (bit-identical child_values armed vs unarmed), and the K<=2
    forced-tie POSITIVE CONTROL — a pinned real seeded position where a tie is
    on the board at k_remaining<=2, proving win_value flips 0.5->0.0 armed
    while the K<=2 win/margin coincidence proposition still holds.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "src", ROOT / "engine", ROOT / "scripts" / "level2"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import endgame_solver as S  # noqa: E402
from carcassonne_ai import rules_profile as rp  # noqa: E402
from carcassonne_ai.game_wrapper import (  # noqa: E402
    Game,
    WC_TIE_VALUE,
    resolve_winner,
)
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers                                                                       #
# --------------------------------------------------------------------------- #
def _stub_terminal(score0: int, score1: int):
    """A lightweight stub board — `get_game_ended` only reads
    `.state.is_terminated()` and `.state.scores`."""
    return SimpleNamespace(state=SimpleNamespace(
        is_terminated=lambda: True, scores=[score0, score1]))


def _play_first_legal(game: Game):
    """Play `game` to a real terminal with the cheapest deterministic policy
    (always the first legal action — no `random` consumption, so two separate
    Game objects driven by this policy produce IDENTICAL trajectories with no
    seeding gymnastics). Returns (actions, final_board). Real games finish in
    well under a second this way (~150 plies)."""
    board = game.get_init_board()
    actions: list[int] = []
    while not board.state.is_terminated():
        legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
        a = legal[0]
        actions.append(a)
        board, _ = game.get_next_state(board, a)
    return actions, board


def _endgame(seed: int, k: int):
    """Roll a seeded game to the first TILES decision with k_remaining <= k
    (mirrors tests/test_e1_win_objective.py's fixture shape exactly, so a
    pinned seed here is directly comparable to that suite's fixtures)."""
    from carcassonne_ai import fair_agent

    random.seed(seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    actions = []
    while True:
        st = board.state
        if (st.phase == GamePhase.TILES
                and fair_agent.k_remaining(st) <= k):
            return game, board, actions
        legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
        a = legal[len(legal) // 2]
        actions.append(a)
        board, _ = game.get_next_state(board, a)


# --------------------------------------------------------------------------- #
# player-0-is-the-starting-player, the load-bearing assumption of this whole   #
# flag: `get_init_board` -> `CarcassonneGameState.__init__` sets               #
# `current_player = 0` unconditionally (engine/wingedsheep/carcassonne/        #
# carcassonne_game_state.py), so seat 0 IS the starting player on every        #
# `Game()`, with or without the flag (the flag never touches setup/turn        #
# order — terminal-scoring-only).                                              #
# --------------------------------------------------------------------------- #
def test_player_0_is_the_starting_player():
    board = Game().get_init_board()
    assert board.state.current_player == 0


# --------------------------------------------------------------------------- #
# TestDefaultIsOff — flag-off byte-identity                                    #
# --------------------------------------------------------------------------- #
class TestDefaultIsOff:
    def test_absent_and_explicit_false_are_the_same_object_graph(self):
        assert Game().wc_tiebreak is False
        assert Game(wc_tiebreak=False).wc_tiebreak is False
        # `CarcassonneGameState.__init__` shuffles the deck via the GLOBAL
        # `random` module (not a per-call seed), so two constructions must be
        # reseeded identically to compare boards — otherwise the two decks
        # differ trivially and the comparison proves nothing about the flag.
        random.seed(0)
        b1 = Game().get_init_board()
        random.seed(0)
        b2 = Game(wc_tiebreak=False).get_init_board()
        g_ref = Game()
        assert g_ref.string_representation(b1) == g_ref.string_representation(b2)

    @pytest.mark.parametrize("s0,s1", [(0, 0), (10, 10), (28, 28), (14, 17), (30, 5)])
    def test_get_game_ended_identical_absent_vs_explicit_false(self, s0, s1):
        g1, g2 = Game(), Game(wc_tiebreak=False)
        b = _stub_terminal(s0, s1)
        for p in (0, 1):
            assert g1.get_game_ended(b, p) == g2.get_game_ended(b, p)

    def test_full_seeded_game_identical_action_sequence_and_final_state(self):
        """The strongest form of the byte-identity claim: not just that the two
        Game objects AGREE on get_game_ended, but that an entire game driven by
        a deterministic policy produces the SAME actions and the SAME final
        state digest whether the flag is absent or explicitly False. Reseed
        the global `random` module identically before each construction (see
        the comment above) so the two decks — not just the two Game objects —
        start identical."""
        random.seed(1)
        actions1, board1 = _play_first_legal(Game())
        random.seed(1)
        actions2, board2 = _play_first_legal(Game(wc_tiebreak=False))
        assert actions1 == actions2
        assert board1.state.scores == board2.state.scores
        g_ref = Game()
        assert g_ref.string_representation(board1) == g_ref.string_representation(board2)


# --------------------------------------------------------------------------- #
# Armed correctness                                                            #
# --------------------------------------------------------------------------- #
class TestArmedCorrectness:
    @pytest.mark.parametrize("s0,s1", [(0, 0), (10, 10), (28, 28)])
    def test_armed_tie_flips_seat0_to_a_loss(self, s0, s1):
        g_off, g_on = Game(), Game(wc_tiebreak=True)
        b = _stub_terminal(s0, s1)
        # unarmed: seat 0 gets the POSITIVE epsilon (today's convention)
        assert g_off.get_game_ended(b, 0) > 0
        assert g_off.get_game_ended(b, 1) < 0
        # armed: seat 0 (the starting player) automatically LOSES the tie
        assert g_on.get_game_ended(b, 0) < 0
        assert g_on.get_game_ended(b, 1) > 0
        # magnitude is untouched — only the sign convention differs
        assert abs(abs(g_off.get_game_ended(b, 0)) - WC_TIE_VALUE) < 1e-15
        assert abs(abs(g_on.get_game_ended(b, 0)) - WC_TIE_VALUE) < 1e-15

    @pytest.mark.parametrize("s0,s1", [(0, 0), (10, 10), (28, 28)])
    def test_antisymmetry_holds_in_both_modes(self, s0, s1):
        b = _stub_terminal(s0, s1)
        for g in (Game(wc_tiebreak=False), Game(wc_tiebreak=True)):
            assert g.get_game_ended(b, 0) == -g.get_game_ended(b, 1)
            # the "tied on points" discriminator still works either way
            assert abs(g.get_game_ended(b, 0)) < 1e-4

    @pytest.mark.parametrize("s0,s1", [(15, 10), (10, 15), (36, 1)])
    def test_non_tied_terminals_are_bit_identical_armed_vs_unarmed(self, s0, s1):
        b = _stub_terminal(s0, s1)
        g_off, g_on = Game(wc_tiebreak=False), Game(wc_tiebreak=True)
        for p in (0, 1):
            assert g_off.get_game_ended(b, p) == g_on.get_game_ended(b, p)

    def test_real_terminal_state_armed_vs_unarmed(self):
        """A REAL terminal (not a stub) — deterministic first-legal-action play
        to completion, pinned at seed 36 (found by scan) which ends 28-28."""
        random.seed(36)
        actions, board = _play_first_legal(Game(enable_legal_moves_cache=True))
        assert board.state.scores == [28, 28], (
            "pinned seed 36's tied ending moved — the engine or the "
            "deterministic policy changed under this test")
        g_off, g_on = Game(wc_tiebreak=False), Game(wc_tiebreak=True)
        assert g_off.get_game_ended(board, 0) > 0 and g_off.get_game_ended(board, 1) < 0
        assert g_on.get_game_ended(board, 0) < 0 and g_on.get_game_ended(board, 1) > 0


# --------------------------------------------------------------------------- #
# resolve_winner truth table                                                    #
# --------------------------------------------------------------------------- #
class TestResolveWinner:
    def test_non_tied_scores_agree_in_both_modes(self):
        for wc in (False, True):
            assert resolve_winner(10, 5, wc_tiebreak=wc) == 0
            assert resolve_winner(5, 10, wc_tiebreak=wc) == 1

    def test_tie_unarmed_is_a_draw(self):
        assert resolve_winner(7, 7) == -1
        assert resolve_winner(7, 7, wc_tiebreak=False) == -1

    def test_tie_armed_is_unreachable_as_a_draw_seat1_wins(self):
        assert resolve_winner(7, 7, wc_tiebreak=True) == 1
        assert resolve_winner(0, 0, wc_tiebreak=True) == 1
        # draw (-1) is provably unreachable when armed
        for s in range(0, 50):
            assert resolve_winner(s, s, wc_tiebreak=True) != -1


# --------------------------------------------------------------------------- #
# rules_profile                                                                #
# --------------------------------------------------------------------------- #
class TestRulesProfile:
    def test_every_named_profile_keeps_wc_tiebreak_false(self):
        for name in rp.known():
            assert rp.resolve(name).wc_tiebreak is False, name

    def test_walled_game_kwargs_is_still_the_empty_dict(self):
        assert rp.PROFILES["walled"].game_kwargs() == {}

    def test_fixed_v1_does_not_carry_wc_tiebreak(self):
        """The Phase-B bundle does NOT cover the WC tie rule (BACKLOG: 'the
        one rules divergence fixed_v1 does not cover') — adoption into a
        future fixed_v2 is an explicitly separate decision."""
        assert rp.PROFILES["fixed_v1"].wc_tiebreak is False
        assert "wc_tiebreak" not in rp.PROFILES["fixed_v1"].game_kwargs()

    def test_a_hand_built_armed_profile_yields_the_kwarg(self):
        from dataclasses import replace

        prof = replace(rp.PROFILES["walled"], name="test_wc_armed", wc_tiebreak=True)
        assert prof.game_kwargs() == {"wc_tiebreak": True}

    def test_a_hand_built_armed_profile_reaches_game_init_directly(self):
        from dataclasses import replace

        prof = replace(rp.PROFILES["walled"], name="test_wc_armed2", wc_tiebreak=True)
        rp.PROFILES["test_wc_armed2"] = prof
        try:
            rp.activate("test_wc_armed2")
            g = Game()
            assert g.wc_tiebreak is True
        finally:
            rp.reset()
            del rp.PROFILES["test_wc_armed2"]

    def test_a_hand_built_armed_profile_reaches_game_init_via_env_activate(self):
        """Spawn workers resolve the profile from the environment, never from
        argv — this is the path they actually take (rp.active(), not
        rp.resolve() called directly)."""
        import os
        from dataclasses import replace

        prof = replace(rp.PROFILES["walled"], name="test_wc_armed3", wc_tiebreak=True)
        rp.PROFILES["test_wc_armed3"] = prof
        try:
            rp.activate("test_wc_armed3")
            # simulate a fresh interpreter that inherited the env only
            rp._cache = rp._cache_key = None
            assert os.environ[rp.ENV_VAR] == "test_wc_armed3"
            g = Game()
            assert g.wc_tiebreak is True
        finally:
            rp.reset()
            del rp.PROFILES["test_wc_armed3"]

    def test_explicit_true_always_wins_regardless_of_the_active_profile(self):
        g = Game(wc_tiebreak=True)
        assert g.wc_tiebreak is True
        from dataclasses import replace

        prof = replace(rp.PROFILES["walled"], name="test_wc_armed4", wc_tiebreak=True)
        rp.PROFILES["test_wc_armed4"] = prof
        try:
            rp.activate("test_wc_armed4")
            assert Game(wc_tiebreak=True).wc_tiebreak is True
        finally:
            rp.reset()
            del rp.PROFILES["test_wc_armed4"]

    def test_explicit_false_cannot_be_told_apart_from_unset_under_an_armed_profile(self):
        """SPEC AMBIGUITY, reported not silently guessed around: the wiring
        block's own comment claims 'an explicit kwarg always wins', but that is
        only true for the `start_row`/`start_col` fields, which use a `None`
        sentinel to distinguish 'caller said nothing' from 'caller said 0'.
        `wc_tiebreak` is wired in the SAME STYLE as its neighbours
        `cloister_scan_fix` (`if not cloister_scan_fix and _prof_kw.get(...)`)
        and `fixed_start_tile` — plain bools defaulting False, with no sentinel
        to distinguish "caller didn't say" from "caller explicitly said False".
        So `Game(wc_tiebreak=False)` under an armed profile is
        INDISTINGUISHABLE from `Game()` and the profile wins — reproduced here
        for `cloister_scan_fix` as the existing-behaviour control, so this is
        pinned as a documented shared property, not a `wc_tiebreak`-only bug."""
        from dataclasses import replace

        prof = replace(rp.PROFILES["walled"], name="test_wc_armed5", wc_tiebreak=True)
        rp.PROFILES["test_wc_armed5"] = prof
        try:
            rp.activate("test_wc_armed5")
            assert Game(wc_tiebreak=False).wc_tiebreak is True

            # the identical property already holds for cloister_scan_fix today
            # (unrelated to this flag) — control proving this is not new
            prof2 = replace(rp.PROFILES["walled"], name="test_cloister_armed",
                            cloister_scan="fixed")
            rp.PROFILES["test_cloister_armed"] = prof2
            rp.activate("test_cloister_armed")
            assert Game(cloister_scan_fix=False).cloister_scan_fix is True
        finally:
            rp.reset()
            del rp.PROFILES["test_wc_armed5"]
            rp.PROFILES.pop("test_cloister_armed", None)

    def test_as_manifest_always_stamps_the_key(self):
        for name in rp.known():
            man = rp.resolve(name).as_manifest()
            assert "wc_tiebreak" in man
            assert man["wc_tiebreak"] is False
        from dataclasses import replace

        prof = replace(rp.PROFILES["walled"], name="test_wc_manifest", wc_tiebreak=True)
        assert prof.as_manifest()["wc_tiebreak"] is True

    def test_resolve_does_not_raise_on_an_armed_profile(self):
        """The flag IS honourable end-to-end in python, unlike the still-unbuilt
        W3 board-size lever — resolving an armed profile must not raise."""
        from dataclasses import replace

        prof = replace(rp.PROFILES["walled"], name="test_wc_resolve_ok", wc_tiebreak=True)
        rp.PROFILES["test_wc_resolve_ok"] = prof
        try:
            got = rp.resolve("test_wc_resolve_ok")
            assert got.wc_tiebreak is True
        finally:
            del rp.PROFILES["test_wc_resolve_ok"]


# --------------------------------------------------------------------------- #
# Solver: _outcome truth table + margin-objective inertness                    #
# --------------------------------------------------------------------------- #
class TestSolverOutcome:
    def test_outcome_truth_table_unarmed(self):
        assert S._outcome(3.0) == 1.0
        assert S._outcome(0.0) == 0.5
        assert S._outcome(-2.0) == 0.0

    def test_outcome_truth_table_armed(self):
        assert S._outcome(3.0, wc_tiebreak=True) == 1.0
        assert S._outcome(0.0, wc_tiebreak=True) == 0.0    # the whole point
        assert S._outcome(-2.0, wc_tiebreak=True) == 0.0

    def test_outcome_default_kwarg_matches_explicit_false(self):
        for m in (-5.0, -1.0, 0.0, 1.0, 5.0):
            assert S._outcome(m) == S._outcome(m, wc_tiebreak=False)

    def test_solve_result_stamps_wc_tiebreak(self):
        game, board, _ = _endgame(11, 2)
        r_off = S.solve(game, board, mode="marginalized")
        r_on = S.solve(game, board, mode="marginalized", wc_tiebreak=True)
        assert r_off.wc_tiebreak is False
        assert r_on.wc_tiebreak is True

    def test_margin_objective_is_inert_under_wc_tiebreak(self):
        """The core inertness claim: objective='margin' never calls _outcome,
        so an armed-but-margin solve is BIT-IDENTICAL to the unarmed one on
        every field _outcome could possibly influence."""
        game, board, _ = _endgame(11, 2)
        r_off = S.solve(game, board, mode="marginalized", objective="margin",
                        wc_tiebreak=False)
        r_on = S.solve(game, board, mode="marginalized", objective="margin",
                       wc_tiebreak=True)
        assert r_off.value == r_on.value
        assert r_off.child_values == r_on.child_values
        assert r_off.optimal_actions == r_on.optimal_actions
        assert r_off.win_value is None and r_on.win_value is None
        assert r_off.child_win_values is None and r_on.child_win_values is None
        # only the visibility field differs
        assert r_off.wc_tiebreak is False and r_on.wc_tiebreak is True

    def test_wc_tiebreak_does_not_raise_under_margin_objective(self):
        """Unlike E1's clairvoyant+win refusal, armed-but-inert is legitimate
        and must not raise — it can arrive from a process-wide rules profile
        while this leg runs the margin objective."""
        game, board, _ = _endgame(11, 2)
        S.solve(game, board, mode="marginalized", objective="margin", wc_tiebreak=True)
        S.solve(game, board, mode="clairvoyant", objective="margin", wc_tiebreak=True)


# --------------------------------------------------------------------------- #
# K<=2 forced-tie POSITIVE CONTROL                                              #
# --------------------------------------------------------------------------- #
# Found by a bounded seed scan (deck_seed 0..12, ~113s wall-clock — the K<=2
# python solve costs ~4-17s/seed with the DESIGN §2 fixture's "middle legal
# action" replay policy; the >200-seed / <2min combination in the brief is not
# jointly achievable at this per-seed cost, so the scan was time-boxed to
# ~100s instead and reported honestly here rather than silently narrowed).
# deck_seed=4 (the same `_endgame(seed, k)` shape as
# tests/test_e1_win_objective.py) reaches k_remaining==2 after exactly the
# 140 actions below, and root child action 953 is an exact margin tie
# (child_values[953] == 0.0) that is NOT itself in the optimal set (the true
# optimum is a clean win, margin 1.0) — i.e. a real, on-the-board tied line
# whose win_value the flag is free to move without disturbing which move is
# actually best.
_WC_K2_SEED = 4
_WC_K2_ACTIONS = [
    1248, 2506, 1350, 2504, 1346, 2509, 1255, 2508, 1347, 2504, 1051, 2504,
    1154, 2503, 1341, 2510, 1348, 2510, 1157, 2504, 1448, 2506, 1336, 2506,
    1258, 2507, 1238, 2506, 1234, 2504, 1363, 2508, 1260, 2510, 1440, 2510,
    1264, 2510, 1269, 2510, 1368, 2510, 1164, 2510, 1356, 2510, 1450, 2510,
    1224, 2510, 1136, 2510, 1224, 2510, 1328, 2510, 1429, 2510, 1432, 2510,
    1275, 2510, 1326, 2510, 1469, 2507, 1170, 2510, 1242, 2510, 1456, 2510,
    1530, 2510, 1460, 2510, 1327, 2510, 1320, 2510, 1316, 2510, 1421, 2510,
    1416, 2510, 1035, 2510, 1045, 2510, 1444, 2510, 1429, 2510, 1371, 2510,
    1028, 2510, 1450, 2510, 1024, 2510, 1221, 2510, 1182, 2510, 1187, 2510,
    1189, 2510, 1285, 2510, 1442, 2510, 1085, 2510, 1455, 2510, 1194, 2510,
    1411, 2510, 1219, 2510, 1279, 2510, 1472, 2510, 1294, 2510, 1388, 2510,
    1308, 2510, 1462, 2510, 1472, 2510, 1404, 2510,
]
_WC_K2_TIED_ACTION = 953


def _wc_k2_fixture():
    """Replays the pinned control from scratch (no cross-test state)."""
    random.seed(_WC_K2_SEED)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    for a in _WC_K2_ACTIONS:
        board, _ = game.get_next_state(board, a)
    from carcassonne_ai import fair_agent

    assert board.state.phase == GamePhase.TILES
    assert fair_agent.k_remaining(board.state) == 2, (
        "pinned control seed 4's k_remaining moved off 2 — engine or replay "
        "policy changed under this fixture")
    return game, board


class TestK2ForcedTiePositiveControl:
    def test_the_pinned_tied_line_exists_and_is_not_the_optimum(self):
        game, board = _wc_k2_fixture()
        r = S.solve(game, board, mode="marginalized", objective="margin")
        assert r.child_values[_WC_K2_TIED_ACTION] == 0.0
        assert _WC_K2_TIED_ACTION not in r.optimal_actions
        assert r.value == 1.0    # the true optimum is a clean win, unaffected

    def test_unarmed_win_value_is_a_draw_on_the_tied_line(self):
        game, board = _wc_k2_fixture()
        r = S.solve(game, board, mode="marginalized", objective="win")
        assert r.child_win_values[_WC_K2_TIED_ACTION] == 0.5
        assert r.child_values[_WC_K2_TIED_ACTION] == 0.0   # margin component unchanged

    def test_armed_win_value_flips_the_tied_line_to_a_loss(self):
        game, board = _wc_k2_fixture()
        r = S.solve(game, board, mode="marginalized", objective="win", wc_tiebreak=True)
        assert r.child_win_values[_WC_K2_TIED_ACTION] == 0.0   # the whole point
        assert r.child_values[_WC_K2_TIED_ACTION] == 0.0       # margin untouched
        assert r.wc_tiebreak is True

    def test_k2_coincidence_proposition_survives_armed(self):
        """DESIGN §2 (unarmed) SURVIVES the flag: `_outcome(m, wc_tiebreak=True)`
        is still monotone non-decreasing in `m` (0.0 for m<=0, 1.0 for m>0),
        and at K<=2 every chance bag is a singleton (deterministic minimax), so
        lexicographic (w, m) max still equals plain margin max — same optimal
        SET — whether or not the flag is armed."""
        game, board = _wc_k2_fixture()
        m_off = S.solve(game, board, mode="marginalized", objective="margin")
        w_off = S.solve(game, board, mode="marginalized", objective="win")
        m_on = S.solve(game, board, mode="marginalized", objective="margin",
                       wc_tiebreak=True)
        w_on = S.solve(game, board, mode="marginalized", objective="win",
                       wc_tiebreak=True)
        # unarmed coincidence (the original DESIGN §2 proposition)
        assert set(m_off.optimal_actions) == set(w_off.optimal_actions)
        # margin objective is inert to the flag (bit-identical either way)
        assert m_off.value == m_on.value
        assert m_off.child_values == m_on.child_values
        assert m_off.optimal_actions == m_on.optimal_actions
        # armed coincidence: STILL holds
        assert set(m_on.optimal_actions) == set(w_on.optimal_actions)
        # and win-mode's optimal SET is unaffected here (the pinned tied line
        # was never in it — only its own win_value moved, checked above)
        assert set(w_off.optimal_actions) == set(w_on.optimal_actions)
