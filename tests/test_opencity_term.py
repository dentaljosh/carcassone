"""OPEN-CITY DISCIPLINE — penalize the acting side's OWN large open cities
(`LeafConfig.opencity_dose` / `opencity_size_min` / `opencity_edge_min` /
`opencity_symmetric`).

BACKLOG 2026-05-16 / LEVER_INDEX "penalize large open cities" — the flagged
NEVER-TRIED leaf term, externally endorsed 2026-08-12 by four independent strategy
guides (docs/research/PRO_STRATEGY_SCAN_2026-08-12.md §F1): city scoring gives no
per-tile size bonus while completion probability falls and steal/merge exposure
rises with every open edge, so the champion's leaf — which prices a city's
anticipated VALUE but never its RISK — reads a big wide-open city as an asset
where a strong human reads a liability. The term subtracts
`dose * ((tiles - size_min + 1) * (open_n - edge_min + 1))` summed over the side's
own strict-majority incomplete cities, as a SIGNED differential, in
`flat_leaf.flat_opencity_term` and the Rust `carc_core::leaf::opencity_term`.
Spec: measurement/opencity_term_20260812/TERM_SPEC.md.

Contracts (the denial / F7b test-file pattern):
  1. DEFAULT OFF IS INERT. The champion's leaf hashes recompute unchanged across
     the four additive fields, and a default-off cfg produces bit-identical leaf
     values (dose 0.0 gates the whole term — the other three knobs are inert while
     it is 0.0, INCLUDING a flipped `opencity_symmetric`).
  2. The term FIRES ONLY ON QUALIFYING CITIES — the predicate matrix is pinned on
     hand-built fixtures: large+wide own city fires; large-but-nearly-closed
     doesn't; small+wide doesn't; TIED and unmeepled never; finished or unclosable
     (open_n == 0) never; big meeples weigh 2; the escalation is the product of the
     two linear excesses.
  3. SCOPE + SIGN. The penalty follows the BUILDER (own strict majority), never the
     opponent's cities in their own right; symmetric (default) makes the term
     ANTISYMMETRIC (`T(p) == -T(1-p)`, so it can RAISE the eval when the opponent
     is the more overextended builder); asymmetric makes it own-side-only and
     non-negative. Either way the leaf moves by exactly `-dose * T` — the term
     ADJUSTS the city terms, it never replaces them.
  4. ENV/CONFIG PLUMBING round-trips (CARCASSONNE_OPENCITY_* -> _config_from_env).
  5. THE CY FAST PATH IS REFUSED (no cy implementation, the F7b/denial decision —
     the candidate cells run `--backend rust`); a stale `.so` can never serve an
     intact (open-city-blind) leaf to an open-city run.
  6. THE OBJECT PATH FAILS LOUD rather than silently scoring without the term.
  7. RUST == PYTHON bit-exactly with the term ON (spot check here; the full-corpus
     gate is `scripts/rustport/reconcile_leaf.py --configs opencity`), and
     `rust_agent.leaf_config_rs` forwards the knobs as conditional kwargs — a stale
     carc_rs build keeps serving default-off configs but raises TypeError on a
     nonzero dose (fail-closed loud, never a silently-intact leaf).
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
O_HALF = dc.replace(CHAMP, opencity_dose=0.5)
O_ONE = dc.replace(CHAMP, opencity_dose=1.0)
# deliberately permissive thresholds so the term fires often on random states
O_LOOSE = dc.replace(CHAMP, opencity_dose=2.0, opencity_size_min=2.0, opencity_edge_min=1)
O_ASYM = dc.replace(CHAMP, opencity_dose=1.0, opencity_size_min=2.0,
                    opencity_edge_min=1, opencity_symmetric=False)
# dose 0.0 with MOVED thresholds AND flipped symmetry — must be bit-identical to CHAMP.
O_IDENTITY = dc.replace(CHAMP, opencity_dose=0.0, opencity_size_min=2.0,
                        opencity_edge_min=1, opencity_symmetric=False)

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
# exactly the fields flat_opencity_term reads.                                 #
# --------------------------------------------------------------------------- #
class _CityTile:
    def get_type(self, side):
        return TerrainType.CITY


def _mk(cities, meeples):
    """cities: {root: (finished, open_n, n_tiles)}.
    meeples: [(player, root, meeple_type)] — each meeple gets its own cell (row =
    an increasing counter, col 0, side TOP) mapped onto its city root.

    `city_root_coords` carries `n_tiles` synthetic distinct coordinates per root —
    the term reads only its CARDINALITY. `city_root_delta` is filled consistently
    (tiles, no shields) so the fixture stays a legal Decomp, but the open-city term
    never consults it: tiles, not points, is this term's size axis."""
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
        city_root_positions={},
        city_root_coords={k: {(k, i) for i in range(v[2])} for k, v in cities.items()},
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
    assert DEFAULT_CONFIG.opencity_dose == 0.0
    assert DEFAULT_CONFIG.opencity_size_min == 4.0
    assert DEFAULT_CONFIG.opencity_edge_min == 2
    assert DEFAULT_CONFIG.opencity_symmetric is True
    # env-buildable candidate knob (the v29_phase_beta / denial pattern):
    # CARCASSONNE_OPENCITY_* defaults keep production DEFAULT_CONFIG unchanged.
    import inspect

    from carcassonne_ai import virtual_score_v2 as vs2
    src = inspect.getsource(vs2._config_from_env)
    assert "CARCASSONNE_OPENCITY_DOSE" in src


