//! `scripts/level2/endgame_solver.py`, `mode="marginalized"` — the exact
//! endgame the fair champion latches into at `k_remaining <= exact_max_k`.
//!
//! Expectiminimax with an EXACT-value transposition table and **no alpha-beta**
//! (chance nodes have no minimax cutoff, so pruning is clairvoyant-only and the
//! fair agent therefore never uses it).  Leaf value = the REAL final score
//! differential `flat_base_score(state, 0)`; P0 maximizes, P1 minimizes.
//!
//! Ported for the phone (the Python solver stays the ORACLE — every answer is
//! gated against it by `scripts/rustport/reconcile_fair.py`).
//!
//! ## The five details that are easy to get wrong
//!
//! 1. **`_tick` is charged per non-terminal TT-MISS `_value` call only.**  The
//!    root position itself is never ticked (`solve` descends into each root
//!    child directly), terminals are not ticked, TT hits are not ticked, and
//!    `_chance` is not ticked.  Node counts are part of the gate.
//! 2. **The TT is shared across root actions** and root actions are visited in
//!    ASCENDING order, so the node count depends on that order.
//! 3. **The chance node's "drop one instance" drops the whole TYPE.**  Python
//!    writes `remaining = [t for t in bag if t is not rep]`, and the vendored
//!    engine hands out *canonical shared* `Tile` objects — every copy of
//!    `bent_road` in a deck is literally one object, and `copy.deepcopy`
//!    memoizes by `id`, so identity ≡ description.  At the deployed
//!    `exact_max_k = 2` the post-draw bag never exceeds one tile so the two
//!    readings coincide; above it they do not.  Ported AS WRITTEN — see
//!    [`ChanceDrop`], which exists so the divergence is nameable rather than
//!    silently baked in.
//! 4. **The expectation accumulates in bag-group INSERTION order** (`groups`
//!    is a `dict` keyed by description, first appearance wins) — float addition
//!    is not associative, so the order is load-bearing.
//! 5. **The marginalized TT key sorts the deck descriptions** (the spec's V5
//!    no-leak key: states differing only in unrevealed order collide).

use std::collections::HashMap;

use crate::game::Game;
use crate::sha256::sha256_bytes;
use crate::tiles;

/// `_TIE` — optimal-set membership tolerance in the marginalized mode.
pub const TIE: f64 = 1e-6;

/// E1: tolerance on the WIN component of the lexicographic `(w, m)` value —
/// `w` is an expectation of `{0, 0.5, 1}` over rational bag probabilities, so
/// two mathematically equal `w`'s can differ by float-order noise; without a
/// tolerance the margin tiebreak would be decided by that noise instead of by
/// margin.  1e-9 is far above accumulated f64 noise at endgame tree sizes and
/// far below the smallest genuine outcome-probability gap the deployed bag
/// sizes can produce.
pub const WIN_TIE: f64 = 1e-9;

/// E1 — the exact solver's OBJECTIVE (`measurement/e1_winobj_20260814/DESIGN.md` §1).
///
/// `Margin` (default, the incumbent): value = `E[final score differential]`,
/// maximized/minimized at every depth — the ONLY objective that ever shipped;
/// with `Objective::Margin` the solve is the untouched pre-E1 code path,
/// bit-identical.
///
/// `Win`: node value is the pair `(w, m)` — `w = E[outcome]` with
/// `outcome = 1 / 0.5 / 0` for win / draw / loss (P0 POV, draw = half a win:
/// the lattice the eval harness scores W/D/L on), `m = E[margin]` *under the
/// win-first policy*.  Chance nodes take component-wise expectations; decision
/// nodes compare **lexicographically** — `w` first (within [`WIN_TIE`]), then
/// `m`.  Win-first-margin-tiebreak is deliberately the SMALLEST semantic
/// change that flips the objective: the `w` backup alone is standard
/// expectiminimax on outcome (so the solver exactly maximizes
/// `P(win) + 0.5*P(draw)`), while margin keeps breaking ties so play stays
/// deterministic and outcome-equal lines are ordered exactly as the incumbent
/// orders them.  A pure `{+1, 0, -1}` objective would throw that tiebreak
/// away.
///
/// ⚠️ At the deployed `exact_max_k = 2` the two objectives PROVABLY coincide
/// (every chance bag is a singleton — see detail #3 above — so the solve is a
/// deterministic minimax and `outcome` is a monotone transform of the
/// deterministic margin; DESIGN §2 proposition).  Divergence requires a chance
/// bag of ≥ 2, i.e. a K ≥ 3 latch.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Objective {
    Margin,
    Win,
}

