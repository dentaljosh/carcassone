# E4 — human-vs-champion games (phone archives)

Pulled from the Pixel via adb (`run-as com.jishal.carcassonne cat files/games/*.json`),
schema `carcassonne-android-archive/v1`: lossless `(deck_seed, actions)` per the
root_replay contract, plus result summary, per-move AI latencies, and provenance
(champion id, leaf hash, effective budget).

**⚠️ Grading context is EPOCH-DEPENDENT — read the archive, not this sentence.** Archives
from **before the 2026-08-01 app build** were played at the **k4×688 mobile carve-out**
(~50 elo below the champion of record) and grade against that budget. Archives from the
**2026-08-01 build onward** were played by the **champion of record** — k8×1376 = 11008 on
the rust backend; the carve-out is **CLOSED** (see PRODUCTION.yaml `deploy_profiles` and
DECISIONS 2026-08-01 evening). Every archive records `sims_effective`/`k_dets_effective`,
and from 2026-08-01 the **ABSENCE of `runtime_budget_override`** is the full-strength
marker. Full epoch rules — including `start_rule` and `grid_rule` — in the
"Grading-epoch boundary at 2026-08-01" section below.

**Replay verification (2026-07-30, desktop, PROD_ENV + project venv):** both archives
replay to termination and the desktop-recomputed final scores match the phone's recorded
scores exactly (111–113 and 73–108) — phone→desktop replay is lossless and
cross-platform (ARM/Pixel → x86/WSL) deterministic.

| file | date | result (human first) | note |
|---|---|---|---|
| `1785205383_867966.json` | 2026-07-27 | **111–113 L** | Joshua's 2nd-ever game; 2-pt loss |
| `1785466497_161583.json` | 2026-07-30 | **73–108 L** | the invisible-border game (top-row wall); farms won 27–3, during-play lost 44–89 |
| `1785975832_66810.json` | 2026-08-05 | **98–78 W** | 🏆 **FIRST HUMAN WIN, and it is against the CHAMPION OF RECORD at full strength** — `sims_effective 1376` × `k_dets_effective 8` = **11008**, `start_rule retail` + `grid_rule centered18` (fixed_v1), `verify: true`, leaf `a36d2e15a3b3d71d`, and **no `runtime_budget_override`** = the full-strength marker. Won on the *endgame ledger*, not during play: during-play 41–43 (−2), **unfinished features 42–26 (+16)**, farms 15–9 (+6). That is the exact pattern the slice-1 analyzer said was missing from the two losses (incomplete_pts 2 and ~20 vs a corpus mean of 23.0 — meeples recycled instead of banked). 142 actions, 72 tiles. |

| `1785982194_705585.json` | 2026-08-05 | **80–87 L** | first **fixed_v1-epoch** game (the build stamps `rules_profile`/`cloister_rule: fixed`/`farm_rule: r9` — the provenance fields whose absence caused the same-day grading retraction). Champion won on during-play 68–37. |
| `1785984310_1698417952.json` | 2026-08-05 | **101–107 L** | close; farms 33–30 — the contested-farm battle game (Joshua: one ~30-pt farm, 4–5 meeples, "kept flipping"). |
| `1785986044_1911511187.json` | 2026-08-05 | **109–65 W** | second human win, the blowout: during-play 71–50 AND farms **30–0** (champion at 0 farm pts ≈ its own p5). |

| `1786045035_338139.json` | 2026-08-06 | **105–115 L** | farms 39–36 Joshua; lost on unfinished 16–36 |
| `1786074812_935815.json` | 2026-08-06 | **90–104 L** | **first game Joshua lost the farms** (12–24) |
| `1786076853_2116173857.json` | 2026-08-07 | **90–87 W** | 3-pt win; champion won during-play 56–48 |
| `1786113542_627623.json` | 2026-08-07 | **116–78 W** | biggest win; during-play 78–53 **and** farms 33–0 |
| `1786116818_134510.json` | 2026-08-07 | **76–104 L** | champion's biggest during-play win, 68–26; farms tied 27–27 |
| `1786118143_1621601234.json` | 2026-08-07 | **74–71 W** | 3-pt win, lowest-scoring game of the set |
| `1786142936_703591.json` | 2026-08-07 | **74–112 L** | biggest loss (−38); during-play 65–29, farms tied 24–24 |
| `1786242001_49628.json` | 2026-08-07 | **86–95 L** | farms 39–0 to Joshua and he still lost — during-play 66–40, unfinished 29–7 |
| `1786243458_1382293676.json` | 2026-08-07 | **97–75 W** | farms 18–0; won during-play too (63–57) |

