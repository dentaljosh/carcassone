//! `variant` — sizing the ONE lever the breakdown exposes.
//!
//! PROFILING ONLY. Nothing in `carc-core` is modified.
//!
//! The tier1 candidate loop scores every candidate as
//! `GameState::clone -> apply_action -> count_final_scores` (the engine route).
//! `carc-core` already ships a SECOND, gate-equal route to the same integer:
//! `leaf::decompose_into` (union-find, allocation-free after warm-up) +
//! `leaf::flat_base_score`. This binary runs BOTH on every candidate of a real
//! tier1 playout, asserts they return the same i64, and times them separately.
//!
//! The playout itself always follows the ENGINE route, so the trajectory is the
//! production one; the decomp route is a passenger.
//!
//! Usage: variant <n_seeds> <plies_csv> <B>

use std::time::Instant;

use carc_core::action_space::{decode, meeple_farmer_base, meeple_pass_index};
use carc_core::compat::mt19937::MT19937;
use carc_core::engine::Phase;
use carc_core::fair::reshuffled_determinization;
use carc_core::game::Game;
use carc_core::leaf::decomp::{decompose_into, Decomp, Scratch};
use carc_core::leaf::flat_base_score;

const MAX_PLIES: usize = 400;
const NB: usize = 6; // placed-tile buckets, 12 tiles wide

#[derive(Default)]
struct Acc {
    n: [u64; NB],
    clone_ns: [u128; NB],
    apply_ns: [u128; NB],
    cfs_ns: [u128; NB],      // engine route: count_final_scores
    decomp_ns: [u128; NB],   // decomp route: decompose_into
    fbs_ns: [u128; NB],      // decomp route: flat_base_score over the Decomp
    extra_clone_ns: [u128; NB],
    mismatches: u64,
    plies: u64,
    playouts: u64,
    decisions: u64,
}

fn bucket(placed: usize) -> usize {
    (placed / 13).min(NB - 1)
}

fn root_at(seed: &str, plies: usize) -> Option<Game> {
    let mut g = Game::from_seed(seed);
    for _ in 0..plies {
        let l = g.legal_actions();
        if l.is_empty() || g.is_terminal() {
            return None;
        }
        g.advance(l[l.len() / 2]).ok()?;
    }
    for _ in 0..40 {
        if g.is_terminal() {
            return None;
        }
        let l = g.legal_actions();
        if g.state.phase == Phase::Tiles && l.len() >= 2 {
            return Some(g);
        }
        if l.is_empty() {
            return None;
        }
        g.advance(l[l.len() / 2]).ok()?;
    }
    None
}

fn n_placed(g: &Game) -> usize {
    let mut n = 0;
    for r in 0..35 {
        for c in 0..35 {
            if g.state.board_direct(r, c).is_some() {
                n += 1;
            }
        }
    }
    n
}

