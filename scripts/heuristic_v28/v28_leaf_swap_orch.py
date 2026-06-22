"""Phase 7 (gate) — iter8 leaf-swap via the carc-orch SHM orchestrator.

PRIMARY matchup (Joshua's spec 2026-06-22):
  A = ITER8_PROD_WITH_V28_MEEPLE_K2_LEAF : NeuralMCTS@sims, net priors + leaf value
      tanh(virtual_score_v2(.., meeple_k=2)/15) + 0.25*v_nn
  B = ITER8_PROD_WITH_V27_LEAF           : same net, same residual 0.25, leaf = v2.7
ONLY the leaf base changes. Same checkpoint / sims / c_puct / residual 0.25 / seeds / band /
both seats. The net forward (priors+value) is served by the shared GPU SHM server; the v2.7(/+meeple)
leaf + residual run on the CPU worker — both sides query the SAME net, so the eval isolates the leaf.

NB: meeple_k is the LEGACY LeafConfig field -> _v28_active is False -> the leaf runs on the FLAT
(production) path, full speed, on the orchestrator. Residual head is v2.7-trained; keeping it (0.25)
on both sides is the PRODUCTION-REALISTIC drop-in test (Joshua's call), not a pure-leaf isolation.

Measurement only. Champion + production + PRODUCTION.yaml UNCHANGED. v2.7 frozen.

Requires the carc-orch SHM server already running (launch via scripts/heuristic_v28/v28_leaf_swap_orch.sh).
"""
from __future__ import annotations
import argparse, dataclasses, json, math, os, socket, sys, time
from dataclasses import asdict, dataclass
from pathlib import Path
import multiprocessing as mp

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "heuristic_v28"))
import v28_configs; v28_configs.set_prod_env()
from carcassonne_ai.claim import try_claim as _try_claim          # noqa: E402
from carcassonne_ai.game_wrapper import Game                       # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS                         # noqa: E402
from carcassonne_ai.evaluators import make_v25_value_wrapper       # noqa: E402
from carcassonne_ai.remote_evaluators import make_remote_single_evaluator  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG         # noqa: E402

_W: dict = {}


@dataclass
class GameResult:
    seed: int
    a_player: int
    sims: int
    c_puct: float
    score_p0: int
    score_p1: int
    diff: int            # v2.8-leaf(A) - v2.7-leaf(B)
    won_by_a: bool
    drew: bool
    elapsed_s: float
    moves: int


def _result_path(out, sims, c, seed, a_player):
    return out / f"s{sims:04d}_c{str(c).replace('.','')}_seed{seed:09d}_a{a_player}.json"


def _try_load(p):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p, r):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    json.dump(asdict(r), open(tmp, "w")); tmp.replace(p)


def _worker_init(shm_name, id_q, ns, residual_scale, meeple_k, shared_claim, claim_host, claim_stale):
    from carcassonne_ai.shm_eval_handles import connect_shm
    _W["handles"] = connect_shm(shm_name, id_q.get(), ns)
    _W["ns"] = ns
    _W["include_farm"] = ns > 10
    _W["rs"] = residual_scale
    _W["mk"] = meeple_k
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["claim_stale"] = claim_stale


def _play_one(args):
    out_str, seed, a_player, sims, c_puct = args
    out = Path(out_str)
    p = _result_path(out, sims, c_puct, seed, a_player)
    c = _try_load(p)
    if c is not None:
        return c
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None
    import random
    random.seed(seed)
    # separate games so the two trees' legal caches don't mix; one shared SHM handle (sequential).
    ga = Game(enable_legal_moves_cache=True, include_farm_scalars=_W["include_farm"])
    gb = Game(enable_legal_moves_cache=True, include_farm_scalars=_W["include_farm"])
    base_a = make_remote_single_evaluator(_W["handles"], ga)
    base_b = make_remote_single_evaluator(_W["handles"], gb)
    cfg_a = dataclasses.replace(DEFAULT_CONFIG, residual_scale=_W["rs"], meeple_k=_W["mk"])  # v2.8
    cfg_b = dataclasses.replace(DEFAULT_CONFIG, residual_scale=_W["rs"])                     # v2.7
    leaf_a = make_v25_value_wrapper(base_a, cfg_a)
    leaf_b = make_v25_value_wrapper(base_b, cfg_b)
    mcts_a = NeuralMCTS(game=ga, evaluator=leaf_a, simulations=sims, seed=seed, c_puct=c_puct)
    mcts_b = NeuralMCTS(game=gb, evaluator=leaf_b, simulations=sims, seed=seed + 1, c_puct=c_puct)
    board = ga.get_init_board()
    t0 = time.perf_counter(); moves = 0
    while ga.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mcts = mcts_a if cur == a_player else mcts_b
        mcts.clear()
        board, _ = ga.get_next_state(board, mcts.best_action(board))
        moves += 1
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_player == 0 else (s1 - s0)
    r = GameResult(seed=seed, a_player=a_player, sims=sims, c_puct=c_puct,
                   score_p0=int(s0), score_p1=int(s1), diff=int(diff),
                   won_by_a=(diff > 0), drew=(diff == 0),
                   elapsed_s=time.perf_counter() - t0, moves=moves)
    _save(p, r)
    return r


