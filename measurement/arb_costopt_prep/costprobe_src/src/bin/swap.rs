//! `swap` — the END-TO-END sizing of option B.
//!
//! PROFILING ONLY. `carc-core` is not modified.
//!
//! Runs each playout twice on the same (world, pick, seed):
//!   * `engine` — the shadow of `tier1::tier1_playout` exactly as deployed
//!     (`clone -> apply_action -> count_final_scores` per candidate);
//!   * `decomp` — the same loop with ONLY the per-candidate scorer replaced by
//!     `leaf::decompose_into` + `leaf::flat_base_score`, buffers reused.
//!
//! Both are gated against the production `tier1::tier1_playout` on (margin,
//! plies). If the swapped player ever plays a different game, the run aborts:
//! that is exactly the bit-identity gate the real change would have to pass.
//!
//! Usage: swap <n_seeds> <plies_csv> <B>

use std::time::Instant;

use carc_core::action_space::{decode, meeple_farmer_base, meeple_pass_index};
use carc_core::compat::mt19937::MT19937;
use carc_core::engine::Phase;
use carc_core::fair::reshuffled_determinization;
use carc_core::game::Game;
use carc_core::leaf::decomp::{decompose_into, Decomp, Scratch};
use carc_core::leaf::flat_base_score;
use carc_core::tier1::tier1_playout;

const MAX_PLIES: usize = 400;

struct Buf {
    d: Decomp,
    sc: Scratch,
}

fn decide(g: &Game, rng: &mut MT19937, decomp_route: bool, b: &mut Buf) -> Result<i32, String> {
    let m = g.legal_mask();
    if m.n_total > 0 && m.n_overflow == m.n_total {
        return Err("overflow".into());
    }
    let legal: Vec<i32> = m
        .mask
        .iter()
        .enumerate()
        .filter(|(_, &v)| v != 0)
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
    let mut scores: Vec<i64> = Vec::with_capacity(candidates.len());
    for &ai in &candidates {
        let action = decode(ai, &g.offset, g.state.phase, g.state.next_tile, ltc)
            .map_err(|e| format!("{e:?}"))?;
        let mut scratch = g.state.clone();
        scratch.apply_action(action);
        if decomp_route {
            decompose_into(&scratch, &mut b.d, &mut b.sc);
            scores.push(flat_base_score(&scratch, player, &b.d));
        } else {
            scratch.count_final_scores();
            scores.push(scratch.scores[player] - scratch.scores[opp]);
        }
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

fn playout(
    world: &Game,
    pick: i32,
    seat: usize,
    seed: i64,
    decomp_route: bool,
    b: &mut Buf,
) -> Result<(f64, usize), String> {
    let mut g = world.clone();
    g.advance(pick)?;
    let mut rng = MT19937::from_py_int_seed_i64(seed);
    let mut n = 0usize;
    while !g.is_terminal() {
        if n >= MAX_PLIES {
            return Err("max_plies".into());
        }
        let a = decide(&g, &mut rng, decomp_route, b)?;
        g.advance(a)?;
        n += 1;
    }
    let opp = 1 - seat;
    Ok(((g.state.scores[seat] - g.state.scores[opp]) as f64, n))
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

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let n_seeds: usize = a.first().map(|s| s.parse().unwrap()).unwrap_or(6);
    let plies: Vec<usize> = a
        .get(1)
        .map(|s| s.split(',').map(|x| x.parse().unwrap()).collect())
        .unwrap_or_else(|| vec![6, 22, 40, 60, 86, 100]);
    let b: usize = a.get(2).map(|s| s.parse().unwrap()).unwrap_or(3);

    struct J {
        root_ply: usize,
        world: Game,
        picks: [i32; 2],
        seat: usize,
        seed: i64,
    }
    let mut jobs: Vec<J> = Vec::new();
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
                let mut r = MT19937::from_py_int_seed_i64(ws);
                let Ok(world) = reshuffled_determinization(&root, &mut r) else { continue };
                jobs.push(J {
                    root_ply: p,
                    world,
                    picks: [legal[0], legal[legal.len() / 2]],
                    seat,
                    seed: 500_000 + ws,
                });
            }
        }
    }
    eprintln!("[swap] {} jobs x 2 arms = {} playouts", jobs.len(), jobs.len() * 2);

    let mut buf = Buf { d: Decomp::default(), sc: Scratch::default() };

    // ground truth (production)
    let mut truth: Vec<(f64, usize)> = Vec::new();
    for j in &jobs {
        for &p in &j.picks {
            truth.push(tier1_playout(&j.world, p, j.seat, j.seed, MAX_PLIES, None).unwrap());
        }
    }

    // engine-route shadow
    let mut mis_e = 0usize;
    let mut k = 0usize;
    let mut per_e: Vec<(usize, f64)> = Vec::new();
    let te = Instant::now();
    for j in &jobs {
        for &p in &j.picks {
            let s = Instant::now();
            let r = playout(&j.world, p, j.seat, j.seed, false, &mut buf).unwrap();
            per_e.push((j.root_ply, s.elapsed().as_secs_f64()));
            if r != truth[k] { mis_e += 1; }
            k += 1;
        }
    }
    let eng = te.elapsed().as_secs_f64();

    // decomp-route shadow
    let mut mis_d = 0usize;
    let mut k = 0usize;
    let mut per_d: Vec<(usize, f64)> = Vec::new();
    let td = Instant::now();
    for j in &jobs {
        for &p in &j.picks {
            let s = Instant::now();
            let r = playout(&j.world, p, j.seat, j.seed, true, &mut buf).unwrap();
            per_d.push((j.root_ply, s.elapsed().as_secs_f64()));
            if r != truth[k] { mis_d += 1; }
            k += 1;
        }
    }
    let dec = td.elapsed().as_secs_f64();

    let n = k as f64;
    println!("{{");
    println!("  \"artifact\": \"TIER1_SWAP_ENDTOEND\",");
    println!("  \"n_playouts\": {k},");
    println!("  \"identity_gate\": {{\"engine_shadow_mismatches\": {mis_e}, \"decomp_shadow_mismatches\": {mis_d}, \"reference\": \"carc_core::tier1::tier1_playout\", \"compared\": \"(margin, plies)\"}},");
    println!("  \"engine_route_s_per_playout\": {:.6},", eng / n);
    println!("  \"decomp_route_s_per_playout\": {:.6},", dec / n);
    println!("  \"end_to_end_speedup\": {:.4},", eng / dec);
    let mut ge: std::collections::BTreeMap<usize, (f64, f64, usize)> = Default::default();
    for (i, (rp, s)) in per_e.iter().enumerate() {
        let e = ge.entry(*rp).or_insert((0.0, 0.0, 0));
        e.0 += s;
        e.1 += per_d[i].1;
        e.2 += 1;
    }
    println!("  \"by_root_ply\": [");
    let last = *ge.keys().next_back().unwrap();
    for (rp, (se, sd, c)) in &ge {
        println!(
            "    {{\"root_ply\": {rp}, \"n\": {c}, \"engine_ms\": {:.3}, \"decomp_ms\": {:.3}, \"speedup\": {:.3}}}{}",
            se / *c as f64 * 1000.0,
            sd / *c as f64 * 1000.0,
            se / sd,
            if *rp == last { "" } else { "," }
        );
    }
    println!("  ]");
    println!("}}");
}
