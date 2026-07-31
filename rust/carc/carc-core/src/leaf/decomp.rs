//! `flat_leaf.decompose` — the whole-board int union-find decomposition.
//!
//! A line-for-line port of `src/carcassonne_ai/flat_leaf.py::decompose`, with
//! two representation changes that are provably behaviour-neutral:
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
//!
//! Everything that is load-bearing for the leaf value is ported verbatim,
//! including the **grid-bounded open-cell counting**: a feature edge pointing
//! off the 35x35 board contributes to `finished == false` but *not* to
//! `open_n`, so a board-edge feature can be unfinished with `open_n == 0` (the
//! "D16 unclosable city" case). That is the walled-variant distortion; it is
//! part of the measured champion and is reproduced exactly.

use crate::engine::{GameState, BOARD_COLS, BOARD_ROWS};
use crate::tiles::{self, Side, TileId};

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

/// The whole-board structural decomposition (`flat_leaf.Decomp`).
///
/// Root-keyed facts are stored as vectors indexed by the root node id; entries
/// for non-root ids are present but unused, exactly as a Python dict keyed by
/// the canonical root would be.
pub struct Decomp {
    /// Placed cells in row-major order — the Python `for r: for c:` scan order.
    pub placed: Vec<(i32, i32)>,

    // --- CITY ---------------------------------------------------------------
    pub city_nodes: Vec<(i32, i32, u8)>,
    pub city_labels: Vec<u32>,
    /// `ord * 9 + side_ix -> node id`, `-1` for absent.
    city_node_id: Vec<i32>,
    pub city_root_coords: Vec<Vec<(i32, i32)>>,
    pub city_root_finished: Vec<bool>,
    pub city_root_open_n: Vec<usize>,
    pub city_root_delta: Vec<i64>,

    // --- ROAD ---------------------------------------------------------------
    pub road_nodes: Vec<(i32, i32, u8)>,
    pub road_labels: Vec<u32>,
    road_node_id: Vec<i32>,
    pub road_root_coords: Vec<Vec<(i32, i32)>>,
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
    pub farm_root_adj_city_roots: Vec<Vec<u32>>,
    pub farm_root_finished_cities: Vec<usize>,
}

