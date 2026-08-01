"""JSON bridge between the Kotlin/Compose app and the production Carcassonne champion.

This is the ONLY hand-written Python under ``android/``. Everything else in the
on-device bundle is copied verbatim from the repo by ``android/tools/sync_python.py``.

DESIGN CONTRACTS
----------------
1. **Importable on desktop.** No ``android`` / ``java`` / ``com.chaquo`` imports, so the
   whole API is pytest-able (``tests/android/test_bridge.py``) and drivable from
   ``android/tools/smoke_selfplay.py``.
2. **Production leaf env FIRST.** The v2.7/v2.9 leaf reads ``CARCASSONNE_*`` knobs at
   *library import time*; ``champion_factory``'s verify RAISES if they were not set. So
   this module applies them via ``os.environ.setdefault`` at module top, BEFORE the
   first ``carcassonne_ai`` import. The values are a literal copy of
   ``scripts/human_anchor/env_preamble.PROD_ENV`` (that file is not in the on-device
   bundle); ``tests/android/test_bridge.py::test_prod_env_matches_repo_preamble``
   asserts the copy has not drifted.
3. **The YAML is the champion.** No strength knob is hardcoded here.
   ``champion_factory.PRODUCTION_YAML`` is a module global resolved at call time, so we
   point it at the bundled ``carcassonne_ai/data/PRODUCTION.yaml`` when that exists
   (device) and leave the repo's ``governance/PRODUCTION.yaml`` otherwise (desktop).
4. **All in/out is a JSON string** — Chaquopy marshals ``str`` cleanly and nothing else
   needs a type mapping. Every response is a JSON object carrying ``ok``; failures are
   ``{"ok": false, "error": {"code", "message"}}`` and never raise across the bridge.
5. **Determinism / save-restore.** The engine touches the global ``random`` stream in
   exactly one place (the deck shuffle inside ``get_init_board``), so a game is fully
   determined by ``(deck_seed, action_log)`` — the ``root_replay.py`` contract. Restore
   replays the log and re-seats the agent's ``_move_idx`` (its per-move search seeds are
   derived from it) and its exact-endgame latch.

THREADING (what Kotlin must respect)
------------------------------------
``new_game`` / ``apply_action`` / ``ai_move`` / ``save_game`` / ``restore_game`` mutate
the single module session and must all run on ONE thread (the app uses a single-thread
coroutine dispatcher). ``get_progress`` is the sole exception: it reads module-global
ints only and is safe to poll from the UI thread while ``ai_move`` blocks.
"""
from __future__ import annotations

import json
import os
import platform
import random
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# 1. Production leaf env — MUST precede any carcassonne_ai import.             #
#    Literal copy of scripts/human_anchor/env_preamble.PROD_ENV (2026-07-27).  #
# --------------------------------------------------------------------------- #
PROD_ENV: dict[str, str] = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
for _k, _v in PROD_ENV.items():
    os.environ.setdefault(_k, _v)
# The knobs as they stood the instant before carcassonne_ai was first imported — i.e.
# the leaf shape this process actually froze into ``virtual_score_v2.DEFAULT_CONFIG``.
# (A later importer may rewrite os.environ; that no longer changes this process's leaf,
# so RESOLVED_ENV, not os.environ, is the honest record for a manifest or a test.)
RESOLVED_ENV: dict[str, str] = {k: os.environ.get(k, "") for k in PROD_ENV}

# On-device endgame-solver NODE budget (measurement/ANDROID_WALLCLOCK_MEMO_20260728.md,
# lever #1). The desktop default is 2,000,000 nodes; the budget has no wall-clock
# component and PythonBridge.reset() queues BEHIND a running ai_move, so on a phone a
# runaway solve is an uncancellable hang with a progress-less spinner.
#
# Largest solve observed to date: 2,214 nodes across the memo's 9 endgames, and 7,067
# nodes in a 3-position Tier-1-prefix probe run while wiring this up — so the observed
# tail is WIDER than the memo's sample suggested, and 100,000 is ~14x the largest solve
# seen anywhere (not the ~45x the memo estimated off 2,214). Still a bound that should
# never fire (0 budget hits in 400 screen games), but the margin is thinner than it
# looks and is worth re-checking if more endgames are ever sampled. If it DOES fire,
# that ONE decision falls back to fair PIMC (stamped on agent.manifest).
ANDROID_EXACT_BUDGET: int = 100_000

# --------------------------------------------------------------------------- #
# 1a. THE MOBILE BUDGET PROFILE (added 2026-07-29 with the k8x1376 promotion).  #
#                                                                              #
# On 2026-07-29 the DESKTOP deploy budget was promoted k4x688 (2752) ->         #
# k8x1376 (11008), which is +49.85 elo (CL-060, paired z 3.48) and is only      #
# clock-legal because the k determinization worlds are split across 8 spawn     #
# processes (6.37x, 2.16 s/move).                                               #
#                                                                              #
# ⚠️ THE PHONE CANNOT DO THAT. Chaquopy has no `multiprocessing`, so on-device   #
# the ONLY available execution is the sequential k-loop -> 11008 sims would     #
# cost ~25 s/move (4.26x the measured 1.7 s/move at 2752). So PRODUCTION.yaml    #
# carries `champion.fair_deploy.deploy_profiles.mobile` pinning this platform   #
# at k4x688, and this module resolves THAT, not the champion-of-record fields.  #
#                                                                              #
# DESIGN CONTRACT 3 ("the YAML is the champion, no strength knob is hardcoded   #
# here") is preserved: the numbers still come from the YAML. The constant below #
# is a FAIL-CLOSED floor for the one case the contract cannot cover — a bundled #
# YAML with no `mobile` profile, where inheriting the champion budget would ship #
# a 25 s/move hang. It must never be read when the profile is present.          #
#                                                                              #
# The phone is therefore running a WEAKER agent than the champion of record     #
# (same family, same leaf a36d2e15, same priors, same exact-K<=2 tail; only the #
# budget differs). `champion_factory` stamps `runtime_budget_override` on the   #
# manifest automatically, so every archived game says which budget played —     #
# E4 human-vs-champion games must be graded against k4x688.                     #
# --------------------------------------------------------------------------- #
ANDROID_DEPLOY_PROFILE: str = "mobile"
ANDROID_FALLBACK_BUDGET: dict[str, int] = {"k_dets": 4, "sims_per_det": 688}

# Desktop convenience: when the repo tree is visible above this file and the package is
# not installed, make src/ importable. On device this resolves to a path that does not
# exist and is skipped. (android/app/src/main/python/android_bridge.py -> parents[4] is
# `android`, parents[5] is the repo root.)
_HERE = Path(__file__).resolve()
_MAYBE_REPO = _HERE.parents[5] if len(_HERE.parents) > 5 else None
if _MAYBE_REPO is not None and (_MAYBE_REPO / "src" / "carcassonne_ai").is_dir():
    _src = str(_MAYBE_REPO / "src")
    if _src not in sys.path:
        sys.path.append(_src)   # append, never prepend: an installed copy still wins

# --------------------------------------------------------------------------- #
# 1b. Cython fast paths — republish carc_cy.* under their carcassonne_ai names. #
#                                                                              #
# The compiled extensions ship in a standalone `carc_cy` wheel (see            #
# android/native/carc-cy). They CANNOT ship inside `carcassonne_ai` itself: on  #
# device that package arrives via Chaquopy's *source* asset while pip           #
# requirements arrive via a *separate* asset, and Python binds a package's      #
# __path__ to the first sys.path entry that provides it — so a package split    #
# across the two finders would make `carcassonne_ai.flat_leaf_cy` unimportable. #
#                                                                              #
# Aliasing into sys.modules is what the LAZY `from . import flat_leaf_cy` in    #
# flat_leaf.py (and `from .flat_repr_cy import ...` in board_repr.py) then      #
# resolves against. Must run BEFORE the first leaf evaluation, because both     #
# sites cache a False sentinel on ImportError and never retry.                  #
# No wheel (desktop, or an NDK-less build) -> stays pure Python, which is       #
# correct, just slower.                                                        #
# --------------------------------------------------------------------------- #
CY_MODULES: tuple[str, ...] = ("flat_leaf_cy", "flat_repr_cy")


def _install_cy_aliases() -> dict[str, bool]:
    """Map ``carc_cy.<m>`` onto ``carcassonne_ai.<m>``. Returns which ones loaded."""
    import importlib

    loaded: dict[str, bool] = {}
    for name in CY_MODULES:
        target = f"carcassonne_ai.{name}"
        if target in sys.modules:            # already importable the ordinary way
            loaded[name] = True
            continue
        try:
            mod = importlib.import_module(f"carc_cy.{name}")
        except ImportError:
            loaded[name] = False
            continue
        sys.modules[target] = mod
        loaded[name] = True
    if any(loaded.values()):
        # Also bind on the parent package, so plain attribute access agrees with
        # sys.modules (CPython's IMPORT_FROM falls back to sys.modules, but only
        # after an AttributeError — this keeps the two views consistent).
        try:
            import carcassonne_ai as _ca
            for name, got in loaded.items():
                if got:
                    setattr(_ca, name, sys.modules[f"carcassonne_ai.{name}"])
        except ImportError:
            pass
    return loaded


CY_LOADED: dict[str, bool] = _install_cy_aliases()

import numpy as np  # noqa: E402

from carcassonne_ai import champion_factory  # noqa: E402
from carcassonne_ai.action_space import (  # noqa: E402
    decode,
    meeple_pass_index,
    tile_action_count,
    tile_pass_index,
)
from carcassonne_ai.game_wrapper import RETAIL_START_TILE, Board, Game  # noqa: E402
# The intra-tile meeple grouping of record. It USED to be defined in this file; it moved
# into the package (2026-07-27) when the search grew a MEEPLE-DEDUP mode that needs the
# same definition, and a second copy would drift. Re-exported here so `feature_groups`
# stays part of this module's API for existing importers (the census, tests/android).
from carcassonne_ai.meeple_equiv import feature_groups  # noqa: E402,F401
from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction  # noqa: E402
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate import Coordinate  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402

SAVE_SCHEMA = "carcassonne-android-save/v1"
STATE_SCHEMA = "carcassonne-android-state/v1"
# A finished game's permanent record. A SUPERSET of a save: the same restorable
# (deck_seed, actions) core plus the read-only result summary, so `filesDir/games/`
# is both a scoreboard and a replay archive. See `archive_record`.
ARCHIVE_SCHEMA = "carcassonne-android-archive/v1"

# Start-tile convention (2026-07-30, Joshua-approved for the APP ONLY).
#   "engine" — the vendored engine's native rule: the first player draws a RANDOM
#              tile which is auto-placed at starting_position, costing them a turn
#              and giving them a free meeple on it. Every training run, eval and
#              solver measurement to date used this; it stays the library default.
#   "retail" — retail/tournament: a fixed "D" tile (city + straight road) is
#              pre-placed before anyone draws. Nobody spends a turn on it, no
#              meeple goes on it, and the deck is the remaining 71.
# The app plays "retail". This travels in the SAVE PAYLOAD, so a game archived
# under "engine" replays under "engine" forever — the (deck_seed, actions) core is
# only lossless with respect to the rules it was played under.
START_RULE_ENGINE = "engine"
START_RULE_RETAIL = "retail"
START_RULE = START_RULE_RETAIL          # what a NEW app game uses
START_RULE_LEGACY = START_RULE_ENGINE   # what a save with no `start_rule` means

