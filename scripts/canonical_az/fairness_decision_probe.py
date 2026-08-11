#!/usr/bin/env python3
"""Decision-level fairness probe — exact-solver move regret, clairvoyant vs fair.

QUESTION: at the CHAMPION's config (HeuristicMCTS, v2.9 Bmild_cap8 leaf, deep sims),
how much does deck-clairvoyance change/improve DECISIONS — measured as exact-solver
move regret on already-solved roots?  This is the cheap, NON-CIRCULAR first stage of
the fairness-tax measurement: the ground truth is the exact marginalized endgame
solver (real final score-diff leaf, uncorrelated with the v2.9 leaf), and at K<=2
marginalized == clairvoyant, so the truth itself is fair-legit.  A game-level n=400
fair-vs-clair head-to-head is only worth its budget if THIS shows a real tax.

DESIGN (mirrors solver_score.py's root loading/solve; the FAIR arm mirrors the
root-determinization/PIMC pattern of clairvoyance_gap.py::_choose_action and
NeuralMCTS._reshuffled_root, ported to HeuristicMCTS which has no fair_chance flag):

  1. Load the qprobe_A ∩ pool_A sibling roots (the 10,067-root reuse set), filter
     k_remaining<=2 (1,119 roots, all K=2, all marginalized-tractable), seeded
     shuffle, take --n (deterministic subset).
  2. Per root, reconstruct via replay_to(seed, ply), verify checksum, solve exact
     (mode=marginalized).  Then two arms pick a move:
       CLAIR: HeuristicMCTS(sims=S, c=3.0, v2.9 Bmild_cap8 leaf) best_action on the
              TRUE board — the champion's move (simulations descend the true
              state.deck order: the base MCTS is structurally clairvoyant).
       FAIR:  PIMC over K determinizations — each: deepcopy the board, RESHUFFLE
              ONLY the unseen state.deck (multiset preserved; next_tile — the
              already-revealed in-hand tile — untouched; the caller's board never
              mutated: the _reshuffled_root semantics), run a FRESH HeuristicMCTS
              (fresh tree per determinization = no cross-determinization leak, the
              fair_isolate discipline), pool root-child visits across the K trees
              (deduped by child identity, exactly like best_action), pick argmax
              pooled-N (primary, the spec's rule).  A pooled-Q pick (Q=sum sW/sum N,
              N tiebreak — best_action's rule generalized, clairvoyance_gap's
              pooling) is recorded as a secondary read-out so an aggregation-rule
              confound can't hide/fake the verdict.
  3. regret_of(res, move) for both arms (raw points, >=0, mover perspective).

SCOPE CAVEAT (verbatim, by design): at K<=2 the deck has <=1 hidden draw beyond the
current tile — clairvoyance advantage is structurally SMALL here (this measures the
endgame-decision tax, not the midgame tax).  Sharper: at a K=2 TILES-phase root the
unseen deck is a SINGLE tile whose identity is inferable from the public multiset,
so the reshuffle is an identity permutation — at deck_len<=1 the two arms differ
only by search RNG and aggregation (K pooled searches vs one), i.e. the measured
"tax" there is an upper bound on aggregation/noise effects, not hidden information.
deck_len is recorded per root and aggregated so the output states how much of the
sample is in that degenerate regime.

MEASUREMENT ONLY.  Pure CPU, no CUDA.  No champion/PRODUCTION change.

Usage:
  smoke:  python scripts/canonical_az/fairness_decision_probe.py \
              --n 8 --sims 200 --k 3 --workers 4 --out /tmp/smoke.json
  real:   nice -n 19 python scripts/canonical_az/fairness_decision_probe.py \
              --n 300 --sims 1600 --k 8 --workers 10 \
              --out measurement/fairness_probe/fairness_decision_s1600_k8_n300.json
"""
from __future__ import annotations

