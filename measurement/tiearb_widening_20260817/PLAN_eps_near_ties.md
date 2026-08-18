# PLAN — rung (4) `eps > 0` near-ties

> **STATUS: PLAN ONLY, 2026-08-17. Not pre-registered, not funded to launch, nothing run.**
> Rung (4) of the tie-arbiter widening campaign ([roadmap](../../docs/PROGRAM_ROADMAP_2026-07-07.md),
> funded 2026-08-17). Queues behind the JCZ cells. Owner ranks this rung **LAST of the four**
> ("weakest prior"). Its virtue is **cheap falsifiability**, not ambition.
>
> ⛔ **BLINDNESS DISCLOSURE (read first).** The census this rung needs **already exists on disk,
> published 2026-08-12** (`measurement/tiletie_pricing_20260812/census/CENSUS.md`). §2's
> `phi(eps)` is therefore a **READ of a banked artifact, not a blind measurement** — blind-prereg
> discipline cannot apply and this plan does not pretend otherwise. The §3 kill bar is
> consequently derived from **power arithmetic (§4), which is independent of the census**, and is
> stated *before* the census read is applied to it. A blind read would need a fresh corpus
> (§2.4) — but §4 shows the bar is unreachable at any eps, so that spend is not recommended.

---

## 1. Provenance of the "66%" — what exactly is 66% of what

**Quoted exactly**, `measurement/tiletie_pricing_20260812/census/CENSUS.md` §1, row `ALL|ALL|ALL`:

> | ALL\|ALL\|ALL | 2607 | 66.0% [64.1, 67.8] (1720/2607) | 66.6% | 69.0% | 72.3% | 79.9% |

**The definition (decisive for this rung):** a row is `tie_exact` iff the **leaf's argmax over the
ply's TILE-placement candidates is NOT UNIQUE** — `top1 == top2` in f64, where `top2` is the next
**DISTINCT** leaf value and `tie_size_exact` counts every candidate at `top1`. So **66% = "the top
of the leaf ranking is a plateau of ≥2 moves"**, *not* "the top-2 are within some tolerance".
Instrument: `scripts/tiletie/chain_census.py::tie_report`, membership `(top1 - float(v)) <= eps`
(line 246) — an **absolute**, points-like tolerance.

**22.96 vs 65.98%** — same statistic, different stratum. `22.96 tied tile plies/game` = **597 tied
plies / 26 E4 games** (`tiletie_pricing_20260812/DESIGN.md:792`); 597 is exactly the `e4|ALL|ALL`
count above (65.5%, 597/912). `65.98%` is the pooled `ALL|ALL|ALL` figure (1720/2607).

**Consequence:** since the trigger is "argmax plateau" and `gap = top1 − top2` is the distance from
that plateau to the next distinct value, **`phi(eps)` is exactly the CDF of `gap`** over the
currently-untied rows — computable from banked fields at **arbitrary** eps, no re-run (§2).

---

## 2. Census — ALREADY BANKED, computed here, zero new compute

### 2.1 The artifacts (both, independently)

| corpus | file | rows | exact-tied |
|---|---|---:|---:|
| tiletie pricing | `measurement/tiletie_pricing_20260812/census/rows.jsonl` | 2,607 | 1,720 (65.98%) |
| tiearb2 corpus | `measurement/tiearb2_20260816/corpus/census/rows.jsonl` | 3,400 | 2,191 (64.44%) |

Both carry per-ply `top1`, `top2`, `gap`, `tie_exact`, `tie_size_exact`, and a `by_eps` block at
the pre-registered grid `{0.0, 0.05, 0.2, 0.5, 1.0}`. Leaf hash asserted `a36d2e15a3b3d71d`.

### 2.2 `phi(eps)` — the marginal ply mass a widened trigger buys

Computed as `#{untied rows with gap ≤ eps}`; "rel growth" is **relative to the 66% already fired**
(the operative currency — it is what multiplies the confirmed +3.07 pts/game).

| eps | new plies (tiletie) | rel growth | new plies (tiearb2) | rel growth |
|---:|---:|---:|---:|---:|
| 0 (committed) | 0 | — | 0 | — |
| **1e-9** (float noise) | 10 / 887 | **+0.58%** | 7 / 1209 | **+0.32%** |
| **0.05** (first lattice rung) | 17 | **+0.99%** | 15 | **+0.68%** |
| 0.15 | 75 | +4.36% | 82 | +3.74% |
| 0.25 | 110 | +6.40% | 130 | +5.93% |
| 0.50 | 166 | +9.65% | 228 | +10.41% |
| **1.00** (one full point) | 366 | **+21.28%** | 477 | **+21.77%** |
| 2.00 | 540 | +31.40% | 753 | +34.37% |

**The two independent corpora agree to within ~1pp at every rung.**

