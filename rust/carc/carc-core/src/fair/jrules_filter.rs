//! J-RULES AS ROOT FILTERS — surface C (`measurement/jrules_filters_20260814/DESIGN.md`).
//!
//! The third — and last untested — encoding surface for the anchor's strategy:
//!
//! * surface A (static leaf terms) RAN 2026-08-13 → *loss, confounded by budget*;
//! * surface B (PUCT priors) RAN 2026-08-14 → a MEASURED CLEAN NULL (the
//!   sims-washout: 11,008 sims wash out a 13% pick-flip prior perturbation);
//! * surface C (this module): the bot's HARD FILTERS — `joshua_bot._apply_filters`,
//!   F-END / F-J10 / F-J9 / F-J3 — applied to the ROOT legal-action set of the
//!   production fair-PIMC agent, BEFORE any world search runs.
//!
//! ## Why a filter is categorically different from a prior
//!
//! A prior BIASES visit allocation; the search can (and at 11,008 sims
//! demonstrably does) override it with evidence. A root filter REMOVES the
//! action from the root candidate set: no amount of search brings it back. It
//! is the strategy expressed as a CONSTRAINT rather than a preference — which
//! is also its danger: when the filter is wrong, the excluded move's evidence
//! is thrown away, not outvoted.
//!
//! ## Fidelity to the bot
//!
//! `joshua_bot.JoshuaBot._apply_filters` applies the four filters IN ORDER,
//! each skipped when it would empty the candidate set, and ONLY in the MEEPLES
//! phase (tile-phase candidates are never hard-filtered by the bot; the
//! filters only shape its tile scoring through the lookahead). This module
//! keeps all of that:
//!
//! * **meeple-phase roots only** — a TILES-phase root is returned untouched;
//! * **fixed order** F-END, F-J10, F-J9, F-J3;
//! * **never-empty guard, generalized**: a filter that would leave fewer than
//!   `min_keep` candidates YIELDS (is skipped for that ply) and the yield is
//!   counted. `min_keep = 1` is the bot's own rule exactly.
//!
//! Parameters are the bot's `current` preset, FROZEN as `JF_*` constants
//! (pinned against `joshua_bot.JoshuaParams` by
//! `tests/test_jrules_filter.py::test_constants_match_joshua_bot`), with the
//! same two freezes the prior surfaces disclosed:
//!
//! * `k0` is frozen at [`crate::leaf::JR_K0`] (72.0) — the bot latches `k0` at
//!   its first decision, which in every real game is 72;
//! * `j8_break_reserve_floor` is FROZEN OFF: the tournament-selected `current`
//!   preset carries `False`, so F-J3's pivotal-overcommit exemption is not
//!   expressed here (a `j8brk` variant is a named, unexercised option needing
//!   its own calibration).
//!
//! F-J9 exists as a mask bit but is NOT in the `current` stack
//! ([`JF_CURRENT`] = END|J10|J3 = 11): the bot's `j9_avoid_cloisters` is
//! opt-in and defaults OFF, and the tournament read no conviction on it.
//!
//! ## Contract
//!
//! * Pure function of `(game, mask, min_keep)` — no RNG, no globals; the
//!   Python reference mirror is `carcassonne_ai/jrules_filter.py` and the two
//!   are compared bit-for-bit on replayed games.
//! * Consumed ONLY by [`super::FairAgent::pimc_move`] under
//!   `SearchConfig::jrules_filter_mask != 0` — mask 0 (the default, the
//!   champion) never calls into this module at all, so default traffic is
//!   bit-identical, not merely equal.
//! * NOT part of `LeafConfig` and NOT hashed into any leaf fingerprint: the
//!   candidate's leaf hash EQUALS the champion's. ⚠️ A moved-leaf-hash wiring
//!   gate CANNOT prove this term live — the gates are the resolved
//!   `jrules_filter_mask` in the manifest plus the per-cell positive control
//!   (`jf_dropped_total >= 1` summed over the cell's games).
//! * The filter runs ONCE PER MOVE (not per node), on the TRUE root state
//!   (all inputs are fair information: the board, both reserves, `k`), before
//!   any determinization is drawn — so it consumes no randomness and is
//!   identical across the `k_dets` worlds.

