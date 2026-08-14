# Pro/Strong-Human Carcassonne GAME RECORDS Inventory — 2026-08-14

**Status:** current (web inventory + feasibility assessment, nothing ingested, nothing downloaded)
**Purpose:** inventory sources of machine-readable (or transcribable) records of strong-human Carcassonne *games* — actual move-by-move data, not strategy prose. Companion to the strategy scan ([PRO_STRATEGY_SCAN_2026-08-12.md](PRO_STRATEGY_SCAN_2026-08-12.md)); motivated by the encoding-triptych null (mining *un-articulated* strong play is the live route) and by structural blocker #1 (no strong non-saturated external reference). Everything here is inventory only — no bulk downloads, no logged-in scraping, no ToS violations were performed or are recommended below.
**Scope discipline:** project ruleset is 2p Base+Farmers, no River, no expansions, `rules_profile: fixed_v1` (governance/PRODUCTION.yaml). Any external corpus splits into **(A) games by strong players under our ruleset footprint** (directly minable after a divergence audit) vs **(B) games under variant rules/expansions** (needs the audit *and* may be unusable) — per the JCZ precedent, where a single half-edge convention (R9) produced 66 farm-partition divergences until audited ([RULES_FIDELITY_AUDIT_20260802.md](../RULES_FIDELITY_AUDIT_20260802.md), [jcz_oracle VALIDATION_REPORT](../../measurement/jcz_oracle_20260803/VALIDATION_REPORT.md): 43/43 exact-score agreement only *after* fixed_v1+R9).

**Method note on sourcing:** same blocks as the 2026-08-12 scan — BoardGameGeek, Carcassonne Central (carcassonnecentral.com), and wikicarpedia.com all bot-block direct fetches (403/Anubis), so every claim about those rests on WebSearch snippets and is flagged. New blocks found this pass: `boardgamearena.com/award` pages are a JS app that fails to render for a fetcher (the top-ELO lists exist but could not be read); YouTube watch pages return only the page shell (video length/description unverifiable); the WTCOC rules PDFs at carcassonne.cat 404 at every versioned URL Google has indexed (the rules content below is snippet-only). BGA's main site (gamepanel, table pages, doc wiki, forum) *does* answer direct fetches and those claims are page-verified.

---

## 1. BoardGameArena (BGA) — the volume + strength center of gravity

**What exists (page-verified unless noted):**
- **15,278,860 Carcassonne games played** on BGA (gamepanel page, fetched 2026-08-14). Carcassonne is BGA game id 1; 2–5 players, ~15 min typical.
- **Replays exist for every table** and are an *exact recording*: BGA archives the static game files and re-sends the recorded per-move notification stream to the browser (en.doc.boardgamearena.com/Game_replay — developer doc, fetched). I.e. the underlying record is machine-readable JSON per move; a Medium writeup (Liam Johansson, "Web scraping for board game analysis") demonstrates parsing exactly this replay structure for another BGA game.
- **Table pages record the full config** — the fetched sample table page lists per-table options incl. The River, Inns & Cathedrals, Traders & Builders, Princess & Dragon, "Strategic variant", and a **"Field scoring" variant toggle** — so for any given game the ruleset footprint is *knowable*, which is exactly what a divergence audit needs.
- **Top-strength play is identifiable**: award pages for Top-20/Top-10 ELO and World-ELO-leader exist (award=28/29/33; JS-rendered, could not be read directly); BGA tracks top-100 ELO. The **WTCOC** (World Team Carcassonne Online Championship, ~20+ countries, recognized by Hans im Glück) is **played on BGA with the base game** (snippet-only for the config claim; carcassonne.cat hosts full brackets/results 2020–2025). National groups (Carcassonne USA/Belgium/France, King of Carcassonne club) organize on-BGA events; Carcassonne Belgium separately tracks a **"Basic Game" BGA ELO** ranking for its players (weebly page fetched, config details absent). So strong 2p base-game play is not just present on BGA — the *organized competitive scene* lives there.
- Community tooling confirms client-side state is readable in practice: yzemaze/bga-carcassonne-scripts (userscripts, explicitly "designed and tested for 2p-Carcassonne without expansions" — telling about what the competitive queue plays), a Chrome auto-tile-counter extension, and a `replay-to-top-carcassonner` userscript that feeds BGA replays into an external analysis site (top-carcassonner.com, see §7).

