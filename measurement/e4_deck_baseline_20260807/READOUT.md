# E4 deck baseline — READOUT

**STATUS: RAN AND CLOSED 2026-08-08.** Spec pre-registered in [SPEC.md](SPEC.md) (`7b472fe`,
committed before any game ran). **No strength claim, no claim id, PRODUCTION.yaml untouched.**
Descriptive tooling on top of the E4 stream.

**Sign convention, everywhere: positive = seat 0 = Joshua ahead** (`scores[0] − scores[1]`).

Artifacts — every number below is a field of one of these:
`selfplay.jsonl` (96 games, one line each) · `analysis.json` (the computed estimates) ·
`driver.log` · `scripts/e4_deck_baseline.py` · `scripts/e4_deck_baseline_analyze.py` ·
`tests/test_e4_deck_baseline.py`.

---

## 0. The one-line answer

**The adjustment bought almost nothing, and it could not have bought much.** Joshua's
E4 margin reads **−0.17 ± 6.76** points adjusted, against **−0.17 ± 7.06** unadjusted —
a **4.2% se reduction** (realized variance ratio `estimates.var_ratio_beta_hat` = **0.918**).
The point estimate is **identical by construction** (the adjustment is centred), so nothing
about the "dead even at n=12" reading changes. Deck luck is real in these 12 games but it is
**small next to game-to-game noise**: the self-play deck-effect sd is **7.16** points against a
within-deck game sd of **21.49** (`deck_spread`), i.e. **ICC 0.100** — roughly *half* the
Phase-C figure the idea was funded on.

**What the run IS worth is the per-deck ledger in §3** — which of his twelve results were
deck-assisted and which were earned. That turned out to be the deliverable; the variance
reduction was not.

---

## 1. Run integrity

| check | value | field |
|---|---|---|
| games | **96** (12 decks × K=8), 0 failures, 0 resumes needed | `wc -l selfplay.jsonl` |
| decks | 12, **12 distinct `deck_hash`** (no deck collision, no deck repeated by accident) | `deck_hash` |
| deck reconstruction | proven by replay: the archived action sequence replays on the reconstructed deck to the phone's **recorded final scores** | `tests/test_e4_deck_baseline.py::test_deck_reconstruction_replays_archive_to_recorded_scores` |
| rules profile | `fixed_v1` on every game, `CARCASSONNE_FIX_R9=1` exported before import | `rules_profile`, `driver.log` line 1 |
| champion | `puct_priors_v29_bmild_cap8`, leaf **`a36d2e15a3b3d71d`** on all 96, `verify=True` | `champion_leaf_hash` |
| budget | **11008** = k_dets 8 × 1376 on all 96; no override | `total_sims_of_record`, `sims_override: null` |
| backend | **rust** on all 96, `rust_threads: 1` | `execution.backend` |
| cost | 1.226 s/move mean, 142.0 moves/game mean, 278.4 core-min, **21.2 min wall at W=14** | `secs_per_move`, `driver.log` |

Archive selection was by the archive's **own `rules_profile` stamp** — never
`(start_rule, grid_rule)`, which the Aug-2 build also writes. The 3 non-`fixed_v1` archives
(2 `walled` + the pre-`fixed_v1` 98–78 win) are excluded and a test asserts it.

**By-catch worth keeping:** across the 96 self-play games seat 0 goes **W42 / D1 / L53**
(wr 0.443) while the seat-0 **margin** mean is **+0.229 ± 2.303**. Under `fixed_v1` there is
no detectable seat-0 points advantage; if anything seat 1 wins slightly more *games* while
seat 0's wins are bigger. n=96, neither reading is past 2σ.

---

## 2. The three estimates

| estimate | β | point estimate | se | realized var ratio |
|---|---|---|---|---|
| unadjusted | — | -0.167 | **7.056** | 1.000 (reference) |
| β = 1 (naive) | 1.000 | -0.167 | 6.447 | 0.835 |
| β̂ (control variate) | +0.953 ± 0.677 | -0.167 | **6.760** | 0.918 |

- **HEADLINE (pre-registered rule = smaller se): `beta_hat`, se 6.760.** The adjustment
  helped, by 4.2% on the se / 8.2% on the variance.
- **corr(d̂, m) = +0.407** (R² 0.166), n = 12 — **t = 1.41 on 10 df, p ≈ 0.19.** The
  correlation is in the right direction and its *size* is a near-match for the Phase-C ICC
  0.19 that motivated the experiment, but at n=12 it is **not distinguishable from zero**.
- **β̂ = 0.953 ± 0.677.** Consistent with 1 (the value theory expects if deck value transfers
  one-for-one from champion to human) *and* consistent with 0 (z = 1.41). It settles nothing.

### Three honest notes the numbers force

1. **All three point estimates are the same number, −0.167, and always would be.** The
   centred form `m_i − β(d̂_i − d̄)` has a mean of `mean(m)` for *any* β, because the centred
   term sums to zero. This was written into the SPEC before results existed. The control
   variate buys **precision only** — it cannot move the "dead even" verdict, only sharpen it.
