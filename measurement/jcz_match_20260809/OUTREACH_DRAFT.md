# External-AI challenge — outreach draft + battle spec

> **STATUS: DRAFT, NOT SENT.** Prepared 2026-08-09 after the JCZ n=400 result and the
> [external-AI inventory](EXTERNAL_AI_INVENTORY.md). Sending is Joshua's call; edit voice freely.
> Primary target: Twin Sails Interactive / Frima Studio (official app, "Conqueror" AI — the only
> candidate with a community strength reputation). The same letter works with light edits for the
> academic authors (Carcasum's Yannick Müller; the Ameneyro–Galván group).

---

## The email (draft)

Subject: **Benchmarking challenge: our Carcassonne AI vs. yours, rules-certified, 400 paired games**

Hi —

I'm an amateur who spent the last few months building a Carcassonne AI (2-player base game +
farmers) as a hobby research project, together with an AI coding assistant. It plays at full
strength on a phone, and we recently benchmarked it against the strongest open-source Carcassonne
AI we could find — JCloisterZone's `LegacyAiPlayer` — over **400 deck-paired, seat-swapped games**
with per-move rules cross-validation (56,777 plies, zero scoring divergences between the two
engines). Result: **+111 Elo (65.5% win rate, +6.5 points/game)**.

We'd love to benchmark against a stronger opponent, and your AI has the best strength reputation
of any Carcassonne implementation we've found. Would you be interested in an engine-vs-engine
match? Two ways it could work, whichever costs you less:

1. **Wire protocol** (preferred): any interface that accepts "here's the tile drawn + game state
   (or the full move history), give me your move" — a of couple hundred lines of glue on our side,
   read-only on yours. We run everything, you get the full game logs and the writeup.
2. **You run it**: we send you our engine as a self-contained binary + the match harness; you run
   the gauntlet privately and share only what you're comfortable sharing.

Either way we'd first run a small rules-agreement audit (edge-case scoring positions both sides
score independently) so any result is about strength, not rules drift — that discipline is what
made the JCloisterZone number clean. Happy to share that writeup, our methodology, or anything
else. And if the answer is no, no hard feelings — thanks for building the best digital Carcassonne
out there.

[Joshua's sign-off]

---

## Battle spec (one page, attach or inline on request)

- **Scope:** 2-player base game + farmers, 3rd-edition-style scoring (tied features score full for
  all tied players; farms 3 pts/completed city). No river, no expansions. If your AI plays a rules
  variant, the audit surfaces it and we either match it or we don't run — no silent drift.
- **Pairing:** N decks × 2 games each with seats swapped (both AIs see identical tile order once
  from each side). Deck-paired margin is the primary statistic (it cancels most deck luck);
  win rate is secondary. N=200 decks (400 games) resolves ~±17 Elo at 1σ; a 20-game smoke first.
- **Rules-agreement audit (before any rated game):** both engines independently score a fixed set
  of edge-case positions (tied roads/cities, multi-city farms, cloister completion, final-scoring
  partials). Any disagreement is resolved or documented before play. In the JCZ match this took
  one day and caught real divergences before they could contaminate results.
- **Wire format (if option 1):** JSON per turn: we send `{tile_drawn, legal_actions, move_history}`,
  you return `{action}` — or any equivalent your side already has (JCZ needed only its existing
  save-game format). Determinism/timing are up to you; we log per-move latency but the match is
  untimed (our side spends ~1.3 s/move).
- **What gets published/shared:** your call, agreed in advance — from "nothing, private result"
  to full logs + a joint writeup. We keep the raw game logs either way so results are auditable.
- **What we never ask for:** source code, models, or anything proprietary. Ideas are discussed in
  the open; implementations stay on their own side of the wire.
