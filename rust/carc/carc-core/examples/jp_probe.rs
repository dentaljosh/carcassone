// Scratch probe (not shipped as a gate): how often does jrules_prior_term
// differentiate siblings, and by how much? Used while building surface B.
use carc_core::game::Game;
use carc_core::leaf::{self, LeafConfig, LeafScratch};

fn main() {
    let cfg = LeafConfig::curve125();
    let mut scratch = LeafScratch::new();
    let mut n_nodes = 0;
    let mut n_diff = 0;
    for seed in ["28000000000", "42", "7", "1234", "999"] {
        let mut g = Game::from_seed(seed);
        for ply in 0..120 {
            let legal = g.legal_actions();
            if legal.is_empty() {
                break;
            }
            let pinned_ply = (seed == "28000000000" && ply == 55)
                || (seed == "42" && ply == 61)
                || (seed == "7" && ply == 71);
            if pinned_ply {
                println!("PINNED-ARRIVED seed {seed} ply {ply} legal={}", legal.len());
            }
            if ply >= 30 && legal.len() >= 2 {
                let mover = g.state.current_player;
                leaf::decompose_into(&g.state, &mut scratch.decomp, &mut scratch.scratch);
                let clock = leaf::jr_prior_clock(&g.state, mover, &scratch.decomp);
                let mut vals: Vec<f64> = Vec::new();
                for &a in &legal {
                    let mut child = g.clone();
                    child.advance(a).unwrap();
                    let (_lv, base) =
                        scratch.leaf_float_and_base(&child.state, mover, &cfg, false).unwrap();
                    let t = leaf::jrules_prior_term(
                        &child.state, mover, &scratch.decomp, 31, &clock, base,
                    );
                    vals.push(t);
                }
                n_nodes += 1;
                let mn = vals.iter().cloned().fold(f64::INFINITY, f64::min);
                let mx = vals.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
                if mx - mn > 1e-12 {
                    n_diff += 1;
                }
                let pinned = (seed == "28000000000" && ply == 55)
                    || (seed == "42" && ply == 61)
                    || (seed == "7" && ply == 71);
                if pinned {
                    println!(
                        "PINNED seed {seed} ply {ply}: spread {:.4} (min {mn:.3} max {mx:.3}, n={})",
                        mx - mn,
                        vals.len()
                    );
                }
            }
            let a = legal[legal.len() / 2];
            g.advance(a).unwrap();
        }
    }
    println!("nodes probed: {n_nodes}, differentiating: {n_diff}");
}
