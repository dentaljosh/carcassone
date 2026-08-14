"""TILE-TIE TIE-BREAK — a bounded micro-term that discriminates only where the
leaf is (near-)silent (`LeafConfig.tiletie_dose` / `tiletie_w_city` /
`tiletie_w_road` / `tiletie_w_perim` / `tiletie_w_lib` / `tiletie_norm`).

Motivation: measurement/tiletie_pricing_20260812 (pooled n=733, branch 4) — the
leaf exactly ties the top TILE placement on ~66% of champion tile plies, the
tied sets carry real value spread (S1a z +4.26), and the champion's 11008-sim
search leaves +0.252 pts/tied ply of it unrecovered (z +3.43). CL-065 forbids a
learned tie-breaker, so T is hand-crafted geometry (closure-cell
constrainedness + board-frontier shape), bounded |T| < 1 through the monotone
map t/(1+|t|), and the leaf ADDS `tiletie_dose * T`. Spec:
measurement/tiletie_term_20260814/DESIGN.md.

Contracts (the denial / open-city / jrules test-file pattern):
  1. DEFAULT OFF IS INERT. Champion fingerprints recompute unchanged; a
     default-off cfg is bit-identical even with MOVED weights and norm (the
     dose gates the whole term).
  2. The wallin feature fires only on QUALIFYING components: strict weighted
     majority (BIG=2, tie => nobody), unfinished, closable; the per-open-cell
     contribution is occ4(e) - 1.
  3. SIGN + SYMMETRY. Default weights (city 1, road 1, perim 0, lib 0) make T
     ANTISYMMETRIC; a nonzero perim/lib weight is a DISCLOSED antisymmetry wart
     (the denial pattern). |T| < 1 always; ORDERING is invariant to
     `tiletie_norm` (the bounded map is strictly monotone).
  4. The leaf moves by exactly `+dose * T` and by nothing else.
  5. ENV/CONFIG PLUMBING round-trips (CARCASSONNE_TILETIE_* -> _config_from_env).
  6. THE CY FAST PATH IS REFUSED (no cy implementation).
  7. THE OBJECT PATH FAILS LOUD.
  8. `rust_agent.leaf_config_rs` forwards conditional kwargs — with NO rust
     mirror built yet, ANY current carc_rs raises TypeError on a nonzero dose
     (fail-closed loud), while default-off configs are served unchanged.
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
from carcassonne_ai.virtual_score_v2 import (DEFAULT_CONFIG, _config_from_env,
                                             virtual_score_v2)

N = MeepleType.NORMAL
B = MeepleType.BIG

CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
CHAMP = dc.replace(DEFAULT_CONFIG, meeple_k=2.0, bonus_cap=8.0, opp_bonus_cap=8.0,
                   closure_p={1: 0.5, 2: 0.2, 3: 0.05}, v29_meeple_curve=CURVE125)
T_MICRO = dc.replace(CHAMP, tiletie_dose=0.02)
T_BIG = dc.replace(CHAMP, tiletie_dose=1.0)
T_PERIM = dc.replace(CHAMP, tiletie_dose=0.02, tiletie_w_city=0.0,
                     tiletie_w_road=0.0, tiletie_w_perim=1.0)
T_LIB = dc.replace(CHAMP, tiletie_dose=0.02, tiletie_w_city=0.0,
                   tiletie_w_road=0.0, tiletie_w_lib=1.0)
# dose 0.0 with MOVED weights and norm — must be bit-identical to CHAMP.
T_IDENTITY = dc.replace(CHAMP, tiletie_dose=0.0, tiletie_w_city=-3.0,
                        tiletie_w_road=0.5, tiletie_w_perim=9.0,
                        tiletie_w_lib=-2.0, tiletie_norm=1.0)


def _states(n_seeds=5, max_plies=140, start=20, every=7, seed_base=9100):
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
# fixture builder: a minimal (state, decomp) pair for the wallin predicate.    #
# One city component `root`; its positions/open cells are painted onto a       #
# 12x12 board so occ4 is controlled exactly.                                   #
# --------------------------------------------------------------------------- #
class _CityTile:
    inn = False
    shield = False

    def get_type(self, side):
        return TerrainType.CITY


def _mk(occupied, positions, finished, open_n, meeples):
    """occupied: [(r, c)] cells that hold a tile.  positions: [(r, c, Side)]
    component city sides.  meeples: [(player, meeple_type)] all mapped onto the
    FIRST position of the component."""
    board = [[None] * 12 for _ in range(12)]
    for (r, c) in occupied:
        board[r][c] = _CityTile()
    root = 7
    placed = [[], []]
    r0, c0, s0 = positions[0]
    for (pl, mt) in meeples:
        placed[pl].append(SimpleNamespace(
            coordinate_with_side=SimpleNamespace(
                coordinate=SimpleNamespace(row=r0, column=c0), side=s0),
            meeple_type=mt))
    st = SimpleNamespace(board=board, placed_meeples=placed, open_positions=set())
    d = SimpleNamespace(
        city_side_root={(r, c, s): root for (r, c, s) in positions},
        city_root_positions={root: frozenset(positions)},
        city_root_finished={root: finished},
        city_root_open_n={root: open_n},
        road_side_root={}, road_root_positions={},
        road_root_finished={}, road_root_open_n={})
    return st, d


def _wall(st, d):
    return flat_leaf._tiletie_wallin(
        st, d, d.city_side_root, d.city_root_positions,
        d.city_root_finished, d.city_root_open_n, TerrainType.CITY)


# --- 1. default off is inert -------------------------------------------------- #
def test_champion_leaf_hashes_unchanged():
    from carcassonne_ai.alphabeta_agent import _leaf_hash

    assert _leaf_hash(CHAMP) == "a36d2e15a3b3d71d"
    assert _leaf_hash(T_MICRO) != "a36d2e15a3b3d71d"     # a SET dose IS a new leaf
    assert _leaf_hash(T_MICRO) != _leaf_hash(T_PERIM)    # the weights are part of the leaf


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
    """dose 0.0 == champion bit-for-bit, even with MOVED weights and norm (the
    dose gates the whole term), on both the int and pre-round float paths."""
    for st in states:
        for p in (0, 1):
            ref_f = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            assert flat_leaf.flat_virtual_score_v2_float(st, p, T_IDENTITY).hex() == ref_f.hex()
            assert (flat_leaf.flat_virtual_score_v2(st, p, T_IDENTITY)
                    == flat_leaf.flat_virtual_score_v2(st, p, CHAMP))


# --- 2. the wallin predicate matrix ------------------------------------------- #
def test_wallin_lone_open_cell_contributes_zero():
    # city tile at (5,5), open side RIGHT -> open cell (5,6); occ4 = 1 (the city
    # tile itself) -> contribution occ4 - 1 = 0.
    st, d = _mk([(5, 5)], [(5, 5, Side.RIGHT)], False, 1, [(0, N)])
    assert _wall(st, d) == [0.0, 0.0]


def test_wallin_counts_extra_walls_around_open_cell():
    # add occupied neighbours around the open cell (5,6): (4,6) and (6,6)
    # -> occ4 = 3 -> contribution 2, charged to the OWNER (p0).
    st, d = _mk([(5, 5), (4, 6), (6, 6)], [(5, 5, Side.RIGHT)], False, 1, [(0, N)])
    assert _wall(st, d) == [2.0, 0.0]
    # and T (mover POV) is NEGATIVE for the owner, POSITIVE for the opponent
    t0 = flat_leaf.flat_tiletie_term(st, 0, d, T_MICRO)
    t1 = flat_leaf.flat_tiletie_term(st, 1, d, T_MICRO)
    assert t0 < 0.0 < t1 and t0 == -t1        # antisymmetric at default weights


def test_wallin_gates():
    occ = [(5, 5), (4, 6), (6, 6)]
    pos = [(5, 5, Side.RIGHT)]
    st, d = _mk(occ, pos, True, 1, [(0, N)])          # finished -> never
    assert _wall(st, d) == [0.0, 0.0]
    st, d = _mk(occ, pos, False, 0, [(0, N)])         # unclosable -> never
    assert _wall(st, d) == [0.0, 0.0]
    st, d = _mk(occ, pos, False, 1, [])               # unmeepled -> never
    assert _wall(st, d) == [0.0, 0.0]
    st, d = _mk(occ, pos, False, 1, [(0, N), (1, N)])  # tied -> nobody
    assert _wall(st, d) == [0.0, 0.0]
    st, d = _mk(occ, pos, False, 1, [(0, N), (1, B)])  # BIG outweighs one NORMAL
    assert _wall(st, d) == [0.0, 2.0]


def test_wallin_dedupes_open_cells():
    # two sides of the SAME component crossing into the SAME empty cell must
    # count that cell once: (5,5,RIGHT) and (4,6,BOTTOM) both border (5,6).
    st, d = _mk([(5, 5), (4, 6), (6, 6)],
                [(5, 5, Side.RIGHT), (4, 6, Side.BOTTOM)], False, 1, [(0, N)])
    assert _wall(st, d) == [2.0, 0.0]                  # occ4(5,6)=3 -> 2, once


# --- 3. boundedness + norm-invariance of ordering ----------------------------- #
def test_bounded_and_ordering_invariant_to_norm(states):
    for st in states[:10]:
        d = flat_leaf.decompose(st)
        for cfg in (T_MICRO, T_PERIM, T_LIB):
            assert abs(flat_leaf.flat_tiletie_term(st, 0, d, cfg)) < 1.0
    # ordering across states is preserved under a norm change
    prev = None
    for norm_a, norm_b in ((8.0, 2.0), (8.0, 40.0)):
        va = [flat_leaf.flat_tiletie_term(s, 0, flat_leaf.decompose(s),
                                          dc.replace(T_PERIM, tiletie_norm=norm_a))
              for s in states[:12]]
        vb = [flat_leaf.flat_tiletie_term(s, 0, flat_leaf.decompose(s),
                                          dc.replace(T_PERIM, tiletie_norm=norm_b))
              for s in states[:12]]
        assert np.array_equal(np.argsort(va, kind="stable"),
                              np.argsort(vb, kind="stable"))
        prev = (va, vb)
    assert prev is not None


# --- 4. the leaf moves by exactly +dose * T ----------------------------------- #
def test_leaf_moves_by_exactly_dose_times_term(states):
    fired = 0
    for st in states:
        d = flat_leaf.decompose(st)
        for p in (0, 1):
            ref = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            for cfg in (T_MICRO, T_BIG, T_PERIM, T_LIB):
                t = flat_leaf.flat_tiletie_term(st, p, d, cfg)
                got = flat_leaf.flat_virtual_score_v2_float(st, p, cfg)
                assert got == pytest.approx(ref + cfg.tiletie_dose * t, abs=1e-9)
                if t:
                    fired += 1
    assert fired > 0, "tiletie term never fired on the random-state corpus"


# --- 5. env plumbing ---------------------------------------------------------- #
def test_env_round_trip(monkeypatch):
    off = _config_from_env()
    assert (off.tiletie_dose, off.tiletie_w_city, off.tiletie_w_road,
            off.tiletie_w_perim, off.tiletie_w_lib, off.tiletie_norm) == (
        0.0, 1.0, 1.0, 0.0, 0.0, 8.0)
    monkeypatch.setenv("CARCASSONNE_TILETIE_DOSE", "0.02")
    monkeypatch.setenv("CARCASSONNE_TILETIE_W_CITY", "0.0")
    monkeypatch.setenv("CARCASSONNE_TILETIE_W_PERIM", "-1.5")
    monkeypatch.setenv("CARCASSONNE_TILETIE_NORM", "16.0")
    on = _config_from_env()
    assert (on.tiletie_dose, on.tiletie_w_city, on.tiletie_w_road,
            on.tiletie_w_perim, on.tiletie_w_lib, on.tiletie_norm) == (
        0.02, 0.0, 1.0, -1.5, 0.0, 16.0)


# --- 6. the cy fast path is refused ------------------------------------------- #
def test_cy_fast_path_refused_for_tiletie(states, monkeypatch):
    assert flat_leaf._tiletie_off(CHAMP) is True
    assert flat_leaf._tiletie_off(T_IDENTITY) is True   # dose 0.0 == off, cy OK
    for cfg in (T_MICRO, T_BIG, T_PERIM, T_LIB):
        assert flat_leaf._tiletie_off(cfg) is False

    monkeypatch.setattr(flat_leaf, "USE_CY_LEAF", True)

    def _boom(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("tiletie cfg reached the Cython leaf")

    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2", _boom)
    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2_FLOAT", _boom)
    for st in states[:6]:
        for cfg in (T_MICRO, T_PERIM):
            flat_leaf.flat_virtual_score_v2(st, 0, cfg)
            flat_leaf.flat_virtual_score_v2_float(st, 0, cfg)


# --- 7. the object path fails loud -------------------------------------------- #
@pytest.mark.parametrize("cfg", [T_MICRO, T_PERIM])
def test_object_path_fails_loud(states, cfg, monkeypatch):
    monkeypatch.setattr(flat_leaf, "USE_FLAT_LEAF", False)
    with pytest.raises(NotImplementedError, match="tiletie_dose"):
        virtual_score_v2(states[0], 0, cfg)


# --- 8. rust forwarding is fail-closed ---------------------------------------- #
def test_leaf_config_rs_conditional_kwargs():
    """Default-off configs must build on ANY carc_rs (no tiletie kwargs passed);
    a nonzero dose must raise TypeError until the rust mirror lands (there is
    deliberately NO rust implementation yet — fail-closed loud, never a
    silently tiebreak-blind leaf)."""
    carc_rs = pytest.importorskip("carc_rs")
    from carcassonne_ai.rust_agent import leaf_config_rs

    leaf_config_rs(CHAMP)               # default-off: must build on any wheel
    leaf_config_rs(T_IDENTITY)          # moved weights, dose 0.0: still no kwargs
    try:
        leaf_config_rs(T_MICRO)
    except TypeError:
        pass                            # stale/current wheel: fail-closed, correct
    else:
        # a future wheel that ACCEPTS the kwargs must also advertise the term —
        # reaching here before the rust mirror exists would be a silent no-op.
        assert hasattr(carc_rs, "LeafConfigRs")
        pytest.fail("carc_rs accepted tiletie kwargs — if the rust mirror has "
                    "landed, update this test + reconcile_leaf --configs tiletie")


# --- 9. the --cand-leaf-json severability path --------------------------------- #
def test_cand_leaf_json_round_trip_and_guards(capsys):
    """The candidate side is severable through `--cand-leaf-json` exactly like
    denial/open-city: named fields replace ONLY the candidate leaf, a set dose
    WARNS (incl. the no-rust-mirror fact), and a nonsensical norm is fatal."""
    import sys
    from pathlib import Path

    p = str(Path(__file__).resolve().parents[1] / "scripts" / "classical_search")
    if p not in sys.path:
        sys.path.insert(0, p)
    import c5_leaf_override as ovr

    cfg = ovr._load_cand_leaf_cfg(
        '{"tiletie_dose": 0.02, "tiletie_w_city": 1.0, "tiletie_w_road": 0.0,'
        ' "tiletie_w_perim": 0.0, "tiletie_w_lib": 0.0, "tiletie_norm": 8.0,'
        ' "v29_meeple_curve": [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]}')
    assert cfg.tiletie_dose == 0.02
    assert cfg.tiletie_w_road == 0.0
    assert tuple(cfg.v29_meeple_curve) == CURVE125
    # a SET dose is a different leaf than the champion (the wiring gate's check)
    assert ovr._leaf_hash(cfg) != ovr._leaf_hash(DEFAULT_CONFIG)
    # ... but a no-op dose-0.0 override hashes AS the champion (the fields are
    # excluded while at their defaults -> a no-op JSON cannot fake a new leaf)
    same = ovr._load_cand_leaf_cfg('{"tiletie_dose": 0.0}')
    assert ovr._leaf_hash(same) == ovr._leaf_hash(DEFAULT_CONFIG)
    # a set dose WARNS (incl. the no-rust-mirror fact) at the cy-path assert
    ovr._assert_cy_float_path(cfg)
    err = capsys.readouterr().err
    assert "tile-tie tie-break set" in err and "NO rust mirror" in err
    # a non-positive norm defines a different (broken) map -> fatal
    with pytest.raises(ValueError, match="tiletie_norm"):
        ovr._assert_cy_float_path(dc.replace(cfg, tiletie_norm=0.0))
