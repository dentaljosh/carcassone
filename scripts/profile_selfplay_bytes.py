#!/usr/bin/env python3
"""Bytes/sim diagnostic for the self-play hot path — find the DOMINANT DRAM-traffic
consumer BEFORE committing to a big rewrite (so we don't repeat the flat-leaf miss:
optimizing a non-dominant consumer).

Context: production self-play is RAM-BANDWIDTH-bound (DECISIONS 2026-06-09). The flat
leaf cut leaf COMPUTE 2.26x but didn't move the wall => the leaf is NOT the dominant
traffic. The suspects are the MCTS machinery: string transposition keys, state
copy/replay, the 190 KB NN-input encoding (78x25x25 f32), and dense per-node priors
(9.8 KB, A=2511, ~99% zeros). This script attributes ALLOCATION volume + TIME per
component over one real in-process game.

Runs ONE game in-process via play_one_selfplay_game (NOT the mp Pool — cProfile of
run_selfplay_iter misses the worker), at PRODUCTION knobs (sims=200, v2.7 leaf,
value_blend=0, policy-only NN). Reports:
  (A) tracemalloc: top allocation sites grouped by module (proxy for write traffic +
      GC churn — the encoding tensors, string keys, prior arrays, board copies)
  (B) cProfile: cumulative time by function (cross-check; DRAM-stall-heavy code shows
      as high time/low work)

On the laptop (native pop-os, real perf counters) wrap the WHOLE invocation for the
true DRAM number:
  perf stat -e LLC-load-misses,LLC-store-misses,cache-misses,instructions \
    python scripts/profile_selfplay_bytes.py --device cpu --no-cprofile

Usage:
  PYTHONPATH=src:engine python scripts/profile_selfplay_bytes.py [--ckpt P] [--sims 200] [--device cpu|cuda] [--no-cprofile]
"""
from __future__ import annotations

import argparse
import cProfile
import dataclasses
import io
import linecache
import os
import pstats
import sys
import tracemalloc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt")
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=2000000)
    ap.add_argument("--device", default=None, help="cpu|cuda (default: cuda if avail)")
    ap.add_argument("--no-cprofile", action="store_true",
                    help="skip cProfile (perf-stat the whole run instead)")
    ap.add_argument("--topn", type=int, default=25)
    args = ap.parse_args()

    os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
    os.environ.setdefault("CARCASSONNE_V25_CAP", "12")

    import torch
    from carcassonne_ai.evaluators import (
        make_single_evaluator_policy_only,
        make_v25_value_wrapper,
    )
    from carcassonne_ai.features import N_SCALAR_FEATURES
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.network import CarcassonneNet
    from carcassonne_ai.selfplay import play_one_selfplay_game
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    dev = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    ckpt = torch.load(args.ckpt, map_location=dev, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"],
        n_scalar_features=int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES)),
        value_global_pool=bool(ckpt.get("value_global_pool", False)),
    ).to(dev)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)

    game = Game()
    # Production leaf: policy-only NN (value fully from the v2.7 leaf) + v2_5 wrapper,
    # value_blend=0, residual=0 — exactly the gen hot path.
    ev = make_single_evaluator_policy_only(net, dev, game, use_fp16=False)
    leaf_cfg = dataclasses.replace(DEFAULT_CONFIG, value_blend=0.0, residual_scale=0.0)
    ev = make_v25_value_wrapper(ev, cfg=leaf_cfg)

    def one_game():
        return play_one_selfplay_game(
            game=game, evaluator=ev, sims=args.sims, c_puct=args.c_puct,
            dirichlet_alpha=0.3, dirichlet_eps=0.25, temp_threshold=10,
            seed=args.seed, batch_size=1, batch_evaluator=None,
            virtual_loss=1.0, value_target="score_diff",
            interior_min_visits=0, interior_max_per_move=0,
        )

    # warm one move so import/JIT/cache effects don't pollute the measured game
    print(f"device={dev}  sims={args.sims}  ckpt={os.path.basename(args.ckpt)}", flush=True)
    print("warming…", flush=True)
    one_game()

    # (A) allocation attribution
    print("\n=== (A) tracemalloc: allocation by site (one game) ===", flush=True)
    tracemalloc.start(25)
    one_game()
    snap = tracemalloc.take_snapshot()
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"traced current={cur/1e6:.1f} MB  peak={peak/1e6:.1f} MB")

    # group by module bucket so the picture is readable
    BUCKETS = {
        "board_repr": "board_repr", "mcts": "mcts", "flat_leaf": "flat_leaf",
        "virtual_score": "virtual_score", "game_wrapper": "game_wrapper",
        "features": "features", "selfplay": "selfplay", "evaluators": "evaluators",
        "action_space": "action_space",
    }
    by_bucket: dict[str, int] = {}
    for st in snap.statistics("filename"):
        fn = st.traceback[0].filename
        label = "engine" if "/engine/" in fn or "wingedsheep" in fn else "other"
        for key, name in BUCKETS.items():
            if f"/{key}.py" in fn or fn.endswith(f"{key}.py"):
                label = name
                break
        if "torch" in fn or "site-packages" in fn:
            label = "torch/np" if label in ("other", "engine") and "wingedsheep" not in fn else label
        by_bucket[label] = by_bucket.get(label, 0) + st.size
    print(f"\n  {'component':<16} {'live KB':>10}")
    for label, sz in sorted(by_bucket.items(), key=lambda x: -x[1]):
        print(f"  {label:<16} {sz/1024:>10.1f}")

    print(f"\n  top {args.topn} allocation lines:")
    for st in snap.statistics("lineno")[:args.topn]:
        fr = st.traceback[0]
        src = linecache.getline(fr.filename, fr.lineno).strip()[:70]
        short = "/".join(fr.filename.split("/")[-2:])
        print(f"  {st.size/1024:>9.1f} KB  {short}:{fr.lineno}  {src}")

    # (B) time cross-check
    if not args.no_cprofile:
        print("\n=== (B) cProfile: cumulative time by function (one game) ===", flush=True)
        pr = cProfile.Profile()
        pr.enable()
        one_game()
        pr.disable()
        s = io.StringIO()
        pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(args.topn)
        # trim pstats header noise
        for ln in s.getvalue().splitlines():
            if any(k in ln for k in ("board_repr", "mcts", "flat_leaf", "virtual_score",
                                     "game_wrapper", "selfplay", "evaluators",
                                     "function calls", "ncalls", "string_rep",
                                     "deepcopy", "encode")):
                print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
