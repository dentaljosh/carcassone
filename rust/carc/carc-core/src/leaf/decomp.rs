//! `flat_leaf.decompose` — the whole-board int union-find decomposition.
//!
//! A port of `src/carcassonne_ai/flat_leaf.py::decompose`, with representation
//! changes that are provably behaviour-neutral:
//!
//! * Python keys its node dicts by `(row, col, side_ix)` tuples; we key by
//!   `(tile_ordinal * 9 + side_ix)` where `tile_ordinal` is the index of the
//!   cell in the **row-major sorted list of placed coordinates**. The Python
//!   scan `for r: for c:` visits placed cells in exactly that order, so node
//!   ids are assigned identically and the union-find sees the same edge list in
//!   the same order — i.e. the *root ids themselves* match Python's, not just
//!   the partition.
//! * Python keys farm nodes by `id(FarmerConnection)`; we key by
//!   `(coord, farm_slot)`, the P1 substitution (see `engine`'s module docs).
//! * Python's per-root **sets** (`city_root_coords`, the empty-adjacency sets,
//!   `farm_root_adj_city_roots`) become flat aggregates or one sorted-deduped
//!   pair array each, because every consumer of them is either an integer sum
//!   or a `math.fsum` — both functions of the multiset, not of the order. This
//!   is a ~2x throughput difference (per-root `Vec<Vec<_>>` costs an allocation
//!   per component); the G2 gate re-runs bit-exact across all corpora.
//!
//! The **grid-bounded open counting** is ported verbatim: a feature edge
//! pointing off the 35x35 board contributes to `finished == false` but *not* to
//! `open_n`, so a board-edge feature can be unfinished with `open_n == 0` (the
//! "D16 unclosable city" case). That is the walled-variant distortion; it is
//! part of the measured champion and is reproduced exactly.

use crate::engine::{GameState, BOARD_COLS, BOARD_ROWS};
use crate::tiles::{self, Side, TileId};

const N_CELLS: usize = (BOARD_ROWS * BOARD_COLS) as usize;

/// `(d_row, d_col, neighbour_side)` for a cardinal side — `flat_leaf._OPP`,
/// mirroring `CityUtil/RoadUtil.opposite_edge`.
#[inline]
fn opp(side_ix: u8) -> (i32, i32, u8) {
    match side_ix {
        0 => (-1, 0, 2), // TOP -> BOTTOM
        1 => (0, 1, 3),  // RIGHT -> LEFT
        2 => (1, 0, 0),  // BOTTOM -> TOP
        3 => (0, -1, 1), // LEFT -> RIGHT
        other => panic!("_OPP has no entry for side ix {other} (Python: KeyError)"),
    }
}

/// `flat_leaf._label_components` — union-find with path halving, `parent[a] = b`.
fn label_components(n: usize, eu: &[u32], ev: &[u32]) -> Vec<u32> {
    let mut parent: Vec<u32> = (0..n as u32).collect();

    #[inline]
    fn find(parent: &mut [u32], mut x: u32) -> u32 {
        while parent[x as usize] != x {
            parent[x as usize] = parent[parent[x as usize] as usize];
            x = parent[x as usize];
        }
        x
    }

    for i in 0..eu.len() {
        let a = find(&mut parent, eu[i]);
        let b = find(&mut parent, ev[i]);
        if a != b {
            parent[a as usize] = b;
        }
    }
    (0..n as u32).map(|x| find(&mut parent, x)).collect()
}

/// Count distinct `(group, item)` pairs per group.  `keys` is `group * stride +
/// item`; the caller guarantees `item < stride`.
fn count_distinct_per_group(keys: &mut Vec<u32>, stride: u32, out: &mut [usize]) {
    keys.sort_unstable();
    keys.dedup();
    for &k in keys.iter() {
        out[(k / stride) as usize] += 1;
    }
}

/// The whole-board structural decomposition (`flat_leaf.Decomp`).
///
/// Root-keyed facts are vectors indexed by the root node id; entries for
/// non-root ids are present but unused, exactly as a Python dict keyed by the
/// canonical root would be.
pub struct Decomp {
    /// Placed cells in row-major order — the Python `for r: for c:` scan order.
    pub placed: Vec<(i32, i32)>,
    /// `row * 35 + col -> index into `placed``, `-1` for an empty cell.
    cell_ord: Vec<i32>,

