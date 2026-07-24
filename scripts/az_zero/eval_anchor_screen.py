#!/usr/bin/env python3
"""az_zero — CHEAP anchor screen: the tabula-rasa candidate net-agent vs a
baseline opponent, NeuralMCTS each side, net VALUE + net POLICY (pure NN leaf).

Two baselines (pick with --opponent):
  * random  : a uniform-random legal-move player (the absolute floor — "is the
              loop learning ANYTHING above chance?").
  * net      : a FIXED reference net-agent (default the heuristic warm-start),
              same sims — the "what does the heuristic scaffolding buy?"
              comparison. az_zero starts from RANDOM weights; the warm-start
              starts from the heuristic. A per-iter az_zero-vs-warmstart winrate
              tracks how far the zero-start has closed (or not) that gap.

BOTH agents are a NeuralMCTS running each side's OWN net for BOTH the PUCT priors
(policy head, masked softmax) AND the leaf VALUE (value head, tanh) — i.e. the
SAME pure-NN agent the az_zero self-play loop uses. No v2.7/v2.9 heuristic leaf,
no exact-endgame solver — that keeps the screen faithful to the tabula-rasa agent
(injecting the heuristic leaf here would measure a different agent than the loop
trains). Each side featurizes with its OWN Game encoder (peeked from its ckpt), so
a SIGHTED candidate (81ch/42) can be screened against a BLIND reference (78ch/10)
without the reps ever mixing — the two nets only ever see their own encoding of
the one shared board.

CLAIRVOYANCE: like the az_zero self-play machinery (selfplay.py builds NeuralMCTS
with fair_chance=False), the search here is CLAIRVOYANT — it descends the board's
TRUE future deck order (perfect-info single-determinization, sees the next tiles).
Both agents get the same information, so the head-to-head is fair; but the ABSOLUTE
strength is a clairvoyant-search number, NOT a blind-PIMC deployment number. See
measurement/az_zero_20260724/DESIGN.md.

Deck-paired: each seed is played with the candidate at BOTH seats (seat swap),
so seat/first-move advantage cancels in the paired mean. net-on-CPU (the screen is
n=50 at sims=128 — cheap; no orch server to manage). Per-game JSON checkpointing
(resume skips cached games).

Usage (vs random):
  CUDA_VISIBLE_DEVICES="" scripts/az_zero/eval_anchor_screen.py \
      --cand-ckpt <iter_NN.pt> --opponent random \
      --n 50 --sims 128 --workers 4 --out <dir>
Usage (vs the warm-start net):
  CUDA_VISIBLE_DEVICES="" scripts/az_zero/eval_anchor_screen.py \
      --cand-ckpt <iter_NN.pt> --opponent net \
      --anchor-ckpt <warmstart.pt> --n 50 --sims 128 --workers 4 --out <dir>
"""
from __future__ import annotations

import os

# Cap BLAS/torch intra-op threads to 1 BEFORE torch imports (each worker runs the
# net on CPU; without this one worker oversubscribes ~all cores of torch threads
# and W>1 thrashes — throughput scales with WORKER count, not threads). setdefault
# so a caller that deliberately set them wins. Mirrors gen_fair_distill's _CANON_ENV.
for _k, _v in {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "OPENBLAS_NUM_THREADS": "1"}.items():
    os.environ.setdefault(_k, _v)

import argparse
import json
import math
import multiprocessing as mp
import random
import socket
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai.claim import try_claim as _try_claim  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402


_W: dict = {}


@dataclass
class GameResult:
    seed: int
    cand_seat: int      # seat (0/1) the candidate plays this game
    sims: int
    c_puct: float
    score_p0: int
    score_p1: int
    diff: int           # candidate - opponent, seat-corrected
    won_by_cand: bool
    drew: bool
    elapsed_s: float
    moves: int


def _result_path(out: Path, sims: int, c: float, seed: int, cand_seat: int) -> Path:
    return out / f"s{sims:04d}_c{str(c).replace('.', '')}_seed{seed:09d}_a{cand_seat}.json"


def _try_load(p: Path) -> GameResult | None:
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p: Path, r: GameResult) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    json.dump(asdict(r), open(tmp, "w"))
    tmp.replace(p)


