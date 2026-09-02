//! `fair::pool` — **RISK-ASYMMETRIC WORLD POOLING** (GT-M1).
//!
//! The deployed champion picks its root move by the **mean** of the per-world
//! PIMC values: the k determinization worlds' `root_stats_list` are summed into
//! one `(N, W)` pool and the pick is [`super::pooled_q_argmax`] over
//! `Q = ΣW / ΣN`.  That is a *visit-weighted mean over worlds*, and it is
//! risk-neutral by construction.
//!
//! [`PoolMode::CVaR`] replaces it with a **lower-tail (risk-averse) mean**: each
//! candidate action is scored by the average of its per-world `Q` over the
//! `ceil(α·k)` worlds where it does WORST, and the pick is the argmax of that
//! score.  Small α = look only at the worst worlds = maximally adversarial.
//!
//! # ⛔ THE ARITHMETIC IS THE CENSUS'S, NOT A RE-DERIVATION
//!
//! Every definition below is transcribed from the free, judge-free census that
//! licensed this lever —
//! `measurement/cl083_mech_censuses_20260830/PREREG.md` §"CENSUS 1 — Definitions
//! (fixed before compute)" and its implementation
//! `analyze_census13.py::{per_world_argmax, cvar, census1_row}`.  The census
//! computed the RATE at which this rule changes the champion's pick
//! (`reach(α)`); this module is the same rule made PLAYABLE.  If the two ever
//! disagree, the census is right and this file is wrong:
//! `tests::census_transcription_*` pin the four places the transcription could
//! silently drift.
//!
//! | census term | here |
//! |---|---|
//! | per-world `q_i(a) = W_i(a) / N_i(a)` from world *i*'s `root_stats_list` | [`world_q`] |
//! | CVaR-**eligible** action: `N_i(a) >= min_visits` in **ALL** k worlds, and present in all k | [`cvar_eligible`] |
//! | `CVaR_α(a)` = mean of the `ceil(α·k)` SMALLEST `q_i(a)` | [`cvar_score`] |
//! | pick = `max` over eligible of `(CVaR_α, Σ_i N_i(a), -a)` | [`cvar_argmax`] |
//!
//! # ⚠️⚠️ α = 1.0 IS **NOT** THE DEPLOYED MEAN — this is a DISCLOSED census finding
//!
//! It is tempting to read `CVaR_{1.0}` as an identity control ("the whole tail
//! is the whole distribution, so it must be the mean").  It is the mean of the
//! per-world `q_i` with **EQUAL WEIGHT PER WORLD**.  The deployed rule is
//! `ΣW / ΣN`, which is **visit-weighted** across worlds, and the two differ
//! whenever a world spends a different number of visits on an action than its
//! siblings do — which is the normal case, since PUCT allocates visits by what
//! it finds.
//!
//! The census disclosed exactly this and refused to call α=1.00 an identity
//! control (`DEVIATIONS.md` D-1): **the α=1.00 rule changed the champion's pick
//! on 18.1% of contest-exposed plies by itself.**  `reach_vs_equalweight`
//! exists in that artefact precisely to separate the two effects, and it puts
//! the marginal contribution of *risk aversion* at α=0.25 at 21.3pp on top of
//! the 18.1pp weighting effect.
//!
//! ⛔ So a build brief that says "α=1.0 must be bit-exact with Mean" is asking
//! for something the census already measured to be FALSE.  What IS bit-exact,
//! and what [`tests::alpha_one_is_the_sorted_order_equal_weight_mean`] pins, is
//! that `CVaR_{1.0}` equals the **sorted-order** equal-weight mean —
//! `sorted(q).sum() / k`, summed in ASCENDING order, because that is the order
//! the census's `sum(s[:j])/j` sums in and float addition is not associative.
//! A cell that wants the risk-aversion effect *net of* the weighting effect
//! must run an α=1.0 arm as its own control; this module makes that arm
//! expressible and the PREREG scopes it.
//!
//! # Bit-identity of the default path
//!
//! [`PoolMode::Mean`] is the default and is dispatched by a single `match` on a
//! `Copy` enum placed immediately before the existing
//! [`super::pooled_q_argmax`] call.  Nothing in this module is constructed,
//! allocated or read on that arm — the same rule
//! [`crate::search::SearchConfig::tiearb_enabled`] and
//! `jrules_filter_mask == 0` follow.  The default path is byte-identical, not
//! merely equal, and `measurement/cvar_pool_prep/goldengate/` is its witness.

