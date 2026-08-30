# OM-M1 — DEVIATIONS

House class distinction, carried from `IS-D1` (invasion round 1) and the
`everyply` `EP-D1..D5` precedent: a **deviation** is a departure from the frozen
[`PREREG.md`](PREREG.md) that a later reader must know about to interpret a
number. Execution-layer / statistics-blind items are recorded too; they are
labelled as such.

Nothing here has yet produced a flip rate — the gate has **not been run**. These
are build-time findings.

---

## `OM-D1` — the 22.96 constant is the WRONG POPULATION (corrected before freeze)

**Class: statistics-affecting, caught and corrected BEFORE any leg ran.**

The funded menu row and the tiearb plans quote **22.96 fired tile plies/game**.
Traced to source it is `597 tied plies / 26 E4 games`
(`measurement/tiletie_pricing_20260812/DESIGN.md:792`, quoted verbatim in
`../tiearb_widening_20260817/PLAN_eps_near_ties.md` §1) — the **E4 phone /
`fixed_v1` / owner-opponent stratum**, not the walled champion-selfplay corpora
this gate replays.

Measured on this gate's own population (2026-08-30, 120 `champ449` games, leaf
`a36d2e15a3b3d71d`, zero playouts):

| statistic | value |
|---|---:|
| banked exact-tied TILE plies/game (`tile_gap_rows.jsonl`, 449 games) | **45.26** (20,322 / 31,827 rows = 63.9 %) |
| this replay's DEPLOYED fired plies/game | **37.03** |
| fired ÷ tied | **0.818** |

The gap between 45.26 and 37.03 is the arm dedupe: tie sets that collapse to a
single distinct afterstate are NOT fired (`arbitrate_decision`'s
`arms.len() < 2` rule). The widening census reports the analogous MEEPLE
collapse at 13.7 %; 18.2 % on TILE is the same shape.

**Effect on the bar: NONE, and provably so.** §5's bar is
`target / (F × R_x)`, and `R_x = G_arb / (F × P)`, so `F` cancels exactly and
the bar is `target × P / G_arb = 0.21723` at any fire rate. The prereg was
rewritten to state the bar in the cancelled form and
`tests/test_omm1_refuter_gate.py::test_the_bar_does_not_depend_on_the_fire_rate`
asserts it at `F ∈ {22.96, 37.0, 45.26, 100.0}`. Had the bar consumed `F`
directly it would have been ~2× wrong.

**Effect on `G-FIRE`: the guard was rewritten.** The first draft bracketed the
replayed rate at `[18, 28]/game` around 22.96 — a guard that a *correct* replay
fails. It was replaced by an exact per-ply join (below) plus an advisory
fraction bracket. Recorded because the replaced guard was written into a draft
of the prereg before the number existed; the frozen text carries only the
corrected form.

---

## `OM-D2` — a residual 0.45 % `G-FIRE` join disagreement, measured and UNEXPLAINED

**Class: statistics-blind at stage 1 (it concerns the CROSS-CHECK, not the
population), but it must be resolved before the funded run.**

`G-FIRE`(a) joins every replayed FIRED ply against the banked census's
`tie_exact`. On the 120-game slice:

```
joined 4,443 · disagree 20 · agreement 0.99550
```

i.e. 20 plies where **this replay's rust trigger fires and the banked python
census recorded the leaf ranking as UNTIED**. The threshold is 0.99 and it
passes, but 20 is not zero, and classifying the 10 recorded witnesses by the
census's own `gap = top1 − top2` makes the residual worse, not better:

| class | banked `gap` at the witness | count (of 10) | reading |
|---|---|---:|---|
| **ULP** | `1.7763568394002505e-15` | **2** | a python-vs-rust f64 summation difference at the last bit. The tie predicate is EXACT equality at `eps = 0.0`, so one ULP flips it. Expected and benign. |
| **REAL** | `0.25`, `0.40`, `0.50`, `0.50`, `0.75`, `0.75`, `1.00`, `1.00` | **8** | **not** a rounding artifact. |

⛔ **The REAL class is a genuine, previously-unmeasured divergence between
`carc_core::tiearb::chain_values` and its python definition of record.** The
possibility that the two are measuring different predicates is excluded:
`meeple_tie_census.tile_gap_ply` calls `chain_census.chain_values` +
`chain_census.tie_report` **verbatim** (its own docstring says so), and
`chain_census.chain_values` is exactly what `tiearb.rs`'s module docs name as
the definition the rust ports. Same leaf hash (`a36d2e15a3b3d71d`), same
`walled` profile, same corpus, same `(deck_seed, ply)` keys, same combined
tile+meeple ply indexing (99.55 % of 4,443 keys agree, so the boards match).

