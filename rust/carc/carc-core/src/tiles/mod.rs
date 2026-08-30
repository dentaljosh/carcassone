//! Tile data: the vendored engine's base deck, plus the rotation machinery.
//!
//! [`generated`] is codegen'd from `engine/.../tile_sets/base_deck.py` by
//! `scripts/rustport/export_tile_data.py` and checked in (no Python-invoking
//! `build.rs`).  Everything else here is a port of the engine's
//! `SideModificationUtil` / `Tile.turn` / `Tile.get_type`.
//!
//! ## The registry
//!
//! The Python engine hands around `Tile` objects and rotates them lazily
//! (`Tile.turn(times)`, memoised per base tile).  Only rotations 0..=3 are ever
//! produced by the action space, so we precompute all `N_BASE * 4` rotated tiles
//! once into a flat table and refer to them by a `TileId` index.  `TileId`
//! equality is the exact analogue of the Python engine's canonical-reference
//! sharing (`base_tiles[name].turn(k)` returns the *same* object every time).

pub mod generated;

use std::sync::OnceLock;

// ---------------------------------------------------------------------------
// Enums — declaration order matches the Python enums so `as usize` is stable.
// ---------------------------------------------------------------------------

/// `wingedsheep.carcassonne.objects.side.Side`.
#[derive(Copy, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
#[repr(u8)]
pub enum Side {
    Top = 0,
    Right = 1,
    Bottom = 2,
    Left = 3,
    Center = 4,
    TopLeft = 5,
    TopRight = 6,
    BottomLeft = 7,
    BottomRight = 8,
}

pub const N_SIDES: usize = 9;

impl Side {
    /// The Python enum's `.value` — what lands in `string_representation`.
    pub const fn value(self) -> &'static str {
        match self {
            Side::Top => "top",
            Side::Right => "right",
            Side::Bottom => "bottom",
            Side::Left => "left",
            Side::Center => "center",
            Side::TopLeft => "top_left",
            Side::TopRight => "top_right",
            Side::BottomLeft => "bottom_left",
            Side::BottomRight => "bottom_right",
        }
    }

    /// `SideModificationUtil.turn_side(side, times)` — one 90° clockwise step.
    pub const fn turn_once(self) -> Side {
        match self {
            Side::Top => Side::Right,
            Side::Right => Side::Bottom,
            Side::Bottom => Side::Left,
            Side::Left => Side::Top,
            Side::Center => Side::Center,
            Side::TopLeft => Side::TopRight,
            Side::TopRight => Side::BottomRight,
            Side::BottomRight => Side::BottomLeft,
            // the Python `else` branch: BOTTOM_LEFT
            Side::BottomLeft => Side::TopLeft,
        }
    }

    pub fn turn(self, times: u32) -> Side {
        let mut s = self;
        for _ in 0..times {
            s = s.turn_once();
        }
        s
    }
}

/// `wingedsheep.carcassonne.objects.farmer_side.FarmerSide`.
#[derive(Copy, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
#[repr(u8)]
pub enum FarmerSide {
    Tll = 0,
    Tlt = 1,
    Trt = 2,
    Trr = 3,
    Bll = 4,
    Blb = 5,
    Brb = 6,
    Brr = 7,
}

impl FarmerSide {
    pub const fn value(self) -> &'static str {
        match self {
            FarmerSide::Tll => "tll",
            FarmerSide::Tlt => "tlt",
            FarmerSide::Trt => "trt",
            FarmerSide::Trr => "trr",
            FarmerSide::Bll => "bll",
            FarmerSide::Blb => "blb",
            FarmerSide::Brb => "brb",
            FarmerSide::Brr => "brr",
        }
    }

    /// `FarmerSide.get_side()` — the cardinal edge this half-side lies on
    /// (the Python patch precomputes it from `value[2]`).
    pub const fn get_side(self) -> Side {
        match self {
            FarmerSide::Tll => Side::Left,
            FarmerSide::Tlt => Side::Top,
            FarmerSide::Trt => Side::Top,
            FarmerSide::Trr => Side::Right,
            FarmerSide::Bll => Side::Left,
            FarmerSide::Blb => Side::Bottom,
            FarmerSide::Brb => Side::Bottom,
            FarmerSide::Brr => Side::Right,
        }
    }

    /// `SideModificationUtil.turn_farmer_side(fs, times)` — one 90° step.
    pub const fn turn_once(self) -> FarmerSide {
        match self {
            FarmerSide::Tll => FarmerSide::Trt,
            FarmerSide::Tlt => FarmerSide::Trr,
            FarmerSide::Trt => FarmerSide::Brr,
            FarmerSide::Trr => FarmerSide::Brb,
            FarmerSide::Brr => FarmerSide::Blb,
            FarmerSide::Brb => FarmerSide::Bll,
            FarmerSide::Blb => FarmerSide::Tll,
            // the Python `else` branch: BLL
            FarmerSide::Bll => FarmerSide::Tlt,
        }
    }

    pub fn turn(self, times: u32) -> FarmerSide {
        let mut s = self;
        for _ in 0..times {
            s = s.turn_once();
        }
        s
    }

    /// `SideModificationUtil.opposite_farmer_side` — **with the vendored fork's
    /// `TRT -> BRB` fix** (upstream had `TRT -> BRR`, which made the map
    /// non-bijective and farm adjacency asymmetric; see DECISIONS 2026-05-29).
    /// The 8 half-sides form 4 involution pairs:
    /// `{TLL,TRR} {TLT,BLB} {TRT,BRB} {BRR,BLL}`.
    pub const fn opposite(self) -> FarmerSide {
        match self {
            FarmerSide::Tll => FarmerSide::Trr,
            FarmerSide::Tlt => FarmerSide::Blb,
            FarmerSide::Trt => FarmerSide::Brb,
            FarmerSide::Trr => FarmerSide::Tll,
            FarmerSide::Brr => FarmerSide::Bll,
            FarmerSide::Brb => FarmerSide::Trt,
            FarmerSide::Blb => FarmerSide::Tlt,
            FarmerSide::Bll => FarmerSide::Brr,
        }
    }
}

