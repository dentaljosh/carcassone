//! J-RULES AS POLICY PRIORS — surface B (`measurement/jrules_priors_20260814/DESIGN.md`).
//!
//! The static-leaf encoding of the anchor's strategy (the sibling
//! [`super::jrules_term`], surface A) ran at the deploy budget 2026-08-13 and was
//! adjudicated a *loss, confounded by budget* (no claim minted; the prereg's §7
//! left this surface — the policy prior — explicitly untouched by every branch).
//! This module is the prior-surface encoding: the same interview, consumed at
//! **node expansion** to bias WHERE the search spends visits, while the leaf's
//! value estimates — and therefore everything the search backs up — stay the
//! unmodified champion's.
//!
//! ## What the prior surface can express that the static leaf could not
//!
//! The leaf of record must be an **antisymmetric** pure function of
//! `(state, cfg)` (`V(s,p) == -V(s,1-p)`; the search negates it on backup). A
//! prior is neither backed up nor negated — it is a preference ordering over the
//! MOVER's own children, computed while the decision node's full state is in
//! hand. Three consequences, each a rule the static form had to weaken or drop:
//!
//! 1. **"He must already be there" is RESTORED.** The bot's J1 / J2-steal /
//!    J6-road-join all require `cnt[me] >= 1 AND cnt[opp] >= 1` — a JOIN into
//!    *his* structure. In a signed differential that predicate self-cancels
//!    (DESIGN §3.0 of the static cell), so surface A had to credit *holding a
//!    share*. Here each rule is evaluated for the mover only, so the original
//!    predicates run verbatim.
//! 2. **J2a — the planning clause — is EXPRESSED.** "this requires planning 2-4
//!    tiles in advance, so i look at remaining tiles": the bot's deck-counted
//!    reach model ([`super::super::engine::GameState::remaining_deck`] +
//!    entry-cell scan) is a function of the decision node, which a leaf cannot
//!    see coherently but an expansion-time prior can. Ported from
//!    `joshua_bot.j2_reach` / the APPROACH loop of `j2_farm_attack`.
//! 3. **J5 runs in the bot's own BEFORE/AFTER form.** The bot's J5 charges a
//!    *move* ("a throwaway placement that feeds unclaimed value"), not a
//!    position. A potential has no "before"; an expansion-time prior has the
//!    parent in hand, so `j5_dump` is ported verbatim (throwaway gate on the
//!    naive-count gain, charge on the unclaimed value fed).
//!
//! Also restored from the bot, per its fair-information design: the CLOCK
//! ([`JrPriorClock`]) — `k`, `late_frac`, the bag farm fraction, both reserves
//! and the margin — is read **once from the decision node** and reused for every
//! candidate child, exactly like `joshua_bot.Clock` (the static form had to read
//! these per-leaf, and J8's "margin at the root" became "margin at the leaf").
//!
//! ## What it still cannot express
//!
//! * Multi-ply plans as such — the search itself remains the planner; the reach
//!   model is a one-scalar proxy, not a plan.
//! * Value: a prior cannot make the search *prefer outcomes* the leaf scores
//!   badly — it only reallocates visits. If the leaf mis-prices a J-favoured
//!   line, more visits will simply confirm the leaf's verdict (this is the
//!   honest mechanism behind the pre-registered sims-washout risk).
//! * J3 (already in the leaf as curve125), J7 (tournament-calibrated to zero),
//!   J9 (no conviction), J10f / hard floors (root FILTERS, still a separate,
//!   undosable intervention — deliberately not smuggled in here).
//!
//! ## Contract
//!
//! * Pure function of `(parent_state, child_state, mover, mask)` — reproducible
//!   for the Python reference mirror (`carcassonne_ai/jrules_priors.py`);
//!   every reduction is [`fsum`] over a push-ordered `Vec`, matching the parent
//!   module's determinism discipline.
//! * Consumed ONLY by `search::Searcher::evaluate` under
//!   `SearchConfig::jrules_prior_dose != 0.0` — dose 0.0 (the default, the
//!   champion) never calls into this module at all, so default traffic is
//!   bit-identical, not merely equal.
//! * NOT part of `LeafConfig` and NOT hashed into any leaf fingerprint: the
//!   candidate's leaf hash EQUALS the champion's `a36d2e15a3b3d71d`. ⚠️ A
//!   moved-leaf-hash wiring gate therefore CANNOT prove this term live — the
//!   gate is the resolved `jrules_prior_dose` in the manifest plus the dose-0
//!   bit-exactness control (see the DESIGN's wiring-gate table).

