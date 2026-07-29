# THE CLIFF LADDER — 688 / 1376 / 2752 deck-matched on shared band 88e9

**STATUS: COMPLETE (2026-07-29). All three rungs ran to full n=400 deck-paired on the SAME 200
decks against the SAME opponent. 0 solver timeouts and 400/400 endgame latches on every side of
every cell. `results.csv` rows: `cliff688_k4x172_vs_deploy_n400_b88e9`,
`cliff1376_k4x344_vs_deploy_n400_b88e9`,
`cliff2752_k4x688_IDENTITY_CONTROL_vs_deploy_n400_b88e9`.**

**VERDICT 1 — G2's loose end is ANSWERED, and the answer is MONOTONE. Within one band, deck-matched,
the low end orders 688 ≪ 1376 ≈ 2752: `1376 − 688 = +5.030 pts/deck, deck-paired z +4.85`, and
`1376 − (identity zero) = −1.475 pts/deck, z −1.23`. Shape = STEEP RISE 688→1376, then FLAT by 2752.
The cross-band "1376 below 688" inversion that CL-068 recorded as unresolved was an artifact — there
is no inversion.**

**VERDICT 2 — the identity control prices the noise floor, and it EXONERATES THE HARNESS. A cell
whose true value is EXACTLY 0 by construction reads +25.2 ± 17.4 elo (wr z +1.45) and +1.2325
pts/deck (margin z +1.44), with seat-arm asymmetry +0.885 ± 1.926 (z +0.46). No harness asymmetry
beyond noise. ⇒ the 3σ cross-band contradiction on the 1376 cell is NOT a broken harness; the
economical reading is BAND-LEVEL OVER-DISPERSION of ~1.8–2.2×, present in BOTH house statistics.**

**NOTHING IS PROMOTED. `governance/PRODUCTION.yaml` untouched. `k4×344` remains NOT
proposal-eligible — see §5, where the reason changes from "proven costly" to "too dispersed to
certify safe", which is a stronger bar, not a weaker one.**

Ladder run by the experiment-runner session `c0b61ee1`. Rung 688 on the Apple M5 Air
(`darwin-arm64`, W10); rungs 1376 and 2752 on `laptop-wsl` (x86-64, W16). Frame for rung 688 and the
M5 platform verification: [M5_CAMPAIGN_READOUT_20260729.md](M5_CAMPAIGN_READOUT_20260729.md).

---

## 1. What was owed

[docs/PROGRAM_ROADMAP_2026-07-07.md](../../docs/PROGRAM_ROADMAP_2026-07-07.md) Track **G2**,
`governance/CLAIM_REGISTRY.csv` **CL-068** (counterevidence field), and
[G2_CONFIRM_READOUT_20260728.md](G2_CONFIRM_READOUT_20260728.md) all carry the same open item:

> **LOOSE END, unresolved:** this puts 1376 (−53.4, b76e9) BELOW 688 (−37.5, b62e9), difference
> −15.9 ± 24.7 = z −0.64 cross-band, so the low end's ORDERING is unmeasured; shaping the cliff
> needs 688/1376/2752 deck-matched on one shared fresh band.

**This ladder is that experiment.** One band (88e9), one opponent, one deck set, three budgets.

> ⚠️ **Precision correction to the loose end as it was written.** The −37.5 it quotes is
> `pareto_k2x344_688_vs_deploy` — the **k2×344** allocation. The ladder's 688 rung is **k4×172**,
> whose like-for-like prior reading is `pareto_k4x172_688_vs_deploy` = **−46.3 ± 17.5 on band
> 62e9**. Both are cross-band and both are now superseded for ordering purposes by the within-band
> ladder below.

---

## 2. Design — one band, one opponent, one deck set

All three cells: `eval_fair_puct.py --info fair --opponent fair-champion --exact-k 2 --paired
--shared-claim --no-results-csv`, `--seed-start 88000000000`, `n=400` (200 decks × 2 seats),
`c_puct 1.5 · tau_p 5 · leaf-quantize float · final-select visits · value-norm 15`.

**The manifests were diffed field-by-field across all three cells. They differ in EXACTLY four keys:
`config/champion/sims_per_det`, `config/champion/total_sims`, `host`, `code_rev`/`utc`.** Everything
else is identical, including:

