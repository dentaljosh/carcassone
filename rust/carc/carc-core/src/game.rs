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

// ---------------------------------------------------------------------------
// P5: the rules-fix FLAGS.  Nothing here is enabled by default anywhere.
// ---------------------------------------------------------------------------

/// The retail/tournament "D" start tile: a city on one edge with a road running
/// straight through.  `game_wrapper.RETAIL_START_TILE`.
pub const RETAIL_START_TILE: &str = "city_top_straight_road";

/// The vendored engine's `CarcassonneGameState.starting_position` — row 6 of a
/// 35-row grid (6 rows of headroom above, 28 below: the "invisible border").
pub const DEFAULT_START_ROW: i32 = 6;
pub const DEFAULT_START_COL: i32 = 15;

/// The start-tile convention, mirroring the Android bridge's `start_rule`.
///
/// * `"engine"` — the vendored engine's native rule: player 0 DRAWS a random
///   tile which is auto-placed at `starting_position`, costing them a turn.
///   Every training run, eval and solver measurement to date used this; it is
///   what a **missing** `start_rule` means and it stays the default everywhere.
/// * `"retail"` — a fixed D tile is pre-placed before anyone draws.
///
/// Anything else is an error, never a silent default: picking a rule for the
/// caller would decode a DIFFERENT game from the same `(deck_seed, actions)`.
#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub enum StartRule {
    Engine,
    Retail,
}

impl StartRule {
    /// `None` ⇒ `Engine` (the legacy meaning of an absent field in a save
    /// payload); `"engine"`/`"retail"` ⇒ themselves; anything else ⇒ `Err`.
    pub fn parse(s: Option<&str>) -> Result<Self, String> {
        match s {
            None | Some("engine") => Ok(StartRule::Engine),
            Some("retail") => Ok(StartRule::Retail),
            Some(other) => Err(format!(
                "unknown start_rule {other:?}; expected 'engine' or 'retail'"
            )),
        }
    }

    pub const fn value(self) -> &'static str {
        match self {
            StartRule::Engine => "engine",
            StartRule::Retail => "retail",
        }
    }

    pub const fn fixed_start_tile(self) -> bool {
        matches!(self, StartRule::Retail)
    }
}

/// The unplaceable-tile draw rule (F9/A3, audit RF-D-2), mirroring
/// `game_wrapper.DRAW_RULES`.
///
/// * `"engine"` — the vendored engine's native behaviour: a TILES-phase
///   `PassAction` discards the unplaceable tile, draws the next AND passes the
///   turn, so the drawer forfeits a placement.  This is what a **missing**
///   `draw_rule` means and it stays the default everywhere.
/// * `"redraw"` — the retail rule: reveal, set the tile aside (it leaves the
///   game), draw again, same player continues.
///
/// Anything else is an error, never a silent default: the two rules decode
/// DIFFERENT games from the same `(deck_seed, actions)`.  The rules clause and
/// the recursion / bag sub-decisions are documented on the Python twin,
/// `StateUpdater._apply_action_to`.
#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub enum DrawRule {
    Engine,
    Redraw,
}

impl DrawRule {
    pub fn parse(s: Option<&str>) -> Result<Self, String> {
        match s {
            None | Some("engine") => Ok(DrawRule::Engine),
            Some("redraw") => Ok(DrawRule::Redraw),
            Some(other) => Err(format!(
                "unknown draw_rule {other:?}; expected 'engine' or 'redraw'"
            )),
        }
    }

    pub const fn value(self) -> &'static str {
        match self {
            DrawRule::Engine => "engine",
            DrawRule::Redraw => "redraw",
        }
    }

    pub const fn redraw_unplaceable(self) -> bool {
        matches!(self, DrawRule::Redraw)
    }
}

/// Game-setup configuration.  `GameConfig::default()` is byte-compatible with
/// the walled engine of record: engine start rule, start (6, 15), window 25,
/// engine draw rule.
#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub struct GameConfig {
    pub window_size: i32,
    pub start_rule: StartRule,
    pub start_row: i32,
    pub start_col: i32,
    pub draw_rule: DrawRule,
}