### 2.3 The gap quantum — RESOLVED, and it is not a float-noise story

- **Smallest nonzero gap = 4.44e-16** (one ULP). **10 / 887** untied plies (tiletie) and **7 / 1209**
  (tiearb2) sit below 1e-9 — genuine arithmetic indifference hidden by bit-inequality.
- Above that the value set is a **comb, not a continuum**. CENSUS.md §3's top-gap histogram:
  1.0 (94×), 3.0 (34×), 0.25 (28×), 1.5 (28×), 2.0 (23×), 0.5 (19×), 4.0 (19×), 0.75 (18×),
  0.15 (15×), 1.25 (14×). The lattice comes from an **integer scoring base** plus the frozen
  `CURVE125 = (-10, -5, -1.25, 0, 2.5, 3.75, 5, 6.25)` (all exact multiples of **1.25**) plus
  probability-scaled closure terms at ~0.05 resolution.
- **⇒ the first real rung above float noise is ~0.05, and it is worth ~1% relative.** Getting
  ~20% relative requires **eps ≈ 1.0 — a full point of Carcassonne score.** That is not a
  "near-tie"; it is overriding a substantive leaf preference.

### 2.4 If a blind/fresh census is nonetheless wanted (not recommended)

`scripts/tiletie/run_census.py` on a fresh band: leaf-only, **0.0192 s/ply contended** (CENSUS.md's
own upper bound). A 20,000-ply scan = **380 worker-s = 0.11 worker-h** → **~13 s at W30, ~17 s at
W22**. It is free in both currencies. It is *not* recommended because it cannot change §4.

---

## 3. ⭐ THE KILL BRANCH — pre-registered form, bar set from §4, not from the census

> **`K-DEAD` (the cheap kill):** *if the first lattice rung above float noise (`eps = 0.05`) adds
> **< 5% relative** fired plies, the rung dies for free.*
>
> The **5%** is not arbitrary and is not fitted: §4 shows that even at a **full** transfer of the
> exact-tie effect, ~5% relative growth needs **n ≈ 10⁵ games/cell**, ~125× the largest cell the
> programme has ever funded (Stage-2 Phase B, n=800/cell). 5% is the point below which the rung
> is unmeasurable *by arithmetic alone*, whatever the census says.

**Applying the banked census: `K-DEAD` FIRES.** eps=0.05 adds **+0.99%** (tiletie) / **+0.68%**
(tiearb2) — **5–7× below the bar, on both corpora independently.**

