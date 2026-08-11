#!/usr/bin/env python3
"""Multi-phase root-position suite for the deeper-search audit (Part D).

Same DETERMINISTIC greedy (RuleBasedPlayer) generator + replay_to(seed,ply) as the
endgame suite (scripts/level2/gen_endgame_positions.py), but snapshots the first
TILES-phase board at target k_remaining (= tiles left in bag) buckets spanning the
WHOLE game (opening -> endgame), not just the endgame tail. Agent-unbiased boards;
suite is fixed once written (committed) so every agent + re-run sees identical positions.

Phase label (by k_remaining): endgame 2-6 | pre_endgame 7-14 | late_mid 15-28 |
midgame 29-46 | opening 47+. Each record also carries legal_n, free/placed meeples,
scores, placed-farmer count (farm-heaviness), to_move, and the checksum for replay.

  python scripts/deeper_search/gen_multiphase_positions.py --band 1925000000 --n 90 \
      --out measurement/deeper_search_ruler/multiphase_positions.jsonl
"""
from __future__ import annotations
import argparse, json, os, random, sys
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from wingedsheep.carcassonne.objects.game_phase import GamePhase

GEN_PLAYER_SEED = 70123
SOURCE_AGENT = "greedy_selfplay"
# k_remaining buckets spanning the whole game (first TILES position at each, per game)
DEFAULT_KS = [2, 3, 4, 5, 6, 8, 10, 12, 14, 18, 22, 26, 32, 38, 44, 50, 56, 62]


def k_remaining(board) -> int:
    return len(board.state.deck) + (1 if board.state.next_tile is not None else 0)


def phase_of(k: int) -> str:
    if k <= 6:   return "endgame"
    if k <= 14:  return "pre_endgame"
    if k <= 28:  return "late_mid"
    if k <= 46:  return "midgame"
    return "opening"


def _placed_farmers(state) -> int:
    """Count placed meeples sitting on a FIELD (farmer) position, both players.
    Robust to engine field-name variants; falls back to -1 if not introspectable."""
    n = 0
    try:
        for pid in (0, 1):
            for pm in state.placed_meeples[pid]:
                cs = getattr(pm, "coordinate_with_side", None) or getattr(pm, "position", None)
                side = getattr(cs, "side", None)
                nm = getattr(side, "name", str(side)).upper() if side is not None else ""
                if "FIELD" in nm or "FARM" in nm:
                    n += 1
    except Exception:
        return -1
    return n


def _provenance(game, board, ply, seed):
    s = board.state
    deck_descs = [t.description for t in s.deck]
    k = k_remaining(board)
    return {
        "gen_id": f"mp{seed}", "source_agent": SOURCE_AGENT, "seed": seed, "ply": ply,
        "k_remaining": k, "phase": phase_of(k), "to_move": int(s.current_player),
        "scores": [int(s.scores[0]), int(s.scores[1])],
        "score_margin_abs": abs(int(s.scores[0]) - int(s.scores[1])),
        "meeples_free": [int(s.meeples[0]), int(s.meeples[1])],
        "meeples_placed": [len(s.placed_meeples[0]), len(s.placed_meeples[1])],
        "placed_farmers": _placed_farmers(s),
        "in_hand_tile": s.next_tile.description if s.next_tile is not None else None,
        "bag_size": len(deck_descs), "known_order": deck_descs,
        "legal_n": int(game.get_valid_moves(board).sum()),
        "checksum": game.string_representation(board),
    }


def generate_game(seed, want_ks):
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=GEN_PLAYER_SEED)
    seen, ply = {}, 0
    while game.get_game_ended(board, 0) == 0.0:
        if board.state.phase == GamePhase.TILES:
            k = k_remaining(board)
            if k in want_ks and k not in seen:
                seen[k] = _provenance(game, board, ply, seed)
        mask = game.get_valid_moves(board)
        a = player.choose_action(game, board, mask)
        board, _ = game.get_next_state(board, int(a))
        ply += 1
    return [seen[k] for k in sorted(seen)]


def _gen_one(arg):
    seed, want = arg
    try:
        return generate_game(seed, want)
    except Exception as e:
        print(f"  seed {seed} skipped: {e}", file=sys.stderr); return []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", type=int, default=1_925_000_000)
    ap.add_argument("--n", type=int, default=90, help="number of generator games")
    ap.add_argument("--ks", type=int, nargs="+", default=DEFAULT_KS)
    ap.add_argument("--out", default="measurement/deeper_search_ruler/multiphase_positions.jsonl")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args(argv)
    want = set(args.ks)
    seeds = [args.band + i for i in range(args.n)]
    records = []
    from multiprocessing import get_context
    with get_context("fork").Pool(args.workers) as pool:
        done = 0
        for recs in pool.imap_unordered(_gen_one, [(s, want) for s in seeds], chunksize=2):
            records.extend(recs); done += 1
            if done % 30 == 0:
                print(f"  {done}/{args.n} games, {len(records)} positions", flush=True)
    records.sort(key=lambda r: (r["seed"], r["k_remaining"]))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(records)} positions to {args.out}")
    print("by phase:", dict(Counter(r["phase"] for r in records)))
    print("by k:", dict(sorted(Counter(r["k_remaining"] for r in records).items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
