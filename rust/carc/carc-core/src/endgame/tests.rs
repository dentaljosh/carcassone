//! Unit gates for the deep exact-K endgame solver.
//!
//! These reproduce, in Rust, the checks `tests/test_endgame_solver.py` runs on
//! the Python oracle — V-brute (alpha-beta and the no-prune TT path both equal
//! an independent brute force), V2 (K=1 clairvoyant == K=1 marginalized), V9
//! (the value is realized by optimal play) and the regret sign law — plus the
//! anti-drift gate against the shipped [`crate::fair::solver`].

use super::*;
use crate::fair;

/// Drive a seeded game to the first TILES decision with `k_remaining <= k`.
///
/// The mover is the deterministic mid-index policy the other `carc-core` test
/// modules use, so the positions are reproducible without an RNG.
fn endgame(seed: &str, k: usize) -> Game {
    let mut g = Game::from_seed(seed);
    loop {
        let kr = g.state.deck_len() + usize::from(g.state.next_tile.is_some());
        if kr <= k && g.state.phase == crate::engine::Phase::Tiles {
            return g;
        }
        let legal = g.legal_actions();
        g.advance(legal[legal.len() / 2]).unwrap();
    }
}

fn cfg_ab(alphabeta: bool) -> Config {
    Config {
        budget: 5_000_000,
        alphabeta,
        ..Config::default()
    }
}

fn bits(v: f64) -> u64 {
    v.to_bits()
}

/// **V-brute** — the no-prune TT solver's clairvoyant answer equals an
/// independent brute force: `V*`, the optimal SET, and every child value.
#[test]
fn v_brute_clairvoyant_matches_the_brute_force() {
    for seed in ["11", "12", "13", "17"] {
        let g = endgame(seed, 2);
        let (vb, ob, cvb) = brute_clairvoyant_root(&g, 5_000_000).unwrap();
        let r = solve(&g, Mode::Clairvoyant, &cfg_ab(false)).unwrap();
        assert_eq!(bits(r.value), bits(vb), "seed {seed}");
        assert_eq!(r.optimal_actions, ob, "seed {seed}");
        assert_eq!(r.child_values.len(), cvb.len());
        for (&(a, v), &(ab, vbb)) in r.child_values.iter().zip(cvb.iter()) {
            assert_eq!(a, ab);
            assert_eq!(bits(v), bits(vbb), "seed {seed} action {a}");
        }
    }
}

/// **Alpha-beta is EXACT** — it only prunes provably-irrelevant subtrees, so at
/// the root (where every child is solved with a full window) it must return the
/// SAME value, the SAME optimal set and the SAME child values as both the
/// no-prune TT path and the brute force.  Only `nodes` may differ (fewer).
#[test]
fn alphabeta_equals_the_no_prune_path_and_the_brute_force() {
    for seed in ["11", "12", "13", "17"] {
        let g = endgame(seed, 2);
        let plain = solve(&g, Mode::Clairvoyant, &cfg_ab(false)).unwrap();
        let ab = solve(&g, Mode::Clairvoyant, &cfg_ab(true)).unwrap();
        let (vb, ob, _) = brute_clairvoyant_root(&g, 5_000_000).unwrap();
        assert_eq!(bits(ab.value), bits(plain.value), "seed {seed}");
        assert_eq!(bits(ab.value), bits(vb), "seed {seed}");
        assert_eq!(ab.optimal_actions, plain.optimal_actions, "seed {seed}");
        assert_eq!(ab.optimal_actions, ob, "seed {seed}");
        for (&(a, v), &(a2, v2)) in ab.child_values.iter().zip(plain.child_values.iter()) {
            assert_eq!(a, a2);
            assert_eq!(bits(v), bits(v2), "seed {seed} action {a}");
        }
        assert!(
            ab.nodes <= plain.nodes,
            "seed {seed}: pruning must not COST nodes ({} vs {})",
            ab.nodes,
            plain.nodes
        );
    }
}

/// **V2** — at K=1 there is no hidden future, so clairvoyant == marginalized
/// exactly (value, optimal set, every child value).
#[test]
fn v2_last_tile_clairvoyant_equals_marginalized() {
    for seed in ["11", "12", "13", "17", "23"] {
        let g = endgame(seed, 1);
        let rc = solve(&g, Mode::Clairvoyant, &Config::default()).unwrap();
        let rm = solve(&g, Mode::Marginalized, &Config::default()).unwrap();
        assert_eq!(bits(rc.value), bits(rm.value), "seed {seed}");
        assert_eq!(rc.optimal_actions, rm.optimal_actions, "seed {seed}");
        assert_eq!(rc.child_values.len(), rm.child_values.len());
        for (&(a, v), &(a2, v2)) in rc.child_values.iter().zip(rm.child_values.iter()) {
            assert_eq!(a, a2);
            assert_eq!(bits(v), bits(v2), "seed {seed} action {a}");
        }
    }
}

