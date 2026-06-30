#!/usr/bin/env python3
"""Step 0(b) — determinization-averaged vs single-determinization value-target probe.

Charter §7 Step 0 (F-B2): does the value head look "inert" partly because the
self-play value target is a CLAIRVOYANT single-determinization outcome — i.e. the
result under ONE realized deck order, which the board cannot reveal, so a chunk of
the target is irreducible deck-noise the net can never fit?

Method (cheap, local, no cluster, no net):
  * sample N roots from the existing 10,067 h6400_v2.9 sets (probe.jsonl seed+ply);
  * for each root, draw K determinizations of the UNSEEN deck (reshuffle state.deck,
    keep next_tile) and play a FIXED greedy policy (RuleBasedPlayer, fixed tiebreak
    seed) to terminal → POV value tanh((s_pov - s_opp)/15) per determinization;
  * SINGLE target = one determinization (k=0); AVG target = mean over K.

Two read-outs:
  (A) VARIANCE DECOMPOSITION (decisive, no training): between-root Var(avg) = the
      predictable-from-board signal; mean within-root Var = the irreducible per-deck
      noise. A value head trained on SINGLE targets has an MSE floor = the within-root
      noise; its corr ceiling = sqrt(between/(between+within)). If within << between,
      single-det contamination is negligible → proceed to Step 1 as planned. If
      within dominates, the "inert" verdict is partly target-noise → pull Step 4
      (fair-information targets) earlier.
  (B) TRAIN-TWO-HEADS (pre-registered): train the small ValCNN (reused from
      probe_value_head_c4.py) on SINGLE vs AVG targets; compare held-out corr/MSE
      against the held-out AVG target (the lowest-variance truth we have). single ≈
      avg ⇒ contamination ruled out.

Caveat (logged, per the 2026-06-04 probe house style): the production value target is
the sims=200 NeuralMCTS self-play outcome / search root.Q, NOT the greedy
RuleBasedPlayer outcome used here. Greedy is a fixed, fast, representative policy for
ESTIMATING deck-induced outcome variance; the within/between RATIO is the diagnostic,
not the absolute values. If the verdict is borderline, escalate a subset to h200
playouts.
"""
from __future__ import annotations

import os

# Frozen v2.9 leaf config (matches scripts/rod_v2/value_search/forced_move.py and
# measurement_infra.snapshot.frozen_v29_cfg) so any virtual_score the policy touches
# uses the fast, canonical flat leaf. CPU-only + single-thread per worker.
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import copy
import json
import math
import random
import sys
import time
from multiprocessing import get_context
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

from gen_endgame_positions import replay_to  # noqa: E402  (deck_seed+ply -> board)

PROBE = REPO / "measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl"
OUT = REPO / "measurement/step0_determinization"

_W: dict = {}


def _worker_init(max_plies: int):
    from carcassonne_ai.rule_based_player import RuleBasedPlayer

    _W["RuleBasedPlayer"] = RuleBasedPlayer
    _W["max_plies"] = max_plies


def _playout_value(game, root_board, pov: int, deck_seed: int, max_plies: int) -> float:
    """Reshuffle the UNSEEN deck (deterministic in deck_seed), play fixed greedy to
    terminal, return tanh((s_pov - s_opp)/15) from the ROOT player's POV."""
    b = copy.deepcopy(root_board)
    rng = random.Random(deck_seed)
    rng.shuffle(b.state.deck)          # contents preserved, order randomized
    b._str_repr_cache = None
    player = _W["RuleBasedPlayer"](seed=70123)   # fixed tiebreak -> only deck varies
    steps = 0
    while game.get_game_ended(b, 0) == 0.0 and steps < max_plies:
        mask = game.get_valid_moves(b)
        if int(mask.sum()) == 0:
            break
        a = player.choose_action(game, b, mask)
        b, _ = game.get_next_state(b, int(a))
        steps += 1
    s = b.state.scores
    return float(math.tanh((s[pov] - s[1 - pov]) / 15.0))


