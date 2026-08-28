//! Port of the `tier1-greedy` continuation playout — the arbiter's cost core.
//!
//! Python twins, verbatim:
//!
//!   * [`RuleBasedPlayer`] — `src/carcassonne_ai/rule_based_player.py`
//!     (`choose_action` / `_choose_meeple` / `_choose_tile` /
//!     `_best_by_virtual_score`), whose per-candidate score is
//!     `virtual_score.virtual_score_inplace` = deepcopy the state, apply the
//!     action in place, `PointsCollector.count_final_scores`, read
//!     `scores[player] - scores[1 - player]`.  The Rust analogue is
//!     [`crate::engine::GameState::count_final_scores`] on a clone, i.e. exactly
//!     [`crate::engine::GameState::flat_base_score`] — the two-hop equality
//!     `virtual_score == flat_leaf.flat_base_score == rust` is gated by
//!     `tests/test_flat_leaf_edge_cases.py` and
//!     `scripts/rustport/reconcile_engine.py`.
//!   * [`tier1_playout`] — `scripts/measurement_infra/oracle_score_pilot.py::_playout_value`
//!     with `--oracle-policy tier1-greedy` (`_GreedyContinuation`).
//!   * [`tier1_leg`] — the same file's `_process`: root replay, then per world
//!     ONE `reshuffled_determinization` shared by BOTH picks (the CRN), then a
//!     playout per pick, each with a FRESH `RuleBasedPlayer(playout_seed)`.
//!
//! Nothing in this module is reachable from any pre-existing path; it is purely
//! additive.
//!
//! ## The RNG contract (the part that silently breaks bit-exactness)
//!
//! `random.Random.choice(seq)` is `seq[self._randbelow(len(seq))]`, and
//! `_randbelow_with_getrandbits(n)` draws `getrandbits(n.bit_length())` in a
//! rejection loop.  **For `n == 1` that still consumes `getrandbits(1)` and
//! loops until it draws 0** — it is NOT a free call.  Two paths consume NO draw
//! at all, and both are reachable in real games:
//!
//!   1. `choose_action` returning the single legal action (Rule 1);
//!   2. `_best_by_virtual_score` returning early on `len(legal) == 1`, which in
//!      the meeple phase happens *after* the Rule 3 / Rule 2 filters collapse
//!      the candidate set to one.
//!
//! Getting either of those wrong desynchronizes the stream for the rest of the
//! playout.
//!
//! ## ⚠️ The legal-mask cache is LOAD-BEARING, and it is load-bearing because it
//! ## is BUGGY ([`LegalMaskCache`])
//!
//! `game_wrapper.Game.get_valid_moves` memoizes the legal mask on the `Game`
//! object under `Game.string_representation(board)`, and
//! `oracle_score_pilot._process` builds ONE `Game` per position-record — so a
//! single cache spans that record's root query and all `2 x m` playouts.
//!
//! That key is **not injective**.  Its per-tile component,
//! `_tile_rotation_signature` = `(4 outer edges, shield, chapel, flowers)`,
//! cannot tell rotation 0 from rotation 2 of a 180°-rotationally-symmetric tile
//! — the witness is `city_left_right`, whose edges read
//! `('grass', 'city', 'grass', 'city')` at both — while the tile's FARM SLOTS do
//! rotate (`farmer_positions` / `tile_connections` are permuted).  Two genuinely
//! different boards therefore share one key and the second to ask is handed the
//! first's mask, which offers a FARMER corner that is not legal here and
//! withholds the one that is (observed: cached-minus-fresh `[2506]` = FARMER
//! TopLeft, fresh-minus-cached `[2509]` = FARMER BottomRight).  The greedy
//! continuation then plays a different move and the playout ends on a different
//! terminal score.
//!
//! This is **not cosmetic and not optional**: on the committed `G-BITEXACT`
//! sample it moved 57 of 15,360 banked playout values (0.371%).  The Stage-1b
//! corpus is BURNED and cannot be regenerated, so a port that computes the mask
//! honestly does not reproduce it.  [`LegalMaskCache`] therefore reproduces the
//! Python memo **including its collisions**, and `tier1_leg`'s
//! `legal_mask_cache` flag switches it:
//!
//!   * `true`  — byte-faithful to the banked judge.  **This is what `G-BITEXACT`
//!     grades and what the cost re-measure prices**, because it is the player
//!     that produced the adjudicated ladder.
//!   * `false` — the honest mask, recomputed every ply.  Use it to *measure* the
//!     defect (`scripts/tiletie/diagnose_tier1_cache_collision.py`), never to
//!     grade the gate.
//!
//! The collision is a defect in `game_wrapper`, not in this module, and fixing
//! it there is a separate decision with its own blast radius (the same key is
//! the MCTS transposition key).  Nothing here changes `game_wrapper`.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};

use crate::action_space::{decode, meeple_farmer_base, meeple_pass_index};
use crate::compat::mt19937::MT19937;
use crate::engine::{GameState, Phase, BOARD_COLS, BOARD_ROWS};
use crate::fair::reshuffled_determinization;
use crate::game::{deck_from_seed, Game};
use crate::leaf::{decompose_into, flat_base_score, Decomp, Scratch};
use crate::repr_key::string_representation;