/// `wingedsheep.carcassonne.objects.terrain_type.TerrainType`.
#[derive(Copy, Clone, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum TerrainType {
    City = 0,
    Grass = 1,
    Road = 2,
    Chapel = 3,
    Flowers = 4,
    Unplayable = 5,
}

impl TerrainType {
    pub const fn value(self) -> &'static str {
        match self {
            TerrainType::City => "city",
            TerrainType::Grass => "grass",
            TerrainType::Road => "road",
            TerrainType::Chapel => "chapel",
            TerrainType::Flowers => "flowers",
            TerrainType::Unplayable => "unplayable",
        }
    }
}

// ---------------------------------------------------------------------------
// Static (generated) definitions
// ---------------------------------------------------------------------------

/// One `FarmerConnection` literal from `base_deck.py`.
pub struct FarmerConnectionDef {
    pub farmer_positions: &'static [Side],
    pub tile_connections: &'static [FarmerSide],
    pub city_sides: &'static [Side],
}

/// One `Tile(...)` literal from `base_deck.py` (rotation 0).
pub struct TileDef {
    pub description: &'static str,
    pub road: &'static [(Side, Side)],
    pub river: &'static [(Side, Side)],
    pub city: &'static [&'static [Side]],
    pub grass: &'static [Side],
    pub farms: &'static [FarmerConnectionDef],
    pub shield: bool,
    pub chapel: bool,
    pub flowers: bool,
    pub inn: &'static [Side],
    pub cathedral: bool,
    pub unplayable_sides: &'static [Side],
}

// ---------------------------------------------------------------------------
// Rotated tiles (the runtime representation)
// ---------------------------------------------------------------------------

/// A `FarmerConnection` after rotation.
#[derive(Clone, Debug)]
pub struct FarmerConn {
    pub farmer_positions: Vec<Side>,
    pub tile_connections: Vec<FarmerSide>,
    pub city_sides: Vec<Side>,
}

/// `base_tiles[name].turn(rot)` — one concrete, immutable tile instance.
#[derive(Clone, Debug)]
pub struct RotTile {
    pub base: u16,
    pub rot: u8,
    pub description: &'static str,
    pub road: Vec<(Side, Side)>,
    pub river: Vec<(Side, Side)>,
    pub city: Vec<Vec<Side>>,
    pub grass: Vec<Side>,
    pub farms: Vec<FarmerConn>,
    pub shield: bool,
    pub chapel: bool,
    pub flowers: bool,
    pub inn: Vec<Side>,
    pub cathedral: bool,
    pub unplayable_sides: Vec<Side>,
    /// `Tile.get_type` for all 9 sides (the vendored `_type_cache`).
    pub type_cache: [Option<TerrainType>; N_SIDES],
    /// Precomputed `repr()` of `game_wrapper._tile_rotation_signature(tile)`.
    pub rot_sig_repr: String,
    /// Cardinal sides carrying a city (`get_city_sides`).
    pub city_sides_set: Vec<Side>,
    pub road_ends: Vec<Side>,
    pub river_ends: Vec<Side>,
}

impl RotTile {
    #[inline]
    pub fn get_type(&self, side: Side) -> Option<TerrainType> {
        self.type_cache[side as usize]
    }

    #[inline]
    pub fn has_side(list: &[Side], s: Side) -> bool {
        list.contains(&s)
    }
}

/// Flat index into [`registry`]: `base * 4 + rot`.
pub type TileId = u16;

#[inline]
pub const fn tile_id(base: u16, rot: u8) -> TileId {
    base * 4 + rot as u16
}

pub fn n_base_tiles() -> usize {
    generated::BASE_TILES.len()
}

// ---------------------------------------------------------------------------
// R9 — "a field half-edge may not lie on a city edge" (F9 remediation).
//
//   *** DEFAULT OFF.  Building this flag adopts nothing. ***
//
// A **data** flag: `generated::R9_FARM_OVERRIDE` (codegen'd from
// `base_deck.r9_farm_override()`, the single Python derivation) replaces the
// `farms` of the affected tiles, and nothing else in this crate changes.
// Descriptions, counts and insertion order are untouched, so `TileId`s, deck
// shuffles, action spaces, board reprs and legal masks are bit-identical in
// both states — only farm decomposition moves.
//
// Process-global by construction, mirroring the Python side: `base_tiles` is an
// import-time module global there and the registry is a `OnceLock` here.
// Set `CARCASSONNE_FIX_R9` before first use.  Both registries are built lazily
// and independently so a test can hold both in one process.
// ---------------------------------------------------------------------------