impl Decomp {
    #[inline]
    pub fn ordinal(&self, row: i32, col: i32) -> Option<usize> {
        self.placed.binary_search(&(row, col)).ok()
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
    let ord_of = |row: i32, col: i32| -> Option<usize> { placed.binary_search(&(row, col)).ok() };

    // ---- enumerate nodes + intra-tile edges -------------------------------- //
    let mut city_node_id: Vec<i32> = vec![-1; n_cells * 9];
    let mut city_nodes: Vec<(i32, i32, u8)> = Vec::new();
    let mut city_eu: Vec<u32> = Vec::new();
    let mut city_ev: Vec<u32> = Vec::new();

    let mut road_node_id: Vec<i32> = vec![-1; n_cells * 9];
    let mut road_nodes: Vec<(i32, i32, u8)> = Vec::new();
    let mut road_eu: Vec<u32> = Vec::new();
    let mut road_ev: Vec<u32> = Vec::new();

    let mut farm_node_rc: Vec<(i32, i32)> = Vec::new();
    let mut farm_node_slot: Vec<u8> = Vec::new();
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

    let mut farm_eu: Vec<u32> = Vec::new();
    let mut farm_ev: Vec<u32> = Vec::new();
    for nid in 0..farm_node_rc.len() {
        let (r, c) = farm_node_rc[nid];
        let o = ord_of(r, c).expect("farm node on an unplaced cell");
        let tid = state.get_tile(r, c).unwrap();
        let conns = &tiles::tile(tid).farms[farm_node_slot[nid] as usize].tile_connections;
        for &fs in conns {
            let step = fs.get_side();
            let (dr, dc) = match step {
                Side::Top => (-1, 0),
                Side::Right => (0, 1),
                Side::Bottom => (1, 0),
                Side::Left => (0, -1),
                other => panic!("farmer side on a non-cardinal edge {other:?}"),
            };
            let _ = o;
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
    let nc = city_nodes.len();
    let mut city_root_coords: Vec<Vec<(i32, i32)>> = vec![Vec::new(); nc];
    let mut city_root_is_open = vec![false; nc];
    let mut city_root_emptyadj: Vec<Vec<(i32, i32)>> = vec![Vec::new(); nc];
    let mut city_root_seen = vec![false; nc];
    for nid in 0..nc {
        let (r, c, ix) = city_nodes[nid];
        let root = city_labels[nid] as usize;
        city_root_seen[root] = true;
        if !city_root_coords[root].contains(&(r, c)) {
            city_root_coords[root].push((r, c));
        }
        if city_open[nid] {
            city_root_is_open[root] = true;
        }
        let (dr, dc, _o) = opp(ix);
        let (nr, ncol) = (r + dr, c + dc);
        if nr >= 0
            && nr < BOARD_ROWS
            && ncol >= 0
            && ncol < BOARD_COLS
            && state.get_tile(nr, ncol).is_none()
            && !city_root_emptyadj[root].contains(&(nr, ncol))
        {
            city_root_emptyadj[root].push((nr, ncol));
        }
    }
    let mut city_root_finished = vec![false; nc];
    let mut city_root_open_n = vec![0usize; nc];
    let mut city_root_delta = vec![0i64; nc];
    for root in 0..nc {
        if !city_root_seen[root] {
            continue;
        }
        city_root_finished[root] = !city_root_is_open[root];
        city_root_open_n[root] = city_root_emptyadj[root].len();
        let mut shields = 0i64;
        let mut cathedral = false;
        let mut total = 0i64;
        for &(r, c) in &city_root_coords[root] {
            let tile = tiles::tile(state.get_tile(r, c).unwrap());
            if !tile.inn.is_empty() {
                cathedral = true;
            }
            if tile.shield {
                shields += 1;
            }
            total += 1;
        }
        city_root_delta[root] = if cathedral {
            3 * total + 3 * shields
        } else {
            total + shields
        };
    }

    // ---- road facts -------------------------------------------------------- //
    let nr_nodes = road_nodes.len();
    let mut road_root_coords: Vec<Vec<(i32, i32)>> = vec![Vec::new(); nr_nodes];
    let mut road_root_is_open = vec![false; nr_nodes];
    let mut road_root_emptyadj: Vec<Vec<(i32, i32)>> = vec![Vec::new(); nr_nodes];
    let mut road_root_seen = vec![false; nr_nodes];
    for nid in 0..nr_nodes {
        let (r, c, ix) = road_nodes[nid];
        let root = road_labels[nid] as usize;
        road_root_seen[root] = true;
        if !road_root_coords[root].contains(&(r, c)) {
            road_root_coords[root].push((r, c));
        }
        if road_open[nid] {
            road_root_is_open[root] = true;
        }
        let (dr, dc, _o) = opp(ix);
        let (nrr, ncol) = (r + dr, c + dc);
        if nrr >= 0
            && nrr < BOARD_ROWS
            && ncol >= 0
            && ncol < BOARD_COLS
            && state.get_tile(nrr, ncol).is_none()
            && !road_root_emptyadj[root].contains(&(nrr, ncol))
        {
            road_root_emptyadj[root].push((nrr, ncol));
        }
    }
    let mut road_root_finished = vec![false; nr_nodes];
    let mut road_root_open_n = vec![0usize; nr_nodes];
    for root in 0..nr_nodes {
        if !road_root_seen[root] {
            continue;
        }
        road_root_finished[root] = !road_root_is_open[root];
        road_root_open_n[root] = road_root_emptyadj[root].len();
    }

    // ---- farm facts -------------------------------------------------------- //
    let nf = farm_node_rc.len();
    let mut farm_pos0_root: Vec<i32> = vec![-1; n_cells * 9];
    let mut farm_anypos_root: Vec<i32> = vec![-1; n_cells * 9];
    let mut farm_root_members: Vec<Vec<u32>> = vec![Vec::new(); nf];
    for nid in 0..nf {
        let root = farm_labels[nid] as usize;
        let (r, c) = farm_node_rc[nid];
        let o = ord_of(r, c).unwrap();
        farm_root_members[root].push(nid as u32);
        let tid = state.get_tile(r, c).unwrap();
        let fp = &tiles::tile(tid).farms[farm_node_slot[nid] as usize].farmer_positions;
        if !fp.is_empty() {
            farm_pos0_root[o * 9 + fp[0] as usize] = root as i32;
            for &pos in fp {
                farm_anypos_root[o * 9 + pos as usize] = root as i32;
            }
        }
    }

    let mut farm_root_adj_city_roots: Vec<Vec<u32>> = vec![Vec::new(); nf];
    let mut farm_root_finished_cities: Vec<usize> = vec![0; nf];
    for root in 0..nf {
        if farm_root_members[root].is_empty() {
            continue;
        }
        let mut adj: Vec<u32> = Vec::new();
        for &nid in &farm_root_members[root] {
            let (r, c) = farm_node_rc[nid as usize];
            let o = ord_of(r, c).unwrap();
            let tid = state.get_tile(r, c).unwrap();
            let sides = &tiles::tile(tid).farms[farm_node_slot[nid as usize] as usize].city_sides;
            for &cs in sides {
                let cnid = city_node_id[o * 9 + cs as usize];
                if cnid >= 0 {
                    let croot = city_labels[cnid as usize];
                    if !adj.contains(&croot) {
                        adj.push(croot);
                    }
                }
            }
        }
        farm_root_finished_cities[root] = adj
            .iter()
            .filter(|&&croot| city_root_finished[croot as usize])
            .count();
        farm_root_adj_city_roots[root] = adj;
    }

    Decomp {
        placed,
        city_nodes,
        city_labels,
        city_node_id,
        city_root_coords,
        city_root_finished,
        city_root_open_n,
        city_root_delta,
        road_nodes,
        road_labels,
        road_node_id,
        road_root_coords,
        road_root_finished,
        road_root_open_n,
        farm_node_rc,
        farm_node_slot,
        farm_labels,
        farm_pos0_root,
        farm_anypos_root,
        farm_root_adj_city_roots,
        farm_root_finished_cities,
    }
}