def _summary(results, sims, label):
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
    print(f"\n=== {label}, NeuralMCTS@{sims}, n={n} ===")
    print(f"A(v2.8 leaf): {w}W/{d}D/{losses}L  wr {wr:.3f}  avg diff {avg:+.2f}  z_margin {z:+.2f}  ELO {elo:+.1f} (+/-{es:.1f})")
    sig = "VERDICT-RANGE" if (not math.isnan(es) and abs(elo) > 2 * es) else "INCONCLUSIVE"
    print(f"signal: {sig}")
    return {"label": label, "sims": sims, "n": n, "W": w, "D": d, "L": losses, "winrate": round(wr, 4),
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
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--shm-eval-server", required=True, help="carc-orch SHM name (server must be running)")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--residual-scale", type=float, default=0.25)
    ap.add_argument("--meeple-k", type=float, default=2.0)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--seed-start", type=int, default=1_906_220_000)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--out-subdir", default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=5400)
    ap.add_argument("--claim-host", default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2:
        ap.error("--paired requires even --n")

    import torch
    ns = int(torch.load(args.checkpoint, map_location="cpu", weights_only=False).get("n_scalar_features", 10))
    sub = args.out_subdir or f"iter8leaf_meeplek{str(args.meeple_k).replace('.','')}_vs_v27_s{args.sims}_rs{str(args.residual_scale).replace('.','')}"
    out = Path(args.out_root) / sub
    out.mkdir(parents=True, exist_ok=True)
    json.dump({"kind": "iter8_leaf_swap_orch", "checkpoint": args.checkpoint, "shm": args.shm_eval_server,
               "sims": args.sims, "c_puct": args.c_puct, "residual_scale": args.residual_scale,
               "meeple_k": args.meeple_k, "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
               "A": "net+v2.7+meeple_k%g leaf, resid %g" % (args.meeple_k, args.residual_scale),
               "B": "net+v2.7 leaf, resid %g" % args.residual_scale,
               "base_env": v28_configs.PROD_ENV}, open(out / "manifest.json", "w"), indent=2)

    tasks = [(str(out), s, ap_, args.sims, args.c_puct) for s, ap_ in _build_work(args.seed_start, args.n, args.paired)]
    label = f"A=net+v2.7+meeple_k{args.meeple_k} (resid {args.residual_scale}) vs B=net+v2.7 (resid {args.residual_scale})"
    if args.summary_only:
        res = [r for t in tasks if (r := _try_load(_result_path(out, args.sims, args.c_puct, t[1], t[2]))) is not None]
        if res:
            json.dump(_summary(res, args.sims, label), open(out / "result.json", "w"), indent=2)
        else:
            print("no cached results")
        return 0

    todo = [t for t in tasks if not _result_path(out, args.sims, args.c_puct, t[1], t[2]).exists()]
    print(f"[leaf-swap-orch] ckpt={Path(args.checkpoint).name} n={args.n} sims={args.sims} c={args.c_puct} "
          f"resid={args.residual_scale} meeple_k={args.meeple_k} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, W={args.workers}, shm={args.shm_eval_server}, out={out}", flush=True)
    sys.stdout.flush()
    results = []
    if todo:
        ctx = mp.get_context("spawn")
        id_q = ctx.Queue()
        for w in range(args.workers):
            id_q.put(w)
        t0 = time.perf_counter()
        with ctx.Pool(processes=args.workers, initializer=_worker_init,
                      initargs=(args.shm_eval_server, id_q, ns, args.residual_scale, args.meeple_k,
                                args.shared_claim, args.claim_host, args.claim_stale_secs)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r); done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} ({el/done:.1f}s/game, ~{(len(todo)-done)*el/done/60:.0f} min left)", flush=True)
    for t in tasks:
        p = _result_path(out, args.sims, args.c_puct, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_player == t[2] for r in results):
            cc = _try_load(p)
            if cc:
                results.append(cc)
    if results:
        json.dump(_summary(results, args.sims, label), open(out / "result.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