/// `farms` for `def` under R9, or `def.farms` when the tile is unaffected.
fn r9_farms_for(def: &'static TileDef) -> &'static [FarmerConnectionDef] {
    generated::R9_FARM_OVERRIDE
        .iter()
        .find(|(name, _)| *name == def.description)
        .map(|&(_, farms)| farms)
        .unwrap_or(def.farms)
}

fn build_registry(r9: bool) -> Vec<RotTile> {
    let mut out = Vec::with_capacity(generated::BASE_TILES.len() * 4);
    for (bi, def) in generated::BASE_TILES.iter().enumerate() {
        let farms = if r9 { r9_farms_for(def) } else { def.farms };
        for rot in 0u8..4 {
            out.push(rotate_with_farms(def, farms, bi as u16, rot));
        }
    }
    out
}

fn rotate_with_farms(
    def: &'static TileDef,
    def_farms: &'static [FarmerConnectionDef],
    base: u16,
    rot: u8,
) -> RotTile {
    let t = rot as u32;
    let road: Vec<(Side, Side)> = def.road.iter().map(|&(a, b)| (a.turn(t), b.turn(t))).collect();
    let river: Vec<(Side, Side)> =
        def.river.iter().map(|&(a, b)| (a.turn(t), b.turn(t))).collect();
    let city: Vec<Vec<Side>> = def
        .city
        .iter()
        .map(|g| g.iter().map(|&s| s.turn(t)).collect())
        .collect();
    let grass: Vec<Side> = def.grass.iter().map(|&s| s.turn(t)).collect();
    let farms: Vec<FarmerConn> = def_farms
        .iter()
        .map(|f| FarmerConn {
            farmer_positions: f.farmer_positions.iter().map(|&s| s.turn(t)).collect(),
            tile_connections: f.tile_connections.iter().map(|&s| s.turn(t)).collect(),
            city_sides: f.city_sides.iter().map(|&s| s.turn(t)).collect(),
        })
        .collect();
    let inn: Vec<Side> = def.inn.iter().map(|&s| s.turn(t)).collect();
    let unplayable_sides: Vec<Side> = def.unplayable_sides.iter().map(|&s| s.turn(t)).collect();

    // --- Tile._build_type_cache, in the same test order -------------------
    let mut river_ends: Vec<Side> = Vec::new();
    for &(a, b) in &river {
        if !river_ends.contains(&a) {
            river_ends.push(a);
        }
        if !river_ends.contains(&b) {
            river_ends.push(b);
        }
    }
    let mut road_ends: Vec<Side> = Vec::new();
    for &(a, b) in &road {
        if !road_ends.contains(&a) {
            road_ends.push(a);
        }
        if !road_ends.contains(&b) {
            road_ends.push(b);
        }
    }
    let mut city_sides_set: Vec<Side> = Vec::new();
    for g in &city {
        for &s in g {
            if !city_sides_set.contains(&s) {
                city_sides_set.push(s);
            }
        }
    }

    const ALL_SIDES: [Side; N_SIDES] = [
        Side::Top,
        Side::Right,
        Side::Bottom,
        Side::Left,
        Side::Center,
        Side::TopLeft,
        Side::TopRight,
        Side::BottomLeft,
        Side::BottomRight,
    ];
    let mut type_cache: [Option<TerrainType>; N_SIDES] = [None; N_SIDES];
    for &side in ALL_SIDES.iter() {
        let ty = if unplayable_sides.contains(&side) {
            Some(TerrainType::Unplayable)
        } else if side == Side::Center && def.chapel {
            Some(TerrainType::Chapel)
        } else if side == Side::Center && def.flowers {
            Some(TerrainType::Flowers)
        } else if river_ends.contains(&side) {
            Some(TerrainType::Unplayable)
        } else if road_ends.contains(&side) {
            Some(TerrainType::Road)
        } else if city_sides_set.contains(&side) {
            Some(TerrainType::City)
        } else if grass.contains(&side) {
            Some(TerrainType::Grass)
        } else {
            None
        };
        type_cache[side as usize] = ty;
    }

    // --- game_wrapper._tile_rotation_signature, pre-repr'd ----------------
    let edge = |s: Side| -> String {
        match type_cache[s as usize] {
            // Python does `tile.get_type(side).value` — a None here is an
            // AttributeError there, so it must be one here too.
            None => panic!(
                "tile {} rot {} has no terrain type on {:?}; Python would raise \
                 AttributeError in _tile_rotation_signature",
                def.description, rot, s
            ),
            Some(t) => format!("'{}'", t.value()),
        }
    };
    let rot_sig_repr = format!(
        "(({}, {}, {}, {}), {}, {}, {})",
        edge(Side::Top),
        edge(Side::Right),
        edge(Side::Bottom),
        edge(Side::Left),
        if def.shield { "True" } else { "False" },
        if def.chapel { "True" } else { "False" },
        if def.flowers { "True" } else { "False" },
    );

    RotTile {
        base,
        rot,
        description: def.description,
        road,
        river,
        city,
        grass,
        farms,
        shield: def.shield,
        chapel: def.chapel,
        flowers: def.flowers,
        inn,
        cathedral: def.cathedral,
        unplayable_sides,
        type_cache,
        rot_sig_repr,
        city_sides_set,
        road_ends,
        river_ends,
    }
}

// ---------------------------------------------------------------------------
// The FLAT registry — the same data, contiguous (registry flattening, 2026-08-30)
//
// `RotTile` is the faithful mirror of the Python `Tile` object and stays as it
// is: it carries `String`s, `Vec<Vec<Side>>` and a `Vec<FarmerConn>` whose
// every `FarmerConn` owns three more `Vec`s.  Reading one tile's city groups,
// road connections and farm connections out of it therefore costs ~10 dependent
// pointer loads into scattered heap allocations.
//
// `decompose_into` reads exactly seven things per placed tile — the city
// groups, the road connections, each farm's `tile_connections` /
// `farmer_positions` / `city_sides`, `shield`, and whether `inn` is non-empty —
// once per placed tile per leaf evaluation, on the hottest path in the engine.
// `TileFlat` is those seven things and nothing else, in **fixed-size arrays
// inside one `#[repr(C)]` value** (102 bytes, two cache lines), stored in a flat
// table parallel to `registry()`.  The pointer chase becomes index arithmetic.
//
// **This is a pure representation change.**  The flat table is DERIVED from
// `registry_for(r9)` (never from `generated::` directly) so it cannot drift from
// the object registry, and every list keeps its source order — group order,
// side-within-group order, road-pair order, farm-slot order, and the order of
// each farm's three lists.  `decompose_into`'s output is bit-identical; see
// `leaf::decomp::refimpl` and the gates in `examples/registry_flat_gate.rs`.
// ---------------------------------------------------------------------------

/// Max sides across all city groups of one tile (base deck measures 4).
pub const MAX_CITY_SIDES: usize = 8;
/// Max city groups on one tile (base deck measures 2).
pub const MAX_CITY_GROUPS: usize = 4;
/// Max road connections on one tile (base deck measures 4 — the crossroads).
pub const MAX_ROADS: usize = 4;
/// Max `FarmerConnection`s on one tile (base deck measures 4).
pub const MAX_FARMS: usize = 4;
/// Max `farmer_positions` in one `FarmerConnection` (base deck measures 4).
pub const MAX_FPOS: usize = 4;
/// Max `tile_connections` in one `FarmerConnection` (base deck measures 8).
pub const MAX_TCONN: usize = 8;
/// Max `city_sides` in one `FarmerConnection` (base deck measures 3).
pub const MAX_CSIDES: usize = 4;

/// `(d_row, d_col)` for `FarmerSide::get_side()` — a const LUT replacing the
/// two chained `match`es (`get_side()` then `Side -> delta`) on the hot path.
/// Indexed by `FarmerSide as usize`; identical by construction to
/// `get_side()`'s cardinal answer.
pub const FARMER_SIDE_DELTA: [(i8, i8); 8] = [
    (0, -1), // Tll -> Left
    (-1, 0), // Tlt -> Top
    (-1, 0), // Trt -> Top
    (0, 1),  // Trr -> Right
    (0, -1), // Bll -> Left
    (1, 0),  // Blb -> Bottom
    (1, 0),  // Brb -> Bottom
    (0, 1),  // Brr -> Right
];

/// `FarmerSide::opposite() as u8`, as a const LUT (the fixed involution).
pub const FARMER_SIDE_OPP: [u8; 8] = [
    FarmerSide::Trr as u8, // Tll
    FarmerSide::Blb as u8, // Tlt
    FarmerSide::Brb as u8, // Trt
    FarmerSide::Tll as u8, // Trr
    FarmerSide::Brr as u8, // Bll
    FarmerSide::Tlt as u8, // Blb
    FarmerSide::Trt as u8, // Brb
    FarmerSide::Bll as u8, // Brr
];

/// One `FarmerConn`, flattened.  Sides are stored as their `as u8` discriminant
/// in **source order**; the counts say how much of each array is live.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(C)]
pub struct FarmFlat {
    /// `tile_connections`, as `FarmerSide as u8`.
    pub tconn: [u8; MAX_TCONN],
    /// `farmer_positions`, as `Side as u8`.
    pub fpos: [u8; MAX_FPOS],
    /// `city_sides`, as `Side as u8`.
    pub csides: [u8; MAX_CSIDES],
    pub n_tconn: u8,
    pub n_fpos: u8,
    pub n_csides: u8,
}

impl FarmFlat {
    const EMPTY: FarmFlat = FarmFlat {
        tconn: [0; MAX_TCONN],
        fpos: [0; MAX_FPOS],
        csides: [0; MAX_CSIDES],
        n_tconn: 0,
        n_fpos: 0,
        n_csides: 0,
    };
    #[inline]
    pub fn tconn(&self) -> &[u8] {
        &self.tconn[..self.n_tconn as usize]
    }
    #[inline]
    pub fn fpos(&self) -> &[u8] {
        &self.fpos[..self.n_fpos as usize]
    }
    #[inline]
    pub fn csides(&self) -> &[u8] {
        &self.csides[..self.n_csides as usize]
    }
}

/// The decomposition-relevant slice of a [`RotTile`], contiguous.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(C)]
pub struct TileFlat {
    /// All city-group sides concatenated in group order, `Side as u8`.
    pub city_sides: [u8; MAX_CITY_SIDES],
    /// Exclusive end index into `city_sides` for each group, ascending.
    pub city_group_end: [u8; MAX_CITY_GROUPS],
    /// Road connections flattened: `road[2*i]`, `road[2*i + 1]`, `Side as u8`.
    pub road: [u8; MAX_ROADS * 2],
    pub farms: [FarmFlat; MAX_FARMS],
    pub n_city_groups: u8,
    pub n_road: u8,
    pub n_farms: u8,
    pub shield: bool,
    /// `!inn.is_empty()` — precomputed; `decompose` only ever asks that.
    pub has_inn: bool,
}

impl TileFlat {
    /// The sides of city group `gi`, in source order.
    #[inline]
    pub fn city_group(&self, gi: usize) -> &[u8] {
        let start = if gi == 0 {
            0
        } else {
            self.city_group_end[gi - 1] as usize
        };
        &self.city_sides[start..self.city_group_end[gi] as usize]
    }
    #[inline]
    pub fn farms(&self) -> &[FarmFlat] {
        &self.farms[..self.n_farms as usize]
    }
}

fn flatten(t: &RotTile) -> TileFlat {
    let mut out = TileFlat {
        city_sides: [0; MAX_CITY_SIDES],
        city_group_end: [0; MAX_CITY_GROUPS],
        road: [0; MAX_ROADS * 2],
        farms: [FarmFlat::EMPTY; MAX_FARMS],
        n_city_groups: 0,
        n_road: 0,
        n_farms: 0,
        shield: t.shield,
        has_inn: !t.inn.is_empty(),
    };

    assert!(
        t.city.len() <= MAX_CITY_GROUPS,
        "tile {} rot {}: {} city groups > MAX_CITY_GROUPS",
        t.description,
        t.rot,
        t.city.len()
    );
    let mut k = 0usize;
    for (gi, group) in t.city.iter().enumerate() {
        for &s in group {
            assert!(
                k < MAX_CITY_SIDES,
                "tile {} rot {}: city sides > MAX_CITY_SIDES",
                t.description,
                t.rot
            );
            out.city_sides[k] = s as u8;
            k += 1;
        }
        out.city_group_end[gi] = k as u8;
    }
    out.n_city_groups = t.city.len() as u8;

    assert!(
        t.road.len() <= MAX_ROADS,
        "tile {} rot {}: {} roads > MAX_ROADS",
        t.description,
        t.rot,
        t.road.len()
    );
    for (i, &(a, b)) in t.road.iter().enumerate() {
        out.road[2 * i] = a as u8;
        out.road[2 * i + 1] = b as u8;
    }
    out.n_road = t.road.len() as u8;

    assert!(
        t.farms.len() <= MAX_FARMS,
        "tile {} rot {}: {} farms > MAX_FARMS",
        t.description,
        t.rot,
        t.farms.len()
    );
    for (slot, fc) in t.farms.iter().enumerate() {
        let f = &mut out.farms[slot];
        assert!(fc.tile_connections.len() <= MAX_TCONN, "MAX_TCONN");
        assert!(fc.farmer_positions.len() <= MAX_FPOS, "MAX_FPOS");
        assert!(fc.city_sides.len() <= MAX_CSIDES, "MAX_CSIDES");
        for (i, &fs) in fc.tile_connections.iter().enumerate() {
            f.tconn[i] = fs as u8;
        }
        for (i, &s) in fc.farmer_positions.iter().enumerate() {
            f.fpos[i] = s as u8;
        }
        for (i, &s) in fc.city_sides.iter().enumerate() {
            f.csides[i] = s as u8;
        }
        f.n_tconn = fc.tile_connections.len() as u8;
        f.n_fpos = fc.farmer_positions.len() as u8;
        f.n_csides = fc.city_sides.len() as u8;
    }
    out.n_farms = t.farms.len() as u8;

    out
}

static REGISTRY: OnceLock<Vec<RotTile>> = OnceLock::new();
static REGISTRY_R9: OnceLock<Vec<RotTile>> = OnceLock::new();
static FLAT: OnceLock<Vec<TileFlat>> = OnceLock::new();
static FLAT_R9: OnceLock<Vec<TileFlat>> = OnceLock::new();
static PLAY: OnceLock<Vec<TilePlayFlat>> = OnceLock::new();
static PLAY_R9: OnceLock<Vec<TilePlayFlat>> = OnceLock::new();
static R9_ON: OnceLock<bool> = OnceLock::new();

/// The `CARCASSONNE_FIX_R9` env flag, resolved once per process.  Accepts the
/// same spellings as the Python side (`1`/`true`/`yes`/`on`, case-insensitive).
pub fn r9_enabled() -> bool {
    *R9_ON.get_or_init(|| {
        std::env::var("CARCASSONNE_FIX_R9")
            .map(|v| matches!(v.trim().to_ascii_lowercase().as_str(),
                              "1" | "true" | "yes" | "on"))
            .unwrap_or(false)
    })
}

/// The registry for an explicit flag state — both are independently memoised so
/// a parity test can compare them inside one process.
pub fn registry_for(r9: bool) -> &'static [RotTile] {
    if r9 {
        REGISTRY_R9.get_or_init(|| build_registry(true))
    } else {
        REGISTRY.get_or_init(|| build_registry(false))
    }
}

