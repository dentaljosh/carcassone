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

---

## External review (2026-07-07) — Stage-0 classified YELLOW; the owed narrow Stage-1

**Status: FOLDED 2026-07-07. Does NOT change the VERDICT above — the VALUE-label route stays KILL-CONFIRM (puct_q τ 0.567 / puct_visits τ 0.578, both < leaf 0.615 by >2σ). This records the POLICY-route correction that three parties (Joshua + Fable + an external reviewer) independently flagged: Stage-0 closed the value route but is owed a narrow, pre-registered policy Stage-1 — deferred behind max-search-first, not dead.**

An external reviewer read the Stage-0 result and the +148 PUCT breakthrough and asked "how does this fit our strategy." Faithful capture of what the review said and how it maps onto our roadmap.

### Overall verdict: YELLOW (not a Green value-reopen, not a Red kill)

The reviewer built its own three-bucket decision rule; by that rule Stage-0 lands **Yellow** — the full-ranking τ does NOT beat the leaf (= our KILL-CONFIRM), but the top-1 regret *does* improve, so by the reviewer's rule the teacher is "not dead" and is owed a **narrower Stage-1 policy-prior test**. The Yellow is about the **policy route**, explicitly NOT a reopening of the value KILL: *"I would not use 'teacher tau <= leaf' alone as a total kill, because full-ranking tau and move-choice regret can diverge. A PUCT teacher may be worse at ordering irrelevant siblings but better at selecting the decisive top move."*

The reviewer stressed this is NOT "neural is back." The strongest claim it endorsed is only that *"the previous closure of policy distillation was likely mis-scoped because the teacher distribution was corrupted by random expansion"* — enough to reopen the branch, not evidence the student can fit the signal, that the signal survives off the solver root set, or that it improves fair games. Its named failure mode: *"doing six exciting follow-ups at once and losing causal attribution. Freeze PUCT@2750, run Stage 0, then branch."*

### The three-bucket rule (verbatim from the review)

- **Green** — PUCT@2750 beats the v2.9 leaf on τ with a paired CI excluding zero, **and** improves top-1 regret or high-gap pair accuracy → *"Stage 1 distillation is justified."*
- **Yellow** — PUCT@2750 does NOT beat leaf τ, but improves top-1 regret or high-gap pair accuracy → *"do not declare teacher dead. Run a narrower Stage 1 policy-prior test, because a search teacher may be useful at top-action selection even if full sibling ranking tau is lower."*
- **Red** — PUCT@2750 is at or below leaf on τ, top-1 regret, **and** high-gap pair accuracy → *"the distillation re-open mostly closes. PUCT is a stronger search agent, but not a better non-circular teacher on this ruler."*

