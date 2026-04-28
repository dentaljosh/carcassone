# Carcassonne AI — Claude Code Project Prompt

> Verbatim copy of the project spec Joshua wrote on 2026-04-27. Do not edit; treat as source-of-truth for the project's goals, scope, and phase structure. Decisions made along the way (which override or refine this spec) live in [DECISIONS.md](../DECISIONS.md).

---

**Author:** Joshua Ishal
**Goal:** Build a Carcassonne AI strong enough to give me and the kids a real fight, and (more interestingly) to analyze our family games and tell us what we should have done differently.
**Hardware:** Workstation with RTX 5060 Ti 16GB, WSL2/Ubuntu dev environment.
**Build environment:** Claude Code.

---

## Read this first

### Trust boundaries

The phases below contain **specific numbers and design choices** (board size, hyperparameters, action space treatment) that came from a planning conversation, not from code that was tested. Treat them as starting points, not gospel. Where I (the prompt author) gave you a specific number, I either:
- (a) cited a paper, in which case trust it but verify on first use, or
- (b) gave a reasoned guess, in which case **measure before committing**.

The "Known unknowns" section below lists every place I'm guessing. When you encounter one of these in a phase, your first job is to measure, not to build on the guess.

### Communication protocol

When you're about to make a non-trivial design decision that wasn't explicit in this prompt, **stop and ask Joshua first**. Do not silently choose between equally-valid approaches. Examples that require asking: alternative board representations, different network architectures, swapping out the AlphaZero framework, changing the action space encoding. Examples that don't require asking: variable names, file organization, minor refactors, library version pinning.

Log every non-trivial decision in `DECISIONS.md` (template at end of this file).

### Project framing

This is **not** a "build superhuman Carcassonne AI" project. That's been attempted by a handful of academic groups since 2020 and has stalled — not because the idea is wrong, but because nobody's bothered to throw serious compute at it. We're not going to either.

What we **are** building, in this order:

1. A working Carcassonne game engine (forked, not from scratch)
2. A Monte Carlo Tree Search (MCTS) bot reproducing the published 2020 baseline
3. An AlphaZero-style self-play loop, **warm-started from existing work** (not tabula rasa)
4. A position analyzer / coaching tool that reviews family games and explains where points were lost

The win condition is **(4)**, not raw playing strength. A 90th-percentile bot that can also explain *why* a move was bad is more useful to me than a superhuman black box.

---

## Why warm-start matters (don't skip this section)

The famous AlphaZero paper trained from random play. That worked because DeepMind had 5,000 TPUs. We have one consumer GPU. So we steal every published rung of the ladder:

