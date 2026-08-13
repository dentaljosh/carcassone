"""J-RULES ON SEARCH — the 2026-08-12 anchor interview as one leaf bundle
(`LeafConfig.jrules_dose` / `jrules_mask`).

WHY THIS TERM EXISTS. The 2026-08-13 Joshua-bot tournament measured the owner's
self-described strategy (J1..J9, `measurement/e4_games/ANCHOR_INTERVIEW_2026-08-12.md`)
as a SCRIPTED opponent and it lost to the production champion by -16.0 pts/deck at
z -24.4 — *weaker than JCloisterZone's shallow AI* at -6.5
(`measurement/joshuabot_20260812/CONFIRM_VERDICT.md`). That result is confounded:
the bot applied the J-rules on a ONE-PLY GREEDY base while the champion ran
11008-sim PIMC, so depth swamped strategy and no amount of n separates them. This
term is the design fix that verdict earned — the same rules on the champion's OWN
leaf, so candidate and opponent differ in STRATEGY ONLY. Spec:
`measurement/jrules_on_search_20260813/DESIGN.md`.

Contracts (the denial / open-city / F7b test-file pattern):
  1. DEFAULT OFF IS INERT. The champion's leaf fingerprints recompute unchanged
     across the two additive fields, and a default-off cfg produces bit-identical
     leaf values (the dose gates the whole bundle — `jrules_mask` is inert while it
     is 0.0, including a moved mask), on BOTH the int and the pre-round float path.
  2. THE ENCODING MATCHES THE BOT. Every frozen parameter equals its
     `joshua_bot.PRESETS["current"]` counterpart, so the two renderings of the
     interview can never silently drift.
  3. PER-RULE FIRES / MUST-NOT-FIRE, pinned on hand-built fixtures, one rule at a
     time via `jrules_mask`. Includes the three THE-JOIN-PAYS transitions (J1, J2,
     J6-road-join): opponent-alone -> tie must RAISE the differential by exactly the
     rule's bonus. That transition is the whole reason those three rules drop the
     bot's "the opponent must already be there" predicate — see DESIGN.md §3.
  4. ANTISYMMETRY. `T(s, p) == -T(s, 1-p)` exactly, on a random-play corpus and on
     the fixtures. The Rust/Python search evaluates the leaf from the MOVER's POV and
     negates on backup, so a non-antisymmetric term is not a coherent zero-sum value
     function.
  5. THE LEAF MOVES BY EXACTLY `+dose * T` — note the SIGN: this bundle is a BONUS
     potential and is ADDED, unlike denial/open-city which are penalties.
  6. ENV/CONFIG PLUMBING round-trips (CARCASSONNE_JRULES_* -> _config_from_env).
  7. THE CY FAST PATH IS REFUSED (no cy implementation — the F7b/denial/open-city
     decision), so a stale `.so` can never serve an intact (J-rule-free) leaf.
  8. THE OBJECT PATH FAILS LOUD rather than silently scoring without the bundle —
     which would read as "the anchor's strategy is worth nothing" instead of "the
     strategy never ran". That misreading is exactly what this build exists to stop.
  9. `rust_agent.leaf_config_rs` forwards the knobs as CONDITIONAL kwargs (a stale
     carc_rs keeps serving default-off configs, a nonzero dose raises TypeError —
     fail-closed loud), and Rust == Python bit-exactly when the loaded build has the
     term (skipped otherwise; the full-corpus gate is
     `scripts/rustport/reconcile_leaf.py --configs jrules`).
 10. FULL-GAME SMOKE: the modified leaf plays complete, legal games to termination.
"""
from __future__ import annotations

import dataclasses as dc
import random
from types import SimpleNamespace

import numpy as np
import pytest
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

from carcassonne_ai import flat_leaf
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import (DEFAULT_CONFIG, LeafConfig,
                                             _config_from_env, virtual_score_v2)

CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
CHAMP = dc.replace(DEFAULT_CONFIG, meeple_k=2.0, bonus_cap=8.0, opp_bonus_cap=8.0,
                   closure_p={1: 0.5, 2: 0.2, 3: 0.05}, v29_meeple_curve=CURVE125)
JR_HALF = dc.replace(CHAMP, jrules_dose=0.5)
JR_ONE = dc.replace(CHAMP, jrules_dose=1.0)
# dose 0.0 with a MOVED mask — must be bit-identical to CHAMP (the dose gates all).
JR_IDENTITY = dc.replace(CHAMP, jrules_dose=0.0, jrules_mask=flat_leaf.JR_J1)


def _cfg(mask: int, dose: float = 1.0) -> LeafConfig:
    return dc.replace(CHAMP, jrules_dose=dose, jrules_mask=mask)


