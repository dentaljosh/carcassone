"""Production leaf environment for the F3 public-state oracle — import FIRST.

The v2.9 Bmild_cap8 leaf reads these knobs from the environment at import time
(DEFAULT_CONFIG is import-frozen); the library sets none itself. Every F3 script
does ``import env_preamble`` as its FIRST import so the fair champion built via
``champion_factory`` runs the exact production leaf shape and its runtime
verify (curve125) passes.

Byte-identical to ``scripts/classical_search/eval_fair_puct.py``'s ``_CANON_ENV``
(the sibling fair eval): the env fixes the cap8 / curve100 BASE leaf, and
``champion_factory.production_prior_cfg`` injects curve125 on top via
``dataclasses.replace`` — exactly how the deployed champion is constructed.
setdefault: a caller (orchestrator) who already exported these wins.

Pure CPU, net-free: no GPU, no BLAS thread pools (the fair game is a Cython
leaf + PUCT tree + the marginalized solver — no matmul).
"""
from __future__ import annotations

import os

# Verbatim eval_fair_puct._CANON_ENV (curve100 base; curve125 injected by the
# champion_factory at cfg build time — see module docstring).
CANON_ENV: dict[str, str] = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    # OpenBLAS is the real backend (scipy-OpenBLAS DYNAMIC_ARCH, not MKL); left
    # unpinned it spawns a box-sized busy-wait pool per fork worker and thrashes
    # the scheduler. Pin to 1 — result-neutral for a net-free CPU stack.
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


def apply() -> dict[str, str]:
    """Fill any unset production knob; return the resolved subset (for manifests)."""
    for k, v in CANON_ENV.items():
        os.environ.setdefault(k, v)
    return {k: os.environ.get(k, "") for k in CANON_ENV}


# Apply on import so `import env_preamble` before `import carcassonne_ai` suffices.
RESOLVED = apply()