impl Objective {
    pub fn parse(s: &str) -> Result<Self, String> {
        match s {
            "margin" => Ok(Objective::Margin),
            "win" => Ok(Objective::Win),
            other => Err(format!("objective must be 'margin' | 'win'; got {other:?}")),
        }
    }

    pub fn value(&self) -> &'static str {
        match self {
            Objective::Margin => "margin",
            Objective::Win => "win",
        }
    }
}

/// `outcome(m)` — the terminal WIN lattice, P0 POV.  `m` is an exact integral
/// score differential at terminals, so the comparisons are exact.
#[inline]
fn outcome(m: f64) -> f64 {
    if m > 0.0 {
        1.0
    } else if m == 0.0 {
        0.5
    } else {
        0.0
    }
}

/// Lexicographic `(w, m)` comparison with [`WIN_TIE`] on the win component.
/// Returns true when `x` is strictly better than `v` for the mover.  Keep-first
/// scan semantics (Python's `max`/`min`): the caller only replaces on strict
/// improvement, so the first extremum in legal-action order wins ties.
#[inline]
fn lex_better(x: (f64, f64), v: (f64, f64), maximize: bool) -> bool {
    let dw = x.0 - v.0;
    if maximize {
        dw > WIN_TIE || (dw.abs() <= WIN_TIE && x.1 > v.1)
    } else {
        dw < -WIN_TIE || (dw.abs() <= WIN_TIE && x.1 < v.1)
    }
}

/// How `_chance` removes the drawn representative from the bag.
///
/// The Python is `[t for t in bag if t is not rep]` over canonical shared tile
/// objects, i.e. [`ChanceDrop::Type`].  [`ChanceDrop::One`] is the reading the
/// comment claims ("drop one instance") and is provided ONLY so a test can show
/// the two agree at `k <= 2` and disagree above it.  The agent always uses
/// `Type`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ChanceDrop {
    /// `t is not rep` over canonical tiles ⇒ every tile of that description goes.
    Type,
    /// Remove exactly one instance (the comment's intent; NOT what runs).
    One,
}

#[derive(Debug)]
pub enum SolveError {
    /// `BudgetExceeded` — node budget blown; the agent falls back to PIMC for
    /// this decision only and stays latched.
    BudgetExceeded,
    /// `ValueError("no legal actions at root")`.
    NoLegalActionsAtRoot,
    Engine(String),
}

impl std::fmt::Display for SolveError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SolveError::BudgetExceeded => write!(f, "BudgetExceeded"),
            SolveError::NoLegalActionsAtRoot => write!(f, "no legal actions at root"),
            SolveError::Engine(s) => write!(f, "engine error: {s}"),
        }
    }
}

#[derive(Clone)]
pub struct SolverConfig {
    /// `budget` — `BudgetExceeded` once `nodes > budget`.
    pub budget: u64,
    /// `CARCASSONNE_TT_CAP`; `0` = unlimited (the production default).
    pub tt_cap: usize,
    pub chance_drop: ChanceDrop,
    /// E1 (default [`Objective::Margin`] = the untouched incumbent code path).
    pub objective: Objective,
}

impl Default for SolverConfig {
    fn default() -> Self {
        SolverConfig {
            // `fair_agent.DEFAULT_EXACT_BUDGET`
            budget: 2_000_000,
            tt_cap: 0,
            chance_drop: ChanceDrop::Type,
            objective: Objective::Margin,
        }
    }
}

