//! `tiearb` — the RUNTIME chain-value tie detector and the terminal-grounded
//! tie ARBITER (tiearb2 Stage 2, Phase B).
//!
//! Pre-registration of record:
//! `measurement/tiearb2_stage2_20260817/DESIGN.md` §2 (the arbiter), §3 (the
//! firing rate), §4 (the inverted liveness gate), and
//! `measurement/tiearb2_stage2_20260817/READ_RULE.md` §2/§3 (the quantities the
//! instrument must emit).
//!
//! Everything here is ADDITIVE. Nothing pre-existing calls into this module,
//! and [`crate::fair::FairAgent`] reaches it only when
//! `SearchConfig::tiearb_enabled` is `true` — the knob-off path is the
//! pre-change code, byte for byte (the surface-C `root_allow` precedent).
//!
//! ## The predicate is the CORPUS predicate, ported
//!
//! `scripts/tiletie/chain_census.py` is the definition of record:
//!
//!   * [`chain_values`] ← `chain_census.chain_values` (itself copied verbatim
//!     from `jcz_mining/mine_disagreements.chain_values`): every legal TILE
//!     action's **outer chain value** = apply the tile, and if the successor is
//!     still the acting seat's turn take the BEST legal meeple continuation
//!     (ties to the LOWEST action index — ascending iteration, strict `>`);
//!     otherwise the chain is the tile alone. The leaf is always read from the
//!     ACTING seat's point of view, captured at the ROOT.
//!   * [`detect_tie`] ← `chain_census.tie_report`: membership at `eps` is
//!     `top1 - value <= eps`, and `eps = 0.0` reproduces the exact-tie case
//!     bit-for-bit because subtracting two bit-identical f64s is exactly
//!     `0.0 <= 0.0`. **DESIGN §2 fixes `eps = 0` — f64 EQUALITY, not a
//!     tolerance.**
//!   * [`build_arms`] ← `scripts/tiletie/build_positions.build_tie_arms` +
//!     `transposition_census.py`: the tie set, deduped by SUCCESSOR BOARD
//!     (`string_representation` of the TILE successor, before the meeple
//!     decision — the corpus keys it there because the tie is scored on the
//!     outer chain value), the lowest action of each transposition group
//!     surviving, then capped at `J` by a SEEDED DRAW (never index
//!     truncation), then the champion's own pick appended if it is not already
//!     represented.
//!
//! Two runtime-vs-corpus mismatches are PRE-REGISTERED in DESIGN §2.1 and are
//! not defects of this port: (i) the corpus predicate was evaluated on a
//! REPLAYED board at the champion's seat, here it runs inside a live search on
//! the candidate's own seat; (ii) the corpus `champ_picks` came from a FRESH
//! search and CL-070 showed reseeding alone flips picks. ⇒ the offline 22.96
//! tied tile plies/game ESTIMATES the runtime rate; it does not equal it.
//!
//! ## The playout, and the ONE deliberate deviation (flagged, not silent)
//!
//! The value of an arm is the Phase-A [`crate::tier1`] `tier1-greedy`
//! continuation to terminal, margin from the candidate's seat, averaged over
//! `B` CRN determinizations (DESIGN §2). The worlds are drawn ONCE per fired
//! ply and SHARED by every arm — that is the CRN and it is the whole point —
//! and each `(world, arm)` playout gets a fresh `RuleBasedPlayer` seeded from
//! the world's own playout seed, so the two arms of a comparison see the same
//! player stream as well as the same world (Stage 1b's `tier1_leg` contract).
//!
//! ⚠️ **DEVIATION, deliberate: the arbiter runs with the legal-mask memo OFF**
//! (`tier1_playout(.., cache = None)`), i.e. the HONEST mask.
//! [`crate::tier1::LegalMaskCache`] exists to reproduce
//! `game_wrapper.Game._legal_cache`'s non-injective key so the port could be
//! graded bit-identical against the BANKED Stage-1b records; it is a defect of
//! the python REPLAY HARNESS, not part of the `tier1-greedy` policy. Enabling
//! it at runtime would additionally make arm `k`'s playout depend on arms
//! `< k` through a shared memo — an ARM-ORDER SIDE CHANNEL, and arm 0 is the
//! privileged incumbent (the leaf's own tie-break), so the bias would not be
//! symmetric across arms. Phase A measured the cost of the honest mask at
//! `c` = 0.178857 vs 0.178232 worker-s/playout (**+0.35%**), so the choice is
//! not bought with a cost advantage. Both cells (`ARB` and `RND`) run the
//! identical code, so the mechanism statistic `D` is unaffected either way.
//!
//! ## `argmax` vs `random` must be WALL-CLOCK INDISTINGUISHABLE
//!
//! `RND` is the matched-wall-clock control and `D = M_arb - M_rnd` is the
//! mechanism statistic, so the two modes MUST cost the same. [`arbitrate`]
//! therefore runs the identical playout loop, computes the per-arm means AND
//! the argmax in BOTH modes, and differs only in which arm the last line
//! returns. `TiearbMode::Random` draws from its own RNG stream, seeded from the
//! same state digest, which consumes nothing from the playout work.

