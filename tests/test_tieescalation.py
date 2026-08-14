"""Contract tests for the tie-triggered search-escalation pre-gate instrument
(scripts/tiletie/escalation_ladder.py; measurement/tieescalation_20260814/).

Pure arithmetic + corpus-metadata contracts — no engine import, no search."""
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import escalation_ladder as EL  # noqa: E402


# --------------------------------------------------------------------------- #
# pick resolution                                                              #
# --------------------------------------------------------------------------- #
def test_resolve_pick_exact_membership():
    assert EL.resolve_pick(943, [940, 941, 943, 954], None) == 2


def test_resolve_pick_via_transposition_map():
    # 1149 is a board-duplicate of the surviving representative 1148
    rmap = {1148: 1148, 1149: 1148, 1150: 1148, 1348: 1348}
    assert EL.resolve_pick(1149, [1148, 1348], rmap) == 0


def test_resolve_pick_unresolved_outside_scored_set():
    assert EL.resolve_pick(9999, [940, 941], {1149: 1148}) is None
    assert EL.resolve_pick(None, [940, 941], None) is None


# --------------------------------------------------------------------------- #
# honest regret (symmetrized parity split)                                     #
# --------------------------------------------------------------------------- #
def test_honest_regret_zero_when_base_is_best_everywhere():
    values = [[5.0] * 8, [1.0] * 8]
    assert EL.honest_regret(values, 0) == 0.0


def test_honest_regret_positive_when_another_arm_dominates():
    values = [[1.0] * 8, [3.0] * 8]
    assert EL.honest_regret(values, 0) == 2.0


def test_honest_regret_symmetric_in_parity():
    # arm 1 looks best on even worlds only; arm 2 on odd worlds only —
    # the symmetrized statistic must not depend on which half selects.
    even_up = [10.0, 0.0] * 4
    odd_up = [0.0, 10.0] * 4
    base = [1.0] * 8
    v = [base, even_up, odd_up]
    r1 = EL.honest_regret(v, 0)
    v_swapped = [base, odd_up, even_up]
    r2 = EL.honest_regret(v_swapped, 0)
    assert math.isclose(r1, r2)


# --------------------------------------------------------------------------- #
# rung statistics                                                              #
# --------------------------------------------------------------------------- #
def _row(rid, root, base_idx, rung_idx, values, scale=1.0, stratum="selfplay",
         champ=None):
    picks = {EL.BASE_RUNG: 100 + (base_idx if base_idx is not None else 99)}
    idxs = {EL.BASE_RUNG: base_idx}
    picks[2752] = 100 + (rung_idx if rung_idx is not None else 99)
    idxs[2752] = rung_idx
    return {"rid": rid, "root_id": root, "stratum": stratum, "profile": "walled",
            "phase": "mid", "scale_all": scale, "arms": [100, 101, 102],
            "values": values, "champ_action": champ, "picks": picks,
            "idxs": idxs, "secs": {EL.BASE_RUNG: 10.0, 2752: 20.0}}


def test_rung_stats_capture_and_coverage():
    v = [[0.0] * 4, [2.0] * 4, [1.0] * 4]
    rows = [
        _row("a", "r1", 0, 1, v),            # capture +2
        _row("b", "r2", 0, 0, v),            # unchanged, capture 0
        _row("c", "r3", 0, None, v),         # rung escaped the scored set
        _row("d", "r4", None, 1, v),         # base unresolved -> excluded
    ]
    s = EL.rung_stats(rows, 2752)
    assert s["n_pairs"] == 2
    assert s["n_base_resolved"] == 3
    assert math.isclose(s["mean_capture"], 1.0)          # (2 + 0) / 2
    assert math.isclose(s["coverage"], 2 / 4)
    assert math.isclose(s["outside_scored_rate"], 1 / 3)
    assert math.isclose(s["pick_change_rate_arm"], 1 / 2)


def test_rung_stats_applies_scale_all():
    v = [[0.0] * 4, [2.0] * 4]
    rows = [_row("a", "r1", 0, 1, v, scale=0.5),
            _row("b", "r2", 0, 1, v, scale=0.5)]
    s = EL.rung_stats(rows, 2752)
    assert math.isclose(s["mean_capture"], 1.0)          # 2 * 0.5


def test_denom_stats_uses_base_resolved_population():
    v = [[1.0] * 8, [3.0] * 8]
    rows = [_row("a", "r1", 0, 1, v), _row("b", "r2", None, 1, v)]
    d = EL.denom_stats(rows)
    assert d["n"] == 1
    assert math.isclose(d["mean"], 2.0)


