> ⚠️ **SUPERSEDED as the claim source by [`governance/CLAIM_REGISTRY.csv`](governance/CLAIM_REGISTRY.csv) (2026-06-07).** Kept for historical narrative; new claims go in the registry, not here. The open-questions / ablation queue below stays live here. See [`governance/README.md`](governance/README.md) for the raw → interpretation → decisions spine.

# Experiments — open ablation roadmap

A living priority queue of ablations toward superhuman play. **Not exhaustive** — meant to prevent drift, not to predict everything. Each row is one knob, not a recipe combo. Rewrite priorities when a finding invalidates a downstream question.

**Goal (primary, set 2026-05-28):** genuinely superhuman play — **beat strong/expert humans, aspirationally the world champion**, at **2p Base+Farmers** (River DROPPED 2026-06-02 — see DECISIONS). This is now the explicit target (overrides the original prompt; see [DECISIONS.md](DECISIONS.md) 2026-05-28 "Goal change"). The analyzer (Phase 5) and heuristic research (Phase 6) are downstream.

**⚠️ 2026-06-02 reframe — read first:** a foundational audit ([docs/research/foundational_audit_2026-06-02.md](docs/research/foundational_audit_2026-06-02.md)) operationalized "the leaf is the ceiling": the v2.7 leaf was masking 2 live bugs (farm + MCTS double-counts, FIXED) AND the learned value head was **never in the search loop**. The current path is the staged correction ([docs/CORRECTION_PLAN_2026-06-02.md](docs/CORRECTION_PLAN_2026-06-02.md) / [PHASE1_BUILD_SPEC](docs/PHASE1_BUILD_SPEC_2026-06-02.md)), not the open-ablation list below — treat that list as the post-correction backlog.

**The measurement problem is the #1 blocker.** The best checkpoint wins ~80-90% vs Tier-1, but Tier-1 is a saturated 1-ply heuristic a thinking human beats 2-of-3 — beating it is *not* superhuman. Self-anchored checkpoint-vs-checkpoint elo can climb while absolute strength regresses (Option-B chain proved it). No human benchmark is available right now. **So before more training has meaning, build a strong non-saturated reference ladder** (high-sim vanilla MCTS / the Ameneyro 2020 baseline) as an absolute yardstick. Without it we're flying blind.

**The leaf is the strength ceiling.** Search over the hand-crafted v2.7 leaf caps us near strong-human by construction; the path past it is making the *learned* components exceed the heuristic (KataGo-style domain planes + aux heads + scale), not more config tuning.

**Phase 5 (analyzer) is gated on superhuman.** Don't drift to Phase 5 work.

## Rules of engagement

- One knob varied per experiment. Hold everything else fixed.
- **`experiments/results.csv` is the source of truth for numbers** (added 2026-05-28). This ledger is the *narrative* layer — it cites the table, it does not own the authoritative numbers. Before claiming a finding, **query results.csv for prior measurements of the same cell** and resolve any contradiction.
- **n-discipline (CORRECTED 2026-06-02, round-2 audit G-M1):** near wr=0.5, σ_elo ≈ 695·√(0.25/n) unpaired → **n=100 ≈ ±35 elo, n=400 ≈ ±17 elo, ±9 needs n≈1500** (the old "±17 / ±9" was ~2× too optimistic). n=100 = coarse screen; n=400 = verdict ONLY for effects ≥ ~35 elo. **Deck-pairing (same deck both colors) ~halves variance → use it.** **Never promote a finding from a single screen.** A lone value beating its parameter-neighbors by >1σ is a **noise signature, not a peak** — re-measure. (This rule exists because the "c=3 +47" spike, sandwiched between +8 and +25 neighbors, was promoted to production and then re-screened at +13.9 — see DECISIONS 2026-05-28.)
- Reuse a fixed seed range across comparisons. Every eval must write a self-describing `manifest.json`.
- Log result in results.csv (auto-appended by the eval script); summarize the conclusion here. Move row from "open" to "done."
- If a finding flips an assumption downstream, *re-prioritize* the open list before continuing.

## Currently running