use std::collections::HashMap;

use crate::compat::mt19937::MT19937;
use crate::engine::Phase;
use crate::fair::reshuffled_determinization;
use crate::game::Game;
use crate::leaf::{LeafConfig, LeafScratch};
use crate::repr_key::string_representation;
use crate::sha256::sha256_bytes;
use crate::tier1::tier1_playout;

/// The salt of record (DESIGN §2). Any other value is a different experiment.
pub const TIEARB_SALT_OF_RECORD: &str = "tiearb2-deploy-v1";

/// Playout ply ceiling. A full 2-player base game is ~144 plies (72 tiles x
/// tile+meeple); the same 400 the Phase-A tests use, i.e. a guard, never a
/// truncation (a truncated playout would ERROR, never score — DESIGN's
/// terminal-grounding estimand forbids a non-terminal value).
pub const TIEARB_MAX_PLIES: usize = 400;

/// `ARB` takes the argmax of the world-mean playout value; `RND` runs the
/// identical playouts, DISCARDS the values, and draws an arm from a seeded RNG.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TiearbMode {
    Argmax,
    Random,
}

impl TiearbMode {
    pub fn parse(s: &str) -> Result<Self, String> {
        match s {
            "argmax" => Ok(TiearbMode::Argmax),
            "random" => Ok(TiearbMode::Random),
            other => Err(format!(
                "tiearb_mode must be 'argmax'|'random'; got {other:?}"
            )),
        }
    }

    pub fn value(&self) -> &'static str {
        match self {
            TiearbMode::Argmax => "argmax",
            TiearbMode::Random => "random",
        }
    }
}

/// One legal tile action's OUTER CHAIN value.
#[derive(Clone, Debug)]
pub struct ChainValue {
    pub action: i32,
    /// The chain value: tile + its best meeple continuation, or the tile alone
    /// when the successor hands the turn over.
    pub value: f64,
    /// The meeple action the chain took, when there was one.
    pub meeple: Option<i32>,
}