// ---------------------------------------------------------------------------
// The per-candidate scorer (the playout's 97.4 %)
// ---------------------------------------------------------------------------
//
// `_best_by_virtual_score` scores every candidate with the terminal leaf.  Two
// routes compute that same i64:
//
//   * ENGINE ROUTE — `GameState::count_final_scores` on the scratch afterstate.
//     The literal Python twin (`virtual_score_inplace`), and what this module
//     called until 2026-08-28.  It re-runs a from-scratch flood fill per placed
//     meeple, allocating ~690 times per call.
//   * FLAT ROUTE — `leaf::decompose_into` (whole-board int union-find, allocation
//     free after warm-up, caller-owned buffers) + `leaf::flat_base_score`.
//
// The equality is the two-hop `virtual_score == flat_leaf.flat_base_score ==
// rust` named in the module docs, gated by the P2 suite on every position, by
// DECISIONS 2026-07-31 (G1) on 134,172 evaluations across the whole game record,
// and by `measurement/arb_costopt_prep/PROFILE_TIER1.md` on 238,203 / 238,203
// tier1 candidate values plus 216 / 216 whole playouts identical in
// `(margin, plies)`.  The flat route measured **7.90× end to end** there, which
// is why it is the deployed one.  This is a bit-identical replacement: no flag,
// no config knob, no strength claim owed.
//
// ## ⚠️ THE BORDER HAZARD — why there is still a fallback
//
// The two routes read the board through DIFFERENT accessors, and the difference
// is observable at exactly one place:
//
//   * the engine route reaches the board through [`GameState::board_direct`],
//     which reproduces CPython's `board[row][column]` **including the negative
//     index wrap** — `board_direct(-1, c)` returns the tile at ROW 34.
//   * the flat route reads [`GameState::get_tile`], which is honestly
//     bounds-checked and answers "no tile" outside the grid
//     (`leaf::decomp` line 487/531, `leaf::cloister_points`).
//
// Every index either route can produce is one step off a placed tile (or the
// cloister 3x3), so a `-1` query needs a tile on row 0 / column 0 — which is
// constant on the production hot path (row 0 is occupied in 77 % of the recorded
// champion corpus) — and the wrap only ANSWERS DIFFERENTLY when the cell it
// wraps to, row 34 / column 34, is occupied.  That same last-row / last-column
// occupancy is the historical FATAL class: before the 2026-08-23 `board_direct`
// fix the engine route raised `IndexError` there while `flat_base_score` scored
// the position fine (DECISIONS 2026-07-31, the fourth border face).
//
// So the divergence set and the historical crash set are the same set, and it is
// named by a purely local predicate: **does any placed tile sit on row 34 or
// column 34**.  [`border_wrap_hazard`] tests exactly that, and when it fires the
// candidate is scored by the LEGACY ENGINE ROUTE — including whatever the legacy
// route would do, panic included.  Behaviour is therefore identical **by
// construction** on every position, not by an unreachability argument, and the
// domain is not silently widened.  [`border_fallbacks`] counts the fires so a
// gate can report the expected 0 rather than assume it.

/// Per-thread buffers for the flat route.
///
/// `decompose_into` is allocation-free only if the caller keeps the buffers, so
/// ONE pair is reused across candidates, plies and playouts.  They live in
/// thread-local storage rather than on a threaded-through `&mut` because
/// [`crate::tiearb::arbitrate`] drives playouts from a `Fn + Sync` closure across
/// `std::thread::scope` workers: TLS gives every worker its own pair with no
/// sharing, no locks, and no API change (`PROFILE_TIER1.md` §4.6 item 7).
#[derive(Default)]
struct ScorerBufs {
    decomp: Decomp,
    scratch: Scratch,
}

thread_local! {
    static SCORER_BUFS: RefCell<ScorerBufs> = RefCell::new(ScorerBufs::default());
    /// ⚠️ GATES AND TESTS ONLY — see [`with_legacy_scorer`].
    static FORCE_LEGACY: Cell<bool> = const { Cell::new(false) };
}

/// How many candidate evaluations took the legacy fallback because the board
/// touched the wrapping border.  Process-wide, monotonic, `Relaxed`; only ever
/// written on the (expected-unreachable) fallback path, so it costs the hot path
/// nothing.
static BORDER_FALLBACKS: AtomicU64 = AtomicU64::new(0);

/// Reads [`BORDER_FALLBACKS`] — the identity gate's receipt that the border
/// class never fired.
pub fn border_fallbacks() -> u64 {
    BORDER_FALLBACKS.load(Ordering::Relaxed)
}

/// Zeroes [`border_fallbacks`] so a gate can scope a count to its own pass.
pub fn reset_border_fallbacks() {
    BORDER_FALLBACKS.store(0, Ordering::Relaxed);
}

/// Does this board occupy the last row or the last column?
///
/// The predicate that separates the two scorer routes — see the module comment
/// above.  A superset of the true divergence set (which additionally needs a
/// tile on row 0 / column 0 to issue the `-1` query), chosen because it is also
/// exactly the historical crash class and because it is one pass over
/// `placed_coords` (≤ 72 entries, once per DECISION, not per candidate).
#[inline]
fn border_wrap_hazard(state: &GameState) -> bool {
    state
        .placed_coords
        .iter()
        .any(|&(r, c)| r >= BOARD_ROWS - 1 || c >= BOARD_COLS - 1)
}

/// The per-candidate leaf by the LEGACY ENGINE ROUTE — `count_final_scores` on a
/// clone, `scores[player] - scores[opp]`.
///
/// Kept public and callable so the identity gates can contrast the routes on
/// identical afterstates.  Identical to [`GameState::flat_base_score`]; named
/// here so a gate reads as what it is testing.
pub fn candidate_leaf_legacy(after: &GameState, player: usize) -> i64 {
    let mut s = after.clone();
    s.count_final_scores();
    s.scores[player] - s.scores[1 - player]
}

/// The per-candidate leaf by the FLAT ROUTE, allocating its own buffers.
///
/// The deployed path uses the thread-local buffers instead; this is the gate /
/// test entry point.
pub fn candidate_leaf_flat(after: &GameState, player: usize) -> i64 {
    let mut d = Decomp::default();
    let mut sc = Scratch::default();
    decompose_into(after, &mut d, &mut sc);
    flat_base_score(after, player, &d)
}

/// Restores [`FORCE_LEGACY`] even if `f` unwinds.
struct LegacyGuard(bool);
impl Drop for LegacyGuard {
    fn drop(&mut self) {
        FORCE_LEGACY.with(|c| c.set(self.0));
    }
}

/// ⚠️ **GATES AND TESTS ONLY.** Runs `f` with the per-candidate scorer forced
/// back to the legacy engine route **on this thread**.
///
/// This is not a configuration knob and nothing in production calls it: the swap
/// is bit-identical, so there is no shape to choose between. It exists so an
/// identity gate can run BOTH routes over the same seeds — at playout and at
/// `arbitrate` granularity — instead of re-implementing the RNG contract.
#[doc(hidden)]
pub fn with_legacy_scorer<R>(f: impl FnOnce() -> R) -> R {
    let prev = FORCE_LEGACY.with(|c| c.replace(true));
    let _g = LegacyGuard(prev);
    f()
}

