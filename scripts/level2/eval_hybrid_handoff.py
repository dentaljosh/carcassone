"""L2 hybrid-handoff eval: can iter8's early/mid policy + deep heuristic endgame
combine?  (measurement only — no training.)

Plays N paired, seat-balanced head-to-head games between two agents and reports
W/D/L, elo, raw winrate, paired-margin z, deck hashes + a provenance manifest.
The paired-z / summary math is byte-for-byte the canonical Level-2 statistic
(scripts/ladder_rung_eval.py); iter8/heur construction is byte-for-byte the
L2-3 regret harness (scripts/level2/endgame_regret.py) so this run sits on the
SAME ruler as the #8 / L2-3 verdicts.

Agent spec tokens (--agent-a / --agent-b):
    iter8            production NeuralMCTS@200, c=3.0, v2.7 leaf + residual 0.25
    heur@<sims>      HeuristicMCTS(heur_leaf="v2_7", simulations=<sims>)
    hybrid:<K>:<sims>
                     iter8's policy until the endgame, then HeuristicMCTS@<sims>.
                     HANDOFF SEMANTICS (latched, turn-atomic): on the FIRST of the
                     agent's own decisions that is a TILES-phase position with
                     k_remaining <= K, the agent switches to the heuristic for that
                     tile AND every decision after (its meeple + all later turns).
                     k_remaining = len(deck) + (1 if next_tile is not None else 0)
                     — IDENTICAL to gen_endgame_positions.k_remaining, so "K<=2"
                     here == the L2-3 K=2 band. Latching only on a TILES decision
                     keeps turns atomic (the boundary tile+meeple are not split
                     across the two sub-agents).

The v2.7 production leaf env is set below (CAP=12, DROP_THREE_OPEN=1, FLAT_LEAF=1,
VALUE_BLEND=0) BEFORE the carcassonne_ai import; iter8's residual_scale=0.25 is
applied in code (dataclasses.replace), matching endgame_regret exactly.

Usage:
  # plumbing + handoff-fires smoke (single process, fast):
  python scripts/level2/eval_hybrid_handoff.py --agent-a hybrid:5:800 --agent-b iter8 \
      --ckpt /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
      --smoke

  # real paired band:
  python -u scripts/level2/eval_hybrid_handoff.py --agent-a hybrid:5:3200 --agent-b iter8 \
      --ckpt /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
      --n 200 --paired --seed-start 3400000000 --workers 14 \
      --out-root /mnt/c/carc-shared/level2_hybrid --shared-claim
"""
from __future__ import annotations

import os
# v2.7 production leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG
# reads these at import). Matches endgame_regret / the L1 ladder / production.
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import dataclasses
import json
import math
import socket
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing import get_context
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))   # scripts/level2 -> endgame_solver

import torch
from wingedsheep.carcassonne.objects.game_phase import GamePhase

from carcassonne_ai.claim import try_claim as _try_claim
from carcassonne_ai.eval_provenance import deck_hash
from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.run_manifest import game_tag, write_manifest
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
import endgame_solver as S  # exact endgame solver (same dir); leaf-independent terminal scoring

REPO = Path(__file__).resolve().parent.parent.parent
EVAL_ROOT = REPO / "data" / "level2_hybrid"

# iter8 production play knobs (PRODUCTION.yaml). residual_scale lives in code, not env.
ITER8_SIMS = 200
ITER8_CPUCT = 3.0
ITER8_RESIDUAL_SCALE = 0.25

# Exact endgame-solver modes for the `exact:K:MODE` agent.
#   clair -> clairvoyant minimax + alpha-beta (FAST; a like-for-like comparison vs the
#            clairvoyant-search production agents, which also descend the true deck order).
#   marg  -> marginalized expectiminimax (fair-information / honest hidden-bag value; NO
#            alpha-beta -> realistically tractable only ~K<=2).
# The exact tail is LEAF-INDEPENDENT (flat_base_score = true terminal score), so meeple_k
# only ever affects the NEURAL prefix, never an exact move.
_EXACT_MODES = {"clair": "clairvoyant", "marg": "marginalized"}
EXACT_BUDGET = int(os.environ.get("CARCASSONNE_EXACT_BUDGET", "2000000"))