/// **V9** — playing solver-optimal moves for BOTH sides from the root reaches a
/// terminal whose real score differential equals `V*`.
#[test]
fn v9_the_value_is_realized_by_optimal_play() {
    for seed in ["11", "12", "17"] {
        let g = endgame(seed, 2);
        let root = solve(&g, Mode::Clairvoyant, &cfg_ab(true)).unwrap();
        let mut cur = g.clone();
        let mut guard = 0;
        while !cur.state.is_terminated() {
            guard += 1;
            assert!(guard < 40, "seed {seed}: runaway optimal-play walk");
            let r = solve(&cur, Mode::Clairvoyant, &cfg_ab(true)).unwrap();
            cur.advance(r.optimal_actions[0]).unwrap();
        }
        let final_diff = cur.flat_base_score(0) as f64;
        assert_eq!(bits(final_diff), bits(root.value), "seed {seed}");
    }
}

/// `regret_of >= 0` for every legal action, and exactly 0 for the optimal ones.
#[test]
fn regret_is_non_negative_and_zero_at_the_optimum() {
    let g = endgame("11", 2);
    let r = solve(&g, Mode::Clairvoyant, &cfg_ab(true)).unwrap();
    for &(a, _) in &r.child_values {
        let reg = r.regret_of(a).unwrap();
        assert!(reg >= -1e-9, "action {a} has negative regret {reg}");
        if r.optimal_actions.contains(&a) {
            assert!(reg.abs() < 1e-9, "optimal action {a} has regret {reg}");
        }
    }
    assert!(r.regret_of(-1).is_none());
}

/// **THE ANTI-DRIFT GATE (gate 4).**  Two independent transcriptions of one
/// Python file must not disagree: this module's marginalized mode is bit-equal
/// to the SHIPPED [`crate::fair::solver::solve_marginalized`] — value, optimal
/// set, every child value, and the node count (i.e. the search SHAPE) — on the
/// fair solver's own fixture seeds, at K=1 and K=2.
#[test]
fn marginalized_agrees_with_the_fair_solver() {
    for seed in ["11", "12", "13", "14", "17", "23"] {
        for k in [1usize, 2] {
            let g = endgame(seed, k);
            let mine = solve(&g, Mode::Marginalized, &Config::default()).unwrap();
            let theirs = fair::solver::solve_marginalized(
                &g,
                &fair::SolverConfig {
                    // The Python default for a bare `solve()` call; the fair
                    // agent ships 2_000_000, which only matters if it trips.
                    budget: 4_000_000,
                    ..fair::SolverConfig::default()
                },
            )
            .unwrap();
            assert_eq!(bits(mine.value), bits(theirs.value), "seed {seed} k{k}");
            assert_eq!(mine.to_move, theirs.to_move, "seed {seed} k{k}");
            assert_eq!(
                mine.optimal_actions, theirs.optimal_actions,
                "seed {seed} k{k}"
            );
            assert_eq!(mine.nodes, theirs.nodes, "seed {seed} k{k} node count");
            assert_eq!(mine.child_values.len(), theirs.child_values.len());
            for (&(a, v), &(a2, v2)) in mine.child_values.iter().zip(theirs.child_values.iter()) {
                assert_eq!(a, a2);
                assert_eq!(bits(v), bits(v2), "seed {seed} k{k} action {a}");
            }
        }
    }
}

/// The same drift gate one rung DEEPER, where the [`ChanceDrop`] quirk stops
/// being inert (the post-draw bag can hold two tiles of one type at K=3).
#[test]
fn marginalized_agrees_with_the_fair_solver_at_k3() {
    for seed in ["11", "17"] {
        let g = endgame(seed, 3);
        let mine = solve(&g, Mode::Marginalized, &Config::default()).unwrap();
        let theirs = fair::solver::solve_marginalized(
            &g,
            &fair::SolverConfig {
                budget: 4_000_000,
                ..fair::SolverConfig::default()
            },
        )
        .unwrap();
        assert_eq!(bits(mine.value), bits(theirs.value), "seed {seed}");
        assert_eq!(mine.optimal_actions, theirs.optimal_actions, "seed {seed}");
        assert_eq!(mine.nodes, theirs.nodes, "seed {seed}");
    }
}

/// Alpha-beta is refused for the marginalized mode (the Python `assert`).
#[test]
fn alphabeta_is_refused_for_the_marginalized_mode() {
    let g = endgame("11", 1);
    let e = solve(
        &g,
        Mode::Marginalized,
        &Config {
            alphabeta: true,
            ..Config::default()
        },
    );
    assert!(matches!(e, Err(SolveError::Engine(_))));
}