def test_env_round_trip(monkeypatch):
    monkeypatch.setenv("CARCASSONNE_OPENCITY_DOSE", "1.5")
    monkeypatch.setenv("CARCASSONNE_OPENCITY_SIZE_MIN", "6")
    monkeypatch.setenv("CARCASSONNE_OPENCITY_EDGE_MIN", "3")
    monkeypatch.setenv("CARCASSONNE_OPENCITY_SYMMETRIC", "0")
    cfg = _config_from_env()
    assert cfg.opencity_dose == 1.5
    assert cfg.opencity_size_min == 6.0
    assert cfg.opencity_edge_min == 3
    assert cfg.opencity_symmetric is False
    for k in ("CARCASSONNE_OPENCITY_DOSE", "CARCASSONNE_OPENCITY_SIZE_MIN",
              "CARCASSONNE_OPENCITY_EDGE_MIN", "CARCASSONNE_OPENCITY_SYMMETRIC"):
        monkeypatch.delenv(k)
    off = _config_from_env()
    assert (off.opencity_dose, off.opencity_size_min, off.opencity_edge_min,
            off.opencity_symmetric) == (0.0, 4.0, 2, True)


def test_champion_leaf_hashes_unchanged():
    """The additive fields must not move the champion's fingerprints."""
    from carcassonne_ai.alphabeta_agent import _leaf_hash

    assert _leaf_hash(CHAMP) == "a36d2e15a3b3d71d"
    assert _leaf_hash(O_HALF) != "a36d2e15a3b3d71d"      # a SET dose IS a new leaf
    assert _leaf_hash(O_HALF) != _leaf_hash(O_ONE)
    assert _leaf_hash(O_ONE) != _leaf_hash(O_ASYM)       # symmetry is part of the leaf


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
    """dose 0.0 == champion bit-for-bit, even with MOVED thresholds and a FLIPPED
    symmetry flag (the dose gates the whole term), on both the int and pre-round
    float paths."""
    for st in states:
        for p in (0, 1):
            ref_f = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            assert flat_leaf.flat_virtual_score_v2_float(st, p, O_IDENTITY).hex() == ref_f.hex()
            assert (flat_leaf.flat_virtual_score_v2(st, p, O_IDENTITY)
                    == flat_leaf.flat_virtual_score_v2(st, p, CHAMP))


