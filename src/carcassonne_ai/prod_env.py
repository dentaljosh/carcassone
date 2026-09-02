"""THE canonical production leaf environment — one definition, many consumers.

Before this module existed the same ``CARCASSONNE_*`` block was hand-copied into
eight places (two ``env_preamble.py`` files, ``eval_fair_puct._CANON_ENV``,
``android_bridge.PROD_ENV``, ``m5_bench.bench_champion.PROD_ENV``,
``tests/release/conftest.py``, ``tests/test_alphabeta_agent.py`` and two shell
launchers). They had drifted. This module is now the single place the VALUES
live; every site imports (or, where it physically cannot, is pinned to this
module by ``tests/test_prod_env.py``).

===========================================================================
⚠️  ORDERING CONSTRAINT — THIS IS THE WHOLE REASON THE MODULE IS SHAPED THIS WAY
===========================================================================
The knobs below are **latched at import time**, not read per call:

  * ``virtual_score_v2.DEFAULT_CONFIG`` is built ONCE by ``_config_from_env()``
    at the first ``carcassonne_ai.virtual_score_v2`` import. Whichever module
    wins that race fixes the session-global leaf shape for everything after it.
  * ``flat_leaf.USE_FLAT_LEAF`` / ``USE_CY_LEAF`` and ``board_repr.USE_CY_REPR``
    are read at THEIR module import.
  * ``CARCASSONNE_FIX_R9`` is latched harder still — ``wingedsheep`` ``base_deck``
    rewrites its module-level tile table at import and the Rust registry
    memoises in a ``OnceLock``. See ``carcassonne_ai.rules_profile``.

So ``apply()`` MUST run **before the first ``carcassonne_ai`` / ``wingedsheep``
import** at every site. That is why this module imports ``os`` and nothing else,
and why ``carcassonne_ai/__init__.py`` is deliberately empty: ::

    from carcassonne_ai.prod_env import apply   # safe — pulls in nothing
    apply()                                     # or apply(RULER)
    import carcassonne_ai.champion_factory      # NOW the library may load

Importing this module does NOT import the leaf, so it cannot itself lose the
race. Do not add a package-level import to this file, and do not add imports to
``carcassonne_ai/__init__.py``.

``apply()`` uses ``os.environ.setdefault`` throughout: a caller (an orchestrator,
a launcher, a ``--shared-claim`` cell) that already exported a knob WINS. We only
fill blanks.

===========================================================================
THE TWO PROFILES — AND WHY THEY ARE NOT ONE
===========================================================================
``PLAY`` and ``RULER`` differ in exactly one value, ``CARCASSONNE_V29_MEEPLE_CURVE``,
and that difference is **load-bearing**. Do not "simplify" it away.

  ``PLAY``  — curve125 IN THE ENVIRONMENT. For anything that plays the champion
              off ``DEFAULT_CONFIG``: the human-anchor play harness, the Android
              bridge, the M5 bench, the rustport shape guard. Here the env IS the
              leaf, so it must carry the adopted C5 curve125 (CL-051, 2026-07-13).

  ``RULER`` — curve100 in the environment. For the EVAL harnesses. They build the
              champion through ``champion_factory``, which does
              ``dc.replace(DEFAULT_CONFIG, v29_meeple_curve=CURVE125)`` — the
              champion side gets curve125 regardless of the env — while the FIXED
              ruler / anchor side is deliberately left on the frozen v2.9 curve100
              substrate (7fc930b8). ``governance/PRODUCTION.yaml`` states the rule
              in as many words: "⚠️ Do NOT export CARCASSONNE_V29_MEEPLE_CURVE
              globally — the rulers setdefault, so an ambient curve125 would
              silently move the fixed ruler/anchor side and contaminate
              baselines."

  ⇒ Collapsing these two into one curve would either move the deployed champion's
    leaf (if RULER won) or silently re-baseline every fixed ruler and anchor in
    the measurement record (if PLAY won). Both are wrong. Pick the profile by
    ASKING "does this process play off DEFAULT_CONFIG, or does it build the
    champion through champion_factory and also host a fixed reference?".

The two profiles also differ in thread pins; see ``_THREADS_MIN`` below, which
carries a KNOWN DEFECT flagged for the owner rather than silently fixed.

===========================================================================
SHELL CONSUMERS
===========================================================================
Launcher ``.sh`` files consume the same values without duplicating them::

    eval "$(python -m carcassonne_ai.prod_env --export --profile ruler)"

``--export`` prints POSIX ``export K='V'`` lines (single-quote-escaped) and
nothing else, so it is safe to ``eval``. ``--json`` prints the same mapping as
JSON for manifest writers.

===========================================================================
WHAT IS DELIBERATELY *NOT* HERE
===========================================================================
``CARCASSONNE_FIX_R9`` / ``CARCASSONNE_RULES_PROFILE``. The rules profile is a
per-RUN choice (the walled record vs ``fixed_v1``), declared by
``carcassonne_ai.rules_profile`` and exported per-cell by each launcher —
``PRODUCTION.yaml`` names ``fixed_v1`` as the profile of record for NEW work, but
folding R9 into this block would silently re-rule every legacy replay path that
imports it. ``rules_profile.activate()`` remains the seam. (The Android bridge
sets ``CARCASSONNE_FIX_R9`` itself, immediately after ``apply()``, because the app
always plays R9 — see its section 1a.)
"""
from __future__ import annotations

