"""Multi-source endgame position generator (selection-bias control for L2-3/K4).

The original gen_endgame_positions.py snapshots GREEDY self-play only. The K=4
probe needs positions from a SPREAD of generators so we can test whether the
solver's tractable set is biased toward one agent's style (a higher-K suite is
useless if it only solves the easy boards one policy happens to reach). Sources:

    greedy        RuleBasedPlayer (1-ply, neutral, fast)
    iter8         production NeuralMCTS@200 (c_puct=3.0, residual_scale=0.25)
    heur@3200     HeuristicMCTS@3200, v2.7 leaf (the deepest heuristic)
    hybrid:K:N    iter8 until k_remaining<=K, then heur@N (the Phase-1 handoff)

RECONSTRUCTION: unlike the greedy generator we do NOT rely on (seed, ply) replay
(that would re-run MCTS at solve time). Each record stores the full ACTION-INDEX
SEQUENCE up to the snapshot; `replay_actions(seed, actions)` reconstructs the
exact Board by replaying those actions through the engine transition — no MCTS,
source-agnostic, deterministic. Action indices are window-offset-relative, but
replaying the identical sequence evolves the offset identically, so they stay
valid (this is exactly how the engine consumes them during play).

The deck shuffle is fixed by `random.seed(seed)` at get_init_board (same as the
greedy generator); the agents use their own fixed-seed RNGs for tie-breaks.

Usage:
  python scripts/level2/gen_endgame_multisource.py --band 3500000000 \
      --sources greedy iter8 heur@3200 hybrid:8:3200 --games-per-source 15 \
      --ks 4 5 --ckpt /mnt/.../iter8.pt --device cpu --workers 8 \
      --out measurement/level2/l23_k4_multisource.jsonl
"""
from __future__ import annotations

import os
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import dataclasses
import json
import random
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from wingedsheep.carcassonne.objects.game_phase import GamePhase

GEN_PLAYER_SEED = 70123  # fixed tie-break seed (matches gen_endgame_positions)


def _new_game():
    return Game(enable_legal_moves_cache=True)


def k_remaining(board) -> int:
    return len(board.state.deck) + (1 if board.state.next_tile is not None else 0)


def replay_actions(seed: int, actions: list[int]):
    """Reconstruct (game, board) by replaying a recorded action-index sequence.
    Source-agnostic, no MCTS. Mirrors the engine's own consumption of actions."""
    random.seed(seed)  # fixes the deck shuffle (same as gen_endgame_positions.replay_to)
    game = _new_game()
    board = game.get_init_board()
    for a in actions:
        board, _ = game.get_next_state(board, int(a))
    return game, board


# --- policies --------------------------------------------------------------- #
# Each policy is choose(game, board, seed) -> action_idx. The neural/hybrid
# policies hold per-worker net state in _W (set by _worker_init).
_W: dict = {}


def _make_iter8_mcts(game_farm, seed):
    import dataclasses as _dc
    from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
    from carcassonne_ai.mcts import NeuralMCTS
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    base = make_single_evaluator(_W["net"], _W["dev"], game_farm)
    cfg = _dc.replace(DEFAULT_CONFIG, residual_scale=0.25)
    leaf = make_v25_value_wrapper(base, cfg)
    return NeuralMCTS(game=game_farm, evaluator=leaf, simulations=200, seed=seed, c_puct=3.0)


def _make_heur_mcts(game_plain, sims, seed):
    from carcassonne_ai.mcts import HeuristicMCTS
    return HeuristicMCTS(game=game_plain, simulations=sims, seed=seed, heur_leaf="v2_7")


class _Policy:
    """Pluggable source policy. greedy/heur are stateless per move; iter8/hybrid
    need the net (game_farm) and hybrid latches once k_remaining<=K."""

    def __init__(self, spec: str):
        self.spec = spec
        self.kind = spec.split(":")[0]
        self.hybrid_K = self.hybrid_N = None
        self.heur_sims = None
        if self.kind == "hybrid":
            _, k, n = spec.split(":")
            self.hybrid_K, self.hybrid_N = int(k), int(n)
        elif self.kind == "heur":
            self.heur_sims = int(spec.split("@")[1])
        self.latched = False  # hybrid: switched to heur yet?

    def reset(self):
        self.latched = False

    def choose(self, game_plain, game_farm, board, seed) -> int:
        kind = self.kind
        if kind == "greedy":
            rb = RuleBasedPlayer(seed=seed)
            return int(rb.choose_action(game_plain, board, game_plain.get_valid_moves(board)))
        if kind == "heur":
            return int(_make_heur_mcts(game_plain, self.heur_sims, seed).best_action(board))
        if kind == "iter8":
            return int(_make_iter8_mcts(game_farm, seed).best_action(board))
        if kind == "hybrid":
            # latch to heur at the first own TILES decision with k_remaining<=K
            if not self.latched and board.state.phase == GamePhase.TILES \
                    and k_remaining(board) <= self.hybrid_K:
                self.latched = True
            if self.latched:
                return int(_make_heur_mcts(game_plain, self.hybrid_N, seed).best_action(board))
            return int(_make_iter8_mcts(game_farm, seed).best_action(board))
        raise ValueError(f"unknown source policy: {self.spec}")


