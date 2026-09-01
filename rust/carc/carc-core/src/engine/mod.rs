//! A port of the vendored (patched) wingedsheep engine: state, transitions,
//! legality and scoring, for the locked scope **2 players, Base tile set,
//! FARMERS supplementary rule** (no River, no Inns & Cathedrals, no Abbots,
//! no Big meeples).
//!
//! ## Fidelity notes — the quirks that are load-bearing
//!
//! * **Tied features score full points for every tied player**
//!   (`PointsCollector.get_winning_players` returns a *list*; upstream returned
//!   a sole winner or nothing).
//! * **Farm adjacency uses the fixed involution** `TRT <-> BRB`
//!   ([`crate::tiles::FarmerSide::opposite`]).
//! * **`find_farm` is a complete, start-independent connected-component DFS.**
//!   Python keys nodes by `(row, col, id(FarmerConnection))`; a tile's farm
//!   objects are distinct per slot and canonically shared, so `(coord, slot)`
//!   is an exact substitute.
//! * **A TILES-phase `PassAction` discards the tile and hands off** (the
//!   2026-04-28 vendored patch) rather than falling through to MEEPLES with a
//!   stale `last_tile_action`.
//! * **`Tile.get_type`** drives everything, including `has_cathedral`, which is
//!   read off `tile.inn` (upstream mislabelling that the scorer depends on).
//! * **Python negative-index wrap.** `CityUtil.cities_for_position`,
//!   `FarmUtil.farm_for_position` and `PointsCollector.chapel_or_flowers_points`
//!   index `game_state.board[row][column]` *directly*, so `row == -1` reads row
//!   34 in CPython. [`GameState::board_direct`] reproduces that exactly (it is
//!   benign only because the far rows/columns stay empty — but "benign" is a
//!   property of the corpus, not of the code).
//!
//!   ⚠️ **The OTHER end of the same unguarded index used to CRASH** (fixed
//!   2026-08-23, `panic-triage`).  All three readers above are reached with a
//!   coordinate stepped ONE cell off the tile they started from —
//!   `CityUtil.opposite_edge`, `FarmUtil.opposite_edge` and the cloister 3x3 —
//!   so a region touching the LAST row/column produces index `35`, which CPython
//!   raises `IndexError` on and this port faithfully panicked on
//!   (`IndexError: board row index 35 out of range (len 35)`).  Under
//!   `fixed_v1` (`centered18`, start row 18) the bottom wall is only 16 rows
//!   from the start tile and the tie-arbiter's tier-1 playouts spread far wider
//!   than champion play, so it fired at ~0.1% of live B=32 games (three seeds,
//!   2026-08-22).  [`GameState::board_direct`] now returns `None` — "no tile
//!   there" — for any index outside `[-len, len)` instead of panicking.
//!   **The `-1` wrap is deliberately UNCHANGED**: it is a scoring semantic every
//!   recorded game, checkpoint and gate was produced under, so touching it would
//!   move the rules epoch.  Only the crash is removed, and no game that did not
//!   crash can observe the difference.
//! * **`remove_meeples_and_collect_points` rebinds its `coordinate` local
//!   inside the cloister scan**, so each outer row iteration re-derives its
//!   column range from the *last tile seen*.  See
//!   [`GameState::remove_meeples_and_collect_points`].
//! * **`find_roads` does not dedup** (Python `Road` has no `__eq__`/`__hash__`,
//!   so `set()` keeps one entry per road-typed side); `find_cities` does
//!   (Python `City` has value equality).

use std::collections::{BTreeSet, HashMap, HashSet};

use crate::tiles::{self, tile_id, FarmerSide, RotTile, Side, TerrainType, TileId};

#[cfg(test)]
mod board_bounds_tests;
#[cfg(test)]
mod board_wall_probe;
#[cfg(test)]
mod cloister_scan_fix_tests;
/// Engine follow-on A — the flat-play-table conversion's correctness gates.
#[cfg(test)]
mod flat_play_tests;

pub const BOARD_ROWS: i32 = 35;
pub const BOARD_COLS: i32 = 35;
pub const EMPTY: u16 = u16::MAX;
pub const CARDINALS: [Side; 4] = [Side::Top, Side::Right, Side::Bottom, Side::Left];

// ---------------------------------------------------------------------------
// Value types
// ---------------------------------------------------------------------------

#[derive(Copy, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct Coord {
    pub row: i32,
    pub col: i32,
}

impl Coord {
    pub const fn new(row: i32, col: i32) -> Self {
        Coord { row, col }
    }
}

pub type CoordSide = (i32, i32, Side);

#[derive(Copy, Clone, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum Phase {
    Tiles = 0,
    Meeples = 1,
}

impl Phase {
    pub const fn value(self) -> &'static str {
        match self {
            Phase::Tiles => "tiles",
            Phase::Meeples => "meeples",
        }
    }
}

#[derive(Copy, Clone, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum MeepleType {
    Normal = 0,
    Abbot = 1,
    Farmer = 2,
    Big = 3,
    BigFarmer = 4,
}

impl MeepleType {
    pub const fn value(self) -> &'static str {
        match self {
            MeepleType::Normal => "normal",
            MeepleType::Abbot => "abbot",
            MeepleType::Farmer => "farmer",
            MeepleType::Big => "big",
            MeepleType::BigFarmer => "big_farmer",
        }
    }
}

#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub struct MeeplePosition {
    pub meeple_type: MeepleType,
    pub coord: Coord,
    pub side: Side,
}

#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub struct TileAction {
    /// The *rotated* tile actually placed (registry id).
    pub tile: TileId,
    pub coord: Coord,
    pub rotations: u8,
}

#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub struct MeepleAction {
    pub meeple_type: MeepleType,
    pub coord: Coord,
    pub side: Side,
    pub remove: bool,
}

#[derive(Copy, Clone, PartialEq, Eq, Debug)]
pub enum Action {
    Tile(TileAction),
    Meeple(MeepleAction),
    Pass,
}

// ---------------------------------------------------------------------------
// Feature components
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct City {
    pub positions: Vec<CoordSide>, // sorted, deduped
    pub finished: bool,
}

#[derive(Clone, Debug)]
pub struct Road {
    pub positions: Vec<CoordSide>, // sorted, deduped
    pub finished: bool,
}

/// A `FarmerConnectionWithCoordinate`: a tile coordinate + which of that tile's
/// farm slots.  `(coord, slot)` replaces Python's `id(FarmerConnection)` key.
#[derive(Copy, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct FarmNode {
    pub coord: Coord,
    pub slot: u8,
}