# Per-worker state (set in _worker_init).
_W: dict = {}


# --------------------------------------------------------------------------- #
# Agent spec parsing                                                           #
# --------------------------------------------------------------------------- #
def parse_agent(spec: str):
    """-> (kind, K, sims). Validates the token.

    iter8            -> ("iter8", None, ITER8_SIMS)
    heur@N           -> ("heur", None, N)
    hybrid:K:N       -> ("hybrid", K, N)
    """
    spec = spec.strip()
    if spec == "iter8":
        return ("iter8", None, ITER8_SIMS)
    if spec.startswith("heur@"):
        sims = int(spec[len("heur@"):])
        if sims <= 0:
            raise ValueError(f"bad sims in {spec!r}")
        return ("heur", None, sims)
    if spec.startswith("hybrid:"):
        parts = spec.split(":")
        if len(parts) != 3:
            raise ValueError(f"hybrid spec must be hybrid:K:N, got {spec!r}")
        K, sims = int(parts[1]), int(parts[2])
        if K < 0 or sims <= 0:
            raise ValueError(f"bad K/sims in {spec!r}")
        return ("hybrid", K, sims)
    if spec.startswith("exact:"):
        parts = spec.split(":")
        if len(parts) != 3:
            raise ValueError(f"exact spec must be exact:K:MODE (MODE=clair|marg), got {spec!r}")
        K, mode = int(parts[1]), parts[2]
        if K < 0:
            raise ValueError(f"bad K in {spec!r}")
        if mode not in _EXACT_MODES:
            raise ValueError(f"bad mode {mode!r} in {spec!r}; expected clair|marg")
        return ("exact", K, mode)        # 3rd field is the MODE string, not sims
    raise ValueError(f"unknown agent spec {spec!r}; expected iter8|heur@N|hybrid:K:N|exact:K:MODE")


def _needs_net(spec: str) -> bool:
    # exact needs the net for the early/mid prefix AND the timeout fallback move.
    return parse_agent(spec)[0] in ("iter8", "hybrid", "exact")


def k_remaining(state) -> int:
    """Tiles left = undrawn deck + the one in hand. IDENTICAL to
    gen_endgame_positions.k_remaining, so the hybrid's K matches the L2-3 band."""
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def hybrid_should_latch(state, K: int):
    """The endgame handoff trigger. Returns (latch_now, k_remaining).

    latch_now is True iff this is a TILES-phase position with k_remaining<=K.
    Restricting the trigger to the TILES phase keeps turns atomic — the boundary
    tile AND its meeple are played by the same (heuristic) sub-agent, never split.
    Because k_remaining is monotone non-increasing, latching is a one-way switch."""
    k = k_remaining(state)
    return (state.phase == GamePhase.TILES and k <= K), k


# --------------------------------------------------------------------------- #
# Agents — uniform interface .move(board) -> int, plus move counters           #
# --------------------------------------------------------------------------- #
def _make_iter8_mcts(base_eval, game_farm, seed, meeple_k=0.0):
    """base_eval = the raw net evaluator for game_farm (local make_single_evaluator
    OR remote SHM make_remote_single_evaluator). The v2.7 leaf wraps it.

    meeple_k (2026-06-22, v2.8 leaf-swap): adds the v2.8 flat meeple-economy term to the
    NEURAL VALUE leaf (legacy LeafConfig.meeple_k field -> flat path). 0.0 == v2.7 (default,
    bit-identical to prior CL-026 behaviour)."""
    cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=ITER8_RESIDUAL_SCALE, meeple_k=meeple_k)
    leaf = make_v25_value_wrapper(base_eval, cfg)
    return NeuralMCTS(game=game_farm, evaluator=leaf, simulations=ITER8_SIMS,
                      seed=seed, c_puct=ITER8_CPUCT)


def _heur_leaf_cfg(meeple_k):
    """v2.8 leaf-swap: a LeafConfig with the flat meeple term for the HeuristicMCTS endgame
    (None == v2.7 / DEFAULT_CONFIG, bit-identical default)."""
    return dataclasses.replace(DEFAULT_CONFIG, meeple_k=meeple_k) if meeple_k else None


