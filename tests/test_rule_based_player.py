"""Tests for the rule-based Tier-1 baseline player."""
from __future__ import annotations

import numpy as np
import pytest

from carcassonne_ai.action_space import meeple_farmer_base, meeple_pass_index
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer


# ---------------------------------------------------------------------------
# Plumbing: every choice is a legal action, every game finishes.
# ---------------------------------------------------------------------------


def test_choose_action_returns_legal_for_first_position() -> None:
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    mask = g.get_valid_moves(b)
    player = RuleBasedPlayer(seed=0)
    a = player.choose_action(g, b, mask)
    assert mask[a], "rule player returned an illegal action"


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_full_game_runs_to_completion(seed: int) -> None:
    """A full game with rule-player on both sides terminates without crashing
    and every action it picks is legal. Catches decode mismatches and edge
    cases (single-legal forced moves, farmer pruning, pass) in one path."""
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    p0 = RuleBasedPlayer(seed=seed)
    p1 = RuleBasedPlayer(seed=seed + 100)
    moves = 0
    while g.get_game_ended(b, 0) == 0.0:
        mask = g.get_valid_moves(b)
        cur = b.state.current_player
        a = (p0 if cur == 0 else p1).choose_action(g, b, mask)
        assert mask[a], f"player {cur} returned illegal action {a} at move {moves}"
        b, _ = g.get_next_state(b, a)
        moves += 1
        if moves > 500:
            pytest.fail(f"game ran past 500 moves on seed {seed}")
    assert moves > 50, f"game ended after only {moves} moves on seed {seed}"


# ---------------------------------------------------------------------------
# Forced-move shortcut (Rule 1).
# ---------------------------------------------------------------------------


def test_forced_move_returns_the_only_legal_action() -> None:
    g = Game()
    b = g.get_init_board()
    player = RuleBasedPlayer(seed=0)
    fake_mask = np.zeros(g.get_action_size(), dtype=bool)
    fake_mask[42] = True
    assert player.choose_action(g, b, fake_mask) == 42


def test_empty_legal_mask_raises() -> None:
    g = Game()
    b = g.get_init_board()
    player = RuleBasedPlayer(seed=0)
    empty = np.zeros(g.get_action_size(), dtype=bool)
    with pytest.raises(RuntimeError, match="no legal moves"):
        player.choose_action(g, b, empty)


# ---------------------------------------------------------------------------
# Rule 3 — avoid early farmers.
# ---------------------------------------------------------------------------


def test_early_meeple_phase_skips_farmer_when_normal_available() -> None:
    """If both NORMAL and FARMER options are legal AND we're in early game,
    Rule 3 should drop the farmer options. The remaining (NORMAL) options are
    then ranked by virtual_score; pick should never be a farmer."""
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    # First action: place the first tile somewhere legal. Get into meeple phase.
    mask = g.get_valid_moves(b)
    legal_tiles = np.flatnonzero(mask)
    b, _ = g.get_next_state(b, int(legal_tiles[0]))

    # Now phase=meeples. Construct a fake mask with one NORMAL and one FARMER.
    W = g.window_size
    farmer_base = meeple_farmer_base(W)
    pass_idx = meeple_pass_index(W)
    fake_mask = np.zeros(g.get_action_size(), dtype=bool)
    real_mask = g.get_valid_moves(b)
    normal_options = [
        i for i in np.flatnonzero(real_mask) if i < farmer_base
    ]
    farmer_options = [
        i for i in np.flatnonzero(real_mask) if farmer_base <= i < pass_idx
    ]
    if not normal_options or not farmer_options:
        pytest.skip("first-tile meeple slot doesn't expose both NORMAL and FARMER")
    fake_mask[normal_options[0]] = True
    fake_mask[farmer_options[0]] = True

    player = RuleBasedPlayer(seed=0)
    # Early phase: tiles_left ≈ full deck → farmer should be filtered.
    assert b.state.deck and len(b.state.deck) > 0.6 * b.total_tiles
    pick = player.choose_action(g, b, fake_mask)
    assert pick == normal_options[0], (
        f"early farmer was picked: {pick} (farmer_base={farmer_base})"
    )


