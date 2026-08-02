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
//! 3. **The legal-move cache is keyed by `string_representation`.**
//!    `NeuralMCTS.__init__` force-enables it, so two distinct boards that share
//!    one repr key (the Phase-0.3 rotation family) are served the *first*
//!    board's mask. Reproduced by [`Tree::legal_cache`] rather than recomputing.
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
pub mod trace;

pub use fxhash::FxBuildHasher;
pub use trace::{JsonlTrace, TraceSink};

pub type NodeId = u32;

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
    /// DIAGNOSTIC (mirrors `CARCASSONNE_CACHE_COLLIDE_CHECK=1`): on every
    /// legal-move-cache HIT, recompute the mask and count disagreements — i.e.
    /// measure whether two distinct boards really do share one
    /// `string_representation` key during a search. Counting only; the CACHED
    /// mask is still returned, so behaviour is unchanged (that is the Python
    /// DEFAULT, and it is the semantics under gate). Costs a full enumeration
    /// per hit, so it is off for the gate legs.
    pub legal_cache_collide_check: bool,
    /// Reuse ONE [`LeafScratch`] for every leaf evaluation of the search (the P2
    /// perf lever). `false` calls the allocating `leaf::leaf_value_float`, which
    /// is what the P2 gate measured — kept so the lever can be A/B'd in one
    /// process (`bench_search_scratch_ab`) rather than across builds. Results
    /// are bit-identical either way.
    pub use_leaf_scratch: bool,
    pub leaf: LeafConfig,
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
            legal_cache_collide_check: false,
            use_leaf_scratch: true,
            leaf: LeafConfig::curve125(),
        }
    }
}

#[derive(Debug)]
pub enum SearchError {
    Leaf(LeafError),
    Engine(String),
    /// `node.valid_actions[0]` on an empty list — the Python raises `IndexError`.
    NoLegalActionsAtInterior,
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
            SearchError::NoRootChildren => {
                write!(f, "root has no children (Python StopIteration)")
            }
        }
    }
}

/// `mcts._NeuralNode`.
pub struct Node {
    /// The `string_representation` bytes, heap-allocated **once** per node.
    /// `Tree::index` / `Tree::legal_cache` hold refcount handles onto the same
    /// buffer (the tree is per-thread, so `Rc` suffices) — the 2026-08-02
    /// review's finding #2 was three independent copies of a 1.2–5.0 KB key.
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

/// `NeuralMCTS._nodes` + the `Game` legal-move cache, which share a lifetime
/// (`clear()` wipes both).
#[derive(Default)]
pub struct Tree {
    pub nodes: Vec<Node>,
    index: HashMap<Rc<str>, NodeId, FxBuildHasher>,
    /// `Game._legal_cache` — keyed by `string_representation`, exactly as in
    /// `game_wrapper.get_valid_moves`.
    legal_cache: HashMap<Rc<str>, Vec<i32>, FxBuildHasher>,
    pub legal_cache_hits: u64,
    pub legal_cache_misses: u64,
    /// Cache HITS whose recomputed mask disagreed (only counted under
    /// `SearchConfig::legal_cache_collide_check`).
    pub legal_cache_collisions: u64,
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
    pub legal_cache_hits: u64,
    pub legal_cache_misses: u64,
    pub legal_cache_collisions: u64,
}

pub struct Searcher<'a> {
    pub cfg: &'a SearchConfig,
    pub tree: Tree,
    pub leaf_evals: u64,
    /// One reusable decomposition buffer for the whole search — the P2 perf
    /// lever (~27 KB of buffer churn per leaf call, at tens of leaf calls per
    /// node expansion).
    scratch: LeafScratch,
    trace: Option<&'a mut dyn TraceSink>,
}

impl<'a> Searcher<'a> {
    pub fn new(cfg: &'a SearchConfig) -> Self {
        Searcher {
            cfg,
            tree: Tree::default(),
            leaf_evals: 0,
            scratch: LeafScratch::new(),
            trace: None,
        }
    }

    pub fn with_trace(cfg: &'a SearchConfig, trace: &'a mut dyn TraceSink) -> Self {
        Searcher {
            cfg,
            tree: Tree::default(),
            leaf_evals: 0,
            scratch: LeafScratch::new(),
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
    fn game_ended(&self, g: &Game, player: usize) -> f64 {
        if !g.state.is_terminated() {
            return 0.0;
        }
        let opp = 1 - player;
        let diff = (g.state.scores[player] - g.state.scores[opp]) as f64;
        let v = self.tanh(diff / self.cfg.score_norm_scale);
        if v == 0.0 {
            if player == 0 {
                1e-6
            } else {
                -1e-6
            }
        } else {
            v
        }
    }

    /// `game_wrapper.Game.get_valid_moves` **through the repr-keyed cache**.
    fn legal_actions(&mut self, g: &Game, key: &Rc<str>) -> Vec<i32> {
        if let Some(v) = self.tree.legal_cache.get(key.as_ref()) {
            self.tree.legal_cache_hits += 1;
            let hit = v.clone();
            if self.cfg.legal_cache_collide_check && hit != g.legal_actions() {
                self.tree.legal_cache_collisions += 1;
            }
            return hit;
        }
        self.tree.legal_cache_misses += 1;
        let legal = g.legal_actions();
        self.tree.legal_cache.insert(Rc::clone(key), legal.clone());
        legal
    }

    // -- the evaluator ------------------------------------------------------ //

    /// `heuristic_prior_mcts.make_heuristic_prior_evaluator`'s closure:
    /// returns `(legal, priors_over_legal_f32, value)`.
    fn evaluate(
        &mut self,
        g: &Game,
        key: &Rc<str>,
    ) -> Result<(Vec<i32>, Vec<f32>, f64), SearchError> {
        let mover = g.state.current_player;
        let leaf_parent = self.leaf_at(g, mover)?;
        let legal = self.legal_actions(g, key);

        // deltas[i] = leaf(child_i, mover) - leaf_parent, in `legal` order.
        let mut deltas: Vec<f64> = Vec::with_capacity(legal.len());
        for &a in &legal {
            let mut child = g.clone();
            child.advance(a).map_err(SearchError::Engine)?;
            deltas.push(self.leaf_at(&child, mover)? - leaf_parent);
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
    fn expand(&mut self, id: NodeId, g: &Game, via_f32: bool) -> Result<(), SearchError> {
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
        // Refcount handle, not a fresh copy of the multi-KB key.
        let key = Rc::clone(&self.tree.get(id).key);
        let (legal, priors_f32, value_raw) = self.evaluate(g, &key)?;

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
            let action = self.select_child_puct(node)?;
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
                        self.expand(child, &g, false)?;
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
        let root = self.create_or_get(root_game);
        if !self.tree.get(root).expanded && !self.tree.get(root).is_terminal {
            // `_eval_boards` -> float32 values array -> `float(values_b[0])`.
            self.expand(root, root_game, true)?;
        }
        for i in 0..self.cfg.simulations {
            self.simulate(root_game, root, i)?;
        }
        self.finish(root)
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
            legal_cache_hits: self.tree.legal_cache_hits,
            legal_cache_misses: self.tree.legal_cache_misses,
            legal_cache_collisions: self.tree.legal_cache_collisions,
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
}
