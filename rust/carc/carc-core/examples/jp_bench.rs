// J-RULES PRIOR surface B — search-level cost bench (G7 analogue).
//
// Interleaved paired A/B (off, on, off, on ...) per position so a shared-tenancy
// box distorts both legs alike; report per-position ratios and the aggregate.
// Run: cargo run --release -p carc-core --example jp_bench [dose]
use std::time::Instant;

use carc_core::game::Game;
use carc_core::search::{search_single, SearchConfig};

fn positions() -> Vec<Game> {
    let mut out = Vec::new();
    for seed in ["28000000000", "42", "7", "1234"] {
        let mut g = Game::from_seed(seed);
        let mut ply = 0;
        loop {
            let legal = g.legal_actions();
            if legal.is_empty() {
                break;
            }
            if ply >= 30 && ply % 18 == 0 && legal.len() >= 6 {
                out.push(g.clone());
            }
            if ply >= 90 {
                break;
            }
            let a = legal[legal.len() / 2];
            g.advance(a).unwrap();
            ply += 1;
        }
    }
    out
}

fn main() {
    let dose: f64 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(0.25);
    let scope = match std::env::args().nth(2).as_deref() {
        Some("own") => carc_core::search::JrPriorScope::Own,
        // S1 (measurement/s1_asymmetry_prep): the opponent-model arm. This is
        // the direct measurement of SIZING §3's INFERRED 1.085x overhead.
        Some("opp") => carc_core::search::JrPriorScope::Opp,
        _ => carc_core::search::JrPriorScope::All,
    };
    let sims = 1376usize;
    let off = SearchConfig {
        simulations: sims,
        ..SearchConfig::default()
    };
    let on = SearchConfig {
        simulations: sims,
        jrules_prior_dose: dose,
        jrules_prior_scope: scope,
        ..SearchConfig::default()
    };
    let ps = positions();
    eprintln!("positions: {} · sims {} · dose {} · scope {:?}", ps.len(), sims, dose, scope);
    // warm both paths
    for g in ps.iter().take(2) {
        search_single(g, &off).unwrap();
        search_single(g, &on).unwrap();
    }
    // MIN-of-reps per leg: robust to shared-tenancy contention (the min
    // approximates the unloaded time; the mean does not).
    let reps = 6;
    let mut tot_off = 0.0f64;
    let mut tot_on = 0.0f64;
    let mut ratios: Vec<f64> = Vec::new();
    for (i, g) in ps.iter().enumerate() {
        let mut t_off = f64::INFINITY;
        let mut t_on = f64::INFINITY;
        for _ in 0..reps {
            let t = Instant::now();
            search_single(g, &off).unwrap();
            t_off = t_off.min(t.elapsed().as_secs_f64());
            let t = Instant::now();
            search_single(g, &on).unwrap();
            t_on = t_on.min(t.elapsed().as_secs_f64());
        }
        tot_off += t_off;
        tot_on += t_on;
        ratios.push(t_on / t_off);
        println!(
            "pos {i:2}: off {:7.1} ms  on {:7.1} ms  ratio {:.4}  (min of {reps})",
            1e3 * t_off,
            1e3 * t_on,
            t_on / t_off
        );
    }
    ratios.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let median = ratios[ratios.len() / 2];
    println!(
        "AGGREGATE ratio on/off = {:.4}  median {:.4}  (off {:.1} ms/search, on {:.1} ms/search)",
        tot_on / tot_off,
        median,
        1e3 * tot_off / ps.len() as f64,
        1e3 * tot_on / ps.len() as f64,
    );
}
