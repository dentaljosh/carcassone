> ⛔ **DRAFT — NOT FROZEN, NOT COMMITTED.** Prepared 2026-08-23 alongside [`DESIGN.md`](DESIGN.md) / [`READ_RULE.md`](READ_RULE.md). **VERDICT: NO BAND IS OWED.** Nothing in this note asks the orchestrator to append a registry row; it asks the orchestrator to *verify* that none is needed and then leave [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) untouched.

# BAND NOTE — the every-ply probe consumes NO deck band

**Question the orchestrator must answer before launch:** does this probe owe a
`governance/BAND_REGISTRY.csv` claim?

**Answer: NO — on every branch, whatever the outcome.**

---

## 1. Why not — the position sourcing, verified

The probe's positions are **not generated**. They are **replayed** from games that already exist
on disk and whose band was claimed and retired long ago.

| step | what actually happens | new games? |
|---|---|---|
| frame | a **query** over the tracked census [`../tiearb_widening_20260817/census/tile_gap_rows.jsonl`](../tiearb_widening_20260817/census/tile_gap_rows.jsonl) — 31,827 rows already on disk | **no** |
| position build | `scripts/measurement_infra/root_replay.py::replay_actions(deck_seed, actions, ply)` reconstructs `(game, board)` from [`../champ_action_logs/champ_games.jsonl`](../champ_action_logs/champ_games.jsonl)'s stored `(deck_seed, actions)` | **no** |
| champion pick | ONE fresh `make_production_champion("fair", …)` **search at that reconstructed position** — a single move decision, not a game | **no** |
| ARB / IF legs | `tier1-greedy` and `clair-puct` continuations on **CRN worlds derived from the position's own remaining deck** — `sha256("world"\|rid\|j\|salt)` | **no** |

Every `deck_seed` in `champ_games.jsonl` lies in **band `28000000000`**, and every row of the
census carries that same `deck_seed` as its replay key (verified: `game_id == deck_seed` on every
selected row, pinned by test in
[`../../tests/test_everyply_plan.py`](../../tests/test_everyply_plan.py)).

## 2. The governing precedent is already in the registry, verbatim

`governance/BAND_REGISTRY.csv` row `28000000000`:

> `28000000000, move-agreement bank (k4 roots) - reused as the replay source for oracle scoring,
> claim, retired, 2026-07-28, yes, CL-070,` **"Roots from this band are replayed by opponent-free
> instruments (no new band consumed)."**

That note is not an analogy — it is **this exact reuse pattern, written down for this exact
band**, and it has already governed `tiletie_pricing_20260812`, `tiearb_20260816`,
`tiearb2_20260816` and the widening legs, none of which claimed a band for their offline pricing.

**Both judges here are opponent-free.** `tier1-greedy` and `clair-puct` play *continuations from a
fixed position on a known deck*; neither is a match between two agents, so there is no head-to-head
whose result a band would need to seal.

## 3. Band identity is still load-bearing — what the read-out must therefore say

CL-068's cross-band over-dispersion (1.8–2.2×) makes band identity load-bearing even when no band
is *claimed*. So although nothing is appended to the registry:

- The read-out **must stamp** `band = 28000000000` and `corpus = champ449` on every row and in the
  manifest, so a later reader can never mistake this corpus for a fresh band.
- **No number from this probe may be pooled with any statistic from another band.** `κ` is a
  within-corpus quantity.
- Band `28000000000` is **already retired from confirmatory use** (it influenced CL-070). This
  probe does not un-retire it and does not extend it: it adds no games and consumes no seeds.

## 4. ⚠️ WHEN A BAND *WOULD* BE OWED — the condition, stated so it is checkable

A band **would** be owed the moment any of the following became true. **None is true of this
design, and the launcher cannot make any of them true:**

1. **Fresh self-play generation.** If the corpus needed *new* games — a different champion epoch,
   a different rules profile, more than the 449 games on disk, or non-tied plies from a corpus that
   does not exist yet — that generation consumes deck seeds and **owes a claim**.
2. **A game cell.** Any deck-paired ARB-vs-CHAMP head-to-head (what `E-CLEAN` could at most license
   *a design for*) is a game cell and **owes a fresh sealed band**. `READ_RULE.md` §5 forbids any
   branch from launching one.
3. ⚠️ **Extending the corpus for a top-up — and a HARD CONSTRAINT the plan does not state.**
   The corpus is **449 games**, and DESIGN §2.4 caps positions at **2 per game**. **Maximum
   constructible supply is therefore 449 × 2 = 898 positions.**

   > **SIZE-2 AS THE PLAN STATES IT (pool 1,000, priced n = 900) DOES NOT FIT: 1,000 > 898 and
   > 900 > 898.** SIZE-1 (pool 450, priced 400) fits with room to spare; SIZE-2 does not fit at
   > all.

   A funded top-up would therefore have to do one of three things, each with a consequence:
   (a) **raise `--cap-per-game` above 2** — degrading the root-cluster design effect the cap
   exists to protect (the tiearb corpus realized ≈ 0.94 at cap 2), which inflates `se(κ)` beyond
   the DESIGN §7.1 table the top-up would be sized on; (b) **cap the top-up at n ≤ 898** and
   re-derive its power; or (c) **generate new games — which consumes deck seeds and OWES A BAND
   CLAIM.**

   **This is a real, previously-unstated constraint on the unfunded top-up**, found while
   transcribing the plan, and it is recorded here so a future "just add n" ask cannot skip it.
   It does not affect SIZE-1 in any way.

⇒ **Deliverable for the orchestrator: confirm (1)–(3) are all false for SIZE-1, then claim
nothing.** If a top-up is ever funded, **re-read item 3 first.**

## 5. What the close-out touches instead

`BAND_REGISTRY.csv` is **untouched**. The governance row this probe flips on adjudication is the
[`LEVER_INDEX`](../../docs/LEVER_INDEX.md) row *"every-ply rollout arbitration"*, which currently
reads **NAMED, NEVER TRIED (2026-08-20)** and moves to whatever branch fires (`KILLED` on
`E-HARM`, `PARKED` on `E-FLATNULL`, and an explicit *"probed, unresolved at n=400"* on
`E-UNRESOLVED`). See [`DESIGN.md`](DESIGN.md) §13.