# --------------------------------------------------------------------------- #
# Agent backend (P7). DEFAULT IS UNCHANGED: the Python champion.                #
#                                                                              #
# "rust" swaps ONLY the opponent's move choice for `carc_rs.FairAgentRs`, the   #
# bit-exact port gated at G1-G5. The Python engine stays authoritative for      #
# everything else — legality, UI, scoring, the save/archive record — so the     #
# switch cannot change what a game IS, only who picks the champion's move.      #
#                                                                              #
# It is OPT-IN and stays opt-in until Joshua flips it: the phone keeps playing  #
# the Python k4x688 path. Selectable per game via new_game's `backend` key, or  #
# process-wide via CARC_ANDROID_BACKEND for a test harness.                     #
# --------------------------------------------------------------------------- #
BACKEND_PYTHON = "python"
BACKEND_RUST = "rust"
BACKEND_DEFAULT = os.environ.get("CARC_ANDROID_BACKEND", BACKEND_PYTHON)

# The libm flavour bionic actually implements, MEASURED on a Pixel 9 Pro at G7
# leg 1 (measurement/rustport_p7/G7_libm_device.json): `tanh`/`expm1` are msun,
# exact on the production corpus AND 10^7 fuzz args. It differs from the desktop
# (glibc_fma, G0 §2) — which is exactly why the flavour is a config knob and not
# a compile-time constant. `glibc` passes the tanh CORPUS here and fails the
# fuzz, so do not re-derive this from a corpus-only run.
ANDROID_TANH_FLAVOR = "msun"
# Scalar `exp` matched exp64_fma (0/201,525 corpus, 0/10^7 fuzz) on the same run.
ANDROID_EXP_FMA = True

# Per-ply mirror assertion. Off by default (it renders the board twice per
# action); the game-start check runs unconditionally either way.
_RS_RECONCILE = os.environ.get("CARC_RS_RECONCILE", "") == "1"

# Meeple-dot placement, as RATIOS of the tile size, lifted from
# CarcassonneVisualiser.meeple_position_offsets (tile_size=60, meeple_size=~21). The
# visualiser itself is excluded from the bundle (tkinter/PIL), so the numbers travel
# here and the Compose canvas multiplies them by its own tile size.
MEEPLE_OFFSET_RATIO: dict[str, tuple[float, float]] = {
    "top": (0.5, 0.175),
    "right": (0.825, 0.5),
    "bottom": (0.5, 0.825),
    "left": (0.175, 0.5),
    "center": (0.5, 0.5),
    "top_left": (0.25, 0.175),
    "top_right": (0.75, 0.175),
    "bottom_left": (0.25, 0.825),
    "bottom_right": (0.75, 0.825),
}


# --------------------------------------------------------------------------- #
# 2. Bundled PRODUCTION.yaml                                                    #
# --------------------------------------------------------------------------- #
def _resolve_production_yaml() -> str:
    """Point ``champion_factory.PRODUCTION_YAML`` at the bundled YAML when present.

    On device the package lives at ``<bundle>/carcassonne_ai/`` and the factory's
    ``REPO = parents[2]`` guess is meaningless, so the bundled copy at
    ``carcassonne_ai/data/PRODUCTION.yaml`` is authoritative. On desktop that file does
    not exist and the factory's repo path is already correct."""
    import carcassonne_ai

    bundled = Path(carcassonne_ai.__file__).resolve().parent / "data" / "PRODUCTION.yaml"
    if bundled.is_file():
        champion_factory.PRODUCTION_YAML = bundled
        return str(bundled)
    return str(champion_factory.PRODUCTION_YAML)


PRODUCTION_YAML_PATH = _resolve_production_yaml()


def mobile_budget(spec=None) -> dict:
    """The per-move budget THIS PLATFORM runs — the YAML's ``mobile`` deploy profile.

    Returns ``{"k_dets", "sims_per_det", "total_sims", "profile", "from_yaml"}``.

    FAIL-CLOSED, and that is the whole point of the function: if the bundled YAML has no
    ``mobile`` profile (an old bundle, a hand-edited file), we fall back to
    ``ANDROID_FALLBACK_BUDGET`` — **never** to ``spec.k_dets``/``spec.sims_per_det``.
    Since 2026-07-29 the champion of record is k8x1376 = 11008 sims, which on a phone is
    ~25 s/move sequentially (no ``multiprocessing`` under Chaquopy), so inheriting it
    silently is the exact failure this guards. ``from_yaml=False`` in the response says
    the fallback fired."""
    spec = spec or champion_factory.load_production_spec()
    prof = champion_factory.deploy_profile(ANDROID_DEPLOY_PROFILE, spec)
    if prof["found"]:
        k, s = int(prof["k_dets"]), int(prof["sims_per_det"])
    else:
        k = int(ANDROID_FALLBACK_BUDGET["k_dets"])
        s = int(ANDROID_FALLBACK_BUDGET["sims_per_det"])
    return {"k_dets": k, "sims_per_det": s, "total_sims": k * s,
            "profile": ANDROID_DEPLOY_PROFILE, "from_yaml": bool(prof["found"])}


def _shim_factory_repo() -> str | None:
    """Make ``champion_factory._hashers()``'s sys.path inserts harmless on device.

    The factory inserts ``REPO/scripts/classical_search`` and
    ``REPO/scripts/measurement_infra`` at ``sys.path[0]`` before importing the hash
    dialects. On device REPO resolves inside Chaquopy's AssetFinder tree where those
    dirs don't exist — and Chaquopy's path hook RAISES FileNotFoundError for a missing
    path entry (desktop CPython silently skips it), so the insert poisons the very next
    import and the champion can never construct. Worse, the entry stays in sys.path, so
    one failed construction poisons every import after it.

    Fix: when the real repo layout is absent, point REPO at a scratch dir that really
    contains those two (empty) subdirs. The inserted entries then exist and are
    harmlessly empty; the bundled top-level ``c5_leaf_override``/``snapshot`` modules
    satisfy the imports. Must run at import time, before the first construction.
    """
    if (champion_factory.REPO / "scripts" / "classical_search").is_dir():
        return None  # desktop checkout — leave it alone
    import tempfile

    shim = Path(tempfile.mkdtemp(prefix="carc_repo_shim_"))
    for rel in ("scripts/classical_search", "scripts/measurement_infra"):
        (shim / rel).mkdir(parents=True, exist_ok=True)
    champion_factory.REPO = shim
    return str(shim)


FACTORY_REPO_SHIM = _shim_factory_repo()


# --------------------------------------------------------------------------- #
# 3. Pure helpers (ported from scripts/play_vs_tier1_gui.py:118-188, no tkinter) #
# --------------------------------------------------------------------------- #
def legal_rotations_at_cell(game: Game, board: Board, row: int, col: int) -> list[int]:
    off = board.offset
    win = off.to_window(Coordinate(row=row, column=col))
    if win is None:
        return []
    wr, wc = win
    base = (wr * off.size + wc) * 4
    mask = game.get_valid_moves(board)
    return [r for r in range(4) if mask[base + r]]


def tile_action_index(off, row: int, col: int, rot: int) -> int:
    win = off.to_window(Coordinate(row=row, column=col))
    if win is None:
        raise ValueError(f"cell ({row},{col}) is outside the action window")
    wr, wc = win
    return (wr * off.size + wc) * 4 + rot


def all_legal_tile_cells(game: Game, board: Board) -> set[tuple[int, int]]:
    mask = game.get_valid_moves(board)
    off = board.offset
    n_tile = tile_action_count(off.size)
    cells: set[tuple[int, int]] = set()
    for idx in np.flatnonzero(mask[:n_tile]):
        cell, _rot = divmod(int(idx), 4)
        wr, wc = divmod(cell, off.size)
        coord = off.to_engine(wr, wc)
        cells.add((coord.row, coord.column))
    return cells


def legal_meeple_indices(game: Game, board: Board) -> list[int]:
    mask = game.get_valid_moves(board)
    off = board.offset
    n_tile = tile_action_count(off.size)
    pass_idx = meeple_pass_index(off.size)
    return [int(i) for i in np.flatnonzero(mask)
            if int(i) >= n_tile and int(i) != pass_idx]


def _terrain_name(tile, side: Side) -> str:
    t = tile.get_type(side)
    return t.name if t is not None else "GRASS"


def format_action(idx: int, board: Board) -> str:
    """Human-readable string for a flat action index in the board's current phase."""
    phase = board.state.phase.value
    if phase == "tiles":
        if idx == tile_pass_index(board.offset.size):
            return "pass (no legal placement)"
        action = decode(idx, off=board.offset, phase="tiles",
                        next_tile=board.state.next_tile)
        assert isinstance(action, TileAction)
        c = action.coordinate
        return f"tile @ ({c.row:+d}, {c.column:+d}) rot={action.tile_rotations}"
    if idx == meeple_pass_index(board.offset.size):
        return "skip meeple"
    last = board.state.last_tile_action
    last_coord = last.coordinate if last is not None else None
    action = decode(idx, off=board.offset, phase="meeples", last_tile_coord=last_coord)
    assert isinstance(action, MeepleAction)
    return f"{action.meeple_type.name} on {action.coordinate_with_side.side.name}"


def k_remaining(state) -> int:
    """Tiles left = undrawn deck + the one in hand (the fair_agent.k_remaining band)."""
    return len(state.deck) + (1 if state.next_tile is not None else 0)


# --------------------------------------------------------------------------- #
# 3b. What just happened — the last-move event summary                          #
# --------------------------------------------------------------------------- #
def _meeple_key(player: int, mp) -> tuple:
    cws = mp.coordinate_with_side
    return (int(player), int(cws.coordinate.row), int(cws.coordinate.column),
            str(cws.side.value), str(mp.meeple_type.value))


def _meeple_index(state) -> dict:
    """``{key: (player, MeeplePosition)}`` for every meeple standing on the board."""
    out = {}
    for player, positions in enumerate(state.placed_meeples):
        for mp in positions:
            out[_meeple_key(player, mp)] = (int(player), mp)
    return out


