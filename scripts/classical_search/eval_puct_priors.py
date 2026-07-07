#!/usr/bin/env python3
"""Phase 1.1 deck-paired A/B: PUCT-with-heuristic-priors (candidate) vs the
production champion (HeuristicMCTS @ h6400 + exact-K endgame), search-only.

Pre-registration: measurement/classical_search/PLAN.md (H1.1).

Both sides are CLAIRVOYANT (descend the true deck) — this is an internal
algorithm A/B, matched-mode per the plan. Deck-paired: the same shuffled deck is
played from both seats (seats swapped), so the paired-margin z removes deck
variance. BOTH sides get the IDENTICAL exact-K<=4 clairvoyant endgame handoff
(latched on the first TILES decision with k_remaining<=K), so the ONLY difference
measured is the SEARCH prefix: PUCT+heuristic-priors (candidate) vs
random-expansion UCT h6400 (champion). The exact tail is leaf-independent (true
terminal score), so it cannot bias the comparison.

Candidate = HeuristicPriorAgent(c_puct, tau_p, leaf_quantize, final_select) @ cand_sims.
Champion  = HeuristicMCTS(heur_leaf="v2_7", c=3.0) @ champ_sims (default 6400),
            leaf = env-built v2.9 Bmild_cap8 (DEFAULT_CONFIG).

Pure CPU, net-free (no GPU/orchestrator) -> keep --workers <= threads, nice -n 19.

Usage:
  # plumbing + handoff smoke (single process, fast):
  nice -n 19 .venv/bin/python scripts/classical_search/eval_puct_priors.py \
      --c-puct 1.5 --tau-p 5 --cand-sims 800 --exact-k 2 --games 4 --smoke

  # one screen cell (n=100 deck-paired), the sweep launches these across boxes:
  nice -n 19 .venv/bin/python -u scripts/classical_search/eval_puct_priors.py \
      --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select Q \
      --cand-sims 800 --champ-sims 6400 --exact-k 4 --n 100 --paired \
      --seed-start 9000000000 --workers 14 \
      --out-root /mnt/c/carc-shared/classical_search --shared-claim

Phase 1.1b transitivity round-robin (measurement/classical_search/ROUND_ROBIN_PLAN.md)
adds two OPTIONAL flags (legacy invocations are byte-identical without them):
  --candidate {puct|h<sims>}   h<sims> = plain HeuristicMCTS candidate (same v2.9 leaf
                               + exact-K handoff as the champion side); puct = default.
  --opponent {h<sims>|net:<ckpt.pt>}
                               h<sims> = HeuristicMCTS opponent (+ exact-K handoff).
                               net:<ckpt> = NeuralMCTS opponent, play knobs PINNED to
                               the rod_v2 anchor harness (scripts/level2/
                               eval_hybrid_handoff.py ITER8_*): sims=200, c_puct=3.0,
                               v2.9 leaf + residual_scale=0.25, BARE (no exact tail —
                               the anchor rows were played bare). Net-on-CPU per worker
                               by default; pass --shm-eval-server <NAME> to attach the
                               workers to a running carc-orch SHM orchestrator.
  New-flag cells get rr_* out-subdirs (e.g. rr_puct2750_vs_net-iter02_k2); seat pairing,
  deck seeds, claims, aggregation and summary.json ride the existing machinery.
"""
from __future__ import annotations

import os

# v2.9 Bmild_cap8 leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG
# reads these at import). Matches production / scripts/bench_phone_budget.py.
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
import csv
import dataclasses as dc
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
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
)
from carcassonne_ai.mcts import HeuristicMCTS  # noqa: E402
from carcassonne_ai.run_manifest import code_rev, game_tag, write_manifest  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

import endgame_solver as S  # noqa: E402

try:
    from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
    _TILES_PHASE = GamePhase.TILES
except Exception:  # pragma: no cover
    _TILES_PHASE = None

EVAL_ROOT = REPO / "data" / "classical_search"
CHAMP_C = 3.0  # production UCT exploration constant for HeuristicMCTS
EXACT_BUDGET = int(os.environ.get("CARCASSONNE_EXACT_BUDGET", "2000000"))

# Neural-opponent play knobs — PINNED to the rod_v2 anchor construction
# (scripts/level2/eval_hybrid_handoff.py: ITER8_SIMS / ITER8_CPUCT /
# ITER8_RESIDUAL_SCALE + _make_iter8_mcts), the harness behind the rod_v2 iter_02
# anchor rows (results.csv rodv2_iter02_vs_heur6400_v29_n200 /
# rodv2_iter02_vs_heur3200_v29_n200, launched via scripts/rod_v2/run_heur_eval_v29.sh).
# NET_MEEPLE_K matches that wrapper's --meeple-k-a 2.0 (inert under the v2.9 curve —
# the curve replaces the flat term — kept for byte-parity with the anchor harness).
NET_SIMS = 200
NET_CPUCT = 3.0
NET_RESIDUAL_SCALE = 0.25
NET_MEEPLE_K = 2.0
NET_N_CH = 78   # iter_02-family input planes; MUST match the orch server export (n_ch=78)


