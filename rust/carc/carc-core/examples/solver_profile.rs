//! **L2 — exact-solver terminal-scorer profile / directional bench.**
//!
//! Drives seeded games down to a `k_remaining <= K` TILES decision and runs
//! `fair::solver::solve_marginalized` on each, reporting wall-clock per solve
//! and per node.  Built to be `perf record`-ed so the terminal-scoring share
//! (`count_final_scores` / `find_city` / `find_farm` / `GameState::clone`) is
//! attributable by symbol rather than guessed.
//!
//! Run (release, niced):
//! ```text
//! nice -n 19 cargo run --release --example solver_profile \
//!     --manifest-path rust/carc/Cargo.toml -- <K> <N>
//! ```

use std::time::Instant;

use carc_core::engine::Phase;
use carc_core::fair::solver::{solve_marginalized, SolverConfig};
use carc_core::game::Game;

/// Descend a seeded game to a `k_remaining <= k` TILES decision.
/// Mid-index action choice — the same deterministic descent the solver's own
/// unit tests use, so positions are reproducible without an RNG contract.
fn endgame(seed: &str, k: usize) -> Option<Game> {
    let mut g = Game::from_seed(seed);
    let mut guard = 0;
    loop {
        guard += 1;
        if guard > 400 {
            return None;
        }
        let kr = g.state.deck_len() + usize::from(g.state.next_tile.is_some());
        if kr <= k && g.state.phase == Phase::Tiles {
            return Some(g);
        }
        let legal = g.legal_actions();
        if legal.is_empty() {
            return None;
        }
        if g.advance(legal[legal.len() / 2]).is_err() {
            return None;
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let k: usize = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(3);
    let n: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(24);

    let cfg = SolverConfig::default();
    let mut positions = Vec::new();
    for i in 0..n {
        let seed = format!("{}", 4_000_000 + i as u64 * 7919);
        if let Some(g) = endgame(&seed, k) {
            positions.push(g);
        }
    }
    eprintln!("K={k}  positions={}", positions.len());

    let t0 = Instant::now();
    let mut nodes = 0u64;
    let mut solved = 0usize;
    let mut vsum = 0f64;
    for g in &positions {
        match solve_marginalized(g, &cfg) {
            Ok(r) => {
                nodes += r.nodes;
                vsum += r.value;
                solved += 1;
            }
            Err(e) => eprintln!("  skip: {e}"),
        }
    }
    let el = t0.elapsed().as_secs_f64();
    println!(
        "K={k}  solved={solved}  nodes={nodes}  wall={el:.3}s  \
         {:.1} us/solve  {:.3} us/node  checksum={vsum}",
        el / solved.max(1) as f64 * 1e6,
        el / nodes.max(1) as f64 * 1e6,
    );
}
