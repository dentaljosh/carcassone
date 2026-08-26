//! INVASION-RISK TERM FAMILY — four candidate leaf shapes (A/B/C/D).
//!
//! Spec of record: `measurement/invasion_term_build/SHAPES.md` (the screening
//! prereg quotes it verbatim). Mechanism (`docs/LEVER_INDEX.md`, row
//! "contested-feature / invasion-risk term", + the Stage A census in
//! `measurement/e4_exploit_grading_20260825/`): an invasion is a multi-ply plan
//! whose FIRST move — a 2-tile stub claim next to an opponent feature — the
//! champion leaf DEMOTES, because the merge payoff is several plies away and the
//! vendored full-points-on-tie rule hides the victim's loss, so self-play never
//! priced it. These terms make step one look good at depth 0 (offense) and make
//! one's own big open-edged features look less safe (defense).
//!
//! ## RUST-ONLY, BY DECISION
//!
//! Unlike denial / open-city / J-rules, there is **no `flat_leaf.py` mirror and
//! no Cython mirror** — the owner-approved build is RUST-FIRST (screening cells
//! run `--backend rust`). The Python side carries the CONFIG FIELDS ONLY (so
//! `--cand-leaf-json` and the leaf-hash dialect work) and FAILS LOUD on a nonzero
//! weight. That is the tile-tie pattern with the sides reversed.
//!
//! ## Every weight defaults to 0.0 == the champion leaf, BIT-FOR-BIT
//!
//! Each shape is a SEPARATE gated statement in [`super::leaf_terms_with`]; a zero
//! weight takes an early branch and is never an add/subtract of 0.0, so default
//! traffic is bit-identical, not merely equal.

use crate::compat::fsum;
use crate::engine::{GameState, BOARD_COLS, BOARD_ROWS};
use crate::tiles::{self, Side};

use super::decomp::Decomp;
use super::{city_points, jr_counts, road_points, LeafConfig};

/// `LeafConfig.invasion_stub_max_tiles` default — the draft spec's "<= 2-tile
/// stub claim".
pub const INV_STUB_MAX_TILES: i64 = 2;

/// `(d_row, d_col)` for a cardinal side index — the neighbour a feature edge on
/// that side points at. The delta half of `decomp::opp` (which is private to
/// `decomp`); the opposite-side index is not needed here.
#[inline]
fn side_delta(side_ix: u8) -> (i32, i32) {
    match side_ix {
        0 => (-1, 0), // TOP
        1 => (0, 1),  // RIGHT
        2 => (1, 0),  // BOTTOM
        3 => (0, -1), // LEFT
        other => panic!("cardinal side index expected, got {other}"),
    }
}

/// `true` iff `(r, c)` is ON the 35x35 grid and EMPTY — the grid-bounded open
/// rule `decomp` uses, reproduced exactly (a feature edge pointing off the board
/// is unfinished but NOT open; the D16 walled-variant distortion is part of the
/// measured champion and must not be "fixed" here).
#[inline]
fn is_open_cell(state: &GameState, r: i32, c: i32) -> bool {
    r >= 0 && r < BOARD_ROWS && c >= 0 && c < BOARD_COLS && state.get_tile(r, c).is_none()
}

/// The three terrain families this family prices. Cloisters are excluded: a
/// cloister cannot be joined, merged or invaded (it is a single-tile claim with
/// no edges), so no shape can fire on one.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Kind {
    City,
    Road,
    Farm,
}

/// One claimed-or-claimable component, flattened to what the shapes need.
#[derive(Clone, Copy, Debug)]
struct Comp {
    kind: Kind,
    root: u32,
    /// Weighted meeple counts (big meeple == 2), per player.
    cnt: [i64; 2],
    /// STRICT weighted-majority holder, or `None` (tied / unclaimed — no shape
    /// fires on one: nobody's value is at risk and nothing is there to invade).
    holder: Option<usize>,
    /// The points the leaf's BASE term currently awards the holder — the unit
    /// every shape prices in (`city_points` / `road_points` / `3 * finished
    /// adjacent cities`). NOT the closure-anticipated value.
    value: f64,
    /// Distinct tiles the component spans (the shape-B "stub" / "larger" axis).
    tiles: i64,
    /// Distinct EMPTY board cells the component has a feature edge into.
    open_n: usize,
    /// Feature-edge nodes in the component (shape C's perimeter denominator).
    edges: usize,
}

impl Comp {
    #[inline]
    fn other_can_join(&self, state: &GameState, invader: usize) -> bool {
        // The invader must still have a meeple to commit AND the component must
        // still be growable (>= 1 open board cell). This is the cheap
        // `P_contest` proxy the draft spec names; it is 0/1, never graded.
        self.open_n >= 1 && state.meeples[invader] >= 1
    }
}