    // --- CITY ---------------------------------------------------------------
    pub city_nodes: Vec<(i32, i32, u8)>,
    pub city_labels: Vec<u32>,
    /// `ord * 9 + side_ix -> node id`, `-1` for absent.
    city_node_id: Vec<i32>,
    /// Per-root aggregates over the component's **distinct tiles**.
    pub city_root_tiles: Vec<i64>,
    pub city_root_shields: Vec<i64>,
    pub city_root_cathedral: Vec<bool>,
    pub city_root_finished: Vec<bool>,
    pub city_root_open_n: Vec<usize>,
    pub city_root_delta: Vec<i64>,

    // --- ROAD ---------------------------------------------------------------
    pub road_nodes: Vec<(i32, i32, u8)>,
    pub road_labels: Vec<u32>,
    road_node_id: Vec<i32>,
    pub road_root_tiles: Vec<i64>,
    pub road_root_inn: Vec<bool>,
    pub road_root_finished: Vec<bool>,
    pub road_root_open_n: Vec<usize>,

    // --- FARM ---------------------------------------------------------------
    pub farm_node_rc: Vec<(i32, i32)>,
    pub farm_node_slot: Vec<u8>,
    pub farm_labels: Vec<u32>,
    /// `ord * 9 + side_ix -> farm root`, `-1` for absent. Base-scoring match
    /// (`find_meeples` compares against `farmer_positions[0]`).
    farm_pos0_root: Vec<i32>,
    /// Same keyspace, but every `farmer_position` maps (bonus match, ==
    /// `find_farm_by_coordinate`).
    farm_anypos_root: Vec<i32>,
    /// Sorted, deduped `(farm_root << 32) | city_root` adjacency pairs.
    farm_adj: Vec<u64>,
    pub farm_root_finished_cities: Vec<usize>,
}

impl Decomp {
    #[inline]
    pub fn ordinal(&self, row: i32, col: i32) -> Option<usize> {
        if row < 0 || row >= BOARD_ROWS || col < 0 || col >= BOARD_COLS {
            return None;
        }
        let v = self.cell_ord[(row * BOARD_COLS + col) as usize];
        if v < 0 {
            None
        } else {
            Some(v as usize)
        }
    }

    /// `decomp.city_side_root.get((r, c, side))`.
    #[inline]
    pub fn city_side_root(&self, row: i32, col: i32, side: Side) -> Option<u32> {
        let o = self.ordinal(row, col)?;
        let nid = self.city_node_id[o * 9 + side as usize];
        if nid < 0 {
            None
        } else {
            Some(self.city_labels[nid as usize])
        }
    }

    /// `decomp.road_side_root.get((r, c, side))`.
    #[inline]
    pub fn road_side_root(&self, row: i32, col: i32, side: Side) -> Option<u32> {
        let o = self.ordinal(row, col)?;
        let nid = self.road_node_id[o * 9 + side as usize];
        if nid < 0 {
            None
        } else {
            Some(self.road_labels[nid as usize])
        }
    }

    /// `decomp.farm_pos0_root.get((r, c, side))`.
    #[inline]
    pub fn farm_pos0_root(&self, row: i32, col: i32, side: Side) -> Option<u32> {
        let o = self.ordinal(row, col)?;
        let v = self.farm_pos0_root[o * 9 + side as usize];
        if v < 0 {
            None
        } else {
            Some(v as u32)
        }
    }

    /// `decomp.farm_anypos_root.get((r, c, side))`.
    #[inline]
    pub fn farm_anypos_root(&self, row: i32, col: i32, side: Side) -> Option<u32> {
        let o = self.ordinal(row, col)?;
        let v = self.farm_anypos_root[o * 9 + side as usize];
        if v < 0 {
            None
        } else {
            Some(v as u32)
        }
    }

