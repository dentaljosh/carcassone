# READOUT — HP-M1 "bag-conditioned field-fate forecast" KILL GATE

> ## ⛔ VERDICT: **MECHANISM DEAD.**
> **Bar (a) FAILS · Bar (b) passes (weak) · Bar (c) FAILS, and fails BACKWARDS.**
> Per the frozen verdict rule in [PREREG.md](PREREG.md) §6, any bar failing kills
> the mechanism: **no build, no band, no dose ladder, no follow-on cell.**
> Zero games were played. Nothing was promoted, and no registry or roadmap row is
> written by this instrument (orchestrator's call).

| | |
|---|---|
| Prereg | [PREREG.md](PREREG.md), frozen **before** any statistic was computed |
| Deviations | [DEVIATIONS.md](DEVIATIONS.md) — 2 entries, both statistics-blind |
| Machine / cost | laptop (`laptop-wsl`), 16 workers, `nice -n 19`; **~3 min wall**, zero $ |
| Judge | **NONE** (CL-085) — the only arbiter is the engine's own realized award |
| Leaf of record | `harness_leaf_hash = a36d2e15a3b3d71d` (curve125, `champion_factory.verify_leaf` PASS) |
| Wiring | **505/505 games reconciled** (E4 53+2+1, SP449 449/449); R9 expected=observed on every leg |

---

## 1. Realized row counts (bar (a) requires these stated)

| universe | rows | scoring | **zero** | zero-rate | Stage-A pooled-50 |
|---|---|---|---|---|---|
| **PRIMARY — E4 champion, `fixed_v1`** | **199** | **107** | **92** | **46.23 %** | 46.2 % (85/184) |
| E4 owner, `fixed_v1` | 219 | 206 | 13 | 5.94 % | 5.4 % (11/205) |
| E4 all profiles, champion / owner | 209 / 231 | | | 46.41 % / 5.63 % | |
| SP449 champion self-play (`walled`) | 3 080 | 2 605 | 475 | **15.42 %** | — |

The primary universe reproduces the Stage-A headline to within a tenth of a point
(**46.23 %** vs 46.2 %) on a **larger, independently re-replayed** corpus (53
`fixed_v1` archives now on disk vs the 50 pooled then). The instrument is
measuring the thing the funding was about.

E4 profile split: `fixed_v1` 418 rows · `walled` 17 · `app_aug2` 5. The primary
universe is `fixed_v1`-only per PREREG §1.2; the 22 non-`fixed_v1` rows are
reported but adjudicate nothing (rules-epoch discipline).

---

## 2. The three bars

### Bar (a) — AUC ≥ 0.70 · **FAIL**

| forecast | AUC (primary, out-of-fold) |
|---|---|
| **F-FIT** (45 features, 5-fold grouped by game) | **0.6518**  CI95 [0.5657, 0.7324] |
| F-PF (parameter-free, `proj_finished_cities − invade_risk`) | 0.6480 |

`0.6518 < 0.70` ⇒ **FAIL** on the pre-registered point-estimate rule.

**Stated straight:** the 95 % CI (game-clustered bootstrap) **does include 0.70**,
so bar (a) *on its own* is a fail at n=199 that a larger corpus could in principle
overturn. It is not the load-bearing kill — bar (c) is. Reported this way
deliberately: overstating (a) would be minting a false kill, and understating
(c) would be minting a false survival.

### Bar (b) — beat B-LEAF **and** B-BAG on identical rows · **PASS (weak)**

| | AUC | Δ vs F-FIT | Δ CI95 |
|---|---|---|---|
| F-FIT | 0.6518 | — | — |
| B-LEAF (production leaf's own marginal valuation of the farmer) | **0.5610** | +0.0909 | [−0.0014, 0.1851] |
| B-BAG (the incumbent `bag_close` variant, same construction) | **0.5610** | +0.0909 | [−0.0014, 0.1851] |

Point estimates strictly greater than both ⇒ **PASS as written**, labelled
**weak** because both difference CIs graze zero.

**Two things this pass is not.** First, §4 shows the margin over B-LEAF is a
*claim-timing clock*, not bag counting — so bar (b) is not evidence for HP-M1.
Second, the two baselines are **identical to sixteen digits**, which is itself a
finding: **`b_leaf == b_bag` on 3 454 of 3 498 rows (98.7 %), and on 199/199 of
the primary rows.** The incumbent bag variant is **inert on farmer deployments**
— `bag_close` gates *city/cloister* closure anticipation and never touches a
field. LEVER_INDEX row 202 ("TRIED — ties the champion; C5 cell null") is
consistent with this and is not disturbed: nothing here re-opens it.

### Bar (c) — seat contrast must run owner-high / champion-low · **FAIL (reversed, significant)**

Forecast applied by the **SP449-trained** model, which never saw an E4 row (so the
contrast cannot be manufactured by fitting on owner rows):

| | mean forecast | zero-rate |
|---|---|---|
| E4 owner deployments (n=231) | **1.569** | **5.6 %** |
| E4 champion deployments (n=209) | **1.871** | **46.4 %** |
| **Δ (owner − champion)** | **−0.302** | |
| game-clustered seat-permutation p (10 000) | **1.0 × 10⁻⁴** | |

Required direction: **owner-high**. Observed: **champion-high**, and not
marginally — the reversal is the most significant number in the run.

**This is the kill.** The champion's farmer deployments score *better* under the
bag-conditioned forecast than the owner's, while scoring **zero 8× more often in
reality**. Whatever separates the two seats' farm outcomes, the bag at claim time
prices it **backwards**.

---

## 3. Secondary and tertiary (adjudicate nothing)

| | AUC |
|---|---|
| SP449 champion self-play, F-FIT out-of-fold (n=3 080, 449 games) | 0.5926 |
| SP449, F-PF | 0.5468 |
| SP449, B-LEAF / B-BAG | 0.5417 / 0.5414 |
| Transfer: fit on all SP449 → predict E4 champion rows | 0.6750 |

The powered corpus is **16× the primary** and the forecast gets *weaker* there
(0.59), not stronger. A signal that dilutes as n grows by an order of magnitude
is the shape of a nuisance correlate, not a mechanism.

---

## 4. Why it fails — post-hoc, descriptive, adjudicates nothing

Computed after the bars were read ([POSTHOC.json](POSTHOC.json)), to answer the
one question the bars raise: *where does the 0.65 that does exist come from?*

**It comes from the clock, not the bag.**

| model | out-of-fold AUC |
|---|---|
| full 45 features | 0.6518 |
| **`ply_frac` ALONE (single feature, no fit)** | **0.6625** |
| phase only (`bag_n` + `ply_frac`) | 0.6460 |
| all 43 features with `bag_n`/`ply_frac` removed | 0.6519 |

A single number — *how late in the game you staked the farm* — **outperforms the
entire 45-feature bag-conditioned model**. Every one of the ten
strongest single features is a monotone function of how many tiles are left
(`bag_cls_CE2_FR2_CH0` 0.324, `bag_n` 0.336, `bag_ce0` 0.337, `bag_ge1` 0.342 …):
they are the same clock wearing different hats. The *composition* of the bag,
conditioned on the field — the funded mechanism — adds essentially nothing over
knowing the ply.

**And the bag says the dead farms were fine.** Among the champion's 92
zero-scoring deployments, **88.0 % had `proj_finished_cities > 0` at claim** — the
bag could still pay that field — against 98.1 % of its scoring ones. The
champion is not staking fields the bag has already condemned; it stakes live
fields and then loses them.

**The decisive contrast is the opponent, not the bag:**

| | champion farm zero-rate |
|---|---|
| vs **itself** (SP449 self-play, n=3 080) | **15.4 %** |
| vs **the owner** (E4, n=199) | **46.2 %** |

The champion's farm dead-capital rate **triples in the presence of one specific
opponent**, on the same leaf, the same search, the same claim policy. A
bag-reading defect would be present against both. This is opponent-induced loss
— consistent with the farm-steal mechanism Stage A already measured and with
**CL-083**'s reading that the owner's edge is position-steering and EV-based
victim selection over the remaining deck, not a per-move pricing gap the
champion could close by counting tiles at claim time.

---

## 5. What is and is not concluded

**Concluded.** A farmer deployment's final fate is **not** predictable from the
remaining-deck composition at claim time to the funded standard: the forecast
misses the 0.70 bar, dilutes on a 16×-larger corpus, is out-ranked by a single
phase feature, and prices the two seats' deployments **backwards**. The specific
story *"the champion's 46.2 % dead-farm rate is bag-blindness at claim time"* is
**refuted**. HP-M1 is dead.

**NOT concluded — forbidden readings.**
1. **NOT** "farms are not where the champion loses." The 46.2 % vs 5.4 % gap is
   real, replicated here, and untouched by this gate. Only the *bag-at-claim-time
   explanation* of it is killed.
2. **NOT** "the owner does not count tiles." This gate prices one specific use of
   bag counting — forecasting a field's fate at the moment of commitment. The
   owner's own account attaches counting to *later* decisions (whether to
   contest, when to surrender), which this instrument does not touch.
3. **NOT** a licence to re-run `bag_close`. Nothing here re-opens LEVER_INDEX
   row 202; it adds the new fact that `bag_close` is *inert on farm deployments*.
4. **NOT** a claim about post-claim interventions. The measured fact that
   88 % of dead farms looked payable at claim, and that the deficit is
   opponent-conditional, points at the **contest** phase, not the claim. Any such
   proposal needs its own mechanism argument and its own prereg (CL-079).
5. **No pooling.** Primary, SP449 and the non-`fixed_v1` E4 rows are never pooled
   into a quoted estimate (CL-068).

---

## 6. Limitations, stated rather than buried

* **n = 199** on the primary universe. Bar (a)'s CI includes the bar; bar (c)'s
  reversal does not depend on power.
* **`bag_minus_deck == 2` on 264/3 520 rows** (4.3 % of primary). An *unplaceable*
  drawn tile is discarded, so it sits neither on the board nor in the deck and
  the board-derived bag keeps counting it as remaining — a bias of ≤2 tiles in a
  bag of 40–70. **Disclosed, NOT corrected**: the bar statistics had already been
  read, and PREREG §9 forbids a post-read fix. It cannot plausibly produce a
  significant *sign reversal*, and it can only attenuate (a).
* **F-FIT is given the mechanism's best shot** (45 features, fitted). The
  deployable parameter-free form is *worse* (0.6480). A kill under the stronger
  form is the stronger kill.
* **The bar (c) model is trained on champion self-play**, a different rules epoch
  (`walled`) from the E4 rows (`fixed_v1`). That is the prereg's design — it is
  what makes the owner-row scores fully out-of-sample — but it is a cross-epoch
  application and is labelled as such. Its transfer AUC on E4 champion rows
  (0.675) shows the model does carry.

---

## 7. Artifacts

| file | what |
|---|---|
| [PREREG.md](PREREG.md) | the frozen contract |
| [RESULTS.json](RESULTS.json) | the adjudication of record (all three bars) |
| [POSTHOC.json](POSTHOC.json) | §4, explicitly post-hoc |
| [DEVIATIONS.md](DEVIATIONS.md) | both statistics-blind |
| [TILE_CLASSES.json](TILE_CLASSES.json) / [FEATURES.json](FEATURES.json) | the disclosed derivation + frozen feature order |
| `rows_*.jsonl` (+ `_games` / `_manifest`) | every row, every game's reconciliation, resolved env + leaf hashes |
| [fieldfate_census.py](fieldfate_census.py) · [fieldfate_gate.py](fieldfate_gate.py) · [posthoc.py](posthoc.py) · [run_gate.sh](run_gate.sh) | the instrument |
| `tests/test_hpm1_fieldfate.py` | 10 tests, all passing — incl. the two-pass agreement against the banked Stage-A kernel, the bag accounting gate, and the leaf-counterfactual state restore |
| [run.log](run.log) | the run |
