# E4 — human-vs-champion games (phone archives)

Pulled from the Pixel via adb (`run-as com.jishal.carcassonne cat files/games/*.json`),
schema `carcassonne-android-archive/v1`: lossless `(deck_seed, actions)` per the
root_replay contract, plus result summary, per-move AI latencies, and provenance
(champion id, leaf hash, effective budget).

> ✅ **2026-08-17 (CURRENT): 9 NEW ARCHIVES PULLED (2026-08-16 14:27 → 08-17 22:10) + 7 BACKLOG
> ARCHIVES INGESTED.** Full readout, integrity checks and statistics:
> **[E4_UPDATE_20260817.md](E4_UPDATE_20260817.md)**. ⚠️ That readout covers **16** games — the
> seven archives from 2026-08-12 → 08-16 were pulled as raw data (`3d69c5b8`, `b5fd5427`) but
> never written into this ledger's prose. Headline moves:
> - **Overall record 26–16–1** (42 archives = 26 W / 15 L / **1 D**, + 1 pre-archival
>   unrecorded loss).
> - **`fixed_v1` epoch: n=39, W25/L13/D1, margin +13.846 ± 4.038 (z +3.43)** — new nine alone
>   6–3 (+16.778 ± 8.79), the seven-game backlog 6–0–1 (+22.571 ± 6.23).
> - ⚠️ **Read the trend, not the pool: this is a LEVEL SHIFT, not a learning rate.** Epoch
>   first 19 +6.53 (W9) vs last 20 +20.80 (W16), but the OLS slope *within* the 16 new games is
>   **−0.119 pts/game (z −0.10)** — flat — and the full-epoch slope has deflated for the second
>   readout running: +2.58 → +1.215 → **+0.586 (se 0.351, z +1.67)**. The anchor is
>   NONSTATIONARY (see `ANCHOR_INTERVIEW_2026-08-12.md`); the pooled z prices the human, not
>   the engine.
> - ⚠️ **The farm anomaly OSCILLATES — treat it as unresolved.** Block-by-block paired farm
>   margin **+11.40 → +1.50 → +18.00 (z +5.73) → +7.33**. The 08-12 "did not replicate" call
>   was correct on its data; it then un-collapsed and re-collapsed. **Do not quote the pooled
>   +9.615 ± 2.240 (z +4.29) as a stable effect.** Champion farm pts/seat at n=39: **15.62
>   (se 1.85)** vs a corpus norm of 20.5; zeroed in 7 of 39.
> - **During play is the component actually trending** (+3.43 → +6.57 → +10.78 across blocks,
>   monotone, each block individually z ≈ 1). Unfinished features stays his one persistent
>   deficit (−1.46 pooled, negative in every block).
> - **First draw in E4 history:** `1786590116_64346`, **55–55**, and the lowest-scoring game on
>   record (110 combined vs an epoch mean of 190.4). Replays exactly.
> - Integrity: **16/16 replay exactly**, **all 16 seeds distinct** (corpus-wide the only dup is
>   still the known pre-fix 523563 pair ⇒ seedfix confirmed a third time), no partials, and
>   **`assists` is still ABSENT in all 42**.
> - `rust_threads` went 4 → 2 at 2026-08-16 (battery A/B). **Not a strength boundary** — play is
>   bit-identical across thread counts; do not split the corpus on this field.
> - ⏳ **NOT run (deferred-gates job owns the boxes):** F14 per-deck baseline for the 24 unpriced
>   decks (~48 min at W14 — its "re-run at n~25-30" threshold is now met at n=39), and EV-loss
>   grading of the 11 ungraded games, epoch 29–39 (~50 min, exclusive tenant).
>
> <details><summary>Previous readout — 2026-08-12 (8 archives, epoch n=23)</summary>
>
> ✅ **2026-08-12: 8 NEW ARCHIVES INGESTED (2026-08-10 09:16 → 08-12 01:17).** The pull block
> earlier today is resolved (Joshua re-paired the phone). Full readout, integrity checks and
> statistics: **[E4_UPDATE_20260812.md](E4_UPDATE_20260812.md)**. Headline moves:
> - **Overall record 14–13** (26 archives = 14 W / 12 L, + 1 pre-archival unrecorded loss).
> - **`fixed_v1` epoch: n=23, W13/L10, margin +10.043 ± 5.627 (z +1.78)** — new batch alone
>   5–3, +11.750 ± 8.212.
> - ⚠️ **The farm anomaly DID NOT REPLICATE.** Paired farm margin +11.400 ± 3.588 (z +3.18) on
>   the first 15 → **+1.500 ± 3.929 (z +0.38)** on the new 8; the champion's farm points snapped
>   back from 14.0 to **21.4** pts/seat (its own corpus norm is 20.5) and it was zeroed in 0 of
>   8 (was 4 of 15). The pooled epoch figure (+7.957 ± 2.839) is now carried by the first half.
> - **Trend:** OLS slope on the full epoch **+1.215 pts/game (se 0.827, z +1.47)** — the prior
>   +2.58 read *halved* on new data. Not a learning rate.
> - Integrity: **26/26 replay exactly**, one duplicate `deck_seed` (the known 523563 pair, all
>   8 new seeds distinct ⇒ the on-device seedfix is behaviourally confirmed), and **`assists`
>   is still ABSENT in all 26** — E4 stays an assisted-human reference with the assist level
>   unstamped.
> - **EV-loss: all 8 graded, 8/8 acceptance gates PASS, 8/8 replay-verified.** The
>   grade-vs-outcome inversion held **5 more times (8 of 8 wins in the epoch; 11 of 11 graded
>   games overall)** — but he is out-graded by the *same* ~5× factor in his losses, so it is a
>   property of the stream, not of his wins. ⚠️ The human/champion **ratio is retired as a
>   headline**: its 2.90× → 5.12× rise is entirely the champion-seat denominator halving
>   (instrument noise floor); human ΔQ is flat at 0.055 → 0.054.
> - ⚠️ The phone no longer holds the two oldest archives; **this directory is the archive of
>   record**, the device is not a complete mirror.
>
> The per-game table further down covers archives through 2026-08-10 only; games 16–23 are
> tabulated in the readout.
>
> </details>
>
> ⚠️ **The per-game table and all statistics below this banner are FROZEN AT n=15
> (2026-08-10).** They are kept for provenance. **Games 16–23 are tabulated in
> [E4_UPDATE_20260812.md](E4_UPDATE_20260812.md); games 24–39 in
> [E4_UPDATE_20260817.md](E4_UPDATE_20260817.md)** — which carries the current record, the
> current trend read, and the current farm figures. Do not quote the n=15 tables below as
> current.

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
| `1786337185_638286.json` | 2026-08-10 | **125–71 W** | **+54, the fourth straight win** — during-play 77–35 (**+42**), unfinished 24–21 (+3), farms 24–15 (+9). **NEW `deck_seed` 638286 — no collision with anything in the ledger** (the seed-reuse bug did not fire here; a restart between games avoids it). Widest during-play margin he has ever taken off the champion (previous best +67 on 08-09 came with a −14 unfinished swing against him; this one is clean in all three components). Graded: champion mean ΔQ 0.01285, human 0.03145 (2.45×, z +1.97), human blunders 10 / champion 2. |

