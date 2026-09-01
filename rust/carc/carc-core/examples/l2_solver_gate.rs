//! **L2 — the fresh randomized bit-identity gate for the solver terminal-scorer swap.**
//!
//! Samples real late-game positions off seeded **tier-1 (`RuleBasedPlayer`)
//! playouts** — the same policy the champion's playout engine drives, so the
//! boards are the ones the exact-K latch really sees — then solves each position
//! TWICE from the same `Game`:
//!
//!   * **PRE**  — under `with_legacy_terminal_scorer`, i.e. scored
//!     `Game::advance` (in-place `count_final_scores`) + `GameState::flat_base_score`,
//!     which is the pre-L2 code path byte for byte;
//!   * **POST** — the shipped L2 route (`advance_unscored` + `decompose_into` +
//!     `leaf::flat_base_score` over thread-local buffers).
//!
//! Compared surfaces, all required equal:
//!   1. `value` as **raw f64 bits**
//!   2. the **full optimal-action set** (order included)
//!   3. **every child value's bits**, action by action
//!   4. `nodes` (the node count — the traversal must be untouched)
//!   5. `tt_entries` (the transposition table must be reached identically)
//!   6. `win_value` / `child_win_values` bits in the E1 win objective
//!
//! Both solver front doors are gated: `fair::solver::solve_marginalized` (the
//! SHIPPED exact-K latch) and `endgame::solve` in `Marginalized` and
//! `Clairvoyant`+alpha-beta modes (the measurement solver).
//!
//! Both arms run inside the SAME worker thread and the legs fan out across
//! `workers` threads, so the flat route's thread-local buffers are exercised
//! concurrently — the L0 threading-gate analogue, as by-catch.
//!
//! Run (release, niced):
//! ```text
//! nice -n 19 cargo run --release --example l2_solver_gate \
//!     --manifest-path rust/carc/Cargo.toml -- <N_K2> <N_K3> <WORKERS> <OUT.json>
//! ```

use std::time::Instant;

use carc_core::endgame::{Config as EgConfig, Mode};
use carc_core::engine::Phase;
use carc_core::fair::solver::{
    solve_marginalized, with_legacy_terminal_scorer, Objective, SolverConfig,
};
use carc_core::game::Game;
use carc_core::tier1::RuleBasedPlayer;

/// One sampled position: a real tier-1 late-game board at `k_remaining <= k`.
struct Pos {
    g: Game,
    seed: String,
    k: usize,
}

/// Drive a seeded tier-1 self-play game and capture the FIRST TILES decision at
/// each of `k_targets`, descending.
fn sample(seed_dec: &str, play_seed: i64, k_targets: &[usize], out: &mut Vec<Pos>) {
    let mut g = Game::from_seed(seed_dec);
    let mut p = RuleBasedPlayer::new(play_seed);
    let mut want: Vec<usize> = k_targets.to_vec();
    want.sort_unstable_by(|a, b| b.cmp(a)); // descending: 3, 2
    let mut guard = 0usize;
    while !g.is_terminal() && guard < 400 {
        guard += 1;
        let kr = g.state.deck_len() + usize::from(g.state.next_tile.is_some());
        if g.state.phase == Phase::Tiles {
            if let Some(&k) = want.first() {
                if kr <= k {
                    out.push(Pos {
                        g: g.clone(),
                        seed: seed_dec.to_string(),
                        k,
                    });
                    want.remove(0);
                    if want.is_empty() {
                        return;
                    }
                }
            }
        }
        let a = match p.choose_action(&g, None) {
            Ok(a) => a,
            Err(_) => return,
        };
        if g.advance(a).is_err() {
            return;
        }
    }
}

#[derive(Default)]
struct Tally {
    checks: usize,
    mismatches: Vec<String>,
    value_bits: usize,
    optimal_sets: usize,
    child_values: usize,
    nodes: usize,
    tt_entries: usize,
    win_bits: usize,
}