def _provenance(game, board, ply, seed, source, actions) -> dict:
    s = board.state
    deck_descs = [t.description for t in s.deck]
    return {
        "gen_id": f"{source.replace(':','_').replace('@','')}_s{seed}",
        "source_agent": source,
        "seed": seed,
        "ply": ply,
        "actions": list(actions),               # full prefix -> replay_actions reconstructs
        "k_remaining": k_remaining(board),
        "to_move": int(s.current_player),
        "scores": [int(s.scores[0]), int(s.scores[1])],
        "meeples": {"free": [int(s.meeples[0]), int(s.meeples[1])],
                    "placed": [len(s.placed_meeples[0]), len(s.placed_meeples[1])]},
        "in_hand_tile": s.next_tile.description if s.next_tile is not None else None,
        "bag_multiset": dict(sorted(Counter(deck_descs).items())),
        "bag_size": len(deck_descs),
        "known_order": deck_descs,
        "legal_n": int(game.get_valid_moves(board).sum()),
        "checksum": game.string_representation(board),
    }


def generate_game(seed: int, source: str, want_ks: set[int]) -> list[dict]:
    """Play one self-play game with `source`'s policy, snapshotting the first
    TILES position at each target K, recording the action prefix for replay."""
    random.seed(seed)
    game_plain = _new_game()
    game_farm = Game(enable_legal_moves_cache=True,
                     include_farm_scalars=(_W.get("ns", 10) > 10)) if source.startswith(("iter8", "hybrid")) else game_plain
    board = game_plain.get_init_board()
    pol = _Policy(source)
    pol.reset()
    actions: list[int] = []
    seen: dict[int, dict] = {}
    ply = 0
    while game_plain.get_game_ended(board, 0) == 0.0:
        if board.state.phase == GamePhase.TILES:
            k = k_remaining(board)
            if k in want_ks and k not in seen:
                seen[k] = _provenance(game_plain, board, ply, seed, source, actions)
        move_seed = (seed * 131 + ply) & 0x7FFFFFFF
        a = pol.choose(game_plain, game_farm, board, move_seed)
        board, _ = game_plain.get_next_state(board, int(a))
        actions.append(int(a))
        ply += 1
    return [seen[k] for k in sorted(seen)]


# --- pool plumbing ---------------------------------------------------------- #
_CFG: dict = {}


def _worker_init(ckpt, device_str, needs_net):
    import torch
    torch.set_num_threads(1)
    dev = torch.device(device_str)
    _W["dev"] = dev
    if needs_net:
        from carcassonne_ai.network import CarcassonneNet
        ck = torch.load(ckpt, map_location=dev, weights_only=False)
        ns = int(ck.get("n_scalar_features", 10))
        net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                             n_scalar_features=ns,
                             value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
        net.load_state_dict(ck["model_state"])
        net.train(False)
        _W["net"] = net
        _W["ns"] = ns


def _gen_one(arg):
    seed, source, want = arg
    try:
        return generate_game(seed, source, want)
    except Exception as e:  # noqa - one game dying shouldn't kill the suite
        print(f"  {source} seed {seed} skipped: {repr(e)[:120]}", file=sys.stderr, flush=True)
        return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", type=int, default=3_500_000_000)
    ap.add_argument("--sources", nargs="+",
                    default=["greedy", "iter8", "heur@3200", "hybrid:8:3200"])
    ap.add_argument("--games-per-source", type=int, default=15)
    ap.add_argument("--ks", type=int, nargs="+", default=[4, 5])
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="measurement/level2/l23_k4_multisource.jsonl")
    args = ap.parse_args(argv)
    want = set(args.ks)
    needs_net = any(s.startswith(("iter8", "hybrid")) for s in args.sources)
    if needs_net and not args.ckpt:
        ap.error("iter8/hybrid sources need --ckpt")

    # Distinct seed sub-band per source so positions never collide across sources.
    tasks = []
    for si, source in enumerate(args.sources):
        base = args.band + si * 1_000_000
        for i in range(args.games_per_source):
            tasks.append((base + i, source, want))

    from multiprocessing import get_context
    ctx = get_context("fork")
    print(f"multisource gen: {len(args.sources)} sources x {args.games_per_source} games, "
          f"K={sorted(want)}, device={args.device}, W={args.workers}", flush=True)
    t0 = time.perf_counter()
    records = []
    with ctx.Pool(args.workers, initializer=_worker_init,
                  initargs=(args.ckpt, args.device, needs_net)) as pool:
        done = 0
        for recs in pool.imap_unordered(_gen_one, tasks, chunksize=1):
            records.extend(recs)
            done += 1
            if done % 5 == 0:
                el = time.perf_counter() - t0
                print(f"  {done}/{len(tasks)} games, {len(records)} positions "
                      f"({el/done:.1f}s/game, ~{(len(tasks)-done)*el/done/60:.0f} min left)", flush=True)

    records.sort(key=lambda r: (r["source_agent"], r["seed"], r["k_remaining"]))
    with open(args.out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(records)} positions to {args.out}")
    print("by source x K:")
    bsk = Counter((r["source_agent"], r["k_remaining"]) for r in records)
    for (src, k) in sorted(bsk):
        print(f"  {src:<16} K={k}: {bsk[(src, k)]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
