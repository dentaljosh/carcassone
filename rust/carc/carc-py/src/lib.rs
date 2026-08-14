//! `carc_rs` — PyO3 bindings for `carc-core`.
//!
//! P0 exposed the `compat` primitives. P1 adds [`MirrorState`] — the engine
//! mirror advanced by action ints, which is the wire format the reconcile
//! scripts drive. `FairAgentRs` / `choose_action` land with P3–P4.

use carc_core::compat;
use carc_core::endgame;
use carc_core::fair;
use carc_core::game::{deck_from_descriptions, deck_from_seed, Game, GameConfig};
use carc_core::leaf;
use carc_core::search;
use carc_core::tiles;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

// --------------------------------------------------------------------------
// P5: the rules-fix flags.  Every knob is OPT-IN; omitting all of them gives
// the byte-compatible walled engine of record (`start_rule` missing ⇒ engine,
// start (6, 15), no pre-placed tile).
// --------------------------------------------------------------------------

/// Resolve + validate the P5/F9 setup flags, surfacing every refusal as a
/// `ValueError` (unknown `start_rule`, odd shift, off-board start).
fn game_cfg(
    start_rule: Option<&str>,
    start_row: Option<i32>,
    start_col: Option<i32>,
    window_size: i32,
    cloister_scan_fix: Option<bool>,
    draw_rule: Option<&str>,
) -> PyResult<GameConfig> {
    GameConfig::resolve(
        start_rule,
        start_row,
        start_col,
        window_size,
        cloister_scan_fix,
        draw_rule,
    )
    .map_err(pyo3::exceptions::PyValueError::new_err)
}

/// The validated flags as a dict — the unit under test for the bridge's
/// `start_rule` semantics ("retail"/"engine"/missing ⇒ engine/unknown ⇒ raise)
/// and for the EVEN-shift assertion, without building a deck.
#[pyfunction]
#[pyo3(signature = (start_rule=None, start_row=None, start_col=None, window_size=25,
                    cloister_scan_fix=None, draw_rule=None))]
fn resolve_game_config<'py>(
    py: Python<'py>,
    start_rule: Option<&str>,
    start_row: Option<i32>,
    start_col: Option<i32>,
    window_size: i32,
    cloister_scan_fix: Option<bool>,
    draw_rule: Option<&str>,
) -> PyResult<Bound<'py, PyDict>> {
    let cfg = game_cfg(
        start_rule,
        start_row,
        start_col,
        window_size,
        cloister_scan_fix,
        draw_rule,
    )?;
    let d = PyDict::new(py);
    d.set_item("start_rule", cfg.start_rule.value())?;
    d.set_item("fixed_start_tile", cfg.start_rule.fixed_start_tile())?;
    d.set_item("start_row", cfg.start_row)?;
    d.set_item("start_col", cfg.start_col)?;
    d.set_item("window_size", cfg.window_size)?;
    d.set_item("cloister_scan_fix", cfg.cloister_scan_fix)?;
    d.set_item("draw_rule", cfg.draw_rule.value())?;
    d.set_item(
        "redraw_unplaceable",
        cfg.draw_rule.redraw_unplaceable(),
    )?;
    Ok(d)
}

// --------------------------------------------------------------------------
// P2: the leaf config
// --------------------------------------------------------------------------

/// A mirror of the flat-leaf-relevant fields of
/// `carcassonne_ai.virtual_score_v2.LeafConfig`.
///
/// Built explicitly from Python so the reconcile gate drives the *same* config
/// into both implementations; nothing about the champion leaf is hard-coded on
/// the Rust side (`LeafConfigRs.curve125()` is a convenience for tests only).
#[pyclass(name = "LeafConfigRs")]
#[derive(Clone)]
struct PyLeafConfig {
    inner: leaf::LeafConfig,
}

#[pymethods]
impl PyLeafConfig {
    #[new]
    #[pyo3(signature = (
        closure_p,
        bonus_cap,
        opp_bonus_cap,
        meeple_k = 0.0,
        v29_meeple_curve = None,
        soft_cap_slope = 0.0,
        opp_soft_cap_slope = 0.0,
        v29_meeple_return_k = 0.0,
        v29_farm_flip_k = 0.0,
        bag_close = false,
        tile_counting_closure = false,
        closure_continuous_slack = 0.0,
        farm_base_off = false,
        farm_growth_off = false,
        v29_phase_beta = 0.0,
        v29_phase_norm = 1.0,
        denial_dose = 0.0,
        denial_size_min = 8.0,
        denial_open_max = 2,
        opencity_dose = 0.0,
        opencity_size_min = 4.0,
        opencity_edge_min = 2,
        opencity_symmetric = true,
        opencity_cap = 0.0,
        jrules_dose = 0.0,
        jrules_mask = 31,
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        closure_p: Vec<(i32, f64)>,
        bonus_cap: f64,
        opp_bonus_cap: f64,
        meeple_k: f64,
        v29_meeple_curve: Option<Vec<f64>>,
        soft_cap_slope: f64,
        opp_soft_cap_slope: f64,
        v29_meeple_return_k: f64,
        v29_farm_flip_k: f64,
        bag_close: bool,
        tile_counting_closure: bool,
        closure_continuous_slack: f64,
        farm_base_off: bool,
        farm_growth_off: bool,
        v29_phase_beta: f64,
        v29_phase_norm: f64,
        denial_dose: f64,
        denial_size_min: f64,
        denial_open_max: i32,
        opencity_dose: f64,
        opencity_size_min: f64,
        opencity_edge_min: i32,
        opencity_symmetric: bool,
        opencity_cap: f64,
        jrules_dose: f64,
        jrules_mask: i64,
    ) -> Self {
        PyLeafConfig {
            inner: leaf::LeafConfig {
                closure_p,
                bonus_cap,
                opp_bonus_cap,
                meeple_k,
                v29_meeple_curve,
                soft_cap_slope,
                opp_soft_cap_slope,
                v29_meeple_return_k,
                v29_farm_flip_k,
                bag_close,
                tile_counting_closure,
                closure_continuous_slack,
                farm_base_off,
                farm_growth_off,
                v29_phase_beta,
                v29_phase_norm,
                denial_dose,
                denial_size_min,
                denial_open_max,
                opencity_dose,
                opencity_size_min,
                opencity_edge_min,
                opencity_symmetric,
                opencity_cap,
                jrules_dose,
                jrules_mask,
            },
        }
    }

    /// The champion leaf of record, `v2_9_2_Bmild_cap8_curve125`.
    #[staticmethod]
    fn curve125() -> Self {
        PyLeafConfig {
            inner: leaf::LeafConfig::curve125(),
        }
    }

    fn __repr__(&self) -> String {
        format!("{:?}", self.inner)
    }
}

fn leaf_err(e: leaf::LeafError) -> PyErr {
    match e {
        leaf::LeafError::UnsupportedConfig => pyo3::exceptions::PyNotImplementedError::new_err(
            "flat_closure_bonus implements only the v2.7 schedule path \
             (no tile_counting_closure / closure_continuous_slack)",
        ),
        leaf::LeafError::ReturnTermNeedsCurve => pyo3::exceptions::PyValueError::new_err(
            "v29_meeple_return_k requires v29_meeple_curve (Term R prices the \
             marginal step of the liquidity curve)",
        ),
        leaf::LeafError::NotTwoPlayer => {
            pyo3::exceptions::PyValueError::new_err("flat_virtual_score_v2 is 2-player only")
        }
    }
}

// --------------------------------------------------------------------------
// P1: the engine mirror state
// --------------------------------------------------------------------------

/// A Rust-side Carcassonne game advanced by flat action indices.
///
/// The constructor mirrors the two replay entry points in the spec:
/// `MirrorState.from_seed(deck_seed)` (CPython-MT-compatible deck shuffle) and
/// `MirrorState.from_deck([...])` (explicit deck; no RNG dependence, the phone
/// path).  `advance(action)` is called for **every** applied action, both seats.
#[pyclass(name = "MirrorState")]
struct PyMirrorState {
    game: Game,
}