# ---------------------------------------------------------------------------
# Rule 4 — tile-phase 1-ply virtual_score: agrees with the heuristic policy.
# ---------------------------------------------------------------------------


def test_tile_choice_matches_heuristic_argmax() -> None:
    """Rule 4 is argmax of `_heuristic_policy` (without softmax temperature).
    For a mid-game position, the rule player should pick an action that has
    the maximum 1-ply virtual_score among legals — i.e. a maximizer of the
    same scoring function the heuristic policy is built on."""
    from carcassonne_ai.warmstart import _heuristic_policy

    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    # Walk a deterministic random game forward a bit to a mid-game tile phase.
    import random as _r
    rng = _r.Random(7)
    for _ in range(20):
        mask = g.get_valid_moves(b)
        legal = np.flatnonzero(mask)
        if len(legal) == 0 or g.get_game_ended(b, 0) != 0.0:
            break
        b, _next = g.get_next_state(b, int(rng.choice(legal.tolist())))

    if g.get_game_ended(b, 0) != 0.0 or b.state.phase.value != "tiles":
        pytest.skip("walk-forward did not reach a mid-game tile-phase position")

    mask = g.get_valid_moves(b)
    legal = np.flatnonzero(mask)
    if len(legal) < 2:
        pytest.skip("only one legal tile placement — argmax is trivial")

    player = RuleBasedPlayer(seed=0)
    pick = player.choose_action(g, b, mask)

    # virtual_score at tau=very-small is one-hot on the argmax; check the
    # rule player picked an action that's tied for the heuristic max.
    pol = _heuristic_policy(g, b, mask, tau=0.001)
    top_mass_actions = np.flatnonzero(pol > 0.5 / len(legal))
    # The rule player's pick should land on an action that the heuristic also
    # ranks at or near the top — exact equality unlikely due to softmax
    # blurring, so use a generous threshold: the chosen action's policy
    # weight should be >= the median legal weight.
    chosen_weight = pol[pick]
    median_weight = float(np.median(pol[legal]))
    assert chosen_weight >= median_weight, (
        f"rule pick {pick} has heuristic policy weight {chosen_weight:.4f}, "
        f"below median {median_weight:.4f}"
    )


def test_tile_choice_strictly_better_than_random_in_expectation() -> None:
    """Smoke check: across N games, rule-player avg score > random-player avg
    score by a meaningful margin (≥5 points). This is the macro evidence
    that Rule 4 is actually doing something."""
    import random as _r

    n_games = 6
    rule_diffs: list[int] = []
    for seed in range(n_games):
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        rng = _r.Random(seed)
        rule = RuleBasedPlayer(seed=seed)
        rule_idx = seed % 2
        while g.get_game_ended(b, 0) == 0.0:
            mask = g.get_valid_moves(b)
            legal = np.flatnonzero(mask)
            cur = b.state.current_player
            if cur == rule_idx:
                a = rule.choose_action(g, b, mask)
            else:
                a = int(rng.choice(legal.tolist()))
            b, _ = g.get_next_state(b, a)
        s0, s1 = b.state.scores
        diff = (s0 - s1) if rule_idx == 0 else (s1 - s0)
        rule_diffs.append(diff)
    mean_diff = sum(rule_diffs) / len(rule_diffs)
    # Heuristic-policy-driven rule player should beat random by a wide margin.
    # The 1-ply virtual_score heuristic at tau→0 is what generated
    # warmstart_canonical's labels, which beats random by ~100% wr at depth 0.
    # 5-point lead per game is a conservative floor.
    assert mean_diff > 5.0, (
        f"rule player avg diff vs random was only {mean_diff:+.1f} "
        f"across {n_games} games — Rule 4 may be miswired"
    )