def scoring_events(prev_state, new_state, human_player: int, opponent_name: str,
                   claims: list | None = None) -> list[dict]:
    """What the just-applied action(s) actually paid, itemised.

    The board only *tells* you a score changed; it does not say why, and Base+Farmers
    pays in lumps large enough that "11 -> 17" with no explanation is the single most
    confusing thing about watching the champion play. This is the explanation.

    METHOD — a meeple leaving the board is the signal. The engine returns a meeple to
    its owner's hand exactly when the feature it was standing on completes and scores
    (``PointsCollector.remove_meeples_and_collect_points``, run at the END of the
    meeple sub-phase), so the meeples in ``prev_state`` but not in ``new_state`` are
    precisely the features that just paid out. Each one is re-found in the NEW state —
    ``find_city``/``find_road`` take a ``CoordinateWithSide`` and do not need a meeple,
    and the feature is *complete* there, so ``count_*_points`` returns the finished
    rate rather than the reduced one the previous state would have given.

    ``claims`` closes the one hole in that diff. A player may claim a feature the tile
    they just laid ALREADY completed — the meeple is placed and collected inside the
    same ``get_next_state``, so it is in neither state and the plain diff reports a
    score out of nowhere. The caller therefore passes the ``(player, MeeplePosition)``
    this decision placed, and it is treated as having been on the board. (Only the
    primary action can claim: ``auto_pass_forced`` applies passes, which never place
    a meeple.)

    Farmers are deliberately not handled: farms score only in the final pass, which
    this function refuses outright (see below).

    THREE HONESTY RULES, in the spirit of ``_final_breakdown``:

    * **A terminated state yields nothing.** The engine's endgame pass consumes EVERY
      remaining meeple inside the terminating action, so the diff would report the
      whole board closing at once. The result dialog's breakdown is the right surface
      for that, and it already exists.
    * **The itemisation must reconcile.** The per-player sum of what these events
      claim was paid is checked against the real score delta; if they disagree the
      whole list is replaced by a bare "+N" event. A wrong itemisation is worse than a
      coarse one.
    * **Nothing is mutated.** Both states are read; the meeple-consuming walk that
      ``aux_targets.extract_terminal_ownership`` needs a deepcopy for is not used here.
    """
    if new_state.is_terminated():
        return []
    prev_scores = [int(x) for x in prev_state.scores]
    new_scores = [int(x) for x in new_state.scores]
    n = min(len(prev_scores), len(new_scores))
    delta = [new_scores[p] - prev_scores[p] for p in range(n)]
    if not any(d > 0 for d in delta):
        return []

    def _who(winners: list[int]) -> str:
        names = [("You" if w == human_player else opponent_name) for w in winners]
        return " and ".join(names) if names else "nobody"

    def _generic() -> list[dict]:
        out = []
        for p in range(n):
            if delta[p] <= 0:
                continue
            out.append({
                "kind": "score", "points": delta[p], "winners": [p],
                "meeples_returned": 0,
                "text": f"{_who([p])} +{delta[p]}",
            })
        return out

    try:
        from wingedsheep.carcassonne.objects.meeple_type import MeepleType
        from wingedsheep.carcassonne.objects.terrain_type import TerrainType
        from wingedsheep.carcassonne.utils.city_util import CityUtil
        from wingedsheep.carcassonne.utils.points_collector import PointsCollector
        from wingedsheep.carcassonne.utils.road_util import RoadUtil

        before = _meeple_index(prev_state)
        for player, mp in (claims or []):
            before[_meeple_key(player, mp)] = (int(player), mp)
        after = _meeple_index(new_state)
        gone = [before[k] for k in before.keys() - after.keys()]
        if not gone:
            return _generic()

        # feature key -> {"kind", "points", "cells", "counts"}
        features: dict = {}
        for player, mp in gone:
            if mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                return _generic()      # a farm paid out mid-game: not a thing we model
            cws = mp.coordinate_with_side
            coord = cws.coordinate
            tile = new_state.board[coord.row][coord.column]
            if tile is None:
                return _generic()
            terrain = tile.get_type(cws.side)
            if terrain == TerrainType.CITY:
                feat = CityUtil.find_city(new_state, cws)
                kind, cells = "city", frozenset(feat.city_positions)
                points = int(PointsCollector.count_city_points(new_state, feat))
            elif terrain == TerrainType.ROAD:
                feat = RoadUtil.find_road(new_state, cws)
                kind, cells = "road", frozenset(feat.road_positions)
                points = int(PointsCollector.count_road_points(new_state, feat))
            elif terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                kind = "cloister"
                cells = frozenset({(int(coord.row), int(coord.column))})
                points = int(PointsCollector.chapel_or_flowers_points(new_state, coord))
            else:
                return _generic()
            entry = features.setdefault(
                (kind, cells), {"kind": kind, "points": points, "counts": [0] * n})
            if 0 <= player < n:
                entry["counts"][player] += 1

        events: list[dict] = []
        implied = [0] * n
        for entry in features.values():
            winners = [int(w) for w in
                       PointsCollector.get_winning_players(entry["counts"])]
            for w in winners:
                if 0 <= w < n:
                    implied[w] += entry["points"]
            returned = sum(entry["counts"])
            label = {"city": "City completed", "road": "Road completed",
                     "cloister": "Cloister completed"}[entry["kind"]]
            paid = ", ".join(
                f"{'You' if w == human_player else opponent_name} +{entry['points']}"
                for w in winners) or f"+{entry['points']}"
            back = (f", {returned} meeple{'' if returned == 1 else 's'} back"
                    if returned else "")
            events.append({
                "kind": entry["kind"],
                "points": entry["points"],
                "winners": winners,
                "meeples_returned": returned,
                "text": f"{label} — {paid}{back}",
            })

        if implied != delta[:n]:
            # The parts do not add up to the whole; say the honest coarse thing.
            return _generic()
        # Biggest payout first: the one line a glance catches should be the one that
        # moved the game most.
        events.sort(key=lambda e: -e["points"])
        return events
    except Exception:                             # noqa: BLE001 — never break a move
        return _generic()


# --------------------------------------------------------------------------- #
# 4. Progress counters — module globals, read WITHOUT the session lock.         #
# --------------------------------------------------------------------------- #
_prog_leaf_calls = 0        # cumulative evaluator calls for the CURRENT ai_move
_prog_expected = 0          # k_dets * sims (the nominal leaf budget)
_prog_t0 = 0.0              # perf_counter at ai_move entry; 0.0 == idle
_prog_thinking = False
_agent_ref = None           # the live agent, for a lock-free `_latched` read


def _wrap_evaluator_with_counter(agent) -> None:
    """Wrap ``agent._evaluator`` in a counting closure (the cheapest honest seam).

    ``FairHeuristicPriorAgent`` reads ``self._evaluator`` afresh on every
    ``NeuralMCTS`` construction inside ``_pimc_move``, so wrapping AFTER construction
    is picked up by every subsequent search. The wrapper forwards ``*args`` because
    ``NeuralMCTS`` calls ``evaluator(board)`` or ``evaluator(board, parent)`` depending
    on the evaluator's ``wants_parent`` flag (absent on the production evaluator)."""
    inner = getattr(agent, "_evaluator", None)
    if inner is None:                     # tier1 (RuleBasedPlayer) has no evaluator
        return

    def counting(*args):
        global _prog_leaf_calls
        _prog_leaf_calls += 1
        return inner(*args)

    if getattr(inner, "wants_parent", False):
        counting.wants_parent = True
    agent._evaluator = counting