/// All `N_BASE * 4` rotated tiles, indexed by [`tile_id`].
pub fn registry() -> &'static [RotTile] {
    registry_for(r9_enabled())
}

#[inline]
pub fn tile(id: TileId) -> &'static RotTile {
    &registry()[id as usize]
}

/// The flat table for an explicit flag state, derived from [`registry_for`].
pub fn flat_registry_for(r9: bool) -> &'static [TileFlat] {
    let lock = if r9 { &FLAT_R9 } else { &FLAT };
    lock.get_or_init(|| registry_for(r9).iter().map(flatten).collect())
}

/// All `N_BASE * 4` rotated tiles as [`TileFlat`], indexed by [`tile_id`].
///
/// Hoist this **once** per hot loop and index it; that is the whole point.
#[inline]
pub fn flat_registry() -> &'static [TileFlat] {
    flat_registry_for(r9_enabled())
}

#[inline]
pub fn tile_flat(id: TileId) -> &'static TileFlat {
    &flat_registry()[id as usize]
}

// ---------------------------------------------------------------------------
// THE PLAY VIEW — `TilePlayFlat` (2026-08-30, engine follow-on A)
//
// [`TileFlat`] carries the seven things `leaf::decompose_into` reads and
// nothing else, and its layout is graded by the registry-flattening round's
// banked oracle.  The OTHER `tiles::tile()` consumers — `engine::mod`'s
// legality / scoring / move-generation path and `leaf::mod`'s per-term meeple
// walks — read a DIFFERENT set: `type_cache`, `chapel`, `flowers`, `shield`,
// `inn`, and (for [`fits`]) the `grass` / `city_sides_set` / `road_ends` edge
// lists.  Those get their own parallel table rather than being bolted onto
// `TileFlat`, for two reasons:
//
//   1. `TileFlat`'s layout is what the flattening round's gate certificate is
//      about.  Growing it would perturb a certified structure for the benefit
//      of code that does not read it.
//   2. The two views have different access shapes.  The decomposition wants
//      ordered LISTS; the legality path wants SET MEMBERSHIP on four cardinal
//      sides, which is one `u8` bitmask and a shift — not a list walk at all.
//
// Both tables are derived from `registry_for(r9)` (never from `generated::`),
// memoised per R9 flag state, and pinned element-by-element against the object
// registry by `play_registry_matches_the_object_registry`.
// ---------------------------------------------------------------------------

