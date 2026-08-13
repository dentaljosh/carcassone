# JOSHUA-BOT VARIANT TOURNAMENT — PRE-REGISTRATION (screen + confirm)

> ## 🔚 EXECUTED AND CLOSED OUT 2026-08-13 — this pre-registration is SPENT
>
> All 7 cells ran (6-cell screen n=300 on band 1.25e11 → J7ZERO confirm n=800 on the sealed
> band 1.26e11). **Adjudication lives in [CONFIRM_VERDICT.md](CONFIRM_VERDICT.md), not here.**
> One-line result: **the anti-champion instrument claim is NOT bought, and it is refused with
> power** — confirm margin **−16.036 pts/deck, z −24.42** (799 scored / 399 paired decks, 1
> excluded game, 0.125 %). ⚠️ **The run cannot separate STRATEGY from DEPTH** (J1–J9 on a
> one-ply greedy base; JCZ's shallower-but-stronger `LegacyAiPlayer` loses to the same champion
> by only −6.50), so it prices the encoding-on-a-greedy-base. The **calibration** (question b)
> is the real product: `j7_weight` 0 > 1 · preset `current` > `early` · **J8 exemption exactly
> INERT** ([J8EX_INERT_FINDING.md](J8EX_INERT_FINDING.md)) · J9 no conviction.
> Six-touch close-out: `experiments/results.csv` rows
> `joshuabot_screen_*_n300_b125e9` ×6 + `joshuabot_confirm_j7zero_*_n799_b126e9` ·
> DECISIONS 2026-08-13 · `STATUS.md` · `docs/PROGRAM_ROADMAP_2026-07-07.md` ·
> `docs/LEVER_INDEX.md`. **No `CLAIM_REGISTRY` row** (a non-conviction on an instrument
> question mints no claim); `governance/PRODUCTION.yaml` untouched. Bands 1.25e11 / 1.26e11
> are **retired, decision-influenced** — ⚠️ their `governance/BAND_REGISTRY.csv` rows were not
> flipped by this close-out (the file was held by another session) and remain **owed**.
>
> **STATUS AT WRITING: WRITTEN 2026-08-12 (late), BEFORE GAME 1 AND BEFORE ANY VARIANT'S MARGIN WAS
> READ.** Not yet authorized, not yet launched. Its purpose is to fix the cells, the primary
> statistic, the read-rules and the band *before* the numbers exist — the forking-path
> discipline that the denial campaign codified after four winner's-curse instances
> (§6). **0 games played at the time of writing.**
>
> **This document promotes nothing.** The Joshua-bot is an **instrument**, not a champion
> candidate and not a strength lever. `governance/PRODUCTION.yaml` is untouched on every
> branch below, no `CLAIM_REGISTRY` row is minted by the screen, and no leaf, search or
> config knob of the champion is modified anywhere in this campaign.
>
> Bot build + rule derivation: `measurement/joshuabot_20260812/SPEC.md` (J1–J10, and the
> eight OPEN QUESTIONS this tournament answers three of). Driver: `scripts/joshuabot/h2h.py`.
> Chain launcher: `scripts/joshuabot/tournament_chain.sh`. All three land in the main tree
> at the bot worktree's merge — they are deliberately *not* linked here, because this file
> is written before that merge.
>
> Primary source for the strategy: [ANCHOR_INTERVIEW_2026-08-12](../e4_games/ANCHOR_INTERVIEW_2026-08-12.md).
> Conventions parents: [denial screen PREREG](../denial_screen_20260811/PREREG_DRAFT.md) ·
> [sims-split census PREREG](../simsplit_census_20260811/PREREG.md).

---

## 0. Why this exists, in one paragraph

The E4 human stream is the only non-saturated signal in the program, and it arrives at ~1
game/evening from a **nonstationary** anchor ([E4_UPDATE_20260812](../e4_games/E4_UPDATE_20260812.md);
lean **+10.0 ± 5.6 pts/game**, n=23, z +1.78 — unpowerable at that rate; the `fixed_v1`-epoch
subset reads **+9.13 ± 7.63**, n=15). The anchor interview wrote his strategy down; the bot
encodes it. This tournament asks whether the written-down strategy, played at volume against
the champion of record, reproduces any of the lean — and, in the same games, which settings
of the three interpretation questions the owner declined to answer by hand
(*"test these and see what wins empirically"*, 2026-08-12) the record actually favours.