#[derive(Clone, Debug)]
pub struct Farm {
    pub nodes: Vec<FarmNode>, // sorted, deduped
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

#[derive(Clone)]
pub struct GameState {
    /// 35x35, row-major; [`EMPTY`] for an empty cell, else a registry [`TileId`].
    pub board: Vec<u16>,
    /// Undrawn tiles as *base* tile indices, in draw order.
    pub deck: Vec<u16>,
    deck_head: usize,
    /// The drawn-but-unplayed tile (base tile index), `None` once the bag is out.
    pub next_tile: Option<u16>,
    pub players: usize,
    pub meeples: [i32; 2],
    pub abbots: [i32; 2],
    pub big_meeples: [i32; 2],
    pub placed_meeples: [Vec<MeeplePosition>; 2],
    pub scores: [i64; 2],
    pub current_player: usize,
    pub phase: Phase,
    pub last_tile_action: Option<TileAction>,
    pub open_positions: BTreeSet<(i32, i32)>,
    pub placed_coords: BTreeSet<(i32, i32)>,
    pub starting_position: Coord,
    /// F9-A2, OPT-IN and DEFAULT FALSE: score a cloister the moment its 3x3 is
    /// full instead of leaving it to the drifting scan (audit RF-D-1).  Seeded
    /// from [`crate::game::GameConfig`]; a `clone()` (search / determinization)
    /// carries it, so a subtree can never change convention mid-search.
    pub cloister_scan_fix: bool,
    /// Completions scored at their true ply that the legacy drifting window
    /// would NOT have visited — an upper bound on monk-pins avoided.  Only ever
    /// incremented when `cloister_scan_fix` is on.
    pub cloister_completions_accelerated: i64,
    /// F9/A3 — `CarcassonneGameState.redraw_unplaceable`.  `false` (default) is
    /// the engine of record: a TILES-phase pass costs the drawer their turn.
    /// `true` is the retail rule (set aside, draw again, same player).  Lives on
    /// the state, not the config, for the same reason the Python twin does:
    /// every transition helper takes the state alone, so the flag must ride
    /// `clone()` into every search node, PIMC world and solver child.
    pub redraw_unplaceable: bool,
    /// Tiles that left the game unplaced, in removal order.  Written under BOTH
    /// draw rules (pure telemetry — no scorer, repr, mask or leaf reads it);
    /// only `redraw_unplaceable` makes it behavioural.
    pub set_aside: Vec<u16>,
}

impl GameState {
    /// A state with the given deck (base tile indices, draw order).  The first
    /// tile is immediately drawn into `next_tile`, exactly as
    /// `CarcassonneGameState.__init__` does (`self.deck.pop(0)`).
    pub fn from_deck(deck: Vec<u16>) -> Self {
        Self::from_deck_with_start(deck, Coord::new(6, 15))
    }

    /// As [`Self::from_deck`] but with an explicit `starting_position` — the
    /// engine's `CarcassonneGameState(starting_position=Coordinate(r, c))`
    /// constructor argument.  P5's opt-in recentring flag rides on this; the
    /// EVEN-shift constraint is enforced one level up, in
    /// [`crate::game::GameConfig`], because it is a property of the *window*
    /// (banker's rounding in `offset_from_centroid_sums`), not of the engine.
    pub fn from_deck_with_start(deck: Vec<u16>, starting_position: Coord) -> Self {
        let mut st = GameState {
            board: vec![EMPTY; (BOARD_ROWS * BOARD_COLS) as usize],
            deck,
            deck_head: 0,
            next_tile: None,
            players: 2,
            meeples: [7, 7],
            abbots: [0, 0],
            big_meeples: [0, 0],
            placed_meeples: [Vec::new(), Vec::new()],
            scores: [0, 0],
            current_player: 0,
            phase: Phase::Tiles,
            last_tile_action: None,
            open_positions: BTreeSet::new(),
            placed_coords: BTreeSet::new(),
            starting_position,
            cloister_scan_fix: false,
            cloister_completions_accelerated: 0,
            redraw_unplaceable: false,
            set_aside: Vec::new(),
        };
        st.next_tile = st.pop_deck();
        st
    }

    /// `game_wrapper.preplace_retail_start_tile` — the retail/tournament fixed
    /// start tile, pre-placed **in place** on a virgin state.
    ///
    /// Byte-for-byte the Python body (merge `5c35106`, worktree `b7d61ab`):
    ///
    /// 1. refuse a non-virgin state;
    /// 2. `pool = [next_tile] + list(deck)`, then remove the **first** entry
    ///    whose description matches — i.e. the earliest D in draw order, so
    ///    *which* copy leaves the bag is fixed by the shuffle, not by us;
    /// 3. place it UNROTATED (`base_tiles[name]`, rotation 0) at
    ///    `starting_position`, register `placed_coords` and the four in-bounds
    ///    empty neighbours in `open_positions`;
    /// 4. `deck = pool; next_tile = deck.pop(0)` — so the pre-placed tile is
    ///    gone from the bag and 71 remain to be drawn;
    /// 5. phase TILES, current_player 0, **`last_tile_action = None`** — nobody
    ///    played it, so no meeple phase and no completion scoring follows.
    ///
    /// (Python's `pool` would hold a literal `None` when `next_tile` is `None`;
    /// the `tile is not None` guard skips it, so dropping it here is
    /// behaviourally identical — and unreachable anyway on a fresh 72-tile deck.)
    pub fn preplace_start_tile(&mut self, base: u16, tile_name: &str) -> Result<(), String> {
        if !self.placed_coords.is_empty() {
            return Err("preplace_retail_start_tile requires a virgin state".to_string());
        }
        let mut pool: Vec<u16> = Vec::with_capacity(self.deck_len() + 1);
        if let Some(nt) = self.next_tile {
            pool.push(nt);
        }
        pool.extend_from_slice(self.remaining_deck());

        match pool.iter().position(|&t| t == base) {
            Some(i) => {
                pool.remove(i);
            }
            None => {
                return Err(format!(
                    "no {tile_name:?} tile in the deck — the retail start tile is a \
                     base-game tile; is TileSet.BASE enabled?"
                ))
            }
        }

        let coord = self.starting_position;
        self.set_tile(coord, tiles::tile_id(base, 0));
        self.placed_coords.insert((coord.row, coord.col));
        let (r, c) = (coord.row, coord.col);
        for (nr, nc) in [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)] {
            if nr >= 0
                && nr < BOARD_ROWS
                && nc >= 0
                && nc < BOARD_COLS
                && self.get_tile(nr, nc).is_none()
            {
                self.open_positions.insert((nr, nc));
            }
        }

        self.deck = pool;
        self.deck_head = 0;
        self.next_tile = self.pop_deck();
        self.phase = Phase::Tiles;
        self.current_player = 0;
        self.last_tile_action = None;
        Ok(())
    }

    fn pop_deck(&mut self) -> Option<u16> {
        if self.deck_head >= self.deck.len() {
            None
        } else {
            let v = self.deck[self.deck_head];
            self.deck_head += 1;
            Some(v)
        }
    }

    #[inline]
    pub fn deck_len(&self) -> usize {
        self.deck.len() - self.deck_head
    }

    /// `state.deck` as Python sees it: the **undrawn** tiles only (the Python
    /// engine `pop(0)`s, so its list shrinks; ours keeps a head index).
    #[inline]
    pub fn remaining_deck(&self) -> &[u16] {
        &self.deck[self.deck_head..]
    }

    /// Overwrite the **undrawn** tiles in place (`state.deck[:] = [...]` on the
    /// Python side) — the determinization hook. Length must match; `next_tile`
    /// and everything already placed are untouched.
    pub fn set_remaining_deck(&mut self, ids: &[u16]) -> Result<(), String> {
        if ids.len() != self.deck_len() {
            return Err(format!(
                "unseen deck length mismatch: got {}, state holds {}",
                ids.len(),
                self.deck_len()
            ));
        }
        self.deck.truncate(self.deck_head);
        self.deck.extend_from_slice(ids);
        Ok(())
    }

    /// `endgame_solver._clone_with_tile` — install an arbitrary hidden state
    /// (`st.next_tile = tile; st.deck = list(remaining)`).  Unlike
    /// [`Self::set_remaining_deck`] the length is FREE: the solver's chance node
    /// hands out a bag with one *type* removed, which shortens the deck.
    ///
    /// Everything already placed (board, meeples, scores, phase,
    /// `last_tile_action`) is untouched, exactly as the Python does by mutating
    /// two fields of a `deepcopy`d state.
    pub fn replace_hidden(&mut self, next_tile: Option<u16>, remaining: &[u16]) {
        self.next_tile = next_tile;
        self.deck.truncate(self.deck_head);
        self.deck.extend_from_slice(remaining);
    }

    #[inline]
    pub fn is_terminated(&self) -> bool {
        self.next_tile.is_none()
    }

