# OUTSIDE_REVIEW — Carcassonne AlphaZero/KataGo-style project

**Prepared for an external technical reviewer with no prior involvement.**
**Repo:** `/home/doctor/projects/carcassone` · **HEAD:** `fd9952e` (R1 fix `d472d10`) · **Branch:** `stage-b-wiring` · **Date assembled:** 2026-06-07

> **UPDATE 2026-06-07 — R1 was tested and CONFIRMED load-bearing.** After this
> package was assembled, we ran the corrective experiment for finding R1 (§11, A8):
> we gave `HeuristicMCTS` the matched **v2.7** leaf and re-ran the headline cell
> (`iter_01` vs HeuristicMCTS, sims=200, c=3.0, n=400 paired, seeds 700000+).
> **Result: +48.1 elo ± 17.5 (225W/5D/170L, 2.7σ)** — vs the buggy-baseline
> **+86.9** (opponent on the v1 leaf). **Matching the leaf cost ~39 elo (~45% of
> the headline).** The learned policy's edge over heuristic search is **real but
> ~half** what the headline claimed: **+48, not +87.** Row:
> `results.csv: r1_iter01_vs_heuristic_v27leaf_baseonly_s200_n400`. This does NOT
> overturn the relative/marginal findings (§7, §9) and it *sharpens* the
> "leaf-is-most-of-the-strength" thesis. (A caution worth recording: the n=70
> interim read was −55 elo — small-n noise that regressed to +48 by n=400, a live
> instance of the project's own "a lone screen is a noise signature" rule.)

> **How to read this package.** The goal is to make our mistakes findable, not to
> defend our approach. Throughout, **[FACT]** marks something checked in code or
> taken verbatim from `experiments/results.csv`; **[INTERPRETATION]** marks our
> reading of it, which you should distrust. Exact numbers, dates, commits, seeds,
> and file:line references are preserved. `UNKNOWN` means we could not determine it
> from the repo and did not infer it.
>
> Supporting files in this directory:
> `CODE_MAP.md`, `EXPERIMENT_LEDGER.csv`, `CURRENT_CONFIG.yaml`, `METRIC_DICTIONARY.md`,
> `KNOWN_ANOMALIES.md`, `REPRODUCTION.md`, `OPEN_QUESTIONS.md`, and `artifacts/`
> (raw `results.csv`, the two foundational audits, the correction plan, example
> `manifest.json`s). The repo itself is the primary evidence; we cite it by path.

---

## 1. Executive orientation

### The game
Carcassonne is a tile-laying board game. Players draw a random tile from a bag, place
it legally adjacent to the existing board, optionally place one of their limited
"meeples" on a feature of that tile (city, road, monastery, or **field/farm**), and
score features as they complete. Properties that matter for an AI:

- **[FACT] Stochastic draws.** Each turn the tile is drawn at random from the remaining bag. The bag *multiset* is known by deduction; the *order* is hidden.
- **[FACT] Two-consecutive-moves structure.** A turn is two engine actions: place tile (TILES phase), then place/skip meeple (MEEPLES phase). The same player moves twice in a row. This affects the negamax sign convention and FPU (§2, §11).
- **[FACT] Farms are the dominant, highest-variance scoring axis.** Fields are scored only at game end (3 points per completed city the field touches), they merge across the whole board, and majority control can swing large totals. The engine computes them via flood-fill (`FarmUtil.find_farm`).
- **[FACT] Delayed, sparse reward.** Most points land at completion or game end; a placement's value is realized many plies later.
- Scope locked to **2-player, Base game + Farmers** (River dropped 2026-06-02; no Inns & Cathedrals, Abbots, Big meeples). `CLAUDE.md`.

### The system we are building
An AlphaZero-style agent: a single ResNet with a **policy head** and a **value head**,
guided by **PUCT MCTS**, improved by **self-play → train → evaluate** iterations on a
3-box home cluster. `CODE_MAP.md` and §2 give the full pipeline.

### What is borrowed from where [FACT/INTERPRETATION]
- **AlphaZero:** the overall shape (policy+value net, PUCT, self-play, visit-count policy targets, Dirichlet root noise). Vendored reference: `az/` (suragnair/alpha-zero-general, used as reference, **not imported**).
- **KataGo:** the *aspiration* of auxiliary targets (ownership planes exist as a training-only aux head) and "value learned in the loop on its own search distribution." The KataGo-style in-loop value flywheel was attempted late (2026-06-04→07) and is the current frontier.
- **Domain-specific, NOT from AZ/KataGo:** the **hand-crafted `virtual_score` leaf** (after Ameneyro et al. 2020) that *replaces the net's value at every MCTS leaf* in production. This is the single biggest architectural divergence and the crux of everything below.

### Current definition of success [FACT]
"Genuinely superhuman play — beat strong/expert humans, aspirationally the world
champion, at 2-player Base+Farmers" (set 2026-05-28, **overriding** the original
project prompt, which had explicitly scoped superhuman *out* and named a position
analyzer as the win condition; see `docs/ORIGINAL_PROMPT.md` + `CLAUDE.md`).

### Current strongest model [FACT]
There is no single champion; "best" depends on the play-time `sims` and on which
ruler you trust:
- **Clean base-only game, policy:** `stage_b/ckpt/iter_01.pt` — **+86.9 elo / 4.9σ** vs HeuristicMCTS@200, n=400 paired (`results.csv: stage_b_iter1_vs_heuristic_baseonly_s200_n400`).
- **Value lever:** the **residual leaf** (`lever_seq/ckpt/residual.pt`, `CARCASSONNE_V25_RESIDUAL_SCALE=0.25`) — **+46.5 marginal** elo from the value head (pooled, z=2.29), validated out-of-lineage to heur@800.
- **Pre-Phase-0 (River-era) bests** `v25_retrain_optionB_iter1` (sims=200 plane) and `v25_retrain_deepsearch` (sims=800 plane) are superseded by the game change; iter_11's value collapsed to ≈ heuristic on the real game.

### Baselines [FACT]
- **HeuristicMCTS** — vanilla UCT + a `virtual_score` rollout-replacement, no learned policy. **The primary "non-saturated" yardstick.** ⚠ uses the **v1** leaf, not v2.7 (§5, §11 R1, anomaly A8).
- **Tier-1 `RuleBasedPlayer`** — 1-ply argmax of v1 `virtual_score`. The "saturated" baseline (a thinking human beats it ~2/3).
- vanilla MCTS (random rollouts), random — used only in `eval_rule_player.py`.
- **[FACT] No above-amateur or human reference exists anywhere in the repo** (searched all eval code).

### Where progress plateaued [FACT]
On the clean base-only game, **+87 elo vs HeuristicMCTS is a wall**: three cheap
levers to exceed it (policy iteration, value-blend at play time, test-time depth vs a
fixed reference) all fail (§6). The learned **value head** cannot be used as a search
leaf without large losses (−24 to −604 elo as its weight rises), at every correlation
level it was trained to. The one positive value result (residual, +46.5 marginal)
"raises the ceiling ~1 doubling" but does not break it.

### Central symptoms that triggered this review [INTERPRETATION]
1. A "+181.7 / 9.2σ trustworthy absolute signal" collapsed to +25.2 / 1.45σ from a ruleset+bugfix change (A1) — i.e. our most confident number was mostly artifact.
2. Every value-head rebuild raises outcome-correlation and changes nothing about strength (A2).
3. Self-anchored / lineage-relative gains repeatedly fail to translate to the independent ladder (A4).
4. We cannot, with any current instrument, distinguish strong-amateur from world-champion — the ruler ends at amateur.