class _Iter8Agent:
    def __init__(self, base_eval, game_farm, seed, meeple_k=0.0):
        self._m = _make_iter8_mcts(base_eval, game_farm, seed, meeple_k)
        self.neural_moves = 0
        self.heur_moves = 0
        self.latch_k = None

    def move(self, board) -> int:
        self._m.clear()
        self.neural_moves += 1
        return int(self._m.best_action(board))


class _HeurAgent:
    def __init__(self, game_plain, sims, seed, meeple_k=0.0):
        self._m = HeuristicMCTS(game=game_plain, simulations=sims, seed=seed,
                                heur_leaf="v2_7", leaf_cfg=_heur_leaf_cfg(meeple_k))
        self.neural_moves = 0
        self.heur_moves = 0
        self.latch_k = None

    def move(self, board) -> int:
        self._m.clear()
        self.heur_moves += 1
        return int(self._m.best_action(board))


class _HybridAgent:
    """iter8 policy until the first TILES decision with k_remaining<=K, then heur@sims."""

    def __init__(self, base_eval, game_farm, game_plain, K, heur_sims, seed, meeple_k=0.0):
        self._neural = _make_iter8_mcts(base_eval, game_farm, seed, meeple_k)
        # offset the heur seed so it never coincides with the neural seed
        self._heur = HeuristicMCTS(game=game_plain, simulations=heur_sims,
                                   seed=seed + 7, heur_leaf="v2_7",
                                   leaf_cfg=_heur_leaf_cfg(meeple_k))
        self._K = K
        self._latched = False
        self.latch_k = None
        self.neural_moves = 0
        self.heur_moves = 0

    def move(self, board) -> int:
        if not self._latched:
            latch_now, k = hybrid_should_latch(board.state, self._K)
            if latch_now:
                self._latched = True
                self.latch_k = k
        if self._latched:
            self._heur.clear()
            self.heur_moves += 1
            return int(self._heur.best_action(board))
        self._neural.clear()
        self.neural_moves += 1
        return int(self._neural.best_action(board))


class _ExactAgent:
    """Neural (RoD/iter8) policy until the first TILES decision with k_remaining<=K,
    then EXACT-SOLVER play for the rest of the game (the boundary tile's meeple + all
    later turns). Latching is the SAME trigger as _HybridAgent (turn-atomic, one-way).

    The chosen move is min(optimal_actions): deterministic, and value-irrelevant within
    the optimal set under optimal play. The solver is minimax-optimal vs a WORST-CASE
    opponent — NOT a best-response to this specific (suboptimal) opponent — i.e. a valid,
    conservative endgame policy, not an oracle exploiter.

    Timeout fallback: a solve that exceeds the node budget (BudgetExceeded) falls back to
    the NEURAL move for THAT decision only (the agent stays latched and retries the solver
    next ply on the now-smaller tree). Fallbacks are counted (n_timeouts), never hidden.
    mode='marg' has no alpha-beta and will time out above ~K=2."""

    def __init__(self, base_eval, game_farm, game_plain, K, mode, seed, meeple_k=0.0,
                 budget=EXACT_BUDGET):
        self._neural = _make_iter8_mcts(base_eval, game_farm, seed, meeple_k)
        self._game = game_plain
        self._K = K
        self._mode = _EXACT_MODES[mode]
        self._ab = (self._mode == "clairvoyant")   # alpha-beta is clairvoyant-only
        self._budget = budget
        self._latched = False
        self.latch_k = None
        self.neural_moves = 0
        self.heur_moves = 0          # kept 0 — harness symmetry only
        # exact instrumentation (read by _play_one into GameResult)
        self.exact_moves = 0
        self.n_timeouts = 0
        self.solver_secs = 0.0
        self.solver_nodes = 0
        self.max_solve_secs = 0.0
        self.latch_score = None      # margin (mover perspective) at the latching decision
        self.latch_meeples = None    # mover's meeples-in-hand at latch
        self.latch_nlegal = None     # legal action count at latch

    def move(self, board) -> int:
        if not self._latched:
            latch_now, k = hybrid_should_latch(board.state, self._K)
            if latch_now:
                self._latched = True
                self.latch_k = k
                mv = board.state.current_player
                sc = board.state.scores
                self.latch_score = int(sc[mv] - sc[1 - mv])
                self.latch_meeples = int(board.state.meeples[mv])
                self.latch_nlegal = int(self._game.get_valid_moves(board).sum())
        if not self._latched:
            self._neural.clear()
            self.neural_moves += 1
            return int(self._neural.best_action(board))
        t0 = time.perf_counter()
        try:
            res = S.solve(self._game, board, mode=self._mode,
                          budget=self._budget, alphabeta=self._ab)
            dt = time.perf_counter() - t0
            self.solver_secs += dt
            self.max_solve_secs = max(self.max_solve_secs, dt)
            self.solver_nodes += res.nodes
            self.exact_moves += 1
            return int(min(res.optimal_actions))
        except S.BudgetExceeded:
            self.solver_secs += time.perf_counter() - t0
            self.n_timeouts += 1
            self._neural.clear()
            self.neural_moves += 1       # fallback move; stays latched
            return int(self._neural.best_action(board))


