# PRE-TOOL AUDIT — what iter8 actually misses, and whether a tool/action-ranker branch is justified

> **Measurement only.** No training, no MCTS integration, no production change, no promotion.
> This audit decides *whether* and *what* to build, not *how*. Base commit `1924261`.
> Champion unchanged: `flywheel2_champion_iter8` ([governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml)).
>
> **Every number cites its source.** **FACT** = read off an artifact (cited). **INTERPRETATION** =
> my reading. Clairvoyant labels are kept distinct from fair-information; solver labels from teacher
> labels; same-band paired conclusions from cross-band.

## TL;DR (INTERPRETATION, evidence below)

> **Recommendation: MORE MEASUREMENT before tool-coding — do NOT start the tool branch on this
> evidence.** The originally-proposed raw per-action tools (immediate-score / meeple / completion
> deltas) are **provably uninformative at the endgame** (constant across legal moves), and the one
> existing cheap quantity that *does* rank endgame actions — the v2.7 leaf — is already what iter8
> uses. iter8's endgame deficit is a **search-depth / policy-weighting** problem (already patched by
> the hybrid-handoff, CL-026), not a missing-feature problem. The audit's real blind spot is the
> **opening/midgame**, where iter8 is strong and where the raw quantities *do* vary — but there are
> **no ground-truth labels there**. Build the midgame reference first; only then revisit tools.

## Dataset (Phase 2) — FACT

408 exact-solver-labelled endgame positions, 17,674 action rows
([ACTION_AUDIT_DATASET.jsonl](ACTION_AUDIT_DATASET.jsonl), [manifest](ACTION_AUDIT_MANIFEST.json)):
K=2 (150, clairvoyant=marginalized), K=3 (71, clairvoyant), K=4 (187, clairvoyant; 4 source buckets
greedy/iter8/heur@3200/hybrid). Pipeline validated — recomputed agent top-1 reproduces the committed
[L23](../level2/LEVEL2_L23_VERDICT.md)/[K4](../level2/LEVEL2_K4_PROBE_VERDICT.md) verdicts to the
decimal (heur@3200 K=2 0.837, iter8 K=4 0.561, etc.).

---

## The 10 questions

### 1. What does iter8 actually miss? — FACT + INTERPRETATION
iter8 plays the EXACT endgame **worst of all tested agents** at every depth: top-1 **0.667 (K=2) /
0.592 (K=3) / 0.561 (K=4)** vs heur@3200 0.837/0.618/0.679 (BASELINE_RESULTS.csv; replicates
CL-025/CL-027). The misses are **small in points but frequent** (mean regret 0.6 at K=2 → 1.5 at
K=4; blunders >10pt only 0–3%). **INTERPRETATION:** iter8's weakness is endgame *precision*, decoupled
from full-game Elo (it beats heur@800/@1600 full-game, L2-2). Its misses are **structural/positional**,
not point-grabs it failed to take.

### 2. Are misses concentrated by source / phase / K / difficulty / type? — FACT
Strongly concentrated by **sharpness**: on sharp (best-vs-2nd gap≥2) K=4 positions iter8 top-1 **0.395
/ regret 3.34** vs forgiving 0.604 / 1.01 (BASELINE_RESULTS_BY_DIFFICULTY.csv). By **source**: worst on
greedy-generated K=4 (0.44) vs its own (0.65) — but **source is confounded with difficulty** (iter8-gen
endgames are objectively easier: within1 28.5 vs greedy 7; CL-027). Deficit **deepens K=2→K=3→K=4**.
**INTERPRETATION:** iter8 both *reaches* easier endgames *and* mishandles sharp/high-branching/OOD ones
worst — two compounding effects.

