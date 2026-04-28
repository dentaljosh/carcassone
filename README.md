# Carcassonne AI

AlphaZero-style Carcassonne agent + position analyzer for family games.

**Author:** Joshua Ishal
**Hardware:** AMD 5800X + RTX 5060 Ti 16GB, WSL2/Ubuntu.
**Scope:** Base game + River expansion + Farmers, 2-player (Phase 1-5), with multiplayer as a stretch goal.
**Goal:** Phase 5 position analyzer that reviews family games, not raw playing strength.

## Status

Phase 0 — environment scaffolding.

## Layout

- `engine/` — vendored copy of [wingedsheep/carcassonne](https://github.com/wingedsheep/carcassonne) (MIT, last upstream release Oct 2021)
- `az/` — vendored copy of [suragnair/alpha-zero-general](https://github.com/suragnair/alpha-zero-general) (MIT)
- `src/carcassonne_ai/` — our code (game wrapper, board representation, MCTS, network, self-play, analyzer)
- `scripts/` — runnable entry points (smoke tests, measurements, training, play CLI)
- `tests/` — pytest
- `data/`, `checkpoints/`, `runs/` — gitignored artifacts

## Tracking docs

- [`DECISIONS.md`](DECISIONS.md) — architecture decision log. Read this if you wonder "why was this chosen?"
- [`BACKLOG.md`](BACKLOG.md) — parking lot for tangents and out-of-scope ideas.

## Attribution

Vendored upstream code retains its original licenses; see `THIRD_PARTY_LICENSES/`.
