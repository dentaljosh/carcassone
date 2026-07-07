#!/usr/bin/env python3
"""Solver-scoring adapter for the PUCT-heuristic-priors AGENT (Stage 0 of
measurement/classical_search/TEACHER_TAU_PLAN.md).

Question: does the PUCT-priors@2750 agent's ROOT-Q RANKING beat the static v2.9
leaf's ranking against exact ground truth? (= first label source ABOVE the
heuristic.) Baselines on file (measurement/canonical_az/solver_score_m2_final_
it00_04.json): v2.9 leaf tau=0.615, M2 value heads tau=0.018-0.023.

COMPARABILITY IS THE POINT — this is a thin sibling of solver_score.py that
REUSES (imports, does not copy) its root set, root reconstruction, solve modes,
mover orientation, group_metrics (argmax-regret / top-1 / kendall_tau_b) and
aggregation, so the numbers land on the SAME ruler as the M2 value-head reads:

  * roots:   the 1,119 K<=2 sibling roots (qprobe_A JOIN pool_A), replayed via
             replay_to(seed, ply) + checksum verify — solver_score.load_sibling_roots
             + the same (k, seed, ply) candidate ordering.
  * truth:   endgame_solver.solve, MARGINALIZED at K<=2 (== clairvoyant there),
             clairvoyant+alpha-beta above — identical mode policy (solver_score.
             MARG_MAX_K). Solves are CACHED to a jsonl (child_values keyed by
             seed:ply:mode) so re-runs / config sweeps pay ZERO new solver cost
             (solve-once-score-many, now across invocations too).
  * metrics: solver child values flipped to the MOVER's POV exactly like
             solver_score.score_root (P0-persp -> negate when to_move==1), then
             scored with the SAME step1_train.group_metrics. Per-root output
             records use the SAME shape as solver_score.py ("rankers" sub-dict,
             "aggregate"/"by_k" blocks), so analyze_v210_screen.py's paired
             sign-z read works on this json unchanged.

Rankers emitted per root (all scored on the same solved root):
  * v29_leaf     — solver_score.make_v29_leaf_ranker (the 0.615 baseline,
                   re-scored here so the paired per-root comparison is exact,
                   not cross-run).
  * puct_q       — a FRESH heuristic-prior PUCT search per root
                   (make_heuristic_prior_mcts; default = the CONFIRMED cell:
                   c_puct 1.5, tau_p 5, leaf_quantize float, sims 2750, v2.9
                   Bmild_cap8 env == eval_puct_priors._CANON_ENV), children
                   ranked by root child search-Q in the MOVER's POV (the
                   best_action sign convention: q = child.Q flipped iff the
                   child's player_to_move differs from the root's). Children
                   the search never visited score BELOW every visited child
                   (single shared sentinel -> tied among themselves; count
                   recorded as n_unvisited).
  * puct_visits  — same search, children ranked by root visit counts
                   (unvisited = 0).

Secondary per-root stats (TEACHER_TAU_PLAN "also record"): visit top-share
(max deduped child visits / total), n_children, and Q-vs-visits rank agreement
(the SAME kendall_tau_b group_metrics uses), plus root_q / search_secs.

Aggregate adds the pre-registered read's uncertainty: BOOTSTRAP-OVER-ROOTS
sigma for each ranker's mean tau, the PAIRED per-root delta-tau vs the v29_leaf
baseline (bootstrap sigma + z), and the paired sign-z on solver_regret
(analyze_v210_screen.py convention).

Resumable: per-root records append to <out>.progress.jsonl as they complete;
a rerun skips finished roots (errors are retried). Fresh solves append to the
solve cache immediately. Multiprocessing over roots (fork pool, net-free CPU,
OMP_NUM_THREADS=1 via the canonical env).

MEASUREMENT ONLY. No champion / PRODUCTION / governance change; never writes
results.csv.

Full Stage-0 run (after the boxes free up — see TEACHER_TAU_PLAN.md):
  nice -n 19 .venv/bin/python -u scripts/canonical_az/solver_score_agent.py \
      --sims 2750 --workers 12 \
      --out measurement/classical_search/teacher_tau/stage0_sims2750.json
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
sys.path.insert(0, str(REPO / "scripts" / "canonical_az"))

# Env FIRST: importing eval_puct_priors applies its _CANON_ENV setdefaults
# (v2.9 Bmild_cap8 + USE_CY_LEAF/CY_REPR + CUDA masked + OMP/MKL=1) BEFORE any
# carcassonne_ai import builds DEFAULT_CONFIG — the exact env the confirmed
# PUCT-priors cell ran under. solver_score's own (subset) setdefaults then
# no-op. Import it for the env + so the manifest can point at the shared dict.
from eval_puct_priors import _CANON_ENV  # noqa: E402  (env side-effect wanted)

import solver_score as SS  # noqa: E402  (the F4 ruler: roots/solver/metrics/agg)
import step1_train as ST   # noqa: E402  (kendall_tau_b — the fn inside group_metrics)

import argparse            # noqa: E402
import json                # noqa: E402
import math                # noqa: E402
import os                  # noqa: E402
import time                # noqa: E402
from collections import Counter  # noqa: E402

import numpy as np         # noqa: E402

from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_heuristic_prior_mcts,
)
from carcassonne_ai.run_manifest import code_rev, write_manifest  # noqa: E402

DEFAULT_OUT = str(REPO / "measurement" / "classical_search" / "teacher_tau"
                  / "stage0_agent_tau.json")
DEFAULT_SOLVE_CACHE = str(REPO / "measurement" / "classical_search" / "teacher_tau"
                          / "solve_cache_k2.jsonl")


# --------------------------------------------------------------------------- #
# Solve cache (solve-once-score-many, across invocations)                      #
# --------------------------------------------------------------------------- #
def load_solve_cache(path: str) -> dict:
    cache = {}
    p = Path(path)
    if not p.exists():
        return cache
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        cache[(int(e["seed"]), int(e["ply"]), e["mode"])] = e
    return cache


# --------------------------------------------------------------------------- #
# Per-root scoring (the adapter core)                                          #
# --------------------------------------------------------------------------- #
# fork-inherited worker context (same pattern as solver_score._POOL_CTX — a
# main()-local closure can't cross Pool.imap_unordered).
_CTX: dict = {}


def _score_one(rec):
    """Reconstruct one root, solve it (or reuse the cache), then score the
    v29_leaf baseline + the PUCT-priors agent (Q- and visit-rankings) on the
    same exact child values. Mirrors solver_score.score_root field-for-field,
    adding the agent block. Returns a per-root dict; '_error'/'_skip' dicts
    carry seed/ply so resume can skip deterministic skips but retry errors."""
    cfg: HeuristicPriorConfig = _CTX["cfg"]
    sims: int = _CTX["sims"]
    budget: int = _CTX["budget"]
    max_k: int = _CTX["max_k"]
    solve_cache: dict = _CTX["solve_cache"]
    leaf_ranker = _CTX["leaf_ranker"]

    seed, ply = int(rec["seed"]), int(rec["ply"])
    t_rep = time.perf_counter()
    try:
        game, board = SS.replay_to(seed, ply)
    except Exception as e:  # noqa: BLE001
        return {"_error": f"{seed}:{ply} recon {type(e).__name__}: {e}",
                "seed": seed, "ply": ply}
    if game.string_representation(board) != rec["checksum"]:
        return {"_error": f"{seed}:{ply} checksum_mismatch", "seed": seed, "ply": ply}
    replay_secs = time.perf_counter() - t_rep

    k = SS.k_remaining(board)                  # POST-replay (authoritative)
    if k > max_k:
        return {"_skip": "k>max_k", "k": k, "seed": seed, "ply": ply}
    if k <= SS.MARG_MAX_K:
        mode, ab = "marginalized", False
    else:
        mode, ab = "clairvoyant", True

    root_player = board.state.current_player
    legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
    if legal.size < 2:
        return {"_skip": "<2 legal", "k": k, "seed": seed, "ply": ply}

    # ---- exact ground truth: cache hit or a fresh solve ----
    ent = solve_cache.get((seed, ply, mode))
    fresh_solve = None
    if ent is not None:
        actions = [int(a) for a in ent["actions"]]
        cvals = [float(v) for v in ent["child_values"]]
        tm = int(ent["to_move"])
        nodes = int(ent["nodes"])
        solve_secs = 0.0
        solve_cached = True
    else:
        t0 = time.perf_counter()
        try:
            res = SS.S.solve(game, board, mode=mode, budget=budget, alphabeta=ab)
        except SS.S.BudgetExceeded:
            return {"_skip": "budget", "k": k, "mode": mode, "seed": seed, "ply": ply,
                    "secs": round(time.perf_counter() - t0, 2)}
        solve_secs = time.perf_counter() - t0
        cv = res.child_values                  # {action: P0-perspective value}
        tm = int(res.to_move)
        actions = [int(a) for a in cv.keys()]  # preserve solver enumeration order
        cvals = [float(cv[a]) for a in actions]
        nodes = int(res.nodes)
        solve_cached = False
        fresh_solve = {"seed": seed, "ply": ply, "mode": mode, "k": k,
                       "to_move": tm, "nodes": nodes,
                       "solve_secs": round(solve_secs, 2),
                       "actions": actions, "child_values": cvals}

    # Mover orientation — IDENTICAL to solver_score.score_root: P0-perspective
    # child values are negated when the mover is P1, so argmax(target)=best move.
    solver_mover = np.array([(v if tm == 0 else -v) for v in cvals], dtype=np.float64)

    # ---- baseline ranker: the static v2.9 leaf on the same children ----
    children = [game.get_next_state(board, int(a))[0] for a in actions]
    leaf_score = np.array(
        [float(leaf_ranker(child, root_player, game)) for child in children],
        dtype=np.float64)

    # ---- the agent: one fresh PUCT-priors search from this root ----
    t1 = time.perf_counter()
    mcts = make_heuristic_prior_mcts(game, cfg, simulations=sims, seed=seed)
    mcts.search(board)
    search_secs = time.perf_counter() - t1
    root = mcts._nodes[game.string_representation(board)]
    mover = root.player_to_move                # == root_player (fresh tree)

    # Per-ACTION search-Q in the MOVER's POV — the best_action sign convention
    # (mcts.py:861). Transposition-aliased rotations share one node -> identical
    # Q/N per colliding slot, which matches the solver giving them equal values.
    q_by_a, n_by_a = {}, {}
    for a in actions:
        child = root.children.get(int(a))
        if child is not None and child.N > 0:
            q_by_a[a] = float(child.Q if child.player_to_move == mover else -child.Q)
            n_by_a[a] = int(child.N)
    n_unvisited = len(actions) - len(q_by_a)
    # Unvisited children: the search allocated them zero visits, so the agent's
    # ranking has no Q for them -> rank strictly below every visited child, tied
    # among themselves (one shared sentinel; Q lives in [-1,1] so min-1 is safe).
    sentinel = (min(q_by_a.values()) - 1.0) if q_by_a else 0.0
    q_vec = np.array([q_by_a.get(a, sentinel) for a in actions], dtype=np.float64)
    n_vec = np.array([float(n_by_a.get(a, 0)) for a in actions], dtype=np.float64)

    # Secondary stats (TEACHER_TAU_PLAN): visit top-share over DEDUPED children
    # (alias slots share a node; counting per-slot would double-count), and the
    # Q-vs-visits rank agreement with the SAME kendall the primary metric uses.
    dedup = mcts._deduped_children(root)
    dedup_n = [c.N for _, c in dedup]
    tot_n = int(sum(dedup_n))
    top_share = (max(dedup_n) / tot_n) if tot_n > 0 else None
    q_visits_tau = float(ST.kendall_tau_b(q_vec, n_vec))

    per_ranker = {}
    for name, score in (("v29_leaf", leaf_score),
                        ("puct_q", q_vec),
                        ("puct_visits", n_vec)):
        regret, top1, tau = SS.group_metrics(score, solver_mover)
        per_ranker[name] = {
            "solver_regret": round(float(regret), 4),
            "top1": int(top1), "tau": float(tau),
            "pick": int(actions[int(np.argmax(score))]),
        }
    per_ranker["puct_q"]["n_unvisited"] = int(n_unvisited)

    sm_sorted = np.sort(solver_mover)[::-1]
    gap = float(sm_sorted[0] - sm_sorted[1]) if len(sm_sorted) >= 2 else None
    out = {
        "seed": seed, "ply": ply, "phase": rec.get("phase", "?"),
        "k": k, "mode": mode, "n_legal": len(actions), "to_move": tm,
        "nodes": nodes, "solve_secs": round(solve_secs, 2),
        "solve_cached": solve_cached,
        "rankers": per_ranker,
        "best_vs_second_gap": round(gap, 4) if gap is not None else None,
        "value_spread": round(float(solver_mover.max() - solver_mover.min()), 4),
        "agent": {
            "sims": sims,
            "search_secs": round(search_secs, 2),
            "replay_secs": round(replay_secs, 2),
            "root_q": round(float(root.Q), 6),
            "top_share": round(top_share, 4) if top_share is not None else None,
            "n_children": len(actions),
            "n_tree_children": len(dedup),
            "n_unvisited": int(n_unvisited),
            "q_visits_tau": q_visits_tau if math.isfinite(q_visits_tau) else None,
        },
    }
    if fresh_solve is not None:
        out["_solve_entry"] = fresh_solve
    return out


# --------------------------------------------------------------------------- #
# Aggregation extras: bootstrap-over-roots + paired reads                      #
# --------------------------------------------------------------------------- #
def bootstrap_block(scored, names, baseline="v29_leaf", B=10_000, seed=0):
    """Bootstrap-over-roots sigma for each ranker's mean tau, plus the PAIRED
    per-root delta-tau vs the baseline (bootstrap sigma + z) and the paired
    sign-z on solver_regret (analyze_v210_screen.py convention). nan taus
    (all-tied roots, spread 0) are nanmean'd exactly like solver_score._agg;
    paired deltas use only roots where BOTH taus are finite."""
    n = len(scored)
    if n == 0:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(B, n))
    taus = {nm: np.array([r["rankers"][nm]["tau"] for r in scored], dtype=np.float64)
            for nm in names}
    regs = {nm: np.array([r["rankers"][nm]["solver_regret"] for r in scored],
                         dtype=np.float64) for nm in names}
    out = {"B": B, "seed": seed, "n_roots": n, "baseline": baseline}
    base_t, base_r = taus[baseline], regs[baseline]
    for nm in names:
        t = taus[nm]
        boot_means = np.nanmean(t[idx], axis=1)
        ent = {
            "tau_mean": round(float(np.nanmean(t)), 4),
            "tau_sigma_boot": round(float(np.nanstd(boot_means)), 5),
            "n_tau_nan": int(np.isnan(t).sum()),
        }
        if nm != baseline:
            ok = np.isfinite(t) & np.isfinite(base_t)
            dt = t[ok] - base_t[ok]
            if dt.size:
                idx2 = rng.integers(0, dt.size, size=(B, dt.size))
                dboot = dt[idx2].mean(axis=1)
                dsig = float(dboot.std())
                ent["dtau_vs_baseline_mean"] = round(float(dt.mean()), 4)
                ent["dtau_sigma_boot"] = round(dsig, 5)
                ent["dtau_z"] = round(float(dt.mean() / dsig), 2) if dsig > 0 else None
                ent["n_paired"] = int(dt.size)
            d = regs[nm] - base_r
            better, worse = int((d < 0).sum()), int((d > 0).sum())
            ent["regret_better"] = better
            ent["regret_worse"] = worse
            ent["regret_tie"] = int((d == 0).sum())
            ent["regret_sign_z"] = round(
                (better - worse) / math.sqrt(better + worse), 2
            ) if (better + worse) else 0.0
            ent["mean_dregret"] = round(float(d.mean()), 4)
        out[nm] = ent
    return out


def _agent_agg(scored):
    if not scored:
        return None
    def col(k):
        return np.array([r["agent"][k] for r in scored if r["agent"][k] is not None],
                        dtype=np.float64)
    ts, qv = col("top_share"), col("q_visits_tau")
    return {
        "search_secs_mean": round(float(col("search_secs").mean()), 2),
        "replay_secs_mean": round(float(col("replay_secs").mean()), 2),
        "top_share_mean": round(float(ts.mean()), 4) if ts.size else None,
        "top_share_p10": round(float(np.percentile(ts, 10)), 4) if ts.size else None,
        "top_share_p50": round(float(np.percentile(ts, 50)), 4) if ts.size else None,
        "top_share_p90": round(float(np.percentile(ts, 90)), 4) if ts.size else None,
        "q_visits_tau_mean": round(float(qv.mean()), 4) if qv.size else None,
        "unvisited_frac_mean": round(float(np.mean(
            [r["agent"]["n_unvisited"] / max(r["agent"]["n_children"], 1)
             for r in scored])), 4),
    }


# --------------------------------------------------------------------------- #
def _parse_roots(spec: str):
    """'seed:ply,seed:ply' -> set of (seed, ply)."""
    out = set()
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        s, _, p = tok.partition(":")
        out.add((int(s), int(p)))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qprobe", default=SS.DEFAULT_QPROBE)
    ap.add_argument("--pool", default=SS.DEFAULT_POOL)
    ap.add_argument("--max-k", type=int, default=2,
                    help="K filter (TEACHER_TAU_PLAN uses the K<=2 marginalized set)")
    # Agent knobs — defaults = the CONFIRMED cell (results.csv phase1.1 CONFIRM:
    # c_puct 1.5, tau_p 5, leaf_quantize float, sims 2750).
    ap.add_argument("--sims", type=int, default=2750)
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--tau-p", type=float, default=5.0)
    ap.add_argument("--leaf-quantize", choices=("int", "float"), default="float")
    ap.add_argument("--value-norm", type=float, default=15.0)
    ap.add_argument("--n", type=int, default=0, help="cap #roots to score (0=all)")
    ap.add_argument("--roots", default="",
                    help="explicit 'seed:ply,seed:ply' subset (tests/smoke)")
    ap.add_argument("--budget", type=int, default=5_000_000, help="solver node budget/root")
    ap.add_argument("--workers", type=int, default=1,
                    help="fork pool over roots (net-free CPU; OMP/MKL=1 via env)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="full JSON report path")
    ap.add_argument("--solve-cache", default=DEFAULT_SOLVE_CACHE,
                    help="jsonl of exact solves keyed (seed,ply,mode) — read+appended")
    ap.add_argument("--no-resume", action="store_true",
                    help="ignore an existing progress file (rescore everything)")
    ap.add_argument("--seed-shuffle", type=int, default=0,
                    help="shuffle candidates with this seed before the --n cap")
    ap.add_argument("--boot-b", type=int, default=10_000)
    ap.add_argument("--boot-seed", type=int, default=0)
    args = ap.parse_args(argv)

    cfg = HeuristicPriorConfig(c_puct=args.c_puct, tau_p=args.tau_p,
                               leaf_quantize=args.leaf_quantize,
                               final_select="Q",  # not used: we emit BOTH rankings
                               value_norm=args.value_norm)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path = Path(str(out_path) + ".progress.jsonl")

    # ---- roots: identical loading + candidate ordering to solver_score ----
    recs = SS.load_sibling_roots(args.qprobe, args.pool)
    print(f"[load] {len(recs)} sibling roots (qprobe ∩ pool)", flush=True)
    cand = [r for r in recs if int(r.get("k_remaining", 99)) <= args.max_k]
    if args.roots:
        want = _parse_roots(args.roots)
        cand = [r for r in cand if (int(r["seed"]), int(r["ply"])) in want]
        missing = want - {(int(r["seed"]), int(r["ply"])) for r in cand}
        if missing:
            print(f"[warn] --roots not in candidate set: {sorted(missing)}", flush=True)
    if args.seed_shuffle:
        import random
        random.Random(args.seed_shuffle).shuffle(cand)
    else:
        cand.sort(key=lambda r: (int(r.get("k_remaining", 99)), int(r["seed"]), int(r["ply"])))
    kdist = Counter(int(r.get("k_remaining", 99)) for r in cand)
    print(f"[filter] {len(cand)} roots with record k_remaining<={args.max_k} "
          f"K-dist={dict(sorted(kdist.items()))}", flush=True)

    # ---- resume: previously scored roots + deterministic skips ----
    scored, skips, errs = [], [], []
    done = set()
    if progress_path.exists() and not args.no_resume:
        for line in open(progress_path):
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            key = (int(e["seed"]), int(e["ply"]))
            if e.get("kind") == "scored":
                scored.append(e["rec"])
                done.add(key)
            elif e.get("kind") == "skip":
                skips.append(e)
                done.add(key)
        print(f"[resume] {len(scored)} scored + {len(skips)} skips from "
              f"{progress_path.name}", flush=True)
    todo = [r for r in cand if (int(r["seed"]), int(r["ply"])) not in done]

    solve_cache = load_solve_cache(args.solve_cache)
    print(f"[cache] {len(solve_cache)} solved roots in {args.solve_cache}", flush=True)

    # ---- manifest (before the run, solver_score/eval_puct_priors style) ----
    config = {
        "tool": "solver_score_agent.py",
        "plan": "measurement/classical_search/TEACHER_TAU_PLAN.md (Stage 0)",
        "agent": {"kind": "puct_heuristic_priors",
                  "factory": "make_heuristic_prior_mcts",
                  "sims": args.sims, **cfg.as_manifest()},
        "rankers": ["v29_leaf", "puct_q", "puct_visits"],
        "ranking_conventions": {
            "puct_q": "root child search-Q, mover POV (best_action flip); "
                      "unvisited children tied below all visited",
            "puct_visits": "root child visit counts (unvisited=0)",
            "mover_orientation": "solver child_values P0-persp, negated iff to_move==1 "
                                 "(solver_score.score_root)",
        },
        "max_k": args.max_k, "budget": args.budget,
        "qprobe": args.qprobe, "pool": args.pool,
        "solve_cache": args.solve_cache,
        "n_cap": args.n, "roots_subset": args.roots or None,
        "seed_shuffle": args.seed_shuffle,
        "workers": args.workers,
        "bootstrap": {"B": args.boot_b, "seed": args.boot_seed},
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
        "argv": sys.argv,
        "code_rev": code_rev(),
    }
    write_manifest(out_path.parent, kind="solver_score_agent", game="base",
                   config=config, overwrite=True)

    _CTX.update(cfg=cfg, sims=args.sims, budget=args.budget, max_k=args.max_k,
                solve_cache=solve_cache, leaf_ranker=SS.make_v29_leaf_ranker())

    cache_fh = open(args.solve_cache, "a")
    progress_fh = open(progress_path, "a")

    def _handle(out):
        if out is None:
            return
        ent = out.pop("_solve_entry", None)
        if ent is not None:
            cache_fh.write(json.dumps(ent) + "\n")
            cache_fh.flush()
        if "_error" in out:
            errs.append(out)          # NOT persisted -> retried on resume
            print(f"  [err] {out['_error']}", flush=True)
        elif "_skip" in out:
            skips.append(out)
            progress_fh.write(json.dumps({"kind": "skip", **out}) + "\n")
            progress_fh.flush()
        else:
            scored.append(out)
            progress_fh.write(json.dumps(
                {"kind": "scored", "seed": out["seed"], "ply": out["ply"],
                 "rec": out}) + "\n")
            progress_fh.flush()

    t0 = time.perf_counter()
    n_target = args.n if args.n else None
    if args.workers <= 1:
        for rec in todo:
            if n_target and len(scored) >= n_target:
                break
            _handle(_score_one(rec))
            if scored and len(scored) % 10 == 0:
                el = time.perf_counter() - t0
                print(f"  scored={len(scored)} skip={len(skips)} err={len(errs)} "
                      f"({el / max(len(scored), 1):.1f}s/scored)", flush=True)
    else:
        from multiprocessing import get_context
        ctx = get_context("fork")
        sub = todo[: args.n * 3] if args.n else todo   # 3x headroom for skips
        with ctx.Pool(args.workers) as pool:
            for out in pool.imap_unordered(_score_one, sub, chunksize=1):
                _handle(out)
                if scored and len(scored) % 25 == 0:
                    el = time.perf_counter() - t0
                    print(f"  scored={len(scored)} skip={len(skips)} err={len(errs)} "
                          f"({el / max(len(scored), 1):.1f}s/scored)", flush=True)
                if n_target and len(scored) >= n_target:
                    break

    dt = time.perf_counter() - t0
    print(f"[done] scored={len(scored)} skipped={len(skips)} errors={len(errs)} "
          f"in {dt:.1f}s", flush=True)
    cache_fh.close()
    progress_fh.close()

    # ---- aggregate: same _agg as solver_score, per ranker / per K ----
    names = ["v29_leaf", "puct_q", "puct_visits"]
    ks = sorted({r["k"] for r in scored})
    aggregate = {nm: SS._agg(SS._ranker_rows(scored, nm)) for nm in names}
    by_k = {nm: {k: SS._agg(SS._ranker_rows([r for r in scored if r["k"] == k], nm))
                 for k in ks} for nm in names}
    boot = bootstrap_block(scored, names, baseline="v29_leaf",
                           B=args.boot_b, seed=args.boot_seed)
    report = {
        "manifest": config,
        "rankers": names,
        "ranker_baseline": "v29_leaf",
        "max_k": args.max_k, "budget": args.budget,
        "qprobe": args.qprobe, "pool": args.pool,
        "n_roots_total": len(recs), "n_candidates": len(cand),
        "n_scored": len(scored), "n_skipped": len(skips), "n_errors": len(errs),
        "aggregate": aggregate, "by_k": by_k,
        "agent_aggregate": _agent_agg(scored),
        "bootstrap": boot,
        "per_root": scored,
    }
    out_path.write_text(json.dumps(report, indent=2))
    print(f"[out] wrote {out_path}", flush=True)

    for nm in names:
        a = aggregate[nm]
        if not a:
            continue
        line = (f"==== SOLVER-SCORE ({nm}) ====  n={a['n']}  "
                f"regret mean={a['solver_regret_mean']} median={a['solver_regret_median']}  "
                f"top1={a['top1_rate']}  tau={a['tau_mean']}")
        if boot and nm in boot:
            b = boot[nm]
            line += f"  (tau sigma_boot={b['tau_sigma_boot']}"
            if "dtau_vs_baseline_mean" in b:
                line += (f"; dtau vs leaf={b['dtau_vs_baseline_mean']}"
                         f"±{b['dtau_sigma_boot']} z={b['dtau_z']}"
                         f"; regret sign-z={b['regret_sign_z']}")
            line += ")"
        print(line)
    aa = report["agent_aggregate"]
    if aa:
        print(f"[agent] search {aa['search_secs_mean']}s/root  "
              f"top_share mean={aa['top_share_mean']} "
              f"p50={aa['top_share_p50']} p90={aa['top_share_p90']}  "
              f"q_visits_tau={aa['q_visits_tau_mean']}  "
              f"unvisited_frac={aa['unvisited_frac_mean']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