use super::Pool;

/// Which rule turns the k per-world root statistics into ONE root move.
///
/// ⚠️ `PartialEq` only (no `Eq`/`Hash`): the CVaR arm carries an `f64`.
#[derive(Clone, Copy, PartialEq, Debug)]
pub enum PoolMode {
    /// ⭐ THE CHAMPION. Visit-weighted pooled `Q = ΣW / ΣN` over all k worlds,
    /// picked by [`super::pooled_q_argmax`]. Byte-identical to the pre-flag
    /// code path.
    Mean,
    /// Lower-tail CVaR at level `alpha ∈ (0, 1]` over the per-world `Q`.
    /// `ceil(alpha * k)` worlds enter the mean (always at least 1).
    CVaR { alpha: f64 },
}

impl PoolMode {
    /// `"mean"` / `"cvar"` — the wire spelling the python layer and every
    /// manifest use. ⛔ The alpha is NOT part of the name (a manifest carries it
    /// in its own field), so a reader can never confuse `cvar` at two doses.
    pub fn name(&self) -> &'static str {
        match self {
            PoolMode::Mean => "mean",
            PoolMode::CVaR { .. } => "cvar",
        }
    }

    /// The resolved alpha, or `None` on [`PoolMode::Mean`].
    pub fn alpha(&self) -> Option<f64> {
        match self {
            PoolMode::Mean => None,
            PoolMode::CVaR { alpha } => Some(*alpha),
        }
    }

    /// Parse `(name, alpha)` fail-CLOSED.
    ///
    /// ⛔ Every combination that could ride silently is refused here rather than
    /// coerced: `mean` with an alpha (a caller who believes they dosed the knob
    /// and did not), `cvar` without one, a non-finite alpha, and an alpha
    /// outside `(0, 1]`. α ≤ 0 selects zero worlds (the census's `max(1, …)`
    /// would silently turn it into "the single worst world", i.e. a DIFFERENT
    /// rule wearing the requested one's name) and α > 1 selects more worlds than
    /// exist.
    pub fn parse(name: &str, alpha: Option<f64>) -> Result<Self, String> {
        match name {
            "mean" => {
                if let Some(a) = alpha {
                    return Err(format!(
                        "pool_mode='mean' takes NO alpha, got {a} — a caller that \
                         passed an alpha believes it dosed the pooling rule and did \
                         not. Pass pool_mode='cvar' or drop the alpha."
                    ));
                }
                Ok(PoolMode::Mean)
            }
            "cvar" => {
                let a = alpha.ok_or_else(|| {
                    "pool_mode='cvar' requires pool_alpha in (0, 1] — the lower-tail \
                     fraction of worlds that enter the mean (0.25 == the worst \
                     quarter). There is no default: a defaulted alpha is a \
                     different experiment wearing this cell's name."
                        .to_string()
                })?;
                if !a.is_finite() || a <= 0.0 || a > 1.0 {
                    return Err(format!(
                        "pool_alpha must be finite and in (0, 1]; got {a}. \
                         alpha <= 0 selects zero worlds (the ceil()'s max(1,..) \
                         would silently make it 'the single worst world', a \
                         DIFFERENT rule) and alpha > 1 selects more worlds than \
                         exist."
                    ));
                }
                Ok(PoolMode::CVaR { alpha: a })
            }
            other => Err(format!(
                "pool_mode must be 'mean'|'cvar'; got {other:?} ('mean' == the \
                 deployed champion, bit-for-bit)"
            )),
        }
    }
}

