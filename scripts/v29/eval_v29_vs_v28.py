"""v2.9 candidate vs v2.8 baseline — paired full-game HeuristicMCTS head-to-head.

Both sides are pure HeuristicMCTS on the v2_7 leaf; the ONLY difference is the
LeafConfig (side A = a v2.9 candidate, side B = the v2.8 production baseline,
meeple_k=2.0). Winrate is the throne — this measures actual game-winning strength,
not margin or trap-score.

Forked from eval_heur_vs_heur.py: same deck-pairing, balanced seats, per-game JSON
checkpoint (resumable), shared-claim cluster support, clean-seed namespace, full
provenance manifest. Adds:
  - leaf_cfg parametrization on both sides (CANDIDATES table).
  - a PRE-ENDGAME margin snapshot (a's score lead when the deck first drops to
    <=K_SNAPSHOT tiles) so the close/even/behind + already-won-padding splits are
    computed on a PRE-OUTCOME state, not the final-margin collider.
  - full resolved LeafConfig (both sides) + git commit in the manifest.

Pure CPU (no GPU/orchestrator) -> keep workers <= threads.

Usage:
  python -u scripts/v29/eval_v29_vs_v28.py --candidate A16 --n 200 --sims 200 --paired \
      --seed-start 1000000000 --workers 14 --out-root /mnt/c/carc-shared/v29_eval
"""
from __future__ import annotations

import argparse
import dataclasses as dc
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carcassonne_ai.claim import try_claim as _try_claim
from carcassonne_ai import eval_provenance as ep
from carcassonne_ai.eval_provenance import deck_hash
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS
from carcassonne_ai.run_manifest import game_tag, write_manifest
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

REPO = Path(__file__).resolve().parent.parent.parent
EVAL_ROOT = REPO / "data" / "v29_eval"
K_SNAPSHOT = 6  # tiles-remaining threshold for the pre-endgame lead snapshot

# v2.8 production baseline: DEFAULT_CONFIG (cap=12, drop-three-open) + flat meeple_k=2.0.
V28 = dc.replace(DEFAULT_CONFIG, meeple_k=2.0)
# Nonlinear meeple liquidity curves (value by free-meeple count 0..7).
MILD_CURVE = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
AGGR_CURVE = (-14.0, -7.0, -3.0, 0.0, 2.0, 3.0, 3.5, 4.0)


def candidate_cfg(name: str):
    """Map a candidate name to a LeafConfig (built on the v2.8 baseline)."""
    if name == "v28":
        return V28                                            # null control (A vs B both v28)
    if name.startswith("A") and name[1:].isdigit():
        return dc.replace(V28, v29_util_tanh_t=float(name[1:]))   # Candidate A: win-shape T
    if name == "Bmild":
        return dc.replace(V28, v29_meeple_curve=MILD_CURVE)
    if name == "Baggr":
        return dc.replace(V28, v29_meeple_curve=AGGR_CURVE)
    if name == "Bk1":
        return dc.replace(V28, meeple_k=1.0)                  # flat-k control
    if name == "Bk3":
        return dc.replace(V28, meeple_k=3.0)
    # combos: "A16+Bmild"
    if "+" in name:
        cfg = V28
        for part in name.split("+"):
            sub = candidate_cfg(part)
            for f in ("v29_util_tanh_t", "v29_meeple_curve", "meeple_k"):
                v = getattr(sub, f)
                if v != getattr(V28, f):
                    cfg = dc.replace(cfg, **{f: v})
        return cfg
    raise ValueError(f"unknown candidate {name!r}")


@dataclass
class GameResult:
    seed: int
    a_player: int          # seat the candidate (side A) plays
    sims: int
    score_p0: int
    score_p1: int
    diff: int              # candidate - baseline
    won_by_a: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""
    snap_margin: int = 0   # a's score lead when deck first <= K_SNAPSHOT (pre-endgame)
    snap_ply: int = -1


def _result_path(out: Path, sims: int, seed: int, a_player: int) -> Path:
    return out / f"s{sims:04d}_seed{seed:06d}_a{a_player}.json"


def _try_load(p: Path):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p: Path, r: GameResult):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.stem + ".partial.json")
    json.dump(asdict(r), open(tmp, "w"))
    tmp.replace(p)


_W = {"shared_claim": False, "claim_host": "", "stale": 5400, "cand": None, "base": None}


def _worker_init(shared_claim, claim_host, stale, cand_cfg, base_cfg):
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["stale"] = stale
    _W["cand"] = cand_cfg
    _W["base"] = base_cfg


def _make_sides(seed, sims):
    game_a = Game(enable_legal_moves_cache=True)
    game_b = Game(enable_legal_moves_cache=True)
    a = HeuristicMCTS(game=game_a, simulations=sims, seed=seed, heur_leaf="v2_7", leaf_cfg=_W["cand"])
    b = HeuristicMCTS(game=game_b, simulations=sims, seed=seed + 1, heur_leaf="v2_7", leaf_cfg=_W["base"])
    return game_a, a, b