#[inline]
fn strict_holder(cnt: [i64; 2]) -> Option<usize> {
    if cnt[0] > cnt[1] {
        Some(0)
    } else if cnt[1] > cnt[0] {
        Some(1)
    } else {
        None
    }
}

// ---------------------------------------------------------------------------
// Farm geometry (`Decomp` keeps none of it — cities/roads have it precomputed)
// ---------------------------------------------------------------------------

/// Sorted, deduped `(farm_root, cell)` pairs — the distinct empty board cells
/// each field has a farmer-edge into. Same grid-bounded rule as `decomp`'s
/// city/road open counting.
fn farm_open_pairs(state: &GameState, d: &Decomp) -> Vec<(u32, i32)> {
    let mut out: Vec<(u32, i32)> = Vec::new();
    for nid in 0..d.farm_node_rc.len() {
        let (r, c) = d.farm_node_rc[nid];
        let tid = match state.get_tile(r, c) {
            Some(t) => t,
            None => continue,
        };
        let root = d.farm_labels[nid];
        let conns = &tiles::tile(tid).farms[d.farm_node_slot[nid] as usize].tile_connections;
        for &fs in conns {
            let (dr, dc) = match fs.get_side() {
                Side::Top => (-1, 0),
                Side::Right => (0, 1),
                Side::Bottom => (1, 0),
                Side::Left => (0, -1),
                other => panic!("farmer side on a non-cardinal edge {other:?}"),
            };
            let (nr, nc) = (r + dr, c + dc);
            if is_open_cell(state, nr, nc) {
                out.push((root, nr * BOARD_COLS + nc));
            }
        }
    }
    out.sort_unstable();
    out.dedup();
    out
}

/// Sorted, deduped `(city_root, cell)` pairs.
fn city_open_pairs(state: &GameState, d: &Decomp) -> Vec<(u32, i32)> {
    let mut out: Vec<(u32, i32)> = Vec::new();
    for nid in 0..d.city_nodes.len() {
        let (r, c, ix) = d.city_nodes[nid];
        let (dr, dc) = side_delta(ix);
        let (nr, nc) = (r + dr, c + dc);
        if is_open_cell(state, nr, nc) {
            out.push((d.city_labels[nid], nr * BOARD_COLS + nc));
        }
    }
    out.sort_unstable();
    out.dedup();
    out
}

/// Sorted, deduped `(road_root, cell)` pairs.
fn road_open_pairs(state: &GameState, d: &Decomp) -> Vec<(u32, i32)> {
    let mut out: Vec<(u32, i32)> = Vec::new();
    for nid in 0..d.road_nodes.len() {
        let (r, c, ix) = d.road_nodes[nid];
        let (dr, dc) = side_delta(ix);
        let (nr, nc) = (r + dr, c + dc);
        if is_open_cell(state, nr, nc) {
            out.push((d.road_labels[nid], nr * BOARD_COLS + nc));
        }
    }
    out.sort_unstable();
    out.dedup();
    out
}

#[inline]
fn open_n_of(pairs: &[(u32, i32)], root: u32) -> usize {
    pairs.iter().filter(|p| p.0 == root).count()
}

/// Distinct tiles + FARMER-EDGE count per farm root.
///
/// ⚠️ The edge count is the number of `tile_connections` across the component's
/// `FarmerConnection` nodes, NOT the node count: one field node can carry up to
/// four farmer sides, so a node count would be SMALLER than the distinct-open-cell
/// count and shape C's fraction could exceed 1. Counting connections restores the
/// city/road invariant `open_n <= edges` (distinct open cells can only merge
/// several connections into one, never split one into several).
fn farm_tiles_and_edges(state: &GameState, d: &Decomp, root: u32) -> (i64, usize) {
    let mut cells: Vec<i32> = Vec::new();
    let mut edges = 0usize;
    for nid in 0..d.farm_node_rc.len() {
        if d.farm_labels[nid] != root {
            continue;
        }
        let (r, c) = d.farm_node_rc[nid];
        if let Some(tid) = state.get_tile(r, c) {
            edges += tiles::tile(tid).farms[d.farm_node_slot[nid] as usize]
                .tile_connections
                .len();
        }
        cells.push(r * BOARD_COLS + c);
    }
    cells.sort_unstable();
    cells.dedup();
    (cells.len() as i64, edges)
}

#[inline]
fn node_count(labels: &[u32], root: u32) -> usize {
    labels.iter().filter(|&&l| l == root).count()
}

// ---------------------------------------------------------------------------
// The component scan the four shapes share
// ---------------------------------------------------------------------------

