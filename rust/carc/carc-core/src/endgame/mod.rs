//! `scripts/level2/endgame_solver.py` — the **deep exact-K endgame solver**, both
//! modes, in Rust.
//!
//! The Python file is the spec and stays the ORACLE; every answer here is gated
//! against it by `scripts/rustport/reconcile_exact_solver.py` (value, the whole
//! optimal-action SET, every child value, and the NODE COUNT).
//!
//! ```text
//! mode="clairvoyant"  : perfect-information minimax over the KNOWN real future
//!                       deck order.  `alphabeta=true` prunes inside each root
//!                       child's subtree (exact — it only removes provably
//!                       irrelevant subtrees), `false` is the no-prune oracle.
//! mode="marginalized" : expectiminimax — every draw is a CHANCE node over the
//!                       remaining-bag multiset.  Alpha-beta is FORBIDDEN here
//!                       (chance nodes have no minimax cutoff), exactly as the
//!                       Python `assert` says.
//! ```
//!
//! Leaf value = the REAL final score differential `flat_base_score(state, 0)`;
//! P0 maximizes, P1 minimizes, at every depth, in both modes.
//!
//! ## Relationship to [`crate::fair::solver`]
//!
//! [`crate::fair::solver::solve_marginalized`] is the SHIPPED marginalized
//! solver — it is what the fair champion latches into at `k_remaining <=
//! exact_max_k` and it carries its own byte-identity guarantees, so this module
//! does not touch it.  This module is a second, independent transcription of the
//! same Python file that additionally covers the clairvoyant half and the
//! alpha-beta path.  Two implementations of one spec must not drift, so
//! `marginalized_agrees_with_the_fair_solver` asserts them bit-equal (value,
//! optimal set, every child value, node count) on the fair solver's own fixtures.
//!
//! [`ChanceDrop`], [`SolveError`] and [`TIE`] are REUSED from that module rather
//! than re-declared: a second definition of the chance-node quirk is exactly the
//! drift the parity test exists to prevent.
//!
//! ## The details that are easy to get wrong (all gated)
//!
//! 1. **`_tick` is charged per non-terminal TT-MISS call only.**  The root
//!    position is never ticked (`solve` descends into each root child directly),
//!    terminals are not ticked, TT hits are not ticked, `_chance` is not ticked.
//!    In the alpha-beta path a TT entry that RETURNS (exact, or a bound that
//!    cuts) does not tick; one that merely narrows the window does.
//! 2. **The TT is shared across root actions**, and root actions are visited in
//!    ASCENDING order — so the node count depends on that order.
//! 3. **The TT key is mode-dependent**: the clairvoyant key hashes the deck in
//!    ORDER (the real future is public to the solver), the marginalized key
//!    hashes the SORTED multiset (the spec's V5 no-leak key).
//! 4. **`_chance` drops the whole TYPE** — see [`ChanceDrop`].
//! 5. **The expectation accumulates in bag-group INSERTION order** (float
//!    addition is not associative).
//! 6. **The optimal set is `abs(v - vstar) <= tol`** with `tol = 1e-6` in the
//!    marginalized mode and `tol = 0` (exact equality) in the clairvoyant one.

use std::collections::HashMap;

use crate::fair::solver::{ChanceDrop, Objective, SolveError, TIE};
use crate::game::Game;
use crate::sha256::sha256_bytes;
use crate::tiles;

/// `endgame_solver.solve(mode=...)`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mode {
    /// Minimax over the real deck order (`board.state.deck` as it stands).
    Clairvoyant,
    /// Expectiminimax over the remaining-bag multiset.
    Marginalized,
}

impl Mode {
    pub fn parse(s: &str) -> Result<Self, String> {
        match s {
            "clairvoyant" => Ok(Mode::Clairvoyant),
            "marginalized" => Ok(Mode::Marginalized),
            other => Err(format!(
                "mode must be 'clairvoyant' | 'marginalized'; got {other:?}"
            )),
        }
    }