/// `measurement/cl083_mech_censuses_20260830/analyze_census13.py::cvar` —
/// **the mean of the `ceil(alpha*k)` SMALLEST values.**
///
/// ```text
/// s = sorted(vals); j = max(1, ceil(alpha * len(s))); sum(s[:j]) / j
/// ```
///
/// ⚠️⚠️ **THE SUM IS IN ASCENDING (SORTED) ORDER AND THAT IS LOAD-BEARING.**
/// Float addition is not associative, so `sorted(v).sum()` and `v.sum()` are
/// different f64s in general. The census sums the sorted prefix; so does this.
/// A "harmless" reordering here would make every replay of a banked cell
/// disagree with it in the last bits and, at a tie, in the *pick*.
///
/// Sorting uses `f64::total_cmp`, which orders NaN deterministically rather
/// than leaving `sort_by(partial_cmp)` to panic. A NaN cannot reach here — the
/// per-world `Q` is `W/N` with `N >= min_visits >= 1` — but the argmax below
/// must never be at the mercy of a comparator that can abort a game.
///
/// # Panics
/// If `vals` is empty (the caller guarantees k >= 1 worlds).
pub fn cvar_score(vals: &[f64], alpha: f64) -> f64 {
    assert!(!vals.is_empty(), "cvar_score on zero worlds");
    let mut s: Vec<f64> = vals.to_vec();
    s.sort_by(|a, b| a.total_cmp(b));
    // `max(1, ceil(alpha * k))`. `alpha` is validated to (0, 1] by
    // `PoolMode::parse`, so `j` lands in [1, k] — the max(1) is the census's
    // own guard, kept verbatim so the transcription is checkable by eye.
    let j = ((alpha * s.len() as f64).ceil() as usize).max(1).min(s.len());
    let mut acc = 0.0f64;
    for &v in &s[..j] {
        acc += v;
    }
    acc / j as f64
}

/// One world's `q_i(a) = W_i(a) / N_i(a)`, in that world's `root_stats_list`
/// order, plus its `N_i(a)`.
///
/// ⚠️ NO `min_visits` filter here — the census's `per_world_argmax` builds the
/// full per-world q map and applies eligibility separately
/// ([`cvar_eligible`]), because CVaR eligibility is a cross-world predicate.
/// Filtering early would drop actions that a *different* world visited enough
/// and silently change which actions are comparable.
fn world_q(stats: &[(i32, i64, f64)]) -> Vec<(i32, f64, i64)> {
    stats.iter().map(|&(a, n, w)| (a, w / n as f64, n)).collect()
}

/// The **CVaR-eligible** action set: present with `N_i(a) >= min_visits` in
/// **EVERY** world.
///
/// The census's justification, kept verbatim because it is the reason this is
/// not the pooled eligibility rule: *"An action the search barely looked at in
/// some world has no defined per-world Q there and cannot be given one by a
/// pooling rule."*
///
/// ⚠️ ORDER: world 0's `root_stats_list` order, which is the census's
/// `for a in qmaps[0]` (a python dict preserves insertion order). The argmax
/// key below is a strict total order, so the answer does not *depend* on this —
/// but the order is preserved anyway so a per-ply dump of the eligible set is
/// comparable to the census's.
fn cvar_eligible(worlds: &[Vec<(i32, f64, i64)>], min_visits: f64) -> Vec<i32> {
    if worlds.is_empty() {
        return Vec::new();
    }
    worlds[0]
        .iter()
        .filter(|&&(a, _q, _n)| {
            worlds
                .iter()
                .all(|w| w.iter().any(|&(b, _q, n)| b == a && (n as f64) >= min_visits))
        })
        .map(|&(a, _q, _n)| a)
        .collect()
}

/// The outcome of one CVaR pooling decision — the pick plus everything a gate
/// or a census needs to check that the rule actually bound.
#[derive(Clone, Debug, PartialEq)]
pub struct CvarPick {
    /// The action the CVaR rule chose, or `None` when NO action is
    /// CVaR-eligible (see [`cvar_argmax`]'s fallback contract).
    pub action: Option<i32>,
    /// How many actions were CVaR-eligible.
    pub n_eligible: usize,
    /// How many worlds entered the lower-tail mean: `max(1, ceil(alpha * k))`.
    pub j_worlds: usize,
}