impl Tally {
    fn merge(&mut self, o: Tally) {
        self.checks += o.checks;
        self.value_bits += o.value_bits;
        self.optimal_sets += o.optimal_sets;
        self.child_values += o.child_values;
        self.nodes += o.nodes;
        self.tt_entries += o.tt_entries;
        self.win_bits += o.win_bits;
        self.mismatches.extend(o.mismatches);
    }

    fn cmp_result(
        &mut self,
        label: &str,
        pos: &Pos,
        pre: &carc_core::fair::solver::SolveResult,
        post: &carc_core::fair::solver::SolveResult,
    ) {
        self.checks += 1;
        let tag = format!("{label} seed={} k={}", pos.seed, pos.k);
        if pre.value.to_bits() != post.value.to_bits() {
            self.mismatches.push(format!(
                "{tag}: value bits {:#x} != {:#x}",
                pre.value.to_bits(),
                post.value.to_bits()
            ));
        } else {
            self.value_bits += 1;
        }
        if pre.optimal_actions != post.optimal_actions {
            self.mismatches.push(format!(
                "{tag}: optimal set {:?} != {:?}",
                pre.optimal_actions, post.optimal_actions
            ));
        } else {
            self.optimal_sets += 1;
        }
        let mut cv_ok = pre.child_values.len() == post.child_values.len();
        if cv_ok {
            for ((a1, v1), (a2, v2)) in pre.child_values.iter().zip(post.child_values.iter()) {
                if a1 != a2 || v1.to_bits() != v2.to_bits() {
                    cv_ok = false;
                    self.mismatches
                        .push(format!("{tag}: child {a1}/{a2} bits differ"));
                    break;
                }
            }
        } else {
            self.mismatches
                .push(format!("{tag}: child_values length differs"));
        }
        if cv_ok {
            self.child_values += 1;
        }
        if pre.nodes != post.nodes {
            self.mismatches
                .push(format!("{tag}: nodes {} != {}", pre.nodes, post.nodes));
        } else {
            self.nodes += 1;
        }
        if pre.tt_entries != post.tt_entries {
            self.mismatches.push(format!(
                "{tag}: tt_entries {} != {}",
                pre.tt_entries, post.tt_entries
            ));
        } else {
            self.tt_entries += 1;
        }
        let wv_ok = pre.win_value.map(f64::to_bits) == post.win_value.map(f64::to_bits)
            && pre.child_win_values.len() == post.child_win_values.len()
            && pre
                .child_win_values
                .iter()
                .zip(post.child_win_values.iter())
                .all(|((a1, v1), (a2, v2))| a1 == a2 && v1.to_bits() == v2.to_bits());
        if wv_ok {
            self.win_bits += 1;
        } else {
            self.mismatches.push(format!("{tag}: win payload differs"));
        }
    }
}

fn eg_to_fair(r: carc_core::endgame::SolveResult) -> carc_core::fair::solver::SolveResult {
    carc_core::fair::solver::SolveResult {
        value: r.value,
        to_move: r.to_move,
        optimal_actions: r.optimal_actions,
        child_values: r.child_values,
        nodes: r.nodes,
        win_value: r.win_value,
        child_win_values: r.child_win_values,
        tt_entries: r.tt_entries,
        wc_tiebreak: false,
    }
}

#[derive(Clone, Copy)]
enum Leg {
    FairMargin,
    FairWin,
    EgMarg,
    EgClairAb,
}