def _play_one(args) -> GameResult | None:
    out_str, seed, a_player, sims = args
    out = Path(out_str)
    p = _result_path(out, sims, seed, a_player)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _W["shared_claim"]:
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["stale"]):
            return None

    import random
    random.seed(seed)
    game, a_mcts, b_mcts = _make_sides(seed, sims)
    board = game.get_init_board()
    dh = deck_hash(board)

    t0 = time.perf_counter()
    moves = 0
    snap_margin, snap_ply = 0, -1
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mcts = a_mcts if cur == a_player else b_mcts
        mcts.clear()
        action = mcts.best_action(board)
        board, _ = game.get_next_state(board, action)
        moves += 1
        if snap_ply < 0 and len(board.state.deck) <= K_SNAPSHOT:
            s0, s1 = board.state.scores
            snap_margin = int((s0 - s1) if a_player == 0 else (s1 - s0))
            snap_ply = moves
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_player == 0 else (s1 - s0)
    r = GameResult(seed=seed, a_player=a_player, sims=sims, score_p0=int(s0), score_p1=int(s1),
                   diff=int(diff), won_by_a=(diff > 0), drew=(diff == 0),
                   elapsed_s=elapsed, moves=moves, deck_hash=dh,
                   snap_margin=snap_margin, snap_ply=snap_ply)
    _save(p, r)
    return r


def _summary(results, sims, candidate):
    import math
    n = len(results)
    w = sum(1 for r in results if r.won_by_a)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    avg = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    # paired z on the score margin (per-game diff is already candidate - baseline)
    import statistics
    mean = avg
    sd = statistics.pstdev([r.diff for r in results]) if n > 1 else 0.0
    z = (mean / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    print()
    print(f"=== v2.9[{candidate}] vs v2.8 @ sims={sims} ===")
    print(f"games:  {n}   candidate: {w}W / {d}D / {losses}L   winrate {wr:.3f}")
    print(f"avg score diff (cand - base): {avg:+.2f}   paired z(margin): {z:+.2f}")
    print(f"ELO: {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    # pre-endgame lead split (snapshot at <=K_SNAPSHOT tiles — pre-outcome, not a collider)
    def bucket(m):
        if m <= -5: return "behind"
        if m >= 20: return "blowout_ahead"
        if abs(m) <= 4: return "even"
        return "ahead"
    from collections import defaultdict
    bb = defaultdict(list)
    for r in results:
        bb[bucket(r.snap_margin)].append(r)
    print(f"  pre-endgame split (snapshot at deck<={K_SNAPSHOT}):")
    for k in ("behind", "even", "ahead", "blowout_ahead"):
        sub = bb.get(k, [])
        if sub:
            sw = (sum(1 for r in sub if r.won_by_a) + 0.5 * sum(1 for r in sub if r.drew)) / len(sub)
            sa = sum(r.diff for r in sub) / len(sub)
            print(f"    {k:14} n={len(sub):4}  wr={sw:.3f}  avg_diff={sa:+.2f}")
    if abs(elo) <= 35 and not math.isnan(elo_sig):
        print(f"  POWER NOTE: |elo|<=35 at n={n} (1σ≈±{elo_sig:.0f}); a >=0.53 verdict needs n>=400.")


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))
    return work


def _git_commit():
    try:
        return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_v29_vs_v28")
    ap.add_argument("--candidate", required=True, help="A8/A12/A16/A24/A32/A48/Bmild/Baggr/Bk1/Bk3/A16+Bmild/v28")
    ap.add_argument("--baseline", default="v28")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=ep.EVAL_SEED_FLOOR)
    ap.add_argument("--allow-selfplay-seeds", action="store_true")
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--out-root", type=str, default=None)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=5400)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n")

    cand_cfg = candidate_cfg(args.candidate)
    base_cfg = candidate_cfg(args.baseline)
    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    sub = args.out_subdir or f"v29_{args.candidate}_vs_{args.baseline}_s{args.sims}"
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    tasks = [(str(out), seed, a_player, args.sims)
             for seed, a_player in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, args.sims, t[1], t[2]))) is not None]
        if results:
            _summary(results, args.sims, args.candidate)
        else:
            print("no cached results yet")
        return 0

    # provenance manifest: full resolved LeafConfig (both sides) + git + win-shape flag.
    write_manifest(out, kind="eval_v29_vs_v28", game=game_tag(Game()),
                   config={"n": args.n, "sims": args.sims, "paired": args.paired,
                           "seed_start": args.seed_start, "k_snapshot": K_SNAPSHOT,
                           "candidate": args.candidate, "baseline": args.baseline,
                           "git_commit": _git_commit(),
                           "leaf_version": "v29_experimental",
                           "win_shaped": cand_cfg.v29_util_tanh_t > 0.0,
                           "cand_cfg": {k: (list(v) if isinstance(v, tuple) else v)
                                        for k, v in asdict(cand_cfg).items()},
                           "base_cfg": {k: (list(v) if isinstance(v, tuple) else v)
                                        for k, v in asdict(base_cfg).items()}},
                   evaluator=None, overwrite=True)

    todo = [t for t in tasks if not _result_path(out, args.sims, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"v29[{args.candidate}] vs [{args.baseline}]: n={args.n} sims={args.sims} | "
          f"{len(tasks)-len(todo)} cached, {len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        with Pool(processes=workers, initializer=_worker_init,
                  initargs=(args.shared_claim, args.claim_host, args.claim_stale_secs,
                            cand_cfg, base_cfg)) as pool:
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
        p = _result_path(out, args.sims, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_player == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    if results:
        _summary(results, args.sims, args.candidate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
