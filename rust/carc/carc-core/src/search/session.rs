//! `session` — the PERSISTENT / RE-ROOTABLE search tree (rustport **P6**, Gap 2).
//!
//! ## Why this module exists
//!
//! [`super::Searcher`] already keeps its [`Tree`] for the life of ONE
//! `Searcher` value, and every production entry point
//! (`search::search_single`, `fair::FairAgent`'s per-world searches,
//! `MirrorState.search_single`) builds a fresh `Searcher` per call — i.e. a
//! fresh tree per search.  That is exactly `HeuristicPriorAgent(...).move()`
//! with `reuse_tree=False`, and it is the ONLY search semantics the Rust port
//! offered until now.
//!
//! The Python ruler has a **second** one, and the instrument tier runs on it:
//!
//! ```python
//! def best_action(self, board):          # heuristic_prior_mcts.py
//!     self.mcts.search(board)            # <- NO clear(), at ANY reuse_tree
//!     ...
//! def move(self, board):
//!     if self._reuse_tree: self._reroot_or_clear(board)
//!     else:                self.clear()
//!     return self.best_action(board)
//! ```
//!
//! `best_action` never clears, so a caller that drives an advancing game with
//! `best_action` (which `oracle_score_pilot._playout_value` does, every ply, to
//! terminal) runs ONE `NeuralMCTS._nodes` transposition table across the whole
//! playout: each ply's root arrives already carrying the statistics it
//! accumulated while it was a *descendant* of an earlier ply's tree.  This is
//! not a subtlety — it is measured in
//! `measurement/rustport_p6/GAP2_ORACLE_CONTINUATION_TREE.json`: at the pilot's
//! own `--oracle-sims 100` the per-ply root pre-exists with `N > sims` on 102 of
//! 103 plies, and replaying the identical world fresh-tree-per-ply diverges in
//! 4/4 positions (first divergence by ply 3–7, terminal margins differing by up
//! to 12 points).  A fresh-tree Rust leg is a DIFFERENT PLAYER, and the whole
//! oracle / clairvoyant instrument tier therefore failed closed on `--backend
//! rust`.
//!
//! [`SearchSession`] is that missing semantics, and nothing else: it owns the
//! tree ACROSS calls and exposes the three Python transitions verbatim —
//!
//! | Python | here |
//! |---|---|
//! | `agent.best_action(board)` (tree carries) | [`SearchSession::search_carry`] |
//! | `agent.move(board)`, `reuse_tree=False` (`clear()` first) | [`SearchSession::search_fresh`] |
//! | `agent.move(board)`, `reuse_tree=True` (`_reroot_or_clear` first) | [`SearchSession::reroot_to`] + [`SearchSession::search_carry`] |
//!
//! ## Byte-identity of the existing path
//!
//! This module adds NO line to any existing code path.  `search_carry` runs the
//! stock [`super::Searcher::search`] over a tree it lends in and takes back
//! (`Searcher::tree` is a public field, and `Tree: Default`), so a session whose
//! tree is empty is bit-for-bit `search::search_single`.  That is asserted here
//! (`fresh_session_equals_search_single`) as well as by the P6 gates.
//!
//! ## Node identity across an advancing board
//!
//! Python's `_nodes` is keyed by `game.string_representation(board)` and so is
//! [`Tree::index`]; the key survives board advancement for free, because it is a
//! pure function of the position.  The one structure that is keyed by node
//! *identity* rather than by position is `node.child_canon` (Python's
//! `id(child)`), which [`SearchSession::prune_to_subtree`] remaps when it
//! compacts the arena — the Rust counterpart of Python's "the same object simply
//! stays in the new dict".

use std::collections::HashMap;

use super::{fxhash::FxBuildHasher, Node, NodeId, SearchConfig, SearchError, SearchResult, Searcher, Tree};
use crate::game::Game;

/// The outcome of a [`SearchSession::reroot_to`] — `HeuristicPriorAgent`'s three
/// counters (`reuse_hits` / `reuse_fresh` / `reuse_collide`), returned instead of
/// accumulated so the caller keeps the Python bookkeeping.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Reroot {
    /// Re-rooted into the retained subtree; carries the node's `N`.
    Hit(i64),
    /// `board` is not usefully in the retained tree (absent / unexpanded /
    /// terminal / zero-visit) — tree wiped, next search is fresh.
    Fresh,
    /// Wrong-rotation transposition sibling (same `string_representation`, a
    /// different legal action set) — tree wiped, next search is fresh.
    Collide,
}