    pub fn value(&self) -> &'static str {
        match self {
            Mode::Clairvoyant => "clairvoyant",
            Mode::Marginalized => "marginalized",
        }
    }
}

/// `_Solver.__init__` knobs.
#[derive(Clone)]
pub struct Config {
    /// `budget` — [`SolveError::BudgetExceeded`] once `nodes > budget`.
    /// The Python default is `4_000_000`.
    pub budget: u64,
    /// `CARCASSONNE_TT_CAP`; `0` = unlimited.
    ///
    /// **Policy = FREEZE, not evict** (the Python's, verbatim): once the table
    /// holds `tt_cap` entries no NEW key is inserted, but existing keys are
    /// still read and still updated.  This is correctness-neutral — the TT is
    /// pure memoization, so a missing entry only forces recomputation — and it
    /// trades memory for node count.  It therefore CHANGES `nodes`, so a gate
    /// that compares node counts must run both sides at the same cap.
    pub tt_cap: usize,
    /// Clairvoyant only; the Python `assert` rejects it for marginalized.
    pub alphabeta: bool,
    pub chance_drop: ChanceDrop,
    /// E1 objective (default [`Objective::Margin`] = the untouched incumbent).
    ///
    /// `Win` is MARGINALIZED-ONLY, and its marginalized solve DELEGATES to
    /// [`crate::fair::solver::solve_marginalized`] — the changed semantics get
    /// exactly ONE implementation, per this module's own anti-drift rule
    /// (`ChanceDrop`/`TIE` are reused the same way; two transcriptions of a
    /// new backup would be exactly the drift the parity tests exist to
    /// prevent).  `Clairvoyant + Win` is REJECTED: a clairvoyant future is
    /// deterministic, `outcome` is a monotone transform of the deterministic
    /// margin, so margin-max is already win-optimal — a clairvoyant "win mode"
    /// would be a live-looking no-op flag.
    pub objective: Objective,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            budget: 4_000_000,
            tt_cap: 0,
            alphabeta: false,
            chance_drop: ChanceDrop::Type,
            objective: Objective::Margin,
        }
    }
}

/// `endgame_solver.SolveResult`.
#[derive(Clone, Debug)]
pub struct SolveResult {
    pub mode: Mode,
    pub value: f64,
    pub to_move: usize,
    /// Actions achieving `value`, in ASCENDING action order.
    pub optimal_actions: Vec<i32>,
    /// Every legal root action's exact value, ascending (the Python builds a
    /// dict in ascending legal order and the caller relies on that order).
    pub child_values: Vec<(i32, f64)>,
    pub nodes: u64,
    /// Transposition-table entries retained at the end of the solve — the
    /// memory figure.  (The table only grows, so this IS the peak.)
    pub tt_entries: usize,
    /// E1 win mode only: `E[outcome]` of the optimum (`None` under
    /// [`Objective::Margin`]).
    pub win_value: Option<f64>,
    /// E1 win mode only: per-child `E[outcome]`, ascending (empty otherwise).
    pub child_win_values: Vec<(i32, f64)>,
}

impl SolveResult {
    /// `endgame_solver.regret_of` — points `action` loses vs optimal, from the
    /// MOVER's perspective (`>= 0`).  `None` if the action was not scored.
    pub fn regret_of(&self, action: i32) -> Option<f64> {
        let v = self
            .child_values
            .iter()
            .find(|(a, _)| *a == action)
            .map(|(_, v)| *v)?;
        Some(if self.to_move == 0 {
            self.value - v
        } else {
            v - self.value
        })
    }
}

/// 128-bit TT key.
///
/// Python hashes `(string_representation, deck descriptions)` with
/// `blake2b(digest_size=16)`; we hash the SAME two components with the crate's
/// sha256 truncated to 128 bits.  Semantically identical modulo hash collisions
/// (~1e-27 at 1M entries at either digest) — and a collision is the ONLY way the
/// node counts could differ, which the gate would catch.
type Key = [u8; 16];

