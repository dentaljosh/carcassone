//! The production leaf evaluator — a port of `src/carcassonne_ai/flat_leaf.py`.
//!
//! The leaf of record is **`v2_9_2_Bmild_cap8_curve125`** (`governance/
//! PRODUCTION.yaml`, leaf hash `a36d2e15a3b3d71d`): closure schedule
//! `{1: 0.5, 2: 0.2, 3: 0.05}`, caps 8/8, and the C5 meeple curve
//! `[-10, -5, -1.25, 0, 2.5, 3.75, 5, 6.25]` (the v2.9 curve x1.25). Nothing
//! here hard-codes it — [`LeafConfig::curve125`] is a convenience only, and the
//! reconcile gate drives the config in from Python.
//!
//! ## Determinism-critical details, all verified in `flat_leaf.py`
//!
//! * **`math.fsum` at three sites** — `flat_closure_bonus` (`contribs`),
//!   `flat_return_term` (`plist`, once per player) and `flat_farm_flip_term`
//!   (`contribs`). These are the `CANONICAL_BONUS_SUM` semantics: the sum is a
//!   function of the *multiset*, not of the iteration order, which is why the
//!   Python sets can be iterated in any order and why this port may too.
//!   [`crate::compat::fsum`] is the bit-exact Shewchuk port.
//! * **Fixed term order**: `base + bonus_self - bonus_opp`, then the curve (or
//!   `meeple_k`) differential, then **Term R, then Term F** as two separate
//!   gated adds. Float addition is not associative; fusing them would break
//!   3-way bit-exactness (the comment at `flat_leaf.py:1045` says so explicitly).
//! * **`int(round(x))`** — CPython's `float.__round__` is round-half-to-even, so
//!   the terminal quantisation is [`f64::round_ties_even`], never `round()`.
//! * **Grid-bounded open counting** — see [`decomp`].
//! * The **cloister 3x3 in `_cloister_points` is bounds-checked**, unlike the
//!   engine's `chapel_or_flowers_points`, which indexes directly and lets
//!   CPython wrap negative rows. Both are reproduced where they are used: this
//!   module ports the *flat* (bounds-checked) one because that is what the
//!   measured leaf runs.
//!
//! ## Not implemented (Python raises / forces the object path)
//!
//! `tile_counting_closure` and `closure_continuous_slack` make
//! `flat_closure_bonus` raise `NotImplementedError`; [`leaf_value_float`]
//! returns [`LeafError::UnsupportedConfig`] for the same configs. The `v28_*`
//! and `v29_util_tanh_t` / `punish` / `farm_access` knobs are *silently ignored*
//! by `flat_leaf.py` (their dispatch happens in `virtual_score_v2`), so they are
//! ignored here too — a caller that sets them is off the flat path in Python and
//! must not be routed here.

pub mod decomp;

pub use decomp::{decompose, Decomp};

use crate::compat::fsum;
use crate::engine::{GameState, MeepleType, BOARD_COLS, BOARD_ROWS};
use crate::tiles::{self, TerrainType};

/// `flat_leaf._FLIP_BETA` (C7 Term F, a module constant, not a config field).
pub const FLIP_BETA: f64 = 0.5;
/// `flat_leaf._FLIP_RAMP`.
pub const FLIP_RAMP: f64 = 2.0;

