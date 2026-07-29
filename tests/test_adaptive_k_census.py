"""Unit tests for the adaptive-k PRE-GATE census (scripts/measurement_infra/adaptive_k_census.py).

Covers the PURE parts only — world-seed determinism, the cheap-signature/real-shuffle
equivalence the duplicate census rests on, duplicate detection, phase bucketing, the
pooled-Q prefix picks, and the stratified sampler. The searched parts are exercised by
the run itself (checksum-verified replay + the --noise-control determinism assertion).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import adaptive_k_census as AK  # noqa: E402


# --------------------------------------------------------------------------- #
# phase bucketing — must match the CL-070 root bank exactly                     #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("k,expected", [
    (72, "early"), (49, "early"), (48, "late"), (47, "mid"),
    (25, "mid"), (24, "late"), (23, "late"), (2, "late"), (0, "late"),
])
def test_phase_bucket_matches_bank_cuts(k, expected):
    assert AK.phase_bucket(k) == expected


def test_phase_bucket_reproduces_the_banks_boundary_quirk():
    """PHASE_CUTS uses STRICT `lo < k < hi`, so the exact cut points 48 and 24 match no
    band and fall through to the "late" default. That is a quirk, not a design — but the
    CL-070 root bank was built with it (k=48 rows carry phase_bucket="late" on disk), and
    this census must join to that bank, so we reproduce it verbatim rather than "fix" it.
    Affects 14 of the bank's 898 roots."""
    assert AK.phase_bucket(48) == "late"
    assert AK.phase_bucket(24) == "late"
    assert AK.phase_bucket(47) == "mid"
    assert AK.phase_bucket(49) == "early"


# --------------------------------------------------------------------------- #
# world seed lineage                                                            #
# --------------------------------------------------------------------------- #
def test_world_seed_is_deterministic_and_in_range():
    a = AK.world_seed(28000000000, 66, AK.DEFAULT_SALT)
    b = AK.world_seed(28000000000, 66, AK.DEFAULT_SALT)
    assert a == b
    assert 0 <= a <= 0x7FFFFFFF


def test_world_seed_separates_roots_and_salts():
    base = AK.world_seed(1234, 10, 7)
    assert AK.world_seed(1234, 11, 7) != base      # different ply
    assert AK.world_seed(1235, 10, 7) != base      # different game
    assert AK.world_seed(1234, 10, 8) != base      # different salt


def test_world_seed_salt_is_disjoint_from_bank_tag_salts():
    """The census salt must not collide with the CL-070 tag lineage (9000/9001), else
    the redrawn worlds stop being independent of the picks recorded in the bank."""
    for ds, ply in ((28000000000, 66), (28000000005, 3), (1, 1)):
        base = AK.world_seed(ds, ply, AK.DEFAULT_SALT)
        assert base != AK.world_seed(ds, ply, 9000)
        assert base != AK.world_seed(ds, ply, 9001)


# --------------------------------------------------------------------------- #
# THE load-bearing equivalence: shuffling descriptions == shuffling the tiles    #
# --------------------------------------------------------------------------- #
class _FakeTile:
    def __init__(self, description):
        self.description = description


def test_shuffle_is_content_independent_same_permutation():
    """random.Random.shuffle is Fisher-Yates over INDICES; it never inspects elements.
    The duplicate census draws its replicate groups by shuffling description strings
    instead of deepcopying boards, which is only valid if the permutation (and the rng
    stream consumption) is identical. Pin that."""
    descs = sorted(["road"] * 9 + ["city"] * 5 + ["monastery"] * 4 + ["river"] * 2)
    tiles = [_FakeTile(d) for d in descs]

    r1 = random.Random(12345)
    r1.shuffle(tiles)
    from_tiles = tuple(t.description for t in tiles)

    r2 = random.Random(12345)
    from_strs = AK.draw_world_signature(descs, r2)

    assert from_tiles == from_strs
    # and the rng streams must be at the SAME state afterwards
    assert r1.random() == r2.random()


def test_draw_world_signature_does_not_mutate_input():
    canon = ["a", "b", "c", "d", "e"]
    before = list(canon)
    AK.draw_world_signature(canon, random.Random(1))
    assert canon == before


def test_draw_world_signature_preserves_multiset():
    canon = sorted(["x"] * 3 + ["y"] * 2)
    sig = AK.draw_world_signature(canon, random.Random(9))
    assert sorted(sig) == canon


def test_canonical_deck_descriptions_is_order_invariant():
    """The audit hardening: the world must be a pure function of the unseen MULTISET,
    not of the engine's (unobservable) true deck order."""
    a = [_FakeTile(d) for d in ["road", "city", "road", "monastery"]]
    b = [_FakeTile(d) for d in ["monastery", "road", "road", "city"]]
    assert AK.canonical_deck_descriptions(a) == AK.canonical_deck_descriptions(b)


# --------------------------------------------------------------------------- #
# duplicate detection                                                           #
# --------------------------------------------------------------------------- #
def test_duplicate_stats_all_distinct():
    sigs = [("a", "b"), ("b", "a"), ("a", "b", "c"), ("c",)]
    d = AK.duplicate_stats(sigs)
    assert d["k"] == 4
    assert d["n_distinct_full"] == 4
    assert d["dup_any"] is False
    assert d["n_wasted_full"] == 0


def test_duplicate_stats_exact_duplicates():
    s = ("a", "b", "c")
    d = AK.duplicate_stats([s, s, ("c", "b", "a"), s])
    assert d["n_distinct_full"] == 2
    assert d["dup_any"] is True
    assert d["n_wasted_full"] == 2


