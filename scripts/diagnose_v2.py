"""Diagnostic: why did virtual_score_v2 regress 47pp vs v1?

Plays one (or a few) hybrid_v2 vs Tier-1 game(s) at sims=100 (cheap)
and dumps per-move bonus breakdown:

  - v1 base (`virtual_score(state, hybrid_player)`)
  - v2 bonus_self / bonus_opp / total
  - per-meeple contributions: terrain type, P(close), delta, contribution
  - flags: cathedral branch firing (likely bug), bonus_magnitude > base

After the game we report aggregate stats:
  - did the cathedral branch ever fire? (it shouldn't in 2p River+Farmers)
  - how often did |bonus_self - bonus_opp| > |base|?  (sign-flip risk)
  - which terrain types contributed the most bonus?
  - example moves where v2 likely picked a worse action than v1

Run:  python -u scripts/diagnose_v2.py --sims 100 --n 1
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.utils.city_util import CityUtil
from wingedsheep.carcassonne.utils.farm_util import FarmUtil

from carcassonne_ai.action_space import (
    meeple_farmer_base,
    meeple_normal_base,
    meeple_pass_index,
    tile_action_count,
    tile_pass_index,
)
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from carcassonne_ai.virtual_score import virtual_score
from carcassonne_ai.virtual_score_v2 import (
    _BONUS_CAP,
    _close_prob,
    _closure_anticipation_bonus,
    _open_city_positions,
    _surrounding_count,
    virtual_score_v2,
)


_worker_net = None
_worker_device = None


def _init_net(checkpoint_path: str) -> None:
    global _worker_net, _worker_device
    import torch
    from carcassonne_ai.network import CarcassonneNet

    _worker_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(checkpoint_path, map_location=_worker_device, weights_only=False)
    net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]).to(_worker_device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    _worker_net = net


def _closure_anticipation_bonus_debug(state, player: int) -> tuple[float, list[dict]]:
    """Mirrors `_closure_anticipation_bonus` but returns a per-meeple breakdown.
    Each entry: {terrain, p, delta, contrib, cathedral_fired}."""
    bonus = 0.0
    rows: list[dict] = []
    for mp in state.placed_meeples[player]:
        coord_side = mp.coordinate_with_side
        coord = coord_side.coordinate
        tile = state.board[coord.row][coord.column]
        if tile is None:
            continue
        terrain = tile.get_type(coord_side.side)
        row: dict = {
            "terrain": terrain.value if hasattr(terrain, "value") else str(terrain),
            "coord": (coord.row, coord.column),
            "p": 0.0,
            "delta": 0,
            "contrib": 0.0,
            "cathedral_fired": False,
        }

        if terrain == TerrainType.CITY:
            city = CityUtil.find_city(game_state=state, city_position=coord_side)
            if city.finished:
                continue
            open_n = _open_city_positions(state, city)
            p = _close_prob(open_n)
            row["p"] = p
            row["open_n"] = open_n
            row["n_city_tiles"] = len({(cp.coordinate.row, cp.coordinate.column) for cp in city.city_positions})
            if p > 0:
                # Mirror production fn delta computation, capture cathedral fire.
                has_cathedral = False
                coords: set[tuple[int, int]] = set()
                for pos in city.city_positions:
                    c = pos.coordinate
                    t = state.board[c.row][c.column]
                    if t is None:
                        continue
                    if t.inn:
                        has_cathedral = True
                    coords.add((c.row, c.column))
                delta = 0
                for r, col in coords:
                    t = state.board[r][col]
                    if has_cathedral:
                        delta += 6 if t.shield else 3
                    else:
                        delta += 2 if t.shield else 1
                row["delta"] = delta
                row["cathedral_fired"] = has_cathedral
                contrib = p * delta
                row["contrib"] = contrib
                bonus += contrib

        elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
            n_surround = _surrounding_count(state, coord)
            needed = 8 - n_surround
            if needed > 0:
                p = _close_prob(needed)
                row["p"] = p
                row["open_n"] = needed
                if p > 0:
                    delta = 8 - n_surround
                    row["delta"] = delta
                    contrib = p * delta
                    row["contrib"] = contrib
                    bonus += contrib

        elif mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
            farm = FarmUtil.find_farm_by_coordinate(game_state=state, position=coord_side)
            visited_cities: set[int] = set()
            farm_contrib = 0.0
            farm_n_cities = 0
            for fc in farm.farmer_connections_with_coordinate:
                cities = CityUtil.find_cities(
                    game_state=state,
                    coordinate=fc.coordinate,
                    sides=fc.farmer_connection.city_sides,
                )
                for city in cities:
                    cid = id(city)
                    if cid in visited_cities:
                        continue
                    visited_cities.add(cid)
                    if city.finished:
                        continue
                    open_n = _open_city_positions(state, city)
                    p = _close_prob(open_n)
                    if p > 0:
                        c = p * 3
                        farm_contrib += c
                        farm_n_cities += 1
            row["delta"] = 3 * farm_n_cities  # max delta if all close
            row["contrib"] = farm_contrib
            row["farm_n_cities_pending"] = farm_n_cities
            bonus += farm_contrib

        if row["contrib"] != 0 or row["cathedral_fired"]:
            rows.append(row)

    return bonus, rows


def _hybrid_v2_evaluator(game: Game):
    import torch

    def evaluator(board):
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(_worker_device)
        scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(_worker_device)
        with torch.no_grad():
            logits, _ = _worker_net(obs_t, scalars_t)
            mask = game.get_valid_moves(board)
            mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(_worker_device)
            probs = _worker_net.policy_softmax_with_mask(logits, mask_t)
        diff = virtual_score_v2(board.state, board.state.current_player)
        v = math.tanh(diff / 15.0)
        return probs[0].cpu().numpy(), v

    return evaluator


def _describe_action(game: Game, board, action_idx: int) -> str:
    W = game.window_size
    if action_idx == tile_pass_index(W):
        return "TILE_PASS"
    if action_idx == meeple_pass_index(W):
        return "MEEPLE_PASS"
    a_tile = tile_action_count(W)
    if action_idx < a_tile:
        cell, rot = divmod(action_idx, 4)
        wr, wc = divmod(cell, W)
        coord = board.offset.to_engine(wr, wc)
        return f"TILE({coord.row},{coord.column}) rot={rot}"
    norm_base = meeple_normal_base(W)
    farm_base = meeple_farmer_base(W)
    if norm_base <= action_idx < farm_base:
        slot = action_idx - norm_base
        sides = ["TOP", "RIGHT", "BOTTOM", "LEFT", "CENTER"]
        return f"MEEPLE_NORMAL {sides[slot]}"
    if farm_base <= action_idx < meeple_pass_index(W):
        slot = action_idx - farm_base
        corners = ["TL", "TR", "BL", "BR"]
        return f"MEEPLE_FARMER {corners[slot]}"
    return f"action_idx={action_idx}"


def play_one(seed: int, hybrid_idx: int, sims: int) -> dict:
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    rule = RuleBasedPlayer(seed=seed)
    evaluator = _hybrid_v2_evaluator(game)
    opp = NeuralMCTS(game=game, evaluator=evaluator, simulations=sims, seed=seed + 1)

    moves: list[dict] = []
    t0 = time.perf_counter()
    move_idx = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        if cur == hybrid_idx:
            opp.clear()
            action = opp.best_action(board)
            actor = "hybrid_v2"
        else:
            action = rule.choose_action(game, board, mask)
            actor = "tier1"
        if not mask[action]:
            raise RuntimeError(f"player {cur} returned illegal action {action}")
        action_desc = _describe_action(game, board, action)
        board, _ = game.get_next_state(board, action)

        # Post-state diagnostics: v1 base + v2 breakdown from hybrid's view.
        # `_closure_anticipation_bonus_debug` returns the RAW uncapped sum
        # plus the per-meeple rows. The production capped value is what
        # actually feeds the search.
        base = virtual_score(board.state, hybrid_idx)
        raw_self, rows_self = _closure_anticipation_bonus_debug(board.state, hybrid_idx)
        raw_opp, rows_opp = _closure_anticipation_bonus_debug(board.state, 1 - hybrid_idx)
        bonus_self = _closure_anticipation_bonus(board.state, hybrid_idx)
        bonus_opp = _closure_anticipation_bonus(board.state, 1 - hybrid_idx)
        v2_total = int(round(base + bonus_self - bonus_opp))

        s0, s1 = board.state.scores
        moves.append(
            {
                "move": move_idx,
                "actor": actor,
                "action": action_desc,
                "score_p0": int(s0),
                "score_p1": int(s1),
                "base": int(base),
                "bonus_self": float(bonus_self),  # capped, fed to search
                "bonus_opp": float(bonus_opp),
                "raw_self": float(raw_self),  # uncapped, shows what WOULD fire
                "raw_opp": float(raw_opp),
                "v2": v2_total,
                "rows_self": rows_self,
                "rows_opp": rows_opp,
            }
        )
        move_idx += 1

    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    hybrid_score = s0 if hybrid_idx == 0 else s1
    tier1_score = s1 if hybrid_idx == 0 else s0
    return {
        "seed": seed,
        "hybrid_idx": hybrid_idx,
        "hybrid_score": int(hybrid_score),
        "tier1_score": int(tier1_score),
        "hybrid_won": hybrid_score > tier1_score,
        "moves": moves,
        "elapsed_s": elapsed,
    }


def report(result: dict) -> None:
    moves = result["moves"]
    print()
    print(f"=== seed={result['seed']} hybrid={'p0' if result['hybrid_idx']==0 else 'p1'} "
          f"final {result['hybrid_score']}-{result['tier1_score']} "
          f"{'WON' if result['hybrid_won'] else 'LOST'} "
          f"({result['elapsed_s']:.1f}s, {len(moves)} moves) ===")

    # Aggregate signals.
    cathedral_fires = 0
    sign_flips = 0  # |net_bonus_capped| > |base|
    bonus_magnitude_excess = 0  # capped sum > |base|
    cap_hit_self = 0  # raw_self exceeded cap
    cap_hit_opp = 0  # raw_opp exceeded cap
    terrain_contrib_self: dict[str, float] = defaultdict(float)
    terrain_contrib_opp: dict[str, float] = defaultdict(float)
    max_raw_self = 0.0
    max_raw_opp = 0.0

    for m in moves:
        for r in m["rows_self"]:
            terrain_contrib_self[r["terrain"]] += r["contrib"]
            if r["cathedral_fired"]:
                cathedral_fires += 1
        for r in m["rows_opp"]:
            terrain_contrib_opp[r["terrain"]] += r["contrib"]
            if r["cathedral_fired"]:
                cathedral_fires += 1
        net_bonus = m["bonus_self"] - m["bonus_opp"]
        if m["base"] != 0 and abs(net_bonus) > abs(m["base"]):
            sign_flips += 1
        if (m["bonus_self"] + m["bonus_opp"]) > abs(m["base"]):
            bonus_magnitude_excess += 1
        if m["raw_self"] > _BONUS_CAP:
            cap_hit_self += 1
        if m["raw_opp"] > _BONUS_CAP:
            cap_hit_opp += 1
        max_raw_self = max(max_raw_self, m["raw_self"])
        max_raw_opp = max(max_raw_opp, m["raw_opp"])

    print()
    print("--- aggregate signals ---")
    print(f"  total moves                 : {len(moves)}")
    print(f"  cathedral branch firings    : {cathedral_fires}  {'<-- BUG: cathedrals not in scope' if cathedral_fires else ''}")
    print(f"  bonus cap (production)      : ±{_BONUS_CAP}")
    print(f"  cap hits (self)             : {cap_hit_self}/{len(moves)} ({100*cap_hit_self/len(moves):.0f}%) — moves where raw exceeded cap")
    print(f"  cap hits (opp)              : {cap_hit_opp}/{len(moves)} ({100*cap_hit_opp/len(moves):.0f}%)")
    print(f"  |net_bonus(capped)| > |base|: {sign_flips}/{len(moves)} ({100*sign_flips/len(moves):.0f}%)")
    print(f"  capped_sum > |base| moves   : {bonus_magnitude_excess}/{len(moves)} ({100*bonus_magnitude_excess/len(moves):.0f}%)")
    print(f"  max RAW bonus_self          : {max_raw_self:.1f}")
    print(f"  max RAW bonus_opp           : {max_raw_opp:.1f}")
    print()
    print("  contribution by terrain (self):")
    for t, c in sorted(terrain_contrib_self.items(), key=lambda x: -x[1]):
        print(f"    {t:<10} {c:>8.1f}")
    print("  contribution by terrain (opp):")
    for t, c in sorted(terrain_contrib_opp.items(), key=lambda x: -x[1]):
        print(f"    {t:<10} {c:>8.1f}")

    # Per-move table — sample every 5 moves + last 10 + any big bonus event.
    print()
    print("--- per-move trace (sampled) ---")
    print(f"  {'mv':>3} {'actor':<10} {'action':<26} {'p0':>3} {'p1':>3} "
          f"{'base':>5} {'b_s':>5} {'b_o':>5} {'raw_s':>6} {'raw_o':>6} {'v2':>5}")
    last_n = 10
    cutoff = max(0, len(moves) - last_n)
    for m in moves:
        big_event = (m["raw_self"] >= 2 * _BONUS_CAP or m["raw_opp"] >= 2 * _BONUS_CAP)
        if (m["move"] % 5 == 0) or (m["move"] >= cutoff) or big_event:
            flag = ""
            if big_event:
                flag += " *"
            if m["base"] != 0 and abs(m["bonus_self"] - m["bonus_opp"]) > abs(m["base"]):
                flag += " !"
            print(f"  {m['move']:>3} {m['actor']:<10} {m['action']:<26} "
                  f"{m['score_p0']:>3} {m['score_p1']:>3} "
                  f"{m['base']:>+5d} {m['bonus_self']:>5.1f} {m['bonus_opp']:>5.1f} "
                  f"{m['raw_self']:>6.1f} {m['raw_opp']:>6.1f} "
                  f"{m['v2']:>+5d}{flag}")

    # Print first 3 moves where a cathedral branch fired, if any.
    if cathedral_fires:
        print()
        print("--- cathedral branch firings (likely BUG) ---")
        n_shown = 0
        for m in moves:
            if n_shown >= 3:
                break
            for r in m["rows_self"] + m["rows_opp"]:
                if r["cathedral_fired"]:
                    print(f"  move {m['move']} {m['actor']} terrain={r['terrain']} "
                          f"coord={r['coord']} p={r['p']:.2f} delta={r['delta']} "
                          f"contrib={r['contrib']:.1f}")
                    n_shown += 1
                    break


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=1)
    p.add_argument("--sims", type=int, default=100)
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=REPO_ROOT / "checkpoints" / "warmstart_canonical.pt",
    )
    args = p.parse_args()

    # In-process — diagnostic only, no need for spawn pool. Init net once.
    _init_net(str(args.checkpoint.resolve()))

    print(f"=== diagnose_v2: hybrid_v2 vs Tier-1 at sims={args.sims}, n={args.n} ===")
    for i in range(args.n):
        seed = args.seed_start + i
        hybrid_idx = i % 2
        r = play_one(seed, hybrid_idx, args.sims)
        report(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