**Volume estimate at strong level, 2p base+farmers:** unquantifiable precisely without login, but the competitive scene (WTCOC editions 2020–2026, national championships, top-100 ladder) plausibly generates **thousands of identifiable strong-player 2p base-game tables**, each with a replay. Flag: estimate, not a counted number.

**Data format + converter needs:** per-move notification JSON (tile drawn, placement coords/rotation, meeple slot, scores). A converter would map BGA tile ids → our 24 tile kinds + rotation/coordinate conventions + meeple-slot mapping — the same three mapping problems the JCZ spike already solved once for a different vocabulary ([SPIKE_REPORT](../../measurement/jcz_spike_20260803/SPIKE_REPORT.md)), so call it days-not-weeks *if* the data were in hand. Deck order is fully determined by the replay (each draw is recorded), which fits the lossless deck-seed+action-sequence replay infra directly.

**Ruleset divergence from fixed_v1:** base game with no options ticked ≈ current official C3 base rules = our footprint (base tiles, farmers, no river) — closest match of any source in this inventory. Knobs to audit per-table: the "Field scoring" variant toggle, start-tile handling, any tie-break conventions. The audit machinery exists (`scripts/jcz_oracle/` pattern: replay externally-recorded games through our engine and diff scores).

**Access + ToS posture (the blocker — be explicit):** replays are **login-only**, with an undocumented rate limit even for premium (~30–100 replay views/24h per forum reports; deliberately not disclosed). **BGA's ToS prohibits automated scripts and web scraping**, and forum guidance is that scrapers get banned and that you should **contact a BGA admin before attempting anything similar** (forum threads t=17899 and the Medium writeup both, page-verified). There is **no official export API** (feature-request threads t=15014/t=21248 went unanswered by staff). Retention/expiry of old replays: could not be established. **Conservative reading: the only compliant routes are (a) written permission from BGA, or (b) manual replay viewing on Joshua's own account with hand transcription, within normal-use limits.** Manual transcription of a watched replay is ordinary note-taking on games one is entitled to view; bulk redistribution of transcribed corpora is a separate question not assessed here.

**Effort to first ingested game:** via route (b): ~1 session to locate one WTCOC/top-ELO 2p base table + transcribe (~35–40 plies) + a small BGA-notation→replay-format converter; call it 1–2 days to first verified game. Route (a) is a single email with unknown latency but unlocks everything else.

## 2. JCloisterZone (.jcz saves) — cheapest ingest, no discovered corpus

**What exists:** JCZ 5.12.1 current, 4.6.1 legacy (jcloisterzone.com, fetched). Saves are XML game snapshots incl. remaining-tile lists (github snippets); 5.x speaks a line-JSON protocol the project already drives headlessly (`ForcedDrawTilePack` takes our deck verbatim — SPIKE_REPORT). **Carcassonne Central's leagues and online tournaments moved to JCZ** (JCloisterZone Facebook post, snippet-only) — so JCZ-format records of organized competitive games *have existed*. But: **no public repository/archive of .jcz save files was found anywhere** — not on GitHub (searched), not indexed from the CC forum. If saves live anywhere, it is as attachments inside carcassonnecentral.com threads ("Online Games and Competitions" board), which is bot-blocked — **human browsing required to confirm even existence**. Post-BGA-era, CC competitive activity appears to have migrated to BGA (WTCOC is co-organized by Carcassonne Central *on BGA*), so the JCZ-league era may be historical and modest in volume.
**Ruleset:** JCZ leagues historically played with expansions as often as base (unverified, snippet-level impression); every candidate save's expansion set is declared in the file, so filterable. Divergences from fixed_v1 are *already fully characterized* (R9 etc. — the one source where the audit is DONE).
**Effort to first ingested game:** hours, *if* a base-game .jcz save is ever located — the oracle/replay tooling exists. The blocker is corpus discovery, not engineering.
**Credibility:** format/tooling claims page-verified + in-repo; corpus-existence claims snippet-only.

## 3. Tournament records (WC / national, live events)

