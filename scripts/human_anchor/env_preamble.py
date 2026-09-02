"""Production leaf environment — MUST be imported before `carcassonne_ai`.

    import env_preamble  # noqa: F401   <- BEFORE any carcassonne_ai import

⚠️ CONSOLIDATED 2026-09-02. The values NO LONGER live here. This module is a thin
adapter over the ONE canonical definition, `carcassonne_ai.prod_env` — read that
module's docstring for the import-ordering contract, for why the PLAY (curve125)
and RULER (curve100) profiles must stay distinct, and for the OpenBLAS thread-pin
defect this profile still carries. `PROD_ENV` is re-exported under its historic
name because ~25 scripts and tests import it (`fair_common`, `prod_leaf_env`,
`window_truncation_census`, `android_bridge`'s drift test, …).

Why the adapter survives at all: `scripts/human_anchor/` is a sys.path-relative
top-level module used as the FIRST import of every human-anchor script, and
`scripts/rustport/prod_leaf_env` documents `env_preamble` as its value source.
Keeping the name is cheaper than editing 25 call sites, and it now cannot drift.

The profile is PLAY — curve125 IN THE ENVIRONMENT — because the human-anchor
harness PLAYS the champion off `DEFAULT_CONFIG` (the env IS the leaf here). This
is the operational wiring `governance/PRODUCTION.yaml` names for the curve125
adopt (CL-051, 2026-07-13). Do NOT export the curve globally: the eval rulers
`setdefault`, so an ambient curve125 would move the fixed ruler/anchor side.

`setdefault` semantics are unchanged: a caller who already exported these (e.g.
an orchestrator) wins; we only fill blanks.
"""
from __future__ import annotations

import sys
from pathlib import Path

# The canonical module lives in the package; make a bare repo checkout work even
# when `carcassonne_ai` is not pip-installed. Append, never prepend, so an
# installed copy still wins.
_SRC = str(Path(__file__).resolve().parents[2] / "src")
if (Path(_SRC) / "carcassonne_ai").is_dir() and _SRC not in sys.path:
    sys.path.append(_SRC)

from carcassonne_ai import prod_env  # noqa: E402
from carcassonne_ai.prod_env import PLAY as PROD_ENV  # noqa: E402

__all__ = ["PROD_ENV", "apply", "resolved", "RESOLVED"]


# Bound to PLAY explicitly (rather than re-exported) so this stays correct even if
# `prod_env.apply`'s default profile is ever changed.
def apply() -> dict[str, str]:
    """Fill any unset production knob; return the resolved subset (for manifests)."""
    return prod_env.apply(PROD_ENV)


def resolved() -> dict[str, str]:
    """The PLAY knobs as they stand in os.environ right now."""
    return prod_env.resolved(PROD_ENV)


# Apply on import so `import env_preamble` before `import carcassonne_ai` is enough.
RESOLVED = apply()