#[allow(clippy::too_many_arguments)]
fn decide(
    g: &Game,
    rng: &mut MT19937,
    a: &mut Acc,
    d: &mut Decomp,
    sc: &mut Scratch,
    placed: usize,
) -> Result<i32, String> {
    a.decisions += 1;
    let m = g.legal_mask();
    if m.n_total > 0 && m.n_overflow == m.n_total {
        return Err("overflow".into());
    }
    let legal: Vec<i32> = m
        .mask
        .iter()
        .enumerate()
        .filter(|(_, &b)| b != 0)
        .map(|(i, _)| i as i32)
        .collect();
    if legal.is_empty() {
        return Err("no legal".into());
    }
    if legal.len() == 1 {
        return Ok(legal[0]);
    }
    let candidates: Vec<i32> = match g.state.phase {
        Phase::Tiles => legal.clone(),
        Phase::Meeples => {
            let w = g.window_size;
            let fb = meeple_farmer_base(w);
            let pi = meeple_pass_index(w);
            let cur = g.state.current_player;
            let hand = g.state.meeples[cur] as i64;
            let left = g.state.deck_len() as i64;
            let mut cand = legal.clone();
            if (left as f64) > 0.6 * (g.total_tiles as f64) {
                let nf: Vec<i32> = cand.iter().copied().filter(|&x| !(fb <= x && x < pi)).collect();
                if !nf.is_empty() {
                    cand = nf;
                }
            }
            if left <= hand {
                let np: Vec<i32> = cand.iter().copied().filter(|&x| x != pi).collect();
                if !np.is_empty() {
                    cand = np;
                }
            }
            if cand.is_empty() {
                cand = legal.clone();
            }
            cand
        }
    };
    let player = g.state.current_player;
    if candidates.len() == 1 {
        return Ok(candidates[0]);
    }
    let opp = 1 - player;
    let ltc = g.state.last_tile_action.map(|l| l.coord);
    let bi = bucket(placed);
    let mut scores: Vec<i64> = Vec::with_capacity(candidates.len());
    for &ai in &candidates {
        let action = decode(ai, &g.offset, g.state.phase, g.state.next_tile, ltc)
            .map_err(|e| format!("{e:?}"))?;
        let t0 = Instant::now();
        let mut scratch = g.state.clone();
        let t1 = Instant::now();
        scratch.apply_action(action);
        let t2 = Instant::now();

        // --- route B (decomp), non-mutating, buffers reused --------------
        decompose_into(&scratch, d, sc);
        let t3 = Instant::now();
        let sb = flat_base_score(&scratch, player, d);
        let t4 = Instant::now();

        // --- route A (engine, PRODUCTION) -------------------------------
        // count_final_scores mutates, so route A gets its own copy; that extra
        // clone is timed separately and is NOT part of the production cost.
        let mut s2 = scratch.clone();
        let t5 = Instant::now();
        s2.count_final_scores();
        let sa = s2.scores[player] - s2.scores[opp];
        let t6 = Instant::now();

        if sa != sb {
            a.mismatches += 1;
        }
        a.n[bi] += 1;
        a.clone_ns[bi] += t1.duration_since(t0).as_nanos();
        a.apply_ns[bi] += t2.duration_since(t1).as_nanos();
        a.decomp_ns[bi] += t3.duration_since(t2).as_nanos();
        a.fbs_ns[bi] += t4.duration_since(t3).as_nanos();
        a.extra_clone_ns[bi] += t5.duration_since(t4).as_nanos();
        a.cfs_ns[bi] += t6.duration_since(t5).as_nanos();
        scores.push(sa);
    }
    let best = *scores.iter().max().unwrap();
    let bl: Vec<usize> = scores
        .iter()
        .enumerate()
        .filter(|&(_, &s)| s == best)
        .map(|(i, _)| i)
        .collect();
    let ch = rng.randbelow(bl.len() as u64) as usize;
    Ok(candidates[bl[ch]])
}

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let n_seeds: usize = a.first().map(|s| s.parse().unwrap()).unwrap_or(4);
    let plies: Vec<usize> = a
        .get(1)
        .map(|s| s.split(',').map(|x| x.parse().unwrap()).collect())
        .unwrap_or_else(|| vec![10, 30, 50, 70]);
    let b: usize = a.get(2).map(|s| s.parse().unwrap()).unwrap_or(2);

    let mut acc = Acc::default();
    let mut d = Decomp::default();
    let mut sc = Scratch::default();

    for si in 0..n_seeds {
        let seed = format!("{}", 28_100_000_001u64 + si as u64 * 7_919);
        for &p in &plies {
            let Some(root) = root_at(&seed, p) else { continue };
            let legal = root.legal_actions();
            if legal.len() < 2 {
                continue;
            }
            let seat = root.state.current_player;
            for j in 0..b {
                let ws = 900_000 + (si as i64) * 1_000 + (p as i64) * 10 + j as i64;
                let mut rng0 = MT19937::from_py_int_seed_i64(ws);
                let Ok(world) = reshuffled_determinization(&root, &mut rng0) else {
                    continue;
                };
                for &pick in &[legal[0], legal[legal.len() / 2]] {
                    let mut g = world.clone();
                    if g.advance(pick).is_err() {
                        continue;
                    }
                    let mut rng = MT19937::from_py_int_seed_i64(500_000 + ws);
                    let mut plies_n = 0usize;
                    while !g.is_terminal() && plies_n < MAX_PLIES {
                        let placed = n_placed(&g);
                        let Ok(act) = decide(&g, &mut rng, &mut acc, &mut d, &mut sc, placed) else {
                            break;
                        };
                        if g.advance(act).is_err() {
                            break;
                        }
                        plies_n += 1;
                    }
                    acc.playouts += 1;
                    acc.plies += plies_n as u64;
                }
            }
        }
    }

    let tot: u64 = acc.n.iter().sum();
    let s = |v: &[u128; NB]| -> f64 { v.iter().sum::<u128>() as f64 / 1000.0 / tot as f64 };
    println!("{{");
    println!("  \"artifact\": \"TIER1_VARIANT_B_SIZING\",");
    println!("  \"n_seeds\": {n_seeds}, \"B\": {b},");
    println!("  \"playouts\": {}, \"plies\": {}, \"decisions\": {}, \"candidate_evals\": {tot},", acc.playouts, acc.plies, acc.decisions);
    println!("  \"identity_gate\": {{\"checked\": {tot}, \"mismatches\": {}, \"claim\": \"leaf::decompose_into+flat_base_score == clone+apply+count_final_scores\"}},", acc.mismatches);
    println!("  \"us_per_candidate\": {{");
    println!("    \"clone\": {:.3},", s(&acc.clone_ns));
    println!("    \"apply_action\": {:.3},", s(&acc.apply_ns));
    println!("    \"count_final_scores__ENGINE_ROUTE\": {:.3},", s(&acc.cfs_ns));
    println!("    \"decompose_into__DECOMP_ROUTE\": {:.3},", s(&acc.decomp_ns));
    println!("    \"flat_base_score__DECOMP_ROUTE\": {:.3},", s(&acc.fbs_ns));
    println!("    \"extra_clone_for_route_A_isolation_NOT_production\": {:.3}", s(&acc.extra_clone_ns));
    println!("  }},");
    let ea: f64 = acc.cfs_ns.iter().sum::<u128>() as f64;
    let eb: f64 = (acc.decomp_ns.iter().sum::<u128>() + acc.fbs_ns.iter().sum::<u128>()) as f64;
    println!("  \"scorer_speedup_engine_over_decomp\": {:.3},", ea / eb);
    println!("  \"buckets\": [");
    for i in 0..NB {
        if acc.n[i] == 0 {
            continue;
        }
        let n = acc.n[i] as f64;
        println!(
            "    {{\"placed_tiles\": \"{}-{}\", \"n\": {}, \"cfs_us\": {:.3}, \"decomp_us\": {:.3}, \"fbs_us\": {:.3}, \"clone_us\": {:.3}, \"apply_us\": {:.3}}}{}",
            i * 13,
            i * 13 + 12,
            acc.n[i],
            acc.cfs_ns[i] as f64 / 1000.0 / n,
            acc.decomp_ns[i] as f64 / 1000.0 / n,
            acc.fbs_ns[i] as f64 / 1000.0 / n,
            acc.clone_ns[i] as f64 / 1000.0 / n,
            acc.apply_ns[i] as f64 / 1000.0 / n,
            if i + 1 < NB && acc.n[i + 1] > 0 { "," } else { "" }
        );
    }
    println!("  ]");
    println!("}}");
}
