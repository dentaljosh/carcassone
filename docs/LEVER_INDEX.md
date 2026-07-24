# LEVER INDEX — every intervention, keyed by the name you'd grep

> **Why this file exists (2026-07-24).** An agent proposed five "new" levers to fix the value head; **four had been tried and killed months earlier**. The docs failed because they record **CONCLUSIONS, not INTERVENTIONS** — [governance/CLAIM_REGISTRY.csv](../governance/CLAIM_REGISTRY.csv) stores *"net value is inert"*, not *"we tried the ownership auxiliary head"*, so it greps to zero for `ownership`, `--aux-weight`, `anchor-fraction`, `search_value`, `symmetry`. The knowledge existed only as prose in [DECISIONS.md](../DECISIONS.md)'s 386KB, findable only if you already guessed the keyword.
>
> **How to use it.**
> 1. **Before proposing any lever, grep THIS file first** — by the colloquial name, the CLI flag, the code symbol, or the codename. Every alias we've ever used is in the first column on purpose.
> 2. **Absent ≠ untried.** A missing row means *nobody indexed it*, not *nobody tried it*. If you grep DECISIONS/results.csv/governance and find something, **add the row** — including `NEVER-TRIED` and `DECLINED` rows with their one-clause reason. That is what keeps this file from decaying into the thing it replaced.
> 3. **Pointers only, never evidence.** Numbers live in [experiments/results.csv](../experiments/results.csv), [governance/CLAIM_REGISTRY.csv](../governance/CLAIM_REGISTRY.csv), [governance/PRODUCTION.yaml](../governance/PRODUCTION.yaml). A figure appears below **only when the figure *is* the verdict**, with its source — per CLAUDE.md "point, don't copy".
>
> **Verdict vocabulary:** `TRIED` (ran to a verdict) · `IN FLIGHT` · `BUILT-NOT-RUN` (code exists, no verdict) · `DECLINED` (considered, explicitly not done) · `NEVER-TRIED` (named, never built or run) · `NEVER-NAMED` (nobody has even proposed it here) · `BUGFIX/HYGIENE/SPEED` (real work, not a strength claim).
>
> **Densest provenance sources** if a row is thin: `scripts/run_selfplay_iter.py:560-604` (every `--value-target` choice cites its own DECISIONS date) · `scripts/train_iter.py:320-360` (loss knobs) · [CLAIM_REGISTRY.csv](../governance/CLAIM_REGISTRY.csv) (CL-001…CL-065) · [PROGRAM_ROADMAP](PROGRAM_ROADMAP_2026-07-07.md) GATE + Track F + Parking lot (the 2026-07 declined register) · [BACKLOG_REAUDIT_2026-07-13](BACKLOG_REAUDIT_2026-07-13.md) (every parked idea re-scored against current premises) · [REVIEW_ADOPTION_20260719](reviews/REVIEW_ADOPTION_20260719.md) §"Deferred / declined" · [REVIEW_LOG.md](../REVIEW_LOG.md) (F-applied / D-deferred code review).

---

## 1. Value head — targets, losses, architecture

