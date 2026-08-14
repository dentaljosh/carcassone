"""Unit tests for the OPEN-CITY E4-replay calibration instrument's PURE helpers.

`scripts/classical_search/opencity_e4_replay.py` is structured so that arm
parsing, the Wilson interval and the corpus rollup are importable with no
`carcassonne_ai` / `ev_loss` import (those are deferred into `grade_archive`),
which is what lets this file run in milliseconds and never latch the leaf env.

No searches, no archives, no engine: everything here is arithmetic and dicts.
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
_MOD_PATH = REPO / "scripts" / "classical_search" / "opencity_e4_replay.py"


def _load():
    spec = importlib.util.spec_from_file_location("opencity_e4_replay", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


oc = _load()


def test_module_imports_without_carcassonne_ai():
    """The whole point of the import placement: the pure helpers are free.

    Checked in a SUBPROCESS. Asserting on this process's `sys.modules` would be testing
    the whole pytest session rather than this module — any sibling test file that imports
    `carcassonne_ai` (e.g. tests/test_opencity_term.py) makes the assertion fail purely on
    collection order, which is the import-order-pollution artifact tests/conftest.py
    already exists to work around. A fresh interpreter tests the real property."""
    src = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('oc', r'{_MOD_PATH}')\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "sys.modules['oc'] = mod\n"
        "spec.loader.exec_module(mod)\n"
        "mod.parse_arms(mod.DEFAULT_ARM_SPECS)\n"       # the pure path must stay free too
        "mod.wilson_ci(48, 1079)\n"
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
def test_default_ladder_parses_to_the_preregistered_grid():
    arms = oc.parse_arms(oc.DEFAULT_ARM_SPECS)
    assert len(arms) == 6
    assert [a.name for a in arms] == ["A_d0p5", "A_d2p0", "B_d0p5", "B_d2p0",
                                      "C_d0p5", "C_d2p0"]
    # CALIB_READ_RULE §1: A (4,2), B (3,2), C (6,3); doses {0.5, 2.0} in each.
    got = {a.name: (a.size_min, a.edge_min, a.dose) for a in arms}
    assert got["A_d0p5"] == (4.0, 2, 0.5)
    assert got["A_d2p0"] == (4.0, 2, 2.0)
    assert got["B_d0p5"] == (3.0, 2, 0.5)
    assert got["B_d2p0"] == (3.0, 2, 2.0)
    assert got["C_d0p5"] == (6.0, 3, 0.5)
    assert got["C_d2p0"] == (6.0, 3, 2.0)


def test_default_ladder_names_and_knobs_are_unique():
    arms = oc.parse_arms(oc.DEFAULT_ARM_SPECS)
    assert len({a.name for a in arms}) == 6
    assert len({(a.size_min, a.edge_min, a.dose) for a in arms}) == 6


def test_arm_spec_round_trips():
    for spec in oc.DEFAULT_ARM_SPECS:
        arm = oc.parse_arm(spec)
        assert oc.parse_arm(arm.spec()) == arm


def test_arm_as_dict_shape():
    d = oc.parse_arm("A_d0p5:4:2:0.5").as_dict()
    assert d == {"name": "A_d0p5", "size_min": 4.0, "edge_min": 2, "dose": 0.5,
                 "cap": 0.0}


# --- the 5th field: opencity_cap (round-2 capped form, 2026-08-14) ----------- #
def test_arm_cap_parses_round_trips_and_keys_uniqueness():
    a = oc.parse_arm("Acap1_d2p0:4:2:2.0:1")
    assert (a.size_min, a.edge_min, a.dose, a.cap) == (4.0, 2, 2.0, 1.0)
    assert oc.parse_arm(a.spec()) == a
    # omitted cap == explicit 0 == uncapped, and the two specs are the SAME cell
    assert oc.parse_arm("A:4:2:0.5") == oc.parse_arm("A:4:2:0.5:0")
    with pytest.raises(ValueError, match="duplicates the knobs"):
        oc.parse_arms(["A:4:2:0.5", "B:4:2:0.5:0"])
    # a capped and an uncapped arm at the same (size, edge, dose) are DIFFERENT cells
    arms = oc.parse_arms(["A:4:2:0.5", "Acap:4:2:0.5:2"])
    assert len(arms) == 2 and arms[0].cap == 0.0 and arms[1].cap == 2.0
    # uncapped arms keep the CL-080-era 4-field spec string (byte-stable specs)
    assert oc.parse_arm("A_d0p5:4:2:0.5").spec() == "A_d0p5:4:2:0.5"


def test_arm_cap_garbage_rejected():
    with pytest.raises(ValueError, match="CAP must be >= 0"):
        oc.parse_arm("A:4:2:0.5:-1")
    with pytest.raises(ValueError, match="not finite"):
        oc.parse_arm("A:4:2:0.5:inf")
    with pytest.raises(ValueError, match="not a number"):
        oc.parse_arm("A:4:2:0.5:x")
    with pytest.raises(ValueError, match="4 or 5 colon-separated"):
        oc.parse_arm("A:4:2:0.5:1:9")


def test_duplicate_names_rejected():
    with pytest.raises(ValueError, match="duplicate arm NAME"):
        oc.parse_arms(["A:4:2:0.5", "A:3:2:0.5"])


def test_duplicate_knobs_rejected_even_under_different_names():
    with pytest.raises(ValueError, match="duplicates the knobs"):
        oc.parse_arms(["A:4:2:0.5", "B:4:2:0.5"])


def test_dose_zero_rejected_and_says_it_is_the_champion_arm():
    with pytest.raises(ValueError) as e:
        oc.parse_arm("A:4:2:0")
    msg = str(e.value)
    assert "dose 0 IS the champion" in msg.lower() or "DOSE must be > 0" in msg
    assert "champion" in msg.lower()


def test_negative_dose_rejected():
    with pytest.raises(ValueError, match="DOSE must be > 0"):
        oc.parse_arm("A:4:2:-0.5")


def test_edge_min_below_one_rejected():
    with pytest.raises(ValueError, match="EDGE_MIN .* must be >= 1"):
        oc.parse_arm("A:4:0:0.5")
    with pytest.raises(ValueError, match="EDGE_MIN .* must be >= 1"):
        oc.parse_arm("A:4:-1:0.5")


def test_size_min_below_one_rejected():
    with pytest.raises(ValueError, match="SIZE_MIN .* must be >= 1"):
        oc.parse_arm("A:0.5:2:0.5")


@pytest.mark.parametrize("bad", [
    "",                    # empty
    "   ",                 # blank
    "A:4:2",               # too few fields
    "A:4:2:0.5:9:9",       # too many fields (5th is CAP since 2026-08-14; 6 is garbage)
    "A:x:2:0.5",           # non-numeric size_min
    "A:4:y:0.5",           # non-numeric edge_min
    "A:4:2.5:0.5",         # edge_min must be an int
    "A:4:2:z",             # non-numeric dose
    ":4:2:0.5",            # empty name
    "A B:4:2:0.5",         # whitespace in name
    "A:nan:2:0.5",         # non-finite
    "A:4:2:inf",           # non-finite
])
def test_garbage_rejected(bad):
    with pytest.raises(ValueError):
        oc.parse_arm(bad)


def test_empty_arm_list_rejected():
    with pytest.raises(ValueError, match="no arms"):
        oc.parse_arms([])
    with pytest.raises(ValueError, match="no arms"):
        oc.parse_arms(None)


def test_non_string_arm_rejected():
    with pytest.raises(ValueError):
        oc.parse_arm(4)


# --------------------------------------------------------------------------- #
# wilson_ci                                                                    #
# --------------------------------------------------------------------------- #
def test_wilson_brackets_the_denial_arm_a_point_estimate():
    """Denial's production-spec arm: 48/1079 = 4.45% (CALIB_READOUT §2)."""
    lo, hi = oc.wilson_ci(48, 1079)
    f = 48 / 1079
    assert lo < f < hi
    assert f == pytest.approx(0.0445, abs=5e-4)
    assert 0.0 < lo < 0.05
    assert 0.05 < hi < 0.07


