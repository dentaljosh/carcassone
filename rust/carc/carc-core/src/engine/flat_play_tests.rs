//! Engine follow-on A — the FLAT PLAY TABLE conversion: correctness gates.
//!
//! [`super::fits`] and ~20 `tiles::tile()` reads across `engine::mod` (plus 8
//! in `leaf::mod`) were converted to [`crate::tiles::TilePlayFlat`] /
//! [`crate::tiles::TileFlat`].  The data layer is pinned by
//! `tiles::tests::play_registry_matches_the_object_registry` (every field, all
//! 128 rotated tiles, both R9 flag states).  What is left to pin is the CODE:
//!
//! | gate | what it refuses |
//! |---|---|
//! | [`fits_flat_matches_fits_on_every_single_neighbour_board`] | the mask predicate, exhaustively, one neighbour at a time |
//! | [`fits_flat_matches_fits_on_randomized_quadruples`] | the mask predicate on full 4-neighbour boards |
//! | [`possible_playing_positions_is_unchanged_across_a_corpus`] | the converted call site, in situ, ORDER included |
//! | [`the_converted_reads_agree_with_the_object_registry_in_situ`] | every other converted read, walked over real boards |
//!
//! Whole-game action identity vs the pre-change build is a separate, external
//! gate (`examples/flat_play_gate.rs`) because it needs two builds.

use super::*;
use crate::game::Game;
use crate::tiles::{self, Side, TileId};

/// A reproducible picker.  Not `rand` — the corpus must be a constant of the
/// gate, re-derivable from this file alone.  (Same LCG as the L1a gates.)
struct Lcg(u64);
impl Lcg {
    fn new(seed: u64) -> Self {
        Lcg(seed
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407))
    }
    fn next(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.0 >> 33
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() as usize) % n.max(1)
    }
}

/// Every position of one randomly-played game, visited in order.
fn walk_game(seed: u64, mut visit: impl FnMut(&Game)) {
    let mut g = Game::from_seed(&seed.to_string());
    let mut rng = Lcg::new(seed);
    let mut guard = 0usize;
    while !g.state.is_terminated() {
        guard += 1;
        assert!(guard < 400, "game {seed} did not terminate");
        visit(&g);
        let legal = g.legal_actions();
        assert!(!legal.is_empty(), "no legal action at a non-terminal state");
        let a = legal[rng.below(legal.len())];
        g.advance(a).unwrap();
    }
}

// ── (a) the predicate itself ─────────────────────────────────────────────── //

/// Exhaustive over `(center, one occupied neighbour)`: 128 centers x 4 slots x
/// 128 neighbours = 65,536 boards, every one of them compared object-vs-flat.
///
/// One neighbour at a time is the shape that isolates a per-side bug — a wrong
/// opposite-side in the mask arithmetic shows up here and nowhere else, because
/// a full board masks it behind the other three conjuncts.
#[test]
fn fits_flat_matches_fits_on_every_single_neighbour_board() {
    let reg = tiles::registry();
    let preg = tiles::play_registry();
    let n = reg.len();
    let mut compared = 0usize;
    for c in 0..n {
        for slot in 0..4usize {
            for nb in 0..n {
                let mut sides: [Option<TileId>; 4] = [None; 4];
                sides[slot] = Some(nb as TileId);
                let (top, right, bottom, left) = (sides[0], sides[1], sides[2], sides[3]);
                let want = fits(&reg[c], top, bottom, left, right);
                let got = fits_flat(&preg[c], top, bottom, left, right);
                assert_eq!(
                    want, got,
                    "center {} rot {} vs neighbour {} rot {} in slot {slot}",
                    reg[c].description, reg[c].rot, reg[nb].description, reg[nb].rot
                );
                compared += 1;
            }
        }
    }
    assert_eq!(compared, n * 4 * n, "corpus size drifted");
    assert!(compared >= 65_536, "corpus too small: {compared}");
}

/// 200,000 randomized 4-neighbour boards (each slot independently empty or any
/// rotated tile), object vs flat.  Both answers are exercised: the test refuses
/// a corpus that is all-`false` or all-`true`.
#[test]
fn fits_flat_matches_fits_on_randomized_quadruples() {
    let reg = tiles::registry();
    let preg = tiles::play_registry();
    let n = reg.len();
    let mut rng = Lcg::new(0xf1a7_c0de_2026_0830);
    let mut n_true = 0usize;
    let mut n_false = 0usize;
    // 1 in 5 slots empty, so most boards have all four occupied.
    fn pick(rng: &mut Lcg, n: usize) -> Option<TileId> {
        if rng.below(5) == 0 {
            None
        } else {
            Some(rng.below(n) as TileId)
        }
    }
    for _ in 0..200_000 {
        let c = rng.below(n);
        let top = pick(&mut rng, n);
        let right = pick(&mut rng, n);
        let bottom = pick(&mut rng, n);
        let left = pick(&mut rng, n);
        let want = fits(&reg[c], top, bottom, left, right);
        let got = fits_flat(&preg[c], top, bottom, left, right);
        assert_eq!(want, got, "center {} rot {}", reg[c].description, reg[c].rot);
        if want {
            n_true += 1
        } else {
            n_false += 1
        }
    }
    assert!(n_true > 1_000, "corpus never says fits: {n_true}");
    assert!(n_false > 1_000, "corpus never says does-not-fit: {n_false}");
}

// ── (b) the converted call site, in situ ─────────────────────────────────── //