def make_agent(spec: str, *, base_factory, game_farm, game_plain, seed, meeple_k=0.0):
    """base_factory(game_farm) -> raw net evaluator (local or remote SHM). Only
    called for agents that need the net (iter8, hybrid, exact); heur never touches it.
    meeple_k>0 swaps in the v2.8 flat meeple-economy leaf (default 0.0 == v2.7)."""
    kind, K, sims_or_mode = parse_agent(spec)
    if kind == "iter8":
        return _Iter8Agent(base_factory(game_farm), game_farm, seed, meeple_k)
    if kind == "heur":
        return _HeurAgent(game_plain, sims_or_mode, seed, meeple_k)
    if kind == "exact":
        return _ExactAgent(base_factory(game_farm), game_farm, game_plain, K, sims_or_mode,
                           seed, meeple_k)
    return _HybridAgent(base_factory(game_farm), game_farm, game_plain, K, sims_or_mode,
                        seed, meeple_k)


# --------------------------------------------------------------------------- #
@dataclass
class GameResult:
    seed: int
    a_seat: int            # seat agent-A plays this game (0 or 1)
    agent_a: str
    agent_b: str
    score_p0: int
    score_p1: int
    diff: int              # A - B  (from A's perspective)
    won_by_a: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""
    a_neural_moves: int = 0
    a_heur_moves: int = 0
    b_neural_moves: int = 0
    b_heur_moves: int = 0
    a_latch_k: int | None = None
    b_latch_k: int | None = None
    # exact-solver handoff instrumentation (0/None unless the side is an exact:K:MODE agent)
    a_exact_moves: int = 0
    b_exact_moves: int = 0
    a_timeouts: int = 0
    b_timeouts: int = 0
    a_solver_secs: float = 0.0
    b_solver_secs: float = 0.0
    a_solver_nodes: int = 0
    b_solver_nodes: int = 0
    a_max_solve_secs: float = 0.0
    b_max_solve_secs: float = 0.0
    a_latch_score: int | None = None
    b_latch_score: int | None = None
    a_latch_meeples: int | None = None
    b_latch_meeples: int | None = None
    a_latch_nlegal: int | None = None
    b_latch_nlegal: int | None = None


def _result_path(out: Path, seed: int, a_seat: int) -> Path:
    return out / f"seed{seed:010d}_a{a_seat}.json"


def _try_load(p: Path):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p: Path, r: GameResult):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    json.dump(asdict(r), open(tmp, "w"))
    tmp.replace(p)


