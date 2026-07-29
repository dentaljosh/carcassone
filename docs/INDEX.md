# Doc index — find a doc without grepping the tree

> One line per doc under `docs/`, `measurement/`, `clean_eval/`, `governance/`, grouped by role,
> with each doc's **own** stated status (current / superseded / historical). Maintained by hand —
> when you add or close out a doc, add/flip its line here. The always-loaded navigation pointers
> live in [CLAUDE.md](../CLAUDE.md) "Where the truth lives"; this is the full list.

## Current program & live reference
| Doc | Role | Status |
|---|---|---|
| [LEVER_INDEX.md](LEVER_INDEX.md) | **The intervention index** — every strength lever ever tried / declined / named-but-never-tried, keyed by the name you'd grep (colloquial · CLI flag · code symbol · codename), one line each, pointers only | **current — check before proposing a lever; add the row if it's missing** |
| [PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md) | **The single work queue** — everything live, gated, or promised; Track F is the live (adopted external-review) queue | living doc — update on every close-out (6th touch) |
| [DISTILL_STRONG_TEACHER_SPEC_2026-07-23.md](DISTILL_STRONG_TEACHER_SPEC_2026-07-23.md) | Distill the ~+40-over-deploy k8×1376 teacher into a cheap net (one-shot, NOT a flywheel; value stays severed) | GEN RUNNING (launched 2026-07-23) |
| [BACKLOG_REAUDIT_2026-07-13.md](BACKLOG_REAUDIT_2026-07-13.md) | Re-scoring of every BACKLOG / parking-lot / Track-E item against *current* premises (the premise-expiration pass) | advisory audit, point-in-time 2026-07-13 |
| [reviews/F1_RELEASE_INTEGRITY_SPEC_20260719.md](reviews/F1_RELEASE_INTEGRITY_SPEC_20260719.md) | F1 build spec — champion factory, parity-routed eval, replay audit | BUILT + MERGED 2026-07-19 (`91bff94`); residue cleared 2026-07-21 |
| [reviews/INTEGRATED_REVIEW_20260719.md](reviews/INTEGRATED_REVIEW_20260719.md) | **The integrated external review (2 independent reviewers, merged; verbatim)** — verdict audit of the whole program, 5 decision probes, stop rules, superhuman protocol | received 2026-07-19; response → adoption doc |
| [reviews/REVIEW_ADOPTION_20260719.md](reviews/REVIEW_ADOPTION_20260719.md) | **The adopted response** — disposition of every rec (adopted queue F0-F5 / policies / deferred / declined), corrections to the review's factual base | **ADOPTED 2026-07-19 (the live queue = roadmap Track F)** |
| [F3_PUBLIC_STATE_ORACLE_SPEC.md](F3_PUBLIC_STATE_ORACLE_SPEC.md) | **F3 build spec** — exact public-state oracle vs PIMC pooled-Q (root mining at genuine hidden-K, reuses `endgame_solver` marginalized DP, fusion-premium detector, Candidate-4 label persistence) | **CLOSED 2026-07-21 by Joshua** — K=3 suite ran (fusion real but modest, coverage 61% blocked a KILL); make/unmake declined a 2nd time ⇒ permanently inconclusive by choice (STATUS 2026-07-21) |
| [POST_REVIEW_PLAN.md](POST_REVIEW_PLAN.md) | **The live program (2026-07-01)** — reconciles the fresh-look review (F1–F10) with live state: solver-scored gates (F4), S1/S2 ship, M1/M2/M3 reopeners | **S1 FLIPPED · S2 CLOSED · M1 KILL · M3 FIRES (FPU axis closed) · M2 KILL 2026-07-03 (CL-042) — all reopeners resolved** |
| [AZ_VALUE_ROUTE_AUTOPSY_2026-07-01.md](AZ_VALUE_ROUTE_AUTOPSY_2026-07-01.md) | The program-level autopsy of the learned-value route — earned vs pending; the route-closure is a **REOPENING, not a death** (M1 KILL + M3 FIRE refuted Gate-B as a law) | ✅ FINAL 2026-07-03 — all three reopeners read out (M1 KILL · M3 fire-then-bounded · **M2 KILL**), CL-039 upgraded to an earned, scoped closure (CL-042) |
| [../measurement/canonical_az/M2_PLAN.md](../measurement/canonical_az/M2_PLAN.md) | **M2 runbook** — the never-run canonical-AZ cell (sighted rep × pooled value head × `score_diff_wide` × FPU=0.6 × `--leaf-eval nn`), solver-scored; read-out pre-registered (eval iters 1/3/5) | **EXECUTED — M2 KILL 2026-07-03** on both pre-registered reads (CL-042; DECISIONS 2026-07-03) |
| [../scripts/canonical_az/solver_score.py](../scripts/canonical_az/solver_score.py) | **Solver-scoring harness** (the F4 non-circular scorer) — ranks value heads vs the exact K≤4 solver, not the 0.995-circular h6400 oracle | current tooling (`b0e7158`) |
| [MEASUREMENT_FIRST_SPEC_2026-06-18.md](MEASUREMENT_FIRST_SPEC_2026-06-18.md) | The 2026-06-18 program framing — measurement-first (3 levels) | EXECUTED (L1/L2 verdicts CL-022…CL-027); still the *diagnosis* of record, but the live **queue** is the roadmap above |
| [CORRECTION_PLAN_2026-06-02.md](CORRECTION_PLAN_2026-06-02.md) | Master fix sequence (phases 0–3) | current path (Phases 1–2 outcome addendum 2026-06-12) |
| [PHASE1_BUILD_SPEC_2026-06-02.md](PHASE1_BUILD_SPEC_2026-06-02.md) | Concrete staged build A→B→C | DRAFT |
| [PeNS_SCHEMA.md](PeNS_SCHEMA.md) | Step-2 primitive substrate — triaged v0 feature shortlist (groups A–F, ~82 inputs) gating the warmstart; doctrine = encode atoms not strategies; combinatorial calc = deck-only, log-space | Step-2 weaned-value-leaf flywheel CONCLUDED 2026-06-30 — genuine Gate-B (value can rank, can't drive the leaf); see CL-038 + DECISIONS.md 2026-06-30 (closes the value-leaf lever, not the superhuman goal) |
| [ORIGINAL_PROMPT.md](ORIGINAL_PROMPT.md) | Verbatim original spec | reference (win-condition framing superseded by the 2026-05-28 goal change) |
| [CLUSTER_OPS.md](CLUSTER_OPS.md) | 3-box cluster hardware / ssh / W / launch runbook | current |
| [PATH_B.md](PATH_B.md) | Value-bootstrap (KataGo-style) | PARTIALLY FOLDED into the correction plan (not dead) |
| [../scripts/measurement_infra/README.md](../scripts/measurement_infra/README.md) | **Default measurement tooling** (not a strength lever) — multi-depth snapshot search (one deep search → all sim levels, ~2× cheaper, bit-exact to standalone h_L, h12800-verified) · lossless (deck-seed+action-sequence) root replay (any policy) · h200 top-2-gap tagging · adaptive 4-strata labeling queue. Origin CL-035. | current |

## Measurement verdicts (solver/ruler-grounded strength findings)
| Doc | Role | Status |
|---|---|---|
| [../measurement/level2/LEVEL2_LADDER_VERDICT.md](../measurement/level2/LEVEL2_LADDER_VERDICT.md) | L2-1 saturated-ruler ladder (CL-023) | VERDICT |
| [../measurement/level2/LEVEL2_L22_VERDICT.md](../measurement/level2/LEVEL2_L22_VERDICT.md) | L2-2 iter8 on the validated ladder (CL-024) | VERDICT |
| [../measurement/level2/LEVEL2_L23_VERDICT.md](../measurement/level2/LEVEL2_L23_VERDICT.md) | L2-3 endgame regret (CL-025) | VERDICT |
| [../measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md](../measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md) | Clairvoyance gap (CL-022) | VERDICT |
| [../measurement/level2/LEVEL2_LADDER_PROTOCOL.md](../measurement/level2/LEVEL2_LADDER_PROTOCOL.md) · [LEVEL2_L23_PROTOCOL.md](../measurement/level2/LEVEL2_L23_PROTOCOL.md) · [CLAIRVOYANCE_GAP_PROTOCOL.md](../measurement/clairvoyance/CLAIRVOYANCE_GAP_PROTOCOL.md) | Pre-registered protocols for the above | pre-registered |
| [../measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md](../measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md) · [G2_CONFIRM_READOUT_20260728.md](../measurement/classical_search/G2_CONFIRM_READOUT_20260728.md) · [ORACLE_PILOT_EXT_READOUT_20260728.md](../measurement/classical_search/ORACLE_PILOT_EXT_READOUT_20260728.md) | The 2026-07-28 verdict batch: meeple-dedup KILLED + intra-carry PARKED (n=1200 confirm) · "halving is free" REFUTED (−53.4, 3σ) · oracle-scored disagreements MEASURED (2752 not at the knee, cluster-robust z +2.97; same-family caveat open) | VERDICTs |
| [../measurement/classical_search/ADAPTIVE_K_CENSUS_20260728.md](../measurement/classical_search/ADAPTIVE_K_CENSUS_20260728.md) | **The adaptive-k PRE-GATE census** — 898 CL-070 roots, 4 worlds each at the production 688-sim budget: across-world value spread FLAT by phase (0.092/0.096/0.092, all \|z\|<0.6) and duplicate worlds exactly 0.00% for k_remaining ≥ 8 (whole prize 0.93% of compute = +0.16 elo) ⇒ phase-adaptive k **dies free, never built**. Also the reference for what a "dies at its pre-gate" read-out looks like. | VERDICT (gate FAIL) |
| [../measurement/ANDROID_WALLCLOCK_MEMO_20260728.md](../measurement/ANDROID_WALLCLOCK_MEMO_20260728.md) | On-device wall-clock advisory: where the Pixel's 1.7 s/move goes (meeple half > tile half), the solver-latch tail, and the two shipped levers (`exact_budget` bound + `flat_base_score`→Cython 1.28–1.34×) | memo (applied) |
| [../measurement/TOURNAMENT_LANDSCAPE_MEMO_20260728.md](../measurement/TOURNAMENT_LANDSCAPE_MEMO_20260728.md) | Tournament landscape + shopping plan: WC = exact scope match (2p base+farmers), no duplicate-deck play anywhere, zero prize money, BGA ToS closed to bots; proposed sequence is regret-exam-first, then a pro match | memo (awaiting Joshua) |
| [../measurement/m5_bench_20260728/M5_BENCH_READOUT_20260728.md](../measurement/m5_bench_20260728/M5_BENCH_READOUT_20260728.md) | **Apple M5 bench (stage Eff Jensen)** — champion single-stream ladder (deploy k4×688 = **1.58 s/move**, native arm64 Cython, hashes verified; ≈0.93× the Pixel ⇒ DRAM-latency-bound confirmed) + **ANE probe: CL-067 batch-1 forward 0.42 ms fp16, all 52 ops on the NPU, zero fallback** (vs 2.6 ms torch-CPU same box). 5900XT clean reference still owed (local was gate-contended). **§6 (2026-07-29) adds the aggregate W-ladder: optimum W=10 (bracketed — 12/14 are lower), 3.04 moves/s = 0.75× a 5900XT at W16 (4.06 moves/s, derived from 82k decisions), zero throttling on a fanless MacBook Air.** | measured 2026-07-28, throughput 2026-07-29 |
| [../measurement/PIXEL_NPU_PREP_20260729.md](../measurement/PIXEL_NPU_PREP_20260729.md) | **Pixel 9 Pro / Tensor G4 LiteRT ladder (stage Eff Jensen)** — the Android half of the ANE probe. **The G4 NPU is NOT reachable**: `google-edgetpu` is enumerated but refuses the net in all 3 precisions (float + int8-dynamic fall back to CPU *silently*; full-integer fails hard `ANEURALNETWORKS_BAD_DATA`) ⇒ GPU delegate is the third-party ceiling. Best faithful **7.76 ms** (fp16, GPU, 55/55 nodes, 3.00× the phone's 23.27 ms CPU baseline, argmax 60/60 vs torch); best faithful single-thread 10.99 ms. **≈18× the M5's ANE 0.42 ms for the identical net** ⇒ the ANE result does not transfer to the shipping device. int8-full destroys the value head (max\|Δ\| **0.787** on [-1,1]) — documented negative. Toolchain note: `ai-edge-torch` is now a deprecation shim, real converter is `litert-torch` 0.9.2. | measured 2026-07-29 |

## Research & audits (reference)
| Doc | Role | Status |
|---|---|---|
| [research/foundational_audit_2026-06-02.md](research/foundational_audit_2026-06-02.md) · [round2](research/foundational_audit_round2_2026-06-02.md) | Why the learned value can't beat v2.7 (6 root causes) | reference evidence |
| [research/leaf_eval_research_2026-06-01.md](research/leaf_eval_research_2026-06-01.md) | Perfect-info stochastic-game AI literature scan | reference |
| [../clean_eval/CLEAN_EVAL_AUDIT.md](../clean_eval/CLEAN_EVAL_AUDIT.md) | Trustworthy-ruler audit — old claims re-judged | current ruler |
| [../clean_eval/SEMANTIC_TEST_REPORT.md](../clean_eval/SEMANTIC_TEST_REPORT.md) | 11 evaluation-ruler semantic contracts | current |

## Lever specs — executed/closed (historical; here for trace)
| Doc | Lever | Status (per the doc) |
|---|---|---|
| [PROBE_A_STRUCTURED_VALUE_SPEC.md](PROBE_A_STRUCTURED_VALUE_SPEC.md) · [PROBE_B_FAIR_INFO_SPEC.md](PROBE_B_FAIR_INFO_SPEC.md) · [PROBE_B_4A_RESULTS.md](../measurement/probe_b_4a/PROBE_B_4A_RESULTS.md) | Post-Gate-B AZ probes: structure-emitting value leaf (A) · fair-info flywheel (B) | **BOTH CLOSED** — A KILLED §3A (redundant ~8σ `315122d`); B flywheel closed on the ledger, §4A all-inert/depth-saturated (`be538a7`), **B1 ships**. AZ-value route exhausted → analyzer. |
| [PROBE_5A_TEMPO_AXIS_GATE.md](PROBE_5A_TEMPO_AXIS_GATE.md) · [PROBE_5A_RESULTS.md](../measurement/probe_5a/PROBE_5A_RESULTS.md) | §5A — third-independent-axis gate (tempo/timing) before the autopsy's dimensionality sentence | **RAN — INCONCLUSIVE on the rigorous gate, live OFFLINE LEAD.** Gate-zero PASS (PARTIAL; 10-feat timing-depth core, ρ₁=0.76). Single-seed: `tempo_only` **+44.7%** (leak-clean, > farm/bag's −20.5%) → tempo is **NOT** inert; but the `both` control broke (init-fragility) so **no seed-swept Δ_indep** (confirming 4×4 sweep OOMed, not relaunched). **QUALIFIES CL-039's "low-dimensional" clause**; ship (analyzer+B1) unchanged (offline-only → recorded lead, not a loop). **CL-040**. |
| [../measurement/step2_calibration/M3_PLAN.md](../measurement/step2_calibration/M3_PLAN.md) | M3 reopener — is Gate-B a fixable calibration/tails failure (LCB / isotonic / FPU re-sweep), not a law? | **FIRES → FPU axis CLOSED** — full n=400 FPU curve peaks at parity (fpu=0.6=0.496), rolls off beyond; Gate-B (CL-038) refuted as a LAW but recovery is to parity, not exceeding. **CL-042**. |
| [../measurement/bot_anchor/S2_BOT_ANCHOR_SCOPING.md](../measurement/bot_anchor/S2_BOT_ANCHOR_SCOPING.md) | S2 ship action — out-of-ecosystem bot anchor (SamuelScheit MuZero / Ameneyro MCTS-RAVE) to break v2.x-family circularity | **CLOSED (clean negative)** — both sub-greedy → no usable anchor; non-circular refs remaining = the exact K≤4 solver + (deferred) humans. |
| [ATTEMPT2_SPEC_2026-06-08.md](ATTEMPT2_SPEC_2026-06-08.md) | Track-B flywheel attempt #2 → **iter8 champion** | COMPLETED (+67.4 elo / z2.73) |
| [PLATEAU_DECOMP_2026-06-10.md](PLATEAU_DECOMP_2026-06-10.md) | Attempt-#2 plateau decomposition | historical analysis |
| [DEEPER_TEACHER_SPEC_2026-06-11.md](DEEPER_TEACHER_SPEC_2026-06-11.md) | Stronger/deeper teacher | CLOSED — TIE vs iter8 |
| [VALUE_LOSS_ATTACK_2026-06-05.md](VALUE_LOSS_ATTACK_2026-06-05.md) → [VALUE_RANKING_ARCH_SPEC_2026-06-17.md](VALUE_RANKING_ARCH_SPEC_2026-06-17.md) | Decision-ranking value loss / arch swing | EXECUTED & CLOSED — disfavored (CL-021) |
| [V210_LEAF_SPEC_2026-07-04.md](V210_LEAF_SPEC_2026-07-04.md) | v2.10 leaf arc (cap6 reweight · bag-close) | ❌ CLOSED 2026-07-05 — both candidates tied; leaf at practical ceiling |
| [CEILING_AND_C4C6_2026-06-04.md](CEILING_AND_C4C6_2026-06-04.md) | +87 ceiling / C4·C6 value-head rebuild | CLEAN-HISTORICAL — refuted |
| [INLOOP_VALUE_FLYWHEEL_BUILD_2026-06-04.md](INLOOP_VALUE_FLYWHEEL_BUILD_2026-06-04.md) · [IN_LOOP_SEARCHVALUE_BUILD_2026-06-04.md](IN_LOOP_SEARCHVALUE_BUILD_2026-06-04.md) | In-loop value / search-value retrain | EXECUTED (historical) |
| [ASYNC_FLYWHEEL_DESIGN_2026-06-10.md](ASYNC_FLYWHEEL_DESIGN_2026-06-10.md) | Async flywheel (take selection off critical path) | DESIGN ONLY — not built |
| [STAGE_B_LAUNCH_READINESS.md](STAGE_B_LAUNCH_READINESS.md) · [STAGE_B_G-S1_PLAN_2026-06-03.md](STAGE_B_G-S1_PLAN_2026-06-03.md) | Stage-B value-in-loop retrain wiring | wiring done / plan (branch `stage-b-wiring`) |
| [PHASE3_NOTES.md](PHASE3_NOTES.md) | Phase-3 network/warmstart notes | draft, historical |
| [TEST_SUITE_GAP_ANALYSIS_2026-06-03.md](TEST_SUITE_GAP_ANALYSIS_2026-06-03.md) | Test-suite gap review | CLEAN-HISTORICAL |

## Engine / infra specs
| Doc | Role | Status |
|---|---|---|
| [DEOBJECTIFY_LEAF_PLAN_2026-06-09.md](DEOBJECTIFY_LEAF_PLAN_2026-06-09.md) | The **production** flat leaf (`USE_FLAT_LEAF=1`) | COMPLETE — DEPLOYED (current production leaf) |
| [FLAT_LEAF_BENCH_DEPLOY_RUNBOOK_2026-06-09.md](FLAT_LEAF_BENCH_DEPLOY_RUNBOOK_2026-06-09.md) | Flat-leaf throughput bench + deploy | VERDICT: DEPLOY |
| [COMPACT_LEAF_REWRITE_PLAN_2026-06-09.md](COMPACT_LEAF_REWRITE_PLAN_2026-06-09.md) · [ASBUILT](COMPACT_LEAF_REWRITE_ASBUILT_2026-06-09.md) | Compact-leaf attempt (`USE_COMPACT_LEAF`) | EXECUTED then SUPERSEDED by flat leaf — stays OFF |
| [XEON_DIRECT_SSH_2026-06-04.md](XEON_DIRECT_SSH_2026-06-04.md) | `ssh xeon-wsl` direct-WSL access | AS-EXECUTED, LIVE |
| [../android/README.md](../android/README.md) | **Android app** (side project 2026-07-27): on-device champion via Chaquopy — build/install/assets/difficulty/archive format | LIVE — SHIPPED to Joshua's Pixel (1.7 s/move full budget) |

## Governance spine
| Doc | Role |
|---|---|
| [../governance/README.md](../governance/README.md) | The governance spine — what each artifact answers |
| [../governance/PRODUCTION.yaml](../governance/PRODUCTION.yaml) | **Champion + resolved production config** (canonical) |
| [../governance/CLAIM_REGISTRY.csv](../governance/CLAIM_REGISTRY.csv) · [CHECKPOINT_LINEAGE.csv](../governance/CHECKPOINT_LINEAGE.csv) | Claim registry (CL-NNN) + checkpoint lineage |
| [../governance/EVIDENCE_EPOCHS.md](../governance/EVIDENCE_EPOCHS.md) | Evidence epochs (when the ruler/game changed under us) |
| [../governance/PROTOCOL_TEMPLATE.md](../governance/PROTOCOL_TEMPLATE.md) · [PROTOCOL_001](../governance/protocols/PROTOCOL_001_residual_marginal_topup.md) · [002](../governance/protocols/PROTOCOL_002_residual_vs_iter11_h2h.md) | Pre-registration template + filed protocols |
| [../governance/TRAINING_OBSERVABILITY_SPEC.md](../governance/TRAINING_OBSERVABILITY_SPEC.md) | Phase-B training observability spec |
