# J-RULES SURFACE B — the anchor's rules as POLICY PRIORS in the champion's PUCT search

> **STATUS AT WRITING: 🔧 BUILT + PROVEN DEFAULT-OFF, NOT CALIBRATED, NOT RUN — 2026-08-14.
> Code on the worktree branch, DEFAULT-OFF everywhere.**
> **0 games · 0 flip rates read · no band claimed · no `results.csv` row · no claim minted ·
> [`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml) untouched ·
> [`governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) untouched.**
> Nothing in this document is a strength statement. The only strength numbers below are the
> static cell's and CL-080's, quoted as evidence about *other* levers.
>
> Remaining sequence (owner/orchestrator): calibration run (instrument BUILT, read-rule
> COMMITTED, run deliberately deferred) → band claim → per-box wheel rebuild → launch.

Parent: [`../jrules_on_search_20260813/`](../jrules_on_search_20260813/DESIGN.md) — surface A
(the static leaf encoding), RAN 2026-08-13, adjudicated **"loss, confounded by budget"**
(margin −2.4912 pts/deck, z −3.8564, elo −33.98 ± 12.34, n=800; `ms_ratio` 1.2116 > the 1.20
N4 trigger; no claim minted, CL-081 left unused). Its prereg **§7 names the policy-prior
surface (B) as untouched by every branch** — this build is that surface.

---

## 1. Why this surface, mechanically

The shared failure mechanism of the two adjudicated leaf-term losses (surface A and CL-080's
open-city term) is the **double-count**: a STATIC leaf term re-prices what the 11,008-sim
search already prices emergently through its own closure schedule, so the backed-up values are
distorted at every node. **A prior does not have that shape.** The house priors are
`P(a) = softmax(Δleaf(a)/tau_p)` over per-child afterstates at every expansion; boosting them
biases WHERE the search spends visits **without moving any value the search backs up**. If the
search's own evaluation disagrees with a J-boosted move, the visits it spends there return the
leaf's verdict and the move still loses the argmax — the prior surface is *advisory* in a way
a leaf term cannot be.

House precedent that the prior surface can carry value the leaf surface can't: **CL-051**
(curve125 read null under random-expansion UCT and a win under PUCT + priors — the identical
information, moved from the value surface to the prior surface, changed the verdict's sign).

**The honest counter-argument, stated up front (it was surface A's §4 reason 2 for declining
this surface):** the measured sims-washout — the same policy change read +82.8 elo (z 3.48) at
sims 200 and +8.0 (z 0.34) at sims 800 — predicts a prior intervention at 11008 sims reads
null. Two things have changed since that argument was written: (i) surface A's own §7 now
lists surface B as an untouched, *named* alternative rather than a rejected one, and (ii) the
washout was measured on ROOT-prior/policy-net gains, whereas this build boosts priors at
**every expansion in the tree** (the same site the house priors themselves act on — CL-051's
win was at this site too). The washout risk is real, is pre-registered here as the honest
failure mode, and is exactly what the calibration's flip-rate instrument measures before any
band is spent: **if the boost cannot change picks at deploy depth, no cell is bought.**

## 2. The functional form

At every node expansion (subject to `scope`, §4), for each legal child `i`:

```
z_i = ( Δleaf_i  +  dose · T(child_i, mover) ) / tau_p        # then the UNCHANGED pipeline:
P   = renormalize( float32( softmax(z) ) )                    # max-shift, exp, f64-sum, f32
```

Equivalently: a **multiplicative boost `exp(dose·T/tau_p)` on child `i`'s prior,
renormalized**. Because softmax is shift-invariant, any component of `T` that is constant
across siblings cancels *exactly* (bit-for-bit) — only what differentiates siblings reaches
the priors. The leaf value backed up (`tanh(leaf_parent/value_norm)`) is computed from the
parent leaf alone and is untouched on every path.

**Dose semantics are the static cell's, deliberately:** `T` is in points (dose 1.0 == the
interview's own magnitudes), `tau_p = 5.0` is the production prior temperature, so
`dose · T` competes with `Δleaf` on the same scale the priors already use. The calibration
ladders of the two surfaces are therefore directly comparable.

## 3. Encoding table — rule → prior form → what is expressible now

The predicates are the bot's (`joshua_bot.py`, `PRESETS["current"]`, the epoch the tournament
selected at z +3.68), evaluated for the **mover only** on the child afterstate. A prior is
neither backed up nor negated, so the leaf's antisymmetry contract (`V(s,p) = −V(s,1−p)`) —
which forced every deviation surface A disclosed — **does not bind**.