def test_wilson_zero_successes_has_zero_lower_bound_and_nonzero_upper():
    lo, hi = oc.wilson_ci(0, 1079)
    assert lo == 0.0
    assert 0.0 < hi < 0.01


def test_wilson_all_successes_upper_bound_is_one():
    lo, hi = oc.wilson_ci(1079, 1079)
    assert hi == pytest.approx(1.0)
    assert 0.99 < lo < 1.0


def test_wilson_half_width_matches_the_read_rule_quoted_values():
    """CALIB_READ_RULE §1 quotes ~±1.3pp at f=5% and ~±1.8pp at f=10%, n≈1079.

    This is a real check on the implementation: a Wald interval would read
    ±1.30pp / ±1.79pp too, but a botched Wilson (wrong z, wrong denominator)
    misses these by far more than the 0.3pp tolerance."""
    n = 1079
    lo5, hi5 = oc.wilson_ci(round(0.05 * n), n)
    half5 = (hi5 - lo5) / 2.0
    assert half5 == pytest.approx(0.013, abs=0.003)

    lo10, hi10 = oc.wilson_ci(round(0.10 * n), n)
    half10 = (hi10 - lo10) / 2.0
    assert half10 == pytest.approx(0.018, abs=0.003)

    # And the interval WIDENS with f in this range, as the read-rule implies.
    assert half10 > half5


