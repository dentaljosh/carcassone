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
- **n-discipline:** n=100 is a *screen* (1σ ≈ ±17 elo); n=400 is a *verdict* (1σ ≈ ±9). **Never promote a finding from a single screen.** A lone value beating its parameter-neighbors by >1σ is a **noise signature, not a peak** — re-measure. (This rule exists because the "c=3 +47" spike, sandwiched between +8 and +25 neighbors, was promoted to production and then re-screened at +13.9 — see DECISIONS 2026-05-28.)
- Reuse a fixed seed range across comparisons. Every eval must write a self-describing `manifest.json`.
- Log result in results.csv (auto-appended by the eval script); summarize the conclusion here. Move row from "open" to "done."
- If a finding flips an assumption downstream, *re-prioritize* the open list before continuing.

## Currently running

- **A1 re-baseline (2026-06-02):** iter_11 (NeuralMCTS) vs HeuristicMCTS, n=400, 3-box, on the new base-only bug-fixed game. Establishes the post-Phase-0 "where we actually stand." n=8 smoke 3W/5L=0.375 (screen). Verdict → results.csv. See STATUS.md.

## Open — by component, priority order

### Leaf evaluator (highest priority — strongly suspected ceiling)

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

| date | knob | result | conclusion |
|---|---|---|---|
| 2026-05-13 | Tier-1 vs warmstart_canonical (n=50 sims=100) | Tier-1 77% wr | NN-only NeuralMCTS loses to 1-ply heuristic. Recipe ceiling. |
| 2026-05-13 | Tier-1 vs iter_12 (n=50 sims=100) | Tier-1 75% wr | Same as above with v6's best checkpoint. |
| 2026-05-14 | HeuristicMCTS (no NN) vs Tier-1 (n=20 sims=200) | Tier-1 60% wr | Vanilla UCT + virtual_score leaf approaches Tier-1 but doesn't beat. |
| 2026-05-14 | Hybrid iter_12 (NN priors + virtual_score) vs Tier-1 (n=20 sims=100) | Tier-1 40% wr | **Value head was actively harmful.** 35pp swing from one knob. |
| 2026-05-14 | Hybrid iter_12 sims=200 (n=20) | Tier-1 40% wr | More sims didn't help. iter_12's policy is the ceiling. |
| 2026-05-14 | Hybrid warmstart_canonical sims=100 (n=20) | Tier-1 20% wr | **v1-v6 self-play degraded the policy head.** day-0 warmstart > iter_12 by 20pp. |
| 2026-05-14 | Hybrid warmstart_canonical sims=200 (n=20) | Tier-1 35% wr | More sims hurt hybrid_warmstart. Search exploits virtual_score's blind spots at depth. |
| 2026-05-14 | Sims sweep hybrid_warmstart (n=30 each: sims 50/100/150/200/400/800) | Tier-1 winrate: 36.7/41.7/41.7/30.0/23.3/23.3% | Earlier n=20 sims=100 was a lucky sample (was 20%). Curve actually monotone-improving with diminishing returns, plateau by sims=400. sims=800 = 0 gain over sims=400. Production sims=400. |
| 2026-05-14 | puct_uniform (no NN, uniform priors + virtual_score leaf) sims=100 (n=30) | Tier-1 60% wr | **NN policy head is worth ~18pp.** Cannot drop the network — uniform priors much worse than NN priors. |
| 2026-05-14 | virtual_score diagnostic — replay lost games at sims=400 (n=10, 3 losses inspected) | 5 failure modes ranked: closure-event blindness (3/3), farm composition opacity (2/3), denial invisible, over-committed meeples, late-game volatility | Top-2 modes account for the 30-pt-swing-in-1-move pattern. Informs virtual_score_v2 design (closure-proximity bonus + farm-growth potential). |
| 2026-05-14 | hybrid_v2 (v1 base + closure-anticipation + farm-growth) vs Tier-1 sims=400 n=30 | Tier-1 70.0% wr / hybrid_v2 30.0% / avg diff -10.6 | **v2 FAILS, ~47pp regression vs v1.** Adding leaf signal hurt search. Hypotheses: P heuristic too aggressive, cathedral-flag detection broken (`tile.inn` ≠ cathedral), bonus magnitude overwhelms base. Halt v2 deployment; build v2-diagnostic before v2.5/v3 decision. |
| 2026-05-14 | v2-diagnostic — per-move bonus dump on 1 hybrid_v2 vs Tier-1 game (sims=100) | cathedral never fires; bonus > base in 92% of moves; max bonus 133 (~7× base); farm-growth dominates 20× over city-closure | Root cause = scale, not bugs. tanh saturates → search loses gradient. Cathedral hypothesis wrong. Fix = halve P + cap bonus at ±5/player. |
| 2026-05-14 | hybrid_v2.5 (halved P + cap ±5) vs Tier-1 sims=400 n=30 | Tier-1 16.7% wr / **hybrid_v2.5 83.3%** / avg diff -30.7 | **v2.5 wins by 60pt+ pts**: +6.6pp over v1 (76.7%), +53pp over v2 (30%). Hits stretch goal ≥80%. The anticipation-bonus design was correct; the magnitudes had to be small enough to leave tanh in its responsive region. Production candidate. |
| 2026-05-14 | hybrid_v2.5 sims sweep n=30 each (50/100/200/400) | v2.5 wr: 50.0% / 71.7% / 80.0% / 83.3% (rule-player view: 50/28/20/17%); avg diff for v2.5: +1.8 / +19.5 / +24.7 / +30.7 | **sims=200 is the new sweet spot** at half the compute of sims=400. v2.5 ramps with depth more steeply than v1 (v2.5 < v1 at sims=50 by 13pp, but +10pp at sims=200, +6.6pp at sims=400). Bonuses are noise without enough search depth. |
| 2026-05-14 | orchestrator A/B at sims=100 (n=12 each) | W=6 baseline 19.0s/game; W=12 baseline 16.8s/game; W=12+orch 14.6s/game (avg_batch=4.8) | Orchestrator helps at W≥10ish locally; W=6 too few workers to fill batches → IPC overhead exceeds gain. Combined W=6→W=12+orch saves ~25% wallclock. |
| 2026-05-14 | hybrid_v2.5 cap sweep cap ∈ {2, 5, 8, 15} at sims=200 n=30 | hybrid wr: 60/80/73/77% | **cap=5 is the inverted-U optimum.** cap=2 strangles signal (-20pp); cap=8/15 reintroduces saturation (-3 to -7pp). Hand-picked cap=5 happened to land on the knee. n=30 SE ~9pp; cap=5 dominance over cap=2 is decisive, dominance over 8/15 is suggestive. Production stays cap=5. |
| 2026-05-15 | v2.5 dedup bug-fix: fixed v2.5 + cap=5, n=20 sims=200 cloud | wr 70% (down from buggy 80%) | The over-counting bug was load-bearing on cap=5's tuning. Fix correct, but bench number drops because cap was tuned against inflated bonuses. Triggers cap re-sweep. |
| 2026-05-15 | fixed v2.5 cap re-sweep cap ∈ {5, 8, 12, 20} n=20 each cloud | 70 / 60 / 85 / 85% | **cap=12 + cap=20 tie at the new optimum.** cap=12 chosen (lower magnitude = safer). +15pp over cap=5. |
| 2026-05-15 | v2.7 P-schedule sweep cap=12 n=20 each cloud: 1-only / drop-3-open / 3-tier | 77.5 / 90 / 85% | **v2.7 (drop-3-open) wins at 90%**, +5pp over 3-tier and +12.5pp over 1-only. The 3-open lottery tickets (P=0.05) were noise, not signal. Production = `_CLOSURE_P={1:0.5, 2:0.2}` + `_BONUS_CAP=12`. |
| 2026-05-15 | Cloud retrain iter_00 on v2.7 self-play (1200 games sims=200, ~$2.40, 6h10min) | iter_00 vs warmstart_canonical anchor (n=30 sims=200 v2.7 both sides): 18W/1D/11L = 61.7% wr, avg +14.3, elo +82.6 | **Policy retrain works.** First checkpoint generated by the new pipeline (correct leaf + retuned hyperparams + dedup) cleanly beats warmstart by +21pp. Saved at `checkpoints/v25_retrain/iter_00.pt`. |
| 2026-05-15 | iter_00 + v2.7 leaf vs Tier-1 (n=20 sims=200 local W=12+orch) | rule-player 1W/2D/17L → iter_00 wr 90%, avg diff -35.9 | iter_00 hits the same wr ceiling vs Tier-1 as warmstart_canonical+v2.7 (90%), but wins by more points (-35.9 vs -30.6). Tier-1 is now a saturated reference. The real test of iter_00 strength is human play. |
| 2026-05-15 | iter_00 vs iter_12 head-to-head (n=20 sims=200 v2.7 leaf both sides) | iter_00 16W/1D/3L = 82.5% wr, avg +16.5, elo +269.4 | **iter_00 demolishes the prior global best.** One iter of v2.7-leaf pipeline > 13 iters of v6 NN-value pipeline. Confirms the leaf eval matters way more than iteration count. iter_12 was probably weaker than warmstart_canonical too at v2.7 leaf — the v6 self-play degraded the policy. |
| 2026-05-15 | v3 sweep opp_cap ∈ {5, 8, 12, 20, 30}: Tier-1 vs iter_00+v3 (NN side only), n=20 sims=200 each | iter_00 wr: 95 / 75 / 90 / 80 / 80% | Wide swing 75-95% at n=20 SE ~7pp = within noise. Looked like opp_cap=5 was the winner. Tried n=50 confirmation. |
| 2026-05-15 | opp_cap=5 n=50 + opp_cap=20 n=50 confirmation | Both land at iter_00 80% wr; score diffs -26.3 vs -27.3 from rule POV (identical) | **n=20 wins/regressions all evaporated to ~80% at n=50.** v3 cap tuning is fitting noise. The v2.7 "90% baseline" was also n=20, so its true mean is likely ~80% too. Final read: opp_cap ∈ {5..30} all produce indistinguishable iter_00 strength against Tier-1. Cap-tuning direction exhausted. |
| 2026-05-15 | PUCT c sweep c ∈ {0.5, 1.0, 1.5, 2.0, 3.0} at iter_00+v2.7 leaf, n=20 sims=200 | iter_00 wr: 67.5 / 52.5 / 80 / 85 / 75%; score diff (NN POV): +4.2 / +7.2 / +27.4 / +40.3 / +37.0 | **Strong signal at low c.** c≤1.0 catastrophic (iter_00 barely beats Tier-1). c=1.5/2.0/3.0 all within n=20 noise but score-diff peaked at c=2.0. Confirms 2026-05-14 hypothesis: low c → search over-explores into virtual_score's blind spots. |
| 2026-05-15 | c=2.0 vs c=1.5 n=50 head-to-head | c=2.0: iter_00 88% / -38.5 score diff. c=1.5: iter_00 84% / -38.0 score diff | **c=2.0 advantage evaporates at n=50.** wr gap 4pp = 0.6σ; score diffs identical within 0.5pt. Default c=1.5 is fine; don't promote c=2.0. Real finding from sweep is the catastrophic-low-c boundary, not a better high-c value. |
| 2026-05-16 | iter_01 retrain: 1200-game v2.7 self-play from iter_00 weights (local, W=14, 10.6h) | anchor-gate vs iter_00 n=20: 12W/0D/8L = 60% wr, +11.8 avg diff; **n=100 confirm: 59W/1D/40L = 59.5% wr, +13.3 avg diff, +66.8 elo** | **iter_01 is the new global best.** First n=20 signal of the week to survive a larger-n confirmation (v3/PUCT both evaporated). +13.3 score-diff is similar magnitude to iter_00's +14.3 over warmstart → the v2.7 recipe compounded a second time. Next: iter_02 (does it keep compounding?). |
| 2026-05-17 | iter_02 retrain: 1200-game v2.7 self-play from iter_01 weights (local, W=14, 11.3h) | anchor-gate vs iter_01 n=20: 11W/0D/9L = 55%; **n=100 confirm: 51W/5D/44L = 53.5% wr, +0.2 avg diff, +24.4 elo** | **Compounding FLATTENED.** iter_00→01 was +13.3; iter_01→02 is +0.2 (wr 0.7σ above 50% — within noise; score-diff says zero gain). The policy has saturated against the fixed v2.7 leaf. Data-scarcity hypothesis held for exactly 2 iterations (+14.3, +13.3) then hit the leaf-defined ceiling. **iter_01 stays global best** — iter_02 not promoted (0.7σ isn't a confident gain; same discipline as the v3/PUCT n=20 false winners). Next is a structural change to the *leaf*, not more iterations — and NOT a bigger net (a bigger policy net saturates against the same leaf). |
| 2026-05-17 | leaf A/B: tile-counting closure gate (hard) vs v2.7, iter_01 both sides, n=100 sims=200 | tile-counting 45W/1D/54L = 45% wr, −4.8 avg diff, −31.4 elo | Hard deck-completability gate is null-to-slight-negative. The cliff fires only in the deep endgame — too rarely to move play. Triggered the continuous-ramp follow-up. |
| 2026-05-17 | leaf A/B: continuous deck-aware closure ramp (slack=3) vs v2.7, iter_01 both sides, n=100 sims=200 | continuous-P 50W/1D/49L = 50% wr, −1.4 avg diff, +3.5 elo | **Flat wash.** The ramp fires constantly in the mid-game (vs the cliff's deep-endgame-only) and still nets exactly 0. Pooled with the hard gate = 95/200 = 47.5%. **Closure-probability accuracy is not the lever.** Closure-P leaf refinement closed; pivot to Option 2 (NN value-head correction). |

## Closed — won't pursue

- **Try-another-recipe variants (v7+).** v1-v6 produced compound recipe knobs without isolating cause. Replaced by ablation-first.
- **Bigger self-play box class.** Was a candidate for v6 perf. Irrelevant now that v1-v6 is judged net-negative.

## Meta-rule

> "When self-play plateaus, the next experiment is component ablation, not another recipe variant. Try-harder-with-the-same-architecture is the trap." (DECISIONS.md 2026-05-14.)
