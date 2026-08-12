"""Unit tests for the sims-split PRE-GATE census (scripts/measurement_infra/simsplit_census.py).

Covers the PURE parts only — rung derivation, the turn-atomic latch rule, salt
disjointness, flip computation, gap binning, the two-proportion contrast, and the
summary aggregation on synthetic rows. The searched parts are exercised by the run
itself (checksum-verified replay + the --determinism-every bit-identity assertion),
exactly the split test_adaptive_k_census.py uses.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import adaptive_k_census as AK  # noqa: E402
import simsplit_census as SC  # noqa: E402


# --------------------------------------------------------------------------- #
# rung derivation                                                               #
# --------------------------------------------------------------------------- #
def test_derive_rungs_production_ladder():
    """The pre-registered ladder at the production per-world budget."""
    assert SC.derive_rungs(1376) == [172, 344, 688, 1376]


def test_derive_rungs_ends_at_reference():
    assert SC.derive_rungs(688) == [86, 172, 344, 688]
    assert SC.derive_rungs(688)[-1] == 688


def test_derive_rungs_rejects_degenerate():
    with pytest.raises(ValueError):
        SC.derive_rungs(4)            # 4//8 = 0 -> invalid rung
    with pytest.raises(ValueError):
        SC.derive_rungs(1376, divisors=(8, 4, 2))   # must end at 1 (the reference)
    with pytest.raises(ValueError):
        SC.derive_rungs(8, divisors=(8, 8, 1))      # duplicate rungs


# --------------------------------------------------------------------------- #
# turn-atomic latch rule                                                        #
# --------------------------------------------------------------------------- #
def test_latch_tiles_is_the_agent_condition():
    """TILES: exactly fair_agent's latch condition (phase==TILES and k<=EXACT_MAX_K)."""
    assert SC.turn_latch_owned("TILES", SC.LATCH_K) is True
    assert SC.turn_latch_owned("TILES", SC.LATCH_K + 1) is False
    assert SC.turn_latch_owned("TILES", 1) is True


def test_latch_meeples_is_turn_atomic_not_blanket():
    """A MEEPLES root at k == EXACT_MAX_K is LIVE: its turn's TILES decision saw
    k+1 > EXACT_MAX_K (the engine pre-draws next turn's tile during MEEPLES), so
    the latch had not fired and the meeple decision was searched by fair PIMC.
    The adaptive-k census's blanket k<=2 wrongly counts these as solver-owned —
    which is exactly why this census records both rules."""
    assert SC.turn_latch_owned("MEEPLES", SC.LATCH_K) is False        # live
    assert SC.turn_latch_owned("MEEPLES", SC.LATCH_K - 1) is True     # solver-owned


def test_latch_unknown_phase_raises():
    with pytest.raises(ValueError):
        SC.turn_latch_owned("RIVER", 5)


def test_latch_k_tracks_fair_agent():
    from carcassonne_ai import fair_agent as FA
    assert SC.LATCH_K == FA.EXACT_MAX_K


# --------------------------------------------------------------------------- #
# salt disjointness (world lineage must be independent of every prior probe)     #
# --------------------------------------------------------------------------- #
def test_salt_is_disjoint_from_adaptive_k_and_bank_lineages():
    assert SC.DEFAULT_SALT != AK.DEFAULT_SALT
    for ds, ply in ((28000000000, 66), (28000000005, 3), (1, 1)):
        base = AK.world_seed(ds, ply, SC.DEFAULT_SALT)
        for other in (AK.DEFAULT_SALT, 9000, 9001):
            assert base != AK.world_seed(ds, ply, other)


# --------------------------------------------------------------------------- #
# flip computation                                                              #
# --------------------------------------------------------------------------- #
def test_flips_vs_ref_basic():
    picks = {172: 5, 344: 7, 688: 7, 1376: 7}
    f = SC.flips_vs_ref(picks, 1376)
    assert f == {172: True, 344: False, 688: False}
    assert 1376 not in f                      # the reference never flips vs itself


def test_flips_vs_ref_none_pick_counts_as_flip():
    """A rung that produced no pooled action IS a decision change vs a real ref pick."""
    assert SC.flips_vs_ref({172: None, 1376: 7}, 1376)[172] is True
    assert SC.flips_vs_ref({172: None, 1376: None}, 1376)[172] is False


def test_world_flip_frac():
    assert SC.world_flip_frac([1, 2, 3, 4], [1, 2, 3, 4]) == 0.0
    assert SC.world_flip_frac([1, 2, 3, 4], [1, 2, 9, 9]) == 0.5
    assert SC.world_flip_frac([1, None, 3], [9, 2, 3]) == pytest.approx(0.5)
    assert SC.world_flip_frac([None], [None]) is None


# --------------------------------------------------------------------------- #
# gap bins (fixed, pre-registered)                                              #
# --------------------------------------------------------------------------- #
def test_gap_bin_edges():
    assert SC.gap_bin(None) == "na"
    assert SC.gap_bin(0.0) == "[0,0.02)"
    assert SC.gap_bin(0.019999) == "[0,0.02)"
    assert SC.gap_bin(0.02) == "[0.02,0.05)"
    assert SC.gap_bin(0.05) == "[0.05,0.1)"
    assert SC.gap_bin(0.10) == "[0.1,inf)"
    assert SC.gap_bin(3.0) == "[0.1,inf)"


def test_gap_bin_labels_cover_every_declared_bin():
    labels = {SC.gap_bin(lo) for lo, _hi in SC.GAP_BINS}
    assert len(labels) == len(SC.GAP_BINS)