---

## 1. TWO questions, kept strictly distinct

They share games; they do **not** share a read-rule, a power calculation, or a verdict.

**(a) INSTRUMENT — does the scripted strategy reproduce the E4 lean at scale?**
Statistic: each cell's own deck-paired margin (bot − champion, pts/deck) and its sign.
This question is **well powered** at the screen's n (§4): a reproduction worth even ~+3
pts/deck reads z ≈ 3. A large negative margin in every cell is the informative negative
result — it says the articulated strategy is not the edge, and the edge is in what the
anchor cannot articulate (or in variance), which is exactly what the LEVER_INDEX row
predicted would be worth knowing ([LEVER_INDEX](../../docs/LEVER_INDEX.md), *human-strategy
scripted opponent*).

**(b) CALIBRATION — which settings of the owner's open questions 1–4 does the record favour?**
Statistic: the per-axis contrast (cell − BASE) on the same band. This question is **weakly
powered by construction** (§4: ±2.8 pts/deck at 2σ) and is governed by the binding
read-rules in §5, whose default is *interview fidelity*, not the empirical argmax.

Question (a) can resolve while (b) does not. That is the expected outcome and is not a
failure of the design.

---

## 2. The two players, and what the numbers are comparable to

| seat | agent | budget / config |
|---|---|---|
| candidate | `carcassonne_ai.joshua_bot.JoshuaBot` at the cell's variant | deterministic, no RNG, no search; ~50–85 ms/move |
| opponent | the **production champion of record**, `champion_factory.make_production_champion("fair", verify=True)` | fair PIMC at the `fair_deploy` budget in [`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml) (k_dets 8 × sims_per_det 1376 = 11008 per move at the time of writing — **read the file, do not trust this parenthesis**), `backend: rust`, exact-K endgame tail per production |

**Rules epoch: `fixed_v1` (implies `CARCASSONNE_FIX_R9=1`).** This is the epoch the E4 human
games are played in and the only one the app has stamped since 2026-08-05 — the bot must be
measured under the rules of the human it imitates. ⚠️ R9-on is **not** the production
default: **nothing in this campaign is comparable to walled elo**, and no row here may be
placed on a walled ladder.

⚠️ **Bot-vs-champion margins are NOT comparable to human E4 margins.** Different opponent
behaviour distributions (the champion's farm income alone moves 14.0 → 20.5 → 31.9 pts/seat
across Joshua / self-play / JCZ), different assist levels (the bot counts the bag and
computes a virtual score by construction — interview §3 makes those in-scope for the human
reference but the human is not yet using them), different stationarity. **Reproduction of
the lean is a QUALITATIVE read: sign, and rough magnitude.** A sentence of the form "the bot
reproduces 62% of the human's +10" is forbidden by this prereg.

---

## 3. Design — the SCREEN: 6 cells, one shared band, n=150 decks each

Every cell: `--decks 150` (each deck seed played **both seatings** ⇒ **300 games/cell**,
1800 games total), `--profile fixed_v1`, rust backend, champion at the PRODUCTION.yaml
budget, deck-paired, same band for all six (CRN — see the §5 read-rule that refuses to spend
that CRN in the power calculation).

| # | cell | driver flags (on top of `--decks 150 --profile fixed_v1`) | axis it moves | expected `axes` in the manifest |
|---|---|---|---|---|
| 1 | **BASE** | `--preset current` | none — the interview-fidelity reference | `j7_weight 1.0`, `j8_break_reserve_floor false`, `j9_avoid_cloisters false`, preset `current` |
| 2 | **J7ZERO** | `--preset current --j7-weight 0.0` | OPEN Q3 — hesitate (1.0) vs merely notice (0.0) the 3 farm points his field takes when a bordering city closes | `j7_weight 0.0`, false, false, `current` |
| 3 | **J8EX** | `--preset current --j8-break-reserve-floor` | OPEN Q8 — **J8 present vs J8 absent** (see the reframe below), i.e. may a pivotal-feature overcommit break the J3 reserve floor? | `1.0`, **true**, false, `current` |
| 4 | **J9ON** | `--preset current --j9-avoid-cloisters` | OPEN Q1 — encode his stated cloister-caution adaptation? | `1.0`, false, **true**, `current` |
| 5 | **EARLY** | `--preset early` | OPEN Q6 — which epoch is the reference player (J10) | `1.0`, false, false, **`early`** |
| 6 | **ALLTOG** | `--preset current --j7-weight 0.0 --j8-break-reserve-floor --j9-avoid-cloisters` | interaction probe (3 axes at once) | `0.0`, true, true, `current` |

- **Sign convention everywhere: positive = Joshua-bot ahead** (the driver's
  `margin_joshua_minus_champ`).
- **One `--out` file per cell** — the driver refuses to append a different `variant_id` to an
  existing file, and each cell writes `<out>.manifest.json` with the fully resolved
  `JoshuaParams`. A cell is self-describing; no dirname archaeology.
- **No post-hoc cell insertion.** A promising-looking in-between setting (e.g.
  `j7_weight 0.5`, or `j9_cloister_block_frac` retuning) is a **new prereg**, not an extra
  cell here.
- ⚠️ **EARLY is a PRESET, not an axis.** It moves eight knobs at once (`early_farm_block_frac`,
  four J2 weights, the reach threshold, the farm-surrender bar, the city-count clock). Its
  contrast answers "which epoch plays better against the champion", never "which knob did it".
- ⚠️ **ALLTOG cannot attribute.** It reports only whether the joint perturbation beats BASE.
  If ALLTOG beats BASE while all three single-axis contrasts are null, the correct write-up
  is "unresolved interaction", not "the axes combine".
- The driver's `--override KEY=VALUE` (any `JoshuaParams` field, typed, raises on a typo)
  exists and is deliberately **unused by every cell here**. Sweeping a knob that this prereg
  did not name is a new prereg, not an extra cell.

### ⚠️ Two reframes recorded BEFORE the cells run (both from the bot build, 2026-08-12)

**J8EX is "J8 exists vs J8 absent", not a marginal exemption.** Measured on the built bot:
with the J3 reserve floor intact, `j8_overcommit` fired on **ZERO chosen moves per
`current`-preset game**; with `--j8-break-reserve-floor` it fires **8–28× per game**. The
hard filter F-J3 was swallowing the entire mechanism (SPEC §7 OPEN Q8 predicted the fight;
the measurement settles which side wins). Consequences, binding on the write-up:

- **BASE effectively plays with J8 OFF.** Every other cell in this screen (except ALLTOG)
  therefore also has J8 off — the pivotal-feature overcommit is absent from the reference
  player, and the reference player is still the interview-fidelity player, because "keep a
  meeple in hand" is a *hard economy statement* in the interview and "take chances" is not.
- **A null on the J8EX contrast means the whole J8 mechanism buys nothing measurable at this
  resolution** — not "the exemption tweak failed". That is a materially larger statement and
  it is the one that gets written.
- A *positive* J8EX contrast is the more interesting outcome: it says the interview's two
  meeple-economy sentences are in genuine tension and the record prefers the aggressive
  reading — which rule 2 of §5 still refuses to adopt below 2σ.

**J9's timing threshold is an invented number.** `j9_cloister_block_frac = 0.55` is
**borrowed verbatim from J10's `early_farm_block_frac`**, because the interview gives a
direction ("i'm more cautious about grabbing them now") and no clock. So the J9ON cell tests
*one specific operationalisation* of his cloister caution — cautious while more than 55% of
the bag remains, unless the cloister's 3×3 already holds 6 tiles. A null on J9ON is a null on
**that** encoding at that threshold, never on "he is cautious about cloisters"; re-tuning the
threshold after seeing the result is explicitly out of bounds (it would be a new prereg, and
`--override j9_cloister_block_frac=…` makes it cheap enough to be tempting).

---

## 4. Primary statistic and power (stated so no null can be over-read)

**Primary statistic: the within-cell deck-paired margin in pts/deck** (per deck, the mean of
`joshua − champion` over the two seatings; only decks with both seatings contribute). Elo is
reported alongside for readability and is **never** primary — see the house's repeated
elo-vs-margin disagreements (band 1.20e11 `curve175`: +25.2 elo with a flat margin z +0.70).

**Realized-σ basis (measured, not assumed).** The closest structural analogue with a
published paired sd is the **JCZ external-AI match** — a strong, out-of-lineage,
behaviourally-different opponent, deck-paired at 200 decks, `+6.50 ± 0.86` pts/deck ⇒ per-deck
**sd ≈ 12.2 pts**. (Champion-vs-champion cells are tighter — band 1.20e11 realized se
0.45–0.55 at 400 decks ⇒ sd ≈ 9.1–10.9 — so 12.2 is the conservative choice for an
asymmetric pairing.)

| quantity | n | se (pts/deck) | 2σ (pts/deck) | ≈ 2σ in elo |
|---|---|---|---|---|
| a cell's own margin (question **a**) | 150 decks / 300 games | **≈ 1.00** | **± 2.0** | ≈ ± 35 |
| a per-axis contrast (cell − BASE), powered **as if independent** (question **b**) | 150 vs 150 | **≈ 1.41** | **± 2.8** | ≈ ± 49 |
| the CONFIRM cell's own margin | 400 decks / 800 games | ≈ 0.61 | ± 1.22 | ≈ ± 21 |

Elo cross-check (house formula, unpaired): σ_elo = 695·√(0.25/n) = **±20.1 elo 1σ at n=300**,
halved-variance by pairing to **≈ ±14 elo 1σ**. ⚠️ That formula is calibrated near wr = 0.5;
if the bot's win rate lands far from 0.5 (likely), the elo interval widens and the **margin
is the only statistic to read**.

⚠️ **The realized sd is a prediction, not a measurement, until the first cell closes.** The
launcher records the realized per-deck sd of BASE; if it exceeds ~15 pts/deck the whole
power table above degrades ~25% and the §5 thresholds must be re-read against the realized
number, not this table. That re-read is a **reporting obligation**, not a licence to move a
threshold.

**Why the CRN across cells buys nothing here.** All six cells share one band and, because
`champion_seed()` keys only on `(deck_seed, joshua_seat)`, they share the champion's
determinization seeds too. That is deliberate and free — but the measured house lesson is
that CRN **across cells** bought only **9.9%** of the A−B contrast variance
([tile-allocation A/B](../simsplit_alloc_20260812/PREREG.md); LEVER_INDEX *deck-seed banding*
row), so the contrast se above is computed **as if the cells were independent**. Any
post-hoc claim of a tighter contrast se must be justified from the realized paired records,
in writing, before it is used.

---

## 5. READ-RULES — binding, and fixed before game 1

1. **THE SCREEN RANKS. IT NEVER PROMOTES, ADOPTS, OR SETS A DEFAULT.** No cell of this
   screen may change `PRESETS["current"]`, the bot's dataclass defaults, `PRODUCTION.yaml`,
   or any champion config. The only thing a screen result can buy is a CONFIRM (rule 4).
2. **Per-axis contrasts are read as (cell − BASE), powered AS IF INDEPENDENT** (§4). The
   thresholds are on the contrast, not on the cell's own margin:
   - `|contrast| ≥ 2σ` (≥ 2.8 pts/deck) → the axis **has a measured direction at screen
     resolution**. It still does not change a default; it makes that cell eligible for the
     confirm under rule 4.
   - `|contrast| < 2σ` → **the axis DEFAULTS TO INTERVIEW FIDELITY**: `j7_weight = 1.0`,
     `j8_break_reserve_floor = off` (⇒ J8 absent, per the reframe in §3),
     `j9_avoid_cloisters = off`, preset `current`. **Noise never overrides the anchor's
     self-report.** This is the whole reason the rule is
     written before the numbers: a sub-2σ empirical lean is a *worse* estimate of how Joshua
     plays than his own sentence about how he plays.
   - The EARLY contrast is read the same way, and its default-on-null is **`current`** (the
     epoch the live E4 stream is in).
3. **A cell's own margin (question a) is read against zero, not against BASE**, and carries
   only the qualitative claim licensed in §2.
4. **CONFIRM: the single top cell by margin — one cell, n=400 decks (800 games), on a FRESH
   band.** Top = highest deck-paired margin among the six; ties broken by the priority order
   in §7 (BASE first). The confirm is the *only* mechanism by which anything from this
   campaign becomes quotable, and it re-measures that cell **against the champion**, not
   against BASE. No pooling with the screen cell, ever (different band; §4 of CLAUDE.md's
   cross-band rule and the 1.24e11 precedent).
5. **The anti-champion-instrument claim needs the CONFIRM, never the screen.** A variant
   whose confirm margin beats the champion at **≥ 2σ** (≥ +1.22 pts/deck at n=400 decks) is
   the program's **first powered, reproducible anti-champion instrument** — a genuinely
   large result, which is exactly why it may not be minted from a 6-cell screen where the
   winning cell was *selected by being the maximum*. Until that confirm lands, the correct
   sentence is "cell X led the screen at n=150 decks".
6. **If the top cell is BASE**, the confirm still runs on BASE (it is the interview-fidelity
   player and the instrument question is about *it*), and the calibration question closes as
   "no axis moved the record at screen resolution; interview fidelity stands".
7. **Nothing in this campaign mints a claim id for a champion-strength statement.** The
   champion is the *opponent*, unmodified, on both sides of every contrast.

---

## 6. Winner's curse — the house's own record, and what it does to rule 4

The top cell of six is a **selected maximum**. The screen's per-cell se is ~1.0 pts/deck, so
under a true all-null the largest of six cells lands ~1.3–1.5 se above the mean by selection
alone (~+1.4 pts/deck ≈ +24 elo of pure selection). The house has four confirmed instances
of exactly this, all of them larger and all of them regressed:

| # | lever | screen | powered re-measure |
|---|---|---|---|
| 1 | `c=3` PUCT constant | "+47 elo" | a noise spike; forced the results.csv discipline (DECISIONS 2026-05-28) |
| 2 | `intra_reuse` within-turn carry | +40.1 (n=200) | +16.2 ± 10.0 at n=1200, **95% CI includes 0** |
| 3 | meeple-curve phase β = +0.3 | +33.1 / z +1.39 (n=200) | **sign-flipped** null at n=800, margin z −0.78 |
| 4 | `farm_growth_off` | pooled +26.6 ± 12.3 | **+3.3 ± 8.7** at n=1600 on a fresh band |

One counter-instance is on record and is the reason the confirm is worth running at all:
the denial dose-1.0 lean **HELD** on extension (halves −1.625 / −1.515, between-half z +0.08)
— leans do sometimes survive, which is why the rule is *confirm*, not *discard*.

⇒ **The screen's top margin is a biased estimate of that variant's strength and must never
be quoted as its value.** The confirm's number, on a fresh band, is the estimate of record.
If the confirm regresses to null, the honest write-up is "the screen's leader did not
confirm", and the axis reverts to interview fidelity per rule 2.

---

## 7. Bands (registered in `governance/BAND_REGISTRY.csv` in the same commit as this file)

| band | use | seeds consumed | tier / status |
|---|---|---|---|
| **1.25e11** = `125000000000` | the 6-cell SCREEN, CRN-shared | `125000000000 .. 125000000149` (150 decks × 2 seats × 6 cells) | dev / claimed |
| `125900000000 ..` | bench + the 6 axis-wiring probe games | `+900000000` offset — **inside the label, disjoint from the cells** (the 1.06e11 / 1.18e11 smoke precedent) | — (no cell influenced) |
| **1.26e11** = `126000000000` | the single CONFIRM cell, FRESH band | `126000000000 .. 126000000399` (400 decks); `+400 .. +799` **RESERVED, NOT LICENSED** | sealed / claimed |

- Seeds thread through the driver's `--seed-base`; deck seed *i* of a cell is
  `seed_base + i`, and both seatings of every deck are played (seat-major, so a killed run
  leaves complete pairs).
- **The screen band retires at close-out**: choosing the confirm cell IS a decision, so
  1.25e11 is decision-influenced and leaves confirmatory use. That is why the confirm draws
  a fresh band and why the reservation exists up front (the 1.21e11 correction — a registry
  row must never understate what a band will spend).
- The `+400..+799` reservation on 1.26e11 is **not** a pre-registered top-up licence. No
  top-up branch is registered for the confirm. Extending it requires a new prereg; topping
  up a cell that lands just under a threshold is the forking-path pattern that the 1.19e11
  close-out explicitly declined (|z| = 1.487, top-up not run).

---

## 8. Cost, the bench-first gate, and the degradation order

**Owner's grant (2026-08-12, verbatim intent):** *"both boxes are yours. laptop for like
48hrs. local w30 until 11am, then w14"*. The chain therefore picks **W per cell at cell start
time**: `W = 30` if the cell is projected to finish before 11:00 local, else `W = 14` — a
W30 cell must never straddle 11:00.

**Planning basis (measured, cited, and to be replaced by the bench):**

- The denial deploy confirm realized **≈ 238 s/game at 52 workers** across both boxes with
  **both** seats at the champion budget, and `champ_prefix_ms_per_move` **1466.5 ms** at 36
  workers ([PREREG_DEPLOY_CONFIRM](../denial_screen_20260811/PREREG_DEPLOY_CONFIRM.md);
  `verdicts/DEPLOY_CONFIRM.json`).
- A Joshua-bot game has **one** champion seat (~70 champion decisions instead of ~140) plus
  a ~50–85 ms/move bot ⇒ planning estimate **120–170 s/game per worker** at comparable
  contention. Everything below is arithmetic on that band, not a measurement:

| | games | at W30 (635–900 games/h) | at W14 (296–420 games/h) |
|---|---|---|---|
| one screen cell | 300 | **0.33 – 0.47 h** | 0.71 – 1.01 h |
| the 6-cell screen | 1800 | **2.0 – 2.8 h** | 4.3 – 6.1 h |
| the confirm | 800 | 0.9 – 1.3 h | 1.9 – 2.7 h |

**BENCH-FIRST IS A HARD GATE.** `tournament_chain.sh` runs `--limit 1` at production knobs
(BASE variant, bench seed range) and logs the realized single-worker s/game **before any cell
starts**. It then re-derives the table above from that number and:

- **aborts** (`FAILED_TOURNAMENT`) if s/game is absurd (> 600 s, the signature of a python
  backend fallback or a mis-resolved champion), and
- **degrades** the cell set to what fits the remaining W30 window, dropping from the END of
  this priority order:

  > **BASE → J7ZERO → EARLY → J8EX → J9ON → ALLTOG**

  Rationale for the order: BASE is the instrument question and the reference every contrast
  is taken against (without it nothing else is readable); J7ZERO is the owner's biggest
  single interpretation (SPEC OPEN Q3, "materially different players"); EARLY answers which
  epoch is the reference; J8EX and J9ON are single-line filters with narrower reach; ALLTOG
  cannot attribute and is the first thing to lose.
- Cells that do not fit are written to `DEFERRED_CELLS`, **not silently dropped** — the
  orchestrator can run them at W14 after 11:00 or on the laptop (each cell is an independent
  invocation with its own `--out`; the laptop's 48 h grant covers them).

⚠️ The bench is a **single-worker** timing. Converting it to a W30 throughput uses a
documented contention constant (`JB_CONTENTION_W30`, default 1.6; `JB_CONTENTION_W14`, 1.15)
which is a **planning constant, not a measurement**. `JB_BENCH_LIMIT=<W>` runs a full
contended wave instead if the orchestrator wants the honest number and can spend the extra
~5 minutes.

---

## 9. Wiring gates — before game 1 of the screen (all in the launcher)

1. **Flag-surface gate.** Every flag the chain uses must appear in `h2h.py --help`:
   `--decks --seed-base --preset --workers --out --resume --limit --j7-weight
   --j8-break-reserve-floor --j9-avoid-cloisters`. Missing flag ⇒ `FAILED_TOURNAMENT`, no
   games. (The three axis flags were **verified present in the bot worktree's COMMITTED
   driver** on 2026-08-12 — `--j7-weight FLOAT`, the other two argparse `store_true` — so
   they are no longer assumptions. The gate stays: this prereg was drafted against an
   unmerged tree, merging is the orchestrator's step rather than this document's, and the
   gate also catches a bool flag that later grows a value. The driver additionally
   **hard-refuses to append two different variants to one file**, which is why every cell
   gets its own `--out`.)
2. **Bench-record gate.** The bench game's record must carry `rules_profile == "fixed_v1"`,
   an `execution` block that resolves to **rust**, a non-null `champion_id`, and a non-null
   `total_sims_of_record`. A python-backend or unverified-champion bench voids the run.
3. **AXIS-WIRING GATE (the load-bearing one).** Each of the six cells runs a **1-game probe**
   on the disjoint probe seeds, and the probe's `<out>.manifest.json` must report the
   `axes` and `preset` in the §3 table. **A silently-ignored flag would make J7ZERO
   byte-identical to BASE and produce a guaranteed, meaningless null** — the same failure
   mode the band-1.23e11 W9 gate was written to catch (a defaulted-off cell A *is* cell B).
   Mismatch ⇒ `FAILED_TOURNAMENT`.
4. **Fire-count observation (descriptive, NOT a gate).** The probes' `joshua_rule_fires` are
   dumped to `probe/PROBE_FIRES.json`. If an axis's counter never fires in its probe game,
   the log WARNs — a cell whose rule never fires is destined to read null for mechanical
   reasons, and knowing that in advance changes how the null is written up. It **may not**
   be used to drop, add, or re-tune a cell (the denial calibration's §4 guard, restated).
5. **No concurrent tenancy for the timing numbers.** Strength statistics here are
   deck-paired and first-order insensitive to contention, but every absolute `ms/move`,
   `games/h` and the bench itself are not. The chain records `W` per cell in its log; any
   absolute timing quoted from a cell must name the W it ran at.

---

## 10. What this campaign CANNOT say (carried into every write-up)

1. **Not a strength claim about the champion.** The champion is unmodified on both sides of
   every contrast. Nothing here can move `PRODUCTION.yaml`.
2. **Not a measurement of Joshua.** It measures a *written-down reading* of eight sentences
   he said on one evening, with eight named interpretation choices (SPEC §6) and three of
   them under test. A null on an axis means "this reading did not separate at n=150 decks",
   never "he doesn't do that".
3. **Not comparable to the human E4 record** (§2), and not comparable to walled elo (R9 on).
4. **Not a fair fight in either direction.** The bot has assists the human does not currently
   use (bag multiset, exact virtual score, no misclicks) and lacks everything the human has
   (adaptation, look-ahead beyond one turn, the ability to change strategy mid-game). The
   anchor is nonstationary; the bot is frozen. That asymmetry is the *point* of an
   instrument, and it is also why the instrument can never replace the human stream.
5. **Flip-side of the instrument prize:** even a confirmed anti-champion instrument prices
   only *this* strategy. It becomes a regression target, not a strength verdict.

---

## 11. Close-out obligations (the six touches, one sitting)

`experiments/results.csv` rows (one per cell that ran, plus the confirm) → DECISIONS.md index
line → status banner on this file → `governance/BAND_REGISTRY.csv` rows flipped to `retired`
(both bands, at their own close-outs) → STATUS.md top block → the roadmap line. Then
`python3 scripts/doc_lint.py`. The LEVER_INDEX *human-strategy scripted opponent* row moves
off NEVER-TRIED to whatever the record says — including, if the screen is all-negative, a
plainly-worded "the articulated strategy does not reproduce the lean".