import os

__all__ = [
    "CURVE100", "CURVE125", "PLAY", "RULER", "PLAY_SHAPE", "SHAPE_KEYS",
    "PROFILES", "LATCHING_MODULES", "apply", "resolved", "verify",
    "latched_modules",
]

#: The modules that LATCH one of these knobs at their own import. Once any of them is
#: in ``sys.modules``, ``apply()`` can no longer change what this process will do, and
#: an import-order guard should fire.
#:
#: ⚠️ This is the list every import-order guard in the tree should test — NOT the
#: presence of ``"carcassonne_ai"`` itself. The package's ``__init__.py`` is empty, so
#: importing the package (or this module) latches nothing; a guard that tests the
#: package name is a PROXY that fires on innocent imports. That proxy is what made a
#: whole-tree ``pytest`` abort collection and run ZERO tests (2026-08-13), and what
#: would fire on every `import env_preamble` now that the preamble is an adapter over
#: this module.
LATCHING_MODULES: tuple[str, ...] = (
    "carcassonne_ai.virtual_score_v2",              # DEFAULT_CONFIG (the leaf shape)
    "carcassonne_ai.flat_leaf",                     # USE_FLAT_LEAF / USE_CY_LEAF
    "carcassonne_ai.board_repr",                    # USE_CY_REPR
    "wingedsheep.carcassonne.tile_sets.base_deck",  # CARCASSONNE_FIX_R9 tile table
)


def latched_modules() -> tuple[str, ...]:
    """Which latching modules are ALREADY imported — i.e. too late for ``apply()``.

    Empty tuple means the environment can still be shaped. Use this in an
    import-order guard instead of testing for ``"carcassonne_ai" in sys.modules``.
    """
    import sys as _sys
    return tuple(m for m in LATCHING_MODULES if m in _sys.modules)


# --------------------------------------------------------------------------- #
# Value blocks. Composed into profiles below — never consumed directly.        #
# --------------------------------------------------------------------------- #

# The v2.9 Bmild_cap8 leaf SHAPE. These are exactly the knobs
# `virtual_score_v2._config_from_env()` reads to build DEFAULT_CONFIG, minus the
# curve (which is what the two profiles disagree about).
#   cap 8 / opp_cap 8      : C5 confirmed cap8 optimal (opp_cap wings both negative)
#   DROP_THREE_OPEN "0"    : keeps the 3-open term; note `_config_from_env` tests
#                            `== "1"`, so "0" and *unset* are the same schedule.
#   MEEPLE_K "2.0"         : INERT under a non-null curve (`flat_leaf` takes the
#                            curve branch), kept because it is what the champion
#                            leaf-hash dialect `a36d2e15a3b3d71d` was computed with.
_LEAF_SHAPE: dict[str, str] = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
}