    #[inline]
    pub fn empty_board(&self) -> bool {
        self.placed_coords.is_empty()
    }

    // --- board access -----------------------------------------------------

    /// `game_state.board[row][column]` — **including CPython's negative-index
    /// wrap** (`row == -1` reads row 34).
    ///
    /// ⚠️ Every caller reaches this with a coordinate stepped one cell off a
    /// placed tile (`opposite_edge` for cities/farms, the 3x3 for cloisters), so
    /// an index of `BOARD_ROWS` / `BOARD_COLS` is a NORMAL consequence of a
    /// region touching the last row or column.  CPython raises `IndexError`
    /// there and this port used to panic with it; that crashed live production
    /// games (three b32v64 seeds, 2026-08-22).  An index outside `[-len, len)`
    /// now reads as **`None` — "no tile there"**, which is what every caller
    /// already does with an off-board neighbour.
    ///
    /// ⛔ The `-1` wrap is NOT fixed here on purpose.  It is a scoring semantic
    /// of the engine of record (see the module header); removing it would move
    /// the rules epoch, and it is unreachable-in-effect unless the board occupies
    /// BOTH extreme rows (or columns) at once.  A fix for it belongs behind an
    /// opt-in `GameConfig` flag like `cloister_scan_fix`, not here.
    #[inline]
    pub fn board_direct(&self, row: i32, col: i32) -> Option<TileId> {
        let r = py_index(row, BOARD_ROWS)?;
        let c = py_index(col, BOARD_COLS)?;
        let v = self.board[(r * BOARD_COLS + c) as usize];
        if v == EMPTY {
            None
        } else {
            Some(v)
        }
    }

    /// `CarcassonneGameState.get_tile` — bounds-checked, `None` outside.
    #[inline]
    pub fn get_tile(&self, row: i32, col: i32) -> Option<TileId> {
        if row < 0 || col < 0 || row >= BOARD_ROWS || col >= BOARD_COLS {
            return None;
        }
        let v = self.board[(row * BOARD_COLS + col) as usize];
        if v == EMPTY {
            None
        } else {
            Some(v)
        }
    }

    /// Place `id` at `coord`.
    ///
    /// ⚠️ **The bounds check is not defensive padding — it closes a SILENT
    /// wrong-cell WRITE.**  The index is row-major (`row * BOARD_COLS + col`),
    /// so an out-of-range COLUMN with an in-range row aliases into a neighbouring
    /// row and lands *inside* the buffer: `(10, 35)` writes `(11, 0)` and
    /// `(10, -1)` writes `(9, 34)` — no panic, no error, just a tile in the wrong
    /// place and a board that disagrees with `placed_coords`.  Only a coordinate
    /// far enough out to leave the whole 1,225-cell buffer crashes, which is the
    /// case the banked-fixture replay happens to hit.
    ///
    /// Legal play cannot reach either: `possible_playing_positions` draws from
    /// `open_positions`, which is bounds-filtered on insert.  The exposure is the
    /// REPLAY path — `MirrorState.advance` applies a banked action verbatim, with
    /// no legality check — so a fixture recorded under a different `grid_rule`
    /// (`engine6` start row 6 vs `centered18` start row 18 = a 12-row shift)
    /// arrives here off-board.  Fail loudly and name the coordinate.
    #[inline]
    fn set_tile(&mut self, coord: Coord, id: TileId) {
        assert!(
            coord.row >= 0 && coord.row < BOARD_ROWS && coord.col >= 0 && coord.col < BOARD_COLS,
            "tile placement at ({}, {}) is outside the {}x{} board — a row-major \
             write there would alias a DIFFERENT in-bounds cell.  Legal play cannot \
             produce this; it means an action was replayed onto a board whose \
             geometry it was not recorded under (check grid_rule / start_row).",
            coord.row,
            coord.col,
            BOARD_ROWS,
            BOARD_COLS
        );
        self.board[(coord.row * BOARD_COLS + coord.col) as usize] = id;
    }

    // --- transitions ------------------------------------------------------

    /// `StateUpdater.apply_action_inplace` (the shared `_apply_action_to` body).
    ///
    /// ⚠️ This is the SHARED transition every consumer drives (tier1 playouts,
    /// PUCT search, the eval harness, the phone). It is untouched by L2 — see
    /// [`GameState::apply_action_unscored`] for the solver-scoped variant.
    pub fn apply_action(&mut self, action: Action) {
        self.apply_action_inner(action, true)
    }

    /// **L2 — `apply_action` with the terminal `count_final_scores` DEFERRED.**
    ///
    /// Identical to [`apply_action`] on every transition except the two that
    /// terminate the game, where the in-place object scoring is simply not run:
    /// `scores` keep their RUNNING values and `placed_meeples` keep every
    /// meeple. A caller that uses this MUST score terminals itself — the flat
    /// route `leaf::decompose_into` + `leaf::flat_base_score` reproduces exactly
    /// what the skipped `count_final_scores` would have produced, because
    /// `flat_base_score` is `running + final_award` (the P2 suite gates that
    /// equality on every position; L2's own gates re-gate it on solver-reached
    /// terminals).
    ///
    /// Nothing downstream of a solver terminal reads `scores` or
    /// `placed_meeples`: [`is_terminated`] is `next_tile.is_none()` (score- and
    /// meeple-independent) and the transposition key is only ever taken on
    /// NON-terminal nodes, which this variant does not touch. That is the whole
    /// safety argument, and it is why the substitution is scoped here instead of
    /// inside the shared [`apply_action`].
    ///
    /// [`apply_action`]: GameState::apply_action
    /// [`is_terminated`]: GameState::is_terminated
    pub fn apply_action_unscored(&mut self, action: Action) {
        self.apply_action_inner(action, false)
    }

    /// The shared body. `score_final` gates ONLY the two terminal
    /// `count_final_scores()` calls; every other effect is common to both
    /// entry points, so `apply_action`'s behaviour is unchanged by
    /// construction rather than by re-derivation.
    fn apply_action_inner(&mut self, action: Action, score_final: bool) {
        let original_phase = self.phase;
        match action {
            Action::Tile(ta) => {
                self.play_tile(ta);
                self.phase = Phase::Meeples;
            }
            Action::Meeple(ma) => self.play_meeple(ma),
            Action::Pass => {
                if original_phase == Phase::Tiles {
                    // Vendored patch (2026-04-28): the unplaceable tile is
                    // discarded, `last_tile_action` cleared, a new tile drawn,
                    // and the turn handed off.  No meeple decision is owed.
                    //
                    // F9/A3: under `redraw_unplaceable` the turn is NOT handed
                    // off — the tile is set aside (removed from the game) and
                    // the same player draws again.  Recursion is realized as a
                    // sequence of forced passes (the redrawn-and-still-
                    // unplaceable state has Pass as its only legal move), and
                    // it terminates because the bag strictly shrinks.  Deck
                    // exhausted mid-redraw falls into the same
                    // `is_terminated()` / `count_final_scores` block below, as
                    // the normal path does.  Full rationale on the Python twin.
                    self.last_tile_action = None;
                    if let Some(t) = self.next_tile {
                        self.set_aside.push(t);
                    }
                    self.draw_tile();
                    if !self.redraw_unplaceable {
                        self.next_player();
                    }
                    if score_final && self.is_terminated() {
                        self.count_final_scores();
                    }
                    return;
                }
            }
        }

        if original_phase == Phase::Meeples {
            if let Some(lta) = self.last_tile_action {
                self.remove_meeples_and_collect_points(lta.coord);
            }
            self.draw_tile();
            self.next_player();
        }

        if score_final && self.is_terminated() {
            self.count_final_scores();
        }
    }

    fn next_player(&mut self) {
        self.phase = Phase::Tiles;
        self.current_player += 1;
        if self.current_player >= self.players {
            self.current_player = 0;
        }
    }

