//! **L2 — where does `solve_marginalized` actually spend its time?**
//!
//! `perf` is unavailable on the WSL2 kernel, so the solver's per-node budget is
//! decomposed by timing its components directly on states captured from a real
//! solve-shaped descent:
//!
//! * `legal_actions` (the per-node move enumeration + mask allocation)
//! * `string_repr` + the sha256 TT key
//! * `clone` + `apply_action` on a NON-terminal transition
//! * `clone` + `apply_action` on a TERMINAL transition (this is the one that
//!   runs `count_final_scores` in place — the L2 target)
//! * `GameState::flat_base_score` (clone + a second, drained `count_final_scores`)
//! * the FLAT route: `decompose_into` + `leaf::flat_base_score`
//!
//! Run (release, niced):
//! ```text
//! nice -n 19 cargo run --release --example solver_component_bench \
//!     --manifest-path rust/carc/Cargo.toml -- <K> <N>
//! ```

use std::time::Instant;

use carc_core::engine::{GameState, Phase};
use carc_core::game::Game;
use carc_core::leaf::{decompose_into, flat_base_score, Decomp, Scratch};

fn endgame(seed: &str, k: usize) -> Option<Game> {
    let mut g = Game::from_seed(seed);
    let mut guard = 0;
    loop {
        guard += 1;
        if guard > 400 {
            return None;
        }
        let kr = g.state.deck_len() + usize::from(g.state.next_tile.is_some());
        if kr <= k && g.state.phase == Phase::Tiles {
            return Some(g);
        }
        let legal = g.legal_actions();
        if legal.is_empty() {
            return None;
        }
        if g.advance(legal[legal.len() / 2]).is_err() {
            return None;
        }
    }
}

/// Walk the sub-tree below `g` breadth-first (bounded), collecting the
/// (parent, action) pairs that lead to a terminal and those that do not — the
/// exact two transition classes the solver drives.
fn collect(g: &Game, term: &mut Vec<(Game, i32)>, nonterm: &mut Vec<(Game, i32)>, cap: usize) {
    let mut frontier = vec![g.clone()];
    while let Some(cur) = frontier.pop() {
        if term.len() >= cap && nonterm.len() >= cap {
            return;
        }
        for a in cur.legal_actions() {
            let mut nb = cur.clone();
            if nb.advance(a).is_err() {
                continue;
            }
            if nb.state.is_terminated() {
                if term.len() < cap {
                    term.push((cur.clone(), a));
                }
            } else {
                if nonterm.len() < cap {
                    nonterm.push((cur.clone(), a));
                }
                if frontier.len() < 64 {
                    frontier.push(nb);
                }
            }
        }
    }
}