impl Reroot {
    /// `_reroot_or_clear`'s three counter names.
    pub fn label(&self) -> &'static str {
        match self {
            Reroot::Hit(_) => "hit",
            Reroot::Fresh => "fresh",
            Reroot::Collide => "collide",
        }
    }
    /// Visits carried IN (0 for both fallbacks) — `NeuralMCTS.reroot_to`'s return.
    pub fn carried(&self) -> i64 {
        match self {
            Reroot::Hit(n) => *n,
            _ => 0,
        }
    }
}

/// A search whose [`Tree`] outlives the individual search call.
///
/// Owns its [`SearchConfig`] (the sessions are long-lived and cross an FFI
/// boundary, so a borrowed config would infect every caller with a lifetime).
pub struct SearchSession {
    pub cfg: SearchConfig,
    tree: Tree,
    /// Cumulative across the session's searches (the per-call figure is in each
    /// [`SearchResult`]).
    pub leaf_evals: u64,
    pub searches: u64,
    /// `root.N` as the LAST search found it, BEFORE adding its own simulations —
    /// the gap-2 diagnostic (`> 0` ⇒ the root pre-existed; `> cfg.simulations` ⇒
    /// it carried more than one search's budget).
    pub last_root_n_before: i64,
    pub last_reroot: Option<Reroot>,
}

/// ⛔ **R6 (merge review 2026-08-30) — scope boosts do not survive tree reuse.**
///
/// [`super::Searcher`]'s J-rules prior scope is decided ONCE, at the moment a
/// node is EXPANDED (`search/mod.rs`, the `jrules_prior_dose != 0.0` branch),
/// from `root_player == mover` for the search that expanded it. Priors are
/// never recomputed afterwards. On a fresh tree that is exactly the intended
/// semantics — every node in the tree was expanded under the one root whose
/// seat the scope is defined against.
///
/// A CARRIED tree breaks it. [`SearchSession::search_carry`] lends the same
/// [`Tree`] into a new [`super::Searcher`] at a new root, and `search()`
/// re-latches `root_player` for the counters — but every node the previous
/// searches already expanded keeps the priors it was given under the OLD root.
/// A node expanded as an opponent node under ply `n` stays boosted when ply
/// `n+1` re-roots onto it and it becomes an own-mover node (the new root
/// itself, in the common case). `scope = own`/`opp` therefore silently
/// degrades toward `all` as a session ages, and no counter in the tree can say
/// by how much: the census counts EXPANSIONS, and a carried node is not
/// re-expanded.
///
/// `all` is immune (every node is boosted under every root) and so is
/// `dose == 0.0` (nothing is boosted at all), so this fails closed on exactly
/// the two scopes that cannot be made to mean anything on a carried tree.
///
/// Fresh-tree searches are untouched — [`super::search_single`],
/// [`crate::fair::search_worlds`]'s per-world `Searcher::new`, every
/// `Searcher` a caller drives itself. Only the persistent-session object is
/// refused, and it is refused at CONSTRUCTION rather than at
/// [`SearchSession::search_carry`], because a session that cannot legally
/// carry has no business existing (its `search_fresh` would be a fresh
/// `Searcher` wearing a carried object's name).
pub fn carried_scope_guard(cfg: &SearchConfig) -> Result<(), String> {
    if cfg.jrules_prior_dose == 0.0 {
        return Ok(());
    }
    let scope = match cfg.jrules_prior_scope {
        super::JrPriorScope::All => return Ok(()),
        super::JrPriorScope::Own => "own",
        super::JrPriorScope::Opp => "opp",
    };
    Err(format!(
        "R6: a persistent/carried SearchSession refuses jrules_prior_scope={scope:?} \
         (dose={}). Scope is latched at NODE EXPANSION from the expanding search's \
         root seat and is never recomputed, so a carried tree keeps boosts a node \
         earned under a DIFFERENT root — scope={scope:?} silently degrades toward \
         \"all\" as the session ages, by an amount the expansion census cannot see. \
         Use a fresh-tree search (search_single / fair::search_worlds), or \
         jrules_prior_scope=\"all\", or dose=0.",
        cfg.jrules_prior_dose
    ))
}

impl SearchSession {
    /// R6-checked constructor. See [`carried_scope_guard`].
    pub fn try_new(cfg: SearchConfig) -> Result<Self, String> {
        carried_scope_guard(&cfg)?;
        Ok(SearchSession::build(cfg))
    }

