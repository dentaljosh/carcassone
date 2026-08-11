"""Intra-tile meeple-action equivalence — the SINGLE SOURCE OF TRUTH for grouping.

Two legal meeple actions are *game-equivalent* when they claim the SAME connected
feature on the just-placed tile: a city with two openings (``city=[[TOP, RIGHT]]``)
offers a knight slot on each opening, but either slot claims the one city. Placing on
either yields a position that scores identically for the rest of the game — Carcassonne
features only ever MERGE, never split, so an equivalence established on the tile can
never be undone by a later placement.

Three consumers, one definition (this module):

* ``android_bridge.feature_groups`` — the Android UI collapses duplicate meeple dots.
  It re-exports the function from here; this module is where it now lives.
* ``scripts/measurement_infra/meeple_dedup_census.py`` — the census that measured
  60.75% of the champion's meeple decisions as containing >=2 equivalent actions
  (measurement/classical_search/meeple_dedup_census_20260727.json).
* ``mcts.NeuralMCTS`` — the MEEPLE-DEDUP search feature (flag-gated, default OFF):
  at meeple-phase nodes it keeps only the lowest-action-id member of each group, so
  the prior mass is not split and no duplicate subtree is ever built.

⚠️ **INTRA-TILE ONLY — a LOWER BOUND on true equivalence.** ``feature_groups`` is a
pure read of ONE tile. Two sides that are separate *on the tile* but already joined
into one feature *through the rest of the board* (the common case for farms) are
reported here as distinct. That direction is the safe one: this module never claims an
equivalence that does not hold, it only misses some that do. A board-level union-find
grouping would be a strictly larger (and separately-validated) change.

THE FLAG
--------
``CARCASSONNE_MEEPLE_DEDUP=1`` turns the search feature on process-wide. It is read
ONCE here at import (like the leaf knobs) into ``MEEPLE_DEDUP``. Default OFF, and OFF
is a provably untouched code path in ``mcts`` — see the flag's use site there.

``NeuralMCTS(..., meeple_dedup=True/False)`` overrides the global PER AGENT, which is
what a candidate-vs-champion screen needs: both players usually live in ONE worker
process, so a purely process-global flag could not run a dedup-ON candidate against a
dedup-OFF champion. ``None`` (the default) means "inherit ``MEEPLE_DEDUP``".
"""
from __future__ import annotations

import os

from wingedsheep.carcassonne.objects.game_phase import GamePhase
from wingedsheep.carcassonne.objects.side import Side

from .action_space import FARMER_SIDES, NORMAL_SIDES, meeple_normal_base

# --------------------------------------------------------------------------- #
# The flag                                                                     #
# --------------------------------------------------------------------------- #
ENV_VAR = "CARCASSONNE_MEEPLE_DEDUP"
# How the dropped members' prior mass is handled. "fold" (default) moves it onto the
# surviving representative — the group competes ONCE with the mass the evaluator gave
# the concept, exactly the convention `_NeuralNode.prior_bonus` already uses for
# byte-identical transposition aliases. "drop" discards it and renormalizes over the
# survivors, which instead makes a 2-opening feature and a 1-opening feature with equal
# leaf deltas get equal prior. See the module's build report — worth an A/B, not a
# free choice, so it is a knob rather than a hardcode.
PRIOR_ENV_VAR = "CARCASSONNE_MEEPLE_DEDUP_PRIOR"
_TRUE = {"1", "true", "yes", "on"}


def _env_flag() -> bool:
    return os.environ.get(ENV_VAR, "0").strip().lower() in _TRUE


def _env_prior_mode() -> str:
    mode = os.environ.get(PRIOR_ENV_VAR, "fold").strip().lower()
    return mode if mode in ("fold", "drop") else "fold"


MEEPLE_DEDUP: bool = _env_flag()
PRIOR_MODE: str = _env_prior_mode()


def enabled() -> bool:
    """The process-wide default for new searches."""
    return MEEPLE_DEDUP


def resolve(flag: bool | None) -> bool:
    """Resolve a per-agent ``meeple_dedup`` kwarg: ``None`` means inherit the flag."""
    return MEEPLE_DEDUP if flag is None else bool(flag)


def set_enabled(on: bool, *, export: bool = True) -> None:
    """Flip the process-wide default at runtime (a CLI flag's entry point).

    ``export`` also writes ``os.environ`` so that multiprocessing children — which
    re-import this module under 'spawn' and would otherwise re-read the *original*
    env — inherit the same setting. Call it BEFORE forking/spawning workers.
    """
    global MEEPLE_DEDUP
    MEEPLE_DEDUP = bool(on)
    if export:
        os.environ[ENV_VAR] = "1" if on else "0"


