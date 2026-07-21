"""F3 §1 — mine genuinely-hidden late roots for the public-state oracle.

Produces the root suite the oracle scores: TILES-phase roots in the K band with a
GENUINELY HIDDEN draw (bag has >=2 distinct tile types), >=2 legal actions, with
per-root provenance (fully reconstructable) + stratum flags + a checksum guard.

ROOT SOURCE (updated 2026-07-21): the spec's PRIMARY source — champion fair-PIMC
k4x688 self-play (deck_seed, actions) game logs via root_replay — NOW EXISTS. Generate
it with the champion self-play emitter:

    scripts/distill_flywheel/gen_fair_distill.py --games N --k-dets 4 --sims 688 \
        --actions-only --shared-claim --seed-start <fresh band> --out <share dir>
    scripts/distill_flywheel/collect_action_logs.py --in <share dir> --out <games.jsonl>

then mine with `--source champion --games <games.jsonl>`.

(2026-07-20 history: no such logs existed — only head-to-head eval SUMMARIES with no
actions array — so the buildable default was the spec's documented FALLBACK, the greedy
L2-3 distribution: a neutral generator where 96% of K=3 roots are genuinely hidden.
`--source greedy` remains the default flag value, and roots_k3_suite.jsonl is the greedy
suite the first F3/Gate-B runs used. The two distributions are NOT interchangeable: at
K=3 the champion holds far more meeples in hand and reaches much higher scores.)

Sources:
  --source greedy  --positions measurement/level2/l23_positions.jsonl   (reconstruct via replay_to)
  --source greedy  --generate --band <seed> --n <games>                 (fresh greedy self-play)
  --source champion --games <deck_seed+actions jsonl>                   (root_replay; when it exists)

Reconstruction: greedy = gen_endgame_positions.replay_to(seed, ply); champion =
root_replay.replay_actions(deck_seed, actions, ply). Every record's checksum is
verified on reconstruction at mine time (and again at solve time, test I).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Production leaf env before any carcassonne_ai import (decompose/leaf are curve-
# independent, but keep the whole toolchain on the production shape).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_preamble  # noqa: E402,F401

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import argparse  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
from collections import Counter  # noqa: E402

import numpy as np  # noqa: E402

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.rule_based_player import RuleBasedPlayer  # noqa: E402
from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import sighted_planes as SP  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.objects.meeple_type import MeepleType  # noqa: E402

import gen_endgame_positions as GEP  # noqa: E402  (replay_to, k_remaining)
import root_replay as RR  # noqa: E402

GEN_PLAYER_SEED = GEP.GEN_PLAYER_SEED


# --------------------------------------------------------------------------- #
# Filters & strata (§1.4)                                                       #
# --------------------------------------------------------------------------- #
def genuinely_hidden(board) -> bool:
    """>=2 tiles left in the deck AND >=2 distinct tile types (entropy > 0)."""
    descs = [t.description for t in board.state.deck]
    return len(descs) >= 2 and len(set(descs)) >= 2


def _placed_meeple_coords(state) -> set:
    out = set()
    for p in range(state.players):
        for mp in state.placed_meeples[p]:
            cws = mp.coordinate_with_side
            out.add((cws.coordinate.row, cws.coordinate.column))
    return out


def strata_flags(game, board) -> dict:
    """Deterministic board-type tags for balanced sampling (§1.4). Best-effort on
    the decomposition-derived tags (guarded); live_meeple is exact from state."""
    s = board.state
    flags = {
        "contested_farm": False,
        "open_city": False,
        "live_meeple": bool(s.meeples[0] >= 1 or s.meeples[1] >= 1),
    }
    try:
        decomp = flat_leaf.decompose(s)
        owners = SP._farm_component_owners(s, decomp, root_player=int(s.current_player))
        flags["contested_farm"] = any(v == "contested" for v in owners.values())
        meepled_coords = _placed_meeple_coords(s)
        for root, coords in decomp.city_root_coords.items():
            if decomp.city_root_finished.get(root, False):
                continue
            if decomp.city_root_open_n.get(root, 99) > 2:
                continue
            if any(rc in meepled_coords for rc in coords):
                flags["open_city"] = True
                break
    except Exception as e:  # noqa - strata are metadata; never kill mining on them
        flags["_strata_error"] = f"{type(e).__name__}: {e}"
    return flags


def _tag_top2_gap(game, board, sims: int = 200) -> float | None:
    """h200 top-2 Q-gap (§1.4 stratum 4). Optional (costs a search); None if off."""
    from carcassonne_ai.mcts import HeuristicMCTS
    import tagging
    agent = HeuristicMCTS(game=game, simulations=sims, c=3.0, seed=12345,
                          heur_leaf="v2_7")
    try:
        tags = tagging.tag_root(agent, board, sims=sims)
        return float(tags["top2_q_gap"])
    finally:
        agent.clear()


# --------------------------------------------------------------------------- #
# Provenance (§1.3, reuses gen_endgame_positions._provenance fields)            #
# --------------------------------------------------------------------------- #
def provenance(game, board, *, source_agent: str, ids: dict, ply: int,
               tag_gap: bool = False) -> dict:
    s = board.state
    deck_descs = [t.description for t in s.deck]
    rec = {
        "source_agent": source_agent,
        "ply": int(ply),
        "k_remaining": GEP.k_remaining(board),
        "to_move": int(s.current_player),
        "scores": [int(s.scores[0]), int(s.scores[1])],
        "meeples": {"free": [int(s.meeples[0]), int(s.meeples[1])],
                    "placed": [len(s.placed_meeples[0]), len(s.placed_meeples[1])]},
        "in_hand_tile": s.next_tile.description if s.next_tile is not None else None,
        "bag_multiset": dict(sorted(Counter(deck_descs).items())),
        "bag_size": len(deck_descs),
        "n_distinct_types": len(set(deck_descs)),
        "known_order": deck_descs,
        "legal_n": int(game.get_valid_moves(board).sum()),
        "checksum": game.string_representation(board),
    }
    rec.update(ids)                       # seed/ply (greedy) or game_id/deck_seed/actions (champ)
    rec["strata"] = strata_flags(game, board)
    rec["top2_q_gap"] = _tag_top2_gap(game, board) if tag_gap else None
    return rec


def _passes(game, board) -> bool:
    """§1.4 exclusions applied at mine time: TILES phase, >=2 legal, genuinely hidden.
    (The 'effectively decided' spread<0.5 exclusion needs the exact solve -> applied
    downstream in run_oracle, which marks decided=True; documented there.)"""
    if board.state.phase != GamePhase.TILES:
        return False
    if int(game.get_valid_moves(board).sum()) < 2:
        return False
    return genuinely_hidden(board)


# --------------------------------------------------------------------------- #
# Source: greedy from an l23_positions.jsonl snapshot file                      #
# --------------------------------------------------------------------------- #
def _mine_one_l23(arg):
    r, tag_gap = arg
    seed, ply = int(r["seed"]), int(r["ply"])
    try:
        game, board = GEP.replay_to(seed, ply)
    except Exception as e:  # noqa
        return ("recon_fail", seed, ply, str(e))
    if game.string_representation(board) != r["checksum"]:
        return ("checksum_mismatch", seed, ply, None)
    if not _passes(game, board):
        return None
    return provenance(game, board, source_agent="greedy_selfplay_l23",
                      ids={"seed": seed, "ply": ply}, ply=ply, tag_gap=tag_gap)


def mine_from_l23(records, band: set, tag_gap: bool, workers: int = 4) -> list:
    from multiprocessing import get_context
    args = [(r, tag_gap) for r in records if int(r["k_remaining"]) in band]
    out = []
    ctx = get_context("fork")
    with ctx.Pool(workers) as pool:
        for res in pool.imap_unordered(_mine_one_l23, args, chunksize=2):
            if res is None:
                continue
            if isinstance(res, tuple):
                print(f"  {res[0]} seed={res[1]} ply={res[2]}: {res[3]}", file=sys.stderr)
                continue
            out.append(res)
    return out


# --------------------------------------------------------------------------- #
# Source: fresh greedy self-play generation (like gen_endgame_positions)         #
# --------------------------------------------------------------------------- #
def _generate_one(arg):
    seed, band, tag_gap = arg
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=GEN_PLAYER_SEED)
    seen: dict = {}
    ply = 0
    while game.get_game_ended(board, 0) == 0.0:
        if board.state.phase == GamePhase.TILES:
            k = GEP.k_remaining(board)
            if k in band and k not in seen and _passes(game, board):
                seen[k] = provenance(game, board, source_agent="greedy_selfplay_gen",
                                     ids={"seed": seed, "ply": ply}, ply=ply,
                                     tag_gap=tag_gap)
        a = player.choose_action(game, board, game.get_valid_moves(board))
        board, _ = game.get_next_state(board, int(a))
        ply += 1
    return list(seen.values())


def mine_from_generate(band: set, seed_band: int, n: int, workers: int,
                       tag_gap: bool) -> list:
    from multiprocessing import get_context
    seeds = [seed_band + i for i in range(n)]
    args = [(s, band, tag_gap) for s in seeds]
    out = []
    ctx = get_context("fork")
    with ctx.Pool(workers) as pool:
        for recs in pool.imap_unordered(_generate_one, args, chunksize=2):
            out.extend(recs)
    return out


# --------------------------------------------------------------------------- #
# Source: champion (or any) self-play (deck_seed, actions) game logs             #
# --------------------------------------------------------------------------- #
def mine_from_champion(games_path: str, band: set, tag_gap: bool) -> list:
    games = RR.load_games(games_path)
    out = []
    for g in games:
        seen: dict = {}
        game, board = RR.replay_actions(g.deck_seed, g.actions, 0)
        ply = 0
        n = len(g.actions)
        while ply <= n and game.get_game_ended(board, 0) == 0.0:
            if board.state.phase == GamePhase.TILES:
                k = GEP.k_remaining(board)
                if k in band and k not in seen and _passes(game, board):
                    seen[k] = provenance(
                        game, board, source_agent=g.meta.get("gen", "champion_fair"),
                        ids={"game_id": int(g.game_id), "deck_seed": int(g.deck_seed),
                             "actions": list(g.actions), "ply": ply},
                        ply=ply, tag_gap=tag_gap)
            if ply >= n:
                break
            board, _ = game.get_next_state(board, int(g.actions[ply]))
            ply += 1
        out.extend(seen.values())
    return out


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["greedy", "champion"], default="greedy")
    ap.add_argument("--positions", default=str(REPO / "measurement" / "level2" / "l23_positions.jsonl"),
                    help="greedy snapshot jsonl (seed+ply); used when not --generate")
    ap.add_argument("--generate", action="store_true", help="greedy: fresh self-play instead of --positions")
    ap.add_argument("--band", type=int, default=3_400_000_000, help="greedy --generate seed band")
    ap.add_argument("--n", type=int, default=400, help="greedy --generate #games")
    ap.add_argument("--games", default=None, help="champion (deck_seed,actions) game log jsonl")
    ap.add_argument("--ks", type=int, nargs="+", default=[3], help="K band (default 3-only, the buildable phase)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", action="store_true", help="compute the h200 top-2 Q gap per root (costs a search)")
    ap.add_argument("--out", default=str(REPO / "measurement" / "f3_public_state_oracle" / "roots.jsonl"))
    args = ap.parse_args(argv)

    band = set(args.ks)
    if args.source == "champion":
        if not args.games:
            ap.error("--source champion requires --games <jsonl>")
        recs = mine_from_champion(args.games, band, args.tag)
    elif args.generate:
        recs = mine_from_generate(band, args.band, args.n, args.workers, args.tag)
    else:
        with open(args.positions) as f:
            src = [json.loads(l) for l in f if l.strip()]
        recs = mine_from_l23(src, band, args.tag, workers=args.workers)

    recs.sort(key=lambda r: (r["k_remaining"], r.get("seed", r.get("game_id", 0)), r["ply"]))
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")

    by_k = Counter(r["k_remaining"] for r in recs)
    strata = {name: sum(1 for r in recs if r["strata"].get(name))
              for name in ("contested_farm", "open_city", "live_meeple")}
    print(f"wrote {len(recs)} genuinely-hidden roots to {outp}")
    print("by K:", dict(sorted(by_k.items())))
    print("strata counts:", strata)
    print("pass note: 'effectively decided' (child spread<0.5) is applied downstream in run_oracle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
