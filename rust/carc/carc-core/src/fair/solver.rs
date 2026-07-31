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
}

impl Default for SolverConfig {
    fn default() -> Self {
        SolverConfig {
            // `fair_agent.DEFAULT_EXACT_BUDGET`
            budget: 2_000_000,
            tt_cap: 0,
            chance_drop: ChanceDrop::Type,
        }
    }
}

/// `endgame_solver.SolveResult` (marginalized mode).
pub struct SolveResult {
    pub value: f64,
    pub to_move: usize,
    /// Actions within [`TIE`] of `value`, in ASCENDING action order (the Python
    /// builds them from `child_values`, a dict filled in ascending legal order).
    pub optimal_actions: Vec<i32>,
    pub child_values: Vec<(i32, f64)>,
    pub nodes: u64,
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
}

impl<'a> Solver<'a> {
    fn new(cfg: &'a SolverConfig) -> Self {
        Solver {
            cfg,
            nodes: 0,
            tt: HashMap::new(),
        }
    }

    /// `_put` — freeze the table (do not INSERT) once capped; updates still land.
    fn put(&mut self, key: Key, val: f64) {
        if self.tt.contains_key(&key) || self.cfg.tt_cap == 0 || self.tt.len() < self.cfg.tt_cap {
            self.tt.insert(key, val);
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
            if was_meeples && !nb.state.is_terminated() {
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
}

/// `endgame_solver.solve(game, board, mode="marginalized", budget, alphabeta=False)`.
///
/// Every legal root action is solved exactly (no cross-action pruning), so a
/// regret harness can score any move.  The TT is shared across them.
pub fn solve_marginalized(g: &Game, cfg: &SolverConfig) -> Result<SolveResult, SolveError> {
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
        } else if was_meeples {
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
}
