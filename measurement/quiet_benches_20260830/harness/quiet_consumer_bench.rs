//! **Registry flattening — the two CONSUMER arms the quiet re-read owes**
//! (`measurement/registry_flattening_20260830/READOUT.md` §6 items 2 and 3).
//!
//! §6.2 asks for "a real search slice, not just `decompose`", and §6.3 for "a
//! tier1 playout arm post-swap, since tier1 is the other full-rebuild consumer".
//!
//! Both arms time the SAME frozen roots under the SAME binary; the arm is
//! selected by `CARC_DECOMP_REF` (a scratch-build-only `OnceLock` dispatch
//! inserted at the top of `leaf::decomp::decompose_into`):
//!
//! * `CARC_DECOMP_REF=0` (default) — the flat registry, i.e. the new path.
//! * `CARC_DECOMP_REF=1`           — `decompose_into_ref`, the frozen
//!                                   object-registry reference.
//!
//! Because the flat path is bit-identical (READOUT §3, 149,100 positions), both
//! arms visit the SAME nodes and play the SAME moves — the emitted
//! `chosen_action` / `root_n` / playout `margin` and `plies` are printed so the
//! caller can verify that arm-to-arm identity rather than assume it.
//!
//!     ./quiet_consumer_bench <reps> <playout_reps>

use std::time::Instant;

use carc_core::game::Game;
use carc_core::search::{search_single, SearchConfig};
use carc_core::tier1::tier1_playout;

/// Replay first-legal to a given ply — the `perfprobe` idiom. This is a COST
/// probe; move quality is irrelevant to what it measures.
fn root_at(seed: &str, ply: usize) -> Game {
    let mut g = Game::from_seed(seed);
    for _ in 0..ply {
        let la = g.legal_actions();
        if la.is_empty() {
            break;
        }
        g.advance(la[0]).unwrap();
    }
    g
}

fn med(v: &mut Vec<f64>) -> f64 {
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    v[v.len() / 2]
}

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let reps: usize = a.first().and_then(|s| s.parse().ok()).unwrap_or(3);
    let preps: usize = a.get(1).and_then(|s| s.parse().ok()).unwrap_or(20);
    let arm = if std::env::var("CARC_DECOMP_REF").as_deref() == Ok("1") {
        "ref_object"
    } else {
        "flat"
    };

    let cfg = SearchConfig::default();
    eprintln!("== consumer arms — arm={arm} sims={} reps={reps} playout_reps={preps}", cfg.simulations);

    // ---- Arm S: a real search slice (whole PUCT, production budget) ----
    // Tile-phase-ish roots across the game arc, on three deck seeds.
    let seeds = ["1", "17", "1234"];
    let plies = [10usize, 30, 50, 70, 90];
    let mut json = String::from("{\n  \"arm\": \"");
    json.push_str(arm);
    json.push_str("\",\n  \"search\": [\n");
    let mut s_tot = 0.0f64;
    eprintln!("\n-- arm S: search_single (sims={})", cfg.simulations);
    eprintln!(" seed  ply | med_s   | nodes | chosen | root_n");
    for seed in seeds {
        for &ply in &plies {
            let g = root_at(seed, ply);
            if g.is_terminal() {
                continue;
            }
            // warm-up
            let w = search_single(&g, &cfg).unwrap();
            let mut ts: Vec<f64> = Vec::new();
            for _ in 0..reps {
                let t0 = Instant::now();
                let r = search_single(&g, &cfg).unwrap();
                ts.push(t0.elapsed().as_secs_f64());
                std::hint::black_box(r.chosen_action);
            }
            let m = med(&mut ts);
            s_tot += m;
            eprintln!(
                "  {seed:>4} {ply:>3} | {m:.5} | {:5} | {:6} | {}",
                w.node_count, w.chosen_action, w.root_n
            );
            json.push_str(&format!(
                "    {{\"seed\": \"{seed}\", \"ply\": {ply}, \"med_s\": {m:.6}, \"nodes\": {}, \"chosen_action\": {}, \"root_n\": {}}},\n",
                w.node_count, w.chosen_action, w.root_n
            ));
        }
    }
    if json.ends_with(",\n") {
        json.truncate(json.len() - 2);
        json.push('\n');
    }
    json.push_str("  ],\n");
    json.push_str(&format!("  \"search_total_med_s\": {s_tot:.6},\n"));
    eprintln!("arm S total of medians: {s_tot:.5} s");

    // ---- Arm T: tier1 playouts (the other full-rebuild consumer) ----
    eprintln!("\n-- arm T: tier1_playout");
    eprintln!(" seed  ply | med_s   | margin | plies");
    json.push_str("  \"tier1\": [\n");
    let mut t_tot = 0.0f64;
    for seed in seeds {
        for &ply in &[8usize, 24, 40] {
            let g = root_at(seed, ply);
            if g.is_terminal() {
                continue;
            }
            let pick = g.legal_actions()[0];
            // warm-up + the identity receipts
            let (wm, wp) = tier1_playout(&g, pick, 0, 12345, 400, None).unwrap();
            let mut ts: Vec<f64> = Vec::new();
            for _ in 0..reps {
                let t0 = Instant::now();
                for k in 0..preps {
                    let r = tier1_playout(&g, pick, 0, 12345 + k as i64, 400, None).unwrap();
                    std::hint::black_box(r.0);
                }
                ts.push(t0.elapsed().as_secs_f64() / preps as f64);
            }
            let m = med(&mut ts);
            t_tot += m;
            eprintln!("  {seed:>4} {ply:>3} | {m:.5} | {wm:6.1} | {wp}");
            json.push_str(&format!(
                "    {{\"seed\": \"{seed}\", \"ply\": {ply}, \"med_s\": {m:.6}, \"margin\": {wm}, \"plies\": {wp}}},\n"
            ));
        }
    }
    if json.ends_with(",\n") {
        json.truncate(json.len() - 2);
        json.push('\n');
    }
    json.push_str("  ],\n");
    json.push_str(&format!("  \"tier1_total_med_s\": {t_tot:.6}\n}}\n"));
    eprintln!("arm T total of medians: {t_tot:.5} s");
    print!("{json}");
}
