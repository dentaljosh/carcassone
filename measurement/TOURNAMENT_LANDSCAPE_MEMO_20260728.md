# Competitive Carcassonne — landscape, and how to shop the champion around

> **STATUS: RESEARCH + PROPOSAL, 2026-07-28. Nothing committed, no run launched, no
> production change. This memo answers "who would we play, under what rules, and what
> would a match actually prove." It supersedes nothing; it EXTENDS
> [docs/research/TOURNAMENT_TIMING_2026-07-26.md](../docs/research/TOURNAMENT_TIMING_2026-07-26.md)
> (which established the time controls and ruleset) with the organizational landscape,
> the platform/bot-policy constraint, the AI-vs-human precedent base, and three concrete
> match designs with their statistics.**
>
> **Three headline findings, before anything else:**
> 1. **Our locked scope is EXACTLY the competitive ruleset.** 2-player, base 72 tiles,
>    no expansions, farmers included at 3 pts/completed-city. Nothing to change. But
>    **three small rules-fidelity gaps exist** (ties, start tile, pondering) — §1.4.
> 2. **Board Game Arena is a closed door.** Its ToS forbids both engine assistance AND
>    protocol-level automation; there is no API, no bot-account pathway, no research
>    precedent, and BGA is simultaneously the venue for the US/UK/Belgian national
>    championships and the CCL. **The "anonymous arena climb first" step in the original
>    brief is struck** — §2.3.
> 3. **A 5-game match is not merely weak, it is ~1.08:1 evidence.** The path to a real
>    claim is per-decision regret (the backgammon PR paradigm) plus a curated position
>    suite — both of which we have already built and never used — §5.

---

## 1. Landscape findings

### 1.1 The official World Championship