use crate::action_space::{decode, meeple_farmer_base, meeple_pass_index};
use crate::engine::{Action, Phase};
use crate::game::Game;
use crate::leaf::{decompose, jr_counts, Decomp, JR_K0};
use crate::tiles::{self, Side, TerrainType};

// --- mask bits (a filter is binary per rule; there is no dose) --------------
/// F-END — endgame deployment: with `k_remaining <= my reserve` an unplaced
/// meeple is wasted points, so PASS is dropped. Overrides J3 (the bot's rule).
pub const JF_END: i64 = 1;
/// F-J10 — early-farmer block: no FARMER claim while more than
/// [`JF_EARLY_FARM_BLOCK_FRAC`] of the bag is left (the J10 `current` epoch's
/// stated adaptation).
pub const JF_J10: i64 = 2;
/// F-J9 — cloister caution (the bot's OPT-IN axis): no CLOISTER claim while
/// more than [`JF_J9_CLOISTER_BLOCK_FRAC`] of the bag is left, unless its 3x3
/// already holds [`JF_J9_MIN_SURROUNDING`] tiles.
pub const JF_J9: i64 = 4;
/// F-J3 — own-reserve floor: do not spend down below [`JF_J3_RESERVE_FLOOR`]
/// unless the meeple comes straight back (a closure) or the placement is a
/// majority swing. Released in the endgame (`k <= my reserve`, or
/// `k <= JF_J3_ENDGAME_RELEASE_K`).
pub const JF_J3: i64 = 8;
/// Every filter bit.
pub const JF_ALL: i64 = JF_END | JF_J10 | JF_J9 | JF_J3;
/// The bot's `current`-preset filter stack: F-END + F-J10 + F-J3 (F-J9 is the
/// opt-in axis the tournament read no conviction on; its bit exists for
/// ablation, not for the primary stack).
pub const JF_CURRENT: i64 = JF_END | JF_J10 | JF_J3;

// --- the FROZEN `current`-preset parameters ---------------------------------
/// `JoshuaParams.j3_reserve_floor` — "keep at least 1 meeple in my hand".
pub const JF_J3_RESERVE_FLOOR: i64 = 1;
/// `JoshuaParams.j3_endgame_release_k` — "...until the bag is nearly empty".
pub const JF_J3_ENDGAME_RELEASE_K: i64 = 8;
/// `JoshuaParams.early_farm_block_frac` (the `current` epoch).
pub const JF_EARLY_FARM_BLOCK_FRAC: f64 = 0.55;
/// `JoshuaParams.j9_cloister_block_frac`.
pub const JF_J9_CLOISTER_BLOCK_FRAC: f64 = 0.55;
/// `JoshuaParams.j9_min_surrounding` (3x3 fullness INCLUDING the centre tile).
pub const JF_J9_MIN_SURROUNDING: i64 = 6;

/// The four filters, in application order — index into
/// [`FilterOutcome::fires`] / [`FilterOutcome::yields`].
pub const JF_FILTER_NAMES: [&str; 4] = ["f_end", "f_j10", "f_j9", "f_j3"];

/// The outcome of one root-filter evaluation.
#[derive(Clone, Debug, Default)]
pub struct FilterOutcome {
    /// The surviving root candidate set, in the legal-action order the search
    /// would otherwise see. Equals the full legal set when nothing fired.
    pub kept: Vec<i32>,
    /// The actions the filters removed (legal-order).
    pub dropped: Vec<i32>,
    /// Per-filter, `[F-END, F-J10, F-J9, F-J3]`: the filter really bit
    /// (removed at least one action and survived the guard).
    pub fires: [bool; 4],
    /// Per-filter: the never-empty guard fired — the filter WOULD have left
    /// fewer than `min_keep` candidates and was skipped for this ply.
    pub yields: [bool; 4],
    /// False when the filter did not apply at all (tiles phase, forced move,
    /// or mask 0) — `kept` is then the untouched legal set.
    pub applicable: bool,
}

