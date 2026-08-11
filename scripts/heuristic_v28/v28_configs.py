#!/usr/bin/env python3
"""Single source of truth for the v2.8 variant LeafConfigs.

Builds the named v2.8 variants as `dc.replace()` overrides on top of the PRODUCTION
v2.7 base (CAP=12, DROP_THREE_OPEN, etc.). All audit/eval scripts in this branch import
`build_variants()` so the variant definitions never drift from V28_VARIANT_CONFIGS.json.

IMPORTANT: import this module BEFORE carcassonne_ai so the production env knobs are set
at import time (DEFAULT_CONFIG is built from env once). Or call `set_prod_env()` first.
"""
from __future__ import annotations
import dataclasses as dc
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SPEC = os.path.join(REPO, "measurement", "heuristic_v28", "V28_VARIANT_CONFIGS.json")

PROD_ENV = {
    "CARCASSONNE_V25_CAP": "12",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_V25_RESIDUAL_SCALE": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
}


def set_prod_env() -> None:
    """Set the production v2.7 env knobs (idempotent, setdefault). Call before importing
    carcassonne_ai so DEFAULT_CONFIG resolves to the real v2.7 base, not the CAP=5 default."""
    for k, v in PROD_ENV.items():
        os.environ.setdefault(k, v)


def load_spec() -> dict:
    with open(SPEC) as fh:
        return json.load(fh)


def build_variants(names: list[str] | None = None) -> dict:
    """Return {variant_name: LeafConfig}. Base = the env-built DEFAULT_CONFIG (must be the
    v2.7 production base — call set_prod_env() first). Each variant = dc.replace(base, **overrides)."""
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402
    spec = load_spec()
    base = DEFAULT_CONFIG
    # sanity: refuse to run if the base isn't the production v2.7 (CAP=12, drop-three-open)
    assert base.bonus_cap == 12.0, f"base bonus_cap={base.bonus_cap}, expected 12 — set_prod_env() not called?"
    assert base.closure_p == {1: 0.5, 2: 0.2}, f"base closure_p={base.closure_p} — DROP_THREE_OPEN not set?"
    out = {}
    for name, v in spec["variants"].items():
        if names and name not in names:
            continue
        ov = dict(v.get("overrides", {}))
        out[name] = dc.replace(base, **ov) if ov else base
    return out


if __name__ == "__main__":
    set_prod_env()
    import sys
    sys.path.insert(0, os.path.join(REPO, "src"))
    vs = build_variants()
    for name, cfg in vs.items():
        print(f"{name:16} farm={cfg.v28_farm_majority} meeple_k={cfg.v28_meeple_k} "
              f"meeple_t0={cfg.v28_meeple_recovery_t0} slack={cfg.closure_continuous_slack} "
              f"opp_cap={cfg.opp_bonus_cap} cap={cfg.bonus_cap}")