- *(nothing live — see [STATUS.md](STATUS.md) "Right now" for the active step.)* The A1 re-baseline finished 2026-06-02: iter_11 vs HeuristicMCTS, n=400, base-only bug-fixed game = **+25.2 elo** (`results.csv: ladder_iter11_vs_heuristic_baseonly_n400`), collapsed from the old-game +181.7 — the learned policy adds ~nothing over the v2.7 leaf. See DECISIONS 2026-06-02 "RE-BASELINE VERDICT".

## Post-correction backlog — by component

> **⚠️ NOT the current plan.** The active path is the staged correction ([CORRECTION_PLAN](docs/CORRECTION_PLAN_2026-06-02.md) → Stage A/B/C in [PHASE1_BUILD_SPEC](docs/PHASE1_BUILD_SPEC_2026-06-02.md)). This list is the pre-audit open-ablation queue, kept as a backlog to pull from *after* the correction lands (and to avoid re-litigating already-closed knobs). Many entries below were written before the 2026-06-02 audit reframed "the leaf is the ceiling" as "the value head was never in the loop" — read them as historical priorities, not marching orders. Don't action a row without checking it against the build spec first.

### Leaf evaluator (pre-audit "highest priority"; mostly closed below)

- [X] ~~**Does NN policy actually help?**~~ DONE 2026-05-14: yes, worth ~18pp. puct_uniform sims=100 → Tier-1 60%; hybrid_warmstart sims=100 → Tier-1 41.7%. Network adds real value; can't drop it.
- [X] ~~**What does virtual_score get wrong?**~~ DONE 2026-05-14: top failure modes are closure-event blindness (3/3 lost games) and farm composition opacity (2/3). Both involve `virtual_score` giving partial credit that doesn't anticipate the partial→full credit swing when features close. Full writeup in [DECISIONS.md](DECISIONS.md). Tooling: [scripts/diagnose_v2.py](scripts/diagnose_v2.py) (shows both v1 base AND v2 bonus per move; the older `diagnose_virtual_score.py` was deleted 2026-05-15 since the v2 tool subsumes it).
- [X] ~~**virtual_score_v2: closure-proximity bonus + farm-growth potential.**~~ DONE 2026-05-14: built and benched. **FAILED** — 30.0% wr vs Tier-1 at sims=400 n=30, a ~47pp regression from v1's 76.7%. Tools (`virtual_score_v2.py`, `_hybrid_v2_evaluator` wiring, 11 tests) are committed for v2.5 / v3 iteration. See DECISIONS.md 2026-05-14 for hypothesized causes (P heuristic too aggressive, possible cathedral-flag bug, possible bonus-dominates-base scale issue).
- [X] ~~**v2-diagnostic: which bonus type misled v2?**~~ DONE 2026-05-14: cathedral branch doesn't fire (not a bug); `bonus` overwhelms `base` in 92% of moves; max bonus ~7× base; tanh saturates → search loses gradient. Farm-growth bonus dominates 20× over city-closure. Root cause = magnitude, not sign or design. See DECISIONS.md.
- [X] ~~**v2.5: halve P heuristic + cap bonus per player at ±5.**~~ DONE 2026-05-14: **83.3% wr vs Tier-1** at sims=400 n=30 (+6.6pp over v1, +53pp over v2, hits stretch target). Avg score diff -30.7 from Tier-1's side. Production candidate. See DECISIONS.md.
- [X] ~~**v2.5 sims sweep.**~~ DONE 2026-05-14: curve = 50/72/80/83% at sims 50/100/200/400 (n=30 each). **sims=200 is the new sweet spot** — 80% wr at half the compute of sims=400. Production reads diminish hard after 200. v2.5 ramps with depth more steeply than v1 (v2.5 < v1 at sims=50, but pulls ahead at sims≥100).
- [X] ~~**v2.5 cap tuning.**~~ DONE 2026-05-14: cap ∈ {2, 5, 8, 15} at sims=200 n=30. Result: 60/80/73/77% — **cap=5 is the optimum**, hand-picked happened to land on the knee. cap=2 strangles signal (-20pp); cap=8/15 reintroduces tanh saturation (-3 to -7pp). n=30 SE ~9pp so cap=5 vs cap=8/15 isn't bulletproof but cap=2 is decisively worse. Production stays cap=5.
- [X] ~~**v3 (denial-value + meeple-economy).**~~ DONE 2026-05-15: **INCONCLUSIVE — cap tuning is fitting n=20 noise.** Full sweep opp_cap ∈ {5, 8, 12, 20, 30} ranged 75-95% at n=20 SE ~7pp. n=50 confirmation: opp_cap=5 lands at 80%, opp_cap=20 lands at 80%. All opp_cap values produce iter_00 wr ~80% ± 5pp vs Tier-1 — the v2.7 "baseline 90%" anchor was also n=20 noise. Meeple_K null. Infra committed but defaults unchanged. **Implication:** v2.7 cap=12 is at or near a local optimum; further cap tuning won't move the needle. Real next steps: more training data (iter_01 retrain), different leaf structure, or PUCT search-side knobs.
- [X] ~~**PUCT c sweep.**~~ DONE 2026-05-15: c ∈ {0.5, 1.0, 1.5, 2.0, 3.0} at iter_00+v2.7 leaf, sims=200, n=20 pilot. **Real finding:** low c is catastrophic — c=0.5 → iter_00 67.5%, c=1.0 → 52.5% (barely beats Tier-1). c=1.5/2.0/3.0 all land at 75-85% at n=20. c=2.0 n=50 = 88%, c=1.5 n=50 = 84% — indistinguishable (0.6σ). Default c=1.5 is well-chosen; do NOT promote c=2.0. Hypothesis "low c → over-exploration into virtual_score blind spots" CONFIRMED. The NN policy prior is load-bearing.
- [X] ~~**Deck-aware closure probability (tile-counting leaf refinement).**~~ DONE 2026-05-17: closure-anticipation P(closure) made deck-aware — a hard gate (P→0 when the deck can't finish a feature) and a continuous ramp (P scaled by deck supply). Same-checkpoint leaf A/B, iter_01 both sides, n=100 each. **Both null:** hard gate 45% wr / −4.8 diff, continuous ramp 50% wr / −1.4 diff; pooled 47.5%. **Closure-probability accuracy is not the leaf-eval lever** — MCTS doesn't need it calibrated. Closure-angle leaf hand-tuning exhausted; pivot to NN value-head correction (Option 2). See DECISIONS.md 2026-05-17. Infra (`LeafConfig`, leaf-variant A/B) is reusable for Option-2 tuning.

### Policy head

- [ ] **Policy retraining on hybrid-generated data.** Generate ~10K games of hybrid_warmstart vs hybrid_warmstart at sims=100. Train a fresh policy head (frozen trunk) on those positions. Test vs Tier-1. Hypothesis: training on hybrid-strength games beats training on heuristic targets. (~1 day code + 4-8h compute, ~$2-5 cloud.)
- [ ] **Bigger policy capacity.** Widen `policy_project_channels` 4 → 16 → 32 (BACKLOG note). Retrain warmstart with the wider head. Test vs Tier-1 with hybrid eval. (~1 day arch + 4h retrain, ~$2.)
- [ ] **Action-space dedup.** Coalesce equivalent meeple-placement slots (BACKLOG note). Bigger refactor — touches action_space.py + decode + dataset shape. Defer unless small-action-space variants give clear wins. (~1 day refactor + 4h retrain.)

### Search

- [X] ~~**Sims-depth self-consistency A/B.**~~ DONE 2026-05-18: iter_01 @ sims=800 vs iter_01 @ sims=200, same checkpoint both sides (only search depth varies), n=50, plain v2.7 leaf. **38W/0D/12L = 76% wr, +24.9 avg diff, +200 elo (3.7σ).** The policy is significantly under-searched at production sims=200 — deeper search is a large, under-exploited strength lever. Reframes the iter_01→02→B1 retrain plateau as the *training* recipe saturating, NOT a hard v2.7-leaf ceiling. **Re-prioritization:** search-depth knobs (sims ladder to find saturation, deeper-search self-play, α-β) are now the validated #1 strength lever. See DECISIONS.md / STATUS.md 2026-05-18.
- [X] ~~**Sims ladder.**~~ DONE 2026-05-18: 3 rungs (n=50, iter_01 both sides). 800 v 200 = **76%**; 800 v 400 = **62%/+85 elo**; 1600 v 800 = **52%** (coin-flip). **Knee at 800, confirmed both sides** — 400 insufficient (800 wins 62%), 1600 buys nothing. 200→800 ≈ +200 elo. Production/play inference-sims target = **800**; deeper-search self-play (if pursued) = sims=800, ~4× compute (no 2× shortcut). See STATUS.md.
- [ ] **Deeper-search self-play.** Retrain with sims=800 (or the ladder knee) self-play — stronger MCTS visit-count targets may un-stick the policy plateau. ~4× per-iteration compute vs sims=200; cost decision pending.
- [ ] **Depth-limited search.** Force the search to reach a minimum depth before evaluating leaves. May counteract virtual_score's exploit-at-deeper-depth failure mode. (~2 days code.)
- [ ] **Alpha-beta variant.** Replace PUCT with classical α-β at depth 4-6. For domains with a strong static eval (which we now have), α-β often beats MCTS. (~3 days code.)
- [ ] **MCTS with NN value retained.** Re-test (NN policy + NN value) vs (NN policy + virtual_score) once the value head is retrained — does fixing value-head training rescue it? Only after policy-retraining experiment lands.

### Network architecture

- [ ] **Bigger trunk.** 192×14 or 256×10 (BACKLOG note). Untested. Defer until policy/leaf experiments converge — bigger trunk only matters if we have a training signal that uses the capacity. (~1 day arch + 8h retrain, ~$5.)
- [ ] **Drop the value head entirely.** With virtual_score-as-leaf, the value head is dead weight: slow forward pass, no contribution to search. Removing it saves ~1M params and ~5ms/inference. (~30 min code if we keep the file, more if we cleanup training pipelines.)

### Training process

- [ ] **Self-play with hybrid players.** Rebuild the self-play loop using `hybrid_warmstart` (not raw NN) as both players. Generates higher-quality training data than the v1-v6 setup that degraded both heads. (~1-2 days code; depends on the policy-retraining experiment outcome.)
- [ ] **Async training.** BACKLOG note. Only sensible if self-play resumes as a useful signal.

## Done — findings ledger

> **Moved.** The per-experiment numbers (n, wr, elo, score-diff) live in [experiments/results.csv](experiments/results.csv) — the source of truth — and the reasoning behind each is in the dated [DECISIONS.md](DECISIONS.md) entries (see its Index). This ledger used to duplicate both and drifted, so it's gone. To look up a past finding: grep results.csv for the run name, then read the matching DECISIONS entry for the *why*.

The arc of the May findings, in one paragraph so a fresh reader has the shape: NN-only NeuralMCTS lost to the Tier-1 1-ply heuristic (the v1–v6 recipe ceiling) → the **NN value head was the bug** (NN priors + `virtual_score` leaf flipped Tier-1 75%→40% in our favor) → leaf tuning: v2 failed (magnitude/tanh-saturation), v2.5 fixed it (cap=5, then cap=12 after the dedup bug-fix), v2.7 (drop-3-open) became production → policy retrains compounded twice (iter_00 +21pp, iter_01 +13.3) then **flattened at iter_02** (saturated against the fixed leaf) → cap/PUCT/closure-P sweeps all evaporated at larger n (the noise-vs-signal lessons that hardened the n-discipline rule). The 2026-06-02 audit then reframed the whole plateau: the value head was **never in the search loop** (prod self-play ran the v2.7 leaf), so it never had a chance to beat the heuristic — which is exactly what Stage B tests.

## Closed — won't pursue

- **Try-another-recipe variants (v7+).** v1-v6 produced compound recipe knobs without isolating cause. Replaced by ablation-first.
- **Bigger self-play box class.** Was a candidate for v6 perf. Irrelevant now that v1-v6 is judged net-negative.

## Meta-rule

> "When self-play plateaus, the next experiment is component ablation, not another recipe variant. Try-harder-with-the-same-architecture is the trap." (DECISIONS.md 2026-05-14.)
