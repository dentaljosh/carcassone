"""F9-A2 — the cloister-completion scan fix (`cloister_scan_fix`), Python side.

The deterministic control/trigger pair from the rules-fidelity audit
(`docs/RULES_FIDELITY_AUDIT_20260802.md`, RF-D-1) promoted into `tests/`:

    a cloister with a monk at (10, 10), completed by a placement at (9, 10).

    control  nothing to the right of the 3x3 block.  The drifting scan happens
             to reach (10, 10) anyway -> scores 9, monk returns.
    trigger  tiles also at (8, 11) and (9, 12).  Scan row 9 drifts to cols
             10-12 and row 10 to cols 11-13, so (10, 10) is never visited ->
             nothing scored, MONK PINNED for the rest of the game.

The flag is OPT-IN and DEFAULT OFF, so `trigger + flags-off` must keep failing
exactly as recorded — that is the pin on the quirk the Rust port carries
verbatim (G1) — and only `trigger + flags-on` scores at the true ply.

The Rust twin of this pair lives in `rust/carc/carc-core/src/engine/mod.rs`
(`cloister_scan_fix_*` unit tests); the two engines are checked against each
other action-for-action by `scripts/rustport/lockstep_fuzz.py --cloister-scan-fix`.
"""

from __future__ import annotations

import copy

import pytest

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles
from wingedsheep.carcassonne.utils.points_collector import PointsCollector

CLOISTER = Coordinate(10, 10)
PLACEMENT = Coordinate(9, 10)          # the tile whose placement completes it
TRIGGER_TILES = ((8, 11), (9, 12))     # what makes the scan window drift away

# Every tile in the fixture is a plain "chapel" (four grass edges, cloister
# centre).  No cities, no roads, no farmers -> the ONLY scoring event any of
# these tests can produce is the cloister one under examination.
FILLER = "chapel"


def _fixture(trigger: bool, fix: bool) -> CarcassonneGameState:
    """The audit's board: a monk-bearing cloister whose 3x3 is exactly full."""
    st = CarcassonneGameState(cloister_scan_fix=fix)
    tile = base_tiles[FILLER]
    for r in range(CLOISTER.row - 1, CLOISTER.row + 2):
        for c in range(CLOISTER.column - 1, CLOISTER.column + 2):
            st.board[r][c] = tile
    if trigger:
        for r, c in TRIGGER_TILES:
            st.board[r][c] = tile
    st.players = 2
    st.scores = [0, 0]
    st.meeples = [6, 7]                # player 0 has the monk on the board
    st.placed_meeples = [
        [MeeplePosition(meeple_type=MeepleType.NORMAL,
                        coordinate_with_side=CoordinateWithSide(CLOISTER, Side.CENTER))],
        [],
    ]
    return st


def _score(st: CarcassonneGameState) -> None:
    PointsCollector.remove_meeples_and_collect_points(game_state=st, coordinate=PLACEMENT)


def _accel(st: CarcassonneGameState) -> int:
    return getattr(st, "cloister_completions_accelerated", 0)


# --- the reproducer pair ---------------------------------------------------

@pytest.mark.parametrize("fix", [False, True])
def test_control_scores_and_returns_the_monk_under_both_conventions(fix):
    """Control: the drift is harmless here, so the two conventions agree."""
    st = _fixture(trigger=False, fix=fix)
    _score(st)
    assert st.scores == [9, 0]
    assert st.meeples == [7, 7]
    assert st.placed_meeples[0] == []
    # The legacy walk reached (10, 10) too, so nothing was "accelerated".
    assert _accel(st) == 0


def test_trigger_flags_off_misses_the_completion_and_pins_the_monk():
    """DEFAULT behaviour — RF-D-1, pinned so a silent fix cannot slip in."""
    st = _fixture(trigger=True, fix=False)
    _score(st)
    assert st.scores == [0, 0]
    assert st.meeples == [6, 7]
    assert len(st.placed_meeples[0]) == 1
    assert st.placed_meeples[0][0].coordinate_with_side.coordinate == CLOISTER
    assert _accel(st) == 0             # counter never moves on the default path


def test_trigger_flags_on_scores_at_the_true_ply_and_frees_the_monk():
    st = _fixture(trigger=True, fix=True)
    _score(st)
    assert st.scores == [9, 0]
    assert st.meeples == [7, 7]
    assert st.placed_meeples[0] == []
    assert _accel(st) == 1             # exactly one monk-pin avoided


# --- the endgame interaction (points deferred, not lost) -------------------

def test_the_endgame_pass_pays_the_same_total_either_way():
    """`count_final_scores` awards 9 for a monk still sitting on a completed
    cloister, so the TOTAL is convention-independent: the flag moves *when* the
    9 lands (and whether the meeple is available in between), not how much."""
    off = _fixture(trigger=True, fix=False)
    _score(off)
    assert off.scores == [0, 0]        # deferred
    PointsCollector.count_final_scores(off)
    assert off.scores == [9, 0]

    on = _fixture(trigger=True, fix=True)
    _score(on)
    assert on.scores == [9, 0]         # paid at the true ply
    PointsCollector.count_final_scores(on)
    assert on.scores == [9, 0]         # and NOT paid twice


def test_flags_on_leaves_no_meeple_for_the_endgame_pass_to_re_score():
    on = _fixture(trigger=True, fix=True)
    _score(on)
    before = list(on.scores)
    PointsCollector.count_final_scores(on)
    assert on.scores == before, "the monk was already returned; nothing left to pay"


# --- the flag is a state property that survives the copy -------------------

def test_the_flag_and_counter_survive_deepcopy():
    """`CarcassonneGameState.__deepcopy__` is hand-written (it builds the copy
    with `__new__` and assigns field by field), so a new field is invisible to
    it unless it is added there.  An MCTS rollout deep-copies every ply."""
    st = _fixture(trigger=True, fix=True)
    _score(st)
    clone = copy.deepcopy(st)
    assert clone.cloister_scan_fix is True
    assert clone.cloister_completions_accelerated == 1

    plain = copy.deepcopy(_fixture(trigger=True, fix=False))
    assert plain.cloister_scan_fix is False


def test_default_state_construction_is_flags_off():
    assert CarcassonneGameState().cloister_scan_fix is False
    assert CarcassonneGameState().cloister_completions_accelerated == 0


# --- the wrapper knob ------------------------------------------------------

def test_game_wrapper_default_is_off_and_opt_in_reaches_the_engine():
    from carcassonne_ai.game_wrapper import Game

    assert Game().cloister_scan_fix is False
    assert Game().get_init_board().state.cloister_scan_fix is False
    assert Game(cloister_scan_fix=True).get_init_board().state.cloister_scan_fix is True


def test_the_legacy_scan_cell_enumeration_matches_the_audit():
    """The counter's denominator: the cells the drifting scan actually visits.
    Audit RF-D-1 — row 9 drifts to cols 10-12, row 10 to cols 11-13."""
    st = _fixture(trigger=True, fix=True)
    visited = PointsCollector._legacy_scan_cells(st, PLACEMENT)
    assert (10, 10) not in visited, "the trigger's whole point"
    assert visited == {(8, 11), (9, 10), (9, 11), (9, 12), (10, 11)}

    control = _fixture(trigger=False, fix=True)
    assert (10, 10) in PointsCollector._legacy_scan_cells(control, PLACEMENT)