    fn draw_tile(&mut self) {
        self.next_tile = self.pop_deck();
    }

    fn play_tile(&mut self, ta: TileAction) {
        self.set_tile(ta.coord, ta.tile);
        self.phase = Phase::Meeples;
        // last_river_rotation: base deck has no river tiles, so
        // RiverRotationUtil.get_river_rotation is always Rotation.NONE.
        debug_assert!(tiles::tile(ta.tile).river.is_empty(), "river is out of scope");
        self.last_tile_action = Some(ta);

        let (r, c) = (ta.coord.row, ta.coord.col);
        self.open_positions.remove(&(r, c));
        for (nr, nc) in [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)] {
            if nr >= 0 && nr < BOARD_ROWS && nc >= 0 && nc < BOARD_COLS && self.get_tile(nr, nc).is_none()
            {
                self.open_positions.insert((nr, nc));
            }
        }
        self.placed_coords.insert((r, c));
    }

    fn play_meeple(&mut self, ma: MeepleAction) {
        let mp = MeeplePosition {
            meeple_type: ma.meeple_type,
            coord: ma.coord,
            side: ma.side,
        };
        let cur = self.current_player;
        if !ma.remove {
            self.placed_meeples[cur].push(mp);
        } else {
            // list.remove() drops the FIRST value-equal element.
            let idx = self.placed_meeples[cur]
                .iter()
                .position(|m| *m == mp)
                .expect("MeepleAction(remove=True) for a meeple that is not placed");
            self.placed_meeples[cur].remove(idx);
        }

        let delta = if ma.remove { 1 } else { -1 };
        match ma.meeple_type {
            MeepleType::Normal | MeepleType::Farmer => self.meeples[cur] += delta,
            MeepleType::Abbot => {
                if ma.remove {
                    let pts = self.chapel_or_flowers_points(ma.coord);
                    self.scores[cur] += pts;
                }
                self.abbots[cur] += delta;
            }
            MeepleType::Big | MeepleType::BigFarmer => self.big_meeples[cur] += delta,
        }
    }

    // --- scoring ----------------------------------------------------------

    /// `PointsCollector._legacy_scan_cells` — the cells the LEGACY (drifting)
    /// cloister scan would visit for this placement.  Pure enumeration, no
    /// scoring; called only when `cloister_scan_fix` is on, to count the
    /// completions the drift would have missed.
    fn legacy_scan_cells(&self, coordinate: Coord) -> HashSet<(i32, i32)> {
        let mut visited = HashSet::new();
        let mut anchor = coordinate;
        for row in (coordinate.row - 1)..=(coordinate.row + 1) {
            for column in (anchor.col - 1)..=(anchor.col + 1) {
                if self.get_tile(row, column).is_none() {
                    continue;
                }
                anchor = Coord::new(row, column);
                visited.insert((row, column));
            }
        }
        visited
    }

    /// `PointsCollector.remove_meeples_and_collect_points`.
    pub fn remove_meeples_and_collect_points(&mut self, coordinate: Coord) {
        // --- finished cities ---
        for city in self.find_cities(coordinate, &CARDINALS) {
            if !city.finished {
                continue;
            }
            let meeples = self.city_find_meeples(&city);
            let counts = meeple_counts_per_player(&meeples);
            if counts.iter().sum::<i64>() == 0 {
                continue;
            }
            let winners = winning_players(&counts);
            if !winners.is_empty() {
                let pts = self.count_city_points(&city);
                for w in &winners {
                    self.scores[*w] += pts;
                }
            }
            self.remove_meeples(&meeples);
        }

        // --- finished roads (no dedup: see the module note) ---
        for road in self.find_roads(coordinate) {
            if !road.finished {
                continue;
            }
            let meeples = self.road_find_meeples(&road);
            let counts = meeple_counts_per_player(&meeples);
            if counts.iter().sum::<i64>() == 0 {
                continue;
            }
            let winners = winning_players(&counts);
            if !winners.is_empty() {
                let pts = self.count_road_points(&road);
                for w in &winners {
                    self.scores[*w] += pts;
                }
            }
            self.remove_meeples(&meeples);
        }

        // --- finished cloisters ---
        //
        // QUIRK, ported verbatim: the Python loop REBINDS its `coordinate`
        // local to the last non-empty cell it saw, and the *inner* `range(...)`
        // is re-evaluated once per outer iteration — so row `r` scans the
        // columns around whatever tile was last touched, not around the
        // original coordinate.  The outer row range is evaluated once, from the
        // original coordinate.
        //
        // F9-A2: `cloister_scan_fix` (DEFAULT FALSE) stops the rebinding —
        // `anchor` is the loop bound, `scan` is the cell.  Mirrors the Python
        // `PointsCollector.remove_meeples_and_collect_points` split exactly,
        // including `legacy_scan_cells` for the event counter.
        let fix = self.cloister_scan_fix;
        let legacy_visited: Option<HashSet<(i32, i32)>> =
            if fix { Some(self.legacy_scan_cells(coordinate)) } else { None };
        let row_lo = coordinate.row - 1;
        let row_hi = coordinate.row + 1;
        let mut anchor = coordinate;
        for row in row_lo..=row_hi {
            let col_lo = anchor.col - 1;
            let col_hi = anchor.col + 1;
            for column in col_lo..=col_hi {
                let tid = match self.get_tile(row, column) {
                    None => continue,
                    Some(t) => t,
                };
                let tile = tiles::tile_play(tid);
                let scan = Coord::new(row, column);
                if !fix {
                    anchor = scan; // LEGACY: the rebinding quirk (RF-D-1)
                }
                let meeple_of_player = self.position_contains_meeple(scan, Side::Center);
                if (tile.chapel || tile.flowers) && meeple_of_player.is_some() {
                    let points = self.chapel_or_flowers_points(scan);
                    if points == 9 {
                        if let Some(seen) = legacy_visited.as_ref() {
                            if !seen.contains(&(row, column)) {
                                self.cloister_completions_accelerated += 1;
                            }
                        }
                        let p = meeple_of_player.unwrap();
                        self.scores[p] += points;
                        let mut per_player: [Vec<MeeplePosition>; 2] = [Vec::new(), Vec::new()];
                        for mp in &self.placed_meeples[p] {
                            if mp.coord == scan && mp.side == Side::Center {
                                per_player[p].push(*mp);
                            }
                        }
                        self.remove_meeples(&per_player);
                    }
                }
            }
        }
    }

    /// `PointsCollector.count_final_scores`.
    ///
    /// The Python drain is `set(placed_meeples).pop()` — an order that is not
    /// reproducible across processes (`MeeplePosition.__hash__` bottoms out in
    /// identity-hashed enum members).  `scripts/rustport/
    /// property_count_final_scores_order.py` measures that the outcome is
    /// order-invariant; this port drains in `placed_meeples` insertion order
    /// over a *snapshot*, matching the Python snapshot semantics (a meeple
    /// removed by an earlier component is still visited, and then finds no
    /// meeples).
    pub fn count_final_scores(&mut self) {
        for player in 0..self.players {
            let mut snapshot: Vec<MeeplePosition> = Vec::new();
            for mp in &self.placed_meeples[player] {
                if !snapshot.contains(mp) {
                    snapshot.push(*mp);
                }
            }
            for mp in snapshot {
                let tid = self
                    .board_direct(mp.coord.row, mp.coord.col)
                    .expect("meeple on an empty cell");
                let terrain = tiles::tile_play(tid).get_type(mp.side);

                if terrain == Some(TerrainType::City) {
                    let city = self.find_city((mp.coord.row, mp.coord.col, mp.side));
                    let meeples = self.city_find_meeples(&city);
                    let counts = meeple_counts_per_player(&meeples);
                    let winners = winning_players(&counts);
                    if !winners.is_empty() {
                        let pts = self.count_city_points(&city);
                        for w in &winners {
                            self.scores[*w] += pts;
                        }
                    }
                    self.remove_meeples(&meeples);
                    continue;
                }

                if terrain == Some(TerrainType::Road) {
                    let road = self.find_road((mp.coord.row, mp.coord.col, mp.side));
                    let meeples = self.road_find_meeples(&road);
                    let counts = meeple_counts_per_player(&meeples);
                    let winners = winning_players(&counts);
                    if !winners.is_empty() {
                        let pts = self.count_road_points(&road);
                        for w in &winners {
                            self.scores[*w] += pts;
                        }
                    }
                    self.remove_meeples(&meeples);
                    continue;
                }

                if terrain == Some(TerrainType::Chapel) || terrain == Some(TerrainType::Flowers) {
                    let pts = self.chapel_or_flowers_points(mp.coord);
                    self.scores[player] += pts;
                    let mut per_player: [Vec<MeeplePosition>; 2] = [Vec::new(), Vec::new()];
                    per_player[player].push(mp);
                    self.remove_meeples(&per_player);
                    continue;
                }

                if mp.meeple_type == MeepleType::Farmer || mp.meeple_type == MeepleType::BigFarmer {
                    let farm = match self.find_farm_by_coordinate(mp.coord, mp.side) {
                        Some(f) => f,
                        None => continue, // Python returns None -> AttributeError; unreachable
                    };
                    let meeples = self.farm_find_meeples(&farm);
                    let counts = meeple_counts_per_player(&meeples);
                    let winners = winning_players(&counts);
                    if !winners.is_empty() {
                        let pts = self.count_farm_points(&farm);
                        for w in &winners {
                            self.scores[*w] += pts;
                        }
                    }
                    self.remove_meeples(&meeples);
                    continue;
                }
            }
        }
    }

    /// `scores[player] - scores[opp]` at end of game — the exact terminal leaf
    /// (`flat_leaf.flat_base_score`), computed engine-exactly on a snapshot.
    pub fn flat_base_score(&self, player: usize) -> i64 {
        assert_eq!(self.players, 2, "flat_base_score is 2-player only");
        let mut snap = self.clone();
        snap.count_final_scores();
        let opp = 1 - player;
        snap.scores[player] - snap.scores[opp]
    }

    fn count_city_points(&self, city: &City) -> i64 {
        let mut points = 0i64;
        let mut has_cathedral = false;
        let mut coordinates: Vec<Coord> = Vec::new();
        let preg = tiles::play_registry();
        for &(r, c, _s) in &city.positions {
            let tid = self.board_direct(r, c).expect("city position on an empty cell");
            if preg[tid as usize].has_inn {
                has_cathedral = true;
            }
            let coord = Coord::new(r, c);
            if !coordinates.contains(&coord) {
                coordinates.push(coord);
            }
        }
        if !city.finished && has_cathedral {
            return 0;
        }
        for coord in coordinates {
            let tid = self.board_direct(coord.row, coord.col).unwrap();
            let tile = &preg[tid as usize];
            if tile.shield {
                points += if has_cathedral {
                    6
                } else if city.finished {
                    4
                } else {
                    2
                };
            } else {
                points += if has_cathedral {
                    3
                } else if city.finished {
                    2
                } else {
                    1
                };
            }
        }
        points
    }

    fn count_road_points(&self, road: &Road) -> i64 {
        let mut has_inn = false;
        let mut coordinates: Vec<Coord> = Vec::new();
        let preg = tiles::play_registry();
        for &(r, c, _s) in &road.positions {
            let tid = self.board_direct(r, c).expect("road position on an empty cell");
            if preg[tid as usize].has_inn {
                has_inn = true;
            }
            let coord = Coord::new(r, c);
            if !coordinates.contains(&coord) {
                coordinates.push(coord);
            }
        }
        if !road.finished && has_inn {
            return 0;
        }
        coordinates.len() as i64 * if has_inn { 2 } else { 1 }
    }

    /// `PointsCollector.chapel_or_flowers_points` — a 3x3 count of placed tiles,
    /// via **direct** board indexing (so `row == -1` wraps, per CPython).
    fn chapel_or_flowers_points(&self, coordinate: Coord) -> i64 {
        let mut points = 0;
        for row in (coordinate.row - 1)..=(coordinate.row + 1) {
            for column in (coordinate.col - 1)..=(coordinate.col + 1) {
                if self.board_direct(row, column).is_some() {
                    points += 1;
                }
            }
        }
        points
    }

    fn count_farm_points(&self, farm: &Farm) -> i64 {
        // Dedup touched cities by their POSITION SET (the 2026-06-02 fix).
        let mut counted: HashSet<Vec<CoordSide>> = HashSet::new();
        let mut points = 0i64;
        // A2: the farm's `city_sides` come off the flat table into a fixed
        // stack array — same sides, same order — instead of a heap `Vec` clone
        // per farm node.
        let mut sides = [Side::Top; tiles::MAX_CSIDES];
        for node in &farm.nodes {
            let tid = self.board_direct(node.coord.row, node.coord.col).unwrap();
            let f = &tiles::tile_flat(tid).farms[node.slot as usize];
            let n = f.n_csides as usize;
            for (i, &b) in f.csides().iter().enumerate() {
                sides[i] = tiles::SIDE_FROM_U8[b as usize];
            }
            for city in self.find_cities(node.coord, &sides[..n]) {
                if !counted.insert(city.positions.clone()) {
                    continue;
                }
                if city.finished {
                    points += 3;
                }
            }
        }
        points
    }

    // --- meeple helpers ---------------------------------------------------

    fn position_contains_meeple(&self, coord: Coord, side: Side) -> Option<usize> {
        for player in 0..self.players {
            if self.placed_meeples[player]
                .iter()
                .any(|m| m.coord == coord && m.side == side)
            {
                return Some(player);
            }
        }
        None
    }

    fn remove_meeples(&mut self, meeples: &[Vec<MeeplePosition>; 2]) {
        for player in 0..self.players {
            for mp in &meeples[player] {
                let idx = self.placed_meeples[player]
                    .iter()
                    .position(|m| m == mp)
                    .expect("remove_meeple: not placed (Python would raise ValueError)");
                self.placed_meeples[player].remove(idx);
                match mp.meeple_type {
                    MeepleType::Normal | MeepleType::Farmer => self.meeples[player] += 1,
                    MeepleType::Abbot => self.abbots[player] += 1,
                    MeepleType::Big | MeepleType::BigFarmer => self.big_meeples[player] += 1,
                }
            }
        }
    }

    // --- cities -----------------------------------------------------------

    fn cities_for_position(&self, pos: CoordSide) -> Vec<CoordSide> {
        let (r, c, side) = pos;
        let mut out = Vec::new();
        let tid = match self.board_direct(r, c) {
            None => return out,
            Some(t) => t,
        };
        let tf = tiles::tile_flat(tid);
        let sb = side as u8;
        for gi in 0..tf.n_city_groups as usize {
            let group = tf.city_group(gi);
            if group.contains(&sb) {
                for &s in group {
                    out.push((r, c, tiles::SIDE_FROM_U8[s as usize]));
                }
            }
        }
        out
    }

    /// `CityUtil.find_city` — symmetric BFS to closure (start-independent, so
    /// the pop order of the Python worklist cannot matter).
    pub fn find_city(&self, pos: CoordSide) -> City {
        let (cities, explored) =
            flood(self.cities_for_position(pos), |e| self.cities_for_position(e));
        let finished = explored.len() == cities.len();
        let mut positions: Vec<CoordSide> = cities.into_iter().collect();
        positions.sort();
        City { positions, finished }
    }

    /// `CityUtil.find_cities` — deduped by city-position set (Python `City` has
    /// value equality).
    pub fn find_cities(&self, coord: Coord, sides: &[Side]) -> Vec<City> {
        let mut out: Vec<City> = Vec::new();
        let tid = match self.board_direct(coord.row, coord.col) {
            None => return out,
            Some(t) => t,
        };
        let tile = tiles::tile_play(tid);
        for &side in sides {
            if tile.is_type(side, TerrainType::City) {
                let city = self.find_city((coord.row, coord.col, side));
                if !out.iter().any(|c| c.positions == city.positions) {
                    out.push(city);
                }
            }
        }
        out
    }

    fn city_find_meeples(&self, city: &City) -> [Vec<MeeplePosition>; 2] {
        let mut out: [Vec<MeeplePosition>; 2] = [Vec::new(), Vec::new()];
        for &(r, c, s) in &city.positions {
            for player in 0..self.players {
                for mp in &self.placed_meeples[player] {
                    if mp.coord.row == r && mp.coord.col == c && mp.side == s {
                        out[player].push(*mp);
                    }
                }
            }
        }
        out
    }

    fn city_contains_meeples(&self, city: &City) -> bool {
        for &(r, c, s) in &city.positions {
            for player in 0..self.players {
                if self.placed_meeples[player]
                    .iter()
                    .any(|m| m.coord.row == r && m.coord.col == c && m.side == s)
                {
                    return true;
                }
            }
        }
        false
    }

    // --- roads ------------------------------------------------------------

    fn outgoing_roads_for_position(&self, pos: CoordSide) -> Vec<CoordSide> {
        let (r, c, side) = pos;
        let mut out = Vec::new();
        let tid = match self.get_tile(r, c) {
            None => return out,
            Some(t) => t,
        };
        let tf = tiles::tile_flat(tid);
        let sb = side as u8;
        const CENTER: u8 = Side::Center as u8;
        for i in 0..tf.n_road as usize {
            let (a, b) = (tf.road[2 * i], tf.road[2 * i + 1]);
            if a == sb || b == sb {
                if a != CENTER {
                    out.push((r, c, tiles::SIDE_FROM_U8[a as usize]));
                }
                if b != CENTER {
                    out.push((r, c, tiles::SIDE_FROM_U8[b as usize]));
                }
            }
        }
        out
    }

    pub fn find_road(&self, pos: CoordSide) -> Road {
        let (roads, explored) = flood(self.outgoing_roads_for_position(pos), |e| {
            self.outgoing_roads_for_position(e)
        });
        let finished = explored.len() == roads.len();
        let mut positions: Vec<CoordSide> = roads.into_iter().collect();
        positions.sort();
        Road { positions, finished }
    }

    /// `RoadUtil.find_roads` — **not** deduped (Python `Road` lacks value
    /// equality, so its `set()` keeps one entry per road-typed side).
    pub fn find_roads(&self, coord: Coord) -> Vec<Road> {
        let mut out = Vec::new();
        let tid = match self.board_direct(coord.row, coord.col) {
            None => return out,
            Some(t) => t,
        };
        let tile = tiles::tile_play(tid);
        for &side in &CARDINALS {
            if tile.is_type(side, TerrainType::Road) {
                out.push(self.find_road((coord.row, coord.col, side)));
            }
        }
        out
    }

    fn road_find_meeples(&self, road: &Road) -> [Vec<MeeplePosition>; 2] {
        let mut out: [Vec<MeeplePosition>; 2] = [Vec::new(), Vec::new()];
        for &(r, c, s) in &road.positions {
            for player in 0..self.players {
                for mp in &self.placed_meeples[player] {
                    if mp.coord.row == r && mp.coord.col == c && mp.side == s {
                        out[player].push(*mp);
                    }
                }
            }
        }
        out
    }

    fn road_contains_meeples(&self, road: &Road) -> bool {
        for &(r, c, s) in &road.positions {
            for player in 0..self.players {
                if self.placed_meeples[player]
                    .iter()
                    .any(|m| m.coord.row == r && m.coord.col == c && m.side == s)
                {
                    return true;
                }
            }
        }
        false
    }

    // --- farms ------------------------------------------------------------

    fn farm_for_position(&self, coord: Coord, fs: FarmerSide) -> Option<FarmNode> {
        let tid = self.board_direct(coord.row, coord.col)?;
        let fsb = fs as u8;
        for (slot, fc) in tiles::tile_flat(tid).farms().iter().enumerate() {
            if fc.tconn().contains(&fsb) {
                return Some(FarmNode {
                    coord,
                    slot: slot as u8,
                });
            }
        }
        None
    }

    /// `FarmUtil.find_farm` — complete, start-independent component DFS.
    pub fn find_farm(&self, start: FarmNode) -> Farm {
        let mut component: HashSet<FarmNode> = HashSet::new();
        component.insert(start);
        let mut stack = vec![start];
        while let Some(node) = stack.pop() {
            let tid = self.board_direct(node.coord.row, node.coord.col).unwrap();
            let conns = tiles::tile_flat(tid).farms[node.slot as usize].tconn();
            for &fsb in conns {
                let fs = tiles::FARMER_SIDE_FROM_U8[fsb as usize];
                let (ncoord, nfs) = farmer_opposite_edge(node.coord, fs);
                if let Some(neighbor) = self.farm_for_position(ncoord, nfs) {
                    if component.insert(neighbor) {
                        stack.push(neighbor);
                    }
                }
            }
        }
        let mut nodes: Vec<FarmNode> = component.into_iter().collect();
        nodes.sort();
        Farm { nodes }
    }

    pub fn find_farm_by_coordinate(&self, coord: Coord, side: Side) -> Option<Farm> {
        let tid = self.get_tile(coord.row, coord.col)?;
        let sb = side as u8;
        for (slot, fc) in tiles::tile_flat(tid).farms().iter().enumerate() {
            if fc.fpos().contains(&sb) {
                return Some(self.find_farm(FarmNode {
                    coord,
                    slot: slot as u8,
                }));
            }
        }
        None
    }

    fn farm_find_meeples(&self, farm: &Farm) -> [Vec<MeeplePosition>; 2] {
        let mut out: [Vec<MeeplePosition>; 2] = [Vec::new(), Vec::new()];
        for node in &farm.nodes {
            let tid = self.board_direct(node.coord.row, node.coord.col).unwrap();
            // `fpos()` is the LIVE slice, so an empty `farmer_positions` still
            // panics here exactly as `farmer_positions[0]` did.
            let fp = tiles::SIDE_FROM_U8
                [tiles::tile_flat(tid).farms[node.slot as usize].fpos()[0] as usize];
            for player in 0..self.players {
                for mp in &self.placed_meeples[player] {
                    if mp.coord == node.coord && mp.side == fp {
                        out[player].push(*mp);
                    }
                }
            }
        }
        out
    }

    fn farm_has_meeples(&self, farm: &Farm) -> bool {
        let m = self.farm_find_meeples(farm);
        !m[0].is_empty() || !m[1].is_empty()
    }

    // --- legality / move generation ---------------------------------------

    /// `TilePositionFinder.possible_playing_positions` — `(row, col)`-sorted
    /// open positions x rotations 0..3.
    pub fn possible_playing_positions(&self, base: u16) -> Vec<(Coord, u8)> {
        if self.empty_board() {
            return vec![(self.starting_position, 0)];
        }
        let mut out = Vec::new();
        // A2: the play table is hoisted out of BOTH loops (one `OnceLock` load
        // per call instead of one per rotation), and the four neighbour lookups
        // out of the rotation loop — they do not depend on `turns`.  Neither
        // moves an observable: `get_tile` is a pure read and the emission order
        // over `(open_positions, turns)` is unchanged.
        let preg = tiles::play_registry();
        for &(row, col) in &self.open_positions {
            let top = self.get_tile(row - 1, col);
            let bottom = self.get_tile(row + 1, col);
            let left = self.get_tile(row, col - 1);
            let right = self.get_tile(row, col + 1);
            for turns in 0u8..4 {
                let center = &preg[tile_id(base, turns) as usize];
                if fits_flat(center, top, bottom, left, right) {
                    out.push((Coord::new(row, col), turns));
                }
            }
        }
        out
    }

    /// `ActionUtil.get_possible_actions`.
    pub fn possible_actions(&self) -> Vec<Action> {
        let mut actions = Vec::new();
        match self.phase {
            Phase::Tiles => {
                let base = match self.next_tile {
                    None => return actions,
                    Some(b) => b,
                };
                let positions = self.possible_playing_positions(base);
                if positions.is_empty() {
                    actions.push(Action::Pass);
                } else {
                    for (coord, turns) in positions {
                        actions.push(Action::Tile(TileAction {
                            tile: tile_id(base, turns),
                            coord,
                            rotations: turns,
                        }));
                    }
                }
            }
            Phase::Meeples => {
                actions.extend(self.possible_meeple_actions());
                actions.push(Action::Pass);
            }
        }
        actions
    }

    fn possible_meeple_actions(&self) -> Vec<Action> {
        let cur = self.current_player;
        let lta = self.last_tile_action.expect("MEEPLES phase without a last tile action");
        let mut out = Vec::new();

        let meeple_positions = self.possible_meeple_positions(&lta);
        // FARMERS is always in scope; NORMAL_MEEPLES_CAN_USE_FLOWERS is not.
        let farmer_positions = self.possible_farmer_positions(&lta);

        if self.meeples[cur] > 0 {
            for &(coord, side) in &meeple_positions {
                out.push(Action::Meeple(MeepleAction {
                    meeple_type: MeepleType::Normal,
                    coord,
                    side,
                    remove: false,
                }));
            }
            for &(coord, side) in &farmer_positions {
                out.push(Action::Meeple(MeepleAction {
                    meeple_type: MeepleType::Farmer,
                    coord,
                    side,
                    remove: false,
                }));
            }
        }
        if self.big_meeples[cur] > 0 {
            for &(coord, side) in &meeple_positions {
                out.push(Action::Meeple(MeepleAction {
                    meeple_type: MeepleType::Big,
                    coord,
                    side,
                    remove: false,
                }));
            }
            for &(coord, side) in &farmer_positions {
                out.push(Action::Meeple(MeepleAction {
                    meeple_type: MeepleType::BigFarmer,
                    coord,
                    side,
                    remove: false,
                }));
            }
        }
        if self.abbots[cur] > 0 {
            let tile = tiles::tile_play(lta.tile);
            if tile.chapel || tile.flowers {
                out.push(Action::Meeple(MeepleAction {
                    meeple_type: MeepleType::Abbot,
                    coord: lta.coord,
                    side: Side::Center,
                    remove: false,
                }));
            }
        }
        for mp in &self.placed_meeples[cur] {
            if mp.meeple_type == MeepleType::Abbot {
                out.push(Action::Meeple(MeepleAction {
                    meeple_type: MeepleType::Abbot,
                    coord: mp.coord,
                    side: mp.side,
                    remove: true,
                }));
            }
        }
        out
    }

    fn possible_meeple_positions(&self, lta: &TileAction) -> Vec<(Coord, Side)> {
        let mut out = Vec::new();
        let tile = tiles::tile_play(lta.tile);
        if tile.chapel {
            out.push((lta.coord, Side::Center));
        }
        // NORMAL_MEEPLES_CAN_USE_FLOWERS is not in the locked supplementary set.
        for &side in &CARDINALS {
            if tile.is_type(side, TerrainType::City) {
                let city = self.find_city((lta.coord.row, lta.coord.col, side));
                if self.city_contains_meeples(&city) {
                    continue;
                }
                out.push((lta.coord, side));
            }
            if tile.is_type(side, TerrainType::Road) {
                let road = self.find_road((lta.coord.row, lta.coord.col, side));
                if self.road_contains_meeples(&road) {
                    continue;
                }
                out.push((lta.coord, side));
            }
        }
        out
    }

    fn possible_farmer_positions(&self, lta: &TileAction) -> Vec<(Coord, Side)> {
        let mut out = Vec::new();
        let tile = tiles::tile_flat(lta.tile);
        for (slot, fc) in tile.farms().iter().enumerate() {
            let farm = self.find_farm(FarmNode {
                coord: lta.coord,
                slot: slot as u8,
            });
            if self.farm_has_meeples(&farm) {
                continue;
            }
            out.push((lta.coord, tiles::SIDE_FROM_U8[fc.fpos()[0] as usize]));
        }
        out
    }
}

