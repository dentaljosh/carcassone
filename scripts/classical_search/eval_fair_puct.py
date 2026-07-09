#!/usr/bin/env python3
"""A2 — Fair (imperfect-information / PIMC) deployable-config eval for the
PUCT-with-heuristic-priors CHAMPION vs a fixed heuristic rung.

Pre-registration / roadmap: docs/PROGRAM_ROADMAP_2026-07-07.md item A2.

WHY: the production champion (HeuristicPriorAgent, c1.5/tau5/float/visits @ ~2750
sims; governance/PRODUCTION.yaml) as shipped plays CLAIRVOYANT — its NeuralMCTS
descends the engine's pre-shuffled TRUE deck, so it "sees" the upcoming tiles. Any
human/superhuman strength claim is graded on the DEPLOYABLE FAIR config: the same
champion under imperfect information (root-determinization PIMC). This script
derives that fair config and refreshes the stale iter8-only clairvoyance tax
(CL-022, ~26.6 elo) at the champion's OWN config.

THREE ARMS (--info), all vs the SAME fixed rung on the SAME decks so their paired
Δ isolates the one variable that changes:
  - fair     : FairHeuristicPriorAgent (fair PIMC prefix; k_dets determinizations per
               move, pooled-Q) — the deployable config. DEFAULT.
  - clair    : the clairvoyant champion (HeuristicPriorAgent on the true deck) — the
               as-shipped strength; the CL-022 CLAIR arm at champion config.
  - fair-net : the fair PIMC prefix with IDENTICAL heuristic priors but a LEARNED
               deck-aware net leaf value (C-cheap; needs --net <sighted ckpt>). vs the
               `fair` arm on the same decks it isolates the VALUE component: does a
               deck-aware learned value shrink the clairvoyance tax? (Gate: fair-elo
               of fair-net minus fair >= +35 elo; C_CHEAP_SPEC §4.) The priors are
               byte-identical to `fair` (make_heuristic_prior_evaluator_with_net_value).
ALL arms get the IDENTICAL fair MARGINALIZED exact endgame handoff (latched on the
first TILES decision with k_remaining<=K), so the only measured difference is the
SEARCH PREFIX (fair PIMC vs clairvoyant). The endgame is marginalized (honest
hidden-bag value), NOT clairvoyant — a clairvoyant K=3-4 solve would be the cheating
path and is intractable-fair anyway. tax = elo(clair) - elo(fair).

RUNG = HeuristicMCTS @ rung_sims (default 800, c=3.0, v2.9 Bmild_cap8 leaf) — the
CL-022 ruler (measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md "vs HeuristicMCTS
@ heur_sims=800, v2.7 leaf"), NO endgame (fixed yardstick).

EQUAL-WALL-CLOCK: the fair champion's total per-move search budget = k_dets*sims,
targeted at the deployed clairvoyant champion's ~2750 sims (default k_dets=8 *
sims=344 ~= 2752). The k_dets separate root expansions add a little fixed overhead,
so the fair arm gets a hair MORE compute than a single 2750 search — conservative
(if it still loses the tax, the tax is real).

GRID (docs/PROGRAM_ROADMAP A2): K in {2,4,8} (fair endgame handoff depth) x matched
sims. K=2 marginalized solves are RAM-safe; K>=3 marginalized is expensive (no
alpha-beta over chance nodes -> RAM/OOM regime) -> ATTENDED ONLY (see run_fair_grid.sh).

Pure CPU, net-free -> keep --workers <= threads, nice -n 19. CARCASSONNE_TT_CAP is
honored by the solver (env passthrough, recorded in the manifest).

Usage:
  # plumbing + K=2 handoff smoke (single process, tiny):
  nice -n 19 .venv/bin/python scripts/classical_search/eval_fair_puct.py \
      --info fair --exact-k 2 --k-dets 2 --sims 64 --games 2 --smoke

  # C-cheap fair-net plumbing smoke (RANDOM 81ch/42-scalar net, no training):
  nice -n 19 .venv/bin/python scripts/classical_search/eval_fair_puct.py \
      --info fair-net --exact-k 2 --k-dets 2 --sims 32 --games 2 --smoke

  # C-cheap fair-net A/B cell (n=100 deck-paired, vs the CL-045 fair baseline):
  CARCASSONNE_TT_CAP=200000 nice -n 19 .venv/bin/python -u \
      scripts/classical_search/eval_fair_puct.py \
      --info fair-net --net <sighted_value.pt> --exact-k 2 --k-dets 8 --sims 344 \
      --rung-sims 800 --n 100 --paired --seed-start 13000000000 --workers 14 \
      --out-root /mnt/c/carc-shared/classical_search --shared-claim --no-results-csv

  # one K=2 fair screen cell (n=100 deck-paired):
  CARCASSONNE_TT_CAP=200000 nice -n 19 .venv/bin/python -u \
      scripts/classical_search/eval_fair_puct.py \
      --info fair --exact-k 2 --k-dets 8 --sims 344 --rung-sims 800 \
      --n 100 --paired --seed-start 13000000000 --workers 14 \
      --out-root /mnt/c/carc-shared/classical_search --shared-claim --no-results-csv
"""
from __future__ import annotations