- **Game engine:** fork [`wingedsheep/carcassonne`](https://github.com/wingedsheep/carcassonne) (Python, MIT, OpenAI-Gym-style API, supports base + River + Inns & Cathedrals, includes farmers and abbots). This is ~60% of the engineering work, free.
- **MCTS algorithm:** reproduce Ameneyro et al. 2020 ([arXiv:2009.12974](https://arxiv.org/abs/2009.12974)) — vanilla MCTS with `s=100` simulations, `C=3` exploration constant. They beat Star2.5 with this. It's our baseline.
- **Heuristic value function:** their "virtual score" evaluation function gives us a non-trivial starting policy. Pre-train the neural network to mimic this heuristic before any self-play. Now epoch 1 of self-play already plays at decent-amateur level.
- **Self-play framework:** fork [`suragnair/alpha-zero-general`](https://github.com/suragnair/alpha-zero-general) (PyTorch/Keras, well-documented, many community examples). Subclass `Game.py` and `NeuralNet.py` for Carcassonne.
- **Tuning:** Jappert 2022 thesis (Basel) tested evolutionary tweaks to UCT parameters specifically for Carcassonne. Use their values.
- **Strategy heuristics:** the human Carcassonne competitive scene has documented opening theory, farmer valuation rules, and meeple economy ratios. Hand-code these as input features for the neural network.

By the time we start the self-play loop, we're climbing from "expert amateur," not from zero.

---

## Known unknowns — measure these, don't trust them

These are values or design choices the prompt asserts confidently but that are actually **guesses**. Verify each one before building on it.

| Item | Prompt says | Reality |
|---|---|---|
| Board representation size | 31×31 centered window | Guess based on intuition. Empirically measure max bounding box across 1000 random games + 1000 MCTS games **with River expansion enabled** (River makes the board snake further than base game). Use 99th percentile + 4 tile margin. |
| Action space size | "large but bounded" | Not measured. Compute actual max action space (positions × rotations × meeple slots) on real Base+River+Farmers games. If >5000, consider factored action space (separate position/rotation/meeple heads). |
| Engine correctness | wingedsheep is good | Last released Oct 2021, basically unmaintained. Verify scoring against canonical examples (especially **farmers**, which are subtle, the most-likely-buggy feature, AND the rule we actually use). |
| Dirichlet noise alpha | 0.3 | AlphaZero chess value. Carcassonne branching factor is different. Rule of thumb: ~10 / mean_legal_moves. Measure mean legal moves first, then set alpha. |
| MCTS simulations during self-play | 200 | Standard guess. Could need to be 100 (faster) or 400 (better data) depending on convergence behavior. Sweep this. |
| Replay buffer size | 200K positions | Guess. Should be tuned to roughly the data generated in 10-20 iterations. |
| Network depth | 10-15 residual blocks | Underdetermined. Try 6, 10, 15 and see what trains stably. |
| Iterations to reach "beats Joshua" | 150-300 | Pure speculation. Could be 50, could be 1000. Track ELO and stop when it plateaus. |
| Existing AlphaZero-Carcassonne repo | Possibly exists | Search GitHub for "alphazero carcassonne" before reimplementing. If found, study before forking. |

If any of these turns out to be wildly wrong, **stop and tell Joshua** before adapting. Some of these are load-bearing for downstream phases.

---

## Phase 0 — Environment setup

**Target machine:** Joshua's 5800X workstation running WSL2/Ubuntu (or native Linux). Not the M5 MacBook Air. All paths, commands, and assumptions should target Linux. The Air is for editing/monitoring over SSH, not running training.

```bash
# in WSL2/Ubuntu
mkdir -p ~/projects/carcassonne-ai && cd ~/projects/carcassonne-ai
python3 -m venv .venv
source .venv/bin/activate

git clone https://github.com/wingedsheep/carcassonne.git engine
git clone https://github.com/suragnair/alpha-zero-general.git az
pip install torch numpy matplotlib tqdm tensorboard
# verify CUDA on the 5060 Ti
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

**Acceptance for Phase 0:** can run `python -m wingedsheep.carcassonne.example` (or equivalent) and see two random agents play a game to completion with proper scoring.

**Engine sanity checks (do these before Phase 1):**
1. Run 100 random games with `[BASE, THE_RIVER]` and `[FARMERS]`. Verify all complete without crashes.
2. Verify scoring on these canonical scenarios (hand-construct or find in tests):
   - A 4-tile completed city with a shield: 4 × 2 + 2 = 10 points
   - A completed monastery (cloister) surrounded by 8 tiles: 9 points
   - Two players sharing a road feature: both score full value
   - **End-of-game farmer scoring: 3 points per completed city in the field** (this is critical — farmers are core to our scope)
   - **Contested farmer field: only the player with the most farmers in a connected field scores. Tied → both score.**
   - River start tile and end tile place correctly (river segments must connect)
3. If any of the above are wrong, **stop and report to Joshua before proceeding**. The engine is the foundation. We can fork-and-fix if needed but you need permission first. Farmer scoring bugs in particular are unacceptable since farmers are central to gameplay.

---

## Phase 1 — Game engine wrapper

The wingedsheep engine is good but its API isn't quite what AlphaZero expects. Build a thin adapter.

### Scope: which tile sets and rules

Joshua's family plays with **Base game + River expansion + Farmers** as their standard configuration. They own these and use them every game. No Abbots, no Inns & Cathedrals, nothing else.

For Phases 1-5, scope tight to match what the family actually plays:

```python
game = CarcassonneGame(
    players=2,  # 2-player for training; family games are 4-player but we handle that as a stretch goal
    tile_sets=[TileSet.BASE, TileSet.THE_RIVER],
    supplementary_rules=[SupplementaryRule.FARMERS]
)
```

**Do NOT enable** Inns & Cathedrals, Abbots, or any other tile sets even though wingedsheep supports them. Each adds scoring complexity and training cost. We're not testing how general the approach is — we're building a tool for one specific family's game.

If you find yourself thinking "while we're at it, let's add Inns & Cathedrals" — stop and put it in `BACKLOG.md`. Joshua's family doesn't own that expansion.

**Tasks:**
1. Subclass `Game.py` from alpha-zero-general for Carcassonne. Implement: `getInitBoard`, `getBoardSize`, `getActionSize`, `getNextState`, `getValidMoves`, `getGameEnded`, `getCanonicalForm`, `stringRepresentation`.
2. Decide board representation. **This is the hard design decision — read carefully:**
   - The classic chess/Go AlphaZero uses a fixed grid. Carcassonne's board grows. Don't naively use 72×72 (mostly zeros, won't train).
   - Recommended approach: **centered sliding window**. Track the bounding box of placed tiles. Represent the board as a 31×31 multi-channel tensor centered on the centroid of placed tiles. 31×31 covers >99% of real games (typical Carcassonne games stay within ~25 tiles wide).
   - Channels (each 31×31): tile-edge-type-N, tile-edge-type-S, tile-edge-type-E, tile-edge-type-W (categorical: city/road/field/none), occupied flag, my-meeple, opponent-meeple, my-farmer, opponent-farmer, completed-feature flag, current-tile-to-place (broadcasted). Probably ~15-20 channels.
   - Add scalar features (concatenated to network's flat layer): meeples-remaining-mine, meeples-remaining-opponent, score-mine, score-opponent, tiles-remaining-in-bag, current-score-differential.
3. Action space: every legal (position, rotation, meeple-placement) tuple. This is large but bounded per turn. Implement `getValidMoves` returning a mask over the full action space.
4. **Start 2-player only.** Multiplayer comes later. Don't engineer for it now.

**Acceptance for Phase 1:** Random agent plays a full game using the alpha-zero-general API. Game state round-trips through `stringRepresentation` and back without loss. `getValidMoves` is correct (verified by random playing 1,000 games with no rule violations).

---

## Phase 2 — MCTS baseline (reproducing 2020 paper)

Implement vanilla MCTS without the neural network first. This is the published baseline and we need it as a sparring partner.

**Tasks:**
1. Implement MCTS with chance nodes (tile draws are stochastic). Reference Ameneyro et al. Section III.B. Diamond-shaped chance nodes between player decisions.
2. Use the paper's parameters: `C=3`, `s=100` simulations per move, default policy = uniform random rollout to game end.
3. Implement the "virtual score" evaluation function from the paper. This becomes the rollout-cutoff heuristic later.
4. **Sanity check:** MCTS bot should beat random 95%+ of the time. If it doesn't, the engine wrapper is broken.
5. Implement deterministic mode for testing: predefined tile sequences so games are reproducible.

**Acceptance for Phase 2:** MCTS bot beats random 100/100 games. MCTS-vs-MCTS games complete in reasonable time (target <30 sec/game on the 5060 Ti's host CPU). Move latency target: <2 seconds per move at `s=100`.

---

## Phase 3 — Neural network + warm start

Now the AlphaZero piece.

**Tasks:**
1. Network architecture: ResNet-style trunk (10-15 residual blocks, 128 filters), two heads:
   - **Policy head:** softmax over the action space (use the valid-move mask)
   - **Value head:** scalar predicting expected score differential (mine - opponent), tanh-bounded to [-1, 1] after normalization
2. Concatenate the scalar features (Phase 1, item 2) into the dense layer before the heads.
3. **Warm start (critical):** generate ~500K random board positions (mid-game states from random and MCTS play). Label each with the virtual-score heuristic from Phase 2. Supervised-train the value head to match the heuristic. Train the policy head to match MCTS's visit distribution from the same positions.
4. Confirm the warm-started network alone (no MCTS) plays around the level of the heuristic. Should beat random 90%+.

**Acceptance for Phase 3:** Warm-started network beats random 90%+ standalone. Network + MCTS (50 simulations) beats vanilla MCTS (100 simulations) at >55% — proves the network is adding value over pure search.

---

## Phase 4 — Self-play loop

Standard AlphaZero training loop, scaled down for one GPU.

**Tasks:**
1. Self-play worker: network plays itself using MCTS guided by current network. Save (state, MCTS-policy, game-outcome) tuples.
2. Training worker: sample from replay buffer, train network on (state → MCTS-policy, game-outcome).
3. Evaluation worker: every N iterations, new network plays gauntlet vs previous best. If new network wins >55%, promote it.
4. Hyperparameters to start with (will need tuning):
   - Self-play games per iteration: 100
   - MCTS simulations per move during self-play: 200 (lower than evaluation to speed up data generation)
   - MCTS simulations during evaluation/play: 800
   - Learning rate: 1e-3 with decay
   - Replay buffer size: 200K positions
   - Dirichlet noise on root: alpha=0.3, epsilon=0.25 (standard AlphaZero values)
   - Temperature: 1.0 for first 15 moves of game, 0 after (encourages exploration early)
5. **Logging:** TensorBoard. Track: ELO vs heuristic baseline, ELO vs vanilla MCTS, training loss (policy + value separately), average game length, average score differential.
6. **Checkpoint at training milestones, not just the best.** Save the model at iterations 10, 25, 50, 100, 150, 200, and final. We need these for Phase 6 (heuristic emergence analysis). Disk is cheap. Don't only keep the strongest model.

**Acceptance for Phase 4:** After ~50 iterations (probably a few days of training), network beats the vanilla MCTS baseline >70% of the time. After ~200 iterations, network beats me (Joshua) in actual play. We will know if the loop is healthy by iteration 10 — if ELO is monotonically increasing, keep going. If it's flat or oscillating, we have a bug or hyperparameter problem.

**Phase 4 prerequisites — do these before any long training run:**
1. **Hyperparameter sanity sweep.** Run 5 short trainings (5 iterations each) with different values of: Dirichlet alpha (0.1, 0.3, 1.0), MCTS sims/move (100, 200, 400), learning rate (3e-4, 1e-3, 3e-3). Pick the combo that shows the steepest ELO improvement curve. This costs ~half a day and saves a week of bad training.
2. **Convergence smoke test.** Run 10 iterations end-to-end. ELO vs heuristic baseline must be monotonically increasing, even if slowly. If it's flat, oscillating, or decreasing — **stop and tell Joshua**. Do not "let it run longer hoping it'll improve." That's how a week disappears.
3. **Checkpoint every iteration.** Disk is cheap. We want to be able to roll back to iteration 47 if iteration 48 broke something.

**Things that commonly go wrong here, watch for them:**
- Policy collapse: network always plays same opening. Fix: increase Dirichlet noise, reduce temperature decay aggressiveness.
- Value head overconfident: predicts ±1 always. Fix: lower learning rate on value head, scale rewards.
- Replay buffer staleness: old games dominate. Fix: weight recent games more, or prune harder.

**Hardware notes for Phase 4:**
- Joshua's training rig: AMD 5800X (8C/16T) + RTX 5060 Ti 16GB. CPU is the bottleneck, not GPU.
- Run 8 parallel self-play workers (one per physical core, leave hyperthreads for OS/training).
- Expected wall-clock per iteration on this hardware: ~30-45 minutes for 100 self-play games at 200 MCTS sims/move.
- 50 iterations ≈ 1.5 days continuous. 200 iterations ≈ 1 week. Plan accordingly.
- If the loop is healthy after 20 iterations and Joshua wants to scale up, renting a 32-core box on Vast.ai or RunPod is the right move (4x speedup, ~$50-150 for a serious run).
- VRAM is not a bottleneck. The network we're training fits in <500MB.

---

## Phase 5 — The actually useful part: position analyzer

This is what I actually want from this project. The bot exists. Now make it teach.

**Tasks:**
1. Game logger: input a real family game (tile-by-tile, move-by-move) via CLI or simple web UI. Most efficient input format: photo of board after each turn → manual transcription tool. (Do NOT try computer-vision tile recognition. That's a separate project. Skip.)
2. Position analyzer: at each turn, run MCTS with high simulation count (5000+) on the actual played position. Compare the actual move against MCTS's preferred move. Compute **expected value loss** (delta in expected final score differential).
3. Generate a per-game report:
   - Top 3 worst moves by expected-value loss, with the network's preferred alternative and a one-paragraph explanation
   - Farmer placement timing: was the farmer placed too early/late given how the field developed?
   - Meeple economy: average meeples-on-board over the game. Compare to optimal play.
   - Blocking moves: were any blocks net-negative (cost more in tied-up meeples than they denied opponent)?
4. Format the report as Markdown. Include board diagrams (matplotlib/plotly suffices, no need for fancy graphics).

**Acceptance for Phase 5:** Generate a readable post-game analysis from a real family Carcassonne game with my kids. The analysis should pass the smell test for at least me — i.e. the moves it flags as bad should mostly be moves I already suspected were bad, plus a few I didn't notice. If the analyzer flags moves that seem fine, the value head is poorly calibrated.

---

## Phase 6 — Heuristic research (the interesting part)

This phase is what separates the project from "a Carcassonne bot exists" to "we learned something." Two parallel tracks.

### Track A: Validating human folk wisdom

The Carcassonne competitive community has a pile of contested strategy claims that have never been rigorously tested. We use the bot as an experimental apparatus to settle them.

**Methodology:**
1. Compile ~20 specific testable claims from forums (BoardGameGeek, the Carcassonne subreddit, competitive play guides). Examples: "don't claim roads under 3 tiles," "first farmer in a field usually wins it," "blocking is net-negative if you have <4 meeples available."
2. For each claim, formulate it as a constraint on bot play (bot follows rule vs. bot ignores rule).
3. Run matched simulations: 1000 games per claim, identical tile sequences for paired bots, hold all other variables constant.
4. Measure expected score delta and statistical significance.
5. Categorize each claim: ✓ confirmed, ✗ refuted, ~ context-dependent (works in some game phases but not others).

**Output:** a writeup with empirical evidence on each tested claim. This is genuinely useful to the competitive community and is the most publishable angle of the whole project.

### Track B: Extracting heuristics the bot discovered

Look for what the bot "knows" that humans don't. This is the AlphaGo-move-37 hunt.

**Methodology:**
1. Generate ~10K diverse mid-game positions via MCTS self-play.
2. For each position, compute the bot's top move (high-sim MCTS guided by trained network).
3. For each position, compute a "human consensus" top move. Two ways to estimate this:
   - The Phase 2 vanilla MCTS bot (no learned policy) is a reasonable proxy for "competent human reasoning"
   - If we have time/budget, recruit a small panel of strong players to annotate a subset of positions
4. Flag positions where bot move and consensus move disagree by >X expected score.
5. Manually inspect the top 50 disagreements. Look for patterns. Articulate them as principles.

**Bonus: emergence over training time.** The Phase 4 checkpoints at iterations 10/25/50/100/150/200 let us track *when* specific concepts emerge during training. Reference: McGrath et al. 2021, "Acquisition of Chess Knowledge in AlphaZero." Their methodology was probing the network's internal representations at different training stages to find when chess concepts (piece value, mobility, king safety) became encoded. We'd do the equivalent for Carcassonne concepts (farmer value, meeple economy, blocking).

**Output:** a list of bot-discovered heuristics, with empirical validation and (ideally) human-expert evaluation.

### Track C (combined): the actually novel research contribution

Compare results from Track A and Track B:
- **Folk wisdom that's right** (humans figured it out)
- **Folk wisdom that's wrong** (humans were miscalibrated)
- **Bot wisdom that humans missed** (genuine novel strategy)

The third category is what makes this worth writing up. If we find even 2-3 strategy principles the bot has discovered that humans haven't articulated, that's a real contribution to the game's competitive scene.

**Acceptance for Phase 6:** Track A produces validated/refuted/context-dependent verdicts on at least 15 folk claims with statistical confidence. Track B identifies at least 5 bot-vs-consensus disagreement patterns, with human-expert evaluation on a subset. Track C produces a final categorization document.

This is the phase that could plausibly become an arXiv preprint or IEEE CoG paper. Don't optimize for that during the build, but if the data ends up interesting, the writeup is straightforward.

---

## Phase 7 — Stretch goals (don't start until 0-6 are solid)

- **3-4 player support.** Real research problem because of kingmaker dynamics (a non-winning player's choices determining who wins). Approach: train the value head to predict each player's expected final score independently, then weight policy decisions by score-differential vs leader. Won't be optimal — multiplayer non-zero-sum has no clean equilibrium concept the way 2-player zero-sum does — but should be reasonable enough for family play. This is what Joshua actually wants to play against, so it's the highest-value stretch goal.
- **Coach mode for live games.** During a real game, the bot watches and offers move suggestions on request, with explanations. Builds on Phase 5's analyzer. Especially valuable if the family wants to use it during play (the kids might love this).
- **Web UI for opponents.** Flask app that lets the family play against the bot in a browser. Lower priority than the analysis tools — Joshua mostly wants insight, not a digital opponent.

**Expansion handling — important note:** if Joshua ever wants to add another expansion (e.g., buys Inns & Cathedrals at a future date), the right approach is **a separate trained model per expansion configuration**, not one universal model that handles all combos. Reasons:
- Inns & Cathedrals especially changes the value function dramatically (cities become 3 pts/tile completed vs 0 pts uncompleted, much higher variance than base game's 2 vs 1)
- One model trying to handle all combos requires either training on the union of all rule sets (slow, mediocre at each) or routing inputs through expansion-specific paths (complex)
- Specialized models per config train faster and play better

This isn't relevant for the current scope (Base + River + Farmers), but document it here so future-Joshua doesn't try to retrofit a universal model.

---

## Constraints and rules of engagement

- **Don't give me a checklist of homework.** If you (Claude Code) can run the command, run the command. If you can write the code, write the code. Don't make me do glue work that you could automate.
- **Commit early and often.** I want a clean git history I can roll back. Use feature branches: `phase-1-engine-wrapper`, `phase-2-mcts`, etc.
- **Test as you go.** Pytest. I do not want to debug Phase 4 training and discover Phase 1's `getValidMoves` is wrong.
- **No silent dependency installs.** If you need a package, mention it and add to a `requirements.txt`. I want to know what's on my system.
- **Fail loudly.** If something doesn't reproduce a published result, surface it. Don't paper over it.
- **Stay in scope.** If you find yourself wanting to also reimplement the game engine, or build a fancy UI, or add tile-recognition CV — stop. Note it in `BACKLOG.md` and keep moving.

---

## Reference materials (verified, current as of April 2026)

**Code repos:**
- Game engine: <https://github.com/wingedsheep/carcassonne>
- AlphaZero framework: <https://github.com/suragnair/alpha-zero-general>
- Existing Carcassonne RL attempt (different approach, possibly useful as reference): <https://github.com/SamuelScheit/carcassonne-ai>
- Alternative Carcassonne engine: <https://github.com/tiborcamargo/Carcassython>

**Papers:**
- Ameneyro et al. 2020, "Playing Carcassonne with Monte Carlo Tree Search," arXiv:2009.12974 — the baseline we're reproducing in Phase 2
- Jappert 2022, Basel bachelor's thesis on MCTS evolutionary tuning for Carcassonne (PDF on Basel AI dept site) — hyperparameter source
- Heeringa & Steyvers 2009, "Implementing a Computer Player for Carcassonne" — Maastricht University master's thesis, classical AI approach, useful for understanding game features

**Tutorials:**
- David Foster, "How to build your own AlphaZero AI using Python and Keras" — Medium, walkthrough of building AlphaZero for Connect4. The clearest explanation I've found.
- DeepMind's original AlphaZero paper (Silver et al. 2017, arXiv:1712.01815) — the canonical reference. Skim Algorithm 1.
- McGrath et al. 2021, "Acquisition of Chess Knowledge in AlphaZero" (arXiv:2111.09259) — methodology reference for Phase 6 Track B (heuristic emergence over training time).

---

## Decision log

When making non-obvious technical decisions, append to `DECISIONS.md` in the repo (template at bottom of this file). This is for Joshua to read in 3 weeks when he's forgotten why we chose the centered sliding window over a graph representation.

When tangents or out-of-scope ideas come up, append to `BACKLOG.md` (template at bottom). Capture and move on. Do not action items from BACKLOG.md without explicit approval.

---

## Start here

When this prompt is loaded, do the following before anything else:

1. Confirm you've read this whole document.
2. Create `BACKLOG.md` and `DECISIONS.md` in the repo root using the templates at the bottom of this file. Initial commit message: `chore: scaffold project tracking files`.
3. Confirm Phase 0 environment is set up. If it isn't, set it up. Note: we're working on the 5800X box (Linux/WSL2), not the M5 MacBook. Don't assume macOS paths or Apple Silicon quirks.
4. Run a single random-vs-random Carcassonne game using the wingedsheep engine and print the final score. This is the hello-world.
5. Run the engine sanity checks listed in Phase 0.
6. Then, and only then, propose a Phase 1 implementation plan and wait for my go-ahead.

Don't skip step 6. Phase 1's board representation is the most consequential design decision in the project — get it wrong and Phase 4 won't train. I want to review your plan before you commit code.
