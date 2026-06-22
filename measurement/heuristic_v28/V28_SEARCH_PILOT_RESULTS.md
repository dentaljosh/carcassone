# v2.8 search pilots (Phase 5)

> Paired full-game **HeuristicMCTS** A/B: side A = heur@N with a v2.8 leaf (`leaf_cfg=`), side B =
> heur@N with v2.7 (`leaf_cfg=None`). The Elo of A over B IS the leaf gain at that search depth. Pure
> CPU (no net, no orchestrator). Harness [scripts/heuristic_v28/v28_search_pilot.py](../../scripts/heuristic_v28/v28_search_pilot.py);
> data [V28_SEARCH_PILOT_RESULTS.csv](V28_SEARCH_PILOT_RESULTS.csv);
> manifest [V28_SEARCH_PILOT_MANIFEST.json](V28_SEARCH_PILOT_MANIFEST.json). Deck-paired, seat-balanced,
> fresh seed namespaces (NOT the spent 1.7e9 sealed panel). Power: n=200 paired ⇒ 1σ_elo ≈ ±25;
> `|z_margin|>2` on the per-game paired diff = reliable margin (CLAUDE.md discipline).

## Results (FACT)

| variant | leaf override | sims | n | W/D/L | winrate | Elo (A−B) | z_margin | signal |
|---|---|---|---|---|---|---|---|---|
| `v28_completion` | slack=3.0 | 200 | 200 | 99/4/97 | 0.505 | **+3.5** ± 24.6 | +1.09 | INCONCLUSIVE |
| `v28_meeple` | k=2, t0=72 | 200 | 200 | 129/1/70 | 0.648 | **+105.6** | +4.65 | VERDICT |
| `v28_meeple` | k=2, t0=72 | **800** | 120 | 76/0/44 | 0.633 | **+94.9** | +3.76 | VERDICT |
| **`v28_meeple_flat`** | **k=2, t0=0** | 200 | 200 | 145/5/50 | **0.738** | **+179.5** | **+9.92** | VERDICT |
| `v28_meeple_k1` | k=1, t0=72 | 200 | 200 | 109/4/87 | 0.555 | +38.4 | +1.38 | INCONCLUSIVE |

## What survives the search gate

- **`v28_completion` — KILLED at search.** The exact-confirmed endgame-K2 leaf gain (Phase 4) does
  **not** translate to full-game strength: +3.5 elo, z=1.09, a null. This is the hybrid-handoff lesson
  (CL-026): endgame-local improvements are real but immaterial to full-game Elo because the endgame is
  a small slice of the game. Mechanism-supported but **strategically immaterial** — not in v2.8.
- **`v28_meeple` (meeple-economy term) — SURVIVES, large + robust.** +105.6 elo @200 (z=4.65) and the
  gain **holds at heur@800** (+94.9, z=3.76) — so it is **NOT search-imitation** (deeper search does not
  erase it; a leaf term that washed out under depth would have). This is the **strongest strength
  signal the whole v2.8 branch produced.**

## The mechanism, corrected (disentangle + bracket)

The Phase-4 autopsy flagged `v28_meeple`'s *recovery-scaling* mechanism as **unsupported**. The Phase-5
disentangle confirms it and **reassigns the credit to the flat term**:

- **FLAT (t0=0) is far STRONGER than recovery-scaled**: `v28_meeple_flat` = **+179.5 elo (z=9.92)** vs
  the scaled `v28_meeple` +105.6. The recovery scaling (t0=72) I added **detracts** ~75 elo. So the
  real lever is the **plain `meeple_k·(meeples_self − meeples_opp)` economy term**, NOT the recovery
  refinement. (Autopsy vindicated: the scaling was never the mechanism.)
- **k-bracket**: k=1 → +38 (inconclusive), k=2(scaled) → +106, k=2(flat) → +180. The effect grows with
  k; k=2 is not a single-point fluke. (Upper bracket k=3/4 not yet run — the optimum may be higher;
  flagged for the larger eval, not tuned here.) Note `HEURISTIC_VALUE_NORM=15`, so k=2 is a *large*
  leaf reweighting — the optimum k should be tuned, not assumed.

## ⚠️ Contradiction resolved (results-discipline)

This **overturns a prior verdict**: DECISIONS.md 2026-05-14 recorded `meeple_K ∈ {0.5,1,2}` as **NULL**
("all 3 magnitudes identical at n=20", hypothesized an additive-on-saturating-cap dead-zone). That was
an **n=20** screen (CLAUDE.md: n=20 is one-σ noise; n=400 for a verdict). At **n=200 paired** the flat
`meeple_k=2` is **+179.5 elo, z=9.92** — unambiguous. The old null was **underpowered**, and the term
sits *after* the cap (so the dead-zone hypothesis was wrong). The meeple-economy lever was real and
missed for ~5 weeks — a direct instance of the bracket-and-power lessons.

## ⚠️ The load-bearing caveat (INTERPRETATION — gates promotion)

**These are heuristic-vs-heuristic results: a v2.8 leaf beating the v2.7 leaf in HeuristicMCTS.** v2.7's
own diagnosed failure mode #4 was *over-committed meeples* (DECISIONS 2026-05-14). A meeple-economy term
that rewards keeping meeples free **directly counters that v2.7 weakness** — so a large heur-vs-heur Elo
gain is **consistent with both** "real absolute strength gain" AND "style that exploits v2.7's specific
over-commitment." Beating the v2.7 ruler is **not** the same as absolute strength (CLAUDE.md anchor
lesson). The decisive disambiguator is whether the term **also helps the neural production policy**
(iter8 leaf-swap, Phase 7) and an out-of-lineage reference — run next. **No promotion on heur-vs-heur
alone.**

→ Phase 6 composes the candidate from the meeple-economy term (flat, the strongest form);
`v28_completion` is excluded (null full-game). Phase 7 runs the neural leaf-swap as the generalization
gate.