use super::{
    flat_base_score_farm, fsum, jr_counts, jr_farm_potential, jr_late_frac, jr_min1,
    jr_unclaimed_value, jr_urgency, Decomp, JrCounts, JR_J1, JR_J2, JR_J5, JR_J6, JR_J8,
};
use crate::engine::{GameState, BOARD_COLS, BOARD_ROWS};
use crate::tiles;

// --- the FROZEN `current`-preset parameters this surface adds ----------------
// The five rules' shared constants live in the parent module (`JR_*`); these are
// the bot parameters ONLY the prior surface can express, copied
// constant-for-constant from `joshua_bot.JoshuaParams` defaults (== the
// `current` preset, the epoch the tournament selected at z +3.68) and pinned by
// `tests/test_jrules_priors.py::test_constants_match_joshua_bot`. Deliberately
// NOT config fields: the calibration axis is the single scalar dose.
/// `JoshuaParams.j2_approach_w`.
pub const JP_J2_APPROACH_W: f64 = 0.15;
/// `JoshuaParams.j2_plan_horizon` — "2-4 tiles in advance".
pub const JP_J2_PLAN_HORIZON: usize = 3;
/// `JoshuaParams.j2_reach_threshold` — "is it realistic to get there".
pub const JP_J2_REACH_THRESHOLD: f64 = 0.50;
/// `JoshuaParams.j2_entry_cells_cap`.
pub const JP_J2_ENTRY_CELLS_CAP: i64 = 3;
/// `JoshuaParams.j5_throwaway_gain` — a placement gaining <= this is a
/// "throwaway tile".
pub const JP_J5_THROWAWAY_GAIN: f64 = 1.0;
/// `JoshuaParams.j5_weight` (same value the static bundle froze as
/// `JR_J5_WEIGHT`; named separately because the two surfaces use it in
/// different formulas — the bot's before/after dump here, a potential there).
pub const JP_J5_WEIGHT: f64 = 0.5;

/// The decision node's clock + bag — `joshua_bot.Clock`, read ONCE per node
/// expansion from the PARENT state and reused for every candidate child.
/// Keeping it off the children is the bot's own fair-information rule ("blind to
/// the tile the engine draws inside a lookahead") and is also what makes the
/// added cost per child small.
#[derive(Clone, Debug)]
pub struct JrPriorClock {
    /// `k_remaining` at the decision node (undrawn deck + the tile in hand).
    pub k: usize,
    /// `Clock.late_frac` against the frozen [`super::JR_K0`].
    pub late_frac: f64,
    /// `joshua_bot.bag_farm_fraction` over the node's (determinized) undrawn
    /// deck — `next_tile` deliberately EXCLUDED, as the bot excludes it.
    pub bag_farm_frac: f64,
    /// J4 urgency from the OPPONENT's reserve at the decision node.
    pub urg: f64,
    /// The opponent's meeple reserve (gates J5's dump).
    pub opp_reserve: i32,
    /// `flat_base_score` at the decision node from the mover's seat — J5's
    /// "before" and J8's margin (the bot reads the margin at the decision root;
    /// the static form could only read it at the leaf).
    pub parent_base: f64,
    /// `|parent_base|` — what J8 compares swings against.
    pub abs_margin: f64,
    /// `unclaimed_value` at the decision node — J5's "before".
    pub parent_unclaimed: f64,
}

/// Build the clock from the decision node. `d` MUST be `parent`'s decomposition.
pub fn jr_prior_clock(parent: &GameState, mover: usize, d: &Decomp) -> JrPriorClock {
    let opp = 1 - mover;
    let k = parent.deck_len() + usize::from(parent.next_tile.is_some());
    let deck = parent.remaining_deck();
    let mut farm_ok: usize = 0;
    for &base in deck {
        // ⚠️ Deck entries are BASE tile indices, NOT registry TileIds — convert
        // via `tile_id(base, 0)` (farm presence is rotation-invariant). Reading
        // `tiles::tile(base)` directly would silently sample the wrong tiles.
        if !tiles::tile(tiles::tile_id(base, 0)).farms.is_empty() {
            farm_ok += 1;
        }
    }
    let bag_farm_frac = if deck.is_empty() {
        0.0
    } else {
        farm_ok as f64 / deck.len() as f64
    };
    let (city_counts, road_counts, _farm_counts, cloister_owned) = jr_counts(parent, d);
    let parent_base = flat_base_score_farm(parent, mover, d, false) as f64;
    let parent_unclaimed = jr_unclaimed_value(parent, d, &city_counts, &road_counts, &cloister_owned);
    JrPriorClock {
        k,
        late_frac: jr_late_frac(k),
        bag_farm_frac,
        urg: jr_urgency(parent.meeples[opp]),
        opp_reserve: parent.meeples[opp],
        parent_base,
        abs_margin: parent_base.abs(),
        parent_unclaimed,
    }
}

