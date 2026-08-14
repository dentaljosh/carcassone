"""Pure-helper tests for the surface-C calibration instrument
(`scripts/classical_search/jrules_filter_e4_replay.py`).

Instant by design: nothing here imports `carcassonne_ai` or `carc_rs` at
module scope, so the suite runs on a box with no wheel at all. The
instrument's heavy guards (the positive control, the inverted hash guard, the
stale-wheel probe) are exercised at runtime by `_make_champ` /
`_assert_surface_c_live` and smoked via `--limit-games 1 --limit-plies N`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts" / "classical_search"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import jrules_filter_e4_replay as jfe  # noqa: E402
import jrules_priors_e4_replay as jp  # noqa: E402


def test_mask_constants_match_jrules_filter_module():
    for _p in (REPO / "src", REPO / "engine"):
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
    from carcassonne_ai import jrules_filter as jf

    assert (jfe.JF_END, jfe.JF_J10, jfe.JF_J9, jfe.JF_J3) == \
        (jf.JF_END, jf.JF_J10, jf.JF_J9, jf.JF_J3)
    assert jfe.JF_ALL == jf.JF_ALL == 15
    assert jfe.JF_CURRENT == jf.JF_CURRENT == 11
    assert tuple(jfe.JF_FILTER_NAMES) == tuple(jf.JF_FILTER_NAMES)


def test_wilson_matches_the_surface_b_instrument():
    """Same statistic across the three ladders — value-for-value."""
    for k, n in ((0, 0), (0, 10), (3, 10), (203, 1556), (10, 10)):
        assert jfe.wilson_ci(k, n) == jp.wilson_ci(k, n)


def test_default_ladder_is_the_mask_lattice():
    arms = jfe.parse_arms(jfe.DEFAULT_ARM_SPECS)
    assert [a.name for a in arms] == ["j10", "j3", "current", "all"]
    assert [a.mask for a in arms] == [2, 8, 11, 15]
    assert all(a.min_keep == 1 for a in arms)


def test_parse_arm_round_trips_with_min_keep():
    a = jfe.parse_arm("current:11:2")
    assert a == jfe.Arm(name="current", mask=11, min_keep=2)
    assert jfe.parse_arm(a.spec()) == a
    assert jfe.parse_arm("x:2").min_keep == 1
    assert jfe.mask_filters(11) == ["f_end", "f_j10", "f_j3"]


@pytest.mark.parametrize("bad", [
    "", "noname", "x:0", "x:16", "x:-1", "x:2:0", "x:nan", "x y:2",
])
def test_parse_arm_rejects(bad):
    with pytest.raises(ValueError):
        jfe.parse_arm(bad)


def test_parse_arms_rejects_duplicates():
    with pytest.raises(ValueError, match="duplicate arm NAME"):
        jfe.parse_arms(["a:2", "a:8"])
    with pytest.raises(ValueError, match="duplicates the knobs"):
        jfe.parse_arms(["a:2", "b:2"])
    assert len(jfe.parse_arms(["a:2", "b:2:3"])) == 2   # min_keep splits knobs


def test_missing_arms_in_resume_flags_the_late_added_arm():
    done = [{"ply": 3, "excluded_current": False, "yield_current": False}]
    arms = jfe.parse_arms(["current:11", "all:15"])
    assert jfe.missing_arms_in_resume(done, arms) == ["all"]
    assert jfe.missing_arms_in_resume([], arms) == []


def test_rollup_counts_exclusions_and_yields():
    s = {
        "archive": "g1.json", "rules_profile": "fixed_v1", "n_graded": 50,
        "arms": [{"name": "current", "mask": 11, "min_keep": 1,
                  "filters": ["f_end", "f_j10", "f_j3"], "leaf_hash": "x"}],
        "exclusions": {"current": 5}, "yields": {"current": 1},
        "applicable": {"current": 20},
        "filter_fires": {"current": {"f_j10": 12, "f_j3": 2}},
        "replay_scores_match": True, "champ_agrees_archive": 30,
        "budget": {"sims_per_det": 1376, "k_dets": 8},
    }
    roll = jfe.rollup_from_summaries([s])
    arm = roll["arms"]["current"]
    assert arm["exclusions_total"] == 5
    assert arm["exclusion_rate"] == pytest.approx(0.1)
    assert arm["yield_rate"] == pytest.approx(0.02)
    assert arm["applicable_share"] == pytest.approx(0.4)
    assert arm["filter_fires"] == {"f_j10": 12, "f_j3": 2}
    assert roll["all_replay_scores_match"] is True
    lo, hi = arm["wilson95"]
    assert 0.0 < lo < 0.1 < hi < 1.0


def test_rollup_reports_partial_checksum_as_not_clean():
    s = {"archive": "g1.json", "n_graded": 5, "arms": [],
         "exclusions": {}, "yields": {}, "applicable": {},
         "replay_scores_match": None}
    roll = jfe.rollup_from_summaries([s])
    assert roll["all_replay_scores_match"] is False


def test_schema_is_surface_c():
    assert "jrules-filter" in jfe.SCHEMA
    assert jfe.SCHEMA != jp.SCHEMA
