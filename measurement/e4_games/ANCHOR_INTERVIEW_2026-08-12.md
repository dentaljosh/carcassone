# Anchor interview — Joshua's self-described strategy vs the champion (2026-08-12)

**Status: CAPTURED 2026-08-12 (in-session, verbatim). This is primary data for the
"human-strategy scripted opponent" lever (LEVER_INDEX row minted 2026-08-12) and a prior
for the E4 autopsy's mechanism tags. It is self-report from a NONSTATIONARY anchor — treat
as hypotheses about his play, not measurements of it. He expects to add more as he plays.**

Related: [E4_UPDATE_20260812.md](E4_UPDATE_20260812.md) ·
[PRO_STRATEGY_SCAN_2026-08-12](../../docs/research/PRO_STRATEGY_SCAN_2026-08-12.md) ·
autopsy census `../e4_autopsy_20260812/CENSUS.md`.

---

## 1. Verbatim notes

> sometimes i lay down a farm early. sometimes he lays it down early. i might challenge it
> right away.
>
> i notice he tends to build large cities that probably wont close. if they are getting on
> the bigger side, i will attempt to sneak a meeple in, sometimes late in hte game
>
> if i see a farm is valuable, i will try to tie it or steal from him. sometimes this
> requires planning 2-4 tiles in advance, so i look at remaining tiles and try to see if
> its realistic to get there.
>
> i try to keep at least 1 meeple in my hand so i can quickly collect on easy to close
> vacant cities.
>
> if i see he is out of meeple, i am more okay with leaving a something juicy unclaimed
>
> if he has meeple and i have a throwaway tile, i will place it somewhere where it doesn't
> add to anything unclaimed that is already worth more than a few points
>
> i learned from him to keep a big city and road as mine, even if there is no plan to
> close it. this was i at least collect the unfinished points at game end and have
> somewhere to dump otherwise worthless tiles. i think he does this with roads too early.
> sometimes i see his road is getting long and thats my signal to tie it up. but i'm
> generally less bullish on roads than him.
>
> its hard for me to pass up on closing unclaimed cities. i hesistate if I've already
> surrendered the farm to him because he gets an easy 3 points there.
>
> sometimes it takes 2 meeple to secure a city. sometimes 3 for a single farm. you can
> sometimes see that the game will turn on a single large feature, and in those cases,
> you have to take chances.
>
> he is good at blocking my cloister completions. i'm more cautious about grabbing them
> now. he loves to put 2 cloisters next to each other, which is smart. sometimes he puts a
> cloister down and claims it when its clear he wont close it. i scratch my head and
> figure he's happy with hte 7 or 8 points he's confident he'll get for it, even if he
> cant reclaim the meeple.
>
> i think i did go less aggressive on farms, especially early on in the game, since my
> first few games against him. some games, at the end, the farms really aren't worth much.
> so i started to count the cities, especially late in game, and surrender a farm
>
> but he will sometimes start a brand new farm mid-late in the game, and i'll be surprised
> that he manages to close 2 or 3 cities around it. and then i'll sometimes scramble to
> sneak in.
>
> also, i'll tell you my opinion. the goal is to get him superhuman. so i dont mind
> assisting myself with things a good human is certainly doing. that means, tile bag peak
> because a pro is counting. and i'll probably ask for a menu of virtual score counts,
> because these are things someone can easily calculate with enough time and practice.
> its mechanical. its also why i'm not so against and occasional undo button. sometiuems
> its a genuine brainfart, like i forgot to add the meeple when i finally got the tile i
> was waiting for. presumably these are less common in good focused players.
>
> but these aren't priority now because i'm beating him even without these. and again, i'm
> newish to the game. i expect a pro to destroy me. i expect a good bot to destroy me.
>
> i'm generally confused by the idea of the grader. how is he grading the bot? what does
> he know that the bot doesn't know?
>
> he has a move where he adds to my city to prevent me from closing it. its smart because
> an open city is worth half as many points and it locks up the meeple. so its smart to
> sacrifice the 1 or 2 points the tile adds to my score.

---

## 2. Structured extraction — strategy elements → mechanisms