/// `joshua_bot.Position.farm_entry_cells` — distinct EMPTY board cells
/// orthogonally adjacent to the field (the permissive "is there still a way in"
/// proxy; rotation is free, so any adjacent empty cell counts once).
fn jp_farm_entry_cells(state: &GameState, d: &Decomp, root: u32) -> i64 {
    // Distinct field cells first (farm nodes are per (cell, slot)).
    let mut cells: Vec<(i32, i32)> = Vec::new();
    for (nid, &rc) in d.farm_node_rc.iter().enumerate() {
        if d.farm_labels[nid] == root && !cells.contains(&rc) {
            cells.push(rc);
        }
    }
    let mut entries: Vec<(i32, i32)> = Vec::new();
    for &(r, c) in &cells {
        for (dr, dc) in [(-1i32, 0i32), (1, 0), (0, -1), (0, 1)] {
            let (nr, nc) = (r + dr, c + dc);
            // Python: `0 <= nr < h and 0 <= nc < w and board[nr][nc] is None`.
            if (0..BOARD_ROWS).contains(&nr)
                && (0..BOARD_COLS).contains(&nc)
                && state.get_tile(nr, nc).is_none()
                && !entries.contains(&(nr, nc))
            {
                entries.push((nr, nc));
            }
        }
    }
    entries.len() as i64
}

/// `joshua_bot.j2_reach` — the deck-counted "can I still get in" model.
/// `1 - (1 - per_turn)^h`; permissive by construction.
fn jp_j2_reach(state: &GameState, d: &Decomp, root: u32, clock: &JrPriorClock) -> f64 {
    let my_turns = clock.k / 2;
    if my_turns < 1 {
        return 0.0;
    }
    let cells = jp_farm_entry_cells(state, d, root);
    if cells == 0 {
        return 0.0;
    }
    let h = JP_J2_PLAN_HORIZON.min(my_turns);
    if h < 1 {
        return 0.0;
    }
    let cap = JP_J2_ENTRY_CELLS_CAP.max(1);
    let per_turn = jr_min1(clock.bag_farm_frac * cells.min(cap) as f64 / cap as f64);
    // `powf`, not `powi`: CPython's `float ** int` goes through libm `pow`,
    // and the Python reference mirror must reproduce this bit-for-bit.
    1.0 - (1.0 - per_turn).powf(h as f64)
}

/// J1 — the bot's ORIGINAL `j1_majority_steal`: a JOIN into HIS large open city
/// (`cnt[me] >= 1 AND cnt[opp] >= 1 AND cnt[me] >= cnt[opp]` — the predicate the
/// static surface had to drop).
fn jp_j1(d: &Decomp, city_counts: &JrCounts, me: usize, clock: &JrPriorClock) -> f64 {
    let opp = 1 - me;
    let mut contribs: Vec<f64> = Vec::new();
    let bonus =
        super::JR_J1_JOIN_BONUS * (1.0 + super::JR_J1_LATE_EXTRA * clock.late_frac) * clock.urg;
    for &(root, cnt) in city_counts {
        let r = root as usize;
        if d.city_root_finished[r] {
            continue;
        }
        if cnt[me] < 1 || cnt[opp] < 1 {
            continue; // not a JOIN into his city — RESTORED predicate
        }
        if cnt[me] < cnt[opp] {
            continue; // not a tie/majority
        }
        if d.city_root_tiles[r] < super::JR_J1_MIN_CITY_TILES {
            continue;
        }
        if d.city_root_open_n[r] < super::JR_J1_MIN_OPEN_EDGES {
            continue;
        }
        contribs.push(bonus);
    }
    fsum(&contribs)
}

