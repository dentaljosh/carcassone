# Evidence Epochs

Raw evidence is append-only; this file reclassifies which historical eras are trustworthy — it never deletes results.

**Layer:** INTERPRETATION (see [governance/README.md](README.md) for the 3-layer spine). This doc partitions the append-only raw evidence (`experiments/results.csv`, per-run `manifest.json`, raw per-game JSON, `clean_eval/CLEAN_RESULTS.csv`) into eras and states which eras are trustworthy for which purposes. It does not, and cannot, delete or rewrite any raw number.

## The 7 evidence epochs

| epoch_id | name | date range | scope of invalidation | superseded by |
|---|---|---|---|---|
| E0-river | River-vs-base era | before 2026-06-02 | River tiles in deck → off-distribution; all numbers incomparable to base-only | base-only reruns |
| E1-farmbug | pre-farm-scoring-fix | before 2026-05-29 | `opposite_farmer_side` typo → nondeterministic farm scores (~2.2% games), double-count | fix 2026-05-29 |
| E2-transposition | pre-transposition-fix | before 2026-06-02 (C2) | MCTS didn't dedup equivalent actions → visit-mass mis-split | C2 fix |
| E3-unmatched-leaf | unmatched-leaf (R1) era | before 2026-06-07 | yardstick HeuristicMCTS ran **v1** while agent ran **v2.7**; every vs-HeuristicMCTS absolute inflated, NON-TRANSITIVELY (no fixed discount) | clean matched-leaf reruns (`cleaneval_*`) |
| E4-overlap-seed | overlapping-seed era | before 2026-06-07 | eval seeds overlapped the self-play namespace → deck-comparability contamination | 1e9 seed floor + deck hashes |
| E5-R7-residual | R7-affected residual era | before 2026-06-07 | residual evals could silently fall back to pure v2.7 (v_nn=0) → residual numbers suspect | R7 runtime guard |
| E6-clean-ruler | clean-ruler era | 2026-06-07 onward | (trustworthy) runtime-verified provenance, 1e9 seeds, deck hashes, matched leaf | — current |

## How to use

- Every row in [`CLAIM_REGISTRY.csv`](CLAIM_REGISTRY.csv) and [`CHECKPOINT_LINEAGE.csv`](CHECKPOINT_LINEAGE.csv) references an `epoch_id` (or a pair, e.g. `old=E3, clean=E6`). When you read a claim or a checkpoint's evidence, read its epoch first — the epoch tells you what that number can and cannot be used for.
- A result from epoch E_k that is "invalidated" by a later epoch may **still be used for: debugging / qualitative / historical context** — it is not erased, only reclassified. State which of those purposes you are using it for. What it may NOT be used for is a quantitative comparison against a number from a different (later) epoch.
- **Epochs overlap.** A single number can sit in several epochs at once: a pre-2026-06-02 vs-HeuristicMCTS measurement is in **E0** (if River was in the deck), **E3** (unmatched leaf), and **E4** (overlapping seeds) simultaneously. Tag a result with every epoch whose invalidation scope covers it, not just the most recent one.
- Only **E6-clean-ruler** evidence (2026-06-07 onward) is trustworthy for new quantitative strength verdicts. See [`clean_eval/CLEAN_EVAL_AUDIT.md`](../clean_eval/CLEAN_EVAL_AUDIT.md) for the runtime-verified provenance behind E6.
