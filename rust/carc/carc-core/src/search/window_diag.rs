//! F-c "fail loud" — the diagnostic behind an empty action mask at an interior
//! search node.
//!
//! `measurement/window_truncation_20260813/DESIGN.md` §1: `action_space::encode`
//! returns `None` for a TILE placement outside the window, and
//! [`crate::game::Game::legal_mask`] counts those as `n_overflow` and **drops
//! them silently**.  When *every* legal action of a node overflows, the node is
//! expanded with an empty `valid_actions` and the next descent through it raises
//! `SearchError::NoLegalActionsAtInterior` — a bare `IndexError`-shaped message
//! that says nothing about the cause and cannot be told apart from a genuinely
//! action-less node.  DESIGN §6-P3 fired by OCCURRENCE in production
//! (`measurement/joshuabot_20260812/CONFIRM_EXCLUSIONS.md`), which licenses this.
//!
//! ⚠️ **Cost discipline.** Every function here runs on the ERROR path only —
//! nothing in this module is reachable while a search is succeeding, so the
//! no-fire path is byte-identical to the pre-fix search by construction.  The
//! only edit to live code is the `Err(..)` arm of an existing `?` in
//! [`crate::search::Searcher::simulate`].
//!
//! What the diagnostic canNOT know: the deck seed, the seat and the GLOBAL ply.
//! Those live above the search (the harness owns the deck; the agent owns its
//! own `move_idx`), and `carcassonne_ai.window_truncation` on the Python side is
//! what joins them onto this payload.  See that module's docstring for the
//! `move_idx`-is-not-the-ply trap.

use crate::action_space::encode;
use crate::engine::Action;
use crate::game::Game;
use crate::sha256::sha256_hex_prefix;

/// How many dropped placements are listed in the payload before it is truncated
/// (the count is always reported in full as `n_overflow`).
const MAX_DROPPED_LISTED: usize = 64;

/// Why the node's encoded action set was empty.
///
/// This is the requirement-3 discriminator: `WindowTruncation` is the defect;
/// the other two are *different* bugs that must not be filed under it.
#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub enum EmptyMaskCause {
    /// The engine offered ≥1 legal action and **every one of them** failed to
    /// encode — i.e. the window truncated the whole move list.  THE DEFECT.
    WindowTruncation,
    /// The engine itself offered no action at a non-terminal node.  Nothing to
    /// do with the window; an engine/legality bug if it ever appears.
    NoEngineActions,
    /// The mask is **not** empty when re-derived at the raise, so the node's
    /// empty `valid_actions` cannot be explained by the window at all
    /// (a transposition-key collision, or a node reached before expansion).
    MaskNotEmpty,
}

impl EmptyMaskCause {
    pub const fn value(self) -> &'static str {
        match self {
            EmptyMaskCause::WindowTruncation => "window_truncation",
            EmptyMaskCause::NoEngineActions => "no_engine_actions",
            EmptyMaskCause::MaskNotEmpty => "mask_not_empty",
        }
    }
}

/// One legal placement the window refused to encode, in ENGINE coordinates.
#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub struct DroppedPlacement {
    pub row: i32,
    pub col: i32,
    pub rotations: u8,
}

/// Everything the search itself can say about an empty-mask node.
#[derive(Clone, Debug)]
pub struct EmptyMaskDiag {
    pub cause: EmptyMaskCause,
    /// `legal_mask()` counters re-derived at the raise.
    pub n_total: usize,
    pub n_overflow: usize,
    pub n_encoded: usize,
    /// The window under which the mask was built.
    pub window_size: i32,
    pub origin_row: i32,
    pub origin_col: i32,
    pub phase: &'static str,
    pub player_to_move: usize,
    /// Tiles left in the (determinized) deck — the census's `k_remaining`.
    pub k_remaining: usize,
    pub tiles_placed: i64,
    /// Plies from the SEARCH root (not the game root): `descent_actions.len()`.
    pub depth: usize,
    /// Which simulation of this world's search hit it.
    pub sim_idx: usize,
    /// The action sequence from the search root to this node — replaying it from
    /// the seated root reconstructs the node losslessly (DESIGN §3).
    pub descent_actions: Vec<i32>,
    /// `sha256(string_representation)[:16]` — the trace harness's node identity,
    /// so a payload can be matched against a `window_truncation_census` trace.
    pub node_digest: String,
    /// `Game::state_digest` — repr + mask + scores + offset + terminal.
    pub state_digest: String,
    /// Board extent in engine coordinates, `(min_row, max_row, min_col, max_col)`;
    /// `None` on an empty board.
    pub board_extent: Option<(i32, i32, i32, i32)>,
    /// Up to [`MAX_DROPPED_LISTED`] of the dropped placements.
    pub dropped: Vec<DroppedPlacement>,
}