/// The deployed per-candidate scorer: flat route, thread-local buffers, legacy
/// fallback at the border.  `after` is the scratch afterstate and is consumed
/// (the legacy route mutates it).
#[inline]
fn candidate_leaf(after: &mut GameState, player: usize, bufs: &mut ScorerBufs) -> i64 {
    if border_wrap_hazard(after) {
        BORDER_FALLBACKS.fetch_add(1, Ordering::Relaxed);
        after.count_final_scores();
        return after.scores[player] - after.scores[1 - player];
    }
    decompose_into(after, &mut bufs.decomp, &mut bufs.scratch);
    flat_base_score(after, player, &bufs.decomp)
}

/// `game_wrapper.Game._legal_cache` — the per-`Game` legal-mask memo, keyed by
/// the byte-exact `string_representation`.
///
/// Collisions are REPRODUCED, not repaired: see the module docs.  The key is
/// produced by [`crate::repr_key::string_representation`], which is byte-exact
/// to the Python (G1), so two boards collide here exactly when they collide
/// there.
#[derive(Default)]
pub struct LegalMaskCache {
    map: HashMap<String, Vec<i32>>,
    pub hits: u64,
    pub misses: u64,
}

impl LegalMaskCache {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn len(&self) -> usize {
        self.map.len()
    }

    pub fn is_empty(&self) -> bool {
        self.map.is_empty()
    }
}

/// `RuleBasedPlayer(seed=...)` — one RNG stream, driving BOTH seats.
pub struct RuleBasedPlayer {
    rng: MT19937,
}

impl RuleBasedPlayer {
    /// `random.Random(seed)` on an `int` — CPython's `init_by_array` over the
    /// little-endian 32-bit words of `abs(seed)`.
    pub fn new(seed: i64) -> Self {
        RuleBasedPlayer {
            rng: MT19937::from_py_int_seed_i64(seed),
        }
    }

    /// `choose_action(game, board, valid_mask)`.
    ///
    /// `legal` is `np.flatnonzero(valid_mask)` — ascending action indices — which
    /// is exactly what `game.get_valid_moves` yields.
    pub fn choose_action(
        &mut self,
        g: &Game,
        cache: Option<&mut LegalMaskCache>,
    ) -> Result<i32, String> {
        Ok(self.decide(g, cache)?.action)
    }

    /// `choose_action`, plus the intermediate quantities a divergence probe
    /// needs (the legal set, the post-filter candidate set, and the per-candidate
    /// int64 leaf scores).  The hot path drops them; nothing extra is computed.
    pub fn decide(
        &mut self,
        g: &Game,
        cache: Option<&mut LegalMaskCache>,
    ) -> Result<Decision, String> {
        let legal = legal_actions_checked(g, cache)?;
        if legal.is_empty() {
            return Err("no legal moves — game should have ended".to_string());
        }
        // Rule 1: forced move.  NO RNG DRAW.
        if legal.len() == 1 {
            let a = legal[0];
            return Ok(Decision {
                action: a,
                legal,
                candidates: Vec::new(),
                scores: Vec::new(),
                player: g.state.current_player,
            });
        }
        match g.state.phase {
            Phase::Meeples => self.choose_meeple(g, legal),
            Phase::Tiles => {
                let c = legal.clone();
                self.best_by_virtual_score(g, legal, c)
            }
        }
    }

    /// `_choose_meeple` — Rule 3 (no early farmers) is applied FIRST, then
    /// Rule 2 (force-place near the endgame), then Rule 5 (best 1-ply
    /// virtual_score) over whatever survives.  The order is load-bearing: a
    /// swap changes which candidate set reaches the argmax.
    fn choose_meeple(&mut self, g: &Game, legal: Vec<i32>) -> Result<Decision, String> {
        let w = g.window_size;
        let farmer_base = meeple_farmer_base(w);
        let pass_idx = meeple_pass_index(w);

        let cur = g.state.current_player;
        let meeples_in_hand = g.state.meeples[cur] as i64;
        // `_tiles_remaining` = `len(state.deck)`, i.e. the UNSEEN deck (the
        // already-drawn `next_tile` is not part of it).
        let tiles_left = g.state.deck_len() as i64;

        let mut candidates: Vec<i32> = legal.clone();

        // Rule 3: `tiles_left > 0.6 * board.total_tiles`.  Python evaluates the
        // right-hand side as an IEEE double and compares int-to-float; do the
        // same, do not rationalize it to integer arithmetic.
        let early_phase = (tiles_left as f64) > 0.6 * (g.total_tiles as f64);
        if early_phase {
            let non_farmer: Vec<i32> = candidates
                .iter()
                .copied()
                .filter(|&a| !(farmer_base <= a && a < pass_idx))
                .collect();
            if !non_farmer.is_empty() {
                candidates = non_farmer;
            }
        }

        // Rule 2: `tiles_left <= meeples_in_hand` ⇒ never pass.
        let force_place = tiles_left <= meeples_in_hand;
        if force_place {
            let non_pass: Vec<i32> = candidates.iter().copied().filter(|&a| a != pass_idx).collect();
            if !non_pass.is_empty() {
                candidates = non_pass;
            }
        }

        if candidates.is_empty() {
            candidates = legal.clone();
        }

        self.best_by_virtual_score(g, legal, candidates)
    }

