"""Unit tests for the asymmetric-ladder crossover interpolation."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from ladder_asymmetric import crossover_heur_sims  # noqa: E402


def test_crossover_interpolates_in_log2_space():
    # wr crosses 0.5 exactly halfway (in log2) between 200 and 800 → 400.
    rungs = [(50, 0.80), (200, 0.60), (800, 0.40), (3200, 0.20)]
    cross, _ = crossover_heur_sims(rungs)
    assert abs(cross - 400.0) < 1.0  # log2 midpoint of 200..800


def test_crossover_exact_at_rung():
    # wr is exactly 0.5 at a rung → that rung's heur_sims.
    rungs = [(50, 0.70), (200, 0.50), (800, 0.30)]
    cross, _ = crossover_heur_sims(rungs)
    assert abs(cross - 200.0) < 1e-6


def test_all_wins_returns_inf():
    rungs = [(50, 0.9), (200, 0.8), (800, 0.7)]
    cross, note = crossover_heur_sims(rungs)
    assert math.isinf(cross) and "ALL" in note


def test_all_losses_returns_zero():
    rungs = [(50, 0.4), (200, 0.3), (800, 0.2)]
    cross, note = crossover_heur_sims(rungs)
    assert cross == 0.0 and "ALL" in note


def test_unsorted_input_handled():
    rungs = [(800, 0.40), (50, 0.80), (200, 0.60)]
    cross, _ = crossover_heur_sims(rungs)
    assert abs(cross - 400.0) < 1.0


def test_empty_is_nan():
    cross, _ = crossover_heur_sims([])
    assert math.isnan(cross)