| rule | prior form (this build) | newly expressible vs surface A | still NOT expressible |
|---|---|---|---|
| **J1** | the bot's ORIGINAL `j1_majority_steal`: a JOIN into **his** large open city — `cnt[me]≥1 AND cnt[opp]≥1 AND cnt[me]≥cnt[opp]`, tiles ≥5, open ≥2 → `3.0·(1+late)·urg` per city | ⭐ **"he must already be there" RESTORED** (self-cancelling in a signed differential, so surface A had to credit *holding a share* — and thereby collided head-on with `opencity_dose`; the restored form does not credit solo ownership, so that collision is gone) | — |
| **J2c** | ORIGINAL realized steal (`mine≥1 AND his≥1 AND mine≥his AND value≥3` → `steal_w·pot·urg`) + surrender charge | "he must already be there" restored | — |
| **J2a** | ⭐ **THE PLANNING CLAUSE, EXPRESSED**: the bot's APPROACH loop — his valuable fields I'm not on, `reach = 1−(1−per_turn)^h` from `bag_farm_fraction` (the determinized undrawn deck) × entry-cell scan, gated at reach ≥ 0.5 → `0.15·value·reach·urg` | surface A's §3.1 disclosed this as inexpressible (needs bag + board scan outside the leaf contract). An expansion-time prior has the decision node in hand; in a PIMC world the bag is the determinization's | the plan itself — the search remains the planner; reach is a one-scalar proxy |
| **J5+J13** | ⭐ **the bot's ORIGINAL before/after `j5_dump`**: a throwaway placement (naive gain ≤ 1.0) is charged `0.5 · unclaimed-value-fed · urg` (off when he has no meeples) | a potential has no "before"; surface A had to substitute `unclaimed × claim_edge`. The prior form is the bot's actual rule | — |
| **J6** | ORIGINAL anchors + road skepticism + road JOIN with `cnt[opp]≥1` restored | join predicate restored | — |
| **J8** | ORIGINAL `j8_overcommit` with the **margin at the DECISION NODE** (`clock.abs_margin`) and the bot's **still-enterable-farm gate** | surface A read the margin at the leaf (a potential has no root) and substituted a `k≥1` clock gate for enterability | still fires rarely by nature; a bundle null is NOT a J8 null (unchanged) |
| **CLOCK** | ⭐ `k / late_frac / bag_farm_frac / urgency / margin` read **ONCE from the decision node**, reused for every child — `joshua_bot.Clock`'s own fair-information rule | surface A had to read all of these per-leaf | `k0` still frozen at 72 (the leaf-purity constraint carried over: the term must be a pure function of its inputs for the parity gate) |
| J3 | — (already in the champion leaf as curve125) | | |
| J7 | — (tournament-calibrated best weight is 0.0; zero code is the answer) | | |
| J9 | — (tournament no-conviction; off) | | |
| J10f + J3's hard floor | — root FILTERS: still a categorically different, undosable intervention; **not smuggled in** (surface A §3.5's reasoning stands verbatim) | | |

**What the prior surface still cannot express, honestly:** it cannot make the search *prefer
outcomes* the leaf scores badly. It reallocates visits; the leaf then judges the lines those
visits find. If the anchor's strategy is good for reasons the leaf cannot see even after deep
search, surface B will read null — that is the washout failure mode of §1 and it is a
pre-registered reading, not a surprise.

## 4. Knobs

All **SEARCH-config knobs** (`SearchConfig` / `HeuristicPriorConfig`), deliberately NOT
`LeafConfig` fields:

| knob | default | semantics |
|---|---|---|
| `jrules_prior_dose` | **0.0 = OFF** | §2. Dose 0 short-circuits before any prior code runs — the champion, bit-for-bit |
| `jrules_prior_mask` | 31 | per-rule ablation bits, the static bundle's `JR_J1\|J2\|J5\|J6\|J8`; J2a rides inside `JR_J2` as it does in the bot |
| `jrules_prior_scope` | `all` | `all`: every expansion, from that node's mover's POV — the structural analogue of the house priors themselves and of surface A's antisymmetric form (both in-tree players "play the strategy"). `own`: only nodes where the ROOT player moves — the internal opponent model stays the unmodified champion (the prior-surface analogue of surface A §12 Q1's own-side-only option; **a different hypothesis**, named and buildable without a rebuild, but never a rung of the primary ladder) |

