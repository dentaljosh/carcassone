# SEARCH / POLICY MIXING — Final Decision Report

> **Measurement only. No training, no flywheel, no champion change, no promotion, no production
> routing integration.** Champion of record unchanged: `flywheel2_champion_iter8`
> ([governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml)). Base commit `8c42550`.
> **FACT** = read off a cited artifact. **INTERPRETATION** = my reading. Three metric planes are
> kept strictly separate and are **non-transitive**: full-game Elo · root-action agreement ·
> teacher-imitation. Clairvoyant/real-deck labels kept distinct from fair-information.

## TL;DR (INTERPRETATION)
> **iter8's value is whole-game policy strength, not per-move precision. It is best used as a
> standalone agent or the early leg of the fixed-K hybrid — NOT as a root prior, candidate
> generator, or per-move deep-search emulator (it loses every per-move-imitation comparison to
> heuristic search). The residual/value head is a SMALL positive full-game lever (+35 elo, z=1.52 at
> n=200 — suggestive, sub-2σ; neutral/harmful at the root but it WINS games — keep it, don't lean on
> it). No dynamic routing rule has any root-level headroom over fixed
> K≤8 — "use deeper heuristic search" dominates per-move, so a dynamic hybrid is not justified to
> build. The bottleneck is unchanged: the v2.7 leaf caps learned strength, and no mixing of the
> existing components breaks that cap. Recommended next branch: a stronger leaf (v2.8) and/or an
> external/human anchor — NOT a search/policy-mixing or dynamic-hybrid build.**

## Evidence base (FACT)
- **Root-action audit** ([ROOT_ACTION_AUDIT.md](ROOT_ACTION_AUDIT.md)): 1000 midgame positions, every
  variant's root pick vs the heur@3200 teacher, by band / disagreement / sharpness.
- **Routing analysis** ([ROUTING_RULE_ANALYSIS.md](ROUTING_RULE_ANALYSIS.md)): can a cheap signal
  beat fixed-K at the root?
- **Residual full-game pilot** ([RESIDUAL_ROLE_AUDIT.md](RESIDUAL_ROLE_AUDIT.md)): iter8@resid0.25 vs
  iter8@resid0, paired, fresh band b360, n=200 (local+laptop orch).
- **Reused, not re-run:** fixed-K hybrid full-games ([../level2/LEVEL2_HYBRID_VERDICT.md](../level2/LEVEL2_HYBRID_VERDICT.md));
  iter8 vs heur@800 +58.7 elo full-game (PRODUCTION.yaml champion validation).

## The seven decision questions

### 1. Is iter8 useful primarily as standalone / root-prior / candidate-generator / early-specialist / late-liability / none? (INTERPRETATION)
- **standalone agent — YES** (its established role): full-game it beats heur@800 (+58.7 elo) and
  heur@1600 — strength the root metric cannot see.
- **early-game leg of the fixed-K hybrid — YES, supported**: by band, iter8's per-move competence is
  front-loaded (opening 0.61 → endgame 0.39) and inverts to *worst* in the endgame; the fixed-K
  hybrid that hands the endgame to deep heuristic beats iter8 (+20.9 elo, z=5.79) — gap-closing.
- **root prior / candidate generator — NO**: the raw policy argmax matches the teacher only **0.259**
  (vs search 0.487, heur@800 0.658). The policy *needs* search; alone it is a weak ranker.
- **per-move deep-search emulator — NO**: heur@800 out-imitates iter8 in **every** band, sharpness,
  branching and source cell; even equal-budget **heur@200 (0.578) beats iter8@200 (0.487)**.
- **late-game liability — YES, locally**: weakest in the endgame; this is exactly what the hybrid patches.

### 2. Does iter8 policy improve heuristic search at equal budget? (FACT → INTERPRETATION)
**No, for per-move imitation.** HEUR_200 (0.578) > ITER8_PROD@200 (0.487) vs the teacher, and
heur@800 dominates everywhere. **BUT** this is the imitation plane; full-game iter8 > heur@800. So
the honest answer: **the net policy does not help a search *imitate the deep teacher per-move*, yet
the iter8 agent is full-game-stronger than heur@800** — the gain is whole-game, not per-move. There
is no cheap-budget regime where adding the policy to heuristic search visibly helps the teacher metric.

