# Value Resurrection Pilot — PLAN (Stage 0)

> **STATUS: PLAN / SCOPING (2026-06-28). Branch `rod_v2_flywheel`. DIAGNOSTIC ONLY.**
> No promotion, no PRODUCTION.yaml change, no checkpoint promotion, no RoD flywheel, no policy
> training, no new branch. Hard constraints per the experiment brief.

## The one narrow question

> **Can a learned value/ranking component beat the v2.9 leaf on held-out sibling child-state
> ordering** (and only then: improve NMCTS, and only then: improve games)?

This is the value problem MCTS actually needs solved — *rank these siblings* — not "predict the final
outcome." If yes → first component of a resurrected value/search flywheel. If no → learned value stays
dead; continue classical-evaluator / measurement / productization work.

## ⚠️ This substantially re-runs three concluded negatives — read before spending

| Prior | What it tested | Result |
|---|---|---|
| **CL-021 value-ranking kill-test** (`value_ranking/VALUE_RANKING_VERDICT.md`, 2026-06-18) | **Exactly this**: sibling sets (root + all legal children) labeled by a deep oracle; learned value/ranking gauged by held-out **Kendall-τ / top1 / pairwise / regret**. Targets: MSE, **listwise ListNet (=V4)**, attention, **advantage-centered (=V2)**. | **Every learned arm ranked siblings at τ≈0.03 vs the v2.7 leaf's τ=0.579.** "DISFAVORED, **not probe-limited**." **Scale-robust**: the production net trained on *millions* still ranks at τ=0.081 ≪ 0.58. A learned per-position value **scalar** cannot out-rank the structural leaf. |
| **b99c9ed Decision D** (`measurement/value_search_autopsy/`, 2026-06-27) | Is the residual value head (`v2.9_leaf + α·v_nn`) useful in search? | **Inert.** rs 0/0.25/0.5 indistinguishable; residual **never corrupts** the leaf ranking (I6: 107 wrong→right, 0 right→wrong). The residual framing is already null. |
| **Exact-endgame hybrid + L2-3 / K4** (`measurement/exact_endgame_hybrid/`, `measurement/level2/`) | Does *perfect* endgame value convert? | Exact endgame is **outcome-neutral** (sharper score margin, no winrate edge); the net plays the K=2/3/4 endgame **worst** of all agents. |

**Implication:** the pilot's working thesis ("the net was trained as a mushy outcome predictor; ask it
to rank siblings instead") is precisely what CL-021 tested and refuted. The honest prior is that this
pilot lands at **Decision B** (target exists — the leaf has regret — but the net cannot learn to beat it
offline), reproducing CL-021 against the v2.9 leaf.

### What is genuinely NEW here (the only reasons to run it)

1. **v2.9 leaf** (bmild_cap8) instead of v2.7 — a stronger leaf, so the residual remainder is the
   *harder, finer* part (cuts against success, but it is a different cell on the record).
2. **h6400_v2.9 teacher** (6400-sim HeuristicMCTS, config_hash `7fc930b82801cb43`) instead of CL-021's
   400-sim oracle — a deeper, cleaner teacher.
3. **Endgame focus + exact labels.** CL-021 used a 400-sim oracle and did not isolate K≤3. The one
   live hypothesis is **Decision F** (value works *only* in pre-endgame/endgame, where exact K=2/3
   labels remove all teacher noise and the horizon is short). This is the genuinely-novel sliver.

## Data inventory — Stages 1+2 are ALREADY ON DISK (no self-play / no search to build)

| Artifact | Rows | Teacher per-child Q | State | Use |
|---|---|---|---|---|
| `high_gap_distillation/scaled/qprobe_A/probe.jsonl` ∩ `pool_A.jsonl` | **10,067** sibling sets | **h6400_v2.9 `action_q`** (full per-child Q on 7250; partial on 2817 — unvisited children = effectively low-Q) | `replay_to(seed,ply)`; `checksum` verifies | **primary pilot dataset** |
| phase split of the 10,067 | endgame 3358 · pre_endgame 2238 · midgame 2238 · late_mid 1120 · opening 1113 | — | — | endgame/pre-endgame slice for the narrow pilot |
| `pool_B.jsonl` | 10,080 | **unlabeled** (would need a CPU h6400 pass) | yes | optional leakage-clean independent test set |
| `value_search_autopsy/data/miss_probe.jsonl` | 1,321 | h6400 `action_q` (gap≥0.02 biased, mp1925 band) | replay | auxiliary high-gap eval slice |

- **Teacher provenance verified** (`scripts/rod_v2/highgap/probe_signal_density.py`): HeuristicMCTS @6400,
  `heur_leaf="v2_7"`, leaf_cfg = v2.9 bmild_cap8, config_hash `7fc930b82801cb43`.
