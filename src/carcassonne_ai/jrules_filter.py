"""J-RULES AS ROOT FILTERS (surface C) — the PYTHON REFERENCE MIRROR.

⚠️ NEVER a production path. The production filter is
``carc_core::fair::jrules_filter`` (rust), bound into
``FairAgent::pimc_move`` behind ``SearchConfig.jrules_filter_mask`` (default 0
= OFF = the champion, bit-for-bit). This module exists so the rust filter has
an independently-written twin to be compared against on replayed games
(``tests/test_jrules_filter.py::test_rust_python_filter_parity_on_replayed_games``),
exactly as ``jrules_priors.py`` mirrors surface B.

The filter is ``joshua_bot.JoshuaBot._apply_filters`` — the bot's four HARD
FILTERS, F-END / F-J10 / F-J9 / F-J3, in that fixed order, each individually
guarded by the never-empty rule — applied to the ROOT legal-action set of the
production fair-PIMC agent before any world search runs. MEEPLE-phase roots
only (the bot never hard-filters tile candidates). See
``measurement/jrules_filters_20260814/DESIGN.md``.

Frozen parameters (== ``joshua_bot.PRESETS["current"]``, the epoch the
tournament selected; pinned by ``test_constants_match_joshua_bot``):

* ``k0`` frozen at 72 (``flat_leaf.JR_K0`` precedent — the bot latches k0 at
  its first move, which in every real game is 72);
* ``j8_break_reserve_floor`` frozen OFF ⇒ F-J3 has NO pivotal-overcommit
  exemption here (a ``j8brk`` variant is a named, unexercised option);
* F-J9 exists as a mask bit but is NOT in ``JF_CURRENT`` (the bot's
  ``j9_avoid_cloisters`` is opt-in and defaults OFF).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from wingedsheep.carcassonne.objects.terrain_type import TerrainType

from .action_space import decode, meeple_farmer_base, meeple_pass_index
from .joshua_bot import analyze, k_remaining, surrounding_count

__all__ = [
    "JF_END", "JF_J10", "JF_J9", "JF_J3", "JF_ALL", "JF_CURRENT",
    "JF_FILTER_NAMES", "JF_J3_RESERVE_FLOOR", "JF_J3_ENDGAME_RELEASE_K",
    "JF_EARLY_FARM_BLOCK_FRAC", "JF_J9_CLOISTER_BLOCK_FRAC",
    "JF_J9_MIN_SURROUNDING", "JF_K0", "FilterOutcome", "jrules_root_filter",
    "mask_filters",
]

# --- mask bits (a filter is binary per rule; there is no dose) --------------
JF_END = 1    #: endgame deployment — k <= my reserve ⇒ drop PASS
JF_J10 = 2    #: early-farmer block — no FARMER claim while the bag is full
JF_J9 = 4     #: cloister caution (the bot's OPT-IN axis)
JF_J3 = 8     #: own-reserve floor — never spend the last meeple except
#:               closures / majority swings
JF_ALL = JF_END | JF_J10 | JF_J9 | JF_J3            # == 15
#: The bot's `current`-preset stack: F-END + F-J10 + F-J3 (J9 is opt-in OFF).
JF_CURRENT = JF_END | JF_J10 | JF_J3                # == 11

#: Application order — index into FilterOutcome.fires / .yields.
JF_FILTER_NAMES = ("f_end", "f_j10", "f_j9", "f_j3")

# --- FROZEN `current`-preset parameters (pinned against JoshuaParams) -------
JF_J3_RESERVE_FLOOR = 1
JF_J3_ENDGAME_RELEASE_K = 8
JF_EARLY_FARM_BLOCK_FRAC = 0.55
JF_J9_CLOISTER_BLOCK_FRAC = 0.55
JF_J9_MIN_SURROUNDING = 6
#: The frozen game clock's k0 — `flat_leaf.JR_K0`'s value, duplicated to keep
#: this module import-light; pinned by `test_constants_match_flat_leaf_k0`.
JF_K0 = 72.0

_CLOISTER_TERRAIN = (TerrainType.CHAPEL, TerrainType.FLOWERS)


@dataclass
class FilterOutcome:
    """Mirror of `carc_core::fair::jrules_filter::FilterOutcome`."""

    kept: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    fires: list = field(default_factory=lambda: [False] * 4)
    yields: list = field(default_factory=lambda: [False] * 4)
    applicable: bool = False

    def as_dict(self) -> dict:
        return {
            "applicable": self.applicable,
            "kept": list(self.kept),
            "dropped": list(self.dropped),
            "fires": dict(zip(JF_FILTER_NAMES, self.fires)),
            "yields": dict(zip(JF_FILTER_NAMES, self.yields)),
        }


def mask_filters(mask: int) -> list:
    """``11`` -> ``['f_end', 'f_j10', 'f_j3']`` — the filters a mask enables."""
    bits = (JF_END, JF_J10, JF_J9, JF_J3)
    return [n for n, b in zip(JF_FILTER_NAMES, bits) if int(mask) & b]


def _tag(game, board, action: int, me: int, need_j3: bool) -> dict:
    """`joshua_bot.JoshuaBot._tag_meeple` for ONE meeple-phase root action."""
    state = board.state
    w = game.window_size
    t = {"is_meeple_place": False, "is_farmer": False, "is_cloister": False,
         "cloister_strong": False, "closes_own": False, "swings_majority": False}
    if action >= meeple_pass_index(w):
        return t                                     # PASS
    t["is_meeple_place"] = True
    t["is_farmer"] = meeple_farmer_base(w) <= action < meeple_pass_index(w)
    act = decode(action, off=board.offset, phase=state.phase.value,
                 next_tile=state.next_tile,
                 last_tile_coord=(state.last_tile_action.coordinate
                                  if state.last_tile_action is not None else None))
    cws = getattr(act, "coordinate_with_side", None)
    if cws is None:
        return t
    r, c, side = cws.coordinate.row, cws.coordinate.column, cws.side
    tile = state.board[r][c]
    if tile is None:
        return t                                     # the bot bails the same way
    terrain = tile.get_type(side)
    if terrain in _CLOISTER_TERRAIN:
        t["is_cloister"] = True
        t["cloister_strong"] = (
            surrounding_count(state.board, r, c) >= JF_J9_MIN_SURROUNDING)
        return t
    if not need_j3:
        return t                                     # closes/swings feed F-J3 only

    nb, _ = game.get_next_state(board, action)       # the child afterstate
    after = analyze(nb.state)
    d = after.decomp
    opp = 1 - me
    if terrain == TerrainType.CITY:
        root = d.city_side_root.get((r, c, side))
        counts, finished = after.city_counts, d.city_root_finished
    elif terrain == TerrainType.ROAD:
        root = d.road_side_root.get((r, c, side))
        counts, finished = after.road_counts, d.road_root_finished
    else:
        root = d.farm_pos0_root.get((r, c, side))
        counts, finished = after.farm_counts, {}     # farms never "finish"
    if root is None:
        return t
    t["closes_own"] = bool(finished.get(root, False))
    cnt = counts.get(root)
    if cnt and cnt[opp] >= 1 and cnt[me] >= cnt[opp]:
        t["swings_majority"] = True
    return t


def jrules_root_filter(game, board, mask: int, min_keep: int = 1) -> FilterOutcome:
    """The root filter — pure; consumes no RNG; MEEPLE-phase roots only.

    ``game``/``board`` are the wrapper Game and the root Board (never mutated:
    children go through ``get_next_state``). Semantics mirror the rust filter
    bit-for-bit; see the module docstring.
    """
    import numpy as np

    mask = int(mask)
    if mask & ~JF_ALL:
        raise ValueError(f"jrules_filter: mask {mask} has bits outside JF_ALL ({JF_ALL})")
    state = board.state
    legal = [int(i) for i in np.flatnonzero(game.get_valid_moves(board))]
    out = FilterOutcome(kept=list(legal))
    if mask == 0 or state.phase.value != "meeples" or len(legal) <= 1:
        return out                                   # tiles phase / forced / OFF
    out.applicable = True
    min_keep = max(1, int(min_keep))

    me = int(state.current_player)
    k = k_remaining(state)
    my_reserve = int(state.meeples[me])
    endgame = k <= my_reserve

    j3_armed = bool(mask & JF_J3) and not endgame \
        and k > JF_J3_ENDGAME_RELEASE_K and my_reserve <= JF_J3_RESERVE_FLOOR

    tags = {a: _tag(game, board, a, me, j3_armed) for a in legal}

    def _apply(kept: list, idx: int, pred) -> list:
        filtered = [a for a in kept if pred(tags[a])]
        if len(filtered) < len(kept):
            if len(filtered) >= min_keep:
                out.fires[idx] = True
                return filtered
            out.yields[idx] = True
        return kept

    kept = list(legal)
    if mask & JF_END and endgame:
        kept = _apply(kept, 0, lambda t: t["is_meeple_place"])
    if mask & JF_J10 and JF_EARLY_FARM_BLOCK_FRAC > 0.0 \
            and k > JF_EARLY_FARM_BLOCK_FRAC * max(JF_K0, 1.0):
        kept = _apply(kept, 1, lambda t: not t["is_farmer"])
    if mask & JF_J9 and k > JF_J9_CLOISTER_BLOCK_FRAC * max(JF_K0, 1.0):
        kept = _apply(kept, 2,
                      lambda t: (not t["is_cloister"]) or t["cloister_strong"])
    if j3_armed:
        # j8_break_reserve_floor is FROZEN OFF (the tournament-selected
        # `current` preset), so there is no pivotal-overcommit exemption.
        kept = _apply(kept, 3, lambda t: (not t["is_meeple_place"])
                      or t["closes_own"] or t["swings_majority"])

    out.kept = kept
    out.dropped = [a for a in legal if a not in kept]
    return out
