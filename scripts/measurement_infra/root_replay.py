"""Root replay format — lossless reconstruction of any game position from (deck_seed, actions, ply).

MEASUREMENT INFRASTRUCTURE (not a strength lever). Promoted from the post-search-residual pilot
(CL-035). Supersedes the greedy-only `gen_endgame_positions.replay_to` for arbitrary-policy games.

## The contract (why this is lossless for ANY policy)

The wingedsheep engine consumes the global `random` stream in exactly ONE place: the deck shuffle in
`Game.get_init_board()`. During play (`get_next_state` / `get_valid_moves` / scoring) it consumes NO
global random. MCTS agents draw from their OWN `random.Random` instance, never the global stream.

Therefore a game is fully determined by `(deck_seed, action_sequence)`:

    random.seed(deck_seed)          # fixes the deck shuffle
    board = game.get_init_board()   # deck now deterministic
    for a in actions[:ply]:         # replay the recorded moves
        board, _ = game.get_next_state(board, a)

This reconstructs the EXACT board at `ply`, regardless of which policy (greedy, HeuristicMCTS,
NeuralMCTS, ...) produced `actions`. Verified bit-exact at generation time (`recon_ok`) and in
`tests/test_measurement_infra.py`.

## Format on disk (games jsonl — one JSON object per line)

    {"game_id": int, "deck_seed": int, "actions": [int, ...], "n_plies": int, ...optional metadata}

A *root* is a reference into a game: `RootRef(deck_seed, actions, ply)` (or `(game_id, ply)` joined
against a loaded games dict).
"""
from __future__ import annotations
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from carcassonne_ai.game_wrapper import Game


@dataclass(frozen=True)
class RootRef:
    """A reconstructable position: the deck seed, the move sequence, and the ply to stop at."""
    deck_seed: int
    actions: tuple        # full game action sequence (ints); only actions[:ply] are applied
    ply: int
    meta: dict = field(default_factory=dict, compare=False)

    def replay(self, include_farm_scalars: bool = True):
        return replay_actions(self.deck_seed, self.actions, self.ply, include_farm_scalars)


def replay_actions(deck_seed: int, actions, ply: int, include_farm_scalars: bool = True):
    """Reconstruct (game, board) at move index `ply`. Lossless for any policy (see module docstring)."""
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm_scalars)
    board = game.get_init_board()
    for a in actions[:ply]:
        board, _ = game.get_next_state(board, int(a))
    return game, board


@dataclass
class GameRecord:
    """A full recorded game. `actions` is the complete move sequence from the seeded init board."""
    game_id: int
    deck_seed: int
    actions: list
    n_plies: int
    meta: dict = field(default_factory=dict)

    def root(self, ply: int) -> RootRef:
        return RootRef(self.deck_seed, tuple(self.actions), int(ply), dict(self.meta))

    def to_json(self) -> dict:
        d = {"game_id": int(self.game_id), "deck_seed": int(self.deck_seed),
             "actions": [int(a) for a in self.actions], "n_plies": int(self.n_plies)}
        d.update(self.meta)
        return d


def save_games(path, games) -> None:
    """Write an iterable of GameRecord to a jsonl file."""
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as fh:
        for g in games:
            fh.write(json.dumps(g.to_json()) + "\n")


def load_games(path) -> list:
    """Load a games jsonl into a list of GameRecord. Accepts legacy `seed` as an alias for
    `deck_seed` (the post-search-residual games_mcts.jsonl used `seed`)."""
    out = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        seed = int(o.get("deck_seed", o.get("seed")))
        actions = [int(a) for a in o["actions"]]
        meta = {k: v for k, v in o.items()
                if k not in ("game_id", "deck_seed", "seed", "actions", "n_plies")}
        out.append(GameRecord(int(o["game_id"]), seed, actions,
                              int(o.get("n_plies", len(actions))), meta))
    return out


def load_games_dict(path) -> dict:
    """game_id -> actions list (for joining (game_id, ply) roots back to their move sequence)."""
    return {g.game_id: g.actions for g in load_games(path)}