/// Alpha-beta TT bound flags — `_EXACT`, `_LOWER`, `_UPPER`.
const F_EXACT: u8 = 0;
const F_LOWER: u8 = 1;
const F_UPPER: u8 = 2;

struct Solver<'a> {
    cfg: &'a Config,
    mode: Mode,
    nodes: u64,
    /// The exact-value table (`_value`, both modes).
    tt: HashMap<Key, f64>,
    /// The bound-flagged table (`_value_ab`, clairvoyant only).  Exactly one of
    /// the two is used per solve, and `tt_cap` applies to whichever it is —
    /// Python has a single `self.tt` and a single `_put`.
    tt_ab: HashMap<Key, (f64, u8)>,
}

impl<'a> Solver<'a> {
    fn new(cfg: &'a Config, mode: Mode) -> Self {
        Solver {
            cfg,
            mode,
            nodes: 0,
            tt: HashMap::new(),
            tt_ab: HashMap::new(),
        }
    }

    fn tt_entries(&self) -> usize {
        if self.cfg.alphabeta {
            self.tt_ab.len()
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

    fn put_ab(&mut self, key: Key, val: (f64, u8)) {
        if self.tt_ab.contains_key(&key)
            || self.cfg.tt_cap == 0
            || self.tt_ab.len() < self.cfg.tt_cap
        {
            self.tt_ab.insert(key, val);
        }
    }

    fn tick(&mut self) -> Result<(), SolveError> {
        self.nodes += 1;
        if self.nodes > self.cfg.budget {
            return Err(SolveError::BudgetExceeded);
        }
        Ok(())
    }

    /// `_key` — `sr` + `\x00` + `\x1f`-joined deck descriptions, in DECK ORDER
    /// (clairvoyant) or SORTED (marginalized).
    fn key(&self, g: &Game) -> Key {
        let mut descs: Vec<&'static str> = g
            .state
            .remaining_deck()
            .iter()
            .map(|&t| tiles::generated::BASE_TILES[t as usize].description)
            .collect();
        if self.mode == Mode::Marginalized {
            // Python `sorted(descs)` — code-point order on ASCII descriptions,
            // i.e. Rust's byte order.
            descs.sort_unstable();
        }
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

    /// `_Solver._value` — plain minimax / expectiminimax with an EXACT-value TT.
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
        let marg = self.mode == Mode::Marginalized;
        let mut vals: Vec<f64> = Vec::new();
        for a in g.legal_actions() {
            let mut nb = g.clone();
            nb.advance(a).map_err(SolveError::Engine)?;
            if marg && !nb.state.is_terminated() && drew_a_tile(g, &nb, was_meeples) {
                vals.push(self.chance(&nb)?);
            } else {
                vals.push(self.value(&nb)?);
            }
        }
        // `max(vals)` / `min(vals)` — Python's builtins keep the FIRST extremum
        // and never see a NaN here.  An empty list is Python's `ValueError`; a
        // non-terminal position with no legal action is engine-impossible.
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

    /// `_Solver._chance(nb)` — `nb` is POST-draw; marginalize the just-drawn
    /// tile over the remaining-bag multiset.
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

    /// `_Solver._value_ab` — exact fail-soft alpha-beta for the clairvoyant mode.
    fn value_ab(&mut self, g: &Game, mut alpha: f64, mut beta: f64) -> Result<f64, SolveError> {
        if g.state.is_terminated() {
            return Ok(g.flat_base_score(0) as f64);
        }
        let key = self.key(g);
        if let Some(&(val, flag)) = self.tt_ab.get(&key) {
            if flag == F_EXACT {
                return Ok(val);
            }
            if flag == F_LOWER {
                if val >= beta {
                    return Ok(val);
                }
                if val > alpha {
                    alpha = val;
                }
            } else if flag == F_UPPER {
                if val <= alpha {
                    return Ok(val);
                }
                if val < beta {
                    beta = val;
                }
            }
            if alpha >= beta {
                return Ok(val);
            }
        }
        self.tick()?;
        let mover = g.state.current_player;
        let (a0, b0) = (alpha, beta);
        let best;
        if mover == 0 {
            // maximizer
            let mut b = f64::NEG_INFINITY;
            for a in g.legal_actions() {
                let mut nb = g.clone();
                nb.advance(a).map_err(SolveError::Engine)?;
                let v = self.value_ab(&nb, alpha, beta)?;
                if v > b {
                    b = v;
                }
                if b > alpha {
                    alpha = b;
                }
                if alpha >= beta {
                    break; // beta cutoff
                }
            }
            best = b;
        } else {
            // minimizer
            let mut b = f64::INFINITY;
            for a in g.legal_actions() {
                let mut nb = g.clone();
                nb.advance(a).map_err(SolveError::Engine)?;
                let v = self.value_ab(&nb, alpha, beta)?;
                if v < b {
                    b = v;
                }
                if b < beta {
                    beta = b;
                }
                if beta <= alpha {
                    break; // alpha cutoff
                }
            }
            best = b;
        }
        // Fail-soft bound classification for the TT.
        let flag = if best <= a0 {
            F_UPPER
        } else if best >= b0 {
            F_LOWER
        } else {
            F_EXACT
        };
        self.put_ab(key, (best, flag));
        Ok(best)
    }
}

/// `endgame_solver._drew_a_tile` — did `g -> nb` DRAW a replacement from the bag?
///
/// Two transitions draw.  The MEEPLES-phase one (`was_meeples`) has always been
/// marginalized.  The second is the F9/A3 redraw: under `draw_rule="redraw"` a
/// TILES-phase pass sets the unplaceable tile aside and draws again, and that
/// draw is a chance event of exactly the same kind.
///
/// Marginalizing it is REQUIRED, not cosmetic: [`Solver::key`] hashes the SORTED
/// bag in the marginalized mode, so letting a redraw's value depend on which
/// tile happened to sit at the front of the deck would return one deck order's
/// answer for another's.  The same unsoundness is latent on the flag-OFF discard
/// path and is deliberately NOT fixed there — flags-off must stay byte-identical.
///
/// The clairvoyant mode never consults this: it reads the true order, so a
/// redraw is not a chance event for it.
fn drew_a_tile(g: &Game, nb: &Game, was_meeples: bool) -> bool {
    was_meeples
        || (nb.state.redraw_unplaceable && nb.state.set_aside.len() > g.state.set_aside.len())
}

/// `endgame_solver.solve(game, board, mode, budget, alphabeta)`.
///
/// Every legal root action is solved exactly (no cross-action pruning at the
/// root, and each root child gets a FULL alpha-beta window) so a regret harness
/// can score any move.  The TT is shared across root actions.
pub fn solve(g: &Game, mode: Mode, cfg: &Config) -> Result<SolveResult, SolveError> {
    if cfg.alphabeta && mode == Mode::Marginalized {
        return Err(SolveError::Engine(
            "alpha-beta is clairvoyant-only (chance nodes break minimax cutoffs)".to_string(),
        ));
    }
    if cfg.objective == Objective::Win {
        if mode == Mode::Clairvoyant {
            return Err(SolveError::Engine(
                "objective='win' is marginalized-only: a clairvoyant future is \
                 deterministic and outcome is a monotone transform of the deterministic \
                 margin, so margin-max is already win-optimal there"
                    .to_string(),
            ));
        }
        // Delegate to the SHIPPED fair solver (single implementation of the
        // win semantics; see `Config::objective`).
        let fcfg = crate::fair::solver::SolverConfig {
            budget: cfg.budget,
            tt_cap: cfg.tt_cap,
            chance_drop: cfg.chance_drop,
            objective: Objective::Win,
        };
        let r = crate::fair::solver::solve_marginalized(g, &fcfg)?;
        return Ok(SolveResult {
            mode,
            value: r.value,
            to_move: r.to_move,
            optimal_actions: r.optimal_actions,
            child_values: r.child_values,
            nodes: r.nodes,
            tt_entries: r.tt_entries,
            win_value: r.win_value,
            child_win_values: r.child_win_values,
        });
    }
    let mut s = Solver::new(cfg, mode);
    let to_move = g.state.current_player;
    let was_meeples = g.state.phase == crate::engine::Phase::Meeples;
    let legal = g.legal_actions();
    let mut child_values: Vec<(i32, f64)> = Vec::with_capacity(legal.len());
    for a in legal {
        let mut nb = g.clone();
        nb.advance(a).map_err(SolveError::Engine)?;
        let v = if nb.state.is_terminated() {
            nb.flat_base_score(0) as f64
        } else if mode == Mode::Marginalized && drew_a_tile(g, &nb, was_meeples) {
            s.chance(&nb)?
        } else if cfg.alphabeta {
            s.value_ab(&nb, f64::NEG_INFINITY, f64::INFINITY)?
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
    // `tol = _TIE if mode == "marginalized" else 0` — the clairvoyant set is
    // EXACT equality (integral score diffs), the marginalized one is within 1e-6.
    let tol = match mode {
        Mode::Marginalized => TIE,
        Mode::Clairvoyant => 0.0,
    };
    let optimal_actions: Vec<i32> = child_values
        .iter()
        .filter(|(_, v)| (v - vstar).abs() <= tol)
        .map(|(a, _)| *a)
        .collect();
    Ok(SolveResult {
        mode,
        value: vstar,
        to_move,
        optimal_actions,
        child_values,
        nodes: s.nodes,
        tt_entries: s.tt_entries(),
        win_value: None,
        child_win_values: Vec::new(),
    })
}

// --------------------------------------------------------------------------
// The independent brute-force reference (`tests/test_endgame_solver.py::_brute_*`)
// --------------------------------------------------------------------------

/// `_brute_clair` — pure minimax over the real deck order, **no TT, no pruning**.
///
/// This is the validation oracle, not a solver: it is exponential and is only
/// usable at K<=2 (and small K=3).  `budget` bounds the recursion so a fuzz
/// harness cannot hang; it counts EVERY non-terminal visit (there is no TT to
/// miss), so it is NOT comparable to [`SolveResult::nodes`].
pub fn brute_clairvoyant(g: &Game, budget: u64) -> Result<f64, SolveError> {
    let mut n = 0u64;
    brute_inner(g, budget, &mut n)
}

fn brute_inner(g: &Game, budget: u64, n: &mut u64) -> Result<f64, SolveError> {
    if g.state.is_terminated() {
        return Ok(g.flat_base_score(0) as f64);
    }
    *n += 1;
    if *n > budget {
        return Err(SolveError::BudgetExceeded);
    }
    let mover = g.state.current_player;
    let mut best: Option<f64> = None;
    for a in g.legal_actions() {
        let mut nb = g.clone();
        nb.advance(a).map_err(SolveError::Engine)?;
        let v = brute_inner(&nb, budget, n)?;
        best = Some(match best {
            None => v,
            Some(b) => {
                if (mover == 0 && v > b) || (mover != 0 && v < b) {
                    v
                } else {
                    b
                }
            }
        });
    }
    best.ok_or_else(|| {
        SolveError::Engine("brute reached a non-terminal node with no legal actions".to_string())
    })
}

/// `_brute_root` — `(V*, optimal set, every child value)` from the brute force.
pub fn brute_clairvoyant_root(
    g: &Game,
    budget: u64,
) -> Result<(f64, Vec<i32>, Vec<(i32, f64)>), SolveError> {
    let to_move = g.state.current_player;
    let mut child_values: Vec<(i32, f64)> = Vec::new();
    for a in g.legal_actions() {
        let mut nb = g.clone();
        nb.advance(a).map_err(SolveError::Engine)?;
        child_values.push((a, brute_clairvoyant(&nb, budget)?));
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
    let optimal: Vec<i32> = child_values
        .iter()
        .filter(|(_, v)| *v == vstar)
        .map(|(a, _)| *a)
        .collect();
    Ok((vstar, optimal, child_values))
}

#[cfg(test)]
mod tests;
