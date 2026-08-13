"""Unit tests for the J-RULES E4-replay calibration instrument's PURE helpers.

`scripts/classical_search/jrules_e4_replay.py` is structured so that arm parsing,
the Wilson interval and the corpus rollup are importable with no
`carcassonne_ai` / `ev_loss` import (those are deferred into `grade_archive`),
which is what lets this file run in milliseconds and never latch the leaf env.

Mirrors `tests/test_opencity_e4_replay.py` in style and coverage, plus two guards
this instrument needs and that one does not:

* `test_wilson_matches_the_opencity_instrument` — the flip rates of the two
  calibrations must be the SAME STATISTIC (the CL-080 anchor is quoted against
  this ladder), so the interval is pinned against the open-city module's, value
  for value, rather than merely "looking right".
* `test_mask_constants_match_flat_leaf` — the mask validator carries a MIRROR of
  `flat_leaf.JR_ALL`, so it must be pinned against the real bits or a rule added
  to the bundle would leave this script rejecting a legitimate mask.

No searches, no archives, no engine: everything else here is arithmetic and dicts.
"""
from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_MOD_PATH = REPO / "scripts" / "classical_search" / "jrules_e4_replay.py"
_OC_PATH = REPO / "scripts" / "classical_search" / "opencity_e4_replay.py"


def _load(path=_MOD_PATH, name="jrules_e4_replay"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


jr = _load()


def test_module_imports_without_carcassonne_ai():
    """The whole point of the import placement: the pure helpers are free.

    Checked in a SUBPROCESS. Asserting on this process's `sys.modules` would be testing
    the whole pytest session rather than this module — any sibling test file that imports
    `carcassonne_ai` (e.g. tests/test_jrules_term.py) makes the assertion fail purely on
    collection order, which is the import-order-pollution artifact tests/conftest.py
    already exists to work around. A fresh interpreter tests the real property."""
    src = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('jr', r'{_MOD_PATH}')\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "sys.modules['jr'] = mod\n"
        "spec.loader.exec_module(mod)\n"
        "mod.parse_arms(mod.DEFAULT_ARM_SPECS)\n"       # the pure path must stay free too
        "mod.wilson_ci(157, 1556)\n"
        "assert 'carcassonne_ai' not in sys.modules, 'importing the module pulled "
        "carcassonne_ai'\n"
        "assert 'ev_loss' not in sys.modules, 'importing the module pulled ev_loss'\n"
        "print('CLEAN')\n")
    p = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True,
                       timeout=300)
    assert p.returncode == 0, p.stderr
    assert "CLEAN" in p.stdout


# --------------------------------------------------------------------------- #
# parse_arm / parse_arms                                                       #
# --------------------------------------------------------------------------- #
def test_default_ladder_parses_to_the_preregistered_rungs():
    arms = jr.parse_arms(jr.DEFAULT_ARM_SPECS)
    assert len(arms) == 3
    assert [a.name for a in arms] == ["d0p5", "d1p0", "d2p0"]
    # CALIB_READ_RULE §1 / DESIGN §7: ladder {0.5, 1.0, 2.0}, mask held at JR_ALL.
    assert [a.dose for a in arms] == [0.5, 1.0, 2.0]
    assert {a.mask for a in arms} == {31}


def test_default_ladder_names_and_knobs_are_unique():
    arms = jr.parse_arms(jr.DEFAULT_ARM_SPECS)
    assert len({a.name for a in arms}) == 3
    assert len({(a.dose, a.mask) for a in arms}) == 3


def test_finer_rung_is_a_valid_arm_at_dose_0p25():
    """CALIB_READ_RULE §3.1's pre-committed rung must actually parse."""
    arm = jr.parse_arm(jr.FINER_RUNG_ARM_SPEC)
    assert (arm.dose, arm.mask) == (0.25, 31)
    assert jr.FINER_RUNG_ARM_SPEC not in jr.DEFAULT_ARM_SPECS   # measured only on trigger


def test_arm_spec_round_trips():
    for spec in (*jr.DEFAULT_ARM_SPECS, jr.FINER_RUNG_ARM_SPEC, "j6only:1.0:8"):
        arm = jr.parse_arm(spec)
        assert jr.parse_arm(arm.spec()) == arm