- **Reconstruction** (`scripts/level2/gen_endgame_positions.py:replay_to`): greedy `RuleBasedPlayer`
  replay from `seed` to `ply`; `string_representation(board)` must equal the row `checksum`.
- **Child enum + dedup**: `_deduped_children` (transposition collisions removed by `id(child)`);
  `action_id` indexing is identical to `Game.get_next_state(board, action_id)`. v2.9 leaf per child =
  `tanh(virtual_score_v2(child.state, child.state.current_player, cfg)/15)`, root-POV negated.

## Reusable harness (do NOT rebuild)

- `scripts/value_ranking_train.py` — arms A/B/C/C0/E; **ListNet listwise (V4)** + **advantage-centered
  (V2)** + MSE; by-game leakage split; gauge = held-out Kendall-τ + top1 + pairwise + regret. CLI:
  `--dataset --arm --rank-temp --ceiling-json --groups-per-batch --epochs --out`.
- `scripts/value_ranking_dump_dataset.py` / `_merge.py` / `_label_reliability.py` — dataset build +
  ceiling. Reuse; swap teacher labels to the existing h6400_v2.9 `action_q` (no re-search) and the leaf
  to v2.9.
- `scripts/rod_v2/value_search/{forced_move,classical_leg}.py` — child enumerate + v2.9-leaf-per-child
  scoring pattern.

## Staged gate sequence (cheapest-informative-first; STOP at the first failed gate)

| Stage | What | Cost / where | Gate → decision if fail |
|---|---|---|---|
| **0** | this plan | free | — |
| **1+2** | assemble 10,067 sibling sets (h6400 Q + v2.9-leaf per child) | **already on disk** + offline join | — |
| **3 — LEAF AUDIT** | does v2.9 leaf leave *learnable* signal? top1/τ/regret of v2.9-leaf vs h6400, by phase × gap-tier; proceed only if ≥1k held-out sets where leaf-top≠teacher-top **and** regret≥0.01 (substantial subset regret≥0.02, h6400/exact-confirmed) | **local CPU, ~15–25 min**, no orch | leaf matches teacher too well → **Decision A** (no target), STOP |
| **4** | train V1 (residual reg.) / V2 (advantage) / V3 (pairwise) / V4 (listwise softmax) / V5 (endgame-exact-heavy); **policy FROZEN** | single-GPU, local | — |
| **5 — OFFLINE GATE** | learned value **+ v2.9 must beat v2.9 leaf alone** on held-out sibling regret (≥15–20% regret↓, top1/top3 up, no ordinary catastrophe); α sweep {0,.05,.1,.25,.5,1} | local | no candidate beats leaf → **Decision B**, STOP (do NOT run NMCTS/games) |
| **6** | best candidate into NMCTS; α sweep + gated variants; root diagnostics on miss set / held-out / endgame | **rust orch, high W, local+laptop** | NMCTS no better → **Decision C** |
| **7** | tiny game screen vs h6400 / h3200 / iter04 (n=100–200 paired) | **rust orch, local+laptop** | search↑ but games flat → **Decision D**; games↑ → **Decision E** |
| **8** | `VALUE_RESURRECTION_DECISION.md` (A–F) | free | — |

**The orch+highW directive (local+laptop) applies to Stages 6–7 only** — and only if Stage 5 passes.
Everything up to the decisive offline gate is CPU/single-GPU and free of cluster spend. This is the
spec's own rule ("do not run games unless the value model first beats v2.9 leaf offline").

## Stop rules (decision labels)

- **A** — v2.9 leaf already matches teacher too well (no target). Stop at Stage 3.
- **B** — target exists, net can't beat leaf offline (the CL-021 prior). Stop at Stage 5.
- **C** — beats leaf offline but NMCTS can't use it. Stop at Stage 6.
- **D** — NMCTS improves but games don't (the root-metric trap, 4th instance). Stop at Stage 7, do not promote.
- **E** — games improve. First evidence for a resurrected value/search flywheel → stop for review.
- **F** — works only in pre-endgame/endgame → exact/endgame-gated value, not full-game replacement.

## Hard constraints (from the brief)

No change to v2.9 evaluator · no PRODUCTION.yaml change · no checkpoint promotion · no RoD flywheel ·
no policy distillation · no root-agreement as the main target · no final-W/L regression as the primary
value target · **freeze the policy** · no new branch mid-experiment · gate strength on GAMES, never on
root metrics (the lesson from Path-3 / sims-washout / b99c9ed).

## Artifacts (under `measurement/value_resurrection_pilot/`)

`VALUE_RESURRECTION_PLAN.md` (this) · `_DATASET.md` · `_LEAF_AUDIT.md` · `_TRAINING.md` ·
`_OFFLINE_RESULTS.md` · `_SEARCH_RESULTS.md` · `_GAME_RESULTS.md` · `_DECISION.md`.