def _cy():
    """The compiled leaf is a BUILD ARTIFACT (gitignored), so it is absent in a fresh
    worktree. Only the two cy-specific contracts need it — deliberately NOT a
    module-level importorskip, which would silently skip the whole term suite on any
    box that has not built the extension."""
    return pytest.importorskip("carcassonne_ai.flat_leaf_cy")


def _states(n_seeds=8, max_plies=140, start=15, every=5, seed_base=8800):
    out = []
    for s in range(n_seeds):
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        rng = random.Random(seed_base + s)
        ply = 0
        while g.get_game_ended(b, 0) == 0.0 and ply < max_plies:
            legal = np.flatnonzero(g.get_valid_moves(b))
            b, _ = g.get_next_state(b, int(rng.choice(legal.tolist())))
            ply += 1
            if ply >= start and ply % every == 0:
                out.append(b.state)
    assert out
    return out


@pytest.fixture(scope="module")
def states():
    return _states()


# --------------------------------------------------------------------------- #
# fixture builder: a minimal state+decomp pair carrying exactly the fields the  #
# J-rules term reads. Feature cells live at (row=i, col=0); the cloister block  #
# lives at rows 20+ so it can never collide with a feature cell.               #
# --------------------------------------------------------------------------- #
class _Tile:
    """A tile whose every side reports one terrain (so CENTER reports it too —
    which is what makes a CITY tile provably NOT a cloister for the J5 scan)."""

    def __init__(self, terrain):
        self.terrain = terrain
        self.inn = False
        self.shield = False

    def get_type(self, side):
        return self.terrain


_TERRAIN = {"city": TerrainType.CITY, "road": TerrainType.ROAD,
            "farm": TerrainType.GRASS, "cloister": TerrainType.CHAPEL,
            "plain": TerrainType.GRASS}
N = MeepleType.NORMAL
BIG = MeepleType.BIG
FARMER = MeepleType.FARMER


def _mk(cities=None, roads=None, farms=None, meeples=(), *,
        k=72, reserves=(4, 4), cloister_blocks=()):
    """cities: {root: (finished, open_n, n_tiles)}  (delta == n_tiles, no shields)
    roads:    {root: (finished, n_tiles)}
    farms:    {root: (n_finished_adj_cities, (adjacent_city_roots, ...))}
    meeples:  [(player, kind, root, meeple_type)] with kind in city/road/farm
    cloister_blocks: [(top_row, n_extra_neighbours)] — an UNCLAIMED cloister at
              (top_row+1, 5) with `n_extra_neighbours` plain tiles filled around it,
              so `_cloister_points` reads `1 + n_extra_neighbours`.
    """
    cities = dict(cities or {})
    roads = dict(roads or {})
    farms = dict(farms or {})
    board = [[None] * 40 for _ in range(40)]
    placed = [[], []]
    placed_coords = []
    city_side_root, road_side_root, farm_pos0_root = {}, {}, {}
    for i, (pl, kind, root, mt) in enumerate(meeples):
        r, c = i, 0
        board[r][c] = _Tile(_TERRAIN[kind])
        placed_coords.append(SimpleNamespace(row=r, column=c))
        key = (r, c, Side.TOP)
        if kind == "city":
            city_side_root[key] = root
        elif kind == "road":
            road_side_root[key] = root
        elif kind == "farm":
            farm_pos0_root[key] = root
        placed[pl].append(SimpleNamespace(
            coordinate_with_side=SimpleNamespace(
                coordinate=SimpleNamespace(row=r, column=c), side=Side.TOP),
            meeple_type=mt))
    for (top, extra) in cloister_blocks:
        cr, cc = top + 1, 5
        board[cr][cc] = _Tile(TerrainType.CHAPEL)
        placed_coords.append(SimpleNamespace(row=cr, column=cc))
        cells = [(cr - 1, cc - 1), (cr - 1, cc), (cr - 1, cc + 1),
                 (cr, cc - 1), (cr, cc + 1),
                 (cr + 1, cc - 1), (cr + 1, cc), (cr + 1, cc + 1)]
        for (rr, ccx) in cells[:extra]:
            board[rr][ccx] = _Tile(TerrainType.GRASS)
            placed_coords.append(SimpleNamespace(row=rr, column=ccx))
    state = SimpleNamespace(
        board=board, placed_meeples=placed, meeples=list(reserves),
        deck=[None] * max(k - 1, 0), next_tile=(object() if k >= 1 else None),
        placed_coords=placed_coords, players=2, scores=[0, 0])
    decomp = flat_leaf.Decomp(
        city_side_root=city_side_root,
        city_root_positions={},
        city_root_coords={r: {(r, i) for i in range(v[2])} for r, v in cities.items()},
        city_root_finished={r: v[0] for r, v in cities.items()},
        city_root_open_n={r: v[1] for r, v in cities.items()},
        city_root_delta={r: v[2] for r, v in cities.items()},
        road_side_root=road_side_root, road_root_positions={},
        road_root_coords={r: {(100 + r, i) for i in range(v[1])} for r, v in roads.items()},
        road_root_finished={r: v[0] for r, v in roads.items()},
        road_root_open_n={r: 1 for r in roads},
        farm_pos0_root=farm_pos0_root, farm_anypos_root={}, farm_root_keys={},
        farm_root_adj_city_roots={r: frozenset(v[1]) for r, v in farms.items()},
        farm_root_finished_cities={r: v[0] for r, v in farms.items()})
    return state, decomp