/// J2 — the bot's ORIGINAL `j2_farm_attack`, all three pieces: REALIZED steal
/// (restored `his >= 1`), the J10-current SURRENDER charge, and — newly
/// expressible on this surface — the APPROACH loop (the planning clause), gated
/// by the deck-counted reach model.
fn jp_j2(
    state: &GameState,
    d: &Decomp,
    farm_counts: &JrCounts,
    me: usize,
    clock: &JrPriorClock,
) -> f64 {
    let opp = 1 - me;
    let mut contribs: Vec<f64> = Vec::new();
    for &(root, cnt) in farm_counts {
        let pot = jr_farm_potential(d, root, clock.k);
        let value = 3.0 * d.farm_root_finished_cities[root as usize] as f64 + pot;
        let (mine, his) = (cnt[me], cnt[opp]);
        if mine >= 1 && his >= 1 && mine >= his {
            // REALIZED: the tie/steal already happened; no reach test owed.
            if value >= super::JR_J2_MIN_FARM_VALUE {
                contribs.push(super::JR_J2_STEAL_W * pot * clock.urg);
            }
        }
        if mine >= 1 && value < super::JR_J2_MIN_FARM_VALUE {
            contribs.push(-super::JR_J2_LOW_FARM_PENALTY * mine as f64); // SURRENDER
        }
    }
    // APPROACH — "planning 2-4 tiles in advance": his valuable fields I am not
    // on, on which a way in still exists. This loop is J2a, the clause the
    // static surface disclosed as not expressible.
    for &(root, cnt) in farm_counts {
        if cnt[me] >= 1 || cnt[opp] < 1 {
            continue;
        }
        let value = 3.0 * d.farm_root_finished_cities[root as usize] as f64
            + jr_farm_potential(d, root, clock.k);
        if value < super::JR_J2_MIN_FARM_VALUE {
            continue;
        }
        let reach = jp_j2_reach(state, d, root, clock);
        if reach < JP_J2_REACH_THRESHOLD {
            continue;
        }
        contribs.push(JP_J2_APPROACH_W * value * reach * clock.urg);
    }
    fsum(&contribs)
}

/// J5 — the bot's ORIGINAL before/after `j5_dump`: a throwaway placement
/// (naive-count gain <= [`JP_J5_THROWAWAY_GAIN`]) is charged for every point of
/// UNCLAIMED value it feeds. Needs the parent ("before"), which only this
/// surface has.
fn jp_j5(
    state: &GameState,
    d: &Decomp,
    city_counts: &JrCounts,
    road_counts: &JrCounts,
    cloister_owned: &[(i32, i32)],
    clock: &JrPriorClock,
    child_base: f64,
) -> f64 {
    if clock.opp_reserve <= 0 {
        return 0.0;
    }
    if child_base - clock.parent_base > JP_J5_THROWAWAY_GAIN {
        return 0.0; // not a throwaway: take the points
    }
    let fed = jr_unclaimed_value(state, d, city_counts, road_counts, cloister_owned)
        - clock.parent_unclaimed;
    if fed <= 0.0 {
        return 0.0;
    }
    -JP_J5_WEIGHT * fed * clock.urg
}

/// J6 — the bot's ORIGINAL `j6_anchor_and_roads`: anchors + road skepticism
/// (own-side predicates, unchanged from the static surface) plus the road JOIN
/// with its restored `cnt[opp] >= 1`.
fn jp_j6(d: &Decomp, city_counts: &JrCounts, road_counts: &JrCounts, me: usize,
         clock: &JrPriorClock) -> f64 {
    let opp = 1 - me;
    let mut contribs: Vec<f64> = Vec::new();
    let mut has_city_anchor = false;
    for &(root, cnt) in city_counts {
        let r = root as usize;
        if d.city_root_finished[r] || cnt[me] <= cnt[opp] {
            continue;
        }
        if d.city_root_tiles[r] >= super::JR_J6_ANCHOR_CITY_MIN {
            has_city_anchor = true;
            break;
        }
    }
    let mut has_road_anchor = false;
    let mut n_short_solo: i64 = 0;
    for &(root, cnt) in road_counts {
        let r = root as usize;
        if d.road_root_finished[r] {
            continue;
        }
        let length = d.road_root_tiles[r];
        if cnt[me] >= 1 && cnt[opp] >= 1 && cnt[me] >= cnt[opp]
            && length >= super::JR_J6_ROAD_JOIN_MIN_LEN
        {
            contribs.push(super::JR_J6_ROAD_JOIN_BONUS * clock.urg); // (b) JOIN, restored
        }
        if cnt[me] > cnt[opp] {
            if length >= super::JR_J6_ANCHOR_ROAD_MIN {
                has_road_anchor = true;
            }
            if cnt[opp] == 0 && length <= super::JR_J6_ROAD_SKEPTIC_MAX_LEN {
                n_short_solo += 1;
            }
        }
    }
    contribs.push(
        super::JR_J6_ANCHOR_BONUS
            * (i64::from(has_city_anchor) + i64::from(has_road_anchor)) as f64,
    ); // (a)
    let mut excess = n_short_solo - super::JR_J6_ROAD_ANCHOR_ALLOWANCE;
    if excess < 0 {
        excess = 0;
    }
    contribs.push(-super::JR_J6_ROAD_CLAIM_PENALTY * excess as f64); // (c)
    fsum(&contribs)
}