import os

# v2.9 Bmild_cap8 leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG
# reads these at import). Verbatim from eval_puct_priors.py / fair_agent_smoke.py.
_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

import argparse
import hashlib
import json
import math
import socket
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))  # endgame_solver

from carcassonne_ai import eval_provenance as ep  # noqa: E402
from carcassonne_ai.claim import try_claim as _try_claim  # noqa: E402
from carcassonne_ai.eval_provenance import deck_hash  # noqa: E402
from carcassonne_ai.fair_agent import (  # noqa: E402
    FairHeuristicPriorAgent,
    k_remaining,
)
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
)
from carcassonne_ai.mcts import DEFAULT_C, HeuristicMCTS  # noqa: E402
from carcassonne_ai.run_manifest import code_rev, game_tag, write_manifest  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

import endgame_solver as S  # noqa: E402

try:
    from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
    _TILES_PHASE = GamePhase.TILES
except Exception:  # pragma: no cover
    _TILES_PHASE = None


# --------------------------------------------------------------------------- #
# C-cheap deck-aware NET value (the `fair-net` arm). torch + CarcassonneNet are   #
# imported lazily (only this arm needs them) so the fair/clair arms keep their    #
# net-free, torch-free startup.                                                   #
# --------------------------------------------------------------------------- #
def _load_net(path, device="cpu"):
    """Load a sighted (81ch/42-scalar) CarcassonneNet checkpoint for value read-out.
    Mirrors verify_sighted_orch_parity._load_net (arch dims live in the ckpt)."""
    import torch
    from carcassonne_ai.network import CarcassonneNet
    ck = torch.load(path, map_location=device, weights_only=False)
    n_ch = int(ck.get("n_input_channels", 78))
    n_scalar = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(
        n_filters=ck.get("n_filters", 96), n_blocks=ck.get("n_blocks", 6),
        n_input_channels=n_ch, n_scalar_features=n_scalar,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.eval()
    if n_ch != 81 or n_scalar != 42 or not bool(ck.get("sighted", False)):
        print(f"[warn] --net is not an 81ch/42-scalar sighted net "
              f"(n_ch={n_ch} n_scalar={n_scalar} sighted={ck.get('sighted')}); "
              "the deck-aware fair-net arm expects the sighted rep.", file=sys.stderr)
    return net


def _random_sighted_net(device="cpu", value_global_pool=True, seed=0):
    """A randomly-initialized 81ch/42-scalar sighted net — the --smoke plumbing
    net (proves the fair-net path end-to-end without any training)."""
    import torch
    from carcassonne_ai.network import CarcassonneNet
    torch.manual_seed(seed)
    net = CarcassonneNet(
        n_input_channels=81, n_scalar_features=42,
        value_global_pool=value_global_pool,
    ).to(device)
    net.eval()
    return net

EVAL_ROOT = REPO / "data" / "classical_search"
RUNG_C = DEFAULT_C  # 3.0 — the CL-022 rung's HeuristicMCTS exploration constant
EXACT_BUDGET = int(os.environ.get("CARCASSONNE_EXACT_BUDGET", "2000000"))


# --------------------------------------------------------------------------- #
# Marginalized (FAIR) endgame handoff — mirrors eval_puct_priors._ExactHandoff  #
# but mode="marginalized"/alphabeta=False (the honest hidden-bag solve). Shared  #
# by BOTH the fair and clair champion arms so the endgame is identical and the   #
# clairvoyance tax isolates the search PREFIX. Generalized over the prefix agent #
# (`.move(board) -> int`).                                                       #
# --------------------------------------------------------------------------- #
class _MarginalizedHandoff:
    def __init__(self, prefix, game_plain, K: int, budget: int = EXACT_BUDGET):
        self._prefix = prefix
        self._game = game_plain
        self._K = int(K)
        self._budget = budget
        self._latched = False
        self.latch_k = None
        self.prefix_moves = 0
        self.exact_moves = 0
        self.n_timeouts = 0
        self.solver_secs = 0.0
        self.solver_nodes = 0
        self.max_solve_secs = 0.0
        self.prefix_secs = 0.0

    def _should_latch(self, state) -> bool:
        return (self._K > 0 and _TILES_PHASE is not None
                and state.phase == _TILES_PHASE and k_remaining(state) <= self._K)

    def move(self, board) -> int:
        if not self._latched and self._should_latch(board.state):
            self._latched = True
            self.latch_k = k_remaining(board.state)
        if not self._latched:
            t0 = time.perf_counter()
            mv = int(self._prefix.move(board))
            self.prefix_secs += time.perf_counter() - t0
            self.prefix_moves += 1
            return mv
        t0 = time.perf_counter()
        try:
            res = S.solve(self._game, board, mode="marginalized",
                          budget=self._budget, alphabeta=False)
            dt = time.perf_counter() - t0
            self.solver_secs += dt
            self.max_solve_secs = max(self.max_solve_secs, dt)
            self.solver_nodes += res.nodes
            self.exact_moves += 1
            return int(min(res.optimal_actions))
        except S.BudgetExceeded:
            # Marginalized solve too big at this K: fall back to the FAIR prefix
            # for THIS decision only (stays latched, retries next ply).
            self.solver_secs += time.perf_counter() - t0
            self.n_timeouts += 1
            t1 = time.perf_counter()
            mv = int(self._prefix.move(board))
            self.prefix_secs += time.perf_counter() - t1
            self.prefix_moves += 1
            return mv


class _RungPrefix:
    """Fixed rung: HeuristicMCTS @ rung_sims, c=3.0, v2.9 Bmild_cap8 leaf. NO
    endgame handoff (the CL-022 yardstick convention)."""

    def __init__(self, game, sims, seed, leaf_cfg):
        self._m = HeuristicMCTS(game=game, simulations=sims, c=RUNG_C, seed=seed,
                                heur_leaf="v2_7", leaf_cfg=leaf_cfg)

    def move(self, board) -> int:
        self._m.clear()
        return int(self._m.best_action(board))


def _build_champ_cfg(c_puct, tau_p, leaf_quantize, final_select, value_norm):
    return HeuristicPriorConfig(
        c_puct=c_puct, tau_p=tau_p, leaf_quantize=leaf_quantize,
        final_select=final_select, value_norm=value_norm, leaf_cfg=DEFAULT_CONFIG,
    )


def _make_champion(info, cfg, sims, k_dets, K, seed, game, net=None):
    """Build the champion side, wrapped in the fair marginalized endgame at K.

    info=="fair"     -> FairHeuristicPriorAgent prefix (fair PIMC, endgame OFF here —
                        the _MarginalizedHandoff owns the endgame so both arms share it).
    info=="fair-net" -> FairHeuristicPriorAgent prefix with IDENTICAL heuristic priors
                        but the learned deck-aware net value (C-cheap). Same fair PIMC
                        + shared endgame as `fair`; ONLY the leaf value differs.
    info=="clair"    -> HeuristicPriorAgent prefix (clairvoyant PUCT on the true deck)."""
    if info == "fair":
        prefix = FairHeuristicPriorAgent(game, cfg, sims=sims, k_dets=k_dets,
                                         seed=seed, exact_endgame=False)
    elif info == "fair-net":
        if net is None:
            raise ValueError("info=fair-net requires a loaded net (--net)")
        prefix = FairHeuristicPriorAgent(game, cfg, sims=sims, k_dets=k_dets,
                                         seed=seed, exact_endgame=False, net=net)
    else:  # clair
        prefix = HeuristicPriorAgent(game, cfg, simulations=(sims * k_dets), seed=seed)
    return _MarginalizedHandoff(prefix, Game(enable_legal_moves_cache=True), K)


def _leaf_hash(cfg) -> str:
    payload = {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(cfg).items()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
@dataclass
class GameResult:
    seed: int
    a_seat: int            # seat the CHAMPION plays this game
    info: str              # fair | clair
    exact_k: int
    k_dets: int
    sims: int
    rung_sims: int
    score_p0: int
    score_p1: int
    diff: int              # champion - rung
    won_by_champ: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""
    # champion instrumentation
    champ_prefix_moves: int = 0
    champ_exact_moves: int = 0
    champ_prefix_secs: float = 0.0
    champ_solver_secs: float = 0.0
    champ_timeouts: int = 0
    # rung instrumentation
    rung_moves: int = 0
    rung_secs: float = 0.0
    latch_k: int | None = None


def _result_path(out: Path, seed: int, a_seat: int) -> Path:
    return out / f"seed{seed:012d}_a{a_seat}.json"


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


_W: dict = {}


def _worker_init(info, champ_cfg_dict, sims, k_dets, exact_k, rung_sims,
                 shared_claim, claim_host, claim_stale, net_ckpt=None):
    _W["info"] = info
    _W["champ_cfg_dict"] = champ_cfg_dict
    _W["sims"] = sims
    _W["k_dets"] = k_dets
    _W["exact_k"] = exact_k
    _W["rung_sims"] = rung_sims
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["claim_stale"] = claim_stale
    # fair-net: each worker loads its OWN net-on-CPU copy (the eval env hides CUDA;
    # a 7M net is ~30MB/worker). Loaded once per process, reused across games.
    _W["net"] = _load_net(net_ckpt, device="cpu") if (info == "fair-net" and net_ckpt) else None


def _cfg_from_dict(d):
    return _build_champ_cfg(d["c_puct"], d["tau_p"], d["leaf_quantize"],
                            d["final_select"], d["value_norm"])


def _play_one(args) -> GameResult | None:
    out_str, seed, a_seat = args
    out = Path(out_str)
    p = _result_path(out, seed, a_seat)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None

    import random
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)  # referee / deck driver
    board = game.get_init_board()
    dh = deck_hash(board)

    cfg = _cfg_from_dict(_W["champ_cfg_dict"])
    champ = _make_champion(_W["info"], cfg, _W["sims"], _W["k_dets"], _W["exact_k"],
                           seed, Game(enable_legal_moves_cache=True), net=_W.get("net"))
    rung = _RungPrefix(Game(enable_legal_moves_cache=True), _W["rung_sims"],
                       seed + 1, DEFAULT_CONFIG)

    t0 = time.perf_counter()
    moves = 0
    rung_moves = 0
    rung_secs = 0.0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == a_seat:
            action = champ.move(board)
        else:
            r0 = time.perf_counter()
            action = rung.move(board)
            rung_secs += time.perf_counter() - r0
            rung_moves += 1
        board, _ = game.get_next_state(board, action)
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    r = GameResult(
        seed=seed, a_seat=a_seat, info=_W["info"], exact_k=_W["exact_k"],
        k_dets=_W["k_dets"], sims=_W["sims"], rung_sims=_W["rung_sims"],
        score_p0=int(s0), score_p1=int(s1), diff=int(diff),
        won_by_champ=(diff > 0), drew=(diff == 0), elapsed_s=round(elapsed, 3),
        moves=moves, deck_hash=dh,
        champ_prefix_moves=champ.prefix_moves, champ_exact_moves=champ.exact_moves,
        champ_prefix_secs=round(champ.prefix_secs, 3),
        champ_solver_secs=round(champ.solver_secs, 3),
        champ_timeouts=champ.n_timeouts,
        rung_moves=rung_moves, rung_secs=round(rung_secs, 3),
        latch_k=champ.latch_k,
    )
    _save(p, r)
    return r


# --------------------------------------------------------------------------- #
def _paired_z(results):
    """Paired z on per-deck seat-balanced margin (= eval_puct_priors._paired_z)."""
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


def _summary(results, info, exact_k, k_dets, sims, rung_sims):
    n = len(results)
    w = sum(1 for r in results if r.won_by_champ)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    avg = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    wr_se = math.sqrt(0.25 / n)
    wr_z = (wr - 0.5) / wr_se if wr_se > 0 else float("nan")
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    mean_d, z, npair = _paired_z(results)
    champ_latched = sum(1 for r in results if r.champ_exact_moves > 0)
    champ_ms = (sum(r.champ_prefix_secs for r in results) /
                max(1, sum(r.champ_prefix_moves for r in results))) * 1e3
    rung_ms = (sum(r.rung_secs for r in results) /
               max(1, sum(r.rung_moves for r in results))) * 1e3
    solver_pergame = sum(r.champ_solver_secs for r in results) / n
    print()
    print(f"=== FAIR-PUCT[{info}] (K={exact_k}, k_dets={k_dets}, sims={sims}, "
          f"total~{k_dets * sims}) vs HeuristicMCTS(h{rung_sims}) ===")
    print(f"games: {n}   champion: {w}W / {d}D / {losses}L   winrate {wr:.3f} (z={wr_z:+.2f})")
    print(f"avg score diff (champ - rung): {avg:+.2f}")
    print(f"ELO: {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    if mean_d is not None:
        print(f"PAIRED: {npair} decks   mean seat-balanced margin {mean_d:+.2f}   z = {z:+.2f}")
    print(f"prefix ms/move: champion {champ_ms:.0f}  rung {rung_ms:.0f}  "
          f"(ratio {champ_ms/max(1e-9,rung_ms):.2f}x)")
    print(f"fair endgame: latched {champ_latched}/{n} games, {solver_pergame:.2f}s solver/game, "
          f"timeouts={sum(r.champ_timeouts for r in results)}")
    if abs(elo) <= 35 and not math.isnan(elo_sig):
        print(f"  POWER NOTE: |elo|<=35 at n={n} (1σ≈±{elo_sig:.0f}); a >=35-elo verdict needs n>=400.")
    return {
        "info": info, "exact_k": exact_k, "k_dets": k_dets, "sims": sims,
        "total_sims": k_dets * sims, "rung_sims": rung_sims,
        "n": n, "W": w, "D": d, "L": losses, "winrate": wr, "winrate_z": wr_z,
        "elo": elo, "elo_sig_1sigma": elo_sig, "avg_diff": avg,
        "paired_mean_margin": mean_d, "paired_z": z, "n_paired": npair,
        "champ_prefix_ms_per_move": champ_ms, "rung_ms_per_move": rung_ms,
        "champ_latched_games": champ_latched, "solver_secs_per_game": solver_pergame,
        "champ_timeouts": sum(r.champ_timeouts for r in results),
    }


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))
    return work


