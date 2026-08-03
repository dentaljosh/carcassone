"""C5 candidate-leaf override helpers (--cand-leaf-json) — SHARED between
``eval_puct_priors.py`` (clairvoyant screen, Stage 0/1) and ``eval_fair_puct.py``
(fair re-confirm, Stage 3). Design: measurement/classical_search/
C5_LEAF_RETUNE_DESIGN.md §"Stage 0".

The candidate side of a leaf A/B replaces ONLY the named fields on the env-resolved
``DEFAULT_CONFIG`` (v2.9 Bmild_cap8); the champion / opponent rung side ALWAYS keeps
env ``DEFAULT_CONFIG``. Absent flag -> the candidate stays ``DEFAULT_CONFIG`` too, so
the run is byte-identical to today (default-OFF).

⚠️ The CALLER MUST set the leaf env (CARCASSONNE_V25_* / V29_MEEPLE_CURVE / ...) BEFORE
importing this module: ``DEFAULT_CONFIG`` is the env-resolved singleton from
``virtual_score_v2`` and is captured at that module's import time. Both harnesses set
the env via ``os.environ.setdefault`` at their top, above every carcassonne_ai import,
so importing this module from their import block resolves the production leaf.

Lifted verbatim from eval_puct_priors.py (commit 7605ef9) so the two harnesses can
never diverge on the parse/coercion/guard semantics — the Trap-1 (wrong-leaf) mitigation
relies on both sides speaking the exact same LeafConfig JSON dialect.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG


# F6 soft-cap slopes are EXCLUDED from the harness _leaf_hash while at their default
# (0.0) so the champion's a36d2e15 dialect recomputes UNCHANGED across this additive,
# default-off field. NOTE the asymmetry vs the earlier default-off knobs (bag_close /
# C7 Term R/F): those predate the a36d2e15 baseline (2026-07-19) and are BAKED INTO it,
# so they stay in the dict; F6 postdates it and must be dropped to preserve the hash. A
# candidate that SETS a slope is a different leaf and DOES shift the hash (as intended).
# Mirror in alphabeta_agent._leaf_hash + tests/test_t3_optuna's inline recipe.
# F7b farm knockouts (2026-08-02) postdate a36d2e15 too, so they follow the F6 rule.
_LEAF_HASH_EXCLUDE_IF_DEFAULT = {"soft_cap_slope": 0.0, "opp_soft_cap_slope": 0.0,
                                 "farm_base_off": False, "farm_growth_off": False}


def _leaf_dict(cfg) -> dict:
    """JSON-serializable dict of a resolved LeafConfig (tuples -> lists), dropping the
    F6 soft-cap slopes while default (see `_LEAF_HASH_EXCLUDE_IF_DEFAULT`)."""
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(cfg).items()
            if not (k in _LEAF_HASH_EXCLUDE_IF_DEFAULT and v == _LEAF_HASH_EXCLUDE_IF_DEFAULT[k])}


def _leaf_hash(cfg) -> str:
    """Stable short hash of the resolved LeafConfig (provenance)."""
    return hashlib.sha256(
        json.dumps(_leaf_dict(cfg), sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def _load_cand_leaf_cfg(spec):
    """Parse --cand-leaf-json into a candidate LeafConfig by replacing ONLY the
    named fields on the env-resolved DEFAULT_CONFIG (v2.9 Bmild_cap8). `spec` is
    inline JSON (a `{...}` object) or a path to a JSON file. Returns None for a
    falsy spec (flag absent -> the candidate side stays DEFAULT_CONFIG, so the run
    is byte-identical to today). Overrides ONLY the CANDIDATE leaf; the champion
    side always keeps DEFAULT_CONFIG.

    Field coercions (JSON -> LeafConfig):
      closure_p       object with string keys -> {int: float} (the schedule dict)
      v29_meeple_curve  list -> tuple(float); null -> None (curve OFF)
      everything else passes through (floats / bools / ints).
    Unknown field names raise (fail-loud on a typo silently running the wrong leaf).
    """
    if not spec:
        return None
    import dataclasses as _dc

    txt = spec.strip()
    if not txt.startswith(("{", "[")):   # else a path to a JSON file
        txt = Path(spec).read_text()
    raw = json.loads(txt)
    if not isinstance(raw, dict):
        raise ValueError("--cand-leaf-json must be a JSON object (LeafConfig field -> value)")
    valid = {f.name for f in _dc.fields(DEFAULT_CONFIG)}
    over = {}
    for k, v in raw.items():
        if k not in valid:
            raise ValueError(
                f"--cand-leaf-json: unknown LeafConfig field {k!r} (valid: {sorted(valid)})"
            )
        if k == "closure_p" and v is not None:
            over[k] = {int(kk): float(vv) for kk, vv in v.items()}
        elif k == "v29_meeple_curve":
            over[k] = None if v is None else tuple(float(x) for x in v)
        else:
            over[k] = v
    return _dc.replace(DEFAULT_CONFIG, **over)


def _assert_cy_float_path(cfg) -> None:
    """S0 cy-path guard (design Stage 0, item 3): the candidate leaf MUST stay on
    the Cython float flat-leaf path, else it silently runs the ~30x slower pure-
    Python object leaf (v2.8/v2.9-non-curve terms) or a non-cy path (tile-counting
    / continuous-slack). Curve-only and bag_close are cy-float-supported by this
    build; everything the screen sweeps use qualifies by construction."""
    from carcassonne_ai import virtual_score_v2 as _vs2
    if _vs2._v28_active(cfg):
        raise ValueError("--cand-leaf-json: v2.8 terms (v28_farm_majority/v28_meeple_k) "
                         "force the object path — not a Cython float leaf")
    if _vs2._v29_active(cfg) and not _vs2._v29_flat_eligible(cfg):
        raise ValueError("--cand-leaf-json: v2.9 object-only terms (util_tanh/punish/farm_access) "
                         "force the object path — only the curve / C7 Term R (v29_meeple_return_k) / "
                         "Term F (v29_farm_flip_k) stay on the cy float path")
    if cfg.tile_counting_closure or cfg.closure_continuous_slack > 0.0:
        raise ValueError("--cand-leaf-json: tile_counting_closure / closure_continuous_slack "
                         "force the non-cy path")
    if cfg.bag_close:
        try:
            from carcassonne_ai import flat_leaf_cy as _cy
            if not bool(getattr(_cy, "SUPPORTS_V210_BAG_CLOSE", False)):
                raise ValueError("--cand-leaf-json: bag_close set but the compiled cy leaf "
                                 "lacks SUPPORTS_V210_BAG_CLOSE (rebuild flat_leaf_cy)")
        except ImportError as e:
            raise ValueError("--cand-leaf-json: bag_close set but flat_leaf_cy is not built") from e
    # C7 wave-2: Term R / Term F need the SUPPORTS_V29_C7_TERMS build, else a stale .so
    # silently falls back to the ~30x-slower pure-Python flat (mirrors the bag_close clause).
    if cfg.v29_meeple_return_k != 0.0 or cfg.v29_farm_flip_k != 0.0:
        try:
            from carcassonne_ai import flat_leaf_cy as _cy
            if not bool(getattr(_cy, "SUPPORTS_V29_C7_TERMS", False)):
                raise ValueError("--cand-leaf-json: v29_meeple_return_k/v29_farm_flip_k set but the "
                                 "compiled cy leaf lacks SUPPORTS_V29_C7_TERMS (rebuild flat_leaf_cy)")
        except ImportError as e:
            raise ValueError("--cand-leaf-json: C7 terms set but flat_leaf_cy is not built") from e
    # R-requires-curve (defensive; the champion always carries a curve, so a --cand-leaf-json
    # replacing only v29_meeple_return_k inherits it — this catches an explicit curve=null).
    if cfg.v29_meeple_return_k != 0.0 and cfg.v29_meeple_curve is None:
        raise ValueError("--cand-leaf-json: v29_meeple_return_k requires v29_meeple_curve "
                         "(Term R prices the marginal step of the liquidity curve)")
    # F6 soft cap: a SET slope needs the SUPPORTS_F6_SOFT_CAP build, else a stale .so
    # silently hard-clamps via the pure-Python flat fallback (~30x slower; mirrors the
    # bag_close / C7 clauses). slope 0.0 is bit-exact on any .so (hard clamp), so skip.
    if getattr(cfg, "soft_cap_slope", 0.0) != 0.0 or getattr(cfg, "opp_soft_cap_slope", 0.0) != 0.0:
        try:
            from carcassonne_ai import flat_leaf_cy as _cy
            if not bool(getattr(_cy, "SUPPORTS_F6_SOFT_CAP", False)):
                raise ValueError("--cand-leaf-json: soft_cap_slope/opp_soft_cap_slope set but the "
                                 "compiled cy leaf lacks SUPPORTS_F6_SOFT_CAP (rebuild flat_leaf_cy)")
        except ImportError as e:
            raise ValueError("--cand-leaf-json: soft-cap slope set but flat_leaf_cy is not built") from e
    # F7b farm knockouts: the ONE knob family that deliberately has no cy implementation
    # (roadmap F7b — the cells run `--backend rust`, where no Python leaf is computed).
    # A set knob therefore ALWAYS leaves the cy fast path for the pure-Python flat leaf,
    # which is bit-exact (scripts/rustport/reconcile_leaf.py --configs farmoff) but
    # ~12.5x slower per leaf. That is a SPEED fact, not a correctness one — exactly like
    # every clause above, all of which also fall back to a correct pure-Python leaf — so
    # this WARNS instead of raising: raising would make the intended `--backend rust`
    # cells unlaunchable, and a `--backend python` leg (the wiring gate's reference leg)
    # must stay runnable.
    if getattr(cfg, "farm_base_off", False) or getattr(cfg, "farm_growth_off", False):
        import sys as _sys
        print("[leaf-override] WARNING: F7b farm knockout set (farm_base_off="
              f"{getattr(cfg, 'farm_base_off', False)}, farm_growth_off="
              f"{getattr(cfg, 'farm_growth_off', False)}) — the candidate leaf leaves the "
              "Cython fast path for the pure-Python flat leaf (bit-exact, ~12.5x slower "
              "per leaf). Intended only with --backend rust, where no Python leaf runs.",
              file=_sys.stderr)