def _T(st, d, mask, dose=1.0, player=0, base=0.0):
    return flat_leaf.flat_jrules_term(st, player, d, _cfg(mask, dose), base)


# --- 1. default off is inert ------------------------------------------------ #
def test_defaults_are_off_and_env_buildable():
    assert DEFAULT_CONFIG.jrules_dose == 0.0
    assert DEFAULT_CONFIG.jrules_mask == 31 == flat_leaf.JR_ALL
    import inspect

    from carcassonne_ai import virtual_score_v2 as vs2
    assert "CARCASSONNE_JRULES_DOSE" in inspect.getsource(vs2._config_from_env)


def test_env_round_trip(monkeypatch):
    monkeypatch.setenv("CARCASSONNE_JRULES_DOSE", "0.75")
    monkeypatch.setenv("CARCASSONNE_JRULES_MASK", "5")
    cfg = _config_from_env()
    assert cfg.jrules_dose == 0.75
    assert cfg.jrules_mask == 5
    for kk in ("CARCASSONNE_JRULES_DOSE", "CARCASSONNE_JRULES_MASK"):
        monkeypatch.delenv(kk)
    off = _config_from_env()
    assert (off.jrules_dose, off.jrules_mask) == (0.0, 31)


def test_champion_leaf_hashes_unchanged():
    """The additive fields must not move the champion's fingerprints."""
    from carcassonne_ai.alphabeta_agent import _leaf_hash

    assert _leaf_hash(CHAMP) == "a36d2e15a3b3d71d"
    assert _leaf_hash(JR_ONE) != "a36d2e15a3b3d71d"     # a SET dose IS a new leaf
    assert _leaf_hash(JR_HALF) != _leaf_hash(JR_ONE)
    assert _leaf_hash(_cfg(flat_leaf.JR_J1)) != _leaf_hash(JR_ONE)   # mask is part of it


def test_frozen_recipe_hashes_unchanged():
    import sys
    from pathlib import Path

    p = str(Path(__file__).resolve().parents[1] / "scripts" / "measurement_infra")
    if p not in sys.path:
        sys.path.insert(0, p)
    from snapshot import _frozen_config_hash

    assert _frozen_config_hash(CHAMP) == "158f17ff76adaa02"
    assert _frozen_config_hash(dc.replace(CHAMP, meeple_k=0.0)) == "6dfffd57051690f2"


def test_off_is_bit_identical(states):
    """dose 0.0 == champion bit-for-bit, even with a MOVED mask (the dose gates the
    whole bundle), on both the int and the pre-round float path."""
    for st in states:
        for p in (0, 1):
            ref_f = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            assert flat_leaf.flat_virtual_score_v2_float(st, p, JR_IDENTITY).hex() == ref_f.hex()
            assert (flat_leaf.flat_virtual_score_v2(st, p, JR_IDENTITY)
                    == flat_leaf.flat_virtual_score_v2(st, p, CHAMP))


def test_zero_mask_is_zero(states):
    for st in states:
        d = flat_leaf.decompose(st)
        assert flat_leaf.flat_jrules_term(st, 0, d, _cfg(0), 0.0) == 0.0