/// `Side` by discriminant — the inverse of `s as u8`, as a const LUT.
pub const SIDE_FROM_U8: [Side; N_SIDES] = [
    Side::Top,
    Side::Right,
    Side::Bottom,
    Side::Left,
    Side::Center,
    Side::TopLeft,
    Side::TopRight,
    Side::BottomLeft,
    Side::BottomRight,
];

/// `FarmerSide` by discriminant — the inverse of `fs as u8`, as a const LUT.
pub const FARMER_SIDE_FROM_U8: [FarmerSide; 8] = [
    FarmerSide::Tll,
    FarmerSide::Tlt,
    FarmerSide::Trt,
    FarmerSide::Trr,
    FarmerSide::Bll,
    FarmerSide::Blb,
    FarmerSide::Brb,
    FarmerSide::Brr,
];

/// The four cardinals occupy discriminants 0..4 (`Top`, `Right`, `Bottom`,
/// `Left`), so a cardinal set is a 4-bit mask and the opposite of cardinal `i`
/// is `(i + 2) % 4`.  Non-cardinal sides are simply absent from the mask, which
/// matches the `_ => false` arm of every edge-fit `match` they replace.
pub const N_CARDINALS: usize = 4;

#[inline]
const fn cardinal_mask_bit(s: Side) -> u8 {
    let d = s as u8;
    if (d as usize) < N_CARDINALS {
        1 << d
    } else {
        0
    }
}