### EV-loss grading, the three 2026-08-09/10 games (`scripts/analyzer/ev_loss.py`)

All three graded at the archive's own budget k8×1376 = 11008, `fixed_v1` profile resolved from the
archive's **explicit `rules_profile` stamp** (the resolver's priority-1 route — see
`resolve_profile_name` in `ev_loss.py`). All replay-verified (`integrity.replay_scores_match:
true`, final scores match recorded exactly, `leaf_hash_matches_archive: true`) and all three
**acceptance-gate PASS** (`acceptance_gate.pass`): champion mean ΔQ 0.01061 vs null p95 0.07566
(game 1), 0.01894 vs 0.08958 (game 2), 0.01285 vs 0.06516 (game 3) — all well inside the
instrument's own noise floor.

| game | champion mean ΔQ | human mean ΔQ | ratio | z (human−champ) | human blunders | champion blunders |
|---|---:|---:|---:|---:|---:|---:|
| `1786325073` (140–84, +56) | 0.01061 | 0.03224 | 3.04× | +2.48 | 1 | 0 |
| `1786329790` (115–86, +29) | 0.01894 | 0.05087 | 2.69× | +2.38 | 6 | 1 |
| `1786337185` (125–71, +54) | 0.01285 | 0.03145 | 2.45× | +1.97 | 10 | 2 |

