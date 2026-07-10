# A vs C — decision synthesis (2026-07-09/10, FINAL)

**TL;DR (FINAL — both bets RUN DOWN): A-small = ❌ DECLINE. C-cheap = ❌ DEAD (ran it: W0/L100 catastrophic, CL-049). k_dets tuning = no free win (peak at 8). Both post-B strength levers are weak — which is the measurement doing its job. The fair strength we HAVE is near the ceiling for this leaf (+81 vs h800 at deploy, +149 at 2× search, still scaling — "search deeper, fair" is the one demonstrated lever). → E4 (the fair human exam) is the real next question, and it needs Joshua (opponents/match setup; the fair ruler D0 + fair config A2 are built).**

**What C's death actually showed (the sharp finding):** the fair agent selects by **pooled-Q (value-driven)**, which needs a value that sharply ranks *sibling afterstates*. The v2.9 heuristic leaf IS that near-perfect *local* ranker; a learned value (even globally correct, corr +0.5) is a smooth *global* predictor with near-zero local discrimination (sibling std ~0.01 vs leaf ~0.04) → swapping it in makes move-selection ~random → loses every game. Deck-awareness never got tested; the base local ranking fails first. This is the value-inertness ledger, confirmed decisively. (Nuance: harshest test — full leaf REPLACEMENT + pooled-Q; a residual-blend value is untested/low-prior.)

**k_dets tuning (deploy + C-marginalization probe):** inverted-U, peak at **k_dets=8** (+81; 4=+70, 16=+49, 32=+9) → the deployed split is already optimal, and more PIMC sampling doesn't help (marginalization not under-provisioned).

---
## A-small (endgame alpha-beta) — DECLINE
Full spec: `A_SMALL_SPEC.md`. Verdict rests on 4 evidenced points:
1. **Alpha-beta is clairvoyant-only** — chance/deck nodes break minimax cutoffs (`endgame_solver.py:105` asserts it). The FAIR endgame is a K≤2 *marginalized expectiminimax*, no pruning. So "ID-alpha-beta+TT for bigger-K-in-the-same-time" is a clairvoyant fantasy fair, exactly like full-game alpha-beta.
2. **The endgame has no fair winrate headroom.** The clairvoyant K-series (an *upper bound* on fair value) is winrate-flat/NS through K=4 (0.526→0.537→0.568), with a standing STOP-at-K=4 decision. Margin scales with K; winning doesn't. Fair ≤ that ≈ 0.
3. **The ~120 tax is MIDGAME** (CL-048: persists across 7× sims, doesn't close with search) — a deeper *endgame* provably doesn't touch it. The champion already banks the low-tax endgame at K≤2 fair.
4. **The only real fair lever** (make/unmake for deeper marginalized K) is a **3–5 day, OOM-prone build for ~0 expected winrate ROI.**
→ **A0 = decline, free.** If you want a direct fair number anyway: **A1** = `run_fair_grid.sh 3` (fair K=3 vs deployed K=2, CRN n=200) — build-free but **ATTENDED** (K=3 RAM regime, W≤6, capped TT/budget), hard kill-gate at winrate z<2. Held for you (not run unattended).

---
## C-cheap (deck-aware value) — LOW-ODDS cheap shot
Full spec: `C_CHEAP_SPEC.md`. The idea is real and Fable-sanctioned, BUT:
1. **The offline version already ran NULL** (`measurement/probe_b_4a/`, 2026-07-01): a sighted/deck-aware head on fair targets was inert across all 6 arms — at play depth the v2.9 leaf is a near-perfect *ranker*, so learned value adds no residual. This burns the cheap offline gate.
2. **Weak mechanism:** the bag histogram is *identical across the k_dets determinizations* at a given ply, so a deck-aware value only bites if it changes *relative* Q — a narrow window.
3. **6+ value-inertness nulls** already on the ledger.
4. **The one un-refuted cell:** a fair-outcome-labeled deck-aware value *inside the fair-play loop*, graded on fair PLAY — genuinely never run. Cheap to test (deck-aware input already exists + plumbed; build ≈ 1 emitter + a value-swap + a 3rd eval arm; ~1 local day, zero cloud). Pre-registered gate: fair-elo ≥ +35 over the heuristic-value fair champion; hard kill on null.
→ **Low success prior. The C-spec's own recommendation: run E4/A first, pull C by appetite as a single pre-registered fair A/B.** I'm NOT running it unattended against that ordering + prior; it's specced + gated for your call. (I can build+verify the scaffold in a worktree so it's a one-command launch, if you want it ready.)

---
## The k_dets probe (RUNNING) — the one live autonomous result
Fixed total 2752, k_dets {4,8,16,32}, fair vs h800, CRN n=200. Two payoffs:
- **DEPLOY TUNING:** the champion fixes k_dets=8; if 16 (or 4) beats 8 at *equal compute*, that's a **free fair-strength deploy win** (I'll n=400-confirm it — safe, cheap, real).
- **C mechanism signal:** if more sampling (more dets) shrinks the tax, marginalization is under-provisioned → C's mechanism has a target (raises C's prior); if k_dets=8 is optimal, C's prior stays low.
[RESULT: __TBD — fill when the sweep lands__]

---
## The meta-read (the thing worth saying out loud)
Both strength levers past B are weak: A's regime has no fair headroom, C's mechanism is mostly refuted. **That's not a failure — it's the measurement doing its job.** It means:
- The fair strength we HAVE is likely near the classical-search ceiling for this leaf: **+81 vs h800 at deploy, +149 at 2× compute, still scaling.** "Search deeper, fair" (more sims, not deeper endgame) remains the one lever that demonstrably raises fair strength — cheaply, no build.
- **E4 (the fair human exam) is the real question:** is +81/+149-vs-h800 *enough* to beat strong/expert humans? That's the deployment verdict, and it needs YOU (opponents / match setup). The fair ruler (D0) + the fair config (A2) to place humans on the scale are BUILT.
- If E4 says we're short, THEN the expensive bets (bigger nets / from-scratch — Fable's blocker-#2 path, still deferred) get their justification. A and C don't move that needle enough to fund ahead of E4.