⚠️ **BECAUSE THESE ARE NOT LEAF FIELDS, NO LEAF HASH MOVES.** The candidate's `cand_leaf_hash`
EQUALS the champion's `a36d2e15a3b3d71d` on a live-term cell. **Every hash-moved wiring gate
from the A/opencity/denial campaigns is inert here** — the gate that proves the term live is
(1) the RESOLVED `cand_jrules_prior.dose` in the manifest, and (2) the dose-0 positive-control
pair (below). This inversion is stamped in the code, the manifest, the instrument and the
prereg draft, because it is the one place a reader carrying surface-A habits would be wrong.

## 5. What was built

| surface | change |
|---|---|
| `carc-core/src/leaf/jrules_prior.rs` | `JrPriorClock` + `jr_prior_clock` + `jrules_prior_term` + the frozen `JP_*` constants (approach/planning + J5-dump params, pinned against `joshua_bot`); shares the `Decomp` and the `jr_*` helpers with surface A |
| `carc-core/src/leaf/mod.rs` | `LeafScratch::leaf_float_and_base` — one decomposition serves the leaf AND the prior term per child |
| `carc-core/src/search/mod.rs` | `SearchConfig.jrules_prior_{dose,mask,scope}` + `JrPriorScope`; `Searcher::evaluate` adds `dose·T` to each child's Δleaf before the softmax, behind `dose != 0.0` (the OFF path is the pre-change code verbatim); `root_player` latched per `search()` for scope=own |
| `carc-py/src/lib.rs` | `SearchConfigRs` trailing kwargs (validated even at dose 0) + resolved-knobs getter + `MirrorState.jrules_prior_probe` (the parity surface; bit patterns) + repr suffix only when live |
| `heuristic_prior_mcts.py` | `HeuristicPriorConfig` fields + validation + `as_manifest` stamp; `make_heuristic_prior_evaluator` **fail-louds** on a set dose (surface B is rust-only) |
| `rust_agent.search_config_rs` | conditional kwargs — forwarded ONLY when the dose is nonzero, so a stale `carc_rs` serves every champion config and raises `TypeError` on a set dose (fail-closed loud; **verified live against the installed pre-B wheel**) |
| `jrules_priors.py` | the python REFERENCE MIRROR (parity target; never a production path) |
| `eval_fair_puct.py` | `--cand-jrules-prior-{dose,mask,scope}` (candidate side ONLY), launch-time stale-wheel probe, `[smoke]` liveness banner, manifest key `cand_jrules_prior` (the RESOLVED dict) |
| `jrules_priors_e4_replay.py` | the calibration instrument — sibling of surface A's (same statistic), arm tuple `name:dose[:mask[:scope]]`, **inverted hash guard** (leaf hash must EQUAL the champion's) + **positive-control search** at construction (a pinned root where dose 1.0 provably moves priors — the only liveness proof available when no hash can move) |
| tests | `tests/test_jrules_priors.py` (22) + `tests/test_jrules_priors_e4_replay.py` (15) |

## 6. Proofs (this tree's wheel, pinned toolchain 1.96.0)

