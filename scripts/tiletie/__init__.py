"""tiletie — leaf top-2 tie-structure census (TILE decisions only).

Answers: does the production leaf's reported 55.1% top-2 exact-tie rate on TILE
placements (measured on the JCloisterZone corpus by
``scripts/jcz_mining/mine_disagreements.py``) replicate on OUR OWN position
distributions, and what is the tie SIZE / gap / phase structure? Leaf
evaluations only — no search, no oracle scoring.

  - chain_census : the shared library (`chain_values`, `tie_report`,
                    `census_ply`, `build_leaf`, `prepare_env`, ...)
  - run_census    : the driver (one subprocess per rules profile; merges legs
                     into rows.jsonl / manifest.json / summary.json / CENSUS.md)

Importable either as a package (`from tiletie import chain_census`) or by adding
this directory to `sys.path` and importing the submodules by name (the pattern
`run_census.py`'s subprocess relaunch uses, mirroring
`scripts/measurement_infra/__init__.py`).
"""
import sys as _sys
from pathlib import Path as _Path

_HERE = _Path(__file__).resolve().parent
if str(_HERE) not in _sys.path:
    _sys.path.insert(0, str(_HERE))

from chain_census import (  # noqa: E402,F401
    LEAF_HASH_OF_RECORD, TIE_EPS_GRID, PHASE_CUTS, TIE_ACTIONS_CAP, ROW_SCHEMA_KEYS,
    phase_bucket, tercile_of, prepare_env, build_leaf,
    chain_values, argmax_chain, tie_report, census_ply,
)