#[pymethods]
impl PyMirrorState {
    /// `random.seed(deck_seed); Game().get_init_board()`.
    ///
    /// `deck_seed` is a **decimal string** so arbitrary-precision CPython ints
    /// round-trip (see the G0 mt19937 gate).
    #[staticmethod]
    #[pyo3(signature = (deck_seed, window_size=25, start_rule=None, start_row=None, start_col=None,
                        cloister_scan_fix=None, draw_rule=None))]
    fn from_seed(
        deck_seed: &str,
        window_size: i32,
        start_rule: Option<&str>,
        start_row: Option<i32>,
        start_col: Option<i32>,
        cloister_scan_fix: Option<bool>,
        draw_rule: Option<&str>,
    ) -> PyResult<Self> {
        let cfg = game_cfg(
            start_rule,
            start_row,
            start_col,
            window_size,
            cloister_scan_fix,
            draw_rule,
        )?;
        Ok(PyMirrorState {
            game: Game::from_deck_with_config(deck_from_seed(deck_seed), cfg)
                .map_err(pyo3::exceptions::PyValueError::new_err)?,
        })
    }

    /// Build from an explicit deck of tile descriptions, in draw order.
    #[staticmethod]
    #[pyo3(signature = (descriptions, window_size=25, start_rule=None, start_row=None,
                        start_col=None, cloister_scan_fix=None, draw_rule=None))]
    fn from_deck(
        descriptions: Vec<String>,
        window_size: i32,
        start_rule: Option<&str>,
        start_row: Option<i32>,
        start_col: Option<i32>,
        cloister_scan_fix: Option<bool>,
        draw_rule: Option<&str>,
    ) -> PyResult<Self> {
        let deck = deck_from_descriptions(&descriptions)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        let cfg = game_cfg(
            start_rule,
            start_row,
            start_col,
            window_size,
            cloister_scan_fix,
            draw_rule,
        )?;
        Ok(PyMirrorState {
            game: Game::from_deck_with_config(deck, cfg)
                .map_err(pyo3::exceptions::PyValueError::new_err)?,
        })
    }

    // --- P5: what setup flags is this mirror running under? ---------------

    /// `"engine"` | `"retail"` — the resolved start-tile convention.
    fn start_rule(&self) -> &'static str {
        self.game.cfg.start_rule.value()
    }

    /// F9-A2: is the cloister-completion scan fix on for this mirror?
    fn cloister_scan_fix(&self) -> bool {
        self.game.cfg.cloister_scan_fix
    }

    /// `state.cloister_completions_accelerated` — completions scored at their
    /// true ply that the legacy drifting window would not have visited.  Always
    /// 0 with the flag off; compared ply-by-ply against the Python counter by
    /// `scripts/rustport/lockstep_fuzz.py`, so the counter is itself a parity
    /// observable and not just a report.
    fn cloister_accel(&self) -> i64 {
        self.game.state.cloister_completions_accelerated
    }

    /// F9/A3 — `"engine"` | `"redraw"`, the resolved unplaceable-tile rule.
    fn draw_rule(&self) -> &'static str {
        self.game.cfg.draw_rule.value()
    }

    /// Tile descriptions that have left the game unplaced, in removal order —
    /// `CarcassonneGameState.set_aside_tiles`.  The lockstep observable for A3.
    fn set_aside_tiles(&self) -> Vec<String> {
        self.game
            .state
            .set_aside
            .iter()
            .map(|&b| carc_core::tiles::generated::BASE_TILES[b as usize].description.to_string())
            .collect()
    }

    /// `(row, col)` of `CarcassonneGameState.starting_position`.
    fn starting_position(&self) -> (i32, i32) {
        let sp = self.game.starting_position();
        (sp.row, sp.col)
    }

    /// `state.next_tile.description` — the drawn-but-unplayed tile.
    fn next_tile(&self) -> Option<&'static str> {
        self.game
            .state
            .next_tile
            .map(|b| tiles::tile(tiles::tile_id(b, 0)).description)
    }

    /// `Board.total_tiles` — `len(deck) + 1 + len(placed_coords)`.
    fn total_tiles(&self) -> i64 {
        self.game.total_tiles
    }

    /// `Board.tile_count` — the incremental centroid tile counter.
    fn tile_count(&self) -> i64 {
        self.game.tile_count
    }

    /// `sorted(state.placed_coords)` with each tile's `(description, rotation)`.
    /// The even-shift property leg compares these under the row transform.
    fn placed_tiles(&self) -> Vec<(i32, i32, String, u8)> {
        self.game
            .state
            .placed_coords
            .iter()
            .filter_map(|&(r, c)| {
                self.game.state.get_tile(r, c).map(|tid| {
                    let t = tiles::tile(tid);
                    (r, c, t.description.to_string(), t.rot)
                })
            })
            .collect()
    }

    /// Apply one flat action index.
    fn advance(&mut self, action: i32) -> PyResult<()> {
        self.game
            .advance(action)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// The exact `Game.string_representation` bytes.
    fn string_repr(&self) -> String {
        self.game.string_repr()
    }

    /// `hashlib.sha256(get_valid_moves(board).tobytes()).hexdigest()`.
    fn legal_mask_sha256(&self) -> String {
        self.game.legal_mask_sha256()
    }

    /// The legal mask as raw bytes (one `0`/`1` per action index).
    fn legal_mask_bytes<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new(py, &self.game.legal_mask().mask)
    }

    fn legal_actions(&self) -> Vec<i32> {
        self.game.legal_actions()
    }

    /// `(n_total, n_overflow)` from the mask build — the two counters
    /// `Game._compute_mask` uses for its `WindowOverflowError` conditions.
    fn mask_counts(&self) -> (usize, usize) {
        let m = self.game.legal_mask();
        (m.n_total, m.n_overflow)
    }

    fn scores(&self) -> (i64, i64) {
        let s = self.game.scores();
        (s[0], s[1])
    }

    fn meeples(&self) -> (i32, i32) {
        (self.game.state.meeples[0], self.game.state.meeples[1])
    }

    fn is_terminal(&self) -> bool {
        self.game.is_terminal()
    }

    fn current_player(&self) -> usize {
        self.game.state.current_player
    }

    fn phase(&self) -> &'static str {
        self.game.state.phase.value()
    }

    fn deck_len(&self) -> usize {
        self.game.state.deck_len()
    }

    /// `flat_leaf.flat_base_score(state, player)` — the exact terminal leaf.
    #[pyo3(signature = (player=0))]
    fn flat_base_score(&self, player: usize) -> i64 {
        self.game.flat_base_score(player)
    }

    /// `(origin_row, origin_col, size)` of the centered window.
    fn window_offset(&self) -> (i32, i32, i32) {
        let o = self.game.offset;
        (o.origin_row, o.origin_col, o.size)
    }

    /// A short content digest over repr + mask + scores + offset + terminal.
    fn state_digest(&self) -> String {
        self.game.state_digest()
    }

    // --- P3: the deck the search descends (determinization hook) ---------

    /// `state.deck` as Python sees it — the UNDRAWN tiles, in draw order
    /// (`next_tile` is already out of the list).
    fn unseen_deck(&self) -> Vec<String> {
        self.game.unseen_deck().into_iter().map(String::from).collect()
    }

    /// `board.state.deck[:] = [...]` — swap in one determinization world's deck.
    /// Length must match; `next_tile` and the placed board are untouched.
    fn set_unseen_deck(&mut self, descriptions: Vec<String>) -> PyResult<()> {
        self.game
            .set_unseen_deck(&descriptions)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    // --- P3: single-world PUCT -------------------------------------------

    /// Run ONE determinization world's PUCT search from this state.
    ///
    /// Equivalent to `HeuristicPriorAgent(game, cfg, sims).move(board)` with
    /// `reuse_tree=False` (a fresh tree + fresh legal-move cache per move) on a
    /// board whose deck is whatever `set_unseen_deck` last installed.
    ///
    /// Returns a dict; every float is a raw `f64` **bit pattern** (`int`) so the
    /// reconcile gate compares values, not decimal renderings.
    #[pyo3(signature = (cfg, trace_path=None, trace_expansions=true))]
    fn search_single<'py>(
        &self,
        py: Python<'py>,
        cfg: &PySearchConfig,
        trace_path: Option<&str>,
        trace_expansions: bool,
    ) -> PyResult<Bound<'py, PyDict>> {
        let r = match trace_path {
            None => py
                .allow_threads(|| search::search_single(&self.game, &cfg.inner))
                .map_err(search_err)?,
            Some(p) => {
                let f = std::fs::File::create(p)?;
                let w = std::io::BufWriter::new(f);
                let mut sink = search::JsonlTrace::new(w);
                sink.expansions = trace_expansions;
                let mut s = search::Searcher::with_trace(&cfg.inner, &mut sink);
                let r = s.search(&self.game).map_err(search_err)?;
                use std::io::Write;
                sink.into_inner().flush()?;
                r
            }
        };
        result_to_dict(py, &r)
    }

    /// `search_single` followed by `advance(chosen_action)` — the full-game
    /// driver's inner loop, one FFI hop per ply.
    fn search_and_advance<'py>(
        &mut self,
        py: Python<'py>,
        cfg: &PySearchConfig,
    ) -> PyResult<Bound<'py, PyDict>> {
        let r = py
            .allow_threads(|| search::search_single(&self.game, &cfg.inner))
            .map_err(search_err)?;
        self.game
            .advance(r.chosen_action)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        result_to_dict(py, &r)
    }

    // --- J-RULES PRIOR surface B: the parity probe ------------------------

    /// The J-rules PRIOR clock + per-legal-child term at THIS state's mover —
    /// the parity surface for `carcassonne_ai.jrules_priors` (the Python
    /// reference mirror). Floats are returned both as values and as raw f64
    /// bit patterns so the gate compares bits, not decimal renderings.
    ///
    /// This is exactly what `Searcher::evaluate` adds to each child's Δleaf
    /// (times the dose) before the prior softmax when
    /// `jrules_prior_dose != 0`.
    #[pyo3(signature = (mask=31))]
    fn jrules_prior_probe<'py>(
        &self,
        py: Python<'py>,
        mask: i64,
    ) -> PyResult<Bound<'py, PyDict>> {
        let g = &self.game;
        let mover = g.state.current_player;
        let mut scratch = leaf::LeafScratch::new();
        leaf::decompose_into(&g.state, &mut scratch.decomp, &mut scratch.scratch);
        let clock = leaf::jr_prior_clock(&g.state, mover, &scratch.decomp);
        let legal = g.legal_actions();
        let mut rows: Vec<(i32, f64, u64, f64)> = Vec::with_capacity(legal.len());
        for &a in &legal {
            let mut child = g.clone();
            child
                .advance(a)
                .map_err(pyo3::exceptions::PyValueError::new_err)?;
            leaf::decompose_into(&child.state, &mut scratch.decomp, &mut scratch.scratch);
            let base =
                leaf::flat_base_score_farm(&child.state, mover, &scratch.decomp, false) as f64;
            let t = leaf::jrules_prior_term(
                &child.state,
                mover,
                &scratch.decomp,
                mask,
                &clock,
                base,
            );
            rows.push((a, t, t.to_bits(), base));
        }
        let d = PyDict::new(py);
        d.set_item("mover", mover)?;
        d.set_item("mask", mask)?;
        d.set_item("k", clock.k)?;
        d.set_item("late_frac", clock.late_frac)?;
        d.set_item("late_frac_bits", clock.late_frac.to_bits())?;
        d.set_item("bag_farm_frac", clock.bag_farm_frac)?;
        d.set_item("bag_farm_frac_bits", clock.bag_farm_frac.to_bits())?;
        d.set_item("urg", clock.urg)?;
        d.set_item("urg_bits", clock.urg.to_bits())?;
        d.set_item("opp_reserve", clock.opp_reserve)?;
        d.set_item("parent_base", clock.parent_base)?;
        d.set_item("abs_margin", clock.abs_margin)?;
        d.set_item("parent_unclaimed", clock.parent_unclaimed)?;
        d.set_item("parent_unclaimed_bits", clock.parent_unclaimed.to_bits())?;
        d.set_item("children", rows)?;
        Ok(d)
    }

    // --- P2: the leaf ----------------------------------------------------

    /// `flat_leaf.flat_virtual_score_v2(state, player, cfg)`.
    fn leaf_value(&self, player: usize, cfg: &PyLeafConfig) -> PyResult<i64> {
        leaf::leaf_value(&self.game.state, player, &cfg.inner).map_err(leaf_err)
    }

    /// `flat_leaf.flat_virtual_score_v2_float(state, player, cfg)` — the
    /// pre-round float leaf (`leaf_quantize: float`, the champion's setting).
    fn leaf_value_float(&self, player: usize, cfg: &PyLeafConfig) -> PyResult<f64> {
        leaf::leaf_value_float(&self.game.state, player, &cfg.inner).map_err(leaf_err)
    }

    /// Both POVs at once off ONE decomposition: `(int_p0, int_p1, f64_p0, f64_p1)`.
    fn leaf_both(&self, cfg: &PyLeafConfig) -> PyResult<(i64, i64, f64, f64)> {
        let d = leaf::decompose(&self.game.state);
        let a = leaf::leaf_terms_with(&self.game.state, 0, &cfg.inner, &d).map_err(leaf_err)?;
        let b = leaf::leaf_terms_with(&self.game.state, 1, &cfg.inner, &d).map_err(leaf_err)?;
        Ok((a.value, b.value, a.score, b.score))
    }

    /// The per-term breakdown — the divergence-hunting view.  Keys mirror the
    /// intermediate names in `flat_virtual_score_v2`.
    fn leaf_terms<'py>(
        &self,
        py: Python<'py>,
        player: usize,
        cfg: &PyLeafConfig,
    ) -> PyResult<Bound<'py, pyo3::types::PyDict>> {
        let t = leaf::leaf_terms(&self.game.state, player, &cfg.inner).map_err(leaf_err)?;
        let d = pyo3::types::PyDict::new(py);
        d.set_item("base", t.base)?;
        d.set_item("bonus_self_raw", t.bonus_self_raw)?;
        d.set_item("bonus_opp_raw", t.bonus_opp_raw)?;
        d.set_item("bonus_self", t.bonus_self)?;
        d.set_item("bonus_opp", t.bonus_opp)?;
        d.set_item("denial_term", t.denial_term)?;
        d.set_item("opencity_term", t.opencity_term)?;
        d.set_item("jrules_term", t.jrules_term)?;
        d.set_item("meeple_term", t.meeple_term)?;
        d.set_item("return_term", t.return_term)?;
        d.set_item("flip_term", t.flip_term)?;
        d.set_item("score", t.score)?;
        d.set_item("value", t.value)?;
        Ok(d)
    }

    /// `flat_leaf.flat_base_score` via the **flat decomposition** (the P2 route),
    /// as opposed to `flat_base_score`, which is the engine's own
    /// `count_final_scores` route (P1).  They must agree everywhere.
    #[pyo3(signature = (player=0))]
    fn flat_base_score_decomp(&self, player: usize) -> i64 {
        let d = leaf::decompose(&self.game.state);
        leaf::flat_base_score(&self.game.state, player, &d)
    }

    // --- P7: the deep exact-K endgame solver -------------------------------

    /// `scripts/level2/endgame_solver.solve(game, board, mode, budget, alphabeta)`.
    ///
    /// Solves the CURRENT position exactly in either mode, at any K.  Returns a
    /// dict with `mode` / `value` / `value_bits` / `to_move` /
    /// `optimal_actions` / `child_values` (as `[(action, f64 raw bits)]`) /
    /// `nodes` / `tt_entries` / `wall_ms`, or **`None`** on `BudgetExceeded`
    /// (the Python raises; the gate treats a blown budget as "skip", so `None`
    /// is the honest wire value).
    ///
    /// `chance_drop` is the marginalized chance node's bag-removal reading —
    /// `"type"` is what the Python actually does and is the only value any gate
    /// should pass; `"one"` exists so the divergence stays nameable.
    ///
    /// **`tt_cap` changes `nodes`** (freeze-not-evict), so a node-count
    /// comparison must run both sides at the same cap.  The solve runs under
    /// `allow_threads`, so a Python-side pool is free to fan out.
    #[pyo3(signature = (mode="clairvoyant", budget=4_000_000, alphabeta=false,
                        tt_cap=0, chance_drop="type", objective="margin"))]
    fn solve_endgame<'py>(
        &self,
        py: Python<'py>,
        mode: &str,
        budget: u64,
        alphabeta: bool,
        tt_cap: usize,
        chance_drop: &str,
        objective: &str,
    ) -> PyResult<Option<Bound<'py, PyDict>>> {
        let m = endgame::Mode::parse(mode).map_err(pyo3::exceptions::PyValueError::new_err)?;
        let cfg = endgame::Config {
            budget,
            tt_cap,
            alphabeta,
            chance_drop: parse_chance_drop(chance_drop)?,
            // E1: "margin" = the untouched incumbent; "win" is marginalized-only
            // (the core rejects clairvoyant+win loudly).
            objective: fair::solver::Objective::parse(objective)
                .map_err(pyo3::exceptions::PyValueError::new_err)?,
        };
        let game = &self.game;
        let t0 = std::time::Instant::now();
        let res = py.allow_threads(|| endgame::solve(game, m, &cfg));
        let wall_ms = t0.elapsed().as_secs_f64() * 1e3;
        let res = match res {
            Err(fair::SolveError::BudgetExceeded) => return Ok(None),
            Err(e) => return Err(pyo3::exceptions::PyRuntimeError::new_err(e.to_string())),
            Ok(r) => r,
        };
        let d = PyDict::new(py);
        d.set_item("mode", res.mode.value())?;
        d.set_item("value", res.value)?;
        d.set_item("value_bits", res.value.to_bits())?;
        d.set_item("to_move", res.to_move)?;
        d.set_item("optimal_actions", res.optimal_actions)?;
        d.set_item(
            "child_values",
            res.child_values
                .iter()
                .map(|&(a, v)| (a, v.to_bits()))
                .collect::<Vec<_>>(),
        )?;
        d.set_item("nodes", res.nodes)?;
        d.set_item("tt_entries", res.tt_entries)?;
        d.set_item("wall_ms", wall_ms)?;
        // E1 win-objective payload (`None`/`[]` under objective="margin").
        d.set_item("objective", cfg.objective.value())?;
        d.set_item("win_value", res.win_value)?;
        d.set_item("win_value_bits", res.win_value.map(|v| v.to_bits()))?;
        d.set_item(
            "child_win_values",
            res.child_win_values
                .iter()
                .map(|&(a, v)| (a, v.to_bits()))
                .collect::<Vec<_>>(),
        )?;
        Ok(Some(d))
    }

    /// The independent brute force (`tests/test_endgame_solver._brute_root`) —
    /// pure clairvoyant minimax, **no TT and no pruning**.  Exponential; only
    /// usable at tiny K.  Returns `(value, optimal_actions, [(action, bits)])`,
    /// or `None` if `budget` recursion steps were exceeded.
    #[pyo3(signature = (budget=5_000_000))]
    #[allow(clippy::type_complexity)]
    fn brute_solve_endgame(
        &self,
        py: Python<'_>,
        budget: u64,
    ) -> PyResult<Option<(f64, Vec<i32>, Vec<(i32, u64)>)>> {
        let game = &self.game;
        match py.allow_threads(|| endgame::brute_clairvoyant_root(game, budget)) {
            Err(fair::SolveError::BudgetExceeded) => Ok(None),
            Err(e) => Err(pyo3::exceptions::PyRuntimeError::new_err(e.to_string())),
            Ok((v, opt, cv)) => Ok(Some((
                v,
                opt,
                cv.into_iter().map(|(a, x)| (a, x.to_bits())).collect(),
            ))),
        }
    }

    /// `k_remaining` — undrawn deck + the in-hand tile, the suites' key.
    fn k_remaining(&self) -> usize {
        self.game.state.deck_len() + usize::from(self.game.state.next_tile.is_some())
    }

    /// TEST HOOK — force an explicit board from `(row, col, description, rot)`.
    ///
    /// Clears the board, meeples and scores first.  The rules-oracle
    /// reproducers need hand-built positions that no legal play sequence has to
    /// be found for, and they must drive the *same* position through both
    /// engines; this is that seam.  Not used by any production path.
    fn set_board(&mut self, cells: Vec<(i32, i32, String, u8)>) -> PyResult<()> {
        let st = &mut self.game.state;
        for cell in st.board.iter_mut() {
            *cell = carc_core::engine::EMPTY;
        }
        st.placed_coords.clear();
        st.open_positions.clear();
        st.placed_meeples = [Vec::new(), Vec::new()];
        st.scores = [0, 0];
        for (row, col, desc, rot) in cells {
            if rot > 3 {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    format!("rotation {rot} out of range 0..=3"),
                ));
            }
            let base = tiles::generated::BASE_TILES
                .iter()
                .position(|t| t.description == desc.as_str())
                .ok_or_else(|| {
                    pyo3::exceptions::PyValueError::new_err(format!("unknown tile {desc:?}"))
                })? as u16;
            let idx = (row * carc_core::engine::BOARD_COLS + col) as usize;
            if row < 0 || col < 0 || idx >= st.board.len() {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    format!("({row}, {col}) is off the board"),
                ));
            }
            st.board[idx] = tiles::tile_id(base, rot);
            st.placed_coords.insert((row, col));
        }
        Ok(())
    }

    /// TEST HOOK — force explicit meeples from `(player, row, col, side, type)`.
    /// Companion to [`set_board`]; replaces `placed_meeples` wholesale.
    fn set_meeples(&mut self, meeples: Vec<(usize, i32, i32, String, String)>) -> PyResult<()> {
        use carc_core::engine::{MeeplePosition, MeepleType};
        let st = &mut self.game.state;
        st.placed_meeples = [Vec::new(), Vec::new()];
        for (player, row, col, side, kind) in meeples {
            if player > 1 {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    format!("player {player} out of range 0..=1"),
                ));
            }
            let mt = match kind.as_str() {
                "normal" => MeepleType::Normal,
                "abbot" => MeepleType::Abbot,
                "farmer" => MeepleType::Farmer,
                "big" => MeepleType::Big,
                "big_farmer" => MeepleType::BigFarmer,
                _ => {
                    return Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "unknown MeepleType value {kind:?}"
                    )))
                }
            };
            st.placed_meeples[player].push(MeeplePosition {
                meeple_type: mt,
                coord: carc_core::engine::Coord::new(row, col),
                side: side_from_value(&side)?,
            });
        }
        Ok(())
    }

    /// `flat_leaf.decompose(state).farm_anypos_root.get((row, col, side))` —
    /// the farm component id a `farmer_position` belongs to, straight off the
    /// **production Rust decomposition**.  `None` when that slot carries no
    /// farm.  Two positions share a farm iff they return the same id.
    fn farm_anypos_root(&self, row: i32, col: i32, side: &str) -> PyResult<Option<u32>> {
        let s = side_from_value(side)?;
        Ok(leaf::decompose(&self.game.state).farm_anypos_root(row, col, s))
    }

    /// The number of distinct farm components on the board — the coarse
    /// observable for "did two fields merge?".
    fn n_farm_components(&self) -> usize {
        let d = leaf::decompose(&self.game.state);
        let mut roots: Vec<u32> = d.farm_labels.clone();
        roots.sort_unstable();
        roots.dedup();
        roots.len()
    }

    /// `flat_leaf._bag_stats` — `(n, ge1, ge2, ge3, ge4)`.
    fn bag_stats(&self) -> (i32, i32, i32, i32, i32) {
        let b = leaf::bag_stats(&self.game.state);
        (b[0], b[1], b[2], b[3], b[4])
    }

    /// Force the state into the `champion_factory._empty(meeples)` shape used by
    /// the `_LEAF_VALUE_PANEL` semantic guard: empty board, no meeples placed,
    /// zero scores, `next_tile = None`, explicit free-meeple counts.
    fn make_empty_panel_state(&mut self, meeple_p0: i32, meeple_p1: i32) {
        let st = &mut self.game.state;
        for cell in st.board.iter_mut() {
            *cell = carc_core::engine::EMPTY;
        }
        st.placed_coords.clear();
        st.open_positions.clear();
        st.placed_meeples = [Vec::new(), Vec::new()];
        st.scores = [0, 0];
        st.next_tile = None;
        st.meeples = [meeple_p0, meeple_p1];
    }

    /// Time `repeats` bare `decompose(state)` calls — the share of the leaf that
    /// is board decomposition rather than scoring.
    fn bench_decompose(&self, repeats: usize, py: Python<'_>) -> (f64, usize) {
        let state = &self.game.state;
        py.allow_threads(|| {
            let t0 = std::time::Instant::now();
            let mut n = 0usize;
            for _ in 0..repeats {
                n += leaf::decompose(state).city_nodes.len();
            }
            (t0.elapsed().as_secs_f64(), n)
        })
    }

    /// Time `repeats` leaf evaluations of the current position, both POVs, off a
    /// fresh decomposition each time — the same work the Python/Cython leaf does
    /// per call.  Returns `(seconds, checksum)`; the checksum keeps the loop from
    /// being optimised away and cross-checks the values.
    fn bench_leaf(&self, cfg: &PyLeafConfig, repeats: usize, py: Python<'_>) -> PyResult<(f64, i64)> {
        let state = &self.game.state;
        let c = &cfg.inner;
        py.allow_threads(|| {
            let t0 = std::time::Instant::now();
            let mut checksum = 0i64;
            for _ in 0..repeats {
                for p in 0..2 {
                    checksum = checksum.wrapping_add(leaf::leaf_value(state, p, c).unwrap_or(0));
                }
            }
            Ok((t0.elapsed().as_secs_f64(), checksum))
        })
    }
}

