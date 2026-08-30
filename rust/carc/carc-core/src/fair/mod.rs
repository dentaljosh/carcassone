//! `fair` — the deployed champion: root-determinization PIMC + the one-way
//! exact latch (rustport **P4**).
//!
//! A bit-faithful port of `carcassonne_ai.fair_agent.FairHeuristicPriorAgent`
//! (`governance/PRODUCTION.yaml champion.fair_deploy`: `k_dets=8`,
//! `sims_per_det=1376`).  Each move:
//!
//! 1. **Forced-move short-circuit** — one legal action ⇒ return it, consuming
//!    NO randomness.  (It lives in the agent, not the search — P3 confirmed.)
//! 2. `k_dets` determinizations drawn SEQUENTIALLY from one
//!    `random.Random(det_seed_base + 1)`, each a copy of the board whose UNSEEN
//!    deck is canonicalized (**sorted by tile description** — the CL-056
//!    hardening) and then `random.Random.shuffle`d.  `next_tile` is untouched.
//! 3. Each world runs a FRESH [`crate::search`] tree at
//!    `seed = det_seed_base + 100 + i` (the seed is inert in the ported search —
//!    the champion draws no randomness inside a search — but it is carried so
//!    the contract is visible).
//! 4. The per-world `root_stats_list` are merged into the pooled `(N, W)`
//!    accumulators **in world order 0..k-1**, and the move is
//!    [`pooled_q_argmax`].
//!
//! ## Determinism under threading
//!
//! The k worlds are independent until the pooled argmax, so they run on
//! `std::thread::scope` over `min(k, threads)` workers — but the *merge* is a
//! sequential fold over an index-addressed result vector performed AFTER every
//! join.  Float addition is not associative, so this is what makes the answer
//! **bit-identical at any thread count**, with zero scheduler nondeterminism
//! (`tests::thread_count_invariance`, and the Python-side gate).
//!
//! Determinizations are generated sequentially and *before* any thread starts,
//! because the shared `det_rng` draw order is part of the contract.
//!
//! ## The exact latch
//!
//! On the first **TILES-phase** decision with `k_remaining <= exact_max_k` the
//! agent latches — **one-way**, turn-atomic (the boundary tile AND its meeple go
//! to the solver, never split) — and plays [`solver::solve_marginalized`] for the
//! rest of the game, `min(optimal_actions)`.  A `BudgetExceeded` solve falls back
//! to the fair PIMC move for THAT decision only; the agent stays latched.

pub mod jrules_filter;
pub mod solver;

use std::collections::HashMap;

use crate::compat::mt19937::MT19937;
use crate::engine::Phase;
use crate::game::Game;
use crate::search::{self, SearchConfig, SearchError};
use crate::tiles;

pub use jrules_filter::{
    jrules_root_filter, FilterOutcome, JF_ALL, JF_CURRENT, JF_END, JF_FILTER_NAMES, JF_J10,
    JF_J3, JF_J9,
};
pub use solver::{ChanceDrop, SolveError, SolveResult, SolverConfig};

/// `fair_agent.DEFAULT_MIN_POOLED_VISITS`.
pub const DEFAULT_MIN_POOLED_VISITS: f64 = 2.0;
/// `fair_agent.EXACT_MAX_K`.
pub const DEFAULT_EXACT_MAX_K: i64 = 2;

#[derive(Clone)]
pub struct FairConfig {
    pub search: SearchConfig,
    pub k_dets: usize,
    /// The agent's base seed (`FairHeuristicPriorAgent(seed=...)`).
    pub seed: i64,
    /// `min_pooled_visits`; compared against the pooled `N`, which the Python
    /// accumulates as a `float` (`defaultdict(float)`).
    pub min_pooled_visits: f64,
    pub exact_endgame: bool,
    pub exact_max_k: i64,
    pub solver: SolverConfig,
    /// World threads.  `1` = the sequential loop (the Android/Chaquopy path).
    /// Results are bit-identical at every value.
    pub threads: usize,
}

impl Default for FairConfig {
    fn default() -> Self {
        FairConfig {
            search: SearchConfig::default(),
            k_dets: 8,
            seed: 0,
            min_pooled_visits: DEFAULT_MIN_POOLED_VISITS,
            exact_endgame: true,
            exact_max_k: DEFAULT_EXACT_MAX_K,
            solver: SolverConfig::default(),
            threads: 1,
        }
    }
}

/// Reconcile the agent-level `wc_tiebreak` kwarg against the `wc_tiebreak`
/// already baked into a caller-supplied `search_cfg` (`PySearchConfig` on the
/// pyo3 side), for [`FairConfig`]'s two legs (`search` and `solver`) — a pure
/// function so the resolution rule is unit-testable without pyo3 or a live
/// wheel.
///
/// The agent constructor's own `wc_tiebreak` kwarg is `Option<bool>`:
///
/// - `None` (unspecified) — **inherit** `search_cfg_value`, no override at
///   all. This is the untouched-default path: a caller who never mentions the
///   flag anywhere gets `false` on both legs, byte-identical to before the
///   flag existed.
/// - `Some(w)` where `search_cfg_value == true && w == false` — this is the
///   SILENT-DISARM case: a caller explicitly armed the search leg
///   (`PySearchConfig(wc_tiebreak=True)`) and then, whether by a stale
///   default or a copy-paste, asked the agent to build with the flag OFF.
///   Silently letting the agent kwarg win would quietly disarm a leg the
///   caller deliberately armed — a wrong-rules-cell factory, the exact
///   failure class this house has been burned by repeatedly (silently-inert /
///   silently-overridden knobs). **RAISE**, don't resolve.
/// - `Some(w)` otherwise (armed-agrees, or the agent arms a leg the search
///   config left off) — resolve to `w`, applied to BOTH legs. This is the
///   normal arming path: `search_config_rs(...)` is built WITHOUT
///   `wc_tiebreak` (`false`) and the caller passes `wc_tiebreak=True` to the
///   agent only when armed — `search_cfg_value=false` + `Some(true)` must
///   resolve, not raise.
pub fn resolve_wc_tiebreak(search_cfg_value: bool, agent_kwarg: Option<bool>) -> Result<bool, String> {
    match agent_kwarg {
        None => Ok(search_cfg_value),
        Some(w) if search_cfg_value && !w => Err(format!(
            "wc_tiebreak mismatch: search_cfg was built with wc_tiebreak=True but the \
             agent constructor was called with wc_tiebreak=False — this would SILENTLY \
             DISARM the search leg's WC tie-break rule while some other leg may still \
             think it is armed. Fix by either (a) passing wc_tiebreak=True to the agent \
             too (arm both legs), or (b) omitting the agent's wc_tiebreak kwarg entirely \
             (defaults to None, which INHERITS search_cfg's value)."
        )),
        Some(w) => Ok(w),
    }
}

#[cfg(test)]
mod resolve_wc_tiebreak_tests {
    use super::resolve_wc_tiebreak;

    /// The full truth table: `None`/`Some(true)`/`Some(false)` agent kwarg ×
    /// `search_cfg_value` true/false — six cells, five resolve, one raises.
    #[test]
    fn truth_table() {
        // None (unspecified) always inherits, whatever search_cfg carries.
        assert_eq!(resolve_wc_tiebreak(false, None), Ok(false));
        assert_eq!(resolve_wc_tiebreak(true, None), Ok(true));
        // Some(w) where search_cfg is false: never a silent disarm (there is
        // nothing armed to disarm), so both resolve to w.
        assert_eq!(resolve_wc_tiebreak(false, Some(false)), Ok(false));
        assert_eq!(
            resolve_wc_tiebreak(false, Some(true)),
            Ok(true),
            "the normal arming path: search_cfg=false + Some(true) must resolve, not raise"
        );
        // Some(true) where search_cfg is already true: agrees, resolves.
        assert_eq!(resolve_wc_tiebreak(true, Some(true)), Ok(true));
        // Some(false) where search_cfg is true: the silent-disarm case — raise.
        let e = resolve_wc_tiebreak(true, Some(false)).unwrap_err();
        assert!(e.contains("wc_tiebreak=True"), "must name the search leg's value: {e}");
        assert!(e.contains("wc_tiebreak=False"), "must name the agent kwarg's value: {e}");
        assert!(e.contains("DISARM"), "must say what's dangerous about it: {e}");
    }
}

#[derive(Debug)]
pub enum FairError {
    /// `ValueError("fair agent asked to move with no legal actions")`.
    NoLegalActions,
    Search(SearchError),
    Solver(SolveError),
    Engine(String),
}

impl std::fmt::Display for FairError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FairError::NoLegalActions => {
                write!(f, "fair agent asked to move with no legal actions")
            }
            FairError::Search(e) => write!(f, "search error: {e}"),
            FairError::Solver(e) => write!(f, "solver error: {e}"),
            FairError::Engine(s) => write!(f, "engine error: {s}"),
        }
    }
}

/// `fair_agent.k_remaining(state)` — undrawn deck + the one in hand.
#[inline]
pub fn k_remaining(g: &Game) -> i64 {
    g.state.deck_len() as i64 + i64::from(g.state.next_tile.is_some())
}

