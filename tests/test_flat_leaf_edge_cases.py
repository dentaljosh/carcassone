"""Edge-case equivalence tests for the flat leaf — the branches the random
base-game gate (scripts/reconcile_flat_leaf.py) CANNOT reach.

The gate plays random Base+Farmers games, so it never exercises:
  - tile.inn (cathedral on cities / inn on roads) — no inn tiles in the base deck,
  - tile.shield combos in those cathedral paths,
  - BIG / BIG_FARMER meeples (weight 2 in get_meeple_counts_per_player).

flat_leaf reproduces all of these engine branches (_city_points cathedral, _road_points
inn, _meeple_weight==2), so they must be tested directly. We take REAL mid-game states
and apply minimal synthetic mutations (a fresh inn'd/shield'd Tile in a city/road; a
meeple's type bumped to BIG), then assert the flat leaf still equals the engine
bit-exactly. Both flat and engine read the SAME mutated state, so the comparison is
valid even though the state is synthetic.

Runnable as pytest OR standalone:
  PYTHONPATH=.../src:.../engine CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 \
    python tests/test_flat_leaf_edge_cases.py
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402
import carcassonne_ai.virtual_score_v2 as _v2  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score import virtual_score  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2  # noqa: E402
from wingedsheep.carcassonne.objects.meeple_type import MeepleType  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402
from wingedsheep.carcassonne.objects.terrain_type import TerrainType  # noqa: E402
from wingedsheep.carcassonne.objects.tile import Tile  # noqa: E402


def _collect(n_games: int = 12, snap_every: int = 5, seed: int = 4242):
    g = Game()
    states = []
    for gi in range(n_games):
        random.seed(seed + gi)
        b = g.get_init_board()
        plies = 0
        while g.get_game_ended(b, 0) == 0.0 and plies < 400:
            legal = np.flatnonzero(g.get_valid_moves(b))
            if legal.size == 0:
                break
            b, _ = g.get_next_state(b, int(random.choice(legal.tolist())))
            plies += 1
            if plies % snap_every == 0 and g.get_game_ended(b, 0) == 0.0 and b.state.players == 2:
                states.append(b.state)
        if b.state.players == 2:
            states.append(b.state)
    return states


def _clone_tile(t, inn=None, shield=None):
    """Fresh Tile copying t's STRUCTURE (city/road/farms shared — immutable tile
    defs) with inn/shield overridden. Fresh object => isolated id => the 4b
    per-tile feature cache recomputes; inn/shield don't affect get_type or the
    decomposition, only scoring, so the component partition is unchanged."""
    return Tile(
        description=t.description, turns=t.turns, road=t.road, river=t.river,
        city=t.city, grass=t.grass, farms=t.farms,
        shield=t.shield if shield is None else shield,
        chapel=t.chapel, flowers=t.flowers,
        inn=t.inn if inn is None else inn,
        cathedral=t.cathedral, unplayable_sides=t.unplayable_sides, image=t.image,
    )


def _flat_eq_engine(state) -> bool:
    """flat == engine for base (int) AND full v2 (int, canonical) both players."""
    for p in range(2):
        if flat_leaf.flat_base_score(state, p) != virtual_score(state, p):
            return False
    saved = _v2.CANONICAL_BONUS_SUM
    _v2.CANONICAL_BONUS_SUM = True
    try:
        for p in range(2):
            if flat_leaf.flat_virtual_score_v2(state, p, DEFAULT_CONFIG) != virtual_score_v2(
                state, p, DEFAULT_CONFIG
            ):
                return False
    finally:
        _v2.CANONICAL_BONUS_SUM = saved
    return True


def _first_meeple_on(state, terrain):
    """(player, idx, meeple) for the first placed meeple whose tile.get_type(side)
    is `terrain` (or, for farms, a FARMER meeple)."""
    for player in range(2):
        for idx, mp in enumerate(state.placed_meeples[player]):
            cws = mp.coordinate_with_side
            tile = state.board[cws.coordinate.row][cws.coordinate.column]
            if tile is None:
                continue
            t = tile.get_type(cws.side)
            if terrain == "FARM":
                if mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                    return player, idx, mp
            elif t == terrain:
                return player, idx, mp
    return None


def test_cathedral_inn_and_shield_branches():
    """A fresh inn'd / shield'd Tile inside a meepled city must score identically
    flat vs engine (count_city_points cathedral/shield paths, incl. the unfinished
    cathedral -> 0 rule)."""
    states = _collect()
    inn_hits = shield_hits = road_inn_hits = 0
    for state in states:
        # cathedral: inn a tile of a city that holds a knight
        hit = _first_meeple_on(state, TerrainType.CITY)
        if hit is not None:
            _p, _i, mp = hit
            r, c = mp.coordinate_with_side.coordinate.row, mp.coordinate_with_side.coordinate.column
            orig = state.board[r][c]
            state.board[r][c] = _clone_tile(orig, inn=(Side.TOP,))
            assert _flat_eq_engine(state), f"cathedral mismatch at {(r, c)}"
            inn_hits += 1
            state.board[r][c] = _clone_tile(orig, shield=True)
            assert _flat_eq_engine(state), f"shield mismatch at {(r, c)}"
            shield_hits += 1
            state.board[r][c] = orig
        # inn on a road that holds a meeple
        hitr = _first_meeple_on(state, TerrainType.ROAD)
        if hitr is not None:
            _p, _i, mp = hitr
            r, c = mp.coordinate_with_side.coordinate.row, mp.coordinate_with_side.coordinate.column
            orig = state.board[r][c]
            state.board[r][c] = _clone_tile(orig, inn=(Side.TOP,))
            assert _flat_eq_engine(state), f"road-inn mismatch at {(r, c)}"
            road_inn_hits += 1
            state.board[r][c] = orig
    assert inn_hits > 0 and shield_hits > 0 and road_inn_hits > 0, (
        f"insufficient coverage: inn={inn_hits} shield={shield_hits} road_inn={road_inn_hits}"
    )


def test_big_meeple_weight_two():
    """A BIG / BIG_FARMER meeple counts 2 (get_meeple_counts_per_player) — the flat
    _meeple_weight==2 path. Bumping a placed meeple's type must keep flat == engine
    (it can flip the majority winner, which both must resolve identically)."""
    states = _collect()
    knight_hits = farmer_hits = 0
    for state in states:
        for terrain, big in ((TerrainType.CITY, MeepleType.BIG),
                             (TerrainType.ROAD, MeepleType.BIG),
                             ("FARM", MeepleType.BIG_FARMER)):
            hit = _first_meeple_on(state, terrain)
            if hit is None:
                continue
            _p, _i, mp = hit
            saved = mp.meeple_type
            mp.meeple_type = big
            try:
                assert _flat_eq_engine(state), f"big-meeple mismatch ({terrain})"
            finally:
                mp.meeple_type = saved
            if terrain == "FARM":
                farmer_hits += 1
            else:
                knight_hits += 1
    assert knight_hits > 0 and farmer_hits > 0, (
        f"insufficient coverage: knight/road={knight_hits} farmer={farmer_hits}"
    )


def test_base_score_cy_dispatch_is_bit_exact():
    """flat_base_score's USE_CY_LEAF dispatch (2026-07-28, the exact solver's terminal
    leaf — measurement/ANDROID_WALLCLOCK_MEMO_20260728.md lever #2) must be a pure
    speed change: integer output, so the bar is plain ==, on real states at every depth.

    The full population gate is scripts/reconcile_cy_leaf.py; this is the in-suite
    canary that the dispatch keeps routing and keeps agreeing."""
    import pytest

    try:
        from carcassonne_ai import flat_leaf_cy  # noqa: F401
    except ImportError:
        pytest.skip("flat_leaf_cy .so not built on this box")

    states = _collect(n_games=4, snap_every=3)
    assert len(states) > 40, "too few states to be a meaningful check"
    saved = flat_leaf.USE_CY_LEAF
    try:
        for state in states:
            for p in range(2):
                flat_leaf.USE_CY_LEAF = False
                py = flat_leaf.flat_base_score(state, p)
                flat_leaf.USE_CY_LEAF = True
                assert flat_leaf.flat_base_score(state, p) == py
                # ...and the engine reference, so a cy==py agreement on a WRONG
                # value cannot pass.
                assert py == virtual_score(state, p)
    finally:
        flat_leaf.USE_CY_LEAF = saved


def test_base_score_with_explicit_decomp_stays_on_python():
    """A caller that supplies a `decomp` expects THAT decomposition to be scored; the cy
    entry point takes only (state, player) and would silently ignore it. Poison the bound
    function to prove the redirect does not fire on that path."""
    states = _collect(n_games=1, snap_every=7)
    state = states[-1]

    def _poison(*a, **k):
        raise AssertionError("flat_base_score redirected despite an explicit decomp")

    saved_flag, saved_bind = flat_leaf.USE_CY_LEAF, flat_leaf._CY_BASE
    try:
        flat_leaf.USE_CY_LEAF = True
        flat_leaf._CY_BASE = _poison
        got = flat_leaf.flat_base_score(state, 0, flat_leaf.decompose(state))
        flat_leaf.USE_CY_LEAF = False
        assert got == flat_leaf.flat_base_score(state, 0)
    finally:
        flat_leaf.USE_CY_LEAF, flat_leaf._CY_BASE = saved_flag, saved_bind


def test_base_score_falls_back_when_the_so_is_missing():
    """A box without the .so (or with a STALE one predating the export) must degrade to
    pure Python, not crash — the graceful-fallback contract the v2 leaf already keeps."""
    states = _collect(n_games=1, snap_every=7)
    state = states[-1]
    saved_flag, saved_bind = flat_leaf.USE_CY_LEAF, flat_leaf._CY_BASE
    try:
        flat_leaf.USE_CY_LEAF = False
        expect = flat_leaf.flat_base_score(state, 0)
        flat_leaf.USE_CY_LEAF = True
        flat_leaf._CY_BASE = False          # the "missing/stale .so" sentinel
        assert flat_leaf.flat_base_score(state, 0) == expect
    finally:
        flat_leaf.USE_CY_LEAF, flat_leaf._CY_BASE = saved_flag, saved_bind


if __name__ == "__main__":
    test_cathedral_inn_and_shield_branches()
    print("PASS: cathedral / inn / shield branches flat == engine")
    test_big_meeple_weight_two()
    print("PASS: BIG / BIG_FARMER weight-2 branch flat == engine")
    print("All edge-case equivalence tests passed.")
