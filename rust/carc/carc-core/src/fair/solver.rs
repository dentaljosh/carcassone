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

use std::cell::{Cell, RefCell};
use std::collections::HashMap;

use crate::game::Game;
use crate::leaf::{decompose_into, flat_base_score, Decomp, Scratch};
use crate::sha256::sha256_bytes;
use crate::tiles;

// ---------------------------------------------------------------------------
// L2 — the terminal scorer swap
// ---------------------------------------------------------------------------
//
// Every terminal this solver reaches used to be scored TWICE by the object
// route: once in place by `GameState::apply_action`'s terminal
// `count_final_scores()` (a from-scratch BFS flood fill per placed meeple, plus
// `count_farm_points`'s per-farm-node `HashSet<Vec<CoordSide>>` dedup), and once
// again by `GameState::flat_base_score`, which clones the whole state and re-runs
// `count_final_scores` on it — a near no-op by then, since the first pass has
// already drained the meeples, so that second call was paying for a
// `GameState::clone` and nothing else.
//
// L2 replaces both with ONE flat pass:
//
//   * the traversal drives `Game::advance_unscored`, which skips the in-place
//     `count_final_scores` at terminals and leaves `scores` RUNNING with every
//     meeple still placed;
//   * the terminal value comes from `leaf::decompose_into` + `leaf::flat_base_score`
//     (`running + final_award`) over caller-owned, thread-local buffers.
//
// **Why this is scoped here and not in `apply_action`.** `apply_action` is the
// shared transition — tier1 playouts, PUCT search, the eval harness and the
// phone all drive it, and several of them read a terminal state's `scores` and
// `placed_meeples` afterwards. Changing it globally would owe a proof that the
// meeple DRAIN is reproduced exactly as well as the scores. Scoping the
// substitution to the solver owes only the score, because nothing downstream of
// a solver terminal reads anything else: `is_terminated()` is
// `next_tile.is_none()`, and `Solver::key` is only ever taken on NON-terminal
// nodes (both `value` and `value_win` return before keying a terminal). The
// shared path is byte-untouched.
//
// **Bit-identity.** `leaf::flat_base_score == GameState::flat_base_score` on
// every position is already gated by the P2 suite and by L0's 240-leg
// `G-BITEXACT`; L2 re-gates it on solver-reached terminals specifically, and
// gates the whole solve (value bits, optimal-action set, every child value's
// bits, node count, TT entries) against the pre-change route.

/// Per-thread flat-route buffers. `decompose_into` is allocation-free only if
/// the caller keeps the buffers, so ONE pair is reused across every terminal of
/// every solve on this thread. Thread-local rather than threaded through
/// `Solver` because the solver is also driven from `std::thread::scope` workers
/// (the exact-K eval fans solves across threads); TLS gives each its own pair
/// with no sharing, no locks and no API change — the same discipline L0's
/// `tier1::SCORER_BUFS` validated under its threading gate.
#[derive(Default)]
struct TerminalBufs {
    decomp: Decomp,
    scratch: Scratch,
}

thread_local! {
    static TERMINAL_BUFS: RefCell<TerminalBufs> = RefCell::new(TerminalBufs::default());
    /// ⚠️ GATES AND TESTS ONLY — see [`with_legacy_terminal_scorer`].
    static FORCE_LEGACY_TERMINAL: Cell<bool> = const { Cell::new(false) };
}

/// Restores [`FORCE_LEGACY_TERMINAL`] even if `f` unwinds.
struct LegacyTerminalGuard(bool);
impl Drop for LegacyTerminalGuard {
    fn drop(&mut self) {
        FORCE_LEGACY_TERMINAL.with(|c| c.set(self.0));
    }
}

/// ⚠️ **GATES AND TESTS ONLY.** Runs `f` with the solver's terminal handling
/// forced back to the PRE-L2 route **on this thread** — scored `Game::advance`
/// (in-place `count_final_scores`) plus `GameState::flat_base_score`.
///
/// This is not a configuration knob and nothing in production calls it: the swap
/// is bit-identical, so there is no shape to choose between. It exists so an
/// identity gate can run BOTH routes over the same positions without
/// re-implementing the traversal, exactly as `tier1::with_legacy_scorer` does
/// for L0.
#[doc(hidden)]
pub fn with_legacy_terminal_scorer<R>(f: impl FnOnce() -> R) -> R {
    let prev = FORCE_LEGACY_TERMINAL.with(|c| c.replace(true));
    let _g = LegacyTerminalGuard(prev);
    f()
}

