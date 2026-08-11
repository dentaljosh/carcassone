# RoD v2.8 Continuation Probe — Ruler Matchups (Phase 5)

**Question:** does the learned continuation close the **equal-leaf gap** to the strong out-of-lineage heuristic ruler — and does it *exceed* it? Data: [`RULER_MATCHUPS.csv`](RULER_MATCHUPS.csv). Harness: `scripts/heuristic_v28/v28_handoff_orch.sh` → `scripts/level2/eval_hybrid_handoff.py` (carc-orch SHM, `--agent-a iter8` = neural agent from `--ckpt`, `--meeple-k 2.0` = v2.8 leaf both sides), deck-paired both seats, fresh band 1922100000, local 5800x + laptop work-stealing.

## Result vs the strong ruler (heur@3200_v28)

| agent (both v2.8 leaf, NeuralMCTS@200 vs HeuristicMCTS@3200) | n | W/D/L | winrate | Elo (winrate) | ±1σ | paired score margin | paired z |
|---|---|---|---|---|---|---|---|
| `iter8 + v2.8` (frozen parent, anchor) | 200 | — | — | **−38.4** | — | — | −1.56 |
| `RoD_iter_01 + v2.8` (pilot) | 200 | 107/3/90 | 0.542 | +29.6 | 24.7 | +1.80 | +1.17 |
| **`RoD_iter_01 + v2.8` (firmed, n=800)** | 800 | 412/14/374 | 0.524 | **+16.5** | 12.3 | **−0.36** | **−0.47** |

## Verdict: gap CLOSED to parity; does NOT exceed the heuristic

- **The n=200 +29.6 was an up-fluctuation; n=800 firms it to a TIE.** Winrate is marginally positive (+16.5 Elo, z=1.34 — not significant); the paired *score margin* is marginally negative (−0.36, z=−0.47). RoD wins slightly more games but by slightly smaller margins → net **statistical tie** with `heur@3200_v28`.
- **The gap closed.** Parent `iter8+v2.8` sat at −38.4 vs this ruler; `RoD_iter_01+v2.8` is at ~0. RoD reached **parity with deep heuristic search at equal leaf** — which neither the v2.7 nor v2.8 parent could.
- **It does NOT exceed the heuristic.** No significant win over `heur@3200_v28` at n=800. So this is "learned reaches deep-heuristic level," **not** "learned beats the heuristic."
- **Transitivity holds cleanly** (corroborates the parent matchup, not a non-transitive artifact): parent −38.4 + (RoD vs parent +53.4) ⇒ predicted +15.0; measured +16.5 (winrate) / ~0 (margin). The rigorous significant claim is the **+53.4 / z3.51 over the parent**; vs the ruler it is a tie.

## What this means for the project's blocker

CLAUDE.md structural-blocker #2: "superhuman requires the learned components to **exceed the heuristic**, which they don't yet." Under v2.7 the learned agent couldn't even *reach* deep heuristic search (iter8: −28.7 vs heur@3200_v2.7). Under v2.8, one re-distillation brings it **up to parity** — the gap is gone, but the learned agent has not yet crossed *above* the heuristic. **Exceeding** it (significantly) is the open question for iter2 / more iterations. **Not superhuman** (hand-crafted leaf, no human/external anchor).

## Follow-ups
- `RoD vs heur@800_v28` (matched-budget ruler; expected comfortable RoD win) — completes the picture.
- **iter2 (compounding):** does `RoD_iter_02` push *significantly above* heur@3200_v28 — the first "learned > heuristic at equal leaf"? Given iter1 captured the re-alignment gain and reached parity, this is the decisive open test.
- Phase-6 root audit (running): did RoD's root choices move toward `heur@3200_v28`'s — the mechanism behind the gap-closure?
