#!/usr/bin/env python3
"""Harvest a small, self-contained MID-GAME position set for the M5 latency bench.

Source of truth for the positions is the champion's own action-log corpus
(``measurement/champ_action_logs/champ_games.jsonl``, 449 games played by
``FairHeuristicPriorAgent`` at k4x688 — see ``CORPUS_MANIFEST.json``), so every
position bundled here is a board the production champion actually reached.

FORMAT — one JSON object per line, a truncated ``root_replay`` RootRef::

    {"pos_id": int, "deck_seed": int, "actions": [int, ...], "ply": int,
     "phase": "tiles"|"meeples", "k_remaining": int, "n_legal": int,
     "game_id": int}

``actions`` is already truncated to ``actions[:ply]``, so ``ply == len(actions)``
and the replay is::

    random.seed(deck_seed); board = Game().get_init_board()
    for a in actions: board, _ = game.get_next_state(board, a)

which is lossless for ANY policy (the engine consumes the global ``random``
stream only in the deck shuffle) — the contract documented in
``scripts/measurement_infra/root_replay.py``.

SELECTION RULES (all enforced, and recorded per position):
  * ``k_remaining > exact_max_k`` (default 2) — the fair agent latches its EXACT
    endgame solver at ``k_remaining <= exact_max_k`` on a TILES decision, and a
    solve is a different (and wildly variable) cost from a PIMC search. A latency
    bench of "the search" must not sample it. This is asserted, not hoped for.
  * ``n_legal >= 2`` — a forced move is not a decision.
  * Both phases are sampled in a fixed ratio (default 1:1). The Android wall-clock
    memo (§2) found the MEEPLE half costs MORE than the tile half despite having
    far fewer candidates, so a tile-only sample would understate s/move.
  * One position per source game, games spread evenly across the corpus.

Usage::

    python3 scripts/m5_bench/make_positions.py --out /tmp/positions.jsonl -n 60
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"


def _import_engine():
    """Import the game wrapper without disturbing the caller's env knobs.

    Position harvesting is leaf-INDEPENDENT (it only replays recorded actions), so
    this deliberately sets no CARCASSONNE_* knob: the bench script owns that.
    """
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "engine"))
    from carcassonne_ai.game_wrapper import Game  # noqa: PLC0415

    return Game


def k_remaining(state) -> int:
    """Tiles left = undrawn deck + the one in hand (the fair_agent band)."""
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def harvest(corpus: Path, n: int, *, exact_max_k: int = 2, seed: int = 7,
            lo_frac: float = 0.30, hi_frac: float = 0.80) -> list[dict]:
    """Pick ``n`` positions, alternating tile/meeple phase, one per game."""
    import numpy as np

    Game = _import_engine()
    games = [json.loads(line) for line in corpus.read_text().splitlines() if line.strip()]
    if not games:
        raise SystemExit(f"make_positions: empty corpus {corpus}")

    rng = random.Random(seed)
    # Spread the source games evenly over the corpus rather than taking a prefix.
    stride = max(1, len(games) // (n * 2))
    candidates = games[::stride]
    rng.shuffle(candidates)

    want_phase = ["tiles", "meeples"]
    out: list[dict] = []
    for g in candidates:
        if len(out) >= n:
            break
        actions = [int(a) for a in g["actions"]]
        n_plies = len(actions)
        target_phase = want_phase[len(out) % 2]

        lo, hi = int(n_plies * lo_frac), int(n_plies * hi_frac)
        plies = list(range(lo, hi))
        rng.shuffle(plies)

        game = Game(enable_legal_moves_cache=True)
        random.seed(int(g["deck_seed"]))
        board = game.get_init_board()
        # Replay once, snapshotting the metadata at every ply we might want. The
        # board itself is not kept (a deepcopy per ply would be gratuitous); the
        # chosen ply is re-replayed by the bench from (deck_seed, actions[:ply]).
        meta: dict[int, dict] = {}
        keep = set(plies)
        for ply, a in enumerate(actions):
            if ply in keep and not board.state.is_terminated():
                mask = game.get_valid_moves(board)
                meta[ply] = {
                    "phase": str(board.state.phase.value),
                    "k_remaining": int(k_remaining(board.state)),
                    "n_legal": int(np.count_nonzero(mask)),
                }
            board, _ = game.get_next_state(board, a)

        for ply in plies:
            m = meta.get(ply)
            if m is None:
                continue
            if m["phase"] != target_phase:
                continue
            if m["k_remaining"] <= exact_max_k:
                continue          # would latch the exact solver — not a search sample
            if m["n_legal"] < 2:
                continue          # forced move: not a decision
            out.append({
                "pos_id": len(out),
                "game_id": int(g["game_id"]),
                "deck_seed": int(g["deck_seed"]),
                "actions": actions[:ply],
                "ply": int(ply),
                **m,
            })
            break

    if len(out) < n:
        print(f"make_positions: WARNING only {len(out)}/{n} positions found",
              file=sys.stderr)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("-n", type=int, default=60)
    p.add_argument("--exact-max-k", type=int, default=2)
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args(argv)

    if not a.corpus.is_file():
        raise SystemExit(f"make_positions: corpus not found: {a.corpus}")
    rows = harvest(a.corpus, a.n, exact_max_k=a.exact_max_k, seed=a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    n_tile = sum(1 for r in rows if r["phase"] == "tiles")
    ks = sorted(r["k_remaining"] for r in rows)
    print(f"make_positions: {len(rows)} positions -> {a.out} "
          f"({os.path.getsize(a.out) / 1e3:.1f} kB)")
    print(f"  phase: tiles={n_tile} meeples={len(rows) - n_tile}")
    print(f"  k_remaining: min={ks[0]} median={ks[len(ks) // 2]} max={ks[-1]} "
          f"(all > exact_max_k={a.exact_max_k})")
    print(f"  n_legal: min={min(r['n_legal'] for r in rows)} "
          f"max={max(r['n_legal'] for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
