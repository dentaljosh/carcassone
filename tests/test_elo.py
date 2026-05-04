"""Tests for the elo module — small enough that a few corner-case checks
suffice."""
from __future__ import annotations

import math

import pytest

from carcassonne_ai.elo import (
    elo_delta_from_winrate,
    expected_score,
    update_pair,
)


def test_expected_score_symmetry() -> None:
    assert expected_score(1500, 1500) == pytest.approx(0.5)
    e_a = expected_score(1600, 1500)
    e_b = expected_score(1500, 1600)
    assert e_a + e_b == pytest.approx(1.0)


def test_50pct_winrate_is_zero_delta() -> None:
    assert elo_delta_from_winrate(5, 5, 0) == pytest.approx(0.0, abs=1e-6)
    assert elo_delta_from_winrate(2, 2, 6) == pytest.approx(0.0, abs=1e-6)


def test_perfect_winrate_capped_at_max_delta() -> None:
    assert elo_delta_from_winrate(10, 0, 0) == 800.0
    assert elo_delta_from_winrate(0, 10, 0) == -800.0


def test_inversion_round_trips() -> None:
    """A 75% win rate corresponds to an ELO delta of ~191.
    log10(.75/.25) * 400 = log10(3) * 400 ≈ 190.85."""
    d = elo_delta_from_winrate(75, 25, 0)
    assert d == pytest.approx(400.0 * math.log10(3.0))


def test_update_pair_returns_anchor_plus_delta() -> None:
    new_elo, delta = update_pair(
        iter_n_elo_estimate=999.0, iter_prev_elo=1500.0,
        wins=8, losses=2, draws=0,
    )
    expected_delta = 400.0 * math.log10(0.8 / 0.2)
    assert delta == pytest.approx(expected_delta)
    assert new_elo == pytest.approx(1500.0 + expected_delta)


def test_zero_total_games_is_zero_delta() -> None:
    assert elo_delta_from_winrate(0, 0, 0) == 0.0