import os
# v2.9 Bmild_cap8 champion leaf env — MUST precede the carcassonne_ai imports
# (DEFAULT_CONFIG reads these at import).  EXACTLY matches solver_score.py /
# dump_dataset.py; under this env DEFAULT_CONFIG == the PRODUCTION.yaml champion
# leaf_config (curve -8,-4,-1,0,2,3,4,5 + cap 8/8 + meeple_k 2.0), i.e. the same
# LeafConfig eval_v29_vs_v28.candidate_cfg("Bmild_cap8") builds (leaf v2_9_1_Bmild_cap8).
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import copy
import dataclasses
import json
import math
import random
import socket
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import endgame_solver as S                                 # noqa: E402
from gen_endgame_positions import replay_to, k_remaining   # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS              # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

HG = REPO / "measurement" / "high_gap_distillation" / "scaled"
DEFAULT_QPROBE = str(HG / "qprobe_A" / "probe.jsonl")
DEFAULT_POOL = str(HG / "pool_A.jsonl")

MARG_MAX_K = 2      # marginalized tractable (== clairvoyant) — the fair-legit truth
TOP1_TOL = 1e-6     # regret <= tol counts as a solver-optimal pick

SCOPE_NOTE = ("at K<=2 the deck has <=1 hidden draw beyond the current tile — "
              "clairvoyance advantage is structurally SMALL here (this measures the "
              "endgame-decision tax, not the midgame tax)")
DEGENERACY_NOTE = ("at deck_len<=1 the unseen-deck reshuffle is an identity permutation "
                   "(the single hidden tile's identity is inferable from the public "
                   "multiset), so the two arms differ only by search RNG and "
                   "aggregation (K pooled searches vs one) — zero hidden information; "
                   "see deck_len_dist for how much of the sample is in that regime")


# --------------------------------------------------------------------------- #
def load_sibling_roots(qprobe: str, pool: str):
    """qprobe_A (action_q / k_remaining / phase) JOIN pool_A (checksum) on
    (seed, ply).  Copied from solver_score.load_sibling_roots."""
    checks = {}
    for line in open(pool):
        r = json.loads(line)
        checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(qprobe):
        r = json.loads(line)
        key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]
            recs.append(r)
    return recs


def _root_seed(base: int, seed: int, ply: int) -> int:
    """Deterministic per-root search-rng seed (stable across runs/workers)."""
    return (base * 1_000_003 + seed * 8191 + ply * 131) & 0x7FFFFFFF


def _make_mcts(game, sims, c, seed):
    """The champion search: HeuristicMCTS on the v2.9 Bmild_cap8 leaf.
    leaf_cfg=None -> virtual_score_v2 uses DEFAULT_CONFIG, which under this
    file's env preamble IS the champion leaf (v2_9_1_Bmild_cap8)."""
    return HeuristicMCTS(game=game, simulations=sims, c=c, seed=seed,
                         heur_leaf="v2_7", leaf_cfg=None)


def _pool_root_stats(mcts, root, agg_n, agg_w):
    """Harvest one search tree's deduped root-child stats into the PIMC pools.
    Dedup by child object identity, lowest action kept — exactly the base
    MCTS.best_action convention (rotations of a symmetric tile share one child;
    without dedup that move would be pooled once per alias)."""
    seen: set[int] = set()
    for a in sorted(root.children):
        ch = root.children[a]
        if ch.N <= 0 or id(ch) in seen:
            continue
        seen.add(id(ch))
        sw = ch.W if ch.player_to_move == root.player_to_move else -ch.W
        agg_n[a] += ch.N
        agg_w[a] += sw