**What exists:** carcassonne-meisterschaft.de (official WC site, fetched) publishes **results and photo galleries back to 2006 — no move records**. No national federation publishing game notation was found; there is no evidence anyone records OTB Carcassonne games in notation (no standard notation exists; yzemaze's `toggle-coords` userscript exists precisely because players lack coordinates to talk about moves).
**Video:** full-length YouTube recordings exist for WC finals (2021: eecKGlkccWg; 2022 Essen: uB3GBhnUS6E; 2023: KOoVWpEs3VU), Belgium 2024 final, a WC Global Qualifier 2024 stream, and a **World Team Carcassonne Online Championship 2024 playlist** (screen-captured BGA games — see the transcription note in §4). Physical-table finals: camera setup/board legibility **unverified** (YouTube pages would not render to the fetcher); transcription feasibility is plausible-but-unproven, and tile-identity at stream resolution is the known risk. Volume: order 1–5 games per event per year — **tiny**.
**Ruleset:** WC plays official base game (with WC tie-break, which fixed_v1 deliberately omits — noted divergence, endgame-tie plies only).
**Effort:** high per game (manual video transcription with re-watching), low total ceiling. Credibility: video existence page-search-verified; content quality unverified.

## 4. Strong-player video (BGA screen recordings) — the sleeper transcription source

**Alexey's Carcassonne Channel** (youtube @AlexeysCarcassonneChannel): Alexey Pegushev, six-time national champion and described as the **highest-ever-rated BGA Carcassonne player**, posts competitive-Carcassonne commentary/gameplay (snippet-verified). A screen-recorded BGA game is *perfectly* transcribable — the UI displays the exact drawn tile, placement, meeple slot, and running score, with no camera-angle ambiguity — and public-video transcription for private research has no ToS entanglement at all. The WTCOC-2024 playlist (§3) is the same category. Volume: unknown (channel size unverifiable through the fetch block), plausibly dozens-to-hundreds of games at the very top of human play, ruleset visible per video.
**Effort to first ingested game:** ~half a day (watch + transcribe + reuse the §1 converter). Cheapest *fully-compliant* route to a top-human game found in this inventory.

## 5. Academic / research datasets

**Nothing.** No public corpus of Carcassonne games exists in the literature: the MCTS papers (Ameneyro et al. 2020, the UCB-evolution follow-up 2112.09697, the Maastricht thesis) all self-generate AI-vs-AI data; the AR/gaze paper (2208.09094) reportedly had to build an AI *because* no datasets of Carcassonne game progressions were available (that specific claim: search-snippet-level; its abstract, fetched, neither confirms nor denies). No Kaggle/GitHub/Zenodo dataset found under any naming tried. Human-game data: zero.

## 6. "The Book of Carcassonne" (Dee & Chard, tehill.net)

Fetched the book page directly: contents are history, interviews (incl. Wrede), competitive-play chapter, basic+advanced strategy, expansions, "expert tips from 5 world champions" — **no mention of annotated games or move-by-move analysis anywhere**, no sample chapter online, TOC not published. Amazon/Goodreads listings and the BGG thread about the book (snippets) likewise never mention example games. **Working conclusion: it is a tips book, not a games collection — decisively NOT a game-records source unless buying it (£7.95) proves otherwise.** Keep it on the *strategy* shelf (it was the strategy scan's highest-credibility-if-accessible lead), drop it from the game-records track.

## 7. Other digital platforms (surveyed, all weak)

- **top-carcassonner.com** — online Carcassonne vs AI & players; the yzemaze userscript pipes BGA replays into it as an analysis viewer, and the Japanese competitive community (rabbitrain blog) uses it for daily position-voting puzzles. Could not inspect (JS app). *Lead, unverified: if it retains imported BGA replays, someone else already built the BGA-replay ingestion pipeline.*
- **Yucata.de** — hosts Hunters & Gatherers and South Seas only, **not base Carcassonne** → out of scope entirely.
- **Boîte à Jeux** — no Carcassonne implementation found.
- **Asmodee "Tiles & Tactics" / official app** — no replay export or sharing feature found; recurring server outages reported 2025; dead end.
- **Tabletop Simulator** — a Carcassonne mod exists (DinnerBuffet/TTSCarcassonne); TTS saves are state snapshots, not move logs; no competitive archive found; dead end.
- **Our own E4 archive** — the existing 28-game corpus (measurement/e4_games/) remains the only in-hand strong-human data; this inventory found nothing that ingests faster than transcribed BGA games.

---

## Ranked verdict (volume × strength × ingestion-cheapness × rules-proximity)

| # | Source | Volume (strong 2p base) | Strength | Ingest cost | Rules proximity | Class | Blocker |
|---|--------|------------------------|----------|-------------|-----------------|-------|---------|
| 1 | **BGA replays (WTCOC + top-ELO tables)** | 1000s (estimate) | world-class | medium (converter + per-game access) | **highest** (config known per table) | A after audit | ToS: no automation; login + rate limits; needs BGA permission for anything bulk |
| 2 | **BGA screen-recorded video (Alexey, WTCOC casts)** | 10s–100s | top-of-ladder | medium (manual transcription, zero ambiguity) | same as #1 | A after audit | none (public video, manual work) |
| 3 | **CC forum .jcz saves (JCZ league era)** | unknown, maybe 0 | strong-club | **lowest** (oracle exists) | audited already (R9) | A/B mixed (expansions common) | corpus existence unconfirmed; forum bot-blocked → human browsing |
| 4 | WC finals video (physical table) | ~1–5/yr | world-champion | high (camera ambiguity) | official rules (+tie-break) | A after audit | view quality unverified |
| 5 | Book of Carcassonne | ~0 | n/a | n/a | n/a | — | no evidence of annotated games |
| 6 | Academic datasets | 0 | — | — | — | — | nothing exists |

**Single best first target: BGA — specifically the WTCOC finals/knockout tables.** They are simultaneously the strongest identifiable humans, a *known* base-game configuration, team-vetted play (less noise than ladder games), and enumerable from carcassonne.cat's public brackets. **Concrete next step (compliant, two prongs in parallel):** (1) Joshua, on his own BGA account, opens one WTCOC 2025 final-round table, confirms the replay renders and the options panel shows base-game/no-expansions + which field-scoring setting, and hand-transcribes one game — that single game validates the BGA→fixed_v1 converter end-to-end (build it against this game; reuse the JCZ spike's mapping methodology). (2) Simultaneously email BGA support/admin — the forum's own stated protocol — asking for research permission to export a bounded set (~100–500) of identified competitive-table replays; the answer gates whether route #1 scales past manual volume. Fallback if BGA declines and manual volume is too slow: route #2 (video transcription of Alexey/WTCOC casts) delivers the same rules footprint with zero ToS exposure at ~2× the per-game cost.

**Class-A vs Class-B flag, restated:** WTCOC/base-game BGA tables and base-game video transcriptions are Class A — *strong players under our ruleset footprint*, minable after one BGA-conventions divergence audit (start tile, field-scoring toggle, tie handling) run through the existing jcz_oracle-style replay-diff. Anything with I&C/River/expansion ticks (much BGA ladder play; possibly most JCZ-league saves; any pre-2022 arena seasons if the community claim that arena used I&C is right — snippet-only) is Class B: do not spend converter effort there without a decision that the divergence audit is worth it.

## What I could not verify

- **BGA arena-mode Carcassonne configuration** (base vs I&C, field-scoring setting) — community snippet only; the award/arena pages would not render. Resolve in 2 minutes logged-in.
- **BGA replay retention window** (do 2020-era WTCOC tables still replay?) — no documentation found either way.
- **WTCOC official rules text** (platform/options clauses) — every indexed PDF URL 404s; the "base game on BGA" claim rests on search snippets + the co-organizers' sites.
- **Whether any .jcz saves are actually attached in Carcassonne Central league threads** — the forum is bot-blocked; existence is inference from "leagues were played on JCZ", not observation.
- **Physical WC final video board-legibility** — YouTube pages would not render; nobody watched the footage this pass.
- **top-carcassonner.com internals** (replay retention, any API) — JS app, uninspectable by fetch.
- **Book of Carcassonne contents beyond the marketing page** — absence of annotated games is inferred from every listing omitting them, not from reading the book.

**Report path:** `/home/doctor/projects/carcassone/docs/research/PRO_GAME_RECORDS_INVENTORY_2026-08-14.md`
