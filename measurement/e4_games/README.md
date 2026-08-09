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

## The fixed_v1 epoch at n=12: DEAD EVEN on points, and a stable component signature

Twelve games under the current rules (2026-08-05 → 08-07). **W 5 / L 7, winrate 0.417.**
Margins (Joshua − champion): −7, −6, +44, −10, −14, +3, +38, −28, +3, −38, −9, +22.

| statistic | mean | se | z |
|---|---:|---:|---:|
| **TOTAL margin** | **−0.17** | 7.06 | **−0.02** |
| during play | −8.17 | 6.39 | −1.28 |
| unfinished features | −3.75 | 3.59 | −1.05 |
| **farms** | **+11.75** | 4.42 | **+2.66** |

**The total is as close to zero as a number can get**, and it is not one blowout cancelling
another — it is a *structured* draw: he loses the engine room (during play, unfinished) and wins
the fields by more than enough to pay for it. The farm component is the only one past 2σ.
⚠️ **Unpaired, one seat, no deck pairing, and the human is an ASSISTED and IMPROVING player**
(BACKLOG 2026-07-30 assists entry) — a description of twelve games, NOT a rating. Phase-C
sizing for a real read: **193 seat-swap deck-paired games at true wr 0.55, 48 at 0.60.**

## ⚠️ Champion farm points against Joshua — an estimate that will not sit still

| n | champion farm pts/seat vs Joshua |
|---|---|
| 3 | 11.0 |
| 6 | 19.5 |
| **12** | **14.8** (se 3.8; its own self-play corpus = 20.5) |

The 2026-08-05 "the champion is starved of farms (11.0 vs 20.5)" claim was a 3-game artifact and
was corrected on 08-07 to 19.5; at n=12 it is 14.8, i.e. **~1.5σ below its corpus norm and still
moving**. Do not quote any single value of this as a fact. What IS stable at n=12 is the *paired*
farm margin above (+11.75, z +2.66) and one concrete oddity: the champion scores **zero** farm
points in **4 of 12** games, against a corpus p5 of 0. The farm-war discriminator that this
motivated returned INCONCLUSIVE ([FARMWAR_READOUT](../analyzer_evloss_20260805/FARMWAR_READOUT.md)),
so nothing downstream depends on the unstable figure.

Joshua's overall E4 record: **5–10** (game 1 predates the archiving feature — unrecorded by
design, not an archive bug); the fixed_v1-epoch record is **5–7**. Joshua wins the farms in
**9 of 12** fixed_v1 games and averages 26.5 farm pts/seat against the corpus norm of 20.5.
⚠️ **The luck floor is real** — champion-vs-greedy paired-deck play leaves ~6.25% pooled luck
in the base game — so at n=12 unpaired this is a description, not a rating.

## ⚠️ Grading-epoch boundary at 2026-08-01 (the rust-port flips)

Games archived BEFORE the 2026-08-01 app build grade against the **k4×688 mobile
carve-out** on the **walled engine grid** with the **random start tile** (the two games
above). Games from the 2026-08-01 build onward carry three simultaneous changes, each
recorded in the archive payload: **budget = the champion of record k8×1376** (rust
backend; the carve-out is closed — see DECISIONS 2026-08-01), **start_rule = retail**,
and — from the recentring build — **grid_rule = centered18**. Cross-epoch E4 comparisons
must condition on these fields; per-game self-consistency is unaffected (both seats play
the same rules in any one game).