def probe_root(rec, sims, K, c, budget, search_seed):
    """One root: replay, solve exact, CLAIR pick, FAIR (PIMC-K) pick, regrets."""
    seed, ply = int(rec["seed"]), int(rec["ply"])
    try:
        game, board = replay_to(seed, ply)
    except Exception as e:  # noqa: BLE001
        return {"_error": f"{seed}:{ply} recon {type(e).__name__}: {e}"}
    if game.string_representation(board) != rec["checksum"]:
        return {"_error": f"{seed}:{ply} checksum_mismatch"}

    k = k_remaining(board)                     # authoritative post-replay K
    if k > MARG_MAX_K:
        return {"_skip": "k>2", "k": k}
    legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
    if legal.size < 2:
        return {"_skip": "<2 legal", "k": k}

    # ---- exact ground truth (marginalized == clairvoyant at K<=2) ----
    t0 = time.perf_counter()
    try:
        res = S.solve(game, board, mode="marginalized", budget=budget, alphabeta=False)
    except S.BudgetExceeded:
        return {"_skip": "budget", "k": k, "secs": round(time.perf_counter() - t0, 2)}
    solve_secs = time.perf_counter() - t0

    rs = _root_seed(search_seed, seed, ply)
    root_key = game.string_representation(board)
    t1 = time.perf_counter()

    # ---- CLAIR arm: the champion's move on the TRUE board ----
    clair = _make_mcts(game, sims, c, rs)
    clair_move = int(clair.best_action(board))
    clair.clear()

    # ---- FAIR arm: PIMC over K root determinizations ----
    det_rng = random.Random(rs + 1)            # deck reshuffles
    agg_n: dict[int, float] = defaultdict(float)
    agg_w: dict[int, float] = defaultdict(float)
    for i in range(K):
        b = copy.deepcopy(board)               # caller's board never mutated
        det_rng.shuffle(b.state.deck)          # ONLY the unseen deck; next_tile kept
        b._str_repr_cache = None               # deck order isn't in the key; be safe
        m = _make_mcts(game, sims, c, rs + 100 + i)   # FRESH tree per determinization
        m.search(b)
        root = m._nodes.get(root_key) or m._nodes[m.game.string_representation(b)]
        _pool_root_stats(m, root, agg_n, agg_w)
        m.clear()
    if agg_n:
        # primary (spec rule): argmax pooled visit count (Q then lowest-action tiebreak)
        fair_move = int(max(agg_n, key=lambda a: (agg_n[a], agg_w[a] / agg_n[a], -a)))
        # secondary: pooled-Q, N tiebreak — best_action's rule generalized to the
        # ensemble (clairvoyance_gap._choose_action's pooling statistic)
        fair_move_q = int(max(agg_n, key=lambda a: (agg_w[a] / agg_n[a], agg_n[a], -a)))
    else:                                      # pathological: no visited children
        fair_move = fair_move_q = int(legal[0])
    search_secs = time.perf_counter() - t1

    clair_regret = float(S.regret_of(res, clair_move))
    fair_regret = float(S.regret_of(res, fair_move))
    fair_regret_q = float(S.regret_of(res, fair_move_q))

    # mover-perspective difficulty context
    tm = res.to_move
    mv = sorted(((v if tm == 0 else -v) for v in res.child_values.values()), reverse=True)
    gap = float(mv[0] - mv[1]) if len(mv) >= 2 else None

    return {
        "seed": seed, "ply": ply, "k": k, "to_move": tm,
        "deck_len": len(board.state.deck),     # degenerate-regime marker (see notes)
        "n_legal": int(legal.size), "n_optimal": len(res.optimal_actions),
        "clair_move": clair_move, "fair_move": fair_move, "fair_move_q": fair_move_q,
        "differ": clair_move != fair_move,
        "clair_regret": round(clair_regret, 6),
        "fair_regret": round(fair_regret, 6),
        "fair_regret_q": round(fair_regret_q, 6),
        "best_vs_second_gap": round(gap, 4) if gap is not None else None,
        "solve_secs": round(solve_secs, 2), "search_secs": round(search_secs, 2),
        "solver_nodes": res.nodes,
    }


# fork-inherited worker context (module-level: picklable through Pool)
_CTX: dict = {}


def _worker(rec):
    return probe_root(rec, _CTX["sims"], _CTX["K"], _CTX["c"],
                      _CTX["budget"], _CTX["search_seed"])


# --------------------------------------------------------------------------- #
def _arm_agg(scored, key):
    reg = np.array([r[key] for r in scored], dtype=np.float64)
    return {
        "regret_mean": round(float(reg.mean()), 4),
        "regret_median": round(float(np.median(reg)), 4),
        "regret_max": round(float(reg.max()), 4),
        "top1_rate": round(float((reg <= TOP1_TOL).mean()), 4),
    }