impl Default for GameConfig {
    fn default() -> Self {
        GameConfig {
            window_size: DEFAULT_WINDOW_SIZE,
            start_rule: StartRule::Engine,
            start_row: DEFAULT_START_ROW,
            start_col: DEFAULT_START_COL,
            draw_rule: DrawRule::Engine,
        }
    }
}

impl GameConfig {
    /// Validate and resolve the three opt-in knobs.  `None` everywhere ⇒
    /// [`GameConfig::default`].
    ///
    /// **The shift must be EVEN on both axes.**
    /// `board_repr.offset_from_centroid_sums` centres the window with
    /// `round(sum / count)`, and CPython's banker's rounding is equivariant
    /// under even translations only (`round(6.5) == 6` but `round(17.5) == 18`).
    /// An ODD shift silently slips the window by one cell on ~half of all
    /// positions, which would invalidate every trained checkpoint's input
    /// distribution — so it is refused at construction rather than measured
    /// later.  (`tests/test_start_tile_grid_bound.py`,
    /// `test_odd_shift_breaks_the_window_offset`.)
    pub fn resolve(
        start_rule: Option<&str>,
        start_row: Option<i32>,
        start_col: Option<i32>,
        window_size: i32,
        draw_rule: Option<&str>,
    ) -> Result<Self, String> {
        let rule = StartRule::parse(start_rule)?;
        let draw = DrawRule::parse(draw_rule)?;
        let row = start_row.unwrap_or(DEFAULT_START_ROW);
        let col = start_col.unwrap_or(DEFAULT_START_COL);

        for (axis, v, base, extent) in [
            ("start_row", row, DEFAULT_START_ROW, crate::engine::BOARD_ROWS),
            ("start_col", col, DEFAULT_START_COL, crate::engine::BOARD_COLS),
        ] {
            let shift = v - base;
            if shift % 2 != 0 {
                return Err(format!(
                    "{axis} shift must be EVEN: {v} is {shift} from the engine default \
                     {base}. board_repr.offset_from_centroid_sums centres the window with \
                     banker's-rounded round(sum/count), which is equivariant under even \
                     translations only; an odd shift silently moves the window by one cell \
                     on ~half of all positions."
                ));
            }
            if v < 0 || v >= extent {
                return Err(format!("{axis} {v} is outside the 0..{extent} board"));
            }
        }
        if window_size < 1 {
            return Err(format!("window_size must be >= 1, got {window_size}"));
        }
        Ok(GameConfig {
            window_size,
            start_rule: rule,
            start_row: row,
            start_col: col,
            draw_rule: draw,
        })
    }

    pub fn starting_position(&self) -> Coord {
        Coord::new(self.start_row, self.start_col)
    }
}

