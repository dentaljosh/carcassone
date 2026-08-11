# Phase 4 — value-ranking kill-test VERDICT (2026-06-18)

**Bottom line: the value-as-leaf architecture swing is NOT supported. A relational/attention value
head does not out-rank a plain conv, and every learned formulation ranks siblings at ~chance while
the target is reliably rankable (v2.7 extracts τ=0.58). Recommendation: do NOT pursue the
architecture swing; pivot to measurement-first.**

## Setup
- **Dataset** (`value_ranking/VALUE_RANKING_DATASET_MANIFEST.json`): 1,494 decision nodes / 20,670
  child rows / **47 games**, merged from two leakage-disjoint shards (5800x seed-band 2024 + laptop
  seed-band 5000); harvest/oracle net = champion iter8; oracle = v2.7-leaf MCTS @400 sims.
- **Split:** leakage-safe **by game** (train 1077 / val 102 / test 315 groups).
- **Target:** parent-POV deep-oracle child value (the sibling-ranking label).
- **Gauge:** held-out Kendall-τ vs the oracle (NOT global value-correlation), + top-1, pairwise, regret.
- **Reference points:** v2.7 leaf τ = **0.579**; production net (MSE, millions of positions) τ = **0.081**;
  4A oracle ceiling: self-consistent (deterministic) + 0.644 vs a 1600-sim deeper oracle → target
  is reliably rankable ([VALUE_RANKING_LABEL_RELIABILITY.md](VALUE_RANKING_LABEL_RELIABILITY.md)).

## Arm results (held-out test, 315 groups; `VALUE_RANKING_RESULTS.csv`)
| arm | head | loss | params | **τ** | top1 | high-spread τ |
|---|---|---|---|---|---|---|
| A | conv | MSE (control) | 382k | −0.004 ± 0.015 | 0.095 | +0.022 |
| B | conv | ranking | 382k | **+0.029 ± 0.012** | 0.098 | +0.037 |
| C | **attention** | ranking (THE SWING) | 403k | +0.012 ± 0.014 | 0.162 | −0.004 |
| C0 | conv-wide | ranking (capacity-matched control for C) | 663k | +0.015 ± 0.015 | 0.083 | +0.016 |
| E | conv | ranking, advantage-centered | 382k | +0.014 ± 0.013 | 0.089 | +0.013 |

## Within-experiment contrasts (the actual questions)
- **Architecture (the swing): C(attn) − C0(conv, capacity-matched) = Δτ −0.002, z −0.12 → NO effect.**
  Attention is also −0.016 (z −0.89) vs the same-loss conv (B), and **worst on high-spread groups**
  (where ranking matters most: C = −0.004). The relational head does not unlock ranking.
- **Loss form: B(ranking) − A(MSE) = Δτ +0.032, z +1.63 → weak positive, not significant** (z<2).
  Ranking loss helps a hair; it does not change the picture.
- **Absolute: best arm τ = 0.029 vs v2.7's 0.579** — every learned arm ranks at **~3–5% of the
  achievable**.

## 4E decision-rule application
- B clears A? **Marginally** (z 1.6) — loss form matters a little, inconclusively.
- C clears A AND the capacity-matched conv (C0)? **NO** (z −0.12) → **relational architecture did NOT
  matter.** The swing fails its own gate.
- All arms fail while oracle labels are reliable? **YES** — the target is reliably rankable (v2.7=0.58;
  oracle self-consistent; 0.644 vs deeper oracle), yet all arms ≈ chance ⇒ **the tested
  learned-ranking formulations are strongly DISFAVORED** (not probe-limited).

## Caveats (honest bounds)
- **From-scratch / data scale:** arms trained from random init on 1077 groups (~15k rows). This bounds
  the *absolute* τ. BUT the data-scale escape is closed from the other side: the **production net
  trained on MILLIONS still ranks at 0.081** — also ≪ v2.7. So "more data unlocks it" is not
  supported; the learned per-position value scalar underperforms the structural v2.7 score at sibling
  discrimination regardless of scale. The *relative* within-experiment result (C≈C0) is scale-robust.
- **Arm D (+OWN oracle channels) not run** (the core dump omitted terminal-ownership planes). But D's
  question — "is the sibling-Q rankable at all?" — is already answered **YES** by v2.7 (0.58) and the
  oracle's self-consistency. So the gap is *learnability of a per-position scalar*, not rankability.
- Per the spec's own caution, this does NOT prove "value-as-leaf is categorically impossible" — it
  proves the *tested* swing (relational arch + ranking loss, this scale) is disfavored, with no
  positive signal pointing at a near-variant that would work.

## Decision (feeds Phase 5)
The architecture swing was the cheap, decisive test gating the value-head direction. It came back
**negative**: a board-spanning relational head does not lift sibling ranking over a conv, and learned
value scalars rank ~20× below the v2.7 leaf the system already uses. **Do not invest in a value-head
retrain on this path.** The live fork is **measurement-first** (a non-clairvoyant engine + an external/
human ruler) — necessary regardless and now the highest-info next move.