# --------------------------------------------------------------------------- #
# Grouping (moved verbatim from android_bridge.feature_groups, 2026-07-27)      #
# --------------------------------------------------------------------------- #
def feature_groups(tile) -> dict[str, int]:
    """Map each meeple-able ``Side.value`` on ONE tile to an intra-tile feature id.

    Two sides sharing an id are two openings onto the SAME feature, so a meeple on
    either claims the same thing — the duplicate choice the UI collapses to a single
    dot and the search collapses to a single child. A city spanning two edges is the
    common case (``city=[[TOP, RIGHT]]``); a straight road is the other
    (``road=[Connection(LEFT, RIGHT)]``).

    Purely a READ of the tile model — no engine call, no board, no action space.

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
    every consumer must give it a PRIVATE group — never a shared one.
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


# --------------------------------------------------------------------------- #
# Action-space view: the 9 meeple slots, memoized per (tile, rotation)          #
# --------------------------------------------------------------------------- #
# Slot i is action index `meeple_normal_base(W) + i` (action_space's layout):
#   0..4 NORMAL on TOP, RIGHT, BOTTOM, LEFT, CENTER
#   5..8 FARMER on TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT
SLOT_SIDES: tuple = NORMAL_SIDES + FARMER_SIDES
N_SLOTS: int = len(SLOT_SIDES)
_N_NORMAL: int = len(NORMAL_SIDES)
# Namespace offset applied to FARMER slot group ids. `feature_groups` already numbers
# every structure distinctly, so knight and farmer ids cannot collide today — this
# makes "a type-different action is NEVER merged" structural rather than incidental.
_FARMER_NS = 1_000
NO_GROUP = -1   # side the tile model does not describe -> always its own private group

# (tile.description, tile.turns) -> per-slot group id. Tiles are immutable and the
# engine's own `Tile.turn` cache makes the rotated tiles canonical, so the pair is a
# complete identity for the placed orientation (and, unlike id(), it survives the
# deepcopy that `get_next_state` performs on every board).
_SLOT_CACHE: dict[tuple[str, int], tuple[int, ...]] = {}


def slot_group_ids(tile) -> tuple[int, ...]:
    """Per-slot equivalence ids for a placed tile — the memoized hot-path table.

    Length ``N_SLOTS`` (9), indexed by ``action - meeple_normal_base(W)``. Equal ids
    mean interchangeable placements; ``NO_GROUP`` means "undescribed side, never
    merge". One dict lookup per meeple decision after the first sighting of each
    (tile, rotation) — 32 base tiles x 4 rotations bounds the table at 128 entries.
    """
    if tile is None:
        return (NO_GROUP,) * N_SLOTS
    key = (tile.description, int(tile.turns))
    cached = _SLOT_CACHE.get(key)
    if cached is not None:
        return cached
    raw = feature_groups(tile)
    ids = []
    for i, side in enumerate(SLOT_SIDES):
        g = raw.get(side.value)
        if g is None:
            ids.append(NO_GROUP)
        else:
            ids.append(int(g) + (0 if i < _N_NORMAL else _FARMER_NS))
    out = tuple(ids)
    _SLOT_CACHE[key] = out
    return out


def placed_tile(board):
    """The tile the current meeple decision is about, or None if there isn't one."""
    state = board.state
    if state.phase != GamePhase.MEEPLES:
        return None
    last = state.last_tile_action
    if last is None:
        return None
    coord = last.coordinate
    return state.board[coord.row][coord.column]


def dedup_legal(board, legal):
    """Positions of ``legal`` to KEEP, and the prior mass to fold, at a meeple node.

    ``legal`` is the ascending array of legal action indices at ``board`` (exactly
    ``np.flatnonzero(mask)``). Returns ``None`` — meaning "nothing to do, use ``legal``
    unchanged" — for every non-meeple phase and for any meeple decision whose options
    are already all distinct. That None fast-path is why the OFF flag costs nothing
    beyond one phase comparison.

    When there IS a duplicate, returns ``(keep_positions, folds)``:

    * ``keep_positions`` — ascending list of indices INTO ``legal``; the survivors are
      the lowest action id of each group plus every non-grouped action (the pass, any
      undescribed side).
    * ``folds`` — ``[(dst_pos, src_pos), ...]``, each saying "the prior mass at
      position ``src_pos`` belongs to the representative at ``dst_pos``".

    Positions rather than action ids so the caller can reindex its prior vector with
    no dict lookups.
    """
    tile = placed_tile(board)
    if tile is None:
        return None
    gids = slot_group_ids(tile)
    base = meeple_normal_base(board.offset.size)
    rep: dict[int, int] = {}                 # group id -> position of representative
    keep: list[int] = []
    folds: list[tuple[int, int]] = []
    for pos, a in enumerate(legal):
        slot = int(a) - base
        # Not one of the 9 slots (the meeple pass, or defensively a stray index) ->
        # never grouped, always kept.
        if slot < 0 or slot >= N_SLOTS:
            keep.append(pos)
            continue
        g = gids[slot]
        if g == NO_GROUP:                    # undescribed side: private group
            keep.append(pos)
            continue
        first = rep.get(g)
        if first is None:
            rep[g] = pos
            keep.append(pos)
        else:
            folds.append((first, pos))
    if not folds:
        return None
    return keep, folds


def equivalent_meeple_action_groups(game, board) -> dict[int, int]:
    """``{action_id: group_id}`` over the CURRENT meeple-phase legal non-pass actions.

    Dense group ids (0, 1, 2, ... in ascending action order); every undescribed side
    gets a private id of its own, matching the UI's ``_renumber_groups`` convention.
    Empty dict when the board is not at a meeple decision.

    This is the readable/public view of the same table ``dedup_legal`` uses — handy for
    tests, telemetry and the census. The search does NOT call it (it wants positions,
    not a dict).
    """
    import numpy as np

    tile = placed_tile(board)
    if tile is None:
        return {}
    gids = slot_group_ids(tile)
    base = meeple_normal_base(board.offset.size)
    out: dict[int, int] = {}
    dense: dict[object, int] = {}
    for a in np.flatnonzero(game.get_valid_moves(board)):
        a = int(a)
        slot = a - base
        if slot < 0 or slot >= N_SLOTS:
            continue                          # the pass action is not a placement
        g = gids[slot]
        key: object = ("solo", a) if g == NO_GROUP else g
        if key not in dense:
            dense[key] = len(dense)
        out[a] = dense[key]
    return out