/// `chain_census.chain_values`, specialised to the TILE instrument.
///
/// `seat` is the ACTING seat at the root and the leaf is always read from it —
/// including inside the meeple continuation, where the state's own
/// `current_player` may already have moved on.
///
/// Cost is `Sum_a (1 + n_meeple(a))` leaf calls; on a `k8 x 1376 = 11,008`-sim
/// decision that is noise.
pub fn chain_values(
    g: &Game,
    seat: usize,
    cfg: &LeafConfig,
    scratch: &mut LeafScratch,
) -> Result<Vec<ChainValue>, String> {
    let mut out = Vec::new();
    for a in g.legal_actions() {
        let mut g1 = g.clone();
        g1.advance(a)?;
        if g1.state.current_player == seat {
            let legal2 = g1.legal_actions();
            if !legal2.is_empty() {
                let mut best_v: Option<f64> = None;
                let mut best_m: Option<i32> = None;
                // ascending -> the LOWEST action index wins ties (strict `>`).
                for m in legal2 {
                    let mut g2 = g1.clone();
                    g2.advance(m)?;
                    let v = scratch
                        .leaf_value_float(&g2.state, seat, cfg)
                        .map_err(|e| format!("leaf failed on meeple {m}: {e:?}"))?;
                    if best_v.is_none() || v > best_v.unwrap() {
                        best_v = Some(v);
                        best_m = Some(m);
                    }
                }
                out.push(ChainValue {
                    action: a,
                    value: best_v.expect("legal2 non-empty"),
                    meeple: best_m,
                });
                continue;
            }
        }
        let v = scratch
            .leaf_value_float(&g1.state, seat, cfg)
            .map_err(|e| format!("leaf failed on tile {a}: {e:?}"))?;
        out.push(ChainValue {
            action: a,
            value: v,
            meeple: None,
        });
    }
    Ok(out)
}

/// The exact-tie structure of a `chain_values` output — `chain_census.tie_report`
/// reduced to what the trigger needs.
#[derive(Clone, Debug)]
pub struct TieDetection {
    /// Ascending, `len >= 2` by construction.
    pub tie_actions: Vec<i32>,
    pub top1: f64,
    pub n_cand: usize,
}

/// DESIGN §2 trigger clause 3. `eps = 0.0` is EXACT f64 equality (the membership
/// test `top1 - v <= eps` degenerates to `0.0 <= 0.0`), which is the committed
/// setting; the parameter exists so the manifest can prove it was 0.
pub fn detect_tie(values: &[ChainValue], eps: f64) -> Option<TieDetection> {
    if values.len() < 2 {
        return None;
    }
    let mut top1 = values[0].value;
    for cv in &values[1..] {
        if cv.value > top1 {
            top1 = cv.value;
        }
    }
    let tie_actions: Vec<i32> = values
        .iter()
        .filter(|cv| (top1 - cv.value) <= eps)
        .map(|cv| cv.action)
        .collect();
    if tie_actions.len() < 2 {
        return None;
    }
    Some(TieDetection {
        tie_actions,
        top1,
        n_cand: values.len(),
    })
}

/// The arm set for one fired ply.
#[derive(Clone, Debug)]
pub struct ArmSet {
    /// `arms[0]` is the leaf's own tie-break of record (`min(tie_actions)`,
    /// invariant under the dedupe by construction).
    pub arms: Vec<i32>,
    /// The tie set collapsed to one action per distinct successor board.
    pub n_distinct_afterstates: usize,
    /// The whole tie set reaches ONE board — the leaf had nothing to
    /// discriminate and the "tie" is correct by construction.
    pub all_transposition: bool,
    /// The `J` cap dropped at least one deduped candidate.
    pub capped: bool,
    /// The champion's own pick was outside the capped set and was appended.
    pub champ_appended: bool,
}