### 3. Do simple baselines already explain the misses? — FACT (decisive)
**No.** Kendall-τ of cheap per-action quantities vs the exact K=2 solver value:
**v2.7 leaf τ=+0.55 (informative in 89% of positions); immediate-score-delta, meeple-delta,
score-diff-after = τ undefined in 100% of positions (constant across all legal moves)**
(BASELINE_RESULTS.md). Consequently every selector built on the raw quantities collapses to
**exactly random** (top-1 0.238). Of iter8's 158 misses, only **8 (~5%) are "v2.7-rankable"** (its own
static leaf scores the better move higher); **77 (49%) beyond the static leaf** (deep search recovers
most); **69 (44%) "both-miss"** (heur@3200 also fails) (DISAGREEMENT_CATEGORIES.csv).
**INTERPRETATION:** no simple existing per-action feature explains the misses; they live in deeper
search / position structure.

### 4. Is v2.7 / heur@3200 already enough to explain the target? — FACT + INTERPRETATION
The **static** v2.7 leaf explains ~55% of the K=2 action ranking (τ). **Deep v2.7 search** (heur@3200)
explains much more (K=2 top-1 0.837) and is the **strongest known directly-tested practical ruler** —
but **not optimal and not universal**: it is 2nd-worst at K=3 (0.618) and still leaves ~32% of K=4
sub-optimal; ~44% of iter8's misses are positions heur@3200 *also* misses. **INTERPRETATION:** deep v2.7
is a strong-but-incomplete explainer. (Per [EVIDENCE_HYGIENE_NOTES.md](EVIDENCE_HYGIENE_NOTES.md): do
not call heur@3200 "most endgame-precise on every suite.")