| lever · aliases you might grep | verdict | pointer |
|---|---|---|
| **score_diff value target** · `--value-target score_diff` · `tanh(Δ/15)` · "Option 2 currency" | TRIED — the standing default; never displaced | DECISIONS 2026-04-27, 2026-05-17 |
| **score_diff_wide** · `--value-target score_diff_wide` · `tanh(Δ/40)` · "C6 de-saturated target" | TRIED — de-saturation alone unlocks nothing | [CORRECTION_PLAN](CORRECTION_PLAN_2026-06-02.md) C6; CL-042, CL-049 |
| **win/loss target** · `--value-target wl` · "AZ-canonical ±1/0" | DECLINED as default — score_diff gives the trunk a richer signal | BACKLOG.md 2026-05-19 ("do NOT fix the default") |
| **search-Q value target** · `--value-target search_value` · "root.Q targets" · "the overfitting fix" | TRIED — fixed value-head overfitting (corr gate passed), no strength | DECISIONS 2026-06-04 pm-2/pm-3; [IN_LOOP_SEARCHVALUE_BUILD](IN_LOOP_SEARCHVALUE_BUILD_2026-06-04.md); results.csv `searchval_*` |
| **tree-interior value harvest** · `--value-target search_value_tree` · `--interior-min-visits` · `--interior-max-per-move` · "flywheel step 1" | TRIED — one-shot not enough; value-in-leaf still hurts | DECISIONS 2026-06-05; [INLOOP_VALUE_FLYWHEEL_BUILD](INLOOP_VALUE_FLYWHEEL_BUILD_2026-06-04.md) |
| **mimic-the-heuristic target** · `--value-target v2_7` · "MIMIC-V2.7" · **"STEP B.0"** | TRIED — proved the **loss form**, not the target, was the problem | DECISIONS 2026-06-05 pm-2/pm-3; [VALUE_LOSS_ATTACK](VALUE_LOSS_ATTACK_2026-06-05.md); results.csv `mimic_v27_*` |
| **listwise sibling-RANKING loss** · **"STEP B.1"** · `--value-target search_value_rank` · `--rank-weight` · `--rank-temp` · `listwise_ranking_loss` · `train_rank_loss` · `group_id` · `rank_sweep` · modern: `V4_listwise` · RankNet · LTR | **TRIED — RAN to a verdict 2026-06-05→06: "helps but INSUFFICIENT"; no config reached marginal ≥ 0.** Re-fired offline 3× since, always negative | DECISIONS 2026-06-05 pm-4 (build `369677f`) + pm-5 (verdict `88a5b5e`); results.csv `rank_a{05,10,30}t{01,03}_*` (7 rows); code `scripts/train_iter.py:59-91`; later CL-021, CL-033, CL-064 |
| **per-node centered MSE** · `--center-weight` · `centered_group_mse` · **"Lever 2"** | TRIED — FAILED; value still hurts | DECISIONS 2026-06-06 (4-lever campaign); results.csv `lever2_centered_b0*` |
| **predict-the-RESIDUAL** · `--value-target residual` · `--residual-scale` · `CARCASSONNE_V25_RESIDUAL_SCALE` · **"Lever 1"** | TRIED — the ONE asset-positive learned value; adopted, later superseded by the classical champion | DECISIONS 2026-06-06; CL-004, CL-005, CL-017; [PROTOCOL_001](../governance/protocols/PROTOCOL_001_residual_marginal_topup.md) |
| **residual FLYWHEEL** (residual live during self-play) · **"Lever 3"** · `run_residual_flywheel.sh` · "attempt #1 / attempt #2" | TRIED — NULL for compounding; the residual is a *static* asset. Attempt-2 gave a bounded gain then plateaued | DECISIONS 2026-06-07, 2026-06-10; [ATTEMPT2_SPEC](ATTEMPT2_SPEC_2026-06-08.md); CL-011, CL-018 |
| **"Lever 4"** | ⚠️ NOT A LEVER — the decision branch taken if no lever clears | `scripts/lever_sequencer.sh:190` |
| **ownership auxiliary head** · `--aux-weight` · `ownership_head` · **"Path B step 1"** · "aux-target generation" | TRIED — held-out value↔outcome corr crossed the heuristic's; **strength never converted**; always-on since, never isolated; `aux_weight=0` in every current recipe | DECISIONS 2026-05-29 (labels + the farm bug they surfaced), 2026-05-31 (corr S-curve); [PATH_B.md](PATH_B.md); `network.py` `ownership_head` |
| **value-loss weight** · `--value-loss-weight` · "gradient-starved value head" | TRIED — knob shipped, never the unlock; **CL-008 is still *Provisional*, "NEVER directly measured"** | DECISIONS 2026-06-03 (Stage-B wiring); CL-008 |
| **cosine LR / low-LR value refine** · `--lr-schedule cosine` · "G-T1" | BUILT-NOT-RUN as an isolated A/B — knob only | DECISIONS 2026-06-03 |
| **global-pool value head** · `--global-pool` · `value_global_pool=True` · `--warm-value-fresh` · "flywheel step 2" | TRIED — still fails the value-as-leaf gate; retained as standard arch | DECISIONS 2026-06-05 |
| **relational / attention value head** · "the architecture swing" · "arm C" · control "C0/conv-wide" · "arm E advantage-centered" | TRIED — DISFAVORED; attention did not out-rank its own capacity-matched conv control | [VALUE_RANKING_ARCH_SPEC](VALUE_RANKING_ARCH_SPEC_2026-06-17.md); `value_ranking/VALUE_RANKING_VERDICT.md`; CL-021 |
| **capacity ladder** · **"B3"** · `f64b4` / `f128b6` / `f256b8` · "capacity probe" | TRIED — DEAD; ~25× params moves sibling-ranking τ not at all. (An earlier "capacity crashed/abandoned" was a mis-diagnosed WSL host-memory OOM, not a result) | [CAPACITY_PROBE.md](../measurement/capacity_probe/CAPACITY_PROBE.md); CL-064 |
| **structure-emitting value leaf** · **"Probe A"** · "§3A farm/bag independence gate" | TRIED — KILLED at its own pre-registered gate | [PROBE_A_STRUCTURED_VALUE_SPEC](PROBE_A_STRUCTURED_VALUE_SPEC.md); CL-039 |
| **feature-graph action comparator** · "sibling-relative learned comparator" | TRIED — beat the leaf OFFLINE at sibling ordering, never converted to strength | `measurement/feature_graph_comparator/`; CL-034 |
| **typed feature graph / component-GNN + dynamic action head** · "Gate-C d" | TRIED (offline) → **CLOSED 2026-07-23**; relational structure buys nothing | `measurement/feature_graph_search_residual/`; CL-036; roadmap Track B B5; CL-065 |
| **PeNS scalar substrate / weaned value leaf** · "Step-2 PeNS" · **"GATE B"** · `ScalarMLP` | TRIED — genuine Gate-B: value can RANK but cannot DRIVE the leaf | [PeNS_SCHEMA.md](PeNS_SCHEMA.md); DECISIONS 2026-06-30; CL-038 |
| **learned leaf from the leaf's OWN decomposition** · **"C0"** · "learnability probe" · ridge/GBDT on 84 union-find features | TRIED — **DEAD** on a pre-registered gate; terminally closes the learned-LEAF direction, representation-independently | `measurement/gatec_c0_20260723/`; CL-065; DECISIONS 2026-07-23 |
| **bigger net / widen `policy_project_channels`** (128×10, 192×14, 256×10, 4→32 policy proj) | NEVER-TRIED — needs a fresh warmstart; **and B3/CL-064 now argues capacity isn't binding** | BACKLOG.md Phase-4 "Bigger net" |
| **KataGo-style auxiliary loss heads** (score-delta, per-feature end-controller, closure timing) | NEVER-TRIED — invasive; bundle only with a fresh-warmstart re-architecture | BACKLOG.md Phase-4 "KataGo-style auxiliary loss heads" |
| **MuZero latent value / learned dynamics** | NEVER-TRIED — Tier-4 research bet (~6 weeks), may not improve strength at all | BACKLOG.md 2026-05-27 |
| **transformer trunk over board features** | NEVER-TRIED — Tier-4 bet; bench a feature-distance probe first | BACKLOG.md 2026-05-27 |

## 2. Value — transform, calibration, information regime