# --------------------------------------------------------------------------- #
# two-proportion contrast                                                       #
# --------------------------------------------------------------------------- #
def test_two_prop_z_known_value():
    # 30/100 vs 10/100: p=0.2, se=sqrt(.2*.8*.02)=0.056568..., z=0.2/se
    z = SC.two_prop_z(30, 100, 10, 100)
    assert z == pytest.approx(0.20 / math.sqrt(0.2 * 0.8 * 0.02), abs=1e-12)


def test_two_prop_z_sign_and_degenerate():
    assert SC.two_prop_z(10, 100, 30, 100) < 0
    assert SC.two_prop_z(0, 0, 5, 10) is None            # empty cell
    assert SC.two_prop_z(0, 50, 0, 50) is None           # pooled variance 0
    assert SC.two_prop_z(50, 50, 50, 50) is None


# --------------------------------------------------------------------------- #
# summary aggregation on synthetic rows                                         #
# --------------------------------------------------------------------------- #
def _row(phase, flips, *, gap=0.06, n_legal=None, k_rem=30, latch=False, det=None):
    r = {"ok": True, "phase": phase, "phase_bucket": "mid", "k_remaining": k_rem,
         "n_legal": n_legal if n_legal is not None else (28 if phase == "TILES" else 4),
         "latch_owned": latch, "latch_owned_blanket": latch,
         "ref_gap": gap, "ref_gap_bin": SC.gap_bin(gap),
         "flip_by_sims": {str(s): bool(v) for s, v in flips.items()},
         "world_flip_frac_by_sims": {str(s): (1.0 if v else 0.0)
                                     for s, v in flips.items()},
         "secs": 1.0}
    if det is not None:
        r["determinism_identical"] = det
    return r


RUNGS = [172, 344, 688, 1376]


def test_summarize_flip_rates_split_by_decision_type():
    rows = ([_row("TILES", {172: True, 344: True, 688: False}) for _ in range(6)]
            + [_row("TILES", {172: False, 344: False, 688: False}) for _ in range(4)]
            + [_row("MEEPLES", {172: True, 344: False, 688: False}) for _ in range(2)]
            + [_row("MEEPLES", {172: False, 344: False, 688: False}) for _ in range(8)])
    s = SC.summarize(rows, RUNGS)
    assert s["n_live"] == 20
    t = s["by_decision_type"]["TILES"]
    m = s["by_decision_type"]["MEEPLES"]
    assert t["n"] == 10 and m["n"] == 10
    assert t["flip_344_rate"] == pytest.approx(0.6)
    assert m["flip_344_rate"] == pytest.approx(0.0)
    assert t["flip_172_rate"] == pytest.approx(0.6)
    assert m["flip_172_rate"] == pytest.approx(0.2)
    assert t["flip_688_rate"] == 0.0
    # the confound guard: n_legal is reported right next to the rates
    assert t["n_legal_mean"] == pytest.approx(28)
    assert m["n_legal_mean"] == pytest.approx(4)
    # contrast carries counts + z per rung
    c = s["tiles_vs_meeples_flip_contrast"]["344"]
    assert c["tiles"] == [6, 10] and c["meeples"] == [0, 10]
    assert c["raw_z"] > 0


def test_summarize_excludes_latch_owned_and_counts_both_rules():
    rows = ([_row("TILES", {172: True, 344: False, 688: False})]
            + [_row("TILES", {172: False, 344: False, 688: False}) for _ in range(2)]
            + [_row("TILES", {}, latch=True) for _ in range(2)])
    s = SC.summarize(rows, RUNGS)
    assert s["n_live"] == 3
    assert s["n_latch_owned_turn_atomic"] == 2
    assert s["overall"]["flip_172_rate"] == pytest.approx(1 / 3)


def test_summarize_gap_bins_and_determinism():
    rows = ([_row("MEEPLES", {172: True, 344: False, 688: False}, gap=0.01, det=True)
             for _ in range(5)]
            + [_row("MEEPLES", {172: False, 344: False, 688: False}, gap=0.5, det=True)
               for _ in range(5)])
    s = SC.summarize(rows, RUNGS)
    gb = s["by_gap_bin"]["MEEPLES"]
    assert gb["[0,0.02)"]["n"] == 5
    assert gb["[0,0.02)"]["flip_172_rate"] == pytest.approx(1.0)
    assert gb["[0.1,inf)"]["flip_172_rate"] == pytest.approx(0.0)
    assert s["determinism_n"] == 10
    assert s["determinism_all_identical"] is True
    rows[0]["determinism_identical"] = False
    assert SC.summarize(rows, RUNGS)["determinism_all_identical"] is False


def test_summarize_reports_wilson_intervals():
    rows = [_row("TILES", {172: i < 2, 344: False, 688: False}) for i in range(10)]
    s = SC.summarize(rows, RUNGS)
    lo68, hi68 = s["overall"]["flip_172_ci68"]
    lo95, hi95 = s["overall"]["flip_172_ci95"]
    assert lo95 <= lo68 <= 0.2 <= hi68 <= hi95


# --------------------------------------------------------------------------- #
# shared machinery really is shared (pins against silent divergence from AK)     #
# --------------------------------------------------------------------------- #
def test_reuses_adaptive_k_pooled_pick_and_phase_cuts():
    """The pooled pick and phase cuts must be the SAME objects the adaptive-k
    census (and through it, fair_agent's production rule) uses — this census must
    stay joinable to that bank, not carry a drifting copy."""
    import simsplit_census as SC2
    assert SC2.AK is AK
    assert AK.pooled_pick is SC.AK.pooled_pick
    assert AK.PHASE_CUTS == {"early": (48, 10**9), "mid": (24, 48), "late": (-1, 24)}
