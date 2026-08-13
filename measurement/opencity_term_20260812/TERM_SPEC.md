# OPEN-CITY DISCIPLINE — a leaf term that penalizes the builder's own large open cities

> **STATUS: BUILT, DEFAULT-OFF, NOT RUN (2026-08-12).** Code + tests + reconcile gate only —
> **zero games, zero evals, zero calibration, no deck band claimed, no elo statistic anywhere
> in this document.** `LeafConfig.opencity_dose` defaults to `0.0`, which is a byte-identical
> no-op: the champion leaf of record (`a36d2e15a3b3d71d`, `governance/PRODUCTION.yaml`) is
> untouched and `governance/PRODUCTION.yaml` was not edited. This document is the *design of
> record* for the term and the *proposed* measurement path; nothing in it is authorized to
> run. The next step is the calibration in §7, whose read-rule must be committed **before**
> its numbers are read.

**Lever identity (for the grep that finds this later):** "penalize large open cities" ·
"open-city discipline" · `LeafConfig.opencity_dose` / `opencity_size_min` /
`opencity_edge_min` / `opencity_symmetric` · `flat_leaf.flat_opencity_term` ·
`carc_core::leaf::opencity_term` · `--cand-leaf-json '{"opencity_dose": …}'` ·
`CARCASSONNE_OPENCITY_*` · reconcile family `--configs opencity` · `tests/test_opencity_term.py`.

---

## 1. Why this term exists

**Authorization of record.** `BACKLOG.md` 2026-05-16 named it; `docs/LEVER_INDEX.md`
("Genuinely untried", item 7) carried it as **NEVER-TRIED** through 2026-08-12; and
`docs/research/PRO_STRATEGY_SCAN_2026-08-12.md` **§F1** is the external endorsement — the
scan's #2-ranked finding and the only one in the whole scan with unanimous convergence.

**Mechanism (F1, verbatim).**

> "Carcassonne city scoring gives no per-tile-size bonus (2 pts/tile + 2 pts/shield whether
> the city is 2 tiles or 12), while completion probability drops and steal/merge
> vulnerability rises as a city grows — every additional open edge is both a harder
> tile-matching requirement to close AND another door for an opponent to join for a
> tie/majority. Guidance converges on: build small (2–4 tile) cities, and when choosing
> which of two builders to expand, **prefer starting shapes with one open edge, tolerate
> two, avoid three.**"

Four independent, non-affiliated guide sites converge without citing each other
(tilelord, boostyourplay, elusivemeeple, meeplemountain — quoted in §F1). The
elusivemeeple wording is the sharpest and is what the default `opencity_edge_min = 2`
encodes: *"start with one that leads to a single edge – two edges is okay, three edges is
bad."*

**Why the champion's leaf cannot express it today.** The v2.9 leaf prices an incomplete
city's *anticipated value* — `closure_p[open_n] × city_root_delta`, capped at
`bonus_cap` — and its *realized* value through `flat_base_score`. Both are monotone
**increasing** in city size. Nothing in the leaf is monotone increasing in *exposure*. So
a 7-tile city with 3 open edges reads as a large asset with a modest closure discount,
where the guides read a liability: same 2 pts/tile as a 2-tile city, a materially worse
chance of ever closing, a meeple locked up meanwhile, and three doors an opponent can
walk through. This term supplies the missing risk price.

**Distinctness from the two adjacent killed levers** (§F1's own disambiguation):

| adjacent lever | what it priced | verdict | how this term differs |
|---|---|---|---|
| targeted denial (`denial_dose`) | *opponent's* near-complete large cities | harmful at the 2750 instrument, bounded-null at deploy (CL-079) | opposite side of the board (the **builder's own** city) and opposite corner of the (size, open) plane (**wide open**, not near-complete) |
| farm-growth bonus | *farm* size | null | cities, and a **penalty** not a bonus |

---

## 2. The term, exactly

