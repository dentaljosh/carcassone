//! `tier1_costprobe` — where the tie-arbiter's playout second actually goes.
//!
//! PROFILING ONLY. Nothing in `carc-core` is modified; this is an out-of-tree
//! crate that depends on it by path and re-implements the `tier1::tier1_playout`
//! decision loop as an INSTRUMENTED SHADOW, using only the crate's public API.
//!
//! The shadow is only trustworthy if it is the same player, so every shadow
//! playout is gated against the production `tier1::tier1_playout` on the same
//! (world, pick, seed): identical margin AND identical ply count. A single
//! mismatch aborts the run — a timing breakdown of a different player is worse
//! than no breakdown.
//!
//! Three passes over the SAME work:
//!   1. `baseline`  — the real `tier1::tier1_playout`, untouched. THE number.
//!   2. `shadow0`   — the shadow with all timing compiled out (const generic).
//!                    `shadow0 / baseline` is the shadow-fidelity ratio.
//!   3. `shadow1`   — the shadow with per-stage timers. `shadow1 / shadow0` is
//!                    the instrumentation tax; stage shares are renormalised
//!                    against `shadow1` and reported with that tax stated.
//!
//! Usage: tier1_costprobe <n_seeds> <plies_csv> <B> <mode:none|cache>

use std::time::Instant;

use carc_core::action_space::{decode, meeple_farmer_base, meeple_pass_index};
use carc_core::compat::mt19937::MT19937;
use carc_core::engine::Phase;
use carc_core::fair::reshuffled_determinization;
use carc_core::game::Game;
use carc_core::repr_key::string_representation;
use carc_core::tier1::tier1_playout;

use std::collections::HashMap;

// ---------------------------------------------------------------- allocator --
#[cfg(feature = "allocount")]
mod alloc_count {
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

    pub static ON: AtomicBool = AtomicBool::new(false);
    pub static N: AtomicU64 = AtomicU64::new(0);
    pub static BYTES: AtomicU64 = AtomicU64::new(0);

    pub struct Counting;
    unsafe impl GlobalAlloc for Counting {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 {
            if ON.load(Ordering::Relaxed) {
                N.fetch_add(1, Ordering::Relaxed);
                BYTES.fetch_add(l.size() as u64, Ordering::Relaxed);
            }
            System.alloc(l)
        }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) {
            System.dealloc(p, l)
        }
        unsafe fn realloc(&self, p: *mut u8, l: Layout, new: usize) -> *mut u8 {
            if ON.load(Ordering::Relaxed) {
                N.fetch_add(1, Ordering::Relaxed);
                BYTES.fetch_add(new as u64, Ordering::Relaxed);
            }
            System.realloc(p, l, new)
        }
    }
}
#[cfg(feature = "allocount")]
#[global_allocator]
static GA: alloc_count::Counting = alloc_count::Counting;

// ------------------------------------------------------------------ timings --
#[derive(Default, Clone)]
struct T {
    // per-ply
    repr_key: u128,      // string_representation for the memo key (cache mode)
    memo_lookup: u128,   // HashMap get / insert + Vec clone
    legal_mask: u128,    // Game::legal_mask()  == the window-mask rebuild
    legal_collect: u128, // scan the 2511-byte mask -> Vec<i32>
    filter: u128,        // Rule 3 / Rule 2 candidate filters (meeple phase)
    // per-candidate
    decode: u128,
    clone: u128, // GameState::clone
    apply: u128, // GameState::apply_action
    score: u128, // GameState::count_final_scores  (the "full-board rescore")
    // per-decision tail
    argmax: u128,
    rng: u128,
    // per-ply tail
    advance: u128,
    terminal: u128,
    total: u128,
}

impl T {
    fn sum_stages(&self) -> u128 {
        self.repr_key
            + self.memo_lookup
            + self.legal_mask
            + self.legal_collect
            + self.filter
            + self.decode
            + self.clone
            + self.apply
            + self.score
            + self.argmax
            + self.rng
            + self.advance
            + self.terminal
    }
}

#[derive(Default, Clone)]
struct C {
    playouts: u64,
    plies: u64,
    decisions: u64,
    rule1: u64,          // forced move, no candidate loop
    single_candidate: u64, // collapsed to one, no candidate loop
    candidates: u64,     // total per-candidate leaf evaluations
    mask_builds: u64,
    memo_hits: u64,
    memo_misses: u64,
}