**Publisher-run, not fan-run.** The Carcassonne World Championship (WC) is organized by
**Hans im Glück** and **Spielezentrum Herne**, with Brettspielwelt and Asmodee as listed
partners. The rules text is explicit about who decides: *"Publisher Hans im Glück and
Spielezentrum reserve the right to let other people take part as well…"*
([tournament rules](https://carcassonne-meisterschaft.de/en/tournamentrules.htm),
last updated 14 April 2026). Z-Man Games (the NA publisher) has no organizing role we
could find.

**History and scale.** First edition 2006 at SPIEL Essen; annual since, **2020 cancelled
for COVID** ([final-2020](https://carcassonne-meisterschaft.de/en/final-2020.htm)).
The final **moved from Essen to Spielezentrum Herne in 2023** and has stayed there
([final-2023](https://carcassonne-meisterschaft.de/en/final-2023neu.htm)). Growth:
16 players (2006) → 36 players / 25 countries (2019) → 42 / 37 (2023) → 46 (2024) →
**52 players from 45 countries (2025, an explicit record)**. The
[countries page](https://carcassonne-meisterschaft.de/en/countries.htm) (updated
2026-07-22) lists **58 countries/regions, of which 40 have confirmed for 2026**.

> ⚠️ **Date discrepancy, unresolved.** The
> [tournament index page](https://carcassonne-meisterschaft.de/en/tournament.htm) says the
> next tournament is **29.08.2026**; the
> [2026 final page](https://carcassonne-meisterschaft.de/en/final-2026.htm) gives
> **Saturday 24 October 2026** in Herne (09:00 registration → 17:30 ceremony → 19:00
> aftershow). Two independent fetches, two dates. **The 20th WC is 1–3 months away either
> way** — if Joshua wants any 2026 presence, the window for contacting organizers is now.
> Resolve by email to the organizers before acting on either date.

**Qualification** ([rules page](https://carcassonne-meisterschaft.de/en/tournamentrules.htm))
is a hybrid of national champions plus **five online wildcards**:
the reigning World Champion (may defend); the **national champion of each participating
country**; the winner of the **"All Other Countries"** BGA tournament; the winners of
**MSO**, **CCL** and **KOC**; and **one player from each of the top 3 nations of WTCOC**.
An anti-tourism clause caps each player at one national championship per season.

Hans im Glück has formally absorbed the online circuit: the
[tournament page](https://carcassonne-meisterschaft.de/en/tournament.htm) describes WTCOC
and CCL as *"two additional online championships … which we have accepted as part of the
official Carcassonne World Championship."*

### 1.2 The ruleset — it matches our locked scope exactly

All verbatim from the
[WC tournament rules](https://carcassonne-meisterschaft.de/en/tournamentrules.htm):

- **No expansions:** *"All games are played with the basic Carcassonne game only."*
  No Inns & Cathedrals, no Traders, no River, no Abbot.
- **Farmers INCLUDED, at 3 points (2nd-edition rule), not 4:** *"cities with two tiles
  give four points (not two). The Farmer's value is calculated like this: for every meadow
  the number of farmers is calculated and a player with the most farmers receives 3 points
  for every city at that meadow. Note that every player can get the points for one city in
  this manner more than one time!"*
- **Strictly 2-player at every stage:** *"The preelimination is a 6 round tournament at
  two player tables."*
- **15 min/player, chess clocks, sudden death** — timeout is an absolute loss even when
  ahead on points. (Established in the prior memo; re-confirmed here.)

Independently corroborated by the MSO rules PDF, which spells out the BGA settings for the
WC-qualifying online event: *"All expansions: Off / Field scoring: Each field is worth 3
points per adjacent completed city (International rules) / Completed 2-tile cities: 4
points (International rules)"*
([MSO Carcassonne 2025](https://mindsportsolympiad.com/wp-content/uploads/2025/01/Carcassonne-2025.pdf)).
**"International rules" is the community name for this exact configuration.**

⇒ **No scope decision is required.** The locked scope (2p, Base + Farmers, current
scoring, no River) is the competitive standard. This is the single best piece of news in
the memo.

### 1.3 Format, tiebreaks, and the tile-draw procedure

**Swiss + knockout, and the knockout is BEST-OF-ONE.** Six Swiss rounds with
Buchholz/Solkoff, then a straight single-game QF/SF/F bracket (1v8, 2v7, 3v6, 4v5).
**The world title is decided by four single games after the Swiss.** Round counts have
varied (5 rounds in 2021 and 2023).

**Three-level tiebreak, and the third is a points-margin tiebreak:** victories → Buchholz
→ Buchholz-with-best-and-worst-discarded → *"the difference of victory points over all six
games will be summed up."* Visible as the `Vic. | W.1 | W.2 | Diff.` columns in the
[2025 standings](https://carcassonne-meisterschaft.de/en/final-results-2025.htm).

**⚠️ The tie rule is strategically significant and we do NOT model it:**
> *"IMPORTANT: in the unlikely case of a draw / tie in all games (preelimination,
> quarter-final, semi-final and final round) the starting player always loses
> automatically!"*

The 2019 final was in fact 102–102 and resolved this way. See §1.4.

**Tile-draw procedure — face-down pool, player-selected, no bag:**
> *"During your opponent's turn you may choose and look at your next tile. But beware: the
> new tile has to be at anytime above the tabletop… You may look at it (secretly), but at
> the beginning of your turn before you add it to the 'board', let your opponent have a
> look at it."*

Informationally this is equivalent to a random face-down draw, so **no engine change is
implied** — but it has one important consequence: because the draw order is
*player-determined*, **duplicate decks are structurally impossible in physical play**
(§2.1).

Other conduct rules worth knowing: touch-move applies to tiles and meeples; meeple supply
must stay visible; **written tile-counting is banned** (*"It's not allowed to make any
private notes during the game (like counting tiles on a sheet of paper)"*); talking to
spectators is banned; tiles are counted before every game; the non-starting player chooses
colour; streaming consent is automatic.

### 1.4 ⚠️ Three rules-fidelity gaps on OUR side

| # | Gap | Our current behaviour | Competitive rule | Severity |
|---|---|---|---|---|
| 1 | **Ties** | `game_wrapper.get_game_ended` returns ±1e-6 for an exact tie — a **draw**, symmetric for both seats | **The starting player loses all ties, at every stage** | **Real.** Draws are ~1–2.5% of our games (2/200 in the luck-floor cell, 3–5/200 in the 2026-07-28 screens). It makes the second seat strictly preferable at equal score and changes optimal endgame play *asymmetrically by seat* — a value-function change, not a bookkeeping one. **Not in LEVER_INDEX; nobody has ever modelled it.** |
| 2 | **Fixed start tile** | `initialize_deck` shuffles all 72 into one deck; first player draws a random tile onto an empty board | Retail/tournament convention pre-places the city+road "D" start tile | Small (already triaged: [BACKLOG](../BACKLOG.md) 2026-07-28, PARKED, "bundle with G1"). Near-null strategically, but re-baselines every measurement. |
| 3 | **Pondering** | We idle on the opponent's clock | Humans may **legally** choose and look at their next tile during the opponent's turn ⇒ ~2× effective budget | Known: roadmap **G1, HELD pending contest registration**. This memo is the plan G1 was held for. |

Gap 1 is new and is the one worth surfacing to Joshua. It costs nothing to *measure*
(re-score existing paired archives under "starting player loses ties" and see how many
game outcomes flip) before deciding whether to change the agent.

### 1.5 National championships

40+ countries run qualifiers, **mostly organized by publishers/distributors** (Devir in
Latin America and Spain, Asmodee in France, Giochi Uniti in Italy, Swan PanAsia in
China/Taiwan, Bard in Poland, 999 Games in NL, Piatnik in Hungary) rather than by an
independent player federation. Index:
[countries page](https://carcassonne-meisterschaft.de/en/countries.htm).

Rules deviations found (all vs the WC baseline):

- **Netherlands** — base only, no River/Abbot, farms at 3 pts, but a **40-min round cap
  with a 50-min hard stop instead of per-player chess clocks**; 3 prelim rounds → top-16
  knockout, capacity 128 ([rollthedice.nl](https://www.rollthedice.nl/toernooien/nk-carcassonne/)).
- **Poland** — 2nd-edition base, no Abbot/River; qualifier slots scale with field size;
  **winner's travel to Essen reimbursed** ([bard.pl](https://wydawnictwo.bard.pl/?page_id=2102)).
- **Great Britain** — base only, **6 Swiss rounds**, capacity 56, defers detail to the MSO
  ruleset ([UK Games Expo](https://www.ukgamesexpo.co.uk/events/3670-carcassonne-uk-championship/)).
- **France** — 5 Swiss + top-8; **all-expenses-paid trip to the world final** for the
  winner ([asmodee.fr](https://www.asmodee.fr/events/championnat-carcassonne/)).
- **Czech Republic** — Swiss, 2 per table, but **25 min/player** *(snippet-sourced, not
  quote-verified)*.
- **USA / Canada / Australia** — no local organizer; routed through **BGA online
  tournaments**. The US National Championship 2026 runs on BGA (6 Swiss + top-8, 15 min
  fixed).

### 1.6 The online scene is much larger than the live one

This is the part that matters most for finding an opponent:

- **King of Carcassonne** (BGA): 2025 World Cup drew **628 players** (601 in 2024); the KOC
  World Championship runs a **512-player bracket**
  ([carcassonne.gg/King-of-Carcassonne](https://carcassonne.gg/King-of-Carcassonne/)).
- **Carcassonne Champions League (CCL)** — described as **60 of the strongest players**;
  4 qualification brackets → league → R16/QF/SF/F, **Bo3 in qualification and early
  playoffs, Bo5 from the quarter-finals**, each game a 2-player BGA table at 15 min/player,
  *"All expansions - No"* ([CCL 2026 rules](https://carcassonne.gg/CCL-2026-Rules/)).
- **WTCOC** — national teams of 5–10, round-robin → knockout, matches = 5 duels, best-of-3
  each ([carcassonne.cat](https://www.carcassonne.cat/english/)).
- **[carcassonne.gg](https://carcassonne.gg/)** is the community's competitive hub, tracking
  CCL, MSO, KOC, WC, nationals, WTCOC, ETCOC, Copa America and the Asian Cup, plus podcasts
  and creator video.
- **BGA scale context:** Carcassonne shows **15,165,434 games played**
  ([gamepanel](https://en.boardgamearena.com/gamepanel?game=carcassonne)) and was the
  **#1 game on BGA by tournament count in 2025 with ~6.5k tournaments organized**
  ([BGA 2025 year in review](https://en.boardgamearena.com/news?id=1025)).

⇒ **The live WC is ~50 players, but the competitive funnel behind it is hundreds to low
thousands of players, all on BGA, all playing our exact ruleset.**

---

## 2. How organized play handles the randomness problem

### 2.1 Duplicate decks: nobody does it, and the WC structurally cannot

**Finding: no Carcassonne tournament anywhere uses duplicate or mirrored tile orders.**
This is a negative finding from absence of evidence (BGG and Carcassonne Central were both
hard-blocked to our fetches), but the WC rules make it *structurally* impossible:

- *"The standard Carcassonne box is used for all games"* + *"You have to count the tiles
  each time before a new game starts"* ⇒ every table shuffles its own physical box.
- The **choose-your-own-tile** rule means the draw sequence is player-determined, so two
  tables would diverge on move one.
- The online qualifiers (MSO/KOC/CCL/WTCOC) run BGA's stock implementation with standard
  random draws; none of their rules documents mentions seeded or mirrored decks.

**So luck is handled entirely by round count and Buchholz — never by deck control.** The
6-round Swiss is the variance instrument; the knockout deliberately reintroduces it.

The strongest single data point on how much luck the format retains: **Matt Tucker won the
2023 world title in what German coverage describes as his first-ever live tournament**
(*"Für Matt Tucker … die erste Teilnahme an einem Turnier überhaupt"*,
[halloherne.de](https://www.halloherne.de/artikel/erste-carcassonne-wm-in-herne-64871)).
And in 2025, Horacio Mastandrea won **6/6** in the Swiss with a **+119** point differential
and did not win the title; Xiangyu Qin won it from 4.0/6 and **+21**
([2025 results](https://carcassonne-meisterschaft.de/en/final-results-2025.htm)).

### 2.2 Match lengths

| Context | Match length |
|---|---|
| WC Swiss | 6 × **single games** |
| WC knockout (QF/SF/F) | **single game each** |
| CCL qualification + R16 | **Bo3** |
| CCL QF onwards | **Bo5** |
| Belgian BCL | Bo3 |
| WTCOC duels | Bo3 |
| Hungary (Piatnik, online) | Bo3 over a 9-week season |

**Bo5 is the longest format that exists anywhere in competitive Carcassonne.** Everything
we propose in §5 that is longer than Bo5 is therefore *outside* the sport's own norms and
has to be sold as a scientific protocol, not as a match.

### 2.3 ⛔ Board Game Arena forbids what we would need to do

This is the decisive platform finding, and it strikes the "anonymous BGA arena climb"
step from the brief.

**The operative clause — Terms of Use §VIII "Fair Play"**
([boardgamearena.com/legal?section=tosv](https://boardgamearena.com/legal?section=tosv)):

> *"BGA will not tolerate any cheating and/or lack of fair play, whether through the use of
> **cheating software**, **analysis of communication protocols or code**, use of multiple
> Accounts, collusion with other Users, leaving the game before its normal end, use of game
> blocking tactics in order to force other Users to quit, or the use of obscene or foul
> language, etc."*

> ⚠️ **Provenance caveat, carried deliberately.** The live legal page is JS-assembled and
> truncates before §VIII. This wording was obtained from two independent secondary sources
> that agree verbatim (a search-index extraction and a BGA forum moderator quoting it at
> [forum p=158329](https://forum.boardgamearena.com/viewtopic.php?p=158329)). Rate it
> **high-confidence, not primary-verified.** Confirm in a rendered browser session before
> relying on it contractually.
>
> ⚠️ **A fabrication was caught during this research and must not resurface.** An earlier
> pass produced a confident quote — *"You may not use any automated system, bot, or script
> to play games…"* — attributed to `BGA_TC_Pub_en.pdf`. The researcher then read the actual
> PDF: it is the **publisher licensing contract** (AD2G Studio SAS ↔ rights-holders) and
> **contains no bot/AI/automation clause at all**. If that sentence turns up in a future
> session, it is invented. Discard it.

**Two of the enumerated prohibitions bite independently:**
1. *"cheating software"* — an engine selecting the moves is the paradigm case.
2. *"analysis of communication protocols or code"* — this bites on the **plumbing**, so a
   programmatic client is prohibited on its face **even if a human made every move**.

**No API, no bot pathway, no research precedent.** BGA staff: *"Nope, no API"*
([forum t=33251](https://forum.boardgamearena.com/viewtopic.php?t=33251)); replay mining is
rate-limited and *"not encouraged"* ([t=22483](https://forum.boardgamearena.com/viewtopic.php?t=22483)).
The developer doc states *"There is no framework support (now) for AI/Bots"* and that the
games with "bots" run **Automa solo rules, not AI**
([Bots and Artificial Intelligence](https://en.doc.boardgamearena.com/Bots_and_Artificial_Intelligence)).
Can't Stop is the lone true bot-as-player and is deliberately non-replicable — a developer
asking to build an AI opponent was told *"basically answer is no"*
([t=14521](https://forum.boardgamearena.com/viewtopic.php?t=14521)). **Carcassonne has no
bot support.**

**Enforcement is weak in practice** — there is no report category for engine cheating
([bug 67476](https://en.boardgamearena.com/bug?id=67476)), and "are there bots?" threads get
locked without a staff policy statement. **That is not a reason to do it.** The decisive
argument is not legal exposure, it is that BGA hosts the US, UK and Belgian national
championships, the CCL, the KOC and the "All Other Countries" WC wildcard — i.e. **the same
platform is the venue for every person we would ever want to recruit, annotate with, or be
credible in front of.** A ToS-violating rating climb would be the single most efficient way
to make the entire competitive community refuse to engage with us.

**Also, we could not read the leaderboard.** BGA's `award`, `halloffame` and `playerstat`
pages are JS-rendered and Premium-gated (*"Players' statistics are only available to
players who become Board Game Arena Premium members"*), and BGA **does not publish the
number of ranked players** ([forum p=195990](https://forum.boardgamearena.com/viewtopic.php?p=195990&lang=en)).
A ~$30/yr Premium account plus a rendered session would fix this and is the cheapest way to
identify targets by rating rather than by title.

> ⚠️ **Two BGA facts are contradictory in official sources.** The live FAQ and the 2017
> announcement describe a **0-based ELO** (Beginner 0 … Master 700+,
> [news id=319](https://en.boardgamearena.com/news?id=319)); the developer wiki says ratings
> **start at 1500** with K=60/40 ([doc/Rating](https://en.doc.boardgamearena.com/Rating)).
> Third-party evidence favours the 0-based scale as the live one, with the 1500 figure
> belonging to the hidden **Elite Arena Score**. Do not calibrate anything to BGA ELO
> without resolving this.

**Alternative platforms are UNRESEARCHED.** Yucata.de (turn-based, has a rating system,
historically the permissive class of server), Brettspielwelt (the historic Carcassonne
server — and, notably, a *listed WC partner*), JCloisterZone (the client Carcassonne
Central leagues used; its site says AI is **legacy-client only**), and the Asmodee/Exozet
official app were all queued but not reached before the session's 200-call search budget
ran out. **This is the top open research item** — Brettspielwelt in particular is
interesting precisely because it already has a relationship with the WC organizers.

---

## 3. Seriousness and money

### 3.1 Champions

| Year | Champion | Nationality |
|---|---|---|
| 2006, 2008, 2009, 2010 | **Ralph Querfurth** | Germany (**record 4 titles**) |
| 2007 | Sebastian Trunz | Germany |
| 2011 | Els Bulten | Netherlands (**only female champion**) |
| 2012 | Martin Mojzis | Czech Republic |
| 2013, 2015 | **Pantelis Litsardopoulos** | Greece (2 titles, 5 consecutive finals) |
| 2014 | Takafumi Mochizuki | Japan |
| 2016 | Vladimir Kovalev | Russia |
| 2017 | Tomasz Preuss | Poland |
| 2018 | Genro Fujimoto | Japan |
| 2019 | Marian Curcan | Romania |
| 2020 | *cancelled (COVID)* | — |
| 2021 | Maciej Polak | Poland |
| 2022 | Arpad Gere | Romania |
| 2023 | Matt Tucker | Great Britain |
| 2024 | Daniel Angelats | Catalonia |
| 2025 | **Xiangyu Qin** | China |

Sources: [official history](https://carcassonne-meisterschaft.de/en/former-results.htm)
(stale after 2023) plus the [2024](https://carcassonne-meisterschaft.de/en/final-results-2024.htm)
and [2025](https://carcassonne-meisterschaft.de/en/final-results-2025.htm) results tables;
cross-checked against the
[Carcassonne Belgium archive](https://carcassonnebelgium.weebly.com/carcassonne-world-championship-live.html),
which also gives 2025 runners-up **Horacio Mastandrea (Uruguay)** and **Raf Mesotten
(Belgium, 3rd)** and 2023 runner-up **Alexey Pegushev (Latvia)**.

**A recognizable elite exists, but titles do not repeat.** Kovalev (2016 champion) topped
the 2024 Swiss at 6/6 and finished 5th; Preuss (2017) was 14th in 2025; Angelats (2024
champion) 37th in 2025; Tucker (2023 champion) 12th in 2024. **Single-game knockouts mean
the defending champion routinely finishes mid-table** — which is itself the strongest
argument that these people already understand the luck problem viscerally and will be
receptive to a properly-designed protocol.

### 3.2 Money: essentially none, and this is an opportunity

**There is no cash prize for the Carcassonne World Champion.**

- The rules page mentions prizes **zero times**.
- German press covering Herne describes only *"den Siegerpokal"* — the trophy
  ([halloherne.de](https://www.halloherne.de/artikel/erste-carcassonne-wm-in-herne-64871)).
- A 2012 BGG thread is literally titled
  ["World Championship prizes?"](https://boardgamegeek.com/thread/857679/world-championship-prizes),
  started by a qualified national representative who could not find any published prize
  information.
- What the WC *does* provide ([final-2026](https://carcassonne-meisterschaft.de/en/final-2026.htm)):
  free drinks all day, lunch catering, a SPIEL Essen ticket, and an aftershow buffet.
  **Accommodation is explicitly the player's own problem** and there is no travel
  reimbursement from the WC organizers. (Poland and France reimburse their own national
  champions.)
- **The only cash figure anywhere in competitive Carcassonne is MSO's £30 first prize** for
  its live event ([MSO prizes](https://mindsportsolympiad.com/prizes-2023/), snippet-sourced).
  MSO's online Carcassonne pays **medals**; WTCOC's rules say *"The only prize will be to be
  crowned the best Carcassonne online team of the world. A badge will be awarded."*
  The Carcassonne Central community championship prize was **a copy of a game**.

**There is no professional scene** — no sponsorships, no appearance fees, no paid
exhibitions. The pattern matches other Eurogame world championships (the Catan World
Championship is structurally identical and also has no published cash prize).

⇒ **Strategic read: a four-figure honorarium would be, by a wide margin, the largest sum
ever paid to anyone for playing Carcassonne.** That is real leverage — but it also means
the incentive to say yes is mostly *interest and status*, not money, so the pitch matters
more than the number.

---

## 4. Precedents

### 4.1 Carcassonne AI: the field is empty and stalled

The entire academic corpus is **four artifacts from two groups**:

- **Heyden (MSc, Maastricht, 2009)** —
  [PDF](https://project.dke.maastrichtuniversity.nl/games/files/msc/MasterThesisCarcassonne.pdf).
  Scope exactly ours (2p, base, farms). Game-tree complexity **O(10¹⁹⁴)**, state space
  **≥O(10⁴⁰)**. Star2.5 beat MCTS 70/100.
  **§6.5 is the ONLY human comparison in the entire literature**, verbatim: *"the Star2.5
  player played against advanced human players (Cathleen Heyden, Robert Briesemeister).
  Totally, there were 10 games played, whereof the Star2.5 player won 6 games."*
  The "advanced human players" are the thesis author and a friend named in her own preface.
  **6/10 is p≈0.38 under a fair coin.** This is the entire evidence base for "Carcassonne AI
  beats strong humans."
- **Ameneyro, Galván & Kuri Morales, IEEE SSCI 2020** —
  [arXiv:2009.12974](https://arxiv.org/abs/2009.12974). MCTS ≫ Star2.5 (77–89%), directly
  **contradicting Heyden** (they attribute it to setup differences). Two things transfer:
  (a) they already use **deck-pairing with 100 pre-generated tile sequences and role swaps**
  — so paired-deck evaluation is the published norm in this game, we are consistent with it,
  not ahead of it; (b) their budgets are **s=100 simulations** and Star2.5 at depth 3, i.e.
  orders of magnitude below our production configs. They explicitly decline to measure
  strength: *"exhaustive experiments against agents with particular behaviours are needed to
  measure their strength in the future."*
- **Galván & Simpson 2021** ([arXiv:2112.09697](https://arxiv.org/abs/2112.09697)) and
  **Galván, Simpson & Ameneyro 2022** ([arXiv:2208.13589](https://arxiv.org/abs/2208.13589))
  — evolved UCT formulas, algorithmic opponents only, **no human comparison**. The group's
  later papers move **off** Carcassonne onto synthetic landscapes.

**No AlphaZero-style Carcassonne work has ever been published. Nobody has ever claimed
superhuman. No bot has ever played humans online in a documented, evaluated way.**

⇒ On this evidence, **a properly-powered, deck-paired, regret-scored human evaluation would
be the most rigorous human-strength measurement ever performed for a modern designer board
game.** That is a publishable result independent of whether we win.

### 4.2 The backgammon paradigm — the most important precedent for us

**The matches were tiny and inconclusive; the community solved it by switching statistic.**

Berliner's BKG 9.8 beat world champion Luigi Villa 7–1 in 1979 — and **Berliner himself
wrote that Villa was the better player**, on the basis of a per-decision error count:
*"down the line Villa played better"*, BKG made **eight errors in seventy-three non-forced
situations**, and *"the dice had the final say"*
([Computer Backgammon](https://bkgm.com/articles/Berliner/ComputerBackgammon/)).
**The winner of the first man-machine world-champion match publicly declared his own
program weaker, using exactly the metric we should adopt.**

TD-Gammon's human record was similarly ambiguous (−13 pts over 51 games in 1991; −1 pt over
40 vs Bill Robertie in 1993; −8 over 100 vs Malcolm Davis in 1998
([Tesauro, CACM 1995](https://bkgm.com/articles/tesauro/tdl.html))). Kit Woolsey's
calibration: **JellyFish played 300 games each against Mike Senkiewicz and Nack Ballard and
came out dead even — +58 vs one, −58 vs the other**
([Using the Bots](https://bkgm.com/articles/GOL/Oct00/bot.htm)). **n=600 to conclude "world
class."**

**So the community replaced win/loss with per-decision equity error.** XG's
**PR = total equity lost × 500 / decisions** ([backgammon101](https://backgammon101.com/pr-er/));
GNU Backgammon publishes **rating bands** on normalised error/move
([manual](https://www.gnu.org/software/gnubg/manual/html_node/Overall-rating.html)):
Supernatural 0.000–0.002 · World Class 0.002–0.005 · Expert 0.005–0.008 · Advanced
0.008–0.012 · Intermediate 0.012–0.018 · Casual 0.018–0.026 · Beginner 0.026–0.035.

Chuck Bower's ["Quantifying Backgammon Skill"](https://www.bkgm.com/articles/GOL/Sep01/gol901.htm)
is the founding document, and gives **the exact contrast we need**:

- Snowie **1.753 mppm (±0.705)** vs JellyFish **2.533 (±0.705)** on the *same 19-point match*;
  best human Dirk Schiemann **2.927**; top-30 human average **3.93 ± 0.15 over 327 matches**.
- And: establishing a **55% match-win expectation by results alone requires "on the order of
  400 matches"** at 95% confidence.

**400 matches by outcome vs bot-separated-from-best-human on a single 19-point match.**

Corroborating the hopelessness of outcomes: a
[fit over ~650 matches](https://freerangestats.info/blog/2016/03/19/elo-pr-luck) finds
**luck alone predicts the winner 97.9% of the time**; net error rate alone, 65.0%.
Reliability guidance: *"Average PR over 20+ matches is a much better indicator of skill
level"* ([BackgammonHit](https://backgammonhit.com/articles/backgammon-ratings/)).

**Where bot judgment is untrustworthy** (Woolsey): races, coming in against an anchor,
board-building in holding games, **priming battles where timing is critical**, back games,
and cube decisions. And **play-vs-play comparisons are more trustworthy than absolute
equities because errors partially cancel** — which is exactly the argument for scoring
*disagreements* rather than absolute values.

**The disagreement-mining design already exists**: the
[Depreli bot comparisons](http://www.bkgm.com/articles/Keith/DepreliBotComparison/index.html)
— *"any position where the bots disagreed on what to do was saved and later 'rolled out'"* —
which is precisely the shape of our own CL-070 successor experiment (the oracle-score
pilot). Keith flags the validity limit honestly: **bot-vs-bot disagreement positions may not
resemble the positions humans reach**, which is an argument for mining disagreements
*between the human and the champion*, not between two of our own configs.

### 4.3 Poker: sample sizes and the two luck-control regimes

- **Libratus (2017)**: **120,000 hands over 20 days**, 4 HUNL specialists, +147 mbb/game,
  **p = 0.0002**, $200,000 purse
  ([Science](https://noambrown.com/papers/17-Science-Superhuman.pdf),
  [CMU](https://www.cmu.edu/news/stories/archives/2017/january/AI-beats-poker-pros.html)).
  **The duplicate mechanism is documented only in press releases, not the paper**: *"Player
  A in each pair will receive the same cards as the computer receives against Player B, and
  vice versa. **One of the players in each of these pairs will play on the floor of the
  casino, while his counterpart will be isolated in a separate room**"*
  ([CMU Piper](https://www.cmu.edu/piper/news/archives/2017/january/poker-play-begins.html)).
  Physical isolation is load-bearing.
- **Claudico (2015) is the cautionary tale**: **80,000 hands with duplicate pairing was not
  enough** — *"Despite Claudico losing by over 9 big blinds per 100 hands (a margin that is
  considered 'huge' by poker professionals), the result is only on the edge of statistical
  significance, making it hard to draw a conclusion from this large investment of human
  time"* ([AIVAT paper](https://cdn.aaai.org/ojs/11481/11481-13-15009-1-2-20201228.pdf)).
- **Duplicate's honest limits**, from Schmid's textbook §21.6.1
  ([arXiv:2111.05884](https://arxiv.org/pdf/2111.05884)): *"note that this method also
  **halves the number of datapoints** as the paired outcome then forms a single measurement…
  While simple, this method provides only a **modest improvement**."*
- **AIVAT** ([arXiv:1612.06915](https://arxiv.org/abs/1612.06915)) — a provably unbiased
  control-variate estimator that **"reduce[s] the standard deviation … by 85% and
  consequently requires 44 times fewer games."** Two findings matter more than the headline:
  (a) **the baseline's quality is the bottleneck** — 85% with DeepStack's value net, only
  68% with a weaker agent's estimates; **a better evaluator buys a better ruler and a better
  player from the same artifact**; (b) **AIVAT structurally cannot debias a human**, because
  a human's action distribution is unknown.
- The natural experiment: **DeepStack (AIVAT, ~3,000 hands/player) got statistically
  significant results on individual humans in hours; Libratus (duplicate, 120,000 hands)
  needed three weeks to get a result only for the aggregate.** Duplicate's one decisive
  advantage is that **it requires nothing from the opponent** — which is exactly why it is
  the only option against a human.
- **Pluribus's software trick is the one to steal**: *"we replay each hand with a copy of
  Pluribus in the human's position… The human's win rate is subtracted by the Control's win
  rate (which in expectation must be zero)"*
  ([supplement](https://noambrown.com/papers/19-Science-Superhuman_Supp.pdf)). **A
  software-only analogue of duplicate dealing that needs only ONE human.** §5.2 builds on
  this.
- **Pay on the variance-reduced estimator.** Libratus gave each pro a **$20,000 floor** and
  split the remaining $120,000 **by performance relative to the worst human**. Pluribus paid
  **$(1 + 0.005X) per hand** where X is the **variance-reduced** win rate, clamped to ±120,
  with players **not told X until the end**. This aligns the opponent's incentive with skill
  instead of luck, and it is a citable norm.

### 4.4 Bridge, Scrabble, Hanabi, Diplomacy — four more transferable designs

- **Bridge is duplicate by definition** — you are scored only against others holding
  identical cards; **IMPs** additionally pass raw margins through a **compressive lookup
  table**, a native shrinkage estimator that stops one freak deal dominating
  ([Duplicate bridge](https://en.wikipedia.org/wiki/Duplicate_bridge)).
- **The NukkAI "NooK" challenge (Paris, 24–25 March 2022)**: **800 deals, 100 per champion**,
  declarer play only, always 3NT, **defenders = WBridge5 run deterministically** — so the
  human and the AI face a **bit-for-bit reproducible environment**, arguably cleaner than
  poker's duplicate. NooK beat eight world champions
  ([Imperial](https://www.imperial.ac.uk/news/235238/ai-based-imperial-research-beats-world/),
  [Guardian](https://www.theguardian.com/technology/2022/mar/29/artificial-intelligence-beats-eight-world-champions-at-bridge)).
  ⚠️ **No peer-reviewed paper exists and the official results page shows placeholder text** —
  the margin (909 pts, ~67/80 sets) is secondary-sourced only. Noam Brown's public criticism
  — that removing bidding removes the communication/deception layer — is worth carrying.
- **⭐ Ginsberg's GIB paper (JAIR 14, 2001,
  [arXiv:1106.0669](https://arxiv.org/abs/1106.0669)) is the closest methodological
  ancestor of what we should do.** He scored **human world/national-championship records**
  against a **double-dummy ground truth**, measuring *"how frequently humans make mistakes
  at the bridge table"* as P(error at trick n), and found *"the error profiles of the two are
  quite similar."* He also states the bias explicitly: *"this method of analysis favors gib
  slightly… human declarers often work to give the defenders problems that exploit their
  relative lack of information, and that tactic is not rewarded."* **Generalised: a
  perfect-information oracle used as a ruler undervalues deception and information-gathering.
  Carcassonne is perfect-information with stochastic draws, so we dodge most of this — but it
  applies directly to any clairvoyant reference we use.** And he annotates every match margin
  with its σ (*"a total of 6.4 imps (a 0.3 standard deviation event)"*) and refuses to
  conclude from 14 deals.
- **Ginsberg's third luck-control strategy is the curated position suite.** GIB entered the
  **1998 Par Contest** at the world championships: *"gib joined a field of 34 of the best card
  players in the world, each player facing twelve such problems over two days… finished
  twelfth."* **12 problems × 35 competitors produced a meaningful ranking** because the
  positions were pre-selected to discriminate and luck was removed by construction.
- **Scrabble shows exhibitions are worthless and continuous play is not.** Maven beat Adam
  Logan 9–5 (1998) and Quackle beat David Boys 3–2 (2006) — 14 and 5 games with independent
  racks. The number that actually settled the question came later: **Grandmaster Kenji
  Matsumoto played 500 games against Quackle; Quackle won 252–248 (~50.4%)**
  ([Del Solar](https://medium.com/@14domino/scrabble-is-nowhere-close-to-a-solved-game-6628ec9f5ab0)).
  Modern **BestBot** runs **~58–60% against top humans** and the community's own framing is
  *"modestly better than the best humans"*, established by **continuous online play against a
  named reigning champion**, not by an exhibition
  ([Woogles blog](https://blog.woogles.io/posts/2025-05-04-the-mathematics-and-algorithms-behind-bestbot/)).
- **⭐ Thomas, "Variance Decomposition and Replication in Scrabble" (2011,
  [arXiv:1107.2456](https://arxiv.org/abs/1107.2456))** proposes a **"Two-Sided Draw
  Method"** letting players face identical tile sequences across matches **while maintaining
  the appearance of standard bag-based draws**, explicitly analogised to duplicate bridge.
  **This is the closest published deck-pairing protocol for a tile-draw game and transfers
  to Carcassonne directly.**
- **⭐ Hanabi / Other-Play (Hu et al., ICML 2020,
  [PMLR](https://proceedings.mlr.press/v119/hu20a/hu20a.pdf) §6.5) is the design to copy.**
  **N=20** club players, each played **one game with each of two bots in random order**,
  single-blind. *"Since in Hanabi the exact deck being used can make a huge difference… to
  reduce the variance of our results **we play each seed by two different players, one for our
  OP agent, and one for the control.** Importantly, to prevent any adaptation advantages, we
  alternate the order between which bot came first."* **Paired analysis: won 15 of 20 per-seed
  comparisons, tied 2, lost 3 → p = 0.0041.** Twenty human-games, p<0.005, purely from
  seed-pairing against a control.
- **Siu et al. (NeurIPS 2021, [arXiv:2107.07630](https://arxiv.org/abs/2107.07630))**: N=29,
  single-blind, familiarisation game then two blocks of three, IRB protocol, **$10 gift card
  + $50 top-scorer bonus, $350 total**. Findings that matter to us: the **only** significant
  score predictor was **block (p=0.009)** — a human learning effect that must be designed for;
  and humans **preferred the rule-based bot on nearly every subjective metric despite no score
  difference**, with **experts rating the learned agent worse than novices did**. *Qualitative
  preference and objective strength dissociate — plan for that.*
- **Diplomacy/CICERO** ([tech report](https://noambrown.com/papers/22-Science-Diplomacy-TR.pdf)):
  **40 anonymous games** on webDiplomacy, mean score 25.8% vs opponents' 12.4%, humans **not
  told** they were playing an AI (revealed afterwards, consent requested). *"CICERO passed as
  a human player for 40 games… with 82 distinct players, and no in-game messages indicated
  that players believed that they were playing with an AI agent."* ⚠️ **The 40-game human
  result has no confidence interval and it is the paper's weakest point**; by contrast
  **SearchBot** ([arXiv:2010.02923](https://arxiv.org/abs/2010.02923)) played **116 games and
  reported 26.6% ± 3.2%**. Copy SearchBot's habit, not CICERO's.

### 4.5 Qualitative expert assessment — the channel Joshua wants

**The precedent is much stronger than expected. The calibration warnings are severe.**

**The cautionary half — Deep Blue.** Kasparov on the 1996 Game 1 pawn move: *"a wonderful
and extremely human move… I could feel — I could smell — a new kind of intelligence across
the table"* ([TIME](https://time.com/archive/6728763/the-day-that-i-sensed-a-new-kind-of-intelligence/)).
It was brute force six moves deep. In 1997 he read **36.axb5/37.Be4** as *"too sophisticated
for a computer"* and accused IBM of human intervention — **retracted in 2016**; modern
engines endorse the move but it was **not uniquely winning**
([ChessBase](https://en.chessbase.com/post/deep-blue-s-cheating-move)). And **Deep Blue's
44th move in Game 1 was reportedly a bug** — Murray Campbell to Nate Silver: the machine
*"was unable to select a move and simply picked one at random,"* and *"Kasparov had concluded
that the counterintuitive play must be a sign of superior intelligence. He had never
considered that it was simply a bug."*
⇒ **In the most-scrutinised man-machine match in history, a reigning world champion twice
read machine behaviour as deep understanding — once about pure brute force, once about a
crash fallback — and separately resigned a drawn position after a genuinely bad machine
move.** Unstructured expert impression is a *hypothesis generator*, not evidence of strength.

**The constructive half — and it is genuinely strong:**

- **AlphaGo move 37**: [Michael Redmond 9p](https://en.wikipedia.org/wiki/AlphaGo_versus_Lee_Sedol)
  called it *"creative"* and *"a move that most professional players would not have
  considered"*; An Younggil 8p called it *"a rare and intriguing shoulder hit."* **And the
  same channel caught a real blind spot**: in Game 5 Redmond identified AlphaGo as having
  missed the *tombstone squeeze* tesuji, with a mechanistic explanation (*"Humans are taught
  to recognize the specific pattern, but it is a long sequence of moves, made difficult if
  computed from scratch"*).
- **⭐ McGrath et al., "Acquisition of Chess Knowledge in AlphaZero," PNAS 2022**
  ([arXiv:2111.09259](https://arxiv.org/abs/2111.09259)) — **Vladimir Kramnik, 14th World
  Chess Champion, is a listed co-author, and the abstract states the paper provides
  "qualitative analysis from chess Grandmaster Vladimir Kramnik."** This is the cleanest
  citable precedent that **an elite player's written judgement can be a formal, peer-reviewed
  results section.** Kramnik is also co-author on
  ["Assessing Game Balance with AlphaZero"](https://arxiv.org/abs/2009.04374).
- **Sadler & Regan, *Game Changer* (New In Chess, 2019)** — 416pp, Kasparov foreword,
  Hassabis introduction, written with **exclusive access to the dev team and 2,000+
  unpublished AlphaZero games**, published by DeepMind as part of the AlphaZero announcement;
  won **both** the ECF and FIDE 2019 Book of the Year awards. ⚠️ Whether it was a paid
  commission is not published.
- **⭐ Bill Robertie, *Learning from the Machine* (The Gammon Press, 1993)** —
  [listing](https://www.bkgm.com/books/Robertie-LearningFromTheMachine.html). **An entire book
  that is an annotated transcript of a 31-game match between a two-time world champion and
  TD-Gammon, played in October 1991 explicitly to evaluate the program's strength**, with a
  quantified verdict (an expert would average 0.20–0.25 ppg against it). **This is the single
  closest precedent to what §5 Format C proposes.** Robertie separately published the rollout
  analysis showing TD-Gammon's 24-23 split beat the conventional slot — *"Within a few years,
  slotting had disappeared from tournament play"* ([TD-Gammon](https://en.wikipedia.org/wiki/TD-Gammon)).
  **Elite adoption of the bot's novelties is itself a strength signal, and it was published by
  the pro, not the lab.**
- **Kit Woolsey** — world-class in *both* bridge and backgammon — is the standing adversarial
  reviewer, publishing structured critiques of Snowie and JellyFish including the specific
  failure taxonomy quoted in §4.2.
- **Catan gives the template for honest small-n qualitative work.** Szita et al. (ACG12 2009,
  [PDF](https://spronck.net/pubs/ACG12Szita.pdf)) §5.2: *"the first author, who is an
  accomplished Settlers of Catan player, played a few dozen games… **While the number of games
  played is not sufficient for drawing statistically relevant conclusions**… we assess that the
  SmartSettlers agent makes justifiable moves that often coincide with moves that a human would
  play. Still, we found that an expert human player can confidently beat the SmartSettlers
  agent."* They then give a **mechanistic** diagnosis (over-prefers ore/wheat and roads,
  under-builds settlements, because a settlement needs four resources and the payoff sits
  beyond the MCTS horizon). **That is qualitative assessment doing diagnostic work a win rate
  could not.**
- **⭐ The rubric to copy is CICERO's dialogue evaluation**: *"two expert Diplomacy players
  annotated model-generated messages in 126 Diplomacy situations… **aware that the messages
  were model-generated, but not which model generated which**"*, scored on three fixed rubric
  items. **Blind-to-condition, multiple raters, explicit rubric.**

### 4.6 What elite players get paid

**Two templates, and which applies is set by whether there is a media audience.**

| Model A — prestige match | |
|---|---|
| Kasparov–Deep Blue 1997 | $700k winner / $400k loser |
| Kasparov–Deep Junior 2003 | *"Total one million dollars, **$500,000 Kasparov fee**, prize money $500,000"* ([ChessBase](https://en.chessbase.com/post/kasparov-vs-deep-junior-match-details)) — the cleanest published fee+prize split |
| Kasparov–X3D Fritz 2003 | **$150,000 flat for playing** + $25,000 for the draw |
| Kramnik–Deep Fritz 2006 | **$500,000 for playing, $1,000,000 if he won** |
| Lee Sedol–AlphaGo 2016 | **$150,000 appearance fee + $20,000 for the one game he won** = $170,000 |
| Ke Jie–AlphaGo 2017 | $300,000 to the losing side for three games |
| **⭐ Shin Jinseo–KataGo, Seoul, 21 July 2026** | **₩150M appearance fee (~$108k) + ₩50M per win + a Genesis G90**, 3 games at **2-stone handicap to the human**; Shin won 2–1 ([Korea Times](https://www.koreatimes.co.kr/lifestyle/people-events/20260721/humans-strike-back-shin-jin-seo-defeats-top-go-ai-katago-2-1)) |

| Model B — research experiment | |
|---|---|
| Claudico 2015 | **$100,000** in appearance fees across 4 pros |
| Libratus 2017 | **$200,000**, **$20,000 floor each**, remainder by relative performance |
| **Pluribus 2019** | **$50,000 divided among 13 pros by performance** — Elias and Ferguson **$2,000 each**, +$2,000 to Ferguson for outperforming Elias. Note how small this is for named pros in a *Science* paper. |
| Hanabi (Siu et al.) | **$10 + $50 bonus, $350 total for 29 participants** |

**Where nothing is published, we say so:** no purse for *any* TD-Gammon engagement; no fees
disclosed for the eight NooK bridge champions; no purse for Maven–Logan or Quackle–Boys;
Shogi Denou-sen per-player 対局料 are explicitly **非公表 (undisclosed)**.

**Honest comparables for a Carcassonne champion** (no TV audience attached): the **research
model, $2k–$50k pooled**, or an expert-network hourly band. Expert networks: junior
$75–150/hr, senior $200–300/hr on GLG; practitioner reports of $300–500/hr baseline and
$600–1,500/hr for deep-technical. Chess coaching reality-check from the live
[Chess.com coach directory](https://www.chess.com/coaches): **IM Mark Plotkin $85/hr;
GM Rolando Kutirov (FIDE 2500) €20–30/hr on bundles** — the "$100–150 GM rate" is the top of
the market, not the median. The circulating "$500–2,000/hr for a Carlsen tier" figure is
speculative blog content; do not cite it.

**And note the 2026 Go precedent's design choice: a handicap was set so the human could
plausibly win, which is what made the event worth staging at all.**

---

## 5. Proposed formats

### 5.1 The statistics — why a 5-game match is theater

Our champion's per-game win rate against a strong human is **unknown** (that is the whole
point of E4). Assume 0.55–0.65, i.e. +35 to +108 elo — the band our best fair agent shows
against strong search opponents.

**Match win probability, best-of-N, ignoring draws:**

| per-game wr | elo | bo1 | **bo3** | **bo5** | bo7 | bo9 | bo11 | bo21 | bo31 | bo51 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.55 | +35 | .550 | .575 | **.593** | .608 | .621 | .633 | .679 | .713 | .764 |
| 0.60 | +70 | .600 | .648 | **.683** | .710 | .733 | .753 | .826 | .872 | .926 |
| 0.65 | +108 | .650 | .718 | **.765** | .800 | .828 | .851 | .923 | .958 | .986 |
| 0.70 | +147 | .700 | .784 | .837 | .874 | .901 | .922 | .974 | .990 | .999 |
| 0.80 | +241 | .800 | .896 | .942 | .967 | .980 | .988 | .999 | 1.000 | 1.000 |
| 0.935 | +463 | .935 | .988 | .998 | .999 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

**A 55%-per-game engine wins a Bo5 59.3% of the time — 9 percentage points above a coin
flip. It LOSES the match 40.7% of the time.**

**What a Bo5 result actually licenses — likelihood ratios, wr 0.65 vs wr 0.50:**

| Bo5 score | P(score \| wr=0.50) | P(score \| wr=0.65) | **Likelihood ratio** | Read |
|---|---:|---:|---:|---|
| 5–0 | .031 | .116 | **3.7 : 1** | weak-to-moderate |
| 4–1 | .156 | .312 | **2.0 : 1** | weak |
| **3–2** | .313 | .336 | **1.08 : 1** | **no information at all** |
| 2–3 | .313 | .181 | 0.58 : 1 | no information |

**A 3–2 win is 1.08:1 evidence.** Starting from a 50/50 prior you finish at 52%. That is the
quantitative form of Joshua's own intuition, and it is why the qualitative channel is not a
consolation prize — **in a Bo5 it is the entire signal**.

**And the last row of the first table is the flip side.** Our measured luck floor is
**6.50% [Wilson 3.84, 10.80]** — a tier-1 greedy agent takes 13/200 off the champion despite
a **+478 ± 52 elo** gap (`results.csv luckfloor_champ_k4x688_vs_greedy_b54e9`, DECISIONS
2026-07-27/28). **So a single loss to a world champion is not evidence against superhuman
play, and we must say so publicly BEFORE the match, not after.**

**What a longer series would establish** — from
[measurement/human_anchor/LUCK_FLOOR.md](human_anchor/LUCK_FLOOR.md), our own measured
numbers (σ_game ≈ 22.2 pts, σ_pair ≈ 14.5 pts, deck-luck share of margin variance ≈ **0.14**):

| true wr | implied point edge | n (naive per-game) | n (seat-swap deck-paired) |
|---:|---:|---:|---:|
| 0.52 | +1.1 | 2,398 | 1,309 |
| 0.55 | +2.8 | 381 | 209 |
| 0.60 | +5.6 | 93 | 52 |

> ⚠️ **The honest correction to the brief's premise.** Deck-pairing is our native measurement
> and it is the right default — but in Carcassonne it is **worth only ~14%**, not the ~2×
> that duplicate bridge or poker suggest. Our own decomposition says **deck identity explains
> only ~0.14 of margin variance; ~0.86 is play divergence.** Seat-swap pairing cuts the games
> needed by ~14%, no more. Schmid's textbook warning applies with extra force here:
> duplicate *"provides only a modest improvement"* and *halves your datapoints*. **Do not
> sell a human on a duplicate-deck protocol by promising it makes the match short.**
>
> ⚠️ **And there is a second, human-specific problem the brief flagged implicitly.** "The
> human plays both sides of the same decks on different days" **leaks the tile order to a
> memory-bearing opponent.** Agents replay a deck blind; a human does not. The leak biases
> *against* us (conservative) but it destroys the equal-conditions logic and any strong
> player will notice and object. **Format B below replaces human-vs-himself pairing with the
> Pluribus control-replay design, which has no memory problem.**

### 5.2 Format A — "The Control-Replay Series" (the real measurement)

**This is the recommended primary format.** It is the Pluribus 1H+5AI trick
(*"we replay each hand with a copy of Pluribus in the human's position"*) fused with
Other-Play's seed-pairing, adapted so the human never replays a deck.

**Protocol.** For each deck seed *s*:
1. The human plays deck *s* against the champion (seats alternated across seeds), yielding
   margin `M_human(s)`.
2. **Offline and free**, we replay deck *s* with a **control agent** in the human's exact
   seat against the same champion at the same config, **M times** (M ≈ 50), yielding a
   near-exact `E[M_control(s)]`.
3. The statistic is `D(s) = M_human(s) − E[M_control(s)]`, and the claim is a paired test on
   `D`.

**Why this is better than seat-swap pairing here:**
- **No memory leak** — the human sees each deck once.
- **No halving of datapoints** — unlike true duplicate, each human game remains one
  observation.
- **The control's own variance is driven to ~0 by compute**, which we have and the human's
  time is not.
- **It answers the right question directly**: *how much better or worse than a known agent is
  this human, on identical decks?* That places the human on our existing ladder rather than
  producing an isolated win rate.
- **Choice of control is the lever**: run several controls per deck (tier-1 greedy, h800,
  h3200-tier RoD-v2 iter_02, the champion itself) and the human is **bracketed**, not merely
  scored. This turns "did we beat a champion" into "where on our measured ladder does a world
  champion sit" — which is the actual E4 deliverable and the structural blocker #1 the
  program has been stuck on since 2026-06-18.
- ⚠️ **It is NOT AIVAT and must not be described as such.** AIVAT needs the debiased agent's
  own action distribution; we do not have the human's. This is a control-variate on the
  *deck*, which caps its benefit near the 0.14 luck share. Its real value is **calibration
  against the ladder**, not variance reduction.

**Size.** 30 decks is the working target: ~10–15 h of the human's play time (see §6),
enough for the regret channel below to carry the statistical load, and enough to bracket
them between two adjacent ladder rungs even if the direct win rate stays inconclusive.

### 5.3 Format B — "The Regret Exam" (the cheapest powered signal)

**This is the backgammon-PR paradigm, and we built the infrastructure for it months ago and
never used it.**

Two components, both already coded:

**(i) The curated position suite** — `scripts/human_anchor/build_suite.py` produces a JSONL
suite of 200–500 positions with **objective ground truth**: exact-solver `child_values` for
K≤4 endgames (K=2 free from the on-disk cache) and h6400 midgame labels, stratified by
`meeple_scarcity` / `farm_fight` / `closure_race` / `midgame_generic` / `endgame_k{K}`. It
already has a `--score` mode taking `{position_id: chosen_action_id}` and emitting
**per-stratum mean regret and best-move match rate**.

**This is Ginsberg's 1998 Par Contest, and it is the highest information per minute of
expert time available to us.** 100–150 positions is ~2–4 hours; each position is an
independent observation with a known correct answer, and the champion's regret on the same
suite is free to compute. The output is a **band-classified error rate** in the shape GNU
Backgammon publishes — and the same suite is already earmarked as the Phase-5 analyzer's
held-out validation set, so the work is dual-use.

**(ii) Per-decision regret on the played games.** Every game from Format A is a
`root_replay` record (deck seed + action log) via `play_harness.py`'s signed manifests and
the Android app's archive schema. Score **every human decision and every champion decision**
against the deepest reference we can afford, and report mean regret per decision with
game-clustered standard errors.

**Why this is the load-bearing channel:** ~72 searched decisions per player per game means a
30-game series yields ~2,000 scored human decisions. Bower's number — **400 matches to
establish a 55% edge by outcome, versus bot-separated-from-best-human on one 19-point
match** — is the precedent for the efficiency gain. Backgammon's own reliability guidance
(**"20+ matches"**) is where the 30-game target in Format A comes from.

⚠️ **Three caveats that must ship with this channel:**
1. **Decisions within a game are correlated** — cluster by game, do not treat 2,000 decisions
   as 2,000 independent samples.
2. **Ginsberg's bias** — a clairvoyant/deep reference undervalues moves that create problems
   for an opponent with less information. Carcassonne is perfect-information with stochastic
   draws so most of this dodges us, but our own CL-045/CL-048 result that clairvoyant edges
   wash out ~4:1 under PIMC is the same phenomenon, and **the reference must be a FAIR
   reference or the bias must be stated**.
3. **We have never calibrated the regret metric's discriminating power on known-different
   agents.** Before spending an expert's time, run the free pre-flight in §6.

### 5.4 Format C — "The Assessment" (the qualitative channel, structured)

Joshua's requirement — *a strong player can judge from the style whether the agent is
strong* — is legitimate and has excellent precedent (§4.5). But Kasparov's two false reads
say it must be **structured, blind, and rubric-driven**, not a vibe check.

**Design, copying CICERO's annotation protocol and Robertie's book:**

1. **Blind move-quality panel.** Take ~120 positions from real games. For each, present 2–4
   candidate moves — the champion's pick, the human's pick (where they differ), a deep-search
   pick, and a plausible decoy — **unlabelled and order-randomised**. The expert ranks them
   and writes one line of reasoning. Score against exact/deep ground truth. This measures the
   *expert* and the *agent* on the same axis, and it is the only way to know whether the
   expert's judgement is itself calibrated.
2. **Disagreement review.** Mine the positions where the human and the champion disagree —
   the Depreli protocol, but human-vs-bot rather than bot-vs-bot, which fixes Keith's own
   stated validity limit (*bot-vs-bot disagreement positions may not resemble the positions
   humans reach*). Roll those out deep. Ask the expert to explain **why** they would deviate.
   **This is where a real weakness would be found, if one exists.**
3. **A written assessment as the deliverable.** ~2,000–4,000 words: does the agent play like a
   strong player; where does it look alien; where does it look *weak*; would they adopt any of
   its ideas. Precedent: Robertie's *Learning from the Machine*, Woolsey's bot critiques,
   Kramnik's named contribution to a PNAS abstract. **Offer co-authorship**, not just a fee —
   the precedent says that is what elite players actually valued.
4. **Expect preference and strength to dissociate.** Siu et al. found humans preferred the
   rule-based agent on nearly every subjective metric with *no* score difference, and that
   **experts rated the learned agent worse than novices did**. Pre-register that the
   qualitative verdict is a *diagnostic*, not a strength measurement, so a negative aesthetic
   read cannot be spun either way after the fact.

### 5.5 Format D — the public exhibition (Bo5), if and only if it is wanted

Bo5 matches the CCL's own knockout format so it is the only "match" shape the community will
read as legitimate. **Its purpose is publicity and access, not measurement.** Run it *after*
Formats A–C, publish the pre-registered statistics table from §5.1 *before* it is played, and
follow the 2026 Shin Jinseo template if we want a spectacle the human can plausibly win
(a stated handicap, e.g. the champion at a reduced budget, is more honest than a rigged
narrative). Under the WC's own rules the second seat wins ties — if we play a "tournament
rules" exhibition we must implement gap #1 first (§1.4).

---

## 6. Recommended sequence, with costs

| # | Step | Cost | Gate to proceed |
|---|---|---|---|
| **0** | **Free pre-flight, no humans involved.** (a) Calibrate the regret metric: score two agents of *known* elo separation (champion vs h800, champion vs RoD-v2) on the position suite and on played games, and measure how many positions/decisions are needed to separate them. (b) Re-score existing paired archives under "starting player loses ties" and count how many outcomes flip (§1.4 gap 1). (c) Generate the K=3/4 suite (needs boxes). | ~1 box-day. No money. | If regret cannot separate two agents 100 elo apart on ≤150 positions, **Format B is dead** and the plan reverts to a long series. **Do not skip this** — it is the pre-flight-smoke rule applied to a human's time. |
| **1** | **Resolve the venue.** Research Yucata / Brettspielwelt / JCloisterZone / the official app (unreached this session). Buy a BGA Premium account (~$30/yr) to read the Carcassonne leaderboard and identify targets by rating. Decide the play interface: our CLI `play_harness.py`, a thin web wrapper on it, or an Android sideload. | ~$30 + a day. | A venue where 2p base+farmers at 15 min/player is playable **and** where a bot is not prohibited. **BGA is excluded** (§2.3). |
| **2** | **Recruit one expert for the Regret Exam (Format B, position suite only).** ~2–4 h of their time. This is the cheapest possible real signal and requires no match, no venue, no anti-cheat. | **$500–$1,500 honorarium** (research model; expert-network equivalent would be $600–$6,000, but this sport pays £30 for a national title — a four-figure sum is already unprecedented). | Their regret vs the champion's regret on the same suite. This alone may answer the superhuman question. |
| **3** | **The Control-Replay Series (Format A), 30 decks**, same or a second expert, plus per-decision regret on every game. | ~10–15 h of play. **$2,000–$5,000**, structured as the Libratus/Pluribus model: **a floor plus a bonus on the variance-reduced statistic, with the statistic not disclosed until the end.** Compute cost is ours and trivial (30 decks × 50 control replays ≈ 1,500 games ≈ hours on two boxes). | A deck-paired margin placing the human on our ladder, plus ~2,000 scored decisions. |
| **4** | **The Assessment (Format C)**, blind panel + disagreement review + written piece. Offer **co-authorship**. | 4–8 h. **$1,000–$3,000**, or bundled with step 3. | The written deliverable — the thing Joshua actually wants — plus any identified weakness. |
| **5** | **Public exhibition (Format D)** and/or contest registration. | Travel + fee, **$2k–$10k**, in-person adds flights/hotel (the WC pays neither). | Only after 2–4 give a defensible claim, and only after gaps #1–#3 in §1.4 are closed. **This is the trigger that unholds G1 (pondering).** |

**Total for steps 0–4: roughly $3,500–$10,000 and ~2 box-weeks.** Steps 0–2 cost under
$2,000 and could produce a decisive answer.

### 6.1 Named, plausibly approachable candidates

| Who | Credential | Why approachable |
|---|---|---|
| **⭐ Alexey Pegushev** ("Alexey_LV", Latvia) | **WC 2023 runner-up**; MSO 2026 winner; reported **six-time national champion and highest-ever-rated BGA Carcassonne player** | **Runs [Alexey's Carcassonne Channel](https://www.youtube.com/@AlexeysCarcassonneChannel), which does move-by-move analysis of viewer games.** He *already does the deliverable we want*, in public, for free. Best first contact by a wide margin. |
| **Raf Mesotten** (Belgium) | **3rd at WC 2025** | Runs [carcassonnebelgium.weebly.com](https://carcassonnebelgium.weebly.com/), which maintains the WC results archive and a BGA-ELO page — i.e. already an analyst as well as a player. |
| **Matt Tucker** (GB) | **WC 2023 champion** | Reachable via MSO / UK Games Expo, who run the UK championship. |
| **Xiangyu Qin** (China), **Daniel Angelats** (Catalonia) | **WC 2025 / 2024 champions** | Via Swan PanAsia / carcassonne.cat national organizers. |
| **Nallerheim** (CCL 2026), **bignacho610** (KOC WC 2026), **Kithara** (KoC ToC 2025) | Current online-circuit champions | Via [carcassonne.gg](https://carcassonne.gg/), which is also the natural **institutional** partner — approaching the hub rather than an individual may be the better opening move. |

**Pitch framing that follows from the research:** this community has *never* had its skill
measured, plays for a trophy and a £30 prize, is visibly aware that single-game knockouts are
luck-dominated (a first-time tournament player won the 2023 world title), and has an active
analysis culture on YouTube and carcassonne.gg. **Offer them the measurement, co-authorship,
and the annotated games — not primarily the money.**

### 6.2 Anti-cheat and verification, from the human's side

A strong player's first objection will be *how do I know it isn't cheating*. We can answer
this better than almost any project could, and should lead with it:

- **The agent is audited-honest.** The fair champion is non-clairvoyant PIMC — it never sees
  the real deck (Phase 0.1/0.4 audits green). We can hand over the audit.
- **Pre-commit the decks.** Publish `SHA256(seed ‖ salt)` for every deck **before** play,
  reveal the salt afterwards. This proves the tile order was fixed in advance and not dealt
  adaptively — the single strongest guarantee, and it costs nothing.
- **Signed game records.** `play_harness.py` already writes a manifest with git rev, resolved
  leaf env, config hash, leaf hash, deck seed + deck hash, and a **tamper-evident content
  signature** over the canonical manifest + moves. Every game is independently verifiable and
  replayable via `root_replay`.
- **Reproducibility on demand.** Any move can be re-derived from the record; a third party
  can rerun the agent on the same position.
- **Symmetric obligation.** Offer the same in reverse — the human's environment is theirs, we
  do not police it, and we say publicly that we are not treating their play as adversarial.
- **Disclosure.** Unlike CICERO (which played 40 anonymous games and revealed afterwards), we
  should be **disclosed from the start**. CICERO's rationale for concealment — that players
  would hunt the bot — does not apply to a 2-player abstract, and concealment on a platform
  whose ToS forbids bots would be indefensible.

### 6.3 Constraints from our side

- **~1.7 s/move on a Pixel 9 Pro, ~2.2–3.5 s/move on desktop**, at the full k4×688 (2752 sim)
  fair budget ⇒ **~26% of a 15-minute sudden-death clock**. Comfortably legal. The engine is
  clock-safe as-is.
- **The compute lever is unavailable where it matters** — CL-060's +50 elo at 4× budget sits
  at **91% of clock** and the 8× config at **178%**
  ([TOURNAMENT_TIMING](../docs/research/TOURNAMENT_TIMING_2026-07-26.md)). We cannot buy
  strength for a clocked match.
- **Base + Farmers, current scoring, no River** — matches the competitive standard exactly.
  ⚠️ **Pre-flight check owed:** confirm on disk that our engine scores farms at **3 pts per
  adjacent completed city** and **2-tile cities at 4 pts** (the "International rules"
  configuration). The Android playtest verified scoring in play, but nobody has explicitly
  checked these two numbers against the WC text.
- **Three rules-fidelity gaps** — ties, fixed start tile, pondering (§1.4). Gap 1 is new and
  unmodelled; gaps 2 and 3 are already triaged as "bundle with G1".
- **The champion is classical, not learned.** If any public claim is made, it must say so —
  the superhuman goal is about the *learned* components exceeding the heuristic, and a
  classical-search champion beating a human would be a strength result, not progress on
  structural blocker #2.

---

## 7. Open decisions for Joshua

1. **Do we pursue this at all now, or after the C3-intra confirm and the current queue land?**
   Steps 0–1 are free and can run in parallel with anything.
2. **Ties (§1.4 gap 1).** Measure first (free), then decide whether to model "starting player
   loses ties". It changes the value function asymmetrically by seat and is not in
   LEVER_INDEX. **Recommend: measure now, decide later.**
3. **Budget.** Is $3,500–$10,000 across steps 2–4 in scope? Is a **$500–$1,500 single-expert
   position-suite exam** (step 2) approved on its own? That is the decision that actually
   unblocks E4.
4. **Who to approach first.** Recommend **Alexey Pegushev**, and in parallel
   **carcassonne.gg as an institution**. Both are public and cost nothing to email.
5. **Disclosure posture.** Confirm: fully disclosed, no anonymous play, and **BGA is off the
   table**. (Recommend yes to all three.)
6. **E4 unpark.** This memo is the plan G1 was held for. Does E4 come off "PARKED", and does
   **G1 (pondering)** move from HELD to scoped — noting that G1 only matters for a *clocked*
   match (steps 3–5), not for the position-suite exam.
7. **2026 WC timing.** The 20th WC is 1–3 months away and the date is ambiguous in the
   organizers' own sources. Do we want any 2026 presence (spectating, contacting organizers,
   recruiting at the event), or is 2027 the realistic target?

---

## Appendix — items explicitly NOT verified

- **WC 2026 date**: two official pages give 29.08.2026 and 24.10.2026. Unresolved.
- **BGA ToS §VIII wording**: high-confidence from two agreeing secondary sources; the primary
  page is JS-truncated. **Not primary-verified.**
- **A fabricated BGA bot clause was caught and discarded** — see the boxed warning in §2.3.
  If it reappears, it is invented.
- **BGA ELO scale**: official sources contradict each other (0-based vs 1500-based).
- **Alternative platforms** (Yucata, Brettspielwelt, JCloisterZone, official app): **not
  researched** — the session's 200-call web-search budget was exhausted. Top open item.
- **BGA Carcassonne leaderboard**: Premium-gated and JS-rendered; no names or ratings obtained.
- **Duplicate decks**: negative finding from absence of evidence; BGG and Carcassonne Central
  were both hard-blocked (403), so club-level experiments cannot be ruled out.
- **WC prize specifics beyond "a trophy"**; whether organizers pay any finalist travel.
- **Czech 25-min clock, Belgium's 2024 4-player qualifying rounds, Italy's ruleset**:
  snippet-sourced only.
- **NooK challenge margin** (909 pts / ~67 of 80 sets): secondary sources disagree and the
  official results page shows placeholder text; **no peer-reviewed paper exists**.
- **Appearance fees**: none published for TD-Gammon, the NooK champions, Maven–Logan,
  Quackle–Boys, or Denou-sen (explicitly 非公表). Kasparov's 1996/1997 appearance guarantees
  are unpublished.
- **Deep Blue's move-44 bug**: substance corroborated, exact wording via secondary rendering.
- **Fan Hui's "not a human move" quote** and the **1-in-10,000 policy-probability figure**:
  secondary-only (wired.com fetch-blocked); the attribution of the latter to David Silver is
  unverified.
- **Whether DeepMind paid Sadler, Regan, Fan Hui or Kramnik**: not published.