# --------------------------------------------------------------------------- #
# Handoff (mirrors scripts/level2/eval_hybrid_handoff._ExactAgent, generalized  #
# over the prefix agent so BOTH sides share the SAME exact-K endgame).          #
# --------------------------------------------------------------------------- #
def k_remaining(state) -> int:
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def _should_latch(state, K: int) -> bool:
    """Latch on the first TILES-phase decision with k_remaining<=K (turn-atomic,
    one-way: k is monotone non-increasing). IDENTICAL trigger to eval_hybrid_handoff."""
    return (_TILES_PHASE is not None and state.phase == _TILES_PHASE
            and k_remaining(state) <= K)


class _ExactHandoff:
    """A prefix agent, then EXACT clairvoyant-solver play once latched.

    `prefix` is any object exposing `.move(board) -> int` (candidate or champion).
    Latching + timeout-fallback semantics match eval_hybrid_handoff._ExactAgent:
    on BudgetExceeded the prefix plays THAT move (stays latched, retries next ply)."""

    def __init__(self, prefix, game_plain, K: int, budget: int = EXACT_BUDGET):
        self._prefix = prefix
        self._game = game_plain
        self._K = K
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

    def move(self, board) -> int:
        if not self._latched and _should_latch(board.state, self._K):
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
            res = S.solve(self._game, board, mode="clairvoyant",
                          budget=self._budget, alphabeta=True)
            dt = time.perf_counter() - t0
            self.solver_secs += dt
            self.max_solve_secs = max(self.max_solve_secs, dt)
            self.solver_nodes += res.nodes
            self.exact_moves += 1
            return int(min(res.optimal_actions))
        except S.BudgetExceeded:
            self.solver_secs += time.perf_counter() - t0
            self.n_timeouts += 1
            t1 = time.perf_counter()
            mv = int(self._prefix.move(board))
            self.prefix_secs += time.perf_counter() - t1
            self.prefix_moves += 1
            return mv


class _ChampPrefix:
    """Champion prefix: HeuristicMCTS(heur_leaf='v2_7') @ champ_sims, c=3.0."""

    def __init__(self, game, sims, seed, leaf_cfg):
        self._m = HeuristicMCTS(game=game, simulations=sims, c=CHAMP_C, seed=seed,
                                heur_leaf="v2_7", leaf_cfg=leaf_cfg)

    def move(self, board) -> int:
        self._m.clear()
        return int(self._m.best_action(board))


# --------------------------------------------------------------------------- #
# Round-robin extension: candidate/opponent specs + the neural opponent         #
# (measurement/classical_search/ROUND_ROBIN_PLAN.md). Torch is imported lazily  #
# so the legacy pure-CPU cells never pay for it.                                #
# --------------------------------------------------------------------------- #
def _parse_candidate(tok: str):
    """'puct' -> ("puct", None); 'h<sims>' -> ("heur", sims)."""
    tok = tok.strip()
    if tok == "puct":
        return ("puct", None)
    if tok.startswith("h") and tok[1:].isdigit() and int(tok[1:]) > 0:
        return ("heur", int(tok[1:]))
    raise ValueError(f"bad --candidate {tok!r}; expected puct|h<sims> (e.g. h6400)")


def _parse_opponent(tok: str):
    """'h<sims>' -> ("heur", sims, None); 'net:<ckpt>' -> ("net", NET_SIMS, path)."""
    tok = tok.strip()
    if tok.startswith("net:"):
        path = tok[len("net:"):]
        if not path:
            raise ValueError("net: opponent needs a checkpoint path (net:/abs/iter.pt)")
        return ("net", NET_SIMS, path)
    if tok.startswith("h") and tok[1:].isdigit() and int(tok[1:]) > 0:
        return ("heur", int(tok[1:]), None)
    raise ValueError(f"bad --opponent {tok!r}; expected h<sims>|net:<ckpt.pt>")


def _resolve_specs(args):
    """Resolve --candidate/--opponent -> (cand_kind, opp_kind, opp_sims, net_ckpt,
    new_mode). Sets args.cand_sims from an h<sims> candidate token (the token wins).
    Raises ValueError on a bad/missing spec (callers map it to an argparse error)."""
    cand_kind, cand_tok_sims = _parse_candidate(args.candidate)
    if cand_kind == "heur":
        args.cand_sims = cand_tok_sims
    elif args.cand_sims is None:
        raise ValueError("--cand-sims is required for --candidate puct")
    if args.opponent is None:
        opp_kind, opp_sims, net_ckpt = "heur", args.champ_sims, None
    else:
        opp_kind, opp_sims, net_ckpt = _parse_opponent(args.opponent)
    new_mode = (args.candidate != "puct") or (args.opponent is not None)
    return cand_kind, opp_kind, opp_sims, net_ckpt, new_mode


