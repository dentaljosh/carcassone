# Carcassonne AI

AlphaZero-style Carcassonne agent + position analyzer for family games.

**Author:** Joshua Ishal
**Hardware:** AMD 5800X + RTX 5060 Ti 16GB, WSL2/Ubuntu.
**Scope:** Base game + River expansion + Farmers, 2-player (Phase 1-5), with multiplayer as a stretch goal.
**Goal:** Phase 5 position analyzer that reviews family games, not raw playing strength.

## Status

Phase 1 — AlphaZero-style game wrapper. Phase 2 (MCTS) skeleton placeholder in `src/carcassonne_ai/mcts.py`.

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

# Full pytest suite (Phase 1 acceptance)
pytest tests/

# 1000-game wrapper fuzz (Phase 1 acceptance)
python -m carcassonne_ai.game_wrapper --self-play-random --n 1000

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