// ---------------------------------------------------------------------------
// Free functions
// ---------------------------------------------------------------------------

/// CPython list indexing **as an `Option`**: negatives wrap (`-1` -> `len - 1`),
/// and an index outside `[-len, len)` — where CPython raises `IndexError` —
/// yields `None`.
///
/// The wrap half is load-bearing and bit-exact with the Python engine.  The
/// `None` half is the 2026-08-23 board-bounds fix: the sole caller
/// ([`GameState::board_direct`]) is only ever asked about a cell one step off a
/// placed tile, and "off the board" means "no tile", not "abort the game".
#[inline]
fn py_index(i: i32, len: i32) -> Option<i32> {
    let j = if i < 0 { i + len } else { i };
    if j < 0 || j >= len {
        return None;
    }
    Some(j)
}

/// The shared body of `CityUtil.find_city` and `RoadUtil.find_road`: grow the
/// member set to closure across `opposite_edge`, tracking every edge visited.
///
/// Mirrors the Python control flow exactly, including the two details that
/// decide `finished`:
///  * `open_edges` is seeded from **every** member's opposite edge — even ones
///    that are themselves members — and every seed is expanded;
///  * `explored` = members ∪ every opposite edge ever seen, so
///    `len(explored) == len(members)` iff the region has no open border.
///
/// The result is a closure and therefore independent of the pop order, which is
/// why the Python `set.pop()` cannot leak nondeterminism here.
fn flood<F>(seed: Vec<CoordSide>, expand: F) -> (HashSet<CoordSide>, HashSet<CoordSide>)
where
    F: Fn(CoordSide) -> Vec<CoordSide>,
{
    let members: HashSet<CoordSide> = seed.into_iter().collect();
    let mut explored: HashSet<CoordSide> = members.clone();
    let mut members = members;
    let open: HashSet<CoordSide> = members.iter().map(|&m| opposite_edge(m)).collect();
    let mut frontier: Vec<CoordSide> = open.iter().copied().collect();
    explored.extend(open.iter().copied());

    while let Some(edge) = frontier.pop() {
        let fresh = expand(edge);
        for m in &fresh {
            members.insert(*m);
        }
        let new_open: HashSet<CoordSide> = fresh.iter().map(|&m| opposite_edge(m)).collect();
        for m in &fresh {
            explored.insert(*m);
        }
        for e in new_open {
            if explored.insert(e) {
                frontier.push(e);
            }
        }
    }
    (members, explored)
}