# --- 2. the encoding matches joshua_bot ------------------------------------- #
def test_constants_match_joshua_bot():
    """Every frozen parameter equals its `PRESETS["current"]` counterpart — the two
    renderings of the same interview may not silently drift."""
    from carcassonne_ai.joshua_bot import PRESETS

    p = PRESETS["current"]
    pairs = [
        ("j1_min_city_tiles", flat_leaf._JR_J1_MIN_CITY_TILES),
        ("j1_min_open_edges", flat_leaf._JR_J1_MIN_OPEN_EDGES),
        ("j1_join_bonus", flat_leaf._JR_J1_JOIN_BONUS),
        ("j1_late_extra", flat_leaf._JR_J1_LATE_EXTRA),
        ("j4_min_urgency", flat_leaf._JR_J4_MIN_URGENCY),
        ("j4_full_reserve", flat_leaf._JR_J4_FULL_RESERVE),
        ("j2_steal_w", flat_leaf._JR_J2_STEAL_W),
        ("j2_min_farm_value", flat_leaf._JR_J2_MIN_FARM_VALUE),
        ("j2_low_farm_penalty", flat_leaf._JR_J2_LOW_FARM_PENALTY),
        ("j2_unfinished_city_weight", flat_leaf._JR_J2_UNFINISHED_CITY_W),
        ("j2_city_count_from_k", flat_leaf._JR_J2_CITY_COUNT_FROM_K),
        ("j2_city_close_open_max", flat_leaf._JR_J2_CITY_CLOSE_OPEN_MAX),
        ("j5_weight", flat_leaf._JR_J5_WEIGHT),
        ("j5_value_floor", flat_leaf._JR_J5_VALUE_FLOOR),
        ("j6_anchor_bonus", flat_leaf._JR_J6_ANCHOR_BONUS),
        ("j6_anchor_city_min", flat_leaf._JR_J6_ANCHOR_CITY_MIN),
        ("j6_anchor_road_min", flat_leaf._JR_J6_ANCHOR_ROAD_MIN),
        ("j6_road_join_min_len", flat_leaf._JR_J6_ROAD_JOIN_MIN_LEN),
        ("j6_road_join_bonus", flat_leaf._JR_J6_ROAD_JOIN_BONUS),
        ("j6_road_skeptic_max_len", flat_leaf._JR_J6_ROAD_SKEPTIC_MAX_LEN),
        ("j6_road_claim_penalty", flat_leaf._JR_J6_ROAD_CLAIM_PENALTY),
        ("j6_road_anchor_allowance", flat_leaf._JR_J6_ROAD_ANCHOR_ALLOWANCE),
        ("j8_pivotal_swing", flat_leaf._JR_J8_PIVOTAL_SWING),
        ("j8_overcommit_bonus", flat_leaf._JR_J8_OVERCOMMIT_BONUS),
        ("j8_value_norm", flat_leaf._JR_J8_VALUE_NORM),
        ("j8_max_city_meeples", flat_leaf._JR_J8_MAX_CITY_MEEPLES),
        ("j8_max_farm_meeples", flat_leaf._JR_J8_MAX_FARM_MEEPLES),
    ]
    for name, frozen in pairs:
        assert getattr(p, name) == frozen, f"{name}: bot {getattr(p, name)} vs leaf {frozen}"


def test_k0_matches_a_real_game_start():
    """`_JR_K0` stands in for the bot's per-game latched `Clock.k0`."""
    b = Game(enable_legal_moves_cache=False).get_init_board()
    assert flat_leaf._k_remaining(b.state) == int(flat_leaf._JR_K0)


# --- 3. J1 ------------------------------------------------------------------ #
def test_j1_fires_on_large_open_city_share():
    # 6 tiles, 3 open, I hold it alone; k=72 -> late_frac 0 -> bonus 3.0
    st, d = _mk(cities={7: (False, 3, 6)}, meeples=[(0, "city", 7, N)])
    assert _T(st, d, flat_leaf.JR_J1) == pytest.approx(3.0)
    # late in the game the premium grows: k=36 -> late_frac 0.5 -> 3.0 * 1.5
    st, d = _mk(cities={7: (False, 3, 6)}, meeples=[(0, "city", 7, N)], k=36)
    assert _T(st, d, flat_leaf.JR_J1) == pytest.approx(4.5)


def test_j1_the_join_pays_exactly_the_bonus():
    """THE load-bearing transition. Opponent alone in his big open city -> I sneak in
    to a TIE. The differential must RISE by exactly the bonus. (With the bot's
    `cnt[other] >= 1` predicate retained this delta would be 0.0 — DESIGN.md §3.)"""
    before, d0 = _mk(cities={7: (False, 3, 6)}, meeples=[(1, "city", 7, N)])
    after, d1 = _mk(cities={7: (False, 3, 6)},
                    meeples=[(1, "city", 7, N), (0, "city", 7, N)])
    t0 = _T(before, d0, flat_leaf.JR_J1)
    t1 = _T(after, d1, flat_leaf.JR_J1)
    assert t0 == pytest.approx(-3.0)
    assert t1 == pytest.approx(0.0)
    assert t1 - t0 == pytest.approx(3.0)


def test_j1_must_not_fire():
    for cities in ({7: (False, 3, 4)},        # too small (4 < 5 tiles)
                   {7: (False, 1, 6)},        # only one open edge
                   {7: (True, 3, 6)},         # finished
                   ):
        st, d = _mk(cities=cities, meeples=[(0, "city", 7, N)])
        assert _T(st, d, flat_leaf.JR_J1) == 0.0
    # minority holder gets no share
    st, d = _mk(cities={7: (False, 3, 6)},
                meeples=[(1, "city", 7, BIG), (0, "city", 7, N)])
    assert _T(st, d, flat_leaf.JR_J1) == pytest.approx(-3.0)   # HIS share, not mine