# --------------------------------------------------------------------------- #
# 5. The session                                                                #
# --------------------------------------------------------------------------- #
class _Session:
    """Everything one game needs. One instance lives in the module global ``_S``."""

    def __init__(self, *, seed: int, human_player: int, opponent: str,
                 sims: int | None, k_dets: int | None, verify: bool,
                 generation: int, start_rule: str = START_RULE,
                 backend: str = BACKEND_DEFAULT):
        self.seed = int(seed)
        # Which start-tile convention this session plays under. New games use the
        # app default (retail); a RESTORE passes whatever the save recorded, so a
        # game archived before the retail start shipped still replays exactly.
        # Reject anything else rather than defaulting: silently picking a rule
        # would decode a DIFFERENT game from the same (deck_seed, actions).
        if start_rule not in (START_RULE_ENGINE, START_RULE_RETAIL):
            raise ValueError(
                f"unknown start_rule {start_rule!r}; expected "
                f"{START_RULE_ENGINE!r} or {START_RULE_RETAIL!r}")
        self.start_rule = str(start_rule)
        self.human_player = int(human_player)
        self.opponent_kind = str(opponent)
        self.req_sims = None if sims is None else int(sims)
        self.req_k_dets = None if k_dets is None else int(k_dets)
        self.verify = bool(verify)
        self.generation = int(generation)
        if backend not in (BACKEND_PYTHON, BACKEND_RUST):
            raise ValueError(f"unknown backend {backend!r}; expected "
                             f"{BACKEND_PYTHON!r} or {BACKEND_RUST!r}")
        self.backend = str(backend)
        # The Rust mirror, or None. `apply()` is the ONE place it is advanced.
        self.rs = None
        self.rs_note: str | None = None

        fixed_start = self.start_rule == START_RULE_RETAIL
        self.game = Game(enable_legal_moves_cache=True, fixed_start_tile=fixed_start)
        # The agent gets its OWN Game (mirrors play_vs_tier1_gui.build_opponent): the
        # UI-side Game carries a legal-moves cache and the agent may run on another
        # thread, so private Games remove any chance of a cross-thread cache race.
        # `fixed_start_tile` only affects get_init_board, which the agent's Game never
        # calls — it is passed for consistency, not because the search needs it.
        self.ai_game = Game(enable_legal_moves_cache=True, fixed_start_tile=fixed_start)

        self.agent = None
        self.pick = None
        self.manifest = None
        self.budget_note = None
        self.opponent_name = ""
        self.eff_sims = 0
        self.eff_k_dets = 0
        self._build_opponent()

        # Deck seeding must be the LAST thing before get_init_board: the engine draws
        # its shuffle from the GLOBAL random stream there and nowhere else, which is
        # what makes (deck_seed, action_log) a lossless save (root_replay contract).
        random.seed(self.seed)
        self.board: Board = self.game.get_init_board()

        # Opt-in only; a failure here degrades to the Python path with a note
        # rather than killing the game (the wheel may simply be absent).
        if self.backend == BACKEND_RUST:
            self._start_rust_mirror()

        self.action_log: list[int] = []
        self.turn = 0
        self.ai_last_tile: tuple[int, int] | None = None
        self.ai_last_move: dict | None = None
        # One record per AI decision: {"ply", "elapsed_s"}. Live play only — a
        # RESTORED game replays its log without searching, so the timings of the
        # original session are simply not reconstructable and the list starts empty
        # rather than carrying invented numbers. Two floats a move; the archive
        # record is the only reader.
        self.ai_elapsed: list[dict] = []

        # The position BEFORE the most recent action, kept solely so the end-of-game
        # breakdown can be reconstructed (see `_final_breakdown`). Free: the engine's
        # `get_next_state` already deepcopies, so the previous Board was going to be
        # discarded anyway — this just holds the reference instead of dropping it.
        self.prev_board: Board | None = None
        self.last_action: int | None = None
        # Memoised `_final_breakdown` (the terminal `_state_dict` is rebuilt on
        # every `get_state`, and the reconstruction is a deepcopy + a full
        # feature traversal — not something to repeat on a poll).
        self.breakdown: list[dict] | None = None
        self.breakdown_done: bool = False

        # What the most recent DECISION paid out (see `scoring_events`). Replaced
        # wholesale by `apply_and_collect`, so it always describes exactly one
        # decision — never an accumulation across a turn.
        self.last_events: list[dict] = []

    # -- opponent construction (mirrors play_vs_tier1_gui.build_opponent) ----
    def _build_opponent(self) -> None:
        if self.opponent_kind == "tier1":
            from carcassonne_ai.rule_based_player import RuleBasedPlayer

            tier1 = RuleBasedPlayer(seed=self.seed)
            self.agent = tier1
            self.pick = lambda board: int(
                tier1.choose_action(self.ai_game, board,
                                    self.ai_game.get_valid_moves(board)))
            self.opponent_name = "Tier-1"
            self.budget_note = None
            self.eff_sims = 0
            self.eff_k_dets = 0
            return

        if self.opponent_kind != "champion":
            raise ValueError(f"opponent must be 'champion'|'tier1'; got "
                             f"{self.opponent_kind!r}")

        spec = champion_factory.load_production_spec()
        # THE MOBILE PROFILE, not the champion-of-record fields: since 2026-07-29 the
        # champion budget is k8x1376 = 11008, which needs the 8-way k-parallel split to
        # be playable and Chaquopy has no multiprocessing. See mobile_budget().
        mob = mobile_budget(spec)
        eff_sims = mob["sims_per_det"] if self.req_sims is None else int(self.req_sims)
        eff_k = mob["k_dets"] if self.req_k_dets is None else int(self.req_k_dets)
        # parallel_workers is deliberately NEVER passed here: the fair agent's split uses
        # spawn processes, which Chaquopy cannot provide. Omitting it is the byte-identical
        # sequential path — the SAME player, just slower, not a different agent.
        agent = champion_factory.make_production_champion(
            "fair", game=self.ai_game, seed=self.seed, sims=eff_sims, k_dets=eff_k,
            exact_endgame=True, verify=self.verify,
            # Bound the endgame solver on-device: the desktop default is 2,000,000
            # nodes with no wall-clock component and no mid-search cancel, so a bad
            # board is an unbounded hang on a phone. 100k is ~45x the largest solve
            # ever observed (2,214 nodes across 9 real endgames) — it should never
            # fire; if it does, that one move is the documented PIMC fallback.
            # See measurement/ANDROID_WALLCLOCK_MEMO_20260728.md (lever #1).
            exact_budget=ANDROID_EXACT_BUDGET,
        )
        _wrap_evaluator_with_counter(agent)
        self.agent = agent
        self.pick = lambda board: int(agent.choose_action(board))
        self.manifest = getattr(agent, "manifest", None)
        self.eff_sims, self.eff_k_dets = eff_sims, eff_k

        self.opponent_name = "Champion"
        self.budget_note = None
        full = spec.k_dets * spec.sims_per_det
        if (eff_sims, eff_k) != (mob["sims_per_det"], mob["k_dets"]):
            # The user (or a debug screen) asked for LESS than this device's profile.
            self.budget_note = (
                f"BELOW CHAMPION BUDGET — running k{eff_k}x{eff_sims}="
                f"{eff_k * eff_sims} sims/move vs this device's "
                f"k{mob['k_dets']}x{mob['sims_per_det']}="
                f"{mob['total_sims']} (champion of record: "
                f"k{spec.k_dets}x{spec.sims_per_det}={full}). This is a WEAKENED agent; "
                f"beating it is not beating the champion.")
            self.opponent_name = f"Champion(weakened k{eff_k}x{eff_sims})"
        elif mob["total_sims"] != full:
            # Running exactly the device profile, but the profile is below the champion of
            # record (the 2026-07-29 promotion made the phone a deliberate carve-out).
            # Honest, and archived with the game — E4 must grade against THIS budget.
            self.budget_note = (
                f"MOBILE PROFILE — k{mob['k_dets']}x{mob['sims_per_det']}="
                f"{mob['total_sims']} sims/move, the on-device budget. The desktop "
                f"champion of record runs k{spec.k_dets}x{spec.sims_per_det}={full} "
                f"across 8 worker processes, which Chaquopy cannot do; the same budget "
                f"sequentially here would be ~25 s/move. Same agent, same leaf, smaller "
                f"search — grade results against this budget, not the champion's.")

    # -- the Rust mirror (P7, opt-in) ---------------------------------------
    def _full_deck_descriptions(self) -> list[str]:
        """The shuffled deck in DRAW order, as descriptions.

        ``FairAgentRs.start_game_from_deck`` is the phone path precisely because
        it carries no RNG dependence: the deck crosses the FFI as data, so the
        mirror cannot drift by reproducing a shuffle slightly differently.

        Reconstructing that order from the LIVE state is not possible — the state
        has already popped ``next_tile``, and the retail rule additionally removes
        the D tile from an unrecorded position in the pool. So a throwaway state
        is built under the same seed and read BEFORE either of those happens.
        ``random.seed`` is re-primed afterwards so the real board draws exactly
        the same deck; ``_assert_mirror`` then proves it did.
        """
        from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState

        random.seed(self.seed)
        probe = CarcassonneGameState(
            players=self.game.players,
            tile_sets=list(self.game.tile_sets),
            supplementary_rules=list(self.game.supplementary_rules),
        )
        # __init__ pops next_tile off the front, so the pool is next_tile + deck.
        pool = [probe.next_tile] + list(probe.deck)
        return [t.description for t in pool if t is not None]

    def _assert_mirror(self, where: str) -> None:
        """The mirror must render the SAME board bytes as the Python engine.

        `string_representation` is the node key the whole port is gated on (G1),
        so equality here is the same claim the desktop gates make — checked at
        game start always, and after every action when CARC_RS_RECONCILE=1.
        """
        want = self.game.string_representation(self.board)
        got = self.rs.string_repr()
        if want != got:
            raise RuntimeError(
                f"rust mirror diverged at {where}: repr differs "
                f"(python {len(want)}B, rust {len(got)}B)")

    def _start_rust_mirror(self) -> None:
        try:
            import carc_rs
        except ImportError as exc:
            self.rs_note = f"carc_rs unavailable ({exc}); using the Python backend"
            self.backend = BACKEND_PYTHON
            return
        # The mirror is a state mirror FIRST and a move chooser second. Against
        # tier1 the session has no search budget at all (eff_sims/eff_k_dets are
        # 0), but the mirror is still worth building — it is what proves the
        # bridge's deck harvest and choke point are right — so fall back to this
        # device's champion profile for a config that is valid and never searched.
        mob = mobile_budget()
        sims = int(self.eff_sims) or int(mob["sims_per_det"])
        k_dets = int(self.eff_k_dets) or int(mob["k_dets"])
        try:
            leaf = carc_rs.LeafConfigRs.curve125()
            search = carc_rs.SearchConfigRs(
                leaf, sims,
                float(self.spec_knob("c_puct")), float(self.spec_knob("tau_p")),
                float(self.spec_knob("value_norm")), 15.0,
                str(self.spec_knob("leaf_quantize")), str(self.spec_knob("final_select")),
                None, 1.0,
                ANDROID_EXP_FMA, ANDROID_TANH_FLAVOR, False,
            )
            self.rs = carc_rs.FairAgentRs(
                search, k_dets=k_dets, seed=int(self.seed),
                min_pooled_visits=2.0, exact_endgame=True, exact_max_k=2,
                exact_budget=ANDROID_EXACT_BUDGET, tt_cap=0, chance_drop="type",
                threads=1,
                # Start-rule semantics are preserved EXACTLY: the mirror is told
                # the session's own rule, and "engine" is spelled None on the FFI
                # (the P5 flag default), matching what a save with no `start_rule`
                # means on this side.
                start_rule=(None if self.start_rule == START_RULE_ENGINE
                            else self.start_rule),
            )
            self.rs.start_game_from_deck(self._full_deck_descriptions())
            self._assert_mirror("game start")
        except Exception as exc:                  # noqa: BLE001
            self.rs = None
            self.rs_note = f"rust backend failed to start ({type(exc).__name__}: {exc})"
            self.backend = BACKEND_PYTHON
            return
        # Only the CHAMPION's move choice moves to Rust. Tier-1 is a different
        # agent entirely (RuleBasedPlayer, no search) and has no Rust port; its
        # session keeps the mirror for state, not for picking.
        if self.opponent_kind == "champion":
            self.pick = lambda board: int(self.rs.choose_action())
        else:
            self.rs_note = ("mirror only: the rust backend replaces the CHAMPION's "
                            f"move choice, and this game's opponent is "
                            f"{self.opponent_kind!r}")

    def spec_knob(self, name: str):
        """One champion knob from PRODUCTION.yaml (no strength number is ever
        hardcoded here — DESIGN CONTRACT 3)."""
        return getattr(champion_factory.load_production_spec(), name)

    # -- board mechanics ----------------------------------------------------
    @property
    def ai_player(self) -> int:
        return 1 - self.human_player

    def legal_mask(self):
        return self.game.get_valid_moves(self.board)

    def legal_ids(self) -> list[int]:
        return [int(i) for i in np.flatnonzero(self.legal_mask())]

    def _pass_index(self) -> int:
        size = self.board.offset.size
        return (tile_pass_index(size) if self.board.state.phase == GamePhase.TILES
                else meeple_pass_index(size))

    def apply(self, action_id: int) -> None:
        self.prev_board = self.board
        self.last_action = int(action_id)
        self.board, _ = self.game.get_next_state(self.board, int(action_id))
        self.action_log.append(int(action_id))
        self.turn += 1
        # THE single step choke point: every applied action, both seats, exactly
        # once. The mirror is advanced here and nowhere else — that is what keeps
        # it from drifting, and it is why `undo_last_tile` / `restore_game` (which
        # rebuild the session by replaying the log) need no mirror-specific code.
        if self.rs is not None:
            self.rs.advance(int(action_id))
            if _RS_RECONCILE:
                self._assert_mirror(f"ply {self.turn}")

    def _claim_of(self, action_id: int) -> tuple | None:
        """``(player, MeeplePosition)`` if ``action_id`` puts a meeple down here.

        Needed because a meeple can be placed AND collected inside one engine call —
        see ``scoring_events``' ``claims``. Read-only, and best-effort: anything it
        cannot decode simply yields ``None`` and the diff falls back to its coarse
        answer rather than the move failing."""
        try:
            state = self.board.state
            if state.phase != GamePhase.MEEPLES:
                return None
            if int(action_id) == meeple_pass_index(self.board.offset.size):
                return None
            last = state.last_tile_action
            if last is None:
                return None
            act = decode(int(action_id), off=self.board.offset, phase="meeples",
                         last_tile_coord=last.coordinate)
            if not isinstance(act, MeepleAction) or getattr(act, "remove", False):
                return None
            from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition

            return (int(state.current_player),
                    MeeplePosition(meeple_type=act.meeple_type,
                                   coordinate_with_side=act.coordinate_with_side))
        except Exception:                         # noqa: BLE001
            return None

    def apply_and_collect(self, action_id: int) -> None:
        """Apply one decision (plus any forced human pass it triggers) and record
        what it paid out in ``last_events``.

        The reference to the pre-action board is taken by hand rather than reusing
        ``prev_board``: ``auto_pass_forced`` can apply further actions, each of which
        moves ``prev_board`` on, and the events must describe the whole decision.
        Keeping the reference is free — ``get_next_state`` deepcopies, so that board
        was going to be discarded anyway and is guaranteed not to be mutated."""
        before = self.board
        claim = self._claim_of(action_id)
        self.apply(action_id)
        self.auto_pass_forced()
        self.last_events = scoring_events(
            before.state, self.board.state, self.human_player, self.opponent_name,
            claims=[claim] if claim is not None else None)

    def auto_pass_forced(self) -> int:
        """Auto-apply a forced pass on the HUMAN seat so the UI never renders a phase
        whose only legal action is 'pass'. Mirrors ``play_vs_tier1_gui._advance``.

        The AI seat is deliberately NOT auto-passed: the agent handles a forced move
        internally and must still burn one ``choose_action`` so its ``_move_idx`` (and
        therefore every per-move search seed) stays aligned with a replayed restore."""
        n = 0
        while not self.board.state.is_terminated():
            if self.board.state.current_player != self.human_player:
                break
            legal = self.legal_ids()
            if legal != [self._pass_index()]:
                break
            self.apply(legal[0])
            n += 1
        return n


_S: _Session | None = None
_GENERATION = 0


# --------------------------------------------------------------------------- #
# 6. State serialisation                                                        #
# --------------------------------------------------------------------------- #
def _tile_json(tile) -> dict:
    return {"image": getattr(tile, "image", None),
            "turns": int(getattr(tile, "turns", 0)),
            "description": getattr(tile, "description", "")}


def _board_tiles(state) -> list[dict]:
    out = []
    for coord in sorted(state.placed_coords, key=lambda c: (c.row, c.column)):
        tile = state.board[coord.row][coord.column]
        if tile is None:
            continue
        d = _tile_json(tile)
        d["row"], d["col"] = int(coord.row), int(coord.column)
        out.append(d)
    return out


def _placed_meeples(state) -> list[dict]:
    out = []
    for player, positions in enumerate(state.placed_meeples):
        for mp in positions:
            cws = mp.coordinate_with_side
            side = cws.side.value
            out.append({
                "player": int(player),
                "row": int(cws.coordinate.row),
                "col": int(cws.coordinate.column),
                "side": side,
                "type": mp.meeple_type.value,
                "offset_ratio": list(MEEPLE_OFFSET_RATIO.get(side, (0.5, 0.5))),
            })
    return out


