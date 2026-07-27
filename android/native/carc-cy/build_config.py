"""Single source of truth for what the ``carc-cy`` wheel contains.

Imported by BOTH build paths so they cannot drift:

* ``setup.py``                  — the ordinary desktop / sdist build (real pip).
* ``android/tools/build_cy_wheels.py`` — the Android cross-build (NDK clang).

The ``.pyx`` files themselves are NOT stored here. They are copied in from
``src/carcassonne_ai/`` by the sync step (see ``build_cy_wheels.py --sync-only``)
and are gitignored, so the repo keeps exactly one copy of each source.
"""
from __future__ import annotations

# Import package the extensions live in inside the wheel.
#
# ⚠️ Deliberately NOT ``carcassonne_ai``. On device the ``carcassonne_ai`` package is
# delivered by Chaquopy's *source* asset (app.imy) while pip requirements land in a
# *separate* asset (requirements-*.imy). Python's path finder binds a package's
# ``__path__`` to the first sys.path entry that provides it, so a package split across
# those two finders would make ``carcassonne_ai.flat_leaf_cy`` unimportable. Shipping a
# standalone top-level package and aliasing it into ``sys.modules`` (see
# ``android_bridge._install_cy_aliases``) sidesteps the split entirely.
PACKAGE = "carc_cy"

# Distribution name. pip normalises ``carc_cy`` <-> ``carc-cy``; Chaquopy's
# pip_install.py rebuilds the requirement for the 2nd..Nth ABI as
# ``dist_info_name.replace("_", "-") == version``, so both spellings must round-trip.
DIST_NAME = "carc-cy"

# Extension module basenames. Each maps to ``src/carcassonne_ai/<name>.pyx`` upstream
# and to ``carc_cy/<name>.so`` inside the wheel.
MODULES: tuple[str, ...] = ("flat_leaf_cy", "flat_repr_cy")

# Where the canonical .pyx sources live, relative to the repo root.
PYX_SOURCE_DIR = "src/carcassonne_ai"

# Android ABIs to cross-build, and the clang target triple for each.
ABI_TRIPLES: dict[str, str] = {
    "arm64-v8a": "aarch64-linux-android",
    "x86_64": "x86_64-linux-android",
}

# Wheel platform-tag API level. 21 matches Chaquopy's own published wheels
# (e.g. numpy-1.26.2-0-cp312-cp312-android_21_arm64_v8a.whl). pip's
# ``packaging.tags.android_platforms()`` yields every level from the target minSdk
# down to 16, so an android_21 wheel stays installable at minSdk 26.
ANDROID_API = 21

# CPython shipped by Chaquopy 17.0.0 (verified against the version string in the
# libpython3.12.so it packages). Determines the ``com.chaquo.python:target`` artifact
# we pull Android headers + libpython from.
PYTHON_VERSION = "3.12"
TARGET_ARTIFACT_VERSION = "3.12.12-0"
