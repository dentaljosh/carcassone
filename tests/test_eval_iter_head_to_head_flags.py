"""Tests for the per-side LeafConfig override helpers in
`scripts/eval_iter_head_to_head.py`.

Specifically: `_apply_leaf_cap` (added 2026-05-20 for the cap A/B sweep) and
its interaction with `_apply_value_blend` + `_leaf_config_for`. These three
helpers compose the LeafConfig handed to each worker pool, so they need to
chain cleanly and be no-ops when their flag is None / 0.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_iter_head_to_head.py"


@pytest.fixture(scope="module")
def eval_mod():
    spec = importlib.util.spec_from_file_location("eval_iter_head_to_head", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_iter_head_to_head"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_apply_leaf_cap_overrides_both_caps(eval_mod):
    cfg = eval_mod._apply_leaf_cap(eval_mod._leaf_config_for("v2_7"), 20.0)
    assert cfg.bonus_cap == 20.0
    assert cfg.opp_bonus_cap == 20.0


def test_apply_leaf_cap_preserves_other_variant_fields(eval_mod):
    cfg = eval_mod._apply_leaf_cap(eval_mod._leaf_config_for("tile_counting"), 8.0)
    assert cfg.bonus_cap == 8.0
    assert cfg.tile_counting_closure is True


@pytest.mark.parametrize("cap", [None, 0, -1, 0.0])
def test_apply_leaf_cap_noop_when_unset(eval_mod, cap):
    # None / 0 / negative cap → return cfg unchanged (possibly None)
    assert eval_mod._apply_leaf_cap(None, cap) is None
    base = eval_mod._leaf_config_for("v2_7")
    assert eval_mod._apply_leaf_cap(base, cap) is base


def test_apply_leaf_cap_chains_with_value_blend(eval_mod):
    # Both apply_value_blend and apply_leaf_cap should compose without
    # clobbering each other.
    cfg = eval_mod._apply_leaf_cap(
        eval_mod._apply_value_blend(eval_mod._leaf_config_for("v2_7"), 0.5),
        15.0,
    )
    assert cfg.value_blend == 0.5
    assert cfg.bonus_cap == 15.0
    assert cfg.opp_bonus_cap == 15.0


def test_apply_leaf_cap_from_none_builds_from_default(eval_mod):
    # When the input cfg is None (v2_7 variant), apply_leaf_cap must still
    # produce a usable LeafConfig — it builds from DEFAULT_CONFIG.
    cfg = eval_mod._apply_leaf_cap(None, 12.0)
    assert cfg is not None
    assert cfg.bonus_cap == 12.0
    assert cfg.opp_bonus_cap == 12.0


def test_env_var_enables_tile_counting_via_default_config(eval_mod, monkeypatch):
    # CARCASSONNE_V25_TILE_COUNTING=1 should make DEFAULT_CONFIG's
    # tile_counting_closure True at next import. Spot-check the wiring by
    # re-running _config_from_env directly (the module-level DEFAULT_CONFIG
    # is set at import time and frozen).
    monkeypatch.setenv("CARCASSONNE_V25_TILE_COUNTING", "1")
    from carcassonne_ai.virtual_score_v2 import _config_from_env
    cfg = _config_from_env()
    assert cfg.tile_counting_closure is True
