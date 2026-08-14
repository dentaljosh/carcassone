"""Test-infra only (leaf-rewrite branch). Lets the WHOLE suite run under the
compact-leaf path so we can prove `pytest green with the toggle ON` — set
CARC_TEST_COMPACT_LEAF=1. No effect on production (default OFF, never imported by
runtime code)."""
import dataclasses as dc
import os
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# rustport import-order contract (the `prod_leaf_env` race)
# ---------------------------------------------------------------------------
# The `scripts/rustport/` gate scripts the parity suite drives — reconcile_engine
# / reconcile_leaf / trace_search / lockstep_fuzz — each `import prod_leaf_env`,
# which REFUSES to load once `carcassonne_ai` is already in sys.modules (it
# shapes the leaf knobs that virtual_score_v2.DEFAULT_CONFIG freezes at ITS
# import).
#
# In a whole-tree run that guard trips on collection ORDER: `tests/android/`
# sorts before `tests/rustport/` and imports `carcassonne_ai` (via
# `android_bridge`) long before rustport is reached, so six rustport modules
# raise RuntimeError while being imported —
#     test_p1_engine  test_p2_leaf  test_p3_search
#     test_p5_flags   test_lockstep_fuzz  test_cloister_scan_fix_parity
# — and because a COLLECTION error aborts the session, `pytest tests/` was
# running ZERO tests, not merely skipping rustport (measured 2026-08-13).
#
# The frozen shape is not actually wrong. `android_bridge` applies the same
# production env, so the DEFAULT_CONFIG a whole-tree run freezes is BYTE-
# IDENTICAL to the one `prod_leaf_env` produces (verified field-by-field
# 2026-08-13, incl. v29_meeple_curve = curve125). The guard is tripping on its
# PROXY — "did I get imported first" — not on the invariant it protects. So the
# fix is to let this conftest legitimately WIN that race: it is imported before
# any test module, so applying the shape here both satisfies the guard and makes
# the session-global leaf shape DETERMINISTIC instead of a side effect of
# `android` happening to sort before `rustport`.
#
# Deliberately NOT a skip/xfail/tolerance change: nothing is relaxed, and the
# rustport modules keep their own `import prod_leaf_env` (a no-op once it is in
# sys.modules).
#
# Scoped to sessions that actually collect tests/rustport, so a standalone
# `pytest tests/test_v29_variants.py` keeps the bare no-env default it asserts.
# sys.path is snapshotted/restored — only the import itself needs scripts/rustport.
def _session_collects_rustport() -> bool:
    rustport = (Path(__file__).parent / "rustport").resolve()
    paths = []
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            continue
        p = Path(arg.split("::")[0])
        if p.exists():
            paths.append(p.resolve())
    if not paths:
        return True  # bare `pytest` / `pytest -k ...` collects the whole tree
    return any(p == rustport or rustport in p.parents or p in rustport.parents
               for p in paths)


if _session_collects_rustport():
    _saved_sys_path = list(sys.path)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "rustport"))
    try:
        import prod_leaf_env  # noqa: F401  (must precede every carcassonne_ai import)
    finally:
        sys.path[:] = _saved_sys_path
        del _saved_sys_path


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
