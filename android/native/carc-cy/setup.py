#!/usr/bin/env python3
"""Desktop / sdist build of the ``carc-cy`` extension package.

    pip install ./android/native/carc-cy

This is the ORDINARY build path and it is what makes ``carc-cy`` a genuine
pip-installable package. It is NOT the path that produces the Android wheels:
Chaquopy 17's pip runs with ``--only-binary :all:`` and refuses to compile native
code (``error: CCompiler.compile: Chaquopy cannot compile native code``), so the
Android artefacts are cross-compiled ahead of time by
``android/tools/build_cy_wheels.py`` and handed to Chaquopy as finished wheels.

Both paths read ``build_config.py`` so the module list cannot drift.

The ``.pyx`` sources are gitignored copies synced from ``src/carcassonne_ai/``.
Run the sync first if they are absent:

    python3 android/tools/build_cy_wheels.py --sync-only
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from setuptools import Extension, setup

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build_config import MODULES, PACKAGE  # noqa: E402

missing = [m for m in MODULES if not (HERE / PACKAGE / f"{m}.pyx").is_file()]
if missing:
    raise SystemExit(
        f"carc-cy: missing synced sources {missing} in {HERE / PACKAGE}.\n"
        "These are gitignored copies of src/carcassonne_ai/*.pyx. Sync them with:\n"
        "    python3 android/tools/build_cy_wheels.py --sync-only"
    )

try:
    from Cython.Build import cythonize
except ImportError:  # pragma: no cover - build-time only
    raise SystemExit("carc-cy: Cython is required to build (pip install Cython>=3.0)")

setup(
    name="carc-cy",
    # Content-addressed by the caller so a .pyx edit always yields a new version and
    # can never be served from a stale pip/wheel cache. See build_cy_wheels.py.
    version=os.environ.get("CARC_CY_VERSION", "0.0.0.dev0"),
    description="Cython fast paths (flat leaf + board encoder) for Carcassonne AI",
    packages=[PACKAGE],
    ext_modules=cythonize(
        [
            Extension(
                f"{PACKAGE}.{m}",
                [str(Path(PACKAGE) / f"{m}.pyx")],
                extra_compile_args=["-O3"],
            )
            for m in MODULES
        ],
        compiler_directives={"language_level": "3"},
    ),
    zip_safe=False,
)
