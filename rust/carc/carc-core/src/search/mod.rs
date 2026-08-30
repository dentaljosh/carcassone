//! `search` — single-world PUCT with heuristic-leaf priors (rustport **P3**).
//!
//! A bit-faithful port of the Python champion's *one determinization world*:
//! [`mcts.NeuralMCTS`] driven by the evaluator built in
//! [`heuristic_prior_mcts.make_heuristic_prior_evaluator`].  Everything the
//! Python does with floats is reproduced through [`crate::compat`] — the two
//! transcendental sites (`np.exp` at the prior softmax, `math.tanh` at the value
//! and at `get_game_ended`), numpy's **pairwise** `sum` in both `float64` and
//! `float32`, and the `float32` round-trips the prior vector makes on the way
//! into the tree.
//!
//! Nothing about the champion is hard-coded: every knob arrives in
//! [`SearchConfig`] from Python (the P2 `LeafConfigRs` precedent).
//!
//! ## The five details that are easy to get wrong
//!
//! 1. **The root's `leaf_value` goes through a `float32` round-trip; interior
//!    nodes do not.** `search()` expands the root via `_eval_boards`, which
//!    packs the values into `np.array(..., dtype=np.float32)`; `_expand`
//!    (interior) hands the evaluator's raw Python float straight through. See
//!    [`Searcher::expand`]'s `via_f32` argument.
//! 2. **Two reductions, two dtypes.** The softmax normalizes in `float64`
//!    (`np.sum` pairwise), is cast to `float32`, and is then normalized *again*
//!    in `float32` inside `_expand_with_priors` (`legal_priors.sum()` on a
//!    `float32` array returns `np.float32`, and NEP-50 keeps the following
//!    divide in `float32`).
//! 3. **Python's repr-keyed legal-move cache has no observable effect HERE, so
//!    it is not reproduced.** `NeuralMCTS.__init__` force-enables it, so two
//!    distinct boards sharing one repr key (the Phase-0.3 rotation family) are
//!    served the *first* board's mask — but in this port that collapse already
//!    happens one step earlier, at [`Tree::index`]: `create_or_get` returns the
//!    existing node and [`Searcher::expand`] short-circuits on `expanded`, so a
//!    key can never be evaluated twice and the cache was structurally incapable
//!    of hitting (measured: 0 hits in 50,326 lookups — ROUND2 C-e, 2026-08-02).
//! 4. **A terminal root is never expanded**, so its `leaf_value` stays at the
//!    `0.0` default and every simulation backs up zero.
//! 5. **`node.children` insertion order is observable** — `best_action` falls
//!    back to `next(iter(root.children))` when no child has a visit.
//!
//! Gate: `scripts/rustport/reconcile_search.py` (G3, "0 mismatches, full stop").

use std::collections::HashMap;
use std::collections::HashSet;
use std::rc::Rc;

use crate::compat::{self, LibmFlavor};
use crate::engine::Phase;
use crate::game::Game;
use crate::leaf::{self, LeafConfig, LeafError, LeafScratch};
use crate::sha256::sha256_hex_prefix;

/// The trace-harness node identity: `hashlib.sha256(state_key).hexdigest()[:16]`
/// (`scripts/rustport/trace_search.py:digest`).  A RECORDED ARTIFACT CONTRACT —
/// the algorithm must not change; only *when* it is paid may.
fn node_digest(key: &str) -> String {
    sha256_hex_prefix(key.as_bytes(), 16)
}

mod fxhash;
/// L1a — the meeple-phase decomposition hoist's correctness gates.
#[cfg(test)]
mod l1a_hoist_tests;
/// P6 (Gap 2): the persistent / re-rootable tree.  ADDITIVE — nothing in this
/// module calls into it, so the fresh-tree path above is byte-identical with the
/// session unused.
pub mod session;
pub mod trace;
/// F-c: the empty-action-mask diagnostic.  ERROR PATH ONLY — see the module doc.
pub mod window_diag;

pub use fxhash::FxBuildHasher;
pub use session::{carried_scope_guard, Reroot, SearchSession};
pub use trace::{JsonlTrace, TraceSink};
pub use window_diag::{DroppedPlacement, EmptyMaskCause, EmptyMaskDiag};

pub type NodeId = u32;

thread_local! {
    /// ⚠️ GATES AND TESTS ONLY — see [`with_fresh_decomp`].
    static FORCE_FRESH_DECOMP: std::cell::Cell<bool> = const { std::cell::Cell::new(false) };
}

#[inline]
fn force_fresh_decomp() -> bool {
    FORCE_FRESH_DECOMP.with(|c| c.get())
}

/// Restores [`FORCE_FRESH_DECOMP`] even if `f` unwinds.
struct FreshDecompGuard(bool);
impl Drop for FreshDecompGuard {
    fn drop(&mut self) {
        FORCE_FRESH_DECOMP.with(|c| c.set(self.0));
    }
}

/// ⚠️ **GATES AND TESTS ONLY.** Runs `f` with the L1a meeple-phase
/// decomposition hoist disabled **on this thread**, i.e. every child pays its
/// own `decompose_into` exactly as the pre-L1a code did.
///
/// This is not a configuration knob and nothing in production calls it: the
/// hoist is bit-identical (a meeple action cannot move a tile, and
/// `decompose_into` reads only the tile board), so there is no shape to choose
/// between. It exists so an identity gate can run BOTH routes over the same
/// roots and seeds instead of re-implementing the search. Precedent and shape:
/// [`crate::tier1::with_legacy_scorer`].
#[doc(hidden)]
pub fn with_fresh_decomp<R>(f: impl FnOnce() -> R) -> R {
    let prev = FORCE_FRESH_DECOMP.with(|c| c.replace(true));
    let _g = FreshDecompGuard(prev);
    f()
}

/// `HeuristicPriorConfig.final_select`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum FinalSelect {
    /// `NeuralMCTS.best_action` — `(Q, N)` lexicographic max over visited,
    /// deduped root children.
    Q,
    /// `argmax` of the deduped root visit distribution (the champion).
    Visits,
    /// `HeuristicPriorAgent._lcb_action`.
    Lcb,
}

/// J-RULES PRIOR surface B (`measurement/jrules_priors_20260814/DESIGN.md`):
/// which expansions get the prior boost when `jrules_prior_dose != 0.0`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum JrPriorScope {
    /// Every expanded node, from that node's MOVER's own POV — the structural
    /// analogue of the house priors themselves (every node's softmax already
    /// prefers the mover's leaf-improving moves) and of the static bundle's
    /// antisymmetric form (both in-tree players "play the strategy"). The
    /// default and the pre-registered primary.
    All,
    /// Only nodes where the ROOT player is to move — the internal opponent
    /// model stays the unmodified champion. A named ablation (the prior-surface
    /// analogue of the static cell's `jrules_symmetric = False` open question);
    /// needs its own prereg, never a rung of the primary cell's ladder.
    Own,
    /// S1 (`measurement/s1_asymmetry_prep/DESIGN.md`): only nodes where the
    /// root player is **NOT** to move — the OPPONENT-MODEL arm. The champion's
    /// own move ordering is untouched at every own-mover node (the ROOT
    /// included, since the root's mover IS the root player), so the whole
    /// behavioural difference is search-mediated: it arrives through interior
    /// opponent expansions only, where the modelled opponent now orders its
    /// moves by the anchor's J bundle (which carries the J2 farm-steal JOIN
    /// predicate — the invasion predicate). The LEAF VALUE backed up is
    /// untouched on every path and no leaf hash moves, exactly as under
    /// [`JrPriorScope::All`]/[`JrPriorScope::Own`].
    ///
    /// ⚠️ **This is the exact complement of [`JrPriorScope::Own`]** — see
    /// [`SearchResult::jr_expansions_boosted`] for the machine-checkable
    /// decomposition identity (`Own ∪ Opp = All`, disjoint).
    ///
    /// ⚠️ **Root priors are IDENTICAL to the champion's by design.** Any
    /// liveness control that asserts moved ROOT PRIORS is *wrong* for this
    /// scope and will fail on a correctly wired build (DESIGN §9.2).
    Opp,
}

/// `HeuristicPriorConfig.leaf_quantize`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum LeafQuantize {
    /// `flat_virtual_score_v2` (`int(round(...))`), widened to a float.
    Int,
    /// `flat_virtual_score_v2_float` — the champion.
    Float,
}