/// `endgame_solver.SolveResult` (marginalized mode).
pub struct SolveResult {
    /// The MARGIN component of the optimum in both objectives: `E[margin]`
    /// under the optimal policy (margin mode), or under the win-first policy
    /// (win mode).
    pub value: f64,
    pub to_move: usize,
    /// Actions within [`TIE`] of `value`, in ASCENDING action order (the Python
    /// builds them from `child_values`, a dict filled in ascending legal order).
    /// In win mode: within [`WIN_TIE`] of `win_value` AND within [`TIE`] of
    /// `value` — the lexicographic tie set.
    pub optimal_actions: Vec<i32>,
    /// Per-child MARGIN component, ascending legal order (both objectives).
    pub child_values: Vec<(i32, f64)>,
    pub nodes: u64,
    /// E1 win mode only: `E[outcome]` of the optimum (`None` in margin mode —
    /// the liveness discriminator a manifest can read).
    pub win_value: Option<f64>,
    /// E1 win mode only: per-child `E[outcome]`, ascending (empty in margin mode).
    pub child_win_values: Vec<(i32, f64)>,
    /// Transposition-table entries retained at the end of the solve.
    pub tt_entries: usize,
}

/// 128-bit TT key.
///
/// Python hashes `(string_representation, sorted deck descriptions)` to a
/// `blake2b(digest_size=16)`.  We hash the SAME two components with the crate's
/// sha256, truncated to 128 bits.  This is semantically identical modulo hash
/// collisions, of which there are none at either digest at endgame table sizes
/// (~1e-27 at 1M entries) — and a collision is the ONLY way the two node counts
/// could differ, which the gate would catch.
type Key = [u8; 16];

struct Solver<'a> {
    cfg: &'a SolverConfig,
    nodes: u64,
    tt: HashMap<Key, f64>,
    /// E1 win mode's `(w, m)` table.  Exactly one of `tt`/`tt_win` is used per
    /// solve; `tt_cap` applies to whichever it is.
    tt_win: HashMap<Key, (f64, f64)>,
}

impl<'a> Solver<'a> {
    fn new(cfg: &'a SolverConfig) -> Self {
        Solver {
            cfg,
            nodes: 0,
            tt: HashMap::new(),
            tt_win: HashMap::new(),
        }
    }

    fn tt_entries(&self) -> usize {
        if self.cfg.objective == Objective::Win {
            self.tt_win.len()
        } else {
            self.tt.len()
        }
    }

    /// `_put` — freeze the table (do not INSERT) once capped; updates still land.
    fn put(&mut self, key: Key, val: f64) {
        if self.tt.contains_key(&key) || self.cfg.tt_cap == 0 || self.tt.len() < self.cfg.tt_cap {
            self.tt.insert(key, val);
        }
    }

    fn put_win(&mut self, key: Key, val: (f64, f64)) {
        if self.tt_win.contains_key(&key)
            || self.cfg.tt_cap == 0
            || self.tt_win.len() < self.cfg.tt_cap
        {
            self.tt_win.insert(key, val);
        }
    }

    fn tick(&mut self) -> Result<(), SolveError> {
        self.nodes += 1;
        if self.nodes > self.cfg.budget {
            return Err(SolveError::BudgetExceeded);
        }
        Ok(())
    }

    /// `_key` in the marginalized mode: `sr` + `\x00` + `\x1f`-joined SORTED
    /// deck descriptions.
    fn key(&self, g: &Game) -> Key {
        let mut descs: Vec<&'static str> = g
            .state
            .remaining_deck()
            .iter()
            .map(|&t| tiles::generated::BASE_TILES[t as usize].description)
            .collect();
        descs.sort_unstable();
        let mut buf: Vec<u8> = Vec::with_capacity(8192);
        buf.extend_from_slice(g.string_repr().as_bytes());
        buf.push(0u8);
        for (i, d) in descs.iter().enumerate() {
            if i > 0 {
                buf.push(0x1f);
            }
            buf.extend_from_slice(d.as_bytes());
        }
        let full = sha256_bytes(&buf);
        let mut k = [0u8; 16];
        k.copy_from_slice(&full[..16]);
        k
    }