    /// Panics on an R6-illegal config — see [`SearchSession::try_new`] for the
    /// recoverable form (which is what the FFI boundary uses).
    pub fn new(cfg: SearchConfig) -> Self {
        match carried_scope_guard(&cfg) {
            Ok(()) => SearchSession::build(cfg),
            Err(e) => panic!("{e}"),
        }
    }

    fn build(cfg: SearchConfig) -> Self {
        SearchSession {
            cfg,
            tree: Tree::default(),
            leaf_evals: 0,
            searches: 0,
            last_root_n_before: 0,
            last_reroot: None,
        }
    }

    pub fn tree(&self) -> &Tree {
        &self.tree
    }

    pub fn tree_len(&self) -> usize {
        self.tree.len()
    }

    /// `NeuralMCTS.clear()` — drop every node.  (Python also drops the
    /// legal-moves cache and `_noisy_roots`; the Rust port has neither, see the
    /// `search` module docs §3.)
    pub fn clear(&mut self) {
        self.tree = Tree::default();
    }

    /// `root.N` for `g`'s position as the tree holds it right now (0 = absent).
    pub fn root_n_at(&self, g: &Game) -> i64 {
        match self.tree.lookup(&g.string_repr()) {
            Some(id) => self.tree.get(id).n,
            None => 0,
        }
    }

    /// Is `g`'s position already in the tree?
    pub fn contains(&self, g: &Game) -> bool {
        self.tree.lookup(&g.string_repr()).is_some()
    }

    /// **`HeuristicPriorAgent.best_action`** — run `cfg.simulations` PUCT
    /// simulations from `g` on the CARRIED tree, exactly as
    /// `NeuralMCTS.search` does when `_nodes` was never cleared:
    ///
    /// * an already-interned root is REUSED with its accumulated `(N, W)`, and
    /// * an already-EXPANDED root is not re-expanded — so it keeps the raw-f64
    ///   `leaf_value` it got as an interior node and never takes the root-only
    ///   `float32` round-trip (`_eval_boards`).  That asymmetry is the reason a
    ///   carried search cannot be emulated by replaying a fresh one.
    pub fn search_carry(&mut self, g: &Game) -> Result<SearchResult, SearchError> {
        self.last_root_n_before = self.root_n_at(g);
        let SearchSession {
            cfg,
            tree,
            leaf_evals,
            searches,
            ..
        } = self;
        let mut s = Searcher::new(cfg);
        s.tree = std::mem::take(tree);
        let out = s.search(g);
        // Take the tree BACK on the error path too: a `SearchError` is not fatal
        // to the session (the Python raises out of `search` with `_nodes` intact).
        *tree = std::mem::take(&mut s.tree);
        *leaf_evals += s.leaf_evals;
        *searches += 1;
        out
    }

    /// **`HeuristicPriorAgent.move` with `reuse_tree=False`** — `clear()` and
    /// then search.  Bit-for-bit [`super::search_single`].
    pub fn search_fresh(&mut self, g: &Game) -> Result<SearchResult, SearchError> {
        self.clear();
        self.last_reroot = None;
        self.search_carry(g)
    }

    /// **`HeuristicPriorAgent.move` with `reuse_tree=True`** — re-root, then
    /// search on whatever survived.
    pub fn search_reroot(&mut self, g: &Game) -> Result<SearchResult, SearchError> {
        self.reroot_to(g);
        self.search_carry(g)
    }

    /// `HeuristicPriorAgent._reroot_or_clear` (== `NeuralMCTS.reroot_to`, the
    /// single shared implementation on the Python side).  Ported verbatim,
    /// including the ORDER of the two rejections:
    ///
    /// ```python
    /// retained = m._nodes.get(next_key)
    /// if retained is None or not retained.expanded or retained.is_terminal or retained.N == 0:
    ///     m._nodes.clear(); self.reuse_fresh += 1; return
    /// if set(retained.valid_actions) != {int(a) for a in np.flatnonzero(game.get_valid_moves(board))}:
    ///     m._nodes.clear(); self.reuse_collide += 1; return
    /// self._prune_to_subtree(retained); self.reuse_hits += 1
    /// ```
    ///
    /// NOTE the collision guard compares against the RAW legal mask
    /// (`np.flatnonzero`), not a dedup-narrowed one — MEEPLE-DEDUP is a
    /// python-only search variant that `rust_agent.search_config_rs` refuses, so
    /// the two definitions coincide here.
    pub fn reroot_to(&mut self, g: &Game) -> Reroot {
        let out = self.reroot_inner(g);
        self.last_reroot = Some(out);
        out
    }