> **`K-STRUCTURAL` (the second, independent kill):** the rung needs an eps satisfying **both**
> (i) `m(eps) ≥ 0.30` (§4's affordability floor) and (ii) the added plies are *near*-ties, i.e.
> the leaf's preference over them is small enough that arbitration plausibly beats it.
> **These are mutually unsatisfiable on the banked distribution:** `m ≥ 0.30` requires
> `eps ≳ 1.5–2.0` points, at which the arbiter is overriding a leaf preference of up to two full
> points. **`K-STRUCTURAL` FIRES.**

**Two independent kills, zero worker-seconds spent. The rung is dead as a strength lever.**

---

## 4. Power — the arithmetic the bar is built from

**Effect model.** `Δ(eps) = phi₀ × m(eps) × δ_new` pts/game, where `phi₀ = 17.5725` (Stage-2 Phase B
realized ARB), `m(eps)` from §2.2, and `δ_new` = pts/tied-ply the arbiter adds on the **new** plies.

**Anchors (verified, not assumed):**
- `δ_exact` = **+0.1441** pts/tied ply, se 0.0479, **z +3.01** (Stage-1b arm `H`, B=16, n=1350).
- In-game cross-check: **+3.0700** pts/game ÷ 17.5725 = **0.1747** pts/fired ply. Consistent.
- Precision: **paired_z +4.445 at n=800/cell** ⇒ `se_M = 3.0700/4.445 = 0.6906` ⇒
  **sd of the deck-paired per-game margin ≈ 19.53 pts**.

**Sizing at a HALF effect** (`δ_new = 0.5 × 0.1441 = 0.0721`), 2σ, per cell:

| eps | m | Δ (pts/game) | n — model A (sd fixed) | n — model B (CRN-conditioned) |
|---:|---:|---:|---:|---:|
| 0.05 | 0.0099 | 0.0125 | **9.7 M** | **451,000** |
| 0.25 | 0.0640 | 0.0811 | 232,000 | 69,800 |
| 0.50 | 0.0965 | 0.1223 | 102,000 | 46,300 |
| 1.00 | 0.2128 | 0.2696 | 21,000 | **21,000** |
| 2.00 | 0.3140 | 0.3978 | 9,644 | 9,644 |

- **Model A** = naive, `sd = 19.53` fixed, `n ∝ 1/m²`.
- **Model B** = the one real saving: under CRN (same salt/seeds/decks) the eps-cell and the eps=0
  cell are **bit-identical on every game with no newly-fired ply**, so `sd_eff ≈ √(m/0.2128) × 19.53`
  and `n ∝ 1/m`. Generous, and it does not rescue the rung; at eps ≥ 1.0 nearly every game diverges
  (`λ = 3.74` new plies/game ⇒ p ≈ 0.98) and the models converge.
- **At FULL transfer** divide by 4: best case is still **≈ 5,250 games/cell at eps = 1.0** — 6.6×
  Stage-2 Phase B, for a lever whose own risk model says full transfer cannot happen.

**The offline escape hatch.** The per-ply instrument is ~10³× more efficient than games: Stage-1b
resolved `δ` to se 0.0479 on n=1350 positions, so a half-effect at 2σ needs se ≤ 0.036 ⇒
**N ≈ 2,390 near-tie positions** — genuinely affordable. **This is the only fundable version of the
rung** and it is what §5 prices. It buys a *per-ply* number, never a deploy licence: converting it
to a game verdict re-enters the table above.

---

## 5. Cost + ETA if §3 had not fired (the offline pricing design only)

**Corpus.** Near-tie supply already banked at `0 < gap ≤ 1.0`: **366 + 477 = 843** positions from
6,007 scanned plies (14.0% yield). N=2,390 needs **~17,100 plies scanned** — census cost
**0.09 worker-h**, negligible. **A fresh band is still required** (`BAND_REGISTRY.csv` max claimed
= `132000000000`; reserve **`133000000000`**, shared with the other rungs if §7 is adopted).

| leg | worker-h | @ W30 | @ W22 |
|---|---:|---:|---:|
| census / mining scan (leaf only) | 0.1 | <1 min | <1 min |
| arbiter side, tier1-greedy **RUST** — `N × Ā 3.0022 × B 16 × c_tier1_rust 0.178232` | **5.7** | 11 min | 16 min |
| oracle side, clair-puct (Stage-1b rate 0.0889 worker-h/pos, **PYTHON-era**) | **213** | **7.1 h** | **9.7 h** |
| **total** | **≈ 219** | **≈ 7.3 h** | **≈ 9.9 h** |

**Two currencies, per Stage-2 §0.G — do not conflate them.** The oracle leg dominates by 37× and is
the term to attack (it is python-era; if clair-puct has a rust path, re-price before funding).

---

## 6. Gates and branches skeleton (for a mechanical READ_RULE, if ever revived)

**Primary statistic — and the null is NOT random.** At exact ties the champion's tie-break is
arbitrary, so `random` was the honest control. **At eps>0 the leaf has a real preference**, so:

> `Δ_leaf = oracle(arbiter's pick) − oracle(leaf's argmax pick)`, over plies with `0 < gap ≤ eps`.

Prior art that makes the harm branch live, not a formality: the **same-compute RANDOM control was
ACTIVELY HARMFUL — −4.4287 pts/game, z −6.669**. A leaf-tied set is *not* interchangeable moves;
a leaf-*near*-tied set is strictly less interchangeable.

| gate | condition | meaning |
|---|---|---|
| `E-CONFIRMED` | `Δ_leaf > 0` at 2σ | arbitration beats the leaf's small preference. Licenses a DESIGN for an eps-widened shape — nothing more. |
| **`E-HARM`** ⚠️ | **`Δ_leaf < 0` at 2σ** | **arbitration OVERRIDES a correct leaf preference and LOSES.** Kills the rung *and* fires a review rider on eps=0: report `Δ_leaf` vs `gap` to check the harm does not extrapolate back toward the plateau. |
| `E-FREE` | CI contains 0 and excludes ±0.0721 | powered null. Rung retires; the leaf is right at the margin. |
| `E-INCONCLUSIVE` | neither | report, do not adjudicate, do not top up without a fresh read-rule. |
| `E-MONOTONE` (rider) | `Δ_leaf` regressed on `gap` | the decision-relevant shape: if `Δ_leaf` decays to 0 by `gap ≈ 0.15`, no eps is ever justified and this closes the rung permanently. |
| `G-FIRE` / `G-TOOL` / `G-STAT` | inherit Stage-2 verbatim | `cand_leaf_hash` MUST equal `a36d2e15a3b3d71d` (INVERTED gate); manifest must round-trip `cand_tiearb.eps`. |

**No code change is needed to run any of this.** `--cand-tiearb-eps` **already exists**
(`eval_fair_puct.py:3212`, `type=float, default=0.0`), the pyo3 boundary already validates
`tiearb_eps ≥ 0` and finite, `SearchConfig::tiearb_eps` defaults `0.0`
(`rust/carc/carc-core/src/search/mod.rs:193`), and the rust predicate `(top1 - cv.value) <= eps`
(`tiearb.rs:218`) is **character-identical in semantics** to the python instrument's
`(top1 - float(v)) <= eps` (`chain_census.py:246`) — both **absolute**, same subtraction order,
same `<=`. **Nothing anywhere has ever RUN at eps > 0** (every manifest reads `"eps": 0.0`);
only the offline census exercised the grid.

---

## 7. Deploy note — eps>0 grows `phi`, hence in-game clock

Stage-2 realized **`ms_ratio` 2.4242 (ARB) / 2.4163 (RND)** at `phi ≈ 17.05–17.95`, reconciled by
`1 + (9.57 × phi / 72) / 1.7`. Scaling that by §2.2's `m`:

| eps | `phi` | predicted `ms_ratio` | vs eps=0 |
|---:|---:|---:|---:|
| 0 | 17.57 | 2.374 | — |
| 0.05 | 17.75 | 2.388 | **+0.6%** |
| 0.25 | 18.70 | 2.462 | +3.7% |
| 1.00 | 21.31 | 2.666 | **+12.3%** |
| 2.00 | 23.09 | 2.805 | +18.2% |

**The cost is NOT the objection** (owner: "don't let that be the constraint") — the objection is
§3/§4. But two riders: (i) **arm count also grows** — mean `min(size,4)` 3.128 → 3.611 at eps=1.0,
with the **fraction of plies hitting the J=4 cap rising 32.8% → 64.2%**, so at eps=1.0 the arbiter
is choosing a random 4-subset of a mean-14 tied set and **may not even contain the leaf's argmax
group**; (ii) **on-device**, `rho_phone` was **5.520 at B=16** and Stage 2 licensed **no** phone
deploy — eps=1.0 multiplies that by ≈ `1.213 (phi) × 1.155 (Ā)` ≈ **1.40×**, making an
already-unlicensed cost worse.

---

## 8. Interactions with the other rungs

- **⭐ Rung (1) meeple plies — YES, PIGGYBACK, one replay pass, two counters, near-zero cost.**
  [`PLAN_meeple_ties.md`](PLAN_meeple_ties.md) §"Script" already reuses `chain_census.tie_report()`
  with the **identical** eps grid `(0.0, 0.05, 0.2, 0.5, 1.0)`, so its rows will carry `by_eps`
  for free. **The single ask to the rung-(1) planner: also emit the scalar `gap = top1 − top2`
  per row** (both are already computed inside `tie_report` to detect the tie at all — zero extra
  leaf calls). That upgrades the 5 grid points into the **arbitrary-eps CDF** of §2.2 and yields
  the meeple-ply analogue of this entire rung for one extra field.
  (`scripts/tiletie/` is outside the commit-freeze; `scripts/classical_search/` is not — no change
  is proposed there.)
- **Rung (2) `B > 16`** — orthogonal in mechanism, but note `B` and `eps` trade against each other
  for a fixed clock budget: §7 shows eps=1.0 costs +12.3% clock, which at fixed budget would buy
  `B ≈ 14` instead of 16. Given rung (2)'s prior is stronger, **eps should never be spent from a
  budget rung (2) could use.**
- **Rung (3) `J > 4`** — **materially coupled, and it is a warning.** Rung (3) exists because the
  J=4 cap truncates 18% of tied sets; §7 shows eps=1.0 pushes that to **64.2%**. Widening eps
  without first resolving `J` would make the cap the dominant behaviour of the arbiter. **If eps
  is ever revived, it must queue AFTER rung (3), never before or beside it.**

---

## 9. Open questions for the owner

1. **The float-noise band is a free HYGIENE fix, not a strength lever — take it?** 10/887 and
   7/1209 untied plies differ by ~1 ULP (min 4.44e-16). Bit-exact equality makes the fired set
   depend on float association order, hence on backend/compiler/SIMD — exactly the surface Phase
   A's bit-exactness gate polices, so `eps = 1e-9` would make the trigger *backend-robust*. But it
   is ~0.5% of plies (unmeasurable as strength) **and it changes the fired set, so it needs its own
   bit-exactness re-gate.** Recommend **document, do not deploy**, unless a future rust/python
   divergence is traced to it.
2. Record `K-DEAD`/`K-STRUCTURAL` as a `docs/LEVER_INDEX.md` row + DECISIONS line (retired at zero
   cost) — or run §2.4's blind fresh census anyway for the record? (§4: it cannot change the verdict.)
3. Fund the offline-only probe (§5, ≈219 worker-h, N≈2,390) purely for `E-MONOTONE`, which would
   close eps *permanently* rather than leaving it "weakest prior, untested"? **Recommendation: no**
   — spend it on rung (1) or (2) and cite this document as the closure.
4. `δ_new`'s 0.5 transfer fraction is **assumed, not measured.** Right planning value, or should the
   harm prior (`δ_new < 0`) be treated as equally likely given the RND control's −4.43?