/// Every knob the search reads. Driven in from Python; no defaults are baked in
/// beyond the struct's own `Default`, which exists only for tests.
#[derive(Clone)]
pub struct SearchConfig {
    pub c_puct: f64,
    pub tau_p: f64,
    pub value_norm: f64,
    /// `game_wrapper.SCORE_NORM_SCALE` (terminal value normalizer).
    pub score_norm_scale: f64,
    pub leaf_quantize: LeafQuantize,
    pub simulations: usize,
    /// `NeuralMCTS.fpu_reduction`; `None` = the legacy optimistic `q = 0.0`.
    pub fpu_reduction: Option<f64>,
    pub final_select: FinalSelect,
    pub c_lcb: f64,
    /// `np.exp` float64 → glibc's `__exp_fma` ifunc on x86-64 (G0 §3).
    pub exp_fma: bool,
    /// `math.tanh` → [`LibmFlavor::GlibcFma`] on x86-64 (G0 §2).
    pub tanh_flavor: LibmFlavor,
    /// Reuse ONE [`LeafScratch`] for every leaf evaluation of the search (the P2
    /// perf lever). `false` calls the allocating `leaf::leaf_value_float`, which
    /// is what the P2 gate measured — kept so the lever can be A/B'd in one
    /// process (`bench_search_scratch_ab`) rather than across builds. Results
    /// are bit-identical either way.
    pub use_leaf_scratch: bool,
    pub leaf: LeafConfig,
    /// J-RULES PRIOR surface B. `0.0` (default == the champion) NEVER touches
    /// the prior pipeline — the dose-0 code path is the pre-change code,
    /// byte-for-byte, so default traffic is bit-identical, not merely equal.
    /// Nonzero: each legal child's Δleaf gets `dose * jrules_prior_term(child)`
    /// added BEFORE the prior softmax (⇒ a multiplicative, renormalized
    /// `exp(dose·T/tau_p)` boost on that child's prior). The LEAF VALUE the
    /// search backs up is untouched on every path — this knob is not part of
    /// [`LeafConfig`] and moves no leaf hash, so a moved-hash gate cannot prove
    /// it live; the manifest's resolved dose is the wiring gate.
    pub jrules_prior_dose: f64,
    /// Per-rule ablation mask over `leaf::{JR_J1,JR_J2,JR_J5,JR_J6,JR_J8}`
    /// (default 31 == the bundle). Only read when the dose is nonzero.
    pub jrules_prior_mask: i64,
    /// See [`JrPriorScope`]. Only read when the dose is nonzero.
    pub jrules_prior_scope: JrPriorScope,
    /// J-RULES ROOT FILTER surface C
    /// (`measurement/jrules_filters_20260814/DESIGN.md`). `0` (default == the
    /// champion) NEVER touches the filter code — the mask-0 path is the
    /// pre-change code, byte-for-byte. Nonzero: the fair agent applies the
    /// bot's hard filters (`fair::jrules_filter`, bits F-END|F-J10|F-J9|F-J3)
    /// to the ROOT legal-action set BEFORE the PIMC world searches run; the
    /// searches then expand only the surviving root candidates. ROOT ONLY —
    /// interior nodes are never filtered. NOT a [`LeafConfig`] field: no leaf
    /// hash moves, so a moved-hash gate cannot prove it live; the manifest's
    /// resolved mask + the per-cell drop counter are the wiring gates.
    /// ⚠️ Read by [`crate::fair::FairAgent`], NOT by the single-world
    /// [`Searcher`] itself (a bare `search_single` ignores it — the filter is
    /// an AGENT-level, once-per-move intervention).
    pub jrules_filter_mask: i64,
    /// Never-empty guard for the root filter: a filter that would leave fewer
    /// than this many root candidates YIELDS (is skipped for that ply, and the
    /// yield is counted). Default 1 == `joshua_bot`'s own "skip if it would
    /// empty the set". Only read when `jrules_filter_mask != 0`.
    pub jrules_filter_min_keep: usize,
    /// TIE ARBITRATION surface (`measurement/tiearb2_stage2_20260817/DESIGN.md`).
    /// `false` (default == the champion) NEVER touches [`crate::tiearb`] — the
    /// disabled path is the pre-change code, byte for byte, exactly as
    /// `jrules_filter_mask == 0` is. Enabled: after the pooled PUCT argmax,
    /// [`crate::fair::FairAgent`] re-decides an exactly-tied TILE ply by
    /// `tier1-greedy` playouts over `tiearb_b` CRN determinizations.
    /// ⚠️ Read by [`crate::fair::FairAgent`], NOT by the single-world
    /// [`Searcher`]: the arbiter is an AGENT-level, once-per-move intervention
    /// and it moves NO leaf hash and NO search byte — the manifest's resolved
    /// `cand_tiearb` dict plus the two-sided J13 positive control are the only
    /// wiring gates that can prove it live.
    pub tiearb_enabled: bool,
    /// `B` — CRN determinizations per fired ply, SHARED by every arm.
    pub tiearb_b: usize,
    /// `J` — the cap on the deduped tie set, applied by a seeded draw.
    pub tiearb_j: usize,
    pub tiearb_mode: crate::tiearb::TiearbMode,
    /// THE FIRE-GATE — a PHASE WINDOW on the arbiter's fire decision
    /// (`measurement/phasegate_prep/DESIGN.md` §7.2). `All` (the default) is
    /// the pre-change arbiter byte for byte: [`crate::fair::FairAgent`]
    /// short-circuits on it without reading the deck at all, exactly as
    /// `tiearb_enabled == false` returns without touching [`crate::tiearb`].
    ///
    /// The window is evaluated on `crate::fair::k_remaining(g)` — undrawn deck
    /// **plus the tile in hand** — and bucketed by
    /// [`crate::tiearb::phase_bucket`], the canonical census axis
    /// (`early` = [49,71], `mid` = [25,47], `late` = [0,23] ⚠️ **plus `k=48`
    /// and `k=24`**, which fall through). ⛔ NEVER `g.state.deck_len()`, which
    /// is off by one against that axis.
    ///
    /// ⛔ Unrelated to [`Self::tiearb_max_plies`], which is a *playout* ceiling.
    pub tiearb_phase_gate: crate::tiearb::TiearbPhaseGate,
    /// The seed salt of record, `tiearb2-deploy-v1`.
    pub tiearb_salt: String,
    /// Tie membership tolerance. **0.0 is the committed setting** — exact f64
    /// equality, not a tolerance (DESIGN §2).
    pub tiearb_eps: f64,
    /// Ply ceiling for the arbiter's `tier1-greedy` continuations. A GUARD, not
    /// a truncation: a playout that hits it ERRORS (and the whole ply reverts to
    /// the champion's own pick), it is never scored short — DESIGN's
    /// terminal-grounding estimand forbids a non-terminal value, and READ_RULE
    /// §0.D's anti-gaming clause forbids truncating for cost. 400 is the
    /// default; a full 2-player base game is ~144 plies. Exposed only so a test
    /// can CONSTRUCT a mid-playout failure and witness the whole-ply revert.
    pub tiearb_max_plies: usize,
    /// WC tie-break rule (`BACKLOG.md` 2026-08-03; verbatim source at
    /// `crate::fair::solver::SolverConfig::wc_tiebreak`'s doc comment): official
    /// World Championship rules rule a tied FINAL score a LOSS for the
    /// starting player (P0). `false` (default == the champion) is the
    /// untouched incumbent — [`Searcher::game_ended`]'s tie branch (the
    /// terminal-value sentinel for an exact `tanh` output of `0.0`) keeps its
    /// pre-flag signs byte for byte. Armed, that tie branch sign-flips: `-1e-6`
    /// for player 0, `1e-6` for player 1 (magnitude UNCHANGED — this is a
    /// terminal-scoring-only rule change, not a rescale of the margin-flavored
    /// tanh value). Mirrors `game_wrapper.Game.get_game_ended`'s armed branch
    /// exactly (the python-side mirror-image change).
    pub wc_tiebreak: bool,
    /// OS threads the arbiter splits its `B` CRN worlds across (arms inner).
    /// **A LATENCY knob and nothing else** — [`crate::tiearb::arbitrate`] is
    /// bit-identical at every thread count (same means, same pick, same error),
    /// the G6/G4 behaviour-identity class. `1` (the default) is the pre-change
    /// sequential loop, so no cell changes until this is deliberately raised.
    /// Deliberately NOT `FairConfig::threads`: the k-world fan-out and the
    /// arbiter's world fan-out are different budgets on different boxes, and
    /// coupling them would silently flip a deployed `rust_threads = 2` cell.
    pub tiearb_threads: usize,
}

impl Default for SearchConfig {
    fn default() -> Self {
        SearchConfig {
            c_puct: 1.5,
            tau_p: 5.0,
            value_norm: 15.0,
            score_norm_scale: 15.0,
            leaf_quantize: LeafQuantize::Float,
            simulations: 1376,
            fpu_reduction: None,
            final_select: FinalSelect::Visits,
            c_lcb: 1.0,
            exp_fma: true,
            tanh_flavor: LibmFlavor::GlibcFma,
            use_leaf_scratch: true,
            leaf: LeafConfig::curve125(),
            jrules_prior_dose: 0.0,
            jrules_prior_mask: leaf::JR_ALL,
            jrules_prior_scope: JrPriorScope::All,
            jrules_filter_mask: 0,
            jrules_filter_min_keep: 1,
            tiearb_enabled: false,
            tiearb_b: 16,
            tiearb_j: 4,
            tiearb_mode: crate::tiearb::TiearbMode::Argmax,
            // ⭐ THE IDENTITY PREMISE of the `IDENT` cell: the default is `All`,
            // i.e. no gate, i.e. today's arbiter. A build whose default were
            // anything else would silently re-slice every deployed cell.
            tiearb_phase_gate: crate::tiearb::TiearbPhaseGate::All,
            tiearb_salt: String::from(crate::tiearb::TIEARB_SALT_OF_RECORD),
            tiearb_eps: 0.0,
            tiearb_max_plies: crate::tiearb::TIEARB_MAX_PLIES,
            tiearb_threads: 1,
            wc_tiebreak: false,
        }
    }
}

/// The token that separates the human sentence from the machine payload in an
/// [`SearchError::EmptyMaskAtInterior`] message.  A RECORDED CONTRACT:
/// `carcassonne_ai.window_truncation.parse_diag` splits on exactly this.
pub const EMPTY_MASK_DIAG_MARKER: &str = "EMPTY_MASK_DIAG=";

#[derive(Debug)]
pub enum SearchError {
    Leaf(LeafError),
    Engine(String),
    /// `node.valid_actions[0]` on an empty list — the Python raises `IndexError`.
    ///
    /// Raised by [`Searcher::select_child_puct`], which sees only the node and
    /// so cannot say WHY the list is empty.  [`Searcher::simulate`] upgrades it
    /// to [`SearchError::EmptyMaskAtInterior`] on the way out, where the game
    /// state at the node is still in hand.  It therefore no longer escapes the
    /// search — the variant is kept so the bare (diagnosis-free) case remains
    /// representable.
    NoLegalActionsAtInterior,
    /// F-c (DESIGN §7): the same event, DIAGNOSED — carries the mask counters,
    /// the window, the descent that reached the node and the dropped placements,
    /// and says whether the window truncated the move list or something else did
    /// (`diag.cause`).
    EmptyMaskAtInterior(Box<EmptyMaskDiag>),
    /// `next(iter(root.children))` on an empty dict — the Python raises.
    NoRootChildren,
}

impl From<LeafError> for SearchError {
    fn from(e: LeafError) -> Self {
        SearchError::Leaf(e)
    }
}

impl std::fmt::Display for SearchError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SearchError::Leaf(e) => write!(f, "leaf error: {e:?}"),
            SearchError::Engine(s) => write!(f, "engine error: {s}"),
            SearchError::NoLegalActionsAtInterior => {
                write!(f, "PUCT reached a node with no valid actions (Python IndexError)")
            }
            // The leading clause is byte-identical to the bare variant above, on
            // purpose: `h2h.failed_record`, CONFIRM_EXCLUSIONS and every existing
            // grep key off that sentence.  Everything after it is additive.
            SearchError::EmptyMaskAtInterior(d) => write!(
                f,
                "PUCT reached a node with no valid actions (Python IndexError) \
                 [cause={} n_total={} n_overflow={} window={}@({},{}) depth={} phase={}] \
                 {}{}",
                d.cause.value(),
                d.n_total,
                d.n_overflow,
                d.window_size,
                d.origin_row,
                d.origin_col,
                d.depth,
                d.phase,
                EMPTY_MASK_DIAG_MARKER,
                d.to_json()
            ),
            SearchError::NoRootChildren => {
                write!(f, "root has no children (Python StopIteration)")
            }
        }
    }
}