/// ⭐⭐ THE RULE. `argmax` over CVaR-eligible actions of
/// `(CVaR_α(a), Σ_i N_i(a), -a)`.
///
/// The tie key is the census's, which is in turn `pooled_q_argmax`'s key with
/// the pooled `Q` swapped for the CVaR score: score first, then total visits,
/// then the LOWEST action id. `-a` is unique, so the key is a strict total
/// order and the answer is independent of iteration order — the same property
/// [`super::pooled_q_argmax`]'s doc comment records.
///
/// # ⛔ THE FALLBACK CONTRACT (a DEPARTURE from the census, and it must be)
///
/// The census could return `None` for a ply with no CVaR-eligible action and
/// simply not count it (`reach[α] = None`). **A player cannot decline to
/// move.** So when the eligible set is empty this returns
/// `CvarPick { action: None, .. }` and the caller
/// ([`super::FairAgent::pimc_move`]) falls back to the champion's own
/// [`super::pooled_q_argmax`] for that ply. The fallback is:
///
/// * **rare by construction** — it needs an action that some world visited
///   fewer than `min_visits = 2` times *while at least one other world's stats
///   list contains it*, at 1376 sims per world;
/// * **counted**, never silent (`FairAgent::pool_fallbacks` rides in `stats()`),
///   so a cell where it fired often is visible before anyone reads an outcome;
/// * **the champion's move**, not an arbitrary one — a ply the rule cannot
///   express is a ply the candidate plays as the champion, which biases the
///   measured effect toward zero rather than in an unknown direction.
pub fn cvar_argmax(
    stats: &[Vec<(i32, i64, f64)>],
    alpha: f64,
    min_visits: f64,
) -> CvarPick {
    let worlds: Vec<Vec<(i32, f64, i64)>> = stats.iter().map(|s| world_q(s)).collect();
    let k = worlds.len();
    let j_worlds = if k == 0 {
        0
    } else {
        ((alpha * k as f64).ceil() as usize).max(1).min(k)
    };
    let elig = cvar_eligible(&worlds, min_visits);
    if elig.is_empty() {
        return CvarPick { action: None, n_eligible: 0, j_worlds };
    }
    // Score every eligible action, then argmax on the census's total-order key.
    let mut best: Option<(i32, f64, f64)> = None; // (action, score, total_n)
    for &a in &elig {
        let mut vals: Vec<f64> = Vec::with_capacity(k);
        let mut total_n = 0.0f64;
        for w in &worlds {
            // `find` over the world's stats list: the lists are short (root
            // legal moves) and the ELIGIBILITY predicate above already proved
            // `a` is in every one of them, so this cannot miss.
            let (_b, q, n) = *w
                .iter()
                .find(|&&(b, _q, _n)| b == a)
                .expect("cvar_eligible guarantees membership in every world");
            vals.push(q);
            total_n += n as f64;
        }
        let score = cvar_score(&vals, alpha);
        let better = match best {
            None => true,
            Some((ba, bs, bn)) => {
                // Python `max(..., key=...)` keeps the FIRST maximum; the key is
                // a strict total order here (`-a` is unique), so ">" is exactly
                // the tuple comparison.
                score > bs
                    || (score == bs
                        && (total_n > bn || (total_n == bn && -(a as i64) > -(ba as i64))))
            }
        };
        if better {
            best = Some((a, score, total_n));
        }
    }
    CvarPick {
        action: best.map(|(a, _, _)| a),
        n_eligible: elig.len(),
        j_worlds,
    }
}