def test_j4_urgency_scales_j1():
    """Opponent out of meeples -> urgency floor 0.35 on MY contest terms."""
    st, d = _mk(cities={7: (False, 3, 6)}, meeples=[(0, "city", 7, N)], reserves=(4, 0))
    assert _T(st, d, flat_leaf.JR_J1) == pytest.approx(3.0 * 0.35)
    st, d = _mk(cities={7: (False, 3, 6)}, meeples=[(0, "city", 7, N)], reserves=(4, 2))
    assert _T(st, d, flat_leaf.JR_J1) == pytest.approx(3.0 * (0.35 + 0.65 * 0.5))


# --- 3. J2 ------------------------------------------------------------------ #
def test_j2_realized_steal_credits_the_unfinished_potential():
    # k=30 (<= 36, so late-game city counting is on); field adjoins city 9, which is
    # unfinished with 2 open cells (closable) -> potential 3.0. One finished adjacent
    # city too, so value = 3 + 3 = 6 >= the 3.0 bar.
    st, d = _mk(cities={9: (False, 2, 4)}, farms={5: (1, (9,))},
                meeples=[(0, "farm", 5, FARMER)], k=30)
    assert _T(st, d, flat_leaf.JR_J2) == pytest.approx(3.0)
    # ... and it is OFF early (k > j2_city_count_from_k = 36): potential 0 and the
    # field's remaining value (3, from the finished city) still clears the bar, so the
    # surrender charge does not fire either.
    st, d = _mk(cities={9: (False, 2, 4)}, farms={5: (1, (9,))},
                meeples=[(0, "farm", 5, FARMER)], k=50)
    assert _T(st, d, flat_leaf.JR_J2) == pytest.approx(0.0)


def test_j2_the_steal_pays_the_potential():
    """Same transition contract as J1: he alone on the valuable field -> I tie it."""
    before, d0 = _mk(cities={9: (False, 2, 4)}, farms={5: (1, (9,))},
                     meeples=[(1, "farm", 5, FARMER)], k=30)
    after, d1 = _mk(cities={9: (False, 2, 4)}, farms={5: (1, (9,))},
                    meeples=[(1, "farm", 5, FARMER), (0, "farm", 5, FARMER)], k=30)
    t0 = _T(before, d0, flat_leaf.JR_J2)
    t1 = _T(after, d1, flat_leaf.JR_J2)
    assert t0 == pytest.approx(-3.0)
    assert t1 == pytest.approx(0.0)


def test_j2_surrenders_low_value_fields():
    # no adjacent cities at all -> value 0 < 3.0 -> charged 2.0 per weighted meeple
    st, d = _mk(farms={5: (0, ())}, meeples=[(0, "farm", 5, FARMER)], k=30)
    assert _T(st, d, flat_leaf.JR_J2) == pytest.approx(-2.0)
    st, d = _mk(farms={5: (0, ())}, meeples=[(1, "farm", 5, FARMER)], k=30)
    assert _T(st, d, flat_leaf.JR_J2) == pytest.approx(2.0)


def test_j2_ignores_unclosable_adjacent_cities():
    # city 9 is unfinished but 5 cells from closing (> j2_city_close_open_max = 2)
    st, d = _mk(cities={9: (False, 5, 4)}, farms={5: (1, (9,))},
                meeples=[(0, "farm", 5, FARMER)], k=30)
    assert _T(st, d, flat_leaf.JR_J2) == pytest.approx(0.0)


# --- 3. J5 + J13 ------------------------------------------------------------ #
def test_j5_signs_unclaimed_value_by_the_reserve_edge():
    """An unclaimed 9-tile city (value 9, floor 4 -> 5 points of excess). With MORE
    meeples than him it is an ASSET (J13: build it up, I'll claim it); with FEWER it
    is a LIABILITY (J5: don't feed it)."""
    kw = dict(cities={7: (False, 3, 9)}, farms=None)
    st, d = _mk(**kw, meeples=[], reserves=(4, 2))     # edge +1 (clipped)
    assert _T(st, d, flat_leaf.JR_J5) == pytest.approx(0.5 * 5.0 * 1.0)
    st, d = _mk(**kw, meeples=[], reserves=(2, 4))     # edge -1
    assert _T(st, d, flat_leaf.JR_J5) == pytest.approx(-0.5 * 5.0)
    st, d = _mk(**kw, meeples=[], reserves=(3, 3))     # equal reserves -> silent
    assert _T(st, d, flat_leaf.JR_J5) == 0.0
    st, d = _mk(**kw, meeples=[], reserves=(4, 3))     # edge +0.5, NOT clipped
    assert _T(st, d, flat_leaf.JR_J5) == pytest.approx(0.5 * 5.0 * 0.5)


