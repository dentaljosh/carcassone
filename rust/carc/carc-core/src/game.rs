//! The mirror state the FFI advances: `game_wrapper.Game` + `Board`.
//!
//! Wire format = the replay contract (`scripts/measurement_infra/root_replay.py`):
//! a game is `(deck_seed, [action ints])`, or `(deck as tile descriptions,
//! [action ints])` for the phone path where no RNG is involved.

use crate::action_space::{
    action_size, decode, encode, offset_from_centroid_sums, WindowOffset, DEFAULT_WINDOW_SIZE,
};
use crate::compat::mt19937::MT19937;
use crate::engine::{Action, Coord, GameState};
use crate::repr_key::string_representation;
use crate::sha256::sha256_hex;
use crate::tiles;

/// The deck for `random.seed(deck_seed)`, reproducing
/// `CarcassonneGameState.initialize_deck` for `TileSet.BASE`:
///
/// ```python
/// new_tiles = []
/// for card_name, count in base_tile_counts.items():   # dict insertion order
///     for i in range(count):
///         new_tiles.append(base_tiles[card_name])
/// random.shuffle(new_tiles)                            # the ONE global draw
/// ```
pub fn deck_from_seed(deck_seed_decimal: &str) -> Vec<u16> {
    let mut deck = base_deck_unshuffled();
    let mut mt = MT19937::from_py_int_seed_decimal(deck_seed_decimal);
    mt.shuffle(&mut deck);
    deck
}

/// The 72-tile multiset in `base_tile_counts` insertion order, pre-shuffle.
pub fn base_deck_unshuffled() -> Vec<u16> {
    let mut out = Vec::with_capacity(72);
    for (idx, count) in tiles::counts_in_order() {
        for _ in 0..count {
            out.push(idx);
        }
    }
    out
}

/// Resolve a deck given as tile descriptions (the Android archive path).
pub fn deck_from_descriptions(names: &[String]) -> Result<Vec<u16>, String> {
    names
        .iter()
        .map(|n| {
            tiles::generated::BASE_TILES
                .iter()
                .position(|t| t.description == n.as_str())
                .map(|i| i as u16)
                .ok_or_else(|| format!("unknown tile description {n:?}"))
        })
        .collect()
}

#[derive(Clone)]
pub struct Game {
    pub state: GameState,
    pub window_size: i32,
    pub total_tiles: i64,
    pub sum_row: i64,
    pub sum_col: i64,
    pub tile_count: i64,
    pub offset: WindowOffset,
}

#[derive(Debug)]
pub struct MaskResult {
    /// One byte per action index, `0`/`1` — the bytes `numpy` would hand to
    /// `hashlib.sha256(mask.tobytes())`.
    pub mask: Vec<u8>,
    pub n_total: usize,
    pub n_overflow: usize,
}

impl Game {
    pub fn from_deck(deck: Vec<u16>) -> Self {
        Self::from_deck_with_window(deck, DEFAULT_WINDOW_SIZE)
    }

    pub fn from_deck_with_window(deck: Vec<u16>, window_size: i32) -> Self {
        let state = GameState::from_deck(deck);
        let total_tiles = state.deck_len() as i64 + 1;
        let offset =
            offset_from_centroid_sums(state.starting_position, 0, 0, 0, window_size);
        Game {
            state,
            window_size,
            total_tiles,
            sum_row: 0,
            sum_col: 0,
            tile_count: 0,
            offset,
        }
    }

    pub fn from_seed(deck_seed_decimal: &str) -> Self {
        Self::from_deck(deck_from_seed(deck_seed_decimal))
    }

    /// `Game.get_next_state` — decode against the *current* offset and phase,
    /// apply, then carry the centroid sums forward (only a tile placement moves
    /// the centroid) and re-derive the offset.
    pub fn advance(&mut self, action_idx: i32) -> Result<(), String> {
        let action = decode(
            action_idx,
            &self.offset,
            self.state.phase,
            self.state.next_tile,
            self.state.last_tile_action.map(|lta| lta.coord),
        )
        .map_err(|e| format!("decode({action_idx}) failed: {e:?}"))?;

        if let Action::Tile(ta) = action {
            self.sum_row += ta.coord.row as i64;
            self.sum_col += ta.coord.col as i64;
            self.tile_count += 1;
        }
        self.state.apply_action(action);
        self.offset = offset_from_centroid_sums(
            self.state.starting_position,
            self.sum_row,
            self.sum_col,
            self.tile_count,
            self.window_size,
        );
        Ok(())
    }