/// `mcts._NeuralNode`.
pub struct Node {
    /// The `string_representation` bytes, heap-allocated **once** per node.
    /// `Tree::index` holds a refcount handle onto the same buffer (the tree is
    /// per-thread, so `Rc` suffices) — the 2026-08-02 review's finding #2 was
    /// three independent copies of a 1.2–5.0 KB key.
    pub key: Rc<str>,
    pub player_to_move: usize,
    pub is_terminal: bool,
    pub terminal_value: f64,
    pub expanded: bool,
    pub n: i64,
    pub w: f64,
    pub leaf_value: f64,
    /// Ascending (the `np.flatnonzero` order); `priors`/`prior_bonus`/`alias`
    /// are parallel to it.
    pub valid_actions: Vec<i32>,
    pub priors: Vec<f64>,
    pub prior_bonus: Vec<f64>,
    pub alias: Vec<bool>,
    /// Mirrors Python's truthiness test on the `prior_bonus` / `child_aliases`
    /// containers (`if prior_bonus:` / `if aliases:`).
    pub has_bonus: bool,
    pub has_alias: bool,
    /// `node.children` **insertion order** (observable via `best_action`).
    pub child_actions: Vec<i32>,
    pub children: HashMap<i32, NodeId, FxBuildHasher>,
    /// `id(child) -> representative action`.
    pub child_canon: HashMap<NodeId, i32, FxBuildHasher>,
}

impl Node {
    fn new(key: Rc<str>, player_to_move: usize, terminal_value: f64) -> Self {
        Node {
            key,
            player_to_move,
            is_terminal: terminal_value != 0.0,
            terminal_value,
            expanded: false,
            n: 0,
            w: 0.0,
            leaf_value: 0.0,
            valid_actions: Vec::new(),
            priors: Vec::new(),
            prior_bonus: Vec::new(),
            alias: Vec::new(),
            has_bonus: false,
            has_alias: false,
            child_actions: Vec::new(),
            children: HashMap::default(),
            child_canon: HashMap::default(),
        }
    }

    /// `_NeuralNode.Q`.
    #[inline]
    pub fn q(&self) -> f64 {
        if self.n > 0 {
            self.w / (self.n as f64)
        } else {
            0.0
        }
    }

    #[inline]
    fn action_index(&self, action: i32) -> Option<usize> {
        self.valid_actions.binary_search(&action).ok()
    }
}

/// `NeuralMCTS._nodes`.
#[derive(Default)]
pub struct Tree {
    pub nodes: Vec<Node>,
    index: HashMap<Rc<str>, NodeId, FxBuildHasher>,
}

impl Tree {
    pub fn len(&self) -> usize {
        self.nodes.len()
    }
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }
    pub fn get(&self, id: NodeId) -> &Node {
        &self.nodes[id as usize]
    }
    fn get_mut(&mut self, id: NodeId) -> &mut Node {
        &mut self.nodes[id as usize]
    }
    fn lookup(&self, key: &str) -> Option<NodeId> {
        self.index.get(key).copied()
    }
    /// `self._nodes.setdefault(fresh.state_key, fresh)`.
    fn intern(&mut self, node: Node) -> NodeId {
        if let Some(id) = self.index.get(node.key.as_ref()) {
            return *id;
        }
        let id = self.nodes.len() as NodeId;
        // Refcount handle onto the node's single key allocation, not a copy.
        self.index.insert(Rc::clone(&node.key), id);
        self.nodes.push(node);
        id
    }
}

/// The per-search result surface the reconcile gate compares.
pub struct SearchResult {
    pub chosen_action: i32,
    /// `(action, N, W)` for every entry of `root.children`, ascending by action.
    /// `W` is compared as raw bits by the gate.
    pub root_children: Vec<(i32, i64, f64)>,
    /// `_deduped_children(root)` — `(action, N, W)`.
    pub deduped: Vec<(i32, i64, f64)>,
    /// P4: `fair_agent.root_stats_list(root)` — deduped, `N>0`-filtered, and
    /// **root-POV-signed** `W`.  This is what the PIMC pool accumulates.
    pub pooled_stats: Vec<(i32, i64, f64)>,
    /// `root.player_to_move` — the POV `pooled_stats` is signed into.
    pub root_player: usize,
    pub root_n: i64,
    pub root_w: f64,
    pub root_leaf_value: f64,
    pub root_priors: Vec<(i32, f64)>,
    pub node_count: usize,
    pub leaf_evals: u64,
    /// S1 §9.2(c) — the J-rules-prior EXPANSION CENSUS for this search.
    /// All three are `0` unless `jrules_prior_dose != 0.0` (the counters live
    /// inside the dose branch so champion traffic is untouched).
    ///
    /// `jr_expansions_total` = every expansion the search performed;
    /// `jr_expansions_own_mover` = those whose mover IS the root player;
    /// `jr_expansions_boosted` = those the active scope actually boosted.
    ///
    /// The decomposition identity, checkable **within one tree** (and therefore
    /// exact, unlike a cross-scope set comparison, whose trees diverge the
    /// moment a prior moves):
    ///
    /// * `All` ⇒ `boosted == total`
    /// * `Own` ⇒ `boosted == own_mover`
    /// * `Opp` ⇒ `boosted == total - own_mover`
    ///
    /// i.e. `Own` and `Opp` boost disjoint sets whose union is `All`'s.
    pub jr_expansions_total: u64,
    pub jr_expansions_own_mover: u64,
    pub jr_expansions_boosted: u64,
}

/// S1 §9.2(c) — the J-rules-prior expansion census SUMMED over many searches.
///
/// [`SearchResult`] carries the census of ONE tree, and one tree is not a unit
/// anybody can read a cell off: a PIMC decision searches `k_dets` determinized
/// worlds and a game makes dozens of decisions.  The play-derived witness a
/// cell needs is therefore a SUM — this type, folded world -> decision -> game
/// ([`crate::fair::search_worlds`] then [`crate::fair::FairAgent`]).
///
/// The counters are plain counts over DISJOINT trees, so they add, and the
/// per-tree decomposition identity survives the summation term by term:
///
/// * `All` ⇒ `boosted == total`
/// * `Own` ⇒ `boosted == own_mover`
/// * `Opp` ⇒ `boosted == total - own_mover`
///
/// ⚠️ All three stay 0 whenever `jrules_prior_dose == 0.0` (the champion) —
/// the per-tree counters live INSIDE the dose branch so champion traffic keeps
/// its pre-change short-circuit.  An unarmed side's readable invariant is
/// therefore `boosted == 0`, not `total > 0`.
#[derive(Default, Clone, Copy, Debug, PartialEq, Eq)]
pub struct JrExpansions {
    pub total: u64,
    pub own_mover: u64,
    pub boosted: u64,
}

impl JrExpansions {
    /// The census of one finished search.
    pub fn of(r: &SearchResult) -> Self {
        JrExpansions {
            total: r.jr_expansions_total,
            own_mover: r.jr_expansions_own_mover,
            boosted: r.jr_expansions_boosted,
        }
    }

    /// Fold another census in (world -> decision -> game).
    pub fn add(&mut self, o: JrExpansions) {
        self.total += o.total;
        self.own_mover += o.own_mover;
        self.boosted += o.boosted;
    }
}

pub struct Searcher<'a> {
    pub cfg: &'a SearchConfig,
    pub tree: Tree,
    pub leaf_evals: u64,
    /// One reusable decomposition buffer for the whole search — the P2 perf
    /// lever (~27 KB of buffer churn per leaf call, at tens of leaf calls per
    /// node expansion).
    scratch: LeafScratch,
    /// The seat this search() call is FOR — latched at [`Searcher::search`],
    /// read ONLY by the J-rules prior surface under
    /// [`JrPriorScope::Own`] and [`JrPriorScope::Opp`]. `None` until a search
    /// starts.
    root_player: Option<usize>,
    /// S1 §9.2(c) expansion census — see [`SearchResult::jr_expansions_total`].
    /// Reset at every [`Searcher::search`] entry so a reused `Searcher`
    /// reports PER-SEARCH counts, exactly like `root_player`'s latch.
    jr_expansions_total: u64,
    jr_expansions_own_mover: u64,
    jr_expansions_boosted: u64,
    /// J-RULES ROOT FILTER surface C: when set (only ever by
    /// [`Searcher::search_with_root_allow`], only ever by the fair agent), the
    /// ROOT node's legal-action set is restricted to this list BEFORE the prior
    /// softmax — the dropped actions are, to this search, illegal at the root.
    /// Interior nodes are NEVER touched. `None` (the default and the champion)
    /// is the pre-change code path, byte-for-byte.
    root_allow: Option<Vec<i32>>,
    trace: Option<&'a mut dyn TraceSink>,
}

impl<'a> Searcher<'a> {
    pub fn new(cfg: &'a SearchConfig) -> Self {
        Searcher {
            cfg,
            tree: Tree::default(),
            leaf_evals: 0,
            scratch: LeafScratch::new(),
            root_player: None,
            jr_expansions_total: 0,
            jr_expansions_own_mover: 0,
            jr_expansions_boosted: 0,
            root_allow: None,
            trace: None,
        }
    }

    pub fn with_trace(cfg: &'a SearchConfig, trace: &'a mut dyn TraceSink) -> Self {
        Searcher {
            cfg,
            tree: Tree::default(),
            leaf_evals: 0,
            scratch: LeafScratch::new(),
            root_player: None,
            jr_expansions_total: 0,
            jr_expansions_own_mover: 0,
            jr_expansions_boosted: 0,
            root_allow: None,
            trace: Some(trace),
        }
    }

    // -- leaf / value primitives ------------------------------------------- //

    #[inline]
    fn leaf_at(&mut self, g: &Game, player: usize) -> Result<f64, SearchError> {
        self.leaf_evals += 1;
        Ok(match (self.cfg.leaf_quantize, self.cfg.use_leaf_scratch) {
            (LeafQuantize::Float, true) => {
                self.scratch.leaf_value_float(&g.state, player, &self.cfg.leaf)?
            }
            (LeafQuantize::Float, false) => {
                leaf::leaf_value_float(&g.state, player, &self.cfg.leaf)?
            }
            // `float(flat_virtual_score_v2(...))`
            (LeafQuantize::Int, true) => {
                self.scratch.leaf_value(&g.state, player, &self.cfg.leaf)? as f64
            }
            (LeafQuantize::Int, false) => {
                leaf::leaf_value(&g.state, player, &self.cfg.leaf)? as f64
            }
        })
    }

    #[inline]
    fn tanh(&self, x: f64) -> f64 {
        compat::tanh64_flavor(x, self.cfg.tanh_flavor)
    }

    #[inline]
    fn exp(&self, x: f64) -> f64 {
        if self.cfg.exp_fma {
            compat::exp64_fma(x)
        } else {
            compat::exp64(x)
        }
    }

