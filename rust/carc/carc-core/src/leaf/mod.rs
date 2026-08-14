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
/// J-RULES AS POLICY PRIORS (surface B) — expansion-time prior modulation for
/// the search. NOT a leaf term: nothing in it touches [`LeafConfig`], any leaf
/// value, or any leaf hash. It lives under `leaf` because it shares the
/// [`Decomp`] and the `jr_*` predicate helpers with surface A.
pub mod jrules_prior;

pub use decomp::{decompose, decompose_into, Decomp, Scratch};
pub use jrules_prior::{jr_prior_clock, jrules_prior_term, JrPriorClock};

/// Reusable working set for a hot leaf loop (P3/P4 search rates).
///
/// One per search thread: `leaf_value_float_with` decomposes into the retained
/// [`Decomp`] using the retained [`Scratch`], so the whole leaf evaluation is
/// allocation-free after the first call.  Results are bit-identical to the
/// allocating path (the buffers are overwritten, never read stale) — asserted
/// by `scripts/rustport/reconcile_leaf.py` and by a unit test here.
#[derive(Default)]
pub struct LeafScratch {
    pub decomp: Decomp,
    pub scratch: Scratch,
}

impl LeafScratch {
    pub fn new() -> Self {
        Self::default()
    }

    /// `flat_leaf.flat_virtual_score_v2_float`, reusing this scratch.
    pub fn leaf_value_float(
        &mut self,
        state: &GameState,
        player: usize,
        cfg: &LeafConfig,
    ) -> Result<f64, LeafError> {
        if state.players != 2 {
            return Err(LeafError::NotTwoPlayer);
        }
        decompose_into(state, &mut self.decomp, &mut self.scratch);
        Ok(leaf_terms_with(state, player, cfg, &self.decomp)?.score)
    }

    /// `flat_leaf.flat_virtual_score_v2`, reusing this scratch.
    pub fn leaf_value(
        &mut self,
        state: &GameState,
        player: usize,
        cfg: &LeafConfig,
    ) -> Result<i64, LeafError> {
        if state.players != 2 {
            return Err(LeafError::NotTwoPlayer);
        }
        decompose_into(state, &mut self.decomp, &mut self.scratch);
        Ok(leaf_terms_with(state, player, cfg, &self.decomp)?.value)
    }

    /// [`Self::leaf_value_float`] / [`Self::leaf_value`] plus the raw
    /// `flat_base_score` — one decomposition for both, for the J-rules PRIOR
    /// surface (`jrules_prior`), whose J5/J8 need the naive count of the same
    /// afterstate the leaf just priced. The leaf component is BIT-IDENTICAL to
    /// the plain calls (same `leaf_terms_with`, same decomp); the caller may
    /// then read `self.decomp` (still this state's) for
    /// [`jrules_prior::jrules_prior_term`].
    ///
    /// `quantize_int` mirrors the search's `LeafQuantize`: `true` returns
    /// `value as f64` (the int leaf widened), `false` the float leaf.
    pub fn leaf_float_and_base(
        &mut self,
        state: &GameState,
        player: usize,
        cfg: &LeafConfig,
        quantize_int: bool,
    ) -> Result<(f64, f64), LeafError> {
        if state.players != 2 {
            return Err(LeafError::NotTwoPlayer);
        }
        decompose_into(state, &mut self.decomp, &mut self.scratch);
        let t = leaf_terms_with(state, player, cfg, &self.decomp)?;
        let leaf = if quantize_int { t.value as f64 } else { t.score };
        Ok((leaf, t.base as f64))
    }
}

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
    /// F7b: drop farm scoring from the BASE term (`final_scores` awards no field
    /// points). Default `false` == the champion leaf, bit-for-bit.
    pub farm_base_off: bool,
    /// F7b: drop the FARM-GROWTH block of the closure-anticipation bonus.
    /// Default `false` == the champion leaf, bit-for-bit.
    pub farm_growth_off: bool,
    /// Part C phase multiplier on the meeple curve
    /// (`measurement/curve_shape_scope_20260809/PREREG_DRAFT.md` §4). `0.0` (default)
    /// == no phase dependence == the champion leaf, bit-for-bit (early branch, NOT a
    /// multiply by 1.0). `== virtual_score_v2.LeafConfig.v29_phase_beta`.
    pub v29_phase_beta: f64,
    /// The RUN-LEVEL `E[f]` renormalizer, so `E[f_eff] = 1` over a game's empirical
    /// k-distribution (`scripts/classical_search/compute_phase_norm.py`). Supplied by
    /// the caller: the leaf must stay a pure function of `(state, cfg)`.
    pub v29_phase_norm: f64,
    /// Targeted denial on near-complete large opponent cities
    /// (`virtual_score_v2.LeafConfig.denial_dose`; BACKLOG 2026-05-16 item 3).
    /// `0.0` (default) == term fully off == the champion leaf, bit-for-bit (early
    /// branch, never a subtract of 0.0). A nonzero dose subtracts
    /// `dose * Σ (delta - denial_size_min + 1)` over every OPPONENT-strict-majority
    /// incomplete city with `0 < open_n <= denial_open_max` and
    /// `city_root_delta >= denial_size_min` — deliberately NOT subject to
    /// `opp_bonus_cap` (escaping that cap for near-complete large opponent cities
    /// is the point of the term; see [`denial_term`]).
    pub denial_dose: f64,
    /// `LeafConfig.denial_size_min` — anticipated-completed-value threshold (points).
    pub denial_size_min: f64,
    /// `LeafConfig.denial_open_max` — max distinct open cells to count as near-complete.
    pub denial_open_max: i32,
    /// Open-city discipline — penalize the acting side's OWN large open cities
    /// (`virtual_score_v2.LeafConfig.opencity_dose`; BACKLOG 2026-05-16, LEVER_INDEX
    /// "penalize large open cities", spec
    /// `measurement/opencity_term_20260812/TERM_SPEC.md`). `0.0` (default) == term
    /// fully off == the champion leaf, bit-for-bit (early branch, never a subtract of
    /// 0.0). A nonzero dose subtracts `dose * T` where `T` is the SIGNED differential
    /// built by [`opencity_term`].
    pub opencity_dose: f64,
    /// `LeafConfig.opencity_size_min` — city-size threshold in DISTINCT TILES.
    /// ⚠️ NOT the same units as `denial_size_min` (points / `city_root_delta`).
    pub opencity_size_min: f64,
    /// `LeafConfig.opencity_edge_min` — minimum distinct open cells for the penalty
    /// to fire (default 2 == the guides' "prefer one, tolerate two, avoid three").
    pub opencity_edge_min: i32,
    /// `LeafConfig.opencity_symmetric` — `true` (default) makes `T = pen(self) -
    /// pen(opp)`, keeping the leaf antisymmetric; `false` makes `T = pen(self)`.
    pub opencity_symmetric: bool,
    /// `LeafConfig.opencity_cap` (added 2026-08-14, the round-2 falsifier of
    /// CL-080's uncapped-product form) — PER-CITY cap on the raw product
    /// contribution, in the term's own units (before the dose multiply). `0.0`
    /// (default) == UNCAPPED == the cap branch is never taken, bit-exact with the
    /// CL-080-era term at the same dose. `> 0.0` -> each qualifying city
    /// contributes `min(raw, cap)`; at cap 1.0 the term degenerates to a count of
    /// qualifying cities per side.
    pub opencity_cap: f64,
    /// J-rules on search — the 2026-08-12 anchor interview's self-described strategy
    /// as ONE signed leaf term (`virtual_score_v2.LeafConfig.jrules_dose`, spec
    /// `measurement/jrules_on_search_20260813/DESIGN.md`). `0.0` (default) == bundle
    /// fully off == the champion leaf, bit-for-bit (early branch, never an add of
    /// 0.0). A nonzero dose **ADDS** `dose * T` — ⚠️ NOTE THE SIGN: `denial_dose`
    /// and `opencity_dose` are penalties and are SUBTRACTED; this bundle is a BONUS
    /// potential (the J-rules say what to seek, not only what to fear). `T` is the
    /// SIGNED differential built by [`jrules_term`].
    pub jrules_dose: f64,
    /// `LeafConfig.jrules_mask` — rule bitmask for ablations
    /// ([`JR_J1`] | [`JR_J2`] | [`JR_J5`] | [`JR_J6`] | [`JR_J8`] == [`JR_ALL`] == 31,
    /// the default and the primary cell).
    pub jrules_mask: i64,
}