def _load_net(path: str, device: str = "cpu"):
    """Load a CarcassonneNet checkpoint on `device` (CPU by default). Arch dims
    ride in the ckpt (81ch/42 sighted candidate, or 78ch/10 blind reference)."""
    import torch

    from carcassonne_ai.network import CarcassonneNet
    ck = torch.load(path, map_location=device, weights_only=False)
    n_ch = int(ck.get("n_input_channels", 78))
    n_scalar = int(ck.get("n_scalar_features", 10))
    sighted = bool(ck.get("sighted", False))
    net = CarcassonneNet(
        n_filters=int(ck.get("n_filters", 96)), n_blocks=int(ck.get("n_blocks", 6)),
        n_input_channels=n_ch, n_scalar_features=n_scalar,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    return net, n_ch, n_scalar, sighted


def _worker_init(cand_ckpt, anchor_ckpt, opponent, device, fpu,
                 shared_claim, claim_host, claim_stale):
    import torch  # noqa: F401  (ensures torch thread env respected before net build)

    from carcassonne_ai.evaluators import make_single_evaluator

    _W["opponent"] = opponent
    _W["fpu"] = fpu
    _W["device_str"] = device
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["claim_stale"] = claim_stale

    import torch as _t
    dev = _t.device(device)

    cnet, c_nch, c_ns, c_sighted = _load_net(cand_ckpt, device)
    ga = Game(enable_legal_moves_cache=True, sighted=c_sighted,
              include_farm_scalars=(c_ns > 10) and not c_sighted)
    _W["ga"] = ga
    _W["cand_eval"] = make_single_evaluator(cnet, dev, ga)

    if opponent == "net":
        anet, a_nch, a_ns, a_sighted = _load_net(anchor_ckpt, device)
        gb = Game(enable_legal_moves_cache=True, sighted=a_sighted,
                  include_farm_scalars=(a_ns > 10) and not a_sighted)
        _W["gb"] = gb
        _W["anchor_eval"] = make_single_evaluator(anet, dev, gb)
    else:
        _W["gb"] = None
        _W["anchor_eval"] = None


def _play_one(args):
    out_str, seed, cand_seat, sims, c_puct = args
    out = Path(out_str)
    p = _result_path(out, sims, c_puct, seed, cand_seat)
    c = _try_load(p)
    if c is not None:
        return c
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None

    ga = _W["ga"]
    fpu = _W["fpu"]
    # Deck shuffle uses the global RNG (get_init_board) — seed it. A SEPARATE rng
    # drives the random opponent's move picks so it never perturbs the deck stream.
    random.seed(seed)
    rng = random.Random(seed ^ 0x5A5A5A5A)

    cand_mcts = NeuralMCTS(game=ga, evaluator=_W["cand_eval"], simulations=sims,
                           seed=seed, c_puct=c_puct, fpu_reduction=fpu)
    opp_kind = _W["opponent"]
    if opp_kind == "net":
        gb = _W["gb"]
        opp_mcts = NeuralMCTS(game=gb, evaluator=_W["anchor_eval"], simulations=sims,
                              seed=seed + 1, c_puct=c_puct, fpu_reduction=fpu)
    else:
        gb = None
        opp_mcts = None

    board = ga.get_init_board()
    t0 = time.perf_counter()
    moves = 0
    while ga.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == cand_seat:
            cand_mcts.clear()
            action = cand_mcts.best_action(board)
        elif opp_kind == "net":
            opp_mcts.clear()
            action = opp_mcts.best_action(board)
        else:
            # uniform-random legal move
            import numpy as np
            legal = np.flatnonzero(ga.get_valid_moves(board))
            action = int(rng.choice(legal.tolist()))
        board, _ = ga.get_next_state(board, action)
        moves += 1

    s0, s1 = int(board.state.scores[0]), int(board.state.scores[1])
    diff = (s0 - s1) if cand_seat == 0 else (s1 - s0)
    r = GameResult(seed=seed, cand_seat=cand_seat, sims=sims, c_puct=c_puct,
                   score_p0=s0, score_p1=s1, diff=diff,
                   won_by_cand=(diff > 0), drew=(diff == 0),
                   elapsed_s=time.perf_counter() - t0, moves=moves)
    _save(p, r)
    return r


def _summary(results, sims, label):
    n = len(results)
    w = sum(r.won_by_cand for r in results)
    d = sum(r.drew for r in results)
    losses = n - w - d
    avg = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    diffs = [r.diff for r in results]
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    z = (mean / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        es = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, es = math.copysign(800.0, wr - 0.5), float("nan")
    # deck-paired mean (candidate at both seats of each seed)
    by_seed: dict[int, dict[int, int]] = {}
    for r in results:
        by_seed.setdefault(r.seed, {})[r.cand_seat] = r.diff
    pairs = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    if pairs:
        pmean = sum(pairs) / len(pairs)
        pvar = sum((x - pmean) ** 2 for x in pairs) / (len(pairs) - 1) if len(pairs) > 1 else 0.0
        psd = math.sqrt(pvar)
        pz = (pmean / (psd / math.sqrt(len(pairs)))) if psd > 0 else float("nan")
    else:
        pmean = pz = float("nan")
    print(f"\n=== {label}, NeuralMCTS@{sims}, n={n} ===")
    print(f"CAND: {w}W/{d}D/{losses}L  wr {wr:.3f}  avg diff {avg:+.2f}  "
          f"z_margin {z:+.2f}  ELO {elo:+.1f} (+/-{es:.1f})")
    print(f"   deck-paired: mean {pmean:+.2f} over {len(pairs)} pairs  paired_z {pz:+.2f}")
    sig = "VERDICT-RANGE" if (not math.isnan(es) and abs(elo) > 2 * es) else "INCONCLUSIVE"
    print(f"signal: {sig}")
    return {
        "label": label, "sims": sims, "n": n, "W": w, "D": d, "L": losses,
        "winrate": round(wr, 4), "avg_diff": round(avg, 3), "z_margin": round(z, 3),
        "elo": round(elo, 1), "elo_1sig": (round(es, 1) if not math.isnan(es) else None),
        "paired_mean": (round(pmean, 3) if not math.isnan(pmean) else None),
        "paired_z": (round(pz, 3) if not math.isnan(pz) else None),
        "n_pairs": len(pairs), "signal": sig,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval_anchor_screen")
    ap.add_argument("--cand-ckpt", required=True, help="tabula-rasa candidate checkpoint")
    ap.add_argument("--opponent", choices=["random", "net"], required=True,
                    help="'random' = uniform legal-move floor; 'net' = a fixed "
                         "reference net-agent (--anchor-ckpt).")
    ap.add_argument("--anchor-ckpt", default=None,
                    help="Required with --opponent net: the FIXED reference net "
                         "(e.g. the heuristic warm-start).")
    ap.add_argument("--n", type=int, default=50, help="games (default 50)")
    ap.add_argument("--sims", type=int, default=128, help="NeuralMCTS sims/move (loop budget)")
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--fpu", type=float, default=None,
                    help="First-play-urgency reduction (None = legacy optimistic-zero).")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--device", default="cpu", help="cpu (default) or cuda")
    ap.add_argument("--seed-start", type=int, default=770_000_000)
    ap.add_argument("--out", required=True, help="output dir")
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=600)
    ap.add_argument("--claim-host", default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)

    if args.opponent == "net" and not args.anchor_ckpt:
        ap.error("--opponent net requires --anchor-ckpt")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lbl_opp = "random" if args.opponent == "random" else f"net({Path(args.anchor_ckpt).name})"
    label = f"CAND={Path(args.cand_ckpt).name} vs {lbl_opp} (pure-NN leaf, clairvoyant)"

    # seat-alternating deck pairing: seed i played with the candidate at seat i%2.
    tasks = [(str(out), args.seed_start + (i // 2), i % 2, args.sims, args.c_puct)
             for i in range(args.n)]

    json.dump({
        "kind": "az_zero_anchor_screen",
        "cand_ckpt": args.cand_ckpt, "opponent": args.opponent,
        "anchor_ckpt": args.anchor_ckpt, "n": args.n, "sims": args.sims,
        "c_puct": args.c_puct, "fpu": args.fpu, "seed_start": args.seed_start,
        "device": args.device,
        "leaf": "pure NN (net priors + net value head); NO heuristic leaf, NO solver",
        "clairvoyance": "fair_chance=False (clairvoyant, sees true future deck) — matches selfplay.py",
    }, open(out / "manifest.json", "w"), indent=2)

    if args.summary_only:
        res = [r for t in tasks
               if (r := _try_load(_result_path(out, args.sims, args.c_puct, t[1], t[2]))) is not None]
        if res:
            json.dump(_summary(res, args.sims, label), open(out / "result.json", "w"), indent=2)
        else:
            print("no cached results")
        return 0

    todo = [t for t in tasks
            if not _result_path(out, args.sims, args.c_puct, t[1], t[2]).exists()]
    print(f"[az-anchor] {label} | n={args.n} sims={args.sims} c={args.c_puct} "
          f"device={args.device} | {len(tasks) - len(todo)} cached, {len(todo)} to play, "
          f"W={args.workers}, out={out}", flush=True)

    results = []
    if todo:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=args.workers, initializer=_worker_init,
                      initargs=(args.cand_ckpt, args.anchor_ckpt, args.opponent,
                                args.device, args.fpu, args.shared_claim,
                                args.claim_host, args.claim_stale_secs)) as pool:
            t0 = time.perf_counter()
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r)
                done += 1
                if done % 10 == 0:
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el / done:.1f}s/game)", flush=True)

    # fold in any cached results not replayed this run
    for t in tasks:
        p = _result_path(out, args.sims, args.c_puct, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.cand_seat == t[2] for r in results):
            cc = _try_load(p)
            if cc:
                results.append(cc)

    if results:
        summ = _summary(results, args.sims, label)
        json.dump(summ, open(out / "result.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