| lever · aliases | verdict | pointer |
|---|---|---|
| **`value_norm` / tanh denominator** · `--teacher-value-norm` · `HeuristicMCTS.value_norm` · **"C4"** {8,15,30} · "Wave D n12" · diff/20→/15 | TRIED repeatedly — 15 optimal, both wings negative → axis closed | DECISIONS 2026-04-27, 2026-06-25 (Wave D); roadmap Track C C4; results.csv `rr_puct2750-vn{8,30}_*` |
| **win-shaping / aggressive win-probability leaf** · `v210_winshape_n4` · "do points add up to wins?" | TRIED — null; the n4 screen failed fresh-band replication. Roadmap E1's exact-K winrate re-run is still UNSTARTED | roadmap Track E E1; results.csv `v210_winshape_n4_*` |
| **utility calibration of the leaf margin** · **"F0b"**, **"F0b′"** · "T\*≈31" · "tanh 2× too steep" | TRIED — NO-GO; the F0b headline was a **raw-margin artifact** corrected by F0b′; also retro-explains the C4 vn=30 null | `measurement/utility_calibration_2026072{1,9}/REPORT.md`; CL-061 |
| **isotonic recalibration + LCB pessimism on the value leaf** · **"M3 reopener"** · `iso_map.npz` | TRIED — recovered less than FPU; not the mechanism | [M3_PLAN.md](../measurement/step2_calibration/M3_PLAN.md); CL-042 |
| **value-blend into the leaf** · `--value-blend` λ · `LeafConfig.value_blend` · `STAGE_B_BLEND` · "Option 2" · "Stage B / G-S1" | TRIED — closed **twice**; blend hurts monotonically | DECISIONS 2026-05-18, 2026-06-03, 2026-06-04; [STAGE_B_G-S1_PLAN](STAGE_B_G-S1_PLAN_2026-06-03.md); results.csv `step9_blend_lam*` |
| **pure-NN leaf (λ=1.0)** · "Path B Step 9" · `purennleaf` · "the calibration cliff" | TRIED — catastrophic; CL-006 "pure learned value is unusable as a full search leaf" | DECISIONS 2026-05-31; [PATH_B.md](PATH_B.md); results.csv `step9_nnleaf_vs_v27` |
| **additive vs convex step-2 leaf** · `--leaf-mode {convex,additive}` · `CARCASSONNE_STEP2_LEAF_MODE` · "nail 2" | TRIED — additive sits below the pure-heuristic anchor | [M3_PLAN.md](../measurement/step2_calibration/M3_PLAN.md); results.csv `step2_nail2_arm{A,B,C}_*` |
| **severed value loop** (value trained but never consulted) · "F-B1" · `--leaf-eval v2_5` at blend 0 | TRIED — first an accident, then a deliberate design lever of the 2026-07 distill flywheel | DECISIONS 2026-06-02 ("F-B1 CONFIRMED"), 2026-07-18; memory `project_flywheel_design_levers` |
| **clairvoyant vs fair value targets** · "Probe B §4A" · `--target-kind fair\|clair` | TRIED — all arms inert under BOTH regimes (the fourth nail). CL-009 ("clairvoyance harms value learning") remains *Provisional* | [PROBE_B_4A_RESULTS](../measurement/probe_b_4a/PROBE_B_4A_RESULTS.md); CL-009, CL-039 |
| **determinization-averaged (fair-info) value targets** · "Step 0(b) det probe" · K=8 reshuffles · "Step 4" | TRIED as a probe — deck noise is real but secondary; the head fails far below the noise ceiling. The full Step-4 lever was never pulled | [STEP0_DETERMINIZATION_DECISION](../measurement/step0_determinization/STEP0_DETERMINIZATION_DECISION.md) |
| **deck-aware (sighted) value** · **"Track C-cheap"** v1 and v2-residual · `train_value_only_sighted.py` | TRIED — v1 catastrophic, v2 NULL → Track C CLOSED | DECISIONS 2026-07-10; CL-049, CL-050 |
| **tempo / timing third axis** · **"§5A"** · `tempo_only` arm | TRIED — INCONCLUSIVE on the rigorous bar; real but leaf-dominated | [PROBE_5A_RESULTS](../measurement/probe_5a/PROBE_5A_RESULTS.md); CL-040 |
| **value resurrection / sibling-ordering re-probe** (reuse existing labels) · best-α=0 | TRIED — learned value still cannot beat the v2.9 leaf | `measurement/value_resurrection_pilot/`; CL-033 |
| **value/search conversion autopsy** (residual-scale ablation at the miss-set roots) | TRIED — neural value INERT at the decision level | `measurement/value_search_autopsy/`; CL-032 |
| **M2 canonical-AZ cell** · "the never-run canonical cell" · sighted × pooled-value × `score_diff_wide` × FPU 0.6 × `--leaf-eval nn` | TRIED — **KILLED on both pre-registered reads 2026-07-03** | [M2_PLAN.md](../measurement/canonical_az/M2_PLAN.md); CL-042 |
| **chance-node / determinization-ensemble value targets** · "C9 exact chance nodes" | DECLINED — de-prioritized once the clairvoyance screen came back dead-even | [CORRECTION_PLAN](CORRECTION_PLAN_2026-06-02.md) C9 |
| **curriculum value bootstrap** (base game first, then farmers) | NEVER-TRIED — transfer analogy judged weak; a new pipeline, not a knob | BACKLOG.md 2026-05-19 |

## 3. Policy head, priors, distillation