    /// `decomp.farm_root_adj_city_roots[root]` — the distinct city components
    /// this field touches, ascending.
    pub fn farm_adj_city_roots(&self, farm_root: u32) -> impl Iterator<Item = u32> + '_ {
        let lo = (farm_root as u64) << 32;
        let hi = lo | 0xffff_ffff;
        let start = self.farm_adj.partition_point(|&k| k < lo);
        self.farm_adj[start..]
            .iter()
            .take_while(move |&&k| k <= hi)
            .map(|&k| k as u32)
    }

    /// The component's city positions — rebuilt on demand (Python keeps them in
    /// `city_root_positions`; only the bag-close gate reads them, which is OFF
    /// in the champion, so we do not pay for the frozensets on the hot path).
    pub fn city_root_positions(&self, root: u32) -> Vec<(i32, i32, u8)> {
        self.city_nodes
            .iter()
            .enumerate()
            .filter(|(nid, _)| self.city_labels[*nid] == root)
            .map(|(_, &p)| p)
            .collect()
    }
}

/// `flat_leaf.decompose(state)`.
pub fn decompose(state: &GameState) -> Decomp {
    let placed: Vec<(i32, i32)> = state.placed_coords.iter().copied().collect();
    let n_cells = placed.len();
    let mut cell_ord: Vec<i32> = vec![-1; N_CELLS];
    for (o, &(r, c)) in placed.iter().enumerate() {
        cell_ord[(r * BOARD_COLS + c) as usize] = o as i32;
    }
    let ord_of = |row: i32, col: i32| -> Option<usize> {
        if row < 0 || row >= BOARD_ROWS || col < 0 || col >= BOARD_COLS {
            return None;
        }
        let v = cell_ord[(row * BOARD_COLS + col) as usize];
        if v < 0 {
            None
        } else {
            Some(v as usize)
        }
    };

    // ---- enumerate nodes + intra-tile edges -------------------------------- //
    let mut city_node_id: Vec<i32> = vec![-1; n_cells * 9];
    let mut city_nodes: Vec<(i32, i32, u8)> = Vec::with_capacity(n_cells * 2);
    let mut city_eu: Vec<u32> = Vec::with_capacity(n_cells * 2);
    let mut city_ev: Vec<u32> = Vec::with_capacity(n_cells * 2);

    let mut road_node_id: Vec<i32> = vec![-1; n_cells * 9];
    let mut road_nodes: Vec<(i32, i32, u8)> = Vec::with_capacity(n_cells * 2);
    let mut road_eu: Vec<u32> = Vec::with_capacity(n_cells * 2);
    let mut road_ev: Vec<u32> = Vec::with_capacity(n_cells * 2);

    let mut farm_node_rc: Vec<(i32, i32)> = Vec::with_capacity(n_cells * 2);
    let mut farm_node_slot: Vec<u8> = Vec::with_capacity(n_cells * 2);
    let mut farm_side_to_node: Vec<i32> = vec![-1; n_cells * 8];

    for (o, &(r, c)) in placed.iter().enumerate() {
        let tid: TileId = state
            .get_tile(r, c)
            .expect("placed_coords names an empty cell");
        let tile = tiles::tile(tid);

        // cities: sides of one `tile.city` group are connected
        for group in &tile.city {
            let mut first: Option<u32> = None;
            for &s in group {
                let key = o * 9 + s as usize;
                let nid = if city_node_id[key] < 0 {
                    let nid = city_nodes.len() as u32;
                    city_node_id[key] = nid as i32;
                    city_nodes.push((r, c, s as u8));
                    nid
                } else {
                    city_node_id[key] as u32
                };
                match first {
                    None => first = Some(nid),
                    Some(f) => {
                        city_eu.push(f);
                        city_ev.push(nid);
                    }
                }
            }
        }

        // roads: the two non-CENTER ends of a Connection are connected
        for &(a, b) in &tile.road {
            let mut mk = |s: Side| -> u32 {
                let key = o * 9 + s as usize;
                if road_node_id[key] < 0 {
                    let nid = road_nodes.len() as u32;
                    road_node_id[key] = nid as i32;
                    road_nodes.push((r, c, s as u8));
                    nid
                } else {
                    road_node_id[key] as u32
                }
            };
            let ida = if a == Side::Center { None } else { Some(mk(a)) };
            let idb = if b == Side::Center { None } else { Some(mk(b)) };
            if let (Some(x), Some(y)) = (ida, idb) {
                road_eu.push(x);
                road_ev.push(y);
            }
        }

        // farms: one node per FarmerConnection
        for (slot, fc) in tile.farms.iter().enumerate() {
            let nid = farm_node_rc.len() as i32;
            farm_node_rc.push((r, c));
            farm_node_slot.push(slot as u8);
            for &fs in &fc.tile_connections {
                farm_side_to_node[o * 8 + fs as usize] = nid;
            }
        }
    }

    // ---- cross-tile edges + open detection --------------------------------- //
    let mut city_open = vec![false; city_nodes.len()];
    for nid in 0..city_nodes.len() {
        let (r, c, ix) = city_nodes[nid];
        let (dr, dc, o_ix) = opp(ix);
        let onid = ord_of(r + dr, c + dc).map(|o| city_node_id[o * 9 + o_ix as usize]);
        match onid {
            Some(v) if v >= 0 => {
                city_eu.push(nid as u32);
                city_ev.push(v as u32);
            }
            _ => city_open[nid] = true,
        }
    }

    let mut road_open = vec![false; road_nodes.len()];
    for nid in 0..road_nodes.len() {
        let (r, c, ix) = road_nodes[nid];
        let (dr, dc, o_ix) = opp(ix);
        let onid = ord_of(r + dr, c + dc).map(|o| road_node_id[o * 9 + o_ix as usize]);
        match onid {
            Some(v) if v >= 0 => {
                road_eu.push(nid as u32);
                road_ev.push(v as u32);
            }
            _ => road_open[nid] = true,
        }
    }

    let mut farm_eu: Vec<u32> = Vec::with_capacity(farm_node_rc.len() * 2);
    let mut farm_ev: Vec<u32> = Vec::with_capacity(farm_node_rc.len() * 2);
    for nid in 0..farm_node_rc.len() {
        let (r, c) = farm_node_rc[nid];
        let tid = state.get_tile(r, c).unwrap();
        let conns = &tiles::tile(tid).farms[farm_node_slot[nid] as usize].tile_connections;
        for &fs in conns {
            let (dr, dc) = match fs.get_side() {
                Side::Top => (-1, 0),
                Side::Right => (0, 1),
                Side::Bottom => (1, 0),
                Side::Left => (0, -1),
                other => panic!("farmer side on a non-cardinal edge {other:?}"),
            };
            if let Some(no) = ord_of(r + dr, c + dc) {
                let neighbor = farm_side_to_node[no * 8 + fs.opposite() as usize];
                if neighbor >= 0 {
                    farm_eu.push(nid as u32);
                    farm_ev.push(neighbor as u32);
                }
            }
        }
    }

    // ---- label components -------------------------------------------------- //
    let city_labels = label_components(city_nodes.len(), &city_eu, &city_ev);
    let road_labels = label_components(road_nodes.len(), &road_eu, &road_ev);
    let farm_labels = label_components(farm_node_rc.len(), &farm_eu, &farm_ev);

    // ---- city facts -------------------------------------------------------- //
    //
    // Per-root aggregates over DISTINCT tiles.  A component's nodes are grouped
    // by cell in ascending cell order (nodes are created cell block by cell
    // block), so a `last cell seen for this root` stamp is an exact dedup.
    let nc = city_nodes.len();
    let mut city_root_tiles = vec![0i64; nc];
    let mut city_root_shields = vec![0i64; nc];
    let mut city_root_cathedral = vec![false; nc];
    let mut city_root_finished = vec![true; nc];
    let mut city_last_cell = vec![-1i32; nc];
    let mut city_empty_keys: Vec<u32> = Vec::with_capacity(nc);
    for nid in 0..nc {
        let (r, c, ix) = city_nodes[nid];
        let root = city_labels[nid] as usize;
        let cell = r * BOARD_COLS + c;
        if city_last_cell[root] != cell {
            city_last_cell[root] = cell;
            let tile = tiles::tile(state.get_tile(r, c).unwrap());
            city_root_tiles[root] += 1;
            if tile.shield {
                city_root_shields[root] += 1;
            }
            if !tile.inn.is_empty() {
                city_root_cathedral[root] = true;
            }
        }
        if city_open[nid] {
            city_root_finished[root] = false;
        }
        let (dr, dc, _o) = opp(ix);
        let (nr, ncol) = (r + dr, c + dc);
        if nr >= 0 && nr < BOARD_ROWS && ncol >= 0 && ncol < BOARD_COLS
            && cell_ord[(nr * BOARD_COLS + ncol) as usize] < 0
        {
            city_empty_keys.push(root as u32 * N_CELLS as u32 + (nr * BOARD_COLS + ncol) as u32);
        }
    }
    let mut city_root_open_n = vec![0usize; nc];
    count_distinct_per_group(&mut city_empty_keys, N_CELLS as u32, &mut city_root_open_n);

    // closure delta == count_city_points if the component closed (full credit)
    let mut city_root_delta = vec![0i64; nc];
    for root in 0..nc {
        let (t, s) = (city_root_tiles[root], city_root_shields[root]);
        city_root_delta[root] = if city_root_cathedral[root] {
            3 * t + 3 * s
        } else {
            t + s
        };
    }

    // ---- road facts -------------------------------------------------------- //
    let nrn = road_nodes.len();
    let mut road_root_tiles = vec![0i64; nrn];
    let mut road_root_inn = vec![false; nrn];
    let mut road_root_finished = vec![true; nrn];
    let mut road_last_cell = vec![-1i32; nrn];
    let mut road_empty_keys: Vec<u32> = Vec::with_capacity(nrn);
    for nid in 0..nrn {
        let (r, c, ix) = road_nodes[nid];
        let root = road_labels[nid] as usize;
        let cell = r * BOARD_COLS + c;
        if road_last_cell[root] != cell {
            road_last_cell[root] = cell;
            road_root_tiles[root] += 1;
            if !tiles::tile(state.get_tile(r, c).unwrap()).inn.is_empty() {
                road_root_inn[root] = true;
            }
        }
        if road_open[nid] {
            road_root_finished[root] = false;
        }
        let (dr, dc, _o) = opp(ix);
        let (nr, ncol) = (r + dr, c + dc);
        if nr >= 0 && nr < BOARD_ROWS && ncol >= 0 && ncol < BOARD_COLS
            && cell_ord[(nr * BOARD_COLS + ncol) as usize] < 0
        {
            road_empty_keys.push(root as u32 * N_CELLS as u32 + (nr * BOARD_COLS + ncol) as u32);
        }
    }
    let mut road_root_open_n = vec![0usize; nrn];
    count_distinct_per_group(&mut road_empty_keys, N_CELLS as u32, &mut road_root_open_n);

    // ---- farm facts -------------------------------------------------------- //
    let nf = farm_node_rc.len();
    let mut farm_pos0_root: Vec<i32> = vec![-1; n_cells * 9];
    let mut farm_anypos_root: Vec<i32> = vec![-1; n_cells * 9];
    let mut farm_adj: Vec<u64> = Vec::with_capacity(nf * 2);
    for nid in 0..nf {
        let root = farm_labels[nid] as usize;
        let (r, c) = farm_node_rc[nid];
        let o = ord_of(r, c).unwrap();
        let tid = state.get_tile(r, c).unwrap();
        let fc = &tiles::tile(tid).farms[farm_node_slot[nid] as usize];
        if !fc.farmer_positions.is_empty() {
            farm_pos0_root[o * 9 + fc.farmer_positions[0] as usize] = root as i32;
            for &pos in &fc.farmer_positions {
                farm_anypos_root[o * 9 + pos as usize] = root as i32;
            }
        }
        for &cs in &fc.city_sides {
            let cnid = city_node_id[o * 9 + cs as usize];
            if cnid >= 0 {
                farm_adj.push(((root as u64) << 32) | city_labels[cnid as usize] as u64);
            }
        }
    }
    farm_adj.sort_unstable();
    farm_adj.dedup();
    let mut farm_root_finished_cities = vec![0usize; nf];
    for &k in &farm_adj {
        if city_root_finished[(k as u32) as usize] {
            farm_root_finished_cities[(k >> 32) as usize] += 1;
        }
    }

    Decomp {
        placed,
        cell_ord,
        city_nodes,
        city_labels,
        city_node_id,
        city_root_tiles,
        city_root_shields,
        city_root_cathedral,
        city_root_finished,
        city_root_open_n,
        city_root_delta,
        road_nodes,
        road_labels,
        road_node_id,
        road_root_tiles,
        road_root_inn,
        road_root_finished,
        road_root_open_n,
        farm_node_rc,
        farm_node_slot,
        farm_labels,
        farm_pos0_root,
        farm_anypos_root,
        farm_adj,
        farm_root_finished_cities,
    }
}
