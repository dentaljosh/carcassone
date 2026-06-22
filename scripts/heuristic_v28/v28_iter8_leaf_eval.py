"""Phase 7 — iter8 leaf-swap eval: NeuralMCTS(net priors) + v2.8 leaf vs + v2.7 leaf.

OPT-IN MEASUREMENT WRAPPER ONLY — does NOT change production. Both sides use the iter8 net
policy prior and NeuralMCTS@sims c_puct=3.0; they differ ONLY in the leaf VALUE config:
  side A = make_v25_value_wrapper(net, <v2.8 cfg, residual_scale=0>)
  side B = make_v25_value_wrapper(net, <v2.7 cfg, residual_scale=0>)
Residual is forced 0 on BOTH: the production residual head was TRAINED against the v2.7 base
(Δ = Q − tanh(vs2.7/15)); adding it on top of a v2.8 base is semantically broken, so the clean
leaf-isolating comparison uses the PURE leaf value under the same net policy. Deck-paired,
balanced seats, resumable. Net on CPU (throughput scales with workers).

Usage:
  python -u scripts/heuristic_v28/v28_iter8_leaf_eval.py --variant v28_completion --n 200 \
      --sims 200 --paired --workers 14 --out-root /mnt/c/carc-shared/v28_pilot
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
import dataclasses as dc
from dataclasses import asdict, dataclass
from multiprocessing import get_context
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")   # net on CPU; scale with workers
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "heuristic_v28"))
import v28_configs; v28_configs.set_prod_env()
from carcassonne_ai.game_wrapper import Game           # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS              # noqa: E402

CKPT = os.environ.get("V28_CKPT", "/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt")
_W: dict = {}


@dataclass
class GameResult:
    seed: int
    a_player: int
    sims: int
    score_p0: int
    score_p1: int
    diff: int            # v2.8-leaf(A) - v2.7-leaf(B)
    won_by_a: bool
    drew: bool
    elapsed_s: float
    moves: int


def _result_path(out, sims, seed, a_player):
    return out / f"s{sims:04d}_seed{seed:09d}_a{a_player}.json"


def _try_load(p):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p, r):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.stem + ".partial.json"); json.dump(asdict(r), open(tmp, "w")); tmp.replace(p)


def _worker_init(variant_name, ckpt):
    import torch
    torch.set_num_threads(1)
    from carcassonne_ai.network import CarcassonneNet
    from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
    dev = torch.device("cpu")
    ck = torch.load(ckpt, map_location=dev, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"], n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
    net.load_state_dict(ck["model_state"]); net.train(False)
    game_farm = Game(enable_legal_moves_cache=True, include_farm_scalars=(ns > 10))
    base = make_single_evaluator(net, dev, game_farm)
    variants = v28_configs.build_variants([variant_name, "v27_baseline"])
    # force residual 0 on both — isolate the PURE leaf value
    cfg_v28 = dc.replace(variants[variant_name], residual_scale=0.0)
    cfg_v27 = dc.replace(variants["v27_baseline"], residual_scale=0.0)
    _W["ns"] = ns
    _W["leaf_v28"] = make_v25_value_wrapper(base, cfg_v28)
    _W["leaf_v27"] = make_v25_value_wrapper(base, cfg_v27)


def _play_one(args):
    out_str, seed, a_player, sims = args
    out = Path(out_str); p = _result_path(out, sims, seed, a_player)
    c = _try_load(p)
    if c is not None:
        return c
    import random
    random.seed(seed)
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=(_W["ns"] > 10))
    a = NeuralMCTS(game=g, evaluator=_W["leaf_v28"], simulations=sims, seed=seed, c_puct=3.0)
    b = NeuralMCTS(game=g, evaluator=_W["leaf_v27"], simulations=sims, seed=seed + 1, c_puct=3.0)
    board = g.get_init_board()
    t0 = time.perf_counter(); moves = 0
    while g.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mcts = a if cur == a_player else b
        mcts.clear()
        board, _ = g.get_next_state(board, mcts.best_action(board))
        moves += 1
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_player == 0 else (s1 - s0)
    r = GameResult(seed=seed, a_player=a_player, sims=sims, score_p0=int(s0), score_p1=int(s1),
                   diff=int(diff), won_by_a=(diff > 0), drew=(diff == 0),
                   elapsed_s=time.perf_counter() - t0, moves=moves)
    _save(p, r)
    return r


def _summary(results, sims, variant):
    n = len(results); w = sum(r.won_by_a for r in results); d = sum(r.drew for r in results)
    losses = n - w - d; avg = sum(r.diff for r in results) / n; wr = (w + 0.5 * d) / n
    diffs = [r.diff for r in results]; mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var); z = (mean / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        es = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, es = math.copysign(800.0, wr - 0.5), float("nan")
    print(f"\n=== iter8 net + {variant} leaf (A) vs iter8 net + v2.7 leaf (B), NeuralMCTS@{sims}, n={n} ===")
    print(f"A: {w}W/{d}D/{losses}L  wr {wr:.3f}  avg diff {avg:+.2f}  z_margin {z:+.2f}  ELO {elo:+.1f} (+/-{es:.1f})")
    sig = "VERDICT-RANGE" if (not math.isnan(es) and abs(elo) > 2 * es) else "INCONCLUSIVE"
    print(f"signal: {sig}")
    return {"variant": variant, "sims": sims, "n": n, "W": w, "D": d, "L": losses, "winrate": round(wr, 4),
            "avg_diff": round(avg, 3), "z_margin": round(z, 3), "elo": round(elo, 1),
            "elo_1sig": (round(es, 1) if not math.isnan(es) else None), "signal": sig}


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0)); work.append((seed_start + i, 1))
    return work


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed-start", type=int, default=1_906_220_000)
    ap.add_argument("--out-root", type=str, default=str(REPO / "data" / "v28_pilot"))
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2:
        ap.error("--paired requires even --n")

    out = Path(args.out_root) / f"iter8leaf_{args.variant}_vs_v27_s{args.sims}"
    out.mkdir(parents=True, exist_ok=True)
    spec = v28_configs.load_spec()["variants"][args.variant]
    json.dump({"variant": args.variant, "patch": spec["patch"], "kind": "iter8_leaf_swap",
               "residual_scale": 0.0, "ckpt": args.ckpt, "sims": args.sims, "n": args.n,
               "paired": args.paired, "seed_start": args.seed_start},
              open(out / "manifest.json", "w"), indent=2)

    tasks = [(str(out), s, ap_, args.sims) for s, ap_ in _build_work(args.seed_start, args.n, args.paired)]
    if args.summary_only:
        res = [r for t in tasks if (r := _try_load(_result_path(out, args.sims, t[1], t[2]))) is not None]
        if res:
            json.dump(_summary(res, args.sims, args.variant), open(out / "result.json", "w"), indent=2)
        else:
            print("no cached results")
        return 0

    todo = [t for t in tasks if not _result_path(out, args.sims, t[1], t[2]).exists()]
    print(f"iter8 leaf-swap: {args.variant} vs v2.7, n={args.n} sims={args.sims} | "
          f"{len(tasks)-len(todo)} cached, {len(todo)} to play, W={args.workers}", flush=True)
    ctx = get_context("fork")
    results = []
    if todo:
        t0 = time.perf_counter()
        with ctx.Pool(args.workers, initializer=_worker_init, initargs=(args.variant, args.ckpt)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                results.append(r); done += 1
                if done % 20 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} ({el/done:.1f}s/game, ~{(len(todo)-done)*el/done/60:.1f} min left)", flush=True)
    for t in tasks:
        p = _result_path(out, args.sims, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_player == t[2] for r in results):
            cc = _try_load(p)
            if cc:
                results.append(cc)
    if results:
        json.dump(_summary(results, args.sims, args.variant), open(out / "result.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