    fn value(&mut self, g: &Game) -> Result<f64, SolveError> {
        if g.state.is_terminated() {
            return Ok(g.flat_base_score(0) as f64);
        }
        let key = self.key(g);
        if let Some(&v) = self.tt.get(&key) {
            return Ok(v);
        }
        self.tick()?;
        let mover = g.state.current_player;
        let was_meeples = g.state.phase == crate::engine::Phase::Meeples;
        let mut vals: Vec<f64> = Vec::new();
        for a in g.legal_actions() {
            let mut nb = g.clone();
            nb.advance(a).map_err(SolveError::Engine)?;
            if drew_a_tile(g, &nb, was_meeples) && !nb.state.is_terminated() {
                vals.push(self.chance(&nb)?);
            } else {
                vals.push(self.value(&nb)?);
            }
        }
        // `max(vals)` / `min(vals)` — Python's builtins keep the FIRST extremum
        // and never see a NaN here (every value is a finite score expectation).
        // An empty list is Python's `ValueError`; a non-terminal position with no
        // legal action is engine-impossible (the PassAction-in-TILES patch), so
        // reaching it is a bug, not a game state.
        if vals.is_empty() {
            return Err(SolveError::Engine(
                "solver reached a non-terminal node with no legal actions".to_string(),
            ));
        }
        let mut v = vals[0];
        for &x in vals.iter().skip(1) {
            if (mover == 0 && x > v) || (mover != 0 && x < v) {
                v = x;
            }
        }
        self.put(key, v);
        Ok(v)
    }

    /// `_chance(nb)` — `nb` is POST-draw; marginalize the just-drawn tile over
    /// the remaining-bag multiset.
    fn chance(&mut self, nb: &Game) -> Result<f64, SolveError> {
        // bag = [nb.state.next_tile] + list(nb.state.deck)
        let mut bag: Vec<u16> = Vec::with_capacity(nb.state.deck_len() + 1);
        if let Some(t) = nb.state.next_tile {
            bag.push(t);
        }
        bag.extend_from_slice(nb.state.remaining_deck());
        let total = bag.len();

        // groups: description -> instances, in bag INSERTION order.
        let mut order: Vec<u16> = Vec::new();
        let mut counts: HashMap<u16, usize> = HashMap::new();
        for &t in &bag {
            let e = counts.entry(t).or_insert(0);
            if *e == 0 {
                order.push(t);
            }
            *e += 1;
        }

        let mut exp = 0.0f64;
        for &rep in &order {
            let n_group = counts[&rep];
            let remaining: Vec<u16> = match self.cfg.chance_drop {
                ChanceDrop::Type => bag.iter().copied().filter(|&t| t != rep).collect(),
                ChanceDrop::One => {
                    let mut dropped = false;
                    bag.iter()
                        .copied()
                        .filter(|&t| {
                            if !dropped && t == rep {
                                dropped = true;
                                false
                            } else {
                                true
                            }
                        })
                        .collect()
                }
            };
            let mut child = nb.clone();
            child.state.replace_hidden(Some(rep), &remaining);
            exp += (n_group as f64 / total as f64) * self.value(&child)?;
        }
        Ok(exp)
    }

    // ---- E1 win-objective mirror of `value`/`chance` --------------------- //
    // A PARALLEL pair, not a parameterization of the margin pair: the margin
    // path must stay untouched code (flag-off bit-identity is structural).
    // Same tick/TT/traversal discipline; the payload is `(w, m)` and decision
    // nodes compare lexicographically via `lex_better`.

    fn value_win(&mut self, g: &Game) -> Result<(f64, f64), SolveError> {
        if g.state.is_terminated() {
            let m = g.flat_base_score(0) as f64;
            return Ok((outcome(m), m));
        }
        let key = self.key(g);
        if let Some(&v) = self.tt_win.get(&key) {
            return Ok(v);
        }
        self.tick()?;
        let mover = g.state.current_player;
        let was_meeples = g.state.phase == crate::engine::Phase::Meeples;
        let mut vals: Vec<(f64, f64)> = Vec::new();
        for a in g.legal_actions() {
            let mut nb = g.clone();
            nb.advance(a).map_err(SolveError::Engine)?;
            if drew_a_tile(g, &nb, was_meeples) && !nb.state.is_terminated() {
                vals.push(self.chance_win(&nb)?);
            } else {
                vals.push(self.value_win(&nb)?);
            }
        }
        if vals.is_empty() {
            return Err(SolveError::Engine(
                "solver reached a non-terminal node with no legal actions".to_string(),
            ));
        }
        let mut v = vals[0];
        for &x in vals.iter().skip(1) {
            if lex_better(x, v, mover == 0) {
                v = x;
            }
        }
        self.put_win(key, v);
        Ok(v)
    }

