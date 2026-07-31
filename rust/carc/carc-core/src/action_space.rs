//! Port of `src/carcassonne_ai/action_space.py` + the window-offset half of
//! `src/carcassonne_ai/board_repr.py`.
//!
//! Layout for window size `W` (identical integers to the Python module):
//!
//! ```text
//!   0 .. W*W*4 - 1     TileAction     idx = (wr * W + wc) * 4 + rotation
//!   W*W*4              tile-phase Pass
//!   W*W*4 + 1 ..  + 5  MeepleAction NORMAL on {TOP,RIGHT,BOTTOM,LEFT,CENTER}
//!   W*W*4 + 6 ..  + 9  MeepleAction FARMER on {TL,TR,BL,BR}
//!   W*W*4 + 10         meeple-phase Pass
//! ```

use crate::engine::{Action, Coord, MeepleAction, MeepleType, Phase, TileAction};
use crate::tiles::{tile_id, Side};

pub const DEFAULT_WINDOW_SIZE: i32 = 25;
pub const N_ROTATIONS: i32 = 4;

pub const NORMAL_SIDES: [Side; 5] = [
    Side::Top,
    Side::Right,
    Side::Bottom,
    Side::Left,
    Side::Center,
];
pub const FARMER_SIDES: [Side; 4] = [
    Side::TopLeft,
    Side::TopRight,
    Side::BottomLeft,
    Side::BottomRight,
];

#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub struct WindowOffset {
    pub origin_row: i32,
    pub origin_col: i32,
    pub size: i32,
}

impl WindowOffset {
    #[inline]
    pub fn to_window(&self, c: Coord) -> Option<(i32, i32)> {
        let (wr, wc) = (c.row - self.origin_row, c.col - self.origin_col);
        if wr >= 0 && wr < self.size && wc >= 0 && wc < self.size {
            Some((wr, wc))
        } else {
            None
        }
    }

    #[inline]
    pub fn to_engine(&self, wr: i32, wc: i32) -> Coord {
        Coord::new(wr + self.origin_row, wc + self.origin_col)
    }
}

#[inline]
pub fn tile_action_count(w: i32) -> i32 {
    w * w * N_ROTATIONS
}
#[inline]
pub fn tile_pass_index(w: i32) -> i32 {
    tile_action_count(w)
}
#[inline]
pub fn meeple_normal_base(w: i32) -> i32 {
    tile_pass_index(w) + 1
}
#[inline]
pub fn meeple_farmer_base(w: i32) -> i32 {
    meeple_normal_base(w) + NORMAL_SIDES.len() as i32
}
#[inline]
pub fn meeple_pass_index(w: i32) -> i32 {
    meeple_farmer_base(w) + FARMER_SIDES.len() as i32
}
#[inline]
pub fn action_size(w: i32) -> i32 {
    meeple_pass_index(w) + 1
}

/// `board_repr.offset_from_centroid_sums`.
///
/// `round(sum / count)` is CPython's `round` on a **float** — round-half-to-even
/// on the IEEE double, which is `f64::round_ties_even`.
pub fn offset_from_centroid_sums(
    starting_position: Coord,
    sum_row: i64,
    sum_col: i64,
    tile_count: i64,
    window_size: i32,
) -> WindowOffset {
    let (center_r, center_c) = if tile_count == 0 {
        (starting_position.row as i64, starting_position.col as i64)
    } else {
        let r = (sum_row as f64 / tile_count as f64).round_ties_even();
        let c = (sum_col as f64 / tile_count as f64).round_ties_even();
        (r as i64, c as i64)
    };
    let half = (window_size / 2) as i64;
    WindowOffset {
        origin_row: (center_r - half) as i32,
        origin_col: (center_c - half) as i32,
        size: window_size,
    }
}

