"""Tests for the luck-floor paired-archive reader (scripts/human_anchor/luck_floor.py).

These pin the CONSUMER CONTRACT that `scripts/rules_fixed/gen_luck_pairs.sh`
produces against: the F9 Phase C §1 residue is completed by feeding a seat-swap
paired archive to `luck_floor.load_pairs` / `archive_stats`, and the archive is
emitted by `scripts/classical_search/eval_fair_puct.py`, whose per-game JSON
spells the win boolean `won_by_champ` — not the `won_by_a` of the June v28
archives the module was written against. A silent mis-read there does not crash;
it reports wr_A ~= 0.0 for a champion-vs-champion archive, which looks like a
plausible number. Hence the pins.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))

import luck_floor as lf  # noqa: E402


def _write_pair(d: Path, seed: int, s0_a0, s1_a0, s0_a1, s1_a1, *, win_key="won_by_champ",
                pad=12):
    """Write one deck's two seatings in the eval_fair_puct on-disk shape.

    `(s0_a0, s1_a0)` = the seat0/seat1 final scores of the game where A sat in
    seat 0; `(s0_a1, s1_a1)` = the same for the game where A sat in seat 1.
    """
    for a_seat, (p0, p1) in ((0, (s0_a0, s1_a0)), (1, (s0_a1, s1_a1))):
        diff = (p0 - p1) if a_seat == 0 else (p1 - p0)
        rec = {
            "seed": seed, "a_seat": a_seat,
            "score_p0": int(p0), "score_p1": int(p1),
            "diff": int(diff), "drew": diff == 0,
            "elapsed_s": 1.0, "moves": 144, "deck_hash": f"{seed:016x}",
        }
        if win_key is not None:
            rec[win_key] = diff > 0
        name = f"seed{seed:0{pad}d}_a{a_seat}.json"
        (d / name).write_text(json.dumps(rec))


# A 4-deck archive. Deck margins are engineered so the two seatings of a deck
# agree in seat-0 sign (a real deck effect) while A's own margin flips around.
DECKS = [
    # seed, (A-in-seat0: p0, p1), (A-in-seat1: p0, p1)
    (109500000000, (110, 90), (95, 105)),    # A +20 then +10
    (109500000001, (80, 100), (120, 70)),    # A -20 then -50
    (109500000002, (100, 100), (100, 100)),  # draw both ways
    (109500000003, (130, 85), (70, 140)),    # A +45 then +70
]


def _build(d: Path, **kw):
    for seed, a0, a1 in DECKS:
        _write_pair(d, seed, a0[0], a0[1], a1[0], a1[1], **kw)
    return d


def test_load_pairs_reads_the_eval_fair_puct_shape(tmp_path):
    pairs = lf.load_pairs(_build(tmp_path))
    assert len(pairs) == 4
    for seed, rec in pairs.items():
        assert set(rec) == {0, 1}
        assert rec[0]["a_seat"] == 0 and rec[1]["a_seat"] == 1


def test_load_pairs_accepts_both_seed_paddings(tmp_path):
    """June archives name seed1924100000_a0.json; eval_fair_puct zero-pads to 12."""
    _write_pair(tmp_path, 1924100000, 110, 90, 95, 105, win_key="won_by_a", pad=0)
    _write_pair(tmp_path, 109500000000, 110, 90, 95, 105, pad=12)
    assert len(lf.load_pairs(tmp_path)) == 2


def test_load_pairs_ignores_partials_and_unpaired(tmp_path):
    _build(tmp_path)
    (tmp_path / "seed109500000009_a0.json").write_text(
        json.dumps({"seed": 109500000009, "a_seat": 0, "score_p0": 1, "score_p1": 2,
                    "diff": -1, "drew": False}))          # only one seating -> dropped
    (tmp_path / ".seed109500000010_a0.partial.json").write_text("{}")
    assert len(lf.load_pairs(tmp_path)) == 4


def test_archive_stats_pairs_and_sigmas(tmp_path):
    st = lf.archive_stats(_build(tmp_path), min_pairs=4)
    assert st["n_pairs"] == 4 and st["n_games"] == 8
    # A's margins: a0 = [+20, -20, 0, +45]; a1 = [+10, -50, 0, +70]
    assert st["mean_A_margin"] == pytest.approx((20 - 20 + 0 + 45 + 10 - 50 + 0 + 70) / 8)
    # seat_adv = (mean(a0) - mean(a1)) / 2
    assert st["seat_adv"] == pytest.approx((11.25 - 7.5) / 2)
    # sigma_pair is the SD of the seat-swap-averaged per-deck margin
    pair_means = [15.0, -35.0, 0.0, 57.5]
    mu = sum(pair_means) / 4
    assert st["sigma_pair"] == pytest.approx(
        (sum((x - mu) ** 2 for x in pair_means) / 4) ** 0.5)
    assert -1.0 <= st["luck_share"] <= 1.0


def test_min_pairs_gate(tmp_path):
    d = _build(tmp_path)
    assert lf.archive_stats(d) is None          # default 10 > 4 pairs
    assert lf.archive_stats(d, min_pairs=4) is not None


@pytest.mark.parametrize("win_key", ["won_by_champ", "won_by_cand", "won_by_a", None])
def test_wr_A_is_read_under_every_harness_spelling(tmp_path, win_key):
    """The regression this file exists for: `won_by_champ` must not read as a loss.

    A wins 2 of 8 (decks 0 and 3, both seatings), draws 2, loses 4 -> wr = 0.5625.
    """
    st = lf.archive_stats(_build(tmp_path, win_key=win_key), min_pairs=4)
    assert st["wr_A"] == pytest.approx((4 * 1.0 + 2 * 0.5) / 8)


def test_won_by_a_helper_prefers_the_recorded_flag_over_the_margin(tmp_path):
    # A deliberately inconsistent record: the flag wins, so a harness that
    # defines "win" differently (e.g. on a tiebreak) is not silently overruled.
    assert lf._won_by_a({"won_by_a": True}, -5) is True
    assert lf._won_by_a({"won_by_champ": False}, +5) is False
    assert lf._won_by_a({}, +5) is True
    assert lf._won_by_a({}, -5) is False
