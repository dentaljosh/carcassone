"""Size the net@800 (GPU) vs heur@800 (CPU) split in an eval game, to bound the
Rust-heur payoff. Each player makes ~half the moves in net-vs-heur, so the share of
search time is ~ the per-search-time ratio. Fast-forward to representative stages with
cheap play, then time a full 800-sim search of each player there. Matches prod eval config."""
import os, time, dataclasses, random, statistics, sys
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
SIMS, CPUCT, SEED = 800, 3.0, 12345
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"device={device}")
ckpt = torch.load(CKPT, map_location=device, weights_only=False)
n_scalar = int(ckpt.get("n_scalar_features", 10)); include_farm = (n_scalar == 12)
net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"],
                     n_scalar_features=n_scalar).to(device)
net.load_state_dict(ckpt["model_state"]); net.train(False)

game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
base = make_single_evaluator(net, device, game)
cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=0.25)
net_mcts = NeuralMCTS(game=game, evaluator=make_v25_value_wrapper(base, cfg),
                      simulations=SIMS, seed=SEED, c_puct=CPUCT)
heur_mcts = HeuristicMCTS(game=Game(enable_legal_moves_cache=True),
                          simulations=SIMS, seed=SEED + 1, heur_leaf="v2_7")
ff = HeuristicMCTS(game=Game(enable_legal_moves_cache=True),
                   simulations=40, seed=SEED + 2, heur_leaf="v2_7")

def timed(mcts, b):
    mcts.clear(); t = time.perf_counter(); mcts.best_action(b)
    if device.type == "cuda": torch.cuda.synchronize()
    return time.perf_counter() - t

random.seed(SEED)
board = game.get_init_board()
print("warming up net (cudnn autotune)...")
net_mcts.clear(); net_mcts.best_action(board)
if device.type == "cuda": torch.cuda.synchronize()

targets = [8, 22, 40, 58]; moves = 0; results = []
for tgt in targets:
    while moves < tgt and game.get_game_ended(board, 0) == 0.0:
        ff.clear(); board, _ = game.get_next_state(board, ff.best_action(board)); moves += 1
    if game.get_game_ended(board, 0) != 0.0:
        print(f"(game ended at move {moves}, stopping)"); break
    nt = timed(net_mcts, board); ht = timed(heur_mcts, board)
    results.append((moves, nt, ht))
    print(f"move {moves:3d}: net@800={nt:6.2f}s  heur@800={ht:6.2f}s  net/heur={nt/ht:.2f}  heur_share={ht/(nt+ht)*100:4.0f}%")

nts = [r[1] for r in results]; hts = [r[2] for r in results]
sn, sh = sum(nts), sum(hts)
print(f"\n=== AGGREGATE over {len(results)} sampled stages (SIMS={SIMS}) ===")
print(f"  mean net@800  search: {statistics.mean(nts):.2f}s  (GPU-dispatch, NOT Rust-able)")
print(f"  mean heur@800 search: {statistics.mean(hts):.2f}s  (pure CPU, RUST-ABLE)")
print(f"  heur CPU share of a net-vs-heur game: {sh/(sn+sh)*100:.0f}%  <- Rust-payoff ceiling")
print(f"  net GPU floor (stays even with Rust):  {sn/(sn+sh)*100:.0f}%")