# --- 2. the predicate matrix (hand-built fixtures) --------------------------- #
def test_fires_on_large_wide_own_city():
    # 6 tiles, 3 open, my knight: (6-4+1) * (3-2+1) = 3 * 2 = 6, charged to ME.
    st, d = _mk({7: (False, 3, 6)}, [(0, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == pytest.approx(6.0)
    # the threshold corner is exactly 1.0
    st, d = _mk({7: (False, 2, 4)}, [(0, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == pytest.approx(1.0)
    # escalation is the PRODUCT of the two linear excesses
    st, d = _mk({7: (False, 4, 7)}, [(0, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == pytest.approx((7 - 4 + 1) * (4 - 2 + 1))


def test_does_not_fire_nearly_closed():
    # large but only ONE open edge — the shape the guides PREFER.
    st, d = _mk({7: (False, 1, 9)}, [(0, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == 0.0
    # boundary: open_n == edge_min fires, edge_min-1 doesn't
    st, d = _mk({7: (False, 2, 9)}, [(0, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) > 0.0


def test_does_not_fire_small():
    st, d = _mk({7: (False, 4, 3)}, [(0, 7, N)])    # wide open but only 3 tiles
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == 0.0
    # boundary: tiles == size_min fires
    st, d = _mk({7: (False, 2, 4)}, [(0, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == pytest.approx(1.0)


def test_never_fires_on_tied_or_unmeepled_city():
    # TIED city never fires either way — nobody OWNS the overextension.
    st, d = _mk({7: (False, 3, 6)}, [(0, 7, N), (1, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == 0.0
    assert flat_leaf.flat_opencity_term(st, 1, d, O_ONE) == 0.0
    # unmeepled city never fires (no committed stake).
    st, d = _mk({7: (False, 3, 6)}, [])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == 0.0


def test_never_fires_finished_or_unclosable():
    st, d = _mk({7: (True, 0, 9)}, [(0, 7, N)])     # finished
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == 0.0
    st, d = _mk({7: (False, 0, 9)}, [(0, 7, N)])    # D16 unclosable board-edge city
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == 0.0
    # even with edge_min lowered to 1, open_n == 0 stays inert
    st, d = _mk({7: (False, 0, 9)}, [(0, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_LOOSE) == 0.0


def test_meeple_weights_and_multiple_cities():
    # big meeple weighs 2: my BIG vs opp 1 normal -> strict majority -> charged to me.
    st, d = _mk({7: (False, 3, 6)}, [(0, 7, BIG), (1, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == pytest.approx(6.0)
    # my BIG vs opp 2 normals -> tied -> nobody is charged.
    st, d = _mk({7: (False, 3, 6)}, [(0, 7, BIG), (1, 7, N), (1, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == 0.0
    # two qualifying own cities sum; a non-qualifying third adds nothing.
    st, d = _mk({1: (False, 2, 4), 2: (False, 3, 5), 3: (False, 1, 12)},
                [(0, 1, N), (0, 2, N), (0, 3, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == pytest.approx(1.0 + 2.0 * 2.0)
    # the loose cell (size_min 2, edge_min 1) picks up smaller/narrower cities.
    st, d = _mk({1: (False, 1, 3)}, [(0, 1, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == 0.0
    assert flat_leaf.flat_opencity_term(st, 0, d, O_LOOSE) == pytest.approx((3 - 2 + 1) * (1 - 1 + 1))


# --- 3. scope + sign -------------------------------------------------------- #
def test_scope_follows_the_builder_and_is_antisymmetric():
    """The penalty is charged to whoever OWNS the overextended city — so under the
    default (symmetric) flag it LOWERS the owner's eval and RAISES the other's by
    the same magnitude. That antisymmetry is the reason symmetric is the default."""
    st, d = _mk({7: (False, 3, 6)}, [(0, 7, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == pytest.approx(6.0)
    assert flat_leaf.flat_opencity_term(st, 1, d, O_ONE) == pytest.approx(-6.0)
    # net differential when BOTH players are overextended
    st, d = _mk({1: (False, 3, 6), 2: (False, 2, 4)}, [(0, 1, N), (1, 2, N)])
    assert flat_leaf.flat_opencity_term(st, 0, d, O_ONE) == pytest.approx(6.0 - 1.0)
    assert flat_leaf.flat_opencity_term(st, 1, d, O_ONE) == pytest.approx(1.0 - 6.0)


def test_asymmetric_flag_is_own_side_only_and_nonnegative():
    st, d = _mk({7: (False, 3, 6)}, [(0, 7, N)])
    asym1 = dc.replace(O_ONE, opencity_symmetric=False)
    assert flat_leaf.flat_opencity_term(st, 0, d, asym1) == pytest.approx(6.0)
    assert flat_leaf.flat_opencity_term(st, 1, d, asym1) == 0.0   # not credited the opp's sin


def test_antisymmetry_on_the_corpus(states):
    """T(p) == -T(1-p) exactly, for every symmetric config, on real states."""
    for st in states:
        d = flat_leaf.decompose(st)
        for cfg in (O_ONE, O_LOOSE):
            t0 = flat_leaf.flat_opencity_term(st, 0, d, cfg)
            t1 = flat_leaf.flat_opencity_term(st, 1, d, cfg)
            assert t0 == pytest.approx(-t1, abs=1e-12)


def test_leaf_moves_by_exactly_dose_times_term(states):
    """The term ADJUSTS the leaf by exactly `-dose * T` — it never replaces the
    existing (closure-anticipation) city credit."""
    fired = 0
    for st in states:
        d = flat_leaf.decompose(st)
        for p in (0, 1):
            ref = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            for cfg in (O_HALF, O_ONE, O_LOOSE, O_ASYM):
                t = flat_leaf.flat_opencity_term(st, p, d, cfg)
                if not cfg.opencity_symmetric:
                    assert t >= 0.0
                got = flat_leaf.flat_virtual_score_v2_float(st, p, cfg)
                assert got == pytest.approx(ref - cfg.opencity_dose * t, abs=1e-9)
                if t:
                    fired += 1
    assert fired > 0, "open-city term never fired on the random-state corpus — inert fixture set"


# --- 5. the cy fast path is refused ------------------------------------------ #
def test_cy_fast_path_refused_for_opencity(states, monkeypatch):
    assert flat_leaf._opencity_off(CHAMP) is True
    assert flat_leaf._opencity_off(O_IDENTITY) is True    # dose 0.0 == off, cy OK
    for cfg in (O_HALF, O_ONE, O_LOOSE, O_ASYM):
        assert flat_leaf._opencity_off(cfg) is False

    monkeypatch.setattr(flat_leaf, "USE_CY_LEAF", True)

    def _boom(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("open-city cfg reached the Cython leaf")

    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2", _boom)
    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2_FLOAT", _boom)
    for st in states[:8]:
        for cfg in (O_HALF, O_ONE, O_LOOSE, O_ASYM):
            flat_leaf.flat_virtual_score_v2(st, 0, cfg)
            flat_leaf.flat_virtual_score_v2_float(st, 0, cfg)


def test_cy_does_not_advertise_opencity_support():
    """Documents the decision: the .pyx deliberately has no open-city term."""
    assert not hasattr(cy, "SUPPORTS_OPENCITY")


# --- 6. the object path fails loud ------------------------------------------- #
@pytest.mark.parametrize("cfg", [O_HALF, O_ONE, O_LOOSE, O_ASYM])
def test_object_path_fails_loud(states, cfg, monkeypatch):
    monkeypatch.setattr(flat_leaf, "USE_FLAT_LEAF", False)
    with pytest.raises(NotImplementedError, match="opencity_dose"):
        virtual_score_v2(states[0], 0, cfg)


# --- the --cand-leaf-json severability path ---------------------------------- #
def test_cand_leaf_json_round_trip_and_guards(capsys):
    """The candidate side is severable through `--cand-leaf-json` exactly like the
    denial term: named fields replace ONLY the candidate leaf, an unknown field is
    fatal, a set dose WARNS about leaving the cy fast path, and a nonsensical
    threshold is fatal."""
    import sys
    from pathlib import Path

    p = str(Path(__file__).resolve().parents[1] / "scripts" / "classical_search")
    if p not in sys.path:
        sys.path.insert(0, p)
    import c5_leaf_override as ovr

    assert ovr._load_cand_leaf_cfg(None) is None
    cfg = ovr._load_cand_leaf_cfg(
        '{"opencity_dose": 1.0, "opencity_size_min": 5.0, "opencity_edge_min": 3,'
        ' "opencity_symmetric": false,'
        ' "v29_meeple_curve": [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]}')
    assert cfg.opencity_dose == 1.0
    assert cfg.opencity_size_min == 5.0
    assert cfg.opencity_edge_min == 3
    assert cfg.opencity_symmetric is False
    assert tuple(cfg.v29_meeple_curve) == CURVE125
    # a SET dose is a different leaf than the champion (the wiring gate's check)
    assert ovr._leaf_hash(cfg) != ovr._leaf_hash(DEFAULT_CONFIG)
    # ... but a dose-0.0 override with moved thresholds hashes AS the champion
    # (the fields are excluded while default -> a no-op JSON cannot fake a new leaf)
    same = ovr._load_cand_leaf_cfg('{"opencity_dose": 0.0}')
    assert ovr._leaf_hash(same) == ovr._leaf_hash(DEFAULT_CONFIG)

    with pytest.raises(ValueError, match="unknown LeafConfig field"):
        ovr._load_cand_leaf_cfg('{"opencity_does": 1.0}')

    ovr._assert_cy_float_path(cfg)
    assert "open-city discipline set" in capsys.readouterr().err
    with pytest.raises(ValueError, match="opencity_edge_min"):
        ovr._assert_cy_float_path(dc.replace(cfg, opencity_edge_min=0))
    with pytest.raises(ValueError, match="opencity_size_min"):
        ovr._assert_cy_float_path(dc.replace(cfg, opencity_size_min=0.0))


# --- 7. rust parity + config forwarding -------------------------------------- #
def _rs_supports_opencity(carc_rs) -> bool:
    try:
        carc_rs.LeafConfigRs([(1, 0.5)], 8.0, 8.0, opencity_dose=1.0,
                             opencity_size_min=4.0, opencity_edge_min=2,
                             opencity_symmetric=True)
        return True
    except TypeError:
        return False


def test_leaf_config_rs_conditional_kwargs():
    """Default-off configs must build on ANY carc_rs (no opencity kwargs passed);
    a nonzero dose must either forward (opencity-capable build) or raise TypeError
    (stale build — fail-closed loud, never a silently-intact leaf)."""
    carc_rs = pytest.importorskip("carc_rs")
    from carcassonne_ai.rust_agent import leaf_config_rs

    leaf_config_rs(CHAMP)          # any build
    leaf_config_rs(O_IDENTITY)     # dose 0.0 -> no kwargs -> any build
    if _rs_supports_opencity(carc_rs):
        r = repr(leaf_config_rs(O_LOOSE))
        assert "opencity_dose: 2.0" in r, r
        assert "opencity_size_min: 2.0" in r, r
        assert "opencity_edge_min: 1" in r, r
        assert "opencity_symmetric: true" in r, r
        assert "opencity_symmetric: false" in repr(leaf_config_rs(O_ASYM))
    else:
        with pytest.raises(TypeError):
            leaf_config_rs(O_ONE)


def test_rust_parity_spot_check():
    """py == rust bit-exactly with the open-city term ON along one replayed game
    (the full-corpus version is
    `scripts/rustport/reconcile_leaf.py --configs opencity`)."""
    carc_rs = pytest.importorskip("carc_rs")
    if not _rs_supports_opencity(carc_rs):
        pytest.skip("carc_rs build predates the open-city term (rebuild the wheel)")
    from carcassonne_ai.rust_agent import leaf_config_rs

    cfgs = {"champ": CHAMP, "o1": O_ONE, "loose": O_LOOSE, "asym": O_ASYM}
    rcfgs = {name: leaf_config_rs(cfg) for name, cfg in cfgs.items()}

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


def test_rust_leaf_terms_exposes_opencity():
    """The per-term breakdown carries the raw T (0.0 while the dose is off)."""
    carc_rs = pytest.importorskip("carc_rs")
    if not _rs_supports_opencity(carc_rs):
        pytest.skip("carc_rs build predates the open-city term (rebuild the wheel)")
    from carcassonne_ai.rust_agent import leaf_config_rs

    ms = carc_rs.MirrorState.from_seed("4242")
    rng = random.Random(1)
    g2 = Game(enable_legal_moves_cache=True)
    import random as _r
    _r.seed(4242)
    b = g2.get_init_board()
    for _ in range(60):
        legal = np.flatnonzero(g2.get_valid_moves(b))
        a = int(rng.choice(legal.tolist()))
        b, _ = g2.get_next_state(b, a)
        ms.advance(a)
    assert ms.leaf_terms(0, leaf_config_rs(CHAMP))["opencity_term"] == 0.0
    d = flat_leaf.decompose(b.state)
    assert (ms.leaf_terms(0, leaf_config_rs(O_LOOSE))["opencity_term"]
            == pytest.approx(flat_leaf.flat_opencity_term(b.state, 0, d, O_LOOSE)))
