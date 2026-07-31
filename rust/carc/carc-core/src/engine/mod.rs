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
//! * **`remove_meeples_and_collect_points` rebinds its `coordinate` local
//!   inside the cloister scan**, so each outer row iteration re-derives its
//!   column range from the *last tile seen*.  See
//!   [`GameState::remove_meeples_and_collect_points`].
//! * **`find_roads` does not dedup** (Python `Road` has no `__eq__`/`__hash__`,
//!   so `set()` keeps one entry per road-typed side); `find_cities` does
//!   (Python `City` has value equality).

use std::collections::{BTreeSet, HashMap, HashSet};

use crate::tiles::{self, tile_id, FarmerSide, RotTile, Side, TerrainType, TileId};

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
}

impl GameState {
    /// A state with the given deck (base tile indices, draw order).  The first
    /// tile is immediately drawn into `next_tile`, exactly as
    /// `CarcassonneGameState.__init__` does (`self.deck.pop(0)`).
    pub fn from_deck(deck: Vec<u16>) -> Self {
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
            starting_position: Coord::new(6, 15),
        };
        st.next_tile = st.pop_deck();
        st
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
    /// wrap**.  Out-of-range indices panic, mirroring `IndexError`.
    #[inline]
    pub fn board_direct(&self, row: i32, col: i32) -> Option<TileId> {
        let r = py_index(row, BOARD_ROWS, "row");
        let c = py_index(col, BOARD_COLS, "column");
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

    #[inline]
    fn set_tile(&mut self, coord: Coord, id: TileId) {
        self.board[(coord.row * BOARD_COLS + coord.col) as usize] = id;
    }

    // --- transitions ------------------------------------------------------

    /// `StateUpdater.apply_action_inplace` (the shared `_apply_action_to` body).
    pub fn apply_action(&mut self, action: Action) {
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
                    self.last_tile_action = None;
                    self.draw_tile();
                    self.next_player();
                    if self.is_terminated() {
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

        if self.is_terminated() {
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
        let row_lo = coordinate.row - 1;
        let row_hi = coordinate.row + 1;
        let mut cur = coordinate;
        for row in row_lo..=row_hi {
            let col_lo = cur.col - 1;
            let col_hi = cur.col + 1;
            for column in col_lo..=col_hi {
                let tid = match self.get_tile(row, column) {
                    None => continue,
                    Some(t) => t,
                };
                let tile = tiles::tile(tid);
                cur = Coord::new(row, column);
                let meeple_of_player = self.position_contains_meeple(cur, Side::Center);
                if (tile.chapel || tile.flowers) && meeple_of_player.is_some() {
                    let points = self.chapel_or_flowers_points(cur);
                    if points == 9 {
                        let p = meeple_of_player.unwrap();
                        self.scores[p] += points;
                        let mut per_player: [Vec<MeeplePosition>; 2] = [Vec::new(), Vec::new()];
                        for mp in &self.placed_meeples[p] {
                            if mp.coord == cur && mp.side == Side::Center {
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
                let terrain = tiles::tile(tid).get_type(mp.side);

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
        for &(r, c, _s) in &city.positions {
            let tid = self.board_direct(r, c).expect("city position on an empty cell");
            if !tiles::tile(tid).inn.is_empty() {
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
            let tile = tiles::tile(tid);
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
        for &(r, c, _s) in &road.positions {
            let tid = self.board_direct(r, c).expect("road position on an empty cell");
            if !tiles::tile(tid).inn.is_empty() {
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
        for node in &farm.nodes {
            let tid = self.board_direct(node.coord.row, node.coord.col).unwrap();
            let sides = tiles::tile(tid).farms[node.slot as usize].city_sides.clone();
            for city in self.find_cities(node.coord, &sides) {
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
        for group in &tiles::tile(tid).city {
            if group.contains(&side) {
                for &s in group {
                    out.push((r, c, s));
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
        let tile = tiles::tile(tid);
        for &side in sides {
            if tile.get_type(side) == Some(TerrainType::City) {
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
        for &(a, b) in &tiles::tile(tid).road {
            if a == side || b == side {
                if a != Side::Center {
                    out.push((r, c, a));
                }
                if b != Side::Center {
                    out.push((r, c, b));
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
        let tile = tiles::tile(tid);
        for &side in &CARDINALS {
            if tile.get_type(side) == Some(TerrainType::Road) {
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
        for (slot, fc) in tiles::tile(tid).farms.iter().enumerate() {
            if fc.tile_connections.contains(&fs) {
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
            let conns = &tiles::tile(tid).farms[node.slot as usize].tile_connections;
            for &fs in conns {
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
        for (slot, fc) in tiles::tile(tid).farms.iter().enumerate() {
            if fc.farmer_positions.contains(&side) {
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
            let fp = tiles::tile(tid).farms[node.slot as usize].farmer_positions[0];
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
        for &(row, col) in &self.open_positions {
            for turns in 0u8..4 {
                let top = self.get_tile(row - 1, col);
                let bottom = self.get_tile(row + 1, col);
                let left = self.get_tile(row, col - 1);
                let right = self.get_tile(row, col + 1);
                if fits(tiles::tile(tile_id(base, turns)), top, bottom, left, right) {
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
            let tile = tiles::tile(lta.tile);
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
        let tile = tiles::tile(lta.tile);
        if tile.chapel {
            out.push((lta.coord, Side::Center));
        }
        // NORMAL_MEEPLES_CAN_USE_FLOWERS is not in the locked supplementary set.
        for &side in &CARDINALS {
            if tile.get_type(side) == Some(TerrainType::City) {
                let city = self.find_city((lta.coord.row, lta.coord.col, side));
                if self.city_contains_meeples(&city) {
                    continue;
                }
                out.push((lta.coord, side));
            }
            if tile.get_type(side) == Some(TerrainType::Road) {
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
        let tile = tiles::tile(lta.tile);
        for (slot, fc) in tile.farms.iter().enumerate() {
            let farm = self.find_farm(FarmNode {
                coord: lta.coord,
                slot: slot as u8,
            });
            if self.farm_has_meeples(&farm) {
                continue;
            }
            out.push((lta.coord, fc.farmer_positions[0]));
        }
        out
    }
}

// ---------------------------------------------------------------------------
// Free functions
// ---------------------------------------------------------------------------

/// CPython list indexing: negatives wrap, out-of-range is an `IndexError`.
#[inline]
fn py_index(i: i32, len: i32, what: &str) -> i32 {
    let j = if i < 0 { i + len } else { i };
    if j < 0 || j >= len {
        panic!("IndexError: board {what} index {i} out of range (len {len})");
    }
    j
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