/// The deck `random.seed(deck_seed)` produces, as tile descriptions in draw
/// order (index 0 is the tile immediately drawn into `next_tile`).
#[pyfunction]
fn deck_descriptions_from_seed(deck_seed: &str) -> Vec<String> {
    deck_from_seed(deck_seed)
        .into_iter()
        .map(|b| tiles::tile(tiles::tile_id(b, 0)).description.to_string())
        .collect()
}

/// `(source_sha256, semantic_digest)` compiled into `tiles/generated.rs` — the
/// drift guard against `engine/.../base_deck.py`.
#[pyfunction]
fn tile_data_digests() -> (String, String) {
    (
        tiles::generated::SOURCE_SHA256.to_string(),
        tiles::generated::SEMANTIC_DIGEST.to_string(),
    )
}

/// `Side` from its Python `.value` string.
fn side_from_value(v: &str) -> PyResult<tiles::Side> {
    use tiles::Side::*;
    Ok(match v {
        "top" => Top,
        "right" => Right,
        "bottom" => Bottom,
        "left" => Left,
        "center" => Center,
        "top_left" => TopLeft,
        "top_right" => TopRight,
        "bottom_left" => BottomLeft,
        "bottom_right" => BottomRight,
        _ => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "unknown Side value {v:?}"
            )))
        }
    })
}