fn bench<F: FnMut() -> u64>(label: &str, iters: usize, mut f: F) -> f64 {
    // one warm pass, then the timed pass
    let mut sink = 0u64;
    for _ in 0..(iters / 8).max(1) {
        sink = sink.wrapping_add(f());
    }
    let t = Instant::now();
    for _ in 0..iters {
        sink = sink.wrapping_add(f());
    }
    let ns = t.elapsed().as_secs_f64() / iters as f64 * 1e9;
    println!("  {label:<46} {ns:>10.0} ns   (sink {})", sink % 7);
    ns
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let k: usize = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(3);
    let n: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(6);

    let mut term: Vec<(Game, i32)> = Vec::new();
    let mut nonterm: Vec<(Game, i32)> = Vec::new();
    for i in 0..n {
        let seed = format!("{}", 4_000_000 + i as u64 * 7919);
        if let Some(g) = endgame(&seed, k) {
            collect(&g, &mut term, &mut nonterm, 40);
        }
    }
    println!("K={k}  terminal transitions={}  non-terminal={}", term.len(), nonterm.len());
    if term.is_empty() || nonterm.is_empty() {
        eprintln!("not enough samples");
        return;
    }

    // terminal STATES, for the two scorer routes
    let mut term_states: Vec<GameState> = Vec::new();
    for (p, a) in &term {
        let mut nb = p.clone();
        nb.advance(*a).unwrap();
        term_states.push(nb.state.clone());
    }

    let iters = 2000;
    let mut i = 0usize;

    println!("\nper-node components (solver drives one of each per node):");
    let ns_legal = bench("legal_actions (non-terminal node)", iters, || {
        i = (i + 1) % nonterm.len();
        nonterm[i].0.legal_actions().len() as u64
    });
    let ns_key = bench("string_repr + sha256 (TT key)", iters, || {
        i = (i + 1) % nonterm.len();
        nonterm[i].0.string_repr().len() as u64
    });
    let ns_adv_nt = bench("clone + advance  [NON-terminal]", iters, || {
        i = (i + 1) % nonterm.len();
        let mut nb = nonterm[i].0.clone();
        nb.advance(nonterm[i].1).unwrap();
        nb.state.scores[0] as u64
    });
    let ns_adv_t = bench("clone + advance  [TERMINAL: count_final_scores]", iters, || {
        i = (i + 1) % term.len();
        let mut nb = term[i].0.clone();
        nb.advance(term[i].1).unwrap();
        nb.state.scores[0] as u64
    });
    let ns_clone_only = bench("clone only (parent game)", iters, || {
        i = (i + 1) % term.len();
        let nb = term[i].0.clone();
        nb.state.scores[0] as u64
    });

    println!("\nterminal SCORER routes (on already-drained terminal states):");
    let ns_fbs = bench("GameState::flat_base_score (clone + cfs)", iters, || {
        i = (i + 1) % term_states.len();
        term_states[i].flat_base_score(0) as u64
    });
    let mut d = Decomp::default();
    let mut sc = Scratch::default();
    let ns_flat = bench("decompose_into + leaf::flat_base_score", iters, || {
        i = (i + 1) % term_states.len();
        decompose_into(&term_states[i], &mut d, &mut sc);
        flat_base_score(&term_states[i], 0, &d) as u64
    });

    // ---- the HONEST scorer A/B ------------------------------------------- //
    // The comparison above is unfair: `apply_action` has already DRAINED the
    // terminal state's meeples, so the flat route's `final_scores` walks an
    // empty meeple list while the incumbent's in-place `count_final_scores`
    // (inside the terminal advance, above) walked a full one.  Re-run both
    // routes on the PARENT states, which still carry every placed meeple —
    // that is the input the terminal scorer really sees.
    println!("\nscorer A/B on UN-drained late states (parents of terminals):");
    let parents: Vec<GameState> = term.iter().map(|(p, _)| p.state.clone()).collect();
    let ns_legacy_undrained = bench("legacy: clone + count_final_scores", iters, || {
        i = (i + 1) % parents.len();
        carc_core::tier1::candidate_leaf_legacy(&parents[i], 0) as u64
    });
    let ns_flat_undrained = bench("flat: decompose_into + flat_base_score", iters, || {
        i = (i + 1) % parents.len();
        decompose_into(&parents[i], &mut d, &mut sc);
        flat_base_score(&parents[i], 0, &d) as u64
    });
    let ns_decomp_only = bench("  ...of which decompose_into alone", iters, || {
        i = (i + 1) % parents.len();
        decompose_into(&parents[i], &mut d, &mut sc);
        d.ordinal(0, 0).unwrap_or(0) as u64
    });
    println!(
        "  SCORER FACTOR (legacy / flat) on un-drained states: {:.2}x",
        ns_legacy_undrained / ns_flat_undrained
    );
    println!("  ns_decomp_only={ns_decomp_only:.0}");
    let mut bad_p = 0;
    for s in &parents {
        decompose_into(s, &mut d, &mut sc);
        if carc_core::tier1::candidate_leaf_legacy(s, 0) != flat_base_score(s, 0, &d) {
            bad_p += 1;
        }
    }
    println!("  un-drained route equality: {}/{} match", parents.len() - bad_p, parents.len());

    println!("\nderived:");
    println!(
        "  terminal advance premium over non-terminal : {:.0} ns  ({:.2}x)",
        ns_adv_t - ns_adv_nt,
        ns_adv_t / ns_adv_nt
    );
    println!(
        "  engine flat_base_score / flat route        : {:.2}x",
        ns_fbs / ns_flat
    );
    println!(
        "  clone share of the non-terminal advance    : {:.0}%",
        ns_clone_only / ns_adv_nt * 100.0
    );
    println!(
        "  ns_legal={ns_legal:.0} ns_key={ns_key:.0} ns_adv_nt={ns_adv_nt:.0} \
         ns_adv_t={ns_adv_t:.0} ns_fbs={ns_fbs:.0} ns_flat={ns_flat:.0}"
    );

    // equality spot-check on every captured terminal state
    let mut bad = 0;
    for s in &term_states {
        decompose_into(s, &mut d, &mut sc);
        if s.flat_base_score(0) != flat_base_score(s, 0, &d) {
            bad += 1;
        }
    }
    println!("\nterminal-state route equality: {}/{} match", term_states.len() - bad, term_states.len());
}
