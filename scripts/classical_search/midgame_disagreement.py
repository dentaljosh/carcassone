#!/usr/bin/env python3
"""Diagnostic (a) of measurement/classical_search/TEACHER_TAU_PLAN.md ("NEXT"):
MIDGAME leaf-prior vs teacher-move disagreement rate — THE DECISIVE GATE.

The Step-1 distillation ("a distilled net-prior inside the new PUCT, judged in
games") can only recover value the SEARCH adds ON TOP of the raw leaf-prior. That
"distillable delta" is bounded by how often the 2750-sim search's final move
DIFFERS from the move the leaf-prior alone would pick. Fable's Stage-0 review
showed the earlier "policy reopen" signal was an ENDGAME artifact (all 1,119
solver roots are K=2 = last two tiles); this diagnostic asks the same question
on a MIDGAME slice, where a real policy delta would have to live.

  Step 1 is funded ONLY if >=20% REAL (non-noise) midgame disagreement.

Per MIDGAME root (k_remaining in [15,45], the qprobe_A strata {22,32,44}):
  * TEACHER move  = the PUCT-priors@2750 final move = ROOT VISIT-ARGMAX (the
    CONFIRMED champion selector: results.csv phase1.1 CONFIRM used
    final_select=visits, +148.2 elo / z10.17). Deduped over transposition-alias
    rotations (mcts.root_visit_distribution).
  * LEAF-PRIOR move = argmax over legal children of the agent's OWN prior logit
    = argmax Δleaf(child) (mover POV) — the move softmax(Δleaf/τ) would pick
    BEFORE any search. Read straight off the agent's evaluator
    (make_heuristic_prior_evaluator), NOT re-derived: `priors[legal]` IS
    softmax(Δleaf/τ), so argmax(priors) is exactly the agent's prior pick.

AGREE is compared by SUCCESSOR-BOARD KEY, not raw action index: rotationally
symmetric tiles emit >=2 legal actions that produce the IDENTICAL child board
(the same transposition collision _deduped_children collapses). Comparing raw
actions would count an alias of the SAME move as a disagreement; comparing
string_representation(child) is the semantically-correct "same move".

NOISE PROXY — the Δleaf gap between the leaf-prior's top-2 DISTINCT children
(deduped by successor key). A small gap means the two best moves are near-tied in
raw leaf value, so a teacher!=leaf-prior disagreement there is within leaf noise,
not real signal. Recovered from the agent's OWN prior weights via the exact
inverse softmax: for any two legal actions Δleaf_a - Δleaf_b = τ·(ln w_a - ln w_b)
(shared normalization cancels), so the top-2 gap = τ·(ln w1 - ln w2) in leaf
points — the agent's own numbers, no leaf re-derivation.

REAL disagreement (the number the >=20% gate compares against):
    teacher != leaf-prior  AND  teacher_visit_share > top_share_min (0.15)
                           AND  top-2 Δleaf gap > gap_eps (0.5 leaf points).
All raw per-root fields (agree, gap, visit_share) are stored, so both thresholds
can be re-swept from the JSON without re-running.

Also reports mean top_share on the midgame slice (contrast to the 0.31 ENDGAME
figure from stage0_sims2750.json — is midgame search still peaked?).

Pure CPU, NET-FREE, NO SOLVER (no endgame_solver.solve is ever called — importing
solver_score is only for its identical root-loading/replay helpers). Fork pool
over positions, OMP/MKL=1 via the canonical env.

MEASUREMENT ONLY. No champion / PRODUCTION / governance / results.csv change.

Full run (after the boxes free up — see TEACHER_TAU_PLAN.md):
  nice -n 19 .venv/bin/python -u scripts/classical_search/midgame_disagreement.py \
      --sims 2750 --n 400 --workers 12 \
      --out measurement/classical_search/midgame_disagree/disagreement.json
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
# PUCT-priors cell ran under.
from eval_puct_priors import _CANON_ENV  # noqa: E402  (env side-effect wanted)

import solver_score as SS  # noqa: E402  (root loading + replay_to/k_remaining ONLY; no solve)

import argparse            # noqa: E402
import json                # noqa: E402
import math                # noqa: E402
import os                  # noqa: E402
import time                # noqa: E402
from collections import Counter  # noqa: E402

import numpy as np         # noqa: E402

from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
    make_heuristic_prior_mcts,
)
from carcassonne_ai.run_manifest import code_rev, write_manifest  # noqa: E402

DEFAULT_OUT = str(REPO / "measurement" / "classical_search" / "midgame_disagree"
                  / "disagreement.json")


# --------------------------------------------------------------------------- #
# Pure, hand-testable core (no engine deps — unit-tested on synthetic cases).   #
# --------------------------------------------------------------------------- #
def dedup_by_key(legal, weights, child_keys):
    """Collapse alias actions (same successor board key) to DISTINCT children.

    legal:      iterable of legal action ints
    weights:    array aligned to `legal` (the agent's softmax prior over legal)
    child_keys: dict action -> successor-board key (str)

    Returns (distinct_keys, distinct_weights, rep_actions) where each distinct
    successor key appears once, its weight is the MAX over its aliases (they are
    equal by construction — identical board => identical Δleaf => identical prior
    — max only guards float32 ulp jitter), and rep_action is the lowest-index
    action producing that key (matches _deduped_children's representative). Order
    is first-appearance in `legal` (deterministic)."""
    legal = [int(a) for a in legal]
    w = np.asarray(weights, dtype=np.float64)
    keys, wts, reps = [], [], []
    idx_of = {}
    for a, wa in zip(legal, w):
        key = child_keys[a]
        if key in idx_of:
            j = idx_of[key]
            if wa > wts[j]:
                wts[j] = float(wa)
            if a < reps[j]:
                reps[j] = a
        else:
            idx_of[key] = len(keys)
            keys.append(key)
            wts.append(float(wa))
            reps.append(a)
    return keys, np.asarray(wts, dtype=np.float64), reps


def classify(distinct_keys, distinct_weights, teacher_key, teacher_visit_share,
             *, tau, top_share_min, gap_eps):
    """Given the DISTINCT-child prior weights + the teacher's chosen successor
    key, decide agree / disagree, the top-2 Δleaf noise gap, and whether the
    disagreement is REAL (passes both noise filters). All inputs are primitives
    so this is exercised directly by the synthetic unit test.

    top-2 Δleaf gap = τ·(ln w1 - ln w2) over the two highest-prior distinct
    children (leaf points). float('inf') if the 2nd prior underflowed to 0 (a
    huge gap — the leaf strongly prefers its top move; would only occur for a
    top-2 Δleaf gap of hundreds of points, i.e. never in practice)."""
    keys = list(distinct_keys)
    w = np.asarray(distinct_weights, dtype=np.float64)
    order = np.argsort(-w, kind="stable")            # desc, ties in first-seen order
    lp_key = keys[int(order[0])]
    lp_weight = float(w[int(order[0])])
    agree = (lp_key == teacher_key)
    if w.size >= 2:
        w1, w2 = float(w[int(order[0])]), float(w[int(order[1])])
        gap = tau * (math.log(w1) - math.log(w2)) if (w1 > 0.0 and w2 > 0.0) \
            else float("inf")
    else:
        gap = None                                    # single distinct move: no gap
    real = ((not agree)
            and (teacher_visit_share > top_share_min)
            and (gap is not None and gap > gap_eps))
    return {
        "leaf_prior_key": lp_key,
        "leaf_prior_weight": round(lp_weight, 6),
        "agree": bool(agree),
        "top2_gap": (None if gap is None
                     else (round(float(gap), 4) if math.isfinite(gap) else None)),
        "gap_saturated": bool(gap == float("inf")),
        "teacher_visit_share": round(float(teacher_visit_share), 4),
        "real_disagreement": bool(real),
    }


# --------------------------------------------------------------------------- #
# Per-position worker (fork-inherited context, same pattern as solver_score).   #
# --------------------------------------------------------------------------- #
_CTX: dict = {}


def _analyze_one(rec):
    """Replay one midgame root, read the agent's leaf-prior pick + top-2 gap and
    the 2750-sim visit-argmax teacher move, classify. No solver, no net."""
    cfg: HeuristicPriorConfig = _CTX["cfg"]
    sims: int = _CTX["sims"]
    kmin: int = _CTX["kmin"]
    kmax: int = _CTX["kmax"]
    tau: float = float(cfg.tau_p)
    top_share_min: float = _CTX["top_share_min"]
    gap_eps: float = _CTX["gap_eps"]

    seed, ply = int(rec["seed"]), int(rec["ply"])
    try:
        game, board = SS.replay_to(seed, ply)
    except Exception as e:  # noqa: BLE001
        return {"_error": f"{seed}:{ply} recon {type(e).__name__}: {e}",
                "seed": seed, "ply": ply}
    if game.string_representation(board) != rec["checksum"]:
        return {"_error": f"{seed}:{ply} checksum_mismatch", "seed": seed, "ply": ply}

    k = SS.k_remaining(board)                          # POST-replay (authoritative)
    if not (kmin <= k <= kmax):
        return {"_skip": "k_out_of_band", "k": k, "seed": seed, "ply": ply}

    legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
    if legal.size < 2:
        return {"_skip": "<2 legal", "k": k, "seed": seed, "ply": ply}

    # ---- leaf-prior: the agent's OWN evaluator (argmax priors = argmax Δleaf) ----
    ev = make_heuristic_prior_evaluator(game, cfg)
    priors, root_value = ev(board)
    w_legal = np.asarray(priors, dtype=np.float64)[legal]

    # successor-board keys for every legal action (dedups rotation aliases).
    child_keys = {int(a): game.string_representation(game.get_next_state(board, int(a))[0])
                  for a in legal}
    distinct_keys, distinct_w, rep_actions = dedup_by_key(legal, w_legal, child_keys)

    # ---- teacher: one fresh 2750-sim PUCT-priors search, VISIT-argmax ----
    t1 = time.perf_counter()
    mcts = make_heuristic_prior_mcts(game, cfg, simulations=sims, seed=seed)
    mcts.search(board)
    counts, actions = mcts.root_visit_distribution(board)   # deduped children
    search_secs = time.perf_counter() - t1
    total = float(counts.sum())
    ti = int(np.argmax(counts))
    teacher_action = int(actions[ti])
    teacher_share = (float(counts[ti]) / total) if total > 0 else 0.0
    teacher_key = child_keys.get(teacher_action) or game.string_representation(
        game.get_next_state(board, teacher_action)[0])

    res = classify(distinct_keys, distinct_w, teacher_key, teacher_share,
                   tau=tau, top_share_min=top_share_min, gap_eps=gap_eps)

    lp_rep = rep_actions[distinct_keys.index(res["leaf_prior_key"])]
    return {
        "seed": seed, "ply": ply, "phase": rec.get("phase", "?"), "k": k,
        "n_legal": int(legal.size), "n_distinct": len(distinct_keys),
        "teacher_action": teacher_action,
        "leaf_prior_action": int(lp_rep),
        "agree": res["agree"],
        "disagree": (not res["agree"]),
        "real_disagreement": res["real_disagreement"],
        "top2_gap": res["top2_gap"],
        "gap_saturated": res["gap_saturated"],
        "teacher_visit_share": res["teacher_visit_share"],
        "top_share": round(float(counts.max()) / total, 4) if total > 0 else None,
        "root_value": round(float(root_value), 6),
        "leaf_prior_weight": res["leaf_prior_weight"],
        "search_secs": round(search_secs, 3),
    }


# --------------------------------------------------------------------------- #
def _rate(scored, key):
    if not scored:
        return None
    return round(float(np.mean([1.0 if r[key] else 0.0 for r in scored])), 4)


def _share_stats(scored):
    ts = np.array([r["top_share"] for r in scored if r["top_share"] is not None],
                  dtype=np.float64)
    if ts.size == 0:
        return {}
    return {
        "top_share_mean": round(float(ts.mean()), 4),
        "top_share_p10": round(float(np.percentile(ts, 10)), 4),
        "top_share_p50": round(float(np.percentile(ts, 50)), 4),
        "top_share_p90": round(float(np.percentile(ts, 90)), 4),
    }


def _aggregate(scored, top_share_min, gap_eps):
    n = len(scored)
    dis = [r for r in scored if r["disagree"]]
    passed_share = [r for r in dis if r["teacher_visit_share"] > top_share_min]
    passed_gap = [r for r in dis
                  if r["gap_saturated"] or (r["top2_gap"] is not None and r["top2_gap"] > gap_eps)]
    agg = {
        "n_scored": n,
        "disagreement_rate": _rate(scored, "disagree"),
        "real_disagreement_rate": _rate(scored, "real_disagreement"),
        "n_disagree": len(dis),
        "n_disagree_pass_share": len(passed_share),
        "n_disagree_pass_gap": len(passed_gap),
        "n_real_disagree": sum(1 for r in scored if r["real_disagreement"]),
        "mean_n_legal": round(float(np.mean([r["n_legal"] for r in scored])), 2) if n else None,
        "mean_n_distinct": round(float(np.mean([r["n_distinct"] for r in scored])), 2) if n else None,
        "search_secs_mean": round(float(np.mean([r["search_secs"] for r in scored])), 3) if n else None,
        "gate_bar": 0.20,
        "top_share_min": top_share_min,
        "gap_eps": gap_eps,
    }
    agg.update(_share_stats(scored))
    return agg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qprobe", default=SS.DEFAULT_QPROBE)
    ap.add_argument("--pool", default=SS.DEFAULT_POOL)
    ap.add_argument("--k-min", type=int, default=15, help="midgame band lower bound (inclusive)")
    ap.add_argument("--k-max", type=int, default=45, help="midgame band upper bound (inclusive)")
    # Agent knobs — defaults = the CONFIRMED cell (c_puct 1.5, tau_p 5, float, sims 2750).
    ap.add_argument("--sims", type=int, default=2750)
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--tau-p", type=float, default=5.0)
    ap.add_argument("--leaf-quantize", choices=("int", "float"), default="float")
    ap.add_argument("--value-norm", type=float, default=15.0)
    # "real disagreement" noise thresholds (both re-sweepable from the stored JSON).
    ap.add_argument("--top-share-min", type=float, default=0.15,
                    help="teacher visit share of its pick must EXCEED this to count 'real'")
    ap.add_argument("--gap-eps", type=float, default=0.5,
                    help="top-2 Δleaf gap (leaf points) must EXCEED this to count 'real'")
    ap.add_argument("--n", type=int, default=400, help="cap #midgame roots (0=all in band)")
    ap.add_argument("--seed-shuffle", type=int, default=1234,
                    help="shuffle band candidates with this seed before --n (samples across "
                         "strata); 0 = deterministic (k,seed,ply) sort")
    ap.add_argument("--roots", default="",
                    help="explicit 'seed:ply,seed:ply' subset (tests/smoke)")
    ap.add_argument("--workers", type=int, default=1,
                    help="fork pool over positions (net-free CPU; OMP/MKL=1 via env)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    cfg = HeuristicPriorConfig(c_puct=args.c_puct, tau_p=args.tau_p,
                               leaf_quantize=args.leaf_quantize,
                               final_select="visits",   # teacher = visit-argmax
                               value_norm=args.value_norm)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ---- roots: identical loading/join to solver_score; filter to the MIDGAME band ----
    recs = SS.load_sibling_roots(args.qprobe, args.pool)
    print(f"[load] {len(recs)} sibling roots (qprobe ∩ pool)", flush=True)
    cand = [r for r in recs
            if args.k_min <= int(r.get("k_remaining", 99)) <= args.k_max]
    n_in_band = len(cand)
    if args.roots:
        want = set()
        for tok in args.roots.split(","):
            tok = tok.strip()
            if tok:
                s, _, p = tok.partition(":")
                want.add((int(s), int(p)))
        cand = [r for r in cand if (int(r["seed"]), int(r["ply"])) in want]
    elif args.seed_shuffle:
        import random
        random.Random(args.seed_shuffle).shuffle(cand)
    else:
        cand.sort(key=lambda r: (int(r.get("k_remaining", 99)), int(r["seed"]), int(r["ply"])))
    kdist_band = Counter(int(r.get("k_remaining", 99))
                         for r in recs if args.k_min <= int(r.get("k_remaining", 99)) <= args.k_max)
    print(f"[band] k in [{args.k_min},{args.k_max}]: {n_in_band} roots available "
          f"K-dist={dict(sorted(kdist_band.items()))}", flush=True)

    # ---- manifest (before the run) ----
    config = {
        "tool": "midgame_disagreement.py",
        "plan": "measurement/classical_search/TEACHER_TAU_PLAN.md (NEXT diagnostic (a))",
        "agent": {"kind": "puct_heuristic_priors", "factory": "make_heuristic_prior_mcts",
                  "teacher_selector": "visit_argmax", "sims": args.sims, **cfg.as_manifest()},
        "leaf_prior": "argmax over legal of the agent's own softmax(Δleaf/τ) prior "
                      "(make_heuristic_prior_evaluator); agree compared by successor-board key",
        "midgame_band": [args.k_min, args.k_max],
        "noise_thresholds": {"top_share_min": args.top_share_min, "gap_eps": args.gap_eps},
        "gate_bar": 0.20,
        "n_cap": args.n, "seed_shuffle": args.seed_shuffle,
        "roots_subset": args.roots or None,
        "n_in_band": n_in_band,
        "qprobe": args.qprobe, "pool": args.pool,
        "workers": args.workers,
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
        "argv": sys.argv,
        "code_rev": code_rev(),
        "solver_used": False, "net_used": False,
    }
    write_manifest(out_path.parent, kind="midgame_disagreement", game="base",
                   config=config, overwrite=True)

    _CTX.update(cfg=cfg, sims=args.sims, kmin=args.k_min, kmax=args.k_max,
                top_share_min=args.top_share_min, gap_eps=args.gap_eps)

    scored, skips, errs = [], [], []
    t0 = time.perf_counter()
    n_target = args.n if args.n else None

    def _handle(out):
        if out is None:
            return
        if "_error" in out:
            errs.append(out)
            print(f"  [err] {out['_error']}", flush=True)
        elif "_skip" in out:
            skips.append(out)
        else:
            scored.append(out)

    if args.workers <= 1:
        for rec in cand:
            if n_target and len(scored) >= n_target:
                break
            _handle(_analyze_one(rec))
            if scored and len(scored) % 25 == 0:
                el = time.perf_counter() - t0
                print(f"  scored={len(scored)} skip={len(skips)} err={len(errs)} "
                      f"({el / max(len(scored), 1):.2f}s/scored)", flush=True)
    else:
        from multiprocessing import get_context
        ctx = get_context("fork")
        sub = cand[: args.n * 3] if args.n else cand   # 3x headroom for band-skips
        with ctx.Pool(args.workers) as pool:
            for out in pool.imap_unordered(_analyze_one, sub, chunksize=1):
                _handle(out)
                if scored and len(scored) % 25 == 0:
                    el = time.perf_counter() - t0
                    print(f"  scored={len(scored)} skip={len(skips)} err={len(errs)} "
                          f"({el / max(len(scored), 1):.2f}s/scored)", flush=True)
                if n_target and len(scored) >= n_target:
                    break

    dt = time.perf_counter() - t0
    print(f"[done] scored={len(scored)} skipped={len(skips)} errors={len(errs)} "
          f"in {dt:.1f}s", flush=True)

    aggregate = _aggregate(scored, args.top_share_min, args.gap_eps)
    ks = sorted({r["k"] for r in scored})
    by_k = {k: _aggregate([r for r in scored if r["k"] == k],
                          args.top_share_min, args.gap_eps) for k in ks}
    report = {
        "manifest": config,
        "n_in_band": n_in_band,
        "n_scored": len(scored), "n_skipped": len(skips), "n_errors": len(errs),
        "aggregate": aggregate,
        "by_k": by_k,
        "per_root": scored,
    }
    out_path.write_text(json.dumps(report, indent=2))
    print(f"[out] wrote {out_path}", flush=True)

    a = aggregate
    print("\n==== MIDGAME LEAF-PRIOR vs TEACHER DISAGREEMENT ====")
    print(f"n={a['n_scored']}  band k∈[{args.k_min},{args.k_max}] "
          f"(avail {n_in_band})  sims={args.sims}")
    print(f"disagreement_rate      = {a['disagreement_rate']}  "
          f"({a['n_disagree']}/{a['n_scored']})")
    print(f"REAL disagreement_rate = {a['real_disagreement_rate']}  "
          f"({a['n_real_disagree']}/{a['n_scored']})   [gate bar >= 0.20]")
    print(f"  of {a['n_disagree']} disagreements: {a['n_disagree_pass_share']} pass "
          f"visit-share>{args.top_share_min}, {a['n_disagree_pass_gap']} pass "
          f"gap>{args.gap_eps} leaf-pts")
    print(f"mean top_share (midgame) = {a.get('top_share_mean')}  "
          f"p10={a.get('top_share_p10')} p50={a.get('top_share_p50')} "
          f"p90={a.get('top_share_p90')}   (endgame ref: 0.3135)")
    print(f"mean n_legal={a['mean_n_legal']} n_distinct={a['mean_n_distinct']}  "
          f"search {a['search_secs_mean']}s/root")
    verdict = ("FUND Step 1" if (a["real_disagreement_rate"] or 0) >= 0.20
               else "DO NOT fund Step 1")
    print(f"GATE: real_disagreement_rate {a['real_disagreement_rate']} "
          f"{'>=' if (a['real_disagreement_rate'] or 0) >= 0.20 else '<'} 0.20  ->  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