    /// `_best_by_virtual_score` — int64 argmax over the 1-ply terminal leaf,
    /// uniform tie-break over the ties' positions IN the candidate list
    /// (ascending).  `legal` rides through only so the probe can report it.
    fn best_by_virtual_score(
        &mut self,
        g: &Game,
        legal: Vec<i32>,
        candidates: Vec<i32>,
    ) -> Result<Decision, String> {
        let player = g.state.current_player;
        // NO RNG DRAW on the single-candidate path.
        if candidates.len() == 1 {
            let a = candidates[0];
            return Ok(Decision {
                action: a,
                legal,
                candidates,
                scores: Vec::new(),
                player,
            });
        }
        // `player` is captured BEFORE any action is applied: the score is always
        // read from the perspective of whoever is to move at the ROOT of this
        // decision, not of whoever is to move in the scratch afterstate.
        let opp = 1 - player;
        let last_tile_coord = g.state.last_tile_action.map(|lta| lta.coord);

        // The route is read ONCE per decision, not per candidate: it cannot
        // change inside a decision, and production never sets it at all.
        let force_legacy = FORCE_LEGACY.with(|c| c.get());
        let mut scores: Vec<i64> = Vec::with_capacity(candidates.len());
        SCORER_BUFS.with(|cell| -> Result<(), String> {
            let bufs = &mut *cell.borrow_mut();
            for &action_idx in &candidates {
                let action = decode(
                    action_idx,
                    &g.offset,
                    g.state.phase,
                    g.state.next_tile,
                    last_tile_coord,
                )
                .map_err(|e| format!("decode({action_idx}) failed: {e:?}"))?;
                // `copy.deepcopy(board.state)` + `StateUpdater.apply_action_inplace`
                // + `virtual_score_inplace`.  Note this is the raw GameState apply,
                // NOT `Game::advance`: the Python scores the scratch STATE and never
                // touches the window offset.
                let mut scratch = g.state.clone();
                scratch.apply_action(action);
                // The leaf itself: flat route + thread-local buffers, with the
                // legacy engine route preserved at the wrapping border (see the
                // scorer section at the top of this module).
                scores.push(if force_legacy {
                    scratch.count_final_scores();
                    scratch.scores[player] - scratch.scores[opp]
                } else {
                    candidate_leaf(&mut scratch, player, bufs)
                });
            }
            Ok(())
        })?;

        let best = *scores.iter().max().expect("len(candidates) >= 2 here");
        // `np.flatnonzero(scores == best)` — indices INTO the candidate list,
        // ascending.
        let best_local: Vec<usize> = scores
            .iter()
            .enumerate()
            .filter(|&(_, &s)| s == best)
            .map(|(i, _)| i)
            .collect();
        // `self._rng.choice(best_local.tolist())` — ALWAYS draws, including the
        // `len == 1` case (`_randbelow(1)` consumes `getrandbits(1)` in a
        // rejection loop until it draws 0).
        let choice = self.rng.randbelow(best_local.len() as u64) as usize;
        let action = candidates[best_local[choice]];
        Ok(Decision {
            action,
            legal,
            candidates,
            scores,
            player,
        })
    }
}

/// One `choose_action` decision, with the intermediates a divergence probe needs.
#[derive(Clone, Debug)]
pub struct Decision {
    pub action: i32,
    /// `np.flatnonzero(valid_mask)`, ascending.
    pub legal: Vec<i32>,
    /// The set that actually reached the argmax (post Rule 3 / Rule 2 in the
    /// meeple phase; `== legal` in the tile phase).  Empty on the Rule-1 path.
    pub candidates: Vec<i32>,
    /// The int64 leaf score per candidate.  Empty on either no-draw early return.
    pub scores: Vec<i64>,
    pub player: usize,
}

/// `Game.get_valid_moves` — the memo, then the mask, with the Python's
/// all-overflow refusal.
///
/// The Python raises `WindowOverflowError` when EVERY legal action falls outside
/// the centred window (`n_total > 0 and n_overflow == n_total`); a partial
/// overflow is silently dropped in production (`CARCASSONNE_WINDOW_STRICT`
/// defaults off).  The raise happens inside `_compute_mask`, i.e. BEFORE the
/// memo is written, so a refused position leaves no cache entry.  Mirrored
/// exactly so a divergence can never be silent.
fn legal_actions_checked(
    g: &Game,
    cache: Option<&mut LegalMaskCache>,
) -> Result<Vec<i32>, String> {
    match cache {
        None => compute_legal_actions(g),
        Some(c) => {
            let key = string_representation(&g.state);
            if let Some(hit) = c.map.get(&key) {
                c.hits += 1;
                return Ok(hit.clone());
            }
            c.misses += 1;
            let fresh = compute_legal_actions(g)?;
            c.map.insert(key, fresh.clone());
            Ok(fresh)
        }
    }
}

/// `Game._compute_mask`, as an ascending action-index list.
fn compute_legal_actions(g: &Game) -> Result<Vec<i32>, String> {
    let m = g.legal_mask();
    if m.n_total > 0 && m.n_overflow == m.n_total {
        return Err(format!(
            "All {} legal actions fall outside the {}x{} window centered at ({}, {})",
            m.n_total, g.offset.size, g.offset.size, g.offset.origin_row, g.offset.origin_col
        ));
    }
    Ok(m.mask
        .iter()
        .enumerate()
        .filter(|(_, &v)| v != 0)
        .map(|(i, _)| i as i32)
        .collect())
}

/// `_playout_value` — apply `pick` to a copy of the determinized world, then
/// play to terminal with ONE [`RuleBasedPlayer`] driving both seats.
///
/// Returns `(margin, n_plies)` where `margin = scores[root_player] -
/// scores[1 - root_player]` at the terminal, and `n_plies` counts the moves
/// AFTER the pick (the pick itself is not a ply).  The engine fires
/// `count_final_scores` on the terminal transition, so the scores are final.
///
/// `cache` is the record-scoped [`LegalMaskCache`]; pass the SAME one to every
/// playout of a record, in the Python's order, or the collisions land elsewhere.
pub fn tier1_playout(
    world: &Game,
    pick: i32,
    root_player: usize,
    playout_seed: i64,
    max_plies: usize,
    mut cache: Option<&mut LegalMaskCache>,
) -> Result<(f64, usize), String> {
    if root_player > 1 {
        return Err(format!("root_player must be 0 or 1, got {root_player}"));
    }
    let mut g = world.clone();
    g.advance(pick)?;
    let mut agent = RuleBasedPlayer::new(playout_seed);
    let mut plies = 0usize;
    while !g.is_terminal() {
        if plies >= max_plies {
            return Err(format!("playout exceeded max_plies={max_plies}"));
        }
        let a = agent.choose_action(&g, cache.as_deref_mut())?;
        g.advance(a)?;
        plies += 1;
    }
    let opp = 1 - root_player;
    Ok((
        (g.state.scores[root_player] - g.state.scores[opp]) as f64,
        plies,
    ))
}

/// A single playout's full decision trace — the divergence-localisation tool.
pub struct PlayoutTrace {
    pub actions: Vec<i32>,
    pub margin: f64,
    pub plies: usize,
    /// The full [`Decision`] at `probe_ply`, if it was reached.
    pub probe: Option<Decision>,
}

