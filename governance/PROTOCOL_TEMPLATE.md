# Pre-registered Experiment Protocol — TEMPLATE (blank)

> **Fill and commit this BEFORE running the experiment.** Store separately from results so the hypothesis cannot be rewritten after the outcome is known. One filled protocol per material experiment.

**Layer:** DECISIONS-support / INTERPRETATION (see [governance/README.md](README.md)). A filled protocol pre-commits the hypothesis and the decision rules so the `RESULT` section can only be filled in, never the hypothesis edited. Copy this file to `governance/protocols/PROTOCOL_<NNN>_<slug>.md` and fill every field. See `protocols/PROTOCOL_001_residual_marginal_topup.md` for a worked example.

---

## experiment_id
`PROTOCOL_<NNN>` / `<slug>`

## decision
<!-- The concrete decision this experiment exists to make, and the CLAIM_REGISTRY claim_id(s) it resolves. -->

## primary hypothesis
<!-- One falsifiable statement. State the effect size and the significance bar you expect. -->

## competing hypotheses
<!-- The null and any alternative(s) the experiment must be able to distinguish (e.g. H0 = null/noise; H-small = real but below the production-relevant threshold). -->

## single variable changed
<!-- The ONE thing that varies between conditions. If the run answers more than one question, list each variable and the cells it defines. -->

## held fixed
<!-- Everything else: checkpoint(s), sims, deck set / seed namespace, env knobs (CAP, DROP_THREE_OPEN, ...), opponent leaf, seating. -->

## primary metric
<!-- The single number the verdict is read off (e.g. deck-paired Δ winrate → elo ± σ, with z). -->

## secondary metrics
<!-- Supporting numbers, not used for the go/no-go verdict. -->

## sample size
<!-- Games per cell, paired/unpaired, and the expected z at the hypothesized effect size. Justify against the σ_elo ≈ 695·√(0.25/n) thresholds. -->

## pairing / seed design
<!-- Deck-pairing? Same seed both seats? Seed namespace (must be ≥1e9 clean floor)? Deck hashes recorded? -->

## top-up rule
<!-- PRE-REGISTERED. State exactly when (if ever) n is extended, by how much, and that it is a one-shot escalation — no repeated peek-and-extend. -->

## stopping rule
<!-- Fixed n, no optional stopping. Summarize only at the target n. -->

## success threshold
<!-- The exact metric value that makes the primary hypothesis Supported/Confirmed, and the registry status transition it triggers. -->

## failure threshold
<!-- The exact metric value that makes the hypothesis Disfavored/Inconclusive, and the registry status transition it triggers. -->

## what each outcome PERMITS
<!-- For each possible outcome (success / null / in-between): what follow-on action or claim it licenses. -->

## what each outcome FORBIDS
<!-- For each possible outcome: what it explicitly does NOT license. Be concrete — this is the guard against over-claiming (e.g. a Supported marginal still FORBIDS auto-fold-in without an out-of-lineage check). -->

## estimated compute cost
<!-- Games, boxes, wall-clock, train-or-eval-only. -->

## links to manifests / raw outputs
<!-- Run dirs, analysis scripts, launcher + commit hash, manifest paths. Raw outputs are append-only RAW-layer evidence. -->

---

## RESULT
<!-- Leave blank until the run completes. Fill ONLY this section; never edit the hypothesis/thresholds above after launch. Record: per-cell numbers, the primary metric with z, which threshold was met, the resulting registry status transition, and links to the final summaries. -->

_(to be filled at completion)_