    /// `game_wrapper.Game.get_game_ended(board, player)`.
    ///
    /// The tie branch (`v == 0.0`, an exact `tanh` zero) is the WC tie-break
    /// seam: unarmed it is the symmetric draw sentinel (`1e-6` / `-1e-6`,
    /// signed so `player == 0` is positive); armed
    /// ([`SearchConfig::wc_tiebreak`]) it SIGN-FLIPS to `-1e-6` for player 0
    /// and `1e-6` for player 1 — a tied final score is a loss for the
    /// starting player (P0), not a draw. Byte-for-byte port of
    /// `game_wrapper.Game.get_game_ended`'s armed branch. The magnitude stays
    /// epsilon in both readings (untouched, unarmed literals for `false`) —
    /// this is a *margin*-flavored tanh value and inflating it would corrupt
    /// the margin scale.
    fn game_ended(&self, g: &Game, player: usize) -> f64 {
        if !g.state.is_terminated() {
            return 0.0;
        }
        let opp = 1 - player;
        let diff = (g.state.scores[player] - g.state.scores[opp]) as f64;
        let v = self.tanh(diff / self.cfg.score_norm_scale);
        if v == 0.0 {
            if self.cfg.wc_tiebreak {
                if player == 0 {
                    -1e-6
                } else {
                    1e-6
                }
            } else if player == 0 {
                1e-6
            } else {
                -1e-6
            }
        } else {
            v
        }
    }

    // -- the evaluator ------------------------------------------------------ //

    /// `heuristic_prior_mcts.make_heuristic_prior_evaluator`'s closure:
    /// returns `(legal, priors_over_legal_f32, value)`.
    ///
    /// `at_root` is true ONLY for the root expansion driven by
    /// [`Searcher::search`] — it gates the J-rules ROOT-FILTER restriction
    /// (surface C), which must never reach an interior node. With
    /// `root_allow == None` (the default and the champion) the flag is inert
    /// and this is the pre-change code, byte-for-byte.
    fn evaluate(
        &mut self,
        g: &Game,
        at_root: bool,
    ) -> Result<(Vec<i32>, Vec<f32>, f64), SearchError> {
        let mover = g.state.current_player;
        let leaf_parent = self.leaf_at(g, mover)?;
        let mut legal = g.legal_actions();
        if at_root {
            if let Some(allow) = &self.root_allow {
                // Surface C: the dropped root actions are, to this search,
                // illegal — the prior softmax renormalizes over the survivors
                // and no simulation can ever visit a dropped action.
                legal.retain(|a| allow.contains(a));
                if legal.is_empty() {
                    // The fair agent's never-empty guard makes this unreachable;
                    // if it ever fires, something upstream broke — fail loud.
                    return Err(SearchError::Engine(
                        "jrules root filter emptied the root candidate set \
                         (the fair agent's min_keep guard should have yielded)"
                            .into(),
                    ));
                }
            }
        }

        // J-RULES PRIOR surface B: dose 0.0 (the default, the champion) takes
        // the pre-change loop verbatim — this whole block is behind the dose
        // test, so default traffic is bit-identical, not merely equal. Nonzero:
        // the clock is read ONCE from THIS node (the bot's own fair-information
        // rule — blind to what a lookahead draws), and each child's Δleaf gets
        // `dose * jrules_prior_term(child)` added before the softmax. Only the
        // PRIORS move; `leaf_parent`, `value` and everything backed up do not.
        //
        // S1: the three scopes partition the expansion population by whether
        // the node's mover is the root player. The census counters below are
        // the machine-checkable form of that partition (DESIGN §9.2 leg (c));
        // they are maintained ONLY inside the dose!=0 branch, so dose-0
        // (champion) traffic keeps the pre-change short-circuit untouched.
        let jr_on = if self.cfg.jrules_prior_dose != 0.0 {
            let own_node = self.root_player == Some(mover);
            let on = match self.cfg.jrules_prior_scope {
                JrPriorScope::All => true,
                JrPriorScope::Own => own_node,
                JrPriorScope::Opp => !own_node,
            };
            self.jr_expansions_total += 1;
            if own_node {
                self.jr_expansions_own_mover += 1;
            }
            if on {
                self.jr_expansions_boosted += 1;
            }
            on
        } else {
            false
        };
        let jr_clock = if jr_on {
            // Re-decompose the PARENT (the child loop overwrites the scratch
            // decomp per child) — one extra decomposition per expansion.
            leaf::decompose_into(&g.state, &mut self.scratch.decomp, &mut self.scratch.scratch);
            Some(leaf::jr_prior_clock(&g.state, mover, &self.scratch.decomp))
        } else {
            None
        };

        // ── L1a: THE MEEPLE-PHASE DECOMPOSITION HOIST ──────────────────────
        //
        // [`leaf::decompose_into`] is a pure function of the TILE BOARD: it
        // reads `state.placed_coords` and `state.board` and nothing else — no
        // meeple, no score, no phase, no deck field appears anywhere in its
        // body. A parent in [`Phase::Meeples`] has only `Action::Meeple` and
        // `Action::Pass` legal, and neither places a tile (`apply_action`:
        // `Meeple => play_meeple`, and the meeple-phase `Pass` falls straight
        // through to `remove_meeples_and_collect_points` / `draw_tile` /
        // `next_player`). So EVERY child of a meeple-phase node has, bit for
        // bit, its parent's decomposition, and the per-child `decompose_into`
        // is redundant work — 52.9–60.5% of PUCT search time is in that one
        // function (eval-perf sweep, 2026-08-30).
        //
        // Bit-identity is therefore by CONSTRUCTION, not by measurement; the
        // measurement (3,104/3,104 children in the sweep, re-run here as
        // `every_meeple_phase_child_shares_its_parents_decomposition`, plus the
        // leaf-VALUE gate `the_meeple_phase_hoist_is_leaf_value_identical`) is
        // the falsifier, not the argument. No knob: there is no shape to choose
        // between, so no config field and no strength claim (the tier1-swap
        // precedent).
        //
        // ⚠️ This adds CALL-SITE logic only. `decompose_into`'s interface is
        // untouched on purpose — the L1 delta-decompose spike restructures the
        // function itself, and the two changes must compose.
        let hoist = g.state.phase == Phase::Meeples && !force_fresh_decomp();
        if hoist && !jr_on && !self.cfg.use_leaf_scratch {
            // The only route that leaves `scratch.decomp` NOT holding this
            // node's decomposition: `leaf_at` took the allocating free
            // function and never touched the scratch. (`use_leaf_scratch`
            // true ⇒ `leaf_at` just decomposed `g.state` into it; `jr_on`
            // ⇒ the clock block above did.)
            leaf::decompose_into(&g.state, &mut self.scratch.decomp, &mut self.scratch.scratch);
        }
        let quantize_int = self.cfg.leaf_quantize == LeafQuantize::Int;

        // deltas[i] = leaf(child_i, mover) - leaf_parent, in `legal` order.
        let mut deltas: Vec<f64> = Vec::with_capacity(legal.len());
        for &a in &legal {
            let mut child = g.clone();
            child.advance(a).map_err(SearchError::Engine)?;
            match &jr_clock {
                None if hoist => {
                    // Same `leaf_terms_with` the scratch path funnels through,
                    // against the parent's decomposition — which IS the
                    // child's. `self.scratch.decomp` is NOT overwritten in this
                    // loop, so it stays valid for every sibling.
                    self.leaf_evals += 1;
                    let t = leaf::leaf_terms_with(
                        &child.state,
                        mover,
                        &self.cfg.leaf,
                        &self.scratch.decomp,
                    )?;
                    let leaf_v = if quantize_int { t.value as f64 } else { t.score };
                    deltas.push(leaf_v - leaf_parent);
                }
                None => deltas.push(self.leaf_at(&child, mover)? - leaf_parent),
                Some(clock) => {
                    // One decomposition serves the leaf AND the prior term.
                    // The leaf component is the same `leaf_terms_with` the
                    // plain path funnels through — bit-identical by
                    // construction; only the prior-softmax input moves.
                    self.leaf_evals += 1;
                    let (leaf_v, base) = if hoist {
                        // Hoisted: the parent decomp already in the scratch is
                        // the child's, so BOTH the leaf and the prior term read
                        // it — one decomposition for the whole expansion
                        // instead of one per child.
                        let t = leaf::leaf_terms_with(
                            &child.state,
                            mover,
                            &self.cfg.leaf,
                            &self.scratch.decomp,
                        )?;
                        (
                            if quantize_int { t.value as f64 } else { t.score },
                            t.base as f64,
                        )
                    } else {
                        self.scratch.leaf_float_and_base(
                            &child.state,
                            mover,
                            &self.cfg.leaf,
                            quantize_int,
                        )?
                    };
                    let t = leaf::jrules_prior_term(
                        &child.state,
                        mover,
                        &self.scratch.decomp,
                        self.cfg.jrules_prior_mask,
                        clock,
                        base,
                    );
                    deltas.push(leaf_v - leaf_parent + self.cfg.jrules_prior_dose * t);
                }
            }
        }

        let value = self.tanh(leaf_parent / self.cfg.value_norm);
        if legal.is_empty() {
            return Ok((legal, Vec::new(), value));
        }

        // z = deltas / tau ; z -= z.max() ; w = np.exp(z) ; w /= w.sum()
        let tau = self.cfg.tau_p;
        let mut z: Vec<f64> = deltas.iter().map(|d| d / tau).collect();
        let mut mx = f64::NEG_INFINITY;
        for &v in &z {
            if v > mx {
                mx = v;
            }
        }
        for v in z.iter_mut() {
            *v -= mx;
        }
        let mut w: Vec<f64> = z.iter().map(|&v| self.exp(v)).collect();
        let s = compat::np_sum_f64(&w);
        for v in w.iter_mut() {
            *v /= s;
        }
        // priors[legal] = w.astype(np.float32)
        let priors: Vec<f32> = w.iter().map(|&v| v as f32).collect();
        Ok((legal, priors, value))
    }

    // -- expansion ---------------------------------------------------------- //

