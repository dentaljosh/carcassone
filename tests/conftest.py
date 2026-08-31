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


# ---------------------------------------------------------------------------
# Window-overflow audit latch (the `CARCASSONNE_WINDOW_AUDIT` ordering race)
# ---------------------------------------------------------------------------
# Same failure shape as the block above, different flag. Three rustport modules
# set `os.environ["CARCASSONNE_WINDOW_AUDIT"] = "1"` at import with the comment
# "must precede game_wrapper import" — and standalone that is true and works.
# Under a whole-tree run it is too late: `tests/android/` has already imported
# `game_wrapper`, which latched `_WINDOW_AUDIT` from the env AT ITS import, so
# the assignment lands after the latch and the audit stays OFF. The lockstep
# drivers then read zero audit records where they require exactly one per ply
# (`lockstep_fuzz.fail("window_audit_records", ply, len(audit), 1)`), so 26
# tests across those three modules fail on a flag, not on a divergence
# (measured 2026-08-13: 30 failures in `pytest tests/android tests/golden
# tests/release tests/rustport`, 4 with the audit on).
#
# Deliberately NOT fixed by presetting the env var for the whole session, even
# though that is the smaller diff. `_WINDOW_AUDIT` is read INSIDE
# `_compute_mask` on every legal-mask computation, and when on it appends a
# record to a module-global list AND calls `_count_out_of_window_tiles` (a scan
# over placed tiles). Only the lockstep drivers drain that list; every other
# test in the suite would append to it forever. A session-wide preset therefore
# buys an unbounded list and a per-mask cost across the entire suite, on a box
# with a documented pytest-memory history — for the benefit of three modules.
#
# `_WINDOW_AUDIT` is a module global read at CALL time (only its initial value
# comes from the env), and the sibling `_WINDOW_STRICT` is already documented as
# "tests monkeypatch `game_wrapper._WINDOW_STRICT`". So the narrow fix is to
# monkeypatch the global for exactly the modules that ask for it, which is both
# import-order-proof AND auto-restored per test. The modules keep their
# `os.environ` assignment: it is still correct standalone, and it is what any
# subprocess they spawn inherits.
#
# The audit is read-only instrumentation — it never touches the mask, the raise
# condition, or any leaf/eval semantic (game_wrapper.py, "Window-overflow audit"
# block) — so this changes nothing for the tests it covers except making the
# records they already expect actually appear.
_WINDOW_AUDIT_MODULES = frozenset({
    "test_lockstep_fuzz",
    "test_p5_flags",
    "test_cloister_scan_fix_parity",
})


@pytest.fixture(autouse=True)
def _window_audit_latch(request, monkeypatch):
    """Force `game_wrapper._WINDOW_AUDIT` on for the modules whose drivers
    require the per-decision audit records, regardless of import order.

    Deliberately NOT a yield-fixture: this runs for every test in the suite, and
    a generator fixture with an early `return` raises `StopIteration` in pytest.
    The restore is monkeypatch's; the post-test drain is a finalizer.
    """
    if request.module.__name__.rsplit(".", 1)[-1] not in _WINDOW_AUDIT_MODULES:
        return
    from carcassonne_ai import game_wrapper as gw

    monkeypatch.setattr(gw, "_WINDOW_AUDIT", True, raising=True)
    gw.drain_window_audit()      # no records from a previous test leak in
    request.addfinalizer(gw.drain_window_audit)   # and none leak out


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


@pytest.fixture
def legacy_cache_key(monkeypatch):
    """Run a test under the HISTORICAL (non-injective) legal-cache /
    transposition key.

    `CARCASSONNE_FIX_LEGAL_CACHE_KEY` went DEFAULT-ON on 2026-08-30 (the
    180-symmetric-tile rotation collision — see the flag comment in
    `game_wrapper`). `string_representation` is both the legal-mask memo key
    and the MCTS transposition key, so the fix legitimately moves any scripted
    python-MCTS line. Goldens banked under the old key keep their numbers
    (supersede-by-rerun, never retro-edit) and pin themselves with this
    fixture, which is therefore the ONLY licensed reason to use it.

    `_tile_rotation_signature` memoizes per Tile instance and `Tile.turn()`
    memoizes rotated instances, so the caches are cleared on BOTH sides of the
    flip — otherwise a stale post-flip signature leaks in either direction."""
    import carcassonne_ai.game_wrapper as gw

    gw.clear_rotation_signature_caches()
    monkeypatch.setattr(gw, "_FIX_LEGAL_CACHE_KEY", False)
    yield
    gw.clear_rotation_signature_caches()
