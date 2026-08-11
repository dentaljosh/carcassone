# External Carcassonne AI inventory — candidates stronger than JCloisterZone LegacyAiPlayer

Context: our champion beat JCZ LegacyAiPlayer by +111.4 elo (n=400 deck-paired, base+farmers).
JCZ is the strongest known *open-source* engine. This inventories every other candidate found
(2026-08-09 web research) toward a programmatic "API battle." Research only — no code, no outreach sent.

**Headline finding: no candidate below has a verified strength claim that would place it above
JCZ, let alone above our champion.** The one AI with a real community reputation for strength
(the official app's "Conqueror" tier) is closed-source with no programmatic path. Every
open-source alternative is small research/hobby code with no published elo and no head-to-head
vs. JCZ that we could find.

---

## 1. Carcassonne – Tiles & Tactics (official licensed app)

**Who makes it / link:** Developer Frima Studio (Québec), publisher Twin Sails Interactive; Android
package is `com.asmodeedigital.carcassonne`, implying an Asmodee Digital distribution tie today.
Same Steam AppID (598810) was originally shipped as "Carcassonne: The Official Board Game" (2017)
and later rebranded "Tiles & Tactics." [Wikipedia](https://en.wikipedia.org/wiki/Carcassonne_%E2%80%93_Tiles_%26_Tactics) ·
[Steam](https://store.steampowered.com/app/598810/) · [App Store](https://apps.apple.com/us/app/carcassonne-tiles-tactics/id1199912736) ·
[Google Play](https://play.google.com/store/apps/details?id=com.asmodeedigital.carcassonne)

**AI claims — CLAIMED vs VERIFIED:** This is almost certainly the app Joshua half-remembered, but
**we found no primary source claiming MCTS.** The one primary source we located is the developer's
own blog post, [blog.carcassonneapp.com/post/558206279/the-ai-of-carcassonne](https://blog.carcassonneapp.com/post/558206279/the-ai-of-carcassonne),
which announces **8 AI personas** (Count/Countess, Maid/Servant, Juggler/Fortune Teller,
Witch/Warlock) framed purely by *personality/style*, credited to an engineer named "Toby" — it
gives **zero algorithmic detail**, no mention of MCTS, minimax, or any search method. Third-party
reviews (game-solver.com, play-board-games.com, Common Sense Media) likewise make no algorithm
claim, only difficulty commentary. **Verdict: "MCTS" for this app is unsourced — do not repeat it
as fact without a better primary source than what we found.** The Steam version separately exposes
4 selectable difficulty tiers (commonly described by AI-color: green/yellow/red/purple, purple ==
"Conqueror" == strongest) — this is a UI fact, not an algorithm fact.

**Community strength reputation:** Consistently described as the strongest *branded* opponent.
Steam: ["Conqueror (violet) is a lot better than the other three... I don't think I have ever seen a violet-AI below the others"](https://steamcommunity.com/app/598810/discussions/0/2997669078618143043/).
A second thread, [I think the AI is a better player than most live opponents I've faced](https://steamcommunity.com/app/598810/discussions/0/3087760096562488391/),
shows a split community — some call it stronger than average humans, others call it beatable, some
suspect favorable tile draws ("cheating," likely confirmation bias per one commenter). Threads are
about **base + expansions mixed** (one names the Princess & Dragon DLC); no thread isolates
base+farmers-only strength. Nintendo Switch port reviewed "sluggish AI" (Nintendo Life, via
Wikipedia) — a port-quality complaint, not a strength signal.

**Automatability:** None found. Closed-source commercial Unity-ish mobile/Steam title, no public
API, no documented save-file format, no mod/scripting community turned up (searched explicitly).
Only path would be screen-scrape + input-injection (ADB/emulator), which is high-effort, fragile,
and carries ToS risk — and still wouldn't give us deterministic seed control for deck-paired replay.

**Rules-fidelity risk:** Unknown/unverified for farmers-only base scoring — the community chatter
we saw was expansion-inclusive, so we can't confirm base+farmers behavior matches 3rd-edition
scoring without buying and testing the app ourselves.

**Contactability:** Twin Sails Interactive support: [asmodee.helpshift.com/hc/en/84-twin-sails-interactive](https://asmodee.helpshift.com/hc/en/84-twin-sails-interactive/contact-us/);
publisher inbox reported as `publishing@twin-sails.com`-style (via Twin Sails site, unverified
exact address — see [twin-sails.com](https://twin-sails.com/en/)); social: [@TwinSailsInt on X](https://x.com/twinsailsint).
No individual engineer name surfaced beyond "Toby" (blog byline "Martin," pseudonymous).

---

## 2. Academic MCTS Carcassonne research (Ameneyro, Galván, Kuri Morales)

**Who / link:** Fred Valdez Ameneyro, Edgar Galván (Maynooth University, Ireland — prior posts at
UCD, Trinity College Dublin, INRIA Paris-Saclay per his [Maynooth staff page](https://www.maynoothuniversity.ie/faculty-science-engineering/our-people/edgar-galvan)),
Anger Fernando Kuri Morales. Paper: **"Playing Carcassonne with Monte Carlo Tree Search"**, IEEE
SSCI 2020. [arXiv:2009.12974](https://arxiv.org/abs/2009.12974) · [IEEE Xplore](https://ieeexplore.ieee.org/document/9308458/)

**AI claims (VERIFIED, this is a primary source — the paper itself):** Compares vanilla MCTS and
MCTS-RAVE against a prior Star2.5 expectimax-family baseline (from Cathleen Heyden's 2009
Maastricht master's thesis lineage). Finding: MCTS-based methods "consistently outperformed the
Star2.5 algorithm," vanilla MCTS more robust than RAVE. No elo/win-rate numbers surfaced in our
excerpts — would need the PDF read in full for exact win-rate tables.

**Follow-on work, same group** (evolving the MCTS UCB formula itself, not claiming a stronger
*player*): [arXiv:2112.09697](https://arxiv.org/abs/2112.09697) (SSCI, Dec 2021) and
[arXiv:2208.13589](https://arxiv.org/abs/2208.13589) (2022) — internals-tuning papers, not strength claims.

**Code:** Fred Valdez Ameneyro's GitHub is [github.com/33fred33](https://github.com/33fred33); his
repo **[33fred33/CarcassonneAI](https://github.com/33fred33/CarcassonneAI)** (Python, pygame UI,
9 stars/2 forks, `PLAY_GAME_UI.sh` launcher, includes `Development_hub.ipynb` and `MCTasks.txt`)
is almost certainly the code behind (or descended from) the paper — **runnable**, lets you pick
AI players and run matches through a pygame GUI. We could not confirm from the README excerpt
whether it supports farmers/full field scoring or has a headless (no-GUI) entry point; would need
a source read to confirm both before trusting it as a battle opponent.

**Community strength reputation:** None found — this is academic, not discussed on
BGG/Reddit/Carcassonne Central in anything we turned up.

**Automatability:** Source is open (Python) — automatable in principle by importing/wrapping
directly, no API needed. Rules-fidelity risk is real: research-scale code, unclear farmer support,
would need our standard rules-divergence audit before trusting any result.

**Contactability:** GitHub issues/PR on `33fred33/CarcassonneAI`; Edgar Galván's Maynooth page
(no email captured — page returned 403 to WebFetch, use the staff directory link above) or his
older [cs.nuim.ie/~egalvan/](https://www.cs.nuim.ie/~egalvan/) site.

---

## 3. Carcasum (Yannick Müller, master's thesis MCTS engine)

**Who / link:** Yannick Müller (GitHub `TripleWhy`), written for a Master's Thesis explicitly
"to research about Monte-Carlo Tree Search," graphics/config partly borrowed from JCloisterZone.
[github.com/TripleWhy/Carcasum](https://github.com/TripleWhy/Carcasum) ·
[BGG thread "Carcasum | Research about Board Games and AI"](https://boardgamegeek.com/thread/1208744/carcasum)
(fetch 403'd for us — visit directly) · thesis PDF in the [v1.0.0 release](https://github.com/TripleWhy/Carcasum/releases/download/v1.0.0/MasterThesis.pdf).

**AI claims (VERIFIED — primary source is the thesis itself):** MCTS by design/intent, per the
README and thesis title. We have not read the thesis PDF itself, so exact strength results
(win-rate tables, if any) are unconfirmed by us — flagging as a next step if this candidate is
pursued further, not asserting numbers we haven't seen.

**Community strength reputation:** Essentially none outside its own BGG announcement thread — a
niche academic release, not discussed in strength-ranking threads we found.

**Automatability:** **Best of the open-source candidates on paper** — open source (AGPL-3.0), C++
with Qt, builds from source (git + GCC 4.8+ + Qt 5.2.1+ + optional Boost). No headless mode
documented in the README, but AGPL C++ source means we could add a CLI/headless driver ourselves
if the strength case justified the engineering.

**Rules-fidelity risk:** Unconfirmed farmer/scoring support from the README alone — needs a source
read or a quick smoke game before trusting it.

**Contactability:** GitHub issues on `TripleWhy/Carcasum`; author explicitly invites research use
("welcomes research applications... requests public code contributions" per README) — a
cooperative-sounding maintainer, good candidate to actually ask.

---

## 4. Other open-source Carcassonne engines found on GitHub (beyond JCZ)

Searched GitHub broadly; three more turned up with *some* AI (not just a rules engine, all small):

- **[mmbednarek/msi-carcassonne](https://github.com/mmbednarek/msi-carcassonne)** — "Carcassonne
  implementation with monte carlo tree search AI," C++/CMake, Protocol Buffers, 8 stars, 72
  commits, 1 open issue. GPL-2.0. **CLAIMED MCTS in the repo description itself (primary source,
  the maintainer's own words) — not third-party rumor.** We could not extract farmer-rule support,
  API shape, or strength claims from the README excerpt; would need a source read.
- **[SamuelScheit/carcassonne-ai](https://github.com/SamuelScheit/carcassonne-ai)** — school
  seminar project; notably **"a rewritten wingedsheep adapted version in python"** — i.e. built on
  the *same upstream engine we vendor* (`engine/` in this repo). Archived/read-only since
  2023-09-14 (inactive). GPL-2.0, 9 stars/1 fork. Given the shared wingedsheep lineage, rules
  compatibility risk is *lower* than the others, but the project is dead and algorithm strength
  unverified.
- **[sash2104/carcassonne](https://github.com/sash2104/carcassonne)** — C++, references a
  Maastricht University master's thesis (the same Star2.5 lineage the 2020 MCTS paper benchmarks
  against), 0 stars, described in-repo as early-stage ("just checking tile_holder behavior").
  Not a serious strength candidate.

None of these three have a discoverable strength reputation or a benchmark vs. JCZ — all hobby/coursework scale.

---

## 5. Board Game Arena — Carcassonne implementation

**Finding: BGA's Carcassonne has no AI/bot opponent.** BGA's own docs
([Bots and Artificial Intelligence](https://en.boardgamearena.com/doc/Bots_and_Artificial_Intelligence))
say only a handful of titles (Conspiracy, Glow, The Crew / Crew Deepsea, Tapestry) have bot modes,
and BGA describes those as rule-based "Automa" implementations, not real search-based AI. Carcassonne
is not on that list. A BGA forum thread we checked ([viewtopic.php?t=12423](https://forum.boardgamearena.com/viewtopic.php?t=12423))
turned out to be about a different game (Quarto) and confirms nothing Carcassonne-specific. **Not
a viable candidate — drop from consideration**, no further automatability/contactability work needed.

---

## 6. Other commercial/mobile clones

We searched explicitly for other reputed-strong commercial clones and found none distinct from
Tiles & Tactics — search results for "best Carcassonne AI app" repeatedly resolve back to the same
Steam/App Store title (Frima/Twin Sails). No second commercial app with an independent strength
reputation surfaced. Not treating this as exhaustive — a deeper mobile-store sweep (Chinese/Asian
markets, Windows Store legacy ports) was out of scope for this pass.

---

## RANKED SHORTLIST FOR AN API BATTLE

Ranking by (expected strength × automatability). **Caveat that applies to every entry below:**
none of these has a verified elo or a head-to-head vs. JCZ — "expected strength" here is
reputation/design-intent, not measurement. Any of these needs our standard three-gate pattern
(rules-divergence audit → n=20 smoke → n=400 deck-paired) before a verdict, and gate 1 is doing
double duty here since farmer-rule fidelity is unconfirmed for all of them.

1. **Carcasum (TripleWhy)** — best automatability of the open-source set: real open C++ source
   (AGPL-3.0), a cooperative-sounding author, and a from-scratch MCTS design (not a coursework
   afterthought). Concrete path: clone the repo, read the thesis PDF for any win-rate claims Müller
   already published, then do a source-level rules-divergence audit against our engine (does its
   scoring match 3rd-edition farmers?) before writing any adapter. If the engine has no headless
   entry point, budget for adding a thin CLI wrapper ourselves (source is available, license
   permits it) that accepts a (deck_seed, action-sequence) replay analogous to our harness. Expected
   strength is unknown but plausibly JCZ-adjacent (both are single-author MCTS/heuristic hobby
   engines) — this is a *measurement* candidate, not a presumed-stronger one.

2. **33fred33/CarcassonneAI (Ameneyro et al. paper code)** — second-best automatability: open
   Python source, runnable today via `PLAY_GAME_UI.sh`, and it's tied to a peer-reviewed primary
   source claiming its MCTS beat a Star2.5 baseline. Concrete path: read the source to confirm
   farmer/field scoring is implemented (the README excerpt didn't confirm this), strip the pygame
   UI to get a programmatic loop, then run the same three-gate pattern. Risk: research-scale code
   quality and no evidence it was ever tuned for competitive strength rather than illustrating the
   paper's UCB-variant comparisons — treat as a coin-flip on whether it clears JCZ, not a favorite.

3. **mmbednarek/msi-carcassonne** — MCTS claimed directly by the maintainer in the repo
   description (primary source, just terse), C++/protobuf stack suggests it may already expose a
   wire protocol (protobuf is often used for exactly this kind of engine-to-engine interface,
   though we haven't confirmed this from the README). Concrete path: read the full source before
   anything else — this is the one candidate where the network-protocol angle could shortcut
   straight to an "API battle" instead of us building the harness, *if* the protobuf schema turns
   out to be a real service interface rather than just internal serialization. Lowest confidence
   of the top three since we have the least visibility into it.

4. **Carcassonne – Tiles & Tactics (official app)** — ranked last **despite having the only real
   community reputation for strength** ("Conqueror" beating live opponents), because automatability
   is ~zero: closed-source, no API, no documented save format, no scripting community. Only
   worth revisiting if Joshua is willing to fund a screen-scrape/ADB-injection integration (high
   effort, ToS risk, and still no deterministic seed control for deck-paired replay) or if a dev
   cooperation request to Twin Sails/Frima actually lands a private API — treat as a
   "email if we want it, don't build blind" candidate rather than a near-term automation target.

**Bottom line for Joshua:** the +111.4 elo already banked over JCZ is not yet contested by any
externally-verified-stronger engine we could find. The two most promising *next measurements* are
Carcasum and the Ameneyro paper's code, purely on automatability — neither has a strength claim
we'd bet on beating JCZ, let alone our champion. If "beat something with real reputation" is the
actual goal rather than "find another automatable ruler," Tiles & Tactics' Conqueror tier is the
only candidate with that reputation, and it requires either screen-scrape engineering or a
dev-cooperation ask — worth a one-line confirm with Joshua before spending effort either way.