/// `FairHeuristicPriorAgent.det_seed_base`.
#[inline]
pub fn det_seed_base(seed: i64, move_idx: i64) -> i64 {
    // Python ints are unbounded; the mask makes the product's high bits
    // irrelevant, but wrapping i64 arithmetic would still differ from Python for
    // absurd seeds, so do the multiply in i128 and mask.
    (((seed as i128) * 1_000_003 + (move_idx as i128) * 8191) & 0x7FFF_FFFF) as i64
}

/// `FairHeuristicPriorAgent.det_search_seed`.
#[inline]
pub fn det_search_seed(seed: i64, move_idx: i64, det_idx: usize) -> i64 {
    det_seed_base(seed, move_idx) + 100 + det_idx as i64
}

/// `FairHeuristicMCTSAgent.reshuffled_determinization`.
///
/// The unseen deck is CANONICALIZED (stable sort by tile description) BEFORE the
/// reshuffle, so the determinization is a pure function of the unseen *multiset*
/// plus the rng — invariant to the engine's unobservable TRUE deck order (the
/// 2026-07-06 fair-handoff audit, probe C).  `next_tile` is untouched.
pub fn reshuffled_determinization(base: &Game, rng: &mut MT19937) -> Result<Game, String> {
    let mut g = base.clone();
    let mut deck: Vec<u16> = g.state.remaining_deck().to_vec();
    // `list.sort(key=lambda t: t.description)` — STABLE.  (Base-tile ids are in
    // bijection with descriptions, so ties are between identical ids and the
    // stability is vacuous; `sort_by` is stable regardless.)
    deck.sort_by(|&a, &b| {
        tiles::generated::BASE_TILES[a as usize]
            .description
            .cmp(tiles::generated::BASE_TILES[b as usize].description)
    });
    rng.shuffle(&mut deck);
    g.state.set_remaining_deck(&deck)?;
    Ok(g)
}

/// The pooled `(N, W)` accumulators, in first-seen (insertion) order — the
/// Python's `defaultdict(float)` iteration order.
#[derive(Default, Clone)]
pub struct Pool {
    pub order: Vec<i32>,
    pub n: HashMap<i32, f64>,
    pub w: HashMap<i32, f64>,
}

impl Pool {
    /// `fair_agent._merge_root_stats` — THE single accumulation point.  Float
    /// addition is order-sensitive; identity across modes rests on merging
    /// worlds in the SAME order with the SAME `+=` sequence.
    pub fn merge(&mut self, stats: &[(i32, i64, f64)]) {
        for &(a, n, w) in stats {
            if !self.n.contains_key(&a) {
                self.order.push(a);
                self.n.insert(a, 0.0);
                self.w.insert(a, 0.0);
            }
            *self.n.get_mut(&a).unwrap() += n as f64;
            *self.w.get_mut(&a).unwrap() += w;
        }
    }

    pub fn is_empty(&self) -> bool {
        self.order.is_empty()
    }
}

/// `fair_agent.pooled_q_argmax` — argmax over eligible actions (pooled
/// `N >= min_visits`; fall back to ALL visited actions if none qualify) of
/// `(Q = W/N, N, -action)`.  The key is a total order (`-action` is unique), so
/// the answer does not depend on iteration order.
pub fn pooled_q_argmax(pool: &Pool, min_visits: f64) -> Option<i32> {
    if pool.is_empty() {
        return None;
    }
    let eligible: Vec<i32> = pool
        .order
        .iter()
        .copied()
        .filter(|a| pool.n[a] >= min_visits)
        .collect();
    let eligible = if eligible.is_empty() {
        pool.order.clone()
    } else {
        eligible
    };
    let key = |a: i32| -> (f64, f64, i64) { (pool.w[&a] / pool.n[&a], pool.n[&a], -(a as i64)) };
    let mut best = eligible[0];
    let mut bk = key(best);
    for &a in eligible.iter().skip(1) {
        let k = key(a);
        // `max(..., key=...)` keeps the FIRST maximum; the key is a strict total
        // order here, so ">" is exactly Python's tuple comparison.
        if k.0 > bk.0 || (k.0 == bk.0 && (k.1 > bk.1 || (k.1 == bk.1 && k.2 > bk.2))) {
            bk = k;
            best = a;
        }
    }
    Some(best)
}

/// Per-move telemetry — the manifest-parity surface.
#[derive(Default, Clone, Debug)]
pub struct MoveInfo {
    pub move_idx: i64,
    pub action: i32,
    /// `True` when the exact solver owned this decision.
    pub exact: bool,
    /// `True` when the agent was latched at entry (whether or not the solve
    /// completed).
    pub latched: bool,
    /// `True` on the forced-move short-circuit (no RNG consumed, no search run).
    pub forced: bool,
    /// `True` when the solve blew its budget and the move fell back to PIMC.
    pub timeout: bool,
    pub solver_nodes: u64,
    pub solver_value: Option<f64>,
    pub solver_optimal: Vec<i32>,
    pub secs: f64,
    /// `agg_n` / `agg_w` in insertion order — the raw pooled floats the gate
    /// compares bit-for-bit.
    pub pooled: Vec<(i32, f64, f64)>,
    pub k_remaining: i64,
    /// The per-world sims budget the PIMC search actually ran (0 when no search
    /// ran: forced move or a completed exact solve). Equals
    /// `cfg.search.simulations` unless a per-call override was passed — the
    /// sims-split knob's per-move evidence surface.
    pub sims_used: usize,
    /// S1 §9.2(c) `R7`: the J-rules-prior expansion census of THIS decision,
    /// summed over its `k_dets` determinized worlds. All-zero on champion
    /// traffic (`jrules_prior_dose == 0.0`) — see [`search::JrExpansions`].
    pub jr_expansions: search::JrExpansions,
    /// Surface C: root actions the J-rules filter removed at THIS decision
    /// (empty when the mask is 0, the phase is TILES, or nothing fired).
    pub jf_dropped: Vec<i32>,
    /// Surface C, per filter `[F-END, F-J10, F-J9, F-J3]`: really bit here.
    pub jf_fires: [bool; 4],
    /// Surface C, per filter: the never-empty guard blocked a real bite here.
    pub jf_yields: [bool; 4],
    /// TIE ARBITER: the trigger fired at this decision (all-false / empty when
    /// `tiearb_enabled` is off — the knob-off path never even looks).
    pub tiearb_fired: bool,
    /// The arm set actually arbitrated (`arms[0]` = the leaf tie-break of
    /// record; the champion's own pick appended if the cap excluded it).
    pub tiearb_arms: Vec<i32>,
    /// The champion's own `pooled_q_argmax` pick at this decision — what the
    /// arbiter overrode, or agreed with.
    pub tiearb_champ_pick: i32,
    /// The returned action differs from `tiearb_champ_pick`.
    pub tiearb_pickchange: bool,
    /// `arms x B` playouts spent here.
    pub tiearb_playouts: usize,
    /// Wall-clock the arbiter added to this decision.
    pub tiearb_secs: f64,
}