    /// `_expand` + `_expand_with_priors`.
    ///
    /// `via_f32` reproduces the ROOT-ONLY `float32` round-trip that
    /// `_eval_boards` puts the value through (`np.array(values, float32)`).
    /// `at_root` (true only from [`Searcher::search`]'s root expansion) gates
    /// the surface-C root-filter restriction in [`Searcher::evaluate`]; it is
    /// carried separately from `via_f32` (which happens to coincide) so the
    /// two root-only behaviours cannot silently drift apart.
    fn expand(
        &mut self,
        id: NodeId,
        g: &Game,
        via_f32: bool,
        at_root: bool,
    ) -> Result<(), SearchError> {
        if self.tree.get(id).expanded {
            return Ok(());
        }
        if self.tree.get(id).is_terminal {
            let tv = self.tree.get(id).terminal_value;
            let n = self.tree.get_mut(id);
            n.leaf_value = tv;
            n.expanded = true;
            self.trace_expand(id);
            return Ok(());
        }
        let (legal, priors_f32, value_raw) = self.evaluate(g, at_root)?;

        if legal.is_empty() {
            let n = self.tree.get_mut(id);
            n.leaf_value = 0.0;
            n.expanded = true;
            self.trace_expand(id);
            return Ok(());
        }

        // --- prior sanitization (shape/finite/non-negative/sum) ------------ //
        let mut priors_ok = priors_f32.iter().all(|p| p.is_finite() && *p >= 0.0);
        let mut s_f64 = 0.0f64;
        if priors_ok {
            // `float(legal_priors.sum())` — numpy PAIRWISE float32 reduction.
            s_f64 = compat::np_sum_f32(&priors_f32) as f64;
            if s_f64 <= 0.0 || !s_f64.is_finite() {
                priors_ok = false;
            }
        }
        let legal_priors: Vec<f32> = if priors_ok {
            // NEP-50: float32 array / weak python float -> float32.
            let s32 = s_f64 as f32;
            priors_f32.iter().map(|p| p / s32).collect()
        } else {
            let u = (1.0f64 / legal.len() as f64) as f32;
            vec![u; legal.len()]
        };

        // --- value sanitization ------------------------------------------- //
        let mut v = if via_f32 {
            (value_raw as f32) as f64
        } else {
            value_raw
        };
        if !v.is_finite() {
            v = 0.0;
        }
        v = v.clamp(-1.0, 1.0);

        let n_legal = legal.len();
        let node = self.tree.get_mut(id);
        node.valid_actions = legal;
        node.priors = legal_priors.iter().map(|&p| p as f64).collect();
        node.prior_bonus = vec![0.0; n_legal];
        node.alias = vec![false; n_legal];
        node.leaf_value = v;
        node.expanded = true;
        self.trace_expand(id);
        Ok(())
    }

    /// `_create_node` + `_nodes.setdefault`.
    fn create_or_get(&mut self, g: &Game) -> NodeId {
        let key = g.string_repr();
        if let Some(id) = self.tree.lookup(&key) {
            return id;
        }
        let player = g.state.current_player;
        let tv = self.game_ended(g, player);
        self.tree.intern(Node::new(Rc::from(key), player, tv))
    }

    // -- selection ---------------------------------------------------------- //

    /// `_select_child_puct`.
    fn select_child_puct(&self, id: NodeId) -> Result<i32, SearchError> {
        let node = self.tree.get(id);
        if node.valid_actions.is_empty() {
            return Err(SearchError::NoLegalActionsAtInterior);
        }
        let sqrt_parent_n = (node.n.max(1) as f64).sqrt();
        let mut best_action = node.valid_actions[0];
        let mut best_score = f64::NEG_INFINITY;
        let node_q = node.q();
        for (i, &action) in node.valid_actions.iter().enumerate() {
            if node.has_alias && node.alias[i] {
                continue;
            }
            let (q, n) = match node.children.get(&action) {
                None => (
                    match self.cfg.fpu_reduction {
                        None => 0.0,
                        Some(r) => node_q - r,
                    },
                    0i64,
                ),
                Some(&cid) => {
                    let c = self.tree.get(cid);
                    let cq = c.q();
                    (
                        if c.player_to_move == node.player_to_move {
                            cq
                        } else {
                            -cq
                        },
                        c.n,
                    )
                }
            };
            let mut p = node.priors[i];
            if node.has_bonus {
                p += node.prior_bonus[i];
            }
            let u = self.cfg.c_puct * p * sqrt_parent_n / ((1 + n) as f64);
            let score = q + u;
            if score > best_score {
                best_score = score;
                best_action = action;
            }
        }
        Ok(best_action)
    }

    /// `_link_child` — the transposition-alias structure.
    ///
    /// ```python
    /// node.children[action] = child
    /// canon = node.child_canon.get(id(child))
    /// if canon is None:            node.child_canon[id(child)] = action
    /// elif canon != action and action not in node.child_aliases:
    ///     node.child_aliases.add(action)
    ///     node.prior_bonus[canon] = node.prior_bonus.get(canon, 0.0) \
    ///                             + node.priors.get(action, 0.0)
    /// ```
    fn link_child(&mut self, parent: NodeId, action: i32, child: NodeId) {
        let p = self.tree.get_mut(parent);
        if !p.children.contains_key(&action) {
            p.child_actions.push(action);
        }
        p.children.insert(action, child);
        let canon = p.child_canon.get(&child).copied();
        let Some(canon) = canon else {
            p.child_canon.insert(child, action);
            return;
        };
        let ai = p.action_index(action);
        // `action in node.child_aliases`
        let already_alias = matches!(ai, Some(i) if p.alias[i]);
        if canon == action || already_alias {
            return;
        }
        if let Some(i) = ai {
            p.alias[i] = true;
        }
        // Python adds to the SET regardless of whether the action carries a
        // prior slot, so the `if aliases:` truthiness flips either way.
        p.has_alias = true;
        // `node.priors.get(action, 0.0)`
        let add = match ai {
            Some(i) => p.priors[i],
            None => 0.0,
        };
        if let Some(ci) = p.action_index(canon) {
            p.prior_bonus[ci] += add;
        }
        p.has_bonus = true;
    }

    // -- one simulation ------------------------------------------------------ //

    /// `_simulate` (serial, `forced_root_action=None`).
    fn simulate(&mut self, root_game: &Game, root: NodeId, sim_idx: usize) -> Result<(), SearchError> {
        let mut path: Vec<NodeId> = vec![root];
        let mut acts: Vec<i32> = Vec::new();
        let mut g = root_game.clone();
        let mut node = root;

        while self.tree.get(node).expanded && !self.tree.get(node).is_terminal {
            // F-c (DESIGN §7).  The Ok arm is the pre-fix `?` verbatim — the only
            // change is that the ERROR arm now stops to say why, while `g` (the
            // state AT this node) is still in hand.  Nothing here runs unless the
            // search is already dead, so the no-fire path is untouched.
            let action = match self.select_child_puct(node) {
                Ok(a) => a,
                Err(SearchError::NoLegalActionsAtInterior) => {
                    return Err(SearchError::EmptyMaskAtInterior(Box::new(
                        EmptyMaskDiag::collect(&g, &acts, sim_idx),
                    )));
                }
                Err(e) => return Err(e),
            };
            g.advance(action).map_err(SearchError::Engine)?;
            acts.push(action);
            let existing = self.tree.get(node).children.get(&action).copied();
            match existing {
                Some(child) => {
                    path.push(child);
                    node = child;
                }
                None => {
                    let child = self.create_or_get(&g);
                    if !self.tree.get(child).expanded {
                        self.expand(child, &g, false, false)?;
                    }
                    self.link_child(node, action, child);
                    path.push(child);
                    node = child;
                    break;
                }
            }
        }

        let leaf_value = self.tree.get(node).leaf_value;
        let leaf_player = self.tree.get(node).player_to_move;
        for &nid in &path {
            let n = self.tree.get_mut(nid);
            n.n += 1;
            n.w += if n.player_to_move == leaf_player {
                leaf_value
            } else {
                -leaf_value
            };
        }
        self.trace_sim(sim_idx, &path, &acts, leaf_value);
        Ok(())
    }

    // -- the driver ---------------------------------------------------------- //

    /// `NeuralMCTS.search` + `HeuristicPriorAgent.best_action` on a fresh tree
    /// (`reuse_tree=False` ⇒ `clear()` before every move).
    pub fn search(&mut self, root_game: &Game) -> Result<SearchResult, SearchError> {
        // Latched per search() call (covers the session's search_carry too,
        // which drives this same entry point). Only JrPriorScope::Own and
        // JrPriorScope::Opp read it.
        self.root_player = Some(root_game.state.current_player);
        // S1 §9.2(c): the census is PER SEARCH, latched alongside root_player
        // (a reused Searcher must not report a running total).
        self.jr_expansions_total = 0;
        self.jr_expansions_own_mover = 0;
        self.jr_expansions_boosted = 0;
        let root = self.create_or_get(root_game);
        if !self.tree.get(root).expanded && !self.tree.get(root).is_terminal {
            // `_eval_boards` -> float32 values array -> `float(values_b[0])`.
            self.expand(root, root_game, true, true)?;
        }
        for i in 0..self.cfg.simulations {
            self.simulate(root_game, root, i)?;
        }
        self.finish(root)
    }

    /// [`Searcher::search`] with a ROOT-only action allowlist — the J-rules
    /// ROOT-FILTER (surface C) entry point, used ONLY by
    /// [`crate::fair::FairAgent::pimc_move`]. `None` is byte-for-byte
    /// [`Searcher::search`] (the same code path, not a parallel one).
    pub fn search_with_root_allow(
        &mut self,
        root_game: &Game,
        root_allow: Option<&[i32]>,
    ) -> Result<SearchResult, SearchError> {
        self.root_allow = root_allow.map(|a| a.to_vec());
        let r = self.search(root_game);
        self.root_allow = None;
        r
    }

    fn finish(&mut self, root: NodeId) -> Result<SearchResult, SearchError> {
        let chosen = self.final_action(root)?;
        let pooled_stats = self.root_stats(root);
        let r = self.tree.get(root);
        let mut acts: Vec<i32> = r.children.keys().copied().collect();
        acts.sort_unstable();
        let root_children: Vec<(i32, i64, f64)> = acts
            .iter()
            .map(|&a| {
                let c = self.tree.get(r.children[&a]);
                (a, c.n, c.w)
            })
            .collect();
        let deduped: Vec<(i32, i64, f64)> = self
            .deduped_children(root)
            .into_iter()
            .map(|(a, id)| {
                let c = self.tree.get(id);
                (a, c.n, c.w)
            })
            .collect();
        Ok(SearchResult {
            chosen_action: chosen,
            root_children,
            deduped,
            pooled_stats,
            root_player: r.player_to_move,
            root_n: r.n,
            root_w: r.w,
            root_leaf_value: r.leaf_value,
            root_priors: r
                .valid_actions
                .iter()
                .copied()
                .zip(r.priors.iter().copied())
                .collect(),
            node_count: self.tree.len(),
            leaf_evals: self.leaf_evals,
            jr_expansions_total: self.jr_expansions_total,
            jr_expansions_own_mover: self.jr_expansions_own_mover,
            jr_expansions_boosted: self.jr_expansions_boosted,
        })
    }