    fn reroot_inner(&mut self, g: &Game) -> Reroot {
        let key = g.string_repr();
        let Some(id) = self.tree.lookup(&key) else {
            self.clear();
            return Reroot::Fresh;
        };
        {
            let n = self.tree.get(id);
            if !n.expanded || n.is_terminal || n.n == 0 {
                self.clear();
                return Reroot::Fresh;
            }
        }
        // `set(retained.valid_actions) != fresh_actions`.  Both sides are the
        // ascending, duplicate-free `np.flatnonzero` order, so vector equality
        // IS set equality here.
        let fresh = g.legal_actions();
        if self.tree.get(id).valid_actions != fresh {
            self.clear();
            return Reroot::Collide;
        }
        let carried = self.tree.get(id).n;
        self.prune_to_subtree(id);
        Reroot::Hit(carried)
    }

    /// `NeuralMCTS.prune_to_subtree` — keep ONLY the subtree reachable from
    /// `root`, dropping every other retained node.
    ///
    /// Python simply rebinds `_nodes` to a smaller dict of the SAME node objects,
    /// so `id(child)` (and therefore `child_canon`) is preserved for free.  The
    /// Rust arena is index-addressed, so compaction has to REMAP the two
    /// identity-keyed structures — `Node::children`'s values and
    /// `Node::child_canon`'s keys — which this does in one pass.  Traversal order
    /// mirrors Python's `stack.pop()` DFS; it is not observable (no search
    /// output depends on `NodeId` VALUES, only on their equality), but matching
    /// it keeps the two implementations readable side by side.
    fn prune_to_subtree(&mut self, root: NodeId) {
        let old = std::mem::take(&mut self.tree.nodes);
        let mut slots: Vec<Option<Node>> = old.into_iter().map(Some).collect();
        let mut remap: HashMap<NodeId, NodeId, FxBuildHasher> = HashMap::default();
        let mut order: Vec<NodeId> = Vec::new();
        let mut stack: Vec<NodeId> = vec![root];
        while let Some(nid) = stack.pop() {
            if remap.contains_key(&nid) {
                continue;
            }
            remap.insert(nid, order.len() as NodeId);
            order.push(nid);
            // `for child in node.children.values()` — the child ids, in this
            // node's insertion order (Python iterates the dict, same thing).
            let node = slots[nid as usize]
                .as_ref()
                .expect("prune: node visited twice");
            for a in node.child_actions.iter() {
                let cid = node.children[a];
                if !remap.contains_key(&cid) {
                    stack.push(cid);
                }
            }
        }
        let mut nodes: Vec<Node> = Vec::with_capacity(order.len());
        let mut index: HashMap<std::rc::Rc<str>, NodeId, FxBuildHasher> = HashMap::default();
        for (new_id, old_id) in order.iter().enumerate() {
            let mut node = slots[*old_id as usize].take().expect("prune: missing node");
            for v in node.children.values_mut() {
                *v = remap[v];
            }
            let canon: HashMap<NodeId, i32, FxBuildHasher> = node
                .child_canon
                .iter()
                .map(|(k, v)| (remap[k], *v))
                .collect();
            node.child_canon = canon;
            index.insert(std::rc::Rc::clone(&node.key), new_id as NodeId);
            nodes.push(node);
        }
        self.tree.nodes = nodes;
        self.tree.index = index;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::search::{self, FinalSelect};

    fn cfg(sims: usize) -> SearchConfig {
        SearchConfig {
            simulations: sims,
            ..SearchConfig::default()
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

    fn same(a: &SearchResult, b: &SearchResult) {
        assert_eq!(a.chosen_action, b.chosen_action);
        assert_eq!(a.root_n, b.root_n);
        assert_eq!(a.root_w.to_bits(), b.root_w.to_bits());
        assert_eq!(a.node_count, b.node_count);
        assert_eq!(a.root_children.len(), b.root_children.len());
        for (x, y) in a.root_children.iter().zip(b.root_children.iter()) {
            assert_eq!((x.0, x.1, x.2.to_bits()), (y.0, y.1, y.2.to_bits()));
        }
    }

    /// THE DEFAULT-OFF GUARANTEE: an empty session is `search_single`, bit-exact.
    #[test]
    fn fresh_session_equals_search_single() {
        let g = midgame("28000000000", 55);
        let want = search::search_single(&g, &cfg(256)).unwrap();
        let got = SearchSession::new(cfg(256)).search_carry(&g).unwrap();
        same(&want, &got);
        // ...and so is an explicitly cleared one, at every subsequent ply.
        let mut s = SearchSession::new(cfg(256));
        let mut g2 = g.clone();
        for _ in 0..3 {
            let a = s.search_fresh(&g2).unwrap();
            let b = search::search_single(&g2, &cfg(256)).unwrap();
            same(&b, &a);
            g2.advance(a.chosen_action).unwrap();
        }
    }

    /// The carry is REAL: the second ply's root arrives with visits, and the
    /// search it runs is not the fresh-tree one.
    #[test]
    fn a_carried_root_pre_exists_and_changes_the_search() {
        let g = midgame("28000000000", 55);
        let mut s = SearchSession::new(cfg(128));
        let r0 = s.search_carry(&g).unwrap();
        let mut g1 = g.clone();
        g1.advance(r0.chosen_action).unwrap();
        assert_eq!(s.last_root_n_before, 0, "the first root is brand new");
        let carried = s.search_carry(&g1).unwrap();
        assert!(
            s.last_root_n_before > 0,
            "ply 2's root must pre-exist as a descendant of ply 1's tree"
        );
        assert_eq!(
            carried.root_n,
            s.last_root_n_before + 128,
            "a carried search ADDS its budget on top of the retained visits"
        );
        let fresh = search::search_single(&g1, &cfg(128)).unwrap();
        assert_eq!(fresh.root_n, 128);
        assert_ne!(carried.root_n, fresh.root_n);
    }

    /// `move()` with `reuse_tree=False` must wipe everything the carry retained.
    #[test]
    fn search_fresh_drops_the_carry() {
        let g = midgame("42", 40);
        let mut s = SearchSession::new(cfg(64));
        let r0 = s.search_carry(&g).unwrap();
        let mut g1 = g.clone();
        g1.advance(r0.chosen_action).unwrap();
        let r1 = s.search_fresh(&g1).unwrap();
        assert_eq!(s.last_root_n_before, 0);
        assert_eq!(r1.root_n, 64);
        same(&search::search_single(&g1, &cfg(64)).unwrap(), &r1);
    }

    /// Re-root keeps the retained statistics and drops everything unreachable.
    #[test]
    fn reroot_hits_and_prunes() {
        let g = midgame("28000000000", 55);
        let mut s = SearchSession::new(cfg(256));
        let r0 = s.search_carry(&g).unwrap();
        let before = s.tree_len();
        let mut g1 = g.clone();
        g1.advance(r0.chosen_action).unwrap();
        let n_at = s.root_n_at(&g1);
        let rr = s.reroot_to(&g1);
        assert_eq!(rr, Reroot::Hit(n_at));
        assert!(s.tree_len() < before, "prune must drop unreachable nodes");
        assert_eq!(s.root_n_at(&g1), n_at, "the retained root keeps its visits");
        // the pruned tree still searches, and still carries
        let r1 = s.search_reroot(&g1).unwrap();
        assert_eq!(r1.root_n, n_at + 256);
    }

    /// A position the tree never saw re-roots to a CLEARED tree (`reuse_fresh`).
    #[test]
    fn reroot_misses_clear_the_tree() {
        let g = midgame("42", 40);
        let mut s = SearchSession::new(cfg(32));
        s.search_carry(&g).unwrap();
        assert!(s.tree_len() > 1);
        let other = midgame("777", 60);
        assert_eq!(s.reroot_to(&other), Reroot::Fresh);
        assert_eq!(s.tree_len(), 0);
        let r = s.search_carry(&other).unwrap();
        same(&search::search_single(&other, &cfg(32)).unwrap(), &r);
    }

    /// Pruning must not change what the tree computes: a search after a re-root
    /// is bit-identical to the same search on the un-pruned carried tree.
    #[test]
    fn prune_is_semantically_invisible() {
        let g = midgame("28000000000", 48);
        let mut a = SearchSession::new(cfg(192));
        let mut b = SearchSession::new(cfg(192));
        let r0 = a.search_carry(&g).unwrap();
        let r0b = b.search_carry(&g).unwrap();
        same(&r0, &r0b);
        let mut g1 = g.clone();
        g1.advance(r0.chosen_action).unwrap();
        // a: re-root (prunes + remaps ids). b: plain carry (no prune).
        assert!(matches!(a.reroot_to(&g1), Reroot::Hit(_)));
        let ra = a.search_carry(&g1).unwrap();
        let rb = b.search_carry(&g1).unwrap();
        assert_eq!(ra.chosen_action, rb.chosen_action);
        assert_eq!(ra.root_n, rb.root_n);
        assert_eq!(ra.root_w.to_bits(), rb.root_w.to_bits());
        for (x, y) in ra.root_children.iter().zip(rb.root_children.iter()) {
            assert_eq!((x.0, x.1, x.2.to_bits()), (y.0, y.1, y.2.to_bits()));
        }
    }

    /// A full carried playout to terminal — the `oracle_score_pilot` shape.
    #[test]
    fn a_carried_playout_reaches_terminal() {
        let mut g = midgame("28000000001", 40);
        let mut s = SearchSession::new(SearchConfig {
            final_select: FinalSelect::Visits,
            ..cfg(48)
        });
        let mut plies = 0;
        let mut preexisting = 0;
        while !g.state.is_terminated() && plies < 200 {
            let r = s.search_carry(&g).unwrap();
            if s.last_root_n_before > 0 {
                preexisting += 1;
            }
            g.advance(r.chosen_action).unwrap();
            plies += 1;
        }
        assert!(g.state.is_terminated());
        assert!(
            preexisting as f64 > 0.8 * plies as f64,
            "the pilot measures a pre-existing root on ~99% of plies; got \
             {preexisting}/{plies}"
        );
    }
    /// ⛔ R6 (merge review 2026-08-30) — a CARRIED session refuses a SCOPED
    /// J-rules prior, at construction.
    ///
    /// The bug it fails closed on is invisible by construction: scope is
    /// decided when a node is EXPANDED and never recomputed, so a node expanded
    /// as an opponent node under ply `n` stays boosted when ply `n+1` re-roots
    /// onto it as an own-mover node. The expansion census cannot see it either
    /// (a carried node is not re-expanded), which is exactly why this is a
    /// refusal and not a counter.
    #[test]
    fn r6_carried_session_refuses_a_scoped_jrules_prior() {
        let scoped = |dose: f64, scope| SearchConfig {
            jrules_prior_dose: dose,
            jrules_prior_scope: scope,
            ..cfg(8)
        };
        for scope in [search::JrPriorScope::Own, search::JrPriorScope::Opp] {
            let e = SearchSession::try_new(scoped(1.0, scope))
                .err()
                .unwrap_or_else(|| panic!("{scope:?} was accepted by a carried session"));
            assert!(e.contains("R6"), "the refusal must name R6; got {e:?}");
            assert!(
                carried_scope_guard(&scoped(1.0, scope)).is_err(),
                "the free guard and the constructor must agree"
            );
        }
        // scope=all is immune (every node is boosted under every root), and so
        // is dose=0 (nothing is boosted at all) — both stay allowed, at every
        // scope value, so the champion and the `all` ladder are untouched.
        assert!(SearchSession::try_new(scoped(1.0, search::JrPriorScope::All)).is_ok());
        for scope in [
            search::JrPriorScope::All,
            search::JrPriorScope::Own,
            search::JrPriorScope::Opp,
        ] {
            assert!(
                SearchSession::try_new(scoped(0.0, scope)).is_ok(),
                "dose=0 must stay allowed at scope={scope:?}"
            );
        }
        // And the default config — the champion — is of course fine.
        assert!(SearchSession::try_new(cfg(8)).is_ok());
    }

    /// The infallible constructor is LOUD, not silent: the same R6 refusal.
    #[test]
    #[should_panic(expected = "R6")]
    fn r6_new_panics_rather_than_carrying_a_scoped_prior() {
        let _ = SearchSession::new(SearchConfig {
            jrules_prior_dose: 1.0,
            jrules_prior_scope: search::JrPriorScope::Opp,
            ..cfg(8)
        });
    }

    /// R6 fails closed on the SESSION only — a fresh-tree search at the same
    /// scoped config is untouched (it is what `fair::search_worlds` runs, and
    /// what the G3 cell plays).
    #[test]
    fn r6_does_not_touch_fresh_tree_searches() {
        let g = midgame("28000000000", 30);
        let r = search::search_single(
            &g,
            &SearchConfig {
                jrules_prior_dose: 1.0,
                jrules_prior_scope: search::JrPriorScope::Opp,
                ..cfg(64)
            },
        )
        .unwrap();
        assert!(r.jr_expansions_boosted > 0);
    }
}
