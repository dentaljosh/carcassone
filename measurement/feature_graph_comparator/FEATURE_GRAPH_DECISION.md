# Feature-Graph Action Comparator Pilot — DECISION

**Verdict: Decision C — offline comparator works, search cannot use it.**
**Concluded 2026-06-28 · branch `rod_v2_flywheel` · no games run, no cluster used, no production change.**

The pilot answered its scientific question and then failed the search gate cleanly. Below: the 8
spec questions, the label, and the conclusion to preserve.

## The 8 questions

1. **Could we extract a useful feature/action schema cheaply?** **YES.** A 50-scalar action-feature/
   delta vector (`decompose` + `decompose_v29`, no engine change) built over all 10,067 roots in
   ~11 min, 0 errors. Enumeration bit-identical to the value-resurrection reference (audit reproduced
   τ=0.8951 / top1=0.4553 / 1197 decisive exactly; leaf_q bit-exact). *Decision-A not triggered.*
2. **Did simple feature/action models beat old neural value?** **YES (transitively).** The v2.9 leaf
   already beats the old scalar value head (inert per `b99c9ed`); the feature/action models beat the
   leaf offline. A *linear* model over the feature vector suffices — representation, not capacity.
3. **Did any model beat v2.9 leaf offline?** **YES, decisively.** Held-out sibling regret: full-pool
   −41% (0.0289→0.0171), top1 0.464→0.535, ordinary subset also improved (no regression); decisive
   tail −44% (linear) to −52% (listwise). Survives leak scan (no label in `feat`) and negative
   controls (shuffled-label refits collapse below the leaf). Reverses the Value Resurrection α=0.
4. **Was improvement only in the decisive tail or full pool?** **Full pool**, concentrated in the
   decisive tail, and **driven by representation, not reweighting**: Tier-1 (the leaf's own
   components, reweighted) only −13% on the tail; Tier-2 explicit structure (contested control,
   open-edge exposure, meeple lockup/return, completed value, move semantics) drives the rest.
5. **Did search use the comparator?** **NO.** Four narrow integration modes (small-α leaf-value
   blend, top-k restriction, decisive-tail gating, post-search rerank) over 596 held-out roots at
   HeuristicMCTS(sims=200): **no setting beats `search_leaf` on decisive-tail regret, and every α>0
   setting regresses ordinary play.** Best α>0 blend decisive regret 0.01954 vs search_leaf 0.01946
   (+0.4% worse); gated no better. Sanity asserts all pass.
6. **Did games improve?** **N/A — not run.** Gated out by the Stage-5 failure (correctly; no cluster
   spend incurred).
7. **Is a new learned architecture path justified?** **No, not on this evidence.** A heavier model
   (graph net) is not warranted: the bottleneck is **redundancy with search**, not model capacity.
   The structural signal the comparator learned is the *same* signal MCTS recovers by visiting and
   re-scoring siblings — capacity won't change that.
8. **Is a resurrected flywheel plausible only with feature/action representation?** **No flywheel
   justified.** The representation answers the open scientific question, but the signal does not
   survive search at play depth, so it cannot drive a strength flywheel.

## Why search washes it out (the mechanism, in one paragraph)

The static v2.9 leaf misranks the decisive tail (regret 0.122). But HeuristicMCTS(200) backs up
values through that same leaf across all siblings — and at sims=200 it **explores every legal child**
(`teacher_explored_frac = 1.0`), collapsing decisive-tail regret ~6× to 0.019 (decisive top1 →0.79)
*on its own*. The offline comparator (decisive regret 0.075) is **behind** search, not ahead. The
"room" the comparator filled offline — re-ranking siblings the static leaf got wrong — is exactly the
room search already fills by visiting them. What little is left (41 explored-but-misranked decisive
roots) the learned residual fixes only 3/41 of, breaking as many as it fixes → net ordinary
regression. The offline sibling-ranking metric was a **screen**, and the screened win does not
convert through search. This is the `b99c9ed` pattern in clean, pre-registered form.

## The conclusion to preserve (do not overstate)

This is **not** "flywheel resurrected." The durable findings are two:

1. **Explicit feature/action representation beats the v2.9 leaf OFFLINE (representation, not
   reweighting).** This answers the question the prior pilots left open: the scalar value head was
   dead for **lack of explicit Carcassonne feature/action structure**, *not* because learned value is
   hopeless. A cheap linear model over the right features clears the static leaf.
2. **…but that offline win is redundant with search.** To matter for **strength**, a learned
   component must beat what *search already extracts*, not what the *static leaf* gets wrong. The
   structural signal here is precisely what search recovers for free at play sims. This sharpens the
   project's standing blocker (CLAUDE.md): superhuman needs the learned components to exceed the
   heuristic **after search** — better static sibling ranking is not that lever.

## Recommendation

**Stop.** Do not promote, do not run games, do not escalate to a graph architecture, do not start a
flywheel. v2.9 / `PRODUCTION.yaml` unchanged.

One non-recommended, BACKLOG-only angle (logged, not pursued): the washout is sims-dependent —
search explored all children at sims=200, so the comparator's only conceivable use is **search
*efficiency*** (better priors/move-ordering to reach the same quality at fewer sims), a
compute-efficiency play, **not** a strength play. Not worth opening absent a separate efficiency goal.

## Artifacts

`FEATURE_GRAPH_{PLAN,SCHEMA,DATASET,BASELINES,TRAINING,OFFLINE_RESULTS,SEARCH_RESULTS}.md` ·
`data/rows_feat.npz` (gitignored) · `offline_results.json` · `search_results.json` ·
`scripts/feature_graph/{build_feat_dataset,validate_dataset,eval_lib,run_offline,check_leak,search_screen}.py`.
