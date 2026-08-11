#!/usr/bin/env python3
"""PROBE B — MILESTONE 1: fair value-target label pipeline (B1 / PIMC) + the
CRITICAL dynamic-range kill-check.  (docs/PROBE_B_FAIR_INFO_SPEC.md §4, §7.2 / OQ7.2)

WHAT THIS BUILDS
----------------
For a sample of roots (reused from the replay-verified qprobe pool), draw K
determinizations of the KNOWN remaining bag (contents preserved, unseen deck ORDER
re-shuffled, `next_tile` kept — the fair-chance / non-clairvoyant primitive), run
the FAIR (non-clairvoyant) search on each, and compute a
**determinization-averaged value target** per root (and per child action). These are
the FAIR labels (charter Step 4) — NEVER single-true-deck.

Fair search = the SAME v2.9 deep-teacher leaf the qprobe's clairvoyant `action_q`
labels used (HeuristicMCTS, v2.7/v2.9 leaf; env preamble below is byte-identical to
scripts/rod_v2/highgap/probe_signal_density.py), but run per determinization on a
reshuffled bag rather than the true future deck. So the ONLY difference between the
fair target and the clairvoyant reference on the same root is clairvoyance —
apples-to-apples for the range comparison.

Per-determinization ISOLATION: each of the K searches gets its own fresh HeuristicMCTS
(tree cleared per determinization). This is the clairvoyance_gap.py / fair_isolate
pattern — no stale cross-determinization node reuse (the gate-zero leak).

THE KILL-CHECK (§4 dynamic-range guard, open question 7.2)
----------------------------------------------------------
Determinization-AVERAGED targets risk collapsing toward zero — the near-zero-range
residual-target problem that killed CL-036 / bit CL-004. This script REPORTS the
distribution (std / IQR / min / max / histogram) of the fair value targets and
COMPARES their spread to the clairvoyant/h6400 `action_q` spread on the SAME roots,
then prints a VERDICT: ADEQUATE (train against it) or DEGENERATE (kill the fair-target
design BEFORE any training spend). No training happens here.

USAGE (LOCAL, small sample; net-free → CPU-parallel):
  CARCASSONNE_* env is hard-set below (frozen v2.9 Bmild_cap8 leaf) before any import.
  nice -n 19 .venv/bin/python scripts/probe_b/build_fair_targets.py \
      --n-roots 120 --K 12 --sims 800 --workers 12
"""
from __future__ import annotations

import os
# --- frozen v2.9 (Bmild_cap8) leaf: byte-identical to probe_signal_density.py so the
#     fair target uses the SAME leaf as the clairvoyant action_q labels. Must be set
#     BEFORE any carcassonne import (populates virtual_score_v2.DEFAULT_CONFIG). ---
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"            # inert under the curve
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"
os.environ["CARCASSONNE_V25_VALUE_BLEND"] = "0"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")        # net-free — CPU only
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import copy
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import numpy as np
from multiprocessing import get_context

from gen_endgame_positions import replay_to           # canonical (seed, ply) -> (game, board)
from carcassonne_ai.mcts import HeuristicMCTS
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

PROBE_JSONL = REPO / "measurement" / "high_gap_distillation" / "qprobe" / "probe.jsonl"

_W: dict = {}


# --------------------------------------------------------------------------- #
# Fair determinization primitive (the clairvoyance_gap / _reshuffled_root machinery).
# --------------------------------------------------------------------------- #
def _reshuffled_board(board, rng: random.Random):
    """Copy `board`; permute ONLY the unseen `state.deck` (multiset preserved),
    keep `next_tile`. One plausible future — the info a fair player actually has.
    Identical to NeuralMCTS._reshuffled_root but for an arbitrary HeuristicMCTS root."""
    b = copy.deepcopy(board)
    rng.shuffle(b.state.deck)
    b._str_repr_cache = None  # deck order isn't in the key, but be safe
    return b


