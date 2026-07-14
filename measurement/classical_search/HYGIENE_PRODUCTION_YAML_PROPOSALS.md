# PRODUCTION.yaml hygiene proposals — PROPOSE, DO NOT APPLY (needs Joshua)

**Date:** 2026-07-14 · **Status:** PROPOSED (unapplied) · **Source:** BACKLOG re-audit T4 (items a + b).

Standing rule: `governance/PRODUCTION.yaml` is never touched without Joshua's explicit
approval. He is away. Both items below are behavior-neutral config hygiene (the champion
plays identically either way — the meeple_k key is proven INERT and the endgame line is
documentation), so there is no urgency; they are staged here for the next approved
governance touch. Neither has been applied.

---

## (a) Phase-0.1 wording fix — the `endgame:` line conflates two configs

The fair-handoff audit (`measurement/fair_handoff_audit/REPORT.md`, 2026-07-06) proved
that the "K<=4 alpha-beta" wording can only describe the CLAIRVOYANT reference/eval agent,
never the FAIR deployable path: alpha-beta is clairvoyant-only (chance nodes break minimax
cutoffs) and the fair agent caps at **K<=2 marginalized** expectiminimax. One champion,
two handoffs; the current line names only the clairvoyant one under a generic label.

**Current (PRODUCTION.yaml line 72):**
```yaml
  endgame: "exact K<=4 alpha-beta solver handoff (scripts/level2/endgame_solver.py) — UNCHANGED; identical both sides so it does not affect the search-A/B margin"
```

**Proposed replacement** (adapted from REPORT.md §"Proposed PRODUCTION.yaml wording fix";
distinguishes the two configs the single champion actually runs, and keeps the existing
"identical both sides / does not affect the search-A/B margin" note that post-dates the
audit's draft):
```yaml
  endgame: >
    Two handoffs share this champion. (a) CLAIRVOYANT reference/eval agent — what the
    champion's strength numbers were measured with: exact K<=4 clairvoyant alpha-beta solver
    (scripts/level2/endgame_solver.py, mode=clairvoyant), margin-correct; UNCHANGED and
    identical both sides, so it does not affect the search-A/B margin. (b) FAIR deployable
    agent for human-facing play (src/carcassonne_ai/fair_agent.py): exact K<=2 MARGINALIZED
    expectiminimax handoff (mode=marginalized, no alpha-beta). Alpha-beta and K=3-4 are
    clairvoyant-only (they read the true deck order) so the fair agent caps at K<=2 marginalized.
    Audited 2026-07-06 (measurement/fair_handoff_audit/REPORT.md): 0 clairvoyant/alpha-beta
    solves in 20 fair games; the marginalized solve is bit-invariant to deck permutation.
```

Rationale: documentation-only; removes the one place the clairvoyant reference config and
the fair deployable config are conflated. No claim in `CLAIM_REGISTRY.csv` is contradicted
(the audit upgrades the K<=2-marginalized fact from prose to runtime-verified). No champion
behavior change.

---

## (b) Remove the INERT `meeple_k: 2.0` key — config-hygiene trap

The C5 leaf-retune design pass (roadmap 2026-07-13; `C5_LEAF_RETUNE_DESIGN.md`) found that
`meeple_k` is dead once the meeple **curve** is non-null: the flat `meeple_k` term is
replaced by the curve (`flat_leaf.py`: `if curve is not None`). The champion leaf
(`v2_9_2_Bmild_cap8_curve125`) sets `v29_meeple_curve`, so `meeple_k: 2.0` is read but never
used. Leaving a load-bearing-looking value that is silently ignored is a config-hygiene trap
(a future tuner could "sweep meeple_k" and measure pure noise).

**Current (PRODUCTION.yaml lines 68-69):**
```yaml
    meeple_k: 2.0                       # INERT — the curve (non-null) REPLACES the flat meeple_k term
                                        # (flat_leaf.py:838, `if curve is not None`). Kept for record; not load-bearing.
```

**Proposed:** delete both lines (the key + its comment).

Rationale: INERT key removal; the value does not enter the leaf while a curve is set, so
deleting it cannot change champion play. If preferred over deletion, an alternative is to
leave it with the existing INERT comment (status quo) — but the audit's recommendation is
removal to eliminate the trap. Flagged for Joshua to choose delete-vs-keep.

---

*Neither change applied. Apply only on Joshua's explicit approval, folded into the next
governance touch (results.csv / DECISIONS / CLAIM_REGISTRY close-out per the CLAUDE.md
six-touch rule).*
