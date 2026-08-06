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

Joshua's overall E4 record: **1–3** (game 1 predates the archiving feature — unrecorded by
design, not an archive bug). ⚠️ **n=4 and the luck floor is real** — champion-vs-greedy
paired-deck winrate leaves ~6.25% pooled luck in the base game, and the E4 protocol prices
the champion at wr 0.55 against a strong opponent, so **one win is not a rating claim**.
It is a milestone and a datum, not evidence of parity.

## ⚠️ Grading-epoch boundary at 2026-08-01 (the rust-port flips)

Games archived BEFORE the 2026-08-01 app build grade against the **k4×688 mobile
carve-out** on the **walled engine grid** with the **random start tile** (the two games
above). Games from the 2026-08-01 build onward carry three simultaneous changes, each
recorded in the archive payload: **budget = the champion of record k8×1376** (rust
backend; the carve-out is closed — see DECISIONS 2026-08-01), **start_rule = retail**,
and — from the recentring build — **grid_rule = centered18**. Cross-epoch E4 comparisons
must condition on these fields; per-game self-consistency is unaffected (both seats play
the same rules in any one game).