Implemented in `src/carcassonne_ai/flat_leaf.py::flat_opencity_term` and mirrored
bit-exactly by `rust/carc/carc-core/src/leaf/mod.rs::opencity_term`.

For each **city component** in the flat decomposition, define `owner` = the player with a
**strict weighted-meeple majority** (`MeepleType.BIG` = 2, the `_final_scores` semantics);
a tie or an unmeepled city has no owner. The component **qualifies** iff all of:

1. it has an owner (strict majority — never a tie, never unmeepled);
2. it is **incomplete** (`not city_root_finished[root]`);
3. it is **closable**: `city_root_open_n[root] > 0` (the `open_n == 0` D16 board-edge city
   can never close — that is a *scoring* fact the base term already prices, not an
   exposure fact);
4. it is **wide**: `open_n >= opencity_edge_min`;
5. it is **large**: `tiles >= opencity_size_min`, where `tiles` is the count of **distinct
   tiles** the component spans (`len(city_root_coords[root])` in Python,
   `city_root_tiles[root]` in Rust).

A qualifying component contributes to **its owner's** penalty:

```
contribution = (tiles - opencity_size_min + 1) * (open_n - opencity_edge_min + 1)
```

— linear escalation on **both** axes, exactly `1.0` at the joint threshold corner.
Per-side contributions are `fsum`-reduced (order-independent). Then

```
T = pen(self) - pen(opp)      # opencity_symmetric = True  (default)
T = pen(self)                 # opencity_symmetric = False (ablation)
score -= opencity_dose * T
```

applied as a **separate, uncapped statement** immediately after the denial subtraction and
before the meeple/curve term, in that fixed order (float addition is non-associative; a
fused expression would break python↔rust bit-exactness).

**Why tiles and not points.** Denial's size axis is `city_root_delta` (points). This term
deliberately uses **tile count**, because F1's mechanism is that the marginal tile of a big
city earns *the same* 2 points as the marginal tile of a small one while adding *all* of
the completion and steal/merge risk. Exposure scales with the object's **extent**, not with
its value. (Shields raise value without adding an edge or a matching requirement, so they
should not raise the risk price.) This is a design commitment, not a knob — see §9.

---

## 3. SCOPE DECISION — the builder's own cities, and why

**Decision: the penalty follows the BUILDER.** It is charged to whoever holds the strict
majority in the overextended city. It is *not* a bonus for the opponent having a
near-complete city, and it is *not* a general "big cities are bad" term applied
regardless of ownership. Four reasons, in descending weight:

1. **The adjacent opponent-side lever has already been measured, and it did not pay.**
   Targeted denial — a static leaf term pricing the *opponent's* cities — read
   **harmful** at the 2750 ablation instrument (pooled n=400, margin z −2.293) and a
   **bounded null** at the real deploy budget (n=800, margin z −0.127); `CL-079`.
   Repeating the opponent-side shape with a different sign is the same bet with worse
   odds.
2. **The champion's SEARCH already finds denial emergently, so a static opponent-side
   term double-counts.** `measurement/e4_games/ANCHOR_INTERVIEW_2026-08-12.md` **J12**:
   the human anchor independently describes the champion extending *his* city to prevent
   closure and prices the trade correctly (sacrifice 1–2 pts to halve the value and lock
   a meeple). The interview's §4 item 2 states the consistent read explicitly: *"the
   search already finds denial when it is actually good; a static leaf bonus for it
   double-counts and distorts."* A builder-discipline penalty is not in that class — it
   prices a property of the position the search **cannot** discover from a shallow
   rollout, because the payoff (an unclosed city at game end, or a steal 15 plies later)
   lands past the horizon.
3. **It is what the guides actually say.** F1's advice is addressed to the *builder*
   ("build small", "when choosing which of two builders to expand"). It is a policy over
   your own move, not a read of the opponent's board.
