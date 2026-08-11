# Unbranded Tile-Laying Game — Store Market Census

**Date:** 2026-08-05
**Type:** Market research / read-only scrape. No engineering implications.
**Question being answered:** If we redraw the art and drop the Carcassonne name, what does organic
store discovery actually deliver? Read off apps that have already run the experiment.

**Status of this document:** Unplaced research artifact. Not registered in `docs/INDEX.md`,
`DECISIONS.md`, `STATUS.md`, or `governance/`. Placement is the owner's call.

**Convention used throughout:** **FACT** = read directly off a store or analytics page.
*INFERENCE* = derived by me, with arithmetic shown. Anything not marked is a FACT.

---

## 1. Headline

**The best outcome any unbranded Carcassonne-like has ever achieved on mobile is roughly 50,000–100,000
lifetime installs and an estimated $5,000–$13,000 net revenue — accumulated over eleven years.**
That is the ceiling, not the median. The median unbranded tile-layer on the app stores sits at about
**5,000 installs and 38 ratings**, and roughly **29% of the ones that ever shipped are dead** (no update
in 2+ years, or delisted outright). The entire unbranded category across both stores is **seven apps**,
of which two are corpses and two more have single-digit-to-double-digit rating counts. I set out to find
eight or more qualifying clones and could not — **that emptiness is the finding.**

**But the ceiling is on the wrong platform.** On Steam, the unbranded tile-layer *Dorfromantik* has
~820,000 owners at a never-discounted $13.99 (*INFERENCE*: ~$8.0M net, arithmetic in §6) — which is
**several times what the officially-licensed Carcassonne has earned across all its channels combined.**
The pattern in the data is not "the brand buys installs." It buys roughly 2× the installs. What it
actually buys is **the right to charge money on mobile**: the licensed app sells at $5.99 plus $3
expansions, while *every single* unbranded mobile tile-layer that is still alive is free, because nobody
pays upfront for an unknown board game. On Steam that handicap does not exist, because nobody expects a
Steam indie to be licensed.

**On AI strength:** yes, users notice, and there is one direct data point that they will pay for it —
a $0.99 "Hard Computer player" IAP with a 5-star review saying *"That's definitely worth it. Medium was
too easy for me."* Weak AI is the single most repeated complaint across the free clones, and the
*licensed* app's Steam forum has standing threads titled "Terrible AI" and "illogical AI." Details in §5.

---

## 2. The distribution — full census

### 2a. Qualifying unbranded tile-layers on Google Play / App Store

Sorted by estimated installs descending. Google Play publishes install **brackets**, not exact counts;
the "installs" column below is the **bracket floor** as reported by AppstoreSpy, so true installs sit
between the floor and the next bracket up. **Apple publishes no install counts at all** — for iOS rows,
rating count is the only proxy and the installs column is my inference (method in §3).

| # | App | Publisher | Store | Installs | Ratings | Stars | First release | Last update | Price model | Online MP | AI difficulty | Reviews say AI weak? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Farm Builder 2D (Farmassone) | LAN-GAMES EOOD / BoardGamesOnline.net | Play | **50,000+** | **905** | 3.7 | 2015-06-19 | 2026-01-02 | free + ads + IAP | Yes | Yes ("robots", easy/med) | **Yes** |
| 2 | War of Carcassonne board Games | PlayStal Games | Play | **50,000+** | **553** | 3.0 | 2021-07 | 2025-11 | free + ads + IAP | Yes (to 4p) | Yes ("improved AI") | Not found |
| 3 | Carcassone – Tile Strategy | Awoken Industry | Play | **5,000+** | **128** | 3.9 | 2025-03-22 | 2026-07-22 | free + IAP | No (offline) | Yes (named bots) | Not found |
| 4 | Farmassone | LAN-GAMES EOOD | iOS | *~3,800 (inf.)* | **38** (US) | 3.8 | ~2015 (unconf.) | 2025-11-08 | free | Yes | Yes | **Yes** |
| 5 | Castles board game | Bastiaan Modderkolk | iOS | *~500 (inf.)* | **25** | 4.8 | 2014-12-10 | **2020-01-06 ☠** | $0.99 + $0.99 IAP | Yes (Game Center) | **Yes — Hard AI is a paid IAP** | **Yes** |
| 6 | Seizer | Seizer LLC | Play | **100+** | not shown | — | 2025-09-15 | 2026-03-02 | free, no IAP | Yes (RT + async) | Yes ("intelligent bots") | No reviews mention it |
| 6 | Seizer | Seizer LLC | iOS | *~500 (inf.)* | **5** | 4.2 | 2025-08-02 | 2026-02-28 | free, no IAP | Yes | Yes | No reviews mention it |
| 7 | Placium: Tile Tactics Strategy | Sinopsis | Play | **10+** | ~0 | n/a | 2026-01-08 | 2026-07-29 | free + ads + IAP | Yes | Yes (solo vs AI) | n/a — no reviews |
| — | Seven Castles | unknown | iOS | **DELISTED ☠** | — | — | ~2015 | — | — | Yes | Yes | — |

**Count: 7 live-or-recently-live unbranded apps, 2 of them dead (Castles, Seven Castles) = 29% death rate.**
Seizer and Farmassone each ship on both stores and are counted once.

**Median of the set** (by rating count: 905, 553, 128, 38, 25, 5, ~0) = **38 ratings**.
**Median Play install bracket** (50K, 50K, 5K, 100, 10) = **5,000 installs**.

### 2b. The unbranded scene that is NOT on the app stores

This is where the category actually lives, and it is a material finding: four separate unbranded
Carcassonne-likes launched as **browser games with no app-store presence at all.**

