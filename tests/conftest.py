"""Test-infra only (leaf-rewrite branch). Lets the WHOLE suite run under the
compact-leaf path so we can prove `pytest green with the toggle ON` — set
CARC_TEST_COMPACT_LEAF=1. No effect on production (default OFF, never imported by
runtime code)."""
import dataclasses as dc
import os
import sys

import pytest


def pytest_configure(config):
    if os.environ.get("CARC_TEST_COMPACT_LEAF") == "1":
        from carcassonne_ai import virtual_score as _vs

        _vs.USE_COMPACT_LEAF = True
        print("\n[conftest] USE_COMPACT_LEAF forced ON for this session")


# ---------------------------------------------------------------------------
# DEFAULT_CONFIG cross-module isolation (import-order pollution guard)
# ---------------------------------------------------------------------------
# virtual_score_v2.DEFAULT_CONFIG is built ONCE, at first import, from the
# CARCASSONNE_V25_*/V29_*/V28_* env. Sibling test modules that pin the frozen
# v2.9 leaf path (test_measurement_infra, test_probe_a_feature_emit) set those
# vars via os.environ.setdefault AT IMPORT — so whichever module wins the
# DEFAULT_CONFIG build race decides the session-global default. In the full
# suite the frozen-v2.9 env wins, baking cap8 + the v2.9 meeple curve into the
# global default. Modules that assert the *bare* production default (no leaf-
# shape env) then fail purely on import order — an isolation artifact, NOT a
# leaf regression (each passes in isolation). This autouse fixture rebuilds a
# bare DEFAULT_CONFIG from a leaf-shape-cleared env for exactly those modules
# and monkeypatches it (auto-restored per test), so the frozen-v2.9 consumers
# are untouched. It does NOT change any leaf semantics.
_BARE_DEFAULT_CONFIG_MODULES = frozenset({
    "test_v29_variants",
    "test_v29_flat_curve",
    "test_retune_parser",
    "test_frozen_substrates",
})

# Every leaf-shape env var _config_from_env() consults; cleared so the rebuilt
# DEFAULT_CONFIG is the true no-env production default (cap5, 3-open, no curve).
_LEAF_SHAPE_ENV = (
    "CARCASSONNE_V25_ONE_OPEN_ONLY", "CARCASSONNE_V25_DROP_THREE_OPEN",
    "CARCASSONNE_V25_CAP", "CARCASSONNE_V25_OPP_CAP", "CARCASSONNE_V25_MEEPLE_K",
    "CARCASSONNE_V25_VALUE_BLEND", "CARCASSONNE_V25_RESIDUAL_SCALE",
    "CARCASSONNE_V25_TILE_COUNTING", "CARCASSONNE_V25_CLOSURE_SLACK",
    "CARCASSONNE_V29_MEEPLE_CURVE",
    "CARCASSONNE_V28_FARM_MAJORITY", "CARCASSONNE_V28_MEEPLE_K",
    "CARCASSONNE_V28_MEEPLE_RECOVERY_T0", "CARCASSONNE_V210_BAG_CLOSE",
)


@pytest.fixture(autouse=True)
def _isolate_bare_default_config(request, monkeypatch):
    """For modules asserting the bare production leaf default, rebuild
    DEFAULT_CONFIG from a leaf-shape-cleared env and patch it (plus each
    module's derived V28 baseline) so the assertions are import-order robust."""
    mod_name = request.module.__name__.rsplit(".", 1)[-1]
    if mod_name not in _BARE_DEFAULT_CONFIG_MODULES:
        return
    from carcassonne_ai import virtual_score_v2 as vs

    for k in _LEAF_SHAPE_ENV:
        monkeypatch.delenv(k, raising=False)
    bare = vs._config_from_env()
    v28 = dc.replace(bare, meeple_k=2.0)  # the shared "v2.8 baseline" the retune builds on

    # Patch the global (drives the cfg=None leaf path), the test module, and the
    # retune harness module (candidate_cfg builds every candidate off its V28).
    targets = [vs, request.module]
    ev = sys.modules.get("eval_v29_vs_v28")
    if ev is not None:
        targets.append(ev)
    for t in targets:
        if hasattr(t, "DEFAULT_CONFIG"):
            monkeypatch.setattr(t, "DEFAULT_CONFIG", bare, raising=False)
        if hasattr(t, "V28"):
            monkeypatch.setattr(t, "V28", v28, raising=False)