CURVE_KEY = "CARCASSONNE_V29_MEEPLE_CURVE"
#: The frozen v2.9 substrate curve (7fc930b8) — the RULER-side base.
CURVE100 = "-8,-4,-1,0,2,3,4,5"
#: C5 curve125 = curve100 x1.25 exactly. The adopted champion leaf (CL-051,
#: 2026-07-13). Mirrors governance/PRODUCTION.yaml champion.leaf_config.
CURVE125 = "-10,-5,-1.25,0,2.5,3.75,5,6.25"

# Implementation dispatch (governance/PRODUCTION.yaml champion.env_knobs).
#   USE_FLAT_LEAF  defaults OFF -> MUST be set.
#   USE_CY_REPR    defaults OFF -> MUST be set.
#   USE_CY_LEAF    defaults ON  (`os.environ.get(..., "1") != "0"`), so setting it
#                  to "1" is a no-op; it is spelled out so the block matches
#                  PRODUCTION.yaml env_knobs and so `--export` is self-describing.
_DISPATCH: dict[str, str] = {
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
}
# The PLAY sites historically omit USE_CY_LEAF. Because its default is ON the
# resolved dispatch is identical either way, but the KEY SET is what
# `android_bridge.RESOLVED_ENV` stamps into on-device manifests and what
# `tests/android/test_bridge.py` compares, so the omission is preserved verbatim
# rather than "tidied" — changing a shipped manifest schema is not this module's
# call to make.
_DISPATCH_PLAY: dict[str, str] = {
    k: v for k, v in _DISPATCH.items() if k != "CARCASSONNE_USE_CY_LEAF"
}

