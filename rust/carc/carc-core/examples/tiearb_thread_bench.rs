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
//! Env overrides:
//!   `TIEARB_THREADS` — comma-separated thread counts to sweep, e.g. `2` or
//!                      `2,3` (default `1,2,4,8`).
//!   `TIEARB_REPS`    — timed repeats per thread-count config, clamped to
//!                      [3, 5] (default 5).
//!
//! ⚠️ 2026-08-2x FIX: this bench's doc comment used to promise "one warm call,
//! then the timed one" but the code only ever fired a SINGLE COLD
//! `arbitrate()` per thread count and timed that one call. On mobile that
//! confounds DVFS ramp + EAS little-core placement with the actual threading
//! effect (made B=32 look no cheaper than B=64; rep spread up to 38%). Fixed:
//! every thread count now gets one genuine UNTIMED warm call first (absorbs
//! ramp/placement/caches), followed by `TIEARB_REPS` TIMED repeats, each
//! printed individually plus the median and min across reps. Every call
//! (warm and timed, every thread count) is asserted bit-identical to the
//! first call's means, and each config's mean-bits are also folded into a
//! printed digest so identity can be eyeballed ACROSS separate process
//! invocations too (e.g. two `adb shell` runs at different B) — a single
//! process only ever runs one B value, so the in-process assertion alone
//! can't catch a B-to-B drift.

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

fn parse_threads_env() -> Vec<usize> {
    match std::env::var("TIEARB_THREADS") {
        Ok(s) if !s.trim().is_empty() => s
            .split(',')
            .map(|tok| {
                tok.trim()
                    .parse::<usize>()
                    .unwrap_or_else(|_| panic!("TIEARB_THREADS: bad integer token {tok:?}"))
            })
            .collect(),
        _ => vec![1, 2, 4, 8],
    }
}

fn parse_reps_env() -> usize {
    let reps = std::env::var("TIEARB_REPS")
        .ok()
        .and_then(|s| s.trim().parse::<usize>().ok())
        .unwrap_or(5);
    reps.clamp(3, 5)
}

fn median(sorted_ascending: &[f64]) -> f64 {
    let n = sorted_ascending.len();
    if n % 2 == 1 {
        sorted_ascending[n / 2]
    } else {
        (sorted_ascending[n / 2 - 1] + sorted_ascending[n / 2]) / 2.0
    }
}

/// Order-sensitive FNV-1a-style fold over the mean bit patterns — not
/// cryptographic, just enough to eyeball cross-process identity at a glance.
fn bits_digest(bits: &[u64]) -> u64 {
    bits.iter().fold(0xcbf29ce484222325u64, |acc, &b| {
        (acc ^ b).wrapping_mul(0x100000001b3)
    })
}

/// Records `bits` against the shared reference (set on the very first call
/// across the whole run) and asserts equality on every subsequent call —
/// warm or timed, any thread count.
fn check_identity(ref_means: &mut Option<Vec<u64>>, bits: Vec<u64>, tag: &str) {
    match ref_means {
        None => *ref_means = Some(bits),
        Some(r) => assert!(
            *r == bits,
            "means differ at {tag} — the bench is not measuring the same computation"
        ),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let b: usize = args.get(1).map(|s| s.parse().unwrap()).unwrap_or(64);
    let n_arms: usize = args.get(2).map(|s| s.parse().unwrap()).unwrap_or(3);
    let plies: usize = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(40);
    let threads_list = parse_threads_env();
    let reps = parse_reps_env();

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
         {} legal actions, hw_par={:?}, threads={threads_list:?}, reps={reps}",
        b * n_arms,
        legal.len(),
        std::thread::available_parallelism().map(|n| n.get()).ok(),
    );

    let mut ref_means: Option<Vec<u64>> = None;
    let mut base_median: Option<f64> = None;
    let first_t = threads_list[0];

    let call = |t: usize| -> (f64, Vec<u64>) {
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
        (dt, bits)
    };

    for &t in &threads_list {
        // (a) one genuine UNTIMED warm call — absorbs DVFS ramp, EAS
        // core-placement settling, and any first-touch cache effects before
        // anything is timed. Its wall-clock is deliberately not recorded.
        let (_warm_dt, warm_bits) = call(t);
        check_identity(&mut ref_means, warm_bits, &format!("threads={t} warm"));

        // (b) timed repeats.
        let mut times = Vec::with_capacity(reps);
        for rep in 0..reps {
            let (dt, bits) = call(t);
            check_identity(&mut ref_means, bits, &format!("threads={t} rep={rep}"));
            times.push(dt);
            println!("  threads={t} rep={rep} s/call={dt:.4}");
        }

        let mut sorted = times.clone();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let med = median(&sorted);
        let min = sorted[0];
        let sp = match base_median {
            None => {
                base_median = Some(med);
                1.0
            }
            Some(b0) => b0 / med,
        };
        let digest = bits_digest(ref_means.as_ref().unwrap());
        println!(
            "{t:>8} threads: median={med:.4}s min={min:.4}s speedup(median vs threads={first_t})={sp:.2}x mean_bits_digest=0x{digest:016x}"
        );
    }
}