/// The flat index of an action, or `None` when a tile placement falls outside
/// the window (Python raises `WindowOverflowError`; the caller decides).
pub fn encode(action: &Action, off: &WindowOffset, phase: Phase) -> Option<i32> {
    match action {
        Action::Tile(ta) => {
            let (wr, wc) = off.to_window(ta.coord)?;
            Some((wr * off.size + wc) * N_ROTATIONS + ta.rotations as i32)
        }
        Action::Meeple(ma) => match ma.meeple_type {
            MeepleType::Normal => Some(
                meeple_normal_base(off.size)
                    + NORMAL_SIDES.iter().position(|&s| s == ma.side).expect(
                        "NORMAL meeple on a side outside {TOP,RIGHT,BOTTOM,LEFT,CENTER}",
                    ) as i32,
            ),
            MeepleType::Farmer => Some(
                meeple_farmer_base(off.size)
                    + FARMER_SIDES
                        .iter()
                        .position(|&s| s == ma.side)
                        .expect("FARMER meeple on a non-corner side") as i32,
            ),
            other => panic!("unsupported MeepleType {other:?} (scope is NORMAL + FARMER only)"),
        },
        Action::Pass => Some(match phase {
            Phase::Tiles => tile_pass_index(off.size),
            Phase::Meeples => meeple_pass_index(off.size),
        }),
    }
}

#[derive(Debug)]
pub enum DecodeError {
    OutOfRange(i32),
    WrongPhase(i32),
    MissingNextTile,
    MissingLastTileCoord,
    Unassigned(i32),
}

/// `action_space.decode` — the inverse of [`encode`], phase-aware.
pub fn decode(
    idx: i32,
    off: &WindowOffset,
    phase: Phase,
    next_tile: Option<u16>,
    last_tile_coord: Option<Coord>,
) -> Result<Action, DecodeError> {
    let total = action_size(off.size);
    if idx < 0 || idx >= total {
        return Err(DecodeError::OutOfRange(idx));
    }
    let a_tile = tile_action_count(off.size);
    let tile_pass = tile_pass_index(off.size);
    let norm_base = meeple_normal_base(off.size);
    let farm_base = meeple_farmer_base(off.size);
    let meeple_pass = meeple_pass_index(off.size);

    match phase {
        Phase::Tiles => {
            if idx == tile_pass {
                return Ok(Action::Pass);
            }
            if idx >= a_tile {
                return Err(DecodeError::WrongPhase(idx));
            }
            let base = next_tile.ok_or(DecodeError::MissingNextTile)?;
            let (cell, rot) = (idx / N_ROTATIONS, idx % N_ROTATIONS);
            let (wr, wc) = (cell / off.size, cell % off.size);
            Ok(Action::Tile(TileAction {
                tile: tile_id(base, rot as u8),
                coord: off.to_engine(wr, wc),
                rotations: rot as u8,
            }))
        }
        Phase::Meeples => {
            if idx < a_tile || idx == tile_pass {
                return Err(DecodeError::WrongPhase(idx));
            }
            if idx == meeple_pass {
                return Ok(Action::Pass);
            }
            let coord = last_tile_coord.ok_or(DecodeError::MissingLastTileCoord)?;
            if idx >= norm_base && idx < norm_base + NORMAL_SIDES.len() as i32 {
                return Ok(Action::Meeple(MeepleAction {
                    meeple_type: MeepleType::Normal,
                    coord,
                    side: NORMAL_SIDES[(idx - norm_base) as usize],
                    remove: false,
                }));
            }
            if idx >= farm_base && idx < farm_base + FARMER_SIDES.len() as i32 {
                return Ok(Action::Meeple(MeepleAction {
                    meeple_type: MeepleType::Farmer,
                    coord,
                    side: FARMER_SIDES[(idx - farm_base) as usize],
                    remove: false,
                }));
            }
            Err(DecodeError::Unassigned(idx))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layout_matches_python() {
        assert_eq!(action_size(25), 2511);
        assert_eq!(tile_pass_index(25), 2500);
        assert_eq!(meeple_normal_base(25), 2501);
        assert_eq!(meeple_farmer_base(25), 2506);
        assert_eq!(meeple_pass_index(25), 2510);
    }

    #[test]
    fn round_is_ties_to_even() {
        let sp = Coord::new(6, 15);
        // 5 / 2 = 2.5 -> 2 (even), 7 / 2 = 3.5 -> 4 (even)
        assert_eq!(offset_from_centroid_sums(sp, 5, 7, 2, 25).origin_row, 2 - 12);
        assert_eq!(offset_from_centroid_sums(sp, 5, 7, 2, 25).origin_col, 4 - 12);
    }
}