def test_mask_is_optional_and_defaults_to_jr_all():
    assert jr.parse_arm("d1p0:1.0") == jr.parse_arm("d1p0:1.0:31")
    assert jr.parse_arm("d1p0:1.0").mask == jr.JR_ALL == 31
    assert jr.DEFAULT_MASK == 31


def test_arm_as_dict_shape():
    assert jr.parse_arm("d0p5:0.5:31").as_dict() == {"name": "d0p5", "dose": 0.5,
                                                     "mask": 31}


def test_mask_rules_names_the_enabled_rules():
    assert jr.mask_rules(31) == ["J1", "J2", "J5", "J6", "J8"]
    assert jr.mask_rules(8) == ["J6"]
    assert jr.mask_rules(jr.JR_J1 | jr.JR_J8) == ["J1", "J8"]


def test_mask_constants_match_flat_leaf():
    """The module mirrors `flat_leaf.JR_*` to stay import-free; pin the mirror.

    If a sixth rule is ever added to the bundle, JR_ALL grows and this validator
    would start rejecting the new legitimate mask — this test fails first."""
    from carcassonne_ai import flat_leaf
    assert (jr.JR_J1, jr.JR_J2, jr.JR_J5, jr.JR_J6, jr.JR_J8) == (
        flat_leaf.JR_J1, flat_leaf.JR_J2, flat_leaf.JR_J5, flat_leaf.JR_J6,
        flat_leaf.JR_J8)
    assert jr.JR_ALL == flat_leaf.JR_ALL == 31


def test_ablation_masks_accepted():
    for spec in ("a:1.0:1", "b:1.0:16", "c:1.0:0x1f", "d:1.0:30"):
        assert jr.parse_arm(spec).dose == 1.0


def test_duplicate_names_rejected():
    with pytest.raises(ValueError, match="duplicate arm NAME"):
        jr.parse_arms(["a:0.5:31", "a:1.0:31"])


def test_duplicate_knobs_rejected_even_under_different_names():
    with pytest.raises(ValueError, match="duplicates the knobs"):
        jr.parse_arms(["a:0.5:31", "b:0.5:31"])
    # ... and the implicit default mask counts as the same cell as an explicit 31.
    with pytest.raises(ValueError, match="duplicates the knobs"):
        jr.parse_arms(["a:0.5", "b:0.5:31"])


def test_dose_zero_rejected_and_says_it_is_the_champion_arm():
    with pytest.raises(ValueError) as e:
        jr.parse_arm("a:0")
    msg = str(e.value)
    assert "DOSE must be > 0" in msg
    assert "champion" in msg.lower()


def test_negative_dose_rejected():
    with pytest.raises(ValueError, match="DOSE must be > 0"):
        jr.parse_arm("a:-0.5:31")


def test_mask_zero_rejected_as_the_silent_null():
    with pytest.raises(ValueError) as e:
        jr.parse_arm("a:1.0:0")
    msg = str(e.value)
    assert "MASK must be non-zero" in msg
    assert "null" in msg.lower()


def test_mask_bits_outside_jr_all_rejected():
    with pytest.raises(ValueError, match="outside JR_ALL"):
        jr.parse_arm("a:1.0:32")
    with pytest.raises(ValueError, match="outside JR_ALL"):
        jr.parse_arm("a:1.0:63")
    with pytest.raises(ValueError):
        jr.parse_arm("a:1.0:-1")


@pytest.mark.parametrize("bad", [
    "",                    # empty
    "   ",                 # blank
    "a",                   # too few fields
    "a:1.0:31:9",          # too many fields
    "a:x:31",              # non-numeric dose
    "a:1.0:y",             # non-numeric mask
    "a:1.0:2.5",           # mask must be an int
    ":1.0:31",             # empty name
    "a b:1.0:31",          # whitespace in name
    "a:nan:31",            # non-finite
    "a:inf",               # non-finite
])
def test_garbage_rejected(bad):
    with pytest.raises(ValueError):
        jr.parse_arm(bad)


def test_empty_arm_list_rejected():
    with pytest.raises(ValueError, match="no arms"):
        jr.parse_arms([])
    with pytest.raises(ValueError, match="no arms"):
        jr.parse_arms(None)


def test_non_string_arm_rejected():
    with pytest.raises(ValueError):
        jr.parse_arm(1.0)