/// `CityUtil.opposite_edge` / `RoadUtil.opposite_edge` (identical bodies).
#[inline]
pub fn opposite_edge(pos: CoordSide) -> CoordSide {
    let (r, c, side) = pos;
    match side {
        Side::Top => (r - 1, c, Side::Bottom),
        Side::Right => (r, c + 1, Side::Left),
        Side::Bottom => (r + 1, c, Side::Top),
        Side::Left => (r, c - 1, Side::Right),
        other => panic!("opposite_edge on a non-cardinal side {other:?} (Python returns None)"),
    }
}

/// `FarmUtil.opposite_edge` — crosses the shared border of two tiles.
#[inline]
pub fn farmer_opposite_edge(coord: Coord, fs: FarmerSide) -> (Coord, FarmerSide) {
    let opp = fs.opposite();
    match fs.get_side() {
        Side::Top => (Coord::new(coord.row - 1, coord.col), opp),
        Side::Right => (Coord::new(coord.row, coord.col + 1), opp),
        Side::Bottom => (Coord::new(coord.row + 1, coord.col), opp),
        Side::Left => (Coord::new(coord.row, coord.col - 1), opp),
        other => panic!("farmer side on a non-cardinal edge {other:?}"),
    }
}

/// `PointsCollector.get_meeple_counts_per_player` (BIG meeples count 2).
pub fn meeple_counts_per_player(meeples: &[Vec<MeeplePosition>; 2]) -> [i64; 2] {
    let mut out = [0i64; 2];
    for p in 0..2 {
        out[p] = meeples[p]
            .iter()
            .map(|m| {
                if m.meeple_type == MeepleType::Big || m.meeple_type == MeepleType::BigFarmer {
                    2
                } else {
                    1
                }
            })
            .sum();
    }
    out
}