def meeple_slots_for(game: Game, board: Board) -> list[dict]:
    """The meeple slots offered on ``board``'s just-placed tile, UI-shaped.

    Shared by the live legal block and by ``preview_meeple_slots`` (which runs it
    against a throwaway copy of the board), so the two can never drift apart —
    the preview dots are the same objects the real sub-phase will offer.

    Each slot carries ``feature_group``: slots with the same group claim the SAME
    on-tile feature and are therefore interchangeable (see ``feature_groups``).
    Nothing is filtered here — the champion's action space and every test see the
    full list; grouping is advice for the renderer only.
    """
    state = board.state
    last = state.last_tile_action
    if last is None:
        return []
    coord = last.coordinate
    tile = state.board[coord.row][coord.column]
    groups = feature_groups(tile)
    slots = []
    for idx in legal_meeple_indices(game, board):
        action = decode(idx, off=board.offset, phase="meeples", last_tile_coord=coord)
        assert isinstance(action, MeepleAction)
        side = action.coordinate_with_side.side
        slots.append({
            "action_id": int(idx),
            "side": side.value,
            "type": action.meeple_type.value,
            "terrain": _terrain_name(tile, side) if tile is not None else "GRASS",
            "offset_ratio": list(MEEPLE_OFFSET_RATIO.get(side.value, (0.5, 0.5))),
            "describe": format_action(idx, board),
            "feature_group": int(groups.get(side.value, -1)),
        })
    return _renumber_groups(slots)


def _renumber_groups(slots: list[dict]) -> list[dict]:
    """Make ``feature_group`` dense (0,1,2,…) over the slots actually offered, and
    give every ungrouped slot (``-1``) a private group of its own.

    Two reasons this is not just ``feature_groups``' raw numbering: the raw ids are
    per-tile and include features whose slots are not legal here (a city already
    claimed elsewhere), and a side the tile model does not describe must never be
    silently merged with another. A private group is the safe default — it renders
    as its own dot, i.e. exactly today's behaviour."""
    dense: dict = {}
    nxt = 0
    for slot in slots:
        raw = slot["feature_group"]
        # -1 (unknown) is deliberately never shared: key it by identity instead.
        key = raw if raw >= 0 else ("solo", slot["action_id"])
        if key not in dense:
            dense[key] = nxt
            nxt += 1
        slot["feature_group"] = dense[key]
    return slots


def _legal_block(s: _Session) -> dict:
    """Legal moves for whoever is on turn, shaped for the Compose UI."""
    state = s.board.state
    empty = {"tile_cells": [], "meeple_slots": [], "meeple_target": None,
             "tile_pass_id": None, "meeple_pass_id": None, "action_ids": []}
    if state.is_terminated():
        return empty
    size = s.board.offset.size
    mask = s.legal_mask()
    ids = [int(i) for i in np.flatnonzero(mask)]
    block = dict(empty)
    block["action_ids"] = ids

    if state.phase == GamePhase.TILES:
        tp = tile_pass_index(size)
        block["tile_pass_id"] = tp if tp in ids else None
        cells = []
        for (row, col) in sorted(all_legal_tile_cells(s.game, s.board)):
            rots = legal_rotations_at_cell(s.game, s.board, row, col)
            cells.append({
                "row": row, "col": col, "rotations": rots,
                "action_ids": [tile_action_index(s.board.offset, row, col, r)
                               for r in rots],
            })
        block["tile_cells"] = cells
        return block

    mp = meeple_pass_index(size)
    block["meeple_pass_id"] = mp if mp in ids else None
    last = state.last_tile_action
    if last is None:
        return block
    coord = last.coordinate
    block["meeple_target"] = {"row": int(coord.row), "col": int(coord.column)}
    block["meeple_slots"] = meeple_slots_for(s.game, s.board)
    return block


def _final_breakdown(s: _Session, final_scores: list[int]) -> list[dict] | None:
    """Split each seat's final score into (banked during play, unfinished, farms).

    Base+Farmers pays most of its points in one lump on the last tile — farms
    settle, and every still-open city/road pays a reduced rate — so the scoreboard
    jumps (11-56 to 15-106 in the round-2 playtest) with nothing on screen to
    explain it. This is that jump, itemised.

    Why it needs the PREVIOUS board rather than the terminal one: the engine runs
    the endgame pass *inside* the terminating move
    (``StateUpdater._apply_action_to`` -> ``PointsCollector.count_final_scores``),
    and that pass CONSUMES the placed meeples. By the time the bridge sees the
    terminal state there is nothing left to attribute the points to. So the last
    action is re-applied to a copy of the previous board with the final-scoring
    pass stubbed for that one call, which leaves the meeple-intact terminal state
    that ``aux_targets.extract_terminal_ownership`` documents as its input. Same
    reconstruction ``selfplay`` already uses for its ownership labels; ``engine/``
    is untouched and nothing here can reach the live session's board.

    Best-effort by construction: anything unexpected — no previous board (a save
    restored directly onto a terminal position), a reconstruction that does not
    land terminal, or a split that does not add up — returns ``None`` and the
    dialog simply omits the block. A breakdown that does not reconcile with the
    score the player can see would be worse than no breakdown at all.
    """
    if s.prev_board is None or s.last_action is None:
        return None
    try:
        import copy

        from carcassonne_ai.aux_targets import extract_terminal_ownership
        from wingedsheep.carcassonne.utils.points_collector import PointsCollector

        term = copy.deepcopy(s.prev_board)
        # A private, cache-free Game: `apply_action_inplace` mutates the board it
        # is given, and the session's Games carry a legal-moves cache that has no
        # business seeing a throwaway state.
        replay_game = Game()
        orig_cfs = PointsCollector.count_final_scores
        PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)
        try:
            replay_game.apply_action_inplace(term, int(s.last_action))
        finally:
            PointsCollector.count_final_scores = orig_cfs
        if not term.state.is_terminated():
            return None

        n = len(final_scores)
        during = [int(x) for x in term.state.scores][:n]
        if len(during) != n:
            return None
        farms = [0] * n
        incomplete = [0] * n
        for r in extract_terminal_ownership(term.state):
            bucket = farms if r.terrain == "farm" else incomplete
            for w in r.winners:
                if 0 <= w < n:
                    bucket[w] += int(r.points)

        rows = []
        for p in range(n):
            if during[p] + incomplete[p] + farms[p] != int(final_scores[p]):
                return None
            rows.append({"during_play": during[p], "incomplete": incomplete[p],
                         "farms": farms[p], "total": int(final_scores[p])})
        return rows
    except Exception:
        return None


def _state_dict(s: _Session) -> dict:
    state = s.board.state
    terminated = bool(state.is_terminated())
    scores = [int(x) for x in state.scores]
    d = {
        "ok": True,
        "schema": STATE_SCHEMA,
        "generation": s.generation,
        "phase": state.phase.value,
        "turn": int(s.turn),
        "current_player": int(state.current_player),
        "human_player": int(s.human_player),
        "ai_player": int(s.ai_player),
        "is_human_turn": (not terminated
                          and int(state.current_player) == int(s.human_player)),
        "scores": scores,
        "meeples_free": [int(x) for x in state.meeples],
        "deck_remaining": int(len(state.deck)),
        "tiles_remaining": int(k_remaining(state)),
        "next_tile": _tile_json(state.next_tile) if state.next_tile is not None else None,
        "board": _board_tiles(state),
        "meeples": _placed_meeples(state),
        "legal": _legal_block(s),
        "opponent": s.opponent_kind,
        "opponent_name": s.opponent_name,
        "budget_note": s.budget_note,
        # Which implementation is picking the champion's move (P7). Always
        # present, always "python" unless a caller opted in; `backend_note`
        # carries the reason when a requested "rust" fell back.
        "backend": s.backend,
        "backend_note": s.rs_note,
        "ai_last_tile": ({"row": s.ai_last_tile[0], "col": s.ai_last_tile[1]}
                         if s.ai_last_tile is not None else None),
        "ai_last_move": s.ai_last_move,
        "is_terminated": terminated,
        "n_actions": len(s.action_log),
        # What the LAST decision paid out (see `scoring_events`). A list, because one
        # tile can close two features at once. Empty for a move that scored nothing —
        # which is most moves — and empty on a freshly restored session, whose
        # decisions were replayed rather than played.
        "events": list(s.last_events),
    }
    if terminated:
        diff = scores[0] - scores[1]
        if diff == 0:
            verdict, winner = "Tie!", None
        else:
            winner = 0 if diff > 0 else 1
            verdict = ("You win!" if winner == s.human_player
                       else f"{s.opponent_name} wins.")
        if not s.breakdown_done:
            s.breakdown = _final_breakdown(s, scores)
            s.breakdown_done = True
        d["result"] = {"scores": scores, "diff": abs(diff), "winner": winner,
                       "verdict": verdict, "budget_note": s.budget_note,
                       "breakdown": s.breakdown}
    return d


# --------------------------------------------------------------------------- #
# 7. Response plumbing                                                          #
# --------------------------------------------------------------------------- #
def _err(code: str, message: str, **extra) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message}}
    payload.update(extra)
    return json.dumps(payload)


def _ok(d: dict) -> str:
    return json.dumps(d, default=str)


def _require_session() -> _Session:
    if _S is None:
        raise RuntimeError("no active game — call new_game() first")
    return _S


# --------------------------------------------------------------------------- #
# 8. Public API — every function takes/returns JSON strings                     #
# --------------------------------------------------------------------------- #
def new_game(config_json: str = "{}") -> str:
    """Start a game. ``config_json`` keys (all optional):

        seed          int, default 0     — deck seed AND agent seed
        human_player  0|1, default 0     — which seat the human plays
        opponent      "champion"|"tier1", default "champion"
        sims          int|null           — per-determinization sims (null = YAML budget)
        k_dets        int|null           — determinizations   (null = YAML budget)
        verify        bool, default true — champion_factory's runtime leaf proof
        start_rule    "retail"|"engine", default "retail" — start-tile convention
                      (see START_RULE; the app plays retail, the library default
                      stays "engine" so evals are unaffected)
        backend       "python"|"rust", default "python" — who picks the CHAMPION's
                      move. "rust" mirrors the game into `carc_rs.FairAgentRs`;
                      the Python engine stays authoritative for legality, UI,
                      scoring and the save record either way. Opt-in (P7).

    Returns the full state object (see ``get_state``)."""
    global _S, _GENERATION, _prog_leaf_calls, _prog_expected, _prog_t0
    global _prog_thinking, _agent_ref
    try:
        cfg = json.loads(config_json) if config_json else {}
        if not isinstance(cfg, dict):
            return _err("bad_config", "config_json must be a JSON object")
        human_player = int(cfg.get("human_player", 0))
        if human_player not in (0, 1):
            return _err("bad_config", "human_player must be 0 or 1")
        _GENERATION += 1
        s = _Session(
            seed=int(cfg.get("seed", 0)),
            human_player=human_player,
            opponent=str(cfg.get("opponent", "champion")),
            sims=cfg.get("sims"),
            k_dets=cfg.get("k_dets"),
            verify=bool(cfg.get("verify", True)),
            generation=_GENERATION,
            start_rule=str(cfg.get("start_rule", START_RULE)),
            backend=str(cfg.get("backend", BACKEND_DEFAULT)),
        )
        _S = s
        _agent_ref = s.agent
        _prog_leaf_calls = 0
        _prog_expected = max(0, s.eff_sims * s.eff_k_dets)
        _prog_t0 = 0.0
        _prog_thinking = False
        s.auto_pass_forced()
        return _ok(_state_dict(s))
    except Exception as exc:                      # noqa: BLE001 — never raise across JNI
        return _err(type(exc).__name__, str(exc))


