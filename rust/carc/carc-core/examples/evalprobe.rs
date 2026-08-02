//! Denominator probe for the rust-side neural-evaluator design
//! (`docs/RUST_NET_EVAL_DESIGN_20260802.md`).
//!
//!     cargo build --release --example evalprobe -p carc-core
//!     ./target/release/examples/evalprobe <seed-decimal> <ply,ply,...> <reps>
//!
//! The reopen condition of the CL-067 equal-wall-clock gate is
//! `r = forward_ms / search_ms_per_sim <= ~1.5`.  `perfprobe` already prints the
//! numerator-free half of that (seconds per `search_single`), but the design memo
//! needs three more quantities that no existing probe reports:
//!
//! 1. **`search_ms_per_sim`** itself — the denominator, at the champion's own
//!    per-determinization budget (`SearchConfig::default().simulations` = 1376).
//! 2. **leaf evals per simulation** — because the heuristic evaluator costs
//!    `1 + |legal|` leaf calls per EXPANSION, and a net-prior evaluator *replaces*
//!    that whole child sweep with one forward.  The port's economics cannot be read
//!    off the forward cost alone: the net arm deletes work as well as adding it.
//! 3. **isolated leaf cost** — the ~7 µs figure the design brief quotes, measured
//!    here rather than assumed, on the same box and build as everything else.
//! 4. **the child-sweep cost** — `clone + advance + leaf` per legal action, which is
//!    the work a net-prior evaluator DELETES. Without this the substitution
//!    argument is hand-waving; with it, the projected cost ratio has measured
//!    inputs.
//!
//! Positions are reached by replaying the first legal action, exactly as
//! `perfprobe` does: a cheap deterministic route to a board of a given ply.  This
//! is a COST probe, not a strength one.

use carc_core::game::Game;
use carc_core::leaf::{LeafConfig, LeafScratch};
use carc_core::search::{search_single, SearchConfig};
use std::time::Instant;

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let seed = a[0].clone();
    let plies: Vec<usize> = a[1].split(',').map(|s| s.parse().unwrap()).collect();
    let reps: usize = a[2].parse().unwrap();
    let cfg = SearchConfig::default();
    let leaf_cfg = LeafConfig::curve125();

    println!(
        "# sims/search={} leaf=curve125 (SearchConfig::default)",
        cfg.simulations
    );
    println!(
        "ply\tlegal\tsearch_ms\tms_per_sim\tleaf_evals\tleaf_per_sim\tleaf_us\tchild_us\tsweep_ms_per_sim\tsweep_frac\tnodes"
    );

    for &ply in &plies {
        let mut g = Game::from_seed(&seed);
        for _ in 0..ply {
            let la = g.legal_actions();
            if la.is_empty() {
                break;
            }
            g.advance(la[0]).unwrap();
        }
        let n_legal = g.legal_actions().len();

        // --- isolated leaf cost, scratch-reused (the production configuration) ---
        let mut scratch = LeafScratch::new();
        let player = g.state.current_player;
        let mut leaf_ts: Vec<f64> = Vec::new();
        const LEAF_ITERS: usize = 2_000;
        for _ in 0..reps {
            let t0 = Instant::now();
            let mut acc = 0.0f64;
            for _ in 0..LEAF_ITERS {
                acc += std::hint::black_box(
                    scratch.leaf_value_float(&g.state, player, &leaf_cfg).unwrap(),
                );
            }
            std::hint::black_box(acc);
            leaf_ts.push(t0.elapsed().as_secs_f64() / LEAF_ITERS as f64);
        }
        leaf_ts.sort_by(|x, y| x.partial_cmp(y).unwrap());
        let leaf_us = leaf_ts[0] * 1e6;

        // --- the child sweep: clone + advance + leaf, per legal action ---
        // This is EXACTLY what `Searcher::evaluate` does per child to build the
        // heuristic priors, and exactly what a net forward replaces. Timed as the
        // whole triple because the clone is not separable in practice — the
        // afterstate has to exist before it can be evaluated.
        let legal = g.legal_actions();
        let mut child_ts: Vec<f64> = Vec::new();
        if !legal.is_empty() {
            for _ in 0..reps {
                let t0 = Instant::now();
                let mut acc = 0.0f64;
                for &a in &legal {
                    let mut child = g.clone();
                    if child.advance(a).is_ok() {
                        acc += scratch
                            .leaf_value_float(&child.state, player, &leaf_cfg)
                            .unwrap_or(0.0);
                    }
                }
                std::hint::black_box(acc);
                child_ts.push(t0.elapsed().as_secs_f64() / legal.len() as f64);
            }
            child_ts.sort_by(|x, y| x.partial_cmp(y).unwrap());
        } else {
            child_ts.push(0.0);
        }
        let child_us = child_ts[0] * 1e6;

        // --- full search: wall clock + the leaf-eval counter ---
        let mut ts: Vec<f64> = Vec::new();
        let mut leaf_evals = 0u64;
        let mut nodes = 0usize;
        for _ in 0..reps {
            let t0 = Instant::now();
            let r = search_single(&g, &cfg).unwrap();
            ts.push(t0.elapsed().as_secs_f64());
            leaf_evals = r.leaf_evals;
            nodes = r.node_count;
        }
        ts.sort_by(|x, y| x.partial_cmp(y).unwrap());
        let best = ts[0];
        let ms_per_sim = best * 1e3 / cfg.simulations as f64;
        let leaf_per_sim = leaf_evals as f64 / cfg.simulations as f64;
        // The sweep evaluates the CHILDREN: `leaf_per_sim` counts the parent too,
        // so the children are `leaf_per_sim - 1` per simulation.
        let sweep_ms_per_sim = (leaf_per_sim - 1.0).max(0.0) * child_us / 1e3;
        println!(
            "{ply}\t{n_legal}\t{:.2}\t{:.5}\t{leaf_evals}\t{:.2}\t{:.2}\t{:.2}\t{:.5}\t{:.3}\t{nodes}",
            best * 1e3,
            ms_per_sim,
            leaf_per_sim,
            leaf_us,
            child_us,
            sweep_ms_per_sim,
            sweep_ms_per_sim / ms_per_sim,
        );
    }
}