| shared invariant | value |
|---|---|
| `config/seed_start` | `88000000000` (all three) |
| `config/paired` | `true` (all three) |
| deck seed sets | **verified identical set-for-set, 200 decks, all three cells** |
| candidate leaf hash | `a36d2e15a3b3d71d` |
| opponent leaf hash | `a36d2e15a3b3d71d` (`both_sides_curve125: true`) |
| curve125 provenance hash | `6dfffd57051690f2` (expected == actual, all three) |
| endgame, both sides | `exact_k=2`, `exact_budget=2000000` |
| leaf env | `V25_CAP=8 V25_OPP_CAP=8 V25_DROP_THREE_OPEN=0 V25_MEEPLE_K=2.0 V25_VALUE_BLEND=0` |

**The opponent is the PRE-PROMOTION deploy champion `k4×688` = 2752, by design.** The ladder was
designed and launched before the `54b31ac` promotion of the champion to `k8×1376`; all three rungs
share the same opponent, which is what makes the ladder internally valid. Rows label it
`..._PRODUCTION_pre54b31ac`. **These elos are distances from the OLD champion and must not be
compared to anything graded against the new one.**

---

## 3. The three rungs (every figure re-derived from the per-game records, not copied from summaries)

| | **688** | **1376** | **2752 = IDENTITY CONTROL** |
|---|---:|---:|---:|
| allocation | k4×172 | k4×344 | k4×688 |
| × deploy budget | 0.25× | 0.50× | **1.00× (identical to opponent)** |
| W / D / L | 150 / 6 / 244 | 206 / 12 / 182 | 211 / 7 / 182 |
| winrate | 0.38250 | 0.53000 | 0.53625 |
| winrate z | **−4.70** | +1.20 | +1.45 |
| elo | **−83.20** | +20.87 | +25.23 |
| σ (elo, 1σ) | ± 17.4 | ± 17.4 | ± 17.4 |
| **deck-paired margin** (pts/deck) | **−5.2725** | **−0.2425** | **+1.2325** |
| **margin z** | **−7.22** | **−0.29** | **+1.44** |
| σ_margin (per-deck SEM) | 0.7298 | 0.8356 | 0.8560 |
| candidate ms/move | 918 | 1832 | 3655 |
| opponent ms/move | 3693 | 3638 | 3613 |
| **cost ratio** | **0.249×** | **0.503×** | **1.012×** |
| solver s/game (cand) | 20.67 | 15.69 | 15.50 |
| timeouts, both sides | 0 | 0 | 0 |
| endgame latched, both sides | 400/400 | 400/400 | 400/400 |
| platform | **darwin-arm64** (M5 Air) | x86-64 `laptop-wsl` | x86-64 `laptop-wsl` |
| workers | **W10** | W16 | W16 |
| wall-clock | 4.11 h | 2.95 h | 3.83 h |
| `code_rev` (manifest) | `3d7ce4f` ⚠️ | `c6f0f9676-dirty` | `c6f0f9676-dirty` |

**Verification performed for this read-out** (not inherited from the summaries):

- W/D/L, winrate, elo recomputed from the 400 per-game records of each cell — **all three match
  their `summary.json` exactly**.
- σ_margin derived two independent ways — `|margin / paired_z|` from the summary, and the per-deck
  SEM recomputed from the records — **agree to 4 decimal places in all three cells**.
- The `diff` field's sign convention was read off the emitter (`eval_fair_puct.py:1551`,
  `diff = (s0-s1) if a_seat==0 else (s1-s0)`) **before** parsing: `diff` is already stored
  candidate-minus-opponent, so it must NOT be seat-flipped again. A first pass that flipped it
  produced +0.88 instead of −5.2725 on the 688 cell; the emitter settled it.
- **Cost ratios independently confirm each cell ran its claimed budget:** 0.249× / 0.503× / 1.012×
  against nominal 0.25× / 0.50× / 1.00×.
- Exchange rate implied by three independent cells is stable at **≈16 elo per pt/deck**
  (cliff688 15.8 · g2confirm 16.3 · CL-060 16.7) — a sanity check that the two house statistics are
  measuring the same thing at these effect sizes.

