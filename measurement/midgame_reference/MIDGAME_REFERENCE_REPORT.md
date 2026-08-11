# MIDGAME REFERENCE REPORT — does the midgame have a tool/action-ranker case?

> **Measurement only.** No training, no flywheel, no MCTS integration, no production change, no
> promotion. Base commit `f84eb01`. Champion unchanged: `flywheel2_champion_iter8`.
> Built on a **1000-position midgame sample** (250 each from greedy / heur@3200 / hybrid:8:3200 /
> iter8 self-play; 200 each in 5 tiles-remaining bands K=52/40/28/16/10), labelled by a
> **deep-search teacher** (heur@800/1600/3200), the **production agent** (iter8 MCTS@200 + policy
> prior), and **static v2.7**. **No exact solver exists at midgame K — every reference is a soft
> label with known bias; none is ground truth.** All search descends the real fixed deck order
> (clairvoyant-leaning; weaker leakage than endgame). **FACT** = read off an artifact (cited).
> **INTERPRETATION** = my reading. See [REUSE_AND_SCOPE.md](REUSE_AND_SCOPE.md).

## TL;DR (INTERPRETATION, evidence below)

> **Recommendation: do NOT start the tool branch. The midgame — the pre-tool audit's blind spot —
> shows the SAME pattern as the endgame, more sharply.** The deep-search teacher's preferences are
> explained almost entirely by **static v2.7** (Kendall τ **+0.61**, 90% informative; offline
> ranker with v2.7 = **0.453** test top-1 vs **0.147** without it — v2.7's standardized coefficient
> **0.594** dwarfs every raw/bag feature's **≤0.013**). The **raw per-action deltas are sparse**
> (informative ~22–36% of positions, τ ~0.22–0.30) — *not* materially less sparse than the
> endgame. The **new bag-aware/structural features vary a LOT** (open-edge-delta / scarcity vary
> in ~55–62% of positions) **but carry essentially zero teacher-aligned signal** (τ **+0.01**), and
> recover only **~2–6%** of the cases where v2.7 or iter8 disagrees with the teacher. Where v2.7 is
> wrong, the recovery comes from **deeper search** (iter8 recovers ~30% of v2.7's misses; heur@800
> recovers ~47% of iter8's misses), **not** from any cheap feature. **90% of disagreement cases are
> structural/positional**, not cheap-feature-mechanism. The weak gate is **not** plausible in the
> midgame either. ⇒ **measurement says no.**

## The sample (FACT)

[MIDGAME_POSITION_SAMPLE.jsonl](MIDGAME_POSITION_SAMPLE.jsonl) — 1000 TILES-phase positions, built
by replaying the full-game action prefixes in `l23_k4_expand.jsonl` to earlier plies
([MIDGAME_SAMPLE_MANIFEST.json](MIDGAME_SAMPLE_MANIFEST.json)). Balanced 250/source × 200/band.
Median legal **tile** actions grow opening→pre_endgame **22 → 40** (vs a handful at K≤4) — so the
midgame genuinely offers far more action variation than the endgame audit could see.

## The 10 questions

### 1. Do action-delta features vary substantially in midgame? — FACT (mixed)
Partly. From [MIDGAME_FEATURE_MANIFEST.json](MIDGAME_FEATURE_MANIFEST.json) (informative = varies
across a position's legal actions): **v2.7 0.90**; the **structural/bag features vary the most** —
open-edge-delta **0.61**, closure-proximity **0.57**, owner **0.54** — but the **raw immediate
deltas are still sparse**: imm-net **0.315**, completion **0.33**, best-meeple **0.36**, meeple
**0.22**, claim-gain **0.08**. So the **structural** quantities vary much more than raw deltas, but
the raw deltas themselves are **not** dramatically less sparse than at the endgame.

### 2. Are they more informative than in K≤4 endgames? — FACT: **no.**
The raw deltas are about the **same** sparsity/signal as the endgame, NOT more. Midgame imm-net
informative **0.315** vs endgame K=2 **0.32**; midgame τ(imm-net)=**+0.30** vs endgame **+0.49**
(if anything *weaker*, because the teacher is a soft deep-search value, not the exact solver). The
audit's hypothesis that "raw quantities vary far more / carry more signal in the midgame" is
**not borne out** for the raw deltas. (It *is* true that more structural quantities are non-constant
— but see Q3: that variation is not teacher-aligned.)

### 3. Does bag-aware completion add signal beyond raw completion/score? — FACT: **no.**
This is the sharpest negative. The bag-aware/structural features vary in ~55–62% of positions but
their Kendall τ vs the teacher child-Q ranking is **~+0.01** (open-edge-delta **+0.016**,
bag-closure **+0.009**) — i.e. they vary a lot but **the variation is orthogonal to teacher value**.
As selectors they reach top-1 **0.10** (below even the raw-score selectors at 0.13, vs v2.7 0.48).
The offline ranker confirms it: raw+bag features alone → **0.147** test top-1; their standardized
coefficients are all **|β| ≤ 0.013**. **Bag-aware completion adds no measurable signal over raw
score, and very little over random** — `bag_city_supply` is even **constant across actions** (the
deck is the same whichever tile you place; it discriminates positions, not actions).

### 4. Does v2.7 static already explain most deep-search teacher preferences? — FACT: **yes.**
[MIDGAME_BASELINE_RESULTS.md](MIDGAME_BASELINE_RESULTS.md): v2.7-static **τ +0.61** (90% informative),
top-1 **0.48**, and on **high-confidence** teacher decisions (gap≥0.15, n=41) v2.7-static **0.951**,
iter8 **0.976**, heur@800 **0.976** — all near-perfect, while cheap features sit at 0.24–0.41. The
offline ranker jumps from 0.147→**0.453** the instant v2.7 is added (coef **0.594**). **v2.7 — which
is already iter8's MCTS leaf — explains nearly all of the deep teacher.** This is the brief's
explicit *do-not-proceed* condition #1.

### 5. Where does iter8 beat v2.7 static? — FACT: **the opening, via search — not a feature.**
By band, iter8 vs v2.7-static top-1: opening **0.61 vs 0.485**, early_mid 0.50 vs 0.51, mid 0.485 vs
0.43, late_mid 0.45 vs 0.46, **pre_endgame 0.39 vs 0.515**. iter8's edge over its own static leaf is
**front-loaded in the opening and inverts by the endgame** (iter8 ends up *worse* than static v2.7
near K=10 — reproducing the endgame audit's "iter8 weakest at the endgame", CL-027). Net-of-net:
iter8 recovers **154** of v2.7's misses but throws away **147** (≈ wash; overall 0.487 vs 0.480).
The net's value over v2.7 is **real but small and search-mediated**, concentrated early.

### 6. Where does iter8 lose to deep heuristic? — FACT: **search depth, not a missing feature.**
On the **513** positions where iter8 ≠ teacher, what recovers the teacher's pick? **heur@800 0.468**,
**v2.7-static 0.287**, composite-v2.7+delta 0.271 — but **raw/bag features only 0.06–0.07**. So
iter8's misses are recovered by **deeper/heuristic search**, essentially never by a cheap per-action
feature. Same as the endgame: the deficit is **policy-weighting / search depth**, addressed by the
hybrid-handoff (CL-026), not by a tool.

### 7. Are the most important misses tool-addressable, search-depth-addressable, or unclear? — FACT
[MIDGAME_DISAGREEMENT_CATEGORIES.csv](MIDGAME_DISAGREEMENT_CATEGORIES.csv): of 667 disagreement
cases, **structural/unclear 471 + structural/closure 133 = 604 (90.6%)**; cheap-feature-mechanism
only **63 (9.4%)** (meeple 27, completion-greed 21, bag/scarcity 9, immediate-score 6). **The misses
are overwhelmingly structural/positional / search-depth-addressable, not tool-addressable** —
mirroring the endgame's ~82 structural vs ~7 completion split.

### 8. Which feature groups, if any, deserve a small offline action-ranker test? — INTERPRETATION
**None passes the bar.** The offline ranker was *already run here* as the diagnostic (it is the
cheapest possible test): raw+bag features alone reach **0.147**, and contribute **nothing** once
v2.7 is present (every non-v2.7 coef ≈ 0). There is no feature group with **independent** signal to
promote. The only quantity that ranks is v2.7 — which iter8 already consumes at its leaf.

### 9. Which feature groups should be avoided for now? — INTERPRETATION
- **Bag-aware completion / open-edge / scarcity** — they *look* attractive (vary in ~60% of
  positions) but are a **variance trap**: τ ≈ 0 vs teacher value, ~2% recovery on disagreements.
  Building them would chase variation that is not aligned with strength.
- **Raw immediate-score / completion / meeple deltas** — sparse and weak here as at the endgame;
  completion-greed remains a hazard (highest q-regret among the cheap selectors).
- **An explicit per-action v2.7-score tool** — would only re-feed the net the heuristic it already
  uses at the leaf (the value-ranking kill-test failure); composite-v2.7+delta ≈ v2.7-static alone.

### 10. What is the next gate before integration? — INTERPRETATION
There is **no next tool gate** — the weak gate is failed in both regimes now. The live levers remain
the **non-tool** ones already on the program: **search-depth / policy-weighting** (the hybrid-handoff
direction, which is where both the endgame and midgame misses actually live) and the structural
blockers named in CLAUDE.md (measurement reference, learned components exceeding the v2.7 leaf).

## Decision framework (applied) — INTERPRETATION

**Proceed to a small offline action-ranker ONLY if ALL hold:**
| condition | verdict |
|---|---|
| features vary in a meaningful fraction of midgame positions | **partly** (structural yes; raw deltas no) |
| ≥1 feature group explains high-confidence teacher prefs beyond random AND beyond immediate-score greed | **NO** — only v2.7 does (τ+0.61); bag/structural τ≈0.01 |
| the group helps specifically in iter8-vs-teacher OR v2.7-vs-teacher disagreement cases | **NO** — ~2–6% recovery; deeper search recovers ~30–47% |
| plausible path to improve *beyond* static v2.7, not merely clone it | **NO** — composite-v2.7+delta ≈ v2.7-static; non-v2.7 coefs ≈ 0 |

**Do NOT proceed if ANY hold — all four fire:**
| stop condition | verdict |
|---|---|
| v2.7 static explains nearly all high-confidence teacher choices | **YES** (0.951 on sharp; τ+0.61) |
| feature signals sparse/unstable | **YES** (raw sparse ~30%; structural varies but τ≈0) |
| features only help easy positions | **YES** (cheap features collapse to ~0.06 on disagreements) |
| gains disappear in teacher-disagreement cases | **YES** (~2–6% recovery) |
| the only successful feature is "v2.7 score," no independent signal | **YES** (ranker: v2.7 coef 0.594, rest ≈0) |

## Staged gates (carried from the pre-tool audit) — INTERPRETATION
| gate | endgame audit | **midgame (this report)** |
|---|---|---|
| **WEAK** (features beat iter8/v2.7 on the target, offline) | not plausible (sparse / v2.7-redundant) | **not plausible** (τ≈0 structural; ~2–6% disagreement recovery; ranker no independent signal) |
| **MEDIUM** (features approach v2.7 OR improve a combined ranker) | untested | **failed** (raw+bag 0.147; +v2.7 only restates v2.7) |
| **STRONG** (improves play-depth Elo, no washout) | untested | untested — moot, weak gate failed |

## Risks & blind spots of THIS measurement (INTERPRETATION — kept honest)
1. **Soft teacher, not ground truth.** heur@3200 is the strongest practical midgame ruler but is
   itself imperfect and **clairvoyant-leaning** (real fixed deck in its lookahead). If the true
   midgame optimum diverged systematically from heur@3200 in a way the cheap features capture, this
   would understate them — but the features show τ≈0 against the teacher's *ranking* (not just its
   top-1), which is hard to explain away as teacher error. A fair-information teacher is intractable
   ([FEATURE_BACKLOG.md](FEATURE_BACKLOG.md) B6).
2. **Bag-aware features are a coarse proxy** (`_deck_city_supply` over-counts; per-component
   open-edge identity not tracked across merges — B1/B2). A *precise* bag-completion matcher might
   carry more signal — but it is half a tool, and the coarse proxy already varies in 60% of
   positions with τ≈0, so a sharper version would have to convert *zero* correlation into signal,
   not merely add resolution. Low prior.
3. **Source ≠ difficulty.** iter8/greedy reach different midgames (confounded, as in the K4 probe);
   conclusions are reported same-band/same-source where it matters. The pattern holds across all
   four sources (BY_SOURCE.csv).
4. **iter8 labelled by MCTS@200 net-on-CPU** (production knobs); the policy *prior* (no search) is
   far weaker (0.259) — search matters, as expected — but the choice used is the production agent's.

## Bottom line (INTERPRETATION)
The midgame reference the pre-tool audit asked for has been built and answers the open question:
**there is no midgame tool case either.** v2.7 (already the leaf) explains the deep teacher; the
raw deltas are sparse; the bag-aware/structural features vary widely but carry no teacher-aligned
signal and recover almost none of the disagreements; iter8's residual edge over v2.7 is small,
search-mediated, and front-loaded in the opening. **Do not start the tool branch.** The decision
is now grounded in both regimes — endgame (where these tools look worst) and midgame (where the
audit expected them to look best). They don't.