---

## 2. Current end-to-end system

Each item: what it is, where it lives, and the **exact divergence from canonical AlphaZero/KataGo**.

### State representation [FACT]
- **Board:** `(78, 25, 25)` tensor, current-player POV. `board_repr.py:encode_board (:253-349)`. 78 planes: 16 edge-type one-hots × 4 sides, tile-present, shield, chapel/flowers, 6 internal road pairs, 6 internal city pairs, 5+5 normal-meeple slots (mine/opp), **4+4 farmer corner slots (mine/opp)**, 16 reference-tile edges (broadcast), 12 reference-tile internal pairs (broadcast), last-placed-tile position. Full table in `CODE_MAP.md`.
- **Scalars:** 10 (`features.py:104-137`): meeples mine/opp, score mine/opp, score-diff, tiles-remaining, current-player flag, two phase flags, game-progress. Normalizations: meeple/7, score/100, diff/50, deck/72.
- **Canonical form:** perspective by channel assignment + scalar sign, **no spatial mirroring** (`game_wrapper.py:296-312`).
- **Divergence:** farmers are encoded as **per-corner presence bits only** — there is **no plane for farm connectivity, no bag/tile-type histogram, no open-feature/closure-progress plane** (`board_repr.py`; foundational audit F-B3). The net is structurally blind to the highest-value scoring axis and to tile-counting.

### Action representation + legal moves [FACT]
- **2511 actions** (`action_space.py:71`): `25×25×4` tile placements (cell × rotation) + tile-pass + 5 normal-meeple sides + 4 farmer corners + meeple-pass. Phase-aware encode/decode (`:208-281`).
- Legal moves from the engine, with a wrapper-level cache (`game_wrapper.get_valid_moves`, `tests/test_legal_moves_cache.py`).
- **Divergence:** **no equivalent-action coalescing** — a rotationally-symmetric tile placement maps to multiple distinct action indices. Policy mass can split across equivalent slots; the MCTS C2 fix dedups in *search* but the *policy target* can still split (§11 R6).

### Network I/O [FACT]
- `CarcassonneNet` (`network.py:56`): stem conv → 6 ResBlocks × 96 filters → policy head (1×1 conv→4 ch→flatten 2500→concat scalars→`Linear(2510→2511)`) + value head (1×1→1 ch→625→concat scalars→`Linear→64→tanh`) + training-only ownership aux head (`(3,25,25)`, tanh).
- **7,411,887 params** (measured; the `network.py:3` docstring "~4M" is stale).
- **Policy target:** MCTS root visit distribution over deduped children (`mcts.py:559-576`), normalized; sampled at temperature for the played move.
- **Value target:** configurable (`selfplay.py`): production = `score_diff` = `tanh((p0−p1)/15)`, one terminal value sign-flipped per ply by current player. Alternatives: `score_diff_wide` (/40), `wl`, `search_value` (root.Q), `search_value_tree`, `residual` (searchQ − v2.7), `v2_7`.
- **Auxiliary target:** end-of-game per-feature ownership planes (`aux_targets.py`), `aux_weight=0.15`. **OFF in all three global-best checkpoints.**