    /// `Game._compute_mask` — the engine's own enumeration, encoded.
    pub fn legal_mask(&self) -> MaskResult {
        let mut mask = vec![0u8; action_size(self.window_size) as usize];
        let mut n_total = 0usize;
        let mut n_overflow = 0usize;
        for action in self.state.possible_actions() {
            n_total += 1;
            match encode(&action, &self.offset, self.state.phase) {
                None => n_overflow += 1,
                Some(idx) => mask[idx as usize] = 1,
            }
        }
        MaskResult {
            mask,
            n_total,
            n_overflow,
        }
    }

    pub fn legal_mask_sha256(&self) -> String {
        sha256_hex(&self.legal_mask().mask)
    }

    pub fn legal_actions(&self) -> Vec<i32> {
        let m = self.legal_mask();
        m.mask
            .iter()
            .enumerate()
            .filter(|(_, &v)| v != 0)
            .map(|(i, _)| i as i32)
            .collect()
    }

    pub fn string_repr(&self) -> String {
        string_representation(&self.state)
    }

    /// A short content digest of the full mirror state — the reconcile-mode
    /// per-move assert compares this, not the human-readable repr.
    pub fn state_digest(&self) -> String {
        let mut s = self.string_repr();
        s.push('|');
        s.push_str(&self.legal_mask_sha256());
        s.push('|');
        s.push_str(&format!(
            "{},{}|{},{},{}|{}",
            self.state.scores[0],
            self.state.scores[1],
            self.offset.origin_row,
            self.offset.origin_col,
            self.offset.size,
            self.state.is_terminated() as u8
        ));
        sha256_hex(s.as_bytes())[..32].to_string()
    }

    pub fn scores(&self) -> [i64; 2] {
        self.state.scores
    }

    pub fn is_terminal(&self) -> bool {
        self.state.is_terminated()
    }

    pub fn flat_base_score(&self, player: usize) -> i64 {
        self.state.flat_base_score(player)
    }

    pub fn starting_position(&self) -> Coord {
        self.state.starting_position
    }

    /// The **unseen** deck (`CarcassonneGameState.deck` on the Python side — the
    /// already-drawn `next_tile` is NOT part of it), in draw order.
    pub fn unseen_deck(&self) -> Vec<&'static str> {
        self.state
            .remaining_deck()
            .iter()
            .map(|&t| tiles::generated::BASE_TILES[t as usize].description)
            .collect()
    }

    /// Replace the unseen deck in place — the determinization hook
    /// (`FairHeuristicMCTSAgent.reshuffled_determinization` shuffles exactly
    /// this list and leaves `next_tile` untouched).  The multiset is NOT
    /// checked; the caller owns that (P4's determinizer preserves it by
    /// construction, and the P3 reconcile drives both sides from ONE list).
    pub fn set_unseen_deck(&mut self, names: &[String]) -> Result<(), String> {
        let ids = deck_from_descriptions(names)?;
        self.state.set_remaining_deck(&ids)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deck_lengths() {
        assert_eq!(base_deck_unshuffled().len(), 72);
        let g = Game::from_seed("1");
        assert_eq!(g.state.deck_len(), 71);
        assert_eq!(g.total_tiles, 72);
    }

    #[test]
    fn first_move_is_forced_to_the_starting_position() {
        let g = Game::from_seed("1");
        let legal = g.legal_actions();
        assert_eq!(legal.len(), 1, "the empty board offers exactly one placement");
    }

    #[test]
    fn a_seeded_game_plays_to_termination_greedily() {
        let mut g = Game::from_seed("1");
        let mut plies = 0;
        while !g.is_terminal() && plies < 400 {
            let legal = g.legal_actions();
            assert!(!legal.is_empty(), "no legal action at ply {plies}");
            g.advance(legal[0]).unwrap();
            plies += 1;
        }
        assert!(g.is_terminal(), "game did not terminate in {plies} plies");
        assert!(g.state.placed_coords.len() > 20);
    }
}
