# STAGE 0 — IS THE PUCT-PRIORS AGENT A LABEL SOURCE ABOVE THE LEAF? — PRE-REGISTRATION

**Status: PRE-REGISTERED 2026-07-07 (before any number). Runs AFTER the round-robin frees the boxes.**
**Provenance:** Fable premise-expiration audit #1 (2026-07-07): the 2026-06-24 "distillation from classical is EV-LOW" kill was justified by *near-uniform heuristic visit distributions* — a symptom of the random-expansion search falsified on 2026-07-06 (+148.2, z10.17). Every value-route kill (M2/CL-039/CL-042) is scope-guarded to sims≤200 self-taught data; a 2750-sim PUCT-priors teacher is outside all kill scopes. This is a NEW-premise re-open, not a re-proposal.

## ✅ VERDICT (2026-07-07): KILL-CONFIRM (value branch) — per the pre-registered τ gate. Fable-reviewed.
n=1119, `teacher_tau/stage0_sims2750.json`. **The value-label route stays CLOSED.**
- **Pre-registered read (τ):** puct_q τ=**0.567** (dτ vs leaf z=**−3.49**), puct_visits τ=**0.578** (z=−2.86), both **below** leaf 0.615 by >2σ → **KILL-CONFIRM**. The plan even anticipated the mechanism ("Q-averaging dilution"). A **5th independent confirmation the v2.9 leaf is a freakishly good global sibling-ranker** (M2 τ=0.02, CL-034 comparator τ-collapse, M3 max-op-hunts-the-tail, now search-Q-with-terminal-access τ<leaf). τ is the *right* gate for the value question because the MCTS max-operator hunts the value's optimistic tail (CL-042/M3) — tail-ranking quality is exactly what a search-driving value needs.
- **FINDING (recorded, NOT a gate override):** the regret/top_share divergence (puct_q regret 0.198 vs leaf 0.951, sign-z +12.6; puct_visits top1 0.629 > leaf 0.610; top_share mean 0.31) does **NOT** reopen a policy route, per Fable review: **all 1,119 roots are K=2 (the last two tiles)** — a 2750-sim search reaches *terminal states*, so its low regret is quasi-exact **endgame reading, not policy quality** (CL-034 already measured the same 6× regret collapse), and production **hands these roots to the exact solver anyway**. The top_share "refutation" is confounded: the 2026-06-24 kill's 0.05–0.08 was *multi-phase*, this 0.31 is *endgame-only* (p10=0.038), and **rod1's own multi-phase top_share was already 0.27** — a rich-visit policy existed all along and never beat the leaf. Target richness was never the missing ingredient; CL-031 distilled sharp (temp-0.03) targets and washed out anyway. Counting note (Fable): 271 better / 47 worse / 801 tie = **1,119** (regret, all roots); the 937 is τ-pairable (1,119 − 182 leaf-τ-NaN).
- **BLOCKER #2 read:** a stronger classical *policy* generates *worse* value labels than the leaf → **orthogonal to the value route**; it does not feed blocker #2. What remains open there is scale/architecture (10–100×), not better 7M teachers (CL-039 scope guard).

## NEXT (Fable path; Joshua 🟢 2026-07-07) — the ONE unsampled cell, gated on free diagnostics
The single genuinely-new question: a distilled **net-prior inside the NEW classical PUCT**, competing against **leaf-priors**, judged **in games** (the +148 proved priors matter enormously in the new search; net-prior-vs-leaf-prior at equal wall-clock is unsampled). Three prior washouts (CL-031/CL-032/sims-washout) predict it fails; the bar is now leaf-priors (cheap, CPU-only, champion), not flat.
- **Diagnostic (a):** leaf-prior-argmax vs teacher-final-move **disagreement rate on a MIDGAME slice** — the distillable delta is bounded by it. **Step 1 funded ONLY if ≥20% real (non-noise) midgame disagreement.**
- **Diagnostic (b):** top-m-visited τ (does search-Q beat the leaf even in its most charitable value reading — restricting τ to the children search actually explored).
- **Step 1 (conditional, ~1 box-day):** ~10–20K PUCT@2750 roots → policy-only net on visit-dist targets → judged **exclusively** by n=400 paired **games**, PUCT-with-net-prior vs PUCT-with-leaf-prior at equal wall-clock (hardware asymmetry in the manifest — net side pays GPU/forward latency). Pre-register against **CL-031's registered falsifier**, not as a Stage-0 reinterpretation. Offline-judged Stage 1 = worth zero.

## Question
Does the PUCT-priors@2750 agent's **root-Q ranking** beat the static v2.9 leaf's ranking against exact ground truth? (= is it the first label source ABOVE the heuristic — the missing ingredient of structural blocker #2.)

## Design
- **Ruler:** the existing 1,119 K≤2 marginalized exact-solver roots (the F4 non-circular ruler; solve-once-score-many — solves are cached, no new solver cost).
- **Measure:** Kendall-τ of the agent's root child ranking (by search-Q after 2750 sims, c1.5/τ5/float — the confirmed config) vs the exact solver's child values, same protocol as the M2 value-head scoring.
- **Baselines (already on file):** v2.9 leaf τ = 0.615; M2 value heads τ = 0.018–0.023.
- **Also record (secondary, no gate):** visit-distribution top-share (the 2026-06-24 kill cited h12800 top_share 0.05–0.08 — quantify how peaked the PUCT teacher is by contrast), and root-Q vs visit-count ranking agreement.

## Pre-registered read-out (single read)
- **REOPEN (teacher-τ > 0.615 + 2σ_τ):** a label source above the leaf exists → Stage 1 becomes the pre-registered follow-up: ~10–20K roots of PUCT@2750 self-play, train the existing 7M arch (existing recipe) on search-Q value + visit-dist policy targets; judged by solver-τ vs the 0.02 M2 baseline and the 0.615 leaf on the SAME ruler. Surface cost before launching Stage 1.
- **HOLD (τ within ±2σ of 0.615):** teacher ranks ≈ the leaf it searches with — distillation gains would be policy-only; Stage 1 downgraded, surface before any spend.
- **KILL-CONFIRM (τ < 0.615 − 2σ):** search-Q at 2750 is a *worse* ranker than the raw leaf (plausible via Q-averaging dilution) — the 2026-06-24 EV-LOW verdict survives on the new premise; write the confirmation and close.
- σ_τ from the same bootstrap-over-roots used in the M2 read.

## Cost / ops
~1,119 roots × one 2750-sim search ≈ 1 box-hour at moderate W (CPU-only, net-free). Runs after RR-4. Requires a small adapter (search-agent → per-root child ranking in solver_score's format) — build + tests tonight, measurement gated on a green adapter test + boxes free.
