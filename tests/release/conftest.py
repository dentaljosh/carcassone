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
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for _p in ("src", "scripts/measurement_infra", "scripts/classical_search", "scripts/level2"):
    _abs = str(_REPO / _p)
    if _abs not in sys.path:
        sys.path.insert(0, _abs)

# Production leaf env as a setdefault fallback — harmless when the runner already set it
# (scripts/release_audit.sh does), and it fills blanks for the in-suite run.
# DEFAULT_CONFIG is import-frozen so setdefault alone is not enough under pollution; the
# fixture below is.
#
# ⚠️ CONSOLIDATED 2026-09-02: values come from `carcassonne_ai.prod_env`, the ONE
# canonical definition. RULER (curve100 base) is the correct profile here: the factory
# injects curve125 on the champion side, which is exactly what this suite asserts.
from carcassonne_ai import prod_env  # noqa: E402

prod_env.apply(prod_env.RULER)


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
