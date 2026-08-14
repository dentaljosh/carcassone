"""Contract tests for the k-width / determinization pre-gate instrument
(scripts/tiletie/kwidth_ladder.py; measurement/kwidth_ties_20260814/).

Pure arithmetic + corpus-metadata contracts — no engine import, no search.
The statistical routines themselves (pick resolution, honest regret, oracle
loading) are IMPORTED from escalation_ladder and are covered by
tests/test_tieescalation.py; what is tested here is what this instrument adds:
the rung table, the iso-budget invariant, and the READ_RULE §5 adjudicator."""
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import kwidth_ladder as KL  # noqa: E402

MEAS = REPO / "measurement" / "kwidth_ties_20260814"


# --------------------------------------------------------------------------- #
# the frozen rung table (READ_RULE §2)                                         #
# --------------------------------------------------------------------------- #
def test_rung_table_is_the_committed_one():
    assert [r[0] for r in KL.RUNGS] == ["R0", "R1", "R2", "R3", "C1", "C2"]
    assert KL.rung_by_id("R0")[1:3] == (8, 1376)
    assert KL.rung_by_id("R3")[1:3] == (64, 1376)
    assert KL.rung_by_id("C2")[1:3] == (32, 344)


def test_expansion_rungs_hold_sims_per_det_fixed():
    """The ONE axis that changes vs the vart: k scales, sims/det does not."""
    exp = [r for r in KL.RUNGS if r[3] in ("base", "expansion")]
    assert {r[2] for r in exp} == {1376}
    assert [r[1] for r in exp] == [8, 16, 32, 64]


def test_isobudget_rungs_are_exactly_the_champion_budget():
    """The design's load-bearing invariant: the controls cost the SAME as the
    champion of record, so a capture there is allocation, not budget."""
    for r in KL.RUNGS:
        if r[3] == "isobudget":
            assert r[1] * r[2] == KL.BASE_TOTAL == 11008, r


def test_deploy_multiplier_is_exactly_one_for_isobudget():
    for r in KL.RUNGS:
        if r[3] == "isobudget":
            assert math.isclose(KL.deploy_multiplier(r[0]), 1.0)
    assert KL.deploy_multiplier("R1") > 1.0
    assert KL.deploy_multiplier("R3") > KL.deploy_multiplier("R2")


def test_rung_key_encodes_the_full_config():
    assert KL.rung_key(32, 344) == "k32x344"
    assert KL.rung_key(16, 688) != KL.rung_key(16, 1376)


def test_bars_match_the_vart_unchanged():
    import escalation_ladder as EL
    assert KL.BAR_CAPTURE_RATIO == EL.BAR_CAPTURE_RATIO == 0.35
    assert KL.BAR_Z == EL.BAR_Z == 2.0
    assert KL.BAR_COVERAGE == EL.BAR_COVERAGE == 0.85


# --------------------------------------------------------------------------- #
# the adjudicator (READ_RULE §5)                                               #
# --------------------------------------------------------------------------- #
def _stat(rid_, capture, se, coverage=0.95):
    _, k, s, klass = KL.rung_by_id(rid_)
    return {"id": rid_, "k_dets": k, "sims_per_det": s, "total_sims": k * s,
            "class": klass, "mean_capture": capture, "se": se,
            "z": capture / se, "coverage": coverage, "n_base_resolved": 500}


def _table(**overrides):
    base = {"R0": _stat("R0", 0.0, 0.05),
            "R1": _stat("R1", 0.0, 0.05),
            "R2": _stat("R2", 0.0, 0.05),
            "R3": _stat("R3", 0.0, 0.05),
            "C1": _stat("C1", 0.0, 0.05),
            "C2": _stat("C2", 0.0, 0.05)}
    base.update(overrides)
    return base


DENOM = 0.28


def test_flat_when_nothing_clears():
    v = KL.adjudicate(_table(), {}, 522, DENOM)
    assert v["branch"] == "W-FLAT"


def test_harmful_beats_flat():
    t = _table(R2=_stat("R2", -0.20, 0.05))
    v = KL.adjudicate(t, {}, 522, DENOM)
    assert v["branch"] == "W-HARMFUL"
    assert v["why"]["harmful_rungs"] == ["R2"]


