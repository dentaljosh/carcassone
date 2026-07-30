# Competitive Carcassonne time controls — and what our engine can legally spend

> **⚠️ STATUS AMENDED 2026-07-30 (audit F9) — THE FORMAT RESEARCH STANDS; THE "WHAT WE CAN SPEND" HALF IS SUPERSEDED.**
> **Every per-move cost and %-of-clock figure in this doc prices the search SINGLE-STREAM — an assumption
> the doc never states.** The k determinizations are independent until the pooled-Q argmax, so
> **CL-071 (2026-07-29)** runs them on `parallel_workers=8`: measured **6.370×**, **30/30 action-identical
> roots**, transport 7.24 ms/move. The 4× teacher (11008) therefore costs **~20.6% of the 900 s clock**
> — 2.1595 s/move × 70 decisions + the **34 s exact-K solve, which is NOT parallelized** (the commonly
> quoted 14.3–17.4% band divides that solver term by the speedup; see CL-071 counterevidence (4) for the
> reconciliation) — and **it was promoted to deploy champion**. So "compute is a knob for UNCLOCKED play
> only" is **false as of 2026-07-29**. Still true: the **sequential fallback** (Android/Chaquopy, daemonic
> eval-farm parents) is the same player 6.37× slower, so the mobile profile stays at k4×688.
> **The time-control research itself — 15 min/player/game, sudden death, no increment, ~70 searched
> decisions, the 34 s K=2 solve — is unchanged and remains the authority.**
>
> **STATUS: RESEARCH COMPLETE 2026-07-26 (delegated web research, sources below).**
> **Bottom line: the competitive standard is 15 minutes per player per game, sudden death,
> no increment. Only the DEPLOY CHAMPION (2.8 s/move, 26% of clock) is comfortably legal.
> The +50-elo 4× budget lever (11.2 s/move) sits at 91% of clock and the 8× config at 178%
> — i.e. the strength that CL-060 showed is purchasable with compute CANNOT be spent under
> tournament conditions.** This is a scope-level constraint on the superhuman goal, not an
> ops detail.

## 1. The time controls (sourced)