fn cardinal_mask(sides: &[Side]) -> u8 {
    let mut m = 0u8;
    for &s in sides {
        m |= cardinal_mask_bit(s);
    }
    m
}

/// `None` is encoded as 0 and `Some(t)` as `t as u8 + 1`, so the whole
/// `type_cache` is nine plain bytes with no niche games.
#[inline]
const fn encode_terrain(t: Option<TerrainType>) -> u8 {
    match t {
        None => 0,
        Some(x) => x as u8 + 1,
    }
}

#[inline]
const fn decode_terrain(b: u8) -> Option<TerrainType> {
    match b {
        0 => None,
        1 => Some(TerrainType::City),
        2 => Some(TerrainType::Grass),
        3 => Some(TerrainType::Road),
        4 => Some(TerrainType::Chapel),
        5 => Some(TerrainType::Flowers),
        6 => Some(TerrainType::Unplayable),
        _ => None,
    }
}

/// The legality / scoring / move-generation slice of a [`RotTile`], contiguous.
///
/// 15 bytes.  Everything here is a byte or a bit test; there is not a single
/// heap indirection left on the paths that read it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(C)]
pub struct TilePlayFlat {
    /// [`RotTile::type_cache`], encoded by [`encode_terrain`].
    pub terrain: [u8; N_SIDES],
    /// `grass` restricted to the cardinals, as a bitmask.
    pub grass_mask: u8,
    /// `city_sides_set` as a bitmask.
    pub city_side_mask: u8,
    /// `road_ends` as a bitmask.
    pub road_end_mask: u8,
    /// `sum(len(group) for group in city)` — `leaf::bag_stats`' `ne`.
    pub city_edges: u8,
    pub chapel: bool,
    pub flowers: bool,
    pub shield: bool,
    /// `!inn.is_empty()`.  (The engine's cathedral / inn tests only ever ask
    /// that; the `inn` list itself is never read on these paths.)
    pub has_inn: bool,
    /// `river.is_empty()` — the `play_tile` scope assert.
    pub river_empty: bool,
    /// `river_ends.is_empty()` — the [`fits`] scope assert.
    pub river_ends_empty: bool,
}

impl TilePlayFlat {
    /// [`RotTile::get_type`], from the flat table.
    #[inline]
    pub const fn get_type(&self, side: Side) -> Option<TerrainType> {
        decode_terrain(self.terrain[side as usize])
    }

    /// `get_type(side) == Some(t)` without materialising the `Option`.
    #[inline]
    pub const fn is_type(&self, side: Side, t: TerrainType) -> bool {
        self.terrain[side as usize] == t as u8 + 1
    }
}

fn flatten_play(t: &RotTile) -> TilePlayFlat {
    let mut terrain = [0u8; N_SIDES];
    for (i, slot) in t.type_cache.iter().enumerate() {
        terrain[i] = encode_terrain(*slot);
    }
    let city_edges: usize = t.city.iter().map(|g| g.len()).sum();
    assert!(
        city_edges <= u8::MAX as usize,
        "tile {} rot {}: city_edges overflows u8",
        t.description,
        t.rot
    );
    TilePlayFlat {
        terrain,
        grass_mask: cardinal_mask(&t.grass),
        city_side_mask: cardinal_mask(&t.city_sides_set),
        road_end_mask: cardinal_mask(&t.road_ends),
        city_edges: city_edges as u8,
        chapel: t.chapel,
        flowers: t.flowers,
        shield: t.shield,
        has_inn: !t.inn.is_empty(),
        river_empty: t.river.is_empty(),
        river_ends_empty: t.river_ends.is_empty(),
    }
}

