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
//!
//! ## World THREADING is a latency knob with no semantics (2026-08-21)
//!
//! [`arbitrate`] takes a `threads` count and splits the `B` CRN worlds across
//! `min(B, threads)` scoped OS threads (arms inner) — `fair::search_worlds`'s
//! idiom and its chunking. This buys nothing but wall-clock and is REQUIRED to
//! change no number: the per-`(world, arm)` seeds are pure functions of
//! `(salt, digest, ply, j)` and nothing is shared between playouts, so the only
//! order-sensitive step is the f64 accumulation — which is why the threads
//! write margins into disjoint per-world slots and the fold into the per-arm
//! sums happens after the join, in the original `j`-then-arm order. The
//! whole-ply revert survives too: the fold propagates the error of the FIRST
//! failing `(j, arm)` in sequential order, never whichever thread lost the
//! race. `threads = 1` is the pre-change loop including its short-circuit, and
//! `SearchConfig::tiearb_threads` defaults to 1, so no deployed cell changes
//! until someone deliberately flips it. It does NOT change the mode contract
//! above: `ARB` and `RND` run the identical playouts at the identical thread
//! count, so they stay wall-clock indistinguishable.

use std::collections::HashMap;

use crate::compat::mt19937::MT19937;
use crate::engine::Phase;
use crate::fair::reshuffled_determinization;
use crate::game::Game;
use crate::leaf::{LeafConfig, LeafScratch};
use crate::repr_key::string_representation;
use crate::sha256::sha256_bytes;
use crate::tier1::{tier1_playout, tier1_playout_with, RefuterConfig};

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

/// The CANONICAL phase bucket of a `k_remaining`, reproduced BIT-FOR-BIT from
/// `scripts/measurement_infra/sample_agreement_roots.py:96` (copied verbatim
/// into `scripts/tiletie/chain_census.py:63`, which documents the copy as *"NOT
/// redefined independently"*, and keyed on by
/// `measurement/tiearb_widening_20260817/census/CENSUS.md` §6, the CL-070 root
/// bank and `split_tiearb2.py`'s strata):
///
/// ```python
/// PHASE_CUTS = {"early": (48, 10**9), "mid": (24, 48), "late": (-1, 24)}
/// def phase_bucket(k):
///     for name, (lo, hi) in PHASE_CUTS.items():
///         if lo < k < hi:        # STRICT on BOTH ends
///             return name
///     return "late"              # the fall-through
/// ```
///
/// ⚠️⚠️ **`k == 48` AND `k == 24` MATCH NO INTERVAL AND FALL THROUGH TO
/// `"late"`.** Both ends of every cut are strict, so `48` fails `48 < 48` twice
/// and `24` fails `24 < 24` twice. This is **reproduced, not repaired**
/// (`measurement/phasegate_prep/DESIGN.md` §2.2 / `READ_RULE.md` §3): every
/// artefact keyed on `phase_bucket` carries it, and a build that "fixed" the
/// edge would no longer be measuring the axis those artefacts label. Repairing
/// it is a separate, tree-wide change and is OUT OF SCOPE.
///
/// ⛔ The argument is `crate::fair::k_remaining(g)` — undrawn deck **plus the
/// tile in hand** — NEVER `g.state.deck_len()`, which
/// `search/window_diag.rs:156` uses and which is off by one against this axis.
///
/// Golden table (`k=71,49 -> early`; `47,25 -> mid`; `48,24,23 -> late`) is
/// pinned by [`tests::phase_bucket_golden_table`] and, on the python side, by
/// `tests/test_tiearb_phase_gate.py` against the canonical function itself.
pub fn phase_bucket(k_remaining: i64) -> &'static str {
    // Iteration order is `early`, `mid`, `late` — a python 3.7+ dict literal
    // preserves insertion order, so this `if` chain IS that loop.
    if 48 < k_remaining && k_remaining < 1_000_000_000 {
        "early"
    } else if 24 < k_remaining && k_remaining < 48 {
        "mid"
    } else if -1 < k_remaining && k_remaining < 24 {
        "late"
    } else {
        // The fall-through: k == 48, k == 24, k < 0, and k >= 10**9.
        "late"
    }
}

/// THE FIRE-GATE (`measurement/phasegate_prep/DESIGN.md` §7.2). A phase window
/// on the tie arbiter's *fire* decision, evaluated at the root hook.
///
/// ⛔ **NOT [`TIEARB_MAX_PLIES`]**, which is the *playout* ply ceiling — how
/// deep one `tier1-greedy` rollout may run before it ERRORS. This says which
/// GAME plies the arbiter fires at, and nothing about a rollout.
///
/// [`TiearbPhaseGate::All`] is the DEFAULT and is the pre-change arbiter, byte
/// for byte: `fires_at` returns `true` unconditionally and nothing else on this
/// surface is read. [`TiearbPhaseGate::None`] disarms the arbiter at every ply
/// while leaving the knob armed — the `IDENT` cell's shape, which proves the
/// gate reached the harness without changing a single played action.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TiearbPhaseGate {
    /// Fire at every detected tie — the pre-change behaviour, the default.
    All,
    /// Fire only where [`phase_bucket`] is `"early"` (`k_remaining` ∈ [49, 71]).
    Early,
    /// Fire only where [`phase_bucket`] is `"mid"` (`k_remaining` ∈ [25, 47]).
    Mid,
    /// Fire only where [`phase_bucket`] is `"late"` (`k_remaining` ∈ [0, 23]
    /// ⚠️ **plus `k == 48` and `k == 24`**).
    Late,
    /// Fire nowhere. The armed-but-inert `IDENT` shape.
    #[allow(clippy::enum_variant_names)]
    None,
}

impl TiearbPhaseGate {
    /// Fail-closed parse, the [`TiearbMode::parse`] shape. ⛔ An unknown or
    /// empty string is an ERROR, never a silent `All` — a silently-defaulted
    /// `all` would make `ARB_EARLY` *BE* `ARB_FULL` and the primary a
    /// guaranteed-meaningless duplicate of the anchor that looks perfectly
    /// healthy (DESIGN §7.4, the inverted-liveness hazard).
    pub fn parse(s: &str) -> Result<Self, String> {
        match s {
            "all" => Ok(TiearbPhaseGate::All),
            "early" => Ok(TiearbPhaseGate::Early),
            "mid" => Ok(TiearbPhaseGate::Mid),
            "late" => Ok(TiearbPhaseGate::Late),
            "none" => Ok(TiearbPhaseGate::None),
            other => Err(format!(
                "tiearb_phase_gate must be 'all'|'early'|'mid'|'late'|'none'; got {other:?}"
            )),
        }
    }

