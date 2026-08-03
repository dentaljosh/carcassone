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

static REGISTRY: OnceLock<Vec<RotTile>> = OnceLock::new();
static REGISTRY_R9: OnceLock<Vec<RotTile>> = OnceLock::new();
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

    #[test]
    fn counts_sum_to_seventy_two() {
        let total: u32 = counts_in_order().iter().map(|&(_, c)| c).sum();
        assert_eq!(total, 72);
        assert_eq!(n_base_tiles(), 32);
    }
}