4. **It is the only version that is genuinely NEVER-TRIED.** §F1's own disambiguation:
   "Neither killed test evaluated a general penalty on the *acting player's own*
   open-city size/edge-count."

**Symmetry: default SYMMETRIC (`opencity_symmetric = True`), argued.** Symmetric means the
differential `pen(self) − pen(opp)` — *both players' own cities*, each charged to its own
builder. It does **not** mean "penalize the opponent's cities"; the opponent's
overextension enters only as the absence of a penalty against me, which is the
arithmetic definition of a differential evaluation. Three arguments:

- **It preserves antisymmetry.** Every other structural term in the leaf is antisymmetric
  (`base` is a score differential, the closure bonus is `self − opp`, the meeple curve is
  a differential), so `V(s, p) = −V(s, 1−p)`. Symmetric open-city keeps that:
  `T(p) = −T(1−p)` exactly (pinned by `test_antisymmetry_on_the_corpus`). The asymmetric
  variant does **not** — it makes the leaf non-zero-sum, which is exactly the wart
  `denial_dose` already carries (`V(p) + V(1−p) = −dose·(T_own + T_opp) ≠ 0`). A
  non-zero-sum leaf is a real hazard in a negamax/alpha-beta tail, and the exact-K
  endgame solver sits behind this search.
- **A one-sided penalty is a level shift, not a preference.** Charging only my own
  overextension shifts my evaluation of *every* position where I hold a big open city,
  including positions where the opponent holds a bigger one. The differential is what
  actually encodes "prefer the shape that leaves *me* less exposed than *him*", which is
  the comparative the guides are giving.
- **It is not a smuggled opponent-side denial term.** The opponent-side effect here is
  *the opposite sign* of denial: denial feared the opponent's **near-complete** city;
  this term is silent on near-complete cities (`open_n < edge_min` never fires) and only
  ever rewards me for the opponent's **wide-open** overextension. The two predicates are
  disjoint by construction at the default thresholds (denial: `open_n ≤ 2`; open-city:
  `open_n ≥ 2` **and** `tiles ≥ 4` — they can overlap only at exactly `open_n == 2`, and
  only if both doses are set at once, which no proposed cell does).

`opencity_symmetric = False` is retained as an explicit **ablation knob** (own-side-only,
non-negative penalty) so the symmetry choice is falsifiable rather than assumed. It is not
a default and is not in the proposed screen ladder.

---

## 4. Interaction with the existing city terms — it ADJUSTS, never replaces

The term is a *separate, uncapped subtraction*. It does not touch, gate, scale, or replace:

- `flat_base_score` — the realized `1 pt/tile + 1 pt/shield` for an incomplete city stands;
- `flat_closure_bonus` — the anticipation credit `closure_p[open_n] × city_root_delta` for
  the very same city stands, and is still subject to `bonus_cap` / `opp_bonus_cap`;
- the F6 soft caps, the meeple curve, the C7 terms, `bag_close`.

So a big wide-open city keeps earning everything it earns today and *additionally* pays a
risk price. This independence is deliberate: a dose sweep then moves exactly one thing —
the price of exposure — instead of confounding it with the closure schedule's shape (the
2026-05-15 "bug fix shifts hyperparameter optima" lesson in reverse). It is pinned by
`test_leaf_moves_by_exactly_dose_times_term`: the leaf moves by exactly `−dose × T` and by
nothing else.

Deliberately **uncapped**, like denial: capping it under `opp_bonus_cap` would make the
term unable to express more fear than the cap already expresses, which is the whole point
of adding it.

---

## 5. Parameter table

All four knobs are flag-tunable; none of the taste is hardcoded. Defaults below are the
*shape* the guides describe, **not** a calibrated recommendation — §7 picks the cell.

