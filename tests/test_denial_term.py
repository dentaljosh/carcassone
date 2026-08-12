"""TARGETED DENIAL on near-complete large opponent cities
(`LeafConfig.denial_dose` / `denial_size_min` / `denial_open_max`).

BACKLOG 2026-05-16 item 3 / LEVER_INDEX "targeted denial" (the lit-review reframe
of the killed v3 blanket opp-cap): the leaf's capped opponent anticipation can
never express more than `opp_bonus_cap` points of fear, so the champion won't
spend a tile to block a large, near-complete opponent city. The denial term
subtracts `dose * (city_root_delta - size_min + 1)` for every OPPONENT-strict-
majority incomplete city with `0 < open_n <= open_max` and `delta >= size_min`,
UNCAPPED and on top of the existing anticipation, in `flat_leaf.flat_denial_term`
and the Rust `carc_core::leaf::denial_term`.

Contracts (the F7b test-file pattern):
  1. DEFAULT OFF IS INERT. The champion's leaf hashes recompute unchanged across
     the three additive fields, and a default-off cfg produces bit-identical leaf
     values (dose 0.0 gates the whole term — thresholds are inert while it is 0.0).
  2. The term FIRES ONLY ON QUALIFYING CITIES — the predicate matrix is pinned on
     hand-built fixtures: large+near-complete opponent city fires; large-but-wide-
     open doesn't; small+near-complete doesn't; OWN/tied/unmeepled never; finished
     or unclosable (open_n == 0) never; big meeples weigh 2.
  3. The term only ever LOWERS the evaluation from the evaluating player's POV,
     by exactly `dose * flat_denial_term(...)`.
  4. ENV/CONFIG PLUMBING round-trips (CARCASSONNE_DENIAL_* -> _config_from_env).
  5. THE CY FAST PATH IS REFUSED (no cy implementation, the F7b decision — the
     candidate cells run `--backend rust`); a stale `.so` can never serve an
     intact (denial-blind) leaf to a denial run.
  6. THE OBJECT PATH FAILS LOUD rather than silently scoring without denial.
  7. RUST == PYTHON bit-exactly with denial ON (spot check here; the full-corpus
     gate is `scripts/rustport/reconcile_leaf.py --configs denial`), and
     `rust_agent.leaf_config_rs` forwards the knobs as conditional kwargs — a
     stale carc_rs build keeps serving default-off configs but raises TypeError
     on a nonzero dose (fail-closed loud, never a silently-intact leaf).
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
D_HALF = dc.replace(CHAMP, denial_dose=0.5)
D_ONE = dc.replace(CHAMP, denial_dose=1.0)
D_LOOSE = dc.replace(CHAMP, denial_dose=2.0, denial_size_min=6.0, denial_open_max=3)
# dose 0.0 with MOVED thresholds — must be bit-identical to CHAMP everywhere.
D_IDENTITY = dc.replace(CHAMP, denial_dose=0.0, denial_size_min=4.0, denial_open_max=3)

cy = pytest.importorskip("carcassonne_ai.flat_leaf_cy")


def _states(n_seeds=6, max_plies=140, start=20, every=6, seed_base=8800):
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
# fixture builder for the predicate matrix: a minimal state+decomp pair with   #
# exactly the fields flat_denial_term reads.                                   #
# --------------------------------------------------------------------------- #
class _CityTile:
    def get_type(self, side):
        return TerrainType.CITY


def _mk(cities, meeples):
    """cities: {root: (finished, open_n, delta)}.
    meeples: [(player, root, meeple_type)] — each meeple gets its own cell (row =
    an increasing counter, col 0, side TOP) mapped onto its city root."""
    board = [[None] * 40 for _ in range(40)]
    placed = [[], []]
    side_root = {}
    for i, (pl, root, mt) in enumerate(meeples):
        r, c = i, 0
        board[r][c] = _CityTile()
        side_root[(r, c, Side.TOP)] = root
        placed[pl].append(SimpleNamespace(
            coordinate_with_side=SimpleNamespace(
                coordinate=SimpleNamespace(row=r, column=c), side=Side.TOP),
            meeple_type=mt))
    state = SimpleNamespace(board=board, placed_meeples=placed)
    decomp = flat_leaf.Decomp(
        city_side_root=side_root,
        city_root_positions={}, city_root_coords={},
        city_root_finished={k: v[0] for k, v in cities.items()},
        city_root_open_n={k: v[1] for k, v in cities.items()},
        city_root_delta={k: v[2] for k, v in cities.items()},
        road_side_root={}, road_root_positions={}, road_root_coords={},
        road_root_finished={}, road_root_open_n={},
        farm_pos0_root={}, farm_anypos_root={}, farm_root_keys={},
        farm_root_adj_city_roots={}, farm_root_finished_cities={})
    return state, decomp


N = MeepleType.NORMAL
BIG = MeepleType.BIG


# --- 1. default off is inert ------------------------------------------------ #
def test_defaults_are_off_and_env_buildable():
    assert DEFAULT_CONFIG.denial_dose == 0.0
    assert DEFAULT_CONFIG.denial_size_min == 8.0
    assert DEFAULT_CONFIG.denial_open_max == 2
    # env-buildable candidate knob (the v29_phase_beta pattern, NOT the F7b one):
    # CARCASSONNE_DENIAL_* defaults keep production DEFAULT_CONFIG unchanged.
    import inspect

    from carcassonne_ai import virtual_score_v2 as vs2
    src = inspect.getsource(vs2._config_from_env)
    assert "CARCASSONNE_DENIAL_DOSE" in src


def test_env_round_trip(monkeypatch):
    monkeypatch.setenv("CARCASSONNE_DENIAL_DOSE", "1.5")
    monkeypatch.setenv("CARCASSONNE_DENIAL_SIZE_MIN", "6")
    monkeypatch.setenv("CARCASSONNE_DENIAL_OPEN_MAX", "3")
    cfg = _config_from_env()
    assert cfg.denial_dose == 1.5
    assert cfg.denial_size_min == 6.0
    assert cfg.denial_open_max == 3
    monkeypatch.delenv("CARCASSONNE_DENIAL_DOSE")
    monkeypatch.delenv("CARCASSONNE_DENIAL_SIZE_MIN")
    monkeypatch.delenv("CARCASSONNE_DENIAL_OPEN_MAX")
    off = _config_from_env()
    assert (off.denial_dose, off.denial_size_min, off.denial_open_max) == (0.0, 8.0, 2)


def test_champion_leaf_hashes_unchanged():
    """The additive fields must not move the champion's fingerprints."""
    from carcassonne_ai.alphabeta_agent import _leaf_hash

    assert _leaf_hash(CHAMP) == "a36d2e15a3b3d71d"
    assert _leaf_hash(D_HALF) != "a36d2e15a3b3d71d"      # a SET dose IS a new leaf
    assert _leaf_hash(D_HALF) != _leaf_hash(D_ONE)
    # thresholds at NON-defaults shift the hash even at dose 0 (a different cfg),
    # which is fine — the identity contract below is about VALUES, not hashes.


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
    """dose 0.0 == champion bit-for-bit, even with MOVED thresholds (the dose
    gates the whole term), on both the int and pre-round float paths."""
    for st in states:
        for p in (0, 1):
            ref_f = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            assert flat_leaf.flat_virtual_score_v2_float(st, p, D_IDENTITY).hex() == ref_f.hex()
            assert (flat_leaf.flat_virtual_score_v2(st, p, D_IDENTITY)
                    == flat_leaf.flat_virtual_score_v2(st, p, CHAMP))


