"""tests/release/ — the F1 semantic/property release-integrity suite.

Gate: ZERO semantic/configuration divergences before any headline claim. Runnable in
isolation via scripts/release_audit.sh (which sets the production leaf env before python
starts) OR as part of the full pytest run.

This conftest makes the release tests IMPORT-ORDER-ROBUST: it forces the champion factory
to build off the frozen v2.9 (cap8, curve100) substrate — deterministic, independent of
whichever sibling test module won the session DEFAULT_CONFIG build race. Without it, a
polluted session default (e.g. a bare cap5 config) would make the factory's curve125
verify raise on the caps — a session artifact, not a real regression.
"""
import os
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for _p in ("src", "scripts/measurement_infra", "scripts/classical_search", "scripts/level2"):
    _abs = str(_REPO / _p)
    if _abs not in sys.path:
        sys.path.insert(0, _abs)

# Production leaf env (the _CANON_ENV shape) as a setdefault fallback — harmless when the
# runner already set it, and it fills blanks for the in-suite run. DEFAULT_CONFIG is
# import-frozen so setdefault alone is not enough under pollution; the fixture below is.
for _k, _v in {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
}.items():
    os.environ.setdefault(_k, _v)


def production_base_cfg():
    """The frozen v2.9 (cap8, curve100, meeple_k=2.0) LeafConfig, built DETERMINISTICALLY
    from an explicit env (snapshot.frozen_v29_cfg asserts its hash). champion_factory
    replaces only the meeple curve -> curve125, so this is the production base."""
    from snapshot import frozen_v29_cfg
    return frozen_v29_cfg(value_norm=2.0)


@pytest.fixture(autouse=True)
def _force_production_leaf(monkeypatch):
    """Force champion_factory (and virtual_score_v2) DEFAULT_CONFIG to the frozen v2.9
    base so the release tests resolve the production curve125 leaf regardless of the
    session import order."""
    base = production_base_cfg()
    import carcassonne_ai.champion_factory as cf
    import carcassonne_ai.virtual_score_v2 as vs
    monkeypatch.setattr(cf, "DEFAULT_CONFIG", base, raising=False)
    monkeypatch.setattr(vs, "DEFAULT_CONFIG", base, raising=False)
