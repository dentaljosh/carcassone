"""Production leaf environment for the F3 public-state oracle — import FIRST.

    import env_preamble  # noqa: F401   <- BEFORE any carcassonne_ai import

⚠️ CONSOLIDATED 2026-09-02. The values NO LONGER live here. This module is a thin
adapter over the ONE canonical definition, `carcassonne_ai.prod_env`; read that
docstring for the import-ordering contract and the PLAY/RULER split. `CANON_ENV`
is re-exported under its historic name for the existing importers
(`f3_public_state_oracle/{run_oracle,mine_roots}.py`,
`measurement_infra/gate_b_depth_transfer.py`, `tests/android/test_bridge.py`).

The profile is RULER — curve100 (the frozen v2.9 substrate) in the environment,
NOT curve125. That is deliberate and load-bearing, not a stale copy: the F3 fair
champion is built through `champion_factory`, which injects curve125 on the
CHAMPION side via `dataclasses.replace`, while the fixed reference side stays on
the frozen substrate. Exporting curve125 here would silently re-baseline the
reference. It is byte-identical to `eval_fair_puct`'s ruler env for the same
reason — both are now the same object.

Pure CPU, net-free: no GPU, no BLAS thread pools (the fair game is a Cython leaf
+ PUCT tree + the marginalized solver — no matmul). setdefault: a caller
(orchestrator) who already exported these wins.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make a bare repo checkout work when `carcassonne_ai` is not pip-installed.
# Append, never prepend, so an installed copy still wins.
_SRC = str(Path(__file__).resolve().parents[2] / "src")
if (Path(_SRC) / "carcassonne_ai").is_dir() and _SRC not in sys.path:
    sys.path.append(_SRC)

from carcassonne_ai import prod_env  # noqa: E402
from carcassonne_ai.prod_env import RULER as CANON_ENV  # noqa: E402

__all__ = ["CANON_ENV", "apply", "resolved", "RESOLVED"]


# Bound to RULER rather than re-exported: `prod_env.apply()` defaults to PLAY
# (curve125), so a bare `env_preamble.apply()` here must NOT inherit that default.
def apply() -> dict[str, str]:
    """Fill any unset RULER knob; return the resolved subset (for manifests)."""
    return prod_env.apply(CANON_ENV)


def resolved() -> dict[str, str]:
    """The RULER knobs as they stand in os.environ right now."""
    return prod_env.resolved(CANON_ENV)


# Apply on import so `import env_preamble` before `import carcassonne_ai` suffices.
RESOLVED = apply()