def test_unreadable_beats_everything():
    t = _table(C2=_stat("C2", 0.20, 0.05))
    v = KL.adjudicate(t, {"checksum_error": 1}, 522, DENOM)
    assert v["branch"] == "W-0 UNREADABLE"


def test_budget_only_when_only_the_expensive_rung_captures():
    """The reading the vart already killed: budget in width's clothing."""
    t = _table(R2=_stat("R2", 0.20, 0.05))          # ratio 0.71, z 4.0
    v = KL.adjudicate(t, {}, 522, DENOM)
    assert v["branch"] == "W-BUDGET-ONLY"
    assert v["attribution"] == "BUDGET"
    assert v["named_rung"] == "R2"


def test_fund_worlds_when_an_isobudget_rung_clears():
    t = _table(R2=_stat("R2", 0.20, 0.05), C2=_stat("C2", 0.18, 0.05))
    v = KL.adjudicate(t, {}, 522, DENOM)
    assert v["branch"] == "W-FUND-WORLDS"
    assert v["attribution"] == "WORLDS"
    assert v["iso_budget_clearing"] == ["C2"]
    # smallest TOTAL budget among clearers -> the 11,008 control, not R2
    assert v["named_rung"] == "C2"


def test_named_rung_ties_break_toward_smaller_k():
    t = _table(C1=_stat("C1", 0.18, 0.05), C2=_stat("C2", 0.18, 0.05))
    v = KL.adjudicate(t, {}, 522, DENOM)
    assert v["branch"] == "W-FUND-WORLDS"
    assert v["named_rung"] == "C1"


def test_ambig_when_isobudget_is_positive_but_underpowered():
    t = _table(R2=_stat("R2", 0.20, 0.05), C2=_stat("C2", 0.08, 0.05))
    v = KL.adjudicate(t, {}, 522, DENOM)          # C2 z = 1.6 > 1.0, does not clear
    assert v["branch"] == "W-FUND-AMBIG"
    assert v["attribution"] == "UNSEPARATED"


def test_coverage_floor_blocks_a_clear():
    t = _table(C2=_stat("C2", 0.20, 0.05, coverage=0.60))
    v = KL.adjudicate(t, {}, 522, DENOM)
    assert v["branch"] == "W-FLAT"


def test_effect_size_bar_blocks_a_significant_but_small_capture():
    t = _table(C2=_stat("C2", 0.06, 0.02))        # z 3.0 but ratio 0.21 < 0.35
    v = KL.adjudicate(t, {}, 522, DENOM)
    assert v["branch"] == "W-FLAT"


# --------------------------------------------------------------------------- #
# discipline: no holdout code path                                             #
# --------------------------------------------------------------------------- #
def test_instrument_has_no_holdout_code_path():
    src = (REPO / "scripts" / "tiletie" / "kwidth_ladder.py").read_text()
    # the only permitted mentions are the exclusion of holdout roots and prose
    assert "slice_rids(per, \"holdout\")" not in src
    assert "--slice" not in src
    assert "EL.slice_rids(per, \"dev\")" in src


def test_dev_slice_excludes_every_holdout_root():
    import escalation_ladder as EL
    import term_gate as TG
    per = TG.load_per_position()
    hold = EL.load_holdout_roots()
    dev = EL.slice_rids(per, "dev")
    assert dev, "dev slice is empty — corpus missing?"
    assert not any(per[r]["root_id"] in hold for r in dev)


# --------------------------------------------------------------------------- #
# governance: the pre-registration really is pre-registered                    #
# --------------------------------------------------------------------------- #
def test_design_and_read_rule_exist_and_name_the_isobudget_rungs():
    d = (MEAS / "DESIGN.md").read_text()
    rr = (MEAS / "READ_RULE.md").read_text()
    for text in (d, rr):
        assert "11,008" in text
        assert "ISO-BUDGET" in text or "iso-budget" in text
    assert "W-FUND-WORLDS" in rr and "W-BUDGET-ONLY" in rr and "W-FLAT" in rr


def test_readout_json_if_present_carries_the_committed_bars():
    p = MEAS / "LADDER_READOUT.json"
    if not p.is_file():
        return
    r = json.loads(p.read_text())
    assert r["bars"]["capture_ratio"] == 0.35
    assert r["bars"]["z"] == 2.0
    assert r["bars"]["coverage"] == 0.85
    assert "NOT OPENED" in r["holdout"]
