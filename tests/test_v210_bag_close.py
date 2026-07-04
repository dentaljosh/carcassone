"""v2.10 bag-aware closure gate (docs/V210_LEAF_SPEC_2026-07-04.md Track B,
CARCASSONNE_V210_BAG_CLOSE, flat_leaf + flat_leaf_cy).

Contracts:
  1. Default OFF == bit-identical v2.9: the flat leaf with bag_close=False still
     equals the object path under CANONICAL_BONUS_SUM (the pre-existing gate
     invariant), and the module flag defaults to False.
  2. python <-> cython parity is bit-exact with the gate OFF *and* ON (mandatory
     per the spec).
  3. The gate actually bites (ON != OFF somewhere on late-game states) — not inert.
  4. Exact stuck-meeple semantics: with an EMPTY bag every unfinished-feature
     contribution is gated -> closure bonus == 0.0 exactly.
  5. _bag_stats phase semantics: the in-hand next_tile counts in the TILES phase
     only (in MEEPLES phase it is a stale ref to the just-placed tile).
  6. The engine/object path fails LOUDLY when the flag is on (never silently
     drops the gate).
"""
from __future__ import annotations

import dataclasses as dc
import random

import numpy as np
import pytest

from carcassonne_ai import flat_leaf
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

BMILD_CAP8 = dc.replace(
    DEFAULT_CONFIG, meeple_k=2.0, bonus_cap=8.0, opp_bonus_cap=8.0,
    v29_meeple_curve=(-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0),
)

cy = pytest.importorskip("carcassonne_ai.flat_leaf_cy")


def _states(n_seeds=8, max_plies=140, start=20, every=4, seed_base=500):
    """Random-play states from opening through endgame (deck runs low late —
    that's where the bag gate fires)."""
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


def test_module_flag_defaults_off():
    assert flat_leaf.V210_BAG_CLOSE is False
    assert bool(getattr(cy, "SUPPORTS_V210_BAG_CLOSE", False)) is True


def test_off_bit_identical_and_py_cy_parity_on():
    """One pass over the states checks: OFF py==cy, ON py==cy (parity), and the
    OFF value still equals the object path under canonical fsum (v2.9 unchanged)."""
    import carcassonne_ai.virtual_score_v2 as vs

    states = _states()
    saved_flat, saved_cy, saved_canon = (
        flat_leaf.USE_FLAT_LEAF, flat_leaf.USE_CY_LEAF, vs.CANONICAL_BONUS_SUM)
    n_bite = 0
    try:
        for st in states:
            for p in (0, 1):
                flat_leaf.USE_CY_LEAF = False
                py_off = flat_leaf.flat_virtual_score_v2(st, p, BMILD_CAP8, bag_close=False)
                py_on = flat_leaf.flat_virtual_score_v2(st, p, BMILD_CAP8, bag_close=True)
                flat_leaf.USE_CY_LEAF = True
                cy_off = cy.flat_virtual_score_v2_cy(st, p, BMILD_CAP8, False)
                cy_on = cy.flat_virtual_score_v2_cy(st, p, BMILD_CAP8, True)
                assert py_off == cy_off, "py<->cy parity broke with the gate OFF"
                assert py_on == cy_on, "py<->cy parity broke with the gate ON"
                if py_on != py_off:
                    n_bite += 1
                # OFF still == the validated object path (canonical fsum)
                vs.CANONICAL_BONUS_SUM = True
                flat_leaf.USE_FLAT_LEAF = False
                obj = virtual_score_v2(st, p, BMILD_CAP8)
                flat_leaf.USE_FLAT_LEAF = saved_flat
                vs.CANONICAL_BONUS_SUM = saved_canon
                assert py_off == obj, "gate-OFF flat leaf drifted from the object path"
    finally:
        flat_leaf.USE_FLAT_LEAF = saved_flat
        flat_leaf.USE_CY_LEAF = saved_cy
        vs.CANONICAL_BONUS_SUM = saved_canon
    assert n_bite > 0, "bag gate never changed a score - it is inert"


def test_empty_bag_zeroes_all_closure_contributions():
    """Zero matching tiles => P=0 exactly: with deck emptied, the UNCAPPED
    closure bonus must be exactly 0.0 for both players on every state (cities,
    growth cities and cloisters are all bag-gated)."""
    states = _states(n_seeds=4)
    n_had_bonus = 0
    for st in states:
        saved_deck, saved_nt = st.deck, st.next_tile
        try:
            st.deck = []
            st.next_tile = None
            decomp = flat_leaf.decompose(st)
            bag = flat_leaf._bag_stats(st)
            assert bag == (0, 0, 0, 0, 0)
            for p in (0, 1):
                if flat_leaf.flat_closure_bonus(st, p, decomp, BMILD_CAP8, None) > 0:
                    n_had_bonus += 1
                assert flat_leaf.flat_closure_bonus(st, p, decomp, BMILD_CAP8, bag) == 0.0
        finally:
            st.deck, st.next_tile = saved_deck, saved_nt
    assert n_had_bonus > 0, "no state had any ungated bonus - test vacuous"


def test_bag_stats_phase_semantics():
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    st = b.state
    assert st.phase == GamePhase.TILES and st.next_tile is not None
    assert flat_leaf._bag_stats(st)[0] == len(st.deck) + 1, "TILES phase must count the in-hand tile"
    # advance one tile placement -> MEEPLES phase, next_tile now ON the board
    legal = np.flatnonzero(g.get_valid_moves(b))
    b2, _ = g.get_next_state(b, int(legal[0]))
    st2 = b2.state
    if st2.phase == GamePhase.MEEPLES:
        assert flat_leaf._bag_stats(st2)[0] == len(st2.deck), "MEEPLES phase must NOT count the stale next_tile"


def test_object_path_fails_loudly_when_flag_on():
    saved_flag, saved_flat = flat_leaf.V210_BAG_CLOSE, flat_leaf.USE_FLAT_LEAF
    st = _states(n_seeds=1, max_plies=30, start=20)[0]
    try:
        flat_leaf.V210_BAG_CLOSE = True
        flat_leaf.USE_FLAT_LEAF = False   # forces the engine/object path
        with pytest.raises(NotImplementedError):
            virtual_score_v2(st, 0, BMILD_CAP8)
    finally:
        flat_leaf.V210_BAG_CLOSE = saved_flag
        flat_leaf.USE_FLAT_LEAF = saved_flat
