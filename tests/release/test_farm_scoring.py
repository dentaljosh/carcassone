"""F1 property: dual-farm / same-city TERMINAL scoring — the review's P1-L5 "stop the
line" claim. A completed city adjacent to TWO topologically-distinct fields of ONE player
must score 3+3=6 (not deduped to 3). Adopts the F0a permanent fixture
tests/test_farm_multifield_city_p1l5.py: the release gate re-runs its engine + leaf
assertions so a leaf change that reintroduces the cross-field city dedup fails the audit.
"""
import importlib.util
from pathlib import Path

_F0A = Path(__file__).resolve().parents[1] / "test_farm_multifield_city_p1l5.py"
_spec = importlib.util.spec_from_file_location("_p1l5_fixture", _F0A)
p1l5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p1l5)


def test_engine_pays_six_same_player_two_fields():
    p1l5.test_engine_pays_six_same_player_two_fields()


def test_engine_splits_three_each_different_players():
    p1l5.test_engine_pays_three_each_different_players()


def test_flat_leaf_base_credits_city_twice_same_player():
    p1l5.test_flat_leaf_base_credits_city_twice_same_player()


def test_flat_leaf_base_splits_between_players():
    p1l5.test_flat_leaf_base_splits_between_players()


def test_object_leaf_base_credits_city_twice_same_player():
    p1l5.test_object_leaf_base_credits_city_twice_same_player()


def test_full_production_leaf_reflects_six():
    p1l5.test_full_production_leaf_reflects_six()


def test_growth_anticipation_dedup_is_the_documented_heuristic_choice():
    # The ONLY place the cross-field city dedup lives is the incomplete-city closure-
    # anticipation heuristic (bounded, capped, symmetric) — asserted, not a rule bug.
    p1l5.test_growth_anticipation_dedups_incomplete_city_across_fields()
