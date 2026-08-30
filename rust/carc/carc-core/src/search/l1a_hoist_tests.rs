//! L1a — THE MEEPLE-PHASE DECOMPOSITION HOIST: the correctness gates.
//!
//! The change is at [`super::Searcher::evaluate`]: when the expanding node is in
//! [`Phase::Meeples`], every child reuses the PARENT's [`Decomp`] instead of
//! running its own [`leaf::decompose_into`].
//!
//! ## Why it is bit-identical by construction
//!
//! `decompose_into` is a pure function of the TILE BOARD — it reads
//! `state.placed_coords` and `state.board`, and no meeple / score / phase /
//! deck field appears anywhere in its body. A node in `Phase::Meeples` has only
//! `Action::Meeple` and `Action::Pass` legal, and `GameState::apply_action`
//! routes both to code that never places a tile. So the child's decomposition
//! IS the parent's, byte for byte.
//!
//! ## The gates here
//!
//! | gate | what it refuses |
//! |---|---|
//! | [`every_meeple_phase_child_shares_its_parents_decomposition`] | the structural claim itself — `Decomp == Decomp`, parent vs child, over a corpus sized past the sweep's 3,104 |
//! | [`the_meeple_phase_hoist_is_leaf_value_identical`] | the consumed claim — hoisted vs fresh LEAF VALUE, raw f64 bits, over a randomized 200-game corpus |
//! | [`the_hoist_leaves_the_search_bit_identical`] | end to end — a whole `search_single` with the hoist on vs off ([`super::with_fresh_decomp`]), every result field compared as bits |
//! | [`a_tile_phase_child_generally_does_not_share_the_decomposition`] | the POSITIVE CONTROL — proves the gates above can fail |
//!
//! `bench_meeple_hoist` (`--ignored`) reads the realized factor.

use super::*;
use crate::engine::Phase;
use crate::leaf::{self, Decomp, LeafConfig, Scratch};

/// A reproducible action picker. Not `rand` — the corpus must be a constant of
/// the gate, re-derivable from this file alone.
struct Lcg(u64);
impl Lcg {
    fn new(seed: u64) -> Self {
        Lcg(seed.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407))
    }
    fn next_below(&mut self, n: usize) -> usize {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        ((self.0 >> 33) as usize) % n.max(1)
    }
}

/// Every position of one randomly-played game, visited in order.
fn walk_game(seed: u64, mut visit: impl FnMut(&Game)) {
    let mut g = Game::from_seed(&seed.to_string());
    let mut rng = Lcg::new(seed);
    let mut guard = 0usize;
    while !g.state.is_terminated() {
        guard += 1;
        assert!(guard < 400, "game {seed} did not terminate");
        visit(&g);
        let legal = g.legal_actions();
        assert!(!legal.is_empty(), "no legal action at a non-terminal state");
        let a = legal[rng.next_below(legal.len())];
        g.advance(a).unwrap();
    }
}

// ── GATE (a) — the structural claim ──────────────────────────────────────── //

/// The sweep's 3,104/3,104 result, regenerated in-tree.
///
/// The banked corpus lives only in the 2026-08-30 sweep's session artifacts, so
/// this rebuilds one from deck seeds and asserts past the same floor: **every**
/// meeple-phase child's decomposition equals its parent's, bit for bit.
#[test]
fn every_meeple_phase_child_shares_its_parents_decomposition() {
    let mut d_parent = Decomp::default();
    let mut d_child = Decomp::default();
    let mut sc = Scratch::default();
    let mut n_children = 0usize;
    let mut n_nodes = 0usize;
    let mut divergences = 0usize;

    for seed in 28_000_000_000u64..28_000_000_024 {
        walk_game(seed, |g| {
            if g.state.phase != Phase::Meeples {
                return;
            }
            n_nodes += 1;
            leaf::decompose_into(&g.state, &mut d_parent, &mut sc);
            for &a in &g.legal_actions() {
                let mut child = g.clone();
                child.advance(a).unwrap();
                leaf::decompose_into(&child.state, &mut d_child, &mut sc);
                n_children += 1;
                if d_child != d_parent {
                    divergences += 1;
                }
            }
        });
    }

    println!(
        "L1a gate (a): {n_children} meeple-phase children over {n_nodes} nodes, \
         {divergences} decomposition divergences"
    );
    assert!(
        n_children >= 3_104,
        "corpus too small to re-run the sweep's gate: {n_children} < 3104"
    );
    assert_eq!(divergences, 0, "a meeple-phase child changed the decomposition");
}