def _worker_init(ckpt: str, device_str: str, need_net: bool,
                 shared_claim: bool, claim_host: str, claim_stale_secs: int,
                 shm_name: str = "", id_q=None, ns: int = 10,
                 meeple_k_a: float = 0.0, meeple_k_b: float = 0.0):
    torch.set_num_threads(1)
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["claim_stale_secs"] = claim_stale_secs
    _W["mk_a"] = meeple_k_a
    _W["mk_b"] = meeple_k_b
    _W["net"] = None
    _W["handles"] = None
    _W["orch"] = False
    _W["farm"] = ns > 10
    if shm_name:
        # carc-orch SHM orchestrator: the server owns the only net copy; this
        # worker is CPU-only and gets net forwards (iter8 priors+value) over SHM.
        # The v2.7 leaf + the heur@N search still run here on the worker (CPU).
        from carcassonne_ai.shm_eval_handles import connect_shm
        _W["orch"] = True
        _W["dev"] = torch.device("cpu")
        _W["handles"] = connect_shm(shm_name, id_q.get(), ns)
        return
    dev = torch.device(device_str)
    _W["dev"] = dev
    if need_net:
        ck = torch.load(ckpt, map_location=dev, weights_only=False)
        ns = int(ck.get("n_scalar_features", 10))
        net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                             n_scalar_features=ns,
                             value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
        net.load_state_dict(ck["model_state"])
        net.train(False)
        _W["net"] = net
        _W["farm"] = ns > 10


def _play_one(args) -> GameResult | None:
    out_str, seed, a_seat, agent_a, agent_b = args
    out = Path(out_str)
    p = _result_path(out, seed, a_seat)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale_secs"]):
            return None

    import random
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)            # referee, drives the deck
    board = game.get_init_board()
    dh = deck_hash(board)

    # Per-side games so legal-move caches never cross. Neural/hybrid need the
    # farm-scalar game width that matches the net (ns>10 -> include farm scalars).
    farm = _W.get("farm", False)
    ga_farm = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    ga_plain = Game(enable_legal_moves_cache=True)
    gb_farm = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    gb_plain = Game(enable_legal_moves_cache=True)
    if _W.get("orch"):
        def base_factory(gf):
            return make_remote_single_evaluator(_W["handles"], gf)
    else:
        def base_factory(gf):
            return make_single_evaluator(_W["net"], _W["dev"], gf)
    a = make_agent(agent_a, base_factory=base_factory,
                   game_farm=ga_farm, game_plain=ga_plain, seed=seed, meeple_k=_W.get("mk_a", 0.0))
    b = make_agent(agent_b, base_factory=base_factory,
                   game_farm=gb_farm, game_plain=gb_plain, seed=seed + 1, meeple_k=_W.get("mk_b", 0.0))

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        agent = a if cur == a_seat else b
        action = agent.move(board)
        if not mask[action]:
            raise RuntimeError(f"agent returned illegal action {action}")
        board, _ = game.get_next_state(board, action)
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    def gx(agent, attr, default=0):
        return getattr(agent, attr, default)
    r = GameResult(
        seed=seed, a_seat=a_seat, agent_a=agent_a, agent_b=agent_b,
        score_p0=int(s0), score_p1=int(s1), diff=int(diff),
        won_by_a=(diff > 0), drew=(diff == 0), elapsed_s=elapsed, moves=moves,
        deck_hash=dh,
        a_neural_moves=a.neural_moves, a_heur_moves=a.heur_moves,
        b_neural_moves=b.neural_moves, b_heur_moves=b.heur_moves,
        a_latch_k=a.latch_k, b_latch_k=b.latch_k,
        a_exact_moves=gx(a, "exact_moves"), b_exact_moves=gx(b, "exact_moves"),
        a_timeouts=gx(a, "n_timeouts"), b_timeouts=gx(b, "n_timeouts"),
        a_solver_secs=round(gx(a, "solver_secs", 0.0), 3), b_solver_secs=round(gx(b, "solver_secs", 0.0), 3),
        a_solver_nodes=gx(a, "solver_nodes"), b_solver_nodes=gx(b, "solver_nodes"),
        a_max_solve_secs=round(gx(a, "max_solve_secs", 0.0), 3), b_max_solve_secs=round(gx(b, "max_solve_secs", 0.0), 3),
        a_latch_score=gx(a, "latch_score", None), b_latch_score=gx(b, "latch_score", None),
        a_latch_meeples=gx(a, "latch_meeples", None), b_latch_meeples=gx(b, "latch_meeples", None),
        a_latch_nlegal=gx(a, "latch_nlegal", None), b_latch_nlegal=gx(b, "latch_nlegal", None),
    )
    _save(p, r)
    return r


