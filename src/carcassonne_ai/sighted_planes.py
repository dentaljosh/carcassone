"""Sighted-representation feature helpers (M2 canonical-AZ cell).

The CL-033 "value resurrection" pilot found that a learned value/ranker on the
78-channel board representation CANNOT out-rank the v2.9 heuristic leaf at
sibling ordering (best alpha=0, net-alone Kendall-tau ~0.105 vs leaf ~0.895).
Hypothesis: the value head is inert because the representation is BLIND to
(a) farm connectivity (who owns which field, per cell) and (b) the bag (what
tiles remain). The M2 "sighted" cell appends those two structural signals:

  * farm_connectivity_planes(state, root_player, off, W) -> (3, W, W)
      per-cell live farm ownership, projected onto the SAME centered window as
      encode_board:
        plane0 = root_player owns the field touching this cell (winning farmer)
        plane1 = opponent owns it
        plane2 = contested (both players tie for the winning farmer count)
      Computed off flat_leaf.decompose (the project's fast int-union-find leaf
      path) — NO per-cell FarmUtil.find_farm object traversal.
  * bag_histogram(state) -> (32,)
      per-base-tile-type fraction of that type still in the bag (deck + next_tile
      if in the TILES phase), in [0, 1]. The 32 distinct base-tile descriptions
      and their full-deck counts are frozen below (base game is a fixed 72-tile
      multiset over 32 distinct descriptions; only ORDER varies by seed).

Both are STRUCTURAL: they are functions of the board / bag, NOT of the oracle_q /
leaf_q labels. This is the src-tree home of the standalone helpers first written
in scripts/feature_planes_gate/step1_planes.py (kept byte-identical; a parity
test pins them). Used ONLY when Game(sighted=True); the production 78-channel /
10-or-12-scalar path never imports or calls this module.
"""
from __future__ import annotations

import numpy as np

from wingedsheep.carcassonne.objects.game_phase import GamePhase
from wingedsheep.carcassonne.objects.meeple_type import MeepleType

from .flat_leaf import _winners, decompose

# --- frozen bag census ------------------------------------------------------ #
# Enumerated empirically (build a fresh Game, count the .description of every
# tile in deck + next_tile). The base game is a fixed 72-tile multiset over 32
# distinct descriptions; only the ORDER varies by seed (verified identical
# multiset across fresh games). Frozen here as the canonical sorted ordering +
# full-deck counts so the histogram channel layout never drifts.
BASE_TILE_COUNTS: dict[str, int] = {
    "bent_road": 8,
    "bent_road_flowers": 1,
    "chapel": 4,
    "chapel_with_road": 2,
    "city_bottom_grass": 2,
    "city_bottom_grass_flowers": 1,
    "city_bottom_grass_shield": 1,
    "city_bottom_road": 1,
    "city_bottom_road_shield": 2,
    "city_diagonal_top_left_road": 3,
    "city_diagonal_top_left_shield_road": 2,
    "city_diagonal_top_right": 2,
    "city_diagonal_top_right_flowers": 1,
    "city_diagonal_top_right_shield": 1,
    "city_diagonal_top_right_shield_flowers": 1,
    "city_left_right": 2,
    "city_narrow": 1,
    "city_narrow_shield": 2,
    "city_top": 4,
    "city_top_bottom_flowers": 1,
    "city_top_crossroads": 3,
    "city_top_flowers": 1,
    "city_top_left_flowers": 1,
    "city_top_right": 1,
    "city_top_road_bend_left": 3,
    "city_top_road_bend_right": 3,
    "city_top_straight_road": 4,
    "crossroads": 1,
    "full_city_with_shield": 1,
    "straight_road": 7,
    "straight_road_flowers": 1,
    "three_split_road": 4,
}
BAG_ORDER: list[str] = sorted(BASE_TILE_COUNTS)
N_BAG = len(BAG_ORDER)
_BAG_INDEX: dict[str, int] = {d: i for i, d in enumerate(BAG_ORDER)}
_BAG_MAX = np.array([BASE_TILE_COUNTS[d] for d in BAG_ORDER], dtype=np.float32)

assert N_BAG == 32, f"expected 32 distinct base-tile types, got {N_BAG}"
assert sum(BASE_TILE_COUNTS.values()) == 72, (
    f"expected 72 base tiles, got {sum(BASE_TILE_COUNTS.values())}"
)

