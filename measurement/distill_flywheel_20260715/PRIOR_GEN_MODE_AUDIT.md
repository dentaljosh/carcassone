# Prior gen-mode audit — were all earlier training attempts clairvoyant?

**Date:** 2026-07-16 · **Type:** read-only historical audit (no code/jobs touched)
**Question:** did any prior self-play / flywheel / RL TRAINING attempt train on FAIR
(blind / root-determinization) gen, or was the entire neural lineage clairvoyant-trained
(self-play that steps the engine's TRUE pre-shuffled deck)?

---

## 1. One-line verdict

**YES — every prior neural TRAINING attempt that produced a checkpoint used CLAIRVOYANT
(true-deck) generation.** No earlier full flywheel (gen+train, ≥1 iter) ever trained on
fair gen. `gen_fair_selfplay.py` was a VALUE-ONLY offline side experiment (C-cheap), never
a gen+train policy loop. The distill flywheel now running (`gen_fair_distill.py`,
2026-07-15) is therefore the **first fair-trained net lineage** in the project.

---

## 2. The crux — proof for the main self-play loop (clairvoyant by construction)

The whole lineage routes gen through
`run_selfplay_iter.py → selfplay.play_one_selfplay_game → NeuralMCTS`. Three facts settle it:

1. **The MCTS descends the engine's true future deck.** `src/carcassonne_ai/mcts.py:439`
   defaults `fair_chance: bool = False`, and the docstring/comment states it outright:
   - `mcts.py:18-21` — *"Tile draws use the engine's pre-shuffled deterministic deck.
     **No POMDP-style re-shuffling at chance nodes** … our MCTS-vs-MCTS games **fix the
     deck at game start.**"*
   - `mcts.py:450-453` — *"by default every simulation descends along the actual upcoming
     tiles (single-determinization / perfect-info search — **the agent 'sees' future
     draws**)."*

2. **The self-play loop never passes `fair_chance`.** In `selfplay.py`, both MCTS
   instances are built without the flag, so it defaults to `False`:
   - `selfplay.py:208` `learner_mcts = NeuralMCTS(game=…, evaluator=…, …)` — no `fair_chance`.
   - `selfplay.py:231` `anchor_mcts = NeuralMCTS(…)` — no `fair_chance`.

3. **The loop advances the REAL engine board (true deck), never re-determinizes.**
   - `selfplay.py:503` `board, _ = game.get_next_state(board, action)` — the only state
     advance in the move loop; it steps the once-shuffled engine deck.
   - Confirming grep: `fair_chance|determiniz|reshuffl` in `selfplay.py` **and**
     `run_selfplay_iter.py` → **zero hits.**

Repo-wide, `fair_chance=True` / PIMC re-determinization appears **only in eval/diagnostic
probes** (`scripts/clairvoyance_gap.py`, `scripts/diag_clairvoyance.py`,
`scripts/clairvoyance_step0_sentinel.py`), never in any gen-or-train path.

That single fact — the production loop always advances the true engine deck and only ever
constructs `NeuralMCTS` with the default `fair_chance=False` — settles the entire neural
lineage below, because every checkpoint-producing attempt uses this same loop (directly, or
via `gen_step2.py` which calls the same `play_one_selfplay_game`).

---

## 3. Per-attempt table

Legend: **CLAIRVOYANT** = agent steps the engine's true pre-shuffled deck during search
(standard AZ self-play here). **FAIR/PIMC** = per-move re-determinization of the unseen bag.
**Supervised-heuristic** = static-heuristic labels on true-deck games (no deck-descending
search at all, so neither clairvoyant-search nor PIMC).

| Attempt | Gen entry point | Gen mode | Evidence |
|---|---|---|---|
| `warmstart_canonical.pt` | `generate_warmstart_smoke.py` → `warmstart.py` labeler | **Supervised-heuristic** (1–2 ply `virtual_score` labels on true-deck games) | `warmstart.py:6-8,205-251`; `CHECKPOINT_LINEAGE.csv` row = *"n/a (supervised warmstart, not self-play replay)"* / *"no self-play; heuristic-labelled corpus"* |
| `warmstart_sighted.pt` (M2) | same labeler, `--sighted` | **Supervised-heuristic** (sighted 81ch/42-scalar input rep; still no fair determinization) | `SIGHTED_SCOPE.md:24-25,136` — *"fresh heuristic warmstart (no self-play / residual / deck baggage)"* |
| v1–v6 self-play recipes | `run_selfplay_iter.py` → `play_one_selfplay_game` | **CLAIRVOYANT** | §2 crux (`mcts.py:18-21`, `selfplay.py:208,503`) |
| `v25_retrain` / `v25_retrain_iter01` | `run_selfplay_iter.py` → `play_one_selfplay_game` | **CLAIRVOYANT** | §2 crux — leaf/cap variants of the same loop |
| Option B (`score_diff` value targets) | `run_selfplay_iter.py --value-target score_diff` | **CLAIRVOYANT** | `value_target` is a label-encoding knob (`selfplay.py:70-160`); gen/step semantics unchanged |
| deepteacher / `v25_retrain_deepsearch` (sims=800) | `run_selfplay_iter.py --sims 800` | **CLAIRVOYANT** | only the sim budget differs; same true-deck loop |
| `flywheel_residual_attempt1` + **attempt2 (champion iter8)** | `run_residual_flywheel.sh` / `_v2.sh` → `run_selfplay_iter.py --value-target residual` | **CLAIRVOYANT** | `run_residual_flywheel*.sh` kills `run_selfplay_iter` + trains `train_iter.py`; residual target computed in-loop (`selfplay.py:444-476`) on the same clairvoyant search. Current champion (`governance/PRODUCTION.yaml`) |
| `rod_v2` flywheel | `rod_v2/run_rod_v2_flywheel.sh` + `gen_flywheel_v29.sh` → `run_selfplay_iter.py` | **CLAIRVOYANT** | `gen_flywheel_v29.sh:76,80` invoke `run_selfplay_iter.py` |
| `rod_v28` flywheel | `rod_v28/run_overnight_flywheel.sh` → `run_selfplay_iter.py` | **CLAIRVOYANT** | `run_overnight_flywheel.sh` kills `run_selfplay_iter` + trains `train_iter.py` |
| M2 sighted experiments (`m2_sighted/ckpt/iter_00..04`) | `canonical_az/run_m2_loop.sh` + `gen_m2_orch.sh` → `run_selfplay_iter.py` | **CLAIRVOYANT** (sighted = input rep, NOT fair determinization) | `run_m2_loop.sh:196`, `gen_m2_orch.sh:60` call `run_selfplay_iter.py`; DECISIONS 2026-07-03 "M2 KILL"/CL-039/CL-042 |
| PeNS / step-2 | `step2_pens/gen_step2.py` → `play_one_selfplay_game` | **CLAIRVOYANT** | `gen_step2.py` — *"runs N games via the PRODUCTION `play_one_selfplay_game`"*; DECISIONS CL-038 |
| **C-cheap** | `canonical_az/gen_fair_selfplay.py` → `train_value_only_sighted.py` | **FAIR/PIMC — but VALUE-ONLY, never a policy flywheel** | see §4; DEAD CL-049 (v1 W0/L100) / CL-050 (v2 NULL) |
| **distill flywheel (2026-07-15, RUNNING)** | `distill_flywheel/gen_fair_distill.py` → `run_distill_stage1.sh` | **FAIR / blind-PIMC — full gen+train POLICY flywheel (the FIRST one)** | see §4/§5 |

Non-training gen entries (not part of any lineage): `post_search_residual/gen_mcts_selfplay.py`,
`deeper_search/*`, `strategic_ladder/gen_*`, `level2/gen_endgame_*`, `window_audit/gen_games.py`,
`midgame_reference/*` — these build labeled position suites or run evals; none feed a policy
training loop.

Note: one row in `experiments/results.csv` (clairvoyance-gap eval, CL-022) records a
`fair_chance=TRUE` K=12 root-determinization arm — but that is an **evaluation** of the
finished champion iter8, not a training-gen run.

---

## 4. Resolving `gen_fair_selfplay.py` — value-only, never a flywheel

`scripts/canonical_az/gen_fair_selfplay.py` is **VALUE-ONLY** and was **never wired into a
gen+train loop**:

- Docstring `gen_fair_selfplay.py:2` — *"net-free FAIR self-play emitter for deck-aware
  **VALUE labels**"*; `:20-23` — emits a `warmstart.GameDataset` .npz with **`aux_mask=False`
  (VALUE-ONLY rows — dummy policy/ownership/mask … the policy priors stay the heuristic
  softmax at play time and are never learned here)**.
- Code confirms it: `:234` `policies=np.zeros(...)  # value-only dummy`, `:236`
  `valid_masks=np.zeros(...)  # dummy`, `:238` `aux_mask=np.zeros(N)  # every row VALUE-ONLY`.
- **Its only consumer is the value-head-only trainer** `train_value_only_sighted.py`
  (`:22,101,173` name it as the input source). No flywheel `.sh`/driver imports or calls it.
- The C-cheap program that used it explicitly forbade standing up a flywheel and was run +
  killed as an offline value-head A/B: verdicts **CL-049** (v1 W0/L100 catastrophic) and
  **CL-050** (v2 NULL) — "C-cheap is DEAD."

So the answer to "did ANY prior FULL flywheel train on fair gen?" is **NO**, and
`gen_fair_selfplay.py` was never more than a value-only side experiment.

---

## 5. The one fair gen+train POLICY flywheel is new (this experiment)

The only fair-trained *policy* flywheel is `scripts/distill_flywheel/gen_fair_distill.py`
(created 2026-07-15/16), a **distinct, newer script copied from** `gen_fair_selfplay.py`:

- `gen_fair_distill.py:1-8` — *"records the blind-PIMC champion's POOLED visit distribution
  (**policy target**) + game-outcome value, for the distill-flywheel … distil the **blind
  PIMC** champion, NOT the clairvoyant one, to avoid strategy-fusion bias."*
- Teacher = `FairHeuristicPriorAgent` (blind PIMC), differing from the value-only emitter's
  legacy `FairHeuristicMCTSAgent`; it adds POLICY targets (the five addendum changes).
- Status: RUNNING as a measurement-only Stage-1 experiment (`STAGE1_STATUS.md`);
  `governance/PRODUCTION.yaml` is untouched.

---

## 6. Implication

Because every prior checkpoint-producing attempt trained on clairvoyant (true-deck) gen —
the production self-play loop always advances the real once-shuffled engine deck and only
ever builds `NeuralMCTS` with the default `fair_chance=False` — the current fair
distillation flywheel is the **first fair-trained net lineage** in the project. Any strength
comparison it produces is the first that removes the clairvoyant train / blind serve
information mismatch (the F-B2 issue) from the *policy*, not just the value head.