def _paired(scored, fair_key, fair_move_key):
    """Paired fair-minus-clair delta + sign test on differ-roots."""
    d = np.array([r[fair_key] - r["clair_regret"] for r in scored], dtype=np.float64)
    n = len(d)
    sd = float(d.std(ddof=1)) if n > 1 else 0.0
    z = float(d.mean() / (sd / math.sqrt(n))) if sd > 0 else 0.0
    differ = [r for r in scored if r["clair_move"] != r[fair_move_key]]
    fair_better = sum(1 for r in differ if r[fair_key] < r["clair_regret"] - TOP1_TOL)
    clair_better = sum(1 for r in differ if r[fair_key] > r["clair_regret"] + TOP1_TOL)
    nb = fair_better + clair_better
    sign_z = float((fair_better - clair_better) / math.sqrt(nb)) if nb else 0.0
    return {
        "n": n,
        "mean_delta_fair_minus_clair": round(float(d.mean()), 4),
        "delta_sd": round(sd, 4),
        "paired_z": round(z, 3),
        "differ_rate": round(len(differ) / n, 4) if n else None,
        "n_differ": len(differ),
        "differ_fair_better": fair_better,
        "differ_clair_better": clair_better,
        "differ_regret_equal": len(differ) - nb,
        "sign_z_on_differ": round(sign_z, 3),
    }


