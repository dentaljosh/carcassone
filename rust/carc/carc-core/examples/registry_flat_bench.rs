//! **Registry flattening — directional bench.**
//!
//! Same cost-law harness as the L1 delta spike's Bench A: capture board states
//! at every tile placement across several deck seeds, then time
//! `decompose_into` (flat registry) against `decompose_into_ref` (the frozen
//! object-registry path) on the SAME states, interleaved, and least-squares fit
//! `ns = a + b * placed` for each arm.
//!
//! A second arm pair adds the production leaf (`leaf_terms_with(curve125)`, both
//! povs) on top of the same decomposition, so the readout carries the
//! consumer-level factor as well as the decompose-only one.
//!
//! Run (release, niced):
//! ```text
//! nice -n 19 cargo run --release --example registry_flat_bench \
//!     --manifest-path rust/carc/Cargo.toml
//! ```

use std::time::Instant;

use carc_core::engine::GameState;
use carc_core::game::Game;
use carc_core::leaf::decomp::decompose_into_ref;
use carc_core::leaf::{decompose_into, leaf_terms_with, Decomp, LeafConfig, Scratch};

/// Least-squares fit of `y = a + b*x`; returns `(a, b, r2)`.
fn fit(xs: &[f64], ys: &[f64]) -> (f64, f64, f64) {
    let n = xs.len() as f64;
    let mx = xs.iter().sum::<f64>() / n;
    let my = ys.iter().sum::<f64>() / n;
    let (mut sxy, mut sxx) = (0.0, 0.0);
    for i in 0..xs.len() {
        sxy += (xs[i] - mx) * (ys[i] - my);
        sxx += (xs[i] - mx) * (xs[i] - mx);
    }
    let b = sxy / sxx;
    let a = my - b * mx;
    let (mut ss_res, mut ss_tot) = (0.0, 0.0);
    for i in 0..xs.len() {
        let p = a + b * xs[i];
        ss_res += (ys[i] - p) * (ys[i] - p);
        ss_tot += (ys[i] - my) * (ys[i] - my);
    }
    (a, b, 1.0 - ss_res / ss_tot)
}

struct Sample {
    state: GameState,
    placed: usize,
}

/// Board states captured after every tile placement of a greedy game.
fn capture(seed: &str, out: &mut Vec<Sample>) {
    let mut g = Game::from_seed(seed);
    let mut ply = 0usize;
    let mut last = 0usize;
    while !g.is_terminal() && ply < 400 {
        let legal = g.legal_actions();
        if legal.is_empty() {
            break;
        }
        g.advance(legal[0]).unwrap();
        ply += 1;
        let placed = g.state.placed_coords.len();
        if placed > last {
            last = placed;
            out.push(Sample {
                state: g.state.clone(),
                placed,
            });
        }
    }
}