⚠️ **`code_rev` nit on the 688 rung.** Its manifest records `3d7ce4f`, which **does not resolve in
this repo's history** — the M5 has a separate rsync'd tree (no share mount; memory
`reference_m5_access`). The landed row cites `cc73b3c`, the local rev at launch. Load-bearing check
in place of the rev: the cell's leaf hashes and curve125 provenance hash are **byte-identical to the
other two cells**, and both sides of the cell share the code, so any drift is common-mode within
that cell.

---

## 4. Within-band, deck-matched — the ladder question

Same 200 decks, same opponent, same seat balancing, so these contrasts are the honest read. Both
forms are reported: treating the cells as independent, and truly deck-paired on the shared decks.

| contrast | Δ margin (pts/deck) | independent-cells z | **deck-paired z** |
|---|---:|---:|---:|
| **1376 − 688** | **+5.030** | +4.53 | **+4.85** |
| **1376 − 2752** (identity zero) | **−1.475** | −1.23 | **−1.23** |
| 688 − 2752 (identity zero) | −6.505 | −5.78 | −5.73 |

**⇒ STEEP RISE 688→1376 (z +4.85), then FLAT by 2752 (z −1.23).** 1376 sits within ~1.2σ of the
deploy budget on this band. **This reproduces CL-068's flat-then-cliff shape on ONE band,
deck-matched, for the low end — and it establishes the low end's ORDERING as monotone with no
inversion.** G2's loose end is discharged.

> **Note on the pairing:** deck-pairing across *cells* buys almost nothing here (the two z-forms
> agree to ~0.05, and for the 1376-vs-2752 contrast the paired sd is slightly *larger* than the
> independent form implies). That is expected: two different budgets diverge from the first move, so
> sharing a deck does not induce much correlation in the final margin. The deck-pairing that *does*
> pay is the within-cell seat-balanced pairing already baked into every `margin z`.

⚠️ **PLATFORM CONFOUND, travels with the 688-vs-1376 contrast.** Rung 688 ran `darwin-arm64` at
W10; rungs 1376 and 2752 ran x86-64 at W16. Both sides of *each* cell share their platform, so every
cell is internally sound, but the +5.030 contrast is not platform-clean. The harness itself documents
that float reduction order can differ across boxes and flip a near-tied argmax — so the mechanism for
a platform effect exists. At z +4.85 platform is an implausible *full* explanation, but it is not
zero, and a platform-clean re-run of 688 on x86-64 is the cheap way to close it if anyone ever needs
the contrast to be exact rather than directional.

---

## 5. The identity control, and what it does to the cross-band contradiction

### 5.1 What the control is