impl EmptyMaskDiag {
    /// Build the payload from the game state AT the node.  ERROR PATH ONLY.
    pub fn collect(g: &Game, descent_actions: &[i32], sim_idx: usize) -> Self {
        let mask = g.legal_mask();
        let n_encoded = mask.n_total - mask.n_overflow;
        let cause = if n_encoded > 0 {
            EmptyMaskCause::MaskNotEmpty
        } else if mask.n_total == 0 {
            EmptyMaskCause::NoEngineActions
        } else {
            EmptyMaskCause::WindowTruncation
        };

        let mut dropped = Vec::new();
        for action in g.state.possible_actions() {
            if encode(&action, &g.offset, g.state.phase).is_some() {
                continue;
            }
            if dropped.len() >= MAX_DROPPED_LISTED {
                break;
            }
            if let Action::Tile(ta) = action {
                dropped.push(DroppedPlacement {
                    row: ta.coord.row,
                    col: ta.coord.col,
                    rotations: ta.rotations,
                });
            }
        }

        let mut extent: Option<(i32, i32, i32, i32)> = None;
        for &(r, c) in &g.state.placed_coords {
            extent = Some(match extent {
                None => (r, r, c, c),
                Some((r0, r1, c0, c1)) => (r0.min(r), r1.max(r), c0.min(c), c1.max(c)),
            });
        }

        let key = g.string_repr();
        EmptyMaskDiag {
            cause,
            n_total: mask.n_total,
            n_overflow: mask.n_overflow,
            n_encoded,
            window_size: g.window_size,
            origin_row: g.offset.origin_row,
            origin_col: g.offset.origin_col,
            phase: g.state.phase.value(),
            player_to_move: g.state.current_player,
            k_remaining: g.state.deck_len(),
            tiles_placed: g.tile_count,
            depth: descent_actions.len(),
            sim_idx,
            descent_actions: descent_actions.to_vec(),
            node_digest: sha256_hex_prefix(key.as_bytes(), 16),
            state_digest: g.state_digest(),
            board_extent: extent,
            dropped,
        }
    }

    pub fn is_truncation(&self) -> bool {
        self.cause == EmptyMaskCause::WindowTruncation
    }