macro_rules! tick {
    ($timed:expr, $t:expr, $last:expr, $f:ident) => {
        if $timed {
            let n = Instant::now();
            $t.$f += n.duration_since($last).as_nanos();
            $last = n;
        }
    };
}

// ------------------------------------------------------------------- shadow --
/// `tier1::legal_actions_checked` + `compute_legal_actions`, instrumented.
#[inline]
fn legal_checked<const TIMED: bool>(
    g: &Game,
    memo: Option<&mut HashMap<String, Vec<i32>>>,
    t: &mut T,
    c: &mut C,
    last: &mut Instant,
) -> Result<Vec<i32>, String> {
    match memo {
        None => {
            let m = g.legal_mask();
            c.mask_builds += 1;
            tick!(TIMED, t, *last, legal_mask);
            if m.n_total > 0 && m.n_overflow == m.n_total {
                return Err("window overflow".to_string());
            }
            let v: Vec<i32> = m
                .mask
                .iter()
                .enumerate()
                .filter(|(_, &b)| b != 0)
                .map(|(i, _)| i as i32)
                .collect();
            tick!(TIMED, t, *last, legal_collect);
            Ok(v)
        }
        Some(map) => {
            let key = string_representation(&g.state);
            tick!(TIMED, t, *last, repr_key);
            if let Some(hit) = map.get(&key) {
                let v = hit.clone();
                c.memo_hits += 1;
                tick!(TIMED, t, *last, memo_lookup);
                return Ok(v);
            }
            c.memo_misses += 1;
            tick!(TIMED, t, *last, memo_lookup);
            let m = g.legal_mask();
            c.mask_builds += 1;
            tick!(TIMED, t, *last, legal_mask);
            if m.n_total > 0 && m.n_overflow == m.n_total {
                return Err("window overflow".to_string());
            }
            let v: Vec<i32> = m
                .mask
                .iter()
                .enumerate()
                .filter(|(_, &b)| b != 0)
                .map(|(i, _)| i as i32)
                .collect();
            tick!(TIMED, t, *last, legal_collect);
            map.insert(key, v.clone());
            tick!(TIMED, t, *last, memo_lookup);
            Ok(v)
        }
    }
}