/// Semantic digest of the deck **with R9 applied** — the flags-ON drift guard.
#[pyfunction]
fn tile_data_digest_r9() -> String {
    tiles::generated::SEMANTIC_DIGEST_R9.to_string()
}

/// Is the R9 field-on-city-edge fix active in this process?  (F9 remediation,
/// `CARCASSONNE_FIX_R9`, DEFAULT OFF — resolved once, at first use.)
#[pyfunction]
fn r9_enabled() -> bool {
    tiles::r9_enabled()
}

/// The R9 farm data as `(description, farm_slot, tile_connections, city_sides)`
/// for an explicit flag state — the python<->Rust farm-data parity gate, which
/// must be answerable for BOTH states inside one process.
#[pyfunction]
fn farm_table(r9: bool) -> Vec<(String, usize, u8, Vec<String>, Vec<String>, Vec<String>)> {
    let mut out = Vec::new();
    for t in tiles::registry_for(r9) {
        for (slot, fc) in t.farms.iter().enumerate() {
            out.push((
                t.description.to_string(),
                slot,
                t.rot,
                fc.farmer_positions.iter().map(|s| s.value().to_string()).collect(),
                fc.tile_connections.iter().map(|s| s.value().to_string()).collect(),
                fc.city_sides.iter().map(|s| s.value().to_string()).collect(),
            ));
        }
    }
    out
}

/// Every rotated tile as `(description, rot, edge_type_repr_signature)` — used
/// by the tile-rotation reconcile against `Tile.turn` + `get_type`.
#[pyfunction]
fn rotated_tile_table() -> Vec<(String, u8, String)> {
    tiles::registry()
        .iter()
        .map(|t| (t.description.to_string(), t.rot, t.rot_sig_repr.clone()))
        .collect()
}

// --------------------------------------------------------------------------
// mt19937
// --------------------------------------------------------------------------

/// `random.seed(seed); random.shuffle(list(range(n)))` — the resulting permutation.
///
/// `seed` is a **decimal string** so arbitrary-precision CPython int seeds
/// (>= 2^64) round-trip exactly. `mode` is `"global"` or `"random"`.
#[pyfunction]
#[pyo3(signature = (seed, n, mode="global"))]
fn shuffle_indices(seed: &str, n: usize, mode: &str) -> PyResult<Vec<u32>> {
    let m = match mode {
        "global" => compat::SeedMode::GlobalSeed,
        "random" => compat::SeedMode::RandomInstance,
        other => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "mode must be 'global' or 'random', got {other:?}"
            )))
        }
    };
    Ok(compat::shuffle_indices(seed, m, n))
}

/// The little-endian 32-bit word vector CPython's `random_seed()` builds.
#[pyfunction]
fn seed_words(seed: &str) -> Vec<u32> {
    compat::mt19937::seed_words_from_decimal(seed)
}

/// `[genrand_uint32() for _ in range(count)]` after seeding with `seed`.
#[pyfunction]
fn genrand_uint32_stream(seed: &str, count: usize) -> Vec<u32> {
    let mut mt = compat::MT19937::from_py_int_seed_decimal(seed);
    (0..count).map(|_| mt.genrand_uint32()).collect()
}

/// `[getrandbits(k) for k in ks]` after seeding with `seed` (`k <= 64`).
#[pyfunction]
fn getrandbits_stream(seed: &str, ks: Vec<u32>) -> Vec<u64> {
    let mut mt = compat::MT19937::from_py_int_seed_decimal(seed);
    ks.into_iter().map(|k| mt.getrandbits(k)).collect()
}

/// `[_randbelow(n) for n in ns]` after seeding with `seed`.
#[pyfunction]
fn randbelow_stream(seed: &str, ns: Vec<u64>) -> Vec<u64> {
    let mut mt = compat::MT19937::from_py_int_seed_decimal(seed);
    ns.into_iter().map(|n| mt.randbelow(n)).collect()
}

// --------------------------------------------------------------------------
// fsum / npsum
// --------------------------------------------------------------------------

/// `math.fsum(xs)`.
#[pyfunction]
fn fsum(xs: Vec<f64>) -> f64 {
    compat::fsum(&xs)
}

/// `math.fsum` applied to each row of a flat buffer of `n_rows * row_len` f64s.
/// Batched to keep the 10^6-case reconcile fuzz out of per-call FFI overhead.
#[pyfunction]
fn fsum_batch(flat: Vec<f64>, offsets: Vec<usize>) -> Vec<f64> {
    offsets
        .windows(2)
        .map(|w| compat::fsum(&flat[w[0]..w[1]]))
        .collect()
}

/// `np.sum(np.asarray(xs, dtype=np.float64))`.
#[pyfunction]
fn np_sum_f64(xs: Vec<f64>) -> f64 {
    compat::np_sum_f64(&xs)
}

/// `np.sum(np.asarray(xs, dtype=np.float32))`.
#[pyfunction]
fn np_sum_f32(xs: Vec<f32>) -> f32 {
    compat::np_sum_f32(&xs)
}

/// Batched `np.sum` over ragged f64 rows described by a prefix-offset array.
#[pyfunction]
fn np_sum_f64_batch(flat: Vec<f64>, offsets: Vec<usize>) -> Vec<f64> {
    offsets
        .windows(2)
        .map(|w| compat::np_sum_f64(&flat[w[0]..w[1]]))
        .collect()
}

