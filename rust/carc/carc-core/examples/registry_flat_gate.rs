//! **Registry flattening — bit-identity gates.**
//!
//! Compares the flattened `decompose_into` against the frozen object-registry
//! `decompose_into_ref` (`leaf::decomp::refimpl`) field-for-field over all 25
//! `Decomp` fields, plus a leaf-VALUE bit-identity arm over the same corpus.
//!
//! Gate shape (corpora, policies, seeds, the 25-field comparator) is lifted from
//! the L1 delta spike's `l1_spike.rs` so the two rounds' claims are comparable.
//!
//! Run (release, niced):
//! ```text
//! nice -n 19 cargo run --release --example registry_flat_gate \
//!     --manifest-path rust/carc/Cargo.toml
//! ```
//! Set `CARCASSONNE_FIX_R9=1` to gate the R9 farm-override registry instead
//! (the flag is process-global, so it needs a second process).
//!
//! Emits JSON on stdout, a human readout on stderr, and exits non-zero on any
//! gate failure.

use carc_core::game::Game;
use carc_core::leaf::decomp::{decomp_diff, decompose_into_ref, DECOMP_FIELDS};
use carc_core::leaf::{decompose_into, leaf_terms_with, Decomp, LeafConfig, Scratch};

struct Lcg(u64);
impl Lcg {
    fn next(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.0 >> 17
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() as usize) % n.max(1)
    }
}

struct Walker {
    d_new: Decomp,
    d_ref: Decomp,
    sc_new: Scratch,
    sc_ref: Scratch,
    cfg: LeafConfig,
}

impl Walker {
    fn new() -> Self {
        Walker {
            d_new: Decomp::default(),
            d_ref: Decomp::default(),
            sc_new: Scratch::default(),
            sc_ref: Scratch::default(),
            cfg: LeafConfig::curve125(),
        }
    }

    /// Walk one game, comparing at EVERY ply (tile and meeple phases alike).
    /// Returns `(positions, leaf_values, first_failure)`.
    fn walk(
        &mut self,
        seed: &str,
        mut pick: impl FnMut(usize) -> usize,
        max_ply: usize,
        check_leaf: bool,
    ) -> (usize, usize, Option<(usize, String)>) {
        let mut g = Game::from_seed(seed);
        let mut positions = 0usize;
        let mut values = 0usize;
        let mut ply = 0usize;
        while !g.is_terminal() && ply < max_ply {
            decompose_into(&g.state, &mut self.d_new, &mut self.sc_new);
            decompose_into_ref(&g.state, &mut self.d_ref, &mut self.sc_ref);
            positions += 1;
            if let Err(field) = decomp_diff(&self.d_new, &self.d_ref) {
                return (positions, values, Some((ply, format!("field={field}"))));
            }
            if check_leaf && g.state.players == 2 {
                for p in 0..2 {
                    let a = leaf_terms_with(&g.state, p, &self.cfg, &self.d_new);
                    let b = leaf_terms_with(&g.state, p, &self.cfg, &self.d_ref);
                    match (a, b) {
                        (Ok(a), Ok(b)) => {
                            values += 1;
                            if a.value != b.value
                                || a.score.to_bits() != b.score.to_bits()
                                || a.base != b.base
                                || a.bonus_self.to_bits() != b.bonus_self.to_bits()
                                || a.bonus_opp.to_bits() != b.bonus_opp.to_bits()
                                || a.meeple_term.to_bits() != b.meeple_term.to_bits()
                                || a.return_term.to_bits() != b.return_term.to_bits()
                                || a.flip_term.to_bits() != b.flip_term.to_bits()
                            {
                                return (
                                    positions,
                                    values,
                                    Some((ply, format!("leaf value pov={p}"))),
                                );
                            }
                        }
                        (Err(_), Err(_)) => {}
                        _ => {
                            return (positions, values, Some((ply, "leaf Ok/Err split".into())))
                        }
                    }
                }
            }
            let legal = g.legal_actions();
            if legal.is_empty() {
                break;
            }
            let a = legal[pick(legal.len())];
            g.advance(a).unwrap();
            ply += 1;
        }
        (positions, values, None)
    }
}