# --------------------------------------------------------------------------- #
def _smoke(args) -> int:
    """Single-process plumbing + fair-handoff-fires proof: play `games` paired
    games, print move/handoff counts, assert the fair marginalized endgame fired,
    and print an elo/z summary. Exits 0 on success."""
    cfg = _build_champ_cfg(args.c_puct, args.tau_p, args.leaf_quantize,
                           args.final_select, args.value_norm)
    # fair-net smoke: load --net if given, else a randomly-initialized 81ch/42-scalar
    # net (pure plumbing proof — NO training). Other arms ignore the net.
    smoke_net = None
    if args.info == "fair-net":
        smoke_net = (_load_net(args.net, device="cpu") if args.net
                     else _random_sighted_net(device="cpu",
                                              value_global_pool=args.value_global_pool))
        print(f"[smoke] fair-net value = {'ckpt ' + args.net if args.net else 'RANDOM'} "
              f"81ch/42-scalar net (value_global_pool={args.value_global_pool})")
    print(f"[smoke] info={args.info} K={args.exact_k} k_dets={args.k_dets} sims={args.sims} "
          f"(total~{args.k_dets*args.sims}) | rung h{args.rung_sims} c{RUNG_C}")
    import random
    results = []
    t0 = time.perf_counter()
    for i in range(max(1, args.games)):
        a_seat = i % 2
        seed = args.seed_start + (i // 2)
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        dh = deck_hash(board)
        champ = _make_champion(args.info, cfg, args.sims, args.k_dets, args.exact_k,
                               seed, Game(enable_legal_moves_cache=True), net=smoke_net)
        rung = _RungPrefix(Game(enable_legal_moves_cache=True), args.rung_sims,
                           seed + 1, DEFAULT_CONFIG)
        moves = 0
        rung_moves = 0
        rung_secs = 0.0
        while game.get_game_ended(board, 0) == 0.0:
            cur = board.state.current_player
            mask = game.get_valid_moves(board)
            if cur == a_seat:
                act = champ.move(board)
            else:
                r0 = time.perf_counter()
                act = rung.move(board)
                rung_secs += time.perf_counter() - r0
                rung_moves += 1
            assert mask[act], f"illegal action {act}"
            board, _ = game.get_next_state(board, act)
            moves += 1
        s0, s1 = board.state.scores
        diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
        results.append(GameResult(
            seed=seed, a_seat=a_seat, info=args.info, exact_k=args.exact_k,
            k_dets=args.k_dets, sims=args.sims, rung_sims=args.rung_sims,
            score_p0=int(s0), score_p1=int(s1), diff=int(diff),
            won_by_champ=(diff > 0), drew=(diff == 0), elapsed_s=0.0, moves=moves,
            deck_hash=dh, champ_prefix_moves=champ.prefix_moves,
            champ_exact_moves=champ.exact_moves, champ_prefix_secs=champ.prefix_secs,
            champ_solver_secs=champ.solver_secs, champ_timeouts=champ.n_timeouts,
            rung_moves=rung_moves, rung_secs=rung_secs, latch_k=champ.latch_k))
        print(f"[smoke] a_seat={a_seat}: {s0}-{s1} diff(champ-rung)={diff:+d} moves={moves} | "
              f"champ prefix/exact={champ.prefix_moves}/{champ.exact_moves} "
              f"latch_k={champ.latch_k} solver={champ.solver_secs:.2f}s to={champ.n_timeouts}")
        if args.exact_k > 0:
            assert champ.exact_moves > 0, \
                "champion never reached the fair exact endgame (K too small / rung got all the endgames?)"
        assert champ.prefix_moves > 0, "prefix search never ran (K too big?)"

    summ = _summary(results, args.info, args.exact_k, args.k_dets, args.sims, args.rung_sims)
    if args.out_root:
        out = Path(args.out_root) / (args.out_subdir or "fair_smoke_k2")
        out.mkdir(parents=True, exist_ok=True)
        json.dump(summ, open(out / "summary.json", "w"), indent=2)
        print(f"[smoke] wrote {out/'summary.json'}")
    print(f"[smoke] OK — fair plumbing + marginalized endgame verified "
          f"({time.perf_counter()-t0:.1f}s for {len(results)} games)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_fair_puct")
    ap.add_argument("--info", choices=("fair", "clair", "fair-net"), default="fair",
                    help="fair = FairHeuristicPriorAgent PIMC (deployable, default); "
                         "clair = clairvoyant champion (CL-022 CLAIR arm at champion config); "
                         "fair-net = fair PIMC with IDENTICAL heuristic priors but a learned "
                         "deck-aware net leaf value (C-cheap; needs --net)")
    ap.add_argument("--net", type=str, default=None,
                    help="fair-net arm: path to the sighted (81ch/42-scalar) value-net "
                         "checkpoint. Under --smoke this may be omitted (a random net is used).")
    ap.add_argument("--value-global-pool", action="store_true", default=True,
                    help="fair-net --smoke random net: build with KataGo-style value global "
                         "pooling (the recommended C-cheap arch; default True)")
    ap.add_argument("--no-value-global-pool", dest="value_global_pool", action="store_false")
    ap.add_argument("--exact-k", type=int, default=2,
                    help="fair marginalized endgame handoff at k_remaining<=K (the A2 grid axis)")
    ap.add_argument("--k-dets", type=int, default=8, help="determinizations per move (fair PIMC)")
    ap.add_argument("--sims", type=int, default=344, help="PUCT sims per determinization")
    ap.add_argument("--rung-sims", type=int, default=800, help="fixed HeuristicMCTS rung sims (CL-022=800)")
    # champion knobs (governance/PRODUCTION.yaml defaults)
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--tau-p", type=float, default=5.0)
    ap.add_argument("--leaf-quantize", choices=("int", "float"), default="float")
    ap.add_argument("--final-select", choices=("Q", "visits", "lcb"), default="visits")
    ap.add_argument("--value-norm", type=float, default=15.0)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--games", type=int, default=None, help="alias for --n (convenience)")
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=13_000_000_000)
    ap.add_argument("--allow-selfplay-seeds", action="store_true")
    ap.add_argument("--out-root", type=str, default=None)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=7200)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--no-results-csv", action="store_true",
                    help="do not append to experiments/results.csv (this eval NEVER writes it; "
                         "flag kept for launcher symmetry / explicit intent)")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args(argv)
    if args.games is not None:
        args.n = args.games
    if args.k_dets < 1:
        ap.error("--k-dets must be >= 1")
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n")

    if args.smoke:
        return _smoke(args)

    if args.info == "fair-net" and not args.net:
        ap.error("--info fair-net requires --net <sighted checkpoint> (except under --smoke)")

    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    cfg = _build_champ_cfg(args.c_puct, args.tau_p, args.leaf_quantize,
                           args.final_select, args.value_norm)
    champ_cfg_dict = {"c_puct": args.c_puct, "tau_p": args.tau_p,
                      "leaf_quantize": args.leaf_quantize,
                      "final_select": args.final_select, "value_norm": args.value_norm}

    tag = (f"fair_{args.info}_c{args.c_puct:g}_tau{args.tau_p:g}_{args.leaf_quantize}"
           f"_kd{args.k_dets}_s{args.sims}_vs_h{args.rung_sims}_k{args.exact_k}")
    sub = args.out_subdir or tag
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    tasks = [(str(out), seed, a_seat)
             for seed, a_seat in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, t[1], t[2]))) is not None]
        if results:
            summ = _summary(results, args.info, args.exact_k, args.k_dets, args.sims, args.rung_sims)
            json.dump(summ, open(out / "summary.json", "w"), indent=2)
        else:
            print("no cached results yet")
        return 0

    leaf_cfg = cfg.resolved_leaf_cfg()
    _AGENT_NAME = {
        "fair": "FairHeuristicPriorAgent",
        "fair-net": "FairHeuristicPriorAgent + deck-aware net value (C-cheap)",
        "clair": "HeuristicPriorAgent (clairvoyant)",
    }
    man_cfg = {
        "info": args.info,
        "champion": {"agent": _AGENT_NAME[args.info],
                     **cfg.as_manifest(),
                     "k_dets": args.k_dets, "sims_per_det": args.sims,
                     "total_sims": args.k_dets * args.sims,
                     "net": (args.net if args.info == "fair-net" else None),
                     "value_source": ("learned deck-aware net (sighted 81ch/42-scalar)"
                                      if args.info == "fair-net" else "v2.9 heuristic leaf"),
                     "aggregation": ("single clairvoyant search (final_select)" if args.info == "clair"
                                     else "pooled-Q over k_dets determinizations (final_select inert)")},
        "endgame": {"mode": "marginalized", "exact_k": args.exact_k,
                    "exact_budget": EXACT_BUDGET, "shared_by_both_arms": True,
                    "tt_cap": os.environ.get("CARCASSONNE_TT_CAP")},
        "rung": {"agent": "HeuristicMCTS", "heur_leaf": "v2_7", "c": RUNG_C,
                 "sims": args.rung_sims, "endgame": None,
                 "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)",
                 "provenance": "CL-022 ruler (CLAIRVOYANCE_GAP_VERDICT.md, h800 v2.7)"},
        "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
        "leaf_hash": _leaf_hash(leaf_cfg), "code_rev": code_rev(),
        "equal_wall_clock_note": ("champion total per-move budget k_dets*sims targets the "
                                  "deployed clairvoyant champion ~2750 sims (equal wall-clock; "
                                  "k_dets root expansions add a little fixed overhead)"),
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
    }
    write_manifest(out, kind="eval_fair_puct", game=game_tag(Game()),
                   config=man_cfg, overwrite=True)

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"fair-puct[{tag}]: info={args.info} n={args.n} paired={args.paired} K={args.exact_k} "
          f"k_dets={args.k_dets} sims={args.sims} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        with Pool(processes=workers, initializer=_worker_init,
                  initargs=(args.info, champ_cfg_dict, args.sims, args.k_dets,
                            args.exact_k, args.rung_sims, args.shared_claim,
                            args.claim_host, args.claim_stale_secs, args.net)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r)
                done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, "
                          f"~{(len(todo)-done)*el/done/60:.0f} min left)", flush=True)
    for t in tasks:
        p = _result_path(out, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_seat == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    if not results:
        print("no results")
        return 0
    summ = _summary(results, args.info, args.exact_k, args.k_dets, args.sims, args.rung_sims)
    json.dump(summ, open(out / "summary.json", "w"), indent=2)
    print(f"[summary.json] wrote {out/'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