def test_j5_ignores_claimed_and_sub_floor_features():
    # the same city, but CLAIMED -> not unclaimed value any more
    st, d = _mk(cities={7: (False, 3, 9)}, meeples=[(1, "city", 7, N)], reserves=(4, 0))
    assert _T(st, d, flat_leaf.JR_J5) == 0.0
    # a 4-tile city is exactly AT the floor -> no excess
    st, d = _mk(cities={7: (False, 3, 4)}, meeples=[], reserves=(4, 0))
    assert _T(st, d, flat_leaf.JR_J5) == 0.0


def test_j5_counts_roads_and_cloisters():
    st, d = _mk(roads={3: (False, 7)}, meeples=[], reserves=(4, 2))
    assert _T(st, d, flat_leaf.JR_J5) == pytest.approx(0.5 * (7.0 - 4.0))
    # an unclaimed cloister with 1 + 6 = 7 tiles in its 3x3 -> excess 3
    st, d = _mk(meeples=[], reserves=(4, 2), cloister_blocks=[(20, 6)])
    assert _T(st, d, flat_leaf.JR_J5) == pytest.approx(0.5 * 3.0)


def test_j5_finished_unclaimed_city_pays_double():
    st, d = _mk(cities={7: (True, 0, 5)}, meeples=[], reserves=(4, 2))
    assert _T(st, d, flat_leaf.JR_J5) == pytest.approx(0.5 * (2 * 5.0 - 4.0))


# --- 3. J6 ------------------------------------------------------------------ #
def test_j6_anchor_bonus_for_a_city_and_a_road():
    st, d = _mk(cities={7: (False, 3, 3)}, meeples=[(0, "city", 7, N)])
    assert _T(st, d, flat_leaf.JR_J6) == pytest.approx(2.0)
    st, d = _mk(cities={7: (False, 3, 3)}, roads={3: (False, 2)},
                meeples=[(0, "city", 7, N), (0, "road", 3, N)])
    # city anchor + road anchor = 4.0; the road is length 2 <= skeptic max 3 and solo,
    # so it is also the ONE allowed short solo road -> no claim penalty.
    assert _T(st, d, flat_leaf.JR_J6) == pytest.approx(4.0)


def test_j6_road_skepticism_charges_the_second_short_solo_road():
    st, d = _mk(roads={3: (False, 2), 4: (False, 2)},
                meeples=[(0, "road", 3, N), (0, "road", 4, N)])
    # 2 anchors' worth? no — only ONE road anchor bonus (2.0); two short solo roads,
    # one allowed, so 1 excess x 1.5 charged.
    assert _T(st, d, flat_leaf.JR_J6) == pytest.approx(2.0 - 1.5)


def test_j6_the_road_join_pays():
    before, d0 = _mk(roads={3: (False, 5)}, meeples=[(1, "road", 3, N)])
    after, d1 = _mk(roads={3: (False, 5)},
                    meeples=[(1, "road", 3, N), (0, "road", 3, N)])
    # before: he owns a length-5 road -> his anchor (2.0) + his join credit (2.0)
    assert _T(before, d0, flat_leaf.JR_J6) == pytest.approx(-4.0)
    # after: tied -> neither has a strict majority (no anchor either side), both hold a
    # share of the long road -> the join credits cancel; net 0.
    assert _T(after, d1, flat_leaf.JR_J6) == pytest.approx(0.0)


def test_j6_road_join_needs_length():
    st, d = _mk(roads={3: (False, 3)}, meeples=[(0, "road", 3, N)])
    # length 3 < j6_road_join_min_len 4 -> no join credit; anchor only (length >= 2)
    assert _T(st, d, flat_leaf.JR_J6) == pytest.approx(2.0)


# --- 3. J8 ------------------------------------------------------------------ #
def test_j8_pays_a_two_meeple_lead_on_a_pivotal_city():
    # 8-tile unfinished open city, I hold 2 meeples and he holds 0: swing 16 >= 12 and
    # >= |margin| 0 -> 3.0 * min(1, 8/10)
    st, d = _mk(cities={7: (False, 2, 8)},
                meeples=[(0, "city", 7, N), (0, "city", 7, N)])
    assert _T(st, d, flat_leaf.JR_J8) == pytest.approx(3.0 * 0.8)
    # a BIG meeple alone is also a weight-2 lead
    st, d = _mk(cities={7: (False, 2, 8)}, meeples=[(0, "city", 7, BIG)])
    assert _T(st, d, flat_leaf.JR_J8) == pytest.approx(3.0 * 0.8)


