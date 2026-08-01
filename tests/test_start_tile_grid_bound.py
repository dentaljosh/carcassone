"""The engine grid's start tile is NOT centred — the "invisible border" bug.

Reported 2026-07-30 (Joshua, playing the champion on the Pixel): at the TOP edge
of the board a rule-legal tile placement was never offered, and later the entire
row above the board was dead — "an invisible border to the game".

Root cause (this module is the executable evidence):

    engine/wingedsheep/carcassonne/carcassonne_game_state.py:24-25
        board_size: (int, int) = (35, 35)
        starting_position: Coordinate = Coordinate(6, 15)

Row 6 of a 35-row grid leaves only **6 rows of headroom above** the start tile
versus 28 below (columns are far healthier: 15 left / 19 right). Measured
placed-tile spans reach 17 rows, so a board that drifts upward runs into row 0
routinely. ``StateUpdater.play_tile`` bounds-checks before adding to
``open_positions`` (state_updater.py:42), so off-grid cells never enter the
candidate set and ``TilePositionFinder`` never offers them — silently, with no
error and no visual cue. The Android bridge and Kotlin canvas are pure
pass-throughs of that mask, so the phone renders exactly what the engine
believes: no legal cell above row 0.

Measured over 400 random base+farmers games (paired against an oversized board
so the grid never binds):
    67.8% of games have >= 1 rule-legal placement denied by the wall
    21.7% of tile plies have >= 1 denied placement
     2.6% of all rule-legal tile placements are denied
      100% of denials are row < 0 — zero on any other side

Fixing it is a Joshua decision, not a drive-by: the wall is symmetric between
players, so it is *fair*, but removing it changes the legal-move set in ~68% of
games and therefore makes every existing eval number non-reproducible (and
retires every deck band that was measured under it).

What is safe to say is HOW to fix it, which
``test_even_shift_preserves_the_encoding`` pins: the network representation is
translation-invariant, so recentring the start tile is representation-neutral —
**provided the shift is EVEN on both axes**. ``board_repr.offset_from_centroid_sums``
centres the window with ``round(sum/count)``, and Python's banker's rounding is
only equivariant under even translations (round(0.5)=0 but round(11.5)=12). An
odd shift silently moves the window by one cell on ~half of all positions and
would invalidate every trained checkpoint's input distribution; an even shift is
bit-identical.
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from carcassonne_ai.game_wrapper import Board, Game
from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet
from wingedsheep.carcassonne.utils.action_util import ActionUtil
from wingedsheep.carcassonne.utils.state_updater import StateUpdater

# An EVEN shift on both axes — see the module docstring. Row 6 -> 18 restores the
# headroom (18 above / 16 below); the column stays put (shift 0, trivially even).
ROW_SHIFT = 12


def _fresh_deck(seed: int = 1234) -> list:
    """A deterministic deck. ``initialize_deck`` shuffles via the GLOBAL ``random``
    module, so without pinning the seed these tests would depend on whatever else
    the session ran first."""
    saved = random.getstate()
    try:
        random.seed(seed)
        probe = CarcassonneGameState(
            tile_sets=[TileSet.BASE],
            supplementary_rules=[SupplementaryRule.FARMERS],
            players=2,
        )
        return [probe.next_tile] + list(probe.deck)
    finally:
        random.setstate(saved)


def _state(start_row: int, deck: list, size: int = 35) -> CarcassonneGameState:
    st = CarcassonneGameState(
        tile_sets=[TileSet.BASE],
        supplementary_rules=[SupplementaryRule.FARMERS],
        players=2,
        board_size=(size, size),
        starting_position=Coordinate(start_row, 15),
    )
    st.deck = list(deck)
    st.next_tile = st.deck.pop(0)
    return st


def test_start_tile_is_not_centred() -> None:
    """Pins the defect itself: the start tile sits 6 rows from the top wall."""
    st = CarcassonneGameState(
        tile_sets=[TileSet.BASE],
        supplementary_rules=[SupplementaryRule.FARMERS],
        players=2,
    )
    n_rows, n_cols = len(st.board), len(st.board[0])
    sp = st.starting_position
    above, below = sp.row, n_rows - 1 - sp.row
    left, right = sp.column, n_cols - 1 - sp.column

    # Documented, measured asymmetry. If someone recentres the start tile this
    # assertion fires — which is the intended prompt to do the close-out
    # (results.csv / DECISIONS / band registry), not a reason to revert.
    assert (above, below) == (6, 28), (
        f"start-tile row headroom changed to {(above, below)}; the invisible-border "
        "bug may have been fixed — run the experiment close-out checklist."
    )
    # Columns were never observed to bind (0 denials in 400 games) but are also
    # asymmetric; recorded so a future grid change is a conscious one.
    assert (left, right) == (15, 19)
    # The wall genuinely bites: observed placed-tile spans reach 17 rows > 6.
    assert above < 17


def test_off_grid_cells_never_enter_open_positions() -> None:
    """The mechanism: bounds-checked ``open_positions`` maintenance.

    A tile placed on row 0 has a rule-legal neighbour at row -1, but
    ``StateUpdater.play_tile`` refuses to record it, so ``TilePositionFinder``
    can never offer it and nothing anywhere raises.
    """
    deck = _fresh_deck()
    st = _state(start_row=0, deck=deck)  # start ON the wall
    first = next(a for a in ActionUtil.get_possible_actions(st) if isinstance(a, TileAction))
    st = StateUpdater.apply_action(st, first)

    assert any(c.row == 0 for c in st.placed_coords)
    assert all(c.row >= 0 for c in st.open_positions), (
        "off-grid cells must not appear in open_positions"
    )
    # The cell above the start tile is rule-legal in real Carcassonne but is
    # simply absent from the candidate set — no error, no signal.
    assert Coordinate(row=-1, column=st.starting_position.column) not in st.open_positions


def test_even_shift_preserves_the_encoding() -> None:
    """Recentring by an EVEN shift is bit-identical for the trained representation.

    Plays one deck on both the production board and a row-shifted board and
    compares the encoded tensor + scalars ply-for-ply. This is the check that
    makes a future recentring safe for existing checkpoints; it must keep
    passing. (Divergence of the legal-move MASK is expected and excluded here —
    that divergence IS the bug, and is asserted by the test below.)
    """
    g = Game()
    rng = random.Random(7)
    deck = _fresh_deck()
    a = Board.from_state(_state(6, deck), total_tiles=72, window_size=g.window_size)
    b = Board.from_state(_state(6 + ROW_SHIFT, deck), total_tiles=72, window_size=g.window_size)

    compared = 0
    while not a.state.is_terminated():
        ma, mb = g.get_valid_moves(a), g.get_valid_moves(b)
        if not np.array_equal(ma, mb):
            break  # the wall bit — encoding comparison is no longer paired
        ca, cb = g.get_canonical_form(a, 1), g.get_canonical_form(b, 1)
        ta = ca[0] if isinstance(ca, tuple) else ca
        tb = cb[0] if isinstance(cb, tuple) else cb
        assert np.array_equal(ta, tb), (
            f"board tensor differs at ply {compared} under an even shift — "
            "recentring would NOT be representation-neutral"
        )
        if isinstance(ca, tuple):
            assert np.allclose(ca[1], cb[1]), f"scalars differ at ply {compared}"
        compared += 1
        idx = int(rng.choice(list(np.flatnonzero(ma))))
        a, b = g.get_next_state(a, idx)[0], g.get_next_state(b, idx)[0]

    assert compared > 30, f"only {compared} plies compared — probe degenerate"


def test_odd_shift_breaks_the_window_offset() -> None:
    """Guards the EVEN-shift caveat so a future fix can't quietly pick row 17.

    ``offset_from_centroid_sums`` centres the window with ``round(sum/count)``,
    and Python's ``round`` is banker's rounding (half-to-EVEN). That is
    equivariant under even translations but NOT odd ones: a centroid of 6.5
    rounds to 6, while the same board shifted 11 rows down has centroid 17.5 and
    rounds to 18 — one row more than 6 + 11. The window, and therefore the whole
    encoded tensor, silently slips by one cell.
    """
    from carcassonne_ai.board_repr import offset_from_centroid_sums

    st = _state(6, _fresh_deck())
    # Two placed tiles whose row centroid lands exactly on .5 — the tie case.
    sum_row, sum_col, count = 13, 30, 2
    base = offset_from_centroid_sums(st, sum_row, sum_col, count)

    odd, even = 11, 12
    off_odd = offset_from_centroid_sums(st, sum_row + odd * count, sum_col, count)
    off_even = offset_from_centroid_sums(st, sum_row + even * count, sum_col, count)

    assert off_even.origin_row == base.origin_row + even, (
        "an EVEN shift must translate the window exactly — this is the property "
        "that makes recentring the start tile representation-neutral"
    )
    assert off_odd.origin_row != base.origin_row + odd, (
        "expected an ODD shift to desynchronise the window offset (banker's "
        "rounding); if this no longer holds, the even-shift caveat in the module "
        "docstring can be relaxed"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN BUG (2026-07-30): the 35x35 grid with starting_position (6, 15) denies "
        "rule-legal placements above row 0 in ~68% of games. Fixing it changes the "
        "legal-move set and therefore every existing eval number — a Joshua decision. "
        "When the start tile is recentred this test XPASSes; remove the xfail marker."
    ),
)
def test_no_rule_legal_placement_is_ever_denied() -> None:
    """The contract the engine SHOULD satisfy: the grid never removes a legal move.

    Drives the board upward (always taking the lowest-row legal placement) so the
    wall is reached quickly, and compares the production grid against an oversized
    grid on which the same configuration is unconstrained.
    """
    pad = 30
    deck = _fresh_deck()
    prod = _state(6, deck)
    big = _state(6 + pad, deck, size=35 + 2 * pad)

    for _ in range(40):
        if prod.is_terminated():
            break
        p_acts = ActionUtil.get_possible_actions(prod)
        b_acts = ActionUtil.get_possible_actions(big)
        p_tiles = [a for a in p_acts if isinstance(a, TileAction)]
        b_tiles = [a for a in b_acts if isinstance(a, TileAction)]
        if p_tiles and b_tiles:
            assert len(b_tiles) == len(p_tiles), (
                f"grid denied {len(b_tiles) - len(p_tiles)} rule-legal placement(s); "
                f"lowest legal row on the production board = "
                f"{min(a.coordinate.row for a in p_tiles)}"
            )
            # Drive upward to reach the wall fast.
            p_pick = min(p_tiles, key=lambda a: (a.coordinate.row, a.coordinate.column))
            b_pick = min(b_tiles, key=lambda a: (a.coordinate.row, a.coordinate.column))
        else:
            p_pick, b_pick = p_acts[0], b_acts[0]
        prod = StateUpdater.apply_action(prod, p_pick)
        big = StateUpdater.apply_action(big, b_pick)
