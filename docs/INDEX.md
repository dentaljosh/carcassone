# Doc index — find a doc without grepping the tree

> One line per doc under `docs/`, `measurement/`, `clean_eval/`, `governance/`, grouped by role,
> with each doc's **own** stated status (current / superseded / historical). Maintained by hand —
> when you add or close out a doc, add/flip its line here. The always-loaded navigation pointers
> live in [CLAUDE.md](../CLAUDE.md) "Where the truth lives"; this is the full list.

## Current program & live reference
| Doc | Role | Status |
|---|---|---|
| [MEASUREMENT_FIRST_SPEC_2026-06-18.md](MEASUREMENT_FIRST_SPEC_2026-06-18.md) | The current program — measurement-first (3 levels) | PROPOSED |
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
| [ATTEMPT2_SPEC_2026-06-08.md](ATTEMPT2_SPEC_2026-06-08.md) | Track-B flywheel attempt #2 → **iter8 champion** | COMPLETED (+67.4 elo / z2.73) |
| [PLATEAU_DECOMP_2026-06-10.md](PLATEAU_DECOMP_2026-06-10.md) | Attempt-#2 plateau decomposition | historical analysis |
| [DEEPER_TEACHER_SPEC_2026-06-11.md](DEEPER_TEACHER_SPEC_2026-06-11.md) | Stronger/deeper teacher | CLOSED — TIE vs iter8 |
| [VALUE_LOSS_ATTACK_2026-06-05.md](VALUE_LOSS_ATTACK_2026-06-05.md) → [VALUE_RANKING_ARCH_SPEC_2026-06-17.md](VALUE_RANKING_ARCH_SPEC_2026-06-17.md) | Decision-ranking value loss / arch swing | EXECUTED & CLOSED — disfavored (CL-021) |
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

## Governance spine
| Doc | Role |
|---|---|
| [../governance/README.md](../governance/README.md) | The governance spine — what each artifact answers |
| [../governance/PRODUCTION.yaml](../governance/PRODUCTION.yaml) | **Champion + resolved production config** (canonical) |
| [../governance/CLAIM_REGISTRY.csv](../governance/CLAIM_REGISTRY.csv) · [CHECKPOINT_LINEAGE.csv](../governance/CHECKPOINT_LINEAGE.csv) | Claim registry (CL-NNN) + checkpoint lineage |
| [../governance/EVIDENCE_EPOCHS.md](../governance/EVIDENCE_EPOCHS.md) | Evidence epochs (when the ruler/game changed under us) |
| [../governance/PROTOCOL_TEMPLATE.md](../governance/PROTOCOL_TEMPLATE.md) · [PROTOCOL_001](../governance/protocols/PROTOCOL_001_residual_marginal_topup.md) · [002](../governance/protocols/PROTOCOL_002_residual_vs_iter11_h2h.md) | Pre-registration template + filed protocols |
| [../governance/TRAINING_OBSERVABILITY_SPEC.md](../governance/TRAINING_OBSERVABILITY_SPEC.md) | Phase-B training observability spec |