| proof | status |
|---|---|
| **BIT-IDENTITY, F-c style** — the F-c golden gate re-run on this wheel: **208 real production searches** (2 rules geometries × 4 decks × 26 plies at 400 sims; chosen action, every root child's (action, N, W-bits), deduped + pooled stats, root priors, node + leaf-eval counts) hash to the **RECORDED pre-F-c digest** `6cd80a92ad2dd7b55d9fd0a2c77252b654f3c5de3492d59131973ba1a73f3d89` over 736,607 leaf evals / 75,886 nodes | ✅ (`tests/test_window_truncation_failloud.py` blocks A, both tests pass — this chains the proof back through F-c to the recorded baseline, stronger than a fresh two-wheel bake) |
| champion leaf fingerprints `a36d2e15a3b3d71d` / `158f17ff76adaa02` / `6dfffd57051690f2` | ✅ recompute unchanged (python + rust panels agreeing) |
| dose-0 with a MOVED mask **and** scope, wide 22-legal root, byte-identical search | ✅ rust unit gate + the pyo3-level twin |
| dose 1.0 moves PRIORS but NOT the backed-up root leaf value; priors stay renormalized | ✅ rust unit gate + pyo3 twin |
| scope=own boosts the root identically to scope=all (root is own) | ✅ rust unit gate |
| **rust ↔ python term parity, BIT-FOR-BIT** on replayed games — clock fields + every per-child term, 2 seeds × 3 masks (31/1/27), ≥40 values per cell | ✅ `test_rust_python_term_parity_on_replayed_games` |
| stale wheel: default-off configs served; nonzero dose → `TypeError` at `search_config_rs`; harness probes at LAUNCH | ✅ verified live against the installed pre-B wheel |
| stale wheel: test suite **SKIPS LOUDLY** (9 skips naming the per-box rebuild) instead of passing vacuously | ✅ 13 passed / 9 skipped observed |
| neighbours undisturbed | ✅ `test_jrules_term` 39p/1s · `rustport/test_p3_search` 20p · `rustport/test_p4_fair` 55p · carc-core `cargo test` 110p · `reconcile_leaf --configs jrules --corpus golden` **83,824 values, 0 mismatches** on this wheel |
| end-to-end: `eval_fair_puct --smoke` with `--cand-jrules-prior-dose 0.25 --backend rust` plays clean; instrument `--limit-games 1` grades a real archive | ✅ |

(The known pre-existing cross-suite interference — running `rustport/test_p4_fair.py` before
`test_jrules_term.py` in ONE pytest process makes `test_every_rule_fires_somewhere_on_the_corpus`
fail on J8 — reproduces identically on the untouched main tree with the installed wheel; it is
an env-latch ordering artifact, not this build's.)

## 7. Cost — MEASURED (shared-tenancy caveat)

Search-level A/B (`carc-core/examples/jp_bench.rs`): 16 midgame positions (4 seeds × plies
30–90, ≥6 legal), sims 1376, interleaved legs, **min-of-6 reps per leg** (min is the
contention-robust estimator; the box was carrying a live 6-worker replay at measure time —
disclosed, and the reason the prereg's N4 must still read the real `ms_ratio` off
`menu_block_summary`):

| config | aggregate on/off | median |
|---|---|---|
| dose 0.25, mask 31, **scope all** | **1.154×** | 1.176× |
| dose 0.25, mask 31, **scope own** | **1.069×** | 1.111× |

Dose-independence expected (the term computes whatever the dose). The cost sits at the
expansion site: per legal child, one `jr_counts` pass + the rule loops (J2a/J8's entry-cell
scans are memoized per term call and gated behind the cheap predicates) + one extra parent
decomposition per expansion for the clock (~1/(n_legal+1) of leaf traffic).

⚠️ **N4 risk, stated before any cell:** surface A predicted 1.12–1.14 from a leaf bench and
measured **1.2116** at the cell — past the 1.20 trigger — and that confound is what voided its
N1. Surface B's ~1.15 (scope all) is in the same danger band. Three pre-registered mitigations,
none of which may be chosen after seeing a strength number: (i) the prereg carries the same N4
branch with the same 1.20 trigger — read off the FIRST block, and if the realized ratio is
already >1.20 the owner can abort before the band is spent; (ii) `scope own` at ~1.07× is the
named cost fallback **but is a different hypothesis** (opponent model stays champion) — it
would need its own prereg, never a silent swap; (iii) AMENDMENT_1's equal-sims argument (both
arms run identical 11008 sims, so wall-clock is not a strength variable) was recorded on
surface A **as dissent, not adopted** — the owner's "default" ruling stands, and this design
does not relitigate it.

## 8. Calibration — instrument BUILT, read-rule COMMITTED, run DEFERRED

* **Instrument:** [`jrules_priors_e4_replay.py`](../../scripts/classical_search/jrules_priors_e4_replay.py)
  — the same statistic as surface A's / CL-080's (champion-ply search pick-flip on the banked
  E4 archives under CRN, budget from each archive's own stamp, profile resolved per archive,
  per-ply resumable, one subprocess per archive). Wiring-smoked on one real archive
  (`--limit-games 1 --limit-plies 12`: graded 6 plies, stamped `partial`, refused to be read
  as a calibration — as designed).
* **Read-rule:** [`CALIB_READ_RULE.md`](CALIB_READ_RULE.md) — **committed in this same
  worktree branch, before any arm's flip rate has been read by anyone** (the instrument has
  produced no flip rate beyond the 6-ply wiring smoke, whose `partial` stamp voids it as a
  calibration by the rule's own §3.0). Ladder `{0.5, 1.0, 2.0}` + the pre-committed 0.25
  `FINER-RUNG` (trigger `f(1.0) > 0.20`), funding branch **FUND-SMALLEST** at the 10%
  point-estimate bar, `NO-EXPRESSION` stop branch — cloned from surface A's rule, with the
  surface-B changes (scope axis excluded from the ladder; the VOID gate checks the INVERTED
  hash condition + the positive control).
* **Running it is the orchestrator's** (~26 archives × ~60 champion plies × 4 arms at 11008
  sims ≈ 6,200 searches ≈ several pool-hours — deliberately not spent by this build session,
  and the box currently carries a live run).