def process_root(rec):
    """Return (obs f16, scalars f16, outcomes[K] f32, phase, pov, legal_n)."""
    try:
        from carcassonne_ai.game_wrapper import Game  # noqa: F401 (replay_to builds it)

        seed = int(rec["seed"])
        ply = int(rec["ply"])
        K = int(rec["_K"])
        game, board = replay_to(seed, ply)
        pov = int(board.state.current_player)
        obs, scalars = game.get_canonical_form(board, pov)
        max_plies = _W["max_plies"]
        outs = np.array(
            [_playout_value(game, board, pov, seed * 1000 + k, max_plies) for k in range(K)],
            dtype=np.float32,
        )
        return {
            "obs": obs.astype(np.float16),
            "scalars": scalars.astype(np.float16),
            "outcomes": outs,
            "phase": rec.get("phase", "?"),
            "pov": pov,
            "legal_n": int(rec.get("legal_n", -1)),
        }
    except Exception as e:  # fail loud per-root, keep the batch alive
        return {"error": f"{type(e).__name__}: {e}", "seed": rec.get("seed")}


def load_roots(n: int, K: int, rng_seed: int):
    recs = [json.loads(l) for l in PROBE.read_text().splitlines() if l.strip()]
    rng = np.random.default_rng(rng_seed)
    # stratify by phase so opening/endgame deck-variance are both represented
    by_phase: dict[str, list] = {}
    for r in recs:
        by_phase.setdefault(r.get("phase", "?"), []).append(r)
    picked = []
    phases = sorted(by_phase)
    per = max(1, n // len(phases))
    for ph in phases:
        pool = by_phase[ph]
        idx = rng.choice(len(pool), size=min(per, len(pool)), replace=False)
        picked.extend(pool[i] for i in idx)
    rng.shuffle(picked)
    picked = picked[:n]
    for r in picked:
        r["_K"] = K
    return picked


# ---- (B) train-two-heads: reuse the ValCNN from probe_value_head_c4.py ----
def train_eval_heads(obs, scl, single, avg, epochs, seeds, dev):
    import torch
    import torch.nn as nn

    sys.path.insert(0, str(REPO / "scripts"))
    from probe_value_head_c4 import ValCNN  # the small 3-conv value head

    n = obs.shape[0]
    rng = np.random.default_rng(0)
    order = rng.permutation(n)
    cut = int(n * 0.8)
    tr, va = order[:cut], order[cut:]
    n_scalar = scl.shape[1]

    Btr = torch.from_numpy(obs[tr]).float().to(dev)
    Str = torch.from_numpy(scl[tr]).float().to(dev)
    Bva = torch.from_numpy(obs[va]).float().to(dev)
    Sva = torch.from_numpy(scl[va]).float().to(dev)
    avg_va = avg[va]

    def run(target, label):
        Ttr = torch.from_numpy(target[tr]).float().to(dev)
        cs, ms = [], []
        for s in range(seeds):
            torch.manual_seed(s)
            net = ValCNN(obs.shape[1], n_scalar=n_scalar).to(dev)
            opt = torch.optim.Adam(net.parameters(), lr=1e-3)
            lossf = nn.MSELoss()
            for _ in range(epochs):
                net.train()
                perm = torch.randperm(Btr.shape[0], device=dev)
                for i in range(0, Btr.shape[0], 256):
                    j = perm[i:i + 256]
                    opt.zero_grad()
                    lossf(net(Btr[j], Str[j]), Ttr[j]).backward()
                    opt.step()
            net.eval()
            with torch.no_grad():
                pred = net(Bva, Sva).cpu().numpy()
            # score vs the held-out AVG target (lowest-variance truth)
            cs.append(float(np.corrcoef(pred, avg_va)[0, 1]))
            ms.append(float(np.mean((pred - avg_va) ** 2)))
        print(f"  head[{label}] vs AVG-truth: corr={np.mean(cs):+.3f}±{np.std(cs):.3f} "
              f"MSE={np.mean(ms):.4f}±{np.std(ms):.4f} (seeds={seeds})")
        return float(np.mean(cs)), float(np.mean(ms))

    return {"single": run(single, "SINGLE"), "avg": run(avg, "AVG")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--K", type=int, default=12)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--max-plies", type=int, default=200)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--rng-seed", type=int, default=12345)
    ap.add_argument("--tag", default="full")
    ap.add_argument("--no-train", action="store_true",
                    help="skip the GPU train-two-heads (for CPU-only shard boxes; "
                         "training stays on the local box). Still saves arrays + "
                         "variance decomposition.")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    roots = load_roots(args.n, args.K, args.rng_seed)
    print(f"[step0b] {len(roots)} roots, K={args.K}, workers={args.workers}, "
          f"max_plies={args.max_plies}")

    ctx = get_context("spawn")
    results = []
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=(args.max_plies,)) as pool:
        for i, r in enumerate(pool.imap_unordered(process_root, roots, chunksize=8)):
            results.append(r)
            if (i + 1) % 50 == 0:
                el = time.time() - t0
                print(f"  {i+1}/{len(roots)} roots  ({el:.0f}s, {(i+1)/el:.1f} roots/s)")

    errs = [r for r in results if "error" in r]
    ok = [r for r in results if "error" not in r]
    if errs:
        print(f"[step0b] {len(errs)} root errors (showing 3): "
              f"{[e['error'] for e in errs[:3]]}")
    print(f"[step0b] {len(ok)} roots OK in {time.time()-t0:.0f}s")

    outcomes = np.stack([r["outcomes"] for r in ok])     # (N, K)
    obs = np.stack([r["obs"] for r in ok])               # (N, C, W, W)
    scl = np.stack([r["scalars"] for r in ok])           # (N, S)
    single = outcomes[:, 0].astype(np.float32)
    avg = outcomes.mean(axis=1).astype(np.float32)
    within = outcomes.var(axis=1, ddof=1)                # per-root deck variance
    phases = np.array([r["phase"] for r in ok])

    between = float(np.var(avg, ddof=1))
    mean_within = float(np.mean(within))
    total = between + mean_within
    corr_ceiling_single = math.sqrt(between / total) if total > 0 else float("nan")
    # SINGLE vs AVG target agreement directly (what the head is asked to predict)
    single_avg_corr = float(np.corrcoef(single, avg)[0, 1])

    print("\n========== (A) VARIANCE DECOMPOSITION ==========")
    print(f"  N roots                         : {len(avg)}")
    print(f"  between-root Var(avg target)     : {between:.5f}  (predictable signal)")
    print(f"  mean within-root Var (deck noise): {mean_within:.5f}  (irreducible)")
    print(f"  noise / (signal+noise)           : {mean_within/total:.3f}")
    print(f"  corr ceiling for SINGLE target   : {corr_ceiling_single:.3f}")
    print(f"  corr(single, avg)                : {single_avg_corr:.3f}")
    print("  per-phase mean within-root Var:")
    for ph in sorted(set(phases.tolist())):
        m = phases == ph
        print(f"    {ph:14s} n={int(m.sum()):5d}  within={float(np.mean(within[m])):.5f}  "
              f"between={float(np.var(avg[m], ddof=1)):.5f}")

    dev = "cuda"
    try:
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        dev = "cpu"
    print(f"\n========== (B) TRAIN-TWO-HEADS (dev={dev}) ==========")
    heads = train_eval_heads(obs, scl, single, avg, args.epochs, args.seeds, dev)

    summary = {
        "n_roots": len(avg), "K": args.K, "max_plies": args.max_plies,
        "between_var": between, "mean_within_var": mean_within,
        "noise_fraction": mean_within / total,
        "corr_ceiling_single": corr_ceiling_single,
        "corr_single_avg": single_avg_corr,
        "head_single_corr_mse": heads["single"],
        "head_avg_corr_mse": heads["avg"],
        "policy": "RuleBasedPlayer greedy (proxy; production target is h200 self-play)",
        "n_errors": len(errs),
    }
    (OUT / f"det_probe_{args.tag}.json").write_text(json.dumps(summary, indent=2))
    np.savez_compressed(OUT / f"det_probe_{args.tag}_arrays.npz",
                        outcomes=outcomes, single=single, avg=avg, within=within,
                        phases=phases)
    print(f"\n[step0b] wrote {OUT}/det_probe_{args.tag}.json")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
