"""bench_fair_batch.py — ms/move vs batch_size for the FAIR NET-PRIOR agent.

THE QUESTION: the distilled fair net-prior candidate beat the fair champion by
+88.7 elo at equal SIMS, but ran 12.67x SLOWER per move (57138 vs 4509 ms/move),
which kills the result at equal WALL-CLOCK. Root cause: FairHeuristicPriorAgent's
per-determinization NeuralMCTS ran batch_size=1, so each of the k_dets*sims node
expansions fired ONE forward and waited a full IPC+GPU round-trip, SERIALIZED —
GPU at ~15% util. carc-orch batches ACROSS games (throughput), never WITHIN a
search. This bench measures the within-search batching fix.

WHAT IT MEASURES: mean ms/move for `--info fair-netprior` at production knobs
(k_dets x sims, sighted net via carc-orch) across `--batch-sizes`, on a FIXED set
of mid-game positions (the same positions for every batch size, so the curve is a
clean single-variable sweep). Optionally also times the heuristic-priors CHAMPION
on the same positions as the reference (`--champion`).

⚠️ NOT AN EVAL. This plays no games and produces no strength claim — it times
`choose_action` on fixed positions. Virtual-loss batching CHANGES the search, so
the bench also reports policy-sanity diagnostics (pooled support size, top-action
agreement vs the batch_size=1 baseline) to show the batched search didn't collapse
— NOT that it is bit-identical (it isn't, by construction).

⚠️ MAX_K=8: the SHM wire protocol caps ONE request at 8 boards
(shm_eval_handles.MAX_K / rust shm.rs::MAX_K, compile-time on both sides). The
batch evaluator chunks above that, so batch_size>8 is ceil(N/8) SEQUENTIAL
round-trips — correct, but no extra transport win. Expect the curve to flatten
after 8 unless MAX_K is raised (needs a rust rebuild).
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

from carcassonne_ai.fair_agent import FairHeuristicPriorAgent
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.heuristic_prior_mcts import (
    HeuristicPriorConfig,
    make_fair_net_prior_batch_evaluator,
    make_fair_net_prior_evaluator,
)

CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)


# --------------------------------------------------------------------------- #
# CONCURRENCY worker (multi-agent throughput — where server --max-batch bites). #
# A SINGLE agent never fills the server's aggregate batch (it fires <=MAX_K=8   #
# boards/request, serially), so max-batch 16 vs 64 is invisible to it. In       #
# PRODUCTION many workers search CONCURRENTLY and the server aggregates their    #
# requests up to --max-batch — that is the axis the coordinator's "avg_batch     #
# 13-14/16 saturating" observation lives on. This worker runs ONE fair-netprior  #
# agent for `moves` decisions and reports its wall time; the parent runs W of    #
# them at once through one orch server and sums throughput.                       #
# --------------------------------------------------------------------------- #
def _concurrency_worker(wargs):
    (wid, shm_name, sims, k_dets, batch_size, moves, plies, seed0) = wargs
    # spawn context: re-import + rebuild everything inside the child.
    import time as _time

    from carcassonne_ai.fair_agent import FairHeuristicPriorAgent as _Agent
    from carcassonne_ai.game_wrapper import Game as _Game
    from carcassonne_ai.heuristic_prior_mcts import (
        HeuristicPriorConfig as _Cfg,
    )
    from carcassonne_ai.heuristic_prior_mcts import (
        make_fair_net_prior_batch_evaluator as _mkbatch,
    )
    from carcassonne_ai.heuristic_prior_mcts import (
        make_fair_net_prior_evaluator as _mksingle,
    )
    from carcassonne_ai.shm_eval_handles import connect_shm as _connect

    cfg = _Cfg(c_puct=1.5, tau_p=5.0, leaf_quantize="float", final_select="visits")
    sg = _Game(sighted=True)
    handles = _connect(shm_name, wid, sg.get_scalar_feature_size(),
                       sg.get_input_channels())
    single = _mksingle(cfg, handles=handles, sighted_game=sg)
    batch = _mkbatch(cfg, handles=handles, sighted_game=sg) if batch_size > 1 else None

    # each worker its OWN distinct positions (realistic: workers aren't in lockstep).
    positions = build_positions(moves, plies, seed0=seed0 + wid * 97)
    n_done = 0
    t0 = _time.perf_counter()
    for i, (game, board) in enumerate(positions):
        agent = _Agent(_Game(enable_legal_moves_cache=True), cfg, sims=sims,
                       k_dets=k_dets, seed=9000 + wid * 31 + i, exact_endgame=False,
                       evaluator=single, batch_evaluator=batch, batch_size=batch_size)
        act = agent.choose_action(board)
        assert game.get_valid_moves(board)[act]
        n_done += 1
    dt = _time.perf_counter() - t0
    return {"wid": wid, "moves": n_done, "elapsed_s": dt,
            "ms_per_move": dt / max(1, n_done) * 1000.0}


# --------------------------------------------------------------------------- #
# GPU sampling (util is a BUSY FLAG, not load — power.draw is the real signal)  #
# --------------------------------------------------------------------------- #
class GpuSampler:
    def __init__(self, period_s: float = 0.5):
        self.period_s = period_s
        self._stop = threading.Event()
        self._rows: list[tuple[float, float]] = []
        self._t: threading.Thread | None = None

    def _poll(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu,power.draw",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5)
                line = out.stdout.strip().splitlines()[0]
                u, p = (x.strip() for x in line.split(","))
                self._rows.append((float(u), float(p)))
            except Exception:
                pass
            self._stop.wait(self.period_s)

    def __enter__(self):
        self._rows = []
        self._stop.clear()
        self._t = threading.Thread(target=self._poll, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t:
            self._t.join(timeout=3)

    def summary(self) -> dict:
        if not self._rows:
            return {"util_pct_mean": None, "power_w_mean": None, "n_samples": 0}
        us = [r[0] for r in self._rows]
        ps = [r[1] for r in self._rows]
        return {
            "util_pct_mean": round(statistics.fmean(us), 1),
            "util_pct_max": round(max(us), 1),
            "power_w_mean": round(statistics.fmean(ps), 1),
            "power_w_max": round(max(ps), 1),
            "n_samples": len(self._rows),
        }


# --------------------------------------------------------------------------- #
# Fixed positions — deterministic random playouts (the test_fair_agent idiom)   #
# --------------------------------------------------------------------------- #
def midgame_position(seed: int, plies: int):
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    rng = random.Random(seed ^ 0xA5A5)
    for _ in range(plies):
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(rng.choice(legal)))
    if game.get_game_ended(b, 0) != 0.0:
        raise RuntimeError(f"position seed={seed} plies={plies} ended early")
    return game, b


def _multi_legal(game, board, minimum=4) -> bool:
    return int(game.get_valid_moves(board).sum()) >= minimum


def build_positions(n: int, plies: int, seed0: int = 1000):
    out = []
    s = seed0
    while len(out) < n:
        try:
            game, b = midgame_position(s, plies)
            if _multi_legal(game, b):
                out.append((game, b))
        except RuntimeError:
            pass
        s += 1
        if s > seed0 + 500:
            raise RuntimeError("could not build enough positions")
    return out


# --------------------------------------------------------------------------- #
# One timed sweep point                                                        #
# --------------------------------------------------------------------------- #
def time_agent(make_agent, positions, label: str) -> dict:
    """Time choose_action on each position with a FRESH agent (so no tree/state
    carries across positions). Returns per-move ms + the pooled-policy diagnostics."""
    per_move_ms = []
    picks = []
    supports = []
    with GpuSampler() as gpu:
        for i, (game, board) in enumerate(positions):
            agent = make_agent(seed=4242 + i)
            t0 = time.perf_counter()
            act = agent.choose_action(board)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            assert game.get_valid_moves(board)[act], f"{label}: illegal action {act}"
            per_move_ms.append(dt_ms)
            picks.append(int(act))
            pv = agent.last_pooled_visits or {}
            supports.append(len(pv))
            # policy sanity: every pooled action legal + positively visited
            mask = game.get_valid_moves(board)
            assert all(mask[a] for a in pv), f"{label}: pooled visits contain illegal action"
            assert all(v > 0 for v in pv.values()), f"{label}: non-positive pooled visit"
            print(f"    [{label}] pos{i}: {dt_ms:9.1f} ms  pick={act:5d}  support={len(pv):3d}",
                  flush=True)
    return {
        "label": label,
        "ms_per_move_mean": round(statistics.fmean(per_move_ms), 1),
        "ms_per_move_median": round(statistics.median(per_move_ms), 1),
        "ms_per_move_min": round(min(per_move_ms), 1),
        "ms_per_move_max": round(max(per_move_ms), 1),
        "per_move_ms": [round(x, 1) for x in per_move_ms],
        "picks": picks,
        "support_mean": round(statistics.fmean(supports), 1),
        "gpu": gpu.summary(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--orch-shm-name", type=str, default=None,
                    help="carc-orch SHM name (the production transport). Omit for a CPU net.")
    ap.add_argument("--net", type=str, default=None,
                    help="checkpoint .pt for the CPU-net path (ignored when --orch-shm-name)")
    ap.add_argument("--batch-sizes", type=str, default="1,8,16,32")
    ap.add_argument("--sims", type=int, default=688, help="PUCT sims per determinization")
    ap.add_argument("--k-dets", type=int, default=4, help="determinizations per move")
    ap.add_argument("--moves", type=int, default=3, help="positions timed per batch size")
    ap.add_argument("--plies", type=int, default=40, help="random plies to build a position")
    ap.add_argument("--champion", action="store_true",
                    help="also time the heuristic-priors fair champion (the reference)")
    ap.add_argument("--rtt-probe", action="store_true",
                    help="instead of the agent sweep, measure raw orch ROUND-TRIP time "
                         "vs k (boards/request). Answers whether the residual per-leaf "
                         "cost is latency (flat in k -> raising MAX_K amortizes it) or "
                         "GPU compute (grows with k -> raising MAX_K buys nothing).")
    ap.add_argument("--concurrency", type=int, default=0,
                    help="instead of the single-agent sweep, run THIS many fair-netprior "
                         "agents CONCURRENTLY against the orch and report aggregate "
                         "throughput. This is where server --max-batch bites (a single "
                         "agent never fills the aggregate batch). Requires --orch-shm-name; "
                         "the server must be started with --workers >= concurrency.")
    ap.add_argument("--out", type=str, default=None, help="write results JSON here")
    args = ap.parse_args()

    batch_sizes = [int(x) for x in args.batch_sizes.split(",") if x.strip()]

    # --- resolve + VERIFY the leaf (curve125, the champion's frozen leaf). A silent
    #     curve100 would make every number here describe the wrong agent.
    cfg = HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, leaf_quantize="float",
                               final_select="visits")
    leaf = cfg.resolved_leaf_cfg()
    curve = tuple(float(x) for x in (leaf.v29_meeple_curve or ()))
    if curve != CURVE125:
        raise SystemExit(
            f"FATAL: resolved leaf curve {curve} != curve125 {CURVE125}. "
            "Source scripts/distill_flywheel/champ_env.sh before running.")
    print(f"[bench] leaf OK: curve125, bonus_cap={leaf.bonus_cap}, "
          f"opp_bonus_cap={leaf.opp_bonus_cap}", flush=True)

    # --- CONCURRENCY throughput mode (multi-agent; where server --max-batch bites) ---
    # The parent does NOT connect handles here (each spawned child owns its own worker
    # slot 0..W-1); it only launches the children and samples the GPU centrally.
    if args.concurrency > 0:
        if not args.orch_shm_name:
            raise SystemExit("--concurrency needs --orch-shm-name (the shared orch server)")
        import multiprocessing as mp
        bs_list = [int(x) for x in args.batch_sizes.split(",") if x.strip()]
        W = args.concurrency
        ctx = mp.get_context("spawn")
        results = {"mode": "concurrency", "concurrency": W,
                   "knobs": {"sims": args.sims, "k_dets": args.k_dets,
                             "budget": args.sims * args.k_dets, "moves": args.moves},
                   "points": []}
        print(f"[bench] CONCURRENCY throughput: {W} agents x {args.moves} moves each, "
              f"knobs k_dets={args.k_dets} x sims={args.sims}", flush=True)
        for bs in bs_list:
            wargs = [(wid, args.orch_shm_name, args.sims, args.k_dets, bs,
                      args.moves, args.plies, 2000) for wid in range(W)]
            with GpuSampler() as gpu:
                t0 = time.perf_counter()
                with ctx.Pool(processes=W) as pool:
                    rows = pool.map(_concurrency_worker, wargs)
                wall = time.perf_counter() - t0
            total_moves = sum(r["moves"] for r in rows)
            agg_mps = total_moves / wall                       # moves/sec across all agents
            per_agent_ms = statistics.fmean([r["ms_per_move"] for r in rows])
            pt = {"batch_size": bs, "wall_s": round(wall, 2),
                  "total_moves": total_moves,
                  "throughput_moves_per_s": round(agg_mps, 3),
                  "per_agent_ms_per_move": round(per_agent_ms, 1),
                  "effective_ms_per_move": round(wall / total_moves * 1000.0, 1),
                  "gpu": gpu.summary()}
            results["points"].append(pt)
            print(f"[bench] bs={bs:2d}: {agg_mps:6.3f} moves/s aggregate | "
                  f"per-agent {per_agent_ms:8.1f} ms/move | "
                  f"effective {pt['effective_ms_per_move']:8.1f} ms/move | "
                  f"GPU {pt['gpu']['util_pct_mean']}% / {pt['gpu']['power_w_mean']}W",
                  flush=True)
        if args.out:
            Path(args.out).write_text(json.dumps(results, indent=2))
            print(f"[bench] wrote {args.out}")
        return

    # --- build the net-prior evaluators (single + batch) over the SAME transport
    handles = None
    sighted_game = None
    net = None
    if args.orch_shm_name:
        from carcassonne_ai.shm_eval_handles import MAX_K, connect_shm
        sighted_game = Game(sighted=True)
        handles = connect_shm(args.orch_shm_name, 0,
                              sighted_game.get_scalar_feature_size(),
                              sighted_game.get_input_channels())
        print(f"[bench] connected to carc-orch shm='{args.orch_shm_name}' as worker 0 "
              f"(MAX_K={MAX_K} boards/request)", flush=True)
        over = [b for b in batch_sizes if b > MAX_K]
        if over:
            print(f"[bench] NOTE: batch sizes {over} exceed the SHM MAX_K={MAX_K}; the "
                  f"evaluator CHUNKS them into ceil(N/{MAX_K}) sequential round-trips "
                  f"-> expect the curve to FLATTEN after {MAX_K}.", flush=True)
    elif args.net:
        # Reuse the eval harness's loader: it INFERS the rep from the checkpoint and
        # fails loud on an internally-inconsistent one (rather than mis-encoding every
        # leaf). Don't hand-roll the load — the ckpt carries n_filters/n_blocks too.
        sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
        from eval_fair_puct import _load_net_rep
        net, rep = _load_net_rep(args.net, device="cpu")
        sighted_game = Game(sighted=bool(rep["sighted"]))
        print(f"[bench] CPU net {Path(args.net).name}: "
              f"{rep['n_input_channels']}ch/{rep['n_scalar_features']}sc "
              f"({'sighted' if rep['sighted'] else 'non-sighted'})", flush=True)
    else:
        raise SystemExit("need --orch-shm-name or --net")

    single_ev = make_fair_net_prior_evaluator(
        cfg, net=net, handles=handles, sighted_game=sighted_game)
    batch_ev = make_fair_net_prior_batch_evaluator(
        cfg, net=net, handles=handles, sighted_game=sighted_game)

    # --- RTT PROBE: is the residual per-leaf cost LATENCY or GPU COMPUTE? ---------
    # The agent sweep flattens after batch_size=8 because the SHM protocol chunks at
    # MAX_K=8, so batch_size>8 still costs one round-trip per 8 leaves. Whether raising
    # MAX_K would help depends entirely on the SHAPE of RTT(k):
    #   flat in k  -> pure latency; k boards ride ONE round-trip -> raising MAX_K
    #                 divides the per-leaf transport cost by the new MAX_K.
    #   linear in k-> GPU compute-bound; raising MAX_K buys nothing.
    # Measure it directly rather than extrapolating from the agent curve.
    if args.rtt_probe:
        from carcassonne_ai.remote_evaluators import make_remote_batch_evaluator
        if handles is None:
            raise SystemExit("--rtt-probe needs --orch-shm-name")
        remote = make_remote_batch_evaluator(handles, sighted_game)
        probe_positions = build_positions(8, args.plies)
        pool = [b for _g, b in probe_positions]
        print("\n[bench] === RTT probe: round-trip time vs k (boards/request) ===",
              flush=True)
        print("      k |  RTT ms |  ms/board | vs k=1")
        print("    " + "-" * 44)
        rtt_rows = []
        base_rtt = None
        for k in (1, 2, 4, 8):
            boards = (pool * ((k // len(pool)) + 1))[:k]
            for _ in range(5):          # warm
                remote(boards)
            reps = 40
            t0 = time.perf_counter()
            for _ in range(reps):
                remote(boards)
            rtt = (time.perf_counter() - t0) / reps * 1000.0
            base_rtt = base_rtt if base_rtt is not None else rtt
            rtt_rows.append({"k": k, "rtt_ms": round(rtt, 3),
                             "ms_per_board": round(rtt / k, 3)})
            print(f"    {k:3d} | {rtt:7.3f} | {rtt / k:9.3f} | {rtt / base_rtt:5.2f}x",
                  flush=True)
        print("    " + "-" * 44)
        flat = rtt_rows[-1]["rtt_ms"] / rtt_rows[0]["rtt_ms"]
        print(f"[bench] RTT(k=8)/RTT(k=1) = {flat:.2f}x  -> "
              + ("LATENCY-bound (k is ~free): raising MAX_K divides per-leaf transport "
                 "by the new cap." if flat < 2.0 else
                 "COMPUTE-bound: raising MAX_K would NOT help."), flush=True)
        if args.out:
            Path(args.out).write_text(json.dumps(
                {"rtt_probe": rtt_rows, "transport": "carc-orch SHM"}, indent=2))
            print(f"[bench] wrote {args.out}")
        return

    positions = build_positions(args.moves, args.plies)
    print(f"[bench] {len(positions)} fixed positions @ {args.plies} plies; "
          f"knobs k_dets={args.k_dets} x sims={args.sims} = {args.k_dets * args.sims}",
          flush=True)

    results = {
        "knobs": {"sims": args.sims, "k_dets": args.k_dets,
                  "budget": args.sims * args.k_dets, "moves": args.moves,
                  "plies": args.plies,
                  "transport": "carc-orch SHM" if handles is not None else "CPU net",
                  "leaf": "v2.9 Bmild_cap8 curve125"},
        "points": [],
    }

    # --- the CHAMPION reference (heuristic priors, net-free, in-process Cython leaf)
    if args.champion:
        def make_champ(seed):
            return FairHeuristicPriorAgent(
                Game(enable_legal_moves_cache=True), cfg, sims=args.sims,
                k_dets=args.k_dets, seed=seed, exact_endgame=False)
        print("\n[bench] === CHAMPION (heuristic priors, batch_size=1) ===", flush=True)
        r = time_agent(make_champ, positions, "champion")
        results["points"].append(r)
        print(f"[bench] champion: {r['ms_per_move_mean']} ms/move "
              f"(GPU {r['gpu']['util_pct_mean']}% / {r['gpu']['power_w_mean']}W)", flush=True)

    # --- the net-prior curve
    for bs in batch_sizes:
        def make_net_agent(seed, _bs=bs):
            return FairHeuristicPriorAgent(
                Game(enable_legal_moves_cache=True), cfg, sims=args.sims,
                k_dets=args.k_dets, seed=seed, exact_endgame=False,
                evaluator=single_ev,
                batch_evaluator=(batch_ev if _bs > 1 else None),
                batch_size=_bs)
        print(f"\n[bench] === fair-netprior batch_size={bs} ===", flush=True)
        r = time_agent(make_net_agent, positions, f"netprior_bs{bs}")
        r["batch_size"] = bs
        results["points"].append(r)
        print(f"[bench] bs={bs}: {r['ms_per_move_mean']} ms/move "
              f"(GPU {r['gpu']['util_pct_mean']}% / {r['gpu']['power_w_mean']}W)", flush=True)

    # --- the curve + the pick-agreement diagnostic (vs bs=1: sanity, NOT identity)
    base = next((p for p in results["points"] if p.get("batch_size") == 1), None)
    print("\n" + "=" * 78)
    print("  batch_size |   ms/move |  speedup |  GPU util |  GPU power | picks==bs1")
    print("=" * 78)
    for p in results["points"]:
        bs = p.get("batch_size")
        spd = (base["ms_per_move_mean"] / p["ms_per_move_mean"]) if base else float("nan")
        agree = ""
        if base and bs is not None:
            n_same = sum(1 for a, b in zip(p["picks"], base["picks"]) if a == b)
            agree = f"{n_same}/{len(base['picks'])}"
            p["picks_match_bs1"] = agree
        print(f"  {str(bs) if bs else 'champion':>10} | {p['ms_per_move_mean']:9.1f} | "
              f"{spd:7.2f}x | {str(p['gpu']['util_pct_mean']) + '%':>9} | "
              f"{str(p['gpu']['power_w_mean']) + 'W':>10} | {agree:>10}")
    print("=" * 78)

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2))
        print(f"[bench] wrote {args.out}")


if __name__ == "__main__":
    main()