/// The pooled `Q` the DEPLOYED rule would compute for `a` — exposed only so a
/// test can state the α=1.0-is-not-the-mean proposition as arithmetic rather
/// than as prose.
#[doc(hidden)]
pub fn deployed_pooled_q(pool: &Pool, a: i32) -> f64 {
    pool.w[&a] / pool.n[&a]
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Hand-built world matrix: `worlds[i]` = that world's `(action, N, W)`.
    fn mk(rows: &[&[(i32, i64, f64)]]) -> Vec<Vec<(i32, i64, f64)>> {
        rows.iter().map(|r| r.to_vec()).collect()
    }

    // ---------------------------------------------------------------- parse --

    #[test]
    fn parse_refuses_every_silent_ride() {
        assert_eq!(PoolMode::parse("mean", None).unwrap(), PoolMode::Mean);
        // mean + an alpha: the caller thinks they dosed it and did not.
        assert!(PoolMode::parse("mean", Some(0.25)).is_err());
        // cvar with no alpha: no default is allowed to exist.
        assert!(PoolMode::parse("cvar", None).is_err());
        for bad in [0.0, -0.25, 1.5, f64::NAN, f64::INFINITY] {
            assert!(
                PoolMode::parse("cvar", Some(bad)).is_err(),
                "alpha {bad} must be refused"
            );
        }
        assert!(PoolMode::parse("CVaR", Some(0.25)).is_err(), "case-sensitive");
        assert_eq!(
            PoolMode::parse("cvar", Some(0.25)).unwrap(),
            PoolMode::CVaR { alpha: 0.25 }
        );
        assert_eq!(PoolMode::Mean.name(), "mean");
        assert_eq!(PoolMode::CVaR { alpha: 0.5 }.name(), "cvar");
        assert_eq!(PoolMode::Mean.alpha(), None);
        assert_eq!(PoolMode::CVaR { alpha: 0.5 }.alpha(), Some(0.5));
    }

    // ------------------------------------------------- the ceil(alpha*k) edge --

    /// ⭐ THE EDGE CASE THE CENSUS'S `max(1, ceil(alpha*k))` EXISTS FOR, and the
    /// k=16 DEPLOYED WIDTH the round actually plays at.
    #[test]
    fn census_transcription_j_worlds_at_every_declared_alpha() {
        let v: Vec<f64> = (0..16).map(|i| i as f64).collect(); // 0..15
        // k = 16 (the deployed width): 0.25 -> 4, 0.50 -> 8, 0.75 -> 12, 1.0 -> 16.
        // mean of the j smallest of 0..15 = (j-1)/2.
        for (alpha, j) in [(0.25, 4usize), (0.5, 8), (0.75, 12), (1.0, 16)] {
            let want = (0..j).map(|x| x as f64).sum::<f64>() / j as f64;
            assert_eq!(cvar_score(&v, alpha), want, "k=16 alpha={alpha} j={j}");
        }
        // k = 8 (the CENSUS's width): 0.25 -> 2, 0.50 -> 4, 0.75 -> 6, 1.0 -> 8.
        let v8: Vec<f64> = (0..8).map(|i| i as f64).collect();
        for (alpha, j) in [(0.25, 2usize), (0.5, 4), (0.75, 6), (1.0, 8)] {
            let want = (0..j).map(|x| x as f64).sum::<f64>() / j as f64;
            assert_eq!(cvar_score(&v8, alpha), want, "k=8 alpha={alpha} j={j}");
        }
        // NON-DIVISIBLE k: ceil ROUNDS UP, it does not round to nearest.
        // k=5, alpha=0.25 -> ceil(1.25) = 2, NOT 1.
        let v5 = [10.0, 20.0, 30.0, 40.0, 50.0];
        assert_eq!(cvar_score(&v5, 0.25), 15.0);
        // k=3, alpha=0.25 -> ceil(0.75) = 1.
        assert_eq!(cvar_score(&[7.0, 8.0, 9.0], 0.25), 7.0);
        // k=1: every alpha selects the one world.
        assert_eq!(cvar_score(&[4.0], 0.25), 4.0);
        assert_eq!(cvar_score(&[4.0], 1.0), 4.0);
    }

    /// ⚠️ The lower tail is the SMALLEST values — a sign slip here inverts the
    /// whole lever into risk-SEEKING pooling while every label still says CVaR.
    #[test]
    fn census_transcription_lower_tail_not_upper() {
        let v = [1.0, 2.0, 3.0, 100.0];
        assert_eq!(cvar_score(&v, 0.25), 1.0, "worst 1 of 4");
        assert_eq!(cvar_score(&v, 0.5), 1.5, "worst 2 of 4");
        assert_ne!(cvar_score(&v, 0.25), 100.0);
        // input order must not matter (it is sorted first)
        assert_eq!(cvar_score(&[100.0, 3.0, 1.0, 2.0], 0.5), 1.5);
    }

    /// ⭐⭐ α = 1.0 IS THE **SORTED-ORDER** EQUAL-WEIGHT MEAN — and is NOT, in
    /// general, the naive input-order mean. Float addition is not associative;
    /// the census sums the sorted prefix and so must we.
    #[test]
    fn alpha_one_is_the_sorted_order_equal_weight_mean() {
        // A set chosen so ascending-order and input-order summation differ in
        // the last bits.
        let v: [f64; 8] = [1e16, 1.0, -1e16, 3.0, 2.0, 1.0, 1.0, 1.0];
        let mut s = v.to_vec();
        s.sort_by(|a, b| a.total_cmp(b));
        let sorted_mean = s.iter().fold(0.0f64, |acc, &x| acc + x) / v.len() as f64;
        assert_eq!(cvar_score(&v, 1.0), sorted_mean);
        let naive_mean = v.iter().fold(0.0f64, |acc, &x| acc + x) / v.len() as f64;
        assert_ne!(
            cvar_score(&v, 1.0),
            naive_mean,
            "if these ever coincide, pick a nastier fixture — the POINT of this \
             test is that summation order is observable"
        );
    }

    // ------------------------------------------------------------ eligibility --

    /// The cross-world eligibility rule: `N_i >= min_visits` in EVERY world.
    #[test]
    fn census_transcription_eligibility_is_cross_world() {
        // action 7 is starved in world 1 (N=1 < 2) -> INELIGIBLE even though it
        // is the pooled favourite. action 9 is missing entirely from world 1.
        let stats = mk(&[
            &[(5, 10, 5.0), (7, 10, 9.9), (9, 10, 1.0)],
            &[(5, 10, 5.0), (7, 1, 0.99)],
        ]);
        let worlds: Vec<_> = stats.iter().map(|s| world_q(s)).collect();
        assert_eq!(cvar_eligible(&worlds, 2.0), vec![5]);
        // relax the floor and 7 becomes eligible; 9 never does (absent in w1).
        assert_eq!(cvar_eligible(&worlds, 1.0), vec![5, 7]);
    }

    /// ⛔ THE FALLBACK CONTRACT: no eligible action => `action: None`, and the
    /// AGENT (not this function) reverts to the champion's own pick.
    #[test]
    fn empty_eligible_set_returns_none_for_the_agent_to_fall_back() {
        let stats = mk(&[&[(5, 10, 5.0)], &[(6, 10, 5.0)]]); // disjoint sets
        let p = cvar_argmax(&stats, 0.25, 2.0);
        assert_eq!(p.action, None);
        assert_eq!(p.n_eligible, 0);
    }

    // ----------------------------------------------------------- the argmax --

    /// ⭐ THE LEVER'S WHOLE POINT, as arithmetic: an action that wins on the
    /// MEAN can lose on the lower tail, and CVaR then picks differently.
    #[test]
    fn cvar_can_disagree_with_the_mean_and_that_is_the_lever() {
        // Two worlds, two actions, equal visits everywhere so the deployed
        // pooled Q and the equal-weight mean coincide (isolating RISK).
        //   a=1: q = (0.9, -0.5)  mean +0.20  worst -0.50
        //   a=2: q = (0.1,  0.1)  mean +0.10  worst +0.10
        // mean prefers 1; the worst-world rule prefers 2.
        let stats = mk(&[&[(1, 10, 9.0), (2, 10, 1.0)], &[(1, 10, -5.0), (2, 10, 1.0)]]);
        assert_eq!(cvar_argmax(&stats, 1.0, 2.0).action, Some(1), "mean picks 1");
        assert_eq!(cvar_argmax(&stats, 0.5, 2.0).action, Some(2), "worst-1 picks 2");
        assert_eq!(cvar_argmax(&stats, 0.5, 2.0).j_worlds, 1);
        assert_eq!(cvar_argmax(&stats, 1.0, 2.0).j_worlds, 2);
    }

    /// The tie key `(score, Σ N, -action)` — score ties break on TOTAL VISITS,
    /// then on the LOWEST action id. Same order `pooled_q_argmax` uses.
    #[test]
    fn census_transcription_tiebreak_is_score_then_visits_then_lowest_action() {
        // identical scores, different total visits -> higher Σ N wins
        let stats = mk(&[&[(3, 4, 2.0), (9, 10, 5.0)], &[(3, 4, 2.0), (9, 10, 5.0)]]);
        assert_eq!(cvar_argmax(&stats, 1.0, 2.0).action, Some(9));
        // identical scores AND identical visits -> LOWEST action id wins
        let stats2 = mk(&[&[(9, 10, 5.0), (3, 10, 5.0)], &[(9, 10, 5.0), (3, 10, 5.0)]]);
        assert_eq!(cvar_argmax(&stats2, 1.0, 2.0).action, Some(3));
        assert_eq!(cvar_argmax(&stats2, 0.25, 2.0).action, Some(3));
    }

    /// ⭐⭐ THE DISCLOSED CENSUS FINDING (`DEVIATIONS.md` D-1), as a TEST rather
    /// than a footnote: **α = 1.0 is NOT the deployed pooled argmax.** The
    /// deployed rule is visit-weighted (`ΣW / ΣN`); α=1.0 weights worlds
    /// EQUALLY. When the visit counts differ across worlds they disagree, and
    /// the census measured that disagreement at 18.1% of contest-exposed plies.
    #[test]
    fn alpha_one_is_not_the_deployed_visit_weighted_mean() {
        // a=1: world A 100 visits at q=+0.10, world B 2 visits at q=-1.00
        //        pooled  = (10.0 + -2.0) / 102 = +0.0784
        //        equal-w = (0.10 + -1.00) / 2  = -0.4500
        // a=2: q = -0.20 in both worlds, 51 visits each
        //        pooled  = -0.20 ; equal-w = -0.20
        // => deployed prefers 1 (+0.078 > -0.20); equal-weight prefers 2.
        let stats = mk(&[
            &[(1, 100, 10.0), (2, 51, -10.2)],
            &[(1, 2, -2.0), (2, 51, -10.2)],
        ]);
        let mut pool = Pool::default();
        for s in &stats {
            pool.merge(s);
        }
        let deployed = super::super::pooled_q_argmax(&pool, 2.0).unwrap();
        assert_eq!(deployed, 1, "the DEPLOYED visit-weighted rule picks 1");
        assert_eq!(
            cvar_argmax(&stats, 1.0, 2.0).action,
            Some(2),
            "⛔ alpha=1.0 (EQUAL-WEIGHT worlds) picks 2 — it is NOT an identity \
             control for the deployed mean, exactly as census DEVIATIONS D-1 \
             disclosed (18.1% pick change on its own)"
        );
        // and the arithmetic behind it, stated directly
        assert!(deployed_pooled_q(&pool, 1) > deployed_pooled_q(&pool, 2));
    }

    /// k = 16, the DEPLOYED width, end to end: a plausibly-shaped world matrix
    /// at both funded doses.
    #[test]
    fn deployed_width_k16_at_both_funded_doses() {
        // action 1 is a "greedy" move: good in 12 worlds, catastrophic in 4.
        // action 2 is flat. Equal visits so weighting is not the variable.
        let mut rows: Vec<Vec<(i32, i64, f64)>> = Vec::new();
        for i in 0..16 {
            let q1 = if i < 12 { 0.5 } else { -3.0 };
            rows.push(vec![(1, 10, q1 * 10.0), (2, 10, 0.0)]);
        }
        // alpha 0.25 -> worst 4 = exactly the four -3.0 worlds -> -3.0 < 0.0
        let p25 = cvar_argmax(&rows, 0.25, 2.0);
        assert_eq!(p25.j_worlds, 4);
        assert_eq!(p25.action, Some(2));
        // alpha 0.50 -> worst 8 = four -3.0 and four +0.5 -> (-12+2)/8 = -1.25 < 0
        let p50 = cvar_argmax(&rows, 0.5, 2.0);
        assert_eq!(p50.j_worlds, 8);
        assert_eq!(p50.action, Some(2));
        // the MEAN over all 16 = (12*0.5 + 4*-3.0)/16 = -0.375 < 0 -> also 2 here;
        // flip action 1's downside to -1.0 and the mean prefers 1 while 0.25 does not.
        let mut rows2: Vec<Vec<(i32, i64, f64)>> = Vec::new();
        for i in 0..16 {
            let q1 = if i < 12 { 0.5 } else { -1.0 };
            rows2.push(vec![(1, 10, q1 * 10.0), (2, 10, 0.0)]);
        }
        assert_eq!(cvar_argmax(&rows2, 1.0, 2.0).action, Some(1), "mean: +0.125");
        assert_eq!(cvar_argmax(&rows2, 0.25, 2.0).action, Some(2), "worst 4: -1.0");
        assert_eq!(p25.n_eligible, 2);
    }
}