| # | element (his words, compressed) | mechanism class | converges with | Joshua-bot rule candidate |
|---|---|---|---|---|
| J1 | sneak a meeple into his large won't-close cities, sometimes late | late majority-steal join | scan **F2**; census F2 tags; scan **F1** (the champion *builds* the exploitable object) | if opp city ≥ N tiles and open-edges ≥ 2 and tie reachable ⇒ prioritize the join |
| J2 | tie/steal valuable farms, planning 2–4 tiles ahead off remaining-tile counts | deck-counted multi-tile farm attack | farm-war file (H1 unresolved); he IS deck-counting | plan k-tile chains to farm entry when P(needed tiles) clears a bar |
| J3 | keep ≥1 meeple in hand for quick closes of vacant easy cities | own-reserve floor | census hold-vs-spend **1.9×**, `road→pass` 48 | never place the last meeple except on closures/majority swings |
| J4 | if he's out of meeples, OK leaving juicy things unclaimed | **opponent**-reserve conditioning | scan **F3** | contest/claim urgency scales with opp reserve |
| J5 | throwaway tiles go where they DON'T feed unclaimed value (if opp has meeples) | value-starving dump placement | novel (not in scan or killed set) | dump tiles minimize Δ(unclaimed feature value) when opp reserve > 0 |
| J6 | keep one big city+road as endgame-points home + tile dump; tie up his long roads; less bullish on roads than him | anchor-structure economy; road skepticism | census `road→pass`; he says he LEARNED the anchor-structure from the champion | maintain 1 city + 1 road anchor; join opp road when length ≥ N |
| J7 | hesitates closing unclaimed cities once the farm is surrendered (each close = +3 to his farm) | city-close × farm-majority interaction | novel — an interaction term, not in the killed set | discount city closes by 3 × (opp farm majority over the adjacent field) |
| J8 | 2 meeples to secure a city, 3 for a farm; when the game turns on one feature, take chances | pivotal-feature overcommit (variance-seeking) | scan **F6** (trailer variance) | detect pivotal feature; overcommit even at negative naive EV |
| J9 | champion blocks cloisters well; doubles cloisters; claims cloisters it won't close for the confident 7–8 pts | (champion behaviors he respects — defensive info) | — | Joshua-bot should AVOID early cloister grabs (his stated adaptation) |
| J10 | went less farm-aggressive early-game after the first few games; counts cities late and surrenders low-value farms | **anchor shift** — see §4 | E4_UPDATE §6 farm-anomaly collapse | version the bot: "early-epoch Joshua" (farm-aggressive) vs "current" |
| J11 | champion's late new farms close 2–3 cities around them and surprise him | (champion strength — defensive info) | item-1 farm-norm replay | — |
| J12 | champion adds tiles to HIS city to prevent closing (halves value + locks meeple) — he rates it smart | (champion behavior) — **emergent denial via search** | the denial LEAF term measured harmful/null — see §4 | — |

## 3. Owner policy — assists are IN-SCOPE for the E4 reference (captured verbatim)

The goal is superhuman ⇒ the reference human may use anything "a good human is certainly
doing": **tile-bag peek** (pros count), a **virtual-score menu** (mechanical, calculable
with time/practice), an **occasional undo** for genuine misclicks/brainfarts. **His stated
priority: NONE now** — "i'm beating him even without these". Consequences: (a) the E4
stream is an *assisted-human* reference **by design**, not by accident — the standing
"assists unstamped" caveat becomes "assist level is part of the reference definition,
stamp it when features land"; (b) the three app features are BACKLOG items, not funded
work. Calibration he states himself: he is new to the game and expects both a pro and a
good bot to destroy him — the current lean is vs one improving amateur, not vs the field.

## 4. Interpretation hypotheses (NOT findings)

1. **The farm-anomaly collapse now has a candidate mechanism: the ANCHOR moved.** He says
   he deliberately went less farm-aggressive early-game after his first few games — the
   epoch-half split in E4_UPDATE §6 (farm margin +11.4 z+3.18 → +1.5 z+0.38; champion farm
   pts/seat 14.0 → 21.4) is timed consistently with that self-report. This makes the farm
   collapse an anchor-shift story rather than a champion-recovery story — untestable
   retroactively except via the autopsy's per-game splits, but it retires any urge to
   "explain" the champion's farm recovery.
2. **The champion already plays targeted denial — emergently, through search.** J12: he
   describes the champion extending *his* city to deny closure and prices it correctly
   (sacrifice 1–2 pts to halve value + lock a meeple). The 2026-08-12 denial *leaf term*
   measured harmful-at-2750 / bounded-null-at-deploy. Consistent read: the search already
   finds denial when it is actually good; a static leaf bonus for it double-counts and
   distorts. This is a mechanism-level gloss on CL-079's transfer story, worth carrying
   into any future denial re-aim.
3. **His self-report matches the census asymmetries** (hold-vs-spend 1.9×, road→pass
   largest cell, champion-side F2/F9 counts): the interview and the extraction were
   produced independently and agree — the Joshua-bot spec is grounded in both.

## 5. What this unlocks

- **Joshua-bot is now buildable**: J1–J8 are concrete, encodable rules; J10 says build it
  versioned (early vs current epoch). Next step per the lever row: encode + n=400–800
  deck-paired vs the champion; even partial reproduction of the +10 pts/game lean makes it
  the program's first powered anti-champion instrument.
- **Autopsy priors sharpened**: the F2/F3 tags and the DEG/FARM strata now carry
  anchor-confirmed priors; J5 (value-starving dumps) and J7 (close×farm interaction) are
  NEW candidate tags computable offline from replay — queue for the analysis pass, no new
  search needed.
- The three assist features → BACKLOG (not priority, owner's words).
