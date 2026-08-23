//! Board-bounds regression pins (2026-08-23, `panic-triage`).
//!
//! THE BUG.  `board_direct` mirrors CPython's `game_state.board[row][column]`,
//! negative-index wrap included.  Three readers reach it with a coordinate
//! stepped ONE cell off the tile they started from —
//!
//!   * `cities_for_position`, via `CityUtil.opposite_edge`
//!   * `farm_for_position`,   via `FarmUtil.opposite_edge`
//!   * `chapel_or_flowers_points`, via its 3x3 window
//!
//! — so a region touching the LAST row/column asks for index 35 on a 35-cell
//! axis.  CPython raises `IndexError` there and this port faithfully panicked,
//! which killed three live b32v64 production games on 2026-08-22 (deck seeds
//! 140000001096 / 140000001115 / 140000001286).  Each of the three seeds landed
//! on a DIFFERENT one of the three readers, which is why the pin below exercises
//! all three rather than only the one that happened to be reported first.
//!
//! WHAT IS PINNED.  Off-board reads answer "no tile", both axes, both ends.
//! WHAT IS DELIBERATELY PINNED **UNCHANGED**: the `-1` wrap.  It is a scoring
//! semantic of the engine of record and moving it would move the rules epoch —
//! see `wrap_at_the_near_edge_is_deliberately_unchanged`.
//!
//! `set_tile` gets its own pins because its failure mode is the dangerous one: a
//! row-major write with an out-of-range COLUMN lands on a different in-bounds
//! cell, silently.

use super::*;

const LAST_ROW: i32 = BOARD_ROWS - 1; // 34
const LAST_COL: i32 = BOARD_COLS - 1; // 34

fn base(description: &str) -> u16 {
    tiles::generated::BASE_TILES
        .iter()
        .position(|t| t.description == description)
        .unwrap_or_else(|| panic!("the base deck has a {description:?} tile")) as u16
}

/// The rotation of `description` whose city faces `side`.  Asked for rather than
/// hard-coded so the pin cannot rot against a re-generated tile table.
fn rot_with_city_facing(description: &str, side: Side) -> u8 {
    (0..4u8)
        .find(|&rot| {
            tiles::tile(tile_id(base(description), rot))
                .city_sides_set
                .contains(&side)
        })
        .unwrap_or_else(|| panic!("some rotation of {description:?} faces {side:?}"))
}

/// A board with a single tile, and nothing else — so the only thing any scan can
/// run into is the wall.
fn one_tile(description: &str, rot: u8, coord: Coord) -> GameState {
    let mut st = GameState::from_deck_with_start(Vec::new(), Coord::new(6, 15));
    st.set_tile(coord, tile_id(base(description), rot));
    st.placed_coords.insert((coord.row, coord.col));
    st.scores = [0, 0];
    st
}

// --------------------------------------------------------------------------- //
// The three readers that crashed live.                                          //
// --------------------------------------------------------------------------- //

/// Seed 140000001115 / 140000001286's frame: `cities_for_position` ->
/// `board_direct(35, col)`.  `city_bottom_grass` puts a city on the BOTTOM edge,
/// so on the last row `CityUtil.opposite_edge` steps straight off the board.
#[test]
fn find_city_on_the_last_row_does_not_panic() {
    let coord = Coord::new(LAST_ROW, 15);
    let rot = rot_with_city_facing("city_bottom_grass", Side::Bottom);
    let st = one_tile("city_bottom_grass", rot, coord);

    let city = st.find_city((coord.row, coord.col, Side::Bottom));

    assert!(
        city.positions
            .contains(&(coord.row, coord.col, Side::Bottom)),
        "the seed side must still be in the component"
    );
    assert!(
        !city.finished,
        "a city whose only open edge points off the board is UNFINISHED — the \
         wall is not a neighbour that closes it"
    );
}

/// The same reader on the other axis: rotate the city onto the RIGHT edge and
/// put the tile on the last column.
#[test]
fn find_city_on_the_last_column_does_not_panic() {
    let coord = Coord::new(15, LAST_COL);
    let rot = rot_with_city_facing("city_bottom_grass", Side::Right);
    let st = one_tile("city_bottom_grass", rot, coord);

    let city = st.find_city((coord.row, coord.col, Side::Right));

    assert!(city
        .positions
        .contains(&(coord.row, coord.col, Side::Right)));
    assert!(!city.finished);
}

/// Seed 140000001096's frame: `find_farm` -> `farm_for_position` ->
/// `board_direct(35, col)`.  Every base tile has farm connections on its grass
/// edges, so a plain chapel on the last row steps off the board on slot 0.
#[test]
fn find_farm_on_the_last_row_does_not_panic() {
    let coord = Coord::new(LAST_ROW, 15);
    let st = one_tile("chapel", 0, coord);

    let farm = st.find_farm(FarmNode { coord, slot: 0 });

    assert_eq!(
        farm.nodes,
        vec![FarmNode { coord, slot: 0 }],
        "an isolated tile's farm is itself — the off-board neighbours contribute \
         nothing, they do not abort the walk"
    );
}

#[test]
fn find_farm_on_the_last_column_does_not_panic() {
    let coord = Coord::new(15, LAST_COL);
    let st = one_tile("chapel", 0, coord);
    let farm = st.find_farm(FarmNode { coord, slot: 0 });
    assert_eq!(farm.nodes, vec![FarmNode { coord, slot: 0 }]);
}