/// Every CLAIMED component (a meeple of either player on it), flattened.
///
/// Unclaimed components are skipped by construction: `jr_counts` only ever
/// records a root a meeple sits on, and every shape's predicate requires a
/// strict-majority holder. Cloisters are out of scope (see [`Kind`]).
fn scan(state: &GameState, d: &Decomp) -> (Vec<Comp>, OpenPairs) {
    let (city_counts, road_counts, farm_counts, _cloister) = jr_counts(state, d);
    let pairs = OpenPairs {
        city: city_open_pairs(state, d),
        road: road_open_pairs(state, d),
        farm: farm_open_pairs(state, d),
    };
    let mut out: Vec<Comp> = Vec::new();

    for &(root, cnt) in &city_counts {
        let r = root as usize;
        out.push(Comp {
            kind: Kind::City,
            root,
            cnt,
            holder: strict_holder(cnt),
            value: city_points(d, root) as f64,
            tiles: d.city_root_tiles[r],
            open_n: open_n_of(&pairs.city, root),
            edges: node_count(&d.city_labels, root),
        });
    }
    for &(root, cnt) in &road_counts {
        let r = root as usize;
        out.push(Comp {
            kind: Kind::Road,
            root,
            cnt,
            holder: strict_holder(cnt),
            value: road_points(d, root) as f64,
            tiles: d.road_root_tiles[r],
            open_n: open_n_of(&pairs.road, root),
            edges: node_count(&d.road_labels, root),
        });
    }
    for &(root, cnt) in &farm_counts {
        let (tiles_n, edges) = farm_tiles_and_edges(state, d, root);
        out.push(Comp {
            kind: Kind::Farm,
            root,
            cnt,
            holder: strict_holder(cnt),
            value: 3.0 * d.farm_root_finished_cities[root as usize] as f64,
            tiles: tiles_n,
            open_n: open_n_of(&pairs.farm, root),
            edges,
        });
    }
    (out, pairs)
}

struct OpenPairs {
    city: Vec<(u32, i32)>,
    road: Vec<(u32, i32)>,
    farm: Vec<(u32, i32)>,
}

impl OpenPairs {
    #[inline]
    fn of(&self, kind: Kind) -> &[(u32, i32)] {
        match kind {
            Kind::City => &self.city,
            Kind::Road => &self.road,
            Kind::Farm => &self.farm,
        }
    }
}

// ---------------------------------------------------------------------------
// SHAPE A — contested-value transfer ("the tie is not free")
// ---------------------------------------------------------------------------

/// The SIGNED contested-transfer differential `T_A` from `player`'s POV; the leaf
/// **ADDS** `cfg.invasion_beta * T_A`.
///
/// ```text
/// T_A = Σ  V(f)   over f held by OPP    that PLAYER can still join
///     − Σ  V(f)   over f held by PLAYER that OPP    can still join
/// ```
/// over every city / road / farm component with a STRICT weighted-meeple
/// majority holder (big meeple = 2; tied and unclaimed never fire). `V(f)` is
/// the value the BASE term already awards the holder. "can still join" is the
/// draft's cheap `P_contest` proxy: the invader holds >= 1 meeple in reserve AND
/// the component still has >= 1 open board cell — a 0/1 gate, never graded.
///
/// Why this is the right sign. The vendored rule is FULL POINTS ON TIE: a
/// successful invasion pays the invader `V` and costs the victim NOTHING in raw
/// points, so in the DIFFERENTIAL leaf the victim loses exactly `V`. The base
/// term prices a majority-held component as a clean `±V`; this term walks that
/// back toward 0 by `beta * V` for every component the other side can still
/// reach. Offense and defense in one antisymmetric weight.
///
/// ⚠️ DEVIATION FROM THE DRAFT (deliberate, exactly a factor of 2). The draft
/// writes the shape as TWO edits — `v_feature *= (1 - beta*P)` on the holder AND
/// `+= beta*P*v` credited to the invader. In a two-player DIFFERENTIAL leaf both
/// edits move the same difference the same way, so the draft's form is
/// identically `2 * T_A` for every position — a constant rescaling absorbed into
/// the swept weight. Implemented as the single signed transfer so that
/// `beta = 1.0` has the exact meaning "a contestable component is worth nothing
/// in the differential".
pub fn shape_a_term(state: &GameState, player: usize, d: &Decomp, _cfg: &LeafConfig) -> f64 {
    let opp = 1 - player;
    let (comps, _pairs) = scan(state, d);
    let mut contribs: Vec<f64> = Vec::new();
    for c in &comps {
        match c.holder {
            Some(h) if h == opp => {
                if c.other_can_join(state, player) {
                    contribs.push(c.value);
                }
            }
            Some(h) if h == player => {
                if c.other_can_join(state, opp) {
                    contribs.push(-c.value);
                }
            }
            _ => {}
        }
    }
    fsum(&contribs)
}

// ---------------------------------------------------------------------------
// SHAPE B — stub-claim merge-potential bonus (OFFENSE ONLY)
// ---------------------------------------------------------------------------

