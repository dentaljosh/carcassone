"""Test-infra only (leaf-rewrite branch). Lets the WHOLE suite run under the
compact-leaf path so we can prove `pytest green with the toggle ON` — set
CARC_TEST_COMPACT_LEAF=1. No effect on production (default OFF, never imported by
runtime code)."""
import os


def pytest_configure(config):
    if os.environ.get("CARC_TEST_COMPACT_LEAF") == "1":
        from carcassonne_ai import virtual_score as _vs

        _vs.USE_COMPACT_LEAF = True
        print("\n[conftest] USE_COMPACT_LEAF forced ON for this session")