/// Batched `np.sum` over ragged f32 rows described by a prefix-offset array.
#[pyfunction]
fn np_sum_f32_batch(flat: Vec<f32>, offsets: Vec<usize>) -> Vec<f32> {
    offsets
        .windows(2)
        .map(|w| compat::np_sum_f32(&flat[w[0]..w[1]]))
        .collect()
}

// --------------------------------------------------------------------------
// libm compat
// --------------------------------------------------------------------------

/// `exp(x)` — ARM optimized-routines port, no FMA contraction.
#[pyfunction]
fn exp64(x: f64) -> f64 {
    compat::exp64(x)
}

/// `exp(x)` — the same algorithm with FMA contraction (glibc `-mfma` variant).
#[pyfunction]
fn exp64_fma(x: f64) -> f64 {
    compat::exp64_fma(x)
}

/// `tanh(x)` — fdlibm port.
#[pyfunction]
fn tanh64(x: f64) -> f64 {
    compat::tanh64(x)
}

/// `expm1(x)` — fdlibm port (the kernel `tanh64` is built on).
#[pyfunction]
fn expm1_64(x: f64) -> f64 {
    compat::expm1_64(x)
}

fn parse_flavor(name: &str) -> PyResult<compat::LibmFlavor> {
    Ok(match name {
        "msun" => compat::LibmFlavor::Msun,
        "msun_fma" => compat::LibmFlavor::MsunFma,
        "glibc" => compat::LibmFlavor::Glibc,
        "glibc_fma" => compat::LibmFlavor::GlibcFma,
        other => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "flavor must be one of msun|msun_fma|glibc|glibc_fma, got {other:?}"
            )))
        }
    })
}

/// `expm1(x)` under an explicit platform hypothesis.
#[pyfunction]
#[pyo3(signature = (x, flavor="msun"))]
fn expm1_64_flavor(x: f64, flavor: &str) -> PyResult<f64> {
    Ok(compat::expm1_64_flavor(x, parse_flavor(flavor)?))
}

/// `tanh(x)` under an explicit platform hypothesis.
#[pyfunction]
#[pyo3(signature = (x, flavor="msun"))]
fn tanh64_flavor(x: f64, flavor: &str) -> PyResult<f64> {
    Ok(compat::tanh64_flavor(x, parse_flavor(flavor)?))
}

/// The four platform hypotheses, in the order the harness reports them.
#[pyfunction]
fn libm_flavors() -> Vec<String> {
    ["msun", "msun_fma", "glibc", "glibc_fma"].iter().map(|s| s.to_string()).collect()
}

/// Vectorised `exp64` over a little-endian f64 byte buffer; returns the results
/// as a byte buffer. Buffer-in/buffer-out keeps the 10^8-sample harness from
/// paying Python list-boxing costs.
#[pyfunction]
fn exp64_buf<'py>(py: Python<'py>, xs: &[u8], fma: bool) -> PyResult<Bound<'py, PyBytes>> {
    map_f64_buf(py, xs, |v| if fma { compat::exp64_fma(v) } else { compat::exp64(v) })
}

/// Vectorised `tanh64` over a little-endian f64 byte buffer, under an explicit
/// platform hypothesis.
#[pyfunction]
#[pyo3(signature = (xs, flavor="msun"))]
fn tanh64_buf<'py>(py: Python<'py>, xs: &[u8], flavor: &str) -> PyResult<Bound<'py, PyBytes>> {
    let f = parse_flavor(flavor)?;
    map_f64_buf(py, xs, |v| compat::tanh64_flavor(v, f))
}

/// Vectorised `expm1` over a little-endian f64 byte buffer.
#[pyfunction]
#[pyo3(signature = (xs, flavor="msun"))]
fn expm1_64_buf<'py>(py: Python<'py>, xs: &[u8], flavor: &str) -> PyResult<Bound<'py, PyBytes>> {
    let f = parse_flavor(flavor)?;
    map_f64_buf(py, xs, |v| compat::expm1_64_flavor(v, f))
}

fn map_f64_buf<'py>(
    py: Python<'py>,
    xs: &[u8],
    f: impl Fn(f64) -> f64,
) -> PyResult<Bound<'py, PyBytes>> {
    if xs.len() % 8 != 0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "buffer length must be a multiple of 8",
        ));
    }
    let n = xs.len() / 8;
    let mut out = vec![0u8; xs.len()];
    for i in 0..n {
        let mut b = [0u8; 8];
        b.copy_from_slice(&xs[i * 8..i * 8 + 8]);
        let y = f(f64::from_le_bytes(b));
        out[i * 8..i * 8 + 8].copy_from_slice(&y.to_le_bytes());
    }
    Ok(PyBytes::new(py, &out))
}

// --------------------------------------------------------------------------
// P3: single-world PUCT search
// --------------------------------------------------------------------------

/// Every knob `mcts.NeuralMCTS` + `HeuristicPriorConfig` read, driven in from
/// Python (`governance/PRODUCTION.yaml champion.agent_knobs`).  Nothing about
/// the champion search is defaulted on the Rust side beyond what a test needs.
#[pyclass(name = "SearchConfigRs")]
#[derive(Clone)]
struct PySearchConfig {
    inner: search::SearchConfig,
}

#[pymethods]
impl PySearchConfig {
    #[new]
    #[pyo3(signature = (
        leaf_cfg,
        simulations,
        c_puct,
        tau_p,
        value_norm,
        score_norm_scale=15.0,
        leaf_quantize="float",
        final_select="visits",
        fpu_reduction=None,
        c_lcb=1.0,
        exp_fma=true,
        tanh_flavor="glibc_fma",
        jrules_prior_dose=0.0,
        jrules_prior_mask=31,
        jrules_prior_scope="all",
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        leaf_cfg: &PyLeafConfig,
        simulations: usize,
        c_puct: f64,
        tau_p: f64,
        value_norm: f64,
        score_norm_scale: f64,
        leaf_quantize: &str,
        final_select: &str,
        fpu_reduction: Option<f64>,
        c_lcb: f64,
        exp_fma: bool,
        tanh_flavor: &str,
        jrules_prior_dose: f64,
        jrules_prior_mask: i64,
        jrules_prior_scope: &str,
    ) -> PyResult<Self> {
        let lq = match leaf_quantize {
            "float" => search::LeafQuantize::Float,
            "int" => search::LeafQuantize::Int,
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "leaf_quantize must be 'float'|'int'; got {other:?}"
                )))
            }
        };
        let fs = match final_select {
            "visits" => search::FinalSelect::Visits,
            "Q" | "q" => search::FinalSelect::Q,
            "lcb" => search::FinalSelect::Lcb,
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "final_select must be 'visits'|'Q'|'lcb'; got {other:?}"
                )))
            }
        };
        // J-RULES PRIOR surface B (search-level knobs; NOT LeafConfig fields —
        // they move no leaf hash). Validated even at dose 0 so a typo'd scope
        // or an out-of-range mask never rides silently.
        let jr_scope = match jrules_prior_scope {
            "all" => search::JrPriorScope::All,
            "own" => search::JrPriorScope::Own,
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "jrules_prior_scope must be 'all'|'own'; got {other:?}"
                )))
            }
        };
        if !jrules_prior_dose.is_finite() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "jrules_prior_dose must be finite",
            ));
        }
        if jrules_prior_mask & !leaf::JR_ALL != 0 || jrules_prior_mask == 0 {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "jrules_prior_mask {jrules_prior_mask} invalid: must be nonzero and within \
                 JR_ALL ({})",
                leaf::JR_ALL
            )));
        }
        Ok(PySearchConfig {
            inner: search::SearchConfig {
                c_puct,
                tau_p,
                value_norm,
                score_norm_scale,
                leaf_quantize: lq,
                simulations,
                fpu_reduction,
                final_select: fs,
                c_lcb,
                exp_fma,
                tanh_flavor: parse_flavor(tanh_flavor)?,
                use_leaf_scratch: true,
                leaf: leaf_cfg.inner.clone(),
                jrules_prior_dose,
                jrules_prior_mask,
                jrules_prior_scope: jr_scope,
            },
        })
    }

    /// The resolved J-rules-prior knobs — what a manifest must stamp (the
    /// wiring gate for surface B is the RESOLVED dose, never the leaf hash,
    /// which this surface deliberately does not move).
    #[getter]
    fn jrules_prior(&self) -> (f64, i64, &'static str) {
        (
            self.inner.jrules_prior_dose,
            self.inner.jrules_prior_mask,
            match self.inner.jrules_prior_scope {
                search::JrPriorScope::All => "all",
                search::JrPriorScope::Own => "own",
            },
        )
    }

    #[getter]
    fn simulations(&self) -> usize {
        self.inner.simulations
    }

    /// A copy with a different sim budget (the breadth/verdict ladder).
    fn with_simulations(&self, simulations: usize) -> Self {
        let mut c = self.clone();
        c.inner.simulations = simulations;
        c
    }

    fn __repr__(&self) -> String {
        let i = &self.inner;
        // The J-rules-prior suffix appears ONLY when the dose is live, so every
        // default-off (champion) repr is byte-identical to the pre-B string.
        let jr = if i.jrules_prior_dose != 0.0 {
            format!(
                ", jrules_prior_dose={}, jrules_prior_mask={}, jrules_prior_scope={:?}",
                i.jrules_prior_dose, i.jrules_prior_mask, i.jrules_prior_scope
            )
        } else {
            String::new()
        };
        format!(
            "SearchConfigRs(sims={}, c_puct={}, tau_p={}, value_norm={}, \
             leaf_quantize={:?}, final_select={:?}, fpu={:?}, exp_fma={}, tanh={:?}{})",
            i.simulations,
            i.c_puct,
            i.tau_p,
            i.value_norm,
            i.leaf_quantize,
            i.final_select,
            i.fpu_reduction,
            i.exp_fma,
            i.tanh_flavor,
            jr
        )
    }
}