def test_wilson_symmetry_of_success_and_failure():
    lo_k, hi_k = oc.wilson_ci(120, 1000)
    lo_c, hi_c = oc.wilson_ci(880, 1000)
    assert lo_k == pytest.approx(1.0 - hi_c)
    assert hi_k == pytest.approx(1.0 - lo_c)


def test_wilson_half_of_n_is_centred_on_one_half():
    lo, hi = oc.wilson_ci(500, 1000)
    assert (lo + hi) / 2.0 == pytest.approx(0.5)


def test_wilson_narrows_with_n():
    def half(k, n):
        lo, hi = oc.wilson_ci(k, n)
        return hi - lo
    assert half(50, 1000) < half(5, 100) < half(1, 20)


def test_wilson_bounds_are_in_the_unit_interval():
    for n in (1, 7, 100, 1079):
        for k in range(0, n + 1, max(1, n // 5)):
            lo, hi = oc.wilson_ci(k, n)
            assert 0.0 <= lo <= hi <= 1.0
            assert math.isfinite(lo) and math.isfinite(hi)


def test_wilson_n_zero_is_the_vacuous_interval():
    assert oc.wilson_ci(0, 0) == (0.0, 1.0)


def test_wilson_rejects_impossible_counts():
    with pytest.raises(ValueError):
        oc.wilson_ci(5, 4)
    with pytest.raises(ValueError):
        oc.wilson_ci(-1, 10)
    with pytest.raises(ValueError):
        oc.wilson_ci(0, -3)


# --------------------------------------------------------------------------- #
# the rollup                                                                   #
# --------------------------------------------------------------------------- #
_ARMS_STAMP = [
    {"name": "A_d0p5", "size_min": 4.0, "edge_min": 2, "dose": 0.5,
     "symmetric": True, "leaf_hash": "aaaa000000000001"},
    {"name": "B_d0p5", "size_min": 3.0, "edge_min": 2, "dose": 0.5,
     "symmetric": True, "leaf_hash": "bbbb000000000002"},
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
        "schema": oc.SCHEMA,
        "archive": archive,
        "rules_profile": profile,
        "human_player": 0,
        "recorded_scores": [80, 75],
        "replay_scores_match": match,
        "partial": False,
        "budget": {"sims_per_det": sims, "k_dets": k_dets,
                   "total_per_decision": sims * k_dets, "source": "archive"},
        "opencity_symmetric": True,
        "arms": _ARMS_STAMP,
        "leaf_hash_production": oc.LEAF_HASH_OF_RECORD,
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
        _game("g1.json", "fixed_v1", 60, {"A_d0p5": 3, "B_d0p5": 9}, agrees=40),
        _game("g2.json", "walled", 40, {"A_d0p5": 1, "B_d0p5": 5}, agrees=25),
    ]
    _write(tmp_path, games)
    roll = oc.rollup(tmp_path)

    assert roll["n_games"] == 2
    assert roll["n_graded_plies"] == 100
    assert roll["flips_total"] == {"A_d0p5": 4, "B_d0p5": 14}
    assert roll["flip_rate"]["A_d0p5"] == pytest.approx(0.04)
    assert roll["flip_rate"]["B_d0p5"] == pytest.approx(0.14)
    assert roll["arms"]["A_d0p5"]["n_graded"] == 100
    assert roll["champ_agrees_archive"] == 65
    assert roll["champ_agrees_archive_rate"] == pytest.approx(0.65)

    for name, k in (("A_d0p5", 4), ("B_d0p5", 14)):
        lo, hi = roll["arms"][name]["wilson95"]
        assert (lo, hi) == oc.wilson_ci(k, 100)
        assert lo < k / 100 < hi

    # SUMMARY.json on disk is the artifact; it must match what we returned.
    assert json.loads((tmp_path / "SUMMARY.json").read_text()) == roll


def test_rollup_profile_histogram(tmp_path):
    games = [
        _game("g1.json", "fixed_v1", 10, {"A_d0p5": 1, "B_d0p5": 2}),
        _game("g2.json", "fixed_v1", 10, {"A_d0p5": 0, "B_d0p5": 1}),
        _game("g3.json", "walled", 10, {"A_d0p5": 1, "B_d0p5": 1}),
        _game("g4.json", "app_aug2", 10, {"A_d0p5": 0, "B_d0p5": 0}),
    ]
    _write(tmp_path, games)
    roll = oc.rollup(tmp_path)
    assert roll["rules_profile_histogram"] == {"fixed_v1": 2, "walled": 1,
                                               "app_aug2": 1}


def test_rollup_flags_a_single_replay_mismatch(tmp_path, capsys):
    games = [
        _game("g1.json", "fixed_v1", 10, {"A_d0p5": 1, "B_d0p5": 1}),
        _game("g2.json", "fixed_v1", 10, {"A_d0p5": 1, "B_d0p5": 1}, match=False),
        _game("g3.json", "walled", 10, {"A_d0p5": 0, "B_d0p5": 0}),
    ]
    _write(tmp_path, games)
    roll = oc.rollup(tmp_path)
    assert roll["all_replay_scores_match"] is False
    assert roll["replay_scores_mismatch_archives"] == ["g2.json"]
    assert roll["replay_scores_match"] == {"g1.json": True, "g2.json": False,
                                           "g3.json": True}
    assert "WARNING" in capsys.readouterr().out


def test_rollup_all_clean_replays(tmp_path):
    _write(tmp_path, [_game("g1.json", "fixed_v1", 10, {"A_d0p5": 1, "B_d0p5": 1})])
    roll = oc.rollup(tmp_path)
    assert roll["all_replay_scores_match"] is True
    assert roll["replay_scores_mismatch_archives"] == []


def test_rollup_treats_an_unchecked_partial_replay_as_not_clean(tmp_path):
    g = _game("g1.json", "fixed_v1", 6, {"A_d0p5": 1, "B_d0p5": 1}, match=None)
    g["partial"] = True
    _write(tmp_path, [g])
    roll = oc.rollup(tmp_path)
    assert roll["all_replay_scores_match"] is False
    assert roll["replay_scores_mismatch_archives"] == ["g1.json"]


def test_rollup_phase_split(tmp_path):
    games = [
        _game("g1.json", "fixed_v1", 20, {"A_d0p5": 4, "B_d0p5": 2},
              phases={"A_d0p5": ["tiles", "tiles", "tiles", "meeples"],
                      "B_d0p5": ["meeples", "meeples"]}),
        _game("g2.json", "fixed_v1", 20, {"A_d0p5": 2, "B_d0p5": 2},
              phases={"A_d0p5": ["tiles", "meeples"],
                      "B_d0p5": ["tiles", "tiles"]}),
    ]
    _write(tmp_path, games)
    roll = oc.rollup(tmp_path)
    a = roll["arms"]["A_d0p5"]["phase_split"]
    b = roll["arms"]["B_d0p5"]["phase_split"]
    assert (a["tiles"], a["meeples"]) == (4, 2)
    assert a["tile_share"] == pytest.approx(4 / 6)
    assert (b["tiles"], b["meeples"]) == (2, 2)
    assert b["tile_share"] == pytest.approx(0.5)


def test_rollup_carries_budget_and_arm_knobs(tmp_path):
    _write(tmp_path, [
        _game("g1.json", "fixed_v1", 10, {"A_d0p5": 1, "B_d0p5": 1},
              sims=1376, k_dets=8),
        _game("g2.json", "walled", 10, {"A_d0p5": 0, "B_d0p5": 0},
              sims=344, k_dets=4),
    ])
    roll = oc.rollup(tmp_path)
    assert roll["budget_by_archive"]["g1.json"]["total_per_decision"] == 11008
    assert roll["budget_by_archive"]["g2.json"]["total_per_decision"] == 1376
    assert roll["arm_knobs"]["A_d0p5"]["leaf_hash"] == "aaaa000000000001"
    assert roll["arm_knobs"]["B_d0p5"]["dose"] == 0.5
    assert roll["opencity_symmetric"] == [True]


def test_rollup_arm_order_is_first_seen(tmp_path):
    _write(tmp_path, [_game("g1.json", "fixed_v1", 10,
                            {"B_d0p5": 1, "A_d0p5": 1})])
    roll = oc.rollup(tmp_path)
    # `arms` stamp order wins over dict insertion order of `flips`.
    assert list(roll["flip_rate"]) == ["A_d0p5", "B_d0p5"]


def test_rollup_of_empty_dir_is_empty(tmp_path):
    assert oc.rollup(tmp_path) == {}
    assert not (tmp_path / "SUMMARY.json").exists()


def test_rollup_from_summaries_is_pure(tmp_path):
    """The rollup arithmetic is available with no filesystem at all."""
    games = [_game("g1.json", "fixed_v1", 50, {"A_d0p5": 5, "B_d0p5": 10})]
    roll = oc.rollup_from_summaries(games)
    assert roll["flip_rate"]["A_d0p5"] == pytest.approx(0.10)
    assert roll["flip_rate"]["B_d0p5"] == pytest.approx(0.20)
    assert not list(tmp_path.iterdir())


def test_rollup_zero_graded_plies_reports_none_not_a_crash():
    roll = oc.rollup_from_summaries([_game("g1.json", "fixed_v1", 0,
                                           {"A_d0p5": 0, "B_d0p5": 0})])
    assert roll["flip_rate"]["A_d0p5"] is None
    assert roll["champ_agrees_archive_rate"] is None
    assert roll["arms"]["A_d0p5"]["wilson95"] == [0.0, 1.0]