    /// A compact JSON object.  Every field is a number or a fixed-alphabet
    /// string (phase names, hex digests), so no escaping is possible or needed;
    /// `carcassonne_ai.window_truncation.parse_diag` is the reader.
    pub fn to_json(&self) -> String {
        let mut s = String::with_capacity(512);
        s.push('{');
        s.push_str(&format!(r#""cause":"{}","#, self.cause.value()));
        s.push_str(&format!(r#""n_total":{},"#, self.n_total));
        s.push_str(&format!(r#""n_overflow":{},"#, self.n_overflow));
        s.push_str(&format!(r#""n_encoded":{},"#, self.n_encoded));
        s.push_str(&format!(r#""window_size":{},"#, self.window_size));
        s.push_str(&format!(
            r#""window_offset":[{},{},{}],"#,
            self.origin_row, self.origin_col, self.window_size
        ));
        s.push_str(&format!(r#""phase":"{}","#, self.phase));
        s.push_str(&format!(r#""player_to_move":{},"#, self.player_to_move));
        s.push_str(&format!(r#""k_remaining":{},"#, self.k_remaining));
        s.push_str(&format!(r#""tiles_placed":{},"#, self.tiles_placed));
        s.push_str(&format!(r#""depth":{},"#, self.depth));
        s.push_str(&format!(r#""sim_idx":{},"#, self.sim_idx));
        s.push_str(r#""descent_actions":["#);
        for (i, a) in self.descent_actions.iter().enumerate() {
            if i > 0 {
                s.push(',');
            }
            s.push_str(&a.to_string());
        }
        s.push_str("],");
        s.push_str(&format!(r#""node_digest":"{}","#, self.node_digest));
        s.push_str(&format!(r#""state_digest":"{}","#, self.state_digest));
        match self.board_extent {
            None => s.push_str(r#""board_extent":null,"#),
            Some((r0, r1, c0, c1)) => s.push_str(&format!(
                r#""board_extent":[{r0},{r1},{c0},{c1}],"#
            )),
        }
        s.push_str(r#""dropped":["#);
        for (i, d) in self.dropped.iter().enumerate() {
            if i > 0 {
                s.push(',');
            }
            s.push_str(&format!(
                r#"{{"row":{},"col":{},"rot":{}}}"#,
                d.row, d.col, d.rotations
            ));
        }
        s.push_str("],");
        s.push_str(&format!(r#""n_dropped_listed":{}"#, self.dropped.len()));
        s.push('}');
        s
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::Game;

    /// A window small enough that the board immediately outgrows it: the mask
    /// counters and the cause must agree, and the dropped placements must be
    /// listed in ENGINE coordinates.
    ///
    /// W=1 admits exactly one board cell (the start position), so the FIRST tile
    /// still encodes and every neighbour placement after it overflows.
    #[test]
    fn a_narrow_window_is_classified_as_truncation() {
        let mut g = Game::from_deck_with_window(crate::game::deck_from_seed("126000000135"), 1);
        let mut fired = false;
        let mut acts: Vec<i32> = Vec::new();
        for _ in 0..6 {
            let m = g.legal_mask();
            if m.n_total > 0 && m.n_total == m.n_overflow {
                let d = EmptyMaskDiag::collect(&g, &acts, 3);
                assert_eq!(d.cause, EmptyMaskCause::WindowTruncation);
                assert!(d.is_truncation());
                assert_eq!(d.n_encoded, 0);
                assert_eq!(d.n_overflow, m.n_overflow);
                assert_eq!(d.n_total, m.n_total);
                assert_eq!(d.window_size, 1);
                assert_eq!(d.depth, acts.len());
                assert_eq!(d.descent_actions, acts);
                assert!(!d.dropped.is_empty(), "a truncation must name its coords");
                let json = d.to_json();
                assert!(json.contains(r#""cause":"window_truncation""#));
                assert!(json.contains(r#""n_encoded":0"#));
                assert!(json.contains(r#""dropped":[{"row":"#));
                fired = true;
                break;
            }
            let legal = g.legal_actions();
            assert!(!legal.is_empty(), "no legal action and no truncation either");
            g.advance(legal[0]).expect("advance the first legal action");
            acts.push(legal[0]);
        }
        assert!(fired, "a W=1 board must truncate its whole move list within 6 plies");
    }

    /// The wide (production) window on the same root must NOT be a truncation.
    #[test]
    fn the_production_window_is_not_truncated_at_the_root() {
        let g = Game::from_seed("126000000135");
        let m = g.legal_mask();
        assert_eq!(m.n_overflow, 0);
        let d = EmptyMaskDiag::collect(&g, &[3, 4], 7);
        // The mask is non-empty, so this node's `valid_actions` being empty
        // could not have been the window's doing.
        assert_eq!(d.cause, EmptyMaskCause::MaskNotEmpty);
        assert!(!d.is_truncation());
        assert_eq!(d.depth, 2);
        assert_eq!(d.sim_idx, 7);
        assert_eq!(d.descent_actions, vec![3, 4]);
    }
}