So at ≈ **0.45 % of fired plies the rust chain value ranking is tied where the
python's is separated by a quarter-point to a full point.** The existing
`reconcile_leaf` gates prove leaf-value bit-exactness on single states; they do
not cover the CHAIN (tile + best meeple continuation), which is where this
lives. Leading hypotheses, none yet tested: the meeple-continuation argmax's
tie-break, the border-wrap legacy-scorer fallback inside the continuation, or a
`bag_close` / closure-anticipation term evaluated on a different afterstate.

**Why it does not invalidate this instrument.** The gate's population is
defined by the **rust** trigger — the shipped `arbitrate_decision` path, which
is the one the deployed arbiter actually uses in play. Every ply the gate
arbitrates is a ply the deployed arbiter would have arbitrated, by construction
(`tiearb::tests::the_multi_leg_decision_fires_on_the_deployed_trigger`). The
census is an independent implementation used as a cross-check; the disagreement
is evidence about the CROSS-CHECK, and about the rust port, not about whether
the gate measured the arbiter.

**Owed before the funded run:** localise the REAL class on 2–3 witnesses by
running `tiearb_probe`'s `chain_values` against
`scripts/tiletie/chain_census.chain_values` on the identical state and diffing
per-action. Witnesses in hand: `(28000000011, 24)` gap 0.75, `(28000000015, 72)`
gap 1.00, `(28000000059, 138)` gap 1.00, `(28000000052, 48)` gap 0.25.

**Owed regardless of this gate:** this is a finding about the SHIPPED tie
arbiter, not about OM-M1. If the rust port fires at plies the leaf-of-record
would not call tied, the deployed arbiter has been arbitrating a slightly wider
set than its spec for as long as it has been deployed. Worth its own line in the
roadmap whichever way OM-M1 reads.

---

## `OM-D3` — `tiearb2_850` is untracked, and the smoke ran on `champ449` alone

**Class: execution-layer.**

`measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl` (2.1 MB, 850
games) exists in the main working tree but is **not in git**, so it is absent
from the build worktree. Every build-time number above is therefore `champ449`
only, and `build_fired_plies.py` was given an `--allow-missing-corpus` flag that
records the omission in `FIRE_CENSUS.json::corpora_missing` rather than
silently narrowing the population.

PREREG §3 adjudicates on the **POOLED** row over both corpora. The funded run
must be launched from a tree where both files are present, and the readout must
show `corpora_missing: []`. A run that reads only `champ449` is a DEVIATION and
halves the sample.

---

## `OM-D4` — the refuter's armed path scores in f64, the disarmed path in int64

**Class: design, stated in the prereg (§4.3) and pinned by tests — recorded here
because it is the one place the instrument is NOT a pure superset of the
deployed code.**

`RuleBasedPlayer`'s per-candidate score is the **int64** base terminal-score
differential. The invasion potentials are f64 and the of-record dose contributes
at most `0.99` points, so an int64 round-trip would swallow the entire `R_ref`
signal and make a kill uninterpretable. The armed path therefore argmaxes in
f64.

The disarmed path is untouched: `RefuterConfig::is_inert()` (all invasion
weights `0.0`) and `refuter: None` both take the pre-change int64 branch, and
both identities are pinned bit-for-bit —
`tier1::tests::refuter_none_is_bit_identical_to_the_pre_change_playout`,
`tier1::tests::refuter_with_zero_weights_takes_the_unchanged_int64_path`,
`tiearb::tests::refuter_with_zero_weights_is_bit_identical_to_plain_greedy`,
`tiearb::tests::symmetric_leg_is_bit_identical_to_the_deployed_arbiter`.

Two consequences a reader should hold:

1. `with_legacy_scorer` (`FORCE_LEGACY`) is **not honoured** on the refuter
   path — that knob contrasts the two int64 scorer routes and the refuter is not
   part of that identity.
2. At the wrapping border `candidate_leaf` takes the legacy engine route and
   never builds a `Decomp`, so **no invasion term can be computed there**. The
   refuter is inert on those candidates (counted by `border_fallbacks`), which
   very slightly under-states expression. Documented in
   `candidate_leaf_refuter`'s own doc comment.

---

## `OM-D5` — the gate was BUILT beside a live eval, and was not RUN

**Class: execution-layer.**

The S1 G3 round held both boxes on 2026-08-30. Per the funding brief the build
and its unit tests ran (`nice -19`, `-j 4`, ≈ 60 s of cargo + 47 s of rust tests
+ 20 s of leaf-only replay on 120 games), and **no rollout campaign was
launched**. The `G-TENANCY` guard therefore has nothing to report yet; the cost
table in §8 is a projection from banked `c_tier1_rust`, not a measurement of
this instrument, and is labelled as such.

The rust extension was built into a scratch `CARGO_TARGET_DIR` and imported via
`PYTHONPATH`, never installed into the shared `.venv` — installing a fresh
`carc_rs` wheel mid-round would have swapped the code under the live
rev-pinned cells (memory `feedback_worktree_isolation_live_tree`).
