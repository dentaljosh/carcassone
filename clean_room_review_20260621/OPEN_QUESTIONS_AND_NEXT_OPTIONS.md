# Open Questions & Next Options

The live questions and the candidate branches. The team's current standing program is
**measurement-first** ([sources/MEASUREMENT_FIRST_SPEC_2026-06-18.md](sources/MEASUREMENT_FIRST_SPEC_2026-06-18.md)):
both strength levers (policy iteration via deepteacher; learned value head) are exhausted, so the
binding constraint is a reference that is neither clairvoyant-inflated, nor saturated, nor
in-ecosystem. The options below are framed against that constraint.

---

## A. Pre-tool audit / tool-augmented action ranker (the immediately proposed branch)

**The proposal (PROP-1):** give the agent richer hand-built move/endgame features and/or a learned
**action-ranker** head, on the theory that it could add the sharp/OOD endgame precision iter8 lacks
(CL-025/027) and possibly exceed the v2.7 ceiling.

**Why it is proposed.** The endgame suites show a *specific, real, locally-patchable* weakness:
iter8 is the worst endgame technician (K=2 0.667, K=3 0.574, K=4 0.561), it handles sharp/OOD
positions worst (K=4 sharp top-1 0.40), and a heuristic-endgame handoff demonstrably patches it
(CL-026). A ranker that learns endgame/sharp-position move ordering is the natural learned analogue
of that patch.

**What the pre-tool audit should measure BEFORE writing any features:**
1. **Is the weakness learnable at all by a ranker?** The value-head kill-test already says a learned
   *per-position value scalar* ranks siblings at ~chance (CL-021, τ≈0.03 vs v2.7 0.58). A pre-tool
   audit must show that the *action-ranker* formulation (pairwise/listwise over moves, possibly with
   tool features) is **not** the same dead end — e.g. by fitting the ranker to the **exact solver
   labels** (K=2/3/4 are available, non-circular) and showing held-out move-ranking τ materially
   above v2.7, especially on **sharp gap≥2** positions.
2. **Does any gain survive search depth?** Net/policy gains are known to **wash out under deep MCTS**
   (memory `feedback_sims_washout_net_eval`: a +82.8/z3.48 s200 effect became +8/z0.34 at s800). The
   audit must check that a ranker gain measured at low sims is still present at play depth — otherwise
   it is irrelevant to a deep-search agent.
3. **Feature-value attribution.** Which tool features (if any) carry signal vs the exact-solver
   labels, measured *before* integration, so the build targets only features that move move-ranking.

**Risks.**
- **Repeats the failed value-head lever.** CL-021 is a strong prior that learned per-position
  scoring underperforms the structural v2.7 leaf at sibling discrimination, *at any data scale*. A
  ranker is a different loss/architecture but the same underlying ask.
- **Washout.** A ranker that helps at the leaf may add nothing once MCTS runs deep.
- **Goalpost drift.** "Tool features" can quietly become classical-engine feature engineering that
  improves the heuristic, not the *learned* agent — which does not advance the AlphaZero goal (see B).
- **Measurement still missing.** Even a successful ranker is measured on the same clairvoyant,
  in-ecosystem, heuristic-capped ruler; it cannot by itself support a superhuman claim (see D).

**Decision rule for continuing (proposed):** proceed to feature/tool *coding* only if the pre-tool
audit shows **(i)** a ranker fit to exact-solver labels beats v2.7 on held-out move-ranking on
**sharp/OOD** endgame positions by a margin that **(ii)** survives at play-depth sims. If either
fails, the branch is the value-head dead end again — stop and bank.

---

## B. Heuristic improvement v2.7 → v2.8

**Why it may help.** Depth scales the heuristic ruler with real headroom (CL-023: +76→+55→+35 per
doubling through @3200, not saturated at @1600). A better leaf (v2.8) could (a) raise the ruler the
learned agent must clear, and (b) since iter8 *distills* the leaf, a better leaf could lift the whole
learned lineage.

**Why it is classical-engine development, not automatically AlphaZero progress.** Improving the
hand-crafted leaf makes the *heuristic* stronger. The project goal is **learned** components that
*exceed* the heuristic. A v2.8 that beats v2.7 raises the bar but does not demonstrate learned
supremacy; it can even *widen* the gap the learned agent must close.