Exact tail: both seats played optimally in all three games (0.0 pts regret on every latched ply —
2 human / 2 champion plies in g1, 1 / 1 in g2, 1 / 1 in g3).

⚠️ **Do not read the blunder COUNTS across games.** The bucket thresholds are re-calibrated
per game from that game's own second-seed null (D2), so a game with a tighter null converts
more mid-sized ΔQ into "blunder": g3's null p95 is 0.06516 against g1's 0.07566, which is why
g3 shows 10 human blunders on a *lower* mean ΔQ than g2's 6. The cross-game-comparable
statistics are the mean ΔQ and the human-vs-champion ratio on the same board.

**The grade-vs-outcome inversion holds a third time.** g3 is his second-biggest win and his
*second-best* grade of the three (ratio 2.45×, the smallest gap of the set) — but the gap is
still positive and still ~2σ, i.e. the champion out-played him move-for-move in the game he won
by 54. Artifacts: `../analyzer_evloss_20260805/EV_LOSS_1786325073_523563.{json,md}`,
`../analyzer_evloss_20260805/EV_LOSS_1786329790_523563.{json,md}`,
`../analyzer_evloss_20260805/EV_LOSS_1786337185_638286.{json,md}` (g3 graded on the laptop,
pre-seam checkout — same leaf hash `a36d2e15a3b3d71d`, same 11008 budget). No strength claim, no
`governance/PRODUCTION.yaml` change.

## The fixed_v1 epoch at n=15: a positive lean, and a four-game winning streak

Fifteen games under the current rules (2026-08-05 → 08-10). **W 8 / L 7, winrate 0.533.**
Margins (Joshua − champion): −7, −6, +44, −10, −14, +3, +38, −28, +3, −38, −9, +22, +56, +29, **+54**.

**Streak, verified against archive `finished_at` timestamps (not prose): the last four archived
games are all wins** — `1786243458` (+22), `1786325073` (+56), `1786329790` (+29), `1786337185`
(+54) — and the **last ten are 7 W / 3 L** (the three losses: `1786116818` −28, `1786142936` −38,
`1786242001` −9). Joshua's "4 in a row, 7 of the last 10" is exactly right.

⚠️ **Games 13 and 14 (`1786325073_523563`, `1786329790_523563`) share `deck_seed` 523563** — see
the note on that row above. Their margins are correlated through one common deck effect,
so the n=15 se below is **very slightly optimistic** (15 games, not 15 independent draws). The
rigorous per-game read for those two is the **deck-adjusted residual** below, not the raw margin.
Game 15 (`638286`) is an independent draw — no seed collision.

✅ **The seed-reuse bug is fixed and shipped (2026-08-10).** `27cd337` rerolls the new-game seed
after every `newGame()`; built from HEAD and installed to the phone as an update
(apk sha256 `7dfb40b4…`, hash-verified against the on-device `base.apk`; all 16 archives survived).
**The "restart the app between games" workaround is retired** — games archived from 2026-08-10 on
draw a fresh deck per rematch by construction. Games 1–15 above are unaffected and keep the
correlated-pair handling described in this section.

| statistic | mean | se | z |
|---|---:|---:|---:|
| **TOTAL margin** | **+9.13** | 7.63 | **+1.20** |
| during play | +1.67 | 7.75 | +0.22 |
| unfinished features | −3.93 | 2.97 | **−1.33** |
| **farms** | **+11.40** | 3.59 | **+3.18** |

The three recent wins pull the total from dead-even (−0.17 at n=12) to +5.93 at n=14 to **+9.13 at
n=15** — a positive lean that is still only **z +1.20**, i.e. **not a distinguishable shift** and
nowhere near a claim. The during-play component crossed zero for the first time (−1.21 → +1.67)
purely on game 15's +42, and at z +0.22 that is noise, not a trend. The farm component stays the
only one past 3σ. ⚠️ **Unpaired, one seat, not fully
independent (shared-deck note above), and the human is an ASSISTED and IMPROVING player**
(BACKLOG 2026-07-30 assists entry) — a description of fifteen games, NOT a rating. Phase-C
sizing for a real read: **193 seat-swap deck-paired games at true wr 0.55, 48 at 0.60.**
A four-game winning streak has probability 1/16 under a fair coin and is not evidence of a
change in strength at this n.

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