| knob | type | default | units | meaning | plausible calibration range | bracketing note |
|---|---|---|---|---|---|---|
| `opencity_dose` | float | `0.0` | leaf points per unit `T` | `0.0` = term fully OFF (early branch → byte-identical champion). Scales the whole penalty. | `0.25 – 4.0`, geometric ladder | The denial screen's `{1.0, 4.0}` ladder proved 4.0 is far enough out to resolve decisively (z −11). Start the ladder **below** 1.0: `T` here is a *product* of two excesses and grows faster than denial's linear `T`, so equal dose is a larger perturbation. Fix the ladder before reading anything (§7). |
| `opencity_size_min` | float | `4.0` | **distinct TILES** ⚠️ | Minimum city extent for the penalty to fire. ⚠️ NOT the same units as `denial_size_min`, which is in points. | `2.0 – 6.0` | F1 says "build small (2–4 tile) cities", so 4 is the first tile that is *not* small. Bracket **both** sides: 3 (aggressive), 4 (spec), 5–6 (conservative). The wiring gate (§6) shows `size_min=6 ∧ edge_min=3` never fired on the golden corpus — do not start there. |
| `opencity_edge_min` | int | `2` | distinct open cells (`open_n`) | Minimum openness for the penalty to fire. | `2 – 3` | This is the guides' converged rule made numeric: at 2, a 1-open city never fires ("prefer"), 2-open weighs 1 ("tolerate"), 3-open weighs 2 ("avoid"). `1` is available but changes the term's meaning (it would price *every* incomplete city) — treat `1` as a different term, not a rung. Must be `>= 1`; `c5_leaf_override` raises on `< 1`. |
| `opencity_symmetric` | bool | `True` | — | `True` → `T = pen(self) − pen(opp)` (antisymmetric leaf). `False` → `T = pen(self)` (own-side only). | `{True}` for the screen; `False` only as a follow-up ablation if a symmetric cell resolves positive | Not a rung on the dose ladder. Flipping it is a *different term*, and mixing it into the same ladder is the forking-path pattern the denial calibration was written to prevent. |

Worked values at the defaults (`size_min=4`, `edge_min=2`), penalty per city:

| tiles ↓ / open_n → | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| 3 | 0 | 0 | 0 | 0 |
| 4 | 0 | 1 | 2 | 3 |
| 6 | 0 | 3 | 6 | 9 |
| 8 | 0 | 5 | 10 | 15 |

(At `dose = 1.0` those are leaf points, against a leaf whose closure bonus is capped at
8.0 — so a `dose` near 1.0 with a 6-tile 3-open city is already a large perturbation. This
is the main reason the ladder should start below 1.0.)

---

## 6. What is built, and the off-state proof

**Code (all default-off; no production path changes behaviour):**

| file | change |
|---|---|
| `src/carcassonne_ai/virtual_score_v2.py` | 4 `LeafConfig` fields + doc block; `CARCASSONNE_OPENCITY_*` in `_config_from_env`; object-path `NotImplementedError` (fail loud, never a silently-intact leaf) |
| `src/carcassonne_ai/flat_leaf.py` | `flat_opencity_term`, `_opencity_off`, the two dose-gated subtractions (int + pre-round float paths), cy-dispatch gate |
| `src/carcassonne_ai/heuristic_prior_mcts.py` | the same gated subtraction in the PUCT float leaf (calls the shared helper, does not re-implement) |
| `src/carcassonne_ai/rust_agent.py` | `leaf_config_rs` forwards the 4 knobs as **conditional kwargs** — a stale `carc_rs` keeps serving default-off configs and raises `TypeError` on a nonzero dose |
| `src/carcassonne_ai/alphabeta_agent.py`, `scripts/classical_search/c5_leaf_override.py` | `_LEAF_HASH_EXCLUDE_IF_DEFAULT` += the 4 fields (so `a36d2e15a3b3d71d` recomputes unchanged); `c5_leaf_override` also gains the cy-fallback WARNING + fatal threshold sanity |
| `scripts/measurement_infra/snapshot.py` | `_FROZEN_HASH_DEFAULT_OFF` += the 4 fields (so `158f17ff…` / `6dfffd57…` / `7fc930b8…` recompute unchanged) |
| `rust/carc/carc-core/src/leaf/mod.rs` | 4 `LeafConfig` fields, `curve125()` defaults, `opencity_term`, `LeafTerms.opencity_term`, the gated subtraction in `leaf_terms_with` |
| `rust/carc/carc-py/src/lib.rs` | `LeafConfigRs` signature + fields; `leaf_terms()["opencity_term"]` |
| `scripts/rustport/reconcile_leaf.py` | new `--configs opencity` family (5 cells incl. a dose-0 identity control and an asymmetric cell); `CY_UNSUPPORTED` += the 4 live cells; `_to_rs` forwarding |
| `tests/test_opencity_term.py` | **new**, 25 tests |
| `tests/test_frozen_substrates.py`, `tests/test_v29_flat_curve.py`, `tests/test_t3_optuna.py` | mirrored exclusion dicts (3 sites) |

