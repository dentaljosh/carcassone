//! `tiearb` world-threading bench — the latency half of the 2026-08-21
//! "arbiter playout threading" lever (the identity half is the in-crate
//! `threading_is_bit_identical_to_sequential` gate).
//!
//! ```text
//! cargo build --release --manifest-path rust/carc/carc-core/Cargo.toml \
//!     --example tiearb_thread_bench
//! ./rust/carc/target/release/examples/tiearb_thread_bench [B] [n_arms] [plies]
//! ```
//!
//! Reports s/call and the speedup over `threads = 1` at 1/2/4/8 threads, and
//! ASSERTS bit-identical means at every thread count so a bench number can
//! never be bought with a changed answer.

use std::time::Instant;

use carc_core::game::Game;
use carc_core::tiearb::{arbitrate, TiearbMode, TIEARB_MAX_PLIES, TIEARB_SALT_OF_RECORD};

fn midgame(seed: &str, plies: usize) -> Game {
    let mut g = Game::from_seed(seed);
    for _ in 0..plies {
        let l = g.legal_actions();
        g.advance(l[l.len() / 2]).unwrap();
    }
    while g.state.phase != carc_core::engine::Phase::Tiles || g.legal_actions().len() < 4 {
        let l = g.legal_actions();
        g.advance(l[l.len() / 2]).unwrap();
    }
    g
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let b: usize = args.get(1).map(|s| s.parse().unwrap()).unwrap_or(64);
    let n_arms: usize = args.get(2).map(|s| s.parse().unwrap()).unwrap_or(3);
    let plies: usize = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(40);

    let g = midgame("28000000000", plies);
    let legal = g.legal_actions();
    assert!(
        legal.len() >= n_arms,
        "need >= {n_arms} legal actions, got {}",
        legal.len()
    );
    let arms: Vec<i32> = legal.iter().copied().take(n_arms).collect();
    let seat = g.state.current_player;

    println!(
        "tiearb thread bench: B={b}, arms={n_arms} ({} playouts/call), mid-game ply {plies}, \
         {} legal actions, hw_par={:?}",
        b * n_arms,
        legal.len(),
        std::thread::available_parallelism().map(|n| n.get()).ok()
    );
    println!("{:>8} {:>12} {:>10} {:>12}", "threads", "s/call", "speedup", "means-ok");

    let mut base: Option<f64> = None;
    let mut ref_means: Option<Vec<u64>> = None;
    for t in [1usize, 2, 4, 8] {
        // one warm call, then the timed one (a single arbitrate at B=64 is
        // already ~seconds; the run-to-run spread is small next to the effect).
        let t0 = Instant::now();
        let out = arbitrate(
            &g,
            seat,
            &arms,
            b,
            TIEARB_SALT_OF_RECORD,
            "bench-digest",
            7,
            TiearbMode::Argmax,
            TIEARB_MAX_PLIES,
            t,
        )
        .expect("arbitrate failed");
        let dt = t0.elapsed().as_secs_f64();
        let bits: Vec<u64> = out.means.iter().map(|m| m.to_bits()).collect();
        let ok = match &ref_means {
            None => {
                ref_means = Some(bits);
                true
            }
            Some(r) => *r == bits,
        };
        assert!(ok, "means differ at threads={t} — the bench is not measuring the same computation");
        let sp = match base {
            None => {
                base = Some(dt);
                1.0
            }
            Some(b0) => b0 / dt,
        };
        println!("{t:>8} {dt:>12.4} {sp:>9.2}x {:>12}", if ok { "yes" } else { "NO" });
    }
}