def get_state() -> str:
    """The full UI state object for the live game."""
    try:
        return _ok(_state_dict(_require_session()))
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def apply_action(action_id) -> str:
    """Apply a HUMAN action. Validates against the legal mask, appends to the action
    log, then auto-applies any forced pass. Returns the new state (or a JSON error)."""
    try:
        s = _require_session()
        try:
            idx = int(action_id)
        except (TypeError, ValueError):
            return _err("illegal_action", f"action_id {action_id!r} is not an int")
        if s.board.state.is_terminated():
            return _err("game_over", "the game has ended")
        mask = s.legal_mask()
        if not (0 <= idx < len(mask)) or not bool(mask[idx]):
            return _err("illegal_action",
                        f"action {idx} is not legal in phase "
                        f"{s.board.state.phase.value}",
                        legal_action_ids=s.legal_ids())
        describe = format_action(idx, s.board)
        s.apply_and_collect(idx)
        out = _state_dict(s)
        out["applied"] = {"action_id": idx, "describe": describe}
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def ai_move(generation=None) -> str:
    """Run ONE AI decision (blocking; seconds at champion budget) and apply it.

    ``generation`` is the session generation Kotlin believes is current. A mismatch on
    entry is refused; a mismatch on EXIT (the user reset mid-search) discards the move
    instead of applying it to a board it was never computed for. The echoed
    ``generation`` lets the caller drop a stale result unconditionally."""
    global _prog_leaf_calls, _prog_t0, _prog_thinking, _prog_expected
    try:
        s = _require_session()
        gen = s.generation if generation is None else int(generation)
        if gen != s.generation:
            return _err("stale_generation",
                        f"generation {gen} != current {s.generation}",
                        generation=gen, current_generation=s.generation, stale=True)
        if s.board.state.is_terminated():
            return _err("game_over", "the game has ended")
        if s.board.state.current_player == s.human_player:
            return _err("not_ai_turn", "it is the human's turn")

        board = s.board
        t0 = time.perf_counter()
        _prog_leaf_calls = 0
        _prog_expected = max(0, s.eff_sims * s.eff_k_dets)
        _prog_t0 = t0
        _prog_thinking = True
        try:
            idx = int(s.pick(board))
        finally:
            _prog_thinking = False
            _prog_t0 = 0.0
        elapsed_s = time.perf_counter() - t0

        if _S is not s or s.generation != gen:
            # Reset landed while we were thinking: the answer belongs to a board that
            # no longer exists. Drop it — never apply a move computed for another game.
            return _ok({"ok": True, "stale": True, "generation": gen,
                        "current_generation": (_S.generation if _S else None),
                        "action_id": idx})

        mask = s.legal_mask()
        if not (0 <= idx < len(mask)) or not bool(mask[idx]):
            return _err("agent_illegal_action",
                        f"agent returned illegal action {idx}")
        describe = format_action(idx, s.board)
        if (s.board.state.phase == GamePhase.TILES
                and idx != tile_pass_index(s.board.offset.size)):
            act = decode(idx, off=s.board.offset, phase="tiles",
                         next_tile=s.board.state.next_tile)
            s.ai_last_tile = (int(act.coordinate.row), int(act.coordinate.column))
        s.ai_last_move = {"action_id": idx, "describe": describe,
                          "elapsed_s": round(elapsed_s, 4)}
        s.ai_elapsed.append({"ply": len(s.action_log),
                             "elapsed_s": round(elapsed_s, 4)})
        s.apply_and_collect(idx)

        out = _state_dict(s)
        out.update({"action_id": idx, "describe": describe,
                    "elapsed_s": round(elapsed_s, 4), "generation": gen,
                    "stale": False, "leaf_calls": _prog_leaf_calls})
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def get_progress() -> str:
    """Cheap, lock-free progress poll — the ONLY function safe to call while
    ``ai_move`` is blocking. Reads module-global ints and one agent bool."""
    try:
        t0 = _prog_t0
        thinking = bool(_prog_thinking)
        leaf_calls = int(_prog_leaf_calls)
        expected = int(_prog_expected)
        latched = bool(getattr(_agent_ref, "_latched", False))
        if not thinking:
            phase = "idle"
        elif latched:
            phase = "exact"     # exact-endgame solve: leaf counter does not move
        else:
            phase = "search"
        elapsed = (time.perf_counter() - t0) if (thinking and t0) else 0.0
        frac = (min(1.0, leaf_calls / expected) if (expected > 0 and phase == "search")
                else None)
        return _ok({"ok": True, "leaf_calls": leaf_calls, "expected": expected,
                    "elapsed_s": round(elapsed, 3), "phase": phase,
                    "fraction": frac})
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def _spec_fingerprint() -> dict:
    """``{champion_id, leaf_hash}`` for the CURRENT PRODUCTION.yaml, or empty strings.

    Recorded in every save and re-checked on restore (see ``restore_game``'s
    ``save_mismatch``). The leaf hash matters for BOTH opponents, not just the
    champion: ``RuleBasedPlayer`` ranks its candidates with ``virtual_score``, so a
    leaf change moves tier-1's play too."""
    try:
        spec = champion_factory.load_production_spec()
        return {"champion_id": str(spec.champion_id),
                "leaf_hash": str(spec.yaml_leaf_hash)}
    except Exception:                             # noqa: BLE001 — never break a save
        return {"champion_id": "", "leaf_hash": ""}


def _save_payload(s: _Session) -> dict:
    """The restorable core of a save. Shared by ``save_game`` and ``archive_record``
    so an archived game is replayable by exactly the same contract as the autosave."""
    out = {
        "ok": True,
        "schema": SAVE_SCHEMA,
        "deck_seed": s.seed,
        "actions": list(s.action_log),
        "human_player": s.human_player,
        "opponent": s.opponent_kind,
        "sims": s.req_sims,
        "k_dets": s.req_k_dets,
        "verify": s.verify,
        # Load-bearing for replay: (deck_seed, actions) only reproduces the game
        # under the SAME start-tile rule. Saves written before this field existed
        # are read as START_RULE_LEGACY.
        "start_rule": s.start_rule,
    }
    out.update(_spec_fingerprint())
    return out


def save_game() -> str:
    """Serialise the game to ``{deck_seed, actions, human_player, opponent, sims,
    k_dets, verify}`` — a few hundred ints. Losslessly restorable via
    ``restore_game`` (the root_replay contract).

    Also stamps the champion identity (``champion_id`` + the YAML ``leaf_hash``) so a
    save written by an older build can be RECOGNISED as such on restore. The stamp is
    advisory: ``restore_game`` warns, never refuses.

    Works at a TERMINATED state too — nothing here reads the phase — which is what
    lets ``archive_record`` build on it after the last tile lands."""
    try:
        return _ok(_save_payload(_require_session()))
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def archive_record() -> str:
    """The permanent record of a FINISHED game, for ``filesDir/games/``.

    The autosave is deleted at termination, which threw away the one artefact worth
    keeping: the ``(deck_seed, action_log)`` pair that reproduces the game exactly.
    This is that pair — the full ``save_game`` payload, restorable by the same
    ``restore_game`` contract and replayable on the desktop by ``root_replay`` — plus
    the read-only summary the Past-games list needs so it never has to replay 150
    plies just to print a score line.

    Refuses a game that is not over: an archive entry is a *result*, and a
    half-finished one would show up in the list as a game the player never lost.
    """
    try:
        s = _require_session()
        if not s.board.state.is_terminated():
            return _err("not_terminated",
                        "archive_record is only for a finished game")
        st = _state_dict(s)
        out = _save_payload(s)
        out.update({
            "schema": ARCHIVE_SCHEMA,
            "save_schema": SAVE_SCHEMA,
            "finished_at": int(time.time()),
            "opponent_name": s.opponent_name,
            "budget_note": s.budget_note,
            "sims_effective": s.eff_sims,
            "k_dets_effective": s.eff_k_dets,
            "result": st.get("result"),
            "scores": st["scores"],
            "n_actions": len(s.action_log),
            "tiles_placed": len(st["board"]),
            "ai_elapsed": list(s.ai_elapsed),
        })
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def preview_meeple_slots(action_id) -> str:
    """What meeple options a PROSPECTIVE tile placement would open.

    Applies ``action_id`` to a COPY of the live board and reads the meeple slots off
    the result, so the ghost can show its consequences before the player commits.
    Same shape as ``legal.meeple_slots`` (``feature_group`` and ``offset_ratio``
    included) because it is literally the same builder.

    Read-only by construction, twice over: ``Game.get_next_state`` is documented to
    leave its input board unmodified (it is MCTS's tree-expansion path), and the copy
    is driven by a PRIVATE cache-free ``Game`` so the session's legal-moves cache
    never sees the throwaway state. Nothing here touches ``_S``.
    """
    try:
        s = _require_session()
        try:
            idx = int(action_id)
        except (TypeError, ValueError):
            return _err("illegal_action", f"action_id {action_id!r} is not an int")
        if s.board.state.is_terminated():
            return _err("game_over", "the game has ended")
        if s.board.state.phase != GamePhase.TILES:
            return _err("not_tile_phase",
                        "preview_meeple_slots takes a TILE action")
        mask = s.legal_mask()
        if not (0 <= idx < len(mask)) or not bool(mask[idx]):
            return _err("illegal_action", f"action {idx} is not legal here")
        if idx == tile_pass_index(s.board.offset.size):
            # A pass places no tile, so there is nothing to put a meeple on.
            return _ok({"ok": True, "action_id": idx, "slots": []})

        preview_game = Game()
        next_board, _ = preview_game.get_next_state(s.board, idx)
        slots = ([] if next_board.state.phase != GamePhase.MEEPLES
                 else meeple_slots_for(preview_game, next_board))
        return _ok({"ok": True, "action_id": idx, "slots": slots,
                    "generation": s.generation})
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def _replays_rng(agent) -> bool:
    """Does this agent need its RNG rebuilt by REPLAYING decisions?

    True for a stream-random agent (``RuleBasedPlayer``: one ``_rng`` advanced by every
    tie-break, no per-move seed). False for the champion, whose search seeds are derived
    from ``_move_idx`` — re-seating that integer is exact and free, and replaying its
    decisions would cost a full search per ply."""
    return hasattr(agent, "_rng") and not hasattr(agent, "_move_idx")


def _save_mismatch(blob: dict) -> dict | None:
    """Compare the save's champion stamp with the running one; ``None`` if they agree.

    Saves written before the stamp existed carry no fields and are treated as matching
    — an absent stamp is not evidence of a difference."""
    cur = _spec_fingerprint()
    fields = {}
    for key in ("champion_id", "leaf_hash"):
        was = str(blob.get(key, "") or "")
        now = str(cur.get(key, "") or "")
        if was and now and was != now:
            fields[key] = {"saved": was, "current": now}
    if not fields:
        return None
    return {
        "fields": fields,
        "message": ("This game was saved against a different champion build; the "
                    "opponent may now play differently from here on."),
    }


