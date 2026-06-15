"""Contended version of the eval-split profiler — addresses the 'isolated, not production'
flaw. W workers build net@800 + heur@800, advance to mid-game, then a Barrier releases them
to search SIMULTANEOUSLY (real GPU/CPU contention like production eval). Reports the contended
net/heur split + the absolute contended net time (cross-check vs the ~12.5s/move sealed games)."""
import os, time, dataclasses, random, statistics
import multiprocessing as mp

def worker(wid, barrier, q):
    os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
    os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
    os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
    import torch
    from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS
    from carcassonne_ai.network import CarcassonneNet
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    CKPT = "/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt"
    SIMS, CPUCT, SEED = 800, 3.0, 1000 + wid
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(CKPT, map_location=device, weights_only=False)
    n_scalar = int(ckpt.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"],
                         n_scalar_features=n_scalar).to(device)
    net.load_state_dict(ckpt["model_state"]); net.train(False)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=(n_scalar == 12))
    base = make_single_evaluator(net, device, game)
    cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=0.25)
    net_mcts = NeuralMCTS(game=game, evaluator=make_v25_value_wrapper(base, cfg),
                          simulations=SIMS, seed=SEED, c_puct=CPUCT)
    heur_mcts = HeuristicMCTS(game=Game(enable_legal_moves_cache=True),
                              simulations=SIMS, seed=SEED + 1, heur_leaf="v2_7")
    ff = HeuristicMCTS(game=Game(enable_legal_moves_cache=True),
                       simulations=40, seed=SEED + 2, heur_leaf="v2_7")
    random.seed(SEED)
    board = game.get_init_board(); mv = 0
    while mv < 30 and game.get_game_ended(board, 0) == 0.0:
        ff.clear(); board, _ = game.get_next_state(board, ff.best_action(board)); mv += 1
    import threading
    net_mcts.clear(); net_mcts.best_action(board)            # warmup
    if device.type == "cuda": torch.cuda.synchronize()
    try: barrier.wait(timeout=180)                            # all start net search together
    except (threading.BrokenBarrierError, Exception): pass    # a worker died -> proceed anyway
    t = time.perf_counter(); net_mcts.clear(); net_mcts.best_action(board)
    if device.type == "cuda": torch.cuda.synchronize()
    net_t = time.perf_counter() - t
    try: barrier.wait(timeout=180)                            # all start heur search together
    except (threading.BrokenBarrierError, Exception): pass
    t = time.perf_counter(); heur_mcts.clear(); heur_mcts.best_action(board)
    heur_t = time.perf_counter() - t
    q.put((wid, net_t, heur_t, mv))

if __name__ == "__main__":
    N = 14
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(N); q = ctx.Queue()
    ps = [ctx.Process(target=worker, args=(i, barrier, q)) for i in range(N)]
    for p in ps: p.start()
    res = []
    import queue as _q
    for _ in range(N):
        try: res.append(q.get(timeout=420))
        except _q.Empty: break
    for p in ps:
        p.join(timeout=10)
        if p.is_alive(): p.terminate()
    print(f"collected {len(res)}/{N} workers")
    if len(res) < 2:
        print("TOO FEW workers survived — result unreliable, rerun with smaller N"); raise SystemExit(1)
    nts = [r[1] for r in res]; hts = [r[2] for r in res]
    sn, sh = sum(nts), sum(hts)
    print(f"\n=== CONTENDED (W={N} simultaneous, mid-game ~move 30, SIMS=800) ===")
    print(f"  net@800:  mean={statistics.mean(nts):5.2f}s  min={min(nts):.2f} max={max(nts):.2f}  (GPU, contended)")
    print(f"  heur@800: mean={statistics.mean(hts):5.2f}s  min={min(hts):.2f} max={max(hts):.2f}  (CPU, contended)")
    print(f"  heur CPU share (CONTENDED): {sh/(sn+sh)*100:.0f}%   <- the reliable Rust-payoff ceiling (isolated said 13%)")
    print(f"  net  GPU share (CONTENDED): {sn/(sn+sh)*100:.0f}%")
    print(f"  cross-check: contended net@800 mean {statistics.mean(nts):.1f}s/move vs sealed-game ~12.5s/move")