**Deliberately NOT implemented in `flat_leaf_cy.pyx`** — the third knob family (after the
F7b farm knockouts and denial) with no Cython implementation, on the same decision: the
candidate cells run `--backend rust`, where no Python leaf is computed at all. A set dose
therefore *always* leaves the cy fast path for the bit-exact pure-Python flat leaf. That is
a **speed** fact, not a correctness one, and it is enforced: `_opencity_off` gates both
dispatchers and `test_cy_fast_path_refused_for_opencity` proves a stale `.so` can never
serve an open-city-blind leaf to an open-city run.

**Off-state proof — status: PASS.**

- **3-way reconcile, golden corpus** (`--configs opencity --corpus golden`):
  **76,876 values compared, 0 mismatches, verdict PASS**, artifact
  `G2_leaf_opencity_golden.json` in this directory. This includes the `golden_disk` leg —
  448 values compared against the **frozen pre-change** `tests/golden/golden_fixture.json`
  on disk, i.e. the literal "python vs rust vs pre-change golden" check.
- The `opencity-d0-identity` cell (dose `0.0` with `size_min` moved to 2.0, `edge_min` to
  1, and `symmetric` flipped to `False`) reproduces `prod-curve125` exactly on every leg —
  the dose gates the whole term.
- `test_off_is_bit_identical` asserts `.hex()` equality of the pre-round float leaf and
  int equality, for a default-off-but-thresholds-moved cfg, over a random-play corpus.
- Champion fingerprints recompute unchanged: `_leaf_hash(CHAMP) == a36d2e15a3b3d71d`,
  `_frozen_config_hash` `158f17ff76adaa02` / `6dfffd57051690f2`
  (`test_champion_leaf_hashes_unchanged`, `test_frozen_recipe_hashes_unchanged`, plus the
  pre-existing `test_denial_term` / `test_frozen_substrates` / `test_v29_flat_curve` /
  `test_t3_optuna` assertions on the same constants, all still green).