2. **β=1 actually beat β̂ here (se 6.447 vs 6.760), and the spec forbids promoting it.**
   That ordering is not a paradox: β̂ came out at 0.953, i.e. essentially 1, so the estimated
   β bought nothing over the fixed one while its se pays the pre-registered `ddof=2` penalty
   for having been estimated. Reporting β=1 as the headline *after* seeing it win would be
   selecting on the outcome — exactly what the pre-registration exists to stop. It is
   reported and it is not the headline.
3. **The baseline is nearly as noisy as the effect it is estimating.** The mean per-deck se
   is ~7.3 points (`per_deck[].deck_value_se`, range 2.60–11.27) against an estimated true
   deck-effect sd of 7.16. That is the exact regime the SPEC warned about — and it is *why*
   the reduction is 4% rather than the ~19% a perfectly-known deck value would have given.

---

## 3. The per-deck ledger — which games were uphill

| deck_seed | archive | d̂ (deck value) ± se | K | self-play margins | Joshua's margin | terrain |
|---|---|---|---|---|---|---|
| `1382293676` | `1786243458_1382293676.json` | **-11.75** ± 8.75 | 8 | -51, -42, -12, -9, -8, -6, +9, +25 | **+22** | uphill |
| `338139` | `1786045035_338139.json` | **-11.50** ± 2.60 | 8 | -23, -18, -17, -10, -9, -8, -7, +0 | **-10** | uphill |
| `134510` | `1786116818_134510.json` | **-9.75** ± 9.14 | 8 | -32, -28, -26, -22, -18, -6, +9, +45 | **-28** | uphill |
| `705585` | `1785982194_705585.json` | **-8.50** ± 6.61 | 8 | -32, -14, -13, -13, -12, -10, -8, +34 | **-7** | uphill |
| `935815` | `1786074812_935815.json` | **-2.38** ± 9.03 | 8 | -36, -34, -14, -8, +7, +11, +17, +38 | **-14** | uphill |
| `2116173857` | `1786076853_2116173857.json` | **-0.25** ± 6.68 | 8 | -33, -14, -7, -4, -1, +13, +20, +24 | **+3** | uphill |
| `703591` | `1786142936_703591.json` | **-0.25** ± 6.22 | 8 | -26, -23, -8, +2, +5, +11, +13, +24 | **-38** | uphill |
| `627623` | `1786113542_627623.json` | **+0.88** ± 5.83 | 8 | -21, -20, -7, -2, +6, +9, +18, +24 | **+38** | downhill |
| `1698417952` | `1785984310_1698417952.json` | **+3.25** ± 6.05 | 8 | -21, -14, -10, +5, +6, +11, +22, +27 | **-6** | downhill |
| `49628` | `1786242001_49628.json` | **+5.25** ± 7.95 | 8 | -20, -16, -5, -2, +2, +13, +20, +50 | **-9** | downhill |
| `1621601234` | `1786118143_1621601234.json` | **+17.50** ± 11.27 | 8 | -24, -20, -11, +19, +36, +38, +42, +60 | **+3** | downhill |
| `1911511187` | `1785986044_1911511187.json` | **+20.25** ± 7.51 | 8 | -3, +1, +6, +10, +24, +26, +38, +60 | **+44** | downhill |

**His twelve decks were collectively neutral: mean(d̂) = +0.23.** He did not get a bad draw
overall; the "dead even" read is not a deck-luck artifact in either direction.

### Residual `m − d̂` — the ranked story

| deck | d̂ | his margin | residual | reading |
|---|---:|---:|---:|---|
| `703591` | −0.25 | **−38** | **−37.75** | **his worst game, and the deck was neutral.** The −38 loss is not deck luck. |
| `134510` | −9.75 | −28 | −18.25 | a bad deck made worse |
| `1621601234` | +17.50 | **+3** | **−14.50** | ⚠️ the 74–71 **win** is the one result the deck *carried* — on this deck the champion averages +17.5 against itself and he took only +3 |
| `49628` | +5.25 | −9 | −14.25 | the farms-39–0 loss came on a *favourable* deck |
| `935815` | −2.38 | −14 | −11.62 | |
| `1698417952` | +3.25 | −6 | −9.25 | the contested-farm 101–107 game: mildly favourable deck, small underperformance |
| `338139` | −11.50 | −10 | +1.50 | **an uphill deck he essentially broke even on** |
| `705585` | −8.50 | −7 | +1.50 | same: par on a bad deck |
| `2116173857` | −0.25 | +3 | +3.25 | |
| `1911511187` | **+20.25** | **+44** | +23.75 | the 109–65 blowout came on **the single most seat-0-favourable deck of the twelve** — roughly *half* that +44 is the deck |
| `1382293676` | **−11.75** | **+22** | **+33.75** | ⚠️ **the 97–75 win is arguably his best game of the twelve**: he won by 22 on a deck the champion loses by ~12 on |
| `627623` | +0.88 | **+38** | **+37.12** | **the 116–78 blowout was earned** — neutral deck, biggest residual in the set |