def test_j8_must_not_fire():
    # not pivotal enough (swing 2*5 = 10 < 12)
    st, d = _mk(cities={7: (False, 2, 5)},
                meeples=[(0, "city", 7, N), (0, "city", 7, N)])
    assert _T(st, d, flat_leaf.JR_J8) == 0.0
    # pivotal, but the margin already dwarfs it (|base| 20 > swing 16)
    st, d = _mk(cities={7: (False, 2, 8)},
                meeples=[(0, "city", 7, N), (0, "city", 7, N)])
    assert _T(st, d, flat_leaf.JR_J8, base=20.0) == 0.0
    # pivotal, but only a ONE-meeple lead (not an overcommit)
    st, d = _mk(cities={7: (False, 2, 8)}, meeples=[(0, "city", 7, N)])
    assert _T(st, d, flat_leaf.JR_J8) == 0.0
    # pivotal + 3 meeples: past j8_max_city_meeples = 2
    st, d = _mk(cities={7: (False, 2, 8)},
                meeples=[(0, "city", 7, N), (0, "city", 7, N), (0, "city", 7, N)])
    assert _T(st, d, flat_leaf.JR_J8) == 0.0
    # pivotal but he can no longer get in (open_n == 0)
    st, d = _mk(cities={7: (False, 0, 8)},
                meeples=[(0, "city", 7, N), (0, "city", 7, N)])
    assert _T(st, d, flat_leaf.JR_J8) == 0.0


def test_j8_farm_branch_allows_three_meeples():
    # field with 4 finished adjacent cities -> value 12, swing 24 >= 12
    st, d = _mk(farms={5: (4, ())},
                meeples=[(0, "farm", 5, FARMER)] * 3, k=30)
    assert _T(st, d, flat_leaf.JR_J8) == pytest.approx(3.0 * 1.0)
    st, d = _mk(farms={5: (4, ())},
                meeples=[(0, "farm", 5, FARMER)] * 4, k=30)
    assert _T(st, d, flat_leaf.JR_J8) == 0.0


# --- 4. antisymmetry + composition ------------------------------------------ #
def test_antisymmetry_on_the_corpus(states):
    for st in states:
        d = flat_leaf.decompose(st)
        base = float(flat_leaf.flat_base_score(st, 0, d))
        t0 = flat_leaf.flat_jrules_term(st, 0, d, JR_ONE, base)
        t1 = flat_leaf.flat_jrules_term(st, 1, d, JR_ONE, -base)
        assert t0 == -t1


def test_every_rule_fires_somewhere_on_the_corpus(states):
    """A rule that can never fire on real boards is a silent no-op, and a null on a
    no-op is not a measurement (the J8-exemption failure mode, J8EX_INERT_FINDING).

    ⚠️ MEASURED FIRING RATES on this 208-state random-play corpus (2026-08-13):
    J6 98%, J2 83%, J1 23%, J5 16%, **J8 3%**. J8 is nearly inert even as a score
    term — its predicate wants a >=2-meeple lead on a feature whose swing both clears
    12 points AND exceeds the current margin, which is rare. DESIGN.md §6 carries this
    forward: a null on the full bundle must NOT be read as a null on J8."""
    for mask, name in ((flat_leaf.JR_J1, "J1"), (flat_leaf.JR_J2, "J2"),
                       (flat_leaf.JR_J5, "J5"), (flat_leaf.JR_J6, "J6"),
                       (flat_leaf.JR_J8, "J8")):
        fired = False
        for st in states:
            d = flat_leaf.decompose(st)
            base = float(flat_leaf.flat_base_score(st, 0, d))
            if flat_leaf.flat_jrules_term(st, 0, d, _cfg(mask), base) != 0.0:
                fired = True
                break
        assert fired, f"{name} never fired on the random-play corpus"


def test_mask_composes(states):
    for st in states[:8]:
        d = flat_leaf.decompose(st)
        base = float(flat_leaf.flat_base_score(st, 0, d))
        parts = sum(flat_leaf.flat_jrules_term(st, 0, d, _cfg(m), base)
                    for m in (1, 2, 4, 8, 16))
        assert flat_leaf.flat_jrules_term(st, 0, d, JR_ONE, base) == pytest.approx(parts)


def test_leaf_moves_by_exactly_plus_dose_times_term(states):
    """The bundle ADJUSTS the leaf and is ADDED (not subtracted — it is a bonus
    potential, unlike denial/open-city)."""
    for st in states:
        for p in (0, 1):
            d = flat_leaf.decompose(st)
            base = flat_leaf.flat_base_score(st, p, d)
            ref = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            for cfg in (JR_HALF, JR_ONE):
                t = flat_leaf.flat_jrules_term(st, p, d, cfg, base)
                got = flat_leaf.flat_virtual_score_v2_float(st, p, cfg)
                assert got == pytest.approx(ref + cfg.jrules_dose * t, abs=1e-9)