    /// Component-wise expectation, same bag grouping and the SAME insertion-
    /// order accumulation as [`Solver::chance`].
    fn chance_win(&mut self, nb: &Game) -> Result<(f64, f64), SolveError> {
        let mut bag: Vec<u16> = Vec::with_capacity(nb.state.deck_len() + 1);
        if let Some(t) = nb.state.next_tile {
            bag.push(t);
        }
        bag.extend_from_slice(nb.state.remaining_deck());
        let total = bag.len();

        let mut order: Vec<u16> = Vec::new();
        let mut counts: HashMap<u16, usize> = HashMap::new();
        for &t in &bag {
            let e = counts.entry(t).or_insert(0);
            if *e == 0 {
                order.push(t);
            }
            *e += 1;
        }

        let mut exp = (0.0f64, 0.0f64);
        for &rep in &order {
            let n_group = counts[&rep];
            let remaining: Vec<u16> = match self.cfg.chance_drop {
                ChanceDrop::Type => bag.iter().copied().filter(|&t| t != rep).collect(),
                ChanceDrop::One => {
                    let mut dropped = false;
                    bag.iter()
                        .copied()
                        .filter(|&t| {
                            if !dropped && t == rep {
                                dropped = true;
                                false
                            } else {
                                true
                            }
                        })
                        .collect()
                }
            };
            let mut child = nb.clone();
            child.state.replace_hidden(Some(rep), &remaining);
            let p = n_group as f64 / total as f64;
            let (w, m) = self.value_win(&child)?;
            exp.0 += p * w;
            exp.1 += p * m;
        }
        Ok(exp)
    }
}

/// `endgame_solver._drew_a_tile` — did `g -> nb` DRAW a replacement from the bag?
///
/// Two transitions draw.  The MEEPLES-phase one (`was_meeples`) has always been
/// marginalized.  The second is the F9/A3 redraw: under `draw_rule="redraw"` a
/// TILES-phase pass sets the unplaceable tile aside and draws again, and that
/// draw is a chance event of exactly the same kind.
///
/// Marginalizing it is REQUIRED, not cosmetic: [`Solver::key`] hashes the
/// **sorted** bag (the multiset is the information set), so letting a redraw's
/// value depend on which tile happened to sit at the front of the deck would
/// return one deck order's answer for another's.  The same unsoundness is latent
/// on the flag-OFF discard path and is deliberately NOT fixed there — flags-off
/// must stay byte-identical.
fn drew_a_tile(g: &Game, nb: &Game, was_meeples: bool) -> bool {
    was_meeples
        || (nb.state.redraw_unplaceable && nb.state.set_aside.len() > g.state.set_aside.len())
}

/// `endgame_solver.solve(game, board, mode="marginalized", budget, alphabeta=False)`.
///
/// Every legal root action is solved exactly (no cross-action pruning), so a
/// regret harness can score any move.  The TT is shared across them.
pub fn solve_marginalized(g: &Game, cfg: &SolverConfig) -> Result<SolveResult, SolveError> {
    if cfg.objective == Objective::Win {
        return solve_marginalized_win(g, cfg);
    }
    let mut s = Solver::new(cfg);
    let to_move = g.state.current_player;
    let was_meeples = g.state.phase == crate::engine::Phase::Meeples;
    let legal = g.legal_actions();
    let mut child_values: Vec<(i32, f64)> = Vec::with_capacity(legal.len());
    for a in legal {
        let mut nb = g.clone();
        nb.advance(a).map_err(SolveError::Engine)?;
        let v = if nb.state.is_terminated() {
            nb.flat_base_score(0) as f64
        } else if drew_a_tile(g, &nb, was_meeples) {
            s.chance(&nb)?
        } else {
            s.value(&nb)?
        };
        child_values.push((a, v));
    }
    if child_values.is_empty() {
        return Err(SolveError::NoLegalActionsAtRoot);
    }
    let mut vstar = child_values[0].1;
    for &(_, v) in child_values.iter().skip(1) {
        if (to_move == 0 && v > vstar) || (to_move != 0 && v < vstar) {
            vstar = v;
        }
    }
    let optimal_actions: Vec<i32> = child_values
        .iter()
        .filter(|(_, v)| (v - vstar).abs() <= TIE)
        .map(|(a, _)| *a)
        .collect();
    Ok(SolveResult {
        value: vstar,
        to_move,
        optimal_actions,
        child_values,
        nodes: s.nodes,
        win_value: None,
        child_win_values: Vec::new(),
        tt_entries: s.tt_entries(),
    })
}