def _paired_z(results):
    """Paired z on per-deck score difference. Pairs (seed,a_seat=0) with
    (seed,a_seat=1): both A-perspective diffs, so d=(diff0+diff1)/2 is A's net
    seat-balanced margin per deck. z = mean_d / se_d. (= ladder_rung_eval._paired_z)"""
    by_seed = {}
    for r in results:
        by_seed.setdefault(r.seed, {})[r.a_seat] = r.diff
    ds = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    if len(ds) < 2:
        return None, None, 0
    mean = sum(ds) / len(ds)
    var = sum((d - mean) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    z = mean / se if se > 0 else float("nan")
    return mean, z, len(ds)


def _summary(results, agent_a, agent_b):
    n = len(results)
    w = sum(1 for r in results if r.won_by_a)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    avg = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    # raw-winrate z vs 0.5 (the "winrate z" the #8 row reports alongside paired-z)
    wr_se = math.sqrt(0.25 / n)
    wr_z = (wr - 0.5) / wr_se if wr_se > 0 else float("nan")
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    mean_d, z, npair = _paired_z(results)
    # handoff instrumentation (A side; mirror B if it is the hybrid)
    a_heur = [r.a_heur_moves for r in results]
    a_neu = [r.a_neural_moves for r in results]
    latches = [r.a_latch_k for r in results if r.a_latch_k is not None]
    # exact-solver instrumentation (A side)
    a_exact = [r.a_exact_moves for r in results]
    a_solv = [r.a_solver_secs for r in results]
    a_to = [r.a_timeouts for r in results]
    a_maxsolve = [r.a_max_solve_secs for r in results]
    print()
    print(f"=== HYBRID-HANDOFF: {agent_a}  vs  {agent_b} ===")
    print(f"games:  {n}   {agent_a}: {w}W / {d}D / {losses}L   winrate {wr:.3f} (z={wr_z:+.2f})")
    print(f"avg score diff (A - B): {avg:+.2f}")
    print(f"ELO (A vs B): {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    if mean_d is not None:
        print(f"PAIRED: {npair} decks   mean seat-balanced margin {mean_d:+.2f}   z = {z:+.2f}")
    if any(a_heur):
        print(f"A handoff: heur-moves/game mean {sum(a_heur)/n:.1f} "
              f"(range {min(a_heur)}-{max(a_heur)}), neural-moves/game mean {sum(a_neu)/n:.1f}; "
              f"latched in {len(latches)}/{n} games")
    if any(a_exact):
        print(f"A EXACT: exact-moves/game mean {sum(a_exact)/n:.1f} "
              f"(range {min(a_exact)}-{max(a_exact)}); solver {sum(a_solv)/n:.2f}s/game "
              f"(max-single-solve {max(a_maxsolve):.1f}s); timeouts {sum(a_to)} over {n} games; "
              f"latched {len(latches)}/{n}")
    return {
        "agent_a": agent_a, "agent_b": agent_b, "n": n, "W": w, "D": d, "L": losses,
        "winrate": wr, "winrate_z": wr_z, "elo": elo, "elo_sig_1sigma": elo_sig,
        "avg_diff": avg, "paired_mean_margin": mean_d, "paired_z": z,
        "n_paired": npair, "n_deck_hashes": len({r.deck_hash for r in results}),
        "a_heur_moves_mean": (sum(a_heur) / n) if n else 0,
        "a_neural_moves_mean": (sum(a_neu) / n) if n else 0,
        "a_latched_games": len(latches),
        "a_exact_moves_mean": (sum(a_exact) / n) if n else 0,
        "a_solver_secs_mean": (sum(a_solv) / n) if n else 0,
        "a_solver_secs_max_single": max(a_maxsolve) if a_maxsolve else 0,
        "a_timeouts_total": sum(a_to),
    }


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))
    return work


