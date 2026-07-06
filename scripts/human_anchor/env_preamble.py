"""Production leaf environment — MUST be imported before `carcassonne_ai`.

The v2.7/v2.9 leaf reads these knobs from the environment at import time (the
CALLER shapes them; the library sets none itself). Every human-anchor script
does `import env_preamble` as its FIRST import so the deployed agent and the
solver use the exact production leaf shape. `setdefault` = a caller who already
exported these (e.g. an orchestrator) wins; we only fill blanks.

Source of the knob values: the task's "Production leaf env preamble" +
governance/PRODUCTION.yaml (as of 2026-06-11: FLAT_LEAF, cap 8, meeple curve).
"""
from __future__ import annotations

import os

PROD_ENV: dict[str, str] = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    # net-on-CPU / single-thread: no GPU, no BLAS thread thrash (this is a
    # heuristic-leaf + solver stack; there is no net forward here).
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}


def apply() -> dict[str, str]:
    """Fill any unset production knob; return the resolved subset (for manifests)."""
    for k, v in PROD_ENV.items():
        os.environ.setdefault(k, v)
    return {k: os.environ.get(k, "") for k in PROD_ENV}


# Apply on import so `import env_preamble` before `import carcassonne_ai` is enough.
RESOLVED = apply()
