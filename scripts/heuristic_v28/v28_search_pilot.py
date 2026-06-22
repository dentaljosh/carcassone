"""Phase 5 — low-budget paired search pilot: heur@N with a v2.8 leaf vs heur@N with v2.7.

Both sides are PURE HeuristicMCTS at MATCHED sims; side A uses a v2.8 LeafConfig (via the new
HeuristicMCTS leaf_cfg= threading), side B uses v2.7 (leaf_cfg=None == DEFAULT_CONFIG). The Elo of
A over B IS the v2.8-vs-v2.7 leaf gain at that search depth. No net, no orchestrator (CPU-bound →
keep workers <= threads). Deck-paired, balanced seats, per-game JSON checkpoint (resumable).

Mirrors scripts/eval_heur_vs_heur.py. Measurement only — champion + production unchanged.

Usage:
  python -u scripts/heuristic_v28/v28_search_pilot.py --variant v28_completion --n 200 --sims 200 \
      --paired --workers 14 --out-root /mnt/c/carc-shared/v28_pilot
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "heuristic_v28"))
import v28_configs; v28_configs.set_prod_env()
from carcassonne_ai.game_wrapper import Game           # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS           # noqa: E402

_VARIANT_NAME = None
_VARIANT_CFG = None


@dataclass
class GameResult:
    seed: int
    a_player: int
    sims: int
    score_p0: int
    score_p1: int
    diff: int            # v2.8(A) - v2.7(B)
    won_by_a: bool
    drew: bool
    elapsed_s: float
    moves: int


def _result_path(out: Path, sims, seed, a_player):
    return out / f"s{sims:04d}_seed{seed:09d}_a{a_player}.json"


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


def _worker_init(variant_name, sims_b=None):
    global _VARIANT_NAME, _VARIANT_CFG, _SIMS_B
    _VARIANT_NAME = variant_name
    _VARIANT_CFG = v28_configs.build_variants([variant_name])[variant_name]
    _SIMS_B = sims_b


_SIMS_B = None  # side-B sims override (cross-depth anchor); None -> same as side A


def _make_sides(seed, sims):
    """Side A = v2.8 variant leaf @ sims; side B = v2.7 leaf @ (_SIMS_B or sims)."""
    ga, gb = Game(enable_legal_moves_cache=True), Game(enable_legal_moves_cache=True)
    sims_b = _SIMS_B if _SIMS_B else sims
    a = HeuristicMCTS(game=ga, simulations=sims, seed=seed, heur_leaf="v2_7", leaf_cfg=_VARIANT_CFG)
    b = HeuristicMCTS(game=gb, simulations=sims_b, seed=seed + 1, heur_leaf="v2_7", leaf_cfg=None)
    return ga, a, b


def _play_one(args):
    out_str, seed, a_player, sims = args
    out = Path(out_str)
    p = _result_path(out, sims, seed, a_player)
    c = _try_load(p)
    if c is not None:
        return c
    import random
    random.seed(seed)
    game, a_mcts, b_mcts = _make_sides(seed, sims)
    board = game.get_init_board()
    t0 = time.perf_counter(); moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mcts = a_mcts if cur == a_player else b_mcts
        mcts.clear()
        board, _ = game.get_next_state(board, mcts.best_action(board))
        moves += 1
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_player == 0 else (s1 - s0)
    r = GameResult(seed=seed, a_player=a_player, sims=sims, score_p0=int(s0), score_p1=int(s1),
                   diff=int(diff), won_by_a=(diff > 0), drew=(diff == 0),
                   elapsed_s=time.perf_counter() - t0, moves=moves)
    _save(p, r)
    return r


def _summary(results, sims, variant):
    n = len(results)
    w = sum(1 for r in results if r.won_by_a)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    avg = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    # paired margin z (per-game diff): mean / (sd/sqrt(n))
    diffs = [r.diff for r in results]
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    zmargin = (mean / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    print(f"\n=== {variant} (A) vs v2.7 (B), HeuristicMCTS @ sims={sims}, n={n} ===")
    print(f"A: {w}W / {d}D / {losses}L   winrate {wr:.3f}")
    print(f"avg score diff (A - B): {avg:+.2f}   paired margin z = {zmargin:+.2f}")
    print(f"ELO (A vs B): {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    note = ("VERDICT-RANGE" if (not math.isnan(elo_sig) and abs(elo) > 2 * elo_sig) else "INCONCLUSIVE")
    print(f"signal: {note}  (n={n} paired; |z_margin|>2 => reliable per-game margin)")
    return {"variant": variant, "sims": sims, "n": n, "W": w, "D": d, "L": losses,
            "winrate": round(wr, 4), "avg_diff": round(avg, 3), "z_margin": round(zmargin, 3),
            "elo": round(elo, 1), "elo_1sig": (round(elo_sig, 1) if not math.isnan(elo_sig) else None),
            "signal": note}


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0)); work.append((seed_start + i, 1))
    return work


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help="v2.8 variant name from V28_VARIANT_CONFIGS.json")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--sims-b", type=int, default=None, help="side-B (v2.7) sims override for the cross-depth anchor; default = --sims")
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed-start", type=int, default=1_700_000_000)  # distinct namespace; not selfplay seeds
    ap.add_argument("--out-root", type=str, default=str(REPO / "data" / "v28_pilot"))
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2:
        ap.error("--paired requires even --n")

    cfg = v28_configs.build_variants([args.variant])[args.variant]
    _suffix = f"s{args.sims}" if not args.sims_b else f"s{args.sims}_vs_v27s{args.sims_b}"
    out = Path(args.out_root) / f"{args.variant}_vs_v27_{_suffix}"
    out.mkdir(parents=True, exist_ok=True)
    # manifest
    spec = v28_configs.load_spec()["variants"][args.variant]
    json.dump({"variant": args.variant, "patch": spec["patch"], "overrides": spec["overrides"],
               "sims": args.sims, "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
               "base_env": v28_configs.PROD_ENV, "side_A": "heur@%d v2.8" % args.sims,
               "side_B": "heur@%d v2.7" % args.sims},
              open(out / "manifest.json", "w"), indent=2)

    tasks = [(str(out), seed, ap_, args.sims) for seed, ap_ in _build_work(args.seed_start, args.n, args.paired)]
    if args.summary_only:
        res = [r for t in tasks if (r := _try_load(_result_path(out, args.sims, t[1], t[2]))) is not None]
        if res:
            json.dump(_summary(res, args.sims, args.variant), open(out / "result.json", "w"), indent=2)
        else:
            print("no cached results")
        return 0

    todo = [t for t in tasks if not _result_path(out, args.sims, t[1], t[2]).exists()]
    print(f"v28 search pilot: {args.variant} vs v2.7, n={args.n} sims={args.sims} | "
          f"{len(tasks)-len(todo)} cached, {len(todo)} to play, W={args.workers}, out={out}", flush=True)
    results = []
    if todo:
        t0 = time.perf_counter()
        with Pool(args.workers, initializer=_worker_init, initargs=(args.variant, args.sims_b)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                results.append(r); done += 1
                if done % 20 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} ({el/done:.1f}s/game, ~{(len(todo)-done)*el/done/60:.1f} min left)", flush=True)
    for t in tasks:
        p = _result_path(out, args.sims, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_player == t[2] for r in results):
            cc = _try_load(p)
            if cc:
                results.append(cc)
    if results:
        summ = _summary(results, args.sims, args.variant)
        json.dump(summ, open(out / "result.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
