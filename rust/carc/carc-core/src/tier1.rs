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

use std::collections::HashMap;

use crate::action_space::{decode, meeple_farmer_base, meeple_pass_index};
use crate::compat::mt19937::MT19937;
use crate::engine::Phase;
use crate::fair::reshuffled_determinization;
use crate::game::{deck_from_seed, Game};
use crate::repr_key::string_representation;

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

        let mut scores: Vec<i64> = Vec::with_capacity(candidates.len());
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
            scratch.count_final_scores();
            scores.push(scratch.scores[player] - scratch.scores[opp]);
        }

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
