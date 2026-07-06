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
                 shared_claim, claim_host, claim_stale):
    _W["cand_cfg_dict"] = cand_cfg_dict
    _W["cand_sims"] = cand_sims
    _W["champ_sims"] = champ_sims
    _W["exact_k"] = exact_k
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["claim_stale"] = claim_stale


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
    cfg = _make_cand_cfg()
    # candidate side (prefix = PUCT+heur priors), champion side (prefix = HeuristicMCTS)
    cand_prefix = HeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                                      simulations=_W["cand_sims"], seed=seed)
    champ_prefix = _ChampPrefix(Game(enable_legal_moves_cache=True), _W["champ_sims"],
                                seed + 1, DEFAULT_CONFIG)
    cand = _ExactHandoff(cand_prefix, Game(enable_legal_moves_cache=True), K)
    champ = _ExactHandoff(champ_prefix, Game(enable_legal_moves_cache=True), K)

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
        seed=seed, a_seat=a_seat, cand_sims=_W["cand_sims"], champ_sims=_W["champ_sims"],
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


def _summary(results, cand_sims, champ_sims):
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
    print(f"=== PUCT-heur-priors(cand s{cand_sims}) vs champion(heur h{champ_sims}) ===")
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
def _smoke(args) -> int:
    """Single-process plumbing + handoff-fires proof: play 2 paired games, print
    move/handoff counts, assert both sides latched to the exact endgame, exit."""
    cfg = HeuristicPriorConfig(c_puct=args.c_puct, tau_p=args.tau_p,
                               leaf_quantize=args.leaf_quantize, final_select=args.final_select,
                               leaf_cfg=DEFAULT_CONFIG)
    import random
    print(f"[smoke] cand: c_puct={args.c_puct} tau_p={args.tau_p} quant={args.leaf_quantize} "
          f"select={args.final_select} sims={args.cand_sims} | champ h{args.champ_sims} | exact-K={args.exact_k}")
    t0 = time.perf_counter()
    for a_seat in (0, 1):
        seed = args.seed_start
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        cand = _ExactHandoff(HeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                                                 simulations=args.cand_sims, seed=seed),
                             Game(enable_legal_moves_cache=True), args.exact_k)
        champ = _ExactHandoff(_ChampPrefix(Game(enable_legal_moves_cache=True), args.champ_sims,
                                           seed + 1, DEFAULT_CONFIG),
                              Game(enable_legal_moves_cache=True), args.exact_k)
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
        assert cand.exact_moves > 0, "candidate never reached the exact endgame (K too small?)"
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
    ap.add_argument("--cand-sims", type=int, required=True,
                    help="candidate PUCT sims (from the equal-time bench match)")
    ap.add_argument("--champ-sims", type=int, default=6400)
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

    if args.smoke:
        return _smoke(args)

    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    cfg = HeuristicPriorConfig(c_puct=args.c_puct, tau_p=args.tau_p,
                               leaf_quantize=args.leaf_quantize, final_select=args.final_select,
                               value_norm=args.value_norm, leaf_cfg=DEFAULT_CONFIG)
    cand_cfg_dict = {"c_puct": args.c_puct, "tau_p": args.tau_p,
                     "leaf_quantize": args.leaf_quantize, "final_select": args.final_select,
                     "value_norm": args.value_norm}

    tag = (f"puct_c{args.c_puct:g}_tau{args.tau_p:g}_{args.leaf_quantize}_{args.final_select}"
           f"_s{args.cand_sims}_vs_h{args.champ_sims}_k{args.exact_k}")
    sub = args.out_subdir or tag
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    tasks = [(str(out), seed, a_seat)
             for seed, a_seat in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, t[1], t[2]))) is not None]
        if results:
            summ = _summary(results, args.cand_sims, args.champ_sims)
            json.dump(summ, open(out / "summary.json", "w"), indent=2)
        else:
            print("no cached results yet")
        return 0

    leaf_cfg = cfg.resolved_leaf_cfg()
    write_manifest(out, kind="eval_puct_priors", game=game_tag(Game()),
                   config={"candidate": cfg.as_manifest(),
                           "cand_sims": args.cand_sims, "champ_sims": args.champ_sims,
                           "champion": {"agent": "HeuristicMCTS", "heur_leaf": "v2_7",
                                        "c": CHAMP_C, "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)"},
                           "exact_k": args.exact_k, "exact_mode": "clairvoyant",
                           "exact_budget": EXACT_BUDGET,
                           "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
                           "leaf_hash": _leaf_hash(leaf_cfg), "code_rev": code_rev(),
                           "env": {k: os.environ.get(k) for k in _CANON_ENV}},
                   overwrite=True)

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"puct-priors[{tag}]: n={args.n} paired={args.paired} | "
          f"{len(tasks)-len(todo)} cached, {len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        with Pool(processes=workers, initializer=_worker_init,
                  initargs=(cand_cfg_dict, args.cand_sims, args.champ_sims, args.exact_k,
                            args.shared_claim, args.claim_host, args.claim_stale_secs)) as pool:
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
    summ = _summary(results, args.cand_sims, args.champ_sims)
    json.dump(summ, open(out / "summary.json", "w"), indent=2)

    if not args.no_results_csv:
        note = (f"Phase 1.1 PUCT-heur-priors vs champion (search-only, both exact-K<={args.exact_k}). "
                f"c_puct={args.c_puct} tau_p={args.tau_p} quant={args.leaf_quantize} "
                f"select={args.final_select}. cand ms/move {summ['cand_prefix_ms_per_move']:.0f} "
                f"vs champ {summ['champ_prefix_ms_per_move']:.0f}. paired_z={summ['paired_z']}.")
        _append_results_csv(REPO / "experiments" / "results.csv", {
            "exp_id": tag, "date": time.strftime("%Y-%m-%d"), "game": "base",
            "code_rev": code_rev(), "n": summ["n"],
            "new_ckpt": f"puct_prior_{args.leaf_quantize}_{args.final_select}",
            "new_c": args.c_puct, "new_cap": leaf_cfg.bonus_cap, "new_var": "puct_heur_prior",
            "new_sims": args.cand_sims,
            "old_ckpt": "heur_h6400_champion", "old_c": CHAMP_C, "old_cap": leaf_cfg.bonus_cap,
            "old_var": "v2_9_champion", "old_sims": args.champ_sims,
            "W": summ["W"], "L": summ["L"], "D": summ["D"],
            "elo": round(summ["elo"], 1), "sigma": round(summ["elo_sig_1sigma"], 1),
            "avg_diff": round(summ["avg_diff"], 2), "src_dir": str(out),
            "confidence": "screen" if summ["n"] < 400 else "high", "note": note,
        })
        print(f"[results.csv] appended row exp_id={tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