/// The third reader: the cloister 3x3 reaches row 35 from row 34.
#[test]
fn chapel_scan_on_the_last_row_does_not_panic() {
    let coord = Coord::new(LAST_ROW, 15);
    let st = one_tile("chapel", 0, coord);

    assert_eq!(
        st.chapel_or_flowers_points(coord),
        1,
        "only the cloister itself is placed; the three off-board cells count as \
         empty, exactly as the three in-board empty ones do"
    );
}

#[test]
fn chapel_scan_on_the_last_column_does_not_panic() {
    let coord = Coord::new(15, LAST_COL);
    let st = one_tile("chapel", 0, coord);
    assert_eq!(st.chapel_or_flowers_points(coord), 1);
}

/// The whole-game entry point the live crash actually came through: move
/// generation on a last-row tile (`possible_actions` -> farmer positions ->
/// `find_farm`).
#[test]
fn move_generation_on_the_last_row_does_not_panic() {
    let coord = Coord::new(LAST_ROW, 15);
    let mut st = one_tile("chapel", 0, coord);
    st.phase = Phase::Meeples;
    st.last_tile_action = Some(TileAction {
        tile: tile_id(base("chapel"), 0),
        coord,
        rotations: 0,
    });

    let actions = st.possible_actions();

    assert!(
        !actions.is_empty(),
        "MEEPLES phase always offers at least a Pass"
    );
}

// --------------------------------------------------------------------------- //
// The boundary itself.                                                          //
// --------------------------------------------------------------------------- //

#[test]
fn out_of_range_indices_read_as_empty_on_both_axes_and_both_ends() {
    let st = one_tile("chapel", 0, Coord::new(15, 15));
    for (row, col) in [
        (BOARD_ROWS, 15),      // the live crash: index 35 on a len-35 axis
        (15, BOARD_COLS),      // its column twin
        (BOARD_ROWS + 40, 15), // far past the end
        (-BOARD_ROWS - 1, 15), // past the far end of the WRAP, not merely negative
        (15, -BOARD_COLS - 1),
    ] {
        assert_eq!(
            st.board_direct(row, col),
            None,
            "board_direct({row}, {col}) must read as 'no tile', not panic"
        );
    }
}

/// ⛔ THE WRAP IS NOT PART OF THE FIX.  `board[-1]` reads the LAST row in
/// CPython, every recorded game was produced under that, and this pin exists so
/// a future "tidy up the bounds handling" cannot quietly change the rules epoch.
///
/// It is also the honest statement of the residual risk: a read at row `-1`
/// returns a REAL tile whenever the far row is occupied, and nothing about that
/// is loud.  It needs the board to occupy BOTH extreme rows (or columns) at
/// once, which is why it has never been observed — but it is a property of the
/// corpus, not of the code.
#[test]
fn wrap_at_the_near_edge_is_deliberately_unchanged() {
    let far = Coord::new(LAST_ROW, 15);
    let st = one_tile("chapel", 0, far);
    let tid = tile_id(base("chapel"), 0);

    assert_eq!(
        st.board_direct(-1, 15),
        Some(tid),
        "row -1 still wraps to row 34 (CPython semantics, load-bearing)"
    );
    assert_eq!(
        st.board_direct(-BOARD_ROWS, 15),
        None,
        "row -35 wraps to row 0"
    );

    let far_col = Coord::new(15, LAST_COL);
    let st = one_tile("chapel", 0, far_col);
    assert_eq!(
        st.board_direct(15, -1),
        Some(tid),
        "column -1 still wraps to column 34"
    );
}

// --------------------------------------------------------------------------- //
// `set_tile` — the silent-write path.                                           //
// --------------------------------------------------------------------------- //

/// The dangerous one.  `(row, BOARD_COLS)` is row-major-equal to `(row + 1, 0)`,
/// so before the guard this wrote a real tile into a real cell that no caller
/// asked about, with no panic and no error.
#[test]
#[should_panic(expected = "outside the 35x35 board")]
fn set_tile_refuses_a_column_that_would_alias_the_next_row() {
    let mut st = GameState::from_deck_with_start(Vec::new(), Coord::new(6, 15));
    st.set_tile(Coord::new(10, BOARD_COLS), tile_id(base("chapel"), 0));
}

#[test]
#[should_panic(expected = "outside the 35x35 board")]
fn set_tile_refuses_a_negative_column_that_would_alias_the_previous_row() {
    let mut st = GameState::from_deck_with_start(Vec::new(), Coord::new(6, 15));
    st.set_tile(Coord::new(10, -1), tile_id(base("chapel"), 0));
}

/// The banked-fixture case: a row shifted off the board entirely.  This one
/// always crashed; the pin is that it crashes with a message that NAMES the
/// coordinate instead of `index out of bounds: len 1225, index 18446744073709551560`.
#[test]
#[should_panic(expected = "outside the 35x35 board")]
fn set_tile_refuses_a_row_off_the_board() {
    let mut st = GameState::from_deck_with_start(Vec::new(), Coord::new(6, 15));
    st.set_tile(Coord::new(-2, 14), tile_id(base("chapel"), 0));
}