/// Per-candidate tags — everything the bot's `_tag_meeple` records.
struct Tags {
    is_meeple_place: bool,
    is_farmer: bool,
    is_cloister: bool,
    cloister_strong: bool,
    closes_own: bool,
    swings_majority: bool,
}

/// 3x3 fullness including the centre — `joshua_bot.surrounding_count`.
fn surrounding_count(g: &Game, r: i32, c: i32) -> i64 {
    let mut n = 0i64;
    for dr in -1..=1i32 {
        for dc in -1..=1i32 {
            if g.state.get_tile(r + dr, c + dc).is_some() {
                n += 1;
            }
        }
    }
    n
}

/// `joshua_bot.JoshuaBot._tag_meeple`, for ONE meeple-phase action at the root.
///
/// `need_j3` gates the expensive part (a cloned child + full decomposition):
/// F-J10/F-J9 need only the action's geometry, so when F-J3 is not armed for
/// this ply the child afterstate is never built.
fn tag_action(g: &Game, action: i32, me: usize, need_j3: bool) -> Result<Tags, String> {
    let w = g.window_size;
    let mut t = Tags {
        is_meeple_place: false,
        is_farmer: false,
        is_cloister: false,
        cloister_strong: false,
        closes_own: false,
        swings_majority: false,
    };
    if action >= meeple_pass_index(w) {
        return Ok(t); // PASS
    }
    t.is_meeple_place = true;
    t.is_farmer = meeple_farmer_base(w) <= action && action < meeple_pass_index(w);
    let act = decode(
        action,
        &g.offset,
        Phase::Meeples,
        g.state.next_tile,
        g.state.last_tile_action.map(|lta| lta.coord),
    )
    .map_err(|e| format!("jrules_filter: decode({action}) failed: {e:?}"))?;
    let Action::Meeple(ma) = act else {
        return Ok(t); // unreachable given the index range, but never panic
    };
    let (r, c, side): (i32, i32, Side) = (ma.coord.row, ma.coord.col, ma.side);
    let tid = match g.state.get_tile(r, c) {
        Some(t) => t,
        None => return Ok(t), // the bot bails the same way (`tile is None`)
    };
    let terrain = tiles::tile(tid).get_type(side);
    if terrain == Some(TerrainType::Chapel) || terrain == Some(TerrainType::Flowers) {
        // A cloister has no majority contest, but it IS the J9 decision.
        t.is_cloister = true;
        t.cloister_strong = surrounding_count(g, r, c) >= JF_J9_MIN_SURROUNDING;
        return Ok(t);
    }
    if !need_j3 {
        return Ok(t); // closes_own / swings_majority only feed F-J3
    }

    // F-J3's tags read the CHILD afterstate (counts AFTER this placement).
    let mut child = g.clone();
    child.advance(action)?;
    let d: Decomp = decompose(&child.state);
    let opp = 1 - me;
    let (city_counts, road_counts, farm_counts, _cloister_owned) = jr_counts(&child.state, &d);
    let (root, counts, finished): (Option<u32>, _, Option<&[bool]>) = match terrain {
        Some(TerrainType::City) => (
            d.city_side_root(r, c, side),
            &city_counts,
            Some(&d.city_root_finished[..]),
        ),
        Some(TerrainType::Road) => (
            d.road_side_root(r, c, side),
            &road_counts,
            Some(&d.road_root_finished[..]),
        ),
        _ => (d.farm_pos0_root(r, c, side), &farm_counts, None), // farms never "finish"
    };
    let Some(root) = root else {
        return Ok(t);
    };
    t.closes_own = matches!(finished, Some(f) if f[root as usize]);
    if let Some(&(_, cnt)) = counts.iter().find(|e| e.0 == root) {
        if cnt[opp] >= 1 && cnt[me] >= cnt[opp] {
            t.swings_majority = true;
        }
    }
    Ok(t)
}

