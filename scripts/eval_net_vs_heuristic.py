"""Measurement ladder (#1): the learned net vs a STRONG non-saturated reference.

The project's measurement wall: Tier-1 (1-ply heuristic) is saturated, and
self-anchored elo (iter_N vs warm/prev) can climb while absolute strength
regresses. We need an opponent that is (a) strong, (b) NOT saturated, (c) gives
an absolute-ish read. **HeuristicMCTS** = a virtual_score leaf + UCT search
(mcts.py), with NO learned policy. So:

    NeuralMCTS(net priors + v2.7 leaf value)  vs  HeuristicMCTS(--heur-leaf)
    at MATCHED sims.

This isolates the LEARNED POLICY's contribution over pure heuristic search at
equal compute — BUT ONLY IF both sides use the SAME leaf.

⚠ R1 (outside-review 2026-06-07): HeuristicMCTS historically ran the **v1** leaf
(base virtual_score) by default, while the neural side runs **v2.7**
(make_v25_value_wrapper). So the legacy default did NOT hold the leaf fixed — its
margin confounded the learned policy with the v2.7-vs-v1 leaf gap. Pass
``--heur-leaf v2_7`` to give the opponent the matching v2.7 leaf and measure the
policy alone. The default stays ``v1`` so prior ladder numbers remain comparable;
new isolating runs should pass ``--heur-leaf v2_7``.

IMPORTANT: the neural side uses the PRODUCTION play config — net priors + v2.7
leaf value (make_v25_value_wrapper) — NOT the raw net value head (which Step 9
showed is a bad search leaf).

Per-game JSON checkpoint (resumable), multiprocessing pool. Mirror
play_mcts_vs_random / eval_neural_mcts_vs_vanilla conventions.

Usage:
  python -u scripts/eval_net_vs_heuristic.py --checkpoint <ckpt> \
      --n 100 --sims 200 --c-puct 3.0 --workers 14
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass
import multiprocessing as mp
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import torch

from carcassonne_ai.claim import try_claim as _try_claim
from carcassonne_ai import eval_provenance as ep
from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.run_manifest import game_tag, write_manifest
from carcassonne_ai.selfplay import _bench_tick  # gated moves/s instrumentation (CARC_BENCH_TP)
from carcassonne_ai.eval_provenance import deck_hash
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

REPO = Path(__file__).resolve().parent.parent
EVAL_ROOT = REPO / "data" / "ladder"

_worker_net = None
_worker_device = None
_worker_include_farm = False
# M2 sighted rep + FPU knob (both default-off → byte-identical to prior eval).
_worker_sighted = False
_worker_fpu: float | None = None
# Leaf the HeuristicMCTS opponent uses: "v1" (legacy default) or "v2_7" (match the
# agent's leaf so the eval isolates the policy — outside-review finding R1).
_worker_heur_leaf: str = "v1"
# Residual scale override (None = use DEFAULT_CONFIG / env; a float forces the
# leaf wrapper's residual_scale, e.g. 0.0 for the pure-v2.7 control or 0.25 for
# the residual cell). Plumbed through for Phase-3 #4/#5.
_worker_residual_scale: float | None = None
# Work-stealing claim (only used with --shared-claim). Mirrors eval_iter_head_to_head.
_worker_shared_claim: bool = False
_worker_claim_host: str = ""
_worker_claim_stale_secs: int = 5400
# Orchestrator (carc-orch SHM) client. When _worker_orch, the net forward
# (priors+value) comes from the shared GPU server over _worker_handles instead
# of a per-worker net; the v2.7 leaf + residual still run on the worker (CPU).
_worker_orch: bool = False
_worker_handles = None


@dataclass
class GameResult:
    seed: int
    net_player: int
    sims: int
    heur_sims: int
    c_puct: float
    score_p0: int
    score_p1: int
    diff: int          # net - heuristic
    won_by_net: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""        # 16-hex deck identity (default keeps old JSON loadable)


def _result_path(out: Path, sims: int, heur_sims: int, c_puct: float,
                 seed: int, net_player: int) -> Path:
    ct = str(c_puct).replace(".", "")
    return out / f"n{sims:04d}_h{heur_sims:04d}_c{ct}_seed{seed:06d}_p{net_player}.json"


def _try_load(p: Path):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p: Path, r: GameResult):
    p.parent.mkdir(parents=True, exist_ok=True)
    # dot-prefixed (so *seed*.json globs in the flywheel wait-loops/gate_elo never count it)
    # + host/pid-unique (so two boxes replaying the same seed after an orphan-stall heal can't
    # corrupt a shared temp). Mirrors warmstart.py's .npz pattern. Shell-audit w3gbnte6z #3/#7.
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    json.dump(asdict(r), open(tmp, "w"))
    tmp.replace(p)


def _worker_init(checkpoint: str, shared_claim: bool = False,
                 claim_host: str = "", claim_stale_secs: int = 5400,
                 heur_leaf: str = "v1", residual_scale: float | None = None,
                 shm_name: str = "", id_q=None, ns: int = 10,
                 fpu: float | None = None, nch: int = N_CHANNELS,
                 sighted: bool = False):
    global _worker_net, _worker_device, _worker_include_farm, _worker_heur_leaf
    global _worker_shared_claim, _worker_claim_host, _worker_claim_stale_secs
    global _worker_residual_scale, _worker_orch, _worker_handles
    global _worker_sighted, _worker_fpu
    _worker_shared_claim = shared_claim
    _worker_claim_host = claim_host
    _worker_claim_stale_secs = claim_stale_secs
    _worker_heur_leaf = heur_leaf
    _worker_residual_scale = residual_scale
    _worker_fpu = fpu
    if shm_name:
        # Orchestrator (carc-orch SHM): the server owns the only net copy; the
        # worker is CPU-only — pop a unique slot id, attach to the SHM ring. The
        # net forward goes over SHM; the v2.7 leaf still runs here on the worker.
        from carcassonne_ai.shm_eval_handles import connect_shm
        _worker_orch = True
        _worker_device = torch.device("cpu")
        # The worker featurizes locally (its Game must match the served net's
        # rep): a sighted 81ch net -> Game(sighted=True); a blind farm-scalar net
        # -> include_farm_scalars. Both flags + (n_ch, n_scalar) come from the
        # ckpt peek in main() so the client SHM layout matches the server.
        _worker_sighted = sighted
        _worker_include_farm = (ns > 10) and not sighted
        _worker_handles = connect_shm(shm_name, id_q.get(), ns, nch)
        return
    _worker_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(checkpoint, map_location=_worker_device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    _worker_sighted = bool(ck.get("sighted", False))
    _worker_include_farm = bool(ck.get("include_farm_scalars", (ns > 10) and not _worker_sighted))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_input_channels=int(ck.get("n_input_channels", N_CHANNELS)),
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))
                         ).to(_worker_device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    _worker_net = net


def _play_one(args) -> GameResult:
    out_str, seed, net_player, sims, heur_sims, c_puct = args
    out = Path(out_str)
    p = _result_path(out, sims, heur_sims, c_puct, seed, net_player)
    cached = _try_load(p)
    if cached is not None:
        return cached

    # Work-stealing: atomically claim this (seed, net_player) before the
    # expensive game. If another box owns it, skip (return None). The .claim
    # sits next to the eventual .json; the exists-check above is the permanent
    # done-marker. Mirrors eval_iter_head_to_head.
    if _worker_shared_claim:
        claim_path = p.with_suffix(".claim")
        if not _try_claim(claim_path, _worker_claim_host, _worker_claim_stale_secs):
            return None

    import random
    random.seed(seed)

    game = Game(enable_legal_moves_cache=True, include_farm_scalars=_worker_include_farm,
                sighted=_worker_sighted)
    board = game.get_init_board()
    dh = deck_hash(board)  # capture the deck identity BEFORE any tile is drawn

    # Neural side = PRODUCTION play config: net priors + v2.7 leaf value.
    # Orchestrator: priors/value come from the shared GPU server over SHM.
    if _worker_orch:
        base = make_remote_single_evaluator(_worker_handles, game)
    else:
        base = make_single_evaluator(_worker_net, _worker_device, game)
    # residual_scale override: None = DEFAULT_CONFIG/env; a float forces it (0.0 =
    # pure-v2.7 control, 0.25 = residual cell). dataclasses.replace keeps all other
    # v2.7 knobs (cap/drop-three-open) identical so only the value path changes.
    if _worker_residual_scale is None:
        leaf_eval = make_v25_value_wrapper(base)  # priors from net, value from v2.7
    else:
        cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=float(_worker_residual_scale))
        leaf_eval = make_v25_value_wrapper(base, cfg)
    net_mcts = NeuralMCTS(game=game, evaluator=leaf_eval, simulations=sims,
                          seed=seed, c_puct=c_puct, fpu_reduction=_worker_fpu)

    # Heuristic side = UCT + a virtual_score leaf, NO learned policy. Its own game
    # so its legal-cache doesn't poison the neural side. The leaf is `_worker_heur_leaf`:
    # "v1" (legacy default) or "v2_7" to MATCH the neural side's leaf (isolates the policy).
    heur_game = Game(enable_legal_moves_cache=True)
    heur_mcts = HeuristicMCTS(game=heur_game, simulations=heur_sims, seed=seed + 1,
                              heur_leaf=_worker_heur_leaf)

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == net_player:
            net_mcts.clear()
            action = net_mcts.best_action(board)
        else:
            heur_mcts.clear()
            action = heur_mcts.best_action(board)
        board, _ = game.get_next_state(board, action)
        moves += 1
        _bench_tick()  # no-op unless CARC_BENCH_TP set

    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if net_player == 0 else (s1 - s0)
    r = GameResult(
        seed=seed, net_player=net_player, sims=sims, heur_sims=heur_sims,
        c_puct=c_puct, score_p0=int(s0), score_p1=int(s1), diff=int(diff),
        won_by_net=(diff > 0), drew=(diff == 0), elapsed_s=elapsed, moves=moves,
        deck_hash=dh,
    )
    _save(p, r)
    return r


def _summary(results, sims, heur_sims):
    import math
    n = len(results)
    w = sum(1 for r in results if r.won_by_net)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    avg_diff = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    # elo + binomial sigma
    score = wr
    if 0 < score < 1:
        elo = 400.0 * math.log10(score / (1 - score))
        wr_sig = math.sqrt(score * (1 - score) / n)
        elo_sig = (400.0 / math.log(10)) * wr_sig / (score * (1 - score))
    else:
        elo = math.copysign(800.0, score - 0.5)
        elo_sig = float("nan")
    print()
    print(f"=== LADDER: NeuralMCTS(net, s={sims}) vs HeuristicMCTS(s={heur_sims}) ===")
    print(f"games:   {n}")
    print(f"net:     {w}W / {d}D / {losses}L   winrate {wr:.3f}")
    print(f"avg score diff (net - heuristic): {avg_diff:+.1f}")
    print(f"ELO (net vs heuristic): {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    print()
    if wr > 0.55:
        print("READ: net's LEARNED POLICY beats pure heuristic search at matched compute"
              " -> real signal raw search can't replicate.")
    elif wr < 0.45:
        print("READ: net LOSES to pure heuristic search at matched compute"
              " -> the policy is not adding strength over the leaf+search.")
    else:
        print("READ: net ~ heuristic search (within noise) -> policy adds little at this sims/scale.")


def _build_work(seed_start: int, n: int, paired: bool):
    """Yield (seed, net_player) pairs.

    Legacy (unpaired): alternate net_player across n consecutive seeds.
    Paired (G-M2 deck-pairing): play each DECK both colors — same seed with the
    net as p0 AND as p1 — so first-player advantage AND deck-draw variance both
    cancel (~halves variance vs unpaired). n must be even; n/2 distinct decks.
    """
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        seed = seed_start + i
        work.append((seed, 0))
        work.append((seed, 1))
    return work


def _load_net(checkpoint, device):
    """Load a checkpoint into a CarcassonneNet on `device`.
    Returns (net, include_farm, sighted)."""
    ck = torch.load(checkpoint, map_location=device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    sighted = bool(ck.get("sighted", False))
    include_farm = bool(ck.get("include_farm_scalars", (ns > 10) and not sighted))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_input_channels=int(ck.get("n_input_channels", N_CHANNELS)),
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))
                         ).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    return net, include_farm, sighted


def _make_matchup(net, device, game, heur_game, *, seed, sims, heur_sims, c_puct,
                  heur_leaf, residual_scale, include_farm=False, fpu_reduction=None):
    """Build the (NeuralMCTS, HeuristicMCTS, leaf_eval) triple used by both the
    Pool worker logic and the single-process provenance smoke. `leaf_eval` is the
    `_V25Wrapped` whose `.counters` the smoke reads to prove the leaf path ran."""
    base = make_single_evaluator(net, device, game)
    if residual_scale is None:
        leaf_eval = make_v25_value_wrapper(base)
    else:
        cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=float(residual_scale))
        leaf_eval = make_v25_value_wrapper(base, cfg)
    net_mcts = NeuralMCTS(game=game, evaluator=leaf_eval, simulations=sims,
                          seed=seed, c_puct=c_puct, fpu_reduction=fpu_reduction)
    heur_mcts = HeuristicMCTS(game=heur_game, simulations=heur_sims, seed=seed + 1,
                              heur_leaf=heur_leaf)
    return net_mcts, heur_mcts, leaf_eval


def _both_specs(net_mcts, heur_mcts, *, checkpoint, sims, heur_sims, paired,
                seed_range, argv):
    """Both-sides EvaluatorSpecs read from the LIVE MCTS objects (R1: record the
    actual leaf invoked, not a label)."""
    nspec = ep.spec_from_neural_mcts(
        net_mcts, side="A_net", checkpoint_path=str(checkpoint), sims=sims,
        paired=paired, seed_range=seed_range,
        eval_script="eval_net_vs_heuristic.py", argv=argv)
    hspec = ep.spec_from_heuristic_mcts(
        heur_mcts, side="B_heur", sims=heur_sims, paired=paired,
        seed_range=seed_range, eval_script="eval_net_vs_heuristic.py", argv=argv)
    return nspec, hspec


def _provenance_smoke(args, heur_sims, seed_range, out) -> int:
    """Single-process runtime proof. Plays one game per seat, reads the live
    leaf-path counters off both sides, asserts the claimed leaf/value path
    actually executed, and writes a manifest stamped runtime_verified.ok=true."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net, include_farm, sighted = _load_net(args.checkpoint, device)
    print(f"[provenance-smoke] device={device} heur_leaf={args.heur_leaf} "
          f"residual_scale={args.residual_scale} sims={args.sims}/{heur_sims} "
          f"sighted={sighted} fpu={args.fpu}")
    # Persistent objects so counters accumulate across both seats.
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm,
                sighted=sighted)
    heur_game = Game(enable_legal_moves_cache=True)
    net_mcts, heur_mcts, leaf_eval = _make_matchup(
        net, device, game, heur_game, seed=seed_range[0], sims=args.sims,
        heur_sims=heur_sims, c_puct=args.c_puct, heur_leaf=args.heur_leaf,
        residual_scale=args.residual_scale, include_farm=include_farm,
        fpu_reduction=args.fpu)
    import random
    for net_player in (0, 1):
        random.seed(seed_range[0])
        board = game.get_init_board()
        while game.get_game_ended(board, 0) == 0.0:
            cur = board.state.current_player
            if cur == net_player:
                net_mcts.clear(); action = net_mcts.best_action(board)
            else:
                heur_mcts.clear(); action = heur_mcts.best_action(board)
            board, _ = game.get_next_state(board, action)
    counters_by_side = {"A_net": leaf_eval.counters.as_dict(),
                        "B_heur": heur_mcts.counters}
    nspec, hspec = _both_specs(net_mcts, heur_mcts, checkpoint=args.checkpoint,
                               sims=args.sims, heur_sims=heur_sims, paired=args.paired,
                               seed_range=seed_range, argv=sys.argv[1:])
    verdict = ep.assert_provenance_consistent([nspec, hspec], counters_by_side)
    print("[provenance-smoke] counters:", json.dumps(counters_by_side))
    print("[provenance-smoke] OK — claimed leaf/value paths verified at runtime")
    block = ep.build_eval_provenance([nspec, hspec], kind="eval_net_vs_heuristic",
                                     argv=sys.argv[1:], runtime_verified=verdict)
    mpath = write_manifest(out, kind="eval_net_vs_heuristic", game=game_tag(Game()),
                           config={"checkpoint": str(args.checkpoint), "n": args.n,
                                   "sims": args.sims, "heur_sims": heur_sims,
                                   "c_puct": args.c_puct, "paired": args.paired,
                                   "seed_start": args.seed_start, "opponent": "HeuristicMCTS",
                                   "heur_leaf": args.heur_leaf, "new_var": "v2_7",
                                   "residual_scale": args.residual_scale,
                                   "provenance_smoke": True},
                           evaluator=block, overwrite=True)
    print(f"[provenance-smoke] manifest with runtime_verified -> {mpath}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_net_vs_heuristic")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--sims", type=int, default=200, help="NeuralMCTS sims")
    ap.add_argument("--heur-sims", type=int, default=None,
                    help="HeuristicMCTS sims (default = --sims, i.e. matched compute)")
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--fpu", type=float, default=None,
                    help="NeuralMCTS first-play-urgency reduction (q=parent.Q-fpu "
                         "for unvisited children). None (default) = legacy q=0, "
                         "byte-identical to prior evals. M2 fixed ingredient: 0.6.")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--shm-eval-server", type=str, default=None,
                    help="carc-orch SHM orchestrator mode: attach to /dev/shm/carc_<NAME> for "
                         "batched net forwards over shared memory (the server owns the net; "
                         "workers are CPU-only). Start the server first via "
                         "rust/carc-orch/run_server.sh (see scripts/eval_orch.sh). "
                         "Unset = orch-off (per-worker net, the default).")
    ap.add_argument("--seed-start", type=int, default=ep.EVAL_SEED_FLOOR,
                    help="first deck seed. Defaults to the clean-eval floor (1e9) so decks "
                         "never overlap the self-play namespace (outside-review A9). A value "
                         "below the floor is rejected unless --allow-selfplay-seeds.")
    ap.add_argument("--residual-scale", type=float, default=None,
                    help="override the leaf wrapper's residual_scale (None=use DEFAULT_CONFIG/env). "
                         "0.0 = pure-v2.7 control; e.g. 0.25 = residual cell (Phase-3 #4/#5). "
                         "All other v2.7 knobs (cap/drop-three-open) stay identical.")
    ap.add_argument("--allow-selfplay-seeds", action="store_true",
                    help="bypass the clean-eval seed-floor guard (only to intentionally "
                         "reproduce an OLD run's deck namespace; taints train/test separation).")
    ap.add_argument("--provenance-smoke", action="store_true",
                    help="single-process runtime proof: play 1-2 games, read the live leaf-path "
                         "counters, assert the CLAIMED leaf/value path actually executed "
                         "(assert_provenance_consistent), stamp runtime_verified into the manifest, "
                         "and exit. Run this BEFORE the real Pool eval (R1/R7 guard).")
    ap.add_argument("--out-subdir", type=str, default=None,
                    help="subdir under the out-root (default: derived from ckpt name)")
    ap.add_argument("--out-root", type=str, default=None,
                    help="root dir for results (default: REPO/data/ladder). Point at the "
                         "CIFS share + use --shared-claim to work-steal across boxes "
                         "(all boxes pass the SAME --seed-start/--n).")
    ap.add_argument("--paired", action="store_true",
                    help="deck-pairing (G-M2): play each deck both colors so first-player "
                         "advantage + deck variance cancel (~halves variance). n must be even.")
    ap.add_argument("--shared-claim", action="store_true",
                    help="work-stealing across boxes: atomically claim each (seed,player) via "
                         "an O_CREAT|O_EXCL .claim sidecar so idle boxes pull the tail instead "
                         "of sitting idle. All boxes use the SAME --seed-start/--n/--out-root.")
    ap.add_argument("--claim-stale-secs", type=int, default=5400,
                    help="a .claim older than this is re-claimable (default 90 min).")
    ap.add_argument("--claim-host", type=str, default=socket.gethostname(),
                    help="identity written into the claim body (host:pid:ts).")
    ap.add_argument("--heur-leaf", choices=["v1", "v2_7"], default="v1",
                    help="leaf the HeuristicMCTS opponent uses. 'v1' (default) = legacy "
                         "base virtual_score (keeps prior ladder numbers comparable). "
                         "'v2_7' = match the agent's leaf so the eval isolates the learned "
                         "policy instead of confounding it with the v2.7-vs-v1 leaf gap (R1).")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n (n/2 decks x 2 colors)")

    heur_sims = args.heur_sims if args.heur_sims is not None else args.sims
    seed_range = [args.seed_start, args.seed_start + (args.n // 2 if args.paired else args.n)]

    # Clean-eval seed-floor guard (A9): a serious eval must draw decks from above
    # the self-play namespace so it can never replay a trained-on deck. Hard error
    # unless the user explicitly opts into the old namespace.
    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    # Include heur_leaf in the default subdir so a v2_7 run never collides with / resumes
    # from a cached v1 run at the same ckpt/sims/c (they are different opponents).
    _hl_tag = "" if args.heur_leaf == "v1" else f"_heur{args.heur_leaf}"
    _rs_tag = "" if args.residual_scale is None else f"_rs{str(args.residual_scale).replace('.', '')}"
    sub = args.out_subdir or f"{args.checkpoint.stem}_s{args.sims}_h{heur_sims}_c{str(args.c_puct).replace('.', '')}{_hl_tag}{_rs_tag}"
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    # Runtime provenance proof (single process) — verify the claimed leaf/value
    # path actually executes, then exit. Run BEFORE the real Pool eval.
    if args.provenance_smoke:
        return _provenance_smoke(args, heur_sims, seed_range, out)

    # self-describing run manifest (provenance: game/code_rev/leaf-env + the
    # both-sides evaluator block read off live MCTS objects) — D21 + R1/R7.
    if not args.summary_only:
        device_cpu = torch.device("cpu")  # CPU keeps the parent CUDA-clean before fork
        _net, _farm, _sighted = _load_net(args.checkpoint, device_cpu)
        _g, _hg = (Game(enable_legal_moves_cache=True, include_farm_scalars=_farm,
                        sighted=_sighted),
                   Game(enable_legal_moves_cache=True))
        _nm, _hm, _ = _make_matchup(_net, device_cpu, _g, _hg, seed=args.seed_start,
                                    sims=args.sims, heur_sims=heur_sims, c_puct=args.c_puct,
                                    heur_leaf=args.heur_leaf, residual_scale=args.residual_scale,
                                    fpu_reduction=args.fpu)
        _nspec, _hspec = _both_specs(_nm, _hm, checkpoint=args.checkpoint, sims=args.sims,
                                     heur_sims=heur_sims, paired=args.paired,
                                     seed_range=seed_range, argv=sys.argv[1:])
        _block = ep.build_eval_provenance([_nspec, _hspec], kind="eval_net_vs_heuristic",
                                          argv=sys.argv[1:], runtime_verified=None)
        del _net, _nm, _hm  # free before the Pool fork
        write_manifest(out, kind="eval_net_vs_heuristic", game=game_tag(Game()),
                       config={"checkpoint": str(args.checkpoint), "n": args.n,
                               "sims": args.sims, "heur_sims": heur_sims,
                               "c_puct": args.c_puct, "paired": args.paired,
                               "seed_start": args.seed_start, "opponent": "HeuristicMCTS",
                               "heur_leaf": args.heur_leaf, "new_var": "v2_7",
                               "residual_scale": args.residual_scale},
                       evaluator=_block)

    # color balance via _build_work (paired = each deck both colors)
    tasks = [(str(out), seed, net_player, args.sims, heur_sims, args.c_puct)
             for seed, net_player in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, args.sims, heur_sims, args.c_puct, t[1], t[2]))) is not None]
        if results:
            _summary(results, args.sims, heur_sims)
        else:
            print("no cached results yet")
        return 0

    todo = [t for t in tasks if not _result_path(out, args.sims, heur_sims, args.c_puct, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"net-vs-heuristic: ckpt={args.checkpoint.name} n={args.n} sims={args.sims} "
          f"heur_sims={heur_sims} c={args.c_puct} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        _ck = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
        ns = int(_ck.get("n_scalar_features", 10))
        _nch = int(_ck.get("n_input_channels", N_CHANNELS))
        _sighted = bool(_ck.get("sighted", False))
        del _ck
        if args.shm_eval_server:
            # Orchestrator: spawn context (matches run_selfplay_iter) so the
            # worker-id Queue passes cleanly + workers re-import CUDA-clean.
            _ctx = mp.get_context("spawn")
            _id_q = _ctx.Queue()
            for _w in range(workers):
                _id_q.put(_w)
            print(f"  [orch] SHM eval-server '{args.shm_eval_server}': {workers} CPU "
                  f"workers attach to /dev/shm/carc_{args.shm_eval_server}")
            sys.stdout.flush()
            _pool_cm = _ctx.Pool(processes=workers, initializer=_worker_init,
                                 initargs=(str(args.checkpoint), args.shared_claim,
                                           args.claim_host, args.claim_stale_secs,
                                           args.heur_leaf, args.residual_scale,
                                           args.shm_eval_server, _id_q, ns, args.fpu,
                                           _nch, _sighted))
        else:
            _pool_cm = Pool(processes=workers, initializer=_worker_init,
                            initargs=(str(args.checkpoint), args.shared_claim,
                                      args.claim_host, args.claim_stale_secs,
                                      args.heur_leaf, args.residual_scale,
                                      "", None, ns, args.fpu, _nch, _sighted))
        with _pool_cm as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    # work-steal skip: another box owns this (seed,player).
                    continue
                results.append(r)
                done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, "
                          f"~{(len(todo)-done)*el/done/60:.0f} min left)")
                    sys.stdout.flush()
    # add cached
    for t in tasks:
        p = _result_path(out, args.sims, heur_sims, args.c_puct, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.net_player == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    _summary(results, args.sims, heur_sims)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
