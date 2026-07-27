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
from carcassonne_ai.game_wrapper import Board, Game  # noqa: E402
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


def feature_groups(tile) -> dict[str, int]:
    """Map each meeple-able ``Side.value`` on ONE tile to an intra-tile feature id.

    Two sides sharing an id are two openings onto the SAME feature, so a meeple on
    either claims the same thing — the duplicate choice the UI should collapse to a
    single dot. A city spanning two edges is the common case (``city=[[TOP, RIGHT]]``);
    a straight road is the other (``road=[Connection(LEFT, RIGHT)]``).

    Purely a READ of the tile model — no engine call, no board, no action space. The
    champion still gets every action; this only tells the renderer which of them are
    interchangeable.

    The tile model is already in placed orientation: ``Tile.turn(n)`` rotates ``city``,
    ``road`` and ``farms`` along with the art, and the board stores the rotated tile.
    So the sides here are the sides as they appear on screen, and nothing needs
    un-rotating.

    Three structures, three rules:

    * ``tile.city: [[Side]]`` — already grouped by the engine, one inner list per
      connected city region. Adopt it verbatim.
    * ``tile.road: [Connection]`` — one ``Connection(a, b)`` per road segment, so its
      two endpoints are one feature. ``Side.CENTER`` endpoints are SKIPPED: they mark
      a road dying mid-tile (a crossroads is four separate ``(side, CENTER)``
      connections, which must stay four features) and CENTER is the monastery's own
      slot, which a road must never be merged into.
    * ``tile.farms: [FarmerConnection]`` — every ``farmer_positions`` entry of one
      connection is an equivalent placement on the same field.

    A monastery (``chapel``/``flowers``) is a feature of one slot, ``CENTER``.
    Anything the model does not describe is simply absent from the returned map, and
    ``meeple_slots_for`` gives it a private group — never a shared one.
    """
    groups: dict[str, int] = {}
    nxt = 0
    if tile is None:
        return groups

    for side_group in getattr(tile, "city", ()) or ():
        touched = False
        for side in side_group:
            groups[side.value] = nxt
            touched = True
        if touched:
            nxt += 1

    for conn in getattr(tile, "road", ()) or ():
        touched = False
        for side in (conn.a, conn.b):
            if side is None or side == Side.CENTER:
                continue
            groups[side.value] = nxt
            touched = True
        if touched:
            nxt += 1

    if getattr(tile, "chapel", False) or getattr(tile, "flowers", False):
        groups[Side.CENTER.value] = nxt
        nxt += 1

    for farm in getattr(tile, "farms", ()) or ():
        touched = False
        for side in getattr(farm, "farmer_positions", ()) or ():
            groups[side.value] = nxt
            touched = True
        if touched:
            nxt += 1

    return groups


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
                 generation: int):
        self.seed = int(seed)
        self.human_player = int(human_player)
        self.opponent_kind = str(opponent)
        self.req_sims = None if sims is None else int(sims)
        self.req_k_dets = None if k_dets is None else int(k_dets)
        self.verify = bool(verify)
        self.generation = int(generation)

        self.game = Game(enable_legal_moves_cache=True)
        # The agent gets its OWN Game (mirrors play_vs_tier1_gui.build_opponent): the
        # UI-side Game carries a legal-moves cache and the agent may run on another
        # thread, so private Games remove any chance of a cross-thread cache race.
        self.ai_game = Game(enable_legal_moves_cache=True)

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
        eff_sims = spec.sims_per_det if self.req_sims is None else int(self.req_sims)
        eff_k = spec.k_dets if self.req_k_dets is None else int(self.req_k_dets)
        agent = champion_factory.make_production_champion(
            "fair", game=self.ai_game, seed=self.seed, sims=eff_sims, k_dets=eff_k,
            exact_endgame=True, verify=self.verify,
        )
        _wrap_evaluator_with_counter(agent)
        self.agent = agent
        self.pick = lambda board: int(agent.choose_action(board))
        self.manifest = getattr(agent, "manifest", None)
        self.eff_sims, self.eff_k_dets = eff_sims, eff_k

        self.opponent_name = "Champion"
        self.budget_note = None
        if (eff_sims, eff_k) != (spec.sims_per_det, spec.k_dets):
            full = spec.k_dets * spec.sims_per_det
            self.budget_note = (
                f"BELOW CHAMPION BUDGET — running k{eff_k}x{eff_sims}="
                f"{eff_k * eff_sims} sims/move vs the champion's "
                f"k{spec.k_dets}x{spec.sims_per_det}={full}. This is a WEAKENED agent; "
                f"beating it is not beating the champion.")
            self.opponent_name = f"Champion(weakened k{eff_k}x{eff_sims})"

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
        "ai_last_tile": ({"row": s.ai_last_tile[0], "col": s.ai_last_tile[1]}
                         if s.ai_last_tile is not None else None),
        "ai_last_move": s.ai_last_move,
        "is_terminated": terminated,
        "n_actions": len(s.action_log),
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
        s.apply(idx)
        s.auto_pass_forced()
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
        s.apply(idx)
        s.auto_pass_forced()

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


def get_ownership() -> str:
    """Every CLAIMED feature on the board: kind, the cells it covers, and who owns it.

    Feeds the ownership overlay. Read-only and on demand — the UI calls it when the
    toggle is on and after each state change, never in the search hot path.

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

        for player, positions in enumerate(state.placed_meeples):
            for mp in positions:
                cws = mp.coordinate_with_side
                coord = cws.coordinate
                tile = state.board[coord.row][coord.column]
                if tile is None:
                    continue
                kind, cells, finished, points, meeples = None, [], None, 0, None
                try:
                    if mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                        farm = FarmUtil.find_farm_by_coordinate(state, position=cws)
                        kind = "farm"
                        cells = sorted({
                            (int(f.coordinate.row), int(f.coordinate.column))
                            for f in farm.farmer_connections_with_coordinate
                        })
                        meeples = FarmUtil.find_meeples(state, farm)
                        points = int(PointsCollector.count_farm_points(state, farm))
                    else:
                        terrain = tile.get_type(cws.side)
                        if terrain == TerrainType.CITY:
                            city = CityUtil.find_city(state, cws)
                            kind = "city"
                            cells = _cells(city.city_positions)
                            finished = bool(city.finished)
                            meeples = CityUtil.find_meeples(state, city)
                            points = int(PointsCollector.count_city_points(state, city))
                        elif terrain == TerrainType.ROAD:
                            road = RoadUtil.find_road(state, cws)
                            kind = "road"
                            cells = _cells(road.road_positions)
                            finished = bool(road.finished)
                            meeples = RoadUtil.find_meeples(state, road)
                            points = int(PointsCollector.count_road_points(state, road))
                        elif terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                            kind = "chapel"
                            cells = [(int(coord.row), int(coord.column))]
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
    """The YAML champion budget, so the UI never hardcodes a strength knob."""
    try:
        spec = champion_factory.load_production_spec()
        return _ok({"ok": True, "champion_id": spec.champion_id,
                    "sims_per_det": spec.sims_per_det, "k_dets": spec.k_dets,
                    "total_sims": spec.k_dets * spec.sims_per_det,
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
        return _ok({
            "ok": True,
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "numpy": np.__version__,
            "cython": cython,
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