**Wiring evidence — the term is not inert** (from the same gate's bite tally; this is a
*wiring* number, **not** a calibration and **not** a flip rate — it counts leaf values that
differ from the champion's, not decisions that change):

| cell | leaf values changed vs champion (golden corpus) |
|---|---|
| `opencity-d0.5` / `opencity-d1.0` (defaults 4 tiles / 2 edges, symmetric) | **21.9 %** |
| `opencity-d1.0-asym` (own-side only) | 15.0 % |
| `opencity-d2.0-s6-e3` (6 tiles / 3 edges) | **0.0 % — never fired** |

The 0.0 % row is the load-bearing one for §5: at `size_min=6 ∧ edge_min=3` the predicate
did not fire once on the golden corpus. Bracket **downward** from the defaults, not upward.
(A leaf-value change is an upper bound on a decision change; the flip rate that actually
gates funding is §7's, and it will be materially lower.)

**Tests: 25 in `tests/test_opencity_term.py`** (all pass; 2 of them skip on a `carc_rs`
build that predates the term, and both **ran and passed** against the freshly-built wheel).
Neighbouring suites re-run green: `test_denial_term` (19), `test_frozen_substrates`,
`test_v29_flat_curve`, `test_v29_phase_multiplier`, `test_f7b_farm_knockout` (52 together),
`test_t3_optuna` (17, with the leaf env set).

### ⚠️ MANUAL STEP — the `carc_rs` wheel is NOT installed

The Rust code compiles (`cargo check --workspace --tests`, clean) and a wheel was built and
verified **in a scratch directory only**. It was deliberately **not** installed into the
shared `.venv`, because `carc_rs` lives in `site-packages` and replacing it would expose
every box's future spawn-workers to a mid-build revision (the worktree-isolation rule).
**Before any open-city cell can run**, on **every** box:

```bash
# 1) build + install the wheel (per box, from the merged tree)
cd /home/doctor/projects/carcassone/rust/carc/carc-py
maturin develop --release            # or: maturin build --release && pip install --force-reinstall <whl>

# 2) prove the build actually carries the term (the stale-wheel trap)
python -c "import carc_rs; carc_rs.LeafConfigRs([(1,0.5)],8.,8.,opencity_dose=1.0, \
  opencity_size_min=4.0, opencity_edge_min=2, opencity_symmetric=True)"   # TypeError == stale

# 3) full 2-leg reconcile (python == rust) over every corpus
.venv/bin/python scripts/rustport/reconcile_leaf.py --corpus all --configs opencity --workers 12
```

Step 2 is not optional: `leaf_config_rs` is fail-closed (a stale wheel raises `TypeError`
rather than silently dropping the knobs), but a *launcher* that swallows the exception
would produce a champion-vs-champion cell that reads as a perfect null. The denial campaign
codified this as `scripts/classical_search/chain_capability_probe.py --require denial …`;
an `--require opencity` mode should be added there before launch.

---

## 7. Calibration — recommended protocol (offline E4-replay flip rate, read-rule first)

**Recommendation: reuse the denial calibration verbatim**
(`measurement/denial_screen_20260811/CALIB_READ_RULE.md` + `CALIB_READOUT.md`, instrument
`scripts/classical_search/denial_e4_replay.py`). It is the strongest methodological
artifact the 2026-08 campaign produced, and this term needs it *more* than denial did,
because its firing rate is threshold-sensitive over a wide range (see the 0.0 % row above).

The protocol, restated for this term:

1. Replay the banked E4 human-vs-champion archives. At each **champion decision ply**,
   re-run the production search under CRN with the open-city leaf and with the production
   leaf, and record whether the **pick changes** — a binary flip. Nothing about strength,
   EV, or regret is measured; the calibration corpus (human games) and the screen corpus
   (fresh self-play decks) are disjoint by design.
2. **Commit the read-rule before reading any arm.** The floor arithmetic is unchanged: an
   n=200 deck-paired screen resolves ≈ ±2.0 pts/deck at 2σ; a champion plays ~70
   decisions/game; the required gain per changed move is `2.0 / (70·p)`. So
   `p < 5 %` cannot produce a resolvable screen result *even if the term is genuinely
   good*, and the branches are `FUND-SMALLEST` (`p ≥ 0.10`) / `FUND-MARGINAL`
   (`0.05 ≤ p < 0.10`, written up as underpowered by construction) / `STRUCTURAL-NO-FUND`
   (`p < 0.05` everywhere and flat) / `UNRESOLVED` (`p < 0.05` but rising).
3. **Fix the arms and the dose ladder in advance**; no post-hoc dose insertion. Proposed
   arms — deliberately bracketing the spec cell on **both** sides per the
   `bracket-hyperparams` rule, and note the denial precedent that the *production-spec*
   arm read below the floor (4.45 %) while a looser arm read 13.6 %:

   | arm | `opencity_size_min` | `opencity_edge_min` | doses |
   |---|---|---|---|
   | A (spec) | 4 | 2 | 0.5, 2.0 |
   | B (loose) | 3 | 2 | 0.5, 2.0 |
   | C (tight) | 6 | 3 | 0.5, 2.0 |

   Arm C is expected to read ≈ 0 (§6) and is included precisely so the ladder's shape is
   measured rather than assumed. `opencity_symmetric` is held at `True` in all arms.
4. "Where the flips land" stays **descriptive only** — explicitly barred from the funding
   decision.

---

## 8. What the eval would be

**Do NOT run a 2750-only screen and call it a verdict.** `CL-079` (minted 2026-08-12 on the
denial pair) states that **2750-ablation-instrument verdicts do not reliably transfer to
the deploy budget** — the denial term resolved negative at 2750 (margin z −2.293, n=400)
and read a bounded null at deploy (margin z −0.127, n=800). A 2750 result is licensed as a
*screen*, never as a kill or an adoption.

Proposed sequence, both stages pre-registered before either runs:

- **Stage 1 (screen, optional and clearly labelled):** `eval_puct_priors.py --cand-sims
  2750`, the funded cells from §7. Its only licensed outputs are "keep" / "the term does
  not express" — a negative here does **not** kill the lever (CL-079), and a positive here
  does **not** promote it.
- **Stage 2 (the verdict, mandatory before any claim): deploy-budget fair PIMC cell.**

  | | |
  |---|---|
  | candidate | champion leaf + open-city discipline at the calibrated cell; `cand_leaf_hash` stamped and asserted ≠ champion |
  | opponent | unmodified production champion, leaf `a36d2e15a3b3d71d` |
  | budget, BOTH arms | `--k-dets 8 --sims 1376` = **11008** per decision (`governance/PRODUCTION.yaml` `fair_deploy`) |
  | harness | `scripts/classical_search/eval_fair_puct.py --info fair --opponent fair-champion` |
  | fixed | `--backend rust`, `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1`, `--exact-k 2` both arms, `--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits`, `--paired`, `--shared-claim`, `--no-results-csv`, `nice -n 19`, detached |
  | candidate leaf | `--cand-leaf-json` file carrying the open-city knobs **plus** curve125 verbatim, with `--allow-cand-curve-drift` |
  | n | **≥ 800** deck-paired (400 decks × 2 seats) |
  | band | **fresh**, claimed at launch via `claim_next_band.py` into `governance/BAND_REGISTRY.csv`; retires from confirmatory use once it influences a decision |
  | statistic | the **deck-paired margin** z is the primary read; elo is reported but is the weaker statistic (CL-072: elo alone failed to resolve where margin did) |

  Pre-flight gates, all three mandatory (cloned from
  `measurement/denial_screen_20260811/run_deploy_confirm.sh`): git-rev identity across
  boxes · `_leaf_hash(cell JSON)` equals the expected candidate hash **and** differs from
  the champion's · `chain_capability_probe.py --require opencity` on **every** box (the
  stale-wheel trap of §6).

- **Branch map (pre-register verbatim):** `|z| ≥ 2.0` → resolved; `1.5 ≤ |z| < 2.0` → the
  authorized top-up on fresh decks **of the same band**; `|z| < 1.5` → bounded null,
  reported strictly as "bounded at the realized 2σ", never as a kill or a win.
- **Never pool** the 2750 and deploy cells, and apply CL-068's 1.8–2.2× over-dispersion
  inflation to any cross-band contrast.

---

## 9. Double-count caveat, and open design questions

**Double-count caveat (read before funding).** Everything a leaf term prices, the *search*
may already be pricing implicitly. J12 is the recorded instance of exactly that failure
mode for the neighbouring lever: the champion's search already plays denial, so a static
denial bonus "double-counts and distorts"
(`measurement/e4_games/ANCHOR_INTERVIEW_2026-08-12.md` §4 item 2). The honest version of
this term's hypothesis is **the horizon argument**: an open city's cost is realized either
at scoring (an unclosed city scores half) or at a steal/merge many plies later — both
typically *past* an 11008-sim PIMC horizon, and the exact-K=2 tail is far too shallow to
see it. If that argument is wrong — if the search already discounts wide-open cities
through the closure schedule and the endgame tail — this term will read null at best and
harmful at worst, exactly as denial did. Two cheap diagnostics that would sharpen the prior
*before* spending a deploy-budget cell (both offline, no games):

1. **The F1 diagnostic the scan itself proposed** — bucket the 26 archived E4 games'
   city-claim decisions by final size / open-edge count, AI vs human. If the champion's
   own cities are already no larger/no more open than the human's at claim time, the
   premise is weak before any leaf change.
2. **A closure-schedule confound check** — the leaf already discounts a 3-open city to
   `closure_p[3] = 0.05`. Measure how much of the proposed penalty is *already* expressed
   by that discount at the candidate thresholds; if the two are near-collinear, the term
   is a re-parameterization of `closure_p`, and the cheaper experiment is a `closure_p`
   re-sweep, not a new term.

**Open design questions (deliberately left open; each is a knob-shaped fork, so none should
be resolved by looking at outcome data):**

1. **Tiles vs points as the size axis.** §2 commits to tiles on mechanism grounds. If the
   term ever resolves positive, `city_root_delta` is the obvious ablation — but adding it
   as a *switch* now would double the calibration grid.
2. **Multiplicative vs additive escalation.** The current shape is the product of two
   linear excesses, which grows fast (see §5's table). An additive shape
   `a·(tiles−s+1) + b·(open−e+1)` is the natural alternative and would need its own dose
   scale. The product was chosen because F1's mechanism is a *conjunction* (large AND
   open), and a product is the smallest faithful encoding of a conjunction.
3. **No per-city cap.** Denial is uncapped and this term follows it, but a 10-tile 4-open
   city contributes 21 leaf points at dose 1.0, which can dominate the whole evaluation.
   `opencity_cap` is a plausible fifth knob; it was omitted to keep the calibration grid at
   3 live dimensions. Revisit only if a dose ladder shows the term behaving as an
   all-or-nothing switch.
4. **Meeple-locking is priced twice, weakly.** A big open city also locks a meeple, which
   the v2.9 meeple curve already prices. The overlap is real but small (the curve prices
   the *count* of free meeples, not the *quality* of what they are stuck in) and is not
   modelled here.
5. **Farms.** A city adjacent to a contested field has an entirely different risk profile
   (a stolen city also moves farm value). Out of scope; noted so a later reader knows it
   was considered and dropped, not missed.

---

## Pointers

- `docs/research/PRO_STRATEGY_SCAN_2026-08-12.md` §F1 — the endorsement + the four guides
- `docs/LEVER_INDEX.md` — "Genuinely untried" item 7 (this term's NEVER-TRIED entry of
  record); the "leaf ideas from the competitive-strategy literature" row (targeted denial)
- `BACKLOG.md` 2026-05-16 — the original naming
- `measurement/denial_screen_20260811/` — the template this build clones
  (`CALIB_READ_RULE.md`, `PREREG_DRAFT.md`, `PREREG_DEPLOY_CONFIRM.md`,
  `run_deploy_confirm.sh`)
- `measurement/e4_games/ANCHOR_INTERVIEW_2026-08-12.md` J12 + §4 — the double-count gloss
- `governance/CLAIM_REGISTRY.csv` CL-079 — 2750 verdicts do not reliably transfer
- `governance/PRODUCTION.yaml` — the champion leaf + `fair_deploy` budget of record
- `tests/test_opencity_term.py`, `scripts/rustport/reconcile_leaf.py --configs opencity`