## 9. Deploy cell — DRAFT prereg

[`DEPLOY_PREREG_DRAFT.md`](DEPLOY_PREREG_DRAFT.md) — cloned from surface A's adjudicated
prereg: n=800 deck-paired (400 decks × 2 seats), fair PIMC k8×1376 = 11008 BOTH arms, rust
both sides, `fixed_v1` + R9, exact-K 2 shared, margin z primary, N0–N5 branch map with the
`ms_ratio` 1.20 N4 trigger, **band = `CLAIMED-BY-ORCHESTRATOR` placeholder**, and the
**13 wiring gates** — including the surface-B-specific ones: resolved
`cand_jrules_prior.dose` in the manifest (the hash gates CANNOT prove liveness here),
`cand_leaf_hash` EQUAL to the champion's (inverted!), and no `jrules_*`/`jrules_prior_*` key
on the opponent side. It is a DRAFT until the calibration names a dose and the owner claims a
band; the launching session fills exactly those two fields and commits it as the prereg of
record before game 1.

## 10. Expectation management

The pre-stated prior is a LOSS OR NULL, and the null is the *specific* risk here (§1's
washout). Every hand-crafted term in the program's record has come back null or harmful
(CL-055/063/074/078/079/080, surface A). What is genuinely different this time: (i) the
double-count mechanism named by CL-080 and surface A **does not apply to a prior** — nothing
is double-priced in the value pathway; (ii) CL-051 is a real precedent of this exact surface
carrying value; (iii) the encoding is strictly MORE faithful than surface A's (restored
predicates, the planning clause, the bot's own J5 and clock semantics). The value of the cell
is that it prices the anchor's strategy at the champion's depth **with the encoding
disclaimers removed** — a powered negative would bound the strategy itself far more tightly
than surface A's confounded loss could.

## 11. Launch-blocking gates (surface-B analogue of A's §11)

| # | gate | state |
|---|---|---|
| **B-G1** | worktree merged to the main tree at a quiet window | ⛔ pending (a live run holds the tree) |
| **B-G2** | `pytest tests/test_jrules_priors.py` green on the run box with its wheel (22 pass, 0 of the 9 rust-gated skips firing) | ✅ on this worktree's wheel; **per-box** |
| **B-G3** | `carc_rs` wheel rebuilt on EVERY box that runs anything (`maturin build --release` + reinstall) — the F-c golden digest + `reconcile_leaf --configs jrules` + the 22 tests re-run there | ✅ local worktree wheel; ⛔ main venv + laptop |
| **B-G4** | the instrument's positive control passes on the run box (`_assert_surface_b_live` — it runs automatically at every grading) | ✅ this wheel |
| **B-G5** | calibration ladder run + `CALIB_READ_RULE.md` applied mechanically | ⛔ deferred to orchestrator |
| **B-G6** | fresh band claimed in `governance/BAND_REGISTRY.csv` | ⛔ owner's call |
| **B-G7** | first-block `ms_ratio` read from `menu_block_summary` against the §7 prediction (~1.15 scope-all) | ⛔ at launch |