/// Compare one (pre, post) pair, folding both the both-Ok and the both-Err
/// cases in. A one-sided error is itself a mismatch.
fn pair<E: std::fmt::Display>(
    t: &mut Tally,
    label: &str,
    p: &Pos,
    pre: Result<carc_core::fair::solver::SolveResult, E>,
    post: Result<carc_core::fair::solver::SolveResult, E>,
) {
    match (pre, post) {
        (Ok(a), Ok(b)) => t.cmp_result(label, p, &a, &b),
        (Err(a), Err(b)) => {
            t.checks += 1;
            if a.to_string() != b.to_string() {
                t.mismatches.push(format!(
                    "{label} seed={} k={}: error {a} != {b}",
                    p.seed, p.k
                ));
            } else {
                // an identical refusal on both arms is agreement on every surface
                t.value_bits += 1;
                t.optimal_sets += 1;
                t.child_values += 1;
                t.nodes += 1;
                t.tt_entries += 1;
                t.win_bits += 1;
            }
        }
        (a, b) => {
            t.checks += 1;
            t.mismatches.push(format!(
                "{label} seed={} k={}: one arm errored (pre_err={}, post_err={})",
                p.seed,
                p.k,
                a.is_err(),
                b.is_err()
            ));
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    // N at the DEPLOYED latch depth (exact_max_k = 2), then a smaller
    // depth-stress leg at k=3 where the chance bag is genuinely mixed.
    let n_k2: usize = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(500);
    let n_k3: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(20);
    let workers: usize = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(14);
    let out_path = args.get(4).cloned();

    // ---- sample ---------------------------------------------------------- //
    let mut k2: Vec<Pos> = Vec::new();
    let mut k3: Vec<Pos> = Vec::new();
    let mut i = 0u64;
    while (k2.len() < n_k2 || k3.len() < n_k3) && i < 40_000 {
        let seed = format!("{}", 8_100_000_000u64 + i * 104_729);
        let mut got: Vec<Pos> = Vec::new();
        sample(&seed, 900_000 + i as i64, &[3usize, 2], &mut got);
        for p in got {
            if p.k == 2 && k2.len() < n_k2 {
                k2.push(p);
            } else if p.k == 3 && k3.len() < n_k3 {
                k3.push(p);
            }
        }
        i += 1;
    }
    eprintln!(
        "sampled from {i} seeded tier-1 games: k=2 -> {}, k=3 -> {}  (workers={workers})",
        k2.len(),
        k3.len()
    );

    let t0 = Instant::now();
    let margin = SolverConfig {
        budget: 4_000_000,
        ..SolverConfig::default()
    };
    let win = SolverConfig {
        objective: Objective::Win,
        budget: 4_000_000,
        ..SolverConfig::default()
    };
    let eg = EgConfig {
        budget: 4_000_000,
        ..EgConfig::default()
    };
    let eg_ab = EgConfig {
        budget: 4_000_000,
        alphabeta: true,
        ..EgConfig::default()
    };

    let run = |positions: &[Pos], legs: &[Leg]| -> Tally {
        if positions.is_empty() {
            return Tally::default();
        }
        let chunk = positions.len().div_ceil(workers.max(1)).max(1);
        let parts: Vec<Tally> = std::thread::scope(|sc| {
            let hs: Vec<_> = positions
                .chunks(chunk)
                .map(|ch| {
                    let (margin, win, eg, eg_ab) = (&margin, &win, &eg, &eg_ab);
                    sc.spawn(move || {
                        let mut t = Tally::default();
                        for p in ch {
                            for leg in legs {
                                match leg {
                                    Leg::FairMargin => {
                                        let pre = with_legacy_terminal_scorer(|| {
                                            solve_marginalized(&p.g, margin)
                                        });
                                        let post = solve_marginalized(&p.g, margin);
                                        pair(&mut t, "fair/margin", p, pre, post);
                                    }
                                    Leg::FairWin => {
                                        let pre = with_legacy_terminal_scorer(|| {
                                            solve_marginalized(&p.g, win)
                                        });
                                        let post = solve_marginalized(&p.g, win);
                                        pair(&mut t, "fair/win", p, pre, post);
                                    }
                                    Leg::EgMarg => {
                                        let pre = with_legacy_terminal_scorer(|| {
                                            carc_core::endgame::solve(&p.g, Mode::Marginalized, eg)
                                        });
                                        let post =
                                            carc_core::endgame::solve(&p.g, Mode::Marginalized, eg);
                                        pair(
                                            &mut t,
                                            "endgame/marg",
                                            p,
                                            pre.map(eg_to_fair),
                                            post.map(eg_to_fair),
                                        );
                                    }
                                    Leg::EgClairAb => {
                                        let pre = with_legacy_terminal_scorer(|| {
                                            carc_core::endgame::solve(
                                                &p.g,
                                                Mode::Clairvoyant,
                                                eg_ab,
                                            )
                                        });
                                        let post = carc_core::endgame::solve(
                                            &p.g,
                                            Mode::Clairvoyant,
                                            eg_ab,
                                        );
                                        pair(
                                            &mut t,
                                            "endgame/clair+ab",
                                            p,
                                            pre.map(eg_to_fair),
                                            post.map(eg_to_fair),
                                        );
                                    }
                                }
                            }
                        }
                        t
                    })
                })
                .collect();
            hs.into_iter().map(|h| h.join().unwrap()).collect()
        });
        let mut t = Tally::default();
        for p in parts {
            t.merge(p);
        }
        t
    };

    let mut total = Tally::default();
    let t_k2 = run(
        &k2,
        &[Leg::FairMargin, Leg::FairWin, Leg::EgMarg, Leg::EgClairAb],
    );
    eprintln!(
        "  k=2 legs done ({} checks, {} mismatches), {:.1}s",
        t_k2.checks,
        t_k2.mismatches.len(),
        t0.elapsed().as_secs_f64()
    );
    total.merge(t_k2);
    let t_k3 = run(&k3, &[Leg::FairMargin, Leg::FairWin]);
    eprintln!(
        "  k=3 legs done ({} checks, {} mismatches), {:.1}s",
        t_k3.checks,
        t_k3.mismatches.len(),
        t0.elapsed().as_secs_f64()
    );
    total.merge(t_k3);
    let t = total;
    let elapsed = t0.elapsed().as_secs_f64();

    let n_positions = k2.len() + k3.len();
    let by_k = format!("\"2\": {}, \"3\": {}", k2.len(), k3.len());
    let pass = t.mismatches.is_empty() && t.checks > 0;
    println!("\n=== L2 randomized bit-identity gate ===");
    println!(
        "positions      : {n_positions}  (k=2: {}, k=3: {})",
        k2.len(),
        k3.len()
    );
    println!("checks         : {}", t.checks);
    println!("value bits     : {}/{}", t.value_bits, t.checks);
    println!("optimal sets   : {}/{}", t.optimal_sets, t.checks);
    println!("child values   : {}/{}", t.child_values, t.checks);
    println!("node counts    : {}/{}", t.nodes, t.checks);
    println!("tt entries     : {}/{}", t.tt_entries, t.checks);
    println!("win payload    : {}/{}", t.win_bits, t.checks);
    println!("mismatches     : {}", t.mismatches.len());
    for m in t.mismatches.iter().take(20) {
        println!("   {m}");
    }
    println!("wall           : {elapsed:.1}s   workers: {workers}");
    println!("VERDICT        : {}", if pass { "PASS" } else { "FAIL" });

    if let Some(path) = out_path {
        let json = format!(
            "{{\n  \"gate\": \"L2/solver_terminal_scorer\",\n  \"positions\": {n_positions},\n  \
             \"by_k\": {{{by_k}}},\n  \"workers\": {workers},\n  \"checks\": {},\n  \
             \"value_bits\": {},\n  \"optimal_sets\": {},\n  \"child_values\": {},\n  \
             \"node_counts\": {},\n  \"tt_entries\": {},\n  \"win_payload\": {},\n  \
             \"n_mismatches\": {},\n  \"wall_secs\": {elapsed:.3},\n  \"verdict\": \"{}\"\n}}\n",
            t.checks,
            t.value_bits,
            t.optimal_sets,
            t.child_values,
            t.nodes,
            t.tt_entries,
            t.win_bits,
            t.mismatches.len(),
            if pass { "PASS" } else { "FAIL" }
        );
        std::fs::write(&path, json).expect("write gate json");
        eprintln!("wrote {path}");
    }
    if !pass {
        std::process::exit(1);
    }
}