/// `FairHeuristicPriorAgent`.
pub struct FairAgent {
    pub cfg: FairConfig,
    pub move_idx: i64,
    pub latched: bool,
    pub latch_k: Option<i64>,
    // `eval_hybrid_handoff` harness-compatible instrumentation.
    pub heur_moves: u64,
    pub exact_moves: u64,
    pub n_timeouts: u64,
    pub solver_nodes: u64,
    pub solver_secs: f64,
    pub max_solve_secs: f64,
    pub forced_moves: u64,
    /// `last_pooled_visits`: `{a: 1.0}` on a forced move, `{}` on an exact
    /// decision, else `dict(agg_n)`.
    pub last_pooled_visits: Vec<(i32, f64)>,
    pub last_move: MoveInfo,
    /// Surface C cumulative counters, `[F-END, F-J10, F-J9, F-J3]`: decisions
    /// where the filter really bit. All-zero whenever
    /// `cfg.search.jrules_filter_mask == 0` (the champion).
    pub jf_fires: [u64; 4],
    /// Surface C: decisions where the never-empty guard blocked a real bite.
    pub jf_yields: [u64; 4],
    /// Surface C: total root actions removed across the game — the cell-level
    /// positive control (a live-mask game with 0 here never fired the filter).
    pub jf_dropped_total: u64,
    /// Surface C: PIMC decisions on which the filter was APPLICABLE (meeple
    /// phase, >1 legal, mask nonzero) — the yield/fire rates' denominator.
    pub jf_applicable_moves: u64,
    /// ⭐ S1 §9.2(c) `R7` (merge review 2026-08-30): the J-rules-prior
    /// EXPANSION CENSUS accumulated over every PIMC world of every decision
    /// this agent made — i.e. per GAME, since the harness builds one agent per
    /// game (`scripts/classical_search/eval_fair_puct.py::_play_one_inner`).
    ///
    /// ⛔ THE ONLY WITNESS, derived from PLAY rather than from config, that a
    /// `jrules_prior_scope` arm actually BOUND. A manifest echo proves the knob
    /// was requested and nothing more; this program has twice banked a cell
    /// whose knob never bound (the FPU knob, the phasegate smoke). On a scoped
    /// cell `boosted > 0` is the liveness bit and
    /// `boosted == total - own_mover` (scope=opp) / `boosted == own_mover`
    /// (scope=own) is the partition bit.
    ///
    /// All-zero on champion traffic — the per-tree counters live inside the
    /// `jrules_prior_dose != 0.0` branch, so an UNARMED side's assertable
    /// invariant is `boosted == 0`, never `total > 0`.
    pub jr_expansions: search::JrExpansions,
    /// The arbiter's leaf scratch — reused across decisions so the detector is
    /// allocation-lean (`Sum_a (1 + n_meeple(a))` leaf calls per tile ply).
    /// Untouched, and never even read, when the knob is off.
    tiearb_scratch: crate::leaf::LeafScratch,
    // --- TIE ARBITER (tiearb2 Stage 2 Phase B) cumulative counters. All zero
    // whenever `cfg.search.tiearb_enabled` is false (the champion). These are
    // the READ_RULE §2 `phi` numerator/denominator and the §4.3 pick-change
    // witness; nothing else on this surface can prove the knob live.
    /// PIMC TILE decisions with >= 2 legal actions — the plies at which the
    /// trigger was even evaluated (`phi`'s cheap denominator).
    pub tiearb_tile_plies: u64,
    /// Decisions where the trigger FIRED and the arbiter ran (`phi`'s
    /// numerator; `G-FIRE` voids the cell below 1.0 per game).
    pub tiearb_fired_plies: u64,
    /// ⭐ PER-PHASE fired plies, bucketed by [`crate::tiearb::phase_bucket`] of
    /// `k_remaining` at the fired ply (`measurement/phasegate_prep/DESIGN.md`
    /// §7.2). ⛔ `G-PHI`'s address, and the ONLY witness of the gate that is
    /// derived from PLAY rather than from config: on a `phase_gate = early`
    /// cell `mid` and `late` must be 0 and `early` > 0; on `all` the three sum
    /// to [`Self::tiearb_fired_plies`]; on `none` all four are 0.
    ///
    /// ⭐ They also measure the round's own deduped per-phase fired split,
    /// which `DESIGN.md` §6.2 could only PROXY (the banked
    /// `tile_gap_rows.jsonl` carries no repr-dedup column, so the true split is
    /// unrecoverable from disk). `[early, mid, late]`.
    pub tiearb_fired_by_phase: [u64; 3],
    /// Fired decisions where the returned action differs from the champion's
    /// own `pooled_q_argmax` pick.
    pub tiearb_pickchanges: u64,
    /// [`Self::tiearb_pickchanges`] bucketed the same way. `[early, mid, late]`.
    pub tiearb_pickchanges_by_phase: [u64; 3],
    /// Total arms arbitrated (the runtime analogue of the corpus `Ā` = 3.0022).
    pub tiearb_arms_total: u64,
    /// Total `tier1-greedy` playouts spent by the arbiter.
    pub tiearb_playouts_total: u64,
    /// Total wall-clock the arbiter added (the in-cell half of `ms_ratio`).
    pub tiearb_secs: f64,
    /// Plies where the arbiter ERRORED and the champion's own pick stood. A
    /// deep `tier1-greedy` continuation in a determinized world can hit the
    /// engine's window refusal or the ply ceiling; that must not kill the game
    /// (a candidate-correlated exclusion is invisible in the elo), so it falls
    /// back and is counted here. Nonzero is REPORTABLE, not fatal.
    pub tiearb_errors: u64,
    /// The first such error's message, kept so a nonzero count is diagnosable
    /// without a re-run.
    pub tiearb_first_error: Option<String>,
    /// READ_RULE §0.F `G-PLY`: plies where an argmax was taken over FEWER than
    /// `B` completed worlds. ⚠️ It is **0 by construction** — [`crate::tiearb::
    /// arbitrate`] propagates the first playout error with `?`, so a partial
    /// world set never reaches the argmax and the whole ply reverts to the
    /// champion's own pick instead. This counter exists because *a condition no
    /// gate can see is not a condition*: a partial-world argmax would silently
    /// break the CRN pairing across arms, which is the entire basis of the
    /// ARB-vs-RND comparison, and nothing else in the run would show it.
    /// **Non-zero (or absent) ⇒ `U-UNREADABLE`.**
    pub tiearb_partial_argmax: u64,
}

impl FairAgent {
    pub fn new(cfg: FairConfig) -> Self {
        FairAgent {
            cfg,
            move_idx: 0,
            latched: false,
            latch_k: None,
            heur_moves: 0,
            exact_moves: 0,
            n_timeouts: 0,
            solver_nodes: 0,
            solver_secs: 0.0,
            max_solve_secs: 0.0,
            forced_moves: 0,
            last_pooled_visits: Vec::new(),
            last_move: MoveInfo::default(),
            jf_fires: [0; 4],
            jf_yields: [0; 4],
            jf_dropped_total: 0,
            jf_applicable_moves: 0,
            jr_expansions: search::JrExpansions::default(),
            tiearb_scratch: crate::leaf::LeafScratch::new(),
            tiearb_tile_plies: 0,
            tiearb_fired_plies: 0,
            tiearb_fired_by_phase: [0; 3],
            tiearb_pickchanges: 0,
            tiearb_pickchanges_by_phase: [0; 3],
            tiearb_arms_total: 0,
            tiearb_playouts_total: 0,
            tiearb_secs: 0.0,
            tiearb_errors: 0,
            tiearb_first_error: None,
            tiearb_partial_argmax: 0,
        }
    }

    /// `choose_action(board)`.  `move_idx` is the agent's own counter; pass
    /// `None` to use it, or an explicit value when a harness owns the timeline.
    pub fn choose_action(&mut self, g: &Game, move_idx: Option<i64>) -> Result<i32, FairError> {
        self.choose_action_with_sims(g, move_idx, None)
    }

    /// [`Self::choose_action`] with a PER-CALL per-world sims override — the
    /// play-time seam for the phase-asymmetric sims split (`sims_tile` /
    /// `sims_meeple`). `None` is byte-for-byte `choose_action` (the same code
    /// path, not a parallel one).
    ///
    /// DESIGN: a per-call override rather than a config-swap setter, for two
    /// reasons. (1) STATELESS — `self.cfg` is never mutated, so `stats()`
    /// keeps reporting the constructed budget, `reset()` (which clones `cfg`
    /// into a fresh agent) cannot carry a leaked override into the next game,
    /// and there is no "forgot to swap back" failure mode between decisions.
    /// (2) MIRROR-SAFE BY CONSTRUCTION — the override touches only the
    /// `SearchConfig` handed to this move's world searches; the game mirror,
    /// the latch, the determinization RNG stream and the pooled merge are the
    /// untouched production code, so no override sequence can desync the
    /// mirror protocol. The override does NOT reach the exact solver or the
    /// forced-move short-circuit (neither consumes sims).
    pub fn choose_action_with_sims(
        &mut self,
        g: &Game,
        move_idx: Option<i64>,
        sims_override: Option<usize>,
    ) -> Result<i32, FairError> {
        let mi = move_idx.unwrap_or(self.move_idx);
        self.move_idx = mi + 1;
        let t0 = std::time::Instant::now();
        let mut info = MoveInfo {
            move_idx: mi,
            k_remaining: k_remaining(g),
            ..MoveInfo::default()
        };

        if self.cfg.exact_endgame && !self.latched {
            let k = k_remaining(g);
            // Latch only on a TILES decision (turn-atomic); one-way, because
            // k_remaining is monotone non-increasing.
            if g.state.phase == Phase::Tiles && k <= self.cfg.exact_max_k {
                self.latched = true;
                self.latch_k = Some(k);
            }
        }
        info.latched = self.latched;

        if self.latched {
            let ts = std::time::Instant::now();
            match solver::solve_marginalized(g, &self.cfg.solver) {
                Ok(res) => {
                    let dt = ts.elapsed().as_secs_f64();
                    self.solver_secs += dt;
                    if dt > self.max_solve_secs {
                        self.max_solve_secs = dt;
                    }
                    self.solver_nodes += res.nodes;
                    self.exact_moves += 1;
                    // `int(min(res.optimal_actions))`
                    let a = *res.optimal_actions.iter().min().expect("non-empty optimal set");
                    self.last_pooled_visits = Vec::new(); // value-only row
                    info.exact = true;
                    info.action = a;
                    info.solver_nodes = res.nodes;
                    info.solver_value = Some(res.value);
                    info.solver_optimal = res.optimal_actions;
                    info.secs = t0.elapsed().as_secs_f64();
                    self.last_move = info;
                    return Ok(a);
                }
                Err(SolveError::BudgetExceeded) => {
                    self.solver_secs += ts.elapsed().as_secs_f64();
                    self.n_timeouts += 1;
                    info.timeout = true;
                    // fall through to the fair PIMC move for THIS decision only
                }
                Err(e) => return Err(FairError::Solver(e)),
            }
        }

        let a = self.pimc_move(g, mi, &mut info, sims_override)?;
        info.action = a;
        info.secs = t0.elapsed().as_secs_f64();
        self.last_move = info;
        Ok(a)
    }