/// Ports `build_positions.build_tie_arms` (+ its `--afterstate-map` dedupe) and
/// `resolve_champion_arm`'s step 3, with the corpus's `rid` replaced by the
/// runtime analogue `(state_digest, ply)`.
///
/// The cap is a SEEDED DRAW over the deduped candidates — never index
/// truncation (DESIGN §2, and `build_tie_arms`'s `rng.sample`). The draw is a
/// seeded permutation prefix, which is the same uniform-without-replacement
/// distribution `random.sample` yields; it is NOT stream-identical to CPython's
/// `sample`, and it does not need to be — the corpus cap and the runtime cap
/// are two different draws over two different populations by construction
/// (DESIGN §2.1).
pub fn build_arms(
    g: &Game,
    tie_actions: &[i32],
    j: usize,
    champ_pick: Option<i32>,
    salt: &str,
    digest: &str,
    ply: i64,
) -> Result<ArmSet, String> {
    // --- dedupe by SUCCESSOR BOARD (the TILE successor, before the meeple).
    let mut by_key: HashMap<String, Vec<i32>> = HashMap::new();
    let mut order: Vec<String> = Vec::new();
    let mut key_of: HashMap<i32, String> = HashMap::new();
    for &a in tie_actions {
        let mut g1 = g.clone();
        g1.advance(a)?;
        let k = string_representation(&g1.state);
        key_of.insert(a, k.clone());
        if !by_key.contains_key(&k) {
            order.push(k.clone());
            by_key.insert(k.clone(), Vec::new());
        }
        by_key.get_mut(&k).unwrap().push(a);
    }
    let mut groups: Vec<Vec<i32>> = order
        .iter()
        .map(|k| {
            let mut v = by_key[k].clone();
            v.sort_unstable();
            v
        })
        .collect();
    groups.sort_by_key(|v| v[0]);
    let kept: Vec<i32> = groups.iter().map(|v| v[0]).collect();
    let n_distinct = kept.len();
    let all_transposition = n_distinct == 1;

    let reference = kept[0];
    let mut candidates: Vec<i32> = kept[1..].to_vec();
    let cap = j.max(1);
    let mut capped = false;
    if candidates.len() > cap - 1 {
        let seed = seed_i64(&[salt, digest, &ply.to_string(), "cap"]);
        let mut rng = MT19937::from_py_int_seed_i64(seed);
        let perm = rng.shuffle_range(candidates.len());
        let mut chosen: Vec<i32> = perm
            .iter()
            .take(cap - 1)
            .map(|&i| candidates[i as usize])
            .collect();
        chosen.sort_unstable();
        candidates = chosen;
        capped = true;
    }
    let mut arms = vec![reference];
    arms.extend(candidates);

    // --- step 3: the champion's own pick. Appended unless an arm already
    // reaches the SAME successor board (a transposition duplicate would be a
    // known-zero arm — `resolve_champion_arm`'s `repr_of` rule).
    // `None` = a census read with no champion pick to append; the deployed
    // arbiter always passes `Some(pooled_q_argmax(..))`.
    let mut champ_appended = false;
    if let Some(cp) = champ_pick {
        if !arms.contains(&cp) {
            let ck = match key_of.get(&cp) {
                Some(k) => k.clone(),
                None => {
                    // The champion's pick is OUTSIDE the tie set (it is free to
                    // be: the pooled PUCT argmax is not the leaf's argmax). Key
                    // it the same way so the duplicate test is the same test.
                    let mut g1 = g.clone();
                    g1.advance(cp)?;
                    string_representation(&g1.state)
                }
            };
            let dup = arms.iter().any(|a| key_of.get(a) == Some(&ck));
            if !dup {
                arms.push(cp);
                champ_appended = true;
            }
        }
    }

    Ok(ArmSet {
        arms,
        n_distinct_afterstates: n_distinct,
        all_transposition,
        capped,
        champ_appended,
    })
}

/// `sha256(part_0 | part_1 | ...)` -> a non-negative i64 seed. The DESIGN's
/// `sha256("tiearb2-deploy-v1" | state_digest | ply | j)`, with the same
/// `"|"`-join discipline `build_positions._stable_seed` uses (never
/// `random.Random(<tuple>)`, whose hash is per-process salted).
pub fn seed_i64(parts: &[&str]) -> i64 {
    let joined = parts.join("|");
    let h = sha256_bytes(joined.as_bytes());
    let mut b = [0u8; 8];
    b.copy_from_slice(&h[..8]);
    (u64::from_be_bytes(b) & 0x7FFF_FFFF_FFFF_FFFF) as i64
}

/// One fired ply's arbitration.
#[derive(Clone, Debug)]
pub struct ArbOutcome {
    pub arms: Vec<i32>,
    /// Mean margin (candidate's seat) over the `B` CRN worlds, per arm.
    pub means: Vec<f64>,
    /// The argmax arm. Computed in BOTH modes (the wall-clock contract).
    pub argmax_arm: i32,
    /// The arm actually returned: the argmax under `Argmax`, the seeded draw
    /// under `Random`.
    pub chosen: i32,
    pub n_playouts: usize,
}

