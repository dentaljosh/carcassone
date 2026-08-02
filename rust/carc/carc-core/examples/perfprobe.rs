//! The measurement instrument for the 2026-08-02 perf pass (review findings
//! #2/#3/#4 + the ROUND2 C-e/C-f riders).  It exists because the review's core
//! complaint was that **no gate in the port measures cost at all** — gates
//! assert identity, so a byte-identical rewrite is invisible to them.
//!
//!     cargo build --release --example perfprobe -p carc-core
//!     ./target/release/examples/perfprobe <seed-decimal> <ply,ply,...> <reps> [pp]
//!
//! Prints, per ply: wall-clock seconds per `search_single` at the `SearchConfig`
//! default budget (min/median/max over `reps`) and the process VmHWM (peak RSS,
//! KiB).  Run ONE ply per process when the RSS number matters — VmHWM is a
//! process-lifetime high-water mark, not a per-call one.  The optional `pp`
//! argument switches to an isolated `possible_playing_positions` microbench
//! (the C-f rider) instead of the full search.
//!
//! Positions are reached by replaying the first-legal action, which is a cheap
//! deterministic way to a board of a given ply — it is a COST probe, not a
//! strength one, and nothing about the move quality matters to what it measures.

use carc_core::game::Game;
use carc_core::search::{search_single, SearchConfig};
use std::time::Instant;

fn vmhwm_kb() -> u64 {
    let s = std::fs::read_to_string("/proc/self/status").unwrap_or_default();
    for line in s.lines() {
        if let Some(rest) = line.strip_prefix("VmHWM:") {
            return rest
                .trim()
                .trim_end_matches(" kB")
                .trim()
                .parse()
                .unwrap_or(0);
        }
    }
    0
}

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let seed = a[0].clone();
    let plies: Vec<usize> = a[1].split(',').map(|s| s.parse().unwrap()).collect();
    let reps: usize = a[2].parse().unwrap();
    let cfg = SearchConfig::default();

    for &ply in &plies {
        let mut g = Game::from_seed(&seed);
        for _ in 0..ply {
            let la = g.legal_actions();
            if la.is_empty() {
                break;
            }
            g.advance(la[0]).unwrap();
        }
        let repr_len = g.string_repr().len();
        // Optional 4th arg "pp": microbench `possible_playing_positions` alone
        // (the C-f rider) instead of the full search.
        if a.len() > 3 && a[3] == "pp" {
            let base = g.state.next_tile.unwrap_or(0);
            let mut ts: Vec<f64> = Vec::new();
            let mut acc = 0usize;
            for _ in 0..reps {
                let t0 = Instant::now();
                for _ in 0..20_000 {
                    acc += std::hint::black_box(g.state.possible_playing_positions(base)).len();
                }
                ts.push(t0.elapsed().as_secs_f64());
            }
            ts.sort_by(|x, y| x.partial_cmp(y).unwrap());
            println!(
                "ply={ply} repr_bytes={repr_len} nodes={acc} min={:.4} med={:.4} max={:.4} vmhwm_kb={}",
                ts[0],
                ts[reps / 2],
                ts[reps - 1],
                vmhwm_kb()
            );
            continue;
        }
        let mut ts: Vec<f64> = Vec::new();
        let mut nodes = 0usize;
        for _ in 0..reps {
            let t0 = Instant::now();
            let r = search_single(&g, &cfg).unwrap();
            ts.push(t0.elapsed().as_secs_f64());
            nodes = r.node_count;
        }
        ts.sort_by(|x, y| x.partial_cmp(y).unwrap());
        println!(
            "ply={ply} repr_bytes={repr_len} nodes={nodes} min={:.4} med={:.4} max={:.4} vmhwm_kb={}",
            ts[0],
            ts[reps / 2],
            ts[reps - 1],
            vmhwm_kb()
        );
    }
}