    fn pimc_move(
        &mut self,
        g: &Game,
        move_idx: i64,
        info: &mut MoveInfo,
        sims_override: Option<usize>,
    ) -> Result<i32, FairError> {
        self.heur_moves += 1;
        let legal = g.legal_actions();
        if legal.is_empty() {
            return Err(FairError::NoLegalActions);
        }
        if legal.len() == 1 {
            // Forced move: skip the K searches — and, critically, consume NO
            // randomness (`det_rng` is not even constructed).
            self.forced_moves += 1;
            self.last_pooled_visits = vec![(legal[0], 1.0)];
            info.forced = true;
            return Ok(legal[0]);
        }
        // J-RULES ROOT FILTER surface C — mask 0 (the default, the champion)
        // never calls into the filter module at all, so default traffic is
        // bit-identical, not merely equal. Nonzero: the bot's hard filters run
        // ONCE on the TRUE root (fair information only, no RNG consumed —
        // placement before the det_rng construction below is therefore
        // inert), and the surviving candidate set restricts every world
        // search's ROOT expansion. The never-empty guard lives inside
        // `jrules_root_filter` (min_keep); a filter that would leave fewer
        // than min_keep candidates yields for this ply and the yield is
        // counted.
        let mut root_allow: Option<Vec<i32>> = None;
        if self.cfg.search.jrules_filter_mask != 0 {
            let fo = jrules_filter::jrules_root_filter(
                g,
                self.cfg.search.jrules_filter_mask,
                self.cfg.search.jrules_filter_min_keep,
            )
            .map_err(FairError::Engine)?;
            if fo.applicable {
                self.jf_applicable_moves += 1;
            }
            for i in 0..4 {
                if fo.fires[i] {
                    self.jf_fires[i] += 1;
                }
                if fo.yields[i] {
                    self.jf_yields[i] += 1;
                }
            }
            self.jf_dropped_total += fo.dropped.len() as u64;
            info.jf_dropped = fo.dropped.clone();
            info.jf_fires = fo.fires;
            info.jf_yields = fo.yields;
            if !fo.dropped.is_empty() {
                root_allow = Some(fo.kept);
            }
        }

        let base = det_seed_base(self.cfg.seed, move_idx);
        let mut det_rng = MT19937::from_py_int_seed_i64(base + 1);

        // (1) determinizations, SEQUENTIALLY (the shared rng's draw order is
        //     part of the contract), all before any thread starts.
        let mut worlds: Vec<Game> = Vec::with_capacity(self.cfg.k_dets);
        for _ in 0..self.cfg.k_dets {
            worlds.push(reshuffled_determinization(g, &mut det_rng).map_err(FairError::Engine)?);
        }

        // (2) k world searches, index-addressed.  A per-call sims override swaps
        //     ONLY the simulation budget of this move's SearchConfig; everything
        //     else (leaf, priors, selection, threads, merge order) is the
        //     baked config.  `None` borrows the baked config itself — the
        //     pre-override code path, byte for byte.
        let scfg_owned = sims_override.map(|s| {
            let mut c = self.cfg.search.clone();
            c.simulations = s;
            c
        });
        let scfg = scfg_owned.as_ref().unwrap_or(&self.cfg.search);
        info.sims_used = scfg.simulations;
        let (stats, jr_census) =
            search_worlds(&worlds, scfg, self.cfg.threads, root_allow.as_deref())?;
        // S1 §9.2(c) `R7`: bank the decision's census on the move record AND on
        // the game total BEFORE any of the early returns below — a decision
        // that pooled nothing, or that the arbiter later re-decided, still
        // performed the expansions the witness is counting.
        info.jr_expansions = jr_census;
        self.jr_expansions.add(jr_census);

        // (3) merge — a sequential fold in world order, AFTER every join.
        let mut pool = Pool::default();
        for s in &stats {
            pool.merge(s);
        }

        if pool.is_empty() {
            // pathological: nothing visited. Fall back inside the FILTERED set
            // when a root filter is live (legal[0] could be a dropped action).
            self.last_pooled_visits = Vec::new();
            return Ok(match &root_allow {
                Some(kept) => kept[0],
                None => legal[0],
            });
        }
        self.last_pooled_visits = pool.order.iter().map(|&a| (a, pool.n[&a])).collect();
        info.pooled = pool
            .order
            .iter()
            .map(|&a| (a, pool.n[&a], pool.w[&a]))
            .collect();
        let champ_pick =
            pooled_q_argmax(&pool, self.cfg.min_pooled_visits).expect("pool is non-empty");

        // TIE ARBITRATION (tiearb2 Stage 2 Phase B) — the root hook, placed
        // AFTER `pooled_q_argmax` because the champion's own pick is an INPUT
        // (it is appended to the arm set when the cap excluded it, and it is
        // the pick-change baseline). `tiearb_enabled == false` (the default,
        // the champion) returns here without touching `crate::tiearb` at all,
        // so the default path is byte-identical, not merely equal — the
        // surface-C `root_allow` invariant.
        if !self.cfg.search.tiearb_enabled {
            return Ok(champ_pick);
        }
        // ⭐ THE PHASE FIRE-GATE (`measurement/phasegate_prep/DESIGN.md` §7.2).
        // A gated-out ply returns the champion's own pick down the SAME single
        // branch as `tiearb_enabled == false` above — `crate::tiearb` is never
        // touched and no counter moves, so `phase_gate = none` is the champion
        // byte for byte and `phase_gate = all` short-circuits inside
        // `fires_at` without even reading the deck.
        //
        // ⛔ `crate::fair::k_remaining(g)` — undrawn deck PLUS the tile in hand
        // — is the census axis. NEVER `g.state.deck_len()`
        // (`search/window_diag.rs:156`), which omits the tile in hand and is
        // off by one against every artefact keyed on `phase_bucket`.
        if !self.cfg.search.tiearb_phase_gate.fires_at(k_remaining(g)) {
            return Ok(champ_pick);
        }
        self.tiearb_arbitrate(g, move_idx, info, champ_pick)
    }

    /// The arbitration half of [`Self::pimc_move`], split out so the knob-off
    /// path above is a single branch. Reached ONLY when the knob is on.
    fn tiearb_arbitrate(
        &mut self,
        g: &Game,
        move_idx: i64,
        info: &mut MoveInfo,
        champ_pick: i32,
    ) -> Result<i32, FairError> {
        info.tiearb_champ_pick = champ_pick;
        if g.state.phase == Phase::Tiles {
            self.tiearb_tile_plies += 1;
        }
        let t0 = std::time::Instant::now();
        let s = &self.cfg.search;
        let result = crate::tiearb::arbitrate_decision(
            g,
            champ_pick,
            &s.leaf,
            s.tiearb_b,
            s.tiearb_j,
            &s.tiearb_salt,
            s.tiearb_eps,
            move_idx,
            s.tiearb_mode,
            s.tiearb_max_plies,
            s.tiearb_threads,
            &mut self.tiearb_scratch,
        );
        // ⚠️ FAIL SOFT, AND COUNT IT. The arbiter introduces a failure mode the
        // champion does not have: a `tier1-greedy` continuation runs deep into a
        // DETERMINIZED world and can hit the engine's all-legal-actions-outside-
        // the-window refusal (the window-truncation family) or the ply ceiling.
        // Propagating that would kill the GAME, and a game-level exclusion here
        // would be CANDIDATE-CORRELATED — the capoff pattern, where the missing
        // games were exactly the ones the candidate's own style drove into the
        // wall, and the loss is invisible in the elo. So: the champion's own
        // `pooled_q_argmax` pick stands for that ply, the error is COUNTED, and
        // the first message is kept. It cannot hide (`tiearb_errors` rides in
        // `stats()` beside the firing rate), and it is symmetric across the two
        // cells by construction — `ARB` and `RND` run the identical playouts on
        // the identical worlds, so they fail on the identical plies and `D` is
        // unaffected.
        let outcome = match result {
            Ok(o) => o,
            Err(e) => {
                self.tiearb_errors += 1;
                if self.tiearb_first_error.is_none() {
                    self.tiearb_first_error = Some(e);
                }
                self.tiearb_secs += t0.elapsed().as_secs_f64();
                return Ok(champ_pick);
            }
        };
        let dt = t0.elapsed().as_secs_f64();
        self.tiearb_secs += dt;
        info.tiearb_secs = dt;
        match outcome {
            None => Ok(champ_pick),
            Some((arms, out)) => {
                // READ_RULE §0.F `G-PLY`: assert the whole-ply property rather
                // than assume it. `arbitrate` cannot return Ok with a partial
                // world set, so this must never fire — which is exactly why it
                // is worth counting.
                if out.worlds_completed != self.cfg.search.tiearb_b {
                    self.tiearb_partial_argmax += 1;
                }
                self.tiearb_fired_plies += 1;
                // ⭐ PER-PHASE fire counters — the same `k_remaining` the gate
                // itself read one frame up, bucketed by the canonical census
                // axis. Free (one deck read), and it is what makes DESIGN
                // §6.2's biased proxy self-correcting: `ARB_FULL` measures its
                // own deduped per-phase fired split as a by-product.
                let ph = crate::tiearb::phase_bucket(k_remaining(g));
                let pi = match ph {
                    "early" => 0,
                    "mid" => 1,
                    _ => 2,
                };
                self.tiearb_fired_by_phase[pi] += 1;
                self.tiearb_arms_total += arms.arms.len() as u64;
                self.tiearb_playouts_total += out.n_playouts as u64;
                let changed = out.chosen != champ_pick;
                if changed {
                    self.tiearb_pickchanges += 1;
                    self.tiearb_pickchanges_by_phase[pi] += 1;
                }
                info.tiearb_fired = true;
                info.tiearb_arms = arms.arms;
                info.tiearb_pickchange = changed;
                info.tiearb_playouts = out.n_playouts;
                Ok(out.chosen)
            }
        }
    }
}