/// DESIGN §2's arbiter: `B` CRN determinizations SHARED by every arm, a
/// `tier1-greedy` playout to terminal per `(world, arm)`, margin from `seat`,
/// mean over worlds.
///
/// ⚠️ Both modes execute the identical work — the same worlds, the same
/// playouts, the same means, the same argmax. Only the returned arm differs.
#[allow(clippy::too_many_arguments)]
pub fn arbitrate(
    g: &Game,
    seat: usize,
    arms: &[i32],
    b: usize,
    salt: &str,
    digest: &str,
    ply: i64,
    mode: TiearbMode,
) -> Result<ArbOutcome, String> {
    if arms.is_empty() {
        return Err("arbitrate called with an empty arm set".to_string());
    }
    let mut sums = vec![0.0f64; arms.len()];
    let mut n_playouts = 0usize;
    for j in 0..b {
        let js = j.to_string();
        let world_seed = seed_i64(&[salt, digest, &ply.to_string(), &js]);
        let playout_seed = seed_i64(&[salt, digest, &ply.to_string(), &js, "playout"]);
        let mut rng = MT19937::from_py_int_seed_i64(world_seed);
        let world = reshuffled_determinization(g, &mut rng)?;
        for (i, &a) in arms.iter().enumerate() {
            // cache = None: the HONEST legal mask. See the module docs — the
            // memo is a python-replay-harness defect and would leak an
            // arm-order side channel into a CRN comparison.
            let (margin, _plies) =
                tier1_playout(&world, a, seat, playout_seed, TIEARB_MAX_PLIES, None)?;
            sums[i] += margin;
            n_playouts += 1;
        }
    }
    let denom = b.max(1) as f64;
    let means: Vec<f64> = sums.iter().map(|s| s / denom).collect();
    // argmax with strict `>` over the arm order, so a tie keeps the EARLIEST
    // arm — i.e. the incumbent leaf tie-break at `arms[0]`. Computed in both
    // modes so the two are wall-clock indistinguishable up to this line.
    let mut best = 0usize;
    for i in 1..arms.len() {
        if means[i] > means[best] {
            best = i;
        }
    }
    let argmax_arm = arms[best];
    let chosen = match mode {
        TiearbMode::Argmax => argmax_arm,
        TiearbMode::Random => {
            // Its OWN stream, seeded from the same state digest: reproducible
            // in replay, and it consumes nothing from the playout work.
            let mut rng =
                MT19937::from_py_int_seed_i64(seed_i64(&[salt, digest, &ply.to_string(), "select"]));
            arms[rng.randbelow(arms.len() as u64) as usize]
        }
    };
    Ok(ArbOutcome {
        arms: arms.to_vec(),
        means,
        argmax_arm,
        chosen,
        n_playouts,
    })
}