/// The play table for an explicit flag state, derived from [`registry_for`].
pub fn play_registry_for(r9: bool) -> &'static [TilePlayFlat] {
    let lock = if r9 { &PLAY_R9 } else { &PLAY };
    lock.get_or_init(|| registry_for(r9).iter().map(flatten_play).collect())
}

/// All `N_BASE * 4` rotated tiles as [`TilePlayFlat`], indexed by [`tile_id`].
///
/// Hoist this **once** per hot loop and index it; that is the whole point.
#[inline]
pub fn play_registry() -> &'static [TilePlayFlat] {
    play_registry_for(r9_enabled())
}

#[inline]
pub fn tile_play(id: TileId) -> &'static TilePlayFlat {
    &play_registry()[id as usize]
}

/// `base_tile_counts` in dict-insertion order, resolved to base indices.
/// Deck construction iterates this order **before** the shuffle.
pub fn counts_in_order() -> Vec<(u16, u32)> {
    generated::COUNTS
        .iter()
        .map(|&(name, count)| {
            let idx = generated::BASE_TILES
                .iter()
                .position(|t| t.description == name)
                .unwrap_or_else(|| panic!("base_tile_counts names unknown tile {name:?}"))
                as u16;
            (idx, count)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rotation_is_order_four() {
        for id in 0..registry().len() as u16 {
            let t = tile(id);
            let base = tile(tile_id(t.base, 0));
            if t.rot == 0 {
                continue;
            }
            // turning 4 times returns to the base orientation
            let quad: Vec<Side> = base.grass.iter().map(|&s| s.turn(4)).collect();
            assert_eq!(quad, base.grass);
        }
    }

    #[test]
    fn opposite_farmer_side_is_an_involution() {
        use FarmerSide::*;
        for fs in [Tll, Tlt, Trt, Trr, Bll, Blb, Brb, Brr] {
            assert_eq!(fs.opposite().opposite(), fs, "{fs:?}");
            // the fix: the map is a bijection (every side is somebody's image)
            assert_ne!(fs.opposite(), fs);
        }
        assert_eq!(Trt.opposite(), Brb);
    }

    /// The two const LUTs must equal the `match`es they replace, for all 8
    /// half-sides.  If `opposite()` or `get_side()` is ever edited, this fires.
    #[test]
    fn farmer_side_luts_match_the_functions() {
        use FarmerSide::*;
        for fs in [Tll, Tlt, Trt, Trr, Bll, Blb, Brb, Brr] {
            let i = fs as usize;
            assert_eq!(FARMER_SIDE_OPP[i], fs.opposite() as u8, "{fs:?}");
            let want = match fs.get_side() {
                Side::Top => (-1i8, 0i8),
                Side::Right => (0, 1),
                Side::Bottom => (1, 0),
                Side::Left => (0, -1),
                other => panic!("farmer side on a non-cardinal edge {other:?}"),
            };
            assert_eq!(FARMER_SIDE_DELTA[i], want, "{fs:?}");
        }
    }

    /// The inverse LUTs must be exactly that, for every discriminant.
    #[test]
    fn side_and_farmer_side_from_u8_luts_are_inverses() {
        for (i, &s) in SIDE_FROM_U8.iter().enumerate() {
            assert_eq!(s as usize, i, "SIDE_FROM_U8[{i}] = {s:?}");
        }
        for (i, &fs) in FARMER_SIDE_FROM_U8.iter().enumerate() {
            assert_eq!(fs as usize, i, "FARMER_SIDE_FROM_U8[{i}] = {fs:?}");
        }
    }

    /// The terrain codec must round-trip every inhabitant of
    /// `Option<TerrainType>`, including `None`.
    #[test]
    fn terrain_codec_round_trips() {
        use TerrainType::*;
        for t in [
            None,
            Some(City),
            Some(Grass),
            Some(Road),
            Some(Chapel),
            Some(Flowers),
            Some(Unplayable),
        ] {
            assert_eq!(decode_terrain(encode_terrain(t)), t, "{t:?}");
        }
    }

    /// The PLAY table must reproduce every field the legality / scoring /
    /// move-generation path reads, for every tile in BOTH registry flag states.
    ///
    /// This is the gate that pins the play view at the data layer, exactly as
    /// `flat_registry_matches_the_object_registry` pins the decomposition view.
    #[test]
    fn play_registry_matches_the_object_registry() {
        for r9 in [false, true] {
            let objs = registry_for(r9);
            let plays = play_registry_for(r9);
            assert_eq!(objs.len(), plays.len(), "r9={r9}: table lengths differ");
            for (id, (o, p)) in objs.iter().zip(plays.iter()).enumerate() {
                let ctx = format!("r9={r9} id={id} {} rot {}", o.description, o.rot);

                // type_cache, every side, decoded back through the codec.
                for &s in &SIDE_FROM_U8 {
                    assert_eq!(p.get_type(s), o.get_type(s), "{ctx}: get_type({s:?})");
                    if let Some(t) = o.get_type(s) {
                        assert!(p.is_type(s, t), "{ctx}: is_type({s:?}, {t:?})");
                    }
                }

                // The three edge masks: membership must agree on all 9 sides,
                // and the mask must carry no bit the object list lacks.
                for &s in &SIDE_FROM_U8 {
                    let bit = cardinal_mask_bit(s);
                    let cardinal = bit != 0;
                    assert_eq!(
                        p.grass_mask & bit != 0,
                        cardinal && o.grass.contains(&s),
                        "{ctx}: grass_mask {s:?}"
                    );
                    assert_eq!(
                        p.city_side_mask & bit != 0,
                        cardinal && o.city_sides_set.contains(&s),
                        "{ctx}: city_side_mask {s:?}"
                    );
                    assert_eq!(
                        p.road_end_mask & bit != 0,
                        cardinal && o.road_ends.contains(&s),
                        "{ctx}: road_end_mask {s:?}"
                    );
                }
                // ...and the mask drops NOTHING but non-cardinals.
                //
                // ⚠️ The edge lists are NOT cardinal-only: `road_ends` carries
                // `Side::Center` on the crossroads tiles (`chapel_with_road`
                // rot 0 is the first). A 4-bit cardinal mask cannot hold that,
                // and does not need to: `engine::fits` reads these lists in
                // exactly two ways, and `Center` is inert in BOTH —
                //
                //   * the CENTER tile's own list is walked by a `match side`
                //     whose only arms are the four cardinals plus `_ => false`,
                //     so a non-cardinal member can never make a placement
                //     illegal; and
                //   * a NEIGHBOUR's list is only ever asked
                //     `.contains(&Side::{Top,Right,Bottom,Left})`, so a
                //     non-cardinal member can never be the answer.
                //
                // The equivalence is not argued from that alone —
                // `engine::flat_play_tests::fits_flat_matches_fits_*` compares
                // the two predicates exhaustively over single-neighbour boards
                // and over 200k randomized quadruples. What this assertion
                // pins is the narrower data claim: the mask's population is
                // exactly the cardinal members, so a conversion bug that
                // dropped a CARDINAL would fire here.
                for (name, list) in [
                    ("grass", &o.grass),
                    ("city_sides_set", &o.city_sides_set),
                    ("road_ends", &o.road_ends),
                ] {
                    let mask = match name {
                        "grass" => p.grass_mask,
                        "city_sides_set" => p.city_side_mask,
                        _ => p.road_end_mask,
                    };
                    let mut cardinals: Vec<Side> = Vec::new();
                    for &s in list.iter() {
                        if (s as usize) < N_CARDINALS && !cardinals.contains(&s) {
                            cardinals.push(s);
                        }
                    }
                    assert_eq!(
                        mask.count_ones() as usize,
                        cardinals.len(),
                        "{ctx}: {name} mask population {mask:#06b} != {} cardinal \
                         members of {list:?}",
                        cardinals.len()
                    );
                }

                let city_edges: usize = o.city.iter().map(|g| g.len()).sum();
                assert_eq!(p.city_edges as usize, city_edges, "{ctx}: city_edges");
                assert_eq!(p.chapel, o.chapel, "{ctx}: chapel");
                assert_eq!(p.flowers, o.flowers, "{ctx}: flowers");
                assert_eq!(p.shield, o.shield, "{ctx}: shield");
                assert_eq!(p.has_inn, !o.inn.is_empty(), "{ctx}: has_inn");
                assert_eq!(p.river_empty, o.river.is_empty(), "{ctx}: river_empty");
                assert_eq!(
                    p.river_ends_empty,
                    o.river_ends.is_empty(),
                    "{ctx}: river_ends_empty"
                );
            }
        }
    }

    /// The flat table must reproduce every list `decompose` reads, in order,
    /// for every tile in BOTH registry flag states.
    #[test]
    fn flat_registry_matches_the_object_registry() {
        for r9 in [false, true] {
            let objs = registry_for(r9);
            let flats = flat_registry_for(r9);
            assert_eq!(objs.len(), flats.len());
            for (id, (t, f)) in objs.iter().zip(flats.iter()).enumerate() {
                let ctx = format!("r9={r9} id={id} {} rot {}", t.description, t.rot);
                assert_eq!(f.n_city_groups as usize, t.city.len(), "{ctx} groups");
                for (gi, group) in t.city.iter().enumerate() {
                    let want: Vec<u8> = group.iter().map(|&s| s as u8).collect();
                    assert_eq!(f.city_group(gi), &want[..], "{ctx} city group {gi}");
                }
                assert_eq!(f.n_road as usize, t.road.len(), "{ctx} roads");
                for (i, &(a, b)) in t.road.iter().enumerate() {
                    assert_eq!(f.road[2 * i], a as u8, "{ctx} road {i}.0");
                    assert_eq!(f.road[2 * i + 1], b as u8, "{ctx} road {i}.1");
                }
                assert_eq!(f.shield, t.shield, "{ctx} shield");
                assert_eq!(f.has_inn, !t.inn.is_empty(), "{ctx} has_inn");
                assert_eq!(f.n_farms as usize, t.farms.len(), "{ctx} farms");
                for (slot, fc) in t.farms.iter().enumerate() {
                    let ff = &f.farms[slot];
                    let want_t: Vec<u8> =
                        fc.tile_connections.iter().map(|&x| x as u8).collect();
                    let want_p: Vec<u8> =
                        fc.farmer_positions.iter().map(|&x| x as u8).collect();
                    let want_c: Vec<u8> = fc.city_sides.iter().map(|&x| x as u8).collect();
                    assert_eq!(ff.tconn(), &want_t[..], "{ctx} farm {slot} tconn");
                    assert_eq!(ff.fpos(), &want_p[..], "{ctx} farm {slot} fpos");
                    assert_eq!(ff.csides(), &want_c[..], "{ctx} farm {slot} csides");
                }
            }
        }
    }

    #[test]
    fn counts_sum_to_seventy_two() {
        let total: u32 = counts_in_order().iter().map(|&(_, c)| c).sum();
        assert_eq!(total, 72);
        assert_eq!(n_base_tiles(), 32);
    }
}