def _cell_tag(args, cand_kind, opp_kind, opp_sims, net_ckpt, new_mode) -> str:
    """Out-subdir cell tag. LEGACY invocations (no --candidate/--opponent) keep the
    historical naming byte-identical; round-robin invocations get rr_* names
    (e.g. rr_puct2750_vs_net-iter02_k2, rr_h6400_vs_h12800_k2)."""
    if not new_mode:
        return (f"puct_c{args.c_puct:g}_tau{args.tau_p:g}_{args.leaf_quantize}_{args.final_select}"
                f"_s{args.cand_sims}_vs_h{args.champ_sims}_k{args.exact_k}")
    cand_tok = f"puct{args.cand_sims}" if cand_kind == "puct" else f"h{args.cand_sims}"
    opp_tok = (f"h{opp_sims}" if opp_kind == "heur"
               else "net-" + Path(net_ckpt).stem.replace("_", ""))
    return f"rr_{cand_tok}_vs_{opp_tok}_k{args.exact_k}"


class _NetPrefix:
    """Neural opponent prefix: NeuralMCTS @ NET_SIMS, c_puct=NET_CPUCT, priors+value
    from the net with the value replaced by the v2.9 leaf + net-value residual at
    NET_RESIDUAL_SCALE. Construction mirrors eval_hybrid_handoff._make_iter8_mcts
    (the rod_v2 anchor) byte-for-byte: dataclasses.replace(DEFAULT_CONFIG,
    residual_scale, meeple_k) -> make_v25_value_wrapper -> NeuralMCTS."""

    def __init__(self, base_eval, game_farm, seed):
        from carcassonne_ai.evaluators import make_v25_value_wrapper
        from carcassonne_ai.mcts import NeuralMCTS
        cfg = dc.replace(DEFAULT_CONFIG, residual_scale=NET_RESIDUAL_SCALE,
                         meeple_k=NET_MEEPLE_K)
        leaf = make_v25_value_wrapper(base_eval, cfg)
        self._m = NeuralMCTS(game=game_farm, evaluator=leaf, simulations=NET_SIMS,
                             seed=seed, c_puct=NET_CPUCT)

    def move(self, board) -> int:
        self._m.clear()
        return int(self._m.best_action(board))