/// The flattened [`GameState::possible_playing_positions`] must return the same
/// `(coord, rotation)` list — same elements AND the same ORDER — as the object
/// path, at every tile-phase position of a randomized corpus.
///
/// Order is asserted because it is load-bearing: the action space and every
/// tie-break downstream read this list positionally.
#[test]
fn possible_playing_positions_is_unchanged_across_a_corpus() {
    let reg = tiles::registry();
    let mut n_positions = 0usize;
    for seed in 28_400_000_000u64..28_400_000_020 {
        walk_game(seed, |g| {
            let base = match g.state.next_tile {
                None => return,
                Some(b) => b,
            };
            if g.state.phase != Phase::Tiles || g.state.empty_board() {
                return;
            }
            // The object path, rebuilt here verbatim from the pre-change body.
            let mut want: Vec<(Coord, u8)> = Vec::new();
            for &(row, col) in &g.state.open_positions {
                for turns in 0u8..4 {
                    let top = g.state.get_tile(row - 1, col);
                    let bottom = g.state.get_tile(row + 1, col);
                    let left = g.state.get_tile(row, col - 1);
                    let right = g.state.get_tile(row, col + 1);
                    if fits(
                        &reg[tile_id(base, turns) as usize],
                        top,
                        bottom,
                        left,
                        right,
                    ) {
                        want.push((Coord::new(row, col), turns));
                    }
                }
            }
            let got = g.state.possible_playing_positions(base);
            assert_eq!(want, got, "seed {seed}: playing positions diverged");
            n_positions += 1;
        });
    }
    assert!(n_positions > 500, "corpus too small: {n_positions}");
}

/// Every OTHER converted read, walked over real boards: for each placed tile
/// and each placed meeple, the flat answer must equal the object answer.
///
/// This is the site-by-site receipt.  It is deliberately dumb — it re-derives
/// each quantity from `tiles::tile()` and compares — so it fails if any single
/// conversion in `engine::mod` / `leaf::mod` picked the wrong field, the wrong
/// order, or the wrong `u8` round-trip.
#[test]
fn the_converted_reads_agree_with_the_object_registry_in_situ() {
    let mut n_tiles = 0usize;
    for seed in 28_400_100_000u64..28_400_100_012 {
        walk_game(seed, |g| {
            for &(r, c) in &g.state.placed_coords {
                let tid = g.state.board_direct(r, c).unwrap();
                let o = tiles::tile(tid);
                let f = tiles::tile_flat(tid);
                let p = tiles::tile_play(tid);
                n_tiles += 1;

                // count_city_points / count_road_points / count_city_points
                assert_eq!(p.has_inn, !o.inn.is_empty());
                assert_eq!(p.shield, o.shield);
                // remove_meeples_and_collect_points / possible_meeple_actions
                assert_eq!(p.chapel, o.chapel);
                assert_eq!(p.flowers, o.flowers);
                // count_final_scores / find_cities / find_roads /
                // possible_meeple_positions / every leaf term
                for &s in &tiles::SIDE_FROM_U8 {
                    assert_eq!(p.get_type(s), o.get_type(s), "get_type {s:?}");
                }
                // cities_for_position
                assert_eq!(f.n_city_groups as usize, o.city.len());
                for (gi, group) in o.city.iter().enumerate() {
                    let flat: Vec<Side> = f
                        .city_group(gi)
                        .iter()
                        .map(|&b| tiles::SIDE_FROM_U8[b as usize])
                        .collect();
                    assert_eq!(&flat, group, "city group {gi}");
                }
                // outgoing_roads_for_position
                assert_eq!(f.n_road as usize, o.road.len());
                for (i, &(a, b)) in o.road.iter().enumerate() {
                    assert_eq!(tiles::SIDE_FROM_U8[f.road[2 * i] as usize], a);
                    assert_eq!(tiles::SIDE_FROM_U8[f.road[2 * i + 1] as usize], b);
                }
                // farm_for_position / find_farm / find_farm_by_coordinate /
                // farm_find_meeples / possible_farmer_positions /
                // count_farm_points
                assert_eq!(f.n_farms as usize, o.farms.len());
                for (slot, fc) in o.farms.iter().enumerate() {
                    let ff = &f.farms[slot];
                    let tconn: Vec<_> = ff
                        .tconn()
                        .iter()
                        .map(|&b| tiles::FARMER_SIDE_FROM_U8[b as usize])
                        .collect();
                    assert_eq!(tconn, fc.tile_connections, "farm {slot} tconn");
                    let fpos: Vec<Side> = ff
                        .fpos()
                        .iter()
                        .map(|&b| tiles::SIDE_FROM_U8[b as usize])
                        .collect();
                    assert_eq!(fpos, fc.farmer_positions, "farm {slot} fpos");
                    let csides: Vec<Side> = ff
                        .csides()
                        .iter()
                        .map(|&b| tiles::SIDE_FROM_U8[b as usize])
                        .collect();
                    assert_eq!(csides, fc.city_sides, "farm {slot} csides");
                }
            }
        });
    }
    assert!(n_tiles > 2_000, "corpus too small: {n_tiles}");
}

/// `bag_stats`' `city_edges` shortcut, over the whole deck in both flag states.
#[test]
fn city_edges_equals_the_summed_city_group_lengths() {
    for r9 in [false, true] {
        for (o, p) in tiles::registry_for(r9)
            .iter()
            .zip(tiles::play_registry_for(r9).iter())
        {
            let want: usize = o.city.iter().map(|g| g.len()).sum();
            assert_eq!(p.city_edges as usize, want, "{} rot {}", o.description, o.rot);
        }
    }
}