**How to keep it from moving goalposts.** Treat v2.8 explicitly as a **ruler upgrade**, not a strength
win: (1) version it as a new ladder rung and re-anchor, don't silently swap the production leaf; (2)
keep the superhuman claim gated on **learned − heuristic > 0**, measured against whichever leaf is
current; (3) log it in the ladder/claim registry as engine work, separate from any learned-agent
claim.

---

## C. Solver path (exact endgame labels / measurement infrastructure)

The exact solver is the program's **only non-circular ground truth** and is the cleanest source of
labels for any ranker audit (A). Open extensions:
- **K=4 expansion** — done at 200 balanced positions (CL-027); larger n or 2nd band would tighten the
  by-source / sharpness reads.
- **Marginalized (bag-expectation) K=4 labels** — the **preferred** fair-information ground truth
  (current K=4 labels are clairvoyant only). Alpha-beta does **not** apply (chance nodes break
  cutoffs) → needs the speedup below.
- **K=5 feasibility** — small probe, only after K=4; the memory wall is worse.
- **make/unmake / Rust** — the engine's per-node deepcopy in `get_next_state` is the binding
  constraint (solver monsters reach ~10.6 GB from *transient* deepcopy churn, not the TT). make/unmake
  (incremental apply/undo, ~3–5× speedup, reuses the trusted engine) is the prerequisite for
  marginalized labels and K=5; Rust was scoped (~1–1.5k LOC + a bit-exact gauntlet) and deferred.

**Why this is measurement / label infrastructure, not immediate strength.** None of these make any
agent play better. They (a) deepen the endgame-optimality evidence and (b) provide non-circular labels
to *audit* a ranker. Value is as the **eye**, not the **engine** (MEASUREMENT_FIRST_SPEC §6, Level 3).

---

## D. Human / external benchmark

**Why it is needed for any superhuman claim.** Every elo in this packet is **clairvoyant and
in-ecosystem** (v2.7-leaf family). Clairvoyance is bounded small (CL-022), but the ruler is still
heuristic-capped and self-referential. "Beats strong/expert humans" is **literally unmeasurable**
without a human/expert anchor (MEASUREMENT_FIRST_SPEC §6 / Level 3: online-platform logs,
expert-annotated positions, or recruited experts). This is the long pole — *weeks of data
acquisition*, not compute — and it gates the *claim*, not the engineering. No tool/ranker/leaf work
can substitute for it.

---

## E. Stop / bank option — what is already achieved

If work stops here, the **banked, defensible** results are:
1. A **provenance-clean, runtime-verified measurement apparatus** (R1/R7 guards, deck-hashed,
   seed-floored, orch-path bit-identical to historical) — CL-013/014/015/024.
2. A **production champion (iter8)** that is a **real, significant** strength gain over its incumbent
   (+67.4/z2.73 on a sealed out-of-lineage ruler), with the gain honestly characterized as **bounded
   policy distillation** (CL-005/011/018).
3. A **clean powered-null** closing the deeper-teacher lever (CL-019) and a **kill-test** closing the
   learned-value-head lever (CL-021) — two negative results that save future spend.
4. The **clairvoyance question settled** (small, ~25–30 elo; clairvoyant numbers ≈ transfer) — CL-022.
5. A **validated, non-saturated heuristic ladder** placing iter8 precisely: beats heur up to ~@1600,
   caught at @3200 (CL-023/024).
6. The **first non-circular ground truth** in the program (exact endgame solver, K=2→K=4), a
   reproducible characterization of iter8 as a strong-early/weak-endgame agent, and a **locally
   patchable** hybrid (CL-025/026/027).

What is **not** achieved and would remain open: any **absolute / human-anchored** strength number, any
**supra-heuristic learned component**, and therefore any **superhuman** claim.

---

## The single highest-information next measurement (recommendation to the reviewer)
Before any tool/feature coding, run the **pre-tool audit (A)**: fit the candidate action-ranker to the
**exact-solver labels** that already exist (K=2/3/4) and check held-out move-ranking on **sharp/OOD**
positions, **and** whether any gain survives at play-depth sims. It is cheap (labels exist), it
directly tests PROP-1's load-bearing assumption, and — like the clairvoyance gap and the value-head
kill-test before it — it is decisive in either direction.
