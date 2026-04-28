# Phase 3 design notes (draft, not yet plan-mode reviewed)

> Sketched during the s=20 tournament's wall-clock window. Treat as starting points; full plan-mode review needed before any implementation.

## What Phase 3 has to deliver

Per [docs/ORIGINAL_PROMPT.md](ORIGINAL_PROMPT.md):

1. **Network**: ResNet-style trunk (10-15 residual blocks, 128 filters), policy head (softmax over action space, masked) + value head (scalar, tanh-bounded).
2. **Scalar features** concatenated to the dense layer before heads. Already implemented in `src/carcassonne_ai/features.py` (10 floats).
3. **Warm-start (critical)**: ~500K labeled positions. Each labeled with:
   - **Value target** = virtual_score heuristic estimate (Ameneyro 2020 §III.B equivalent).
   - **Policy target** = visit distribution from MCTS at that state.
4. **Supervised pre-training** of both heads to match the warm-start labels.
5. **Acceptance**: warm-started network alone beats random 90%+. Network + MCTS(s=50) beats vanilla MCTS(s=100) at >55%.

## Network architecture sketch

```
Input: (B, 40, 25, 25) board tensor + (B, 10) scalar features

Conv stem: Conv2d(40 → 128, 3x3, pad=1) + BN + ReLU
Residual trunk: 10× ResBlock(128, 128) — each two 3x3 convs, BN+ReLU between, skip connection
                                       with 128 filters; output (B, 128, 25, 25)
Flatten + scalar concat: → (B, 128*25*25 + 10) = (B, 80,010)

Policy head:
  Dense(80010 → 256) + ReLU
  Dense(256 → 2511 = action_size) — masked-softmax at inference

Value head:
  Dense(80010 → 256) + ReLU
  Dense(256 → 1)
  tanh — already in [-1, +1]
```

Open questions for plan-mode:
- Block count: prompt says 10-15. Start at 10 (cheaper to train, lighter inference); bump to 15 if underfit.
- Attention vs pure ResNet: pure ResNet is simpler and proven for this size. Skip attention.
- Mixed precision: yes, fp16 forward + fp32 master weights. Standard PyTorch AMP.
- Optimizer: AdamW or SGD-momentum? AlphaZero used SGD-momentum (lr=0.01, mom=0.9). Worth following the canonical recipe.

## virtual_score_estimate (the warm-start labeler)

This is the load-bearing piece I deferred from Phase 2. It's the function `value(board, player) → expected final score differential`. Components I expect (will verify against the Ameneyro paper before locking):

1. **Current realized scores**: `state.scores[player] - state.scores[opponent]`.
2. **Pending closure of incomplete features** owned by each player:
   - Incomplete cities owned by my meeple: count completed-tile equivalents × 1pt + shields × 1pt. Penalize by (1 - completion_likelihood).
   - Incomplete roads owned by my meeple: count tiles × 1pt × completion_likelihood.
   - Cloisters owned by my meeple: count surrounding tiles + 1.
3. **End-game farmer scoring estimate**:
   - For each FarmerConnection set the player has a farmer in, count cities-touching that field that are likely to be completed by game end → 3pts each.
4. **Meeple economy bonus**: extra weight for having more meeples in hand (more flexibility).

For warm-start labels, this can be a Python function on `CarcassonneGameState` — doesn't need to be fast, just correct. Speed matters when generating 500K labels but we can parallelize.

Component code skeleton (NOT to commit yet):

```python
def virtual_score_estimate(state, player):
    realized = state.scores[player] - state.scores[1 - player]

    pending = 0.0
    for city in find_my_cities(state, player):
        if not city.finished:
            pending += city_value_with_completion_prob(state, city)
    for road in find_my_roads(state, player):
        if not road.finished:
            pending += road_value_with_completion_prob(state, road)
    for cloister in find_my_cloisters(state, player):
        pending += cloister_expected_value(state, cloister)

    farmer_estimate = 0.0
    for farm in find_my_farms(state, player):
        farmer_estimate += 3 * expected_completed_cities(state, farm)

    return realized + pending - opponent_equivalent + farmer_estimate
```

The `_with_completion_prob` functions are heuristic (can simply assume 70% closure for partial features).

## Labeled-position generation pipeline

```
foreach seed in range(seeds):
    board = game.get_init_board()
    while not game.get_game_ended(...):
        # mid-game: snapshot the position
        if random_p_mid_game_eligible_position():
            run MCTS(sims=200, network=None) for warm-start visit policy
            label = (
                board_state,
                mcts_visit_distribution,
                virtual_score_estimate(board, current_player),
            )
            yield label
        # advance with random play (so we sample many positions per game)
        ...
```

Output format: `data/warmstart/seed_<N>_move_<M>.npz` with `(board_tensor, scalar_feats, policy_target, value_target)`. Same per-item-checkpointing pattern as Phase 2 tournament — resumable.

500K positions ÷ 100 positions/game ≈ 5K games × MCTS(s=200) per position ≈ a LOT of compute. Roughly: each MCTS-labeled position is ~5 min at s=200 on this CPU (extrapolating from Phase 2's s=10 ≈ 1.78s × 20x). 500K × 5 min / 16 workers = ~2700 hours = wildly too much.

Realistic pipeline: lower s for warm-start (s=50 maybe), and accept noisier visit distributions. Or use the Ameneyro virtual_score directly as both the value target AND a seed for the policy target (with a softmax over heuristic-scored actions). Latter is much cheaper.

This is the single biggest design decision in Phase 3 — needs careful thought + plan-mode session before implementing.

## Supervised pre-training

Standard. Loss = policy cross-entropy + value MSE, weighted (typically 1.0 for both).
- Batch size: 256-1024
- LR schedule: linear warmup + cosine decay
- Optimizer: SGD-mom 0.9 with weight decay 1e-4
- Train for ~20 epochs on 500K positions. Stop when value MSE stabilizes.

## Acceptance test plan

After warm-start training:

1. **Standalone network vs random**: 100 games. Network plays argmax-policy (no MCTS). Acceptance ≥90% wins.
2. **Network+MCTS(s=50) vs vanilla MCTS(s=100)**: 100 games. Network MCTS uses prior=network policy, leaf=network value. Acceptance >55% wins.

The latter is the real Phase 3 win condition: prove that the network adds value over pure search at the same compute budget.

## Risks I want to flag for plan-mode

- **virtual_score may be hard to nail for this engine.** The Ameneyro paper used a custom Carcassonne engine; their farmer-completion heuristic relied on engine-internal data we don't have direct access to. May need to write our own version using `CityUtil.find_cities` etc.
- **500K positions might be too few or too many.** Replay buffer in canonical AlphaZero is ~500K, sized to ~10-20 iterations of Phase 4 self-play data. For Phase 3 warm-start we want enough diversity to teach the network "what good play looks like." If the labeling pipeline is slow, we may settle for 100K and see if that's enough.
- **Network might fail to fit virtual_score** if the heuristic is itself noisy or contradictory. Smoke test early: train on 10K positions, see if value MSE converges.

## What I'm NOT doing during Joshua's break

- Implementing virtual_score (needs design review)
- Building the network module (needs design review)
- Generating any positions (needs CPU and review)

These notes are pure design sketching for the plan-mode session.
