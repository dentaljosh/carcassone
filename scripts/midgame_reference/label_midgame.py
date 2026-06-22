#!/usr/bin/env python3
"""Midgame reference (Phase 3) — create separately-kept reference labels for each position.

NO exact solver exists at midgame K. Labels (all kept distinct, NONE called ground truth):
  - deep-search TEACHER: heur@800/1600/3200, from ONE incrementally-deepened tree (same seed →
    the first 800 sims of a 3200 budget are byte-identical to an independent heur@800 run, so the
    per-budget choices match independent agents exactly, at 3200 sims total not 5600). Records
    each budget's choice + heur@3200 root child mover-Q + visits → teacher-confidence gap.
  - learned AGENT: iter8 NeuralMCTS@200 choice (production knobs) + iter8 raw policy-prior argmax.
  - static: v2.7-depth-0 best action (argmax virtual_score_v2 over legal afterstates).

All search descends the REAL fixed deck order (clairvoyant-leaning; flagged). Net on CPU per
worker (CUDA_VISIBLE_DEVICES="") — the desktop-friendly throughput-scales-with-workers pattern.

In : MIDGAME_POSITION_SAMPLE.jsonl (Phase 1)
Out: MIDGAME_REFERENCE_LABELS.jsonl + REFERENCE_LABELS_MANIFEST.md
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")   # net on CPU; throughput scales with workers
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import dataclasses as dc
import json
import random
import sys
import time
from collections import Counter
from multiprocessing import get_context

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))

from carcassonne_ai.game_wrapper import Game                          # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS             # noqa: E402
from carcassonne_ai.virtual_score_v2 import virtual_score_v2, DEFAULT_CONFIG  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase      # noqa: E402

CKPT = "/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt"
_W: dict = {}


def _worker_init(ckpt):
    import torch
    torch.set_num_threads(1)
    from carcassonne_ai.network import CarcassonneNet
    from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
    dev = torch.device("cpu")
    ck = torch.load(ckpt, map_location=dev, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"], n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
    net.load_state_dict(ck["model_state"]); net.train(False)
    _W["net"], _W["dev"], _W["ns"] = net, dev, ns
    game_farm = Game(enable_legal_moves_cache=True, include_farm_scalars=(ns > 10))
    _W["base"] = make_single_evaluator(net, dev, game_farm)
    _W["leaf"] = make_v25_value_wrapper(_W["base"], dc.replace(DEFAULT_CONFIG, residual_scale=0.25))


def _replay(seed, prefix, include_farm):
    random.seed(seed)
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    b = g.get_init_board()
    for a in prefix:
        b, _ = g.get_next_state(b, int(a))
    return g, b


def _mover_child_stats(mcts, board):
    """root child {action: mover-perspective Q}, {action: visits} (dedup transposition collisions)."""
    root = mcts._nodes.get(mcts.game.string_representation(board))
    q, n = {}, {}
    if root is None:
        return q, n
    seen = set()
    for a in sorted(root.children):
        c = root.children[a]
        if id(c) in seen:
            continue
        seen.add(id(c))
        qv = c.Q if c.player_to_move == root.player_to_move else -c.Q
        q[a] = round(float(qv), 5)
        n[a] = int(c.N)
    return q, n


def _gap(qmap):
    """best-minus-second mover-Q over root children (teacher confidence). None if <2 children."""
    if len(qmap) < 2:
        return None
    vals = sorted(qmap.values(), reverse=True)
    return round(vals[0] - vals[1], 5)


def _process(pos):
    try:
        seed = (pos["source_game_seed"] * 131 + pos["ply"]) & 0x7FFFFFFF
        ns = _W["ns"]
        game, board = _replay(pos["source_game_seed"], pos["prefix"], include_farm=(ns > 10))
        mover = board.state.current_player

        # ---- deep-search teacher: one incrementally-deepened heur tree -> 800/1600/3200 ----
        hm = HeuristicMCTS(game=game, simulations=800, seed=seed, heur_leaf="v2_7")
        hm.search(board); c800 = hm.best_action(board)            # 800 sims done
        hm.search(board); c1600 = hm.best_action(board)           # 1600
        hm.search(board); hm.search(board); c3200 = hm.best_action(board)  # 3200
        q3200, v3200 = _mover_child_stats(hm, board)

        # ---- learned agent: iter8 policy prior + MCTS@200 ----
        prior, _val = _W["base"](board)
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
        prior_arg = int(legal[int(np.argmax([prior[a] for a in legal]))])
        nm = NeuralMCTS(game=game, evaluator=_W["leaf"], simulations=200, seed=seed, c_puct=3.0)
        iter8_choice = int(nm.best_action(board))

        # ---- static v2.7-depth-0 best (argmax virtual_score_v2 over legal afterstates) ----
        best_v27, v27_arg = None, None
        for a in legal:
            child, _ = game.get_next_state(board, int(a))
            v = virtual_score_v2(child.state, mover, DEFAULT_CONFIG)
            if best_v27 is None or v > best_v27:
                best_v27, v27_arg = v, int(a)

        return {
            "position_id": pos["position_id"], "source_bucket": pos["source_bucket"],
            "band": pos["band"], "k_remaining": pos["k_remaining"], "to_move": mover,
            "n_legal": int(len(legal)),
            "clairvoyance": "real_deck_order",      # search descends the fixed deck; NOT fair-info
            # teacher (deep heuristic):
            "heur800_choice": int(c800), "heur1600_choice": int(c1600), "heur3200_choice": int(c3200),
            "heur3200_child_q": {str(k): val for k, val in q3200.items()},
            "heur3200_visits": {str(k): val for k, val in v3200.items()},
            "teacher_gap_q": _gap(q3200),                          # best-vs-2nd mover-Q (confidence)
            "shallow_deep_agree": bool(c800 == c3200),
            "ladder_agree": bool(c800 == c1600 == c3200),
            # learned agent:
            "iter8_choice": iter8_choice, "iter8_prior_argmax": prior_arg,
            # static:
            "v27_static_choice": v27_arg,
        }
    except Exception as e:
        return {"_error": f"{pos['position_id']}: {type(e).__name__}: {e}"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(REPO, "measurement", "midgame_reference"))
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0, help="0=all; else first N (smoke)")
    args = ap.parse_args(argv)

    positions = [json.loads(l) for l in open(os.path.join(args.dir, "MIDGAME_POSITION_SAMPLE.jsonl"))]
    if args.limit:
        positions = positions[:args.limit]
    print(f"[phase3] {len(positions)} positions, W={args.workers}, ckpt={args.ckpt}", flush=True)

    t0 = time.perf_counter()
    ctx = get_context("fork")
    results = []
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=(args.ckpt,)) as pool:
        done = 0
        for r in pool.imap_unordered(_process, positions, chunksize=4):
            results.append(r); done += 1
            if done % 100 == 0:
                el = time.perf_counter() - t0
                print(f"  {done}/{len(positions)} ({el/done:.2f}s/pos, ~{(len(positions)-done)*el/done/60:.1f} min left)", flush=True)

    errors = [r for r in results if "_error" in r]
    lines = [r for r in results if "_error" not in r]
    lines.sort(key=lambda x: (-x["k_remaining"], x["source_bucket"], x["position_id"]))
    out_path = os.path.join(args.dir, "MIDGAME_REFERENCE_LABELS.jsonl")
    with open(out_path, "w") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")

    # manifest (markdown, per the brief)
    n = len(lines)
    agree_id_t = sum(1 for ln in lines if ln["iter8_choice"] == ln["heur3200_choice"]) / n if n else 0
    agree_v27_t = sum(1 for ln in lines if ln["v27_static_choice"] == ln["heur3200_choice"]) / n if n else 0
    agree_prior_mcts = sum(1 for ln in lines if ln["iter8_prior_argmax"] == ln["iter8_choice"]) / n if n else 0
    shallow_deep = sum(1 for ln in lines if ln["shallow_deep_agree"]) / n if n else 0
    by_band = Counter(ln["band"] for ln in lines)
    el = time.perf_counter() - t0
    md = [
        "# Phase 3 — Reference Labels Manifest", "",
        "> **No exact solver at midgame K.** These are separately-kept reference labels; **none is",
        "> ground truth.** All search descends the **real fixed deck order** → clairvoyant-leaning",
        "> (flagged `clairvoyance: real_deck_order` on every row). Strongest practical ruler =",
        "> heur@3200; `teacher_gap_q` (best−2nd mover-Q at the root) is its confidence.", "",
        f"- built_by: `scripts/midgame_reference/label_midgame.py`  ·  ckpt: `{args.ckpt}`",
        f"- positions labelled: **{n}**  ·  errors: {len(errors)}  ·  wall: {el/60:.1f} min @ W={args.workers}",
        f"- by band: {dict(by_band)}", "",
        "## Label kinds (kept distinct)", "",
        "| label | source | semantics |",
        "|---|---|---|",
        "| `heur800/1600/3200_choice` | HeuristicMCTS v2.7 leaf, incremental same-seed tree | deep-search TEACHER root choice at each budget |",
        "| `heur3200_child_q` / `_visits` | heur@3200 root | mover-perspective Q + visit counts per legal action |",
        "| `teacher_gap_q` | heur@3200 | best−2nd mover-Q = teacher confidence (None if <2 children) |",
        "| `shallow_deep_agree` / `ladder_agree` | heur 800 vs 3200 / all three | does deeper search change the pick |",
        "| `iter8_choice` | NeuralMCTS@200, c_puct=3.0, residual_scale=0.25 | production AGENT choice |",
        "| `iter8_prior_argmax` | net policy head, 1 forward | raw learned-policy choice (no search) |",
        "| `v27_static_choice` | argmax virtual_score_v2 over legal afterstates | STATIC depth-0 heuristic |",
        "", "## Headline agreements (FACT)", "",
        f"- iter8 (MCTS@200) vs heur@3200 teacher: **{agree_id_t:.3f}** top-1 agreement",
        f"- v2.7-static vs heur@3200 teacher: **{agree_v27_t:.3f}**",
        f"- iter8 policy-prior vs iter8 MCTS@200 (search adds how much): **{agree_prior_mcts:.3f}** agree",
        f"- shallow (heur@800) vs deep (heur@3200) agree: **{shallow_deep:.3f}** (1−this = deeper search flips the pick)",
        "",
        "Interpretation lives in MIDGAME_BASELINE_RESULTS.md / MIDGAME_REFERENCE_REPORT.md; this file is FACT only.",
    ]
    with open(os.path.join(args.dir, "REFERENCE_LABELS_MANIFEST.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")

    print(f"[phase3] wrote {n} labels -> {out_path} ({el/60:.1f} min)", flush=True)
    print(f"[phase3] iter8-vs-teacher={agree_id_t:.3f} v27static-vs-teacher={agree_v27_t:.3f} "
          f"prior-vs-mcts={agree_prior_mcts:.3f} shallow-deep-agree={shallow_deep:.3f}", flush=True)
    if errors:
        print(f"[phase3] ERRORS ({len(errors)}): {[e['_error'] for e in errors[:5]]}", flush=True)


if __name__ == "__main__":
    main()