/// `PointsCollector.get_winning_players` — **every** player tied for the most
/// meeples scores full points (the vendored fix; upstream awarded nobody).
pub fn winning_players(counts: &[i64; 2]) -> Vec<usize> {
    let max = *counts.iter().max().unwrap();
    if max == 0 {
        return Vec::new();
    }
    (0..counts.len()).filter(|&i| counts[i] == max).collect()
}

/// `TileFitter.fits` — grass, cities and roads must all agree with every
/// placed neighbour, and at least one neighbour must exist.
pub fn fits(
    center: &RotTile,
    top: Option<TileId>,
    bottom: Option<TileId>,
    left: Option<TileId>,
    right: Option<TileId>,
) -> bool {
    if top.is_none() && right.is_none() && bottom.is_none() && left.is_none() {
        return false;
    }
    let t = top.map(tiles::tile);
    let b = bottom.map(tiles::tile);
    let l = left.map(tiles::tile);
    let r = right.map(tiles::tile);

    // grass_fits
    for &side in &center.grass {
        let bad = match side {
            Side::Left => l.is_some_and(|n| !n.grass.contains(&Side::Right)),
            Side::Right => r.is_some_and(|n| !n.grass.contains(&Side::Left)),
            Side::Top => t.is_some_and(|n| !n.grass.contains(&Side::Bottom)),
            Side::Bottom => b.is_some_and(|n| !n.grass.contains(&Side::Top)),
            _ => false,
        };
        if bad {
            return false;
        }
    }
    // cities_fit
    for &side in &center.city_sides_set {
        let bad = match side {
            Side::Left => l.is_some_and(|n| !n.city_sides_set.contains(&Side::Right)),
            Side::Right => r.is_some_and(|n| !n.city_sides_set.contains(&Side::Left)),
            Side::Top => t.is_some_and(|n| !n.city_sides_set.contains(&Side::Bottom)),
            Side::Bottom => b.is_some_and(|n| !n.city_sides_set.contains(&Side::Top)),
            _ => false,
        };
        if bad {
            return false;
        }
    }
    // roads_fit
    for &side in &center.road_ends {
        let bad = match side {
            Side::Left => l.is_some_and(|n| !n.road_ends.contains(&Side::Right)),
            Side::Right => r.is_some_and(|n| !n.road_ends.contains(&Side::Left)),
            Side::Top => t.is_some_and(|n| !n.road_ends.contains(&Side::Bottom)),
            Side::Bottom => b.is_some_and(|n| !n.road_ends.contains(&Side::Top)),
            _ => false,
        };
        if bad {
            return false;
        }
    }
    // rivers_fit: `len(center.get_river_ends()) == 0 -> True` for the base deck.
    assert!(center.river_ends.is_empty(), "river tiles are out of scope for v1");
    true
}

