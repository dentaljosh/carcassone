//! **Engine follow-ons A + B — the CROSS-BUILD action-identity gate.**
//!
//! Plays whole games and digests everything observable about them, so the same
//! binary source run against the PRE-CHANGE tree and against HEAD must emit the
//! identical sha256. It is the "two builds, one digest" companion to the
//! in-suite gates, which can only compare two paths inside ONE build.
//!
//! Two arms, both digested:
//!
//! * **arm `engine`** — random-policy self-play through `Game::advance`. Covers
//!   `possible_actions` / `possible_playing_positions` / `fits` (A: the flat
//!   play table + `fits_flat`), `possible_meeple_positions` /
//!   `possible_farmer_positions`, `apply_action`,
//!   `remove_meeples_and_collect_points` (find_cities / find_roads / find_farm /
//!   count_*_points) and `count_final_scores`.
//! * **arm `tier1`** — `RuleBasedPlayer` self-play, both memo shapes. Covers
//!   the same engine surface PLUS the per-candidate leaf and therefore
//!   **follow-on B**, the tier1 meeple-phase decomposition hoist, end to end.
//!
//! The digest absorbs, per game: every action index in order, every ply's legal
//! move count, every scored candidate's int64 leaf, the final scores, the ply
//! count, and the border-fallback counter. A change in ANY of them — including
//! a pure REORDERING of a legal-move list, which no score comparison would
//! catch — moves the digest.
//!
//! Run (release, niced):
//! ```text
//! nice -n 19 cargo run --release --example flat_play_gate \
//!     --manifest-path rust/carc/Cargo.toml
//! ```
//! `CARCASSONNE_FIX_R9=1` gates the R9 registry instead (process-global flag,
//! so it needs a second process). `FLAT_PLAY_GATE_N` overrides the game count
//! (default 250; the funded floor is 200).
//!
//! Emits JSON on stdout and a human readout on stderr. Exits 0 always — this
//! arm PRODUCES a digest; the comparison across builds is the caller's job (see
//! `scripts/engine_followons/flat_play_gate.sh`).

use carc_core::game::Game;
use carc_core::sha256::{sha256_hex, Sha256};
use carc_core::tier1::{border_fallbacks, LegalMaskCache, RuleBasedPlayer};
use carc_core::tiles;

struct Lcg(u64);
impl Lcg {
    fn new(seed: u64) -> Self {
        Lcg(seed
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407))
    }
    fn next(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.0 >> 33
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() as usize) % n.max(1)
    }
}

fn feed_i64(h: &mut Sha256, v: i64) {
    h.update(&v.to_le_bytes());
}

/// Arm `engine`: random policy, every legal-move list and every action digested.
fn arm_engine(n_games: usize, base_seed: u64) -> (String, usize, usize) {
    let mut h = Sha256::new();
    let mut plies = 0usize;
    let mut n_actions = 0usize;
    for i in 0..n_games {
        let seed = base_seed + i as u64;
        let mut g = Game::from_seed(&seed.to_string());
        let mut rng = Lcg::new(seed);
        feed_i64(&mut h, seed as i64);
        let mut guard = 0usize;
        while !g.state.is_terminated() {
            guard += 1;
            assert!(guard < 400, "game {seed} did not terminate");
            let legal = g.legal_actions();
            assert!(!legal.is_empty(), "no legal action at a non-terminal state");
            // The WHOLE list, in order — a reordering must move the digest.
            feed_i64(&mut h, legal.len() as i64);
            for &a in &legal {
                feed_i64(&mut h, a as i64);
            }
            feed_i64(&mut h, g.state.phase as i64);
            feed_i64(&mut h, g.state.current_player as i64);
            feed_i64(&mut h, g.state.scores[0]);
            feed_i64(&mut h, g.state.scores[1]);
            let a = legal[rng.below(legal.len())];
            feed_i64(&mut h, a as i64);
            g.advance(a).expect("advance");
            plies += 1;
            n_actions += legal.len();
        }
        feed_i64(&mut h, g.state.scores[0]);
        feed_i64(&mut h, g.state.scores[1]);
        feed_i64(&mut h, guard as i64);
    }
    (sha256_hex(&h.finalize()), plies, n_actions)
}