def _fair_root_targets(game, board, K: int, sims: int, base_seed: int, cfg):
    """Run K fair (non-clairvoyant) HeuristicMCTS searches, one per determinization
    of the known bag, and pool.

    Returns:
      root_value_fair : determinization-AVERAGED root value (root-player POV, [-1,1]).
                        For each determinization the search root Q (root.Q, W/N in the
                        root player's POV) is the value of the position under that
                        one plausible future; averaging over K = the chance-node
                        expectation over unseen orders (the §4 fair value target).
      per_det_root_q  : the K per-determinization root Qs (for spread diagnostics).
      action_q_fair   : {action: determinization-averaged child Q, root-player POV}
                        (the optional per-child fair action target).
      n_children      : # of distinct child actions that got any visits.
    """
    key = game.string_representation(board)
    rng = random.Random(base_seed)  # deterministic K-world sampler (per root)

    per_det_root_q: list[float] = []
    aggN: dict[int, float] = defaultdict(float)
    aggW: dict[int, float] = defaultdict(float)

    for k in range(K):
        det = _reshuffled_board(board, rng)
        # Fresh tree per determinization (fair_isolate / clairvoyance_gap pattern):
        # no stale cross-determinization node reuse.
        m = HeuristicMCTS(game=game, simulations=sims,
                          seed=base_seed * 131 + k, heur_leaf="v2_7", leaf_cfg=cfg)
        m.clear()
        m.search(det)
        # The determinized root shares `key` with the true root (deck order not in
        # the key), so its node is found under the SAME key.
        root = m._nodes[key]
        per_det_root_q.append(float(root.Q))  # root-player POV

        # Pool child stats the same way clairvoyance_gap._choose_action does:
        # summed visits N_a and summed signed value W_a (root-player POV).
        _seen = set()
        for a in sorted(root.children):
            c = root.children[a]
            if c.N <= 0 or id(c) in _seen:
                continue
            _seen.add(id(c))
            sw = c.W if c.player_to_move == root.player_to_move else -c.W
            aggN[int(a)] += c.N
            aggW[int(a)] += sw

    root_value_fair = float(np.mean(per_det_root_q)) if per_det_root_q else 0.0
    action_q_fair = {a: (aggW[a] / aggN[a]) for a in aggN if aggN[a] > 0}
    return root_value_fair, per_det_root_q, action_q_fair, len(action_q_fair)


# --------------------------------------------------------------------------- #
# Worker
# --------------------------------------------------------------------------- #
def _worker_init(K, sims):
    import eval_hybrid_handoff as EH
    _W["cfg"] = EH._heur_leaf_cfg(2.0)   # v2.9 Bmild_cap8 (matches the qprobe labels)
    _W["K"] = int(K)
    _W["sims"] = int(sims)


def _process(rec):
    try:
        seed, ply = int(rec["seed"]), int(rec["ply"])
        game, board = replay_to(seed, ply)
        # qprobe rows carry no checksum, but seed/ply are the canonical replay key
        # (the pool was checksum-verified upstream). Sanity: legal_n must match.
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if int(legal.size) != int(rec.get("legal_n", legal.size)):
            return {"_error": f"{seed}:{ply} legal_n mismatch "
                              f"({legal.size} != {rec.get('legal_n')})"}
        if legal.size < 2:
            return {"_error": f"{seed}:{ply} <2 legal"}

        root_v, per_det, aq_fair, n_kids = _fair_root_targets(
            game, board, _W["K"], _W["sims"], seed * 13 + ply, _W["cfg"]
        )
        if n_kids < 2:
            return {"_error": f"{seed}:{ply} <2 fair children"}

        # Clairvoyant reference (h6400 v2.9 action_q) already on the record.
        clair_aq = {int(a): float(v) for a, v in rec["action_q"].items()}
        clair_qs = sorted(clair_aq.values(), reverse=True)
        clair_range = float(clair_qs[0] - clair_qs[-1])

        fair_qs = sorted(aq_fair.values(), reverse=True)
        fair_range = float(fair_qs[0] - fair_qs[-1]) if len(fair_qs) >= 2 else 0.0

        return {
            "seed": seed, "ply": ply, "phase": rec.get("phase"),
            "k_remaining": rec.get("k_remaining"), "legal_n": int(legal.size),
            "n_fair_children": n_kids,
            # THE fair value target (determinization-averaged root value):
            "fair_root_value": root_v,
            # per-determinization root Qs (spread within a root across worlds):
            "per_det_root_q_std": float(np.std(per_det)),
            "per_det_root_q_min": float(np.min(per_det)),
            "per_det_root_q_max": float(np.max(per_det)),
            # per-child fair action targets + their within-root spread:
            "fair_action_q": {int(a): float(v) for a, v in aq_fair.items()},
            "fair_action_range": fair_range,
            "fair_action_best": float(fair_qs[0]),
            # clairvoyant reference on the SAME root:
            "clair_action_range": clair_range,
            "clair_action_best": float(clair_qs[0]),
            "clair_q_range_recorded": float(rec.get("q_range", clair_range)),
        }
    except Exception as e:  # noqa: BLE001
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} "
                          f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- #
