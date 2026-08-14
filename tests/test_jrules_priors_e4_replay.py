"""Pure-helper tests for the surface-B calibration instrument
(`scripts/classical_search/jrules_priors_e4_replay.py`).

Instant by design: nothing here imports `carcassonne_ai` or `carc_rs`, so the
suite runs on a box with no wheel at all. The instrument's own heavy guards
(the positive control, the inverted hash guard, the stale-wheel probe) are
exercised at runtime by `_make_arms` / `_assert_surface_b_live` and smoked via
`--limit-games 1 --limit-plies N`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts" / "classical_search"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import jrules_e4_replay as surface_a  # noqa: E402
import jrules_priors_e4_replay as jp  # noqa: E402


def test_mask_constants_match_flat_leaf():
    for _p in (REPO / "src", REPO / "engine"):
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
    from carcassonne_ai import flat_leaf
    assert (jp.JR_J1, jp.JR_J2, jp.JR_J5, jp.JR_J6, jp.JR_J8, jp.JR_ALL) == (
        flat_leaf.JR_J1, flat_leaf.JR_J2, flat_leaf.JR_J5, flat_leaf.JR_J6,
        flat_leaf.JR_J8, flat_leaf.JR_ALL)


def test_wilson_matches_the_surface_a_instrument():
    """Same statistic, pinned value-for-value — the two ladders must stay
    directly comparable (and both against CL-080's)."""
    for k, n in ((0, 1), (1, 10), (368, 1556), (723, 1556), (5, 5)):
        assert jp.wilson_ci(k, n) == surface_a.wilson_ci(k, n)


def test_default_ladder_matches_surface_a_rungs():
    """The pre-registered doses are surface A's, deliberately, so the ladders
    are comparable; only the arm-tuple SHAPE differs (scope added)."""
    a = [s.split(":")[1] for s in surface_a.DEFAULT_ARM_SPECS]
    b = [s.split(":")[1] for s in jp.DEFAULT_ARM_SPECS]
    assert a == b == ["0.5", "1.0", "2.0"]
    assert jp.FINER_RUNG_ARM_SPEC.split(":")[1] == "0.25"
    assert all(s.endswith(":all") for s in jp.DEFAULT_ARM_SPECS)


def test_parse_arm_round_trips_with_scope():
    a = jp.parse_arm("x:0.5:27:own")
    assert (a.name, a.dose, a.mask, a.scope) == ("x", 0.5, 27, "own")
    assert jp.parse_arm(a.spec()) == a
    # defaults: mask 31, scope all
    d = jp.parse_arm("y:1.0")
    assert (d.mask, d.scope) == (31, "all")


@pytest.mark.parametrize("bad", [
    "x:0",            # dose 0 IS the champion
    "x:-1",           # negative dose
    "x:0.5:0",        # mask 0 enables nothing
    "x:0.5:64",       # bit outside JR_ALL
    "x:0.5:31:both",  # unknown scope
    "x:0.5:31:all:extra",
    ":0.5",
    "",
])
def test_parse_arm_rejects(bad):
    with pytest.raises(ValueError):
        jp.parse_arm(bad)


def test_parse_arms_rejects_duplicate_knobs_but_allows_scope_split():
    with pytest.raises(ValueError):
        jp.parse_arms(["a:0.5:31:all", "b:0.5:31:all"])
    # same dose+mask at a DIFFERENT scope is a legitimate separate cell
    arms = jp.parse_arms(["a:0.5:31:all", "b:0.5:31:own"])
    assert [a.scope for a in arms] == ["all", "own"]


def test_missing_arms_in_resume_flags_the_late_added_arm():
    arms = jp.parse_arms(["a:0.5", "b:1.0"])
    done = [{"ply": 3, "pick_a": 7, "flip_a": False}]
    assert jp.missing_arms_in_resume(done, arms) == ["b"]
    assert jp.missing_arms_in_resume([], arms) == []


def test_schema_is_surface_b_not_surface_a():
    assert jp.SCHEMA == "carcassonne-jrules-priors-e4-replay/v1"
    assert jp.SCHEMA != surface_a.SCHEMA