Our Stage-0 read against this rule: full-ranking τ 0.567/0.578 < leaf 0.615 (fails Green's τ clause) BUT puct_q regret 0.198 « leaf 0.951 and puct_visits top1 0.629 > 0.610 (meets the regret/top-1 clause) ⇒ **Yellow by the reviewer's own rule** — not Green, not Red.

### The endgame-artifact caveat (why Yellow is NOT a clean policy reopen)

The reviewer did not have the K-composition of the root set. Fable did, and this is the load-bearing correction the VERDICT above already records: **all 1,119 Stage-0 roots are K=2 (the last two tiles)**, so a 2750-sim search reaches *terminal* states and its low regret is quasi-exact **endgame reading, not policy quality** (CL-034 already measured the same ~6× regret collapse); production hands these roots to the exact solver anyway. The top_share signal is separately **confounded** — the 2026-06-24 kill's top_share 0.05–0.08 was *multi-phase* whereas this 0.31 is *endgame-only* (p10=0.038), and **rod1's own multi-phase top_share was already ~0.27** (a rich-visit policy existed all along and never beat the leaf; target richness was never the missing ingredient). So the regret/top_share improvement that earns Yellow is largely a terminal-reading artifact — which is exactly why the reviewer's Yellow (a narrow test *owed*, not launched) and Fable's caveat converge on **"deferred, not dead," not "reopen now."**

### Adapter warnings (the review's strongest engineering caution — "the difference between a decisive Stage 0 and a misleading one")

- **Score every legal sibling, not only visited children.** *"A root-Q scorer can accidentally look amazing if it only scores actions the PUCT search chose to visit. The exact-solver ruler is a sibling-ranking test; every legal sibling needs a defined score."*
- **Prescribed adapter:** (1) enumerate all legal root actions; (2) force-create/evaluate every legal child once, OR assign a **pre-registered** fallback score to every unvisited legal action; (3) run the remaining PUCT budget; (4) export one score per legal action in solver-score format.
- **Cleanest primary score:** *"backed-up child mean Q after all-legal root initialization plus PUCT budget."*
- If all-legal init is too invasive, pre-register a fallback for unvisited children (afterstate leaf-Q, parent FPU, or minimum visited-Q) — *"but do not choose the fallback after seeing which one looks best."*
- **Freeze the breakthrough agent exactly** for the measurement: leaf version, PUCT formula, prior source, c_puct, FPU/default-Q, value_norm, root-noise OFF, temperature OFF, deterministic seed, sims=2750, fair/clair mode declared — *"a measurement of the teacher, not a robustness test."*

(Our `solver_score_agent.py` adapter, commit 76d524a, was sign-verified τ_Q +0.59/+0.71/+0.74 on known roots; the pre-registered read was gated on a green adapter test per "## Cost / ops" above — the adapter warning was satisfied.)

### Stage 1A / 1B / 1C, as the review laid it out

Owed only if Stage-0 is Green or Yellow, and — the reviewer's phrase — *"ruthlessly small and non-circular"*:

- **Stage 1A — policy-prior distillation:** train the net to predict PUCT **visit distributions** on a large root set. Use the new PUCT teacher (not random expansion); preserve the peakedness of the teacher distribution; pre-register any temperature targets; judge first on held-out PUCT labels AND exact-solver roots; *"do not claim success from teacher imitation alone"* — success requires the distilled prior improves exact-solver root decisions or fixed-budget search.
- **Stage 1B — action-ranking distillation:** train an action-conditioned ranker/value model on PUCT root-Q or pairwise preferences (*"may be more promising than a flat 2511 policy head"*). Suggested inputs: legal-action candidate encoding, afterstate score delta, component/farm/meeple/liquidity features, bag histogram, PUCT prior, **the v2.9 leaf as an input feature (not the target)**, optional CNN board trunk. *"The learned object should score candidate moves, not just emit a board scalar."*
- **Stage 1C — search integration:** use the student first as a **PUCT prior, not a leaf replacement** (*"a prior has a lower burden: it only needs to allocate search better"*). Pre-registered integration ladder: (1) prior only, leaf unchanged; (2) prior + small value/rank blend; (3) value-only ONLY after non-circular evidence says it beats the leaf.

### Mapping onto our roadmap — B1a (done) and B2 (deferred)

The reviewer's narrow Stage-1 is already our roadmap's B1a→B2 sequence (`docs/PROGRAM_ROADMAP_2026-07-07.md`), which pre-dates the review:

- **B1a — midgame disagreement diagnostic (DONE):** the reviewer's "policy signal even if τ is lower" is bounded by how often the teacher's chosen move differs from the leaf-prior's argmax OFF the terminal-reading K=2 roots. `midgame_disagreement.py` (commit 71c6ae8) measured it on a midgame slice (k∈[15,45]): 51% raw, **4.75% real** disagreement after the noise floor — « the 20%-headroom funding bar. This is the concrete, non-endgame answer to the reviewer's Yellow: the distillable delta is small.
- **B2 — the ONE unsampled cell (the reviewer's 1A run through 1C's rung 1):** a distilled **net-prior vs leaf-prior INSIDE the new PUCT**, ~10-20K PUCT@2750 roots → policy-only net on visit-dist targets → judged EXCLUSIVELY by **n=400 paired games** at equal wall-clock (net side pays GPU/forward latency; hardware asymmetry recorded in the manifest), **pre-registered against CL-031's registered falsifier** (not as a Stage-0 reinterpretation; offline-judged Stage-1 = worth zero). This is Stage 1A (policy-prior distillation) taken through Stage 1C's "prior only, leaf unchanged" rung — the lower-burden route the reviewer favored. Stage 1B (a separate action-conditioned ranker) is not on the current queue.

**Status of B2: DEFERRED behind the max-search-first campaign** per Joshua's strategic call (*"I still lean towards maxing out search first and then we can try messing with the net"*). Three prior washouts (CL-031, CL-032, sims-washout) predict it fails — the +82→+8 elo sims-washout in particular implies maxing search *shrinks* the prior's headroom rather than growing it. So B2 is worth **≤1 box-day only as a clean, pre-registered kill in the new PUCT regime** — a registered null that closes the last unsampled policy cell, not a hopeful bet.

### Net: the correction three parties independently flagged

Joshua, Fable, and the external reviewer converged on the same shape: **Stage-0 closed the VALUE route (τ KILL-CONFIRM, unchanged), but the POLICY route is owed a narrow, pre-registered Stage-1 (= B2) — which is deferred behind max-search-first, not dead.** The Yellow is a "don't lose this cell," not a "run it now."