| `1786325073_523563.json` | 2026-08-09 | **140–84 W** | 🏆 **record margin +56** — during-play 101–34 (+67), unfinished 24–38 (−14), farms 15–12 (+3). Graded (EV-loss, see below): champion mean ΔQ 0.01061, human 0.03224 (3.04×, z +2.48), human blunders 1 / champion 0. |
| `1786329790_523563.json` | 2026-08-09 | **115–86 W** | ⚠️ **SAME `deck_seed` as the game above (523563)** — the app appears to have reused the seed on a rematch (not investigated further, noted as a likely app bug, not a human choice: Joshua did not choose to replay the deck, and action-sequence divergence from the prior game starts within the first couple of tiles — a human cannot memorize a 72-tile draw order anyway). During-play 57–43 (+14), unfinished 34–37 (−3), farms 24–6 (+18). Graded: champion mean ΔQ 0.01894, human 0.05087 (2.69×, z +2.38), human blunders 6 / champion 1. |

### EV-loss grading, both 2026-08-09 games (`scripts/analyzer/ev_loss.py`)

Both graded at the archive's own budget k8×1376 = 11008, `fixed_v1` profile resolved from the
archive's **explicit `rules_profile` stamp** (the resolver's priority-1 route — see
`resolve_profile_name` in `ev_loss.py`). Both replay-verified (`integrity.replay_scores_match:
true`, final scores match recorded exactly) and both **acceptance-gate PASS**
(`acceptance_gate.pass`): champion mean ΔQ 0.01061 vs null p95 0.07566 (game 1), 0.01894 vs
0.08958 (game 2) — both well inside the instrument's own noise floor.

| game | champion mean ΔQ | human mean ΔQ | ratio | z (human−champ) | human blunders | champion blunders |
|---|---:|---:|---:|---:|---:|---:|
| `1786325073` (140–84, +56) | 0.01061 | 0.03224 | 3.04× | +2.48 | 1 | 0 |
| `1786329790` (115–86, +29) | 0.01894 | 0.05087 | 2.69× | +2.38 | 6 | 1 |

Exact tail: both seats played optimally in both games (0.0 pts regret on every latched ply — 2
human / 2 champion plies in g1, 1 / 1 in g2). Artifacts:
`../analyzer_evloss_20260805/EV_LOSS_1786325073_523563.{json,md}`,
`../analyzer_evloss_20260805/EV_LOSS_1786329790_523563.{json,md}`. No strength claim, no
`governance/PRODUCTION.yaml` change.

## The fixed_v1 epoch at n=14: a small positive lean, carried by two wins on a shared deck

Fourteen games under the current rules (2026-08-05 → 08-09). **W 7 / L 7, winrate 0.50.**
Margins (Joshua − champion): −7, −6, +44, −10, −14, +3, +38, −28, +3, −38, −9, +22, **+56, +29**.

⚠️ **Games 13 and 14 (`1786325073_523563`, `1786329790_523563`) share `deck_seed` 523563** — see
the note on the second row above. Their margins are correlated through one common deck effect,
so the n=14 se below is **very slightly optimistic** (14 games, not 14 independent draws). The
rigorous per-game read for these two is the **deck-adjusted residual** below, not the raw margin.

| statistic | mean | se | z |
|---|---:|---:|---:|
| **TOTAL margin** | **+5.93** | 7.43 | **+0.80** |
| during play | −1.21 | 7.73 | −0.16 |
| unfinished features | −4.43 | 3.14 | **−1.41** |
| **farms** | **+11.57** | 3.85 | **+3.01** |

The two new wins pull the total from dead-even (−0.17 at n=12) to a small positive lean (+5.93
at n=14), still well inside 1σ — not a distinguishable shift. The farm component stays the one
component past 2σ and is now the only one past 3σ. ⚠️ **Unpaired, one seat, not fully
independent (shared-deck note above), and the human is an ASSISTED and IMPROVING player**
(BACKLOG 2026-07-30 assists entry) — a description of fourteen games, NOT a rating. Phase-C
sizing for a real read: **193 seat-swap deck-paired games at true wr 0.55, 48 at 0.60.**

### Deck-adjusted residual for the two 523563 games (2026-08-09)

A single-deck extension of the 2026-08-08 control-variate ledger below (not folded into its
formal n=12 estimates — see the scope note there): the champion self-played deck `523563` K=8
times at the full 11008 budget under `fixed_v1` (`scripts/e4_deck_baseline.py --k 8 --workers 14
--rust-threads 1`, local box, 3.3 min wall, all games `replay`-consistent, no failures). Self-play
margins (seat0 − seat1): +21, +11, +2, −2, −16, −20, +15, −7 → **d̂ = +0.50 ± 5.17** — a
near-neutral deck, close to `627623` (+0.88) and `2116173857` (−0.25) in the existing ledger.

| game | margin | d̂ | **residual (margin − d̂)** |
|---|---:|---:|---:|
| `1786325073` (140–84, +56) | +56 | +0.50 | **+55.5** |
| `1786329790` (115–86, +29) | +29 | +0.50 | **+28.5** |