/// J8 — the bot's ORIGINAL `j8_overcommit`, own side, with the margin read at
/// the DECISION NODE (`clock.abs_margin`) — the bot's own semantics, which the
/// static surface had to approximate with the margin at the leaf — and the
/// bot's own farm gate (the field must still be enterable, `farm_entry_cells
/// >= 1`; the static surface substituted a `k >= 1` clock gate).
fn jp_j8(
    state: &GameState,
    d: &Decomp,
    city_counts: &JrCounts,
    farm_counts: &JrCounts,
    me: usize,
    clock: &JrPriorClock,
) -> f64 {
    let opp = 1 - me;
    let mut contribs: Vec<f64> = Vec::new();
    for &(root, cnt) in city_counts {
        let r = root as usize;
        if d.city_root_finished[r] {
            continue;
        }
        if d.city_root_open_n[r] < 1 {
            continue; // he can no longer get in
        }
        let value = d.city_root_delta[r] as f64;
        let swing = 2.0 * value;
        if swing < super::JR_J8_PIVOTAL_SWING || swing < clock.abs_margin {
            continue;
        }
        if cnt[me] - cnt[opp] < 2 || cnt[me] > super::JR_J8_MAX_CITY_MEEPLES {
            continue;
        }
        contribs.push(
            super::JR_J8_OVERCOMMIT_BONUS * jr_min1(value / super::JR_J8_VALUE_NORM) * clock.urg,
        );
    }
    for &(root, cnt) in farm_counts {
        if jp_farm_entry_cells(state, d, root) < 1 {
            continue; // no longer enterable — the bot's own gate
        }
        let value = 3.0 * d.farm_root_finished_cities[root as usize] as f64
            + jr_farm_potential(d, root, clock.k);
        let swing = 2.0 * value;
        if swing < super::JR_J8_PIVOTAL_SWING || swing < clock.abs_margin {
            continue;
        }
        if cnt[me] - cnt[opp] < 2 || cnt[me] > super::JR_J8_MAX_FARM_MEEPLES {
            continue;
        }
        contribs.push(
            super::JR_J8_OVERCOMMIT_BONUS * jr_min1(value / super::JR_J8_VALUE_NORM) * clock.urg,
        );
    }
    fsum(&contribs)
}

/// The J-rules PRIOR term for one candidate child — the bot's rules, mover's own
/// side only (a prior needs no antisymmetry), original predicates, clock from
/// the decision node. The search adds `dose * term` to the child's Δleaf
/// BEFORE the prior softmax — i.e. a multiplicative, renormalized boost of
/// `exp(dose * term / tau_p)` on that child's prior, and NOTHING else: no
/// backed-up value moves.
///
/// `state`/`d` are the CHILD afterstate and its decomposition; `child_base` is
/// `flat_base_score` of the child from the mover's seat (the caller's leaf
/// evaluation already computed it — see `LeafScratch::leaf_float_and_base`).
///
/// Mask bits are the parent module's [`JR_J1`] .. [`JR_J8`] (default 31 == the
/// bundle); J2's APPROACH clause rides inside [`JR_J2`], as it does in the bot.
/// Parts are pushed in the fixed order J1, J2, J5, J6, J8 and [`fsum`]-reduced.
pub fn jrules_prior_term(
    state: &GameState,
    mover: usize,
    d: &Decomp,
    mask: i64,
    clock: &JrPriorClock,
    child_base: f64,
) -> f64 {
    let (city_counts, road_counts, farm_counts, cloister_owned) = jr_counts(state, d);
    let mut parts: Vec<f64> = Vec::new();
    if mask & JR_J1 != 0 {
        parts.push(jp_j1(d, &city_counts, mover, clock));
    }
    if mask & JR_J2 != 0 {
        parts.push(jp_j2(state, d, &farm_counts, mover, clock));
    }
    if mask & JR_J5 != 0 {
        parts.push(jp_j5(state, d, &city_counts, &road_counts, &cloister_owned, clock, child_base));
    }
    if mask & JR_J6 != 0 {
        parts.push(jp_j6(d, &city_counts, &road_counts, mover, clock));
    }
    if mask & JR_J8 != 0 {
        parts.push(jp_j8(state, d, &city_counts, &farm_counts, mover, clock));
    }
    fsum(&parts)
}