| lever · aliases | verdict | pointer |
|---|---|---|
| **visit-distribution policy targets** (the baseline) · `select_for_training(τ)` | TRIED — never replaced | DECISIONS 2026-05-03 (`79905cd`) |
| **self-play temperature** · `--temp-threshold` (15) | TRIED/LANDED — but listed in the 2026-05-26 "set early, never re-tuned" audit and **still never re-swept** | DECISIONS 2026-05-08, 2026-05-26 |
| **Dirichlet root noise** · `--dirichlet-alpha` (0.3) · `--dirichlet-eps` (0.25) | **BUILT-NOT-SWEPT** — implemented 2026-05-08, named in the stale-knob audit, never actually swept (the rule-of-thumb α for our branching would be ~0.53) | DECISIONS 2026-05-08, 2026-05-26 |
| **pooled-visit targets** (fair PIMC) | TRIED — part of the stage-1 distillation tie; never isolated | DECISIONS 2026-07-18; `scripts/distill_flywheel/gen_fair_distill.py` |
| **sharper-τ warmstart labels** · `heuristic_tau05` | TRIED — became the canonical warmstart | DECISIONS 2026-04-28, 2026-04-29 |
| **warmstart-mix schedule** · `--warmstart-mix-fraction` · "mix floor 0.3" | TRIED — v2 recipe failed acceptance; mixing later retired entirely | DECISIONS 2026-05-11; REVIEW_LOG D6 |
| **strong-teacher / sighted warmstart** · `--warm-from` · `warmstart_canonical.pt` · `warmstart_sighted.pt` · `--warm-value-fresh` | TRIED — the standing bootstrap. ⚠️ every learned-track closure is scoped *at 7M-warmstart scale* | roadmap GATE #2 |
| **2-ply heuristic policy labels** · `--heuristic-lookahead 2ply` | BUILT-NOT-RUN at scale — smoke gave near-identical policies to 1-ply, never diagnosed | BACKLOG.md 2026-04-28 |
| **MCTS-labelled warmstart** · "Option C" | DECLINED — Option D won ~25× on wins-per-hour-of-generation | BACKLOG.md 2026-04-29 |
| **anchor-fraction self-play** · `--anchor-fraction` · `--anchor-checkpoint` · "J1" · `RUN=pathb_anchor` | TRIED — the headline gain was **overturned by the independent ladder** (anchor-overfitting, no absolute gain) | DECISIONS 2026-06-01 (incl. the same-day "FALSE POSITIVE" update); results.csv `af_v1_*` |
| **Option-B chain** (chain-vs-prev anchoring) · "B1/B2/B4" | TRIED — KILLED after B4; chain anchors lied about absolute strength | DECISIONS 2026-05-24; results.csv `optionB_iter*` |
| **multi-anchor league** (N anchors, AlphaStar-style) | NEVER-TRIED — deferred pending single-anchor confirmation, which then failed | BACKLOG.md 2026-05-27 |
| **specialist warmstarts + league play** (roads/cities/farms-weighted labelers) | NEVER-TRIED — mode-collapse insurance only | BACKLOG.md Phase-4 deferred |
| **mixed-mode self-play + plateau guard + confirm-before-kill** | TRIED/WIRED — selection-gate machinery, not a strength claim | DECISIONS 2026-06-01; REVIEW_LOG F16 |
| **uniform-priors ablation** (drop the policy head) | TRIED — the policy head is load-bearing; can't drop the net | DECISIONS 2026-05-14 |
| **prior flattening** (temper the net's OWN prior) | TRIED **offline only** — a root-agreement gain **never converted to a game A/B** ⇒ arguably still untested in play | `measurement/value_search_autopsy/`; CL-032 |
| **heuristic priors at the PUCT root** · `HeuristicPriorAgent` · "Phase 1.1 / MT-1" · "the +148 flip" · `puct_priors_v29_bmild_cap8` | TRIED — **FIRED → production champion**, and it transfers fair. Its ancestor sat in BACKLOG for 6 weeks: *grep BACKLOG before dismissing "small" ideas* | CL-043, CL-047; [PRODUCTION.yaml](../governance/PRODUCTION.yaml); [PUCT_PRIORS_RESULTS](../measurement/classical_search/PUCT_PRIORS_RESULTS.md) |
| **prior temperature τ_p** · `--teacher-tau-p` · `HeuristicPriorConfig.tau_p` · "R7 tau bracket" | Standalone bracket DECLINED (Joshua 2026-07-06); TRIED inside C5-S4 and the T3 joint sweep → τ=5 confirmed, null elsewhere | roadmap Parking lot + C5-S4; CL-057; results.csv `c5_s4_curve125_taup{3,8}` |
| **leaf quantization for prior resolution** · `--teacher-leaf-quantize {float,int}` | TRIED — float confirmed as the champion setting | results.csv `puct_c*_tau*_float_*` |
| **oracle root priors** · **"F2 / Gate A"** · `--oracle-prior-mult` · `carcassonne_ai.oracle_prior` | TRIED — clairvoyant screen FIRED, **FAIR confirm is a dead tie** ⇒ the policy-prior channel has no capturable fair headroom | CL-059; results.csv `f2_oracle_prior_screen`, `gateA_fair_confirm` |
| **prior-as-move-ordering / depth transfer** · **"F4 / Gate B"**, **"F4b"** · `gate_b_depth_transfer.py` · `gate_b_fair_pimc.py` | TRIED — prior influence **decays with search depth** (Q-convergence); replicates fair and on champion-distribution roots. This is the mechanism behind the sims-washout | CL-062; [GATE_B_FAIR_VERDICT](../measurement/gate_b_fair_pimc/GATE_B_FAIR_VERDICT.md) |
| **stage-0 teacher-τ** (value labels from the stronger classical policy) · "B1" | TRIED — KILL-CONFIRM: a stronger classical policy makes *worse* value labels | roadmap Track B B1; [TEACHER_TAU_PLAN](../measurement/classical_search/TEACHER_TAU_PLAN.md) |
| **champion→net distillation, stage 1** · `--teacher heuristic_prior` · `gen_fair_distill.py` · `champ_env.sh` | TRIED — the distilled net **TIES** the fair champion at production budget: a faithful copy, so no win was available | `measurement/distill_flywheel_20260715/`; CL-058 |
| **distill flywheel stage-2** (net-prior self-play growth) · "the it16 peak" | TRIED — growth **REFUTED** (fresh-band extension + production-depth washout) | CL-058; memory `project_flywheel_design_levers`; results.csv `eval_iter*_vs_rodv2iter02*` |
| **distill a STRONGER-than-deploy teacher** · `distill_strong_20260723` · teacher `k8×1376` | **IN FLIGHT** (gen launched 2026-07-23) — first distillation where the teacher genuinely beats deploy | [DISTILL_STRONG_TEACHER_SPEC](DISTILL_STRONG_TEACHER_SPEC_2026-07-23.md) |
| **deeper teacher** (sims=800 generator) · `deepteacher` · `deepsearch` · "SEALED / WASHOUT" · "M1 reopener" | TRIED — TIE vs its warm-from parent; the apparent gain was band noise (and had a provenance defect) | [DEEPER_TEACHER_SPEC](DEEPER_TEACHER_SPEC_2026-06-11.md); CL-019, CL-020, CL-042 |
| **hard-state policy repair** (h3200≠h6400 disagreement states) · "decision A" | TRIED — DEAD END; the target is signal-free on those states | `measurement/hard_policy_repair/`; CL-030 |
| **high-contrast decision-signal distillation** (Q-gap / regret selection) · "decision B" | TRIED — signal exists and is learnable but does **not convert through search**. Note: plain loss/importance re-weighting per se was never tried | `measurement/high_gap_distillation/`; CL-031 |
| **B2 — distilled net-prior vs leaf-prior inside the new PUCT** · "the one unsampled cell" | DECLINED / NOT FUNDED — the B1a headroom diagnostic came in far under its bar | roadmap Track B B2 |
| **policy-scale** (clean-policy iteration at scale) · "the +87 ceiling" | TRIED — failed to climb past the ceiling | DECISIONS 2026-06-04 (pm) |
| **root-action / policy-mixing role audit** (standalone · root-prior · candidate-generator · specialist) | TRIED (offline) — the net is not a useful standalone root-prior | `measurement/search_policy_mixing/ROOT_ACTION_AUDIT.md` |
| **hybrid handoff** (net early/mid → deep heuristic endgame) · `l2hyb_K*` | TRIED — real and monotone in K; superseded by the classical champion | CL-026; results.csv `l2hyb_K*` |
| **tabula-rasa / from-scratch net** · **"az_zero"** · `make_random_ckpt.py` · `run_az_zero.sh` | **IN FLIGHT** (launched 2026-07-24) — first true zero-start. Tests the *scaffolding confound*, explicitly **not** a strength lever. ⚠️ supersedes the roadmap's "never-run / don't fund" line | [PREREG](../measurement/az_zero_20260724/PREREG.md) + [DESIGN](../measurement/az_zero_20260724/DESIGN.md); roadmap GATE #3 |
| **distil to a small fast student** (4×64 / 6×64, KL to teacher) | NEVER-TRIED — a *latency* play, not strength; distinct from the two distillation rows above | BACKLOG.md 2026-05-27 |

## 4. Representation / input features

| lever · aliases | verdict | pointer |
|---|---|---|
| **sighted vs blind representation** · "sighted rep" (81ch + 42 scalars) · "the bag" | TRIED — passes the offline gate, **no detectable game gain**; kept for ~zero cost | `measurement/feature_planes_gate/STEP1_GATE_RESULTS.md`; CL-037; STATUS 2026-07-17 |
| **farm-connectivity planes (+3) · bag/deck histogram (+32)** · "C4 representation planes" · modes `none/farm/bag/both/both_shuffled` | TRIED — **Gate A PASS** offline (flipped CL-033); the expensive Stage-C retrain never gated open because Gate B failed | [CORRECTION_PLAN](CORRECTION_PLAN_2026-06-02.md); CL-037, CL-038 |
| **symmetry augmentation (4× rotations)** · `--augment-rotations` · `augment_with_rotations` · "C5 / Stage A3" | BUILT (16 tests) → **A/B NULL, shelved**. Reflection augmentation NEVER-BUILT (curved roads aren't reflection-symmetric) | DECISIONS 2026-06-10 pm-2/pm-3; results.csv `symaug_aug_{on,off}_*` |
| **KataGo-style domain input planes** (`tiles_remaining`, `my_meeples_in_hand`, `is_endgame`, …) | NEVER-TRIED — breaks weight compatibility with every checkpoint. ⚠️ **No input addition has EVER fired in games in this project** | BACKLOG.md Phase-4; `measurement/distill_flywheel_20260715/INPUT_EXPOSURE_HISTORY.md` |
| **full-board / no-crop representation rework** · "P1-R1..R4" · `compute_window_offset` | DECLINED — the window audit measured 0 dropped legal actions on the production distribution | [REVIEW_ADOPTION](reviews/REVIEW_ADOPTION_20260719.md) §Deferred/declined |
| **action-space dedup** (redundant meeple slots) · "D19 raw un-deduped child N" | DECLINED/DEFERRED — invalidates every checkpoint (policy-head shape); in the hygiene bundle, never actioned | BACKLOG.md 2026-05-14; REVIEW_LOG D19; roadmap Parking lot |
| **scalar redundancy (P1-R6) · rotation-alias label fragmentation (P1-A3) · tie-epsilon asymmetry (P1-G1)** | DECLINED — below the current cost line, logged to BACKLOG | [REVIEW_ADOPTION](reviews/REVIEW_ADOPTION_20260719.md) §Deferred/declined |
| **probing classifiers / hand-curated tactical probe set** | NEVER-TRIED — measures, doesn't fix | BACKLOG.md Phase-4 deferred |

## 5. Search & allocation

| lever · aliases | verdict | pointer |
|---|---|---|
| **c_puct sweep** · `--c-puct` · `phase2_puct_c*` | TRIED — low c catastrophic, c=1.5 well-chosen | DECISIONS 2026-05-15; results.csv `phase2_puct_c*` |
| **the c=3 bump** · "the +47 free win" · `hygiene_c3_vs_c15` · "stale-PUCT" | TRIED — **the founding results-discipline lesson**: +47 shrank at n=1600 and went FLAT in Stage-A2; default unchanged | DECISIONS 2026-05-26, 2026-05-28, 2026-06-02; results.csv `hygiene_c3_vs_c15_n1600` |
| **c_puct under the PUCT-priors champion** · "C5-S5" · c1.0 / c2.25 wings | TRIED — c=1.5 remains best | roadmap C5-S5; results.csv `c5_s5_curve125_cpuct*` |
| **FPU / first-play urgency** · `--fpu` · `fpu_reduction` · fpu02…fpu10 | TRIED twice — a Stage-A2 screen fired but **its n=400 confirm was never run** (mooted by expand-all); M3 later ran the full curve → **peaks at parity, axis CLOSED** | DECISIONS 2026-06-02; [M3_PLAN](../measurement/step2_calibration/M3_PLAN.md); CL-042 |
| **virtual loss + batched-eval MCTS** · `--virtual-loss` · `--batch-size` · `_select_leaf_with_vloss` | TRIED/SHIPPED — SPEED (3× batch-fill; enables orchestrator batching) | DECISIONS 2026-05-08 |
| **tree reuse / re-root between moves** · `reuse_tree` · "C3" | TRIED → folded clairvoyant, but **fair value ≈ 0 by mechanism** (a no-op inside `FairHeuristicPriorAgent`); ON for clairvoyant dev only | CL-044; roadmap C3 |
| **Gumbel root / sequential halving / completed-Q selector** · "C1" · top-m (m16/m256) · `retain_g`/`noG` | TRIED — top-m loses badly; completed-Q is a small **clairvoyant-only** gain (fair mode is already Q-based) → CLOSED, flag-gated default OFF | CL-052; results.csv `rr_puct2750-gumbel*` |
| **LCB final selection** · "C2" · `c_lcb` | TRIED — a wash; visit-argmax stays | roadmap C2; results.csv `rr_puct2750-lcbclcb1_*` |
| **determinization width k** · `k_dets` · `--k-dets` · `--opp-k-dets` · "the k_dets marginalization bracket" | TRIED → **ADOPTED**: inverted-U peaked at k=4, cost-neutral; the first fair lever to fire *and* confirm | CL-054; [PRODUCTION.yaml](../governance/PRODUCTION.yaml); results.csv `kdets_k*` |
| **width-vs-budget re-allocation at higher budgets** · k8×1376@11008 · k16×1376@22016 · "under-determinized k8×2752" | TRIED — **allocation matters more than budget** (a ~32-elo swing at 8×); CL-054's k4 optimum is budget-specific. ⚠️ tension with CL-054 UNRESOLVED | CL-060 (Reopened); results.csv `cl060_*`, `curve_k*` |
| **buying simulations / throughput** · **"F5"** · `fair_ruler_rebase_*` · "the ladder bends" | TRIED — closed NO-GO, then **RE-OPENED by its own falsifier**; budget is purchasable but expensive and leaves the structural blocker untouched. Standing rec: **do not fund a throughput program** | CL-060; roadmap F5 |
| **fair PIMC vs clairvoyant play** · `--fair` · `FairHeuristicPriorAgent` · `eval_fair_puct.py` · "the clairvoyance tax" | TRIED — the tax is real and **persists** across a 7× sims range; the fair sub-ladder is the **ruler of record** | CL-022, CL-045, CL-046, CL-048 |
| **PIMC determinization fairness leak** · `fair_agent.py` reshuffle | BUGFIX — a real leak in the deployed fair champion; fixed, creating a fair-baseline discontinuity | CL-056 |
| **exact endgame solver hybrid** · `exact:K` · `endgame_solver.py` | TRIED — **in the champion** at K≤4; margin scales with K but **winrate does not**; also the program's first non-circular label source | CL-025, CL-026, CL-027 |
| **make/unmake** (incremental apply/undo for the solver) · "the real lever for K=5" · "F3 Phase-2" | **DECLINED TWICE** (Joshua 2026-07-09, 2026-07-21) — 3–5 eng-days, ~0 production strength; F3 therefore stands permanently inconclusive *by choice* | roadmap Track F F3; BACKLOG.md 2026-06-21 |
| **compact TT keys / TT cap for the solver** · `CARCASSONNE_TT_CAP` | TRIED — only ~1.5–1.7×, and **0.22% cross-parent hits** ⇒ the chess-engine TT framing is dead here; the cap is a safety valve, not a speedup | BACKLOG.md 2026-06-21 (`6f9dd08`); roadmap C6 stage-0 |
| **transposition table in MCTS** · `NeuralMCTS._nodes` | ALREADY IMPLEMENTED — don't re-propose. (A collided-visit double-count bug was fixed 2026-06-02) | BACKLOG.md 2026-05-27; DECISIONS 2026-06-02 |
| **move ordering (Δleaf) in αβ** | TRIED inside C6 only — the only surviving αβ advantage besides depth; never used in PUCT | [C6_COST_SURFACE](../measurement/classical_search/C6_COST_SURFACE.md) |
| **full-game ID-alpha-beta + TT** ("the clairvoyant chess-engine gambit") · **"C6"** | TRIED (built, calibrated, screened) → CLOSED — clairvoyant-only, no fair form ⇒ strategically inert | CL-053; [C6_ALPHABETA_DESIGN](../measurement/classical_search/C6_ALPHABETA_DESIGN.md) |
| **αβ+TT as a fair ENDGAME module** · **"A-small"** · A0/A1 | DECLINED (free) — αβ is clairvoyant-only (chance nodes break minimax) and the tax is midgame. A1 fair screen held as attended, never run | [A_SMALL_SPEC](../measurement/classical_search/A_SMALL_SPEC_2026-07-09.md); roadmap Track A |
| **public-state oracle / strategy-fusion recovery** · **"F3"** | TRIED (K=3 suite ran) — fusion is real but modest and not cheaply recoverable; coverage blocked a KILL ⇒ closed inconclusive | [F3_PUBLIC_STATE_ORACLE_SPEC](F3_PUBLIC_STATE_ORACLE_SPEC.md); roadmap F3 |
| **joint hyperparameter search (Optuna / TPE)** · **"T3"** · `optuna_trial_*` · t020 / t27 | TRIED — CLOSED NULL; both clairvoyant candidates died at the mandatory fair gate (t020 was a winner's-curse spike) | CL-057; [OPTUNA_KNOB_SWEEP_DESIGN](../measurement/classical_search/OPTUNA_KNOB_SWEEP_DESIGN.md) |
| **multi-fidelity screening (Hyperband / successive halving)** | Realized *inside* the T3 driver as nested successive-halving; the standalone BOHB/pruner wrapper is NEVER-TRIED | BACKLOG.md 2026-05-27; OPTUNA_KNOB_SWEEP_DESIGN |
| **adaptive-compute escalation scheduler** · post-search residual · `low_top2gap` · "Decision C" | TRIED → **CLOSED FOR STRENGTH — "do NOT re-suggest"**; survives only as a parked efficiency-only idea | CL-035; BACKLOG.md 2026-06-29 |
| **endgame depth boost** (last-10-tiles sims=400) · "MCTS-side domain tweaks #1" | NEVER-TRIED | BACKLOG.md Phase-4 "MCTS-side domain tweaks" |
| **forced-move shortcut** (skip search when one legal placement) · "MCTS-side domain tweaks #3" | NEVER-TRIED | BACKLOG.md Phase-4 "MCTS-side domain tweaks" |
| **search self-consistency probe** (sims=200 vs 1000 disagreement) | NEVER-TRIED — diagnostic only, deferred | BACKLOG.md 2026-05-17 |
| **shortened-game deck subsetting as a screening regime** | DECLINED — cuts ~80% of closing-phase decisions; sims reduction gives the same speedup with less generalization risk | BACKLOG.md 2026-05-28 |
| **root parallelism** | **NEVER-TRIED and NEVER-NAMED** — the only parallelism ever pursued is process-level (workers / work-stealing / orchestrator batching) | absence confirmed by grep over DECISIONS.md + BACKLOG.md, 2026-07-24 |
| **afterstate search** | **NEVER-TRIED under that name.** Nearest relatives are sibling *child-state* ranking (CL-033) and the action-conditioned comparator (CL-034) | CL-033, CL-034 |
| **ISMCTS / belief-space / CFR-family rebuild** | NEVER-TRIED, NEVER-SCOPED — "an order of magnitude larger rebuild"; advisory read = ISMCTS marginal, CFR dead-on-mechanism | roadmap F3 body + Track B B5 |

## 6. Leaf & heuristic

| lever · aliases | verdict | pointer |
|---|---|---|
| **v1 → v2 → v2.5 leaf lineage** · `virtual_score.py` · `virtual_score_v2.py` · `--leaf-eval v2_5` | TRIED — v2 FAILED the bench (closure-blindness / farm opacity / tanh saturation); v2.5 then passed. This ladder is where the real strength came from | DECISIONS 2026-05-14 |
| **farm/city dedup fix (v2.5) + farmer-adjacency involution fix** (`opposite_farmer_side` `TRT→BRB`) · "C1" | BUGFIX — shifted every downstream optimum and invalidated prior elo; forced a full cap re-sweep | DECISIONS 2026-05-15, 2026-05-29, 2026-06-02; CLAUDE.md "Engine notes" |
| **`bonus_cap` / closure-anticipation cap** · `_BONUS_CAP` · `CARCASSONNE_V25_CAP` · cap5/6/8/12/20/Inf · `drop-3-open` | TRIED many times — **the longest null record in the project**; the one real move was v2.9.1 cap 5→8 | CL-028; results.csv `phase4_cap*`, `v291_waveB_*`, `v210_cap6_*`, `c5_cap*` |
| **asymmetric opponent cap** · `_OPP_BONUS_CAP` · `c5_oppcap4/12` · "D3 antisymmetry" | TRIED — v3 blanket version was n=20 noise, C5 cells null. The lit-review reframe ("targeted denial on near-complete large opponent cities") is **NEVER-TRIED** | DECISIONS 2026-05-15; REVIEW_LOG D3; BACKLOG.md 2026-05-16 |
| **closure-probability schedule** · `_CLOSURE_P` · `CARCASSONNE_V25_DROP_THREE_OPEN` · `c5_pclose080/120` | TRIED — already well-tuned; "closure-probability accuracy is not the lever" | DECISIONS 2026-05-17; results.csv `c5_pclose*` |
| **Bmild meeple-economy curve** · `v2_9_2_Bmild_cap8` · "the MILD curve" · THRONE test | TRIED → PROMOTED (v2.9.1); meeple economy is a real, large heuristic-leaf gain | CL-028, CL-041; [V29_DECISION](../measurement/v29_leaf_audit/V29_DECISION.md) |
| **meeple curve ×1.25** · `curve125` · `v29_meeple_curve` · `CARCASSONNE_V29_MEEPLE_CURVE` · **"C5"** | TRIED → **ADOPTED**. Note the premise lesson: **NULL under random-expansion UCT, WIN under PUCT+priors** — a leaf knob's value depends on the search that consumes it | CL-051; [C5_CURVE125_PROPOSAL](../measurement/classical_search/C5_CURVE125_PROPOSAL.md) |
| **`meeple_k`** (flat meeple-count term) | TRIED (null in v3) and now **INERT under a non-null curve** — a config-hygiene item, not a lever | [PRODUCTION.yaml](../governance/PRODUCTION.yaml) `leaf_config`; roadmap Parking lot |
| **tile-counting / bag-aware closure probability** · `bag_close` · `leaf_variant tile_counting` | TRIED — ties the champion; C5 cell null | [V210_LEAF_SPEC](V210_LEAF_SPEC_2026-07-04.md); results.csv `v210_bagclose_*`, `c5_bagclose_*` |
| **new leaf TERMS by hand** · **"C7"** · Term R `v29_meeple_return_k` (stranding) · Term F `v29_farm_flip_k` (farm majority flip) | TRIED → **CLOSED NULL**; Term R was decisively *harmful*. curve125 had already soaked the extractable headroom | CL-055; [C7_LEAF_TERMS_DESIGN](../measurement/classical_search/C7_LEAF_TERMS_DESIGN.md) |
| **v2.10 leaf arc** · cap6 reweight · bag-close | TRIED → CLOSED. Lasting finding: **the K≤2 solver screen does NOT predict full-game leaf strength** | [V210_LEAF_SPEC](V210_LEAF_SPEC_2026-07-04.md) |
| **error-guided leaf-term discovery** · **"F6"** · leaf residual mining · `bonus_overflow_self` | TRIED — AMBIGUOUS-at-the-floor ≈ a powered null | CL-063; [PREREG](../measurement/leaf_residual_mining_20260721/PREREG.md) |
| **soft cap** (linear credit above the closure cap) · "F6 S1" · 5-slope dose sweep | TRIED — flat-to-negative at every slope ⇒ the leaf-accuracy channel is **confirmed closed** | CL-063 (amended); results.csv `f6_softcap*` |
| **board-edge unclosable-city bonus** · "D16" | BUGFIX — fixed; no cap re-sweep needed (trigger practically unreachable) | REVIEW_LOG D16 |
| **farm multi-field-city rule check** · "F0a / P1-L5" | TRIED — **REFUTED**: engine and both leaves already pay multi-field city farms correctly; fixture `tests/test_farm_multifield_city_p1l5.py` | roadmap F0a; STATUS 2026-07-19 |
| **leaf ideas from the competitive-strategy literature** | Partly TRIED (tile-counting, stranding, farm-flip — all null/harmful). **"Penalize large open cities" and "targeted denial" remain NEVER-TRIED** | BACKLOG.md 2026-05-16 |
| **per-side leaf A/B harness** · `--cand-leaf-json` · per-side `leaf_hash` in manifests | BUILT (prerequisite) — before this, a leaf A/B was literally impossible (both sides got `DEFAULT_CONFIG`) | [C5_LEAF_RETUNE_DESIGN](../measurement/classical_search/C5_LEAF_RETUNE_DESIGN.md) |
| **flat leaf (de-objectified)** · `flat_leaf.py` · `CARCASSONNE_USE_FLAT_LEAF=1` | TRIED → **DEPLOYED**. SPEED, bit-exact ⇒ no ruler change | [DEOBJECTIFY_LEAF_PLAN](DEOBJECTIFY_LEAF_PLAN_2026-06-09.md) |
| **compact leaf** · `compact_leaf.py` · `USE_COMPACT_LEAF` · `CANONICAL_BONUS_SUM` | TRIED (logic-exact) → superseded by the flat leaf; **stays OFF, do not re-propose** | [COMPACT_LEAF_REWRITE_PLAN](COMPACT_LEAF_REWRITE_PLAN_2026-06-09.md) |
| **Cython leaf + board encoder** · `USE_CY_LEAF` · `flat_repr_cy` · `USE_CY_REPR` · `compute_window_offset` O(1) | TRIED → FOLDED to production. SPEED ONLY | BACKLOG.md 2026-06-12 (pm); memory `feedback_default_cython_and_orch` |
| **leaf flood-fill lazy memo** (farm + city caches) | TRIED/SHIPPED — SPEED, value-invariant | DECISIONS 2026-05-29 |
| **stepping-path Cython / re-de-objectify the engine** | DEAD — break-even spike; **do not re-propose without a new premise** | roadmap Parking lot (`d3896c0`) |

## 7. Data & training

| lever · aliases | verdict | pointer |
|---|---|---|
| **replay window size** · `--window` (10 → 30, 12 in the distill flywheel) · "window-aging" | TRIED as a recipe change, but the **isolated A/B has never been run** — the two designs are confounded by selection + warm-from-best + leaf | DECISIONS 2026-05-11; BACKLOG.md 2026-06-11 |
| **batch size 256 vs 512** | TRIED — **keep 256**: b512 ties head-to-head but fails the parent gate and under-trains the policy | `measurement/rod_batch512_calibration/`; roadmap B4 |
| **epochs per iter** (3 standard; "2-epoch batch-256 freebie") | The 2-epoch variant is **NEVER-TRIED** — explicitly unclaimed from the b512 calibration | roadmap Track B B4 |
| **LR schedule sweep** | **NEVER-TRIED as a strength lever** — no LR sweep exists in DECISIONS or results.csv; LR-groups appear once, inside the C-cheap v2 trainer | absence confirmed by grep, 2026-07-24 |
| **per-sample loss / importance weighting** | **NEVER-TRIED** — the closest work is *dataset selection* (hard-state repair, high-gap distillation), not re-weighting | CL-030, CL-031 |
| **entropy-floor collapse guard** · `--entropy-floor-frac` | GUARD, not a lever — shipped; disabled for az_zero | DECISIONS 2026-05-29 (evening) |
| **invalid-visit clip / rotation-alias cache collision** · "Phase 0.3" | BUGFIX — a silent policy-target corruption across the whole prior era; root-caused + regression-tested | [ROOT_CAUSE](../measurement/invalid_visit_clip/ROOT_CAUSE.md) |
| **deck-seed banding + deck PAIRING (CRN)** · "band Ne9" · `deck_hash` · "G-M2" | STANDARD PRACTICE, not a strength lever — load-bearing against band noise (the M1 KILL was a band-noise unmasking). Known gap: `deck_hash` omits the first drawn tile | CL-014, CL-042; [EVIDENCE_EPOCHS](../governance/EVIDENCE_EPOCHS.md) |
| **self-play game count / data scarcity** | TRIED — more v2.7 self-play did make a stronger model early; later runs are capped by the leaf ceiling, not by data | DECISIONS 2026-05-16 |
| **training-box shopping / more dataloader workers** | TRIED — training is **GPU-latency-bound**, not CPU-bound; don't re-propose | memory `reference_training_latency_bound` |

## 8. Infrastructure — marked SPEED vs pursued-AS-STRENGTH

| lever · aliases | verdict | pointer |
|---|---|---|
| **"would a throughput/search-core program buy elo?"** · **"F5"** | **PURSUED AS STRENGTH** — measured: compute is purchasable but expensive, and it does not touch the structural blocker. Standing recommendation: **don't fund it** | CL-060; roadmap F5 |
| **GPU orchestrator** · `carc-orch` · SHM eval-server · forwarders · CUDA-streams gambit | TRIED, mixed → **SPEED ONLY**. ⚠️ incompatible with K≥4 solver evals (starves the server) | memory `reference_carc_orch_verdict`, `reference_exact_solver_eval_infra`; [CLUSTER_OPS](CLUSTER_OPS.md) |
| **orchestrator multi-process pool / GIL hypothesis** | TRIED → NULL; workers are the bottleneck, not the GIL | DECISIONS 2026-05-13 |
| **worker-count (W) sweeps** · `--workers` · SMT fan-out | TRIED extensively → SPEED ONLY, and **does not transfer** between boxes or between gen and eval. The laptop **GEN** sweep has never been done | memory `feedback_worker_count_by_bottleneck`; BACKLOG.md 2026-07-17 |
| **FP16 inference** · `--fp16` | TRIED → **batch-conditional SPEED**: slower at small per-worker batch, positive under the orchestrator at large max_batch. The canonical "grep BACKLOG first" example | DECISIONS 2026-05-12, 2026-06-01; memory `feedback_grep_backlog_before_suggesting_easy_wins` |
| **batch-1 search fix / wiring evals onto the orchestrator** | Originally DECLINED as scoped, later superseded by orch-in-eval. ⚠️ the batch-1 fix changed the net's per-move cost by ~6× — **re-read any older equal-wall-clock ratio with suspicion** | BACKLOG.md 2026-05-31; STATUS 2026-07-17 |
| **MCTS Python hot-path Cython rewrite** | NEVER-TRIED — and contra-indicated: the profile says the PUCT loop was never hot | BACKLOG.md Phase-4 |
| **async flywheel** (selection off the critical path) | **DESIGN ONLY — NOT BUILT**; the step-2 variant was DOA the day it was proposed | [ASYNC_FLYWHEEL_DESIGN](ASYNC_FLYWHEEL_DESIGN_2026-06-10.md) |
| **work-stealing / multi-box sharding** · `--shared-claim` · `--claim-stale-secs` | TRIED/DEFAULT. Known unfixed: claim-tail idle, D9 failed-game claim hold, D15 multi-winner race (accepted) | REVIEW_LOG D9/D15; BACKLOG.md 2026-06-02 |
| **network-distributed eval server** · `remote_eval_bridge.py` | TRIED → DEAD END (box retired); a suspected stale-response correctness bug is logged unfixed | BACKLOG.md 2026-05-21 |
| **Apple silicon** · MPS backend · ANE / Core ML | MPS TRIED (fp32 + no-MPS was optimal); **ANE NEVER-TRIED** — real integration project, smallest cluster contributor | DECISIONS 2026-05-12; BACKLOG.md 2026-05-27 |
| **flywheel-orchestrator resilience (`HOSTS` knob) · telemetry-gate stall window** | DECLINED/DEFERRED — infra hardening, not strength | BACKLOG.md 2026-06-14 |
| **measurement infra** · multi-depth snapshot search · lossless root replay · h200 top-2-gap tagging · adaptive strata queue | BUILT — the **default tooling**, explicitly *not* a strength lever; it is what made F4/F4b/F6 affordable | [measurement_infra/README](../scripts/measurement_infra/README.md); CL-035 |
| **release integrity** · **"F1"** · `champion_factory.py` · `tests/release/` · replay audit | BUILT/COMPLETE — the standing gate for headline claims; re-run after ANY champion-touching change | roadmap F1; `measurement/release_audit_20260721/` |
| **out-of-ecosystem bot anchor** (SamuelScheit MuZero / Ameneyro MCTS-RAVE) · "S2" | TRIED — clean negative; both sub-greedy, no usable external anchor | [S2_BOT_ANCHOR_SCOPING](../measurement/bot_anchor/S2_BOT_ANCHOR_SCOPING.md) |
| **human anchor** · **"E4"** | **NEVER-RUN — parked by Joshua** ("no human yet"). With the exact solver, the only non-circular reference we have | roadmap Tracks E/F; [REVIEW_ADOPTION](reviews/REVIEW_ADOPTION_20260719.md) |
| **phone / deployment budget bench** | TRIED — corrects the "net@200 is instant" assumption (that was GPU/NPU-only). Deployment sizing, not strength | [PHONE_BUDGET_BENCH](../measurement/phone_budget/PHONE_BUDGET_BENCH.md) |

---

## Genuinely untried, as of 2026-07-24

A standing short list so "what's actually left?" doesn't require re-reading the tables. Everything here is `NEVER-TRIED`, `NEVER-NAMED`, or `BUILT-NOT-RUN` — **not** "tried and killed". Order is roughly cheapest-first, not by expected value.

1. **`--temp-threshold` / `--dirichlet-alpha` / `--dirichlet-eps` re-sweep** — set in Phase 4, flagged stale 2026-05-26, never swept. Dirichlet in particular is BUILT-NOT-SWEPT.
2. **2-epoch batch-256 recipe refresh** (roadmap B4 remainder) and an **LR-schedule sweep** (never done at all).
3. **Prior flattening as a *game* A/B** — the offline root-agreement gain (CL-032) was never converted into a strength measurement.
4. **Replay-window A/B** (accepted-iters-only window) — BACKLOG 2026-06-11; every window claim to date is confounded.
5. **Width at fixed budget on ONE deck band** — CL-060's own named next test; today's width residual is a cross-band quadrature difference at z≈1.2.
6. **Learning-to-rank on the *newest* (Gate-C) feature representation** — CL-065's own caveat: its pre-registered learners were MSE regressors. Judged *implausible, not ruled out* — every prior LTR fire (STEP B.1, CL-021 arm B, CL-033/CL-037 `V4_listwise`) was negative.
7. **Leaf terms never tried:** "penalize large open cities" and "targeted denial on near-complete large opponent cities" (BACKLOG 2026-05-16); endgame depth boost and the forced-move shortcut on the search side.
8. **2-ply heuristic policy labels at scale** — built, smoked, never diagnosed.
9. **Root parallelism · afterstate search · ISMCTS/belief-space/CFR** — never even proposed here (the first two), or named-and-never-scoped (the third).
10. **Human anchor (E4)** — parked by Joshua, not closed. Still the highest-information measurement available.

Everything else in the tables above has a verdict. Check it before proposing it.