# Net-free CPU stack: no GPU, no BLAS thread pools. Result-neutral — a fair game
# is a Cython leaf + PUCT tree + the marginalized solver, with no matmul anywhere.
#
# ⚠️ KNOWN DEFECT, PRESERVED ON PURPOSE — DO NOT FIX SILENTLY.
# The installed numpy is scipy-OpenBLAS (DYNAMIC_ARCH), NOT MKL, so OMP_NUM_THREADS
# and MKL_NUM_THREADS are INERT for the real BLAS backend. Left unpinned, OpenBLAS
# spawns a box-sized busy-waiting pool per forked worker; that is the root cause of
# the curve175 n=400 clairvoyant hang (root-caused 2026-07-13, commit e006036).
# The eval harnesses learned this and pin OPENBLAS/NUMEXPR/VECLIB (_THREADS_FULL).
# The PLAY sites never got the fix and still carry only the inert pair, so a
# multi-worker play/bench harness on this profile has the same latent hang risk.
# Promoting PLAY to _THREADS_FULL is a one-line change and is leaf-value-neutral,
# but it is an owner decision (it changes the Android runtime's thread behaviour),
# so it is REPORTED, not taken. Consolidation preserved the current values exactly.
_THREADS_MIN: dict[str, str] = {
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
_THREADS_FULL: dict[str, str] = {
    **_THREADS_MIN,
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}

# --------------------------------------------------------------------------- #
# The profiles.                                                               #
# --------------------------------------------------------------------------- #

#: Production PLAY env — curve125 in the environment (the env IS the leaf here).
PLAY: dict[str, str] = {
    **_LEAF_SHAPE, CURVE_KEY: CURVE125, **_DISPATCH_PLAY, **_THREADS_MIN,
}

#: Eval-harness env — curve100 base; champion_factory injects curve125 on the
#: champion side only, leaving fixed rulers/anchors on the frozen substrate.
RULER: dict[str, str] = {
    **_LEAF_SHAPE, CURVE_KEY: CURVE100, **_DISPATCH, **_THREADS_FULL,
}

PROFILES: dict[str, dict[str, str]] = {"play": PLAY, "ruler": RULER}

#: The PLAY subset that `virtual_score_v2._config_from_env()` actually reads —
#: i.e. the keys that freeze DEFAULT_CONFIG. `scripts/rustport/prod_leaf_env`
#: applies ONLY these: the rustport gates build every LeafConfig explicitly and
#: were gated with the dispatch knobs as they found them, so flipping dispatch
#: there would change which implementation a passed gate is evidence about.
PLAY_SHAPE: dict[str, str] = {**_LEAF_SHAPE, CURVE_KEY: CURVE125}
SHAPE_KEYS: tuple[str, ...] = tuple(PLAY_SHAPE)


# --------------------------------------------------------------------------- #
# API                                                                          #
# --------------------------------------------------------------------------- #
def _resolve(profile: dict[str, str] | str | None) -> dict[str, str]:
    if profile is None:
        return PLAY
    if isinstance(profile, str):
        try:
            return PROFILES[profile]
        except KeyError:
            raise KeyError(
                f"unknown prod_env profile {profile!r}; "
                f"expected one of {sorted(PROFILES)}") from None
    return profile


def apply(profile: dict[str, str] | str | None = None) -> dict[str, str]:
    """Fill any UNSET knob of ``profile`` (default ``PLAY``); return the resolved subset.

    ``setdefault`` semantics: an environment that already carries a knob wins, so a
    launcher or orchestrator can override without editing this file.

    ⚠️ MUST be called before the first ``carcassonne_ai`` / ``wingedsheep`` import —
    see the module docstring. Idempotent.
    """
    env = _resolve(profile)
    for k, v in env.items():
        os.environ.setdefault(k, v)
    return resolved(env)


def resolved(profile: dict[str, str] | str | None = None) -> dict[str, str]:
    """The profile's keys as they stand in ``os.environ`` RIGHT NOW.

    Capture this immediately after ``apply()`` and stamp THAT into manifests: a
    later importer may rewrite ``os.environ``, but it can no longer change the leaf
    this process already froze, so the captured snapshot is the honest record.
    """
    env = _resolve(profile)
    return {k: os.environ.get(k, "") for k in env}


def verify(profile: dict[str, str] | str | None = None, *,
           keys: tuple[str, ...] | None = None) -> dict[str, str]:
    """RAISE ``RuntimeError`` unless every knob of ``profile`` matches ``os.environ``.

    Use at a site that must fail loudly rather than run a mis-shaped leaf. Pass
    ``keys`` to check a subset (e.g. ``SHAPE_KEYS`` — only the DEFAULT_CONFIG-forming
    knobs — when the dispatch knobs are deliberately left as found).
    """
    env = _resolve(profile)
    want = {k: env[k] for k in (keys or tuple(env))}
    bad = {k: (v, os.environ.get(k)) for k, v in want.items()
           if os.environ.get(k) != v}
    if bad:
        lines = "\n".join(
            f"  {k}: expected {exp!r}, got {got!r}" for k, (exp, got) in sorted(bad.items()))
        raise RuntimeError(
            "production leaf environment mismatch — the leaf this process froze is NOT "
            "the champion's.\n" + lines +
            "\nDid something import carcassonne_ai before prod_env.apply()? The knobs are "
            "latched at import; setting them afterwards is too late (see prod_env docstring).")
    return dict(want)


def _shell_quote(v: str) -> str:
    return "'" + v.replace("'", "'\\''") + "'"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    p = argparse.ArgumentParser(
        prog="python -m carcassonne_ai.prod_env",
        description="Emit the canonical production leaf environment for shell launchers.")
    p.add_argument("--profile", default="play", choices=sorted(PROFILES),
                   help="play = curve125 in env (deployed play); "
                        "ruler = curve100 base (eval harnesses; factory injects curve125)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--export", action="store_true",
                   help="POSIX `export K='V'` lines, safe to eval (default)")
    g.add_argument("--json", action="store_true", help="the mapping as JSON")
    a = p.parse_args(argv)

    env = PROFILES[a.profile]
    if a.json:
        print(json.dumps(env, indent=2, sort_keys=True))
    else:
        for k, v in env.items():
            print(f"export {k}={_shell_quote(v)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