    pub fn value(&self) -> &'static str {
        match self {
            TiearbPhaseGate::All => "all",
            TiearbPhaseGate::Early => "early",
            TiearbPhaseGate::Mid => "mid",
            TiearbPhaseGate::Late => "late",
            TiearbPhaseGate::None => "none",
        }
    }

    /// Does the arbiter fire at this `k_remaining`?
    ///
    /// ⭐ `All` short-circuits WITHOUT calling [`phase_bucket`], so the default
    /// path does not even read the deck — the identity property is structural,
    /// not arithmetic.
    #[inline]
    pub fn fires_at(&self, k_remaining: i64) -> bool {
        match self {
            TiearbPhaseGate::All => true,
            TiearbPhaseGate::None => false,
            TiearbPhaseGate::Early => phase_bucket(k_remaining) == "early",
            TiearbPhaseGate::Mid => phase_bucket(k_remaining) == "mid",
            TiearbPhaseGate::Late => phase_bucket(k_remaining) == "late",
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
    /// Worlds whose FULL arm set completed. ⚠️ On an `Ok` return this is ALWAYS
    /// `B`: [`arbitrate`] propagates the first playout error with `?`, so there
    /// is no code path that averages over a partial world set. The field exists
    /// so the caller can ASSERT that rather than assume it (READ_RULE §0.F
    /// `G-PLY`) — a condition no gate can see is not a condition.
    pub worlds_completed: usize,
}

/// DESIGN §2's arbiter: `B` CRN determinizations SHARED by every arm, a
/// `tier1-greedy` playout to terminal per `(world, arm)`, margin from `seat`,
/// mean over worlds.
///
/// ⚠️ Both modes execute the identical work — the same worlds, the same
/// playouts, the same means, the same argmax. Only the returned arm differs.
///
/// `threads` splits the `B` worlds across `min(b, threads)` scoped OS threads
/// (arms inner). It is a LATENCY knob and NOTHING else: the result is
/// bit-identical at every thread count — same `means` to the bit, same
/// `argmax_arm`, same `chosen`, same error on any failing playout (see
/// [`arbitrate_core`]). `1` (the default everywhere) is the pre-change
/// sequential loop, short-circuit included.
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
    max_plies: usize,
    threads: usize,
) -> Result<ArbOutcome, String> {
    arbitrate_core(
        g,
        arms,
        b,
        salt,
        digest,
        ply,
        mode,
        threads,
        |_j, world, a, playout_seed| {
            // cache = None: the HONEST legal mask, at every thread count. See
            // the module docs — the memo is a python-replay-harness defect and
            // would leak an arm-order side channel into a CRN comparison. A
            // SHARED memo across threads would be that side channel plus a data
            // race, so there is deliberately no per-thread cache either.
            tier1_playout(world, a, seat, playout_seed, max_plies, None).map(|(margin, _plies)| margin)
        },
    )
}