/// Search `worlds` on `min(worlds.len(), threads)` scoped threads and return the
/// per-world [`search::Searcher::root_stats`], **index-addressed**, together
/// with the S1 §9.2(c) J-rules expansion census SUMMED over the worlds.
///
/// The only thing threads change is when work happens: results are written into
/// disjoint slots and never combined here, so the caller's sequential fold sees
/// the identical sequence of `f64` additions at every thread count.  The census
/// is folded in WORLD ORDER after every join for the same reason, even though
/// `u64` addition could not care (`R7`, merge review 2026-08-30).
/// `root_allow` (surface C, `None` = the champion, byte-for-byte): a ROOT-only
/// action allowlist applied identically to every world — see
/// [`search::Searcher::search_with_root_allow`].
///
/// ⚠️ R7: the census is the arm's only PLAY-DERIVED witness. A per-world
/// [`search::SearchResult`] carried it already, but this function used to drop
/// it on the floor, so a `jrules_prior_scope` cell could only ever prove its
/// config echo — the failure mode that burned the FPU knob and the phasegate
/// smoke. It is [`search::JrExpansions::default()`] on champion traffic.
pub fn search_worlds(
    worlds: &[Game],
    cfg: &SearchConfig,
    threads: usize,
    root_allow: Option<&[i32]>,
) -> Result<(Vec<Vec<(i32, i64, f64)>>, search::JrExpansions), FairError> {
    type World = (Vec<(i32, i64, f64)>, search::JrExpansions);
    let k = worlds.len();
    let mut out: Vec<Result<World, SearchError>> = Vec::with_capacity(k);
    for _ in 0..k {
        out.push(Ok((Vec::new(), search::JrExpansions::default())));
    }
    let n_workers = threads.clamp(1, k.max(1));
    if k == 0 {
        return Ok((Vec::new(), search::JrExpansions::default()));
    }
    let one = |g: &Game| -> Result<World, SearchError> {
        search::Searcher::new(cfg)
            .search_with_root_allow(g, root_allow)
            .map(|r| {
                let jr = search::JrExpansions::of(&r);
                (r.pooled_stats, jr)
            })
    };
    if n_workers == 1 {
        for (i, g) in worlds.iter().enumerate() {
            out[i] = one(g);
        }
    } else {
        // ceil(k / workers) contiguous worlds per worker — the Python chunking.
        let per = k.div_ceil(n_workers);
        let one = &one;
        std::thread::scope(|s| {
            for (win, wout) in worlds.chunks(per).zip(out.chunks_mut(per)) {
                s.spawn(move || {
                    for (g, o) in win.iter().zip(wout.iter_mut()) {
                        *o = one(g);
                    }
                });
            }
        });
    }
    let joined = out
        .into_iter()
        .collect::<Result<Vec<World>, _>>()
        .map_err(FairError::Search)?;
    let mut stats = Vec::with_capacity(joined.len());
    let mut census = search::JrExpansions::default();
    for (s, jr) in joined {
        stats.push(s);
        census.add(jr);
    }
    Ok((stats, census))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::search::JrPriorScope;

    fn cfg(k: usize, sims: usize, threads: usize) -> FairConfig {
        FairConfig {
            search: SearchConfig {
                simulations: sims,
                ..SearchConfig::default()
            },
            k_dets: k,
            seed: 101,
            threads,
            ..FairConfig::default()
        }
    }

    fn midgame(seed: &str, plies: usize) -> Game {
        let mut g = Game::from_seed(seed);
        for _ in 0..plies {
            let legal = g.legal_actions();
            g.advance(legal[legal.len() / 2]).unwrap();
        }
        g
    }

    /// The gate's thread-invariance leg, in-crate: bit-identical pooled floats
    /// and identical actions at threads = 1, 4, 8.
    #[test]
    fn thread_count_invariance() {
        let g = midgame("28000000000", 40);
        let mut ref_pooled: Option<Vec<(i32, f64, f64)>> = None;
        let mut ref_action = 0;
        for t in [1usize, 4, 8] {
            let mut a = FairAgent::new(cfg(8, 64, t));
            let act = a.choose_action(&g, Some(7)).unwrap();
            let pooled = a.last_move.pooled.clone();
            match &ref_pooled {
                None => {
                    ref_pooled = Some(pooled);
                    ref_action = act;
                }
                Some(r) => {
                    assert_eq!(act, ref_action, "action differs at threads={t}");
                    assert_eq!(r.len(), pooled.len(), "pool size differs at threads={t}");
                    for (x, y) in r.iter().zip(pooled.iter()) {
                        assert_eq!(
                            (x.0, x.1.to_bits(), x.2.to_bits()),
                            (y.0, y.1.to_bits(), y.2.to_bits()),
                            "pooled floats differ at threads={t}"
                        );
                    }
                }
            }
        }
    }

    /// ⭐ S1 §9.2(c) `R7` (merge review 2026-08-30) — THE PLAY-DERIVED WITNESS,
    /// at the level a CELL reads it.
    ///
    /// `search::tests::s1_*` already pin the partition inside ONE tree. What R7
    /// found missing is everything after that: [`search_worlds`] dropped the
    /// per-world census on the floor and [`FairAgent`] never accumulated it, so
    /// a played `jrules_prior_scope` cell had no witness but its own manifest
    /// config echo — the failure mode that burned the FPU knob and the
    /// phasegate smoke.
    ///
    /// So this asserts the identity ON THE FOLD: summed over `k_dets` worlds
    /// per decision and over the decisions of a game, which is the number that
    /// reaches `summary.json`.
    #[test]
    fn s1_jr_expansion_census_folds_over_worlds_and_decisions() {
        let scoped = |dose: f64, scope, threads| {
            let mut c = cfg(4, 256, threads);
            c.search.jrules_prior_dose = dose;
            c.search.jrules_prior_scope = scope;
            c
        };
        let root = midgame("28000000000", 30);
        // Play a short prefix and return (game total, sum of the per-decision
        // records) — the two must agree, or `last_move` and `stats()` would
        // tell a cell two different stories.
        let play = |dose, scope, threads| {
            let mut a = FairAgent::new(scoped(dose, scope, threads));
            let mut g = root.clone();
            let mut per_move = search::JrExpansions::default();
            for i in 0..2i64 {
                let act = a.choose_action(&g, Some(i)).unwrap();
                per_move.add(a.last_move.jr_expansions);
                g.advance(act).unwrap();
            }
            (a.jr_expansions, per_move)
        };

        for scope in [JrPriorScope::All, JrPriorScope::Own, JrPriorScope::Opp] {
            let (game, per_move) = play(1.0, scope, 1);
            assert_eq!(
                game, per_move,
                "{scope:?}: the game total and the per-decision records disagree"
            );
            // Liveness: the arm BOUND, on play rather than on config.
            assert!(
                game.boosted > 0,
                "{scope:?}: the fold reports ZERO boosted expansions — a scoped \
                 cell with this census is unwitnessed, not null"
            );
            // The partition, summed (it survives summation term by term).
            let expect = match scope {
                JrPriorScope::All => game.total,
                JrPriorScope::Own => game.own_mover,
                JrPriorScope::Opp => game.total - game.own_mover,
            };
            assert_eq!(game.boosted, expect, "{scope:?}: partition identity broken");
            // Non-vacuity: both halves non-empty, or the identity is trivial.
            assert!(
                game.own_mover > 0 && game.total > game.own_mover,
                "{scope:?}: the expansion population is one-sided (own {} of {})",
                game.own_mover,
                game.total
            );
        }

        // The champion: the counters live inside the dose branch, so an UNARMED
        // side reports all-zero. Its assertable invariant is `boosted == 0` —
        // NEVER `total > 0`, which is what a gate would wrongly demand of the
        // opponent side of a G3 cell.
        let (champ, champ_moves) = play(0.0, JrPriorScope::All, 1);
        assert_eq!(champ, search::JrExpansions::default());
        assert_eq!(champ_moves, search::JrExpansions::default());

        // Thread-invariance, the same leg `thread_count_invariance` runs on the
        // pooled floats: the fold is over disjoint per-world counts, so the
        // census must not move with the worker count.
        let (t1, _) = play(1.0, JrPriorScope::Opp, 1);
        let (t4, _) = play(1.0, JrPriorScope::Opp, 4);
        assert_eq!(t1, t4, "the census moved with the thread count");
    }

    /// Determinizations are a pure function of (unseen multiset, rng) — NOT of
    /// the engine's true deck order (the CL-056 hardening).
    #[test]
    fn determinization_is_invariant_to_the_true_deck_order() {
        let g = midgame("42", 30);
        let mut shuffled = g.clone();
        let mut d: Vec<u16> = shuffled.state.remaining_deck().to_vec();
        d.reverse();
        shuffled.state.set_remaining_deck(&d).unwrap();

        let mut r1 = MT19937::from_py_int_seed_i64(1234);
        let mut r2 = MT19937::from_py_int_seed_i64(1234);
        let a = reshuffled_determinization(&g, &mut r1).unwrap();
        let b = reshuffled_determinization(&shuffled, &mut r2).unwrap();
        assert_eq!(a.state.remaining_deck(), b.state.remaining_deck());
    }

    /// A forced move must consume NO randomness and run NO search.
    #[test]
    fn a_forced_move_short_circuits() {
        let g = Game::from_seed("1"); // the empty board offers one placement
        assert_eq!(g.legal_actions().len(), 1);
        let mut a = FairAgent::new(cfg(8, 1376, 4));
        let t = std::time::Instant::now();
        let act = a.choose_action(&g, Some(0)).unwrap();
        assert_eq!(act, g.legal_actions()[0]);
        assert!(a.last_move.forced);
        assert!(t.elapsed().as_secs_f64() < 0.5, "a forced move searched");
        assert_eq!(a.last_pooled_visits, vec![(act, 1.0)]);
    }

    /// The latch is one-way and fires only on a TILES decision.
    #[test]
    fn the_latch_is_one_way_and_tiles_only() {
        let mut g = Game::from_seed("11");
        let mut a = FairAgent::new(cfg(2, 16, 1));
        let mut latch_phase = None;
        let mut exact_seen = 0;
        while !g.is_terminal() {
            let act = a.choose_action(&g, None).unwrap();
            if a.latched && latch_phase.is_none() {
                latch_phase = Some(g.state.phase);
            }
            if a.last_move.exact {
                exact_seen += 1;
            }
            g.advance(act).unwrap();
        }
        assert_eq!(latch_phase, Some(Phase::Tiles), "latched off a TILES decision");
        assert!(exact_seen > 0, "the solver never played");
        assert!(a.latch_k.unwrap() <= DEFAULT_EXACT_MAX_K);
    }

    /// `choose_action` must be byte-for-byte `choose_action_with_sims(.., None)`
    /// (the delegation contract), and a `None` override must record the baked
    /// budget in `sims_used`.
    #[test]
    fn sims_override_none_is_the_plain_path() {
        let g = midgame("28000000000", 40);
        let mut a = FairAgent::new(cfg(4, 48, 2));
        let mut b = FairAgent::new(cfg(4, 48, 2));
        let act_a = a.choose_action(&g, Some(7)).unwrap();
        let act_b = b.choose_action_with_sims(&g, Some(7), None).unwrap();
        assert_eq!(act_a, act_b);
        assert_eq!(a.last_move.sims_used, 48);
        assert_eq!(b.last_move.sims_used, 48);
        for (x, y) in a.last_move.pooled.iter().zip(b.last_move.pooled.iter()) {
            assert_eq!(
                (x.0, x.1.to_bits(), x.2.to_bits()),
                (y.0, y.1.to_bits(), y.2.to_bits())
            );
        }
    }

    /// An override of S must be bit-identical to an agent CONSTRUCTED at S —
    /// and must leave the agent's own config untouched (statelessness): the
    /// next un-overridden call runs the baked budget again.
    #[test]
    fn sims_override_equals_a_baked_config_and_is_stateless() {
        let g = midgame("28000000000", 40);
        let mut over = FairAgent::new(cfg(4, 64, 2)); // baked 64, overridden to 24
        let mut baked = FairAgent::new(cfg(4, 24, 2)); // baked 24
        let act_o = over.choose_action_with_sims(&g, Some(7), Some(24)).unwrap();
        let act_b = baked.choose_action(&g, Some(7)).unwrap();
        assert_eq!(act_o, act_b, "override(24) != baked 24");
        assert_eq!(over.last_move.sims_used, 24);
        assert_eq!(
            over.last_move.pooled.len(),
            baked.last_move.pooled.len(),
            "pool size differs"
        );
        for (x, y) in over.last_move.pooled.iter().zip(baked.last_move.pooled.iter()) {
            assert_eq!(
                (x.0, x.1.to_bits(), x.2.to_bits()),
                (y.0, y.1.to_bits(), y.2.to_bits()),
                "override(24) pooled floats differ from baked 24"
            );
        }
        // Statelessness: the override did not leak into the config.
        assert_eq!(over.cfg.search.simulations, 64);
        let mut plain = FairAgent::new(cfg(4, 64, 2));
        let act_p = plain.choose_action(&g, Some(8)).unwrap();
        let act_o2 = over.choose_action(&g, Some(8)).unwrap();
        assert_eq!(act_o2, act_p, "a past override changed a later plain move");
        assert_eq!(over.last_move.sims_used, 64);
        for (x, y) in over.last_move.pooled.iter().zip(plain.last_move.pooled.iter()) {
            assert_eq!(
                (x.0, x.1.to_bits(), x.2.to_bits()),
                (y.0, y.1.to_bits(), y.2.to_bits())
            );
        }
    }

    /// Surface C, the dose-0 analogue: mask 0 with a MOVED min_keep must be
    /// byte-identical to the plain default agent — the OFF path may not even
    /// read the min_keep knob.
    #[test]
    fn jrules_filter_mask0_with_moved_min_keep_is_bit_identical() {
        let g = midgame("28000000000", 41); // meeples-phase root (41 plies)
        let mut base = FairAgent::new(cfg(4, 48, 2));
        let mut c = cfg(4, 48, 2);
        c.search.jrules_filter_mask = 0;
        c.search.jrules_filter_min_keep = 7; // deliberately moved
        let mut moved = FairAgent::new(c);
        let a1 = base.choose_action(&g, Some(5)).unwrap();
        let a2 = moved.choose_action(&g, Some(5)).unwrap();
        assert_eq!(a1, a2);
        assert_eq!(base.last_move.pooled.len(), moved.last_move.pooled.len());
        for (x, y) in base.last_move.pooled.iter().zip(moved.last_move.pooled.iter()) {
            assert_eq!(
                (x.0, x.1.to_bits(), x.2.to_bits()),
                (y.0, y.1.to_bits(), y.2.to_bits()),
                "mask-0 surface C changed a pooled float"
            );
        }
        assert_eq!(moved.jf_dropped_total, 0);
        assert_eq!(moved.jf_applicable_moves, 0);
    }

    /// Surface C live: on a meeple root where the filter drops something, every
    /// pooled action must be in the KEPT set, the chosen action must be kept,
    /// and the counters must record the drop.
    #[test]
    fn jrules_filter_restricts_the_pimc_root() {
        // Find a meeple root with >1 legal where the current-stack filter bites.
        let mut found = false;
        for seed in ["7", "1234", "99", "28000000000", "555", "31337"] {
            let mut g = Game::from_seed(seed);
            for _ in 0..400 {
                if g.state.phase == crate::engine::Phase::Meeples && g.legal_actions().len() > 1
                {
                    let fo =
                        jrules_filter::jrules_root_filter(&g, jrules_filter::JF_CURRENT, 1)
                            .unwrap();
                    if !fo.dropped.is_empty() {
                        let mut c = cfg(4, 48, 1);
                        c.search.jrules_filter_mask = jrules_filter::JF_CURRENT;
                        let mut a = FairAgent::new(c);
                        let act = a.choose_action(&g, Some(3)).unwrap();
                        assert!(fo.kept.contains(&act), "chosen action was filtered out");
                        for &(pa, _, _) in &a.last_move.pooled {
                            assert!(
                                fo.kept.contains(&pa),
                                "pooled action {pa} is outside the kept set"
                            );
                        }
                        assert_eq!(a.last_move.jf_dropped, fo.dropped);
                        assert_eq!(a.jf_dropped_total, fo.dropped.len() as u64);
                        assert_eq!(a.jf_applicable_moves, 1);
                        assert!(a.jf_fires.iter().any(|&n| n > 0));
                        found = true;
                        break;
                    }
                }
                let la = g.legal_actions();
                g.advance(la[la.len() / 2]).unwrap();
            }
            if found {
                break;
            }
        }
        assert!(found, "no meeple root where JF_CURRENT bites was found");
    }

    /// TIE ARBITER dose-0 analogue: `tiearb_enabled = false` with every OTHER
    /// tiearb knob deliberately moved must be BYTE-identical to the plain
    /// default agent — the OFF path may not even read the knobs.
    #[test]
    fn tiearb_disabled_with_moved_knobs_is_bit_identical() {
        let g = midgame("28000000000", 40);
        let mut base = FairAgent::new(cfg(4, 48, 2));
        let mut c = cfg(4, 48, 2);
        c.search.tiearb_enabled = false;
        c.search.tiearb_b = 3; // deliberately moved
        c.search.tiearb_j = 7;
        c.search.tiearb_mode = crate::tiearb::TiearbMode::Random;
        c.search.tiearb_salt = String::from("not-the-salt-of-record");
        c.search.tiearb_eps = 9.5;
        let mut moved = FairAgent::new(c);
        let a1 = base.choose_action(&g, Some(5)).unwrap();
        let a2 = moved.choose_action(&g, Some(5)).unwrap();
        assert_eq!(a1, a2);
        assert_eq!(base.last_move.pooled.len(), moved.last_move.pooled.len());
        for (x, y) in base.last_move.pooled.iter().zip(moved.last_move.pooled.iter()) {
            assert_eq!(
                (x.0, x.1.to_bits(), x.2.to_bits()),
                (y.0, y.1.to_bits(), y.2.to_bits()),
                "a disabled tiearb knob changed a pooled float"
            );
        }
        assert_eq!(moved.tiearb_fired_plies, 0);
        assert_eq!(moved.tiearb_tile_plies, 0);
        assert_eq!(moved.tiearb_playouts_total, 0);
        assert_eq!(moved.tiearb_secs, 0.0);
        assert!(!moved.last_move.tiearb_fired);
    }

    /// The arbiter is LIVE at the agent root: on a game where the trigger
    /// fires, the counters move, the arms are a real set, and the returned
    /// action is one of them. (Whether it CHANGES the pick is the J13
    /// positive control's job — it needs a hunt across plies.)
    #[test]
    fn tiearb_enabled_fires_and_returns_an_arm() {
        let mut c = cfg(2, 16, 1);
        c.search.tiearb_enabled = true;
        c.search.tiearb_b = 2; // cheap: this is a wiring test, not the cell
        c.exact_endgame = false;
        let mut a = FairAgent::new(c);
        let mut g = Game::from_seed("28000000000");
        let mut fired = 0u64;
        for _ in 0..40 {
            if g.is_terminal() {
                break;
            }
            let act = a.choose_action(&g, None).unwrap();
            if a.last_move.tiearb_fired {
                fired += 1;
                assert!(a.last_move.tiearb_arms.len() >= 2);
                assert!(
                    a.last_move.tiearb_arms.contains(&act),
                    "the returned action is not in the arm set"
                );
                assert_eq!(
                    a.last_move.tiearb_pickchange,
                    act != a.last_move.tiearb_champ_pick
                );
                assert!(a.last_move.tiearb_playouts >= 2 * 2);
            }
            g.advance(act).unwrap();
        }
        assert!(fired > 0, "the trigger never fired in 40 plies");
        assert_eq!(a.tiearb_fired_plies, fired);
        assert!(a.tiearb_tile_plies >= fired);
        assert!(a.tiearb_arms_total >= 2 * fired);
        assert!(a.tiearb_secs > 0.0);
    }

    /// AGENT-LEVEL leg of the arbiter's world-threading identity gate
    /// (2026-08-21): `search.tiearb_threads` is a LATENCY knob, so a whole
    /// played game must be identical at every setting — same action sequence,
    /// same firing/pick-change/playout telemetry. Note this is the arbiter's
    /// OWN thread count, deliberately independent of `FairConfig::threads`
    /// (the k-world fan-out), which stays at 1 here.
    #[test]
    fn tiearb_thread_count_invariance() {
        let play = |tiearb_threads: usize| {
            let mut c = cfg(2, 16, 1);
            c.search.tiearb_enabled = true;
            c.search.tiearb_b = 4;
            c.search.tiearb_threads = tiearb_threads;
            c.exact_endgame = false;
            let mut a = FairAgent::new(c);
            let mut g = Game::from_seed("28000000000");
            let mut acts = Vec::new();
            for _ in 0..24 {
                if g.is_terminal() {
                    break;
                }
                let act = a.choose_action(&g, None).unwrap();
                acts.push(act);
                g.advance(act).unwrap();
            }
            (
                acts,
                a.tiearb_fired_plies,
                a.tiearb_pickchanges,
                a.tiearb_arms_total,
                a.tiearb_playouts_total,
                a.tiearb_errors,
                a.tiearb_partial_argmax,
            )
        };
        let want = play(1);
        assert!(want.1 > 0, "the arbiter never fired — the test is vacuous");
        for t in [2usize, 4, 8] {
            assert_eq!(play(t), want, "tiearb_threads={t} changed the game");
        }
    }

    /// `random` mode must spend the SAME playouts as `argmax` on the same
    /// decisions — the matched-wall-clock control's whole basis.
    #[test]
    fn tiearb_random_mode_spends_the_same_playouts() {
        let mk = |mode| {
            let mut c = cfg(2, 16, 1);
            c.search.tiearb_enabled = true;
            c.search.tiearb_b = 2;
            c.search.tiearb_mode = mode;
            c.exact_endgame = false;
            FairAgent::new(c)
        };
        let mut arb = mk(crate::tiearb::TiearbMode::Argmax);
        let mut rnd = mk(crate::tiearb::TiearbMode::Random);
        let g = midgame("28000000000", 40);
        let _ = arb.choose_action(&g, Some(11)).unwrap();
        let _ = rnd.choose_action(&g, Some(11)).unwrap();
        assert!(arb.last_move.tiearb_fired || !rnd.last_move.tiearb_fired);
        assert_eq!(arb.last_move.tiearb_fired, rnd.last_move.tiearb_fired);
        assert_eq!(arb.last_move.tiearb_arms, rnd.last_move.tiearb_arms);
        assert_eq!(arb.tiearb_playouts_total, rnd.tiearb_playouts_total);
    }

    /// READ_RULE §0.F `G-PLY`, the implementation witness: a mid-playout
    /// failure must revert the WHOLE ply to the champion's own
    /// `pooled_q_argmax` pick — never an argmax over the surviving worlds.
    /// Constructed by squeezing the ply ceiling so the continuations error.
    #[test]
    fn a_playout_failure_reverts_the_whole_ply_and_never_partially_argmaxes() {
        let g = midgame("28000000000", 40);
        let mut base = FairAgent::new(cfg(4, 48, 1));
        let champ = base.choose_action(&g, Some(9)).unwrap();

        let mut c = cfg(4, 48, 1);
        c.search.tiearb_enabled = true;
        c.search.tiearb_b = 4;
        c.search.tiearb_max_plies = 3; // every continuation dies mid-playout
        c.exact_endgame = false;
        let mut broken = FairAgent::new(c);
        let act = broken.choose_action(&g, Some(9)).unwrap();

        assert_eq!(act, champ, "a failed arbitration did not revert to the champion's pick");
        assert!(broken.tiearb_errors > 0, "the ceiling did not actually break a playout");
        assert!(!broken.last_move.tiearb_fired, "a failed ply must not count as fired");
        assert_eq!(broken.tiearb_fired_plies, 0);
        assert_eq!(broken.tiearb_partial_argmax, 0,
                   "an argmax was taken over a PARTIAL world set");
        assert!(broken.tiearb_first_error.is_some());
    }

    /// ...and on a HEALTHY ply every world completes, so the same counter stays
    /// 0 for the opposite reason. Both halves are needed: a counter that is 0
    /// because the arbiter never ran proves nothing.
    #[test]
    fn a_healthy_ply_completes_every_world() {
        let mut c = cfg(2, 16, 1);
        c.search.tiearb_enabled = true;
        c.search.tiearb_b = 2;
        c.exact_endgame = false;
        let mut a = FairAgent::new(c);
        let mut g = Game::from_seed("28000000000");
        for _ in 0..30 {
            if g.is_terminal() {
                break;
            }
            let act = a.choose_action(&g, None).unwrap();
            g.advance(act).unwrap();
        }
        assert!(a.tiearb_fired_plies > 0, "the arbiter never ran");
        assert_eq!(a.tiearb_errors, 0);
        assert_eq!(a.tiearb_partial_argmax, 0);
    }

    // ----------------------------------------------------------------- //
    // THE PHASE FIRE-GATE (measurement/phasegate_prep/DESIGN.md §7.2/§7.5) //
    // ----------------------------------------------------------------- //

    /// Play one seeded game with the arbiter armed at `gate` and return
    /// `(action sequence, [fired_early, fired_mid, fired_late], fired_plies,
    ///   tile_plies, errors, pickchanges)`.
    #[allow(clippy::type_complexity)]
    fn play_gated(
        gate: crate::tiearb::TiearbPhaseGate,
        enabled: bool,
        seed: &str,
        plies: usize,
    ) -> (Vec<i32>, [u64; 3], u64, u64, u64, u64) {
        let mut c = cfg(2, 16, 1);
        c.search.tiearb_enabled = enabled;
        c.search.tiearb_phase_gate = gate;
        c.search.tiearb_b = 2; // cheap: these are wiring tests, not the cell
        c.exact_endgame = false;
        let mut a = FairAgent::new(c);
        let mut g = Game::from_seed(seed);
        let mut acts = Vec::new();
        for _ in 0..plies {
            if g.is_terminal() {
                break;
            }
            let act = a.choose_action(&g, None).unwrap();
            acts.push(act);
            g.advance(act).unwrap();
        }
        (
            acts,
            a.tiearb_fired_by_phase,
            a.tiearb_fired_plies,
            a.tiearb_tile_plies,
            a.tiearb_errors,
            a.tiearb_pickchanges,
        )
    }

    /// ⭐⭐ IDENTITY 1 — `gate = All` is TODAY'S UNGATED ARBITER. The default
    /// IS `All`, so this asserts the default has not moved AND that setting it
    /// explicitly changes nothing: same action sequence, same counters.
    #[test]
    fn phase_gate_all_is_the_ungated_arbiter() {
        assert_eq!(
            SearchConfig::default().tiearb_phase_gate,
            crate::tiearb::TiearbPhaseGate::All,
            "the DEFAULT gate must be All — the IDENT cell's premise"
        );
        // an agent built WITHOUT touching the field ...
        let mut c = cfg(2, 16, 1);
        c.search.tiearb_enabled = true;
        c.search.tiearb_b = 2;
        c.exact_endgame = false;
        let mut base = FairAgent::new(c);
        let mut g = Game::from_seed("28000000000");
        let mut base_acts = Vec::new();
        for _ in 0..30 {
            if g.is_terminal() {
                break;
            }
            let act = base.choose_action(&g, None).unwrap();
            base_acts.push(act);
            g.advance(act).unwrap();
        }
        // ... and one built with `All` set explicitly.
        let (all_acts, _, fired_all, tile_all, _, chg_all) =
            play_gated(crate::tiearb::TiearbPhaseGate::All, true, "28000000000", 30);
        assert_eq!(base_acts, all_acts, "gate=all changed a played action");
        assert_eq!(base.tiearb_fired_plies, fired_all);
        assert_eq!(base.tiearb_tile_plies, tile_all);
        assert_eq!(base.tiearb_pickchanges, chg_all);
        assert!(fired_all > 0, "the arbiter never fired — the test proves nothing");
    }

    /// ⭐⭐ IDENTITY 2 — `gate = None` is THE UNMODIFIED CHAMPION. The armed
    /// knob must produce the champion's own action sequence, byte for byte,
    /// and touch NO counter (the gated-out ply returns down the same branch as
    /// `tiearb_enabled == false`).
    #[test]
    fn phase_gate_none_is_the_unmodified_champion() {
        let (champ_acts, champ_ph, champ_fired, champ_tile, champ_err, champ_chg) =
            play_gated(crate::tiearb::TiearbPhaseGate::All, false, "28000000000", 40);
        let (none_acts, none_ph, none_fired, none_tile, none_err, none_chg) =
            play_gated(crate::tiearb::TiearbPhaseGate::None, true, "28000000000", 40);
        assert_eq!(champ_acts, none_acts, "gate=none is NOT the champion");
        assert_eq!((champ_ph, none_ph), ([0; 3], [0; 3]));
        assert_eq!((champ_fired, none_fired), (0, 0));
        // ⚠️ the gate short-circuits BEFORE `tiearb_arbitrate`, so a gated-out
        // ply is not even a "tile ply at which the trigger was evaluated".
        assert_eq!((champ_tile, none_tile), (0, 0));
        assert_eq!((champ_err, none_err), (0, 0), "a gated-out ply is NOT an error");
        assert_eq!((champ_chg, none_chg), (0, 0));
    }

    /// PARTITION — on `gate = all` the three per-phase counters sum to
    /// `fired_plies` and at least two buckets are exercised over a whole game.
    #[test]
    fn phase_gate_counters_partition_the_fired_plies() {
        let (_, ph, fired, _, err, _) =
            play_gated(crate::tiearb::TiearbPhaseGate::All, true, "28000000000", 400);
        assert!(fired > 0, "the arbiter never fired");
        assert_eq!(ph[0] + ph[1] + ph[2], fired, "per-phase counters do not partition");
        assert_eq!(err, 0);
        assert!(
            ph.iter().filter(|&&n| n > 0).count() >= 2,
            "a whole game must span more than one phase; got {ph:?}"
        );
    }

    /// ⭐⭐ DISJOINTNESS — `G-PHI`'s window bit, proved from PLAY. On
    /// `gate = early` the mid and late counters are 0 and early is positive;
    /// mirror for mid and late.
    #[test]
    fn phase_gate_windows_are_disjoint_in_play() {
        for (gate, idx) in [
            (crate::tiearb::TiearbPhaseGate::Early, 0usize),
            (crate::tiearb::TiearbPhaseGate::Mid, 1),
            (crate::tiearb::TiearbPhaseGate::Late, 2),
        ] {
            let (_, ph, fired, _, err, _) = play_gated(gate, true, "28000000000", 400);
            assert!(ph[idx] > 0, "gate={} never fired: {ph:?}", gate.value());
            assert_eq!(ph[idx], fired, "gate={} fired outside its window", gate.value());
            for (j, n) in ph.iter().enumerate() {
                if j != idx {
                    assert_eq!(*n, 0, "gate={} fired in bucket {j}", gate.value());
                }
            }
            assert_eq!(err, 0, "a gated-out ply must not touch tiearb_errors");
        }
    }

    /// The gated cells are STRICTLY CHEAPER than `all` in fired plies, and the
    /// three windows' fired counts sum to the ungated cell's — ⛔ on the SAME
    /// game only, which is why this is asserted on ply COUNTS from the shared
    /// prefix and never used as a claim about MARGINS (DESIGN §1.2: the slices
    /// play different games and need not sum).
    #[test]
    fn phase_gate_fires_strictly_less_than_all() {
        let (_, _, fired_all, _, _, _) =
            play_gated(crate::tiearb::TiearbPhaseGate::All, true, "28000000000", 400);
        for gate in [
            crate::tiearb::TiearbPhaseGate::Early,
            crate::tiearb::TiearbPhaseGate::Mid,
            crate::tiearb::TiearbPhaseGate::Late,
        ] {
            let (_, _, fired, _, _, _) = play_gated(gate, true, "28000000000", 400);
            assert!(
                fired < fired_all,
                "gate={} fired {fired} >= all's {fired_all}",
                gate.value()
            );
        }
    }

    /// The gate reads `k_remaining` (deck + the tile IN HAND), NOT
    /// `deck_len()`. A gate built on `deck_len` would fire one tile late; this
    /// pins the two apart at the plies where a tile IS in hand.
    #[test]
    fn k_remaining_is_deck_len_plus_the_tile_in_hand() {
        let mut g = Game::from_seed("28000000000");
        let mut saw_difference = false;
        for _ in 0..60 {
            if g.is_terminal() {
                break;
            }
            let k = k_remaining(&g);
            let d = g.state.deck_len() as i64;
            assert!(k == d || k == d + 1);
            if k == d + 1 {
                saw_difference = true;
                // the off-by-one is REAL at the boundary: k=49 is early while
                // deck_len=48 would bucket as late.
                if k == 49 {
                    assert_eq!(crate::tiearb::phase_bucket(k), "early");
                    assert_eq!(crate::tiearb::phase_bucket(d), "late");
                }
            }
            let la = g.legal_actions();
            g.advance(la[la.len() / 2]).unwrap();
        }
        assert!(saw_difference, "never observed a tile in hand — the test proves nothing");
    }

    #[test]
    fn pooled_q_argmax_tiebreaks_on_n_then_lowest_action() {
        let mut p = Pool::default();
        // same Q, different N -> higher N wins
        p.merge(&[(9, 4, 2.0), (3, 8, 4.0)]);
        assert_eq!(pooled_q_argmax(&p, 2.0), Some(3));
        // same Q AND same N -> LOWEST action wins
        let mut q = Pool::default();
        q.merge(&[(9, 4, 2.0), (3, 4, 2.0)]);
        assert_eq!(pooled_q_argmax(&q, 2.0), Some(3));
        // the min-visits floor excludes 1-visit noise picks...
        let mut r = Pool::default();
        r.merge(&[(9, 1, 5.0), (3, 4, 2.0)]);
        assert_eq!(pooled_q_argmax(&r, 2.0), Some(3));
        // ...unless NOTHING qualifies, in which case all visited become eligible
        let mut s = Pool::default();
        s.merge(&[(9, 1, 5.0), (3, 1, 2.0)]);
        assert_eq!(pooled_q_argmax(&s, 2.0), Some(9));
    }
}
