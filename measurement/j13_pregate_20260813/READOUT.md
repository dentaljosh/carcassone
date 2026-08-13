# J13 / J5 pre-gate — does "build up an unclaimed feature you'll claim later" pay?

> **⚠️ STATUS 2026-08-13 — COMPLETE. DESCRIPTIVE INSTRUMENT, 0 GAMES PLAYED.**
> No `experiments/results.csv` row, no band claim, no claim id — house precedent:
> farm-war, adaptive-k census, item-1 farm-norm replay. Nothing here promotes,
> retires, or prices anything. The verdict on the *lever* is
> **DISCOURAGING BUT NOT A KILL**, and the specific hypothesis that motivated it
> is **REFUTED IN SIGN**. Machine-readable numbers: [VERDICT.json](VERDICT.json).
> Instrument: [`scripts/analyzer/j13_pregate.py`](../../scripts/analyzer/j13_pregate.py) ·
> tests: [`tests/test_j13_pregate.py`](../../tests/test_j13_pregate.py) (39, green).

## What was asked

Joshua, 2026-08-12: *"what about something else for unclaimed features. if you
suspect you have a high chance of claiming later, even if you can't now. makes
sense to build it up."* — the **J13** lever
([LEVER_INDEX](../../docs/LEVER_INDEX.md), row minted 2026-08-12): price unclaimed
features at `V(feature) × (P_self(claim) − P_opp(claim))`, with the defensive
side (**J5**, don't feed what the opponent will capture) as the same signed
weight. The premise is verified and unusual: **the production leaf prices
ownerless structures at exactly ZERO for everyone**, because the incomplete-feature
credit is owner-gated. It is a genuinely empty slot.

This document is the **pre-gate**, not the term. It asks of the 26 banked
human-vs-champion games: does that pattern happen, does it pay, and do the two
seats differ in it?

## What it cannot tell you — read this before quoting a number

1. **No causation.** "He built it up and later claimed it" is outcome-conditioned
   selection. The only defensible reading is a **rate comparison between the two
   seats on the same boards** — they share every deck, every board, every game
   length, so a within-game paired contrast cancels the nuisance variance — plus
   base rates that **bound** how much value the term could reach.
2. **One human, 26 games, 3 rules epochs.** The headline is the `fixed_v1` epoch
   (n=23). The `walled` epoch (n=2) has the human's net points-per-buildup-touch
   at −0.082 against `fixed_v1`'s +0.015: **the sign disagrees, so the epochs are
   never pooled** (farm-war rule). Pooled-all-epoch figures appear in VERDICT.json
   for completeness and are not the finding.
3. **The anchor is nonstationary.** The human self-reports changing strategy
   (memory `reference_android_app`); a rate averaged over 23 games is an average
   over a moving player.
4. **A buildup touch is classified by the CONTEMPORANEOUS component's claim state;
   its fate is the FINAL merged feature.** A field built ownerless for 20 turns
   that later merges into an already-claimed field is scored under the merged
   fate. That is the honest decision-time-investment / terminal-outcome pairing,
   and it is exactly the non-stationarity the term itself would have to price.

## Integrity

| check | result |
|---|---|
| archives | 26 (`walled` 2, `app_aug2` 1, `fixed_v1` 23) |
| rules profile | resolved **from each archive** via `ev_loss.resolve_profile_name`, never assumed; R9 is import-latched so each profile ran in its own subprocess |
| replay reproduces the recorded final scores | **26 / 26 bit-exact** |
| per-feature attribution reconciles to the final score | **26 / 26 exactly** — every point paid in every game is traced to one persistent feature (during-play completion award cross-checked against the engine's own score delta at each scoring pass) |
| features traced | 2,190 (≈84/game) |
| cost | ~0.25 s/game, 3 subprocesses, whole corpus < 10 s |

## Definitions (the instrument owns them)

* **Feature** — a persistent union-find class over *slots* (`(r,c,Side)` for
  cities/roads/fields, the tile for cloisters). Components only grow or merge,
  never split, so unioning every component of every intermediate board yields
  exactly the terminal components. That class is the identity traced forward.
* **Touch** — one `(turn, actor, component)` pair: the tile just placed
  contributed ≥1 slot to that component. One tile can touch several components,
  so touches > plies.
* **Owners at decision time** — meeples on that component *after the tile ply,
  before the actor's own meeple ply*: the view the placing player actually had.
* Every touch is exactly one of **buildup** (ownerless and left ownerless — the
  J13 quantity) · **claim_now** (ownerless, claimed the same turn — already priced
  by the leaf) · **own_growth** · **feed_claimed** (opponent already owned it —
  the blunt J5 quantity) · **contested**.
* **Shared credit** — `credit_p(F) = points_to_p(F) × buildup_p(F) / n_tiles(F)`.
  A split rule is mandatory or a 7-tile city is counted 7 times; this one
  conserves total points and never exceeds them.

---

## 1. Base rates — how much room is there at all?

`fixed_v1`, n=23, 1,958 features.

| | city | road | cloister | farm | all |
|---|---:|---:|---:|---:|---:|
| features traced | 415 | 603 | 322 | 618 | 1,958 |
| **never claimed by anyone** | 157 (37.8%) | 403 (66.8%) | 257 (79.8%) | 551 (89.2%) | **1,368 (69.9%)** |

* **Only 30.1% of features are ever claimed by anyone.**
* Among the features that *are* claimed, tiles laid before the first claim:
  mean 2.0, median 1, **24.9% claimed on the very tile that created them**,
  36.8% with ≥2 tiles laid first, p90 = 4. So a build-then-claim window does
  exist — in roughly a third of claimed features.
* **29% of every point paid (1,276.8 of 4,413) traces pro-rata to tiles laid
  while the feature was ownerless.** That is the accounting headroom, and it is
  large.
* 2,917 points of terminal value sit on never-claimed features. **This is not
  recoverable value** — an ownerless feature pays zero to everyone by rule. The
  leaf's zero is *correct*; the term's only claim is on the **option** value.
* Buildup is nearly the whole game: buildup-ply share 0.961 (human) / 0.944
  (champion), structural-only 0.856 / 0.785. The base is huge and mostly worthless.

**Two structural carve-outs that shrink the addressable slice:**

* **Cloisters: the offensive term is inapplicable by the rules.** A meeple only
  goes on the tile you just played, so a cloister nobody claimed on its own turn
  is **ownerless forever**. Measured: cloister buildup touches are 100% fate
  `none` for both seats, in every game. That is **24.2%** of the human's buildup
  touches (20.5% of the champion's) where zero is already the right price.
* **Farms are 41.6% / 44.0%** of buildup touches, already carry dedicated leaf
  terms, and run 18–19% `both` (contested fields).

⇒ the genuinely addressable slice is **cities + open roads: 34.2%** of the
human's buildup touches (35.6% of the champion's).

## 2. Per-seat conversion and feed — does it pay, and do the seats differ?

`fixed_v1`, pooled touches. Rates are the fate mix of each seat's **buildup**
touches.

| | buildup touches | → self | → opp (**feed**) | → both | → nobody |
|---|---:|---:|---:|---:|---:|
| human, all terrains | 2,211 | 8.9% | 9.2% | 9.7% | **72.1%** |
| champion, all terrains | 1,968 | 10.7% | 8.3% | 9.1% | **71.9%** |
| human, structural | 1,291 | 11.0% | 12.3% | 2.9% | 73.8% |
| champion, structural | 1,103 | 15.1% | 11.4% | 2.3% | 71.3% |

**Within-game paired contrast (human − champion), n=23 games, ± SEM:**

| metric | human | champion | paired H−C | z |
|---|---:|---:|---:|---:|
| unclaimed value added / ply | +2.440 | +2.041 | **+0.399 ± 0.100** | **+4.01** |
| buildup-ply share (structural) | 0.856 | 0.785 | **+0.071 ± 0.021** | **+3.42** |
| unclaimed value added / ply (structural) | +2.179 | +1.836 | **+0.343 ± 0.097** | **+3.55** |
| feeds an *already-claimed* opp feature (share of touches) | 0.046 | 0.033 | +0.013 ± 0.007 | +1.79 |
| conversion → self (structural) | 0.115 | 0.153 | **−0.038 ± 0.021** | **−1.82** |
| conversion → self (all) | 0.091 | 0.108 | −0.017 ± 0.016 | −1.04 |
| feed → opp (all) | 0.094 | 0.083 | +0.011 ± 0.012 | +0.95 |
| never claimed | 0.718 | 0.719 | −0.001 ± 0.015 | −0.08 |
| **net points / buildup touch** | **+0.016** | **−0.000** | +0.017 ± 0.026 | +0.65 |
| net points / buildup touch (structural) | +0.007 | +0.032 | −0.024 ± 0.045 | −0.54 |

**Read it plainly.** Only three contrasts clear 3σ, and all three say the same
thing: **the human invests in ownerless structure more than the champion does**
(more buildup plies, +0.40 points of ownerless value added per tile). Everything
about *converting* that investment goes the **other** way or is noise: his
structural conversion is lower (z −1.82), his feed rate is slightly higher, and
the **net points per buildup touch is statistically indistinguishable from zero
for both seats.**

Caveat on the volume contrast: buildup-ply share is **not independent of claim
policy**. The champion has far more `own_growth` touches (525 vs 385), i.e. it
has meeples down earlier, which mechanically shrinks its buildup denominator and
inflates its conversion. Part of the +3.42 is "the human claims later", not "the
human deliberately builds ownerless things".

**Per-terrain, paired (n=23):**

| terrain | metric | human | champion | paired H−C | z |
|---|---|---:|---:|---:|---:|
| **road** | conversion → self | 0.146 | 0.262 | **−0.117 ± 0.039** | **−2.99** |
| road | net (self − opp) | −0.052 | +0.124 | **−0.175 ± 0.067** | **−2.61** |
| city | conversion → self | 0.312 | 0.231 | +0.081 ± 0.057 | +1.42 |
| city | net (self − opp) | +0.094 | −0.008 | +0.102 ± 0.086 | +1.18 |
| farm | net (self − opp) | +0.006 | +0.009 | −0.004 ± 0.035 | −0.10 |
| cloister | — | 0 | 0 | 0 | n/a |

The champion is **decisively better at ownerless-road buildup** (z −2.99 against
the human). The human's edge is on **cities** and does not resolve (z +1.18/+1.42
— by the project's own n-threshold discipline, inconclusive, and it is one of six
terrain contrasts so it deserves a multiplicity discount on top).

## 3. The mechanism test — does investment buy the option?

The cleanest, seat-symmetric question, free of the meeple-supply confound: among
features **exactly one** player ever claimed, did the player who laid more of its
ownerless tiles get it?

| | n features | decided | builder won | builder lost | tied | share | z vs 0.5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| all terrains | 530 | 351 | 184 | 167 | 179 | **0.524** | **+0.91** |
| structural | 489 | 318 | 167 | 151 | 171 | 0.525 | +0.90 |

**Laying more of a feature's ownerless tiles buys ≈ a 2.4-point edge on who ends
up claiming it — a coin flip.** A claim needs a free meeple, a drawn tile that
touches the feature, and the willingness to spend the meeple; none of those
correlate much with who did the building.

**What this does and does not refute.** It refutes the *narrative* ("build it up
and you'll get it"). It does **not** test the *proposed estimator* — J13's
`P(claim)` would come from the remaining extension-tile multiset plus both meeple
reserves, not from who built more. That estimator is untested here and remains
the only live path.

---

## Honest read: does a J13 leaf term have room?

**The premise survives; the story does not.**

*What survives.* The leaf really does price ownerless structure at zero, 29% of
all points paid really do flow pro-rata through ownerless-phase tiles, and a
build-then-claim window really does exist (37% of claimed features get ≥2 tiles
before their first claim). The accounting headroom is real.

*What does not.* The differential — the thing a **signed** term must capture — is
zero as realized. Net points per buildup touch: human +0.016, champion −0.000,
paired z +0.65. Neither seat currently extracts net value from ownerless buildup.
And the specific hypothesis that motivated the lever is **refuted in sign**: the
prediction was that the human selectively builds what he can capture while the
champion is indifferent because its leaf cannot see the value. Measured, the
champion **converts better** (structural 0.153 vs 0.115, z −1.82; on roads
0.262 vs 0.146, z −2.99) while the human **builds more** (z +3.42/+4.01). A leaf
that literally cannot see unclaimed value is not the seat that is losing this
exchange.

*Scale check.* ~96 buildup touches per seat per game at ≈0.00 net points each,
against a mean |final score difference| of 22.1 points and 192 points paid per
game. A term that moved the net from 0.00 to a very optimistic +0.05 pts/touch
buys ≈5 points/game — plausibly relevant, but it has to be *right* about a
28%-base-rate event and right *differentially*, where the realized split today is
8.9% self vs 9.2% opp.

*Where the remaining room is, precisely.* Cities and open roads only — 34% of
buildup touches. Cloisters (24%) are inapplicable by the rules and the leaf's zero
is exactly correct there. Farms (42%) already have dedicated terms and are
dominated by contested fields.

**Verdict: DISCOURAGING BUT NOT A KILL.** Do not build the term on this evidence.
The one thing that would change the picture is a *position-derived* `P(claim)`
estimator that beats the base rate — which this instrument does not measure and
cannot measure, because it only ever sees what actually happened.

## If the term is built anyway — what it would be and what gates it

**Build the estimator first, offline, as a classifier — not as a leaf term.**
From a mid-game position, predict for each currently-ownerless city/road which
seat (if either) ends up claiming it. Label it with the realized fates this
instrument already emits; grade on this 26-game corpus *plus* champion self-play,
where n is unlimited and free.

**Gate it on discrimination, not prediction.** This is CL-073's lesson verbatim:
a model can predict the outcome better than the heuristic while ranking sibling
moves ~30× worse. So the gate is **not** "the classifier has good AUC on claim
fate". The gate is: **wiring `V(f) × (P_self − P_opp)` into the leaf must improve
sibling move ordering against the solver / `h6400_v2.9` ruler**, on the
cities-and-roads slice, before a single game is played. That is the same falsifier
that closed the learned-value route (CL-039/042/064/065/066/073) and it applies
here unchanged.

**Only if that passes** spend a within-band deck-paired n≥400 A/B on a fresh
claim band from `governance/BAND_REGISTRY.csv`. Do not spend it first — the
offline gate is free and this pre-gate says the prior is unfavourable.

**Do not re-derive the base rates.** They are in
[VERDICT.json](VERDICT.json) (`feature_base_rates`, `claim_race`,
`pooled.*.fate_by_terrain`), per epoch, with the raw per-game records under
`raw/`.