def _read_ckpt_meta(ckpt_path: str) -> dict:
    """Checkpoint architecture metadata (parent-side; needed for SHM connect width,
    the farm-scalar flag and the manifest)."""
    import torch
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    meta = {"n_filters": int(ck["n_filters"]), "n_blocks": int(ck["n_blocks"]),
            "n_scalar_features": int(ck.get("n_scalar_features", 10)),
            "value_global_pool": bool(ck.get("value_global_pool", False))}
    del ck
    return meta


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_net_cpu(ckpt_path: str):
    """Load the checkpoint into a CPU CarcassonneNet (eval mode). Mirrors
    eval_hybrid_handoff._worker_init's non-orch path. -> (net, device, n_scalar)."""
    import torch
    from carcassonne_ai.network import CarcassonneNet
    torch.set_num_threads(1)
    dev = torch.device("cpu")
    ck = torch.load(ckpt_path, map_location=dev, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    return net, dev, ns


def _make_net_prefix(seed: int) -> "_NetPrefix":
    """Per-game neural opponent from worker state: fresh farm-width Game + a base
    evaluator over the worker's local CPU net OR its carc-orch SHM handles."""
    farm = _W["net_ns"] > 10
    gf = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    if _W.get("net_handles") is not None:
        from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
        base = make_remote_single_evaluator(_W["net_handles"], gf)
    else:
        from carcassonne_ai.evaluators import make_single_evaluator
        base = make_single_evaluator(_W["net"], _W["net_dev"], gf)
    return _NetPrefix(base, gf, seed)


def _leaf_hash(cfg) -> str:
    """Stable short hash of the resolved LeafConfig (provenance)."""
    payload = {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(cfg).items()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
@dataclass
class GameResult:
    seed: int
    a_seat: int            # seat the CANDIDATE plays this game
    cand_sims: int
    champ_sims: int
    score_p0: int
    score_p1: int
    diff: int              # candidate - champion
    won_by_cand: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""
    # per-side instrumentation
    cand_prefix_moves: int = 0
    cand_exact_moves: int = 0
    cand_prefix_secs: float = 0.0
    cand_solver_secs: float = 0.0
    cand_timeouts: int = 0
    champ_prefix_moves: int = 0
    champ_exact_moves: int = 0
    champ_prefix_secs: float = 0.0
    champ_solver_secs: float = 0.0
    champ_timeouts: int = 0
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


def _worker_init(cand_cfg_dict, cand_sims, champ_sims, exact_k,
                 shared_claim, claim_host, claim_stale,
                 cand_kind="puct", opp_kind="heur", opp_sims=None,
                 net_ckpt="", net_ns=10, shm_name="", id_q=None):
    _W["cand_cfg_dict"] = cand_cfg_dict
    _W["cand_sims"] = cand_sims
    _W["champ_sims"] = champ_sims
    _W["exact_k"] = exact_k
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["claim_stale"] = claim_stale
    _W["cand_kind"] = cand_kind
    _W["opp_kind"] = opp_kind
    _W["opp_sims"] = opp_sims if opp_sims is not None else champ_sims
    _W["net"] = None
    _W["net_dev"] = None
    _W["net_handles"] = None
    _W["net_ns"] = net_ns
    if opp_kind == "net":
        import torch
        torch.set_num_threads(1)
        if shm_name:
            # carc-orch SHM orchestrator: the server owns the only net copy; this
            # worker is CPU-only and gets forwards over SHM (== eval_hybrid_handoff).
            from carcassonne_ai.shm_eval_handles import connect_shm
            _W["net_handles"] = connect_shm(shm_name, id_q.get(), net_ns, NET_N_CH)
        else:
            _W["net"], _W["net_dev"], _W["net_ns"] = _load_net_cpu(net_ckpt)


def _make_cand_cfg():
    d = _W["cand_cfg_dict"]
    # rebuild the LeafConfig from DEFAULT_CONFIG (env-resolved Bmild_cap8) — the
    # cfg dict only carries the agent knobs; the leaf is the production default.
    return HeuristicPriorConfig(
        c_puct=d["c_puct"], tau_p=d["tau_p"],
        leaf_quantize=d["leaf_quantize"], final_select=d["final_select"],
        value_norm=d["value_norm"], leaf_cfg=DEFAULT_CONFIG,
    )


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

    K = _W["exact_k"]
    # candidate side (prefix = PUCT+heur priors, or plain HeuristicMCTS for h<sims>)
    if _W.get("cand_kind", "puct") == "heur":
        cand_prefix = _ChampPrefix(Game(enable_legal_moves_cache=True), _W["cand_sims"],
                                   seed, DEFAULT_CONFIG)
    else:
        cfg = _make_cand_cfg()
        cand_prefix = HeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                                          simulations=_W["cand_sims"], seed=seed)
    # opponent side (prefix = HeuristicMCTS, or the pinned rod_v2-anchor NeuralMCTS)
    if _W.get("opp_kind", "heur") == "net":
        champ_prefix = _make_net_prefix(seed + 1)
        opp_K = 0   # BARE net (pinned anchor config): K=0 never latches the exact tail
    else:
        champ_prefix = _ChampPrefix(Game(enable_legal_moves_cache=True), _W["opp_sims"],
                                    seed + 1, DEFAULT_CONFIG)
        opp_K = K
    cand = _ExactHandoff(cand_prefix, Game(enable_legal_moves_cache=True), K)
    champ = _ExactHandoff(champ_prefix, Game(enable_legal_moves_cache=True), opp_K)

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        agent = cand if cur == a_seat else champ
        action = agent.move(board)
        board, _ = game.get_next_state(board, action)
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    latch_k = cand.latch_k if cand.latch_k is not None else champ.latch_k
    r = GameResult(
        seed=seed, a_seat=a_seat, cand_sims=_W["cand_sims"], champ_sims=_W["opp_sims"],
        score_p0=int(s0), score_p1=int(s1), diff=int(diff),
        won_by_cand=(diff > 0), drew=(diff == 0), elapsed_s=round(elapsed, 3), moves=moves,
        deck_hash=dh,
        cand_prefix_moves=cand.prefix_moves, cand_exact_moves=cand.exact_moves,
        cand_prefix_secs=round(cand.prefix_secs, 3), cand_solver_secs=round(cand.solver_secs, 3),
        cand_timeouts=cand.n_timeouts,
        champ_prefix_moves=champ.prefix_moves, champ_exact_moves=champ.exact_moves,
        champ_prefix_secs=round(champ.prefix_secs, 3), champ_solver_secs=round(champ.solver_secs, 3),
        champ_timeouts=champ.n_timeouts, latch_k=latch_k,
    )
    _save(p, r)
    return r


# --------------------------------------------------------------------------- #
def _paired_z(results):
    """Paired z on per-deck seat-balanced margin (= eval_hybrid_handoff._paired_z /
    ladder_rung_eval)."""
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


def _summary(results, cand_sims, champ_sims, cand_label=None, opp_label=None):
    n = len(results)
    w = sum(1 for r in results if r.won_by_cand)
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
    cand_latched = sum(1 for r in results if r.cand_exact_moves > 0)
    cand_ms = (sum(r.cand_prefix_secs for r in results) /
               max(1, sum(r.cand_prefix_moves for r in results))) * 1e3
    champ_ms = (sum(r.champ_prefix_secs for r in results) /
                max(1, sum(r.champ_prefix_moves for r in results))) * 1e3
    solver_pergame = sum(r.cand_solver_secs + r.champ_solver_secs for r in results) / n
    print()
    cl = cand_label or f"PUCT-heur-priors(cand s{cand_sims})"
    ol = opp_label or f"champion(heur h{champ_sims})"
    print(f"=== {cl} vs {ol} ===")
    print(f"games: {n}   candidate: {w}W / {d}D / {losses}L   winrate {wr:.3f} (z={wr_z:+.2f})")
    print(f"avg score diff (cand - champ): {avg:+.2f}")
    print(f"ELO: {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    if mean_d is not None:
        print(f"PAIRED: {npair} decks   mean seat-balanced margin {mean_d:+.2f}   z = {z:+.2f}")
    print(f"prefix ms/move: candidate {cand_ms:.0f}  champion {champ_ms:.0f}  "
          f"(ratio {cand_ms/max(1e-9,champ_ms):.2f}x)")
    print(f"exact endgame: latched {cand_latched}/{n} games, {solver_pergame:.2f}s solver/game, "
          f"timeouts cand={sum(r.cand_timeouts for r in results)} champ={sum(r.champ_timeouts for r in results)}")
    if abs(elo) <= 35 and not math.isnan(elo_sig):
        print(f"  POWER NOTE: |elo|<=35 at n={n} (1σ≈±{elo_sig:.0f}); a >=35-elo verdict needs n>=400.")
    return {
        "n": n, "W": w, "D": d, "L": losses, "winrate": wr, "winrate_z": wr_z,
        "elo": elo, "elo_sig_1sigma": elo_sig, "avg_diff": avg,
        "paired_mean_margin": mean_d, "paired_z": z, "n_paired": npair,
        "cand_prefix_ms_per_move": cand_ms, "champ_prefix_ms_per_move": champ_ms,
        "cand_latched_games": cand_latched, "solver_secs_per_game": solver_pergame,
    }


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))
    return work