/// The root filter — `joshua_bot.JoshuaBot._apply_filters` on the production
/// root legal set. Pure; consumes no RNG; runs once per move.
pub fn jrules_root_filter(g: &Game, mask: i64, min_keep: usize) -> Result<FilterOutcome, String> {
    let legal = g.legal_actions();
    let mut out = FilterOutcome {
        kept: legal.clone(),
        ..FilterOutcome::default()
    };
    if mask == 0 || g.state.phase != Phase::Meeples || legal.len() <= 1 {
        return Ok(out); // not applicable: tiles phase / forced / OFF
    }
    if mask & !JF_ALL != 0 {
        return Err(format!(
            "jrules_filter: mask {mask} has bits outside JF_ALL ({JF_ALL})"
        ));
    }
    out.applicable = true;
    let min_keep = min_keep.max(1); // 0 would defeat the never-empty contract

    let me = g.state.current_player;
    let k = super::k_remaining(g);
    let my_reserve = g.state.meeples[me] as i64;
    let endgame = k <= my_reserve;

    // F-J3 is the only filter that needs the (expensive) child-afterstate tags;
    // compute them only when it is armed AND its clock condition holds.
    let j3_armed = mask & JF_J3 != 0
        && !endgame
        && k > JF_J3_ENDGAME_RELEASE_K
        && my_reserve <= JF_J3_RESERVE_FLOOR;

    let mut tags: Vec<Tags> = Vec::with_capacity(legal.len());
    for &a in &legal {
        tags.push(tag_action(g, a, me, j3_armed)?);
    }
    let tag_of = |a: i32| -> &Tags {
        let i = legal.iter().position(|&x| x == a).expect("kept ⊆ legal");
        &tags[i]
    };

    // The bot's `_keep`: apply a filter unless it would leave < min_keep;
    // count a FIRE only on a real bite, a YIELD only when the guard blocked a
    // real bite.
    fn apply_one(
        kept: &mut Vec<i32>,
        idx: usize,
        min_keep: usize,
        fires: &mut [bool; 4],
        yields: &mut [bool; 4],
        pred: impl Fn(i32) -> bool,
    ) {
        let filtered: Vec<i32> = kept.iter().copied().filter(|&a| pred(a)).collect();
        if filtered.len() < kept.len() {
            if filtered.len() >= min_keep {
                *kept = filtered;
                fires[idx] = true;
            } else {
                yields[idx] = true;
            }
        }
    }
    let mut kept = legal.clone();
    let (mut fires, mut yields) = ([false; 4], [false; 4]);

    if mask & JF_END != 0 && endgame {
        apply_one(&mut kept, 0, min_keep, &mut fires, &mut yields, |a| {
            tag_of(a).is_meeple_place
        });
    }
    // frac <= 0 would mean OFF entirely (the `early` epoch); the frozen
    // `current` frac is 0.55 so the guard is vacuous here, kept for fidelity.
    if mask & JF_J10 != 0
        && JF_EARLY_FARM_BLOCK_FRAC > 0.0
        && (k as f64) > JF_EARLY_FARM_BLOCK_FRAC * JR_K0.max(1.0)
    {
        apply_one(&mut kept, 1, min_keep, &mut fires, &mut yields, |a| {
            !tag_of(a).is_farmer
        });
    }
    if mask & JF_J9 != 0 && (k as f64) > JF_J9_CLOISTER_BLOCK_FRAC * JR_K0.max(1.0) {
        apply_one(&mut kept, 2, min_keep, &mut fires, &mut yields, |a| {
            let t = tag_of(a);
            !t.is_cloister || t.cloister_strong
        });
    }
    if j3_armed {
        // j8_break_reserve_floor is FROZEN OFF (the tournament-selected
        // `current` preset), so the pivotal-overcommit exemption is absent.
        apply_one(&mut kept, 3, min_keep, &mut fires, &mut yields, |a| {
            let t = tag_of(a);
            !t.is_meeple_place || t.closes_own || t.swings_majority
        });
    }

    out.dropped = legal.iter().copied().filter(|a| !kept.contains(a)).collect();
    out.kept = kept;
    out.fires = fires;
    out.yields = yields;
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn game_from_seed(seed: &str) -> Game {
        Game::from_seed(seed)
    }

    /// Drive to a MEEPLES-phase root with >1 legal action by centre policy.
    fn to_meeple_root(seed: &str) -> Game {
        let mut g = game_from_seed(seed);
        for _ in 0..400 {
            if g.state.phase == Phase::Meeples && g.legal_actions().len() > 1 {
                return g;
            }
            let la = g.legal_actions();
            g.advance(la[la.len() / 2]).unwrap();
        }
        panic!("no meeple root reached");
    }

    #[test]
    fn mask0_and_tiles_phase_are_inapplicable_and_untouched() {
        let g = game_from_seed("1234");
        assert_eq!(g.state.phase, Phase::Tiles);
        let fo = jrules_root_filter(&g, JF_ALL, 1).unwrap();
        assert!(!fo.applicable);
        assert_eq!(fo.kept, g.legal_actions());
        assert!(fo.dropped.is_empty());
        let g2 = to_meeple_root("1234");
        let fo2 = jrules_root_filter(&g2, 0, 1).unwrap();
        assert!(!fo2.applicable);
        assert_eq!(fo2.kept, g2.legal_actions());
    }

    #[test]
    fn f_j10_drops_farmer_claims_early() {
        // Early game (k > 39.6): any legal FARMER claim must be dropped by
        // mask JF_J10; scan a few seeds for a meeple root that offers one.
        let w = 25;
        let fb = meeple_farmer_base(w);
        let mp = meeple_pass_index(w);
        let mut found = false;
        for seed in ["7", "1234", "99", "28000000000", "555"] {
            let g = to_meeple_root(seed);
            let legal = g.legal_actions();
            let farmers: Vec<i32> = legal
                .iter()
                .copied()
                .filter(|&a| fb <= a && a < mp)
                .collect();
            if farmers.is_empty() || super::super::k_remaining(&g) <= 40 {
                continue;
            }
            let fo = jrules_root_filter(&g, JF_J10, 1).unwrap();
            assert!(fo.fires[1], "F-J10 must fire when farmers are legal early");
            for a in &farmers {
                assert!(fo.dropped.contains(a), "farmer {a} must be dropped");
                assert!(!fo.kept.contains(a));
            }
            assert!(fo.kept.contains(&mp), "PASS survives F-J10");
            found = true;
            break;
        }
        assert!(found, "no early meeple root with a legal farmer claim found");
    }

    #[test]
    fn never_empty_guard_yields_instead_of_emptying() {
        // min_keep = len(legal) makes ANY bite impossible: every filter that
        // would have fired must YIELD and the kept set must equal legal.
        let g = to_meeple_root("7");
        let legal = g.legal_actions();
        let fo = jrules_root_filter(&g, JF_ALL, legal.len()).unwrap();
        assert_eq!(fo.kept, legal);
        assert!(fo.dropped.is_empty());
        assert!(!fo.fires.iter().any(|&f| f));
        // The plain run must really bite on this root for the test to mean
        // anything; if it does, the guarded run must record a yield.
        let plain = jrules_root_filter(&g, JF_ALL, 1).unwrap();
        if !plain.dropped.is_empty() {
            assert!(fo.yields.iter().any(|&y| y), "guard must count its yield");
        }
    }

    #[test]
    fn kept_plus_dropped_partition_legal_in_order() {
        for seed in ["7", "99", "555"] {
            let g = to_meeple_root(seed);
            let legal = g.legal_actions();
            let fo = jrules_root_filter(&g, JF_ALL, 1).unwrap();
            let mut merged: Vec<i32> = Vec::new();
            let (mut ik, mut id) = (0usize, 0usize);
            for &a in &legal {
                if ik < fo.kept.len() && fo.kept[ik] == a {
                    ik += 1;
                    merged.push(a);
                } else if id < fo.dropped.len() && fo.dropped[id] == a {
                    id += 1;
                    merged.push(a);
                }
            }
            assert_eq!(merged, legal, "kept ∪ dropped == legal, order preserved");
            assert_eq!(ik, fo.kept.len());
            assert_eq!(id, fo.dropped.len());
        }
    }
}
