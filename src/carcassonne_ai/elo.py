"""Lightweight ELO tracking for Phase 4 head-to-head evaluation.

Stateless functions; no class overhead. ELO updates are computed from
(wins, losses, draws) of a head-to-head match between two checkpoints.

Convention: when iter_N plays iter_(N-1), `iter_(N-1)` is the reference
(its ELO stays put) and `iter_N` gets `delta = elo_delta_from_winrate(...)`
added to iter_(N-1)'s ELO.

Score convention: a draw counts as half a win.
"""
from __future__ import annotations

import math


def expected_score(my_elo: float, opp_elo: float) -> float:
    """Standard ELO expected score from rating differential."""
    return 1.0 / (1.0 + 10.0 ** ((opp_elo - my_elo) / 400.0))


def elo_delta_from_winrate(
    wins: int, losses: int, draws: int, *, max_delta: float = 800.0
) -> float:
    """Convert a head-to-head record into an ELO delta vs the opponent.

    Inverts `score = 1 / (1 + 10^(-delta/400))` →
            `delta = 400 * log10(score / (1 - score))`.

    Returns `±max_delta` (default 800) if score is exactly 0 or 1, since
    the inversion blows up. Capped at ±max_delta either way to keep noisy
    small-N matches from producing absurd deltas.
    """
    total = wins + losses + draws
    if total <= 0:
        return 0.0
    score = (wins + 0.5 * draws) / total
    eps = 1e-6
    if score >= 1.0 - eps:
        return max_delta
    if score <= eps:
        return -max_delta
    delta = 400.0 * math.log10(score / (1.0 - score))
    return max(-max_delta, min(max_delta, delta))


def update_pair(
    iter_n_elo_estimate: float,
    iter_prev_elo: float,
    wins: int,
    losses: int,
    draws: int,
) -> tuple[float, float]:
    """Return (new_iter_n_elo, elo_delta_from_winrate).

    `iter_prev_elo` is treated as the anchor — it does not change. We
    re-anchor `iter_n` relative to the opponent so it lands at
    `iter_prev_elo + delta`. The previous estimate of iter_n's ELO is
    discarded — we always trust the most recent head-to-head against the
    immediate predecessor.
    """
    delta = elo_delta_from_winrate(wins, losses, draws)
    return iter_prev_elo + delta, delta
