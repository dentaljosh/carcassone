"""F7b FARM-TERM KNOCKOUTS (`LeafConfig.farm_base_off` / `farm_growth_off`).

Roadmap F7b: the one part of the F7 leaf-component ablation that was not
config-severable. Farm scoring enters the champion leaf in TWO places — the farm
award inside `flat_leaf._final_scores` (the BASE term) and the farm-growth block of
`flat_leaf.flat_closure_bonus` — and these two default-OFF knobs sever them
independently, in the Python reference and in the Rust leaf.

Contracts:
  1. DEFAULT OFF IS INERT. The champion's leaf hashes (`a36d2e15a3b3d71d` and the
     frozen-recipe pair) recompute unchanged across the two additive fields, and a
     default-off cfg produces bit-identical leaf values on every path.
  2. The knockouts BITE — a knocked-out leaf differs from the champion leaf on a
     large fraction of real positions (an inert knob would produce a null cell for
     an uninteresting reason).
  3. The knockouts are SEVERABLE: base-off moves only the base term, growth-off
     moves only the closure bonus, both-off moves both.
  4. THE CY FAST PATH IS REFUSED. `flat_leaf_cy.pyx` deliberately does not implement
     the knockouts, so a SET knob must route to the pure-Python flat leaf. A stale
     `.so` can therefore never serve an INTACT-farm leaf to a knockout run.
  5. THE OBJECT PATH FAILS LOUD rather than silently scoring farms intact.
  6. THE EXACT SOLVER'S TERMINAL IS UNTOUCHED. `flat_base_score` without the
     argument is the TRUE final score, farms included — that is what
     `scripts/level2/endgame_solver.py` evaluates, and F7b ablates the heuristic,
     not the rules.
  7. RUST == PYTHON bit-exactly with the knockouts ON (the full-corpus version of
     this is `scripts/rustport/reconcile_leaf.py --configs farmoff`).
"""
from __future__ import annotations

import dataclasses as dc
import random

import numpy as np
import pytest

from carcassonne_ai import flat_leaf
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
CHAMP = dc.replace(DEFAULT_CONFIG, meeple_k=2.0, bonus_cap=8.0, opp_bonus_cap=8.0,
                   closure_p={1: 0.5, 2: 0.2, 3: 0.05}, v29_meeple_curve=CURVE125)
BASE_OFF = dc.replace(CHAMP, farm_base_off=True)
GROWTH_OFF = dc.replace(CHAMP, farm_growth_off=True)
BOTH_OFF = dc.replace(CHAMP, farm_base_off=True, farm_growth_off=True)

cy = pytest.importorskip("carcassonne_ai.flat_leaf_cy")


def _states(n_seeds=6, max_plies=140, start=20, every=6, seed_base=7700):
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


# --- 1. default off is inert ------------------------------------------------ #
def test_defaults_are_off():
    assert DEFAULT_CONFIG.farm_base_off is False
    assert DEFAULT_CONFIG.farm_growth_off is False
    # not env-buildable: no CARCASSONNE_* var can turn a production run into an
    # ablation run (deliberate — these are measurement-only knobs).
    import inspect

    from carcassonne_ai import virtual_score_v2 as vs2
    src = inspect.getsource(vs2._config_from_env)
    assert "farm_base_off" not in src and "farm_growth_off" not in src


def test_champion_leaf_hashes_unchanged():
    """The additive fields must not move the champion's fingerprints."""
    from carcassonne_ai.alphabeta_agent import _leaf_hash

    assert _leaf_hash(CHAMP) == "a36d2e15a3b3d71d"
    assert _leaf_hash(BASE_OFF) != "a36d2e15a3b3d71d"    # a SET knob IS a new leaf
    assert _leaf_hash(GROWTH_OFF) != "a36d2e15a3b3d71d"


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
    """An explicitly-off cfg equals the champion cfg on every path and position."""
    off = dc.replace(CHAMP, farm_base_off=False, farm_growth_off=False)
    for st in states:
        for p in (0, 1):
            assert (flat_leaf.flat_virtual_score_v2_float(st, p, off).hex()
                    == flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP).hex())


# --- 2/3. the knockouts bite, and are severable ----------------------------- #
def test_knockouts_bite(states):
    n = changed_base = changed_growth = 0
    for st in states:
        for p in (0, 1):
            n += 1
            ref = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            if flat_leaf.flat_virtual_score_v2_float(st, p, BASE_OFF) != ref:
                changed_base += 1
            if flat_leaf.flat_virtual_score_v2_float(st, p, GROWTH_OFF) != ref:
                changed_growth += 1
    assert changed_base > 0.2 * n, (changed_base, n)
    assert changed_growth > 0.2 * n, (changed_growth, n)