| Game | URL | Platform | Model | Notes |
|---|---|---|---|---|
| TileLord | tilelord.com | Web only | Free | **"over 1,000 games a week"** (Dec 2025) — the only public traffic number anyone in this category has published. Grew out of /r/Carcassonne. |
| TileKingdom | tilekingdom.io | Web only | Free, no paywall | Advertises **"a dedicated Monte Carlo Tree Search (MCTS) engine and one of the strongest AI opponents available for a Carcassonne-style game"** |
| Cartoria | cartoria.online | Web only | Free | Carcassonne-style, SEO-led ("Carcassonne Alternative Online") |
| Seizer | seizer.io | Web + both stores | Free | Launched early 2025, Seizer LLC, ELO ladder + Discord |

*INFERENCE:* these devs went web-first because the app stores offer this category essentially no organic
discovery (see the 0.6% board-category install rate in §3), whereas a web game can rank on the Google
search term "carcassonne online free" — which is generic search demand for the brand, capturable without
a license. Every one of these four sites is SEO-built around the word "Carcassonne."

Seizer publishes an explicit disclaimer worth noting for the owner's own legal posture:
> *"an independent game… no association with, affiliation with, or endorsement from the board game
> Carcassonne or its creators."*

### 2c. What I rejected, and why

**Total rejected: 60+.** The iOS sweep alone rejected **47** apps; my Play sweep rejected at least 13 more.