# --- 2. the predicate matrix (hand-built fixtures) --------------------------- #
def test_fires_on_large_near_complete_opponent_city():
    st, d = _mk({7: (False, 2, 12)}, [(1, 7, N)])   # opp knight, delta 12, 2 open
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == pytest.approx(12 - 8 + 1)
    # escalation: bigger city, bigger term
    st, d = _mk({7: (False, 1, 20)}, [(1, 7, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == pytest.approx(20 - 8 + 1)


def test_does_not_fire_wide_open():
    st, d = _mk({7: (False, 5, 12)}, [(1, 7, N)])   # large but 5 open cells
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0
    # boundary: open_n == open_max fires, open_max+1 doesn't
    st, d = _mk({7: (False, 2, 12)}, [(1, 7, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) > 0.0
    st, d = _mk({7: (False, 3, 12)}, [(1, 7, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0


def test_does_not_fire_small():
    st, d = _mk({7: (False, 1, 4)}, [(1, 7, N)])    # near-complete but small
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0
    # boundary: delta == size_min fires with weight exactly 1
    st, d = _mk({7: (False, 1, 8)}, [(1, 7, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == pytest.approx(1.0)


def test_never_fires_on_own_or_tied_city():
    # OWN city: fires only from the OPPONENT's POV, never the owner's.
    st, d = _mk({7: (False, 1, 12)}, [(0, 7, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0
    assert flat_leaf.flat_denial_term(st, 1, d, D_ONE) == pytest.approx(5.0)
    # TIED city never fires either way (both players majority-score it).
    st, d = _mk({7: (False, 1, 12)}, [(0, 7, N), (1, 7, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0
    assert flat_leaf.flat_denial_term(st, 1, d, D_ONE) == 0.0
    # unmeepled city never fires.
    st, d = _mk({7: (False, 1, 12)}, [])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0


def test_never_fires_finished_or_unclosable():
    st, d = _mk({7: (True, 0, 12)}, [(1, 7, N)])    # finished
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0
    st, d = _mk({7: (False, 0, 12)}, [(1, 7, N)])   # D16 unclosable board-edge city
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0


def test_meeple_weights_and_multiple_cities():
    # big meeple weighs 2: opp BIG vs my 1 normal -> strict majority -> fires;
    # opp BIG vs my 2 normals -> tied -> doesn't.
    st, d = _mk({7: (False, 1, 12)}, [(1, 7, BIG), (0, 7, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == pytest.approx(5.0)
    st, d = _mk({7: (False, 1, 12)}, [(1, 7, BIG), (0, 7, N), (0, 7, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0
    # two qualifying cities sum; a third non-qualifying one adds nothing.
    st, d = _mk({1: (False, 1, 10), 2: (False, 2, 9), 3: (False, 4, 30)},
                [(1, 1, N), (1, 2, N), (1, 3, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == pytest.approx((10 - 8 + 1) + (9 - 8 + 1))
    # the loose cell (size_min 6, open_max 3) picks up smaller/wider cities.
    st, d = _mk({1: (False, 3, 7)}, [(1, 1, N)])
    assert flat_leaf.flat_denial_term(st, 0, d, D_ONE) == 0.0
    assert flat_leaf.flat_denial_term(st, 0, d, D_LOOSE) == pytest.approx(7 - 6 + 1)


# --- 3. the term lowers the leaf by exactly dose * T ------------------------- #
def test_denial_only_lowers_and_by_dose_times_term(states):
    fired = 0
    for st in states:
        d = flat_leaf.decompose(st)
        for p in (0, 1):
            ref = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            for cfg in (D_HALF, D_ONE, D_LOOSE):
                t = flat_leaf.flat_denial_term(st, p, d, cfg)
                assert t >= 0.0
                got = flat_leaf.flat_virtual_score_v2_float(st, p, cfg)
                assert got <= ref + 1e-12
                assert got == pytest.approx(ref - cfg.denial_dose * t, abs=1e-9)
                if t:
                    fired += 1
    assert fired > 0, "denial never fired on the random-state corpus — inert fixture set"


# --- 5. the cy fast path is refused ------------------------------------------ #
def test_cy_fast_path_refused_for_denial(states, monkeypatch):
    assert flat_leaf._denial_off(CHAMP) is True
    assert flat_leaf._denial_off(D_IDENTITY) is True    # dose 0.0 == off, cy OK
    for cfg in (D_HALF, D_ONE, D_LOOSE):
        assert flat_leaf._denial_off(cfg) is False

    monkeypatch.setattr(flat_leaf, "USE_CY_LEAF", True)

    def _boom(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("denial cfg reached the Cython leaf")

    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2", _boom)
    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2_FLOAT", _boom)
    for st in states[:8]:
        for cfg in (D_HALF, D_ONE, D_LOOSE):
            flat_leaf.flat_virtual_score_v2(st, 0, cfg)
            flat_leaf.flat_virtual_score_v2_float(st, 0, cfg)


def test_cy_does_not_advertise_denial_support():
    """Documents the decision: the .pyx deliberately has no denial (F7b pattern)."""
    assert not hasattr(cy, "SUPPORTS_DENIAL")


# --- 6. the object path fails loud ------------------------------------------- #
@pytest.mark.parametrize("cfg", [D_HALF, D_ONE, D_LOOSE])
def test_object_path_fails_loud(states, cfg, monkeypatch):
    monkeypatch.setattr(flat_leaf, "USE_FLAT_LEAF", False)
    with pytest.raises(NotImplementedError, match="denial_dose"):
        virtual_score_v2(states[0], 0, cfg)


# --- 7. rust parity + config forwarding -------------------------------------- #
def _rs_supports_denial(carc_rs) -> bool:
    try:
        carc_rs.LeafConfigRs([(1, 0.5)], 8.0, 8.0, denial_dose=1.0,
                             denial_size_min=8.0, denial_open_max=2)
        return True
    except TypeError:
        return False


def test_leaf_config_rs_conditional_kwargs():
    """Default-off configs must build on ANY carc_rs (no denial kwargs passed);
    a nonzero dose must either forward (denial-capable build) or raise TypeError
    (stale build — fail-closed loud, never a silently-intact leaf)."""
    carc_rs = pytest.importorskip("carc_rs")
    from carcassonne_ai.rust_agent import leaf_config_rs

    leaf_config_rs(CHAMP)          # any build
    leaf_config_rs(D_IDENTITY)     # dose 0.0 -> no kwargs -> any build
    if _rs_supports_denial(carc_rs):
        r = repr(leaf_config_rs(D_LOOSE))
        assert "denial_dose: 2.0" in r, r
        assert "denial_size_min: 6.0" in r, r
        assert "denial_open_max: 3" in r, r
    else:
        with pytest.raises(TypeError):
            leaf_config_rs(D_ONE)


def test_rust_parity_spot_check():
    """py == rust bit-exactly with denial ON along one replayed game (the
    full-corpus version is `scripts/rustport/reconcile_leaf.py --configs denial`)."""
    carc_rs = pytest.importorskip("carc_rs")
    if not _rs_supports_denial(carc_rs):
        pytest.skip("carc_rs build predates the denial term (rebuild the wheel)")
    from carcassonne_ai.rust_agent import leaf_config_rs

    rcfgs = {name: leaf_config_rs(cfg)
             for name, cfg in (("champ", CHAMP), ("d1", D_ONE), ("loose", D_LOOSE))}
    cfgs = {"champ": CHAMP, "d1": D_ONE, "loose": D_LOOSE}

    # MirrorState.from_seed replays the same CPython-MT deck shuffle contract as
    # root_replay: `random.seed(seed)` BEFORE get_init_board on the python side.
    import random as _r
    g2 = Game(enable_legal_moves_cache=True)
    _r.seed(4242)
    b = g2.get_init_board()
    ms = carc_rs.MirrorState.from_seed("4242")
    rng = random.Random(1)
    checked = 0
    for ply in range(130):
        if g2.get_game_ended(b, 0) != 0.0:
            break
        if ply >= 16 and ply % 5 == 0:
            for name, cfg in cfgs.items():
                for p in (0, 1):
                    py_f = flat_leaf.flat_virtual_score_v2_float(b.state, p, cfg)
                    rs_f = ms.leaf_value_float(p, rcfgs[name])
                    assert py_f.hex() == rs_f.hex(), (name, ply, p, py_f, rs_f)
                    assert (flat_leaf.flat_virtual_score_v2(b.state, p, cfg)
                            == ms.leaf_value(p, rcfgs[name]))
                    checked += 2
        legal = np.flatnonzero(g2.get_valid_moves(b))
        a = int(rng.choice(legal.tolist()))
        b, _ = g2.get_next_state(b, a)
        ms.advance(a)
    assert checked >= 100, f"only {checked} comparisons"