/// The NON-NEGATIVE stub-merge potential `T_B` from `player`'s POV; the leaf
/// **ADDS** `cfg.invasion_alpha * T_B`.
///
/// For every ORDERED pair `(S, L)` of components of the SAME terrain family with
/// * `S` held by PLAYER at a strict weighted majority, spanning
///   `tiles(S) <= cfg.invasion_stub_max_tiles` distinct tiles (the "stub"),
/// * `L` held by OPP at a strict weighted majority, `L != S`,
///   `tiles(L) > tiles(S)` (the "larger opponent feature"),
/// * `S` and `L` at MERGE DISTANCE 1 — they share at least one open board cell,
///   i.e. one tile placed there could connect them,
///
/// the pair contributes `min(V(L), cfg.invasion_alpha_cap)`
/// (`invasion_alpha_cap == 0.0` means UNCAPPED — the cap branch is never taken).
/// `T_B = fsum` of those contributions.
///
/// This is the term that directly promotes the demoted FIRST move of the
/// invasion plan: after the stub claim, the leaf already sees the merge payoff
/// at depth 0, so ordinary search carries the rest of the plan.
///
/// ⚠️ NOT ANTISYMMETRIC — by design. Shape B is offense-only: `T_B >= 0` always,
/// and `T_B(player) != -T_B(opp)`. Both sides of a self-play game get their own
/// offense when each evaluates from its own POV, but a single leaf value is NOT
/// seat-invariant under this term. That is the shape as specified; the symmetric
/// counterpart of the same mechanism is shape A.
pub fn shape_b_term(state: &GameState, player: usize, d: &Decomp, cfg: &LeafConfig) -> f64 {
    let opp = 1 - player;
    let (comps, pairs) = scan(state, d);
    let stub_max = cfg.invasion_stub_max_tiles;
    let mut contribs: Vec<f64> = Vec::new();
    for s in &comps {
        if s.holder != Some(player) || s.tiles > stub_max || s.open_n == 0 {
            continue;
        }
        for l in &comps {
            if l.kind != s.kind || l.root == s.root {
                continue;
            }
            if l.holder != Some(opp) || l.tiles <= s.tiles || l.open_n == 0 {
                continue;
            }
            if !share_open_cell(pairs.of(s.kind), s.root, l.root) {
                continue;
            }
            let mut v = l.value;
            // 0.0 == UNCAPPED: an explicit compare, so the uncapped route never
            // touches the cap arithmetic.
            if cfg.invasion_alpha_cap > 0.0 && v > cfg.invasion_alpha_cap {
                v = cfg.invasion_alpha_cap;
            }
            contribs.push(v);
        }
    }
    fsum(&contribs)
}

/// Merge distance 1: do these two components of one terrain family have a
/// feature edge into the SAME empty board cell?
fn share_open_cell(pairs: &[(u32, i32)], a: u32, b: u32) -> bool {
    for &(ra, cell) in pairs.iter() {
        if ra != a {
            continue;
        }
        if pairs.iter().any(|&(rb, cb)| rb == b && cb == cell) {
            return true;
        }
    }
    false
}

// ---------------------------------------------------------------------------
// SHAPE C — dumping-ground discount (DEFENSE ONLY)
// ---------------------------------------------------------------------------

/// The NON-NEGATIVE unguarded-perimeter penalty `T_C` from `player`'s POV; the
/// leaf **SUBTRACTS** `cfg.invasion_gamma * T_C` (⚠️ note the sign — A, B and D
/// are added; this one is a penalty, like denial and open-city).
///
/// For every component held by PLAYER at a strict weighted majority:
/// ```text
/// frac    = unguarded_open_edges / total_feature_edges          in [0, 1]
/// contrib = frac * V(f)
/// ```
/// `unguarded_open_edges` is the component's distinct open board cells when the
/// OPPONENT still holds >= 1 meeple in reserve, and `0` when they do not (a
/// perimeter nobody can walk through is not a liability). `total_feature_edges`
/// is the component's feature-edge node count (city/road: tile sides; farm:
/// farmer connections), always >= 1 for a claimed component, and always >= the
/// distinct open-cell count, so `frac <= 1`.
///
/// This is the linear form of the draft's `v *= (1 - gamma * frac)`: subtracting
/// `gamma * frac * V` is that multiplication, written as an additive penalty so
/// the term composes with the existing city terms instead of replacing them, and
/// so no clamp (a hidden second knob) is needed. Sweeps stay in `gamma ∈ [0, 1]`,
/// where the two forms are identical.
///
/// ⚠️ NOT ANTISYMMETRIC — by design, and the screening read rule depends on it:
/// shape C is purely defensive, so it can only show up against an opponent that
/// actually invades. An H2H-vs-champion NULL for C is EXPECTED and is NOT
/// disconfirming (the champion does not invade); C is screened against a shape-B
/// agent or the E4 owner, never against the base champion.
pub fn shape_c_term(state: &GameState, player: usize, d: &Decomp, _cfg: &LeafConfig) -> f64 {
    let opp = 1 - player;
    let (comps, _pairs) = scan(state, d);
    let opp_can_walk = state.meeples[opp] >= 1;
    let mut contribs: Vec<f64> = Vec::new();
    for c in &comps {
        if c.holder != Some(player) {
            continue;
        }
        if !opp_can_walk || c.open_n == 0 || c.edges == 0 {
            continue;
        }
        let frac = c.open_n as f64 / c.edges as f64;
        contribs.push(frac * c.value);
    }
    fsum(&contribs)
}