| Reason | Count | Examples |
|---|---|---|
| Match-3 / triple-match / "tile match" puzzlers | ~20 | Tile Match, Tile Club, Tile Story, Tile Master Pro, Tile Family, MatchUp Tile Game, Tile City – Triple Match, Matching Tiles: City Scape |
| City builders / 4X / sims that merely use tiles | ~14 | Landover (Catan-style hex, the #1 "Carcassonne alternative" on AlternativeTo — it is not one), Catan Universe/HD, **Tileburg** (solo city sim), Suburbia, Designer City, Pocket City, Forge of Empires |
| Other board games, no edge-matching or region-claiming | ~11 | Sagrada, 7 Wonders, Root, Wingspan, Spirit Island, Dune: Imperium |
| Score-counter / tile-counter **utilities** (not games) | ~8 | Carcassonne Tiles Counter, Tile Tracker, Carcassonne Scoreboard, Carcassonne Tile Tracker, Meeple Count |
| **Carcassonne city-tourism apps** | 5 | Carcassonne Interactive (10K+ installs, 2.7★ — a *municipal tourist office* app), Carcassonne Travel & Explore, Carcassonne Map and Walks, Ville de Carcassonne, Carcassonne 3D (10+ installs, $3.99 — a 3D walkthrough of the actual city) |
| Azul-style tile *drafting* (pattern-building, no edges or claiming) | 3 | Tiles Mosaic Board Game (**4.6★, 1,200 ratings** — 4× the official Carcassonne's iOS ratings), Tile Wall Strategy, Tiles Azulejos |
| Mahjong / domino / rummy / okey tile games | ~4 | Okey, Rummy, Dominoes, Dragon Castle |
| Stack-and-clear / abstract adjacency puzzlers | 3 | tileforge, Tile Tactics (nativesoft — symbol adjacency, no claiming), Tile Tactics: 2048 |

**Note on search pollution:** the query "tile laying game" on Google Play returns essentially **zero**
qualifying results — the first ten hits are all match-3. The single most productive query by a wide
margin was the brand term **"carcassonne"** itself, which is exactly what §7 predicts: the clones that
exist survive by keyword-squatting the brand, not by ranking on generic mechanic terms.

---

## 3. Method — installs and revenue

### 3a. Review-to-install ratio

Published benchmark, cited: **AppsFlyer** — *"Ideally, you'll convince at least 1% of users to leave a
rating."* ([source](https://www.appsflyer.com/blog/tips-strategy/app-ratings-reviews/)). A second source
puts it lower — *"less than 1% of users will ever leave a rating or review"*
([CS Agents](https://cs-agents.com/blog/appreviews/)). **Appbot** separately measured 3,867 apps and found
**36.6 ratings per written review** ([source](https://appbot.co/blog/relationship-ratings-reviews/)) —
important because "rating count" and "review count" are different numbers and this report uses rating counts.

**I cross-checked that 1% figure against this dataset rather than importing it blind:**

| App | Ratings | Play install bracket | Implied ratio |
|---|---|---|---|
| Farm Builder 2D | 905 | 50,000–100,000 | 905 ÷ 50,000 = **1.8%** … 905 ÷ 100,000 = **0.9%** |
| War of Carcassonne | 553 | 50,000–100,000 | 553 ÷ 50,000 = **1.1%** … 553 ÷ 100,000 = **0.6%** |
| Carcassone – Tile Strategy | 128 | 5,000–10,000 | 128 ÷ 5,000 = **2.6%** … 128 ÷ 10,000 = **1.3%** |

**Ratio adopted for FREE apps: 1.0%, range 0.6%–2.6%.** This is derived from the actual apps in the
census and happens to match the AppsFlyer benchmark.

**Paid apps rate far higher** and must not use the same number. Carcassonne: Tiles & Tactics has
**11,109 ratings** against a 100,000+ bracket (AppBrain estimates 240,000 downloads) →
11,109 ÷ 240,000 = **4.6%**, or ÷ 100,000 = **11%**. **Ratio adopted for PAID apps: 5%.**
*INFERENCE:* paid buyers are far more likely to rate; treat the free and paid populations separately.

**iOS install inference** = rating count ÷ 1% (free) or ÷ 5% (paid). So Seizer's 5 iOS ratings →
5 ÷ 0.01 = *~500 installs*. Castles (paid $0.99) 25 ratings → 25 ÷ 0.05 = *~500 installs*. Farmassone
38 US ratings → 38 ÷ 0.01 = *~3,800 US installs* (US storefront only — see §7).

### 3b. Payer conversion and ARPPU

Board/card/word is reported as the **lowest-converting** mobile game genre — MAF/Mistplay attributes this
to genre saturation. I could not obtain a genre-specific payer-conversion percentage from a primary
source (see §7), so I use a deliberately conservative **1.0% payer conversion** and **$5 ARPPU** for
free tile-layers, and state that assumption openly rather than laundering it.

Store cut: **30%** (both stores; Google's 15% small-business tier would improve these numbers, which
makes the estimates conservative).

### 3c. The discovery number that matters most

**AppTweak, US App Store, 2025: the `Games – Board` category has the LOWEST install rate of any
category on the App Store — 0.6%, against a 3.8% all-category average.**
([source](https://www.apptweak.com/en/aso-blog/average-app-conversion-rate-per-category))

That is a direct, sourced measurement of the exact thing this report was commissioned to find. A user
who browses or searches into the board-games category converts to an install at **one-sixth** the rate
of the average category. Organic store discovery for a board game is not merely weak in absolute terms —
it is the worst-performing category Apple has.

---

## 4. Estimated revenue per app

All arithmetic inline. All figures below are *INFERENCE* unless the input is bolded as a FACT.

**#1 Farm Builder 2D / Farmassone** — the ceiling case. **50,000+ Play installs** (bracket) + *~3,800 iOS*.
Free + ads + IAP. Live **2015-06-19 → 2026-01-02 = 10.5 years**.
- Take midpoint installs 75,000 (Play) + 4,000 (iOS) ≈ 79,000.
- IAP: 79,000 × 1.0% payers = 790 payers × $5 ARPPU = $3,950 gross × 0.70 = **~$2,800 net**
- Ads: at $0.05–$0.20 lifetime ad revenue per install (board games have low eCPM and low session counts):
  79,000 × $0.05 = $3,950 … 79,000 × $0.20 = $15,800, × 0.70 = **~$2,800–$11,000 net**
- **Lifetime total ≈ $5,600–$13,800 net, over 10.5 years ≈ $530–$1,300/year.**

**#2 War of Carcassonne** — **50,000+ installs**, **553 ratings**, **3.0★**, free + ads + IAP,
**2021-07 → 2025-11 = 4.4 years**.
- 75,000 × 1.0% = 750 payers × $5 = $3,750 × 0.70 = **~$2,600 net IAP**
- Ads: 75,000 × $0.05–$0.20 = $3,750–$15,000 × 0.70 = **~$2,600–$10,500 net**
- **Lifetime ≈ $5,200–$13,100 net, over 4.4 years ≈ $1,200–$3,000/year.**

**#3 Carcassone – Tile Strategy** — **5,000+ installs**, **128 ratings**, launched **2025-03-22**
(1.4 years), free + IAP, actively updated (last update **2026-07-22**).
- 7,500 × 1.0% = 75 payers × $5 = $375 × 0.70 = **~$260 net lifetime.**
- **This is the single most relevant comparator in the report**: a competently-built, actively-maintained,
  brand-new unbranded Carcassonne clone with named AI personalities. Sixteen months in, it has earned
  roughly the price of a nice dinner.

**#4 Seizer** — **100+ Play installs**, **5 iOS ratings**, free, **no IAP found on either store**.
- **Revenue: $0 by construction.** Launched Aug–Sep 2025, actively updated through Mar 2026, markets
  itself as "the #1 Free Online Alternative to Carcassonne," has a web version, an ELO ladder and a
  Discord — and after a year has **five iOS ratings**. This is the clearest single measurement of what
  unbranded organic store discovery delivers when you do everything right.

**#5 Castles board game** — $0.99 paid + $0.99 Hard-AI IAP, **25 ratings**, dead since 2020-01-06.
- 25 ÷ 5% = *~500 sales* × $0.99 × 0.70 = **~$350 net**, plus some fraction buying the $0.99 AI IAP.
- **Lifetime under ~$600.**

**#7 Placium** — **10+ installs**, launched 2026-01-08, ads + IAP. **Revenue ≈ $0.**

**Median unbranded app lifetime revenue: *~$300–$3,000*. Ceiling: *~$14,000*, spread over a decade.**

---

## 5. Branded comparators — and the cost of dropping the IP

### 5a. Carcassonne: Tiles & Tactics (Twin Sails Interactive, ex-Asmodee Digital)

| Metric | Google Play | App Store | Steam |
|---|---|---|---|
| Installs | **100,000+** bracket (AppBrain est. **240,000**) | not published by Apple | *~88,000–200,000 owners (inf.)* |
| Ratings / reviews | **11,109** ratings | **260** ratings | **1,959** reviews |
| Stars / score | **2.04 / 5** | **2.5 / 5** | **83%** all-time; **recent 53% (13)** |
| Price | **$5.99** + IAP $0.99–$3.49 | **$4.99** + 5 expansions $1.99–$2.99 | **$9.99** (currently **$2.99**, −70%) + 5 DLC |
| First release | 2017-11-29 | 2020-03-30 | 2017-11-29 |
| Last update | ~2025-07-01 (SDK-36 compliance bump only) | **2021-08-04 — 5 years stale ☠** | — |
| Online MP | Yes, async cross-platform, up to 6p | Yes | Yes |
| AI difficulty levels | Yes — 4 tiers, top tier "Conqueror AI" | Yes | Yes |

Play rating distribution: **6,754 one-star** vs 1,729 five-star out of 11,109. Androidrank shows
**0% rating growth over both 30 and 60 days** — *INFERENCE:* near-zero live acquisition; the app is
dormant, being maintained only to the extent Google's target-API mandate forces it.

**The two predecessor Carcassonne apps are both dead, and both were better:**
- **Exozet (Android, 2011–2018):** **220,000 downloads, ~15,000 ratings, 4.26★.** Removed from Play
  2018-08-05 when its Hans im Glück license expired. *Double the installs and double the star rating of
  the official successor that replaced it.*
- **TheCodingMonkeys (iOS/Mac, 2010–2020):** **8.5M+ lifetime games completed**; removed 2020-02-29 when
  its contract ended. Wired called it *"one of the most polished games on the platform."* A Change.org
  petition was raised to save it.

### 5b. Other branded comparators

| Game | Steam reviews | Steam score | Price | *Est. Steam owners* | Mobile notes |
|---|---|---|---|---|---|
| Terraforming Mars | **5,179** | **69%** | $19.99 | *~233,000* | — |
| Through the Ages | **2,179** | **91%** | $15.99 | *~98,000* | — |
| Carcassonne – Tiles & Tactics | **1,959** | **83%** | $9.99 | *~88,000* | see 5a |
| Splendor | **1,022** | **81%** | $9.99 | *~46,000* | *Lead, unverified:* delisted from both mobile stores |
| Ticket to Ride (2023 ed.) | **1,025** | **68%** | $14.99 | *~31,000* | Marmalade reboot |
| Kingdomino Deluxe (Meeple Corp) | **25** | **88%** | $9.99 | *~750* | Play: **1,000+** installs, **262** ratings, **4.7★**, $3.99. iOS: **196** ratings, **4.8★**, $3.99 |
| Board Game Arena | **not on Steam** | — | freemium/subscription | — | web + mobile; no Steam listing exists |

**Kingdomino deserves its own line.** It is a **Spiel des Jahres winner** with a **live license**, an
actively-shipping developer, a 4.7–4.8★ rating on both mobile stores, and cross-platform play. It has
**262 Play ratings and 196 iOS ratings.** A branded, award-winning, well-executed tile-layer released in
2025 is operating at roughly the same scale as the unbranded clones. *INFERENCE:* the constraint on this
category is demand, not branding or quality.

### 5c. The branded-vs-unbranded ratio — the cost of dropping the IP

This is the number the report was commissioned to produce. It splits in two, and the split is the point.

**On installs, the brand is worth about 2×.**
- Branded Carcassonne on Play: **100,000–240,000**
- Best unbranded on Play (Farmassone): **50,000–100,000**
- Ratio: 240,000 ÷ 100,000 = **2.4×** at the top end; 100,000 ÷ 50,000 = **2.0×** at the bottom.
- **Branded : unbranded ≈ 2–2.4× on installs.** Much smaller than intuition suggests.

**On revenue, the brand is worth roughly 50–200×.**
- Branded, Play base game alone: 100,000 × $5.99 × 0.70 = **$419,000** …
  240,000 × $5.99 × 0.70 = **$1,006,000**. Plus expansion IAP, plus iOS
  (*~5,200 installs* × $4.99 × 0.70 ≈ *$18,000*), plus Steam
  (*~88,000 owners* × ~$4 realized ASP after chronic 70% discounting × 0.70 ≈ *$246,000*) plus 5 DLC.
- Best unbranded, all channels, lifetime: **$5,600–$13,800**.
- Ratio: $419,000 ÷ $13,800 = **30×** … $1,006,000 ÷ $5,600 = **180×**.
- **Branded : unbranded ≈ 30–180× on revenue. Call it ~100×.**

**Why the two ratios differ by 50× is the single most actionable finding in this report.**
The license does not buy audience. It buys **pricing power**. Carcassonne: Tiles & Tactics charges
$5.99 up front and $3 per expansion and people pay it *because they already know the game is good*.
Every living unbranded mobile tile-layer in this census is **free** — Farmassone, War of Carcassonne,
Carcassone – Tile Strategy, Seizer, Placium, all free. The one that tried to charge (Castles, $0.99)
is dead. An unbranded launch does not lose 100× the users; it loses the ability to ask for money at all,
and then has to monetize a genre with the lowest payer conversion on mobile via ads.

---

## 6. Steam / PC channel

**Boxleiter multiplier used:** from Karl Kontus (co-founder, VG Insights), *"How to Estimate Steam Video
Game Sales in 2021?"*, Game Developer, 2 Aug 2021 — a regression over **11,445 Steam games** (>90%
correlation between review count and units sold). Year-banded: **2020+ → 30×**, **2015–2019 → 45×**,
**2014 and earlier → 70×+**. The article attributes the decline (~80× in 2014 → ~30× in 2020) to Steam's
increasingly aggressive review prompts. Corroborated by Simon Carless / GameDiscoverCo with Gamalytic
data (36× for <100-review games, 52.8× for 1,000–10,000-review games) — which suggests the flat 30×/45×
**under**-estimates the large titles.

Method validation: Dorfromantik at 27,328 × 30 = ~820,000 Steam owners, against a publisher-reported
**~1.5M copies across all platforms** (Steam + Switch + PlayStation + Xbox). A ~55% Steam share is
entirely plausible — the method lands in the right place.

| Game | Release | Price | Reviews | Score | Arithmetic | *Est. owners* | Branded? |
|---|---|---|---|---|---|---|---|
| **Dorfromantik** | 2022-04-28 | **$13.99** (never discounted) | **27,328** | **96%** | 27,328 × 30 | ***~820,000*** | **Unbranded** |
| ISLANDERS | 2019-04-04 | $4.99 | **16,099** | **95%** | 16,099 × 45 | *~724,000* | Unbranded (borderline mechanic) |
| Terraforming Mars | 2018-10-17 | $19.99 | **5,179** | **69%** | 5,179 × 45 | *~233,000* | Branded |
| Through the Ages | 2018-03-26 | $15.99 | **2,179** | **91%** | 2,179 × 45 | *~98,000* | Branded |
| Carcassonne – Tiles & Tactics | 2017-11-29 | $9.99 | **1,959** | **83%** | 1,959 × 45 | *~88,000* | **Branded** |
| Splendor | 2015-09-17 | $9.99 | **1,022** | **81%** | 1,022 × 45 | *~46,000* | Branded |
| Ticket to Ride | 2023-11-14 | $14.99 | **1,025** | **68%** | 1,025 × 30 | *~31,000* | Branded |
| Between Two Castles | 2019-11-15 | $12.99 | **448** | **50%** | 448 × 45 | *~20,000* | Branded |
| Galaxy Trucker: Ext. Ed. | 2019-03-07 | $9.99 | **212** | **89%** | 212 × 45 | *~10,000* | Branded |
| Cascadia | 2025-02-19 | $14.99 | **226** | **98%** | 226 × 30 | *~7,000* | Branded (Spiel des Jahres) |
| Isle of Skye | 2018-07-26 | $6.99 | **148** | **66%** | 148 × 45 | *~7,000* | Branded |
| Fate Tectonics | 2015-09-09 | $4.99 | **154** | **75%** | 154 × 45 | *~7,000* | **Unbranded** |
| Land Above Sea Below | 2023-09-13 | $7.99 | **120** | **69%** | 120 × 30 | *~3,600* | **Unbranded** |
| Beacon Patrol | 2025-09-17 | $11.99 | **67** | **97%** | 67 × 30 | *~2,000* | Branded (board game port) |
| Tile Town | 2023-07-20 | $9.99 | **49** | **100%** | 49 × 30 | *~1,500* | **Unbranded** |
| Tile Lands | 2023-11-01 | $2.99 | **28** | **85%** | 28 × 30 | *~840* | **Unbranded** |
| Kingdomino | 2025-11-20 | $9.99 | **25** | **88%** | 25 × 30 | *~750* | Branded |
| Isles & Tiles | 2025-08-25 | $12.99 | **10** | **70%** | 10 × 30 | *~300* | **Unbranded** |
| Kingdom of Cards and Tiles | 2025-04-04 | $4.99 | **~5** | **80%** | 5 × 30 | *~150* | **Unbranded** ("Carcassonne meets Clank!") |

**Steam revenue, Dorfromantik (the ceiling):**
820,000 owners × $13.99 × 0.70 = **$8.03M** *(INFERENCE; upper bound — assumes full price on every unit.
A realistic discount/regional-pricing haircut of 25–35% still leaves **$5.2M–$6.0M**.)*

**Steam revenue, licensed Carcassonne:** 88,000 × ~$4 realized ASP (chronic −70% discounting) × 0.70 =
**~$246,000** *(INFERENCE)*, plus five DLC at $2.00–$2.47.

**The PC read, stated plainly:**
1. **Dorfromantik — unbranded, 3-person Berlin studio, no license — out-earned the licensed Carcassonne
   on Steam by roughly 20–30×**, and out-earned the *entire mobile unbranded category combined* by three
   orders of magnitude. It sells at full price and has never discounted.
2. **PC is premium; mobile is free.** Every title in the table is a paid purchase. Steam does not
   penalize an unknown IP the way the mobile stores do — an unbranded indie at $13.99 is *normal* there.
3. **The category is bimodal.** Below Dorfromantik and ISLANDERS, every unbranded tile-layer on Steam is
   under ~7,000 owners, and most are under 2,000. Quality does not rescue them: Tile Town has a **100%**
   score and ~1,500 owners; Beacon Patrol has **97%** and ~2,000; Cascadia is a Spiel des Jahres winner
   at **98%** with ~7,000. There is nothing in the middle.
4. **DLC is the PC ARPU lever.** A fully-loaded Carcassonne PC customer is a ~$25–30 lifetime purchase,
   not $9.99. That structure does not exist for the indie long tail.

---

## 7. Does AI strength show up in reviews?

**Short answer: yes, consistently, and there is one direct proof that people will pay for it.**

### 7a. The paid-AI data point

**Castles board game** (iOS, $0.99) sells its **Hard AI as a separate $0.99 in-app purchase.**
A 5-star review (johnny29354, 2015-03-29):
> **"Also got the Hard Computer player in-app purchase. That's definitely worth it. Medium was too easy for me."**

This is the only instance in the entire census of anyone monetizing AI strength directly, and the
customer response was positive and explicit. It is a single data point on a long-dead app — but it is
the only direct evidence either way, and it points the right direction.

### 7b. Weak-AI complaints on the unbranded clones

**Farmassone** — AI weakness is its most repeated complaint:
> **"isn't very good (especially at placing farmers)"** — JHolzel, 4★, 2023-07-31
> **"it would be even better if the computer player were harder to beat"** — anplica, 2020-04-05
> the computer opponent **"is not challenging"** — ahduenc, 2020-08-28

One dissent, worth recording honestly:
> **"the robots keep you sweating some times"** — Driver4562, 2017-10-08

Note that "especially at placing farmers" is precisely the hardest part of the game to play well, and
precisely what this project's engine is built around.

### 7c. Weak-AI complaints on the *licensed* app

The licensed Carcassonne's Steam forum has standing threads titled **"Terrible AI"**, **"illogical AI"**,
**"game AI cheats"**, **"AI teamsups"**, **"AI so slow"**, and **"Easier AI Please For Dumbos Like Me"**.

> **"Extremely basic concepts such as 'play your last meeple on your last turn' aren't even implemented
> at the hardest level. Please fix."** — Steam, 2018-03-21
> **"this Frima Studio A.I. must be called A.S. (Artificial Stupidity)"** — Steam, 2018-03-25
> The AI **"slaps tiles down at the end of the game"**; **"Risktaker AI doesn't seem to have a plan."** — Steam, 2018-04-06
> **"The AI could be a bit tougher too. Games are close but I rarely lose."** — play-board-games.com
> bots **"don't expect much of a challenge; only the hardest difficulty seems to make use of
> game-changing fields, and doesn't do it very effectively"**

### 7d. The counter-signal — and it is real

Two findings cut against "strong AI is the differentiator":

1. **Demand runs in both directions.** The same forum has *"Easier AI Please For Dumbos Like Me"*, and
   the licensed app's most-quoted 1-star iOS review is the opposite complaint:
   > **"The AI cheats, it's rigged… How is it fun to play if you know it's rigged against you and 'lets'
   > you win 1 game in 10?"** — djdiskcnskapL, 1★, 2021-12-08

   *INFERENCE:* a much stronger engine will be *perceived* as cheating by a meaningful share of casual
   players unless it ships with well-tuned, genuinely weak lower difficulties and visible explanation of
   its moves. Engine strength is a liability without difficulty calibration.

2. **AI is not the top complaint overall.** Across the licensed app, the dominant negative themes are
   **abandonment and broken servers**, not AI:
   > *"The servers have been down for at least 2 months now, haven't been able to create a new game."*
   > *"This game has so much potential but the fact that it says last updated 4 years ago does not give me hope."*

   The 2.04★ Play rating (6,754 one-stars) is driven by neglect, not by bot quality.

3. **TileKingdom already advertises MCTS.** It markets *"a dedicated Monte Carlo Tree Search (MCTS)
   engine and one of the strongest AI opponents available for a Carcassonne-style game"* — for free, in a
   browser, with no app. Strong AI is already claimed in this space, and the claimant is not visibly
   winning because of it.

**Net read:** AI strength is a **credible differentiator among engaged players and a genuine complaint
vector**, with one direct instance of paid conversion. It is **not** a discovery mechanism. Nothing in
this census suggests strong AI moves install counts; the evidence is that it moves *ratings and retention
among people who already installed*. Given that installs are the binding constraint (§3c), an
engine-strength advantage improves the numerator of a very small fraction.

---

## 8. What I could not determine

Stated plainly, because the owner will act on this document.

**Install counts**
- **Apple publishes no download or install numbers, at all.** Every iOS install figure in this report is
  my inference from rating count. There is no way to validate it.
- **Play "installs" from AppstoreSpy appear to be bracket floors, not exact counts.** True installs sit
  between the floor and the next bracket. All my Play arithmetic uses midpoints and shows both bounds.
- **Kingdomino Deluxe is internally inconsistent** — 262 ratings against a 1,000+ install bracket implies
  a 26% rating rate, which is not credible. Either the bracket is stale or the rating count aggregates
  something I can't see. I did not resolve it; treat that row with suspicion.
- **Seizer's Play rating count** was never obtainable — the Play page truncated and no mirror carried it.
- **iOS rating counts are per-storefront.** Farmassone shows 38 ratings / 3.8★ on the US store but
  18 / 3.3★ on the UK store. I used US only. **Global iOS rating counts are unknown for every iOS app in
  this report**, so all iOS install inferences are US-only and therefore understate the true totals.

**Revenue**
- **No actual revenue figure for any app in this census was obtained.** Every revenue number is derived.
  The two most load-bearing assumptions — **1.0% payer conversion** and **$5 ARPPU** — are my choices,
  not measurements.
- **I could not find a primary source giving payer-conversion percentages specifically for the
  board/card/word genre.** The claim that it is the lowest-converting genre is well-attested
  qualitatively; the number is not. Substitute a real figure if one is available.
- **Ad revenue per install ($0.05–$0.20) is my estimate**, not sourced. It swings the Farmassone and War
  of Carcassonne totals by ~3×, and is the single largest source of error in §4.
- **Steam realized ASP** — I used ~$4 for Carcassonne against a $9.99 list based on chronic 70%
  discounting, but I did not obtain price-history data (SteamDB was not fetched). Dorfromantik's $8.03M
  assumes full price on every unit and is therefore an upper bound.
- **Store cut assumed at a flat 30%.** Google's 15% small-business tier and Apple's Small Business
  Program would materially improve any indie's actual take.

**Coverage**
- **I did not achieve a complete census.** The stores do not expose browsable category listings to any
  tool I have, so this is a search-derived sample, not an enumeration. There are near-certainly small
  clones I did not surface — though the fact that eight distinct query formulations kept returning the
  *same seven apps* is itself evidence the set is close to complete.
- **Non-English storefronts were not swept.** Placium ships in English and Turkish; there may be
  regional clones invisible to English-language search.
- **Seven Castles (iOS)** is confirmed to have existed as a real Carcassonne-style app and its store page
  now 404s on US, IN and GB storefronts. No ratings, price, or dates were recoverable. Counted as dead.
- **TileLord's "1,000 games a week" is the only traffic number any web clone has published.** I have no
  MAU, revenue, or retention data for TileLord, TileKingdom, Cartoria, or Seizer's web version. This is
  a significant hole: the web channel looks like where this category actually lives, and it is the
  channel I can measure least.
- **Splendor's mobile delisting is a single unverified source** — treat as a lead, not a fact.
- **Board Game Arena** was not sized. It has no Steam listing and I obtained no subscriber or MAU figure.
- **Dorfromantik's mobile status** — it is not on iOS; I did not confirm whether an Android version exists.
- **No blocked/paywalled source was worked around.** AppBrain 403'd on every direct fetch (its numbers
  were readable only inside search snippets), appgrooves.com is a **dead domain** (DNS failure),
  apkpure/apkcombo 403'd, carcassonnecentral.com 403'd, and Sensor Tower was skipped as login-walled per
  instruction. androidrank.org and appstorespy.com were the two tools that actually worked.

**Not investigated (out of scope, flagged as follow-ups)**
- The legal/IP question of how far "redraw the art, rename it" actually insulates a clone. Seizer's
  published disclaimer is quoted in §2b as one operator's answer, but I did no legal research.
- Cost of user acquisition. If organic discovery is as weak as §3c indicates, paid UA economics decide
  this question, and this report says nothing about them.

---

## 9. Sources

**Unbranded clones — stores and analytics**
- [Google Play — Carcassone – Tile Strategy (Awoken Industry)](https://play.google.com/store/apps/details?id=com.AwokenIndustry.Carcassone&hl=en_US)
- [AppstoreSpy — com.AwokenIndustry.Carcassone](https://appstorespy.com/android-google-play/com.AwokenIndustry.Carcassone-trends-revenue-statistics-downloads-ratings)
- [Google Play — War of Carcassonne board Games (PlayStal)](https://play.google.com/store/apps/details?id=com.playstal.carcassonne.conquest.free.online.tiles.board.points.scoreboard.game&hl=en_US)
- [AppstoreSpy — War of Carcassonne](https://appstorespy.com/android-google-play/com.playstal.carcassonne.conquest.free.online.tiles.board.points.scoreboard.game-trends-revenue-statistics-downloads-ratings)
- [Google Play — Farm Builder 2D (Farmassone)](https://play.google.com/store/apps/details?id=air.net.boardgamesonline.FarmBuilder&hl=en_US)
- [AppstoreSpy — Farm Builder 2D (Farmassone)](https://appstorespy.com/android-google-play/air.net.boardgamesonline.FarmBuilder-trends-revenue-statistics-downloads-ratings)
- [App Store — Farmassone (US)](https://apps.apple.com/us/app/farmassone/id1010278212) · [reviews](https://apps.apple.com/us/app/farmassone/id1010278212?see-all=reviews) · [GB storefront](https://apps.apple.com/gb/app/farmassone/id1010278212)
- [App Store — Castles board game](https://apps.apple.com/us/app/castles-board-game/id930929122) · [reviews](https://apps.apple.com/us/app/castles-board-game/id930929122?see-all=reviews)
- [App Store — Seizer](https://apps.apple.com/us/app/seizer/id6748835727) · [reviews](https://apps.apple.com/us/app/seizer/id6748835727?see-all=reviews)
- [Google Play — Seizer](https://play.google.com/store/apps/details?id=io.seizer)
- [AppstoreSpy — io.seizer](https://appstorespy.com/android-google-play/io.seizer-trends-revenue-statistics-downloads-ratings)
- [Google Play — Placium: Tile Tactics Strategy](https://play.google.com/store/apps/details?id=io.sinopsis.placium&hl=en_US)
- [AppstoreSpy — io.sinopsis.placium](https://appstorespy.com/android-google-play/io.sinopsis.placium-trends-revenue-statistics-downloads-ratings)
- [App Store — Seven Castles (404, delisted)](https://apps.apple.com/us/app/seven-castles/id969505290)

**Web-only unbranded clones**
- [TileLord](https://tilelord.com/) · [TileLord impressions — GameSpace, Dec 2025](https://gamespace.com/all-articles/news/tilelord-impressions-a-free-browser-based-carcassonne-alternative-that-keeps-growing/) · [dev writeup — dev.to](https://dev.to/erol4/how-i-built-a-free-online-carcassonne-game-alt-you-can-play-in-the-browser-2mgd)
- [TileKingdom](https://tilekingdom.io/)
- [Seizer](https://seizer.io/) · [Seizer — about](https://seizer.io/about)
- [Cartoria Online](https://cartoria.online/) · [Cartoria — Carcassonne alternative blog post](https://cartoria.online/blog/carcassonne-alternative-online-free/)

**Branded comparators**
- [Google Play — Carcassonne: Tiles & Tactics](https://play.google.com/store/apps/details?id=com.asmodeedigital.carcassonne&hl=en_US) (truncates under fetch)
- [androidrank — com.asmodeedigital.carcassonne](https://androidrank.org/application/carcassonne_tiles_tactics/com.asmodeedigital.carcassonne)
- [App Store — Carcassonne – Tiles & Tactics](https://apps.apple.com/us/app/carcassonne-tiles-tactics/id1199912736) · [reviews](https://apps.apple.com/us/app/carcassonne-tiles-tactics/id1199912736?see-all=reviews)
- [Steam — Carcassonne – Tiles & Tactics](https://store.steampowered.com/app/598810/Carcassonne__Tiles__Tactics/) · [negative reviews](https://steamcommunity.com/app/598810/negativereviews/?browsefilter=toprated)
- [Steam forum — "Terrible AI"](https://steamcommunity.com/app/598810/discussions/0/1698294337766520021/) · ["illogical AI"](https://steamcommunity.com/app/598810/discussions/0/2906376154325414793/) · ["game AI cheats"](https://steamcommunity.com/app/598810/discussions/0/3148556875509492806/) · ["Easier AI Please"](https://steamcommunity.com/app/598810/discussions/0/3148556875506207893/)
- [Wikipedia — Carcassonne – Tiles & Tactics](https://en.wikipedia.org/wiki/Carcassonne_%E2%80%93_Tiles_%26_Tactics)
- [Metacritic — Carcassonne: Tiles & Tactics user reviews](https://www.metacritic.com/game/carcassonne-tiles-and-tactics/user-reviews/)
- [play-board-games.com — Tiles & Tactics app review](https://www.play-board-games.com/carcassonne-tiles-tactics-app-review/)
- [AppBrain — Exozet Carcassonne (delisted 2018)](https://www.appbrain.com/app/carcassonne/com.exozet.game.carcassonne)
- [Pocket Gamer — TheCodingMonkeys' Carcassonne removed from App Store](https://www.pocketgamer.com/articles/082238/thecodingmonkeys-iosversion-of-carcassonne-is-set-to-be-removed-from-the-app-store-on-1st-march/) · [carcassonneapp.com farewell page](https://carcassonneapp.com/)
- [Google Play — Kingdomino Deluxe](https://play.google.com/store/apps/details?id=com.meeplecorp.kingdomino&hl=en_US) · [AppstoreSpy](https://appstorespy.com/android-google-play/com.meeplecorp.kingdomino-trends-revenue-statistics-downloads-ratings) · [App Store — Kingdomino](https://apps.apple.com/us/app/kingdomino-the-board-game/id6468810215)

**Steam**
- [Dorfromantik](https://store.steampowered.com/app/1455840/Dorfromantik/) · [SteamSpy](https://steamspy.com/app/1455840) · [Toukana presskit](https://www.toukana.com/dorfromantik/presskit) · [Wikipedia — Toukana Interactive](https://en.wikipedia.org/wiki/Toukana_Interactive)
- [ISLANDERS](https://store.steampowered.com/app/1046030/ISLANDERS/) · [Townscaper](https://store.steampowered.com/app/1291340/Townscaper/) · [Terraforming Mars](https://store.steampowered.com/app/800270/Terraforming_Mars/) · [Through the Ages](https://store.steampowered.com/app/758370/Through_the_Ages/) · [Splendor](https://store.steampowered.com/app/376680/Splendor/) · [Ticket to Ride](https://store.steampowered.com/app/2477010/Ticket_to_Ride/)
- [Cascadia](https://store.steampowered.com/app/2438970/Cascadia/) · [Isle of Skye](https://store.steampowered.com/app/873980/Isle_of_Skye/) · [Beacon Patrol](https://store.steampowered.com/app/2273850/) · [Between Two Castles](https://store.steampowered.com/app/1158500/Between_Two_Castles__Digital_Edition/) · [Galaxy Trucker](https://store.steampowered.com/app/870690/Galaxy_Trucker_Extended_Edition/) · [Patchwork](https://store.steampowered.com/app/528250/Patchwork/)
- [Fate Tectonics](https://store.steampowered.com/app/379530/) · [Land Above Sea Below](https://store.steampowered.com/app/1922020/) · [Tile Town](https://store.steampowered.com/app/2164780/) · [Tile Lands](https://store.steampowered.com/app/2345870/) · [Isles & Tiles](https://store.steampowered.com/app/3165460) · [Kingdom of Cards and Tiles](https://store.steampowered.com/app/3263850/) · [Kingdomino](https://store.steampowered.com/app/3029180/) · [Tileburg](https://store.steampowered.com/app/4639170/) (rejected — city sim)
- [SteamSpy — Carcassonne T&T](https://steamspy.com/app/598810)

**Method / benchmarks**
- [Karl Kontus (VG Insights) — How to Estimate Steam Video Game Sales in 2021, Game Developer](https://www.gamedeveloper.com/business/how-to-estimate-steam-video-game-sales-in-2021-) — **Boxleiter multiplier, primary citation**
- [Simon Carless / GameDiscoverCo — What "Steam review count" tells us about your game](https://newsletter.gamediscover.co/p/what-steam-review-count-tells-us) — corroborating
- [AppsFlyer — App ratings and reviews ("at least 1% of users")](https://www.appsflyer.com/blog/tips-strategy/app-ratings-reviews/) — **review-to-install ratio**
- [CS Agents — The Value in Managing App Ratings and Reviews ("less than 1%")](https://cs-agents.com/blog/appreviews/)
- [Appbot — Relationship between ratings and reviews (36.6 ratings per review)](https://appbot.co/blog/relationship-ratings-reviews/)
- [AppTweak — Average app conversion rate per category (Games–Board = 0.6%, lowest on App Store)](https://www.apptweak.com/en/aso-blog/average-app-conversion-rate-per-category) — **key discovery number**
- [Mistplay / MAF — Mobile game conversion rates](https://business.mistplay.com/resources/app-conversion-rates/) (board/card/word lowest-converting; no genre percentage obtainable)

**Discovery / negative results**
- [AlternativeTo — Games like Carcassonne](https://alternativeto.net/software/carcassonne/) — lists only **3** alternatives, **none of them tile-layers** (all Catan-style). A notable negative result.
- [BoardGameGeek — Kingdomino Digital Edition out now on iOS and Android](https://boardgamegeek.com/thread/3533590/kingdomino-digital-edition-is-out-now-on-ios-and-a)
- [BoardGameGeek — "Made free online Carcassonne alternative, supports single/multiplayer"](https://boardgamegeek.com/thread/3565773/made-free-online-carcassonne-alternative-supports)
- [GitHub — tsaglam/Carcassonne](https://github.com/tsaglam/Carcassonne) (desktop Java, not shipped to any store)
