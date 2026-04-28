# Carcassonne AI

AlphaZero-style Carcassonne agent + position analyzer for family games.

**Author:** Joshua Ishal
**Hardware:** AMD 5800X + RTX 5060 Ti 16GB, WSL2/Ubuntu.
**Scope:** Base game + River expansion + Farmers, 2-player (Phase 1-5), with multiplayer as a stretch goal.
**Goal:** Phase 5 position analyzer that reviews family games, not raw playing strength.

## Status

- **Phase 0** ✅ scaffolding, sanity checks, measurements, vendoring + engine patches
- **Phase 1** ✅ AlphaZero-style game wrapper + opt-in legal-moves cache (39 tests pass)
- **Phase 2** ✅ vanilla MCTS (UCT C=3, in-place rollouts, Q-tiebreak best_action). Acceptance: MCTS(s=20) won 96/100 vs random.
- **Phase 3** in progress — `virtual_score` + `network` (6×96 ResNet) + warmstart pipeline implemented; smoke comparison (Option C MCTS-labels vs Option D heuristic-labels, 5K each) running to settle production label strategy.

See [STATUS.md](STATUS.md) for live state and [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) for the project spec.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e engine
pip install pytest pytest-xdist torch tensorboard tqdm matplotlib

# Smoke test the engine
python scripts/phase0_smoke.py
python scripts/phase0_sanity_checks.py

# Full pytest suite
pytest tests/

# 1000-game wrapper fuzz
python -m carcassonne_ai.game_wrapper --self-play-random --n 1000

# Phase 2 MCTS-vs-random tournament (resumable, per-game checkpoints)
python -u scripts/play_mcts_vs_random.py --n 100 --sims 20

# Phase 3 warm-start pipeline (smoke versions; production will scale up)
python -u scripts/generate_warmstart_smoke.py --label-strategy heuristic --n 5000
python -u scripts/train_warmstart_smoke.py --strategy heuristic --epochs 20 --output checkpoints/warmstart_heuristic_smoke.pt
python -u scripts/eval_warmstart_smoke.py --checkpoint checkpoints/warmstart_heuristic_smoke.best.pt --n 50

# Phase 3 acceptance Tournament 2 (NeuralMCTS s=50 vs vanilla MCTS s=100)
python -u scripts/eval_neural_mcts_vs_vanilla.py --checkpoint checkpoints/warmstart_heuristic_smoke.best.pt --n 100 --neural-sims 50 --vanilla-sims 100

# Profiling
python scripts/bench_quick.py            # per-call cost map + GPU sanity
python scripts/bench_workers.py 64       # parallel-worker speedup
```

## Layout

- `engine/` — vendored copy of [wingedsheep/carcassonne](https://github.com/wingedsheep/carcassonne) (MIT, last upstream release Oct 2021), patched (see `DECISIONS.md`)
- `az/` — vendored copy of [suragnair/alpha-zero-general](https://github.com/suragnair/alpha-zero-general) (MIT, used as a reference, not imported)
- `src/carcassonne_ai/` — our code (game wrapper, board representation, action space, scalar features, ETA helpers, MCTS placeholder)
- `scripts/` — runnable entry points (smoke tests, measurements, benches)
- `tests/` — pytest (33 tests covering action space, board encoding, game wrapper, invariants, legal-moves cache, string repr, window overflow)
- `data/`, `checkpoints/`, `runs/` — gitignored artifacts

## Tracking docs

- [`DECISIONS.md`](DECISIONS.md) — architecture decision log. Read this if you wonder "why was this chosen?"
- [`BACKLOG.md`](BACKLOG.md) — parking lot for tangents and out-of-scope ideas.

## Attribution

Vendored upstream code retains its original licenses; see `THIRD_PARTY_LICENSES/`.