pyo3::create_exception!(
    carc_rs,
    WindowTruncationError,
    pyo3::exceptions::PyRuntimeError,
    "F-c: the search reached a node whose entire legal move list fell OUTSIDE \
     the action window (`measurement/window_truncation_20260813/DESIGN.md` §6-P3). \
     A subclass of `RuntimeError`, so every existing `except RuntimeError` / \
     `except BaseException` guard keeps working; the TYPE is what distinguishes a \
     truncation-caused empty action set from any other cause. The message carries \
     `EMPTY_MASK_DIAG={json}` — read it with \
     `carcassonne_ai.window_truncation.parse_diag`."
);

fn search_err(e: search::SearchError) -> PyErr {
    match e {
        search::SearchError::Leaf(le) => leaf_err(le),
        // F-c: truncation gets its own EXCEPTION TYPE; the other empty-mask
        // causes stay `RuntimeError` but still carry the diagnosis, so the two
        // can never be confused for one another in a dossier.
        search::SearchError::EmptyMaskAtInterior(ref d) if d.is_truncation() => {
            WindowTruncationError::new_err(e.to_string())
        }
        other => pyo3::exceptions::PyRuntimeError::new_err(other.to_string()),
    }
}

fn result_to_dict<'py>(
    py: Python<'py>,
    r: &search::SearchResult,
) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("chosen_action", r.chosen_action)?;
    let pack = |v: &Vec<(i32, i64, f64)>| -> Vec<(i32, i64, u64)> {
        v.iter().map(|&(a, n, w)| (a, n, w.to_bits())).collect()
    };
    d.set_item("root_children", pack(&r.root_children))?;
    d.set_item("deduped", pack(&r.deduped))?;
    // P4: `fair_agent.root_stats_list` — deduped, N>0, ROOT-POV-signed W.
    d.set_item("pooled_stats", pack(&r.pooled_stats))?;
    d.set_item("root_player", r.root_player)?;
    d.set_item("root_n", r.root_n)?;
    d.set_item("root_w_bits", r.root_w.to_bits())?;
    d.set_item("root_leaf_value_bits", r.root_leaf_value.to_bits())?;
    d.set_item(
        "root_priors",
        r.root_priors
            .iter()
            .map(|&(a, p)| (a, p.to_bits()))
            .collect::<Vec<_>>(),
    )?;
    d.set_item("node_count", r.node_count)?;
    d.set_item("leaf_evals", r.leaf_evals)?;
    Ok(d)
}

// --------------------------------------------------------------------------
// P6: the PERSISTENT / RE-ROOTABLE tree (Gap 2)
// --------------------------------------------------------------------------

/// A search whose tree **outlives the call** — `HeuristicPriorAgent`'s other
/// search semantics, and the one feature the whole oracle / clairvoyant
/// instrument tier was blocked on.
///
/// [`MirrorState::search_single`] is fresh-tree only (`.move()` with
/// `reuse_tree=False`).  The Python rulers reach the search through
/// `best_action()`, which **never clears** `NeuralMCTS._nodes`, so a caller that
/// drives an advancing game with it (`oracle_score_pilot._playout_value`, every
/// ply to terminal) runs ONE tree across the whole playout.  Measured, not read
/// off the source: `measurement/rustport_p6/GAP2_ORACLE_CONTINUATION_TREE.json`
/// finds the per-ply root pre-existing with `N > sims` on 102/103 plies, and a
/// fresh-tree replay of the identical world diverging in 4/4 positions.
///
/// ⚠️ **OPT-IN, AND NOTHING ELSE CHANGES.**  This is a NEW class; `MirrorState`,
/// `FairAgentRs` and `SearchConfigRs` are untouched, and the champion path
/// (`FairAgentRs.choose_action`, k-parallel PIMC, fresh tree per world) does not
/// reach a line of this code.  A `PersistentSearcher` that is never constructed
/// costs the process nothing.
///
/// USAGE — the mirror contract is the same one `RustFairAgent` /
/// `RustClairvoyantAgent` document: seat it, then `advance()` EVERY applied
/// action of BOTH seats.
///
/// ```python
/// ms = carc_rs.MirrorState.from_seed(str(deck_seed))     # seat via the gated path
/// for a in prefix: ms.advance(a)
/// ps = carc_rs.PersistentSearcher(ms, scfg)              # clones the mirror's game
/// ps.set_unseen_deck([t.description for t in world.state.deck])
/// ps.advance(pick)
/// while not ps.is_terminal():
///     res = ps.search_and_advance()                      # carry + step, one FFI hop
/// ```
///
/// THREADS: unlike `search_single`, this does **not** release the GIL.  The tree
/// it holds across calls is `Rc`-interned (a deliberate per-thread choice — see
/// `search::Node::key`), so `&mut SearchSession` is not `Send`.  Every caller of
/// this class is a game-parallel `mp.Pool` farm (separate processes, separate
/// GILs), where releasing it would buy nothing.
/// `unsendable`: the retained tree interns its node keys with `Rc` (the
/// per-thread choice the search made deliberately), so the object is pinned to
/// the thread that built it and PyO3 raises if another one touches it.  That is
/// the honest contract — a silently shared tree would be a data race — and it
/// costs nothing: every caller is a game-parallel `mp.Pool` farm.
#[pyclass(name = "PersistentSearcher", unsendable)]
struct PyPersistentSearcher {
    game: Game,
    session: search::SearchSession,
}

#[pymethods]
impl PyPersistentSearcher {
    /// Clone `mirror`'s position into a private game and open an EMPTY tree.
    ///
    /// Seating goes through `MirrorState` on purpose: `from_seed` + `advance`
    /// over the recorded prefix is the byte-equal counterpart of
    /// `root_replay.replay_actions`, already gated by G1/G4, and duplicating it
    /// here would be a second thing to keep true.
    #[new]
    fn new(mirror: &PyMirrorState, cfg: &PySearchConfig) -> Self {
        PyPersistentSearcher {
            game: mirror.game.clone(),
            session: search::SearchSession::new(cfg.inner.clone()),
        }
    }

    // --- the mirror surface (this object owns its own game) ----------------

    fn advance(&mut self, action: i32) -> PyResult<()> {
        self.game
            .advance(action)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    fn string_repr(&self) -> String {
        self.game.string_repr()
    }

    fn state_digest(&self) -> String {
        self.game.state_digest()
    }

    fn legal_actions(&self) -> Vec<i32> {
        self.game.legal_actions()
    }

    fn is_terminal(&self) -> bool {
        self.game.is_terminal()
    }

    fn current_player(&self) -> usize {
        self.game.state.current_player
    }

    fn scores(&self) -> (i64, i64) {
        let s = self.game.scores();
        (s[0], s[1])
    }

    fn unseen_deck(&self) -> Vec<String> {
        self.game.unseen_deck().into_iter().map(String::from).collect()
    }

    /// Install one determinization world's deck (`MirrorState.set_unseen_deck`).
    /// Does NOT touch the tree — the caller decides whether the retained
    /// statistics are still meaningful (they are, for a clairvoyant playout
    /// whose deck is installed once, before the first search).
    fn set_unseen_deck(&mut self, descriptions: Vec<String>) -> PyResult<()> {
        self.game
            .set_unseen_deck(&descriptions)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    // --- the three Python transitions --------------------------------------

    /// `HeuristicPriorAgent.best_action(board)` — search on the CARRIED tree.
    fn search<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let r = self.session.search_carry(&self.game).map_err(search_err)?;
        self.carry_dict(py, &r)
    }

    /// `HeuristicPriorAgent.move(board)` with `reuse_tree=False` — `clear()`,
    /// then search.  Bit-for-bit `MirrorState.search_single`.
    fn search_fresh<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let r = self.session.search_fresh(&self.game).map_err(search_err)?;
        self.carry_dict(py, &r)
    }

    /// `HeuristicPriorAgent.move(board)` with `reuse_tree=True` —
    /// `_reroot_or_clear`, then search.
    fn search_reroot<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let r = self.session.search_reroot(&self.game).map_err(search_err)?;
        self.carry_dict(py, &r)
    }

    /// Carried search + `advance(chosen_action)` — the playout loop's inner
    /// step, one FFI hop per ply.
    fn search_and_advance<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let r = self.session.search_carry(&self.game).map_err(search_err)?;
        self.game
            .advance(r.chosen_action)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        self.carry_dict(py, &r)
    }

    /// `NeuralMCTS.clear()`.
    fn clear(&mut self) {
        self.session.clear();
    }

    /// `HeuristicPriorAgent._reroot_or_clear(board)` on the CURRENT position.
    /// Returns `("hit"|"fresh"|"collide", visits_carried_in)` — the three
    /// `reuse_hits` / `reuse_fresh` / `reuse_collide` outcomes.
    fn reroot(&mut self) -> (&'static str, i64) {
        let rr = self.session.reroot_to(&self.game);
        (rr.label(), rr.carried())
    }

    // --- introspection (the gap-2 diagnostics) -----------------------------

    /// `len(mcts._nodes)`.
    fn tree_len(&self) -> usize {
        self.session.tree_len()
    }

    /// `mcts._nodes[key].N` for the current position, 0 if absent — the
    /// pre-search root visit count the GAP2 measurement counts.
    fn root_n(&self) -> i64 {
        self.session.root_n_at(&self.game)
    }

    fn searches(&self) -> u64 {
        self.session.searches
    }

    fn __repr__(&self) -> String {
        format!(
            "PersistentSearcher(sims={}, nodes={}, searches={})",
            self.session.cfg.simulations,
            self.session.tree_len(),
            self.session.searches
        )
    }
}

impl PyPersistentSearcher {
    /// `result_to_dict` plus the carry diagnostics.  The shared keys are
    /// byte-identical to `search_single`'s, so one comparator serves both.
    fn carry_dict<'py>(
        &self,
        py: Python<'py>,
        r: &search::SearchResult,
    ) -> PyResult<Bound<'py, PyDict>> {
        let d = result_to_dict(py, r)?;
        d.set_item("root_n_before", self.session.last_root_n_before)?;
        d.set_item("carried", self.session.last_root_n_before > 0)?;
        d.set_item("tree_len", self.session.tree_len())?;
        d.set_item(
            "reroot",
            self.session.last_reroot.map(|rr| rr.label()),
        )?;
        Ok(d)
    }
}

// --------------------------------------------------------------------------
// P4: the fair agent (k-parallel PIMC + the one-way exact latch)
// --------------------------------------------------------------------------

