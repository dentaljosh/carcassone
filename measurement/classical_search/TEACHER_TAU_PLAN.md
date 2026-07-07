# STAGE 0 — IS THE PUCT-PRIORS AGENT A LABEL SOURCE ABOVE THE LEAF? — PRE-REGISTRATION

**Status: PRE-REGISTERED 2026-07-07 (before any number). Runs AFTER the round-robin frees the boxes.**
**Provenance:** Fable premise-expiration audit #1 (2026-07-07): the 2026-06-24 "distillation from classical is EV-LOW" kill was justified by *near-uniform heuristic visit distributions* — a symptom of the random-expansion search falsified on 2026-07-06 (+148.2, z10.17). Every value-route kill (M2/CL-039/CL-042) is scope-guarded to sims≤200 self-taught data; a 2750-sim PUCT-priors teacher is outside all kill scopes. This is a NEW-premise re-open, not a re-proposal.

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
