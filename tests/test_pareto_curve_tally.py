"""Pin the Pareto-curve read-out's load-bearing statistic against a PUBLISHED result.

`deck_matched_delta` is the double-CRN contrast the whole curve read-out rests on
(PARETO_CURVE_PREREG.md rule 2: the within-tier allocation contrast is a
deck-matched delta, NOT a difference of absolute elos). A silent bug there would
not look like a bug -- it would look like a result.

CL-054's n=400 confirm cells are the ideal fixture: three allocations at a fixed
total budget, all on the SAME seed band (17.0001e9), with deltas published in
governance/CLAIM_REGISTRY.csv and experiments/results.csv. If this module's
implementation is right it must reproduce them.

These tests skip when the share is not mounted (laptop/CI), since the fixture is
the real run output, not checked-in data.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

# The read-out lives in scripts/, not on the package path. Insert it explicitly
# rather than relying on PYTHONPATH: with a bare `importorskip` a plain
# `pytest tests/` SKIPS every test here, and a silently-skipped regression test
# is worse than no test -- it reads as green.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "classical_search"))
import pareto_curve_tally as pareto  # noqa: E402

SHARE = pathlib.Path("/mnt/c/carc-shared")
CELLS = {
    "k2": "kdets_k2x1376_tot2752_curve125champ_vs_h800_k2_confirm_b17001",
    "k4": "kdets_k4x688_tot2752_curve125champ_vs_h800_k2_confirm_b17001",
    "k8": "kdets_k8x344_tot2752_curve125champ_vs_h800_k2_confirm_b17001",
}

# (candidate, reference, mean pts/deck, se, z) — CL-054, registry + results.csv.
PUBLISHED = [
    ("k4", "k8", +5.18, 1.24, +4.17),
    ("k2", "k8", +3.36, 1.41, +2.38),
    ("k4", "k2", +1.82, 1.37, +1.33),
]


def _games(key: str):
    d = SHARE / CELLS[key]
    if not d.is_dir():
        pytest.skip(f"fixture not mounted: {d}")
    g = pareto.load_games(d)
    if len(g) < 400:
        pytest.skip(f"fixture incomplete: {len(g)}/400 records in {d}")
    return g


@pytest.mark.parametrize("cand,ref,mean,se,z", PUBLISHED)
def test_reproduces_cl054_published_delta(cand, ref, mean, se, z):
    """The deck-matched delta must reproduce CL-054's published numbers."""
    res = pareto.deck_matched_delta(_games(cand), _games(ref))
    assert res is not None
    got_mean, got_se, got_z, n_decks = res
    assert n_decks == 200, f"expected 200 shared decks, got {n_decks}"
    assert got_mean == pytest.approx(mean, abs=0.01)
    assert got_se == pytest.approx(se, abs=0.01)
    assert got_z == pytest.approx(z, abs=0.01)


def test_delta_is_antisymmetric():
    """delta(a,b) == -delta(b,a): a sign slip here would invert every contrast."""
    ab = pareto.deck_matched_delta(_games("k4"), _games("k8"))
    ba = pareto.deck_matched_delta(_games("k8"), _games("k4"))
    assert ab[0] == pytest.approx(-ba[0], abs=1e-9)
    assert ab[1] == pytest.approx(ba[1], abs=1e-9)


def test_self_delta_is_exactly_zero():
    """A cell against itself must be identically 0 — catches deck-misalignment."""
    mean, se, _z, n = pareto.deck_matched_delta(_games("k4"), _games("k4"))
    assert mean == pytest.approx(0.0, abs=1e-12)
    assert se == pytest.approx(0.0, abs=1e-12)
    assert n == 200


def test_per_deck_margin_drops_incomplete_decks():
    """Only decks with BOTH seats count — a half-played deck is seat-biased."""
    games = _games("k4")
    margins = pareto.per_deck_margin(games)
    assert len(margins) == 200
    truncated = [g for g in games if g["a_seat"] == 0]
    assert pareto.per_deck_margin(truncated) == {}