/// E1 win-objective root solve (`cfg.objective == Objective::Win`).  Same root
/// discipline as the margin path: every legal root action is solved exactly,
/// the TT is shared across them, ascending order.
fn solve_marginalized_win(g: &Game, cfg: &SolverConfig) -> Result<SolveResult, SolveError> {
    let mut s = Solver::new(cfg);
    let to_move = g.state.current_player;
    let was_meeples = g.state.phase == crate::engine::Phase::Meeples;
    let legal = g.legal_actions();
    let mut pairs: Vec<(i32, (f64, f64))> = Vec::with_capacity(legal.len());
    for a in legal {
        let mut nb = g.clone();
        nb.advance(a).map_err(SolveError::Engine)?;
        let v = if nb.state.is_terminated() {
            let m = nb.flat_base_score(0) as f64;
            (outcome(m), m)
        } else if drew_a_tile(g, &nb, was_meeples) {
            s.chance_win(&nb)?
        } else {
            s.value_win(&nb)?
        };
        pairs.push((a, v));
    }
    if pairs.is_empty() {
        return Err(SolveError::NoLegalActionsAtRoot);
    }
    let mut vstar = pairs[0].1;
    for &(_, v) in pairs.iter().skip(1) {
        if lex_better(v, vstar, to_move == 0) {
            vstar = v;
        }
    }
    // The lexicographic tie set: win-tied (WIN_TIE) AND margin-tied (TIE).
    let optimal_actions: Vec<i32> = pairs
        .iter()
        .filter(|(_, v)| (v.0 - vstar.0).abs() <= WIN_TIE && (v.1 - vstar.1).abs() <= TIE)
        .map(|(a, _)| *a)
        .collect();
    Ok(SolveResult {
        value: vstar.1,
        to_move,
        optimal_actions,
        child_values: pairs.iter().map(|&(a, v)| (a, v.1)).collect(),
        nodes: s.nodes,
        win_value: Some(vstar.0),
        child_win_values: pairs.iter().map(|&(a, v)| (a, v.0)).collect(),
        tt_entries: s.tt_entries(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Drive a seeded game down to a `k_remaining <= 2` TILES decision.
    fn endgame(seed: &str, k: usize) -> Game {
        let mut g = Game::from_seed(seed);
        loop {
            let kr = g.state.deck_len() + usize::from(g.state.next_tile.is_some());
            if kr <= k && g.state.phase == crate::engine::Phase::Tiles {
                return g;
            }
            let legal = g.legal_actions();
            g.advance(legal[legal.len() / 2]).unwrap();
        }
    }

    #[test]
    fn a_k2_endgame_solves_and_reports_an_optimal_set() {
        let g = endgame("11", 2);
        let r = solve_marginalized(&g, &SolverConfig::default()).unwrap();
        assert!(!r.optimal_actions.is_empty());
        assert_eq!(r.child_values.len(), g.legal_actions().len());
        // optimal actions are a subset of the legal actions, ascending
        let mut prev = i32::MIN;
        for &a in &r.optimal_actions {
            assert!(a > prev);
            prev = a;
        }
        assert_eq!(r.to_move, g.state.current_player);
    }

    /// The `ChanceDrop` axis is INERT at the deployed `exact_max_k = 2` (the
    /// post-draw bag is never larger than one tile there) — the quirk only has
    /// teeth above the band.  Recorded so nobody "fixes" the Type reading.
    #[test]
    fn chance_drop_axis_is_inert_at_k2() {
        for seed in ["11", "12", "13", "14"] {
            let g = endgame(seed, 2);
            let a = solve_marginalized(&g, &SolverConfig::default()).unwrap();
            let b = solve_marginalized(
                &g,
                &SolverConfig {
                    chance_drop: ChanceDrop::One,
                    ..SolverConfig::default()
                },
            )
            .unwrap();
            assert_eq!(a.value.to_bits(), b.value.to_bits());
            assert_eq!(a.optimal_actions, b.optimal_actions);
            assert_eq!(a.nodes, b.nodes);
        }
    }

    #[test]
    fn a_tiny_budget_raises_budget_exceeded() {
        let g = endgame("11", 2);
        let e = solve_marginalized(
            &g,
            &SolverConfig {
                budget: 1,
                ..SolverConfig::default()
            },
        );
        assert!(matches!(e, Err(SolveError::BudgetExceeded)));
    }

    // ---- E1 win objective ------------------------------------------------ //

    fn win_cfg() -> SolverConfig {
        SolverConfig {
            objective: Objective::Win,
            ..SolverConfig::default()
        }
    }

    /// Margin mode must not grow a win payload — `win_value: None` is the
    /// liveness discriminator a manifest reads.
    #[test]
    fn margin_mode_has_no_win_payload() {
        let g = endgame("11", 2);
        let r = solve_marginalized(&g, &SolverConfig::default()).unwrap();
        assert!(r.win_value.is_none());
        assert!(r.child_win_values.is_empty());
    }

    /// DESIGN §2 proposition, tested: at K<=2 every chance bag is a singleton,
    /// the solve is deterministic, and the two objectives coincide EXACTLY —
    /// same optimal set, same margin value, win value = outcome(margin), and
    /// per-child margins bit-equal.
    #[test]
    fn win_and_margin_coincide_at_k2_the_inertness_proposition() {
        for seed in ["11", "12", "13", "14", "15", "16", "17", "18"] {
            let g = endgame(seed, 2);
            let m = solve_marginalized(&g, &SolverConfig::default()).unwrap();
            let w = solve_marginalized(&g, &win_cfg()).unwrap();
            assert_eq!(m.optimal_actions, w.optimal_actions, "seed {seed}");
            assert_eq!(m.value.to_bits(), w.value.to_bits(), "seed {seed}");
            let wv = w.win_value.expect("win mode must report win_value");
            assert_eq!(wv, outcome(m.value), "seed {seed}");
            assert_eq!(m.child_values.len(), w.child_values.len());
            for ((a1, v1), (a2, v2)) in m.child_values.iter().zip(w.child_values.iter()) {
                assert_eq!(a1, a2);
                assert_eq!(v1.to_bits(), v2.to_bits(), "seed {seed} child {a1}");
            }
            // and per-child win values are the outcome of the (deterministic)
            // per-child margins — the monotone-transform structure itself.
            for ((_, m_child), (_, w_child)) in
                m.child_values.iter().zip(w.child_win_values.iter())
            {
                assert_eq!(outcome(*m_child), *w_child, "seed {seed}");
            }
        }
    }

    /// At K=3 the bag is genuinely mixed; the win mode must still solve, and
    /// its win_value must be a legal expectation.  (The pinned DIVERGENCE
    /// positive control lives in the Python test suite where the corpus replay
    /// machinery is — this test pins the mechanics, not the divergence.)
    #[test]
    fn win_mode_solves_a_k3_endgame_with_a_real_chance_mix() {
        let g = endgame("11", 3);
        let w = solve_marginalized(&g, &win_cfg()).unwrap();
        let wv = w.win_value.unwrap();
        assert!((0.0..=1.0).contains(&wv), "E[outcome] out of range: {wv}");
        assert!(!w.optimal_actions.is_empty());
        assert_eq!(w.child_values.len(), w.child_win_values.len());
        // the win-mode optimum's E[outcome] can never be beaten by any child
        let to_move = w.to_move;
        for &(_, cw) in &w.child_win_values {
            if to_move == 0 {
                assert!(cw <= wv + WIN_TIE);
            } else {
                assert!(cw >= wv - WIN_TIE);
            }
        }
    }

    #[test]
    fn win_mode_budget_exceeded_still_raises() {
        let g = endgame("11", 2);
        let e = solve_marginalized(
            &g,
            &SolverConfig {
                budget: 1,
                ..win_cfg()
            },
        );
        assert!(matches!(e, Err(SolveError::BudgetExceeded)));
    }

    #[test]
    fn objective_parses_and_prints() {
        assert_eq!(Objective::parse("margin").unwrap(), Objective::Margin);
        assert_eq!(Objective::parse("win").unwrap(), Objective::Win);
        assert!(Objective::parse("wins").is_err());
        assert_eq!(Objective::Win.value(), "win");
    }
}
