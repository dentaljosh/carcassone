# INVASION-RISK TERM FAMILY — ROUND-1 SCREEN AT 2752 — DESIGN

**STATUS: FROZEN, NOT AUTHORIZED TO LAUNCH (2026-08-26).** No cell has run. No band sentinel
exists. Nothing in this directory has spent a game.

Run id `invasion_screen_prep`. Pair: this file + [`READ_RULE.md`](READ_RULE.md). Launcher:
[`run_cells.sh`](run_cells.sh). Adjudicator: [`analyze_screen.py`](analyze_screen.py). Shared
primitives (the ONE implementation of every bar and every cost figure):
[`screen_lib.py`](screen_lib.py). Band claim: [`BAND_CLAIM.json`](BAND_CLAIM.json).

Spec of record for the thing being screened: [`../invasion_term_build/SHAPES.md`](../invasion_term_build/SHAPES.md)
(**BUILT, NOT SCREENED**). Implementation: `rust/carc/carc-core/src/leaf/invasion.rs`.
Mechanism evidence: [`../e4_exploit_grading_20260825/`](../e4_exploit_grading_20260825/STAGE_B_VERDICT.md)
(Stage A/B census). Lever row: [`../../docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md),
"contested-feature / invasion-risk term".

---

## 0. AUTHORIZATION BLOCK — the sign-off table

**NOT AUTHORIZED TO LAUNCH.** The owner funded the **build-first screening plan**; the LAUNCH
sign-off is a separate act that has not happened. Nothing below claims otherwise.

| # | sign-off | state | why |
|---|---|---|---|
| (a) | **funding ≈54–62 core-h / ≈2.9–3.3 h wall at W=22** (§6) | ⛔ **NOT GIVEN — OWNER** | This is the largest single number in the pair and the standing cost-discipline rule requires a one-sentence confirm before it is spent. The build-first bargain funded the *build*; it did not pre-authorize the screen's compute. The band is the honest range, not a point estimate — see §6's named uncertainty (the candidate-side invasion arithmetic is UNMEASURED) |
| (b) | **the band claim** — `151000000000` (§5) | ⚙️ **ORCHESTRATOR-PROCEDURAL — DONE at freeze** | All-branches sweep re-run 2026-08-26 (139 refs / 641 registry-and-claim files); `151000000000` free everywhere. The row is in [`BAND_CLAIM.json`](BAND_CLAIM.json) and is appended to [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) in the stamping commit. ⛔ **The row does NOT arm the launcher** — see the interlock below |
| (c) | **the frozen MID weights** — `beta 0.12` / `alpha 0.09 @ cap 11.0` / `delta_farm 0.12` (§3.2) | ⚙️ **ORCHESTRATOR-PROCEDURAL — DONE at freeze** | Derived, not chosen: each is `0.40 × G / M_shape` where `G` = the champion leaf's own sibling-move value gap and `M_shape` = the shape's own firing magnitude, both measured on the 93 Stage-A census positions with the rust bindings. Full arithmetic in §3.2; it is reproducible from [`../invasion_term_build/e4_positions.py`](../invasion_term_build/e4_positions.py) |
| (d) | **tie-arbiter OFF on both sides** | ⚙️ **ORCHESTRATOR-PROCEDURAL — DONE at freeze** | The arbiter is a separate, separately-adjudicated lever. Arming it would confound the invasion axis with the arbiter's own tied-ply behaviour. The launcher emits **no** `--cand-tiearb-*` flag of any spelling, and the opponent side is **structurally** disarmed (`eval_fair_puct.py` has no `--opp-tiearb-*` flag; verified in source). `G-TIEARB` records the absence as *verified*, not merely believed |
| (e) | ⭐ **TENANCY CLASS: NON-EXCLUSIVE, RESULT-SAFE** (§6.2) | ⚙️ **ORCHESTRATOR-PROCEDURAL — DECLARED at freeze** | **This pair is SIMS-denominated. It is NOT an exclusive tenant and does NOT require a quiet window** — it may run beside the 1-core `reconcile_exact_solver.py` suite. The full sensitivity-class argument is §6.2; the census in the launcher is **ADVISORY** (throughput and RAM), never a precondition. ⚠️ This is a *deliberate divergence* from `track_d2r4_prep` §0(e), whose gates were timing gates. Ours are not |

⛔ **THE INTERLOCK, UNCHANGED FROM THE HOUSE PATTERN AND NOT A FORMALITY.** `BAND_CLAIMED` is
**deliberately NOT created at freeze**, and [`run_cells.sh`](run_cells.sh) refuses every real cell
without it. Claiming the registry row protects against a concurrent-session band race; it does
**not** arm the launcher.

**Pre-launch checklist** (all must be true before any real cell fires):

- [ ] **(a) funding signed off by the owner** — the one line this build cannot supply
- [x] band claimed in [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) (`151000000000`, §5), after re-running the all-branches sweep
- [x] this pair (`DESIGN.md` + `READ_RULE.md` + launcher + adjudicator + `screen_lib.py`) frozen and committed
- [ ] `BLIND_COMMIT` stamped with the freeze commit's own sha (the launcher refuses a real cell on the `PENDING` placeholder)
- [ ] **the `carc_rs` wheel REBUILT into the shared venv** from the merged tree — §7. ⛔ **The venv wheel is STALE as of this freeze** (measured: `LeafConfigRs.__new__() got an unexpected keyword argument 'invasion_beta'`). The launcher makes this a FATAL precondition; the orchestrator does the rebuild, this build deliberately did not touch the shared venv
- [ ] `analyze_screen.py --selftest` GREEN, **seeded from a real manifest** (§9)
- [ ] the §9 **smoke** leg has run, `n_failed == 0`, **and the adjudicator has been run against the smoke archive and failed only on the pinned allowed set** (§9 — the launcher enforces this)
- [ ] `PINNED_SRC_REV` written from `git rev-parse HEAD` on the launch box, `chmod +x run_cells.sh`
- [ ] `RUN_LIVE.json` sentinel dropped for the duration (freeze-latch discipline — the launcher does this itself)

---

## 1. THE QUESTION

The Stage A/B census ([`../e4_exploit_grading_20260825/STAGE_B_VERDICT.md`](../e4_exploit_grading_20260825/STAGE_B_VERDICT.md))
measured a mechanism the champion does not price: **deliberate invasion**. An invasion's first
move — a 2-tile stub claimed beside an opponent feature — is *demoted* by the champion leaf,
because the merge payoff is several plies out and the vendored full-points-on-tie rule hides the
victim's loss. Measured: deliberate invasions by merge 90 vs 7; late decisive farm captures;
the champion farm-zeroed in 9 of 50 games.

[`../invasion_term_build/SHAPES.md`](../invasion_term_build/SHAPES.md) built four candidate leaf
terms that encode it. **This pair asks exactly one question, at the cheapest budget that can
answer it:**

> At the 2752 screening budget, does adding any single invasion term at a scale-matched mid
> weight move the deck-paired margin against the otherwise-identical champion leaf?

**It is a SCREEN, not a verdict.** A shape that fires here earns **one** production-budget H2H —
a separate pair, a separate band, a separate funding decision. A shape that reads null here is
parked, and the family's kill rule hands the ceiling question to the solver-pricing instrument
(§8, and the skeleton's "build-first bargain").

### 1.1 ⭐ THE E4 INPUTS ARE DISCOVERY AND SIGN-FIXTURES ONLY — the overfitting objection, answered

The obvious objection to this whole family: **its evidence comes from the owner's own games, so is
it fitted to one human opponent?** The answer, recorded before any number so the record carries it:

**No weight is fit to the owner's games.** The E4 / Stage-A census plays exactly two roles, both
upstream of any measurement:

1. **DISCOVERY** — it is where the *mechanism* was found (deliberate invasion by merge, 90 vs 7;
   the champion farm-zeroed in 9 of 50 games). Noticing a phenomenon in one opponent's play is a
   hypothesis-generating act, and hypotheses do not need to be unbiased.
2. **SIGN-FIXTURES and SCALE** — the 93 census positions are where each shape's *direction* was
   unit-tested ([`../invasion_term_build/test_invasion_shapes.py`](../invasion_term_build/test_invasion_shapes.py)
   gate 2) and where §3.2's `G` and `M_shape` were measured. That is a **units** calculation — it
   answers "what magnitude is this term, in leaf points?" — not a fit. **No objective function was
   optimized on E4 data, no weight was tuned to win an E4 game, and no E4 outcome enters any bar.**

**Everything that decides anything is fresh-deck play against the champion**, on a band no E4 game
ever touched. If a weight derived from that corpus is wrong for general play, this screen's own
cells say so: an over- or under-scaled term reads null or `REVERSED` on 400 fresh decks, and no
appeal to the census can rescue it.

**And the residual risk is handled downstream, not waved away.** A term derived from *one*
opponent's exploits could still be an artifact — which is exactly why `READ_RULE.md` §4's
`PROMOTE-<shape>` chain requires an **external-validation cell against Carcasum** before any
champion-of-record discussion, and treats the ongoing E4 stream (a human who **adapts**) as the
final holdout. Self-play evidence alone never adopts a term in this program.

---

## 2. THE INSTRUMENT — production leaf, screening budget, both sides rust

`scripts/classical_search/eval_fair_puct.py`, `--opponent fair-champion` (a `_HEAD_TO_HEAD` mode),
`--backend rust` on **both** sides, deck-paired.

| knob | value | source |
|---|---|---|
| `--info` | `fair` | fair PIMC, not clairvoyant |
| `--opponent` | `fair-champion` | head-to-head mode ⇒ `converted_sides == ["candidate","opponent"]` |
| `--backend` | `rust` | ⛔ **not a speed preference.** The invasion family exists ONLY in rust; both python leaves `raise NotImplementedError` on a nonzero weight ([`SHAPES.md`](../invasion_term_build/SHAPES.md) §"RUST PATH ONLY"). A `--backend python` leg fails loudly rather than producing a beautiful, meaningless null |
| `--k-dets` / `--sims` | `4` / `688` (= **2752** total) | the screening budget; `--opp-k-dets`/`--opp-sims` identical |
| `--exact-k` | `2`, marginalized | the fair deployable handoff; K=3/4 are clairvoyant-only and a fair cell cannot run them |
| `--c-puct` / `--tau-p` | `1.5` / `5` | `governance/PRODUCTION.yaml` champion.search |
| `--leaf-quantize` / `--final-select` | `float` / `visits` | as production |
| `--rules-profile` | `fixed_v1`, with `CARCASSONNE_FIX_R9=1` **exported before the process starts** | the profile of record. R9 is import-latched (a rust `OnceLock`); a parent-only check proves nothing about children, so the preflight runs in a CHILD |
| tie-arbiter | **OFF both sides** | §0(d) |
| leaf | curve125 champion, `a36d2e15a3b3d71d`, **plus the cell's one invasion knob on the candidate side only** | §2.1 |

### 2.1 — the single variable, and how the harness enforces it

`--cand-leaf-json` is a **candidate-side-only** knob. Verified in source
(`eval_fair_puct.py:3769-3778`), quoted because the whole design rests on it:

```python
        if _h2h:
            # The OPPONENT is the production champion (or a second production-config
            # net): ALWAYS curve125, never the user's --cand-leaf-json (which is a
            # CANDIDATE-side knob — the reference side must not move with it, exactly
            # as the h800 rung never takes it).
            opp_leaf_cfg = _curve125_leaf_cfg()
```

So the opponent gets `_curve125_leaf_cfg()` — the plain champion leaf with **all six invasion
fields at their defaults** — regardless of what the candidate JSON says. `G-SINGLEVAR` and
`G-INVASION` (`READ_RULE.md` §3) verify this against the emitted manifest rather than trusting it.

⚠️ **Every cell's `--cand-leaf-json` MUST carry `v29_meeple_curve` explicitly.** `_load_cand_leaf_cfg`
replaces named fields on the **env** `DEFAULT_CONFIG`, which is **curve100**, and
`_assert_netprior_leaf` hard-fails on a candidate whose curve is not CURVE125 — *even with*
`--allow-leaf-hash-drift`. A JSON carrying only the invasion knob would be a curve100 candidate
and would abort. The four JSON files in this directory each carry curve125 + the knob, and the
launcher's preflight asserts the resolved curve before game 1.

### 2.2 — ⚠️ `--allow-leaf-hash-drift` IS REQUIRED on A/B/D, AND MUST NOT BE PASSED ON IDENT

`_assert_netprior_leaf` (`eval_fair_puct.py:493-536`) checks the candidate's `_leaf_hash` against
the pinned `a36d2e15a3b3d71d` and `SystemExit`s on a mismatch. A **nonzero invasion weight moves
that hash by design** ([`SHAPES.md`](../invasion_term_build/SHAPES.md) §6), so cells A/B/D would
abort at launch without `--allow-leaf-hash-drift`.

**The IDENT cell is the opposite, and this is load-bearing:** an *explicit-zero* invasion config
hashes **AS the champion** ([`SHAPES.md`](../invasion_term_build/SHAPES.md) §6 — the hash names
the leaf FUNCTION, and a zero-weight config IS the champion leaf bit-for-bit, gate 1). So IDENT
runs under the **strict, un-relaxed** hash assertion and passes it. The launcher therefore emits
`--allow-leaf-hash-drift` on A/B/D and **deliberately withholds it on IDENT**, and `READ_RULE.md`
§3 `G-LEAF` gates the asymmetry in both directions: a drift-flag on IDENT, or its absence on
A/B/D, is a launcher defect the adjudicator can see in the manifest.

⛔ **AND THE FLAG IS BLUNTER THAN IT LOOKS — which is why `G-LEAF(a)` exists as its own conjunct.**
`--allow-leaf-hash-drift` is a **single** switch that relaxes `_assert_netprior_leaf` on **both**
sides: `eval_fair_puct.py:3763` (candidate) and **`:3777` (opponent)**. So on the three cells that
must pass it, the harness's *opponent*-side hash assertion is no longer enforcing anything, and a
drifted opponent leaf would sail through. `G-LEAF(a)` — `config.opp_leaf_hash ==
a36d2e15a3b3d71d` on **every** cell, read off the emitted manifest — is what puts that check back,
after the fact and outside the harness. Without it the A/B/D cells would not be verifiably
single-variable at all.

### 2.3 — ⚠️ the silent-cap-drop trap, and the gate that catches it

`rust_agent.leaf_config_rs` (`src/carcassonne_ai/rust_agent.py:181-185`) forwards
`invasion_alpha_cap` and `invasion_stub_max_tiles` **only when `invasion_alpha != 0.0`**:

```python
        if float(getattr(leaf_cfg, "invasion_alpha", 0.0)) != 0.0:
            if float(getattr(leaf_cfg, "invasion_alpha_cap", 0.0)) != 0.0:
                invasion["invasion_alpha_cap"] = float(leaf_cfg.invasion_alpha_cap)
```

A cell that set `invasion_beta` **and** a cap would have the cap silently dropped by the rust
config while the manifest's `cand_leaf_cfg` still showed it — a manifest that lies about the
running leaf. This design sets a cap on **cell B only** (where `invasion_alpha != 0.0`, so it is
forwarded), and `G-CAPFWD` asserts the biconditional on every cell: a nonzero `invasion_alpha_cap`
appears in `cand_leaf_cfg` **iff** `invasion_alpha` is nonzero. Found during this build; recorded
here because it is exactly the class of defect a screen cannot detect from its own numbers.

### 2.4 — this is NOT a production H2H, and the harness says so out loud

`k4×688 = 2752` is the **screening** budget. `governance/PRODUCTION.yaml`'s champion is
`k8×1376 = 11008`, and the harness prints a non-fatal warning on every cell:

> `[warn] --opponent fair-champion: the search config deviates from governance/PRODUCTION.yaml
> (k_dets=4 (production 8); sims=688 (production 1376)). BOTH sides use these values, so the swap
> stays single-variable, but the opponent is NOT the shipped production champion — do not report
> this cell as 'vs production'.`

**Expected. Do not suppress it.** `READ_RULE.md` §5 forbids any branch from narrating a cell as a
production result, and §4's `PROMOTE-<shape>` branch buys exactly one thing: the right to *ask*
for a production-budget H2H.

---

## 3. THE CELLS

**Round 1 is FOUR cells, cheapest-informative-first.** The prereg skeleton wrote "5 cells"
(identity + one mid per shape × 4 shapes); **shape C is deferred entirely to round 2** on the
skeleton's own §3 read rule, so round 1 is identity + A + B + D. See §3.3.

| cell | candidate leaf (curve125 +) | opponent | decks | games | drift flag |
|---|---|---|---|---|---|
| `IDENT` | `{beta:0, alpha:0, gamma:0, delta_farm:0}` — explicit zeros, inert knobs at defaults | plain curve125 champion | **200** | 400 | ⛔ NO |
| `A_MID` | `{invasion_beta: 0.12}` | plain curve125 champion | **400** | 800 | ✅ yes |
| `B_MID` | `{invasion_alpha: 0.09, invasion_alpha_cap: 11.0}` (`stub_max_tiles` stays default 2) | plain curve125 champion | **400** | 800 | ✅ yes |
| `D_MID` | `{invasion_delta_farm: 0.12}` | plain curve125 champion | **400** | 800 | ✅ yes |

Every cell: `k4×688 = 2752` on **both** sides, rust both sides, arbiter OFF both sides,
`fixed_v1`+R9, `exact-k 2` marginalized, deck-paired, on band `151000000000`, **its own disjoint
deck range** (§5).

### 3.1 — the IDENT cell is a PRECONDITION on the whole round, not a fifth result

`IDENT` is the **game-level weight-0 identity gate**. [`SHAPES.md`](../invasion_term_build/SHAPES.md)
gate 1 already proves an explicit-zero config is bit-identical to the champion **at the leaf**, on
a random corpus and on 186 real E4 positions. `IDENT` asks the next question up: does that identity
survive the whole pipeline — CLI parse → `_load_cand_leaf_cfg` → `leaf_config_rs` conditional
kwargs → the rust search → 400 games of scoring?

**A failed `IDENT` voids the entire round** (`READ_RULE.md` §3 `G-IDENT` → `U-UNREADABLE` on all
four cells), because a wiring defect that moves a zero-weight leaf moves every nonzero one too,
and no A/B/D reading could be attributed to the term rather than to the plumbing.

### 3.1a — ⛔ THE IDENT BAR IS STATISTICAL, NOT BIT-IDENTITY. HERE IS WHY.

The pair was required to investigate whether the harness's CRN makes a **bit-identical** bar
observable — i.e. whether identically-configured sides at the same deck seeds produce mirrored
games and therefore a per-deck margin of **exactly 0.0**. **They do not, and the reason is
structural, not incidental.**

The harness is fully deterministic given `(deck seed, seat, config)` — `random.seed(seed)` at
`eval_fair_puct.py:2200` is the only entropy source in the file, and PIMC determinizations derive
from it (`fair_agent.py:947-951`):

```python
    def det_seed_base(self, move_idx: int) -> int:
        return (self._seed * 1_000_003 + move_idx * 8191) & 0x7FFFFFFF
```

with the rust port bit-identical at any thread count (`rust/carc/carc-core/src/fair/mod.rs:22-32`).
So a re-run reproduces byte-identical records. **But the two sides are deliberately decoupled:**
`_make_opponent` (`eval_fair_puct.py:1470-1474`) constructs the opponent on `seed + 1` —

```python
    return _make_champion(info, opp_cfg, _opp_sims, _opp_k_dets, K, seed + 1, ...)
```

documented at `1421-1422` as *"`seed+1` mirrors the rung's historical seed offset, so the two
sides never share a determinization stream."*

Consequence, stated as arithmetic:

```
candidate always draws stream A = seed        (both seatings)
opponent  always draws stream B = seed + 1    (both seatings)

seating a=0:  A at seat 0, B at seat 1  =>  diff_0 = s0 - s1
seating a=1:  B at seat 0, A at seat 1  =>  diff_1 = s1 - s0
```

These are **two different games**, not a game and its mirror: `det_seed_base` differs by
`1_000_003 (mod 2^31)` between the sides, so every determinization's deck reshuffle differs. If
both sides shared one seed the two seatings would replay the *same* game, `diff_1 = -diff_0`
exactly, and `D(d) = 0` identically — the `+1` offset is precisely what converts that degenerate
mirror into a real random variable.

**So: `IDENT` carries the FULL per-deck margin variance and its bar is a two-sided ±2σ null at
the cell's own realized SE** (`READ_RULE.md` §3 `G-IDENT`). It is a *statistical* wiring proof,
and it is worth its 8 core-h precisely because it is the only proof available at the game level.

⚠️ **Do NOT "fix" this by patching the offset.** Removing the `+1` would collapse the two seatings
into one game and destroy the deck-paired estimator every cell in this pair depends on. The
degenerate-zero bar is unavailable *by construction of the instrument*, not by oversight.

**⭐ AND IT WAS CONFIRMED EMPIRICALLY, NOT ONLY FROM SOURCE.** An off-band 2-deck
champion-vs-champion probe at the cells' exact knobs, run **twice**, on throwaway dev seeds
`990000000100..` (§9.1 — spends no band, adjudicates nothing):

```
run-to-run: all 4 records byte-stable across two identical invocations  => DETERMINISM CONFIRMED

seed 990000000100  (same deck_hash b10243946d44656c in both seatings -- deck CRN is correct)
    a_seat=0: scores (86,91)   diff  -5.0     a_seat=1: scores (121,103)  diff -18.0
    => D(d) = -11.5000     NOT 0
seed 990000000101  (same deck_hash 54ca57ad35051145)
    a_seat=0: scores (91,98)   diff  -7.0     a_seat=1: scores (77,89)    diff +12.0
    => D(d) =  +2.5000     NOT 0
```

The two seatings are **different games with different final scores** — exactly what the `seed + 1`
offset predicts. `|D(d)|` of 11.5 and 2.5 on two decks is ordinary per-deck dispersion for this
instrument (σ_D ≈ 13–15, §4.1), not a defect. **A bit-identity bar is unavailable. The bar is
statistical.**

### 3.2 ⭐ THE FROZEN MID WEIGHTS — the derivation, and the numbers

**The principle:** a screening weight should make the term's typical firing magnitude a
**meaningful but not dominant fraction of the champion leaf's own move-discrimination scale** —
big enough to reorder siblings, small enough not to replace the leaf. The skeleton's band is
**30–50%**; this pair takes the **midpoint, 40%**, and freezes it.

Both inputs are **measured on the 93 Stage-A census invasion positions**, through the rust
bindings, with the champion leaf — not modelled, not borrowed. Corpus: the 51
`notes.mech == "merge"` rows of
[`../e4_exploit_grading_20260825/stage_b_plies.jsonl`](../e4_exploit_grading_20260825/stage_b_plies.jsonl),
expanded to each row's graded ply **and** its recorded `contest_onset_ply`, replayed with
[`../invasion_term_build/e4_positions.py`](../invasion_term_build/e4_positions.py) →
**93 replayable non-terminal positions across 34 games** (the same corpus
[`../invasion_term_build/test_invasion_shapes.py`](../invasion_term_build/test_invasion_shapes.py)
gate 2 asserts direction on).

#### (i) `G` — the champion leaf's typical sibling-move value gap

At each of the 93 positions, for the mover, every legal action was applied to a fresh replay and
the resulting afterstate scored with `MirrorState.leaf_value_float(mover, champion_cfg)`
(median 10 legal moves per position, mean 16.1, max 50). Three readings of "the gap":

| statistic (median over the 93 positions) | value | nonzero at |
|---|---|---|
| sibling **p90 − p10** of the champion leaf value | **1.76** | 88.2% |
| sibling **IQR** (p75 − p25) | 0.81 | 68.8% |
| **top1 − top2** gap | 0.20 (median) · **1.72 (mean)** | 50.5% |

```
G := 1.76 leaf points        (median sibling p90-p10)
```

Chosen because it is the only one of the three that is nonzero at almost every position (the
top-2 gap has a median of 0.20 purely because half these positions have *ties at the top*, which
is a fact about the census, not about the leaf's scale). It is **independently corroborated**: the
mean top1−top2 gap is **1.72**, within 3% of it, from a completely different definition.

#### (ii) `M_shape` — each shape's own firing magnitude

`|T_shape|` at the same 93 positions, mover POV, champion config; the median **conditional on the
term firing** (a term that is silent contributes nothing to move ordering and must not dilute the
scale):

| shape | fires at | median `|T|` (all 93) | **`M` = median `|T|` when fired** | mean when fired |
|---|---|---|---|---|
| A (`T_A`) | 79.6% (74/93) | 3.0 | **6.0** | 10.64 |
| B (`T_B`, at cap 11.0) | 44.1% (41/93) | 0.0 | **8.0** | 9.59 |
| C (`T_C`) | 63.4% (59/93) | 1.27 | **3.03** | 2.91 |
| D (`T_D`) | 54.8% (51/93) | 3.0 | **6.0** | 9.12 |

`M_A == M_D == 6.0` is not a coincidence and is not an error: `T_A ≡ (cities+roads part) + T_D`
exactly ([`SHAPES.md`](../invasion_term_build/SHAPES.md) §4), and on this corpus the farm part
carries the median.

#### (iii) the arithmetic, and the frozen numbers

```
target contribution  =  0.40 x G  =  0.40 x 1.76  =  0.704 leaf points
                         (the skeleton's 30-50% band = 0.528 .. 0.880)

mid_shape  =  0.704 / M_shape

    A:  0.704 / 6.00  = 0.11733  ->  frozen  beta        = 0.12   (0.12 x 6.00 = 0.72 = 40.9% of G)
    B:  0.704 / 8.00  = 0.08800  ->  frozen  alpha       = 0.09   (0.09 x 8.00 = 0.72 = 40.9% of G)
    D:  0.704 / 6.00  = 0.11733  ->  frozen  delta_farm  = 0.12   (0.12 x 6.00 = 0.72 = 40.9% of G)
   (C:  0.704 / 3.03  = 0.23231  ->  named   gamma       = 0.23   (0.23 x 3.03 = 0.70 = 39.6% of G)
                                             -- ROUND 2, NOT RUN, see 3.3)
```

All three land at **40.9% of G**, inside the skeleton's band by construction. **These numbers are
frozen. Nothing re-picks them after the blind commit.**

#### (iv) ⚠️ the natural unit weight is FAR outside a screening range — stated so nobody proposes it

[`SHAPES.md`](../invasion_term_build/SHAPES.md) §1 gives `beta = 1.0` the meaning *"a contestable
component is worth nothing in the differential"*. On this corpus `beta = 1.0` would contribute
`6.0` leaf points — **341% of the champion leaf's entire sibling-move spread**. It would not tilt
the leaf, it would *replace* it. The mid weights are two-thirds of an order of magnitude below the
"natural" unit, and that is the correct place for a screen to sit.

#### (v) ⚠️ THE ORDERING-BASIS CAVEAT — measured, and it constrains the read

A constant added to every sibling cannot reorder them. The decision-relevant quantity is therefore
the term's **variation across siblings**, not its level. Measured at the same 93 positions (median
over positions of the sibling p90−p10 of `T` across the mover's legal afterstates):

| shape | sibling p90−p10 of `T` (median) | mean | positions with any sibling variation |
|---|---|---|---|
| A | **1.60** | 1.65 | 74.2% |
| B | 0.00 | 1.00 | 28.0% |
| C | 0.77 | 0.67 | 75.3% |
| D | **0.00** | 0.11 | **5.4%** |

At the frozen mid weights this is `0.12 × 1.60 = 0.19` for A (**10.9% of G**), and effectively
**zero at one ply** for D. **This is a real, named limitation of the round-1 read**, not a hidden
assumption:

- The weights are derived on the **level** basis, per the skeleton's instruction, and the level
  basis is the right one for a *tree* search: a term that is constant across one ply's siblings is
  generally **not** constant across the subtrees a 2752-sim search backs up through, and its
  effect accumulates with depth. A one-ply Δ is a **lower bound** on the term's ordering effect,
  not a measure of it.
- But it means **a null on D is weakly informative about D's mechanism** — at these positions the
  farm differential barely moves within a ply. `READ_RULE.md` §5 records this: a D-null must be
  read as "no effect *at 2752, one-ply-flat at the census positions*", never as "farms don't matter".
- Both bases, both tables, are frozen here. Neither is re-derived after the fact.

### 3.2a — `alpha_cap = 11.0`: the Stage A census median invaded-feature value

The census's own field for the value of an invaded feature is `notes.invader_gain` — the points the
invader actually took from the merge. Over **the 51 `notes.mech == "merge"` rows** of
[`stage_b_plies.jsonl`](../e4_exploit_grading_20260825/stage_b_plies.jsonl):

```
n = 51    median = 11.0    mean = 12.16    p25 = 8.5    p75 = 15.0    p90 = 21.0    max = 42.0
47 of 51 strictly positive; positive-only median = 12.0
```

```
frozen:  invasion_alpha_cap = 11.0        invasion_stub_max_tiles = 2  (the default, unmoved)
```

**Cross-check against the leaf's own view of the same positions** (the rust `invasion_scan`, over
the 165 shape-B-eligible opponent features at those 93 states): `V(L)` median **5.0**, p75 8.0,
p90 10.0, max 18.0; and per *qualifying pair*, mean `V(L)` median **6.0**, max 12.67. So a cap of
11.0 **binds only the top decile** — it bounds the tail without reshaping the body, which is what
a cap is for. Measured directly: `T_B` median-when-fired is **8.0 at cap 11.0 and 8.0 uncapped**;
only the mean (9.59 vs 9.90) and the max (34 vs 38) move.

⚠️ `invasion_alpha_cap == 0.0` means **UNCAPPED** in this family (an explicit compare, not a
sentinel bug) — which is why the frozen value is `11.0` and not `0.0`, and why `G-CAPFWD` exists.

### 3.3 — shape C is DEFERRED to round 2. Recorded, with the reason.

[`SHAPES.md`](../invasion_term_build/SHAPES.md) §3: shape C is **defence-only** and
**not antisymmetric**; *"An H2H-vs-champion NULL for C is EXPECTED and is NOT disconfirming (the
champion does not invade). Screen C against a shape-B agent or against E4, never against the base
champion."* Every cell in this pair is vs the base champion. **Running C here would purchase a
guaranteed-uninformative null at 18 core-h.** It is deferred in full, and its round-2 weight is
named above (`gamma` mid `0.23`, bracket `0.08 / 0.23 / 0.69`) so round 2 inherits a derivation
rather than re-picking one.

This is the pair's **one deviation from the skeleton's cell count** (5 → 4), and it is the
skeleton's own §3 rule applied.

### 3.4 — the round-2 bracket, NAMED NOW, NOT RUN

`feedback_bracket_hyperparams`: three well-spread points, and a peak at a ladder endpoint is not
bracketed. The low/high points are `×⅓` and `×3` of the frozen mid:

| shape | low (×⅓) | **mid (RUN in round 1)** | high (×3) |
|---|---|---|---|
| A `invasion_beta` | 0.04 | **0.12** | 0.36 |
| B `invasion_alpha` (@ cap 11.0) | 0.03 | **0.09** | 0.27 |
| D `invasion_delta_farm` | 0.04 | **0.12** | 0.36 |
| C `invasion_gamma` *(round 2 in full)* | 0.08 | *0.23* | 0.69 |

⛔ **These are NOT run in round 1** and no branch in `READ_RULE.md` §4 may quote them as data.
They exist so that a `BRACKET-<shape>` or `PROMOTE-<shape>` branch fires into a *specified*
follow-up instead of a fresh argument about weights.

### 3.5 — ⚠️ A AND D ARE COLLINEAR. THE JOINT READING BASIS IS FROZEN HERE.

[`SHAPES.md`](../invasion_term_build/SHAPES.md) §4, verbatim:

> **⚠️ COLLINEAR WITH SHAPE A — the prereg must say so.** By construction
> `T_A == (cities+roads part of T_A) + T_D` exactly (unit-tested). Running `beta` and
> `delta_farm` together is **not** two independent effects; it is the parameterisation
> "`beta` on everything, `beta + delta_farm` on fields". Screening A against D is a SCOPE
> contrast, not a shape contrast, and a joint 2-D sweep must be read on the
> `(beta, beta + delta_farm)` basis.

**Frozen consequence for this round:** cell `A_MID` is `(beta, beta+delta_farm) = (0.12, 0.12)` —
the same 0.12 on everything. Cell `D_MID` is `(0.00, 0.12)` — nothing on cities/roads, 0.12 on
fields. So **A and D are two points on one two-dimensional surface, not two shapes**, and
`READ_RULE.md` §4.2 reads them jointly on that basis. In particular: "A fires and D does not"
means *the cities+roads part carries it*; "D fires and A does not" means *the field part carries
it and the cities+roads part cancels some of it*; both firing is one effect seen twice, **not two
confirmations**.

### 3.6 — ⚠️ ADOPTING SHAPE A OWES A CAPS RE-SWEEP

[`SHAPES.md`](../invasion_term_build/SHAPES.md) §1: shape A *"subtracts from the same objects the
capped opponent-anticipation bonus already discounts (`V25_OPP_CAP` / `opp_bonus_cap = 8`)"*, and
nothing in the build resolves that overlap.

**Stated before any number exists:** if `A_MID` (or `D_MID`, which is A restricted to farms) reads
`PROMOTE`, the production H2H it earns is **not** a straight adoption. Per
`feedback_bug_fix_shifts_optima` — *"a bug fix in scored heuristics shifts hyperparameter optima"* —
adopting A obliges a **re-sweep of `bonus_cap` / `opp_bonus_cap`** against the new term, because
the incumbent caps were tuned against a leaf that did not have it. A promotion here funds a
*sweep*, not a `governance/PRODUCTION.yaml` edit. `READ_RULE.md` §4's `PROMOTE-A` / `PROMOTE-D`
branches carry this obligation in their text.

---

## 4. THE PRIMARY STATISTIC AND ITS POWER — arithmetic BEFORE any number

```
Per cell, for each deck d in that cell's OWN range that appears in BOTH seatings:

    D(d) = ( diff(d, a_seat=0) + diff(d, a_seat=1) ) / 2

  where diff is the harness's own final-score margin, CANDIDATE minus OPPONENT
  (eval_fair_puct.py:1603 -- `diff = (s0-s1) if a_seat==0 else (s1-s0)`), in POINTS.

D      = mean( D(d) )  over n_common decks
SE(D)  = stdev( D(d) ) / sqrt(n_common)
z_D    = D / SE(D)
```

This is `eval_fair_puct._paired_z`'s own construction (`2371-2383`), and the adjudicator
recomputes it from the raw `seed*_a*.json` records as an independent **witness** (`RECON`).

**Sign convention, load-bearing:** `D > 0` means the **invasion term won**. `D < 0` means it
**lost** — a real, reportable finding (`READ_RULE.md` §4's `REVERSED-<shape>`), not a gate failure.

**Cluster = deck.** Not game, not seat. **Primary unit = POINTS per deck.** Elo is display-only
and is never a branch input.

**Within-band, deck-paired, one instrument ⇒ NO cross-band humility discount.** CL-068's 1.8–2.2×
over-dispersion applies to *cross-band* contrasts; each cell here is its own arm played on its own
decks in one launch window, which is the robust class CLAUDE.md exempts.

### 4.1 — σ_D, read off the instrument, not assumed

Ported from [`../h2h_22016_prep/READ_RULE.md`](../h2h_22016_prep/READ_RULE.md) §2.1, which
inverted seven `n=400`-deck, deck-paired, `fixed_v1`+R9, rust-backend cells already in
[`../../experiments/results.csv`](../../experiments/results.csv) (`SE = |margin| / |z|`,
`σ_D = SE × √400`):

```
median 13.15  |  b119e9 (closest analogue: two champions differing only in budget) 13.60  |  max 14.67
```

**This pair sizes on the MAX, `σ_D = 14.67`** — the conservative bound, on the same reasoning
`h2h_22016_prep` §2.1 gives: a false positive from an underpowered screen is the worse failure
mode, and this screen's whole job is to decide what gets funded next.

⚠️ **The sizing model is for POWER ARITHMETIC ONLY. Every bar in `READ_RULE.md` §4 is evaluated at
the cell's OWN REALIZED SE.** A cell whose realized dispersion differs from the model is read at
its realized dispersion, and the discrepancy is reported.

### 4.2 — what each n buys

```
SE_D(model C) = 14.67 / sqrt(n_decks)

    IDENT   n = 200 decks:  SE_D = 1.0374 pts   ->  2 sigma = +-2.075 pts
    A/B/D   n = 400 decks:  SE_D = 0.7335 pts   ->  2 sigma = +-1.467 pts
                                                    1 sigma = +-0.734 pts
  (at the median model 13.15 the A/B/D figures are SE 0.6575 / 2 sigma +-1.315 -- ~10% tighter)
```

**Power of an A/B/D cell, computed before any answer exists** (2-sided α=.05, model C):

| true effect | z @ SE=0.7335 | power |
|---|---|---|
| +0.72 pts/deck (= the frozen 40%-of-G target, if it transferred 1:1 to margin) | 0.98 | ~16% |
| +1.47 pts/deck | 2.00 | ~52% |
| **+2.06 pts/deck** — the **80%-power minimum detectable effect** | 2.80 | **80%** |
| +2.93 pts/deck | 4.00 | ~98% |

⚠️ **Read that honestly.** This cell **resolves** (2σ) at ±1.47 pts/deck and has **80% power** only
at ±2.06 pts/deck (≈ ±25–28 elo through the in-family bracket). **It is a SCREEN**: it is built to
catch an effect large enough to be worth a production H2H, and it is *blind by design* to a small
true positive. `READ_RULE.md` §4's `SCREEN-NULL` branch is written as a **bound**, never as a zero
— that is the single most important thing this design commits to before any number exists.

### 4.3 — elo is display-only, and the conversion is guarded

Ported verbatim in spirit from [`../h2h_22016_prep/READ_RULE.md`](../h2h_22016_prep/READ_RULE.md)
§1: under a null, `D ≈ 0` and a cell's own `elo_D / D` is a quotient of two noisy near-zero
quantities — it does not converge and its sign is not stable. So: **if `|z_D| ≥ 2.0`** the cell's
own realized `elo/pt` is reportable (cross-checked against the in-family bracket
`[16.74, 19.35]` elo/pt, an anomaly outside it FLAGGED and never a branch input); **otherwise** the
elo display is quoted as a **range through that pinned bracket** and labelled a bracket
conversion, not a measured scale. The adjudicator implements the branch-dependent rule and prints
which limb applied.

---

## 5. THE BAND

**Band `151000000000`.** ⛔ **NOT CLAIMED at freeze-draft time** — the row is in
[`BAND_CLAIM.json`](BAND_CLAIM.json) and is appended to
[`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) by the orchestrator in
the stamping commit. **`BAND_CLAIMED` is NOT created** (§0's interlock).

### 5.1 — allocation: one band, four DISJOINT deck ranges, no reuse

```
IDENT   151000000000 .. 151000000199    200 decks   400 games
A_MID   151000000200 .. 151000000599    400 decks   800 games
B_MID   151000000600 .. 151000000999    400 decks   800 games
D_MID   151000001000 .. 151000001399    400 decks   800 games
                                       ----------  ----------
                                       1400 decks  2800 games

SMOKE   151999999000 .. 151999999007      8 decks    16 games
        THROWAWAY -- disjoint, discarded, never pooled, never claimed, never adjudicated.
        Deliberately far above the cell ranges so no arithmetic slip can reach them.

NO TOP-UP RANGE IS RESERVED.  READ_RULE.md SS5 carries no top-up branch: a bounded null is a
licensed outcome of a screen, not a failure state to rescue.
```

⚠️ **DISJOINT, NOT SHARED — and this is a deliberate choice with a named cost.** `track_d2r4_prep`
gave both its cells the *same* 200 decks because its primary statistic was the **difference
between two cells**, which requires CRN. **This pair's primary statistic is each cell's own
internal deck-paired margin**, which is fully CRN'd *within* the cell (same deck, both seatings)
and needs nothing from the other cells. Disjoint ranges cost the primary read **nothing**.

What they do cost: **shape-vs-shape ranking is a deck-unmatched contrast.** `READ_RULE.md` §5
forbids any branch from taking "A read higher than B" as an input. Each cell is adjudicated against
**zero**, on its own decks, and never against a sibling cell.

### 5.2 — the all-branches sweep, re-run for this pair

The procedure of record ([`../carcasum_arb_challenge_prep/DESIGN.md`](../carcasum_arb_challenge_prep/DESIGN.md)
§4.1, as run by [`../track_d2r4_prep/DESIGN.md`](../track_d2r4_prep/DESIGN.md) §5): for **every**
ref in `refs/heads` and `refs/remotes`, read that ref's own `governance/BAND_REGISTRY.csv` **and**
every `measurement/**/BAND_CLAIM*.json` it carries, then take the lowest integer clear of
everything found anywhere. A registry check scoped to the checked-out branch is blind to an
unmerged sibling freeze branch — that is how `143e9` and `144e9` were double-claimed.

**Re-run 2026-08-26 over 139 refs (122 `refs/heads` + 17 `refs/remotes`) / 641
registry-and-claim files.** (Larger than `track_d2r4_prep`'s stamped "135 / 563" because several
`worktree-agent-*` branches, including this build's, have been created since.)

| band | status found | source |
|---|---|---|
| `143000000000` | claimed | `carcasum_rung2_prep` |
| `144000000000` | retired (D2 attempt 2's spent void) | `track_d2r2_prep` |
| `145000000000` | claimed | `track_d1_fair_rebase` (PRIMARY) |
| `146000000000` | **soft-reserved, no registry row on ANY of the 139 refs** | `track_d1_fair_rebase` — earmarked for its own n=800 extension |
| `147000000000` | claimed | `carcasum_arb_challenge_prep` |
| `148000000000` (+ top-up to `148000000699`) | claimed | `h2h_22016_prep` |
| `149000000000` | ⛔ RETIRED — D2 attempt 3's burn-in-abort void; ~40 decks of real records exist | `track_d2r3_prep` |
| `150000000000` | ⛔ **SPENT** — D2 attempt 4 ran clean and adjudicated `D2-BOUNDED-NULL`; `decision_influenced=yes` | `track_d2r4_prep` |
| **`151000000000`** | **free everywhere** | no ref, no registry version, no claim file mentions it (verified two ways: raw-mention sweep, and a direct `15[1-3]000000000,` row-start grep over every ref's registry — zero hits) |

`146000000000` is **skipped** on exactly the reasoning `carcasum_arb_challenge_prep`,
`h2h_22016_prep`, `track_d2r3_prep` and `track_d2r4_prep` all used: by the letter it is unclaimed,
but a sibling track has spent a committed paragraph earmarking it and asked that nothing run there
without a fresh funding decision. Taking it would manufacture the exact collision the corrected
procedure exists to prevent, the moment that extension is funded.

Per CL-068, **band identity is load-bearing**: never pool this pair's numbers across bands, and
`151000000000` **retires from confirmatory use** once it has influenced any decision.

⚠️ **`RELEASE-IF-NEVER-LAUNCHED`**: if no cell ever runs, `151000000000` is released. Once **any**
real record exists on it — including a round that voids on `G-IDENT` — the band is **spent**, on
the `149e9` precedent (a fifth of one cell was enough).

⚠️ **The sweep is RE-RUN immediately before the CSV append**, in the stamping commit, and the
append aborts if `151000000000` has appeared anywhere in the interim.

---

## 6. COST

### 6.1 — the model, built on the only clean rust calibration this program has

Inputs, measured (not modelled), from `track_d2r4_prep`'s tenancy-enforced clean window and its
realized close-out:

```
d2r4 REALIZED, rust fair PIMC, k4x1024 = 4096 total sims, W=22, exclusive:
    652.5 ms/move   (=> 0.15930 ms per total-sim)
d2r4 close-out banner, verbatim:
    "653.5 ms/move @4096 = +9.6% over linear (F ~= 160 ms/move fixed -- use the two-point F + c*N fit)"
moves per side per game (rust, fixed_v1):  69.00
W-utilisation at W=22 on the 5900XT:       ~84% (conservative; d2r4 realized nearer 97%)
```

⛔ **Use the two-point fit, NOT a linear per-sim rate.** The per-move cost has a ~160 ms fixed
component, so a naive `0.159 ms/sim × 2752` under-prices by ~11%:

```
ms/move(N)  ~=  160 + c*N,     c = (652.5 - 160) / 4096 = 0.12025

    @ 2752:  160 + 331 = 491 ms/move        (naive linear would say 438 -- 11% low)
```

⚠️ **Do NOT price this off `experiments/results.csv fair_ruler_rebase_2752`.** That row (the
skeleton's suggested source) is the right *contrast* but the wrong *era*: it is a **PYTHON**-backend
cell — 260.52 realized worker-s/game at W=12, 3071.66 ms/move = **1.116 ms per total-sim, 7× the
rust figure**. `track_d2r2_prep/DESIGN.md:401-406` explicitly forbids transferring those absolutes
to a rust cell. It is cited here only to record that it was checked and rejected.

```
per game, BOTH sides rust at 2752:
    2 x 69.00 moves x 0.491 s   =  67.7 s
    + ~6% harness/solver overhead (d2r4 realized 89.09 vs 83.8 projected)
                                =  ~72 s/game     <- the BASE figure
```

### 6.2 — per cell, and the named uncertainty

⚠️ **THE CANDIDATE-SIDE INVASION ARITHMETIC IS UNMEASURED.** The four shapes add a per-component
scan plus, for shape B, an ordered-pair scan over same-terrain components with a merge-distance-1
test — on top of a `decompose` the leaf already pays for. It is charged to the **candidate side
only** (the opponent's weights are all 0.0, so the gated statements are skipped). The honest range
is **0% to +50% on the candidate half**, i.e. **0% to +25% per game**, and the pair does not
pretend to know where in it the truth sits.

| cell | games | base (72 s/game) | +25% candidate margin | wall @ W=22, 84% util |
|---|---|---|---|---|
| `IDENT` | 400 | **8.0 core-h** | 8.0 core-h *(both sides weight-0 ⇒ no invasion arithmetic at all)* | **≈26 min** |
| `A_MID` | 800 | 16.0 core-h | **18.0 core-h** | ≈52–58 min |
| `B_MID` | 800 | 16.0 core-h | **18.0 core-h** | ≈52–58 min |
| `D_MID` | 800 | 16.0 core-h | **18.0 core-h** | ≈52–58 min |
| **TOTAL** | **2800** | **≈56 core-h** | **≈62 core-h** | **≈2.9–3.3 h** |

**The funding line in §0(a) should be read as ≈54–62 core-h / ≈2.9–3.3 h wall.** Plus the §9
smoke leg (16 games): **≤5 min**.

⭐ **THE OVERHEAD MEASURES ITSELF, FOR FREE.** Both sides of every cell are otherwise byte-identical
agents, so the cell's own `champ_prefix_ms_per_move` (the **candidate**) divided by
`rung_ms_per_move` (here the **opponent**'s own prefix time, `eval_fair_puct.py:2598-2600`) **is**
the invasion arithmetic's cost multiplier — with `IDENT`'s ratio as the ≈1.0 control.
`READ_RULE.md` §4.3 requires it printed on **every** branch including `U-UNREADABLE`, and it is
the one deliverable this pair produces whether or not any shape fires.

⛔ **It is DESCRIPTIVE-ONLY and is NEVER a branch input** — see §6.3.

### 6.3 ⭐ TENANCY CLASS: NON-EXCLUSIVE, RESULT-SAFE — the sensitivity-class argument

**This pair is SIMS-denominated. It has no equal-time gate, no burn-in, and no timing bar.** That
is the whole reason it can run where `track_d2r4_prep` could not.

The argument, in three steps:

1. **Every gate and the primary statistic are functions of GAME OUTCOMES only.** `D(d)` is built
   from final-score margins; the eighteen gates in `READ_RULE.md` §3 read manifest identity,
   config identity, seed coverage and failure counts. Not one of them reads a clock.
2. **Game outcomes are bit-identical under co-tenancy.** The harness is deterministic given
   `(deck seed, seat, config)` — `random.seed(seed)` is the only entropy source
   (`eval_fair_puct.py:2200`), determinizations derive from it (`fair_agent.py:947-951`), and the
   rust search is **bit-identical at any thread count** by construction: *"the merge is a
   sequential fold over an index-addressed result vector performed AFTER every join … this is what
   makes the answer bit-identical at any thread count, with zero scheduler nondeterminism"*
   (`rust/carc/carc-core/src/fair/mod.rs:22-32`). A co-tenant can change **wall clock** and
   nothing else. `W` itself is throughput-only for the same reason.
3. **Therefore the only quantity a co-tenant can move is the one this pair deliberately does not
   gate on** — §6.2's ms/move ratio, which is stamped `DESCRIPTIVE-ONLY` in the readout precisely
   because it is tenancy-sensitive and this pair will not enforce tenancy to protect it.

**Concretely: this pair MAY run beside `scripts/rustport/reconcile_exact_solver.py --workers 1`**
(live on the local box at freeze time) and beside other non-timing work. `feedback_no_agent_compute_beside_eval`
is honoured, not evaded: that rule's own text says a *TIMING* bench is an exclusive tenant. This is
not one. The launcher's census is therefore **ADVISORY** — it logs co-tenants, checks `nproc ≥ W`
and the RAM floor, and does **not** refuse. The only hard tenancy check that remains is a **foreign
`RUN_LIVE.json`** scan, which is about freeze-latch discipline and mixed-rev archives, not about CPU.

⚠️ **The one real risk is RAM, not CPU.** Concurrent solver jobs carry a 30 GB cap; the launcher
keeps `h2h_22016_prep`'s two-tier RAM floor (preflight and between-passes) and fails closed on it,
because a WSL VM teardown kills the run outright (`reference_wsl2_host_memory_teardown`).

### 6.4 — sequencing

**Cheapest-informative-first, in this order, one box:** `IDENT` → `A_MID` → `B_MID` → `D_MID`.

`IDENT` runs **first and alone** because it is a precondition on the other three (§3.1): if the
wiring is broken, it is found for **8 core-h** instead of 62. The launcher enforces the order and
**refuses to start any A/B/D cell until `IDENT`'s archive is complete and passes its bar** (an
in-launcher pre-check that shares its arithmetic with the adjudicator, so the two cannot drift).

---

## 7. THE WHEEL — a FATAL precondition, and the orchestrator's job

⛔ **THE SHARED VENV'S `carc_rs` IS STALE AS OF THIS FREEZE.** Measured on the local box at build
time, verbatim:

```
TypeError: LeafConfigRs.__new__() got an unexpected keyword argument 'invasion_beta'
```

A stale wheel is the **worst possible failure mode for this pair** and the reason `leaf_config_rs`
forwards the knobs conditionally: a build predating the family serves every default-off
(champion) config **unchanged and silently**, so a stale-wheel `IDENT` cell would pass, and only a
`TypeError` on the first A/B/D game would reveal it — *after* 8 core-h. Worse, a partial mismatch
would read as "the term is worth nothing" instead of "the term never ran".

**The launcher therefore PREFLIGHTS the wheel in a CHILD process, before any game, and makes a
stale wheel FATAL with the rebuild command in the message:**

- import `carc_rs` from the venv; assert `hasattr(carc_rs.MirrorState, "invasion_terms")`;
- construct `leaf_config_rs(dc.replace(CHAMP, invasion_beta=0.12))` — the **actual** nonzero
  forward, not a `hasattr` proxy — and fail closed on `TypeError`;
- assert the cell's own resolved `cand_leaf_cfg` reaches rust with the knob intact, and that the
  cap biconditional (§2.3) holds;
- record `backend_provenance()` into the manifest path the harness already stamps.

**Wheel identity in the manifest.** `carc_rs.__version__` is permanently `"0.1.0"` (the workspace
Cargo version; there is no `build.rs`, no vergen, no compiled-in sha) and **cannot tell a fresh
wheel from a stale one**. The real fingerprint is `rust_agent.carc_rs_build_id()` —
`f"carc_rs-{__version__}+{git_rev[:12]}+rustc{toolchain}"` — plus `carc_rs_binary_sha`, a
sha256[:16] of the installed `.so` (box-local). `eval_fair_puct.py:4814-4826` already patches
`carc_rs_build`, `carc_rs_version`, `carc_rs_binary_sha`, `rust_toolchain` and `mixed_builds` to
the manifest top level; `G-WHEEL` (`READ_RULE.md` §3) gates on `carc_rs_build` being present,
non-null, and **carrying the git rev of the merged invasion build**.

⛔ **THIS BUILD DID NOT REBUILD THE VENV WHEEL, DELIBERATELY.** The venv is shared with a live
solver run and `maturin develop` into shared site-packages while other runs may be live is the
phase-seam defect this program has a named rule against. **The orchestrator rebuilds at launch,
from the merged main tree:**

```
maturin build --release -m rust/carc/carc-py/Cargo.toml -o <wheeldir>
.venv/bin/pip install --force-reinstall --no-deps <wheeldir>/carc_rs-*.whl
```

*(The build's own fixtures were validated against an unpacked **shadow** wheel on `PYTHONPATH`,
site-packages untouched — the pattern [`SHAPES.md`](../invasion_term_build/SHAPES.md) §7
prescribes. The §3.2 weight derivation in this document was computed the same way.)*

---

## 8. WHAT THIS CANNOT SHOW

Stated before launch so no branch can be narrated past them:

1. **It is not a production result.** 2752 is the screening budget; production is 11008 (§2.4).
   The 2752↔deploy divergence caveat stands: **screens aim, they don't verdict.**
2. **It cannot resolve a small true effect.** 80% power only at ≈±2.06 pts/deck (§4.2). A null is
   a **bound**, and §4.2's table is the bound.
3. **It does not test shape C at all** (§3.3), and a C-shaped mechanism could be real while every
   cell here reads null.
4. **A and D are not independent** (§3.5). Two firings are one effect seen twice.
5. **It cannot rank the shapes against each other** — disjoint deck ranges (§5.1). Each cell is
   adjudicated against zero, never against a sibling.
6. **It tests ONE weight per shape.** A mid-null does not exclude an effect at `×3`; that is
   exactly what the round-2 bracket (§3.4) is for, and why the kill rule is stated at `+1σ` rather
   than at significance.
7. **It licenses no `governance/PRODUCTION.yaml` change and no champion-of-record discussion.**
   This screen is **link 1 of a four-link adoption chain** (`READ_RULE.md` §4's
   `PROMOTE-<shape>`): screen → production H2H → **external validation vs Carcasum** → the E4
   stream as final holdout. ⛔ **The external link is not optional.** An invasion term is by
   construction a term that exploits a *blindness of the incumbent champion*, so a margin measured
   *against that champion* is consistent with exploiting the opponent rather than improving the
   agent — and nothing inside the lineage can distinguish the two
   (`feedback_anchor_before_scaling`). A firing A or D additionally owes a caps re-sweep (§3.6).
8. **The one-ply sibling-Δ caveat** (§3.2 v): for D especially, this corpus shows almost no
   within-ply variation, so a D-null is weakly informative about D's *mechanism*.
9. **It does not measure whether the E4 opponent's invasions are actually exploitable** — that is
   the Stage A/B census's question, already answered, and the reason this family exists.

---

## 9. THE SMOKE LEG (pre-blind, mandatory)

n=16 games (8 decks × 2 seatings) on the **separate throwaway range**
`151999999000..151999999007` — never the cell band — running **`B_MID`'s config**, because B is the
cell with the most plumbing to break (a nonzero weight, the drift flag, *and* the cap-forwarding
biconditional). The smoke band is **DISCARDED and never pooled**.

**What the smoke leg verifies (all structural):**

(a) `n_failed == 0` and the harness runs clean at this exact invocation;

(b) every wheel / leaf / rules / cap-forwarding pre-flight fires against **real records** rather
than against the harness's documented behaviour;

(c) ⭐ **it produces the REAL MANIFEST the pair's instrument is validated against.** The leg
**ends by running [`analyze_screen.py`](analyze_screen.py) `--smoke-mode` against the smoke
archive** and requires it to fail **only** on the pinned allowed set — the band/N/deck-coverage
family a 16-game throwaway cannot satisfy by construction. This is the standing rule the
`h2h_22016_prep` post-mortem proposed after a gate written against a manifest the design
*described* rather than one the harness *emits* would have voided a healthy archive, and which
`track_d2r4_prep` was the first to adopt: *"the launcher's smoke step must end by running the
cell's own adjudicator against the smoke archive, and must require it to fail only on band/N
gates."* For the same reason `analyze_screen.py --selftest` **seeds its passing fixture from a
real manifest read off disk** and refuses to run against a synthesized-only fixture.

**The pinned allowed set** (`READ_RULE.md` §3.5 — a failure OUTSIDE it is a launch blocker):
`G-BAND`, `G-DECKS`, `G-N`, `G-SAT`, `G-IDENT`, `RECON/n_paired`. Everything else — `G-LEAF`,
`G-INVASION`, `G-CAPFWD`, `G-WHEEL`, `G-SINGLEVAR`, `G-RULES`, `G-BACKEND`, `G-BUDGET`,
`G-TIEARB`, `G-EXACT` — **must PASS on a 16-game archive**.

**What it explicitly does NOT do:** produce, confirm or influence any statistic. There is no knob
for any leg to re-pick (§0's frozen weights).

### 9.1 — the IDENT determinism probe (disclosed; not the smoke, not a cell)

To settle §3.1a empirically as well as from source, this build ran a **2-deck champion-vs-champion
probe** at the cells' exact knobs (`--opponent fair-champion --backend rust --k-dets 4 --sims 688
--opp-k-dets 4 --opp-sims 688 --exact-k 2 --paired`, `fixed_v1`+R9, plain curve125 both sides) on
throwaway dev seeds `990000000100..990000000101`, **twice**, to observe (i) run-to-run determinism
and (ii) whether the two seatings of a deck are mirrors under identical configs.

**Findings, quoted in §3.1a:** run-to-run **byte-stable** on all four records; seatings **not**
mirrors (`D = −11.5` and `+2.5`); deck CRN correct (identical `deck_hash` across seatings). Two
results follow, both load-bearing: the `IDENT` bar is **statistical** (§3.1a), and the harness's
determinism is **verified on this exact instrument**, which is what §6.3's tenancy-class argument
rests on.

It spent **no band**, wrote nothing into the repo, and **adjudicates nothing**. It is named here
so a reader is not surprised by a dev-seed directory in the build's scratch, and so the claim in
§3.1a is traceable to an observation rather than to a reading of the source alone.

---

## 10. CLOSE-OUT (on adjudication, not before)

The six-touch checklist, verbatim from `CLAUDE.md`: (1) [`../../experiments/results.csv`](../../experiments/results.csv)
row **per cell** (four rows, or `VOID` rows on the `U-UNREADABLE` precedent) · (2)
[`../../DECISIONS.md`](../../DECISIONS.md) index line · (3) status stamp on this `DESIGN.md`,
on [`READ_RULE.md`](READ_RULE.md), **and on [`../invasion_term_build/SHAPES.md`](../invasion_term_build/SHAPES.md)**
(whose banner currently reads `BUILT, NOT SCREENED`) · (4) governance row flip
([`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) `decision_influenced` +
band retirement; **plus a `CLAIM_REGISTRY` row** — a screen that kills a lever is a claim) · (5)
[`../../STATUS.md`](../../STATUS.md) top block · (6) the roadmap line in
[`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md). Then
`python3 scripts/doc_lint.py`. Commit; do not push without asking.

**Also owed, and specific to this family:** (7) a [`../../docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md)
row update for "contested-feature / invasion-risk term" carrying the outcome — including a
`SCREEN-NULL` outcome, which is exactly the knowledge the index exists to preserve; and (8) a
`governance/CHECKPOINT_LINEAGE.csv`-style lineage note for each nonzero-weight leaf hash produced
(a nonzero weight IS a new leaf), per [`SHAPES.md`](../invasion_term_build/SHAPES.md) §8.

**Owed regardless of branch, including `U-UNREADABLE`:** §6.2's measured invasion-arithmetic cost
multiplier (candidate ms/move ÷ opponent ms/move, with `IDENT`'s ratio as the control) — the one
number this pair produces whether or not any shape fires, and the number any future invasion work
needs before it can price itself.