/// The `(world, arm)` engine behind [`arbitrate`], with the playout itself
/// injected so the identity gate can construct failures at a chosen
/// `(j, arm)` (a real `tier1_playout` failure is a deep, state-dependent event
/// that cannot be aimed).
///
/// `playout(j, world, arm, playout_seed) -> margin`. It must be a PURE function
/// of its arguments — that is what makes the world loop parallelisable at all.
///
/// ## Why the reduction is split out from the work (requirement: BIT-IDENTITY)
///
/// f64 addition is not associative, so `sums[i] += margin` in a different `j`
/// order is a different number. The threads therefore only ever WRITE margins
/// into disjoint per-world slots; the fold into `sums` happens after the join,
/// on one thread, in exactly the original `j`-then-arm order. Threads change
/// *when* a playout runs, never *what* is added to what, in which order.
///
/// ## The whole-ply revert, preserved
///
/// Sequentially the first failing `(j, arm)` short-circuits the whole call with
/// `?`. Threaded, every world runs to completion (a thread cannot cancel its
/// siblings) and each world reports EITHER its full arm row OR the first error
/// inside that world — its own determinization first, then arms ascending. The
/// post-join fold then walks worlds in ascending `j` and propagates the first
/// `Err` it meets, so the error that escapes is the error of the first failing
/// `(j, arm)` in SEQUENTIAL order, not whichever thread lost the race. Same
/// error string, same whole-ply revert, at every thread count.
#[allow(clippy::too_many_arguments)]
fn arbitrate_core<F>(
    g: &Game,
    arms: &[i32],
    b: usize,
    salt: &str,
    digest: &str,
    ply: i64,
    mode: TiearbMode,
    threads: usize,
    playout: F,
) -> Result<ArbOutcome, String>
where
    F: Fn(usize, &Game, i32, i64) -> Result<f64, String> + Sync,
{
    if arms.is_empty() {
        return Err("arbitrate called with an empty arm set".to_string());
    }
    let n_arms = arms.len();
    let ply_s = ply.to_string();
    // One world's full arm row, or the first error WITHIN that world. The seeds
    // are pure functions of `(salt, digest, ply, j)` and nothing is shared
    // between worlds, so this closure is order-independent by construction.
    let world_row = |j: usize| -> Result<Vec<f64>, String> {
        let js = j.to_string();
        let world_seed = seed_i64(&[salt, digest, &ply_s, &js]);
        let playout_seed = seed_i64(&[salt, digest, &ply_s, &js, "playout"]);
        let mut rng = MT19937::from_py_int_seed_i64(world_seed);
        let world = reshuffled_determinization(g, &mut rng)?;
        let mut row = Vec::with_capacity(n_arms);
        for &a in arms.iter() {
            row.push(playout(j, &world, a, playout_seed)?);
        }
        Ok(row)
    };

    let n_workers = threads.clamp(1, b.max(1));
    let mut rows: Vec<Result<Vec<f64>, String>> = Vec::with_capacity(b);
    if n_workers <= 1 {
        // The pre-change path, byte for byte in behaviour AND in cost: the
        // first failure short-circuits and the remaining worlds are never run.
        for j in 0..b {
            rows.push(Ok(world_row(j)?));
        }
    } else {
        rows.resize_with(b, || Ok(Vec::new()));
        // ceil(b / workers) CONTIGUOUS worlds per worker — `fair::search_worlds`'s
        // chunking, arms inner.
        let per = b.div_ceil(n_workers);
        let world_row = &world_row;
        std::thread::scope(|s| {
            let mut base = 0usize;
            for chunk in rows.chunks_mut(per) {
                let start = base;
                base += chunk.len();
                s.spawn(move || {
                    for (off, slot) in chunk.iter_mut().enumerate() {
                        *slot = world_row(start + off);
                    }
                });
            }
        });
    }

    let mut sums = vec![0.0f64; n_arms];
    let mut n_playouts = 0usize;
    let mut worlds_completed = 0usize;
    for row in rows {
        // ⚠️ THE `?` IS THE WHOLE-PLY REVERT. A failure in ANY world for ANY arm
        // propagates out of `arbitrate`, so the caller falls back to the
        // champion's own `pooled_q_argmax` pick for the ENTIRE ply. There is
        // deliberately no "average the survivors" path: a partial world set
        // would break the CRN pairing across arms, which is the entire basis of
        // the ARB-vs-RND comparison.
        let row = row?;
        for (i, margin) in row.into_iter().enumerate() {
            sums[i] += margin;
            n_playouts += 1;
        }
        worlds_completed += 1;
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
        worlds_completed,
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
    max_plies: usize,
    threads: usize,
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
    let out = arbitrate(
        g, seat, &arms.arms, b, salt, &digest, ply, mode, max_plies, threads,
    )?;
    Ok(Some((arms, out)))
}

// ===========================================================================
// OM-M1 — REFUTATION-PRICED ARBITRATION (the first kill-gate's instrument)
// ===========================================================================
//
// ⛔ INSTRUMENT ONLY. Spec of record:
// `measurement/omm1_refuter_gate_20260830/PREREG.md`. Nothing below is
// reachable from `arbitrate` / `arbitrate_decision` / any shipped agent — the
// deployed arbiter is untouched, and `G-BITEXACT` (below) is the proof.

/// One leg of a multi-leg arbitration.
///
/// A leg is a (playout-seed stream, continuation policy) pair evaluated over
/// the SAME `B` CRN determinizations as every other leg. `world_seed(j)` is a
/// pure function of `(salt, digest, ply, j)` and does NOT depend on the leg, so
/// all legs are world-paired by construction (`G-CRN`).
#[derive(Clone, Debug)]
pub struct LegSpec {
    /// Reported label. Never enters a seed.
    pub name: String,
    /// Parts appended to the deployed playout-seed parts
    /// `[salt, digest, ply, j, "playout"]`. **EMPTY == the deployed seed
    /// exactly**, which is what makes a leg reproduce [`arbitrate`] bit for bit.
    pub seed_suffix: Vec<String>,
    /// `None` == symmetric: plain `tier1-greedy` on BOTH seats, i.e. the
    /// deployed continuation. `Some(cfg)` arms the OPPONENT of `seat` with
    /// `cfg`'s invasion weights (see [`RefuterConfig`]).
    pub refuter_leaf: Option<LeafConfig>,
}

impl LegSpec {
    /// The deployed leg: deployed seed, symmetric continuation. Its `means` are
    /// bit-identical to [`arbitrate`]'s at the same `(g, seat, arms, b, salt,
    /// digest, ply, max_plies)`.
    pub fn symmetric(name: &str) -> Self {
        LegSpec {
            name: name.to_string(),
            seed_suffix: Vec::new(),
            refuter_leaf: None,
        }
    }

    /// A leg on its OWN playout-seed stream. With `refuter_leaf = None` this is
    /// the PLACEBO of the OM-M1 prereg: same policy class, same cost, same CRN
    /// worlds, differing from the symmetric leg by nothing but the tie-break
    /// stream — the null that separates "the refuter re-ranked" from "half the
    /// worlds were re-rolled".
    pub fn restreamed(name: &str, seed_suffix: &[&str], refuter_leaf: Option<LeafConfig>) -> Self {
        LegSpec {
            name: name.to_string(),
            seed_suffix: seed_suffix.iter().map(|s| s.to_string()).collect(),
            refuter_leaf,
        }
    }
}

/// One leg's raw result. The `margins` matrix is the ONLY thing the harness
/// persists; every statistic in the prereg (`§4.4`) is computed from it in
/// Python, so the read rule can be re-run without re-running a playout.
#[derive(Clone, Debug)]
pub struct LegMatrix {
    pub name: String,
    /// `margins[j][i]` — world `j`, arm `arms[i]`, terminal margin from `seat`.
    pub margins: Vec<Vec<f64>>,
    /// Mean over the `B` worlds, folded in ascending `j` then ascending arm —
    /// the identical order [`arbitrate`] folds in, because f64 addition is not
    /// associative and any other order is a different number.
    pub means: Vec<f64>,
    pub argmax_arm: i32,
    /// Always `b` on an `Ok` return (the whole-ply revert). Exposed so the
    /// caller can ASSERT it (`G-COMPLETE`) rather than assume it.
    pub worlds_completed: usize,
}

/// Every leg's result over one fired ply's shared CRN worlds.
#[derive(Clone, Debug)]
pub struct LegsOutcome {
    pub arms: Vec<i32>,
    pub seat: usize,
    /// The `B` world seeds, identical for every leg. Emitted so `G-CRN` is a
    /// checkable fact and not a claim about the code.
    pub world_seeds: Vec<i64>,
    pub legs: Vec<LegMatrix>,
    pub n_playouts: usize,
}

/// ⛔ **INSTRUMENT ONLY (OM-M1).** [`arbitrate`], run once per leg over ONE
/// shared set of `B` determinizations.
///
/// Contract, in order of importance:
///
/// 1. **`G-BITEXACT`.** A [`LegSpec::symmetric`] leg's `margins`, `means` and
///    `argmax_arm` are bit-identical to [`arbitrate`]'s at the same arguments —
///    same world seeds, same playout seeds, same fold order, same strict-`>`
///    argmax that keeps the earliest arm on a tie. Pinned by
///    [`tests::symmetric_leg_is_bit_identical_to_the_deployed_arbiter`].
/// 2. **`G-CRN`.** `world_seed(j) = seed_i64(salt|digest|ply|j)` for every leg;
///    the determinization is rebuilt per leg from that seed, so legs are paired
///    world-for-world. The seeds are returned for assertion.
/// 3. **`G-COMPLETE`.** The first failing `(leg, j, arm)` propagates with `?`.
///    There is deliberately no "average the survivors" path: a partial world set
///    breaks the CRN pairing the entire comparison rests on.
///
/// `threads` splits the `B` worlds of ONE leg across `min(b, threads)` scoped
/// OS threads (arms inner, legs outer), exactly as [`arbitrate_core`] does, and
/// is a LATENCY knob only — the fold happens after the join, on one thread, in
/// ascending `j`.
#[allow(clippy::too_many_arguments)]
pub fn arbitrate_legs(
    g: &Game,
    seat: usize,
    arms: &[i32],
    b: usize,
    salt: &str,
    digest: &str,
    ply: i64,
    max_plies: usize,
    threads: usize,
    legs: &[LegSpec],
) -> Result<LegsOutcome, String> {
    if arms.is_empty() {
        return Err("arbitrate_legs called with an empty arm set".to_string());
    }
    if legs.is_empty() {
        return Err("arbitrate_legs called with no legs".to_string());
    }
    if seat > 1 {
        return Err(format!("seat must be 0 or 1, got {seat}"));
    }
    let n_arms = arms.len();
    let ply_s = ply.to_string();
    let world_seeds: Vec<i64> = (0..b)
        .map(|j| seed_i64(&[salt, digest, &ply_s, &j.to_string()]))
        .collect();

    let mut out_legs = Vec::with_capacity(legs.len());
    let mut n_playouts = 0usize;
    for leg in legs {
        // The refuter always sits on the OPPONENT of the arbiter's acting seat:
        // OM-M1 asks what a tied candidate is worth against an INVADING
        // opponent, so the invasion must be on the other side of the board.
        let refuter = leg.refuter_leaf.as_ref().map(|cfg| RefuterConfig {
            refuter_seat: 1 - seat,
            leaf: cfg.clone(),
        });
        let world_row = |j: usize| -> Result<Vec<f64>, String> {
            let js = j.to_string();
            // The playout seed's DEPLOYED parts, then the leg's suffix. An
            // empty suffix reproduces `arbitrate`'s seed exactly.
            let mut parts: Vec<&str> = vec![salt, digest, &ply_s, &js, "playout"];
            for s in &leg.seed_suffix {
                parts.push(s.as_str());
            }
            let playout_seed = seed_i64(&parts);
            let mut rng = MT19937::from_py_int_seed_i64(world_seeds[j]);
            let world = reshuffled_determinization(g, &mut rng)?;
            let mut row = Vec::with_capacity(n_arms);
            for &a in arms.iter() {
                // cache = None: the HONEST legal mask, matching `arbitrate`.
                let (margin, _plies) = tier1_playout_with(
                    &world,
                    a,
                    seat,
                    playout_seed,
                    max_plies,
                    None,
                    refuter.clone(),
                )?;
                row.push(margin);
            }
            Ok(row)
        };

        let n_workers = threads.clamp(1, b.max(1));
        let mut rows: Vec<Result<Vec<f64>, String>> = Vec::with_capacity(b);
        if n_workers <= 1 {
            for j in 0..b {
                rows.push(Ok(world_row(j)?));
            }
        } else {
            rows.resize_with(b, || Ok(Vec::new()));
            let per = b.div_ceil(n_workers);
            let world_row = &world_row;
            std::thread::scope(|s| {
                let mut base = 0usize;
                for chunk in rows.chunks_mut(per) {
                    let start = base;
                    base += chunk.len();
                    s.spawn(move || {
                        for (off, slot) in chunk.iter_mut().enumerate() {
                            *slot = world_row(start + off);
                        }
                    });
                }
            });
        }

        // The fold: ascending `j`, ascending arm — `arbitrate_core`'s order.
        let mut sums = vec![0.0f64; n_arms];
        let mut margins: Vec<Vec<f64>> = Vec::with_capacity(b);
        let mut worlds_completed = 0usize;
        for row in rows {
            let row = row?;
            for (i, margin) in row.iter().enumerate() {
                sums[i] += *margin;
                n_playouts += 1;
            }
            margins.push(row);
            worlds_completed += 1;
        }
        let denom = b.max(1) as f64;
        let means: Vec<f64> = sums.iter().map(|s| s / denom).collect();
        let mut best = 0usize;
        for i in 1..n_arms {
            if means[i] > means[best] {
                best = i;
            }
        }
        out_legs.push(LegMatrix {
            name: leg.name.clone(),
            margins,
            means,
            argmax_arm: arms[best],
            worlds_completed,
        });
    }

    Ok(LegsOutcome {
        arms: arms.to_vec(),
        seat,
        world_seeds,
        legs: out_legs,
        n_playouts,
    })
}

/// ⛔ **INSTRUMENT ONLY (OM-M1).** [`arbitrate_decision`]'s trigger + arm set,
/// then [`arbitrate_legs`] instead of [`arbitrate`].
///
/// The trigger, the arm build, the cap, the champion-pick append and the
/// "fewer than 2 arms after dedupe ⇒ NOT fired" rule are the DEPLOYED ones,
/// re-used rather than re-implemented — the whole point of the gate is that its
/// fire set is the arbiter's own.
#[allow(clippy::too_many_arguments)]
pub fn arbitrate_decision_legs(
    g: &Game,
    champ_pick: i32,
    leaf_cfg: &LeafConfig,
    b: usize,
    j: usize,
    salt: &str,
    eps: f64,
    ply: i64,
    max_plies: usize,
    threads: usize,
    legs: &[LegSpec],
    scratch: &mut LeafScratch,
) -> Result<Option<(ArmSet, LegsOutcome)>, String> {
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
        return Ok(None);
    }
    let out = arbitrate_legs(
        g, seat, &arms.arms, b, salt, &digest, ply, max_plies, threads, legs,
    )?;
    Ok(Some((arms, out)))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// ⭐ THE GOLDEN TABLE (`DESIGN.md` §2.2 / `READ_RULE.md` §3), pinned to the
    /// exact seven values the design executed the canonical python function to
    /// obtain. The python side asserts the same table against
    /// `sample_agreement_roots.phase_bucket` itself
    /// (`tests/test_tiearb_phase_gate.py`), so the two implementations cannot
    /// drift apart silently.
    #[test]
    fn phase_bucket_golden_table() {
        for (k, want) in [
            (71, "early"),
            (49, "early"),
            (48, "late"),
            (47, "mid"),
            (25, "mid"),
            (24, "late"),
            (23, "late"),
        ] {
            assert_eq!(phase_bucket(k), want, "phase_bucket({k})");
        }
    }

    /// ⚠️⚠️ The edge is REPRODUCED, NOT REPAIRED. Stated as its own test so a
    /// well-meaning "fix" fails loudly with the reason attached.
    #[test]
    fn phase_bucket_boundary_falls_through_to_late() {
        assert_eq!(phase_bucket(48), "late", "k=48 must NOT be early");
        assert_eq!(phase_bucket(24), "late", "k=24 must NOT be mid");
        // ... and the neighbours on both sides are unaffected.
        assert_eq!(phase_bucket(50), "early");
        assert_eq!(phase_bucket(49), "early");
        assert_eq!(phase_bucket(47), "mid");
        assert_eq!(phase_bucket(26), "mid");
        assert_eq!(phase_bucket(25), "mid");
        assert_eq!(phase_bucket(23), "late");
    }

    /// The whole `k_remaining` range a real game spans (71 -> 0) partitions
    /// into exactly the three windows the read rule freezes, `48`/`24`
    /// included in `late`.
    #[test]
    fn phase_windows_partition_the_whole_range() {
        let mut early = Vec::new();
        let mut mid = Vec::new();
        let mut late = Vec::new();
        for k in 0..=71i64 {
            match phase_bucket(k) {
                "early" => early.push(k),
                "mid" => mid.push(k),
                "late" => late.push(k),
                other => panic!("phase_bucket({k}) returned {other:?}"),
            }
        }
        assert_eq!(early, (49..=71).collect::<Vec<i64>>());
        assert_eq!(mid, (25..=47).collect::<Vec<i64>>());
        let mut want_late: Vec<i64> = (0..=23).collect();
        want_late.push(24);
        want_late.push(48);
        want_late.sort_unstable();
        assert_eq!(late, want_late);
        assert_eq!(early.len() + mid.len() + late.len(), 72);
    }

    /// Out-of-range inputs take the fall-through, exactly as the python does.
    #[test]
    fn phase_bucket_out_of_range_falls_through() {
        assert_eq!(phase_bucket(-1), "late");
        assert_eq!(phase_bucket(-5), "late");
        assert_eq!(phase_bucket(1_000_000_000), "late");
    }

    #[test]
    fn phase_gate_parse_round_trips_and_fails_closed() {
        for s in ["all", "early", "mid", "late", "none"] {
            assert_eq!(TiearbPhaseGate::parse(s).unwrap().value(), s);
        }
        for bad in ["", "ALL", "Early", "full", "phase:early", "0"] {
            assert!(
                TiearbPhaseGate::parse(bad).is_err(),
                "{bad:?} must NOT parse (a silent default is the inverted-liveness hazard)"
            );
        }
    }

    /// `All` fires everywhere, `None` nowhere, and each window fires exactly on
    /// its own bucket — including at the two fall-through k's, where `late`
    /// fires and `early`/`mid` do not.
    #[test]
    fn phase_gate_fires_at_matches_the_bucket() {
        for k in 0..=71i64 {
            let b = phase_bucket(k);
            assert!(TiearbPhaseGate::All.fires_at(k), "All must fire at k={k}");
            assert!(!TiearbPhaseGate::None.fires_at(k), "None must not fire at k={k}");
            assert_eq!(TiearbPhaseGate::Early.fires_at(k), b == "early", "k={k}");
            assert_eq!(TiearbPhaseGate::Mid.fires_at(k), b == "mid", "k={k}");
            assert_eq!(TiearbPhaseGate::Late.fires_at(k), b == "late", "k={k}");
            // exactly one window gate fires at every k
            let n = [TiearbPhaseGate::Early, TiearbPhaseGate::Mid, TiearbPhaseGate::Late]
                .iter()
                .filter(|g| g.fires_at(k))
                .count();
            assert_eq!(n, 1, "exactly one window must own k={k}");
        }
        assert!(!TiearbPhaseGate::Early.fires_at(48), "ARB_EARLY must NOT fire at k=48");
        assert!(TiearbPhaseGate::Late.fires_at(48));
        assert!(!TiearbPhaseGate::Mid.fires_at(24), "ARB_MID must NOT fire at k=24");
        assert!(TiearbPhaseGate::Late.fires_at(24));
    }

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
            TIEARB_MAX_PLIES,
            1,
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
        let a = arbitrate(&g, seat, &arms, 2, "s", "d", 3, TiearbMode::Argmax, TIEARB_MAX_PLIES, 1).unwrap();
        let r = arbitrate(&g, seat, &arms, 2, "s", "d", 3, TiearbMode::Random, TIEARB_MAX_PLIES, 1).unwrap();
        assert_eq!(a.n_playouts, r.n_playouts, "the two modes must cost the same");
        for (x, y) in a.means.iter().zip(r.means.iter()) {
            assert_eq!(x.to_bits(), y.to_bits(), "random mode changed the playouts");
        }
        assert_eq!(a.argmax_arm, r.argmax_arm, "the argmax is computed in both");
        assert_eq!(a.chosen, a.argmax_arm);
        assert!(arms.contains(&r.chosen));
        // seeded => reproducible
        let r2 = arbitrate(&g, seat, &arms, 2, "s", "d", 3, TiearbMode::Random, TIEARB_MAX_PLIES, 1).unwrap();
        assert_eq!(r.chosen, r2.chosen);
        // ...and it is a real draw: some (digest, ply) picks a non-first arm.
        let mut saw_other = false;
        for ply in 0..24i64 {
            let x = arbitrate(&g, seat, &arms, 1, "s", "d", ply, TiearbMode::Random, TIEARB_MAX_PLIES, 1).unwrap();
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
            TIEARB_MAX_PLIES,
            1,
            &mut s,
        )
        .unwrap();
        assert!(out.is_none());
    }

    // ---------------------------------------------------------------------
    // THE WORLD-THREADING IDENTITY GATE (2026-08-21).
    //
    // Threading `arbitrate`'s `B x arms` playouts is a LATENCY lever that owes
    // no strength claim — and it owes none EXACTLY BECAUSE it changes no
    // number. These are the tests that make that a checked property rather
    // than an argument: bit-equal `ArbOutcome` and bit-equal error behaviour at
    // every thread count, on real states and on injected failures.
    // ---------------------------------------------------------------------

    /// Everything an `ArbOutcome` carries, reduced to a bit-comparable value.
    /// `means` go through `to_bits`, because "equal to a tolerance" is exactly
    /// the claim this gate is NOT allowed to settle for.
    fn outcome_bits(o: &ArbOutcome) -> (Vec<i32>, Vec<u64>, i32, i32, usize, usize) {
        (
            o.arms.clone(),
            o.means.iter().map(|m| m.to_bits()).collect(),
            o.argmax_arm,
            o.chosen,
            o.n_playouts,
            o.worlds_completed,
        )
    }

    /// A margin schedule chosen so that a REORDERED fold would be visibly
    /// wrong: `2^53` in world 0 and `1.0` in every later world. Summed in `j`
    /// order every `+ 1.0` is swallowed by the rounding and the total is
    /// exactly `2^53 + arm`; summed in any order that accumulates the ones
    /// first, they survive and the total is larger. So this test fails if the
    /// threaded path ever reduces per-thread partials instead of folding the
    /// per-world slots in the original order.
    fn synthetic_margin(j: usize, arm: i32) -> f64 {
        if j == 0 {
            9_007_199_254_740_992.0 + arm as f64
        } else {
            1.0
        }
    }

    /// The reduction is order-preserving at every `(B, arms, threads)`.
    ///
    /// Uses the injected-playout core so the whole matrix costs no playouts —
    /// the property under test is the FOLD, not the engine.
    #[test]
    fn the_threaded_fold_is_the_sequential_fold_bit_for_bit() {
        let g = tiles_root("28000000000", 30);
        let legal = g.legal_actions();
        for b in [0usize, 1, 2, 3, 16, 32, 64, 65] {
            for n_arms in 1..=5usize {
                let arms: Vec<i32> = legal.iter().copied().take(n_arms).collect();
                // the sequential fold, written out longhand
                let mut want = vec![0.0f64; n_arms];
                for j in 0..b {
                    for (i, &a) in arms.iter().enumerate() {
                        want[i] += synthetic_margin(j, a);
                    }
                }
                let denom = b.max(1) as f64;
                let want: Vec<u64> = want.iter().map(|s| (s / denom).to_bits()).collect();
                for t in [1usize, 2, 3, 4, 8, 64] {
                    let out = arbitrate_core(
                        &g,
                        &arms,
                        b,
                        "s",
                        "d",
                        11,
                        TiearbMode::Argmax,
                        t,
                        |j, _w, a, _seed| Ok(synthetic_margin(j, a)),
                    )
                    .unwrap();
                    let got: Vec<u64> = out.means.iter().map(|m| m.to_bits()).collect();
                    assert_eq!(
                        got, want,
                        "means differ at B={b}, arms={n_arms}, threads={t}"
                    );
                    assert_eq!(out.n_playouts, b * n_arms);
                    assert_eq!(out.worlds_completed, b);
                }
            }
        }
    }

    /// WHOLE-PLY REVERT, and the FIRST failure in SEQUENTIAL order wins.
    ///
    /// Two playouts are made to fail with DISTINGUISHABLE messages at
    /// `(j, arm)` pairs deliberately placed so that the thread that finishes
    /// first is not the one whose error must escape: `(5, 0)` lands in an early
    /// chunk at every thread count, `(2, 3)` earlier still, and the world-major
    /// order says `(2, 3)` is the one the sequential loop would have hit first.
    #[test]
    fn the_first_failure_in_sequential_order_wins_at_every_thread_count() {
        let g = tiles_root("28000000000", 30);
        let legal = g.legal_actions();
        let arms: Vec<i32> = legal.iter().copied().take(5).collect();
        let b = 32usize;
        // (failing (j, arm-index) pairs, the message that must escape)
        let cases: Vec<(Vec<(usize, usize)>, &str)> = vec![
            (vec![(5, 0), (2, 3)], "boom j=2 i=3"),
            (vec![(2, 3), (2, 1)], "boom j=2 i=1"),
            (vec![(31, 0), (0, 4)], "boom j=0 i=4"),
            (vec![(17, 2)], "boom j=17 i=2"),
            // every world fails: the first is still (0, 0)
            ((0..b).map(|j| (j, 0)).collect(), "boom j=0 i=0"),
        ];
        for (fails, want) in cases {
            for t in [1usize, 2, 4, 8, 32] {
                let fails = &fails;
                let arms_ref = &arms;
                let err = arbitrate_core(
                    &g,
                    &arms,
                    b,
                    "s",
                    "d",
                    3,
                    TiearbMode::Argmax,
                    t,
                    move |j, _w, a, _seed| {
                        let i = arms_ref.iter().position(|&x| x == a).unwrap();
                        if fails.contains(&(j, i)) {
                            Err(format!("boom j={j} i={i}"))
                        } else {
                            Ok(1.0)
                        }
                    },
                )
                .expect_err("the whole ply must revert, not average the survivors");
                assert_eq!(err, want, "wrong error escaped at threads={t}");
            }
        }
    }

    /// The gate proper: REAL `tier1-greedy` playouts, a spread of states x arm
    /// sets x `B in {16, 32, 64}`, `threads in {2, 4, 8}` each bit-identical to
    /// the sequential loop — `means` included, in BOTH modes.
    ///
    /// (Late-game roots on purpose: same code path, ~20x cheaper playouts.
    /// carc-core banks no serialized fixture states, so these are built the way
    /// every other test in this module builds them — `Game::from_seed` + a
    /// deterministic walk — which also side-steps the parked banked-fixture
    /// replay panic at `engine/mod.rs:411` entirely.)
    #[test]
    fn threading_is_bit_identical_to_sequential() {
        for (seed, from) in [("28000000000", 132usize), ("42", 130)] {
            let g = tiles_root(seed, from);
            let legal = g.legal_actions();
            let seat = g.state.current_player;
            assert!(legal.len() >= 3, "need >= 3 legal actions at {seed}/{from}");
            // (B, arms, modes). The full mode cross only at B = 16: the mode
            // changes nothing but the last line's `chosen`, and the cheap
            // `the_threaded_fold_is_the_sequential_fold_bit_for_bit` already
            // covers the fold at B in {16, 32, 64, 65} x 1..=5 arms x 6 thread
            // counts. This test is here for the REAL playouts, and a real
            // playout costs ~10 ms.
            let cases: [(usize, usize, &[TiearbMode]); 4] = [
                (16, 2, &[TiearbMode::Argmax, TiearbMode::Random]),
                (16, 3, &[TiearbMode::Argmax, TiearbMode::Random]),
                (32, 3, &[TiearbMode::Argmax]),
                (64, 2, &[TiearbMode::Argmax]),
            ];
            for (b, n_arms, modes) in cases {
                let arms: Vec<i32> = legal.iter().copied().take(n_arms).collect();
                {
                    for &mode in modes {
                        let want = arbitrate(
                            &g,
                            seat,
                            &arms,
                            b,
                            TIEARB_SALT_OF_RECORD,
                            "d",
                            9,
                            mode,
                            TIEARB_MAX_PLIES,
                            1,
                        )
                        .unwrap();
                        for t in [2usize, 4, 8] {
                            let got = arbitrate(
                                &g,
                                seat,
                                &arms,
                                b,
                                TIEARB_SALT_OF_RECORD,
                                "d",
                                9,
                                mode,
                                TIEARB_MAX_PLIES,
                                t,
                            )
                            .unwrap();
                            assert_eq!(
                                outcome_bits(&got),
                                outcome_bits(&want),
                                "threads={t} changed the outcome at seed={seed}, \
                                 from={from}, arms={n_arms}, B={b}, mode={}",
                                mode.value()
                            );
                        }
                    }
                }
            }
        }
    }

    /// **GATE §3a (`measurement/arb_costopt_prep/GATES_DEFERRED.md`) — the
    /// tier1 scorer swap is identical to the LEGACY scorer at production
    /// `arbitrate` shapes, under threads.**
    ///
    /// ## The R9 constraint and how this gate answers it
    ///
    /// [`crate::tier1::with_legacy_scorer`] sets a THREAD-LOCAL flag. It does
    /// NOT propagate into [`arbitrate_core`]'s `std::thread::scope` workers, so
    /// an identity gate written as `with_legacy_scorer(|| arbitrate(.., t))`
    /// with `t > 1` would run the flat scorer in every worker and compare
    /// **flat against flat** — a green light that proves nothing. Two ways out:
    ///
    /// 1. propagate the TLS into the scoped workers for the legacy leg, or
    /// 2. **run the LEGACY leg single-threaded and the FLAT leg threaded.**
    ///
    /// This gate takes **(2)**, deliberately:
    ///
    /// * It needs no production-code change. Option (1) means teaching
    ///   `arbitrate_core` about a gates-only flag — new code on the deployed
    ///   path, written to test the deployed path, whose own correctness would
    ///   then be the thing standing between the gate and the truth.
    /// * It is the STRICTLY STRONGER contrast. `arbitrate`'s result is
    ///   thread-count invariant BY DESIGN (the fold is order-preserving; see
    ///   the module docs and `threading_is_bit_identical_to_sequential`), so
    ///   `legacy@t=1` is a fixed, thread-free reference. Comparing
    ///   `flat@t ∈ {1,2,4,8}` against it closes both questions at once — "is
    ///   the flat scorer the legacy scorer" AND "do the flat scorer's
    ///   THREAD-LOCAL `Decomp`/`Scratch` buffers leak across workers" — in one
    ///   assertion. Option (1) would have compared `legacy@8` to `flat@8`,
    ///   which tests the buffers only against a reference that has no buffers
    ///   to leak, and adds a TLS-propagation mechanism that could itself paper
    ///   over a leak.
    /// * The failure it is built to catch — a shared-buffer race — is
    ///   thread-count DEPENDENT, so a green run at `t=8` against a `t=1`
    ///   reference is exactly the receipt owed.
    ///
    /// `border_fallbacks` is asserted 0 over the whole gate: the legacy
    /// fallback never fired, so every compared value came from the flat route.
    #[test]
    fn the_flat_scorer_matches_the_legacy_scorer_at_every_thread_count() {
        let _lock = crate::tier1::BORDER_FALLBACK_GATE
            .lock()
            .unwrap_or_else(|e| e.into_inner());
        crate::tier1::reset_border_fallbacks();
        let mut n_cases = 0usize;
        for (seed, from) in [("28000000000", 132usize), ("42", 130)] {
            let g = tiles_root(seed, from);
            let legal = g.legal_actions();
            let seat = g.state.current_player;
            assert!(legal.len() >= 3, "need >= 3 legal actions at {seed}/{from}");
            let cases: [(usize, usize, &[TiearbMode]); 4] = [
                (16, 2, &[TiearbMode::Argmax, TiearbMode::Random]),
                (16, 3, &[TiearbMode::Argmax, TiearbMode::Random]),
                (32, 3, &[TiearbMode::Argmax]),
                (64, 2, &[TiearbMode::Argmax]),
            ];
            for (b, n_arms, modes) in cases {
                let arms: Vec<i32> = legal.iter().copied().take(n_arms).collect();
                for &mode in modes {
                    // THE REFERENCE: the legacy `count_final_scores` scorer,
                    // SINGLE-THREADED so the thread-local force flag is in
                    // scope for every playout it drives.
                    let want = crate::tier1::with_legacy_scorer(|| {
                        arbitrate(
                            &g,
                            seat,
                            &arms,
                            b,
                            TIEARB_SALT_OF_RECORD,
                            "d",
                            9,
                            mode,
                            TIEARB_MAX_PLIES,
                            1,
                        )
                    })
                    .unwrap();
                    for t in [1usize, 2, 4, 8] {
                        let got = arbitrate(
                            &g,
                            seat,
                            &arms,
                            b,
                            TIEARB_SALT_OF_RECORD,
                            "d",
                            9,
                            mode,
                            TIEARB_MAX_PLIES,
                            t,
                        )
                        .unwrap();
                        assert_eq!(
                            outcome_bits(&got),
                            outcome_bits(&want),
                            "the flat scorer at threads={t} differs from the legacy \
                             scorer at seed={seed}, from={from}, arms={n_arms}, B={b}, \
                             mode={}",
                            mode.value()
                        );
                        n_cases += 1;
                    }
                }
            }
        }
        assert_eq!(
            crate::tier1::border_fallbacks(),
            0,
            "the border fallback fired — some compared values did NOT come from the \
             flat route, so this gate did not grade what it claims to"
        );
        println!(
            "GATE 3a: {n_cases} threaded arbitrate outcomes bit-identical to the \
             single-threaded LEGACY scorer; border fallbacks 0"
        );
    }

    /// The same identity on the FAILING path, with real playouts: an illegal
    /// arm makes `tier1_playout` error inside every world, and the message that
    /// escapes must be the same one at every thread count. A second case drives
    /// the OTHER real failure mode — the `max_plies` guard.
    #[test]
    fn a_real_playout_failure_reverts_the_whole_ply_at_every_thread_count() {
        let g = tiles_root("28000000000", 132);
        let legal = g.legal_actions();
        let seat = g.state.current_player;
        // arm 1 is illegal -> world 0, arm 1 is the first failure everywhere.
        let arms = [legal[0], 999_999, legal[1]];
        let seq = arbitrate(
            &g,
            seat,
            &arms,
            32,
            TIEARB_SALT_OF_RECORD,
            "d",
            5,
            TiearbMode::Argmax,
            TIEARB_MAX_PLIES,
            1,
        )
        .expect_err("an illegal arm must fail the whole ply");
        for t in [2usize, 4, 8] {
            let got = arbitrate(
                &g,
                seat,
                &arms,
                32,
                TIEARB_SALT_OF_RECORD,
                "d",
                5,
                TiearbMode::Argmax,
                TIEARB_MAX_PLIES,
                t,
            )
            .expect_err("an illegal arm must fail the whole ply");
            assert_eq!(got, seq, "the escaping error changed at threads={t}");
        }
        // ...and the ply ceiling, the failure mode the deployed arbiter
        // actually meets.
        let legal_arms = [legal[0], legal[1]];
        let seq = arbitrate(
            &g,
            seat,
            &legal_arms,
            32,
            TIEARB_SALT_OF_RECORD,
            "d",
            5,
            TiearbMode::Argmax,
            2,
            1,
        )
        .expect_err("max_plies = 2 must abort every playout");
        assert!(seq.contains("max_plies=2"), "unexpected error: {seq}");
        for t in [2usize, 4, 8] {
            let got = arbitrate(
                &g,
                seat,
                &legal_arms,
                32,
                TIEARB_SALT_OF_RECORD,
                "d",
                5,
                TiearbMode::Argmax,
                2,
                t,
            )
            .expect_err("max_plies = 2 must abort every playout");
            assert_eq!(got, seq, "the escaping error changed at threads={t}");
        }
    }

    /// `arbitrate_decision` passes the knob through, and the whole trigger +
    /// arbitration is thread-count invariant end to end.
    #[test]
    fn arbitrate_decision_is_thread_count_invariant() {
        let cfg = LeafConfig::curve125();
        let mut s = LeafScratch::new();
        // Walk until the trigger actually fires, so this is not a vacuous
        // `Ok(None) == Ok(None)`.
        let mut g = tiles_root("28000000000", 120);
        let mut fired = None;
        for _ in 0..40 {
            let champ = g.legal_actions()[0];
            let out = arbitrate_decision(
                &g,
                champ,
                &cfg,
                8,
                4,
                TIEARB_SALT_OF_RECORD,
                0.0,
                13,
                TiearbMode::Argmax,
                TIEARB_MAX_PLIES,
                1,
                &mut s,
            )
            .unwrap();
            if let Some((arms, o)) = out {
                fired = Some((g.clone(), champ, arms, o));
                break;
            }
            let l = g.legal_actions();
            g.advance(l[l.len() / 2]).unwrap();
            while g.state.phase != Phase::Tiles || g.legal_actions().len() < 2 {
                let l = g.legal_actions();
                g.advance(l[l.len() / 2]).unwrap();
            }
        }
        let (g, champ, arms, want) = fired.expect("the trigger never fired in 40 tile plies");
        assert!(arms.arms.len() >= 2);
        for t in [2usize, 4, 8] {
            let (arms_t, got) = arbitrate_decision(
                &g,
                champ,
                &cfg,
                8,
                4,
                TIEARB_SALT_OF_RECORD,
                0.0,
                13,
                TiearbMode::Argmax,
                TIEARB_MAX_PLIES,
                t,
                &mut s,
            )
            .unwrap()
            .expect("the trigger must fire identically at every thread count");
            assert_eq!(arms_t.arms, arms.arms, "arm set differs at threads={t}");
            assert_eq!(
                outcome_bits(&got),
                outcome_bits(&want),
                "arbitrate_decision differs at threads={t}"
            );
        }
    }

    // ---------------------------------------------------------------------
    // OM-M1 — the refuter-leg instrument's golden gates
    // ---------------------------------------------------------------------

    /// The OM-M1 `R_max` (ceiling) refuter leaf.
    fn refuter_max() -> LeafConfig {
        let mut c = LeafConfig::curve125();
        c.invasion_alpha = 1.0;
        c.invasion_alpha_cap = 11.0;
        c.invasion_beta = 1.0;
        c
    }

    /// The `R_ref` dose: the shape-B invader OPPONENT OF RECORD
    /// (`measurement/invasion_screen_r3_prep/DESIGN.md`, `alpha 0.09 @ cap 11.0`).
    fn refuter_of_record() -> LeafConfig {
        let mut c = LeafConfig::curve125();
        c.invasion_alpha = 0.09;
        c.invasion_alpha_cap = 11.0;
        c
    }

    fn leg_bits(l: &LegMatrix) -> (Vec<Vec<u64>>, Vec<u64>, i32, usize) {
        (
            l.margins
                .iter()
                .map(|r| r.iter().map(|v| v.to_bits()).collect())
                .collect(),
            l.means.iter().map(|m| m.to_bits()).collect(),
            l.argmax_arm,
            l.worlds_completed,
        )
    }

    /// ⭐ `G-BITEXACT` — the instrument's symmetric leg IS the deployed
    /// arbiter, to the bit. If this ever fails, every flip rate the gate
    /// reports is measuring the harness instead of the mechanism.
    #[test]
    fn symmetric_leg_is_bit_identical_to_the_deployed_arbiter() {
        let g = tiles_root("28000000000", 40);
        let seat = g.state.current_player;
        let arms: Vec<i32> = g.legal_actions().into_iter().take(3).collect();
        let digest = g.state_digest();
        let b = 6usize;
        for &threads in &[1usize, 3] {
            let want = arbitrate(
                &g,
                seat,
                &arms,
                b,
                TIEARB_SALT_OF_RECORD,
                &digest,
                17,
                TiearbMode::Argmax,
                TIEARB_MAX_PLIES,
                threads,
            )
            .unwrap();
            let got = arbitrate_legs(
                &g,
                seat,
                &arms,
                b,
                TIEARB_SALT_OF_RECORD,
                &digest,
                17,
                TIEARB_MAX_PLIES,
                threads,
                &[LegSpec::symmetric("S")],
            )
            .unwrap();
            let leg = &got.legs[0];
            assert_eq!(
                leg.means.iter().map(|m| m.to_bits()).collect::<Vec<_>>(),
                want.means.iter().map(|m| m.to_bits()).collect::<Vec<_>>(),
                "G-BITEXACT: symmetric-leg means differ from arbitrate at threads={threads}"
            );
            assert_eq!(leg.argmax_arm, want.argmax_arm, "G-BITEXACT: argmax differs");
            assert_eq!(leg.worlds_completed, b, "G-COMPLETE");
            assert_eq!(got.arms, want.arms);
            for j in 0..b {
                assert_eq!(
                    got.world_seeds[j],
                    seed_i64(&[TIEARB_SALT_OF_RECORD, &digest, "17", &j.to_string()]),
                    "G-CRN: world seed {j}"
                );
            }
        }
    }

    /// ⭐ `G-INERT` — a refuter leg whose invasion weights are all `0.0` is the
    /// PLACEBO leg to the bit, not merely equal to it. This is what licenses
    /// reading `R − P` as "the policy change alone": if the armed-but-zero path
    /// diverged, the two legs would differ by an unpriced code path as well.
    #[test]
    fn refuter_with_zero_weights_is_bit_identical_to_plain_greedy() {
        let g = tiles_root("28000000001", 40);
        let seat = g.state.current_player;
        let arms: Vec<i32> = g.legal_actions().into_iter().take(3).collect();
        let digest = g.state_digest();
        let inert = LeafConfig::curve125(); // every invasion weight defaults to 0.0
        assert!(RefuterConfig {
            refuter_seat: 1 - seat,
            leaf: inert.clone()
        }
        .is_inert());
        let out = arbitrate_legs(
            &g,
            seat,
            &arms,
            5,
            TIEARB_SALT_OF_RECORD,
            &digest,
            9,
            TIEARB_MAX_PLIES,
            1,
            &[
                LegSpec::restreamed("P", &["omm1-leg2"], None),
                LegSpec::restreamed("R0", &["omm1-leg2"], Some(inert)),
            ],
        )
        .unwrap();
        assert_eq!(
            leg_bits(&out.legs[1]),
            leg_bits(&out.legs[0]),
            "G-INERT: an all-zero refuter must be the placebo leg bit for bit"
        );
    }

    /// The placebo leg is a REAL null: same policy, same worlds, DIFFERENT
    /// stream.
    #[test]
    fn the_placebo_leg_shares_worlds_but_not_the_playout_stream() {
        let g = tiles_root("28000000002", 40);
        let seat = g.state.current_player;
        let arms: Vec<i32> = g.legal_actions().into_iter().take(3).collect();
        let digest = g.state_digest();
        let out = arbitrate_legs(
            &g,
            seat,
            &arms,
            8,
            TIEARB_SALT_OF_RECORD,
            &digest,
            21,
            TIEARB_MAX_PLIES,
            1,
            &[
                LegSpec::symmetric("S"),
                LegSpec::restreamed("P", &["omm1-leg2"], None),
            ],
        )
        .unwrap();
        assert_eq!(out.legs[0].margins.len(), out.legs[1].margins.len());
        assert_eq!(out.world_seeds.len(), 8);
        assert_ne!(
            seed_i64(&[TIEARB_SALT_OF_RECORD, &digest, "21", "0", "playout"]),
            seed_i64(&[
                TIEARB_SALT_OF_RECORD,
                &digest,
                "21",
                "0",
                "playout",
                "omm1-leg2"
            ]),
            "the placebo must not reuse the deployed playout seed"
        );
    }

    /// An armed leg is genuinely a different computation — otherwise the gate
    /// would report a structural zero no matter what the mechanism does.
    #[test]
    fn an_armed_refuter_leg_actually_changes_something() {
        let mut any_change = false;
        for seed in ["28000000000", "28000000001", "28000000002", "28000000003"] {
            let g = tiles_root(seed, 40);
            let seat = g.state.current_player;
            let arms: Vec<i32> = g.legal_actions().into_iter().take(3).collect();
            if arms.len() < 2 {
                continue;
            }
            let digest = g.state_digest();
            let out = arbitrate_legs(
                &g,
                seat,
                &arms,
                8,
                TIEARB_SALT_OF_RECORD,
                &digest,
                31,
                TIEARB_MAX_PLIES,
                1,
                &[
                    LegSpec::restreamed("P", &["omm1-leg2"], None),
                    LegSpec::restreamed("Rmax", &["omm1-leg2"], Some(refuter_max())),
                    LegSpec::restreamed("Rref", &["omm1-leg2"], Some(refuter_of_record())),
                ],
            )
            .unwrap();
            if leg_bits(&out.legs[1]) != leg_bits(&out.legs[0]) {
                any_change = true;
            }
            assert_eq!(out.legs[2].worlds_completed, 8, "G-COMPLETE on the R_ref leg");
        }
        assert!(
            any_change,
            "an armed R_max refuter changed no margin on any of 4 positions x 8 \
             worlds x 3 arms — the instrument would report a structural zero"
        );
    }

    /// Threading is a latency knob on the multi-leg path too.
    #[test]
    fn arbitrate_legs_is_thread_count_invariant() {
        let g = tiles_root("28000000004", 40);
        let seat = g.state.current_player;
        let arms: Vec<i32> = g.legal_actions().into_iter().take(2).collect();
        let digest = g.state_digest();
        let specs = [
            LegSpec::symmetric("S"),
            LegSpec::restreamed("Rmax", &["omm1-leg2"], Some(refuter_max())),
        ];
        let want = arbitrate_legs(
            &g, seat, &arms, 6, TIEARB_SALT_OF_RECORD, &digest, 5, TIEARB_MAX_PLIES, 1, &specs,
        )
        .unwrap();
        for t in [2usize, 4, 6] {
            let got = arbitrate_legs(
                &g, seat, &arms, 6, TIEARB_SALT_OF_RECORD, &digest, 5, TIEARB_MAX_PLIES, t, &specs,
            )
            .unwrap();
            for (a, b) in got.legs.iter().zip(want.legs.iter()) {
                assert_eq!(
                    leg_bits(a),
                    leg_bits(b),
                    "leg {} differs at threads={t}",
                    a.name
                );
            }
            assert_eq!(got.world_seeds, want.world_seeds);
        }
    }

    /// The deployed `B = 16` arbitration is the first 16 worlds of a `B = 64`
    /// run, bit for bit — the world seed does not depend on `B`. The prereg
    /// leans on this to recover the deployed pick for free.
    #[test]
    fn a_wider_run_contains_the_narrower_one_world_for_world() {
        let g = tiles_root("28000000005", 40);
        let seat = g.state.current_player;
        let arms: Vec<i32> = g.legal_actions().into_iter().take(2).collect();
        let digest = g.state_digest();
        let narrow = arbitrate_legs(
            &g,
            seat,
            &arms,
            4,
            TIEARB_SALT_OF_RECORD,
            &digest,
            11,
            TIEARB_MAX_PLIES,
            1,
            &[LegSpec::symmetric("S")],
        )
        .unwrap();
        let wide = arbitrate_legs(
            &g,
            seat,
            &arms,
            12,
            TIEARB_SALT_OF_RECORD,
            &digest,
            11,
            TIEARB_MAX_PLIES,
            1,
            &[LegSpec::symmetric("S")],
        )
        .unwrap();
        assert_eq!(narrow.world_seeds, wide.world_seeds[..4]);
        for j in 0..4 {
            assert_eq!(
                narrow.legs[0].margins[j]
                    .iter()
                    .map(|v| v.to_bits())
                    .collect::<Vec<_>>(),
                wide.legs[0].margins[j]
                    .iter()
                    .map(|v| v.to_bits())
                    .collect::<Vec<_>>(),
                "world {j} must be identical at B=4 and B=12"
            );
        }
    }

    /// `arbitrate_decision_legs` fires on exactly the plies `arbitrate_decision`
    /// fires on, with exactly the same arm set — the gate's population IS the
    /// deployed arbiter's.
    #[test]
    fn the_multi_leg_decision_fires_on_the_deployed_trigger() {
        let cfg = LeafConfig::curve125();
        let mut s = LeafScratch::new();
        let mut g = tiles_root("28000000000", 120);
        let mut checked = 0usize;
        for _ in 0..25 {
            let champ = g.legal_actions()[0];
            let want = arbitrate_decision(
                &g,
                champ,
                &cfg,
                3,
                4,
                TIEARB_SALT_OF_RECORD,
                0.0,
                13,
                TiearbMode::Argmax,
                TIEARB_MAX_PLIES,
                1,
                &mut s,
            )
            .unwrap();
            let got = arbitrate_decision_legs(
                &g,
                champ,
                &cfg,
                3,
                4,
                TIEARB_SALT_OF_RECORD,
                0.0,
                13,
                TIEARB_MAX_PLIES,
                1,
                &[LegSpec::symmetric("S")],
                &mut s,
            )
            .unwrap();
            assert_eq!(
                want.is_some(),
                got.is_some(),
                "the two decision paths must agree on FIRED"
            );
            if let (Some((wa, wo)), Some((ga, go))) = (want, got) {
                assert_eq!(wa.arms, ga.arms, "arm sets must be identical");
                assert_eq!(
                    go.legs[0]
                        .means
                        .iter()
                        .map(|m| m.to_bits())
                        .collect::<Vec<_>>(),
                    wo.means.iter().map(|m| m.to_bits()).collect::<Vec<_>>(),
                );
                assert_eq!(go.legs[0].argmax_arm, wo.argmax_arm);
                checked += 1;
            }
            let l = g.legal_actions();
            g.advance(l[l.len() / 2]).unwrap();
            while !g.is_terminal() && (g.state.phase != Phase::Tiles || g.legal_actions().len() < 2)
            {
                let l = g.legal_actions();
                g.advance(l[l.len() / 2]).unwrap();
            }
            if g.is_terminal() {
                break;
            }
        }
        assert!(checked > 0, "the trigger never fired — the test is vacuous");
    }

    /// Fail-closed on the two shapes a caller can get wrong.
    #[test]
    fn arbitrate_legs_refuses_an_empty_arm_set_or_no_legs() {
        let g = tiles_root("28000000000", 30);
        let seat = g.state.current_player;
        let arms: Vec<i32> = g.legal_actions().into_iter().take(2).collect();
        let d = g.state_digest();
        assert!(arbitrate_legs(
            &g,
            seat,
            &[],
            2,
            TIEARB_SALT_OF_RECORD,
            &d,
            0,
            TIEARB_MAX_PLIES,
            1,
            &[LegSpec::symmetric("S")]
        )
        .is_err());
        assert!(arbitrate_legs(
            &g,
            seat,
            &arms,
            2,
            TIEARB_SALT_OF_RECORD,
            &d,
            0,
            TIEARB_MAX_PLIES,
            1,
            &[]
        )
        .is_err());
    }
}