# --- 5. the cy fast path is refused ----------------------------------------- #
def test_cy_fast_path_refused_for_jrules(states, monkeypatch):
    """A SET dose must leave the cy fast path — a cy build has no J-rules and would
    silently serve the champion leaf to a J-rules run."""
    _cy()
    monkeypatch.setattr(flat_leaf, "USE_CY_LEAF", True)
    calls = []
    real = flat_leaf._CY_FLAT_V2_FLOAT

    def spy(*a, **k):
        calls.append(1)
        return real(*a, **k)

    if real:
        monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2_FLOAT", spy)
    st = states[0]
    flat_leaf.flat_virtual_score_v2_float(st, 0, JR_ONE)
    assert not calls, "the cy leaf served a jrules_dose config"
    assert flat_leaf._jrules_off(CHAMP) is True
    assert flat_leaf._jrules_off(JR_ONE) is False


def test_cy_does_not_advertise_jrules_support():
    assert not getattr(_cy(), "SUPPORTS_JRULES", False)


# --- 6. the object path fails loud ------------------------------------------- #
@pytest.mark.parametrize("cfg", [JR_HALF, JR_ONE])
def test_object_path_fails_loud(states, cfg, monkeypatch):
    monkeypatch.setattr(flat_leaf, "USE_FLAT_LEAF", False)
    with pytest.raises(NotImplementedError, match="jrules_dose"):
        virtual_score_v2(states[0], 0, cfg)


# --- the --cand-leaf-json severability path ---------------------------------- #
def test_cand_leaf_json_round_trip():
    import sys
    from pathlib import Path

    p = str(Path(__file__).resolve().parents[1] / "scripts" / "classical_search")
    if p not in sys.path:
        sys.path.insert(0, p)
    from c5_leaf_override import _leaf_dict, _load_cand_leaf_cfg

    cfg = _load_cand_leaf_cfg('{"jrules_dose": 1.0, "jrules_mask": 31}')
    assert cfg.jrules_dose == 1.0 and cfg.jrules_mask == 31
    # default-off knobs are dropped from the hash dialect...
    assert "jrules_dose" not in _leaf_dict(CHAMP)
    # ...and present once set.
    assert _leaf_dict(JR_ONE)["jrules_dose"] == 1.0
    with pytest.raises(Exception):
        _load_cand_leaf_cfg('{"jrules_doze": 1.0}')      # typo must not run silently


# --- 7. rust parity + config forwarding -------------------------------------- #
def _carc_rs():
    return pytest.importorskip("carc_rs")


def test_leaf_config_rs_conditional_kwargs():
    """Default-off configs must not forward the kwargs at all (so a stale carc_rs
    build keeps serving the champion); a SET dose must forward them, and against a
    stale build that raises TypeError — fail-closed, never a silently-intact leaf."""
    _carc_rs()
    from carcassonne_ai.rust_agent import leaf_config_rs

    leaf_config_rs(CHAMP)          # must not raise on ANY build
    try:
        leaf_config_rs(JR_ONE)
    except TypeError as e:
        pytest.skip(f"loaded carc_rs predates the jrules term (fail-closed, correct): {e}")


def test_rust_parity_spot_check(states):
    carc_rs = _carc_rs()
    from carcassonne_ai.rust_agent import leaf_config_rs

    try:
        rs_cfg = leaf_config_rs(JR_ONE)
    except TypeError as e:
        pytest.skip(f"loaded carc_rs predates the jrules term: {e}")
    mirror_leaf = getattr(carc_rs, "leaf_value_float_py", None) or getattr(
        carc_rs, "leaf_value_float", None)
    if mirror_leaf is None:
        pytest.skip("no direct carc_rs leaf entry point exposed in this build")
    n = 0
    for st in states[:10]:
        for p in (0, 1):
            py = flat_leaf.flat_virtual_score_v2_float(st, p, JR_ONE)
            rs = mirror_leaf(st, p, rs_cfg)
            assert float(rs).hex() == py.hex()
            n += 1
    assert n


# --- 10. full-game smoke ----------------------------------------------------- #
@pytest.mark.parametrize("seed", [11, 12])
def test_full_game_smoke_greedy_on_the_modified_leaf(seed):
    """A whole legal game to termination with the modified leaf driving every move —
    the cheap proof that a J-rules leaf never crashes mid-game and never proposes an
    illegal action. (The strength question is a deck-paired eval, not a test.)"""
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    rng = random.Random(seed)
    plies = 0
    while g.get_game_ended(b, 0) == 0.0:
        legal = [int(i) for i in np.flatnonzero(g.get_valid_moves(b))]
        assert legal, "no legal moves before the game ended"
        mover = int(b.state.current_player)
        best, best_v = None, None
        cand = legal if len(legal) <= 24 else rng.sample(legal, 24)
        for a in cand:
            nb, _ = g.get_next_state(b, a)
            v = flat_leaf.flat_virtual_score_v2_float(nb.state, mover, JR_ONE)
            if best_v is None or v > best_v:
                best, best_v = a, v
        b, _ = g.get_next_state(b, best)
        plies += 1
        assert plies < 400, "game did not terminate"
    assert plies > 50
    assert sum(b.state.scores) > 0