    /// `fair_agent.root_stats_list(root)` — **the P4 pooling surface**.
    ///
    /// P3 left this as the one named gap: [`SearchResult::root_children`] carries
    /// `W` in the CHILD's own POV, and a root child is *not* always the
    /// opponent's turn (the tile→meeple phase keeps the mover), so the PIMC
    /// pooled merge needs the ROOT-POV-signed value.  Ported verbatim:
    ///
    /// ```python
    /// for a in sorted(root.children):
    ///     ch = root.children[a]
    ///     if ch.N <= 0 or id(ch) in seen: continue
    ///     seen.add(id(ch))
    ///     sw = ch.W if ch.player_to_move == root.player_to_move else -ch.W
    ///     out.append((a, ch.N, sw))
    /// ```
    ///
    /// Note the short-circuit ORDER: an `N <= 0` child is skipped *before* it is
    /// marked seen (immaterial in practice — aliases share one node, hence one
    /// `N` — but ported as written).
    pub fn root_stats(&self, root: NodeId) -> Vec<(i32, i64, f64)> {
        let r = self.tree.get(root);
        let mut acts: Vec<i32> = r.children.keys().copied().collect();
        acts.sort_unstable();
        let mut seen: HashSet<NodeId> = HashSet::new();
        let mut out = Vec::with_capacity(acts.len());
        for a in acts {
            let cid = r.children[&a];
            let c = self.tree.get(cid);
            if c.n <= 0 {
                continue;
            }
            if !seen.insert(cid) {
                continue;
            }
            let sw = if c.player_to_move == r.player_to_move {
                c.w
            } else {
                -c.w
            };
            out.push((a, c.n, sw));
        }
        out
    }

    /// `_deduped_children` — sorted by action, first action to reach a given
    /// child object wins (Python compares `id(child)`).
    pub fn deduped_children(&self, root: NodeId) -> Vec<(i32, NodeId)> {
        let r = self.tree.get(root);
        let mut acts: Vec<i32> = r.children.keys().copied().collect();
        acts.sort_unstable();
        let mut seen: HashSet<NodeId> = HashSet::new();
        let mut out = Vec::new();
        for a in acts {
            let c = r.children[&a];
            if seen.insert(c) {
                out.push((a, c));
            }
        }
        out
    }

    fn final_action(&self, root: NodeId) -> Result<i32, SearchError> {
        match self.cfg.final_select {
            FinalSelect::Visits => {
                // `int(actions[int(np.argmax(counts))])` — argmax takes the FIRST max.
                let items = self.deduped_children(root);
                if items.is_empty() {
                    return Err(SearchError::NoRootChildren);
                }
                let mut best = items[0].0;
                let mut best_n = self.tree.get(items[0].1).n;
                for &(a, id) in items.iter().skip(1) {
                    let n = self.tree.get(id).n;
                    if n > best_n {
                        best_n = n;
                        best = a;
                    }
                }
                Ok(best)
            }
            FinalSelect::Q => {
                let r = self.tree.get(root);
                let items: Vec<(i32, NodeId)> = self
                    .deduped_children(root)
                    .into_iter()
                    .filter(|&(_, id)| self.tree.get(id).n > 0)
                    .collect();
                if items.is_empty() {
                    // `next(iter(root.children))` — dict INSERTION order.
                    return r
                        .child_actions
                        .first()
                        .copied()
                        .ok_or(SearchError::NoRootChildren);
                }
                let score = |id: NodeId| -> (f64, i64) {
                    let c = self.tree.get(id);
                    let q = if c.player_to_move == r.player_to_move {
                        c.q()
                    } else {
                        -c.q()
                    };
                    (q, c.n)
                };
                let mut best = items[0].0;
                let mut best_s = score(items[0].1);
                for &(a, id) in items.iter().skip(1) {
                    let s = score(id);
                    // `max(..., key=score)` keeps the FIRST maximum.
                    if s.0 > best_s.0 || (s.0 == best_s.0 && s.1 > best_s.1) {
                        best_s = s;
                        best = a;
                    }
                }
                Ok(best)
            }
            FinalSelect::Lcb => {
                let r = self.tree.get(root);
                let items: Vec<(i32, NodeId)> = self
                    .deduped_children(root)
                    .into_iter()
                    .filter(|&(_, id)| self.tree.get(id).n > 0)
                    .collect();
                if items.is_empty() {
                    return r
                        .child_actions
                        .first()
                        .copied()
                        .ok_or(SearchError::NoRootChildren);
                }
                let total_n: i64 = items.iter().map(|&(_, id)| self.tree.get(id).n).sum();
                let log_total = if total_n > 0 {
                    (total_n as f64).ln()
                } else {
                    0.0
                };
                let mut best_a: Option<i32> = None;
                let mut best_score = f64::NEG_INFINITY;
                for &(a, id) in &items {
                    let c = self.tree.get(id);
                    let q = if c.player_to_move == r.player_to_move {
                        c.q()
                    } else {
                        -c.q()
                    };
                    let lcb = q - self.cfg.c_lcb * (log_total / c.n as f64).sqrt();
                    if lcb > best_score {
                        best_score = lcb;
                        best_a = Some(a);
                    }
                }
                best_a.ok_or(SearchError::NoRootChildren)
            }
        }
    }

    // -- trace hooks ---------------------------------------------------------- //

    fn trace_expand(&mut self, id: NodeId) {
        let sink: &mut dyn TraceSink = match self.trace.as_mut() {
            None => return,
            Some(s) => &mut **s,
        };
        let n = &self.tree.nodes[id as usize];
        // `sha256(key)[:16]` — a pure function of `node.key`, so the trace format
        // is unchanged; computed HERE (sink attached) instead of for every node
        // of every production search, which never has a sink.
        let digest = node_digest(&n.key);
        sink.expand(&trace::ExpandRecord {
            digest: &digest,
            player_to_move: n.player_to_move,
            is_terminal: n.is_terminal,
            terminal_value: n.terminal_value,
            leaf_value: n.leaf_value,
            valid_actions: &n.valid_actions,
            priors: &n.priors,
        });
    }

    fn trace_sim(&mut self, sim: usize, path: &[NodeId], acts: &[i32], leaf_value: f64) {
        let sink: &mut dyn TraceSink = match self.trace.as_mut() {
            None => return,
            Some(s) => &mut **s,
        };
        let nodes = &self.tree.nodes;
        let owned: Vec<String> = path
            .iter()
            .map(|&i| node_digest(&nodes[i as usize].key))
            .collect();
        let digests: Vec<&str> = owned.iter().map(String::as_str).collect();
        let nw: Vec<(i64, f64)> = path
            .iter()
            .map(|&i| (nodes[i as usize].n, nodes[i as usize].w))
            .collect();
        sink.sim(&trace::SimRecord {
            sim,
            path: &digests,
            actions: acts,
            leaf_value,
            nw: &nw,
        });
    }
}

