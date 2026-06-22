# RoD v2.8 Continuation Probe — Ruler Matchups (Phase 5)

**Question:** does the learned continuation close the **equal-leaf gap** to the strong out-of-lineage heuristic ruler? Data: [`RULER_MATCHUPS.csv`](RULER_MATCHUPS.csv). Harness: `scripts/heuristic_v28/v28_handoff_orch.sh` → `scripts/level2/eval_hybrid_handoff.py` (carc-orch SHM, `--agent-a iter8` = neural agent from `--ckpt`, `--meeple-k 2.0` = v2.8 leaf both sides), deck-paired both seats, fresh band 1922100000.

## Result vs the strong ruler (heur@3200_v28)

| agent (both v2.8 leaf, NeuralMCTS@200 vs HeuristicMCTS@3200) | n | W/D/L | winrate | Elo (A−B) | ±1σ | paired z |
|---|---|---|---|---|---|---|
| **`iter8 + v2.8`** (frozen parent, anchor) | 200 | — | — | **−38.4** | — | −1.56 |
| **`RoD_iter_01 + v2.8`** | 200 | 107/3/90 | 0.542 | **+29.6** | 24.7 | **+1.17** |

- **Swing of ~+68 Elo** in the gap-to-ruler; the sign **flipped from negative to positive**.
- **Transitivity check (corroboration):** parent −38.4 + (RoD vs parent +53.4) ⇒ predicted +15.0 vs heur@3200_v28; **measured +29.6** — same sign, same ballpark. The +53 over the parent is therefore a **real strength gain**, not a non-transitive "tuned-to-beat-iter8" artifact.

## Interpretation

- **The equal-leaf gap CLOSED.** Both the v2.7 parent (iter8: −28.7 vs heur@3200_v2.7) and the v2.8 parent (iter8: −38.4 vs heur@3200_v28) sat clearly *behind* deep heuristic search. After one continuation iteration under the v2.8 leaf, `RoD_iter_01` is **at parity-or-slightly-ahead** of heur@3200_v28 (+29.6 point estimate).
- **But not yet a significant "beats the heuristic" claim.** At n=200 the +29.6 has z=1.17 (not above the 2σ bar). The rigorous, significant statement is the **gap-closure** (via the +53.4 / z3.51 over the parent); the direct ruler number says "parity-or-better," not "significantly exceeds."
- **This is the project's structural-blocker #2, moved.** CLAUDE.md: "superhuman requires the *learned* components to **exceed the heuristic**, which they don't yet." Under v2.7 they couldn't even reach it; under v2.8, re-distillation brings the learned agent **up to** deep-heuristic-search level at equal leaf. Whether it can *exceed* it (significantly) is the iter2 / higher-n question.
- **Not superhuman.** Still a hand-crafted leaf, no human/external anchor. "Matches deep heuristic search at equal leaf" ≠ superhuman.

## Open follow-ups (cheap → expensive)
- Firm up `RoD vs heur@3200_v28` at n=400–800 (is it parity, or significantly ahead?).
- `RoD vs heur@800_v28` (matched-budget ruler; expected comfortable RoD win, completes the picture).
- **iter2 (compounding):** does `RoD_iter_02` push *significantly* past heur@3200_v28 — the first "learned > heuristic at equal leaf"?