def test_base_agreement_witness_counts_selfplay_only():
    v = [[0.0] * 4, [1.0] * 4]
    rows = [_row("a", "r1", 0, 0, v, champ=100),          # base pick 100 == champ
            _row("b", "r2", 1, 1, v, champ=100),          # base pick 101 != champ
            _row("c", "r3", 0, 0, v, stratum="e4", champ=100)]
    w = EL.base_agreement(rows)
    assert (w["n"], w["agree"]) == (2, 1)


# --------------------------------------------------------------------------- #
# adjudication — READ_RULE §4, first match wins                                #
# --------------------------------------------------------------------------- #
def _stats(rung, z, capture, coverage=1.0, n=522):
    return {"rung": rung, "z": z, "mean_capture": capture, "coverage": coverage,
            "n_pairs": int(n * coverage), "n_base_resolved": n}


def test_adjudicate_unreadable_on_checksum_error():
    st = {EL.BASE_RUNG: _stats(EL.BASE_RUNG, float("nan"), 0.0),
          2752: _stats(2752, 3.0, 0.2)}
    v = EL.adjudicate(st, {"checksum_error": 1}, 522, 0.2)
    assert v["branch"] == "E-0 UNREADABLE"


def test_adjudicate_harmful_precedes_fund():
    st = {EL.BASE_RUNG: _stats(EL.BASE_RUNG, float("nan"), 0.0),
          2752: _stats(2752, -2.5, -0.1),
          5504: _stats(5504, 2.5, 0.15)}
    assert EL.adjudicate(st, {}, 522, 0.2)["branch"] == "E-HARMFUL"


def test_adjudicate_flat_when_no_rung_clears_both_bars():
    st = {EL.BASE_RUNG: _stats(EL.BASE_RUNG, float("nan"), 0.0),
          2752: _stats(2752, 2.5, 0.05),     # z ok, ratio 0.25 < 0.35
          5504: _stats(5504, 1.0, 0.15)}     # ratio ok, z < 2
    assert EL.adjudicate(st, {}, 522, 0.2)["branch"] == "E-FLAT"


def test_adjudicate_fund_names_smallest_rung_never_argmax():
    st = {EL.BASE_RUNG: _stats(EL.BASE_RUNG, float("nan"), 0.0),
          2752: _stats(2752, 2.1, 0.08),     # clears: ratio 0.40
          5504: _stats(5504, 4.0, 0.18),     # clears bigger — must NOT be named
          13760: _stats(13760, 3.0, 0.12)}
    v = EL.adjudicate(st, {}, 522, 0.2)
    assert v["branch"] == "E-FUND-DEV"
    assert v["named_rung"] == 2752


def test_adjudicate_fund_requires_coverage_bar():
    st = {EL.BASE_RUNG: _stats(EL.BASE_RUNG, float("nan"), 0.0),
          2752: _stats(2752, 2.5, 0.10, coverage=0.5)}
    assert EL.adjudicate(st, {}, 522, 0.2)["branch"] == "E-FLAT"


def test_adjudicate_holdout_branches():
    assert EL.adjudicate_holdout(2.4) == "E-CONFIRMED"
    assert EL.adjudicate_holdout(1.1) == "E-WEAK"
    assert EL.adjudicate_holdout(-0.3) == "E-REFUTED"


# --------------------------------------------------------------------------- #
# slices — the holdout firewall                                                #
# --------------------------------------------------------------------------- #
def test_slices_match_the_committed_split():
    import term_gate as TG
    per = TG.load_per_position()
    dev = EL.slice_rids(per, "dev")
    hold = EL.slice_rids(per, "holdout")
    assert len(dev) == 522 and len(hold) == 211      # HOLDOUT_ROOTS.json counts
    assert not set(dev) & set(hold)
    hr = EL.load_holdout_roots()
    assert all(per[r]["root_id"] in hr for r in hold)
    assert not any(per[r]["root_id"] in hr for r in dev)


def test_action_repr_maps_cover_corpus_convention():
    maps = EL.load_action_repr_maps()
    # the known duplicate example from the census afterstate map
    m = maps.get("tt_e4_1785205383_867966_p2")
    assert m is not None and m[1149] == 1148 and m[1350] == 1348


def test_deploy_multiplier_shape():
    assert math.isclose(EL.deploy_multiplier(1376), 1.0)
    assert math.isclose(EL.deploy_multiplier(2752),
                        1.0 + EL.TRIGGER_RATE * EL.TILE_SEARCH_SHARE)
    assert EL.deploy_multiplier(13760) < 4.1
