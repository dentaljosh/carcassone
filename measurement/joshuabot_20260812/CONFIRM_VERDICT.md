# Joshua-bot tournament — CONFIRM VERDICT (2026-08-13)

**Status: ADJUDICATED. Nothing promoted; `governance/PRODUCTION.yaml` untouched; no champion
claim minted. Prereg of record: [TOURNAMENT_PREREG.md](TOURNAMENT_PREREG.md) §5 rule 4.**

## The cell

Top screen cell by margin = **J7ZERO** (`current+j7w0`: preset `current`, `j7_weight 0.0`),
re-run on the **fresh sealed band 1.26e11**, 400 decks × 2 seats, `fixed_v1`+R9, candidate =
the scripted JoshuaBot, opponent = the **unmodified production champion** (fair PIMC
k8×1376 = 11008, rust).

**Integrity:** 800 records, 800 unique cells, 0 missing, 0 extra, single `variant_id`.
**1 failed game** (deck `126000000135` seat 0 — the bounded-action-window family; see
[CONFIRM_EXCLUSIONS.md](CONFIRM_EXCLUSIONS.md)) ⇒ **n_scored 799, 399 paired decks**, failure
rate **0.125%**, 4× below the 0.5% house reference; neither pre-stated validity trigger fired.

## The number

| statistic | value |
|---|---|
| win rate (bot) | **0.2040** |
| paired margin | **−16.036 pts/deck** |
| sem | 0.657 |
| **margin z** | **−24.42** |

Screen cell for the same variant read −17.99 ± 0.96; the confirm sits **+1.96 above it**
(z +1.68 on the difference) — consistent, no winner's-curse regression to report, and the
movement is in the *favourable* direction, i.e. the screen did not flatter this cell.

## Adjudication

**The pre-registered claim this cell could have bought — "a variant beating the champion at
≥2σ is the program's first powered, reproducible anti-champion instrument" — is NOT bought.**
The bot loses by 16 pts/deck at z −24.4. **The instrument question (a) is answered NO, and it
is answered with power**, not with an underpowered null.

⚠️ **What this does NOT establish: that the anchor's strategy is worthless.** The result is
**confounded by search depth and the confound is large**. The bot applies J1–J9 on top of a
**one-ply greedy** base; the champion runs 11008-sim PIMC + exact endgame. The project's own
calibration for that gap: JCloisterZone's `LegacyAiPlayer` — a one-turn BFS + one static
evaluator, i.e. a *stronger* shallow player than our greedy base — loses to the same champion
by **−6.50 pts/deck at wr 0.345** (`jcz_legacyai_vs_champ_fixed_v1_r9_n400`). Joshua-bot at
**−16.04 / wr 0.204** is therefore **weaker than JCZ's AI**, which prices the encoding-plus-base
as a shallow player and says nothing clean about the *strategy*.

**Read the two questions separately, as the prereg required:**

- **(a) INSTRUMENT — NO.** No variant reproduces the human's +10.0 ± 5.6 pts/game lean. The
  scripted anchor strategy on a greedy base is not an anti-champion instrument, and structural
  blocker #1 remains undented by this route.
- **(b) CALIBRATION — ANSWERED, and this is the run's real product.** Within a shared shallow
  base the axis contrasts are clean (screen, per-axis contrasts powered as-if-independent):
  **`j7_weight` 0 > 1** (+5.34 pts/deck, z +3.71) · **preset `current` > `early`** (+5.81,
  z +3.68) · **J8 exemption inert** (exactly 0 — see [J8EX_INERT_FINDING.md](J8EX_INERT_FINDING.md))
  · **J9 no conviction** (−2.14, z −1.47 ⇒ defaults to interview fidelity, OFF).

## What the owner's open questions now have as answers

| # | question | empirical answer | strength |
|---|---|---|---|
| 1 | J7 farm-feed weight | **0.0** (count his farm points once, not twice) | z +3.71, clears |
| 3 | J8 reserve-floor exemption | **inert** — changes zero chosen moves | exact, not statistical |
| 6 | which preset is the reference | **`current`** | z +3.68, clears |
| 2 | J9 cloister caution | **no conviction**, point estimate negative ⇒ stays OFF | z −1.47 |

⚠️ J9's timing threshold (0.55) was **borrowed** from J10's farm block, so this tests one
encoding of the cloister adaptation, not the idea. ⚠️ J8 is **untested, not refuted** — the
exemption is pre-empted by F-J3's skip-when-empty rule; if "you have to take chances" is meant
to bite, J8 should arguably be a *score* term rather than a filter exemption.

## The design fix this run earns (named, not funded)

Run the J-rules as a **policy/leaf modifier on top of the champion's own search** instead of on
a greedy base. That is the only way to isolate STRATEGY from DEPTH and make question (a)
answerable; the present design cannot separate them, and no amount of n fixes that.

## Governance

Bands **1.25e11** (screen, 6 cells) and **1.26e11** (confirm) both flip **claimed → retired,
decision-influenced** (the screen selected the confirm cell; the confirm adjudicated). No
`governance/CLAIM_REGISTRY.csv` row: a non-conviction on an instrument question mints no claim.
`experiments/results.csv` rows ARE owed here — unlike the 0-game oracle instruments, these are
2,600 real head-to-head games (1,800 screen + 799 confirm) against the production champion.
