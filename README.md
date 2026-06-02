# Carcassonne AI

AlphaZero-style Carcassonne agent aiming at genuinely superhuman 2-player play.

**Author:** Joshua Ishal
**Hardware:** AMD 5800X + RTX 5060 Ti 16GB, WSL2/Ubuntu (+ a Xeon box and a pop-os laptop in the cluster — see CLAUDE.md).
**Scope:** Base game + Farmers, 2-player (River expansion **dropped 2026-06-02** — competitive/WC play is base-only). No Inns & Cathedrals, no Abbots, no Big meeples.
**Goal (changed 2026-05-28, overriding the original prompt):** genuinely superhuman play — beat strong/expert humans, aspirationally the world champion. The Phase 5 position analyzer + heuristic research are now **downstream** of strength, not the target. See [CLAUDE.md](CLAUDE.md) + DECISIONS.md.

## Status

- **Phase 0** ✅ scaffolding, sanity checks, measurements, vendoring + engine patches
- **Phase 1** ✅ AlphaZero-style game wrapper + opt-in legal-moves cache
- **Phase 2** ✅ vanilla MCTS (UCT C=3, in-place rollouts, Q-tiebreak best_action). Acceptance: MCTS(s=20) won 96/100 vs random
- **Phase 3** ✅ 6×96 ResNet (~7M params) + heuristic warmstart at 100K positions, tau=0.5. `checkpoints/warmstart_canonical.pt` is the canonical baseline. Closure: skip remaining warmstart iteration, advance to self-play (see DECISIONS.md "2026-04-29 — Phase 3 closure")
- **Phase 4** active — self-play loop (virtual-loss / batched-eval MCTS, 3-box cluster, anchor-gate). A 2026-06-02 **foundational audit** reframed the project: the v2.7 hand-crafted leaf was masking 2 live bugs (farm-scoring + MCTS-transposition double-counts, both now FIXED) plus architectural caps (the learned value head was never in the search loop). River was dropped; symmetry augmentation built. Current work is a **staged correction** (A: re-baseline + cheap fixes → B: value-head-in-loop retrain → C: representation planes). The old per-iteration checkpoints (v6 `iter_12`, then `iter_11`) were strongest on the *old* River+buggy game and are being re-baselined on the new base-only game.

See [STATUS.md](STATUS.md) for live state, [docs/CORRECTION_PLAN_2026-06-02.md](docs/CORRECTION_PLAN_2026-06-02.md) + [docs/PHASE1_BUILD_SPEC_2026-06-02.md](docs/PHASE1_BUILD_SPEC_2026-06-02.md) for the current plan, and [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) for the (partly superseded) original spec.

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
- `src/carcassonne_ai/` — our code (game wrapper, board representation, action space, scalar features, MCTS, NeuralMCTS, network, warmstart, selfplay, evaluators, eval_server / eval_server_pool for the GPU orchestrator)
- `scripts/` — runnable entry points (smoke tests, measurements, benches, self-play + train + eval drivers, Phase 4 outer loop)
- `tests/` — pytest suite (covers action space, board encoding, game wrapper, MCTS, NeuralMCTS virtual-loss, eval-server orchestrator, etc.)
- `data/`, `checkpoints/`, `runs/` — gitignored artifacts

## Tracking docs

- [`DECISIONS.md`](DECISIONS.md) — architecture decision log. Read this if you wonder "why was this chosen?"
- [`BACKLOG.md`](BACKLOG.md) — parking lot for tangents and out-of-scope ideas.

## Attribution

Vendored upstream code retains its original licenses; see `THIRD_PARTY_LICENSES/`.