def test_duplicate_stats_prefix_near_identity():
    """Near-identity at prefix N: the next N tiles are what a search sees first."""
    sigs = [("a", "b", "c"), ("a", "z", "y"), ("b", "b", "b"), ("c", "q", "q")]
    d = AK.duplicate_stats(sigs)
    assert d["n_distinct_full"] == 4
    assert d["n_distinct_p1"] == 3        # a, a, b, c
    assert d["dup_any_p1"] is True
    assert d["n_wasted_p1"] == 1
    assert d["n_distinct_p2"] == 4


def test_duplicate_stats_singleton_deck_is_all_duplicate():
    """A 1-tile bag has exactly one ordering: every extra world is pure waste."""
    d = AK.duplicate_stats([("only",)] * 4)
    assert d["n_distinct_full"] == 1
    assert d["n_wasted_full"] == 3
    assert d["dup_any"] is True


def test_duplicate_stats_empty_deck():
    d = AK.duplicate_stats([()] * 4)
    assert d["n_distinct_full"] == 1
    assert d["n_wasted_full"] == 3


# --------------------------------------------------------------------------- #
# pooled prefix picks (the marginal-world measure)                              #
# --------------------------------------------------------------------------- #
def _w(n_map, q_map):
    """(n_map, w_map) from visit counts + per-action Q."""
    return ({a: float(n) for a, n in n_map.items()},
            {a: float(n) * q_map[a] for a, n in n_map.items()})


def test_pooled_pick_prefix_can_change_with_more_worlds():
    # worlds 0,1 love action 1; worlds 2,3 love action 2 strongly enough to flip the pool
    pw = [
        _w({1: 100, 2: 100}, {1: 0.50, 2: 0.10}),
        _w({1: 100, 2: 100}, {1: 0.50, 2: 0.10}),
        _w({1: 100, 2: 100}, {1: 0.00, 2: 0.90}),
        _w({1: 100, 2: 100}, {1: 0.00, 2: 0.90}),
    ]
    p2, _ = AK.pooled_pick(pw, 2)
    p4, g4 = AK.pooled_pick(pw, 4)
    assert p2 == 1
    assert p4 == 2
    assert g4 == pytest.approx(0.25, abs=1e-9)   # (0.5 vs 0.25) pooled means


def test_pooled_pick_stable_when_worlds_agree():
    pw = [_w({1: 50, 2: 50}, {1: 0.4, 2: 0.1}) for _ in range(4)]
    assert AK.pooled_pick(pw, 2)[0] == AK.pooled_pick(pw, 4)[0] == 1


def test_pooled_pick_empty_worlds():
    assert AK.pooled_pick([({}, {})], 1) == (None, None)


def test_pooled_pick_min_visits_floor_excludes_single_visit_noise():
    """A 1-visit action with a spectacular Q must not win the pooled argmax."""
    pw = [_w({1: 200, 7: 1}, {1: 0.3, 7: 0.99})]
    assert AK.pooled_pick(pw, 1, min_visits=2)[0] == 1


def test_pooled_pick_single_action_has_no_gap():
    pw = [_w({5: 10}, {5: 0.2})]
    a, g = AK.pooled_pick(pw, 1)
    assert a == 5 and g is None


# --------------------------------------------------------------------------- #
# stratified sampler                                                            #
# --------------------------------------------------------------------------- #
def _rows(n_by_bucket):
    out = []
    i = 0
    for b, n in n_by_bucket.items():
        for _ in range(n):
            out.append({"deck_seed": 1000 + i, "ply": i % 7, "phase_bucket": b})
            i += 1
    return out


def test_stratified_sample_is_deterministic_and_sized():
    rows = _rows({"early": 100, "mid": 100, "late": 100})
    a = AK.stratified_sample(rows, 60, seed=5)
    b = AK.stratified_sample(rows, 60, seed=5)
    assert len(a) == 60
    assert [(r["deck_seed"], r["ply"]) for r in a] == [(r["deck_seed"], r["ply"]) for r in b]


def test_stratified_sample_is_input_order_invariant():
    rows = _rows({"early": 50, "mid": 60, "late": 40})
    shuffled = list(rows)
    random.Random(3).shuffle(shuffled)
    a = {(r["deck_seed"], r["ply"]) for r in AK.stratified_sample(rows, 45, seed=11)}
    b = {(r["deck_seed"], r["ply"]) for r in AK.stratified_sample(shuffled, 45, seed=11)}
    assert a == b


def test_stratified_sample_keeps_phase_proportions():
    rows = _rows({"early": 300, "mid": 300, "late": 600})
    got = AK.stratified_sample(rows, 120, seed=2)
    from collections import Counter
    c = Counter(r["phase_bucket"] for r in got)
    assert c["early"] == 30 and c["mid"] == 30 and c["late"] == 60


def test_stratified_sample_n_zero_or_all_returns_everything_sorted():
    rows = _rows({"early": 5, "late": 5})
    allr = AK.stratified_sample(rows, 0, seed=1)
    assert len(allr) == 10
    assert allr == sorted(allr, key=lambda r: (r["deck_seed"], r["ply"]))
    assert len(AK.stratified_sample(rows, 999, seed=1)) == 10


def test_stratified_sample_no_duplicates():
    rows = _rows({"early": 33, "mid": 33, "late": 34})
    got = AK.stratified_sample(rows, 47, seed=8)
    keys = [(r["deck_seed"], r["ply"]) for r in got]
    assert len(keys) == len(set(keys)) == 47


# --------------------------------------------------------------------------- #
# latch band constant tracks the agent, not a copy                              #
# --------------------------------------------------------------------------- #
def test_latch_band_tracks_fair_agent():
    from carcassonne_ai import fair_agent as FA
    assert AK.LATCH_K == FA.EXACT_MAX_K
