#!/usr/bin/env python3
"""Build the Cython board-encoder extension in place.

One command (from the repo root, any venv with cython+setuptools):

    python setup_flat_repr_cy.py build_ext --inplace

This drops `carcassonne_ai/flat_repr_cy.cpython-3xx-*.so` next to
`src/carcassonne_ai/board_repr.py`. Nothing imports it unless
CARCASSONNE_USE_CY_REPR=1 (see board_repr.USE_CY_REPR) or a script imports
`carcassonne_ai.flat_repr_cy` explicitly (the reconcile/bench scripts do).

Sibling of setup_flat_leaf_cy.py — same per-box `.so` build/copy story
(cpython-3xx-arch specific, gitignored).
"""
from Cython.Build import cythonize
from setuptools import Extension, setup

setup(
    name="flat_repr_cy",
    ext_modules=cythonize(
        [
            Extension(
                "carcassonne_ai.flat_repr_cy",
                ["src/carcassonne_ai/flat_repr_cy.pyx"],
                extra_compile_args=["-O3"],
            )
        ],
        compiler_directives={"language_level": "3"},
    ),
    package_dir={"": "src"},
    zip_safe=False,
)