/// One edge-fit conjunct, on cardinal bitmasks.
///
/// `nbrs[i]` is the mask of the neighbour across cardinal `i` (`Top`, `Right`,
/// `Bottom`, `Left` — discriminants 0..4), or `None` if that cell is empty.  A
/// cardinal `i` present in `center` demands `(i + 2) % 4` in that neighbour;
/// non-cardinal sides carry no bit, which is the `_ => false` arm of the
/// object-path `match` they replace.  Iteration order is not observable — the
/// answer is a conjunction of independent per-side tests.
#[inline]
fn masks_fit(center: u8, nbrs: &[Option<u8>; tiles::N_CARDINALS]) -> bool {
    for i in 0..tiles::N_CARDINALS as u8 {
        if center & (1 << i) == 0 {
            continue;
        }
        if let Some(m) = nbrs[i as usize] {
            if m & (1 << ((i + 2) % tiles::N_CARDINALS as u8)) == 0 {
                return false;
            }
        }
    }
    true
}

/// [`fits`] on the flat play table — bit-for-bit the same predicate, with the
/// three `Vec<Side>` membership walks replaced by `u8` mask tests.
///
/// Pinned against [`fits`] by `engine::flat_tests::fits_flat_matches_fits_*`
/// (exhaustive over single-neighbour boards, randomized over full quadruples).
pub fn fits_flat(
    center: &tiles::TilePlayFlat,
    top: Option<TileId>,
    bottom: Option<TileId>,
    left: Option<TileId>,
    right: Option<TileId>,
) -> bool {
    if top.is_none() && right.is_none() && bottom.is_none() && left.is_none() {
        return false;
    }
    let preg = tiles::play_registry();
    let at = |o: Option<TileId>| o.map(|id| &preg[id as usize]);
    // Index by cardinal discriminant: 0 Top, 1 Right, 2 Bottom, 3 Left.
    let nb = [at(top), at(right), at(bottom), at(left)];

    let grass = [
        nb[0].map(|t| t.grass_mask),
        nb[1].map(|t| t.grass_mask),
        nb[2].map(|t| t.grass_mask),
        nb[3].map(|t| t.grass_mask),
    ];
    if !masks_fit(center.grass_mask, &grass) {
        return false;
    }
    let city = [
        nb[0].map(|t| t.city_side_mask),
        nb[1].map(|t| t.city_side_mask),
        nb[2].map(|t| t.city_side_mask),
        nb[3].map(|t| t.city_side_mask),
    ];
    if !masks_fit(center.city_side_mask, &city) {
        return false;
    }
    let road = [
        nb[0].map(|t| t.road_end_mask),
        nb[1].map(|t| t.road_end_mask),
        nb[2].map(|t| t.road_end_mask),
        nb[3].map(|t| t.road_end_mask),
    ];
    if !masks_fit(center.road_end_mask, &road) {
        return false;
    }
    assert!(center.river_ends_empty, "river tiles are out of scope for v1");
    true
}

/// Debug aid: a map from farm node to its component id (not used in the hot path).
pub fn farm_components(state: &GameState) -> HashMap<FarmNode, usize> {
    let mut out = HashMap::new();
    let mut next = 0usize;
    for &(r, c) in &state.placed_coords {
        let tid = state.board_direct(r, c).unwrap();
        for slot in 0..tiles::tile(tid).farms.len() {
            let node = FarmNode {
                coord: Coord::new(r, c),
                slot: slot as u8,
            };
            if out.contains_key(&node) {
                continue;
            }
            let farm = state.find_farm(node);
            for n in farm.nodes {
                out.insert(n, next);
            }
            next += 1;
        }
    }
    out
}
