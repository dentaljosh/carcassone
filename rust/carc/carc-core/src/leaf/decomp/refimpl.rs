//! The **frozen reference decomposition** — the gates' oracle.
//!
//! [`decompose_into_ref`] is `decompose_into` exactly as it stood at rev
//! `ec0e52bb`, before the 2026-08-30 registry flattening: it reads the tile
//! registry through the object path (`tiles::tile(id)` → `Vec<Vec<Side>>`,
//! `Vec<FarmerConn>`), chasing a heap pointer per list.
//!
//! It exists for one reason: the flattening claims **bit-identical output**, and
//! a bit-identity claim needs an oracle inside the same binary.  Every gate in
//! `examples/registry_flat_gate.rs` and the unit tests below compare
//! `decompose_into` against this function across all 25 `Decomp` fields
//! ([`decomp_diff`]).
//!
//! ⚠️ **Do not "fix", optimise or refactor this function.**  Its value is that
//! it is frozen.  If a genuine behaviour change to the decomposition is ever
//! made, change `decompose_into`, watch this gate fail, and only then port the
//! change here with the reason recorded — never edit both in one motion.
//!
//! It is never called on any production path; the only cost of keeping it is a
//! few hundred bytes of text.

use super::{
    count_distinct_per_group, fill, label_components_into, opp, Decomp, Scratch, N_CELLS,
};
use crate::engine::{GameState, BOARD_COLS, BOARD_ROWS};
use crate::tiles::{self, Side, TileId};

/// `decompose_into` as of rev `ec0e52bb` — the object-registry path.  FROZEN.
pub fn decompose_into_ref(state: &GameState, out: &mut Decomp, sc: &mut Scratch) {
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
    fill(&mut sc.farm_side_to_node, n_cells * 8, -1i32);

    for (o, &(r, c)) in placed.iter().enumerate() {
        let tid: TileId = state
            .get_tile(r, c)
            .expect("placed_coords names an empty cell");
        let tile = tiles::tile(tid);

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
                        sc.city_eu.push(f);
                        sc.city_ev.push(nid);
                    }
                }
            }
        }

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
                sc.road_eu.push(x);
                sc.road_ev.push(y);
            }
        }

        for (slot, fc) in tile.farms.iter().enumerate() {
            let nid = farm_node_rc.len() as i32;
            farm_node_rc.push((r, c));
            farm_node_slot.push(slot as u8);
            for &fs in &fc.tile_connections {
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
                let neighbor = sc.farm_side_to_node[no * 8 + fs.opposite() as usize];
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
            let tile = tiles::tile(state.get_tile(r, c).unwrap());
            city_root_tiles[root] += 1;
            if tile.shield {
                city_root_shields[root] += 1;
            }
            if !tile.inn.is_empty() {
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
            if !tiles::tile(state.get_tile(r, c).unwrap()).inn.is_empty() {
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
    fill(farm_root_finished_cities, nf, 0usize);
    for &k in farm_adj.iter() {
        if city_root_finished[(k as u32) as usize] {
            farm_root_finished_cities[(k >> 32) as usize] += 1;
        }
    }
}

/// Allocating wrapper around [`decompose_into_ref`].
pub fn decompose_ref(state: &GameState) -> Decomp {
    let mut d = Decomp::default();
    let mut sc = Scratch::default();
    decompose_into_ref(state, &mut d, &mut sc);
    d
}

/// Field-for-field comparator over **all 25** `Decomp` fields — 19 structural
/// plus the 6 city-root arrays.  `Err(name)` names the first field that differs.
///
/// Lifted verbatim from the L1 delta spike (`delta::decomp_diff`,
/// `measurement/l1_delta_decompose_spike_20260830/`) so the two rounds' gates
/// compare exactly the same surface.
pub fn decomp_diff(a: &Decomp, b: &Decomp) -> Result<(), &'static str> {
    macro_rules! f {
        ($n:ident) => {
            if a.$n != b.$n {
                return Err(stringify!($n));
            }
        };
    }
    // 19 structural fields
    f!(placed);
    f!(cell_ord);
    f!(city_nodes);
    f!(city_labels);
    f!(city_node_id);
    f!(road_nodes);
    f!(road_labels);
    f!(road_node_id);
    f!(road_root_tiles);
    f!(road_root_inn);
    f!(road_root_finished);
    f!(road_root_open_n);
    f!(farm_node_rc);
    f!(farm_node_slot);
    f!(farm_labels);
    f!(farm_pos0_root);
    f!(farm_anypos_root);
    f!(farm_adj);
    f!(farm_root_finished_cities);
    // 6 city root arrays
    f!(city_root_tiles);
    f!(city_root_shields);
    f!(city_root_cathedral);
    f!(city_root_finished);
    f!(city_root_open_n);
    f!(city_root_delta);
    Ok(())
}

/// The number of fields [`decomp_diff`] compares — 19 + 6.
pub const DECOMP_FIELDS: usize = 25;