N_FARM_PLANES = 3
FARM_PLANE_ROOT = 0      # root_player owns the field touching this cell
FARM_PLANE_OPP = 1       # opponent owns it
FARM_PLANE_CONTESTED = 2  # both players tie for the winning farmer count


def _farm_component_owners(state, decomp, root_player):
    """root -> owner status for each MEEPLED farm component, root-POV.

    Mirrors flat_leaf._final_scores' farm mapping exactly: place each placed
    FARMER on its component via farm_pos0_root (find_meeples semantics, keyed by
    farmer_positions[0]), tally weighted per-player counts, and award by
    _winners (max meeple count; >=2 winners = tied/contested). Returns a dict
    root -> "self" | "opp" | "contested" (only for components that carry >=1
    farmer; unmeepled fields are absent == score nothing).
    """
    opp = 1 - root_player
    farm_counts: dict = {}
    for player in range(state.players):
        for mp in state.placed_meeples[player]:
            if mp.meeple_type not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                continue
            cws = mp.coordinate_with_side
            r = cws.coordinate.row
            c = cws.coordinate.column
            side = cws.side
            w = 2 if mp.meeple_type == MeepleType.BIG_FARMER else 1
            root = decomp.farm_pos0_root.get((r, c, side))
            if root is not None:
                cnt = farm_counts.get(root)
                if cnt is None:
                    cnt = [0] * state.players
                    farm_counts[root] = cnt
                cnt[player] += w

    owners: dict = {}
    for root, cnt in farm_counts.items():
        winners = _winners(cnt)
        if not winners:
            continue
        if len(winners) >= 2:
            owners[root] = "contested"
        elif winners[0] == root_player:
            owners[root] = "self"
        elif winners[0] == opp:
            owners[root] = "opp"
    return owners


def farm_connectivity_planes(state, root_player, off, W) -> np.ndarray:
    """Per-cell live farm ownership, projected onto encode_board's window.

    For each MEEPLED + decided farm component, project all its tile cells onto
    the window and set the owner plane:
      plane0 (root) / plane1 (opp) / plane2 (contested).
    A cell may touch several farm fields (e.g. opposite corners on a split tile);
    we OR the owner flags across all fields touching the cell, so a cell can be
    flagged for both players (and/or contested) — this is the honest per-cell
    "which sides' farmers reach a field through this tile" signal.

    `off` is the SAME board_repr.WindowOffset encode_board used for this state
    (origin_row/origin_col/size). Cells outside the window are dropped exactly
    like encode_board does.
    """
    planes = np.zeros((N_FARM_PLANES, W, W), dtype=np.float32)
    decomp = decompose(state)
    owners = _farm_component_owners(state, decomp, root_player)
    if not owners:
        return planes
    or_ = off.origin_row
    oc = off.origin_col
    for root, status in owners.items():
        if status == "self":
            ch = FARM_PLANE_ROOT
        elif status == "opp":
            ch = FARM_PLANE_OPP
        else:
            ch = FARM_PLANE_CONTESTED
        cells = {(r, c) for (r, c, _fc) in decomp.farm_root_keys[root]}
        for (r, c) in cells:
            wr = r - or_
            wc = c - oc
            if 0 <= wr < W and 0 <= wc < W:
                planes[ch, wr, wc] = 1.0
    return planes


def bag_histogram(state) -> np.ndarray:
    """(32,) per-base-tile-type fraction of that type still in the bag.

    bag = state.deck (+ state.next_tile if in the TILES phase: it is the drawn
    tile awaiting placement, i.e. still 'remaining' from the decision's POV).
    Each type's remaining count is divided by its full-deck count -> [0, 1]
    (a fresh bag is all-ones; an exhausted bag all-zeros).
    """
    counts = np.zeros(N_BAG, dtype=np.float32)
    for t in state.deck:
        i = _BAG_INDEX.get(getattr(t, "description", None))
        if i is not None:
            counts[i] += 1.0
    nt = getattr(state, "next_tile", None)
    if nt is not None and state.phase == GamePhase.TILES:
        i = _BAG_INDEX.get(getattr(nt, "description", None))
        if i is not None:
            counts[i] += 1.0
    return counts / _BAG_MAX