/// E1: the win objective is marginalized-only here (clairvoyant margin-max is
/// already win-optimal — outcome is a monotone transform of a deterministic
/// margin), and the marginalized win solve DELEGATES to the shipped fair
/// solver, so the two must agree field for field.
#[test]
fn win_objective_clairvoyant_is_refused_and_marginalized_delegates() {
    let g = endgame("11", 2);
    let win_cfg = Config {
        objective: Objective::Win,
        ..Config::default()
    };
    let e = solve(&g, Mode::Clairvoyant, &win_cfg);
    assert!(matches!(e, Err(SolveError::Engine(_))));

    for seed in ["11", "17"] {
        for k in [2usize, 3] {
            let g = endgame(seed, k);
            let mine = solve(&g, Mode::Marginalized, &win_cfg).unwrap();
            let theirs = fair::solver::solve_marginalized(
                &g,
                &fair::SolverConfig {
                    budget: 4_000_000,
                    objective: Objective::Win,
                    ..fair::SolverConfig::default()
                },
            )
            .unwrap();
            assert_eq!(bits(mine.value), bits(theirs.value), "seed {seed} k{k}");
            assert_eq!(mine.optimal_actions, theirs.optimal_actions, "seed {seed} k{k}");
            assert_eq!(mine.nodes, theirs.nodes, "seed {seed} k{k}");
            assert_eq!(
                mine.win_value.map(bits),
                theirs.win_value.map(bits),
                "seed {seed} k{k}"
            );
            assert_eq!(mine.child_win_values.len(), theirs.child_win_values.len());
        }
    }
}

/// A tiny budget raises `BudgetExceeded` on both paths.
#[test]
fn a_tiny_budget_raises_budget_exceeded() {
    let g = endgame("11", 2);
    for ab in [false, true] {
        let e = solve(
            &g,
            Mode::Clairvoyant,
            &Config {
                budget: 1,
                alphabeta: ab,
                ..Config::default()
            },
        );
        assert!(matches!(e, Err(SolveError::BudgetExceeded)), "ab={ab}");
    }
    let e = solve(
        &g,
        Mode::Marginalized,
        &Config {
            budget: 1,
            ..Config::default()
        },
    );
    assert!(matches!(e, Err(SolveError::BudgetExceeded)));
}

/// The TT cap is **correctness-neutral**: freezing the table can only cost
/// nodes, never change the answer.
#[test]
fn the_tt_cap_changes_nodes_but_not_the_answer() {
    let g = endgame("11", 2);
    for ab in [false, true] {
        let free = solve(
            &g,
            Mode::Clairvoyant,
            &Config {
                alphabeta: ab,
                ..cfg_ab(ab)
            },
        )
        .unwrap();
        let capped = solve(
            &g,
            Mode::Clairvoyant,
            &Config {
                tt_cap: 8,
                alphabeta: ab,
                ..cfg_ab(ab)
            },
        )
        .unwrap();
        assert_eq!(bits(capped.value), bits(free.value), "ab={ab}");
        assert_eq!(capped.optimal_actions, free.optimal_actions, "ab={ab}");
        assert!(capped.tt_entries <= 8, "ab={ab}: cap must bound the table");
        assert!(
            capped.nodes >= free.nodes,
            "ab={ab}: a frozen table can only cost nodes"
        );
    }
}

/// The marginalized TT key is deck-ORDER invariant and the clairvoyant one is
/// not — the property `deck_perm_invariance` exists to hold on the Python side.
///
/// Permuting the unseen deck must leave the marginalized value untouched (the
/// information set is the multiset) while the clairvoyant value is free to move
/// (it reads the real order).
#[test]
fn marginalized_is_deck_order_invariant() {
    for seed in ["11", "17"] {
        let g = endgame(seed, 2);
        let mut permuted = g.clone();
        let mut deck: Vec<u16> = permuted.state.remaining_deck().to_vec();
        deck.reverse();
        permuted.state.set_remaining_deck(&deck).unwrap();
        let a = solve(&g, Mode::Marginalized, &Config::default()).unwrap();
        let b = solve(&permuted, Mode::Marginalized, &Config::default()).unwrap();
        assert_eq!(bits(a.value), bits(b.value), "seed {seed}");
        assert_eq!(a.optimal_actions, b.optimal_actions, "seed {seed}");
    }
}

/// The clairvoyant mode reaches K=4 within the default budget, and alpha-beta
/// gets the same answer for strictly fewer nodes.
#[test]
fn k4_clairvoyant_solves_and_alphabeta_prunes() {
    let g = endgame("11", 4);
    let plain = solve(&g, Mode::Clairvoyant, &cfg_ab(false)).unwrap();
    let ab = solve(&g, Mode::Clairvoyant, &cfg_ab(true)).unwrap();
    assert_eq!(bits(ab.value), bits(plain.value));
    assert_eq!(ab.optimal_actions, plain.optimal_actions);
    assert!(
        ab.nodes < plain.nodes,
        "alpha-beta must prune at K=4 ({} vs {})",
        ab.nodes,
        plain.nodes
    );
}