def test_severability(states):
    """base-off moves ONLY the base; growth-off moves ONLY the closure bonus."""
    moved_base = moved_bonus = 0
    for st in states:
        d = flat_leaf.decompose(st)
        for p in (0, 1):
            b_ref = flat_leaf.flat_base_score(st, p, d)
            assert flat_leaf.flat_base_score(st, p, d, False) == b_ref
            if flat_leaf.flat_base_score(st, p, d, True) != b_ref:
                moved_base += 1
            c_ref = flat_leaf.flat_closure_bonus(st, p, d, CHAMP)
            assert flat_leaf.flat_closure_bonus(st, p, d, BASE_OFF) == c_ref
            if flat_leaf.flat_closure_bonus(st, p, d, GROWTH_OFF) != c_ref:
                moved_bonus += 1
            # the farm-growth block only ever ADDS non-negative contributions
            assert flat_leaf.flat_closure_bonus(st, p, d, GROWTH_OFF) <= c_ref + 1e-12
    assert moved_base and moved_bonus


# --- 4. the cy fast path is refused ----------------------------------------- #
def test_cy_fast_path_refused_for_knockouts(states, monkeypatch):
    assert flat_leaf._farm_knockout_off(CHAMP) is True
    for cfg in (BASE_OFF, GROWTH_OFF, BOTH_OFF):
        assert flat_leaf._farm_knockout_off(cfg) is False

    # With USE_CY_LEAF forced ON, a knockout cfg must NOT reach the .so. Poison the
    # cached cy entry points: if the dispatcher used them the test would explode.
    monkeypatch.setattr(flat_leaf, "USE_CY_LEAF", True)

    def _boom(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("knockout cfg reached the Cython leaf")

    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2", _boom)
    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2_FLOAT", _boom)
    for st in states[:8]:
        for cfg in (BASE_OFF, GROWTH_OFF, BOTH_OFF):
            flat_leaf.flat_virtual_score_v2(st, 0, cfg)
            flat_leaf.flat_virtual_score_v2_float(st, 0, cfg)


def test_cy_does_not_advertise_farm_knockout_support():
    """Documents the F7b decision: the .pyx deliberately has no knockout."""
    assert not hasattr(cy, "SUPPORTS_FARM_KNOCKOUT")


# --- 5. the object path fails loud ------------------------------------------ #
@pytest.mark.parametrize("cfg", [BASE_OFF, GROWTH_OFF, BOTH_OFF])
def test_object_path_fails_loud(states, cfg, monkeypatch):
    monkeypatch.setattr(flat_leaf, "USE_FLAT_LEAF", False)
    with pytest.raises(NotImplementedError, match="farm_base_off"):
        virtual_score_v2(states[0], 0, cfg)


# --- 6. the exact solver's terminal keeps full farm scoring ----------------- #
def test_exact_solver_terminal_unaffected(states):
    """`endgame_solver` calls `flat_base_score(state, 0)` — no cfg, no flag — so it
    keeps scoring farms. F7b ablates the heuristic leaf, not the game's rules."""
    import inspect
    import sys
    from pathlib import Path

    p = str(Path(__file__).resolve().parents[1] / "scripts" / "level2")
    if p not in sys.path:
        sys.path.insert(0, p)
    import endgame_solver as S

    src = inspect.getsource(S)
    assert "flat_base_score" in src
    assert "farm_base_off" not in src and "farm_off" not in src
    for st in states[:8]:
        # the no-argument call is the champion/true score on every substrate
        assert (flat_leaf.flat_base_score(st, 0)
                == int(cy.flat_base_score_cy(st, 0))
                == flat_leaf.flat_base_score(st, 0, flat_leaf.decompose(st)))


# --- 7. rust == python with the knockouts ON -------------------------------- #
def test_leaf_config_rs_forwards_both_knobs():
    """A dropped kwarg in the Python->Rust translation would silently run an INTACT
    leaf on the Rust side — the exact hazard that makes a knockout read as null.
    The full-corpus python-vs-rust bit-exactness lives in
    `scripts/rustport/reconcile_leaf.py --configs farmoff`."""
    pytest.importorskip("carc_rs")
    from carcassonne_ai.rust_agent import leaf_config_rs

    for cfg, (want_base, want_growth) in (
            (CHAMP, (False, False)), (BASE_OFF, (True, False)),
            (GROWTH_OFF, (False, True)), (BOTH_OFF, (True, True))):
        r = repr(leaf_config_rs(cfg))
        assert f"farm_base_off: {str(want_base).lower()}" in r, r
        assert f"farm_growth_off: {str(want_growth).lower()}" in r, r