/// One-shot convenience: run a single-world search on `g` and return the result.
pub fn search_single(g: &Game, cfg: &SearchConfig) -> Result<SearchResult, SearchError> {
    Searcher::new(cfg).search(g)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn small_cfg(sims: usize) -> SearchConfig {
        SearchConfig {
            simulations: sims,
            ..SearchConfig::default()
        }
    }

    #[test]
    fn root_visits_equal_sims_on_a_fresh_tree() {
        let g = Game::from_seed("1");
        let cfg = small_cfg(32);
        let mut s = Searcher::new(&cfg);
        let r = s.search(&g).unwrap();
        assert_eq!(r.root_n, 32);
        // every simulation visits exactly one root child edge
        let total: i64 = r.deduped.iter().map(|&(_, n, _)| n).sum();
        assert_eq!(total, 32);
    }

    #[test]
    fn a_forced_first_move_is_the_only_choice() {
        let g = Game::from_seed("1");
        let cfg = small_cfg(8);
        let r = search_single(&g, &cfg).unwrap();
        assert_eq!(r.root_priors.len(), 1);
        assert_eq!(r.root_children.len(), 1);
    }

    /// The scratch lever must be a PURE perf change: identical trees.
    #[test]
    fn leaf_scratch_does_not_change_the_search() {
        let mut g = Game::from_seed("28000000000");
        for _ in 0..55 {
            let legal = g.legal_actions();
            g.advance(legal[legal.len() / 2]).unwrap();
        }
        let a = search_single(&g, &small_cfg(256)).unwrap();
        let b = search_single(&g, &SearchConfig {
            use_leaf_scratch: false,
            ..small_cfg(256)
        }).unwrap();
        assert_eq!(a.chosen_action, b.chosen_action);
        assert_eq!(a.node_count, b.node_count);
        assert_eq!(a.root_w.to_bits(), b.root_w.to_bits());
        for (x, y) in a.root_children.iter().zip(b.root_children.iter()) {
            assert_eq!((x.0, x.1, x.2.to_bits()), (y.0, y.1, y.2.to_bits()));
        }
    }

    /// `cargo test --release -p carc-core -- --ignored --nocapture bench_search_scratch_ab`
    #[test]
    #[ignore]
    fn bench_search_scratch_ab() {
        use std::time::Instant;
        let mut g = Game::from_seed("28000000000");
        for _ in 0..55 {
            let legal = g.legal_actions();
            g.advance(legal[legal.len() / 2]).unwrap();
        }
        let sims = 1376;
        let on = small_cfg(sims);
        let off = SearchConfig { use_leaf_scratch: false, ..small_cfg(sims) };
        // warm both paths
        let _ = search_single(&g, &small_cfg(64)).unwrap();
        let reps = 6;
        let t = Instant::now();
        for _ in 0..reps { search_single(&g, &off).unwrap(); }
        let t_off = t.elapsed().as_secs_f64() / reps as f64;
        let t2 = Instant::now();
        for _ in 0..reps { search_single(&g, &on).unwrap(); }
        let t_on = t2.elapsed().as_secs_f64() / reps as f64;
        println!("search {sims} sims: alloc-leaf {:.0} sims/s, scratch-leaf {:.0} sims/s, \
                  speedup {:.3}x", sims as f64 / t_off, sims as f64 / t_on, t_off / t_on);
    }

    fn midgame(seed: &str, plies: usize) -> Game {
        let mut g = Game::from_seed(seed);
        for _ in 0..plies {
            let legal = g.legal_actions();
            g.advance(legal[legal.len() / 2]).unwrap();
        }
        g
    }

    fn assert_same_search(a: &SearchResult, b: &SearchResult) {
        assert_eq!(a.chosen_action, b.chosen_action);
        assert_eq!(a.node_count, b.node_count);
        assert_eq!(a.leaf_evals, b.leaf_evals);
        assert_eq!(a.root_w.to_bits(), b.root_w.to_bits());
        assert_eq!(a.root_leaf_value.to_bits(), b.root_leaf_value.to_bits());
        assert_eq!(a.root_children.len(), b.root_children.len());
        for (x, y) in a.root_children.iter().zip(b.root_children.iter()) {
            assert_eq!((x.0, x.1, x.2.to_bits()), (y.0, y.1, y.2.to_bits()));
        }
        assert_eq!(a.root_priors.len(), b.root_priors.len());
        for (x, y) in a.root_priors.iter().zip(b.root_priors.iter()) {
            assert_eq!((x.0, x.1.to_bits()), (y.0, y.1.to_bits()));
        }
    }

    /// Surface B's own gate: dose 0.0 — even with a MOVED mask and scope — is
    /// the champion, byte-for-byte (the dose test short-circuits before either
    /// is read). This is the analogue of the static bundle's dose-0 moved-mask
    /// identity control, and the reason a zeroed dose cannot hide behind a
    /// "config differs" check.
    #[test]
    fn jrules_prior_dose0_with_moved_mask_is_bit_identical() {
        // Ply 30 is a WIDE root (22 legal) where dose 1.0 is known to move
        // priors — so identity here is not vacuous.
        let g = midgame("28000000000", 30);
        let base = search_single(&g, &small_cfg(256)).unwrap();
        let moved = search_single(
            &g,
            &SearchConfig {
                jrules_prior_dose: 0.0,
                jrules_prior_mask: 27, // JR_ALL minus JR_J5 — deliberately moved
                jrules_prior_scope: JrPriorScope::Own,
                ..small_cfg(256)
            },
        )
        .unwrap();
        assert_same_search(&base, &moved);
    }

    /// A nonzero dose must move PRIORS only: the root's backed-up value surface
    /// (leaf_value of the root node) is bit-identical, while the prior vector
    /// differs somewhere across a handful of positions. Also pins that the
    /// boost is renormalized (priors still sum to ~1).
    #[test]
    fn jrules_prior_dose_moves_priors_not_the_root_leaf_value() {
        let mut any_prior_moved = false;
        // Walk each game forward and probe the first few WIDE roots (a forced
        // root has one uniform prior and can prove nothing either way).
        for seed in ["28000000000", "42", "7"] {
            let mut g = Game::from_seed(seed);
            let mut probed = 0;
            for _ply in 0..80 {
                let legal = g.legal_actions();
                if legal.is_empty() {
                    break;
                }
                if _ply >= 30 && legal.len() >= 6 && probed < 3 {
                    probed += 1;
                    let off = search_single(&g, &small_cfg(64)).unwrap();
                    let on = search_single(
                        &g,
                        &SearchConfig {
                            jrules_prior_dose: 1.0,
                            ..small_cfg(64)
                        },
                    )
                    .unwrap();
                    // The value the root backs up is computed from leaf_parent
                    // alone — the prior surface must not have touched it.
                    assert_eq!(off.root_leaf_value.to_bits(), on.root_leaf_value.to_bits());
                    let s: f64 = on.root_priors.iter().map(|&(_, p)| p).sum();
                    assert!((s - 1.0).abs() < 1e-6, "priors not renormalized: sum {s}");
                    if off
                        .root_priors
                        .iter()
                        .zip(on.root_priors.iter())
                        .any(|(x, y)| x.1.to_bits() != y.1.to_bits())
                    {
                        any_prior_moved = true;
                    }
                }
                let a = legal[legal.len() / 2];
                g.advance(a).unwrap();
            }
        }
        assert!(
            any_prior_moved,
            "dose 1.0 moved no prior on any probe position — the term is dead-wired"
        );
    }

    /// Scope=Own at the root applies (root player IS the mover there), so the
    /// root priors move; the difference vs scope=All lives at opponent
    /// interior nodes, observable as a (possibly) different tree size — here we
    /// pin only the contract that Own != dead: root priors move exactly as All's
    /// do at the root.
    #[test]
    fn jrules_prior_scope_own_still_boosts_the_root() {
        let g = midgame("28000000000", 30); // wide root (22 legal)
        let all = search_single(
            &g,
            &SearchConfig {
                jrules_prior_dose: 1.0,
                ..small_cfg(16)
            },
        )
        .unwrap();
        let own = search_single(
            &g,
            &SearchConfig {
                jrules_prior_dose: 1.0,
                jrules_prior_scope: JrPriorScope::Own,
                ..small_cfg(16)
            },
        )
        .unwrap();
        // The ROOT expansion is mover==root_player under both scopes: identical.
        for (x, y) in all.root_priors.iter().zip(own.root_priors.iter()) {
            assert_eq!((x.0, x.1.to_bits()), (y.0, y.1.to_bits()));
        }
    }

    // ---- S1: JrPriorScope::Opp (measurement/s1_asymmetry_prep) ------------ //

    /// Surface B's dose-0 identity gate, re-run with the scope moved to the NEW
    /// arm: dose 0.0 short-circuits before the scope is read, so `Opp` at dose 0
    /// is still the champion byte-for-byte. Without this, an `Opp` arm could
    /// smuggle a behaviour change into "the default" and no hash gate would
    /// notice (surface B moves no leaf hash by construction).
    #[test]
    fn jrules_prior_dose0_with_scope_opp_is_bit_identical() {
        let g = midgame("28000000000", 30);
        let base = search_single(&g, &small_cfg(256)).unwrap();
        let moved = search_single(
            &g,
            &SearchConfig {
                jrules_prior_dose: 0.0,
                jrules_prior_mask: 27,
                jrules_prior_scope: JrPriorScope::Opp,
                ..small_cfg(256)
            },
        )
        .unwrap();
        assert_same_search(&base, &moved);
        // The census is inside the dose branch, so dose 0 must count NOTHING.
        assert_eq!(
            (
                moved.jr_expansions_total,
                moved.jr_expansions_own_mover,
                moved.jr_expansions_boosted
            ),
            (0, 0, 0)
        );
    }

    /// ⭐ DESIGN §9.2 leg (a) — THE INVERTED LIVENESS LEG.
    ///
    /// Under `Opp` the root's mover IS the root player, so the boost is OFF at
    /// the root **by design**: root priors and the root's backed-up leaf value
    /// must be bit-identical to the champion's. A MOVED root prior here is the
    /// defect (a mis-wired scope gate), not the signal — which is precisely why
    /// the surface-B positive control (`root priors must move`) cannot serve
    /// this scope and had to be replaced.
    #[test]
    fn s1_opp_leaves_the_root_priors_identical_to_the_champion() {
        for (seed, plies) in [("28000000000", 30), ("42", 34), ("7", 38)] {
            let g = midgame(seed, plies);
            let champ = search_single(&g, &small_cfg(256)).unwrap();
            let opp = search_single(
                &g,
                &SearchConfig {
                    jrules_prior_dose: 1.0,
                    jrules_prior_scope: JrPriorScope::Opp,
                    ..small_cfg(256)
                },
            )
            .unwrap();
            assert_eq!(
                champ.root_priors.len(),
                opp.root_priors.len(),
                "{seed}: root candidate set moved — Opp must not touch the root"
            );
            for (x, y) in champ.root_priors.iter().zip(opp.root_priors.iter()) {
                assert_eq!(
                    (x.0, x.1.to_bits()),
                    (y.0, y.1.to_bits()),
                    "{seed}: scope=opp MOVED a root prior — the scope gate is \
                     mis-wired (the root's mover IS the root player)"
                );
            }
            assert_eq!(
                champ.root_leaf_value.to_bits(),
                opp.root_leaf_value.to_bits(),
                "{seed}: scope=opp moved the root LEAF VALUE — surface B moves \
                 priors only"
            );
        }
    }

    /// ⭐ DESIGN §9.2 leg (b) — the POSITIVE half.
    ///
    /// With the root untouched (leg a), the only way `Opp` can be alive is
    /// through INTERIOR opponent expansions — which the search must be deep
    /// enough to REACH and then deep enough to let the boost propagate back.
    ///
    /// ⚠️ **DEVIATION FROM DESIGN §9.2, measured not assumed.** The design
    /// names ">= 256 sims" and "the root visit distribution". Both are too
    /// weak: at 256 sims this surface is *entirely* unexpressed on all three
    /// probe roots (identical `node_count`, `root_w` bits, root visits and
    /// pooled stats), and even at 1376 the top-level root VISIT COUNTS move on
    /// only 2 of the 3. What moves on 3 of 3 at 1376 is `pooled_stats` — the
    /// deduped, N>0, root-POV-signed surface the PIMC pool actually argmaxes,
    /// i.e. the decision surface. So this control runs at **1376 sims, the
    /// deploy sims-per-determinization of record (k16 x 1376 = 22016)**, and
    /// asserts on the decision surface rather than the raw child counts.
    ///
    /// That 256-sim flatline is not a defect — it is a real, cheap prior for
    /// G1: opponent-node priors need depth to express at all.
    #[test]
    fn s1_opp_moves_the_pooled_root_at_the_deploy_sims_per_det() {
        const DEPLOY_SIMS_PER_DET: usize = 1376;
        for (seed, plies) in [("28000000000", 30), ("42", 34), ("7", 38)] {
            let g = midgame(seed, plies);
            let champ = search_single(&g, &small_cfg(DEPLOY_SIMS_PER_DET)).unwrap();
            let opp = search_single(
                &g,
                &SearchConfig {
                    jrules_prior_dose: 1.0,
                    jrules_prior_scope: JrPriorScope::Opp,
                    ..small_cfg(DEPLOY_SIMS_PER_DET)
                },
            )
            .unwrap();
            // The boost must have actually fired at interior opponent nodes,
            // or a flat result would be uninformative rather than damning.
            assert!(
                opp.jr_expansions_boosted > 0,
                "{seed}: scope=opp boosted ZERO expansions at {DEPLOY_SIMS_PER_DET} \
                 sims — the search never reached an opponent node, so this root \
                 cannot speak to liveness"
            );
            let moved = champ.pooled_stats.len() != opp.pooled_stats.len()
                || champ
                    .pooled_stats
                    .iter()
                    .zip(opp.pooled_stats.iter())
                    .any(|(x, y)| x.0 != y.0 || x.1 != y.1 || x.2.to_bits() != y.2.to_bits());
            assert!(
                moved,
                "{seed}: scope=opp left the POOLED root stats bit-identical to the \
                 champion's at {DEPLOY_SIMS_PER_DET} sims. With the root priors \
                 identical by design (leg a), a bit-identical decision surface is \
                 the signature of a dead-wired opponent-node boost"
            );
        }
    }

    /// The measured companion to leg (b), pinned so a future change that makes
    /// the surface express at shallow depth is NOTICED rather than absorbed:
    /// at 256 sims `scope=opp` is entirely unexpressed on the control root —
    /// same node count, same root_w bits, same pooled stats — even though the
    /// gate demonstrably fired at hundreds of opponent expansions.
    ///
    /// This is a DESCRIPTIVE pin, not a contract: if it ever fails, the right
    /// response is to re-read it as news (the surface got stronger), not to
    /// delete it.
    #[test]
    fn s1_opp_is_unexpressed_at_shallow_depth_on_the_control_root() {
        let g = midgame("28000000000", 30);
        let champ = search_single(&g, &small_cfg(256)).unwrap();
        let opp = search_single(
            &g,
            &SearchConfig {
                jrules_prior_dose: 1.0,
                jrules_prior_scope: JrPriorScope::Opp,
                ..small_cfg(256)
            },
        )
        .unwrap();
        assert!(
            opp.jr_expansions_boosted > 0,
            "the gate did not fire at all — this pin is about EXPRESSION, not wiring"
        );
        assert_eq!(champ.node_count, opp.node_count);
        assert_eq!(champ.root_w.to_bits(), opp.root_w.to_bits());
        assert_eq!(champ.pooled_stats.len(), opp.pooled_stats.len());
    }

    /// ⭐ DESIGN §9.2 leg (c) — the decomposition identity `Own ∪ Opp = All`,
    /// disjoint.
    ///
    /// Read WITHIN each tree, which is the only exact form: the moment a prior
    /// moves the three scopes' trees diverge, so a cross-scope set comparison
    /// of node populations is not well defined. Within one tree the identity is
    /// exact and non-vacuous, because it pins `boosted` against an
    /// independently-counted partition of the SAME expansion population.
    #[test]
    fn s1_scope_partition_identity_own_plus_opp_equals_all() {
        for (seed, plies) in [("28000000000", 30), ("42", 34), ("7", 38)] {
            let g = midgame(seed, plies);
            let mk = |scope| {
                search_single(
                    &g,
                    &SearchConfig {
                        jrules_prior_dose: 1.0,
                        jrules_prior_scope: scope,
                        ..small_cfg(256)
                    },
                )
                .unwrap()
            };
            let all = mk(JrPriorScope::All);
            let own = mk(JrPriorScope::Own);
            let opp = mk(JrPriorScope::Opp);

            // All boosts the WHOLE population.
            assert_eq!(
                all.jr_expansions_boosted, all.jr_expansions_total,
                "{seed}: scope=all did not boost every expansion"
            );
            // Own boosts exactly the own-mover partition...
            assert_eq!(
                own.jr_expansions_boosted, own.jr_expansions_own_mover,
                "{seed}: scope=own boosted a non-own-mover expansion"
            );
            // ...and Opp boosts exactly its complement. Disjoint by
            // construction (the two predicates are negations), union = total.
            assert_eq!(
                opp.jr_expansions_boosted,
                opp.jr_expansions_total - opp.jr_expansions_own_mover,
                "{seed}: scope=opp is not the complement of scope=own"
            );
            // Non-vacuity: both halves of the partition must be non-empty, or
            // the identity holds trivially and proves nothing.
            assert!(
                opp.jr_expansions_own_mover > 0
                    && opp.jr_expansions_total > opp.jr_expansions_own_mover,
                "{seed}: the expansion population is one-sided (own {} of {}) \
                 — the partition identity would be vacuous here",
                opp.jr_expansions_own_mover,
                opp.jr_expansions_total
            );
        }
    }

    /// `root_player` is latched PER SEARCH, and so is the census. Two searches
    /// from the SAME `Searcher` at roots with different movers must each report
    /// their own partition — a stale latch would make `Opp` boost the wrong
    /// half in every PIMC world after the first (each determinized world drives
    /// this same entry point).
    #[test]
    fn s1_root_player_and_census_latch_per_search_not_per_searcher() {
        let cfg = SearchConfig {
            jrules_prior_dose: 1.0,
            jrules_prior_scope: JrPriorScope::Opp,
            ..small_cfg(256)
        };
        // Two roots one ply apart => different movers.
        let g0 = midgame("28000000000", 30);
        let mut g1 = g0.clone();
        let legal = g1.legal_actions();
        g1.advance(legal[legal.len() / 2]).unwrap();

        let mut s = Searcher::new(&cfg);
        let a0 = s.search(&g0).unwrap();
        let a1 = s.search(&g1).unwrap();
        // Fresh counts, not a running total.
        assert!(a1.jr_expansions_total < a0.jr_expansions_total + a1.jr_expansions_total);
        for r in [&a0, &a1] {
            assert_eq!(
                r.jr_expansions_boosted,
                r.jr_expansions_total - r.jr_expansions_own_mover
            );
            assert!(r.jr_expansions_own_mover > 0, "root expansion was not counted as own-mover");
        }
        // And each matches a fresh Searcher on the same root (no carry-over).
        let f0 = search_single(&g0, &cfg).unwrap();
        let f1 = search_single(&g1, &cfg).unwrap();
        assert_eq!(a0.jr_expansions_total, f0.jr_expansions_total);
        assert_eq!(a0.jr_expansions_own_mover, f0.jr_expansions_own_mover);
        assert_eq!(a1.jr_expansions_total, f1.jr_expansions_total);
        assert_eq!(a1.jr_expansions_own_mover, f1.jr_expansions_own_mover);
    }

    /// The ROOT is always an own-mover expansion, so at a 1-simulation search
    /// (root + at most one descent) `Opp`'s root priors are the champion's and
    /// `Own` counts the root as boosted. The minimal-depth statement of the
    /// gate: no interior population is needed for leg (a) to bite.
    ///
    /// ⚠️ Deliberately does NOT assert `opp.boosted == 0` — the first descent
    /// can land on either seat (tile and meeple phases share a mover), so the
    /// child's seat is position-dependent and pinning it would be a fragile
    /// statement about the engine's phase model, not about this gate.
    #[test]
    fn s1_the_root_expansion_is_own_and_opp_skips_it() {
        let g = midgame("28000000000", 30);
        let mk = |scope| {
            search_single(
                &g,
                &SearchConfig {
                    jrules_prior_dose: 1.0,
                    jrules_prior_scope: scope,
                    ..small_cfg(1)
                },
            )
            .unwrap()
        };
        let own = mk(JrPriorScope::Own);
        let opp = mk(JrPriorScope::Opp);
        assert!(
            own.jr_expansions_own_mover >= 1 && own.jr_expansions_boosted >= 1,
            "the root expansion was not counted as an own-mover boost"
        );
        assert_eq!(
            opp.jr_expansions_boosted,
            opp.jr_expansions_total - opp.jr_expansions_own_mover
        );
        assert!(
            opp.jr_expansions_boosted < opp.jr_expansions_total,
            "scope=opp boosted every expansion including the root"
        );
        let champ = search_single(&g, &small_cfg(1)).unwrap();
        assert_eq!(champ.root_priors.len(), opp.root_priors.len());
        for (x, y) in champ.root_priors.iter().zip(opp.root_priors.iter()) {
            assert_eq!((x.0, x.1.to_bits()), (y.0, y.1.to_bits()));
        }
    }

    #[test]
    fn searching_a_midgame_position_is_deterministic() {
        let mut g = Game::from_seed("42");
        for _ in 0..40 {
            let legal = g.legal_actions();
            g.advance(legal[0]).unwrap();
        }
        let cfg = small_cfg(64);
        let a = search_single(&g, &cfg).unwrap();
        let b = search_single(&g, &cfg).unwrap();
        assert_eq!(a.chosen_action, b.chosen_action);
        assert_eq!(a.root_children.len(), b.root_children.len());
        for (x, y) in a.root_children.iter().zip(b.root_children.iter()) {
            assert_eq!(x.0, y.0);
            assert_eq!(x.1, y.1);
            assert_eq!(x.2.to_bits(), y.2.to_bits());
        }
    }

    // ---- WC tie-break rule (BACKLOG.md 2026-08-03) ------------------------ //

    /// Play a seed all the way to `is_terminated()`, then FORCE a tied final
    /// score (`state.scores` set equal) — the cheapest way to construct the
    /// exact-`tanh`-zero terminal the tie branch needs, without depending on
    /// any real seed actually ending level.
    fn terminal_with_tied_score(seed: &str) -> Game {
        let mut g = Game::from_seed(seed);
        let mut guard = 0;
        while !g.state.is_terminated() {
            guard += 1;
            assert!(guard < 400, "seed {seed}: runaway terminal walk");
            let legal = g.legal_actions();
            g.advance(legal[legal.len() / 2]).unwrap();
        }
        g.state.scores = [37, 37];
        g
    }

    #[test]
    fn game_ended_tie_branch_unarmed_keeps_incumbent_signs() {
        let g = terminal_with_tied_score("11");
        let cfg = SearchConfig::default();
        assert!(!cfg.wc_tiebreak, "default must stay off");
        let s = Searcher::new(&cfg);
        assert_eq!(s.game_ended(&g, 0), 1e-6);
        assert_eq!(s.game_ended(&g, 1), -1e-6);
    }

    #[test]
    fn game_ended_tie_branch_armed_sign_flips() {
        let g = terminal_with_tied_score("11");
        let cfg = SearchConfig {
            wc_tiebreak: true,
            ..SearchConfig::default()
        };
        let s = Searcher::new(&cfg);
        assert_eq!(s.game_ended(&g, 0), -1e-6, "P0 (the starting player) loses the tie");
        assert_eq!(s.game_ended(&g, 1), 1e-6);
    }

    /// The perspective contract (`get_game_ended(b,0) == -get_game_ended(b,1)`)
    /// holds in BOTH readings, and across several seeds — arming the flag
    /// sign-flips the sentinel, it does not break antisymmetry.
    #[test]
    fn game_ended_tie_branch_antisymmetric_both_readings() {
        for seed in ["11", "12", "13"] {
            let g = terminal_with_tied_score(seed);
            for wc_tiebreak in [false, true] {
                let cfg = SearchConfig { wc_tiebreak, ..SearchConfig::default() };
                let s = Searcher::new(&cfg);
                let v0 = s.game_ended(&g, 0);
                let v1 = s.game_ended(&g, 1);
                assert_eq!(v0, -v1, "seed {seed} wc_tiebreak={wc_tiebreak}");
                assert_eq!(v0.abs(), 1e-6, "seed {seed} wc_tiebreak={wc_tiebreak}");
            }
        }
    }

    /// A non-tied terminal is untouched by the flag at all — the flag only
    /// ever reaches the `v == 0.0` branch.
    #[test]
    fn game_ended_non_tie_terminal_is_flag_invariant() {
        let mut g = Game::from_seed("11");
        let mut guard = 0;
        while !g.state.is_terminated() {
            guard += 1;
            assert!(guard < 400);
            let legal = g.legal_actions();
            g.advance(legal[legal.len() / 2]).unwrap();
        }
        g.state.scores = [40, 22]; // a real, non-tied margin
        let off_cfg = SearchConfig::default();
        let on_cfg = SearchConfig {
            wc_tiebreak: true,
            ..SearchConfig::default()
        };
        let off = Searcher::new(&off_cfg);
        let on = Searcher::new(&on_cfg);
        for player in [0usize, 1] {
            assert_eq!(off.game_ended(&g, player), on.game_ended(&g, player));
        }
    }
}