/// Arm `tier1`: `RuleBasedPlayer` self-play, both memo shapes, per-candidate
/// int64 leaves digested. This is the arm that grades follow-on B.
fn arm_tier1(n_games: usize, base_seed: u64) -> (String, usize, usize) {
    let mut h = Sha256::new();
    let mut plies = 0usize;
    let mut n_scored = 0usize;
    for i in 0..n_games {
        let seed = base_seed + i as u64;
        for cache_on in [false, true] {
            let mut g = Game::from_seed(&seed.to_string());
            let mut p = RuleBasedPlayer::new(seed as i64);
            let mut cache = if cache_on { Some(LegalMaskCache::new()) } else { None };
            feed_i64(&mut h, seed as i64);
            feed_i64(&mut h, cache_on as i64);
            let mut guard = 0usize;
            while !g.state.is_terminated() {
                guard += 1;
                assert!(guard < 400, "tier1 game {seed} did not terminate");
                let d = p.decide(&g, cache.as_mut()).expect("decide");
                feed_i64(&mut h, d.action as i64);
                feed_i64(&mut h, d.player as i64);
                feed_i64(&mut h, d.legal.len() as i64);
                feed_i64(&mut h, d.candidates.len() as i64);
                for &c in &d.candidates {
                    feed_i64(&mut h, c as i64);
                }
                // The per-candidate leaf: what the hoist actually touches.
                for &s in &d.scores {
                    feed_i64(&mut h, s);
                }
                n_scored += d.scores.len();
                g.advance(d.action).expect("advance");
                plies += 1;
            }
            feed_i64(&mut h, g.state.scores[0]);
            feed_i64(&mut h, g.state.scores[1]);
            feed_i64(&mut h, guard as i64);
            if let Some(c) = cache.as_ref() {
                feed_i64(&mut h, c.hits as i64);
                feed_i64(&mut h, c.misses as i64);
            }
        }
    }
    (sha256_hex(&h.finalize()), plies, n_scored)
}

fn main() {
    let n_games: usize = std::env::var("FLAT_PLAY_GATE_N")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(250);
    assert!(n_games >= 200, "the funded floor is N >= 200 games, got {n_games}");
    let r9 = tiles::r9_enabled();

    let fb_before = border_fallbacks();
    let t0 = std::time::Instant::now();
    let (d_engine, plies_e, acts_e) = arm_engine(n_games, 28_600_000_000);
    let (d_tier1, plies_t, scored_t) = arm_tier1(n_games, 28_600_100_000);
    let wall = t0.elapsed().as_secs_f64();
    let fb = border_fallbacks() - fb_before;

    let mut h = Sha256::new();
    h.update(d_engine.as_bytes());
    h.update(d_tier1.as_bytes());
    let combined = sha256_hex(&h.finalize());

    eprintln!("[flat-play-gate] r9={r9} n_games={n_games}");
    eprintln!("  arm engine : {plies_e} plies, {acts_e} legal entries -> {d_engine}");
    eprintln!("  arm tier1  : {plies_t} plies, {scored_t} scored candidates -> {d_tier1}");
    eprintln!("  border_fallbacks (expect 0): {fb}");
    eprintln!("  combined   : {combined}   [{wall:.1}s]");

    println!(
        "{{\n  \"gate\": \"flat-play-action-identity\",\n  \"r9\": {r9},\n  \
         \"n_games\": {n_games},\n  \"engine_plies\": {plies_e},\n  \
         \"engine_legal_entries\": {acts_e},\n  \"tier1_plies\": {plies_t},\n  \
         \"tier1_scored_candidates\": {scored_t},\n  \"border_fallbacks\": {fb},\n  \
         \"sha256_engine\": \"{d_engine}\",\n  \"sha256_tier1\": \"{d_tier1}\",\n  \
         \"sha256_combined\": \"{combined}\",\n  \"wall_secs\": {wall:.3}\n}}"
    );
}
