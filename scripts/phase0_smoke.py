"""Phase 0 hello-world: random vs random Carcassonne game using the
wingedsheep engine, scoped to Base + River + Farmers (our locked Phase 1 scope).

Run:  python scripts/phase0_smoke.py
"""
import random
from typing import Optional

from wingedsheep.carcassonne.carcassonne_game import CarcassonneGame
from wingedsheep.carcassonne.objects.actions.action import Action
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet


def play_random_game(seed: int = 0) -> tuple[list[int], int, int]:
    """Play one random game; return (final_scores, num_moves, tiles_placed_count)."""
    random.seed(seed)
    game = CarcassonneGame(
        players=2,
        tile_sets=[TileSet.BASE, TileSet.THE_RIVER],
        supplementary_rules=[SupplementaryRule.FARMERS],
    )
    moves = 0
    while not game.is_finished():
        player = game.get_current_player()
        actions = game.get_possible_actions()
        action: Optional[Action] = random.choice(actions) if actions else None
        if action is not None:
            game.step(player, action)
        moves += 1
    placed = sum(
        1 for row in game.state.board for tile in row if tile is not None
    )
    return list(game.state.scores), moves, placed


def main() -> None:
    scores, moves, placed = play_random_game(seed=42)
    print(f"Final scores: player1={scores[0]} player2={scores[1]}")
    print(f"Total moves taken: {moves}")
    print(f"Tiles placed on board: {placed}")
    assert sum(scores) > 0, "no points scored — engine likely broken"


if __name__ == "__main__":
    main()
