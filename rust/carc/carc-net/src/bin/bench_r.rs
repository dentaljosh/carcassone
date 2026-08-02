//! `bench_r` — the forward-cost half of `r`, measured in-process from Rust.
//!
//!     cargo run --release --bin bench_r -- <onnx-dir> [search_ms_per_sim]
//!
//! `r = forward_ms / search_ms_per_sim` is the CL-067 gate's reopen statistic
//! (`measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md` §6, bar `<= ~1.5`).
//! This binary measures the numerator on every backend/batch combination that a rust
//! net arm could plausibly ship, and divides by a denominator measured separately by
//! `carc-core`'s `examples/evalprobe.rs` on the same box and build.
//!
//! Two reporting choices, both deliberate:
//!
//! * **Per-leaf amortized cost is what `r` is computed from at batch > 1.** A batch-8
//!   forward that costs 1.2 ms serves 8 leaves, so the cost attributable to one leaf
//!   evaluation is 0.15 ms. Batching across the k determinizations is the only
//!   amortization available to a PUCT search (the tree itself is sequential), and
//!   k = 8 is exactly the champion's width and the SHM transport's `MAX_K`.
//! * **min, not mean.** The box is shared with a live eval; the minimum over reps is
//!   the statistic least contaminated by a neighbour's cache pressure. The median is
//!   printed alongside so the spread is visible rather than hidden.
//!
//! The forward is timed WITHOUT host-side masking. Masking is O(action_size) of host
//! memory traffic that is identical across backends; folding it in would smear the
//! device comparison this bench exists to make. `faithful` covers the masked path.

use carc_core::eval::NetRep;
use carc_net::{Backend, OrtPolicyEvaluator};
use std::time::Instant;

/// Mid-game per-simulation search cost of the rust classical search, ms.
/// Measured by `examples/evalprobe.rs` at the champion's own per-determinization
/// budget (`SearchConfig::default().simulations` = 1376). Overridable on the CLI so
/// the same binary can be re-read against another box's denominator.
const DEFAULT_SEARCH_MS_PER_SIM: f64 = 0.0903;

fn bench(
    dir: &str,
    rep: NetRep,
    batch: usize,
    backend: Backend,
    reps: usize,
) -> Option<(f64, f64)> {
    let path = format!("{dir}/policy_b{batch}.onnx");
    let mut ev = match OrtPolicyEvaluator::new(&path, rep, batch, backend) {
        Ok(e) => e,
        Err(e) => {
            println!("  {:<12} b{:<3} UNAVAILABLE: {e}", backend.label(), batch);
            return None;
        }
    };

    let boards = vec![0.05f32; batch * rep.board_stride()];
    let scalars = vec![0.05f32; batch * rep.n_scalars];

    for _ in 0..20 {
        ev.logits_batch(&boards, &scalars).ok()?;
    }
    let mut ts = Vec::with_capacity(reps);
    for _ in 0..reps {
        let t0 = Instant::now();
        ev.logits_batch(&boards, &scalars).ok()?;
        ts.push(t0.elapsed().as_secs_f64() * 1e3);
    }
    ts.sort_by(|a, b| a.partial_cmp(b).unwrap());
    Some((ts[0], ts[ts.len() / 2]))
}

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let dir = a
        .first()
        .cloned()
        .unwrap_or_else(|| panic!("usage: bench_r <onnx-dir> [search_ms_per_sim]"));
    let denom: f64 = a
        .get(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(DEFAULT_SEARCH_MS_PER_SIM);
    let reps: usize = a.get(2).and_then(|s| s.parse().ok()).unwrap_or(200);

    let rep = NetRep::SIGHTED;
    println!("# carc-net forward bench — 6x96 policy head, rep 81ch/42sc, A=2511");
    println!("# denominator search_ms_per_sim = {denom:.5} ms (evalprobe, rust classical search)");
    println!("# r = per_leaf_forward_ms / search_ms_per_sim ; CL-067 reopen bar r <= ~1.5");
    println!();
    println!(
        "{:<13} {:>5} {:>11} {:>11} {:>12} {:>8}  {}",
        "backend", "batch", "fwd_min_ms", "fwd_med_ms", "per_leaf_ms", "r", "verdict"
    );

    let backends = [
        Backend::Cpu(1),
        Backend::Cpu(4),
        Backend::Cpu(8),
        Backend::Cuda,
        Backend::CudaGraph,
    ];
    for backend in backends {
        for batch in [1usize, 8, 64] {
            if let Some((mn, med)) = bench(&dir, rep, batch, backend, reps) {
                let per_leaf = mn / batch as f64;
                let r = per_leaf / denom;
                let verdict = if r <= 1.5 { "CLEARS" } else { "fails" };
                println!(
                    "{:<13} {:>5} {:>11.4} {:>11.4} {:>12.4} {:>8.2}  {}",
                    backend.label(),
                    batch,
                    mn,
                    med,
                    per_leaf,
                    r,
                    verdict
                );
            }
        }
    }
}