/// The whole trigger + arbitration for ONE decision, or `None` when the trigger
/// does not fire. `champ_pick` is the champion's own `pooled_q_argmax` pick.
///
/// Trigger (DESIGN §2): phase == TILES, the candidate's own seat, `n_legal >= 2`,
/// and at least two legal tile actions sharing the top OUTER CHAIN value at
/// `eps` (0 == exact f64 equality).
#[allow(clippy::too_many_arguments)]
pub fn arbitrate_decision(
    g: &Game,
    champ_pick: i32,
    leaf_cfg: &LeafConfig,
    b: usize,
    j: usize,
    salt: &str,
    eps: f64,
    ply: i64,
    mode: TiearbMode,
    scratch: &mut LeafScratch,
) -> Result<Option<(ArmSet, ArbOutcome)>, String> {
    if g.state.phase != Phase::Tiles {
        return Ok(None);
    }
    let legal = g.legal_actions();
    if legal.len() < 2 {
        return Ok(None);
    }
    let seat = g.state.current_player;
    let values = chain_values(g, seat, leaf_cfg, scratch)?;
    let det = match detect_tie(&values, eps) {
        None => return Ok(None),
        Some(d) => d,
    };
    let digest = g.state_digest();
    let arms = build_arms(g, &det.tie_actions, j, Some(champ_pick), salt, &digest, ply)?;
    if arms.arms.len() < 2 {
        // Every tied action transposes to one board AND the champion's pick is
        // one of them: there is nothing to arbitrate. Counted as NOT fired.
        return Ok(None);
    }
    let out = arbitrate(g, seat, &arms.arms, b, salt, &digest, ply, mode)?;
    Ok(Some((arms, out)))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn midgame(seed: &str, plies: usize) -> Game {
        let mut g = Game::from_seed(seed);
        for _ in 0..plies {
            let l = g.legal_actions();
            g.advance(l[l.len() / 2]).unwrap();
        }
        g
    }

    fn tiles_root(seed: &str, from: usize) -> Game {
        let mut g = midgame(seed, from);
        while g.state.phase != Phase::Tiles || g.legal_actions().len() < 2 {
            let l = g.legal_actions();
            g.advance(l[l.len() / 2]).unwrap();
        }
        g
    }

    #[test]
    fn chain_values_covers_every_legal_tile_action() {
        let g = tiles_root("28000000000", 30);
        let cfg = LeafConfig::curve125();
        let mut s = LeafScratch::new();
        let v = chain_values(&g, g.state.current_player, &cfg, &mut s).unwrap();
        let legal = g.legal_actions();
        assert_eq!(v.len(), legal.len());
        assert_eq!(
            v.iter().map(|c| c.action).collect::<Vec<_>>(),
            legal,
            "chain_values must stay in ascending action order"
        );
        assert!(v.iter().all(|c| c.value.is_finite()));
    }

    /// The chain is tile + BEST meeple, and the meeple leg is only taken when
    /// the successor is still the acting seat's turn.
    #[test]
    fn the_chain_takes_the_best_meeple_continuation() {
        let g = tiles_root("28000000000", 30);
        let cfg = LeafConfig::curve125();
        let mut s = LeafScratch::new();
        let seat = g.state.current_player;
        let v = chain_values(&g, seat, &cfg, &mut s).unwrap();
        let cv = v.iter().find(|c| c.meeple.is_some()).expect(
            "a tile placement in the base game is always followed by the same \
             player's meeple decision",
        );
        let mut g1 = g.clone();
        g1.advance(cv.action).unwrap();
        assert_eq!(g1.state.current_player, seat);
        let mut best = f64::NEG_INFINITY;
        for m in g1.legal_actions() {
            let mut g2 = g1.clone();
            g2.advance(m).unwrap();
            let x = s.leaf_value_float(&g2.state, seat, &cfg).unwrap();
            if x > best {
                best = x;
            }
        }
        assert_eq!(cv.value.to_bits(), best.to_bits());
    }

    /// `eps = 0` is BIT equality, not a tolerance: a value one ULP below the
    /// top is NOT a member.
    #[test]
    fn eps_zero_is_bit_equality_not_a_tolerance() {
        let mk = |a: i32, v: f64| ChainValue {
            action: a,
            value: v,
            meeple: None,
        };
        let top = 3.25f64;
        let one_ulp_below = f64::from_bits(top.to_bits() - 1);
        assert!(detect_tie(&[mk(1, top), mk(2, one_ulp_below)], 0.0).is_none());
        let d = detect_tie(&[mk(1, top), mk(2, top), mk(5, 0.0)], 0.0).unwrap();
        assert_eq!(d.tie_actions, vec![1, 2]);
        assert_eq!(d.n_cand, 3);
        assert_eq!(d.top1.to_bits(), top.to_bits());
        // ...and a positive eps DOES admit the neighbour, so the parameter is
        // wired (the cell runs eps = 0 and the manifest proves it).
        assert!(detect_tie(&[mk(1, top), mk(2, one_ulp_below)], 1e-9).is_some());
    }

    #[test]
    fn detect_tie_needs_two_actions() {
        let mk = |a: i32, v: f64| ChainValue {
            action: a,
            value: v,
            meeple: None,
        };
        assert!(detect_tie(&[mk(1, 1.0)], 0.0).is_none());
        assert!(detect_tie(&[mk(1, 1.0), mk(2, 0.5)], 0.0).is_none());
    }

    /// The cap is a SEEDED DRAW, not index truncation: with more deduped
    /// candidates than `J - 1` the kept set must (a) be size `J`, (b) contain
    /// the reference arm, and (c) not be the first `J - 1` in index order for
    /// at least one seed — the exact failure `build_tie_arms` calls out.
    #[test]
    fn the_cap_is_a_seeded_draw_and_is_deterministic() {
        // A synthetic tie set over the root's own legal actions. Any actions
        // work: the dedupe key is their successor board, and distinct
        // placements give distinct boards.
        let g = tiles_root("28000000000", 30);
        let legal = g.legal_actions();
        assert!(legal.len() >= 8, "need a wide root; got {}", legal.len());
        let tie: Vec<i32> = legal.iter().copied().take(8).collect();
        let mut saw_non_prefix = false;
        for ply in 0..12i64 {
            let a = build_arms(&g, &tie, 4, Some(tie[0]), TIEARB_SALT_OF_RECORD, "digest", ply).unwrap();
            assert!(a.capped);
            assert_eq!(a.arms.len(), 4, "J = 4 arms");
            assert_eq!(a.arms[0], tie[0], "arm[0] is the leaf tie-break of record");
            assert!(a.arms.iter().all(|x| tie.contains(x)));
            if a.arms[1..] != tie[1..4] {
                saw_non_prefix = true;
            }
            // determinism
            let b = build_arms(&g, &tie, 4, Some(tie[0]), TIEARB_SALT_OF_RECORD, "digest", ply).unwrap();
            assert_eq!(a.arms, b.arms);
        }
        assert!(
            saw_non_prefix,
            "every seed returned the index prefix — the cap is truncating, not drawing"
        );
    }

    /// The champion's pick is appended when the cap (or the tie set) excluded
    /// it, and is NOT appended when an arm already reaches the same board.
    #[test]
    fn the_champion_pick_is_appended_when_excluded() {
        let g = tiles_root("28000000000", 30);
        let legal = g.legal_actions();
        let tie: Vec<i32> = legal.iter().copied().take(8).collect();
        let outside = *legal.last().unwrap();
        assert!(!tie.contains(&outside));
        let a = build_arms(&g, &tie, 4, Some(outside), TIEARB_SALT_OF_RECORD, "d", 0).unwrap();
        assert!(a.champ_appended);
        assert_eq!(a.arms.len(), 5, "J = 4 plus the champion's own pick");
        assert_eq!(*a.arms.last().unwrap(), outside);
        // already an arm -> no append, no duplicate
        let b = build_arms(&g, &tie, 4, Some(a.arms[1]), TIEARB_SALT_OF_RECORD, "d", 0).unwrap();
        assert!(!b.champ_appended);
        assert_eq!(b.arms.len(), 4);
    }

    /// Transposing actions collapse to ONE arm — the corpus's afterstate
    /// dedupe, which is why an all-transposition tie is not arbitrated.
    #[test]
    fn transposing_actions_dedupe_to_one_arm() {
        let g = tiles_root("28000000000", 30);
        let legal = g.legal_actions();
        // A tie set that repeats the same action reaches one board.
        let a = build_arms(&g, &[legal[0], legal[0]], 4, Some(legal[0]), "s", "d", 0).unwrap();
        assert_eq!(a.n_distinct_afterstates, 1);
        assert!(a.all_transposition);
        assert_eq!(a.arms, vec![legal[0]]);
    }

    /// The CRN: every arm is scored on the SAME 16 worlds, so two arms that are
    /// the same action must return bit-identical means.
    #[test]
    fn crn_worlds_are_shared_by_every_arm() {
        let g = tiles_root("28000000000", 30);
        let legal = g.legal_actions();
        let out = arbitrate(
            &g,
            g.state.current_player,
            &[legal[0], legal[0]],
            2,
            TIEARB_SALT_OF_RECORD,
            "d",
            7,
            TiearbMode::Argmax,
        )
        .unwrap();
        assert_eq!(out.means[0].to_bits(), out.means[1].to_bits());
        assert_eq!(out.n_playouts, 4);
        assert_eq!(out.chosen, legal[0]);
    }

    /// `random` runs the identical playouts and returns an arm from the SAME
    /// arm set; the argmax is still computed (the wall-clock contract).
    #[test]
    fn random_mode_does_the_same_work_and_draws_from_the_same_arms() {
        let g = tiles_root("28000000000", 30);
        let legal = g.legal_actions();
        let arms = [legal[0], legal[1], legal[2]];
        let seat = g.state.current_player;
        let a = arbitrate(&g, seat, &arms, 2, "s", "d", 3, TiearbMode::Argmax).unwrap();
        let r = arbitrate(&g, seat, &arms, 2, "s", "d", 3, TiearbMode::Random).unwrap();
        assert_eq!(a.n_playouts, r.n_playouts, "the two modes must cost the same");
        for (x, y) in a.means.iter().zip(r.means.iter()) {
            assert_eq!(x.to_bits(), y.to_bits(), "random mode changed the playouts");
        }
        assert_eq!(a.argmax_arm, r.argmax_arm, "the argmax is computed in both");
        assert_eq!(a.chosen, a.argmax_arm);
        assert!(arms.contains(&r.chosen));
        // seeded => reproducible
        let r2 = arbitrate(&g, seat, &arms, 2, "s", "d", 3, TiearbMode::Random).unwrap();
        assert_eq!(r.chosen, r2.chosen);
        // ...and it is a real draw: some (digest, ply) picks a non-first arm.
        let mut saw_other = false;
        for ply in 0..24i64 {
            let x = arbitrate(&g, seat, &arms, 1, "s", "d", ply, TiearbMode::Random).unwrap();
            if x.chosen != arms[0] {
                saw_other = true;
                break;
            }
        }
        assert!(saw_other, "the random draw never left arm 0");
    }

    #[test]
    fn the_seed_is_a_pure_function_of_its_parts() {
        assert_eq!(seed_i64(&["a", "b"]), seed_i64(&["a", "b"]));
        assert_ne!(seed_i64(&["a", "b"]), seed_i64(&["a", "c"]));
        assert!(seed_i64(&["a", "b"]) >= 0);
    }

    #[test]
    fn mode_parses_and_round_trips() {
        assert_eq!(TiearbMode::parse("argmax").unwrap(), TiearbMode::Argmax);
        assert_eq!(TiearbMode::parse("random").unwrap(), TiearbMode::Random);
        assert!(TiearbMode::parse("Argmax").is_err());
        assert_eq!(TiearbMode::Random.value(), "random");
    }

    /// The MEEPLE phase never triggers (DESIGN §2 clause 1).
    #[test]
    fn the_trigger_is_tiles_only() {
        let mut g = tiles_root("28000000000", 30);
        let cfg = LeafConfig::curve125();
        let mut s = LeafScratch::new();
        g.advance(g.legal_actions()[0]).unwrap();
        assert_eq!(g.state.phase, Phase::Meeples);
        let out = arbitrate_decision(
            &g,
            g.legal_actions()[0],
            &cfg,
            2,
            4,
            TIEARB_SALT_OF_RECORD,
            0.0,
            0,
            TiearbMode::Argmax,
            &mut s,
        )
        .unwrap();
        assert!(out.is_none());
    }
}