### MCTS [FACT]
- **PUCT** (`NeuralMCTS._select_child_puct`, `mcts.py:878-908`): `argmax_a Q + c_puct·P·√N_parent/(1+N_child)`, `c_puct=1.5` default but **production runs c=3.0**.
- **FPU:** unvisited child gets `q=0` (legacy) unless `fpu_reduction` set, then `node.Q − reduction` (`:893-895`) — **without a POV sign flip** (§11 R4).
- **Root noise:** Dirichlet `alpha=0.3, eps=0.25`, mixed root-only once per fresh root (`mcts.py:478-486, 732-736`). **`alpha=0.3` vs measured optimum ~0.53** (F-C4).
- **Expansion/backup:** one evaluator call per leaf; priors sanitized to uniform-over-legal on bad input; value clamped to [−1,1]; **negamax backup** (W stored in each node's own POV, flipped when player differs; `:1022-1078`).
- **Leaf value:** in production, the net's value is **replaced** by `tanh(virtual_score_v2/15)` at every leaf (`evaluators.make_v25_value_wrapper`). `value_blend` λ and `residual_scale` blend net value back in.
- **Transposition table** keyed by `state_key`; nodes shared across paths (a DAG). C2 alias structure dedups symmetric-rotation collisions in NeuralMCTS selection + readout (`:498-524, 750-772`); **base/HeuristicMCTS selection left unchanged** (reference-ladder comparability).
- **Virtual loss** 1.0, only when `batch_size>1` (batched-eval MCTS).

### Chance / hidden info / multiplayer / scoring / terminal [FACT]
- **Chance: NONE — search is clairvoyant.** It descends the engine's true pre-shuffled future deck (`mcts.py:18-21, 966`). `fair_chance=True` (single-determinization reshuffle) exists but is used only by `diag_clairvoyance.py` and is **unsound vs the transposition table** (deck order not in the state key; `mcts.py:451`, F-B2b, D20).
- **Hidden information:** not modeled; the agent effectively sees future draws.
- **Multiplayer:** strict 2-player; engine rejects ≠2 players.
- **Scoring:** the engine's canonical scoring, with the tied-feature patch (all tied owners score full). **Terminal value** `tanh(diff/15)`, antisymmetric, tie → ±1e-6 (`game_wrapper.py:273-292`).
- **Partial games:** self-play caps at `max_plies=400` and **raises** rather than emitting mid-game value targets if a game doesn't terminate (`selfplay.py:427-431`).

### Self-play [FACT]
- `play_one_selfplay_game` runs MCTS per ply, records (board, policy, value-target, mask, scalars, ownership, group_id). **Learner-vs-anchor:** a frozen anchor (`iter_11`, anchor_fraction 0.3) plays some moves at τ=0/no-noise; **only learner moves are recorded** (`selfplay.py:204-225, 273, 327-407`).
- **Production self-play uses the v2.7 leaf** (`--leaf-eval v2_5`, `run_pathb_cluster_loop.sh:362`) → the **net value never drives a move** (F-B1, the root-cause finding). The policy targets come from a tree evaluated entirely by the heuristic.
- Temperature: τ=1 for the first 15 plies (game clock), then τ=0. No resignation, no truncation.

### Replay buffer + sampling [FACT]
- One `.npz` per game (8-array schema), atomic save. Training streams a **sliding window of the last 10 iterations** (`train_iter.py:198-210`, `--window 10`). **No recency weighting, no prioritization** — a 10-iter-stale position is sampled like a fresh one. Warmstart-mix by file-count ratio (0.0 in production).

### Training loop [FACT]
- `train_iter.py`: AdamW, **flat lr=1e-3** (cosine is opt-in, default off — G-T1), weight_decay 1e-4, **3 epochs**, batch 256.
- **Loss = `pol_loss + value_loss_weight·val_loss + 0.15·own_loss + rank_weight·rank_loss + center_weight·center_loss`** (`:574-580`). Defaults: value_loss_weight 1.0, rank/center 0.0. **Policy CE (O(2–6)) dominates value MSE (O(0.1–1)) ~5–10×** → the value head is gradient-starved by default (G-T2). NaN batches skipped; entropy-floor collapse guard.

### Gating / promotion [FACT]
- `run_pathb_cluster_loop.sh` (tracked snapshot): per-iter **gate vs HeuristicMCTS** (out-of-lineage, c=3.0, n=200); adopt iter N as new best only if `gate_elo ≥ best_elo + KEEP_MARGIN_ELO (10)`; **warm-from best-so-far**; plateau-stop after `MAX_FLAT`. Keep-best persisted in `loop_state.env`.
- **⚠ The tracked snapshot's own header (`:2-8`) warns the live copy at `~/run_pathb_cluster_loop.sh` may differ, and that earlier runs used an *advisory-only* gate (F-C3) that warm-from-prev unconditionally.** So historical chains may not have had the keep/reject ratchet (A4, §11 R8).

### Checkpoint lifecycle, move-selection, augmentation, parallelization [FACT]
- Atomic `.pt` save with config (`n_filters/blocks/scalars/...`); naming `iter_NN.pt`.
- `best_action` tiebreaks on **(Q, visits)** in eval but the **training target is argmax-visits** — eval and training can pick different moves (`mcts.py:533-535, 709-713`).
- Data augmentation: 4× rotation built (`board_repr/action_space/warmstart`), **default OFF**; reflection deliberately excluded (curved roads).
- Cluster: 3 boxes, orchestrator-OFF in production (CPU leaf is the bottleneck), per-box workers 14/10/20, shared-claim work-stealing, `nice -n 19`.

### Exact differences from canonical AlphaZero/KataGo [FACT/INTERPRETATION]
1. **The value head is replaced by a hand-crafted heuristic leaf in production self-play and play.** This is the defining divergence; it means the AZ value-improvement flywheel is OFF (F-B1).
2. **Clairvoyant search** (no chance nodes) in a stochastic game.
3. **No symmetry augmentation by default** (KataGo uses all 8; AZ-Go used reflections+rotations).
4. **No bag/connectivity/closure input planes** (KataGo is heavy on domain input features).
5. **Flat LR, value-loss unweighted** vs the usual scheduled LR and tuned loss weights.
6. **Self-anchored / heuristic-anchored evaluation**, no held-out strong reference.
7. **Dirichlet α not tuned to the action space** (0.3 vs ~0.53).

---

## 3. Known-good tests and invariants

Suite status [FACT]: `pytest tests/ -q` → **PASS, 1 skipped** at HEAD; **46 files, 332 `def test_` functions** (~363 with parametrization). The 1 skip is checkpoint-gated. Full catalog with per-test "what it does NOT prove" is long; the high-value summary:

| Domain | Representative tests | Proves | Does NOT prove |
|---|---|---|---|
| Farm scoring (C1) | `test_farm_dedup_c1.py` | `count_farm_points` == position-set-dedup reference over 40 games; old arithmetic would over-count | farm scoring vs **canonical rule values** on hand-built positions; **cross-process** determinism (the original bug was process-dependent) |
| MCTS visit dedup (C2) | `test_mcts_transposition_c2.py` | symmetric collisions deduped; visit vector shares no child; alias structure correct | that the **policy target the trainer consumes** equals the deduped vector |
| Value-in-loop (F-B1) | `test_value_in_loop_fb1.py` | `value_blend=0.9` vs `0.0` changes the search (net value reaches the leaf) | that production *uses* net value (it doesn't, λ=0); that value *improves* search — only that it *changes* it; uses a **stub** value, not a real net |
| Invariants | `test_invariants.py` | `v(p0) == −v(p1)`, bounds, idempotent moves, rejects 4p/Inns/Abbots | that **higher engine score → value > 0** (sign-to-winner mapping untested) |
| Virtual score | `test_virtual_score.py`, `test_virtual_score_v2.py` | v2.7 antisymmetry, caps, dedup, matches v1 at init/terminal | leaf score vs **canonical point values** (only a 2-tile road = 2pts is hand-checked) |
| Self-play data | `test_selfplay.py` (24) | all 8 value-target encodings, sign invariant, interior rows, group ids | value-target **quality**; runs on stub evaluators, never a real net |
| Symmetry | `test_symmetry_aug.py` (16) | rotation equivariance of board/action/policy, hand-derived direction pins | reflections; that augmentation **helps** training |
| Elo | `test_elo.py` | formula symmetry, ±800 cap, round-trips | any confidence-interval / n-threshold logic (lives in docs, not code) |
| Network | `test_network.py`, `test_global_pool.py` | shapes, tanh bounds, param count 6–9M, masked softmax, autograd | **calibration/correctness** of outputs vs any target |
| Eval server | `test_eval_server*.py` | remote == local to 1e-5, concurrency safe | checkpoint-gated → **skips silently in a clean checkout** |

**Top coverage gaps [FACT]** (from `docs/TEST_SUITE_GAP_ANALYSIS_2026-06-03.md` + agent audit):
1. **No cross-process scoring-determinism test** (gap #4, OPEN) — the exact failure class of the 2026-05-29 farmer-adjacency bug.
2. **No tied-feature-scoring test** (gap #5, OPEN) — the engine patch that pays all tied owners full points has zero coverage.
3. **No value-sign/winner-perspective test** — only `v0 == −v1` and bounds.
4. **No "search beats raw policy" test** — nothing asserts search *improves* play (only that priors/value *change* it).
5. **No engine-scoring-vs-canonical-rules test** on hand-built positions (only one 2-tile road).
6. **All MCTS/self-play tests use stub evaluators** — in a clean checkout, **no test exercises the real trained net inside MCTS or self-play**.
7. **No training-converges test** — loss plumbing only, never "a step reduces loss / improves the net."
8. Three `scripts/verify_*.py` (C1, C2, shared-claim) are **not in the pytest tree** — not regression gates.

**[INTERPRETATION]** The suite is strong on *plumbing invariants* (shapes, antisymmetry, dedup, schema) and weak on *semantic ground truth* (does the score match the rules, does search help, does the sign map to the winner, is it deterministic across processes). For an AI whose correctness bugs have historically been *semantic* (farm double-count, transposition, start-dependence), the gaps are exactly where past bugs lived.

---

## 4. Experiment ledger

The complete, raw, authoritative per-run table is `artifacts/results.csv` (110 rows,
2026-05-24 → 2026-06-07). An **enriched, chronological** ledger with hypotheses,
confounds, reproduction status, and alternative interpretations is
`EXPERIMENT_LEDGER.csv`. Read both; this section is the narrative spine and the
warnings.

**[FACT] Structural caveats on the whole ledger:**
- `results.csv` **starts 2026-05-24.** Everything before (Phase 0–3, the v1–v6 era, the leaf v1→v2→v2.5→v2.7 evolution, the first retrain chain) predates the table and is reconstructed from `DECISIONS.md` — `code_rev = UNKNOWN` for all of it, **not reproducible to a commit**.
- `DECISIONS.md`'s latest dated entry is **2026-06-03**; the 06-04 → 06-07 arc (scaling curve, C4a/C6 probes, value-loss levers, flywheel, odometer) lives in `STATUS.md` + git log + `results.csv` only.
- **`game` column splits river vs base** — numbers are **not comparable across** the 2026-06-02 change. Rows 2–61 of `results.csv` are `game=river`; 63+ are `game=base`.

### Milestone timeline [FACT for numbers, INTERPRETATION for "meaning"]
The full table is `EXPERIMENT_LEDGER.csv`. Compressed:

- **2026-04 (Phase 0–3):** measurements (window 25, action 2511, α~0.53), reward norm `/15`, engine patches; `warmstart_canonical.pt` (6×96 ResNet, 100K heuristic positions) — **T1 88%, T2 31%, both below the prompt bars**, promoted anyway and Phase 3 closed.
- **2026-05-03→13 (v1–v6 NN-value-leaf era):** chain elo rose to +176/+612 but **anchored vs a fixed reference, −330** (the foundational anchor-before-scaling lesson, 2026-05-10). v6 `iter_12` = 70% vs warmstart but **Tier-1 (1-ply) beats it 75%** → the entire NN-value line is below the labeler. **All superseded.**
- **2026-05-14 (the leaf discovery):** swapping the NN value for a `virtual_score` leaf flipped Tier-1 win-rate **75%→40%** (35pp from one knob). Leaf evolution: **v2 (30%, failed — tanh saturation) → v2.5 cap=5 (83%) → dedup bug fix shifts cap=5→cap=12 → v2.7 drop-3-open cap=12 (90%)**. The dedup fix is the canonical "bug-fix-shifts-optima" case.
- **2026-05-15→17 (retrain chain):** `v25_retrain` iter_00 (+21pp) → iter_01 (+13.3) → **iter_02 flat (+0.2, confirmed null at n=400)**. Policy saturated against the fixed leaf.
- **2026-05-18→20 (search + Option B):** sims ladder — net is under-searched, knee at sims=800. **iter_B1 (score_diff value) +25.2/1.5σ** (recovered from an n=100 false-null), **deepsearch +35.8/2.0σ at sims=800**. These two become the sims-200 and sims-800 plane bests.
- **2026-05-24→26 (chain + c_puct):** Option-B chain B2–B4 looked positive per-step but **B4 vs iter_01 = −19.1** → Option B chain dead. **c=3.0 "+47.2/2.8σ"** headline.
- **2026-05-28→29 (goal + hygiene):** **goal → superhuman**; `results.csv` established as source of truth; **the +47.2 re-validated at n=1600 → +18.5** (40% regression-to-mean); **farmer-adjacency engine bug fixed** (~2.2% of games mis-scored).
- **2026-05-31 (Path B + first ladder):** value-head corr 0.18→0.81 (mechanism), per-iter +190 **self-anchored**. Pure-NN leaf = **−800 (calibration cliff)**, graceful at low blend. **iter_11 vs HeuristicMCTS (River) = +181.7/9.2σ** — read as the first absolute signal.
- **2026-06-01 (anchor-fraction):** iter_4 "+39 over iter_11" (c=1.5) but **tied on the independent ladder (−16.6) and at c=3.0 (+11.8)** → anchor-overfit + c-artifact, not real.
- **2026-06-02 (audit + bugfix + re-baseline):** 6-agent audit (2 live bugs + 6 caps); C1/C2 fixed, River dropped; **iter_11 collapses to +25.2/1.45σ on the clean game** (from +181.7). Verdict sweep: **c_puct + cap FLAT, FPU the one live lever (+45 screen, unconfirmed)**.
- **2026-06-03 (depth):** **iter_11 vs HeuristicMCTS @ sims=800, n=1143 = +56.7/5.5σ** — policy edge **grows with depth** (25→57 as sims 200→800).
- **2026-06-04 (Stage B):** **clean-data policy retrain iter_01 = +86.9/4.9σ** (the real win); **value-in-loop HURTS** (every λ>0 → ~+35); **value-at-play-time craters** (λ0.5 → −123); **policy_scale iteration ERODES +87 → +38**; scaling curve flat-top is a **weak-ref artifact**; **C4a + C6 probes both REFUTED**.
- **2026-06-05→07 (value-loss attack):** value ranks siblings at **chance (τ 0.08 vs v2.7 0.58)** regardless of target → "loss form is the problem"; ranking-loss sweep **helps but insufficient** (all 6 marginal<0); **Lever 1 residual = +46.5 marginal (z=2.29), first asset-positive learned value**; Lever 2 centered = −62 (failed); **Lever 3 flywheel = NULL for compounding**; **odometer: residual margin survives to heur@800 (+47.5), washes out at heur@3200; ceiling raised ~1 doubling, not broken.**

**[INTERPRETATION] The two recurring failure shapes you should look for in the table:**
(a) a single n=100–200 screen at z≈1.4–1.9 promoted to a "finding," later corrected at large n (c=3 +47→+18; c=2.0 +18pp→reversed; iter_B1 null→+25); (b) a *relative/self-anchored* gain that vanishes against an independent reference (Option-B chain, anchor-fraction iter_4, policy_scale).

---

## 5. Evaluation system audit

### How strength is measured [FACT]
- **Opponents:** HeuristicMCTS (primary), Tier-1 RuleBasedPlayer, vanilla MCTS, random. **No above-amateur or human reference** (searched all eval code).
- **Elo:** `400·log10(score/(1−score))`, draw=½, **±800 clamp** (`elo.py:22-44`).
- **σ:** unpaired binomial delta-method (`eval_net_vs_heuristic.py:194-200`); near wr=0.5: n=100 ≈ ±35, n=400 ≈ ±17, ±9 needs n≈1500.
- **Seat balancing:** `net_player = i%2`. **Deck pairing** optional (`--paired`: same deck both colors); **default unpaired** → net-as-p0 (even seeds) and net-as-p1 (odd seeds) use **disjoint deck sets** (G-M2). Pairing cancels first-player advantage and ~halves variance.
- **Seeds:** deck = f(seed) via global `random.shuffle`. Eval floors: ladder 600k, odometer 800k, head-to-head 1e9.

### Ways the evaluation can conceal or manufacture progress [FACT + flags]
1. **[FACT, A8/R1] The yardstick uses a different leaf than the agent.** `HeuristicMCTS._rollout` (`mcts.py:298-304`) = **v1** `virtual_score`; the neural agent's leaf = **v2.7** (`make_v25_value_wrapper`). Docstrings (`mcts.py:288`, `eval_net_vs_heuristic.py:6,9,156`) claim both are v2.7. So "+25/+57/+87 vs HeuristicMCTS" confounds the learned policy with the v2.7-vs-v1 leaf gap. **This is the single highest-leverage evaluation concern and it is undocumented anywhere outside this package.**
2. **[FACT, A9/G-M6] Eval seed floors overlap self-play seeds.** seed 600000 = iter-60 self-play deck; 800000 = iter-80. Only the head-to-head script was bumped to 1e9; the ladder + odometer were not. Runs that trained past those iters may be evaluated on **trained-on decks**.
3. **[FACT] σ ignores pairing.** The reported σ is the unpaired binomial even under `--paired`; verdict z-values are computed off it. Treat z within ±0.3 of a threshold as unresolved.
4. **[FACT] ±800 clamp + small-n screens.** Many promoted findings are single n=100–200 screens at z≈1.4–1.9; the project's own "noise signature" rule says these are not findings, yet the workflow repeatedly promoted them (A6).
5. **[FACT] Manifest records the checkpoint *path*, not a content hash** (`run_manifest.py`); `leaf_env` omits `residual_scale`/`opp_cap`/etc. Two runs with a swapped checkpoint or different residual scale can produce identical-looking manifests. `ladder_asymmetric.py` writes no manifest at the ladder level.
6. **[FACT] Historical scores are not comparable after the river→base change** (A1) or the farmer-adjacency engine fix (mid-stream). The `game`/`code_rev` columns were added *after* the collapse to detect this going forward; older rows are `code_rev=unknown`.
7. **[FACT] Self-anchored / lineage elo lies** — demonstrated repeatedly (A4). The ladder/odometer were built specifically because of this, but they still bottom out in the virtual_score family (so "out-of-lineage" ≠ "independent of the heuristic").

### Metric-improvement-without-better-play examples [FACT]
- Value-head corr 0.18→0.84 with **no** improvement in search usefulness (A2).
- Per-iter self-anchored "+190 elo" while absolute ladder strength was ≈ the heuristic (Path B; A4).
- "+39 over iter_11" (anchor-fraction) = a dead tie on the independent ladder.

### Does eval differ from training? [FACT]
- Training self-play uses τ-schedule, Dirichlet noise, anchor moves; eval uses τ=0, no noise. Both use the v2.7 leaf and (in production) c=3.0 — **except** the loop's net-vs-net confirm/verify path uses **c=1.5** (G-M4), so a checkpoint can be confirmed at a different search constant than it is gated/played at.

---

## 6. Training and search curves

**[FACT] What instrumentation exists** and where the data is:
- **Per-iter:** `experiments/iter_timings.csv` (selfplay/train/gate seconds, `gate_wr`, `value_corr`) — only `pathb_anchor` iters 0–6 are recorded (partial; some backfilled). `artifacts/iter_timings.csv`.
- **Value↔outcome corr:** printed each train iter (`train_iter.py:156-192`); the climb 0.18→0.81→0.84 is the most-tracked curve.
- **Policy entropy:** collapse guard; stable ~1.74 through policy_scale erosion (no exploration collapse).
- **Strength over time:** `results.csv` is the de-facto strength curve (per-run, not a smooth series).
- **Loss curves / grad norms / weight norms / LR / GPU-util / batch latency / game-length / score distributions / MCTS depth-branching:** **mostly NOT persisted as time series.** TensorBoard is a dependency but no run directory is checked in. Per-iter loss is printed to logs (largely on the CIFS share, not in-repo). **`UNKNOWN` whether grad/weight-norm curves exist anywhere.**

**[FACT] Curves we DO have, with their anomalous regions:**
- **Value corr (flat ceiling):** 0.464 (sims=200) vs 0.467 (sims=400) — flat; matches a from-scratch CNN (0.469) and the C4a probe (0.469 blind vs 0.447 +ownership). The "0.47 ceiling" was first read as an information ceiling, then **overruled** (it's corr with the noisy final margin, not the decision-useful gauge).
- **Test-time scaling Curve A** (iter_01@{50,100,200,400,800} vs fixed heur@200): **−74, +49, +35\*, +85, +70** (`results.csv: scalingcurve_*`). Steep climb out of search-starvation, **flat top** — declared a weak-fixed-reference artifact, not saturation (A3).
- **Reference-hardness Curve B** (iter_01@200 vs heur@{200,400,800}): **+35, −56, +10** — net@200 loses to heur@400 (compute race), noisy at n=100.
- **policy_scale erosion** (7 gates): **+45, +49, +17, +19, +31, +74, +33** → pooled +38±10 SEM, ~50 elo below the +87 parent (A4); the lone +74 (iter_05) reverted at iter_06.
- **Blend/cliff curve** (value weight in leaf): λ0 ≈ +56/+96, λ0.5 ≈ −24 to −38, λ1.0 ≈ −552 to −604 — a smooth monotone cliff reproduced across **four** value nets (A2).
- **Odometer** (residual margin vs opponent depth): +63.6 (h200), +47.5 (h800), −17.5 (h3200) — gain survives 4× depth, washes out at 16×.

**[INTERPRETATION]** The instrumented curves that exist are mostly *evaluation* curves; the *training-dynamics* curves (loss components, grad/weight norms, calibration over time, self-play game-length/diversity over iterations) that would diagnose A2/A4/A5 are largely **not captured**. This is itself a finding: the project cannot inspect its own learning dynamics.

---

## 7. Negative results and abandoned branches

Categorized by *why* they failed (the review's requested taxonomy).

**Clearly disproven [FACT]:**
- NN value head as the search leaf at any non-trivial weight (4 nets, λ-cliff to −552/−604; A2).
- Leaf v2 (un-capped bonuses, 30% vs Tier-1, tanh saturation).
- Option-B as a *chain* lever (B4 vs iter_01 −19.1).
- Centered-MSE value (Lever 2, marginal −62).
- C4a oracle-ownership input planes (0.469 blind vs 0.447 +own → no gain).
- C6 de-saturated value target (no ranking gain).
- Closure-probability accuracy as a leaf lever (deck-aware P, pooled 47.5%).

**Probably unhelpful [FACT/INTERPRETATION]:**
- Policy iteration warm-from-latest without a ratchet (erodes +87).
- value_blend at play time (monotone down).
- Ranking-loss value (helps — crater shrank −576→−358 — but all 6 configs marginal<0).

**Inconclusive — insufficient compute / not run to verdict:**
- FPU = 0.2/0.4 (two positive screens, neither ≥2σ, n=400 confirm never run).
- Residual flywheel compounding (2 iters from one baseline; "rules out STRONG compounding," can't resolve a <+12 climb).
- iter_01's own matched-depth scaling (deferred as multi-hour).

**Inconclusive — noisy evaluation:**
- The "c=3 +47" and "c=2.0 +18pp" spikes (regression-to-mean / pairing reversal).
- The deepsearch "plateau across 3 strategies" (partially retracted same day — off-plane measurement).

**Confounded by simultaneous changes:**
- Stage B "value-in-loop doesn't help": warm-from-iter_11 + held knobs + value-loss starvation (G-T2) all move together; a null does not cleanly falsify the mechanism (the auditor flagged this in the plan).
- The +181.7→+25.2 collapse bundled river-drop + 2 bug fixes + off-distribution.

**Abandoned for operational, not technical, reasons [FACT]:**
- Cloud (vast.ai) self-play — cost + bootstrap fragility; the orchestrator W=48/96 doctrine was a cloud artifact.
- Zenbook eval-server bridge (box died; slot-leak bug unfixed).
- River (scope decision, not a finding).
- The exact-chance-node rebuild (demoted by the n=76 clairvoyance screen — itself underpowered, A7).

---

## 8. Strange observations and unresolved anomalies

The full catalog with "fact / current explanation / still-unexplained" is
`KNOWN_ANOMALIES.md`. Index (A1–A10), in load-bearing order:

- **A1.** Same checkpoint, +181.7 → +25.2 from a "non-strength" change (the ruler is shakier than any single σ suggests).
- **A2.** Value corr 0.18→0.84 with zero search-usefulness gain — every time.
- **A3.** Search stops helping vs a fixed reference; artifact-vs-saturation unresolved for the current best net.
- **A4.** Old checkpoints tie/beat newer ones; no demonstrated multi-iteration absolute climb.
- **A5.** Flywheel iter1 regressed the *policy* ~50 elo; "co-adaptation destabilized" is a label, not a diagnosis.
- **A6.** Lone parameter spikes promoted to production, later shown to be noise — twice (and the pattern recurs in the live residual story).
- **A7.** Clairvoyance declared a non-lever on one underpowered n=76 River screen, yet it gates a whole demoted workstream.
- **A8.** The yardstick (HeuristicMCTS) runs a **different (v1) leaf** than the agent — undocumented; contaminates the most-cited numbers.
- **A9.** Eval seed floors overlap trained-on self-play decks (ladder/odometer unfixed).
- **A10.** Throughput "optima" reversed repeatedly (cloud vs local, fp16); compute-budget numbers not comparable across the project.

---

## 9. Current beliefs, explicitly labeled as hypotheses

Each: evidence for / against / assumptions / falsifier / confidence / origin.

### H1 — "The v2.7 hand-crafted leaf caps learned strength near strong-amateur."
- **For:** every learned-value-as-leaf attempt loses; policy retrains saturate against the fixed leaf; the +87 ceiling resists three levers.
- **Against:** the leaf has never been held *identical on both sides* of a strength eval (A8 — the opponent uses v1, the agent v2.7); the value verdicts are confounded by loss-weighting (G-T2). So "the leaf is the ceiling" has not been tested with the leaf actually controlled.
- **Assumes:** the vs-HeuristicMCTS measurements are valid (A8/A9 say partly not).
- **Falsifier:** a learned value (or a higher-capacity leaf) that beats v2.7 on a matched-leaf, uncontaminated, n≥400 paired eval.
- **Confidence:** medium-high. **Origin:** direct evidence, but repeated discussion has hardened it past what the (confounded) evidence strictly supports.

### H2 — "Outcome-correlation is the wrong gauge; a leaf must rank sibling moves."
- **For:** corr 0.84 head ranks siblings at τ=0.08; v2.7 (corr 0.61) ranks at 0.58 and is a good leaf; mimic-v2.7 under MSE → τ=0.08.
- **Against:** the value-loss was ~5–10× under-weighted (G-T2) in those runs; "MSE can't rank" was never tested with a properly weighted value loss. The residual lever (which *does* help) still uses an MSE-trained Δ head, complicating the "MSE can't rank" story.
- **Falsifier:** an MSE-trained value (properly weighted) that ranks siblings well; or a ranking-loss value that becomes a usable leaf.
- **Confidence:** medium. **Origin:** direct probe (τ), but the confound (G-T2) is unaddressed.

### H3 — "The clean-data policy retrain is the real, robust win (+87)."
- **For:** +86.9/4.9σ, n=400 paired, reproduced the n=200 screen exactly.
- **Against:** measured vs the (mis-leafed, possibly seed-contaminated) HeuristicMCTS; policy iteration on top of it *erodes* rather than climbs; warm-from-iter_11 mixes transfer with fresh retrain.
- **Falsifier:** A8/A9-clean re-measurement that drops +87 substantially; or a demonstration that +87 is the v2.7-vs-v1 leaf gap plus priors.
- **Confidence:** medium. **Origin:** direct, strongest single number, but inherits the ruler's flaws.

### H4 — "Future-sight (clairvoyance) is not a strength lever."
- **For:** clairvoyant-vs-fair n=76 = 0.474 (dead even).
- **Against:** n=76 is ±0.5σ resolution, River-only, never re-run on base; the fair path is itself unsound vs the transposition table (so the screen may not measure what it claims).
- **Falsifier:** a powered (n≥400, base) clairvoyant-vs-sound-chance comparison showing a gap.
- **Confidence:** low-medium. **Origin:** one screen + analogy; over-weighted relative to its power.

### H5 — "The residual value is a real but modest, non-compounding asset."
- **For:** +46.5 marginal pooled (z=2.29), inverted-U, survives out-of-lineage to heur@800.
- **Against:** z=2.29 is barely a verdict; σ doesn't credit pairing; the screen (+68) regressed to confirm (+35); the residual eval is **silently disabled in `eval_iter_head_to_head.py`** (R7) so any verdict routed through that script measured pure v2.7.
- **Falsifier:** a larger paired confirm collapsing it toward 0; or showing the gain is the policy, not the value.
- **Confidence:** medium. **Origin:** direct, the most carefully-replicated current result, still thin.

### H6 — "Measurement is the #1 blocker; we cannot see above amateur."
- **For:** no above-amateur reference exists; self-anchored elo lies; the ladder bottoms out in the heuristic.
- **Against:** none — this is nearly definitional.
- **Falsifier:** building any above-amateur instrument and finding it *does* track our existing gates.
- **Confidence:** high. **Origin:** direct + structural.

---

## 10. Potentially dangerous assumptions

Assumptions that may have become invisible because they are baked into code, docs, or terminology.

1. **[INTERPRETATION] That Carcassonne fits the deterministic-perfect-info AlphaZero frame.** Production search is **clairvoyant** (sees the future deck) — i.e. we solved the stochasticity by *deleting* it. The value head is then trained on single-future, high-variance outcomes it cannot reproduce from fair inputs. The whole "value can't learn" story may be partly "the value target is asking the net to predict a clairvoyant teacher's outcome." This assumption is embedded in `mcts.py` and never re-litigated after the n=76 screen.
2. **[INTERPRETATION] Multiplayer/value semantics in a two-consecutive-moves game.** The negamax sign convention and FPU assume alternating play, but tile→meeple is the *same* player twice. The audit says the negamax signs are correct; FPU's no-flip `parent.Q` (R4) is the place this assumption is least verified.
3. **[INTERPRETATION] Credit assignment via one terminal value per game.** `score_diff` assigns the *whole-game* margin to every learner ply, sign-flipped. Farms (decided at game end, board-spanning) make this an extremely noisy per-move label. The search-value targets were an attempt to fix this; they didn't help (A2).
4. **[FACT→INTERPRETATION] Policy-target quality.** The policy target is the visit distribution of a tree evaluated **entirely by the heuristic leaf** (F-B1). The policy can therefore only learn to imitate heuristic-guided search — a structural cap that "policy retrain saturates" is consistent with.
5. **[INTERPRETATION] Search/value consistency.** The value is trained on the self-play *trajectory* distribution but, when blended in, is queried on the *tree interior* it never saw (the −576 "distribution mismatch"). The flywheel was meant to fix this and was null.
6. **[FACT] Replay staleness.** 10-iter window, no recency weighting (§2). Combined with warm-from-best re-branching, the buffer can mix divergent policies.
7. **[FACT] Symmetry.** Rotation augmentation exists but is **OFF by default**; reflection is correctly excluded. 4× free data unused in the production lineage.
8. **[FACT, CRITICAL] Evaluation transitivity / the ruler.** "Beats HeuristicMCTS by X" is treated as an absolute-strength statement. But the ruler (a) uses a different leaf than the agent (A8), (b) can be played on trained-on decks (A9), (c) is itself only strong-amateur, and (d) is in the same heuristic family the "out-of-lineage" odometer also uses. **Almost every strategic decision rests on this ruler.**
9. **[INTERPRETATION] Compute-bottleneck assumptions.** "The CPU v2.7 leaf is the bottleneck" drove orchestrator-off; true, but it also means the system spends its compute running a *fixed heuristic* millions of times rather than improving a learned evaluator — arguably the bottleneck *is* the architecture choice.
10. **[INTERPRETATION] That "more search should help."** Asserted (the flat top is "an artifact"), but the current best net's matched-depth scaling is unmeasured, and at λ>0 more value-in-the-leaf *hurts*. Whether deeper search helps *this* net is open (A3).
11. **[FACT] That the baseline measures the capability we care about.** Tier-1 is a 1-ply heuristic a human beats 2/3; HeuristicMCTS is search over the same heuristic. Beating them is "stronger than what we built," explicitly **not** superhuman, yet it is the only thing every gate measures.

---

## 11. High-risk code areas

Prioritizing subtle *semantic* errors that could produce plausible-but-invalid learning or measurement. Each: file/function, why risky, tests, missing tests, excerpt/line, proposed independent validation.

### R1 [CRITICAL — measurement] HeuristicMCTS leaf ≠ agent leaf — ✅ CONFIRMED + FIXED 2026-06-07
- **RESOLVED:** measured impact = **+86.9 → +48.1 elo** (n=400 paired) when the opponent is given the matched v2.7 leaf — ~39 elo (~45%) of the headline was the leaf gap; the policy edge is real but ~half (+48, 2.7σ). Fix committed `d472d10`: `HeuristicMCTS(heur_leaf=...)` + `eval_net_vs_heuristic --heur-leaf` (default stays `v1` for back-comparability; pass `v2_7` to isolate the policy). Docstrings corrected. Row `results.csv: r1_iter01_vs_heuristic_v27leaf_baseonly_s200_n400`.
- **Where (the original defect):** `src/carcassonne_ai/mcts.py:298-304` (`HeuristicMCTS._rollout`) → `virtual_score_estimate` (`:266-274`) → `from .virtual_score import virtual_score` (**v1**). Agent leaf: `evaluators.make_v25_value_wrapper` → `virtual_score_v2` (**v2.7**).
- **Why risky:** the docstrings (`mcts.py:288`, `eval_net_vs_heuristic.py:6,9,156`) assert both sides use the v2.7 leaf; they do not. Every "vs HeuristicMCTS" strength number confounds the learned policy with the v2.7-vs-v1 leaf gap.
- **Tests:** none assert the two sides share a leaf. **Missing:** an eval-harness assertion that opponent leaf == agent leaf (or an intentional, documented mismatch).
- **Excerpt:** `diff = virtual_score_estimate(board, leaf_player); return math.tanh(diff / HEURISTIC_VALUE_NORM)` (`mcts.py:303-304`).
- **Validate:** re-run `ladder_iter11_*` and `stage_b_iter1_*` with HeuristicMCTS given the v2.7 leaf; report how much of +25/+57/+87 survives.

### R2 [HIGH — training] Value-loss starvation confounds every value verdict
- **Where:** `scripts/train_iter.py:574-580`. `loss = pol_loss + value_loss_weight*val_loss + ...`, default `value_loss_weight=1.0`; code comment admits policy CE dominates ~5–10× (`:569-573`).
- **Why risky:** "value-in-loop doesn't help / value can't rank" (a strategy-defining family of conclusions) was reached while the value gradient was 5–10× under-weighted.
- **Tests:** loss-plumbing only (`test_entropy_guard`, `test_flywheel_loss_masking`). **Missing:** any run isolating value_loss_weight.
- **Validate:** one value_loss_weight ∈ {1,3,5,10} sweep before any further "value can't X" conclusion.

### R3 [HIGH — measurement] Eval seed floors overlap self-play decks
- **Where:** `eval_net_vs_heuristic.py:245` (600k), `ladder_asymmetric.py:125` (800k); self-play seed `run_selfplay_iter.py:192-194` = `iter*10_000+game_idx`; deck = f(seed) via global shuffle.
- **Why risky:** train/test contamination inflates ladder win-rate for nets trained past iter ~60/80. Head-to-head was fixed to 1e9 (`eval_iter_head_to_head.py:543`), ladder/odometer were not.
- **Validate:** re-run one ladder rung at `--seed-start 1000000000`; compare.

### R4 [MED — search] FPU uses parent.Q with no POV flip
- **Where:** `mcts.py:893-895`: unvisited child `q = node.Q - fpu_reduction`. The visited branch flips POV (`:898`). In tile→meeple turns parent and child often share player, but where they differ the FPU is in the wrong POV.
- **Tests:** `test_neural_mcts.py` checks FPU *changes* search, not correctness of sign. Latent (prod uses legacy q=0). **Validate:** unit test asserting FPU POV matches the visited-child branch for both same- and different-player children.

### R5 [MED — data] Replay staleness + no recency weighting
- **Where:** `train_iter.py:198-210`, `--window 10`. **Validate:** log buffer-age distribution per train; A/B window∈{3,10} for monotonicity.

### R6 [MED — targets] Policy mass splits across equivalent actions
- **Where:** `action_space.py:101-109` (no coalescing); MCTS C2 dedups *search* (`mcts.py:498-524`) but the **policy training target** read by the trainer may still carry split mass for symmetric placements. **Missing:** a test linking the deduped visit vector to what `train_iter` consumes.

### R7 [MED — measurement] Residual leaf silently disabled in a key eval script
- **Where:** `scripts/eval_iter_head_to_head.py:238-247` (`_effective_blend` ignores `residual_scale`); gates at `:372-376, 740, 749` then take the policy-only path (`v_nn=0`) so `evaluators.py:189` computes `h + scale*0 = h`. Production self-play (`run_selfplay_iter.py:263, 788-789`) is correctly guarded; **only this eval script is affected.**
- **Why risky:** any residual verdict routed through `eval_iter_head_to_head.py` measured the **pure v2.7 leaf**, not the residual.
- **Validate:** audit which residual numbers used which script; the odometer (`ladder_asymmetric.py` → `eval_net_vs_heuristic.py`) is *not* affected; net-vs-net residual checks may be.

### R8 [MED — provenance] The gate logic that ran ≠ the tracked logic
- **Where:** `scripts/run_pathb_cluster_loop.sh:2-8` (header warns the live `~/` copy diverges; C7 keep-best was "PENDING"); `REVIEW_LOG.md:412-413` documents an older unconditional warm-from-prev advisory gate (F-C3).
- **Why risky:** whether a given historical chain had the keep/reject ratchet (vs random-walk warm-from-prev) cannot be determined from the repo. Attribution of chain results (A4) is ambiguous.
- **Validate:** diff the live `~/run_pathb_cluster_loop.sh` against the tracked snapshot; record which runs used which.

### R9 [MED — search] fair_chance unsound vs transposition table
- **Where:** `mcts.py:442-461` (reshuffle), `:451` (deck order not in key). Latent (only `diag_clairvoyance.py` uses it) but any future non-clairvoyant search is invalid until the key includes deck order/seed (D20).

### R10 [LOW — engine] `chapel_or_flowers_points` unguarded index
- **Where:** `points_collector.py` (G-R2) indexes `board[row][col]` with no bounds check near the grid edge. Latent (6-row margin).

---

## 12. Minimal reproductions

Full commands, expected ranges, and **UNVERIFIED** flags are in **`REPRODUCTION.md`**.
Summary of what each reproduces:
- **§0** suite sanity (pytest green, 1 skip).
- **§1** a complete game (random fuzz, 0 violations, overflow <5%).
- **§2** one MCTS decision (raw prior argmax vs searched-visit argmax vs Q-tiebreak `best_action`).
- **§3** one self-play game → one 8-array `.npz`.
- **§4** one replay sample (value∈[−1,1], policy a valid distribution over legal actions).
- **§5** one training update (prints loss components + value_corr, atomic save).
- **§6** one checkpoint eval vs HeuristicMCTS (writes a manifest; **⚠ opponent uses v1 leaf, R1**).
- **§7** raw-vs-searched policy comparison (`probe_decision_ranking.py`; value τ≈0.08 vs v2.7 τ≈0.58).
- **§8** the out-of-lineage odometer (residual margins +63.6/+47.5/−17.5).

---

## 13. Representative evidence

The cleanest machine-readable evidence is `artifacts/results.csv` (per-run W/L/D + config + seeds). Specific representative cases:

- **Competent play / a real gain [FACT]:** `stage_b_iter1_vs_heuristic_baseonly_s200_n400` — 245W/8D/147L vs HeuristicMCTS, +86.9 elo, n=400 paired, seeds 700000+ (`artifacts/results.csv`).
- **A recurring weakness — value as a leaf [FACT]:** the λ-cliff reproduced 4× (`searchval_s400_..._blend10` −576.2; `mimic_v27_..._blend10` −603.9; `searchval_tree_GP_..._blend10` −552.1; `step9_nnleaf_vs_v27` −800). Same shape every net.
- **A position where search *worsens* the decision [FACT]:** value-blend at play time — `scalingcurve_iter01_s200_h200_b50_base` = 33W/67L = −123 elo: adding the (correlation-0.8) value into the leaf made the searched move *worse* than the pure-heuristic searched move.
- **MCTS *improving* the raw policy [FACT, indirect]:** `sims_ladder` (DECISIONS 2026-05-18) — same net, sims 200→800 = +200 elo; and iter_11's ladder edge growing 25→57 elo as sims 200→800. (No single-position turnkey artifact; use REPRODUCTION §2/§7.)
- **A value-estimation failure [FACT]:** the decision-ranking probe — value τ=0.081±0.023 vs v2.7 τ=0.579 (STATUS Step A); a value with 0.84 outcome-corr that ranks sibling moves at chance.
- **A policy/eval upset / surprising regression [FACT]:** `ladder_iter4_vs_heuristic_n400` (+165.1) vs `ladder_iter11_vs_heuristic_n400` (+181.7) = −16.6, a "+39 over iter_11" gain that was a dead tie on the independent ladder. And A1: the same checkpoint at +181.7 then +25.2.
- **A policy-distribution anomaly [FACT]:** symmetric-rotation tiles split visit/policy mass (C2; `test_mcts_transposition_c2.py` constructs the collision).

**[FACT] Note on game records:** raw per-game JSON/`.npz` records live under `data/tournament/`, `data/selfplay/`, and (mostly) the CIFS share `/mnt/c/carc-shared/<run>/`. They are not bundled here (size); `src_dir` in `results.csv` points to each. A representative resolved config is `artifacts/example_manifest_odometer_h800.json`.

---

## 14. Questions for the outside reviewer

Please address, in order (standalone copy in `OPEN_QUESTIONS.md`):
1. **Is the reported plateau (+87 elo = hard ceiling) supported by the evidence**, given R1 (mis-leafed ruler) and R3 (seed contamination)?
2. **The three most likely root causes** of the plateau, ranked.
3. **Is there evidence of a correctness bug** invalidating learning? (Top suspects: R1, R2, R3, R4.)
4. **Which current assumptions are least justified?** (§10; we suspect H2 "MSE can't rank" and H4 "clairvoyance isn't a lever.")
5. **Which results have been overinterpreted?** (Candidates: residual +46.5; the "ceiling raised ~1 doubling"; the −576 cliff as a general claim about value heads.)
6. **What crucial evidence is missing?** (We think: an above-amateur reference; matched-depth scaling for the current net; an A8/R1-clean re-run; a G-T2/R2 isolation.)
7. **Highest-information, lowest-cost diagnostics** to run first.
8. **Which experiments should we stop running?**
9. **Is the architecture fundamentally reasonable** for a stochastic, farm-dominated, two-consecutive-moves game — or is clairvoyant-PUCT-over-a-hand-crafted-leaf a poor frame (§10.1)?
10. **What would you do in the next three experimental cycles?**
11. **Under what results should we abandon or substantially redesign** the current approach?

---

## 15. Evidence inventory

| Artifact | Where | Relevance | Current? |
|---|---|---|---|
| `results.csv` (raw, 110 rows) | `artifacts/results.csv` (= `experiments/results.csv`) | **authoritative experiment numbers** | yes (to 2026-06-07) |
| Enriched ledger | `EXPERIMENT_LEDGER.csv` | chronology + hypotheses + confounds | yes |
| Foundational audits (round 1+2) | `artifacts/foundational_audit_2026-06-02*.md` | the F-* and G-* findings (2 live bugs + caps + measurement/training gaps) | yes |
| Correction plan | `artifacts/CORRECTION_PLAN_2026-06-02.md` | the staged A/B/C plan | yes (06-02) |
| Example manifests | `artifacts/example_manifest_*.json` | resolved per-eval config format | yes |
| iter timings | `artifacts/iter_timings.csv` | the only per-iter time/corr series (pathb_anchor 0–6, partial) | partial |
| Live state | `../STATUS.md` | current verdict + the 06-04→07 arc | yes |
| Decision log | `../DECISIONS.md` (~310 KB) | every dated decision + why (to 2026-06-03) | mostly |
| Roadmap / backlog | `../EXPERIMENTS.md`, `../BACKLOG.md` | open/closed/killed ideas | yes |
| Code-review log | `../REVIEW_LOG.md` | F-items fixed, D-items deferred (incl. D15/D20) | yes |
| Test-gap analysis | `../docs/TEST_SUITE_GAP_ANALYSIS_2026-06-03.md` | gaps #4 (cross-proc) #5 (tied-scoring) OPEN | yes |
| Ceiling probes | `../docs/CEILING_AND_C4C6_2026-06-04.md` | C4a/C6 refutations | yes |
| Value-loss plan | `../docs/VALUE_LOSS_ATTACK_2026-06-05.md` | the residual-lever rationale | yes |
| Source code | `../src/carcassonne_ai/`, `../scripts/`, `../engine/` | the system itself (see `CODE_MAP.md`) | yes (commit fd9952e) |
| Checkpoints (pre-Phase-0) | `../checkpoints/` | warmstart_canonical, v25_retrain*, deepsearch, iter_B1 | superseded by game change |
| Checkpoints (Stage-B / levers / residual) | `/mnt/c/carc-shared/{stage_b,lever_seq,flywheel_residual}/ckpt/` | the current bests | on CIFS share, not in repo |
| Raw game/eval dirs | `../data/`, `/mnt/c/carc-shared/<run>/` (see `src_dir`) | per-game records, per-eval manifests | mixed |
| Original prompt | `../docs/ORIGINAL_PROMPT.md` | the superseded win-condition | historical |

**[FACT] Not in this package (and why):** raw `.npz` self-play corpora and per-game tournament JSON (size; pointers in `results.csv:src_dir`); TensorBoard/loss time-series (not persisted in-repo — see §6); the live `~/run_pathb_cluster_loop.sh` (untracked; R8); the on-share checkpoints (CIFS, may be unmounted).

---

### Second-pass self-audit (what a skeptical reader should still distrust in THIS document)
- The HeuristicMCTS-leaf finding (R1/A8) is from a code read confirmed by the main thread (`mcts.py:298-304`), but we have **not** run the corrective experiment — its *impact* on the headline numbers is inferred, not measured.
- Many "verdicts" cited as facts are single screens or barely-2σ results; we have tried to label confidence, but the project's own history (A6) shows we are prone to promoting these.
- The pre-2026-05-24 numbers are reconstructed from `DECISIONS.md`, not `results.csv`, and are `code_rev=unknown`.
- Where the share was unmounted we could not re-read raw eval dirs; those numbers come from `results.csv` notes written at the time.
- "ABSENT (searched X)" claims (no bag plane, no human reference, no resignation) are from code searches by exploration agents; a reviewer should grep to confirm any one that matters to their conclusion.
