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

pub mod refimpl;

pub use refimpl::{decomp_diff, decompose_into_ref, decompose_ref, DECOMP_FIELDS};

use crate::engine::{GameState, BOARD_COLS, BOARD_ROWS};
use crate::tiles::{self, Side, TileId, FARMER_SIDE_DELTA, FARMER_SIDE_OPP};

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

/// `v = vec![val; n]` **without the allocation** when `v` already has capacity.
#[inline]
fn fill<T: Copy>(v: &mut Vec<T>, n: usize, val: T) {
    v.clear();
    v.resize(n, val);
}

/// `flat_leaf._label_components` — union-find with path halving, `parent[a] = b`.
///
/// Writes into caller-owned buffers so the search's per-leaf call does not
/// allocate; `parent` is scratch, `out` is the label vector.
fn label_components_into(
    n: usize,
    eu: &[u32],
    ev: &[u32],
    parent: &mut Vec<u32>,
    out: &mut Vec<u32>,
) {
    parent.clear();
    parent.extend(0..n as u32);

    #[inline]
    fn find(parent: &mut [u32], mut x: u32) -> u32 {
        while parent[x as usize] != x {
            parent[x as usize] = parent[parent[x as usize] as usize];
            x = parent[x as usize];
        }
        x
    }

    for i in 0..eu.len() {
        let a = find(parent, eu[i]);
        let b = find(parent, ev[i]);
        if a != b {
            parent[a as usize] = b;
        }
    }
    out.clear();
    out.reserve(n);
    for x in 0..n as u32 {
        let r = find(parent, x);
        out.push(r);
    }
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
// `PartialEq`/`Eq` are DERIVED FOR THE GATES (L1a, 2026-08-30): every field is
// an integer or bool vector, so structural equality IS bit-identity, and the
// meeple-phase hoist gate needs to assert exactly that between a parent and its
// child. Additive — no field, no method and no signature moves.
#[derive(Default, Clone, PartialEq, Eq)]
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
/// Reusable working buffers for [`decompose_into`].
///
/// P2 flagged the remaining leaf lever: `decompose` allocated ~30 vectors
/// (~27 KB) per call, which at P3/P4 SEARCH rates (tens of leaf evals per node
/// expansion) is pure allocator traffic.  `Scratch` + a caller-owned [`Decomp`]
/// turn every one of those into a `clear()` + `resize()` against retained
/// capacity.  Behaviour-neutral by construction: identical values, identical
/// order, only the storage is reused (the G2 leaf reconcile re-runs bit-exact).
#[derive(Default)]
pub struct Scratch {
    city_eu: Vec<u32>,
    city_ev: Vec<u32>,
    road_eu: Vec<u32>,
    road_ev: Vec<u32>,
    farm_eu: Vec<u32>,
    farm_ev: Vec<u32>,
    farm_side_to_node: Vec<i32>,
    city_open: Vec<bool>,
    road_open: Vec<bool>,
    city_last_cell: Vec<i32>,
    road_last_cell: Vec<i32>,
    city_empty_keys: Vec<u32>,
    road_empty_keys: Vec<u32>,
    parent: Vec<u32>,
    /// `ordinal -> TileId`, filled by the enumeration pass.  The later passes
    /// then reach the tile by index instead of re-running `state.get_tile`.
    ord_tid: Vec<TileId>,
    /// `farm node id -> ordinal of its cell`, likewise.
    farm_node_ord: Vec<u32>,
}

/// The whole-board structural decomposition, allocation-free after warm-up.
///
/// `out` is overwritten; anything it held is dropped logically (the capacity is
/// kept).  See [`decompose`] for the allocating convenience wrapper.
pub fn decompose_into(state: &GameState, out: &mut Decomp, sc: &mut Scratch) {
    let Decomp {
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
    } = out;

    placed.clear();
    placed.extend(state.placed_coords.iter().copied());
    let n_cells = placed.len();
    fill(cell_ord, N_CELLS, -1i32);
    for (o, &(r, c)) in placed.iter().enumerate() {
        cell_ord[(r * BOARD_COLS + c) as usize] = o as i32;
    }
    // Frozen from here on; `ord_of` reads it and nothing writes it again.
    let cell_ord_ro: &[i32] = cell_ord;
    let ord_of = |row: i32, col: i32| -> Option<usize> {
        if row < 0 || row >= BOARD_ROWS || col < 0 || col >= BOARD_COLS {
            return None;
        }
        let v = cell_ord_ro[(row * BOARD_COLS + col) as usize];
        if v < 0 {
            None
        } else {
            Some(v as usize)
        }
    };

    // The flat tile table, hoisted ONCE.  Every per-tile read below is an index
    // into this contiguous slice; `tiles::tile()` (two `OnceLock` loads plus a
    // walk through `Vec<Vec<Side>>` / `Vec<FarmerConn>` heap allocations) is not
    // called anywhere in this function any more.  Same data, same order — see
    // `tiles::flatten` and `refimpl` for the bit-identity argument.
    let freg = tiles::flat_registry();

    // ---- enumerate nodes + intra-tile edges -------------------------------- //
    fill(city_node_id, n_cells * 9, -1i32);
    city_nodes.clear();
    sc.city_eu.clear();
    sc.city_ev.clear();

    fill(road_node_id, n_cells * 9, -1i32);
    road_nodes.clear();
    sc.road_eu.clear();
    sc.road_ev.clear();

    farm_node_rc.clear();
    farm_node_slot.clear();
    sc.farm_node_ord.clear();
    sc.ord_tid.clear();
    sc.ord_tid.reserve(n_cells);
    fill(&mut sc.farm_side_to_node, n_cells * 8, -1i32);

    const CENTER: u8 = Side::Center as u8;

    for (o, &(r, c)) in placed.iter().enumerate() {
        let tid: TileId = state
            .get_tile(r, c)
            .expect("placed_coords names an empty cell");
        sc.ord_tid.push(tid);
        let tf = &freg[tid as usize];

        // cities: sides of one `tile.city` group are connected
        let mut gstart = 0usize;
        for gi in 0..tf.n_city_groups as usize {
            let gend = tf.city_group_end[gi] as usize;
            let mut first: Option<u32> = None;
            for k in gstart..gend {
                let s = tf.city_sides[k];
                let key = o * 9 + s as usize;
                let nid = if city_node_id[key] < 0 {
                    let nid = city_nodes.len() as u32;
                    city_node_id[key] = nid as i32;
                    city_nodes.push((r, c, s));
                    nid
                } else {
                    city_node_id[key] as u32
                };
                match first {
                    None => first = Some(nid),
                    Some(f) => {
                        sc.city_eu.push(f);
                        sc.city_ev.push(nid);
                    }
                }
            }
            gstart = gend;
        }

        // roads: the two non-CENTER ends of a Connection are connected
        for i in 0..tf.n_road as usize {
            let mut mk = |s: u8| -> u32 {
                let key = o * 9 + s as usize;
                if road_node_id[key] < 0 {
                    let nid = road_nodes.len() as u32;
                    road_node_id[key] = nid as i32;
                    road_nodes.push((r, c, s));
                    nid
                } else {
                    road_node_id[key] as u32
                }
            };
            let (a, b) = (tf.road[2 * i], tf.road[2 * i + 1]);
            let ida = if a == CENTER { None } else { Some(mk(a)) };
            let idb = if b == CENTER { None } else { Some(mk(b)) };
            if let (Some(x), Some(y)) = (ida, idb) {
                sc.road_eu.push(x);
                sc.road_ev.push(y);
            }
        }

        // farms: one node per FarmerConnection
        for slot in 0..tf.n_farms as usize {
            let nid = farm_node_rc.len() as i32;
            farm_node_rc.push((r, c));
            farm_node_slot.push(slot as u8);
            sc.farm_node_ord.push(o as u32);
            for &fs in tf.farms[slot].tconn() {
                sc.farm_side_to_node[o * 8 + fs as usize] = nid;
            }
        }
    }

    // ---- cross-tile edges + open detection --------------------------------- //
    fill(&mut sc.city_open, city_nodes.len(), false);
    for nid in 0..city_nodes.len() {
        let (r, c, ix) = city_nodes[nid];
        let (dr, dc, o_ix) = opp(ix);
        let onid = ord_of(r + dr, c + dc).map(|o| city_node_id[o * 9 + o_ix as usize]);
        match onid {
            Some(v) if v >= 0 => {
                sc.city_eu.push(nid as u32);
                sc.city_ev.push(v as u32);
            }
            _ => sc.city_open[nid] = true,
        }
    }

    fill(&mut sc.road_open, road_nodes.len(), false);
    for nid in 0..road_nodes.len() {
        let (r, c, ix) = road_nodes[nid];
        let (dr, dc, o_ix) = opp(ix);
        let onid = ord_of(r + dr, c + dc).map(|o| road_node_id[o * 9 + o_ix as usize]);
        match onid {
            Some(v) if v >= 0 => {
                sc.road_eu.push(nid as u32);
                sc.road_ev.push(v as u32);
            }
            _ => sc.road_open[nid] = true,
        }
    }

    sc.farm_eu.clear();
    sc.farm_ev.clear();
    for nid in 0..farm_node_rc.len() {
        let (r, c) = farm_node_rc[nid];
        let o = sc.farm_node_ord[nid] as usize;
        let fm = &freg[sc.ord_tid[o] as usize].farms[farm_node_slot[nid] as usize];
        // `FARMER_SIDE_DELTA` is `get_side()`'s cardinal delta and
        // `FARMER_SIDE_OPP` is `opposite()`, as const LUTs (gated in
        // `tiles::tests::farmer_side_luts_match_the_functions`).  `get_side()`
        // returns only cardinals, so the reference's non-cardinal `panic!` arm
        // is unreachable and has no LUT entry.
        for &fs in fm.tconn() {
            let (dr, dc) = FARMER_SIDE_DELTA[fs as usize];
            if let Some(no) = ord_of(r + dr as i32, c + dc as i32) {
                let neighbor =
                    sc.farm_side_to_node[no * 8 + FARMER_SIDE_OPP[fs as usize] as usize];
                if neighbor >= 0 {
                    sc.farm_eu.push(nid as u32);
                    sc.farm_ev.push(neighbor as u32);
                }
            }
        }
    }

    // ---- label components -------------------------------------------------- //
    label_components_into(city_nodes.len(), &sc.city_eu, &sc.city_ev,
                          &mut sc.parent, city_labels);
    label_components_into(road_nodes.len(), &sc.road_eu, &sc.road_ev,
                          &mut sc.parent, road_labels);
    label_components_into(farm_node_rc.len(), &sc.farm_eu, &sc.farm_ev,
                          &mut sc.parent, farm_labels);

    // ---- city facts -------------------------------------------------------- //
    //
    // Per-root aggregates over DISTINCT tiles.  A component's nodes are grouped
    // by cell in ascending cell order (nodes are created cell block by cell
    // block), so a `last cell seen for this root` stamp is an exact dedup.
    let nc = city_nodes.len();
    fill(city_root_tiles, nc, 0i64);
    fill(city_root_shields, nc, 0i64);
    fill(city_root_cathedral, nc, false);
    fill(city_root_finished, nc, true);
    fill(&mut sc.city_last_cell, nc, -1i32);
    sc.city_empty_keys.clear();
    for nid in 0..nc {
        let (r, c, ix) = city_nodes[nid];
        let root = city_labels[nid] as usize;
        let cell = r * BOARD_COLS + c;
        if sc.city_last_cell[root] != cell {
            sc.city_last_cell[root] = cell;
            // `cell` is a placed cell, so `cell_ord_ro[cell] >= 0` and names the
            // same tile `state.get_tile(r, c)` would return.
            let tf = &freg[sc.ord_tid[cell_ord_ro[cell as usize] as usize] as usize];
            city_root_tiles[root] += 1;
            if tf.shield {
                city_root_shields[root] += 1;
            }
            if tf.has_inn {
                city_root_cathedral[root] = true;
            }
        }
        if sc.city_open[nid] {
            city_root_finished[root] = false;
        }
        let (dr, dc, _o) = opp(ix);
        let (nr, ncol) = (r + dr, c + dc);
        if nr >= 0 && nr < BOARD_ROWS && ncol >= 0 && ncol < BOARD_COLS
            && cell_ord_ro[(nr * BOARD_COLS + ncol) as usize] < 0
        {
            sc.city_empty_keys
                .push(root as u32 * N_CELLS as u32 + (nr * BOARD_COLS + ncol) as u32);
        }
    }
    fill(city_root_open_n, nc, 0usize);
    count_distinct_per_group(&mut sc.city_empty_keys, N_CELLS as u32, city_root_open_n);

    // closure delta == count_city_points if the component closed (full credit)
    fill(city_root_delta, nc, 0i64);
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
    fill(road_root_tiles, nrn, 0i64);
    fill(road_root_inn, nrn, false);
    fill(road_root_finished, nrn, true);
    fill(&mut sc.road_last_cell, nrn, -1i32);
    sc.road_empty_keys.clear();
    for nid in 0..nrn {
        let (r, c, ix) = road_nodes[nid];
        let root = road_labels[nid] as usize;
        let cell = r * BOARD_COLS + c;
        if sc.road_last_cell[root] != cell {
            sc.road_last_cell[root] = cell;
            road_root_tiles[root] += 1;
            if freg[sc.ord_tid[cell_ord_ro[cell as usize] as usize] as usize].has_inn {
                road_root_inn[root] = true;
            }
        }
        if sc.road_open[nid] {
            road_root_finished[root] = false;
        }
        let (dr, dc, _o) = opp(ix);
        let (nr, ncol) = (r + dr, c + dc);
        if nr >= 0 && nr < BOARD_ROWS && ncol >= 0 && ncol < BOARD_COLS
            && cell_ord_ro[(nr * BOARD_COLS + ncol) as usize] < 0
        {
            sc.road_empty_keys
                .push(root as u32 * N_CELLS as u32 + (nr * BOARD_COLS + ncol) as u32);
        }
    }
    fill(road_root_open_n, nrn, 0usize);
    count_distinct_per_group(&mut sc.road_empty_keys, N_CELLS as u32, road_root_open_n);

    // ---- farm facts -------------------------------------------------------- //
    let nf = farm_node_rc.len();
    fill(farm_pos0_root, n_cells * 9, -1i32);
    fill(farm_anypos_root, n_cells * 9, -1i32);
    farm_adj.clear();
    for nid in 0..nf {
        let root = farm_labels[nid] as usize;
        let o = sc.farm_node_ord[nid] as usize;
        let fc = &freg[sc.ord_tid[o] as usize].farms[farm_node_slot[nid] as usize];
        if fc.n_fpos > 0 {
            farm_pos0_root[o * 9 + fc.fpos[0] as usize] = root as i32;
            for &pos in fc.fpos() {
                farm_anypos_root[o * 9 + pos as usize] = root as i32;
            }
        }
        for &cs in fc.csides() {
            let cnid = city_node_id[o * 9 + cs as usize];
            if cnid >= 0 {
                farm_adj.push(((root as u64) << 32) | city_labels[cnid as usize] as u64);
            }
        }
    }
    farm_adj.sort_unstable();
    farm_adj.dedup();
    fill(farm_root_finished_cities, nf, 0usize);
    for &k in farm_adj.iter() {
        if city_root_finished[(k as u32) as usize] {
            farm_root_finished_cities[(k >> 32) as usize] += 1;
        }
    }
}

/// Allocating convenience wrapper (tests, one-shot callers, the FFI leaf).
pub fn decompose(state: &GameState) -> Decomp {
    let mut d = Decomp::default();
    let mut sc = Scratch::default();
    decompose_into(state, &mut d, &mut sc);
    d
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::Game;

    /// The in-suite arm of the registry-flattening gate: the flat-registry
    /// `decompose_into` must equal the frozen object-registry
    /// `decompose_into_ref` on all 25 `Decomp` fields at every ply.
    ///
    /// The full corpus (500 randomized games x both registry flag states,
    /// ~150k positions and ~300k leaf values) lives in
    /// `examples/registry_flat_gate.rs`; this keeps a fast deterministic slice
    /// inside `cargo test` so a regression cannot land silently.
    #[test]
    fn flat_registry_decomposition_is_bit_identical_to_the_object_path() {
        let mut a = Decomp::default();
        let mut b = Decomp::default();
        let (mut sa, mut sb) = (Scratch::default(), Scratch::default());
        let mut positions = 0usize;
        for seed in ["1", "2", "17", "99"] {
            for policy in 0..3usize {
                let mut g = Game::from_seed(seed);
                let mut ply = 0usize;
                while !g.is_terminal() && ply < 200 {
                    decompose_into(&g.state, &mut a, &mut sa);
                    decompose_into_ref(&g.state, &mut b, &mut sb);
                    positions += 1;
                    if let Err(field) = decomp_diff(&a, &b) {
                        panic!("seed {seed} policy {policy} ply {ply}: field {field} differs");
                    }
                    let legal = g.legal_actions();
                    if legal.is_empty() {
                        break;
                    }
                    let i = match policy {
                        0 => 0,
                        1 => legal.len() / 2,
                        _ => legal.len() - 1,
                    };
                    g.advance(legal[i]).unwrap();
                    ply += 1;
                }
            }
        }
        assert!(positions >= 252, "corpus too small: {positions}");
    }

    /// `Scratch` is reused across calls with different board sizes; the flat
    /// path added two more reused buffers (`ord_tid`, `farm_node_ord`), so
    /// prove a shrinking board cannot read a stale tail.
    #[test]
    fn scratch_reuse_across_shrinking_boards_is_clean() {
        let mut sc = Scratch::default();
        let mut d = Decomp::default();
        let mut states = Vec::new();
        let mut g = Game::from_seed("31337");
        for _ in 0..120 {
            let legal = g.legal_actions();
            if legal.is_empty() {
                break;
            }
            g.advance(legal[0]).unwrap();
            states.push(g.state.clone());
        }
        // big -> small -> big, against a fresh-Scratch oracle each time
        for i in [119usize, 3, 80, 1, 60] {
            let s = &states[i.min(states.len() - 1)];
            decompose_into(s, &mut d, &mut sc);
            let fresh = decompose_ref(s);
            assert!(decomp_diff(&d, &fresh).is_ok(), "stale scratch at index {i}");
        }
    }
}