fn main() {
    let r9 = carc_core::tiles::r9_enabled();
    eprintln!("== registry flattening — bit-identity gates ==");
    eprintln!("registry: {}", if r9 { "R9 override ON" } else { "base (R9 off)" });
    eprintln!("Decomp fields compared per position: {DECOMP_FIELDS} (19 structural + 6 city root arrays)");

    let mut w = Walker::new();
    let mut json = String::from("{\n");
    json.push_str(&format!("  \"r9\": {r9},\n  \"decomp_fields\": {DECOMP_FIELDS},\n"));
    let mut ok = true;

    // -- G0: the empty board -------------------------------------------------
    {
        let g = Game::from_seed("1");
        let mut a = Decomp::default();
        let mut b = Decomp::default();
        let (mut sa, mut sb) = (Scratch::default(), Scratch::default());
        decompose_into(&g.state, &mut a, &mut sa);
        decompose_into_ref(&g.state, &mut b, &mut sb);
        let pass = decomp_diff(&a, &b).is_ok();
        ok &= pass;
        eprintln!("GATE 0 (fresh game / empty-ish board): {}", if pass { "PASS" } else { "FAIL" });
        json.push_str(&format!("  \"gate0_pass\": {pass},\n"));
    }

    // -- G1: deterministic corpus (6 seeds x 3 fixed policies) ---------------
    let mut g1_pos = 0usize;
    let mut g1_val = 0usize;
    let mut g1_fail: Option<String> = None;
    for seed in ["1", "2", "3", "17", "99", "12345678901234567890"] {
        for policy in 0..3usize {
            let pick = move |n: usize| match policy {
                0 => 0,
                1 => n / 2,
                _ => n - 1,
            };
            let (p, v, f) = w.walk(seed, pick, 400, true);
            g1_pos += p;
            g1_val += v;
            if let Some((ply, why)) = f {
                g1_fail = Some(format!("seed={seed} policy={policy} ply={ply} {why}"));
            }
        }
    }
    let g1_pass = g1_fail.is_none() && g1_pos >= 252;
    ok &= g1_pass;
    eprintln!(
        "GATE 1 (deterministic corpus): {g1_pos} positions, {g1_val} leaf values, {}",
        if g1_pass { "PASS" } else { "FAIL" }
    );
    if let Some(f) = &g1_fail {
        eprintln!("   {f}");
    }
    json.push_str(&format!(
        "  \"gate1_positions\": {g1_pos},\n  \"gate1_leaf_values\": {g1_val},\n  \"gate1_pass\": {g1_pass},\n"
    ));

    // -- G2: 500 randomized legal games, every ply, 25 fields + leaf values ---
    const N_GAMES: u64 = 500;
    let mut g2_pos = 0usize;
    let mut g2_val = 0usize;
    let mut g2_fail: Option<String> = None;
    for gi in 0..N_GAMES {
        let deck_seed = 700_000_000_000u64 + gi;
        let mut rng = Lcg(0x5eed_0000_0000_0000u64 ^ gi.wrapping_mul(0x9E3779B97F4A7C15));
        let (p, v, f) = w.walk(&format!("{deck_seed}"), |n| rng.below(n), 400, true);
        g2_pos += p;
        g2_val += v;
        if let Some((ply, why)) = f {
            g2_fail = Some(format!(
                "REPRO deck_seed={deck_seed} lcg_index={gi} ply={ply} {why}"
            ));
            break;
        }
    }
    let g2_pass = g2_fail.is_none();
    ok &= g2_pass;
    eprintln!(
        "GATE 2 ({N_GAMES} random games): {g2_pos} positions, {g2_val} leaf values, {}",
        if g2_pass { "PASS" } else { "FAIL" }
    );
    if let Some(f) = &g2_fail {
        eprintln!("   {f}");
    }
    json.push_str(&format!(
        "  \"gate2_games\": {N_GAMES},\n  \"gate2_positions\": {g2_pos},\n  \"gate2_leaf_values\": {g2_val},\n  \"gate2_pass\": {g2_pass},\n"
    ));

    json.push_str(&format!(
        "  \"total_positions\": {},\n  \"total_leaf_values\": {},\n  \"all_pass\": {ok}\n}}\n",
        g1_pos + g2_pos,
        g1_val + g2_val
    ));
    print!("{json}");
    eprintln!(
        "TOTAL: {} positions / {} leaf values / {}",
        g1_pos + g2_pos,
        g1_val + g2_val,
        if ok { "ALL PASS" } else { "FAILURE" }
    );
    if !ok {
        std::process::exit(1);
    }
}