### 5. Is there evidence explicit tools help beyond the current net? — INTERPRETATION (weak/mixed)
At the **endgame**: weak. (a) raw-delta tools — no (uninformative); (b) static per-action v2.7-score
tool — helps ~5% of misses; (c) the bulk need **search depth** (hybrid-handoff, *not* a tool) or are
**beyond v2.7 entirely** (the hard 44%, clairvoyance-confounded). The structural pro-tool case
([INPUT_INVENTORY.md](INPUT_INVENTORY.md)) is that **bag composition (#6)** and **explicit per-action
v2.7 score (#9)** are genuinely ABSENT from the net input — but the endgame data does not show they'd
move the needle. **⚠️ The audit is endgame-only; the midgame (iter8's strength, raw quantities vary
there) is untested for lack of labels.** The learned-ranker cell remains genuinely untested (the
value-ranking kill-test covered scalar value / sibling-ranking / attention-swing, NOT a tool-augmented
ranker).

### 6. Which 2–3 feature groups first, if any? — INTERPRETATION
If tools proceed despite the recommendation, the most-defensible first candidates (each gated on the
weak offline test FIRST):
1. **Bag-aware completion / remaining-tile-composition** (#6) — the cleanest ABSENT input; tests
   "which tiles can still close my open features"; **game-long, not endgame** → highest upside.
2. **Explicit per-action v2.7 score / Δ to an action-ranker** (#9) — currently reaches the agent only
   via the MCTS leaf; cheap to test; modest endgame upside but plausible for midgame action-pruning.
Build **no third** group initially.

### 7. Which feature groups to avoid for now? — INTERPRETATION
- **Raw immediate-score / meeple-delta / completion-flag tools** — proven uninformative at the
  endgame (constant across legal moves; selectors == random).
- **A clairvoyant-solver-distilled endgame head** — targets the hard 44% but on clairvoyant labels
  (transfer unproven), the hardest slice, with high washout-at-depth risk.

### 8. Failure modes of each proposed group? — INTERPRETATION
- *Bag-aware:* deck over-fitting/leakage; the net may already infer it; marginal over the v2.7 leaf's
  coarse closure-anticipation; washout under MCTS.
- *v2.7-score-to-ranker:* redundant with the MCTS leaf; risks **re-encoding the heuristic the net is
  meant to exceed** (the value-ranking kill-test failure: near-zero learned ranking over v2.7); washout
  at deep sims (the deepteacher / sims-washout lesson).

### 9. Exact offline test the first tool group must pass (WEAK gate) — INTERPRETATION
On a **held-out** set of SHARP / OOD exact-label positions (K=2 fair-info-safe + K=4 sharp / greedy-gen,
where iter8 is worst at 0.40–0.44), a light net+tool **action-ranker** (no full retrain) must beat
**iter8's own action choice** on **top-1 agreement and mean regret by > noise**, using **no clairvoyant
info**. If it cannot beat iter8 offline on the very positions iter8 is worst at, it will not help in
search.

### 10. What would make us stop the tool branch? — INTERPRETATION
- Weak gate fails (ranker can't beat iter8 on held-out sharp/OOD exact positions).
- Passes offline but **washes out at play-depth** (sims-washout lesson) when embedded in search.
- Gains exist only on **clairvoyant** labels that don't survive the marginalized-K=3 fair-info test
  ([FAIR_INFORMATION_LABELS_NOTE.md](FAIR_INFORMATION_LABELS_NOTE.md)).
- The learned ranking is **near-zero over the v2.7 baseline** (the value-ranking kill-test reappears).

---

## Staged decision gates (INTERPRETATION)

| gate | criterion | current audit verdict |
|---|---|---|
| **WEAK** | tool features beat iter8's action choice on held-out sharp/OOD exact-label positions (offline ranking) | **NOT clearly plausible from endgame evidence** for raw-delta tools (uninformative); UNTESTED for bag/v2.7-score tools; midgame unmeasured |
| **MEDIUM** | tool features approach v2.7/heur@3200 ranking OR improve a combined net+tool ranker beyond either alone | untested |
| **STRONG** | improves play-depth Elo embedded in search and does NOT wash out at deeper sims | untested (high washout risk per the sims-washout lesson) |

**Rule applied:** *"Do not recommend full integration unless at least the weak gate is clearly
plausible from audit evidence."* It is **not** clearly plausible from the endgame evidence. ⇒ do not
proceed to full integration now.

## Final recommendation (INTERPRETATION)

**MORE MEASUREMENT, not tool-coding yet.** Two cheap measurements would actually move the decision:
1. **A midgame reference probe** — the audit's blind spot. iter8's strength and the raw quantities'
   variance both live in the opening/midgame, which has no ground-truth labels. Without it, the tool
   question is being judged only where tools look worst.
2. **The marginalized-K=3 fair-info slice** (gated on the make/unmake solver) to confirm the
   clairvoyant endgame ranking transfers to honest play.

If Joshua chooses to proceed to tool-building regardless, start with **bag-aware completion features**
(group #1), build the offline ranker, and **gate hard on the weak test** against iter8 on the sharp/OOD
slice. Avoid raw-delta tools and the clairvoyant-distilled head.

## Files produced by this audit
- [EVIDENCE_HYGIENE_NOTES.md](EVIDENCE_HYGIENE_NOTES.md) (Phase 0) + 4 surgical doc patches
- [INPUT_INVENTORY.md](INPUT_INVENTORY.md) (Phase 1)
- [ACTION_AUDIT_DATASET.jsonl](ACTION_AUDIT_DATASET.jsonl) + [ACTION_AUDIT_MANIFEST.json](ACTION_AUDIT_MANIFEST.json) (Phase 2)
- [k2_childvalues.jsonl](k2_childvalues.jsonl) (re-solved K=2 full per-action value maps)
- [BASELINE_RESULTS.md](BASELINE_RESULTS.md) + [.csv](BASELINE_RESULTS.csv) / [_BY_SOURCE](BASELINE_RESULTS_BY_SOURCE.csv) / [_BY_DIFFICULTY](BASELINE_RESULTS_BY_DIFFICULTY.csv) (Phase 3)
- [DISAGREEMENTS_TOP100.md](DISAGREEMENTS_TOP100.md) + [DISAGREEMENT_CATEGORIES.csv](DISAGREEMENT_CATEGORIES.csv) (Phase 4)
- [FAIR_INFORMATION_LABELS_NOTE.md](FAIR_INFORMATION_LABELS_NOTE.md) (Phase 5)
- This report (Phase 6). Scripts: `scripts/level2/{build_action_audit_dataset,resolve_k2_childvalues,score_baseline_selectors,disagreement_audit}.py`