**+56 was earned, not deck-carried.** This deck is worth almost nothing to seat 0 in the
champion's own hands (+0.50, inside 1 se of zero), so the residual sits within a point of the
raw margin. **+55.5 is the new largest residual in the ledger**, ahead of the previous record
`627623` (+38 margin, +37.12 residual — [READOUT.md §3](../e4_deck_baseline_20260807/READOUT.md)).
The rematch game (+29, residual +28.5) is
smaller but still the third-largest residual on record — on the *same* near-neutral deck, so it
is not a case of one favorable deck being exploited twice.

### Deck luck priced out of that −0.17 (2026-08-08)

> **Scope note (2026-08-09):** the subsection below is the CLOSED n=12 formal control-variate
> experiment, unchanged. The n=14 single-deck residual check above is a separate, informal
> extension covering only the two new games' shared deck; it is not folded into the β̂/ICC
> estimates below.

The champion self-played each of these 12 decks 8× at the full 11008 budget under `fixed_v1`,
to estimate what each deck is intrinsically worth to seat 0 and read his margin against it as
a control variate → [e4_deck_baseline_20260807/READOUT.md](../e4_deck_baseline_20260807/READOUT.md).
**Result: the adjustment bought 4.2% on the se — `−0.17 ± 6.76` vs `−0.17 ± 7.06` — and by
construction could not move the point estimate at all** (the adjustment is centred). His 12
decks were collectively neutral (mean deck value **+0.23**), and deck luck is smaller here than
Phase C priced it: self-play deck-effect sd **7.16** vs within-deck game sd **21.49**, i.e.
**ICC 0.100** (ANOVA F(11,84) = 1.887, p = 0.053), against Phase C's 0.19.
**The lasting output is the per-deck ledger, not the error bar:** the **−38** loss (`703591`)
came on a *neutral* deck and is genuinely his worst game; the **116–78** win (`627623`) was
earned on a neutral deck; the **109–65** blowout (`1911511187`) came on the most seat-0-favourable
deck of the twelve (**+20.25**, ~half the margin); and the **74–71** win (`1621601234`) is the one
result the deck carried (deck **+17.50**, he took **+3**). No strength claim, no claim id.

## ⚠️ Champion farm points against Joshua — an estimate that will not sit still

| n | champion farm pts/seat vs Joshua |
|---|---|
| 3 | 11.0 |
| 6 | 19.5 |
| 12 | 14.8 (se 3.8) |
| **14** | **13.93** (se 3.34; its own self-play corpus = 20.5) |

The 2026-08-05 "the champion is starved of farms (11.0 vs 20.5)" claim was a 3-game artifact and
was corrected on 08-07 to 19.5, then to 14.8 at n=12; at n=14 it is 13.93, i.e. **~1.97σ below its
corpus norm and still moving**. Do not quote any single value of this as a fact. What IS stable at
n=14 is the *paired* farm margin above (+11.57, z +3.01) and one concrete oddity: the champion
scores **zero** farm points in **4 of 14** games (unchanged from n=12 — neither new game is a
champion-zero-farm game: 12 and 6 pts), against a corpus p5 of 0. The farm-war discriminator that
this motivated returned INCONCLUSIVE
([FARMWAR_READOUT](../analyzer_evloss_20260805/FARMWAR_READOUT.md)), so nothing downstream depends
on the unstable figure.

Joshua's overall E4 record: **8–10** (17 archived games: 8W–9L, direct recount of every archived
game's recorded `scores`, plus 1 pre-archival unrecorded loss — game 1 predates the archiving
feature, not an archive bug. ⚠️ This corrects a 1-win bookkeeping gap in the previous "5–10"
figure: the prior 15 archives recount to 6W–9L, not 5W–9L); the fixed_v1-epoch record is **7–7**.
Joshua wins the farms in **11 of 14** fixed_v1 games and averages 25.5 farm pts/seat against the
corpus norm of 20.5. ⚠️ **The luck floor is real** — champion-vs-greedy paired-deck play leaves
~6.25% pooled luck in the base game — so at n=14 unpaired this is a description, not a rating.

## ⚠️ Grading-epoch boundary at 2026-08-01 (the rust-port flips)

Games archived BEFORE the 2026-08-01 app build grade against the **k4×688 mobile
carve-out** on the **walled engine grid** with the **random start tile** (the two games
above). Games from the 2026-08-01 build onward carry three simultaneous changes, each
recorded in the archive payload: **budget = the champion of record k8×1376** (rust
backend; the carve-out is closed — see DECISIONS 2026-08-01), **start_rule = retail**,
and — from the recentring build — **grid_rule = centered18**. Cross-epoch E4 comparisons
must condition on these fields; per-game self-consistency is unaffected (both seats play
the same rules in any one game).
