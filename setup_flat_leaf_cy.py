#!/usr/bin/env python3
"""Build the Cython flat-leaf extension in place.

One command (from the repo root, any venv with cython+setuptools):

    python setup_flat_leaf_cy.py build_ext --inplace

This drops `carcassonne_ai/flat_leaf_cy.cpython-3xx-*.so` next to
`src/carcassonne_ai/flat_leaf.py`. Nothing imports it unless
CARCASSONNE_USE_CY_LEAF=1 (see flat_leaf.USE_CY_LEAF) or a script imports
`carcassonne_ai.flat_leaf_cy` explicitly (the reconcile/bench scripts do).
"""
from Cython.Build import cythonize
from setuptools import Extension, setup

setup(
    name="flat_leaf_cy",
    ext_modules=cythonize(
        [
            Extension(
                "carcassonne_ai.flat_leaf_cy",
                ["src/carcassonne_ai/flat_leaf_cy.pyx"],
                extra_compile_args=["-O3"],
            )
        ],
        compiler_directives={"language_level": "3"},
    ),
    package_dir={"": "src"},
    zip_safe=False,
)
