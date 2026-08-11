//! F9-A2 — the Rust twin of `tests/test_cloister_scan_fix.py`.
//!
//! The audit's deterministic control/trigger pair (RF-D-1): a cloister with a
//! monk at (10, 10), completed by a placement at (9, 10).
//!
//!   control  nothing to the right of the 3x3 -> the drifting scan reaches
//!            (10, 10) anyway; both conventions score.
//!   trigger  tiles also at (8, 11) and (9, 12) -> scan row 9 drifts to cols
//!            10-12 and row 10 to cols 11-13, so (10, 10) is never visited.
//!            Flags OFF that must stay a miss (the quirk the port carries
//!            verbatim, mutation-proven load-bearing at G1); flags ON it scores
//!            at the true ply and the monk goes back to supply.

use super::*;

const CLOISTER: Coord = Coord::new(10, 10);
const PLACEMENT: Coord = Coord::new(9, 10);
const TRIGGER: [(i32, i32); 2] = [(8, 11), (9, 12)];

/// A plain "chapel" tile: four grass edges, cloister centre.  No cities, no
/// roads, no farmers -> the only scoring event possible on this board is the
/// cloister one under examination.
fn chapel() -> TileId {
    let base = tiles::generated::BASE_TILES
        .iter()
        .position(|t| t.description == "chapel")
        .expect("the base deck has a plain chapel") as u16;
    tile_id(base, 0)
}

fn fixture(trigger: bool, fix: bool) -> GameState {
    let mut st = GameState::from_deck_with_start(Vec::new(), Coord::new(6, 15));
    st.cloister_scan_fix = fix;
    let tid = chapel();
    for r in (CLOISTER.row - 1)..=(CLOISTER.row + 1) {
        for c in (CLOISTER.col - 1)..=(CLOISTER.col + 1) {
            st.set_tile(Coord::new(r, c), tid);
        }
    }
    if trigger {
        for (r, c) in TRIGGER {
            st.set_tile(Coord::new(r, c), tid);
        }
    }
    st.scores = [0, 0];
    st.meeples = [6, 7]; // player 0 has the monk on the board
    st.placed_meeples = [
        vec![MeeplePosition {
            meeple_type: MeepleType::Normal,
            coord: CLOISTER,
            side: Side::Center,
        }],
        Vec::new(),
    ];
    st
}

#[test]
fn control_scores_and_returns_the_monk_under_both_conventions() {
    for fix in [false, true] {
        let mut st = fixture(false, fix);
        st.remove_meeples_and_collect_points(PLACEMENT);
        assert_eq!(st.scores, [9, 0], "fix={fix}");
        assert_eq!(st.meeples, [7, 7], "fix={fix}");
        assert!(st.placed_meeples[0].is_empty(), "fix={fix}");
        // The legacy walk reached (10, 10) too: nothing was accelerated.
        assert_eq!(st.cloister_completions_accelerated, 0, "fix={fix}");
    }
}

#[test]
fn trigger_flags_off_misses_the_completion_and_pins_the_monk() {
    let mut st = fixture(true, false);
    st.remove_meeples_and_collect_points(PLACEMENT);
    assert_eq!(st.scores, [0, 0]);
    assert_eq!(st.meeples, [6, 7]);
    assert_eq!(st.placed_meeples[0].len(), 1);
    assert_eq!(st.placed_meeples[0][0].coord, CLOISTER);
    assert_eq!(st.cloister_completions_accelerated, 0);
}

#[test]
fn trigger_flags_on_scores_at_the_true_ply_and_frees_the_monk() {
    let mut st = fixture(true, true);
    st.remove_meeples_and_collect_points(PLACEMENT);
    assert_eq!(st.scores, [9, 0]);
    assert_eq!(st.meeples, [7, 7]);
    assert!(st.placed_meeples[0].is_empty());
    assert_eq!(st.cloister_completions_accelerated, 1);
}

#[test]
fn the_endgame_pass_pays_the_same_total_either_way() {
    // Points are DEFERRED, not lost: `count_final_scores` awards 9 for a monk
    // still sitting on a completed cloister.  The flag moves the ply and the
    // meeple supply, never the total.
    let mut off = fixture(true, false);
    off.remove_meeples_and_collect_points(PLACEMENT);
    assert_eq!(off.scores, [0, 0]);
    off.count_final_scores();
    assert_eq!(off.scores, [9, 0]);

    let mut on = fixture(true, true);
    on.remove_meeples_and_collect_points(PLACEMENT);
    assert_eq!(on.scores, [9, 0]);
    on.count_final_scores();
    assert_eq!(on.scores, [9, 0], "the monk was already returned");
}

#[test]
fn the_legacy_scan_cell_enumeration_matches_the_audit() {
    let st = fixture(true, true);
    let visited = st.legacy_scan_cells(PLACEMENT);
    assert!(!visited.contains(&(10, 10)), "the trigger's whole point");
    let expect: HashSet<(i32, i32)> = [(8, 11), (9, 10), (9, 11), (9, 12), (10, 11)]
        .into_iter()
        .collect();
    assert_eq!(visited, expect);

    assert!(fixture(false, true)
        .legacy_scan_cells(PLACEMENT)
        .contains(&(10, 10)));
}

#[test]
fn a_clone_carries_the_convention_and_the_counter() {
    let mut st = fixture(true, true);
    st.remove_meeples_and_collect_points(PLACEMENT);
    let c = st.clone();
    assert!(c.cloister_scan_fix);
    assert_eq!(c.cloister_completions_accelerated, 1);
    assert!(!fixture(true, false).clone().cloister_scan_fix);
}

#[test]
fn the_default_config_is_flags_off() {
    assert!(!crate::game::GameConfig::default().cloister_scan_fix);
    let g = crate::game::Game::from_deck(Vec::new());
    assert!(!g.state.cloister_scan_fix);
    assert_eq!(g.state.cloister_completions_accelerated, 0);
}
