"""F9 W4 — the wall sentinel's event definitions, one synthetic position per face.

The border ledger the sentinel must count DISTINCTLY (DECISIONS 2026-07-31 evening
and night; docs/F9_BUILD_SPEC_20260802.md §A1):

    1. silent wall denial   — the `open_positions` bounds-drop, BY FACE
    2. negative-row wrap    — `board[-1]` silently reads row 34
    3. col-34 placement     — FATAL, `IndexError` in the farm path
    4. last-row placement   — FATAL, `count_final_scores`' unguarded `board[r+1]`
    5. WindowOverflowError  — FATAL, the 25x25 centroid window

They are three DIFFERENT failures — a silent bias, a silent wrong read, and two
hard crashes — which is exactly why one "the wall fired" counter would be useless
for the W2-vs-W3 decision: W2 removes face 1 and makes faces 3-4 MORE reachable
(spec T2). Each face therefore gets its own synthetic position here.

The G1 lockstep reproducers (`measurement/rustport_p1/G1_lockstep_reproducers/`)
are used as the ground truth for what the fatal faces look like in a real game —
their recorded `last_tile` / `window_origin` are replayed through the sentinel's
classifier, so the definitions in this module are pinned to the events that
actually killed games rather than to my reading of them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from carcassonne_ai import wall_sentinel as ws
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

REPRO = Path(__file__).resolve().parents[1] / "measurement" / "rustport_p1" / "G1_lockstep_reproducers"

PLAIN = base_tiles["full_city_with_shield"]
CHAPEL = base_tiles["chapel"]


class FakeState:
    """The 3 attributes the sentinel reads. Deliberately NOT a CarcassonneGameState:
    the sentinel is a pure observer, so anything it touches beyond `board` and
    `placed_meeples` is a bug this fake will surface as an AttributeError."""

    def __init__(self, rows=35, cols=35, players=2):
        self.board = [[None] * cols for _ in range(rows)]
        self.placed_meeples = [[] for _ in range(players)]

    def place(self, row, col, tile=PLAIN):
        self.board[row][col] = tile
        return Coordinate(row=row, column=col)

    def put_monk(self, player, row, col):
        self.placed_meeples[player].append(MeeplePosition(
            meeple_type=MeepleType.NORMAL,
            coordinate_with_side=CoordinateWithSide(
                coordinate=Coordinate(row=row, column=col), side=Side.CENTER)))


def sentinel(rows=35, cols=35, start_row=6, start_col=15) -> ws.GameSentinel:
    return ws.GameSentinel(board_rows=rows, board_cols=cols,
                           start_row=start_row, start_col=start_col)


# --------------------------------------------------------------------------- #
# Face 1 — silent wall denial, by face                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("row,col,face", [
    (0, 15, "drops_row_neg"),     # the PRODUCTION face: 6 rows of headroom
    (34, 15, "drops_row_over"),
    (10, 0, "drops_col_neg"),
    (10, 34, "drops_col_over"),
])
def test_each_wall_face_is_counted_separately(row, col, face):
    st, s = FakeState(), sentinel()
    s.note_placement(st, st.place(row, col), ply=1)
    counts = {k: getattr(s, k) for k in
              ("drops_row_neg", "drops_row_over", "drops_col_neg", "drops_col_over")}
    assert counts[face] == 1, counts
    assert sum(counts.values()) == 1, f"a border placement leaked into another face: {counts}"
    assert s.drop_plies == 1 and s.first_drop_ply == 1
    assert s.any_event is True


def test_the_sentinel_mirrors_the_engines_bounds_check_exactly():
    """`StateUpdater.play_tile` adds a neighbour iff `0 <= nr < n_rows and
    0 <= nc < n_cols`. A corner placement drops TWO neighbours, on two faces."""
    st, s = FakeState(), sentinel()
    s.note_placement(st, st.place(0, 0), ply=0)
    assert s.drops_row_neg == 1 and s.drops_col_neg == 1
    assert s.drop_cells == 2          # (-1,0) and (0,-1), distinct


def test_an_interior_placement_is_silent():
    st, s = FakeState(), sentinel()
    for r in range(5, 30):
        s.note_placement(st, st.place(r, 15), ply=r)
    assert s.any_event is False
    assert s.drop_plies == 0 and s.row_wrap_plies == 0
    assert s.to_dict()["any_event"] is False


def test_distinct_cells_are_deduped_but_exposure_events_are_not():
    """Two tiles side by side on row 0 each drop their own cell above them; a third
    below the first re-drops nothing. `drop_cells` counts CELLS, `drops_*` count
    per-ply exposure — the probe needs both (how much board is lost vs how often)."""
    st, s = FakeState(), sentinel()
    s.note_placement(st, st.place(0, 15), ply=0)
    s.note_placement(st, st.place(0, 16), ply=1)
    assert s.drops_row_neg == 2 and s.drop_cells == 2


# --------------------------------------------------------------------------- #
# Face 2 — the negative-row wrap                                                #
# --------------------------------------------------------------------------- #
def test_row_zero_is_flagged_as_a_wrap_read_not_only_as_a_denial():
    """Row 0 is TWO distinct problems: cells above it are denied (face 1) AND
    `board[-1]` silently reads row 34 instead of raising (face 2). Executes in 68%
    of uniform games and stays benign — which is exactly why it must be counted
    rather than assumed."""
    st, s = FakeState(), sentinel()
    s.note_placement(st, st.place(0, 15), ply=0)
    assert s.row_wrap_plies == 1
    assert s.drops_row_neg == 1
    assert s.min_dist_row_zero == 0


def test_row_one_does_not_wrap():
    st, s = FakeState(), sentinel()
    s.note_placement(st, st.place(1, 15), ply=0)
    assert s.row_wrap_plies == 0 and s.drops_row_neg == 0
    assert s.min_dist_row_zero == 1


# --------------------------------------------------------------------------- #
# Faces 3 + 4 — the fatal edges, and near-fatal exposure                        #
# --------------------------------------------------------------------------- #
def test_the_two_fatal_faces_are_counted_and_kept_apart():
    st, s = FakeState(), sentinel()
    s.note_placement(st, st.place(10, 34), ply=0)   # col 34 -> IndexError, farm path
    s.note_placement(st, st.place(34, 10), ply=1)   # last row -> count_final_scores
    assert s.col_last_plies == 1 and s.row_last_plies == 1
    assert s.min_dist_col_last == 0 and s.min_dist_row_last == 0


def test_near_fatal_exposure_is_measured_before_the_crash():
    """Faces 3-4 are FATAL, so a game that reaches them does not survive to be
    counted. Proximity is the only exposure signal available, and it is the number
    W2-vs-W3 turns on: recentring cuts downward headroom 28 -> 16."""
    st, s = FakeState(), sentinel()
    s.note_placement(st, st.place(33, 15), ply=0)   # 1 row from the last row
    s.note_placement(st, st.place(10, 33), ply=1)   # 1 col from the last col
    assert s.row_last_plies == 0 and s.col_last_plies == 0   # not fatal yet
    assert s.near_fatal_row_plies == 1 and s.near_fatal_col_plies == 1
    assert s.min_dist_row_last == 1 and s.min_dist_col_last == 1
    assert s.any_event is False, "proximity is EXPOSURE, not an event — it must not "\
                                 "trip the A1-a 'zero events' branch"


# --------------------------------------------------------------------------- #
# Face 5 — WindowOverflowError: caught, counted, and the game MARKED            #
# --------------------------------------------------------------------------- #
def test_window_overflow_aborts_loudly_and_leaves_a_record():
    """The capoff lesson (DECISIONS 2026-07-31 Shabbat eve): 16 games died to this
    deterministically, left zero records, and the exclusion was CANDIDATE-CORRELATED
    — the worst possible kind of missing data. A counted, marked abort is the fix."""
    s = sentinel()
    s.note_window_overflow(84, "All 4 legal actions fall outside the 25x25 window")
    assert s.window_overflow == 1
    assert s.aborted is True
    assert "ply84" in s.abort_reason
    assert s.any_event is True
    assert s.to_dict()["aborted"] is True


# --------------------------------------------------------------------------- #
# A2 — cloister deferral and monk pinning (audit R1/R2)                         #
# --------------------------------------------------------------------------- #
def _surround(st, row, col):
    for r in range(row - 1, row + 2):
        for c in range(col - 1, col + 2):
            if (r, c) != (row, col):
                st.place(r, c)


def test_the_cloister_check_waits_for_the_scoring_pass():
    """⚠️ TIMING, and the n=4 smoke caught it. A tile placement puts the state into
    the MEEPLE phase; `remove_meeples_and_collect_points` — the drifting scan — only
    fires at the END of that phase. So AT placement time every completed cloister
    still carries its monk, and a check performed there reports a 100% deferral rate
    that is pure artefact. The check must land after the scoring pass."""
    st, s = FakeState(), sentinel()
    st.place(10, 10, CHAPEL)
    st.put_monk(0, 10, 10)
    _surround(st, 10, 10)
    s.note_placement(st, Coordinate(row=11, column=11), ply=30)
    assert s.cloister_completions == 0, "checked too early — before scoring ran"
    # ... the engine now scores it and takes the monk back
    st.placed_meeples[0].clear()
    s.note_terminal(st)
    assert s.cloister_completions == 1 and s.cloister_deferrals == 0


def test_a_completed_cloister_with_a_monk_still_on_it_is_a_deferral():
    """RF-D-1: the 3x3 scan rebinds its own loop bound, so a completion can fall
    outside the drifted window — the 9 points arrive at final scoring, the MONK does
    not. Read from the outcome: the engine removes the monk whenever it DOES score
    one, so a monk still sitting on a full 3x3 AFTER scoring ran is a miss."""
    st, s = FakeState(), sentinel()
    st.place(10, 10, CHAPEL)
    st.put_monk(0, 10, 10)
    _surround(st, 10, 10)
    s.note_placement(st, Coordinate(row=11, column=11), ply=30)
    s.note_terminal(st)               # flushes the check, post-scoring
    assert s.cloister_completions == 1
    assert s.cloister_deferrals == 1
    assert s.monk_pins_terminal == 1


def test_an_incomplete_cloister_is_neither():
    st, s = FakeState(), sentinel()
    st.place(10, 10, CHAPEL)
    st.put_monk(0, 10, 10)
    _surround(st, 10, 10)
    st.board[9][9] = None             # one short of 9
    s.note_placement(st, Coordinate(row=11, column=11), ply=30)
    s.note_terminal(st)
    assert s.cloister_completions == 0 and s.cloister_deferrals == 0
    assert s.monk_pins_terminal == 0


def test_a_pinned_monk_is_one_event_not_one_per_ply():
    """A monk pinned for 30 plies is ONE deferral. Without the dedup the probe's
    'deferrals per game' would read as a function of when in the game it happened."""
    st, s = FakeState(), sentinel()
    st.place(10, 10, CHAPEL)
    st.put_monk(0, 10, 10)
    _surround(st, 10, 10)
    for ply in range(30, 40):
        s.note_placement(st, Coordinate(row=11, column=11), ply=ply)
    s.note_terminal(st)
    assert s.cloister_deferrals == 1


def test_a_deferral_that_later_self_heals_is_still_recorded_as_a_deferral():
    """The audit notes a partial, unreliable self-heal: a LATER placement adjacent
    to the cloister can belatedly re-score it. The monk was still pinned in the
    meantime, so the DEFERRAL happened — which is why the probe reports deferral
    events AND terminal pins, and why they are allowed to differ."""
    st, s = FakeState(), sentinel()
    st.place(10, 10, CHAPEL)
    st.put_monk(0, 10, 10)
    _surround(st, 10, 10)
    s.note_placement(st, Coordinate(row=11, column=11), ply=30)
    s.note_placement(st, Coordinate(row=20, column=20), ply=31)   # flush: deferred
    st.placed_meeples[0].clear()                                  # healed later
    s.note_terminal(st)
    assert s.cloister_deferrals == 1
    assert s.monk_pins_terminal == 0


def test_monks_pinned_at_terminal_are_counted_at_game_end():
    """The number R2 is worth: a permanent -1 on a supply of 7, invisible to every
    score-based check."""
    st, s = FakeState(), sentinel()
    st.place(10, 10, CHAPEL)
    st.put_monk(0, 10, 10)
    _surround(st, 10, 10)
    st.place(20, 20, CHAPEL)          # incomplete, its monk is legitimately there
    st.put_monk(1, 20, 20)
    s.note_terminal(st)
    assert s.monk_pins_terminal == 1


def test_a_border_cloister_is_never_called_complete():
    """`chapel_or_flowers_points` is itself unguarded — at row 0 it WRAPS. The
    sentinel guards instead, which can only UNDER-count deferrals. Stated here so
    the conservative direction is a decision, not an accident."""
    st, s = FakeState(), sentinel()
    st.place(0, 10, CHAPEL)
    st.put_monk(0, 0, 10)
    _surround(st, 0, 10)              # the row -1 cells simply cannot exist
    s.note_placement(st, Coordinate(row=1, column=11), ply=30)
    s.note_terminal(st)
    assert s.cloister_completions == 0


# --------------------------------------------------------------------------- #
# Re-pricing a different geometry (the W2-vs-W3 decision input)                 #
# --------------------------------------------------------------------------- #
def test_reprice_reproduces_the_as_played_counters_on_the_same_grid():
    """Sanity floor: re-pricing the grid a game was actually played on must return
    what the sentinel counted live. Without this the re-priced columns of the A1-a
    report are unfalsifiable."""
    st, s = FakeState(), sentinel()
    for r, c in [(0, 15), (1, 15), (2, 15), (10, 34), (34, 10)]:
        s.note_placement(st, st.place(r, c), ply=0)
    rp = ws.reprice(s.rel_coords, 6, 15, 35, 35)
    assert rp["drops_row_neg"] == s.drops_row_neg
    assert rp["row_wrap_plies"] == s.row_wrap_plies
    assert rp["col_last_plies"] == s.col_last_plies
    assert rp["row_last_plies"] == s.row_last_plies


def test_reprice_shows_recentring_trading_one_face_for_another():
    """Spec T2, made concrete. A game that hugs the top wall at row 6 is clean at
    row 18; a game that runs 20 rows DOWN is clean at row 6 and hits the fatal
    last-row face at row 18. Recentring MOVES risk — that is why W4 is a mandatory
    companion to W2, not an alternative to it."""
    upward = [(-6, 0), (-6, 1), (-5, 0)]        # 6 rows above the start tile
    assert ws.reprice(upward, 6, 15)["drops_row_neg"] > 0
    assert ws.reprice(upward, 18, 15)["any_event"] is False

    downward = [(16, 0), (16, 1)]               # 16 rows below the start tile
    assert ws.reprice(downward, 6, 15)["any_event"] is False
    assert ws.reprice(downward, 18, 15)["row_last_plies"] > 0


def test_reprice_flags_a_trajectory_that_does_not_fit_at_all():
    assert ws.reprice([(60, 0)], 6, 15, 35, 35)["fits"] is False
    assert ws.reprice([(60, 0)], 71, 71, 143, 143)["fits"] is True


# --------------------------------------------------------------------------- #
# Aggregation                                                                   #
# --------------------------------------------------------------------------- #
def test_aggregate_separates_per_game_incidence_from_per_event_totals():
    """The A1-a decision is per-GAME ('how often does champion play hit the wall');
    the exposure question is per-EVENT. Reporting only one of them would answer the
    wrong question."""
    st = FakeState()
    a = sentinel()
    for c in (15, 16, 17):
        a.note_placement(st, st.place(0, c), ply=c)
    b = sentinel()
    b.note_placement(FakeState(), Coordinate(row=10, column=10), ply=0)
    agg = ws.aggregate([a.to_dict(), b.to_dict()])
    assert agg["games"] == 2
    assert agg["games_with_drops_row_neg"] == 1     # incidence
    assert agg["drops_row_neg"] == 3                # exposure
    assert agg["games_any_event"] == 1


def test_aggregate_counts_aborted_games_in_the_denominator():
    a = sentinel()
    a.note_window_overflow(84)
    agg = ws.aggregate([a.to_dict(), sentinel().to_dict()])
    assert agg["games"] == 2 and agg["games_aborted"] == 1
    assert agg["window_overflow"] == 1


def test_aggregate_keeps_the_extreme_span_and_the_closest_approach():
    st = FakeState()
    a = sentinel()
    a.note_placement(st, st.place(2, 15), ply=0)     # 4 rows above the start tile
    b = sentinel()
    b.note_placement(FakeState(), Coordinate(row=30, column=20), ply=0)
    agg = ws.aggregate([a.to_dict(), b.to_dict()])
    assert agg["rel_min_row"] == -4 and agg["rel_max_row"] == 24
    assert agg["min_dist_row_zero"] == 2
    assert agg["min_dist_row_last"] == 4             # 34 - 30


# --------------------------------------------------------------------------- #
# The G1 reproducers as ground truth for the fatal faces                        #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not REPRO.is_dir(), reason="G1 reproducers not present")
def test_the_g1_col34_reproducers_classify_as_the_fatal_column_face():
    """4/4 G1-fuzz games that reached col 34 died there (`board[..][35]`,
    IndexError). Their recorded `last_tile` must land on the col-last face — and
    the first of them is at (0, 34), i.e. the row-wrap and the fatal-column faces
    AT ONCE, which is precisely why they are separate counters."""
    files = sorted(REPRO.glob("engine_error_*.json"))
    assert files, "expected the col-34 reproducers"
    for f in files:
        d = json.loads(f.read_text())
        row, col = d["detail"]["last_tile"]
        assert col == 34, f"{f.name}: expected the col-34 face, got col {col}"
        s = sentinel()
        s.note_placement(FakeState(), Coordinate(row=row, column=col), ply=d["ply"])
        assert s.col_last_plies == 1, f.name
        assert s.min_dist_col_last == 0
        if row == 0:
            assert s.row_wrap_plies == 1 and s.drops_row_neg == 1


@pytest.mark.skipif(not REPRO.is_dir(), reason="G1 reproducers not present")
def test_the_g1_window_overflow_reproducer_is_a_board_size_proof_face():
    """`window_origin (-11, 2)` — a NEGATIVE row origin. No board change of any size
    fixes this: the 25x25 centroid window is a REPRESENTATION cap (spec J4), so the
    sentinel reports it as its own face rather than folding it into the wall."""
    f = next(REPRO.glob("window_overflow_*.json"), None)
    assert f is not None
    d = json.loads(f.read_text())
    assert d["detail"]["window_size"] == 25
    s = sentinel()
    s.note_window_overflow(d["ply"], d["detail"]["python_error"])
    assert s.window_overflow == 1 and s.aborted
    # and it is NOT attributed to any wall face
    assert (s.drops_row_neg, s.col_last_plies, s.row_last_plies) == (0, 0, 0)