/// POSITIVE CONTROL for gate (a): the same comparison across a TILE placement
/// must FAIL, or gate (a) is vacuous (e.g. a botched `PartialEq`).
#[test]
fn a_tile_phase_child_generally_does_not_share_the_decomposition() {
    let mut d_parent = Decomp::default();
    let mut d_child = Decomp::default();
    let mut sc = Scratch::default();
    let mut n_placing = 0usize;
    let mut differed = 0usize;
    let mut n_pass = 0usize;
    let mut pass_shared = 0usize;

    for seed in 28_000_000_000u64..28_000_000_004 {
        walk_game(seed, |g| {
            if g.state.phase != Phase::Tiles {
                return;
            }
            leaf::decompose_into(&g.state, &mut d_parent, &mut sc);
            for &a in &g.legal_actions() {
                let mut child = g.clone();
                child.advance(a).unwrap();
                leaf::decompose_into(&child.state, &mut d_child, &mut sc);
                // A tile-phase `Pass` is the vendored unplaceable-tile discard:
                // it draws a new tile and places nothing, so it is the one
                // tile-phase action that DOES keep the decomposition. It is
                // only legal when no placement is, so it is never a sibling of
                // one — and the hoist is scoped to `Phase::Meeples`, so it is
                // out of scope either way. Partition on the board, not on the
                // action encoding.
                if child.state.placed_coords.len() == g.state.placed_coords.len() {
                    n_pass += 1;
                    if d_child == d_parent {
                        pass_shared += 1;
                    }
                    continue;
                }
                n_placing += 1;
                if d_child != d_parent {
                    differed += 1;
                }
            }
        });
    }
    println!(
        "L1a control: {differed}/{n_placing} tile-PLACING children changed the \
         decomposition; {pass_shared}/{n_pass} tile-phase passes kept it"
    );
    assert!(n_placing > 100, "control corpus too small");
    // A tile placement adds a cell to `placed`, so EVERY placing child must
    // differ — if any did not, `Decomp`'s `PartialEq` is not comparing what the
    // gates above assume it compares.
    assert_eq!(
        differed, n_placing,
        "a tile-PLACING child kept the parent's decomposition — the comparison is broken"
    );
    assert_eq!(pass_shared, n_pass, "a tile-phase pass moved the decomposition");
}

// ── GATE (b) — the consumed claim: LEAF VALUES ───────────────────────────── //

/// Hoisted vs fresh, over a randomized 200-game corpus, at every meeple-phase
/// leaf evaluation the search would perform.
///
/// Compares the raw f64 bits of the float leaf, the i64 int leaf, and the
/// `base` the J-rules prior surface consumes — the three numbers
/// `Searcher::evaluate` reads out of `LeafTerms`.
#[test]
fn the_meeple_phase_hoist_is_leaf_value_identical() {
    // The champion leaf of record — the same `SearchConfig::default()` carries.
    let cfg = LeafConfig::curve125();
    let mut d_parent = Decomp::default();
    let mut d_fresh = Decomp::default();
    let mut sc = Scratch::default();
    let mut n_values = 0usize;
    let mut mismatches = 0usize;

    for seed in 28_100_000_000u64..28_100_001_700 {
        walk_game(seed, |g| {
            if g.state.phase != Phase::Meeples {
                return;
            }
            let mover = g.state.current_player;
            // The parent decomposition the hoist keeps in the search scratch.
            leaf::decompose_into(&g.state, &mut d_parent, &mut sc);
            for &a in &g.legal_actions() {
                let mut child = g.clone();
                child.advance(a).unwrap();
                if child.state.players != 2 {
                    continue;
                }
                let hoisted = leaf::leaf_terms_with(&child.state, mover, &cfg, &d_parent).unwrap();
                leaf::decompose_into(&child.state, &mut d_fresh, &mut sc);
                let fresh = leaf::leaf_terms_with(&child.state, mover, &cfg, &d_fresh).unwrap();
                n_values += 1;
                if hoisted.score.to_bits() != fresh.score.to_bits()
                    || hoisted.value != fresh.value
                    || hoisted.base != fresh.base
                {
                    mismatches += 1;
                }
            }
        });
    }

    println!(
        "L1a gate (b): {n_values} meeple-phase leaf values (float bits + int + base), \
         {mismatches} mismatches"
    );
    // 1,700 games (the brief's floor is 200) — sized to clear the sweep's own
    // 231,942-leaf-value gate rather than merely its game count.
    assert!(
        n_values >= 231_942,
        "corpus below the sweep's 231,942-value scale: {n_values}"
    );
    assert_eq!(mismatches, 0, "the hoisted leaf value is not the fresh one");
}

// ── END TO END — the whole search ────────────────────────────────────────── //

fn result_bits(r: &SearchResult) -> Vec<u64> {
    let mut v = vec![r.chosen_action as u64, r.root_player as u64, r.root_n as u64];
    v.push(r.root_w.to_bits());
    v.push(r.root_leaf_value.to_bits());
    for set in [&r.root_children, &r.deduped, &r.pooled_stats] {
        v.push(set.len() as u64);
        for &(a, n, w) in set {
            v.push(a as u64);
            v.push(n as u64);
            v.push(w.to_bits());
        }
    }
    v.push(r.root_priors.len() as u64);
    for &(a, p) in &r.root_priors {
        v.push(a as u64);
        v.push(p.to_bits());
    }
    v
}