#[inline]
fn legacy_terminal() -> bool {
    FORCE_LEGACY_TERMINAL.with(|c| c.get())
}

/// Apply `a` to a clone of `g`, deferring the terminal scoring (unless the
/// gate switch has forced the legacy route). Shared with
/// [`crate::endgame`], which runs the same substitution on its own solver.
#[inline]
pub(crate) fn step(g: &Game, a: i32) -> Result<Game, String> {
    let mut nb = g.clone();
    if legacy_terminal() {
        nb.advance(a)?;
    } else {
        nb.advance_unscored(a)?;
    }
    Ok(nb)
}

/// The terminal leaf — `flat_base_score(state, 0)`, P0 POV, as an `f64`.
///
/// Flat route by default (`running + final_award` off one whole-board
/// decomposition over the thread-local buffers); the legacy engine route under
/// [`with_legacy_terminal_scorer`]. `GameState::flat_base_score` is correct on
/// both a drained and an un-drained terminal, so the two arms differ only in
/// HOW the same number is computed.
#[inline]
pub(crate) fn terminal_value(g: &Game) -> f64 {
    if legacy_terminal() {
        return g.flat_base_score(0) as f64;
    }
    TERMINAL_BUFS.with(|b| {
        let b = &mut *b.borrow_mut();
        decompose_into(&g.state, &mut b.decomp, &mut b.scratch);
        flat_base_score(&g.state, 0, &b.decomp) as f64
    })
}

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
///
/// **The proposition SURVIVES [`SolverConfig::wc_tiebreak`] armed.**  Arming
/// the flag only changes `outcome(0.0)` from `0.5` to `0.0` — it does not
/// touch `m > 0.0` or `m < 0.0` — and `outcome` stays monotone non-decreasing
/// in `m` either way (see `outcome`'s own doc comment).  At K<=2 every chance
/// bag is still a singleton regardless of the flag (the flag is a terminal
/// scoring rule, not a chance-node rule), so the solve is still a
/// deterministic minimax and lexicographic `(w, m)` max still equals margin
/// max, armed or not.
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