def restore_game(json_str: str) -> str:
    """Rebuild a session from ``save_game``'s payload and return the state.

    Replays the action log from the seeded init board, then re-seats the agent:
    ``_move_idx`` = the number of AI *decisions* replayed (its per-move search seeds
    derive from it, ``fair_agent.det_seed_base``) and ``_latched`` = whether the
    exact-endgame latch would already have fired. Without both, a restored game would
    silently play a different champion than the one that was saved.

    An agent whose randomness lives in a *stream* rather than a per-move seed —
    ``RuleBasedPlayer._rng``, which breaks virtual-score ties — cannot be re-seated by
    an index: ``Random.choice`` consumes a data-dependent number of ``getrandbits``
    calls (rejection sampling over ``len(best_local)``, the count of TIED-best actions,
    which is unknowable without scoring the position). So its stream is rebuilt the only
    exact way there is — by replaying the decisions themselves (see ``_replays_rng``).
    Measured before this was added: 12/12 seeds diverged after a mid-game restore."""
    global _S, _GENERATION, _prog_leaf_calls, _prog_expected, _prog_t0
    global _prog_thinking, _agent_ref
    try:
        blob = json.loads(json_str) if isinstance(json_str, str) else dict(json_str)
        if not isinstance(blob, dict):
            return _err("bad_save", "save payload must be a JSON object")
        # An ARCHIVE record is a superset of a save — same `deck_seed` + `actions`
        # core, extra read-only summary fields that replay simply ignores — so a
        # finished game in `filesDir/games/` is replayable by the same call. Refusing
        # it on the schema string alone would make the archive write-only.
        schema = blob.get("schema", SAVE_SCHEMA)
        if schema not in (SAVE_SCHEMA, ARCHIVE_SCHEMA):
            return _err("bad_save", f"unknown save schema {schema!r}")
        actions = [int(a) for a in blob.get("actions", [])]
        human_player = int(blob.get("human_player", 0))
        if human_player not in (0, 1):
            return _err("bad_save", "human_player must be 0 or 1")

        _GENERATION += 1
        s = _Session(
            seed=int(blob.get("deck_seed", 0)),
            human_player=human_player,
            opponent=str(blob.get("opponent", "champion")),
            sims=blob.get("sims"),
            k_dets=blob.get("k_dets"),
            verify=bool(blob.get("verify", True)),
            generation=_GENERATION,
            # Absent field == written before the retail start shipped.
            start_rule=str(blob.get("start_rule", START_RULE_LEGACY)),
            # The backend is a RUNTIME choice, not a property of the saved game —
            # it changes who computes a move, never what the game is — so it is
            # carried from the live session (undo_last_tile rebuilds through here)
            # and falls back to the process default, NOT to anything in the blob.
            backend=(_S.backend if _S is not None else BACKEND_DEFAULT),
        )

        # Replay. Whose decision each logged action was is decided by the board it was
        # played on — human auto-passes are logged too but never consume an AI decision.
        exact_max_k = int(getattr(s.agent, "_exact_max_k", 2))
        exact_on = bool(getattr(s.agent, "_exact_endgame", False))
        replay_rng = _replays_rng(s.agent)
        ai_decisions = 0
        latched = False
        for a in actions:
            st = s.board.state
            if st.is_terminated():
                return _err("bad_save",
                            f"action log is longer than the game ({len(actions)} "
                            f"actions, terminated after {ai_decisions} AI decisions)")
            is_ai_turn = int(st.current_player) != s.human_player
            if is_ai_turn:
                if exact_on and not latched:
                    if st.phase == GamePhase.TILES and k_remaining(st) <= exact_max_k:
                        latched = True
                ai_decisions += 1
            mask = s.game.get_valid_moves(s.board)
            if not (0 <= a < len(mask)) or not bool(mask[a]):
                return _err("bad_save",
                            f"replay hit an illegal action {a} at ply "
                            f"{len(s.action_log)}")
            if is_ai_turn and replay_rng:
                # Burn the agent's RNG stream exactly as live play did: same board,
                # same rng state in, therefore identical consumption out. The RETURNED
                # action is discarded — the log is authoritative — but it should equal
                # `a`, and a mismatch means the save predates a strength change (the
                # `save_mismatch` warning below is the user-visible half of that).
                s.pick(s.board)
            # Cosmetic parity with live play: rebuild the AI's last-move highlight so a
            # restored state deep-compares equal to the state that was saved (only the
            # un-reconstructable wall-clock is left None).
            if is_ai_turn:
                s.ai_last_move = {"action_id": int(a),
                                  "describe": format_action(a, s.board),
                                  "elapsed_s": None}
                if (st.phase == GamePhase.TILES
                        and a != tile_pass_index(s.board.offset.size)):
                    act = decode(a, off=s.board.offset, phase="tiles",
                                 next_tile=st.next_tile)
                    if isinstance(act, TileAction):
                        s.ai_last_tile = (int(act.coordinate.row),
                                          int(act.coordinate.column))
            s.apply(a)

        if hasattr(s.agent, "_move_idx"):
            s.agent._move_idx = ai_decisions
        if hasattr(s.agent, "_latched"):
            s.agent._latched = latched

        _S = s
        _agent_ref = s.agent
        _prog_leaf_calls = 0
        _prog_expected = max(0, s.eff_sims * s.eff_k_dets)
        _prog_t0 = 0.0
        _prog_thinking = False
        s.auto_pass_forced()
        out = _state_dict(s)
        out["restored"] = {"actions": len(actions), "ai_decisions": ai_decisions,
                           "latched": latched, "rng_replayed": replay_rng}
        # Advisory, never fatal: an old save still restores and still plays.
        mismatch = _save_mismatch(blob)
        if mismatch is not None:
            out["save_mismatch"] = mismatch
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def undo_last_tile() -> str:
    """Take the human's just-placed tile back, returning to the tile decision point.

    Only legal in the HUMAN's meeple sub-phase — i.e. the tile is down, its meeple is
    not yet chosen, and *nothing else has happened*. That window is what makes the
    undo exact rather than approximate:

    * **No AI decision sits inside it.** ``auto_pass_forced`` only auto-passes the
      HUMAN seat, and the champion never moves between a human tile and its meeple.
      So dropping the last action removes a human decision and nothing else.
    * **The rebuild is the ordinary restore.** A game is fully determined by
      ``(deck_seed, action_log)`` (the ``root_replay`` contract), so this is literally
      ``restore_game`` on the save payload with the last action sliced off. That
      re-seats the champion's ``_move_idx`` / exact-endgame latch and replays a
      stream-random Tier-1's RNG, exactly as a Resume does — the opponent that plays
      on is bit-identical to the one that would have played had the tile never been
      placed. Nothing here needs its own determinism argument.
    * **The undone action leaves no trace.** The new session's log is the truncated
      one, so the autosave written after this call, and any archive built from it
      later, replay the game the player actually played.

    Two deliberate non-defaults on the rebuilt session:

    ``generation`` is carried over rather than bumped. The UI keys its opening
    camera fit on it, and an undo is not a new game — bumping would yank the board
    back to a whole-board fit mid-turn. Staleness is still sound: ``ai_move``'s guard
    is ``_S is not s`` *or* a generation mismatch, and the identity half catches this
    (the session object is new). Nothing can be in flight anyway — it is the human's
    turn on a single-threaded bridge.

    ``ai_elapsed`` is carried over. A restore cannot reconstruct the original
    session's wall-clock, but no AI decision was removed, so those timings all still
    describe moves that are still in the log; dropping them would silently blank the
    archive's timing record for the whole game.
    """
    try:
        s = _require_session()
        state = s.board.state
        if state.is_terminated():
            return _err("game_over", "the game has ended")
        if state.phase != GamePhase.MEEPLES:
            return _err("not_meeple_phase",
                        "undo_last_tile only applies during the meeple sub-phase")
        if int(state.current_player) != s.human_player:
            return _err("not_human_turn", "it is not the human's turn")
        if not s.action_log:
            return _err("nothing_to_undo", "no action has been played yet")

        undone = int(s.action_log[-1])
        keep_generation = s.generation
        carry_elapsed = list(s.ai_elapsed)
        payload = _save_payload(s)
        payload["actions"] = [int(a) for a in s.action_log[:-1]]

        raw = restore_game(json.dumps(payload))
        out = json.loads(raw)
        if not out.get("ok"):
            return raw                     # the rebuild failed; _S is now the rebuilt
                                           # session or the old one, either way honest
        new_s = _require_session()
        # The truncation must land exactly where the player was standing when they
        # chose the tile. Anything else means the log was not what this function
        # assumed, and silently handing back a different position would be worse
        # than refusing.
        if (new_s.board.state.phase != GamePhase.TILES
                or int(new_s.board.state.current_player) != new_s.human_player):
            return _err("undo_failed",
                        "undoing did not land on the human's tile decision")
        # `_GENERATION` (the monotonic counter) keeps the value restore_game bumped
        # it to; only the SESSION's label is rolled back, so a later new_game still
        # hands out an id nothing has seen.
        new_s.generation = keep_generation
        new_s.ai_elapsed = carry_elapsed
        out = _state_dict(new_s)
        out["undone"] = {"action_id": undone, "n_actions": len(new_s.action_log)}
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def get_ownership() -> str:
    """Every CLAIMED feature on the board: kind, the cells it covers, and who owns it.

    Feeds the always-on ownership shading. Read-only — the UI calls it after each
    state change, never in the search hot path.

    Two levels of geometry are reported and they are NOT redundant:

    ``cells``    the tile coordinates the feature touches. Coarse; a whole-tile mark.
    ``regions``  ``[row, col, side]`` triples — the *part* of each tile the feature
                 actually occupies, which is what the overlay draws. ``side`` is the
                 engine's own ``Side`` value, so it is one of the four edges (a city
                 band or a road band, rendered as a triangle from that edge to the
                 tile centre), ``center`` (a monastery), or one of the four farmer
                 corners ``top_left``/``top_right``/``bottom_left``/``bottom_right``
                 (rendered as that quadrant).

    The tile art is a raster scan with no vector mask, so a region is an
    APPROXIMATION of the painted feature, not its outline — see the renderer's note
    in ``BoardCanvas.drawOwnership``. It is nonetheless the engine's own topology:
    every triple comes from the same ``city_positions`` / ``road_positions`` /
    ``farmer_positions`` the scoring pass walks, never from a guess about the art.

    The walk is ``aux_targets.extract_terminal_ownership``'s, with one deliberate
    difference: that function CONSUMES each feature's meeples (via
    ``MeepleUtil.remove_meeples``) to avoid double-counting, which is why it must
    deepcopy the state first. Two meeples in one city would otherwise be reported as
    two cities. Here the same job is done by keying features on
    ``(kind, frozenset(cells))`` — the engine's own BFS returns the identical cell set
    from either meeple, so the second one dedupes away. Nothing is mutated, so no copy
    is needed and the live session is untouchable by construction.

    ``owners`` is the majority rule the engine actually scores by
    (``PointsCollector.get_winning_players``): empty for nobody, one seat for a sole
    owner, and BOTH seats on a tie — which is what the UI renders as contested.
    """
    try:
        s = _require_session()
        from wingedsheep.carcassonne.objects.meeple_type import MeepleType
        from wingedsheep.carcassonne.objects.terrain_type import TerrainType
        from wingedsheep.carcassonne.utils.city_util import CityUtil
        from wingedsheep.carcassonne.utils.farm_util import FarmUtil
        from wingedsheep.carcassonne.utils.points_collector import PointsCollector
        from wingedsheep.carcassonne.utils.road_util import RoadUtil

        state = s.board.state
        n_players = len(state.placed_meeples)
        seen: dict = {}
        out: list[dict] = []

        def _cells(positions) -> list[tuple[int, int]]:
            uniq = {(int(p.coordinate.row), int(p.coordinate.column)) for p in positions}
            return sorted(uniq)

        def _side_regions(positions) -> list[tuple[int, int, str]]:
            """``CoordinateWithSide`` list -> the (row, col, side) triples it covers."""
            return sorted({
                (int(p.coordinate.row), int(p.coordinate.column), str(p.side.value))
                for p in positions
            })

        for player, positions in enumerate(state.placed_meeples):
            for mp in positions:
                cws = mp.coordinate_with_side
                coord = cws.coordinate
                tile = state.board[coord.row][coord.column]
                if tile is None:
                    continue
                kind, cells, finished, points, meeples = None, [], None, 0, None
                regions: list[tuple[int, int, str]] = []
                try:
                    if mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                        farm = FarmUtil.find_farm_by_coordinate(state, position=cws)
                        kind = "farm"
                        cells = sorted({
                            (int(f.coordinate.row), int(f.coordinate.column))
                            for f in farm.farmer_connections_with_coordinate
                        })
                        # A farm occupies the CORNERS of a tile, not its edges: one
                        # tile can carry two different fields split by a road, and
                        # `farmer_positions` is exactly which corners this one holds.
                        regions = sorted({
                            (int(f.coordinate.row), int(f.coordinate.column),
                             str(side.value))
                            for f in farm.farmer_connections_with_coordinate
                            for side in f.farmer_connection.farmer_positions
                        })
                        meeples = FarmUtil.find_meeples(state, farm)
                        points = int(PointsCollector.count_farm_points(state, farm))
                    else:
                        terrain = tile.get_type(cws.side)
                        if terrain == TerrainType.CITY:
                            city = CityUtil.find_city(state, cws)
                            kind = "city"
                            cells = _cells(city.city_positions)
                            regions = _side_regions(city.city_positions)
                            finished = bool(city.finished)
                            meeples = CityUtil.find_meeples(state, city)
                            points = int(PointsCollector.count_city_points(state, city))
                        elif terrain == TerrainType.ROAD:
                            road = RoadUtil.find_road(state, cws)
                            kind = "road"
                            cells = _cells(road.road_positions)
                            regions = _side_regions(road.road_positions)
                            finished = bool(road.finished)
                            meeples = RoadUtil.find_meeples(state, road)
                            points = int(PointsCollector.count_road_points(state, road))
                        elif terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                            kind = "chapel"
                            cells = [(int(coord.row), int(coord.column))]
                            regions = [(int(coord.row), int(coord.column), "center")]
                            points = int(
                                PointsCollector.chapel_or_flowers_points(state, coord))
                except Exception:                 # noqa: BLE001 — one odd feature must
                    continue                      # not cost the whole overlay
                if kind is None or not cells:
                    continue
                key = (kind, frozenset(cells))
                if key in seen:
                    continue
                seen[key] = True

                if meeples is not None:
                    counts = [int(c) for c in
                              PointsCollector.get_meeple_counts_per_player(meeples)]
                else:
                    # A monastery holds exactly the one meeple that is standing on it.
                    counts = [0] * n_players
                    counts[player] = 1
                while len(counts) < n_players:
                    counts.append(0)
                owners = [int(w) for w in
                          PointsCollector.get_winning_players(counts)]
                out.append({
                    "kind": kind,
                    "cells": [[r, c] for (r, c) in cells],
                    "regions": [[r, c, side] for (r, c, side) in regions],
                    "owners": owners,
                    "meeple_count_per_player": counts,
                    "finished": finished,
                    "points": points,
                })

        return _ok({"ok": True, "generation": s.generation, "features": out})
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def get_bag() -> str:
    """What is still UNSEEN, per tile face — the bag viewer's data.

    Strictly public information, and computed so that it cannot be anything else:
    ``remaining = total_in_the_base_distribution - already_on_the_board - the tile in
    hand``. ``state.deck`` is never read. That matters — the deck is a shuffled LIST,
    so its contents in order are the future draws, and reading it would hand the player
    knowledge the fair champion's determinizations deliberately do not have.

    Faces are counted by ``tile.description``, the key ``base_tile_counts`` itself is
    indexed by and the one field ``Tile.turn(n)`` preserves — so a rotated tile on the
    board still counts against the face it came from.
    """
    try:
        s = _require_session()
        from wingedsheep.carcassonne.tile_sets.base_deck import (
            base_tile_counts,
            base_tiles,
        )

        state = s.board.state
        placed: dict[str, int] = {}
        for coord in state.placed_coords:
            tile = state.board[coord.row][coord.column]
            if tile is None:
                continue
            desc = str(getattr(tile, "description", ""))
            placed[desc] = placed.get(desc, 0) + 1
        # ONLY in the tile phase. The engine does not clear `next_tile` when a tile
        # is played (`StateUpdater.play_tile`); it is replaced later, by `draw_tile`,
        # at the END of the meeple sub-phase. So for the whole meeple phase the tile
        # just placed is BOTH on the board and still "in hand", and subtracting it
        # here as well would count it gone twice — the bag read one short of the deck
        # for half of every turn. Same trap `GameState.tilesLeft` documents on the
        # Kotlin side.
        in_hand = (str(getattr(state.next_tile, "description", ""))
                   if (state.next_tile is not None
                       and state.phase == GamePhase.TILES) else None)

        faces = []
        total_remaining = 0
        for desc, total in sorted(base_tile_counts.items()):
            proto = base_tiles.get(desc)
            gone = placed.get(desc, 0) + (1 if in_hand == desc else 0)
            left = max(0, int(total) - int(gone))
            total_remaining += left
            faces.append({
                "description": desc,
                "image": getattr(proto, "image", None),
                "remaining": left,
                "total": int(total),
            })

        return _ok({"ok": True, "generation": s.generation, "faces": faces,
                    "total_remaining": total_remaining,
                    "in_hand": in_hand,
                    "deck_remaining": int(len(state.deck))})
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def get_manifest() -> str:
    """The champion's resolved runtime manifest (Settings sheet). ``null`` for Tier-1.

    With a live session this is the manifest of the agent that is ACTUALLY playing,
    budget override included. With no session — Settings opened before any game — it
    falls back to ``resolved_manifest("fair")``, the deterministic spec-derived
    manifest for the champion of record, so the sheet is never empty.
    ``manifest_source`` says which one you are looking at; never read a budget out of
    the ``spec`` variant and assume a game is running at it."""
    try:
        s = _S
        if s is None:
            return _ok({"ok": True, "manifest_source": "spec",
                        "manifest": champion_factory.resolved_manifest("fair"),
                        "production_yaml": PRODUCTION_YAML_PATH,
                        "opponent_name": "Champion (no game in progress)",
                        "budget_note": None})
        return _ok({"ok": True, "manifest_source": "session", "manifest": s.manifest,
                    "production_yaml": PRODUCTION_YAML_PATH,
                    "opponent_name": s.opponent_name,
                    "budget_note": s.budget_note})
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def production_budget() -> str:
    """The budget THIS DEVICE runs, so the UI never hardcodes a strength knob.

    ``k_dets``/``sims_per_det``/``total_sims`` are the **mobile deploy profile** — what the
    on-device agent actually searches — because those are the fields the UI prints and it
    must never advertise a budget the phone does not run. The champion of record is carried
    alongside under ``champion_of_record_*`` (since 2026-07-29 the two differ: desktop
    k8x1376=11008, mobile k4x688=2752 — see mobile_budget())."""
    try:
        spec = champion_factory.load_production_spec()
        mob = mobile_budget(spec)
        return _ok({"ok": True, "champion_id": spec.champion_id,
                    "sims_per_det": mob["sims_per_det"], "k_dets": mob["k_dets"],
                    "total_sims": mob["total_sims"],
                    "profile": mob["profile"],
                    "profile_from_yaml": mob["from_yaml"],
                    "champion_of_record_k_dets": spec.k_dets,
                    "champion_of_record_sims_per_det": spec.sims_per_det,
                    "champion_of_record_total_sims": spec.k_dets * spec.sims_per_det,
                    "exact_max_k": spec.exact_max_k,
                    "production_yaml": PRODUCTION_YAML_PATH})
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def runtime_info() -> str:
    """What the Python layer actually resolved to at runtime — for the About/Debug view.

    Answers the question the APK alone cannot: did the compiled Cython fast paths make
    it onto THIS device, or is the champion running the pure-Python leaf?

    Per module, three distinct facts (do not collapse them):
      ``enabled``  the env toggle (``flat_leaf.USE_CY_LEAF`` / ``board_repr.USE_CY_REPR``)
      ``loaded``   the .so genuinely imported and dlopened
      ``bound``    the lazy binding state inside the consuming module —
                   ``active`` (calls go to Cython), ``pure_python`` (import failed, a
                   False sentinel is cached and will not be retried), or ``unbound``
                   (nothing has evaluated a leaf yet, so it has not tried).

    ``bound == "unbound"`` before the first move is normal, not a fault."""
    try:
        import importlib.util

        from carcassonne_ai import board_repr, flat_leaf

        def _state(sentinel) -> str:
            if sentinel is None:
                return "unbound"
            return "active" if sentinel else "pure_python"

        cython = {
            "flat_leaf_cy": {
                "enabled": bool(flat_leaf.USE_CY_LEAF),
                "loaded": bool(CY_LOADED.get("flat_leaf_cy", False))
                or importlib.util.find_spec("carcassonne_ai.flat_leaf_cy") is not None,
                "bound": _state(flat_leaf._CY_FLAT_V2),
            },
            "flat_repr_cy": {
                "enabled": bool(board_repr.USE_CY_REPR),
                "loaded": bool(CY_LOADED.get("flat_repr_cy", False))
                or importlib.util.find_spec("carcassonne_ai.flat_repr_cy") is not None,
                "bound": _state(board_repr._CY_ENCODE),
            },
        }
        # The Rust core (P7). Shipped in the APK but INERT unless a game opts in,
        # so `available` and `active` are deliberately two different facts.
        try:
            import carc_rs

            rust = {"available": True,
                    "version": getattr(carc_rs, "__version__", None),
                    "tanh_flavor": ANDROID_TANH_FLAVOR,
                    "exp_fma": ANDROID_EXP_FMA}
        except ImportError as exc:
            rust = {"available": False, "error": str(exc)}
        rust["default_backend"] = BACKEND_DEFAULT
        rust["active"] = bool(_S is not None and _S.rs is not None)

        return _ok({
            "ok": True,
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "numpy": np.__version__,
            "cython": cython,
            "rust": rust,
            "flat_leaf": bool(flat_leaf.USE_FLAT_LEAF),
            "spec": _spec_fingerprint(),
            "env": RESOLVED_ENV,
        })
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def debug_fast_forward(confirm: str = "", max_plies=600) -> str:
    """DEBUG ONLY — play the current game out to termination, both seats.

    Exists so a finished game can be reached in one call while testing the archive
    and the end-of-game dialog; a real Instant game is ~150 taps. Reachable only from
    the Debug console, and it additionally demands ``confirm`` be the exact token
    below so no ordinary code path can trip it.

    NOT a strength tool and never on the play path: the AI seat still uses the
    session's real agent (``s.pick``), but the HUMAN seat just takes its first legal
    action, so the resulting game is legal and replayable but the human side is
    arbitrary. The action log stays a valid ``(deck_seed, actions)`` record, so the
    archive entry it produces restores exactly like any other.
    """
    try:
        s = _require_session()
        if confirm != "yes-destroy-this-game":
            return _err("not_confirmed",
                        "debug_fast_forward needs confirm='yes-destroy-this-game'")
        limit = int(max_plies)
        plies = 0
        # This drives many decisions in one call, so "what the last move paid" has no
        # meaning afterwards; leaving the previous one would be a lie.
        s.last_events = []
        while not s.board.state.is_terminated():
            plies += 1
            if plies > limit:
                return _err("too_long", f"did not terminate within {limit} plies")
            if int(s.board.state.current_player) == s.human_player:
                legal = s.legal_ids()
                if not legal:
                    return _err("stuck", "no legal action for the human seat")
                s.apply(legal[0])
            else:
                t0 = time.perf_counter()
                idx = int(s.pick(s.board))
                s.ai_elapsed.append({"ply": len(s.action_log),
                                     "elapsed_s": round(time.perf_counter() - t0, 4)})
                s.apply(idx)
            s.auto_pass_forced()
        out = _state_dict(s)
        out["fast_forwarded"] = {"plies": plies}
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def reset() -> str:
    """Drop the session (bumps the generation so an in-flight ai_move is discarded)."""
    global _S, _GENERATION, _agent_ref, _prog_thinking, _prog_t0
    _GENERATION += 1
    _S = None
    _agent_ref = None
    _prog_thinking = False
    _prog_t0 = 0.0
    return _ok({"ok": True, "generation": _GENERATION})