/// The hoist may not move ONE BIT of a search result — at dose 0 (the
/// champion), at a nonzero J-rules prior dose (where the hoisted decomposition
/// also feeds `jrules_prior_term`), under both `LeafQuantize` shapes, and with
/// `use_leaf_scratch` both on and off (the four routes the hoist's validity
/// argument has to cover).
#[test]
fn the_hoist_leaves_the_search_bit_identical() {
    let mut n_cases = 0usize;
    for (seed, plies) in [("28000000000", 40usize), ("42", 61), ("11", 96)] {
        let mut g = Game::from_seed(seed);
        let mut rng = Lcg::new(7);
        for _ in 0..plies {
            let legal = g.legal_actions();
            g.advance(legal[rng.next_below(legal.len())]).unwrap();
        }
        for use_scratch in [true, false] {
            for quantize in [LeafQuantize::Float, LeafQuantize::Int] {
                for dose in [0.0f64, 0.25] {
                    let cfg = SearchConfig {
                        simulations: 96,
                        use_leaf_scratch: use_scratch,
                        leaf_quantize: quantize,
                        jrules_prior_dose: dose,
                        ..SearchConfig::default()
                    };
                    let hoisted = search_single(&g, &cfg).unwrap();
                    let fresh = with_fresh_decomp(|| search_single(&g, &cfg)).unwrap();
                    assert_eq!(
                        result_bits(&hoisted),
                        result_bits(&fresh),
                        "hoist changed the search at seed={seed} plies={plies} \
                         scratch={use_scratch} quantize={quantize:?} dose={dose}"
                    );
                    n_cases += 1;
                }
            }
        }
    }
    println!("L1a end-to-end: {n_cases} search cases bit-identical hoisted vs fresh");
}

/// `with_fresh_decomp` restores the previous value, including on unwind — or
/// the end-to-end gate above silently grades hoist-vs-hoist from its second
/// case onward.
#[test]
fn the_fresh_decomp_scope_is_restored() {
    assert!(!force_fresh_decomp());
    with_fresh_decomp(|| assert!(force_fresh_decomp()));
    assert!(!force_fresh_decomp());
    let prev_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(|_| {})); // the unwind below is EXPECTED
    let caught = std::panic::catch_unwind(|| with_fresh_decomp(|| panic!("expected unwind")));
    std::panic::set_hook(prev_hook);
    assert!(caught.is_err());
    assert!(!force_fresh_decomp(), "the guard leaked after an unwind");
}

// ── BENCH ────────────────────────────────────────────────────────────────── //

/// The realized factor on a search slice — several roots at different plies
/// (the meeple/tile expansion mix, and so the size of the win, moves with the
/// ply), reps INTERLEAVED A/B/A/B so a drifting box biases both legs equally.
/// `--ignored`, release. Absolutes are only honest on an exclusive box; the
/// paired ratio survives shared tenancy.
#[test]
#[ignore]
fn bench_meeple_hoist() {
    use std::time::Instant;
    let cfg = SearchConfig {
        simulations: 1376,
        ..SearchConfig::default()
    };
    let warm = SearchConfig {
        simulations: 64,
        ..SearchConfig::default()
    };
    let reps = 8;
    println!("=== L1a meeple-phase hoist, {} sims x {reps} interleaved reps ===", cfg.simulations);
    let mut tot_fresh = 0.0f64;
    let mut tot_hoist = 0.0f64;
    for (seed, plies) in [("28000000000", 30usize), ("28000000000", 55), ("42", 80), ("11", 105)] {
        let mut g = Game::from_seed(seed);
        let mut rng = Lcg::new(7);
        for _ in 0..plies {
            let legal = g.legal_actions();
            g.advance(legal[rng.next_below(legal.len())]).unwrap();
        }
        let _ = with_fresh_decomp(|| search_single(&g, &warm)).unwrap();
        let _ = search_single(&g, &warm).unwrap();
        let mut t_fresh = 0.0f64;
        let mut t_hoist = 0.0f64;
        for _ in 0..reps {
            let t = Instant::now();
            with_fresh_decomp(|| search_single(&g, &cfg)).unwrap();
            t_fresh += t.elapsed().as_secs_f64();
            let t = Instant::now();
            search_single(&g, &cfg).unwrap();
            t_hoist += t.elapsed().as_secs_f64();
        }
        tot_fresh += t_fresh;
        tot_hoist += t_hoist;
        println!(
            "  seed={seed:>11} ply={plies:>3}: fresh {:7.2} ms  hoist {:7.2} ms  factor {:.4}x",
            t_fresh / reps as f64 * 1e3,
            t_hoist / reps as f64 * 1e3,
            t_fresh / t_hoist
        );
    }
    println!(
        "  POOLED                : fresh {:7.2} ms  hoist {:7.2} ms  FACTOR {:.4}x",
        tot_fresh / (4 * reps) as f64 * 1e3,
        tot_hoist / (4 * reps) as f64 * 1e3,
        tot_fresh / tot_hoist
    );
}
