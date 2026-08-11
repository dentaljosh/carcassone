# Overclaim Risks — what the reviewer should watch for

These are the dangerous overstatements the evidence does **not** support. Each pairs the tempting
claim with the corrected reading and the citation. A reviewer should flag any of these if it appears
in project prose, commit messages, or a future "results" summary.

| # | ❌ Dangerous overclaim | ✅ Supported reading | citation |
|---|---|---|---|
| 1 | **"iter8 is superhuman"** | Unsupported. Every elo is clairvoyant + in-ecosystem (v2.7-leaf), **not human-anchored**. iter8 is a *bounded policy-distillation* gain over its incumbent, capped by the v2.7 leaf, and is *caught* by deeper heuristic search (heur@3200). No absolute / human strength number exists. | CL-005/011/018/024; MEASUREMENT_FIRST_SPEC §1,§6 |
| 2 | **"deepteacher failed"** (flat) | Incomplete. The published "failure"/"washout" numbers were measured against the **wrong baseline** (`residual.pt`, not the warm-from iter8) — a provenance defect. The **correct** clean comparison (iter12 vs iter8) is a **statistical TIE** at both s200 (+14.6/z0.65) and s800 (+12.4/z0.51): a powered null, "did not beat iter8," **not** "ran from a worse start." | CL-019, CL-020; [DEEPTEACHER_PROVENANCE_AUDIT.md](sources/DEEPTEACHER_PROVENANCE_AUDIT.md) |
| 3 | **"hybrid is a new champion"** | False. Hybrid **patches** iter8 (beats it on paired margin, reproduced n=400) but **loses** to heur@3200 (hybrid:5 −13.9/z−0.30, hybrid:8 −19.1/z−0.51, |z|<1). It is **gap-closing, not surpassing**. Nothing was promoted. | CL-026; [LEVEL2_HYBRID_VERDICT.md](sources/LEVEL2_HYBRID_VERDICT.md) |
| 4 | **"iter8 is bad at endgames"** | Too strong. Better: iter8 is **less precise / less robust in sharp / OOD exact-K=4 states** (sharp top-1 0.40, regret 3.34) while *reaching* easier endgames itself (within1=28.5). Its errors are *bidirectional* and small (no >10-pt blunders at K=2). It is the *least precise* endgame technician, not incompetent — and it still *wins full games*. | CL-025/027 (H1 rejected, H2/H3 supported); [LEVEL2_L23_VERDICT.md](sources/LEVEL2_L23_VERDICT.md) |
| 5 | **"clairvoyance was a major artifact"** | Excluded. The paired gap is **+26.6 elo, z=−0.9** (not distinguishable from 0); P(gap≥100) ≈ 2%. A non-clairvoyant agent keeps essentially all of iter8's strength. A **large** clairvoyance inflation is ruled out at ~2σ (at sims=200). | CL-022; [CLAIRVOYANCE_GAP_VERDICT.md](sources/CLAIRVOYANCE_GAP_VERDICT.md) |
| 6 | **"the value head can't work at all"** | Too strong. The **tested** formulations (conv/attention + MSE/ranking/advantage, this scale) are disfavored — they rank siblings ~20× below v2.7. This is *no positive signal for the tested swing*, **not** a proof that *no* learned value/ranker can ever work. | CL-021; [VALUE_RANKING_VERDICT.md](sources/VALUE_RANKING_VERDICT.md) (own "caveats" §) |
| 7 | **"heur@3200 is optimal / ground truth"** | Unsupported. heur@3200 is the **strongest known *practical* ruler** (catches iter8; most endgame-precise), but the ladder shows deeper search **keeps gaining** (not saturated at @1600) — so @3200 is just the deepest rung we ran, **not** an optimum and **not** human-anchored. | CL-023/024; [LEVEL2_LADDER_VERDICT.md](sources/LEVEL2_LADDER_VERDICT.md) |
| 8 | **"tool features will fix it"** | Unproven. No evidence exists either way; the proposal (PROP-1) is motivated by the endgame weakness but must be **audited first** — a learned ranker risks repeating the value-head dead end (CL-021) and any leaf-level gain may **wash out under search**. | PROP-1; CL-021; memory `feedback_sims_washout_net_eval` |

## Subtler traps (cross-cutting)
- **Cross-band elo composition.** Composing elo across *different* deck bands stacks noise and has
  produced phantom effects (the ~50-elo "non-transitivity" was cross-band artifact; the
  +55→+20 heur@1600-vs-@800 "swing" is within noise). Only **same-band paired** comparisons compose.
  (CL-024)
- **Lone >1σ spike vs neighbors = noise, not a peak.** (Project rule; the historical "c=3 +47 elo"
  lesson.) Don't promote a single screen.
- **Clairvoyant vs marginalized labels.** All solver results are **clairvoyant** (perfect deck
  order). The *preferred* fair-information (bag-expectation) ground truth is **untested at K≥3**.
  Don't present clairvoyant endgame optimality as the fair-information truth. (CL-027 caveats)
- **"Strongest known practical agent" ≠ "optimal / superhuman."** Keep these distinct in every
  sentence about heur@3200.
- **Endgame-optimality ≠ full-game Elo.** iter8 is simultaneously the *full-game-strongest learned
  agent up to ~@1600* and the *least endgame-precise* — both are true; neither implies the other.
  (CL-024 vs CL-025/027, deliberately kept separate)
- **"Significant" must name n and pairing.** n=400 paired ≈ ±17.5 elo; a +20 elo gain is *not*
  resolvable at n=400. Several "wins" that didn't carry (deepteacher iter2/iter9) were
  band-favorable single screens.