fn fair_err(e: fair::FairError) -> PyErr {
    match e {
        fair::FairError::Search(se) => search_err(se),
        fair::FairError::NoLegalActions => pyo3::exceptions::PyValueError::new_err(
            "fair agent asked to move with no legal actions",
        ),
        other => pyo3::exceptions::PyRuntimeError::new_err(other.to_string()),
    }
}

fn parse_chance_drop(s: &str) -> PyResult<fair::ChanceDrop> {
    match s {
        "type" => Ok(fair::ChanceDrop::Type),
        "one" => Ok(fair::ChanceDrop::One),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "chance_drop must be 'type' (the Python semantics) | 'one'; got {other:?}"
        ))),
    }
}

/// `carcassonne_ai.fair_agent.FairHeuristicPriorAgent`, in Rust.
///
/// The champion of record (`governance/PRODUCTION.yaml champion.fair_deploy`)
/// is `k_dets=8, sims_per_det=1376`; **nothing is defaulted from that here** —
/// every knob is driven in from Python.
///
/// The whole of [`Self::choose_action`] (latch → solver → PIMC → k world
/// threads → pooled merge) runs under `allow_threads`, which is the entire
/// point on Chaquopy: the GIL forbids Python world-threads, so the k-parallel
/// win has to happen below the FFI boundary.
#[pyclass(name = "FairAgentRs")]
struct PyFairAgent {
    agent: fair::FairAgent,
    game: Option<Game>,
    /// P5 setup flags for the games this agent starts.  Default = the walled
    /// engine of record; `start_rule=None` means "engine", exactly as a save
    /// payload with no `start_rule` field does on the bridge.
    game_cfg: GameConfig,
}

#[pymethods]
impl PyFairAgent {
    #[new]
    #[pyo3(signature = (
        search_cfg,
        k_dets,
        seed,
        min_pooled_visits = 2.0,
        exact_endgame = true,
        exact_max_k = 2,
        exact_budget = 2_000_000,
        tt_cap = 0,
        chance_drop = "type",
        exact_objective = "margin",
        threads = 1,
        window_size = 25,
        start_rule = None,
        start_row = None,
        start_col = None,
        cloister_scan_fix = None,
        draw_rule = None,
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        search_cfg: &PySearchConfig,
        k_dets: usize,
        seed: i64,
        min_pooled_visits: f64,
        exact_endgame: bool,
        exact_max_k: i64,
        exact_budget: u64,
        tt_cap: usize,
        chance_drop: &str,
        exact_objective: &str,
        threads: usize,
        window_size: i32,
        start_rule: Option<&str>,
        start_row: Option<i32>,
        start_col: Option<i32>,
        cloister_scan_fix: Option<bool>,
        draw_rule: Option<&str>,
    ) -> PyResult<Self> {
        // The agent takes the SAME rules knobs as the mirror, so a flags-on
        // eval cannot silently be graded under the flags-off convention.
        let gcfg = game_cfg(
            start_rule,
            start_row,
            start_col,
            window_size,
            cloister_scan_fix,
            draw_rule,
        )?;
        if k_dets < 1 {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "k_dets must be >= 1, got {k_dets}"
            )));
        }
        if exact_max_k < 0 {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "exact_max_k must be >= 0, got {exact_max_k}"
            )));
        }
        if threads < 1 {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "threads must be >= 1, got {threads}"
            )));
        }
        let cfg = fair::FairConfig {
            search: search_cfg.inner.clone(),
            k_dets,
            seed,
            min_pooled_visits,
            exact_endgame,
            exact_max_k,
            solver: fair::SolverConfig {
                budget: exact_budget,
                tt_cap,
                chance_drop: parse_chance_drop(chance_drop)?,
                // E1 (surface-B convention): a SOLVER/search-side knob, never
                // LeafConfig — the leaf hash must not move.  "margin" is the
                // untouched incumbent code path.
                objective: fair::solver::Objective::parse(exact_objective)
                    .map_err(pyo3::exceptions::PyValueError::new_err)?,
            },
            threads,
        };
        Ok(PyFairAgent {
            agent: fair::FairAgent::new(cfg),
            game: None,
            game_cfg: gcfg,
        })
    }

    /// `random.seed(deck_seed); Game().get_init_board()` — the farms/tests path.
    fn start_game_from_seed(&mut self, deck_seed: &str) -> PyResult<()> {
        self.game = Some(
            Game::from_deck_with_config(deck_from_seed(deck_seed), self.game_cfg)
                .map_err(pyo3::exceptions::PyValueError::new_err)?,
        );
        self.reset();
        Ok(())
    }

    /// An explicit deck of tile descriptions in draw order — the phone path
    /// (no RNG dependence at all).
    fn start_game_from_deck(&mut self, descriptions: Vec<String>) -> PyResult<()> {
        let deck = deck_from_descriptions(&descriptions)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        self.game = Some(
            Game::from_deck_with_config(deck, self.game_cfg)
                .map_err(pyo3::exceptions::PyValueError::new_err)?,
        );
        self.reset();
        Ok(())
    }

    /// `"engine"` | `"retail"` — the resolved start-tile convention.
    fn start_rule(&self) -> &'static str {
        self.game_cfg.start_rule.value()
    }

    /// Apply one action — **every** applied action, BOTH seats.
    fn advance(&mut self, action: i32) -> PyResult<()> {
        self.game_mut()?
            .advance(action)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Pick the fair move for the current state.
    ///
    /// `move_idx` defaults to the agent's own counter (which always advances);
    /// pass it explicitly when a harness owns the move timeline.
    ///
    /// `sims_override` (default None = the constructed budget, byte-identical)
    /// is a PER-CALL per-world sims budget for THIS decision's PIMC search —
    /// the sims-split (`sims_tile`/`sims_meeple`) seam. Stateless: the agent's
    /// config is never mutated (`stats()["sims_per_det"]` keeps naming the
    /// constructed budget; `last_move()["sims_used"]` names what this decision
    /// ran), and it cannot touch the mirror, the latch or the determinization
    /// RNG — see `FairAgent::choose_action_with_sims`.
    #[pyo3(signature = (move_idx=None, sims_override=None))]
    fn choose_action(
        &mut self,
        py: Python<'_>,
        move_idx: Option<i64>,
        sims_override: Option<usize>,
    ) -> PyResult<i32> {
        if sims_override == Some(0) {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "sims_override must be >= 1 (or None for the constructed budget)",
            ));
        }
        let game = match self.game.as_ref() {
            None => return Err(no_game()),
            Some(g) => g,
        };
        let agent = &mut self.agent;
        py.allow_threads(|| agent.choose_action_with_sims(game, move_idx, sims_override))
            .map_err(fair_err)
    }

    /// `choose_action` followed by `advance(action)` — the driver's inner loop,
    /// one FFI hop per ply.
    #[pyo3(signature = (move_idx=None, sims_override=None))]
    fn choose_and_advance(
        &mut self,
        py: Python<'_>,
        move_idx: Option<i64>,
        sims_override: Option<usize>,
    ) -> PyResult<i32> {
        let a = self.choose_action(py, move_idx, sims_override)?;
        self.advance(a)?;
        Ok(a)
    }

    /// Solve the CURRENT position with the marginalized expectiminimax, ignoring
    /// the latch — the solver-parity leg drives this directly against
    /// `scripts/level2/endgame_solver.solve(mode="marginalized")`.
    ///
    /// Returns `None` on `BudgetExceeded` (what the agent sees), else a dict
    /// with `value_bits` / `optimal_actions` / `child_values` (raw bits) /
    /// `nodes` / `to_move`.
    #[pyo3(signature = (budget=None, objective=None))]
    fn solve_marginalized<'py>(
        &self,
        py: Python<'py>,
        budget: Option<u64>,
        objective: Option<&str>,
    ) -> PyResult<Option<Bound<'py, PyDict>>> {
        let game = match self.game.as_ref() {
            None => return Err(no_game()),
            Some(g) => g,
        };
        let mut cfg = self.agent.cfg.solver.clone();
        if let Some(b) = budget {
            cfg.budget = b;
        }
        // E1: per-call objective override (None = the agent's constructed
        // objective) — the both-objectives-one-position instrument seam.
        if let Some(o) = objective {
            cfg.objective = fair::solver::Objective::parse(o)
                .map_err(pyo3::exceptions::PyValueError::new_err)?;
        }
        let res = py.allow_threads(|| fair::solver::solve_marginalized(game, &cfg));
        let res = match res {
            Err(fair::SolveError::BudgetExceeded) => return Ok(None),
            Err(e) => {
                return Err(pyo3::exceptions::PyRuntimeError::new_err(e.to_string()));
            }
            Ok(r) => r,
        };
        let d = PyDict::new(py);
        d.set_item("value_bits", res.value.to_bits())?;
        d.set_item("value", res.value)?;
        d.set_item("to_move", res.to_move)?;
        d.set_item("optimal_actions", res.optimal_actions)?;
        d.set_item(
            "child_values",
            res.child_values
                .iter()
                .map(|&(a, v)| (a, v.to_bits()))
                .collect::<Vec<_>>(),
        )?;
        d.set_item("nodes", res.nodes)?;
        // E1 win-objective payload (`None`/`[]` in margin mode — the liveness
        // discriminator the parity/positive-control tests read).
        d.set_item("objective", cfg.objective.value())?;
        d.set_item("win_value", res.win_value)?;
        d.set_item("win_value_bits", res.win_value.map(|v| v.to_bits()))?;
        d.set_item(
            "child_win_values",
            res.child_win_values
                .iter()
                .map(|&(a, v)| (a, v.to_bits()))
                .collect::<Vec<_>>(),
        )?;
        Ok(Some(d))
    }

    /// The `k_dets` determinized decks this move would draw, as description
    /// lists in world order — the determinizer's own parity surface.
    fn determinizations(&self, move_idx: i64) -> PyResult<Vec<Vec<String>>> {
        let game = match self.game.as_ref() {
            None => return Err(no_game()),
            Some(g) => g,
        };
        let base = fair::det_seed_base(self.agent.cfg.seed, move_idx);
        let mut rng = carc_core::compat::mt19937::MT19937::from_py_int_seed_i64(base + 1);
        let mut out = Vec::with_capacity(self.agent.cfg.k_dets);
        for _ in 0..self.agent.cfg.k_dets {
            let w = fair::reshuffled_determinization(game, &mut rng)
                .map_err(pyo3::exceptions::PyValueError::new_err)?;
            out.push(w.unseen_deck().into_iter().map(String::from).collect());
        }
        Ok(out)
    }

    fn det_seed_base(&self, move_idx: i64) -> i64 {
        fair::det_seed_base(self.agent.cfg.seed, move_idx)
    }

    fn det_search_seed(&self, move_idx: i64, det_idx: usize) -> i64 {
        fair::det_search_seed(self.agent.cfg.seed, move_idx, det_idx)
    }

    /// Everything a manifest needs: the harness counters, the latch state, the
    /// solver totals and the LAST move's full record (pooled floats as raw bits).
    fn stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let a = &self.agent;
        let d = PyDict::new(py);
        d.set_item("move_idx", a.move_idx)?;
        d.set_item("latched", a.latched)?;
        d.set_item("latch_k", a.latch_k)?;
        d.set_item("neural_moves", 0)?; // harness symmetry only
        d.set_item("heur_moves", a.heur_moves)?;
        d.set_item("forced_moves", a.forced_moves)?;
        d.set_item("exact_moves", a.exact_moves)?;
        d.set_item("n_timeouts", a.n_timeouts)?;
        d.set_item("solver_nodes", a.solver_nodes)?;
        d.set_item("solver_secs", a.solver_secs)?;
        d.set_item("max_solve_secs", a.max_solve_secs)?;
        d.set_item(
            "last_pooled_visits",
            a.last_pooled_visits.clone(),
        )?;
        d.set_item("k_dets", a.cfg.k_dets)?;
        d.set_item("sims_per_det", a.cfg.search.simulations)?;
        d.set_item("threads", a.cfg.threads)?;
        d.set_item("seed", a.cfg.seed)?;
        d.set_item("exact_max_k", a.cfg.exact_max_k)?;
        d.set_item("exact_budget", a.cfg.solver.budget)?;
        // E1: the RESOLVED objective — the manifest liveness surface (the leaf
        // hash deliberately does not move on this knob, surface-B style).
        d.set_item("exact_objective", a.cfg.solver.objective.value())?;
        d.set_item("min_pooled_visits", a.cfg.min_pooled_visits)?;
        d.set_item("last_move", self.last_move(py)?)?;
        Ok(d)
    }

    /// The last decision's record.  `pooled` is `[(action, N_bits, W_bits)]` in
    /// pool INSERTION order — the raw floats the gate compares.
    fn last_move<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let m = &self.agent.last_move;
        let d = PyDict::new(py);
        d.set_item("move_idx", m.move_idx)?;
        d.set_item("action", m.action)?;
        d.set_item("exact", m.exact)?;
        d.set_item("latched", m.latched)?;
        d.set_item("forced", m.forced)?;
        d.set_item("timeout", m.timeout)?;
        d.set_item("solver_nodes", m.solver_nodes)?;
        d.set_item("solver_value_bits", m.solver_value.map(|v| v.to_bits()))?;
        d.set_item("solver_optimal", m.solver_optimal.clone())?;
        d.set_item("secs", m.secs)?;
        d.set_item("k_remaining", m.k_remaining)?;
        d.set_item("sims_used", m.sims_used)?;
        d.set_item(
            "pooled",
            m.pooled
                .iter()
                .map(|&(a, n, w)| (a, n.to_bits(), w.to_bits()))
                .collect::<Vec<_>>(),
        )?;
        Ok(d)
    }

    // --- mirror-state read-off (reconcile mode compares these) -------------

    fn string_repr(&self) -> PyResult<String> {
        Ok(self.game()?.string_repr())
    }

    fn state_digest(&self) -> PyResult<String> {
        Ok(self.game()?.state_digest())
    }

    fn legal_actions(&self) -> PyResult<Vec<i32>> {
        Ok(self.game()?.legal_actions())
    }

    fn unseen_deck(&self) -> PyResult<Vec<String>> {
        Ok(self.game()?.unseen_deck().into_iter().map(String::from).collect())
    }

    fn set_unseen_deck(&mut self, descriptions: Vec<String>) -> PyResult<()> {
        self.game_mut()?
            .set_unseen_deck(&descriptions)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    fn is_terminal(&self) -> PyResult<bool> {
        Ok(self.game()?.is_terminal())
    }

    fn scores(&self) -> PyResult<(i64, i64)> {
        let s = self.game()?.scores();
        Ok((s[0], s[1]))
    }

    fn current_player(&self) -> PyResult<usize> {
        Ok(self.game()?.state.current_player)
    }

    fn phase(&self) -> PyResult<&'static str> {
        Ok(self.game()?.state.phase.value())
    }

    fn k_remaining(&self) -> PyResult<i64> {
        Ok(fair::k_remaining(self.game()?))
    }

    /// Seat the one-way latch explicitly.
    ///
    /// The latch is a function of the game's HISTORY (the first TILES decision
    /// with `k_remaining <= exact_max_k`), so a harness that jumps the agent
    /// onto a mid-game position via `advance()` alone — which never runs
    /// `choose_action`, hence never evaluates the trigger — must seat it.  The
    /// trigger itself is gated organically by the full-game legs, and its
    /// trajectory over the whole record by the `latch` leg of
    /// `scripts/rustport/reconcile_fair.py`.
    #[pyo3(signature = (latched, latch_k=None))]
    fn set_latched(&mut self, latched: bool, latch_k: Option<i64>) {
        self.agent.latched = latched;
        self.agent.latch_k = latch_k;
    }

    /// Seat the move counter (`FairHeuristicPriorAgent._move_idx`).
    fn set_move_idx(&mut self, move_idx: i64) {
        self.agent.move_idx = move_idx;
    }

    fn set_threads(&mut self, threads: usize) -> PyResult<()> {
        if threads < 1 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "threads must be >= 1",
            ));
        }
        self.agent.cfg.threads = threads;
        Ok(())
    }

    /// Reset the move counter, the latch and every counter (a fresh game on the
    /// same agent).  Called by both `start_game_*`.
    fn reset(&mut self) {
        let cfg = self.agent.cfg.clone();
        self.agent = fair::FairAgent::new(cfg);
    }
}

