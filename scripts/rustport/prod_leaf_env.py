"""Freeze the PRODUCTION leaf SHAPE before `carcassonne_ai` is imported.

    import prod_leaf_env  # noqa: F401   <- BEFORE any carcassonne_ai import

WHY THIS EXISTS.  `virtual_score_v2.DEFAULT_CONFIG` is built ONCE, at the first
`carcassonne_ai` import, from the `CARCASSONNE_V25_*` / `V29_*` environment.
Whichever module wins that race decides the session-global default for every
module that comes after it.  A rustport gate script does not *need* the
production leaf — it builds every `LeafConfig` explicitly — so several of them
imported `carcassonne_ai` with a bare environment.  Run standalone that is
harmless; run inside a full-tree `pytest`, where collection imports the gate
scripts, it freezes `DEFAULT_CONFIG` at the bare cap-5 / no-curve default and
every later `champion_factory.make_production_champion(verify=True)` raises
`ProvenanceError: bonus_cap=5.0 != PRODUCTION.yaml 8.0`.  That is the
order-dependent failure P5 reported (DECISIONS 2026-08-01 pre-dawn, note 5).

WHY NOT JUST `import env_preamble`.  `scripts/human_anchor/env_preamble` sets two
kinds of knob: the leaf SHAPE (caps, curve, meeple_k, value_blend) and the
DISPATCH (`CARCASSONNE_USE_CY_REPR`, `CARCASSONNE_USE_FLAT_LEAF`).  Only the
shape freezes `DEFAULT_CONFIG`; the dispatch knobs decide WHICH IMPLEMENTATION
runs.  G1–G5 were gated with the dispatch knobs as the scripts found them, so
flipping them here would silently change which implementation a passed gate is
evidence about.  This module therefore applies the SHAPE subset only, sourced
from `env_preamble.PROD_ENV` so there is exactly one place the values live.

Scripts that genuinely want the whole production environment (anything that
BUILDS the champion — `fair_common`, and through it `reconcile_fair` /
`reconcile_backend`) keep importing `env_preamble` directly.  Both are
`setdefault`-based, so importing this first and `env_preamble` later is
consistent: the shape values are identical and the dispatch knobs still resolve.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HUMAN_ANCHOR = Path(__file__).resolve().parents[1] / "human_anchor"
if str(_HUMAN_ANCHOR) not in sys.path:
    sys.path.insert(0, str(_HUMAN_ANCHOR))

import env_preamble  # noqa: E402

# The knobs `virtual_score_v2._config_from_env()` reads, i.e. the ones that make
# DEFAULT_CONFIG what it is. Everything else in PROD_ENV is dispatch or threading
# and is deliberately NOT applied here.
SHAPE_KEYS = (
    "CARCASSONNE_V25_CAP",
    "CARCASSONNE_V25_OPP_CAP",
    "CARCASSONNE_V25_DROP_THREE_OPEN",
    "CARCASSONNE_V29_MEEPLE_CURVE",
    "CARCASSONNE_V25_MEEPLE_K",
    "CARCASSONNE_V25_VALUE_BLEND",
)

if "carcassonne_ai" in sys.modules:  # pragma: no cover - import-order guard
    raise RuntimeError(
        "prod_leaf_env must be imported BEFORE carcassonne_ai — "
        "virtual_score_v2.DEFAULT_CONFIG is frozen at ITS import.")


def apply() -> dict[str, str]:
    """Fill any unset leaf-SHAPE knob; return the resolved subset (for manifests)."""
    for k in SHAPE_KEYS:
        v = env_preamble.PROD_ENV.get(k)
        if v is not None:
            os.environ.setdefault(k, v)
    return {k: os.environ.get(k, "") for k in SHAPE_KEYS}


RESOLVED = apply()