/// The C5 production curve: the v2.9 curve scaled x1.25 (`governance/PRODUCTION.yaml`).
pub const CURVE125: [f64; 8] = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25];
/// The pre-C5 v2.9 curve — what `tests/golden/golden_fixture.json` was frozen on.
pub const CURVE_V29: [f64; 8] = [-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LeafError {
    /// `flat_closure_bonus` raises `NotImplementedError` for these.
    UnsupportedConfig,
    /// `flat_return_term` raises `ValueError` when Term R is on without a curve.
    ReturnTermNeedsCurve,
    /// `flat_virtual_score_v2` raises `ValueError` for `players != 2`.
    NotTwoPlayer,
}

/// `virtual_score_v2.LeafConfig`, restricted to the fields the **flat** leaf
/// actually reads.
#[derive(Clone, Debug, PartialEq)]
pub struct LeafConfig {
    /// `{open_positions: P(closure)}`; absent keys are `0.0` (`dict.get(n, 0.0)`).
    pub closure_p: Vec<(i32, f64)>,
    pub bonus_cap: f64,
    pub opp_bonus_cap: f64,
    pub meeple_k: f64,
    pub v29_meeple_curve: Option<Vec<f64>>,
    pub soft_cap_slope: f64,
    pub opp_soft_cap_slope: f64,
    pub v29_meeple_return_k: f64,
    pub v29_farm_flip_k: f64,
    pub bag_close: bool,
    pub tile_counting_closure: bool,
    pub closure_continuous_slack: f64,
}

impl LeafConfig {
    /// The `Bmild` closure schedule (`DROP_THREE_OPEN=0`): `{1:0.5, 2:0.2, 3:0.05}`.
    pub fn bmild_closure() -> Vec<(i32, f64)> {
        vec![(1, 0.5), (2, 0.2), (3, 0.05)]
    }

    /// `v2_9_2_Bmild_cap8_curve125` — the champion leaf of record.
    pub fn curve125() -> Self {
        LeafConfig {
            closure_p: Self::bmild_closure(),
            bonus_cap: 8.0,
            opp_bonus_cap: 8.0,
            meeple_k: 2.0, // inert under a non-null curve
            v29_meeple_curve: Some(CURVE125.to_vec()),
            soft_cap_slope: 0.0,
            opp_soft_cap_slope: 0.0,
            v29_meeple_return_k: 0.0,
            v29_farm_flip_k: 0.0,
            bag_close: false,
            tile_counting_closure: false,
            closure_continuous_slack: 0.0,
        }
    }

    /// `closure_p.get(n, 0.0)`.
    #[inline]
    fn close_prob(&self, n: i32) -> f64 {
        for &(k, v) in &self.closure_p {
            if k == n {
                return v;
            }
        }
        0.0
    }

    #[inline]
    fn c7_off(&self) -> bool {
        self.v29_meeple_return_k == 0.0 && self.v29_farm_flip_k == 0.0
    }
}

// ---------------------------------------------------------------------------
// Base score (`flat_leaf._final_scores` + `flat_base_score`)
// ---------------------------------------------------------------------------

/// `flat_leaf._meeple_weight`.
#[inline]
fn meeple_weight(mt: MeepleType) -> i64 {
    match mt {
        MeepleType::Big | MeepleType::BigFarmer => 2,
        _ => 1,
    }
}

/// `flat_leaf._winners`.
#[inline]
fn winners(counts: [i64; 2]) -> [bool; 2] {
    let m = counts[0].max(counts[1]);
    if m == 0 {
        return [false, false];
    }
    [counts[0] == m, counts[1] == m]
}

/// `flat_leaf._city_points`, evaluated from the component's precomputed
/// distinct-tile aggregates (`total`, `shields`, `has cathedral`).
#[inline]
fn city_points(d: &Decomp, root: u32) -> i64 {
    let r = root as usize;
    let (shields, total) = (d.city_root_shields[r], d.city_root_tiles[r]);
    let cathedral = d.city_root_cathedral[r];
    let finished = d.city_root_finished[r];
    if !finished && cathedral {
        return 0;
    }
    if cathedral {
        return 6 * shields + 3 * (total - shields);
    }
    if finished {
        return 4 * shields + 2 * (total - shields);
    }
    2 * shields + (total - shields)
}

/// `flat_leaf._road_points`.
#[inline]
fn road_points(d: &Decomp, root: u32) -> i64 {
    let r = root as usize;
    let inn = d.road_root_inn[r];
    if !d.road_root_finished[r] && inn {
        return 0;
    }
    (if inn { 2 } else { 1 }) * d.road_root_tiles[r]
}

/// `flat_leaf._cloister_points` — bounds-checked 3x3 including the centre.
fn cloister_points(state: &GameState, r: i32, c: i32) -> i64 {
    let mut pts = 0;
    for rr in (r - 1)..=(r + 1) {
        if rr < 0 || rr >= BOARD_ROWS {
            continue;
        }
        for cc in (c - 1)..=(c + 1) {
            if cc < 0 || cc >= BOARD_COLS {
                continue;
            }
            if state.get_tile(rr, cc).is_some() {
                pts += 1;
            }
        }
    }
    pts
}

/// `flat_leaf._final_scores` — the points `count_final_scores` would ADD.
fn final_scores(state: &GameState, d: &Decomp) -> [i64; 2] {
    // root -> per-player weighted meeple counts, in first-touch order
    let mut city_counts: Vec<(u32, [i64; 2])> = Vec::new();
    let mut road_counts: Vec<(u32, [i64; 2])> = Vec::new();
    let mut farm_counts: Vec<(u32, [i64; 2])> = Vec::new();
    let mut cloister_awards: Vec<(usize, i64)> = Vec::new();

    #[inline]
    fn bump(v: &mut Vec<(u32, [i64; 2])>, root: u32, player: usize, w: i64) {
        for e in v.iter_mut() {
            if e.0 == root {
                e.1[player] += w;
                return;
            }
        }
        let mut cnt = [0i64; 2];
        cnt[player] += w;
        v.push((root, cnt));
    }

    for player in 0..2 {
        for mp in &state.placed_meeples[player] {
            let (r, c, side) = (mp.coord.row, mp.coord.col, mp.side);
            let tile = tiles::tile(state.get_tile(r, c).expect("meeple on an empty cell"));
            let terrain = tile.get_type(side);
            let w = meeple_weight(mp.meeple_type);
            if terrain == Some(TerrainType::City) {
                if let Some(root) = d.city_side_root(r, c, side) {
                    bump(&mut city_counts, root, player, w);
                }
            } else if terrain == Some(TerrainType::Road) {
                if let Some(root) = d.road_side_root(r, c, side) {
                    bump(&mut road_counts, root, player, w);
                }
            } else if terrain == Some(TerrainType::Chapel) || terrain == Some(TerrainType::Flowers)
            {
                cloister_awards.push((player, cloister_points(state, r, c)));
            } else if mp.meeple_type == MeepleType::Farmer
                || mp.meeple_type == MeepleType::BigFarmer
            {
                if let Some(root) = d.farm_pos0_root(r, c, side) {
                    bump(&mut farm_counts, root, player, w);
                }
            }
        }
    }

    let mut final_pts = [0i64; 2];
    for &(root, counts) in &city_counts {
        let w = winners(counts);
        if !w[0] && !w[1] {
            continue;
        }
        let pts = city_points(d, root);
        for p in 0..2 {
            if w[p] {
                final_pts[p] += pts;
            }
        }
    }
    for &(root, counts) in &road_counts {
        let w = winners(counts);
        if !w[0] && !w[1] {
            continue;
        }
        let pts = road_points(d, root);
        for p in 0..2 {
            if w[p] {
                final_pts[p] += pts;
            }
        }
    }
    for &(root, counts) in &farm_counts {
        let w = winners(counts);
        if !w[0] && !w[1] {
            continue;
        }
        let pts = 3 * d.farm_root_finished_cities[root as usize] as i64;
        for p in 0..2 {
            if w[p] {
                final_pts[p] += pts;
            }
        }
    }
    for &(player, pts) in &cloister_awards {
        final_pts[player] += pts;
    }
    final_pts
}

/// `flat_leaf.flat_base_score(state, player, decomp)` — the pure-integer
/// end-of-game score differential, computed from the flat decomposition.
///
/// This is the *flat* route. `engine::GameState::flat_base_score` is the
/// independent engine route (clone + `count_final_scores`); the P2 test suite
/// asserts they agree on every position, which is a free cross-check of the
/// whole decomposition.
pub fn flat_base_score(state: &GameState, player: usize, d: &Decomp) -> i64 {
    let f = final_scores(state, d);
    let opp = 1 - player;
    let running = state.scores[player] - state.scores[opp];
    running + (f[player] - f[opp])
}

// ---------------------------------------------------------------------------
// v2.10 bag-aware closure gate
// ---------------------------------------------------------------------------

/// `flat_leaf._bag_stats` — `(n, ge1, ge2, ge3, ge4)` over the remaining tiles.
pub fn bag_stats(state: &GameState) -> [i32; 5] {
    let mut out = [0i32; 5];
    let mut consider = |base: u16| {
        out[0] += 1;
        let tile = tiles::tile(tiles::tile_id(base, 0));
        let ne: usize = tile.city.iter().map(|g| g.len()).sum();
        if ne >= 1 {
            out[1] += 1;
            if ne >= 2 {
                out[2] += 1;
                if ne >= 3 {
                    out[3] += 1;
                    if ne >= 4 {
                        out[4] += 1;
                    }
                }
            }
        }
    };
    for &b in state.remaining_deck() {
        consider(b);
    }
    // The in-hand tile counts only in the TILES phase (in MEEPLES it is a stale
    // reference to the tile just placed).
    if let Some(nt) = state.next_tile {
        if state.phase == crate::engine::Phase::Tiles {
            consider(nt);
        }
    }
    out
}

/// `flat_leaf._city_faces_ge` — `(ge2, ge3, ge4)` open cells by face demand.
fn city_faces_ge(state: &GameState, d: &Decomp, root: u32) -> (i32, i32, i32) {
    let mut faces: Vec<(i32, i32)> = Vec::new(); // (cell key, count)
    for (r, c, ix) in d.city_root_positions(root) {
        let (dr, dc) = match ix {
            0 => (-1, 0),
            1 => (0, 1),
            2 => (1, 0),
            3 => (0, -1),
            other => panic!("_OPP has no entry for side ix {other}"),
        };
        let (nr, nc) = (r + dr, c + dc);
        if nr >= 0
            && nr < BOARD_ROWS
            && nc >= 0
            && nc < BOARD_COLS
            && state.get_tile(nr, nc).is_none()
        {
            let key = nr * BOARD_COLS + nc;
            match faces.iter_mut().find(|e| e.0 == key) {
                Some(e) => e.1 += 1,
                None => faces.push((key, 1)),
            }
        }
    }
    let (mut ge2, mut ge3, mut ge4) = (0, 0, 0);
    for &(_, v) in &faces {
        if v >= 2 {
            ge2 += 1;
            if v >= 3 {
                ge3 += 1;
                if v >= 4 {
                    ge4 += 1;
                }
            }
        }
    }
    (ge2, ge3, ge4)
}

/// `flat_leaf._bag_city_ok` — Hall's condition on the nested `>=k`-edge classes.
#[inline]
fn bag_city_ok(open_n: i32, faces_ge: (i32, i32, i32), bag: &[i32; 5]) -> bool {
    open_n <= bag[1] && faces_ge.0 <= bag[2] && faces_ge.1 <= bag[3] && faces_ge.2 <= bag[4]
}

// ---------------------------------------------------------------------------
// Closure-anticipation bonus
// ---------------------------------------------------------------------------

/// `flat_leaf._surrounding_count` — placed tiles among the 8 neighbours.
fn surrounding_count(state: &GameState, r: i32, c: i32) -> i32 {
    let mut n = 0;
    for dr in -1i32..=1 {
        for dc in -1i32..=1 {
            if dr == 0 && dc == 0 {
                continue;
            }
            let (rr, cc) = (r + dr, c + dc);
            if rr >= 0
                && rr < BOARD_ROWS
                && cc >= 0
                && cc < BOARD_COLS
                && state.get_tile(rr, cc).is_some()
            {
                n += 1;
            }
        }
    }
    n
}

/// `flat_leaf.flat_closure_bonus` — UNCAPPED, `math.fsum`-reduced.
pub fn closure_bonus(
    state: &GameState,
    player: usize,
    d: &Decomp,
    cfg: &LeafConfig,
    bag: Option<&[i32; 5]>,
) -> Result<f64, LeafError> {
    if cfg.tile_counting_closure || cfg.closure_continuous_slack > 0.0 {
        return Err(LeafError::UnsupportedConfig);
    }

    let mut knight_roots: Vec<u32> = Vec::new();
    let mut cloister_tiles: Vec<(i32, i32)> = Vec::new();
    let mut farm_roots: Vec<u32> = Vec::new();

    for mp in &state.placed_meeples[player] {
        let (r, c, side) = (mp.coord.row, mp.coord.col, mp.side);
        let terrain = tiles::tile(state.get_tile(r, c).unwrap()).get_type(side);
        if terrain == Some(TerrainType::City) {
            if let Some(root) = d.city_side_root(r, c, side) {
                if !knight_roots.contains(&root) {
                    knight_roots.push(root);
                }
            }
        } else if terrain == Some(TerrainType::Chapel) || terrain == Some(TerrainType::Flowers) {
            cloister_tiles.push((r, c));
        } else if mp.meeple_type == MeepleType::Farmer || mp.meeple_type == MeepleType::BigFarmer {
            if let Some(root) = d.farm_anypos_root(r, c, side) {
                if !farm_roots.contains(&root) {
                    farm_roots.push(root);
                }
            }
        }
    }

    // memoised per-city face demand; only consulted when the bag gate is ON
    let mut faces_memo: Vec<(u32, (i32, i32, i32))> = Vec::new();
    let bag_ok = |croot: u32, memo: &mut Vec<(u32, (i32, i32, i32))>| -> bool {
        let bag = bag.unwrap();
        let fg = match memo.iter().find(|e| e.0 == croot) {
            Some(e) => e.1,
            None => {
                let fg = city_faces_ge(state, d, croot);
                memo.push((croot, fg));
                fg
            }
        };
        bag_city_ok(d.city_root_open_n[croot as usize] as i32, fg, bag)
    };

    let mut contribs: Vec<f64> = Vec::new();

    // City closures.
    for &root in &knight_roots {
        if d.city_root_finished[root as usize] {
            continue;
        }
        let open_n = d.city_root_open_n[root as usize] as i32;
        if open_n <= 0 {
            continue; // D16: unclosable board-edge city
        }
        let p = cfg.close_prob(open_n);
        if p > 0.0 && (bag.is_none() || bag_ok(root, &mut faces_memo)) {
            contribs.push(p * d.city_root_delta[root as usize] as f64);
        }
    }

    // Cloister completion.
    for &(r, c) in &cloister_tiles {
        let needed = 8 - surrounding_count(state, r, c);
        if needed > 0 {
            let p = cfg.close_prob(needed);
            if p > 0.0 && (bag.is_none() || needed <= bag.unwrap()[0]) {
                contribs.push(p * needed as f64);
            }
        }
    }

    // Farm growth: incomplete cities adjacent to the player's fields.
    let mut growth_roots: Vec<u32> = Vec::new();
    for &froot in &farm_roots {
        for croot in d.farm_adj_city_roots(froot) {
            if !growth_roots.contains(&croot) {
                growth_roots.push(croot);
            }
        }
    }
    for &croot in &growth_roots {
        if d.city_root_finished[croot as usize] {
            continue;
        }
        let open_n = d.city_root_open_n[croot as usize] as i32;
        if open_n <= 0 {
            continue;
        }
        let p = cfg.close_prob(open_n);
        if p > 0.0 && (bag.is_none() || bag_ok(croot, &mut faces_memo)) {
            contribs.push(p * 3.0);
        }
    }

    Ok(fsum(&contribs))
}

/// `flat_leaf._capped`.
#[inline]
fn capped(bonus: f64, cap: f64) -> f64 {
    if bonus > cap {
        cap
    } else {
        bonus
    }
}

/// `flat_leaf._soft_capped` — `slope == 0.0` delegates to the hard clamp.
#[inline]
fn soft_capped(bonus: f64, cap: f64, slope: f64) -> f64 {
    if slope == 0.0 {
        return capped(bonus, cap);
    }
    if bonus > cap {
        cap + slope * (bonus - cap)
    } else {
        bonus
    }
}

/// `flat_leaf._flat_curve_lookup`.
#[inline]
fn curve_lookup(curve: &[f64], n: i32) -> f64 {
    let l = curve.len() as i32;
    let i = if n < 0 {
        0
    } else if n >= l {
        l - 1
    } else {
        n
    };
    curve[i as usize]
}

/// `flat_leaf._flat_dcurve`.
#[inline]
fn dcurve(curve: &[f64], n: i32) -> f64 {
    let l = curve.len() as i32;
    let mut hi = n + 1;
    if hi > l - 1 {
        hi = l - 1;
    }
    let mut lo = n;
    if lo < 0 {
        lo = 0;
    }
    if lo > l - 1 {
        lo = l - 1;
    }
    curve[hi as usize] - curve[lo as usize]
}

// ---------------------------------------------------------------------------
// C7 wave-2 terms
// ---------------------------------------------------------------------------

/// `flat_leaf.flat_return_term` — Term R, the uncapped `ret(p) - ret(opp)`.
pub fn return_term(
    state: &GameState,
    player: usize,
    d: &Decomp,
    cfg: &LeafConfig,
) -> Result<f64, LeafError> {
    let curve = match &cfg.v29_meeple_curve {
        Some(c) => c,
        None => return Err(LeafError::ReturnTermNeedsCurve),
    };

    let ret = |p: usize| -> f64 {
        let mut plist: Vec<f64> = Vec::new();
        for mp in &state.placed_meeples[p] {
            let (r, c, side) = (mp.coord.row, mp.coord.col, mp.side);
            let terrain = tiles::tile(state.get_tile(r, c).unwrap()).get_type(side);
            if terrain == Some(TerrainType::City) {
                let root = match d.city_side_root(r, c, side) {
                    Some(x) => x,
                    None => continue,
                };
                if d.city_root_finished[root as usize] {
                    continue;
                }
                let open_n = d.city_root_open_n[root as usize] as i32;
                if open_n <= 0 {
                    continue;
                }
                let pr = cfg.close_prob(open_n);
                if pr > 0.0 {
                    plist.push(pr);
                }
            } else if terrain == Some(TerrainType::Road) {
                let root = match d.road_side_root(r, c, side) {
                    Some(x) => x,
                    None => continue,
                };
                if d.road_root_finished[root as usize] {
                    continue;
                }
                let open_n = d.road_root_open_n[root as usize] as i32;
                if open_n <= 0 {
                    continue;
                }
                let pr = cfg.close_prob(open_n);
                if pr > 0.0 {
                    plist.push(pr);
                }
            } else if terrain == Some(TerrainType::Chapel) || terrain == Some(TerrainType::Flowers)
            {
                let needed = 8 - surrounding_count(state, r, c);
                if needed <= 0 {
                    continue;
                }
                let pr = cfg.close_prob(needed);
                if pr > 0.0 {
                    plist.push(pr);
                }
            }
            // FARMER / BIG_FARMER never return.
        }
        dcurve(curve, state.meeples[p]) * fsum(&plist)
    };

    let opp = 1 - player;
    Ok(ret(player) - ret(opp))
}

/// `flat_leaf.flat_farm_flip_term` — Term F.
pub fn farm_flip_term(state: &GameState, player: usize, d: &Decomp) -> f64 {
    let opp = 1 - player;
    let mut field_counts: Vec<(u32, [i64; 2])> = Vec::new();
    for pl in 0..2 {
        for mp in &state.placed_meeples[pl] {
            let mt = mp.meeple_type;
            if mt != MeepleType::Farmer && mt != MeepleType::BigFarmer {
                continue;
            }
            let root = match d.farm_pos0_root(mp.coord.row, mp.coord.col, mp.side) {
                Some(x) => x,
                None => continue,
            };
            let w = if mt == MeepleType::BigFarmer { 2 } else { 1 };
            match field_counts.iter_mut().find(|e| e.0 == root) {
                Some(e) => e.1[pl] += w,
                None => {
                    let mut cnt = [0i64; 2];
                    cnt[pl] += w;
                    field_counts.push((root, cnt));
                }
            }
        }
    }

    let mut free_d = state.meeples[player] - state.meeples[opp];
    if free_d > 1 {
        free_d = 1;
    } else if free_d < -1 {
        free_d = -1;
    }

    let mut contribs: Vec<f64> = Vec::new();
    for &(root, cnt) in &field_counts {
        let w_me = cnt[player];
        let w_opp = cnt[opp];
        if w_me >= 1 && w_opp >= 1 {
            let v = (3 * d.farm_root_finished_cities[root as usize]) as f64;
            let m = w_me - w_opp;
            let step = if m > 0 {
                1.0
            } else if m < 0 {
                -1.0
            } else {
                0.0
            };
            let m_eff = m as f64 + FLIP_BETA * free_d as f64;
            let mut ramp = m_eff / FLIP_RAMP;
            if ramp > 1.0 {
                ramp = 1.0;
            } else if ramp < -1.0 {
                ramp = -1.0;
            }
            contribs.push(v * (ramp - step));
        }
    }
    fsum(&contribs)
}

// ---------------------------------------------------------------------------
// The leaf
// ---------------------------------------------------------------------------

/// Every term of one leaf evaluation — the divergence-hunting view.
#[derive(Clone, Debug, PartialEq)]
pub struct LeafTerms {
    pub base: i64,
    pub bonus_self_raw: f64,
    pub bonus_opp_raw: f64,
    pub bonus_self: f64,
    pub bonus_opp: f64,
    pub meeple_term: f64,
    pub return_term: f64,
    pub flip_term: f64,
    pub score: f64,
    pub value: i64,
}

/// `flat_leaf.flat_virtual_score_v2_float` — the pre-round float leaf, with the
/// per-term breakdown.
///
/// `bag_close` mirrors the Python resolution rule for an **explicit cfg**:
/// `cfg.bag_close`. (The `cfg is None` route reads the module/env flag, which
/// has no analogue here — the Rust API always takes an explicit config.)
pub fn leaf_terms(
    state: &GameState,
    player: usize,
    cfg: &LeafConfig,
) -> Result<LeafTerms, LeafError> {
    if state.players != 2 {
        return Err(LeafError::NotTwoPlayer);
    }
    let d = decompose(state);
    leaf_terms_with(state, player, cfg, &d)
}

/// [`leaf_terms`] against a decomposition the caller already paid for.
pub fn leaf_terms_with(
    state: &GameState,
    player: usize,
    cfg: &LeafConfig,
    d: &Decomp,
) -> Result<LeafTerms, LeafError> {
    if state.players != 2 {
        return Err(LeafError::NotTwoPlayer);
    }
    let opp = 1 - player;
    let bag = if cfg.bag_close {
        Some(bag_stats(state))
    } else {
        None
    };
    let bag_ref = bag.as_ref();

    let base = flat_base_score(state, player, d);
    let bonus_self_raw = closure_bonus(state, player, d, cfg, bag_ref)?;
    let bonus_opp_raw = closure_bonus(state, opp, d, cfg, bag_ref)?;
    let bonus_self = soft_capped(bonus_self_raw, cfg.bonus_cap, cfg.soft_cap_slope);
    let bonus_opp = soft_capped(bonus_opp_raw, cfg.opp_bonus_cap, cfg.opp_soft_cap_slope);

    // `score = base + bonus_self - bonus_opp` — left-associative, exactly as written.
    let mut score = base as f64 + bonus_self - bonus_opp;

    let meeple_term = match &cfg.v29_meeple_curve {
        Some(curve) => {
            curve_lookup(curve, state.meeples[player]) - curve_lookup(curve, state.meeples[opp])
        }
        None => {
            if cfg.meeple_k > 0.0 {
                cfg.meeple_k * (state.meeples[player] - state.meeples[opp]) as f64
            } else {
                0.0
            }
        }
    };
    if cfg.v29_meeple_curve.is_some() || cfg.meeple_k > 0.0 {
        score += meeple_term;
    }

    // C7: Term R then Term F — two SEPARATE gated adds, this fixed order.
    let mut r_term = 0.0;
    if cfg.v29_meeple_return_k != 0.0 {
        r_term = return_term(state, player, d, cfg)?;
        score += cfg.v29_meeple_return_k * r_term;
    }
    let mut f_term = 0.0;
    if cfg.v29_farm_flip_k != 0.0 {
        f_term = farm_flip_term(state, player, d);
        score += cfg.v29_farm_flip_k * f_term;
    }

    Ok(LeafTerms {
        base,
        bonus_self_raw,
        bonus_opp_raw,
        bonus_self,
        bonus_opp,
        meeple_term,
        return_term: r_term,
        flip_term: f_term,
        score,
        value: round_ties_even_i64(score),
    })
}

/// `int(round(x))` — CPython's `float.__round__` is round-half-to-even.
#[inline]
pub fn round_ties_even_i64(x: f64) -> i64 {
    x.round_ties_even() as i64
}

/// `flat_leaf.flat_virtual_score_v2_float`.
pub fn leaf_value_float(
    state: &GameState,
    player: usize,
    cfg: &LeafConfig,
) -> Result<f64, LeafError> {
    Ok(leaf_terms(state, player, cfg)?.score)
}

/// `flat_leaf.flat_virtual_score_v2`.
pub fn leaf_value(state: &GameState, player: usize, cfg: &LeafConfig) -> Result<i64, LeafError> {
    Ok(leaf_terms(state, player, cfg)?.value)
}

/// A convenience assertion used by the P2 tests: `_c7_off` mirrors the Python
/// capability check that decides whether a stale Cython `.so` may serve a config.
pub fn c7_off(cfg: &LeafConfig) -> bool {
    cfg.c7_off()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::Game;

    #[test]
    fn round_ties_even_matches_cpython() {
        assert_eq!(round_ties_even_i64(2.5), 2);
        assert_eq!(round_ties_even_i64(3.5), 4);
        assert_eq!(round_ties_even_i64(-2.5), -2);
        assert_eq!(round_ties_even_i64(-16.25), -16);
        assert_eq!(round_ties_even_i64(0.5), 0);
        assert_eq!(round_ties_even_i64(1.5), 2);
    }

    #[test]
    fn curve_lookup_clamps() {
        let c = CURVE125.to_vec();
        assert_eq!(curve_lookup(&c, -3), -10.0);
        assert_eq!(curve_lookup(&c, 0), -10.0);
        assert_eq!(curve_lookup(&c, 7), 6.25);
        assert_eq!(curve_lookup(&c, 40), 6.25);
        assert_eq!(dcurve(&c, 7), 0.0);
        assert_eq!(dcurve(&c, 3), 2.5);
    }

    /// The flat decomposition's base score must equal the engine's independent
    /// `count_final_scores` route at every ply — the cheapest available proof
    /// that `decompose` partitions the board the way the engine floods it.
    #[test]
    fn flat_base_matches_engine_base_over_a_greedy_game() {
        for seed in ["1", "2", "3", "17", "99"] {
            let mut g = Game::from_seed(seed);
            let mut plies = 0;
            while !g.is_terminal() && plies < 400 {
                let d = decompose(&g.state);
                for p in 0..2 {
                    assert_eq!(
                        flat_base_score(&g.state, p, &d),
                        g.state.flat_base_score(p),
                        "seed {seed} ply {plies} pov {p}"
                    );
                }
                let legal = g.legal_actions();
                g.advance(legal[0]).unwrap();
                plies += 1;
            }
        }
    }

    #[test]
    fn empty_board_leaf_is_the_curve_differential() {
        // The `_LEAF_VALUE_PANEL` shape: an empty board with only meeple counts.
        let mut g = Game::from_seed("1");
        g.state.next_tile = None;
        g.state.meeples = [3, 7];
        let cfg = LeafConfig::curve125();
        assert_eq!(leaf_value_float(&g.state, 0, &cfg).unwrap(), -6.25);
        g.state.meeples = [7, 3];
        assert_eq!(leaf_value_float(&g.state, 0, &cfg).unwrap(), 6.25);
        g.state.meeples = [0, 7];
        assert_eq!(leaf_value(&g.state, 0, &cfg).unwrap(), -16);
        g.state.meeples = [5, 5];
        assert_eq!(leaf_value_float(&g.state, 0, &cfg).unwrap(), 0.0);
    }
}