def _append_results_csv(csv_path: Path, row: dict):
    header = ["exp_id", "date", "game", "code_rev", "n", "new_ckpt", "new_c", "new_cap",
              "new_var", "new_sims", "old_ckpt", "old_c", "old_cap", "old_var", "old_sims",
              "W", "L", "D", "elo", "sigma", "avg_diff", "src_dir", "confidence", "note"]
    exists = csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=header)
        if not exists:
            wtr.writeheader()
        wtr.writerow({k: row.get(k, "") for k in header})


# --------------------------------------------------------------------------- #
def _smoke(args, cand_kind="puct", opp_kind="heur", opp_sims=None, net_ckpt=None,
           new_mode=False) -> int:
    """Single-process plumbing + handoff-fires proof: play 2 paired games, print
    move/handoff counts, assert both sides latched to the exact endgame, exit.
    Honors --candidate/--opponent; a net: opponent is loaded on CPU (no orch)."""
    if opp_sims is None:
        opp_sims = args.champ_sims
    cfg = None
    if cand_kind == "puct":
        cfg = HeuristicPriorConfig(c_puct=args.c_puct, tau_p=args.tau_p,
                                   leaf_quantize=args.leaf_quantize, final_select=args.final_select,
                                   leaf_cfg=DEFAULT_CONFIG)
    net = net_dev = net_ns = None
    if opp_kind == "net":
        net, net_dev, net_ns = _load_net_cpu(net_ckpt)
    import random
    if not new_mode:
        print(f"[smoke] cand: c_puct={args.c_puct} tau_p={args.tau_p} quant={args.leaf_quantize} "
              f"select={args.final_select} sims={args.cand_sims} | champ h{args.champ_sims} | exact-K={args.exact_k}")
    else:
        cand_desc = (f"puct c_puct={args.c_puct} tau_p={args.tau_p} quant={args.leaf_quantize} "
                     f"select={args.final_select} sims={args.cand_sims}" if cand_kind == "puct"
                     else f"heur h{args.cand_sims}")
        opp_desc = (f"heur h{opp_sims}" if opp_kind == "heur"
                    else f"net:{net_ckpt}@{NET_SIMS} c{NET_CPUCT} rs{NET_RESIDUAL_SCALE} (CPU, bare)")
        print(f"[smoke] cand: {cand_desc} | opp: {opp_desc} | exact-K={args.exact_k}")
    t0 = time.perf_counter()
    for a_seat in (0, 1):
        seed = args.seed_start
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        if cand_kind == "heur":
            cand_prefix = _ChampPrefix(Game(enable_legal_moves_cache=True), args.cand_sims,
                                       seed, DEFAULT_CONFIG)
        else:
            cand_prefix = HeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                                              simulations=args.cand_sims, seed=seed)
        opp_K = args.exact_k
        if opp_kind == "net":
            farm = net_ns > 10
            gf = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
            from carcassonne_ai.evaluators import make_single_evaluator
            champ_prefix = _NetPrefix(make_single_evaluator(net, net_dev, gf), gf, seed + 1)
            opp_K = 0   # bare net (pinned anchor config)
        else:
            champ_prefix = _ChampPrefix(Game(enable_legal_moves_cache=True), opp_sims,
                                        seed + 1, DEFAULT_CONFIG)
        cand = _ExactHandoff(cand_prefix, Game(enable_legal_moves_cache=True), args.exact_k)
        champ = _ExactHandoff(champ_prefix, Game(enable_legal_moves_cache=True), opp_K)
        moves = 0
        while game.get_game_ended(board, 0) == 0.0:
            cur = board.state.current_player
            mask = game.get_valid_moves(board)
            agent = cand if cur == a_seat else champ
            act = agent.move(board)
            assert mask[act], f"illegal action {act}"
            board, _ = game.get_next_state(board, act)
            moves += 1
        s0, s1 = board.state.scores
        diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
        print(f"[smoke] a_seat={a_seat}: {s0}-{s1} diff(cand-champ)={diff:+d} moves={moves} | "
              f"cand prefix/exact={cand.prefix_moves}/{cand.exact_moves} latch_k={cand.latch_k} "
              f"solver={cand.solver_secs:.1f}s to={cand.n_timeouts} ; "
              f"champ prefix/exact={champ.prefix_moves}/{champ.exact_moves} latch_k={champ.latch_k} "
              f"solver={champ.solver_secs:.1f}s")
        if args.exact_k > 0:
            assert cand.exact_moves > 0, "candidate never reached the exact endgame (K too small?)"
        if opp_K > 0:
            assert champ.exact_moves > 0, "champion never reached the exact endgame"
        assert cand.prefix_moves > 0 and champ.prefix_moves > 0, "prefix search never ran (K too big?)"
    print(f"[smoke] OK — plumbing + exact handoff verified ({time.perf_counter()-t0:.1f}s for 2 games)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_puct_priors")
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--tau-p", type=float, default=5.0)
    ap.add_argument("--leaf-quantize", choices=("int", "float"), default="float")
    ap.add_argument("--final-select", choices=("Q", "visits"), default="Q")
    ap.add_argument("--value-norm", type=float, default=15.0)
    ap.add_argument("--cand-sims", type=int, default=None,
                    help="candidate PUCT sims (from the equal-time bench match); required "
                         "for --candidate puct, ignored for --candidate h<sims>")
    ap.add_argument("--champ-sims", type=int, default=6400)
    ap.add_argument("--candidate", type=str, default="puct",
                    help="candidate side: 'puct' (default; PUCT-heur-priors @ --cand-sims) or "
                         "'h<sims>' (plain HeuristicMCTS @ <sims>, same v2.9 leaf + exact-K "
                         "handoff as the champion side; puct flags ignored/recorded null)")
    ap.add_argument("--opponent", type=str, default=None,
                    help="opponent side (default: h<champ-sims>, the legacy champion). "
                         "'h<sims>' = HeuristicMCTS @ <sims> (+ exact-K handoff). "
                         "'net:<ckpt.pt>' = NeuralMCTS opponent pinned to the rod_v2 anchor "
                         f"config (sims={NET_SIMS}, c_puct={NET_CPUCT}, v2.9 leaf + residual "
                         f"{NET_RESIDUAL_SCALE}, bare/no exact tail); net-on-CPU unless "
                         "--shm-eval-server is given")
    ap.add_argument("--shm-eval-server", type=str, default=None,
                    help="carc-orch SHM orchestrator name for the net: opponent (workers "
                         "attach to /dev/shm/carc_<NAME>); omit for net-on-CPU per worker")
    ap.add_argument("--exact-k", type=int, default=4, help="exact clairvoyant endgame handoff at k_remaining<=K")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--games", type=int, default=None, help="alias for --n (convenience)")
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=9_000_000_000)
    ap.add_argument("--allow-selfplay-seeds", action="store_true")
    ap.add_argument("--out-root", type=str, default=None)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=5400)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--no-results-csv", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args(argv)
    if args.games is not None:
        args.n = args.games
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n")

    try:
        cand_kind, opp_kind, opp_sims, net_ckpt, new_mode = _resolve_specs(args)
    except ValueError as e:
        ap.error(str(e))
    if args.shm_eval_server and opp_kind != "net":
        ap.error("--shm-eval-server requires --opponent net:<ckpt.pt>")

    if args.smoke:
        return _smoke(args, cand_kind, opp_kind, opp_sims, net_ckpt, new_mode)

    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    net_meta = net_sha = None
    if opp_kind == "net" and not args.summary_only:
        if not Path(net_ckpt).is_file():
            ap.error(f"net opponent checkpoint not found: {net_ckpt}")
        net_meta = _read_ckpt_meta(net_ckpt)
        net_sha = _file_sha256(net_ckpt)

    cfg = HeuristicPriorConfig(c_puct=args.c_puct, tau_p=args.tau_p,
                               leaf_quantize=args.leaf_quantize, final_select=args.final_select,
                               value_norm=args.value_norm, leaf_cfg=DEFAULT_CONFIG)
    cand_cfg_dict = {"c_puct": args.c_puct, "tau_p": args.tau_p,
                     "leaf_quantize": args.leaf_quantize, "final_select": args.final_select,
                     "value_norm": args.value_norm}

    tag = _cell_tag(args, cand_kind, opp_kind, opp_sims, net_ckpt, new_mode)
    sub = args.out_subdir or tag
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    tasks = [(str(out), seed, a_seat)
             for seed, a_seat in _build_work(args.seed_start, args.n, args.paired)]

    # summary labels: legacy None -> byte-identical header; rr cells name both sides.
    cand_label = opp_label = None
    if new_mode:
        cand_label = (f"PUCT-heur-priors(cand s{args.cand_sims})" if cand_kind == "puct"
                      else f"candidate(heur h{args.cand_sims})")
        opp_label = (f"opponent(heur h{opp_sims})" if opp_kind == "heur"
                     else f"opponent(net:{Path(net_ckpt).stem}@{NET_SIMS})")

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, t[1], t[2]))) is not None]
        if results:
            summ = _summary(results, args.cand_sims, args.champ_sims, cand_label, opp_label)
            json.dump(summ, open(out / "summary.json", "w"), indent=2)
        else:
            print("no cached results yet")
        return 0

    leaf_cfg = cfg.resolved_leaf_cfg()
    man_cfg = {"candidate": cfg.as_manifest(),
               "cand_sims": args.cand_sims, "champ_sims": args.champ_sims,
               "champion": {"agent": "HeuristicMCTS", "heur_leaf": "v2_7",
                            "c": CHAMP_C, "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)"},
               "exact_k": args.exact_k, "exact_mode": "clairvoyant",
               "exact_budget": EXACT_BUDGET,
               "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
               "leaf_hash": _leaf_hash(leaf_cfg), "code_rev": code_rev(),
               "env": {k: os.environ.get(k) for k in _CANON_ENV}}
    if new_mode:
        # Round-robin cell: resolved candidate + opponent specs (ROUND_ROBIN_PLAN.md).
        if cand_kind == "puct":
            cand_block = {"kind": "puct", "agent": "HeuristicPriorAgent",
                          "sims": args.cand_sims, "exact_k": args.exact_k,
                          **cfg.as_manifest()}
        else:
            # puct-specific knobs ignored for an h<sims> candidate -> recorded as null.
            cand_block = {"kind": "heur", "agent": "HeuristicMCTS", "heur_leaf": "v2_7",
                          "c": CHAMP_C, "sims": args.cand_sims,
                          "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)",
                          "exact_k": args.exact_k,
                          "c_puct": None, "tau_p": None, "leaf_quantize": None,
                          "final_select": None, "value_norm": None}
        if opp_kind == "heur":
            opp_block = {"kind": "heur", "agent": "HeuristicMCTS", "heur_leaf": "v2_7",
                         "c": CHAMP_C, "sims": opp_sims,
                         "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)",
                         "exact_k": args.exact_k}
        else:
            opp_block = {"kind": "net", "agent": "NeuralMCTS",
                         "ckpt": str(net_ckpt), "ckpt_sha256": net_sha,
                         "sims": NET_SIMS, "c_puct": NET_CPUCT,
                         "residual_scale": NET_RESIDUAL_SCALE, "meeple_k": NET_MEEPLE_K,
                         "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG) + net value residual "
                                 "(make_v25_value_wrapper)",
                         "exact_k": 0,   # bare prefix: NO exact tail (anchor rows were bare)
                         "include_farm_scalars": net_meta["n_scalar_features"] > 10,
                         "orch_shm": args.shm_eval_server,
                         "net_n_ch": NET_N_CH,
                         "pinned_from": "scripts/level2/eval_hybrid_handoff.py ITER8_SIMS/"
                                        "ITER8_CPUCT/ITER8_RESIDUAL_SCALE (rod_v2 anchor "
                                        "harness; results.csv rodv2_iter02_vs_heur*_v29_n200)",
                         **net_meta}
        man_cfg.update({"rr_cell": tag,
                        "candidate_spec": args.candidate,
                        "opponent_spec": args.opponent or f"h{args.champ_sims}",
                        "candidate": cand_block,
                        "opponent": opp_block,
                        "champ_sims": opp_sims})
        del man_cfg["champion"]   # replaced by the resolved "opponent" block
    write_manifest(out, kind="eval_puct_priors", game=game_tag(Game()),
                   config=man_cfg, overwrite=True)

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"puct-priors[{tag}]: n={args.n} paired={args.paired} | "
          f"{len(tasks)-len(todo)} cached, {len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        id_q = None
        if args.shm_eval_server:
            from multiprocessing import Queue
            id_q = Queue()
            for w in range(workers):
                id_q.put(w)
            print(f"  [orch] SHM eval-server '{args.shm_eval_server}': {workers} CPU workers "
                  f"attach to /dev/shm/carc_{args.shm_eval_server} "
                  f"(n_scalar={net_meta['n_scalar_features']})", flush=True)
        with Pool(processes=workers, initializer=_worker_init,
                  initargs=(cand_cfg_dict, args.cand_sims, args.champ_sims, args.exact_k,
                            args.shared_claim, args.claim_host, args.claim_stale_secs,
                            cand_kind, opp_kind, opp_sims, net_ckpt or "",
                            (net_meta or {}).get("n_scalar_features", 10),
                            args.shm_eval_server or "", id_q)) as pool:
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
    summ = _summary(results, args.cand_sims, args.champ_sims, cand_label, opp_label)
    json.dump(summ, open(out / "summary.json", "w"), indent=2)

    if not args.no_results_csv:
        if not new_mode:
            note = (f"Phase 1.1 PUCT-heur-priors vs champion (search-only, both exact-K<={args.exact_k}). "
                    f"c_puct={args.c_puct} tau_p={args.tau_p} quant={args.leaf_quantize} "
                    f"select={args.final_select}. cand ms/move {summ['cand_prefix_ms_per_move']:.0f} "
                    f"vs champ {summ['champ_prefix_ms_per_move']:.0f}. paired_z={summ['paired_z']}.")
            row = {
                "new_ckpt": f"puct_prior_{args.leaf_quantize}_{args.final_select}",
                "new_c": args.c_puct, "new_var": "puct_heur_prior",
                "old_ckpt": "heur_h6400_champion", "old_c": CHAMP_C,
                "old_var": "v2_9_champion", "old_sims": args.champ_sims,
            }
        else:
            cand_desc = (f"PUCT-heur-priors(c_puct={args.c_puct} tau_p={args.tau_p} "
                         f"quant={args.leaf_quantize} select={args.final_select} s{args.cand_sims})"
                         if cand_kind == "puct" else f"HeuristicMCTS h{args.cand_sims}")
            opp_desc = (f"HeuristicMCTS h{opp_sims} (exact-K<={args.exact_k})" if opp_kind == "heur"
                        else f"NeuralMCTS {Path(net_ckpt).stem}@{NET_SIMS} c{NET_CPUCT} "
                             f"rs{NET_RESIDUAL_SCALE} (bare, rod_v2 anchor cfg"
                             f"{', orch ' + args.shm_eval_server if args.shm_eval_server else ', net-on-CPU'})")
            note = (f"Phase 1.1b transitivity round-robin cell {tag} "
                    f"(measurement/classical_search/ROUND_ROBIN_PLAN.md): candidate {cand_desc} "
                    f"exact-K<={args.exact_k} vs opponent {opp_desc}. "
                    f"cand ms/move {summ['cand_prefix_ms_per_move']:.0f} vs opp "
                    f"{summ['champ_prefix_ms_per_move']:.0f}. paired_z={summ['paired_z']}.")
            row = {
                "new_ckpt": (f"puct_prior_{args.leaf_quantize}_{args.final_select}"
                             if cand_kind == "puct" else f"heur_h{args.cand_sims}_champion"),
                "new_c": args.c_puct if cand_kind == "puct" else CHAMP_C,
                "new_var": "puct_heur_prior" if cand_kind == "puct" else "v2_9_champion",
                "old_ckpt": (f"heur_h{opp_sims}" if opp_kind == "heur" else str(net_ckpt)),
                "old_c": CHAMP_C if opp_kind == "heur" else NET_CPUCT,
                "old_var": "v2_9_champion" if opp_kind == "heur" else "v2_9_rodv2_anchor",
                "old_sims": opp_sims,
            }
        row.update({
            "exp_id": tag, "date": time.strftime("%Y-%m-%d"), "game": "base",
            "code_rev": code_rev(), "n": summ["n"],
            "new_cap": leaf_cfg.bonus_cap, "new_sims": args.cand_sims,
            "old_cap": leaf_cfg.bonus_cap,
            "W": summ["W"], "L": summ["L"], "D": summ["D"],
            "elo": round(summ["elo"], 1), "sigma": round(summ["elo_sig_1sigma"], 1),
            "avg_diff": round(summ["avg_diff"], 2), "src_dir": str(out),
            "confidence": "screen" if summ["n"] < 400 else "high", "note": note,
        })
        _append_results_csv(REPO / "experiments" / "results.csv", row)
        print(f"[results.csv] appended row exp_id={tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