fn main() {
    let mut samples: Vec<Sample> = Vec::new();
    for s in ["1", "2", "3", "17", "99", "1234", "555", "31337"] {
        capture(s, &mut samples);
    }
    eprintln!("== registry flattening — directional bench ==");
    eprintln!("samples: {}", samples.len());

    let reps: usize = std::env::var("REPS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(400);
    let cfg = LeafConfig::curve125();

    let mut d = Decomp::default();
    let mut sc = Scratch::default();
    // warm-up (allocator + OnceLock init + i-cache for both arms)
    for s in samples.iter().take(64) {
        decompose_into(&s.state, &mut d, &mut sc);
        decompose_into_ref(&s.state, &mut d, &mut sc);
    }

    // (placed, ref_ns, new_ns, ref_leaf_ns, new_leaf_ns)
    let mut rows: Vec<(usize, f64, f64, f64, f64)> = Vec::new();
    for s in samples.iter() {
        let t = Instant::now();
        for _ in 0..reps {
            decompose_into_ref(&s.state, &mut d, &mut sc);
            std::hint::black_box(&d);
        }
        let ref_ns = t.elapsed().as_nanos() as f64 / reps as f64;

        let t = Instant::now();
        for _ in 0..reps {
            decompose_into(&s.state, &mut d, &mut sc);
            std::hint::black_box(&d);
        }
        let new_ns = t.elapsed().as_nanos() as f64 / reps as f64;

        let t = Instant::now();
        for _ in 0..reps {
            decompose_into_ref(&s.state, &mut d, &mut sc);
            for p in 0..2 {
                std::hint::black_box(leaf_terms_with(&s.state, p, &cfg, &d).ok());
            }
        }
        let ref_leaf_ns = t.elapsed().as_nanos() as f64 / reps as f64;

        let t = Instant::now();
        for _ in 0..reps {
            decompose_into(&s.state, &mut d, &mut sc);
            for p in 0..2 {
                std::hint::black_box(leaf_terms_with(&s.state, p, &cfg, &d).ok());
            }
        }
        let new_leaf_ns = t.elapsed().as_nanos() as f64 / reps as f64;

        rows.push((s.placed, ref_ns, new_ns, ref_leaf_ns, new_leaf_ns));
    }

    let xs: Vec<f64> = rows.iter().map(|r| r.0 as f64).collect();
    let y_ref: Vec<f64> = rows.iter().map(|r| r.1).collect();
    let y_new: Vec<f64> = rows.iter().map(|r| r.2).collect();
    let (a_ref, b_ref, r2_ref) = fit(&xs, &y_ref);
    let (a_new, b_new, r2_new) = fit(&xs, &y_new);

    let tot_ref: f64 = y_ref.iter().sum();
    let tot_new: f64 = y_new.iter().sum();
    let tot_ref_leaf: f64 = rows.iter().map(|r| r.3).sum();
    let tot_new_leaf: f64 = rows.iter().map(|r| r.4).sum();

    eprintln!(
        "ref (object registry): {a_ref:+.1} + {b_ref:.2} * placed ns   R2={r2_ref:.3}"
    );
    eprintln!(
        "new (flat registry)  : {a_new:+.1} + {b_new:.2} * placed ns   R2={r2_new:.3}"
    );
    eprintln!("decompose factor (sum over samples): {:.3}x", tot_ref / tot_new);
    eprintln!("slope factor (ns/placed):            {:.3}x", b_ref / b_new);
    eprintln!(
        "decompose+leaf(2 pov) factor:        {:.3}x",
        tot_ref_leaf / tot_new_leaf
    );

    // per-bucket table
    let mut json = String::from("{\n  \"buckets\": [\n");
    eprintln!("\n placed | ref ns | new ns | factor");
    for lo in (0..88).step_by(8) {
        let sel: Vec<&(usize, f64, f64, f64, f64)> =
            rows.iter().filter(|r| r.0 >= lo && r.0 < lo + 8).collect();
        if sel.is_empty() {
            continue;
        }
        let n = sel.len() as f64;
        let mr = sel.iter().map(|r| r.1).sum::<f64>() / n;
        let mn = sel.iter().map(|r| r.2).sum::<f64>() / n;
        eprintln!(
            "  {:2}-{:2} | {:6.0} | {:6.0} | {:.3}x",
            lo,
            lo + 7,
            mr,
            mn,
            mr / mn
        );
        json.push_str(&format!(
            "    {{\"lo\": {lo}, \"hi\": {}, \"n\": {}, \"ref_ns\": {mr:.1}, \"new_ns\": {mn:.1}, \"factor\": {:.4}}},\n",
            lo + 7,
            sel.len(),
            mr / mn
        ));
    }
    if json.ends_with(",\n") {
        json.truncate(json.len() - 2);
        json.push('\n');
    }
    json.push_str("  ],\n");
    json.push_str(&format!("  \"reps\": {reps},\n  \"samples\": {},\n", rows.len()));
    json.push_str(&format!(
        "  \"ref_law\": {{\"a\": {a_ref:.4}, \"b\": {b_ref:.4}, \"r2\": {r2_ref:.5}}},\n"
    ));
    json.push_str(&format!(
        "  \"new_law\": {{\"a\": {a_new:.4}, \"b\": {b_new:.4}, \"r2\": {r2_new:.5}}},\n"
    ));
    json.push_str(&format!(
        "  \"decompose_factor\": {:.4},\n  \"slope_factor\": {:.4},\n  \"decompose_plus_leaf_factor\": {:.4}\n}}\n",
        tot_ref / tot_new,
        b_ref / b_new,
        tot_ref_leaf / tot_new_leaf
    ));
    print!("{json}");
}