/// Base index of [`RETAIL_START_TILE`] in the generated registry.
pub fn retail_start_base() -> Result<u16, String> {
    tiles::generated::BASE_TILES
        .iter()
        .position(|t| t.description == RETAIL_START_TILE)
        .map(|i| i as u16)
        .ok_or_else(|| format!("the base deck has no {RETAIL_START_TILE:?} tile"))
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
    /// The setup flags this game was built under.  Carried so the mirror can
    /// report them back and so a clone (search / determinization) can never
    /// silently change convention mid-game.
    pub cfg: GameConfig,
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
        Self::from_deck_with_config(
            deck,
            GameConfig {
                window_size,
                ..GameConfig::default()
            },
        )
        .expect("the default (engine) start rule cannot fail")
    }

    /// `Game(fixed_start_tile=..., window_size=...).get_init_board()`.
    ///
    /// Mirrors `game_wrapper.Game.get_init_board` in order: build the virgin
    /// state, optionally pre-place the retail start tile, then
    /// `total_tiles = len(deck) + 1 + len(placed_coords)` and
    /// `Board.from_state`, whose centroid seed is a one-time scan of
    /// `placed_coords` (`board_repr.centroid_sums`).
    pub fn from_deck_with_config(deck: Vec<u16>, cfg: GameConfig) -> Result<Self, String> {
        let mut state = GameState::from_deck_with_start(deck, cfg.starting_position());
        // F9/A3: latch the draw rule onto the state so it rides `clone()` into
        // every search node, determinized world and solver child.
        state.redraw_unplaceable = cfg.draw_rule.redraw_unplaceable();
        if cfg.start_rule.fixed_start_tile() {
            let base = retail_start_base()?;
            state.preplace_start_tile(base, RETAIL_START_TILE)?;
        }
        // `centroid_sums(state)` — a full scan of placed_coords (empty under the
        // engine rule, exactly the pre-placed start tile under retail).
        let mut sum_row = 0i64;
        let mut sum_col = 0i64;
        for &(r, c) in &state.placed_coords {
            sum_row += r as i64;
            sum_col += c as i64;
        }
        let tile_count = state.placed_coords.len() as i64;
        let total_tiles = state.deck_len() as i64 + 1 + tile_count;
        let offset = offset_from_centroid_sums(
            state.starting_position,
            sum_row,
            sum_col,
            tile_count,
            cfg.window_size,
        );
        Ok(Game {
            state,
            window_size: cfg.window_size,
            total_tiles,
            sum_row,
            sum_col,
            tile_count,
            offset,
            cfg,
        })
    }

    pub fn from_seed(deck_seed_decimal: &str) -> Self {
        Self::from_deck(deck_from_seed(deck_seed_decimal))
    }

    pub fn from_seed_with_config(
        deck_seed_decimal: &str,
        cfg: GameConfig,
    ) -> Result<Self, String> {
        Self::from_deck_with_config(deck_from_seed(deck_seed_decimal), cfg)
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
        let n_set_aside_before = self.state.set_aside.len();
        self.state.apply_action(action);
        // F9/A3: a tile set aside leaves the game, so `total_tiles` must shrink
        // with it or `total_tiles - tile_count` stops equalling
        // `deck_len + has_next`.  `game_wrapper._next_total_tiles` is the twin.
        // Gated on the flag: flags-off keeps the pre-existing (latent) drift, so
        // the byte-identity gate stays clean.
        if self.state.redraw_unplaceable {
            self.total_tiles -= (self.state.set_aside.len() - n_set_aside_before) as i64;
        }
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

    // --- P5 flags ---------------------------------------------------------

    fn retail_cfg() -> GameConfig {
        GameConfig {
            start_rule: StartRule::Retail,
            ..GameConfig::default()
        }
    }

    #[test]
    fn default_config_is_the_walled_engine_of_record() {
        let d = GameConfig::default();
        assert_eq!(d.start_rule, StartRule::Engine);
        assert_eq!((d.start_row, d.start_col), (6, 15));
        assert_eq!(d.window_size, 25);
        assert_eq!(GameConfig::resolve(None, None, None, 25, None).unwrap(), d);
        // and it is byte-identical to the pre-P5 constructor
        let a = Game::from_seed("20260730");
        let b = Game::from_seed_with_config("20260730", d).unwrap();
        assert_eq!(a.string_repr(), b.string_repr());
        assert_eq!(a.total_tiles, b.total_tiles);
        assert_eq!(a.legal_mask_sha256(), b.legal_mask_sha256());
    }

    #[test]
    fn start_rule_parsing_mirrors_the_bridge() {
        assert_eq!(StartRule::parse(None).unwrap(), StartRule::Engine);
        assert_eq!(StartRule::parse(Some("engine")).unwrap(), StartRule::Engine);
        assert_eq!(StartRule::parse(Some("retail")).unwrap(), StartRule::Retail);
        for bad in ["RETAIL", "Engine", "", "tournament"] {
            assert!(StartRule::parse(Some(bad)).is_err(), "{bad:?} must raise");
        }
    }

    #[test]
    fn odd_shifts_are_refused_even_shifts_are_not() {
        assert!(GameConfig::resolve(None, Some(18), None, 25, None).is_ok());
        assert!(GameConfig::resolve(None, Some(6), None, 25, None).is_ok());
        assert!(GameConfig::resolve(None, Some(17), None, 25, None).is_err());
        assert!(GameConfig::resolve(None, Some(5), None, 25, None).is_err());
        assert!(GameConfig::resolve(None, None, Some(16), 25, None).is_err());
        assert!(GameConfig::resolve(None, None, Some(17), 25, None).is_ok());
        assert!(GameConfig::resolve(None, Some(-2), None, 25, None).is_err()); // off-board
        assert!(GameConfig::resolve(None, Some(36), None, 25, None).is_err());
    }

    #[test]
    fn retail_start_places_the_unrotated_d_tile() {
        let g = Game::from_seed_with_config("20260730", retail_cfg()).unwrap();
        let sp = g.state.starting_position;
        let tid = g.state.get_tile(sp.row, sp.col).expect("start tile on board");
        let t = tiles::tile(tid);
        assert_eq!(t.description, RETAIL_START_TILE);
        assert_eq!(t.rot, 0, "the retail D tile is placed UNROTATED");
        // nobody played it
        assert_eq!(g.state.current_player, 0);
        assert!(g.state.last_tile_action.is_none());
        assert_eq!(g.state.meeples, [7, 7]);
        assert!(g.state.placed_meeples[0].is_empty() && g.state.placed_meeples[1].is_empty());
        // bookkeeping
        assert_eq!(g.state.placed_coords.len(), 1);
        assert!(!g.state.open_positions.contains(&(sp.row, sp.col)));
        assert_eq!(g.state.open_positions.len(), 4);
        assert_eq!(g.tile_count, 1);
        assert_eq!(g.total_tiles, 72);
        assert_eq!(g.state.deck_len(), 70, "70 undrawn + 1 in hand = 71");
    }

    #[test]
    fn retail_removes_exactly_one_d_from_the_bag() {
        let g = Game::from_seed_with_config("20260730", retail_cfg()).unwrap();
        let base = retail_start_base().unwrap();
        let mut pool: Vec<u16> = vec![g.state.next_tile.unwrap()];
        pool.extend_from_slice(g.state.remaining_deck());
        assert_eq!(pool.len(), 71);
        assert_eq!(pool.iter().filter(|&&t| t == base).count(), 3);
        // full multiset: the 71 in the bag + the one on the board == the deck
        let mut all = pool.clone();
        all.push(base);
        all.sort_unstable();
        let mut want = base_deck_unshuffled();
        want.sort_unstable();
        assert_eq!(all, want);
    }

    #[test]
    fn retail_first_move_is_a_real_choice() {
        assert_eq!(Game::from_seed("20260730").legal_actions().len(), 1);
        assert!(
            Game::from_seed_with_config("20260730", retail_cfg())
                .unwrap()
                .legal_actions()
                .len()
                > 1
        );
    }

    #[test]
    fn window_offset_starts_on_the_start_tile_under_either_rule() {
        for cfg in [GameConfig::default(), retail_cfg()] {
            let g = Game::from_seed_with_config("20260730", cfg).unwrap();
            let sp = g.state.starting_position;
            let half = g.offset.size / 2;
            assert_eq!(g.offset.origin_row, sp.row - half);
            assert_eq!(g.offset.origin_col, sp.col - half);
        }
    }

    #[test]
    fn retail_game_plays_to_a_scored_terminal() {
        let mut g = Game::from_seed_with_config("77", retail_cfg()).unwrap();
        let mut plies = 0;
        while !g.is_terminal() && plies < 400 {
            let legal = g.legal_actions();
            assert!(!legal.is_empty());
            g.advance(legal[0]).unwrap();
            plies += 1;
        }
        assert!(g.is_terminal());
        assert_eq!(g.state.placed_coords.len(), 72);
        assert!(g.scores()[0] + g.scores()[1] > 0);
    }

    #[test]
    fn an_even_row_shift_translates_the_window_exactly() {
        let cfg = GameConfig {
            start_row: 18,
            ..GameConfig::default()
        };
        let a = Game::from_seed("20260730");
        let b = Game::from_seed_with_config("20260730", cfg).unwrap();
        assert_eq!(b.offset.origin_row, a.offset.origin_row + 12);
        assert_eq!(b.offset.origin_col, a.offset.origin_col);
        assert_eq!(b.legal_mask().mask, a.legal_mask().mask);
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
