# Architecture Decision Record

Every non-trivial technical decision gets logged here. The bar for "non-trivial" is: if Joshua looked at this code in 3 weeks and asked "why did we do it this way?" — would the answer be obvious from the code alone? If no, log it.

**Always log:** board representation choices, action space encoding, network architecture, hyperparameter values that aren't from a cited paper, framework/library choices, anything where you considered alternatives.

**Don't log:** variable names, file organization, formatting choices, library version pinning, anything that's purely a style decision.

## Index (newest first)

> Ctrl-F a date or keyword. Entries below are reverse-chronological. This index is maintained by hand — when you add an entry, add its line here. The current path forward is **not** in any single entry; see [STATUS.md](STATUS.md) (live state; the 06-02 correction plan is an executed historical artifact).

**2026-06 — correction era (current)**
- 2026-07-02 (**S1 FLIP — v2.9.1 Bmild_cap8 PROMOTED to the production leaf + deep-classical (HeuristicMCTS h6400–h12800 + exact K≤4 endgame handoff) as the production champion, superseding neural iter8**; post-review plan `docs/POST_REVIEW_PLAN.md` §1; CL-041; authorized by Joshua "flip s1" 2026-07-02) — the DEFERRED h6400 promotion arbiter (fresh band 4.21e9, n=399 paired, `scripts/v29/eval_v29_vs_v28.py`): **v2.9 Bmild_cap8 vs REAL production v2.8 (`v28prod` cap12+drop3open) @ h6400 = winrate 0.591 (234W/4D/161L), +64.3 elo, paired z(margin) +3.77** = verdict-grade, clears the ≥0.55 promotion bar at the DEPLOY depth. Completes the 2026-06-25 audit's deferred h6400 arbiter + the throne-test depth ladder (sims200 +55.2/z3.94, sims800 +34.9/z2.77 — depth-robust). Classical is the stronger agent at depth (RoD1 LOSES to h6400; the sims=200 neural champion capped near strong-human), so PRODUCTION.yaml champion → **deep-classical v2.9 Bmild_cap8**; neural iter8 retained as lineage. **A LEAF/AGENT promotion, NOT a learned-superhuman result** — whether a learned value can EXCEED this leaf is the open post-review autopsy (M1/M2/M3). results.csv `v291_THRONE_bmild_cap8_vs_v28prod_h6400_n399`; **CL-041** (supersedes flywheel2_champion_iter8 as PRODUCTION). Infra: the arbiter tail-stalled repeatedly (workers crash under sustained 5+hr load → stranded shared-claims the once-through harness won't revisit) → cleaned stranded claims + relaunched fresh pools to complete.
- 2026-07-03 (**M2 REOPENER — the never-run canonical-AZ cell BUILT + orch-accelerated + LOOP RUNNING; read-out PRE-REGISTERED, solver-scored**; post-review plan `docs/POST_REVIEW_PLAN.md` §4; contributes to CL-042) — samples the one cell the whole value-inertness ledger left structurally open (every prior net had a saturated/0.5%-variance target, `value_global_pool=False`, blind rep): **sighted rep (+3 union-find farm planes / +32 bag histogram) × pooled value head (`--global-pool`) × `score_diff_wide` target × FPU=0.6 installed × `--leaf-eval nn`** (the value drives the leaf). carc-orch extended to the sighted 81-channel input, gen **parity-proven bit-exact vs orch-off**; loop running 5 iters on local+laptop. Read-out ([measurement/canonical_az/M2_PLAN.md](measurement/canonical_az/M2_PLAN.md), `9cbd818`) fixed before the numbers: eval iters 1/3/5 = (1) solver-scored value ranking vs the exact K≤4 solver (`scripts/canonical_az/solver_score.py`, the F4 non-circular scorer, `b0e7158`) + (2) rs-sweep {0,0.25,0.5}@FPU0.6 game effect vs RoD-v2 iter_02, headline confirm vs h_v2.9@3200. **FIRE** = solver-τ beats the leaf + improves 1→3→5 + ≥2σ monotone rs game gain (first in project history → revives the flywheel); else **earned CL-039 scoped closure**. Commits: sighted `86f9695`/`41d49df`/`e5b6ac0`, orch `f83b38e`, stall-heal `8dd20ed`. MEASUREMENT ONLY.
- 2026-07-03 (**M3 REOPENER — Gate-B refuted as a LAW (FPU recovers the weaned-value crater to parity) but the FPU AXIS is CLOSED (peaks at parity, rolls off beyond)**; post-review plan `docs/POST_REVIEW_PLAN.md` §3; contributes to CL-042) — full n=400 FPU curve on the additive weaned-value crater (candidate-only FPU/c_puct knobs added `724c903`; anchor = additive blend0 wr 0.500): **fpu=None 0.265 → 0.4 0.391 → 0.6 0.496 (PEAK = parity, z−0.15 vs the 0.500 pure-heuristic anchor) → 0.8 0.4825 → 1.0 0.476.** So **Gate-B (CL-038, "a learned value can't drive MCTS search") is refuted as a LAW** — the crater is a fixable FPU/optimistic-tail artifact (isotonic recovered *less* than FPU → mechanism = the MCTS max-operator hunting the value's optimistic tail, which FPU tames directly; the 3 nails were blind to it). BUT recovery is to PARITY not exceeding, and higher FPU rolls off → **FPU removes the weak τ≈0.43 value's harm but cannot make it exceed the τ≈0.895 leaf**; the exceed-lever is a better VALUE (M2), not more FPU. The value-leaf lever REOPENS; CL-039 stays QUALIFIED, not upgraded. results.csv `m3_confirm_fpu0{4,6,8,10}_c3_b027_n400`; commits `0738450`, `1d962e6`. MEASUREMENT ONLY.
- 2026-07-02 (**M1 REOPENER — deepteacher iter2 KILLED: its prior "+53.7" was band noise; "deeper-teacher doesn't help" now POWERED**; post-review plan `docs/POST_REVIEW_PLAN.md` §2; contributes to CL-042) — fresh-band fixed-rung paired eval (each of iter2/iter8 vs heur@800-v2.7, band 5.0e9, sims=800, n=400): iter8 +136.0/z7.71, iter2 +138.0/z7.93 → **paired Δ(iter2−iter8)=+2.0 elo, z=0.09 = TIE.** iter2 does NOT clear ≥2σ over iter8 → the mid-run +53.7/z2.14 (+50.4/z1.42 on a second band) was band-max noise / forking paths, refuted on a third fresh band. No revival of the deeper-teacher line — CL-019 ("a deeper policy teacher doesn't raise strength over its warm-from at the deep plane") STANDS, now powered. results.csv `m1_deepteacher_iter2_vs_iter8_freshband_h800_s800_n400`; commit `0738450`. MEASUREMENT ONLY.
- 2026-07-01 (**PROBE §5A — TEMPO/TIMING third-independent-axis gate: RAN, INCONCLUSIVE on the rigorous gate, but a LIVE OFFLINE LEAD that QUALIFIES CL-039's "genuinely low-dimensional" clause**; spec `docs/PROBE_5A_TEMPO_AXIS_GATE.md`, results `measurement/probe_5a/PROBE_5A_RESULTS.md`; branch `rod_v2_flywheel`; CL-040) — the honest falsifier owed to CL-039's dimensionality claim, which rested on only **two known-redundant axes (farm, bag)**. §5A tests a third axis **uncorrelated-by-construction** with farm/bag: tempo/timing (the leaf's meeple-economy term is FLAT → timing is the named axis the heuristic handles crudely, never value-tested). **Gate-zero (free correlation kill) PASS→PARTIAL:** emitted a structural-tempo block via `step1_dump.py`'s exact enumeration, joined to the CL-037 dataset by (game_seed, ply, child_index), **bit-exact leaf-recompute (0.00e+00)**; the naive counts (open-road/city R²=0.86/0.79, farmer counts ~0.73) are ≥0.72 reconstructible from the already-present representation → dropped; a genuine **10-feature timing-depth core survives** (depth-weighted meeple lockup Σ open_n, closure-race, contested, open-city-delta — mean R²=0.28, canonical ρ₁=0.76 < 0.90). **Single-seed 4-arm at h6400** (n_scalar=54, tempo appended to all arms): **`tempo_only` = +44.7% regret-reduction (τ 0.223, α=0.25, clean monotone sweep), leak-verified** (all tempo features |r|≤0.51 vs oracle_q vs the leaf's own +0.996) = the **strongest clean offline ranker in the whole probe program, LARGER than CL-037's farm/bag −20.5%** → tempo is **NOT** an inert/redundant axis (H-5A-inert REFUTED). **BUT the run is single-seed with a BROKEN positive control:** `both` (farm+bag) came back inert (+0.0%) though the same harness gives CL-037's `both` **+20.5% at n_scalar=44** — appending 10 zero-variance tempo columns (width 44→54) flipped it (**RNG-init/normalization fragility**); the non-monotonic `all_three +17.5 < tempo_only +44.7` confirms single-seed training is noise-dominated. Per §4's invalid-gate guard no clean Δ_indep is readable from one seed → the confirming **4-config × 4-seed sweep was launched and OOM-KILLED before any of the 16 runs finished** (concurrency-4 on the 41 GB WSL box, self-inflicted; **not relaunched** — Joshua's call to start fresh). **NET: INCONCLUSIVE on the pre-registered ≥3pp CRACK bar, but a live, unresolved OFFLINE tempo lead.** **This QUALIFIES CL-039** — the "residual value is genuinely low-dimensional" clause rested on two known-redundant axes; the third, uncorrelated axis was the strongest clean offline ranker, *not* redundant → the low-dimensionality claim is **NOT established**. **The SHIP decision is UNCHANGED (analyzer endgame-2 + B1):** §7 is invariant across branches, AND this is an **OFFLINE** signal — CL-034's −41% offline win WASHED OUT under sims=200 search, so even a seed-confirmed tempo crack is a *recorded lead, not a loop authorization*. If the AZ-value question is ever reopened, step 1 is the seed-swept tempo confirmation (run SOLO / concurrency-2 to avoid the OOM), and **tempo — not farm/bag — is where a future fair-from-scratch loop or scale-up would aim.** No games (offline ranking gate → no results.csv row). MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED. **CL-040** (qualifies CL-039); docs `measurement/probe_5a/`; scripts `scripts/probe_5a/` (`emit_tempo.py`/`gate_zero.py`/`leak_check.py`/`run_seedsweep.sh`/`aggregate_seedsweep.py`); commits `58262ef`/`6710492`/`334bef8`.
- 2026-07-01 (**POST-GATE-B AZ-VALUE PROBES A & B BOTH CLOSED → the learned-value route is EXHAUSTED across scalar/structured/clairvoyant/fair; ship the analyzer (endgame-2) + B1**; specs `docs/PROBE_A_STRUCTURED_VALUE_SPEC.md` / `docs/PROBE_B_FAIR_INFO_SPEC.md`; §4A results `measurement/probe_b_4a/PROBE_B_4A_RESULTS.md`; branch `rod_v2_flywheel`; CL-039) — the two unfalsified AZ-value bets after Gate-B, pre-registered + boxed, both ran and closed. **PROBE A (structure-emitting value LEAF)** — gate-zero speed PASS (structured per-component leaf feasible at 2.24–2.71× the Cython leaf; 24-dim feature contract + bit-exact Cython emit; g_θ trained, aggregate R² 0.99), then **KILLED at the pre-registered §3A farm/bag INDEPENDENCE gate**: re-running CL-037's farm/bag ablation on the *structured* head gave `Δ_indep = both − max(farm-only, bag-only) = +0.05pp` (paired σ 0.36, 95% CI [−0.61,+0.78], ~8σ below the +3pp "separated" bar) — farm/bag stay REDUNDANT in the structured object too (even cleaner than CL-037's scalar +0.8pp; emphasis flips — farm carries it, bag inert). ⇒ the value signal beyond the leaf is genuinely LOW-DIMENSIONAL, the scalar was NOT the bottleneck, the structured object extracts nothing the scalar destroyed. Killed at the CHEAP gate — no crater screen, no in-loop budget. Commits `315122d`/`b48694a`. **PROBE B (fair-info flywheel)** — gate-zero done (`fair_isolate` leak fix: the flywheel-gen path — persistent tree, K=1, per-move reshuffle — reused stale cross-determinization nodes; 0 after the fix, 10/10 deterministic; fair-target range ADEQUATE, `451fadb`). The §4A fair-target diagnostic ran full-n (matched-depth **fair@800 vs clair@800**, obs/scalars/split/ids bit-identical so the only variable is clairvoyance; n_test=1544): **ALL SIX arms INERT** (best_α=0, regret_red +0.0%, beats_leaf=False), and the n=150 preview's "clair non-inert (α=0.05)" was an **8-group small-sample artifact, refuted at full n**. **§4A is DEPTH-SATURATED / inconclusive on its own** — the clean H-4A-inert test needs a *non-inert* clair baseline, but clair@800 is inert too (CL-037's α=0.05 required the DEEP h6400 teacher; at play depth even clairvoyant targets give the value no residual over the v2.9 leaf); clairvoyance-vs-depth is **deliberately left UNRESOLVED, out-of-scope for the ship decision** (an h6400-depth §4A would answer it — a mechanism nicety, not funded). **THE CLOSE IS ON THE LEDGER, NOT THE SCREEN:** the flywheel bet closes on the accumulated value-inertness ledger — CL-029 (RoD2 flywheel null), CL-032 (value/search autopsy), CL-033 (value-resurrection ranker), CL-034/CL-036 (comparator washout / typed-GNN inert), CL-038 (Gate-B scalar leaf), Probe-A §3A (structured leaf) — spanning **scalar+structured on clairvoyant targets**, plus Gate-B's offline→online mechanism (a value can rank yet fail to drive search); §4A only *extends* the pattern to **fair** targets (consistent but inconclusive alone). ⇒ **the AZ-VALUE route is exhausted (scalar/structured/clairvoyant/fair). Ship the analyzer** (endgame-2, the original Phase-5 win condition), served by the proven sighted value head, **with B1 (the fair-info agent, `fair_isolate` fixed) as the deployable, human-anchorable artifact** (Probe B's non-empty failure path). Commits `c4a5465`/`be538a7`. Infra scars (self-inflicted, logged): laptop WSL tore down on the detached gen launch (→ local fallback); the fair+clair 32 GB retargets run CONCURRENTLY OOM-restarted the 41 GB WSL (→ large-obs ops run SOLO); the full-n eval hit a GPU fragmentation OOM (→ `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` + `--groups-per-batch 8`) then a cross-obs page-cache OOM (→ don't cache two 32 GB obs at once — re-run same-obs arms together). No games (offline ranking diagnostic → no results.csv row). MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED. **CL-039**; scripts `scripts/probe_a/` + `scripts/probe_b/`.
- 2026-06-29 (**REPRESENTATION GATE (charter Step 1, the decision gate) CONCLUDED — Gate A PASS: farm-connectivity planes (+3, from `flat_leaf.decompose`) + a per-tile-type bag/deck-composition histogram (+32 scalars) FLIP CL-033's best-α=0 on the SAME sibling-ranking protocol → the value head's inertness was partly a REPRESENTATION confound, not a pure architecture-independent ceiling**; full detail `measurement/feature_planes_gate/STEP1_GATE_RESULTS.md`; branch `rod_v2_flywheel`) — re-ran the CL-033/CL-034 sibling-ranking gate (same 10,067 h6400_v2.9 sets, same RankNet V4_listwise, same α-sweep, group-split by `game_seed` n_test=1544, frozen v2.9 leaf hash `7fc930b82801cb43`) on 5 feature regimes. **Sighted `both` (78+3 farm planes, 12+32 bag scalars): τ 0.207 / α 0.05 / regret 0.0263→0.0209 = −20.5% vs blind `none` (78ch): τ 0.140 / α 0.05 / −1.9%** — clears the pre-registered ≥15% criterion. **Pre-registered NEGATIVE CONTROL `both_shuffled` (farm planes + bag scalars permuted off their true rows, base 78ch+12 kept aligned) collapses the whole effect** (τ→0.139, α→0, +0.0%, val_loss 3.3014 ≈ `none`'s 3.3020, no sub-`none` leak) ⇒ the signal is real + position-aligned, not a leak/artifact. **ATTRIBUTION (farm/bag ablation): farm-only −17.1%, bag-only −19.7%, both −20.5% ⇒ the two are LARGELY REDUNDANT** (substitutes, not additive; each alone recovers most of the signal; at n=1544 the farm-vs-bag gap is within noise — do not hard-rank). **The bag/deck-composition axis is information the v2.7/v2.9 leaf STRUCTURALLY CANNOT see** (it scores the current board, not what remains to draw), yet bag-only alone recovers ~the full effect = the cleanest "net saw something the heuristic can't" evidence. **QUALIFIERS: this is the OFFLINE scientific lock (Gate A) ONLY** — τ 0.207 ≪ the leaf's 0.895 and α is small (0.05), so it is a weak-but-nonzero *sighted-residual* ranker, NOT a value head that rivals/replaces the leaf. Whether it CONVERTS through MCTS search (Gate B) is **UNTESTED** and is the open Step-2 question; CL-034's bigger −41% offline win WASHED OUT under sims=200 search, so conversion arguably trends against a static-integration win — **Gate B is a de-risk signal, NOT a Step-1 kill (the loop is the arbiter, not a one-shot screen).** **METHODOLOGY/ARCH:** this dense board-CNN got −20.5% but CL-034's cheap explicit-scalar model got −41% ⇒ **Step 2's value head should be STRUCTURE-AWARE** (feature-MLP / set-transformer over the decomposition objects), not a dense CNN. Also logged: a mid-run val-loss preview misread bag as low-signal — the listnet val-loss DIVERGED from the regret gate metric (selection-on-val-loss not monotone with regret); only the final regret/α is the result. **CONTESTS** CL-033's "value head inert as an architecture-independent law" reading but does not supersede the row. **Next active step = Step 2 scoping (structure-aware value head), with Gate B (search conversion) the open question.** No games (offline ranking pilot → no results.csv row). MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED. CL-037; docs `measurement/feature_planes_gate/`; scripts `scripts/feature_planes_gate/`.
- 2026-06-27 (**VALUE/SEARCH CONVERSION AUTOPSY (follow-on to Path-3 decision B) CONCLUDED — decision D (value head INERT) + the headline correction "root metrics DON'T convert to game strength"**; full detail `measurement/value_search_autopsy/VALUE_SEARCH_{RESULTS,DECISION}.md`; branch `rod_v2_flywheel`) — localizes WHERE the learned stack fails. Built a 1321-miss diagnostic set (gap≥0.02 roots where iter04 NMCTS@200 misses h6400) + a 9-leg root intervention matrix (sims/prior/residual/classical/forced-move), local+laptop. **ROOT-LEVEL (the seductive-but-misleading part):** the neural **value is inert** (rs0/rs0.25/rs0.5 indistinguishable; residual never corrupts — 107 wrong→right/0 right→wrong at 1-ply), and on decision states the **policy prior makes WORSE decisions than bare classical search** — full-pool (n=4277) agreement with h6400: **classical h200 0.911 > flat-prior neural 0.867 > production neural 0.799** (monotone; flattening the net's OWN prior gains +6.8pp). 88% of misses are explored-but-misranked (the prior concentrates visits, starving the right move's subtree → wrong backed-up Q); more neural sims overcomes it only slowly (0.350→0.553 at 4×). **GAME-LEVEL (the correction):** the root edge does **NOT convert** — classical h200 vs neural iter04 head-to-head at matched 200-sim compute (n=96 paired, v2.9 leaf) = classical **WR 0.438 / margin −2.6 / paired-z −1.19 = not significant, slight lean to NEURAL**. So the net is **game-NEUTRAL vs classical, not game-harmful**; the decision-state errors wash out because most game positions are low-gap (prior fine + efficient there). **THIRD independent instance** (Path-3 prior-washout, sims-washout, now this) that **root/policy agreement ≠ head-to-head strength → gate strength on GAMES, never on root metrics.** Binding constraint for strength = search depth + a value head that beats the v2.9 leaf (blocker #2, still open, value confirmed inert); prior-tempering DEPRIORITIZED (fixes a non-converting metric); policy distillation stays dead. results.csv `valsearch_m1_classical_h200_vs_neural_iter04_n96`; CL-032; scripts `scripts/rod_v2/value_search/`. MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED.
- 2026-06-26 (**HIGH-CONTRAST DECISION-SIGNAL DISTILLATION (Path 3 = the hard-policy-repair NAMED BOUNDARY) CONCLUDED — decision B: the high-contrast signal EXISTS and is LEARNABLE, but does NOT convert through search to strength; the bottleneck is VALUE/SEARCH, not policy exposure**; full detail `measurement/high_gap_distillation/HIGH_GAP_{RESULTS,DECISION}.md`; branch `rod_v2_flywheel`, commits `cbb40fc`/`edbf514`) — selects 'hard' by h6400 **Q-gap/regret**, not argmax disagreement → **inverts** the prior experiment's null. 20160-root fresh pool labeled h6400_v2.9 across **local+laptop** (sharded; cross-leg Q-gap density matched 36.6% vs 38.0% = no stale-code contamination). **Gate PASS:** gap≥0.02 = **37%**, gap≥0.02∧iter04-wrong = 22%, regret≥0.02 = **43%**, phase-balanced (~20–24% every phase incl. endgame) — vs the prior disagreement-only **3%**. **Stage 5 (held-out hard TEST n=1390 game-disjoint, soft Q-softmax targets temp 0.03, policy-only fine-tune from iter04):** prior top1 **0.000→0.18** (R1), top3 0.30→0.42, mean regret **−27%**, median −42%, strong-gap top1 0→0.27, **endgame 0→0.17** — LEARNS + generalises (where the prior one-hot target did not; the scale-up turned the pilot's ambiguous +8pp into +18pp at 14× test size). Ordinary regression modest (R2 top1 1.0→0.95). **Stage 5b NMCTS@200 = WASHOUT:** iter04's *wrong* prior already searches to top1 **0.497**; R2 also **0.497** (R1 0.453) — the prior gain is **redundant at the root** under production search; only endgame moves (0.483→0.552). **Stage 6 games (R2 vs h6400_v2.9, n=126 paired, local+laptop):** WR **0.409 / elo −64 / paired −11.7**, *below* iter04's 0.463 — **NO conversion, if anything harmful** (the ordinary −5pp regression is NOT washed out in full play). **MECHANISM:** search extracts the decision-relevant move from the existing prior → improving the prior is redundant at depth and the broad-distribution cost outweighs it. **SHARPENS autopsy blocker #2:** the **policy** is NOT the binding learned component (already adequate for search); **value/search** is. **Policy distillation (any target) = DEAD END for RoD strength** (this fails signal-but-redundant; the prior fails no-signal). Named boundary (NOT pursued): value/search lever, or endgame-restricted distillation gated on a game screen. results.csv `highgap_R2_vs_heur6400_v29_n126`; CL-031; lineage `highgap_R2_from_iter04` (NOT_CHAMPION); scripts `scripts/rod_v2/highgap/`. MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED.
- 2026-06-26 (**HARD-POSITION POLICY REPAIR (follow-on to the RoD2 autopsy) CONCLUDED — decision A: explicit h6400-labeled exposure CANNOT repair the policy because the target is SIGNAL-FREE on disagreement states**; full detail `measurement/hard_policy_repair/HARD_POLICY_REPAIR_{RESULTS,DECISION}.md`; branch `rod_v2_flywheel`, commits `319cd98`/`a099073`) — narrow diagnostic test of the autopsy's policy-diffuseness finding. Pilot (1620-pool, no gen): 438 hard (h3200!=h6400 = 27%), split 306/66/66 + 1182 ordinary. **PIVOT:** on disagreement states h6400's visit dist is ~uniform (top-share 0.04) and its Q-values are near-tied at the top (**Q-gap #1-#2 = 0.0021 / median 0.0007 vs 0.040 on agreement states; only 3% have gap>0.02**) → 'h3200!=h6400 disagreement' selects **value-INDIFFERENT** states, not deep-distinctive ones; the argmax is a near-coin-flip. **Stage 3/4 (policy-only fine-tune from iter04):** P1-visit test top1 0.076 ≤ 0.091 baseline (no move); P1-onehot **memorizes train (top1 0.775) but generalizes to 0.061** = full capacity, zero transferable signal — a SIGNAL problem, not capacity/training. **Stage 5:** same nets agree with h6400 3.4× more on agreement states (top1 0.311 vs 0.091) — policy already aligned where the teacher is decisive. **REFRAMES the autopsy:** the 'diffuse policy on disagreement states' signal was a NON-failure (diffuseness is correct on indifferent positions); **downweights** that supporting mode but does **NOT overturn decision C** (blocker #2 / value ceiling untouched). Named boundary (NOT pursued): any future distillation must define 'hard' by h6400 Q-gap, not argmax disagreement. P2/P3/Stage-6 games NOT run. No results.csv row (policy-agreement diagnostic, not elo/wr). MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 UNCHANGED. CL-030; scripts `scripts/rod_v2/repair/`.
- 2026-06-26 (**RoD v2 FLYWHEEL (v2.9 leaf Bmild_cap8) AUTOPSY COMPLETE — CONFIRMED NULL, decision C (stop the AZ-style blind flywheel; classical v2.9 is the strength)**; full detail `measurement/rod_v2_flywheel/autopsy/ROD2_AUTOPSY_REPORT.md`; branch `rod_v2_flywheel`, autopsy commit `9e15e28`) — 5 warm-start self-play iters (RoDv2_iter_02..06, gen+train only) on the frozen v2.9 leaf did NOT restart compounding: every ckpt LOSES to h6400_v2.9 (−22..−32 elo, no climb), ~h3200_v2.9 parity, indistinguishable from RoD1 (adjacent deltas NON-transitive, iter04−RoD1 +6 vs h6400 / −40 vs h3200). **Stage F:** training healthy but TARGET-LIMITED (train_pol & entropy RISING = policy diffusing; value_corr flat ~0.45 = value head inert on a near-zero-range residual target). **Stage D:** self-play merely different not stronger (residual 38–43% within ±0.02 of 0). **Stage E:** fixed-ruler odometer shows no climb; selection-on-adjacent-wins invalid. **Stage A-lite (400 fixed pos, provenance-verified v2.9 rulers):** prior lean toward h6400 ~0 and FLAT across iters; DIFFUSE (77.5% "neither" on h3200≠h6400); endgame agreement collapses 0.10–0.13 — reproduces the v2.8 flywheel autopsy exactly. Strength carried by the v2.9 leaf inside MCTS not the net → blocker #2 stands. Stage B/C NOT run (Stage A confirmed, did not contradict). MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 UNCHANGED. results.csv `rodv2_*_vs_heur*_v29`; lineage `rod_v2_iter_06` (NOT_CHAMPION); CL-029; scripts `scripts/rod_v2/autopsy/`.
- 2026-06-24 (**STRATEGIC-BEHAVIOR LADDER (pseudo-human diagnostic) COMPLETE — 3 of 4 motifs are non-diagnostic; the one credible motif (`farm_claim`) shows RoD_iter_01 plays at HEURISTIC level (compression, not a new capability) with ONE clean deficit: it UNDER-CLAIMS farms vs h6400, concentrated vs WEAK opponents (−16pp) and LATE game — i.e. RoD1 does NOT punish weak opponents; deeper heuristic search buys NO extra strategic behavior**; full detail `measurement/strategic_behavior_ladder/STRATEGIC_BEHAVIOR_LADDER_REPORT.md` + `MOTIF_DEFINITIONS.md` + STATUS; branch `strategic-behavior-ladder`) — Joshua-directed diagnostic to answer whether agents exhibit recognizable higher-level strategic behaviors (block/steal/farm/denial/punish/conversion) now that internal Elo/margin rulers are saturated. **DIAGNOSTIC ONLY — not a promotion benchmark, not a training target; full-game winrate vs `h6400_v2.8` remains the strength arbiter.** Built 4 operational motifs (structural detectors off the flat decomposition, NOT gated on the v2.7 score) over **1,918 labeled positions** / 12 regimes / 9-agent weak→strong panel counterfactually harvested (every agent on every position; agent-unbiased). **RULES FINDING:** in 2p base you cannot place a meeple on an occupied feature → meeple-phase steal/denial is IMPOSSIBLE (fired 0/22 games); contest/denial exist ONLY as a TILES-phase MERGE (`contest_merge`). **RESULTS:** `block`/`avoid_feeding` = NOISE (random ≈ h6400, ~2–6pp spread, flat/negative outcome-sanity → KILL); `contest_merge` = coarse "searches-at-all" STEP (random 18% → all search ~45–49%, saturated above greedy, outcome −11pp → descriptive only); **`farm_claim` = the one credible motif** — discriminates (greedy 12% rule-decline → heuristics 60% → rod1 54% → random 24%) AND predicts winning (**+17pp** in close games, strength-confounded so suggestive-not-causal). **RoD1 deficit (clean, identical positions): `farm_claim` 54% vs h6400 60% (−6pp overall), but −16pp vs WEAK opponents (41 vs 57; EQUAL 53/53 vs strong) and growing LATE (pre_endgame 24 vs 53).** Deeper heuristic search h3200→h6400 buys ~0 extra behavior (all ~60%) — consistent w/ the deeper-search ruler (depth sharpens margin not decisions). Anti-benchmax safeguards WORKED: outcome-sanity killed 3/4 motifs; cross-opponent split exposed the vs-weak-only effect a single score would hide. **VERDICT (TIGHTENED by a follow-up validation audit `VALIDATION_FARMCLAIM.md`):** RoD1 compresses heuristic-level strategic play (NOT random/RPS, NOT super-heuristic). The first pass flagged late/weak-opp farm-claim value as a candidate lever; the **audit downgraded it to STOP** — the headline +17pp was a close-game COLLIDER artifact (honest +11pp → **+5pp** after controlling for pre-move lead + removing the vs-weak ceiling), it is **agent-dependent (rod1's OWN farm claims are outcome-neutral, −2pp)**, and rod1's deficit is **LOW-LEVERAGE** (62% of its farm misses vs h6400 are vs WEAK opponents; top misses at already-won pre-move margins +33…+54 = margin-padding; where farms have leverage — vs strong / even / opening — rod1 ALREADY matches h6400 53/53). **Expected winrate move vs h6400_v2.8 ≈ 0 → NO actionable lever; do NOT run the farm probe; do NOT optimize the benchmark score (3/4 motifs are Goodhart traps; the killed motifs confirmed dead — random≡h6400 on 82%/87% of block/avoid_feeding opps). rod1's real loss to h6400 stays the known endgame PLACEMENT/conversion leak.** **HIGH-PRECISION FOLLOW-UP (2026-06-25, `HIGH_PRECISION_STRATEGIC_TRAPS_REPORT.md`, `scripts/strategic_ladder/strict_motifs.py`, fresh 312 strict positions + 1918-bank relabel): PARTIALLY REVERSES the "block is dead / no lever" — that was PARTLY a DETECTOR-FIDELITY ARTIFACT.** Narrow traps requiring PHYSICAL interference (not arg-min "play elsewhere") DISCRIMINATE: take rate random→h6400 `MUST_PUNISH_WEAK` 15→92 (rod1 84), `HIGH_VALUE_FARM_CLAIM_REFINED` 25→89 (rod1 82), `MUST_BLOCK_CITY` 8→50 (rod1 42, **n=12 thin**); `MUST_NOT_FEED` 77→85 = KILL (no discrimination, forced-feed-dominated). **RoD1 −7/−8pp vs h6400 on IDENTICAL positions with disagreements mostly COMPETITIVE (10/14 punish, 6/7 farm — NOT the broad farm_claim's vs-weak padding).** Pre-move-controlled outcome (no collider): punish take−miss +31pp even-score / +29pp vs-strong — **suggestive but AGENT-CONFOUNDED** (strong agents take+win; control removes leading-state not agent identity). **REVISED VERDICT: the narrowing worked; RoD1 has a REAL but MODEST competitive tactical-punish deficit → ONE gated probe NOW JUSTIFIED** (distil h6400 tactical-punish policy / value-head recal toward immediate ≥8 completions+claims), **GATED on ≥2σ full-game paired winrate vs h6400_v2.8 (n≥400, ≈+24 Elo); else the 8pp wasn't the bottleneck. `MUST_BLOCK_CITY` needs a larger targeted sample before quantifying.** Still DIAGNOSTIC ONLY — no training on labels, PRODUCTION.yaml + champion + v2.7 UNCHANGED. No results.csv row (take-rate diagnostic, not an elo/wr experiment). PRODUCTION.yaml + champion UNCHANGED, v2.7 frozen, v2.8 opt-in. INFRA: laptop again UNUSABLE for detached long jobs (WSL distro tore down despite WSL-KeepAlive — gen died right after the launching ssh closed) → ran local-only; scripts `scripts/strategic_ladder/`.
- 2026-06-24 (**DEEPER-SEARCH RULER PROBE COMPLETE — deeper v2.8 heuristic search is a SHARPER RULER not a stronger match agent; RoD_iter_01 LOSES to h6400 so h6400 is the non-saturated REFERENCE the measurement program needs; deeper search EXHAUSTED as a strength/teacher lever**; full detail `measurement/deeper_search_ruler/DEEPER_SEARCH_RULER_REPORT.md` + STATUS; branch `deeper-search-ruler`, commits `589c925`→ HEAD) — Joshua-directed follow-on to the exact-endgame verdict (which recommended exactly this h6400/h12800 ruler probe). Does deeper heuristic search under the SAME v2.8 leaf (v2.7 + flat `meeple_k=2`) produce a stronger ruler/teacher than `heur@3200_v2.8`? **Part B (verdict-grade, `eval_hybrid_handoff.py` heur@N paired both-seats): h6400 vs h3200 n=400 = winrate 0.539 (z+1.6 NS) but paired score margin +2.49pt z+2.61 SIG** — the exact-endgame pattern reproduced for WHOLE-GAME heuristic depth: sharper score-ruler, NOT a stronger match-winner. **Margin SCALES with depth** (h12800 vs h6400 n=100 SCREEN = +3.87pt z+2.27; its winrate 0.605/z+2.1 is an n=100 SCREEN not a verdict — exceeds the margin-slope, likely small-n overshoot like h6400's early +4→+2.49; deliberately NOT topped to n=400 ~7h). **Part C (carc-orch W20): RoD_iter_01 vs h6400 n=200 = winrate 0.435, paired margin −4.41pt z−3.24 SIG = RoD1 LOSES** — it only reached h3200 parity; the deeper ruler erodes it (root agreement looked equidistant but agreement≠strength: RoD1's ~48% disagreements cost more vs the deeper, more-often-right opponent; margin transitivity holds). **Part D (1620-position multi-phase root audit): deeper search changes ~29% of root moves but only ~10% are a STABLE deeper preference (matched ~1:1 by ~10% pure noise), endgame/pre_endgame-weighted; heuristic visit distributions stay near-uniform even at h12800 (top_share 0.05→0.08, no rich policy target — rod1 0.27); RoD1 equidistant from all depths.** **Part E: all disagreements are tile-PLACEMENT (suite is TILES-phase roots), 95.5% positionally-equivalent on immediate turn-score → h6400's margin = better POSITIONING that compounds over ~144 moves, NOT blunder-recovery (h3200 leaves a completion only 1.3%).** **Part F: distillation EV LOW** (no rich policy target, outcome-neutral signal, net adopts the deep move only 19%, and distilling the ruler caps the net AT the heuristic = the v2.7/v2.8-leaf blocker). **VERDICT (Part G): deeper heuristic search EXHAUSTED as a strength lever — both "search-deeper-under-v2.8" endpoints (exact endgame + deeper whole-game heuristic) land on the SAME margin-not-winrate ceiling; the v2.8 leaf dominates move CHOICE, more search refines SCORE not WINS; blocker #2 stands (learned must beat the heuristic on WINRATE not margin). ONE constructive output: ADOPT h6400 as the non-saturated measurement REFERENCE for future learned-agent gates (RoD1 saturated h3200 yet loses to h6400); h12800 only if the sharpest score discriminator is needed (2×/4× cost).** MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion UNCHANGED, v2.7 frozen, v2.8 opt-in. INFRA: laptop UNUSABLE for long jobs (WSL distro tears down <8min after the launching ssh ends; 4 detach methods all failed — `setsid&`/bg-ssh/tmux/`start /b`) → ran local-only (faster per-game for h12800 anyway). results.csv `deepsearch_{h6400_vs_h3200,h12800_vs_h6400,rod1_vs_h6400}_v28_*`; scripts `scripts/deeper_search/`.
- 2026-06-23 (**RoD v2.8 OVERNIGHT FLYWHEEL + TAIL EVAL COMPLETE — the chain plateaus at heuristic PARITY; the extension (iters 11–17) does NOT beat keep-best iter_08; NOT superhuman**; full detail `measurement/rod_v28_overnight_flywheel/EVAL_RESULTS.md` + `OVERNIGHT_STATUS.md` + STATUS; branch `rod_v28_overnight_flywheel`, flywheel commits `85bda88`→`a668cf6`, this-session infra+close-out `5c80aa4`→ HEAD) — Joshua-directed dedicated larger v2.8 flywheel (the "test COMPOUNDING past parity" follow-on the RoD probe recommended), latest-chain warm-from **RoD_iter_01**, **16 continuation iters RoD_iter_02→iter_17** (v2.8 leaf `meeple_k=2`, batch 256 / 3 ep / VLW 1.5 / sims 200 / 400 games·iter, gen W28/8), all HEALTHY no-collapse, all checkpoints retained; STOPPED early at iter_17 (target was 30). **EVAL (net-vs-net, same v2.8 leaf, deck-paired, NeuralMCTS@200):** iters 02–10 → **keep-best iter_08 = +33.1 elo / paired_z +2.00 vs RoD_iter_01 (n=400)**, vs **`heur@3200_v2.8` = TIE at n=800** (+6.5 wr / −0.38 paired) = reaches deep-heuristic PARITY, does NOT exceed; iter_10 endpoint +21.7/z0.69 ~tie; gain NON-monotonic (the n=100 screens overstated throughout — iter_10's +77.7 screen → +21.7 at n400). **TAIL EVAL (iters 11–17 + early 02/03, after-the-fact):** vs RoD1 n100 screens iter_11 +96.2 / iter_17 +41.9 / iter_13 +17.4 / iter_02 +20.9 / iter_15 +3.5 / iter_03 −3.5 — BUT the decisive **vs keep-best iter_08 head-to-heads** show **NO tail iter beats it**: iter_11 (strongest-vs-RoD1) **LOSES −56.1 / z−1.80** (its +96 was non-transitive noise), iter_13 ties (−13.9/z+0.56), iter_17 ties (+13.9/z−0.74), and the **n=384 top-up of the best contender iter_17 vs iter_08 = +6.3 / paired_z −0.16 = TIE at verdict power** (40-min harness timeout clipped from 400). **VERDICT: the whole chain (early/middle/best/endpoint/tail) hovers at RoD1/heuristic level; iter_08 is the lone 2σ-over-RoD1 point and the keep-best, sitting at heur@3200 parity without crossing it — blocker #2 (learned must EXCEED the heuristic) stands.** MEASUREMENT ONLY — no promotion, **PRODUCTION.yaml + champion (`flywheel2_champion_iter8`) UNCHANGED, v2.7 frozen, v2.8 opt-in.** results.csv `rod_ov_*_n100` / `rod_ov_iter08_vs_rod1_v28_n400` / `…_vs_heur3200_v28_n800` / `rod_ov_iter17_vs_iter08_v28_n384`; harnesses `scripts/rod_v28/{run_overnight_evals,run_screens_vs_base,run_heur_eval}.sh`. **INFRA (this session, separate commits):** (a) **SSH cd-drop = a known Claude Code failure mode** — the model silently omits `cd /path &&` from SSH Bash-tool commands at *generation* (over-applies the "avoid cd" Bash-tool guidance to remote SSH; proven not-external via a plain non-ssh echo that drops the phrase too); CLAUDE.md "Remote command rule" + the PreToolUse cd-hook now mandate & allow **path-stable forms** (`git -C`, absolute paths, `--manifest-path`, wrapper scripts) instead of an inline cd. (b) **2-box work-stealing diagnosed** — the "laptop drops out / truncated screens" was a MISREAD: work-stealing distributes correctly (32/68 laptop/local split on iter17, all games played), the laptop never faulted (no OOM/crash — clean-tally early exits); the n=72/80 clips were a **premature-tally race** in the shared-claim path (`v28_net_vs_net_orch.py` — each box does a one-shot pickup + writes `result.json` when *its own* imap pass ends, with NO completion barrier for the peer's in-flight claimed games) compounded by cross-box CIFS→drvfs file-visibility lag; the data always reached full n on re-tally. **FIX PENDING (no speed-ratio prediction):** keep work-stealing, add a drain-to-completion barrier (re-map remaining until all-N json) + lower `--claim-stale-secs` 5400→~180s so a genuine mid-game death self-heals within a screen.
- 2026-06-23 (**BATCH-512 CALIBRATION COMPLETE — KEEP BATCH 256: batch 512 in the RoD v2.8 recipe TIES B256 head-to-head but FAILS the parent gate + under-trains the policy; 1.31× speedup not worth it**; full detail `measurement/rod_batch512_calibration/BATCH512_CALIBRATION_REPORT.md` + STATUS; branch `rod_batch512_calibration`, commits `12558b6`→`ba766ea`) — Joshua-directed recipe-calibration probe: can batch **512** replace **256** in the RoD v2.8 continuation recipe (speed motive: the RoD A/B/C measured 512 ≈ 1.29×/epoch faster) WITHOUT weakening the net? Clean controlled experiment — trained `ROD_ITER1_B512_TEST` from the **same frozen iter8 parent** on the **same 1000-game v2.8 self-play data** (dataset fp `61a12d76` IDENTICAL to B256, REUSED not re-gen), `--batch-size 512` the ONLY change (same lr 1e-3 / seed 0 / 3 epochs / leaf / arch; batch treated as a scientific variable per DECISIONS 2026-06-10 "bigger batch = different net"). B512 sha `9cca3edf`, warm-from iter8 `0d355002`. **SPEED: 1.31× wall-clock** (58.2 vs 76.3 min, 3-epoch) but **HALF the optimizer steps** (12,099 vs 24,196). **TRAINING: no collapse (entropy 1.5393) but the POLICY head is UNDER-FIT** — val_pol plateaus at 0.435 vs B256's 0.270 (+61%), stable across all 3 epochs (halved step count at fixed LR; not an epochs deficit); value head unaffected (corr +0.4115). **vs FROZEN parent (net-vs-net, carc-orch SHM work-stealing local W48 + laptop W16, same v2.8 leaf, deck-paired band 1.922e9 = SAME decks as B256-vs-parent): B512 = +10.4 elo / paired z1.65, n=400 — INCONCLUSIVE** (does NOT credibly beat the parent; B256 was +53.4/z3.51 on the SAME decks). **vs B256 DIRECT (THE decider, fresh band 1.923e9): B512 = −1.7 elo / paired z−0.41, n=400 — TIE** (point est −6.9 n200 → −1.7 n400) — **the val_pol under-fit WASHED OUT under MCTS@200** (policy precision ≠ play strength). **NON-TRANSITIVITY (a real ~41-elo result): transitivity predicted −43 (from the +10.4/+53.4 parent margins) but the direct head-to-head is −1.7** — B512 ties validated B256 yet lost B256's specific edge over the parent; corroborates "parent-relative Elo is a non-transitive proxy for sibling strength." **ROOT AUDIT (1000 v2.8 midgame pos, `BATCH_ROOT_AUDIT.md`): B512 plays 0.737 like B256** (MORE than either vs parent 0.65/0.68) = a *less-converged version of the SAME policy*, not degraded; heur3200 agreement flat (Δ+0.010); no entropy collapse; divergence concentrated in the endgame. **INTERPRETATION / VERDICT: KEEP BATCH 256.** B512 is strength-neutral head-to-head but (a) fails the parent gate (the defining RoD-positive result), (b) under-trains the policy, (c) is untested vs the heur ruler where B256 reached parity (non-transitivity risk) — NOT validated as a drop-in; the modest 1.31× speedup is dominated by a safe lever (2-epoch batch-256 ≈ 1.5× at zero risk; val loss flat by epoch 2). A properly LR-rescaled batch-512 is the only future-worth path (a labeled speed variant that must clear the parent gate — NOT this naive same-LR swap). **MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion (`flywheel2_champion_iter8`) UNCHANGED, v2.7 frozen, v2.8 opt-in.** results.csv `b512_vs_iter8_v28_n400` / `b512_vs_b256_v28_n400`; lineage `rod_iter_01_b512` (NOT_CHAMPION).
- 2026-06-22 (**RoD v2.8 CONTINUATION PROBE COMPLETE — RoD POSITIVE: one continuation iter under the v2.8 leaf BEATS the frozen iter8+v2.8 parent (+53.4/z3.51) and CLOSES the equal-leaf gap to deep heuristic search (parent −38.4 → RoD TIE @n800) = PARITY, NOT exceeded; NOT superhuman**; full detail `measurement/rod_v28_continuation/ROD_V28_CONTINUATION_REPORT.md` + STATUS; branch `rod_v28_continuation_probe`, commits `dbdd4b3`→`c73b58a`) — Joshua-directed small continuation probe ("Revenge of Demis"): does the stronger **v2.8 leaf** (= v2.7 + `meeple_k=2`, the heuristic-v28 survivor) restart self-play improvement BEYOND the frozen `iter8` that the v2.7 substrate had pinned (every v2.7 continuation — deeper-teacher, residual-flywheel plateau — was a powered null)? Recipe held = attempt#2 (warm-from iter8, residual_scale 0.25, sims=200, value_target residual, VLW 1.5, batch256/3ep); the ONLY substrate change = `CARCASSONNE_V25_MEEPLE_K=2.0` in the self-play worker env (legacy LeafConfig field → flat fast path, `_v28_active` stays False; **verified it reaches the MCTS SEARCH leaf** via `run_selfplay_iter.py:354` `replace(DEFAULT_CONFIG,…)` → the visit-count policy targets are genuinely v2.8-guided; **NO code change; v2.7 bit-identical** — reproduction gate `scripts/rod_v28/verify_iter8_v28_parent.py` passed). 1000 v2.8 self-play games (local+laptop carc-orch, 0 failed, 2.12M pos) → `RoD_iter_01` (sha `a8b824df`, warm-from iter8 `0d355002` verified unchanged). **BINDING (net-vs-net, NEW two-server harness `scripts/heuristic_v28/v28_net_vs_net_orch.{py,sh}` — one carc-orch per checkpoint, same v2.8 leaf both sides, deck-paired band 1.922e9): RoD_iter_01 vs frozen `iter8+v2.8` = +53.4 elo, paired z=3.51, n=400** (pilot +70.4/z2.91 regressed) — **RoD POSITIVE, the FIRST continuation to beat its parent.** **RULER (RoD vs `heur@3200_v28`, n=800): TIE** — winrate elo +16.5/z1.34 but paired score margin −0.36/z−0.47 → RoD **CLOSED the equal-leaf gap** (parent `iter8+v2.8` was −38.4 vs the same ruler, row `iter8_v28_vs_heur3200_v28_n200`) to **PARITY**, does NOT exceed deep search (transitivity holds: −38.4+53.4=+15 predicted, +16.5 measured ⇒ the parent-beating is a REAL strength gain, NOT non-transitive). **ROOT AUDIT (1000 midgame pos under v2.8, `ROOT_AUDIT_V28.md`): the +53 is GENUINE POLICY RESHAPING, NOT teacher-imitation** — RoD root-move agreement with heur@3200_v28 = 0.511 vs parent 0.520 (Δ−0.009 ≈0); ~35% of iter8's root moves changed but net agreement with the ruler is flat; phase-dependent (MORE heuristic-aligned in endgame where the meeple term bites, LESS in opening). **INTERPRETATION: the v2.7 leaf WAS a real ceiling (blocker #2) — v2.8 unstuck a continuation gain v2.7 could NOT produce — BUT the DEEPER blocker (learned EXCEEDING the heuristic) is UNRESOLVED: RoD only reached PARITY.** Raising the leaf raised the floor to the heuristic's level, not above it. **NOT superhuman** (hand-crafted leaf, no human/external anchor — still the binding measurement gate). Side: batch A/B/C speed (throwaway, prod unchanged) 256/512/1024 = 1.00/1.29/1.46×/epoch (diminishing; latency-bound only at batch 256; bigger batch = systematically different/less-converged net per DECISIONS 2026-06-10). **MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion (`flywheel2_champion_iter8`) UNCHANGED, v2.7 frozen, v2.8 opt-in.** results.csv `rod_iter01_v28_vs_iter8_v28_n400` / `rod_iter01_v28_vs_heur3200_v28_n800`; lineage `rod_iter_01` (NOT_CHAMPION). **NEXT (recommended): a dedicated larger v2.8 flywheel (branch `rod_v28_flywheel`, warm-from RoD_iter_01) to test COMPOUNDING past parity** (one iter2 too noisy to resolve it); secondary distillation-from-heur@3200_v28; the **external/human anchor** remains the unaddressed superhuman gate.
- 2026-06-21 (**MIDGAME REFERENCE PROBE COMPLETE: no midgame tool/action-ranker case either — the pre-tool audit's blind spot now measured**; full detail `measurement/midgame_reference/MIDGAME_REFERENCE_REPORT.md` + STATUS; commit `2b24831`) — Joshua-directed follow-on to the pre-tool audit (the corrected `f84eb01`, which re-ran `b4c552c` on scoring-resolved afterstates after finding the per-action deltas were read one half-move pre-scoring). The audit named the **opening/midgame as its blind spot** (raw quantities vary there; no exact-solver labels) and recommended this probe BEFORE any tool-coding. Built a **1000-position midgame sample** — 250 each greedy/heur@3200/hybrid:8:3200/iter8 self-play; 200 each in tiles-remaining bands K=52/40/28/16/10 — by replaying `l23_k4_expand` full-game prefixes to earlier plies (free, all 4 source distributions, no MCTS at gen time). REUSED the corrected scoring-resolved afterstate logic verbatim (no pre-scoring bug) + added bag-aware features from `flat_leaf.decompose` and the v2.7 leaf's own `_deck_city_supply`/`_supply_factor`. **No exact solver at midgame K** → references kept distinct, NONE ground truth: deep-search TEACHER heur@800/1600/3200 (one incremental same-seed tree: first-800-sims-of-3200 == an independent heur@800), iter8 MCTS@200 + policy prior, v2.7-static. All search descends the real fixed deck (clairvoyant-leaning; weaker leakage than endgame, intractable to marginalize). **Verdict — do NOT start the tool branch (same pattern as endgame, sharper):** (1) static **v2.7 explains the deep teacher** — Kendall τ **+0.61** (90% informative), offline diagnostic ranker **0.453** top-1 WITH v2.7 vs **0.147** without (v2.7 std-coef **0.594**, every raw/bag coef ≤0.013); (2) raw deltas **sparse** (~22–36%, τ ~0.22–0.30) — **NOT** more informative than the endgame (refutes the audit's hoped-for midgame variance gain for raw deltas); (3) the **bag-aware/structural features vary a LOT** (open-edge/scarcity 55–62% of positions) **but carry ~zero teacher-aligned signal** (τ **+0.01**) and recover only **~2–6%** of v2.7/iter8 disagreements — a variance trap; (4) where v2.7 errs the fix is **deeper SEARCH** (iter8 recovers ~30% of v2.7 misses; heur@800 recovers ~47% of iter8 misses), not a cheap feature; (5) **90% of disagreement cases are structural/positional** (mirrors the endgame ~82 structural/7 completion). iter8's edge over v2.7 is small, search-mediated, **front-loaded in the opening** (0.61 vs 0.485) and **inverts by pre-endgame** (0.39 vs 0.515) — reproduces CL-027. **The weak gate fails in BOTH regimes now (endgame where tools look worst + midgame where the audit expected them best).** Measurement only — no train/flywheel/promotion; champion stays iter8. Scripts `scripts/midgame_reference/{build_midgame_sample,compute_midgame_features,label_midgame,analyze_midgame}.py`.
- 2026-06-21 (**L2 K=4 ENDGAME REGRET COMPLETE: iter8 plays the K=4 endgame WORST overall (top-1 0.561 vs heur@3200 0.679) — replicates CL-025 K2/K3 deeper; the pilot's source-split was n=12 NOISE**; full detail `measurement/level2/LEVEL2_K4_PROBE_VERDICT.md` + `K4_PROBE_RESULTS.json` + STATUS) — Joshua-directed expansion of L2-3 from K=2 to K=4 via an EXACT alpha-beta clairvoyant solver (`endgame_solver.py`, gated 0-mismatch vs the no-prune oracle on K2/K3). Balanced multi-source suite: 200 positions, 50 each from greedy/iter8/heur@3200/hybrid:8:3200 self-play (action-replay reconstruction, bit-exact). **187 solved (94%) @1M-node budget; 13 genuine budget-hits (greedy 7, heur 2, hybrid 2, iter8 2) = correct selection-bias data, NOT failures.** top-1 overall: heur@3200 0.679 > heur@800 0.652 > greedy 0.647 > iter8 0.561 (WORST), mean regret iter8 1.48 vs heur@3200 1.07. **The multi-source control DISENTANGLED the pilot's dramatic 0.92-own/0.36-greedy split as n=12 NOISE** → real effect 0.65-own/0.44-greedy (same direction): TWO compounding effects, each ~2-3× smaller — (1) iter8 REACHES easier endgames (iter8-source within1=28.5 near-opt moves / randReg1.1 vs greedy within1=7 / randReg1.9), AND (2) iter8 still handles SHARP/OOD endgames WORST (0.44 greedy-source vs 0.58-0.60; 0.40 on sharp gap≥2, regret 3.34). heur@3200 GENERALIZES best across sources (0.58-0.73); iter8 most variable. Measurement backing for the hybrid-handoff (CL-026). **Engineering this round:** COMPACT blake2b-128 TT key (`6f9dd08`, bit-identical 12/12 incl node counts) — but the HONEST memory lesson is monsters reach ~10.6GB driven by TRANSIENT deepcopy churn in `get_next_state` (the TT is only ~0.04GB of a ~4.9GB solve), so compact keys bought only ~1.5×; **make/unmake (incremental apply/undo, no deepcopy) is the real lever** + the prerequisite for marginalized labels & K=5 (deferred, BACKLOG; ~3-5 day project, helps the solver family only — NOT production MCTS). Local W dropped 5→3 mid-run after an OOM-warn (W=5×~11GB > 42GB). **CL-027.** Measurement gate only — no train/promote; champion stays iter8. Marginalized K=4 + K=5 feasibility PENDING (gated on make/unmake).
- 2026-06-19 (**L2-3 ENDGAME REGRET (K=2): iter8 plays the endgame WORST — endgame-optimality DECOUPLED from full-game Elo**; full detail `measurement/level2/LEVEL2_L23_VERDICT.md` + STATUS) — Joshua-directed ("go for endgame regret" + detailed spec). Built the program's FIRST NON-circular measurement: an EXACT minimax (clairvoyant)/expectiminimax (bag-marginalized) solver over the final K tiles → ground-truth optimal moves (kills the clairvoyant-label circularity of L1/L2). Brute-force validated (V-brute==reference, V9 value-realized, V2 K1 clair==marg; 9 tests). Suite: 150 greedy-self-play positions/K, band 3.2e9, full provenance. **K=2 result (150 pos, top-1 vs exact optimum, decision positions): heur@3200 0.837 = heur_v1@200 0.837 > heur@1600 0.780 > greedy/heur@800 0.759 > iter8 0.667 (WORST).** ⇒ (1) the full-game Elo champion iter8 is the LEAST precise endgame technician; (2) the weakest full-game agent (v1) ties the best → **endgame-optimality is DECOUPLED from full-game Elo** (kept SEPARATE per Joshua #7); (3) deeper heur search monotonically helps endgame; (4) blunders rare/small (iter8 bidirectional — also optimal where heurs blunder). Hypothesis: iter8's full-game-value policy underweights the last-tile score-squeeze. **Tractability: engine 1.7ms/node deepcopy caps EXACT solving at K=2** (K≥3 needs minutes; make/unmake solver → K=3-6 is future work). **K=3 partial (68 decision pos, clairvoyant): iter8 WORST again (top-1 0.574) → the deficit is DEPTH-ROBUST.** ⚠️ the K=3 run at **W=20 OOM-crashed the 5800x WSL** (solver TTs + heur@3200 trees + nets > 42GB) — 74/150 saved on the share, VM restarted, session reconnected, 0 work lost; memory-bound solver runs need **W≤8-10** (banked `feedback_worker_count_by_bottleneck`). **Joshua #8 — same-band (3.10e9) iter8-vs-heur@3200 DONE: −28.7 elo, 180W/7D/213L=45.9% wr, paired z=−0.70 (tie on margin; winrate z~−1.65).** Completes the MONOTONE same-band ladder **iter8 vs h800 +40.1 / h1600 +24.4 / h3200 −28.7** — iter8's full-game edge shrinks with heur depth and is ERASED by the deepest heuristic (results.csv `l22_iter8_vs_heur3200_b310_n400`; Elo, separate from regret per #7). **Convergence: heur@3200 is BOTH the most endgame-precise (L2-3) AND the heuristic that catches iter8 full-game (#8) — deep search wins on both axes.** **CL-025** (regret) + **CL-024** (same-band ladder extended w/ h3200). Measurement gate only — no train/promote. (Optional: complete K=3 to 150 at W≤8.)
- 2026-06-19 (**L2-2 DONE: iter8 beats BOTH validated rungs but the scale is NON-TRANSITIVE → same-band control running**; full detail `measurement/level2/LEVEL2_L22_VERDICT.md` + STATUS "Right now") — Phase L2-2: re-ground frozen champion iter8 on the *validated* L1 ladder, NEURAL ⇒ via the **carc-orch SHM eval server, both boxes** (5800x OW48 + laptop OW16/24, shared-claim, CY_REPR; eval_orch.sh; smoke validated parity+timing first). **iter8 vs heur@800 (R4): +40.1/z2.29** (V6 reproduce of published +72.2 / sealed +58.7 — within ~1σ band-variation; apparatus+orch path sound; the n=24 smoke's −29 was small-n noise). **iter8 vs heur@1600 (R5): +34.9/z2.0** — iter8 beats the DEEPER rung too, ~same margin (BETTER than predicted; I expected iter8<heur@1600). **⚠️ NON-TRANSITIVE:** compose with CL-023 (heur@1600>heur@800 +55.2) ⇒ transitivity predicts iter8<heur@1600 by ~15, but iter8 WINS by +35 = ~50elo intransitivity. Either real rock-paper-scissors (cf. CL-016; ⇒ elo not a valid single strength axis — central caveat for the measurement program) or band-variance (3 different bands; iter8 swings ±30/band per CL-018). **NOT decidable from different-band data → same-band transitivity control (band 3.10e9: iter8-vs-h1600 + h1600-vs-h800, n=400 each on shared decks) RESOLVED = BAND-VARIANCE: on band 3.10 iter8-vs-h800 +40.1, iter8-vs-h1600 +24.4, h1600-vs-h800 +20.0 → transitive (40.1−20.0=+20.1 pred vs +24.4 meas). The elo ladder IS a valid total order; the ~50elo "non-transitivity" was cross-band artifact (h1600-vs-h800 swung +55 b3.04 → +20 b3.10, but z≈3.2 both → CL-023 replicates). LESSON: cross-band elo composition unreliable ±30-35; only same-band paired comparisons compose.** **CL-024.** Measurement gate only — no train/promote/redesign/modify-iter8. (Overnight autonomous; Joshua's "keep going, keep using both boxes".)
- 2026-06-18 (**L2-1 LADDER DONE: ruler NOT saturated — DEPTH (not leaf-design) moves the heuristic ruler; NEXT = L2-2 iter8-vs-validated-ladder on orch**; full detail `measurement/level2/LEVEL2_LADDER_VERDICT.md` + `LADDER_RESULTS.json` + STATUS "Right now") — Level-2 §8.3 saturated-ruler gate. Pure-CPU adjacent-rung matrix (n=200 paired each, fresh bands 3.0e9+, heur rungs at the **production c=1.5** [eval gate's `--c-puct` hits the NET side only; the HeuristicMCTS opponent has always run at the 1.5 default → the ladder's R4 IS the established ruler] + v2.7-env, per-rung leaf-provenance verified; harness `scripts/ladder_rung_eval.py`). **R1vR0** greedy/random +800/z55.6 ✅, **R2vR1** v1@200/greedy +26.1/z1.87 ⚠, **R3vR2** v2.7@200/v1@200 +24.4/z1.68 ⚠, **R4vR3** v2.7@800/@200 +75.9/z3.59 ✅, **R5vR4 (SATURATION GATE)** v2.7@1600/@800 **+55.2/z3.23 ✅ (n=400, topped up from n=200 +70.4/z2.23 per the pre-registered [1.5,2.5] escalation; z strengthened with n).** Findings: (1) **saturation REFUTED** — deeper plain heur search beats the heur@800 production ruler ⇒ the elo scale has real headroom above it (a stronger, cheap, out-of-lineage reference exists by just spending search); (2) **depth, not leaf-quality, drives resolvable heur strength** — the mid-rungs (greedy↔v1@200↔v2.7@200) are compressed ~+25 elo/z1.7, only the depth rungs separate cleanly (refines the old `heurdepth_*` "≈0" read, which used a FIXED-NET opponent; pure heur-vs-heur differs); (3) ladder monotone-in-ordering, no inverted step (no harness bug). **CL-023.** Pure-CPU ⇒ no orchestrator (correct — no net to batch); **L2-2 IS neural ⇒ run on the carc-orch SHM server at high W** (memory `feedback_use_orch_for_eval_and_gen`). Follow-on R5'@3200-vs-@1600 RUNNING (does depth-headroom continue?). **Measurement gate only — no train/promote/redesign/modify-iter8.** Infra side-win: pretooluse hook now blocks the recurring `ssh host '<repo-cmd>'`-with-no-cd slip (`edc44a9`).
- 2026-06-18 (**CLAIRVOYANCE-GAP MEASURED = small (~27 elo, not ≥100) → numbers transfer to honest play; NEXT = Level-2 ladder**; full detail `measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md` + STATUS "Right now") — First measurement-first experiment (the spec §7 belief-changer). **Step 0** sentinel confirmed production search is deck-order clairvoyant (root value moved 8/8 when only the unseen deck order changed). **Gap** (fresh band 2.7e9, paired, vs heur@800-v2.7, both arms production `best_action`): CLAIR(clairvoyant) **+66.8** [reproduces published +72.2 = harness valid] vs NONCLAIR(K=12 root-determinization, best_action pooled) **+40.3** @ n=182 → paired gap **+26.6 elo z=−0.9** (V1 monotonic; ≤30 minor-contributor gate; ~2σ excludes ≥100). ⟹ clairvoyance is NOT a decision-changing inflation; clairvoyant numbers ~transfer; the non-clairvoyant agent is NOT mandatory for Level 2 → go straight to the saturated-ruler ladder. **CL-022.** Method note: the interim read caught a visit-argmax-vs-`best_action` aggregation bug (~105 elo at sims200/c3.0; clair fixed +70.4 = published, commit `f7ebec3`); harness gained a carc-orch `--shm-eval-server` path (`ad9ad03`) + standing rule (memory `feedback_use_orch_for_eval_and_gen`: default eval+gen to orch+highW). Stopped nonclair at n=182 (Joshua's call; gap stable). Champion unchanged (iter8).
- 2026-06-18 (**VALUE-RANKING KILL-TEST CLOSED = swing DISFAVORED → PIVOT to measurement-first**; full detail `value_ranking/VALUE_RANKING_VERDICT.md` + STATUS "Right now") — The structural value-head lever (the other fork from the deepteacher policy lever) tested + killed. Arms (leakage-safe by-game split, 1494 nodes, held-out Kendall-τ vs deep oracle): A conv+MSE −0.004 / B conv+rank +0.029 / **C attn+rank (THE SWING) +0.012** / C0 conv-wide (capacity-match) +0.015 / E advantage +0.014 — vs **v2.7 leaf 0.579**. **Architecture C-vs-C0 = z−0.12 (NO effect); ranking-loss B-vs-A = z1.63 (weak).** 4A ceiling: target reliably rankable (oracle self-consistent; v2.7 extracts 0.58) ⇒ all arms fail while labels reliable = **learned-ranking formulations DISFAVORED, not probe-limited** (prod net on millions also ranks 0.081 ≪ 0.58 → scale isn't the unlock). **CL-021.** **Both strength levers (policy-teacher + value-head) now exhausted → PIVOT to measurement-first** (spec `docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md`: 3 levels minimal/robust/ideal; first belief-changing experiment = the **clairvoyance gap**, clairvoyant vs non-clairvoyant iter8 paired, NOT yet run). Champion stays iter8. Infra side-win: cd-proof `scripts/sync_box.sh` sync wrapper (deployed laptop).
- 2026-06-17 (PM-3 — **DEEPTEACHER CLOSED: clean iter8-vs-iter12 = TIE both planes**; provenance defect found; full detail STATUS "Right now" + `deepteacher_audit/`) — Audit (Joshua's 5-phase order-of-ops): (1) provenance — deepteacher warm-started from **iter8** (hash-verified chain) but its sealed/washout "iter0" baseline was **residual.pt, not iter8** → the "+8.1 tie"/"+82.8 washout" are vs residual, never vs the warm-from; (2) clean re-measure (FRESH band 2.5e9, n=400 paired): iter12 vs iter8 = **+14.6/z0.65 @s200, +12.4/z0.51 @s800 = TIE**. Deeper-teacher hypothesis = **powered-null at the deep plane**; champion **stays iter8**; iter12 NOT promoted. The "iter2 +53.7 over iter8" was band-favorable noise. New claims CL-019 (deeper-teacher tie), CL-020 (baseline defect). NEXT = value-ranking kill-test. **⚠️ CORRECTS the 2026-06-17 "deepteacher SEALED = WASHOUT not plateau" line below — that washout was iter12-vs-residual, not vs iter8.**
- 2026-06-17 (PM-2 — ORCH-IN-EVAL CONFIRMED + DEPLOYED to the flywheel + cython folded into eval + XEON RETIRED; full detail STATUS "Right now") — confirmed & shipped the 2.24× find below. **Full W-sweep (moves/s, net@800 heur@800, `scripts/ab_orch_eval.sh`, committed `4dc52b6`):** 5800x off W14=**1.95** → orch climbs and **plateaus ~9.3–9.4 from W48** (W40 8.92 / W48 9.25 / W52 9.30 / W56 9.37 / W60 9.39; GPU finally the bottleneck, fwd_busy 32→59%); laptop off→orch climbs to **W28=7.85 but RAM-bound** (0GB avail on the 11GB box; W32 stopped to avoid OOM-wedge) → prod **W26** (2.4GB headroom). **Cython A/B (CARCASSONNE_USE_CY_REPR=1, env-inherits through `eval_orch.sh`/`ab_orch_eval.sh`'s `env $LEAFENV`):** 5800x W48 9.25→**9.78 (+5.7%)**, laptop W26 7.49→**8.04 (+7.3%)** — pure worker-CPU win (fwd_busy unchanged), converts ~directly while the orch eval workers are CPU-bound. **Net: 5800x eval 1.95→9.78 = 5.0×; laptop →8.04.** Eval = 64% of cycle ⟹ **~2× whole-cycle.** **DECISION — DEPLOYED:** `_eval_launch` in `run_residual_flywheel_v2.sh` routes 5800x (W48) + laptop (W26) through `scripts/eval_orch.sh` (TS export → carc-orch → `--shm-eval-server` client → trap-clean), both with `CY_REPR=1` added to `eval_orch.sh`'s LEAFENV; `EVAL_W`=48/26/12. `_eval_launch` is the single chokepoint (covers the keep-best odometer @289/290, sealed @316/317, telemetry gate @231/304). **Smoke PASS** at production knobs (net@200 heur@800 W48: server ready, CY_REPR active in workers, 48 workers, 41 games, no errors; `bash -n` clean both scripts). **✅ PRODUCTION-SIMS NUMBER (net@200 heur@800 A/B, 2026-06-17):** off W14=**8.24** → orch W48=**28.79 (3.49×)** → +cython=**30.32 (3.68× total = production eval speedup)**; cython +5.3%. Smaller than the net@800 5.0× **as predicted** (at net@200 the net is hit ~4× less/move → off baseline far higher, 8.24 vs 1.95 → less context-thrash to collapse); fwd_busy 46–48% at W48 confirms eval-W headroom. Orch wins at every sims plane; **3.68× is the production eval multiple** (the 5.0× was a net@800 upper bound). **Why gen-W (≈28) ≠ eval-W (≈48):** in gen every MCTS node hits the net (high per-worker GPU demand → orch saturates ~W28); in eval the heuristic opponent runs pure-CPU v2.7 MCTS at heur@800 (a CPU sink), so per-worker GPU demand is far lower → the orch server stays underfed (fwd_busy ≤59%) → packs ~2× more workers — expected, not anomalous. **XEON RETIRED (`USE_XEON=0` default):** its weight collapsed once 5800x+laptop got orch+cython eval (it stayed orch-off — Quadro flaky) and it was the #1 cluster-friction source; costs ~10–15% aggregate (mostly gen-side); `USE_XEON=1` re-enlists. (Joshua locked W48 + full-retire via two decisions.) Commits: `4dc52b6` (harness+gitignore) + this deploy.
- 2026-06-17 (PM — CLUSTER orch+cython DEPLOY + 🔥 ORCH-IN-EVAL ≈2.24×; full detail STATUS "Right now" + memory `reference_carc_orch_verdict`) — **(A) GEN deploy:** laptop SWITCHED to **orch W8** @sims800 (sweep orch W8=24/W12=24 games vs off W12=18 = 1.33x; W8 = best throughput at peak_mem 9.1GB vs the 11.9GB RAM ceiling W12+ hit) + **`CY_REPR=1` on the orch GEN path** (5800x py3.12 + laptop py3.14 `.so` built+reconciled 0-mism). Xeon kept **orch-off W10** (orch tentative ~2x but flaky: stall + server-fail; warm positions/s proxy `orch_throughput_sweep.sh`). Commits `cec4237`/`125f96d`/`59c125f`. **(B) 🔥 ORCH-IN-EVAL = 2.24× on the 5800x** (matched W14: orch 4.7 vs off 2.1 moves/s; `fwd_busy=18%` = server idle = headroom for higher W). **REVERSES the 2026-06-16 'orch eval = tie' conclusion below — that tie was XEON-only (CPU-leaf-bound); the 5800x eval is net-GPU-CONTEXT-THRASH-bound** (orch-off runs N separate net CUDA contexts; orch = 1 shared). **Eval = 64% of cycle ⟹ ~35% cycle reduction** — the biggest lever found this session, and the gen-side wins (orch 1.4×, cython +7%) only touched the 15% gen. Confirm + higher-W sweep RUNNING (`scripts/ab_orch_eval.sh`, moves/s via `CARC_BENCH_TP`). IF confirmed → wire eval→orch (client already built, commit 9068640) + add `CY_REPR=1` (free ~+3-5%, only the net player encodes). **Lesson: don't generalize a per-box bottleneck (xeon CPU-leaf-bound) to other boxes — the regime differs (the recurring theme); the 5800x/laptop eval is GPU-context-bound where orch wins big.** ⚠️ n=1, confirm in flight.
- 2026-06-17 (deepteacher SEALED = WASHOUT not plateau + PERF FOLDS banked + value-head pivot; full detail STATUS "Right now" + memories `feedback_sims_washout_net_eval`/`reference_training_latency_bound`/`reference_laptop_cluster_access`) — deepteacher (iters 10-12) finished. **SEALED cumulative (iter12 vs iter0, n=400 paired, held-out band 1.7e9, heur@800-v2.7): deck-paired Δ = +8.1 elo, z=0.34 = TIE at agent sims=800** (iter0 already +135 vs heur; the +143 iter12 was INHERITED). Conditionally did NOT launch iters 13-16 (bar Δ≥90/z≥3). **WASHOUT CONFIRMED (re-eval at agent sims=200, SAME decks): Δ(iter12−iter0) = +82.8, z=3.48 = SIGNIFICANT** (iter12 +74.1, iter0 −8.7 reproducing its old −8.69 to the decimal). ⟹ **the net GENUINELY improved (> old attempt2 +67), but the gain is POLICY which deep search washes out — so the sims=800 selection gate was BLIND the whole run (the per-iter "ties" were measurement, not plateau).** **DECISION: not a strength dead-end-by-failure but by WRONG-COMPONENT — for superhuman (deep play) the lever stays a VALUE head that beats the v2.7 leaf (helps at depth, unlike policy); warm future runs from iter12 (strongest net: +74@s200 > prod iter8 +58.75); gate policy at sims=200 (cheap + not-blind), value work at sims=800.** **PERF FOLDS banked** (between-runs boundary): Cython flat-leaf (`f48ffd1`, default-ON + graceful fallback) + O(1) window-offset (`62d3772`), bit-exact-reconciled on all 3 boxes → ~1.5× heur search / ~1.3× cycle (the 2026-06-12 FOLD-WORTHY pair). **NEXT Cython target landed (`1b55721`): `encode_board` → `flat_repr_cy.encode_board_cy`** — after the leaf was ported, encode_board was the largest pure-Python hot-path cost (~15% self/~25% cum); port (per-tile identity cache + `is`-dispatch zero-hash + array union-find + memoryview + `placed_coords` walk) is **bit-exact** (`reconcile_repr_cy.py` 28,988 encodes 0-mism; `tests/test_flat_repr_cy.py`), behind `CARCASSONNE_USE_CY_REPR` (DEFAULT OFF; redirect at the single call site → all prod paths incl orch-worker). A/B **18.25× isolated / 1.275× (−21.6%) single-process end-to-end**. ⚠️ **Production W=14 orch-off A/B (5800x, same-seed 42 games) = NULL: 9.96→10.08 g/min = 1.012× (noise)** — both arms loadavg ~14 but GPU ~82W/90% (~45% board power) = GPU-dispatch-latency-bound, so the encode CPU win doesn't convert orch-off (the 1.275× single-process was real only because 1 worker leaves the GPU idle). Same kills the eval gate (96% net-GPU @s800). **STAYS DEFAULT-OFF — validated zero-risk tool;** carc-orch IS where it pays — **TESTED 2026-06-17 (5800x, warm examples/s A/B at fixed W28, sims=800): cy ON = 1.07× (+7%) over OFF (4899→5241 ex/s, fwd_busy 85→96%)** — the orchestrator leaves server headroom (85%, not pinned) so faster worker-side encode feeds it harder. So REGIME-DEPENDENT (NULL orch-off W14 GPU-dispatch-bound; +7% orch W28). n=1/arm + gen~15% of cycle ⟹ ~+1% net cycle = real+positive but small, doesn't touch strength. STAYS default-OFF; a flip pays only on the 5800x orch gen path (per-box `.so` + CY_REPR=1). Measurement note: sims=800 W28 completed-game windows are intractable (~13min/game → 20-min window completes ~0) — used the warm examples/s proxy (`scripts/ab_orch_cy_repr_tput.sh`). Lesson → memory `feedback_profile_the_production_path`. **#4 TCC-test SKIPPED** (xeon has no native-Windows Python + TCC breaks WSL CUDA; informational). **Session infra:** heal-thrash FIXED (`73d5150`+`4ac840e`: false-stall window, SIGKILL-scoped reap, timeout-ssh, rc124=launched-no-retry), laptop recovered (S3-sleep via hidden lid-close → power fixed + autologin), **WSL-tax RESOLVED — native-Windows == WSL same 5060 Ti (2.62 vs 2.51ms B=1) = Windows WDDM+torch launch NOT WSL; native-Windows port dead, only OS escape = native Linux.** Commits `1b0485a`/`aae8c31` (verdict) → `62d3772`/`f48ffd1` (folds) → `1b55721` (encode-cy port, default-OFF).
- 2026-06-16 (pm — ORCH-IN-EVAL built + xeon eval-W characterized + xeon FOLDED into the flywheel; full detail STATUS "Right now" + memory `reference_carc_orch_verdict`) — executed the two post-compact decisions from the AM entry below, plus a full eval-W study. **(1) ORCH-IN-EVAL BUILT** — `eval_net_vs_heuristic.py --shm-eval-server` (spawn Pool + worker-id queue → `connect_shm` → `make_remote_single_evaluator`, same v2.7+residual wrapper) + wrapper `scripts/eval_orch.sh`; orch-off path byte-identical. **Verified PARITY_OK** (6/6 games bit-identical orch vs orch-off at matched seeds; TorchScript export parity 1e-9/2e-7). Commit **9068640**. **(2) Xeon eval-W characterized** (game-counts, production leaf, `--heur-leaf v2_7`): orch-off peaks at **W=12** (=12 threads) at BOTH sims=200 and 800, thrash beyond — **CPU-thread-bound** (the v2.7 CPU leaf runs on BOTH the net AND the HeuristicMCTS sides). **orch@W12@800 TIES orch-off** (0.72 g/min both) at **~30% lower CPU load** (8.5 vs 12.1 — orch offloads the net-side forwards to the server). **⇒ xeon eval = orch-OFF W12**; orch doesn't raise throughput on this CPU-bound box (heur-side leaf caps both), and its capacity lever (W>12) isn't worth wiring orch-eval into the flywheel for one box. The matched-W tie also makes the xeon eval a WEAK WSL-latency probe (CPU-bound) → the clean probe is the laptop (`scripts/bench_forward_latency.py`, commit **5cb58f1**, forward-latency vs batch-size: flat ⇒ launch/`/dev/dxg`-tax-bound). **(3) `EVAL_W_<box>` decouple knob** (commit **c8d712e**): eval-W decoupled from gen-W in `run_residual_flywheel_v2.sh` (`EVAL_W_5800X/LAPTOP/XEON`, default per-box gen-W, xeon=12); eval-W=12 > gen-W=10 (modest gain). **(4) XEON FOLDED IN.** Found the deepteacher run (AM entry) had **hung 6h on iter12's selection** (best=iter10; **iter11 REJECTED** Δ−2.0/z−0.06; 2 zombie mains + orphans). Cleaned all 3 boxes + stranded claims, relaunched the resume with `USE_XEON=1` + `TELEMETRY_GATE=0` (the discredited telemetry gate heal-caps ~1h/iter at sims=800). **Laptop went DOWN** mid-cleanup (WSL :2222 AND Windows ssh both unreachable — real box-down) → resume runs on **5800x+xeon**. **PENDING: the SEALED cumulative** (iter12 vs iter0, n=400 held-out) — the verdict for "did 10→12 grow?" — decides extend(START=13)-vs-stop; do NOT extend on the noisy per-iter promotions alone. Commits `9068640`→`c8d712e`.
- 2026-06-16 (CLEAN GAME-COUNT MATRIX → cluster re-wired → FLYWHEEL RESUMED — full detail STATUS "Right now" + memory `reference_carc_orch_verdict`) — Q (Joshua): the per-box orch verdicts rested on uneven/forward-rate evidence; "start over cleanly, done systematically." **The forward-rate (examples/s) proxy proved UNRELIABLE** — it claimed orch wins on the laptop while game-counts said TIE (it over-rewards orch's high W: those workers inflate forwards but thrash RAM without completing more games). Built an opt-in **per-worker throughput counter** (`CARC_THROUGHPUT_LOG`, `da4621d`, zero-cost when off) for a clean forward-rate, but it has a synchronized-start game-cycle oscillation → reverted to **GAME-COUNTS (ground truth)** on all 3 boxes ×{200,800}×{orch,off}, long windows (`scripts/parse_gamecount.py`, harness `laptop_orch_ab.sh`): **5800x orch ~1.4x** (corroborated by 2 methods+2 sims, z~1.2-1.3 → keep orch W28), **laptop TIE → orch-off W10**, **xeon TIE** (@800 orch W12=12 vs off W10=10, z=0.43, GPU only 36% busy = CPU-leaf-bound → orch-off W10). Gaps 1.0-1.4x; gen=~15% of cycle. **⇒ the xeon's deployed "1.40x" (a forward-rate number) is NOT confirmed by games.** **CLUSTER RE-WIRED** (`run_residual_flywheel_v2.sh`): rebuilt-laptop support (`laptop-wsl` ssh + `/home/doctor` path — was dead `/home/pop`) + `USE_XEON` gate (`4adaed9`), xeon hardcoded orch-off W10 (`d3a19e6`). **FLYWHEEL RESUMED** 2026-06-16 (Joshua's GO: "continue the iters") — deepteacher iters 10→12, 5800x orch W28 + laptop orch-off W10, xeon EXCLUDED (was benching). **iter10 ✅ PROMOTED: Δ+84.0/z=2.17 over iter9 (first ≥2σ promotion — compounding NOT plateaued); best=iter10.** iter11 in selection. **DECIDED (post-compact): (1) fold xeon in at the iter11→12 boundary** (USE_XEON=1, orch-off W10); **(2) build orch-in-eval** (eval=~64% of cycle, the higher-leverage win — `eval_net_vs_heuristic.py` needs orchestrator support added + parity test + a restart). Commits `da4621d`→`d3a19e6`.
- 2026-06-15 (carc-orch DEPLOYED to XEON + cluster torch standardized — full detail STATUS "carc-orch" block + memory `reference_carc_orch_verdict`) — after the local 1.33x win, extended the orchestrator to **xeon**: copied the binary (same torch 2.11/cu128 → no rebuild; streams bind on Turing, export parity bit-exact). **A/B via a forward-rate probe** (sims-800 games take >12min on the slow Turing → 0 complete in a 720s window, game-counting impractical): orch server `examples/s` scales **2150 (W10, GPU 37% busy) → 2650 (W14) → 3000 (W18, 85%)** = **≥1.40x over orch-off's VRAM-capped W10** (lower bound; orch-W10 ≥ orch-off-W10 via batching). xeon's Turing is GPU-STARVED at W10 (idle 63%) with idle CPU = SAME winning condition as local; NB the bottleneck FLIPS with sims (CPU-bound at 200, GPU-bound at 800). gen_flywheel.sh gate now allows HOST=xeon (per-host W default: 5800x=28, xeon=18); run_residual passes USE_ORCH to the xeon gen launch; end-to-end smoke clean (code-sync→export→server→SHM self-play→4 games). **Production bundle `carc_stage-b-wiring.bundle` regenerated to the deploy HEAD** (it was stale at 110e38d → a resume would revert remotes to pre-carc-orch code). Also **standardized cluster torch to 2.11.0/cu128**: laptop was drifted to 2.12.0/cu130, downgraded via offline cp311 wheels staged on the share (laptop has no internet), pinned in requirements.txt. Laptop stays orch-off (no Rust binary copied yet, but torch now matches → feasible). Commits `f6f99a3`→`b8bc488`. Flywheel still PARKED at iter10 (resume = Joshua's GO; xeon auto-orchestrates via USE_ORCH=1).
- 2026-06-15 (carc-orch CUDA-streams gambit — full detail STATUS "carc-orch" block + memory `reference_carc_orch_verdict`) — Q (Joshua): reverse the orch-shelve, "make it fast enough to deploy." **Built per-forwarder CUDA streams** (`c10_cuda` C++ shim — tch 0.24 has no stream API; `rust/carc-orch/csrc/cuda_stream_shim.cpp` + `build.rs`, CXX11_ABI=1, CUDA headers from triton's tree) **→ REVERSES the prior orch-off-wins verdict: stream-SHM W28 = 56 games/360s BEATS orch-off W14 = 42 (1.33x, confirmed n=2 on independent seeds, lower power).** Mechanism: orch-off caps at W14 (per-process context VRAM ceiling); the orchestrator runs **W28 on ONE shared context** + streams keep it fed — the prior "CPU-leaf-bound → can't win" read MISSED the W28-vs-W14 worker asymmetry (without streams the default stream serialized → couldn't feed 28 → old 28-35, lost). **W-sweep:** peak W18-28 (~1.33-1.37x, noisy plateau), W≥32 degrades (CPU v2.7-leaf oversubscribes 32 threads), W48 breaks. **SQUEEZE EXHAUSTED — all 3 server-side levers neutral/worse:** cuDNN benchmark (~7% early, drifts + parity risk → reverted), more-forwarders FWD=8 (ex/s capped ~5700), **H2D double-buffer pipeline 0.94x WORSE** (killed by a cheap Python probe `scripts/probe_pipeline.py` BEFORE the ~1-2hr Rust rewrite — the cost-discipline cheap-first pattern). **1.33x is the ceiling** (server has spare capacity; the per-worker CPU v2.7 leaf is the bottleneck — no server-side opt moves games). **DEPLOYED local-only (`d5d8b8e`, Joshua's call):** stall watchdog (`--watchdog-secs`, wedge = jobs-in/no-batches-out → exit(2) loud → flywheel heal-loop restart; verified no false-fire) + `gen_flywheel.sh` orchestrator branch (HOST=5800x + `USE_ORCH=1`: export→TorchScript parity-gated BIT-IDENTICAL→carc-orch→SHM self-play, result-identical priors; smoke-tested 10 games clean) + `run_residual_flywheel_v2.sh` passes `USE_ORCH`/`ORCH_WORKERS` to the LOCAL gen only; STATUS resume recipe now prefixes `USE_ORCH=1`. **xeon/laptop DEFERRED** (no Rust/g++; laptop torch 2.12≠local 2.11 — xeon has same torch → binary could be copied if more gen throughput wanted). NB tch DOES have `pin_memory` (an earlier session note was wrong). Commits `cd949ee`→`708ef84`. No training; flywheel still PARKED at iter10 (resume = Joshua's GO; orchestrator auto-activates via the recipe).
- 2026-06-12 (pm — throughput-rewrite investigation; full detail BACKLOG "2026-06-12 (pm)" + STATUS top block) — Q (Joshua): "is our code slow / would Cython/Rust help?" → 3 **isolated-worktree** spikes, all **bit-exact validated, OFF/branch-only, NONE folded**. **(a) Cython leaf** (branch `worktree-agent-a1588…`/`dd893e4`, flag `CARCASSONNE_USE_CY_LEAF`): 12.5× isolated; leaf=27% of heur@800 search (py-spy) → ~1.33× search — **FOLD-WORTHY**. **(b) Window-offset incremental** (branch `worktree-agent-aedf22…`/`775a8c0`): O(1) centroid, 4.27×/call, 12.3% of search → ~1.10× search — **FOLD-WORTHY**. **(c) Engine de-objectification** (branch `worktree-agent-a659ae…`/`6050ecd`): cheap-hash coords/sides = **NULL** (~0.9% Amdahl, 0.993 ratio, bit-exact 17,270 plies); full array-rewrite caps ~1.3–1.6× / multi-week → **SHELVED**. **Net: leaf+offset ≈ 1.5× eval search ≈ ~1.3× cycle → fold BOTH at a supervised boundary, skip de-objectify.** **Methodology: profile with py-spy NOT cProfile** — cProfile distorted the map (OVERstated primitive tax 37%→16%, UNDERstated window-offset 8.6%→12.3%); memory `feedback_cprofile_overstates_hot_functions`. **VERDICT: NO throughput rewrite touches STRENGTH** (the v2.7-leaf ceiling / superhuman goal is untouched; gen/train are GPU-latency-bound so throughput isn't even the binding constraint). Flywheel (UPDATE 2026-06-14): iters 3,4,5 REJECTED (plateau vs iter2) then **iters 6,7,8 ALL PROMOTED** (lineage iter2→6→7→8, best=iter8) — the "no compounding" read at iter5 was PREMATURE; climb resumed (each Δ marginal z~1.2; SEALED champion-vs-iter0 verdict pending). Extend-to-12 (chain watcher) vindicated. On iter9, ~Mon AM.
- 2026-06-11/12 (index-only summary; full narrative in STATUS + results.csv) — **(a) iter8 FOLDED TO PRODUCTION** (`governance/PRODUCTION.yaml`, anchor-checked +67.4/z2.73 vs incumbent on the sealed heur@800 ruler; CL-005 closed Supported). **(b) DEEPER-TEACHER CONFIRMED REAL:** gen-SIMS 200→800 warm-from-iter8 → iter1 NULL, **iter2 +53.7/z2.14 over iter8** (n=400 paired, fresh band 1.3e9; `confirm_iter2_vs_heur800_v27_s800_n400`) — the earlier "deep search does not distill" read RETRACTED; flywheel RESUMED `START=3` (iters 3→6, warm-from iter2) to test compounding → **iter3 REJECTED (−81.0/z=−2.36)**, iter4 in flight. Still a within-v2.7-leaf policy-distillation gain, NOT a ceiling break. **(c) Xeon flap root-caused** = WSL2 idle VM-teardown → self-healing held-ssh keepalive (`scripts/xeon/xeon_keepalive_loop.sh`); `networkingMode=mirrored` ASSESSED → **SKIP** (removes only the portproxy, not the root cause). **(d) compact-leaf numba bench KILLED** (microbench: `_label_components` = 4.7% of build self-time; see BACKLOG 2026-06-09 entry). **(e) replay-window history recorded** (BACKLOG 2026-06-11): `--window` ran live for all 13 pathb_loop iters, deliberately collapsed in selection-gated flywheels; never A/B'd in isolation.
- 2026-06-10 (pm-3, symmetry-aug A/B RESULT + training-throughput finding) — **NULL: `--augment-rotations` does NOT make a stronger net → shelved.** The pm-2 A/B finished (verdict 23:23). aug_off (1× control) vs aug_on (4× rotated data = 4× gradient steps), both warm-from iter5 on iter8 gen + iter8 recipe, evaluated **n=400 paired vs heur@800-v2.7** (band 2.0e9, scale 0.25): **aug_off +53.4 / aug_on +44.5 → paired EFFECT = −8.9 elo, z=−0.38 = NULL** (slightly negative, within noise; the ±~23 elo paired bar rules out any gain >~+37, can't exclude a small <+15). **SANITY** aug_off vs decomp `sb_iter8_s025` = −19.9 / z=−0.61 → reproduces iter8 within noise = control valid, null trustworthy. **Interpretation:** the net already effectively encodes the 4-fold rotational symmetry, so teaching it via 4× augmented data adds nothing — and the extra 4× gradient steps don't help either, so the pm-2 "4×-steps confound → run matched-steps to disentangle" follow-up is **moot** (turning the flag on as-is simply isn't worth the 4× train cost). **Decision: do NOT fold symmetry aug into production; shelve** (`tests/test_symmetry_aug.py` + the `--augment-rotations` path stay; flag stays OFF). Symmetry was always throughput/prep, never a plateau-breaker → the deeper-teacher experiment (attack the policy) is unaffected and remains the ceiling lever. **Also recorded — GPU-latency-bound training finding (measured):** `train_iter.py` on the 7M net is bottlenecked by per-batch kernel-launch + `.item()` CUDA-sync round-trip *latency*, NOT CPU/workers (idle behind a full prefetch queue) nor GPU compute. Decisive bench: the laptop (i7-14650HX, **1.5× faster** single-thread) trained **~10% SLOWER** than the 5900XT (0.216 vs 0.196 s/batch) — its power-capped mobile 4070m has higher launch latency. ⟹ don't CPU-shop training boxes; more workers / uncompressed npz don't help; the only throughput levers are **(a) one-sync-per-epoch** (accumulate losses on-GPU; strength-neutral, free) and **(b) bigger batch** (strength-affecting via effective-LR → its own mini-A/B w/ LR rescale before trusting; note it only speeds the ~21% train slice of the deeper-teacher cycle, eval is ~64%). Memory `reference_training_latency_bound`. `results.csv: symaug_aug_{off,on}_vs_heur800_v27_n400`; `symaug_ab/eval/SYMAUG_VERDICT.txt`.
- 2026-06-10 (pm-2) — **Speedup triage + symmetry-aug A/B launched, ahead of the deeper-teacher experiment.** Another thread surfaced two loop speedups; verified both. **(1) Symmetry augmentation** (`--augment-rotations`, 4× rotated training data) was **built + tested 2026-06-02** (C5; `tests/test_symmetry_aug.py`, 16 tests) and left **OFF with NO kill decision** (BACKLOG: "to USE pass `--augment-rotations` at the Stage-B retrain" — never switched on, never A/B'd; just queued behind everything). **(2) Async flywheel loop** (`docs/ASYNC_FLYWHEEL_DESIGN_2026-06-10.md`): measured phase split gen 15% / train 21% / **eval 64%** (the in-loop heur@800 selection); async packing + two eval-cost cuts (don't re-play the champion each iter; SPRT-style accumulate-until-significant — NOT naive peek-until-p<0.05, which inflates FPs the project has been bitten by) ≈ 2× iter-rate. **Framing (mine, Joshua agreed): both are throughput multipliers, NOT plateau-breakers** — the policy plateaus on TEACHER quality, so faster iters reach the same ceiling faster; their value is making the (more expensive) deeper-teacher run affordable. **Decisions (Joshua):** fold iter8 to production first → then a single-lever deeper-teacher experiment; settle speedups before that experiment; **async ON HOLD pending the 5800x VRM fix** (needs trustworthy per-box W-throughput; symmetry does NOT — it's a relative A/B where throttling only slows training, can't bias the winner) → **symmetry A/B first.** **Symmetry A/B (running):** aug-ON (5800x, 4× data) vs aug-OFF (laptop), both warm-from iter5 on `iter8_data`, iter8's recipe, 3 epochs, only the flag differs; readout = h2h aug-on-vs-aug-off (net@200, deployed v2.7+0.25·Δ leaf, paired n=400) + sanity aug-off-vs-iter8 (~tie validates reproduction + controls the GPU confound). Tests "turn the flag on as-is" (4× steps included), not symmetry-in-isolation; a matched-steps follow-up (aug-off @12 epochs) disentangles if it wins. **⚠️ OOM bug found (first-ever end-to-end run of `--augment-rotations`):** the in-loader augment (`warmstart.py:608`) 4×-`np.concatenate`s each file INSIDE every DataLoader worker → at `--num-workers 12` it OOM-killed the 5800x (and at 2 workers GPU-starved at 1% — the per-row yield of 4× rows can't feed the GPU); the 16 unit tests cover the transform, not the loader memory model. **Fix:** pre-materialize the 4× data to disk once (`augment_with_rotations`+`GameDataset.save` → `symaug_ab/iter8_data_aug4x/`, validated 4.00×), then train via the normal path (no `--augment-rotations`); aug-ON now runs this on the 5800x, GPU 94–96%, no OOM. For production symmetry use: pre-materialize per-iter or make the streaming augment memory-bounded (rotate per-row, not whole-file concatenate). Live handles in STATUS (watcher `bguaorc5g`, `/tmp/run_symaug_h2h.sh`).
- 2026-06-10 (Track-B flywheel attempt #2 CONCLUDED — SIGNIFICANT but BOUNDED) — **The residual flywheel produced a real, properly-powered cumulative gain, then plateaued; stopped at iter10 on Joshua's call.** Run `flywheel_residual_attempt2` (12 iters planned, external keep-best on heur@800-v2.7 paired, flat leaf from iter5). **Trajectory:** champion lineage iter0→2→4→5→8; per-iter external Δ(new−best): iter1 −17.5✗ · iter2 +32.1✅ · iter3 −19.9✗ · iter4 +31.8✅ · iter5 +43.6✅ · iter6 −33.2✗ · iter7 −21.0✗ · iter8 +3.6✅(noise, margin0) · iter9 −28.2✗ · iter10 −46.2✗. So a **clean 3-promotion climb iter0→5, then a 5-iter plateau (iter6–10 all within ~1.5σ of iter5, trending mildly down)**. **SEALED HEADLINE (held-out band 1.7e9, n=400 paired heur@800-v2.7, champion iter8 vs iter0): +67.4 elo / z=2.73 = SIGNIFICANT** (iter0 −8.7 / iter8 +58.7 vs the heuristic). Clears the charter's cum-≥+45 bar; **strongest pro-compounding evidence the project has produced**, well above attempt #1's null (+14.3 cum) and better-powered than the mid-run 5v0 (+40.6/z1.26). **Two honest caveats:** (1) **BOUNDED** — the gain was banked by iter5 and saturated; this is real *bounded* compounding, NOT open-ended self-improvement toward superhuman. **(⚠️ MECHANISM CORRECTION 2026-06-10 pm, external review — my first writeup of this entry was wrong):** I attributed the plateau to "the value head stopped bootstrapping (flat corr) + the tanh-cap." Both are WITHDRAWN: the tanh-cap is **falsified by my own S-R3-1 scan** (2.6M targets, std 0.071, 0% with |Δ|>1, saturation 0.013% of MSE → clip/linear-head would do nothing), and the flat ~0.49 corr is **residual-vs-residual (mislabeled, not value-vs-outcome)** and can't identify the cause anyway. **The plateau cause is UNIDENTIFIED**; v2.7-anchoring is a live-but-untested hypothesis → resolve via a plateau decomposition before choosing any lever. (2) iter0's absolute vs heur swings by deck band (−8.7 sealed / +22.6 5v0 / +52.5 attempt#1) so this band drew iter0 low; deck-pairing is internally valid but the **honest cumulative gain is ~+40 to +67** (5v0 & sealed bracket it), both real, sealed says significant. **Decision: skip iters 11–12** (plateau clear → ~zero info) **but run the pre-registered sealed on iter8 anyway** (the deliverable, doesn't need the remaining iters). **Claim recording (dual, per external review — don't bury a real result under the unmet grand version):** **CL-011** (strict = *sustained monotonic* compounding) stays **Provisional/not-met** (it plateaued). **NEW CL-018** = "residual-guided self-play yields bounded multi-generation compounding on held-out eval" = **Supported** (sealed n=400 +67.4/z2.73, corroborating 5v0 +40.6, gain accumulated over ~5 gens then saturated). `results.csv: flywheel2_SEALED_{iter0,champ_iter8}_vs_heur800_v27_n400` + `flywheel2_cum_*` (5v0); `flywheel_residual_attempt2/{SEALED_VERDICT.txt,selection.csv}`. **Next:** (a) bank the win — promote iter8, freeze lineage/manifests/sealed panel, update baseline, don't reuse the sealed decks for lever-selection; (b) **plateau decomposition** (eval-only, across iter0/3/5/8/10) to find which ceiling binds — policy absorbed residual / residual stopped improving / both saturated at the heuristic / the ruler became the constraint — **THEN** pick a lever (NOT the falsified tanh fix). **→ DECOMP RESULT (2026-06-10 pm, Stages A+B, eval-only; [docs/PLATEAU_DECOMP_2026-06-10.md](docs/PLATEAU_DECOMP_2026-06-10.md)): the gain is the POLICY.** Stage A (sibling-ranking probe iter0/5/8): raw value head ranks at chance (τ≈0) at every checkpoint, never improves → locally inert. Stage B (policy-only scale0 vs residual-on scale0.25, band 2.0e9 n=200): policy-only climbs iter0 +10.4 → iter5 +52.5 → iter8 +54.3; full lineage gain iter0→8 = +46.4, of which **+43.9 is policy and only +2.5 residual**; residual marginal is a flat static ~+22 (non-growing). Policy gains +42 by iter5 then +1.8 → **the policy plateaus at iter5 = the flywheel plateau.** ⟹ **CL-011's residual-COMPOUNDS mechanism is REFUTED** (the residual is a static additive; what compounded was the policy, then saturated); CL-018 stays Supported but is **reattributed to policy distillation**. Stage C (ruler test) not needed. **Ceiling lever = attack the POLICY** (stronger/deeper self-play teacher — deepsearch +35.8 precedent — opening/deck diversity, stronger gen-time search); value-head/residual tweaks are dead ends. `results.csv: stageB_decomp_*`.
- 2026-06-10 (5v0 cumulative anchor) — **Added a mid-run champion-vs-iter0 cumulative check (Joshua, after asking "why aren't we testing this each iter").** The per-iter selection Δ is *new vs the PREVIOUS champion on a rotating band* → those marginal steps do NOT compose into cumulative-vs-iter0 (cross-band deck variance swamps absolute elos), so the marginal chain **cannot distinguish genuine compounding from non-transitive (RPS) churn**, and we had zero direct evidence iter5 > iter0. 5v0 = iter5 vs iter0, paired heur@800-v2.7, fresh band 1.5e9, n=200 → `Δelo(iter5−iter0)`. Why not every iter automatically: cost + the sealed 1.7e9/n=400 at iter12 stays the unbiased final word. **Logistics constraint discovered:** 5v0 and the flywheel **can't co-locate on any box** — the 5900XT is DRAM-bandwidth-bound, so train + heur@800 eval throttle each other to a crawl (38 s/game → 10+ min; epoch 10→18 min), and the laptop's 8 GB GPU OOMs hosting both; the agent net is too heavy for laptop CPU. ⇒ run 5v0 only while the flywheel is **paused** (burst at the iter7→iter8 boundary). Parked at 71/200; burst script `/tmp/run_5v0_burst.sh`. **→ RESULT (2026-06-10 01:17, flywheel paused at iter7→8, local W14 + laptop W20 contention-free):** iter0 **+22.6** elo (z0.89) · iter5 **+63.2** elo (z2.85) · **deck-paired Δ(iter5−iter0) = +40.6 elo / z1.26 / 100 decks = PARTIAL compounding.** Middle of the pre-registered bands (compounding ~+80–100; RPS ~0–30): the marginal chain (iter2 +32 · iter4 +32 · iter5 +43 ≈ +107 if additive) **transferred ~+40 cumulative (~40% of the naive sum)** → a **real directional gain, NOT pure RPS churn**, but with substantial non-transitivity and underpowered at n=100 (paired z1.26 = directional, not significant). The champion is genuinely stronger than iter0 (iter5 clears the heuristic at z2.85, iter0 only z0.89). Read alongside iter6 + iter7 BOTH rejecting vs iter5 → **real gains through iter5, now plateauing**; the sealed n=400 at iter12 is the unbiased final word. `results.csv: flywheel2_cum_iter{0,5}_vs_heur800_v27_n200`. (Aside: iter0 +22.6 here vs the attempt-#1 odometer's +52.5 same-net/opp/band — ~1.2σ at n=200; the deck-paired Δ controls for it.) Flywheel resumed at iter8 immediately after (warm from iter5).
- 2026-06-09 (leaf-deploy) — **Flat leaf turned ON mid-attempt-2 (iter5 selection onward), Joshua's call ("deploy now, resume iter5").** Merged `leaf-rewrite`→`stage-b-wiring` (`ea70fbf`, default-OFF inert), flag `CARCASSONNE_USE_FLAT_LEAF=1` in `gen_flywheel.sh:28` (gen) + `run_residual_flywheel_v2.sh:40` ENVV (eval), commit `1682797`; remotes bundle-synced. **Why safe mid-run:** bit-exactness independently re-verified before deploy (fresh-seed reconcile 0 mismatches; pytest green; production-redirect probe 20/20 fired, value-diff 0) → the iter1–4 (naive) ↔ iter5+ (flat) chain stays comparable; the only change is canonical-fsum semantics (~7e-5 of evals ±1, within existing cross-process FP noise). **Why now vs next-experiment:** the run was paused and needed a restart regardless, so the cross-box ~+8% on the remaining ~7 iters is ~free (the runbook's own "<1.3× → defer" tree was overridden by the zero-disruption restart). `USE_COMPACT_LEAF` stays OFF. Runbook: docs/FLAT_LEAF_BENCH_DEPLOY_RUNBOOK_2026-06-09.md; switch point logged in STATUS.
- 2026-06-09 (leaf) — **Compact flat-union-find leaf rewrite (branch `leaf-rewrite`, default OFF): LOGIC-EXACT (0 mismatches over 935k farm + 580k city partition + 14.4k score + 28.8k base-value checks), and it surfaced a PRE-EXISTING leaf nondeterminism — the v2.7 closure bonus sums non-associative floats in hash-seed-dependent SET order, so the same position gets different `virtual_score_v2` ints across workers in ~1e-4 of evals (±1 pt; 2 flips in one process, 12 in another; ULP-scale ≈1e-15 reorder tipping banker's rounding at exact-.5).** Added `CANONICAL_BONUS_SUM` (math.fsum, default OFF) → 0 flips, true bit-exact AND deterministic. Compact is NOT yet a measured speedup (pure-Python core; the deferred numba/Cython Phase-4 bench was subsequently **KILLED 2026-06-11** — microbench showed the compilable core is only ~4.7% of build self-time; see BACKLOG 2026-06-09 entry — and the compact approach itself was superseded by the deployed flat leaf, entry above). Gate `scripts/reconcile_compact_leaf.py`; see [docs/COMPACT_LEAF_REWRITE_ASBUILT_2026-06-09.md](docs/COMPACT_LEAF_REWRITE_ASBUILT_2026-06-09.md). Full entry below.
- 2026-06-09 — **CPU upgrade (5800X→5900XT, 16C/32T): self-play is RAM-BANDWIDTH-bound, NOT core/thermal/OOM-bound → W≈16 optimum UNCHANGED; the extra 8 cores give ~0 for self-play (same dual-channel DDR4 bus as the 5800X).** Trigger: CPU swap + suspected VRM thermal throttling → worker sweep (Joshua's 14/24/30, refined to a full W=1..30 scan). **Root cause of "no gain over the 5800X": memory bandwidth, directly demonstrated** (tooling committed; run dirs `/mnt/c/carc-shared/wsweep_thermal`): **(1)** per-worker self-play throughput erodes *smoothly* from W=4 — 100/99/84/66/43/37/34% of the W=1 rate at W=1/2/4/8/14/16/18 — a shared-resource signature, NOT a core-count cliff (a core limit would hold ~100% to 16 then drop). **(2)** a pure-memory microbench (`scripts/bw_scaling.py`) saturates at just **2–4 threads ≈ 40 GB/s** and *degrades* to ~24–28 GB/s under many threads (Zen3 2-CCD→shared-IOD arbitration penalty); the DDR5 laptop holds ~53 GB/s flat by contrast. **(3)** a clean in-cache SIMD bench (`bw_fpu.py`) scales **+40% from 16→32 threads** — so the CORES have headroom; the wall is the DRAM bus, not the cores or SMT. **(4)** effective clock (Windows `\Processor Information % Processor Performance`, the only throttle gauge reachable from WSL — no IMC/uncore counters, no temp sensors under Hyper-V) **held 117–133% (~3.9–4.4 GHz) across every run including sustained back-to-back load → NO VRM throttling** (a hot VRM that doesn't drop the clock costs 0 throughput; throttle ≡ clock drop, which never happened). **(5)** swap stayed flat except W≥28 (per-worker ≈ **0.9 GB**, background/MCP ≈ 10 GB, 36 GB cap; W=30 overshoots → swaps ~2 GB). **Cross-box natural experiment (decisive):** the DDR5 laptop (i7-14650HX, **same 16 cores**, DDR5-4800 dual ≈ **1.9× usable BW at load**) peaks at **W=20 > its core count**, vs the 5900XT's W=16 = core count → **peak-W tracks bandwidth-per-core, not cores.** So the 5900XT ≈ the 5800X for self-play (both dual-channel DDR4-3200); no AM4 CPU swap could move it (reconciles Joshua's "5800X SMT helped at W=14": on 8 cores the same ~40 GB/s left headroom for SMT workers; on 16 cores it's already saturated at W=16). **Config fix:** `.wslconfig` was STALE from the 5800X era (`processors=16`, `memory=32GB`) → bumped to `processors=32`, `memory=36GB` (host has **48 GB** physical; `memory=` is a ceiling not a reservation [verified: `vmmemWSL` held ~8 GB of the 32 cap, Windows saw 29.8 GB free]; 36 fits W≈30 swap-free while leaving Windows a 12 GB floor; `autoMemoryReclaim=dropcache` returns it after runs; needs `wsl --shutdown` to apply, done). **Levers tested & KILLED:** more workers (BW wall — W=24/28/30 ≤ W=16); **thread-pinning** (`OMP/MKL/OPENBLAS_NUM_THREADS=1`+torch — A/B: **−14% at W=16, −3% at W=24**; the ~35 threads/worker productively use the spare logical CPUs, pinning wastes them; so the "560-thread oversubscription" is a non-issue); **CCD/chiplet pinning** (WSL flattens topology to ONE L3 / one package — the 2 CCDs are invisible to the guest, `taskset` can't target them; and low-EV regardless since both CCDs share the same dual-channel DRAM controller). **Real self-play levers (deferred, for if gen speed ever gates):** faster RAM (3200→3600 ≈ +10%, fiddly on the 4-DIMM mixed kit), the **cluster** (3 independent memory buses; the DDR5 laptop is the best per-core engine), a **compact/cache-friendly leaf rewrite** (cut bytes/sim → raise the saturation point → finally let the extra cores help self-play; BACKLOG "2026-06-09 — Compact leaf" entry — NB there are no numbered BACKLOG entries), and **`train(N) ∥ gen(N+1)` overlap** (the GPU is mostly idle during gen — it's CPU-leaf-bound — so a GPU train slots into that idle time across iters; not within one iter — gen→train→eval is a hard data chain). **Scope:** governs the two CPU-MCTS phases — **self-play (gen) and eval/gate** (same v2.7 leaf, same wall); **training is GPU-bound and untouched.** **Production knob: NO CHANGE** — the launcher's `W=14` is already on the flat W=14–18 plateau (differences inside the ±15–20% run-to-run noise; W=16 absolute ranged 13.75–16.87 pos/s across runs). Tooling committed: `scripts/{sweep_w_thermal,scan_loww,sweep_w_mcpswap,bench_threadpin,measure_worker_mem}.sh`, `scripts/{analyze_w_thermal,bw_scaling,bw_fpu}.py`. No training; no model/eval/leaf changes.
- 2026-06-08 (pm-3, EDT) — **Attempt-#2 pre-flight: both research decisions settled by CHEAP measurement (no cluster); attempt-#2 launcher BUILT (not launched).** Joshua's recipe: pre-flight (fix restart+seed hygiene, guarantee the external odometer on every exit, run the leaf comparison + residual ablation, freeze choices) → then a fixed-3-iter attempt #2 with EXTERNAL keep-best. **Pre-flight resolved both experiments without spending cluster (the "run the cheap option first" discipline):** **(1) Residual-output ablation (S-R3-1) is EMPIRICALLY DEAD** — scanned the residual target Δ across **2.6M positions** (flywheel iter1/iter2 + lever_seq residual_data): std **0.071**, p99 **0.27**, **|Δ|>1 in 0.00%** of rows (max 1.369, a handful), saturation = **0.013% of the MSE budget**. The tanh head [−1,1] never saturates (Δ lives near 0); clipping/linearizing changes nothing → **FROZEN: raw Δ + tanh head, unchanged.** The real residual lever is the SCALE, not the head shape; scale **0.25 confirmed +37.6 marginal** (clean r4 +62.0 → r5 +99.6, n=1200) → Joshua: keep 0.25, no sweep. **(2) Leaf comparison (CL-010) was already measured on the clean ruler (2026-06-07, n=400 paired):** pure leaf gap heur-v2.7-vs-v1 = **−24.4 ± 16.5 (1.5σ = INCONCLUSIVE)** — v1 nominally the stronger standalone leaf but unresolved at n=400; the combined net beats BOTH leaves at matched compute (iter_11 vs v2.7 +89.7 / vs v1 +35.7; Stage-B vs v2.7 +34.9 / vs v1 +24.4). v2.7 is the fully-tuned ecosystem (CAP=12, DROP_THREE_OPEN, residual lineage, +86.9 Stage-B); switching to v1 forces a full re-tune → **Joshua: KEEP v2.7** (v1-leaf = a separate future fork, not a pre-flight). **BUILT `scripts/run_residual_flywheel_v2.sh`** (the attempt-#2 launcher; `bash -n` clean, TALLY-parse verified against real attempt-#1 odo data). KEY changes vs attempt #1, each fixing an attempt-#1 failure mode: **EXTERNAL keep-best** — the warm-from is chosen by a DECK-PAIRED heur@800-v2.7 (out-of-lineage) head-to-head new-vs-best on the iter's ROTATING band (`odo_paired_tally.py` TALLY line → promote iff paired Δelo > KEEP_MARGIN), NOT the discordant in-lineage gate (attempt #1's gate kept iter1 +40 and discarded the stronger iter3 +66.8); the **heur@200 gate is demoted to TELEMETRY** (logged, no authority to crown/terminate); **FIXED 3-iter run, NO plateau-stop**; **distinct self-play decks per iter** (`gen_flywheel.sh` gained a `SEED_START` env, default 0; the launcher passes `it*GAMES` → 400/800/1200) + **rotating selection decks** (SEL_SEED_BASE 1.2e9 + it·stride) + a **SEALED held-out confirmation** (1.7e9, n=400) on the final champion vs iter0; **all per-iter ckpts retained**; the external odometer cannot be skipped (selection runs inline every iter, sealed confirmation runs after the loop unconditionally incl. on a DEADLINE break — fixes attempt #1's D-S7 skip structurally). All hardened helpers (heal-cap, kill-pool-before-relaunch, claim-age-30min, `_ssh_bg` rc=255 retry) carried over. Workers 5800x=14 / laptop=20 / xeon=10, all `nice -n 19` (Joshua). **NOT LAUNCHED — Joshua: "build but don't launch until I tell you."** Frozen recipe: [docs/ATTEMPT2_SPEC_2026-06-08.md](docs/ATTEMPT2_SPEC_2026-06-08.md). No training performed.
- 2026-06-08 (pm-2, EDT) — **"Fix all outstanding bugs" pass → v2.7 leaf confirmed SOUND; ≤2-attempt budget LIFTED.** After the flywheel null, cleared the entire safe/mechanical review backlog (commits `3699605` + `29d37f4`, pytest green, bundle current): **D-R4-1** (warmstart train/val leak → unique-path split, +regression test; byte-identical at mix=0.0), **D-S5** (h2h leaf-config cache-collision → `.leafconfig.json` stamp + startup hard-fail), **D-S1–S7** (restart batch applied LIVE — heal-cap, kill-pool-before-relaunch, claim-age 4→30min, best.pt fail-loud, odometer-before-plateau-break, + new `_ssh_bg` rc=255 retry; `next.sh` removed), **D-R4-2** (auto_chain count/tally → clean-namespace seeds), **D-R3-2** (corr printout relabel in residual mode), **5 launcher seeds→1e9** (run_pathb GATE_SEED, scaling_curve, ladder_highsim, rank_sweep, lever_sequencer — no more guard-hang on reuse), **D16** (a board-edge unfinished city with 0 in-bounds open positions no longer gets a 100% closure bonus, both leaf call sites), **D2** (phase compared by `GamePhase` enum, not a `"tiles"`/`"meeples"` string literal, in board_repr/features/warmstart). **The v2.7 leaf is SOUND:** D16's trigger (a city chain reaching the edge of a 35×35 board in a ~72-tile game) is practically unreachable → the leaf/ruler change is negligible, no cap re-sweep needed; **D3** is NOT a bug (intentional asymmetric-cap denial feature, equal in production → antisymmetry holds); **D1** (TILES/MEEPLES ref-tile encoding) was ALREADY resolved 2026-05-29 as intentional (`board_repr.py:321-329`) — I'd mislabeled it "D2, retrain-gated" earlier in the session and corrected REVIEW_LOG + RESTART_BATCH. **No open code bugs across all five review rounds.** **BUDGET CHANGE (Joshua):** the charter's **≤2-funded-attempts cap is RELAXED** — fine with **~10 more iters** of flywheel/research iteration; the pivot-to-Track-A clock is PAUSED (`PROJECT_CHARTER.md` "Pivot/abandonment budgets" updated). **Attempt-#2 recipe (decision PENDING):** (1) gate keep-best on the out-of-lineage **odometer**, not the discordant in-lineage gate — the #1 attempt-#1 lesson (it discarded the stronger iter3 +66.8); (2) **S-R3-1** residual tanh-cap (clip Δ to [−1,1] or linear head); (3) per-iter deck diversity; (4) CL-010 leaf-choice. No training launched.
- 2026-06-08 (pm, EDT) — **Track-B flywheel attempt #1 (`flywheel_residual_v2`) = NULL out-of-lineage → CL-011 stays Disfavored, now on the clean matched-v2.7 ruler.** The 12-iter residual flywheel (warm from the residual net; per iter: 3-box residual self-play [leaf=v2.7+0.25·Δ, value_target=residual] → train → gate scale-curve vs HeuristicMCTS@200-v2.7 → keep-best @+15 margin, plateau-stop on 2 flat) **plateau-stopped at iter3** @ 12:25 EDT. **Gate (in-lineage vs heur@200-v2.7, n=400):** iter0 **76.8** → iter1 **106.6 (best, +30 — the one significant climb)** → iter2 **99.0** → iter3 **116.2** (the high-water by point estimate, but +9.6 over iter1 < the +15 keep-margin = within-noise tie at σ≈18 → 2 flat iters → plateau). So in-lineage: ONE real step then drift buried in noise. **THE VERDICT (out-of-lineage, deck-paired):** `best.pt`(=iter1) vs **heur@800-v2.7**, n=200, seed 1.5e9 = iter0's IDENTICAL decks → paired: **iter0 +52.5, best +40.1, Δ(best−iter0) = −12.4 elo / z=−0.42 = a WASH (B≤A).** The +30 in-lineage gate climb **did NOT transfer** to the stronger out-of-lineage reference — the textbook **overfit-to-the-gate** signature (the net got better at beating its heur@200 co-adaptation opponent without getting stronger vs a harder one). *(iter3.pt — the actual HIGH-WATER net (116.2 in-lineage) that the +15 keep-margin REJECTED — odometers at **+66.8**, the STRONGEST of the three out-of-lineage: iter3−iter0 = **+14.3/z=+0.49**, iter3−best = +26.7/z=+0.72, BOTH within noise at n=200.)* **→ CL-011 stays Disfavored (conf medium→high).** Even the strongest signal (iter3 high-water) is +14.3 over iter0 = z=0.49 within noise AND, at face value, +14.3 cumulative over 3 iters = **+4.8/iter ≈ 3× SHORT of the charter +15/iter & cum-+45 bar** → fails regardless of significance. **Two honest nuances beyond a flat null:** (a) the high-water point estimate IS the best of the three out-of-lineage → the signal is **positive-but-underpowered, not negative** (n=200 can't resolve +14; ~n=1500 would — but +4.8/iter is below-bar anyway, so not worth the cluster); (b) the **in-lineage gate is a DISCORDANT proxy** — iter1 was +30 IN-lineage but −12 OUT-of-lineage vs iter0 — so the keep-best +15 in-lineage margin **SELECTED THE WRONG net** (kept iter1 +40.1, discarded the stronger iter3 +66.8). 2nd attempt null overall (the 2026-06-07 attempt was null too, pre-clean-ruler). **Attempt-#2 levers:** gate keep-best on the ODOMETER not the noisy in-lineage gate; + S-R3-1 (residual tanh-cap), deck diversity. **R5 live-code audit** (6-surface multi-agent, adversarially verified, same session): shell/provenance/training surfaces **CLEAN**; 3 eval-layer findings — #1 re-confirms D-S5 (h2h leaf-config cache key, latent, h2h done), #2/#3 NEW but **LOW** (`odo_paired_tally.py` seat-count guard + `eval_iter_head_to_head` paired-odd seed-range off-by-one), both fixed result-neutral. **Nothing result-affecting was missed.** The residual value head is a confirmed **STATIC** asset (CL-004 Supported, +37.6 marginal) but **does NOT compound** via self-play co-adaptation. **CL-005 unaffected** — that's about the *static* residual net (iter0, +52.5 odometer), which the flywheel neither improved nor harmed; its production fold-in still gates on a clean n≥400 out-of-lineage confirm + the leaf-choice (CL-010). **BUG found + fixed (D-S7):** the iter3 odometer was **SKIPPED** — the plateau `break` lived before the per-iter odometer block, so the terminal iter's out-of-lineage signal (the single most important number) never ran; **recovered manually** via `scripts/odo_oneshot.sh` + `odo_paired_tally.py` (deck-paired tally), and **fixed** in `run_residual_flywheel.next.sh` (break now after the odometer; odometer also fires on any terminal iter, not just the ODO_EVERY cadence) + documented in `RESTART_BATCH.md`. Commit `61e4fcc`. **This was attempt #1 of the ≤2-attempt P-B charter budget** — attempt #2 levers (decisions, not mechanical): **S-R3-1** (residual target Δ∈[−2,2] saturates the tanh value head [−1,1] → high-signal residuals under-learned — the top lever), per-iter deck diversity, and the v2.7-vs-v1 leaf-choice (CL-010). `results.csv: flywheel_v2_odo_*`. Run dir `/mnt/c/carc-shared/flywheel_residual_v2`. No further training launched.
- 2026-06-08 (overnight, EDT) — **AUTO-CHAIN: h2h verdict `residual_wins` (+34.2/z=4.0, n=1500); a multi-agent pre-launch review caught an R1-REDUX before it ran; Track-B flywheel #1 launched (training, Joshua-authorized).** Joshua: "wire up those shits to auto launch." Built `scripts/auto_chain_h2h_flywheel.sh` (detached orchestrator): wait the running PROTOCOL_002 h2h → deck-paired tally → fire the n=1500 top-up **iff** 1.3<|z|<2 (pre-registered band) → write `AUTOCHAIN_VERDICT.json` → launch the flywheel. **H2H RESULT (eval-only):** n=400 **+29.6/z=1.77** landed in the escalation band → auto-escalated → n=1500 **+34.2 ± 8.5 / z=4.00 = `residual_wins`** (815/17/668 over 750 decks; thin win-rate edge, avg +0.41 pts/game; independently re-tallied, exact match). → **CL-002 Disfavored** (its named falsifier fired), **CL-017 Supported** (residual net = strongest established agent, in-ecosystem), **CL-005 Provisional** (agent-comparison gate passed; production fold-in still FORBIDDEN until the clean out-of-lineage odometer). `results.csv: cleaneval_h2h_residual_rs025_vs_iter11_s200_n1500`; `PROTOCOL_002` RESULT filled. **PRE-LAUNCH REVIEW (multi-agent workflow, adversarially verified — 16 confirmed):** the load-bearing catch was an **R1-REDUX** — the flywheel gate AND the out-of-lineage odometer defaulted to `--heur-leaf v1` while the net runs v2.7 (mismatched opponent, the exact bug the clean-eval effort exists to kill); had it run, the "vs heur@800" odometer would have measured the WRONG opponent and could have falsely shown CL-011 flipping. Plus keep-best **nan-corruption** (gawk treats `nan>x` as TRUE → a degenerate gate could be promoted as "best" and burn the run). **FIXED + committed `702781e` BEFORE launch:** `--heur-leaf v2_7` on all 6 eval calls; continuity-corrected gate_elo (never nan) + `-9999` sentinel + string-based nan rejection; ITERS-override validation; orchestrator JSON/nan/stall-heal/partial hygiene. **Deferred (non-blocking):** #5 seed-keyed gate dir, #12 per-box provenance-smoke, #13/#14 manifest residual_scale, #16 other launchers (`run_pathb_cluster_loop.sh`, `rank_sweep.sh`, `lever_sequencer.sh`, `scaling_curve.sh`, `ladder_highsim.sh`) still carry pre-1e9 eval seeds that would hang like the gate did — fix before reuse. Also fixed earlier: `GATE_SEED` 900000→1e9 (`a888134`, the eval guard would have hung iter0) + the in-loop heur@800 odometer. **TRACK-B FLYWHEEL #1 launched 02:48 EDT** (`flywheel_residual_v2`, warm from the residual net): 12 iters, gate@1e9 matched-v2.7, `VLW=1.5` (attacks CL-008 value-gradient-starvation), in-loop out-of-lineage odometer (best vs heur@800-v2.7, clean seed 1.5e9) at iter 0/3/6/9/12 → `flywheel_residual_v2/odometer.csv`. **This is the P-B attempt #1 of the ≤2-attempt charter budget — the falsifier on CL-011.** Plateau-stops on 2 flat iters; no wall-clock cap. **This IS training (Joshua explicitly authorized it; the no-train ruler-build task is complete).**
- 2026-06-08 (pm) — **TOP-UP RESOLVED (PROTOCOL_001, eval-only): residual value-head marginal is REAL (+37.6 elo/z=2.98), and the "non-transitivity" reframe is OVERTURNED.** The n=400 clean pass left two items open; the pre-registered top-up (`scripts/run_clean_eval_topup.sh`, 3-box, commit `4d43c79`) extended the residual cells to **n=1200 paired** and added clean net-vs-heur-**v1** cells. **RESULT (1) — residual marginal:** scale0 **+62.0**, scale0.25 **+99.6** (n=1200); deck-paired marginal **+0.0512 wr / +37.6 elo / z=2.98** → clears the pre-registered +35/2σ bar → **CL-004 Inconclusive→Supported**. The n=400 screen (+26/z=1.30) was **UNDERPOWERED, not wrong**; the old lever-1 "+45 robust" largely survives clean. The residual value head is a confirmed **STATIC** strength asset — but still NOT a self-improvement breakthrough (the flywheel to compound it was null, CL-011 stays Disfavored). **CL-005 (residual→production)** moves from "auto-drop" to a **live decision**: strength precondition met, but PROTOCOL_001 FORBIDS auto-fold-in without a head-to-head + clean out-of-lineage check. **RESULT (2) — non-transitivity OVERTURNED:** the earlier reframe (CLEAN_EVAL_AUDIT: "the opponent-leaf effect is sign-varying — iter_11 finds v2.7 easier, Stage-B finds it harder") was an **artifact of the contaminated v1 baseline**. Clean net-vs-v1: **iter_11 +35.7** (old +25.2), **Stage-B +24.4** (old **+86.9** — a 62-elo inflation). Clean Δ(v2.7−v1): iter_11 **+54 (z=2.29)**, Stage-B **+10 (z=0.46 n.s.)** — **SAME sign for both** (`analyze_nontransitivity.py`). So the leaf effect is NOT sign-varying; both nets simply beat the **weaker v2.7-leaf opponent** (corroborating r1's −24.4) by a net-specific margin. No single universal discount stands (magnitudes differ), and old unmatched-leaf absolutes are confirmed incomparable → **CL-012 strengthened**, new **CL-016 (non-transitivity) Disfavored**. Deliverables updated: `governance/protocols/PROTOCOL_001_*` (RESULT filled), `governance/CLAIM_REGISTRY.csv` (CL-004/005/012/016), `clean_eval/CLEAN_RESULTS.csv` (7 rows) + `CLEAN_EVAL_AUDIT.md` (banner + 2 superseded spots), `results.csv: cleaneval_{r4,r5}_n1200,t1,t2`. **NEXT:** residual@0.25-vs-iter_11 head-to-head (PROTOCOL_002) to crown the production agent. No training performed.
- 2026-06-08 — **GOVERNANCE LAYER (Phase A) + TRACK DECISION: P-B primary, superhuman DEFERRED (no training).** After the clean-eval ruler, two outside reviews asked for an experiment-governance layer to stop hypotheses becoming facts by repetition, incomparable checkpoints being treated as one lineage, and invalidated eras re-entering reasoning. **Gap analysis first** (the repo was already narrative-rich — DECISIONS 314KB, outside_review/ 240KB — so the gap was machine-readable STRUCTURE, not more prose). **Built Phase A** (commit `d0245a0`, branch `stage-b-wiring`, 5 parallel subagents under a frozen canonical spec) in a new top-level `governance/`: **CLAIM_REGISTRY.csv** (+schema) — 15 claims under a controlled 7-term status vocab (Confirmed/Supported/Provisional/Inconclusive/Disfavored/Invalidated/Untested), honestly seeded so two of the reviewers' OWN seed claims landed where evidence forced them — "AlphaZero flywheel demonstrated"=**Disfavored** (CL-011), "use residual in production"=**Untested** (CL-005), "historical unmatched-leaf elo comparable to clean"=**Invalidated** (CL-012), residual marginal=**Inconclusive** (CL-004); only 3 test-backed ruler-infra claims are Confirmed. **CHECKPOINT_LINEAGE.csv** (+schema) — 8 ckpts, real sha256, recovered chain (warmstart→v25_retrain→{optionB,deepsearch}; iter_10→iter_11→stage_b→residual, confirmed `stage_b/warm.pt==iter_11.pt`). **EVIDENCE_EPOCHS.md** (7 epochs: River, farmbug, transposition, unmatched-leaf R1, overlap-seed, R7-residual, clean-ruler). **PROTOCOL_TEMPLATE.md + protocols/PROTOCOL_001** (pre-registration; the running top-up is the worked example, stored separately from results so the hypothesis can't be rewritten). **README.md** (the 3-layer spine: raw→interpretation→decisions). **Consolidation** (additive, 0 deletions): EXPERIMENTS.md superseded-banner, CLAUDE.md truth-table row, experiments/README + outside_review pointer. **KEY FINDING (→ Phase B):** no checkpoint persists its training dataset hash, code commit, or seed ranges (all `unknown@train`, unrecoverable) — a "stamp train-config into the ckpt dict" step MUST land before the next training run. **TRACK DECISION (Joshua):** **Track B (genuine self-improvement) is PRIMARY**; "superhuman vs humans" is **kept but DEFERRED** (unmeasurable — no human/out-of-lineage-strength anchor). Operational consequence: the near-term Track-B objective is the MEASURABLE one — a genuine **out-of-lineage climbing curve** on the asymmetric ladder (heur@800 fixed reference), i.e. **flip CL-011 from Disfavored to Supported**. Superhuman promotes from aspiration to active goal only after the human-anchor rung exists. `PROJECT_CHARTER.md` updated: primary=P-B, superhuman deferred, + the ~12 strategic thresholds filled as **PROPOSED defaults Joshua edits/ratifies** (Track-B bar: ≥3 non-regressing iters, ≥+15 elo/iter out-of-lineage, cumulative ≥+45, gate n≥400; Track-A ship bar: +30 vs heur@800 out-of-lineage n=400 [currently UNMET]; B→A pivot: ≤2 funded attempts ≤~7d each; abandon→analyzer if a structural redesign also fails). The original-prompt-vs-2026-05-28 goal conflict is surfaced in the charter, not papered over; the analyzer (Phase 5) is the explicit abandonment landing zone, not a competing live target. **Phase B** (training observability + the ckpt-stamp) is gated before any next training; **Phase C** (review-bundle automation) deferred. No training performed.
- 2026-06-07 (pm-2) — **CLEAN-EVAL RULER BUILT (no training) → the learned-policy edge is REAL on a trustworthy ruler, but the "leaf-gap = universal +45% inflation" framing is OVERTURNED and the residual value-head marginal does NOT survive clean.** Two outside reviews of `outside_review/` said: repair measurement+provenance before any more training (trigger = R1: the yardstick `HeuristicMCTS` ran the **v1** leaf while the agent ran **v2.7**). Built it in 3 phases (commits `328594e`→`3cc0c9a`, branch `stage-b-wiring`): **(1) provenance** — `src/carcassonne_ai/eval_provenance.py` runtime-asserts the leaf/value path that ACTUALLY executed (fails if a side claims v2.7 but ran v1 [R1], or sets residual_scale>0 but the residual path never fired [R7]); `EvaluatorSpec` (full both-sides config), deck hashes, `EVAL_SEED_FLOOR=1e9` namespace guard; `_V25Wrapped`+`HeuristicMCTS` expose live leaf-path counters; `EVALUATOR_SCHEMA.json`; all 4 eval scripts hardened (`--seed-start 1e9`+guard, deck_hash, evaluator manifest block, `eval_net_vs_heuristic --residual-scale/--provenance-smoke`, `eval_iter_head_to_head` R7 fix `_value_head_needed`); `verify_evaluator_provenance.py` passes. **(2) semantics** — `tests/test_semantic_eval_contracts.py` (11 contracts) + `tests/test_eval_provenance.py` (incl negative tests) = 35/35 green, full suite green; `gen_semantic_test_report.py`→`clean_eval/SEMANTIC_TEST_REPORT.md`. **(3) 5 clean reruns** (3-box `--shared-claim` `run_clean_eval_reruns.sh` W=14/10/20, n=400 paired, seed 1e9, sims=200, matched v2.7 opp CAP=12; aggregator `summarize_clean_eval.py`). **CLEAN RESULTS (vs the MATCHED v2.7 yardstick, `results.csv: cleaneval_*`, `clean_eval/CLEAN_RESULTS.csv`):** iter_11 **+89.7±17 (z=5.2, resolved)**, Stage-B iter_01 **+34.9±18 (~2σ)**, residual scale0 **+56.1**, residual scale0.25 **+83.2**; pure leaf gap heur-v2.7-vs-v1 **−24.4±16 (z=1.5, INCONCLUSIVE, leans v2.7-WEAKER)**; residual value-head **marginal (scale0.25−scale0, deck-paired) = +26±20 / z=1.30 → INCONCLUSIVE**. **THREE NARRATIVE SHIFTS:** (a) the learned policy edge is REAL — every net beats the matched yardstick, so "results are all lies" is NOT the story (the R1 fear was overblown); (b) the **leaf-gap "universal +45% discount" is WRONG** — the pure v2.7 leaf is *weaker* than v1 in standalone search, and the opponent-leaf effect is **NON-TRANSITIVE across nets** (iter_11 +25.2[v1]→+89.7[v2.7] = v2.7 *easier*; Stage-B +86.9[v1]→+34.9[v2.7] = v2.7 *harder*) — absolutes must be re-measured per-net at a matched leaf, not blanket-discounted; (c) the **residual value-head marginal does NOT survive clean** — drops from the old "+45 robust" to +26/z=1.30 once R7 guarantees the residual path fired → do NOT fold the residual into production without an n≈900–1500 top-up (the single most consequential downgrade). **Process note:** cluster eval throughput was ~12.5 games/min combined (net-vs-heur, n=400×4 cells, CIFS+GPU contention) — a 2-worker bench under-predicted wall-clock ~2× (quoted ~1hr, ran ~2hr); bench at production W/share, not low-W. **⏭ NEXT (recommended sequence): (1)+(2) one cluster top-up run (eval-only ~2hr): residual scale0-vs-0.25 at n≈1200 + clean net-vs-heur-**v1** cells for iter_11/Stage-B (nail the non-transitivity); (3) make the residual production fold-in decision on that; (4) return to the strength/superhuman question on the now-trustworthy ruler; (5) refresh `outside_review/` to mark R1+R7 CLOSED.** Deliverables: `clean_eval/` (CLEAN_EVAL_AUDIT.md classifies every old claim, CLEAN_RESULTS.csv, manifests, raw_per_game.tar.gz [2000 games], provenance_smoke). No training performed.
- 2026-06-07 (pm) — **ODOMETER (out-of-lineage) → the residual gain is REAL, not ecosystem illusion; modest (~doubles heur-equiv depth); ceiling RAISED not broken.** Ran the asymmetric-compute ladder (`scripts/ladder_asymmetric.py`, 3-box, seed 950k, n=120/rung): hold the residual net @200 sims, sweep HeuristicMCTS @{200,800,3200}, at BOTH residual scales (0.25 = residual leaf, 0 = pure v2.7). **Result (residual margin = scale0.25 − scale0 elo):** heur@200 **+63.6**, heur@800 (4× deeper, OUT-OF-LINEAGE) **+47.5**, heur@3200 (16×) **−17.5** (within noise of 0 at n=120, σ~45). **Crossover (heur-equiv depth, wr=0.5): residual net ~588 vs pure-policy ~325.** **THE DECISIVE FINDING: the residual margin SURVIVES at heur@800** (+47.5 ≈ the n=300-400 in-ecosystem +45) — a 4×-deeper opponent the net was NEVER gated against → the residual is NOT overfit to the heur@200 operating point (unlike the 2026-06-01 iter_4 "+39 = dead tie on the independent ladder"). It roughly **doubles the heuristic-equivalent depth (325→588)** = a genuine, externally-validated modest strength gain. **BUT it's bounded:** the net still LOSES to heur@800 (−29) and heur@3200 (−38), and the residual edge WASHES OUT at heur@3200 (margin ~0 — against a vastly deeper searcher a small leaf correction stops mattering). So the v2.7-leaf ceiling is **RAISED ~1 doubling, NOT broken** — nowhere near superhuman. **NET (answering "is this the breakthrough?"): the value head genuinely helps now and it's validated out-of-lineage — the project's long-standing value-as-leaf blocker is PARTIALLY cracked — but it's a modest v2.7-anchored refinement, not the superhuman unlock.** (Infra: the asymmetric ladder is now a working non-saturating out-of-lineage odometer — addresses the measurement structural blocker. Also: laptop CPU-bound EVAL worker count corrected to W=20 [24-thread box], was under-utilized at 14.) Results: `results.csv: odometer_residual_*`. Run dir `/mnt/c/carc-shared/odometer_residual`. **NEXT (Joshua's call): (a) accept the residual as a validated modest gain + fold into production + reassess the superhuman goal honestly, or (b) a more careful flywheel / higher-capacity learned leaf to try to push past heur@588 (lower EV — the first flywheel was null + unstable, and the residual washes out at depth).**
- 2026-06-07 — **Lever 3 (residual FLYWHEEL) = NULL for compounding → the residual is a confirmed STATIC asset, not a climbing one.** Wired residual-scale-IN-SELF-PLAY (`1d5ae26`: `--residual-scale` keeps the value head active at value_blend=0, threads to leaf_cfg) + built `run_residual_flywheel.sh` (`ac0afd7`; per iter: 3-box residual self-play [leaf=v2.7+0.25·Δ, value_target=residual] → train → gate scale-curve vs HeuristicMCTS@200 → keep-best, plateau-stop). Hardened: fanned the gate 3-box (`a528b0b`, the eval is ~3 g/min single-box — per-worker CUDA thrash), overnight deadline/keep-margin (`a23f1cf`), and **orphan-stall self-heal** (`cd853b1`) after the first overnight attempt **silently stalled 3h** on a shared-claim orphan-stall (28 stranded `.claim` files from a kill — the 556/600 bug; my gate lacked the stage-b launcher's self-heal). **RESULT (gate seed 900000, n=300):** iter0 (the residual net) scale0.25 **+116.5** (marginal +41); iter1 **+66.8** (REGRESSED −50 — the co-adaptation train destabilized the policy: scale0 +75→+35); iter2 **+125.7** (+9.2 vs iter0, < the +12 keep-margin = TIED within noise; marginal +46.8). Plateau-stopped (2 flat); best stays iter0. **VERDICT: the residual gain does NOT compound via this flywheel** — neither the policy (scale0 flat +75/+35/+79) nor the value-contribution (marginal stable +41/+32/+47) climbs; iter1 showed co-adaptation can DESTABILIZE. (Caveat: only 2 iters, both from the iter0 baseline; gate noise ±21 hides a small <+12 climb but rules out STRONG compounding.) **The residual marginal is now ROBUSTLY confirmed ~+45 across 4 measurements (3 seeds 700k/800k/900k + the iter2 gate)** — a real, modest, STATIC v2.7-refinement. **This does NOT break the v2.7-leaf ceiling** (CLAUDE.md structural blocker stands): the value head is a junior partner nudging v2.7, not a standalone strong eval (pure-NN leaf still craters; inverted-U says more value-weight hurts). **NEXT: the out-of-lineage ODOMETER (Lever 4 measurement) on iter0 best (`flywheel_residual/best.pt` = the residual net)** — the in-ecosystem +116/+45 may overstate (the 2026-06-01 iter_4 "+39 = dead tie on the independent ladder" precedent). If the +45 marginal SURVIVES the odometer → genuine modest strength gain; if it evaporates → in-ecosystem illusion. Results: `results.csv: flywheel_residual_*`. Run dir `/mnt/c/carc-shared/flywheel_residual`.
- 2026-06-06 — **4-LEVER CAMPAIGN → Lever 1 (predict-v2.7 + residual) is the FIRST asset-positive learned-value leaf (confirmed, modest).** Built all 4 levers + an auto-sequencer (`scripts/lever_sequencer.sh` + `lever_summary.py`, judged on the MARGINAL = knob>0 elo − knob=0 elo, with σ+z so a low-n point≥0 isn't mistaken for a win). **Lever 1** (`44100a9`): head predicts the RESIDUAL Δ=search-Q−tanh(vs2/15); leaf = `clip(v2.7 + scale·Δ, ±1)` (`CARCASSONNE_V25_RESIDUAL_SCALE`, `value_target="residual"`). **Lever 2** (`d2a6a53`): per-node-centered MSE (`--center-weight`, reuses rank_data group_id, NO gen). Ran 3-box (laptop solo did the 400-game residual gen in ~1h54m; sequencer train+eval on laptop). **RESULT (paired vs HeuristicMCTS@200):** Lever 1 scale-curve scale0=+28, **scale0.25=+96 (marginal +68, z=1.93)**, scale0.5=+80 (marginal +52, z=1.5) — an inverted-U, two consistent +ve scales (not a lone spike). **INDEPENDENT n=400 confirmation (fresh seed 800000):** scale0=+32, scale0.25=+68 → marginal **+35.5 ± 25 (z=1.43)**; the +68 screen regressed to +36 (regression-to-mean, screen was high). **POOLED (screen n200 + confirm n400, independent seeds) = +46.5 ± 20, z=2.29** → ~99% the residual value is a REAL asset. **Lever 2 FAILED** (marginal −62, value still hurts). **This is the FIRST positive-marginal learned value in the whole investigation** (vs −24/−38/−67/−94 for every prior MSE/ranking approach) — predicting the residual lets the leaf inherit v2.7's local sibling-ranking BY CONSTRUCTION and only nudge where deep search disagrees (the on-distribution Δ is small/tailed: median |Δ|=0.02, but 12% >0.1). **⚠️ Scoping honestly: this is a MECHANISM win (value finally HELPS the search), NOT yet a strength win** — it's ~+40 elo marginal, measured IN-ECOSYSTEM vs our own HeuristicMCTS (the marginal is clean/paired, but absolute strength vs an OUT-OF-LINEAGE odometer is untested; the residual training may also have cost some policy [scale0 baselines +28-32, noisy-consistent with the prior +74 gate]). **NEXT (Joshua to confirm — a multi-hour 3-box run): Lever 3 flywheel** — use the residual leaf in NEW self-play + retrain + iterate so value+policy co-adapt (KataGo; where a modest +40 can compound). ⚠️ the flywheel needs residual-scale-IN-SELF-PLAY wired into `run_pathb_cluster_loop` (it only ramps `--value-blend`; the printed STAGE_B_BLEND hand-off is a placeholder for l1 — set `CARCASSONNE_V25_RESIDUAL_SCALE` + `value_target=residual`, and the per-iter gate must use the residual leaf, not value_blend=0). Results: `results.csv: lever1_residual_*`, `lever2_centered_*`. Run dir: `/mnt/c/carc-shared/lever_seq`.
- 2026-06-05 (pm-5) — **STEP B.1 ranking-loss sweep: HELPS but INSUFFICIENT → DECISION: design + auto-run all 4 levers sequentially.** Sweep (`88a5b5e`, 6 configs α∈{.5,1,3}×τ∈{.1,.3}, each train + λ-curve n=200, 3-box, `/mnt/c/carc-shared/rank_sweep`). **Read the MARGINAL (λ0.5 − λ0), NOT absolute λ0.5** — absolute is confounded by the policy baseline (λ0≈+70; rank_data α=0 gate=+74). Only-complete config a05t01(α=.5) = marginal **−67** (value still hurts); others partial+noisy. **Verdict: ranking loss helps (best −67 vs pure-MSE −80/−94; λ1.0 crater −356 vs −576/−604) but NO config reaches marginal≥0 → not an asset.** ⚠️ **Process note:** I initially over-claimed "a05t01 λ0.5=+6.9 clears the gate" — RETRACTED within the hour (Joshua's "false positive?" caught it): +6.9 is within noise of 0 (z=0.28) AND confounded by the strong policy baseline; the marginal (−67) shows the value still hurts. `rank_sweep_summary.py` rewritten to report the marginal + the corrected verdict so the autonomous read can't repeat the error. **DECISION (Joshua): the sweep tuned ONE lever; now design all 4 genuinely-different levers + wire a SEQUENCER to run them automatically (gen→train→λ-curve each, gate on marginal≥0, early-stop on a winner):** (1) **predict-v2.7+residual** (leaf=v2.7+Δ, inherits local consistency by construction — cheapest/most-likely); (2) **per-node-centered targets** (fit relative sibling diffs; reuse group_id harvest); (3) **in-loop flywheel** (use the value as a λ-leaf in NEW self-play + iterate; KataGo co-adaptation; the one the one-shot sweep can't test; STAGE_B_BLEND already does value-in-self-play); (4) **measurement/accept-ceiling** (odometer `ladder_asymmetric.py` + diverse opponents, or different leaf, or accept ~strong-human). Plan: `docs/VALUE_LOSS_ATTACK_2026-06-05.md` ("the 4-lever auto-sequencer"). ⚠️ ssh-to-xeon-wsl inline `cd` keeps vanishing (use `CMD="cd $REPO && …"` var); detach remotes with `setsid …</dev/null &`; remote scripts via ABSOLUTE path (`$REPO/scripts/x.sh`).
- 2026-06-05 (pm-4) — **STEP B.1 (listwise sibling-ranking loss) BUILT + launched as the Shabbos autonomous sweep.** The fix STEP A/B.0 proved necessary (MSE can't rank siblings even on the optimal target). Build (`369677f`): `mcts.interior_sibling_groups` (each well-visited parent's children as a group, own-POV Q — all children share one POV so own-POV Q is the ordering target); selfplay `value_target=search_value_rank` (trajectory root.Q rows + value-only group rows tagged with a globally-unique `group_id`); `GameDataset.group_id` int64 array (the `aux_mask` pattern: save/load/rotate/augment + `make_streaming_dataset` 8th tuple element; -1 = ungrouped); `train_iter` `listwise_ranking_loss` (per-group segment softmax-CE of head outputs vs search-Q, `--rank-weight α --rank-temp τ`; `shuffle_within_file=False` keeps groups batch-contiguous; value-MSE kept for absolute scale). 3 selfplay group tests + a listwise-loss unit test; updated all 8-tuple consumers; full suite green; gen+train smoke clean (rank loss live). **Shabbos run (Joshua chose the SWEEP over an iterated flywheel — robust unattended):** 3-box gen of the `search_value_rank` dataset (`RUN=rank_data`, 400 games) then `scripts/rank_sweep.sh` over 6 configs α∈{0.5,1,3}×τ_rank∈{0.1,0.3}, each = train + full λ-curve (0/0.5/1.0, n=200 paired) vs HeuristicMCTS@200, split across boxes (self-contained, resumable). **SUCCESS = any config λ0.5 ≥ 0** (prior failures −24/−38/−38). Verdict: `scripts/rank_sweep_summary.py --out /mnt/c/carc-shared/rank_sweep`. If it clears → iterate the flywheel; if not → v2.7-leaf ceiling real (5×) → measurement / different approach (`docs/VALUE_LOSS_ATTACK_2026-06-05.md` "If this ALSO fails"). ⚠️ ssh-to-xeon-wsl inline `cd` keeps vanishing — build remote cmds as `CMD="cd $REPO && …"` (var), and detach remotes with `setsid …</dev/null &` (NOT `nohup…& disown`, which hangs the ssh).
- 2026-06-05 (pm-3) — **STEP B.0 (mimic-v2.7 de-risk) ✅ PROVES the LOSS FORM is the problem (not the target) → STEP B.1 (ranking loss) is mandatory.** The cheap de-risk before the full ranking-loss plumbing: `value_target="v2_7"` (commit `a7691e4`, 3 tests) trains a head to predict the **v2.7 LEAF VALUE** tanh(vs2/15) — the OPTIMAL target (v2.7 itself ranks siblings at τ=0.60). 3-box gen (400 games, warm iter_01, vlw=1.0; remotes bundle-synced to a7691e4) → train → re-probe + λ-curve. **RESULT: the head fit v2.7 globally (corr 0.86) yet ranks siblings at τ=0.088 — chance, IDENTICAL to the search-Q head (0.081), and barely agrees with the v2.7 it was trained to copy (τ_net,v2.7=0.14).** Same λ-failure: λ0=+3.5\* / λ0.5=−38 / λ1.0=−604 (`results.csv: mimic_v27_*`; \*λ0 is a noisy n=100 gate at seed 500000, ~1.5σ below searchval's +56 — the games are near-identical across runs, so it's noise; τ is the low-noise signal). **VERDICT: MSE regression cannot produce a sibling-ranker REGARDLESS of target** — it fits global variance but the within-node Q differences that decide a move are swamped by approximation error. So the failure is the **loss FORM**, not the target (search-Q vs v2.7). This QUADRUPLY confirms value-as-leaf failure and is the FIRST to isolate the cause. **DECISION: build STEP B.1 (the ranking loss)** — the designated and LAST clean lever. Design resolved: a node's children all share one current_player (Carcassonne splits tile vs meeple actions), so the harvest = the existing search_value_tree interior harvest + a `group_id` tag (encode child own-POV, target own-POV Q, value-only rows); the real work is the **batch-grouped listwise loss** in train_iter (segment-softmax of head outputs vs own-POV search-Q within each group, + value-MSE for scale; success = λ0.5≥0). If B.1 ALSO fails → the v2.7-leaf ceiling is real (5× confirmed) → pivot to measurement / a fundamentally different approach (`docs/VALUE_LOSS_ATTACK_2026-06-05.md` "If this ALSO fails"). Probe: `scripts/probe_decision_ranking.py`.
- 2026-06-05 (pm-2) — **STEP A (decision-ranking probe) ✅ CONFIRMS the value LOSS is the problem → proceed to STEP B (ranking-loss retrain).** Built `scripts/probe_decision_ranking.py` (commit `98364bd`; parallel CPU multiprocessing, net on CPU per worker → sidesteps the fork+CUDA crash; `kendall_tau_b` validated on hand-computed cases incl. ties). For on-distribution decision positions (real v2.7-leaf self-play), each legal move's child board is scored 3 ways from the decision-maker's POV: **value-net head**, **1-ply v2.7**, and the **oracle = a deep `oracle_sims=400` v2.7-leaf search from each child** (the move's converged value, = what `search_value_tree` trained the head on). Ranked vs the oracle by Kendall-τ-b / top-1 / oracle-regret. **RESULT (`searchval_tree/ckpt/iter_00.pt`, n=120 nodes, mean k=13.8):** value-net τ **+0.081±0.023** (≈22 SE below v2.7's **+0.579±0.024**), top-1 0.15 vs 0.44, oracle regret **1.92 pts vs 0.62 pts** — the net's regret (0.0675 tanh) is **barely better than random** (0.0794), and net↔v2.7 rankings barely agree (τ=0.10). **→ a 0.84-outcome-corr value head has near-ZERO local move-discrimination; corr is definitively the wrong gauge; the LOSS optimizes the wrong objective.** Methodology that mattered: **oracle DEPTH is load-bearing** — a shallow oracle (sims=60) ≈ 1-ply v2.7 (circular) understated the gap (net τ 0.48); deepening to 400 collapsed net τ→0.08. **⚠️ Caveat:** the 1-ply regret gap (1.9 vs 0.6 pts) is *smaller* than the λ1.0=−576 crater → that crater is ALSO error-compounding at depth + off-distribution (search drives into the net's blind spots), which a 1-ply probe can't capture. So **STEP B targets the λ0.5≥0 gate** (v2.7 still anchors local consistency at 50%), NOT necessarily fixing λ1.0 (that's the flywheel problem). **DECISION: build STEP B** (sibling-set harvest in self-play → batch-grouped **listwise** softmax-CE ranking loss on child search-Q, multi-task with the value-MSE for absolute scale; cheaper de-risk = a "mimic-v2.7" head first). Full plumbing spec in `docs/VALUE_LOSS_ATTACK_2026-06-05.md` ("NEXT action — STEP B build"). No second probe run — 22 SE is conclusive (cost discipline). Result on share: `/mnt/c/carc-shared/decision_ranking_svtree/summary.json`.
- 2026-06-05 (pm) — **FLYWHEEL STEP 2 (global pooling) ALSO FAILS the value-as-leaf gate → DECISION: attack the value LOSS (decision-ranking), not data/architecture.** Built a global-pooling value head (`CarcassonneNet(value_global_pool=True)`: inject `cat[trunk.mean, trunk.amax]` into value_fc1; commit `e4a77ed`, +4 tests, plumbed through all 5 pipeline scripts; `train_iter --global-pool --warm-value-fresh` = partial-warm = keep iter_01 trunk/policy, re-init only the value head → isolates the arch change). Trained it (partial-warm on the 822K interior data, 5 epochs). **3-box λ-gate (xeon via the new `xeon-wsl`!): λ0.5 = −38 ±35, λ1.0 = −552 (4W/96L), corr 0.8446 ≈ step-1's 0.8435** (`results.csv: searchval_tree_GP_iter00_blend{05,10}_*`). **Global pooling moved NOTHING** — same curve as step 1 (+56/−24/−576), all within noise. **VERDICT (TRIPLY confirmed across 3 value nets): a 0.84-outcome-corr value is NOT a usable MCTS leaf, and it's fixed by neither more data (step 1) nor board-wide context (step 2).** **DECISION (Joshua): attack the value LOSS.** Hypothesis: a leaf needs to RANK sibling moves correctly (relative), not predict the absolute outcome; outcome/Q-MSE optimizes the wrong objective (v2.7's corr is lower at 0.61 but it's locally consistent → a good leaf). Plan (`docs/VALUE_LOSS_ATTACK_2026-06-05.md`): **STEP A (cheap gate, ~1-2hr, no training)** = offline decision-ranking probe — harvest decision nodes' sibling sets `(child board, search-Q oracle, v2.7 value)`, compare value-net vs v2.7 vs search-Q rankings (Kendall-τ / oracle-regret); predict value-net τ LOW despite corr 0.84, v2.7 τ HIGH. **STEP B (only if A confirms)** = ranking-loss retrain (listwise softmax-CE / pairwise margin on sibling search-Q; needs sibling-set harvest in self-play), success = λ0.5 crosses ≥0. If B also fails → v2.7-leaf ceiling is real (quadruply confirmed) → measurement / different approach. **Step 3 (iterated ramp) DEFERRED** — my gate (do step 3 only once a net clears λ0.5≥0) is unmet; iterating a known-liability leaf isn't justified yet. NEXT ACTION = build STEP A.
- 2026-06-05 — **FLYWHEEL STEP 1 (interior value targets) BUILT + VALIDATED → one-shot is NOT enough (value-in-leaf still hurts); cheap test exhausted, next lever = step 2 (global pooling) before step 3 (iterated ramp).** Built `value_target="search_value_tree"` (commit `67fd90e`): `NeuralMCTS(record_boards=True)` + `interior_value_targets()` harvest (board→converged Q) from the search TREE INTERIOR; selfplay emits them as **value-only rows** (new per-row `GameDataset.aux_mask`, None→all-True back-compat, threaded through save/load/rotate/augment/streaming-7-tuple); shared `masked_policy_ownership_loss` trains policy+ownership on full rows only, value on all. Full pytest green + plumbing smoke. Ran the validation: 400-game `search_value_tree` (sims=200, warm iter_01, λ=0, 3 boxes), trained warm-from-iter_01 (3 epochs). **Three measures of the interior-trained net:** (1) held-out value↔search-Q corr **0.84** (vs trajectory head 0.46) — the value DID learn to model the interior; (2) **λ-curve vs HeuristicMCTS@200, n=100 paired: λ0=+56 ±35 → λ0.5=−24 ±35 → λ1.0=crater (0/14)** (`results.csv: searchval_tree_iter00_blend{00,05,10}_*`). **VERDICT:** value-in-leaf still degrades strength MONOTONICALLY — essentially the same shape as the trajectory head (+96→−37→−576), all diffs within ~1σ. **One-shot interior training did NOT make the value usable as a search leaf**, even though corr nearly doubled → **re-confirms (3rd time) that value↔Q/outcome correlation is the WRONG gauge for search-leaf usefulness.** Mechanism: the value learned the interior of a *v2.7-guided* search; blending it in shifts the search to a distribution it hasn't seen (KataGo closes this over MANY in-loop iters, not one). **The cheap one-shot flywheel test is exhausted.** Remaining levers both expensive: **step 2 (global pooling** — a better value ARCHITECTURE; the 6×96 conv+flatten can't integrate board-wide farm/meeple state, reviewers' "single biggest quality lever") and **step 3 (the full iterated λ-ramp).** RECOMMENDATION (pending Joshua): **step 2 first** — a one-shot arch upgrade is cheap to test (retrain once, re-measure λ); if the value is fundamentally under-powered, no amount of step-3 iteration on the current net fixes it; only commit to the multi-iteration ramp once a net clears λ=0.5≥0. **Side wins this session:** (a) **9p training-stall fix** — a Windows-drvfs/9p stall wedged the validation train mid-epoch (GPU idle ~50min); `train_iter --stage-local` copies the buffer to ext4 before streaming, wired into the loop (`47fd796`); (b) **Xeon direct-WSL-ssh LIVE** (`ee0c090`) — sshd in WSL :2222 + portproxy + `Host xeon-wsl` → `ssh xeon-wsl "a && b | c"` works like the laptop, cmd.exe hop gone (Windows sshd :22 stays as fallback); (c) **odometer rung 1** — `scripts/ladder_asymmetric.py` (asymmetric-compute v2.7 ladder = heuristic-equivalent depth, out-of-lineage, `07ebda8`).
- 2026-06-04 (pm-5) — **REGROUP (4 independent outside opinions) → BUILD the in-loop value FLYWHEEL; keep superhuman as north star.** After characterizing the search-value lever (pm-3/pm-4), measured the value-as-leaf cliff: value-blend@play **λ0=+96 → λ0.5=−37 → λ1.0 (pure NN leaf)=−576** (`results.csv: searchval_s400_iter00_valueblend10_*`). Then got **4 independent unbiased opinions** (3 blind subagents on a neutral brief + 1 external reviewer Joshua sourced). They converged and **corrected the pm-4 "information ceiling" call:** (a) **~0.47 is NOT an info ceiling** — it's corr with the *noisy final margin* (tile-draw variance); decision-ranking / expected-value is what matters, and outcome-corr is the wrong gauge; (b) the **−576 is a DISTRIBUTION MISMATCH** (value trained on the self-play trajectory, queried on the tree interior it never saw) — KataGo fixes this by training value **in-the-loop on its own search distribution**; (c) the curve **erodes because the value flywheel is OFF** (only policy learns; frozen v2.7 leaf = a half-flywheel that settles) — AlphaGo's climb came from value+policy turning together; (d) **even +87 may be ecosystem-overfit** (vs the same v2.7 we train/play; the iter_4 "+39 = dead tie on the independent ladder" proves the gauge lies) → need a light **out-of-lineage odometer**; (e) all four flagged the goal as resource-mismatched (3 GPUs ≪ known superhuman recipes; high-variance game) and suggested re-scoping. **Joshua's call (reconciling with the AlphaGo playbook — "they didn't know AlphaGo was superhuman until they let it climb, THEN challenged Lee Sedol"):** KEEP superhuman as the north star (do NOT re-scope to the analyzer); **build the in-loop value flywheel** (the only lever that can make the curve CLIMB), put a *light non-lying odometer* on it (the reviewers' measurement point = the trustworthy curve-meter the AlphaGo plan requires — our own gauge lied once), let it climb, challenge a human LAST. We are NOT throwing out the reviewers — the flywheel IS their #1 technical recommendation; only the "lower the goal" counsel is set aside (Joshua's prerogative), with the resource risk recorded honestly. **Build spec: `docs/INLOOP_VALUE_FLYWHEEL_BUILD_2026-06-04.md`** (step 1 = value records the MCTS interior/search distribution [the −576 fix; needs value-only rows + loss masking]; step 2 = global pooling; step 3 = value-into-leaf-in-loop; step 4 = out-of-lineage odometer [asymmetric-compute v2.7 ladder + diverse non-v2.7 opponents + deck-paired cross-play + oracle-regret]; step 5 = diagnose iterate-erosion). Open Qs: chance-node/tile-draw handling, win-prob+score-distribution target form, decision-ranking metric. NEXT ACTION = step 1 + stand up the odometer in parallel.
- 2026-06-04 (pm-4) — **HIGHER-SIMS TARGETS ARE FLAT → ~0.47 (team first read this as an INFORMATION CEILING — ⚠️ SUPERSEDED by pm-5: it's the wrong gauge, outcome-corr not decision value).** Ran the sims=400 search-value iter (`RUN=searchval_s400`, same config as searchval_s200, SIMS=400) and re-ran Gate A on all three heads on the same held-out set (stage_b/iter_05, 600 games): **sims=400 head +0.4675 vs sims=200 head +0.4644 vs iter_01 +0.2888.** sims 200→400 = **+0.003 = within 1 SE = FLAT.** Doubling target search depth did NOT push the head past v2.7. **Reconciliation (the real finding): ~0.47 matches the C4a probe's from-scratch CNN (0.469 BLIND) almost exactly** — two unrelated setups (small outcome-CNN; 7M search-value net @ sims 200/400) both land at ~0.47 → **~0.47 is the information ceiling of predicting the final margin from (board,scalars)**, set by how much a Carcassonne mid-game position inherently determines the outcome — NOT by target source or sims. So the search-value target's achievement is **REACHING** that ceiling (overfitting fix 0.29→0.47), and no target (higher sims, lower variance) can EXCEED it from these inputs. Did NOT run sims=800 (cost discipline: 400 flat + the ceiling argument → 800 would be flat too). sims=400 policy gate +70.4 (n=100, consistent with +87/+96). **NET: the value head is now a working ~v2.7-level component (overfitting fixed, no longer the gross bottleneck), but the search-value lever does NOT break the ~0.47/v2.7 strength ceiling.** Remaining value work (Joshua: "do both") is about making the head USABLE in-search, not superhuman: **(1)** quantify + bank a fast NN-leaf (the λ-blend sweep incl λ1.0 pure-NN-leaf — running); **(2)** off-distribution value targets (train on MCTS-explored nodes, not just the trajectory) to fix the in-search calibration gap (Gate B λ0.5 = −36.6 < the λ0 +96.2 baseline) — Option 2 *enables* Option 1. The superhuman unlock remains measurement (no humans) / better inputs. `results.csv: searchval_s400_iter00_*`. Probe: `scripts/probe_heldout_value_corr.py` (multi-ckpt table).
- 2026-06-04 (pm-3) — **SEARCH-VALUE RETRAIN BUILT + first run; 🎉 GATE A PASS — the value-head overfitting is FIXED.** Built `search_value` as a generation-side `--value-target` mode (cleaner than the pm-2 spec — NO train_iter change, 6-array GameDataset schema unchanged): `NeuralMCTS.root_value()` returns root.Q (current-player POV, W/N from the root's mover); `selfplay.py` records it per learner ply into `values_arr` (no per-ply z-flip — root.Q is already POV-signed — length-guarded); `run_selfplay_iter.py` exposes the `--value-target search_value` choice; the cluster loop already threads `VALUE_TARGET`. 23 tests pass. Smoke confirmed the production orch-off path is FAST (gate-2's W=1 thrash was the ad-hoc generator, NOT the production loop). **Ran one iteration** (`RUN=searchval_s200`; 3-box synced to 5b21023 via git bundle; 400 games sims=200; warm from `stage_b/ckpt/iter_01.pt`; λ=0; pure self-play anchor=0; value-loss-weight 1.0 = clean A/B vs iter_01). **GATE A — held-out value-head corr vs TRUE margin** (`scripts/probe_heldout_value_corr.py` on stage_b/iter_05, 600 games, both ckpts on identical streamed batches): **new search-value head +0.464 vs iter_01 outcome head +0.289** (baseline reproduced first-hand). **The learned value head reaches v2.7's range (0.40–0.65) for the first time → per-position root.Q targets fix the overfitting**, exactly as the pm-2 diagnosis + gate-2 (+0.166 vs −0.04) predicted, now at production scale/power. Policy intact (loop's gate **+96.2 elo** vs HeuristicMCTS @ n=200, consistent with +87 — search-value training did not damage the policy; value-loss-weight stayed 1.0). **READ:** 0.464 sits at the LOW end of v2.7's range → the head now MATCHES v2.7; to BEAT it (the superhuman lever) the TARGET itself must be stronger → **higher-sims root.Q** (sims=200 root.Q ≈ v2.7-quality; 400/800 should exceed it). DECISION (Joshua, "both"): **(1) Gate B** = value-blend@play λ0.5 vs HeuristicMCTS — **RESULT −36.6 elo (89W/1D/110L) vs iter_01's −123** = +86 better blend behavior (head no longer poisons the search) but still net-negative vs the λ=0 baseline (+96.2) → the head MATCHES v2.7 but doesn't yet BEAT it (consistent with Gate A's 0.464 at the low end of v2.7's range). `results.csv: searchval_s200_iter00_valueblend05_vs_heuristic_baseonly_s200_n200`. **(2) sims=400 search-value run LAUNCHED** (`RUN=searchval_s400`, same config, SIMS=400, GATE_GAMES=100) — mechanism: root.Q is the SEARCH-refined v2.7 value, so deeper search → root.Q exceeds the raw leaf → the head can finally beat v2.7. Re-gate held-out corr (target: >0.464) next. Gate harness STREAMS held-out data (the load-all-into-RAM first cut **OOM'd the 31 GB 5800x at ~1200 games** — `--max-games` bounds it; lesson logged). **`stage-b-wiring` commits ffe823e + 5b21023 + 6f18ade + 5c102d6.** AS-BUILT spec: `docs/IN_LOOP_SEARCHVALUE_BUILD_2026-06-04.md`.
- 2026-06-04 (pm-2) — **VALUE HEAD OVERFITS = the real bottleneck; DECISION: BUILD the in-loop search-value retrain.** Gating the value-target-source lever surfaced the deepest diagnostic of the project: iter_01's **actual** value head goes **0.79 corr on its training games → 0.32 held-out** (iter_02/iter_05), *below* v2.7 (~0.4–0.65) — THAT's why blending it into search HURTS (off-distribution positions). Small-CNN C4a/C6 probes got ~0.5 held-out (better than the big net's 0.32 → the 7M net's capacity *hurts* generalization). **Root cause: the value target is the game OUTCOME — one label per game shared across ~144 positions → only ~600–1200 independent labels vs a 7M net → memorization.** Not representation (C4a refuted), not target saturation (C6 refuted) — **label scarcity → overfitting.** **gate-2** (`scripts/gate2_value_head_searchvalue.py`, 24 games sims=50, held-out): per-position **search-value (root.Q)** head **+0.166** vs outcome head **−0.04** → per-position targets fix the overfitting DIRECTION (mechanism confirmed); but underpowered (sims=50 search-value ≈ v2.7 0.42 → can't exceed; 24 games underfits → 0.166 << its 0.423 target). **DECISION (Joshua): BUILD the in-loop search-value retrain** — record `root.Q` per ply in production self-play + `--value-target search_value` in train_iter + one iteration warm-from-iter_01 at sims=200, then gate the new value head (held-out corr vs 0.32; value-blend-at-play vs the −123). Full spec: `docs/IN_LOOP_SEARCHVALUE_BUILD_2026-06-04.md`. Clear-eyed: payoff capped by root.Q quality (needs sims≥200 so the target beats v2.7), elo gain uncertain, superhuman still unprovable w/o measurement. INFRA: multi-worker single-board GPU eval thrashes the CUDA context (gate-2 gen ran W=1) → use the orchestrator/production loop for fast generation. **`stage-b-wiring` commits 994c6f3…2bd3962.**
- 2026-06-04 (pm) — **+87 IS A HARD CEILING; SCALING-CURVE VERDICT; CSV PROVENANCE FIX; C4/C6 SKETCH.** policy_scale (the overnight clean-policy iteration) **FAILED to climb past +87** — 7 gates pooled +38±10 SEM, ~50 elo *below* the +87 parent (warm-from-latest erodes the peak; no ratchet). Then a **test-time scaling sweep** (iter_01, n=100 screens, `results.csv: scalingcurve_iter01_*_base`): **Curve A** (net@S vs FIXED heur@200) climbs −74(s50)→+49(s100)→+85(s400) out of search-starvation then **flat top** — which I initially mis-called "saturation"; **reconciling vs results.csv (per the discipline rule) caught the error**: the flat top is a **weak-fixed-reference artifact** (can't widen the margin vs a shallow opponent), NOT saturation. **Depth-scaling is OPEN** (the only matched-depth evidence is iter_11's ladder +25.2@200→+56.7@800, but that's ~1.5σ AND the wrong net; iter_01 unmeasured — DEFERRED, modest effect). **#1 value-at-play-time probe: HURTS** (λ0→+35, λ0.25→+28, λ0.5→**−123**). **NET RESULT: +87 is a hard ceiling all three CHEAP levers fail to move** (policy-iteration, value-blend, depth-vs-fixed-ref). Confirms the foundational-audit thesis from a new angle: the v2.7 leaf caps learned strength and the value head is *worse* than v2.7, so it can't push past it. **CSV PROVENANCE FIX (commit 8bf0ce3, closes D21):** results.csv conflated eras (iter_11@200-vs-heur read as both +181.7 *river* and +25.2 *base*) — added `game`(river|base)+`code_rev` cols (70 rows backfilled: 9 base/61 river), eval harness now writes self-describing `manifest.json` per run (`carcassonne_ai/run_manifest.py`), `append_result_row.py` appends rows FROM the manifest (drift-proof). **NEXT LEVER = C4/C6 value-head rebuild** (`docs/CEILING_AND_C4C6_2026-06-04.md`): give the value head the inputs v2.7 uses (C4a farm-connectivity planes, C4b bag histogram, C4c open-feature planes, C4d farm scalars) + C6 de-saturated target. ⚠️ HONESTY FLAG: PHASE1_BUILD_SPEC's own gate said "if Stage B value-in-loop is flat/worse → ceiling is deeper than F-B1, RECONSIDER before C4" — and Stage B WAS worse → **C4 is a bet, not a sure thing.** DECISION: run a **cheap OFFLINE value-head probe first** (train a small value head WITH the C4 features on existing positions, compare held-out accuracy to v2.7 — ~1hr) to gate the ~1.5-day full retrain. Measurement wall ("meatbag") still deferred — it calibrates the ceiling, doesn't raise it. **→ PROBE RESULT (same day, `scripts/probe_value_head_c4.py` c26e468): C4a REFUTED.** Data has no stored states (can't compute v2.7/live-features cheaply) so the probe used the npz's terminal `ownership` planes as an ORACLE upper bound on farm-connectivity sight. A capacity-adequate value CNN on iter_01 self-play gains **nothing** from oracle ownership: BLIND corr **0.469** vs +OWN **0.447** (tied/worse; fixing model capacity made BLIND jump 0.28→0.47 and absorb the gain the under-capacity model got from ownership). → the value head is **NOT bottlenecked by farm-representation blindness**; **don't build C4a** (the ~½–1 day piece). Caveats: outcome-prediction proxy (not direct beat-v2.7), C4b/bag untested, from-scratch CNN. Remaining cheap value lever = **C6 only** (de-sat target, already built); if C6 doesn't break +87, the cheap path is exhausted → measurement / a fundamentally different value approach. This is the cheap-probe-first gate working: ~30 min killed a 1.5-day bet. **→ C6 PROBE (same day, `scripts/probe_value_target_c6.py` 1c862ce): also REFUTED.** Margins recover cleanly from the npz (0% hit the float32 ceiling); same deep CNN trained on tanh(m/15) vs tanh(m/40), scored by corr(output, true margin): t15 corr(all)=0.521 / corr(|m|>33)=**0.733**, t40 corr(all)=0.491 / corr(|m|>33)=**0.690** → de-saturation gives NO gain (marginally worse). The head already tracks big margins with the saturating target (corr 0.733 on |m|>33) — MSE on ±0.99 targets still carries graded gradient and corr is scale-invariant, so saturation never destroyed the ranking. **NET: BOTH cheap value levers (C4a representation, C6 target) are REFUTED — the cheap path to beat the v2.7 leaf is FULLY EXHAUSTED; +87 stands as the ceiling.** Remaining paths are all expensive/external (`docs/CEILING_AND_C4C6_2026-06-04.md` "Where that leaves us"): **(1)** a different value-TARGET SOURCE — every probe + the training used the noisy raw-MC game outcome (corr tops ~0.5); a lower-variance target (MCTS search-value / n-step bootstrap / predict-v2.7+residual) is the only untested lever with a real mechanism, but it's a genuine build+retrain not a cheap probe; **(2)** measurement (no humans available now); **(3)** accept ~strong-amateur+ and pivot to the analyzer (Phase 5). Today's net: cheap superhuman push has hit a well-characterized wall; ~1hr of probing ruled out ~2 days of builds.
- 2026-06-04 — **STAGE-B VERDICT + PIVOT TO POLICY-SCALING.** Stage B (value-in-loop, λ ramp 0→1, warm-from-iter_11) ran 11 iters. **(1) iter_1 (λ=0 clean-data policy retrain) = +86.9 elo vs HeuristicMCTS @ n=400 paired — CONFIRMED** (the n=200 screen reproduced EXACTLY; 245W/8D/147L=62.3%, ±17.9). ~+62 over iter_11 (+25.2 same plane) → clears the Stage-B success bar (+25) by a mile. **The bug-fixed base-only clean-data POLICY retrain is the real win** (largest confirmed gain on the clean game; iter_1@sims200 already > iter_11@sims800=+57). `results.csv: stage_b_iter1_vs_heuristic_baseonly_s200_n400`. **(2) value-in-loop is NET-NEGATIVE at current value quality** — every λ>0 iter warmed from the legit-best iter_01 and FELL to ~+35 → the v2.7 heuristic leaf is a BETTER self-play guide than the learned value head (C3 answered: value-in-loop fails *because* the value head is below the heuristic; the keep-chain freezing at iter_01 was CORRECT, not a noise artifact). UNTESTED cheap lever: value at PLAY-time (eval-time blend on a fixed net) ≠ value in self-play; may still help. **DECISION: pivot the overnight cluster to `policy_scale`** — pure λ=0 clean-policy iteration, warm-from-LATEST (`KEEP_MARGIN_ELO=-9999`), from iter_01, ITERS=12 — to test whether clean policy climbs PAST +87. Climbs → policy has headroom, keep scaling; plateaus → policy-only ceiling, next lever = fix the value head (play-time-only use, or C4 representation / C6 target) so it can beat the heuristic. New loop knobs `STAGE_B_BLEND_CONST` + `VALUE_TARGET` (ea36499); keep-best persistence F16 (cc35fed); claim self-heal (db018e3). STRATEGIC: policy-centric AZ WORKS (refutes the audit's "learned can't beat the heuristic"); superhuman now gated less by strength than by the MEASUREMENT WALL (no above-amateur reference).
- 2026-06-03 — **READ-ONLY AUDIT (independent agent; REVIEW_LOG D17-D22 / F16).** Confirmed C1/C2 fixes correct on code-read + value sign/scale consistent + deck-pairing correct. Flagged: **D17** Stage B doesn't cleanly isolate C3 (warm-from-iter_11 river-era + C6/C8/aug held → it's a SCREEN, not a clean C3 verdict); **D18** per-iter n=200 gate can't resolve its own +10-elo keep margin (±25 → adopt/reject is noise-driven); **D19** base `MCTS.search()` returns raw un-deduped child N (future MCTS-warmstart could resurrect C2); **D20** fair-chance determinization key omits deck order; **D21** no per-iter/eval manifests; **D22** deterministic-seed crash strands an iter (no `.failed` marker). **F16 FIXED** (keep-best persistence across relaunches). Verdict: treat live runs as SCREENS; gate Stage C on an n≥400 re-measure. Also fixed: STATUS "from-scratch warmstart" was FALSE (md5: warm.pt == iter_11.pt) → corrected.
- 2026-06-03 — WORKER/MODE RE-BENCH (current-code, blend=0.5). **(1) MODE: orch-off wins ALL 3 boxes ~2×** — orchestrator GIL dispatch is pure overhead for the CPU v2.7 leaf (even xeon's Quadro: off 5.87 > sh3 5.14 > orch 4.5; `sweep_selfplay.sh`, CSVs `wsweep/`). **(2) W: per-box, NOT uniform** (Joshua flagged uniform-W14 as a grid artifact — correct). Fine sweep `sweep_w.sh` (orch-off, FIXED seed = identical games per W, G=40, CSVs `wsweep2/`): **laptop W20** (peak 19.29, +12% vs W14; 24T), **5800x W14** (11.99 jump), **xeon W10** (12T, conservative; sweep cut early, lowest-impact). Was 5800x W16 / laptop W10 / xeon shards=2 W18. Stale +87% mixed-mode bench (2026-06-01) was river-era → superseded. Also: deterministic process provenance via CARC_RUN env-tag + `cluster_census.py`.
- 2026-06-03 — STAGE-B GATES 1+2 LOCKED (Joshua): success bar = ≥25 elo over iter_11 @ n=400 paired; blend curve = `0,0,0.15,0.30,0.50,0.70,1.0` (= `blend_for_iter()`). G-S3 gate design = last open decision before launch
- 2026-06-03 — STAGE-B WIRING (branch `stage-b-wiring`): value-blend-in-loop (G-S1, the F-B1 fix) + G-T1/T2 knobs + anchor stays blend=0; code-reviewed "safe to launch"; NOT launched (gated on Joshua's success-bar + blend-curve)
- 2026-06-03 — TEST-GAP CLOSE: C1/C2/F-B1 regression guards added to pytest (were script-only or absent; the suite green-lit all 4 shipped bugs)
- 2026-06-02 (late) — STAGE-A2 VERDICT (paired n=400): c_puct + cap FLAT → production unchanged; FPU the one lever (+45 screen, n=400 confirm pending)
- 2026-06-02 (late) — Work-stealing is the DEFAULT for eval sweeps (`--shared-claim`, not disjoint shards); cluster dashboard (heartbeat + status) added
- 2026-06-02 — RE-BASELINE VERDICT: iter_11 = +25.2 elo on the clean game (was +181.7); learned policy ≈ v2.7 leaf
- 2026-06-02 — PHASE 1 STAGED A→B→C (not "one batched retrain"); Stage A progress
- 2026-06-02 — PHASE 0 EXECUTED: C1+C2 bugs fixed & verified; RIVER DROPPED
- 2026-06-02 — FOUNDATIONAL AUDIT: the leaf was a symptom; clairvoyance DE-PRIORITIZED
- 2026-06-01 — Anchor-fraction self-play VERDICT: +39 over iter_11 OVERTURNED by the ladder
- 2026-06-01 — Confirm-before-kill: plateau-stop made symmetric with the keep decision
- 2026-06-01 — Strength-push loop wired: mixed-mode + anchor-fraction + plateau guard
- 2026-06-01 — Pipeline bench: orchestrator wrong for CPU v2.7 leaf → mixed-mode (+87% cluster); W≈48/fp16 superseded

**2026-05 — measurement / Path-B / leaf-tuning era**
- 2026-05-31 — PIVOT off value-as-leaf → measurement ladder; iter_11 +119 elo vs strong reference
- 2026-05-31 — Path B Step 9 VERDICT: pure NN-value leaf fails (-800) but it's a CALIBRATION CLIFF
- 2026-05-31 — Path B screening SUCCEEDED (value head crosses heuristic); loop extended to iter 24
- 2026-05-29 — Path B Steps 6–8: smoke PASS, collapse guard + value-corr; 3-box screening LAUNCHED
- 2026-05-29 — Path B Step E: farm scalars IN + free + flip-on wired
- 2026-05-29 — c=3 "+47" RE-VALIDATED at n=1600 → corrected to +18.5; default unchanged
- 2026-05-29 — Leaf flood-fill speedup: lazy per-leaf farm + city memo (1.70× leaf / 1.48× search)
- 2026-05-29 — Prioritize the find_farm speedup as next dev task
- 2026-05-29 — Engine fix: farmer-adjacency bug made farm scoring start-dependent
- 2026-05-28 — GOAL CHANGE: attempt genuinely superhuman play (overrides original prompt)
- 2026-05-28 — Measurement infrastructure: results.csv as source of truth + results discipline
- 2026-05-28 (evening) — Optuna eval-search softens the c=3 "+47"; flagged for re-validation
- 2026-05-28 — c_puct bump: eval-side validated, self-play-side on hypothesis (not yet A/B'd)
- 2026-05-26 — c_puct=1.5→3.0 free win at iter_B1: +47.2 elo n=400; "plateau" was stale-PUCT
- 2026-05-24 — Option B chain KILLED after B4; chain-vs-prev anchors lied; pivot to anchor-fraction
- 2026-05-20 — Network-distributed eval-server: TCP bridge for GPU-less box
- 2026-05-20 — Retroactive-validation pipeline: re-running 4 high-leverage past nulls at n=400
- 2026-05-20 (results) — 2 of 4 false-negatives recovered; iter_B1 promoted to global-best
- 2026-05-19 (late) — Deepsearch verdict revised: matched-regime sims=800 = +17 elo (within noise)
- 2026-05-19 — Deeper-search self-play didn't advance; v2.7 plateau confirmed across 3 strategies
- 2026-05-19 — Code-review loop: 14 fixes; work-stealing stale-recovery race accepted
- 2026-05-18 — Option 2 (NN value-head leaf blend) closed; plain v2.7 plateaued
- 2026-05-17 — self-play perf: hash-cache + get_side shipped; deeper memoization parked
- 2026-05-17 — closure-probability accuracy is not the leaf lever → pivot to Option-2
- 2026-05-17 — iter_02 flattens: policy saturated against fixed v2.7 leaf; compounding ceiling found
- 2026-05-16 — iter_01 retrain confirms data-scarcity hypothesis
- 2026-05-15 — PUCT c sweep: low c (≤1.0) catastrophic; default c=1.5 well-chosen
- 2026-05-15 — v3 leaf: cap tuning fitting n=20 noise; v2.7 cap=12 at local optimum
- 2026-05-15 — v2.5 dedup bug fix + cap/P re-sweep + cloud retrain: iter_00 +21pp over warmstart
- 2026-05-14 — v2.5 hyperparameter sweep: sims=200 sweet spot, cap=5 inverted-U optimum
- 2026-05-14 — orchestrator at W=6 hurts, W=12 helps — IPC vs batching tradeoff
- 2026-05-14 — v2.5 BENCH PASSES 83.3% vs Tier-1; production candidate
- 2026-05-14 — v2-diagnostic: bonus scale 4-7× v1 base — tanh saturates
- 2026-05-14 — virtual_score_v2 FAILS bench: ~47pp regression vs v1
- 2026-05-14 — Virtual_score diagnostic: closure-blindness + farm-composition opacity dominant
- 2026-05-14 — Sims sweep + uniform-priors ablation: policy worth ~18pp; sims=400 ceiling
- 2026-05-14 — The NN value head was the bug: NN priors + virtual_score flipped Tier-1 75%→40%
- 2026-05-14 — Cloud-prep: --leaf-eval v2_5 plumbed; MCTS virtual-loss 3× batch-fill
- 2026-05-13 — Tier-1 baseline destroys warmstart_canonical AND iter_12 → recipe-ceiling confirmed
- 2026-05-13 — Phase B cloud bench: W=32 optimum, full iter 5.2 min, h2h OOM falsified
- 2026-05-13 — Phase A cloud bench: 5-loop MCTS perf patches validated
- 2026-05-13 — MCTS perf loop 2/3/4: tile/rotation/str caches, placed_coords set
- 2026-05-13 — MCTS perf loop 1: engine state __deepcopy__ cut wallclock 3.3×
- 2026-05-13 — Orchestrator multi-process pool: NULL, workers are bottleneck not GIL
- 2026-05-13 — Phase 4 v6 cloud: 20 iters, iter_12 = 70% wr (new peak above v5's 65%)
- 2026-05-12 — Phase 4 v5 HALTED at iter 9 (3 anchor FAILs); peak iter 6 = 65%
- 2026-05-12 — Phase A cloud bench: W=96 optimum (15% faster than W=48)
- 2026-05-12 — GPU orchestrator landed + validated, 10-14% slower local (expected)
- 2026-05-12 — MPS test: W=48 + fp32 + no-MPS optimal
- 2026-05-12 — Cloud bench: W=48 + fp32 optimum on RTX 5090 + 48-core EPYC
- 2026-05-11 — Phase 4 v2 recipe FAILED acceptance: mix=0.3 floor not enough
- 2026-05-10 — Chain-vs-prev ELO discredited; 30-iter "PASS" was absolute regression
- 2026-05-08 — Virtual-loss + batched-eval MCTS landed

**2026-04 — Phase 0-4 foundation era**
- 2026-05-03 — Phase 4 smoke PASS: 5 iters, ELO 0→176
- 2026-04-29 — Phase 3 closure: v2 the warmstart, proceed to Phase 4
- 2026-04-28 — Phase 3 v1 acceptance + v2 retry plan (sharper tau)
- 2026-04-28 — Engine bug: city_diagonal_top_left_road shared description
- 2026-04-28 — Phase 3 production gen sized to 100K not 500K
- 2026-04-28 — Phase 3 production prerequisites landed
- 2026-04-28 — Phase 3 smoke: HEURISTIC wins, scale to 500K (pause for prereqs)
- 2026-04-28 — External review findings + bug fixes
- 2026-04-28 — Phase 3 network capacity: 6 ResBlocks × 96 filters
- 2026-04-28 — Phase 2 acceptance: MCTS(s=20) 96/100 vs random + Q-tiebreak fix
- 2026-04-27 — Phase 4 prereq: get_valid_moves performance strategy
- 2026-04-27 — Phase 1 quick-bench results (per-call cost map)
- 2026-04-27 — Phase 1 action-space encoding: phase-aware flat (size 2511)
- 2026-04-27 — Window size is a Game config parameter
- 2026-04-27 — Parallel-worker count: full SMT fan-out (16 on 5800X)
- 2026-04-27 — Phase 0 measurement results (random play only)
- 2026-04-27 — Vendor upstream repos rather than git submodules
- 2026-04-27 — Reward normalization: tanh(diff / 15)
- 2026-04-27 — Window-overflow handling: drop the game
- 2026-04-27 — Patch engine: ties award full points to all tied players
- 2026-04-27 — Patch engine: lazy tkinter import
- 2026-04-27 — Patch engine: silence print statements behind flag

## Format

```
## YYYY-MM-DD — [decision title]
**Context:** what problem we were solving
**Options considered:**
  - A: [description, pros, cons]
  - B: [description, pros, cons]
  - C: [description, pros, cons]
**Decision:** chose [option]
**Reason:** [why]
**Reversal cost:** low / medium / high
**Phase:** [which phase this was made during]
```

## Decisions

## 2026-06-09 (leaf) — Compact flat-union-find leaf rewrite (logic-exact, default OFF) + a discovered pre-existing leaf nondeterminism

On branch **`leaf-rewrite`** (isolated worktree, off `stage-b-wiring`@4ea8a46 while attempt-#2 ran on the cluster — no commits to stage-b-wiring, no bundle refresh, NO benchmarking). Executes the "compact/cache-friendly leaf rewrite" lever from the 2026-06-09 bandwidth entry / BACKLOG "2026-06-09 — Compact leaf" entry.

**What it does.** `src/carcassonne_ai/compact_leaf.py` replaces the v2.7 leaf's object-graph farm/city flood-fills (`FarmUtil.find_farm` / `CityUtil._compute_city` — pointer-chasing over Tile→FarmerConnection graphs, the RAM-bandwidth source) with a flat union-find: enumerate nodes → small int ids → parallel edge arrays → `parent[]` union-find → reconstruct the engine's own `Farm`/`City` objects. It pre-populates the SAME `_farm_cache`/`_city_cache` dicts the engine already reads, so `find_farm`/`find_city` resolve every query as a cache hit and the BFS never runs — **zero engine edits**. Behind `USE_COMPACT_LEAF` (default **False**); shared into `virtual_score`'s deepcopy snapshot (valid because the state deepcopy shares Tile/FarmerConnection refs → `id()`-keys survive).

**It is LOGIC-EXACT.** Gate `scripts/reconcile_compact_leaf.py` (n=400, production v2.7 env), compact-ON vs the production object-BFS path: **0 mismatches** across **935,018 farm-partition + 579,575 city-partition + 14,400 `count_final_scores` `scores[]` + 28,800 base `virtual_score`** checks. Partitions, end-scores, and the base value are bit-identical. pytest: full suite green OFF (no regression), leaf suite green ON.

**But it surfaced a PRE-EXISTING leaf nondeterminism (the real finding).** `virtual_score_v2` int differs in **2–12 / 28,800** evals (±1 pt). Root cause is NOT compact: the closure-anticipation bonus (`_closure_anticipation_bonus`) sums non-associative floats (0.2-multiples) in the iteration order of a **set** (`farm.farmer_connections_with_coordinate`), which is keyed on enum hashes → **randomized per process by `PYTHONHASHSEED`**. So two self-play/eval workers already compute different `virtual_score_v2` ints for the **same position** in ~1e-4 of cases (max pre-round drift ≈1e-15, flipping `int(round())` only where a score sits exactly on a `.5` banker's-rounding boundary). Evidence: identical gate config → 2 flips in one process, 12 in another. The 2026-05-29 fix made `find_farm` start-independent but left this summation order hash-dependent. **The leaf is the measurement ruler, and it is currently mildly non-reproducible across processes.**

**Fix offered: `CANONICAL_BONUS_SUM`** (default **False**) — accumulate the bonus with `math.fsum` (the correctly-rounded, order-independent sum). With it on, the gate is **0 / 28,800** (`--canonical`, drift 0.0) → compact becomes a TRUE bit-exact drop-in AND the leaf becomes deterministic across processes. **Why default OFF / not flipped now:** turning it on changes production's exact output vs the **currently-running** attempt-#2 flywheel by those same ~1e-4 ±1 flips, so it must be a deliberate decision bundled with the compact merge (Phase 4), never mid-run.

**NOT yet a measured speedup.** The pure-Python union-find still allocates engine objects during enumeration and runs interpreted; the bandwidth win needs the core compiled (numba `cache=True` to dodge per-worker JIT warmup, or Cython-AOT). numba is NOT installed and installing into the shared venv could perturb the flywheel, so it + the benchmark were deferred to Phase 4 (quiet box). The core (`_label_components`) is written as a pure-int kernel over parallel arrays specifically so it can be `@njit`'d later without touching enumeration/reconstruction. **Success criterion for Phase 4 is not "faster" but "moves the bandwidth wall"** (per-worker erosion curve flattens, saturation-W rises above 16 — `scan_loww.sh`).

**Options considered.** (a) Accept the ULP int drift as within-noise — rejected as the default because the leaf is the ruler. (b) Replicate production's exact (arbitrary) set order in compact — infeasible/fragile (depends on which meeple populated the shared cache first). (c) Canonicalize summation (fsum) on both paths — chosen as the recommended closer; it's strictly more correct (also kills the latent hash-seed nondeterminism) and is a clean toggle.

Files (all on `leaf-rewrite`, commit e4902dc): `src/carcassonne_ai/compact_leaf.py` (new), `virtual_score.py` + `virtual_score_v2.py` (toggles; OFF path byte-identical), `scripts/reconcile_compact_leaf.py` (gate), `tests/test_compact_leaf.py` + `tests/conftest.py` (new), `docs/COMPACT_LEAF_REWRITE_ASBUILT_2026-06-09.md` (full report).

**Phase:** Phase 4 (correction-era perf lever; gated, not in production).

## 2026-06-03 — STAGE-B WIRING built on a branch (value-in-loop, the F-B1 fix) + test-gap close

Done overnight (Joshua authorized autonomous progress on the decided path, stop at launch). All on branch **`stage-b-wiring`** (off `gpu-orchestrator`@e595d6c; merge is Joshua's call). Stage B is the cheap retrain that tests whether the learned value head, finally IN the search loop, beats the v2.7 leaf ceiling on the clean base-only game.
- **G-S1 (7fa696d, b2ba341, bfbd47d):** `run_selfplay_iter.py --value-blend λ` blends the NN value into the leaf `(1-λ)·tanh(vs2/15) + λ·v_nn`; the 3 guard sites now read the per-iter value (not import-time `DEFAULT_CONFIG`); `blend_for_iter()` ramp in `run_pathb_cluster_loop.sh` is **DEFAULT OFF** (`STAGE_B_BLEND=1` enables; the curve is a PROPOSAL Joshua tunes). The fixed iter_11 anchor stays **blend=0** (plays pure v2.7 as trained; plan risk #4) — incl. its orch eval-server forced policy_only (review Issue 1, saves 8GB-box VRAM). Smoke-verified: same-seed self-play differs between blend 0.0 and 0.9 (the value reaches the leaf + steers the search).
- **G-T1/T2 (8965852):** `LR_SCHEDULE` (none|cosine) + `VALUE_LOSS_WEIGHT` env knobs into the loop train step; defaults = current behavior; Stage B un-starves the value head (e.g. cosine / 3×).
- **Code review:** subagent verdict "**correct + safe to launch**" — found + I fixed 1 issue (anchor orch server wasted full-forward → OOM-margin on 8GB). Otherwise clean (propagation both paths, default-off byte-identical, score-diff currency matches, no set-u bugs).
- **Test-gap close (be46466):** the suite had green-lit all 4 shipped bugs (C1/C2 guarded only by un-wired `scripts/verify_*.py`; F-B1 untested). Added pytest guards: `test_farm_dedup_c1` (C1), `test_mcts_transposition_c2` (C2), `test_value_in_loop_fb1` (F-B1: value_blend steers the search — guards the wiring). All pass with teeth-assertions (they exercise the bug-prone paths). #4 cross-proc determinism + #5 tied-scoring still open.
- **NOT launched.** Gated on Joshua: (1) pre-registered success bar (suggest ≥25 elo over iter_11 @ n=400 paired), (2) blend curve. Then warm.pt train + Xeon OOM smoke + G-S3 (gate→HeuristicMCTS). Package: `docs/STAGE_B_LAUNCH_READINESS.md` + `docs/STAGE_B_G-S1_PLAN_2026-06-03.md` + `docs/TEST_SUITE_GAP_ANALYSIS_2026-06-03.md`.
**Phase:** Phase 1 (Stage B readiness; build complete, launch pending).

## 2026-06-02 (late) — STAGE-A2 VERDICT: c_puct + cap FLAT (production unchanged); FPU the one live lever

The post-Phase-0 re-sweep owed since the C1/C2 bug fixes (which moved scoring + visit-distribution optima). Paired (G-M2) n=400 head-to-head, iter_11 both sides, only the knob-under-test differing, work-stealing across 3 boxes. Rows: `results.csv: verdict_*`.
- **Pairing validated:** `self_c3` (iter_11 vs itself, identical c=3.0) = 49.5% / z=−0.20. The *unpaired* wave-1 self-cell was 42% — that 8pp was pure first-player harness bias, now cancelled, and variance ~halved (se 2.5pp). This is why we pair.
- **c_puct FLAT across 1.5/2.0/2.5/3.0:** c15 +15.6 (z=0.90), c20 −17.4 (z=−1.0), c25 −15.6 (z=−0.90) — all n.s. vs c=3.0. The n=100 "+18pp at c=2.0" wave-1 screen **reversed** → it was harness bias + noise (textbook lone-spike-is-noise, the c=3 lesson again). **Production c=3.0 stays.**
- **cap FLAT** (wave-1: cap=8/16 ≈ cap=12) → **cap=12 stays.**
- **FPU is the ONE lever showing signal:** fpu_reduction=0.2 (vs legacy q=0) = 56.5% / +45.4 elo / **z=+1.85** at n=200 — the only non-flat cell in the entire sweep. **Per our own discipline this is a SCREEN, not a verdict** (z<2σ) → must confirm at n=400 paired before promoting `fpu_reduction` to the production NeuralMCTS config. fpu04 (0.4) finishing. FPU also gets re-tuned at Stage B (G-S4), so the confirm can fold into the Stage-B sweep.

**Net production change: NONE** (c=3.0 + cap=12 both confirmed). The value of this run was negative (ruling out phantom levers) + validating the paired/work-stealing methodology for everything downstream.
**Phase:** Phase 1 (Stage A re-sweep, closes the C1/C2-owed re-tune except FPU).

## 2026-06-02 (late) — Work-stealing is the DEFAULT for eval sweeps; cluster dashboard added

**Work-stealing (Joshua: "we need to do work stealing whenever possible").** The Stage-A2 verdict first ran with **disjoint per-box seed shards**, which stranded the fast laptop idle ~24 min on the foregone c25 tail while slower boxes ground on. Killed + relaunched with `--shared-claim`: all boxes point at the SAME full seed range and atomically claim `(seed, player)` via O_CREAT|O_EXCL `.claim` sidecars; the on-disk `.json` exists-check is the permanent done-marker so the existing 318 games were reused. **Decision: prefer `--shared-claim` over disjoint shards for ALL eval sweeps**, not just self-play loops. Wired the launcher `scripts/sweep_verdict_steal.sh` (12153b6) and back-ported `--shared-claim` + `--paired` into the ladder gauntlet `eval_net_vs_heuristic.py` (14bcb75) for the upcoming high-sim reference rung. **Known residual:** claim-based stealing has a *tail* inefficiency — once all remaining seeds are claimed-in-flight, a box that drains its queue exits rather than re-stealing (claims only expire after `claim-stale-secs`=90min), so the last ~Σworkers games finish on whichever box is fastest. Acceptable (the bulk idle is gone); a future refinement is a short stale window or queue-drain re-attempt.

**Cluster dashboard (Tier A + B; fe27b9c).** `scripts/cluster_heartbeat.py` (stdlib-only, runs on each box with any `python3`) samples CPU%/loadavg/GPU(util,power,VRAM)/running-job every 4s → `<share>/status/<host>.json`. The CIFS share is the bus — boxes never talk to each other, sidestepping cross-Tailscale networking. `scripts/cluster_status.py` reads them: no flag = consolidated text table (replaces ad-hoc ssh-`ps` bash for my status checks — kills the rewrite-bash-every-time anti-pattern); `--serve PORT` = a tiny stdlib HTTP server rendering a live auto-refreshing web page (Tier B, the one Joshua picked). Tolerates laptop GPUs reporting `[N/A]` power.limit (parse per-field, don't drop the GPU). Reachability gotcha: server binds inside WSL2 (NAT'd) while tailscaled is on the Windows host → reach from Mac via SSH `-L 8765:localhost:8765` or a Windows `netsh portproxy` (for tailnet/phone); WSL mirrored-networking is the clean long-term fix but needs a WSL restart (deferred — would kill running jobs). The dashboard immediately surfaced a real read: the laptop runs GPU-bound on eval (load 12/24 but 4070 at 97%), and the claim-tail idle above.
**Phase:** tooling (supports Phase 1+).

## 2026-06-02 — RE-BASELINE VERDICT: iter_11 = +25.2 elo on the clean game (was +181.7) — the learned policy adds ~nothing over the v2.7 leaf

**The headline empirical result of the Phase-0 cleanup.** iter_11 (our "strongest" checkpoint) vs HeuristicMCTS, n=400, matched c=3.0/sims=200, on the NEW base-only **bug-fixed** game (C1 farm-dedup + C2 MCTS-transposition fixes, River dropped), 3-box disjoint seed shards 700000–700399:
- **212W / 5D / 183L = 53.6% = +25.2 elo (±17.4, ~1.45σ).** Row: `results.csv: ladder_iter11_vs_heuristic_baseonly_n400`.
- **COLLAPSED from the old-game +181.7 elo** (`ladder_iter11_vs_heuristic_n400`, measured on River + buggy farm scoring).

**Interpretation.** ~85% of our headline "beats strong heuristic-search by +181.7" was **game-artifact**: River, the buggy farm scoring, and the fact that iter_11 trained on that exact broken game (so both the checkpoint and the apparent edge lived in the old distribution). On the real game the learned policy is **statistically ≈ the v2.7 leaf** (+25 at 1.45σ — barely positive, not the +180 we believed). This is the audit's central thesis (F-B1: the learned value was never doing the work; the hand-crafted leaf was) measured at verdict strength.

**Consequences.**
- This is NOT new failure — it's the bill for cleaning the foundation, predicted when the n=8 smoke flashed 0.375. The infrastructure (pipeline, 3-box cluster, warmstart, MCTS, val-corr→0.81) is sound; the *game underneath it* was rotten and is now fixed.
- **We finally have a trustworthy baseline:** clean game, n=400 verdict, independent non-saturated reference, correct scoring. Numbers from here are real.
- **Stage B is now unambiguous and low-risk:** there's no real learned strength to lose (we're at ≈heuristic), so the only question that matters is whether value-head-in-the-loop can build genuine learned strength past the v2.7 ceiling on the clean game.
- **iter_11 is no longer a meaningful champion.** Stage B retrains from scratch on the real game. The 12 old screening checkpoints are off-distribution.
**Phase:** Phase 1 (Stage A re-baseline).

## 2026-06-02 — PHASE 1 STAGED A→B→C (not "one batched retrain"); Stage A progress

**Context.** The correction plan said "batch C3+C4+C5+C6+C7+C8 into ONE retrain (pay it once)." A 3-agent review of the Phase-0 work + a direct code read changed the calculus.

**Decision: stage by QUESTION, cheapest-informative-first** (Joshua-approved). Full spec: [docs/PHASE1_BUILD_SPEC_2026-06-02.md](docs/PHASE1_BUILD_SPEC_2026-06-02.md).
  - **Stage A** (no retrain): re-baseline on the new game + cheap code (symmetry aug, gate, exploration, target mode) + the owed re-sweeps.
  - **Stage B** (cheap retrain): does the value head IN the search loop (C3, the F-B1 root cause) beat the v2.7 ceiling with NO new planes? Gate Stage C on it.
  - **Stage C** (expensive): representation planes (C4), only if Stage B breaks upward.
**Reason:** C4 (representation) is ~1 day of engineering and is independent of whether C3 helps. Testing the near-free root-cause lever first de-risks the expensive build. "A few days of real science" > one big bet we can't attribute.
**Reversal cost:** low (it's a sequencing choice).

**Review findings that shaped this (3 agents, no new critical bugs):**
- **F-B1 CONFIRMED:** prod loop `run_pathb_cluster_loop.sh:283` passes `--leaf-eval v2_5`; the `nn` argparse default is overridden. The net value really never drove a move.
- Negamax signs, canonical form, action round-trip, terminal scoring re-verified clean.
- **C2 PUCT-selection residual** (pre-existing, beyond the original C2 fix): `_select_child_puct` double-scored transposition-collided actions. FIXED 2026-06-02 (commit 3a31d2a) via an incremental alias structure on `_NeuralNode` + `_link_child`; base `MCTS` selection left unchanged (it's the reference ladder — changing it breaks comparability). Verified by an extended `scripts/verify_mcts_transposition_fix.py`.

**Stage-A work landed (committed + pushed):**
- **C5 symmetry augmentation DONE** end-to-end (rotate board/action/policy + dataset augment + streaming-loader flag `--augment-rotations`, default off; 16 tests). 90° only; reflection deferred.
- Loop orchestrator **version-controlled** (`scripts/run_pathb_cluster_loop.sh`).
- **3 boxes synced** to HEAD via an offline git **bundle** on the CIFS share — the remotes have no github DNS over Tailscale, so `push`+`pull` doesn't work; `git bundle create` on the share + `git fetch <bundle>` + `git reset --hard` on each box does. Reusable pattern.
- **Re-baseline DONE:** see the headline entry above — iter_11 +25.2 elo on the new game (was +181.7).
**Phase:** Phase 1 (staging + Stage A).

## 2026-06-02 — PHASE 0 EXECUTED: C1+C2 bugs fixed & verified; RIVER DROPPED

**Context.** Acting on the foundational-audit correction plan. Joshua confirmed "drop rivers" and "get started on all those bug fixes."

**What was done (commit follows this entry):**
- **C1 — farm scoring double-count FIXED.** `count_farm_points` (points_collector.py) now dedups touched cities by `frozenset(city.city_positions)` (mirrors virtual_score_v2.py:348) instead of relying on an identity-keyed `set[City]`. Added value `__eq__/__hash__` to `City` (defense-in-depth). **Verify (no retrain):** `scripts/verify_farm_dedup_fix.py` n=150 (876 farms) — fixed score equals an independent position-set-dedup reference on ALL farms; 16.3% of farms were over-scored pre-fix (matches the audit's ~17%), 633 spurious points removed, worst single farm +12.
- **C2 — MCTS transposition visit double-count FIXED.** Rotationally-symmetric tiles emit ≥2 rotations → identical board → the transposition table (`self._nodes`, keyed by board string) hands both action slots the SAME child object, so reading `children[a].N` per action double-counts visit mass. Added `NeuralMCTS._deduped_children` (collapse actions sharing a child object to the lowest-index action) and routed `root_visit_distribution`, `select_for_training`, `best_action`, and base `MCTS.best_action` through it. **Verify (no retrain):** `scripts/verify_mcts_transposition_fix.py` sims=64 — 17.5% of decision nodes had collisions (audit ~20%); the fixed visit vector is collision-free and its mass equals the unique-child sum. (HeuristicMCTS.best_action outcome was provably robust to the collision — same child object → same board — so the +181.7 ladder numbers were NOT corrupted by C2; only NeuralMCTS policy *targets* were.)

**Decision: DROP RIVER (Joshua confirmed).**
**Options considered:**
  - A: keep River (status quo) — more tiles/strategies, but competitive/world-championship play is base-only and the River opening is a non-scoring setup variant we'd be optimizing for needlessly.
  - B: drop River → base-only (BASE tile set, FARMERS). Matches the target meta. Caveat (Joshua): base-only opening is MORE chaotic (no scripted river spine) → deeper/sharper game AND higher draw-variance.
**Decision:** B. `Game` default `tile_sets=(TileSet.BASE,)`; `features.DECK_NORM 85→72` (base deck = 72 tiles vs 83 with River). Engine retains River support for explicit callers; production self-play/eval/training now base-only. Test harness fix: `test_farm_scalars._play` ply cap 150→130 (base games terminate at ~141-144 plies; 150 returned a terminal board and crashed `get_valid_moves`). Full suite green (323 passed, 1 skipped).
**Reason:** C4 (representation planes) forces a from-scratch warmstart anyway → this was the free moment to switch the rule scope. Aligns the whole pipeline with the actual superhuman target meta.
**Reversal cost:** low (flip the default back; engine code unchanged).
**Consequence:** existing river-trained checkpoints (iter_11 etc.) are now off-distribution — expected; Phase 1 retrains from scratch base-only. Carry-over re-sweeps still owed (do alongside retrain prep): v2.7 caps (C1 shifts scoring optima) and c_puct/FPU (C2 changed the visit distribution).
**Phase:** Phase 0 (correctness) + folded-forward scope decision.

## 2026-06-02 — FOUNDATIONAL AUDIT: the leaf was a symptom; pivot to correctness/architecture fixes; clairvoyance DE-PRIORITIZED

**Context.** After the residual-leaf soft-no, the question became "why has AlphaZero failed so badly on a game we *accidentally made deterministic*?" First finding: the MCTS never modeled chance — it descends the engine's pre-shuffled deck in true order (clairvoyant single-determinization; documented in mcts.py:18 as a deliberate Phase-2 simplification for the OLD modest goal, never re-audited when the goal changed to superhuman 2026-05-28). Then a 6-agent parallel audit swept every foundational domain.

**Findings (full evidence: docs/research/foundational_audit_2026-06-02.md; plan: docs/CORRECTION_PLAN_2026-06-02.md).** Multiple agents converged independently. Two LIVE correctness bugs (verified in code): (C1) farm scoring double-counts cities — `count_farm_points` sets `City` objects with no `__eq__/__hash__` → identity dedup → ~17% of farms over-scored (up to +69pts, asymmetric) → **corrupts the reward AND the v2.7 leaf**; (C2) MCTS keys children by action → rotationally-symmetric tiles share a node → ~20% of nodes **double-count visits in every policy target**. Plus architectural caps: the learned **value head is never in the search loop** (prod uses the v2.7 leaf; net value is a side-regression that never drives a move → can't bootstrap past the teacher = root of the calibration cliff); representation **blind to farm connectivity + bag composition**; no symmetry aug; saturated `tanh(diff/15)` value target; advisory loop gate (chain random-walks).

**Clairvoyance screen (n=76, iter_11, sims=200/c=3): clairvoyant vs fair = 36W/40L = 0.474 (−0.5σ) = DEAD EVEN.** Future-sight is NOT a strength lever.

**Decision.** (1) Reframe: the leaf ceiling was a *symptom*, not the disease. Stop leaf-tuning. (2) Fix C1+C2 FIRST (cheap, verify without a retrain — they corrupt every downstream measurement). (3) Then ONE batched retrain turning on the real engine: value-head-in-loop + representation planes (farm connectivity + bag histogram) + drop River (pending Joshua) + symmetry aug + de-saturated target + conditional gate. (4) **Exact chance nodes DEMOTED** to value-target-quality (Phase 3), since the screen proved clairvoyance isn't a strength lever — saved a multi-week build of the wrong thing.
**Reason.** A corrupted reward + corrupted policy targets + a value head that never drives search make every prior strength number partly contaminated and explain the calibration cliff mechanically. Fix the foundation before any more strength work.
**Reversal cost:** medium (C1 shifts v2.7 cap optima → re-sweep; Phase-1 changes net input → retrain from warmstart).
**Phase:** 4 (foundational correction).
**Built this session:** `NeuralMCTS(fair_chance=…)` + `scripts/diag_clairvoyance.py` (commit e88d82b); draw-luck control variate `diag_leaf_gate.py --with-luck` (×1.21 measurement win, commit 7e7ebf1).

## 2026-06-01 — Anchor-fraction self-play VERDICT: ~~real +39 over iter_11~~ → OVERTURNED by the ladder (no absolute gain)

**⚠️ UPDATE (same day, ladder result `ladder_iter4_vs_heuristic_n400`): the +39 below was a FALSE POSITIVE.** iter_4 vs HeuristicMCTS @ c=3.0 n=400 = +165.1 elo vs iter_11's +181.7 → **diff −16.6 ±27.7 = 0.6σ = TIED** (iter_4 nominally *lower*). On the absolute, independent anchor at production c=3.0, **iter_4 is NOT stronger than iter_11.** The head-to-head +39 (c=1.5, vs the same-lineage iter_11) was **anchor-overfitting** (iter_4 trained 30% vs iter_11 → learned to beat *it specifically*) ± a c=1.5 artifact — classic [[feedback_anchor_before_scaling]]: relative-vs-lineage-anchor ≠ absolute strength. **anchor-fraction did NOT break the v2.7 leaf ceiling.** The "takeaways" below (esp. #1 "ceiling NOT absolute") are RETRACTED; the leaf ceiling stands. New lessons: (a) anchor against an INDEPENDENT reference, never a same-lineage one; (b) the ladder caught a false positive the head-to-head would have shipped — always confirm a relative gain absolutely. **Next lever = leaf rework (learned-residual leaf).** The original (now-superseded) reasoning is preserved below for the record.

**Context.** First full run of the anchor-fraction strength loop (`RUN=pathb_anchor`: warm-chain from iter_11, 30% of self-play games vs the fixed iter_11 anchor, all 3 boxes). Ran iters 0–6, then self-stopped via the new confirm-before-kill (plateau confirmed). The open question from the prompt-superseding goal: can the *learned* signal exceed the hand-crafted v2.7 leaf, which was hypothesized to cap strength near iter_11?

**Result (verdict-grade, n=400, c=1.5 sims=200; `results.csv` `anchor_*`):**
- **iter_4 vs iter_11 = 55.6% = +39.3 elo / 2.25σ → REAL gain.** iter_4 is the new best checkpoint.
- iter_6 vs iter_4 = 49.1% (equal) — the two best ckpts are the same strength despite n=40 iter_11 gates of 57.5 vs 68.8 ⇒ those swings were **noise**.
- iter_0 vs iter_5 = 46.5% (floor check, n=100) — chain is **non-monotonic**: checkpoints bounce (iter_4/iter_6 ~+39 over iter_11; iter_0/iter_5 ~iter_11 level). Pipeline healthy (val-corr climbed 0.18→0.81 monotonically, entropy OK).

**Decision / takeaways:**
1. **The v2.7 leaf ceiling is NOT an absolute wall** — anchor-fraction self-play produced a checkpoint measurably stronger than iter_11. This was the open hypothesis (see the "Value-as-leaf CLOSED" entry, which said lifting the ceiling "needs a genuinely stronger *learned* signal — what anchor-fraction is meant to produce"). It produced one. Modest (+39), but real.
2. **The gain is small and noisy/non-monotonic** — not a steady climb; the best checkpoints happen to land ~+39, others sit at iter_11. So anchor-fraction is a real but weak lever; the leaf remains the bigger one for a *large* gain.
3. **Methodology, logged hard: per-iter n=40 gates are SCREENS, not verdicts.** The +39 real signal was invisible/misleading at n=40 (gates swung 37.5–68.8%); only n=400 resolved it. I flip-flopped twice reading the n=40 trend (null→"climbing"→noise→real). Reinforces [[feedback_results_table_source_of_truth]] and the n=100-screen/n=400-verdict rule — and validates the confirm-before-kill design (it correctly auto-escalated to n=400 at the plateau).

**Caveat.** Measured at the loop gate's c=1.5, not the ladder's c=3.0 — iter_4's *absolute* strength vs HeuristicMCTS not yet re-laddered (NEXT #1).
**Reversal cost:** n/a (a measurement). **Phase:** 4.

## 2026-06-01 — Confirm-before-kill: make the plateau-stop symmetric with the keep decision

**Context.** The plateau guard (entry below, item 5) hard-`break`s the loop after MAX_FLAT(=2) consecutive n=40 gates fail to beat the running best. Joshua flagged the asymmetry: a *positive* n=40 gate we (correctly) distrust as noise and demand more data — but a *negative* streak we acted on by killing the whole run. Same ±8% noise, opposite credence. Worse, the guard compared each gate against the running **max** (`best_wr`), so a lucky early high (e.g. iter_1's 55%, when the true rate was ~47%) inflates the bar and biases the counter toward false-trips. And the cost asymmetry runs the same way: a false-positive wastes ~1 iter (~1 hr); a false-negative abandons a working approach and sends us to the much harder leaf rework.

**Options considered:**
  - A: Leave it — accept that n=40×2 is the stop signal. Cheap but kills on screen-grade evidence; violates our own "n=400 = verdict, never promote/demote on a screen" rule.
  - B: Just raise ANCHOR_GAMES/MAX_FLAT — tightens but multiplies *every* iter's gate cost, and still a fixed-threshold guess.
  - C: **Confirm-before-kill** — when the flat streak trips, run ONE n=CONFIRM_GAMES(400) head-to-head of **latest iter vs current best** (net-vs-net), and only stop if latest fails CONFIRM_THRESH(0.54, ~1.5σ over 0.5 at n=400). Else the streak was noise → adopt latest as best, reset, continue.

**Decision:** chose **C**. Live in `~/run_pathb_cluster_loop.sh` (`confirm_gate()` + rewritten plateau block; backed up to `code_sync/`).

**Reason / properties:**
- **Symmetric** — the kill now needs the same verdict-grade (n=400) evidence we'd demand to believe a positive.
- **Ratchet-immune** — confirm compares latest-vs-best *directly* (head-to-head), not against the noise-inflated iter_11 ref.
- **Reversible** — a positive confirm resets and continues; a confirmed stop logs the follow-up (gate best vs iter_11 @ n=400 to classify success-vs-null before the leaf pivot).
- **No false-kill on infra failure** — if the confirm gate yields no verdict (boxes die / share hiccup mid-confirm), it resets flat and re-confirms next plateau rather than killing on no data.
- Two bugs caught while wiring: (1) the eval script zero-pads vs-iter (`:02d`) so the confirm's output-dir lookup had to match (`iter_NN_vs_ON`), else `wait_for_count` hangs → false "kill"; (2) the infra-failure fall-through above.

**Reversal cost:** low (env knobs `CONFIRM_GAMES`/`CONFIRM_THRESH`; set `CONFIRM_GAMES=0`-style or revert the block to restore the bare guard).
**Phase:** 4 (self-play strength push). **Activates on next driver restart** (running driver parsed the loop pre-edit).

## 2026-06-01 — Strength-push loop wired: mixed-mode + anchor-fraction + plateau guard (ready to launch, HELD for go)

**Context.** With the bench done (entry below), wired the bench-optimal config + the long-deferred anchor-fraction strength loop into `~/run_pathb_cluster_loop.sh` (the untracked production launcher; backed up to `code_sync/`).

**What was wired (all 6, two smokes clean):**
1. **Mixed-mode self-play** — `selfplay_mode()` per box: 5800x orch-off W=16, xeon `--orch-shards 2` (W=18), laptop orch-off W=10. +87% cluster (21.9→41.0 mv/s). Strength-neutral: orch-off uses the inline evaluator that `tests/test_eval_server.py` proves matches the orchestrator <1e-5 — **this is the Pass-3 check, satisfied by existing passing tests, no new experiment needed.**
2. **3-box anchor-gate fan-out** — gate launches on all boxes with `--shared-claim`; after `wait_for_count`, a consolidated Python tally over all boxes' JSONs (eval is fastest on the laptop, so fanning beats inline-on-5800x).
3. **WARM/anchor/gate-ref = iter_11** — default `WARM_SRC` now the confirmed-strongest ckpt; gates cumulative climb vs a FIXED ref.
4. **Anchor-fraction self-play** — `--anchor-fraction 0.3 --anchor-checkpoint <WARM=iter_11>` on the self-play cmd (anchor fixed at iter_11 while warm_from chains). Review-hardened (REVIEW_LOG iters 5-8); per-worker anchor-net path works under orch-off (smoke-confirmed, no scalar-width crash).
5. **Plateau guard** — `stop-after-MAX_FLAT(=2)`: tracks the best gate wr vs iter_11, stops after 2 consecutive non-improving iters. n=ANCHOR_GAMES(40) is noisy (1σ≈±8%) → coarse; raise ANCHOR_GAMES/MAX_FLAT to tighten. (This guard previously did NOT exist.)
6. **Safety** — clobber guard (refuses START=0 over an existing `iter_00.pt`) + default `RUN=pathb_anchor` (fresh dir, can't overwrite the pathb_loop screening ckpts iter_00..iter_11).

**Decision:** loop is launch-ready, HELD for Joshua's go (big multi-box compute, ~9–10 hr for 12 iters ≈2× faster post-bench). Launch: `RUN=pathb_anchor nohup nice -n 19 bash /home/doctor/run_pathb_cluster_loop.sh > /tmp/pathb_anchor.log 2>&1 & disown`. sims=200 first; escalate to 800 only if it gates positive.

**Reversal cost:** low (launcher only; checkpoints/data untouched until launched).
**Phase:** 4 (strength push).

## 2026-06-01 — Pipeline bench: orchestrator is the wrong tool for the CPU v2.7 leaf → mixed-mode self-play (+87% cluster); cloud-era W≈48 / fp16 doctrines superseded

**Context.** Ran a per-box per-lever throughput sweep (`scripts/bench_pipeline_sweep.py`, real self-play at production knobs sims=200/v2_5 leaf/score_diff, 240s windows) on all 3 boxes, then a 3-rep verdict-grade confirm of the surprising cells, then a 3-rep deploy-config pass. **Consolidated table (every cell tested, all passes, mean±std): [`experiments/bench_pipeline_results.csv`](experiments/bench_pipeline_results.csv)** (regenerate via `scripts/aggregate_bench_results.py`); raw per-pass data `/mnt/c/carc-shared/bench/sweep_*.csv`.

**What the data says (all confirm/deploy numbers are 3-rep, CV ≤2%).**
- **Worker count is FLAT** under the orchestrator on every box (5800x 7.4–8.1 across W=8–20; xeon ~5.4; laptop ~9.8). All read `ipc_latency` → workers block on the eval-server socket, not CPU.
- **The orchestrator's single GIL-bound dispatch thread is the limiter** (`eval_server.py:135`, mp.Queue pickling a ~0.5MB obs/request). The production leaf is **`v2_5` = `virtual_score`, a CPU heuristic** — the NN only supplies priors — so the GPU sits idle (28W/180W) while the dispatcher is the wall. **The orchestrator earns its keep only when the leaf is a GPU NN-value forward (the abandoned v1–v6 recipes); it outlived its workload.**
- Turning the orchestrator OFF (per-worker inline eval) wins on every box: 5800x 7.4→**14.70** (orch-off W=16, cpu_bound), laptop 9.2→**19.26** (orch-off W=10, gpu 95%), xeon 5.4→**7.0** (→gpu_compute on the weak Turing). `orch_shards=2` is a partial recovery (5800x 11.2, laptop 13.4, xeon 6.9).
- **fp16 is batch-regime-dependent** (reconciles the old "benched slower twice" claim — it was right for small batch): under the **orchestrator** (max_batch 256) fp16 is FASTER on Blackwell (5800x 5060Ti, 9.19 vs 7.40, +24%) and Ada (laptop 4070m, 12.05 vs 9.17, +31%), ~null on Turing. But under **orch-off** (small per-worker batch) fp16 HURTS: 5800x deploy orch-off+fp16 = 13.81 < 14.70 no-fp16 (−6%). The deploy pass also showed the laptop shards+fp16+mb16 stack (18.39) does NOT beat plain orch-off (19.26).

**Decision — mixed-mode per box (the SIMPLEST lever wins where VRAM fits):**
| box | config | mv/s (3-rep) | vs prod orch-on Wdef |
|---|---|---|---|
| 5800x (16GB) | **orch-off W=16, no fp16** | 14.70 | +99% |
| xeon (8GB) | **orch_shards=2** (≈orch-off W=8) | 6.99 | +30% |
| laptop (8GB) | **orch-off W=10** | 19.26 | +110% |

Cluster 21.9→41.0 mv/s = **+87%**. fp16 + shards were red herrings on the strong boxes; orch-off alone wins where the net×W fits VRAM. **Not yet wired into the strength loop** — gated on a Pass-3 strength/correctness check that orch-off + prior-batching-order is strength-neutral (likely — MCTS is robust to tiny prior noise — but unverified; do not promote unverified).

**Superseded cloud-era doctrines (the root cause of weeks of mis-tuning):**
- **"orchestrator saturates / GIL bites at W≈48"** (this file ~L806/838/859/1085) was measured on the **2026-05-12 vast.ai 48-CORE EPYC + 5090** box ($0.37/hr). On the 12–16-thread cluster the GIL-bound dispatcher saturates at **W≈14**. W≈48 was never valid here.
- **"orch-shards GIL only bites at W≈48"** (BACKLOG) — sharding gives +35–50% at W=14–24 on the cluster. Same vast.ai origin.
- **"fp16 is not a lever / benched slower"** (BACKLOG:295, `bench_pipeline_sweep.py:74-77` comment) — REFINED to batch-conditional (above), not blanket-true.

**Not doing:** a shared-memory-IPC orchestrator rewrite (the real single-thread fix — kill the mp.Queue pickle). Parked in BACKLOG; revisit ONLY if a future GPU-bound (NN-value) leaf returns, where cross-worker batching pays off again. For the CPU leaf, orch-off already wins.

**Reversal cost:** low (mode flags only; no checkpoint/data change).
**Phase:** 4 (self-play throughput).

**Phase-3 eval addendum (same session).** Added `--mode eval` + BENCHTP to `eval_net_vs_heuristic` and swept its W (no-orchestrator, batch-1 priors + CPU leaf — the n=400-gauntlet path; n=1/cell screen). Findings:
- **Eval is FASTEST on the laptop = 15.8 mv/s (4070m, GPU-bound 99%) — 2.2× the 5800x (7.1) and 3× the xeon (5.3).** Box-ranking is more lopsided than self-play (an n=400 gauntlet ≈ 63 min on laptop vs ≈2.3 hr on 5800x). So verdict gauntlets should run on the laptop, or work-steal across 3 (`--shared-claim`), NOT inline on the 5800x — yet the in-loop anchor-gate (`run_pathb_cluster_loop.sh:145`) currently runs inline on the 5800x (the *slowest* eval box). Move it / fan it out when convenient.
- **The "eval → W≤10 CPU-bound" rule (CLAUDE.md) is box-dependent — REFINED:** only the strong-GPU 5800x is CPU/latency-bound (plateau ~7 across W=8–16, peak W≈10). The GPU-weaker xeon (Turing) and laptop (Ada) are **GPU-bound** and want W≈14–16 (more workers keep the slow GPU fed — same as orchestrator self-play, opposite of the rule). xeon default W=12 leaves ~5%; bump eval `--workers` to 14–16.
- No big throughput knob remains — the find_farm/leaf speedup (2026-05-29) already captured it; defaults are near-optimal except the xeon W bump + the placement win. Data: `sweep_evalw_*.csv`.

## 2026-05-31 — PIVOT off value-as-leaf → measurement ladder; iter_11 beats a strong reference (+119 elo, first absolute signal)

**Context.** Step 9 closed the value-as-leaf lever (calibration cliff — see entry below). Value-leaf needs scale we don't have. Joshua chose to PIVOT to **measure absolute strength + enable play**, explicitly NOT scale-blind (which would burn weeks into an unmeasurable ceiling). Selected: #1 measurement ladder, #2 headless play, #3 confirm blend.

**The measurement wall this addresses.** Tier-1 (1-ply heuristic) is saturated; self-anchored elo (iter_N vs warm/prev) can climb while absolute strength regresses (the Option-B lesson). We had NO trustworthy absolute read. Fix: a strong, NON-saturated reference = **HeuristicMCTS** (v2.7 leaf + UCT search — the same leaf our bot uses, but NO learned policy). Test: NeuralMCTS(net priors + v2.7 leaf VALUE — the production play config, NOT the raw value head Step 9 killed) vs HeuristicMCTS at **matched sims**. Isolates exactly: does the LEARNED POLICY beat pure heuristic search at equal compute?

**Result (n=100, matched sims=200, c=3):** iter_11 net **66W/1D/33L = 66.5%, +119 elo / 3.2σ, +14.5 score margin.** (Early n=28 was 86%/+311 → regressed to mean, as flagged; the n=100 is the honest number, n=400 verdict running.)

**Reading.** The first TRUSTWORTHY absolute-strength signal in the project: the learned policy decisively beats a strong, non-saturated reference at matched compute. This **validates the +190 self-anchored gain as real strength, not drift** — measurement-first paid off (we now KNOW). Calibration: +119 over our own heuristic+search = "clearly stronger than the thing we built," = ladder rung 1 cleared, NOT "superhuman" (HeuristicMCTS ≈ strong-amateur, not expert). Next rungs: beat Joshua → stronger external reference → pros.

**Tools built + committed.** `scripts/eval_net_vs_heuristic.py` (ladder gauntlet, `ca24392`/`9d39cc5`), `scripts/play_vs_net.py` (headless terminal play — the tkinter GUI is unusable over the SSH chain; `5504fb6`), `scripts/tally_ladder.py` (union tally over fanned-out 3-box runs, validated vs n=100; `1b151c9`).

**Decisions.** (1) Pivot accepted: measurement + play before any more scaling. (2) Promote ladder to n=400 (3-box, disjoint seed ranges → shared folder, running). (3) Don't switch the production leaf to NN value. (4) iter_11 is our confirmed-strongest checkpoint → the play-bot target at sims=800.

**Reversal cost.** Low — additive tooling + eval; no production change.

**Phase.** Phase 4 / Path B → measurement workstream (CLAUDE.md Wall #1).

---

## 2026-05-31 — Path B Step 9 VERDICT: pure NN-value leaf fails (-800), but it's a CALIBRATION CLIFF, not a dead value head

**Result.** Step 9 go/no-go (iter_11, same policy net both sides, NEW=pure NN-value leaf λ=1.0 vs OLD=pure v2.7 leaf λ=0.0, n=400, sims=200, c=3, 3-box): **3W/1D/396L, avg margin −73.7, −800 elo (capped).** Authoritative tally (`scripts/tally_step9.py`, 400/400, 0 corrupt, slot balance 200/200) confirms the driver's number.

**This contradicted the screening (held-out corr 0.81), so before filing a NO-GO we ran diagnostics.** Three checks (`scripts/diag_value_leaf.py` + two inline) RULED OUT the bug hypotheses:
- **Not a sign/POV flip:** corr(NN, v2.7)=+0.31, sign-agreement 57.5% (both > chance); NN value sane (mean −0.01, std 0.64, range [−0.94,+0.96]).
- **No train/serve skew:** recorded iter_11 self-play data is genuinely 12-wide with live, varying farm scalars (contested/balance non-zero); self-play records via the SAME `get_canonical_form` eval uses; encode is deterministic.
- **Leaf wrapper does not perturb:** `make_v25_value_wrapper` at λ=1.0 returns EXACTLY the raw NN value + identical priors (−0.83183 both). Not pathologically overconfident (|v|>0.9 only 11.7%).

**Blend sweep (the decisive follow-up; n=30 each, same net both sides, NEW=λ blend vs OLD=pure v2.7):**
| λ | record | elo vs pure-v2.7 |
|---|---|---|
| 0.1 | 16W/14L | **+23** (break-even, ±64) |
| 0.25 | 12W/2D/16L | −47 |
| 0.5 | 13W/17L | −47 |
| 1.0 | 3W/1D/396L | **−800** |
→ **A smooth, monotonic CALIBRATION CLIFF**: graceful for λ≤0.5 (all within ~1σ of break-even), catastrophic ONLY at pure-NN. A wiring bug would break at all λ; this degrades gracefully → consistent with a real property, not a bug.

**Verdict / reading.** Path B is a **partial success, NOT the NO-GO the −800 implied.** The learned value head DID learn real signal (corr 0.18→0.81, correctly wired) and is **usable as a small blend** (≈break-even at λ=0.1). It is simply **not robust enough at 12-iter scale to be the SOLE search leaf** — MCTS at c=3 steered entirely by it walks into its off-distribution errors. This is the same value-as-search-leaf wall Option 2 hit in May, now at much better in-distribution prediction; KataGo got past it with massive scale + regularization. **The original Step-9 framing (pure-NN-leaf, GO if >+15) was too-extreme a test** — the production-relevant question is the blend, and the blend is viable-to-neutral, not harmful.

**Decisions.**
1. **Step 9 = soft NO-GO on the PURE-NN-leaf**; **partial GO on the value head as a blend.** Don't switch the production leaf to NN value.
2. **Review-agent team: SKIP for now.** The smooth λ-curve + 3 cleared bug hypotheses make a hidden-bug explanation unlikely; a deep code review is low-EV here. Revisit only if a future result looks anomalous.
3. **Strength gain stands:** the +190 anchor-gate (iter_11 vs warm) came via the v2.7 leaf and is untouched by this — the policy genuinely improved.
4. **Next levers (not the value-leaf):** keep iterating (the extended loop is the cheap continuation); if we want the value-leaf to harden, that needs scale + a value-target regularizer, which is a bigger commitment than 12 iters.

**Reversal cost.** None — diagnostics + logging only; no production change.

**Phase.** Phase 4 / Path B Step 9 (closed).

---

## 2026-05-31 — Path B screening SUCCEEDED (value head crosses the heuristic); loop extended to iter 24

**Result.** The 3-box screening loop (12 iters, 600 games/iter, sims=200, farm scalars + ownership aux on) finished Sat 18:26. The diagnostic that gates the whole probe — **held-out value↔outcome correlation** (`train_iter._value_outcome_corr`, val split) — traced a clean S-curve: **0.38 → 0.81**, crossing the v2.7 heuristic's **0.61** ~iter 3-4 and plateauing ~0.81 (old data-starved NN value head = 0.18). No policy-entropy collapse (1.75 → 1.66, floor 0.87). Per-iter anchor-gate iter_11 vs frozen warm: **30W/0D/10L, +190.8 elo**.

**Reading.** A **strong GO *signal***: the learned value head now substantially out-predicts the heuristic on held-out outcomes — the exact Path-B question, on the right (fixed-reference) metric. **NOT yet the verdict:** +190 is self-anchored vs warm (Option-B lesson: self-anchored elo can climb while absolute strength regresses), and corr is mechanism, not playing strength. **Step 9 — go/no-go A/B (NN-value-leaf vs v2.7, same policy net both sides, n=400; GO if >+15 elo) — remains the decisive test, still pending.**

**Why it stopped at 12.** Hardcoded `ITERS=12`, NOT a plateau (loop halts only on NaN / entropy-floor collapse; anchor-gate non-halting). corr-saturation ≠ strength-saturation (value-corr ceiling <1 from tile-draw luck).

**Decision: extend the loop** (Joshua, 2026-05-31). Resumed iters **12→23** in the same run dir (warm-from iter_11, `--window 10` buffer continuous); `run_pathb_cluster_loop.sh` gained `START` resume-in-place support. 3-box WS, nice -19, ~24h. Driver 29976, Monitor `bhnvreb82`.

**Open gaps (production loop v2).** (1) Loop gates only vs frozen warm → no per-iter marginal-strength signal / no plateau-stop; gate vs running-best + stop-after-2-flat. (2) Post-leaf-speedup self-play is GPU/eval-bound (Step-1b W-rebench: W barely matters ≥10, Xeon 10→18) → open throughput lever is a multi-shard eval-server, not more workers. (3) Beyond Step 9, an external/absolute reference ladder (Joshua → club/online → pros) is required to *claim* superhuman.

**Reversal cost.** Low (additive; just more iters; stoppable anytime).

**Phase.** Phase 4 / Path B Step 8 → Step 9 pending.

---

## 2026-05-29 (evening) — Path B Steps 6–8 executed: smoke PASS, collapse guard + value-corr built, 3-box work-stealing screening run LAUNCHED over Shabbos

**Context.** Joshua gave the go to run Step 6 ("run the smoke. low priority nice"), then escalated to launch the loop over Shabbos ("yolo it… wire up 7 and 8, I check back after havdalah"), then **demanded all 3 boxes** for the loop.

**Step 6 (de-risk) — PASS.** Tiny end-to-end smoke (gen 12-scalar → aux-weight sweep {0,0.15,0.5} → self-play → train_iter → anchor-gate): 0 NaN, aux loss falls, mains flat across aux weights (→ freezing aux=0.15 justified), value-leaf swap runs. **1a profile (in-process, sims=200) → PROCEED:** leaf eval ~86% (expected), `get_next_state`/deepcopy only ~10% (confirms the speedup analysis), no >2× surprise. ⚠️ cProfiling `run_selfplay_iter` directly is useless (it spawns a Pool → misses worker hot path); profile in-process via `play_one_selfplay_game` (`scripts/profile_selfplay_inproc.py`). **1b W-rebench (3 boxes, real `run_selfplay_iter`, NOT bench_workers which times raw-engine games): curves FLAT** (post-speedup self-play is eval/dispatch-bound, W barely matters ≥10) → **5800x W=14, Xeon W=18, laptop W=24**; cluster ≈546 g/h.

**Collapse guard + value-corr (new, committed `00b093e` + value-corr commit).** `train_iter.py --entropy-floor-frac` (default 0.5): baseline = warmstart-net policy entropy at iter 0, propagated in the checkpoint; per-iter trained entropy < frac×baseline → exit 2 → loop halts. And a per-iter **value↔outcome correlation** readout (Pearson of value-head vs stored outcome target) — the TRUSTWORTHY progress signal (vs self-anchored chain elo which can climb while absolute strength regresses; beat heuristic's 0.61, old NN was 0.18). Tests + e2e verified. Gate audit found the entropy floor was the only one of the 3 promised deterministic guards not implemented; now all 3 active (NaN-abort, anchor-gate stop, entropy floor).

**3-box loop — DECISION: adapt the proven maximalist infra, don't build from scratch.** `run_phase4_smoke` is single-box; the multi-iter 3-box work-stealing loop wasn't wired. `maximalist_sequencer.sh` already had proven 5800x+xeon work-stealing (`launch_on_host`/`run_selfplay`, held-ssh foreground keeps the Xeon WSL VM alive; `stage_launcher.sh` copies the launcher LOCAL on Xeon to dodge the share-unmounted chicken-egg). Adapted it into `/home/doctor/run_pathb_cluster_loop.sh` + added a **laptop branch** (native Linux, share already mounted, simple held-ssh). Verified each box claims+plays SOLO (mini-scale combined tests just race — the 5800x fills tiny/fast batches before the others boot; irrelevant at production scale). **Launch-hang bug found+fixed:** `pid=$(launch_on_host …)` hung — command substitution waits on the backgrounded worker's orchestrator children holding the pipe fd. Fixed via **pidfile** (launch_on_host writes PID to a file, called WITHOUT `$()`). After fix: all 3 launch instantly, all 3 GPUs active (~26-40% — NOT pegged, consistent with dispatch/CPU-leaf-bound, not GPU-bound), 56 claims = 14+18+24 workers, games landing.

**Screening run (NOT the verdict).** Launched 600 games/iter (not the frozen 1200) for trajectory density over Shabbos: ~9 g/min cluster → ~66min self-play/iter → ~15+ iters in 25h. Directional read of the value-corr trajectory; the GO/NO-GO verdict still needs the frozen 1200 + n=400 Step-9 A/B. Box choice: all 3 per Joshua's demand, accepting the risk that the 3-box multi-iter loop is freshly-wired (mitigated: solo-verified each box + no-hang mini-test + the gates halt on trouble).

**Reversal cost.** Low — the run is killable; warm.pt + per-iter checkpoints preserved on the share; the loop halts cleanly on collapse/NaN.

**Phase.** Phase 4 / Path B Steps 6–8.

---

## 2026-05-29 — Path B Step E shipped: farm scalars IN + made free + flip-on wired; launch plan set (HELD)

**Context.** Joshua decided (2026-05-29) to include the 2 farm-control input scalars in the Path B probe ("farm scalars in. make them free."), and to launch Path B as **3-box work-stealing at `nice -19`** — but **not** until he gives the go.

**Make-free.** The scalars cost +0.49 ms/encode standalone (a whole farmer-field flood per encode), which would erode the 1.48× leaf speedup when on. Fixed by **sharing one `_farm_cache`/`_city_cache` across the policy-encode and the v2.7 leaf-value pass** in `make_v25_value_wrapper` (single + batch): the leaf value floods the same fields anyway, so the scalar floods are reused → **+0.035 ms/leaf (2.2%)**. `virtual_score_v2` was changed to REUSE an attached cache rather than create+delete its own (so it doesn't clobber the wrapper's shared cache). Value-invariant: reconciliation gate n=400 (920k nodes, 0/0) + a wrapper-value==standalone-leaf test. (`70e1b62`)

**Flip-on wired end-to-end.** Rather than a manual flag in every worker script (mismatch-prone), the 12-scalar shape **propagates from the checkpoint's `n_scalar_features`**: eval-server builds net+warmup from it; `run_selfplay_iter` sizes worker/anchor nets from it and the main process peeks the learner checkpoint to set `cfg["include_farm_scalars"]` for worker Games; `eval_iter_head_to_head` derives a per-side Game flag from each checkpoint; `train_iter` reads it from the warm-from checkpoint; `generate_one_game_dataset`/`generate_warmstart_smoke` take `--include-farm-scalars`. **The only manual flag is at the start** (gen + `train_warmstart --include-farm-scalars`); everything downstream auto-derives. Default off → all pre-Step-E (10-scalar) checkpoints byte-identical. (`06b065c`)

**Launch plan (HELD).** 3-box work-stealing (`--shared-claim`), `nice -19`, farm scalars on, frozen knobs per [docs/PATH_B.md](docs/PATH_B.md) table. Full step-by-step in PATH_B "LAUNCH RECIPE" (Step 6 smoke first, then 7 warmstart → 8 loop → 9 go/no-go A/B + value↔outcome corr). **Do NOT launch until Joshua says go.** Pre-launch: propagate commits to Xeon+laptop clones.

**Reversal cost.** Low — all additive + gated; farm scalars opt-in, the share-cache is behind the same toggles.

**Phase.** Phase 4 / Path B Step E + launch prep.

---

## 2026-05-29 — c=3 "+47" RE-VALIDATED at n=1600 → corrected to +18.5; production default unchanged

**Context.** The c_puct=3 production default rested on Phase 2b's +47.2 elo / 5.2σ (n=400), flagged UNDER RE-VALIDATION on 2026-05-28 after Optuna #17 re-screened the same config at +13.9 (n=100) — ~2σ below. Run A was the clean settle: a fresh **n=1600** A/B, iter_B1 both sides, (c=3,cap=12,v2_7) vs (c=1.5,cap=12,v2_7), sims=200, on the **pre-fix engine** (so the leaf matches the original c=3 measurement — this is a hygiene check of the historical claim, not the new fixed leaf).

**Result.** 832W / 747L / 20D = **+18.5 elo / 2.1σ at n=1599** (`experiments/results.csv` `hygiene_c3_vs_c15_n1600`).

**Decision / reading.** c=3 IS a real, significant positive over c=1.5 — but **~40% of the headline +47.2**, which was an inflated point estimate (regression to mean), exactly as the [[bracket-hyperparams]] / [[results-table-source-of-truth]] memories warn. **c=3 stays the production eval-side default** (it's still ≥ c=1.5); the "biggest single free win in weeks / sharp +47 peak" framing is **retired → ~+18**. This closes the last open eval-config re-validation. Consistent with Optuna #17 (+13.9/n=100) and the broader study (winners cluster c=1.5–2.0, c=3 not a standout). Forward: stop spending on eval-config tuning (rounding error vs the superhuman goal); the levers are the structural/Path-B work.

**Caveat unchanged.** This validates the *eval-side* c=3 only; the *self-play-side* c=3 bump (training-data generation) remains hypothesis-only (see 2026-05-28 entry).

**Reversal cost.** None — documentation/epistemics correction; production default unchanged.

**Phase.** Phase 4 hyperparameter methodology.

---

## 2026-05-29 — Leaf flood-fill speedup IMPLEMENTED: lazy per-leaf farm + city memo (not incremental union-find) — 1.70× leaf / 1.48× search

**Context.** Executing the speedup prioritized below. Two priors turned out wrong and reshaped the implementation; both were caught by measuring first (profiling + an A/B bench) instead of trusting the plan's framing.

**Finding 1 — the architecture rules out incremental-union-find-with-rollback.** The plan (PATH_B Step 2) described "maintain a farm union-find as tiles are placed down the tree, with rollback." But the production leaf path is **NeuralMCTS**, which reaches every leaf via **functional `get_next_state`** (deepcopy per step, `StateUpdater.apply_action`), *not* mutate-and-undo. `apply_action_inplace` (the rollback path) is only used by vanilla-MCTS *random rollouts*, which the v2.7 leaf never runs. So there is no tree to thread an incremental structure through — the correct shape is **per-leaf-state**, not incremental-across-tree.

**Finding 2 (profiling, post-fix) — find_farm is ~41% of the leaf, and 54% of its calls are redundant within a single eval.** `cProfile` of `virtual_score_v2` over representative mid/late states: `find_farm` cumtime ≈ 41% (was quoted ~58% pre-fix), `find_cities` ≈ 31%, **deepcopy negligible (~0.4%)** (contradicts old "deepcopy dominates" lore for this leaf). 11.1 `find_farm` calls/leaf, **6.0 redundant** — the same field re-flood-filled once per farmer meeple, across both consumers (`count_final_scores` + the two closure-bonus passes).

**Options for capturing the redundancy.**
  - A: **Eager whole-board decomposition** (`find_all_farms`: one CC pass, index every farm). Benched **1.11× leaf / 1.16× search** — modest, because it pays to enumerate fields no meeple queries.
  - B: **Lazy per-region memo** (`_farm_cache`: memoize `find_farm` under every node of each region as it's first queried; share one cache across all three consumers per leaf). Benched **1.29× leaf / 1.20× search**. Strictly less work than A (only queried fields), and trivially correct (pure memoization of the already-trusted `find_farm`).

**Decision.** Chose **B (lazy memo)** as the production path. `find_farm_by_coordinate` consults an optional `state._farm_cache`; `virtual_score`/`virtual_score_v2` attach one shared cache per leaf eval and detach in `finally`. Behind a `virtual_score.USE_FARM_CACHE` toggle (the A/B baseline). Kept `find_all_farms` (the eager decomposition) in `farm_util` for the future farm INPUT features (Step E, which needs every farm) and as the reconciliation oracle. Safe because: `find_farm` is now start-independent (the farmer-adjacency fix), board topology is frozen during a leaf eval (`count_final_scores` mutates scores/meeples, never `tile.farms`), and `CarcassonneGameState.__deepcopy__` strips unknown attrs so a cache can't leak across `get_next_state`.

**Correctness gate (non-negotiable, mirrors the aux n=2000 gate).** `scripts/reconcile_farm_index.py` — REGION equivalence (`find_all_farms[node]` == `find_farm(node)` for every farmer connection) AND VALUE equivalence (`virtual_score_v2` bit-identical cache-on vs cache-off). **n=400: 919,457 farm nodes, 0 region + 0 value mismatches.** Permanent regression: `tests/test_farm_index.py` (16 cases). No regressions in `test_virtual_score`/`test_aux_targets`.

**City follow-on (same day, Joshua's "fix find cities for now").** Applied the same lazy memo to `CityUtil.find_city` (`_city_cache`) — the other big redundant leaf cost (~31%; `find_cities`/`count_farm_points` re-run it per farmer connection + per city side, count_final_scores per city meeple). `find_city` is a symmetric BFS to closure → start-independent by construction (no farm-style bug), so caching is safe. **One subtlety:** `count_farm_points` dedups adjacent cities via a `set()` keyed on City *identity*, so the memo caches only the `(positions, finished)` flood-fill data and **returns a fresh `City` object each call** — preserving that identity-dedup exactly (value-invariant). Gated by `USE_CITY_CACHE`, shared per leaf eval alongside `_farm_cache` (CoordinateWithSide keys are value-hashable → valid across the deepcopy). `find_meeples`/consumers only read `city_positions`, so sharing the positions set is safe.

**Impact (combined farm + city).** Benched **1.70× leaf / 1.48× end-to-end search** (farm-only was 1.27×/1.20×; city adds 1.33× on top) — ~33% throughput on ALL self-play + eval across the cluster (every NeuralMCTS leaf runs the v2.7 leaf). Gate re-run with BOTH caches toggled: **n=400, 921,953 nodes, 0 region + 0 value mismatches.** `tests/test_farm_index.py` (now incl. a fresh-City memo test) green.

**Reversal cost.** Low — additive, behind `USE_FARM_CACHE` / `USE_CITY_CACHE`, gate-verified. Files: `engine/.../farm_util.py` (find_all_farms + cache branch), `engine/.../city_util.py` (find_city memo + `_compute_city`), `src/.../virtual_score.py`, `virtual_score_v2.py`; tools `scripts/{reconcile_farm_index,bench_farm_index,profile_leaf_farm}.py`; `tests/test_farm_index.py`.

**Phase.** Phase 4 / Path B Step 2 prerequisite.

---

## 2026-05-29 — Prioritize the find_farm speedup (leaf-sharing + union-find) as the next dev task

**Context.** Path B Step 2 ("domain input planes") turned out mostly redundant — 4/6 proposed inputs already exist as scalars; the only net-new ones (`contested_features`, `my/opp_dominant_farms`) are farm-derived and would run `find_farm` at every MCTS leaf-encode, hammering the #1 hot path (~58% of leaf cost). Separately, the 2026-05-29 farmer-adjacency fix made `find_farm` **start-independent**, which unblocks the incremental farmer union-find that was parked 2026-05-17 *precisely because* find_farm was start-dependent.

**Options.** (A) Skip farm inputs for the go/no-go probe, revisit at scale only if Step 9 = GO. (B) Build the `find_farm` speedup now (union-find + leaf-sharing), un-gating it from a GO.

**Decision.** Chose **(B) — build the speedup now** (Joshua's call, 2026-05-29). Rationale: the union-find speeds the EXISTING leaf eval (every leaf already runs count_final_scores → find_farm), so it accelerates **all** self-play + eval throughput across the cluster — value independent of the farm-input feature, and independent of the Step-9 outcome. The farm inputs then come ~free as a downstream. It's pure dev (no compute), so it's productive work to do while the compute decisions (Steps 6–9 box choice) are still open.

**Plan + guardrails.** [docs/PATH_B.md](docs/PATH_B.md) Step 2 (revised) + BACKLOG 2026-05-29. Sequence: incremental union-find → **reconciliation gate** (assert union-find == `find_farm` across many positions, mirroring the aux-target n=2000 gate) → **throughput bench** (measure, don't extrapolate) → leaf-pass sharing → then the farm input features. Correctness risks: the `apply_action_inplace` rollout path + MCTS tree backtrack/rollback of the incremental structure.

**Reversal cost.** Low — additive perf work behind a correctness gate; if the union-find can't match find_farm or doesn't bench faster, drop it and keep the (correct) fixed find_farm.

**Phase.** Phase 4 / Path B Step 2 prerequisite.

---

## 2026-05-29 — Engine fix: farmer-adjacency bug made farm scoring start-dependent (taints virtual_score / v2.7 leaf)

**Context.** Path B Step 1 (aux-target generation) needs per-feature *ownership* labels at game end, validated to reconcile with the engine's `count_final_scores`. Building the validator surfaced that the engine's farm scoring is **non-deterministic across processes**: the same terminal position can score differently depending on Python hash/set-pop order. Root cause traced to two layers:
1. `SideModificationUtil.opposite_farmer_side` was **not a bijection** — `TRT → BRR` (a typo; should be `BRB`). So `BRR` was the image of both `TRT` and `BLL`, and `BRB` was never produced. Crossing the top edge's right-half must mirror to the neighbour's bottom edge right-half (`BRB`). The typo made farmer adjacency **asymmetric**.
2. `FarmUtil.find_farm`'s flood-fill kept a single `to_ignore` edge-set seeded asymmetrically from the start node and marked edges visited in set-pop order, pruning branches before they were explored. Combined with (1), `find_farm` returned **start-dependent** regions — from some farmer meeples it under-collected connections, so `find_meeples` missed meeples and `count_farm_points` missed adjacent finished cities. Via `count_final_scores` this made two same-player farmers on one field score **once or twice depending on pop order**.

**Magnitude (measured, 500 random games):** ~**2.2%** of games mis-scored, mean score-diff error **9.3 pts** (max 30), **0.2%** flip who wins. The same bug lives in `virtual_score` → the **v2.7 leaf eval** the entire current strength rests on, and in `possible_move_finder` (farmer-placement legality). All historical `results.csv` numbers were produced against this buggy, slightly-nondeterministic scorer.

**Options considered.**
  - A: **Fix the engine** — correct `opposite_farmer_side` + rewrite `find_farm` as a complete, start-independent connected-component search. Pro: fixes the root cause everywhere (scoring, leaf, move-gen); deterministic. Con: changes the v2.7 leaf on ~2.2% of evals → per the "bug-fix-shifts-optima" rule, cap/c_puct optima may move; invalidates exact reproduction of some past numbers.
  - B: **Path-B-local** — use a deterministic dedup-correct scorer only for the new self-play data; leave the engine alone. Pro: zero blast radius. Con: leaves the buggy leaf in place; value-target currency mismatch.
  - C: **Replicate the bug** so labels match the (buggy) value target exactly. Con: teaches the aux head a non-deterministic target.

**Decision.** Chose **A — fix the engine now** (Joshua's explicit call when the fork was surfaced). Two vendored-fork patches: `side_modification_util.opposite_farmer_side` `TRT → BRB`; `farm_util.find_farm` rewritten as a node-deduped CC traversal (visits each `(coord, connection)` once, explores every `tile_connection`). After the fix `opposite_farmer_side` is a clean bijective involution ({TLL,TRR}{TLT,BLB}{TRT,BRB}{BRR,BLL}), `find_farm` is start-independent (0/… overlapping-but-unequal components across 300 games, was 112), and the aux-ownership extractor reconciles with `count_final_scores` **exactly at n=2000 (0 failures; was 2.2%)**.

**Consequences / follow-ups.**
- **Re-sweep flag:** the v2.7 leaf changed slightly → the cap=12 / c_puct production optima were tuned against the buggy leaf and should be re-validated before being trusted (memory: bug-fix-shifts-optima). Path B regenerates everything from a fresh warmstart anyway, so this lands naturally.
- **`find_farm` is now start-independent → safely cacheable** (it was previously called out as un-cacheable for exactly this reason) — a real future throughput lever for the hot leaf path. Logged for BACKLOG.
- The overnight hygiene runs (c=3, cap=20) are on the pre-fix engine on their boxes; not disrupted — their results just describe the old leaf. Propagate this fix to all cluster boxes before the next training/eval run.

**Reversal cost.** Medium — it's a vendored-engine correctness change, but well-tested (full suite + n=2000 reconciliation) and isolated to farmer adjacency.

**Phase.** Phase 4 / Path B Step 1.

---

## 2026-05-28 — GOAL CHANGE: attempt genuinely superhuman play (overrides the original-prompt scope)

**Context.** The original prompt ([docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md)) explicitly scoped superhuman strength *out*: *"This is not a 'build superhuman Carcassonne AI' project. That's been attempted by academic groups since 2020 and has stalled — not because the idea is wrong, but because nobody's bothered to throw serious compute at it. We're not going to either."* The stated win condition was the **analyzer (Phase 5)** — "a 90th-percentile bot that explains *why* a move was bad is more useful to me than a superhuman black box." On 2026-05-28, during a strategic regroup, Joshua changed the goal: **he wants genuinely superhuman play — to beat the world champion.**

**Decision.** Superhuman strength is now the **primary** goal. The analyzer (Phase 5) and heuristic research (Phase 6) become **downstream** — pursued after strength milestones, not the target. The locked *rule* scope (2p Base+River+Farmers) is unchanged.

**What this honestly implies (surfaced at decision time, not papered over).**
- This is a **research-grade goal the prompt deliberately avoided**; comparable academic attempts stalled. On a 3-box consumer cluster (~300 g/h eval) this is months-to-maybe-unreachable. We pursue it clear-eyed: real measurable progress is achievable; the summit is not promised.
- **Two structural walls, neither touched by the eval-config tuning of the last month:**
  1. **Measurement.** We have no strong, non-saturated reference. Tier-1 is a saturated 1-ply heuristic; self-anchored elo can climb +600 while absolute strength regresses (the Option-B-chain result proved this). *We cannot tell if we're approaching world-champ level.* First unblock: build a strong reference ladder (high-sim vanilla MCTS / the Ameneyro 2020 baseline) as an absolute yardstick, since a human benchmark isn't available now.
  2. **Leaf ceiling.** Our strength is PUCT search over the **hand-crafted** v2.7 `virtual_score` leaf. A human-designed heuristic caps learned play near strong-human by construction. We already tried to let the NN value head exceed it (Option 2) and it was *worse* (closed 2026-05-18). Superhuman requires the *learned* components to beat the heuristic — the documented path is KataGo-style (domain-feature input planes + auxiliary loss heads + scale), all gated behind a fresh from-scratch warmstart (bundle the deferred D1/D13 feature fixes).
- **The eval-config tuning era (c_puct/leaf_cap/leaf_variant, incl. tonight's Optuna) is rounding error against this goal** and should stop — see the meta-rule in EXPERIMENTS.md ("try-harder-with-the-same-architecture is the trap").

**Roadmap implied (not yet committed — to be planned):** (1) strong reference ladder [unblocks measurement], (2) structural leaf/architecture change [the real lever], (3) scale compute + Optuna-over-*recipe* [where Optuna's automation finally earns its keep].

**Reversal cost.** Low to state; high to pursue (months of compute). The goal can be re-narrowed to the analyzer at any time if the strength climb proves infeasible — the analyzer work is not lost, just deferred.

**Phase.** Strategic pivot atop Phase 4.

---

## 2026-05-28 — Measurement infrastructure: `experiments/results.csv` as source of truth + results discipline

**Context.** The regroup found that disorganization, not just bad luck, produced the false "c=3 = +47 elo" production change. Audit: **54 completed evals across 41 ad-hoc dirs**, config encoded only in directory names, and `elo_log.json` records the *outcome but not the config* (no c_puct/cap/variant). Four disconnected representations of the same results (dirnames, config-less elo_logs, the hand-maintained EXPERIMENTS.md table, the optuna study.db), none queryable. The c=3 contradiction (noise spike at n=400 vs the earlier "c is noise at n=20" finding, vs tonight's +13.9 re-screen) was invisible because no structure forced the comparison.

**Decision.** Build one structured, queryable, git-diffable results table and make it the source of truth; adopt query-before-claim discipline.
- **Artifact:** `experiments/results.csv` — one row per eval (full config both sides + outcome + n + sigma + provenance). CSV (not a DB) because ~54 rows, diffable in PRs, one-line pandas load. Optuna `study.db` exports into it.
- **Root-cause fix:** `eval_iter_head_to_head.py` writes a self-describing `manifest.json` and appends its row to results.csv on completion → the table self-maintains; no future dirname archaeology.
- **Backfill:** the existing 54 elo_logs + 18k per-game JSONs are reconciled with a one-time hand-authored dirname→config map (config isn't in the data). Run as a background subagent 2026-05-28; low-confidence rows flagged, not fabricated.
- **Discipline (also added to CLAUDE.md operating norms):** cite the table, never duplicate authoritative numbers; query for prior measurements of a cell before declaring a finding; n=100 = screen (±17), n=400 = verdict (±9); a lone >1σ spike vs neighbors is noise, not a peak.

**Why not heavier infra (SQLite/dashboard/framework).** 54 rows. A CSV + a 10-line pandas query helper covers every "pivot config-dim × n → elo" view we need. Over-building a results system would itself be the procrastination trap. EXPERIMENTS.md stays as the *narrative* layer that cites the table.

**Reversal cost.** Trivial — it's additive (a CSV + a manifest write + doc norms); nothing depends on it that can't fall back to the old prose tables.

**Phase.** Methodology / measurement, prerequisite for the superhuman push (addresses Wall 1 above).

---

## 2026-05-28 (evening) — Optuna eval-search softens the c=3 "+47 free win"; flagging the headline claim for re-validation

**Context.** The Optuna eval-time study (`eval_time_search_v1`, TPE over {c_puct, leaf_cap, leaf_variant}, multi-fidelity n=100→n=400) ran ~16 trials across 5800X+Xeon+laptop. To bridge it against the 2026-05-26 Phase 2 result, we `enqueue_trial`'d the exact canonical config (c=3.0, cap=12, v2_7) as a NEW-side-vs-(c=1.5,cap=12)-baseline trial — identical A/B design to Phase 2b.

**Result.** Trial #17 screened at **+13.9 elo at n=100** (did not clear the +15 promote threshold, so stayed at n=100). Phase 2b measured the same config at **+47.2 at n=400**. At n=100, 1σ ≈ ±17 elo, so +13.9 is ~2σ below +47.2.

**Reading (careful — sample sizes differ).** A single n=100 screen CANNOT refute an n=400 result; the error bars overlap at ~2σ. But combined with the rest of the study — winners cluster at c=1.5–2.0, the study best is (c=2.0, cap=19, tcc) +24.4, and no high-c config stands out — the weight of evidence is that **Phase 2b's +47.2 was an inflated point estimate (regression-to-mean candidate), and c=3's true edge over the c=1.5 baseline is more modest (~+14, in line with the field).** This is exactly the failure mode the [[bracket-hyperparams]] memory warns about, applied to our own headline result: a single n=400 reading made c=3 look like a sharp +47 peak; broader sampling flattens it.

**What this does and doesn't change.**
- Does NOT mean c=3 is wrong — every measurement still has c=3 ≥ the c=1.5 baseline. The production default is not in danger of being *worse* than old.
- DOES retract the "sharp +47 peak / biggest single free win in weeks" framing. c=3 is *a* reasonable setting, not a standout.
- The whole **c×cap interaction** claim from the 2026-05-28 10:30 STATUS entry is downgraded — it was built on n=100 noise.

**Decision.** Keep c=3 as the production default for now (it's not worse), but **flag the +47 claim as UNDER RE-VALIDATION** and run a fresh **n=400 (c=3, cap=12) vs (c=1.5, cap=12)** before treating any c value as settled. Do NOT re-bump or re-tune off the Optuna n=100 screens — they're too noisy. The clean follow-up is one targeted n=400 eval (cheap, dual-box ~3h), ideally alongside (c=2.0, cap=19) to check the study's apparent best at full power.

**Reversal cost.** None — this is a documentation/epistemics correction, not a code change. The production default is unchanged.

**Phase.** Phase 4 hyperparameter tuning. Methodology: re-validate your own headline wins at full n before enshrining them.

---

## 2026-05-28 — c_puct bump: eval-side validated, self-play-side bumped on hypothesis (NOT yet A/B'd). Documenting the conflation before it bites us.

**Context.** On 2026-05-27 we bumped the `--c-puct` default in both `scripts/eval_iter_head_to_head.py` and `scripts/run_selfplay_iter.py` from 1.5 → 3.0, citing the Phase 2b sweep (+47.2 elo at sims=200) and J4 (+39.3 at sims=800) as justification. That was the same commit. Today (2026-05-28) we noticed the two scripts use c_puct in **structurally different ways**, and the evidence only validates one of them.

**The distinction.**
- **Eval-side c_puct** (`eval_iter_head_to_head.py`): controls PUCT during head-to-head play with a *trained* checkpoint. Phase 2b and J4 tested exactly this: same iter_B1 both sides, different c, count wins. Verdict +47.2 / +39.3 — clean, validated.
- **Self-play-side c_puct** (`run_selfplay_iter.py`): controls PUCT during *training data generation*. A different c changes (a) which actions get selected in self-play games, (b) the shape of the visit distribution that becomes the policy target, and (c) downstream game outcomes that become value targets. The resulting `.npz` files are then fed to `train_iter.py`. The thing we'd measure is the **strength of the trained checkpoint that results** — not the strength of self-play games themselves.

**Why the conflation is plausible-but-unverified.** It's reasonable to assume that c=3 self-play yields a stronger checkpoint than c=1.5 self-play: deeper exploration → more diverse training data → better generalization. But this is a hypothesis. Counter-arguments: (1) Self-play also has Dirichlet noise on root priors and τ=1 for the first 15 moves, which already inject exploration; an additional PUCT widening may be redundant or even hurt by over-spreading visit distributions and producing softer (less informative) policy targets. (2) The Phase 2b/J4 result was specifically about **playing strength of a fixed checkpoint with different c**, which is upstream of the data-generation question. (3) AlphaZero papers typically use the same c at self-play and eval, but their c was tuned end-to-end; ours wasn't.

**Options considered.**
- **A. Roll back self-play default to c=1.5 until A/B run.** Conservative. Costs ~0 (just a default change). Reverts the change that was never validated.
- **B. (chosen) Keep c=3 self-play default, document the gap loudly, schedule an A/B.** Pragmatic. The hypothesis is reasonable and every new run from today onward generates evidence under c=3. Reverting now would create a "what default were the files in this dir generated under?" tracking burden, since we have ~0 c=3 self-play data on disk yet. Document the unverified status, run an explicit A/B at some point.
- **C. Train two iters now (c=1.5 self-play vs c=3 self-play from same warm-from), eval head-to-head before producing any more self-play data.** Most rigorous but blocks ~25h of compute on validating something that probably works.

**Decision.** Option B. Update the docstring on `run_selfplay_iter.py --c-puct` to flag the eval-vs-selfplay distinction and the unverified status. Add a "UNTESTED" row to the STATUS.md verdict table for "c_puct=3.0 in self-play data generation." Add this decision entry. The A/B test gets queued in the forward queue, not blocking.

**What would falsify.** Train iter_X(c=1.5_sp) and iter_X(c=3.0_sp) from the same warm-from on the same data-volume budget. Eval head-to-head, both at c=3 (the validated eval setting). If c=3-self-play loses or is null, roll back the self-play default to 1.5 and reconcile.

**Reversal cost.** Low. Changing the default back to 1.5 is a one-line edit. If we later discover c=3 self-play hurt, the affected output is the data on disk from c=3 self-play runs — flagged via metadata or just the `cfg` JSON each run writes.

**Phase.** Phase 4. Methodology lesson, not a scientific finding.

**Memory cross-ref:** `feedback_bracket_hyperparams` (auto-memory) — same family of failure mode (declaring a config change settled from off-target evidence).

---

## 2026-05-26 — c_puct=1.5 → ~3.0 free win at iter_B1 (sims=200): +47.2 elo at n=400, 2.8σ. Most "leaf-eval plateau" symptoms were stale-PUCT, not leaf saturation.

**Context.** After 8 days of leaf-eval ablations (cap A/B, value-blend, tile-counting) and chain experiments (Option B, anchor-fraction, deepsearch_v2) all returning null or negative, ran the maximalist's Phase 2 PUCT wider sweep (deferred for ~6 weeks since the original c_puct calibration on warmstart-level checkpoints). Same checkpoint iter_B1 both sides; only the per-side c_puct differs. n=400 at sims=200.

**Result table.** All measured at iter_B1, sims=200, leaf v2_5, c=1.5 as the OLD side:
- c=0.5 → −54.3 elo (165W/227L/8D) — catastrophic
- c=1.0 → −11.3 elo (192/205/3) — mildly worse
- c=1.5 (baseline) → 0
- c=2.0 → +5.2 (from 2026-05-20 retroactive test; null)
- **c=3.0 → +47.2 elo (226/172/2) — 2.8σ positive**

Phase 2b (c=2.5/4.0/5.0) is in flight to triangulate the peak; outcome lands ~2026-05-26 18:00.

**Conceptual reading.** In `U(s,a) = Q + c_puct * P * sqrt(ΣN)/(1+N)`, raising c shifts action selection from Q-driven (trust the v2_5 leaf eval's accumulated rollups) to P-driven (trust the network's policy prior). The +47 elo at c=3.0 means **the network's policy is now sharper than the leaf-eval's Q values**. The original c=1.5 was tuned during Phase 3 warmstart on much weaker policies; it never got retuned as the network trained through iter_00 → iter_01 → iter_B1. Classic stale-hyperparameter failure. Several recent "leaf-eval plateau" symptoms (v2.7 leaf doesn't scale, Option-2 blend hurts, cap retunes null) look in retrospect like search wasn't using the policy enough — not that the leaf was actually the limit.

**Why this was missed.** All ablations of the last 6 weeks held c=1.5 constant. The 2026-05-15 PUCT sweep (`puct_c2_vs_c15`) only tested c=2.0 (got +5.2, near-null) and concluded "c=1.5 holds" — that single near-baseline data point made the whole search-config axis look settled when it wasn't. **Lesson: never declare a hyperparameter axis settled from one off-peak point — at minimum bracket above and below.**

**Options considered (the strategic pivot the PUCT find triggers):**
- **A. Update production c_puct to peak (≈3.0 pending Phase 2b) and call it done.** Easiest. Banks the free win immediately. Risks: c may not transfer to sims=800, may have interactions with other hyperparams.
- **B. (chosen) A + retune-everything-stale audit.** Bump production c, then sweep the other "set early, never re-tuned" hyperparams (temp_threshold=15, dirichlet_alpha=0.3, dirichlet_eps=0.25, virtual_loss=1.0) at the new peak c. Same staleness pattern likely applies. Also re-test the recent null verdicts (anchor-fraction, deepsearch_v2, tile-counting) at peak c — many may flip positive.
- **C. Skip the retune audit, jump to bigger projects (transformer net, multi-anchor league).** Higher EV in theory, but option-B audit is cheap (~2-3 days dual-box) and several entries have meaningful probability of paying off.

**Decision.** Option B. Wire (sims × c) 2D probe → re-test top nulls at peak c → other-hyperparam sweep, all dual-box shared-claim. Forward queue documented in STATUS.md. Once stale-hyperparam audit settles, take stock and decide on bigger architectural projects.

**Reversal cost.** Low for the production c bump (config change). Low-medium for the queue itself (each eval is ~3h dual-box, easily killable). The lesson — "bracket hyperparameters above and below the current setpoint when you sweep" — is the durable change in methodology.

**Phase.** Phase 4 (self-play loop) hyperparameter tuning.

**Memory cross-ref:** `feedback_bug_fix_shifts_optima` (auto-memory) — same lesson applied to bug fixes; here it applies to checkpoint progression. Adding a new memory note for the methodological lesson.

---

## 2026-05-24 — Option B chain Phase 1 KILLED after B4; chain-vs-prev anchors were lying about absolute strength; pivoting to anchor-fraction multi-opponent self-play

**Context.** Maximalist sequencer ran Phase 1 chain B2→B4 (B5 in progress, killed mid-flight) over 2026-05-21→24. Each chain step measured iter B(i) vs B(i-1) at n=2000, sims=200. Chain elo deltas looked acceptable: B2=+11.4 / B3=+2.4 / B4=+1.4 — no skip-forward (<−10 elo threshold) trigger. But **directly anchored against iter_01 (the canonical reference) at n=400**, B4 came back at **−19.1 elo** (186W/208L/6D, 1.1σ regression). Given iter_B1 = chain-step-0 = B1 was confirmed at +25.2 over iter_01 (2026-05-20 n=400), this means the chain drifted **~55 elo against the fixed reference** while each chain step looked ~neutral against its predecessor.

This is the **"anchor before scaling" memory rule** failing in practice. Each step's measurement was vs a drifting reference, so the chain was free to spiral away from any externally-meaningful elo. The maximalist's Phase 1 (and Phases 3, 5-retrain) only does chain anchors — no global anchor — and is structurally vulnerable to this pattern.

**Likely cause: RPS / intransitivity from self-specialization.** Each B(i)'s self-play data is dominated by play patterns against B(i-1). The network specializes against B(i-1)'s style → loses generality vs off-distribution opponents (iter_01). Classic AlphaZero failure mode without league/multi-opponent training.

**Options considered:**
- **A. Run more chain steps and hope** (B5/B6/B7 already queued). Rejected: drift is already 55 elo deep; another 60h of compute almost certainly worsens it.
- **B. Anchor-fraction multi-opponent self-play.** Mix N% of self-play games against a fixed strong anchor (iter_B1) into the chain. Prevents drift by tying training data distribution to a fixed reference. Well-established cure for this failure mode. ~190 LoC, ~5h to implement. **CHOSEN pending B2 vs iter_01 anchor verdict.**
- **C. League play (AlphaStar-style, N specialized agents).** Right long-term solution but overkill for our scale (1200 games/iter, 7M-param net). Engineering project: ~2-3 days.
- **D. Different recipe entirely (e.g., score_diff abandoned, leaf-eval rework).** Doesn't address the structural drift, just hopes a different starting point doesn't show it.

**Decision.** Kill chain after B4 (executed 2026-05-24 07:55). Run B2 vs iter_01 direct anchor at n=400 to differentiate "Option B recipe was broken from step 1" (B2 also ≈ −19) from "chain held for 1 step then drifted" (B2 ≈ +25). Then:
- **If B2 ≥ ~+10**: implement anchor-fraction self-play (static anchor=iter_B1, fraction=0.3, alternating sides) per design in this session. Pilot 1 chain step under anchor-fraction; if validates, chain forward.
- **If B2 ≈ −19**: anchor-fraction won't save a broken recipe; pivot to Phase 3 deepsearch / loop's orphaned deepsearch train+anchor / leaf-eval rework.

**Resolved 2026-05-24 11:00.** B2 anchor came back at **−6.1 elo vs iter_01** (193W/200L/7D, n=400, 0.36σ null). Not −19, but not positive either — **Option B chain doesn't even gain in step 1**. B1's confirmed +25 cushion already half-erased by B2. Anchor-fraction would hold the line at iter_B1's strength but can't manufacture gains where the recipe produces none. **Option B as a chain lever is dead.** Pivoting per the B2≈−19 branch above: kicked off the orphaned loop deepsearch train+anchor immediately (PID 5369, nice 19, train+anchor n=100 sims=200 vs iter_01, ETA ~35 min from 11:23). Anchor-fraction implementation will be scoped to the deepsearch lever instead of Option B.

**Updated 2026-05-24 22:30.** Two follow-ons landed:
1. **deepsearch_v2 verdict** (the orphaned /loop train+anchor): trained from the 2026-05-18→21 sims=800 work-stealing data, anchor-gated at **+13.9 elo @ n=100** then re-confirmed at **+5.2 elo @ n=400** (combined +11.4 over 500 games). Under σ=17 → **null vs iter_01 at sims=200**. Sims=800 training data did NOT move the sims=200 needle. The deepsearch (v1) ckpt remains the sims=800-plane best; deepsearch_v2 is roughly equivalent to iter_01 for warm-from purposes.
2. **Anchor-fraction self-play implemented + smoke-validated.** ~280 LoC across `src/carcassonne_ai/selfplay.py` (dual-MCTS routing per `current_player == learner_player_idx`, learner-only record filter — anchor's moves are played but never saved), `scripts/run_selfplay_iter.py` (`--anchor-checkpoint` + `--anchor-fraction` flags, dual eval-server pool wiring, per-seed RNG XOR'd to decorrelate), and `tests/test_anchor_fraction_selfplay.py` (6 new tests covering regression-when-anchor-None, learner-only-records, ~50% record-count, distinct-evaluator legality). Full suite green. Smoke run (4 games at fraction=0.5) showed exact contract: 2 anchor games at ~83 records single-sign (learner-only), 2 self-play games at ~165 records mixed-sign. Mutually exclusive with `--serve-on`/`--remote-eval-server` (single-host or `--shared-claim`-only); compatible with `--shared-claim` for dual-box work-stealing.

**Strategy pivot:** anchor-fraction will be tested at **sims=200 FIRST** (cheap, ~4-5h dual-box) before committing to sims=800 production (~20-25h). The deepsearch lever (sims=800 training) was null at sims=200; no reason to assume sims=800 amplifies the anchor-fraction signal more than sims=200 reveals it. Warm-from = iter_01 (deepsearch_v2 was equivalent strength-wise — picking the simpler chain). Static anchor = iter_B1 (current sims=200 global best, the strongest "fixed opponent" we have).

**Other phase impacts:**
- **Phase 2 (PUCT sweep on iter_B1)**: unaffected by drift — no chain step. Still valid to run as-is (~24h).
- **Phase 4 (FN re-confirms, leaf-eval ablations on iter_B1)**: unaffected — no chain step. Still valid (~10h).
- **Phase 5 smoke (tile-counting vs v2.7 leaf on iter_B1)**: unaffected — no chain step. Still valid (~3h).
- **Phase 3 (deepsearch DS_02)**: IS a chain step — same drift risk. Should be re-implemented under anchor-fraction (anchor = iter_01 or existing deepsearch ckpt). Defer until anchor-fraction lands.
- **Phase 5 conditional retrain**: IS a chain step. Same — defer or rewrite under anchor-fraction.

**Reason.** B2-B4 chain elo (+11.4 / +2.4 / +1.4) "looked fine" by chain measurement, but the direct anchor revealed catastrophic drift. The sequencer's design lacked a global anchor and shipped that bug into ~3 days of compute. The cure (anchor-fraction in self-play, OR adding a "vs iter_01 anchor at n=400 each step" to chain phases as a cheap drift detector) is cheap enough that NOT having it was the real mistake.

**Reversal cost.** Low for the kill itself (`--shared-claim` makes restart cheap — wasted compute is sunk). Medium for the anchor-fraction implementation: new flag in `run_selfplay_iter.py`, second eval-server in pool, two-evaluator routing in `selfplay.py:play_one_selfplay_game`. Defaults off; legacy behavior preserved when `--anchor-fraction 0.0`.

**Phase.** Phase 4 (self-play loop), specifically the chain methodology.

**Memory cross-refs.** `feedback_anchor_before_scaling` (auto-memory) was the exact warning. The maximalist sequencer's design (chain-only anchors) was the mechanism that ignored it. Future autonomous pipelines must include a global anchor per chain step.

---

## 2026-05-20 — Network-distributed eval-server: TCP bridge in front of the existing orchestrator pool, lets a GPU-less box (Zenbook) borrow the 5800X's GPU for inference

**Context.** Zenbook (i7-12700H, 16 GB, no NVIDIA) bootstrapped 2026-05-20 to add as a 3rd cluster box. Two ways to use it: (a) run its own standalone CPU eval-server — works without any new code, but CPU forward is ~80 ms/eval and contributes maybe Xeon-tier throughput; (b) network-distribute the orchestrator so Zenbook's CPU workers offload inference to the 5800X GPU via TCP. Option (b) is meaningfully faster (workers do MCTS only, not torch forwards) and uses RAM Zenbook already has.

**Options considered:**
- **A. Standalone CPU eval-server (no new code).** Trivial: just point Zenbook's existing self-play at its own CPU. Works today, ~0.5-1.0 games/min added. But it's also the upper bound on what CPU can do at sims=200 — the laptop CPU is the limiter, the GPU on the 5800X sits unused for Zenbook's share of work.
- **B. Network-distributed eval-server bridge** (chosen). Add a small TCP listener in front of the existing eval-server orchestrator pool; remote workers connect, ship `(obs, scalars, mask)` over the wire, get `(priors, value)` back. ~0.8-1.0 games/min, much less Zenbook CPU pressure, GPU does the heavy work for both boxes.
- **C. Build a real distributed coordinator (Ray / gRPC / ZMQ).** Overkill — we have 2-3 boxes on one LAN with one tenant. The complexity tax buys nothing.

**Decision.** Build B as a thin TCP bridge:

- **Wire format**: 4 B big-endian uint32 frame length, then per-message payload. Each numpy array is serialised via `np.save` with `allow_pickle=False` into a `BytesIO`, length-prefixed. **No serialization-via-eval anywhere** — `np.load` with `allow_pickle=False` refuses object dtypes. Wire path: `[frame_len][worker_id][request_id][3 npy blobs]`. ~70 KB per single-board request, well under the 64 MB safety cap.
- **Server side**: a daemon thread per connection runs `recv_framed → request_q.put → response_q.get → send_framed`. The bridge **pre-claims K extra slots** in the existing `start_server_pool` (i.e. starts the pool with `n_workers + K` slots) and binds one slot per inbound connection. The running eval-server code is **unchanged** — to the server, the bridge looks like K more local mp.Queue workers.
- **Client side**: a `SocketServerHandles` mimics the existing `eval_server.ServerHandles` interface (same `.request_q.put()` / `.response_q.get()` API), so the existing `make_remote_batch_evaluator` factories work without changes.
- **Failure handling**: if a remote worker disconnects with a request in flight, the bridge drains the eventual server response before releasing the slot — otherwise the next connection on that slot would receive the prior reply. CIFS-style transient errors fall through to the worker's existing `BrokenServerError` path; reconnect is at the worker level.

**Reason.** Bridge mode is ~20% faster than CPU-only and saves Zenbook's CPU for MCTS work where it actually helps. The thin-wrapper approach (re-use the existing orchestrator pool, just front it with TCP) means zero changes to the running self-play code path — workers don't know whether their `ServerHandles` is local mp.Queue or socket-backed.

**Verification.** 9 unit tests (`tests/test_remote_eval_bridge.py`) cover wire roundtrip, concurrent workers, slot exhaustion, slot recycling on disconnect, worker_id restamping. All pass on both the 5800X and Zenbook venvs. Loopback smoke (server + client both on the 5800X, CPU mode): 12932 evals roundtripped, 0 failures, 13 fresh server games + 7 fresh client games out of 20 total — work-stealing balanced as expected.

**Reversal cost.** Low. New code is additive — the `--serve-on` / `--remote-eval-server` flags are off by default; without them the script behaves exactly as before. Easy to revert by not using the flags.

**Phase.** Phase 4 (self-play loop).

**Worker-count knee on Zenbook.** Bridge-mode bench 2026-05-20 with localhost stub (5 ms simulated forward) swept W ∈ {4,8,12,14,16,20}: peak at W=8 (5.26 games/min), curve flat 8→20 (5.0-5.3 games/min). Production recommendation **W=10** (pad +2 from raw peak to give bridge-conn threads + OS headroom, since stub workers in the bench cost ~0.5 cores). Matches the "2×P-cores − 2" heuristic for the 12700H (6 P-cores → 10). HT didn't add throughput on this hybrid CPU because (i) E-cores have no HT, (ii) Linux Thread Director on Alder Lake is shaky pre-6.2, (iii) laptop thermal envelope limits sustained boost. Decision: pin v3 sequencer to `WORKERS_ZENBOOK=10`; sanity-check W=10 vs W=12 against real 5800X GPU once firewall opens.

**Deploy blocker.** Windows firewall on the 5800X needs to allow inbound TCP 19999 LAN-scoped — 1-line PowerShell as admin, see `/home/doctor/network_bridge_deploy.md`. Until then, deploying CPU-only Zenbook (option A) as the interim — adds Xeon-tier throughput today without admin work, swap to bridge mode the moment firewall opens.

---

## 2026-05-20 — Methodological retroactive-validation pipeline: the project's n=100 matched-strength comparisons have been systematically false-negative-prone; re-running 4 high-leverage past nulls at n=400

**Context.** The sims=800 matched-plane re-bench (entry below) — 52% wr at n=100, point estimate slightly positive — sits squarely in the "ambiguous, would-need-more-data" band, the same band where several earlier "null" calls landed (iter_02 at 53.5% / n=100, iter_B1 at 49% / n=100, PUCT c-sweep at n=50). The question came up: have we been throwing out false negatives across the project?

**The math, briefly.** For wr-based head-to-heads:
- n=100: SE ±5.0pp; "significant" (α=0.05 one-sided) bar = ≥58.2% wr → detects ≥+58 elo edges confidently
- n=200: SE ±3.5pp; bar = ≥55.8% → detects ≥+40 elo
- n=400: SE ±2.5pp; bar = ≥54.1% → detects ≥+30 elo
- n=600: SE ±2.0pp; bar = ≥53.4% → detects ≥+25 elo

Matched-strength comparisons (iter vs iter at same leaf) are the project's hardest signal-to-noise regime, and we'd been running them at n=100. Most of our "compounding cadence" conclusions therefore had ~50-60% power against +30 elo edges → up to ~45% miss rate at that effect size. The discipline against *false positives* was strong (the n=50-minimum-for-variant-comparison memory rule caught v3/PUCT noise), but the symmetric guard against false negatives was missing.

**False-negative-suspect calls, ranked by impact-if-wrong:**

| call | n | wr | downstream impact | re-run? |
|---|---|---|---|---|
| iter_02 "saturated against fixed leaf" | 100 | 53.5%, +24.4 elo | huge — closed plain-recipe compounding lever | **yes** |
| iter_B1 ≈ iter_01 (Option 2 NN-value blend) | 100 | 49% wr / +4.6 score diff | big — closed value-head blend pipeline | **yes** |
| deepsearch matched-plane (already in flight) | 100 | 52.5%, +17.4 elo | matched-plane ambiguity, see entry below | **extend to n=400** |
| PUCT c=2.0 vs c=1.5 | 50 ea | 88/84% | small — one-time +25 elo at best, cheap to test | **yes** (separate per-side c_puct job) |
| closure-P leaf A/Bs | 100 ea | 45/50% | small — pooled 47.5% over n=200 is mildly negative, not noisy | no |
| v3 cap sweep | 50 | flat | small — cap=12 production-tested, multiple n=50 readings | no |
| Option 2 blend smoke | 50 | 31% | confirmed negative (2.7σ) | no |

**Implementation.** Autonomous 4-job pipeline (`/home/doctor/sequencer.sh` + `/home/doctor/puct_followup.sh`), nohup'd on the 5800X, drives both boxes via the work-stealing `--shared-claim` primitive (now wired into `eval_iter_head_to_head.py` too, see infra notes below). Each job's verdict appended to `/tmp/retest_verdicts.txt`; sentinel files at `/tmp/{retest_sequencer,puct_followup}.DONE`. Total cluster wallclock ~12-14h overnight.

**Decision.** (1) Run the 4 high-leverage re-tests at n=400. (2) Skip the low-impact ones (closure-P, v3 cap, Option-2 blend) — those were either decisively negative (Option 2) or repeatedly null (closure-P pooled across two leaf variants at n=200, v3 across multiple cap values at n=50). (3) **Going forward, n=400 minimum for matched-strength comparisons**; n=100 reserved for first-look smokes or for variant tests where the effect-size-of-interest is >+50 elo. Add this to the project's operating norms.

**Expected information value.** P(at least one of the 4 re-tests recovers a real positive) ≈ 40-50% under reasonable Bayesian priors. The expected-value math favors running it: even a single "false-negative recovered" outcome unblocks a major lever (e.g. if iter_02 turns out to be a real +30 elo gain, the multi-iteration training pipeline is back open; if PUCT c=2.0 is real, +25 elo free at play time). At ~12-14h cluster cost split across two idle boxes overnight, it's nearly free.

**Infra extracted along the way (commit-worthy in their own right):**
- New `src/carcassonne_ai/claim.py` — work-stealing claim primitive (atomic O_CREAT|O_EXCL on a `.claim` sidecar, with stale-recovery semantics from the run_selfplay_iter implementation). Refactored out of `run_selfplay_iter.py`; both that script and `eval_iter_head_to_head.py` import it.
- `eval_iter_head_to_head.py` gained `--shared-claim` / `--claim-stale-secs` / `--claim-host` — evals can now work-steal across boxes the same way self-play does. Plus per-job consolidated-from-disk summary so each box's printed verdict reflects the cross-box outcome.
- `eval_iter_head_to_head.py` gained `--new-c-puct` / `--old-c-puct` — per-side PUCT exploration constant. Default None falls through to `--c-puct`, so all existing call sites are unaffected. Enables A/B testing exploration constants on the same checkpoint both sides (the PUCT job's whole reason for being).
- 12 tests still green; smoke confirmed.

**Reversal cost:** low. The re-test outcomes either confirm the original verdicts (no change to current conclusions, narrowed noise bands) or update them (correction we should have made earlier). The infra changes are backwards-compat and useful regardless of the re-test results.

**Phase:** 4 (self-play) — methodological / infrastructure.

## 2026-05-20 (results) — Retroactive-validation pipeline complete: 2 of 4 false-negatives recovered. iter_B1 promoted to new global-best. Audit identifies several more reservoirs of likely false-negatives.

**Outcome (4 of 4 jobs done, cluster wallclock ~16h 13:55 → 16:10):**

| job | n | result | elo Δ | σ vs 50% | verdict |
|---|---|---|---|---|---|
| deepsearch vs iter_01 @ sims=800 | 380 | 208W/169L/3D | **+35.8** | 2.0σ | **recovered FN** (already suspected from n=100 +17.4 reading; n=400 confirms at 2σ) |
| iter_02 vs iter_01 @ sims=200 | 400 | 193W/198L/9D | **−4.3** | 0.25σ below 0 | **genuine null** — plain v2.7 recipe really did plateau at iter_01; not a false-negative |
| iter_B1 vs iter_01 @ sims=200 | 400 | 213W/184L/3D | **+25.2** | 1.5σ | **🎯 NEW recovered FN** — Option B (score-diff-targeted self-play, no NN-value blend) is a real +25 elo gain over iter_01. iter_B1 should become global-best. |
| iter_01 c=2.0 NEW vs c=1.5 OLD @ sims=200 | 400 | 200W/194L/6D | **+5.2** | 0.3σ | **genuine null** — c=2.0 does not beat c=1.5; the c-axis is closed at this resolution (n=400 against the ~+20-30 elo effect-of-interest has ~65% power; a small positive effect could still hide) |

**Headline:** Of the 4 hypothesized false-negative-suspect calls, the math from the prior entry (P(at least one recovered) ≈ 40-50%) actually delivered 2 recoveries. **The biggest is iter_B1: the project's claimed "plain v2.7 plateau at iter_01" was wrong — Option B (score-diff value targets, no blend) is a +25 elo lever the n=100 verdict (49% wr, +4.6 score diff) called null.**

**Decisions:**
1. **Promote `checkpoints/v25_retrain_optionB_iter1/iter_00.pt` to global-best**, replacing iter_01. Update CLAUDE.md "current global-best" line accordingly.
2. **Reframe the "plateau" finding.** The 2026-05-19 entry concluded "two-strategy plateau (iter_02 + iter_B1) is real" — half of that (iter_B1) is now retracted. The plain v2.7 *recipe* (W/L value targets, vanilla self-play) really does plateau at iter_01 (iter_02 confirmed at n=400). But the Option B *variant* of the recipe (`score_diff` value targets) is a real +25 elo lever. The plateau is recipe-specific, not net+leaf-bound.
3. **n=400 is the new minimum** for matched-strength comparisons (already decided in the prior entry). Re-confirmed empirically: 3 of the 4 n=100 verdicts in this set were within ±15 elo of a genuinely-different n=400 reading.
4. **No retraining of the deepsearch verdict's downstream implications** — the 2026-05-19 (late) entry's call ("deepsearch becomes global-best for the sims=800 play regime if confirmed") stands and is now confirmed. Deepsearch is global-best for sims=800-plane play; iter_B1 is global-best for sims=200-plane play. (Practical implication: choose the checkpoint by your play-time sims setting. Most matches will be sims=200 → iter_B1; sims=800 power moves → deepsearch.)
5. **PUCT c-axis closed at this resolution.** c=2.0 vs c=1.5 at +5.2 elo / 0.3σ is the strongest single-axis-sweep negative result yet. A real +20 elo c=2.0 effect would need n≥800 to detect at α=0.05 — not worth the compute.

**Broader audit — other reservoirs of likely false-negatives (next-step planning):**

The n=100 verdicts were one source. Reservoirs we should sweep through next:
- **Single-iteration rejections.** Many recipes were killed after one self-play+train cycle. Recipes that compound over 2-3 iters (like Option B might — iter_B1 is +25, iter_B2 could be more) look flat-vs-prev each step. **Highest EV: chain Option B forward (iter_B2, iter_B3, iter_B4) before assuming the lever is single-shot.**
- **Smoke-test rejections (n=20-50).** Even more underpowered than n=100. Any past variant rejection where the smoke landed within ±50 elo of zero was effectively "unknown" — re-run candidates that had borderline smokes.
- **Coarse hyperparameter sweeps.** Only 2 c_puct points tested (1.5 vs 2.0, now null) — never tried 0.5, 3.0, 5.0. Cap sweep stopped at the v2.7-era optimum (5 → 12) — never tested cap=20 or cap=∞. Network: 6×96 ResNet picked in Phase 3, never re-swept at v2.7-era data scale.
- **Pre-bug-fix benchmarks.** The v2.5 farm/city dedup fix (2026-05-15) shifted optima. Any variant rejected *before* that fix was tested against inflated bonus magnitudes — verdicts may not hold.
- **Other plane mismatches.** The sims=200 / sims=800 mismatch was caught. Other potential mismatches: cap value at train vs play, leaf-eval variant at train vs play, orchestrator on/off — not systematically audited.

**Next-step plan (drafted separately, to be wired into a multi-day autonomous pipeline while Joshua is away):** chain Option B forward 3-4 iters; wider c_puct sweep at sims=200; cap=20 and cap=∞ smokes. See STATUS.md "Next" for the queued sequence.

**Reversal cost:** medium. The iter_B1-as-global-best call is well-supported (1.5σ at n=400) but not as solid as iter_01's original promotion (1.9σ at n=100 against warmstart). If a future n=400 deepsearch-style re-test pulls iter_B1 back below iter_01, we'd re-revert. The plateau-retraction is a real correction; the original conclusion was actively misleading and gated several decisions on the wrong premise.

**Phase:** 4 (self-play) — strength.

## 2026-05-19 (late) — Deepsearch verdict revised: anchor-gate plane mattered; matched-regime (sims=800) reading is +17 elo / 52% wr (n=100) — within noise but flips sign from the sims=200 verdict

**Context.** The earlier 2026-05-19 entry below ("Deeper-search self-play retrain did not advance") rested on a single anchor-gate at sims=200. After publishing it, the question came up: deepsearch was *trained* with sims=800 teacher search — was it fair to evaluate it at sims=200 play, the regime tuned to iter_01? The natural matched-regime test (deepsearch vs iter_01 both played at sims=800, n=100) had not been run. We then ran it.

**The run.** Same 100 (seed, player) pairs as the sims=200 anchor (seeds 900000–900099, i%2 player split). Both sides played at sims=800. Work-stealing across both boxes via a newly-extracted `carcassonne_ai.claim` module + a `--shared-claim` flag added to `eval_iter_head_to_head.py`. The eval started as a manual seed-split (5800X 70 / Xeon 30); mid-run the durability gap (no crash failover) prompted a pivot to shared-claim — 54 cached games preserved via exists-check, then both boxes ran the *same* `--games 100 --seed-start 900000` command pointed at one CIFS eval_dir; the claim primitive divvied up the remaining 43 seeds atomically. 24 active workers, 14 5800x + 10 xeon. Wallclock ~3.5h end-to-end (kill→pivot→restart→complete).

**Result.** deepsearch (NEW) vs iter_01 (OLD), 100 games: **52W / 1D / 47L, avg diff +0.61, elo +17.4** (0.50σ above 50%; binomial SE ±5pp).

**Comparison across measurement planes:**

| play sims | result | avg diff | elo |
|---|---|---|---|
| 200 (anchor-gate v1, iter_01-matched) | 45W/0D/55L | −1.2 | **−34.9** |
| 800 (anchor-gate v2, deepsearch-matched) | 52W/1D/47L | +0.6 | **+17.4** |

~52-elo swing from measurement plane alone, with a clean sign flip. Each reading individually is within its noise band (0.5–1σ from 50%); the *anti-correlation* across planes is the suggestive signal — if both were pure noise we'd expect drift in the same direction or independent, not a clean flip.

**What this changes about the prior entry.** "The plain v2.7 retrain recipe is confirmed plateaued at iter_01 across all three lever attempts" overreached on the deepsearch leg. iter_02 (+0.2 at sims=200, iter_01's matched plane) and iter_B1 (+4.6 / 49% at sims=200, iter_01's matched plane) remain flat — those were measured at their training-matched plane and the conclusion stands for those legs. The deepsearch leg was measured *off-plane* and the matched-plane reading is ambiguous (point estimate slightly positive, not significant). The two-strategy plateau (iter_02 + iter_B1) is real; calling it three strategies was wrong.

**Hypothesis the data is consistent with.** Training-sims and play-sims should match. A deeper-teacher policy is tuned to behaviors a deeper search will actually take advantage of at play time; at shallower play it may even score slightly worse because the policy is now relatively under-confident in lines a deeper search would close out. Not proven at n=100 (point estimate within noise) — but the +52-elo flip is the right shape if the hypothesis holds, and the wrong shape if both readings are pure noise.

**Decision.** (1) Do NOT promote deepsearch to global-best yet — +17.4 elo at 0.5σ doesn't clear the same bar iter_01 cleared (1.9σ at n=100 in 2026-05-16). (2) **The n=200 confirmation plan was upgraded to n=400** after a meta-audit (next entry below) revealed n=100/200 is below the resolution needed for matched-strength comparisons in this project. (3) **Conditional on the n=400 confirmation:** if the matched-plane edge holds (≥+30 elo ≈ 1.7σ at n=400), deepsearch becomes the new global-best **for the sims=800 play regime**; if it reverts to ~50%, iter_01 stays. Either way the +200 elo sims=200→800 play-time win (2026-05-18 sims-ladder) is a free side-channel benefit independent of which checkpoint is selected.

**Independent of the n=200 outcome:** the broader claim "the v2.7 leaf is the ceiling" is now less load-bearing. iter_02 and iter_B1 are still flat, so the policy IS saturated at iter_01-matched-plane evaluation. But the deepsearch leg leaves open the chance that training-and-play matched search regimes have more room than the sims=200-only view suggested. Leaf-eval redesign remains the highest-leverage longer-term lever; the matched-regime hypothesis is a cheaper near-term experiment if n=200 confirms.

**Reversal cost:** low. The original entry stays below (history); this entry corrects its conclusion in light of the matched-plane data.

**Phase:** 4 (self-play).

## 2026-05-19 — Deeper-search self-play retrain did not advance; v2.7 plateau confirmed across 3 strategies — leaf-eval becomes the next ceiling

> **2026-05-19 (late) — partial retraction:** see the entry immediately above. The deepsearch leg of this argument used the wrong measurement plane (sims=200 anchor); at the matched sims=800 plane the verdict is ambiguous (+17.4 elo, 0.5σ above 50%) rather than negative. The iter_02 and iter_B1 legs were measured at their matched plane and stand. The original text below is preserved unedited for history.


**Context.** STATUS 2026-05-18 had two strength levers still on the table: (a) deeper-search self-play — retrain with a sims=800 teacher (might un-stick the plateau); (b) leaf-eval redesign (bigger project). The sims-depth A/B (iter_01 @ sims=800 vs itself @ sims=200, n=50, +200 elo) had proved search itself is a large lever *given the leaf* — the working hypothesis was that compounding stronger teacher search into training would lift the policy at production sims=200.

**The run.** 1200-game sims=800 self-play from iter_01, work-stealing across both boxes (one shared SMB folder, atomic-claim load-balance — commit 1895b02). Dataset finished clean (1200/1200, no failures). `train_iter.py` on the 1200-game buffer (188,736 train positions, warm-from iter_01, 3 epochs, batch 256, value-target score_diff per the running default — harmless here, see 2026-05-19 value_target note in BACKLOG.md) → `checkpoints/v25_retrain_deepsearch/iter_00.pt`. Anchor-gate `eval_iter_head_to_head.py`: new vs iter_01, n=100, sims=200 both sides, v2.7 leaf (`CAP=12`, drop-3-open), orchestrator, batch_size=1.

**Result — 45W / 0D / 55L, avg diff −1.2, elo_delta −34.9.** Within ~1σ of flat (n=100 binomial SE ~5pp), not significantly worse, definitely not better. The running tally trended steadily down through the run (60% after 20 → 53% after 40 → 47% after 60 → 43% after 80 → 45% final) — consistent with early-fluke regression to a true ≈50%.

**Compound with the prior anchor-gates from iter_01:**
  - iter_02: +0.2 avg diff (flat — DECISIONS 2026-05-17)
  - iter_B1 (Option-2 value-head blend pipeline, score_diff value head): 49W/0D/51L, +4.6 avg, elo −6.9 (≈ iter_01 — DECISIONS 2026-05-18)
  - deepsearch (this run, stronger teacher search): 45W/0D/55L, −1.2, elo −34.9 (≈ iter_01, slightly worse end of noise)

Three independent strategies — same recipe more iterations, value-head blend, stronger teacher search — all return flat-to-slightly-worse from iter_01. **The plain v2.7 retrain recipe is now confirmed plateaued at iter_01 across all three lever attempts.**

**Why.** The sims=800-at-PLAY result (+200 elo, 2026-05-18) proved search is a large lever *given the leaf*. But teacher-search quality only flows into training as POLICY targets, and a sims=800 teacher's targets are still bounded by what the v2.7 heuristic scores as good during that search. Stronger search refines the policy toward what THIS leaf considers best; it cannot teach the policy moves the evaluator can't recognize as good. iter_01 has converged to ≈ what the v2.7 leaf can teach; deeper teacher search doesn't widen that ceiling.

**Decision:** close deeper-search self-play as a strength lever *for this leaf*. Global-best remains `checkpoints/v25_retrain_iter01/iter_00.pt`. Next strength lever — Joshua's call (no auto-launch): **leaf-eval redesign** is now the only un-closed strength lever for the v2.7-recipe line (BACKLOG.md 2026-05-16 captures the strategy-lit ideas — tile-counting closure P, large-open-city penalty, targeted denial, meeple economy, farm majority-flip).

**Independent of this verdict:** the sims=800-at-PLAY +200-elo gain (2026-05-18 sims-ladder) is still on the table as a free win for production play — no retrain, ~4× per-move latency (fine for human-paced play). Should land in the production config whenever play-vs-human is wired up.

**Reversal cost:** low — checkpoint kept (`checkpoints/v25_retrain_deepsearch/iter_00.pt`), buffer kept (`/mnt/c/carc-shared/deepsearch/iter_00/`); the conclusion can be revisited if a leaf-eval redesign changes the substrate the policy is training against.

**Phase:** 4 (self-play).

## 2026-05-19 — Code-review loop: 14 fixes; work-stealing stale-recovery race accepted, not redesigned

**Context.** A 4-iteration multi-agent review of all living code (24 agent-reviews — 6 subsystems × 4 passes). Applied 14 safe corrections (F1–F14, see REVIEW_LOG.md); deferred 16 findings (D1–D16). Most deferrals are routine (latent / unreachable / retraining-boundary — tracked in REVIEW_LOG.md and BACKLOG.md). One — D15 — is a genuine architecture call worth recording here.

**D15 — the work-stealing stale-claim recovery (`_try_claim`) has a TOCTOU race.** When several workers re-claim the same abandoned (stale) seed, a worker that judged staleness against the *old* claim can `os.rename` aside a *fresh* claim re-created by an earlier winner — so N racers can yield up to N winners, not one. The fast path (the O_EXCL create) is unaffected and correct; this is recovery-only.

**Options considered:**
  - A: Redesign recovery to be single-winner — a per-seed `.recovering` O_EXCL lock, or capture-`st_ino`-then-re-verify. Correct, but ~half a day, and a botched fix to a *live* primitive could lose a claim (a seed never played → a training game silently missing) — strictly worse than the current behavior.
  - B: Accept it. The duplication is bounded (≤ N) and fires only on crash-recovery; the atomic `.npz` write (last-writer-wins) means the worst case is a few duplicate games — wasted compute, never corruption. Relax the docstring's "exactly one winner" overpromise and the test (`xfail` → assert `1 ≤ winners ≤ N`).

**Decision:** chose B — accept + document.

**Reason.** The `.claim` is a *best-effort* lock by design; correctness is owned by the atomic `.npz`. The race's worst case is a handful of recomputed games after a box crash. Option A's risk — losing a claim on a live primitive — is not justified by that. Parked in BACKLOG.md if the cost ever proves real.

**Reversal cost:** low — option A stays available; the BACKLOG entry preserves the analysis.
**Phase:** 4 (self-play).

## 2026-05-18 — Option 2 (NN value-head leaf blend) closed; plain v2.7 recipe confirmed plateaued

**Context.** iter_02 flatlined (+0.2 over iter_01) → working hypothesis: the policy had saturated against the *fixed* v2.7 heuristic leaf. Option 2's response: blend the network value head into the leaf — `leaf = (1−λ)·tanh(vs2/15) + λ·v_nn` — so the leaf co-improves with the policy. Phase A wired it (eb42c25); the λ=0.5 fixed-checkpoint smoke with iter_01's *W/L* value head gave −11.3 avg / 46% wr, hypothesised as a currency mismatch (W/L head vs score-diff heuristic leaf). Phase B: iter_B1 minted a *score-diff* value head (1200-game retrain from iter_01); the re-smoke tested blending it.

**Result — re-smoke (n=50, iter_B1 blended-λ=0.5 vs plain leaf).** −15.5 avg / 31% wr (15W/1D/34L) — *worse* than Phase A, not better. The currency-mismatch hypothesis is refuted. A residual-structure diagnostic (60 games, 9946 positions) confirmed the mechanism: the NN value head correlates only +0.18 with the true outcome vs the v2.7 heuristic's +0.61, and is beaten by the heuristic in every game-phase quartile; the MSE-optimal static blend cuts prediction error only ~4% (in-sample-optimised, so an overestimate).

**Result — iter_B1 strength.** iter_B1's own anchor-gate (n=20) scored 70%/+12.6 vs iter_01, which looked like a gain. An n=100 confirm corrected it: **49W/0D/51L, +4.6 avg diff, elo −6.9** — iter_B1 ≈ iter_01 (even win rate, a marginal score-diff edge at most). The n=20 was a high-side fluke.

**Decision.** (1) **Option 2 is closed** — value-head injection abandoned, both the convex blend and the residual-head variant. The 7.4M-param value head on ~1200 self-play games is simply a weaker position evaluator than the hand-tuned v2.7 heuristic; no blend repairs that. Triple-confirms the v1–v6 finding. (2) **The plain v2.7 self-play recipe is plateaued** — iter_00→iter_01 gained big (+13.3), iter_01→iter_02 flat (+0.2), iter_01→iter_B1 flat (+4.6 / 49%). More plain retrains will not move the needle.

**Reason.** Both the exotic lever (NN-value-leaf) and the simple lever (more plain self-play) are now empirically exhausted against the v2.7-heuristic-leaf ceiling.

**Next.** Not another training-recipe tweak. The real blocker (per EXPERIMENTS.md) is that no checkpoint has been benchmarked against a strong human — "superhuman" is undefined-by-measurement. Branch decision: benchmark iter_01-level play vs a human / strong reference to learn where we actually stand, then either pivot toward Phase 5 (if it clears the bar) or commit to a harder strength lever (heuristic-leaf redesign, net capacity, or search-side knobs — see EXPERIMENTS.md open list).

**Reversal cost:** low — the Option 2 infra (`LeafConfig.value_blend`, blend wiring, `--value-target score_diff`) stays in the tree dormant; revisiting needs a materially stronger value head.
**Phase:** 4 (self-play).

## 2026-05-17 — self-play perf optimization: hash-cache + get_side shipped; deeper leaf-eval memoization (Options A & B) parked — find_farm is start-dependent

**Context.** iter_01/iter_02 each took ~11h of local self-play; iter_B1 and any future iterations pay the same. Profiling one production self-play game (sims=200, v2.5 leaf) showed the heuristic leaf eval is ~83% of CPU, with object hashing ~31% of self-time and the set-based connected-component flood-fills (`find_farm` 328s cumulative, `find_city` 96s) dominating. Three optimization tiers were considered, cheapest first.

**Tier 1 — shipped (committed `080fea7`, on `gpu-orchestrator`).** Cache `__hash__` on the immutable engine value objects (`Coordinate` family, `FarmerConnection`) and precompute `FarmerSide.get_side` (it was walking the enum `.value` descriptor up to 4× per call). Both behavior-preserving (bitwise-identical hashes / outputs; full suite green). cProfile re-profile: 651→561s — ~14% from hashing alone, `get_side` projected ~+12%, ~20-24% combined. Live in iter_B1.

**Tier 2 — Option A, memoize the find_* flood-fills — PARKED.** Cache `find_city`/`find_road`/`find_farm` results per board on the game state, invalidated at the single tile-placement site (`StateUpdater.play_tile`). find_city + find_road were memoized and verified bitwise-identical via a differential test (240 states early/mid/late/terminal + the in-place MCTS-rollout path + `count_final_scores`, all memo-on == memo-off). **But `find_farm` — the #1 hot path — is start-dependent**: the engine's farm flood-fill returns *different* farmer-connection sets depending on which connection you start from (verified by the differential test: 11 vs 4 from the "same" farm). Caching a farm under its member positions is therefore unsound — a query would hit a result computed from a different start point. find_farm was reverted; the surviving find_city+road memo is only ~6% (find_city is ~96s of the ~420s of find_* cost). Committed on branch `leaf-memoization` (`3db30f1`), **not merged**.

**Tier 3 — Option B, incremental connected-components (union-find) — PARKED, not started.** A union-find represents *symmetric* connectivity by construction, so it cannot reproduce a start-dependent `find_farm` without adopting the corrected symmetric farm semantics — which would change the leaf's farm bonus and `count_final_scores`' farm points (a behavior change, not a transparent optimization). For cities/roads alone it could beat Option A's 6% modestly (~10-12%) but needs incremental maintenance on every tile placement (touching `apply_action_inplace` + every River/farmer edge case) — worse risk/reward than A.

**Options considered:**
  - A: Memoize find_* (Tier 2). Found unsound for find_farm; the safe remainder is ~6%.
  - B: Incremental union-find (Tier 3). Cannot represent the engine's start-dependent farm semantics; cities/roads-only is marginal at higher risk.
  - C: Ship Tier 1, park A and B.

**Decision:** chose C.

**Reason.** `find_farm` is ~58% of the leaf-eval cost and is structurally resistant to *both* memoization and union-find, because the engine's farm traversal is start-dependent — no caching strategy reaches it. The reachable remainder (find_city+road) is only ~6%, and it is a vendored-engine change on the scoring path (project-wide blast radius — `count_final_scores` feeds real game outcomes and training labels), so a ~6% gain does not justify the merge-risk attention. The only routes to the find_farm win are (a) micro-optimizing its flood-fill internals — grindy, and the easy parts (hashing, get_side) are already done — or (b) deliberately replacing the buggy start-dependent `find_farm` with a correct symmetric one, a behavior change needing a re-validation A/B, not a free optimization. Neither is worth diverting from the iter_02-ceiling work (Option 2 / iter_B1). Local optimization has hit diminishing returns at the ~20-24% already banked.

**Reversal cost:** low. Tier 1 is committed and behavior-preserving. Option A's verified work sits on `leaf-memoization` if the 6% is ever wanted; Option B was never built.

**Phase:** 4 (self-play infrastructure).

## 2026-05-17 — closure-probability accuracy is not the leaf-eval lever; Option-1 (heuristic-leaf refinement) yields two null results → pivot to Option-2

**Context.** The iter_02 entry below established the next lever is leaf-eval quality, and named two candidates: (1) improve the heuristic leaf, (2) NN value head as a correction term. Option 1 was tried first — lower risk, incremental. The most lit-review-backed leaf refinement was tile-counting closure probability: `virtual_score_v2`'s closure-anticipation bonus uses a fixed P(closure) schedule `{1:0.5, 2:0.2}` keyed only on a feature's open-position count; it never consults the remaining deck. A city needing 3 more city-tiles when only 1 city-tile remains in the deck *cannot* close — yet the fixed schedule still pays the bonus. Making P(closure) deck-aware should be strictly more accurate.

**Infra built (committed, kept regardless of outcome).** `LeafConfig` dataclass — per-evaluator config, replacing the process-global `CARCASSONNE_V25_*` env vars — plus `--{new,old}-leaf-variant` on `eval_iter_head_to_head.py`. Two leaf variants can now run in one process for a clean same-checkpoint leaf-vs-leaf A/B. Reusable for Option-2 tuning. Commits f83ce34, 89f82e3, 1f1c01f.

**Test design.** Both A/Bs: iter_01 checkpoint on *both* sides, only the leaf differs — isolates the leaf change with zero confound from network strength. n=100, sims=200, v2.7 production knobs (cap=12, drop-3-open).

**Two variants tried.**
- *Step 3b — hard tile-counting gate.* P(closure)→0 only when the deck literally cannot finish the feature. **45W/1D/54L = 45% wr, −4.8 avg score diff.** Within noise of 50%, point estimate negative.
- *Step 5 — continuous deck-aware ramp.* P(closure) scaled smoothly by `_supply_factor(supply, need, slack=3)` — discounts in the mid-game, not just the impossible endgame. Unit tests confirm it fires on far more positions than the cliff. **50W/1D/49L = 50% wr, −1.4 avg score diff.** A flat wash.

**Verdict — closure-probability accuracy is not the lever.** The hard gate's 45% could be dismissed as "the cliff fires too rarely." The continuous ramp was built precisely to kill that objection: it fires constantly in the mid-game and still nets *exactly zero*. Pooled across both benches the deck-aware-closure direction is 95/200 = 47.5% — a tight null. MCTS does not need a calibrated P(closure); the rough fixed schedule is already sufficient.

**Decision — Option 1 is closed for the closure-probability angle; pivot to Option 2 (NN value-head correction term).** Reasoning: iter_02 established that the policy saturates against a *fixed* leaf. Hand-tuning the leaf only nudges a fixed ceiling — and two n=100 benches now show how little it nudges. Option 2 makes the leaf value carry a *learnable* component (the value head, trained on iter_01/iter_02's now-good self-play outcomes), so the leaf co-improves with self-play and the ceiling is no longer fixed. That attacks the saturation diagnosis structurally, where leaf hand-tuning cannot.

**Caveat — not every leaf refinement is dead.** Closure-P was one of ~4 lit-review refinements (large-open-city penalty, targeted denial, stranding-risk meeple weighting remain, parked in BACKLOG 2026-05-16). A null on closure-P does not prove a null on those — they are different *features*, not recalibrations of an existing term. But chasing them one-at-a-time is diminishing returns against the structural fix; Option 2 takes priority. The remaining refinements stay parked.

**Reversal cost:** low. The closure-continuous code is committed and off by default (`LeafConfig.closure_continuous_slack=0.0`); production behavior is unchanged. If Option 2 stalls, the parked refinements are still available.

**Phase:** 4 (self-play / leaf-eval).

## 2026-05-17 — iter_02 flattens: policy saturated against the fixed v2.7 leaf; the compounding ceiling is found

**Context.** iter_00 beat warmstart_canonical by +14.3 (2026-05-15); iter_01 beat iter_00 by +13.3 (2026-05-16). Two consecutive ~+14pt jumps from the same recipe (v2.7 leaf, 1200-game self-play, retrain from prev) raised the question: does it keep compounding? iter_02 — a third iteration, same recipe, from iter_01 — tests it.

**Run.** 1200-game v2.7 self-play from iter_01, local, W=14, 11.3h, $0. Pure self-play training (warmstart-mix 0.0), same recipe as iter_01.

**Result.** Anchor-gate vs iter_01 n=20: 11W/0D/9L = 55%. n=100 confirmation: **51W/5D/44L = 53.5% wr, +0.2 avg score diff, +24.4 elo.**

**Verdict — the compounding flattened.**

| step | avg score diff | n=100 wr |
|---|---|---|
| warmstart → iter_00 | +14.3 | (61.7% anchor n=30) |
| iter_00 → iter_01 | +13.3 | 59.5% |
| iter_01 → iter_02 | **+0.2** | **53.5%** |

53.5% is only 0.7σ above 50% (n=100 SE ~5pp) — within noise. The score-diff signal, the reliable one all week, says **+0.2 = zero gain**. iter_02 ≈ iter_01.

**Decision. iter_01 (`checkpoints/v25_retrain_iter01/iter_00.pt`) remains the global best. iter_02 is NOT promoted.** Promoting on 0.7σ would be the exact n=20-noise mistake the v3 cap sweep and PUCT c=2.0 sweep both made this week — at n=100 the discipline is the same: a sub-1σ wr gain with a zero score-diff is not a confident improvement. iter_02 is *equivalent* to iter_01, not better. (iter_02's checkpoint is kept; future work can warm-start from either — they're interchangeable.)

**What this establishes — the data-scarcity hypothesis was right but bounded.** More v2.7-recipe self-play helped for *exactly two iterations* (+14.3, +13.3), then hit a wall. This is **policy saturation against the fixed leaf**: `virtual_score_v2` is a fixed hand-crafted heuristic that never improves, so it defines a ceiling — "the best policy prior achievable given this leaf." iter_01 reached that ceiling; iter_02 can't exceed it. The sharp drop (+13.3 → +0.2, not a gradual taper) is the signature of a hard ceiling, not gradually-diminishing data returns.

**What this rules out.**
- *More iterations of the same recipe* — iter_03+ would also land ~+0. Dead direction.
- *Bigger policy net* — a higher-capacity policy head would saturate against the *same* leaf. Capacity is not the bottleneck. Bigger-net is de-prioritized by this result.

**What this points to — the next lever is leaf-eval quality.** Two candidate structural changes (both gated on a plan-mode session, neither auto-started):
1. **Improve the heuristic leaf** — the competitive-strategy lit-review refinements parked in BACKLOG 2026-05-16 (tile-counting closure probability, large-open-city penalty, targeted denial, stranding-risk meeple weighting). Lower-risk, incremental.
2. **NN value head as a correction term** — train a value head on the now-good iter_01/iter_02 self-play outcomes and use it to correct virtual_score's known blind spots (farm-composition path-dependence especially). Higher-ceiling, more invasive. The value head failed in v1-v6 because it trained on degrading self-play; it now has strong games to learn from.

**Also still open: no human benchmark.** iter_01 has never played a human. Before committing to a structural leaf change, knowing where iter_01 actually stands vs a strong human would size the remaining gap to "superhuman" — worth doing first or in parallel.

## 2026-05-14 — v2.5 hyperparameter sweep: sims=200 is the sweet spot, cap=5 is the inverted-U optimum

**Context:** After v2.5 cleared the v1 baseline at sims=400 (83.3%), two open tuning questions: (1) does sims<400 still match? (2) is cap=5 actually right, or did we get lucky?

**Sims sweep** (hybrid_v2.5 vs Tier-1, n=30 each):

| sims | v2.5 wr | v1 wr (same config) | Δ |
|---|---|---|---|
| 50  | 50.0% | 63.3% | -13.3pp |
| 100 | 71.7% | 58.3% | +13.4pp |
| **200** | **80.0%** | 70.0% | **+10.0pp** |
| 400 | 83.3% | 76.7% | +6.6pp |

**v2.5 ramps with depth more steeply than v1.** At sims=50 v2.5 is *worse* than v1 (the bonus is noise without enough search depth). At sims≥100 the anticipation signal becomes informative and v2.5 pulls ahead. **sims=200 is the new sweet spot** — 80% wr at half the compute of sims=400 (only 3pp less). Production for ablation benches: sims=200. For raw-strength benches: sims=400.

**Cap sweep** (cap ∈ {2, 5, 8, 15} at sims=200 n=30):

| cap | v2.5 wr | Δ vs cap=5 |
|---|---|---|
| 2  | 60.0% | -20.0pp |
| **5 (production)** | **80.0%** | — |
| 8  | 73.3% | -6.7pp |
| 15 | 76.7% | -3.3pp |

Clean inverted-U: cap=2 strangles the bonus signal; cap=8/15 reintroduces tanh saturation (smaller dose of v2's failure mode). Hand-picked cap=5 happens to land on the knee. n=30 SE ~9pp, so cap=5 dominance over cap=2 is decisive (~2σ); over cap=8/15 it's suggestive but not bulletproof.

**Decision: production = `_BONUS_CAP=5.0`, sims=200 (ablation) or sims=400 (raw strength).**

**Plumbed:** `CARCASSONNE_V25_CAP` env var on `virtual_score_v2.py` for future cap sweeps without source edits.

**Lesson:** when a hand-picked initial value happens to be optimal, the clean inverted-U around it is reassuring — confirms it's not a knife-edge dependent on noise. If cap=5 had been on a slope, we'd worry the next change downstream might shift the optimum.

## 2026-05-16 — iter_01 retrain confirms data-scarcity hypothesis: more v2.7 self-play → stronger model

**Context.** iter_00 (1200-game v2.7 self-play retrain) beat warmstart_canonical +21pp on 2026-05-15. Open question: was that a one-shot warmstart→trained jump, or does the recipe keep compounding with more self-play? iter_01 tests it — another 1200 games, same recipe, initialized from iter_00.

**Run.** Launched locally (vast.ai's docker-pull infra was down — 7 boxes stalled; see [[feedback-vastai-success-false-still-creates]]). 1200-game v2.7 self-play, W=14 (the v2.7-recipe worker optimum, freshly benched — not the old W=16 NN-value optimum), sims=200, c_puct=1.5, initialized from iter_00. **Pure self-play training** (`--warmstart-mix-schedule 0,0,0,0`) to replicate iter_00's exact recipe — iter_00 trained with `warmstart_in_list=0` because the cloud box never had the warmstart .npz, so for a clean "more data, same recipe" A/B iter_01 matched that. 10.6h wallclock, $0.

**Result.** Anchor-gate vs iter_00 n=20: 12W/0D/8L = 60% wr, +11.8 avg diff. **n=100 confirmation: 59W/1D/40L = 59.5% wr, +13.3 avg score diff, +66.8 elo.**

**Why the n=100 confirmation.** 60% at n=20 is only ~0.9σ above 50% — the same noise band that produced false winners in the v3 cap sweep and PUCT c-sweep this week (both evaporated at larger n; see [[feedback-n50-min-for-variant-comparison]]). iter_01's 60% was NOT allowed to stand on n=20. At n=100 it held at 59.5% (~1.9σ above 50%) with the score-diff signal *strengthening* (+11.8 → +13.3). First n=20 result of the week to survive — because this one was real.

**Decision. iter_01 (`checkpoints/v25_retrain_iter01/iter_00.pt`) is the new global best.** Supersedes iter_00 and the v6 `iter_12.pt`.

**What this establishes.** The +13.3 score-diff over iter_00 is a similar magnitude to iter_00's +14.3 over warmstart_canonical. Two consecutive ~+14-point jumps from the same recipe → **the ceiling is data quantity, not recipe or architecture.** The v1-v6 plateau was a leaf-eval problem (NN value head), not a fundamental one. With the v2.7 leaf, each 1200-game retrain compounds.

**Open question for iter_02.** Does a third iteration keep the ~+13 cadence, or do returns diminish? If iter_02 also lands ~+13, a longer multi-iter run is clearly worth the compute. If iter_02 flattens, we've found the data-per-iteration knee and should either grow games/iter or accept the current level and pivot to human-play evaluation. iter_02 not launched autonomously — pending Joshua's go.

## 2026-05-15 — PUCT c sweep: low c (≤1.0) catastrophic; default c=1.5 is well-chosen; don't promote c=2.0

**Context.** After v3 cap tuning closed as inconclusive, ran the PUCT c sweep from EXPERIMENTS.md as the next ablation. The 2026-05-14 diagnostic identified "low c → search over-explores into virtual_score's blind spots" as a hypothesis. PUCT formula: `U(a) = Q(a) + c · P(a) · sqrt(N_parent)/(1+N_child)`. Low c down-weights the NN policy prior P(a), so search explores more uniformly.

**Sweep.** iter_00 + v2.7 leaf vs Tier-1 at sims=200, n=20:

| c_puct | iter_00 wr | score diff (NN POV) |
|---|---|---|
| 0.5 | 67.5% | +4.2 |
| 1.0 | **52.5%** ← barely beats Tier-1 | +7.2 |
| 1.5 (current default) | 80% | +27.4 |
| 2.0 | 85% | +40.3 |
| 3.0 | 75% | +37.0 |

**Confirmation runs (n=50, per the n=50-for-comparison memory rule):**
- c=2.0: iter_00 88% wr, score diff -38.5 (rule POV)
- c=1.5: iter_00 84% wr, score diff -38.0 (rule POV)

**Result.** c=2.0 vs c=1.5 at n=50: indistinguishable. WR gap 4pp ≈ 0.6σ (SE ~7pp combined). Score-diff gap 0.5pt = effectively zero. The n=20 spread between c=1.5/2.0/3.0 was within noise; only c=2.0's *winner-at-n=20* status was noise.

**Real finding: catastrophic low-c boundary.** c=1.0 → iter_00 52.5% (nearly ties Tier-1, who is supposed to lose 80%+ of the time). c=0.5 → 67.5%. Both well outside n=20 noise; score-diff signal confirms (+4 to +7 vs default's +27). The 2026-05-14 hypothesis "low c over-explores into virtual_score's blind spots" is CONFIRMED. The NN policy prior is load-bearing — search has to trust it heavily, not explore around it.

**Decision.** Default c=1.5 stays. Don't promote c=2.0. Add a note to mcts.py's `DEFAULT_PUCT_C` constant explaining the lower bound is enforced by empirical data (c≤1.0 catastrophic).

**Why this matters for future work.**
1. If anyone (or future-me) tries to lower c "for more exploration," they'll break iter_00's strength. The constant comment should warn.
2. iter_01 retrain doesn't need a c_puct hyperparameter sweep — c=1.5 is in the flat region, not on a knife-edge.
3. The result indirectly confirms iter_00's policy prior is **well-trained enough that search wants to trust it.** This is a positive signal for the training pipeline.

**Today's second case of n=20-noise-evaporating-at-n=50.** v3 cap tuning (morning) and PUCT high-c promotion (afternoon) both looked like winners at n=20 and collapsed at n=50. The n=50 memory rule has earned its keep twice today. See [[feedback-n50-min-for-variant-comparison]].

## 2026-05-15 — v3 leaf: cap tuning is fitting n=20 noise; v2.7 cap=12 is at the local optimum (or indistinguishable from one)

**Context.** Post-iter_00 retrain landed today, the next leaf-eval iteration was v3 — two additions from the 2026-05-14 failure-mode diagnostic that v2.7 didn't address:
1. **Meeple economy** — `_MEEPLE_K × (meeples_self - meeples_opp)` added after caps (failure-mode 4: over-committed meeples).
2. **Asymmetric opp cap** — `_OPP_BONUS_CAP` separate from `_BONUS_CAP`, raising it amplifies the negative contribution of opponent's near-closures to search value (failure-mode 3: denial invisible).

Implementation refactor: cap moved from inside `_closure_anticipation_bonus` to `virtual_score_v2` via a `_capped(bonus, cap)` helper. Without this, self and opp couldn't be capped differently. Tests updated to reflect the new location.

**Key fact about the bench setup.** The bench was rule_player vs iter_00 (opponent=hybrid_v2). `RuleBasedPlayer` uses `virtual_score_inplace` from `virtual_score` (v1, NOT v2) — see `src/carcassonne_ai/rule_based_player.py:46`. So the `CARCASSONNE_V25_*` env vars **only affect the NN's hybrid_v2 leaf, not the rule-player side.** Tier-1's behavior is invariant under v3.

This means the sweep is a direct test of "does v3 leaf strengthen iter_00 against Tier-1?"

**Sweep.** rule_player (Tier-1) vs iter_00+v3 at n=20 sims=200 W=12+orch. Tier-1 uses v1 virtual_score (env-var-immune), so env vars affect only the NN's hybrid_v2 leaf.

**Full results** (rule_player wr shown; iter_00 wr = 100 - rule wr):

| variant | n=20 rule wr | n=20 iter_00 wr | n=50 iter_00 wr | n=50 score diff (rule POV) |
|---|---|---|---|---|
| v2.7 baseline (cap=12, opp_cap=12 implicit) | 10% | 90% | (not run) | -37 (n=20) |
| meeple_K ∈ {0.5, 1.0, 2.0} | 10% (all 3) | 90% | — | -31.8 to -42.2 |
| opp_cap=5 | 5% | 95% | **80%** | -26.3 |
| opp_cap=8 | 25% | 75% | — | — |
| opp_cap=20 | 20% | 80% | 80% | -27.3 |
| opp_cap=30 | 20% | 80% | — | — |

**The n=20 results suggested a story.** At first read: high opp_cap regressed (80% wr), low opp_cap=5 helped (95% wr), opp_cap=8 was a dip (75%). I built a "denial double-counting" hypothesis around it — NN policy prior already encodes opp-threat awareness, so leaf amplification at high cap hurts; low cap helps by reducing double-counting.

**n=50 broke the story.** Both opp_cap=5 and opp_cap=20 landed at 80% at n=50. Score diffs were identical (-26.3 vs -27.3). The whole n=20 spread (75-95%) was fitting noise — at n=20 SE ~7pp, the 90% v2.7 baseline anchor itself is indistinguishable from 80%.

**Correct conclusion.**
- **v3 cap tuning is exhausted.** opp_cap ∈ {5..30} all produce iter_00 wr ~80% ± 5pp vs Tier-1 at n=50.
- **v2.7 cap=12 IS at the local optimum, or indistinguishable from one.** No tuning direction (up or down) moves the needle at n=50.
- **Meeple_K is null** — all 3 magnitudes gave identical outcomes at n=20. Plausibly an additive-on-saturating-cap dead-zone, but with cap itself being non-tunable, this story doesn't matter much.

**Decision.** Keep v3 env-var infra committed (zero default impact: `_OPP_BONUS_CAP` defaults to `_BONUS_CAP`, `_MEEPLE_K` defaults to 0.0). **Production stays at v2.7 cap=12.** Defaults unchanged.

**The two lessons here are bigger than v3.**
1. **n=20 benches at SE ~7pp can't distinguish 75% from 95% wr.** If I'd run the baseline at n=50 alongside opp_cap variants, I'd have known immediately that the "v3 regresses" story was over-read. Standard practice now: anchor measurements at n=50 minimum when comparing variants within 15pp of each other.
2. **Two separate analytical errors compounded today.** First I mis-identified WHICH side of the bench used env vars (wrote "v3 helps rule-player" when env vars only affected the NN). Then I corrected to "v3 regresses NN" without questioning whether the BASELINE was solid. Both errors live in the prior commit messages (`e55f622`, `862ec37`) — this entry is the third-and-correct read. Lesson: when a result reverses a story, also re-question what the *reference* says.

**Where next.** Cap tuning is closed. Three live directions:
1. **iter_01 cloud retrain** on v2.7 leaf (~$2.40, ~6h). Tests data-scarcity ceiling.
2. **Human play vs iter_00.** Tier-1 is saturated as a reference now — same ~80% wr regardless of leaf cap, so it doesn't discriminate iter_00 from anything similar in strength.
3. **PUCT c sweep** (~30 min local). Search-side knob, separate from leaf.

## 2026-05-15 — v2.5 dedup bug fix + cap/P re-sweep + cloud retrain: iter_00 +21pp over warmstart_canonical

**Context:** Pre-launch we held v2.5 at 80% wr vs Tier-1 (sims=200, cap=5, P={1:0.5, 2:0.2, 3:0.05}). Cloud retrain at sims=200 on a vast.ai 5090 box hit 6× the predicted wallclock (5.8h vs 1.6h estimate). Investigated v2.5 leaf-eval cost; found a real over-counting bug: multiple meeples on the same farm/city each got `_closure_anticipation_bonus` added separately, but the engine itself only scores each farm/city once per player. Bonus inflated for multi-meeple farms.

**Bug fix (commit `08dfead`):** dedup farms/cities by canonical content (`frozenset(farmer_connections_with_coordinate)` and `frozenset(city_positions)`). The engine returns fresh `City`/`Farm` objects per call (no `__eq__`/`__hash__`), so identity dedup didn't work — needed canonical fingerprints.

Side-effect: per-leaf perf was within noise (~325s/game/worker locally, same as pre-fix). The dedup was a correctness fix, not a perf fix. But the wallclock projection was honest — 1500 games on cloud takes ~5h regardless. Reduced retrain target to 1200 games.

**Bench fallout:** fixed v2.5 + cap=5 dropped to 70% wr (from buggy 80%). The over-counting was load-bearing on cap=5's tuning. Re-swept cap on FIXED v2.5:

| config (n=20 sims=200 each) | wr | avg diff |
|---|---|---|
| fixed + cap=5 (3-tier P) | 70% | n/a |
| fixed + cap=8 | 60% | -17.8 |
| **fixed + cap=12** | **85%** | -22.4 |
| fixed + cap=20 | 85% | -34.7 |

cap=12 + cap=20 plateau. cap=12 is safer (lower bonus magnitude → less risk in unusual states).

**P-schedule sweep (cap=12 fixed):**

| variant | _CLOSURE_P | wr |
|---|---|---|
| 3-tier (default) | {1:0.5, 2:0.2, 3:0.05} | 85% |
| v2.6 (1-only) | {1:1.0} | 77.5% |
| **v2.7 (drop 3-open)** | **{1:0.5, 2:0.2}** | **90%** |

v2.7 wins by 5pp over 3-tier and 12.5pp over 1-only. **Joshua's intuition:** 3-open features are lottery tickets — the 0.05 weight just adds noise without useful signal. Dropping them removes the noise floor and lets the higher-quality 1-open and 2-open signals dominate.

**Decision:** production v2.5 leaf = `_BONUS_CAP=12` + `_CLOSURE_P={1:0.5, 2:0.2}` (env vars `CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1`). +10pp over the buggy v2.5 ceiling.

**Cloud retrain (commit `f89b5f3`, watchdog `b46b539`):**
- 1200 games of warmstart_canonical-vs-warmstart_canonical self-play with v2.7 leaf
- sims=200, batch=8, virtual_loss=1.0, orchestrator, W=48
- 6h10min wallclock, ~$2.40 vast.ai (5090 + 48-core EPYC, $0.37/hr)
- Train 3 epochs on 188K positions: train_pol_loss 1.5358→1.5015, train_val_loss 0.9552→0.9125. val_pol_loss drifted up slightly (1.5475→1.5661, mild overfit signal) but anchor result is positive so net-positive.

**Anchor result (apples-to-apples both sides v2.7 leaf, sims=200, n=30):**
- iter_00.pt vs warmstart_canonical.pt: **18W/1D/11L = 61.7% wr**
- avg diff +14.3 (iter_00 wins by ~14 pts/game)
- elo_delta +82.6
- Anchor-gate threshold 50% met cleanly.

**Significance:** the policy retrain on v2.7-driven self-play data improved iter_00 by +21pp over the warmstart it started from. This is the first checkpoint generated by the new pipeline (correct leaf, retuned hyperparameters, fixed dedup) — it cleanly beats the v1-v6 best (iter_12 at 70% wr vs warmstart_canonical with NN value, but those numbers are from the old leaf eval; not directly comparable here).

**Lessons:**
1. **Pre-flight smoke must use SAME knobs as production.** I ran sims=50 smoke locally and extrapolated linearly to sims=200 cloud. Real per-leaf v2.5 cost grows nonlinearly with placed meeples (more late-game state = more farm-util work). Cost: 6× wallclock surprise.
2. **Bug fixes can shift hyperparameter optima.** The cap=5 was tuned against the buggy bonus magnitudes. After dedup, the bonus magnitudes dropped, and cap=5 became too tight. A correct fix doesn't preserve bench numbers — re-tune.
3. **Lottery-ticket weights add noise, not signal.** Dropping the 3-open tier (P=0.05) gained 5pp over including it. The intuitive "more terms is more information" was wrong; small-weight terms can hurt by giving the search small uniform pushes that drown out the high-confidence ones.

## 2026-05-14 — Cloud-prep: --leaf-eval v2_5 plumbed through self-play harness; MCTS virtual-loss batching validates 3× batch-fill improvement

**Context:** Before any cloud retrain on v2.5 self-play data, the harness needs three things consistent: (1) self-play uses v2.5 leaf during MCTS so generated games reflect the v2.5 strategy, (2) MCTS virtual-loss batching is enabled so the orchestrator gets full benefit, (3) anchor-gate / h2h evals use the same leaf eval for apples-to-apples comparison.

**Implemented (commit `1d3a0cb`):**
- `evaluators.py`: new `make_v25_value_wrapper` / `make_v25_batch_value_wrapper`. Wrap any (priors, value) evaluator: keep its priors, replace its value with `tanh(virtual_score_v2(state, current_player) / 15)`. Compatible with both local and remote (orchestrator) evaluators since it only consumes the (priors, value) shape.
- `run_selfplay_iter.py`: added `--leaf-eval {nn, v2_5}` flag. Defaults to `nn` for v1-v6 back-compat.
- `eval_iter_head_to_head.py`: same flag, applied to BOTH sides simultaneously so an anchor-gate eval comparing iter_X to warmstart_canonical compares them at the same leaf eval.
- `run_phase4_smoke.py`: propagates `--leaf-eval` to all 3 substages.
- `train_iter.py`: NOT TOUCHED. Training labels (`z`) come from game outcomes, not leaf evals. Independent of this change.

**Smoke-validated:** End-to-end smoke at W=4 sims=50 batch_size=8 vloss=1.0 orchestrator v2_5 (4 self-play games):
- 78s wallclock, 663 positions saved.
- `avg_batch=7.2` — up from 2.4 measured at W=6 without batching earlier today (~3× batch-fill improvement).
- Stage breakdown 74% dequeue / 26% forward — GPU is now waiting for workers, the inversion we wanted. Earlier bottleneck (PCIe-bound serial inference) is fixed by batching.
- h2h smoke at same config: 89% dequeue / 10% forward (two server pools split traffic). At cloud W=48 the orchestrator should approach saturation.

**Caveat to watch on real cloud run:** smoke h2h with same checkpoint both sides (n=4 only) gave 4-0 instead of expected 50/50. Almost certainly MCTS-seed asymmetry × low N noise, but verify with n≥20 on the actual cloud before trusting any v2.5-vs-v1-warmstart anchor-gate signal.

**Decision:** cloud-ready. Recipe for the policy-retrain run = v6 baseline + `--leaf-eval v2_5 --batch-size 8 --virtual-loss 1.0 --orchestrator`. Estimated cost $1 (vs yesterday's $5 estimate; sims=400→200 + batching + orchestrator each cut a chunk).

## 2026-05-14 — orchestrator at W=6 hurts, at W=12 helps — IPC overhead vs batching tradeoff

**Context:** GPU-Z showed 35% GPU / 76% PCIe load during v2.5 bench at W=6 — looked like PCIe-bound. Plumbed `--orchestrator` into `eval_rule_player.py` (mirroring `eval_iter_head_to_head.py`).

**Local A/B at sims=100 n=12:**

| Config | wallclock/game | avg_batch | speedup |
|---|---|---|---|
| W=6 baseline | 19.0s | n/a | 1.00× |
| W=6 + orchestrator | 16.0s+ | 2.4 | -19% (slower) |
| W=12 baseline | 16.8s | n/a | 1.13× |
| W=12 + orchestrator | 14.6s | 4.8 | 1.30× |

**Diagnosis:** PCIe load was high *count* (many small transfers), not high *latency* (per-transfer is fast). The orchestrator can only amortize forward-pass cost when batches fill, but at W=6 workers pipeline serial inference without contending — avg_batch stays at 2.4. IPC overhead per request exceeds the batching gain. At W=12 contention rises, avg_batch hits 4.8, and the orchestrator pays back.

**Decision:** local production = W=12 + `--orchestrator` for ablation benches. Saves ~25% wallclock vs prior W=6 default. Cloud (W=48 with naturally higher contention) still benefits more, as proven in the 2026-05-12 cloud bench.

**Caveat:** numerical agreement <1e-5 vs baseline at sims≥200; at sims=100 small float noise → argmax flips → different MCTS games. Production sims=200 is fine.

**Bigger lever not yet pulled:** MCTS virtual-loss batching (`batch_size > 1` per worker, with virtual_loss=1.0). One worker submits K sims in parallel via virtual losses → orchestrator batch fill multiplies by K. Code already supports it; calls just don't use it. Estimated 2-4× additional speedup at our worker count. Worth wiring before any cloud retrain.

## 2026-05-14 — v2.5 BENCH PASSES at 83.3% vs Tier-1 — +6.6pp over v1; production candidate

**Context:** v2.5 = halved P heuristic ({1: 0.5, 2: 0.2, 3: 0.05}) + bonus cap at ±5 per player. Built per v2-diagnostic finding that tanh-saturation was the v2 failure mode.

**Bench:** hybrid_v2.5 vs Tier-1, sims=400, n=30, 6 workers, ~35 min wallclock. Result:

| | wr | avg score diff |
|---|---|---|
| Tier-1 (rule-player) | 16.7% (5/30) | +30.7 (Tier-1 loses by avg ~31 pts) |
| **hybrid_v2.5** | **83.3% (25/30)** | -30.7 |

Comparison:
- v1 hybrid_warmstart sims=400 n=30: 76.7% (prior production config)
- v2 hybrid_warmstart_v2 sims=400 n=30: 30.0% (47pp regression, halted)
- **v2.5 hybrid_warmstart_v2.5 sims=400 n=30: 83.3% (+6.6pp over v1, +53pp over v2)**

**Decision:** **v2.5 becomes the production leaf eval.** The closure-anticipation + farm-growth design was strategically correct; the issue was tanh saturation, not the underlying signal. Capping the bonus brings the signal into tanh's responsive region while preserving the strategic content.

Production config update:
- `warmstart_canonical.pt` + `_hybrid_v2_evaluator` + sims=400 + ≥4 workers
- v2 module is named `virtual_score_v2.py` but its constants are now v2.5 (`_CLOSURE_P = {1: 0.5, 2: 0.2, 3: 0.05}`, `_BONUS_CAP = 5.0`). Module name kept for git continuity; the file IS v2.5.

**Still NOT superhuman.** 83.3% wr is 6.6pp better than v1 but Joshua still beats Tier-1 2-of-3. Phase 5 still gated. Next levers (in priority order):

1. **Sims sweep for v2.5** — v1's optimum was sims=400; v2.5's optimum may differ. If sims=200 matches sims=400, production throughput doubles.
2. **Cap tuning** — cap=5 was a hand-picked initial value. Sweep cap ∈ {2, 5, 8, 15} to find the knee.
3. **Retrain policy head on hybrid_v2.5 game data** — the NN policy was trained on virtual_score_v1 self-play. Generating ~10K games with hybrid_v2.5 self-play and retraining the policy head should compound — better leaf → better self-play targets → better policy → better leaf-weighted search.

**Lesson recorded:** When stacking signals into a tanh-squashed leaf eval, **scale matters more than sign-correctness**. v2 had the right design but wrong magnitudes; v2.5 fixed magnitudes alone and unlocked a +6.6pp gain over the v1 baseline. This is the first 50pp+ improvement from a single ablation knob in the project's history.

## 2026-05-14 — v2-diagnostic: bonus scale is 4-7× larger than v1 base — tanh saturates, search loses gradient

**Context:** v2 lost the bench by 47pp. Before tuning P heuristics blindly, built `scripts/diagnose_v2.py` to dump per-move bonus contributions and aggregate signals. One game, sims=100.

**Findings (seed 0, 165 moves):**
- **Cathedral branch never fires.** Good — that hypothesis was wrong; not a bug.
- **|net_bonus| > |base| in 92% of moves.** v2's added bonus dominates v1's base on nearly every move.
- **`bonus_self + bonus_opp` > |base| in 95% of moves.** Same conclusion.
- **Max `bonus_self` = 133 in one game.** v1 base typically sits at ±15-30. Bonus is 4-7× the base.
- **Bonus is wildly asymmetric.** Self farmer contributions: ~9466 cumulative; opp farmer: ~357. Self has many farmers; Tier-1 plays few; v2 gives hybrid a phantom advantage.
- **Terrain-by-terrain attribution (self):** None (farmer) 9466 / city 545 / chapel 109. Farm-growth bonus is the dominant signal by ~20×.

**Root cause:**

The leaf eval is `tanh((base + bonus_self - bonus_opp) / 15)`. With base=+10 and net bonus = +80, `tanh(90/15) = tanh(6) ≈ 1.0`. Most leaves saturate at ±1 because the bonus magnitude exceeds 15. Once tanh saturates, MCTS can no longer distinguish good leaf states from bad ones — the leaf value collapses to a constant, the search loses its gradient, and it picks worse moves than v1 (whose base eval still varied across leaves).

The farm-growth bonus is the dominant offender. Each farmer with K incomplete-but-likely-to-close adjacent cities adds `3K × P` to the bonus. A connected farm can touch 5-15 cities; with P=0.5 for 2-open cities, a single farmer easily contributes +10-15 to the bonus. Multiple farmers + multiple closable cities = bonus magnitudes of 50-130.

**Decision: v2.5 = scale + cap.**

Two complementary fixes (build both, bench together; smallest change that addresses the saturation):

1. **Halve the closure-P heuristic:** `{1: 0.5, 2: 0.2, 3: 0.05}` (was `{1: 1.0, 2: 0.5, 3: 0.25}`). Brings the bonus magnitude into the same scale as the base.
2. **Cap the bonus term at ±5 per player.** Hard ceiling so even if many features chain into a closure-wave, the leaf-eval scale doesn't blow past tanh's linear region. This is a stability measure, not a strategic one.

Acceptance: hybrid_v2.5 sims=400 n=30 vs Tier-1: hybrid wr ≥ 76% (match v1 baseline). Stretch: ≥ 80% (the bonus adds real signal at the right scale).

**If v2.5 fails:** the structural design is wrong, not the magnitude. Pivot to v3 (drop closure-anticipation, try denial-value of opponent's near-closures or meeple-economy state).

**Lesson:** when stacking signals into a leaf eval that's then squashed by tanh, scale matters more than sign-correctness. A *correct* signal of the wrong magnitude is worse than no signal at all because it saturates the squash and kills the gradient.

## 2026-05-14 — virtual_score_v2 FAILS the bench: ~47pp regression vs v1 (30% vs 76.7% wr at sims=400)

**Context:** Built v2 per the prior decision (closure-anticipation bonus + farm-growth potential). Implementation, tests (11/11 pass), wiring through `eval_rule_player.py` as `--opponent hybrid_v2`. Bench: n=30 sims=400 vs Tier-1, 6 workers, ~37 min wallclock.

**Result:** Tier-1 21W / 0D / 9L vs hybrid_v2. **hybrid_v2 wr = 30.0%** vs hybrid_v1 wr = 76.7% at the same sims/n. Avg score diff = -10.6 (v2 loses by ~11pts on average). **~47pp regression.**

**Diagnosis (hypotheses, not yet verified):**
1. **Closure-P heuristic too aggressive.** `P=0.5 at 2 open positions` is probably wrong — most 2-open city positions never close because tile supply runs out or the tiles needed don't exist in the remaining deck.
2. **Farm-growth bonus double-counts denial.** If a farm meeple gets +3 × P for each incomplete adjacent city, AND the same city's closure also fires the city closure bonus on the opponent's side, we may be over-rewarding both players' bonuses asymmetrically.
3. **Cathedral-flag detection is broken.** v2 treats `tile.inn` as the cathedral flag on city tiles, but `inn` is the actual road-inn flag. Cities don't have `tile.cathedral`. This means `_city_closure_delta` adds `6 if tile.shield else 3` for any tile that has an inn-adjacent road. **Likely bug** — needs verification. The base-game + River + Farmers scope shouldn't even have cathedrals, so this branch should never fire; if it does, it's wrong.
4. **Bonus dominates the base.** Median per-game `bonus_self` + `bonus_opp` might be larger than `base`, flipping the leaf-value sign mid-game.

**Decision:** **Halt v2 deployment.** Commit the infrastructure (the diagnostic tools and v2 module remain useful for v2.5 iteration), but do NOT use v2 in production. Production stays at `hybrid_warmstart_canonical` with v1 `virtual_score` + sims=400.

**Next step:** rather than tune the P heuristic blindly (which would burn many bench cycles), build a v2-diagnostic — replay one game with v2 logging EVERY meeple-bonus contribution at every move. Catalog which bonus type fires most, whether the totals are sane, and whether the cathedral branch is firing incorrectly. THEN decide between (a) v2.5 (fix bugs + retune P), (b) v3 (drop closure-anticipation, try denial-value or meeple-economy), or (c) accept v1 + pivot to retraining the policy head on hybrid-generated data.

**Lesson recorded:** Adding *more* signal to a leaf evaluator can hurt search if the signal has the wrong sign or scale at any depth. v2's bonuses were summed onto v1's base then fed through `tanh(diff/15)` — if the bonuses are systematically larger than the base, they overwhelm v1's real signal. Counterintuitive but matches the observed regression magnitude.

## 2026-05-14 — Virtual_score diagnostic: closure-blindness + farm-composition opacity are the dominant failure modes

**Context:** With production hybrid_warmstart still losing 23% to Tier-1 (n=30 sims=400), the next ablation question per [EXPERIMENTS.md](EXPERIMENTS.md) was: what specifically does `virtual_score` miss? Built `scripts/diagnose_virtual_score.py` — replays full hybrid-vs-Tier-1 games at sims=400 and prints per-move tables showing `vs_hybrid` (virtual_score from hybrid's perspective) at every step.

**Method:** n=10 games, 6 workers, ~10 min wallclock. Got 7W/3L (matches n=30 70-77% rate). Inspected all 3 lost games' per-move trajectories.

**Failure modes (ranked by frequency / severity):**

1. **Closure-event blindness (3/3 games).** Partial credit (`virtual_score` = 1pt/tile for incomplete city, 0 for farm with incomplete city) ≠ closure credit (2pt/tile + 3pt/city for farm). When opponent closes a near-complete feature, `vs_hybrid` swings by 5-30pts in *one move* with no advance warning. seed=1 example: tier1 placed TILE(6,16) at move 151, closed a ~13-tile city, `vs_hybrid` went -7 → -36 instantly. Hybrid had no signal that this closure was imminent and could have placed a denial tile.

2. **Farm composition opacity (2/3 games).** `count_farm_points` only counts cities with `city.finished == True`. As cities complete through the game, farm scores change in ways `virtual_score` doesn't anticipate. seed=0 example: at move 158, `vs_hybrid` = +24 (hybrid looking good). By move 163, it crashed to -6 — a 30pt swing where the actual on-board score change was only +11 for opponent. The extra ~20pts came from farm composition flipping.

3. **Denial-value invisible (≥1/3 games obvious).** Hybrid never plays defensive tiles to block opponent's near-complete features because `virtual_score` only sees current state, not opponent's expected future closure value.

4. **Over-committed meeples (1/3 games).** seed=8 showed hybrid playing FARMER moves while behind 18-50 — no meeple opportunity-cost modeling.

5. **Late-game volatility (3/3 games).** Single tile placements in endgame swing `vs_hybrid` by 30+ pts. Predictions aren't robust enough to drive late-game decisions.

**Decision: build virtual_score_v2** with the top two failure modes addressed:

- **Closure-proximity bonus**: for each incomplete feature with a meeple, add `(full_credit - partial_credit) × P(closes by game-end)`. Initial heuristic for P: based on open-positions-needed, e.g. 1.0 if 1 needed, 0.5 if 2, 0.25 if 3, else 0.
- **Farm-growth potential**: for each farm meeple, for each adjacent INCOMPLETE city, add `3 × P(completes)`. Same closure-probability heuristic.

Both extensions reuse the existing engine utilities (`CityUtil.find_city`, etc.). No engine changes needed. Estimated ~1 day implementation + tests + bench.

Acceptance: hybrid_warmstart sims=400 with v2 leaf beats hybrid v1 leaf by ≥10pp winrate at n=30 (i.e., ~13% vs Tier-1 → confirms 1 sigma improvement). If v2 doesn't improve, the failure mode is something else (probably denial-value) and we redesign.

The remaining 3 failure modes (denial, meeple economy, late-game volatility) are deferred — addressed in v3+ if v2 alone doesn't reach superhuman.

## 2026-05-14 — Sims sweep + uniform-priors ablation: policy head worth ~18pp; sims=400 is the ceiling; production config locked.

**Context:** After the value-head finding (next section below), two follow-up questions: (1) is sims=100 the sweet spot or are we missing a peak elsewhere? (2) does the NN policy head actually contribute, or could uniform priors + virtual_score leaf match it?

**Sims sweep** (hybrid_warmstart_canonical vs Tier-1, n=30 each, 4-6 workers):

| sims | Tier-1 winrate | hybrid winrate | avg diff | wallclock/game |
|---|---|---|---|---|
| 50 | 36.7% | 63.3% | -10.3 | 8.8s |
| 100 | 41.7% | 58.3% | -2.0 | 16.9s |
| 150 | 41.7% | 58.3% | +5.7 | 25.0s |
| 200 | 30.0% | 70.0% | -7.6 | 34.5s |
| 400 | 23.3% | 76.7% | -15.5 | 34.5s (4w) / 68.0s (4w) — see note |
| 800 | 23.3% | 76.7% | -12.6 | 97.3s (6w) |

**Uniform-priors ablation** (no NN — uniform priors + virtual_score leaf, sims=100 n=30 vs Tier-1): Tier-1 60% wr / +8.7 avg diff. Compare hybrid_warmstart sims=100 at Tier-1 41.7%. **The NN policy head is worth ~18pp winrate.**

**Findings:**
1. **Sims=400 is the scaling ceiling for hybrid_warmstart.** Doubling to sims=800 produced zero winrate improvement. The earlier "U-shape" hypothesis at sims=100-150 is probably just noise (SE ~9pp at n=30); the true curve is monotonically improving with diminishing returns, plateauing by sims=400.
2. **The NN policy head matters meaningfully.** Uniform priors + virtual_score leaf loses to Tier-1 60-40; with NN priors it wins 58-42. We cannot drop the network.
3. **Production config:** `warmstart_canonical.pt` + `_hybrid_evaluator` + sims=400 + ≥4 workers. Beats Tier-1 76.7% of games by avg 15 points.

**Still not superhuman.** Joshua beats Tier-1 2-of-3 in casual play; beating Tier-1 ~77% is not sufficient. The next ablation is diagnosing virtual_score's blind spots from games where hybrid lost — this informs whether a richer leaf eval (virtual_score_v2 with farm-growth, denial, meeple-economy components) is the path past 77%.

**Caveats:**
- n=30 per point gives SE ~9pp; the sims=100 vs sims=400 gap (~18pp) is ~2σ — real but not bulletproof.
- Earlier n=20 sims=100 result (Tier-1 20%) was a lucky sample; n=30 corrects to ~42%.
- We have NOT tested if the 18pp policy-head advantage holds at higher sims (i.e., possible policy × sims interaction). Open question.
- Bench setup uses per-worker NN forward passes; PCIe is saturated at 4-6 workers. Wiring through the orchestrator would 2-3× throughput on the same box.

## 2026-05-14 — The NN value head was the bug. NN policy priors + `virtual_score` leaf flipped Tier-1 75%→40%.

**Context:** Day 2 after Tier-1 confirmed our trained nets all lose to a 1-ply heuristic. Day 1 result: Tier-1 beat warmstart_canonical 77% and iter_12 75% (both n=50 sims=100). Question: is the NN's policy or value head the broken component?

**Diagnostic:** built `_hybrid_evaluator` in `scripts/eval_rule_player.py` — identical to `_network_evaluator` except the value output is replaced with `tanh(virtual_score(state) / 15)`. Plugged into existing `NeuralMCTS` via its evaluator slot. ~20 LoC change. n=20 bench vs Tier-1.

**Result:**
| Setup | Tier-1 winrate | Avg score diff |
|---|---|---|
| iter_12 NN-only sims=100 (yesterday's bench, n=50) | 75% | (Tier-1 dominant) |
| HeuristicMCTS (no NN, UCT+virtual_score) sims=200 (n=20) | 60% | -1.1 |
| **Hybrid iter_12 (NN priors + virtual_score leaf) sims=100 (n=20)** | **40%** | **-6.8 (hybrid wins by ~7 pts/game)** |

**Conclusion:** 35-percentage-point swing from one knob. Same network, same MCTS, same sims — only swapped the value output. The NN's value head was actively harmful to the search. The policy head is decent (hybrid 60% > pure-heuristic 40% at half the sims). The value head's failure is doubly damning because it IS trained on `tanh(virtual_score/15)` targets — i.e. it's an *approximation* of what we now just compute exactly, and it's WORSE than the exact answer.

**Hypothesized causes** (not yet diagnosed): (a) MCTS-induced distribution shift — training labels from completed-game states, search evaluates partial-game leaves outside that distribution; (b) capacity starved by the policy head's `Linear(2500, 2511)` ~6M params dominating the trunk; (c) subtle perspective/sign bug.

**Decision:** production NeuralMCTS will run with `_hybrid_evaluator` (NN priors + virtual_score leaf). Architectural follow-up: deprecate the value head entirely — it's harmful AND it's a slow forward pass we don't need.

---

### Lesson learned (the meta-decision)

Yes, we should have caught this much earlier. The diagnostic is ~30 LoC + ~10 min bench. The right protocol after Phase 3 (warmstart finished) would have been a 3-bench ablation battery:
1. NN policy + NN value (baseline NeuralMCTS)
2. NN policy + virtual_score value (this finding)
3. uniform policy + NN value (test if priors matter at all)

Run those three after warmstart finished, you immediately see "value head adds nothing or hurts." Total cost: ~30 min compute.

Instead we did try-another-recipe for six variants (v1-v6) over multiple weeks. When v3 plateaued, the right move was diagnose-by-ablation; we kept iterating recipes instead. That's the systemic mistake.

**Fair caveat:** swapping an exact heuristic for the NN value head is *off-path* in AlphaZero literature. The whole AlphaZero premise is that the NN value generalizes better than any hand-designed eval — true in Go/chess because there's no cheap-exact partial-game scorer. Carcassonne is unusual: the engine's `count_final_scores` IS a cheap-exact partial-game scorer. We had something most AlphaZero domains don't, and we used it only as a training target instead of recognizing it could also be the search-time evaluator.

**Generalized rule for next time:** when self-play plateaus, the next experiment is component ablation, not another recipe variant. "Try harder with the same architecture" is the trap.

## 2026-05-13 — Tier-1 baseline destroys both warmstart_canonical AND iter_12 → recipe-ceiling story confirmed

**Context:** Day 1 of the v7 prep plan. Before committing to v7 (symmetry augmentation + warmstart-from-iter_12), test whether the v6 recipe family even matched the heuristic labeler that generated warmstart's training data. Tier-1 = a hand-coded fixed-policy player whose tile-phase rule is "argmax 1-ply virtual_score" (the same scoring function used to label warmstart training data, just at τ→0 instead of τ=0.5 softmax).

**Setup:** `scripts/eval_rule_player.py` extended with `--opponent checkpoint`. NeuralMCTS at sims=100, default c_puct=1.5, GPU-spawn pool with 2 workers. Both N=50, alternating sides each game.

**Results:**

| Tier-1 vs ... | Win rate | Avg score diff (Tier-1 − opp) | ELO Δ |
|---|---|---|---|
| random (sanity, N=20) | 100% | +70.3 | (saturated) |
| **warmstart_canonical (NeuralMCTS s=100), N=50** | **77.0%** (38W/1D/11L) | **+33.9** | +210 |
| **iter_12 (NeuralMCTS s=100), N=50** | **75.0%** (37W/1D/12L) | **+19.9** | +191 |

**Interpretation:**
1. The heuristic oracle (1-ply virtual_score argmax, no search) **dominates** both trained networks at the v6 production sim budget. The supposed "global best" (iter_12, the v6 peak we measured at 70% wr vs warmstart_canonical) loses to the *labeler* 75% of the time.
2. iter_12 is barely stronger than warmstart_canonical against Tier-1 (75% loss vs 77% loss = 2pp on win rate; +19.9 vs +33.9 on margin = 14 points narrower). The 70% wr vs warmstart_canonical that we'd treated as v6's headline result reflected modest progress over an already-weak baseline, not progress over the labeler.
3. The anchor reference (`warmstart_canonical.pt`) was the wrong yardstick all along. We've been measuring NN-vs-NN (two approximations of the same oracle) instead of NN-vs-oracle. v1-v6 were all comparing two flavors of "weaker than the labeler".
4. The mechanism is plausible: NeuralMCTS at sims=100 uses the trained value head (a noisy approximation of `virtual_score`) + shallow tree search; Tier-1 uses the *exact* `virtual_score` at depth 1. Approximation noise + 100-sim search vs exact-oracle-no-search → the oracle wins. Higher sims would close the gap (NeuralMCTS at sims=10000+ would presumably surface the gap), but that's not the production regime.

**Implication for v7 (symmetry augmentation):**
- Symmetry aug provides 4× more training data on the same heuristic-labeled distribution. Adding more data of the same flavor cannot help if the model isn't even matching the labeler at deployment-time sim budgets.
- The recipe-ceiling story is now confirmed empirically, not just suspected. The ceiling is structural (recipe shape), not data-volume.
- Predicted v7 outcome with high confidence: would converge to ~iter_12-equivalent (≤25% wr vs Tier-1, plateau at ~70-75% vs warmstart_canonical anchor). Wouldn't break the ceiling.

**Decision:** Cancel v7 as originally specified (symmetry augmentation alone). Choose Day 2 from the four below.

**Options for Day 2 / next direction:**
- **A. Pivot to Phase 5 using Tier-1 as the policy oracle.** The project's actual win condition (analyzer/coaching tool, per `docs/ORIGINAL_PROMPT.md`) doesn't require a stronger AI than Tier-1 — it needs a tool that explains where the human lost points. Tier-1 already plays at a level the family game can build on; ship it as the policy and use a small NN for value smoothing if needed. Lowest cost, highest project-goal-alignment.
- **B. Specialist league (DOMAIN-SPECIFIC track).** Bias the heuristic labeler 3 ways (roads/cities/farms), train 3 specialists, league play in self-play. Forces the network past the heuristic via diverse opposition. Tagged "high priority if v6 plateaus" in BACKLOG.md — v6 plateaued, so this is now the high-leverage AlphaZero bet. ~$5-10 cloud, 1-2 weeks.
- **C. Heuristic-as-teacher self-play.** Replace NN-vs-NN self-play with NN-vs-Tier1 self-play. Forces the network to first MATCH the heuristic before exceeding it. Smaller architectural change than league. Risk: may just fit Tier-1 exactly without going past.
- **D. Drop self-play, train directly to imitate Tier-1 at higher capacity.** Generate 500K (state, Tier-1's chosen action) tuples; train a deeper net to argmax-imitate. Simple supervised learning. Tells us if model capacity (not recipe) is the bottleneck.

**Recommendation:** A (Phase 5 pivot). Reasons:
- The project's win condition is the analyzer, not the bot. Spending another week+$5-10 chasing a stronger network for a coaching tool that doesn't need one is misaligned.
- Tier-1 is "good enough" for the analyzer use case — it makes principled moves explainable in terms of virtual_score deltas.
- B/C/D are interesting research questions but each adds 1-2 weeks before the project ships its actual user-facing win condition.

**Reversal cost:** low for A (Tier-1 + virtual_score are already in `src/`); medium for B/C/D (each adds 1-2 weeks of fresh work).

**Phase:** 4 closure → 5 entry.

**Artifacts:** `tests/test_rule_based_player.py` (new); `src/carcassonne_ai/rule_based_player.py` (Rules 4+5 added); `scripts/eval_rule_player.py` (--opponent checkpoint added). Logs at `/tmp/tier1_random.log`, `/tmp/tier1_vs_warmstart.log`, `/tmp/tier1_vs_iter12.log`.

## 2026-05-13 — Phase B cloud bench: W-sweep finds W=32 optimum, full iter measured at 5.2 min, h2h OOM hypothesis falsified

**Context:** Phase A (entry below) confirmed 5-loop patches give ~4-5× CPU-side speedup but exposed two gaps: W=48 still OOMs (VRAM-bound, not CPU-bound, so the patches don't help here), and orchestrator-at-N=1 dispatcher saturates with 48 workers. Phase B bundles four experiments on one box to retire all v7 design questions: W-sweep, orchestrator-with-bigger-batch-timeout, full-iter timing, and train cProfile.

**Box:** vast.ai instance 36719047, RTX 5090 + AMD EPYC 9J14 host 384353 mach 79960 Japan ($0.3747/hr). Hardware confirmed via `lscpu`: **192 physical cores / 384 logical via SMT**, cgroup-capped to 48 effective for this rental. torch 2.7.0+cu128, sm_120. Total Phase B spend ~$0.30.

**Phase 1 — W-sweep (no orchestrator), games=64 sims=200 batch=8:**

| W | Wallclock | Success/Failed | Peak VRAM | Mean GPU util |
|---|---|---|---|---|
| **32** | **172.8 s** | **64/0** | 22325 MiB / 32 GB | **87.2%** |
| 40 | 176.4 s | 64/0 | 27906 MiB | 86.8% |
| 44 | 180.3 s | 64/0 | 30695 MiB | 85.9% |

W=32 wins. Higher W doesn't help because **GPU is already saturated at W=32 (87% util)** — extra workers add CPU contention without throughput gain. W=44 sits ~95% of VRAM cap (no headroom) for ~4% throughput penalty.

**Phase 2 — Orchestrator v2 (W=48, `batch_timeout_ms=16` vs default 2):**
Dispatcher still saturated. Killed after 3 min with 0/64 games written, GPU at 5% util. **Bumping batch_timeout_ms doesn't help** — the bottleneck is single-process dispatch CPU work, not batch-assembly latency. To use orchestrator at W=48 we'd need either N>1 shards or a different IPC mechanism (pinned-memory / shared tensors); deferred.

**Phase 3 — Full iter at winner W=32:**
1 iter via `run_phase4_smoke.py` (selfplay + train + anchor; chain h2h auto-skipped because iter 0 has no prior).

| Stage | Wallclock | Notes |
|---|---|---|
| Self-play (64 games, sims=200, W=32) | 187.1 s | 64/0, 10599 positions, ~0% slower than Phase 1 standalone |
| Train (3 epochs, 95K warmstart positions) | ~100 s | Iter 0 has the biggest train cost; later iters ~10-15 s |
| Anchor (16 games, sims=50) | 19.7 s | 8W/0D/8L vs warmstart_canonical (sanity: 50/50 — correct since iter_00 is warmstart_canonical at iter 0) |
| **Per-iter total** | **5.2 min** | vs my earlier "~10 min" estimate |

**Phase 3 supplement — h2h-only test at W=32 (closes the OOM-stress gap):**
Ran `eval_iter_head_to_head.py` with iter_00.pt (the just-trained checkpoint) vs warmstart_canonical at W=32, 32 games, sims=100. **No OOM.** Wallclock 55.2 s. Result: 20W/1D/11L = 63% wr, +12.4 avg diff, ELO Δ +100. **h2h at W=32 works** — the per-worker VRAM for 2-net eval is much smaller than my naive 2×600 MB worst-case math (the eval_iter script must share net allocator pools more efficiently). **No split-W config needed for v7.**

**Phase 4 — Train cProfile (with corrected CLI flags):**
Train iter 1 at warmstart_mix=0.5, 10.5K positions × 1 epoch = 7.8 s wallclock. Cumtime split:

| Phase | cumtime | % |
|---|---|---|
| Process startup (imports, optimizer init) | 2.55 s | 33% |
| DataLoader queue wait (single-worker `__next__`) | 2.34 s | 30% |
| Actual forward + backward + optimizer | ~3 s | 37% |

DataLoader queue-wait is the biggest single non-trivial slice and would shrink ~3× with `--num-workers 4`. But train at iter ≥ 1 is already only ~10-15 s; not the next bottleneck.

**v7 cloud-iter math (revised from Phase A's estimate):**
- Self-play (W=32, games=64, sims=200): ~3 min
- Train (~10K positions × 3 epochs): ~15 s
- Chain h2h (32 games, sims=100, W=32): ~1 min
- Anchor gate (16 games, sims=50, W=32): ~20 s
- **Per-iter total: ~4.5-5 min** (vs Phase A's ~10 min estimate)
- 20-iter v7 run: **~1.5-1.7h, ~$0.65 on this hardware class.**

**Phase B findings, summary:**
1. W=32 is the v7 selfplay+h2h winner. No split config needed.
2. Orchestrator with batch_timeout knob alone can't fix the N=1 dispatcher saturation. Multi-shard N≥2 might (re-test on this hardware once a real motivating workload exists; currently no need).
3. Per-iter cost is ~4.5-5 min — half of what I'd estimated post-Phase-A.
4. **Total budget for v7 = ~$0.65 (down from $3.40 v6 baseline).** 5× cheaper per iter.
5. Train DataLoader could be faster via `num_workers > 0`, but train is already << selfplay+h2h, so not worth the optimization right now.

**Reversal cost:** none. Box destroyed. v7 plan-mode session can lock W=32 + games=64 + no-orch as the cloud-side defaults.

**Phase:** 4 (perf validation)

---

## 2026-05-13 — Phase A cloud bench: 5-loop MCTS perf patches validated on production hardware

**Context:** local A/B at sims=200 batch=8 on 5060 Ti showed ~7.6× cumulative game-wallclock speedup vs the pre-patch baseline. The cloud question: does that translate to a real per-iter throughput win on production hardware (5090 + 48-core EPYC), and does orchestrator-on still pull weight when deepcopy is no longer the bottleneck?

**Box:** vast.ai instance 36717091, RTX 5090 + 96-effective-core box (mach_id 19968, Michigan, host 65203, $0.3481/hr). Different physical machine than v6's host 384353 because Phase A's first attempt on that host (instance 36715218) failed SSH-banner exchange after ~30 min wait — the "SSH-ready ≠ usable" failure mode from CLAUDE.md. Sunk ~$0.19. Total Phase A spend ~$0.40.

**Bench script:** `scripts/cloud_phase_a_bench.sh` runs iter-0 self-play twice back-to-back on the same box (eliminates host variance):
- A1: `--workers 48 --sims 200 --batch-size 8 --games 80` (no orchestrator)
- A2: same + `--orchestrator --orch-shards 1`

Captures wallclock, nvidia-smi GPU util samples (every 2s).

**Results (the interesting story):**

| Config | Wallclock | Games OK | Games OOM-failed | Mean GPU util | Peak VRAM |
|---|---|---|---|---|---|
| A1 (no orchestrator) | 2:41 | **37/80** | **43/80** | 64.7% | **32108 MiB / 32 GB** |
| A2 (orchestrator) | killed after 5:30 (workers stuck blocking on single dispatcher) | 0/80 | 0/80 | 5.6% | 2896 MiB |

**A1 hit the W=48 OOM** — same shape as the 2026-05-12 Phase A bench. Each surviving worker holds a ~600-700 MB allocator pool × 48 ≈ 30+ GB, right at the 32 GB cap. The 5-loop MCTS perf patches do NOT change per-worker VRAM (deepcopy fix saves CPU time, not memory) — VRAM behavior is unchanged from pre-patch. The 37 surviving games finished fast (effectively 4.3 s/successful-game), but 43 failures means the iter would have to be re-run to fill the buffer.

**A2 hit orchestrator dispatcher serialization** — with 48 workers all routing through 1 dispatcher process, the dispatcher saturates (~49% CPU, queue contention) and worker throughput collapses. Killed after 5:30 with 0 games written. This matches the 2026-05-13 N-sweep finding (N=1 optimal among N>=1, but still strictly slower than no-orchestrator) — except now there's no fallback because A1 OOMs.

**The real takeaway:** the 5-loop patches deliver the predicted ~4-5× CPU-side speedup (A1's 37 successful games went very fast), but production at W=48 needs either:
1. **Lower W** (e.g. W=32 or W=24): fits VRAM, no orchestrator needed. Probably the right v7 choice.
2. **Multi-shard orchestrator** (N=2 or N=4): spreads dispatch load. The 2026-05-13 N-sweep on 48-core box said N=1 is optimal, but that test was W=80 on 48 cores; on this 96-core box at W=48 the calculus might differ. Worth a sub-bench.
3. **Bigger GPU** (80 GB H100/A100): ~$1.50-2/hr. Solves OOM without ergonomic compromises but doubles cost.

**v7 implication:** the cloud-iter math from the loop-5 doc commit assumed clean W=48 throughput. With A1's 43/80 OOM, that's wrong. Realistic v7 path:
- Pick W=32 + games=64 (or W=24 + games=48): fits VRAM, all games succeed, similar effective throughput
- Per-iter wallclock: probably still ~10 min (matches the 2.6× estimate)
- 20-iter v7: still ~3-3.5h / ~$1.30 — but only if we make this knob choice

**Reversal cost:** none. Validates the patches without committing to v7 launch. Documents the W=48 OOM as still-present (and the orchestrator-N=1 ceiling) so the v7 plan-mode session has correct constraints.

**Phase:** 4 (perf)

---

## 2026-05-13 — MCTS perf loop 2/3/4: tile `_type_cache`, rotation-signature cache, str_repr cache, `placed_coords` set

**Context:** After the `__deepcopy__` patch (entry below) cut game wallclock 3.3×, re-profiled and chased the next bottlenecks. Three more patches landed in sequence; numbers from `scripts/profile_mcts.py --no-profile --sims 50 --batch-size 8 --seed 42` on local 5060 Ti:

| Loop | Patch | s/game | Cumulative |
|---|---|---|---|
| 0 | baseline (default deepcopy) | 84.7 | 1.00× |
| 1 | engine state `__deepcopy__` | 25.5 | 3.32× |
| 2 | tile `_type_cache` (precompute `(side → TerrainType)` dict per Tile, lazily) | 16.9 | 5.01× |
| 3 | `_rot_sig_cache` on Tile + `_str_repr_cache` on Board (auto-invalidated by Board replacement on `get_next_state`; manual reset on `apply_action_inplace`) | 14.3–17.1 | ~5.4× |
| 4 | `placed_coords: set[Coordinate]` on engine state, replaces 1225-cell board walk in `string_representation` with ~80-coord iteration | 14.5 | **5.84×** |
| 5 | `tile.turn(N)` cache per Tile (production-sims profile showed 1.08M calls/game, ~22s cumtime). Compounds — cached rotated Tile retains its own `_type_cache` + `_rot_sig_cache`. | _(sims=200: 80→44.5, 1.79× incremental)_ | **~7.6× at sims=200** |

**Loop 2 (tile `_type_cache`):** original `Tile.get_type(side)` re-derives `get_road_ends() / get_river_ends() / get_city_sides()` from scratch on every call (~5M calls/game from `TilePositionFinder` + farmer-position lookups). Patched to precompute a `dict[Side, TerrainType]` once per Tile (lazily). Verified by 1584 (tile × rotation × side) checks against the original implementation — zero mismatches.

**Loop 3 (signature + str_repr caches):** Tiles are immutable canonical refs (`base_tiles` dict + `Tile.turn()` returns a fresh Tile per rotation), so `_tile_rotation_signature` can be cached on each Tile. Board is created fresh by every `Game.get_next_state`, so `_str_repr_cache` is auto-invalidated by replacement — *except* `apply_action_inplace` mutates in place without creating a new Board, so the cache must be explicitly reset there. Regression test in `tests/test_state_deepcopy.py::test_string_repr_cache_invalidated_on_apply_action_inplace`. Smaller than predicted — most Boards are queried once, so cache hits are rare; the actual win was the rotation-signature cache.

**Loop 4 (`placed_coords` set):** the remaining cost in `string_representation` after loop 3 was a 35×35 = 1225-cell walk to find ~80 placed tiles. Mirroring the existing `open_positions` patch: added `state.placed_coords: set[Coordinate]`, maintained by `StateUpdater.play_tile` (pure add — tiles never get unplaced). `string_representation` iterates this set (sorted for determinism) instead of the full board. Wrapped in the custom `__deepcopy__` and tested in `tests/test_engine_adjacency.py::test_placed_coords_*`.

**Loop 5 (`tile.turn(N)` cache):** the production-scale (sims=200) profile showed `tile.turn` called 1.08M times/game (~22s of 126.5s cProfile cumtime), each call rebuilding a fresh rotated `Tile` from scratch. The result is a pure function of `(self, times)` and Tiles are immutable, so cache per-base-Tile keyed by `times`. Bigger payoff than predicted (1.79× incremental at sims=200) because the cached rotated Tile carries forward the loop-2 `_type_cache` and loop-3 `_rot_sig_cache` it builds during use — every downstream get_type and rotation_signature on a rotated Tile is also pre-warmed.

**Diminishing returns + final cumulative.** At sims=50 the loop-4 cumulative was 5.84×. At sims=200 the loop-5 cumulative is ~7.6× (production scale matters more — local pre-patch 80s/game → 44.5s/game post-loop-5; vs an extrapolated pre-patch baseline of ~339s/game). Remaining residual at sims=200 is dominated by per-call GPU IPC (`.to()` + `.cpu()` + tensor construction), which only architectural changes (orchestrator + bigger batches across more concurrent workers, persistent CUDA streams) can crack.

**Implications for v7 (revised after loop 5):**
- Self-play phase only: ~7.6× faster at production sims=200. v6's self-play was ~13 min/iter of the ~26 min/iter total; post-patch ~1.7 min/iter.
- Per-iter total (including unchanged train + h2h + anchor): ~26 min → ~10 min, i.e. **~2.6× per-iter**. 20-iter run: ~9h → ~3.4h / ~$1.30.
- Cheaper headline; train is now the next bottleneck per-iter at ~5 min, and we haven't touched it.
- Higher sims (eval at sims=400+) become affordable. Persistent CUDA streams + bigger eval batches via orchestrator-on-selfplay are the next architectural lever; not pursued in this loop.

**Reversal cost:** none. All patches are local; tests gate any regression.

**Phase:** 4 (perf)

---

## 2026-05-13 — MCTS perf loop 1: engine state `__deepcopy__` cut game wallclock 3.3×

**Context:** Orchestrator N-sweep (entry below) proved workers, not the dispatcher, are the bottleneck. Local cProfile of one self-play game (sims=50, batch_size=8, warmstart_canonical, seed=42) showed the actual hot path **inside** the worker. Top 7 by cumtime:

| Function | cumtime | % of wallclock |
|---|---|---|
| `copy.deepcopy` | 199.9s | **75%** |
| `state_updater.apply_action` | 204.2s | 77% |
| `get_next_state` | 205.8s | 77% |
| `_select_leaf_with_vloss` | 212.2s | 79% |
| `batch_evaluator` (GPU fwd) | 43.9s | 16% |
| `get_valid_moves` | 32.0s | 12% |
| `string_representation` | 21.2s | 8% |

(`_select_child_puct`, the PUCT loop I expected to be hot, didn't appear in the top 40 — it's negligible vs deepcopy.) Per-tree-step `get_next_state` deepcopies the entire `CarcassonneGameState`, which by default recursively walks every `Tile` (with `FarmerConnection`s), every `MeeplePosition`, every `Coordinate` in the 35×35 board. ~19,500 deepcopies per game × ~2.2ms each = 200s — way more than the GPU.

**Fix:** custom `__deepcopy__` on `CarcassonneGameState` (vendored engine; ~50 LoC). All immutable refs (`Tile`, `TileAction`, `MeeplePosition`, `Coordinate`, enums) are shared; mutable containers (`board`, `deck`, `scores`, `meeples`, `placed_meeples`, `open_positions`) are shallow-copied at one level. Verified by reading every mutation site in `state_updater.py` and `points_collector.py`: nothing ever mutates Tile/TileAction/MeeplePosition fields after construction — `Tile.turn()` returns a NEW Tile (immutable pattern).

**Microbench** (mid-game state, 80 placed tiles, N=200 copies):

| | per-copy |
|---|---|
| default recursive deepcopy | 2.216 ms |
| custom `__deepcopy__` | 0.004 ms |
| **per-copy speedup** | **503×** |

**End-to-end A/B** (one game, sims=50 batch=8, --no-profile):

| | plies | wallclock | s/ply |
|---|---|---|---|
| default deepcopy | 166 | 84.7 s | 0.510 |
| custom `__deepcopy__` | 165 | **25.5 s** | **0.154** |
| **game speedup** | — | **3.3×** | 3.3× |

**Correctness:** `tests/test_state_deepcopy.py` (4 tests, all pass) verifies: (a) signature equality of fresh state, (b) signature equality after 60 random actions applied to a custom-copy vs a default-copy, (c) no shared mutable substructure (mutating the copy leaves original unchanged), (d) signature equality at mid-game (~60 moves placed). Full suite: **166/166 tests pass** post-patch.

**Other beneficiaries** (any codepath that does `copy.deepcopy(state)`):
- `virtual_score.py` (heuristic labeler used by warmstart gen)
- `warmstart.py` 2-ply heuristic lookahead
- vanilla MCTS rollouts (`mcts.py`, partially mitigated by `apply_action_inplace`)
- analysis scripts (`classify_v2_losses.py`, `audit_virtual_score_farmers.py`)

**Implications for v7:**
- At production sims=200, deepcopy load scales with sims × avg-tree-depth → the 3.3× should hold or widen.
- v6 cloud run was 9h / $3.40 for 20 iters → v7 with this fix runs the same in ~3h / ~$1.10, or ~60 iters in the original 9h budget.
- This eliminates the need to chase fp16 (already proved slower) or Cython-rewrite the PUCT loop (which the profile says was never hot).

**Reversal cost:** none. Engine patch is local to one method; old behavior preserved by deleting the method. Tests gate any future regression.

**Phase:** 4 (perf)

---

## 2026-05-13 — Orchestrator multi-process pool: NULL RESULT, workers are the bottleneck, not the GIL

**Context:** v6 cloud showed GPU at 5-20% utilization with the single-server orchestrator, suggesting the Python dispatch loop was GIL-bound and starving the GPU. Built multi-process pool (`src/carcassonne_ai/eval_server_pool.py`) to shard workers across N parallel server processes (commit `c34ecf9`). Hypothesis: more dispatchers → faster request servicing → 1.5-2× wallclock speedup.

**Cloud sweep** (vast.ai EPYC 9J14 Japan, $0.375/hr, ~$0.56 sweep cost, 2026-05-13):

| N | wallclock | dequeue % (avg per shard) | forward % | vs N=1 |
|---|---|---|---|---|
| 1 | **1134.5 s** | 64% | 35% | baseline |
| 2 | 1181.6 s | 68% | 31% | +4% slower |
| 4 | 1211.6 s | 76% | 23% | +7% slower |
| 8 | 1211.7 s | 84% | 16% | +7% (saturated) |

Each row is iter-0 self-play, 80 games × 200 sims × 80 workers on identical hardware. Per-stage timers in `eval_server.py` capture where the dispatcher Python loop spends time.

**Finding: the orchestrator GIL is NOT the bottleneck.** The dequeue % climbs monotonically (64→68→76→84) as we add shards — each shard waits LONGER for requests to assemble into batches. Forward % drops correspondingly (35→16). Dispatch is always 0% (instant). Multi-process sharding made the dispatcher even more idle, not less.

**What's actually bottlenecked: workers (CPU-bound MCTS tree work).** Each self-play worker spends ~50% of its time on MCTS tree expansion and ~50% blocked on eval responses. The eval responses ARE prompt (dispatch is 0% of orchestrator time); the workers can't generate requests fast enough because their own CPU work is the binding constraint. Fewer requests per shard → each shard idles more.

**Implications for v7:**

1. **The multi-process pool is correctly engineered but solves the wrong problem.** Keep the code (no harm in n_shards=1 default; back-compat preserved) but **do not use N>1 in any production run**. Each shard just wastes VRAM and adds queue contention.
2. **Real perf levers, in priority order:**
   - **fp16 inference** — workers spend 50% of time waiting on eval; cutting eval latency 1.5-2× directly reduces worker block time. Already supported via `--fp16` flag. Free perf, never enabled in production.
   - **Faster MCTS hot path** — 50% of worker time is Python MCTS tree work. Numpy hotspot profiling or Cython rewrite of the inner loop. Significant engineering, but the only path to real throughput gains at our worker count.
   - **More cores** — N=80 workers on 48 effective cores is 1.67× oversubscribed. A 64-core (effective) box would help, but at our box class the 48-core EPYC 9J14 is already the throughput optimum per $.
3. **Don't twiddle worker count to fix this.** Yesterday's W=96 sweep already confirmed games=96 is the worker-count optimum on this box class; we're already there in expectation. The throughput ceiling is real and structural.

**Decision:** orchestrator pool code stays in repo (validated correct + back-compat at n_shards=1) but **v7 will launch at `--orch-shards 1`**. Pivot the perf-engineering effort from "multi-dispatcher" to "fp16 + MCTS hot path".

**Cost of being wrong:** ~$0.56 cloud sweep + ~half a day of engineering on a fix that doesn't help. Cheap diagnostic; would have been ~$4-5 if we'd skipped the sweep and just launched v7 with N=4 (we'd have been 7% slower for the whole run).

**Reversal cost:** none. Code is committed and tested; we can revisit if the workload ever shifts (e.g. bigger net = forward % climbs = orchestrator might matter again).

**Phase:** 4

---

## 2026-05-13 — Phase 4 v6 cloud COMPLETED 20 iters; iter_12 = 70% wr (NEW global peak, first break above v5's 65% ceiling)

**Context:** v6 = same recipe as v5 + two changes: `--initial-checkpoint = selfplay_v5/iter_06.pt` (the 65% wr peak from v5) and `--orchestrator on` (validated 2026-05-12 Phase A). The hypothesis: does a stronger starting checkpoint let the same recipe compound past v5's ceiling?

Box: vast.ai 5090 + EPYC 9J14 Japan ($0.375/hr × ~9 h ≈ $3.40 actual cloud cost; +$0.06 sunk on a destroyed pre-launch box). Total wallclock 490 min for 20 iters (24.5 min/iter average).

**Three launch-time bugs (all now fixed on `gpu-orchestrator`):**
- Dockerfile lacked `openssh-server` → vast.ai SSH proxy rejected all keys. Fixed `62d5283`.
- `bootstrap_cloud.sh` pulled checkpoints but NOT the `heuristic_tau05/` warmstart training data → iter 0 train crashed after 16 min of self-play. Tarballed to bootstrap-v1 release; fixed `7a6f535`.
- `run_phase4_smoke.py` didn't pass `--orchestrator` to the subprocess calls. Fixed `19d8fe8`.

**Anchor-gate trajectory (n=20 vs warmstart_canonical):**
```
iter   v5         v6
 0     40 P       65 P
 1     20 F       65 P
 2     50 P       35 F
 3     60 P       60 P
 4     30 F       50 P
 5     50 P       40 P
 6     65 P       50 P   ← v5 peak (run halted at iter 9)
 7     35 F       35 F
 8     35 F       50 P   ← v6 breaks v5's death-spiral
 9     25 F       60 P   ← v5 halted here; v6 climbing
10     —          35 F
11     —          45 P
12     —          70 P   ← v6 PEAK (new global best, +5pp over v5)
13     —          65 P
14     —          45 P
15     —          55 P
16     —          30 F
17     —          45 P
18     —          25 F
19     —          65 P
```
Summary: **v5 = 5/10 PASS best 65%; v6 = 15/20 PASS best 70%.** Pass rate 50% → 75%, peak +5pp, survived 2× more iters.

**Findings:**

1. **Compounding past v5's ceiling IS possible — iter_12 demonstrates it.** First checkpoint that beats `warmstart_canonical` at ≥70% wr. The "iter_06 warmstart compounds" hypothesis is partially supported: it did push past 65%, just took 12 iters.

2. **The recipe cannot SUSTAIN the gain.** Late iters (14-19) oscillate 25-70% with no plateau. Suggests a structural bound around ~70%.

3. **v6 strictly Pareto-dominates v5 on every metric** (pass rate, peak, floor, survived iters). The "iter_06 + orchestrator" recipe is strictly better than starting from warmstart_canonical.

4. **Recipe drift is real but the rachet does its job.** Every FAIL was followed by a rachet recovery (warm from best-so-far + fresh RNG). Fail counter never reached 2/3.

5. **Capacity is not the immediate bottleneck.** Local 192×14 warmstart (15.8M params, 2.1× the 96×6 baseline) trained on the same heuristic_tau05 data showed essentially no validation improvement (val pol loss 1.65 → 1.62). The 96×6 net is already capacity-saturated at our data scale.

6. **Tile-placement dominates over meeple decisions.** Rule-based player with 3 meeple-phase rules + RANDOM tile placement scored 44% wr / ELO -42 vs random (n=50). Meeple-only rules can't compete. Tile-placement is where the value lives.

**Decision: keep `iter_12.pt` as the new strongest model. v7 should target sample efficiency / data diversity, not capacity or recipe twiddles.**

**Acceptance bars status:**
- ✅ Bar 1 (≥40% wr by iter 5): passed at 40% iter 5
- ❌ Bar 2 (≥55% wr by iter 10): failed at 35% iter 10 (redeemed by iter 12's 70%)
- ❌ Bar 3 (3 consecutive ≥55% by iter 15): never achieved 3 in a row; best was 2 (iters 12+13)
- ✅ Bar 4 (≥70% wr by iter 20): met at iter 12, 8 iters early

Mixed: 2/4 bars hit. Bar 3 (stability) is the real gap.

**v7 direction (deferred to separate plan-mode):** data-scarcity hypothesis. Cheap leverage: symmetry rotation augmentation (free 4× data), then KataGo-style aux loss heads if augmentation alone doesn't break the ceiling. See BACKLOG.md "Phase 4 v7 candidates".

**Reversal cost:** none. v6 artifacts persisted to `checkpoints/selfplay_v6/iter_00..19.pt` + `data/selfplay/v6_cloud/`. Cloud box destroyed. `iter_12.pt` is now the canonical strongest model.

**Phase:** 4

---

## 2026-05-12 — Phase 4 v5 cloud HALTED at iter 9 (3 consecutive anchor FAILs); peak iter 6 = 65% wr vs warmstart

**Context:** v5 cloud recipe = mix-floor 0.5 floor + window K=30 + best-so-far rachet + anchor-gate (n=20, threshold 40%, max-fails 3) + sims=200. Ran on rented 5090 + 48-core EPYC ($0.443/hr) starting 2026-05-12. Final result: harness halted on its own per anchor-max-fails=3 rule.

**Anchor-gate trajectory:**

| Iter | wr | passed | notes |
|---|---|---|---|
| 0 | 40% | ✅ | baseline (warmstart_canonical reference) |
| 1 | 20% | ❌ | rollback to iter_00 |
| 2 | 50% | ✅ | recovery |
| 3 | 60% | ✅ | first time ever above baseline |
| 4 | 30% | ❌ | rollback to iter_03 |
| 5 | 50% | ✅ | recovery |
| 6 | **65%** | ✅ | **peak** — new best ever, +25 pp above baseline |
| 7 | 35% | ❌ | fail #1 |
| 8 | 35% | ❌ | fail #2 |
| 9 | 25% | ❌ | fail #3 — halt |

**What's new this round:**
1. **First time we produced a meaningfully-above-baseline checkpoint.** iter_03 hit 60% and iter_06 hit 65%, vs the +0 pp ceiling on every prior recipe (v1-v4 all regressed to 12-30%).
2. **Best-so-far rachet engaged correctly** — recovered from iter_01 (FAIL) and iter_04 (FAIL) by rolling back to the prior peak's base.
3. **But the recipe still drifts.** After peak iter_06, three consecutive iters regressed and the rachet couldn't recover. Suggests the closed-loop drift mode is still present, just slower than v1-v4. mix-floor 0.5 is not enough on its own.

**Cost:** ~$3 cloud spend for the actual v5 run (6.5h wallclock × $0.443/hr) + ~$2 across multiple bootstrap attempts (rsync proxy throttling, wrong PyTorch wheel on Blackwell, OOM at W=48 chain h2h before --eval-workers cap was added). Total today ~$5.

**Decision:** Pull data + checkpoints (96 MB) + log. Destroy box. Quarantine v5 checkpoints (`checkpoints/selfplay_v5/iter_NN.pt`) for Phase 6 emergence analysis — they're the first set we have that includes any genuinely-above-baseline weights.

**Acceptance status:** v5 PARTIAL — recipe peaks above baseline (proves the AlphaZero loop CAN improve our warmstart) but is not stable enough to compound. Need another recipe iteration OR more compute per iter OR a structural change (the GPU orchestrator, see entry below).

**Phase:** 4 (self-play loop sanity)

---

## 2026-05-12 — Phase A cloud bench: orchestrator validated, W=96 emerges as new optimum (15% faster than W=48)

**Context:** Phase A of the v6 plan — rent a 5090 + 48-core EPYC box, prove the orchestrator survives W=48 chain h2h (where baseline OOMs on torch 2.11), and sweep W to find the v6 production setting. Ran on instance 36645490 (machine 79615 / host 384353 Japan, $0.3747/hr). Total Phase A spend ~$1.40 across one wedged box + the real one.

**A1 — OOM-relief test: orchestrator W=48 chain h2h:**
- 50 self-vs-self games at sims=100. **30W/0D/20L, avg diff +0.4** (≈50/50 as expected by symmetry).
- **Final VRAM: 2 MiB** (vs baseline's projected 58 GB OOM at W=48). Smoking-gun pass.
- Wallclock: 464.8 s.

**A3a vs A3b — orchestrator vs baseline self-play at W=48 sims=200:**
- A3a (orchestrator): 80/80 games, 1168.1 s, 13246 positions, 2 MiB peak VRAM.
- A3b (baseline): **36 of 80 games OOM'd** with `CUBLAS_STATUS_ALLOC_FAILED` + `CUDA out of memory`. Only 44 completed.
- **The baseline pattern is BROKEN at W=48 on torch 2.11.** v5 ran fine at W=48 on torch 2.7; the difference is torch 2.11's larger per-worker allocator pool (~700 MB) × 48 > 32 GB. The orchestrator isn't just nice-to-have; it's structurally required for W=48 with current torch.

**Worker sweep (orchestrator on, sims=200, 80 games, same hardware):**

| W | Wallclock | s/game | Δ vs W=48 |
|---|---|---|---|
| 44 | 1173.6 s | 14.7 | +0.5% (tie) |
| 48 | 1168.1 s | 14.6 | baseline |
| 52 | 1191.3 s | 14.9 | +2% |
| 64 | 1326.1 s | 16.6 | **+14% (local worst)** |
| 80 | 1006.4 s | 12.6 | −14% |
| **96** | **992.9 s** | **12.4** | **−15% (best)** |

**Non-monotonic curve.** Light oversubscription (W=52, W=64) is the WORST regime: workers thrash CPU but don't queue-block enough to free slots. Heavy oversubscription (W=80, W=96) flips into a regime where workers spend so much time waiting on the orchestrator's request queue that other workers run on freed CPU. Net: **W=96 is 15% faster than W=48 on this hardware**.

**Implications for v6:**
- Use `--workers 96` (not 48). Saves ~110 min over a 12 h run = ~$0.75.
- Confounds the v5→v6 clean A/B (v5 was W=48), but the throughput win is large enough that we accept the confound. v6 vs v5 comparison stays valid for the "recipe + warmstart" question; W is independently the new optimum.
- Could try W=128 in a follow-up bench — curve hadn't turned back upward yet at W=96. Deferred.

**Decision:** v6 launches at W=96 with orchestrator on, iter_06.pt as initial weights, otherwise identical to v5 recipe.

**Phase:** 4 (perf / infra → recipe)

---

## 2026-05-12 — GPU orchestrator (inference-server pattern) — landed + numerically validated, 10-14% slower on local 5060 Ti (expected); cloud bench pending

**Context:** Each self-play / eval worker currently loads its own copy of the net (~600 MB allocator pool per worker). At W=48 chain h2h that's 58 GB > 32 GB → OOM. The fix in production was capping `--eval-workers 20`, leaving cores idle. The GPU orchestrator addresses this structurally: one server process owns the net + CUDA context; N CPU-only workers send (obs, scalars, mask) over IPC; server batches across workers.

**What landed (branch `gpu-orchestrator` off `phase-4-selfplay`):**
- `src/carcassonne_ai/eval_server.py` (210 LoC) — `_server_loop` + `start_server` + `shutdown_server` + `ServerHandles` dataclass. Adaptive batching with `max_batch=256`, `batch_timeout_ms=2.0`. Uses `mp.Queue` for IPC (no extra deps).
- `src/carcassonne_ai/remote_evaluators.py` (115 LoC) — drop-in `make_remote_single_evaluator` / `make_remote_batch_evaluator` matching the existing factory contract.
- `tests/test_eval_server.py` (175 LoC) — numerical agreement (single + batch), concurrent 4-worker no-hang, shutdown propagation (BrokenServerError within timeout, not infinite block). **All 4 pass in 24 s.**
- `scripts/run_selfplay_iter.py` — `--orchestrator` flag. 1 server process for the lone net.
- `scripts/eval_iter_head_to_head.py` — `--orchestrator` flag. 2 server processes (one per net).

**Local bench, RTX 5060 Ti, W=8, sims=50, batch_size=8, 10 games:**

| Mode | Wallclock | Positions | Note |
|---|---|---|---|
| Baseline (per-worker net) | 204.5 s | 1658 | reference |
| Orchestrator (1 server) | 224.7 s | 1657 | **0.91× (10% slower)** — IPC overhead wins over batch-coalescing gain at small W |

Eval bench (W=4, sims=25, 6 games, 2 nets):

| Mode | Wallclock | W/L | avg diff |
|---|---|---|---|
| Baseline (2 nets/worker) | 74.3 s | 6/0/0 | +42.3 |
| Orchestrator (2 servers) | 84.5 s | 6/0/0 | +40.0 |

Same W/L tally — fp32-reorder argmax ties cause minor MCTS-tree shifts (the documented ±1-game noise floor). 14% wallclock slowdown.

**Acceptance:** plan called for ≥0.95× baseline wallclock at W=16; we got 0.91× at W=8. Below bar **on the small GPU as expected** — overhead dominates when the per-worker pattern already fits VRAM and only 8 concurrent workers can't generate enough request density to amortize IPC.

**Why this still matters for cloud:** on the 5090 + 48-core box:
- Baseline OOMs at W=48 chain h2h (58 GB > 32 GB). Production has to cap W=20.
- Orchestrator holds 1 GB server + 0 per-worker VRAM → unlocks W=48 chain h2h (and W=96+ on bigger CPU boxes).
- Cross-worker batching: 48 workers × 8 boards = up to 384 boards/forward (vs current 8 boards/forward × 48 separate forwards) — 4-8× higher per-forward efficiency.

**Decision:** Land on `gpu-orchestrator` branch behind `--orchestrator` flag (default off). Validated locally; cloud bench is the actual proof-point. Bench during the next cloud run before turning it on for prod.

**Phase:** 4 (perf / infra), gated on v6 plan-mode decision

---

## 2026-05-12 — MPS test confirms W=48 + fp32 + no-MPS is optimal; ~$1.50 spent across 4 rentals

**Setting:** Yesterday's cloud bench (entry below) established W=48 + fp32 as the optimum, but left open whether CUDA MPS could squeeze more workers in by sharing CUDA contexts across processes. Three rentals were tried today to validate.

**Per-worker VRAM measurement (Tue 2026-05-12 ~13:00 UTC, instance 36616189, 5090 + 48-core EPYC 9J14 Taiwan, $0.443/hr):**

| Config | per-active-worker VRAM | what it tells us |
|---|---|---|
| no_mps | **662 MiB** | Each torch process owns its allocator pool + CUDA context |
| MPS | **~600 MiB** | MPS shares CUDA contexts (~300-500 MB) but each worker keeps its own torch allocator pool. Net savings ≈10%, not 50%+. |

So MPS savings are real but modest. The dominant cost per worker is PyTorch's caching allocator pool, NOT the CUDA context that MPS deduplicates.

**Throughput verification at W=52 + MPS + games=80 (the actual production-scale workload):**
- VRAM peak: 31977 MiB / 32607 MiB (98% used) — fit, but with only 630 MB headroom
- 80 games completed in 427.5s = **5.3s/game wallclock**
- vs W=48 no_mps at games=64 → 217s = 3.4s/game wallclock

W=52 actually **slower** than W=48. The 5090 + 48-core EPYC has cgroup quota of ~46 effective cores; W=52 oversubscribes CPU, workers fight for slices, total throughput drops. CPU-bound, not VRAM-bound.

**Decision:** Lock prod run at W=48 + fp32 + no-MPS. MPS adds operational complexity (daemon startup, env vars, occasional CUDA shutdown errors) for zero throughput gain at our scale.

**For future scaling past W=48** (Phase 6 / AlphaZero-scale work, not now):
- The real fix is the **inference-server pattern** — one process owns the network on GPU, workers send forward requests via multiprocessing.Queue. Eliminates per-worker allocator pool entirely. ~1-2 days of careful engineering.
- Cheap shortcut: rent an 80 GB GPU (H100/A100 ~$1.50-2/hr) — VRAM cap doubles, can run W=96+ without code changes.

**Today's cloud spend breakdown (~$1.50 total):**
- Instance 36592587 (Japan, 48-core EPYC, ~30 min wallclock for sweep + fp16 bench, results: W=48 max, fp16 is slower on Blackwell too): ~$0.40 — useful data
- Instance 36597509 (Japan): network deadlock on rsync, no usable data: ~$0.40 — wasted
- Instance 36598909 (Japan): killed pip install mid-way thinking torch 2.4.0 was sufficient; turns out 5090 (sm_120) requires torch ≥ 2.7 (we have `torch>=2.7` in requirements.txt for exactly this reason), bench produced 0-process VRAM samples: ~$0.40 — wasted
- Instance 36616189 (Taiwan, $0.443/hr 48-core, fast inet): clean MPS bench + W=52 verification: ~$0.30 — useful data

**Lesson:** never skip `uv pip install -r requirements.txt` on a fresh box. The `torch>=2.7` pin exists because Blackwell sm_120 needs torch 2.7+ for kernel images. Shortcuts cost more than they save.

**Reversal cost:** low. All bench data captured in /tmp/cloud_*.log locally. Total cloud spend so far is <1% of the planned prod-run budget ($10).

**Phase:** 4 prod launch ready.

---

## 2026-05-12 — Cloud bench landed: W=48 + fp32 is the optimum on RTX 5090 + 48-core EPYC

**Setting:** Phase 4 v2/v3/v4 all regressed locally (recipe ceilings around -100 to -200 ELO vs warmstart). Decision: rent vast.ai 5090 + 48-core EPYC 9J14 for ~$0.50 to benchmark worker scaling and fp16 on real production-class hardware before committing to a $10 prod run.

**Box**: vast.ai instance 36592587, RTX 5090 + AMD EPYC 9J14 (Bergamo, Zen 4c, 48 effective cores of 384 host cores), 504 GB RAM, 32 GB VRAM, PCIe 5.0 x54, 903 Mbps inet, $0.387/hr, Japan.

**Worker scaling bench (sims=100, games=64, batch_size=8, no MPS):**

| W | wallclock | speedup vs W=8 | games/worker |
|---|---|---|---|
| 8 | 1533 s | 1.00× | 8.00 |
| 16 | 781 s | 1.96× | 4.00 |
| 32 | 420 s | 3.65× | 2.00 |
| 48 | 217 s | 7.05× | 1.33 |
| 64 | OOM (32 GB VRAM exhausted; each spawn worker ≈ 500 MB GPU context overhead × 64 = 32 GB) |
| 96 | not tested (would also OOM) |

**Verdict (worker count):** **W=48 is the safe max** on a 32 GB GPU without CUDA MPS. Scaling is roughly linear up to 48 workers. The OOM is governed by per-worker CUDA context allocations, not by our small (7M param) network weights.

**fp16 bench on Blackwell 5090** (warmstart_canonical, n=48 mid-game boards):
- Numerical agreement: PASS (max prior L1 = 0.004, max value diff = 0.0003, 0 argmax disagreements)
- Single-board (B=1) wallclock: **0.82×** (slower vs fp32)
- Batch (B=8) wallclock: **0.92×** (slower vs fp32)

**Verdict (fp16):** Even on the 5090's bigger Tensor Cores, fp16 is slower for our workload. The autocast context + .float() cast-back overhead exceeds the GPU compute savings on small networks at small batch. This is the *same finding* as the local 5060 Ti bench from 2026-05-10. fp16 is officially dead for self-play inference at our scale; revisit only if (a) network grows past 30M params or (b) batch grows past 32.

**Per-core CPU comparison** (5800X local vs EPYC 9J14 remote):
- EPYC 9J14 is Zen 4c (Bergamo), better IPC than Zen 3 5800X but cloud variants run lower clocks
- Net per-core single-thread: roughly equivalent or modestly worse on the cloud box
- The cloud advantage is **density**: 48 effective cores vs the 5800X's 16 SMT threads → ~3× more workers in parallel, ~7× total throughput at W=48 vs local W=16

**Cost projection for the 30-iter prod run** (sims=200, games=80, W=48, fp32, same v3/v4 recipe):
- ~50 min per iter (~12 min self-play + 5 min train + 25 min head-to-head + 5 min anchor gate)
- 30 iters × 50 min = 25 h × $0.387/hr ≈ **$10**

**Decision:** Prod run plan locked at **W=48, fp32, on a 5090 + 48-core EPYC class box** (~$10). MPS test deferred (one MPS attempt failed mid-bench from a botched `uv pip install`; box destroyed; ~$0.40 wasted on failed attempts). If MPS works it could squeeze W=72-96 and cut cost to ~$5, but the existing W=48 plan is fine to launch as-is.

**Reversal cost:** low. All bench data + box destruction logs in chat history. Total cloud spend so far: ~$0.40.

**Phase:** 4 prod planning.

---

## 2026-05-11 — Phase 4 v2 recipe FAILED acceptance: mix=0.3 floor not enough

**Setting:** Phase 4 v2 (post-2026-05-10 plan-mode session), four recipe fixes from BACKLOG: warmstart-mix floor at 0.3 (vs v1's 0.0), K=10 → K=30, anchor-gate per iter (10 games at sims=50 vs warmstart_canonical), eval games 20 → 50. New CLI plumbed in commit `a1f29ec`. Outputs at `data/selfplay/v2_sanity/` and `checkpoints/selfplay_v2/iter_*.pt` (kept separate from quarantined v1).

**5-iter sanity result (4 hours wallclock):**

Per-iter anchor gate (n=10 each):

| Iter | Mix | Anchor wr | Gate |
|---|---|---|---|
| 0 | 1.0 | 60% | PASS |
| 1 | 0.7 | 40% | PASS (borderline) |
| 2 | 0.4 | 60% | PASS |
| 3 | 0.3 | 40% | PASS (borderline) |
| 4 | 0.3 | 20% | **FAIL** (1 strike, no halt) |

Chain head-to-head (50 games each):

| Match | W/D/L | ELO Δ |
|---|---|---|
| 1 vs 0 | 21/1/28 | -49 |
| 2 vs 1 | 25/0/25 | 0 |
| 3 vs 2 | 23/1/26 | -21 |
| 4 vs 3 | 23/0/27 | -28 |

Total chain ELO drift: **-98 over 4 iters** vs v1's misleading +612 over the same span. Chain ELO is now consistent with absolute strength (per the 2026-05-10 methodology fix).

**Definitive iter_4 vs warmstart_canonical at n=50:** 12W/0D/38L = **24% wr, ELO -200**. 95% CI is [13%, 37%] — upper bound below the 40% acceptance threshold. This is a real regression, not noise.

**v1 vs v2 comparison at same iter count (5):**
- v1 iter_5 (mix dropped to 0 at iter 3): 30% wr at n=30 → ~-134 ELO
- v2 iter_4 (mix held at 0.3 floor): 24% wr at n=50 → -200 ELO

v2 doesn't fall as far per iter as v1 (the chain-ELO drift slope is -25 ELO/iter for v2 vs ~-50 ELO/iter for v1), but the floor mix=0.3 still permits drift. The recipe fixes weren't sufficient.

**Decision:** Phase 4 v2 acceptance FAILED. Quarantine `checkpoints/selfplay_v2/iter_*.pt` and `data/selfplay/v2_sanity/` alongside the v1 artifacts (don't delete; useful for Phase 6 emergence analysis comparing v1's chain-ELO illusion to v2's slowed-but-real regression).

**v3 recipe candidates (need plan-mode session before implementing):**

1. **Higher warmstart-mix floor (0.5 or 0.7).** v2 at 0.3 was insufficient; doubling/tripling the anchor weight in training mix is the most direct fix. Cost: less pure self-play signal per iter (network may have a harder time exceeding warmstart in absolute terms). Trade-off worth measuring.
2. **Best-so-far reference instead of warmstart_canonical.** Track "best iter that passed anchor gate"; on FAIL, restart next iter's warm-from from best-so-far instead of latest. Existing infrastructure (anchor_gate_log.json) makes this easy to implement.
3. **Higher sims for self-play (200 vs 100).** AlphaZero used 800. Noisier policy targets compound; doubling sims doubles per-iter cost (~7h for 5-iter sanity) but might cleanly fix the noise floor. Worth a controlled test.
4. **Reject-iter on anchor FAIL.** Currently FAIL just logs and increments fail counter. Could instead delete the failing iter's checkpoint and re-train iter N from the previous (best/warmstart) starting point with a new RNG seed. Preserves the "checkpoint chain advances only on improvement" property.

**Combinations matter.** A future plan-mode session should select 1-2 of these for v3 (probably higher mix-floor + best-so-far reference) rather than all four — each adds confounders to the diagnosis if v3 also fails.

**What v2 confirmed (so we keep this in v3):**
- The anchor-gate methodology is the right gate; it caught the borderline-passes (iter 1, 3) and the clear FAIL (iter 4) that chain ELO would have hidden.
- The skip-on-error harness, the fp16/CLI plumbing, the per-iter checkpoint cadence, and the v1/v2 separation in `checkpoint-root` all worked as designed.

**Reversal cost:** low. Recipe fixes are CLI defaults and ~80 lines of anchor-gate code, none of which is wrong — just insufficient at this floor value. Branch is intact for v3.

**Phase:** 4 (still re-opened). v3 plan-mode session is the next step.

---

## 2026-05-10 — Chain-vs-prev ELO discredited as standalone metric; 30-iter "PASS" was a regression in absolute strength

**Setting:** Phase 4 30-iter sanity run (`data/selfplay/sanity_30iter`, recipe per the 2026-05-08 vloss-landed entry: sims=100, eval-sims=100, eval-games=20, K=10 buffer, warmstart-mix schedule [1.0, 0.7, 0.4, 0.0], 50 self-play games/iter). Chained head-to-head (each iter vs the previous) showed **ELO 0 → +612 over 24 iters** — every Phase 4 acceptance check from the 2026-05-03 entry was passing (loop runs, ELO trend up, no NaN losses, no entropy collapse). About to top up vast.ai and launch a 200-iter production run on rented hardware (~$15-25).

**Anchor eval before rental as a $0 sanity check:** added `--no-elo-log` flag to `eval_iter_head_to_head.py`, ran `iter_24.pt vs warmstart_canonical.pt` at 50 games / sims=100 / 16 workers / batch=8.

**Result:** iter_24 = **6W/1D/43L** vs warmstart_canonical, avg score diff -32.7, ELO delta **-330**. The network drifted ~942 ELO worse in absolute terms while the chain ELO marched +612 better.

**Diagnostic anchors at iter_5 (so far; iter_10/15/20 in flight):** iter_5 already at **9W/1D/20L vs warmstart, ELO -134**. Confirms regression started in the first ~5 iters — likely as soon as the warmstart-mix schedule hit 0 at iter 3.

**Why this happened (root cause — recipe, not infrastructure):**

The chain ELO measures *relative* strength: "did iter N learn to beat iter N-1?" Both networks can drift toward worse-but-mutually-defeating play, and the chain still climbs. Two compounding ingredients:

1. **Warmstart-mix dropped to 0 at iter 3.** The heuristic-labeled distribution was the only anchor to "actually-good play." Once dropped, training is a closed loop on self-play data — no signal pulling the policy toward objectively reasonable moves.
2. **Replay-buffer K=10.** At iter 11+, no warmstart games appear in training data at all. The echo chamber becomes hermetic.
3. **Sims=100 (vs AlphaZero's 800)** produces noisy policy targets. Noise compounds when the only correction signal is more samples from the same distribution.

The 2026-05-03 "Phase 4 smoke PASS" entry is **superseded** by this finding. That smoke ran 5 iters on the same defective recipe. The +175 ELO it reported was the same chain-ELO illusion at smaller scale; an anchor eval would almost certainly have shown the same regression already underway.

**Decision:** Two parts.

1. **Chain ELO is now insufficient as the sole acceptance signal.** Future Phase 4 runs (and Phase 5/6 work that depends on Phase 4 outputs) require an anchor eval against a fixed reference (`warmstart_canonical.pt` is the canonical anchor) at the start, end, and at least every 10 iters. Anchor wins-vs-warmstart is the primary metric; chain ELO is supplementary.

2. **The current `phase-4-selfplay` outputs (`checkpoints/selfplay/iter_*.pt`, `data/selfplay/sanity_30iter/`) are quarantined.** They will not be used as warmstart for any subsequent run, will not be merged to main, and are kept only for the Phase 6 emergence-analysis archive. The next Phase 4 attempt warm-starts from `warmstart_canonical.pt`.

**Recipe fixes for the next Phase 4 attempt** (going to BACKLOG; details for a future plan-mode session):

- **Floor warmstart-mix at 0.3** throughout (don't drop to 0). Cheap, principled.
- **K=10 → K=30** replay-buffer window. More history, more stability, mostly free in disk cost (~1 GB extra at 200 iters).
- **Anchor-gate**: only accept new iter as warmstart for next iter if it beats `warmstart_canonical` at ≥40% in a quick check (10 games at sims=50 = ~3 min). Effectively a regression-stop. Reject-and-retrain-from-prev on failure.
- **Larger eval games** (20 → 50) for the chained head-to-heads to reduce per-iter ELO variance (a single-game swing at N=20 = ±35 ELO).

**What we got right (so we don't change it):** the methodology of "anchor eval before cloud rental" caught this for $0. Without that gate we'd have spent ~$20-25 + 2-3 days of cloud time to learn the same thing. Future production-scale plans must keep this gate.

**Reversal cost:** low. The 24 trained checkpoints are quarantined, not deleted. The recipe fixes are 4 small CLI flag additions. Branch is intact for re-launching a clean run.

**Phase:** 4 (re-opened). The 2026-05-03 closure was premature.

---

## 2026-05-08 — Virtual-loss + batched-eval MCTS landed; vloss applied in parent's perspective

**Setting:** Phase 4 smoke ran the serial NeuralMCTS path (one GPU forward per sim per worker). At sims=25 / 7 workers we measured ~4 ms/sim, but at production sims=100-200 the GPU forward is a larger fraction of per-sim cost. Standard AlphaZero remedy: virtual-loss MCTS — collect K leaf-evaluation requests from parallel descents and serve them with one batched GPU call.

**Implementation (commit `f9d805e` + the eval-side wiring in this session):**
- New `NeuralMCTS` constructor params: `batch_size` (default 1 = serial), `batch_evaluator` (`Callable[[list[Board]], (priors[B,A], values[B])]`), `virtual_loss` (default 1.0).
- New methods: `_select_leaf_with_vloss`, `_run_batch`, `_eval_boards`, `_expand_with_priors`, `_apply_vloss_at_child`, `_undo_vloss_at_child`.
- Plumbed through `selfplay.play_one_selfplay_game`, `run_selfplay_iter.py --batch-size N --virtual-loss V`, `eval_iter_head_to_head.py --batch-size N`, and `run_phase4_smoke.py`.

**Vloss formulation — sign in parent's perspective, NOT node's own:**

The textbook formulation ("subtract `vloss` from W in node's own perspective") is wrong for negamax-style perspective-flipping trees with player alternation. With own-perspective vloss, the parent's view of an in-flight child becomes BETTER, not worse — because `Q_parent_view = -child.Q` for different-player parent-child pairs. Net result: subsequent sims in the same batch happily revisit the same leaf instead of diversifying.

The fix: apply vloss in the PARENT'S perspective. At each step of selection:
- if `parent.player == child.player` (rare TILE→MEEPLE phase transition): `child.W -= virtual_loss`
- else (typical alternation): `child.W += virtual_loss`

Either way, `Q_parent_view` of child drops by `virtual_loss / N`. Backup undoes this by inverting the same sign rule, then adds the real value in node's own perspective. Net per node: `N += 1`, `W += signed_real_value` — identical to serial backup.

Root has no parent, so root only gets `N += 1` (root.W doesn't enter PUCT for any child).

**Testing:** 9 new tests in `test_neural_mcts_virtual_loss.py` cover total visit count correctness, batch-call accounting (≤ `ceil(sims / B) + 1` calls), vloss-undo invariants (`|W| ≤ N`), diversification (≥2 root actions visited at branching positions), and the serial-mode bypass (when `batch_size=1`, `batch_evaluator` is never called even if wired). Full suite: 145 pass.

**Measured speedup:** Single-process at sims=25, batch_size=8: 48.9 s → 34.0 s (1.44×) for one 166-position self-play game on RTX 5060 Ti. Multi-worker / production-sims speedup is being calibrated as of this entry; expected to compound at higher sims because the GPU per-call overhead amortizes better when batches fill.

**Reversal cost:** Low — `batch_size=1` (default) preserves the existing serial code path bit-for-bit. To revert: don't pass `--batch-size N > 1` on any CLI.

**Phase:** Phase 4 optimization (post-smoke, pre-production-scale).

---

## 2026-05-03 — Phase 4 smoke PASS: 5 iters, ELO 0 → 176, loop runs cleanly

> **Superseded by the 2026-05-10 entry above.** The +176 ELO reported here was a chained-head-to-head measurement only; anchor evals on the 30-iter follow-up showed the same recipe drives an absolute-strength regression vs `warmstart_canonical`. Treat this entry as historical: the loop did run cleanly (which was the literal acceptance bar), but the recipe is broken and the closure was premature.

**Setting:** Phase 4 plan (in `~/.claude/plans/new-project-in-this-spicy-finch.md`) called for a local 5-iter self-play smoke as the acceptance bar — loop completes cleanly, per-iter checkpoint + ELO logged, no policy collapse, no NaN losses. We are not chasing absolute strength in Phase 4; production-scale long runs are a future plan-mode session.

**Build (commit `79905cd`, branch `phase-4-selfplay`):**
- `NeuralMCTS` gained Dirichlet root noise (configurable α, ε; root-only, applied once per fresh root, reset by `clear()`) and `select_for_training(τ)` for sampling-from-visit-count policy targets. Both opt-in; default-disabled keeps tournament/eval call sites unchanged.
- `selfplay.play_one_selfplay_game` produces a `GameDataset` matching the warmstart schema. Value targets are raw z ∈ {-1, 0, +1} sign-flipped per position's current_player. Reuses streaming-dataset machinery unchanged.
- `elo.py` — stateless ELO update from (W, L, D) capped ±800 to keep small-N matches sane.
- 4 driver scripts (`run_selfplay_iter`, `train_iter`, `eval_iter_head_to_head`, `run_phase4_smoke`) with per-game `.npz`/JSON checkpointing and resumable-per-step outer loop.
- Phase-6 prep: every iter saves a numbered checkpoint at `checkpoints/selfplay/iter_NN.pt` plus `iter_NN.metrics.json`; nothing overwrites or deletes.

**Calibration (1 iter, 10 games, s=25, 4 workers): 5.7 min wallclock.** Beat the 50 min/iter pencil-sketch by ~10×; per-MCTS-sim cost was ~4ms (vs the estimated 100ms). The GPU is partially saturated even at 4 workers — cuda-cap=4 was conservative.

**Worker-cap experiment** (added `--no-cuda-cap` flag): 4 workers = 176.5s/10 games; 7 workers = 155.1s/10 games (~12% faster, diminishing returns due to CUDA context-switch overhead). Used `--workers 7 --no-cuda-cap` for the smoke.

**Bug found and fixed during smoke:** the trainer's `policy_cross_entropy` aborted iter 1 because some self-play policy targets had ~0.16-0.36 mass on a snapshot-mask-illegal action. Root cause: occasional divergence between the outer `game.get_valid_moves(board)` call and the MCTS-internal `get_valid_moves` call (suspect: stale legal-moves-cache entry reused across searches; not yet root-caused). Fix: clip MCTS visit distribution to the snapshot mask before normalizing in `selfplay.py`. The snapshot mask is the contract for legality at this position; phantom visits are dropped. If everything got filtered, fall back to uniform-over-legal. Test bumped from sims=3 to sims=25 (production-like) so the deeper PUCT tree path that triggers the bug is exercised in CI.

**Smoke result (5 iters, 25 games/iter, s=25 self-play / s=50 eval, 53.7 min wallclock, `data/selfplay/smoke_v1`):**

| Iter | H2H vs prev | ELO delta | Cumulative ELO |
|---|---|---|---|
| 0 → 1 | 5W/4L/1D | +34.9 | 34.9 |
| 1 → 2 | 6W/4L/0D | +70.4 | 105.3 |
| 2 → 3 | 5W/5L/0D | +0.0 | 105.3 |
| 3 → 4 | 6W/4L/0D | +70.4 | **175.7** |

Strictly non-decreasing ELO across all 4 head-to-head matches. iter 3 hit the 50/50 noise floor at 10 games — expected variance, not regression.

**Stability checks:**
- ✓ No crashes (post-fix), no NaN losses, no policy collapse
- ✓ Train losses decreasing across iters (val_val_loss 0.50 → 0.16 train, val 0.56 → 0.27 → 1.07 ⚠️)
- ⚠️ iter 4 val_val_loss spiked to 1.07 (val split is small — ~1K positions on 6 files). Worth watching in production; not smoke-blocking.

**Decision:** Phase 4 acceptance MET. The loop runs cleanly end-to-end. Production-scale long runs are a separate decision (cloud rental likely needed for 50+ iters; original BACKLOG entry stands). Phase 5 (analyzer) can begin from the same `warmstart_canonical.pt` baseline plus optionally any of the saved iter checkpoints.

**Reversal cost:** low. All Phase 4 scaffolding is on `phase-4-selfplay` branch, not merged to main. Bug fix is a small defensive clip in selfplay; doesn't affect existing data shapes or training.

**Phase:** 4 closure → Phase 5 entry next.

**Open items deferred to a future production-scale plan:**
- Virtual-loss / batched MCTS (BACKLOG): the calibration showed ~4ms/sim wallclock at 4 workers; for 50+ iter production, batched MCTS could 3-5× per-game throughput. Right move when production scale is on the table.
- Larger eval game count per head-to-head (currently 10; the 5W/5L noise floor at iter 3 argues for 30+ for production).
- Automated entropy-floor abort + larger val split for stability monitoring.
- Root-cause the snapshot-mask vs MCTS-mask divergence (defensive clip handles symptom; bug is benign at our scale but worth fixing for hygiene).

## 2026-04-29 — Phase 3 closure: declare v2 the warmstart, skip remaining acceptance iteration, proceed to Phase 4

**Setting:** v2 (100K heuristic-labeled at tau=0.5) hit T1=88/100 (88%) and T2=5/16=31% on NeuralMCTS(s=50) vs vanilla(s=100). Both miss the original prompt's acceptance bars (T1 ≥90%, T2 >55%). Failure-mode classify split (11 v2 T2 losses) showed mean realized gap +11.5 vs mean endgame gap −17.8 — net wins in-play, loses endgame. Working hypothesis: virtual_score's snapshot evaluation is a poor proxy for actual final-score-differential when label-time is mid-late game with substantial development remaining; the value head misses the long-horizon endgame component (farmer field merges, contested-field development, fields-fragility).

**v3 experiment (this entry):** relabel the v2 dataset's value targets with `tanh(actual_game_final_score_diff / 15)` instead of `tanh(virtual_score / 15)`. Same boards, scalars, policy targets, masks. Same hyperparameters (6×96, 20 epochs, batch 256, lr 1e-3, wd 1e-4). Same checkpoint slot. Single variable change.

**Pre-flight:** correlation of virtual_score-target vs final-score-target on 1000 positions = r=0.58. Targets disagree meaningfully (abs-mean diff 0.31 on a [−1, +1] scale), so the experiment was worth running.

**Result:**
- v3 T1 head-to-head on identical 100 seeds: **84/100 (84%)** vs v2's 88/100 (88%). Δ = **−4pp**, not within ±3pp wash band but not ≥−5pp clear regression either.
- v3 final-epoch val MSE = 0.324 vs v2's value MSE in the 0.08 range — ~4× higher. The noisier final-score target genuinely hurts the value head.
- v3 val pol CE plateaued from epoch 8 onward (1.65-1.68); train pol CE kept dropping to 1.27. Clear policy-head overfit.
- Best checkpoint by val loss = epoch 12. Used for T1.

**Interpretation:** the noise hypothesis was right. Random-self-play final scores carry ~20 turns of unrelated development noise downstream of the labeled position, which the value head cannot disentangle from the position's own quality. Snapshot virtual_score is the better target for value-head supervision under these label sources.

**Decision:**
1. **v2 is the canonical warmstart.** Promoted to `checkpoints/warmstart_canonical.pt` (copy of `warmstart_heuristic_tau05_prod.best.pt`).
2. **Skip remaining Phase 3 acceptance iteration.** The remaining warmstart improvement candidates — MCTS-labeled at scale, hybrid rollout labels, 2-ply heuristic policy, c_puct sweep continuation — all require compute commitments comparable to Phase 4 itself with no guarantee of clearing the original prompt's acceptance bar. The acceptance numbers (T1 ≥90%, T2 >55%) were unmeasured guesses in the original prompt, not load-bearing requirements.
3. **Proceed to Phase 4 (self-play).** The only way to get genuinely strong labels is from strong play, and we don't have a strong player to label with. AlphaZero solves this via self-play (the network labels its own training data, getting stronger as labels improve). Continuing warmstart iteration is trying to substitute label engineering for the self-play loop, and v3's failure is evidence we've hit the ceiling on that substitution.

**Why not retry v3 with a different policy regime / different lookahead / different sims:** every such variant runs into the same root cause — labels generated from random self-play cap out at random-self-play strength. The v3 experiment closes off the value-target axis cleanly. The remaining axes (policy lookahead depth, MCTS sim count for labels) are all the same kind of label-engineering substitution.

**Deferred (may revisit if Phase 4 stalls):** 2-ply heuristic policy lookahead (already plumbed via `--heuristic-lookahead 2ply`), full c_puct sweep at {1.5, 3.0, 5.0}, MCTS-label fallback at 50K positions s=50 (~26 hours). All gated on Phase 4 needing them.

**Reversal cost:** medium. v3 dataset and checkpoint stay on disk; if Phase 4 needs the noisier-target experiment revisited (e.g. as a regularizer), can resume directly.

**Phase:** 3 closure → Phase 4 entry.

**Diagnostic artifacts:**
- `data/phase3_diagnostic/v2_loss_split.md` — realized vs endgame breakdown of v2 T2 losses
- `data/phase3_diagnostic/farmer_audit.md` — confirmed virtual_score's farmer term IS engine farmer (no calibration gap)
- `data/phase3_diagnostic/v3_vs_v2_t1.md` — v3 T1 head-to-head with full per-epoch training metrics

## 2026-04-28 — Phase 3 v1 acceptance result + v2 retry plan (sharper tau)

**Setting:** 100K heuristic-labeled positions at tau=10.0, trained 6×96 ResNet 20 epochs.

**Training metrics:**
- Train value MSE: 0.165 → 0.030 (5.5× reduction — strong learning)
- Val value MSE: 0.137 → 0.081, best at epoch 14
- Train policy CE: 1.860 → 1.855 (essentially flat)
- Val policy CE: 1.879 → 1.879 (flat)
- Diagnosis: value head learned the position-value map well; policy head barely fit because tau=10.0 produced near-uniform targets (top-1 mass ~45%, top-1/uniform ratio ~1.17×).

**Tournament 1 (network argmax vs random, 100 games):**
- Result: **84/100 wins (84.0%)** — below the ≥90% acceptance threshold
- avg score diff: +19.0 (net comfortably ahead, just not crushingly)
- 105s wallclock total

**Tournament 2 smoke (NeuralMCTS s=20 vs vanilla MCTS s=20, 2 games):**
- Result: **0/2 wins, avg diff -6.5** — strong signal that the full T2 at s=50/s=100 will also fail
- Per-game wallclock: 6.2 min at s=20/s=20; full s=50/s=100 extrapolates to ~28 min/game × 100 games / 2 spawn workers = ~24h. Decided not to burn that compute on a likely-failing run.

**Decision:** instead of running the 24h T2, regen with sharper tau (=0.5) and retry. Rationale:
- T1 result + flat policy training loss + soft heuristic targets all point at the same root cause: the policy head is barely getting trained because the labels don't favor any one action much.
- Tau=0.5 sharpens top-1 mass from ~45% to ~64% (5.5× over uniform vs 1.17× before) — measured empirically on the new data.
- Cost: ~58 min regen + ~17 min train + ~2 min T1 = ~80 min round-trip vs 24h for the unmodified T2.
- The 100K data at tau=10 stays as a control; v2 goes to `data/warmstart/heuristic_tau05/` so the comparison is reproducible.

**Reversal cost:** none — both datasets coexist; v2 is a separate experiment.
**Phase:** Phase 3

---

## 2026-04-28 — Engine bug fix: city_diagonal_top_left_road shared description with shielded variant

**Context:** External reviewer flagged that the wingedsheep tile dict at `engine/wingedsheep/carcassonne/tile_sets/base_deck.py` had `"city_diagonal_top_left_road"` with a description literal of `"city_diagonal_top_left_shield_road"` — same string as the shielded variant 30 lines above. Our `string_representation` keys placed tiles by `(description, outer_edges)`; both tiles have the same outer edges and (after the bug) the same description. MCTS transposition tables would merge two scoring-distinct states (shielded city tile scores +1 per tile in completed city; unshielded does not).

**Fix:**
- Patched the engine description literal to match its dict key.
- Defense-in-depth: extended `_tile_rotation_signature` in `game_wrapper.py` to include `(shield, chapel, flowers)` booleans, so a future upstream description collision still produces distinct state keys.
- Regression test in `tests/test_string_representation.py::test_shielded_and_unshielded_tile_produce_distinct_signatures`.

**Impact on Phase 3 work:** none. Heuristic gen never invokes string_representation (it labels via virtual_score, which reads tile.shield directly). The bug would have bitten an MCTS-labeled gen or any future MCTS use; it didn't corrupt the 100K dataset.

**Reversal cost:** none — strict bug fix.
**Phase:** Phase 3 (engine patch)

---

## 2026-04-28 — Phase 3 production gen sized to 100K, not 500K

**Context:** Original plan (Option D from smoke comparison) committed to 500K heuristic-labeled positions. With the old 40-channel encoding, that was ~3.3 hours of generation. With the new 78-channel encoding (from the prereq fix), per-position generation cost rose ~3× to ~0.35s wallclock per game with 16 workers. 500K = 50K games would now take ~5 hours of pure CPU. 100K (10K games) takes ~50-60 min.

**Decision:** generate 100K positions now. If acceptance fails by a small margin, scale to 250K or 500K incrementally. If it passes, we're done; the additional gain from going to 500K is marginal (logarithmic improvement at most for this regime).

**Reason:**
- 100K is 20× the smoke-comparison sample size (5K). The smoke verdict was decided by a 24.7× wins-per-hour-of-gen advantage; the heuristic-vs-MCTS hypothesis is robustly tested at 20× scale.
- Acceptance criteria (≥90% net-vs-random standalone, >55% NeuralMCTS-s50 vs vanilla-s100) are absolute targets, not relative to dataset size. Either the network learns enough to clear them, or it doesn't.
- Production gen is resumable. If 100K fails by <5pp, we add 100K more without redoing the existing data.
- Risk-adjusted vs. running ahead: a 1-hour gen with bounded compute commitment beats a 5-hour gen-then-fail.

**Reversal cost:** none — incremental scale-up just adds .npz files; the heuristic policy is deterministic per seed.
**Phase:** Phase 3

---

## 2026-04-28 — Phase 3 production prerequisites landed (encoding richness, scalar normalization, streaming trainer)

**Context:** External review (2026-04-28) flagged three blockers before scaling the heuristic warm-start to 500K positions. All three landed in this session.

**Changes:**

1. **Scalar feature normalization** (`src/carcassonne_ai/features.py`):
   - meeples / 7, scores / 100, score_diff / 50, deck size / 85
   - phase one-hots and progress already 0/1 — left untouched
   - Length still 10; only the values changed. Shifts all features into roughly `[-1, 1]` so the dense head doesn't waste capacity learning the magnitude scaling.

2. **Board encoding richness** (`src/carcassonne_ai/board_repr.py`):
   - 40 → 78 channels.
   - Added 6 same-road and 6 same-city pair indicators per cell (12 ch) — distinguishes e.g. straight-road from chapel-with-road, or full-city from two-separate-cities-on-same-tile, even when outer-edge categories coincide.
   - Replaced the 4 cell-level meeple/farmer presence channels with 18 per-side / per-corner channels: 5 sides × 2 owners (NORMAL meeples) + 4 corners × 2 owners (FARMER). A meeple on TOP claiming a city is now distinct from a meeple at CENTER claiming a chapel.
   - Reference-tile broadcast also gets the 12-channel internal-topology block, so the policy head can pick rotations using the tile's connectivity, not just outer edges.
   - Crossroads / three-way-split road gotcha: engine models these as N separate `Connection(outer, CENTER)` entries. Per Carcassonne rules these are SEPARATE road features (they meet at the tile center but are scored independently). The pair encoder unions only outer↔outer connections, so crossroads correctly reports all-zero pair indicators. Test in `tests/test_board_repr_internal.py::test_crossroads_is_four_separate_roads`.
   - Backwards-compat shims: legacy constants `CH_MEEPLE_MINE`/`OPP`/`FARMER_MINE`/`OPP`/`REF_TILE` still exist and point at the first slot of each block, so existing tests pass without rewrites.

3. **Streaming/IterableDataset trainer** (`src/carcassonne_ai/warmstart.py` + `scripts/train_warmstart.py`):
   - `make_streaming_dataset(files)` returns a torch IterableDataset that lazy-loads one .npz at a time. Worker-shards the file list, shuffles file order per epoch via `set_epoch`, optionally shuffles within file.
   - `split_files_train_val(files, val_fraction, seed)` partitions deterministically by FILE (= by GAME); positions never leak across the split.
   - `count_positions(files)` reads only the npz header, no full array load.
   - New `scripts/train_warmstart.py` is the production trainer (default 6×96 net, 4 DataLoader workers). Smoke trainer untouched for tiny-dataset use.

**Tests added (28 new, 108 total now passing):**
- `tests/test_board_repr_internal.py` — 11 tests covering road/city pair encoders for straight/bent/crossroads/three-way/chapel-with-road/full-city/diagonal/separate-cities.
- `tests/test_board_repr_meeples.py` — 3 tests covering per-side, per-corner, and owner-routing semantics.
- `tests/test_warmstart_streaming.py` — 10 tests covering streaming yield count, shapes, DataLoader integration, multi-worker sharding, train/val determinism, set_epoch behavior.

**Removed:** `tests/test_legal_moves_cache.py::test_cache_speedup_on_repeated_state` — perf microbench that turned flaky after the engine adjacency fix made uncached calls cheap (cache benefit shrunk to within system-noise margin). Cache correctness still covered by `test_cache_hits_on_repeated_calls` and `test_cache_returns_same_mask_as_uncached`.

**Reversal cost:** medium — checkpoints from the smoke comparison (40-channel encoding) are now incompatible with the new network input shape. They have to be regenerated. The smoke comparison itself doesn't need redoing — that decided "heuristic over MCTS at 25× cheaper" and the gap is far too wide to flip. Re-running validation is the 100-position smoke described in STATUS.md.

**Phase:** Phase 3

---

## 2026-04-28 — Phase 3 smoke comparison: HEURISTIC wins, scale to 500K (BUT pause for prerequisites first)

**Comparison results:**

| Strategy | Gen time | Net wins/50 vs random | Wins/hour-of-gen |
|---|---|---|---|
| Heuristic (5K, 4×64 net, 20 ep) | ~2 min | 35/50 (70%) | 1050 |
| MCTS s=50 (5K, 4×64 net, 20 ep) | ~55 min | 39/50 (78%) | 42.5 |

MCTS edges out by ~8 percentage points and ~+5 score diff at 5K positions, but takes ~25x longer to generate. Per the smoke decision rule (wins-per-hour-of-generation), **heuristic wins by 24.7x**.

Production plan: 500K heuristic-labeled positions (~200 min generation, then ~30 min train, then evaluate).

**Decision:** Option D (heuristic-only labeling, 500K positions).

**Caveats logged:**
1. The smoke uses a 4×64 net for 20 epochs on 5K positions. The MCTS-labeled signal might shine more with the production 6×96 net + 50K-or-more positions; we can't extrapolate from the smoke alone. If the 500K-D production run fails the 90%-vs-random acceptance, fall back to a smaller MCTS-C run as a contingency.
2. **Production gen is GATED on the prerequisite work** (BACKLOG): board encoding richness, scalar normalization, streaming dataset trainer. Both the heuristic-D and MCTS-C generation share these limitations — a 500K-D run today would waste compute relative to one with proper encoding.

**Reversal cost:** medium — if heuristic-D production run fails acceptance, regenerate via MCTS-C (~26h on the same hardware)
**Phase:** Phase 3

---

## 2026-04-28 — External review findings + bug fixes

**Context:** External agent reviewed Phase 3 code mid-smoke-run. Two bugs surfaced that didn't bite the live work but violated contracts; several "production-blocking" items also flagged.

**Bugs fixed (commit alongside this entry):**
- `Game.get_canonical_form(board, player)` was double-swapping mine/opp channels when `player != current_player`, silently returning current-player perspective instead. `encode_board(state, player, off)` already handles perspective; the conditional `canonical_swap` is wrong. Removed. New regression test `test_canonical_form_for_opponent_actually_flips_perspective` in `tests/test_invariants.py`.
- `warmstart.generate_one_game_dataset` did not seed the global `random` module before `Game.get_init_board()`. The engine shuffles its deck via `random.shuffle` (global), so seeds were not reproducible. Now `random.seed(seed)` runs first; the local `rng = random.Random(seed + 1)` handles our action choices.

**Production-prerequisites flagged for Phase 3 full warm-start (not blocking smoke):**
1. Board representation needs to encode meeple side/corner (currently just "meeple on this tile") and tile internal topology (currently just outer-edge categories). Two tiles with identical edges but different internal connectivity look identical to the network. Estimated +25 channels (~65 total). Half-day fix.
2. Scalar features unnormalized — raw scores 0-100, tiles 0-85, meeples 0-7. Should divide by sensible scales before training. 30 min fix.
3. Trainer loads all data into RAM. 50K positions ≈ 6 GB, 500K ≈ 60 GB — needs streaming/`IterableDataset` over `.npz` files. Few-hour refactor.

**Decisions:**
- Smoke comparison continues unchanged. Both strategies share these flaws, so the C-vs-D verdict stays valid. Bugs fixed mid-flight don't affect already-generated checkpoints (the generation logic doesn't call get_canonical_form, and the seed-reproducibility doesn't matter for unique-trajectory comparison).
- After smoke decides C vs D: PAUSE before scaling up. Land the three prerequisite fixes + a small validation smoke (re-run 100 positions on the new encoding) before committing to the multi-hour production generation.

**Reversal cost:** none for the bug fixes; medium for the prerequisite refactors (would require re-encoding any previously-generated data)
**Phase:** Phase 3

---

## 2026-04-28 — Phase 3 network starting capacity: 6 ResBlocks × 96 filters

**Context:** Need to pick a starting size for the warm-start network. Original prompt said 10–15 ResBlocks, 128 filters. AlphaZero-Chess used 40×256.

**Options considered:**
  - A: 10×128 (~12M params). Original plan default. Comfortably trainable; fits in <500MB on the 5060 Ti.
  - B: **6×96 (~4M params)**. Smaller, faster to train, faster to iterate during debugging.
  - C: 4×64 (~1M params). Likely too small to capture meaningful policy structure.
  - D: 15×128 (~18M params). High end of the prompt's range. Probably overkill.

**Decision:** chose B (6×96).

**Reason:**
- Carcassonne's branching factor (max 96 legal actions) and state complexity are way smaller than chess (~35 legal actions, far simpler scoring). AlphaZero-Chess's 40×256 was sized for a much harder problem; even our prior 10×128 default was likely overkill.
- Phase 5 (the project's actual goal per `docs/ORIGINAL_PROMPT.md`) is a coaching tool, not a superhuman bot. We don't need maximum playing strength — we need a network that's good enough to surface high-value positional analysis.
- Smaller networks train faster, iterate faster during debugging, and are far easier to scale UP (with the same code) than to scale DOWN a broken big-network setup.
- If Phase 3 acceptance fails (network can't beat random ≥90% standalone, or net+MCTS(s=50) doesn't beat vanilla MCTS(s=100) >55%), bump to 10×128. If it overfits 50K positions instantly, shrink to 4×64.

**Reversal cost:** medium — value/policy heads' weights don't transfer if width changes; need full retrain. Cheap relative to a long warm-start run though.
**Phase:** Phase 3

---

## 2026-04-28 — Phase 2 acceptance: MCTS(s=20) wins 96/100 vs random + Q-tiebreak fix

**Result:** MCTS(s=20) defeated random in **96/100 games** (96.0%, avg score diff +30.9, 0 draws, 4 losses). Cleared the prompt's ≥95% acceptance criterion. Per-game results checkpointed to `data/tournament/s0020_seed*_p*.json` for reproducibility.

**Key fix mid-Phase-2:** the original `MCTS.best_action` chose the most-visited child by N. At low simulation budgets (s=10–20 with ~50 root actions), most children have N=1 — the choice between them is essentially arbitrary. Empirical signal: MCTS(s=10) won only ~47% vs random in the first run. Fixed by switching to `argmax_Q` with N as tiebreak; tournament re-ran and trended cleanly to 96%.

**Sims chosen for acceptance:** s=20 not s=100. Reason: per-game wallclock at s=10 was ~28 min; at s=20 ~11 min/game. The 2020 paper's s=100 was for beating Star2.5; for beating random, s=20 is plenty. Phase 4's NN-MCTS replaces vanilla anyway — vanilla MCTS is just a sparring partner here.

**Pre-Phase-3 perf wins (incidentally landed during Phase 2):**
- `get_valid_moves` 49.5ms → 1.75ms (28×) via engine adjacency tracking (`state.open_positions`)
- mid-game MCTS sim 25s → 1.78s (14×) via `apply_action_inplace` (skips deepcopy in rollout-discard path)

**Reversal cost:** none — this is a result, not a decision
**Phase:** Phase 2

---

## 2026-04-27 — Phase 4 prerequisite: get_valid_moves performance strategy (IMPLEMENTED, opt-in)

**Status update:** option A (wrapper-level cache) is now implemented in `src/carcassonne_ai/game_wrapper.py`, opt-in via `Game(enable_legal_moves_cache=True)`. Tests in `tests/test_legal_moves_cache.py` cover correctness, hit-rate stats, clear semantics, read-only protection on cached masks, and a 5x speedup floor. Default is OFF so Phase 1 fuzz tests don't accidentally rely on cache state. Phase 2 MCTS will pass `enable_legal_moves_cache=True` and call `clear_caches()` between root moves. Engine-level adjacency tracking (option B below) remains deferred — only revisit if the cache hit rate proves insufficient.

**Context:** Quick-bench showed `Game.get_valid_moves` at 49.5ms/call. Phase 4 MCTS will call it at every tree node. Estimate: 200 sims × ~70 moves × 100 games per iteration = 1.4M calls × 49.5ms = ~19 hours of pure get_valid_moves work per iteration. The prompt's plan estimated 30-45 min/iteration — this would blow that by ~25x and break Phase 4.

**Root cause:** `TilePositionFinder.possible_playing_positions` (engine) scans every cell of the 35×35 board (1225 cells) × 4 rotations × `TileFitter.fits` per cell = ~4900 fit-checks per call. Most cells are empty interior or empty-far-from-placed, never legal placements.

**Two complementary mitigations (both deferred until Phase 2 done; caching is the priority):**

### A. Wrapper-level legal-move cache (RECOMMENDED — implement before Phase 4)

**Cache key:** the subset of `string_representation` that affects the legal-move set:
- `(placed_tiles_with_orientation_grid, placed_meeples, current_player, phase, next_tile_signature, last_tile_action_coord_or_None)`.
- Excludes scores, deck-remaining-count, opponent meeple pool. Confirmed by reading `ActionUtil.get_possible_actions`, `TilePositionFinder`, and `PossibleMoveFinder`: the legal-move set depends only on those fields.

**Cache scope:** per-MCTS-search. Cleared between root moves. Avoids stale-state bugs without sacrificing hit rate (within one search the same nodes are revisited heavily).

**Invalidation:** none needed inside an MCTS search. Each tree node has a fixed state and we deepcopy on `apply_action`. Verified by `Game.get_next_state`: `copy.deepcopy(state)` before `StateUpdater.apply_action`. No in-place mutations leak across nodes.

**Memory budget:** action mask = 2511 bools = ~316 bytes packed. State key ≈ 300 bytes. ~600 bytes per entry. Max ~50K entries per search × 600 B ≈ 30 MB per worker. With 16 self-play workers: ~500 MB. Trivial on 32 GB.

**Expected speedup:** MCTS revisits a small set of root-vicinity nodes heavily during selection. Hit rate ≥ 90% in steady-state. Effective per-call cost drops from 49.5ms to <1ms (cache hit) + amortized 49.5ms × (1 - hit rate). Net: ~10x for Phase 4.

### B. Engine-level adjacency tracking (OPTIONAL — defer; revisit if cache underperforms)

**Idea:** maintain a `state.open_positions: set[Coordinate]` set updated incrementally on each placement: add the (up to 4) empty neighbors of the just-placed tile, remove the just-placed tile's coordinate. `TilePositionFinder` iterates `state.open_positions` instead of the full 35×35 grid.

**Speedup of cold (cache-miss) calls:** O(35²×4) → O(open_count × 4). Open count is typically 20-80 mid-game → 15-60x faster cold path.

**Effort:** ~1 day. Need to instrument `StateUpdater.apply_action` to maintain the set, verify no other engine path bypasses it, add tests.

**Memory:** negligible (~100 Coordinate objects = a few KB).

**Why deferred:** the cache alone probably suffices for Phase 4. The engine-level fix is a multiplicative improvement on cold-path latency that matters mostly when the cache hit rate is poor. Reassess after the cache lands.

### Combined plan
1. **Phase 2 (next):** implement vanilla MCTS without caching first to validate correctness against the 2020 paper's baseline.
2. **Pre-Phase 4:** add wrapper-level legal-move cache (option A). Re-bench. If <2 min/iteration achieved, ship it.
3. **If still too slow:** add engine-level adjacency tracking (option B).

**Reversal cost:** zero — both are pure-function caches/optimizations
**Phase:** Phase 1 (design); to implement before Phase 4

---

## 2026-04-27 — Phase 1 quick-bench results (per-call cost map)

**Context:** First profiling pass on the wrapper. Numbers from `scripts/bench_quick.py` on idle CPU.

| op | μs/call | note |
|---|---:|---|
| `Game.get_valid_moves` | 49,500 | dominant cost — engine enumerator |
| `Game.get_canonical_form` | 152 | board+scalar tensor build |
| `Game.string_representation` | 208 | repr hash |
| random self-play (1 worker) | 4.95 s/game | single-process baseline |
| random self-play (Pool x16) | 0.70 s/game | 7.11x speedup |
| GPU 4096² fp16 matmul | 2.80 ms | 49 TFLOPS effective |

**Implications:**
- `get_valid_moves` is ~99% of per-game cost. The engine's `ActionUtil.get_possible_actions` walks the 35×35 board scanning for legal placements; for Phase 4 self-play (with MCTS calling get_valid_moves at every node), this is the bottleneck to address. Possible mitigations (in priority order): cache the legal-move set per state hash; restrict the placement scan to tiles adjacent to placed tiles only; rewrite the inner loop in numpy/cython. Defer until Phase 4 confirms it's blocking.
- `get_canonical_form` and `string_representation` are negligible.
- ETA cheat-sheet (Pool x16 random self-play): 100 games ≈ 70s, 1000 games ≈ 12 min, 5000 games ≈ 58 min.

**Reversal cost:** N/A — measurements only
**Phase:** Phase 1

---

## 2026-04-27 — Phase 1 action-space encoding: phase-aware flat (size 2511)

**Context:** The original Phase 1 plan encoded a turn as `(position, rotation, meeple)` jointly into a single flat 38,440-dim action space. While reading the engine for Phase 1 implementation we discovered the engine treats one Carcassonne turn as **two sequential decisions** (`GamePhase.TILES` then `GamePhase.MEEPLES`). The agent never picks all three components simultaneously.

**Options considered:**
  - A: Unified flat encoding parameterized by phase. Tile half is `W*W*4 + 1` (placement + tile-pass). Meeple half is 11 (5 NORMAL sides + 4 FARMER corners + meeple-pass). Total = `W*W*4 + 11 = 2511` for W=25.
  - B: Two separate policy heads, routed by `state.phase`. Cleaner separation but doubles head count and adds plumbing.
  - C: Original 38,440-dim joint encoding. Would have ~95% of indices unreachable at any state.

**Decision:** chose A.

**Reason:** A matches engine reality (the mask is built directly from the engine's `get_possible_actions`), keeps the network output ~16x smaller than the original plan, and a single Coach/Arena training loop works without phase-aware routing. The `getValidMoves` mask zeroes off-phase indices, so training only ever sees same-phase logits as the active region.

**Reversal cost:** medium — the network policy head depends on this size; switching encodings requires retraining
**Phase:** Phase 1

---

## 2026-04-27 — Window size is a Game config parameter, not a hardcoded constant

**Context:** Phase 0 measurements suggested 25×25 fits 99% of random games with margin. But MCTS-driven play (Phase 2) and Phase 4 self-play may sprawl differently, and we don't want a major refactor if 25 turns out to be wrong.

**Options considered:**
  - A: Module-level `WINDOW_SIZE = 25` constant. Simple. Refactor needed if size changes.
  - B: Config parameter on `Game(window_size=25)`, threaded through `WindowOffset(size)`. Minor plumbing increase, but resizing is a one-line change at the call site.
  - C: Re-measure constantly and resize per-game. Overkill; breaks checkpoint compatibility.

**Decision:** chose B.

**Reason:** Joshua's explicit ask. The cost is small (`WindowOffset` already existed; just added a `size` field), and the freedom to re-train with a different window size in Phase 4 is worth more than the saved keystrokes. `DEFAULT_WINDOW_SIZE = 25` is the module default; tests parametrize over `{21, 25, 31}`.

**Reversal cost:** zero — already configurable
**Phase:** Phase 1

---

## 2026-04-27 — Parallel-worker count: use full SMT fan-out (16 on 5800X)

**Context:** Measurement and (later) self-play workers parallelize CPU-bound random-game simulation. Predicted SMT contention would cap useful parallelism at 8 (physical cores). Benchmarked it instead.

**Setup:** `scripts/bench_workers.py` runs 64 random games per pool size on AMD 5800X (8C/16T):

| workers | wall (s) | games/s | speedup |
|--------:|---------:|--------:|--------:|
|       1 |   286.20 |    0.22 |   1.00x |
|       4 |    80.53 |    0.79 |   3.55x |
|       8 |    51.73 |    1.24 |   5.53x |
|      14 |    43.67 |    1.47 |   6.55x |
|      16 |    41.61 |    1.54 |   6.88x |
|      17 |    43.56 |    1.47 |   6.57x |
|      18 |    42.71 |    1.50 |   6.70x |
|      24 |    41.04 |    1.56 |   6.97x |
|      32 |    42.40 |    1.51 |   6.75x |

Oversubscription (>16) was tested explicitly: 17 is slightly *worse* than 16, 18-20 is a wash, 24 wins by 1.4% (within single-run noise), 32 loses. **16 (`os.cpu_count()`) stays as the default** — 24 is at best a noise-level optimization, and going past that actively hurts.

**Decision:** use `os.cpu_count()` (16 logical) for measurement scripts and self-play.

**Reason:** Predicted SMT-sibling ALU contention didn't materialize. The engine is heavily Python-interpreter-bound — much of the per-instruction time is dispatch/GC/refcount overhead, which doesn't fight SMT siblings the way fused-FP code does. Diminishing returns past 8 are real (5.40x → 6.90x for 2x workers) but it's still strictly faster.

**Reversal cost:** zero — single config knob in two files
**Phase:** Phase 0

---

## 2026-04-27 — Phase 0 measurement results (random play only)

**Context:** Phase 0 step 0.7 — empirically measure the bounding-box size of placed tiles and the per-decision legal-action count, to replace the prompt's "31×31 window" and "alpha=0.3" guesses with data. CSVs live in `data/measurements/`.

**Setup:** 1000 random games for board size, 200 random games (33,084 decisions) for action space, both with `[BASE, THE_RIVER]` + `[FARMERS]`, 2 players.

**Board bounding box (1000 games):**
- width: p50=14, p99=20, max=22
- height: p50=15, p99=20, max=23
- longest side: p50=16, p99=21, max=23

**Action space (33,084 decisions):**
- min=1, mean=18.8, p50=4, p90=51, p99=68, max=96

**Implications (will revisit after Phase 2 MCTS measurements):**
- Window size: 25×25 fits 99% of random games with 4-tile margin. Plan default of 31×31 is overprovisioned for random play. **Holding 25×25 as a tentative target but will retry with MCTS games before committing** — MCTS-driven play tends to sprawl more than random.
- Action space max=96 << 500, so flat softmax with hard masking is comfortably tractable. No factored heads needed.
- Dirichlet alpha rule-of-thumb (10 / mean_legal_moves) ≈ 0.53. The prompt's default of 0.3 is in the right ballpark; 0.5 may train slightly faster. Sweep in Phase 4 hyperparameter pre-flight.

**Reversal cost:** measurements are reusable; window choice is parameterized
**Phase:** Phase 0

---

## 2026-04-27 — Vendor upstream repos rather than using git submodules

**Context:** Phase 0 needs to bring in the wingedsheep Carcassonne engine and the suragnair alpha-zero-general framework. The original prompt's setup snippet implied sibling clones with `pip install -e`.

**Options considered:**
  - A: Vendor (clone, drop `.git`, commit our copy). Pros: patches live in our git history; no submodule friction. Cons: drift from upstream; manual rebases if upstream improves.
  - B: Git submodules. Pros: clean provenance; explicit upstream version pinning. Cons: cannot patch the engine without first forking to our own GitHub fork; submodules add friction for solo development.
  - C: Sibling clone + `pip install -e`. Pros: lightest. Cons: patches live in untracked sibling clones — risk of losing them when switching machines or after a clean checkout.

**Decision:** chose A (vendor).

**Reason:** wingedsheep is unmaintained (last release Oct 2021) and we expect to need engine patches (farmer scoring is the most likely problem area). Vendoring puts patches in our own git history. License attribution preserved in `THIRD_PARTY_LICENSES/`.

**Reversal cost:** low (could re-extract to siblings later if needed)
**Phase:** Phase 0

---

## 2026-04-27 — Reward normalization: tanh(diff / 15) — UPDATED from /20 after measurement

**Context:** AlphaZero-General's value head expects values in [-1, 1]. Need to map Carcassonne score differentials onto that range so the value head trains efficiently — too tight saturates, too loose under-utilizes the range.

**Original choice (now superseded):** `tanh(diff / 20)`, reasoned from "typical close games are ±20" — an assumption, not a measurement.

**Empirical data (1000 random games, `scripts/measure_reward_distribution.py`):**

  diff (signed): min=-45, p1=-31, p5=-19, p25=-7, p50=-1, p75=+7, p95=+18, p99=+31, max=+59
  |diff|: mean=9.0, p50=7, p90=19, p95=24, p99=35

  | D | in [-0.9, +0.9] | saturated (>=0.99) |
  |--:|---:|---:|
  | 10 | 81.7% | 3.7% |
  | **15** | **93.7%** | **0.6%** |
  | 20 | 97.5% | 0.1% |
  | 25 | 99.1% | 0.0% |
  | 30 | 99.6% | 0.0% |

The target was ~90% of games in the non-saturated range with headroom. /20 puts 97.5% in non-sat — under-utilizes the [-1, +1] range, weaker gradient than optimal. /15 is the closest fit at 93.7% non-sat / 0.6% saturated.

**Updated decision:** `tanh(diff / 15)`. Code: `SCORE_NORM_SCALE = 15.0` in `src/carcassonne_ai/game_wrapper.py`.

**Forward-looking note — revisit after Phase 3:** trained-bot games will have a tighter score-differential distribution than random games (the bots stop blowing each other out). Anticipate switching `SCORE_NORM_SCALE` from 15 to **10** at that point. The plan:

1. After Phase 3 warm-start, save 1000 self-play games' (score_p0, score_p1, diff) to `data/measurements/phase3_selfplay_diff.csv` (one row per game).
2. Run `python scripts/measure_reward_distribution.py --source csv --csv data/measurements/phase3_selfplay_diff.csv` (the script is parameterized to accept arbitrary CSV input — random play now, network self-play in Phase 3, trained-bot self-play in Phase 4).
3. Pick the new D from the empirical table (target ~90% non-saturated). Likely 10, possibly 8.
4. If D changes by >20%, update `SCORE_NORM_SCALE` and follow the migration plan below.

**Migration plan for D = 15 → 10 (or whatever Phase 3 indicates):**
- **Default: retrain value head from scratch.** The Phase 3 warm-start is supervised learning on heuristic-labeled positions — labels are cheap to regenerate by re-running the heuristic with the new D. Throw away the /15 weights, regenerate labels with the new D, retrain. This is what alpha-zero-general supports natively and is the cleanest path. Cost: a few hours of supervised training on cached positions.
- **Alternative (rejected unless retraining proves expensive):** label transformation — `tanh(diff/10) ≈ tanh(1.5 * atanh(value_at_15))` lets us reuse /15 weights as a warm start. More elegant and saves training time, but introduces approximation error and requires custom code in the training loop. Reject by default; revisit only if Phase 3 retraining turns out to dominate iteration time.

**Reversal cost:** medium (value-head retrain on cached positions; cheap relative to Phase 4 self-play cost)
**Phase:** Phase 1

---

## 2026-04-27 — Window-overflow handling: drop the game

**Context:** Centered sliding window encoding will occasionally have games sprawl past the window dimensions. Need to decide what happens.

**Options considered:**
  - A: Drop the game from training, log warning.
  - B: Dynamic per-move re-centering. Adds a coordinate-translation step to MCTS state hashing — bug risk.
  - C: Grow the window post-hoc on threshold breach. Adds checkpoint-incompatibility risk between training iterations.

**Decision:** chose A.

**Reason:** With window sized at empirical 99th-pct + 4-tile margin, overflow rate should be <1%. Dropping the game is by far the simplest mechanism. We will track overflow count as a metric and revisit if rate exceeds 0.5% in real self-play data.

**Reversal cost:** low (window size is parameterized; can resize and retrain)
**Phase:** Phase 1

---

## 2026-04-27 — Patch wingedsheep engine: ties award full points to all tied players

**Context:** Phase 0 sanity checks revealed that `PointsCollector.get_winning_player` returned `None` whenever multiple players tied for most meeples on a feature. The caller code awarded zero points in that case. This contradicts the official Carcassonne rules ("if tied, all tied players score full points") and is especially load-bearing for our scope because farmer fields are frequently contested.

**Options considered:**
  - A: Patch the engine in place (vendored fork) — rename `get_winning_player` → `get_winning_players` (returns a list), iterate at all 5 call sites, award points to each.
  - B: Wrap the engine and post-process scores. Fragile — callers compute scores in tight loops during state updates and re-deriving the right answer externally is error-prone.
  - C: Live with the buggy behavior. Unacceptable: farmer scoring is the most subtle and most-contested feature; getting it wrong silently corrupts the value-head training signal.

**Decision:** chose A.

**Reason:** Vendoring was justified specifically for this kind of patch. The change is local to `points_collector.py` and verified by a new sanity check (tied 2-tile road → both players score 2 pts).

**Reversal cost:** low (single file diff)
**Phase:** Phase 0

---

## 2026-04-27 — Patch wingedsheep engine: lazy tkinter import

**Context:** `CarcassonneGame.__init__` eagerly instantiated `CarcassonneVisualiser`, which imports tkinter at module load. WSL2 doesn't have python3-tk by default, and headless training never needs the visualiser.

**Options considered:**
  - A: Make visualiser instantiation lazy in `render()`. Existing call sites continue to work.
  - B: Add `python3-tk` as a system-package requirement. Pushes complexity onto every developer/CI machine.
  - C: Strip the visualiser entirely. Loses an occasionally useful debug tool.

**Decision:** chose A.

**Reason:** Smallest patch with no API change. `render()` still works when the user actually calls it (and tkinter is installed).

**Reversal cost:** low
**Phase:** Phase 0

---

## 2026-04-27 — Patch wingedsheep engine: silence print statements behind module flag

**Context:** `points_collector.py` had 15 `print()` calls that fired on every scoring event. At 100 games the noise was acceptable; for 100K+ self-play positions it would dominate stdout and slow training.

**Options considered:**
  - A: Replace prints with a module-level `_log()` that's gated on `CARCASSONNE_VERBOSE` env var (default off).
  - B: Replace with Python `logging` and a custom logger. More flexible but pulls in handler config we don't need.
  - C: Live with the prints and redirect stdout in our scripts. Pollutes test output and other tooling.

**Decision:** chose A.

**Reason:** Minimal change, opt-in verbosity for debugging, no logging-config plumbing.

**Reversal cost:** low
**Phase:** Phase 0

---

## 2026-06-19 — Hybrid-handoff measurement (iter8 early/mid → heur endgame); CL-026

**Context:** L2-3 found iter8 plays the endgame worst; #8 found iter8 −28.7 Elo vs heur@3200. Question: can iter8's early/mid policy combine with deep-heuristic endgame precision?

**Built:** `scripts/level2/eval_hybrid_handoff.py` (+orch SHM, aggregator, autonomous Phase-2 gate `auto_phase2.sh`). Handoff = latched switch to HeuristicMCTS@N at the first own TILES decision with `k_remaining<=K` (k = len(deck)+in-hand; identical to gen_endgame_positions → "K≤2" == L2-3 K=2). Fresh band b340, n=200 paired, shared decks. Measurement only; champion (iter8) unchanged.

**Phase 1 verdict (DONE): endgame weakness is locally PATCHABLE.** All hybrids beat iter8 on paired margin, monotone in K: K2 +0.36/z2.65, K3 +0.25/z1.18, K5 +0.80/z3.45, K8 +1.36/z4.68; K8 reproduced at n=400 (+1.31/z5.61). Compute sanity K5@heur800 +0.60/z2.89 (cheap heur endgame captures most of it). Modest absolute size. results.csv `l2hyb_*`.

**Phase 2 verdict (DONE): gap-closing, NOT a new champion.** hybrid:5 vs heur@3200 −13.9 Elo/pz−0.30, hybrid:8 −19.1 Elo/pz−0.51 (both n=200) — both *lose* to heur@3200 at |z|<1 (tie-to-slight-loss), but clearly better than iter8's −28.7. The early/mid iter8 policy + deep-heuristic endgame closes most of iter8's gap to the deep heuristic without surpassing it. Promotion rule (beat iter8 paired AND beat heur@3200) NOT met → nothing promoted. Phase 1 reproduced at n=400 (K5 margin+0.90/z+6.23, K8 +1.32/z+5.79). Interpretation: "Hybrid ties/loses heur@3200 → deep heuristic remains strongest." Full writeup [measurement/level2/LEVEL2_HYBRID_VERDICT.md](measurement/level2/LEVEL2_HYBRID_VERDICT.md).

**Cluster decision:** pulled the laptop after 2 transient mobile-4070 GPU stalls (carc-orch cmp 2.4ms→3316ms → 60s SHM worker timeout → BrokenServerError → set -e aborted launcher). Local RTX 5060 Ti stable; runs Phase 2 solo. Per-game JSONs cached/resumable.

**Reversal cost:** low (measurement; no production change).
**Phase:** measurement-first


## 2026-06-22 — Heuristic v2.8 leaf branch: meeple-economy term is a real, large heur-leaf gain (measurement)

**Context:** With both strength levers exhausted and the tool/midgame branches closed, the next live branch was "build a stronger heuristic leaf v2.8 via controlled ablations" (classical-engine progress first; ML progress only if neural search can later use/distill/surpass it). v2.7 frozen forever; v2.8 opt-in. Full writeup: [measurement/heuristic_v28/HEURISTIC_V28_REPORT.md](measurement/heuristic_v28/HEURISTIC_V28_REPORT.md).

**Built:** opt-in versioned v2.8 variants (LeafConfig fields, default OFF == bit-identical v2.7, proven 184 tests; HeuristicMCTS `leaf_cfg=` threading). 4 patches from a 678-case failure taxonomy: farm-majority-gate, deck-aware-closure, meeple-economy, opp-denial. Root-action audit (exact K=2 + heur@3200 teacher), mechanistic autopsies (line autopsy + counterfactual), paired full-game heur search pilots.

**Verdict (DONE): ONE survivor — the flat meeple-economy term.** Killed at root audit: farm (broad degradation, cap-masked), denial (no movement). Killed at search: completion/deck-aware-closure (exact-endgame-K2 top-1 0.763->0.826 but NULL full-game +3.5 elo z=1.09 — endgame-local washes out, hybrid-handoff lesson). **Survivor: meeple-economy = +179.5 elo z=9.9 @ heur@200, holds @ heur@800 (+94.9 z=3.8), and v28@200 BEATS v27@800 (+202.6 z=7.0) — quadrupling v2.7's search does NOT close the gap (real leaf-quality gain, not search-imitation).** results.csv `v28_meeple_*`.

**Key correction:** the candidate is BIT-IDENTICAL to the existing legacy `meeple_k=2` knob (verified 560/560), already implemented in object/flat/Cython paths at full speed. **This OVERTURNS the 2026-05-14 "meeple_K null" verdict — that was an n=20 screen (one-sigma noise) and the additive-on-saturating-cap hypothesis was wrong (the term is post-cap).** The recovery-scaling refinement I added DETRACTS (-75 elo) and is excluded. Autopsy mechanism: fixes v2.7 failure-mode #4 (over-committed meeples).

**Decision:** candidate **v2.8 = v2.7 + meeple_k=2** is an EXPERIMENTAL reference (clears 4/5 promotion gates). **NOT promoted to production, NOT a v2.7 replacement, no PRODUCTION.yaml change, no training.** The open decisive gate: does it help the NEURAL policy (iter8 leaf-swap) — deferred to the SHM orchestrator (net-on-CPU infeasible; harness ready). Next: orchestrator neural leaf-swap, k-optimization, out-of-lineage anchor.

**Reversal cost:** low (measurement; no production change).
**Phase:** measurement-first


## 2026-06-22 (cont.) — v2.8 leaf-swap battery: meeple leaf is a CLASSICAL gain, NOT an ML/superhuman lever

**Context:** the heur-search finding (meeple_k=2 = +179 elo vs v2.7) needed the generalization gate — does it help the NEURAL production policy and let it exceed the deep-heuristic ruler? Ran via the carc-orch SHM orchestrator (2-box, local 5060 Ti + laptop 4070, deck-paired, both seats). Full writeup [measurement/heuristic_v28/V28_LEAF_SWAP_REPORT.md](measurement/heuristic_v28/V28_LEAF_SWAP_REPORT.md); rows results.csv `iter8_v28_*` / `hybrid8_*`.

**Results (same net/sims/c_puct/residual 0.25/decks/seats; ONLY leaf differs):**
- iter8+v2.8 vs iter8+v2.7: **+154.5 elo (z=9.82, n=400)** — the meeple leaf helps the NEURAL policy.
- iter8+v2.8 vs heur@3200_v2.7: **+153.4 (z=5.87)** — flips Joshua #8's iter8+v2.7 = −28.7.
- iter8+v2.8 vs heur@3200_**v2.8** (EQUAL leaf): **−38.4 (z=−1.56)** — the disambiguator.
- hybrid:8:800 v2.8 vs v2.7: **+153.4 (z=5.87)** — the hybrid gains too.
- k-sweep (heur@200, flat term): inverted-U, **peak k=2** (+179.5); k1 +75.9, k3 +159.8, k4 +34.9.
- terminal-hoarding (n=60): NO pathology (last-5-plies in-hand 0.26 v2.8 vs 0.05 v2.7, tiny).

**Decision (INTERPRETATION):** The +153.4 vs heur@3200_v2.7 was **entirely the leaf gap** — at EQUAL leaf the neural agent still LOSES to deep heuristic search (−38.4, ~the same relative position as v2.7's −28.7). So the meeple leaf is a **real, large CLASSICAL-ENGINE improvement** that lifts the heuristic, the neural agent, AND the hybrid ~uniformly (+150–180 each over v2.7) — but it is **NOT an ML/superhuman lever**: the learned components still do not exceed the (now stronger) heuristic. **Structural blocker #2 REMAINS.** v2.8 raises the ceiling for everyone; it does not change who is on top. **Positive:** heur@3200_v2.8 is a stronger non-saturated reference ruler (the better measurement anchor the program is gated on). v2.8 = v2.7 + meeple_k=2 → EXPERIMENTAL reference / stronger ruler. **NOT promoted to production, NOT a v2.7 replacement, no PRODUCTION.yaml change, no training; v2.7 frozen.**

**Next lever:** the learned value/policy must EXCEED the v2.8 heuristic (distillation-from-v2.8 or a fundamentally stronger learned value), measured against the heur@3200_v2.8 ruler.

**Ops:** disambiguator hit the shared-claim orphan-stall (laptop mobile-4070 carc-orch BrokenServerError / 60s SHM timeout → set -e abort → 38 stranded claims); recovered per playbook (cleaned stale claims, finished on local). Reinforces feedback_shared_claim_orphan_stall + the laptop-4070 instability note.

**Reversal cost:** low (measurement; no production change).
**Phase:** measurement-first

## 2026-06-23 — Autopsy: RoD v2.8 overnight iter_08 is a NON-TRANSITIVE style point, not a champion (measurement)

**Context:** deep-dive autopsy of the overnight-flywheel keep-best (iter_08, +33/z2.0 over RoD1 but heur@3200_v2.8 PARITY). Goal: where does iter_08 beat RoD1, is it ruler-aligned or RPS, and what's the highest-EV next branch? Constraints held: nothing promoted, PRODUCTION.yaml/champion/v2.7 untouched, v2.8 opt-in. Full report: **[measurement/rod_v28_overnight_flywheel/autopsy/AUTOPSY_RoD_v28_iter08.md](measurement/rod_v28_overnight_flywheel/autopsy/AUTOPSY_RoD_v28_iter08.md)** (+ CSVs/digests in that dir).

**Method:** all from CACHED records + on-disk metadata except ONE new run (iter_08 root choices on the 1000 fixed midgame positions, NeuralMCTS@200 v2.8, identical method to the cached rod/parent labels). Scripts `scripts/rod_v28/autopsy_*.py`.

**FACT — outcome triangle:** iter08>RoD1 (+33.1 wr / +2.23 paired z2.0, n400) but iter08-vs-h3200 (−0.38) ≡ RoD1-vs-h3200 (−0.36): the +33 transfers ZERO to the external ruler. Clean non-transitive cycle (iter08 > RoD1 ≈ h3200 ≈ iter08). The +33 is **concentrated** (top 10% of decks = 132% of net margin; median deck +0.8) = RPS/exploit tail, not broad skill.

**FACT — training space:** value_outcome_corr DRIFTS DOWN parent 0.510 → RoD1 0.413 → chain 0.36–0.49; iter_08 (0.397) is among the chain's LOWEST value-corr + HIGHEST entropy (1.594). Not a value gain, not a sharper policy.

**FACT — root audit (executed, 1000 pos):** iter08≡h3200 0.521 ≈ RoD1 0.511 ≈ parent 0.520. iter08's divergence from RoD1 = net +10 toward the ruler (z+0.7, NOT significant) → orthogonal/style, confirmed at move level. The disagreement LOCALIZES to the endgame (late_mid/pre_endgame agreement 0.445–0.485, iter08 moves AWAY there) — where the ruler is most confident (L2-3 most endgame-precise).

**Decision (INTERPRETATION):** iter_08 = keep-best parent (conditional yes) but NOT a champion; its gain is RPS/style + selection noise, not ruler-aligned improvement. Structural blocker #2 stands. **Highest-EV next branch = exact/endgame-solver hybrid** (the executed audit localizes the learned policy's costliest, most persistent gap to the endgame — the one place an EXACT solver can provably exceed any heuristic; the l2hyb handoffs only tied h3200 because they handed off to another heuristic). Then h6400 as a non-saturated ruler; deprioritize v2.9-leaf and blind RoD continuation. **STOP undirected RoD continuation iters.**

**Reversal cost:** none (measurement/analysis only; no checkpoint, config, or production change).
**Phase:** measurement-first

## 2026-06-24 — Exact endgame-solver hybrid (exact:K): margin scales with depth, winrate does not — COMPLETE

**Context:** the iter_08 autopsy (2026-06-23) localized the learned agents' costliest gap to the endgame and named the exact/endgame-solver hybrid as the highest-EV next branch (the one place an exact solver can provably exceed a heuristic). Built `exact:K:MODE` in `scripts/level2/eval_hybrid_handoff.py` — RoD1 (v2.8) prefix, then a clairvoyant alpha-beta exact solver for the final K tiles (leaf-independent; fair clairvoyant-vs-clairvoyant). Full report: `measurement/exact_endgame_hybrid/EXACT_ENDGAME_HYBRID_REPORT.md`.

**Finding (FACT, deck-paired both seats):** the exact tail adds a real, highly-significant endgame SCORE-MARGIN gain that SCALES ~linearly with exact depth — Δ-margin vs h3200 +0.65 (K=2, n=400) → +1.26 (K=3, n=400) → +1.94 (K=4, n=94); z+4.5/+7.3/+2.8; vs RoD1 +0.65 → +1.42 (n=400). But the WINRATE does NOT follow: deck-paired 0.526/0.537/0.568, NON-SIGNIFICANT at every depth (z≤1.5; empirical margin→winrate slope only ~1.6%/pt). A K=4 n=82 partial's 0.61/z2.09 was deck-selection bias → regressed to 0.568 (the winrate-vs-margin distinction was decisive). Mechanism (regret micro, n=24): h3200's OWN endgame degrades with depth (top-1 0.833 K=2 → 0.667 K=4 = tied with RoD1), so exact's edge compounds. Mechanism (Part E): RoD1's leak is pure last-tile PLACEMENT, not meeple mgmt; h3200 shares 40% of those mistakes. results.csv `exact{2,3,4}_vs_{rod1,heur3200}_v28_*`.

**Decision (INTERPRETATION):** exact endgame play is PROVABLY better than the deep heuristic on score-margin (and more so the deeper you solve) but the superiority is SUB-POINT and OUTCOME-NEUTRAL — it sharpens the ruler, it does not beat it on winrate. NOT a champion and NOT a path to one: confined to the last ~2–4 tiles; blocker #2 (whole-game learned strength > heuristic) stands untouched. Distillation EV low (value-calibration only). **Next: a non-saturated reference (h6400/h12800) + whole-game strength levers, NOT deeper endgame exactness.** STOP at K=4 (K≥5 needs make-unmake/Rust; not worth it — winrate flat at K≤4).

**Infra lesson (memory `reference_exact_solver_eval_infra`):** carc-orch is INCOMPATIBLE with K≥4 (minutes-long solves starve the SHM eval-server → 60s timeout → BrokenServerError → eval crash) → run K≥4 net-on-CPU; net-on-CPU is RAM-BOUND (solver TT ~1–2GB/worker on hard K=4; W=18 OOMed local's 42GB and took the Claude session down — size W ≤ RAM/~2GB).

**Reversal cost:** none (measurement/engineering only; no checkpoint/config/production change; v2.7 frozen, PRODUCTION + champion `flywheel2_champion_iter8` unchanged, v2.8 opt-in).
**Phase:** measurement-first

## 2026-06-25 — v2.9.1 leaf retune: closure-cap is the one lever; Bmild_cap8 BEATS real production v2.8 (measurement)

**Context.** The v2.9 audit found the nonlinear meeple curve (`Bmild`) beats its baseline. Per the bug-fix-shifts-optima rule, changing the meeple economy can shift the OTHER leaf knobs' optima, so we re-tuned them around the Bmild anchor (sequential waves, NOT a grid). **Success bar: beat the Bmild ANCHOR, not merely v2.8.**

**Finding 0 (the mislabel, found mid-retune).** Every prior v29 run measured against the harness `v28` = `DEFAULT_CONFIG`+meeple_k=2, which resolves from env defaults to **cap=5 + 3-open schedule** — NOT documented production (cap=12 + drop-three-open). The comparisons were internally valid (both sides shared the base), but "Bmild beats v2.8" really meant "beats cap5/3-open". Added a `v28prod` harness baseline (real production) for the throne test the audit never ran.

**Retune result (sims=200, paired, 3-box, vs Bmild anchor).** Of four knobs, exactly ONE moved the needle:
- **Wave A meeple-curve SCALE: NULL.** ×0.75 (−37 elo) and ×1.25 (−26) both lose → the curve shape already captured the magnitude (inverted-U peak at ×1.00).
- **Wave B closure CAP: WIN.** cap 5→8 = **+46 elo @ n=400**, even-bucket 0.669 (competitive gain). cap8 beat cap12 on the even-bucket (0.669 vs 0.453 = cap12 over-values fantasy closures, pads blowouts, loses tight games). Flat plateau 8–16; cap8 the pick. The anchor's cap=5 (env default) was simply too low.
- **Wave C closure-P: NULL.** Only flag (p060, higher prob) collapsed 0.557→0.506 @ n=400, even-bucket 0.385 = padding (same trap as cap12). Schedule already well-tuned.
- **Wave D tanh-norm: NULL.** n12 (diff/12) 0.542→0.515 @ n=400 = noise; norm=15 already fine. (Wired a per-instance `HeuristicMCTS.value_norm`, default-preserving.)

**Final v2.9.1 = `Bmild_cap8`** = MILD curve `(-8,-4,-1,0,2,3,4,5)` + cap=8 + 3-open + diff/15 norm.

**THRONE TEST (the one the audit skipped): `Bmild_cap8` vs REAL production `v28prod`.** sims=200 n=400 = **0.579 wr / +55 elo / z+3.94 / even-bucket 0.636** (competitive win, not padding). Depth-robust: survives the sims=800 washout (0.550 / +35 / z+1.84 / even 0.569; mirrors the original Bmild ladder which recovered at h6400). The curve is the bulk of the win; cap8 adds. results.csv `v291_*` rows.

**Decision (INTERPRETATION).** v2.9.1 (`Bmild_cap8`) is a CONFIRMED, depth-robust CLASSICAL-leaf win over actual production v2.8 — promotion-worthy as a candidate. But this is a classical heuristic-vs-heuristic result; whether it helps the NEURAL champion (value head trained against the v2.8 residual base) is UNTESTED and needs the orchestrator + likely a retrain. **h6400 arbiter DEFERRED to promotion-time** (Joshua's call; ~3-5 hr, ~37 min/game under cluster contention). Pre-registered plan + full tables: [measurement/v29_leaf_audit/V29_1_RETUNE_PLAN.md](measurement/v29_leaf_audit/V29_1_RETUNE_PLAN.md).

**Reversal cost:** none (measurement only; no checkpoint/config/production change; v2.7 frozen, PRODUCTION + champion `flywheel2_champion_iter8` unchanged, v2.8 prod, v2.9/v2.9.1 opt-in). 39 tests green; harness commits d1251ae/c21f751/6133739.
**Phase:** measurement-first

## 2026-06-26 — Autopsy: RoD v2 flywheel (v2.9 leaf Bmild_cap8) is a CONFIRMED NULL — decision C (measurement)

**Context.** RoD v2 = the v2.9-leaf redo of the same warm-start self-play flywheel that the v2.8 overnight autopsy (2026-06-23) found stuck at heuristic parity. One change vs that run: the frozen **v2.9 leaf `Bmild_cap8`** (Bmild meeple curve −8,−4,−1,0,2,3,4,5 replaces flat meeple_k; cap 8; 3-open) instead of the v2.8 leaf. Recipe held (batch 256 · 3 ep · VLW 1.5 · residual_scale 0.25 · sims 200 · c_puct 3.0 · 400 games/iter). 5 train iters RoDv2_iter_02..06, warm-from RoD_iter_01, gen+train only. **Question:** does the better classical leaf restart compounding? **Answer: no.**

**Method (cheapest-informative-first; diagnosis only, no new fixes).** Free stages from existing artifacts: F training dynamics (metrics.json), D self-play data distribution (npz), E fixed-ruler odometer (eval tallies). Then ONE gated compute stage — A-lite: a 400-position root-agreement audit (reused `measurement/deeper_search_ruler/multiphase_positions.jsonl`; v2.9 rulers built by hard-setting the v2.9 leaf env so `eval_hybrid_handoff`'s setdefault is inert → DEFAULT_CONFIG=v2.9; runtime-verified bonus_cap=8 + Bmild curve) comparing RoD1/iter04/iter06 policy-prior argmax + NeuralMCTS@200 against h3200_v2.9 and h6400_v2.9. Stage B (value sibling ranking) and Stage C (residual scale) were pre-gated to run ONLY if A contradicted the free read; it confirmed, so they were NOT run.

**Findings.** (F) Training is healthy per-iter but TARGET-LIMITED: train_pol RISES 1.562→1.619 and policy_entropy RISES 1.567→1.609 toward the warmstart baseline (policy diffusing, not sharpening); value_outcome_corr flat ~0.45, train_val flat ~0.007 (value head inert). (D) Later self-play is merely different, not stronger: residual value target std ~0.13 with 38–43% within ±0.02 of 0; policy-target entropy rising 1.494→1.538; margins flat. (E) vs h6400_v2.9 every checkpoint LOSES (RoD1 −32.2 / iter02 −29.6 / iter04 −26.1@n400/z−4.67 / iter06 −22.6) with no significant climb; vs h3200_v2.9 RoD1 +34.9 but iter04 −5.2; iter04−RoD1 SIGN-FLIPS by ruler (+6 vs h6400, −40 vs h3200) = non-transitive; the inter-checkpoint net-vs-net harness deadlocked (unusable). (A-lite) On the h3200≠h6400 disagreement subset (n=111), prior lean toward h6400 = RoD1 −0.009 → iter04 −0.063 → iter06 −0.027 (Δ −0.018 vs ±0.095 noise) = NO movement toward h6400; the prior picks NEITHER ruler's move 77.5% of the time (DIFFUSE, not h3200-like); NeuralMCTS@200 recovers agreement to ~0.5 but stays h6400≈h3200-equidistant; endgame agreement collapses to 0.10–0.13 and the lean goes negative there.

**Verdict.** RoD2's playing strength is carried by the **v2.9 leaf inside the MCTS, not by the learned net** (diffuse prior + inert value head). No source of supra-heuristic signal — value target = residual-around-the-leaf with no dynamic range; policy target = heuristic-MCTS visits, which cannot exceed the heuristic. Reproduces the v2.8 flywheel autopsy signature exactly; the v2.9 leaf swap changed nothing. Blocker #2 (learned must EXCEED the hand-crafted leaf) stands. **Ranked failure modes:** (1) no source of supra-heuristic signal [root cause, ~0.9]; (2) value head inert [~0.85]; (3) data drifting not climbing [~0.85]; (4) policy not moving toward h6400 [~0.85]; (5) parent/adjacent wins don't transfer [confirmed]; (6) only compresses ~h3200-level search [~0.8]; (7) tether too strong [~0.15, unlikely].

**Decision: C — stop the AlphaZero-style blind flywheel; classical v2.9 is the strength of record.** Continuing (A) won't break blocker #2; a single-component change (B) isn't justified by this autopsy (the failure is joint). The only direction with an EV thesis is D-flavored (the gap localizes to the endgame → an exact/endgame-solver or supra-heuristic-teacher signal, as a SEPARATE project) — named as the decision boundary, **not proposed or started here** (governance: no new branches/curriculum/tools in this autopsy). MEASUREMENT ONLY — no promotion; PRODUCTION.yaml + champion (`flywheel2_champion_iter8`) + v2.7 frozen UNCHANGED; v2.9 stays opt-in/experimental. Deliverables `measurement/rod_v2_flywheel/autopsy/` (ROD2_AUTOPSY_REPORT + TRAINING_DYNAMICS + DATA_DISTRIBUTION + NONTRANSITIVITY + POLICY_ROOT_AUDIT); scripts `scripts/rod_v2/autopsy/{stage_a_lite,phase_breakdown}.py`; results.csv `rodv2_*_vs_heur*_v29`; lineage `rod_v2_iter_06` (NOT_CHAMPION); CL-029; commits 9e15e28/b6ce55f/6a135d5. Precedent `measurement/rod_v28_overnight_flywheel/autopsy/AUTOPSY_RoD_v28_iter08.md`.

## 2026-06-26 — Hard-position policy repair (follow-on to the RoD2 autopsy): decision A — the target is signal-free on disagreement states

**Question (Joshua-directed, narrow):** can explicit h6400-labeled hard-position exposure repair the RoD2 policy failure (diffuse, no movement toward h6400 on `h3200≠h6400` disagreement states)? Built as a single diagnostic repair test, NOT a new flywheel.

**Answer: NO — decision A, with a sharper mechanism than the literal outcome.** Pilot on the fixed 1620-root multiphase pool (no generation), labeled with v2.9 rulers h3200(classify)+h6400(deep teacher): 438 hard (disagreement = 27%), split 306/66/66 hard + 1182 ordinary.

- **Stage 2 baseline** reproduces the autopsy on an independent held-out set (lean≈0, P_neither≈0.80, endgame top1 0.00–0.05) → the metric harness is validated.
- **The pivot (load-bearing):** on disagreement states the h6400 visit distribution is ~uniform (top-move share 0.04; `best_action` ranks by **Q**, not visits) and the **Q-gap between the #1 and #2 move is 0.0021 (median 0.0007) vs 0.040 on ordinary states** — ~20× smaller; only 3% of hard states have a gap >0.02. Two search depths disagree on a position precisely when its top moves are value-near-equal. So **'h3200≠h6400 disagreement' selects VALUE-INDIFFERENT states, not deep-distinctive ones**, and the deep teacher's 'best move' there is a near-coin-flip argmax — there is no generalizable signal to learn.
- **Stage 3/4 (policy-only fine-tune from iter04, `--aux-weight 0 --value-loss-weight 0`):** the soft (visit) target leaves the held-out metric unmoved (top1 0.091→0.076, lean ≈0); the one-hot (h6400 argmax) target — given an aggressive fit — **memorizes the training argmax to top1 0.775 but generalizes to 0.061 on held-out** (below the 0.091 baseline). Full capacity, zero transferable signal → **a SIGNAL problem, not capacity or training.**
- **Stage 5:** the same nets agree with h6400 **3.4× more** on ordinary (decisive, Q-gap 0.040) states than on hard (indifferent) ones (top1 0.311 vs 0.091) — the policy is already aligned with the teacher wherever the teacher is decisive; the fine-tunes mildly degraded ordinary alignment (forgetting), no collapse.

**Reframe of the autopsy (does NOT overturn decision C):** the RoD2 autopsy's headline 'diffuse policy on disagreement states' (Stage A-lite) was **measuring a non-failure** — a diffuse policy is the *correct* response to value-indifferent positions. This **downweights** that supporting mode as evidence of a learnable failure but leaves the binding constraint (blocker #2: the learned value cannot exceed the v2.9 leaf) untouched. The bottleneck is the value/eval ceiling, not policy diffuseness.

**Named boundary (NOT pursued — governance: no new branches/curriculum/tools mid-experiment):** IF policy distillation is ever revisited, define 'hard' by **decision-relevance (h6400 root Q-gap)**, not by argmax disagreement. Genuinely deep-distinctive states (large Q-gap where shallow search errs) are a different, much rarer set (~3% of the disagreement pool) and whether the policy fails *there* is open and untested — a separate experiment, named here, not started.

P2 (ordinary mix) / P3 (from-RoD1) / Stage-6 games NOT run (gated; same signal-free target). No `results.csv` row (policy-agreement diagnostic, not an elo/wr experiment). MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion (`flywheel2_champion_iter8`) + v2.7 frozen + v2.9 evaluator UNCHANGED. Evidence `measurement/hard_policy_repair/HARD_POLICY_REPAIR_{PLAN,RESULTS,DECISION}.md`; scripts `scripts/rod_v2/repair/`; CL-030; lineage `rod_iter04_hardrepair` (NOT_CHAMPION); commits `319cd98`/`a099073`.

---

## 2026-06-26 — HIGH-CONTRAST DECISION-SIGNAL DISTILLATION (Path 3) — decision B (signal learnable, does not convert; bottleneck is value/search)

The follow-on that pursued the hard-policy-repair **named boundary**: define "hard" by h6400
**Q-gap / regret** (decision-relevance), not argmax disagreement. Net-free labeling of a fresh
20160-root multiphase pool with h6400_v2.9, **sharded local + laptop** (the laptop bundle-synced to
the same commit + a cross-leg density check — 36.6% vs 38.0% at gap≥0.02 — confirmed bit-exact, no
stale-code contamination). Soft **Q-softmax** targets (advantage-based, peaked ∝ the gap), policy-only
fine-tune of `iter04` with a decisive-state stabiliser mix (R1 70/30, R2 50/50). Cheapest-informative
discipline throughout: density gate on the existing 1616-pool first, then a pilot-train, then the scale-up.

**Verdict (decision B): the high-contrast signal EXISTS, is LEARNABLE, and GENERALISES — but it does
NOT convert through search to strength. The bottleneck is value/search, not policy exposure.**

- **Gate (Stage 2) — PASS, abundant.** Across the pool: gap≥0.02 = 37%, gap≥0.02∧iter04-wrong = 22%,
  regret≥0.02 = 43%, phase-balanced (~20–24% every phase incl. endgame). This **inverts** the prior
  experiment's disagreement-only 3% — selecting by gap (not disagreement) finds dense, decisive,
  student-wrong states.
- **Stage 5 (held-out hard TEST n=1390, game-disjoint) — learns + generalises.** Prior top1 **0→0.18**,
  top3 0.30→0.42, mean regret −27%, median −42%, strong-gap top1 0→0.27, **endgame 0→0.17**. The soft
  Q-softmax target transferred where the prior experiment's one-hot did not; the scale-up turned the
  pilot's ambiguous +8pp into an unambiguous +18pp at 14× the test size. Ordinary regression modest
  (R2 top1 1.0→0.95).
- **Stage 5b NMCTS@200 — WASHOUT.** iter04's prior is wrong on every hard state (top1 0.000) yet its
  NMCTS@200 already reaches **0.497**; R2 also **0.497** (R1 0.453). The prior improvement is
  **redundant at the root** under production search — search already extracts the decision move. Only
  the **endgame** subset moves (R2 0.552 vs iter04 0.483), the autopsy's collapse region.
- **Stage 6 games (R2 vs h6400_v2.9, n=126 paired, local+laptop, sims=200 c=3.0 rs=0.25) — NO
  conversion, if anything harmful.** WR **0.409 / elo −64 / paired −11.7**, *below* the iter04 baseline
  (0.463) it was fine-tuned from. The redundant-at-root prior gain is bought at a broad-distribution
  cost (ordinary −5pp) that search does **not** wash out in full play.

**Mechanism / why it matters:** at production depth, search backs up the value through the existing
prior and recovers the decision-relevant move from a *bad* prior — so improving the prior adds nothing
at the root, while perturbing the whole policy distribution costs real strength. This **sharpens RoD2
autopsy blocker #2**: the learned **policy** is not the binding component (already adequate for search);
the binding constraint is the learned **value / the search**. **Policy distillation (any target) is a
dead end for RoD strength** — the prior experiment failed for *no signal* (indifferent states), this
one fails for *signal-but-redundant-under-search*. **Named boundary (NOT pursued):** the real next
lever is value/search; or, at most, an endgame-restricted distillation that must itself clear a game
screen. No RoD3 / new flywheel / curriculum / tools / aux-head proposed.

MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion (`flywheel2_champion_iter8`) + v2.7 frozen +
v2.9 evaluator UNCHANGED. Evidence `measurement/high_gap_distillation/HIGH_GAP_{PLAN,SIGNAL_DENSITY,
DATASET,TRAINING,RESULTS,DECISION}.md`; scripts `scripts/rod_v2/highgap/`; results.csv
`highgap_R2_vs_heur6400_v29_n126`; CL-031; lineage `highgap_R2_from_iter04` (NOT_CHAMPION); commits
`cbb40fc`/`edbf514`.

## 2026-06-27 — Value/Search Conversion Autopsy (follow-on to Path-3 decision B): decision D (value inert) + "root metrics don't convert to game strength" (measurement)

**Context.** Path-3 (decision B) proved the high-gap POLICY signal is learnable but non-converting and named the bottleneck as "value/search, not policy exposure." This autopsy localized it. Built a **1321-miss diagnostic set** (the gap≥0.02 decision-relevant roots where iter04 NMCTS@200 misses h6400, out of 4277) and a **9-leg root intervention matrix** run net-on-CPU local+laptop: I0 baseline · I1 sims 400/800 · I2 teacher-prior injection · I3 flat (uniform) prior · I4 residual 0/0.5 · I5 classical HeuristicMCTS@200/800 · I6 forced-move child eval · I7 endgame slice. Scripts `scripts/rod_v2/value_search/{miss_harness,forced_move,classical_leg,agg_miss}.py`.

**Root-level findings (rigorous, but the seductive-and-misleading part).** (1) **Neural VALUE is inert** — rs0/rs0.25/rs0.5 indistinguishable (miss-set top1 0.365/0.350/0.357), and the residual NEVER corrupts the leaf ranking (I6: 107 wrong→right, 0 right→wrong at 1-ply). Kills decision C (value-corrupts) and the value half of D's opposite. (2) **The policy PRIOR makes worse decisions than bare classical search on decision states.** Full-pool (n=4277, same states, un-confounded) agreement with h6400: **classical h200 0.911 > flat-prior neural 0.867 > production neural 0.799** — monotone; flattening the net's OWN prior gains +6.8pp / −45% regret, dropping the net for classical +11.2pp / −63%. (3) **Mechanism:** 88% of misses are explored-but-mis-ranked (not unexplored); `best_action` ranks by backed-up search Q, and the over-confident prior concentrates visits → the right move's subtree is under-searched → its backed-up Q is wrong. Uniform/UCB exploration lets the value-blind leaf's AGGREGATE Q rank correctly (I6: static leaf ranks the teacher child correctly only 22% at 1-ply, 9% in endgame — but deep broad search recovers 79–81%). More neural sims overcomes the bad prior only slowly (miss-set top1 0.350→0.457→0.553 at 200→400→800; classical is 0.815 at 200).

**Game-level finding (THE CORRECTION).** The root edge does **NOT convert.** Stage-5 game screen — classical HeuristicMCTS@200 vs neural iter04@200, head-to-head at MATCHED compute, v2.9 leaf, paired, net-on-CPU 2-box, **n=96 (48 paired decks)**: classical **WR 0.438 (42W/1D/53L), mean score margin −2.6, paired-z −1.19 = NOT significant, a slight lean toward NEURAL.** So despite agreeing with h6400 +11pp MORE at decision roots, classical is ~even with (if anything below) neural in games. The decision-state errors WASH OUT because the vast majority of game positions are low-gap, where the net prior is fine and more efficient than uniform UCB. The net is **game-NEUTRAL vs classical, not game-harmful.**

**Verdict — decision D + non-conversion; NOT F.** The neural **value head is irrelevant (D)**; the policy prior is over-confident at the root (A is real there) but **game-neutral**; classical is better at decision-roots but NOT in games (refutes the strong F). **Headline (methodological):** root/decision-state agreement-with-a-deeper-teacher is NOT a proxy for head-to-head strength — this is the THIRD independent instance (Path-3 held-out-prior washout, the sims-washout, now this) ⇒ **gate strength claims on GAMES, never on root/policy metrics.** Binding constraint for game/superhuman strength stays **search depth + a value head that beats the v2.9 leaf** (blocker #2, still open; this autopsy confirms the current value is inert). **NOT pursued / for review:** a value head that beats the leaf (gate on a game screen vs deep search, never root MSE/rank) is the single highest-value lever; prior-tempering is DEPRIORITIZED (fixes a non-converting metric); policy distillation stays a dead end. results.csv `valsearch_m1_classical_h200_vs_neural_iter04_n96`; CL-032. **MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED.** INFRA: net-on-CPU full games are ~5min each (200 fwd/ply on CPU); W30 oversubscribes a 16-core box for CPU-bound forwards (W=cores is optimal) — the rust orchestrator is the right tool for neural games (deferred here, diagnosis was already decisive at the root). Laptop swap-died from orphaned spawn-workers (killing an mp main doesn't reap them; their cmdline is `multiprocessing.spawn`, invisible to `pkill -f <script>`) → rebooted via Windows `ssh laptop 'shutdown /r'` (autologin WSL-KeepAlive self-recovers); kill spawn-pools by exact pid.

## 2026-06-28 — Value Resurrection Pilot (follow-on to CL-021 / CL-032): decision B — learned value/ranking still cannot beat the v2.9 leaf at sibling child-state ordering (measurement)

**Decision B.** Asked the narrow question the value head actually needs to pass — can a learned value/ranking *out-rank the v2.9 leaf on held-out sibling child states* (not predict game outcome)? **No.** Reused existing h6400_v2.9 labels (`qprobe_A ∩ pool_A` = 10,067 sibling sets, 0 checksum errors, `replay_to` reconstruction) → the whole offline gate cost **zero cluster** (local CPU + 1 GPU). **Stage 3 (leaf audit, gate 1 PASS):** the v2.9 leaf already ranks siblings at **τ=0.895 / top1 0.455** vs h6400, but mis-ranks a real tail (~1,197 decisive sets, gap≥0.02 & regret≥0.02) → a target exists (not decision A). **Stage 5 (offline gate, FAIL → STOP):** V4 listwise / V2 advantage / V1 residual-regression (policy frozen; 124,842-row dataset; leaf~oracle corr **0.995**) all fail — the combined ranker `leaf + α·learned` picks **best α=0** (zero weight on the net) for every variant, regret rises monotonically with α, and the **endgame is no exception** (refutes decision F — the leaf is *strongest* in the endgame, τ 0.94). net-alone τ peaked **0.105** (residual variant **0.005**) vs leaf 0.895 — reproduces **CL-021** (+0.029) against the stronger v2.9 leaf + deeper h6400 teacher. No NMCTS, no games, no orch. **Side-finding:** `forced_move.py` / b99c9ed **I6 has a POV sign-flip** on same-player TILES roots (1816/1816 children keep the mover) — evaluating from the fixed root seat flips leaf~teacher correlation −0.90 → +0.90, implying I6's "leaf value-blind ~91% endgame" was inverted (the leaf ranks the teacher child *correctly* far more often) → reinforces decisions D and B; flagged for a correction pass. **MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED.** CL-033; docs `measurement/value_resurrection_pilot/`; scripts `scripts/rod_v2/value_resurrection/`.

## 2026-06-28 — Feature-Graph Action Comparator Pilot (follow-on to CL-033): decision C — explicit feature/action representation BEATS the v2.9 leaf OFFLINE (representation, not reweighting) but the win WASHES OUT under search (measurement)

**Decision C.** The dead value pilots (CL-021/032/033) all varied training target/architecture but held the *representation* fixed (CNN board encoding → scalar value head). This pilot varied the one axis they never did: an **action-conditioned, sibling-relative learned object** over **50 handcrafted feature/action/delta scalars** (from `decompose` / `decompose_v29` — leaf components, contested control, open-edge exposure, meeple lockup/return, completed value, move semantics; no engine change). Reused the same 10,067 h6400_v2.9 sibling sets → a 314,911-child feature dataset with **bit-identical** enumeration to CL-033 (built-in audit reproduced τ=0.8951 / top1=0.4553 / 1197 decisive **exactly**; leaf_q bit-exact) → **zero cluster**. **Stage 4 (offline gate, PASS — the FIRST learned ranker to clear the static v2.9 leaf):** a cheap **linear** model beats the leaf at held-out sibling regret — full-pool **−41%** (0.0289→0.0171), top1 0.464→0.535, and the **ordinary subset also improves** (no broad regression); decisive tail **−44%** (linear) to **−52%** (listwise). The win is **REPRESENTATION, not reweighting**: Tier-1 (the leaf's OWN components, reweighted) buys only −13% on the tail; the Tier-2 explicit structure drives the rest — **reversing CL-033's best-α=0** (VR's CNN value head ≈ our Tier-1). Robust: no label leak (max single-feature corr 0.996 = `leaf_q` itself; label columns not in `feat`), and negative controls (shuffled-label refits) collapse **below** the leaf. → **Answers the open question from CL-032/033:** the scalar head was dead for lack of explicit Carcassonne feature/action **structure**, NOT because learned value is hopeless. **Stage 5 (search screen, FAIL → STOP):** 596 held-out roots at HeuristicMCTS(200), four narrow integrations (small-α leaf blend, top-k, decisive-tail gating, post-search rerank) — **none beats `search_leaf` on decisive-tail regret, and every α>0 regresses ordinary play.** MECHANISM = **washout**: search alone collapses the static leaf's decisive regret 0.122→0.019 (6×, decisive top1→0.79) and at sims=200 explores **every** sibling (`teacher_explored_frac=1.0`), so the offline comparator (decisive regret 0.075) is *behind* search, not ahead; the blend fixes only **3/41** explored-but-misranked decisive roots, breaking as many. The offline sibling-ranking metric was a **screen** and the screened win does not convert through search — **b99c9ed in clean, pre-registered form. SHARPENS blocker #2:** a learned component must beat what **search** extracts, not what the **static leaf** misses; better static sibling ranking is not the strength lever. No games run (gated out), no graph-architecture escalation justified (bottleneck is redundancy-with-search, not capacity), no flywheel. BACKLOG-only, NOT pursued: the washout is sims-dependent → the only conceivable use is search **efficiency** (priors/ordering to reach the same quality at fewer sims), a compute play, not strength. **MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED.** CL-034; docs `measurement/feature_graph_comparator/`; scripts `scripts/feature_graph/`.

## 2026-06-28 — Post-Search Residual / Adaptive-Compute Pilot (follow-on to CL-034): decision C — the residual that survives shallow search is predictable and an oracle beats uniform compute decisively, but a one-line heuristic captures it and the magnitude is too small to convert (measurement)

**Decision C.** Takes the CL-034 mechanism ("a learned component must beat what SEARCH extracts, not what the STATIC leaf misses") to its conclusion by retargeting from `h6400 − static_leaf` to **`h6400 − h200_search`** — the residual error that *survives* shallow search — and asking the adaptive-compute question: *can we predict where h200 is still materially wrong vs h6400, to escalate deep search ONLY there and beat uniform compute at matched average sims?* Built the dataset two ways: Phase A 3000 greedy roots + **Phase B 12,000 REAL MCTS-play roots** (new lossless reconstruction: record each HeuristicMCTS(200,v2.9) self-play game's deck-seed + action-sequence, replay to any ply — `recon_ok` verified; one HeuristicMCTS(**6400**) search per root **snapshotted** at {200,400,800,1600,3200,6400}, bit-exact to a standalone h_L since MCTS is incremental → all uniform levels + the h6400 reference from ONE search, ~6× cheaper). Frozen v2.9 leaf (`7fc930b82801cb43`) throughout; **net-free, zero cluster, zero metered spend.** **Stage 2 (oracle gate, PASS on BOTH distributions):** a perfect oracle (route each root to the cheapest depth) beats uniform search at matched avg-compute **+92.5% @ C=400** on MCTS roots (greedy +88.6%/+96%). The residual is **extreme-tail-concentrated** — the worst **5%** of roots hold **67%** of all h200 regret, worst 20% hold 99%; median regret(h200)=**0**, mean **0.0031** tanh-Q, h200 agrees with h6400's top move **71%**; positive_strong **2.8%**, phase-concentrated in the **opening**. So the opportunity is real and the ceiling is high. **Stage 3+4 (offline adaptive gate → decision C):** trained escalation predictors held-out **by game** on h200-visible features (NO h6400 leak). The signal **IS predictable** — best model = MLP over h200 diagnostics + 21 Tier-B structural features (`decompose`/`decompose_v29`): **AUROC(positive_strong)=0.78**, robustly beats uniform at matched compute (bootstrap **P=1.00 @C=400**). **BUT a single one-line heuristic — `low_top2gap` (escalate when h200's top-2 backed-up Q are nearly tied) — captures essentially all of it** (AUROC 0.73), and the learned model does **NOT robustly beat it**: bootstrap P(MLP beats heuristic) = **0.92 @C=400** (Δ +0.00023, 95% CI **[−0.00009, +0.00059] crosses 0**) and **0.54 @C=800**. Tier-A (no structural feats) was clearer still — the heuristic *beat* every learned model. **→ Decision C: predictable offline, but a trivial rule suffices; ML adds no robust value; no ML scheduler, no flywheel.** Compounding caveat — **magnitudes are tiny**: mean regret 0.0031, oracle ceiling removes only ~0.0016, the achievable (heuristic/learned) slice ~0.0003–0.0006 → far below game-resolution; **game-conversion doubtful — the b99c9ed "root metrics don't convert" pattern, now its 4th instance** (sims-washout, value/search autopsy, feature-graph, here). Stages 5–6 gated out (**no games, no cluster, no spend**). The roots where shallow search is wrong are simply where h200 itself reports a near-tie — no board understanding needed. **BACKLOG (not pursued):** a *heuristic* (not ML) escalation scheduler as a possible compute-**efficiency** tool (same strength at fewer average sims), gated on a large-n paired game screen; **not** a strength lever. **MEASUREMENT ONLY — no promotion, PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED.** CL-035; docs `measurement/post_search_residual/`; scripts `scripts/post_search_residual/`.

## 2026-06-29 — Feature-Graph Search-Residual Architecture Pilot (follow-on to CL-035): decision B — a Carcassonne-native feature-graph / GNN does NOT learn the post-search residual better than flat scalars; beats neither the scalar MLP nor low_top2gap; graph structure is INERT (measurement)

**Decision B.** The first serious attempt to *redesign* the learned object after the RoD/value/policy/comparator lines closed: instead of a board-tensor CNN or flat scalars, build a **typed feature graph of actual Carcassonne objects** (cities/roads/farms/monasteries/meeples/players/deck + legal-action nodes, 8 node + 8 edge types) and train it against the **post-search residual `h6400 − h200`** (CL-035's target) — asking the one question that would reopen the flywheel: *can a relational model beat what shallow search already extracts?* **Stage 0–0.5 (feasibility, PASS):** `flat_leaf.decompose` already enumerates every city/road/farm component as a union-find root with attributes (finished, open-edge count, tile coords, closure delta, farm→city adjacency) → the graph is ~95% read-offs, ~67 ms/root, 0 errors; the structurally-blind slice (~20% of the decisive tail has `leaf_q_gap≈0` — only deep search separates those children) was surfaced here. **Stage 2 (dataset, net-free, zero cluster):** reused CL-035's 10,351 MCTS-play roots (all {200…6400} Q levels already stored) + extended the replay pass with the graph + the CL-034 50-scalar per-action features → 168,567 action rows + `graphs.pkl`; leakage-safe seed-split 270/64/66; labels derived from stored q200/q6400 (not baked). **Stage 3 (baselines reproduced):** B3 `low_top2gap` AUROC(pos_strong) **0.725**, B5 flat-MLP **0.78**, oracle ceiling ~0.0016 tanh-Q removed @C=400. **Stage 4–6 (the critical offline gate, FAIL → STOP):** two models each with a G3 escalation head + a G4 reranker head — **G0** graph-lite MLP (50 action scalars + diagnostics + Tier-B, 60K params) and **G1** typed message-passing GNN (969K params). *Methodology guard:* G1's first run looked null but was **underfit** (best_epoch=1, train AUROC 0.62 < the 60K MLP's 0.73); after a real fix (lower/scheduled LR, less-noisy `pos_medium` early-stop, balanced 2574-root subsample, per-epoch logging) G1 **fit train to 0.68–0.92 yet still generalized to test AUROC 0.559** — a *fair* null. **Results (TEST=1672, 2000-resample bootstrap):** G3 — G0 AUROC 0.660 / G1 **0.559**, both *below* B3 (0.725) and B5 (0.78); P(beats B3)=0.05–0.34 (need ≥0.95), max matched-compute regret reduction vs B3 = **−100%** (worse). G4 — decisive-tail (46 roots) regret 0.04582→0.037 (G0) / 0.036 (G1), P(reduction>0)=0.94/0.92 (below 0.95) **AND `ordinary_no_regression=False`** (the first full-pool run regressed ordinary play 0.00164→0.0086, 5×) → not a win. **Graph-ablation (decisive):** zeroing G1's graph embedding *lowers* its G4 tail regret (0.03602→0.03324, Δ−0.00278) → **the relational structure is INERT**; whatever marginal effect exists comes from the action scalars, not message passing. **→ Decision B, NOT C** (C would require beating *simple features* offline — G1 is *worse* than both flat models) and **NOT F/H** (gate failed → no search integration, no games, per spec). Root cause is not a fluke: the signal is thin (287 pos_strong train), ~20% structurally blind, a flat MLP already extracts what's extractable (0.78), and the magnitude is below game-resolution (oracle ~0.0016, achievable ~0.0003–0.0006) — exactly CL-035's prior. **Consolation (G-flavor):** the feature graph + ablation harness are useful **evaluator archaeology** (localizing the residual: opening-heavy, low-top2gap, static-invisible) and remain available if a much larger teacher/architecture change ever revisits — but the feature-graph is **not a live search/scheduler module**. No games (gated out → no results.csv row), no promotion. **MEASUREMENT ONLY — PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED; learned-flywheel line stays CLOSED.** CL-036; docs `measurement/feature_graph_search_residual/`; scripts `scripts/feature_graph_search_residual/`.

## 2026-06-30 — Step-2 PeNS Weaned-Value-Leaf Flywheel → genuine GATE-B (CL-038); §10 decision: value can RANK but can't DRIVE search → ship the analyzer (endgame-2) (strength/flywheel)

**Verdict.** The Step-2 PeNS program (a sighted 89-scalar value substrate + a regime that weans the v2.9 heuristic OUT of the MCTS leaf and the learned value IN, gated on games) reached its pre-registered conclusion: **genuine Gate-B.** The learned value head — even on the representation that passed Step-1 Gate A (CL-037: farm-connectivity planes + bag histogram FLIP CL-033's α=0; the value genuinely ranks) — **cannot drive the MCTS leaf better than the v2.9 heuristic.** Weaning/adding it craters play vs RoD2 iter02 across all three objectives: **MSE 0.525→0.212, ranking 0.453→0.287, frozen 0.355→0.215** (all @ blend 0.27, paired, n=100–172).

**Three nails (ruling out every recoverable alternative).**
1. **interior-τ HOLDS flat across search-tree depth** (d1 0.42 / d2-3 0.45 / d4-7 0.43; n=4156/9126/1327) → the value ranks DEEP interior nodes as well as shallow roots → NOT an F-B2 train/serve distribution mismatch. (Refutes the external reviewer's recoverable reading: the in-loop τ was depth-1-only, but the value is not deep-specifically-broken.)
2. **ADDITIVE leaf** (heuristic at FULL weight + value added, clip(h+0.27·v)) craters 0.500→0.285 vs the pure-h anchor (0.500 exact) → it's the value ADDITION that hurts, NOT the heuristic subtraction (the convex down-weighting adds only a secondary hit, 0.285→0.195).
3. **FROZEN warmstart value** (the +43% offline winner, NEVER retrained) craters 0.215 (z−7.47) ≈ MSE 0.212 → freezing the value doesn't rescue it → NOT retraining-drift.

**Why §10 "(a) passes, (b) fails", not "abandon all AZ".** Step-1 PASSED (the value CAN rank — α>0, τ~0.43 every depth, +43% offline). Step-2 FAILED (weaning it into the leaf craters in games). §10's own words for this branch: *"value can rank but can't drive search — keep the analyzer, representation was the issue."* The value head is a proven EVALUATOR → the **analyzer (endgame-2, the original Phase-5 win condition)** is the pre-registered fallback, now with a sighted evaluator.

**SCOPED — NOT "superhuman is impossible".** Gate-B closes the **weaned-learned-value-LEAF** lever (learned value driving the MCTS leaf). It does NOT foreclose other approaches. Program continues — fresh approaches pending (new thread).

**The verdict survived heavy scrutiny.** An external review caught that the in-loop τ was depth-1-only (→ the interior-τ probe, nail 1). A 3-round code-review loop found+fixed 5 bugs (export-parity tolerance, done-marker fabrication, gen orphan-sweep race, gen+eval orch pkill scoping) and verified the crater results were NOT poisoned (every cited eval at full n, intact deck-pairing; the result-critical leaf/POV/win-count paths verified correct). The BUG-8 export-parity fix (1e-4→5e-4) un-blocked the frozen re-run (validated in prod: the trained-policy export that FATAL-halted now passes).

**Options considered & rejected before "ship the analyzer":** (a) objective mismatch — refuted (ranking arm cratered too, τ healthy); (b) miscalibration — refuted (MSE arm is scale-calibrated, still craters); (c) F-B2 interior distribution mismatch — refuted (nail 1); (d) heuristic-subtraction not value-addition — refuted (nail 2); (e) retraining-drift — refuted (nail 3). Evidence: CL-038; results.csv `step2_nail2_*`/`step2_frozen_*`; `measurement/step2_pens/interior_tau/`.
