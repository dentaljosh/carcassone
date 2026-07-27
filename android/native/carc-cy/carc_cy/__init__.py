"""Compiled Cython fast paths for the Carcassonne engine, packaged for Android.

Contains two extension modules, cross-compiled from the canonical sources in
``src/carcassonne_ai/``:

* ``flat_leaf_cy``  — the v2.7 flat leaf evaluator (``flat_virtual_score_v2_cy``)
* ``flat_repr_cy``  — the board encoder (``encode_board_cy``)

Upstream code imports these as ``carcassonne_ai.flat_leaf_cy`` /
``carcassonne_ai.flat_repr_cy``. They ship under this separate top-level package
because on device ``carcassonne_ai`` arrives via Chaquopy's *source* asset while pip
requirements arrive via a *different* asset, and a package cannot span the two (see
``build_config.PACKAGE``). ``android_bridge._install_cy_aliases`` republishes them
under the expected dotted names at startup, which is what the lazy
``from . import flat_leaf_cy`` inside ``flat_leaf.py`` then resolves against.

Importing this package does NOT import the extensions; do that explicitly.
"""

__all__ = ["flat_leaf_cy", "flat_repr_cy"]
