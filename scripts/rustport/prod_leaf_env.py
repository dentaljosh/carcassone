"""Freeze the PRODUCTION leaf SHAPE before `carcassonne_ai` is imported.

    import prod_leaf_env  # noqa: F401   <- BEFORE any carcassonne_ai import

WHY THIS EXISTS.  `virtual_score_v2.DEFAULT_CONFIG` is built ONCE, at the first
`carcassonne_ai.virtual_score_v2` import, from the `CARCASSONNE_V25_*` / `V29_*`
environment.  Whichever module wins that race decides the session-global default
for every module that comes after it.  A rustport gate script does not *need* the
production leaf — it builds every `LeafConfig` explicitly — so several of them
imported `carcassonne_ai` with a bare environment.  Run standalone that is
harmless; run inside a full-tree `pytest`, where collection imports the gate
scripts, it freezes `DEFAULT_CONFIG` at the bare cap-5 / no-curve default and
every later `champion_factory.make_production_champion(verify=True)` raises
`ProvenanceError: bonus_cap=5.0 != PRODUCTION.yaml 8.0`.  That is the
order-dependent failure P5 reported (DECISIONS 2026-08-01 pre-dawn, note 5).

WHY ONLY THE SHAPE SUBSET.  The production env sets two kinds of knob: the leaf
SHAPE (caps, curve, meeple_k, value_blend) and the DISPATCH
(`CARCASSONNE_USE_CY_REPR`, `CARCASSONNE_USE_FLAT_LEAF`, `..._USE_CY_LEAF`).
Only the shape freezes `DEFAULT_CONFIG`; the dispatch knobs decide WHICH
IMPLEMENTATION runs.  G1–G5 were gated with the dispatch knobs as the scripts
found them, so flipping them here would silently change which implementation a
passed gate is evidence about.  This module therefore applies the SHAPE subset
only — `carcassonne_ai.prod_env.PLAY_SHAPE`, the curve125 (PLAY) dialect.

⚠️ CONSOLIDATED 2026-09-02: the values now come from `carcassonne_ai.prod_env`,
the ONE canonical definition (previously they were read out of
`scripts/human_anchor/env_preamble.PROD_ENV`, which is itself now an adapter over
the same module).  Scripts that genuinely want the WHOLE production environment
(anything that BUILDS the champion — `fair_common`, and through it
`reconcile_fair` / `reconcile_backend`) keep importing `env_preamble` directly.
Both are `setdefault`-based and share one source, so importing this first and
`env_preamble` later is consistent: the shape values are identical by
construction and the dispatch knobs still resolve.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make a bare repo checkout work when `carcassonne_ai` is not pip-installed.
# Append, never prepend, so an installed copy still wins.
_SRC = str(Path(__file__).resolve().parents[2] / "src")
if (Path(_SRC) / "carcassonne_ai").is_dir() and _SRC not in sys.path:
    sys.path.append(_SRC)

# ⚠️ The guard below tests `carcassonne_ai.virtual_score_v2`, NOT `carcassonne_ai`.
# That is the invariant this module actually protects — DEFAULT_CONFIG is frozen at
# the *leaf module's* import, and `carcassonne_ai/__init__.py` is deliberately empty
# (importing the package, or `carcassonne_ai.prod_env`, latches nothing).  The old
# package-level test was a PROXY that tripped on collection ORDER in a whole-tree
# pytest run — `tests/android/` sorts before `tests/rustport/` and imports the
# package first — which aborted collection and ran ZERO tests (measured 2026-08-13;
# see the workaround in tests/conftest.py, still in place and still correct).
# Narrowing the guard to the real invariant keeps every protection it ever had.
if "carcassonne_ai.virtual_score_v2" in sys.modules:  # pragma: no cover
    raise RuntimeError(
        "prod_leaf_env must be imported BEFORE carcassonne_ai.virtual_score_v2 — "
        "DEFAULT_CONFIG is frozen at ITS import.")

from carcassonne_ai import prod_env  # noqa: E402
from carcassonne_ai.prod_env import PLAY_SHAPE, SHAPE_KEYS  # noqa: E402,F401

__all__ = ["SHAPE_KEYS", "PLAY_SHAPE", "apply", "RESOLVED"]


def apply() -> dict[str, str]:
    """Fill any unset leaf-SHAPE knob; return the resolved subset (for manifests)."""
    return prod_env.apply(PLAY_SHAPE)


RESOLVED = apply()
