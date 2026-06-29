"""measurement_infra — reusable measurement infrastructure (NOT a strength lever).

Promoted from the post-search-residual pilot (CL-035 / Decision C, which CLOSED adaptive compute as a
strength lever). These primitives are for building and targeting MEASUREMENT datasets cheaply:

  - root_replay   : lossless position reconstruction from (deck_seed, action_sequence, ply)
  - snapshot      : one deep search snapshotted at many sim levels (bit-exact to standalone h_L)
  - tagging       : h200 top-2 Q-gap (+ diagnostics) on every root
  - labeling_queue: adaptive 4-strata queue (ordinary / low_top2gap / opening_heavy / close_score)

See README.md. Importable either as a package (`from measurement_infra import snapshot_search`) or by
adding this dir to sys.path and importing the submodules by name.
"""
import sys as _sys
from pathlib import Path as _Path

_HERE = _Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in (_REPO / "src", _REPO / "scripts" / "level2", _HERE):
    if str(_p) not in _sys.path:
        _sys.path.insert(0, str(_p))

from root_replay import RootRef, GameRecord, replay_actions, load_games, save_games, load_games_dict  # noqa: E402,F401
from snapshot import (  # noqa: E402,F401
    DEFAULT_LEVELS, FROZEN_V29_HASH, FROZEN_V29_ENV, set_frozen_v29_env, frozen_v29_cfg,
    make_heuristic_agent, read_children, snapshot_search, best_action_from, verify_equivalence,
)
from tagging import tag_from_snaps, tag_root, is_low_top2gap  # noqa: E402,F401
from labeling_queue import AdaptiveLabelingQueue  # noqa: E402,F401