### 3. Does residual/value contribute anything durable? (FACT → INTERPRETATION)
**Root: no** — removing residual *improves* root agreement (0.503 vs 0.487) and is teacher-right more
often on the 196 flips (0.219 vs 0.138). **Full-game (n=200 paired, b360): yes, small + suggestive** —
iter8@resid0.25 vs resid0 = 110W/90L, **+1.945 pts/game, +34.9 elo, paired z=1.518** (reverses the
n=20 noise of −1.45; consistent with PRODUCTION.yaml's "validated lever," but **z=1.52 < 2σ** so
inconclusive by the project's own n-threshold rule). PRODUCTION.yaml notes iter8 is "~95% policy."
**INTERPRETATION:** the residual head is **durable-but-small and non-transitive** — it *hurts*
per-move deep-teacher imitation yet *wins games* (+35 elo). **Keep it; don't drop it; don't lean on
it for strength gains** — the policy is load-bearing and the value ceiling is the v2.7 leaf, not the
residual blend.

### 4. Does dynamic hybrid routing beat or plausibly improve on fixed K≤8? (FACT → INTERPRETATION)
**No evidence for it.** Cheap signals *do* sort iter8's root-error (visit-concentration quartile
spread 0.408; policy-confidence 0.264) — but **every** threshold router collapses to "always
heur@800" (0.659 ≈ always-heur 0.658), because heur@800 ≥ iter8 in every stratum; even a perfect
iter8/heur800 router caps at 0.727. The fixed-K sweep is monotone in heur-coverage — a sharpness rule
would just route *more* to the heuristic, i.e. the fixed-K sweep with larger K. **A dynamic hybrid
would duplicate an already-stronger baseline → do not build** (the brief's explicit stop condition).
Fixed K≤8 stands as the best-characterized hybrid (gap-closing, not champion — LEVEL2_HYBRID_VERDICT).

### 5. Which variant, if any, deserves a larger full-game eval? (INTERPRETATION)
- **The residual pilot** is the only new full-game eval that was warranted; it ran at n=200 and came
  back **borderline (+35 elo, z=1.518 < 2σ)**. → **a n=400 top-up is the one larger eval worth
  running** (resumable from the cached 200 games; would push z to ~2.1 if the effect holds). Optional:
  it confirms an already-deployed, already-validated lever, so it is not decision-critical.
- **No other variant clears the gate.** Policy-only-leaf is covered by the residual pilot (it *is*
  resid 0). Dynamic-hybrid: gate not cleared (Q4). Hybrid fixed-K: already measured.

### 6. Which variants should be killed? (INTERPRETATION)
- **ITER8_POLICY_ROOT_ONLY** as a standalone ranker / candidate generator — root pick 0.259, far below
  search. Killed (use the policy only *inside* MCTS, as production already does).
- **HYBRID_PHASE_DYNAMIC / HYBRID_SHARPNESS_DYNAMIC** — no offline headroom (Q4); killed before any
  full-game spend.
- **ITER8_NO_RESIDUAL as a distinct variant** — it is provably identical to ITER8_POLICY_ONLY_LEAF_V27;
  not a separate thing to carry. And per Q3 it is **not worth adopting** (resid 0 *loses* the full-game
  pilot, +35 elo to resid 0.25) — so "drop the residual" is rejected; the production residual_scale=0.25
  stays (no champion change either way — out of scope).

### 7. Next engineering branch (INTERPRETATION)
Ranked:
1. **Stronger heuristic leaf (v2.8)** — the v2.7 leaf is the demonstrated ceiling: it explains the
   deep teacher (τ+0.61), it is what iter8 distills, and *no mixing of the existing components beats
   it* (this audit). Raising the leaf raises both heuristic search AND iter8's leaf simultaneously —
   the one lever that moves the shared cap. **Top recommendation.**
2. **External / human anchor** — the measurement blocker (CLAUDE.md): every ruler here is the
   self-/heuristic-referenced v2.7 family; superhuman cannot be confirmed without an out-of-family
   reference. Orthogonal but necessary.
3. **Search/policy weighting (c_puct / prior temperature) tuning** — cheap, but low ceiling: the root
   audit shows the deficit is search-depth/leaf, not prior weighting.
4. **Dynamic hybrid — DO NOT pursue** (Q4): no headroom, duplicates fixed-K.
5. **Residual/value head as a strength lever — DE-PRIORITIZE** (Q3): iter8 is policy-primary.

## Decision gates applied (from the brief)
**Proceed to larger eval only if** pilot positive/diagnostic, not seat/deck noise, simple
explanation, acceptable cost, not duplicating a stronger baseline → **only the residual pilot
qualified**, and its n=200 verdict came back borderline (+35 elo, z=1.518) → **a n=400 top-up is the
recommended (optional) follow-up**.
**Stop a variant if** it ties/loses at root+pilot, is dominated by heur@800/3200 at comparable cost,
needs complex new code with no pilot signal, improves imitation but not full-game, or works only in a
narrow band → **dynamic-hybrid and policy-only-ranker stopped**; **per-move-emulator framing of iter8
stopped** (heur dominates it).

## Hard-constraint compliance
No training · no flywheel · no champion change · no promotion · no production routing integration ·
every number cites an artifact · same-band paired where possible · full-game Elo / root agreement /
teacher imitation kept separate · clairvoyant vs fair-info kept separate · interpretations marked ·
small pilot run + cost reported before any scaled eval.