The 2752 rung's candidate configuration is **identical to its opponent**: same `k_dets=4 ×
sims_per_det=688`, same curve125 leaf hash on both sides, same `exact_k`/`exact_budget`, same box,
same decks. **Its true value is therefore EXACTLY 0 by construction.** Whatever it reads IS the
harness-plus-deck noise floor on band 88e9.

It reads **+25.23 ± 17.42 elo (wr z +1.45, two-sided p 0.147)** and **+1.2325 pts/deck (margin z
+1.44, p 0.150)**.

### 5.2 What it rules out

| check | result | reading |
|---|---|---|
| both statistics on a true-zero cell | +1.45 and +1.44 | consistent with zero; **no gross σ error within a band** |
| **seat-arm asymmetry** (a_seat0 mean − a_seat1 mean; true value 0) | **+0.885 ± 1.926, z +0.46** | **no seat/colour asymmetry** |
| candidate wins by seat | 111/200 and 100/200 | balanced |
| cost ratio | **1.012×** | the two sides really did run the same budget |
| the two statistics' signs | **agree** (both +) | the 1376 cell's sign *disagreement* is itself a noise artifact, not a systematic |

A broken seat, colour, latch, or scoring asymmetry would surface **here** first, in a cell where
every other difference has been removed. None does.

⚠️ One asymmetry worth recording as harmless: the two sides' *solver seconds per game* differ
(candidate 15.50 s vs opponent 17.69 s, ~14%) despite identical configurations. The exact endgame
solver is deterministic given the position and both sides latched 400/400, so the **moves** are
unaffected — this is timing contention, and it is a reminder that per-side *timing* fields carry
scheduling noise even when the *game* fields cannot.

### 5.3 Therefore: band-level over-dispersion

The `cliff1376` row flagged a **3σ cross-band contradiction**: the same `k4×344` config reads
**−53.4 ± 17.6 on b76e9** (`pareto_k4x344_1376_vs_deploy_CONFIRM`) and **+20.9 ± 17.4 on b88e9**
(this ladder) — a difference of **+74.3 ± 24.7, z +3.00**, same box, same W, config replicated.

**The identity control removes "the harness is broken" from the list of explanations.** What remains
is that the nominal σ under-covers *across* bands. Three measurements of the *same* 1376
configuration:

| band | cell | elo | margin (pts/deck) |
|---|---|---:|---:|
| 60e9 | `pareto_k4x344_1376_vs_deploy` | +0.9 ± 17.4 | −1.032 (z −1.26) |
| 76e9 | `pareto_k4x344_1376_vs_deploy_CONFIRM` | −53.4 ± 17.6 | −3.285 (z −3.54) |
| 88e9 | `cliff1376_k4x344_vs_deploy_n400_b88e9` | +20.9 ± 17.4 | −0.2425 (z −0.29) |

| statistic | sample sd across the 3 bands | mean nominal per-cell σ | **over-dispersion** |
|---|---:|---:|---:|
| elo | 38.45 | 17.5 | **2.20×** |
| deck-paired margin | 1.579 | 0.861 | **1.83×** |

**The over-dispersion appears in BOTH house statistics at a similar magnitude, so it is not an
artifact of the winrate→elo transform.** Pairwise: b60 vs b76 `z −2.19` · b60 vs b88 `z +0.81` ·
b76 vs b88 `z +3.00`. The same signature, weaker, shows on the 688-total `k4×172` config across its
two bands: −46.3 (b62e9) vs −83.2 (b88e9) = **−36.9 ± 25.0, z −1.47**.

> ⚠️ **The obvious explanation does NOT work, and nobody should reach for it.** "Different bands mean
> different decks" is already priced: the per-deck SEM *is* computed from the observed per-deck
> spread, so the deck-draw component is inside the nominal σ, not outside it. A cross-band difference
> of the same config should have σ ≈ √2 × 0.86 ≈ 1.2 pts/deck, and the observed spread is ~1.6.
> **The excess is real and unexplained.** That is precisely why it needs its own systematic look
> rather than a one-line dismissal.

### 5.4 Candidate mechanisms — ENUMERATED, NOT ADJUDICATED

This read-out does not have the evidence to pick among these, and deliberately does not try.

1. **Heavy-tailed per-deck margins.** Per-deck margin sd is ~12 pts on a bounded score scale. If the
   per-deck distribution is heavy-tailed or the 200-deck mean is skewed, the normal-theory SEM
   under-covers. *Cheapest test:* bootstrap per-deck margins within a single cell and compare the
   bootstrap interval to the normal SEM; compare kurtosis across cells.
2. **Code-era drift with an asymmetric-budget interaction.** The three 1376 cells ran at `0bfdc00` /
   `4e67f2b` / `c6f0f96`. Drift is usually waved off as common-mode because both sides share the
   code — but these cells are **budget-asymmetric** (candidate 1376 vs opponent 2752), so a change
   that interacts with budget does *not* cancel. *Cheapest test:* replay a fixed root set at two
   revs and diff the picks.
3. **Box / platform float-reduction differences.** b60e9 ran local+laptop, b76e9 and b88e9
   laptop-only. Reduction order can flip near-tied argmaxes. *Cheapest test:* the same band on two
   boxes.
4. **Latch-depth / solver interaction with deck composition.** The endgame latch is
   budget-independent *once latched*, but the prefix length before latching depends on the search, so
   deck composition could shift the effective prefix budget. *Cheapest test:* compare
   `champ_prefix_moves` / `champ_exact_moves` distributions across bands.
5. **Opponent-era drift.** A harness that resolves the champion from `PRODUCTION.yaml` at import
   time would silently change opponent across eras. *This ladder is clean on this axis* (opponent
   budget is asserted in every manifest), but older cells in the family should be checked.

### 5.5 Practice going forward (the actionable part)

- **Inflate σ by ~1.5–2× on ANY cross-band comparison in this family.** A cross-band `z` of 3.0
  becomes ~1.5–2.0 — suggestive, not decisive.
- **Prefer within-band deck-matched contrasts.** That is what this ladder is, and it is why its
  +4.85 and −1.23 are trustworthy while the +3.00 cross-band z is not.
- **Do not pool across bands and quote the result as an estimate.** For the record, under empirical
  inflation the three 1376 cells pool to **−10.5 ± 22.2, 95% CI [−54, +33]** — a *width*, cited here
  only to show how little three n=400 cells constrain this cell, not as an estimate.

### 5.6 ⚠️ What this does NOT touch — CL-060 / the promotion

**The promotion's evidence is the robust kind and is untouched by this finding.**
`cl060_h2h_k8x1376_vs_deploy_k4x688` is a **within-band, deck-paired** contrast: +49.85 elo with
**paired z 3.48** on a single band (32e9), n=400 paired, W221/D15/L164. That is exactly the class of
measurement §5.5 endorses, and the identity control shows there is no within-band harness pathology
to discount it with. **Nothing here reopens or weakens CL-071 / the k8×1376 promotion.**

Similarly, the running **G7** probe motivates itself partly on "the cliff rows' 3σ cross-band
contradiction makes head-to-heads suspect". This read-out **refines** that: the suspicion applies to
**cross-band** head-to-heads. Within-band deck-paired head-to-heads pass the identity control.

### 5.7 And what it means for `k4×344` specifically

CL-068's amendment REFUTED "halving the deploy budget is free" on the strength of the b76e9 confirm
(−53.4, both statistics past 3σ). **On b88e9, deck-matched against the identity zero, 1376 is FLAT
(−1.475 pts/deck, z −1.23).** The two bands disagree, and that disagreement *is* the over-dispersion
finding — so the flat region's lower edge is **band-dependent and NOT settled**.

**This does NOT rehabilitate `k4×344`, and the conclusion moves in the conservative direction:**

- Three bands read +0.9 / −53.4 / +20.9. Under empirical inflation that pools to −10.5 ± 22.2.
- Pre-registered rule 6 requires a candidate to cost **< ~1σ** to be proposal-eligible. A 95%
  interval of **[−54, +33]** does not clear a ±17.5 tolerance — it is **~2× too wide to certify the
  lever safe**.
- ⇒ **`k4×344` stays NOT proposal-eligible.** The *reason* upgrades from "proven costly on one band"
  to "**not certifiable as safe on any band, because the measurement of it is over-dispersed**".
  That is a stronger bar. **Do not propose it.** The deploy budget is unaffected by this line either
  way — the champion of record is now `k8×1376` (CL-071), well above every rung on this ladder.

---

## 6. Costs

| rung | box | W | wall-clock | Σ per-game CPU | candidate ms/move |
|---|---|---:|---:|---:|---:|
| 688 | M5 Air (`darwin-arm64`) | 10 | 4.11 h | 40.7 h | 918 |
| 1376 | `laptop-wsl` (x86-64) | 16 | 2.95 h | 45.8 h | 1832 |
| 2752 | `laptop-wsl` (x86-64) | 16 | 3.83 h | 60.2 h | 3655 |
| **total** | | | **~10.9 h** (2 boxes, partly serial) | 146.7 h | |

Band **88e9 is now burned** for this family. Rung logs live on their boxes:
`measurement/classical_search/cliff_1376_laptop-wsl.log` and `cliff_2752_laptop-wsl.log` on the
laptop (`rc=0`, watchdogs armed); the 688 rung's log is on the M5.

---

## 7. Six-touch close-out

| touch | state |
|---|---|
| 1. `results.csv` row | ✅ `cliff2752_k4x688_IDENTITY_CONTROL_vs_deploy_n400_b88e9` (688 and 1376 landed earlier) |
| 2. `DECISIONS.md` entry | ✅ 2026-07-29 (evening) — ladder verdict + over-dispersion finding |
| 3. status banner on this doc | ✅ header above |
| 4. governance row flip | ✅ `CLAIM_REGISTRY.csv` CL-068 amended (2026-07-29) |
| 5. `STATUS.md` top block | ✅ cliff-running line replaced with the verdict |
| 6. roadmap line | ✅ G2 loose end flipped to ANSWERED |
| + `docs/INDEX.md` row | ✅ |
| + `doc_lint.py` | ✅ 0 errors |