impl PyFairAgent {
    fn game(&self) -> PyResult<&Game> {
        self.game.as_ref().ok_or_else(no_game)
    }
    fn game_mut(&mut self) -> PyResult<&mut Game> {
        self.game.as_mut().ok_or_else(no_game)
    }
}

fn no_game() -> PyErr {
    pyo3::exceptions::PyRuntimeError::new_err(
        "no game started — call start_game_from_seed() or start_game_from_deck() first",
    )
}

#[pymodule]
fn carc_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", carc_core::VERSION)?;
    m.add("WindowTruncationError", m.py().get_type::<WindowTruncationError>())?;
    m.add("EMPTY_MASK_DIAG_MARKER", search::EMPTY_MASK_DIAG_MARKER)?;
    m.add_function(wrap_pyfunction!(shuffle_indices, m)?)?;
    m.add_function(wrap_pyfunction!(seed_words, m)?)?;
    m.add_function(wrap_pyfunction!(genrand_uint32_stream, m)?)?;
    m.add_function(wrap_pyfunction!(getrandbits_stream, m)?)?;
    m.add_function(wrap_pyfunction!(randbelow_stream, m)?)?;
    m.add_function(wrap_pyfunction!(fsum, m)?)?;
    m.add_function(wrap_pyfunction!(fsum_batch, m)?)?;
    m.add_function(wrap_pyfunction!(np_sum_f64, m)?)?;
    m.add_function(wrap_pyfunction!(np_sum_f32, m)?)?;
    m.add_function(wrap_pyfunction!(np_sum_f64_batch, m)?)?;
    m.add_function(wrap_pyfunction!(np_sum_f32_batch, m)?)?;
    m.add_function(wrap_pyfunction!(exp64, m)?)?;
    m.add_function(wrap_pyfunction!(exp64_fma, m)?)?;
    m.add_function(wrap_pyfunction!(tanh64, m)?)?;
    m.add_function(wrap_pyfunction!(expm1_64, m)?)?;
    m.add_function(wrap_pyfunction!(expm1_64_flavor, m)?)?;
    m.add_function(wrap_pyfunction!(tanh64_flavor, m)?)?;
    m.add_function(wrap_pyfunction!(libm_flavors, m)?)?;
    m.add_function(wrap_pyfunction!(expm1_64_buf, m)?)?;
    m.add_function(wrap_pyfunction!(exp64_buf, m)?)?;
    m.add_function(wrap_pyfunction!(tanh64_buf, m)?)?;
    // P1
    m.add_class::<PyMirrorState>()?;
    // P2
    m.add_class::<PyLeafConfig>()?;
    // P3
    m.add_class::<PySearchConfig>()?;
    // P4
    m.add_class::<PyFairAgent>()?;
    // P6 (Gap 2) — the persistent / re-rootable tree. Opt-in: constructing it is
    // the only way to reach a carried search; nothing above changes.
    m.add_class::<PyPersistentSearcher>()?;
    m.add_function(wrap_pyfunction!(resolve_game_config, m)?)?;
    m.add("RETAIL_START_TILE", carc_core::game::RETAIL_START_TILE)?;
    m.add("DEFAULT_START_ROW", carc_core::game::DEFAULT_START_ROW)?;
    m.add("DEFAULT_START_COL", carc_core::game::DEFAULT_START_COL)?;
    m.add_function(wrap_pyfunction!(deck_descriptions_from_seed, m)?)?;
    m.add_function(wrap_pyfunction!(tile_data_digests, m)?)?;
    m.add_function(wrap_pyfunction!(tile_data_digest_r9, m)?)?;
    m.add_function(wrap_pyfunction!(r9_enabled, m)?)?;
    m.add_function(wrap_pyfunction!(farm_table, m)?)?;
    m.add_function(wrap_pyfunction!(rotated_tile_table, m)?)?;
    Ok(())
}