### Deck-adjusted residual for the 638286 game (2026-08-10)

Same informal single-deck extension, run on the **laptop** (`scripts/e4_deck_baseline.py --k 8
--workers 10 --rust-threads 1`, 2.6 min wall, 8/8 games finished, provenance identical to the
closed n=12 corpus — `champion_leaf_hash a36d2e15a3b3d71d`, `total_sims_of_record 11008`,
`rules_profile fixed_v1`). Self-play margins (seat0 − seat1) on deck `638286`:
+11, −12, −8, +14, +40, +41, +9, −37 → **d̂ = +7.25 ± 9.29** (sd 26.28).

| game | margin | d̂ | **residual (margin − d̂)** |
|---|---:|---:|---:|
| `1786337185` (125–71, +54) | +54 | +7.25 | **+46.75** |

**Mildly seat-0-favourable but not distinguishable from neutral** (+7.25 with se 9.29 — this deck
has the widest self-play spread in the whole ledger, sd 26.28 vs the corpus's 21.49, so K=8 prices
it poorly). Taking the point estimate at face value, **+46.75 is the second-largest residual on
record**, behind `523563`'s +55.5 and ahead of `627623`'s +37.12. Even at the pessimistic end of
the d̂ interval (d̂ = +16.5, one se up) the residual stays above +37 — the win is not deck-carried
on any reading of the baseline. Raw games: `../e4_deck_baseline_20260807/selfplay_638286.jsonl`.

### Deck luck priced out of that −0.17 (2026-08-08)

> **Scope note (2026-08-09, extended 2026-08-10):** the subsection below is the CLOSED n=12
> formal control-variate experiment, unchanged. The two single-deck residual checks above
> (`523563`, `638286`) are separate, informal extensions covering only the three newest games'
> decks; they are not folded into the β̂/ICC estimates below.

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
| 14 | 13.93 (se 3.34) |
| **15** | **14.00** (se 3.11; its own self-play corpus = 20.5) |

The 2026-08-05 "the champion is starved of farms (11.0 vs 20.5)" claim was a 3-game artifact and
was corrected on 08-07 to 19.5, then to 14.8 at n=12, 13.93 at n=14; at n=15 it is 14.00, i.e.
**~2.09σ below its corpus norm and still moving**. Do not quote any single value of this as a fact.
What IS stable at n=15 is the *paired* farm margin above (+11.40, z +3.18) and one concrete oddity:
the champion scores **zero** farm points in **4 of 15** games (unchanged from n=12 — none of the
three newest games is a champion-zero-farm game: 12, 6 and 15 pts), against a corpus p5 of 0. The
farm-war discriminator that
this motivated returned INCONCLUSIVE
([FARMWAR_READOUT](../analyzer_evloss_20260805/FARMWAR_READOUT.md)), so nothing downstream depends
on the unstable figure.

Joshua's overall E4 record: **9–10** (18 archived games: 9W–9L, direct recount of every archived
game's recorded `scores`, plus 1 pre-archival unrecorded loss — game 1 predates the archiving
feature, not an archive bug); the fixed_v1-epoch record is **8–7**. Joshua wins the farms in
**12 of 15** fixed_v1 games and averages 25.40 farm pts/seat against the
corpus norm of 20.5. ⚠️ **The luck floor is real** — champion-vs-greedy paired-deck play leaves
~6.25% pooled luck in the base game — so at n=15 unpaired this is a description, not a rating.

## ⚠️ Grading-epoch boundary at 2026-08-01 (the rust-port flips)

Games archived BEFORE the 2026-08-01 app build grade against the **k4×688 mobile
carve-out** on the **walled engine grid** with the **random start tile** (the two games
above). Games from the 2026-08-01 build onward carry three simultaneous changes, each
recorded in the archive payload: **budget = the champion of record k8×1376** (rust
backend; the carve-out is closed — see DECISIONS 2026-08-01), **start_rule = retail**,
and — from the recentring build — **grid_rule = centered18**. Cross-epoch E4 comparisons
must condition on these fields; per-game self-consistency is unaffected (both seats play
the same rules in any one game).
