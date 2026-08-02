//! `faithful` — argmax-faithfulness of the ORT backend vs torch, on real positions.
//!
//!     cargo run --release --bin faithful -- <onnx-dir> <positions.bin> [batch]
//!
//! ## Why this is not a bit-exactness test
//!
//! It cannot be. Cross-framework float identity is not achievable: ORT and torch
//! pick different conv algorithms, different reduction orders, and different fusion
//! boundaries, and any one of those moves the last ULP. The project has already
//! priced this and set the precedent — `src/carcassonne_ai/coreml_evaluator.py`
//! accepts its ANE backend on **argmax and top-5 agreement plus a reported max-abs
//! residual** (measured 2.4e-7, bit-identical 0/500, argmax and top-5 100%), not on
//! equality, and `verify_coreml_evaluator.py` reports exactly those fields.
//!
//! This binary produces the same readout for the ORT path, so the two backends are
//! judged on one ruler. What matters for search is **move ORDERING**: PUCT consumes
//! priors as a ranking plus a magnitude, and a perturbation that changes no argmax
//! and no top-5 ordering cannot change the move a search selects except through
//! second-order visit-allocation effects.
//!
//! ## What is compared
//!
//! Torch's reference priors are computed at batch 1 by `tools/dump_positions.py` and
//! shipped inside the position dump, so both sides see byte-identical inputs and the
//! residual reported here is backend drift and nothing else. Rows with no legal
//! action (a handful of terminal/aux corpus records) are EXCLUDED and counted
//! separately — they cannot disagree, so scoring them would inflate the agreement
//! rate.

use carc_core::eval::{legal_argmax, NetRep, PolicyEvaluator};
use carc_net::positions::Positions;
use carc_net::{Backend, OrtPolicyEvaluator};

/// Ordered top-k legal actions of a prior row.
fn top_k(priors: &[f32], mask: &[bool], k: usize) -> Vec<usize> {
    let mut idx: Vec<usize> = (0..priors.len()).filter(|&i| mask[i]).collect();
    // Sort by descending prior, ties by ascending index — the same order
    // `np.argsort(-p, kind="stable")` produces, so the comparison is like-for-like.
    idx.sort_by(|&a, &b| {
        priors[b]
            .partial_cmp(&priors[a])
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.cmp(&b))
    });
    idx.truncate(k);
    idx
}

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let dir = &a[0];
    let posfile = &a[1];
    let batch: usize = a.get(2).and_then(|s| s.parse().ok()).unwrap_or(8);

    let p = Positions::load(posfile).expect("load positions");
    let rep = NetRep {
        n_channels: p.n_channels,
        n_scalars: p.n_scalars,
        window: p.window,
        action_size: p.action_size,
    };
    let scorable = p.scorable();
    println!("# positions {} ({} scorable, {} all-illegal excluded)", p.n, scorable.len(), p.n - scorable.len());
    println!("# rep {}ch/{}sc W{} A{} | batch {batch}", p.n_channels, p.n_scalars, p.window, p.action_size);
    println!();
    println!(
        "{:<13} {:>7} {:>10} {:>10} {:>10} {:>12} {:>11}",
        "backend", "n", "argmax%", "top5%", "bitexact", "max_abs", "max_tv"
    );

    // `Backend::CudaGraph` is deliberately NOT exercised here. On this box
    // (ort rc.13 + onnxruntime 1.22) it panics inside ORT's own value layer
    // ("expected `typeinfo_ptr` to not be null") because CUDA-Graph capture wants
    // its inputs and outputs bound to DEVICE memory via IOBinding, and this
    // evaluator hands it host slices. That is an implementation gap, not a
    // faithfulness question — see the design memo §6.2.
    for backend in [Backend::Cpu(4), Backend::Cuda] {
        let path = format!("{dir}/policy_b{batch}.onnx");
        let mut ev = match OrtPolicyEvaluator::new(&path, rep, batch, backend) {
            Ok(e) => e,
            Err(e) => {
                println!("{:<13} UNAVAILABLE: {e}", backend.label());
                continue;
            }
        };

        let bs = p.board_stride();
        let a_sz = p.action_size;
        let mut boards = vec![0.0f32; batch * bs];
        let mut scalars = vec![0.0f32; batch * p.n_scalars];
        let mut masks = vec![false; batch * a_sz];
        let mut out = vec![0.0f32; batch * a_sz];

        let (mut n, mut argmax_ok, mut top5_ok, mut bitexact) = (0usize, 0usize, 0usize, 0usize);
        let (mut max_abs, mut max_tv) = (0.0f64, 0.0f64);

        for chunk in scorable.chunks(batch) {
            // A short final chunk is padded by REPEATING its last row: the ONNX graph
            // is fixed-batch, and repeating a real row keeps the padded lanes on the
            // same numeric distribution as the live ones. Only the first
            // `chunk.len()` lanes are scored.
            for slot in 0..batch {
                let src = chunk[slot.min(chunk.len() - 1)];
                boards[slot * bs..(slot + 1) * bs]
                    .copy_from_slice(&p.boards[src * bs..(src + 1) * bs]);
                scalars[slot * p.n_scalars..(slot + 1) * p.n_scalars]
                    .copy_from_slice(&p.scalars[src * p.n_scalars..(src + 1) * p.n_scalars]);
                masks[slot * a_sz..(slot + 1) * a_sz]
                    .copy_from_slice(&p.masks[src * a_sz..(src + 1) * a_sz]);
            }
            ev.policy_batch(&boards, &scalars, &masks, batch, &mut out)
                .expect("forward");

            for (slot, &src) in chunk.iter().enumerate() {
                let got = &out[slot * a_sz..(slot + 1) * a_sz];
                let refr = &p.ref_priors[src * a_sz..(src + 1) * a_sz];
                let m = &p.masks[src * a_sz..(src + 1) * a_sz];

                n += 1;
                if legal_argmax(got, m) == legal_argmax(refr, m) {
                    argmax_ok += 1;
                }
                if top_k(got, m, 5) == top_k(refr, m, 5) {
                    top5_ok += 1;
                }
                if got == refr {
                    bitexact += 1;
                }
                let mut l1 = 0.0f64;
                for i in 0..a_sz {
                    let d = (got[i] - refr[i]).abs() as f64;
                    if d > max_abs {
                        max_abs = d;
                    }
                    l1 += d;
                }
                let tv = 0.5 * l1;
                if tv > max_tv {
                    max_tv = tv;
                }
            }
        }

        println!(
            "{:<13} {:>7} {:>9.2}% {:>9.2}% {:>10} {:>12.3e} {:>11.3e}",
            backend.label(),
            n,
            100.0 * argmax_ok as f64 / n as f64,
            100.0 * top5_ok as f64 / n as f64,
            bitexact,
            max_abs,
            max_tv
        );
    }
}