# --------------------------------------------------------------------------- #
# wilson_ci                                                                    #
# --------------------------------------------------------------------------- #
def test_wilson_matches_the_opencity_instrument():
    """SAME STATISTIC, mechanically: value-for-value against the open-city module.

    The read-rule compares this ladder's rates directly to CL-080's 10.09% /
    18.89%, which is only legitimate if the interval arithmetic is identical."""
    oc = _load(_OC_PATH, "opencity_e4_replay_for_jrules_test")
    assert jr.Z95 == oc.Z95
    for n in (0, 1, 20, 100, 1079, 1556):
        for k in range(0, n + 1, max(1, n // 7)):
            assert jr.wilson_ci(k, n) == oc.wilson_ci(k, n)


def test_wilson_brackets_the_cl080_anchor_rates():
    """CL-080: open-city's funded arms flipped 10.09% and 18.89% (n=1556)."""
    for f in (0.1009, 0.1889):
        n = 1556
        k = round(f * n)
        lo, hi = jr.wilson_ci(k, n)
        assert lo < k / n < hi
        assert (hi - lo) / 2.0 < 0.03      # the corpus resolves these to ~±2pp


def test_wilson_zero_successes_has_zero_lower_bound_and_nonzero_upper():
    lo, hi = jr.wilson_ci(0, 1556)
    assert lo == 0.0
    assert 0.0 < hi < 0.01


def test_wilson_all_successes_upper_bound_is_one():
    lo, hi = jr.wilson_ci(1556, 1556)
    assert hi == pytest.approx(1.0)
    assert 0.99 < lo < 1.0


def test_wilson_lower_bound_is_the_conservative_side_of_the_bar():
    """CALIB_READ_RULE §2: the BAR is read on the point estimate (the open-city
    convention, inherited unchanged); the Wilson lower bound is reported alongside
    and is by construction the conservative side, so a rung can clear the bar with
    its lower bound below it — the readout flags that as `marginal`."""
    n, k = 1556, round(0.10 * 1556)
    lo, hi = jr.wilson_ci(k, n)
    assert lo < k / n < hi
    assert lo < 0.10 < hi


def test_wilson_symmetry_of_success_and_failure():
    lo_k, hi_k = jr.wilson_ci(120, 1000)
    lo_c, hi_c = jr.wilson_ci(880, 1000)
    assert lo_k == pytest.approx(1.0 - hi_c)
    assert hi_k == pytest.approx(1.0 - lo_c)


def test_wilson_half_of_n_is_centred_on_one_half():
    lo, hi = jr.wilson_ci(500, 1000)
    assert (lo + hi) / 2.0 == pytest.approx(0.5)


def test_wilson_narrows_with_n():
    def half(k, n):
        lo, hi = jr.wilson_ci(k, n)
        return hi - lo
    assert half(50, 1000) < half(5, 100) < half(1, 20)


def test_wilson_bounds_are_in_the_unit_interval():
    for n in (1, 7, 100, 1556):
        for k in range(0, n + 1, max(1, n // 5)):
            lo, hi = jr.wilson_ci(k, n)
            assert 0.0 <= lo <= hi <= 1.0
            assert math.isfinite(lo) and math.isfinite(hi)


def test_wilson_n_zero_is_the_vacuous_interval():
    assert jr.wilson_ci(0, 0) == (0.0, 1.0)


def test_wilson_rejects_impossible_counts():
    with pytest.raises(ValueError):
        jr.wilson_ci(5, 4)
    with pytest.raises(ValueError):
        jr.wilson_ci(-1, 10)
    with pytest.raises(ValueError):
        jr.wilson_ci(0, -3)


# --------------------------------------------------------------------------- #
# the rollup                                                                   #
# --------------------------------------------------------------------------- #
_ARMS_STAMP = [
    {"name": "d0p5", "dose": 0.5, "mask": 31, "rules": ["J1", "J2", "J5", "J6", "J8"],
     "leaf_hash": "aaaa000000000001"},
    {"name": "d1p0", "dose": 1.0, "mask": 31, "rules": ["J1", "J2", "J5", "J6", "J8"],
     "leaf_hash": "bbbb000000000002"},
]


def _game(archive, profile, n_graded, flips, *, agrees=0, match=True,
          phases=None, sims=1376, k_dets=8):
    """A synthetic per-game summary in the shape `grade_archive` writes."""
    phases = phases or {}
    flip_plies = {}
    for name, k in flips.items():
        ph = phases.get(name, ["tiles"] * k)
        flip_plies[name] = [{"ply": 2 * i, "phase": ph[i], "k_remaining": 30 - i,
                             "champ_pick": 10 + i, f"pick_{name}": 20 + i}
                            for i in range(k)]
    return {
        "schema": jr.SCHEMA,
        "archive": archive,
        "rules_profile": profile,
        "human_player": 0,
        "recorded_scores": [80, 75],
        "replay_scores_match": match,
        "partial": False,
        "budget": {"sims_per_det": sims, "k_dets": k_dets,
                   "total_per_decision": sims * k_dets, "source": "archive"},
        "arms": _ARMS_STAMP,
        "leaf_hash_production": jr.LEAF_HASH_OF_RECORD,
        "n_graded": n_graded,
        "champ_agrees_archive": agrees,
        "flips": flips,
        "flip_plies": flip_plies,
    }


def _write(tmp_path, games):
    for g in games:
        (tmp_path / f"game_{Path(g['archive']).stem}.json").write_text(json.dumps(g))
    return tmp_path


def test_rollup_totals_rates_and_wilson(tmp_path):
    games = [
        _game("g1.json", "fixed_v1", 60, {"d0p5": 3, "d1p0": 9}, agrees=40),
        _game("g2.json", "walled", 40, {"d0p5": 1, "d1p0": 5}, agrees=25),
    ]
    _write(tmp_path, games)
    roll = jr.rollup(tmp_path)

    assert roll["n_games"] == 2
    assert roll["n_graded_plies"] == 100
    assert roll["flips_total"] == {"d0p5": 4, "d1p0": 14}
    assert roll["flip_rate"]["d0p5"] == pytest.approx(0.04)
    assert roll["flip_rate"]["d1p0"] == pytest.approx(0.14)
    assert roll["arms"]["d0p5"]["n_graded"] == 100
    assert roll["champ_agrees_archive"] == 65
    assert roll["champ_agrees_archive_rate"] == pytest.approx(0.65)

    for name, k in (("d0p5", 4), ("d1p0", 14)):
        lo, hi = roll["arms"][name]["wilson95"]
        assert (lo, hi) == jr.wilson_ci(k, 100)
        assert lo < k / 100 < hi
        assert roll["arms"][name]["wilson95_lo"] == lo

    # SUMMARY.json on disk is the artifact; it must match what we returned.
    assert json.loads((tmp_path / "SUMMARY.json").read_text()) == roll


def test_rollup_profile_histogram(tmp_path):
    games = [
        _game("g1.json", "fixed_v1", 10, {"d0p5": 1, "d1p0": 2}),
        _game("g2.json", "fixed_v1", 10, {"d0p5": 0, "d1p0": 1}),
        _game("g3.json", "walled", 10, {"d0p5": 1, "d1p0": 1}),
        _game("g4.json", "app_aug2", 10, {"d0p5": 0, "d1p0": 0}),
    ]
    _write(tmp_path, games)
    roll = jr.rollup(tmp_path)
    assert roll["rules_profile_histogram"] == {"fixed_v1": 2, "walled": 1,
                                               "app_aug2": 1}


def test_rollup_flags_a_single_replay_mismatch(tmp_path, capsys):
    games = [
        _game("g1.json", "fixed_v1", 10, {"d0p5": 1, "d1p0": 1}),
        _game("g2.json", "fixed_v1", 10, {"d0p5": 1, "d1p0": 1}, match=False),
        _game("g3.json", "walled", 10, {"d0p5": 0, "d1p0": 0}),
    ]
    _write(tmp_path, games)
    roll = jr.rollup(tmp_path)
    assert roll["all_replay_scores_match"] is False
    assert roll["replay_scores_mismatch_archives"] == ["g2.json"]
    assert roll["replay_scores_match"] == {"g1.json": True, "g2.json": False,
                                           "g3.json": True}
    assert "WARNING" in capsys.readouterr().out


def test_rollup_all_clean_replays(tmp_path):
    _write(tmp_path, [_game("g1.json", "fixed_v1", 10, {"d0p5": 1, "d1p0": 1})])
    roll = jr.rollup(tmp_path)
    assert roll["all_replay_scores_match"] is True
    assert roll["replay_scores_mismatch_archives"] == []


def test_rollup_treats_an_unchecked_partial_replay_as_not_clean(tmp_path):
    g = _game("g1.json", "fixed_v1", 6, {"d0p5": 1, "d1p0": 1}, match=None)
    g["partial"] = True
    _write(tmp_path, [g])
    roll = jr.rollup(tmp_path)
    assert roll["all_replay_scores_match"] is False
    assert roll["replay_scores_mismatch_archives"] == ["g1.json"]


def test_rollup_phase_split(tmp_path):
    games = [
        _game("g1.json", "fixed_v1", 20, {"d0p5": 4, "d1p0": 2},
              phases={"d0p5": ["tiles", "tiles", "tiles", "meeples"],
                      "d1p0": ["meeples", "meeples"]}),
        _game("g2.json", "fixed_v1", 20, {"d0p5": 2, "d1p0": 2},
              phases={"d0p5": ["tiles", "meeples"],
                      "d1p0": ["tiles", "tiles"]}),
    ]
    _write(tmp_path, games)
    roll = jr.rollup(tmp_path)
    a = roll["arms"]["d0p5"]["phase_split"]
    b = roll["arms"]["d1p0"]["phase_split"]
    assert (a["tiles"], a["meeples"]) == (4, 2)
    assert a["tile_share"] == pytest.approx(4 / 6)
    assert (b["tiles"], b["meeples"]) == (2, 2)
    assert b["tile_share"] == pytest.approx(0.5)


def test_rollup_carries_budget_and_arm_knobs(tmp_path):
    _write(tmp_path, [
        _game("g1.json", "fixed_v1", 10, {"d0p5": 1, "d1p0": 1}, sims=1376, k_dets=8),
        _game("g2.json", "walled", 10, {"d0p5": 0, "d1p0": 0}, sims=344, k_dets=4),
    ])
    roll = jr.rollup(tmp_path)
    assert roll["budget_by_archive"]["g1.json"]["total_per_decision"] == 11008
    assert roll["budget_by_archive"]["g2.json"]["total_per_decision"] == 1376
    assert roll["arm_knobs"]["d0p5"]["leaf_hash"] == "aaaa000000000001"
    assert roll["arm_knobs"]["d1p0"]["dose"] == 1.0
    assert roll["arm_knobs"]["d1p0"]["mask"] == 31
    assert roll["jrules_masks"] == [31]


def test_rollup_arm_order_is_first_seen(tmp_path):
    _write(tmp_path, [_game("g1.json", "fixed_v1", 10, {"d1p0": 1, "d0p5": 1})])
    roll = jr.rollup(tmp_path)
    # `arms` stamp order wins over dict insertion order of `flips`.
    assert list(roll["flip_rate"]) == ["d0p5", "d1p0"]


def test_rollup_of_empty_dir_is_empty(tmp_path):
    assert jr.rollup(tmp_path) == {}
    assert not (tmp_path / "SUMMARY.json").exists()


def test_rollup_from_summaries_is_pure(tmp_path):
    """The rollup arithmetic is available with no filesystem at all."""
    games = [_game("g1.json", "fixed_v1", 50, {"d0p5": 5, "d1p0": 10})]
    roll = jr.rollup_from_summaries(games)
    assert roll["flip_rate"]["d0p5"] == pytest.approx(0.10)
    assert roll["flip_rate"]["d1p0"] == pytest.approx(0.20)
    assert not list(tmp_path.iterdir())


def test_rollup_zero_graded_plies_reports_none_not_a_crash():
    roll = jr.rollup_from_summaries([_game("g1.json", "fixed_v1", 0,
                                           {"d0p5": 0, "d1p0": 0})])
    assert roll["flip_rate"]["d0p5"] is None
    assert roll["champ_agrees_archive_rate"] is None
    assert roll["arms"]["d0p5"]["wilson95"] == [0.0, 1.0]


def test_rollup_reports_every_mask_actually_used(tmp_path):
    """An ablation run must be distinguishable from the pre-registered ladder."""
    g = _game("g1.json", "fixed_v1", 10, {"d0p5": 1, "d1p0": 1})
    g["arms"] = [dict(_ARMS_STAMP[0]), {**_ARMS_STAMP[1], "mask": 8, "rules": ["J6"]}]
    _write(tmp_path, [g])
    roll = jr.rollup(tmp_path)
    assert roll["jrules_masks"] == [8, 31]
    assert roll["arm_knobs"]["d1p0"]["rules"] == ["J6"]