/// [`tier1_playout`], recording the action played at every ply and (optionally)
/// the full [`Decision`] at one chosen ply.  Behaviourally identical to
/// `tier1_playout` — same RNG stream, same moves — it just keeps the receipts.
pub fn tier1_playout_trace(
    world: &Game,
    pick: i32,
    root_player: usize,
    playout_seed: i64,
    max_plies: usize,
    probe_ply: i64,
    mut cache: Option<&mut LegalMaskCache>,
) -> Result<PlayoutTrace, String> {
    if root_player > 1 {
        return Err(format!("root_player must be 0 or 1, got {root_player}"));
    }
    let mut g = world.clone();
    g.advance(pick)?;
    let mut agent = RuleBasedPlayer::new(playout_seed);
    let mut actions: Vec<i32> = Vec::new();
    let mut probe = None;
    let mut plies = 0usize;
    while !g.is_terminal() {
        if plies >= max_plies {
            return Err(format!("playout exceeded max_plies={max_plies}"));
        }
        let d = agent.decide(&g, cache.as_deref_mut())?;
        if probe_ply >= 0 && plies == probe_ply as usize {
            probe = Some(d.clone());
        }
        actions.push(d.action);
        g.advance(d.action)?;
        plies += 1;
    }
    let opp = 1 - root_player;
    Ok(PlayoutTrace {
        actions,
        margin: (g.state.scores[root_player] - g.state.scores[opp]) as f64,
        plies,
        probe,
    })
}

/// Replay the root of a leg: `Game(deck_seed)` advanced by `prefix_actions`.
pub fn tier1_root(deck_seed_decimal: &str, prefix_actions: &[i32]) -> Result<Game, String> {
    let mut root = Game::from_deck(deck_from_seed(deck_seed_decimal));
    for (i, &a) in prefix_actions.iter().enumerate() {
        root.advance(a)
            .map_err(|e| format!("root replay failed at prefix index {i} (action {a}): {e}"))?;
    }
    Ok(root)
}

/// Replay a world for a leg: the root plus ONE determinization.  Exposed so a
/// probe can seat the Python side on the byte-identical world.
pub fn tier1_world(
    deck_seed_decimal: &str,
    prefix_actions: &[i32],
    world_seed: i64,
) -> Result<Game, String> {
    let root = tier1_root(deck_seed_decimal, prefix_actions)?;
    let mut rng = MT19937::from_py_int_seed_i64(world_seed);
    reshuffled_determinization(&root, &mut rng)
}

/// The values from ONE position-record: both picks over `m` CRN-shared worlds.
pub struct LegValues {
    pub values_a: Vec<f64>,
    pub values_b: Vec<f64>,
    pub plies_a: Vec<usize>,
    pub plies_b: Vec<usize>,
    /// `(hits, misses, entries)` of the record-scoped legal-mask memo; all zero
    /// when `legal_mask_cache` was `false`.
    pub cache_stats: (u64, u64, usize),
}