| Event | Year | Format | Time control | Source |
|---|---|---|---|---|
| **Carcassonne World Championship** (Hans im Glück / Spielezentrum) | current (page updated 2026-04-14; identical text archived 2021) | 2-player tables, 6 Swiss + QF/SF/F, physical | **15 min per player per game, chess clocks, sudden death** (no increment). Running out = loss even if ahead on points | [carcassonne-meisterschaft.de/en/tournamentrules.htm](https://carcassonne-meisterschaft.de/en/tournamentrules.htm) |
| WC — historical variation | 2021 archive only | as above | Same 15 min, plus a clause (since REMOVED) giving more clock time for the oversized-board final | [web.archive.org 2021-06-23](http://web.archive.org/web/20210623144437/https://carcassonne-meisterschaft.de/en/tournamentrules.htm) |
| German Championship final (22. DM, Herne) | 2024 | 2-player, 6 Swiss + QF/SF/F | **15 min per player**, chess clocks, timeout = loss | [inkognito12.jimdofree.com](https://inkognito12.jimdofree.com/brett-u-kartenspiele/carcassonne/) |
| German Championship final | 2014 | same structure | **18 min per player** — i.e. the control TIGHTENED over the decade | [DM 2014](https://inkognito12.jimdofree.com/brettspiele/dm-carcassonne-2014) |
| German *qualification* tournaments | 2018/2020/2021 | mostly **4-player**, points 5-3-2-1 | **No clock rule at all** in the official PDFs | [CC21 PDF](https://carcassonne-meisterschaft.de/media/uploads/2021/01/CC21-Turnierregeln_2021neueVersion1.pdf) |
| US National Championship (BGA, WC qualifier) | 2026 | 2-player, 6 Swiss + top-8 | **15 min per player**, BGA "fixed time limit" (no increment) | [USCC-2026 PDF](https://drive.google.com/file/d/1Ji84pzsNpT-zNSr04SlE1UllG6IsJZ1D/view) |
| MSO Carcassonne (WC qualifier) | 2025 | 2-player, 7 rounds + playoffs, BGA | **15:00 per player** | [MSO 2025 PDF](https://mindsportsolympiad.com/wp-content/uploads/2025/01/Carcassonne-2025.pdf) |
| Carcassonne Champions League | 2026 | 2-player BGA, Bo3/Bo5 | **"Game maximum duration – 30 mn (15:00 per player)"** | [carcassonne.gg/CCL-2026-Rules](https://carcassonne.gg/CCL-2026-Rules/) |
| Belgian Championship (BCL) | 2026 | 2-player, Bo3 | **15 min per player** | [carcassonnebelgium.weebly.com](https://carcassonnebelgium.weebly.com/introduction--rules-bcl-2026.html) |
| Czech "mistrovství republiky" (Deskohraní) | 2024 | 2 per table, chess clocks | **25 min per player** — but a HOUSE VARIANT (3-tile hand, draft, bonus monasteries) ⇒ almost certainly a domestic event, not the HiG-sanctioned qualifier | [deskohrani.cz](https://deskohrani.cz/cgi/mso/index.pl?turnaj=mcr&text=uvod.htm&telo=propozice.pl&rok=2024&jazyk=cs&hra=car) |
| BGA clock mechanics | current | — | Tournament mode = **"fixed time limit: you get an amount of time at the beginning, and there is no additional time during the game"** | [BGA FAQ](https://en.boardgamearena.com/faq) · [BGA Game clock](https://en.doc.boardgamearena.com/Game_clock) |

**Format + rule set CONFIRMED to match our locked scope:** 2-player everywhere; **base game only**
(WC: *"All games are played with the basic Carcassonne game only"*); **Farmers ARE included**, with
international scoring (3 pts per adjacent completed city, the "3rd field rule", 2-tile cities = 4 pts).

**Slow play:** the only sanction is losing on time — no chess-style arbiter warnings. ⚠️ **Humans may
legally think on the opponent's clock** (WC rules explicitly permit choosing and looking at your next
tile during the opponent's turn), which roughly doubles a human's effective budget relative to an
engine that does not ponder.

## 2. What our engine can spend

**Move accounting (resolved from our own records, `cost_probe_unloaded_w2`):** a game logs
`moves = 144` and the base game has **72 tiles** ⇒ **exactly 2.0 searched decisions per tile**
(place tile, then place meeple). So ~36 *turns* but **~72 searched decisions per player**
(`champ_prefix_moves` 70 + `champ_exact_moves` 2). The per-move costs below are **per decision**.

900 s clock ÷ ~70 decisions ⇒ **~12.9 s available per decision.** Including the K=2 endgame solve,
which also runs on the clock:

| config | elo vs deploy | search | solver | total | % of clock | verdict |
|---|---:|---:|---:|---:|---:|---|
| **deploy champion k4×688** (2752 sims) | 0 | 3.3 m | 34 s | **3.8 m** | **26%** | ✅ comfortable |
| distilled net k4×688 (CL-067) | +35.7 | 13.7 m | 50 s | 14.5 m | **97%** | ⛔ knife-edge |
| **4× teacher k8×1376** (11008) | **+49.9** | 13.1 m | 34 s | 13.6 m | **91%** | ⛔ knife-edge |
| 8× k16×1376 (22016) | +35.6 | 26.1 m | 34 s | 26.7 m | **178%** | ⛔ loses on time |

Per-move costs are the UNLOADED (W=2) measurements — the honest deployment regime, since the
evaluator is `make_remote_single_evaluator` (k=1/request) and the worker blocks, so a deployed agent
gets no batching. See `results.csv distill_strong_iter03_cost_probe_unloaded_w2`.

## 3. Consequences (the reason this doc exists)

1. **⛔ The compute lever is unavailable where it matters.** CL-060 established ~+50 elo is
   purchasable at 4× budget and that the curve then plateaus. This says that +50 cannot be spent in
   a clocked game: 91% of a sudden-death clock with no increment loses to any variance. **Compute is
   a knob for UNCLOCKED play only.** Anyone citing CL-060's +50 as progress toward the superhuman
   goal must now also cite this constraint.
2. **The deploy champion is the only comfortably legal configuration we have** (26%). That is a
   point in favour of the current production config, not a limitation of it.
3. **This retroactively softens CL-067's failure.** The distilled net was refuted on cost
   (4.24× per move, and the raw teacher beats its own distillation at equal cost) — but at 97% of
   clock it was never tournament-deployable either way.
4. **Sub-2752 measurements matter for MARGIN, not completeness.** If ~1376 sims costs only ~−20 elo
   it halves clock usage to ~13%, buying a large buffer against time trouble. The sub-2752 region is
   currently **unmeasured at production width** — the only low-budget ladder (CL-046 D0: +27.9/+61.4
   /+81.4/+149.3 at 800/1600/2752/5504) is `k_dets=8`, and k8→k4 alone is worth ~+66 elo at 2752
   (CL-054: k8×344 +69.5 vs k4×688 +136.0, same band), so its LEVELS do not transfer. Its SHAPE
   (~−27 to −34 elo per halving below deploy) is indicative only.
5. **Pondering is a legal, unexploited lever** — see [LEVER_INDEX](../LEVER_INDEX.md). Humans use the
   opponent's clock by rule; we do not. At 26% clock usage the champion has the headroom.

## 4. What could NOT be established

- Whether the **WC** has ever used a control other than 15 min (page only archived to 2021, already 15).
  The 18→15 tightening is documented for the GERMAN final via a club page, not an official source.
- **Any increment/delay at the WC** — the rules describe a flat 15-minute account and never mention
  increment, so sudden death is inferred **from silence**, not stated.
- **UK** and **Polish** national time controls (rules PDFs unreachable). MSO runs the UK event and uses
  15:00 online, so 15 min is a plausible guess — an inference, not a documented rule.
- Which Czech event is the sanctioned WC qualifier (the 25-min one plays a house variant).
- **Exact BGA real-time clock numbers per speed tier** — BGA deliberately does not publish them
  (auto-tuned by an algorithm targeting a time-penalty rate), so "Real-Time Slow" cannot be converted
  to minutes.
- Measured breakdown of deliberation vs physical tile handling within the ~30-min game.