/// `outcome(m, wc_tiebreak)` — the terminal WIN lattice, P0 POV.  `m` is an
/// exact integral score differential at terminals, so the comparisons are
/// exact.
///
/// `wc_tiebreak` (default `false`, the untouched incumbent reading): official
/// World Championship rules rule a tied final score a LOSS for the starting
/// player — `measurement/TOURNAMENT_LANDSCAPE_MEMO_20260728.md` §1.3,
/// verbatim: *"in the unlikely case of a draw / tie in all games ... the
/// starting player always loses automatically!"*  P0 IS the starting player
/// (`outcome` is already P0-POV, so this is a value change at `m == 0.0`
/// only, no sign/lattice change elsewhere).  Armed, `m == 0.0` yields `0.0`
/// (a loss for P0) instead of the unarmed `0.5` (a draw); `m > 0.0` and
/// `m < 0.0` are untouched in both readings.  Mirrors
/// `scripts/level2/endgame_solver._outcome(m, wc_tiebreak=False)` exactly.
///
/// This function stays monotone non-decreasing in `m` in EITHER reading
/// (unarmed: `0, 0.5, 1`; armed: `0, 0, 1`), which is what keeps the DESIGN
/// §2 K<=2 coincidence proposition (see [`Objective`]'s doc comment) alive
/// under the flag — see `win_and_margin_coincide_at_k2_the_inertness_proposition`
/// and its armed sibling below.
#[inline]
fn outcome(m: f64, wc_tiebreak: bool) -> f64 {
    if m > 0.0 {
        1.0
    } else if m == 0.0 {
        if wc_tiebreak {
            0.0
        } else {
            0.5
        }
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
    /// WC tie-break rule (`BACKLOG.md` 2026-08-03; verbatim source in
    /// `outcome`'s doc comment).  Default `false` == the untouched incumbent:
    /// a tied final score (`m == 0.0`) values as `0.5` (a draw), exactly as it
    /// always has.  Armed, it values as `0.0` (the WC rule: the starting
    /// player, P0, automatically loses a tie).
    ///
    /// ⚠️ Under [`Objective::Margin`] this flag is INERT BY CONSTRUCTION:
    /// margin mode never calls `outcome` (it backs up the raw score
    /// differential `m`, not the win lattice), so an armed-but-margin solve is
    /// bit-identical to an unarmed one.  This is a legitimate "armed but
    /// inert" state — e.g. the flag riding in from a process-wide rules
    /// profile that also has `Objective::Win` cells — and is deliberately NOT
    /// rejected (unlike E1's loud `Clairvoyant + Win` refusal in
    /// `endgame::Config`, which rejects a combination that is never
    /// meaningful).  [`SolveResult::wc_tiebreak`] stamps the resolved value on
    /// every solve, armed or not, objective or not, so the inert state stays
    /// VISIBLE off a result rather than silently assumed.
    pub wc_tiebreak: bool,
}

impl Default for SolverConfig {
    fn default() -> Self {
        SolverConfig {
            // `fair_agent.DEFAULT_EXACT_BUDGET`
            budget: 2_000_000,
            tt_cap: 0,
            chance_drop: ChanceDrop::Type,
            objective: Objective::Margin,
            wc_tiebreak: false,
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
    /// The RESOLVED [`SolverConfig::wc_tiebreak`] this solve ran under —
    /// stamped unconditionally (both objectives, armed or not) so the
    /// `Objective::Margin` "armed but inert" state is readable off a result
    /// instead of assumed from the caller's config.
    pub wc_tiebreak: bool,
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
            return Ok(terminal_value(g));
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
            let nb = step(g, a).map_err(SolveError::Engine)?;
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
            let m = terminal_value(g);
            return Ok((outcome(m, self.cfg.wc_tiebreak), m));
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
            let nb = step(g, a).map_err(SolveError::Engine)?;
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
        let nb = step(g, a).map_err(SolveError::Engine)?;
        let v = if nb.state.is_terminated() {
            terminal_value(&nb)
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
        // Stamped even though margin mode never calls `outcome` — the flag is
        // INERT here by construction, not absent; see `SolverConfig::wc_tiebreak`.
        wc_tiebreak: cfg.wc_tiebreak,
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
        let nb = step(g, a).map_err(SolveError::Engine)?;
        let v = if nb.state.is_terminated() {
            let m = terminal_value(&nb);
            (outcome(m, cfg.wc_tiebreak), m)
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
        wc_tiebreak: cfg.wc_tiebreak,
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
            assert_eq!(wv, outcome(m.value, false), "seed {seed}");
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
                assert_eq!(outcome(*m_child, false), *w_child, "seed {seed}");
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

    // ---- WC tie-break rule (BACKLOG.md 2026-08-03) ------------------------ //

    /// `outcome`'s full truth table, both readings, over positive / zero /
    /// negative margins.  Unarmed is the pre-flag lattice, untouched.
    #[test]
    fn outcome_truth_table_both_readings() {
        for m in [1.0, 0.5, 100.0] {
            assert_eq!(outcome(m, false), 1.0);
            assert_eq!(outcome(m, true), 1.0, "positive margin is a win either way");
        }
        assert_eq!(outcome(0.0, false), 0.5, "unarmed: a tie is a draw");
        assert_eq!(outcome(0.0, true), 0.0, "armed: a tie is a P0 loss (the WC rule)");
        for m in [-1.0, -0.5, -100.0] {
            assert_eq!(outcome(m, false), 0.0);
            assert_eq!(outcome(m, true), 0.0, "negative margin is a loss either way");
        }
    }

    /// Default-off inertness: a seeded win-mode solve with `wc_tiebreak: false`
    /// is bit-identical to `SolverConfig::default()` (which is already
    /// `wc_tiebreak: false` — this pins that constructing the field
    /// explicitly changes nothing, i.e. the field itself carries no hidden
    /// default drift).
    #[test]
    fn wc_tiebreak_false_is_bit_identical_to_default() {
        for seed in ["11", "12", "13", "14"] {
            let g = endgame(seed, 2);
            let a = solve_marginalized(&g, &win_cfg()).unwrap();
            let b = solve_marginalized(
                &g,
                &SolverConfig {
                    wc_tiebreak: false,
                    ..win_cfg()
                },
            )
            .unwrap();
            assert_eq!(a.value.to_bits(), b.value.to_bits());
            assert_eq!(a.win_value.map(f64::to_bits), b.win_value.map(f64::to_bits));
            assert_eq!(a.optimal_actions, b.optimal_actions);
            assert_eq!(a.nodes, b.nodes);
            assert!(!a.wc_tiebreak && !b.wc_tiebreak);
        }
    }

    /// Margin mode is INERT under the flag by construction: margin never
    /// calls `outcome`, so an armed margin solve is bit-identical to an
    /// unarmed one — but the result still STAMPS the armed state (visible,
    /// not silently assumed).
    #[test]
    fn wc_tiebreak_is_inert_under_margin_objective() {
        for seed in ["11", "12", "13", "14"] {
            let g = endgame(seed, 2);
            let off = solve_marginalized(&g, &SolverConfig::default()).unwrap();
            let on = solve_marginalized(
                &g,
                &SolverConfig {
                    wc_tiebreak: true,
                    ..SolverConfig::default()
                },
            )
            .unwrap();
            assert_eq!(off.value.to_bits(), on.value.to_bits(), "seed {seed}");
            assert_eq!(off.optimal_actions, on.optimal_actions, "seed {seed}");
            assert_eq!(off.nodes, on.nodes, "seed {seed}");
            assert!(!off.wc_tiebreak);
            assert!(on.wc_tiebreak, "armed state must be readable off the result");
        }
    }

    /// Armed correctness at a constructed terminal: `m == 0.0` values `0.0`
    /// armed / `0.5` unarmed (already covered by the truth table), and the
    /// lexicographic comparison orders a tie STRICTLY BELOW a win and, armed,
    /// EQUAL-TO a loss on the `w` component.
    #[test]
    fn lex_better_orders_a_tie_below_a_win_and_armed_equal_to_a_loss() {
        let win = (outcome(1.0, true), 1.0); // (1.0, 1.0)
        let tie_armed = (outcome(0.0, true), 0.0); // (0.0, 0.0)
        let tie_unarmed = (outcome(0.0, false), 0.0); // (0.5, 0.0)
        let loss = (outcome(-1.0, true), -1.0); // (0.0, -1.0)

        // A win beats an armed tie, for the maximizer.
        assert!(lex_better(win, tie_armed, true));
        assert!(!lex_better(tie_armed, win, true));
        // An unarmed tie strictly beats an armed tie (0.5 > 0.0 on the w
        // component) for the maximizer — arming the flag costs P0 real value.
        assert!(lex_better(tie_unarmed, tie_armed, true));
        // Armed, a tie's `w` (0.0) equals a loss's `w` (0.0) — lex_better
        // falls through to the margin component, where the tie's m=0.0 beats
        // the loss's m=-1.0.
        assert!((tie_armed.0 - loss.0).abs() <= WIN_TIE, "w components are equal armed");
        assert!(lex_better(tie_armed, loss, true), "same w, better m must still win");
        // For the minimizer the armed tie and the loss are equally preferred
        // on `w` (0.0 == 0.0) but the loss has the better (more negative) `m`.
        assert!(lex_better(loss, tie_armed, false));
    }

    fn win_cfg_armed() -> SolverConfig {
        SolverConfig {
            wc_tiebreak: true,
            ..win_cfg()
        }
    }

    // ---- L2: the terminal scorer swap ------------------------------------ //

    /// Every surface of a solve is bit-identical between the PRE-L2 route
    /// (scored `advance` + `GameState::flat_base_score`) and the shipped flat
    /// route, in BOTH objectives — value bits, the full optimal-action set,
    /// every child value's bits, the node count and the TT size.
    ///
    /// The randomized 500+-position gate lives in
    /// `examples/l2_solver_gate.rs`; this is the in-suite pin.
    #[test]
    fn l2_flat_terminal_route_is_bit_identical_to_the_legacy_route() {
        // k=2 over eight seeds is the deployed depth and is cheap; k=3 is
        // ~10 s/solve, so it gets ONE seed here — the genuinely chance-mixed
        // regime is covered at n=20 by `examples/l2_solver_gate.rs`.
        let cells = [
            ("11", 2usize), ("12", 2), ("13", 2), ("14", 2),
            ("15", 2), ("16", 2), ("17", 2), ("18", 2),
            ("11", 3),
        ];
        {
            for (seed, k) in cells {
                let g = endgame(seed, k);
                for cfg in [SolverConfig::default(), win_cfg()] {
                    let pre = with_legacy_terminal_scorer(|| solve_marginalized(&g, &cfg)).unwrap();
                    let post = solve_marginalized(&g, &cfg).unwrap();
                    assert_eq!(
                        pre.value.to_bits(),
                        post.value.to_bits(),
                        "seed {seed} k {k}: value bits"
                    );
                    assert_eq!(
                        pre.optimal_actions, post.optimal_actions,
                        "seed {seed} k {k}: optimal set"
                    );
                    assert_eq!(pre.nodes, post.nodes, "seed {seed} k {k}: node count");
                    assert_eq!(
                        pre.tt_entries, post.tt_entries,
                        "seed {seed} k {k}: tt entries"
                    );
                    assert_eq!(pre.child_values.len(), post.child_values.len());
                    for ((a1, v1), (a2, v2)) in
                        pre.child_values.iter().zip(post.child_values.iter())
                    {
                        assert_eq!(a1, a2, "seed {seed} k {k}: child action order");
                        assert_eq!(
                            v1.to_bits(),
                            v2.to_bits(),
                            "seed {seed} k {k}: child {a1} value bits"
                        );
                    }
                    assert_eq!(
                        pre.win_value.map(f64::to_bits),
                        post.win_value.map(f64::to_bits)
                    );
                    for ((a1, v1), (a2, v2)) in
                        pre.child_win_values.iter().zip(post.child_win_values.iter())
                    {
                        assert_eq!(a1, a2);
                        assert_eq!(v1.to_bits(), v2.to_bits());
                    }
                }
            }
        }
    }

    /// `advance_unscored` differs from `advance` ONLY at a transition that
    /// terminates the game. Every non-terminal transition must produce a
    /// byte-identical state (`state_digest` covers the repr, the legal mask,
    /// both scores and the terminal flag), and at a terminal the deferred state
    /// must still yield the SAME `flat_base_score` — which is the whole
    /// substitution's contract.
    #[test]
    fn advance_unscored_defers_only_the_terminal_scoring() {
        let mut n_terminal = 0usize;
        let mut n_nonterminal = 0usize;
        for seed in ["11", "12", "13", "14", "15", "16"] {
            // A `k_remaining <= 2` TILES root cannot terminate in ONE ply (the
            // tile placement hands off to the MEEPLES phase), so walk a bounded
            // sub-tree and test every transition in it — that is what reaches
            // both classes. The `n_terminal > 0` assertion below is what caught
            // the one-ply version of this fixture.
            let mut frontier = vec![endgame(seed, 2)];
            let mut visited = 0usize;
            while let Some(g) = frontier.pop() {
                visited += 1;
                if visited > 24 {
                    break;
                }
                for a in g.legal_actions() {
                    let mut scored = g.clone();
                    let mut deferred = g.clone();
                    scored.advance(a).unwrap();
                    deferred.advance_unscored(a).unwrap();
                    if !scored.state.is_terminated() && frontier.len() < 12 {
                        frontier.push(scored.clone());
                    }
                    assert_eq!(
                        scored.state.is_terminated(),
                        deferred.state.is_terminated(),
                        "termination must not depend on the scoring route"
                    );
                    if scored.state.is_terminated() {
                        n_terminal += 1;
                        // the deferred state has NOT been drained…
                        assert!(
                            deferred.state.placed_meeples[0].len()
                                + deferred.state.placed_meeples[1].len()
                                >= scored.state.placed_meeples[0].len()
                                    + scored.state.placed_meeples[1].len(),
                            "the deferred route must not drain meeples"
                        );
                        // …and yet both routes score it identically, by either scorer.
                        let want = scored.flat_base_score(0);
                        assert_eq!(
                            deferred.flat_base_score(0),
                            want,
                            "engine route on the deferred (un-drained) terminal"
                        );
                        assert_eq!(
                            terminal_value(&deferred) as i64,
                            want,
                            "flat route on the deferred (un-drained) terminal"
                        );
                        assert_eq!(
                            terminal_value(&scored) as i64,
                            want,
                            "flat route on the drained terminal"
                        );
                    } else {
                        n_nonterminal += 1;
                        assert_eq!(
                            scored.state_digest(),
                            deferred.state_digest(),
                            "a NON-terminal transition must be byte-identical"
                        );
                    }
                }
            }
        }
        assert!(n_terminal > 0, "the fixture must reach terminals");
        assert!(n_nonterminal > 0, "the fixture must reach non-terminals");
    }

    /// The flat route's buffers are thread-local; solving the same positions
    /// concurrently across threads must give the same answers as solving them
    /// on one thread. (L0's threading gate, at solver granularity.)
    #[test]
    fn flat_terminal_buffers_are_thread_safe() {
        let seeds = ["11", "12", "13", "14", "15", "16", "17", "18"];
        let games: Vec<Game> = seeds.iter().map(|s| endgame(s, 2)).collect();
        let cfg = SolverConfig::default();
        let single: Vec<u64> = games
            .iter()
            .map(|g| solve_marginalized(g, &cfg).unwrap().value.to_bits())
            .collect();
        let threaded: Vec<u64> = std::thread::scope(|sc| {
            let hs: Vec<_> = games
                .iter()
                .map(|g| {
                    let cfg = cfg.clone();
                    sc.spawn(move || solve_marginalized(g, &cfg).unwrap().value.to_bits())
                })
                .collect();
            hs.into_iter().map(|h| h.join().unwrap()).collect()
        });
        assert_eq!(single, threaded);
    }

    /// `with_legacy_terminal_scorer` must restore the previous setting even if
    /// the closure unwinds, or a panicking gate would leave the whole thread on
    /// the slow route.
    #[test]
    fn the_legacy_switch_is_restored_on_unwind() {
        assert!(!legacy_terminal());
        let r = std::panic::catch_unwind(|| {
            with_legacy_terminal_scorer(|| {
                assert!(legacy_terminal());
                panic!("boom");
            })
        });
        assert!(r.is_err());
        assert!(!legacy_terminal(), "the switch must not leak past an unwind");
    }

    /// The DESIGN §2 K<=2 coincidence proposition, ARMED: mirrors
    /// `win_and_margin_coincide_at_k2_the_inertness_proposition` but with
    /// `wc_tiebreak: true` on both sides — win value must equal
    /// `outcome(margin, true)`, not the unarmed lattice.
    #[test]
    fn win_and_margin_coincide_at_k2_armed() {
        for seed in ["11", "12", "13", "14", "15", "16", "17", "18"] {
            let g = endgame(seed, 2);
            let m = solve_marginalized(&g, &SolverConfig::default()).unwrap();
            let w = solve_marginalized(&g, &win_cfg_armed()).unwrap();
            assert_eq!(m.optimal_actions, w.optimal_actions, "seed {seed}");
            assert_eq!(m.value.to_bits(), w.value.to_bits(), "seed {seed}");
            let wv = w.win_value.expect("win mode must report win_value");
            assert_eq!(wv, outcome(m.value, true), "seed {seed}");
            for ((_, m_child), (_, w_child)) in
                m.child_values.iter().zip(w.child_win_values.iter())
            {
                assert_eq!(outcome(*m_child, true), *w_child, "seed {seed}");
            }
            assert!(w.wc_tiebreak);
        }
    }
}
