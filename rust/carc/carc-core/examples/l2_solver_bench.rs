//! **L2 — directional bench: solver µs/solve, PRE vs POST the terminal-scorer swap.**
//!
//! Same positions, same process, ARMS INTERLEAVED per position (so a drifting
//! box clock or a neighbouring tenant hits both arms alike), at each of
//! `K ∈ {2, 3, 4}`:
//!
//!   * **PRE**  — `with_legacy_terminal_scorer`: scored `Game::advance`
//!     (in-place `count_final_scores`) + `GameState::flat_base_score`.
//!   * **POST** — `advance_unscored` + `decompose_into` + `leaf::flat_base_score`.
//!
//! Node counts are bit-identical between the arms (the randomized gate proves
//! it on 520 positions), so this is a pure cost contrast over identical work —
//! including at K=4, where both arms blow the production 2M-node budget at the
//! same node and abort identically.
//!
//! ⚠️ **Contention disclosure**: the harness prints the 1-minute loadavg at
//! start and end. A directional factor measured under load is still a valid
//! *ratio* (both arms are interleaved) but the absolute µs/solve is not a clean
//! number. The p99-tail claim (top 10% of side-games = 59.7% of solver seconds)
//! gets its real verification at a deployment bench, NOT here.
//!
//! Run (release, niced, exclusive tenant preferred):
//! ```text
//! nice -n 19 cargo run --release --example l2_solver_bench \
//!     --manifest-path rust/carc/Cargo.toml -- <N_PER_K> <OUT.json>
//! ```

use std::time::Instant;

use carc_core::engine::Phase;
use carc_core::fair::solver::{
    solve_marginalized, with_legacy_terminal_scorer, SolverConfig,
};
use carc_core::game::Game;
use carc_core::tier1::RuleBasedPlayer;

fn loadavg() -> f64 {
    std::fs::read_to_string("/proc/loadavg")
        .ok()
        .and_then(|s| s.split_whitespace().next().and_then(|v| v.parse().ok()))
        .unwrap_or(f64::NAN)
}

/// First TILES decision at `k_remaining <= k` of a seeded tier-1 self-play game.
fn sample(seed_dec: &str, play_seed: i64, k: usize) -> Option<Game> {
    let mut g = Game::from_seed(seed_dec);
    let mut p = RuleBasedPlayer::new(play_seed);
    let mut guard = 0usize;
    while !g.is_terminal() && guard < 400 {
        guard += 1;
        let kr = g.state.deck_len() + usize::from(g.state.next_tile.is_some());
        if kr <= k && g.state.phase == Phase::Tiles {
            return Some(g);
        }
        let a = p.choose_action(&g, None).ok()?;
        g.advance(a).ok()?;
    }
    None
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n_per_k: usize = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(24);
    let out_path = args.get(2).cloned();

    // Production budget — a K=4 latch really does blow it and fall back to PIMC.
    let cfg = SolverConfig::default();
    let load_start = loadavg();
    println!("loadavg at start: {load_start:.2}   (production budget {})", cfg.budget);

    let mut rows: Vec<(usize, usize, f64, f64, u64, usize)> = Vec::new();
    for k in [2usize, 3, 4] {
        // K=3 is ~10 s/solve and K=4 blows the budget; scale N down with depth.
        let n = match k {
            2 => n_per_k,
            3 => (n_per_k / 4).max(3),
            _ => (n_per_k / 8).max(2),
        };
        let mut games: Vec<Game> = Vec::new();
        let mut i = 0u64;
        while games.len() < n && i < 4_000 {
            let seed = format!("{}", 8_700_000_000u64 + i * 104_729);
            if let Some(g) = sample(&seed, 770_000 + i as i64, k) {
                games.push(g);
            }
            i += 1;
        }
        if games.is_empty() {
            continue;
        }

        let (mut pre_s, mut post_s) = (0.0f64, 0.0f64);
        let mut nodes = 0u64;
        let mut node_mismatch = 0usize;
        for g in &games {
            // interleaved, PRE first then POST, one position at a time
            let t = Instant::now();
            let a = with_legacy_terminal_scorer(|| solve_marginalized(g, &cfg));
            pre_s += t.elapsed().as_secs_f64();
            let t = Instant::now();
            let b = solve_marginalized(g, &cfg);
            post_s += t.elapsed().as_secs_f64();
            match (a, b) {
                (Ok(x), Ok(y)) => {
                    nodes += x.nodes;
                    if x.nodes != y.nodes || x.value.to_bits() != y.value.to_bits() {
                        node_mismatch += 1;
                    }
                }
                (Err(_), Err(_)) => {}
                _ => node_mismatch += 1,
            }
        }
        let n = games.len();
        println!(
            "K={k}  n={n}  nodes={nodes}   PRE {:>10.1} us/solve   POST {:>10.1} us/solve   \
             FACTOR {:.2}x   (identity mismatches: {node_mismatch})",
            pre_s / n as f64 * 1e6,
            post_s / n as f64 * 1e6,
            pre_s / post_s
        );
        rows.push((k, n, pre_s, post_s, nodes, node_mismatch));
    }
    let load_end = loadavg();
    println!("loadavg at end:   {load_end:.2}");

    if let Some(path) = out_path {
        let body = rows
            .iter()
            .map(|(k, n, pre, post, nodes, mm)| {
                format!(
                    "    {{\"k\": {k}, \"n\": {n}, \"pre_us_per_solve\": {:.1}, \
                     \"post_us_per_solve\": {:.1}, \"factor\": {:.4}, \"nodes\": {nodes}, \
                     \"identity_mismatches\": {mm}}}",
                    pre / *n as f64 * 1e6,
                    post / *n as f64 * 1e6,
                    pre / post
                )
            })
            .collect::<Vec<_>>()
            .join(",\n");
        let json = format!(
            "{{\n  \"bench\": \"L2/solver_terminal_scorer\",\n  \"budget\": {},\n  \
             \"loadavg_start\": {load_start:.2},\n  \"loadavg_end\": {load_end:.2},\n  \
             \"rows\": [\n{body}\n  ]\n}}\n",
            cfg.budget
        );
        std::fs::write(&path, json).expect("write bench json");
        eprintln!("wrote {path}");
    }
}