def _smoke(args) -> int:
    """Single-process plumbing + handoff-fires proof: play one paired pair,
    print move counts so the handoff is visibly exercised, then exit."""
    dev = torch.device(args.device)
    net, farm = None, False
    if _needs_net(args.agent_a) or _needs_net(args.agent_b):
        ck = torch.load(args.ckpt, map_location=dev, weights_only=False)
        ns = int(ck.get("n_scalar_features", 10))
        net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                             n_scalar_features=ns,
                             value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
        net.load_state_dict(ck["model_state"])
        net.train(False)
        farm = ns > 10
    print(f"[smoke] device={dev} farm_scalars={farm} a={args.agent_a} b={args.agent_b}")
    import random
    results = []
    t0 = time.perf_counter()
    for a_seat in (0, 1):
        seed = args.seed_start
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        def base_factory(gf):
            return make_single_evaluator(net, dev, gf)
        a = make_agent(args.agent_a, base_factory=base_factory,
                       game_farm=Game(enable_legal_moves_cache=True, include_farm_scalars=farm),
                       game_plain=Game(enable_legal_moves_cache=True), seed=seed, meeple_k=args.meeple_k_a)
        b = make_agent(args.agent_b, base_factory=base_factory,
                       game_farm=Game(enable_legal_moves_cache=True, include_farm_scalars=farm),
                       game_plain=Game(enable_legal_moves_cache=True), seed=seed + 1, meeple_k=args.meeple_k_b)
        moves = 0
        while game.get_game_ended(board, 0) == 0.0:
            cur = board.state.current_player
            mask = game.get_valid_moves(board)
            agent = a if cur == a_seat else b
            action = agent.move(board)
            assert mask[action], f"illegal action {action}"
            board, _ = game.get_next_state(board, action)
            moves += 1
        s0, s1 = board.state.scores
        diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
        print(f"[smoke] a_seat={a_seat}: scores={s0}-{s1} diff(A-B)={diff:+d} moves={moves} | "
              f"A neural/heur/exact={a.neural_moves}/{a.heur_moves}/{getattr(a,'exact_moves',0)} "
              f"latch_k={a.latch_k} solver={getattr(a,'solver_secs',0.0):.1f}s "
              f"(max {getattr(a,'max_solve_secs',0.0):.1f}s) timeouts={getattr(a,'n_timeouts',0)} ; "
              f"B neural/heur/exact={b.neural_moves}/{b.heur_moves}/{getattr(b,'exact_moves',0)} "
              f"latch_k={b.latch_k}")
        results.append((a_seat, diff))
    dt = time.perf_counter() - t0
    # sanity: a hybrid:K agent MUST have made some heur moves (handoff fired)
    for spec, agent in ((args.agent_a, a), (args.agent_b, b)):
        kind, K, sims = parse_agent(spec)
        if kind == "hybrid":
            assert agent.heur_moves > 0, f"hybrid {spec} never handed off (K too small?)"
            assert agent.neural_moves > 0, f"hybrid {spec} never used neural (K too big?)"
        if kind == "exact":
            assert agent.exact_moves > 0, f"exact {spec} never solved (K too small / all timeouts?)"
            assert agent.neural_moves > 0, f"exact {spec} never used neural prefix (K too big?)"
    print(f"[smoke] OK — plumbing + handoff verified ({dt:.1f}s for 2 games)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_hybrid_handoff")
    ap.add_argument("--agent-a", required=True, help="iter8|heur@N|hybrid:K:N")
    ap.add_argument("--agent-b", required=True)
    ap.add_argument("--ckpt", required=True, help="iter8 checkpoint (.pt)")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=3_400_000_000)
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--device", default=("cuda" if torch.cuda.is_available() else "cpu"))
    ap.add_argument("--shm-eval-server", type=str, default=None,
                    help="carc-orch SHM orchestrator: attach to /dev/shm/carc_<NAME> for "
                         "batched iter8 net forwards over shared memory (the server owns the "
                         "net; workers are CPU-only). Start the server first (run_server.sh / "
                         "scripts/level2/run_hybrid_bands_orch.sh). Unset = per-worker nets.")
    ap.add_argument("--smoke", action="store_true",
                    help="single-process plumbing + handoff-fires proof, then exit")
    ap.add_argument("--out-root", type=str, default=None)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=5400)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--meeple-k-a", type=float, default=0.0,
                    help="v2.8 leaf-swap: flat meeple-economy term for agent-A's leaf (neural value "
                         "+ heur endgame). 0.0 == v2.7 (default). e.g. 2.0 for the v2.8 candidate.")
    ap.add_argument("--meeple-k-b", type=float, default=0.0, help="same, for agent-B (default 0.0 = v2.7).")
    args = ap.parse_args(argv)
    parse_agent(args.agent_a); parse_agent(args.agent_b)  # validate early
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n")

    if args.smoke:
        return _smoke(args)

    def _san(s):
        return s.replace("@", "").replace(":", "_")
    _mk_tag = "" if (args.meeple_k_a == 0.0 and args.meeple_k_b == 0.0) else f"_mkA{args.meeple_k_a:g}_mkB{args.meeple_k_b:g}"
    sub = args.out_subdir or f"{_san(args.agent_a)}__vs__{_san(args.agent_b)}{_mk_tag}"
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    tasks = [(str(out), seed, a_seat, args.agent_a, args.agent_b)
             for seed, a_seat in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, t[1], t[2]))) is not None]
        if results:
            summ = _summary(results, args.agent_a, args.agent_b)
            json.dump(summ, open(out / "summary.json", "w"), indent=2)
        else:
            print("no cached results yet")
        return 0

    seed_range = [args.seed_start, args.seed_start + (args.n // 2 if args.paired else args.n)]
    need_net = _needs_net(args.agent_a) or _needs_net(args.agent_b)
    # ns (scalar-feature width) — needed for SHM connect AND for non-orch farm flag.
    _ns = 10
    if need_net:
        _ck = torch.load(str(args.ckpt), map_location="cpu", weights_only=False)
        _ns = int(_ck.get("n_scalar_features", 10))
        del _ck
    write_manifest(out, kind="eval_hybrid_handoff", game=game_tag(Game()),
                   config={"agent_a": args.agent_a, "agent_b": args.agent_b,
                           "ckpt": str(args.ckpt), "n": args.n, "paired": args.paired,
                           "seed_start": args.seed_start, "seed_range": seed_range,
                           "device": args.device, "orch": args.shm_eval_server,
                           "iter8_play": {"sims": ITER8_SIMS, "c_puct": ITER8_CPUCT,
                                          "residual_scale": ITER8_RESIDUAL_SCALE,
                                          "leaf": "v2_7"},
                           "handoff": "latched on first TILES decision with "
                                      "k_remaining<=K; k=len(deck)+(next_tile is not None)",
                           "v25_env": {k: os.environ.get(k) for k in
                                       ("CARCASSONNE_V25_CAP", "CARCASSONNE_V25_DROP_THREE_OPEN",
                                        "CARCASSONNE_USE_FLAT_LEAF", "CARCASSONNE_V25_VALUE_BLEND")}})

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"hybrid-handoff {args.agent_a} vs {args.agent_b}: n={args.n} | "
          f"{len(tasks)-len(todo)} cached, {len(todo)} to play, {workers} workers, "
          f"device={args.device}, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        # spawn: safe with CUDA in workers (fork+CUDA is unsafe). Net loaded per
        # worker in _worker_init (per-worker), OR attached over SHM (orch mode).
        ctx = get_context("spawn")
        id_q = None
        if args.shm_eval_server:
            id_q = ctx.Queue()
            for _w in range(workers):
                id_q.put(_w)
            print(f"  [orch] SHM eval-server '{args.shm_eval_server}': {workers} CPU "
                  f"workers attach to /dev/shm/carc_{args.shm_eval_server} (n_scalar={_ns})")
            sys.stdout.flush()
        with ctx.Pool(processes=workers, initializer=_worker_init,
                      initargs=(str(args.ckpt), args.device, need_net,
                                args.shared_claim, args.claim_host, args.claim_stale_secs,
                                args.shm_eval_server or "", id_q, _ns,
                                args.meeple_k_a, args.meeple_k_b)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r)
                done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, "
                          f"~{(len(todo)-done)*el/done/60:.0f} min left)")
                    sys.stdout.flush()
    for t in tasks:
        p = _result_path(out, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_seat == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    if results:
        summ = _summary(results, args.agent_a, args.agent_b)
        json.dump(summ, open(out / "summary.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