/// `flat_leaf._PHASE_K0` — mid-deck, frozen by the prereg.
pub const PHASE_K0: f64 = 35.0;

/// `flat_leaf._phase_mult`: `clip(1 + beta*(k - K0)/K0, 0.0, 2.0) / norm`, with
/// `k = state.deck_len() + state.next_tile.is_some()` — the `fair_agent.k_remaining`
/// definition of record (NOT `bag_stats`' phase-conditional count).
#[inline]
fn phase_mult(state: &GameState, beta: f64, norm: f64) -> f64 {
    let k = state.deck_len() + usize::from(state.next_tile.is_some());
    let mut f = 1.0 + beta * (k as f64 - PHASE_K0) / PHASE_K0;
    if f < 0.0 {
        f = 0.0;
    } else if f > 2.0 {
        f = 2.0;
    }
    f / norm
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
            farm_base_off: false,
            farm_growth_off: false,
            v29_phase_beta: 0.0,
            v29_phase_norm: 1.0,
            denial_dose: 0.0,
            denial_size_min: 8.0,
            denial_open_max: 2,
            opencity_dose: 0.0,
            opencity_size_min: 4.0,
            opencity_edge_min: 2,
            opencity_symmetric: true,
            opencity_cap: 0.0,
            jrules_dose: 0.0,
            jrules_mask: JR_ALL,
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
///
/// `farm_off` (F7b, `flat_leaf._final_scores(..., farm_off)`) drops the farm award
/// entirely. Default route is `false` — see [`flat_base_score`].
fn final_scores(state: &GameState, d: &Decomp, farm_off: bool) -> [i64; 2] {
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
    if !farm_off {
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
    flat_base_score_farm(state, player, d, false)
}

/// [`flat_base_score`] with the F7b `farm_base_off` knockout — the analogue of
/// `flat_leaf.flat_base_score(state, player, decomp, farm_off)`. Only the leaf's own
/// base term passes `true`; every other route (the exact solver's terminal, the P1/P2
/// cross-checks) keeps full farm scoring.
pub fn flat_base_score_farm(state: &GameState, player: usize, d: &Decomp, farm_off: bool) -> i64 {
    let f = final_scores(state, d, farm_off);
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
    // F7b `farm_growth_off` severs exactly this block (default false == unchanged);
    // `contribs` is fsum-reduced, so dropping members is order-independent.
    if !cfg.farm_growth_off {
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
// Targeted denial (BACKLOG 2026-05-16 item 3; building 2026-08-11)
// ---------------------------------------------------------------------------

/// `flat_leaf.flat_denial_term` — the RAW denial magnitude `T >= 0` from
/// `player`'s POV; the leaf subtracts `cfg.denial_dose * T`.
///
/// A city component qualifies iff ALL of: opponent STRICT weighted-meeple
/// majority (`counts[opp] > counts[player]`, big meeple = 2 — tied / own /
/// unmeepled never fire), incomplete with `0 < open_n <= denial_open_max`
/// (`open_n == 0` is the D16 unclosable board-edge city), and
/// `city_root_delta >= denial_size_min` (the anticipated completed value the
/// closure bonus already prices). Each contributes
/// `delta - denial_size_min + 1.0` (left-associative, matching Python's
/// `float(delta) - size_min + 1.0`); the sum is `fsum`-reduced so iteration
/// order is irrelevant.
///
/// ⚠️ EXPLICITLY NOT SUBJECT TO `opp_bonus_cap`: escaping the opponent-
/// anticipation cap for the (large AND near-complete) conjunction is the entire
/// point of the term. It is applied as a separate uncapped subtraction in
/// [`leaf_terms_with`], on top of the existing (capped) anticipation.
pub fn denial_term(state: &GameState, player: usize, d: &Decomp, cfg: &LeafConfig) -> f64 {
    let opp = 1 - player;
    // city root -> per-player weighted meeple counts, first-touch order
    let mut city_counts: Vec<(u32, [i64; 2])> = Vec::new();
    for pl in 0..2 {
        for mp in &state.placed_meeples[pl] {
            let (r, c, side) = (mp.coord.row, mp.coord.col, mp.side);
            let tile = tiles::tile(state.get_tile(r, c).expect("meeple on an empty cell"));
            if tile.get_type(side) != Some(TerrainType::City) {
                continue;
            }
            let root = match d.city_side_root(r, c, side) {
                Some(x) => x,
                None => continue,
            };
            let w = meeple_weight(mp.meeple_type);
            match city_counts.iter_mut().find(|e| e.0 == root) {
                Some(e) => e.1[pl] += w,
                None => {
                    let mut cnt = [0i64; 2];
                    cnt[pl] += w;
                    city_counts.push((root, cnt));
                }
            }
        }
    }
    let mut contribs: Vec<f64> = Vec::new();
    for &(root, cnt) in &city_counts {
        if cnt[opp] <= cnt[player] {
            continue; // opponent STRICT majority only
        }
        let r = root as usize;
        if d.city_root_finished[r] {
            continue;
        }
        let open_n = d.city_root_open_n[r] as i32;
        if open_n <= 0 || open_n > cfg.denial_open_max {
            continue; // unclosable, or not near-complete
        }
        let delta = d.city_root_delta[r] as f64;
        if delta < cfg.denial_size_min {
            continue; // not large
        }
        contribs.push(delta - cfg.denial_size_min + 1.0);
    }
    fsum(&contribs)
}

// ---------------------------------------------------------------------------
// Open-city discipline (BACKLOG 2026-05-16 / PRO_STRATEGY_SCAN §F1; building 2026-08-12)
// ---------------------------------------------------------------------------

/// `flat_leaf.flat_opencity_term` — the SIGNED open-city differential `T` from
/// `player`'s POV; the leaf subtracts `cfg.opencity_dose * T`.
///
/// `T = pen(player) - pen(opp)` when `cfg.opencity_symmetric` (the default — so
/// `T` may be NEGATIVE when the opponent is the more overextended builder and the
/// leaf stays antisymmetric), else `pen(player)` alone.
///
/// `pen(pl) >= 0` sums, over every city component where `pl` holds a STRICT
/// weighted-meeple majority (big meeple = 2 — tied / unmeepled never fire; the
/// scope is deliberately the BUILDER's own object, never the opponent's, see the
/// spec), which is incomplete with `0 < open_n` and `open_n >= opencity_edge_min`,
/// and which spans `city_root_tiles >= opencity_size_min` DISTINCT TILES (tiles,
/// NOT `city_root_delta` points — denial's axis), the contribution
/// `(tiles - opencity_size_min + 1.0) * (open_n - opencity_edge_min + 1.0)`
/// (left-associative inside each factor, matching Python's
/// `(float(tiles) - size_min + 1.0) * (float(open_n) - float(edge_min) + 1.0)`).
/// Each side's sum is `fsum`-reduced so iteration order is irrelevant.
///
/// ⚠️ The penalty ADJUSTS the existing city terms, never replaces them: the
/// closure-anticipation credit for the same city is untouched, and this is applied
/// as a separate uncapped subtraction in [`leaf_terms_with`].
pub fn opencity_term(state: &GameState, player: usize, d: &Decomp, cfg: &LeafConfig) -> f64 {
    // city root -> per-player weighted meeple counts, first-touch order
    let mut city_counts: Vec<(u32, [i64; 2])> = Vec::new();
    for pl in 0..2 {
        for mp in &state.placed_meeples[pl] {
            let (r, c, side) = (mp.coord.row, mp.coord.col, mp.side);
            let tile = tiles::tile(state.get_tile(r, c).expect("meeple on an empty cell"));
            if tile.get_type(side) != Some(TerrainType::City) {
                continue;
            }
            let root = match d.city_side_root(r, c, side) {
                Some(x) => x,
                None => continue,
            };
            let w = meeple_weight(mp.meeple_type);
            match city_counts.iter_mut().find(|e| e.0 == root) {
                Some(e) => e.1[pl] += w,
                None => {
                    let mut cnt = [0i64; 2];
                    cnt[pl] += w;
                    city_counts.push((root, cnt));
                }
            }
        }
    }
    let mut contribs: [Vec<f64>; 2] = [Vec::new(), Vec::new()];
    for &(root, cnt) in &city_counts {
        let owner = if cnt[0] > cnt[1] {
            0usize
        } else if cnt[1] > cnt[0] {
            1usize
        } else {
            continue; // tied -> nobody owns the overextension
        };
        let r = root as usize;
        if d.city_root_finished[r] {
            continue;
        }
        let open_n = d.city_root_open_n[r] as i32;
        if open_n <= 0 || open_n < cfg.opencity_edge_min {
            continue; // unclosable, or not wide
        }
        let n_tiles = d.city_root_tiles[r];
        if (n_tiles as f64) < cfg.opencity_size_min {
            continue; // not large
        }
        let mut contrib = (n_tiles as f64 - cfg.opencity_size_min + 1.0)
            * (open_n as f64 - cfg.opencity_edge_min as f64 + 1.0);
        // per-city cap (0.0 == uncapped: branch never taken) — mirrors the Python
        // `if cap > 0.0 and contrib > cap` exactly (an explicit compare, not f64::min,
        // so the branch structure is identical on both sides).
        if cfg.opencity_cap > 0.0 && contrib > cfg.opencity_cap {
            contrib = cfg.opencity_cap;
        }
        contribs[owner].push(contrib);
    }
    let pen_self = fsum(&contribs[player]);
    if !cfg.opencity_symmetric {
        return pen_self;
    }
    pen_self - fsum(&contribs[1 - player])
}

// ---------------------------------------------------------------------------
// J-RULES ON SEARCH — the anchor's self-described strategy, as ONE leaf term
// (`measurement/jrules_on_search_20260813/DESIGN.md`; building 2026-08-13).
// A function-for-function mirror of the `flat_leaf.py` block of the same name;
// the Python names are `_jr_*` / `flat_jrules_term`.
// ---------------------------------------------------------------------------

/// `flat_leaf._JR_K0` — `k_remaining` at the FIRST decision of a 2-player
/// Base+Farmers game (71 undrawn + 1 in hand). `joshua_bot` latches this per game
/// (`Clock.k0`); the leaf must stay a pure function of `(state, cfg)`, so it is
/// FROZEN here exactly as Python freezes it.
pub const JR_K0: f64 = 72.0;

/// `flat_leaf.JR_J1` — large-open-city share premium ("sneak a meeple in").
pub const JR_J1: i64 = 1;
/// `flat_leaf.JR_J2` — farm value discipline (realized steal + low-value surrender).
pub const JR_J2: i64 = 2;
/// `flat_leaf.JR_J5` — signed unclaimed-feature value (J5 + J13).
pub const JR_J5: i64 = 4;
/// `flat_leaf.JR_J6` — anchor structure + road policy.
pub const JR_J6: i64 = 8;
/// `flat_leaf.JR_J8` — pivotal-feature overcommit.
pub const JR_J8: i64 = 16;
/// `flat_leaf.JR_ALL` — the default [`LeafConfig::jrules_mask`] (31).
pub const JR_ALL: i64 = JR_J1 | JR_J2 | JR_J5 | JR_J6 | JR_J8;

// --- the FROZEN `current`-preset parameter block ---------------------------
// Copied constant-for-constant from the Python block, which copied it from
// `joshua_bot.PRESETS["current"]`. Deliberately NOT config fields: the
// experiment's calibration axis is the single scalar `jrules_dose`.
const JR_J1_MIN_CITY_TILES: i64 = 5;
const JR_J1_MIN_OPEN_EDGES: usize = 2;
const JR_J1_JOIN_BONUS: f64 = 3.0;
const JR_J1_LATE_EXTRA: f64 = 1.0;
const JR_J4_MIN_URGENCY: f64 = 0.35;
/// Python `_JR_J4_FULL_RESERVE = 4`; only ever read as `float(...)`.
const JR_J4_FULL_RESERVE: f64 = 4.0;
const JR_J2_STEAL_W: f64 = 1.0;
const JR_J2_MIN_FARM_VALUE: f64 = 3.0;
const JR_J2_LOW_FARM_PENALTY: f64 = 2.0;
const JR_J2_UNFINISHED_CITY_W: f64 = 1.0;
const JR_J2_CITY_COUNT_FROM_K: usize = 36;
const JR_J2_CITY_CLOSE_OPEN_MAX: usize = 2;
const JR_J5_WEIGHT: f64 = 0.5;
const JR_J5_VALUE_FLOOR: f64 = 4.0;
const JR_J5_RESERVE_NORM: f64 = 2.0;
const JR_J6_ANCHOR_BONUS: f64 = 2.0;
const JR_J6_ANCHOR_CITY_MIN: i64 = 3;
const JR_J6_ANCHOR_ROAD_MIN: i64 = 2;
const JR_J6_ROAD_JOIN_MIN_LEN: i64 = 4;
const JR_J6_ROAD_JOIN_BONUS: f64 = 2.0;
const JR_J6_ROAD_SKEPTIC_MAX_LEN: i64 = 3;
const JR_J6_ROAD_CLAIM_PENALTY: f64 = 1.5;
const JR_J6_ROAD_ANCHOR_ALLOWANCE: i64 = 1;
const JR_J8_PIVOTAL_SWING: f64 = 12.0;
const JR_J8_OVERCOMMIT_BONUS: f64 = 3.0;
const JR_J8_VALUE_NORM: f64 = 10.0;
const JR_J8_MAX_CITY_MEEPLES: i64 = 2;
const JR_J8_MAX_FARM_MEEPLES: i64 = 3;

/// The `(root, [w0, w1])` association list that stands in for Python's dict.
/// Only ever consumed by `fsum`-reduced loops and by order-independent
/// booleans/counters, so first-touch order is not observable in the result.
type JrCounts = Vec<(u32, [i64; 2])>;

#[inline]
fn jr_bump(v: &mut JrCounts, root: u32, player: usize, w: i64) {
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

#[inline]
fn jr_has_root(v: &JrCounts, root: u32) -> bool {
    v.iter().any(|e| e.0 == root)
}

/// `flat_leaf._jr_counts` — weighted meeple counts per component plus the
/// CLAIMED-cloister cell set. Attribution mirrors [`final_scores`] exactly
/// (terrain of the meeple's own side; farmers via `farm_pos0_root`).
fn jr_counts(state: &GameState, d: &Decomp) -> (JrCounts, JrCounts, JrCounts, Vec<(i32, i32)>) {
    let mut city: JrCounts = Vec::new();
    let mut road: JrCounts = Vec::new();
    let mut farm: JrCounts = Vec::new();
    let mut cloister: Vec<(i32, i32)> = Vec::new();
    for pl in 0..2 {
        for mp in &state.placed_meeples[pl] {
            let (r, c, side) = (mp.coord.row, mp.coord.col, mp.side);
            // Python: `tile = board[r][c]; if tile is None: continue`.
            let tid = match state.get_tile(r, c) {
                Some(t) => t,
                None => continue,
            };
            let terrain = tiles::tile(tid).get_type(side);
            let w = meeple_weight(mp.meeple_type);
            if terrain == Some(TerrainType::City) {
                if let Some(root) = d.city_side_root(r, c, side) {
                    jr_bump(&mut city, root, pl, w);
                }
            } else if terrain == Some(TerrainType::Road) {
                if let Some(root) = d.road_side_root(r, c, side) {
                    jr_bump(&mut road, root, pl, w);
                }
            } else if terrain == Some(TerrainType::Chapel) || terrain == Some(TerrainType::Flowers)
            {
                if !cloister.contains(&(r, c)) {
                    cloister.push((r, c)); // Python: a `set`; membership only
                }
            } else if mp.meeple_type == MeepleType::Farmer
                || mp.meeple_type == MeepleType::BigFarmer
            {
                if let Some(root) = d.farm_pos0_root(r, c, side) {
                    jr_bump(&mut farm, root, pl, w);
                }
            }
        }
    }
    (city, road, farm, cloister)
}

/// `flat_leaf._jr_urgency` — J4, a multiplier in `[JR_J4_MIN_URGENCY, 1.0]` read
/// off the OTHER side's meeple reserve (which is what keeps the assembled
/// differential antisymmetric under a seat swap).
#[inline]
fn jr_urgency(opp_reserve: i32) -> f64 {
    let mut frac = opp_reserve as f64 / JR_J4_FULL_RESERVE;
    if frac > 1.0 {
        frac = 1.0;
    }
    JR_J4_MIN_URGENCY + (1.0 - JR_J4_MIN_URGENCY) * frac
}

/// `flat_leaf._jr_late_frac` — 0.0 at the first decision, 1.0 at the last tile.
#[inline]
fn jr_late_frac(k: usize) -> f64 {
    let f = 1.0 - (k as f64 / JR_K0);
    if f < 0.0 {
        return 0.0;
    }
    if f > 1.0 {
        1.0
    } else {
        f
    }
}

/// `min(1.0, x)` with CPython's `min` semantics (`x if x < 1.0 else 1.0`).
#[inline]
fn jr_min1(x: f64) -> f64 {
    if x < 1.0 {
        x
    } else {
        1.0
    }
}

/// `flat_leaf._jr_j1` — credit for holding a SHARE of a large, still-open city.
/// (The bot's `cnt[other] >= 1` join requirement is dropped: it self-cancels
/// under symmetrization — see the Python docstring.)
fn jr_j1(d: &Decomp, city_counts: &JrCounts, pl: usize, other: usize, late_frac: f64) -> f64 {
    let mut contribs: Vec<f64> = Vec::new();
    let bonus = JR_J1_JOIN_BONUS * (1.0 + JR_J1_LATE_EXTRA * late_frac);
    for &(root, cnt) in city_counts {
        let r = root as usize;
        if d.city_root_finished[r] {
            continue;
        }
        if cnt[pl] < 1 || cnt[pl] < cnt[other] {
            continue; // no share of this city
        }
        if d.city_root_tiles[r] < JR_J1_MIN_CITY_TILES {
            continue; // not "on the bigger side"
        }
        if d.city_root_open_n[r] < JR_J1_MIN_OPEN_EDGES {
            continue; // not "probably wont close"
        }
        contribs.push(bonus);
    }
    fsum(&contribs)
}

/// `flat_leaf._jr_farm_potential` — 3 points per adjacent city that is not
/// finished yet but is plausibly closable (FINISHED ones are already paid by
/// `flat_base_score`).
fn jr_farm_potential(d: &Decomp, root: u32, k: usize) -> f64 {
    if k > JR_J2_CITY_COUNT_FROM_K {
        return 0.0;
    }
    let mut n: i64 = 0;
    for croot in d.farm_adj_city_roots(root) {
        let cr = croot as usize;
        if d.city_root_finished[cr] {
            continue;
        }
        if d.city_root_open_n[cr] <= JR_J2_CITY_CLOSE_OPEN_MAX {
            n += 1;
        }
    }
    3.0 * n as f64 * JR_J2_UNFINISHED_CITY_W
}

/// `flat_leaf._jr_j2` — J2c realized steal + J10 surrender charge. (Same
/// symmetrization deviation as J1: the bot's `cnt[other] >= 1` is dropped.)
fn jr_j2(d: &Decomp, farm_counts: &JrCounts, pl: usize, other: usize, k: usize) -> f64 {
    let mut contribs: Vec<f64> = Vec::new();
    for &(root, cnt) in farm_counts {
        if cnt[pl] < 1 {
            continue;
        }
        let pot = jr_farm_potential(d, root, k);
        let value = 3.0 * d.farm_root_finished_cities[root as usize] as f64 + pot;
        if cnt[pl] >= cnt[other] && value >= JR_J2_MIN_FARM_VALUE {
            contribs.push(JR_J2_STEAL_W * pot);
        }
        if value < JR_J2_MIN_FARM_VALUE {
            contribs.push(-JR_J2_LOW_FARM_PENALTY * cnt[pl] as f64);
        }
    }
    fsum(&contribs)
}

/// `flat_leaf._jr_unclaimed_value` — total value on features NOBODY has a meeple
/// on, counting only the excess over [`JR_J5_VALUE_FLOOR`]. Seat-free by
/// construction (a property of the BOARD), which is what lets J5/J13 be one
/// signed term.
///
/// The Python iterates `decomp.city_root_coords` / `road_root_coords`, whose keys
/// are exactly the distinct component roots. Here the roots are recovered from
/// the label vectors: `label_components_into` writes `labels[x] = find(x)`, and a
/// root `r` satisfies `parent[r] == r`, hence `labels[r] == r`.
fn jr_unclaimed_value(
    state: &GameState,
    d: &Decomp,
    city_counts: &JrCounts,
    road_counts: &JrCounts,
    cloister_owned: &[(i32, i32)],
) -> f64 {
    let mut contribs: Vec<f64> = Vec::new();
    for nid in 0..d.city_labels.len() {
        if d.city_labels[nid] != nid as u32 {
            continue; // not a component root
        }
        if jr_has_root(city_counts, nid as u32) {
            continue;
        }
        let delta = d.city_root_delta[nid] as f64;
        let v = if d.city_root_finished[nid] {
            2.0 * delta
        } else {
            delta
        };
        if v > JR_J5_VALUE_FLOOR {
            contribs.push(v - JR_J5_VALUE_FLOOR);
        }
    }
    for nid in 0..d.road_labels.len() {
        if d.road_labels[nid] != nid as u32 {
            continue; // not a component root
        }
        if jr_has_root(road_counts, nid as u32) {
            continue;
        }
        // `road_root_tiles[root] == len(decomp.road_root_coords[root])`.
        let v = d.road_root_tiles[nid] as f64;
        if v > JR_J5_VALUE_FLOOR {
            contribs.push(v - JR_J5_VALUE_FLOOR);
        }
    }
    // Python scans `state.placed_coords`; `d.placed` is the same cell set (only
    // fsum-reduced below, so the order can never reach the leaf value).
    for &(r, c) in &d.placed {
        if cloister_owned.contains(&(r, c)) {
            continue;
        }
        let tid = match state.get_tile(r, c) {
            Some(t) => t,
            None => continue,
        };
        let terrain = tiles::tile(tid).get_type(tiles::Side::Center);
        if terrain != Some(TerrainType::Chapel) && terrain != Some(TerrainType::Flowers) {
            continue;
        }
        let v = cloister_points(state, r, c) as f64;
        if v > JR_J5_VALUE_FLOOR {
            contribs.push(v - JR_J5_VALUE_FLOOR);
        }
    }
    fsum(&contribs)
}

/// `flat_leaf._jr_claim_edge` — J13's `P_self(claim) - P_opp(claim)`, proxied by
/// the meeple-reserve differential and clipped to `[-1, 1]`.
#[inline]
fn jr_claim_edge(state: &GameState, player: usize, opp: usize) -> f64 {
    let e = (state.meeples[player] - state.meeples[opp]) as f64 / JR_J5_RESERVE_NORM;
    if e > 1.0 {
        return 1.0;
    }
    if e < -1.0 {
        -1.0
    } else {
        e
    }
}

/// `flat_leaf._jr_j6_anchor` — J6 (a)+(c): a bonus for holding one unfinished
/// city anchor and one unfinished road anchor, less a charge on every SOLO short
/// road claim past the one anchor road. NOT urgency-multiplied.
fn jr_j6_anchor(
    d: &Decomp,
    city_counts: &JrCounts,
    road_counts: &JrCounts,
    pl: usize,
    other: usize,
) -> f64 {
    let mut has_city = false;
    for &(root, cnt) in city_counts {
        let r = root as usize;
        if d.city_root_finished[r] || cnt[pl] <= cnt[other] {
            continue;
        }
        if d.city_root_tiles[r] >= JR_J6_ANCHOR_CITY_MIN {
            has_city = true;
            break;
        }
    }
    let mut has_road = false;
    let mut n_short_solo: i64 = 0;
    for &(root, cnt) in road_counts {
        let r = root as usize;
        if d.road_root_finished[r] {
            continue;
        }
        let length = d.road_root_tiles[r];
        if cnt[pl] > cnt[other] {
            if length >= JR_J6_ANCHOR_ROAD_MIN {
                has_road = true;
            }
            if cnt[other] == 0 && length <= JR_J6_ROAD_SKEPTIC_MAX_LEN {
                n_short_solo += 1;
            }
        }
    }
    let mut excess = n_short_solo - JR_J6_ROAD_ANCHOR_ALLOWANCE;
    if excess < 0 {
        excess = 0;
    }
    JR_J6_ANCHOR_BONUS * (i64::from(has_city) + i64::from(has_road)) as f64
        - JR_J6_ROAD_CLAIM_PENALTY * excess as f64
}

/// `flat_leaf._jr_j6_road_join` — credit for holding a share of a long unfinished
/// road (same symmetrization deviation as J1).
fn jr_j6_road_join(d: &Decomp, road_counts: &JrCounts, pl: usize, other: usize) -> f64 {
    let mut contribs: Vec<f64> = Vec::new();
    for &(root, cnt) in road_counts {
        let r = root as usize;
        if d.road_root_finished[r] {
            continue;
        }
        if cnt[pl] < 1 || cnt[pl] < cnt[other] {
            continue;
        }
        if d.road_root_tiles[r] < JR_J6_ROAD_JOIN_MIN_LEN {
            continue;
        }
        contribs.push(JR_J6_ROAD_JOIN_BONUS);
    }
    fsum(&contribs)
}

/// `flat_leaf._jr_j8` — pivotal-feature overcommit. `abs_margin` is `|base|` AT
/// THE LEAF (the bot reads the decision root's margin; a leaf has no root).
fn jr_j8(
    d: &Decomp,
    city_counts: &JrCounts,
    farm_counts: &JrCounts,
    pl: usize,
    other: usize,
    k: usize,
    abs_margin: f64,
) -> f64 {
    let mut contribs: Vec<f64> = Vec::new();
    for &(root, cnt) in city_counts {
        let r = root as usize;
        if d.city_root_finished[r] {
            continue;
        }
        if d.city_root_open_n[r] < 1 {
            continue; // he can no longer get in
        }
        let value = d.city_root_delta[r] as f64;
        let swing = 2.0 * value;
        if swing < JR_J8_PIVOTAL_SWING || swing < abs_margin {
            continue;
        }
        if cnt[pl] - cnt[other] < 2 || cnt[pl] > JR_J8_MAX_CITY_MEEPLES {
            continue;
        }
        contribs.push(JR_J8_OVERCOMMIT_BONUS * jr_min1(value / JR_J8_VALUE_NORM));
    }
    if k >= 1 {
        for &(root, cnt) in farm_counts {
            let value = 3.0 * d.farm_root_finished_cities[root as usize] as f64
                + jr_farm_potential(d, root, k);
            let swing = 2.0 * value;
            if swing < JR_J8_PIVOTAL_SWING || swing < abs_margin {
                continue;
            }
            if cnt[pl] - cnt[other] < 2 || cnt[pl] > JR_J8_MAX_FARM_MEEPLES {
                continue;
            }
            contribs.push(JR_J8_OVERCOMMIT_BONUS * jr_min1(value / JR_J8_VALUE_NORM));
        }
    }
    fsum(&contribs)
}

/// `flat_leaf.flat_jrules_term` — the SIGNED J-rules differential `T` from
/// `player`'s POV; the leaf **ADDS** `cfg.jrules_dose * T`.
///
/// ⚠️ NOTE THE SIGN. [`denial_term`] and [`opencity_term`] are penalties and the
/// leaf SUBTRACTS them; this bundle is a BONUS potential and the leaf ADDS it.
///
/// ANTISYMMETRY IS THE DESIGN CONSTRAINT: the search evaluates the leaf from the
/// MOVER's POV and negates on backup, so every sub-rule is assembled as
/// `urg(pl) * j(pl) - urg(other) * j(other)`, which negates exactly under a seat
/// swap. `parts` is built rule-by-rule in the fixed order J1, J2, J5, J6-anchor,
/// J6-road-join, J8 (J6 pushes TWO parts) and `fsum`-reduced — a function of the
/// multiset, so the association-list iteration order inside each rule cannot
/// reach the value.
///
/// `base` is `flat_base_score`'s value (the leaf passes the one it already
/// computed, cast to `f64`). Only J8 reads it, as `|base|`, which is seat-free.
pub fn jrules_term(
    state: &GameState,
    player: usize,
    d: &Decomp,
    cfg: &LeafConfig,
    base: f64,
) -> f64 {
    let mask = cfg.jrules_mask;
    let opp = 1 - player;
    let (city_counts, road_counts, farm_counts, cloister_owned) = jr_counts(state, d);
    // `_k_remaining(state)` — identical to `phase_mult`'s definition of record.
    let k = state.deck_len() + usize::from(state.next_tile.is_some());
    let mut parts: Vec<f64> = Vec::new();
    if mask & JR_J1 != 0 {
        let late = jr_late_frac(k);
        let u_self = jr_urgency(state.meeples[opp]);
        let u_opp = jr_urgency(state.meeples[player]);
        parts.push(
            u_self * jr_j1(d, &city_counts, player, opp, late)
                - u_opp * jr_j1(d, &city_counts, opp, player, late),
        );
    }
    if mask & JR_J2 != 0 {
        let u_self = jr_urgency(state.meeples[opp]);
        let u_opp = jr_urgency(state.meeples[player]);
        parts.push(
            u_self * jr_j2(d, &farm_counts, player, opp, k)
                - u_opp * jr_j2(d, &farm_counts, opp, player, k),
        );
    }
    if mask & JR_J5 != 0 {
        // J5 + J13 are ONE signed term and are already a differential, so they are
        // NOT run through the per-side frame and are NOT urgency-multiplied — the
        // claim edge IS the reserve conditioning J4 would otherwise supply.
        let u = jr_unclaimed_value(state, d, &city_counts, &road_counts, &cloister_owned);
        parts.push(JR_J5_WEIGHT * u * jr_claim_edge(state, player, opp));
    }
    if mask & JR_J6 != 0 {
        let u_self = jr_urgency(state.meeples[opp]);
        let u_opp = jr_urgency(state.meeples[player]);
        parts.push(
            jr_j6_anchor(d, &city_counts, &road_counts, player, opp)
                - jr_j6_anchor(d, &city_counts, &road_counts, opp, player),
        );
        parts.push(
            u_self * jr_j6_road_join(d, &road_counts, player, opp)
                - u_opp * jr_j6_road_join(d, &road_counts, opp, player),
        );
    }
    if mask & JR_J8 != 0 {
        let abs_margin = base.abs();
        let u_self = jr_urgency(state.meeples[opp]);
        let u_opp = jr_urgency(state.meeples[player]);
        parts.push(
            u_self * jr_j8(d, &city_counts, &farm_counts, player, opp, k, abs_margin)
                - u_opp * jr_j8(d, &city_counts, &farm_counts, opp, player, k, abs_margin),
        );
    }
    fsum(&parts)
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
    /// The RAW targeted-denial magnitude `T` (the leaf subtracts `dose * T`);
    /// `0.0` whenever `denial_dose == 0.0` (the term is never computed then).
    pub denial_term: f64,
    /// The SIGNED open-city differential `T` (the leaf subtracts `dose * T`; it may
    /// be negative). `0.0` whenever `opencity_dose == 0.0` (never computed then).
    pub opencity_term: f64,
    /// The SIGNED J-rules differential `T` (the leaf **ADDS** `dose * T` — note the
    /// sign; it may be negative). `0.0` whenever `jrules_dose == 0.0` (never
    /// computed then).
    pub jrules_term: f64,
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

    let base = flat_base_score_farm(state, player, d, cfg.farm_base_off);
    let bonus_self_raw = closure_bonus(state, player, d, cfg, bag_ref)?;
    let bonus_opp_raw = closure_bonus(state, opp, d, cfg, bag_ref)?;
    let bonus_self = soft_capped(bonus_self_raw, cfg.bonus_cap, cfg.soft_cap_slope);
    let bonus_opp = soft_capped(bonus_opp_raw, cfg.opp_bonus_cap, cfg.opp_soft_cap_slope);

    // `score = base + bonus_self - bonus_opp` — left-associative, exactly as written.
    let mut score = base as f64 + bonus_self - bonus_opp;

    // Targeted denial: an UNCAPPED extra subtraction on top of the (capped)
    // opponent anticipation — deliberately NOT routed through `soft_capped` /
    // `opp_bonus_cap` (see `denial_term`). dose == 0.0 (default/champion) takes
    // an early branch — never a subtract of 0.0 — so default traffic is
    // bit-identical, not merely equal. Mirrors `flat_leaf.flat_virtual_score_v2`:
    // applied BEFORE the meeple/curve term, in the same fixed order.
    let mut den_term = 0.0;
    if cfg.denial_dose != 0.0 {
        den_term = denial_term(state, player, d, cfg);
        score -= cfg.denial_dose * den_term;
    }

    // Open-city discipline: a SIGNED, uncapped subtraction applied AFTER denial —
    // two separate gated statements in this fixed order (float addition is
    // non-associative, so a fused expression would break bit-exactness against
    // Python). It ADJUSTS the city terms, never replaces them. dose == 0.0
    // (default/champion) takes an early branch — never a subtract of 0.0 — so
    // default traffic is bit-identical, not merely equal. Mirrors
    // `flat_leaf.flat_virtual_score_v2`.
    let mut oc_term = 0.0;
    if cfg.opencity_dose != 0.0 {
        oc_term = opencity_term(state, player, d, cfg);
        score -= cfg.opencity_dose * oc_term;
    }

    // J-rules on search: a SIGNED, uncapped **ADDITION** (⚠️ note the sign — this
    // bundle is a BONUS potential, not a penalty like denial/open-city), applied
    // AFTER open-city as a third separate gated statement in this fixed order
    // (float addition is non-associative, so a fused expression would break
    // bit-exactness against Python). dose == 0.0 (default/champion) takes an early
    // branch — never an add of 0.0 — so default traffic is bit-identical, not
    // merely equal. Mirrors `flat_leaf.flat_virtual_score_v2`, which passes the
    // `base` it already computed.
    let mut jr_term = 0.0;
    if cfg.jrules_dose != 0.0 {
        jr_term = jrules_term(state, player, d, cfg, base as f64);
        score += cfg.jrules_dose * jr_term;
    }

    let meeple_term = match &cfg.v29_meeple_curve {
        Some(curve) => {
            // Part C: beta == 0.0 (default/champion) takes the UNMODIFIED expression
            // via an early branch — never a multiply by 1.0 — so the default is
            // bit-identical, not merely equal.
            if cfg.v29_phase_beta == 0.0 {
                curve_lookup(curve, state.meeples[player])
                    - curve_lookup(curve, state.meeples[opp])
            } else {
                phase_mult(state, cfg.v29_phase_beta, cfg.v29_phase_norm)
                    * (curve_lookup(curve, state.meeples[player])
                        - curve_lookup(curve, state.meeples[opp]))
            }
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
        denial_term: den_term,
        opencity_term: oc_term,
        jrules_term: jr_term,
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

    /// The scratch path must be BIT-identical to the allocating path, and it
    /// must stay so when the SAME buffers are reused across many different
    /// positions (stale-data is the only way a buffer-reuse refactor can go
    /// wrong, so the scratch is deliberately reused across every ply here).
    #[test]
    fn leaf_scratch_reuse_is_bit_identical_across_a_whole_game() {
        let cfg = LeafConfig::curve125();
        let mut sc = LeafScratch::new();
        let mut checked = 0usize;
        for seed in ["1", "7", "12345678901234567890"] {
            let mut g = Game::from_seed(seed);
            let mut plies = 0;
            while !g.is_terminal() && plies < 260 {
                for player in 0..2 {
                    let want_f = leaf_value_float(&g.state, player, &cfg).unwrap();
                    let want_i = leaf_value(&g.state, player, &cfg).unwrap();
                    let got_f = sc.leaf_value_float(&g.state, player, &cfg).unwrap();
                    let got_i = sc.leaf_value(&g.state, player, &cfg).unwrap();
                    assert_eq!(got_f.to_bits(), want_f.to_bits(),
                               "seed {seed} ply {plies} p{player} float leaf");
                    assert_eq!(got_i, want_i, "seed {seed} ply {plies} p{player} int leaf");
                    checked += 2;
                }
                let legal = g.legal_actions();
                g.advance(legal[legal.len() / 2]).unwrap();
                plies += 1;
            }
        }
        assert!(checked > 1000, "only {checked} comparisons");
    }

    #[test]
    fn decompose_into_reuse_matches_a_fresh_decompose() {
        let mut d = Decomp::default();
        let mut sc = Scratch::default();
        let mut g = Game::from_seed("99");
        for _ in 0..90 {
            let legal = g.legal_actions();
            g.advance(legal[0]).unwrap();
            decompose_into(&g.state, &mut d, &mut sc);
            let fresh = decompose(&g.state);
            assert_eq!(d.placed, fresh.placed);
            assert_eq!(d.city_labels, fresh.city_labels);
            assert_eq!(d.road_labels, fresh.road_labels);
            assert_eq!(d.farm_labels, fresh.farm_labels);
            assert_eq!(d.city_root_open_n, fresh.city_root_open_n);
            assert_eq!(d.road_root_open_n, fresh.road_root_open_n);
            assert_eq!(d.city_root_delta, fresh.city_root_delta);
            assert_eq!(d.farm_root_finished_cities, fresh.farm_root_finished_cities);
        }
    }

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

#[cfg(test)]
mod scratch_bench {
    use super::*;
    use crate::game::Game;
    use std::time::Instant;

    /// `cargo test --release -p carc-core -- --ignored --nocapture scratch_bench`
    #[test]
    #[ignore]
    fn bench_alloc_vs_scratch() {
        let cfg = LeafConfig::curve125();
        let mut g = Game::from_seed("28000000000");
        for _ in 0..60 {
            let legal = g.legal_actions();
            g.advance(legal[legal.len() / 2]).unwrap();
        }
        let n = 20000;
        let t = Instant::now();
        let mut acc = 0.0f64;
        for _ in 0..n {
            acc += leaf_value_float(&g.state, 0, &cfg).unwrap();
        }
        let alloc = t.elapsed().as_secs_f64() / n as f64 * 1e6;
        let mut sc = LeafScratch::new();
        let t = Instant::now();
        for _ in 0..n {
            acc += sc.leaf_value_float(&g.state, 0, &cfg).unwrap();
        }
        let scratch = t.elapsed().as_secs_f64() / n as f64 * 1e6;
        println!("leaf us/call: alloc={alloc:.3} scratch={scratch:.3} \
                  speedup={:.2}x (acc={acc:.1})", alloc / scratch);
    }
}
