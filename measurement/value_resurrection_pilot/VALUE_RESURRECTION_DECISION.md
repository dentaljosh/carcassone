# Value Resurrection Pilot — DECISION

> **STATUS: CONCLUDED 2026-06-28 — DECISION B (target exists; learned value cannot beat the v2.9 leaf
> offline).** The value head stays **inert**. No new value/search flywheel is justified. MEASUREMENT
> ONLY — no promotion, no PRODUCTION.yaml change, no checkpoint promoted, no policy trained, no cluster
> spend (the whole pilot ran on local CPU + one GPU). Branch `rod_v2_flywheel`.

The narrow question: **can a learned value/ranking component beat the v2.9 leaf on held-out sibling
child-state ordering?** Answer: **No.**

## The seven questions

1. **Did the v2.9 leaf leave meaningful learnable sibling-ranking signal?**
   *Yes, a thin tail.* The v2.9 leaf ranks siblings at **τ = 0.895 / top1 0.455** vs h6400 over 10,067
   sets, but mis-ranks a real decisive minority: ~2,083 sets with regret ≥ 0.02, **~1,197 "decisive"**
   (teacher gap ≥ 0.02 *and* leaf regret ≥ 0.02). A target exists (**not Decision A**). The headroom is
   concentrated in **opening/midgame high-gap misses** — the **endgame is the leaf's *strongest* phase**
   (τ 0.94), so the Decision-F slice has the least to offer.

2. **Could a learned value/ranking model beat the v2.9 leaf offline?**
   **No.** Combined ranker `leaf + α·learned` on 637 held-out groups: **every variant's best α = 0**
   (give the net zero weight); regret rises monotonically with α; **0.0% reduction**. net-alone
   Kendall-τ peaked at **+0.105** (V4) vs the leaf's **0.895** — barely above CL-021's +0.029 against
   the weaker v2.7 leaf.

3. **Which target worked best?** *None.* Ranked least-bad → worst: listwise (τ 0.105) > advantage
   (0.083) ≫ **residual-regression (0.005)**. The natural "learn where the leaf is wrong" framing (V1)
   is the **worst** — the leaf's residual (0.5% of the Q signal; `leaf~oracle corr = 0.995`) is
   unlearnable by this architecture. (V1r/V5 cut short; would only confirm.)

4. **Did learned value improve NMCTS search?** *Not tested — gated out.* No variant cleared Stage 5, so
   Stage 6 was not run (and b99c9ed already showed the residual inert in NMCTS).

5. **Did root/search improvement convert to games?** *Not tested — gated out (Stage 7 not run).*

6. **Is the value head still inert?** **Yes.** A learned per-position value scalar cannot out-rank the
   structural v2.9 leaf — confirmed now on the v2.9 leaf + h6400 teacher + sibling framing, the cleanest
   setup yet. Reinforces b99c9ed Decision D (residual inert in search) and CL-021 (learned ranking
   disfavored, not probe-limited, scale-robust).

7. **Is a new value/search flywheel justified?** **No.** The binding learned component (a value head
   that beats the leaf) does not exist on this architecture. A flywheel built on it would compound the
   leaf's strength, not exceed it.

## Decision: **B** — target exists, net cannot learn it

Of A–F, the evidence lands squarely on **B**:
- **Not A** — the leaf does *not* match the teacher perfectly (~1,197 decisive misses).
- **B** — three formulations (listwise, advantage, residual) all fail to beat the leaf offline; optimal
  weight on the learned term is **zero**; the residual is unlearnable (τ≈0). Architecture/features would
  have to change for any hope; "more data" is closed (the production net on millions also ranks ~0.08).
- **Not C/D/E** — never reached (no offline win to integrate or play).
- **Not F** — the endgame is the leaf's *best* phase and the α-sweep is worse there too; an
  endgame-only learned value is *not* indicated (consistent with exact-endgame being outcome-neutral).

## Side finding (flagged, not actioned) — a POV sign bug in the b99c9ed autopsy

This engine's **TILES-phase action does not flip `current_player`** (place tile → meeple phase, same
player; verified 1816/1816 children). So `forced_move.py`'s `L0 = -tanh(vs2(child, child.current_player)/15)`
("negate for opponent-to-move") is **sign-inverted** for these same-player roots. Evaluating from the
fixed root seat flips the leaf↔teacher correlation from **−0.90 to +0.90**. This implies b99c9ed's I6
"static leaf is value-blind ~91% in the endgame" was likely **inverted** — the v2.9 leaf probably ranks
the teacher's child *correctly* far more often than I6 reported. That would **strengthen** Decision D /
this Decision B (the leaf is an even better ranker than the autopsy credited), not weaken it. Worth a
quick correction pass on `measurement/value_search_autopsy` (own ticket); it does not change any
production state.

## What this means / recommended next direction (for review — NOT actioned)

- **Learned value on this architecture is closed** as a route to beat the v2.9 leaf. Three independent
  experiments now agree: CL-021 (offline ranking), b99c9ed Decision D (residual in search), and this
  pilot (v2.9 + h6400 + sibling framing). **Do not** open a value-head retrain / value-flywheel on this
  net; do not promote anything.
- **The only honest paths to superhuman remain the two structural blockers** (CLAUDE.md): a
  **non-saturated external/human reference** (the measurement blocker), and a **learned component that
  exceeds the heuristic** — which would need an **architecture/representation change** (the value scalar
  is the wrong object for sibling discrimination), not another training recipe on the 6×96 ResNet.
- The strongest cheap agent remains bare HeuristicMCTS on the v2.9 leaf at higher sims.

**Answer delivered; stopping for review per governance.**