# Sampling: a phase-stratified sample of the qprobe pool (reproducible).
# --------------------------------------------------------------------------- #
def _sample_roots(n_roots: int, seed: int):
    recs = [json.loads(l) for l in open(PROBE_JSONL)]
    by_phase: dict[str, list] = defaultdict(list)
    for r in recs:
        by_phase[r.get("phase", "?")].append(r)
    rng = random.Random(seed)
    per = max(1, n_roots // max(1, len(by_phase)))
    out = []
    for ph in sorted(by_phase):
        pool = by_phase[ph]
        rng.shuffle(pool)
        out.extend(pool[:per])
    rng.shuffle(out)
    return out[:n_roots]


# --------------------------------------------------------------------------- #
# The dynamic-range kill-check report (§4 / OQ 7.2) — the headline deliverable.
# --------------------------------------------------------------------------- #
def _hist(vals, bins):
    counts, edges = np.histogram(vals, bins=bins)
    return [(float(edges[i]), float(edges[i + 1]), int(counts[i]))
            for i in range(len(counts))]


def _stats(vals):
    a = np.asarray(vals, dtype=np.float64)
    q1, q3 = np.percentile(a, [25, 75])
    return {
        "n": int(a.size), "mean": float(a.mean()), "std": float(a.std()),
        "min": float(a.min()), "max": float(a.max()),
        "p05": float(np.percentile(a, 5)), "q1": float(q1),
        "median": float(np.median(a)), "q3": float(q3),
        "p95": float(np.percentile(a, 95)), "iqr": float(q3 - q1),
        "range": float(a.max() - a.min()),
    }


# Kill thresholds (pre-registered here). The residual-target failure mode (CL-036/
# CL-004) is a target distribution whose spread is NEGLIGIBLE — the head cannot get a
# gradient distinguishing positions. We judge the fair ROOT-VALUE target (the label a
# value head trains on) on absolute spread AND relative to the clairvoyant spread on
# the same roots. In [-1,1] value units:
_STD_DEGENERATE = 0.05     # a value-target std < 0.05 has almost no learnable signal
_STD_ADEQUATE = 0.10       # std >= 0.10 is clearly trainable (cf. clair action spread ~0.2)
_REL_DEGENERATE = 0.33     # if fair spread < 1/3 of clairvoyant spread → mostly collapsed


def _verdict(fair_root_stats, ratio_std):
    std = fair_root_stats["std"]
    if std < _STD_DEGENERATE or ratio_std < _REL_DEGENERATE:
        return "DEGENERATE"
    if std >= _STD_ADEQUATE:
        return "ADEQUATE"
    return "MARGINAL"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="build_fair_targets")
    ap.add_argument("--n-roots", type=int, default=120,
                    help="sample size (phase-stratified). LOCAL small samples only.")
    ap.add_argument("--K", type=int, default=12, help="determinizations per root (§5: 8-16)")
    ap.add_argument("--sims", type=int, default=800,
                    help="fair-search sims per determinization (cost = n_roots*K*sims)")
    ap.add_argument("--sample-seed", type=int, default=20260630)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", type=str,
                    default=str(REPO / "measurement" / "probe_b_fair_targets"))
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sample = _sample_roots(args.n_roots, args.sample_seed)
    print(f"[fair-targets] sampling {len(sample)} roots (phase-stratified) | "
          f"K={args.K} sims={args.sims} workers={args.workers}", flush=True)
    print(f"[fair-targets] cost ~= n_roots*K*sims = "
          f"{len(sample)*args.K*args.sims:,} leaf searches", flush=True)

    t0 = time.perf_counter()
    ctx = get_context("spawn")
    rows, errs = [], []
    with ctx.Pool(processes=args.workers, initializer=_worker_init,
                  initargs=(args.K, args.sims)) as pool:
        done = 0
        for r in pool.imap_unordered(_process, sample, chunksize=1):
            done += 1
            if "_error" in r:
                errs.append(r["_error"])
            else:
                rows.append(r)
            if done % 10 == 0 or done == len(sample):
                el = time.perf_counter() - t0
                print(f"  {done}/{len(sample)} ({el/done:.1f}s/root, "
                      f"~{(len(sample)-done)*el/done/60:.1f} min left) "
                      f"| ok={len(rows)} err={len(errs)}", flush=True)

    if not rows:
        print("NO ROWS — all roots errored:")
        for e in errs[:20]:
            print("  ", e)
        return 1

    # --- write the raw per-root fair targets ---
    tgt_path = out / f"fair_targets_n{len(rows)}_K{args.K}_s{args.sims}.jsonl"
    with open(tgt_path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    # ======================================================================= #
    # DYNAMIC-RANGE KILL-CHECK (the headline deliverable).
    # ======================================================================= #
    fair_root_vals = [r["fair_root_value"] for r in rows]          # the value-head label
    fair_action_ranges = [r["fair_action_range"] for r in rows]    # within-root child spread
    clair_action_ranges = [r["clair_action_range"] for r in rows]  # clairvoyant child spread
    per_det_stds = [r["per_det_root_q_std"] for r in rows]         # within-root world spread

    fair_root_stats = _stats(fair_root_vals)
    fair_action_range_stats = _stats(fair_action_ranges)
    clair_action_range_stats = _stats(clair_action_ranges)

    # Ratio of spreads: fair vs clairvoyant, matched on the same roots.
    ratio_std = (fair_action_range_stats["mean"] / clair_action_range_stats["mean"]
                 if clair_action_range_stats["mean"] > 1e-9 else 0.0)
    ratio_root_vs_clair = (fair_root_stats["std"] / clair_action_range_stats["mean"]
                           if clair_action_range_stats["mean"] > 1e-9 else 0.0)

    verdict = _verdict(fair_root_stats, ratio_std)

    report = {
        "config": {"n_roots_ok": len(rows), "n_err": len(errs),
                   "K": args.K, "sims": args.sims, "sample_seed": args.sample_seed,
                   "leaf": "v2.9 Bmild_cap8 (matches qprobe clairvoyant labels)"},
        "fair_root_value_target": fair_root_stats,
        "fair_root_value_hist": _hist(fair_root_vals, bins=20),
        "fair_action_range": fair_action_range_stats,
        "clair_action_range": clair_action_range_stats,
        "per_det_root_q_std": _stats(per_det_stds),
        "comparison": {
            "fair_vs_clair_action_range_ratio(mean)": ratio_std,
            "fair_root_std_over_clair_action_range_mean": ratio_root_vs_clair,
        },
        "thresholds": {"std_degenerate": _STD_DEGENERATE,
                       "std_adequate": _STD_ADEQUATE,
                       "rel_degenerate": _REL_DEGENERATE},
        "VERDICT": verdict,
    }
    rep_path = out / f"range_verdict_n{len(rows)}_K{args.K}_s{args.sims}.json"
    json.dump(report, open(rep_path, "w"), indent=2)

    # --- pretty print ---
    def _pp(name, s):
        print(f"  {name:34s} n={s['n']:4d} mean={s['mean']:+.4f} std={s['std']:.4f} "
              f"min={s['min']:+.4f} q1={s['q1']:+.4f} med={s['median']:+.4f} "
              f"q3={s['q3']:+.4f} max={s['max']:+.4f} iqr={s['iqr']:.4f} "
              f"range={s['range']:.4f}")

    print("\n" + "=" * 78)
    print("PROBE B — FAIR VALUE-TARGET DYNAMIC-RANGE KILL-CHECK (§4 / OQ 7.2)")
    print("=" * 78)
    print(f"roots ok={len(rows)}  err={len(errs)}  K={args.K}  sims={args.sims}")
    print("\n-- distributions --")
    _pp("fair_root_value (THE label)", fair_root_stats)
    _pp("fair_action_range (per root)", fair_action_range_stats)
    _pp("clair_action_range (per root)", clair_action_range_stats)
    _pp("per_det_root_q_std (within root)", _stats(per_det_stds))
    print("\n-- fair_root_value histogram (20 bins) --")
    for lo, hi, c in report["fair_root_value_hist"]:
        bar = "#" * min(60, c)
        print(f"  [{lo:+.3f},{hi:+.3f})  {c:4d} {bar}")
    print("\n-- comparison (fair vs clairvoyant, matched roots) --")
    print(f"  fair/clair action-range ratio (mean of per-root spreads) : {ratio_std:.3f}")
    print(f"  fair_root_value std / clair action-range mean            : {ratio_root_vs_clair:.3f}")
    print("\n-- thresholds --")
    print(f"  DEGENERATE if fair_root_value std < {_STD_DEGENERATE} OR "
          f"fair/clair range ratio < {_REL_DEGENERATE}")
    print(f"  ADEQUATE   if fair_root_value std >= {_STD_ADEQUATE}")
    print("\n" + "=" * 78)
    print(f"VERDICT: {verdict}")
    if verdict == "DEGENERATE":
        print("  -> KILL the fair-target design BEFORE any training spend "
              "(near-zero-range residual-target problem, cf. CL-036 / CL-004).")
    elif verdict == "ADEQUATE":
        print("  -> Fair targets have trainable dynamic range. Milestone-2 "
              "(train fair value + fair-vs-fair screen) is NOT blocked by range.")
    else:
        print("  -> MARGINAL: spread is nonzero but modest; re-check at larger n / "
              "higher sims before committing training spend.")
    print("=" * 78)
    print(f"\n[wrote] targets  : {tgt_path}")
    print(f"[wrote] verdict  : {rep_path}")
    if errs:
        print(f"\n[errors] {len(errs)} (first 5):")
        for e in errs[:5]:
            print("  ", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