// ---------------------------------------------------------------------------
// SHAPE D — farm-specific contested differential (the H4 conjunction)
// ---------------------------------------------------------------------------

/// The SIGNED contested-FARM differential `T_D` from `player`'s POV; the leaf
/// **ADDS** `cfg.invasion_delta_farm * T_D`.
///
/// Exactly [`shape_a_term`] restricted to FIELDS:
/// ```text
/// T_D = Σ V(f) over farms held by OPP    that PLAYER can still join
///     − Σ V(f) over farms held by PLAYER that OPP    can still join
/// ```
/// with `V(f) = 3 * (finished cities the field touches)` — the farm award the
/// base term makes — and the same 0/1 `can still join` proxy (invader has a
/// meeple in reserve AND the field still has an open board cell). At
/// `delta_farm = 1.0` a contestable field contributes NOTHING to the
/// differential, which is the draft's "price the farm as swing
/// `my_share - opp_potential_share`, not gross".
///
/// This is the closest shape to the MEASURED E4 mechanism (Stage A: late
/// decisive farm captures; the champion farm-zeroed in 9/50 games).
///
/// ⚠️ COLLINEAR WITH SHAPE A ON FARMS — by construction, and the prereg must say
/// so: `T_A = T_A|cities+roads + T_D`, exactly. Running both weights is not two
/// independent effects; it is the parameterisation "`beta` on everything,
/// `beta + delta_farm` on fields". Screening A against D is a SCOPE contrast, not
/// a shape contrast.
pub fn shape_d_term(state: &GameState, player: usize, d: &Decomp, _cfg: &LeafConfig) -> f64 {
    let opp = 1 - player;
    let (comps, _pairs) = scan(state, d);
    let mut contribs: Vec<f64> = Vec::new();
    for c in &comps {
        if c.kind != Kind::Farm {
            continue;
        }
        match c.holder {
            Some(h) if h == opp => {
                if c.other_can_join(state, player) {
                    contribs.push(c.value);
                }
            }
            Some(h) if h == player => {
                if c.other_can_join(state, opp) {
                    contribs.push(-c.value);
                }
            }
            _ => {}
        }
    }
    fsum(&contribs)
}

// ---------------------------------------------------------------------------
// Diagnostics — not on any leaf path
// ---------------------------------------------------------------------------

/// A per-component dump for the pytest fixtures and for hand-auditing a position
/// (`kind`, root, counts, holder, value, tiles, open_n, edges). Never called by
/// [`super::leaf_terms_with`].
pub fn invasion_scan_debug(state: &GameState, d: &Decomp) -> Vec<InvasionCompDebug> {
    let (comps, _pairs) = scan(state, d);
    comps
        .iter()
        .map(|c| InvasionCompDebug {
            kind: match c.kind {
                Kind::City => "city",
                Kind::Road => "road",
                Kind::Farm => "farm",
            },
            root: c.root,
            cnt0: c.cnt[0],
            cnt1: c.cnt[1],
            holder: c.holder.map(|h| h as i64).unwrap_or(-1),
            value: c.value,
            tiles: c.tiles,
            open_n: c.open_n as i64,
            edges: c.edges as i64,
        })
        .collect()
}

/// One row of [`invasion_scan_debug`].
#[derive(Clone, Debug)]
pub struct InvasionCompDebug {
    pub kind: &'static str,
    pub root: u32,
    pub cnt0: i64,
    pub cnt1: i64,
    /// `-1` when tied (no strict majority holder).
    pub holder: i64,
    pub value: f64,
    pub tiles: i64,
    pub open_n: i64,
    pub edges: i64,
}

