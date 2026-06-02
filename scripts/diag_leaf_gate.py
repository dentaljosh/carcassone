"""Learned-residual-leaf GATE diagnostic (Phase-4 research decision support).

We're deciding whether to build a "learned-residual leaf" for MCTS:

    leaf = v2.7_heuristic + ε · learned_correction

Before investing, this is a CHEAP gate. On realistic (greedy-played) positions
it records three per-position quantities and answers two questions:

  (A) RESIDUAL SIGNAL — does the deep-search value systematically disagree with
      the raw v2.7 leaf? If `vsearch ≈ v27` everywhere, there's nothing for a
      learned correction to capture. If they diverge meaningfully, there's a
      residual to learn.

  (B) WARMUP / "search corrects toward truth" — does deep search predict the
      eventual game outcome BETTER than the raw leaf (higher corr / lower MSE
      vs outcome)? If so, `vsearch` is a better regression target than the raw
      leaf, i.e. search moves the leaf estimate toward ground truth — exactly
      the signal a residual head would distil.

Three per-position quantities, ALL on the MCTS value scale, ALL from that
position's current-player perspective:

  v27     = the v2.7 heuristic leaf value (leaf_eval="v2_5"), i.e.
            tanh(virtual_score_v2(state, cur_player)/15). Obtained as
            evaluator(board)[1] where `evaluator` is the v2.5-value-wrapped
            single evaluator (priors from the net, value from the leaf).
  vsearch = the MCTS root value after a deep (sims=800) search from that
            position = root node's Q (= W/N), current-player perspective.
  outcome = the eventual normalized game result for that position:
            tanh((p0_score - p1_score)/15) from player 0's POV, sign-flipped
            to the position's current player. This matches the "score_diff"
            value target the self-play loop backfills (see selfplay.py), so
            outcome is on the SAME scale as v27 / vsearch.

Perspective handling: NeuralMCTS roots are canonicalized to the position's
current player, so both `evaluator(board)[1]` and `root.Q` are already in the
current-player frame. `outcome` is computed once per game in player-0 frame and
flipped per recorded position by `+z if player==0 else -z` — identical to
selfplay.py's `values_arr` construction.

Usage (play mode, fan across boxes with disjoint --seed-start ranges sharing
one --out-root subdir; resumable, skips seeds whose result file exists):

  CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 \
  python -u scripts/diag_leaf_gate.py \
      --checkpoint /mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt \
      --n 200 --seed-start 0 --sims 800 --c-puct 3.0 \
      --workers 8 --out-root data/diag_leaf_gate

Summary (aggregates all seed_*.json under the derived subdir):

  python scripts/diag_leaf_gate.py \
      --checkpoint /mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt \
      --sims 800 --c-puct 3.0 --out-root data/diag_leaf_gate --summary-only

Detached (recommended for the real run; --workers handles parallelism, the
cluster launcher handles `nice`):

  nohup python -u scripts/diag_leaf_gate.py [...] \
      > /tmp/diag_leaf_gate.log 2>&1 & disown
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import signal
import sys
import time
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.evaluators import (
    make_single_evaluator,
    make_v25_value_wrapper,
)
from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet


REPO_ROOT = Path(__file__).resolve().parent.parent


# Per-worker globals. CUDA can't survive forks, so the Pool uses 'spawn' and
# each worker re-loads the checkpoint exactly once in _worker_init.
_worker_net: CarcassonneNet | None = None
_worker_device: torch.device | None = None
_worker_cfg: dict | None = None


def _worker_init(checkpoint_path: str, cfg: dict) -> None:
    """Pool initializer: load the priors net once per worker (mirrors
    run_selfplay_iter.py's per-worker, non-orchestrator path)."""
    global _worker_net, _worker_device, _worker_cfg
    _worker_cfg = cfg
    _worker_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(
        checkpoint_path, map_location=_worker_device, weights_only=False
    )
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"],
        n_blocks=ckpt["n_blocks"],
        n_scalar_features=int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES)),
    ).to(_worker_device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    _worker_net = net


def _result_path(out_dir: Path, seed: int) -> Path:
    return out_dir / f"seed_{seed:06d}.json"


def _subdir_name(checkpoint: Path, sims: int, c_puct: float) -> str:
    """Self-describing subdir: checkpoint stem + sims + c (no dot), mirroring
    eval_net_vs_heuristic.py's convention so two configs never collide."""
    return f"{checkpoint.stem}_s{sims}_c{str(c_puct).replace('.', '')}"


def _root_q(mcts: NeuralMCTS, game: Game, board) -> float:
    """Retrieve the ROOT VALUE after a search: the root node's Q (= W/N),
    from the root's current-player perspective. The root node lives in the
    transposition table keyed by string_representation (mcts.py:387)."""
    root_key = game.string_representation(board)
    root = mcts._nodes[root_key]
    return float(root.Q)


def _play_one_pool(args: tuple[int, str]) -> tuple[int, str, int]:
    """Worker entry: skip if cached, else play one full greedy game with
    NeuralMCTS, recording (v27, vsearch) at every position, then backfill the
    normalized outcome per position. Writes one JSON file per seed."""
    seed, out_dir_str = args
    out_dir = Path(out_dir_str)
    path = _result_path(out_dir, seed)
    if path.exists():
        # Already done by a prior run / another box. Trust + skip (resumable).
        return seed, "cached", 0

    cfg = _worker_cfg
    assert cfg is not None and _worker_net is not None and _worker_device is not None

    # The Game must emit the scalar width the checkpoint's value/policy heads
    # expect. Path-B checkpoints (e.g. iter_11) are 12-scalar (farm scalars on);
    # pre-Step-E nets are 10-scalar. main() derives this from the checkpoint and
    # passes it through cfg — a mismatch silently feeds wrong-width scalars and
    # crashes the forward (mat1/mat2 shape error).
    game = Game(
        enable_legal_moves_cache=True,
        include_farm_scalars=cfg.get("include_farm_scalars", False),
    )

    # Build the leaf evaluator EXACTLY as run_selfplay_iter does for
    # leaf_eval="v2_5": full single evaluator (we need the value head present
    # for the wrapper's interface even though the v2.5 wrapper overrides the
    # value), then wrap so the returned value IS the v2.7 leaf. evaluator(b)[1]
    # therefore equals tanh(virtual_score_v2/15) on the MCTS scale,
    # current-player POV. NOT policy_only — we want a real (priors, value)
    # callable, and the wrapper expects one.
    base_ev = make_single_evaluator(_worker_net, _worker_device, game)
    evaluator = make_v25_value_wrapper(base_ev)

    sims = cfg["sims"]
    c_puct = cfg["c_puct"]
    max_plies = cfg.get("max_plies", 400)

    records: list[dict] = []  # one per position, outcome filled in at game end

    board = game.get_init_board()
    ply = 0
    # Greedy, deterministic, strong realistic play: one NeuralMCTS search per
    # move, no Dirichlet noise, pick argmax visit count. We reuse the SAME
    # search both to record vsearch and to choose the move (no double search).
    mcts = NeuralMCTS(
        game=game,
        evaluator=evaluator,
        simulations=sims,
        c_puct=c_puct,
        seed=seed,
        dirichlet_alpha=0.0,
        dirichlet_eps=0.0,
        batch_size=1,
    )

    while game.get_game_ended(board, 0) == 0.0 and ply < max_plies:
        cur_player = int(board.state.current_player)
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break

        # v27: raw v2.7 leaf value at this position (current-player POV).
        v27 = float(evaluator(board)[1])

        # vsearch: deep-search root value. Fresh tree per move so no stale
        # subtree mass leaks across roots (matches selfplay's clear()-per-move).
        mcts.clear()
        mcts.search(board)
        vsearch = _root_q(mcts, game, board)

        records.append(
            {
                "seed": seed,
                "move_index": ply,
                "player": cur_player,
                "v27": v27,
                "vsearch": vsearch,
                # outcome + frac filled after the game ends (need total_moves).
            }
        )

        # Greedy move = argmax visit count among the just-computed root visits.
        counts, actions = mcts.root_visit_distribution(board)
        if counts.sum() <= 0:
            action = int(legal[0])
        else:
            action = int(actions[int(np.asarray(counts).argmax())])

        board, _ = game.get_next_state(board, action)
        ply += 1

    # The game must have terminated for the outcome to be well-defined.
    if game.get_game_ended(board, 0) == 0.0:
        sys.stderr.write(
            f"[seed {seed}] game did not terminate (ply={ply}, "
            f"max_plies={max_plies}); skipping (no valid outcome)\n"
        )
        sys.stderr.flush()
        return seed, "failed", 0

    # outcome: normalized score_diff (player-0 POV), flipped per position's
    # player — identical to selfplay.py's value_target="score_diff" backfill.
    p0_score = int(board.state.scores[0])
    p1_score = int(board.state.scores[1])
    z_p0 = float(np.tanh((p0_score - p1_score) / 15.0))

    total_moves = len(records)
    for r in records:
        r["outcome"] = z_p0 if r["player"] == 0 else -z_p0
        # frac = game-stage position in [0,1): move_index / total_moves.
        r["frac"] = (r["move_index"] / total_moves) if total_moves > 0 else 0.0

    # Atomic-ish write: temp then rename, so a partially-written file is never
    # mistaken for a completed seed by a resuming/work-stealing run.
    tmp = path.with_name(path.stem + ".partial.json")
    with open(tmp, "w") as f:
        json.dump(records, f)
    tmp.rename(path)
    return seed, "fresh", len(records)


# --------------------------------------------------------------------------
# Summary / aggregation
# --------------------------------------------------------------------------

def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation; NaN-safe for degenerate (zero-variance) inputs."""
    if a.size < 2:
        return float("nan")
    sa = a.std()
    sb = b.std()
    if sa == 0.0 or sb == 0.0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _mse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean((a - b) ** 2)) if a.size else float("nan")


def _summarize(out_dir: Path) -> int:
    files = sorted(out_dir.glob("seed_*.json"))
    if not files:
        print(f"No data at {out_dir}")
        return 0

    v27_l: list[float] = []
    vsearch_l: list[float] = []
    outcome_l: list[float] = []
    frac_l: list[float] = []
    n_games = 0
    for f in files:
        try:
            recs = json.load(open(f))
        except Exception as e:
            print(f"  load failed: {f.name}: {e}")
            continue
        n_games += 1
        for r in recs:
            v27_l.append(float(r["v27"]))
            vsearch_l.append(float(r["vsearch"]))
            outcome_l.append(float(r["outcome"]))
            frac_l.append(float(r["frac"]))

    v27 = np.asarray(v27_l, dtype=np.float64)
    vsearch = np.asarray(vsearch_l, dtype=np.float64)
    outcome = np.asarray(outcome_l, dtype=np.float64)
    frac = np.asarray(frac_l, dtype=np.float64)
    n = v27.size
    if n == 0:
        print(f"{out_dir}: {n_games} games but 0 positions")
        return 0

    diff = vsearch - v27
    abs_diff = np.abs(diff)

    print(f"=== diag_leaf_gate summary ===")
    print(f"dir: {out_dir}")
    print(f"games: {n_games}   positions: {n}")
    print()

    # ---------------- GATE: does vsearch disagree with v27? ----------------
    print("--- GATE: residual = vsearch - v27 ---")
    print(f"  mean(vsearch - v27) = {diff.mean():+.4f}")
    print(f"  std (vsearch - v27) = {diff.std():.4f}")
    print(f"  corr(vsearch, v27)  = {_pearson(vsearch, v27):.4f}")
    print(f"  frac |diff| > 0.1   = {float(np.mean(abs_diff > 0.1)):.3f}")
    print(f"  frac |diff| > 0.2   = {float(np.mean(abs_diff > 0.2)):.3f}")
    print()
    print("  by game stage (frac of game elapsed):")
    print(f"    {'stage':<14}{'n':>7}{'mean':>10}{'std':>10}"
          f"{'>0.1':>9}{'>0.2':>9}")
    buckets = [
        ("early (<0.33)", frac < 0.33),
        ("mid (0.33-.66)", (frac >= 0.33) & (frac <= 0.66)),
        ("late (>0.66)", frac > 0.66),
    ]
    for label, m in buckets:
        if not m.any():
            print(f"    {label:<14}{0:>7}{'--':>10}{'--':>10}{'--':>9}{'--':>9}")
            continue
        d = diff[m]
        ad = abs_diff[m]
        print(
            f"    {label:<14}{d.size:>7}{d.mean():>+10.4f}{d.std():>10.4f}"
            f"{float(np.mean(ad > 0.1)):>9.3f}{float(np.mean(ad > 0.2)):>9.3f}"
        )
    print()

    # -------- WARMUP: does vsearch predict outcome better than v27? --------
    corr_v27 = _pearson(v27, outcome)
    corr_vsearch = _pearson(vsearch, outcome)
    mse_v27 = _mse(v27, outcome)
    mse_vsearch = _mse(vsearch, outcome)
    print("--- WARMUP: prediction of eventual outcome ---")
    print(f"  corr(v27,     outcome) = {corr_v27:.4f}")
    print(f"  corr(vsearch, outcome) = {corr_vsearch:.4f}   "
          f"(delta {corr_vsearch - corr_v27:+.4f})")
    print(f"  MSE (v27,     outcome) = {mse_v27:.4f}")
    print(f"  MSE (vsearch, outcome) = {mse_vsearch:.4f}   "
          f"(delta {mse_vsearch - mse_v27:+.4f}; negative = search better)")
    headline = corr_vsearch - corr_v27
    print(f"  HEADLINE: vsearch beats v27 at predicting outcome by "
          f"{headline:+.4f} corr, {mse_v27 - mse_vsearch:+.4f} MSE-reduction")
    print()

    # ---------------------------- VERDICT ----------------------------------
    # Thresholds (printed so the call is auditable):
    #   - Value scale is tanh-bounded [-1, 1]; a "meaningful fraction of the
    #     range" residual std is >= 0.10 (= 5% of the 2.0-wide range, and the
    #     same threshold the gate uses for |diff| bucketing).
    #   - corr margin: vsearch must beat v27 by >= 0.03 Pearson to count as a
    #     "clear margin" (above n-noise at the gate's intended n>=200).
    #   - "none" if vsearch ~= v27 everywhere: residual std < 0.02 (peaked at 0).
    STD_STRONG = 0.10
    STD_NONE = 0.02
    CORR_MARGIN = 0.03
    std_diff = float(diff.std())
    corr_margin = corr_vsearch - corr_v27

    if std_diff < STD_NONE:
        verdict = "none"
        why = (f"std(vsearch-v27)={std_diff:.4f} < {STD_NONE} "
               f"(vsearch ~= v27 everywhere; nothing to learn)")
    elif std_diff >= STD_STRONG and corr_margin >= CORR_MARGIN:
        verdict = "strong"
        why = (f"std(vsearch-v27)={std_diff:.4f} >= {STD_STRONG} AND "
               f"corr margin {corr_margin:+.4f} >= {CORR_MARGIN} "
               f"(search both disagrees with the leaf AND predicts truth better)")
    else:
        verdict = "weak"
        why = (f"std(vsearch-v27)={std_diff:.4f} (strong>={STD_STRONG}, "
               f"none<{STD_NONE}); corr margin {corr_margin:+.4f} "
               f"(clear>={CORR_MARGIN}) — not both conditions met")

    print("--- VERDICT ---")
    print(f"  thresholds: residual std strong>={STD_STRONG}, none<{STD_NONE}; "
          f"corr margin clear>={CORR_MARGIN}")
    print(f"  RESIDUAL SIGNAL: {verdict}")
    print(f"  reason: {why}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Translate SIGTERM/SIGHUP into a clean exit so the Pool context manager
    # tears down workers (mirrors run_selfplay_iter; a dropped held-ssh sends
    # SIGHUP to the remote worker).
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))

    p = argparse.ArgumentParser(prog="diag_leaf_gate")
    p.add_argument("--checkpoint", type=Path, required=True,
                   help="Priors-net checkpoint (e.g. iter_11 or the deepsearch "
                        "net). Provides the MCTS priors; leaf VALUE comes from "
                        "the v2.7 heuristic.")
    p.add_argument("--n", type=int, default=0,
                   help="Number of games to play (one fresh game per seed in "
                        "[seed_start, seed_start+n)). Required in play mode.")
    p.add_argument("--seed-start", type=int, default=0,
                   help="First seed; disjoint ranges fan across boxes into one "
                        "shared --out-root subdir.")
    p.add_argument("--sims", type=int, default=800,
                   help="NeuralMCTS simulations per move (default 800 — the "
                        "deep search whose root value is `vsearch`).")
    p.add_argument("--c-puct", type=float, default=3.0,
                   help="PUCT exploration constant (default 3.0 — the validated "
                        "eval-side value).")
    p.add_argument("--leaf-eval", type=str, default="v2_5", choices=["v2_5"],
                   help="Leaf VALUE source. Only 'v2_5' (the v2.7 heuristic) is "
                        "meaningful for this gate; the whole point is comparing "
                        "search against the v2.7 leaf.")
    p.add_argument("--workers", type=int, default=8,
                   help="Pool workers. CPU v2.7 leaf is CPU-bound per worker; "
                        "keep W <= threads (or W~14-16 on GPU-weaker boxes).")
    p.add_argument("--out-root", type=Path, required=True,
                   help="Root dir; a self-describing subdir is created under it.")
    p.add_argument("--summary-only", action="store_true",
                   help="Aggregate existing seed_*.json and print gate/warmup/"
                        "verdict; do not play.")
    args = p.parse_args(argv)

    sub = _subdir_name(args.checkpoint, args.sims, args.c_puct)
    out_dir = args.out_root / sub

    if args.summary_only:
        return _summarize(out_dir)

    if args.n <= 0:
        p.error("--n must be > 0 in play mode (or pass --summary-only)")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Derive the scalar width from the learner checkpoint so workers build a
    # Game whose get_canonical_form emits scalars matching the net's input
    # width (mirrors run_selfplay_iter.py's include_farm_scalars peek).
    _peek = torch.load(str(args.checkpoint), map_location="cpu", weights_only=False)
    learner_ns = int(_peek.get("n_scalar_features", N_SCALAR_FEATURES))
    include_farm_scalars = learner_ns > N_SCALAR_FEATURES
    del _peek

    seeds = list(range(args.seed_start, args.seed_start + args.n))
    pool_args = [(s, str(out_dir)) for s in seeds]
    already = sum(1 for s in seeds if _result_path(out_dir, s).exists())
    remaining = args.n - already
    n_workers = min(args.workers, remaining or 1)

    cfg = {
        "sims": args.sims,
        "c_puct": args.c_puct,
        "leaf_eval": args.leaf_eval,
        "include_farm_scalars": include_farm_scalars,
    }

    print(
        f"diag_leaf_gate: {args.n} games (sims={args.sims}, c_puct={args.c_puct}, "
        f"leaf_eval={args.leaf_eval}), {n_workers} workers, {already} cached, "
        f"{remaining} to play, out={out_dir}"
    )
    sys.stdout.flush()

    if remaining == 0:
        print("All games cached; nothing to do. Run --summary-only to aggregate.")
        return 0

    t0 = time.perf_counter()
    fresh = cached = failed = 0
    n_pos_total = 0
    first_fresh_t: float | None = None
    ctx = mp.get_context("spawn")

    # Launch the Pool FIRST so parallelism is immediate (verify with ps:
    # N>1 workers should hit >50% CPU within one game-time).
    with ctx.Pool(
        processes=n_workers,
        initializer=_worker_init,
        initargs=(str(args.checkpoint), cfg),
    ) as pool:
        for done, (seed, status, n_positions) in enumerate(
            pool.imap_unordered(_play_one_pool, pool_args, chunksize=1), 1
        ):
            n_pos_total += n_positions
            if status == "fresh":
                fresh += 1
                if first_fresh_t is None:
                    first_fresh_t = time.perf_counter()
                    elapsed = first_fresh_t - t0
                    eta_min = (remaining * elapsed / n_workers) / 60.0
                    print(
                        f"  [ETA] first fresh game took {elapsed:.0f}s; "
                        f"~{eta_min:.1f} min for {remaining} fresh"
                    )
                    sys.stdout.flush()
            elif status == "failed":
                failed += 1
            else:
                cached += 1
            if done % max(1, args.n // 10) == 0 or done == args.n:
                print(
                    f"  ... {done}/{args.n} examined "
                    f"(fresh={fresh}, cached={cached}, failed={failed})"
                )
                sys.stdout.flush()

    elapsed = time.perf_counter() - t0
    print(
        f"\nDone: {fresh} fresh + {cached} cached + {failed} failed, "
        f"{n_pos_total} positions, {elapsed:.1f}s wallclock"
    )
    print("Run with --summary-only to aggregate the gate/warmup/verdict.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