def _git_rev():
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qprobe", default=DEFAULT_QPROBE)
    ap.add_argument("--pool", default=DEFAULT_POOL)
    ap.add_argument("--n", type=int, default=300,
                    help="root subset size (seeded shuffle; 0 = all 1,119 K<=2 roots)")
    ap.add_argument("--sims", type=int, default=1600,
                    help="HeuristicMCTS simulations per search (both arms)")
    ap.add_argument("--k", type=int, default=8,
                    help="FAIR-arm determinizations (PIMC K)")
    ap.add_argument("--c", type=float, default=3.0,
                    help="UCT exploration constant (champion: 3.0)")
    ap.add_argument("--budget", type=int, default=5_000_000, help="solver node budget/root")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--subset-seed", type=int, default=20260704,
                    help="seed for the root-subset shuffle (deterministic subset)")
    ap.add_argument("--search-seed", type=int, default=1,
                    help="base seed for the per-root search/determinization rngs")
    ap.add_argument("--out", default="", help="write full JSON report here")
    args = ap.parse_args(argv)

    t_start = time.time()
    recs = load_sibling_roots(args.qprobe, args.pool)
    cand = [r for r in recs if int(r.get("k_remaining", 99)) <= MARG_MAX_K]
    random.Random(args.subset_seed).shuffle(cand)
    if args.n:
        cand = cand[: args.n]
    print(f"[load] {len(recs)} sibling roots; K<={MARG_MAX_K} candidates selected: "
          f"{len(cand)} (subset_seed={args.subset_seed})", flush=True)
    est = (1 + args.k) * args.sims / 1000.0    # very rough s/root at ~1k sims/s
    print(f"[eta] ~{est:.0f}s/root search-side x {len(cand)} roots / W{args.workers} "
          f"~= {est * len(cand) / max(args.workers, 1) / 60:.0f} min (+ solves)", flush=True)

    _CTX.update(sims=args.sims, K=args.k, c=args.c, budget=args.budget,
                search_seed=args.search_seed)
    scored, errs, skips = [], [], []

    def _handle(out):
        if "_error" in out:
            errs.append(out)
        elif "_skip" in out:
            skips.append(out)
        else:
            scored.append(out)
            if len(scored) % 10 == 0:
                el = time.time() - t_start
                per = el / len(scored)
                print(f"  scored={len(scored)}/{len(cand)}  {per:.1f}s/root  "
                      f"eta {(len(cand) - len(scored) - len(skips) - len(errs)) * per / 60:.0f} min",
                      flush=True)

    if args.workers <= 1:
        for rec in cand:
            _handle(_worker(rec))
    else:
        from multiprocessing import get_context
        with get_context("fork").Pool(args.workers) as pool:
            for out in pool.imap_unordered(_worker, cand, chunksize=1):
                _handle(out)

    dt = time.time() - t_start
    print(f"[done] scored={len(scored)} skipped={len(skips)} errors={len(errs)} "
          f"in {dt / 60:.1f} min", flush=True)
    if errs[:3]:
        print("  sample errors:", [e["_error"] for e in errs[:3]], flush=True)
    if skips:
        print("  skip reasons:", dict(Counter(s["_skip"] for s in skips)), flush=True)

    scored.sort(key=lambda r: (r["seed"], r["ply"]))
    deck_len_dist = dict(sorted(Counter(r["deck_len"] for r in scored).items()))
    aggregate = {
        "clair": _arm_agg(scored, "clair_regret") if scored else None,
        "fair_pooledN": _arm_agg(scored, "fair_regret") if scored else None,
        "fair_pooledQ": _arm_agg(scored, "fair_regret_q") if scored else None,
        "paired_pooledN": _paired(scored, "fair_regret", "fair_move") if scored else None,
        "paired_pooledQ": _paired(scored, "fair_regret_q", "fair_move_q") if scored else None,
        "deck_len_dist": deck_len_dist,
    }
    report = {
        "manifest": {
            "probe": "fairness_decision_probe (decision-level fairness tax, stage 1)",
            "agent": "HeuristicMCTS (champion: deep-classical v2.9 Bmild_cap8)",
            "leaf": "v2_9_1_Bmild_cap8 via heur_leaf=v2_7 + env-built DEFAULT_CONFIG",
            "leaf_config_resolved": {
                k: (list(v) if isinstance(v, tuple) else v)
                for k, v in dataclasses.asdict(DEFAULT_CONFIG).items()
            },
            "leaf_env": {k: v for k, v in os.environ.items() if k.startswith("CARCASSONNE_")},
            "sims": args.sims, "K": args.k, "c": args.c, "budget": args.budget,
            "n_requested": args.n, "subset_seed": args.subset_seed,
            "search_seed": args.search_seed, "workers": args.workers,
            "qprobe": args.qprobe, "pool": args.pool,
            "solver_mode": "marginalized (== clairvoyant at K<=2; fair-legit truth)",
            "fair_arm": f"PIMC: {args.k} x fresh HeuristicMCTS on unseen-deck-reshuffled "
                        f"board copies, root visits pooled (dedup by child identity), "
                        f"argmax pooled-N (primary) / pooled-Q (secondary)",
            "clair_arm": "production best_action on the true deck order (Q, N tiebreak)",
            "code_rev": _git_rev(), "host": socket.gethostname(),
            "argv": sys.argv[1:], "started_utc": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_start)),
            "wall_secs": round(dt, 1),
        },
        "notes": [SCOPE_NOTE, DEGENERACY_NOTE],
        "n_scored": len(scored), "n_skipped": len(skips), "n_errors": len(errs),
        "aggregate": aggregate,
        "per_root": scored,
    }
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"[out] wrote {args.out}", flush=True)

    if scored:
        print("\n==== FAIRNESS DECISION PROBE (exact-solver regret, raw points) ====")
        print(f"roots={len(scored)}  sims={args.sims}  K={args.k}  deck_len_dist={deck_len_dist}")
        for arm in ("clair", "fair_pooledN", "fair_pooledQ"):
            a = aggregate[arm]
            print(f"  {arm:13s} regret mean={a['regret_mean']:.4f} "
                  f"median={a['regret_median']:.4f} max={a['regret_max']:.2f} "
                  f"top1={a['top1_rate']:.3f}")
        for pk in ("paired_pooledN", "paired_pooledQ"):
            p = aggregate[pk]
            print(f"  {pk}: mean Δ(fair−clair)={p['mean_delta_fair_minus_clair']:+.4f} "
                  f"(paired z={p['paired_z']:+.2f})  differ={p['n_differ']}/{p['n']} "
                  f"({p['differ_rate']:.1%})  sign fair/clair better="
                  f"{p['differ_fair_better']}/{p['differ_clair_better']} "
                  f"(z={p['sign_z_on_differ']:+.2f})")
        print(f"\nNOTE: {SCOPE_NOTE}")
        print(f"NOTE: {DEGENERACY_NOTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