/// `true` iff EVERY invasion weight is 0.0 — i.e. the leaf takes the four early
/// branches and is bit-identical to the champion. The capability probes and the
/// Python fail-closed guard mirror this predicate.
#[inline]
pub fn invasion_off(cfg: &LeafConfig) -> bool {
    cfg.invasion_beta == 0.0
        && cfg.invasion_alpha == 0.0
        && cfg.invasion_gamma == 0.0
        && cfg.invasion_delta_farm == 0.0
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::Game;
    use crate::leaf::leaf_value_float;

    /// Every weight 0.0 — but with shape B's two INERT knobs deliberately moved
    /// off their defaults, so the gate proves the family is gated on the WEIGHTS
    /// and on nothing else.
    fn off_but_moved() -> LeafConfig {
        LeafConfig {
            invasion_alpha_cap: 3.0,
            invasion_stub_max_tiles: 5,
            ..LeafConfig::curve125()
        }
    }

    /// Walk a game, yielding every state.
    fn walk(seed: &str, max_plies: usize, mut f: impl FnMut(&Game)) {
        let mut g = Game::from_seed(seed);
        let mut plies = 0;
        while !g.is_terminal() && plies < max_plies {
            f(&g);
            let legal = g.legal_actions();
            g.advance(legal[legal.len() / 3]).unwrap();
            plies += 1;
        }
    }

    const SEEDS: [&str; 5] = ["1", "7", "99", "424242", "12345678901234567890"];

    // ---------------------------------------------------------------- gate 1

    /// GATE 1 — WEIGHT-0 IDENTITY. Bit-identical (not merely equal) leaf values
    /// with the whole family off, INCLUDING with the inert shape-B knobs moved.
    #[test]
    fn weight_zero_family_is_bit_identical_to_the_champion() {
        let champ = LeafConfig::curve125();
        let off = off_but_moved();
        let mut checked = 0usize;
        for seed in SEEDS {
            walk(seed, 200, |g| {
                for player in 0..2 {
                    let a = leaf_value_float(&g.state, player, &champ).unwrap();
                    let b = leaf_value_float(&g.state, player, &off).unwrap();
                    assert_eq!(a.to_bits(), b.to_bits(), "seed {seed} pov {player}");
                    checked += 1;
                }
            });
        }
        assert!(checked > 1000, "only {checked} comparisons");
        assert!(invasion_off(&off));
        assert!(!invasion_off(&LeafConfig {
            invasion_beta: 0.25,
            ..LeafConfig::curve125()
        }));
    }

    // ------------------------------------------------- open-cell re-derivation

    /// The module re-derives open cells from `state` (decomp keeps the counts but
    /// not the cells). That re-derivation must reproduce `decomp`'s grid-bounded
    /// rule EXACTLY, or every shape prices a different board than the leaf does.
    #[test]
    fn open_cell_rederivation_matches_decomp_open_n() {
        for seed in SEEDS {
            walk(seed, 160, |g| {
                let d = crate::leaf::decompose(&g.state);
                let cp = city_open_pairs(&g.state, &d);
                for root in 0..d.city_labels.len() as u32 {
                    if d.city_labels[root as usize] != root {
                        continue; // not a component root
                    }
                    assert_eq!(
                        open_n_of(&cp, root),
                        d.city_root_open_n[root as usize],
                        "seed {seed} city root {root}"
                    );
                }
                let rp = road_open_pairs(&g.state, &d);
                for root in 0..d.road_labels.len() as u32 {
                    if d.road_labels[root as usize] != root {
                        continue;
                    }
                    assert_eq!(
                        open_n_of(&rp, root),
                        d.road_root_open_n[root as usize],
                        "seed {seed} road root {root}"
                    );
                }
            });
        }
    }

    // ---------------------------------------------------------------- shape A

    /// Shape A is ANTISYMMETRIC: `T_A(p) == -T_A(1-p)` at every position — what
    /// makes it usable as a plain signed leaf term on both seats.
    #[test]
    fn shape_a_is_antisymmetric() {
        let cfg = LeafConfig::curve125();
        let mut nonzero = 0usize;
        for seed in SEEDS {
            walk(seed, 200, |g| {
                let d = crate::leaf::decompose(&g.state);
                let a0 = shape_a_term(&g.state, 0, &d, &cfg);
                let a1 = shape_a_term(&g.state, 1, &d, &cfg);
                assert_eq!(a0, -a1, "seed {seed}");
                if a0 != 0.0 {
                    nonzero += 1;
                }
            });
        }
        assert!(nonzero > 50, "shape A never fired ({nonzero})");
    }

    /// Shape A is exactly the signed contestable-value difference over the scan.
    #[test]
    fn shape_a_is_the_signed_contestable_value_difference() {
        let cfg = LeafConfig::curve125();
        for seed in SEEDS {
            walk(seed, 200, |g| {
                let d = crate::leaf::decompose(&g.state);
                let (comps, _p) = scan(&g.state, &d);
                for player in 0..2 {
                    let opp = 1 - player;
                    let mut want = 0.0f64;
                    for c in &comps {
                        if c.holder == Some(opp) && c.other_can_join(&g.state, player) {
                            want += c.value;
                        } else if c.holder == Some(player) && c.other_can_join(&g.state, opp) {
                            want -= c.value;
                        }
                    }
                    let got = shape_a_term(&g.state, player, &d, &cfg);
                    assert!((got - want).abs() < 1e-9, "seed {seed} pov {player}");
                }
            });
        }
    }

    /// A side with NO meeple in reserve cannot invade — the reserve gate is
    /// load-bearing, not decoration.
    #[test]
    fn shape_a_needs_a_meeple_in_reserve() {
        let cfg = LeafConfig::curve125();
        let mut saw_change = 0usize;
        for seed in SEEDS {
            walk(seed, 200, |g| {
                let d = crate::leaf::decompose(&g.state);
                let with = shape_a_term(&g.state, 0, &d, &cfg);
                let mut s = g.state.clone();
                s.meeples = [0, 0];
                assert_eq!(shape_a_term(&s, 0, &d, &cfg), 0.0);
                if with != 0.0 {
                    saw_change += 1;
                }
            });
        }
        assert!(saw_change > 50, "reserve gate never observed ({saw_change})");
    }

    // ---------------------------------------------------------------- shape B

    /// Shape B is OFFENSE-ONLY: `T_B >= 0` everywhere, so a nonzero `alpha` never
    /// lowers the leaf.
    #[test]
    fn shape_b_is_non_negative_and_never_lowers_the_leaf() {
        let base = LeafConfig::curve125();
        let on = LeafConfig {
            invasion_alpha: 0.5,
            ..LeafConfig::curve125()
        };
        for seed in SEEDS {
            walk(seed, 200, |g| {
                let d = crate::leaf::decompose(&g.state);
                for player in 0..2 {
                    let t = shape_b_term(&g.state, player, &d, &on);
                    assert!(t >= 0.0, "seed {seed} T_B {t}");
                    let lo = leaf_value_float(&g.state, player, &base).unwrap();
                    let hi = leaf_value_float(&g.state, player, &on).unwrap();
                    assert!(hi >= lo, "seed {seed} pov {player}: {hi} < {lo}");
                }
            });
        }
    }

    /// `alpha_cap`: 0.0 is uncapped, a positive cap can only shrink `T_B`, and a
    /// cap of 1.0 degenerates the term to a COUNT of qualifying pairs.
    #[test]
    fn shape_b_cap_only_shrinks_and_degenerates_to_a_count() {
        let uncapped = LeafConfig {
            invasion_alpha: 1.0,
            invasion_alpha_cap: 0.0,
            ..LeafConfig::curve125()
        };
        let capped1 = LeafConfig {
            invasion_alpha_cap: 1.0,
            ..uncapped.clone()
        };
        let mut fired = 0usize;
        for seed in SEEDS {
            walk(seed, 200, |g| {
                let d = crate::leaf::decompose(&g.state);
                for player in 0..2 {
                    let u = shape_b_term(&g.state, player, &d, &uncapped);
                    let c = shape_b_term(&g.state, player, &d, &capped1);
                    assert!(c <= u + 1e-12, "seed {seed}: cap raised T_B ({c} > {u})");
                    assert_eq!(c, c.round(), "cap 1.0 must yield an integer count");
                    if u > 0.0 {
                        fired += 1;
                    }
                }
            });
        }
        assert!(fired > 5, "shape B never fired in the corpus ({fired})");
    }

    /// A WIDER stub threshold can only admit more pairs, never fewer.
    #[test]
    fn shape_b_stub_threshold_is_monotone() {
        let narrow = LeafConfig {
            invasion_alpha: 1.0,
            invasion_stub_max_tiles: 1,
            ..LeafConfig::curve125()
        };
        let wide = LeafConfig {
            invasion_stub_max_tiles: 6,
            ..narrow.clone()
        };
        for seed in SEEDS {
            walk(seed, 200, |g| {
                let d = crate::leaf::decompose(&g.state);
                for player in 0..2 {
                    let n = shape_b_term(&g.state, player, &d, &narrow);
                    let w = shape_b_term(&g.state, player, &d, &wide);
                    assert!(w >= n - 1e-12, "seed {seed}: widening lost value");
                }
            });
        }
    }

    // ---------------------------------------------------------------- shape C

    /// GATE 2 (defence half) — shape C PENALIZES the undefended-monster side:
    /// `T_C >= 0`, a nonzero `gamma` can only LOWER the leaf, and it must actually
    /// lower it somewhere (a term that never fires is not a term).
    #[test]
    fn shape_c_penalizes_the_open_perimeter_holder() {
        let base = LeafConfig::curve125();
        let on = LeafConfig {
            invasion_gamma: 0.5,
            ..LeafConfig::curve125()
        };
        let mut strictly_lower = 0usize;
        for seed in SEEDS {
            walk(seed, 200, |g| {
                let d = crate::leaf::decompose(&g.state);
                for player in 0..2 {
                    let t = shape_c_term(&g.state, player, &d, &on);
                    assert!(t >= 0.0, "seed {seed} T_C {t}");
                    let lo = leaf_value_float(&g.state, player, &base).unwrap();
                    let hi = leaf_value_float(&g.state, player, &on).unwrap();
                    assert!(hi <= lo, "seed {seed} pov {player}: {hi} > {lo}");
                    if hi < lo {
                        strictly_lower += 1;
                    }
                }
            });
        }
        assert!(
            strictly_lower > 100,
            "shape C never bit ({strictly_lower} positions)"
        );
    }

    /// The C fraction is a genuine fraction: `open_n <= edges` for every claimed
    /// component, so `frac ∈ [0, 1]`.
    #[test]
    fn shape_c_fraction_is_bounded_by_one() {
        for seed in SEEDS {
            walk(seed, 200, |g| {
                let d = crate::leaf::decompose(&g.state);
                let (comps, _p) = scan(&g.state, &d);
                for c in &comps {
                    assert!(
                        c.open_n <= c.edges,
                        "seed {seed} {:?} root {}: open_n {} > edges {}",
                        c.kind,
                        c.root,
                        c.open_n,
                        c.edges
                    );
                }
            });
        }
    }

    // ---------------------------------------------------------------- shape D

    /// THE DOCUMENTED COLLINEARITY: `T_A == (cities+roads part) + T_D`, exactly.
    /// The prereg quotes this; this test pins it.
    #[test]
    fn shape_d_is_exactly_the_farm_restriction_of_shape_a() {
        let cfg = LeafConfig::curve125();
        let mut farm_nonzero = 0usize;
        for seed in SEEDS {
            walk(seed, 220, |g| {
                let d = crate::leaf::decompose(&g.state);
                let (comps, _p) = scan(&g.state, &d);
                for player in 0..2 {
                    let opp = 1 - player;
                    let mut non_farm = 0.0f64;
                    for c in &comps {
                        if c.kind == Kind::Farm {
                            continue;
                        }
                        if c.holder == Some(opp) && c.other_can_join(&g.state, player) {
                            non_farm += c.value;
                        } else if c.holder == Some(player) && c.other_can_join(&g.state, opp) {
                            non_farm -= c.value;
                        }
                    }
                    let a = shape_a_term(&g.state, player, &d, &cfg);
                    let dd = shape_d_term(&g.state, player, &d, &cfg);
                    assert!((a - (non_farm + dd)).abs() < 1e-9, "seed {seed} pov {player}");
                    if dd != 0.0 {
                        farm_nonzero += 1;
                    }
                }
            });
        }
        assert!(farm_nonzero > 20, "shape D never fired ({farm_nonzero})");
    }

    /// Shape D is antisymmetric, like shape A.
    #[test]
    fn shape_d_is_antisymmetric() {
        let cfg = LeafConfig::curve125();
        for seed in SEEDS {
            walk(seed, 220, |g| {
                let d = crate::leaf::decompose(&g.state);
                assert_eq!(
                    shape_d_term(&g.state, 0, &d, &cfg),
                    -shape_d_term(&g.state, 1, &d, &cfg),
                    "seed {seed}"
                );
            });
        }
    }

    // ------------------------------------------------------------ composition

    /// Each weight moves the leaf by EXACTLY its own signed contribution — the
    /// property every ablation depends on (and the one a fused expression would
    /// silently break). Also pins the SIGN of each shape.
    #[test]
    fn each_weight_moves_the_leaf_by_exactly_its_term() {
        let base = LeafConfig::curve125();
        for seed in SEEDS {
            walk(seed, 160, |g| {
                let d = crate::leaf::decompose(&g.state);
                for player in 0..2 {
                    let b0 = leaf_value_float(&g.state, player, &base).unwrap();
                    let a_cfg = LeafConfig { invasion_beta: 0.5, ..base.clone() };
                    let b_cfg = LeafConfig { invasion_alpha: 0.5, ..base.clone() };
                    let c_cfg = LeafConfig { invasion_gamma: 0.5, ..base.clone() };
                    let d_cfg = LeafConfig { invasion_delta_farm: 0.5, ..base.clone() };
                    for (cfg, want) in [
                        (&a_cfg, 0.5 * shape_a_term(&g.state, player, &d, &a_cfg)),
                        (&b_cfg, 0.5 * shape_b_term(&g.state, player, &d, &b_cfg)),
                        (&c_cfg, -0.5 * shape_c_term(&g.state, player, &d, &c_cfg)),
                        (&d_cfg, 0.5 * shape_d_term(&g.state, player, &d, &d_cfg)),
                    ] {
                        let got = leaf_value_float(&g.state, player, cfg).unwrap() - b0;
                        assert!(
                            (got - want).abs() < 1e-9,
                            "seed {seed} pov {player}: moved {got}, term says {want}"
                        );
                    }
                }
            });
        }
    }
}