/// `RuleBasedPlayer::decide`, instrumented. Byte-for-byte the same control flow
/// and the same RNG consumption as `tier1.rs`.
#[allow(clippy::too_many_arguments)]
fn decide<const TIMED: bool>(
    g: &Game,
    rng: &mut MT19937,
    memo: Option<&mut HashMap<String, Vec<i32>>>,
    t: &mut T,
    c: &mut C,
    last: &mut Instant,
) -> Result<i32, String> {
    c.decisions += 1;
    let legal = legal_checked::<TIMED>(g, memo, t, c, last)?;
    if legal.is_empty() {
        return Err("no legal moves".to_string());
    }
    if legal.len() == 1 {
        c.rule1 += 1;
        return Ok(legal[0]);
    }
    let candidates: Vec<i32> = match g.state.phase {
        Phase::Tiles => legal.clone(),
        Phase::Meeples => {
            let w = g.window_size;
            let farmer_base = meeple_farmer_base(w);
            let pass_idx = meeple_pass_index(w);
            let cur = g.state.current_player;
            let meeples_in_hand = g.state.meeples[cur] as i64;
            let tiles_left = g.state.deck_len() as i64;
            let mut cand: Vec<i32> = legal.clone();
            let early = (tiles_left as f64) > 0.6 * (g.total_tiles as f64);
            if early {
                let nf: Vec<i32> = cand
                    .iter()
                    .copied()
                    .filter(|&a| !(farmer_base <= a && a < pass_idx))
                    .collect();
                if !nf.is_empty() {
                    cand = nf;
                }
            }
            if tiles_left <= meeples_in_hand {
                let np: Vec<i32> = cand.iter().copied().filter(|&a| a != pass_idx).collect();
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
    tick!(TIMED, t, *last, filter);

    let player = g.state.current_player;
    if candidates.len() == 1 {
        c.single_candidate += 1;
        return Ok(candidates[0]);
    }
    let opp = 1 - player;
    let ltc = g.state.last_tile_action.map(|lta| lta.coord);
    let mut scores: Vec<i64> = Vec::with_capacity(candidates.len());
    for &ai in &candidates {
        let action = decode(ai, &g.offset, g.state.phase, g.state.next_tile, ltc)
            .map_err(|e| format!("decode({ai}): {e:?}"))?;
        tick!(TIMED, t, *last, decode);
        let mut scratch = g.state.clone();
        tick!(TIMED, t, *last, clone);
        scratch.apply_action(action);
        tick!(TIMED, t, *last, apply);
        scratch.count_final_scores();
        tick!(TIMED, t, *last, score);
        scores.push(scratch.scores[player] - scratch.scores[opp]);
    }
    c.candidates += candidates.len() as u64;
    let best = *scores.iter().max().unwrap();
    let best_local: Vec<usize> = scores
        .iter()
        .enumerate()
        .filter(|&(_, &s)| s == best)
        .map(|(i, _)| i)
        .collect();
    tick!(TIMED, t, *last, argmax);
    let choice = rng.randbelow(best_local.len() as u64) as usize;
    tick!(TIMED, t, *last, rng);
    Ok(candidates[best_local[choice]])
}

/// `tier1::tier1_playout`, instrumented.
fn shadow_playout<const TIMED: bool>(
    world: &Game,
    pick: i32,
    root_player: usize,
    playout_seed: i64,
    max_plies: usize,
    mut memo: Option<&mut HashMap<String, Vec<i32>>>,
    t: &mut T,
    c: &mut C,
) -> Result<(f64, usize), String> {
    let t_start = Instant::now();
    let mut last = t_start;
    let mut g = world.clone();
    g.advance(pick)?;
    tick!(TIMED, t, last, advance);
    let mut rng = MT19937::from_py_int_seed_i64(playout_seed);
    let mut plies = 0usize;
    loop {
        let term = g.is_terminal();
        tick!(TIMED, t, last, terminal);
        if term {
            break;
        }
        if plies >= max_plies {
            return Err("max_plies".to_string());
        }
        let a = decide::<TIMED>(
            &g,
            &mut rng,
            memo.as_deref_mut(),
            t,
            c,
            &mut last,
        )?;
        g.advance(a)?;
        tick!(TIMED, t, last, advance);
        plies += 1;
    }
    c.playouts += 1;
    c.plies += plies as u64;
    t.total += t_start.elapsed().as_nanos();
    let opp = 1 - root_player;
    Ok((
        (g.state.scores[root_player] - g.state.scores[opp]) as f64,
        plies,
    ))
}

// -------------------------------------------------------------------- setup --
struct Job {
    seed: String,
    root_ply: usize,
    world: Game,
    picks: [i32; 2],
    seat: usize,
    playout_seed: i64,
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
    // land on a TILE decision with >= 2 arms, the shape the arbiter is called at
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

fn vmhwm_kb() -> u64 {
    std::fs::read_to_string("/proc/self/status")
        .unwrap_or_default()
        .lines()
        .find_map(|l| {
            l.strip_prefix("VmHWM:")
                .map(|r| r.trim().trim_end_matches(" kB").trim().parse().unwrap_or(0))
        })
        .unwrap_or(0)
}

const MAX_PLIES: usize = 400;

fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let n_seeds: usize = a.first().map(|s| s.parse().unwrap()).unwrap_or(6);
    let plies: Vec<usize> = a
        .get(1)
        .map(|s| s.split(',').map(|x| x.parse().unwrap()).collect())
        .unwrap_or_else(|| vec![10, 25, 40, 55, 70, 90]);
    let b: usize = a.get(2).map(|s| s.parse().unwrap()).unwrap_or(4);
    let mode = a.get(3).cloned().unwrap_or_else(|| "none".to_string());
    let use_memo = mode == "cache";

    // --- timer overhead ---------------------------------------------------
    let mut acc = 0u128;
    let t0 = Instant::now();
    let mut prev = t0;
    for _ in 0..200_000 {
        let n = Instant::now();
        acc += n.duration_since(prev).as_nanos();
        prev = n;
    }
    let timer_ns = t0.elapsed().as_nanos() as f64 / 200_000.0;
    std::hint::black_box(acc);

    // --- jobs -------------------------------------------------------------
    let mut jobs: Vec<Job> = Vec::new();
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
                let mut rng = MT19937::from_py_int_seed_i64(ws);
                let Ok(world) = reshuffled_determinization(&root, &mut rng) else {
                    continue;
                };
                jobs.push(Job {
                    seed: seed.clone(),
                    root_ply: p,
                    world,
                    picks: [legal[0], legal[legal.len() / 2]],
                    seat,
                    playout_seed: 500_000 + ws,
                });
            }
        }
    }
    eprintln!(
        "[probe] {} jobs x 2 arms = {} playouts, mode={mode}",
        jobs.len(),
        jobs.len() * 2
    );

    // --- pass 1: BASELINE (the real tier1_playout) ------------------------
    #[cfg(feature = "allocount")]
    {
        alloc_count::ON.store(true, std::sync::atomic::Ordering::Relaxed);
    }
    let mut per: Vec<(String, usize, usize, f64)> = Vec::new(); // seed, root_ply, plies, secs
    let mut truth: Vec<(f64, usize)> = Vec::new();
    let tb = Instant::now();
    for job in &jobs {
        let mut memo_stub = if use_memo {
            Some(carc_core::tier1::LegalMaskCache::new())
        } else {
            None
        };
        for &pick in &job.picks {
            let s = Instant::now();
            let (m, pl) = tier1_playout(
                &job.world,
                pick,
                job.seat,
                job.playout_seed,
                MAX_PLIES,
                memo_stub.as_mut(),
            )
            .expect("baseline playout failed");
            let secs = s.elapsed().as_secs_f64();
            per.push((job.seed.clone(), job.root_ply, pl, secs));
            truth.push((m, pl));
        }
    }
    let base_total = tb.elapsed().as_secs_f64();
    #[cfg(feature = "allocount")]
    let (alloc_n, alloc_bytes) = {
        alloc_count::ON.store(false, std::sync::atomic::Ordering::Relaxed);
        (
            alloc_count::N.load(std::sync::atomic::Ordering::Relaxed),
            alloc_count::BYTES.load(std::sync::atomic::Ordering::Relaxed),
        )
    };

    // --- pass 2: SHADOW, timing compiled out ------------------------------
    let mut t0s = T::default();
    let mut c0 = C::default();
    let mut k = 0usize;
    let mut mismatch = 0usize;
    let ts = Instant::now();
    for job in &jobs {
        let mut memo = if use_memo { Some(HashMap::new()) } else { None };
        for &pick in &job.picks {
            let (m, pl) = shadow_playout::<false>(
                &job.world,
                pick,
                job.seat,
                job.playout_seed,
                MAX_PLIES,
                memo.as_mut(),
                &mut t0s,
                &mut c0,
            )
            .expect("shadow playout failed");
            if (m, pl) != truth[k] {
                mismatch += 1;
            }
            k += 1;
        }
    }
    let shadow0_total = ts.elapsed().as_secs_f64();
    if mismatch > 0 {
        eprintln!("FATAL: shadow diverged from tier1_playout on {mismatch}/{k}");
        std::process::exit(3);
    }

    // --- pass 3: SHADOW, instrumented -------------------------------------
    let mut t1 = T::default();
    let mut c1 = C::default();
    let mut k = 0usize;
    let mut mismatch = 0usize;
    let ti = Instant::now();
    for job in &jobs {
        let mut memo = if use_memo { Some(HashMap::new()) } else { None };
        for &pick in &job.picks {
            let (m, pl) = shadow_playout::<true>(
                &job.world,
                pick,
                job.seat,
                job.playout_seed,
                MAX_PLIES,
                memo.as_mut(),
                &mut t1,
                &mut c1,
            )
            .expect("shadow playout failed");
            if (m, pl) != truth[k] {
                mismatch += 1;
            }
            k += 1;
        }
    }
    let shadow1_total = ti.elapsed().as_secs_f64();
    if mismatch > 0 {
        eprintln!("FATAL: instrumented shadow diverged on {mismatch}/{k}");
        std::process::exit(3);
    }

    // --- report -----------------------------------------------------------
    let np = c0.playouts as f64;
    let stages: Vec<(&str, u128)> = vec![
        ("repr_key", t1.repr_key),
        ("memo_lookup", t1.memo_lookup),
        ("legal_mask", t1.legal_mask),
        ("legal_collect", t1.legal_collect),
        ("filter", t1.filter),
        ("decode", t1.decode),
        ("clone", t1.clone),
        ("apply", t1.apply),
        ("score", t1.score),
        ("argmax", t1.argmax),
        ("rng", t1.rng),
        ("advance", t1.advance),
        ("terminal", t1.terminal),
    ];
    let measured = t1.sum_stages() as f64;
    let inner = t1.total as f64;
    let residual = inner - measured;

    println!("{{");
    println!("  \"artifact\": \"TIER1_COSTPROBE\",");
    println!("  \"mode\": \"{mode}\",");
    println!("  \"legal_mask_cache\": {},", use_memo);
    println!("  \"n_seeds\": {n_seeds}, \"B\": {b},");
    println!(
        "  \"root_plies\": [{}],",
        plies
            .iter()
            .map(|x| x.to_string())
            .collect::<Vec<_>>()
            .join(",")
    );
    println!("  \"n_playouts\": {},", c0.playouts);
    println!("  \"timer_now_ns\": {timer_ns:.2},");
    println!("  \"identity_gate\": {{\"checked\": {k}, \"mismatches\": 0, \"reference\": \"carc_core::tier1::tier1_playout\"}},");
    println!("  \"baseline_total_secs\": {base_total:.6},");
    println!(
        "  \"baseline_s_per_playout\": {:.6},",
        base_total / np
    );
    println!("  \"shadow_untimed_total_secs\": {shadow0_total:.6},");
    println!("  \"shadow_timed_total_secs\": {shadow1_total:.6},");
    println!(
        "  \"shadow_fidelity_ratio\": {:.4},",
        shadow0_total / base_total
    );
    println!(
        "  \"instrumentation_tax\": {:.4},",
        shadow1_total / shadow0_total
    );
    println!("  \"counters\": {{");
    println!("    \"plies\": {}, \"decisions\": {}, \"rule1\": {}, \"single_candidate\": {},", c0.plies, c0.decisions, c0.rule1, c0.single_candidate);
    println!("    \"candidate_evals\": {}, \"mask_builds\": {}, \"memo_hits\": {}, \"memo_misses\": {},", c0.candidates, c0.mask_builds, c0.memo_hits, c0.memo_misses);
    println!("    \"plies_per_playout\": {:.2},", c0.plies as f64 / np);
    println!("    \"candidates_per_scored_decision\": {:.3}", c0.candidates as f64 / (c0.decisions - c0.rule1 - c0.single_candidate).max(1) as f64);
    println!("  }},");
    println!("  \"stages_ns_total\": {{");
    for (i, (name, v)) in stages.iter().enumerate() {
        println!(
            "    \"{name}\": {{\"ns\": {v}, \"s_per_playout\": {:.6}, \"share_of_timed_inner\": {:.4}}}{}",
            *v as f64 / 1e9 / np,
            *v as f64 / inner,
            if i + 1 < stages.len() { "," } else { "" }
        );
    }
    println!("  }},");
    println!(
        "  \"residual\": {{\"ns\": {:.0}, \"s_per_playout\": {:.6}, \"share_of_timed_inner\": {:.4}}},",
        residual,
        residual / 1e9 / np,
        residual / inner
    );
    println!("  \"timed_inner_total_secs\": {:.6},", inner / 1e9);
    #[cfg(feature = "allocount")]
    println!(
        "  \"alloc_census_baseline\": {{\"n_allocs\": {alloc_n}, \"bytes\": {alloc_bytes}, \"allocs_per_playout\": {:.0}, \"bytes_per_playout\": {:.0}}},",
        alloc_n as f64 / np,
        alloc_bytes as f64 / np
    );
    println!("  \"vmhwm_kb\": {},", vmhwm_kb());
    println!("  \"per_playout\": [");
    for (i, (s, rp, pl, secs)) in per.iter().enumerate() {
        println!(
            "    {{\"seed\": \"{s}\", \"root_ply\": {rp}, \"plies\": {pl}, \"secs\": {secs:.6}}}{}",
            if i + 1 < per.len() { "," } else { "" }
        );
    }
    println!("  ]");
    println!("}}");
}