**Two results change character once the deck is priced in.** The 74–71 win (`1621601234`)
looks like a nail-biter and reads as an *underperformance* on a strongly favourable deck; the
97–75 win (`1382293676`) looks routine and is his largest overperformance after the 116–78.
The two headline blowouts split: **116–78 was his** (neutral deck), **109–65 was ~half the
deck** (+20.25).

⚠️ **Do not over-read individual rows.** `1382293676` (±8.75) and `1621601234` (±11.27) are
the two least-certain deck values in the table, and they are two of the three rows the story
above leans on. `338139` (±2.60) is the only deck value that is sharp.

---

## 4. Do his decks differ at all?

Yes — **barely, and only marginally past noise.**

- observed spread of deck means: **sd(d̂) = 10.44**
- within-deck (replicate) sd: **21.49**
- estimated *true* deck-effect sd after removing baseline sampling noise: **7.16**
- **self-play ICC = 0.100**
- one-way ANOVA over the 12 decks: **F(11, 84) = 1.887, p = 0.053**

So the deck component exists (p ≈ 0.05) and is worth **~7 points of sd** — real, but a
third of the ~21.5-point sd of a single game on a *fixed* deck. The champion's own play
against itself varies enormously on the same deck: `1382293676` ranges **−51 to +25** across
its 8 replicates.

⚠️ **This ICC (0.100) is about half the Phase-C figure (0.19) the idea was funded on.** Both
are estimates with real uncertainty and they are not flatly inconsistent, but the honest
reading is that **this instrument prices deck luck lower than Phase C did**, which is the
proximate reason the control variate returned 4% instead of ~19%.

---

## 5. Verdict — what this bought

**It bought a 4.2% tighter error bar and a per-game uphill/downhill ledger. It did not, and
structurally could not, move the point estimate.** Joshua's fixed_v1 E4 record at n=12 is
**−0.17 ± 6.76 points** (was ±7.06). Every conclusion the E4 stream already carried survives
unchanged.

**Was the method sound? Yes. Was it worth it at this n? Barely — as a variance reducer.**
The honest summary is the one the SPEC pre-committed to: *the correlation is +0.41 but
indistinguishable from zero at n=12, the deck effect is ICC 0.10 not 0.19, and the adjustment
therefore bought a few percent.* If the correlation had come back at ~0 the readout would say
it bought nothing; it came back small-but-positive, and it bought a little.

**The reusable asset is the tooling, not this readout's se.** `scripts/e4_deck_baseline.py`
prices any E4 deck for 8 champion self-play games in ~2 min of wall clock at W=14, and the
per-deck ledger is now available for every future E4 game at negligible cost. The value of
the control variate grows with n (the β̂ noise shrinks), so re-running this at n=25–30 is
cheap and strictly better-powered.

**2026-08-09 addendum (informal, not folded into the n=12 estimates above):** deck `523563`
(the two 2026-08-09 games, `1786325073`/`1786329790`, margins +56/+29) priced at K=8/11008,
3.3 min wall at W=14 — self-play margins +21,+11,+2,−2,−16,−20,+15,−7, **d̂ = +0.50 ± 5.17**
(near-neutral). Residuals: **+55.5** (new record, beats `627623`'s +37.12) and **+28.5**. Full
detail: `measurement/e4_games/README.md` § "Deck-adjusted residual for the two 523563 games".

---

## 6. Caveats owed (all pre-registered in SPEC §"Caveats owed")

1. **n = 12.** Every estimate here is a 12-point regression. β̂ = 0.953 ± 0.677 and
   corr = +0.407 (p ≈ 0.19) are both uninformative on their own.
2. **"Deck value" is defined by the CHAMPION's self-play margin distribution.** A deck worth
   +20 to the champion in seat 0 need not be worth +20 to Joshua — the two exploit different
   deck shapes, and the champion's farm behaviour against Joshua is already known to differ
   from its behaviour in its own corpus (E4 README, farm ledger). The control variate stays
   valid as a *variance reducer* under any correlation; its *interpretation* as "deck luck
   removed" is only as good as that transfer, which this experiment cannot check.
3. **The human is non-stationary and assisted.** Joshua improved across these 12 games and
   some carried UI assists. The adjustment addresses neither confound and the residuals in §3
   are therefore *not* a clean skill ranking of his games — an early game and a late game are
   not the same player.
4. **The baseline carries its own noise** (mean se ~7.3 pts, comparable to the 7.16-pt deck
   effect), which is the mechanism that caps the achievable variance reduction well below the
   ICC's nominal ceiling.
5. **The champion is not an optimal player**, so d̂ is "value to this agent at 11008 sims",
   not "value to perfect play".
6. **Seat is fixed.** Every self-play replicate and every one of Joshua's games has him in
   seat 0. This experiment removes *deck* variance, not seat variance; the Phase-C protocol
   (seat-swap deck pairs, 193 games at wr 0.55) remains what an actual rating needs.