/// The WHOLE leg in one call — `_process` for `--oracle-policy tier1-greedy`.
///
/// Root replay is `RR.replay_actions(deck_seed, actions, ply)` under the walled
/// rules profile, whose `game_kwargs()` is `{}` by construction ⇒ the default
/// [`crate::game::GameConfig`].  Per world `j`: ONE determinization from
/// `random.Random(world_seeds[j])`, SHARED by both picks (the CRN); then a
/// playout per pick, each with a FRESH `RuleBasedPlayer(playout_seeds[j])` —
/// same seed, stream restarted.
///
/// `legal_mask_cache` reproduces `Game._legal_cache` — ONE memo per record,
/// first written by the root legality check and then by every ply of every
/// playout, in `j = 0..m` order with arm `a` before arm `b`.  **The order is
/// part of the contract**: the memo's collisions (module docs) depend on which
/// board asked first.  `true` is the banked judge; `false` is the honest mask.
#[allow(clippy::too_many_arguments)]
pub fn tier1_leg(
    deck_seed_decimal: &str,
    prefix_actions: &[i32],
    pick_a: i32,
    pick_b: i32,
    root_player: usize,
    world_seeds: &[i64],
    playout_seeds: &[i64],
    max_plies: usize,
    legal_mask_cache: bool,
) -> Result<LegValues, String> {
    if world_seeds.len() != playout_seeds.len() {
        return Err(format!(
            "world_seeds ({}) and playout_seeds ({}) must have the same length",
            world_seeds.len(),
            playout_seeds.len()
        ));
    }
    let root = tier1_root(deck_seed_decimal, prefix_actions)?;
    let mut cache = if legal_mask_cache {
        Some(LegalMaskCache::new())
    } else {
        None
    };

    // `_process` asks for the root mask ONCE, to assert both picks are legal,
    // BEFORE any world is drawn.  That query is the memo's first entry, so it
    // has to happen here and in this order.
    let legal = legal_actions_checked(&root, cache.as_mut())?;
    for (tag, pick) in [("pick_a", pick_a), ("pick_b", pick_b)] {
        if !legal.contains(&pick) {
            return Err(format!("{tag}_illegal_at_root ({pick})"));
        }
    }

    let m = world_seeds.len();
    let mut out = LegValues {
        values_a: Vec::with_capacity(m),
        values_b: Vec::with_capacity(m),
        plies_a: Vec::with_capacity(m),
        plies_b: Vec::with_capacity(m),
        cache_stats: (0, 0, 0),
    };
    for j in 0..m {
        let mut rng = MT19937::from_py_int_seed_i64(world_seeds[j]);
        let wb = reshuffled_determinization(&root, &mut rng)?;
        let (ma, pa) = tier1_playout(
            &wb,
            pick_a,
            root_player,
            playout_seeds[j],
            max_plies,
            cache.as_mut(),
        )?;
        let (mb, pb) = tier1_playout(
            &wb,
            pick_b,
            root_player,
            playout_seeds[j],
            max_plies,
            cache.as_mut(),
        )?;
        out.values_a.push(ma);
        out.values_b.push(mb);
        out.plies_a.push(pa);
        out.plies_b.push(pb);
    }
    if let Some(c) = cache {
        out.cache_stats = (c.hits, c.misses, c.len());
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::MeepleType;
    use crate::game::{DrawRule, GameConfig, StartRule};
    use crate::tiles::{self, TerrainType};

    /// `random.Random(s); r._randbelow(1)` returns 0 but CONSUMES draws — the
    /// stream must be advanced exactly as CPython advances it.
    #[test]
    fn randbelow_one_is_not_a_free_call() {
        let mut a = MT19937::from_py_int_seed_i64(5);
        let mut b = MT19937::from_py_int_seed_i64(5);
        assert_eq!(a.randbelow(1), 0);
        // `getrandbits(1)` loops until it yields 0, so at least one 32-bit word
        // is always consumed; a fresh generator must therefore disagree.
        assert_ne!(
            a.getrandbits(32),
            b.getrandbits(32),
            "randbelow(1) consumed no entropy — the rejection loop is missing"
        );
    }

    #[test]
    fn randbelow_zero_is_a_free_call() {
        let mut a = MT19937::from_py_int_seed_i64(5);
        let mut b = MT19937::from_py_int_seed_i64(5);
        assert_eq!(a.randbelow(0), 0);
        assert_eq!(a.getrandbits(32), b.getrandbits(32));
    }

    /// A playout from the opening reaches a scored terminal and the margin is
    /// an exact integer (the terminal leaf is integral by construction).
    #[test]
    fn playout_reaches_a_scored_terminal() {
        let root = Game::from_seed("28100000001");
        let legal = root.legal_actions();
        assert_eq!(legal.len(), 1, "the empty board offers one placement");
        let (margin, plies) = tier1_playout(&root, legal[0], 0, 12345, 400, None).unwrap();
        assert!(plies > 50, "a full game is longer than 50 plies, got {plies}");
        assert_eq!(margin, margin.trunc(), "the terminal margin is integral");
    }

    /// The forced-move path must not draw.
    #[test]
    fn forced_move_consumes_no_draw() {
        let root = Game::from_seed("77");
        let mut p = RuleBasedPlayer::new(9);
        let legal = root.legal_actions();
        assert_eq!(legal.len(), 1);
        let before = p.rng.clone();
        let a = p.choose_action(&root, None).unwrap();
        assert_eq!(a, legal[0]);
        let mut after = p.rng.clone();
        let mut b = before;
        assert_eq!(after.getrandbits(32), b.getrandbits(32));
    }

    #[test]
    fn meeple_action_layout_matches_python() {
        assert_eq!(meeple_farmer_base(25), 2506);
        assert_eq!(meeple_pass_index(25), 2510);
    }

    fn seeded_root(seed: &str, n: usize) -> (Game, Vec<i32>) {
        let mut root = Game::from_seed(seed);
        let mut prefix = Vec::new();
        for _ in 0..n {
            let l = root.legal_actions();
            root.advance(l[0]).unwrap();
            prefix.push(l[0]);
        }
        (root, prefix)
    }

    /// The two picks share ONE determinized world (the CRN), and each arm gets a
    /// FRESH player seeded identically — so a leg whose two picks are the SAME
    /// action must return bit-identical values on both arms.  Holds with the
    /// memo on and off (with it on, arm `b` is a pure cache replay of arm `a`).
    #[test]
    fn leg_crn_shares_the_world_and_restarts_the_stream() {
        let (root, prefix) = seeded_root("28100000001", 12);
        let legal = root.legal_actions();
        let ws: Vec<i64> = vec![101, 202, 303];
        let ps: Vec<i64> = vec![11, 22, 33];
        for cache in [false, true] {
            let out = tier1_leg(
                "28100000001", &prefix, legal[0], legal[0], 0, &ws, &ps, 400, cache,
            )
            .unwrap();
            assert_eq!(out.values_a.len(), 3);
            assert_eq!(out.values_a, out.values_b, "cache={cache}");
            assert_eq!(out.plies_a, out.plies_b, "cache={cache}");
        }
    }

    /// An illegal pick at the root is refused, mirroring `_process`'s
    /// `pick_*_illegal_at_root` guard rather than silently scoring garbage.
    #[test]
    fn an_illegal_pick_is_refused() {
        assert!(tier1_leg("77", &[], 0, 0, 0, &[1], &[1], 400, true).is_err());
        assert!(tier1_leg("77", &[], 0, 0, 0, &[1], &[1], 400, false).is_err());
    }

    /// The memo must actually be exercised — a leg with `m > 1` replays a lot of
    /// board states, so hits must dominate — and it must be scoped to the leg.
    #[test]
    fn the_memo_is_populated_and_record_scoped() {
        let (root, prefix) = seeded_root("28100000001", 12);
        let legal = root.legal_actions();
        let ws: Vec<i64> = vec![101, 101, 101];
        let ps: Vec<i64> = vec![11, 11, 11];
        let out = tier1_leg(
            "28100000001", &prefix, legal[0], legal[0], 0, &ws, &ps, 400, true,
        )
        .unwrap();
        let (hits, misses, entries) = out.cache_stats;
        assert!(misses > 0, "the memo must take at least the root miss");
        assert!(
            hits > misses,
            "identical worlds replay the same boards: hits {hits} misses {misses}"
        );
        assert_eq!(entries as u64, misses, "one entry per miss");

        let off = tier1_leg(
            "28100000001", &prefix, legal[0], legal[0], 0, &ws, &ps, 400, false,
        )
        .unwrap();
        assert_eq!(off.cache_stats, (0, 0, 0), "no memo when it is switched off");
    }

    // -----------------------------------------------------------------------
    // The scorer swap (2026-08-28): flat route == legacy engine route
    // -----------------------------------------------------------------------

    /// Score every candidate of a decision by BOTH routes; returns the values
    /// and bumps the coverage counters.
    #[allow(clippy::type_complexity)]
    fn score_both_routes(g: &Game, legal: &[i32], cov: &mut Coverage) -> Vec<i64> {
        let player = g.state.current_player;
        let last_tile_coord = g.state.last_tile_action.map(|lta| lta.coord);
        let mut vals = Vec::with_capacity(legal.len());
        for &a in legal {
            let action = decode(
                a,
                &g.offset,
                g.state.phase,
                g.state.next_tile,
                last_tile_coord,
            )
            .expect("a legal action decodes");
            let mut after = g.state.clone();
            after.apply_action(action);

            let legacy = candidate_leaf_legacy(&after, player);
            let flat = candidate_leaf_flat(&after, player);
            assert_eq!(
                legacy, flat,
                "scorer routes diverge on action {a} (player {player})"
            );
            // The deployed entry point (thread-local buffers + border guard)
            // must agree with both.
            let deployed = SCORER_BUFS.with(|cell| {
                let bufs = &mut *cell.borrow_mut();
                let mut s = after.clone();
                candidate_leaf(&mut s, player, bufs)
            });
            assert_eq!(deployed, legacy, "the deployed scorer diverges on action {a}");

            cov.checked += 1;
            for p in 0..2 {
                for mp in &after.placed_meeples[p] {
                    let tid = after
                        .get_tile(mp.coord.row, mp.coord.col)
                        .expect("meeple on a placed tile");
                    match tiles::tile(tid).get_type(mp.side) {
                        Some(TerrainType::Chapel) | Some(TerrainType::Flowers) => {
                            cov.cloister += 1
                        }
                        Some(TerrainType::City) => cov.city += 1,
                        Some(TerrainType::Road) => cov.road += 1,
                        _ => {}
                    }
                    if mp.meeple_type == MeepleType::Farmer {
                        cov.farm += 1;
                    }
                }
            }
            vals.push(legacy);
        }
        let best = *vals.iter().max().expect("a decision has candidates");
        if vals.iter().filter(|&&v| v == best).count() > 1 {
            cov.ties += 1;
        }
        vals
    }

    #[derive(Default)]
    struct Coverage {
        checked: usize,
        farm: usize,
        cloister: usize,
        city: usize,
        road: usize,
        ties: usize,
        terminal_games: usize,
    }

    /// **The value gate.** Every candidate afterstate a real tier1 playout would
    /// score, scored by the legacy engine route AND by the flat route, on a
    /// corpus that is asserted to contain farms, cloisters, cities, roads,
    /// argmax ties and full (deck-exhausted) boards.
    #[test]
    fn the_two_scorer_routes_agree_on_every_candidate_of_a_played_corpus() {
        const SAMPLE_EVERY: usize = 6;
        let mut cov = Coverage::default();
        for seed in ["28100000001", "77", "140000001096", "5"] {
            let mut g = Game::from_seed(seed);
            let mut agent = RuleBasedPlayer::new(4242);
            let mut plies = 0usize;
            while !g.is_terminal() && plies < 400 {
                let legal = g.legal_actions();
                if legal.len() >= 2 && plies % SAMPLE_EVERY == 0 {
                    score_both_routes(&g, &legal, &mut cov);
                }
                let a = agent
                    .choose_action(&g, None)
                    .expect("tier1 always has a legal action");
                g.advance(a).expect("tier1 only picks legal actions");
                plies += 1;
            }
            // The terminal position itself — the full-board case.
            if g.is_terminal() {
                cov.terminal_games += 1;
                assert_eq!(
                    candidate_leaf_legacy(&g.state, 0),
                    candidate_leaf_flat(&g.state, 0),
                    "routes diverge on the TERMINAL position of seed {seed}"
                );
            }
        }
        println!(
            "\n=== tier1 scorer routes: {} candidate values, 0 divergences ===\n               coverage: farm {} cloister {} city {} road {} ties {} terminals {}",
            cov.checked, cov.farm, cov.cloister, cov.city, cov.road, cov.ties, cov.terminal_games
        );
        assert!(cov.checked > 2_000, "thin corpus: {} values", cov.checked);
        assert!(cov.farm > 0, "no farmer reached — farm scoring untested");
        assert!(cov.cloister > 0, "no cloister reached");
        assert!(cov.city > 0 && cov.road > 0, "no city/road reached");
        assert!(cov.ties > 0, "no argmax tie reached — the tie set is untested");
        assert_eq!(cov.terminal_games, 4, "every seeded game must reach terminal");
    }

    /// **The trajectory gate (small, always-on).** Whole playouts under the
    /// legacy scorer and under the deployed one must agree in `(margin, plies)`
    /// — which transitively covers the argmax tie set and every downstream
    /// `randbelow` draw.  The 200-playout version is
    /// [`the_scorer_swap_is_trajectory_identical_at_scale`].
    #[test]
    fn the_scorer_swap_is_trajectory_identical() {
        for i in 0..12i64 {
            let seed = (28_100_000_001i64 + i * 7).to_string();
            let root = Game::from_seed(&seed);
            let legal = root.legal_actions();
            let pick = legal[legal.len() / 2];
            let want = with_legacy_scorer(|| tier1_playout(&root, pick, 0, 900 + i, 400, None))
                .expect("legacy playout");
            let got = tier1_playout(&root, pick, 0, 900 + i, 400, None).expect("flat playout");
            assert_eq!(want, got, "playout {i} (seed {seed}) diverged after the swap");
        }
    }

    /// The 200+-playout identity pass over varied roots, both cache shapes.
    /// `#[ignore]`d only because it is minutes-scale beside a live eval; it is
    /// the gate the branch is graded on.
    ///
    /// `cargo test -p carc-core --release -- --ignored --nocapture \
    ///     the_scorer_swap_is_trajectory_identical_at_scale`
    #[test]
    #[ignore = "identity pass at scale: run deliberately (see GATES_DEFERRED.md)"]
    fn the_scorer_swap_is_trajectory_identical_at_scale() {
        reset_border_fallbacks();
        let mut n = 0usize;
        for s in 0..20i64 {
            let seed = (28_100_000_001i64 + s * 977).to_string();
            for &root_ply in &[0usize, 12, 30, 54, 78] {
                let mut root = Game::from_seed(&seed);
                let mut prefix: Vec<i32> = Vec::new();
                let mut ok = true;
                for _ in 0..root_ply {
                    if root.is_terminal() {
                        ok = false;
                        break;
                    }
                    let l = root.legal_actions();
                    let a = l[l.len() / 2];
                    root.advance(a).expect("legal");
                    prefix.push(a);
                }
                if !ok || root.is_terminal() {
                    continue;
                }
                let legal = root.legal_actions();
                for &pick in [legal[0], legal[legal.len() / 2], legal[legal.len() - 1]]
                    .iter()
                    .take(if legal.len() >= 3 { 3 } else { 1 })
                {
                    let ps = 4_000 + s * 31 + root_ply as i64;
                    let want =
                        with_legacy_scorer(|| tier1_playout(&root, pick, 0, ps, 400, None)).unwrap();
                    let got = tier1_playout(&root, pick, 0, ps, 400, None).unwrap();
                    assert_eq!(want, got, "seed {seed} root_ply {root_ply} pick {pick}");
                    n += 1;
                }
            }
        }
        println!("\n=== tier1 scorer swap: {n} playouts, (margin, plies) identical ===");
        println!("  border fallbacks fired: {}", border_fallbacks());
        assert!(n >= 200, "wanted >= 200 playouts, ran {n}");
        assert_eq!(
            border_fallbacks(),
            0,
            "the border class fired — the fallback preserved behaviour, but the \
             unreachability note in the module docs is now false and must be updated"
        );
    }

    /// The border predicate is the SUPERSET of the divergence set, and it routes
    /// to the legacy scorer.
    ///
    /// The mechanism it guards is pinned directly: `board_direct(-1, c)` wraps to
    /// row 34 (CPython semantics, the engine route) while `get_tile(-1, c)`
    /// answers "no tile" (the flat route).  Those two answers differ exactly when
    /// row 34 is occupied — which is what the predicate tests.
    #[test]
    fn the_border_hazard_predicate_routes_to_the_legacy_scorer() {
        // A normal game never touches the last row/col, so the predicate is
        // false throughout and the fast route is always taken.
        let mut g = Game::from_seed("28100000001");
        let mut agent = RuleBasedPlayer::new(7);
        let mut plies = 0;
        while !g.is_terminal() && plies < 400 {
            assert!(
                !border_wrap_hazard(&g.state),
                "unexpected border contact at ply {plies}"
            );
            let a = agent.choose_action(&g, None).unwrap();
            g.advance(a).unwrap();
            plies += 1;
        }

        // A board whose (pre-placed) start tile sits on the LAST ROW / LAST
        // COLUMN: the predicate fires and the value is the legacy value.
        let at = |row: i32, col: i32| -> GameState {
            Game::from_seed_with_config(
                "28100000001",
                GameConfig {
                    window_size: 25,
                    start_rule: StartRule::Retail,
                    start_row: row,
                    start_col: col,
                    cloister_scan_fix: false,
                    draw_rule: DrawRule::Engine,
                },
            )
            .expect("a retail start anywhere in-bounds is constructible")
            .state
        };
        let border = at(BOARD_ROWS - 1, 15);
        assert_eq!(border.placed_coords.len(), 1, "the start tile is placed");
        assert!(border_wrap_hazard(&border), "row 34 must trip the predicate");
        assert!(
            border_wrap_hazard(&at(15, BOARD_COLS - 1)),
            "col 34 must trip the predicate"
        );

        reset_border_fallbacks();
        let before = border_fallbacks();
        let deployed = SCORER_BUFS.with(|cell| {
            let bufs = &mut *cell.borrow_mut();
            let mut s = border.clone();
            candidate_leaf(&mut s, 0, bufs)
        });
        assert_eq!(
            border_fallbacks() - before,
            1,
            "the border candidate must take the legacy fallback"
        );
        assert_eq!(
            deployed,
            candidate_leaf_legacy(&border, 0),
            "the fallback must return the LEGACY value, byte for byte"
        );

        // The accessor asymmetry itself, pinned so this test fails if either
        // route's board access is ever changed underneath the guard.
        assert!(
            border.board_direct(-1, 15).is_some(),
            "board_direct(-1, ..) must wrap to the occupied row 34 (CPython semantics)"
        );
        assert!(
            border.get_tile(-1, 15).is_none(),
            "get_tile(-1, ..) must answer 'no tile' (honest bounds)"
        );
    }

    /// `with_legacy_scorer` is scoped to its closure and to this thread.
    #[test]
    fn the_legacy_override_is_scoped() {
        assert!(!FORCE_LEGACY.with(|c| c.get()));
        with_legacy_scorer(|| assert!(FORCE_LEGACY.with(|c| c.get())));
        assert!(!FORCE_LEGACY.with(|c| c.get()));
    }

    /// W1 sequential timing of the two routes on the same playouts — the
    /// realized in-situ factor at the real call site.
    ///
    /// `cargo test -p carc-core --release -- --ignored --nocapture tier1_scorer_bench`
    #[test]
    #[ignore = "timing bench: exclusive tenant only"]
    fn tier1_scorer_bench() {
        use std::time::Instant;
        let mut roots: Vec<(Game, i32, i64)> = Vec::new();
        for s in 0..6i64 {
            let seed = (28_100_000_001i64 + s * 977).to_string();
            for &root_ply in &[6usize, 30, 60] {
                let mut root = Game::from_seed(&seed);
                for _ in 0..root_ply {
                    let l = root.legal_actions();
                    let a = l[l.len() / 2];
                    root.advance(a).unwrap();
                }
                let legal = root.legal_actions();
                roots.push((root, legal[legal.len() / 2], 5_000 + s * 13 + root_ply as i64));
            }
        }
        // Warm up both routes so neither pays first-touch.
        for (r, p, ps) in roots.iter().take(2) {
            let _ = tier1_playout(r, *p, 0, *ps, 400, None).unwrap();
            let _ = with_legacy_scorer(|| tier1_playout(r, *p, 0, *ps, 400, None)).unwrap();
        }

        let t0 = Instant::now();
        for (r, p, ps) in &roots {
            let _ = with_legacy_scorer(|| tier1_playout(r, *p, 0, *ps, 400, None)).unwrap();
        }
        let legacy = t0.elapsed().as_secs_f64() / roots.len() as f64;

        let t1 = Instant::now();
        for (r, p, ps) in &roots {
            let _ = tier1_playout(r, *p, 0, *ps, 400, None).unwrap();
        }
        let flat = t1.elapsed().as_secs_f64() / roots.len() as f64;

        println!("\n=== tier1 playout scorer, W1, n={} playouts/route ===", roots.len());
        println!("  legacy (count_final_scores) : {:.3} ms/playout", legacy * 1e3);
        println!("  flat   (decompose_into)     : {:.3} ms/playout", flat * 1e3);
        println!("  factor                      : {:.2}x", legacy / flat);
    }

    /// The memo's KEY is the byte-exact Python `string_representation`, so two
    /// states that share a key share a mask.  This pins the key source: a memo
    /// keyed on anything else would not reproduce the banked judge.
    #[test]
    fn the_memo_key_is_the_python_repr() {
        let (root, _) = seeded_root("28100000001", 12);
        let mut c = LegalMaskCache::new();
        let first = legal_actions_checked(&root, Some(&mut c)).unwrap();
        assert_eq!((c.hits, c.misses), (0, 1));
        let again = legal_actions_checked(&root, Some(&mut c)).unwrap();
        assert_eq!((c.hits, c.misses), (1, 1));
        assert_eq!(first, again);
        assert!(c.map.contains_key(&string_representation(&root.state)));
    }
}
